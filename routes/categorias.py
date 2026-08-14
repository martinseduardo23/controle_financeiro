from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from database import db
from models import Categoria


categorias_bp = Blueprint(
    "categorias",
    __name__,
    url_prefix="/categorias"
)


@categorias_bp.route("/")
def listar():

    categorias = Categoria.query.order_by(
        Categoria.tipo,
        Categoria.nome
    ).all()

    return render_template(
        "categorias.html",
        categorias=categorias
    )


@categorias_bp.route(
    "/nova",
    methods=["GET", "POST"]
)
def nova():

    erro = None

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        tipo = request.form.get(
            "tipo",
            ""
        ).strip()

        existente = Categoria.query.filter_by(
            nome=nome,
            tipo=tipo
        ).first()

        if not nome:
            erro = "Informe o nome da categoria."

        elif tipo not in (
            "receita",
            "despesa"
        ):
            erro = "Selecione um tipo válido."

        elif existente:
            erro = "Já existe uma categoria com esse nome e tipo."

        else:

            categoria = Categoria(
                nome=nome,
                tipo=tipo,
                ativa=True
            )

            db.session.add(categoria)
            db.session.commit()

            return redirect(
                url_for("categorias.listar")
            )

    return render_template(
        "categoria_form.html",
        categoria=None,
        erro=erro
    )


@categorias_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    categoria = Categoria.query.get_or_404(id)

    erro = None

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        tipo = request.form.get(
            "tipo",
            ""
        ).strip()

        existente = Categoria.query.filter(
            Categoria.id != categoria.id,
            Categoria.nome == nome,
            Categoria.tipo == tipo
        ).first()

        if not nome:
            erro = "Informe o nome da categoria."

        elif tipo not in (
            "receita",
            "despesa"
        ):
            erro = "Selecione um tipo válido."

        elif existente:
            erro = "Já existe outra categoria com esse nome e tipo."

        else:

            categoria.nome = nome
            categoria.tipo = tipo

            db.session.commit()

            return redirect(
                url_for("categorias.listar")
            )

    return render_template(
        "categoria_form.html",
        categoria=categoria,
        erro=erro
    )


@categorias_bp.route(
    "/alternar/<int:id>",
    methods=["POST"]
)
def alternar(id):

    categoria = Categoria.query.get_or_404(id)

    categoria.ativa = not categoria.ativa

    db.session.commit()

    return redirect(
        url_for("categorias.listar")
    )


@categorias_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    categoria = Categoria.query.get_or_404(id)

    if categoria.lancamentos:
        return redirect(
            url_for("categorias.listar")
        )

    db.session.delete(categoria)
    db.session.commit()

    return redirect(
        url_for("categorias.listar")
    )
