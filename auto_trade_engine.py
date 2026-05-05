# auto_trade_engine.py — RSI Bot v3 Auto Buy/Sell Engine
# Paper trading simulation with full filter pipeline
# Filters: Blacklist → Earnings → ATR → Nifty50 → News → RSI+MACD entry
# Exit: Fixed SL 5% | TSL activates at +10%, trails 5%

import json
import os
import time
import threading
import schedule
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import pytz

from blacklist import is_blacklisted, record_trade as blacklist_record
from gainers  import get_position_multiplier, get_adjusted_allocation, record_trade as gainers_record

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
PAPER_TRADES_FILE   = "logs/paper_trades.json"
OPEN_POSITIONS_FILE = "logs/open_positions.json"

BASE_CAPITAL        = 100_000.0   # ₹1,00,000 virtual capital
MAX_CAPITAL_PER_TRADE = 5_000.0   # ₹5,000 base allocation per trade
MAX_OPEN_POSITIONS  = 5           # max simultaneous positions
BROKERAGE_PCT       = 0.001       # 0.1% brokerage simulation

# RSI settings
RSI_PERIOD          = 14
RSI_BUY_THRESHOLD   = 35          # buy when RSI crosses above this
RSI_SELL_THRESHOLD  = 70          # optional overbought exit

# MACD settings
MACD_FAST           = 12
MACD_SLOW           = 26
MACD_SIGNAL         = 9

# Stop-loss / TSL settings
FIXED_SL_PCT        = 0.05        # 5% fixed stop-loss
TSL_ACTIVATE_PCT    = 0.10        # activate TSL when +10% profit
TSL_TRAIL_PCT       = 0.05        # trail 5% below peak

# ATR filter
ATR_PERIOD          = 14
ATR_MIN_PCT         = 0.015       # min ATR/price = 1.5% (skip low volatility)

# Nifty50 sentiment
NIFTY_SYMBOL        = "^NSEI"
NIFTY_SMA_PERIOD    = 20

# Watchlist — NSE symbols with .NS suffix for yfinance
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS",     "INFY.NS",   "HDFCBANK.NS", "ICICIBANK.NS",
    "WIPRO.NS",    "BAJFINANCE.NS","HINDUNILVR.NS","SBIN.NS", "ADANIENT.NS",
    "TATAMOTORS.NS","SUNPHARMA.NS","AXISBANK.NS","LT.NS",    "MARUTI.NS",
]

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# FILE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def load_open_positions() -> dict:
    from db_state import load_state as _db_load
    db = _db_load()
    if db and db.get("positions"):
        positions = db["positions"]
        # Normalize keys from main.py format to engine format
        for sym, p in positions.items():
            if "stop_loss" in p and "sl_price" not in p:
                p["sl_price"] = p["stop_loss"]
            if "highest_price" in p and "peak_price" not in p:
                p["peak_price"] = p["highest_price"]
            if "allocation" not in p:
                p["allocation"] = round(p["buy_price"] * p["qty"], 2)
            if "buy_time" in p and "entry_time" not in p:
                p["entry_time"] = p["buy_time"]
        return positions
    return _load_json(OPEN_POSITIONS_FILE, {})


def _save_json(path: str, data):
    os.makedirs("logs", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)





def save_open_positions(positions: dict):
    _save_json(OPEN_POSITIONS_FILE, positions)


def load_paper_trades() -> list:
    return _load_json(PAPER_TRADES_FILE, [])


def append_paper_trade(trade: dict):
    trades = load_paper_trades()
    trades.append(trade)
    _save_json(PAPER_TRADES_FILE, trades)


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────
def calc_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(close: pd.Series):
    ema_fast   = close.ewm(span=MACD_FAST,   adjust=False).mean()
    ema_slow   = close.ewm(span=MACD_SLOW,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal     = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram  = macd_line - signal
    return macd_line, signal, histogram


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series,
             period: int = ATR_PERIOD) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


