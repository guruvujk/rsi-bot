content = open("main.py", "r", encoding="utf-8").read()

monitor_fn = """
def monitor_sl():
    try:
        from db_state import get_conn
        from telegram_alerts import send_telegram
        import yfinance as yf
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, symbol, broker, buy_price, sl_price, qty FROM upstox_positions WHERE is_open=TRUE AND sl_price > 0")
        positions = cur.fetchall()
        for pos_id, symbol, broker, buy_price, sl_price, qty in positions:
            try:
                ltp = float(yf.Ticker(symbol).fast_info["last_price"])
                if ltp <= sl_price:
                    pnl = round((ltp - buy_price) * qty, 2)
                    cur.execute("UPDATE upstox_positions SET is_open=FALSE, ltp=%s WHERE id=%s", (ltp, pos_id))
                    conn.commit()
                    send_telegram(f"🔴 SL HIT: {symbol} ({broker})\\nBuy: Rs.{buy_price} | SL: Rs.{sl_price} | Exit: Rs.{ltp}\\nP&L: Rs.{pnl}", "SELL")
                    print(f"  🔴 SL HIT: {symbol} ({broker}) closed at {ltp}")
            except Exception as e:
                print(f"  [SL Monitor] {symbol}: {e}")
        cur.close()
    except Exception as e:
        print(f"  [SL Monitor] Error: {e}")

"""

marker = "# Scheduler loop"
content = content.replace(marker, monitor_fn + marker)

content = content.replace(
    "schedule.every(SCAN_INTERVAL).seconds.do(scan)",
    "schedule.every(SCAN_INTERVAL).seconds.do(scan)\n    schedule.every(5).minutes.do(monitor_sl)"
)

open("main.py", "w", encoding="utf-8").write(content)
print("Done")
