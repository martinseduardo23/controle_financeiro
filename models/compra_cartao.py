from database import db
from datetime import datetime


class CompraCartao(db.Model):
    __tablename__ = "compras_cartao"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    descricao = db.Column(
        db.String(200),
        nullable=False
    )

    valor_total = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    data_compra = db.Column(
        db.Date,
        nullable=False
    )

    parcelas = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    cartao_id = db.Column(
        db.Integer,
        db.ForeignKey("cartoes.id"),
        nullable=False
    )

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey("categorias.id"),
        nullable=False
    )

    observacao = db.Column(
        db.Text,
        nullable=True
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    cartao = db.relationship(
        "Cartao",
        backref="compras"
    )

    categoria = db.relationship(
        "Categoria",
        backref="compras_cartao"
    )

    def valor_parcela(self):
        if not self.parcelas:
            return float(self.valor_total or 0)

        return (
            float(self.valor_total or 0)
            / self.parcelas
        )

    def __repr__(self):
        return f"<CompraCartao {self.descricao}>"