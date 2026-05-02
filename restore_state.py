import os, json
os.environ["DATABASE_URL"] = "postgresql://rsi_bot_db_user:19kNcfkPyTQYKkarzCL9wpVSPNyfxiMA@dpg-d7ou3ee7r5hc73dmjd80-a.singapore-postgres.render.com/rsi_bot_db"
from db_state import init_db, save_state, load_state
init_db()
data = json.load(open("bot_state.json.backup"))
save_state(data)
print("Saved capital:", data.get("capital"))
print("Positions:", len(data.get("positions", {})))
verify = load_state()
print("Verified from DB:", verify.get("capital"))
