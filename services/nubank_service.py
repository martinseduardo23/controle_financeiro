import csv
import io
import re
from datetime import datetime, date
from decimal import Decimal

from database import db
from models import CompraCartao, Cartao, Conta, Categoria, Lancamento, ParcelaCartao
from services.faturas_cartao import vincular_parcelas_compra
from routes.compras_cartao import criar_parcelas


def obter_ou_criar_cartao_nubank():
    """
    Retorna o cartão 'Nubank' cadastrado no sistema.
    Caso não exista, cria um automaticamente.
    """
    cartao = Cartao.query.filter(Cartao.nome.ilike("%Nubank%")).first()
    if not cartao:
        cartao = Cartao(
            nome="Nubank Roxinho",
            banco="Nubank",
            ultimos_digitos="0000",
            limite=Decimal("5000.00"),
            dia_fechamento=1,
            dia_vencimento=8,
            ativo=True
        )
        db.session.add(cartao)
        db.session.commit()
    return cartao


def obter_ou_criar_conta_nubank():
    """
    Retorna a conta bancária 'NuConta' cadastrada no sistema.
    Caso não exista, cria uma automaticamente.
    """
    conta = Conta.query.filter(Conta.nome.ilike("%Nubank%") | Conta.nome.ilike("%NuConta%")).first()
    if not conta:
        conta = Conta(
            nome="Nubank (NuConta)",
            tipo="Conta corrente",
            saldo_inicial=0.0,
            ativa=True
        )
        db.session.add(conta)
        db.session.commit()
    return conta


def mapear_categoria(categoria_nome, tipo="despesa"):
    """
    Mapeia nomes de categorias comuns do Nubank para categorias do sistema.
    """
    mapa = {
        "alimentacao": "Alimentação",
        "supermercado": "Alimentação",
        "transporte": "Transporte",
        "uber": "Transporte",
        "servicos": "Serviços",
        "saude": "Saúde",
        "lazer": "Lazer",
        "viagem": "Viagem",
        "casa": "Moradia",
        "educacao": "Educação",
        "compras": "Outros"
    }
    nome_padrao = mapa.get(categoria_nome.lower().strip(), categoria_nome.capitalize()) if categoria_nome else "Outros"

    cat = Categoria.query.filter(Categoria.nome.ilike(nome_padrao), Categoria.tipo == tipo).first()
    if not cat:
        # Busca qualquer categoria ativa do tipo correspondente
        cat = Categoria.query.filter_by(tipo=tipo, ativa=True).first()
        if not cat:
            cat = Categoria(nome=nome_padrao, tipo=tipo, ativa=True)
            db.session.add(cat)
            db.session.commit()
    return cat


# =========================================================
# PROCESSAR TRANSAÇÃO DO APPLE PAY (TEMPO REAL)
# =========================================================

def processar_transacao_apple_pay(dados):
    """
    Recebe os dados disparados pelo app Atalhos (Shortcuts) do iPhone via Apple Pay.
    Cadastra a transação como Compra no Cartão Nubank.
    """
    estabelecimento = (
        dados.get("estabelecimento")
        or dados.get("comerciante")
        or dados.get("descricao")
        or dados.get("loja")
        or dados.get("merchant")
        or dados.get("title")
        or dados.get("name")
        or "Compra Apple Pay"
    ).strip()

    valor_raw = dados.get("valor") or dados.get("amount") or dados.get("value") or dados.get("total") or 0

    try:
        if isinstance(valor_raw, (int, float)):
            valor_decimal = Decimal(str(valor_raw)).quantize(Decimal("0.01"))
        elif isinstance(valor_raw, str):
            clean = valor_raw.replace("R$", "").replace(" ", "").strip()
            if "," in clean and "." in clean:
                clean = clean.replace(".", "").replace(",", ".")
            elif "," in clean:
                clean = clean.replace(",", ".")
            valor_decimal = Decimal(clean).quantize(Decimal("0.01"))
        else:
            valor_decimal = Decimal(str(valor_raw)).quantize(Decimal("0.01"))
        valor_decimal = abs(valor_decimal)
    except Exception:
        valor_decimal = Decimal("0.00")

    if valor_decimal <= Decimal("0.00"):
        return None, False, "Valor da transação inválido."

    # Data da compra
    data_str = dados.get("data") or dados.get("date")
    data_compra = date.today()
    if data_str:
        if isinstance(data_str, str):
            try:
                data_compra = datetime.fromisoformat(data_str.replace("Z", "+00:00")).date()
            except Exception:
                try:
                    data_compra = datetime.strptime(data_str[:10], "%Y-%m-%d").date()
                except Exception:
                    data_compra = date.today()
        elif isinstance(data_str, (date, datetime)):
            data_compra = data_str if isinstance(data_str, date) else data_str.date()

    cartao = obter_ou_criar_cartao_nubank()
    transacao_id = str(dados.get("id") or dados.get("transacao_id") or "").strip()
    marcador = f"[Apple Pay: {transacao_id}]" if transacao_id else f"[Apple Pay {data_compra.strftime('%d/%m')}]"

    # Verificação de duplicata
    compra_existente = CompraCartao.query.filter(
        CompraCartao.cartao_id == cartao.id,
        CompraCartao.data_compra == data_compra,
        CompraCartao.valor_total == valor_decimal,
        CompraCartao.descricao.ilike(f"%{estabelecimento[:10]}%")
    ).first()

    if compra_existente:
        return compra_existente, False, f"Compra '{estabelecimento}' de R$ {valor_decimal} já cadastrada anteriormente."

    cat_nome = dados.get("categoria") or dados.get("category") or "Outros"
    categoria = mapear_categoria(cat_nome, tipo="despesa")

    nova_compra = CompraCartao(
        descricao=estabelecimento,
        valor_total=valor_decimal,
        data_compra=data_compra,
        parcelas=1,
        cartao_id=cartao.id,
        categoria_id=categoria.id,
        observacao=marcador
    )

    db.session.add(nova_compra)
    db.session.flush()

    criar_parcelas(nova_compra)
    vincular_parcelas_compra(nova_compra)
    db.session.commit()

    return nova_compra, True, f"Compra '{estabelecimento}' de R$ {valor_decimal} no Nubank registrada em tempo real!"


