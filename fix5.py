content = open("dashboard.py", encoding="utf-8").read()
old = '"unrealised_pnl": bot_state.get("unrealised_pnl", 0),'
new = '"unrealised_pnl": sum((p.get("current_price",0) - p.get("buy_price",0)) * p.get("qty",0) for p in raw_positions.values()) if isinstance(raw_positions, dict) else bot_state.get("unrealised_pnl", 0),'
content = content.replace(old, new)
open("dashboard.py", "w", encoding="utf-8").write(content)
print("Done")
