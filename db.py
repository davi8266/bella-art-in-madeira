import sqlite3
import os
import sys

if getattr(sys, 'frozen', False):
    # Executável: salvar ao lado do executável
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Desenvolvimento: salvar ao lado do script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, 'bellart.db')

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha_hash TEXT,
        ativo INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plataformas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE,
        unidade TEXT,
        estoque_atual REAL,
        custo_medio REAL
    )
    """)
    cur.execute("PRAGMA table_info(materias_primas)")
    mp_cols = [r[1] for r in cur.fetchall()]
    if 'unidade' not in mp_cols:
        cur.execute("ALTER TABLE materias_primas ADD COLUMN unidade TEXT")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimentos_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        materia_id INTEGER,
        tipo TEXT,
        quantidade REAL,
        custo_unitario REAL,
        data TEXT,
        ref TEXT,
        FOREIGN KEY(materia_id) REFERENCES materias_primas(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE,
        sku TEXT,
        ativo INTEGER
    )
    """)
    # coluna de código estável do produto
    cur.execute("PRAGMA table_info(produtos)")
    prod_cols = [r[1] for r in cur.fetchall()]
    if 'codigo' not in prod_cols:
        cur.execute("ALTER TABLE produtos ADD COLUMN codigo TEXT")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_codigo ON produtos(codigo)")
    if 'sku' not in prod_cols:
        cur.execute("ALTER TABLE produtos ADD COLUMN sku TEXT")
    if 'ativo' not in prod_cols:
        cur.execute("ALTER TABLE produtos ADD COLUMN ativo INTEGER DEFAULT 1")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS produto_composicao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        materia_id INTEGER,
        quantidade_por_unidade REAL,
        FOREIGN KEY(produto_id) REFERENCES produtos(id),
        FOREIGN KEY(materia_id) REFERENCES materias_primas(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS precos_plataforma (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        plataforma_id INTEGER,
        preco_venda REAL,
        FOREIGN KEY(produto_id) REFERENCES produtos(id),
        FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS taxas_plataforma (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plataforma_id INTEGER UNIQUE,
        percentual REAL,
        valor_fixo REAL,
        FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
    )
    """)
    cur.execute("""PRAGMA table_info(taxas_plataforma)""")
    cols = [r[1] for r in cur.fetchall()]
    if 'imposto_percentual' not in cols:
        cur.execute("ALTER TABLE taxas_plataforma ADD COLUMN imposto_percentual REAL")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        quantidade INTEGER,
        data TEXT,
        custo_extra REAL,
        tempo_minutos INTEGER,
        FOREIGN KEY(produto_id) REFERENCES produtos(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        plataforma_id INTEGER,
        quantidade INTEGER,
        preco_aplicado REAL,
        data TEXT,
        FOREIGN KEY(produto_id) REFERENCES produtos(id),
        FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
    )
    """)
    # garantir coluna para marcação de vendas via QR
    cur.execute("""PRAGMA table_info(vendas)""")
    cols = [r[1] for r in cur.fetchall()]
    if 'via_qr' not in cols:
        cur.execute("ALTER TABLE vendas ADD COLUMN via_qr INTEGER DEFAULT 0")
    if 'ml_mode' not in cols:
        cur.execute("ALTER TABLE vendas ADD COLUMN ml_mode TEXT")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS configuracoes (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qr_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            plataforma_id INTEGER,
            code TEXT UNIQUE,
            short_code TEXT,
            num_code TEXT,
            ml_mode TEXT,
            FOREIGN KEY(produto_id) REFERENCES produtos(id),
            FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
        )
        """
    )
    # add index for short_code if column exists
    cur.execute("PRAGMA table_info(qr_codes)")
    cols = [r[1] for r in cur.fetchall()]
    if 'short_code' not in cols:
        cur.execute("ALTER TABLE qr_codes ADD COLUMN short_code TEXT")
    if 'num_code' not in cols:
        cur.execute("ALTER TABLE qr_codes ADD COLUMN num_code TEXT")
    if 'ml_mode' not in cols:
        cur.execute("ALTER TABLE qr_codes ADD COLUMN ml_mode TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_short ON qr_codes(short_code)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_num ON qr_codes(num_code)")
    conn.commit()

def seed_initial(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM usuarios")
    n_users_row = cur.fetchone()
    n_users = int(n_users_row[0] if n_users_row else 0)
    if n_users == 0:
        import hashlib
        h = hashlib.sha256("admin".encode("utf-8")).hexdigest()
        cur.execute("INSERT OR IGNORE INTO usuarios(username, senha_hash, ativo) VALUES (?, ?, 1)", ("admin", h))
        conn.commit()
    cur.execute("SELECT valor FROM configuracoes WHERE chave='seed_done'")
    row = cur.fetchone()
    if row and str(row[0]) == '1':
        return
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Mercado Livre",))
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Magalu",))
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Shopee",))
    cur.execute("INSERT OR IGNORE INTO configuracoes(chave, valor) VALUES (?, ?)", ("custo_mao_obra_por_minuto", "0"))
    cur.execute("INSERT OR IGNORE INTO materias_primas(nome, unidade, estoque_atual, custo_medio) VALUES (?, ?, ?, ?)", ("MDF 6mm", "placa", 1500, 50))
    cur.execute("INSERT OR IGNORE INTO materias_primas(nome, unidade, estoque_atual, custo_medio) VALUES (?, ?, ?, ?)", ("Caixa 22", "un", 0, 0))
    cur.execute("INSERT OR IGNORE INTO produtos(nome, sku, ativo) VALUES (?, ?, 1)", ("Toalha", "TOA-001",))
    cur.execute("SELECT id FROM produtos WHERE nome=?", ("Toalha",))
    prod = cur.fetchone()
    if prod:
        produto_id = prod[0]
        cur.execute("SELECT id FROM materias_primas WHERE nome=?", ("MDF 6mm",))
        mdf_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM materias_primas WHERE nome=?", ("Caixa 22",))
        caixa_id = cur.fetchone()[0]
        cur.execute("INSERT OR IGNORE INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)", (produto_id, mdf_id, 1.0/6.0))
        cur.execute("INSERT OR IGNORE INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)", (produto_id, caixa_id, 1.0))
        cur.execute("SELECT id FROM plataformas WHERE nome=?", ("Mercado Livre",))
        ml_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM plataformas WHERE nome=?", ("Magalu",))
        mag_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM plataformas WHERE nome=?", ("Shopee",))
        sh_id = cur.fetchone()[0]
        for pid in (ml_id, mag_id, sh_id):
            cur.execute("INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (produto_id, pid, 77.0))
        # taxas 0 por padrão
        for pid in (ml_id, mag_id, sh_id):
            cur.execute("INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (pid, 0.0, 0.0, 0.0))
    conn.commit()
    cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES ('seed_done', '1')")
    conn.commit()
    cur.execute("SELECT COUNT(1) FROM usuarios")
    n = cur.fetchone()[0]
    if int(n or 0) == 0:
        import hashlib
        h = hashlib.sha256("admin".encode("utf-8")).hexdigest()
        cur.execute("INSERT OR IGNORE INTO usuarios(username, senha_hash, ativo) VALUES (?, ?, 1)", ("admin", h))
        conn.commit()
    migrate_ml_split(conn)

def migrate_ml_split(conn):
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracoes WHERE chave='ml_split_done'")
    row = cur.fetchone()
    if row and str(row[0]) == '1':
        return

    # Criar plataformas novas
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Mercado Livre Clássico",))
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Mercado Livre Premium",))
    conn.commit()

    # Obter IDs
    cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre'")
    row_ml = cur.fetchone()
    ml_id = row_ml[0] if row_ml else None

    cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre Clássico'")
    row_cl = cur.fetchone()
    cl_id = row_cl[0] if row_cl else None

    cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre Premium'")
    row_pr = cur.fetchone()
    pr_id = row_pr[0] if row_pr else None

    if not ml_id or not cl_id or not pr_id:
        return

    # Copiar preços
    cur.execute("SELECT produto_id, preco_venda FROM precos_plataforma WHERE plataforma_id=?", (ml_id,))
    prices = cur.fetchall()
    for pid, val in prices:
        # Clássico
        cur.execute("INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (pid, cl_id, val))
        # Premium
        cur.execute("INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (pid, pr_id, val))

    # Tentar copiar taxas de configuracoes ou base
    # Ler taxas base do ML
    cur.execute("SELECT percentual, valor_fixo, imposto_percentual FROM taxas_plataforma WHERE plataforma_id=?", (ml_id,))
    tax_base = cur.fetchone()
    if not tax_base:
        tax_base = (0.0, 0.0, 0.0)
    
    # Função auxiliar para ler config ou fallback
    cur.execute("SELECT chave, valor FROM configuracoes WHERE chave LIKE 'tax_ml_%'")
    cfg_rows = cur.fetchall()
    cfg = {}
    for k, v in cfg_rows:
        try: cfg[k] = float(v)
        except: pass

    def get_val(mode, field, fallback):
        key = f"tax_ml_{mode}_{field}"
        return cfg.get(key, fallback)

    # Inserir taxas Clássico
    cp = get_val('classico', 'percentual', tax_base[0])
    cf = get_val('classico', 'fixo', tax_base[1])
    ci = get_val('classico', 'imposto', tax_base[2])
    cur.execute("INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (cl_id, cp, cf, ci))
    
    # Inserir taxas Premium
    pp = get_val('premium', 'percentual', tax_base[0])
    pf = get_val('premium', 'fixo', tax_base[1])
    pi = get_val('premium', 'imposto', tax_base[2])
    cur.execute("INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (pr_id, pp, pf, pi))

    cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES ('ml_split_done', '1')")
    conn.commit()


def get_user(conn, username):
    cur = conn.cursor()
    cur.execute("SELECT id, username, senha_hash, ativo FROM usuarios WHERE LOWER(username)=LOWER(?)", (username,))
    row = cur.fetchone()
    if not row:
        return None
    return { 'id': int(row[0]), 'username': row[1], 'senha_hash': row[2], 'ativo': int(row[3] or 0) }

def verify_login(conn, username, senha):
    import hashlib
    u = get_user(conn, username)
    if not u or not u['ativo']:
        return None
    h = hashlib.sha256(str(senha or '').encode('utf-8')).hexdigest()
    if h != (u['senha_hash'] or ''):
        return None
    return { 'id': u['id'], 'username': u['username'] }

def change_password(conn, username, old, new):
    import hashlib
    u = verify_login(conn, username, old)
    if not u:
        return False
    nh = hashlib.sha256(str(new or '').encode('utf-8')).hexdigest()
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (nh, u['id']))
    conn.commit()
    return True

def fetch_products(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, nome, sku, ativo FROM produtos ORDER BY nome")
    return cur.fetchall()

def insert_product(conn, nome, sku):
    cur = conn.cursor()
    cur.execute("SELECT id FROM produtos WHERE LOWER(nome)=LOWER(?)", (nome,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE produtos SET sku=?, ativo=1 WHERE id=?", (sku, row[0]))
        conn.commit()
        return row[0]
    cur.execute("INSERT INTO produtos(nome, sku, ativo) VALUES (?, ?, 1)", (nome, sku))
    conn.commit()
    return cur.lastrowid

def ensure_product_code(conn, produto_id):
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM produtos WHERE id=?", (produto_id,))
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    import uuid
    code = 'P' + uuid.uuid4().hex[:10].upper()
    cur.execute("UPDATE produtos SET codigo=? WHERE id=?", (code, produto_id))
    conn.commit()
    return code

def update_product(conn, produto_id, nome, sku):
    cur = conn.cursor()
    cur.execute("UPDATE produtos SET nome=?, sku=? WHERE id=?", (nome, sku, produto_id))
    conn.commit()

def delete_product(conn, produto_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM precos_plataforma WHERE produto_id=?", (produto_id,))
    cur.execute("DELETE FROM produto_composicao WHERE produto_id=?", (produto_id,))
    cur.execute("DELETE FROM producao WHERE produto_id=?", (produto_id,))
    cur.execute("DELETE FROM vendas WHERE produto_id=?", (produto_id,))
    cur.execute("DELETE FROM qr_codes WHERE produto_id=?", (produto_id,))
    cur.execute("DELETE FROM produtos WHERE id=?", (produto_id,))
    conn.commit()

def delete_venda(conn, venda_id):
    cur = conn.cursor()
    # Restaurar estoque antes de excluir
    cur.execute("SELECT produto_id, quantidade FROM vendas WHERE id=?", (venda_id,))
    row = cur.fetchone()
    if row:
        produto_id, quantidade = row
        cur.execute("SELECT materia_id, quantidade_por_unidade FROM produto_composicao WHERE produto_id=?", (produto_id,))
        comps = cur.fetchall()
        for mid, qtd_unit in comps:
            qtd_total = float(qtd_unit) * int(quantidade)
            if qtd_total > 0:
                cur.execute("UPDATE materias_primas SET estoque_atual = estoque_atual + ? WHERE id=?", (qtd_total, mid))
                # Remover log de movimento associado
                cur.execute("DELETE FROM movimentos_estoque WHERE ref=?", (f"Venda {venda_id}",))

    cur.execute("DELETE FROM vendas WHERE id=?", (venda_id,))
    conn.commit()

def get_platform_id(conn, nome):
    cur = conn.cursor()
    cur.execute("SELECT id FROM plataformas WHERE nome=?", (nome,))
    row = cur.fetchone()
    return row[0] if row else None

def get_prices(conn, produto_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT p.nome, pr.preco_venda
        FROM precos_plataforma pr
        JOIN plataformas p ON p.id = pr.plataforma_id
        WHERE pr.produto_id=?
    """, (produto_id,))
    data = { }
    for nome, preco in cur.fetchall():
        data[nome] = float(preco)
    return data

