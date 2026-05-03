import re, psycopg2, json
DATABASE_URL = "postgresql://neondb_owner:npg_nGNplEws72Io@ep-misty-butterfly-aonlxoat.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
match = re.match(r'(?:postgresql|postgres)://([^:]+):([^@]+)@([^/:]+)(?::(\d+))?/([^?]+)', DATABASE_URL)
user, password, host, port, dbname = match.groups()
conn = psycopg2.connect(host=host, port=5432, user=user, password=password, dbname=dbname.split('?')[0], sslmode='require')
cur = conn.cursor()
reset = json.dumps({"capital": 100000, "positions": {}})
cur.execute("UPDATE bot_state SET value = %s WHERE key = 'state'", (reset,))
conn.commit()
print("Reset done. Rows updated:", cur.rowcount)
cur.close()
conn.close()