import json
from flask import request, g
from database import db
from models.log_auditoria import LogAuditoria


def registrar_auditoria(acao: str, usuario_id: int = None, status: str = "sucesso", detalhes: dict = None):
    """
    Registra um evento de segurança ou ação crítica na tabela de auditoria.
    Garante que falhas no log não impeçam a execução da regra de negócio.
    """
    try:
        ip = "127.0.0.1"
        user_agent = "Internal"
        request_id = getattr(g, "request_id", None)

        # Se executado dentro de um contexto de requisição HTTP Flask
        try:
            if request:
                ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "127.0.0.1"
                user_agent = (request.headers.get("User-Agent") or "")[:250]
        except RuntimeError:
            pass

        detalhes_str = json.dumps(detalhes, ensure_ascii=False) if isinstance(detalhes, dict) else (str(detalhes) if detalhes else None)

        log = LogAuditoria(
            usuario_id=usuario_id,
            acao=acao,
            status=status,
            ip_origem=ip[:45],
            user_agent=user_agent[:255],
            detalhes=detalhes_str,
            request_id=request_id
        )

        db.session.add(log)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
