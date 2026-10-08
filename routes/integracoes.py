import json
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session

from database import db
from models import Lancamento, Conta, CompraCartao, Cartao, Usuario
from config import Config, obter_token_mercadopago
from services.mercadopago_service import (
    salvar_token_mercadopago,
    consultar_pagamento_mp,
    processar_pagamento_mp,
    obter_ou_criar_conta_mp
)
from services.nubank_service import (
    processar_transacao_apple_pay,
    parsear_csv_nubank,
    parsear_ofx_nubank,
    importar_lote_nubank,
    obter_ou_criar_cartao_nubank,
    obter_ou_criar_conta_nubank
)

integracoes_bp = Blueprint("integracoes", __name__)


# =========================================================
# PAINEL DA INTEGRAÇÃO DO MERCADO PAGO
# =========================================================

@integracoes_bp.route("/integracoes/mercadopago", methods=["GET"])
def mercadopago_painel():
    usuario_id = session.get("usuario_id")
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    token_webhook = usuario.webhook_token if usuario and usuario.webhook_token else ""

    token_atual = Config.MERCADO_PAGO_ACCESS_TOKEN or obter_token_mercadopago()
    tem_token = bool(token_atual and len(token_atual) > 10)

    # URL pública personalizada para o webhook do usuário
    host = request.host_url.rstrip("/")
    if token_webhook:
        webhook_url = f"{host}/webhooks/mercadopago/{token_webhook}"
    else:
        webhook_url = f"{host}{url_for('integracoes.webhook_mercadopago')}"

    # Últimas movimentações vindas do Mercado Pago para este usuário
    ultimos_lancamentos = (
        Lancamento.query
        .filter(
            Lancamento.usuario_id == usuario_id,
            Lancamento.observacao.like("%[Mercado Pago ID:%")
        )
        .order_by(Lancamento.data.desc(), Lancamento.id.desc())
        .limit(10)
        .all()
    )

    conta_mp = Conta.query.filter_by(usuario_id=usuario_id, nome="Mercado Pago").first()

    return render_template(
        "integracao_mercadopago.html",
        tem_token=tem_token,
        token_preview=f"{token_atual[:8]}...{token_atual[-4:]}" if tem_token else "",
        webhook_url=webhook_url,
        ultimos_lancamentos=ultimos_lancamentos,
        conta_mp=conta_mp
    )


# =========================================================
# SALVAR TOKEN DO MERCADO PAGO
# =========================================================

@integracoes_bp.route("/integracoes/mercadopago/configurar", methods=["POST"])
def mercadopago_configurar():
    usuario_id = session.get("usuario_id")
    token = request.form.get("access_token", "").strip()
    if not token:
        flash("Informe um Access Token válido.", "danger")
    else:
        salvar_token_mercadopago(token)
        # Garante que a conta bancária do usuário exista
        obter_ou_criar_conta_mp(usuario_id=usuario_id)
        flash("Access Token do Mercado Pago configurado com sucesso!", "success")

    return redirect(url_for("integracoes.mercadopago_painel"))


# =========================================================
# SIMULADOR DE TRANSAÇÕES
# =========================================================

@integracoes_bp.route("/integracoes/mercadopago/simular", methods=["POST"])
def mercadopago_simular():
    usuario_id = session.get("usuario_id")
    descricao = request.form.get("descricao", "Compra no Mercado Livre").strip()
    valor_raw = request.form.get("valor", "49.90").replace(",", ".").strip()
    tipo = request.form.get("tipo", "despesa")
    metodo = request.form.get("metodo", "pix")

    try:
        valor = float(valor_raw)
    except ValueError:
        flash("Valor inválido para simulação.", "danger")
        return redirect(url_for("integracoes.mercadopago_painel"))

    timestamp = int(datetime.now().timestamp())
    sim_id = f"TESTE-{timestamp}"

    payload_simulado = {
        "id": sim_id,
        "transaction_amount": valor,
        "description": descricao,
        "tipo": tipo,
        "payment_method_id": metodo,
        "status": "approved",
        "date_approved": datetime.now().isoformat()
    }

    lancamento, sucesso, msg = processar_pagamento_mp(payload_simulado, usuario_id=usuario_id)
    if sucesso:
        flash(f"Simulação concluída! {msg}", "success")
    else:
        flash(f"Aviso na simulação: {msg}", "warning")

    return redirect(url_for("integracoes.mercadopago_painel"))


