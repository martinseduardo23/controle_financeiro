from database import db
from datetime import datetime


class Lancamento(db.Model):
    __tablename__ = "lancamentos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    descricao = db.Column(
        db.String(200),
        nullable=False
    )

    valor = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    tipo = db.Column(
        db.String(20),
        nullable=False
    )

    data = db.Column(
        db.Date,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pendente"
    )

    observacao = db.Column(
        db.Text,
        nullable=True
    )

    conta_id = db.Column(
        db.Integer,
        db.ForeignKey("contas.id"),
        nullable=False
    )

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey("categorias.id"),
        nullable=False
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    conta = db.relationship(
        "Conta",
        back_populates="lancamentos"
    )

    categoria = db.relationship(
        "Categoria",
        back_populates="lancamentos"
    )

    def __repr__(self):
        return f"<Lancamento {self.descricao}>"
