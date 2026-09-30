import os
import sys
import json
import unittest
from decimal import Decimal

# Adiciona o diretório raiz ao sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import criar_app
from database import db
from models.usuario import Usuario
from models.log_auditoria import LogAuditoria
from services.security_service import (
    hash_senha,
    verificar_senha,
    criptografar_token,
    descriptografar_token,
    limiter_login,
    gerar_secret_2fa,
    verificar_codigo_totp,
    gerar_codigos_backup,
    RateLimiter
)
import pyotp


class SecurityTestSuite(unittest.TestCase):

    def setUp(self):
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["WTF_CSRF_ENABLED"] = False

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Cria usuário de teste
        self.user = Usuario(username="sec_user", is_admin=True)
        self.user.set_password("SenhaForte123!")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ---------------------------------------------------------
    # TESTE 1: Senhas em Argon2id e Auto-Upgrade
    # ---------------------------------------------------------
    def test_01_argon2id_password_hashing(self):
        h = hash_senha("SegurancaMaxima2026")
        self.assertTrue(h.startswith("$argon2id$"), f"Esperado hash Argon2id, obtido: {h}")

        valido, precisa_rehash = verificar_senha("SegurancaMaxima2026", h)
        self.assertTrue(valido)
        self.assertFalse(precisa_rehash)

        # Senha incorreta
        invalido, _ = verificar_senha("SenhaErrada", h)
        self.assertFalse(invalido)

    # ---------------------------------------------------------
    # TESTE 2: Criptografia de Tokens em Repouso
    # ---------------------------------------------------------
    def test_02_token_encryption_at_rest(self):
        secret_key = "chave_super_secreta_de_teste"
        token_original = "APP_USR-1234567890-abcdef-token_secreto"

        cifrado = criptografar_token(token_original, secret_key)
        self.assertNotEqual(cifrado, token_original)
        self.assertNotIn("APP_USR", cifrado)

        recuperado = descriptografar_token(cifrado, secret_key)
        self.assertEqual(recuperado, token_original)

    # ---------------------------------------------------------
    # TESTE 3: Rate Limiting & Proteção contra Força Bruta
    # ---------------------------------------------------------
    def test_03_brute_force_rate_limiting(self):
        limiter = RateLimiter()
        chave = "ip:192.168.100.50"

        # 4 falhas não devem bloquear
        for _ in range(4):
            bloqueou = limiter.registrar_falha(chave, max_tentativas=5)
            self.assertFalse(bloqueou)

        bloqueado, _ = limiter.esta_bloqueado(chave)
        self.assertFalse(bloqueado)

        # 5ª falha ativa o bloqueio
        bloqueou = limiter.registrar_falha(chave, max_tentativas=5)
        self.assertTrue(bloqueou)

        bloqueado, seg = limiter.esta_bloqueado(chave)
        self.assertTrue(bloqueado)
        self.assertGreater(seg, 0)

        # Limpeza no sucesso
        limiter.limpar_sucesso(chave)
        bloqueado, _ = limiter.esta_bloqueado(chave)
        self.assertFalse(bloqueado)

    # ---------------------------------------------------------
    # TESTE 4: MFA / 2FA (TOTP RFC 6238) e Backup Codes
    # ---------------------------------------------------------
    def test_04_mfa_totp_and_backup_codes(self):
        secret = gerar_secret_2fa()
        self.assertEqual(len(secret), 32)

        totp = pyotp.TOTP(secret)
        codigo_correto = totp.now()

        # Validação do código TOTP
        self.assertTrue(verificar_codigo_totp(secret, codigo_correto))
        self.assertFalse(verificar_codigo_totp(secret, "000000"))

        # Habilita 2FA no usuário com códigos de backup
        backup_codes = gerar_codigos_backup(5)
        self.user.habilitar_2fa(secret, backup_codes)
        db.session.commit()

        self.assertTrue(self.user.is_2fa_enabled)
        self.assertEqual(len(self.user.obter_codigos_backup()), 5)

        # Consumo de código de backup (uso único)
        codigo_teste = backup_codes[0]
        consumido = self.user.consumir_codigo_backup(codigo_teste)
        self.assertTrue(consumido)
        self.assertEqual(len(self.user.obter_codigos_backup()), 4)

        # Não pode reutilizar o mesmo código
        reutilizado = self.user.consumir_codigo_backup(codigo_teste)
        self.assertFalse(reutilizado)

    # ---------------------------------------------------------
    # TESTE 5: Webhooks Rejeitam Chamadas sem Token (401/403)
    # ---------------------------------------------------------
    def test_05_webhooks_require_token(self):
        # Webhook Mercado Pago sem token -> 401
        res_mp = self.client.post("/webhook/mercadopago", json={"id": "fake_123"})
        self.assertEqual(res_mp.status_code, 401)
        self.assertIn("obrigatório", res_mp.get_json().get("message", ""))

        # Webhook Mercado Pago com token inexistente -> 403
        res_mp_inv = self.client.post("/webhook/mercadopago/token_falso_xyz", json={"id": "fake_123"})
        self.assertEqual(res_mp_inv.status_code, 403)

        # Webhook Nubank sem token -> 401
        res_nu = self.client.post("/webhooks/nubank", json={"comerciante": "Teste", "valor": "50.00"})
        self.assertEqual(res_nu.status_code, 401)

        # Webhook Nubank com token inexistente -> 403
        res_nu_inv = self.client.post("/webhooks/nubank/token_falso_xyz", json={"comerciante": "Teste", "valor": "50.00"})
        self.assertEqual(res_nu_inv.status_code, 403)

        # Webhook Nubank com token válido do usuário -> 200
        res_nu_ok = self.client.post(f"/webhooks/nubank/{self.user.webhook_token}", json={"comerciante": "Padaria", "valor": "12.50"})
        self.assertEqual(res_nu_ok.status_code, 200)

    # ---------------------------------------------------------
    # TESTE 6: Cabeçalhos de Segurança HTTP e Correlation ID
    # ---------------------------------------------------------
    def test_06_security_headers_and_correlation_id(self):
        res = self.client.get("/login")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("default-src 'self'", res.headers.get("Content-Security-Policy", ""))
        self.assertTrue(bool(res.headers.get("X-Request-ID")))

    # ---------------------------------------------------------
    # TESTE 7: Trilha de Auditoria Gravada
    # ---------------------------------------------------------
    def test_07_audit_logging(self):
        # Tenta login com senha incorreta
        self.client.post("/login", data={"username": "sec_user", "password": "SenhaIncorreta"})

        logs = LogAuditoria.query.filter_by(acao="auth.login_failed").all()
        self.assertGreater(len(logs), 0)
        self.assertIn("sec_user", logs[0].detalhes)

    # ---------------------------------------------------------
    # TESTE 8: Onboarding Obrigatório de 2FA Bloqueia Acesso
    # ---------------------------------------------------------
    def test_08_mandatory_2fa_onboarding_blocks_access(self):
        # 1. Usuário sem 2FA loga com senha correta -> Redirecionado para /perfil/seguranca
        res_login = self.client.post("/login", data={"username": "sec_user", "password": "SenhaForte123!"}, follow_redirects=False)
        self.assertEqual(res_login.status_code, 302)
        self.assertIn("/perfil/seguranca", res_login.location)

        # 2. Tentativa de acessar o Dashboard sem 2FA ativado é barrada pelo middleware
        res_dash = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn("/perfil/seguranca", res_dash.location)

        # 3. Acesso à página de segurança/2FA é permitido e exibe banner obrigatório
        res_sec = self.client.get("/perfil/seguranca")
        self.assertEqual(res_sec.status_code, 200)
        self.assertIn("Configuração Obrigatória de Segurança", res_sec.get_data(as_text=True))

        # 4. Ativa o 2FA usando o segredo temporário gerado na sessão
        with self.client.session_transaction() as sess:
            secret_temp = sess.get("temp_totp_secret")
        self.assertIsNotNone(secret_temp)

        codigo_totp = pyotp.TOTP(secret_temp).now()
        res_ativar = self.client.post("/perfil/2fa/ativar", data={"codigo_verificacao": codigo_totp}, follow_redirects=False)
        self.assertEqual(res_ativar.status_code, 302)

        # 5. Verifica se o usuário agora tem 2FA habilitado no banco
        db.session.refresh(self.user)
        self.assertTrue(self.user.is_2fa_enabled)

        # 6. Conclui o onboarding e navega até o dashboard
        res_concluir = self.client.get("/perfil/2fa/concluir", follow_redirects=False)
        self.assertEqual(res_concluir.status_code, 302)
        self.assertIn("/dashboard", res_concluir.location)

        # 7. Dashboard agora responde com 200 OK sem bloqueio
        res_dash_ok = self.client.get("/dashboard")
        self.assertEqual(res_dash_ok.status_code, 200)

    # ---------------------------------------------------------
    # TESTE 9: Controle Granular de Permissões de Módulos
    # ---------------------------------------------------------
    def test_09_permissoes_modulos(self):
        from services.usuario_service import criar_usuario
        # Cria usuário restrito (sem Mercado Pago, sem InfinitePay, sem Nubank)
        u_restrito = criar_usuario(
            username="user_restrito",
            password="SenhaValida123!",
            is_admin=False,
            acesso_mercadopago=False,
            acesso_infinitepay=False,
            acesso_nubank=False
        )
        u_restrito.is_2fa_enabled = True
        db.session.commit()

        # Simula sessão logada como o usuário restrito
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = u_restrito.id
            sess["username"] = u_restrito.username
            sess["is_admin"] = False
            sess["autenticado_2fa"] = True

        # Tenta acessar Mercado Pago -> bloqueado e redirecionado para dashboard
        res_mp = self.client.get("/integracoes/mercadopago", follow_redirects=False)
        self.assertEqual(res_mp.status_code, 302)
        self.assertIn("/dashboard", res_mp.location)

        # Tenta acessar Nubank -> bloqueado e redirecionado para dashboard
        res_nu = self.client.get("/integracoes/nubank", follow_redirects=False)
        self.assertEqual(res_nu.status_code, 302)
        self.assertIn("/dashboard", res_nu.location)

        # Tenta acessar InfinitePay -> bloqueado e redirecionado para dashboard
        res_inf = self.client.get("/calculadora/infinitepay", follow_redirects=False)
        self.assertEqual(res_inf.status_code, 302)
        self.assertIn("/dashboard", res_inf.location)

        # Agora loga como Admin e atualiza as permissões desse usuário
        self.user.is_2fa_enabled = True
        db.session.commit()
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = self.user.id
            sess["username"] = self.user.username
            sess["is_admin"] = True
            sess["autenticado_2fa"] = True

        res_update = self.client.post(
            f"/usuarios/{u_restrito.id}/permissoes",
            data={
                "acesso_mercadopago": "1",
                "acesso_infinitepay": "1",
                "acesso_nubank": "1"
            },
            follow_redirects=False
        )
        self.assertEqual(res_update.status_code, 302)

        # Verifica no banco se as permissões foram atualizadas
        db.session.refresh(u_restrito)
        self.assertTrue(u_restrito.acesso_mercadopago)
        self.assertTrue(u_restrito.acesso_infinitepay)
        self.assertTrue(u_restrito.acesso_nubank)


if __name__ == "__main__":
    unittest.main()

