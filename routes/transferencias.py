from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, request, redirect, url_for, flash, session
from database import db
from models import Conta, Categoria, Lancamento

transferencias_bp = Blueprint("transferencias", __name__)


def obter_ou_criar_categoria_transferencia(usuario_id=None):
    cat = Categoria.query.filter_by(nome="Transferência", usuario_id=usuario_id).first()
    if not cat:
        cat = Categoria(nome="Transferência", tipo="despesa", ativa=True, usuario_id=usuario_id)
        db.session.add(cat)
        db.session.commit()
    return cat


@transferencias_bp.route("/transferencias/nova", methods=["POST"])
def transferir():
    usuario_id = session.get("usuario_id")
    conta_origem_id = request.form.get("conta_origem_id")
    conta_destino_id = request.form.get("conta_destino_id")
    valor_raw = request.form.get("valor", "").strip()
    data_raw = request.form.get("data", "").strip()
    observacao = (request.form.get("observacao") or "").strip()

    if not conta_origem_id or not conta_destino_id:
        flash("Selecione as contas de origem e destino.", "warning")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    if str(conta_origem_id) == str(conta_destino_id):
        flash("A conta de origem e destino não podem ser iguais.", "danger")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    try:
        c_origem_id = int(conta_origem_id)
        c_destino_id = int(conta_destino_id)
    except (ValueError, TypeError):
        flash("Contas inválidas.", "danger")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    conta_origem = Conta.query.filter_by(id=c_origem_id, usuario_id=usuario_id).first()
    conta_destino = Conta.query.filter_by(id=c_destino_id, usuario_id=usuario_id).first()

    if not conta_origem or not conta_destino:
        flash("Uma das contas selecionadas não foi encontrada ou não pertence ao seu usuário.", "danger")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    try:
        limpo = valor_raw.replace("R$", "").replace(" ", "")
        if "," in limpo and "." in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        valor = Decimal(limpo).quantize(Decimal("0.01"))
        if valor <= Decimal("0.00"):
            raise ValueError()
    except Exception:
        flash("Valor inválido para transferência.", "danger")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    try:
        data_mov = datetime.strptime(data_raw, "%Y-%m-%d").date() if data_raw else date.today()
    except ValueError:
        data_mov = date.today()

    cat_transferencia = obter_ou_criar_categoria_transferencia(usuario_id)
    transf_codigo = f"TRF-{int(datetime.utcnow().timestamp())}"
    obs_final = f"[{transf_codigo}] {observacao}".strip()

    # Débito na conta origem
    debito = Lancamento(
        usuario_id=usuario_id,
        descricao=f"Transferência para {conta_destino.nome}",
        valor=valor,
        tipo="despesa",
        data=data_mov,
        status="pago",
        observacao=obs_final,
        conta_id=conta_origem.id,
        categoria_id=cat_transferencia.id
    )

    # Crédito na conta destino
    credito = Lancamento(
        usuario_id=usuario_id,
        descricao=f"Transferência de {conta_origem.nome}",
        valor=valor,
        tipo="receita",
        data=data_mov,
        status="pago",
        observacao=obs_final,
        conta_id=conta_destino.id,
        categoria_id=cat_transferencia.id
    )

    db.session.add(debito)
    db.session.add(credito)
    db.session.commit()

    flash(
        f"Transferência de R$ {valor:,.2f} realizada com sucesso de '{conta_origem.nome}' para '{conta_destino.nome}'!",
        "success"
    )
    return redirect(request.referrer or url_for("dashboard.dashboard"))
