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


def obter_db_encryption_key():
    """
    Retorna a chave de criptografia AES-256 do banco de dados.
    1. Verifica a variável de ambiente DB_ENCRYPTION_KEY (.env)
    2. Se ausente, busca em data/.db_key
    3. Se não existir, gera e persiste uma chave forte de 64 caracteres hexadecimais.
    """
    env_key = os.environ.get("DB_ENCRYPTION_KEY", "").strip()
    if env_key:
        return env_key

    data_dir = os.path.join(BASE_DIR, "data")
    key_file = os.path.join(data_dir, ".db_key")

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


def configurar_banco_dados(base_dir: str) -> str:
    """
    Configura a URI do SQLAlchemy com criptografia de banco em repouso (SQLCipher AES-256).
    Se estiver em modo de teste (TESTING=1), utiliza um banco isolado para não afetar os dados reais.
    """
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    if os.environ.get("TESTING") == "1" or os.environ.get("FLASK_ENV") == "testing":
        test_db = os.path.join(data_dir, "test_isolated.db")
        return "sqlite:///" + test_db

    db_path = os.path.join(data_dir, "financeiro.db")

    try:
        import sqlcipher3
        import sys
        sys.modules['pysqlcipher3'] = sqlcipher3
        sys.modules['pysqlcipher3.dbapi2'] = sqlcipher3
        tem_sqlcipher = True
    except ImportError:
        tem_sqlcipher = False

    if not tem_sqlcipher:
        return "sqlite:///" + db_path

    chave = obter_db_encryption_key()

    # Verifica se o banco existente é SQLite padrão aberto e necessita criptografia
    if os.path.exists(db_path):
        try:
            with open(db_path, "rb") as f:
                header = f.read(16)
            if header == b"SQLite format 3\x00":
                import shutil
                backup_path = db_path + ".backup_legivel"
                temp_enc_path = db_path + ".enc_temp"
                if os.path.exists(temp_enc_path):
                    os.remove(temp_enc_path)

                shutil.copy2(db_path, backup_path)

                conn = sqlcipher3.connect(db_path)
                escaped_key = chave.replace("'", "''")
                conn.execute(f"ATTACH DATABASE '{temp_enc_path}' AS encrypted KEY '{escaped_key}'")
                conn.execute("SELECT sqlcipher_export('encrypted')")
                conn.execute("DETACH DATABASE encrypted")
                conn.close()

                os.remove(db_path)
                shutil.move(temp_enc_path, db_path)
        except Exception:
            pass

    import urllib.parse
    encoded_key = urllib.parse.quote_plus(chave)
    clean_path = db_path.replace("\\", "/")
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path

    return f"sqlite+pysqlcipher://:{encoded_key}@{clean_path}"


class Config:
    SECRET_KEY = obter_secret_key()
    DB_ENCRYPTION_KEY = obter_db_encryption_key()
    SQLALCHEMY_DATABASE_URI = configurar_banco_dados(BASE_DIR)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MERCADO_PAGO_ACCESS_TOKEN = obter_token_mercadopago()

    # Segurança de Sessão e Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Ativa Secure se configurado ou se em produção HTTPS
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
