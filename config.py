import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Carrega arquivo .env se existir
env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Fallback de leitura simples de chave=valor caso dotenv não esteja instalado
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if linha and not linha.startswith("#") and "=" in linha:
                        k, v = linha.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass


def obter_secret_key():
    """
    Retorna SECRET_KEY do ambiente. Se não definida, cria um token seguro
    e persistente em data/.secret_key para manter as sessões ativas entre reinicializações.
    """
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key

    data_dir = os.path.join(BASE_DIR, "data")
    key_file = os.path.join(data_dir, ".secret_key")

    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
                if len(conteudo) >= 16:
                    return conteudo
        except Exception:
            pass

    nova_chave = secrets.token_hex(32)
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(nova_chave)
    except Exception:
        pass

    return nova_chave


def obter_token_mercadopago(chave_secreta: str = None):
    env_token = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token
    token_file = os.path.join(BASE_DIR, "data", "mp_token.txt")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
                if conteudo:
                    from services.security_service import descriptografar_token
                    sec = chave_secreta or os.environ.get("SECRET_KEY") or obter_secret_key()
                    return descriptografar_token(conteudo, sec)
        except Exception:
            return ""
    return ""


class Config:
    SECRET_KEY = obter_secret_key()

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///"
        + os.path.join(
            BASE_DIR,
            "data",
            "financeiro.db"
        )
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MERCADO_PAGO_ACCESS_TOKEN = obter_token_mercadopago()

    # Segurança de Sessão e Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Ativa Secure se configurado ou se em produção HTTPS
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
