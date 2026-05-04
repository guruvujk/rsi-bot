# gainers.py — Automatic winning stock detection system
# Tracks performance and auto-promotes consistent winners
# Position size increases automatically for favorites

import json
import os
from datetime import datetime

GAINERS_FILE       = "logs/gainers.json"
MIN_TRADES         = 3      # minimum trades before promoting
MIN_WIN_RATE       = 0.65   # promote if win rate above 65%
MIN_CONSECUTIVE    = 3      # promote if 3+ consecutive wins
FAVORITE_MULTIPLIER = 1.5   # 1.5x position size for favorites
STAR_MULTIPLIER     = 2.0   # 2x position size for star performers

# ── Tier system ──────────────────────────────────────────────────────────────
# NORMAL   → standard position size (1x)
# FAVORITE → 1.5x position size (win rate > 65%)
# STAR     → 2.0x position size (win rate > 80%)
# LEGEND   → 2.5x position size (win rate > 90%)


def _load() -> dict:
    if not os.path.exists(GAINERS_FILE):
        os.makedirs("logs", exist_ok=True)
        data = {"favorites": [], "stars": [], "legends": [], "history": {}}
        _save(data)
        return data
    try:
        with open(GAINERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"favorites": [], "stars": [], "legends": [], "history": {}}


