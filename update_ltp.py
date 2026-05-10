import yfinance as yf
from upstox_db import get_conn
from datetime import datetime

symbols = ['ITC.NS','WIPRO.NS','MARUTI.NS','SUNPHARMA.NS']
conn = get_conn()
cur = conn.cursor()
for sym in symbols:
    try:
        df = yf.download(sym, period='1d', interval='1m', progress=False, auto_adjust=True)
        if df.empty:
            print(sym + ': empty')
            continue
        val = df['Close'].iloc[-1]
        if hasattr(val, 'iloc'):
            val = val.iloc[0]
        ltp = round(float(val), 2)
        cur.execute('SELECT buy_price FROM upstox_positions WHERE symbol=%s', (sym,))
        row = cur.fetchone()
        if not row:
            print(sym + ': not in db')
            continue
        buy = row[0]
        pnl = round(ltp - buy, 2)
        pnl_pct = round((pnl / buy) * 100, 2)
        cur.execute('UPDATE upstox_positions SET ltp=%s,pnl=%s,pnl_pct=%s,synced_at=%s WHERE symbol=%s', (ltp, pnl, pnl_pct, datetime.now(), sym))
        print(sym + ': LTP=' + str(ltp) + ' PnL=' + str(pnl))
    except Exception as e:
        print(sym + ': ERROR ' + str(e))
conn.commit()
conn.close()
print('Done.')