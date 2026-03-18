import sqlite3
import os

db_path = r'c:\Projetos\Bellart\dist\bellart.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print(f"Checking {db_path}")
print("--- Configs (ml_split_done) ---")
try:
    cur.execute("SELECT * FROM configuracoes WHERE chave='ml_split_done'")
    print(cur.fetchall())
except Exception as e:
    print(e)
