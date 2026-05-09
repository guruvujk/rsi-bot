# auto_trade_routes.py — Flask API routes for RSI Bot v3 Auto Trading
# Endpoints: start/stop scheduler, manual scan, portfolio, trade history

from flask import Blueprint, jsonify, request
from auto_trade_engine import (
    run_scan, start_scheduler, stop_scheduler, scheduler_status,
    get_portfolio_summary, load_paper_trades, load_open_positions,
    paper_sell, WATCHLIST, MAX_CAPITAL_PER_TRADE,
    filter_blacklist, filter_earnings, filter_atr, filter_news,
    get_nifty_sentiment, get_entry_signal,
    calc_rsi, calc_macd, calc_atr,
)
from blacklist import (
    get_blacklist, manually_blacklist, manually_whitelist,
    get_performance_summary as blacklist_summary,
)
from gainers import (
    get_all_favorites, get_tier, get_position_multiplier,
    print_summary as gainers_print,
)
import yfinance as yf

auto_trade_bp = Blueprint("auto_trade", __name__, url_prefix="/api/auto")

# Real brokers list
REAL_BROKERS = ['kite', 'groww', 'upstox', 'zerodha', 'angel', 'angelone', 
                'icici', 'hdfc', 'axis', 'kotak', 'motilal', '5paisa', 
                'sharekhan', 'stoxkart', 'coin', 'dhan']


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER CONTROL
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/start", methods=["POST"])
def start():
    """Start the background scan scheduler."""
    result = start_scheduler()
    return jsonify(result)


@auto_trade_bp.route("/stop", methods=["POST"])
def stop():
    """Stop the background scan scheduler."""
    result = stop_scheduler()
    return jsonify(result)


@auto_trade_bp.route("/status", methods=["GET"])
def status():
    """Get scheduler status + open positions count."""
    return jsonify(scheduler_status())


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL SCAN TRIGGER
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/scan", methods=["POST"])
def manual_scan():
    """
    Trigger a manual scan immediately.
    Body (optional): {"symbols": ["RELIANCE.NS", "TCS.NS"], "force": true}
    force=true bypasses market hours check.
    """
    data    = request.get_json(silent=True) or {}
    symbols = data.get("symbols") or WATCHLIST
    force   = data.get("force", False)
    result  = run_scan(symbols=symbols, force=force)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO - ALL POSITIONS (including paper trades)
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/portfolio", methods=["GET"])
def portfolio():
    """Get ALL open positions with live P&L (includes paper trades)."""
    return jsonify(get_portfolio_summary())


@auto_trade_bp.route("/portfolio/real", methods=["GET"])
def real_portfolio():
    """Get ONLY real broker positions (excludes paper trades)."""
    summary = get_portfolio_summary()
    positions = summary.get("positions", [])
    
    # Filter out paper trades
    real_positions = []
    for pos in positions:
        broker = pos.get("source", pos.get("broker", "")).lower()
        is_paper = pos.get("paper_mode", False) or broker in ['paper', 'manual']
        # Also check if it's from manual add without broker
        if not is_paper and broker not in ['paper', 'manual', '']:
            real_positions.append(pos)
    
    # Calculate real portfolio value
    real_pnl = sum(p.get("pnl", 0) for p in real_positions)
    
    return jsonify({
        "positions": real_positions,
        "count": len(real_positions),
        "total_pnl": round(real_pnl, 2),
        "message": f"Showing {len(real_positions)} real broker positions (paper trades hidden)"
    })


@auto_trade_bp.route("/close/<symbol>", methods=["POST"])
def close_position(symbol):
    """Manually close an open position at current market price."""
    try:
        df    = yf.download(symbol, period="1d", interval="1m",
                            progress=False, auto_adjust=True)
        price = float(df["Close"].squeeze().iloc[-1]) if not df.empty else None
        if price is None:
            return jsonify({"error": "Could not fetch current price"}), 400
        result = paper_sell(symbol, price, "Manual close")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auto_trade_bp.route("/close-all", methods=["POST"])
