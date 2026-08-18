from datetime import datetime, date
from decimal import Decimal
import calendar

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
    Categoria,
    ParcelaCartao
)

from services.faturas_cartao import (
    vincular_parcelas_compra
)


compras_cartao_bp = Blueprint(
    "compras_cartao",
    __name__,
    url_prefix="/compras-cartao"
)


# =========================================================
# CONVERSÃO DE MOEDA
# =========================================================

def moeda_brasileira_para_decimal(valor):

    valor = (valor or "").strip()

    valor = valor.replace(
        "R$",
        ""
    )

    valor = valor.replace(
        " ",
        ""
    )

    if not valor:
        return "0"

    return (
        valor
        .replace(".", "")
        .replace(",", ".")
    )


# =========================================================
# ADICIONAR MESES A UMA DATA
# =========================================================

def adicionar_meses(data_base, meses):

    mes = data_base.month - 1 + meses

    ano = (
        data_base.year +
        mes // 12
    )

    mes = (
        mes % 12
    ) + 1

    ultimo_dia = calendar.monthrange(
        ano,
        mes
    )[1]

    dia = min(
        data_base.day,
        ultimo_dia
    )

    return date(
        ano,
        mes,
        dia
    )


# =========================================================
# CRIAR PARCELAS DA COMPRA
# =========================================================

def criar_parcelas(compra):

    total = Decimal(
        str(
            compra.valor_total
        )
    )

    quantidade = int(
        compra.parcelas
    )

    if quantidade <= 0:
        quantidade = 1

    valor_base = (
        total /
        Decimal(quantidade)
    )

    valor_base = valor_base.quantize(
        Decimal("0.01")
    )

    valor_acumulado = Decimal("0")

    for numero in range(
        1,
        quantidade + 1
    ):

        if numero == quantidade:

            valor_parcela = (
                total -
                valor_acumulado
            )

        else:

            valor_parcela = valor_base

        valor_parcela = valor_parcela.quantize(
            Decimal("0.01")
        )

        data_prevista = adicionar_meses(
            compra.data_compra,
            numero - 1
        )

        parcela = ParcelaCartao(

            compra_id=compra.id,

            numero=numero,

            total_parcelas=quantidade,

            valor=valor_parcela,

            data_prevista=data_prevista,

            status="aberta",

            pago=False

        )

        db.session.add(
            parcela
        )

        valor_acumulado += (
            valor_parcela
        )


# =========================================================
# LISTAGEM DE COMPRAS
# =========================================================

@compras_cartao_bp.route("/")
def listar():

    compras = CompraCartao.query.order_by(
        CompraCartao.data_compra.desc(),
        CompraCartao.id.desc()
    ).all()

    categorias_totais = {}

    for compra in compras:

        categoria_nome = (
            compra.categoria.nome
        )

        valor = Decimal(
            str(
                compra.valor_total or 0
            )
        )

        if categoria_nome not in categorias_totais:

            categorias_totais[
                categoria_nome
            ] = Decimal("0")

        categorias_totais[
            categoria_nome
        ] += valor

    categorias_grafico = sorted(
        categorias_totais.items(),
        key=lambda item: item[1],
        reverse=True
    )

    total_geral = sum(
        categorias_totais.values(),
        Decimal("0")
    )

    maior_categoria = None

    if categorias_grafico:

        nome, valor = (
            categorias_grafico[0]
        )

        maior_categoria = {

            "nome": nome,

            "valor": valor

        }

    categorias_grafico_formatadas = []

    for nome, valor in categorias_grafico:

        if total_geral > 0:

            percentual = (
                valor /
                total_geral *
                Decimal("100")
            )

        else:

            percentual = Decimal("0")

        categorias_grafico_formatadas.append({

            "nome": nome,

            "valor": valor,

            "percentual": float(
                percentual
            )

        })

    return render_template(

        "compras_cartao.html",

        compras=compras,

        total_geral=total_geral,

        maior_categoria=maior_categoria,

        categorias_grafico=(
            categorias_grafico_formatadas
        )

    )


# =========================================================
# DETALHES DA COMPRA
# =========================================================

