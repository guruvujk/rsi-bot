content = open("main.py", "r", encoding="utf-8").read()
content = content.replace(
    "schedule.every(SCAN_INTERVAL).seconds.do(scan)",
    "schedule.every(SCAN_INTERVAL).seconds.do(scan)\n    schedule.every(5).minutes.do(monitor_sl)"
)
open("main.py", "w", encoding="utf-8").write(content)
print("Done")
