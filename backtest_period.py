# backtest_period.py — Run backtest for any period
# Usage:
#   python backtest_period.py 30     → last 30 days
#   python backtest_period.py 60     → last 60 days
#   python backtest_period.py 90     → last 90 days
#   python backtest_period.py 180    → last 6 months
#   python backtest_period.py 365    → last 1 year
#   python backtest_period.py        → defaults to 30 days

import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import WATCHLIST, RSI_BUY, RSI_SELL, CAPITAL, MAX_CAPITAL_PER_TRADE, get_instrument_type
from rsi_engine import compute_rsi, compute_macd, _safe_float

# ── Period ────────────────────────────────────────────────
days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
end   = datetime.today()
start = end - timedelta(days=days)

print("=" * 60)
print(f"  BACKTEST — LAST {days} DAYS")
print(f"  From : {start.strftime('%d-%b-%Y')}")
print(f"  To   : {end.strftime('%d-%b-%Y')}")
print(f"  RSI Buy: {RSI_BUY} | Capital/Trade: Rs.{MAX_CAPITAL_PER_TRADE:,}")
print(f"  Symbols: {len(WATCHLIST)}")
print("=" * 60)

all_trades = []

for symbol in WATCHLIST:
    try:
        # Fetch extra 60 days before start so indicators warm up
        df = yf.download(symbol,
                         start=start - timedelta(days=60),
                         end=end,
                         interval='1d',
                         progress=False,
                         auto_adjust=True,
                         threads=False)
        if df is None or df.empty or len(df) < 30:
            print(f"  {symbol:<22} -> no data")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)

        close   = df['Close'].squeeze()
        rsi     = compute_rsi(close)
        macd_line, sig_line, histogram = compute_macd(close)
        ema200  = close.ewm(span=200, adjust=False).mean()
        volume  = df['Volume'].squeeze() if 'Volume' in df.columns else None
        vol_avg = volume.rolling(20).mean() if volume is not None else None

        itype  = get_instrument_type(symbol)
        sl_pct = 0.015 if itype == "STOCK" else 0.020

        trades   = 0
        position = None

        for i in range(30, len(df)):
            if df.index[i] < pd.Timestamp(start):
                continue

            price    = _safe_float(close.iloc[i])
            rsi_val  = _safe_float(rsi.iloc[i], 50.0)
            macd_val = _safe_float(macd_line.iloc[i])
            macd_s   = _safe_float(sig_line.iloc[i])
            macd_bull   = macd_val > macd_s
            mh_prev     = _safe_float(histogram.iloc[i - 1])
            mh_curr     = _safe_float(histogram.iloc[i])
            macd_rising = mh_curr > mh_prev

            vol_ok = True
            if vol_avg is not None:
                va     = _safe_float(vol_avg.iloc[i])
                vc     = _safe_float(volume.iloc[i])
                vol_ok = (vc > va) if va > 0 else True

            e200     = _safe_float(ema200.iloc[i])
            trend_ok = price > e200

            # ── EXIT ─────────────────────────────────────
            if position:
                bp       = position['buy_price']
                highest  = position.get('highest_price', bp)
                chg      = (price - bp) / bp

                if price > highest:
                    position['highest_price'] = price
                    highest = price

                # TSL activation
                if not position.get('tsl_active') and chg >= 0.03 * 0.4:
                    position['tsl_active'] = True

                if position.get('tsl_active'):
                    profit    = highest - bp
                    tsl_price = bp + (profit * 0.5)
                    if tsl_price > position['stop_loss']:
                        position['stop_loss'] = tsl_price

                reason = None
                if price <= position['stop_loss']:
                    reason = "STOP LOSS"
                elif chg >= 0.03:
                    reason = "TARGET HIT"
                elif rsi_val > RSI_SELL and not macd_bull:
                    reason = "RSI SELL"

                if reason:
                    pnl = (price - bp) * position['qty']
                    all_trades.append({
                        'symbol'   : symbol.replace('.NS', ''),
                        'type'     : itype,
                        'buy_date' : position['buy_date'].strftime('%d-%b'),
                        'sell_date': df.index[i].strftime('%d-%b'),
                        'buy'      : round(bp, 2),
                        'sell'     : round(price, 2),
                        'qty'      : position['qty'],
                        'pnl'      : round(pnl, 2),
                        'pnl_pct'  : round(chg * 100, 2),
                        'reason'   : reason,
                        'result'   : 'WIN' if pnl > 0 else 'LOSS'
                    })
                    trades += 1
                    position = None

            # ── ENTRY ─────────────────────────────────────
            elif rsi_val < RSI_BUY and vol_ok and macd_rising and trend_ok:
                qty = int(MAX_CAPITAL_PER_TRADE / price)
                if qty > 0:
                    position = {
                        'buy_price'    : price,
                        'buy_date'     : df.index[i],
                        'qty'          : qty,
                        'stop_loss'    : round(price * (1 - sl_pct), 4),
                        'highest_price': price,
                        'tsl_active'   : False,
                    }

        print(f"  {symbol:<22} -> {trades} trades")

    except Exception as e:
        print(f"  {symbol:<22} -> error: {e}")

# ── Results ───────────────────────────────────────────────
print("=" * 60)
print(f"  Total trades: {len(all_trades)}")

if all_trades:
    df_t   = pd.DataFrame(all_trades)
    wins   = df_t[df_t['result'] == 'WIN']
    losses = df_t[df_t['result'] == 'LOSS']
    total_pnl = df_t['pnl'].sum()

    print(f"  Win Rate    : {len(wins) / len(df_t) * 100:.1f}%")
    print(f"  Total P&L   : Rs.{total_pnl:,.2f}")
    print(f"  Avg Win     : Rs.{wins['pnl'].mean():,.2f}" if len(wins) > 0 else "  Avg Win     : N/A")
    print(f"  Avg Loss    : Rs.{losses['pnl'].mean():,.2f}" if len(losses) > 0 else "  Avg Loss    : N/A")
    print(f"  Return      : {total_pnl / CAPITAL * 100:.2f}%")
    print("=" * 60)
    print()
    print(df_t.to_string(index=False))
else:
    print(f"  No trades found in last {days} days.")
    print("  (Market may have been in uptrend — RSI stayed above buy threshold)")

print("=" * 60)
