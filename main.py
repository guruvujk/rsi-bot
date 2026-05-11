import csv
import os
import time
import threading
import schedule
import json
from datetime import datetime
import pytz
import requests

from config import (
    WATCHLIST, CAPITAL, RISK_PER_TRADE, STOP_LOSS_PCT, TARGET_PCT,
    MIN_PRICE, SCAN_INTERVAL, MAX_POSITIONS, MAX_SAME_SECTOR, MAX_CAPITAL_PER_TRADE,
    STOCKS, INDICES, COMMODITIES, FOREX, CRYPTO, ETFS, US_STOCKS,
    get_instrument_type, get_usd_inr_rate, SCAN_INTERVAL_STOCKS, SCAN_INTERVAL_CRYPTO,
    SCAN_INTERVAL_FOREX, SCAN_INTERVAL_COMMODITY,
)
from rsi_engine import fetch_ohlcv, get_signal
from telegram_alerts import send_telegram
from dashboard import start_dashboard, bot_state as state
from paper_trade import PaperTrader
from db_state import load_trades, load_state as db_load_state

IST = pytz.timezone("Asia/Kolkata")
STATE_FILE = "bot_state.json"

# ── Delisted / bad symbols to skip silently ───────────────────────────────────
SKIP_SYMBOLS = {"POL-USD", "UNI-USD", "ARB-USD", "ARB/USD", "BTC-INR", "ETH-INR"}

# ─────────────────────────────────────────────────────────────────────────────
# Voice Alert — JKRAO Voice Studio
# ─────────────────────────────────────────────────────────────────────────────
VOICE_ENABLED = os.environ.get("VOICE_ENABLED", "false").lower() == "true"

def speak_alert(message: str, voice: str = "Raj"):
    if not VOICE_ENABLED:
        return  # Skip on cloud — use Telegram instead
    try:
        requests.post(
            "http://localhost:8080/api/alert",
            json={"message": message, "voice": voice},
            timeout=5
        )
    except Exception:
        pass  # Voice Studio only runs on local PC


