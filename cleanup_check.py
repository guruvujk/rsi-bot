from upstox_db import get_conn

conn = get_conn()
cur = conn.cursor()

cur.execute("SELECT id, symbol, broker, source, qty, buy_price FROM upstox_positions WHERE symbol='SUNPHARMA.NS'")
rows = cur.fetchall()
print('Current rows:')
for r in rows:
    print(r)

conn.close()
