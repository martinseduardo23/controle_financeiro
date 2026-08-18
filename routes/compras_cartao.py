from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from database import db
from models import (
    CompraCartao,
    Cartao,
    Categoria
)


compras_cartao_bp = Blueprint(
    "compras_cartao",
    __name__,
    url_prefix="/compras-cartao"
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


@compras_cartao_bp.route("/")
def listar():

    compras = CompraCartao.query.order_by(
        CompraCartao.data_compra.desc(),
        CompraCartao.id.desc()
    ).all()

    return render_template(
        "compras_cartao.html",
        compras=compras
    )


@compras_cartao_bp.route(
    "/nova",
    methods=["GET", "POST"]
)
def nova():

    erro = None

    if request.method == "POST":

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        valor_total = request.form.get(
            "valor_total",
            "0"
        )

        data_compra = request.form.get(
            "data_compra"
        )

        cartao_id = request.form.get(
            "cartao_id"
        )

        categoria_id = request.form.get(
            "categoria_id"
        )

        parcelas = request.form.get(
            "parcelas",
            "1"
        )

        observacao = request.form.get(
            "observacao",
            ""
        ).strip()

        try:

            parcelas = int(parcelas)

        except (
            TypeError,
            ValueError
        ):

            parcelas = 0

        try:

            data_compra = datetime.strptime(
                data_compra,
                "%Y-%m-%d"
            ).date()

        except (
            TypeError,
            ValueError
        ):

            data_compra = None

        try:

            cartao_id_int = int(
                cartao_id
            )

        except (
            TypeError,
            ValueError
        ):

            cartao_id_int = 0

        try:

            categoria_id_int = int(
                categoria_id
            )

        except (
            TypeError,
            ValueError
        ):

            categoria_id_int = 0

        cartao = Cartao.query.filter_by(
            id=cartao_id_int,
            ativo=True
        ).first()

        categoria = Categoria.query.filter_by(
            id=categoria_id_int,
            tipo="despesa",
            ativa=True
        ).first()

        if not descricao:

            erro = "Informe a descrição."

        elif data_compra is None:

            erro = "Informe uma data válida."

        elif not cartao:

            erro = "Selecione um cartão ativo."

        elif not categoria:

            erro = "Selecione uma categoria de despesa."

        elif parcelas < 1:

            erro = (
                "O número de parcelas deve "
                "ser pelo menos 1."
            )

        else:

            valor = moeda_brasileira_para_decimal(
                valor_total
            )

            try:
                valor_float = float(valor)
            except (
                TypeError,
                ValueError
            ):
                valor_float = 0

            if valor_float <= 0:

                erro = "Informe um valor maior que zero."

            else:

                compra = CompraCartao(
                    descricao=descricao,
                    valor_total=valor,
                    data_compra=data_compra,
                    parcelas=parcelas,
                    cartao_id=cartao.id,
                    categoria_id=categoria.id,
                    observacao=observacao
                )

                db.session.add(compra)
                db.session.commit()

                return redirect(
                    url_for(
                        "compras_cartao.listar"
                    )
                )

    cartoes = Cartao.query.filter_by(
        ativo=True
    ).order_by(
        Cartao.nome
    ).all()

    categorias = Categoria.query.filter_by(
        tipo="despesa",
        ativa=True
    ).order_by(
        Categoria.nome
    ).all()

    return render_template(
        "compra_cartao_form.html",
        compra=None,
        cartoes=cartoes,
        categorias=categorias,
        erro=erro
    )


@compras_cartao_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    compra = CompraCartao.query.get_or_404(id)

    erro = None

    if request.method == "POST":

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        valor_total = request.form.get(
            "valor_total",
            "0"
        )

        data_compra = request.form.get(
            "data_compra"
        )

        cartao_id = request.form.get(
            "cartao_id"
        )

        categoria_id = request.form.get(
            "categoria_id"
        )

        parcelas = request.form.get(
            "parcelas",
            "1"
        )

        observacao = request.form.get(
            "observacao",
            ""
        ).strip()

        try:

            parcelas = int(parcelas)

        except (
            TypeError,
            ValueError
        ):

            parcelas = 0

        try:

            data_compra = datetime.strptime(
                data_compra,
                "%Y-%m-%d"
            ).date()

        except (
            TypeError,
            ValueError
        ):

            data_compra = None

        try:

            cartao_id_int = int(
                cartao_id
            )

        except (
            TypeError,
            ValueError
        ):

            cartao_id_int = 0

        try:

            categoria_id_int = int(
                categoria_id
            )

        except (
            TypeError,
            ValueError
        ):

            categoria_id_int = 0

        cartao = Cartao.query.filter_by(
            id=cartao_id_int,
            ativo=True
        ).first()

        categoria = Categoria.query.filter_by(
            id=categoria_id_int,
            tipo="despesa",
            ativa=True
        ).first()

        if not descricao:

            erro = "Informe a descrição."

        elif data_compra is None:

            erro = "Informe uma data válida."

        elif not cartao:

            erro = "Selecione um cartão ativo."

        elif not categoria:

            erro = "Selecione uma categoria de despesa."

        elif parcelas < 1:

            erro = (
                "O número de parcelas deve "
                "ser pelo menos 1."
            )

        else:

            valor = moeda_brasileira_para_decimal(
                valor_total
            )

            try:
                valor_float = float(valor)
            except (
                TypeError,
                ValueError
            ):
                valor_float = 0

            if valor_float <= 0:

                erro = "Informe um valor maior que zero."

            else:

                compra.descricao = descricao
                compra.valor_total = valor
                compra.data_compra = data_compra
                compra.parcelas = parcelas
                compra.cartao_id = cartao.id
                compra.categoria_id = categoria.id
                compra.observacao = observacao

                db.session.commit()

                return redirect(
                    url_for(
                        "compras_cartao.listar"
                    )
                )

    cartoes = Cartao.query.filter_by(
        ativo=True
    ).order_by(
        Cartao.nome
    ).all()

    categorias = Categoria.query.filter_by(
        tipo="despesa",
        ativa=True
    ).order_by(
        Categoria.nome
    ).all()

    return render_template(
        "compra_cartao_form.html",
        compra=compra,
        cartoes=cartoes,
        categorias=categorias,
        erro=erro
    )


@compras_cartao_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    compra = CompraCartao.query.get_or_404(id)

    db.session.delete(compra)

    db.session.commit()

    return redirect(
        url_for(
            "compras_cartao.listar"
        )
    )