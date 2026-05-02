import json, os
os.environ["DATABASE_URL"] = "postgresql://rsi_bot_db_user:19kNcfkPyTQYKkarzCL9wpVSPNyfxiMA@dpg-d7ou3ee7r5hc73dmjd80-a.singapore-postgres.render.com/rsi_bot_db"

from db_state import init_db, save_state

init_db()

with open("bot_state.json") as f:
    state = json.load(f)

save_state(state)
print("✅ State pushed to DB!")
print(f"Capital: {state.get('capital')}")
print(f"Positions: {len(state.get('positions', {}))}")