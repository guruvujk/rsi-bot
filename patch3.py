content = open("main.py", "r", encoding="utf-8").read()

# Remove duplicate monitor_sl function - keep only first occurrence
first = content.find("def monitor_sl():")
second = content.find("def monitor_sl():", first + 1)
if second != -1:
    end = content.find("\n\n\n", second)
    content = content[:second] + content[end:]

# Remove duplicate schedule line
content = content.replace(
    "    schedule.every(5).minutes.do(monitor_sl)\n    schedule.every(5).minutes.do(monitor_sl)",
    "    schedule.every(5).minutes.do(monitor_sl)"
)

open("main.py", "w", encoding="utf-8").write(content)
print("Done")
