from database import db


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    tipo = db.Column(
        db.String(20),
        nullable=False
    )

    ativa = db.Column(
        db.Boolean,
        default=True
    )

    lancamentos = db.relationship(
        "Lancamento",
        back_populates="categoria",
        lazy=True
    )

    def total_movimentado(self):
        return sum(
            float(lancamento.valor or 0)
            for lancamento in self.lancamentos
        )

    def quantidade_lancamentos(self):
        return len(self.lancamentos)

    def __repr__(self):
        return f"<Categoria {self.nome}>"
