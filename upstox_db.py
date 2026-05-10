# upstox_db.py — Neon DB persistence for Upstox positions + token
# Drop into: C:\Users\JKRAOWIN\rsi_bot_v2\rsi_bot_v2\
# Works alongside your existing db_state.py (reuses get_conn)

from db_state import get_conn
from datetime import datetime
import json


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — TABLE INIT  (call once from main.py or db_state.init_db)
# ═════════════════════════════════════════════════════════════════════════════

def init_upstox_tables():
    """
    Creates 2 tables in your Neon DB:
      upstox_token     — stores the daily access token
      upstox_positions — stores synced Upstox portfolio positions
    Safe to call on every startup (IF NOT EXISTS).
    """
    conn = get_conn()
    cur  = conn.cursor()

    # ── Token table ───────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS upstox_token (
            id           SERIAL PRIMARY KEY,
            access_token TEXT        NOT NULL,
            fetched_at   TIMESTAMP   DEFAULT NOW(),
            expires_at   TIMESTAMP,
            is_valid     BOOLEAN     DEFAULT TRUE
        )
    """)

    # ── Positions table ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS upstox_positions (
            id          SERIAL PRIMARY KEY,
            symbol      TEXT        NOT NULL,
            itype       TEXT        DEFAULT 'STOCK',
            qty         INTEGER     DEFAULT 0,
            buy_price   REAL        DEFAULT 0,
            ltp         REAL        DEFAULT 0,
            pnl         REAL        DEFAULT 0,
            pnl_pct     REAL        DEFAULT 0,
            sl_price    REAL        DEFAULT 0,
            tp_price    REAL        DEFAULT 0,
            tsl_active  BOOLEAN     DEFAULT FALSE,
            synced_at   TIMESTAMP   DEFAULT NOW(),
            is_open     BOOLEAN     DEFAULT TRUE
        )
    """)

    # ── Add missing columns if upgrading from older schema ────────────────────
    for col, defn in [
        ("tsl_active", "BOOLEAN DEFAULT FALSE"),
        ("tp_price",   "REAL DEFAULT 0"),
        ("is_open",    "BOOLEAN DEFAULT TRUE"),
        ("itype",      "TEXT DEFAULT 'STOCK'"),
    ]:
        try:
            cur.execute(f"ALTER TABLE upstox_positions ADD COLUMN IF NOT EXISTS {col} {defn}")
        except Exception:
            pass

    conn.commit()
    cur.close()
    conn.close()
    print("[UpstoxDB] Tables ready: upstox_token, upstox_positions")


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — TOKEN PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════

def save_token(access_token: str, expires_at=None):
    """
    Save a new Upstox access token to DB.
    Marks all previous tokens invalid first.
    expires_at: datetime object or None (defaults to same-day 18:30 IST).
    """
    if expires_at is None:
        # Upstox tokens expire at 06:00 UTC = 11:30 IST next day
        # Conservatively treat as same-day 18:00 IST
        from datetime import date
        today = date.today()
        expires_at = datetime(today.year, today.month, today.day, 18, 0, 0)

    conn = get_conn()
    cur  = conn.cursor()

    # Invalidate old tokens
    cur.execute("UPDATE upstox_token SET is_valid = FALSE")

    # Insert new token
    cur.execute("""
        INSERT INTO upstox_token (access_token, fetched_at, expires_at, is_valid)
        VALUES (%s, NOW(), %s, TRUE)
    """, (access_token, expires_at))

    conn.commit()
    cur.close()
    conn.close()
    print(f"[UpstoxDB] Token saved. Expires: {expires_at.strftime('%d-%b-%Y %H:%M')}")


def load_token() -> str | None:
    """
    Load the latest valid Upstox token from DB.
    Returns None if no valid token found.
    """
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT access_token FROM upstox_token
            WHERE is_valid = TRUE
            ORDER BY fetched_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"[UpstoxDB] load_token error: {e}")
        return None


