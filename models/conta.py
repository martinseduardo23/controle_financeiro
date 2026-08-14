from database import db
from datetime import datetime


class Conta(db.Model):
    __tablename__ = "contas"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    tipo = db.Column(
        db.String(50),
        nullable=False,
        default="Conta"
    )

    saldo_inicial = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    ativa = db.Column(
        db.Boolean,
        default=True
    )

    criada_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    lancamentos = db.relationship(
        "Lancamento",
        back_populates="conta",
        lazy=True
    )

    def saldo_atual(self):
        saldo = float(self.saldo_inicial or 0)

        for lancamento in self.lancamentos:
            if lancamento.status != "pago":
                continue

            valor = float(lancamento.valor or 0)

            if lancamento.tipo == "receita":
                saldo += valor
            else:
                saldo -= valor

        return saldo

    def __repr__(self):
        return f"<Conta {self.nome}>"
