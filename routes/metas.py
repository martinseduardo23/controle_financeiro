from datetime import datetime
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from database import db

from models import (
    Meta,
    MetaAporte,
    Conta,
    Categoria,
    Lancamento
)


metas_bp = Blueprint(
    "metas",
    __name__,
    url_prefix="/metas"
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
# LISTAGEM
# =========================================================

@metas_bp.route("/")
def listar():

    metas = (
        Meta.query
        .filter_by(
            ativa=True
        )
        .order_by(
            Meta.prazo.asc(),
            Meta.id.desc()
        )
        .all()
    )

    return render_template(
        "metas.html",
        metas=metas
    )


# =========================================================
# NOVA META
# =========================================================

@metas_bp.route(
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

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        valor_meta = request.form.get(
            "valor_meta",
            "0"
        )

        valor_atual = request.form.get(
            "valor_atual",
            "0"
        )

        rendimento_diario = request.form.get(
            "rendimento_diario",
            "5,68"
        )

        data_inicio = request.form.get(
            "data_inicio_rendimento",
            ""
        )

        prazo = request.form.get(
            "prazo",
            ""
        )

        # -------------------------------------------------
        # NOME
        # -------------------------------------------------

        if not nome:

            erro = "Informe o nome da meta."

        # -------------------------------------------------
        # VALORES
        # -------------------------------------------------

        try:

            valor_meta_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    valor_meta
                )
            )

        except (
            TypeError,
            ValueError
        ):

            valor_meta_decimal = Decimal("0")


        try:

            valor_atual_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    valor_atual
                )
            )

        except (
            TypeError,
            ValueError
        ):

            valor_atual_decimal = Decimal("0")


        try:

            rendimento_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    rendimento_diario
                )
            )

        except (
            TypeError,
            ValueError
        ):

            rendimento_decimal = Decimal("0")


        # -------------------------------------------------
        # DATAS
        # -------------------------------------------------

        data_inicio_rendimento = None

        if data_inicio:

            try:

                data_inicio_rendimento = (
                    datetime.strptime(
                        data_inicio,
                        "%Y-%m-%d"
                    ).date()
                )

            except ValueError:

                erro = (
                    "Informe uma data inicial válida."
                )


        prazo_data = None

        if prazo:

            try:

                prazo_data = datetime.strptime(
                    prazo,
                    "%Y-%m-%d"
                ).date()

            except ValueError:

                erro = (
                    "Informe um prazo válido."
                )


        # -------------------------------------------------
        # VALIDAÇÕES
        # -------------------------------------------------

        if (
            erro is None
            and
            valor_meta_decimal <= 0
        ):

            erro = (
                "O valor da meta deve ser "
                "maior que zero."
            )


        if (
            erro is None
            and
            valor_atual_decimal < 0
        ):

            erro = (
                "O valor atual não pode "
                "ser negativo."
            )


        if (
            erro is None
            and
            rendimento_decimal < 0
        ):

            erro = (
                "O rendimento diário não "
                "pode ser negativo."
            )


        if (
            erro is None
            and
            valor_atual_decimal >
            valor_meta_decimal
        ):

            valor_atual_decimal = (
                valor_meta_decimal
            )


        # -------------------------------------------------
        # CRIA
        # -------------------------------------------------

        if erro is None:

            meta = Meta(

                nome=nome,

                descricao=descricao,

                valor_meta=(
                    valor_meta_decimal
                ),

                valor_atual=(
                    valor_atual_decimal
                ),

                rendimento_diario=(
                    rendimento_decimal
                ),

                data_inicio_rendimento=(
                    data_inicio_rendimento
                ),

                prazo=prazo_data,

                ativa=True

            )

            db.session.add(
                meta
            )

            db.session.commit()

            return redirect(
                url_for(
                    "metas.listar"
                )
            )


    return render_template(

        "meta_form.html",

        meta=None,

        erro=erro

    )


# =========================================================
# EDITAR META
# =========================================================

@metas_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    meta = Meta.query.get_or_404(
        id
    )

    erro = None

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        valor_meta = request.form.get(
            "valor_meta",
            "0"
        )

        rendimento_diario = request.form.get(
            "rendimento_diario",
            "5,68"
        )

        data_inicio = request.form.get(
            "data_inicio_rendimento",
            ""
        )

        prazo = request.form.get(
            "prazo",
            ""
        )


        if not nome:

            erro = "Informe o nome da meta."


        try:

            valor_meta_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    valor_meta
                )
            )

        except (
            TypeError,
            ValueError
        ):

            valor_meta_decimal = Decimal("0")


        try:

            rendimento_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    rendimento_diario
                )
            )

        except (
            TypeError,
            ValueError
        ):

            rendimento_decimal = Decimal("0")


        data_inicio_rendimento = None

        if data_inicio:

            try:

                data_inicio_rendimento = (
                    datetime.strptime(
                        data_inicio,
                        "%Y-%m-%d"
                    ).date()
                )

            except ValueError:

                erro = (
                    "Informe uma data inicial válida."
                )


        prazo_data = None

        if prazo:

            try:

                prazo_data = datetime.strptime(
                    prazo,
                    "%Y-%m-%d"
                ).date()

            except ValueError:

                erro = (
                    "Informe um prazo válido."
                )


        if (
            erro is None
            and
            valor_meta_decimal <= 0
        ):

            erro = (
                "O valor da meta deve ser "
                "maior que zero."
            )


        if (
            erro is None
            and
            rendimento_decimal < 0
        ):

            erro = (
                "O rendimento diário não "
                "pode ser negativo."
            )


        if erro is None:

            meta.nome = nome

            meta.descricao = descricao

            meta.valor_meta = (
                valor_meta_decimal
            )

            meta.rendimento_diario = (
                rendimento_decimal
            )

            meta.data_inicio_rendimento = (
                data_inicio_rendimento
            )

            meta.prazo = prazo_data


            if meta.valor_atual > meta.valor_meta:

                meta.valor_atual = (
                    meta.valor_meta
                )


            db.session.commit()

            return redirect(
                url_for(
                    "metas.listar"
                )
            )


    return render_template(

        "meta_form.html",

        meta=meta,

        erro=erro

    )


