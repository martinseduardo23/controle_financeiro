from database import db
from datetime import datetime, date, timedelta


class Meta(db.Model):

    __tablename__ = "metas"

    # =====================================================
    # IDENTIFICAÇÃO
    # =====================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # =====================================================
    # INFORMAÇÕES
    # =====================================================

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    descricao = db.Column(
        db.Text,
        nullable=True
    )

    # =====================================================
    # VALORES
    # =====================================================

    valor_meta = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    valor_atual = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    # =====================================================
    # RENDIMENTO
    # =====================================================

    rendimento_diario = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=5.68
    )

    data_inicio_rendimento = db.Column(
        db.Date,
        nullable=True
    )

    # =====================================================
    # PRAZO
    # =====================================================

    prazo = db.Column(
        db.Date,
        nullable=True
    )

    # =====================================================
    # CONTROLE
    # =====================================================

    ativa = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    criada_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # =====================================================
    # APORTES
    # =====================================================

    aportes = db.relationship(
        "MetaAporte",
        back_populates="meta",
        cascade="all, delete-orphan",
        order_by="MetaAporte.data.desc()"
    )

    # =====================================================
    # FERIADOS NACIONAIS COM CACHE
    # =====================================================

    _cache_feriados = {}

    @classmethod
    def feriados_ano(cls, ano):
        if ano not in cls._cache_feriados:
            feriados = {
                date(ano, 1, 1),    # Confraternização Universal
                date(ano, 4, 21),   # Tiradentes
                date(ano, 5, 1),    # Dia do Trabalho
                date(ano, 9, 7),    # Independência
                date(ano, 10, 12),  # Nossa Senhora Aparecida
                date(ano, 11, 2),   # Finados
                date(ano, 11, 15),  # Proclamação da República
                date(ano, 11, 20),  # Consciência Negra
                date(ano, 12, 25),  # Natal
            }
            pascoa = cls.calcular_pascoa(ano)
            # Sexta-feira Santa
            feriados.add(pascoa - timedelta(days=2))
            cls._cache_feriados[ano] = feriados

        return cls._cache_feriados[ano]

    # =====================================================
    # CÁLCULO DA PÁSCOA
    # =====================================================

    @staticmethod
    def calcular_pascoa(ano):

        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3

        h = (
            19 * a
            + b
            - d
            - g
            + 15
        ) % 30

        i = c // 4
        k = c % 4

        l = (
            32
            + 2 * e
            + 2 * i
            - h
            - k
        ) % 7

        m = (
            a
            + 11 * h
            + 22 * l
        ) // 451

        mes = (
            h
            + l
            - 7 * m
            + 114
        ) // 31

        dia = (
            (h + l - 7 * m + 114) % 31
        ) + 1

        return date(
            ano,
            mes,
            dia
        )

    # =====================================================
    # DIAS DE RENDIMENTO
    # =====================================================

    def dias_rendimento(
        self,
        data_final=None
    ):

        if not self.data_inicio_rendimento:
            return 0

        inicio = self.data_inicio_rendimento

        if data_final is None:
            data_final = date.today()

        if data_final < inicio:
            return 0

        dias = 0

        data_atual = inicio

        while data_atual <= data_final:

            # Segunda = 0
            # Domingo = 6
            dia_semana = data_atual.weekday()

            # Segunda a sexta
            if dia_semana < 5:

                feriados = self.feriados_ano(
                    data_atual.year
                )

                if data_atual not in feriados:

                    dias += 1

            data_atual += timedelta(
                days=1
            )

        return dias

    # =====================================================
    # RENDIMENTO ACUMULADO
    # =====================================================

    @property
    def rendimento_acumulado(self):

        dias = self.dias_rendimento()

        rendimento = float(
            self.rendimento_diario or 0
        )

        return round(
            dias * rendimento,
            2
        )

    # =====================================================
    # VALOR ESTIMADO
    # =====================================================

    @property
    def valor_estimado(self):

        return round(
            float(
                self.valor_atual or 0
            )
            +
            self.rendimento_acumulado,
            2
        )

    # =====================================================
    # PERCENTUAL
    # =====================================================

    @property
    def percentual(self):

        try:

            if not self.valor_meta:
                return 0

            percentual = (
                self.valor_estimado
                /
                float(self.valor_meta)
                *
                100
            )

            return min(
                max(percentual, 0),
                100
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError
        ):

            return 0

    # =====================================================
    # CONCLUÍDA
    # =====================================================

    @property
    def concluida(self):

        return (
            self.valor_estimado
            >=
            float(
                self.valor_meta or 0
            )
        )

    # =====================================================
    # REPRESENTAÇÃO
    # =====================================================

    def __repr__(self):

        return (
            f"<Meta {self.nome}>"
        )