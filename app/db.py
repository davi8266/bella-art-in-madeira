"""
db.py — Bellart ERP
Camada de acesso ao banco de dados SQLite.
Melhorias aplicadas:
  - Conexão única por thread com threading.local (evita abrir/fechar a cada request)
  - init_db e seed_initial rodados apenas uma vez na inicialização
  - hashlib substituído por pbkdf2_hmac (senhas com salt)
  - Imports todos no topo
  - get_qr_by_code refatorado em funções auxiliares menores
  - Lógica de ml_mode centralizada em resolve_ml_platform_id
"""

import hashlib
import os
import re
import sqlite3
import sys
import threading
import uuid

# ---------------------------------------------------------------------------
# Configuração de caminho
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Sobe dois níveis: app/ -> raiz -> data/
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(_APP_DIR)

DB_PATH = os.path.join(BASE_DIR, "data", "bellart.db")

# ---------------------------------------------------------------------------
# Conexão — uma por thread, reutilizada
# ---------------------------------------------------------------------------

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Retorna a conexão SQLite do thread atual, criando se necessário."""
    if not getattr(_local, "conn", None):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


# ---------------------------------------------------------------------------
# Inicialização — chamada UMA vez ao subir a aplicação
# ---------------------------------------------------------------------------

_db_initialized = False
_init_lock = threading.Lock()


def ensure_initialized():
    """Garante que init_db e seed_initial rodaram exatamente uma vez."""
    global _db_initialized
    if _db_initialized:
        return get_conn()
    with _init_lock:
        if not _db_initialized:
            conn = get_conn()
            init_db(conn)
            seed_initial(conn)
            _db_initialized = True
    return get_conn()


def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE,
            senha_hash   TEXT,
            salt         TEXT,
            ativo        INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS plataformas (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS materias_primas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT UNIQUE,
            unidade       TEXT,
            estoque_atual REAL DEFAULT 0,
            custo_medio   REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS movimentos_estoque (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            materia_id     INTEGER,
            tipo           TEXT,
            quantidade     REAL,
            custo_unitario REAL,
            data           TEXT,
            ref            TEXT,
            FOREIGN KEY(materia_id) REFERENCES materias_primas(id)
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nome   TEXT UNIQUE,
            sku    TEXT,
            codigo TEXT,
            ativo  INTEGER DEFAULT 1
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_codigo ON produtos(codigo);

        CREATE TABLE IF NOT EXISTS produto_composicao (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id            INTEGER,
            materia_id            INTEGER,
            quantidade_por_unidade REAL,
            FOREIGN KEY(produto_id) REFERENCES produtos(id),
            FOREIGN KEY(materia_id) REFERENCES materias_primas(id)
        );

        CREATE TABLE IF NOT EXISTS precos_plataforma (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id    INTEGER,
            plataforma_id INTEGER,
            preco_venda   REAL,
            FOREIGN KEY(produto_id)    REFERENCES produtos(id),
            FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
        );

        CREATE TABLE IF NOT EXISTS taxas_plataforma (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            plataforma_id       INTEGER UNIQUE,
            percentual          REAL DEFAULT 0,
            valor_fixo          REAL DEFAULT 0,
            imposto_percentual  REAL DEFAULT 0,
            FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
        );

        CREATE TABLE IF NOT EXISTS producao (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id     INTEGER,
            quantidade     INTEGER,
            data           TEXT,
            custo_extra    REAL,
            tempo_minutos  INTEGER,
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        );

        CREATE TABLE IF NOT EXISTS vendas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id      INTEGER,
            plataforma_id   INTEGER,
            quantidade      INTEGER,
            preco_aplicado  REAL,
            data            TEXT,
            via_qr          INTEGER DEFAULT 0,
            ml_mode         TEXT,
            FOREIGN KEY(produto_id)    REFERENCES produtos(id),
            FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
        );

        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE TABLE IF NOT EXISTS qr_codes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id    INTEGER,
            plataforma_id INTEGER,
            code          TEXT UNIQUE,
            short_code    TEXT,
            num_code      TEXT,
            ml_mode       TEXT,
            FOREIGN KEY(produto_id)    REFERENCES produtos(id),
            FOREIGN KEY(plataforma_id) REFERENCES plataformas(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_short ON qr_codes(short_code);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_num   ON qr_codes(num_code);
    """)

    # Migrações: adicionar colunas que podem não existir em bancos antigos
    _add_column_if_missing(cur, "materias_primas", "unidade", "TEXT")
    _add_column_if_missing(cur, "produtos", "codigo", "TEXT")
    _add_column_if_missing(cur, "produtos", "sku", "TEXT")
    _add_column_if_missing(cur, "produtos", "ativo", "INTEGER DEFAULT 1")
    _add_column_if_missing(cur, "taxas_plataforma", "imposto_percentual", "REAL DEFAULT 0")
    _add_column_if_missing(cur, "vendas", "via_qr", "INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "vendas", "ml_mode", "TEXT")
    _add_column_if_missing(cur, "qr_codes", "short_code", "TEXT")
    _add_column_if_missing(cur, "qr_codes", "num_code", "TEXT")
    _add_column_if_missing(cur, "qr_codes", "ml_mode", "TEXT")
    _add_column_if_missing(cur, "usuarios", "salt", "TEXT")

    conn.commit()


def _add_column_if_missing(cur, table: str, column: str, col_type: str):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


# ---------------------------------------------------------------------------
# Seed inicial
# ---------------------------------------------------------------------------

def seed_initial(conn: sqlite3.Connection):
    cur = conn.cursor()

    # Cria admin se não houver nenhum usuário
    cur.execute("SELECT COUNT(1) FROM usuarios")
    if cur.fetchone()[0] == 0:
        salt, h = _hash_password("admin")
        cur.execute(
            "INSERT OR IGNORE INTO usuarios(username, senha_hash, salt, ativo) VALUES (?, ?, ?, 1)",
            ("admin", h, salt),
        )
        conn.commit()

    cur.execute("SELECT valor FROM configuracoes WHERE chave='seed_done'")
    if cur.fetchone():
        migrate_ml_split(conn)
        return

    plataformas = ["Mercado Livre", "Magalu", "Shopee"]
    for nome in plataformas:
        cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", (nome,))

    cur.execute(
        "INSERT OR IGNORE INTO configuracoes(chave, valor) VALUES (?, ?)",
        ("custo_mao_obra_por_minuto", "0"),
    )

    materiais = [
        ("MDF 6mm", "placa", 1500, 50),
        ("Caixa 22", "un", 0, 0),
    ]
    for nome, und, est, custo in materiais:
        cur.execute(
            "INSERT OR IGNORE INTO materias_primas(nome, unidade, estoque_atual, custo_medio) VALUES (?, ?, ?, ?)",
            (nome, und, est, custo),
        )

    cur.execute("INSERT OR IGNORE INTO produtos(nome, sku, ativo) VALUES (?, ?, 1)", ("Toalha", "TOA-001"))
    cur.execute("SELECT id FROM produtos WHERE nome='Toalha'")
    prod = cur.fetchone()

    if prod:
        pid = prod[0]
        cur.execute("SELECT id FROM materias_primas WHERE nome='MDF 6mm'")
        mdf_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM materias_primas WHERE nome='Caixa 22'")
        caixa_id = cur.fetchone()[0]
        cur.execute(
            "INSERT OR IGNORE INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)",
            (pid, mdf_id, 1.0 / 6.0),
        )
        cur.execute(
            "INSERT OR IGNORE INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)",
            (pid, caixa_id, 1.0),
        )

        for nome_plat in plataformas:
            cur.execute("SELECT id FROM plataformas WHERE nome=?", (nome_plat,))
            plat_id = cur.fetchone()[0]
            cur.execute(
                "INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)",
                (pid, plat_id, 77.0),
            )
            cur.execute(
                "INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, 0, 0, 0)",
                (plat_id,),
            )

    cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES ('seed_done', '1')")
    conn.commit()
    migrate_ml_split(conn)


def migrate_ml_split(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracoes WHERE chave='ml_split_done'")
    if cur.fetchone():
        return

    for nome in ("Mercado Livre Clássico", "Mercado Livre Premium"):
        cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", (nome,))
    conn.commit()

    ml_id  = get_platform_id(conn, "Mercado Livre")
    cl_id  = get_platform_id(conn, "Mercado Livre Clássico")
    pr_id  = get_platform_id(conn, "Mercado Livre Premium")

    if not all([ml_id, cl_id, pr_id]):
        return

    cur.execute("SELECT produto_id, preco_venda FROM precos_plataforma WHERE plataforma_id=?", (ml_id,))
    for pid, val in cur.fetchall():
        cur.execute(
            "INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)",
            (pid, cl_id, val),
        )
        cur.execute(
            "INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)",
            (pid, pr_id, val),
        )

    cur.execute(
        "SELECT percentual, valor_fixo, imposto_percentual FROM taxas_plataforma WHERE plataforma_id=?",
        (ml_id,),
    )
    tax_base = cur.fetchone() or (0.0, 0.0, 0.0)

    for new_id in (cl_id, pr_id):
        cur.execute(
            "INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)",
            (new_id, *tax_base),
        )

    cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES ('ml_split_done', '1')")
    conn.commit()


# ---------------------------------------------------------------------------
# Segurança — senhas
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> tuple[str, str]:
    """Retorna (salt_hex, hash_hex) usando pbkdf2_hmac."""
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return salt.hex(), h.hex()


def _verify_password(password: str, salt_hex: str, stored_hash: str) -> bool:
    if not salt_hex:
        # Compatibilidade com senhas antigas (SHA-256 sem salt)
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return legacy == stored_hash
    salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return h.hex() == stored_hash


def get_user(conn: sqlite3.Connection, username: str) -> dict | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, senha_hash, salt, ativo FROM usuarios WHERE LOWER(username)=LOWER(?)",
        (username,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "senha_hash": row[2], "salt": row[3], "ativo": int(row[4] or 0)}


def verify_login(conn: sqlite3.Connection, username: str, senha: str) -> dict | None:
    u = get_user(conn, username)
    if not u or not u["ativo"]:
        return None
    if not _verify_password(senha, u.get("salt") or "", u["senha_hash"]):
        return None
    return {"id": u["id"], "username": u["username"]}


def change_password(conn: sqlite3.Connection, username: str, old: str, new: str) -> bool:
    u = verify_login(conn, username, old)
    if not u:
        return False
    salt, h = _hash_password(new)
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET senha_hash=?, salt=? WHERE id=?", (h, salt, u["id"]))
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------

def fetch_products(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT id, nome, sku, ativo FROM produtos ORDER BY nome")
    return cur.fetchall()


def insert_product(conn: sqlite3.Connection, nome: str, sku: str) -> int:
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


def ensure_product_code(conn: sqlite3.Connection, produto_id: int) -> str:
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM produtos WHERE id=?", (produto_id,))
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    code = "P" + uuid.uuid4().hex[:10].upper()
    cur.execute("UPDATE produtos SET codigo=? WHERE id=?", (code, produto_id))
    conn.commit()
    return code


def update_product(conn: sqlite3.Connection, produto_id: int, nome: str, sku: str):
    cur = conn.cursor()
    cur.execute("UPDATE produtos SET nome=?, sku=? WHERE id=?", (nome, sku, produto_id))
    conn.commit()


def delete_product(conn: sqlite3.Connection, produto_id: int):
    cur = conn.cursor()
    for table, col in [
        ("precos_plataforma", "produto_id"),
        ("produto_composicao", "produto_id"),
        ("producao", "produto_id"),
        ("vendas", "produto_id"),
        ("qr_codes", "produto_id"),
    ]:
        cur.execute(f"DELETE FROM {table} WHERE {col}=?", (produto_id,))
    cur.execute("DELETE FROM produtos WHERE id=?", (produto_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Plataformas
# ---------------------------------------------------------------------------

def get_platform_id(conn: sqlite3.Connection, nome: str) -> int | None:
    cur = conn.cursor()
    cur.execute("SELECT id FROM plataformas WHERE nome=?", (nome,))
    row = cur.fetchone()
    return row[0] if row else None


def resolve_ml_platform_id(conn: sqlite3.Connection, plataforma_id: int, ml_mode: str | None) -> int:
    """
    Dado um plataforma_id (possivelmente do 'Mercado Livre' genérico) e um ml_mode,
    retorna o ID da plataforma correta (Clássico ou Premium).
    """
    if not ml_mode:
        return plataforma_id
    mapping = {
        "premium": "Mercado Livre Premium",
        "classico": "Mercado Livre Clássico",
    }
    nome_alvo = mapping.get(ml_mode.lower())
    if nome_alvo:
        real_id = get_platform_id(conn, nome_alvo)
        if real_id:
            return real_id
    return plataforma_id


# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------

def get_prices(conn: sqlite3.Connection, produto_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.nome, pr.preco_venda
        FROM precos_plataforma pr
        JOIN plataformas p ON p.id = pr.plataforma_id
        WHERE pr.produto_id=?
        """,
        (produto_id,),
    )
    return {nome: float(preco) for nome, preco in cur.fetchall()}


def upsert_price(conn: sqlite3.Connection, produto_id: int, plataforma_nome: str, preco: float):
    pid = get_platform_id(conn, plataforma_nome)
    if pid is None:
        return
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM precos_plataforma WHERE produto_id=? AND plataforma_id=?",
        (produto_id, pid),
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE precos_plataforma SET preco_venda=? WHERE id=?", (float(preco), row[0]))
    else:
        cur.execute(
            "INSERT INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)",
            (produto_id, pid, float(preco)),
        )
    conn.commit()


def get_price_by_ids(conn: sqlite3.Connection, produto_id: int, plataforma_id: int) -> float:
    cur = conn.cursor()
    cur.execute(
        "SELECT preco_venda FROM precos_plataforma WHERE produto_id=? AND plataforma_id=?",
        (produto_id, plataforma_id),
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


# ---------------------------------------------------------------------------
# Taxas
# ---------------------------------------------------------------------------

def get_taxes(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.nome, COALESCE(t.percentual,0), COALESCE(t.valor_fixo,0), COALESCE(t.imposto_percentual,0)
        FROM plataformas p
        LEFT JOIN taxas_plataforma t ON t.plataforma_id = p.id
        ORDER BY p.nome
        """,
    )
    data = {}
    for nome, perc, fixo, imp in cur.fetchall():
        if nome == "Mercado Livre":
            continue
        p = float(perc or 0)
        i = float(imp or 0)
        if p > 1:
            p /= 100.0
        if i > 1:
            i /= 100.0
        data[nome] = (p, float(fixo or 0), i)
    return data


def _upsert_tax_platform(conn: sqlite3.Connection, plataforma_nome: str, percentual: float, valor_fixo: float, imposto_percentual: float):
    pid = get_platform_id(conn, plataforma_nome)
    if pid is None:
        return
    cur = conn.cursor()
    cur.execute("SELECT id FROM taxas_plataforma WHERE plataforma_id=?", (pid,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE taxas_plataforma SET percentual=?, valor_fixo=?, imposto_percentual=? WHERE id=?",
            (float(percentual), float(valor_fixo), float(imposto_percentual), row[0]),
        )
    else:
        cur.execute(
            "INSERT INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)",
            (pid, float(percentual), float(valor_fixo), float(imposto_percentual)),
        )
    conn.commit()


def upsert_tax(conn: sqlite3.Connection, plataforma_nome: str, percentual: float, valor_fixo: float, imposto_percentual: float):
    if plataforma_nome.startswith("Mercado Livre "):
        lower = plataforma_nome.lower()
        mode = "classico" if ("clássico" in lower or "classico" in lower) else "premium"
        cur = conn.cursor()
        for field, val in [("percentual", percentual), ("fixo", valor_fixo), ("imposto", imposto_percentual)]:
            cur.execute(
                "INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES (?, ?)",
                (f"tax_ml_{mode}_{field}", float(val)),
            )
        conn.commit()
    _upsert_tax_platform(conn, plataforma_nome, percentual, valor_fixo, imposto_percentual)


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------

def fetch_materials(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT id, nome, unidade, estoque_atual, custo_medio FROM materias_primas ORDER BY nome")
    return cur.fetchall()


def insert_material(conn: sqlite3.Connection, nome: str, unidade: str, estoque_atual: float, custo_medio: float) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO materias_primas(nome, unidade, estoque_atual, custo_medio) VALUES (?, ?, ?, ?)",
        (nome, unidade, float(estoque_atual or 0), float(custo_medio or 0)),
    )
    conn.commit()
    return cur.lastrowid


def update_material(conn: sqlite3.Connection, materia_id: int, nome: str, unidade: str, estoque_atual: float, custo_medio: float):
    cur = conn.cursor()
    cur.execute(
        "UPDATE materias_primas SET nome=?, unidade=?, estoque_atual=?, custo_medio=? WHERE id=?",
        (nome, unidade, float(estoque_atual or 0), float(custo_medio or 0), materia_id),
    )
    conn.commit()


def delete_material(conn: sqlite3.Connection, materia_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM movimentos_estoque WHERE materia_id=?", (materia_id,))
    cur.execute("DELETE FROM produto_composicao WHERE materia_id=?", (materia_id,))
    cur.execute("DELETE FROM materias_primas WHERE id=?", (materia_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Composição
# ---------------------------------------------------------------------------

def get_composition(conn: sqlite3.Connection, produto_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pc.id, mp.nome, mp.unidade, pc.quantidade_por_unidade, mp.custo_medio
        FROM produto_composicao pc
        JOIN materias_primas mp ON mp.id = pc.materia_id
        WHERE pc.produto_id=?
        ORDER BY mp.nome
        """,
        (produto_id,),
    )
    return cur.fetchall()


def upsert_composition(conn: sqlite3.Connection, produto_id: int, materia_id: int, quantidade: float):
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM produto_composicao WHERE produto_id=? AND materia_id=?",
        (produto_id, materia_id),
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE produto_composicao SET quantidade_por_unidade=? WHERE id=?", (float(quantidade), row[0]))
    else:
        cur.execute(
            "INSERT INTO produto_composicao(produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)",
            (produto_id, materia_id, float(quantidade)),
        )
    conn.commit()


def update_composition(conn: sqlite3.Connection, comp_id: int, quantidade: float):
    cur = conn.cursor()
    cur.execute("UPDATE produto_composicao SET quantidade_por_unidade=? WHERE id=?", (float(quantidade), comp_id))
    conn.commit()


def delete_composition(conn: sqlite3.Connection, comp_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM produto_composicao WHERE id=?", (comp_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------

def insert_venda(conn: sqlite3.Connection, produto_id: int, plataforma_id: int, quantidade: int, preco_aplicado: float, data: str, via_qr: int = 0, ml_mode: str | None = None) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO vendas(produto_id, plataforma_id, quantidade, preco_aplicado, data, via_qr, ml_mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (produto_id, plataforma_id, int(quantidade), float(preco_aplicado), data, int(via_qr), ml_mode),
    )
    venda_id = cur.lastrowid

    # Descontar estoque
    cur.execute("SELECT materia_id, quantidade_por_unidade FROM produto_composicao WHERE produto_id=?", (produto_id,))
    for mid, qtd_unit in cur.fetchall():
        qtd_total = float(qtd_unit) * int(quantidade)
        if qtd_total > 0:
            cur.execute("UPDATE materias_primas SET estoque_atual = estoque_atual - ? WHERE id=?", (qtd_total, mid))
            cur.execute("SELECT custo_medio FROM materias_primas WHERE id=?", (mid,))
            custo_row = cur.fetchone()
            custo = custo_row[0] if custo_row else 0
            cur.execute(
                "INSERT INTO movimentos_estoque(materia_id, tipo, quantidade, custo_unitario, data, ref) VALUES (?, 'saida', ?, ?, ?, ?)",
                (mid, qtd_total, custo, data, f"Venda {venda_id}"),
            )
    conn.commit()
    return venda_id


def fetch_vendas(conn: sqlite3.Connection, produto_id: int = 0):
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
            (produto_id,),
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
            """,
        )
    return cur.fetchall()


def delete_venda(conn: sqlite3.Connection, venda_id: int):
    cur = conn.cursor()
    cur.execute("SELECT produto_id, quantidade FROM vendas WHERE id=?", (venda_id,))
    row = cur.fetchone()
    if row:
        produto_id, quantidade = row
        cur.execute("SELECT materia_id, quantidade_por_unidade FROM produto_composicao WHERE produto_id=?", (produto_id,))
        for mid, qtd_unit in cur.fetchall():
            qtd_total = float(qtd_unit) * int(quantidade)
            if qtd_total > 0:
                cur.execute("UPDATE materias_primas SET estoque_atual = estoque_atual + ? WHERE id=?", (qtd_total, mid))
        cur.execute("DELETE FROM movimentos_estoque WHERE ref=?", (f"Venda {venda_id}",))
    cur.execute("DELETE FROM vendas WHERE id=?", (venda_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# QR Codes — auxiliares
# ---------------------------------------------------------------------------

def base36_digest(s: str, length: int = 10) -> str:
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()
    n = int(h, 16)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = ""
    while n > 0 and len(out) < 32:
        out = chars[n % 36] + out
        n //= 36
    return (out or "0")[:length]


def _plat_key_from_name(nome: str) -> str:
    n = nome.lower()
    if "premium" in n:
        return "mlp"
    if "clássico" in n or "classico" in n:
        return "mlc"
    if "mercado" in n:
        return "ml"
    if "magalu" in n:
        return "magalu"
    if "shopee" in n:
        return "shopee"
    return re.sub(r"[^a-z0-9]", "-", n)[:12] or "plat"


def _norm_plat_key(s: str) -> str:
    s = s.lower()
    if s in ("ml", "mercado", "mercadolivre", "mercado_livre", "mrl"):
        return "ml"
    if s in ("mlp", "premium"):
        return "mlp"
    if s in ("mlc", "classico", "clássico"):
        return "mlc"
    if s in ("magalu", "maga", "magal", "magazineluiza", "magazine", "mglu"):
        return "magalu"
    if s in ("shopee", "shop", "shp"):
        return "shopee"
    return s


def _find_plat_by_key(conn: sqlite3.Connection, plat_key: str) -> int | None:
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas")
    for pid, nome in cur.fetchall():
        if _plat_key_from_name(nome) == plat_key:
            return pid
    return None


def _insert_qr_legacy(conn: sqlite3.Connection, produto_id: int, plataforma_id: int, code: str, ml_mode: str | None = None):
    """Salva um QR legado no banco se ainda não existir."""
    prod_code = ensure_product_code(conn, produto_id)
    plat_nome = ""
    cur = conn.cursor()
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plataforma_id,))
    row = cur.fetchone()
    if row:
        plat_nome = row[0]
    key = _plat_key_from_name(plat_nome)
    short = f"SC{prod_code}{key}"
    num = base36_digest(short, 10)
    cur.execute(
        "INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code, ml_mode) VALUES (?, ?, ?, ?, ?, ?)",
        (produto_id, plataforma_id, code, short, num, ml_mode),
    )
    conn.commit()


def get_or_create_qr(conn: sqlite3.Connection, produto_id: int, plataforma_id: int, force: bool = False, ml_mode: str | None = None) -> str:
    cur = conn.cursor()

    if not force:
        if ml_mode is None:
            cur.execute(
                "SELECT code FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')",
                (produto_id, plataforma_id),
            )
        else:
            cur.execute(
                "SELECT code FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?",
                (produto_id, plataforma_id, ml_mode),
            )
        row = cur.fetchone()
        if row and row[0]:
            return row[0]

    prod_code = ensure_product_code(conn, produto_id)
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plataforma_id,))
    plat_row = cur.fetchone()
    plat_name = (plat_row[0] or "").strip().lower() if plat_row else ""

    # Inferir ml_mode a partir do nome se não fornecido
    if not ml_mode:
        if "premium" in plat_name:
            ml_mode = "premium"
        elif "clássico" in plat_name or "classico" in plat_name:
            ml_mode = "classico"

    plat_key = _plat_key_from_name(plat_row[0] if plat_row else "")

    rand = uuid.uuid4().hex[:6].upper() if force else ""
    base = f"BL{prod_code}{rand}{plat_key}"
    short = f"SC{prod_code}{plat_key}"
    num = base36_digest(short, 10)

    if force:
        if ml_mode is None:
            cur.execute(
                "DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')",
                (produto_id, plataforma_id),
            )
        else:
            cur.execute(
                "DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?",
                (produto_id, plataforma_id, ml_mode),
            )

    cur.execute(
        "INSERT OR IGNORE INTO qr_codes(produto_id, plataforma_id, code, short_code, num_code, ml_mode) VALUES (?, ?, ?, ?, ?, ?)",
        (produto_id, plataforma_id, base, short, num, ml_mode),
    )
    conn.commit()
    return base


def get_qr_by_code(conn: sqlite3.Connection, code: str) -> dict | None:
    """
    Busca um QR por código. Tenta várias estratégias em ordem de confiança.
    Retorna {'produto_id': int, 'plataforma_id': int, 'ml_mode': str|None} ou None.
    """
    code = code.strip()
    cur = conn.cursor()

    # 1. Busca direta (case-insensitive em todos os campos de código)
    cur.execute(
        "SELECT produto_id, plataforma_id, ml_mode FROM qr_codes WHERE LOWER(code)=LOWER(?) OR LOWER(short_code)=LOWER(?) OR LOWER(num_code)=LOWER(?)",
        (code, code, code),
    )
    row = cur.fetchone()
    if row:
        return {"produto_id": int(row[0]), "plataforma_id": int(row[1]), "ml_mode": row[2]}

    # 2. Padrão legado numérico: BL-<pid>-<platId>-<rand>
    m = re.match(r"^[Bb][Ll]-(\d+)-(\d+)-[A-Za-z0-9]+$", code)
    if m:
        pid, plat_id = int(m.group(1)), int(m.group(2))
        cur.execute("SELECT 1 FROM produtos WHERE id=?", (pid,))
        cur2 = conn.cursor()
        cur2.execute("SELECT 1 FROM plataformas WHERE id=?", (plat_id,))
        if cur.fetchone() and cur2.fetchone():
            _insert_qr_legacy(conn, pid, plat_id, code)
            return {"produto_id": pid, "plataforma_id": plat_id, "ml_mode": None}

    # 3. Padrão estável: BL<prodCode><platKey>
    m2 = re.match(r"^[Bb][Ll]([A-Za-z0-9]{10,})([a-zA-Z0-9\-]{2,})$", code)
    if m2:
        prod_part = m2.group(1)
        plat_part = _norm_plat_key(m2.group(2))
        cur.execute("SELECT id FROM produtos WHERE UPPER(codigo)=UPPER(?)", (prod_part,))
        prow = cur.fetchone()
        if prow:
            plat_id = _find_plat_by_key(conn, plat_part)
            if plat_id:
                _insert_qr_legacy(conn, int(prow[0]), plat_id, code)
                return {"produto_id": int(prow[0]), "plataforma_id": plat_id, "ml_mode": None}

    # 4. Busca genérica: produto cujo código aparece no texto
    cur.execute("SELECT id, codigo FROM produtos")
    for pid_p, cod in cur.fetchall():
        if cod and cod.upper() in code.upper():
            plat_key = None
            cl = code.lower()
            if "mercado" in cl or "mlp" in cl or "mlc" in cl or cl.endswith("ml"):
                plat_key = "mlp" if "premium" in cl or "mlp" in cl else ("mlc" if "classico" in cl or "mlc" in cl else "ml")
            elif "magalu" in cl:
                plat_key = "magalu"
            elif "shopee" in cl:
                plat_key = "shopee"
            if plat_key:
                plat_id = _find_plat_by_key(conn, plat_key)
                if plat_id:
                    _insert_qr_legacy(conn, int(pid_p), plat_id, code)
                    return {"produto_id": int(pid_p), "plataforma_id": plat_id, "ml_mode": None}

    return None


def get_qr_for_product(conn: sqlite3.Connection, produto_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT q.plataforma_id, p.nome, q.code, q.short_code, q.num_code, q.ml_mode
        FROM qr_codes q
        JOIN plataformas p ON p.id = q.plataforma_id
        WHERE q.produto_id=?
        ORDER BY p.nome
        """,
        (produto_id,),
    )
    out = []
    seen = set()
    for plat_id, nome, code, short, num, ml_mode in cur.fetchall():
        label = nome
        if nome == "Mercado Livre" and ml_mode:
            label = "Mercado Livre Premium" if ml_mode == "premium" else "Mercado Livre Clássico"
        if label in seen:
            continue
        seen.add(label)
        out.append({"plataforma_id": plat_id, "plataforma": label, "code": code, "short": short, "num": num, "ml_mode": ml_mode})
    return out
