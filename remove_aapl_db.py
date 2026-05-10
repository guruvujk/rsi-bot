from upstox_db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute("DELETE FROM upstox_positions WHERE symbol='AAPL'")
print('Deleted:', cur.rowcount)
conn.commit()
conn.close()
