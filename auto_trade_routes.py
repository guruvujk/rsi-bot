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
# PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────
@auto_trade_bp.route("/portfolio", methods=["GET"])
def portfolio():
    """Get all open positions with live P&L."""
    return jsonify(get_portfolio_summary())


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
