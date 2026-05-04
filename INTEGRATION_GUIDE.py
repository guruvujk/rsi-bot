# ═══════════════════════════════════════════════════════════════
#  RSI BOT v3 — AUTO TRADE INTEGRATION GUIDE
#  Add these lines to your existing main.py
# ═══════════════════════════════════════════════════════════════

# ── STEP 1: Add to imports at top of main.py ──────────────────
from auto_trade_routes import auto_trade_bp
from auto_trade_engine  import start_scheduler

# ── STEP 2: Register blueprint (after app = Flask(__name__)) ──
app.register_blueprint(auto_trade_bp)

# ── STEP 3: Auto-start scheduler when server boots ────────────
# Add inside your if __name__ == "__main__": block or
# after app is created, before app.run():
start_scheduler()

# ═══════════════════════════════════════════════════════════════
#  COMPLETE INTEGRATION EXAMPLE (minimal main.py)
# ═══════════════════════════════════════════════════════════════
"""
from flask import Flask
from flask_socketio import SocketIO
from auto_trade_routes import auto_trade_bp
from auto_trade_engine  import start_scheduler
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

app.register_blueprint(auto_trade_bp)   # ← ADD THIS

# ... your existing routes ...

if __name__ == "__main__":
    start_scheduler()                    # ← ADD THIS
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
"""

# ═══════════════════════════════════════════════════════════════
#  API REFERENCE — All new endpoints
# ═══════════════════════════════════════════════════════════════
"""
SCHEDULER
─────────────────────────────────────────────────────────────────
POST /api/auto/start          Start background 15-min scanner
POST /api/auto/stop           Stop scheduler
GET  /api/auto/status         Scheduler status + open count

MANUAL TRADING
─────────────────────────────────────────────────────────────────
POST /api/auto/scan           Force scan now
  Body: {"symbols": ["RELIANCE.NS"], "force": true}
  force=true → bypass market hours check

POST /api/auto/close/RELIANCE.NS   Close single position at LTP
POST /api/auto/close-all           Close ALL open positions

MONITORING
─────────────────────────────────────────────────────────────────
GET  /api/auto/portfolio      Open positions + live P&L
GET  /api/auto/trades         Trade history
  ?type=BUY|SELL  ?symbol=RELIANCE.NS  ?limit=50
GET  /api/auto/inspect/RELIANCE.NS  Full filter pipeline debug

BLACKLIST
─────────────────────────────────────────────────────────────────
GET  /api/auto/blacklist           View blacklist + stats
POST /api/auto/blacklist/add       {"symbol":"X","reason":"y"}
POST /api/auto/blacklist/remove    {"symbol":"X"}

GAINERS
─────────────────────────────────────────────────────────────────
GET  /api/auto/gainers         Favorites / Stars / Legends
GET  /api/auto/watchlist       Current watchlist

═══════════════════════════════════════════════════════════════
 FILTER PIPELINE ORDER (each filter blocks if failed)
═══════════════════════════════════════════════════════════════
 1. Blacklist check      — instant reject from blacklist.json
 2. Earnings ≤3 days     — yfinance calendar
 3. ATR < 1.5%           — too quiet, skip
 4. Nifty50 sentiment    — price > 20-SMA AND RSI > 45
 5. News sentiment       — 2+ negative keywords in last 5 headlines
 6. RSI+MACD crossover   — RSI crosses above 35 AND MACD bull cross

═══════════════════════════════════════════════════════════════
 EXIT LOGIC
═══════════════════════════════════════════════════════════════
 Fixed SL   : exit if price drops 5% from buy price
 TSL         : activates when profit hits +10%
               trails 5% below peak price
               updates upward as price rises

═══════════════════════════════════════════════════════════════
 GAINER TIER POSITION SIZING
═══════════════════════════════════════════════════════════════
 NORMAL   → base ₹5,000  (1.0x)
 FAVORITE → ₹7,500       (1.5x)   win rate > 65%
 STAR     → ₹10,000      (2.0x)   win rate > 80%
 LEGEND   → ₹12,500      (2.5x)   win rate > 90%

═══════════════════════════════════════════════════════════════
 LOG FILES (auto-created in logs/)
═══════════════════════════════════════════════════════════════
 logs/paper_trades.json    — all buy/sell records
 logs/open_positions.json  — current open positions
 logs/blacklist.json       — blacklist + trade history
 logs/gainers.json         — tier + promotion history
"""