def upsert_price(conn, produto_id, plataforma_nome, preco):
    pid = get_platform_id(conn, plataforma_nome)
    if pid is None:
        return
    cur = conn.cursor()
    cur.execute("SELECT id FROM precos_plataforma WHERE produto_id=? AND plataforma_id=?", (produto_id, pid))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE precos_plataforma SET preco_venda=? WHERE id=?", (float(preco), row[0]))
    else:
        cur.execute("INSERT INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (produto_id, pid, float(preco)))
    conn.commit()

def get_taxes(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT p.nome, COALESCE(t.percentual, 0), COALESCE(t.valor_fixo, 0), COALESCE(t.imposto_percentual, 0)
        FROM plataformas p
        LEFT JOIN taxas_plataforma t ON t.plataforma_id = p.id
        ORDER BY p.nome
    """)
    base = {}
    for nome, perc, fixo, imp in cur.fetchall():
        p = float(perc or 0)
        i = float(imp or 0)
        if p > 1:
            p = p / 100.0
        if i > 1:
            i = i / 100.0
        base[nome] = (p, float(fixo or 0), i)
    data = {}
    for nome, tpl in base.items():
        if nome == "Mercado Livre":
            continue
        data[nome] = tpl
    return data

def _upsert_tax_platform(conn, plataforma_nome, percentual, valor_fixo, imposto_percentual):
    pid = get_platform_id(conn, plataforma_nome)
    if pid is None:
        return
    cur = conn.cursor()
    cur.execute("SELECT id FROM taxas_plataforma WHERE plataforma_id=?", (pid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE taxas_plataforma SET percentual=?, valor_fixo=?, imposto_percentual=? WHERE id=?", (float(percentual), float(valor_fixo), float(imposto_percentual), row[0]))
    else:
        cur.execute("INSERT INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (pid, float(percentual), float(valor_fixo), float(imposto_percentual)))
    conn.commit()

def upsert_tax(conn, plataforma_nome, percentual, valor_fixo, imposto_percentual):
    # Salvar nas configurações para compatibilidade (se necessário)
    if plataforma_nome.startswith("Mercado Livre "):
        mode = 'premium'
        lower = plataforma_nome.lower()
        if 'clássico' in lower or 'classico' in lower:
            mode = 'classico'
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES (?, ?)", (f"tax_ml_{mode}_percentual", float(percentual)))
        cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES (?, ?)", (f"tax_ml_{mode}_fixo", float(valor_fixo)))
        cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES (?, ?)", (f"tax_ml_{mode}_imposto", float(imposto_percentual)))
        conn.commit()
    
    # Salvar na tabela oficial de taxas (agora que são plataformas reais)
    _upsert_tax_platform(conn, plataforma_nome, percentual, valor_fixo, imposto_percentual)

def fetch_materials(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, nome, unidade, estoque_atual, custo_medio FROM materias_primas ORDER BY nome")
    return cur.fetchall()

def insert_material(conn, nome, unidade, estoque_atual, custo_medio):
    cur = conn.cursor()
    cur.execute("INSERT INTO materias_primas(nome, unidade, estoque_atual, custo_medio) VALUES (?, ?, ?, ?)", (nome, unidade, float(estoque_atual or 0), float(custo_medio or 0)))
    conn.commit()
    return cur.lastrowid

def update_material(conn, materia_id, nome, unidade, estoque_atual, custo_medio):
    cur = conn.cursor()
    cur.execute("UPDATE materias_primas SET nome=?, unidade=?, estoque_atual=?, custo_medio=? WHERE id=?", (nome, unidade, float(estoque_atual or 0), float(custo_medio or 0), materia_id))
    conn.commit()

def delete_material(conn, materia_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM movimentos_estoque WHERE materia_id=?", (materia_id,))
    cur.execute("DELETE FROM produto_composicao WHERE materia_id=?", (materia_id,))
    cur.execute("DELETE FROM materias_primas WHERE id=?", (materia_id,))
    conn.commit()

def get_composition(conn, produto_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT pc.id, mp.nome, mp.unidade, pc.quantidade_por_unidade, mp.custo_medio
        FROM produto_composicao pc
        JOIN materias_primas mp ON mp.id = pc.materia_id
        WHERE pc.produto_id=?
        ORDER BY mp.nome
    """, (produto_id,))
    return cur.fetchall()

def upsert_composition(conn, produto_id, materia_id, quantidade):
    cur = conn.cursor()
    cur.execute("SELECT id FROM produto_composicao WHERE produto_id=? AND materia_id=?", (produto_id, materia_id))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE produto_composicao SET quantidade_por_unidade=? WHERE id=?", (float(quantidade), row[0]))
    else:
        cur.execute("INSERT INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)", (produto_id, materia_id, float(quantidade)))
    conn.commit()

def update_composition(conn, comp_id, quantidade):
    cur = conn.cursor()
    cur.execute("UPDATE produto_composicao SET quantidade_por_unidade=? WHERE id=?", (float(quantidade), comp_id))
    conn.commit()

def delete_composition(conn, comp_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM produto_composicao WHERE id=?", (comp_id,))
    conn.commit()

def insert_venda(conn, produto_id, plataforma_id, quantidade, preco_aplicado, data, via_qr=0, ml_mode=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO vendas(produto_id, plataforma_id, quantidade, preco_aplicado, data, via_qr, ml_mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (produto_id, plataforma_id, int(quantidade), float(preco_aplicado), data, int(via_qr), ml_mode),
    )
    venda_id = cur.lastrowid

    # Descontar materiais do estoque
    cur.execute("SELECT materia_id, quantidade_por_unidade FROM produto_composicao WHERE produto_id=?", (produto_id,))
    comps = cur.fetchall()
    for mid, qtd_unit in comps:
        qtd_total = float(qtd_unit) * int(quantidade)
        if qtd_total > 0:
            cur.execute("UPDATE materias_primas SET estoque_atual = estoque_atual - ? WHERE id=?", (qtd_total, mid))
            # Registrar movimento
            cur.execute("SELECT custo_medio FROM materias_primas WHERE id=?", (mid,))
            row_custo = cur.fetchone()
            custo = row_custo[0] if row_custo else 0
            cur.execute("INSERT INTO movimentos_estoque (materia_id, tipo, quantidade, custo_unitario, data, ref) VALUES (?, ?, ?, ?, ?, ?)", 
                        (mid, 'saida', qtd_total, custo, data, f"Venda {venda_id}"))

    conn.commit()
    return venda_id

def fetch_vendas(conn, produto_id=0):
    cur = conn.cursor()
    if produto_id:
        cur.execute(
            """
            SELECT v.id, p.nome, v.quantidade, v.preco_aplicado, v.data, v.via_qr, v.ml_mode
            FROM vendas v
            JOIN plataformas p ON p.id = v.plataforma_id
            WHERE v.produto_id=?
            ORDER BY v.data DESC, v.id DESC
            """,
            (produto_id,)
        )
    else:
        cur.execute(
            """
            SELECT v.id, p.nome, v.quantidade, v.preco_aplicado, v.data, v.via_qr, prod.nome, v.ml_mode
            FROM vendas v
            JOIN plataformas p ON p.id = v.plataforma_id
            JOIN produtos prod ON prod.id = v.produto_id
            ORDER BY v.data DESC, v.id DESC
            LIMIT 1000
            """
        )
    return cur.fetchall()

def get_price_by_ids(conn, produto_id, plataforma_id):
    cur = conn.cursor()
    cur.execute("SELECT preco_venda FROM precos_plataforma WHERE produto_id=? AND plataforma_id=?", (produto_id, plataforma_id))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0

def get_or_create_qr(conn, produto_id, plataforma_id, force=False, ml_mode=None):
    cur = conn.cursor()
    if not force:
        if ml_mode is None:
            cur.execute("SELECT code FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')", (produto_id, plataforma_id))
        else:
            cur.execute("SELECT code FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?", (produto_id, plataforma_id, ml_mode))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    prod_code = ensure_product_code(conn, produto_id)
    # chave de plataforma estável baseada no nome
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plataforma_id,))
    plat_row = cur.fetchone()
    plat_name = (plat_row[0] or '').strip().lower() if plat_row else ''
    if 'mercado' in plat_name:
        mode = (ml_mode or '').lower()
        if mode == 'premium':
            plat_key = 'mlp'
        elif mode == 'classico':
            plat_key = 'mlc'
        else:
            plat_key = 'ml'
            # Se o nome da plataforma no banco já tiver o sufixo, tenta inferir
            if 'premium' in plat_name and not ml_mode:
                ml_mode = 'premium'
            elif ('classico' in plat_name or 'clássico' in plat_name) and not ml_mode:
                ml_mode = 'classico'
    elif 'magalu' in plat_name:
        plat_key = 'magalu'
    elif 'shopee' in plat_name:
        plat_key = 'shopee'
    else:
        plat_key = plat_name.replace(' ', '-')[:12] or 'plat'
    import uuid
    rand = uuid.uuid4().hex[:6].upper() if force else ''
    base = f"BL{prod_code}{rand}{plat_key}"
    short = f"SC{prod_code}{plat_key}"
    num = base36_digest(short, 10)
    # quando force, removemos qualquer antigo para esta combinação
    if force:
        if ml_mode is None:
            cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')", (produto_id, plataforma_id))
        else:
            cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?", (produto_id, plataforma_id, ml_mode))
    cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code, ml_mode) VALUES (?, ?, ?, ?, ?, ?)", (produto_id, plataforma_id, base, short, num, ml_mode))
    conn.commit()
    return base