# ─────────────────────────────────────────────────────────────────────────────
# FILTER 1 — BLACKLIST
# ─────────────────────────────────────────────────────────────────────────────
def filter_blacklist(symbol: str) -> tuple[bool, str]:
    """Returns (passed, reason). passed=True means OK to trade."""
    if is_blacklisted(symbol):
        return False, f"{symbol} is blacklisted"
    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# FILTER 2 — EARNINGS DATE (within 3 days)
# ─────────────────────────────────────────────────────────────────────────────
def filter_earnings(symbol: str) -> tuple[bool, str]:
    """Block if earnings announcement within next 3 days."""
    try:
        ticker = yf.Ticker(symbol)
        cal    = ticker.calendar
        if cal is None or cal.empty:
            return True, "No earnings data"

        # calendar may have 'Earnings Date' as index or column
        if hasattr(cal, 'T'):
            cal = cal.T
        for col in ["Earnings Date", "earnings_date"]:
            if col in cal.columns:
                ed = pd.to_datetime(cal[col].iloc[0])
                days_away = (ed - pd.Timestamp.now()).days
                if 0 <= days_away <= 3:
                    return False, f"Earnings in {days_away} day(s) ({ed.date()})"
        return True, "No upcoming earnings"
    except Exception as e:
        return True, f"Earnings check skipped: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# FILTER 3 — ATR VOLATILITY (skip if too low)
# ─────────────────────────────────────────────────────────────────────────────
def filter_atr(df: pd.DataFrame, symbol: str) -> tuple[bool, str]:
    """Block if ATR/price < ATR_MIN_PCT (stock too quiet to trade)."""
    try:
        atr   = calc_atr(df["High"], df["Low"], df["Close"]).iloc[-1]
        price = df["Close"].iloc[-1]
        atr_pct = atr / price
        if atr_pct < ATR_MIN_PCT:
            return False, f"ATR too low: {atr_pct*100:.2f}% < {ATR_MIN_PCT*100:.1f}%"
        return True, f"ATR OK: {atr_pct*100:.2f}%"
    except Exception as e:
        return True, f"ATR check skipped: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# FILTER 4 — NIFTY50 SENTIMENT
# ─────────────────────────────────────────────────────────────────────────────
def get_nifty_sentiment() -> tuple[bool, str]:
    """
    Bullish if Nifty50 is above its 20-SMA AND RSI > 45.
    Returns (is_bullish, reason).
    """
    try:
        df    = yf.download(NIFTY_SYMBOL, period="60d", interval="1d",
                            progress=False, auto_adjust=True)
        if df.empty or len(df) < NIFTY_SMA_PERIOD + 5:
            return True, "Nifty data unavailable — skipping"

        close = df["Close"].squeeze()
        sma   = close.rolling(NIFTY_SMA_PERIOD).mean().iloc[-1]
        rsi   = calc_rsi(close).iloc[-1]
        price = close.iloc[-1]

        if price > sma and rsi > 45:
            return True,  f"Nifty bullish: ₹{price:.0f} > SMA {sma:.0f}, RSI {rsi:.1f}"
        return False, f"Nifty bearish: ₹{price:.0f} vs SMA {sma:.0f}, RSI {rsi:.1f}"
    except Exception as e:
        return True, f"Nifty check skipped: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# FILTER 5 — NEWS SENTIMENT (lightweight keyword scan via yfinance news)
# ─────────────────────────────────────────────────────────────────────────────
NEGATIVE_KEYWORDS = [
    "fraud", "scam", "investigation", "probe", "sebi", "ed ",
    "arrest", "default", "insolvency", "bankruptcy", "loss", "decline",
    "downgrade", "recall", "penalty", "fine", "lawsuit", "suspended",
]

POSITIVE_KEYWORDS = ["buyback", "dividend", "upgrade", "acquisition", "profit",
                     "record", "beat", "strong", "growth"]


