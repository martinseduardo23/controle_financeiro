from database import db
from datetime import datetime


class MetaAporte(db.Model):

    __tablename__ = "metas_aportes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    meta_id = db.Column(
        db.Integer,
        db.ForeignKey("metas.id"),
        nullable=False
    )

    conta_id = db.Column(
        db.Integer,
        db.ForeignKey("contas.id"),
        nullable=False
    )

    lancamento_id = db.Column(
        db.Integer,
        db.ForeignKey("lancamentos.id"),
        nullable=False
    )

    valor = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    data = db.Column(
        db.Date,
        nullable=False
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    meta = db.relationship(
        "Meta",
        back_populates="aportes"
    )

    conta = db.relationship(
        "Conta"
    )

    lancamento = db.relationship(
        "Lancamento"
    )

    def __repr__(self):

        return (
            f"<MetaAporte "
            f"{self.valor}>"
        )