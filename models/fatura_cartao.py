from database import db
from datetime import datetime


class FaturaCartao(db.Model):

    __tablename__ = "faturas_cartao"

    # =====================================================
    # IDENTIFICAÇÃO
    # =====================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # =====================================================
    # CARTÃO
    # =====================================================

    cartao_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "cartoes.id"
        ),
        nullable=False
    )

    # =====================================================
    # REFERÊNCIA
    # =====================================================

    mes_referencia = db.Column(
        db.Integer,
        nullable=False
    )

    ano_referencia = db.Column(
        db.Integer,
        nullable=False
    )

    # =====================================================
    # DATAS
    # =====================================================

    data_fechamento = db.Column(
        db.Date,
        nullable=False
    )

    data_vencimento = db.Column(
        db.Date,
        nullable=False
    )

    # =====================================================
    # VALOR
    # =====================================================

    valor_total = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = db.Column(
        db.String(20),
        nullable=False,
        default="aberta"
    )

    # =====================================================
    # PAGAMENTO
    # =====================================================

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
    # RELACIONAMENTO COM CARTÃO
    # =====================================================

    cartao = db.relationship(
        "Cartao",
        back_populates="faturas"
    )

    # =====================================================
    # RELACIONAMENTO COM PARCELAS
    # =====================================================

    parcelas = db.relationship(
        "ParcelaCartao",
        back_populates="fatura"
    )

    def __repr__(self):

        return (
            f"<FaturaCartao "
            f"{self.mes_referencia:02d}/"
            f"{self.ano_referencia}>"
        )