def filter_news(symbol: str) -> tuple[bool, str]:
    """Block if recent news has strong negative sentiment."""
    try:
        ticker   = yf.Ticker(symbol)
        news     = ticker.news or []
        if not news:
            return True, "No news found"

        negative = 0
        positive = 0
        checked  = 0
        for article in news[:5]:                     # check last 5 headlines
            title = (article.get("title") or "").lower()
            if not title:
                continue
            checked += 1
            negative += sum(1 for kw in NEGATIVE_KEYWORDS if kw in title)
            positive += sum(1 for kw in POSITIVE_KEYWORDS if kw in title)

        if negative >= 2:
            return False, f"Negative news detected ({negative} flags in {checked} headlines)"
        return True, f"News OK (neg={negative}, pos={positive})"
    except Exception as e:
        return True, f"News check skipped: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY SIGNAL — RSI + MACD
# ─────────────────────────────────────────────────────────────────────────────
def get_entry_signal(df: pd.DataFrame) -> tuple[bool, dict]:
    """
    BUY when:
      - RSI crosses above RSI_BUY_THRESHOLD (was below, now above)
      - MACD line crosses above signal line (bullish crossover)
    """
    try:
        close      = df["Close"].squeeze()
        rsi        = calc_rsi(close)
        macd, sig, hist = calc_macd(close)

        rsi_now    = rsi.iloc[-1]
        rsi_prev   = rsi.iloc[-2]
        macd_now   = macd.iloc[-1]
        macd_prev  = macd.iloc[-2]
        sig_now    = sig.iloc[-1]
        sig_prev   = sig.iloc[-2]

        rsi_cross  = rsi_prev <= RSI_BUY_THRESHOLD and rsi_now > RSI_BUY_THRESHOLD
        macd_cross = macd_prev <= sig_prev and macd_now > sig_now

        signal = {
            "rsi"       : round(float(rsi_now),  2),
            "rsi_prev"  : round(float(rsi_prev), 2),
            "macd"      : round(float(macd_now), 4),
            "signal"    : round(float(sig_now),  4),
            "rsi_cross" : rsi_cross,
            "macd_cross": macd_cross,
            "price"     : round(float(close.iloc[-1]), 2),
        }
        return (rsi_cross and macd_cross), signal
    except Exception as e:
        return False, {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# PAPER ORDER EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
def paper_buy(symbol: str, price: float, allocation: float,
              signal: dict, filter_log: list) -> dict:
    """Simulate a BUY order."""
    brokerage = round(allocation * BROKERAGE_PCT, 2)
    qty       = int((allocation - brokerage) / price)
    if qty < 1:
        return {"success": False, "reason": "Insufficient allocation for even 1 share"}

    actual_cost = round(qty * price + brokerage, 2)
    sl_price    = round(price * (1 - FIXED_SL_PCT), 2)

    position = {
        "symbol"       : symbol,
        "qty"          : qty,
        "buy_price"    : price,
        "sl_price"     : sl_price,
        "tsl_active"   : False,
        "peak_price"   : price,
        "tsl_price"    : None,
        "allocation"   : actual_cost,
        "brokerage"    : brokerage,
        "entry_time"   : datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S"),
        "signal"       : signal,
        "filter_log"   : filter_log,
        "status"       : "OPEN",
    }

    positions = load_open_positions()
    positions[symbol] = position
    save_open_positions(positions)

    trade_log = {**position, "type": "BUY", "cost": actual_cost}
    append_paper_trade(trade_log)

    print(f"  🟢 PAPER BUY  {symbol:20s} ₹{price:>8.2f} × {qty} qty"
          f"  SL ₹{sl_price:.2f}  [{datetime.now(IST).strftime('%H:%M:%S')}]")
    return {"success": True, "position": position}


def paper_sell(symbol: str, exit_price: float, reason: str) -> dict:
    """Simulate a SELL order and record result."""
    positions = load_open_positions()
    if symbol not in positions:
        return {"success": False, "reason": "No open position"}

    pos       = positions.pop(symbol)
    qty       = pos["qty"]
    buy_price = pos["buy_price"]
    brokerage = round(exit_price * qty * BROKERAGE_PCT, 2)
    pnl       = round((exit_price - buy_price) * qty - brokerage - pos["brokerage"], 2)
    pnl_pct   = round((exit_price - buy_price) / buy_price * 100, 2)
    result    = "WIN" if pnl > 0 else "LOSS"

    trade_log = {
        "symbol"    : symbol,
        "type"      : "SELL",
        "qty"       : qty,
        "buy_price" : buy_price,
        "sell_price": exit_price,
        "pnl"       : pnl,
        "pnl_pct"   : pnl_pct,
        "result"    : result,
        "reason"    : reason,
        "exit_time" : datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S"),
        "hold_since": pos["entry_time"],
    }
    append_paper_trade(trade_log)
    save_open_positions(positions)

    # Update blacklist and gainers systems
    blacklist_record(symbol, result, pnl, pnl_pct)
    gainers_record(symbol,  result, pnl, pnl_pct)

    emoji = "💚" if result == "WIN" else "🔴"
    print(f"  {emoji} PAPER SELL {symbol:20s} ₹{exit_price:>8.2f}  "
          f"P&L ₹{pnl:>8.2f} ({pnl_pct:+.1f}%)  [{reason}]")
    return {"success": True, "trade": trade_log}


# ─────────────────────────────────────────────────────────────────────────────
# TSL UPDATER — called on every price tick for open positions
# ─────────────────────────────────────────────────────────────────────────────
def update_tsl(symbol: str, current_price: float) -> Optional[str]:
    """
    Update TSL for an open position.
    Returns exit_reason if SL/TSL is hit, else None.
    """
    positions = load_open_positions()
    if symbol not in positions:
        return None

    pos = positions[symbol]

    # Update peak price
    if current_price > pos["peak_price"]:
        pos["peak_price"] = current_price

    profit_pct = (current_price - pos["buy_price"]) / pos["buy_price"]

    # Activate TSL when profit hits TSL_ACTIVATE_PCT
    if not pos["tsl_active"] and profit_pct >= TSL_ACTIVATE_PCT:
        pos["tsl_active"] = True
        pos["tsl_price"]  = round(pos["peak_price"] * (1 - TSL_TRAIL_PCT), 2)
        print(f"  🔔 TSL ACTIVATED for {symbol} at ₹{pos['tsl_price']:.2f}")

    # Update TSL level (trail up with peak)
    if pos["tsl_active"]:
        new_tsl = round(pos["peak_price"] * (1 - TSL_TRAIL_PCT), 2)
        if new_tsl > pos["tsl_price"]:
            pos["tsl_price"] = new_tsl

    # Check exits
    if pos["tsl_active"] and current_price <= pos["tsl_price"]:
        positions[symbol] = pos
        save_open_positions(positions)
        return f"TSL hit ₹{pos['tsl_price']:.2f}"

    if current_price <= pos["sl_price"]:
        positions[symbol] = pos
        save_open_positions(positions)
        return f"Fixed SL hit ₹{pos['sl_price']:.2f}"

    # Overbought RSL exit (optional)
    # if rsi > RSI_SELL_THRESHOLD: return "RSI overbought"

    positions[symbol] = pos
    save_open_positions(positions)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCAN — runs on schedule
# ─────────────────────────────────────────────────────────────────────────────
def run_scan(symbols: list = None, force: bool = False) -> dict:
    """
    Full pipeline:
    1. Check market hours (skip if closed, unless force=True)
    2. Get Nifty sentiment (once per scan)
    3. For each symbol: run all filters → check entry signal → paper buy
    4. For open positions: update TSL → paper sell if hit
    Returns summary dict.
    """
    now = datetime.now(IST)
    symbols = symbols or WATCHLIST

    # ── Market hours check ────────────────────────────────────────────────────
    if not force:
        if now.weekday() >= 5:                           # Saturday/Sunday
            return {"skipped": "Market closed (weekend)"}
        market_open  = now.replace(hour=9,  minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        if not (market_open <= now <= market_close):
            return {"skipped": f"Market closed ({now.strftime('%H:%M IST')})"}

    print(f"\n{'='*60}")
    print(f"  RSI BOT SCAN  [{now.strftime('%d-%b-%Y %H:%M IST')}]")
    print(f"{'='*60}")

    # ── Nifty sentiment (shared across all symbols) ───────────────────────────
    nifty_ok, nifty_reason = get_nifty_sentiment()
    print(f"  Nifty: {'✅' if nifty_ok else '❌'} {nifty_reason}")

    positions   = load_open_positions()
    open_count  = len(positions)
    buys        = []
    sells       = []
    skipped     = []

    # ── EXIT CHECK — update TSL for all open positions ────────────────────────
    print(f"\n  Checking {open_count} open position(s)...")
    for sym in list(positions.keys()):
        try:
            df = yf.download(sym, period="2d", interval="5m",
                             progress=False, auto_adjust=True)
            if df.empty:
                continue
            price = float(df["Close"].squeeze().iloc[-1])
            exit_reason = update_tsl(sym, price)
            if exit_reason:
                result = paper_sell(sym, price, exit_reason)
                if result["success"]:
                    sells.append(result["trade"])
                    open_count -= 1
        except Exception as e:
            print(f"  ⚠ Exit check error {sym}: {e}")

    # ── ENTRY SCAN ────────────────────────────────────────────────────────────
    if open_count >= MAX_OPEN_POSITIONS:
        print(f"\n  Max positions ({MAX_OPEN_POSITIONS}) reached — skipping entry scan")
    else:
        print(f"\n  Scanning {len(symbols)} symbols for entry ({open_count}/{MAX_OPEN_POSITIONS} open)...")
        positions = load_open_positions()          # reload after sells

        for symbol in symbols:
            if symbol in positions:
                skipped.append({"symbol": symbol, "reason": "Already in position"})
                continue
            if open_count >= MAX_OPEN_POSITIONS:
                break

            filter_log = []

            # Filter 1 — Blacklist
            ok, reason = filter_blacklist(symbol)
            filter_log.append({"filter": "blacklist", "passed": ok, "reason": reason})
            if not ok:
                skipped.append({"symbol": symbol, "reason": reason})
                print(f"  ⛔ {symbol:<20} SKIP — {reason}")
                continue

            # Fetch OHLCV data (needed for ATR + signal)
            try:
                df = yf.download(symbol, period="90d", interval="1d",
                                 progress=False, auto_adjust=True)
                if df.empty or len(df) < 40:
                    skipped.append({"symbol": symbol, "reason": "Insufficient data"})
                    continue
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            except Exception as e:
                skipped.append({"symbol": symbol, "reason": f"Data error: {e}"})
                continue

            # Filter 2 — Earnings
            ok, reason = filter_earnings(symbol)
            filter_log.append({"filter": "earnings", "passed": ok, "reason": reason})
            if not ok:
                skipped.append({"symbol": symbol, "reason": reason})
                print(f"  📅 {symbol:<20} SKIP — {reason}")
                continue

            # Filter 3 — ATR
            ok, reason = filter_atr(df, symbol)
            filter_log.append({"filter": "atr", "passed": ok, "reason": reason})
            if not ok:
                skipped.append({"symbol": symbol, "reason": reason})
                print(f"  📉 {symbol:<20} SKIP — {reason}")
                continue

            # Filter 4 — Nifty sentiment
            filter_log.append({"filter": "nifty", "passed": nifty_ok, "reason": nifty_reason})
            if not nifty_ok:
                skipped.append({"symbol": symbol, "reason": nifty_reason})
                print(f"  🌐 {symbol:<20} SKIP — {nifty_reason}")
                continue

            # Filter 5 — News
            ok, reason = filter_news(symbol)
            filter_log.append({"filter": "news", "passed": ok, "reason": reason})
            if not ok:
                skipped.append({"symbol": symbol, "reason": reason})
                print(f"  📰 {symbol:<20} SKIP — {reason}")
                continue

            # Entry signal — RSI + MACD
            entry, signal = get_entry_signal(df)
            filter_log.append({
                "filter": "signal",
                "passed": entry,
                "reason": f"RSI {signal.get('rsi', '?')} MACD cross={signal.get('macd_cross', '?')}"
            })
            if not entry:
                print(f"  ⚪ {symbol:<20} NO SIGNAL — RSI {signal.get('rsi','?'):.1f}")
                skipped.append({"symbol": symbol, "reason": "No entry signal"})
                continue

            # All filters passed — calculate position size
            price      = signal["price"]
            multiplier = get_position_multiplier(symbol)
            allocation = get_adjusted_allocation(symbol, MAX_CAPITAL_PER_TRADE)

            result = paper_buy(symbol, price, allocation, signal, filter_log)
            if result["success"]:
                buys.append(result["position"])
                open_count += 1

    summary = {
        "scan_time"     : now.strftime("%d-%b-%Y %H:%M IST"),
        "nifty_bullish" : nifty_ok,
        "buys"          : buys,
        "sells"         : sells,
        "skipped_count" : len(skipped),
        "open_positions": len(load_open_positions()),
    }

    print(f"\n  ✅ Scan complete — Buys: {len(buys)}  Sells: {len(sells)}"
          f"  Skipped: {len(skipped)}  Open: {summary['open_positions']}")
    print(f"{'='*60}\n")
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER — background thread
# ─────────────────────────────────────────────────────────────────────────────
_scheduler_thread = None
_scheduler_running = False


def start_scheduler():
    """Start background scan scheduler."""
    global _scheduler_running, _scheduler_thread

    if _scheduler_running:
        return {"status": "already_running"}

    schedule.clear()

    # Scan every 15 minutes during market hours
    for hh in range(9, 16):
        for mm in [0, 15, 30, 45]:
            if hh == 9 and mm < 15:
                continue                        # market opens at 9:15
            if hh == 15 and mm > 30:
                continue                        # market closes at 15:30
            schedule.every().day.at(f"{hh:02d}:{mm:02d}").do(run_scan)

    def _run():
        global _scheduler_running
        _scheduler_running = True
        print("  ⏰ Scheduler started — scanning every 15 min (9:15–15:30 IST)")
        while _scheduler_running:
            schedule.run_pending()
            time.sleep(30)

    _scheduler_thread = threading.Thread(target=_run, daemon=True)
    _scheduler_thread.start()
    return {"status": "started"}


def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False
    schedule.clear()
    return {"status": "stopped"}


def scheduler_status() -> dict:
    return {
        "running"      : _scheduler_running,
        "next_run"     : str(schedule.next_run()) if schedule.jobs else None,
        "job_count"    : len(schedule.jobs),
        "open_positions": len(load_open_positions()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
def get_portfolio_summary() -> dict:
    """Current open positions with live P&L."""
    positions = load_open_positions()
    rows      = []
    total_invested = 0
    total_pnl      = 0
    for symbol, pos in positions.items():
        try:
            df    = yf.download(symbol, period="1d", interval="1m",
                                progress=False, auto_adjust=True)
            price = float(df["Close"].squeeze().iloc[-1]) if not df.empty else pos["buy_price"]
        except Exception:
            price = pos["buy_price"]

        pnl     = round((price - pos["buy_price"]) * pos["qty"], 2)
        pnl_pct = round((price - pos["buy_price"]) / pos["buy_price"] * 100, 2)
        total_invested += pos.get("allocation", pos["buy_price"] * pos["qty"])
        USD_TO_INR = 84.0
        pnl_inr = round(pnl * USD_TO_INR, 2) if pos.get("itype") == "US_STOCK" else pnl
        total_pnl += pnl_inr
        rows.append({
            "symbol"    : symbol,
            "qty"       : pos["qty"],
            "buy_price" : pos["buy_price"],
            "ltp"       : round(price, 2),
            "pnl"       : pnl,
            "pnl_pct"   : pnl_pct,
            "sl_price"  : pos.get("stop_loss", pos.get("sl_price", 0)),
            "target"    : pos.get("target", pos.get("tp_price", 0)),
            "tsl_active": pos.get("tsl_active", False),
            "itype"     : pos.get("itype", "?"),
        })

    return {
        "positions"      : rows,
        "total_invested" : round(total_invested, 2),
        "total_pnl"      : round(total_pnl, 2),
        "total_pnl_pct"  : round(total_pnl / total_invested * 100, 2) if total_invested else 0,
        "open_count"     : len(rows),
        "max_positions"  : MAX_OPEN_POSITIONS,
    }

