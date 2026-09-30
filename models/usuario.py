import json
import secrets
from datetime import datetime
from database import db
from services.security_service import hash_senha, verificar_senha, comparar_em_tempo_constante


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

    # Campos de Autenticação Multifator (MFA / 2FA)
    totp_secret = db.Column(db.String(64), nullable=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    backup_codes = db.Column(db.Text, nullable=True)  # Lista JSON de códigos de emergência

    # Permissões de Módulos e Integrações
    acesso_mercadopago = db.Column(db.Boolean, default=True, nullable=False)
    acesso_infinitepay = db.Column(db.Boolean, default=True, nullable=False)
    acesso_nubank = db.Column(db.Boolean, default=True, nullable=False)

    # Relacionamentos
    contas = db.relationship("Conta", back_populates="usuario", cascade="all, delete-orphan")
    categorias = db.relationship("Categoria", back_populates="usuario", cascade="all, delete-orphan")
    lancamentos = db.relationship("Lancamento", back_populates="usuario", cascade="all, delete-orphan")
    cartoes = db.relationship("Cartao", back_populates="usuario", cascade="all, delete-orphan")
    metas = db.relationship("Meta", back_populates="usuario", cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Aplica hashing utilizando Argon2id."""
        self.password_hash = hash_senha(password)

    def check_password(self, password: str) -> bool:
        """
        Valida a senha fornecida. Caso o hash armazenado seja de algoritmo legado,
        faz o upgrade transparente para Argon2id.
        """
        if not self.password_hash:
            return False
        valido, precisa_rehash = verificar_senha(password, self.password_hash)
        if valido and precisa_rehash:
            try:
                self.set_password(password)
                db.session.commit()
            except Exception:
                db.session.rollback()
        return valido

    def habilitar_2fa(self, secret: str, codigos_backup: list):
        """Ativa o 2FA e armazena os códigos de backup."""
        self.totp_secret = secret
        self.is_2fa_enabled = True
        self.backup_codes = json.dumps(codigos_backup)

    def desabilitar_2fa(self):
        """Desativa o 2FA e remove o segredo e códigos de backup."""
        self.totp_secret = None
        self.is_2fa_enabled = False
        self.backup_codes = None

    def obter_codigos_backup(self) -> list:
        if not self.backup_codes:
            return []
        try:
            return json.loads(self.backup_codes)
        except Exception:
            return []

    def consumir_codigo_backup(self, codigo_informado: str) -> bool:
        """Valida e consome um código de backup (uso único)."""
        codigos = self.obter_codigos_backup()
        codigo_limpo = str(codigo_informado).strip().upper()
        for idx, cod in enumerate(codigos):
            if comparar_em_tempo_constante(cod, codigo_limpo):
                # Remove o código usado
                codigos.pop(idx)
                self.backup_codes = json.dumps(codigos)
                db.session.commit()
                return True
        return False

    def __repr__(self):
        return f"<Usuario {self.username}>"
