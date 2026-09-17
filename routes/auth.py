from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models.usuario import Usuario

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
