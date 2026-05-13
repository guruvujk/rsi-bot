import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=30)
stocks = ["SBIN.NS","INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS"]
RSI_BUY = 40

for symbol in stocks:
    df = yf.download(symbol, start=start-timedelta(days=60), end=end, interval="1d", progress=False, auto_adjust=True)
    if df.empty: continue
    close = df["Close"].squeeze()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    trades = 0
    position = None
    for i in range(14, len(df)):
        if df.index[i] < pd.Timestamp(start): continue
        price = float(close.iloc[i])
        rsi_val = float(rsi.iloc[i])
        if position is None and rsi_val < RSI_BUY:
            position = {"buy": price, "qty": int(15000/price)}
        elif position and (price >= position["buy"]*1.05 or price <= position["buy"]*0.97):
            pnl = (price - position["buy"]) * position["qty"]
            print(f"{symbol} BUY={position['buy']:.0f} SELL={price:.0f} PNL=Rs.{pnl:.0f}")
            trades += 1
            position = None
    print(f"{symbol} -> {trades} trades")
