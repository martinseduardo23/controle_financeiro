import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def obter_token_mercadopago():
    env_token = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token
    token_file = os.path.join(BASE_DIR, "data", "mp_token.txt")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""


class Config:
    SECRET_KEY = "financeiro-chave-desenvolvimento"

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
