from auto_trade_engine import load_open_positions, check_rsi_overbought, calc_rsi
import yfinance as yf

positions = load_open_positions()
print(f"Open positions: {list(positions.keys())}\n")

for sym, pos in positions.items():
    try:
        df = yf.download(pos.get("symbol", sym.split("_")[0]), period="90d", interval="1d", progress=False, auto_adjust
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        price = float(df["Close"].squeeze().iloc[-1])
        rsi_series = calc_rsi(df["Close"].squeeze())
        rsi_val = round(float(rsi_series.iloc[-1]), 2)
        ob, ob_rsi = check_rsi_overbought(df)
        sl  = pos.get("sl_price", "MISSING")
        tp  = pos.get("tp_price", "MISSING")
        buy = pos.get("buy_price", "?")
        print(f"{sym}")
        print(f"  buy={buy}  price={price:.2f}  sl={sl}  tp={tp}")
        print(f"  RSI={rsi_val}  overbought_cross={ob}")
        print()
    except Exception as e:
        print(f"{sym}: ERROR — {e}\n")