def invalidate_token():
    """Mark all tokens invalid (e.g. on 401 from Upstox API)."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("UPDATE upstox_token SET is_valid = FALSE")
        conn.commit()
        cur.close()
        conn.close()
        print("[UpstoxDB] All tokens invalidated")
    except Exception as e:
        print(f"[UpstoxDB] invalidate_token error: {e}")


def get_token_status() -> dict:
    """Return token status info for dashboard/API."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT access_token, fetched_at, expires_at, is_valid
            FROM upstox_token
            ORDER BY fetched_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"has_token": False, "is_valid": False}
        token, fetched, expires, valid = row
        return {
            "has_token" : True,
            "is_valid"  : valid,
            "fetched_at": fetched.strftime("%d-%b-%Y %H:%M") if fetched else None,
            "expires_at": expires.strftime("%d-%b-%Y %H:%M") if expires else None,
            "token_preview": token[:20] + "..." if token else None,
        }
    except Exception as e:
        print(f"[UpstoxDB] get_token_status error: {e}")
        return {"has_token": False, "is_valid": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — POSITION PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════

def sync_positions_to_db(positions: list):
    """
    Full sync: replaces all open positions in DB with the latest list.
    positions: list of dicts from /api/auto/portfolio or upstox_integration.sync_to_bot()

    Each dict should have: symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
                           sl_price, tp_price, tsl_active
    """
    if not positions:
        print("[UpstoxDB] No positions to sync")
        return

    conn = get_conn()
    cur  = conn.cursor()

    # Mark all existing positions as closed (will re-insert open ones)
    cur.execute("UPDATE upstox_positions SET is_open = FALSE WHERE source = 'upstox' OR source IS NULL")

    now = datetime.now()
    for pos in positions:
        symbol     = pos.get("symbol", "")
        itype      = pos.get("itype", "STOCK")
        qty        = int(pos.get("qty", 0))
        buy_price  = float(pos.get("buy_price", 0))
        ltp        = float(pos.get("ltp", 0))
        pnl        = float(pos.get("pnl", 0))
        pnl_pct    = float(pos.get("pnl_pct", 0))
        sl_price   = float(pos.get("sl_price", 0))
        tp_price   = float(pos.get("tp_price", 0))
        tsl_active = bool(pos.get("tsl_active", False))

        if not symbol:
            continue

        # Upsert: update if exists (by symbol + is_open), else insert
        cur.execute("""
            INSERT INTO upstox_positions
                (symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
                 sl_price, tp_price, tsl_active, synced_at, is_open, broker, source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,'Upstox','upstox')
            ON CONFLICT DO NOTHING
        """, (symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
              sl_price, tp_price, tsl_active, now))

        # Also update any existing open row for this symbol

        # Also update any existing open row for this symbol
        cur.execute("""
            UPDATE upstox_positions
            SET itype      = %s,
                qty        = %s,
                buy_price  = %s,
                ltp        = %s,
                pnl        = %s,
                pnl_pct    = %s,
                sl_price   = %s,
                tp_price   = %s,
                tsl_active = %s,
                synced_at  = %s,
                is_open    = TRUE
            WHERE symbol = %s AND is_open = TRUE
        """, (itype, qty, buy_price, ltp, pnl, pnl_pct,
              sl_price, tp_price, tsl_active, now, symbol))

    conn.commit()
    cur.close()
    conn.close()
    syms = [p.get("symbol") for p in positions]
    print(f"[UpstoxDB] Synced {len(positions)} positions: {', '.join(syms)}")


def load_positions() -> list:
    """Load all currently open Upstox positions from Neon DB."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
                   sl_price, tp_price, tsl_active, synced_at,
                   COALESCE(broker,'Upstox') as broker,
                   COALESCE(source,'upstox') as source
            FROM upstox_positions
            WHERE is_open = TRUE
            ORDER BY synced_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "symbol"    : r[0],
            "itype"     : r[1],
            "qty"       : r[2],
            "buy_price" : r[3],
            "ltp"       : r[4],
            "pnl"       : r[5],
            "pnl_pct"   : r[6],
            "sl_price"  : r[7],
            "tp_price"  : r[8],
            "tsl_active": r[9],
            "synced_at" : r[10].strftime("%d-%b-%Y %H:%M") if r[10] else None,
            "broker": r[11],
            "source": r[12],
        } for r in rows]
    except Exception as e:
        print(f"[UpstoxDB] load_positions error: {e}")
        return []
          


def close_position(symbol: str):
    """Mark a position as closed (on SELL or SL hit)."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE upstox_positions SET is_open = FALSE
            WHERE symbol = %s AND is_open = TRUE
        """, (symbol,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[UpstoxDB] Position closed: {symbol}")
    except Exception as e:
        print(f"[UpstoxDB] close_position error: {e}")


def update_ltp(symbol: str, ltp: float, pnl: float, pnl_pct: float,
               tsl_active: bool = False):
    """
    Update live price + P&L for a position (call on each price tick).
    Does NOT touch buy_price or sl_price.
    """
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE upstox_positions
            SET ltp = %s, pnl = %s, pnl_pct = %s,
                tsl_active = %s, synced_at = NOW()
            WHERE symbol = %s AND is_open = TRUE
        """, (ltp, pnl, pnl_pct, tsl_active, symbol))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[UpstoxDB] update_ltp error ({symbol}): {e}")


def get_position_history() -> list:
    """Load all positions (open + closed) for the trade history view."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT symbol, itype, qty, buy_price, ltp, pnl, pnl_pct,
                   sl_price, tp_price, tsl_active, synced_at, is_open
            FROM upstox_positions
            ORDER BY synced_at DESC
            LIMIT 200
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "symbol"    : r[0],
            "itype"     : r[1],
            "qty"       : r[2],
            "buy_price" : r[3],
            "ltp"       : r[4],
            "pnl"       : r[5],
            "pnl_pct"   : r[6],
            "sl_price"  : r[7],
            "tp_price"  : r[8],
            "tsl_active": r[9],
            "synced_at" : r[10].strftime("%d-%b-%Y %H:%M") if r[10] else None,
            "is_open"   : r[11],
        } for r in rows]
    except Exception as e:
        print(f"[UpstoxDB] get_position_history error: {e}")
        return []