# =========================================================
# PARSERS DE ARQUIVOS (CSV E OFX DO NUBANK)
# =========================================================

def parsear_csv_nubank(conteudo_str):
    """
    Analisa o CSV do Nubank (Fatura do Cartão ou Extrato da Conta).
    Retorna uma tupla (tipo_detectado, lista_de_transacoes).
    tipo_detectado: 'cartao' ou 'conta'
    """
    linhas = conteudo_str.strip().splitlines()
    if not linhas:
        return None, []

    leitor = csv.reader(linhas)
    cabecalho = next(leitor, None)
    if not cabecalho:
        return None, []

    cabecalho_normalizado = [col.strip().lower() for col in cabecalho]
    transacoes = []

    # Caso 1: Fatura de Cartão de Crédito Nubank (date,category,title,amount)
    if "amount" in cabecalho_normalizado and ("title" in cabecalho_normalizado or "description" in cabecalho_normalizado):
        tipo_detectado = "cartao"
        idx_date = cabecalho_normalizado.index("date") if "date" in cabecalho_normalizado else 0
        idx_title = cabecalho_normalizado.index("title") if "title" in cabecalho_normalizado else cabecalho_normalizado.index("description")
        idx_amount = cabecalho_normalizado.index("amount")
        idx_cat = cabecalho_normalizado.index("category") if "category" in cabecalho_normalizado else -1

        for row in leitor:
            if len(row) <= idx_amount:
                continue
            try:
                data_str = row[idx_date].strip()
                data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
                desc = row[idx_title].strip()
                valor_val = Decimal(row[idx_amount].strip().replace(",", "."))
                categoria_sugerida = row[idx_cat].strip() if idx_cat != -1 and len(row) > idx_cat else "Outros"

                # Ignora pagamento de fatura listado dentro da própria fatura
                if "pagamento recebido" in desc.lower() or "pagamento de fatura" in desc.lower() or valor_val <= 0:
                    continue

                transacoes.append({
                    "data": data_obj,
                    "descricao": desc,
                    "valor": abs(valor_val),
                    "categoria": categoria_sugerida,
                    "tipo": "despesa"
                })
            except Exception:
                continue

        return tipo_detectado, transacoes

    # Caso 2: Extrato da NuConta (Data,Valor,Identificador,Descrição)
    elif "data" in cabecalho_normalizado and "valor" in cabecalho_normalizado:
        tipo_detectado = "conta"
        idx_date = cabecalho_normalizado.index("data")
        idx_val = cabecalho_normalizado.index("valor")
        idx_desc = cabecalho_normalizado.index("descrição") if "descrição" in cabecalho_normalizado else (cabecalho_normalizado.index("descricao") if "descricao" in cabecalho_normalizado else 1)

        for row in leitor:
            if len(row) <= idx_val:
                continue
            try:
                data_str = row[idx_date].strip()
                # Tenta formato DD/MM/AAAA ou AAAA-MM-DD
                if "/" in data_str:
                    data_obj = datetime.strptime(data_str, "%d/%m/%Y").date()
                else:
                    data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()

                desc = row[idx_desc].strip() if len(row) > idx_desc else "Movimentação Nubank"
                valor_raw = Decimal(row[idx_val].strip().replace(",", "."))
                tipo_op = "receita" if valor_raw > 0 else "despesa"

                transacoes.append({
                    "data": data_obj,
                    "descricao": desc,
                    "valor": abs(valor_raw),
                    "categoria": "Outros",
                    "tipo": tipo_op
                })
            except Exception:
                continue

        return tipo_detectado, transacoes

    return "desconhecido", []


