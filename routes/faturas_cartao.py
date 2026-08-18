from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
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

    cartoes = (
        Cartao.query
        .filter_by(
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

    cartao = Cartao.query.get_or_404(
        cartao_id
    )

    faturas = (
        FaturaCartao.query
        .filter_by(
            cartao_id=cartao.id
        )
        .order_by(
            FaturaCartao.ano_referencia.asc(),
            FaturaCartao.mes_referencia.asc()
        )
        .all()
    )

    total_aberto = sum(
        (
            fatura.valor_total or 0
            for fatura in faturas
            if fatura.status != "paga"
        ),
        0
    )

    total_pago = sum(
        (
            fatura.valor_total or 0
            for fatura in faturas
            if fatura.status == "paga"
        ),
        0
    )

    return render_template(
        "faturas_cartao.html",
        cartoes=None,
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

    fatura = FaturaCartao.query.get_or_404(
        id
    )

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

    fatura = FaturaCartao.query.get_or_404(
        id
    )


    # -----------------------------------------------------
    # IMPede pagamento duplicado
    # -----------------------------------------------------

    if fatura.status == "paga":

        return redirect(
            url_for(
                "faturas_cartao.detalhes",
                id=fatura.id
            )
        )


    # -----------------------------------------------------
    # CONTA ESCOLHIDA
    # -----------------------------------------------------

    conta_id = request.form.get(
        "conta_id"
    )


    try:

        conta_id = int(
            conta_id
        )

    except (
        TypeError,
        ValueError
    ):

        conta_id = 0


    conta = (
        Conta.query
        .filter_by(
            id=conta_id,
            ativa=True
        )
        .first()
    )


    if not conta:

        return redirect(
            url_for(
                "faturas_cartao.detalhes",
                id=fatura.id
            )
        )


    # -----------------------------------------------------
    # CATEGORIA DO PAGAMENTO DE CARTÃO
    # -----------------------------------------------------

    categoria = Categoria.query.filter_by(
        nome="Pagamento de cartão",
        tipo="despesa"
    ).first()


    if not categoria:

        categoria = Categoria(
            nome="Pagamento de cartão",
            tipo="despesa",
            ativa=True
        )

        db.session.add(
            categoria
        )

        db.session.flush()


    # -----------------------------------------------------
    # DATA DO PAGAMENTO
    # -----------------------------------------------------

    agora = datetime.now()

    data_pagamento = agora.date()


    # -----------------------------------------------------
    # DESCRIÇÃO
    # -----------------------------------------------------

    descricao = (
        f"Pagamento fatura "
        f"{fatura.cartao.nome} "
        f"{fatura.mes_referencia:02d}/"
        f"{fatura.ano_referencia}"
    )


    # -----------------------------------------------------
    # CRIA LANÇAMENTO
    # -----------------------------------------------------

    lancamento = Lancamento(

        descricao=descricao,

        valor=fatura.valor_total,

        tipo="despesa",

        data=data_pagamento,

        status="pago",

        conta_id=conta.id,

        categoria_id=categoria.id,

        observacao=(
            "Pagamento automático da "
            "fatura do cartão de crédito."
        )

    )

    db.session.add(
        lancamento
    )


    # -----------------------------------------------------
    # ATUALIZA FATURA
    # -----------------------------------------------------

    fatura.status = "paga"

    fatura.data_pagamento = agora


    # -----------------------------------------------------
    # MARCA PARCELAS COMO PAGAS
    # -----------------------------------------------------

    for parcela in fatura.parcelas:

        parcela.pago = True

        parcela.status = "paga"

        parcela.data_pagamento = agora


    # -----------------------------------------------------
    # SALVA TUDO
    # -----------------------------------------------------

    db.session.commit()


    return redirect(
        url_for(
            "faturas_cartao.detalhes",
            id=fatura.id
        )
    )