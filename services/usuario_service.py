from database import db
from models.usuario import Usuario
from models.conta import Conta
from models.categoria import Categoria


def inicializar_dados_usuario(usuario):
    """
    Cria a Conta Principal e as categorias financeiras padrão para um novo usuário.
    """
    # 1. Conta Principal inicial
    conta_existente = Conta.query.filter_by(usuario_id=usuario.id).first()
    if not conta_existente:
        conta_inicial = Conta(
            nome="Conta Principal",
            tipo="Conta corrente",
            saldo_inicial=0.00,
            ativa=True,
            usuario_id=usuario.id
        )
        db.session.add(conta_inicial)

    # 2. Categorias padrão
    categorias_padrao = [
        ("Salário", "receita"),
        ("Freelance", "receita"),
        ("Investimentos", "receita"),
        ("Outras receitas", "receita"),
        ("Moradia", "despesa"),
        ("Alimentação", "despesa"),
        ("Transporte", "despesa"),
        ("Saúde", "despesa"),
        ("Educação", "despesa"),
        ("Lazer", "despesa"),
        ("Assinaturas", "despesa"),
        ("Impostos", "despesa"),
        ("Transferência", "despesa"),
        ("Outras despesas", "despesa"),
    ]

    for nome, tipo in categorias_padrao:
        cat_existente = Categoria.query.filter_by(nome=nome, tipo=tipo, usuario_id=usuario.id).first()
        if not cat_existente:
            db.session.add(
                Categoria(
                    nome=nome,
                    tipo=tipo,
                    ativa=True,
                    usuario_id=usuario.id
                )
            )

    db.session.commit()


def criar_usuario(
    username,
    password,
    is_admin=False,
    acesso_mercadopago=True,
    acesso_infinitepay=True,
    acesso_nubank=True
):
    """
    Cria um novo usuário no sistema e inicializa seus dados individuais.
    """
    username = username.strip()
    if not username:
        raise ValueError("O nome de usuário não pode ser vazio.")

    existente = Usuario.query.filter(Usuario.username.ilike(username)).first()
    if existente:
        raise ValueError(f"O usuário '{username}' já existe.")

    if not password or len(password) < 4:
        raise ValueError("A senha deve ter pelo menos 4 caracteres.")

    # Se for admin, garante acesso total a todos os módulos
    if is_admin:
        acesso_mercadopago = True
        acesso_infinitepay = True
        acesso_nubank = True

    novo_usuario = Usuario(
        username=username,
        is_admin=is_admin,
        acesso_mercadopago=acesso_mercadopago,
        acesso_infinitepay=acesso_infinitepay,
        acesso_nubank=acesso_nubank
    )
    novo_usuario.set_password(password)
    db.session.add(novo_usuario)
    db.session.commit()

    inicializar_dados_usuario(novo_usuario)
    return novo_usuario
