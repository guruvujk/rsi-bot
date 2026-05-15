# upstox_orders.py — Upstox Live Order Placement
# Handles: place_order, verify_order, place_gtt (SL + Target)
# API: v2 for orders, v3 for GTT
# Endpoints:
#   Orders : https://api-hft.upstox.com/v2/order/place
#   GTT    : https://api.upstox.com/v3/order/gtt/place
#   Verify : https://api-hft.upstox.com/v2/order/details

import os
import time
import requests
from upstox_integration import load_token
from telegram_alerts import send_telegram

# ── Instrument Token Map ──────────────────────────────────
# Format: yfinance_symbol → Upstox instrument_key
INSTRUMENT_MAP = {
    # NSE Stocks
    "HDFCBANK.NS"   : "NSE_EQ|INE040A01034",
    "ICICIBANK.NS"  : "NSE_EQ|INE090A01021",
    "SBIN.NS"       : "NSE_EQ|INE062A01020",
    "BAJFINANCE.NS" : "NSE_EQ|INE296A01024",
    "TCS.NS"        : "NSE_EQ|INE467B01029",
    "INFY.NS"       : "NSE_EQ|INE009A01021",
    "WIPRO.NS"      : "NSE_EQ|INE075A01022",
    "RELIANCE.NS"   : "NSE_EQ|INE002A01018",
    "NTPC.NS"       : "NSE_EQ|INE733E01010",
    "ONGC.NS"       : "NSE_EQ|INE213A01029",
    "HINDUNILVR.NS" : "NSE_EQ|INE030A01027",
    "ITC.NS"        : "NSE_EQ|INE154A01025",
    "MARUTI.NS"     : "NSE_EQ|INE585B01010",
    "BAJAJ-AUTO.NS" : "NSE_EQ|INE917I01010",
    "SUNPHARMA.NS"  : "NSE_EQ|INE044A01036",
    "CIPLA.NS"      : "NSE_EQ|INE059A01026",
    "TATASTEEL.NS"  : "NSE_EQ|INE081A01020",
    "LT.NS"         : "NSE_EQ|INE018A01030",
    "BHARTIARTL.NS" : "NSE_EQ|INE397D01024",
    # US Stocks (NYSE/NASDAQ)
    "AAPL"          : "NSE_EQ|AAPL",   # not tradeable on Upstox — placeholder
    "MSFT"          : "NSE_EQ|MSFT",   # not tradeable on Upstox — placeholder
}

ORDER_URL  = "https://api-hft.upstox.com/v2/order/place"
GTT_URL    = "https://api.upstox.com/v3/order/gtt/place"
DETAIL_URL = "https://api-hft.upstox.com/v2/order/details"

# ── Duplicate order guard ─────────────────────────────────
_placed_orders = set()  # in-memory set of symbols with open orders

def is_order_already_placed(symbol: str) -> bool:
    return symbol in _placed_orders

def mark_order_placed(symbol: str):
    _placed_orders.add(symbol)

def mark_order_cleared(symbol: str):
    _placed_orders.discard(symbol)

# ── Helpers ───────────────────────────────────────────────
def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type" : "application/json",
        "Accept"       : "application/json",
    }

def get_instrument_key(symbol: str) -> str:
    key = INSTRUMENT_MAP.get(symbol)
    if not key:
        raise ValueError(f"No instrument key for {symbol}. Add to INSTRUMENT_MAP.")
    return key

