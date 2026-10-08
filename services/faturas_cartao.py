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


    # Se o dia de vencimento for MENOR que o dia de fechamento (ex: fecha dia 25, vence dia 5 do mês seguinte),
    # o vencimento ocorre no mês seguinte ao fechamento.
    # Se o dia de vencimento for MAIOR ou IGUAL (ex: fecha dia 1, vence dia 8; fecha dia 20, vence dia 27),
    # o vencimento ocorre no MESMO mês do fechamento da fatura!
    if cartao.dia_vencimento < cartao.dia_fechamento:
        if mes == 12:
            ano_vencimento = ano + 1
            mes_vencimento = 1
        else:
            ano_vencimento = ano
            mes_vencimento = mes + 1
    else:
        ano_vencimento = ano
        mes_vencimento = mes

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
# RECÁLCULO DO VALOR DA FATURA
# =========================================================

def recalcular_valor_fatura(fatura):
    """
    Garante que o valor_total da fatura seja exatamente igual à soma
    de suas parcelas vinculadas, evitando divergências por edição/exclusão.
    """
    total = sum(
        (Decimal(str(p.valor or 0)) for p in fatura.parcelas),
        Decimal("0.00")
    )
    fatura.valor_total = total.quantize(Decimal("0.01"))
    return fatura


# =========================================================
# VERIFICAÇÃO DE PARCELAS PAGAS
# =========================================================

def compra_tem_parcela_paga(compra):
    """
    Verifica se alguma parcela da compra já foi paga ou pertence a uma fatura quitada.
    """
    for parcela in compra.parcelas_relacionadas:
        if parcela.pago or parcela.status == "paga":
            return True
        if parcela.fatura and parcela.fatura.status == "paga":
            return True
    return False


def obter_faturas_da_compra(compra):
    """
    Retorna uma lista de faturas associadas às parcelas da compra.
    """
    faturas = set()
    for parcela in compra.parcelas_relacionadas:
        if parcela.fatura:
            faturas.add(parcela.fatura)
    return list(faturas)


# =========================================================
# VINCULA UMA PARCELA À FATURA
# =========================================================

def vincular_parcela(
    parcela,
    cartao,
    ano_fixo=None,
    mes_fixo=None
):
    if ano_fixo and mes_fixo:
        ano, mes = ano_fixo, mes_fixo
    else:
        ano, mes = periodo_fatura(
            parcela.data_prevista,
            cartao.dia_fechamento
        )

    fatura = obter_fatura(
        cartao,
        ano,
        mes
    )

    parcela.fatura = fatura
    parcela.fatura_id = fatura.id
    recalcular_valor_fatura(fatura)

    return fatura


# =========================================================
# VINCULA TODAS AS PARCELAS DE UMA COMPRA
# =========================================================

def vincular_parcelas_compra(
    compra,
    ano_fixo=None,
    mes_fixo=None
):
    cartao = compra.cartao
    faturas_afetadas = set()

    for idx, parcela in enumerate(compra.parcelas_relacionadas):
        # Se for especificado mês/ano fixo, a 1ª parcela vai nele e subsequentes avançam
        if ano_fixo and mes_fixo:
            m = mes_fixo + idx
            a = ano_fixo + ((m - 1) // 12)
            m = ((m - 1) % 12) + 1
            fatura = vincular_parcela(
                parcela,
                cartao,
                ano_fixo=a,
                mes_fixo=m
            )
        else:
            fatura = vincular_parcela(
                parcela,
                cartao
            )
        faturas_afetadas.add(fatura)

    for fatura in faturas_afetadas:
        recalcular_valor_fatura(fatura)

    db.session.flush()