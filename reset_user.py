#!/usr/bin/env python3
"""
Script utilitário para resetar ou criar usuários com senha forte e redefinição de 2FA.
Pode ser executado localmente ou no servidor cPanel.

Uso:
    python reset_user.py
    python reset_user.py eduardo Himura23@@##
    python reset_user.py <username> <nova_senha> [--admin]
"""

import sys
from app import app
from database import db
from models import Usuario, Conta, Categoria
from routes.auth import criar_usuario, validar_forca_senha


def resetar_ou_criar_usuario(username="eduardo", nova_senha="Himura23@@##", is_admin=True):
    with app.app_context():
        # Validação de força de senha
        valida, msg = validar_forca_senha(nova_senha)
        if not valida:
            print(f"[!] Erro na validação da senha: {msg}")
            return False

        usuario = Usuario.query.filter(Usuario.username.ilike(username.strip())).first()

        if usuario:
            print(f"[*] Usuário '{usuario.username}' (ID: {usuario.id}) encontrado no banco de dados.")
            # Atualiza senha
            usuario.set_password(nova_senha)
            # Reseta 2FA para que o usuário possa logar e reconfigurar com tranquilidade
            usuario.is_2fa_enabled = False
            usuario.totp_secret = None
            usuario.backup_codes = None
            if is_admin:
                usuario.is_admin = True
            usuario.acesso_mercadopago = True
            usuario.acesso_infinitepay = True
            usuario.acesso_nubank = True
            db.session.commit()
            print(f"[OK] Sucesso! Senha do usuario '{usuario.username}' atualizada e 2FA resetado.")
        else:
            print(f"[*] Usuario '{username}' nao existia. Criando novo usuario...")
            usuario = criar_usuario(
                username=username.strip(),
                password=nova_senha,
                is_admin=is_admin,
                acesso_mercadopago=True,
                acesso_infinitepay=True,
                acesso_nubank=True
            )
            # Garante que 2FA comece desativado ate o primeiro setup
            usuario.is_2fa_enabled = False
            usuario.totp_secret = None
            usuario.backup_codes = None
            db.session.commit()
            print(f"[OK] Sucesso! Usuario '{usuario.username}' (ID: {usuario.id}) criado com a senha informada.")

        # Limpa eventuais bloqueios de tentativas incorretas no limiter
        try:
            from services.security_service import limiter_login
            limiter_login.limpar_sucesso(f"user:{usuario.username.lower()}")
            print(f"[OK] Rate limiter de login limpo para '{usuario.username}'.")
        except Exception:
            pass

        return True


if __name__ == "__main__":
    user_arg = sys.argv[1] if len(sys.argv) > 1 else "eduardo"
    pass_arg = sys.argv[2] if len(sys.argv) > 2 else "Himura23@@##"
    admin_arg = True

    print(f"=== Reset de Usuário: {user_arg} ===")
    resetar_ou_criar_usuario(username=user_arg, nova_senha=pass_arg, is_admin=admin_arg)
