content = open("dashboard.py", encoding="utf-8").read()

old = '''@app.route("/portfolio")
def portfolio():
    return jsonify({
        "capital": bot_state.get("capital", 0),
        "portfolio_val": bot_state.get("portfolio_val", 0),
        "unrealised_pnl": bot_state.get("unrealised_pnl", 0),
        "realised_pnl": bot_state.get("realised_pnl", 0),
        "win_rate": bot_state.get("win_rate", 0),
        "total_trades": bot_state.get("total_trades", 0),
        "positions": bot_state.get("positions", []),
    })

@app.route("/watchlist")
def watchlist():
    return jsonify({"symbols": bot_state.get("watchlist", [])})'''

new = '''@app.route("/portfolio")
def portfolio():
    raw_positions = bot_state.get("positions", {})
    pos_list = []
    if isinstance(raw_positions, dict):
        for sym, p in raw_positions.items():
            invested = p.get("buy_price", 0) * p.get("qty", 0)
            current_val = p.get("current_price", 0) * p.get("qty", 0)
            pnl = current_val - invested
            pos_list.append({
                "symbol": sym.replace(".NS", "").replace("-USD", ""),
                "full_symbol": sym,
                "itype": p.get("itype", "STOCK"),
                "buy_time": p.get("buy_time", ""),
                "qty": p.get("qty", 0),
                "buy_price": p.get("buy_price", 0),
                "current_price": p.get("current_price", 0),
                "invested": invested,
                "current_value": current_val,
                "pnl": pnl,
                "pnl_pct": (pnl / invested * 100) if invested else 0,
                "stop_loss": p.get("stop_loss", 0),
            })
    capital = bot_state.get("capital", 0)
    portfolio_val = bot_state.get("portfolio_val", capital)
    return jsonify({
        "capital": capital,
        "portfolio_value": portfolio_val,
        "unrealised_pnl": bot_state.get("unrealised_pnl", 0),
        "realised_pnl": bot_state.get("realised_pnl", 0),
        "total_return_pct": ((portfolio_val - 100000) / 100000 * 100),
        "win_rate": bot_state.get("win_rate", 0),
        "total_trades": bot_state.get("total_trades", 0),
        "wins": bot_state.get("wins", 0),
        "losses": bot_state.get("losses", 0),
        "last_updated": bot_state.get("last_updated", ""),
        "positions": pos_list,
    })

@app.route("/watchlist")
def watchlist():
    raw = bot_state.get("watchlist", [])
    wlist = []
    if isinstance(raw, dict):
        for sym, w in raw.items():
            wlist.append({
                "symbol": sym.replace(".NS","").replace("-USD",""),
                "full_symbol": sym,
                "signal": w.get("signal", "HOLD"),
                "price": w.get("price", 0),
                "rsi": w.get("rsi", 50),
            })
    elif isinstance(raw, list):
        wlist = raw
    return jsonify({"watchlist": wlist, "scanned_at": bot_state.get("scanned_at", "")})'''

content = content.replace(old, new)
open("dashboard.py", "w", encoding="utf-8").write(content)
print("Done")
