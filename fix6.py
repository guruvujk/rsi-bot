content = open("dashboard.py", encoding="utf-8").read()
old = '"total_return_pct": ((portfolio_val - 100000) / 100000 * 100),'
new = '"total_return_pct": bot_state.get("total_return_pct", 0),'
content = content.replace(old, new)
open("dashboard.py", "w", encoding="utf-8").write(content)
print("Done")