# ── Place Order ───────────────────────────────────────────
def place_order(symbol: str, qty: int, order_type: str = "MARKET",
                price: float = 0, product: str = "CNC") -> dict:
    """
    Place a live order on Upstox.
    order_type: MARKET | LIMIT | SL | SL-M
    product   : CNC (delivery) | MIS (intraday) | MTF
    Returns   : {"success": bool, "order_id": str, "message": str}
    """
    if is_order_already_placed(symbol):
        return {"success": False, "message": f"Order already placed for {symbol}"}

    token = load_token()
    if not token:
        return {"success": False, "message": "No Upstox token — please login"}

    try:
        instrument_key = get_instrument_key(symbol)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    payload = {
        "quantity"          : qty,
        "product"           : product,
        "validity"          : "DAY",
        "price"             : price if order_type == "LIMIT" else 0,
        "instrument_token"  : instrument_key,
        "order_type"        : order_type,
        "transaction_type"  : "BUY",
        "disclosed_quantity": 0,
        "trigger_price"     : 0,
        "is_amo"            : False,
        "tag"               : "RSI_BOT",
    }

    try:
        r = requests.post(ORDER_URL, json=payload, headers=_headers(token), timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            order_id = data["data"]["order_id"]
            mark_order_placed(symbol)
            print(f"  ✅ ORDER PLACED {symbol} qty={qty} order_id={order_id}")
            send_telegram(f"✅ LIVE ORDER PLACED\n{symbol} | Qty: {qty} | Type: {order_type}", "INFO")
            return {"success": True, "order_id": order_id, "message": "Order placed"}
        else:
            msg = data.get("errors", [{}])[0].get("message", str(data))
            print(f"  ❌ ORDER FAILED {symbol}: {msg}")
            send_telegram(f"❌ ORDER FAILED\n{symbol} | {msg}", "INFO")
            return {"success": False, "message": msg}
    except Exception as e:
        print(f"  ❌ ORDER ERROR {symbol}: {e}")
        return {"success": False, "message": str(e)}


# ── Verify Order ──────────────────────────────────────────
def verify_order(order_id: str, retries: int = 5, delay: int = 2) -> dict:
    """
    Poll order status until filled or failed.
    Returns {"success": bool, "status": str, "filled_price": float}
    """
    token = load_token()
    if not token:
        return {"success": False, "status": "NO_TOKEN"}

    for attempt in range(retries):
        try:
            r = requests.get(
                f"{DETAIL_URL}?order_id={order_id}",
                headers=_headers(token),
                timeout=10
            )
            data = r.json()
            if r.status_code == 200:
                order = data.get("data", {})
                status = order.get("status", "").upper()
                filled = float(order.get("average_price", 0))
                print(f"  [Verify] {order_id} → {status} @ ₹{filled}")
                if status in ["COMPLETE", "FILLED"]:
                    return {"success": True,  "status": status, "filled_price": filled}
                if status in ["REJECTED", "CANCELLED"]:
                    return {"success": False, "status": status, "filled_price": 0}
        except Exception as e:
            print(f"  [Verify] Error: {e}")
        time.sleep(delay)

    return {"success": False, "status": "TIMEOUT", "filled_price": 0}


# ── Place GTT (SL + Target) ───────────────────────────────
def place_gtt(symbol: str, qty: int, buy_price: float,
              sl_price: float, target_price: float,
              product: str = "CNC") -> dict:
    """
    Place a multi-leg GTT order with SL + Target after a BUY is filled.
    Uses Upstox v3 GTT API — MULTIPLE type with STOPLOSS + TARGET legs.
    Returns {"success": bool, "gtt_order_id": str}
    """
    token = load_token()
    if not token:
        return {"success": False, "message": "No Upstox token"}

    try:
        instrument_key = get_instrument_key(symbol)
    except ValueError as e:
        return {"success": False, "message": str(e)}

    payload = {
        "type"            : "MULTIPLE",
        "quantity"        : qty,
        "product"         : product,
        "instrument_token": instrument_key,
        "transaction_type": "SELL",
        "rules": [
            {
                "strategy"    : "STOPLOSS",
                "trigger_type": "BELOW",
                "trigger_price": round(sl_price, 2),
            },
            {
                "strategy"    : "TARGET",
                "trigger_type": "ABOVE",
                "trigger_price": round(target_price, 2),
            }
        ]
    }

    try:
        r = requests.post(GTT_URL, json=payload, headers=_headers(token), timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            gtt_id = data["data"]["gtt_order_id"]
            print(f"  ✅ GTT PLACED {symbol} SL={sl_price} TP={target_price} gtt={gtt_id}")
            send_telegram(
                f"✅ GTT ORDER SET\n{symbol}\nSL: ₹{sl_price}\nTarget: ₹{target_price}",
                "INFO"
            )
            return {"success": True, "gtt_order_id": gtt_id}
        else:
            msg = data.get("errors", [{}])[0].get("message", str(data))
            print(f"  ❌ GTT FAILED {symbol}: {msg}")
            return {"success": False, "message": msg}
    except Exception as e:
        print(f"  ❌ GTT ERROR {symbol}: {e}")
        return {"success": False, "message": str(e)}


# ── Full Live Trade Flow ──────────────────────────────────
def execute_live_trade(symbol: str, qty: int, price: float,
                       sl_price: float, target_price: float) -> dict:
    """
    Full flow: place order → verify fill → set GTT SL+Target
    """
    print(f"\n  🔴 LIVE TRADE: {symbol} qty={qty} price={price}")

    # Step 1 — Place market order
    order = place_order(symbol, qty, order_type="MARKET", product="CNC")
    if not order["success"]:
        return {"success": False, "step": "place_order", "message": order["message"]}

    # Step 2 — Verify fill
    filled = verify_order(order["order_id"])
    if not filled["success"]:
        return {"success": False, "step": "verify_order", "status": filled["status"]}

    filled_price = filled["filled_price"] or price

    # Step 3 — Place GTT SL + Target
    gtt = place_gtt(symbol, qty, filled_price, sl_price, target_price)
    if not gtt["success"]:
        send_telegram(f"⚠️ GTT FAILED for {symbol} — set manually!\nSL: ₹{sl_price} | TP: ₹{target_price}", "INFO")


    # Auto-save position to DB
    try:
        from db_state import get_conn as _gc
        _conn = _gc()
        _cur = _conn.cursor()
        _cur.execute(
            "INSERT INTO upstox_positions "
            "(symbol, itype, qty, buy_price, ltp, sl_price, tp_price, is_open, broker, source, paper_mode, synced_at) "
            "VALUES (%s,'STOCK',%s,%s,%s,%s,%s,TRUE,'Upstox','upstox',FALSE,NOW())",
            (symbol, qty, filled_price, filled_price, sl_price, target_price)
        )
        _conn.commit()
        _cur.close()
        print(f"  [DB] Position saved: {symbol} @ {filled_price}")
    except Exception as _e:
        print(f"  [DB] Save failed: {_e}")
    return {
        "success"     : True,
        "order_id"    : order["order_id"],
        "filled_price": filled_price,
        "gtt_order_id": gtt.get("gtt_order_id", "N/A"),
    }


# ── Quick test ────────────────────────────────────────────
if __name__ == "__main__":
    print("Upstox Orders Module loaded ✅")
    print(f"Instrument map: {len(INSTRUMENT_MAP)} symbols")
    print(f"Token: {load_token()[:10]}..." if load_token() else "No token")




# Alias for auto_trade_engine.py compatibility
execute_live_order = execute_live_trade

