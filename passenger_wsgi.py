import sys
import os

# =========================================================
# CONFIGURAÇÃO WSGI PARA CPANEL (PHUSION PASSENGER)
# =========================================================

# Adiciona o diretório base da aplicação ao sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# O cPanel / CloudLinux Passenger espera uma variável chamada 'application'
from app import app as application
