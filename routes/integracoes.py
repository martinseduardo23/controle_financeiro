import json
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from database import db
from models import Lancamento, Conta, CompraCartao, Cartao
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
    token_atual = Config.MERCADO_PAGO_ACCESS_TOKEN or obter_token_mercadopago()
    tem_token = bool(token_atual and len(token_atual) > 10)

    # URL pública recomendada para o webhook
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}{url_for('integracoes.webhook_mercadopago')}"

    # Últimas movimentações vindas do Mercado Pago
    ultimos_lancamentos = (
        Lancamento.query
        .filter(Lancamento.observacao.like("%[Mercado Pago ID:%"))
        .order_by(Lancamento.data.desc(), Lancamento.id.desc())
        .limit(10)
        .all()
    )

    conta_mp = Conta.query.filter_by(nome="Mercado Pago").first()

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
    token = request.form.get("access_token", "").strip()
    if not token:
        flash("Informe um Access Token válido.", "danger")
    else:
        salvar_token_mercadopago(token)
        # Garante que a conta bancária exista
        obter_ou_criar_conta_mp()
        flash("Access Token do Mercado Pago configurado com sucesso!", "success")

    return redirect(url_for("integracoes.mercadopago_painel"))


# =========================================================
# SIMULADOR DE TRANSAÇÕES
# =========================================================

@integracoes_bp.route("/integracoes/mercadopago/simular", methods=["POST"])
def mercadopago_simular():
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

    lancamento, sucesso, msg = processar_pagamento_mp(payload_simulado)
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
@integracoes_bp.route("/webhook/mercadopago", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhook/mercadopago/", methods=["GET", "POST", "OPTIONS"])
def webhook_mercadopago():
    """
    Endpoint chamado pelos servidores do Mercado Pago em tempo real.
    Sempre retorna HTTP 200 para confirmar recebimento.
    """
    if request.method in ("GET", "OPTIONS"):
        return jsonify({
            "status": "online",
            "service": "Controle Financeiro - Webhook Mercado Pago",
            "timestamp": datetime.now().isoformat()
        }), 200

    dados = request.get_json(silent=True) or {}

    # Extrai o payment_id do payload JSON ou dos parâmetros de URL
    payment_id = None
    if isinstance(dados.get("data"), dict) and "id" in dados["data"]:
        payment_id = str(dados["data"]["id"])
        # Verifica se dentro de data há transactions/payments
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

    # Verifica o tipo de evento
    topic = dados.get("type") or dados.get("topic") or request.args.get("topic") or request.args.get("type") or dados.get("action")

    # Se recebeu um ID de pagamento e temos o token configurado, consulta na API oficial
    token = Config.MERCADO_PAGO_ACCESS_TOKEN or obter_token_mercadopago()
    if payment_id and token:
        detalhes = consultar_pagamento_mp(payment_id, token)
        if detalhes:
            lancamento, criado, msg = processar_pagamento_mp(detalhes)
            return jsonify({
                "status": "success" if criado else "ignored",
                "payment_id": payment_id,
                "message": msg
            }), 200

    # Se não temos token mas recebemos um payload com dados diretos (ex: testes manuais)
    if payment_id and (dados.get("transaction_amount") or dados.get("valor")):
        lancamento, criado, msg = processar_pagamento_mp(dados)
        return jsonify({
            "status": "success" if criado else "ignored",
            "message": msg
        }), 200

    # Responde 200 para eventos não processáveis (ex: merchant_order, chargeback, etc.)
    return jsonify({
        "status": "received",
        "payment_id": payment_id,
        "message": "Notificação recebida com sucesso."
    }), 200


# =========================================================
# PAINEL NUBANK & APPLE PAY
# =========================================================

@integracoes_bp.route("/integracoes/nubank", methods=["GET"])
def nubank_painel():
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}{url_for('integracoes.webhook_nubank')}"

    cartao_nu = Cartao.query.filter(Cartao.nome.ilike("%Nubank%")).first()
    conta_nu = Conta.query.filter(Conta.nome.ilike("%Nubank%") | Conta.nome.ilike("%NuConta%")).first()

    # Últimas compras no cartão Nubank
    ultimas_compras = []
    if cartao_nu:
        ultimas_compras = (
            CompraCartao.query
            .filter_by(cartao_id=cartao_nu.id)
            .order_by(CompraCartao.data_compra.desc(), CompraCartao.id.desc())
            .limit(10)
            .all()
        )

    # Últimos lançamentos na NuConta
    ultimos_lancamentos_conta = []
    if conta_nu:
        ultimos_lancamentos_conta = (
            Lancamento.query
            .filter_by(conta_id=conta_nu.id)
            .order_by(Lancamento.data.desc(), Lancamento.id.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "integracao_nubank.html",
        webhook_url=webhook_url,
        cartao_nu=cartao_nu,
        conta_nu=conta_nu,
        ultimas_compras=ultimas_compras,
        ultimos_lancamentos_conta=ultimos_lancamentos_conta
    )


# =========================================================
# WEBHOOK APPLE PAY / IOS SHORTCUTS
# =========================================================

@integracoes_bp.route("/webhooks/nubank", methods=["GET", "POST", "OPTIONS"])
@integracoes_bp.route("/webhooks/nubank/", methods=["GET", "POST", "OPTIONS"])
def webhook_nubank():
    """
    Endpoint chamado pelo app Atalhos (Shortcuts) do iPhone via Apple Pay.
    Sempre responde HTTP 200 com JSON.
    """
    if request.method in ("GET", "OPTIONS"):
        return jsonify({
            "status": "online",
            "service": "Controle Financeiro - Webhook Nubank / Apple Pay (iOS)",
            "timestamp": datetime.now().isoformat()
        }), 200

    dados = request.get_json(silent=True) or request.form.to_dict() or {}
    compra, criado, msg = processar_transacao_apple_pay(dados)

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

    compra, criado, msg = processar_transacao_apple_pay(payload)
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
    resultado = importar_lote_nubank(transacoes, destino=destino)

    flash(
        f"Importação concluída com sucesso! {resultado['importados']} transações adicionadas ({resultado['duplicados']} já existentes foram ignoradas).",
        "success"
    )
    return redirect(url_for("integracoes.nubank_painel"))
