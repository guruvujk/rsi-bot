# pre_market.py — Pre-market health check
# Runs at 9:00 AM IST every market day
# Checks: DB, Upstox token, capital, market day, internet
# Sends Telegram alert if any check fails

import requests
from datetime import datetime
import pytz
from sounds import play_sound
from telegram_alerts import send_telegram
from db_state import load_state

IST = pytz.timezone("Asia/Kolkata")
STARTING_CAPITAL = 315000  # approximate base capital
MIN_CAPITAL_PCT  = 0.20    # warn if capital drops below 20% of starting

# ─────────────────────────────────────────────────────────
def check_db() -> bool:
    try:
        state = load_state()
        return state is not None
    except Exception:
        return False

def check_upstox_token() -> bool:
    try:
        from upstox_db import get_db_connection
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT token FROM upstox_token ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return row is not None and len(row[0]) > 10
    except Exception:
        return False

def check_capital() -> bool:
    try:
        state = load_state()
        capital = state.get("capital", 0)
        min_cap = STARTING_CAPITAL * MIN_CAPITAL_PCT
        return capital >= min_cap
    except Exception:
        return False

def is_market_day() -> bool:
    now = datetime.now(IST)
    # Skip weekends
    if now.weekday() >= 5:
        return False
    # Skip known holidays (add as needed)
    holidays = [
        "2026-01-26", "2026-03-25", "2026-04-14",
        "2026-04-17", "2026-05-01", "2026-08-15",
        "2026-10-02", "2026-11-04", "2026-12-25",
    ]
    today = now.strftime("%Y-%m-%d")
    return today not in holidays

def ping_check() -> bool:
    try:
        r = requests.get("https://www.google.com", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# ─────────────────────────────────────────────────────────
def pre_market_check() -> bool:
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")
    print(f"\n{'='*50}")
    print(f"  PRE-MARKET CHECK @ {now}")
    print(f"{'='*50}")

    checks = {
        "DB Connected"   : check_db(),
        "Internet OK"    : ping_check(),
        "Upstox Token"   : check_upstox_token(),
        "Capital OK"     : check_capital(),
        "Market Day"     : is_market_day(),
    }

    all_ok = True
    for name, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {name:<20} {'OK' if status else 'FAILED'}")
        if not status:
            all_ok = False

    print(f"{'='*50}")

    if all_ok:
        print("  ✅ All checks passed — Bot ready to trade")
        play_sound("startup")
        send_alert(f"✅ Pre-market check passed @ {now}\nBot is ready to trade.")
    else:
        failed = [k for k, v in checks.items() if not v]
        msg = f"⚠️ PRE-MARKET CHECK FAILED @ {now}\nFailed: {', '.join(failed)}"
        print(f"\n  ⚠️  FAILED: {', '.join(failed)}")
        play_sound("stoploss")
        send_telegram(f"✅ Pre-market check passed @ {now}\nBot is ready to trade.")
        send_telegram(f"⚠️ PRE-MARKET CHECK FAILED @ {now}\nFailed: {', '.join(failed)}")

    return all_ok


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    pre_market_check()
