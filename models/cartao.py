from database import db
from datetime import datetime


class Cartao(db.Model):

    __tablename__ = "cartoes"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    nome = db.Column(
        db.String(100),
        nullable=False
    )


    banco = db.Column(
        db.String(100),
        nullable=False
    )


    ultimos_digitos = db.Column(
        db.String(4),
        nullable=True
    )


    limite = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )


    dia_fechamento = db.Column(
        db.Integer,
        nullable=False
    )


    dia_vencimento = db.Column(
        db.Integer,
        nullable=False
    )


    ativo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )


    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    # =====================================================
    # FATURAS DO CARTÃO
    # =====================================================

    faturas = db.relationship(
        "FaturaCartao",
        back_populates="cartao",
        cascade="all, delete-orphan"
    )


    def __repr__(self):

        return f"<Cartao {self.nome}>"