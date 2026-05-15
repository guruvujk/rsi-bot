content = open("main.py", "r", encoding="utf-8").read()

run_scheduler_fn = """
# Scheduler loop
# ─────────────────────────────────────────────────────────────────────────────
def run_scheduler():
    schedule.every(SCAN_INTERVAL).seconds.do(scan)
    schedule.every(5).minutes.do(monitor_sl)
    schedule.every().day.at("09:00").do(morning_briefing)
    schedule.every().day.at("15:25").do(nse_eod_close)
    schedule.every().day.at("15:35").do(nse_eod_summary)
    schedule.every().day.at("23:00").do(crypto_summary)
    from upstox_reminder import send_upstox_reminder
    schedule.every().day.at("08:30").do(send_upstox_reminder)
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Scheduler error: {e}")
            time.sleep(5)
            continue


"""

marker = "# Entry point"
content = content.replace(marker, run_scheduler_fn + marker)
open("main.py", "w", encoding="utf-8").write(content)
print("Done")
