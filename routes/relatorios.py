from datetime import date, datetime

from flask import (
    Blueprint,
    render_template,
    request
)

from models import Lancamento


relatorios_bp = Blueprint(
    "relatorios",
    __name__,
    url_prefix="/relatorios"
)


# =========================================================
# AUXILIAR - MÊS
# =========================================================

def obter_mes():

    mes_param = request.args.get(
        "mes",
        ""
    ).strip()

    hoje = date.today()

    if mes_param:

        try:

            ano, mes = (
                mes_param.split("-")
            )

            ano = int(ano)
            mes = int(mes)

            if 1 <= mes <= 12:

                return ano, mes

        except (
            ValueError,
            TypeError
        ):

            pass

    return (
        hoje.year,
        hoje.month
    )


# =========================================================
# RELATÓRIOS
# =========================================================

@relatorios_bp.route("/")
def listar():

    ano, mes = obter_mes()


    # =====================================================
    # INTERVALO DO MÊS
    # =====================================================

    inicio = datetime(
        ano,
        mes,
        1
    ).date()


    if mes == 12:

        fim = datetime(
            ano + 1,
            1,
            1
        ).date()

    else:

        fim = datetime(
            ano,
            mes + 1,
            1
        ).date()


    # =====================================================
    # LANÇAMENTOS DO MÊS
    # =====================================================

    lancamentos = (
        Lancamento.query
        .filter(
            Lancamento.data >= inicio,
            Lancamento.data < fim
        )
        .order_by(
            Lancamento.data.asc(),
            Lancamento.id.asc()
        )
        .all()
    )


    # =====================================================
    # RECEITAS / DESPESAS
    # =====================================================

    receitas_pagas = 0.0

    despesas_pagas = 0.0

    receitas_pendentes = 0.0

    despesas_pendentes = 0.0


    # =====================================================
    # DESPESAS POR CATEGORIA
    # =====================================================

    despesas_categorias = {}


    # =====================================================
    # RECEITAS POR CATEGORIA
    # =====================================================

    receitas_categorias = {}


    for lancamento in lancamentos:

        valor = float(
            lancamento.valor or 0
        )


        if lancamento.tipo == "receita":

            if lancamento.status == "pago":

                receitas_pagas += valor

                nome_categoria = (
                    lancamento.categoria.nome
                    if lancamento.categoria
                    else "Sem categoria"
                )

                receitas_categorias[
                    nome_categoria
                ] = (
                    receitas_categorias.get(
                        nome_categoria,
                        0
                    )
                    + valor
                )

            else:

                receitas_pendentes += valor


        else:

            if lancamento.status == "pago":

                despesas_pagas += valor

                nome_categoria = (
                    lancamento.categoria.nome
                    if lancamento.categoria
                    else "Sem categoria"
                )

                despesas_categorias[
                    nome_categoria
                ] = (
                    despesas_categorias.get(
                        nome_categoria,
                        0
                    )
                    + valor
                )

            else:

                despesas_pendentes += valor


    # =====================================================
    # RESULTADO
    # =====================================================

    resultado = (
        receitas_pagas
        -
        despesas_pagas
    )


    # =====================================================
    # PERCENTUAIS DAS DESPESAS
    # =====================================================

    despesas_categorias_lista = []

    if despesas_pagas > 0:

        for nome, valor in sorted(
            despesas_categorias.items(),
            key=lambda item: item[1],
            reverse=True
        ):

            percentual = (
                valor
                /
                despesas_pagas
                *
                100
            )

            despesas_categorias_lista.append({

                "nome": nome,

                "valor": valor,

                "percentual": percentual

            })

    else:

        for nome, valor in sorted(
            despesas_categorias.items(),
            key=lambda item: item[1],
            reverse=True
        ):

            despesas_categorias_lista.append({

                "nome": nome,

                "valor": valor,

                "percentual": 0

            })


    # =====================================================
    # PERCENTUAIS DAS RECEITAS
    # =====================================================

    receitas_categorias_lista = []

    if receitas_pagas > 0:

        for nome, valor in sorted(
            receitas_categorias.items(),
            key=lambda item: item[1],
            reverse=True
        ):

            percentual = (
                valor
                /
                receitas_pagas
                *
                100
            )

            receitas_categorias_lista.append({

                "nome": nome,

                "valor": valor,

                "percentual": percentual

            })


    # =====================================================
    # NOME DO MÊS
    # =====================================================

    nomes_meses = [

        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro"

    ]

    nome_mes = nomes_meses[
        mes - 1
    ]


    return render_template(

        "relatorios.html",

        ano=ano,

        mes=mes,

        nome_mes=nome_mes,

        receitas_pagas=receitas_pagas,

        despesas_pagas=despesas_pagas,

        receitas_pendentes=receitas_pendentes,

        despesas_pendentes=despesas_pendentes,

        resultado=resultado,

        despesas_categorias=(
            despesas_categorias_lista
        ),

        receitas_categorias=(
            receitas_categorias_lista
        ),

        lancamentos=lancamentos

    )