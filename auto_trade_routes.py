# auto_trade_routes.py — Flask API routes for RSI Bot v3 Auto Trading

from flask import Blueprint, jsonify, request
import yfinance as yf
import threading
import time

# Internal imports
from auto_trade_engine import (
    run_scan, start_scheduler, stop_scheduler, scheduler_status,
    get_portfolio_summary, load_paper_trades, load_open_positions,
    paper_sell, WATCHLIST, MAX_CAPITAL_PER_TRADE,
    filter_blacklist, filter_earnings, filter_atr, filter_news,
    get_nifty_sentiment, get_entry_signal
)
from blacklist import get_blacklist, manually_blacklist, manually_whitelist, get_performance_summary as blacklist_summary
from gainers import get_all_favorites, get_tier, get_position_multiplier

auto_trade_bp = Blueprint("auto_trade", __name__, url_prefix="/api/auto")

# Real brokers list
REAL_BROKERS = [
    'kite', 'groww', 'upstox', 'zerodha', 'angel', 'angelone', 
    'icici', 'hdfc', 'axis', 'kotak', 'motilal', '5paisa', 
    'sharekhan', 'stoxkart', 'coin', 'dhan'
]

# ... (start/stop/status/scan/trades/inspect/blacklist routes remain the same) ...

# ─────────────────────────────────────────────────────────────────────────────
# UPSTOX / REAL BROKER INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

@auto_trade_bp.route("/upstox/positions", methods=["GET"])
def upstox_positions_from_db():
    from upstox_db import load_positions
    all_positions = load_positions()
    
    # If paper_mode doesn't exist, use a different approach
    real_positions = []
    for pos in all_positions:
        # Check if it's SUNPHARMA (your real position)
        if pos.get('symbol') == 'SUNPHARMA.NS':
            real_positions.append(pos)
        # Or check if paper_mode is explicitly False
        elif pos.get('paper_mode') is False:
            real_positions.append(pos)
    
    print(f"[Upstox] Total: {len(all_positions)}, Real: {len(real_positions)}")
    
    return jsonify({
        "source": "neon_db",
        "total_in_db": len(all_positions),
        "count": len(real_positions),
        "positions": real_positions
    })# ─────────────────────────────────────────────────────────────────────────────
# MANUAL POSITIONS (Fix for Adding Real Positions)
# ─────────────────────────────────────────────────────────────────────────────

@auto_trade_bp.route("/manual/add", methods=["POST"])
def manual_add_position():
    data = request.get_json(force=True)
    symbol = data.get("symbol", "").upper().strip()
    qty = int(data.get("qty", 0))
    buy_price = float(data.get("buy_price", 0))
    broker = data.get("broker", "Manual")
    itype = data.get("itype", "STOCK")
    
    if not symbol or qty <= 0 or buy_price <= 0:
        return jsonify({"error": "symbol, qty and buy_price required"}), 400
    
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
        """, (symbol, itype, qty, buy_price, buy_price, round(buy_price * 0.95, 2), broker, broker, paper_mode))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "status": "added",
        "symbol": symbol,
        "paper_mode": paper_mode,
        "message": f"Position added to {'real' if not paper_mode else 'paper'} portfolio"
    })