@compras_cartao_bp.route(
    "/detalhes/<int:id>"
)
def detalhes(id):

    compra = CompraCartao.query.get_or_404(
        id
    )

    parcelas = sorted(
        compra.parcelas_relacionadas,
        key=lambda parcela:
            parcela.numero
    )

    return render_template(

        "compra_cartao_detalhes.html",

        compra=compra,

        parcelas=parcelas

    )


# =========================================================
# NOVA COMPRA
# =========================================================

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

            parcelas = int(
                parcelas
            )

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

            erro = (
                "Informe a descrição."
            )

        elif data_compra is None:

            erro = (
                "Informe uma data válida."
            )

        elif not cartao:

            erro = (
                "Selecione um cartão ativo."
            )

        elif not categoria:

            erro = (
                "Selecione uma categoria de despesa."
            )

        elif parcelas < 1:

            erro = (
                "O número de parcelas deve "
                "ser pelo menos 1."
            )

        else:

            valor = (
                moeda_brasileira_para_decimal(
                    valor_total
                )
            )

            try:

                valor_decimal = Decimal(
                    str(valor)
                )

            except (
                TypeError,
                ValueError
            ):

                valor_decimal = Decimal(
                    "0"
                )

            if valor_decimal <= 0:

                erro = (
                    "Informe um valor "
                    "maior que zero."
                )

            else:

                compra = CompraCartao(

                    descricao=descricao,

                    valor_total=valor_decimal,

                    data_compra=data_compra,

                    parcelas=parcelas,

                    cartao_id=cartao.id,

                    categoria_id=categoria.id,

                    observacao=observacao

                )

                db.session.add(
                    compra
                )

                db.session.flush()


                # =========================================
                # CRIA AS PARCELAS
                # =========================================

                criar_parcelas(
                    compra
                )

                db.session.flush()


                # =========================================
                # VINCULA AS PARCELAS ÀS FATURAS
                # =========================================

                vincular_parcelas_compra(
                    compra
                )


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


# =========================================================
# EDITAR COMPRA
# =========================================================

@compras_cartao_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    compra = CompraCartao.query.get_or_404(
        id
    )

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

            parcelas = int(
                parcelas
            )

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

            erro = (
                "Informe a descrição."
            )

        elif data_compra is None:

            erro = (
                "Informe uma data válida."
            )

        elif not cartao:

            erro = (
                "Selecione um cartão ativo."
            )

        elif not categoria:

            erro = (
                "Selecione uma categoria de despesa."
            )

        elif parcelas < 1:

            erro = (
                "O número de parcelas deve "
                "ser pelo menos 1."
            )

        else:

            valor = (
                moeda_brasileira_para_decimal(
                    valor_total
                )
            )

            try:

                valor_decimal = Decimal(
                    str(valor)
                )

            except (
                TypeError,
                ValueError
            ):

                valor_decimal = Decimal(
                    "0"
                )

            if valor_decimal <= 0:

                erro = (
                    "Informe um valor "
                    "maior que zero."
                )

            else:

                # =========================================
                # REMOVE PARCELAS ANTIGAS
                # =========================================

                for parcela in (
                    compra.parcelas_relacionadas
                ):

                    db.session.delete(
                        parcela
                    )

                db.session.flush()


                # =========================================
                # ATUALIZA A COMPRA
                # =========================================

                compra.descricao = (
                    descricao
                )

                compra.valor_total = (
                    valor_decimal
                )

                compra.data_compra = (
                    data_compra
                )

                compra.parcelas = (
                    parcelas
                )

                compra.cartao_id = (
                    cartao.id
                )

                compra.categoria_id = (
                    categoria.id
                )

                compra.observacao = (
                    observacao
                )

                db.session.flush()


                # =========================================
                # CRIA AS NOVAS PARCELAS
                # =========================================

                criar_parcelas(
                    compra
                )

                db.session.flush()


                # =========================================
                # VINCULA ÀS FATURAS
                # =========================================

                vincular_parcelas_compra(
                    compra
                )


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


# =========================================================
# EXCLUIR COMPRA
# =========================================================

@compras_cartao_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    compra = CompraCartao.query.get_or_404(
        id
    )

    db.session.delete(
        compra
    )

    db.session.commit()

    return redirect(
        url_for(
            "compras_cartao.listar"
        )
    )