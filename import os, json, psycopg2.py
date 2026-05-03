import os, json, psycopg2

DATABASE_URL = "postgresql://neondb_owner:postgresql://neondb_owner:npg_8Wcu1zDxBrpm@ep-misty-butterfly-aonlxoat-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require@ep-misty-butterfly-aonlxoat.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
url = DATABASE_URL.replace("postgresql://", "postgres://")

with open("bot_state.json") as f:
    data = json.load(f)

conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)")
cur.execute("INSERT INTO bot_state (key, value) VALUES ('state', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (json.dumps(data),))
conn.commit()
cur.close()
conn.close()
print("Done! Capital:", data.get("capital"))
print("Positions:", len(data.get("positions", {})))