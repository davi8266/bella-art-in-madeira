import sqlite3
try:
    conn = sqlite3.connect('bellart.db')
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM qr_codes WHERE ml_mode IN ('premium', 'classico')")
    print(f"Count: {cur.fetchone()[0]}")
    
    cur.execute("SELECT produto_id, plataforma_id, ml_mode, code FROM qr_codes WHERE ml_mode IN ('premium', 'classico') LIMIT 5")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(e)
