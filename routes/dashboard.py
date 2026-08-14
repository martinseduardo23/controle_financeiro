from datetime import date

from flask import Blueprint, render_template

from models import Conta, Lancamento


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


@dashboard_bp.route("/")
def dashboard():

    hoje = date.today()

    contas = Conta.query.filter_by(
        ativa=True
    ).all()

    lancamentos = Lancamento.query.all()

    saldo_atual = 0.0
    saldo_projetado = 0.0

    receitas_mes = 0.0
    despesas_mes = 0.0

    receitas_pendentes = 0.0
    despesas_pendentes = 0.0

    for conta in contas:
        saldo_atual += conta.saldo_atual()

        saldo_projetado += float(
            conta.saldo_inicial or 0
        )

    for lancamento in lancamentos:

        valor = float(lancamento.valor or 0)

        if lancamento.tipo == "receita":
            fator = valor
        else:
            fator = -valor

        # Saldo projetado considera tudo que ainda
        # está previsto, além do que já foi pago.
        saldo_projetado += fator

        if (
            lancamento.data.year == hoje.year
            and lancamento.data.month == hoje.month
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

    resultado_mes = receitas_mes - despesas_mes

    proximos = Lancamento.query.filter(
        Lancamento.status != "pago",
        Lancamento.data >= hoje
    ).order_by(
        Lancamento.data.asc(),
        Lancamento.id.asc()
    ).limit(8).all()

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
        hoje=hoje
    )
