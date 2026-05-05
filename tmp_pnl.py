from db_state import load_state
import yfinance as yf

s = load_state()
pos = s.get('positions', {})
total = 0
for sym, v in pos.items():
    ticker = sym
    try:
        price = yf.Ticker(ticker).fast_info['last_price']
        pnl = (price - v['buy_price']) * v['qty']
        total += pnl
        print(f"{sym:20s} Buy={v['buy_price']:.2f} Now={price:.2f} PnL={pnl:+.2f}")
    except Exception as e:
        print(f"{sym}: error - {e}")
print(f"Total PnL: {total:+.2f}")
