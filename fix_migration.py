import sqlite3
import os
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else r'c:\Projetos\Bellart\bellart.db'

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

print(f"--- Fixing {db_path} ---")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("Checking platforms...")
cur.execute("SELECT nome FROM plataformas")
plats = [r[0] for r in cur.fetchall()]
print(f"Current platforms: {plats}")

if "Mercado Livre Clássico" not in plats:
    print("Migrating...")
    # Reset flag
    cur.execute("DELETE FROM configuracoes WHERE chave='ml_split_done'")
    conn.commit()
    
    # Create platforms
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Mercado Livre Clássico",))
    cur.execute("INSERT OR IGNORE INTO plataformas(nome) VALUES (?)", ("Mercado Livre Premium",))
    conn.commit()
    
    # Get IDs
    cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre'")
    row = cur.fetchone()
    if row:
        ml_id = row[0]
        cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre Clássico'")
        cl_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM plataformas WHERE nome='Mercado Livre Premium'")
        pr_id = cur.fetchone()[0]
        
        # Copy prices
        cur.execute("SELECT produto_id, preco_venda FROM precos_plataforma WHERE plataforma_id=?", (ml_id,))
        rows = cur.fetchall()
        print(f"Copying {len(rows)} prices from ML to new tiers...")
        for pid, val in rows:
            cur.execute("INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (pid, cl_id, val))
            cur.execute("INSERT OR IGNORE INTO precos_plataforma(produto_id, plataforma_id, preco_venda) VALUES (?, ?, ?)", (pid, pr_id, val))
        
        # Copy taxes
        cur.execute("SELECT percentual, valor_fixo, imposto_percentual FROM taxas_plataforma WHERE plataforma_id=?", (ml_id,))
        tax = cur.fetchone() or (0,0,0)
        print(f"Copying taxes: {tax}")
        cur.execute("INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (cl_id, tax[0], tax[1], tax[2]))
        cur.execute("INSERT OR IGNORE INTO taxas_plataforma(plataforma_id, percentual, valor_fixo, imposto_percentual) VALUES (?, ?, ?, ?)", (pr_id, tax[0], tax[1], tax[2]))
        
    cur.execute("INSERT OR REPLACE INTO configuracoes(chave, valor) VALUES ('ml_split_done', '1')")
    conn.commit()
    print("Migration done.")
else:
    print("Migration already applied.")
