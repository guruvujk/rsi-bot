# 📈 RSI Bot v2 — All Instruments Edition

Paper trading bot supporting all major instrument types with
RSI + MACD + Bollinger Bands signals. Auto-logs to CSV and Excel.

---

## 🗂️ Project Structure

```
rsi_bot/
├── main.py                  ← Run this to start the bot
├── config.py                ← ALL settings — edit this file
├── rsi_engine.py            ← RSI + MACD + BB calculations
├── paper_trade.py           ← Trade simulator + Excel logger
├── dashboard.py             ← Web dashboard (Flask)
├── telegram_alerts.py       ← Telegram notifications
├── requirements.txt         ← Dependencies
├── rsi_bot.code-workspace   ← Open this in VS Code
└── logs/
    ├── paper_trades.csv     ← Auto-created
    └── Trading_Journal.xlsx ← Auto-created + auto-updated
```

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Edit config.py — add your Telegram token
# 3. Run the bot
python main.py

# 4. Open dashboard
# http://127.0.0.1:5000
```

---

## 📊 Supported Instruments (A + B + C)

### Option A — Indian Markets
| Type | Examples | Hours IST |
|---|---|---|
| 🏦 NSE Stocks | RELIANCE, TCS, INFY (40+ stocks) | Mon–Fri 9:15–15:30 |
| 📈 Indices | Nifty50, BankNifty, IT, Pharma (11) | Mon–Fri 9:15–15:30 |
| 📊 ETFs | NiftyBees, GoldBees, BankBees (8) | Mon–Fri 9:15–15:30 |

### Option B — Global Markets
| Type | Examples | Hours IST |
|---|---|---|
| 💰 Commodities | Gold, Silver, Oil, Gas, Wheat (16) | Mon–Fri 9:00–23:30 |
| 💱 Forex | USD/INR, EUR/USD, GBP/USD (18 pairs) | 24h Weekdays |

### Option C — 24/7 Markets
| Type | Examples | Hours IST |
|---|---|---|
| 🪙 Crypto | BTC, ETH, SOL, XRP, DOGE (20 coins) | 24/7/365 |
| 🌍 US Stocks | AAPL, MSFT, NVDA, GOOGL (25 stocks) | Mon–Fri 7PM–1:30AM |

---

## ⚙️ Enable/Disable Markets

In `config.py`, simply set `"enabled": True` or `"enabled": False`:

```python
STOCKS      = {"enabled": True,  "symbols": [...]}   # ON
INDICES     = {"enabled": True,  "symbols": [...]}   # ON
ETFS        = {"enabled": True,  "symbols": [...]}   # ON
COMMODITIES = {"enabled": True,  "symbols": [...]}   # ON
FOREX       = {"enabled": True,  "symbols": [...]}   # ON
CRYPTO      = {"enabled": True,  "symbols": [...]}   # ON
US_STOCKS   = {"enabled": True,  "symbols": [...]}   # ON
```

---

## 📱 Telegram Alerts

| Time | Alert |
|---|---|
| 9:00 AM | Morning briefing |
| Any time | BUY signal with RSI + BB info |
| Any time | SELL signal with P&L |
| 3:25 PM | NSE closing warning |
| 3:35 PM | NSE end of day summary |
| 11:00 PM | Crypto positions update |
| 11:25 PM | MCX commodities closing |

---

## 📊 Excel Auto-Updates

`logs/Trading_Journal.xlsx` updates automatically on every trade:

| Sheet | Content |
|---|---|
| Trade Log | Every BUY/SELL with RSI, MACD, BB % |
| Daily Summary | Daily wins/losses/P&L |
| By Instrument | Performance per stock/crypto/forex |
| Stats | Live portfolio metrics |

---

## 🔧 TradingView Integration (Option B)

Use `TRADINGVIEW_WATCHLIST` from config.py to add symbols on TradingView:
```
NSE:RELIANCE   NSE:TCS      NSE:NIFTY
BINANCE:BTCUSDT             FX:USDINR
MCX:GOLD       NASDAQ:AAPL
```
Go to TradingView → Watchlist → Add Symbol → paste any of the above.

---

## ✅ Move to Real Money When

- [ ] 3 weeks of paper trading complete
- [ ] Win rate above 50% for 2 consecutive weeks
- [ ] Trade log filled every day
- [ ] No emotional decisions made
- [ ] Bot profitable 2 weeks in a row
- [ ] Have dedicated capital (not emergency money)

---

## 📞 Support

Review `logs/paper_trades.csv` weekly.
Check `logs/Trading_Journal.xlsx` daily.
