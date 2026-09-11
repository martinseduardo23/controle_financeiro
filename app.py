from flask import Flask

from config import Config
from database import db

from models import (
    Conta,
    Categoria,
    Lancamento
)

from routes.dashboard import dashboard_bp
from routes.contas import contas_bp
from routes.lancamentos import lancamentos_bp
from routes.categorias import categorias_bp
from routes.cartoes import cartoes_bp
from routes.compras_cartao import compras_cartao_bp
from routes.faturas_cartao import faturas_cartao_bp
from routes.metas import metas_bp
from routes.relatorios import relatorios_bp


# =========================================================
# FILTRO DE MOEDA
# =========================================================

def formatar_moeda(valor):

    try:

        valor = float(
            valor or 0
        )

    except (
        TypeError,
        ValueError
    ):

        valor = 0.0


    negativo = valor < 0

    valor = abs(
        valor
    )


    texto = f"{valor:,.2f}"

    texto = (
        texto
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


    if negativo:

        texto = "-" + texto


    return texto


# =========================================================
# CRIAR APLICAÇÃO
# =========================================================

def criar_app():

    app = Flask(
        __name__
    )


    app.config.from_object(
        Config
    )


    # -----------------------------------------------------
    # FILTRO JINJA
    # -----------------------------------------------------

    app.template_filter(
        "moeda"
    )(
        formatar_moeda
    )


    # -----------------------------------------------------
    # BANCO
    # -----------------------------------------------------

    db.init_app(
        app
    )


    # =====================================================
    # BLUEPRINTS
    # =====================================================

    # Dashboard
    app.register_blueprint(
        dashboard_bp
    )


    # Contas
    app.register_blueprint(
        contas_bp
    )


    # Lançamentos
    app.register_blueprint(
        lancamentos_bp
    )


    # Categorias
    app.register_blueprint(
        categorias_bp
    )


    # Cartões
    app.register_blueprint(
        cartoes_bp
    )


    # Compras no cartão
    app.register_blueprint(
        compras_cartao_bp
    )


    # Faturas dos cartões
    app.register_blueprint(
        faturas_cartao_bp
    )


    # Metas
    app.register_blueprint(
        metas_bp
    )


    # Relatórios
    app.register_blueprint(
        relatorios_bp
    )


    # =====================================================
    # INICIALIZAÇÃO DO BANCO
    # =====================================================

    with app.app_context():

        db.create_all()

        inicializar_dados()


    return app


# =========================================================
# DADOS INICIAIS
# =========================================================

def inicializar_dados():

    categorias = [

        ("Salário", "receita"),

        ("Freelance", "receita"),

        ("Outras receitas", "receita"),

        ("Moradia", "despesa"),

        ("Alimentação", "despesa"),

        ("Transporte", "despesa"),

        ("Saúde", "despesa"),

        ("Educação", "despesa"),

        ("Lazer", "despesa"),

        ("Assinaturas", "despesa"),

        ("Impostos", "despesa"),

        ("Financiamentos", "despesa"),

        ("Outras despesas", "despesa"),

    ]


    # -----------------------------------------------------
    # CATEGORIAS
    # -----------------------------------------------------

    for nome, tipo in categorias:

        existente = (
            Categoria.query
            .filter_by(
                nome=nome,
                tipo=tipo
            )
            .first()
        )


        if not existente:

            db.session.add(
                Categoria(
                    nome=nome,
                    tipo=tipo
                )
            )


    # -----------------------------------------------------
    # CONTA PRINCIPAL
    # -----------------------------------------------------

    if not Conta.query.first():

        db.session.add(
            Conta(

                nome="Conta principal",

                tipo="Conta corrente",

                saldo_inicial=0

            )
        )


    # -----------------------------------------------------
    # SALVAR
    # -----------------------------------------------------

    db.session.commit()


# =========================================================
# INSTÂNCIA DA APLICAÇÃO
# =========================================================

app = criar_app()


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

    )