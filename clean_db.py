from db_state import load_state, save_state

state = load_state() or {}
positions = state.get("positions", {})

# Remove ghost positions not in your current 5
keep = ["AAPL", "TCS.NS", "BHARTIARTL.NS", "SBIN.NS", "ITC.NS"]
removed = [k for k in list(positions.keys()) if k not in keep]
for k in removed:
    del positions[k]
    print(f"Removed: {k}")

state["positions"] = positions
save_state(state)
print(f"Done. Kept: {list(positions.keys())}")