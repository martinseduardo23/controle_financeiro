import os
import shutil
from datetime import datetime
from flask import Blueprint, send_file, request, redirect, url_for, flash
from config import BASE_DIR
from database import db

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/backup/download", methods=["GET"])
def download():
    db_path = os.path.join(BASE_DIR, "data", "financeiro.db")
    if not os.path.exists(db_path):
        flash("Arquivo de banco de dados não encontrado.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    nome_arquivo = f"financeiro_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(
        db_path,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/x-sqlite3"
    )


@backup_bp.route("/backup/restaurar", methods=["POST"])
def restaurar():
    arquivo = request.files.get("arquivo_db")
    if not arquivo or not arquivo.filename:
        flash("Nenhum arquivo selecionado para restauração.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    if not (arquivo.filename.endswith(".db") or arquivo.filename.endswith(".sqlite") or arquivo.filename.endswith(".sqlite3")):
        flash("O arquivo deve ser um banco de dados SQLite (.db ou .sqlite).", "danger")
        return redirect(url_for("dashboard.dashboard"))

    db_path = os.path.join(BASE_DIR, "data", "financeiro.db")
    backup_seguranca = os.path.join(BASE_DIR, "data", f"financeiro_antes_restauracao_{int(datetime.now().timestamp())}.db")

    try:
        # Fechar qualquer sessão aberta
        db.session.remove()

        # Cria cópia de segurança antes de sobrescrever
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_seguranca)

        # Salva o novo arquivo
        arquivo.save(db_path)
        flash("Backup restaurado com sucesso! Seus dados foram carregados.", "success")
    except Exception as e:
        flash(f"Erro ao restaurar backup: {str(e)}", "danger")

    return redirect(url_for("dashboard.dashboard"))
