import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


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
