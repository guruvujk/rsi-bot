# ── PASTE THIS BLOCK at the end of auto_trade_routes.py ──────────────────────
# DELETE UPSTOX POSITION — remove by symbol + broker directly from DB

@auto_trade_bp.route("/upstox/position/delete", methods=["POST"])
def delete_upstox_position():
    """
    Delete a specific position row from upstox_positions by symbol + broker.
    Body: {"symbol": "SUNPHARMA.NS", "broker": "Kite"}
    Called by the 🗑 button in the Upstox Real Portfolio table on the dashboard.
    """
    data   = request.get_json(force=True)
    symbol = data.get("symbol", "").upper().strip()
    broker = data.get("broker", "")
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    try:
        from upstox_db import get_conn
        conn = get_conn()
        cur  = conn.cursor()
        if broker:
            cur.execute(
                "DELETE FROM upstox_positions WHERE symbol=%s AND broker=%s",
                (symbol, broker)
            )
        else:
            cur.execute(
                "DELETE FROM upstox_positions WHERE symbol=%s",
                (symbol,)
            )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        # Mirror removal in bot_state
        try:
            from db_state import load_state, save_state
            state     = load_state() or {}
            positions = state.get("positions", {})
            key = symbol + "_" + broker if broker else symbol
            positions.pop(key, None)
            positions.pop(symbol, None)
            state["positions"] = positions
            save_state(state)
        except Exception as e:
            print(f"[Delete] state remove error: {e}")
        return jsonify({"status": "deleted", "symbol": symbol,
                        "broker": broker, "rows_removed": deleted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
