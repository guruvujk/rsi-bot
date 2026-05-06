content = open("dashboard.py", encoding="utf-8").read()
content = content.replace(
    '"capital": state.get(',
    '"capital": bot_state.get('
).replace(
    '"portfolio_val": state.get(',
    '"portfolio_val": bot_state.get('
).replace(
    '"unrealised_pnl": state.get(',
    '"unrealised_pnl": bot_state.get('
).replace(
    '"realised_pnl": state.get(',
    '"realised_pnl": bot_state.get('
).replace(
    '"win_rate": state.get(',
    '"win_rate": bot_state.get('
).replace(
    '"total_trades": state.get(',
    '"total_trades": bot_state.get('
).replace(
    '"positions": state.get(',
    '"positions": bot_state.get('
).replace(
    '{"symbols": state.get(',
    '{"symbols": bot_state.get('
).replace(
    '{"alerts": state.get(',
    '{"alerts": bot_state.get('
).replace(
    '{"trades": state.get(',
    '{"trades": bot_state.get('
)
open("dashboard.py", "w", encoding="utf-8").write(content)
print("Done")
