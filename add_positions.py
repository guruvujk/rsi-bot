from upstox_db import get_conn
from datetime import datetime

conn = get_conn()
cur = conn.cursor()

positions_to_add = [
    # (symbol, broker, qty, buy_price, tp_price, sl_price)
    ('ITC.NS',    'Groww', 16,  309.95,   round(309.95 * 1.08, 2), 303.75),
    ('WIPRO.NS',  'Groww', 52,  198.00,   round(198.00 * 1.08, 2), 194.04),
    ('MARUTI.NS', 'Kite',   1,  13679.00, round(13679.00 * 1.08, 2), 13405.42),
]

for sym, broker, qty, buy, tp, sl in positions_to_add:
    # Check if already exists
    cur.execute("SELECT id FROM upstox_positions WHERE symbol=%s AND broker=%s", (sym, broker))
    if cur.fetchone():
        print(f"SKIP (exists): {sym} / {broker}")
        continue
    cur.execute("""
        INSERT INTO upstox_positions (symbol, broker, qty, buy_price, tp_price, sl_price, itype, tsl_active, synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'STOCK', false, %s)
    """, (sym, broker, qty, buy, tp, sl, datetime.now().strftime('%d-%b-%Y %H:%M')))
    print(f"ADDED: {sym} | {broker} | qty={qty} | buy={buy} | tp={tp} | sl={sl}")

conn.commit()
conn.close()
print("Done.")