def parsear_ofx_nubank(conteudo_str):
    """
    Parser nativo de arquivos bancários OFX sem dependências externas.
    Extrai as tags <STMTTRN> com <DTPOSTED>, <TRNAMT>, <MEMO> e <FITID>.
    """
    blocos_transacao = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", conteudo_str, re.DOTALL | re.IGNORECASE)
    if not blocos_transacao:
        # Tenta formato sem tag de fechamento (comum em OFX 1.0)
        blocos_transacao = re.split(r"<STMTTRN>", conteudo_str, flags=re.IGNORECASE)[1:]

    transacoes = []
    is_cartao = "CREDITCARD" in conteudo_str.upper()

    for bloco in blocos_transacao:
        try:
            amt_match = re.search(r"<TRNAMT>\s*([-+]?\d*\.?\d+)", bloco, re.IGNORECASE)
            dt_match = re.search(r"<DTPOSTED>\s*(\d{8})", bloco, re.IGNORECASE)
            memo_match = re.search(r"<MEMO>\s*([^<\r\n]+)", bloco, re.IGNORECASE)
            fitid_match = re.search(r"<FITID>\s*([^<\r\n]+)", bloco, re.IGNORECASE)

            if not amt_match or not dt_match:
                continue

            valor_raw = Decimal(amt_match.group(1).strip())
            dt_raw = dt_match.group(1).strip()
            data_obj = datetime.strptime(dt_raw, "%Y%m%d").date()

            desc = memo_match.group(1).strip() if memo_match else "Transação Nubank"
            fitid = fitid_match.group(1).strip() if fitid_match else ""

            tipo_op = "receita" if valor_raw > 0 else "despesa"

            # Se for fatura de cartão e for pagamento da própria fatura, pula
            if is_cartao and (valor_raw > 0 or "pagamento" in desc.lower()):
                continue

            transacoes.append({
                "data": data_obj,
                "descricao": desc,
                "valor": abs(valor_raw),
                "categoria": "Outros",
                "tipo": tipo_op,
                "fitid": fitid
            })
        except Exception:
            continue

    tipo_detectado = "cartao" if is_cartao else "conta"
    return tipo_detectado, transacoes


# =========================================================
# IMPORTAÇÃO EM LOTE COM PREVENÇÃO DE DUPLICATAS
# =========================================================

def importar_lote_nubank(transacoes, destino="cartao"):
    """
    Importa a lista de transações com verificação inteligente de duplicatas
    (compatibilidade com compras já inseridas via Apple Pay ou importadas antes).
    """
    importados = 0
    duplicados = 0

    if destino == "cartao":
        cartao = obter_ou_criar_cartao_nubank()
        for item in transacoes:
            data_item = item["data"]
            valor_item = item["valor"]
            desc_item = item["descricao"]

            # Checa se já existe compra similar no cartão (evita duplicar com Apple Pay)
            existente = CompraCartao.query.filter(
                CompraCartao.cartao_id == cartao.id,
                CompraCartao.data_compra == data_item,
                CompraCartao.valor_total == valor_item,
                CompraCartao.descricao.ilike(f"%{desc_item[:12]}%")
            ).first()

            if existente:
                duplicados += 1
                continue

            categoria = mapear_categoria(item.get("categoria", "Outros"), tipo="despesa")
            nova_compra = CompraCartao(
                descricao=desc_item,
                valor_total=valor_item,
                data_compra=data_item,
                parcelas=1,
                cartao_id=cartao.id,
                categoria_id=categoria.id,
                observacao="[Importado Nubank]"
            )
            db.session.add(nova_compra)
            db.session.flush()

            criar_parcelas(nova_compra)
            vincular_parcelas_compra(nova_compra)
            importados += 1

    else:
        conta = obter_ou_criar_conta_nubank()
        for item in transacoes:
            data_item = item["data"]
            valor_item = item["valor"]
            desc_item = item["descricao"]
            tipo_item = item.get("tipo", "despesa")

            # Checa se já existe lançamento similar na conta
            existente = Lancamento.query.filter(
                Lancamento.conta_id == conta.id,
                Lancamento.data == data_item,
                Lancamento.valor == valor_item,
                Lancamento.descricao.ilike(f"%{desc_item[:12]}%")
            ).first()

            if existente:
                duplicados += 1
                continue

            categoria = mapear_categoria(item.get("categoria", "Outros"), tipo=tipo_item)
            novo_lanc = Lancamento(
                descricao=desc_item,
                valor=valor_item,
                tipo=tipo_item,
                data=data_item,
                status="pago",
                observacao="[Importado NuConta]",
                conta_id=conta.id,
                categoria_id=categoria.id
            )
            db.session.add(novo_lanc)
            importados += 1

    db.session.commit()
    return {
        "importados": importados,
        "duplicados": duplicados,
        "total": len(transacoes)
    }
