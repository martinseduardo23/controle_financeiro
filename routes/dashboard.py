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
    # CONTAS ATIVAS
    # =====================================================

    contas = (
        Conta.query
        .filter_by(
            ativa=True
        )
        .all()
    )

    # =====================================================
    # INTERVALO DO MÊS ATUAL
    # =====================================================

    inicio_mes = date(hoje.year, hoje.month, 1)
    if hoje.month == 12:
        fim_mes = date(hoje.year + 1, 1, 1)
    else:
        fim_mes = date(hoje.year, hoje.month + 1, 1)

    # Lançamentos apenas do mês atual via SQL
    lancamentos_mes = (
        Lancamento.query
        .filter(
            Lancamento.data >= inicio_mes,
            Lancamento.data < fim_mes
        )
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
    # SALDOS DAS CONTAS ATIVAS
    # =====================================================

    saldo_atual = sum(conta.saldo_atual() for conta in contas)

    # Saldo projetado considerando apenas contas ativas
    saldo_projetado = sum(float(c.saldo_inicial or 0) for c in contas)
    lancamentos_ativas = (
        Lancamento.query
        .join(Conta)
        .filter(Conta.ativa == True)
        .all()
    )

    for l in lancamentos_ativas:
        val = float(l.valor or 0)
        if l.tipo == "receita":
            saldo_projetado += val
        else:
            saldo_projetado -= val

    # =====================================================
    # RESUMO MENSAL
    # =====================================================

    receitas_mes = 0.0
    despesas_mes = 0.0
    receitas_pendentes = 0.0
    despesas_pendentes = 0.0

    for lancamento in lancamentos_mes:
        valor = float(lancamento.valor or 0)

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

    resultado_mes = receitas_mes - despesas_mes

    # =====================================================
    # COMPROMETIDO NOS CARTÕES
    # =====================================================

    comprometido_cartoes = sum(
        (Decimal(str(fatura.valor_total or 0)) for fatura in faturas_abertas),
        Decimal("0.00")
    )
    comprometido_cartoes = float(comprometido_cartoes)

    # =====================================================
    # COMPROMETIMENTO POR CARTÃO
    # =====================================================

    cartoes_comprometidos = {}

    for fatura in faturas_abertas:
        if not fatura.cartao:
            continue

        cartao_nome = fatura.cartao.nome
        valor = Decimal(str(fatura.valor_total or 0))

        if cartao_nome not in cartoes_comprometidos:
            cartoes_comprometidos[cartao_nome] = Decimal("0.00")

        cartoes_comprometidos[cartao_nome] += valor

    cartoes_comprometidos_lista = [
        {"nome": nome, "valor": float(valor)}
        for nome, valor in sorted(
            cartoes_comprometidos.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]

    disponivel_apos_cartoes = saldo_atual - comprometido_cartoes

    # =====================================================
    # LANÇAMENTOS EM ATRASO (PENDENTES ANTES DE HOJE)
    # =====================================================

    atrasados = (
        Lancamento.query
        .filter(
            Lancamento.status != "pago",
            Lancamento.data < hoje
        )
        .order_by(
            Lancamento.data.asc(),
            Lancamento.id.asc()
        )
        .all()
    )

    total_despesas_atrasadas = sum(
        float(l.valor or 0) for l in atrasados if l.tipo == "despesa"
    )

    # =====================================================
    # PRÓXIMOS LANÇAMENTOS (A PARTIR DE HOJE)
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
        atrasados=atrasados,
        total_despesas_atrasadas=total_despesas_atrasadas,
        hoje=hoje,
        comprometido_cartoes=comprometido_cartoes,
        disponivel_apos_cartoes=disponivel_apos_cartoes,
        cartoes_comprometidos=cartoes_comprometidos_lista
    )