# =========================================================
# APORTAR
# =========================================================

@metas_bp.route(
    "/<int:id>/aportar",
    methods=["GET", "POST"]
)
def aportar(id):

    meta = Meta.query.get_or_404(
        id
    )

    contas = (
        Conta.query
        .filter_by(
            ativa=True
        )
        .order_by(
            Conta.nome
        )
        .all()
    )

    erro = None

    if request.method == "POST":

        valor = request.form.get(
            "valor",
            "0"
        )

        conta_id = request.form.get(
            "conta_id"
        )

        data_str = request.form.get(
            "data"
        )

        observacao = request.form.get(
            "observacao",
            ""
        ).strip()


        try:

            valor_decimal = Decimal(
                moeda_brasileira_para_decimal(
                    valor
                )
            )

        except (
            TypeError,
            ValueError
        ):

            valor_decimal = Decimal("0")


        try:

            conta_id_int = int(
                conta_id
            )

        except (
            TypeError,
            ValueError
        ):

            conta_id_int = 0


        conta = (
            Conta.query
            .filter_by(
                id=conta_id_int,
                ativa=True
            )
            .first()
        )


        try:

            data = datetime.strptime(
                data_str,
                "%Y-%m-%d"
            ).date()

        except (
            TypeError,
            ValueError
        ):

            data = None


        if valor_decimal <= 0:

            erro = (
                "Informe um valor "
                "maior que zero."
            )

        elif not conta:

            erro = (
                "Selecione uma conta."
            )

        elif data is None:

            erro = (
                "Informe uma data válida."
            )

        elif (
            valor_decimal >
            Decimal(
                str(
                    conta.saldo_atual()
                )
            )
        ):

            erro = (
                "O valor do aporte é maior "
                "que o saldo atual da conta."
            )


        valor_restante = (
            Decimal(
                str(
                    meta.valor_meta or 0
                )
            )
            -
            Decimal(
                str(
                    meta.valor_atual or 0
                )
            )
        )


        if (
            erro is None
            and
            valor_decimal > valor_restante
        ):

            erro = (
                "O aporte ultrapassa o "
                "valor restante da meta."
            )


        if erro is None:

            categoria = (
                Categoria.query
                .filter_by(
                    nome="Metas financeiras",
                    tipo="despesa"
                )
                .first()
            )


            if not categoria:

                categoria = Categoria(

                    nome="Metas financeiras",

                    tipo="despesa",

                    ativa=True

                )

                db.session.add(
                    categoria
                )

                db.session.flush()


            lancamento = Lancamento(

                descricao=(
                    f"Aporte para meta: "
                    f"{meta.nome}"
                ),

                valor=valor_decimal,

                tipo="despesa",

                data=data,

                status="pago",

                conta_id=conta.id,

                categoria_id=categoria.id,

                observacao=(
                    observacao
                    or
                    f"Aporte financeiro para a meta "
                    f"'{meta.nome}'."
                )

            )

            db.session.add(
                lancamento
            )

            db.session.flush()


            meta_aporte = MetaAporte(

                meta_id=meta.id,

                conta_id=conta.id,

                lancamento_id=lancamento.id,

                valor=valor_decimal,

                data=data

            )

            db.session.add(
                meta_aporte
            )


            meta.valor_atual = (
                Decimal(
                    str(
                        meta.valor_atual or 0
                    )
                )
                +
                valor_decimal
            )


            if meta.valor_atual > meta.valor_meta:

                meta.valor_atual = (
                    meta.valor_meta
                )


            db.session.commit()


            return redirect(
                url_for(
                    "metas.listar"
                )
            )


    return render_template(

        "meta_aporte_form.html",

        meta=meta,

        contas=contas,

        erro=erro,

        today=datetime.now().date()

    )


# =========================================================
# EXCLUIR
# =========================================================

@metas_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    meta = Meta.query.get_or_404(
        id
    )

    meta.ativa = False

    db.session.commit()

    return redirect(
        url_for(
            "metas.listar"
        )
    )