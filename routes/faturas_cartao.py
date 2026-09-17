from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from database import db

from models import (
    FaturaCartao,
    Cartao,
    Conta,
    Categoria,
    Lancamento
)


faturas_cartao_bp = Blueprint(
    "faturas_cartao",
    __name__,
    url_prefix="/faturas-cartao"
)


# =========================================================
# ESCOLHER CARTÃO
# =========================================================

@faturas_cartao_bp.route("/")
def listar():
    usuario_id = session.get("usuario_id")
    cartoes = (
        Cartao.query
        .filter_by(
            usuario_id=usuario_id,
            ativo=True
        )
        .order_by(
            Cartao.nome
        )
        .all()
    )

    return render_template(
        "faturas_cartao.html",
        cartoes=cartoes
    )


# =========================================================
# FATURAS DE UM CARTÃO
# =========================================================

@faturas_cartao_bp.route(
    "/cartao/<int:cartao_id>"
)
def faturas_cartao(cartao_id):
    usuario_id = session.get("usuario_id")
    cartao = db.session.get(Cartao, cartao_id)
    if not cartao or cartao.usuario_id != usuario_id:
        flash("Cartão não encontrado.", "danger")
        return redirect(url_for("faturas_cartao.listar"))

    faturas = sorted(
        cartao.faturas,
        key=lambda fatura: (
            fatura.ano_referencia,
            fatura.mes_referencia
        ),
        reverse=True
    )

    total_aberto = sum(
        float(f.valor_total or 0)
        for f in faturas
        if f.status != "paga"
    )

    total_pago = sum(
        float(f.valor_total or 0)
        for f in faturas
        if f.status == "paga"
    )

    return render_template(
        "faturas_cartao_lista.html" if False else "faturas_cartao.html", # fallback
        cartao=cartao,
        faturas=faturas,
        total_aberto=total_aberto,
        total_pago=total_pago
    )


# =========================================================
# DETALHES DA FATURA
# =========================================================

@faturas_cartao_bp.route(
    "/fatura/<int:id>"
)
def detalhes(id):
    usuario_id = session.get("usuario_id")
    fatura = db.session.get(FaturaCartao, id)
    if not fatura or not fatura.cartao or fatura.cartao.usuario_id != usuario_id:
        flash("Fatura não encontrada.", "danger")
        return redirect(url_for("faturas_cartao.listar"))

    parcelas = sorted(
        fatura.parcelas,
        key=lambda parcela: (
            parcela.data_prevista,
            parcela.numero
        )
    )

    contas = (
        Conta.query
        .filter_by(
            usuario_id=usuario_id,
            ativa=True
        )
        .order_by(
            Conta.nome
        )
        .all()
    )

    return render_template(
        "fatura_cartao_detalhes.html",
        fatura=fatura,
        parcelas=parcelas,
        contas=contas
    )


# =========================================================
# PAGAR FATURA
# =========================================================

@faturas_cartao_bp.route(
    "/fatura/<int:id>/pagar",
    methods=["POST"]
)
def pagar(id):
    usuario_id = session.get("usuario_id")
    fatura = db.session.get(FaturaCartao, id)
    if not fatura or not fatura.cartao or fatura.cartao.usuario_id != usuario_id:
        flash("Fatura não encontrada.", "danger")
        return redirect(url_for("faturas_cartao.listar"))

    if fatura.status == "paga":
        return redirect(
            url_for(
                "faturas_cartao.detalhes",
                id=fatura.id
            )
        )

    conta_id = request.form.get("conta_id")

    try:
        conta_id = int(conta_id)
    except (TypeError, ValueError):
        conta_id = 0

    conta = (
        Conta.query
        .filter_by(
            id=conta_id,
            usuario_id=usuario_id,
            ativa=True
        )
        .first()
    )

    if not conta:
        flash("Selecione uma conta válida para o pagamento.", "warning")
        return redirect(
            url_for(
                "faturas_cartao.detalhes",
                id=fatura.id
            )
        )

    categoria = Categoria.query.filter_by(
        nome="Pagamento de cartão",
        tipo="despesa",
        usuario_id=usuario_id
    ).first()

    if not categoria:
        categoria = Categoria(
            nome="Pagamento de cartão",
            tipo="despesa",
            ativa=True,
            usuario_id=usuario_id
        )
        db.session.add(categoria)
        db.session.flush()

    agora = datetime.now()
    data_pagamento = agora.date()

    descricao = (
        f"Pagamento fatura "
        f"{fatura.cartao.nome} "
        f"{fatura.mes_referencia:02d}/"
        f"{fatura.ano_referencia}"
    )

    lancamento = Lancamento(
        descricao=descricao,
        valor=fatura.valor_total,
        tipo="despesa",
        data=data_pagamento,
        status="pago",
        conta_id=conta.id,
        categoria_id=categoria.id,
        observacao=f"Fatura {fatura.id} paga",
        usuario_id=usuario_id
    )

    db.session.add(lancamento)
    db.session.flush()

    fatura.status = "paga"
    fatura.data_pagamento = data_pagamento
    fatura.lancamento_id = lancamento.id

    for parcela in fatura.parcelas:
        parcela.status = "paga"
        parcela.pago = True

    db.session.commit()
    flash("Fatura paga com sucesso!", "success")

    return redirect(
        url_for(
            "faturas_cartao.detalhes",
            id=fatura.id
        )
    )