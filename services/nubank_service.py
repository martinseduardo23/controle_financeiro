import csv
import io
import re
from datetime import datetime, date
from decimal import Decimal

from database import db
from models import CompraCartao, Cartao, Conta, Categoria, Lancamento, ParcelaCartao
from services.faturas_cartao import vincular_parcelas_compra
from routes.compras_cartao import criar_parcelas


def obter_ou_criar_cartao_nubank(usuario_id=None):
    """
    Retorna o cartão 'Nubank' cadastrado no sistema para o usuário especificado.
    Caso não exista, cria um automaticamente.
    """
    cartao = Cartao.query.filter(Cartao.usuario_id == usuario_id, Cartao.nome.ilike("%Nubank%")).first()
    if not cartao:
        cartao = Cartao(
            usuario_id=usuario_id,
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


def obter_ou_criar_conta_nubank(usuario_id=None):
    """
    Retorna a conta bancária 'NuConta' cadastrada no sistema para o usuário.
    Caso não exista, cria uma automaticamente.
    """
    conta = Conta.query.filter(
        Conta.usuario_id == usuario_id,
        (Conta.nome.ilike("%Nubank%") | Conta.nome.ilike("%NuConta%"))
    ).first()
    if not conta:
        conta = Conta(
            usuario_id=usuario_id,
            nome="Nubank (NuConta)",
            tipo="Conta corrente",
            saldo_inicial=0.0,
            ativa=True
        )
        db.session.add(conta)
        db.session.commit()
    return conta


def inferir_categoria_por_texto(descricao):
    """
    Identifica de forma inteligente a categoria a partir do estabelecimento ou descrição.
    """
    desc = (descricao or "").lower()
    regras = [
        ("Transporte", ["uber", "99app", "99 *", "99pay", "posto", "combustivel", "gasolina", "etanol", "shell", "ipiranga", "sem parar", "estapar", "estacionamento", "pedagio", "veloe", "concessionaria", "auto posto"]),
        ("Alimentação", ["ifood", "mcdonald", "burger king", "bk ", "restaurante", "padaria", "pao de acucar", "supermercado", "mercado", "carrefour", "assai", "atacadao", "acougue", "cafe", "lanchonete", "pizza", "churrascaria", "hortifruti", "bistrô", "bistro", "chocolat", "sorvet"]),
        ("Lazer", ["netflix", "spotify", "prime video", "hbo", "disney", "cinema", "kinoplex", "ingresso", "steam", "playstation", "xbox", "bar ", "show", "eventim"]),
        ("Saúde", ["droga raia", "drogasil", "farmacia", "drogaria", "pague menos", "panvel", "hospital", "laboratorio", "consulta", "medico", "odont", "otica", "clube da saude"]),
        ("Compras", ["amazon", "mercado livre", "mercadolivre", "shopee", "magalu", "magazine luiza", "aliexpress", "zara", "renner", "riachuelo", "shein", "loja", "eletronicos", "centauro", "decathlon", "kabum", "kalunga"]),
        ("Moradia", ["enel", "cpfl", "sabesp", "copasa", "sanepar", "eletropaulo", "luz", "agua", "gas", "condominio", "aluguel", "leroy merlin", "telhanorte", "camicado", "tok&stok", "tok stok"]),
        ("Serviços", ["claro", "vivo", "tim", "oi", "provedor", "assinatura", "apple.com", "google", "microsoft", "openai", "chatgpt", "correios", "cartorio"])
    ]
    for cat_nome, palavras in regras:
        for p in palavras:
            if p in desc:
                return cat_nome
    return None


def parse_data_flexivel(data_str):
    """Converte strings em múltiplos formatos comuns de data para objeto date."""
    if not data_str:
        return None
    data_limpa = str(data_str).strip().split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(data_limpa, fmt).date()
        except ValueError:
            pass
    return None


def parse_valor_flexivel(val_str):
    """Converte valores com notação brasileira ou internacional para Decimal limpo."""
    if val_str is None:
        return Decimal("0.00")
    if isinstance(val_str, (int, float, Decimal)):
        return Decimal(str(val_str)).quantize(Decimal("0.01"))
    clean = str(val_str).replace("R$", "").replace(" ", "").strip()
    if not clean:
        return Decimal("0.00")
    if "." in clean and "," in clean:
        if clean.rfind(",") > clean.rfind("."):
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(",", "")
    elif "," in clean:
        clean = clean.replace(",", ".")
    return Decimal(clean).quantize(Decimal("0.01"))


def extrair_info_parcela(descricao):
    """
    Detecta se a descrição do Nubank contém menção a parcelamento (ex: 'Parcela 2/5', '01/03', '(2/10)').
    Retorna (descricao_limpa, numero_parcela, total_parcelas).
    """
    if not descricao:
        return descricao, 1, 1

    padrao1 = re.search(r"(?:parcela|parc\.?)\s*(\d{1,2})\s*(?:/|de)\s*(\d{1,2})", descricao, re.IGNORECASE)
    if padrao1:
        num = int(padrao1.group(1))
        tot = int(padrao1.group(2))
        if 1 <= num <= tot <= 99:
            return descricao.strip(), num, tot

    padrao2 = re.search(r"[\(-]?\s*(\d{1,2})\s*/\s*(\d{1,2})\)?\s*$", descricao)
    if padrao2:
        num = int(padrao2.group(1))
        tot = int(padrao2.group(2))
        if 1 <= num <= tot <= 99 and tot > 1:
            return descricao.strip(), num, tot

    return descricao.strip(), 1, 1


def mapear_categoria(categoria_nome, tipo="despesa", usuario_id=None, descricao=None):
    """
    Mapeia nomes de categorias comuns do Nubank para categorias do usuário no sistema.
    Usa inferência textual caso a categoria seja genérica ('Outros') ou não fornecida.
    """
    mapa = {
        "alimentacao": "Alimentação",
        "alimentação": "Alimentação",
        "supermercado": "Alimentação",
        "restaurante": "Alimentação",
        "transporte": "Transporte",
        "uber": "Transporte",
        "servicos": "Serviços",
        "serviços": "Serviços",
        "saude": "Saúde",
        "saúde": "Saúde",
        "lazer": "Lazer",
        "viagem": "Viagem",
        "casa": "Moradia",
        "moradia": "Moradia",
        "educacao": "Educação",
        "educação": "Educação",
        "compras": "Compras",
        "vestuário": "Compras",
        "vestuario": "Compras",
        "eletronicos": "Compras",
        "eletrônicos": "Compras",
        "outros": "Outros"
    }

    cat_limpa = (categoria_nome or "").lower().strip()
    nome_padrao = mapa.get(cat_limpa)

    if (not nome_padrao or nome_padrao == "Outros") and descricao:
        infr = inferir_categoria_por_texto(descricao)
        if infr:
            nome_padrao = infr

    if not nome_padrao:
        nome_padrao = categoria_nome.capitalize() if categoria_nome else "Outros"

    cat = Categoria.query.filter(
        Categoria.usuario_id == usuario_id,
        Categoria.nome.ilike(nome_padrao),
        Categoria.tipo == tipo
    ).first()

    if not cat:
        cat = Categoria.query.filter(
            Categoria.usuario_id == usuario_id,
            Categoria.nome.ilike(f"%{nome_padrao[:5]}%"),
            Categoria.tipo == tipo,
            Categoria.ativa == True
        ).first()

    if not cat:
        cat = Categoria(usuario_id=usuario_id, nome=nome_padrao, tipo=tipo, ativa=True)
        db.session.add(cat)
        db.session.flush()

    return cat


# =========================================================
# PROCESSAR TRANSAÇÃO DO APPLE PAY (TEMPO REAL)
# =========================================================

def processar_transacao_apple_pay(dados, usuario_id=None):
    """
    Recebe os dados disparados pelo app Atalhos (Shortcuts) do iPhone via Apple Pay.
    Cadastra a transação como Compra no Cartão Nubank do usuário especificado.
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

    cartao = obter_ou_criar_cartao_nubank(usuario_id=usuario_id)
    transacao_id = str(dados.get("id") or dados.get("transacao_id") or "").strip()
    marcador = f"[Apple Pay: {transacao_id}]" if transacao_id else f"[Apple Pay {data_compra.strftime('%d/%m')}]"

    # Verificação de duplicata para o usuário
    compra_existente = CompraCartao.query.filter(
        CompraCartao.usuario_id == usuario_id,
        CompraCartao.cartao_id == cartao.id,
        CompraCartao.data_compra == data_compra,
        CompraCartao.valor_total == valor_decimal,
        CompraCartao.descricao.ilike(f"%{estabelecimento[:10]}%")
    ).first()

    if compra_existente:
        return compra_existente, False, f"Compra '{estabelecimento}' de R$ {valor_decimal} já cadastrada anteriormente."

    cat_nome = dados.get("categoria") or dados.get("category") or "Outros"
    categoria = mapear_categoria(cat_nome, tipo="despesa", usuario_id=usuario_id)

    nova_compra = CompraCartao(
        usuario_id=usuario_id,
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
    Suporta diferentes delimitadores (, ou ;), BOM UTF-8 e variações de cabeçalhos.
    Retorna uma tupla (tipo_detectado, lista_de_transacoes).
    tipo_detectado: 'cartao' ou 'conta'
    """
    linhas = conteudo_str.strip().lstrip("\ufeff").splitlines()
    if not linhas:
        return None, []

    # Detecta delimitador (, ou ;)
    primeira_linha = linhas[0]
    delimiter = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","

    leitor = csv.reader(linhas, delimiter=delimiter)
    cabecalho = next(leitor, None)
    if not cabecalho:
        return None, []

    cabecalho_normalizado = [col.strip().lower() for col in cabecalho]
    transacoes = []

    # Localiza índices de colunas de forma resiliente
    idx_date = next((i for i, c in enumerate(cabecalho_normalizado) if c in ("date", "data")), -1)
    idx_title = next((i for i, c in enumerate(cabecalho_normalizado) if c in ("title", "titulo", "título", "description", "descricao", "descrição", "estabelecimento", "nome")), -1)
    idx_amount = next((i for i, c in enumerate(cabecalho_normalizado) if c in ("amount", "valor", "valor (r$)")), -1)
    idx_cat = next((i for i, c in enumerate(cabecalho_normalizado) if c in ("category", "categoria")), -1)
    idx_id = next((i for i, c in enumerate(cabecalho_normalizado) if c in ("identificador", "id")), -1)

    # Identifica se é extrato de conta (presença de 'identificador' ou similar)
    is_conta = idx_id != -1 and ("identificador" in cabecalho_normalizado)

    if not is_conta and idx_amount != -1 and (idx_title != -1 or idx_date != -1):
        tipo_detectado = "cartao"
        idx_title_safe = idx_title if idx_title != -1 else 1

        for row in leitor:
            if len(row) <= idx_amount:
                continue
            try:
                data_str = row[idx_date].strip() if idx_date != -1 and len(row) > idx_date else ""
                data_obj = parse_data_flexivel(data_str) or date.today()

                desc_raw = row[idx_title_safe].strip() if len(row) > idx_title_safe else "Compra Nubank"
                valor_dec = parse_valor_flexivel(row[idx_amount])
                categoria_sugerida = row[idx_cat].strip() if idx_cat != -1 and len(row) > idx_cat else "Outros"

                desc_lower = desc_raw.lower()

                # Ignora pagamento da própria fatura listado dentro do arquivo
                if "pagamento recebido" in desc_lower or "pagamento de fatura" in desc_lower:
                    continue

                desc_limpa, num_parc, tot_parc = extrair_info_parcela(desc_raw)

                # Se o valor for negativo e não for pagamento, pode ser estorno/reembolso
                if valor_dec < Decimal("0.00"):
                    if "estorno" in desc_lower or "reembolso" in desc_lower or "cancelamento" in desc_lower:
                        tipo_op = "estorno"
                    else:
                        continue  # ignora créditos genéricos de pagamento
                else:
                    tipo_op = "despesa"

                transacoes.append({
                    "data": data_obj,
                    "descricao": desc_limpa,
                    "valor": abs(valor_dec),
                    "categoria": categoria_sugerida,
                    "tipo": tipo_op,
                    "num_parcela": num_parc,
                    "total_parcelas": tot_parc
                })
            except Exception:
                continue

        return tipo_detectado, transacoes

    elif idx_date != -1 and idx_amount != -1:
        tipo_detectado = "conta"
        idx_desc_safe = idx_title if idx_title != -1 else (cabecalho_normalizado.index("descrição") if "descrição" in cabecalho_normalizado else (cabecalho_normalizado.index("descricao") if "descricao" in cabecalho_normalizado else 1))

        for row in leitor:
            if len(row) <= idx_amount:
                continue
            try:
                data_str = row[idx_date].strip()
                data_obj = parse_data_flexivel(data_str) or date.today()

                desc = row[idx_desc_safe].strip() if len(row) > idx_desc_safe else "Movimentação Nubank"
                valor_raw = parse_valor_flexivel(row[idx_amount])
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

            valor_raw = parse_valor_flexivel(amt_match.group(1).strip())
            dt_raw = dt_match.group(1).strip()
            data_obj = datetime.strptime(dt_raw, "%Y%m%d").date()

            desc = memo_match.group(1).strip() if memo_match else "Transação Nubank"
            fitid = fitid_match.group(1).strip() if fitid_match else ""

            tipo_op = "receita" if valor_raw > 0 else "despesa"

            # Se for fatura de cartão e for pagamento da própria fatura, pula
            if is_cartao and (valor_raw > 0 or "pagamento" in desc.lower()):
                continue

            desc_limpa, num_parc, tot_parc = extrair_info_parcela(desc)

            transacoes.append({
                "data": data_obj,
                "descricao": desc_limpa,
                "valor": abs(valor_raw),
                "categoria": "Outros",
                "tipo": tipo_op,
                "fitid": fitid,
                "num_parcela": num_parc,
                "total_parcelas": tot_parc
            })
        except Exception:
            continue

    tipo_detectado = "cartao" if is_cartao else "conta"
    return tipo_detectado, transacoes


# =========================================================
# IMPORTAÇÃO EM LOTE COM PREVENÇÃO DE DUPLICATAS
# =========================================================

def importar_lote_nubank(transacoes, destino="cartao", usuario_id=None, cartao_id=None, conta_id=None, fatura_mes_ano=None):
    """
    Importa a lista de transações para o cartão ou conta escolhida pelo usuário.
    Garante vinculação imediata à fatura correta e preserva parcelamentos.
    """
    from services.faturas_cartao import vincular_parcela, recalcular_valor_fatura

    importados = 0
    duplicados = 0

    if destino == "cartao":
        # Seleciona o cartão escolhido ou busca/cria o cartão Nubank
        if cartao_id and str(cartao_id).strip() not in ("criar_novo", "", "None"):
            try:
                cartao = Cartao.query.filter_by(id=int(cartao_id), usuario_id=usuario_id).first()
            except (ValueError, TypeError):
                cartao = None
            if not cartao:
                cartao = obter_ou_criar_cartao_nubank(usuario_id=usuario_id)
        else:
            cartao = obter_ou_criar_cartao_nubank(usuario_id=usuario_id)

        # Mês/ano fixo opcional para a fatura (ex: '2026-10')
        ano_fixo = None
        mes_fixo = None
        if fatura_mes_ano and str(fatura_mes_ano).strip() not in ("auto", "", "None") and "-" in str(fatura_mes_ano):
            try:
                partes = fatura_mes_ano.strip().split("-")
                ano_fixo = int(partes[0])
                mes_fixo = int(partes[1])
            except Exception:
                ano_fixo = None
                mes_fixo = None

        # Rastreia contagem de itens duplicados dentro do lote
        itens_no_banco = {}

        for item in transacoes:
            data_item = item["data"]
            valor_item = item["valor"]
            desc_item = item["descricao"]
            num_parc = item.get("num_parcela", 1)
            tot_parc = item.get("total_parcelas", 1)

            chave = (data_item, str(valor_item), desc_item[:12].lower())

            # Consulta quantas vezes esse registro já existe no banco
            if chave not in itens_no_banco:
                qtd_existente = CompraCartao.query.filter(
                    CompraCartao.usuario_id == usuario_id,
                    CompraCartao.cartao_id == cartao.id,
                    CompraCartao.data_compra == data_item,
                    CompraCartao.valor_total == valor_item,
                    CompraCartao.descricao.ilike(f"%{desc_item[:12]}%")
                ).count()
                itens_no_banco[chave] = {"existentes": qtd_existente, "inseridos": 0}

            # Se já foi inserido tantas vezes quanto já existia, ignoramos
            if itens_no_banco[chave]["inseridos"] < itens_no_banco[chave]["existentes"]:
                itens_no_banco[chave]["inseridos"] += 1
                duplicados += 1
                continue

            categoria = mapear_categoria(
                item.get("categoria", "Outros"),
                tipo="despesa",
                usuario_id=usuario_id,
                descricao=desc_item
            )

            obs_txt = f"[Importado Nubank] Parcela {num_parc}/{tot_parc}" if tot_parc > 1 else "[Importado Nubank]"

            nova_compra = CompraCartao(
                usuario_id=usuario_id,
                descricao=desc_item,
                valor_total=valor_item,
                data_compra=data_item,
                parcelas=1,
                cartao_id=cartao.id,
                categoria_id=categoria.id,
                observacao=obs_txt
            )
            db.session.add(nova_compra)
            db.session.flush()

            # Cria a parcela correspondente
            parcela = ParcelaCartao(
                compra_id=nova_compra.id,
                numero=num_parc,
                total_parcelas=tot_parc,
                valor=valor_item,
                data_prevista=data_item,
                status="aberta",
                pago=False
            )
            db.session.add(parcela)
            db.session.flush()

            # Vincula a parcela à fatura correspondente
            if ano_fixo and mes_fixo:
                fatura = vincular_parcela(parcela, cartao, ano_fixo=ano_fixo, mes_fixo=mes_fixo)
            else:
                fatura = vincular_parcela(parcela, cartao)

            itens_no_banco[chave]["inseridos"] += 1
            importados += 1

        db.session.commit()
        return {
            "importados": importados,
            "duplicados": duplicados,
            "total": len(transacoes),
            "destino_nome": cartao.nome,
            "cartao_id": cartao.id
        }

    else:
        # Seleciona a conta escolhida ou busca/cria a NuConta
        if conta_id and str(conta_id).strip() not in ("criar_nova", "", "None"):
            try:
                conta = Conta.query.filter_by(id=int(conta_id), usuario_id=usuario_id).first()
            except (ValueError, TypeError):
                conta = None
            if not conta:
                conta = obter_ou_criar_conta_nubank(usuario_id=usuario_id)
        else:
            conta = obter_ou_criar_conta_nubank(usuario_id=usuario_id)

        itens_no_banco = {}

        for item in transacoes:
            data_item = item["data"]
            valor_item = item["valor"]
            desc_item = item["descricao"]
            tipo_item = item.get("tipo", "despesa")

            chave = (data_item, str(valor_item), desc_item[:12].lower())

            if chave not in itens_no_banco:
                qtd_existente = Lancamento.query.filter(
                    Lancamento.usuario_id == usuario_id,
                    Lancamento.conta_id == conta.id,
                    Lancamento.data == data_item,
                    Lancamento.valor == valor_item,
                    Lancamento.descricao.ilike(f"%{desc_item[:12]}%")
                ).count()
                itens_no_banco[chave] = {"existentes": qtd_existente, "inseridos": 0}

            if itens_no_banco[chave]["inseridos"] < itens_no_banco[chave]["existentes"]:
                itens_no_banco[chave]["inseridos"] += 1
                duplicados += 1
                continue

            categoria = mapear_categoria(
                item.get("categoria", "Outros"),
                tipo=tipo_item,
                usuario_id=usuario_id,
                descricao=desc_item
            )

            novo_lanc = Lancamento(
                usuario_id=usuario_id,
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
            itens_no_banco[chave]["inseridos"] += 1
            importados += 1

        db.session.commit()
        return {
            "importados": importados,
            "duplicados": duplicados,
            "total": len(transacoes),
            "destino_nome": conta.nome,
            "conta_id": conta.id
        }
