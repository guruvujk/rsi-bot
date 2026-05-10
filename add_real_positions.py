from db_state import get_conn

conn = get_conn()
cur = conn.cursor()

# First, clear existing SUNPHARMA entries
cur.execute("DELETE FROM upstox_positions WHERE symbol = 'SUNPHARMA.NS'")
print('Cleared existing SUNPHARMA entries')

# Add Groww position (23 shares)
cur.execute("""
    INSERT INTO upstox_positions 
    (symbol, itype, qty, buy_price, ltp, sl_price, is_open, broker, source, paper_mode, synced_at)
    VALUES 
    ('SUNPHARMA.NS', 'STOCK', 23, 1797.54, 1847.90, 1707.66, TRUE, 'Groww', 'groww', FALSE, NOW())
""")

# Add Kite position (2 shares)
cur.execute("""
    INSERT INTO upstox_positions 
    (symbol, itype, qty, buy_price, ltp, sl_price, is_open, broker, source, paper_mode, synced_at)
    VALUES 
    ('SUNPHARMA.NS', 'STOCK', 2, 1852.30, 1847.90, 1759.68, TRUE, 'Kite', 'kite', FALSE, NOW())
""")

# Add Upstox position (1 share)
cur.execute("""
    INSERT INTO upstox_positions 
    (symbol, itype, qty, buy_price, ltp, sl_price, is_open, broker, source, paper_mode, synced_at)
    VALUES 
    ('SUNPHARMA.NS', 'STOCK', 1, 1850.10, 1847.90, 1757.59, TRUE, 'Upstox', 'upstox', FALSE, NOW())
""")

conn.commit()
print('Added 3 SUNPHARMA positions (Groww, Kite, Upstox)')

# Verify
cur.execute('SELECT symbol, broker, qty, paper_mode FROM upstox_positions WHERE symbol = "SUNPHARMA.NS"')
print('\nAdded positions:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}, qty={row[2]}, is_real={row[3]==False}')

cur.close()
conn.close()
print('\nDone! Now restart your app: python main.py')