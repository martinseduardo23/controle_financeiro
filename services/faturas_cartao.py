from datetime import date
from decimal import Decimal
import calendar

from database import db

from models import (
    FaturaCartao,
    ParcelaCartao,
)


# =========================================================
# ÚLTIMO DIA DO MÊS
# =========================================================

def ultimo_dia_do_mes(ano, mes):

    return calendar.monthrange(
        ano,
        mes
    )[1]


# =========================================================
# CRIA UMA DATA USANDO DIA DO CARTÃO
# =========================================================

def criar_data_cartao(ano, mes, dia):

    dia = min(
        dia,
        ultimo_dia_do_mes(
            ano,
            mes
        )
    )

    return date(
        ano,
        mes,
        dia
    )


# =========================================================
# DETERMINA O PERÍODO DA FATURA
# =========================================================

def periodo_fatura(
    data_compra,
    dia_fechamento
):

    if data_compra.day <= dia_fechamento:

        mes = data_compra.month
        ano = data_compra.year

    else:

        if data_compra.month == 12:

            mes = 1
            ano = data_compra.year + 1

        else:

            mes = data_compra.month + 1
            ano = data_compra.year

    return ano, mes


# =========================================================
# BUSCA OU CRIA UMA FATURA
# =========================================================

def obter_fatura(
    cartao,
    ano,
    mes
):

    fatura = FaturaCartao.query.filter_by(

        cartao_id=cartao.id,

        ano_referencia=ano,

        mes_referencia=mes

    ).first()


    if fatura:

        return fatura


    data_fechamento = criar_data_cartao(
        ano,
        mes,
        cartao.dia_fechamento
    )


    if mes == 12:

        ano_vencimento = ano + 1
        mes_vencimento = 1

    else:

        ano_vencimento = ano
        mes_vencimento = mes + 1


    data_vencimento = criar_data_cartao(

        ano_vencimento,

        mes_vencimento,

        cartao.dia_vencimento

    )


    fatura = FaturaCartao(

        cartao_id=cartao.id,

        mes_referencia=mes,

        ano_referencia=ano,

        data_fechamento=data_fechamento,

        data_vencimento=data_vencimento,

        valor_total=Decimal("0.00"),

        status="aberta"

    )


    db.session.add(
        fatura
    )


    db.session.flush()


    return fatura


# =========================================================
# VINCULA UMA PARCELA À FATURA
# =========================================================

def vincular_parcela(
    parcela,
    cartao
):

    ano, mes = periodo_fatura(

        parcela.data_prevista,

        cartao.dia_fechamento

    )


    fatura = obter_fatura(

        cartao,

        ano,

        mes

    )


    parcela.fatura_id = fatura.id


    fatura.valor_total = (

        Decimal(
            str(
                fatura.valor_total or 0
            )
        )

        +

        Decimal(
            str(
                parcela.valor or 0
            )
        )

    )


    return fatura


# =========================================================
# VINCULA TODAS AS PARCELAS DE UMA COMPRA
# =========================================================

def vincular_parcelas_compra(
    compra
):

    cartao = compra.cartao


    for parcela in (
        compra.parcelas_relacionadas
    ):

        vincular_parcela(
            parcela,
            cartao
        )


    db.session.flush()