from database import db
from datetime import datetime


class ParcelaCartao(db.Model):

    __tablename__ = "parcelas_cartao"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    # =====================================================
    # COMPRA
    # =====================================================

    compra_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "compras_cartao.id"
        ),
        nullable=False
    )


    # =====================================================
    # FATURA
    # =====================================================

    fatura_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "faturas_cartao.id"
        ),
        nullable=True
    )


    # =====================================================
    # PARCELAMENTO
    # =====================================================

    numero = db.Column(
        db.Integer,
        nullable=False
    )


    total_parcelas = db.Column(
        db.Integer,
        nullable=False
    )


    # =====================================================
    # VALOR
    # =====================================================

    valor = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )


    # =====================================================
    # DATA PREVISTA
    # =====================================================

    data_prevista = db.Column(
        db.Date,
        nullable=False
    )


    # =====================================================
    # STATUS
    # =====================================================

    status = db.Column(
        db.String(20),
        nullable=False,
        default="aberta"
    )


    pago = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )


    data_pagamento = db.Column(
        db.DateTime,
        nullable=True
    )


    # =====================================================
    # CONTROLE
    # =====================================================

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    # =====================================================
    # RELACIONAMENTO COM COMPRA
    # =====================================================

    compra = db.relationship(
        "CompraCartao",
        back_populates="parcelas_relacionadas"
    )


    # =====================================================
    # RELACIONAMENTO COM FATURA
    # =====================================================

    fatura = db.relationship(
        "FaturaCartao",
        back_populates="parcelas"
    )


    def __repr__(self):

        return (
            f"<ParcelaCartao "
            f"{self.numero}/"
            f"{self.total_parcelas}>"
        )