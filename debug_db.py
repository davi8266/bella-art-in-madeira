import sqlite3
import os

db_path = r'c:\Projetos\Bellart\bellart.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("--- Plataformas ---")
cur.execute("SELECT id, nome FROM plataformas")
for r in cur.fetchall():
    print(r)

print("\n--- Configs (ml_split_done) ---")
cur.execute("SELECT * FROM configuracoes WHERE chave='ml_split_done'")
print(cur.fetchall())

print("\n--- Configs (tax_ml_%) ---")
cur.execute("SELECT * FROM configuracoes WHERE chave LIKE 'tax_ml_%'")
print(cur.fetchall())
