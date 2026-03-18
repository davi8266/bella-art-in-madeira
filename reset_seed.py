import sqlite3
import os

db_path = r'c:\Projetos\Bellart\bellart.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print(f"Fixing {db_path}")
# Check if Magalu exists
cur.execute("SELECT count(*) FROM plataformas WHERE nome='Magalu'")
if cur.fetchone()[0] == 0:
    print("Magalu missing. Resetting seed_done.")
    cur.execute("DELETE FROM configuracoes WHERE chave='seed_done'")
    conn.commit()
else:
    print("Magalu exists.")
