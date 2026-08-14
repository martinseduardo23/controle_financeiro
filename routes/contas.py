from flask import Blueprint, render_template, request, redirect, url_for

from database import db
from models import Conta


def moeda_brasileira_para_decimal(valor):
    valor = (valor or "").strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if not valor:
        return 0

    valor = valor.replace(".", "").replace(",", ".")

    return valor


contas_bp = Blueprint(
    "contas",
    __name__,
    url_prefix="/contas"
)


@contas_bp.route("/")
def listar():

    contas = Conta.query.order_by(
        Conta.nome
    ).all()

    saldo_total = sum(
        conta.saldo_atual()
        for conta in contas
        if conta.ativa
    )

    return render_template(
        "contas.html",
        contas=contas,
        saldo_total=saldo_total
    )


@contas_bp.route("/nova", methods=["GET", "POST"])
def nova():

    if request.method == "POST":

        nome = request.form.get("nome")
        tipo = request.form.get("tipo")
        saldo = request.form.get(
            "saldo_inicial",
            "0"
        )

        conta = Conta(
            nome=nome,
            tipo=tipo,
            saldo_inicial=moeda_brasileira_para_decimal(saldo)
        )

        db.session.add(conta)
        db.session.commit()

        return redirect(
            url_for("contas.listar")
        )

    return render_template(
        "conta_form.html"
    )


@contas_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    conta = Conta.query.get_or_404(id)

    if conta.lancamentos:
        return redirect(
            url_for("contas.listar")
        )

    db.session.delete(conta)
    db.session.commit()

    return redirect(
        url_for("contas.listar")
    )