def close_all():
    """Manually close ALL open positions at market price."""
    positions = load_open_positions()
    results   = []
    for symbol in list(positions.keys()):
        try:
            df    = yf.download(symbol, period="1d", interval="1m",
                                progress=False, auto_adjust=True)
            price = float(df["Close"].squeeze().iloc[-1]) if not df.empty else None
            if price:
                result = paper_sell(symbol, price, "Close all")
                results.append(result)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})
    return jsonify({"closed": len(results), "results": results})


# ─────────────────────────────────────────────────────────────────────────────
# TRADE HISTORY
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/trades", methods=["GET"])
def trade_history():
    """
    Get paper trade history.
    Query params: ?type=BUY|SELL&symbol=RELIANCE.NS&limit=50
    """
    trades  = load_paper_trades()
    t_type  = request.args.get("type",   "").upper()
    symbol  = request.args.get("symbol", "").upper()
    limit   = int(request.args.get("limit", 100))

    if t_type:
        trades = [t for t in trades if t.get("type") == t_type]
    if symbol:
        trades = [t for t in trades if symbol in t.get("symbol", "").upper()]

    # Stats
    sells  = [t for t in trades if t.get("type") == "SELL"]
    wins   = [t for t in sells  if t.get("result") == "WIN"]
    total_pnl = sum(t.get("pnl", 0) for t in sells)

    return jsonify({
        "trades"      : list(reversed(trades))[:limit],
        "total_count" : len(trades),
        "sell_count"  : len(sells),
        "win_count"   : len(wins),
        "loss_count"  : len(sells) - len(wins),
        "win_rate"    : round(len(wins) / len(sells) * 100, 1) if sells else 0,
        "total_pnl"   : round(total_pnl, 2),
    })


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL INSPECTOR — debug a single symbol
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/inspect/<symbol>", methods=["GET"])
def inspect_symbol(symbol):
    """
    Run full filter pipeline on a single symbol and return detailed report.
    Useful for debugging why a symbol was skipped.
    Example: GET /api/auto/inspect/RELIANCE.NS
    """
    report = {"symbol": symbol, "filters": [], "entry_signal": None}

    # Blacklist
    ok, reason = filter_blacklist(symbol)
    report["filters"].append({"filter": "blacklist", "passed": ok, "reason": reason})

    # Fetch data
    try:
        df = yf.download(symbol, period="90d", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            return jsonify({"error": "No data returned from yfinance"}), 400
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    except Exception as e:
        return jsonify({"error": f"Data fetch failed: {e}"}), 500

    # Earnings
    ok, reason = filter_earnings(symbol)
    report["filters"].append({"filter": "earnings", "passed": ok, "reason": reason})

    # ATR
    ok, reason = filter_atr(df, symbol)
    report["filters"].append({"filter": "atr", "passed": ok, "reason": reason})

    # Nifty
    ok, reason = get_nifty_sentiment()
    report["filters"].append({"filter": "nifty", "passed": ok, "reason": reason})

    # News
    ok, reason = filter_news(symbol)
    report["filters"].append({"filter": "news", "passed": ok, "reason": reason})

    # Signal
    entry, signal = get_entry_signal(df)
    report["entry_signal"] = {**signal, "triggered": entry}

    # Gainer tier
    report["tier"]       = get_tier(symbol)
    report["multiplier"] = get_position_multiplier(symbol)
    report["allocation"] = round(MAX_CAPITAL_PER_TRADE * report["multiplier"], 2)

    # Overall verdict
    all_passed = all(f["passed"] for f in report["filters"])
    report["verdict"] = "BUY ✅" if (all_passed and entry) else "SKIP ⛔"
    report["block_reason"] = next(
        (f["reason"] for f in report["filters"] if not f["passed"]),
        None if entry else "No RSI+MACD crossover signal"
    )

    return jsonify(report)


# ─────────────────────────────────────────────────────────────────────────────
# BLACKLIST MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/blacklist", methods=["GET"])
def get_blacklist_route():
    return jsonify({
        "blacklisted": get_blacklist(),
        "performance": blacklist_summary(),
    })


@auto_trade_bp.route("/blacklist/add", methods=["POST"])
def add_blacklist():
    data   = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip().upper()
    reason = data.get("reason", "Manual")
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    manually_blacklist(symbol, reason)
    return jsonify({"blacklisted": symbol, "reason": reason})


@auto_trade_bp.route("/blacklist/remove", methods=["POST"])
def remove_blacklist():
    data   = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    manually_whitelist(symbol)
    return jsonify({"whitelisted": symbol})


# ─────────────────────────────────────────────────────────────────────────────
# GAINERS / TIERS
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/gainers", methods=["GET"])
def get_gainers():
    return jsonify(get_all_favorites())


# ─────────────────────────────────────────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/watchlist", methods=["GET"])
def get_watchlist():
    return jsonify({"watchlist": WATCHLIST, "count": len(WATCHLIST)})


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — view and hot-update engine settings
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/config", methods=["GET"])
def get_config():
    import auto_trade_engine as eng
    return jsonify({
        "RSI_PERIOD"           : eng.RSI_PERIOD,
        "RSI_BUY_THRESHOLD"    : eng.RSI_BUY_THRESHOLD,
        "RSI_SELL_THRESHOLD"   : eng.RSI_SELL_THRESHOLD,
        "FIXED_SL_PCT"         : eng.FIXED_SL_PCT,
        "TSL_ACTIVATE_PCT"     : eng.TSL_ACTIVATE_PCT,
        "TSL_TRAIL_PCT"        : eng.TSL_TRAIL_PCT,
        "MAX_CAPITAL_PER_TRADE": eng.MAX_CAPITAL_PER_TRADE,
        "MAX_OPEN_POSITIONS"   : eng.MAX_OPEN_POSITIONS,
        "BROKERAGE_PCT"        : eng.BROKERAGE_PCT,
    })


@auto_trade_bp.route("/config", methods=["POST"])
def set_config():
    import auto_trade_engine as eng
    data = request.get_json(silent=True) or {}
    updated = {}
    allowed = ["RSI_BUY_THRESHOLD", "RSI_SELL_THRESHOLD", "FIXED_SL_PCT",
               "TSL_ACTIVATE_PCT", "TSL_TRAIL_PCT", "MAX_CAPITAL_PER_TRADE",
               "MAX_OPEN_POSITIONS"]
    for key in allowed:
        if key in data:
            setattr(eng, key, type(getattr(eng, key))(data[key]))
            updated[key] = getattr(eng, key)
    return jsonify({"status": "updated", "updated": updated})


# ─────────────────────────────────────────────────────────────────────────────
# UPSTOX / REAL BROKER INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/upstox/login", methods=["GET"])
def upstox_login():
    from upstox_integration import get_login_url
    return jsonify({"login_url": get_login_url()})


@auto_trade_bp.route("/upstox/sync", methods=["POST"])
def upstox_sync():
    from upstox_integration import load_token, sync_to_bot
    token = load_token()
    if not token:
        return jsonify({"error": "No token. Visit /api/auto/upstox/login first"}), 401
    sync_to_bot(token)
    return jsonify({"status": "synced", "db_saved": True})


@auto_trade_bp.route("/upstox/token", methods=["GET"])
def upstox_token_status():
    from upstox_db import get_token_status
    return jsonify(get_token_status())


@auto_trade_bp.route("/upstox/positions", methods=["GET"])
def upstox_positions_from_db():
    """
    Get positions from Upstox/Kite/Groww real portfolio.
    Excludes paper trades and manual entries without broker.
    """
    from upstox_db import load_positions
    all_positions = load_positions()
    
    # Filter to ONLY real broker positions
    real_positions = []
    for pos in all_positions:
        source = pos.get('source', '').lower()
        broker = pos.get('broker', '').lower()
        is_paper = pos.get('paper_mode', False)
        
        # Check if this is a real broker position
        is_real_broker = (source in REAL_BROKERS or broker in REAL_BROKERS)
        is_not_paper = not is_paper and source not in ['paper', 'manual'] and broker not in ['paper', 'manual']
        
        if is_real_broker and is_not_paper:
            real_positions.append(pos)
    
    return jsonify({
        "source": "neon_db",
        "total_in_db": len(all_positions),
        "count": len(real_positions),
        "positions": real_positions,
        "message": f"Showing {len(real_positions)} real portfolio positions (paper trades hidden)"
    })


@auto_trade_bp.route("/upstox/history", methods=["GET"])
def upstox_position_history():
    from upstox_db import get_position_history
    history = get_position_history()
    
    # Filter history to real broker positions only
    real_history = [h for h in history if h.get('source', '').lower() in REAL_BROKERS]
    
    return jsonify({
        "total": len(real_history),
        "history": real_history
    })


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL POSITIONS (for adding real broker entries)
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/manual/add", methods=["POST"])
def manual_add_position():
    """
    Add a manual position to the portfolio.
    broker must be one of: Kite, Groww, Upstox, Zerodha, etc.
    """
    data      = request.get_json(force=True)
    symbol    = data.get("symbol", "").upper().strip()
    qty       = int(data.get("qty", 0))
    buy_price = float(data.get("buy_price", 0))
    broker    = data.get("broker", "Manual")
    itype     = data.get("itype", "STOCK")
    
    if not symbol or qty <= 0 or buy_price <= 0:
        return jsonify({"error": "symbol, qty and buy_price required"}), 400
    
    # Validate broker is a real broker (not paper)
    if broker.lower() in ['paper', 'manual']:
        return jsonify({"error": f"Cannot add position with broker='{broker}'. Use a real broker like Kite, Groww, or Upstox"}), 400
    
    sl_price = round(buy_price * 0.95, 2)
    
    # Check if this is a real broker
    is_real_broker = broker.lower() in REAL_BROKERS
    paper_mode = not is_real_broker

    # Save to Neon DB
    try:
        from db_state import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO upstox_positions
                (symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
                 sl_price, tp_price, tsl_active, synced_at, is_open,
                 broker, source, paper_mode)
            VALUES (%s, %s, %s, %s, %s, 0, 0, %s, 0, FALSE, NOW(), TRUE, %s, %s, %s)
        """, (symbol, itype, qty, buy_price, buy_price, sl_price, broker, broker, paper_mode))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Save to bot_state (in-memory + db_state)
    try:
        from db_state import load_state, save_state
        state = load_state() or {}
        positions = state.get("positions", {})
        positions[symbol] = {
            "symbol"    : symbol,
            "qty"       : qty,
            "buy_price" : buy_price,
            "sl_price"  : sl_price,
            "tsl_active": False,
            "peak_price": buy_price,
            "tsl_price" : None,
            "allocation": round(buy_price * qty, 2),
            "brokerage" : 0,
            "entry_time": "Manual",
            "itype"     : itype,
            "source"    : broker,
            "broker"    : broker,
            "paper_mode": paper_mode,
        }
        state["positions"] = positions
        save_state(state)
    except Exception as e:
        print(f"[Manual] state save error: {e}")

    return jsonify({
        "status": "added",
        "symbol": symbol,
        "broker": broker,
        "sl_price": sl_price,
        "paper_mode": paper_mode,
        "message": f"Position added to {'real' if not paper_mode else 'paper'} portfolio"
    })


@auto_trade_bp.route("/manual/remove", methods=["POST"])
def manual_remove_position():
    """Remove a position from portfolio."""
    data   = request.get_json(force=True)
    symbol = data.get("symbol", "").upper().strip()
    broker = data.get("broker", "")
    
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    
    try:
        from upstox_db import close_position
        close_position(symbol)
    except Exception as e:
        print(f"[Manual] DB close error: {e}")
    
    try:
        from db_state import load_state, save_state
        state = load_state() or {}
        positions = state.get("positions", {})
        key = symbol + "_" + broker if broker else symbol
        positions.pop(key, None)
        positions.pop(symbol, None)
        state["positions"] = positions
        save_state(state)
    except Exception as e:
        print(f"[Manual] state remove error: {e}")
    
    return jsonify({"status": "removed", "symbol": symbol})