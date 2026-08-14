from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from sqlalchemy import or_

from database import db
from models import Lancamento, Conta, Categoria


lancamentos_bp = Blueprint(
    "lancamentos",
    __name__,
    url_prefix="/lancamentos"
)


def moeda_brasileira_para_decimal(valor):
    valor = (valor or "").strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if not valor:
        return 0

    return valor.replace(".", "").replace(",", ".")


def categorias_por_tipo(tipo):
    return Categoria.query.filter_by(
        ativa=True,
        tipo=tipo
    ).order_by(
        Categoria.nome
    ).all()


def obter_filtros():
    return {
        "busca": request.args.get("busca", "").strip(),
        "mes": request.args.get("mes", "").strip(),
        "data_inicio": request.args.get("data_inicio", "").strip(),
        "data_fim": request.args.get("data_fim", "").strip(),
        "tipo": request.args.get("tipo", "").strip(),
        "status": request.args.get("status", "").strip(),
        "conta_id": request.args.get("conta_id", "").strip(),
        "categoria_id": request.args.get("categoria_id", "").strip(),
    }


def aplicar_filtros(query, filtros):
    if filtros["busca"]:
        termo = f"%{filtros['busca']}%"
        query = query.filter(
            or_(
                Lancamento.descricao.ilike(termo),
                Lancamento.observacao.ilike(termo)
            )
        )

    if filtros["mes"]:
        try:
            ano, mes = filtros["mes"].split("-")
            ano = int(ano)
            mes = int(mes)

            if mes == 12:
                proximo_ano = ano + 1
                proximo_mes = 1
            else:
                proximo_ano = ano
                proximo_mes = mes + 1

            inicio = datetime(ano, mes, 1).date()
            fim = datetime(
                proximo_ano,
                proximo_mes,
                1
            ).date()

            query = query.filter(
                Lancamento.data >= inicio,
                Lancamento.data < fim
            )
        except (ValueError, TypeError):
            pass

    if filtros["data_inicio"]:
        try:
            inicio = datetime.strptime(
                filtros["data_inicio"],
                "%Y-%m-%d"
            ).date()

            query = query.filter(
                Lancamento.data >= inicio
            )
        except ValueError:
            pass

    if filtros["data_fim"]:
        try:
            fim = datetime.strptime(
                filtros["data_fim"],
                "%Y-%m-%d"
            ).date()

            query = query.filter(
                Lancamento.data <= fim
            )
        except ValueError:
            pass

    if filtros["tipo"] in ("receita", "despesa"):
        query = query.filter(
            Lancamento.tipo == filtros["tipo"]
        )

    if filtros["status"] in (
        "pago",
        "pendente",
        "agendado"
    ):
        query = query.filter(
            Lancamento.status == filtros["status"]
        )

    if filtros["conta_id"].isdigit():
        query = query.filter(
            Lancamento.conta_id == int(
                filtros["conta_id"]
            )
        )

    if filtros["categoria_id"].isdigit():
        query = query.filter(
            Lancamento.categoria_id == int(
                filtros["categoria_id"]
            )
        )

    return query


@lancamentos_bp.route("/")
def listar():

    filtros = obter_filtros()

    query = Lancamento.query

    query = aplicar_filtros(
        query,
        filtros
    )

    lancamentos = query.order_by(
        Lancamento.data.desc(),
        Lancamento.id.desc()
    ).all()

    total_receitas = sum(
        float(l.valor or 0)
        for l in lancamentos
        if l.tipo == "receita"
    )

    total_despesas = sum(
        float(l.valor or 0)
        for l in lancamentos
        if l.tipo == "despesa"
    )

    saldo_resultado = (
        total_receitas -
        total_despesas
    )

    contas = Conta.query.filter_by(
        ativa=True
    ).order_by(
        Conta.nome
    ).all()

    categorias = Categoria.query.filter_by(
        ativa=True
    ).order_by(
        Categoria.tipo,
        Categoria.nome
    ).all()

    return render_template(
        "lancamentos.html",
        lancamentos=lancamentos,
        contas=contas,
        categorias=categorias,
        filtros=filtros,
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo_resultado=saldo_resultado
    )


@lancamentos_bp.route(
    "/novo",
    methods=["GET", "POST"]
)
def novo():

    if request.method == "POST":

        descricao = request.form.get(
            "descricao"
        )

        valor = request.form.get(
            "valor"
        )

        tipo = request.form.get(
            "tipo"
        )

        data_str = request.form.get(
            "data"
        )

        status = request.form.get(
            "status"
        )

        conta_id = request.form.get(
            "conta_id"
        )

        categoria_id = request.form.get(
            "categoria_id"
        )

        observacao = request.form.get(
            "observacao"
        )

        data = datetime.strptime(
            data_str,
            "%Y-%m-%d"
        ).date()

        categoria = Categoria.query.filter_by(
            id=categoria_id,
            ativa=True
        ).first()

        if not categoria or categoria.tipo != tipo:
            return redirect(
                url_for("lancamentos.novo")
            )

        lancamento = Lancamento(
            descricao=descricao,
            valor=moeda_brasileira_para_decimal(
                valor
            ),
            tipo=tipo,
            data=data,
            status=status,
            conta_id=conta_id,
            categoria_id=categoria_id,
            observacao=observacao
        )

        db.session.add(lancamento)
        db.session.commit()

        return redirect(
            url_for("lancamentos.listar")
        )

    contas = Conta.query.filter_by(
        ativa=True
    ).order_by(
        Conta.nome
    ).all()

    categorias = Categoria.query.filter_by(
        ativa=True
    ).order_by(
        Categoria.tipo,
        Categoria.nome
    ).all()

    return render_template(
        "lancamento_form.html",
        contas=contas,
        categorias=categorias,
        lancamento=None
    )


@lancamentos_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar(id):

    lancamento = Lancamento.query.get_or_404(id)

    if request.method == "POST":

        lancamento.descricao = request.form.get(
            "descricao"
        )

        lancamento.valor = (
            moeda_brasileira_para_decimal(
                request.form.get("valor")
            )
        )

        lancamento.tipo = request.form.get(
            "tipo"
        )

        lancamento.data = datetime.strptime(
            request.form.get("data"),
            "%Y-%m-%d"
        ).date()

        lancamento.status = request.form.get(
            "status"
        )

        lancamento.conta_id = request.form.get(
            "conta_id"
        )

        lancamento.categoria_id = request.form.get(
            "categoria_id"
        )

        lancamento.observacao = request.form.get(
            "observacao"
        )

        categoria = Categoria.query.filter_by(
            id=lancamento.categoria_id,
            ativa=True
        ).first()

        if not categoria or categoria.tipo != lancamento.tipo:
            return redirect(
                url_for("lancamentos.editar", id=id)
            )

        db.session.commit()

        return redirect(
            url_for("lancamentos.listar")
        )

    contas = Conta.query.filter_by(
        ativa=True
    ).order_by(
        Conta.nome
    ).all()

    categorias = Categoria.query.filter_by(
        ativa=True
    ).order_by(
        Categoria.tipo,
        Categoria.nome
    ).all()

    return render_template(
        "lancamento_form.html",
        contas=contas,
        categorias=categorias,
        lancamento=lancamento
    )


@lancamentos_bp.route(
    "/excluir/<int:id>",
    methods=["POST"]
)
def excluir(id):

    lancamento = Lancamento.query.get_or_404(id)

    db.session.delete(lancamento)
    db.session.commit()

    return redirect(
        url_for("lancamentos.listar")
    )
