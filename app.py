from flask import Flask

from config import Config
from database import db

from models import Conta, Categoria, Lancamento

from routes.dashboard import dashboard_bp
from routes.contas import contas_bp
from routes.lancamentos import lancamentos_bp
from routes.categorias import categorias_bp



def formatar_moeda(valor):
    try:
        valor = float(valor or 0)
    except (TypeError, ValueError):
        valor = 0.0

    negativo = valor < 0
    valor = abs(valor)

    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")

    if negativo:
        texto = "-" + texto

    return texto


def criar_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.template_filter("moeda")(formatar_moeda)

    db.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(contas_bp)
    app.register_blueprint(lancamentos_bp)
    app.register_blueprint(categorias_bp)

    with app.app_context():
        db.create_all()
        inicializar_dados()

    return app


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

    for nome, tipo in categorias:
        existente = Categoria.query.filter_by(
            nome=nome,
            tipo=tipo
        ).first()

        if not existente:
            db.session.add(
                Categoria(
                    nome=nome,
                    tipo=tipo
                )
            )

    if not Conta.query.first():
        db.session.add(
            Conta(
                nome="Conta principal",
                tipo="Conta corrente",
                saldo_inicial=0
            )
        )

    db.session.commit()


app = criar_app()

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
