import sqlite3
import os

db_path = r'c:\Projetos\Bellart\bellart.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print(f"Checking {db_path}")
try:
    cur.execute("SELECT COUNT(*) FROM plataformas")
    print(f"Plataformas count: {cur.fetchone()[0]}")
    cur.execute("SELECT id, nome FROM plataformas")
    print(cur.fetchall())
except Exception as e:
    print(f"Error: {e}")
