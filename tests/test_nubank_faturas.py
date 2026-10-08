import os
os.environ["TESTING"] = "1"
import unittest
from datetime import date
from decimal import Decimal
import io

from app import app
from database import db
from models import Usuario, Cartao, CompraCartao, ParcelaCartao, FaturaCartao, Categoria, Conta
from services.nubank_service import (
    parsear_csv_nubank,
    importar_lote_nubank,
    extrair_info_parcela,
    inferir_categoria_por_texto,
    parse_data_flexivel,
    parse_valor_flexivel
)
from services.faturas_cartao import obter_fatura, vincular_parcela, recalcular_valor_fatura


class TestNubankFaturas(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Cria ou obtém usuário de teste
        self.usuario = Usuario.query.filter_by(username="test_nubank_user").first()
        if not self.usuario:
            self.usuario = Usuario(
                username="test_nubank_user",
                is_admin=True,
                is_2fa_enabled=True
            )
            self.usuario.set_password("SenhaForte123!@#")
            db.session.add(self.usuario)
            db.session.commit()

        # Limpa dados anteriores desse usuário de teste
        ParcelaCartao.query.filter(
            ParcelaCartao.compra_id.in_(
                db.session.query(CompraCartao.id).filter_by(usuario_id=self.usuario.id)
            )
        ).delete(synchronize_session=False)
        CompraCartao.query.filter_by(usuario_id=self.usuario.id).delete()
        FaturaCartao.query.filter(
            FaturaCartao.cartao_id.in_(
                db.session.query(Cartao.id).filter_by(usuario_id=self.usuario.id)
            )
        ).delete(synchronize_session=False)
        Cartao.query.filter_by(usuario_id=self.usuario.id).delete()
        db.session.commit()

        # Cria dois cartões de teste para verificar a seleção
        self.cartao1 = Cartao(
            usuario_id=self.usuario.id,
            nome="Nubank Principal",
            banco="Nubank",
            ultimos_digitos="1234",
            limite=Decimal("4000.00"),
            dia_fechamento=20,
            dia_vencimento=27,
            ativo=True
        )
        self.cartao2 = Cartao(
            usuario_id=self.usuario.id,
            nome="Nubank Ultravioleta",
            banco="Nubank",
            ultimos_digitos="5678",
            limite=Decimal("15000.00"),
            dia_fechamento=1,
            dia_vencimento=8,
            ativo=True
        )
        db.session.add_all([self.cartao1, self.cartao2])
        db.session.commit()

    def tearDown(self):
        # Limpa registros criados
        ParcelaCartao.query.filter(
            ParcelaCartao.compra_id.in_(
                db.session.query(CompraCartao.id).filter_by(usuario_id=self.usuario.id)
            )
        ).delete(synchronize_session=False)
        CompraCartao.query.filter_by(usuario_id=self.usuario.id).delete()
        FaturaCartao.query.filter(
            FaturaCartao.cartao_id.in_(
                db.session.query(Cartao.id).filter_by(usuario_id=self.usuario.id)
            )
        ).delete(synchronize_session=False)
        Cartao.query.filter_by(usuario_id=self.usuario.id).delete()
        db.session.commit()
        self.ctx.pop()

    def test_parsear_csv_variacoes_delimitador_e_datas(self):
        """Testa o parser com delimitadores vírgula e ponto-e-vírgula e datas brasileiras e ISO."""
        csv_virgula = """date,category,title,amount
2026-05-10,transporte,Uber *Trip,25.50
2026-05-11,alimentação,Padaria Central,15.00
2026-05-12,pagamento,Pagamento recebido,-1000.00
"""
        tipo, transacoes = parsear_csv_nubank(csv_virgula)
        self.assertEqual(tipo, "cartao")
        self.assertEqual(len(transacoes), 2)  # 'Pagamento recebido' deve ser ignorado
        self.assertEqual(transacoes[0]["descricao"], "Uber *Trip")
        self.assertEqual(transacoes[0]["valor"], Decimal("25.50"))
        self.assertEqual(transacoes[0]["data"], date(2026, 5, 10))

        # CSV com ponto-e-vírgula e data brasileira
        csv_ponto_virgula = """data;categoria;titulo;valor
15/05/2026;alimentação;iFood *Restaurante;89,90
16/05/2026;outros;Amazon - Parcela 2/5;120,00
17/05/2026;pagamento;Pagamento de fatura;-500,00
"""
        tipo_pv, trans_pv = parsear_csv_nubank(csv_ponto_virgula)
        self.assertEqual(tipo_pv, "cartao")
        self.assertEqual(len(trans_pv), 2)
        self.assertEqual(trans_pv[0]["valor"], Decimal("89.90"))
        self.assertEqual(trans_pv[0]["data"], date(2026, 5, 15))
        self.assertEqual(trans_pv[1]["num_parcela"], 2)
        self.assertEqual(trans_pv[1]["total_parcelas"], 5)

    def test_extrair_info_parcela(self):
        """Testa a extração inteligente de número de parcela da descrição."""
        desc, n, tot = extrair_info_parcela("Amazon - Parcela 3/10")
        self.assertEqual(n, 3)
        self.assertEqual(tot, 10)

        desc, n, tot = extrair_info_parcela("Mercado Livre (02/06)")
        self.assertEqual(n, 2)
        self.assertEqual(tot, 6)

        desc, n, tot = extrair_info_parcela("Cafeteria Gourmet")
        self.assertEqual(n, 1)
        self.assertEqual(tot, 1)

    def test_inferir_categoria(self):
        """Testa o reconhecimento automático de categorias comuns."""
        self.assertEqual(inferir_categoria_por_texto("Uber *Trip BR"), "Transporte")
        self.assertEqual(inferir_categoria_por_texto("iFood Brasil"), "Alimentação")
        self.assertEqual(inferir_categoria_por_texto("Netflix.com"), "Lazer")
        self.assertEqual(inferir_categoria_por_texto("Droga Raia 102"), "Saúde")
        self.assertEqual(inferir_categoria_por_texto("Amazon Mktp"), "Compras")

    def test_calculo_vencimento_mesmo_mes_vs_proximo(self):
        """Garante que se dia_vencimento >= dia_fechamento, vencimento ocorre no mesmo mês."""
        # cartao1: fecha 20, vence 27 (ambos em maio/2026)
        fatura1 = obter_fatura(self.cartao1, 2026, 5)
        self.assertEqual(fatura1.data_fechamento, date(2026, 5, 20))
        self.assertEqual(fatura1.data_vencimento, date(2026, 5, 27))

        # Cartão que fecha 25 e vence dia 5 do mês seguinte
        cartao_mes_seguinte = Cartao(
            usuario_id=self.usuario.id,
            nome="Cartão Fecha Fim Mês",
            banco="Inter",
            limite=Decimal("2000.00"),
            dia_fechamento=25,
            dia_vencimento=5,
            ativo=True
        )
        db.session.add(cartao_mes_seguinte)
        db.session.flush()

        fatura2 = obter_fatura(cartao_mes_seguinte, 2026, 5)
        self.assertEqual(fatura2.data_fechamento, date(2026, 5, 25))
        self.assertEqual(fatura2.data_vencimento, date(2026, 6, 5))

    def test_importar_para_cartao_escolhido(self):
        """Garante que a importação respeita o cartao_id selecionado pelo usuário."""
        transacoes = [
            {
                "data": date(2026, 10, 5),
                "descricao": "Posto Shell Gasolina",
                "valor": Decimal("150.00"),
                "categoria": "Transporte",
                "tipo": "despesa",
                "num_parcela": 1,
                "total_parcelas": 1
            },
            {
                "data": date(2026, 10, 6),
                "descricao": "Supermercado Pão de Açúcar",
                "valor": Decimal("230.50"),
                "categoria": "Alimentação",
                "tipo": "despesa",
                "num_parcela": 1,
                "total_parcelas": 1
            }
        ]

        # Importa para o cartao2 (Nubank Ultravioleta)
        res = importar_lote_nubank(
            transacoes,
            destino="cartao",
            usuario_id=self.usuario.id,
            cartao_id=self.cartao2.id
        )

        self.assertEqual(res["importados"], 2)
        self.assertEqual(res["cartao_id"], self.cartao2.id)

        # Verifica se as compras foram associadas ao cartao2
        compras_c2 = CompraCartao.query.filter_by(cartao_id=self.cartao2.id, usuario_id=self.usuario.id).all()
        self.assertEqual(len(compras_c2), 2)

        # O cartao1 não deve conter compras
        compras_c1 = CompraCartao.query.filter_by(cartao_id=self.cartao1.id, usuario_id=self.usuario.id).all()
        self.assertEqual(len(compras_c1), 0)

        # Verifica se a fatura do cartao2 foi criada e recalculada
        fatura_c2 = FaturaCartao.query.filter_by(cartao_id=self.cartao2.id).first()
        self.assertIsNotNone(fatura_c2)
        self.assertEqual(fatura_c2.valor_total, Decimal("380.50"))

    def test_importar_com_fatura_fixa(self):
        """Testa importação garantindo que todas as compras entrem no mês de fatura escolhido."""
        transacoes = [
            {
                "data": date(2026, 8, 25),
                "descricao": "Compra Fim de Agosto",
                "valor": Decimal("100.00"),
                "categoria": "Compras",
                "tipo": "despesa",
                "num_parcela": 1,
                "total_parcelas": 1
            }
        ]

        # Força vincular à fatura de Setembro (2026-09)
        res = importar_lote_nubank(
            transacoes,
            destino="cartao",
            usuario_id=self.usuario.id,
            cartao_id=self.cartao1.id,
            fatura_mes_ano="2026-09"
        )
        self.assertEqual(res["importados"], 1)

        fatura = FaturaCartao.query.filter_by(
            cartao_id=self.cartao1.id,
            ano_referencia=2026,
            mes_referencia=9
        ).first()
        self.assertIsNotNone(fatura)
        self.assertEqual(fatura.valor_total, Decimal("100.00"))

    def test_prevencao_duplicatas_reimportacao(self):
        """Garante que reimportar o mesmo lote não duplica compras no cartão."""
        transacoes = [
            {
                "data": date(2026, 10, 2),
                "descricao": "Almoço Restaurante",
                "valor": Decimal("45.00"),
                "categoria": "Alimentação",
                "tipo": "despesa",
                "num_parcela": 1,
                "total_parcelas": 1
            }
        ]

        # 1ª importação
        res1 = importar_lote_nubank(transacoes, destino="cartao", usuario_id=self.usuario.id, cartao_id=self.cartao1.id)
        self.assertEqual(res1["importados"], 1)
        self.assertEqual(res1["duplicados"], 0)

        # 2ª importação (mesmo arquivo reimportado)
        res2 = importar_lote_nubank(transacoes, destino="cartao", usuario_id=self.usuario.id, cartao_id=self.cartao1.id)
        self.assertEqual(res2["importados"], 0)
        self.assertEqual(res2["duplicados"], 1)


if __name__ == "__main__":
    unittest.main()