def _save(data: dict):
    os.makedirs("logs", exist_ok=True)
    with open(GAINERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
def get_tier(symbol: str) -> str:
    """Return tier for a symbol: NORMAL / FAVORITE / STAR / LEGEND"""
    data = _load()
    if symbol in data.get("legends",   []): return "LEGEND"
    if symbol in data.get("stars",     []): return "STAR"
    if symbol in data.get("favorites", []): return "FAVORITE"
    return "NORMAL"


def get_position_multiplier(symbol: str) -> float:
    """
    Return position size multiplier based on tier.
    NORMAL=1.0, FAVORITE=1.5, STAR=2.0, LEGEND=2.5
    """
    tier = get_tier(symbol)
    return {
        "NORMAL"  : 1.0,
        "FAVORITE": 1.5,
        "STAR"    : 2.0,
        "LEGEND"  : 2.5,
    }.get(tier, 1.0)


def get_all_favorites() -> dict:
    """Return all promoted symbols grouped by tier."""
    data = _load()
    return {
        "favorites": data.get("favorites", []),
        "stars"    : data.get("stars",     []),
        "legends"  : data.get("legends",   []),
    }


# ─────────────────────────────────────────────────────────────────────────────
def _promote(data: dict, symbol: str, new_tier: str, old_tier: str, stats: dict) -> dict:
    """Move symbol to a higher tier."""
    # Remove from all tiers first
    for tier in ["favorites", "stars", "legends"]:
        if symbol in data.get(tier, []):
            data[tier].remove(symbol)

    # Add to new tier
    if new_tier != "NORMAL":
        if new_tier.lower() + "s" not in data:
            data[new_tier.lower() + "s"] = []
        data[new_tier.lower() + "s"].append(symbol)

    # Update history
    if symbol in data["history"]:
        data["history"][symbol]["tier"]        = new_tier
        data["history"][symbol]["promoted_at"] = datetime.now().strftime("%d-%b-%Y %H:%M")
        data["history"][symbol]["promoted_from"] = old_tier

    multiplier = get_position_multiplier(symbol)
    print(
        f"  ⭐ PROMOTED: {symbol} → {new_tier} "
        f"(win rate {stats['win_rate']*100:.0f}%, "
        f"position size {multiplier}x)"
    )
    return data


def _demote(data: dict, symbol: str, reason: str) -> dict:
    """Move symbol back to NORMAL tier."""
    old_tier = get_tier(symbol)
    for tier in ["favorites", "stars", "legends"]:
        if symbol in data.get(tier, []):
            data[tier].remove(symbol)
    if symbol in data["history"]:
        data["history"][symbol]["tier"]       = "NORMAL"
        data["history"][symbol]["demoted_at"] = datetime.now().strftime("%d-%b-%Y %H:%M")
        data["history"][symbol]["demoted_from"] = old_tier
        data["history"][symbol]["demotion_reason"] = reason
    print(f"  📉 DEMOTED: {symbol} → NORMAL ({reason})")
    return data


# ─────────────────────────────────────────────────────────────────────────────
def record_trade(symbol: str, result: str, pnl: float, pnl_pct: float) -> dict:
    """
    Record a completed trade and check if symbol should be promoted/demoted.
    Returns dict with tier, multiplier, promoted/demoted flags.
    """
    data = _load()

    if symbol not in data["history"]:
        data["history"][symbol] = {
            "trades"            : [],
            "wins"              : 0,
            "losses"            : 0,
            "consecutive_wins"  : 0,
            "consecutive_losses": 0,
            "total_pnl"         : 0.0,
            "tier"              : "NORMAL",
        }

    h        = data["history"][symbol]
    old_tier = get_tier(symbol)

    # Record trade
    h["trades"].append({
        "result"  : result,
        "pnl"     : round(pnl, 2),
        "pnl_pct" : round(pnl_pct, 2),
        "date"    : datetime.now().strftime("%d-%b-%Y %H:%M"),
    })
    h["total_pnl"] = round(h.get("total_pnl", 0) + pnl, 2)

    if result == "WIN":
        h["wins"]               += 1
        h["consecutive_wins"]   += 1
        h["consecutive_losses"]  = 0
    else:
        h["losses"]             += 1
        h["consecutive_losses"] += 1
        h["consecutive_wins"]    = 0

    total_trades = h["wins"] + h["losses"]
    win_rate     = h["wins"] / total_trades if total_trades > 0 else 0
    avg_pnl      = h["total_pnl"] / total_trades if total_trades > 0 else 0

    stats = {
        "win_rate"    : win_rate,
        "total_trades": total_trades,
        "total_pnl"   : h["total_pnl"],
        "avg_pnl"     : avg_pnl,
        "con_wins"    : h["consecutive_wins"],
        "con_losses"  : h["consecutive_losses"],
    }

    promoted = False
    demoted  = False
    new_tier = old_tier

    # ── PROMOTION logic ───────────────────────────────────────────────────────
    if total_trades >= MIN_TRADES:

        if win_rate >= 0.90 and old_tier != "LEGEND":
            data    = _promote(data, symbol, "LEGEND", old_tier, stats)
            new_tier = "LEGEND"
            promoted = True

        elif win_rate >= 0.80 and old_tier in ["NORMAL", "FAVORITE"]:
            data    = _promote(data, symbol, "STAR", old_tier, stats)
            new_tier = "STAR"
            promoted = True

        elif win_rate >= MIN_WIN_RATE and old_tier == "NORMAL":
            data    = _promote(data, symbol, "FAVORITE", old_tier, stats)
            new_tier = "FAVORITE"
            promoted = True

        elif h["consecutive_wins"] >= MIN_CONSECUTIVE and old_tier == "NORMAL":
            data    = _promote(data, symbol, "FAVORITE", old_tier, stats)
            new_tier = "FAVORITE"
            promoted = True

    # ── DEMOTION logic ────────────────────────────────────────────────────────
    if old_tier != "NORMAL" and total_trades >= MIN_TRADES:
        if win_rate < 0.50 and old_tier in ["FAVORITE"]:
            data    = _demote(data, symbol, f"Win rate dropped to {win_rate*100:.0f}%")
            new_tier = "NORMAL"
            demoted  = True
        elif win_rate < 0.65 and old_tier in ["STAR", "LEGEND"]:
            data    = _demote(data, symbol, f"Win rate dropped to {win_rate*100:.0f}%")
            new_tier = "NORMAL"
            demoted  = True
        elif h["consecutive_losses"] >= 3 and old_tier != "NORMAL":
            data    = _demote(data, symbol, f"{h['consecutive_losses']} consecutive losses")
            new_tier = "NORMAL"
            demoted  = True

    _save(data)

    multiplier = get_position_multiplier(symbol)
    return {
        "symbol"    : symbol,
        "old_tier"  : old_tier,
        "new_tier"  : new_tier,
        "multiplier": multiplier,
        "promoted"  : promoted,
        "demoted"   : demoted,
        "stats"     : stats,
    }


# ─────────────────────────────────────────────────────────────────────────────
def get_adjusted_allocation(symbol: str, base_allocation: float) -> float:
    """
    Return adjusted position size based on symbol tier.
    base_allocation: your standard MAX_CAPITAL_PER_TRADE (e.g. ₹5,000)
    """
    multiplier = get_position_multiplier(symbol)
    return round(base_allocation * multiplier, 2)


# ─────────────────────────────────────────────────────────────────────────────
def print_summary():
    """Print full gainer performance summary."""
    data    = _load()
    history = data.get("history", {})

    tier_emoji = {
        "LEGEND"  : "👑",
        "STAR"    : "🌟",
        "FAVORITE": "⭐",
        "NORMAL"  : "  ",
    }

    print("\n" + "=" * 70)
    print("  GAINER PERFORMANCE SUMMARY")
    print("=" * 70)
    print(f"  {'':2} {'Symbol':<15} {'Trades':>6} {'WinRate':>8} "
          f"{'AvgP&L':>10} {'TotalP&L':>12} {'Size':>6}")
    print("-" * 70)

    rows = []
    for symbol, h in history.items():
        total = h["wins"] + h["losses"]
        wr    = h["wins"] / total * 100 if total > 0 else 0
        ap    = h["total_pnl"] / total if total > 0 else 0
        tier  = h.get("tier", "NORMAL")
        mult  = get_position_multiplier(symbol)
        rows.append((symbol, tier, total, wr, ap, h["total_pnl"], mult))

    # Sort by total P&L descending
    for symbol, tier, total, wr, ap, tp, mult in sorted(rows, key=lambda x: x[5], reverse=True):
        emoji = tier_emoji.get(tier, "  ")
        print(
            f"  {emoji} {symbol:<15} {total:>6} {wr:>7.1f}% "
            f"₹{ap:>8.2f} ₹{tp:>10.2f}  {mult:.1f}x"
        )

    print("=" * 70)
    fav  = data.get("favorites", [])
    star = data.get("stars",     [])
    leg  = data.get("legends",   [])
    print(f"  👑 Legends  ({len(leg)}): {', '.join(leg)  or 'None'}")
    print(f"  🌟 Stars    ({len(star)}): {', '.join(star) or 'None'}")
    print(f"  ⭐ Favorites({len(fav)}): {', '.join(fav)  or 'None'}")
    print("=" * 70)
