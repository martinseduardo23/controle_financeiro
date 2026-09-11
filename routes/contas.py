from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import db
from models import Conta, MetaAporte


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

    erro = None
    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()
        saldo = request.form.get(
            "saldo_inicial",
            "0"
        )

        if not nome:
            erro = "Informe o nome da conta."
        else:
            conta = Conta(
                nome=nome,
                tipo=tipo or "Conta corrente",
                saldo_inicial=moeda_brasileira_para_decimal(saldo),
                ativa=True
            )

            db.session.add(conta)
            db.session.commit()
            flash(f"Conta '{conta.nome}' criada com sucesso!", "success")

            return redirect(
                url_for("contas.listar")
            )

    return render_template(
        "conta_form.html",
        erro=erro
    )


@contas_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conta = Conta.query.get_or_404(id)
    erro = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()
        saldo = request.form.get("saldo_inicial", "0")
        ativa = request.form.get("ativa") == "on"

        if not nome:
            erro = "Informe o nome da conta."
        else:
            conta.nome = nome
            conta.tipo = tipo or "Conta"
            conta.saldo_inicial = moeda_brasileira_para_decimal(saldo)
            conta.ativa = ativa

            db.session.commit()
            flash(f"Conta '{conta.nome}' atualizada com sucesso!", "success")
            return redirect(url_for("contas.listar"))

    return render_template(
        "conta_editar.html",
        conta=conta,
        erro=erro
    )


@contas_bp.route("/alternar/<int:id>", methods=["POST"])
def alternar(id):
    conta = Conta.query.get_or_404(id)
    conta.ativa = not conta.ativa
    db.session.commit()

    status = "ativada" if conta.ativa else "desativada"
    flash(f"Conta '{conta.nome}' foi {status}.", "info")
    return redirect(url_for("contas.listar"))


@contas_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    conta = Conta.query.get_or_404(id)

    tem_aportes = MetaAporte.query.filter_by(conta_id=conta.id).first()
    if conta.lancamentos or tem_aportes:
        flash("Não é possível excluir esta conta pois existem movimentações ou aportes vinculados a ela. Você pode desativá-la.", "warning")
        return redirect(
            url_for("contas.listar")
        )

    db.session.delete(conta)
    db.session.commit()
    flash(f"Conta '{conta.nome}' excluída com sucesso!", "success")

    return redirect(
        url_for("contas.listar")
    )
