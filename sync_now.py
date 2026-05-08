from db_state import load_state
from upstox_db import sync_positions_to_db

state = load_state()
positions = state.get("positions", {})
cleaned = []
for sym, pos in positions.items():
    buy = pos.get("buy_price", 0)
    ltp = pos.get("ltp", buy)
    qty = pos.get("qty", 0)
    cleaned.append({
        "symbol"    : sym,
        "itype"     : pos.get("itype", "STOCK"),
        "qty"       : qty,
        "buy_price" : buy,
        "ltp"       : ltp,
        "pnl"       : round((ltp - buy) * qty, 2) if buy else 0,
        "pnl_pct"   : round((ltp - buy) / buy * 100, 2) if buy else 0,
        "sl_price"  : pos.get("sl_price", round(buy * 0.95, 2)),
        "tp_price"  : pos.get("tp_price", 0),
        "tsl_active": pos.get("tsl_active", False),
    })
sync_positions_to_db(cleaned)
print(f"Saved {len(cleaned)} positions to Neon DB")
for p in cleaned:
    print(f"  {p['symbol']:20} buy={p['buy_price']}  qty={p['qty']}")