# blacklist.py — Automatic loser detection and blacklist system
# Tracks win/loss per symbol and auto-blacklists consistent losers

import json
import os
from datetime import datetime

BLACKLIST_FILE   = "logs/blacklist.json"
MIN_TRADES       = 3      # minimum trades before blacklisting
MAX_WIN_RATE     = 0.40   # blacklist if win rate below 40%
MAX_LOSSES       = 3      # blacklist if 3+ consecutive losses


# ─────────────────────────────────────────────────────────────────────────────
def _load() -> dict:
    """Load blacklist data from file."""
    if not os.path.exists(BLACKLIST_FILE):
        os.makedirs("logs", exist_ok=True)
        data = {"blacklisted": [], "history": {}}
        _save(data)
        return data
    try:
        with open(BLACKLIST_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"blacklisted": [], "history": {}}


def _save(data: dict):
    """Save blacklist data to file."""
    os.makedirs("logs", exist_ok=True)
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
def is_blacklisted(symbol: str) -> bool:
    """Check if a symbol is blacklisted."""
    data = _load()
    return symbol in data["blacklisted"]


def get_blacklist() -> list:
    """Return full blacklist."""
    return _load()["blacklisted"]


def manually_blacklist(symbol: str, reason: str = "Manual"):
    """Manually blacklist a symbol."""
    data = _load()
    if symbol not in data["blacklisted"]:
        data["blacklisted"].append(symbol)
        if symbol not in data["history"]:
            data["history"][symbol] = {"trades": [], "wins": 0, "losses": 0, "consecutive_losses": 0}
        data["history"][symbol]["manual_blacklist"] = True
        data["history"][symbol]["reason"] = reason
        data["history"][symbol]["blacklisted_at"] = datetime.now().strftime("%d-%b-%Y %H:%M")
        _save(data)
        print(f"  ⛔ {symbol} manually blacklisted: {reason}")


def manually_whitelist(symbol: str):
    """Remove a symbol from blacklist."""
    data = _load()
    if symbol in data["blacklisted"]:
        data["blacklisted"].remove(symbol)
        if symbol in data["history"]:
            data["history"][symbol]["blacklisted"] = False
            data["history"][symbol]["whitelisted_at"] = datetime.now().strftime("%d-%b-%Y %H:%M")
        _save(data)
        print(f"  ✅ {symbol} removed from blacklist")


# ─────────────────────────────────────────────────────────────────────────────
def record_trade(symbol: str, result: str, pnl: float, pnl_pct: float) -> dict:
    """
    Record a completed trade and check if symbol should be blacklisted.
    result: 'WIN' or 'LOSS'
    Returns: dict with blacklisted=True/False and reason
    """
    data = _load()

    # Init history for symbol
    if symbol not in data["history"]:
        data["history"][symbol] = {
            "trades"             : [],
            "wins"               : 0,
            "losses"             : 0,
            "consecutive_losses" : 0,
            "total_pnl"          : 0.0,
        }

    h = data["history"][symbol]

    # Record this trade
    h["trades"].append({
        "result"  : result,
        "pnl"     : round(pnl, 2),
        "pnl_pct" : round(pnl_pct, 2),
        "date"    : datetime.now().strftime("%d-%b-%Y %H:%M"),
    })
    h["total_pnl"] = round(h.get("total_pnl", 0) + pnl, 2)

    if result == "WIN":
        h["wins"]               += 1
        h["consecutive_losses"]  = 0   # reset streak
    else:
        h["losses"]             += 1
        h["consecutive_losses"] += 1

    total_trades = h["wins"] + h["losses"]
    win_rate     = h["wins"] / total_trades if total_trades > 0 else 0

    # ── Check blacklist conditions ────────────────────────────────────────────
    blacklist_reason = None

    if total_trades >= MIN_TRADES:
        if win_rate < MAX_WIN_RATE:
            blacklist_reason = (
                f"Win rate {win_rate*100:.0f}% below {MAX_WIN_RATE*100:.0f}% "
                f"after {total_trades} trades"
            )

    if h["consecutive_losses"] >= MAX_LOSSES:
        blacklist_reason = (
            f"{h['consecutive_losses']} consecutive losses"
        )

    if blacklist_reason and symbol not in data["blacklisted"]:
        data["blacklisted"].append(symbol)
        h["blacklisted"]    = True
        h["blacklisted_at"] = datetime.now().strftime("%d-%b-%Y %H:%M")
        h["reason"]         = blacklist_reason
        _save(data)
        print(f"  ⛔ AUTO-BLACKLISTED: {symbol} — {blacklist_reason}")
        return {
            "blacklisted" : True,
            "reason"      : blacklist_reason,
            "win_rate"    : win_rate,
            "total_trades": total_trades,
            "total_pnl"   : h["total_pnl"],
        }

    _save(data)
    return {
        "blacklisted" : False,
        "win_rate"    : win_rate,
        "total_trades": total_trades,
        "total_pnl"   : h["total_pnl"],
    }


# ─────────────────────────────────────────────────────────────────────────────
def get_performance_summary() -> list:
    """Return performance summary for all tracked symbols."""
    data   = _load()
    result = []
    for symbol, h in data["history"].items():
        total  = h["wins"] + h["losses"]
        wr     = h["wins"] / total * 100 if total > 0 else 0
        result.append({
            "symbol"      : symbol,
            "trades"      : total,
            "wins"        : h["wins"],
            "losses"      : h["losses"],
            "win_rate"    : round(wr, 1),
            "total_pnl"   : h.get("total_pnl", 0),
            "blacklisted" : symbol in data["blacklisted"],
            "con_losses"  : h.get("consecutive_losses", 0),
        })
    return sorted(result, key=lambda x: x["total_pnl"], reverse=True)


def print_summary():
    """Print full performance and blacklist summary."""
    summary     = get_performance_summary()
    blacklisted = get_blacklist()

    print("\n" + "=" * 60)
    print("  SYMBOL PERFORMANCE & BLACKLIST STATUS")
    print("=" * 60)
    print(f"  {'Symbol':<15} {'Trades':>6} {'WinRate':>8} {'P&L':>10} {'Status':>12}")
    print("-" * 60)
    for s in summary:
        status = "⛔ BLACKLISTED" if s["blacklisted"] else "✅ Active"
        print(
            f"  {s['symbol']:<15} {s['trades']:>6} "
            f"{s['win_rate']:>7.1f}% ₹{s['total_pnl']:>8.2f}  {status}"
        )
    print("=" * 60)
    print(f"  Blacklisted ({len(blacklisted)}): {', '.join(blacklisted) or 'None'}")
    print("=" * 60)
