import sqlite3
import os

db_path = r'c:\Projetos\Bellart\dist\bellart.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print(f"Checking {db_path}")
print("--- Plataformas ---")
try:
    cur.execute("SELECT id, nome FROM plataformas")
    for r in cur.fetchall():
        print(r)
except Exception as e:
    print(e)
