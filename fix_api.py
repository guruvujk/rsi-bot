content = open("dashboard.py", encoding="utf-8").read()

new_routes = """
@app.route("/portfolio")
def portfolio():
    return jsonify({
        "capital": state.get("capital", 0),
        "portfolio_val": state.get("portfolio_val", 0),
        "unrealised_pnl": state.get("unrealised_pnl", 0),
        "realised_pnl": state.get("realised_pnl", 0),
        "win_rate": state.get("win_rate", 0),
        "total_trades": state.get("total_trades", 0),
        "positions": state.get("positions", []),
    })

@app.route("/watchlist")
def watchlist():
    return jsonify({"symbols": state.get("watchlist", [])})

@app.route("/alerts")
def alerts():
    return jsonify({"alerts": state.get("alerts", [])})

@app.route("/status")
def status():
    return jsonify({"status": "running", "connected": True})

@app.route("/trades")
def trades():
    return jsonify({"trades": state.get("trade_log", [])})

@app.route("/buy", methods=["POST"])
def buy():
    return jsonify({"status": "ok", "message": "Manual buy not supported in paper mode"})

@app.route("/sell", methods=["POST"])
def sell():
    return jsonify({"status": "ok", "message": "Manual sell not supported in paper mode"})
"""

content = content.replace("@app.route('/')", new_routes + "\n@app.route('/')")
open("dashboard.py", "w", encoding="utf-8").write(content)
print("Done")
