import os
import uuid
from flask import Flask, request, session, redirect, url_for, g, flash

from config import Config
from database import db

from models import (
    Conta,
    Categoria,
    Lancamento,
    Usuario,
    LogAuditoria
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
from routes.integracoes import integracoes_bp
from routes.auth import auth_bp
from routes.transferencias import transferencias_bp
from routes.backup import backup_bp
from routes.simulador import simulador_bp


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

    @app.context_processor
    def injetar_usuario():
        usuario_id = session.get("usuario_id")
        if usuario_id:
            usuario = db.session.get(Usuario, usuario_id)
            return {"usuario_atual": usuario}
        return {"usuario_atual": None}


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

    # Integrações (Mercado Pago, etc.)
    app.register_blueprint(
        integracoes_bp
    )

    # Autenticação e Usuários
    app.register_blueprint(
        auth_bp
    )

    # Transferências entre contas
    app.register_blueprint(
        transferencias_bp
    )

    # Backup do sistema
    app.register_blueprint(
        backup_bp
    )

    # Simulador e Calculadora de Taxas (InfinitePay, etc.)
    app.register_blueprint(
        simulador_bp
    )

    # Limite máximo de payload para proteção contra DoS / Uploads gigantes
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    # =====================================================
    # CONTROLE DE ACESSO E RASTREABILIDADE
    # =====================================================

    @app.before_request
    def proteger_rotas():
        # Injeta correlation ID (request_id) para rastreabilidade de requisições
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Arquivos estáticos são sempre livres
        if request.endpoint == "static":
            return

        # Webhooks externos possuem autenticação própria por token no caminho
        path = request.path or ""
        if path.startswith("/webhooks") or path.startswith("/webhook"):
            return

        # Validação de certificados SSL (cPanel AutoSSL / Let's Encrypt / Sectigo DCV)
        if path.startswith("/.well-known"):
            return

        # Rotas públicas de autenticação (Login e 2FA)
        if request.endpoint in ("auth.login", "auth.verificar_2fa", "servir_desafio_ssl"):
            return

        # Se não logado, redireciona para login
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            if request.method == "GET" and request.endpoint:
                return redirect(url_for("auth.login", next=request.url))
            return redirect(url_for("auth.login"))

        # Se logado, garante a obrigatoriedade da configuração de 2FA
        usuario = db.session.get(Usuario, usuario_id)
        if usuario and not usuario.is_2fa_enabled:
            rotas_livres_2fa = (
                "auth.seguranca_2fa",
                "auth.ativar_2fa",
                "auth.concluir_onboarding_2fa",
                "auth.logout",
                "static"
            )
            if request.endpoint and request.endpoint not in rotas_livres_2fa:
                flash("Para a segurança dos dados financeiros, configure a Autenticação em 2 Etapas (2FA) para liberar o sistema.", "warning")
                return redirect(url_for("auth.seguranca_2fa"))

        # Controle de acesso granular por módulo (Mercado Pago / Mercado Livre, Nubank, InfinitePay)
        if usuario and not usuario.is_admin:
            endpoint = request.endpoint or ""
            
            # 1. Mercado Pago / Mercado Livre
            if endpoint.startswith("integracoes.mercadopago") and not getattr(usuario, "acesso_mercadopago", True):
                flash("Você não possui permissão para acessar a integração do Mercado Pago / Mercado Livre.", "warning")
                return redirect(url_for("dashboard.dashboard"))

            # 2. Nubank & Apple Pay
            if endpoint.startswith("integracoes.nubank") and not getattr(usuario, "acesso_nubank", True):
                flash("Você não possui permissão para acessar a integração do Nubank.", "warning")
                return redirect(url_for("dashboard.dashboard"))

            # 3. Calculadora InfinitePay
            if "infinitepay" in endpoint and not getattr(usuario, "acesso_infinitepay", True):
                flash("Você não possui permissão para acessar a Calculadora InfinitePay.", "warning")
                return redirect(url_for("dashboard.dashboard"))

    @app.route("/.well-known/<path:filename>")
    def servir_desafio_ssl(filename):
        """
        Permite que o cPanel AutoSSL / Let's Encrypt / Sectigo valide o domínio via HTTP DCV.
        """
        pastas_busca = [
            "/home/martinst/controlefinanceiro.martinstechti.com.br/.well-known",
            "/home/martinst/controlefinanceiro/.well-known",
            "/home/martinst/public_html/.well-known",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".well-known"),
        ]
        for base in pastas_busca:
            caminho_real = os.path.abspath(os.path.join(base, filename))
            if caminho_real.startswith(os.path.abspath(base)) and os.path.isfile(caminho_real):
                try:
                    with open(caminho_real, "rb") as f:
                        conteudo = f.read()
                    return conteudo, 200, {"Content-Type": "text/plain; charset=utf-8"}
                except Exception:
                    pass
        return "Desafio ACME não encontrado", 404

    @app.after_request
    def injetar_cabecalhos_seguranca(response):
        # Injeta correlation ID para auditoria
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id

        # Cabeçalhos de Proteção HTTP (OWASP ASVS / Top 10)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # Content-Security-Policy estrito
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        return response

    # =====================================================
    # INICIALIZAÇÃO E AUTO-MIGRAÇÃO DO BANCO
    # =====================================================

    with app.app_context():
        migrar_schema_sqlite()
        db.create_all()
        inicializar_dados()

    # -----------------------------------------------------
    # SUPORTE A PROXY REVERSO (NGINX / VPS / SSL)
    # -----------------------------------------------------
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1
    )

    return app


def migrar_schema_sqlite():
    """Aplica migrações incrementais no banco SQLite de forma idempotente e segura."""
    import sqlite3
    db_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data", "financeiro.db")
    if not os.path.exists(db_file):
        return
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(usuarios);")
        colunas = [row[1] for row in cursor.fetchall()]
        if colunas:
            if "totp_secret" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN totp_secret VARCHAR(64);")
            if "is_2fa_enabled" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT 0 NOT NULL;")
            if "backup_codes" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN backup_codes TEXT;")
            if "acesso_mercadopago" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN acesso_mercadopago BOOLEAN DEFAULT 1 NOT NULL;")
            if "acesso_infinitepay" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN acesso_infinitepay BOOLEAN DEFAULT 1 NOT NULL;")
            if "acesso_nubank" not in colunas:
                cursor.execute("ALTER TABLE usuarios ADD COLUMN acesso_nubank BOOLEAN DEFAULT 1 NOT NULL;")
        conn.commit()
        conn.close()
    except Exception as e:
        print("[Migracao SQLite Warning]:", e)



# =========================================================
# DADOS INICIAIS
# =========================================================

def inicializar_dados():
    from services.usuario_service import criar_usuario
    if not Usuario.query.first():
        criar_usuario("admin", "admin123", is_admin=True)


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