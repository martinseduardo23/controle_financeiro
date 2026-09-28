import os
import shutil
import sqlite3
from datetime import datetime
from flask import Blueprint, send_file, request, redirect, url_for, flash, session
from config import BASE_DIR
from database import db
from services.audit_service import registrar_auditoria

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/backup/download", methods=["GET"])
def download():
    usuario_id = session.get("usuario_id")
    if not session.get("is_admin"):
        registrar_auditoria("backup.download_denied", usuario_id=usuario_id, status="falha")
        flash("Apenas administradores podem fazer download do banco de dados.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    db_path = os.path.join(BASE_DIR, "data", "financeiro.db")
    if not os.path.exists(db_path):
        flash("Arquivo de banco de dados não encontrado.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    registrar_auditoria("backup.download_success", usuario_id=usuario_id)
    nome_arquivo = f"financeiro_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(
        db_path,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/x-sqlite3"
    )


@backup_bp.route("/backup/restaurar", methods=["POST"])
def restaurar():
    usuario_id = session.get("usuario_id")
    if not session.get("is_admin"):
        registrar_auditoria("backup.restore_denied", usuario_id=usuario_id, status="falha")
        flash("Apenas administradores podem restaurar o banco de dados.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    arquivo = request.files.get("arquivo_db")
    if not arquivo or not arquivo.filename:
        flash("Nenhum arquivo selecionado para restauração.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    # 1. Validação de extensão
    extensoes_permitidas = (".db", ".sqlite", ".sqlite3")
    if not any(arquivo.filename.lower().endswith(ext) for ext in extensoes_permitidas):
        flash("O arquivo deve ser um banco de dados SQLite (.db ou .sqlite).", "danger")
        return redirect(url_for("dashboard.dashboard"))

    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    temp_path = os.path.join(data_dir, f"temp_restore_{int(datetime.now().timestamp())}.db")
    db_path = os.path.join(data_dir, "financeiro.db")
    backup_seguranca = os.path.join(data_dir, f"financeiro_antes_restauracao_{int(datetime.now().timestamp())}.db")

    try:
        # Salva primeiro no caminho temporário para testes de integridade
        arquivo.save(temp_path)

        # 2. Validação da Assinatura Mágica do Cabeçalho SQLite (16 bytes)
        with open(temp_path, "rb") as f:
            header = f.read(16)
            if not header.startswith(b"SQLite format 3\000"):
                os.remove(temp_path)
                registrar_auditoria("backup.restore_invalid_header", usuario_id=usuario_id, status="falha")
                flash("O arquivo enviado não é um banco de dados SQLite válido (cabeçalho inválido).", "danger")
                return redirect(url_for("dashboard.dashboard"))

        # 3. Teste de Integridade Estrutural e Schema SQLite
        conn = sqlite3.connect(temp_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            resultado = cursor.fetchone()
            if not resultado or resultado[0] != "ok":
                conn.close()
                os.remove(temp_path)
                registrar_auditoria("backup.restore_corrupt", usuario_id=usuario_id, status="falha")
                flash("O arquivo enviado está corrompido ou danificado (falha no integrity_check).", "danger")
                return redirect(url_for("dashboard.dashboard"))

            # Checa se possui ao menos a tabela de usuários
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios';")
            if not cursor.fetchone():
                conn.close()
                os.remove(temp_path)
                registrar_auditoria("backup.restore_missing_tables", usuario_id=usuario_id, status="falha")
                flash("O arquivo restaurado não contém o esquema esperado do sistema financeiro.", "danger")
                return redirect(url_for("dashboard.dashboard"))
        finally:
            conn.close()

        # 4. Aplicação Segura com Backup Preventivo
        db.session.remove()

        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_seguranca)

        shutil.move(temp_path, db_path)

        registrar_auditoria("backup.restore_success", usuario_id=usuario_id, detalhes={"origem": arquivo.filename})
        flash("Backup restaurado e verificado com sucesso! Seus dados foram carregados.", "success")
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        registrar_auditoria("backup.restore_error", usuario_id=usuario_id, status="erro", detalhes={"erro": str(e)})
        flash("Ocorreu um erro ao restaurar o banco de dados. A integridade anterior foi preservada.", "danger")

    return redirect(url_for("dashboard.dashboard"))
