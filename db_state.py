from dotenv import load_dotenv
load_dotenv()
import psycopg2, json, os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")
print(f"[DB] DATABASE_URL set: {bool(DATABASE_URL)}")

def get_conn():
    import re, time
    url = DATABASE_URL
    match = re.match(r'(?:postgresql|postgres)://([^:]+):([^@]+)@([^/:]+)(?::(\d+))?/([^?]+)', url)
    for attempt in range(3):
        try:
            if match:
                user, password, host, port, dbname = match.groups()
                conn = psycopg2.connect(
                    host=host,
                    port=int(port) if port else 5432,
                    user=user,
                    password=password,
                    dbname=dbname,
                    sslmode='require',
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )
            else:
                conn = psycopg2.connect(url, connect_timeout=10)
            return conn
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                raise e

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
            itype TEXT DEFAULT 'STOCK',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS itype TEXT DEFAULT 'STOCK'")
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
            val = row[0]
            # Handle both string and dict (jsonb auto-parsed by psycopg2)
            if isinstance(val, dict):
                return val
            return json.loads(val)
    except Exception as e:
        print(f"[DB] Load error: {e}")
    return None

def save_trade(trade):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        pnl_val = trade.get("pnl")
        pnl_val = float(pnl_val) if pnl_val not in (None, "", "—") else 0.0
        cur.execute("""
            INSERT INTO trades (date, time, symbol, action, price, qty, rsi, pnl, reason, itype)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now().strftime("%d-%b-%Y"),
            trade.get("time", ""),
            trade.get("symbol", ""),
            trade.get("action", ""),
            trade.get("price", 0),
            trade.get("qty", 0),
            round(trade.get("rsi", 0), 1),
            pnl_val,
            trade.get("reason", ""),
            trade.get("itype", "STOCK"),
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
        cur.execute("SELECT date, time, symbol, action, price, qty, rsi, pnl, reason, itype FROM trades ORDER BY created_at")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "date"      : r[0],
            "time"      : r[1], 
            "symbol"    : r[2],
            "action"    : r[3],
            "price"     : r[4],
            "buy_price" : r[4] if r[3] == "BUY" else "",
            "sell_price": r[4] if r[3] == "SELL" else "",
            "qty"       : r[5],
            "rsi"       : r[6],
            "pnl"       : r[7] if r[3] == "SELL" else "",
            "reason"    : r[8],
            "itype"     : r[9] if len(r) > 9 else "STOCK",
        } for r in rows]
    except Exception as e:
        print(f"[DB] Load trades error: {e}")
        return []