from datetime import date
from decimal import Decimal

from flask import Blueprint, render_template

from models import (
    Conta,
    Lancamento,
    FaturaCartao
)


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


@dashboard_bp.route("/")
def dashboard():

    hoje = date.today()

    # =====================================================
    # CONTAS
    # =====================================================

    contas = (
        Conta.query
        .filter_by(
            ativa=True
        )
        .all()
    )


    # =====================================================
    # LANÇAMENTOS
    # =====================================================

    lancamentos = (
        Lancamento.query
        .all()
    )


    # =====================================================
    # FATURAS DE CARTÃO EM ABERTO
    # =====================================================

    faturas_abertas = (
        FaturaCartao.query
        .filter(
            FaturaCartao.status != "paga"
        )
        .all()
    )


    # =====================================================
    # SALDOS
    # =====================================================

    saldo_atual = 0.0

    saldo_projetado = 0.0


    # =====================================================
    # RESUMO MENSAL
    # =====================================================

    receitas_mes = 0.0

    despesas_mes = 0.0

    receitas_pendentes = 0.0

    despesas_pendentes = 0.0


    # =====================================================
    # CONTAS
    # =====================================================

    for conta in contas:

        saldo_atual += conta.saldo_atual()

        saldo_projetado += float(
            conta.saldo_inicial or 0
        )


    # =====================================================
    # LANÇAMENTOS
    # =====================================================

    for lancamento in lancamentos:

        valor = float(
            lancamento.valor or 0
        )


        if lancamento.tipo == "receita":

            fator = valor

        else:

            fator = -valor


        # -------------------------------------------------
        # SALDO PROJETADO
        # -------------------------------------------------

        saldo_projetado += fator


        # -------------------------------------------------
        # RESUMO DO MÊS
        # -------------------------------------------------

        if (
            lancamento.data.year == hoje.year
            and
            lancamento.data.month == hoje.month
        ):

            if lancamento.tipo == "receita":

                if lancamento.status == "pago":

                    receitas_mes += valor

                else:

                    receitas_pendentes += valor

            else:

                if lancamento.status == "pago":

                    despesas_mes += valor

                else:

                    despesas_pendentes += valor


    # =====================================================
    # RESULTADO DO MÊS
    # =====================================================

    resultado_mes = (
        receitas_mes -
        despesas_mes
    )


    # =====================================================
    # COMPROMETIDO NOS CARTÕES
    # =====================================================

    comprometido_cartoes = sum(

        (
            Decimal(
                str(
                    fatura.valor_total or 0
                )
            )

            for fatura in faturas_abertas

        ),

        Decimal("0.00")

    )


    comprometido_cartoes = float(
        comprometido_cartoes
    )


    # =====================================================
    # COMPROMETIMENTO POR CARTÃO
    # =====================================================

    cartoes_comprometidos = {}

    for fatura in faturas_abertas:

        if not fatura.cartao:
            continue


        cartao_nome = (
            fatura.cartao.nome
        )


        valor = Decimal(
            str(
                fatura.valor_total or 0
            )
        )


        if cartao_nome not in cartoes_comprometidos:

            cartoes_comprometidos[
                cartao_nome
            ] = Decimal("0.00")


        cartoes_comprometidos[
            cartao_nome
        ] += valor


    # -----------------------------------------------------
    # TRANSFORMA EM LISTA ORDENADA
    # -----------------------------------------------------

    cartoes_comprometidos_lista = []

    for nome, valor in sorted(
        cartoes_comprometidos.items(),
        key=lambda item: item[1],
        reverse=True
    ):

        cartoes_comprometidos_lista.append({

            "nome": nome,

            "valor": float(
                valor
            )

        })


    # =====================================================
    # DISPONÍVEL APÓS CARTÕES
    # =====================================================

    disponivel_apos_cartoes = (
        saldo_atual -
        comprometido_cartoes
    )


    # =====================================================
    # PRÓXIMOS LANÇAMENTOS
    # =====================================================

    proximos = (
        Lancamento.query
        .filter(
            Lancamento.status != "pago",
            Lancamento.data >= hoje
        )
        .order_by(
            Lancamento.data.asc(),
            Lancamento.id.asc()
        )
        .limit(8)
        .all()
    )


    # =====================================================
    # RENDER
    # =====================================================

    return render_template(

        "dashboard.html",

        saldo_atual=saldo_atual,

        saldo_projetado=saldo_projetado,

        receitas_mes=receitas_mes,

        despesas_mes=despesas_mes,

        resultado_mes=resultado_mes,

        receitas_pendentes=receitas_pendentes,

        despesas_pendentes=despesas_pendentes,

        proximos=proximos,

        hoje=hoje,

        comprometido_cartoes=(
            comprometido_cartoes
        ),

        disponivel_apos_cartoes=(
            disponivel_apos_cartoes
        ),

        cartoes_comprometidos=(
            cartoes_comprometidos_lista
        )

    )