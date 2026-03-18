import sqlite3
try:
    conn = sqlite3.connect('bellart.db')
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(e)
