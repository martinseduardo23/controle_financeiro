from datetime import datetime
from database import db


class LogAuditoria(db.Model):
    __tablename__ = "logs_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    acao = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(20), default="sucesso", nullable=False)
    ip_origem = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    detalhes = db.Column(db.Text, nullable=True)
    request_id = db.Column(db.String(36), nullable=True, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relacionamento opcional com usuário
    usuario = db.relationship("Usuario", backref=db.backref("logs_auditoria", lazy="dynamic"))

    def __repr__(self):
        return f"<LogAuditoria {self.acao} - {self.status} [{self.criado_em}]>"