# =========================================================
# ENDPOINT DO WEBHOOK OFICIAL MERCADO PAGO
# =========================================================

@integracoes_bp.route("/webhooks/mercadopago", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhooks/mercadopago/", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhooks/mercadopago/<token>", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhook/mercadopago", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhook/mercadopago/", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhook/mercadopago/<token>", methods=["GET", "POST", "OPTIONS"])
def webhook_mercadopago(token=None):
    """
    Endpoint chamado pelos servidores do Mercado Pago em tempo real.
    Exige obrigatoriamente um webhook_token válido do usuário para evitar injeção não autorizada.
    """
    from services.audit_service import registrar_auditoria

    if request.method in ("GET", "OPTIONS"):
        return jsonify({
            "status": "online",
            "service": "Controle Financeiro - Webhook Mercado Pago",
            "timestamp": datetime.now().isoformat()
        }), 200

    # Validação estrita de autorização por token
    if not token:
        registrar_auditoria("webhook.mercadopago_unauthorized", status="falha", detalhes={"motivo": "Token ausente"})
        return jsonify({
            "status": "error",
            "message": "Token de autenticação de webhook obrigatório."
        }), 401

    usuario = Usuario.query.filter_by(webhook_token=token).first()
    if not usuario:
        registrar_auditoria("webhook.mercadopago_forbidden", status="falha", detalhes={"motivo": "Token inválido", "token": token[:6] + "..."})
        return jsonify({
            "status": "error",
            "message": "Token de webhook inválido ou usuário inexistente."
        }), 403

    usuario_id = usuario.id
    dados = request.get_json(silent=True) or {}

    # Extrai o payment_id do payload JSON ou dos parâmetros de URL
    payment_id = None
    if isinstance(dados.get("data"), dict) and "id" in dados["data"]:
        payment_id = str(dados["data"]["id"])
        transactions = dados["data"].get("transactions")
        if isinstance(transactions, dict) and "payments" in transactions and isinstance(transactions["payments"], list) and len(transactions["payments"]) > 0:
            first_pay = transactions["payments"][0]
            if isinstance(first_pay, dict) and "id" in first_pay:
                payment_id = str(first_pay["id"])
    elif "id" in dados:
        payment_id = str(dados["id"])
    elif request.args.get("data.id"):
        payment_id = str(request.args.get("data.id"))
    elif request.args.get("id"):
        payment_id = str(request.args.get("id"))

    token_api = Config.MERCADO_PAGO_ACCESS_TOKEN or obter_token_mercadopago()
    if payment_id and token_api:
        detalhes = consultar_pagamento_mp(payment_id, token_api)
        if detalhes:
            lancamento, criado, msg = processar_pagamento_mp(detalhes, usuario_id=usuario_id)
            if criado:
                registrar_auditoria("webhook.mercadopago_processado", usuario_id=usuario_id, detalhes={"payment_id": payment_id})
            return jsonify({
                "status": "success" if criado else "ignored",
                "payment_id": payment_id,
                "message": msg
            }), 200

    # Responde 200 para eventos não processáveis (ex: merchant_order, status pendente)
    return jsonify({
        "status": "received",
        "payment_id": payment_id,
        "message": "Notificação recebida e processada."
    }), 200


# =========================================================
# PAINEL NUBANK & APPLE PAY
# =========================================================

@integracoes_bp.route("/integracoes/nubank", methods=["GET"])
def nubank_painel():
    usuario_id = session.get("usuario_id")
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    token_webhook = usuario.webhook_token if usuario and usuario.webhook_token else ""

    host = request.host_url.rstrip("/")
    if token_webhook:
        webhook_url = f"{host}/webhooks/nubank/{token_webhook}"
    else:
        webhook_url = f"{host}{url_for('integracoes.webhook_nubank')}"

    cartao_nu = Cartao.query.filter(Cartao.usuario_id == usuario_id, Cartao.nome.ilike("%Nubank%")).first()
    conta_nu = Conta.query.filter(
        Conta.usuario_id == usuario_id,
        (Conta.nome.ilike("%Nubank%") | Conta.nome.ilike("%NuConta%"))
    ).first()

    # Todos os cartões e contas ativas do usuário para seleção no formulário
    cartoes = Cartao.query.filter_by(usuario_id=usuario_id, ativo=True).order_by(Cartao.nome).all()
    contas = Conta.query.filter_by(usuario_id=usuario_id, ativa=True).order_by(Conta.nome).all()

    # Gera opções de meses para vincular à fatura
    from datetime import date
    meses_nomes = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    hoje = date.today()
    meses_fatura = []
    for offset in range(-5, 3):
        m = hoje.month + offset
        a = hoje.year + ((m - 1) // 12)
        m = ((m - 1) % 12) + 1
        valor_mes = f"{a:04d}-{m:02d}"
        rotulo_mes = f"{meses_nomes[m]} / {a}"
        meses_fatura.append({
            "valor": valor_mes,
            "rotulo": rotulo_mes,
            "atual": (a == hoje.year and m == hoje.month)
        })
    meses_fatura.reverse()

    # Últimas compras no cartão Nubank (ou no primeiro cartão ativo) deste usuário
    cartao_ref = cartao_nu or (cartoes[0] if cartoes else None)
    ultimas_compras = []
    if cartao_ref:
        ultimas_compras = (
            CompraCartao.query
            .filter_by(cartao_id=cartao_ref.id, usuario_id=usuario_id)
            .order_by(CompraCartao.data_compra.desc(), CompraCartao.id.desc())
            .limit(10)
            .all()
        )

    # Últimos lançamentos na NuConta deste usuário
    ultimos_lancamentos_conta = []
    if conta_nu:
        ultimos_lancamentos_conta = (
            Lancamento.query
            .filter_by(conta_id=conta_nu.id, usuario_id=usuario_id)
            .order_by(Lancamento.data.desc(), Lancamento.id.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "integracao_nubank.html",
        webhook_url=webhook_url,
        cartao_nu=cartao_nu,
        conta_nu=conta_nu,
        cartoes=cartoes,
        contas=contas,
        meses_fatura=meses_fatura,
        ultimas_compras=ultimas_compras,
        ultimos_lancamentos_conta=ultimos_lancamentos_conta
    )


# =========================================================
# WEBHOOK APPLE PAY / IOS SHORTCUTS
# =========================================================

@integracoes_bp.route("/webhooks/nubank", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhooks/nubank/", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhooks/nubank/<token>", methods=["GET", "POST", "OPTIONS"])
def webhook_nubank(token=None):
    """
    Endpoint chamado pelo app Atalhos (Shortcuts) do iPhone via Apple Pay.
    Exige token específico do usuário na URL (/webhooks/nubank/<token>).
    """
    from services.audit_service import registrar_auditoria

    if request.method in ("GET", "OPTIONS"):
        return jsonify({
            "status": "online",
            "service": "Controle Financeiro - Webhook Nubank / Apple Pay (iOS)",
            "timestamp": datetime.now().isoformat()
        }), 200

    if not token:
        registrar_auditoria("webhook.nubank_unauthorized", status="falha", detalhes={"motivo": "Token ausente"})
        return jsonify({
            "status": "error",
            "message": "Token de webhook obrigatório."
        }), 401

    usuario = Usuario.query.filter_by(webhook_token=token).first()
    if not usuario:
        registrar_auditoria("webhook.nubank_forbidden", status="falha", detalhes={"motivo": "Token inválido"})
        return jsonify({
            "status": "error",
            "message": "Token de webhook não encontrado."
        }), 403

    usuario_id = usuario.id
    dados = request.get_json(silent=True) or request.form.to_dict() or {}
    compra, criado, msg = processar_transacao_apple_pay(dados, usuario_id=usuario_id)

    if criado:
        registrar_auditoria("webhook.nubank_processado", usuario_id=usuario_id, detalhes={"compra_id": compra.id if compra else None})

    return jsonify({
        "status": "success" if criado else "ignored",
        "message": msg,
        "compra_id": compra.id if compra else None
    }), 200


# =========================================================
# SIMULADOR APPLE PAY (IOS)
# =========================================================

@integracoes_bp.route("/integracoes/nubank/simular-ios", methods=["POST"])
def nubank_simular_ios():
    usuario_id = session.get("usuario_id")
    estabelecimento = (request.form.get("estabelecimento") or request.form.get("comerciante") or "Padaria Central").strip()
    valor_raw = request.form.get("valor", "15.90").replace(",", ".").strip()
    categoria = request.form.get("categoria", "Alimentação").strip()

    try:
        valor = float(valor_raw)
    except ValueError:
        flash("Valor inválido para simulação.", "danger")
        return redirect(url_for("integracoes.nubank_painel"))

    payload = {
        "estabelecimento": estabelecimento,
        "valor": valor,
        "categoria": categoria,
        "data": datetime.now().isoformat(),
        "transacao_id": f"IOS-{int(datetime.now().timestamp())}"
    }

    compra, criado, msg = processar_transacao_apple_pay(payload, usuario_id=usuario_id)
    if criado:
        flash(f"Sucesso! {msg}", "success")
    else:
        flash(f"Aviso: {msg}", "warning")

    return redirect(url_for("integracoes.nubank_painel"))


# =========================================================
# IMPORTADOR DE ARQUIVO NUBANK (CSV / OFX)
# =========================================================

@integracoes_bp.route("/integracoes/nubank/importar", methods=["POST"])
def nubank_importar_arquivo():
    usuario_id = session.get("usuario_id")
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo CSV ou OFX para importar.", "danger")
        return redirect(url_for("integracoes.nubank_painel"))

    nome_arquivo = arquivo.filename.lower()
    conteudo = arquivo.read().decode("utf-8", errors="ignore")

    transacoes = []
    tipo_detectado = "cartao"

    if nome_arquivo.endswith(".csv"):
        tipo_detectado, transacoes = parsear_csv_nubank(conteudo)
    elif nome_arquivo.endswith(".ofx"):
        tipo_detectado, transacoes = parsear_ofx_nubank(conteudo)
    else:
        flash("Formato não suportado. Por favor envie um arquivo com extensão .csv ou .ofx.", "danger")
        return redirect(url_for("integracoes.nubank_painel"))

    if not transacoes:
        flash("Nenhuma transação válida foi encontrada no arquivo enviado.", "warning")
        return redirect(url_for("integracoes.nubank_painel"))

    destino = request.form.get("destino", tipo_detectado)
    cartao_id = request.form.get("cartao_id")
    conta_id = request.form.get("conta_id")
    fatura_mes_ano = request.form.get("fatura_mes_ano")

    resultado = importar_lote_nubank(
        transacoes,
        destino=destino,
        usuario_id=usuario_id,
        cartao_id=cartao_id,
        conta_id=conta_id,
        fatura_mes_ano=fatura_mes_ano
    )

    dest_nome = resultado.get("destino_nome", "Cartão")
    flash(
        f"Importação em '{dest_nome}' concluída com sucesso! {resultado['importados']} transação(ões) adicionada(s) ({resultado['duplicados']} já existentes foram ignoradas).",
        "success"
    )
    return redirect(url_for("integracoes.nubank_painel"))
