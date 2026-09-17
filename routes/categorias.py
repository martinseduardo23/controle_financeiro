from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
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
    usuario_id = session.get("usuario_id")
    categorias = Categoria.query.filter_by(usuario_id=usuario_id).order_by(
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
    usuario_id = session.get("usuario_id")
    erro = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()

        existente = Categoria.query.filter_by(
            nome=nome,
            tipo=tipo,
            usuario_id=usuario_id
        ).first()

        if not nome:
            erro = "Informe o nome da categoria."
        elif tipo not in ("receita", "despesa"):
            erro = "Selecione um tipo válido."
        elif existente:
            erro = "Já existe uma categoria com esse nome e tipo."
        else:
            categoria = Categoria(
                nome=nome,
                tipo=tipo,
                ativa=True,
                usuario_id=usuario_id
            )

            db.session.add(categoria)
            db.session.commit()
            flash("Categoria criada com sucesso!", "success")

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
    usuario_id = session.get("usuario_id")
    categoria = db.session.get(Categoria, id)
    if not categoria or categoria.usuario_id != usuario_id:
        flash("Categoria não encontrada.", "danger")
        return redirect(url_for("categorias.listar"))

    erro = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        tipo = request.form.get("tipo", "").strip()

        existente = Categoria.query.filter(
            Categoria.id != categoria.id,
            Categoria.nome == nome,
            Categoria.tipo == tipo,
            Categoria.usuario_id == usuario_id
        ).first()

        if not nome:
            erro = "Informe o nome da categoria."
        elif tipo not in ("receita", "despesa"):
            erro = "Selecione um tipo válido."
        elif existente:
            erro = "Já existe outra categoria com esse nome e tipo."
        else:
            categoria.nome = nome
            categoria.tipo = tipo

            db.session.commit()
            flash("Categoria atualizada com sucesso!", "success")

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
    usuario_id = session.get("usuario_id")
    categoria = db.session.get(Categoria, id)
    if not categoria or categoria.usuario_id != usuario_id:
        flash("Categoria não encontrada.", "danger")
        return redirect(url_for("categorias.listar"))

    categoria.ativa = not categoria.ativa
    db.session.commit()
    novo_status = "ativada" if categoria.ativa else "desativada"
    flash(f"Categoria '{categoria.nome}' foi {novo_status}.", "info")

    return redirect(
        url_for("categorias.listar")
    )


@categorias_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):
    usuario_id = session.get("usuario_id")
    categoria = db.session.get(Categoria, id)
    if not categoria or categoria.usuario_id != usuario_id:
        flash("Categoria não encontrada.", "danger")
        return redirect(url_for("categorias.listar"))

    if categoria.lancamentos:
        flash("Não é possível excluir esta categoria pois existem lançamentos vinculados a ela.", "warning")
        return redirect(
            url_for("categorias.listar")
        )

    db.session.delete(categoria)
    db.session.commit()
    flash(f"Categoria '{categoria.nome}' excluída com sucesso!", "success")

    return redirect(
        url_for("categorias.listar")
    )
