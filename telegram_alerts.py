# telegram_alerts.py — Complete Integration (Telegram + Local API)
import requests
import os
import threading
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ── CONFIGURATION ──────────────────────────────────────
# Point to your LOCAL backend (FastAPI)
API_BASE_URL = "http://localhost:5000/api"

TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERT_EMOJI = {
    "BUY"  : "🟢",
    "SELL" : "🔴",
    "INFO" : "ℹ️",
    "START": "🚀",
    "STOP" : "🛑",
    "WARN" : "⚠️",
}

# ── TELEGRAM FUNCTIONS ─────────────────────────────────
def send_telegram(message: str, alert_type: str = "INFO") -> bool:
    import os
    if os.environ.get("TELEGRAM_ENABLED", "true").lower() == "false":
        return False
    try:
        emoji = ALERT_EMOJI.get(alert_type, "📢")
        payload = {
            "chat_id"   : TELEGRAM_CHAT_ID,
            "text"      : f"{emoji} {message}",
            "parse_mode": "Markdown",
        }
        resp = requests.post(TELEGRAM_BASE_URL, data=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"  [Telegram] {e}")
        return False

def alert_buy(symbol, price, qty, rsi, sl, target, capital_left, itype):
    send_telegram(
        f"*BUY SIGNAL — {itype}*\n"
        f"Symbol : *{symbol}*\n"
        f"Price  : {price}\n"
        f"Qty    : {qty}\n"
        f"RSI    : {rsi:.1f}\n"
        f"SL     : {sl}\n"
        f"Target : {target}\n"
        f"Capital: ₹{capital_left:,.0f}",
        "BUY"
    )

def alert_sell(symbol, price, qty, reason, pnl, total_pnl, capital, itype):
    send_telegram(
        f"*SELL SIGNAL — {itype}*\n"
        f"Symbol : *{symbol}*\n"
        f"Price  : {price}\n"
        f"Qty    : {qty}\n"
        f"Reason : {reason}\n"
        f"P&L    : ₹{pnl:,.2f}\n"
        f"Total P&L: ₹{total_pnl:,.2f}\n"
        f"Capital: ₹{capital:,.0f}",
        "SELL"
    )

def alert_summary(trades, total_pnl, capital):
    wins   = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) <= 0]
    wr     = round(len(wins) / len(trades) * 100, 1) if trades else 0
    send_telegram(
        f"*End of Day Summary*\n"
        f"Trades   : {len(trades)}\n"
        f"Wins     : {len(wins)}\n"
        f"Losses   : {len(losses)}\n"
        f"Win Rate : {wr}%\n"
        f"Total P&L: ₹{total_pnl:,.2f}\n"
        f"Capital  : ₹{capital:,.0f}",
        "INFO"
    )

# ── LOCAL API SYNC FUNCTIONS (For Dashboard) ───────────
def clean_price(p):
    """Helper to clean price strings like '₹1,200.50' -> 1200.50"""
    try:
        return float(str(p).replace('₹','').replace('$','').replace(',','').strip())
    except:
        return 0.0

def sync_buy_to_api(symbol, price, qty, sl, target, rsi, itype):
    """Send BUY trade to Local Backend API"""
    try:
        data = {
            "symbol": symbol,
            "direction": "BUY",
            "price": clean_price(price),
            "qty": qty,
            "stop_loss": clean_price(sl),
            "target": clean_price(target),
            "rsi_value": rsi,
            "reason": f"RSI {rsi:.1f} < 30",
            "instrument_type": itype
        }
        resp = requests.post(f"{API_BASE_URL}/trade", json=data, timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ API: BUY {symbol} synced to Dashboard")
            return True
    except Exception as e:
        print(f"  ⚠️ API Sync Failed: {e}")
        return False

def sync_sell_to_api(symbol, price, qty, pnl, reason, itype="CRYPTO"):
    """Send SELL trade to Local Backend API"""
    try:
        data = {
            "symbol": symbol,
            "direction": "SELL",
            "price": clean_price(price),
            "qty": qty,
            "stop_loss": 0,
            "target": 0,
            "rsi_value": 0,
            "reason": reason,
            "instrument_type": itype
        }
        resp = requests.post(f"{API_BASE_URL}/trade", json=data, timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ API: SELL {symbol} synced to Dashboard")
            return True
    except Exception as e:
        print(f"  ⚠️ API Sync Failed: {e}")
        return False

def update_position_price(symbol, current_price):
    """Update live P&L on Dashboard"""
    try:
        requests.post(
            f"{API_BASE_URL}/position/update",
            json={"symbol": symbol, "current_price": float(current_price)},
            timeout=3
        )
    except:
        pass
# ── VOICE ALERTS ───────────────────────────────────────
def speak_alert(message: str):
    """Text-to-speech alert using gTTS — runs in background thread."""
    try:
        from config import VOICE_ALERTS
        if not VOICE_ALERTS:
            return
    except:
        return
    def _speak():
        try:
            from gtts import gTTS
            import tempfile
            tts = gTTS(text=message, lang='en')
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(tmp.name)
            os.startfile(tmp.name)  # Windows media player
        except Exception as e:
            print(f"  [Voice] {e}")
    threading.Thread(target=_speak, daemon=True).start()
# ── TELEGRAM VOICE MESSAGE ─────────────────────────────
def send_voice_alert(message: str):
    """Generate mp3 with gtts and send as voice message to Telegram."""
    def _send():
        try:
            from gtts import gTTS
            import tempfile, os
            # Generate mp3
            tts = gTTS(text=message, lang='en')
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(tmp.name)
            # Send to Telegram as voice message
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice"
            with open(tmp.name, 'rb') as f:
                requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"voice": f}, timeout=15)
            os.unlink(tmp.name)  # cleanup
        except Exception as e:
            print(f"  [VoiceMsg] {e}")
    import threading
    threading.Thread(target=_send, daemon=True).start()