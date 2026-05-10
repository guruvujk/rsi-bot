from upstox_db import get_conn

conn = get_conn()
cur = conn.cursor()

cur.execute("DELETE FROM upstox_positions WHERE id IN (27, 28)")
print('Deleted:', cur.rowcount, 'rows')
conn.commit()

cur.execute("SELECT id, symbol, broker, source, qty, buy_price FROM upstox_positions WHERE symbol='SUNPHARMA.NS'")
print('Remaining:', cur.fetchall())
conn.close()
