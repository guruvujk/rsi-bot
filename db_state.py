import psycopg2, json, os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            date TEXT,
            time TEXT,
            symbol TEXT,
            action TEXT,
            price REAL,
            qty INTEGER,
            rsi REAL,
            pnl REAL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_state(state):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bot_state (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, ("state", json.dumps(state)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Save error: {e}")

def load_state():
    if not DATABASE_URL:
        return None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_state WHERE key = %s", ("state",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        print(f"[DB] Load error: {e}")
    return None

def save_trade(trade):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trades (date, time, symbol, action, price, qty, rsi, pnl, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now().strftime("%d-%b-%Y"),
            trade.get("time", ""),
            trade.get("symbol", ""),
            trade.get("action", ""),
            trade.get("price", 0),
            trade.get("qty", 0),
            round(trade.get("rsi", 0), 1),
            trade.get("pnl") if trade.get("pnl") is not None else 0,
            trade.get("reason", ""),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Trade save error: {e}")

def load_trades():
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT date, time, symbol, action, price, qty, rsi, pnl, reason FROM trades ORDER BY created_at")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"date":r[0],"time":r[1],"symbol":r[2],"action":r[3],
                 "price":r[4],"qty":r[5],"rsi":r[6],"pnl":r[7],"reason":r[8]} for r in rows]
    except Exception as e:
        print(f"[DB] Load trades error: {e}")
        return []