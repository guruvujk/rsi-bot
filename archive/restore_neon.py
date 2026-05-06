import json, psycopg2, re

DATABASE_URL = "postgresql://neondb_owner:npg_nGNplEws72Io@ep-misty-butterfly-aonlxoat.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

match = re.match(r'postgresql://([^:]+):([^@]+)@([^/]+)/(.+)', DATABASE_URL)
user, password, host, dbname = match.groups()
conn = psycopg2.connect(host=host, user=user, password=password, dbname=dbname.split("?")[0], sslmode='require')
cur = conn.cursor()

with open("bot_state.json") as f:
    data = json.load(f)

# Restore state
cur.execute("CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)")
cur.execute("INSERT INTO bot_state (key, value) VALUES ('state', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (json.dumps(data),))

# Restore trades
cur.execute("""CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY, date TEXT, time TEXT, symbol TEXT,
    action TEXT, price REAL, qty INTEGER, rsi REAL, pnl REAL,
    reason TEXT, itype TEXT DEFAULT 'STOCK',
    created_at TIMESTAMP DEFAULT NOW()
)""")
trades = data.get("trades", [])
for t in trades:
    cur.execute("INSERT INTO trades (date,time,symbol,action,price,qty,rsi,pnl,reason,itype) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (t.get("date",""), t.get("time",""), t.get("symbol",""), t.get("action",""),
         t.get("price",0), t.get("qty",0), t.get("rsi",0), t.get("pnl") or 0,
         t.get("reason",""), t.get("itype","STOCK")))

conn.commit()
cur.close()
conn.close()
print("Done! Capital:", data.get("capital"))
print("Positions:", len(data.get("positions", {})))
print("Trades inserted:", len(trades))