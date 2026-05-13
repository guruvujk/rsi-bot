import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import WATCHLIST, RSI_BUY, RSI_SELL, CAPITAL, MAX_CAPITAL_PER_TRADE, get_instrument_type
from rsi_engine import compute_rsi, compute_macd, _safe_float

end = datetime.today()
start = end - timedelta(days=60)

print("=" * 60)
print(f"  LAST 30 DAYS BACKTEST")
print(f"  From: {start.strftime('%d-%b-%Y')}  To: {end.strftime('%d-%b-%Y')}")
print(f"  RSI Buy: {RSI_BUY} | Capital/Trade: Rs.{MAX_CAPITAL_PER_TRADE:,}")
print("=" * 60)

all_trades = []

for symbol in WATCHLIST:
    try:
        df = yf.download(symbol, start=start - timedelta(days=60), end=end,
                         interval='1d', progress=False, auto_adjust=True, threads=False)
        if df is None or df.empty or len(df) < 30:
            print(f"  {symbol:<20} -> no data")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)

        close = df['Close'].squeeze()
        rsi = compute_rsi(close)
        macd_line, sig_line, histogram = compute_macd(close)
        ema200 = close.ewm(span=200, adjust=False).mean()
        volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
        vol_avg = volume.rolling(20).mean() if volume is not None else None

        trades = 0
        position = None

        for i in range(30, len(df)):
            if df.index[i] < pd.Timestamp(start):
                continue
            price    = _safe_float(close.iloc[i])
            rsi_val  = _safe_float(rsi.iloc[i], 50.0)
            macd_val = _safe_float(macd_line.iloc[i])
            macd_s   = _safe_float(sig_line.iloc[i])
            macd_bull    = macd_val > macd_s
            mh_prev      = _safe_float(histogram.iloc[i - 1])
            mh_curr      = _safe_float(histogram.iloc[i])
            macd_rising  = mh_curr > mh_prev

            vol_ok = True
            if vol_avg is not None:
                va     = _safe_float(vol_avg.iloc[i])
                vc     = _safe_float(volume.iloc[i])
                vol_ok = (vc > va) if va > 0 else True

            e200     = _safe_float(ema200.iloc[i])
            trend_ok = price > e200

            if position:
                bp  = position['buy_price']
                chg = (price - bp) / bp
                if (price <= position['stop_loss'] or
                        chg >= 0.03 or
                        (rsi_val > RSI_SELL and not macd_bull)):
                    pnl = (price - bp) * position['qty']
                    all_trades.append({
                        'symbol'   : symbol,
                        'buy_date' : position['buy_date'].strftime('%d-%b'),
                        'sell_date': df.index[i].strftime('%d-%b'),
                        'buy'      : round(bp, 2),
                        'sell'     : round(price, 2),
                        'qty'      : position['qty'],
                        'pnl'      : round(pnl, 2),
                        'result'   : 'WIN' if pnl > 0 else 'LOSS'
                    })
                    trades += 1
                    position = None

            elif rsi_val < RSI_BUY and vol_ok and macd_rising and trend_ok:
                qty = int(MAX_CAPITAL_PER_TRADE / price)
                if qty > 0:
                    position = {
                        'buy_price': price,
                        'buy_date' : df.index[i],
                        'qty'      : qty,
                        'stop_loss': round(price * 0.985, 4)
                    }

        print(f"  {symbol:<20} -> {trades} trades")

    except Exception as e:
        print(f"  {symbol:<20} -> error: {e}")

print("=" * 60)
print(f"  Total trades: {len(all_trades)}")

if all_trades:
    df_t = pd.DataFrame(all_trades)
    wins = df_t[df_t['result'] == 'WIN']
    print(f"  Win Rate    : {len(wins) / len(df_t) * 100:.1f}%")
    print(f"  Total P&L   : Rs.{df_t['pnl'].sum():,.2f}")
    print("=" * 60)
    print()
    print(df_t.to_string(index=False))
else:
    print("  No trades in last 30 days.")
print("=" * 60)
