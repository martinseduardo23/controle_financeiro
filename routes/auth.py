from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models.usuario import Usuario
from services.usuario_service import criar_usuario
from services.security_service import (
    limiter_login,
    gerar_secret_2fa,
    gerar_uri_provisionamento,
    gerar_qr_code_svg,
    verificar_codigo_totp,
    gerar_codigos_backup,
    validar_forca_senha
)
from services.audit_service import registrar_auditoria

auth_bp = Blueprint("auth", __name__)


def obter_ip_cliente():
    return request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "127.0.0.1"


# =========================================================
# 1. LOGIN COM PROTEÇÃO CONTRA FORÇA BRUTA E 2FA
# =========================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard.dashboard"))

    chave_ip = f"ip:{obter_ip_cliente()}"

    # Verifica se o IP está bloqueado temporariamente por excesso de falhas
    bloqueado, segundos = limiter_login.esta_bloqueado(chave_ip)
    if bloqueado:
        flash(f"Muitas tentativas incorretas. Acesso bloqueado por segurança. Tente novamente em {segundos} segundos.", "danger")
        return render_template("login.html")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        chave_usuario = f"user:{username.lower()}"

        # Verifica bloqueio específico por usuário
        bloqueado_user, seg_user = limiter_login.esta_bloqueado(chave_usuario)
        if bloqueado_user:
            flash(f"Conta temporariamente bloqueada por excesso de tentativas. Tente novamente em {seg_user} segundos.", "danger")
            return render_template("login.html")

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.check_password(password):
            # Se o usuário possui 2FA ativo, inicia o fluxo de segundo fator
            if usuario.is_2fa_enabled and usuario.totp_secret:
                session["partial_2fa_user_id"] = usuario.id
                session["partial_2fa_remember"] = bool(request.form.get("remember"))
                session["partial_2fa_next"] = request.args.get("next")
                registrar_auditoria("auth.login_password_ok_pending_2fa", usuario_id=usuario.id)
                return redirect(url_for("auth.verificar_2fa"))

            # Sem 2FA: Concede sessão mas força o onboarding obrigatório de 2FA
            limiter_login.limpar_sucesso(chave_ip)
            limiter_login.limpar_sucesso(chave_usuario)

            session.clear()
            session["usuario_id"] = usuario.id
            session["username"] = usuario.username
            session["is_admin"] = bool(usuario.is_admin)

            registrar_auditoria("auth.login_success_pending_2fa", usuario_id=usuario.id)
            flash(f"Bem-vindo(a), {usuario.username}! Para a segurança das suas finanças, configure a Autenticação em Duas Etapas (2FA) para liberar o sistema.", "warning")
            return redirect(url_for("auth.seguranca_2fa"))

        # Credenciais incorretas: registra falha
        limiter_login.registrar_falha(chave_ip, max_tentativas=5, janela_segundos=300, tempo_bloqueio=600)
        limiter_login.registrar_falha(chave_usuario, max_tentativas=5, janela_segundos=300, tempo_bloqueio=600)

        registrar_auditoria("auth.login_failed", detalhes={"username": username})
        flash("Usuário ou senha incorretos. Tente novamente.", "danger")

    return render_template("login.html")


# =========================================================
# 2. VERIFICAÇÃO DE 2FA NO LOGIN
# =========================================================

