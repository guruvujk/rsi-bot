import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

end = datetime.today()
start = end - timedelta(days=180)
stocks = ["SBIN.NS","INFY.NS","TCS.NS","RELIANCE.NS","HDFCBANK.NS"]
RSI_BUY = 35

for symbol in stocks:
    df = yf.download(symbol, start=start-timedelta(days=120), end=end, interval="1d", progress=False, auto_adjust=True)
    if df.empty: continue
    close = df["Close"].squeeze()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    ma200 = close.rolling(200).mean()
    trades = 0
    position = None
    for i in range(16, len(df)):
        if df.index[i].date() < start.date(): continue
        price = float(close.iloc[i])
        rsi_today = float(rsi.iloc[i])
        rsi_d1 = float(rsi.iloc[i-1])
        rsi_d2 = float(rsi.iloc[i-2])
        bounce = rsi_d2 < RSI_BUY and rsi_d1 > RSI_BUY and rsi_today > RSI_BUY and price > float(close.iloc[i-1])
        ma200_today = float(ma200.iloc[i])
        above_trend = price > ma200_today
        bounce = rsi_d2 < RSI_BUY and rsi_d1 > RSI_BUY and rsi_today > RSI_BUY and above_trend and price > float(close.iloc[i-1])
        if position is None and bounce:
            position = {"buy": price, "qty": int(15000/price)}
        elif position and (price >= position["buy"]*1.05 or price <= position["buy"]*0.97):
            pnl = (price - position["buy"]) * position["qty"]
            print(f"{symbol} BUY={position['buy']:.0f} SELL={price:.0f} PNL=Rs.{pnl:.0f}")
            trades += 1
            position = None
    print(f"{symbol} -> {trades} trades")
