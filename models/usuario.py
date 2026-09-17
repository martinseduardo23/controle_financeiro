import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from database import db


def gerar_webhook_token():
    return secrets.token_hex(16)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    webhook_token = db.Column(db.String(64), unique=True, nullable=False, default=gerar_webhook_token)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    contas = db.relationship("Conta", back_populates="usuario", cascade="all, delete-orphan")
    categorias = db.relationship("Categoria", back_populates="usuario", cascade="all, delete-orphan")
    lancamentos = db.relationship("Lancamento", back_populates="usuario", cascade="all, delete-orphan")
    cartoes = db.relationship("Cartao", back_populates="usuario", cascade="all, delete-orphan")
    metas = db.relationship("Meta", back_populates="usuario", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Usuario {self.username}>"
