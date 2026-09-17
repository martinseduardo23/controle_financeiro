from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models.usuario import Usuario
from services.usuario_service import criar_usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.check_password(password):
            session["usuario_id"] = usuario.id
            session["username"] = usuario.username
            session["is_admin"] = bool(usuario.is_admin)
            flash(f"Bem-vindo(a) de volta, {usuario.username}!", "success")

            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard.dashboard"))

        flash("Usuário ou senha incorretos. Tente novamente.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
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

        if len(nova_senha) < 4:
            flash("A nova senha deve ter pelo menos 4 caracteres.", "warning")
            return render_template("alterar_senha.html")

        if nova_senha != confirmacao:
            flash("A confirmação da nova senha não confere.", "danger")
            return render_template("alterar_senha.html")

        usuario.set_password(nova_senha)
        db.session.commit()
        flash("Senha atualizada com sucesso!", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("alterar_senha.html")


# =========================================================
# GESTÃO DE USUÁRIOS (ADMINISTRADOR)
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

    try:
        usuario_criado = criar_usuario(username, password, is_admin=is_admin)
        flash(f"Usuário '{usuario_criado.username}' criado com sucesso com categorias e conta inicial!", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar usuário: {str(e)}", "danger")

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
    flash(f"Usuário '{nome}' e todos os seus dados foram excluídos com sucesso.", "success")
    return redirect(url_for("auth.listar_usuarios"))


@auth_bp.route("/usuarios/<int:id>/resetar-senha", methods=["POST"])
def resetar_senha_usuario(id):
    if not session.get("is_admin"):
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    nova_senha = request.form.get("nova_senha") or ""
    if len(nova_senha) < 4:
        flash("A senha deve ter pelo menos 4 caracteres.", "warning")
        return redirect(url_for("auth.listar_usuarios"))

    usuario = db.session.get(Usuario, id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.listar_usuarios"))

    usuario.set_password(nova_senha)
    db.session.commit()
    flash(f"Senha do usuário '{usuario.username}' redefinida com sucesso!", "success")
    return redirect(url_for("auth.listar_usuarios"))
