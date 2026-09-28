import os
import time
import base64
import hmac
import secrets
from typing import Tuple, List, Optional

# Argon2id
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError
    _hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
except ImportError:
    _hasher = None

from werkzeug.security import generate_password_hash, check_password_hash

# Cryptography (Fernet / PBKDF2)
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet = None

# TOTP & QR Code
import pyotp
import qrcode
import qrcode.image.svg


# =========================================================
# 1. HASHING DE SENHA (ARGON2ID + AUTO-UPGRADE)
# =========================================================

def hash_senha(senha: str) -> str:
    """
    Gera hash de senha utilizando Argon2id (padrão OWASP ASVS).
    Caso a biblioteca CFFI não esteja disponível, utiliza werkzeug com scrypt/pbkdf2.
    """
    if _hasher:
        return _hasher.hash(senha)
    return generate_password_hash(senha, method="scrypt")


def verificar_senha(senha: str, hash_armazenado: str) -> Tuple[bool, bool]:
    """
    Verifica se a senha confere com o hash armazenado.
    Retorna uma tupla (senha_valida, precisa_rehash).
    Se o hash armazenado for antigo (scrypt/pbkdf2) e for válido, precisa_rehash será True.
    """
    if not hash_armazenado or not senha:
        return False, False

    # Se já estiver em Argon2id
    if hash_armazenado.startswith("$argon2"):
        if _hasher:
            try:
                valido = _hasher.verify(hash_armazenado, senha)
                precisa_rehash = _hasher.check_needs_rehash(hash_armazenado)
                return valido, precisa_rehash
            except (VerifyMismatchError, VerificationError):
                return False, False
        return False, False

    # Fallback para hashes legados do Werkzeug
    valido = check_password_hash(hash_armazenado, senha)
    # Se válido e temos hasher Argon2id, sinaliza para fazer o upgrade
    precisa_rehash = valido and (_hasher is not None)
    return valido, precisa_rehash


# =========================================================
# 2. CRIPTOGRAFIA DE SEGREDOS EM REPOUSO (FERNET + PBKDF2)
# =========================================================

def _obter_fernet(secret_key: str):
    if not Fernet:
        return None
    # Deriva uma chave de 32 bytes estável a partir da SECRET_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"controle_financeiro_tokens_salt_v1",
        iterations=100_000,
    )
    chave_derivada = base64.urlsafe_b64encode(kdf.derive(secret_key.encode("utf-8")))
    return Fernet(chave_derivada)


def criptografar_token(token: str, secret_key: str) -> str:
    """Criptografa um token sensível antes de persistir em disco ou banco."""
    if not token:
        return ""
    f = _obter_fernet(secret_key)
    if not f:
        # Fallback se cryptography não estiver carregado
        return token
    return f.encrypt(token.encode("utf-8")).decode("utf-8")


def descriptografar_token(token_cifrado: str, secret_key: str) -> str:
    """Descriptografa um token cifrado lido do disco ou banco."""
    if not token_cifrado:
        return ""
    f = _obter_fernet(secret_key)
    if not f:
        return token_cifrado
    try:
        return f.decrypt(token_cifrado.encode("utf-8")).decode("utf-8")
    except Exception:
        # Pode ter sido salvo em texto puro anteriormente (retrocompatibilidade)
        return token_cifrado


# =========================================================
# 3. RATE LIMITING E PROTEÇÃO CONTRA FORÇA BRUTA
# =========================================================

class RateLimiter:
    """
    Rate limiter em memória para proteção de endpoints críticos (/login, webhooks).
    Rastreia tentativas por chave (ex: IP ou IP+Username).
    """
    def __init__(self):
        self._falhas = {}  # key -> list of timestamps
        self._bloqueios = {}  # key -> timestamp until locked

    def registrar_falha(self, chave: str, max_tentativas: int = 5, janela_segundos: int = 300, tempo_bloqueio: int = 600) -> bool:
        """
        Registra uma tentativa falha.
        Retorna True se a chave foi BLOQUEADA como resultado desta falha.
        """
        agora = time.time()
        self._limpar_antigos(chave, agora, janela_segundos)

        tempos = self._falhas.setdefault(chave, [])
        tempos.append(agora)

        if len(tempos) >= max_tentativas:
            self._bloqueios[chave] = agora + tempo_bloqueio
            self._falhas.pop(chave, None)
            return True
        return False

    def esta_bloqueado(self, chave: str) -> Tuple[bool, int]:
        """
        Verifica se a chave está bloqueada.
        Retorna (True, segundos_restantes) ou (False, 0).
        """
        agora = time.time()
        bloqueado_ate = self._bloqueios.get(chave, 0)
        if agora < bloqueado_ate:
            segundos_restantes = int(bloqueado_ate - agora) + 1
            return True, segundos_restantes
        elif chave in self._bloqueios:
            del self._bloqueios[chave]
        return False, 0

    def limpar_sucesso(self, chave: str):
        """Limpa o histórico de falhas após um login ou ação bem-sucedida."""
        self._falhas.pop(chave, None)
        self._bloqueios.pop(chave, None)

    def _limpar_antigos(self, chave: str, agora: float, janela: int):
        if chave in self._falhas:
            limite = agora - janela
            self._falhas[chave] = [t for t in self._falhas[chave] if t >= limite]


limiter_login = RateLimiter()


# =========================================================
# 4. MFA / 2FA (TOTP - RFC 6238)
# =========================================================

def gerar_secret_2fa() -> str:
    """Gera uma chave secreta base32 aleatória de 32 caracteres para TOTP."""
    return pyotp.random_base32()


def gerar_uri_provisionamento(secret: str, username: str, emissor: str = "Controle Financeiro") -> str:
    """Gera o URI compatível com Google Authenticator, Authy, Apple Passwords."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=emissor)


def gerar_qr_code_svg(uri: str) -> str:
    """Gera o QR Code diretamente em formato SVG (puro, sem gravar arquivos)."""
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    return img.to_string(encoding="unicode")


def verificar_codigo_totp(secret: str, codigo: str) -> bool:
    """
    Valida um código de 6 dígitos enviado pelo usuário.
    Usa janela de tolerância de 1 intervalo (30s antes/depois) para compensar desvios de relógio.
    """
    if not secret or not codigo:
        return False
    codigo_limpo = str(codigo).strip().replace(" ", "")
    if len(codigo_limpo) != 6 or not codigo_limpo.isdigit():
        return False
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(codigo_limpo, valid_window=1))


def gerar_codigos_backup(quantidade: int = 5) -> List[str]:
    """Gera códigos de recuperação (Backup Codes) de uso único em formato alfanumérico seguro."""
    return [secrets.token_hex(4).upper() for _ in range(quantidade)]


def comparar_em_tempo_constante(str_a: str, str_b: str) -> bool:
    """Comparação segura contra timing attacks."""
    if not isinstance(str_a, str) or not isinstance(str_b, str):
        return False
    return hmac.compare_digest(str_a.encode("utf-8"), str_b.encode("utf-8"))
