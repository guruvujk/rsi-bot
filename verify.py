from upstox_db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT symbol, broker, qty, buy_price, tp_price, sl_price, tsl_active FROM upstox_positions ORDER BY id")
rows = cur.fetchall()
print(f'upstox_positions: {len(rows)} rows')
for r in rows:
    print(r)
conn.close()