def get_qr_by_code(conn, code):
    cur = conn.cursor()
    # tentativa direta
    cur.execute("SELECT produto_id, plataforma_id, ml_mode FROM qr_codes WHERE code=? OR UPPER(short_code)=UPPER(?) OR UPPER(num_code)=UPPER(?)", (code, code, code))
    row = cur.fetchone()
    if row:
        return {'produto_id': int(row[0]), 'plataforma_id': int(row[1]), 'ml_mode': row[2]}
    # tentativa case-insensitive com trim
    cur.execute("SELECT produto_id, plataforma_id, ml_mode FROM qr_codes WHERE LOWER(code)=LOWER(?) OR LOWER(short_code)=LOWER(?) OR LOWER(num_code)=LOWER(?)", (code.strip(), code.strip(), code.strip()))
    row = cur.fetchone()
    if row:
        return {'produto_id': int(row[0]), 'plataforma_id': int(row[1]), 'ml_mode': row[2]}
    # padrão numérico antigo: BL-<pid>-<platId>-<rand>
    import re
    mm = re.match(r'^[Bb][Ll]-(\d+)-(\d+)-([A-Za-z0-9]+)$', code.strip())
    if mm:
        pid = int(mm.group(1))
        plat_id = int(mm.group(2))
        cur.execute("SELECT 1 FROM produtos WHERE id=?", (pid,))
        ok_prod = cur.fetchone() is not None
        cur.execute("SELECT 1 FROM plataformas WHERE id=?", (plat_id,))
        ok_plat = cur.fetchone() is not None
        if ok_prod and ok_plat:
            # compute stable short
            cur.execute("SELECT nome FROM plataformas WHERE id=?", (plat_id,))
            plat_row = cur.fetchone(); n = (plat_row[0] or '').lower() if plat_row else ''
            plat_key = 'ml' if 'mercado' in n else ('magalu' if 'magalu' in n else ('shopee' if 'shopee' in n else n.replace(' ', '-')))
            short = f"SC{ensure_product_code(conn, pid)}{plat_key}"
            num = base36_digest(short, 10)
            cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code) VALUES (?, ?, ?, ?, ?)", (pid, plat_id, code, short, num))
            conn.commit()
            return {'produto_id': pid, 'plataforma_id': plat_id}
    # padrão estável: BL-<prodCode>-<platKey>
    mm2 = re.match(r'^[Bb][Ll]-([A-Za-z0-9]+)-([A-Za-z0-9\-]+)$', code.strip())
    if mm2:
        prod_code = mm2.group(1)
        plat_key = mm2.group(2)
        cur.execute("SELECT id FROM produtos WHERE UPPER(codigo)=UPPER(?)", (prod_code,))
        prow = cur.fetchone()
        if prow:
            produto_id = int(prow[0])
            # resolver plataforma por key
            cur.execute("SELECT id, nome FROM plataformas")
            for pid, nome in cur.fetchall():
                n = (nome or '').lower()
                key = 'ml' if 'mercado' in n else ('magalu' if 'magalu' in n else ('shopee' if 'shopee' in n else n.replace(' ', '-')))
                if key == plat_key:
                    short = f"SC{ensure_product_code(conn, produto_id)}{key}"
                    num = base36_digest(short, 10)
                    cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code) VALUES (?, ?, ?, ?, ?)", (produto_id, pid, code, short, num))
                    conn.commit()
                    return {'produto_id': produto_id, 'plataforma_id': pid}
    mm3 = re.match(r'^[Bb][Ll]?([A-Za-z0-9]+)(ml|magalu|shopee)$', code.strip())
    if mm3:
        prod_part = mm3.group(1)
        plat_key = mm3.group(2).lower()
        # tentativa exata
        cur.execute("SELECT id FROM produtos WHERE UPPER(codigo)=UPPER(?)", (prod_part,))
        prow = cur.fetchone()
        produto_id = int(prow[0]) if prow else None
        # tentativa prefixo (caso prod_part contenha sufixo aleatório)
        if produto_id is None:
            cur.execute("SELECT id, codigo FROM produtos")
            for pid_p, cod in cur.fetchall():
                if cod and prod_part.upper().startswith(str(cod).upper()):
                    produto_id = int(pid_p)
                    break
        if produto_id is not None:
            cur.execute("SELECT id, nome FROM plataformas")
            for pid, nome in cur.fetchall():
                n = (nome or '').lower()
                key = 'ml' if 'mercado' in n else ('magalu' if 'magalu' in n else ('shopee' if 'shopee' in n else n.replace(' ', '-')))
                if key == plat_key:
                    short = f"SC{ensure_product_code(conn, produto_id)}{key}"
                    num = base36_digest(short, 10)
                    cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code) VALUES (?, ?, ?, ?, ?)", (produto_id, pid, code, short, num))
                    conn.commit()
                    return {'produto_id': produto_id, 'plataforma_id': pid}
    # formato genérico: [BL opcional][codigoProduto][palavraPlataforma]
    mm4 = re.match(r'^(?:[Bb][Ll])?([A-Za-z0-9]+)([A-Za-z]+)$', code.strip())
    if mm4:
        prod_part = mm4.group(1)
        plat_raw = mm4.group(2).lower()
        def norm_plat(s):
            s = s.lower()
            if s in ('ml','mercado','mercadolivre','mercado_livre','mercadol','mrl'): return 'ml'
            if s in ('magalu','maga','magal','magazineluiza','magazine','mglu'): return 'magalu'
            if s in ('shopee','shop','shp'): return 'shopee'
            return s
        plat_key = norm_plat(plat_raw)
        # tentativa 1: match exato
        cur.execute("SELECT id FROM produtos WHERE UPPER(codigo)=UPPER(?)", (prod_part,))
        prow = cur.fetchone()
        produto_id = int(prow[0]) if prow else None
        # tentativa 2: produto cujo codigo é prefixo do prod_part (caso tenha sufixo aleatório)
        if produto_id is None:
            cur.execute("SELECT id, codigo FROM produtos")
            for pid_p, cod in cur.fetchall():
                if cod and prod_part.upper().startswith(str(cod).upper()):
                    produto_id = int(pid_p)
                    break
        if produto_id is not None:
            cur.execute("SELECT id, nome FROM plataformas")
            for pid, nome in cur.fetchall():
                n = (nome or '').lower()
                key = 'ml' if 'mercado' in n else ('magalu' if 'magalu' in n else ('shopee' if 'shopee' in n else n.replace(' ', '-')))
                if key == plat_key:
                    short = f"SC{ensure_product_code(conn, produto_id)}{key}"
                    num = base36_digest(short, 10)
                    cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code) VALUES (?, ?, ?, ?, ?)", (produto_id, pid, code, short, num))
                    conn.commit()
                    return {'produto_id': produto_id, 'plataforma_id': pid}
    # busca genérica: produto cujo codigo aparece dentro do texto e plataforma deduzida
    text_u = code.strip().upper()
    cur.execute("SELECT id, codigo FROM produtos")
    prows = cur.fetchall()
    for pid_p, cod in prows:
        if cod and str(cod).upper() in text_u:
            produto_id = int(pid_p)
            plat_u = code.strip().lower()
            plat_key = 'ml' if ('mercado' in plat_u or 'ml' in plat_u) else ('magalu' if 'magalu' in plat_u or 'mglu' in plat_u else ('shopee' if 'shopee' in plat_u or 'shop' in plat_u or 'shp' in plat_u else None))
            if plat_key:
                cur.execute("SELECT id, nome FROM plataformas")
                for pid, nome in cur.fetchall():
                    n = (nome or '').lower()
                    key = 'ml' if 'mercado' in n else ('magalu' if 'magalu' in n else ('shopee' if 'shopee' in n else n.replace(' ', '-')))
                    if key == plat_key:
                        short = f"SC{ensure_product_code(conn, produto_id)}{key}"
                        cur.execute("INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code) VALUES (?, ?, ?, ?)", (produto_id, pid, code, short))
                        conn.commit()
                        return {'produto_id': produto_id, 'plataforma_id': pid}
    return None

def get_qr_for_product(conn, produto_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT q.plataforma_id, p.nome, q.code, q.short_code, q.num_code, q.ml_mode
        FROM qr_codes q
        JOIN plataformas p ON p.id = q.plataforma_id
        WHERE q.produto_id=?
        ORDER BY p.nome
    """, (produto_id,))
    rows = cur.fetchall()
    out = []
    seen_labels = set()
    for plat_id, nome, code, short, num, ml_mode in rows:
        label = nome
        if nome == 'Mercado Livre' and ml_mode:
            if ml_mode == 'premium':
                label = 'Mercado Livre Premium'
            elif ml_mode == 'classico':
                label = 'Mercado Livre Clássico'
        
        if label in seen_labels:
            continue
        seen_labels.add(label)
        out.append({'plataforma_id': plat_id, 'plataforma': label, 'code': code, 'short': short, 'num': num, 'ml_mode': ml_mode})
    return out
def base36_digest(s: str, length: int = 10):
    import hashlib
    h = hashlib.sha1(s.encode('utf-8')).hexdigest()
    n = int(h, 16)
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    out = ''
    while n > 0 and len(out) < 32:
        out = chars[n % 36] + out
        n //= 36
    out = (out or '0').upper()
    return out[:length]
