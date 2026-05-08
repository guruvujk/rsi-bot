# upstox_reminder.py — Daily Upstox token reminder via Telegram
from telegram_alerts import send_telegram

LOGIN_URL = (
    "https://api.upstox.com/v2/login/authorization/dialog"
    "?response_type=code"
    "&client_id=936905f2-69df-464c-94d2-966b9997adbb"
    "&redirect_uri=http://localhost:5000/upstox/callback"
)

def send_upstox_reminder():
    send_telegram(
        f"*Upstox Daily Login Required*\n\n"
        f"Click to renew your token:\n{LOGIN_URL}\n\n"
        f"After login, token auto-saves.",
        "INFO"
    )
    print("  [Upstox] Morning reminder sent to Telegram")