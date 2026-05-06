import re, psycopg2, json

DATABASE_URL = "postgresql://neondb_owner:npg_nGNplEws72Io@ep-misty-butterfly-aonlxoat.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
match = re.match(r'(?:postgresql|postgres)://([^:]+):([^@]+)@([^/:]+)(?::(\d+))?/([^?]+)', DATABASE_URL)
user, password, host, port, dbname = match.groups()
conn = psycopg2.connect(host=host, port=5432, user=user, password=password, dbname=dbname.split('?')[0], sslmode='require')
cur = conn.cursor()

# Wipe state
reset = json.dumps({"capital": 100000, "positions": {}})
cur.execute("UPDATE bot_state SET value = %s WHERE key = 'state'", (reset,))

# Also delete all trades
cur.execute("DELETE FROM trades")

conn.commit()
print("Force reset done.")
cur.execute("SELECT value FROM bot_state WHERE key = 'state'")
row = cur.fetchone()
data = json.loads(row[0])
print("Capital:", data.get("capital"))
print("Positions:", len(data.get("positions", {})))
cur.close()
conn.close()