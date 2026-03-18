import sqlite3


def get_config(conn, key, default):
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,))
    row = cur.fetchone()
    return float(row[0]) if row else float(default)

def cost_unit(conn, produto_id):
    return materials_cost_unit(conn, produto_id)

def get_material_details(conn, produto_id):
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
        try:
            q = float(qtd or 0)
            c = float(custo or 0)
        except:
            q = 0.0
            c = float(custo or 0)
        
        cost_for_item = q * c
        
        details.append({
            'nome': nome,
            'qtd': q,
            'custo_unit': c,
            'custo_item': cost_for_item
        })
    return details

def materials_cost_unit(conn, produto_id):
    details = get_material_details(conn, produto_id)
    return sum(d['custo_item'] for d in details)

def platform_financials(conn, produto_id):
    cur = conn.cursor()
    custo_total = cost_unit(conn, produto_id)
    custo_materiais = materials_cost_unit(conn, produto_id)
    cur.execute(
        """
        SELECT p.nome, pr.preco_venda, COALESCE(t.percentual,0), COALESCE(t.valor_fixo,0), COALESCE(t.imposto_percentual,0)
        FROM precos_plataforma pr
        JOIN plataformas p ON p.id = pr.plataforma_id
        LEFT JOIN taxas_plataforma t ON t.plataforma_id = p.id
        WHERE pr.produto_id=?
        """,
        (produto_id,),
    )
    rows = cur.fetchall()
    result = []
    ml_base = None
    ml_price = None
    for nome, preco, perc, fixo, imp in rows:
        bruto = float(preco or 0)
        p = float(perc or 0)
        f = float(fixo or 0)
        i = float(imp or 0)
        if p > 1:
            p = p / 100.0
        if i > 1:
            i = i / 100.0
        if nome == "Mercado Livre":
            continue
        impostos_total = bruto * p + bruto * i + f
        receita_liquida = bruto - impostos_total
        lucro_total = receita_liquida - custo_total
        lucro_materiais = receita_liquida - custo_materiais
        margem_total = (lucro_total / bruto) if bruto else 0.0
        result.append((nome, bruto, p, f, i, custo_total, custo_materiais, bruto, impostos_total, receita_liquida, lucro_total, lucro_materiais, margem_total))
    return result

def store_financials(conn, start_date=None, end_date=None):
    cur = conn.cursor()
    # Get all sales with optional date filtering
    query = """
        SELECT v.produto_id, v.plataforma_id, v.quantidade, v.preco_aplicado, v.data,
               p.nome as produto_nome, pl.nome as plataforma_nome
        FROM vendas v
        JOIN produtos p ON p.id = v.produto_id
        JOIN plataformas pl ON pl.id = v.plataforma_id
    """
    params = []
    
    conditions = []
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
    
    # Cache for platform taxes and product costs to avoid repeated queries
    platform_taxes_cache = {}
    product_costs_cache = {}
    
    # Tracking sales by product
    product_sales_map = {}
    
    for pid, plat_id, qtd, preco, data, p_nome, pl_nome in sales:
        qtd = float(qtd or 0)
        preco = float(preco or 0)
        
        # Revenue
        receita_venda = qtd * preco
        
        # Product Cost
        if pid not in product_costs_cache:
            product_costs_cache[pid] = materials_cost_unit(conn, pid)
        unit_cost = product_costs_cache[pid]
        custo_venda = unit_cost * qtd
        
        # Platform Fees
        if plat_id not in platform_taxes_cache:
            cur.execute("SELECT percentual, valor_fixo, imposto_percentual FROM taxas_plataforma WHERE plataforma_id=?", (plat_id,))
            row = cur.fetchone()
            if row:
                platform_taxes_cache[plat_id] = {
                    'perc': float(row[0] or 0),
                    'fixo': float(row[1] or 0),
                    'imp': float(row[2] or 0)
                }
            else:
                platform_taxes_cache[plat_id] = {'perc':0, 'fixo':0, 'imp':0}
        
        taxes = platform_taxes_cache[plat_id]
        p_rate = taxes['perc']
        if p_rate > 1: p_rate /= 100.0
        i_rate = taxes['imp']
        if i_rate > 1: i_rate /= 100.0
        
        # Fee per unit
        fee_unit = (preco * p_rate) + taxes['fixo'] + (preco * i_rate)
        total_fees_venda = fee_unit * qtd
        
        # Profit
        lucro_venda = receita_venda - custo_venda - total_fees_venda
        
        total_receita += receita_venda
        total_custo_materiais += custo_venda
        total_taxas += total_fees_venda
        total_lucro += lucro_venda
        
        # Aggregate by product
        if pid not in product_sales_map:
            product_sales_map[pid] = {
                'nome': p_nome,
                'qtd': 0,
                'receita': 0.0,
                'lucro': 0.0
            }
        product_sales_map[pid]['qtd'] += qtd
        product_sales_map[pid]['receita'] += receita_venda
        product_sales_map[pid]['lucro'] += lucro_venda
        
    # Convert map to sorted list
    ranking_produtos = []
    for pid, data in product_sales_map.items():
        ranking_produtos.append(data)
    
    # Sort by quantity desc
    ranking_produtos.sort(key=lambda x: x['qtd'], reverse=True)
    
    # Calculate total inventory value
    cur.execute("SELECT SUM(estoque_atual * custo_medio) FROM materias_primas")
    row_inv = cur.fetchone()
    total_inventory_value = float(row_inv[0] or 0) if row_inv else 0.0
        
    return {
        'total_receita': total_receita,
        'total_custo_materiais': total_custo_materiais,
        'total_taxas': total_taxas,
        'total_lucro': total_lucro,
        'margem_geral': (total_lucro / total_receita) if total_receita > 0 else 0.0,
        'ranking_produtos': ranking_produtos,
        'valor_estoque_materiais': total_inventory_value
    }
