from upstox_db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute("DELETE FROM upstox_positions WHERE id=33")
print("Deleted duplicate:", cur.rowcount)
conn.commit()
conn.close()
