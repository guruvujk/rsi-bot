from upstox_db import get_conn

conn = get_conn()
cur  = conn.cursor()
cur.execute("DELETE FROM upstox_positions")
print('Deleted rows:', cur.rowcount)
conn.commit()

cur.execute("SELECT COUNT(1) FROM upstox_positions")
print('Remaining:', cur.fetchone()[0])
conn.close()
