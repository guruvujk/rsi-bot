from upstox_db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id, symbol, broker, paper_mode, source, is_open FROM upstox_positions")
for r in cur.fetchall():
    print(r)
conn.close()
