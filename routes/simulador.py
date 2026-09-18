from flask import Blueprint, render_template, request, jsonify
from decimal import Decimal

simulador_bp = Blueprint("simulador", __name__)

# Taxas padrão oficiais InfinitePay (Plano InfiniteSmart / Tap - Bandeiras Visa e Mastercard)
TAXAS_PADRAO_SMART = {
    1: 3.16,
    2: 5.40,
    3: 6.46,
    4: 7.51,
    5: 8.55,
    6: 9.58,
    7: 10.36,
    8: 10.99,
    9: 11.61,
    10: 12.23,
    11: 12.84,
    12: 13.44,
    13: 14.05,
    14: 14.65,
    15: 15.25,
    16: 15.85,
    17: 16.45,
    18: 17.05,
}

# Taxas padrão InfiniteLink (Link de Pagamento)
TAXAS_PADRAO_LINK = {
    1: 4.20,
    2: 6.70,
    3: 7.90,
    4: 9.10,
    5: 10.30,
    6: 11.50,
    7: 12.50,
    8: 13.50,
    9: 14.50,
    10: 15.50,
    11: 16.50,
    12: 17.50,
}


def calcular_parcelamento(valor_base, modo="comprador", taxas=None, max_parcelas=12):
    """
    Calcula o parcelamento completo para o valor especificado.
    - modo 'comprador': repassa a taxa ao cliente (fórmula: V_cobrado = V_base / (1 - taxa/100))
    - modo 'vendedor': vendedor assume a taxa (fórmula: V_liquido = V_base * (1 - taxa/100))
    """
    if taxas is None:
        taxas = TAXAS_PADRAO_SMART

    try:
        valor = float(valor_base)
    except (ValueError, TypeError):
        valor = 0.0

    resultados = []
    if valor <= 0:
        return resultados

    for p in range(1, max_parcelas + 1):
        taxa_pct = float(taxas.get(p) or taxas.get(str(p)) or 0.0)
        taxa_decimal = taxa_pct / 100.0

        if modo == "comprador":
            # Repasse de taxa: o vendedor quer receber 'valor' líquido.
            # O cliente paga total_cobrado.
            if taxa_decimal >= 1.0:
                total_cobrado = valor
            else:
                total_cobrado = valor / (1.0 - taxa_decimal)
            valor_parcela = total_cobrado / p
            custo_juros = total_cobrado - valor
            valor_liquido = valor
        else:
            # Vendedor assume: o cliente paga exatamente 'valor'
            total_cobrado = valor
            valor_parcela = valor / p
            desconto_taxa = valor * taxa_decimal
            custo_juros = desconto_taxa
            valor_liquido = valor - desconto_taxa

        resultados.append({
            "parcela": p,
            "taxa_pct": round(taxa_pct, 2),
            "valor_parcela": round(valor_parcela, 2),
            "total_cobrado": round(total_cobrado, 2),
            "custo_juros": round(custo_juros, 2),
            "valor_liquido": round(valor_liquido, 2),
        })

    return resultados


@simulador_bp.route("/calculadora/infinitepay", methods=["GET"])
def infinitepay():
    valor_inicial = request.args.get("valor", "1000,00").strip()
    return render_template(
        "simulador_infinitepay.html",
        valor_inicial=valor_inicial,
        taxas_smart=TAXAS_PADRAO_SMART,
        taxas_link=TAXAS_PADRAO_LINK
    )


@simulador_bp.route("/api/simulador/calcular", methods=["POST"])
def api_calcular():
    dados = request.get_json(silent=True) or {}
    valor = dados.get("valor", 0)
    modo = dados.get("modo", "comprador")
    canal = dados.get("canal", "smart")
    taxas_custom = dados.get("taxas")

    if not taxas_custom:
        taxas = TAXAS_PADRAO_SMART if canal == "smart" else TAXAS_PADRAO_LINK
    else:
        taxas = taxas_custom

    max_p = int(dados.get("max_parcelas", 12))
    tabela = calcular_parcelamento(valor, modo=modo, taxas=taxas, max_parcelas=max_p)
    return jsonify({
        "status": "success",
        "valor": valor,
        "modo": modo,
        "tabela": tabela
    })
