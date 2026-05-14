# telegram_alerts.py — Complete Integration (Telegram + Local API)
import requests
import os
import threading
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ── CONFIGURATION ──────────────────────────────────────
API_BASE_URL = "http://localhost:5000/api"
TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERT_EMOJI = {
    "BUY"  : "🟢",
    "SELL" : "🔴",
    "WIN"  : "🎯",
    "LOSS" : "⛔",
    "INFO" : "ℹ️",
    "START": "🚀",
    "STOP" : "🛑",
    "WARN" : "⚠️",
    "CRASH": "🚨",
}

# ── TELEGRAM FUNCTIONS ─────────────────────────────────
def send_telegram(message: str, alert_type: str = "INFO") -> bool:
    if os.environ.get("TELEGRAM_ENABLED", "true").lower() == "false":
        return False
    try:
        from config import (
            TELEGRAM_TOKEN,
            CHANNEL_BUY_ALERTS,
            CHANNEL_SELL_ALERTS,
            CHANNEL_SYSTEM_ALERTS,
            TELEGRAM_CHAT_ID
        )

        # Route to correct channel based on alert_type
        if alert_type == "BUY":
            chat_id = CHANNEL_BUY_ALERTS
        elif alert_type == "SELL":
            chat_id = CHANNEL_SELL_ALERTS
        elif alert_type in ["INFO", "ERROR", "WARNING", "SYSTEM"]:
            chat_id = CHANNEL_SYSTEM_ALERTS
        else:
            chat_id = TELEGRAM_CHAT_ID  # fallback

        emoji = ALERT_EMOJI.get(alert_type, "📢")
        payload = {
            "chat_id"   : chat_id,
            "text"      : f"{emoji} {message}",
            "parse_mode": "Markdown",
        }
        resp = requests.post(TELEGRAM_BASE_URL, data=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"  [Telegram] {e}")
        return False


def alert_buy(symbol, price, qty, rsi, sl, target, capital_left, itype):
    clean_sym = symbol.replace(".NS", "").replace("-USD", "")
    send_telegram(
        f"*💰 BUY FIRED — {itype}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 *{clean_sym}*\n"
        f"💵 Entry  : ₹{price}\n"
        f"📊 RSI    : {rsi:.1f} ← oversold\n"
        f"🛡 SL     : ₹{sl}\n"
        f"🎯 Target : ₹{target}\n"
        f"🔢 Qty    : {qty} shares\n"
        f"💼 Capital: ₹{capital_left:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━",
        'BUY'
    )


def alert_sell(symbol, price, qty, reason, pnl, total_pnl, capital, itype):
    clean_sym = symbol.replace(".NS", "").replace("-USD", "")
    is_win    = pnl > 0
    result    = "✅ PROFIT" if is_win else "❌ LOSS"
    emoji_type = "WIN" if is_win else "LOSS"
    reason_emoji = {
        "TARGET HIT" : "🎯",
        "STOP LOSS"  : "⛔",
        "RSI SELL"   : "📉",
        "TRAIL STOP" : "🔒",
    }.get(reason, "📤")

    send_telegram(
        f"*{reason_emoji} {reason} — {itype}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 *{clean_sym}*\n"
        f"💵 Exit   : ₹{price}\n"
        f"📦 Qty    : {qty} shares\n"
        f"💰 P&L    : ₹{pnl:,.2f}\n"
        f"📊 Result : {result}\n"
        f"💼 Capital: ₹{capital:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━",
        'SELL'
    )


def alert_summary(trades, total_pnl, capital):
    wins   = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) <= 0]
    wr     = round(len(wins) / len(trades) * 100, 1) if trades else 0
    emoji  = "🟢" if total_pnl >= 0 else "🔴"
    send_telegram(
        f"*📊 END OF DAY SUMMARY*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades  : {len(trades)}\n"
        f"✅ Wins    : {len(wins)}\n"
        f"❌ Losses  : {len(losses)}\n"
        f"🏆 Win Rate: {wr}%\n"
        f"{emoji} P&L    : ₹{total_pnl:,.2f}\n"
        f"💼 Capital : ₹{capital:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━",
        "INFO"
    )


# ── LOCAL API SYNC FUNCTIONS ───────────────────────────
def clean_price(p):
    try:
        return float(str(p).replace('₹','').replace('$','').replace(',','').strip())
    except:
        return 0.0

def sync_buy_to_api(symbol, price, qty, sl, target, rsi, itype):
    try:
        data = {
            "symbol": symbol, "direction": "BUY",
            "price": clean_price(price), "qty": qty,
            "stop_loss": clean_price(sl), "target": clean_price(target),
            "rsi_value": rsi, "reason": f"RSI {rsi:.1f} < 30",
            "instrument_type": itype
        }
        resp = requests.post(f"{API_BASE_URL}/trade", json=data, timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ API: BUY {symbol} synced")
            return True
    except Exception as e:
        print(f"  ⚠️ API Sync Failed: {e}")
        return False

def sync_sell_to_api(symbol, price, qty, pnl, reason, itype="CRYPTO"):
    try:
        data = {
            "symbol": symbol, "direction": "SELL",
            "price": clean_price(price), "qty": qty,
            "stop_loss": 0, "target": 0, "rsi_value": 0,
            "reason": reason, "instrument_type": itype
        }
        resp = requests.post(f"{API_BASE_URL}/trade", json=data, timeout=5)
        if resp.status_code == 200:
            print(f"  ✅ API: SELL {symbol} synced")
            return True
    except Exception as e:
        print(f"  ⚠️ API Sync Failed: {e}")
        return False

def update_position_price(symbol, current_price):
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
            os.startfile(tmp.name)
        except Exception as e:
            print(f"  [Voice] {e}")
    threading.Thread(target=_speak, daemon=True).start()

# ── TELEGRAM VOICE MESSAGE ─────────────────────────────
def send_voice_alert(message: str):
    def _send():
        try:
            from gtts import gTTS
            import tempfile
            tts = gTTS(text=message, lang='en')
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(tmp.name)
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice"
            with open(tmp.name, 'rb') as f:
                requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"voice": f}, timeout=15)
            os.unlink(tmp.name)
        except Exception as e:
            print(f"  [VoiceMsg] {e}")
    threading.Thread(target=_send, daemon=True).start()
