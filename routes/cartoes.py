from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from database import db
from models import Cartao, CompraCartao


cartoes_bp = Blueprint(
    "cartoes",
    __name__,
    url_prefix="/cartoes"
)


def moeda_brasileira_para_decimal(valor):
    valor = (valor or "").strip()

    valor = valor.replace(
        "R$",
        ""
    ).replace(
        " ",
        ""
    )

    if not valor:
        return 0

    return valor.replace(
        ".",
        ""
    ).replace(
        ",",
        "."
    )


@cartoes_bp.route("/")
def listar():

    cartoes = Cartao.query.order_by(
        Cartao.nome
    ).all()

    return render_template(
        "cartoes.html",
        cartoes=cartoes
    )


@cartoes_bp.route(
    "/novo",
    methods=["GET", "POST"]
)
def novo():

    erro = None

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        banco = request.form.get(
            "banco",
            ""
        ).strip()

        ultimos_digitos = request.form.get(
            "ultimos_digitos",
            ""
        ).strip()

        limite = request.form.get(
            "limite",
            "0"
        )

        dia_fechamento = request.form.get(
            "dia_fechamento"
        )

        dia_vencimento = request.form.get(
            "dia_vencimento"
        )

        try:

            dia_fechamento = int(
                dia_fechamento
            )

            dia_vencimento = int(
                dia_vencimento
            )

        except (
            TypeError,
            ValueError
        ):

            erro = (
                "Informe dias de fechamento "
                "e vencimento válidos."
            )

            return render_template(
                "cartao_form.html",
                cartao=None,
                erro=erro
            )

        if not nome:

            erro = "Informe o nome do cartão."

        elif not banco:

            erro = "Informe o banco ou instituição."

        elif not (
            1 <= dia_fechamento <= 31
        ):

            erro = (
                "O dia de fechamento deve "
                "estar entre 1 e 31."
            )

        elif not (
            1 <= dia_vencimento <= 31
        ):

            erro = (
                "O dia de vencimento deve "
                "estar entre 1 e 31."
            )

        elif (
            ultimos_digitos
            and (
                len(ultimos_digitos) != 4
                or not ultimos_digitos.isdigit()
            )
        ):

            erro = (
                "Os últimos dígitos devem "
                "conter 4 números."
            )

        else:

            cartao = Cartao(
                nome=nome,
                banco=banco,
                ultimos_digitos=(
                    ultimos_digitos
                    or None
                ),
                limite=(
                    moeda_brasileira_para_decimal(
                        limite
                    )
                ),
                dia_fechamento=dia_fechamento,
                dia_vencimento=dia_vencimento,
                ativo=True
            )

            db.session.add(cartao)
            db.session.commit()
            flash("Cartão cadastrado com sucesso!", "success")

            return redirect(
                url_for("cartoes.listar")
            )

    return render_template(
        "cartao_form.html",
        cartao=None,
        erro=erro
    )


@cartoes_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    cartao = Cartao.query.get_or_404(id)

    erro = None

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        banco = request.form.get(
            "banco",
            ""
        ).strip()

        ultimos_digitos = request.form.get(
            "ultimos_digitos",
            ""
        ).strip()

        limite = request.form.get(
            "limite",
            "0"
        )

        dia_fechamento = request.form.get(
            "dia_fechamento"
        )

        dia_vencimento = request.form.get(
            "dia_vencimento"
        )

        try:

            dia_fechamento = int(
                dia_fechamento
            )

            dia_vencimento = int(
                dia_vencimento
            )

        except (
            TypeError,
            ValueError
        ):

            erro = (
                "Informe dias de fechamento "
                "e vencimento válidos."
            )

            return render_template(
                "cartao_form.html",
                cartao=cartao,
                erro=erro
            )

        if not nome:

            erro = "Informe o nome do cartão."

        elif not banco:

            erro = "Informe o banco ou instituição."

        elif not (
            1 <= dia_fechamento <= 31
        ):

            erro = (
                "O dia de fechamento deve "
                "estar entre 1 e 31."
            )

        elif not (
            1 <= dia_vencimento <= 31
        ):

            erro = (
                "O dia de vencimento deve "
                "estar entre 1 e 31."
            )

        elif (
            ultimos_digitos
            and (
                len(ultimos_digitos) != 4
                or not ultimos_digitos.isdigit()
            )
        ):

            erro = (
                "Os últimos dígitos devem "
                "conter 4 números."
            )

        else:

            cartao.nome = nome
            cartao.banco = banco

            cartao.ultimos_digitos = (
                ultimos_digitos
                or None
            )

            cartao.limite = (
                moeda_brasileira_para_decimal(
                    limite
                )
            )

            cartao.dia_fechamento = (
                dia_fechamento
            )

            cartao.dia_vencimento = (
                dia_vencimento
            )

            db.session.commit()
            flash("Cartão atualizado com sucesso!", "success")

            return redirect(
                url_for("cartoes.listar")
            )

    return render_template(
        "cartao_form.html",
        cartao=cartao,
        erro=erro
    )


@cartoes_bp.route(
    "/alternar/<int:id>",
    methods=["POST"]
)
def alternar(id):

    cartao = Cartao.query.get_or_404(id)

    cartao.ativo = not cartao.ativo

    db.session.commit()
    novo_status = "ativado" if cartao.ativo else "desativado"
    flash(f"Cartão '{cartao.nome}' foi {novo_status}.", "info")

    return redirect(
        url_for("cartoes.listar")
    )


@cartoes_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    cartao = Cartao.query.get_or_404(id)

    compras_vinculadas = CompraCartao.query.filter_by(cartao_id=cartao.id).first()
    if compras_vinculadas or cartao.faturas:
        flash("Não é possível excluir o cartão pois existem compras ou faturas registradas. Você pode desativá-lo para não usá-lo mais.", "warning")
        return redirect(
            url_for("cartoes.listar")
        )

    db.session.delete(cartao)
    db.session.commit()
    flash(f"Cartão '{cartao.nome}' excluído com sucesso!", "success")

    return redirect(
        url_for("cartoes.listar")
    )