# ─────────────────────────────────────────────────────────────────────────────
# State persistence helpers
# ─────────────────────────────────────────────────────────────────────────────
def save_state(trader: PaperTrader):
    try:
        stats = trader.stats()
        from db_state import load_trades as _lt
        data = {
            "capital": trader.capital,
            "positions": trader.positions,
            "trades": _lt(),
            "total_trades": stats.get("total_trades", 0),
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "win_rate": stats.get("win_rate", 0),
            "realised_pnl": stats.get("total_pnl", 0),
            "return_pct": stats.get("return_pct", 0),
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        try:
            from db_state import save_state as db_save
            db_save(data)
        except Exception as db_err:
            print(f"  [DB] Save failed: {db_err}")
    except Exception as e:
        print(f"  [State] Save failed: {e}")


def save_trade(trade):
    os.makedirs("logs", exist_ok=True)
    file = "logs/trades.csv"
    write_header = not os.path.exists(file)
    with open(file, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=trade.keys())
        if write_header:
            w.writeheader()
        w.writerow(trade)
    try:
        from db_state import save_trade as db_save_trade
        db_save_trade(trade)
    except Exception as e:
        print(f"  [DB] Trade log error: {e}")


def load_state(trader: PaperTrader):
    try:
        from db_state import load_state as db_load, load_trades as db_load_trades, init_db
        init_db()
        from upstox_db import init_upstox_tables
        init_upstox_tables()
        data = db_load()
        if data:
            trader.capital = float(data.get("capital", CAPITAL))
            trader.positions = data.get("positions", {})
            # ── Always rebuild trades from DB trades table ──
            try:
                stored_trades = db_load_trades()
                trader.trades = [t for t in stored_trades if t.get("action") == "SELL"]
                print(f"  [State] Restored from DB — "
                      f"Capital: ₹{trader.capital:,.0f} | "
                      f"Positions: {len(trader.positions)} | "
                      f"Closed trades: {len(trader.trades)}")
            except Exception as e:
                trader.trades = []
                print(f"  [DB] Reload trades failed: {e}")
            return
    except Exception as e:
        print(f"  [DB] {e}")
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        trader.capital = float(data.get("capital", CAPITAL))
        trader.positions = data.get("positions", {})
        trader.trades = []   # don't restore from JSON, DB is source of truth
        print(f"  [State] Restored from file — Capital: ₹{trader.capital:,.0f}")
    except Exception as e:
        print(f"  [State] Load failed (starting fresh): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive Stop Loss per instrument type
# ─────────────────────────────────────────────────────────────────────────────
def get_adaptive_sl(itype: str) -> float:
    """
    Return adaptive stop-loss % based on instrument volatility.
    Forex is less volatile → tighter SL
    Crypto is more volatile → wider SL
    """
    return {
        "FOREX":     0.008,   # 0.8%
        "STOCK":     0.020,   # 2%
        "INDEX":     0.015,   # 1.5%
        "ETF":       0.015,   # 1.5%
        "COMMODITY": 0.025,   # 2.5%
        "CRYPTO":    0.040,   # 4%
        "US_STOCK":  0.025,   # 2.5%
    }.get(itype, STOP_LOSS_PCT)


def get_adaptive_tp(itype: str) -> float:
    """
    Return adaptive take-profit % based on instrument type.
    """
    return {
        "FOREX":     0.006,   # 0.6%
        "STOCK":     0.030,   # 3%
        "INDEX":     0.020,   # 2%
        "ETF":       0.020,   # 2%
        "COMMODITY": 0.030,   # 3%
        "CRYPTO":    0.050,   # 5%
        "US_STOCK":  0.030,   # 3%
    }.get(itype, TARGET_PCT)


# ─────────────────────────────────────────────────────────────────────────────
# Position sizing — never over-invest
# ─────────────────────────────────────────────────────────────────────────────
def calc_qty(symbol: str, price: float, capital: float, itype: str) -> int:
    """
    Calculate safe quantity respecting MAX_CAPITAL_PER_TRADE.
    Always converts USD prices to INR before dividing.
    """
    from config import get_usd_inr_rate

    if "-USD" in symbol or symbol in ("EURUSD=X", "GBPUSD=X", "AUDUSD=X",
                                      "USDCAD=X", "NZDUSD=X", "USDCHF=X"):
        price_inr = price * get_usd_inr_rate()
    elif "=X" in symbol:
        price_inr = price if price > 10 else price * get_usd_inr_rate()
    else:
        price_inr = price

    max_alloc = min(capital * RISK_PER_TRADE, MAX_CAPITAL_PER_TRADE)

    if price_inr <= 0:
        return 0

    qty = int(max_alloc / price_inr)
    return max(1, qty)


# ─────────────────────────────────────────────────────────────────────────────
# Initialise trader (with crash recovery)
# ─────────────────────────────────────────────────────────────────────────────
pt = PaperTrader(CAPITAL)
trader = pt

# FIX: guard against db_load_state() returning None
_db_state = db_load_state()
if _db_state:
    trader.capital = _db_state.get("capital", trader.initial_capital)
    trader.positions = _db_state.get("positions", {})

# ── Rebuild trades from DB ────────────────────────────────────────────────────
db_trades = load_trades()
trader.trades = [t for t in db_trades if t.get("action") == "SELL"]
print(f"  ✅ Restored {len(trader.trades)} closed trades from DB")
print(f"  ✅ Capital: ₹{trader.capital:,.2f}")
print(f"  ✅ Open positions: {list(trader.positions.keys())}")


def patch_old_positions(trader: PaperTrader):
    for symbol, pos in trader.positions.items():
        itype = get_instrument_type(symbol)
        sl_pct = get_adaptive_sl(itype)
        tp_pct = get_adaptive_tp(itype)
        bp = pos.get("buy_price", 0)
        if bp > 0:
            pos["stop_loss"]     = round(bp * (1 - sl_pct), 6)
            pos["target"]        = round(bp * (1 + tp_pct), 6)
            pos["highest_price"] = pos.get("highest_price", bp)
            pos["tsl_active"]    = pos.get("tsl_active", False)
    print(f"  [Patch] Recalculated SL/TP on {len(trader.positions)} positions")

patch_old_positions(pt)

trades = pt.trades

# ─────────────────────────────────────────────────────────────────────────────
INSTRUMENT_EMOJI = {
    "STOCK":    "🏦",
    "INDEX":    "📈",
    "COMMODITY":"💰",
    "FOREX":    "💱",
    "CRYPTO":   "🪙",
    "ETF":      "📊",
    "US_STOCK": "🌍",
}

# ─────────────────────────────────────────────────────────────────────────────
# Market-hours gate
# ─────────────────────────────────────────────────────────────────────────────
def is_tradeable(symbol):
    now  = datetime.now(IST)
    itype = get_instrument_type(symbol)
    wd   = now.weekday()
    t    = now.hour * 60 + now.minute

    if itype in ("STOCK", "INDEX", "ETF"):
        if wd == 6 and t < 1200:
            return False
        if wd == 5 and t >= 120:
            return False
        return 540 <= t <= 1410 or wd in (6, 0)

    if itype == "COMMODITY":
        if wd == 5 and t >= 120:   # Saturday after 2 AM — closed
            return False
        if wd == 6 and t < 1200:   # Sunday before 8 PM — closed
            return False
            return True

    if itype == "FOREX":
        if wd == 5 and t >= 120:
            return False
        if wd == 6 and t < 1200:
            return False
        return True

    if itype == "CRYPTO":
        return True

    if itype == "US_STOCK":
        if wd >= 5:
            return False
        return t >= 1140 or t <= 90

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────
def format_symbol(symbol):
    return (symbol.replace(".NS", "").replace("=X", "")
                  .replace("=F", "").replace("-USD", "/USD"))

def format_price(symbol, price):
    if "USD" in symbol or "=F" in symbol:
        return f"${price:,.2f}"
    if "=X" in symbol:
        return f"{price:,.4f}"
    return f"₹{price:,.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard sync
# ─────────────────────────────────────────────────────────────────────────────
def sync_dashboard(current_prices={}):
    global state
    if state is None:
        from dashboard import bot_state as _s
        state = _s
    if state is None:
        return  # dashboard not yet initialised — skip safely

    stats = pt.stats()
    state['capital']       = stats['capital']
    state['pnl']           = stats['total_pnl']
    state['realised_pnl']  = stats['total_pnl']
    state['open_pnl']      = stats['open_pnl']
    state['portfolio_val'] = stats['portfolio_val']
    total_gain = stats['total_pnl'] + stats['open_pnl']
    state['return_pct']    = round((total_gain / pt.initial_capital) * 100, 2)
    state['win_rate']      = stats['win_rate']
    state['total_trades']  = stats['total_trades']
    state['trades']        = pt.trades
    state['wins']          = stats['wins']
    state['losses']        = stats['losses']

    from config import get_usd_inr_rate
    rate = get_usd_inr_rate()

    state['positions'] = {}
    for s, p in pt.positions.items():
        raw_price = current_prices.get(s) or state.get('watchlist', {}).get(s, {}).get('price')
        if raw_price is None:
            raw_price = p['buy_price']
        itype      = get_instrument_type(s)
        current_inr = raw_price * rate if "-USD" in s else raw_price
        pnl        = round((current_inr - p['buy_price']) * p['qty'], 2)
        state['positions'][s] = {
            **p,
            'current_price': current_inr,
            'pnl':           pnl,
            'type':          itype,
        }

    state.setdefault('watchlist', {})
    state['paper_mode'] = True


# ─────────────────────────────────────────────────────────────────────────────
# Core scan logic — one symbol at a time
# ─────────────────────────────────────────────────────────────────────────────
def scan_symbol(symbol, current_prices):

    raw = symbol.replace(".NS", "").replace("=X", "").replace("=F", "")
    if raw in SKIP_SYMBOLS or symbol in SKIP_SYMBOLS:
        return

    try:
        if not is_tradeable(symbol):
            return

        df = fetch_ohlcv(symbol)
        if df is None or df.empty or len(df) < 20:
            return

        signal, rsi_val, price, indicators = get_signal(df)

        # Skip if RSI or price is invalid
        if rsi_val != rsi_val or price <= 0:
            return

        current_prices[symbol] = price

        if price < MIN_PRICE and "-USD" not in symbol:
            sym_d = format_symbol(symbol)
            print(f"    → Skip {sym_d}: price ₹{price:.4f} below minimum")
            return

        itype  = get_instrument_type(symbol)
        emoji  = INSTRUMENT_EMOJI.get(itype, "📊")
        sym_d  = format_symbol(symbol)
        p_str  = format_price(symbol, price)

        # Update watchlist in dashboard state safely
        if state is not None:
            state.setdefault('watchlist', {})[symbol] = {
                'rsi':    rsi_val,
                'price':  price,
                'signal': signal,
                'type':   itype,
            }

        print(f"  {emoji} {sym_d:<14}  RSI={rsi_val:>6.1f}"
              f"  {p_str:<16}  {signal}")

        # ── EXIT logic ────────────────────────────────────────────────────────
        if symbol in pt.positions:
            pos     = pt.positions[symbol]
            bp      = pos['buy_price']
            # Update live price and P&L for dashboard
            pos['ltp']     = price
            pos['pnl']     = round((price - bp) * pos.get('qty', 1), 2)
            pos['pnl_pct'] = round((price - bp) / bp * 100, 2) if bp else 0
            chg_pct = (price - bp) / bp
            tp_pct  = get_adaptive_tp(itype)
            half_tp = tp_pct * 0.5

            # Update highest price seen
            if price > pos.get('highest_price', bp):
                pos['highest_price'] = price

            # Activate trailing stop loss at 50% of target
            if not pos.get('tsl_active') and chg_pct >= half_tp:
                pos['tsl_active'] = True
                print(f"    → TSL ACTIVATED: {sym_d}")

            # Trail: lock in 50% of profit above entry
            if pos.get('tsl_active'):
                profit    = pos['highest_price'] - bp
                tsl_price = bp + (profit * 0.5)
                if tsl_price > pos.get('stop_loss', 0):
                    pos['stop_loss'] = round(tsl_price, 4)
                    print(f"    → TSL updated: {sym_d} "
                          f"SL → {format_price(symbol, tsl_price)}")

            reason = None
            if chg_pct >= tp_pct:
                reason = "TARGET HIT 🎯"
            elif signal == "SELL":
                reason = "RSI SELL 📉"

            if reason:
                ok, pnl = pt.sell(symbol, price, rsi_val, reason)
                if ok:
                    emo = "🟢" if pnl >= 0 else "🔴"
                    send_telegram(
                        f"📊 *PAPER TRADE — SELL*\n{'─'*22}\n"
                        f"{emoji} *{sym_d}* [{itype}]\n"
                        f"Price  : {p_str}\n"
                        f"Qty    : {pos['qty']}\n"
                        f"Reason : {reason}\n"
                        f"P&L    : {emo} ₹{pnl:,.2f}\n\n"
                        f"💼 Portfolio: ₹{pt.capital:,.0f}\n"
                        f"📈 Total P&L: ₹{pt.stats()['total_pnl']:,.2f}",
                        "SELL"
                    )
                    clean_reason = reason.replace("🎯", "").replace("📉", "").strip()
                    speak_alert(
                        f"{clean_reason} on {sym_d}. "
                        f"{'Profit' if pnl >= 0 else 'Loss'} "
                        f"rupees {abs(pnl):.0f}."
                    )
                    print(f"    → PAPER SELL | {reason} | P&L ₹{pnl:,.2f}")
                    trade = {
                        'time':   datetime.now(IST).strftime('%H:%M'),
                        'symbol': symbol,
                        'action': 'SELL',
                        'price':  price,
                        'qty':    pos['qty'],
                        'rsi':    rsi_val,
                        'pnl':    round(pnl, 2),
                        'reason': reason,
                        'date':   datetime.now(IST).strftime('%d-%b-%Y'),
                    }
                    trades.append(trade)
                    save_state(pt)
                    save_trade(trade)

        # ── ENTRY logic ───────────────────────────────────────────────────────
        elif (signal == "BUY"
              and symbol not in pt.positions
              and len(pt.positions) < MAX_POSITIONS):

            # Drawdown circuit breaker
            from config import DRAWDOWN_PCT
            drawdown_floor = pt.initial_capital * (1 - DRAWDOWN_PCT)
            if pt.capital < drawdown_floor:
                if state is not None and not state.get('cb_alerted'):
                    send_telegram(
                        f"🔴 *CIRCUIT BREAKER TRIGGERED*\n"
                        f"Capital ₹{pt.capital:,.0f} below floor "
                        f"₹{drawdown_floor:,.0f}\n"
                        f"New BUYs paused until recovery.",
                        "INFO"
                    )
                    state['cb_alerted'] = True
                    print(f"  🔴 CIRCUIT BREAKER: Capital ₹{pt.capital:,.0f} "
                          f"< floor ₹{drawdown_floor:,.0f} — BUYs paused")
                return
            else:
                if state is not None:
                    state['cb_alerted'] = False

            if price < MIN_PRICE:
                print(f"    → Skip {sym_d}: price ₹{price:.4f} below minimum")
                return

            from config import can_enter_trade
            allowed, reason = can_enter_trade(symbol, pt.positions)
            if not allowed:
                print(f"    → Skip {sym_d}: {reason}")
                return

            sl_pct = get_adaptive_sl(itype)
            tp_pct = get_adaptive_tp(itype)
            qty    = calc_qty(symbol, price, pt.capital, itype)

            if qty <= 0:
                print(f"    → Skip {sym_d}: qty=0 (price too high for budget)")
                return

            from config import get_usd_inr_rate
            price_inr = price * get_usd_inr_rate() if "-USD" in symbol else price
            cost      = qty * price_inr

            if cost > pt.capital:
                print(f"    → Skip {sym_d}: insufficient capital"
                      f" (need ₹{cost:,.0f}, have ₹{pt.capital:,.0f})")
                return

            ok, msg = pt.buy(symbol, price_inr, qty, rsi_val,
                             sl_pct, tp_pct, itype=itype)
            if ok:
                sl_price = price * (1 - sl_pct)
                tp_price = price * (1 + tp_pct)
                send_telegram(
                    f"📊 *PAPER TRADE — BUY*\n{'─'*22}\n"
                    f"{emoji} *{sym_d}* [{itype}]\n"
                    f"Price  : {p_str}\n"
                    f"Qty    : {qty}\n"
                    f"RSI    : {rsi_val:.1f}\n"
                    f"SL     : {format_price(symbol, sl_price)}"
                    f" ({sl_pct*100:.1f}%)\n"
                    f"Target : {format_price(symbol, tp_price)}"
                    f" ({tp_pct*100:.1f}%)\n\n"
                    f"💼 Capital left: ₹{pt.capital:,.0f}",
                    "BUY"
                )
                speak_alert(
                    f"Buy signal on {sym_d}. "
                    f"R S I {rsi_val:.0f}. "
                    f"Buying {qty} units.",
                    voice="Raj"
                )
                print(f"    → PAPER BUY | {qty}x @ {p_str}"
                      f" | SL:{sl_pct*100:.1f}% TP:{tp_pct*100:.1f}%")

                trade = {
                    'time':   datetime.now(IST).strftime('%H:%M'),
                    'symbol': symbol,
                    'action': 'BUY',
                    'price':  round(price_inr, 2),
                    'qty':    qty,
                    'rsi':    rsi_val,
                    'pnl':    None,
                    'reason': 'RSI BUY',
                    'date':   datetime.now(IST).strftime('%d-%b-%Y'),
                }
                trades.append(trade)
                save_trade(trade)
                save_state(pt)

    except Exception as e:
        print(f"  [Error] {format_symbol(symbol)}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Full market scan
# ─────────────────────────────────────────────────────────────────────────────
#check_trail_alerts()
#REAL_PORTFOLIO
# ── TRAIL ALERT FOR REAL HOLDINGS ────────────────────────────────
REAL_PORTFOLIO = {
    "HDFCBANK.NS": {"avg": 783.75, "qty": 13, "gtt": 768},
    "SUNPHARMA.NS": {"avg": 1750.65, "qty": 12, "gtt": 1784},
    "CIPLA.NS": {"avg": 1321.10, "qty": 8, "gtt": 1300},
}

GTT_FILE = "logs/gtt_state.json"

def _load_gtt():
    try:
        with open(GTT_FILE) as f:
            return json.load(f)
    except Exception:
        return {k: v["gtt"] for k, v in REAL_PORTFOLIO.items()}

def _save_gtt(gtt: dict):
    os.makedirs("logs", exist_ok=True)
    with open(GTT_FILE, "w") as f:
        json.dump(gtt, f)

def check_trail_alerts(current_prices):
    gtt = _load_gtt()
    for symbol, info in REAL_PORTFOLIO.items():
        price = current_prices.get(symbol)
        if not price:
            continue
        new_sl = round(price * 0.98, 2)
        change_pct = ((price - info["avg"]) / info["avg"]) * 100
        current_gtt = gtt.get(symbol, info["gtt"])
        if new_sl > current_gtt + 10:
            send_telegram(
                f"📈 *TRAIL ALERT*\n{'─'*22}\n"
                f"*{symbol.replace('.NS','')}*\n"
                f"Price  : ₹{price:,.2f}\n"
                f"Change : +{change_pct:.1f}%\n"
                f"Current GTT: ₹{current_gtt}\n"
                f"➡️ Update GTT to: *₹{new_sl:,.2f}*",
                "INFO"
            )
            print(f"  📈 TRAIL ALERT: {symbol} → Update GTT to ₹{new_sl}")
            gtt[symbol] = new_sl
            _save_gtt(gtt)
def scan():
    now    = datetime.now(IST)
    active = [s for s in WATCHLIST if is_tradeable(s)]

    print(f"\n{'═'*62}")
    print(f"  Scan @ {now.strftime('%d-%b-%Y %H:%M:%S IST')}")
    print(f"  Capital: ₹{pt.capital:,.0f}"
          f"  |  Positions: {len(pt.positions)}/{MAX_POSITIONS}")
    print(f"{'═'*62}")

    if not active:
        print("  ⏸  All markets closed right now")
        sync_dashboard()
        return

    open_types = set(get_instrument_type(s) for s in active)
    print(f"  🟢 Open: {', '.join(sorted(open_types))}"
          f"  | Scanning {len(active)} instruments\n")

    current_prices = {}
    for symbol in WATCHLIST:
        scan_symbol(symbol, current_prices)

    pt.update_open_pnl(current_prices)
    check_trail_alerts(current_prices)

    # Recalculate stop_loss using adaptive SL (not fixed pct)
    for symbol, pos in pt.positions.items():
        if symbol in current_prices:
            itype = get_instrument_type(symbol)
            sl_pct = get_adaptive_sl(itype)
            pos["stop_loss"] = round(pos["buy_price"] * (1 - sl_pct), 4)

    stopped = pt.check_and_exit_stops(current_prices)
    for sym, pnl in stopped:
        sym_d = format_symbol(sym)
        send_telegram(f"🔴 STOP-LOSS hit: {sym} | P&L ₹{pnl:,.2f}")
        speak_alert(
            f"Stop loss triggered on {sym_d}. "
            f"Loss rupees {abs(pnl):.0f}.",
            voice="Raj"
        )

    sync_dashboard(current_prices)
    save_state(pt)

    s = pt.stats()
    print(f"\n  Win Rate:{s['win_rate']}%"
          f"  Trades:{s['total_trades']}"
          f"  P&L:₹{s['total_pnl']:,.2f}"
          f"  Open:₹{s['open_pnl']:,.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled alerts
# ─────────────────────────────────────────────────────────────────────────────
def morning_briefing():
    now = datetime.now(IST)
    if now.hour > 10:
        return

    active = []
    if STOCKS["enabled"]:      active.append("🏦 NSE Stocks")
    if INDICES["enabled"]:     active.append("📈 Indices")
    if COMMODITIES["enabled"]: active.append("💰 Commodities")
    if FOREX["enabled"]:       active.append("💱 Forex")
    if CRYPTO["enabled"]:      active.append("🪙 Crypto")
    if ETFS["enabled"]:        active.append("📊 ETFs")
    if US_STOCKS["enabled"]:   active.append("🌍 US Stocks")

    send_telegram(
        f"🌅 *Good Morning!*\n{'─'*24}\n"
        f"Date    : {datetime.now(IST).strftime('%d %b %Y')}\n"
        f"Capital : ₹{pt.capital:,.0f}\n"
        f"Open pos: {len(pt.positions)}/{MAX_POSITIONS}\n\n"
        f"Active markets:\n" + "\n".join(f"  {m}" for m in active) +
        "\n\nNSE opens at 9:15 AM 🚀",
        "INFO"
    )
    speak_alert(
        f"Good morning. Capital rupees {pt.capital:,.0f}. "
        f"{len(pt.positions)} open positions. NSE opens at 9:15 AM.",
        voice="Priya"
    )


def nse_eod_close():
    nse_pos = {s: p for s, p in pt.positions.items()
               if get_instrument_type(s) in ("STOCK", "INDEX")}
    if nse_pos:
        syms = ', '.join(format_symbol(s) for s in nse_pos)
        send_telegram(
            f"⏰ *3:25 PM — NSE Closing Soon*\n\nOpen NSE positions:\n*{syms}*",
            "INFO"
        )
        speak_alert(
            f"NSE closing in 5 minutes. Open positions: {syms}.",
            voice="Priya"
        )


def nse_eod_summary():
    s = pt.stats()
    send_telegram(
        f"📊 *NSE End of Day*\n{'─'*24}\n"
        f"Date    : {datetime.now(IST).strftime('%d %b %Y')}\n"
        f"Capital : ₹{s['capital']:,.2f}\n"
        f"P&L     : ₹{s['total_pnl']:,.2f}\n"
        f"Return  : {s['return_pct']}%\n"
        f"Trades  : {s['total_trades']}\n"
        f"Win Rate: {s['win_rate']}%",
        "INFO"
    )
    speak_alert(
        f"NSE end of day. Total P and L rupees {s['total_pnl']:,.0f}. "
        f"Win rate {s['win_rate']} percent.",
        voice="Raj"
    )


def crypto_summary():
    crypto_pos = {s: p for s, p in pt.positions.items()
                  if get_instrument_type(s) == "CRYPTO"}
    if crypto_pos:
        lines = [
            f"  • {format_symbol(s)}: {p['qty']}x @ ${p['buy_price']:,.2f}"
            for s, p in crypto_pos.items()
        ]
        send_telegram(
            f"🪙 *Crypto Update — 11 PM*\n{'─'*24}\n" + "\n".join(lines),
            "INFO"
        )
        speak_alert(
            f"Crypto update. {len(crypto_pos)} open crypto positions.",
            voice="Raj"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler loop
# ─────────────────────────────────────────────────────────────────────────────
def run_scheduler():
    schedule.every(SCAN_INTERVAL).seconds.do(scan)
    schedule.every().day.at("09:00").do(morning_briefing)
    schedule.every().day.at("15:25").do(nse_eod_close)
    schedule.every().day.at("15:35").do(nse_eod_summary)
    schedule.every().day.at("23:00").do(crypto_summary)
    from upstox_reminder import send_upstox_reminder
    schedule.every().day.at("08:30").do(send_upstox_reminder)
    while True:
        schedule.run_pending()
        time.sleep(1)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 62)
    print("   RSI BOT — All Instruments Edition v3 (FIXED)")
    print("   Paper Trade | No real money at risk")
    print("=" * 62)

    for label, grp in [
        ("🏦 NSE Stocks",  STOCKS),
        ("📈 Indices",     INDICES),
        ("💰 Commodities", COMMODITIES),
        ("💱 Forex",       FOREX),
        ("📊 ETFs",        ETFS),
        ("🌍 US Stocks",   US_STOCKS),
    ]:
        status = (f"✅ {len(grp['symbols'])} symbols"
                  if grp["enabled"] else "❌ disabled")
        print(f"  {label:<22} {status}")

    print(f"\n  Total : {len(WATCHLIST)} instruments"
          f" | Max pos: {MAX_POSITIONS}")
    print("=" * 62)
   
    from auto_trade_engine import start_scheduler as start_auto_scheduler
    from dashboard import app as flask_app
    start_auto_scheduler()
    print('  [AutoTrade] Engine started')

    threading.Thread(target=start_dashboard, daemon=True).start()
    scan()
    run_scheduler()
