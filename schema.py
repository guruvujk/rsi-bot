from upstox_db import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'upstox_positions'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(r)
conn.close()
