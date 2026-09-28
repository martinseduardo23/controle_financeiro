import sys
import os
import traceback

# =========================================================
# CONFIGURAÇÃO WSGI PARA CPANEL (PHUSION PASSENGER)
# =========================================================

# Adiciona o diretório base da aplicação ao sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Garante que a pasta data/ exista com permissão de escrita
data_dir = os.path.join(APP_DIR, "data")
try:
    os.makedirs(data_dir, exist_ok=True)
except Exception:
    pass

try:
    # O cPanel / CloudLinux Passenger espera uma variável chamada 'application'
    from app import app as application
except Exception as e:
    err_traceback = traceback.format_exc()

    # Grava o erro em arquivo de log local para diagnóstico
    try:
        with open(os.path.join(APP_DIR, "error_startup.log"), "w", encoding="utf-8") as f:
            f.write(err_traceback)
    except Exception:
        pass

    # Exibe o erro formatado diretamente na tela se o servidor chamar application
    def application(environ, start_response):
        status = '500 Internal Server Error'
        response_headers = [('Content-Type', 'text/plain; charset=utf-8')]
        start_response(status, response_headers)
        return [f"ERRO DE INICIALIZACAO NO SERVIDOR:\n\n{err_traceback}".encode('utf-8')]
