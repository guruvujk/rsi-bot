import psycopg2, json, os

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
