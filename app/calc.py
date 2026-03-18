"""
calc.py — Bellart ERP
Cálculos financeiros: custo de materiais, financeiro por plataforma, relatório da loja.
Melhorias aplicadas:
  - type hints adicionados
  - Sem imports dentro de funções
  - Lógica de normalização de taxa extraída em helper
  - Variável 'data' renomeada para evitar shadowing do módulo datetime
"""

import sqlite3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_config(conn: sqlite3.Connection, key: str, default: float = 0.0) -> float:
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,))
    row = cur.fetchone()
    return float(row[0]) if row else float(default)


def _normalize_rate(value: float) -> float:
    """Converte taxa de percentual (ex: 12.5) para decimal (0.125) se necessário."""
    return value / 100.0 if value > 1 else value


# ---------------------------------------------------------------------------
# Custos de materiais
# ---------------------------------------------------------------------------

def get_material_details(conn: sqlite3.Connection, produto_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pc.quantidade_por_unidade, mp.custo_medio, mp.nome
        FROM produto_composicao pc
        JOIN materias_primas mp ON mp.id = pc.materia_id
        WHERE pc.produto_id=?
        """,
        (produto_id,),
    )
    details = []
    for qtd, custo, nome in cur.fetchall():
        q = float(qtd or 0)
        c = float(custo or 0)
        details.append({
            "nome": nome,
            "qtd": q,
            "custo_unit": c,
            "custo_item": q * c,
        })
    return details


def materials_cost_unit(conn: sqlite3.Connection, produto_id: int) -> float:
    return sum(d["custo_item"] for d in get_material_details(conn, produto_id))


# Alias mantido para compatibilidade interna
def cost_unit(conn: sqlite3.Connection, produto_id: int) -> float:
    return materials_cost_unit(conn, produto_id)


# ---------------------------------------------------------------------------
# Financeiro por plataforma (relatório de produto)
# ---------------------------------------------------------------------------

def platform_financials(conn: sqlite3.Connection, produto_id: int) -> list[tuple]:
    """
    Retorna lista de tuplas:
    (nome, bruto, perc, fixo, imp, custo_total, custo_mats, bruto,
     impostos_total, receita_liquida, lucro_total, lucro_materiais, margem_total)
    """
    cur = conn.cursor()
    custo_total = cost_unit(conn, produto_id)
    custo_materiais = materials_cost_unit(conn, produto_id)

    cur.execute(
        """
        SELECT p.nome, pr.preco_venda,
               COALESCE(t.percentual, 0),
               COALESCE(t.valor_fixo, 0),
               COALESCE(t.imposto_percentual, 0)
        FROM precos_plataforma pr
        JOIN plataformas p ON p.id = pr.plataforma_id
        LEFT JOIN taxas_plataforma t ON t.plataforma_id = p.id
        WHERE pr.produto_id=?
        """,
        (produto_id,),
    )

    result = []
    for nome, preco, perc, fixo, imp in cur.fetchall():
        if nome == "Mercado Livre":
            continue

        bruto = float(preco or 0)
        p = _normalize_rate(float(perc or 0))
        i = _normalize_rate(float(imp or 0))
        f = float(fixo or 0)

        impostos_total = bruto * p + bruto * i + f
        receita_liquida = bruto - impostos_total
        lucro_total = receita_liquida - custo_total
        lucro_materiais = receita_liquida - custo_materiais
        margem_total = (lucro_total / bruto) if bruto else 0.0

        result.append((
            nome, bruto, p, f, i,
            custo_total, custo_materiais,
            bruto,                  # índice 7 (bruto repetido por compatibilidade)
            impostos_total,
            receita_liquida,
            lucro_total,
            lucro_materiais,
            margem_total,
        ))

    return result


# ---------------------------------------------------------------------------
# Relatório geral da loja
# ---------------------------------------------------------------------------

def store_financials(conn: sqlite3.Connection, start_date: str | None = None, end_date: str | None = None) -> dict:
    cur = conn.cursor()

    query = """
        SELECT v.produto_id, v.plataforma_id, v.quantidade, v.preco_aplicado, v.data,
               p.nome AS produto_nome, pl.nome AS plataforma_nome
        FROM vendas v
        JOIN produtos p  ON p.id  = v.produto_id
        JOIN plataformas pl ON pl.id = v.plataforma_id
    """
    params: list = []
    conditions: list[str] = []

    if start_date:
        conditions.append("v.data >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("v.data <= ?")
        params.append(end_date)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY v.data DESC"

    cur.execute(query, params)
    sales = cur.fetchall()

    total_receita = 0.0
    total_custo_materiais = 0.0
    total_taxas = 0.0
    total_lucro = 0.0

    # Cache para evitar consultas repetidas
    platform_taxes_cache: dict[int, dict] = {}
    product_costs_cache: dict[int, float] = {}
    product_sales_map: dict[int, dict] = {}

    for pid, plat_id, qtd_raw, preco_raw, sale_date, p_nome, pl_nome in sales:
        qtd = float(qtd_raw or 0)
        preco = float(preco_raw or 0)

        receita_venda = qtd * preco

        if pid not in product_costs_cache:
            product_costs_cache[pid] = materials_cost_unit(conn, pid)
        custo_venda = product_costs_cache[pid] * qtd

        if plat_id not in platform_taxes_cache:
            cur.execute(
                "SELECT percentual, valor_fixo, imposto_percentual FROM taxas_plataforma WHERE plataforma_id=?",
                (plat_id,),
            )
            row = cur.fetchone()
            if row:
                platform_taxes_cache[plat_id] = {
                    "perc": _normalize_rate(float(row[0] or 0)),
                    "fixo": float(row[1] or 0),
                    "imp": _normalize_rate(float(row[2] or 0)),
                }
            else:
                platform_taxes_cache[plat_id] = {"perc": 0.0, "fixo": 0.0, "imp": 0.0}

        taxes = platform_taxes_cache[plat_id]
        fee_unit = preco * taxes["perc"] + taxes["fixo"] + preco * taxes["imp"]
        total_fees_venda = fee_unit * qtd

        lucro_venda = receita_venda - custo_venda - total_fees_venda

        total_receita += receita_venda
        total_custo_materiais += custo_venda
        total_taxas += total_fees_venda
        total_lucro += lucro_venda

        if pid not in product_sales_map:
            product_sales_map[pid] = {"nome": p_nome, "qtd": 0, "receita": 0.0, "lucro": 0.0}
        product_sales_map[pid]["qtd"] += qtd
        product_sales_map[pid]["receita"] += receita_venda
        product_sales_map[pid]["lucro"] += lucro_venda

    ranking_produtos = sorted(product_sales_map.values(), key=lambda x: x["qtd"], reverse=True)

    cur.execute("SELECT SUM(estoque_atual * custo_medio) FROM materias_primas")
    row_inv = cur.fetchone()
    total_inventory_value = float(row_inv[0] or 0) if row_inv else 0.0

    return {
        "total_receita": total_receita,
        "total_custo_materiais": total_custo_materiais,
        "total_taxas": total_taxas,
        "total_lucro": total_lucro,
        "margem_geral": (total_lucro / total_receita) if total_receita > 0 else 0.0,
        "ranking_produtos": ranking_produtos,
        "valor_estoque_materiais": total_inventory_value,
    }
