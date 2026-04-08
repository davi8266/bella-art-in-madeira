"""
erp/calc.py — Cálculos financeiros do Bellart ERP (versão Django ORM).
Portado do original FastAPI, substituindo raw SQL pelo Django ORM.
"""
from __future__ import annotations


def _normalize_rate(value: float) -> float:
    """Converte taxa de percentual (ex: 12.5) para decimal (0.125) se necessário."""
    return value / 100.0 if value > 1 else value


def get_config(key: str, default: float = 0.0) -> float:
    from erp.models import Configuracao
    try:
        return float(Configuracao.objects.get(chave=key).valor)
    except (Configuracao.DoesNotExist, ValueError):
        return float(default)


def get_material_details(produto_id: int) -> list[dict]:
    from erp.models import ProdutoComposicao
    composicoes = (
        ProdutoComposicao.objects
        .filter(produto_id=produto_id)
        .select_related("materia")
    )
    details = []
    for comp in composicoes:
        q = float(comp.quantidade_por_unidade or 0)
        c = float(comp.materia.custo_medio or 0)
        details.append({
            "nome": comp.materia.nome,
            "qtd": q,
            "custo_unit": c,
            "custo_item": q * c,
        })
    return details


def materials_cost_unit(produto_id: int) -> float:
    return sum(d["custo_item"] for d in get_material_details(produto_id))


def platform_financials(produto_id: int) -> list[tuple]:
    """
    Retorna lista de tuplas:
    (nome, bruto, perc, fixo, imp, custo_total, custo_mats, bruto,
     impostos_total, receita_liquida, lucro_total, lucro_materiais, margem_total)
    """
    from erp.models import PrecoPlatforma
    custo_total = materials_cost_unit(produto_id)
    custo_materiais = custo_total

    precos = (
        PrecoPlatforma.objects
        .filter(produto_id=produto_id)
        .select_related("plataforma__taxa")
    )

    result = []
    for pp in precos:
        nome = pp.plataforma.nome
        if nome == "Mercado Livre":
            continue

        try:
            taxa = pp.plataforma.taxa
            perc = float(taxa.percentual or 0)
            fixo = float(taxa.valor_fixo or 0)
            imp  = float(taxa.imposto_percentual or 0)
        except Exception:
            perc = fixo = imp = 0.0

        bruto = float(pp.preco_venda or 0)
        p = _normalize_rate(perc)
        i = _normalize_rate(imp)
        f = fixo

        impostos_total   = bruto * p + bruto * i + f
        receita_liquida  = bruto - impostos_total
        lucro_total      = receita_liquida - custo_total
        lucro_materiais  = receita_liquida - custo_materiais
        margem_total     = (lucro_total / bruto) if bruto else 0.0

        result.append((
            nome, bruto, p, f, i,
            custo_total, custo_materiais,
            bruto,
            impostos_total,
            receita_liquida,
            lucro_total,
            lucro_materiais,
            margem_total,
        ))

    return result


def store_financials(start_date: str | None = None, end_date: str | None = None) -> dict:
    from erp.models import Venda, TaxaPlataforma, MateriaPrima

    qs = Venda.objects.select_related("produto", "plataforma")
    if start_date:
        qs = qs.filter(data__gte=start_date)
    if end_date:
        qs = qs.filter(data__lte=end_date)

    total_receita = 0.0
    total_custo_materiais = 0.0
    total_taxas = 0.0
    total_lucro = 0.0

    platform_taxes_cache: dict[int, dict] = {}
    product_costs_cache: dict[int, float] = {}
    product_sales_map: dict[int, dict] = {}

    for venda in qs:
        qtd   = float(venda.quantidade or 0)
        preco = float(venda.preco_aplicado or 0)
        pid   = venda.produto_id
        plid  = venda.plataforma_id

        receita_venda = qtd * preco

        if pid not in product_costs_cache:
            product_costs_cache[pid] = materials_cost_unit(pid)
        custo_venda = product_costs_cache[pid] * qtd

        if plid not in platform_taxes_cache:
            try:
                taxa = TaxaPlataforma.objects.get(plataforma_id=plid)
                platform_taxes_cache[plid] = {
                    "perc": _normalize_rate(float(taxa.percentual or 0)),
                    "fixo": float(taxa.valor_fixo or 0),
                    "imp":  _normalize_rate(float(taxa.imposto_percentual or 0)),
                }
            except TaxaPlataforma.DoesNotExist:
                platform_taxes_cache[plid] = {"perc": 0.0, "fixo": 0.0, "imp": 0.0}

        taxes = platform_taxes_cache[plid]
        fee_unit         = preco * taxes["perc"] + taxes["fixo"] + preco * taxes["imp"]
        total_fees_venda = fee_unit * qtd
        lucro_venda      = receita_venda - custo_venda - total_fees_venda

        total_receita          += receita_venda
        total_custo_materiais  += custo_venda
        total_taxas            += total_fees_venda
        total_lucro            += lucro_venda

        if pid not in product_sales_map:
            product_sales_map[pid] = {
                "nome":    venda.produto.nome,
                "qtd":     0,
                "receita": 0.0,
                "lucro":   0.0,
            }
        product_sales_map[pid]["qtd"]     += qtd
        product_sales_map[pid]["receita"] += receita_venda
        product_sales_map[pid]["lucro"]   += lucro_venda

    ranking_produtos = sorted(
        product_sales_map.values(), key=lambda x: x["qtd"], reverse=True
    )

    from django.db.models import Sum, F, FloatField, ExpressionWrapper
    inv = MateriaPrima.objects.aggregate(
        total=Sum(ExpressionWrapper(
            F("estoque_atual") * F("custo_medio"),
            output_field=FloatField()
        ))
    )
    total_inventory_value = float(inv["total"] or 0)

    return {
        "total_receita":              total_receita,
        "total_custo_materiais":      total_custo_materiais,
        "total_taxas":                total_taxas,
        "total_lucro":                total_lucro,
        "margem_geral":               (total_lucro / total_receita) if total_receita > 0 else 0.0,
        "ranking_produtos":           ranking_produtos,
        "valor_estoque_materiais":    total_inventory_value,
    }
