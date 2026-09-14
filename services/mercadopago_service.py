import os
import json
import urllib.request
import urllib.error
from datetime import datetime, date
from decimal import Decimal

from database import db
from models import Lancamento, Conta, Categoria
from config import BASE_DIR, Config, obter_token_mercadopago


def salvar_token_mercadopago(token):
    """
    Salva o Access Token do Mercado Pago em data/mp_token.txt
    e atualiza a configuração em tempo de execução.
    """
    token = token.strip()
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

    token_file = os.path.join(data_dir, "mp_token.txt")
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(token)

    Config.MERCADO_PAGO_ACCESS_TOKEN = token
    return token


def consultar_pagamento_mp(payment_id, access_token=None):
    """
    Consulta os dados detalhados de um pagamento na API oficial do Mercado Pago.
    Retorna o dicionário com os dados da resposta ou None em caso de falha.
    """
    token = access_token or Config.MERCADO_PAGO_ACCESS_TOKEN or obter_token_mercadopago()
    if not token:
        return None

    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "ControleFinanceiroApp/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 201):
                raw_data = response.read().decode("utf-8")
                return json.loads(raw_data)
    except urllib.error.HTTPError as e:
        print(f"[Mercado Pago API HTTP Error {e.code}]: {e.read().decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"[Mercado Pago API Error]: {e}")

    return None


def obter_ou_criar_conta_mp():
    """
    Retorna a conta 'Mercado Pago' cadastrada no sistema.
    Caso não exista, cria uma automaticamente.
    """
    conta = Conta.query.filter_by(nome="Mercado Pago").first()
    if not conta:
        conta = Conta(
            nome="Mercado Pago",
            tipo="Carteira",
            saldo_inicial=0.0,
            ativa=True
        )
        db.session.add(conta)
        db.session.commit()
    return conta


def obter_ou_criar_categoria_mp(nome="Mercado Pago", tipo="despesa"):
    """
    Retorna uma categoria com o nome especificado.
    Caso não exista, cria uma automaticamente.
    """
    cat = Categoria.query.filter_by(nome=nome, tipo=tipo).first()
    if not cat:
        # Se não houver específica, busca alguma categoria padrão do mesmo tipo
        cat_geral = Categoria.query.filter_by(tipo=tipo, ativa=True).first()
        if cat_geral:
            return cat_geral
        cat = Categoria(
            nome=nome,
            tipo=tipo,
            ativa=True
        )
        db.session.add(cat)
        db.session.commit()
    return cat


def processar_pagamento_mp(dados_pagamento):
    """
    Converte o objeto de pagamento retornado pela API do Mercado Pago (ou simulação)
    em um registro na tabela 'lancamentos', evitando duplicações por idempotência.
    """
    payment_id = str(dados_pagamento.get("id") or dados_pagamento.get("payment_id") or "")
    if not payment_id:
        return None, False, "ID do pagamento ausente."

    # 1. Idempotência: Checa se já existe lançamento com este identificador
    marcador = f"[Mercado Pago ID: {payment_id}]"
    existente = Lancamento.query.filter(
        Lancamento.observacao.like(f"%{marcador}%")
    ).first()

    if existente:
        return existente, False, f"Pagamento #{payment_id} já registrado anteriormente."

    # 2. Dados financeiros
    valor_raw = dados_pagamento.get("transaction_amount") or dados_pagamento.get("valor") or 0
    try:
        valor_decimal = Decimal(str(valor_raw)).quantize(Decimal("0.01"))
    except Exception:
        valor_decimal = Decimal("0.00")

    if valor_decimal <= Decimal("0.00"):
        return None, False, "Valor da transação inválido ou zerado."

    # 3. Descrição
    descricao = (
        dados_pagamento.get("description")
        or dados_pagamento.get("descricao")
        or dados_pagamento.get("reason")
        or f"Transação Mercado Pago #{payment_id}"
    ).strip()

    # 4. Tipo (receita vs despesa)
    tipo_informado = dados_pagamento.get("tipo")
    if tipo_informado in ("receita", "despesa"):
        tipo = tipo_informado
    else:
        # Se recebimento de Pix ou pagamento de terceiros
        operation_type = dados_pagamento.get("operation_type", "")
        collector_id = str(dados_pagamento.get("collector_id", ""))
        user_id = str(dados_pagamento.get("user_id", ""))

        if operation_type in ("money_transfer", "bank_transfer") and collector_id == user_id:
            tipo = "receita"
        else:
            tipo = "despesa"

    # 5. Data da transação
    data_transacao = date.today()
    data_str = dados_pagamento.get("date_approved") or dados_pagamento.get("date_created") or dados_pagamento.get("data")
    if data_str:
        if isinstance(data_str, str):
            try:
                # Tenta formato ISO 8601 comum no Mercado Pago
                data_transacao = datetime.fromisoformat(data_str.replace("Z", "+00:00")).date()
            except Exception:
                try:
                    data_transacao = datetime.strptime(data_str[:10], "%Y-%m-%d").date()
                except Exception:
                    data_transacao = date.today()
        elif isinstance(data_str, (date, datetime)):
            data_transacao = data_str if isinstance(data_str, date) else data_str.date()

    # 6. Status do pagamento
    status_mp = str(dados_pagamento.get("status", "approved")).lower()
    status_lancamento = "pago" if status_mp in ("approved", "accredited", "pago") else "pendente"

    # 7. Conta e Categoria
    conta = obter_ou_criar_conta_mp()
    categoria = obter_ou_criar_categoria_mp(nome="Mercado Pago", tipo=tipo)

    # 8. Criação do Lançamento
    detalhes_op = []
    payment_method = dados_pagamento.get("payment_method_id")
    if payment_method:
        detalhes_op.append(f"Método: {payment_method}")
    detalhes_op.append(marcador)

    obs_final = " | ".join(detalhes_op)

    novo_lancamento = Lancamento(
        descricao=descricao,
        valor=valor_decimal,
        tipo=tipo,
        data=data_transacao,
        status=status_lancamento,
        observacao=obs_final,
        conta_id=conta.id,
        categoria_id=categoria.id
    )

    db.session.add(novo_lancamento)
    db.session.commit()

    return novo_lancamento, True, f"Lançamento '{descricao}' de R$ {valor_decimal} registrado com sucesso!"
