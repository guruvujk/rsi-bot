# debug_filters.py — run this to diagnose why no trades are generated
import yfinance as yf
import pandas as pd
from rsi_engine import compute_rsi, compute_macd, _safe_float
from config import WATCHLIST, RSI_BUY

print("=" * 70)
print(f"  RSI_BUY threshold in config.py: {RSI_BUY}")
print("=" * 70)
print(f"{'Symbol':<22} {'Bars':>5} {'RSI':>6} {'Vol':>6} {'MACD':>6} {'Trend':>6}")
print("-" * 70)

total_rsi = total_vol = total_macd = total_trend = 0

for symbol in WATCHLIST:
    try:
        df = yf.download(symbol, period="2y", interval="1d",
                         progress=False, auto_adjust=True, threads=False)
        if df is None or df.empty or len(df) < 50:
            print(f"{symbol:<22} {'NOT ENOUGH DATA':>5}")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)

        close  = df['Close'].squeeze()
        volume = df['Volume'].squeeze() if 'Volume' in df.columns else None

        rsi                            = compute_rsi(close)
        macd_line, sig_line, histogram = compute_macd(close)
        vol_avg = volume.rolling(20).mean() if volume is not None else None
        ema50   = close.ewm(span=50,  adjust=False).mean()
        ema200  = close.ewm(span=200, adjust=False).mean()

        r = v = m = t = 0
        for i in range(30, len(df)):
            price   = _safe_float(close.iloc[i])
            rsi_val = _safe_float(rsi.iloc[i], 50.0)
            mh_prev = _safe_float(histogram.iloc[i - 1])
            mh_curr = _safe_float(histogram.iloc[i])
            macd_rising = mh_curr > mh_prev

            vol_ok = True
            if vol_avg is not None:
                va     = _safe_float(vol_avg.iloc[i])
                vc     = _safe_float(volume.iloc[i])
                vol_ok = (vc > va) if va > 0 else True

            e50      = _safe_float(ema50.iloc[i])
            e200     = _safe_float(ema200.iloc[i])
            trend_ok = (price > e50) and (price > e200) and (e50 > e200)

            if rsi_val < RSI_BUY:                                          r += 1
            if rsi_val < RSI_BUY and vol_ok:                               v += 1
            if rsi_val < RSI_BUY and vol_ok and macd_rising:               m += 1
            if rsi_val < RSI_BUY and vol_ok and macd_rising and trend_ok:  t += 1

        print(f"{symbol:<22} {len(df):>5} {r:>6} {v:>6} {m:>6} {t:>6}")
        total_rsi += r; total_vol += v; total_macd += m; total_trend += t

    except Exception as e:
        print(f"{symbol:<22} ERROR: {e}")

print("-" * 70)
print(f"{'TOTAL':<22} {'':>5} {total_rsi:>6} {total_vol:>6} {total_macd:>6} {total_trend:>6}")
print("=" * 70)
print()
print("Column meanings:")
print("  RSI   = bars where RSI < RSI_BUY")
print("  Vol   = RSI + volume above average")
print("  MACD  = RSI + volume + MACD histogram rising")
print("  Trend = all above + price > EMA50 > EMA200  ← this must be > 0 for trades")
print()
if total_rsi == 0:
    print("❌ RSI column is 0 — RSI_BUY is set too LOW in config.py. Raise it (e.g. 35 or 40).")
elif total_trend == 0 and total_macd > 0:
    print("❌ Trend filter is killing all trades. EMA50/200 condition too strict.")
elif total_macd == 0 and total_vol > 0:
    print("❌ MACD filter is killing all trades.")
elif total_vol == 0 and total_rsi > 0:
    print("❌ Volume filter is killing all trades.")
else:
    print(f"✅ {total_trend} potential entry signals found. Check backtest logic if still 0 trades.")