@auth_bp.route("/2fa/verificar", methods=["GET", "POST"])
def verificar_2fa():
    usuario_id = session.get("partial_2fa_user_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario or not usuario.is_2fa_enabled:
        session.pop("partial_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    chave_ip = f"2fa:{obter_ip_cliente()}"
    bloqueado, segundos = limiter_login.esta_bloqueado(chave_ip)
    if bloqueado:
        flash(f"Muitas tentativas de código 2FA. Bloqueado por {segundos} segundos.", "danger")
        return render_template("login_2fa.html")

    if request.method == "POST":
        codigo = (request.form.get("codigo_2fa") or "").strip()

        # 1. Tenta validar via TOTP (6 dígitos)
        sucesso_totp = verificar_codigo_totp(usuario.totp_secret, codigo)

        # 2. Se falhar, tenta validar como código de backup de emergência
        sucesso_backup = False
        if not sucesso_totp and len(codigo) >= 6:
            sucesso_backup = usuario.consumir_codigo_backup(codigo)

        if sucesso_totp or sucesso_backup:
            limiter_login.limpar_sucesso(chave_ip)
            limiter_login.limpar_sucesso(f"ip:{obter_ip_cliente()}")
            limiter_login.limpar_sucesso(f"user:{usuario.username.lower()}")

            next_url = session.get("partial_2fa_next")
            session.clear()
            session["usuario_id"] = usuario.id
            session["username"] = usuario.username
            session["is_admin"] = bool(usuario.is_admin)

            metodo = "backup_code" if sucesso_backup else "totp"
            registrar_auditoria("auth.2fa_success", usuario_id=usuario.id, detalhes={"metodo": metodo})

            if sucesso_backup:
                flash("Login realizado com código de recuperação! Recomendamos gerar novos códigos no seu perfil.", "warning")
            else:
                flash(f"Autenticação de dois fatores concluída. Bem-vindo(a), {usuario.username}!", "success")

            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard.dashboard"))

        # Falha de código 2FA
        limiter_login.registrar_falha(chave_ip, max_tentativas=5, janela_segundos=300, tempo_bloqueio=600)
        registrar_auditoria("auth.2fa_failed", usuario_id=usuario.id)
        flash("Código de autenticação incorreto ou expirado. Tente novamente.", "danger")

    return render_template("login_2fa.html")


# =========================================================
# 3. CONFIGURAÇÃO DE 2FA NO PERFIL
# =========================================================

@auth_bp.route("/perfil/seguranca", methods=["GET"])
def seguranca_2fa():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        session.clear()
        return redirect(url_for("auth.login"))

    secret_temp = None
    qr_svg = None
    codigos_backup_novos = []

    # Se ainda não tiver 2FA ativo, prepara um novo segredo temporário na sessão
    if not usuario.is_2fa_enabled:
        secret_temp = session.get("temp_totp_secret")
        if not secret_temp:
            secret_temp = gerar_secret_2fa()
            session["temp_totp_secret"] = secret_temp

        uri = gerar_uri_provisionamento(secret_temp, usuario.username)
        qr_svg = gerar_qr_code_svg(uri)

    codigos_restantes = len(usuario.obter_codigos_backup()) if usuario.is_2fa_enabled else 0

    return render_template(
        "seguranca_2fa.html",
        usuario=usuario,
        secret_temp=secret_temp,
        qr_svg=qr_svg,
        codigos_restantes=codigos_restantes
    )


@auth_bp.route("/perfil/2fa/ativar", methods=["POST"])
def ativar_2fa():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    secret_temp = session.get("temp_totp_secret")
    codigo = (request.form.get("codigo_verificacao") or "").strip()

    if not secret_temp:
        flash("Sessão de configuração expirada. Tente novamente.", "warning")
        return redirect(url_for("auth.seguranca_2fa"))

    if not verificar_codigo_totp(secret_temp, codigo):
        flash("Código de verificação incorreto. Verifique o relógio do seu celular e tente novamente.", "danger")
        return redirect(url_for("auth.seguranca_2fa"))

    # Gera 5 códigos de recuperação descartáveis
    backup_codes = gerar_codigos_backup(5)
    usuario.habilitar_2fa(secret_temp, backup_codes)
    db.session.commit()

    session.pop("temp_totp_secret", None)
    session["backup_codes_apresentar"] = backup_codes

    registrar_auditoria("auth.2fa_enabled", usuario_id=usuario.id)
    flash("Autenticação em 2 Etapas (2FA) ATIVADA com sucesso! Salve seus códigos de recuperação abaixo e clique em Concluir para liberar o sistema.", "success")
    return redirect(url_for("auth.seguranca_2fa"))


@auth_bp.route("/perfil/2fa/concluir", methods=["GET"])
def concluir_onboarding_2fa():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario or not usuario.is_2fa_enabled:
        flash("Configure e ative o 2FA para liberar o acesso ao sistema.", "warning")
        return redirect(url_for("auth.seguranca_2fa"))

    session.pop("backup_codes_apresentar", None)
    flash("Autenticação em 2 Etapas confirmada! Acesso total liberado com segurança.", "success")
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/perfil/2fa/desativar", methods=["POST"])
def desativar_2fa():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    senha = request.form.get("senha_confirmacao") or ""

    if not usuario.check_password(senha):
        flash("Senha incorreta. Não foi possível desativar o 2FA.", "danger")
        return redirect(url_for("auth.seguranca_2fa"))

    usuario.desabilitar_2fa()
    db.session.commit()

    registrar_auditoria("auth.2fa_disabled", usuario_id=usuario.id)
    flash("Autenticação em 2 Etapas (2FA) foi desativada.", "warning")
    return redirect(url_for("auth.seguranca_2fa"))


@auth_bp.route("/perfil/2fa/novos-codigos", methods=["POST"])
def gerar_novos_codigos_backup():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    senha = request.form.get("senha_confirmacao") or ""

    if not usuario.is_2fa_enabled:
        flash("2FA não está ativado nesta conta.", "warning")
        return redirect(url_for("auth.seguranca_2fa"))

    if not usuario.check_password(senha):
        flash("Senha incorreta. Não foi possível gerar novos códigos.", "danger")
        return redirect(url_for("auth.seguranca_2fa"))

    novos_codigos = gerar_codigos_backup(5)
    usuario.backup_codes = json.dumps(novos_codigos)
    db.session.commit()

    session["backup_codes_apresentar"] = novos_codigos
    registrar_auditoria("auth.2fa_backup_codes_regenerated", usuario_id=usuario.id)
    flash("Novos códigos de recuperação gerados com sucesso!", "success")
    return redirect(url_for("auth.seguranca_2fa"))


# =========================================================
# 4. LOGOUT & SENHA
# =========================================================

@auth_bp.route("/logout")
def logout():
    usuario_id = session.get("usuario_id")
    if usuario_id:
        registrar_auditoria("auth.logout", usuario_id=usuario_id)
    session.clear()
    flash("Sessão encerrada com segurança.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/perfil/alterar-senha", methods=["GET", "POST"])
def alterar_senha():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        session.clear()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        senha_atual = request.form.get("senha_atual") or ""
        nova_senha = request.form.get("nova_senha") or ""
        confirmacao = request.form.get("confirmacao") or ""

        if not usuario.check_password(senha_atual):
            flash("Senha atual incorreta.", "danger")
            return render_template("alterar_senha.html")

        valida, msg = validar_forca_senha(nova_senha)
        if not valida:
            flash(msg, "warning")
            return render_template("alterar_senha.html")

        if nova_senha != confirmacao:
            flash("A confirmação da nova senha não confere.", "danger")
            return render_template("alterar_senha.html")

        usuario.set_password(nova_senha)
        db.session.commit()
        registrar_auditoria("auth.password_changed", usuario_id=usuario.id)
        flash("Senha atualizada com sucesso utilizando criptografia Argon2id!", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("alterar_senha.html")


# =========================================================
# 5. GESTÃO DE USUÁRIOS (ADMINISTRADOR)
# =========================================================

@auth_bp.route("/usuarios", methods=["GET"])
def listar_usuarios():
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()
    return render_template("usuarios.html", usuarios=usuarios)


@auth_bp.route("/usuarios/novo", methods=["POST"])
def novo_usuario():
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    is_admin = bool(request.form.get("is_admin"))
    acesso_mercadopago = bool(request.form.get("acesso_mercadopago"))
    acesso_infinitepay = bool(request.form.get("acesso_infinitepay"))
    acesso_nubank = bool(request.form.get("acesso_nubank"))

    valida, msg = validar_forca_senha(password)
    if not valida:
        flash(msg, "warning")
        return redirect(url_for("auth.listar_usuarios"))

    try:
        usuario_criado = criar_usuario(
            username,
            password,
            is_admin=is_admin,
            acesso_mercadopago=acesso_mercadopago,
            acesso_infinitepay=acesso_infinitepay,
            acesso_nubank=acesso_nubank
        )
        registrar_auditoria(
            "auth.user_created",
            usuario_id=session.get("usuario_id"),
            detalhes={
                "novo_usuario": username,
                "is_admin": is_admin,
                "acesso_mercadopago": acesso_mercadopago,
                "acesso_infinitepay": acesso_infinitepay,
                "acesso_nubank": acesso_nubank,
            }
        )
        flash(f"Usuário '{usuario_criado.username}' criado com sucesso! No primeiro login, a ativação do 2FA será obrigatória.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash("Erro ao criar usuário.", "danger")

    return redirect(url_for("auth.listar_usuarios"))


@auth_bp.route("/usuarios/<int:id>/excluir", methods=["POST"])
def excluir_usuario(id):
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    if id == session.get("usuario_id"):
        flash("Você não pode excluir sua própria conta enquanto estiver logado.", "warning")
        return redirect(url_for("auth.listar_usuarios"))

    usuario = db.session.get(Usuario, id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.listar_usuarios"))

    nome = usuario.username
    db.session.delete(usuario)
    db.session.commit()
    registrar_auditoria("auth.user_deleted", usuario_id=session.get("usuario_id"), detalhes={"usuario_excluido": nome})
    flash(f"Usuário '{nome}' e todos os seus dados foram excluídos com sucesso.", "success")
    return redirect(url_for("auth.listar_usuarios"))


@auth_bp.route("/usuarios/<int:id>/resetar-senha", methods=["POST"])
def resetar_senha_usuario(id):
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    nova_senha = request.form.get("nova_senha") or ""
    valida, msg = validar_forca_senha(nova_senha)
    if not valida:
        flash(msg, "warning")
        return redirect(url_for("auth.listar_usuarios"))

    usuario = db.session.get(Usuario, id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.listar_usuarios"))

    usuario.set_password(nova_senha)
    db.session.commit()
    registrar_auditoria("auth.user_password_reset", usuario_id=session.get("usuario_id"), detalhes={"usuario_afetado": usuario.username})
    flash(f"Senha do usuário '{usuario.username}' redefinida com sucesso!", "success")
    return redirect(url_for("auth.listar_usuarios"))


@auth_bp.route("/usuarios/<int:id>/permissoes", methods=["POST"])
def atualizar_permissoes_usuario(id):
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    usuario = db.session.get(Usuario, id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.listar_usuarios"))

    # Não permite tirar o próprio status de administrador para evitar auto-bloqueio
    if id == session.get("usuario_id"):
        is_admin = True
    else:
        is_admin = bool(request.form.get("is_admin"))

    acesso_mercadopago = bool(request.form.get("acesso_mercadopago"))
    acesso_infinitepay = bool(request.form.get("acesso_infinitepay"))
    acesso_nubank = bool(request.form.get("acesso_nubank"))

    if is_admin:
        acesso_mercadopago = True
        acesso_infinitepay = True
        acesso_nubank = True

    usuario.is_admin = is_admin
    usuario.acesso_mercadopago = acesso_mercadopago
    usuario.acesso_infinitepay = acesso_infinitepay
    usuario.acesso_nubank = acesso_nubank

    db.session.commit()
    registrar_auditoria(
        "auth.user_permissions_updated",
        usuario_id=session.get("usuario_id"),
        detalhes={
            "usuario_afetado": usuario.username,
            "is_admin": is_admin,
            "acesso_mercadopago": acesso_mercadopago,
            "acesso_infinitepay": acesso_infinitepay,
            "acesso_nubank": acesso_nubank,
        }
    )
    flash(f"Permissões do usuário '{usuario.username}' atualizadas com sucesso!", "success")
    return redirect(url_for("auth.listar_usuarios"))
