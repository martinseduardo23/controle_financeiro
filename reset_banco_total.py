#!/usr/bin/env python3
"""
Script utilitário para resetar completamente o banco de dados do zero.
Apaga todas as tabelas, recria tudo do zero e inicializa os usuários
'admin' e 'eduardo' com a senha 'Himura23@@##' e suas contas/categorias padrão.
"""

import os
import sys

from app import app
from database import db
from app import inicializar_dados


def resetar_banco_completo():
    print("[*] Iniciando reset completo do banco de dados...")
    with app.app_context():
        print("[*] Apagando todas as tabelas (db.drop_all())...")
        db.drop_all()
        print("[*] Recriando todas as tabelas (db.create_all())...")
        db.create_all()
        print("[*] Inicializando dados iniciais (admin e eduardo com senha Himura23@@##)...")
        inicializar_dados()
        print("[OK] Banco de dados resetado com sucesso do zero!")


if __name__ == "__main__":
    resetar_banco_completo()
