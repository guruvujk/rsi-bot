# production_features.py — Add to auto_trade_engine.py

import time
import threading
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

# ── 1. Market Hours Guard ────────────────────────────────────
def is_market_open():
    now = datetime.now(IST)
    if now.weekday() > 4:
        return False
    open_time  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_time <= now <= close_time

def is_market_day():
    return datetime.now(IST).weekday() <= 4


# ── 2. Pre-Market Check ──────────────────────────────────────
def pre_market_check():
    from db_state import load_state
    from telegram_alerts import send_telegram as send_alert
    results = {}

    # DB check
    try:
        s = load_state()
        results['db'] = s is not None
    except:
        results['db'] = False

    # Token check
    try:
        from upstox_db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT token FROM upstox_token ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        results['token'] = row is not None and row[0] is not None
        conn.close()
    except:
        results['token'] = False

    # Capital check
    try:
        from db_state import load_state
        s = load_state()
        results['capital'] = s.get('capital', 0) > 10000
    except:
        results['capital'] = False

    # Internet check
    try:
        import requests
        requests.get('https://www.google.com', timeout=5)
        results['internet'] = True
    except:
        results['internet'] = False

    all_ok = all(results.values())
    status = '\n'.join([f"{'✅' if v else '❌'} {k}" for k,v in results.items()])

    if all_ok:
        send_alert(f"✅ Pre-Market Check PASSED\n{status}\nBot ready to trade.")
    else:
        send_alert(f"⚠️ Pre-Market Check FAILED\n{status}\nFix before market opens.")

    print(f"[Pre-Market]\n{status}")
    return all_ok


# ── 3. Circuit Breaker ───────────────────────────────────────
DAILY_LOSS_LIMIT_PCT = 0.02   # 2% of capital
_circuit_broken = False

def check_circuit_breaker():
    global _circuit_broken
    if _circuit_broken:
        return True
    try:
        from db_state import load_state
        from telegram_alerts import send_telegram as send_alert
        s = load_state()
        capital = s.get('capital', 100000)
        trades = s.get('trades', [])

        today = datetime.now(IST).strftime('%d-%b-%Y')
        todays_pnl = sum(
            t.get('pnl', 0) or 0
            for t in trades
            if t.get('date') == today and t.get('action') == 'SELL'
        )

        limit = capital * DAILY_LOSS_LIMIT_PCT
        if todays_pnl < -limit:
            _circuit_broken = True
            send_alert(
                f"🔴 CIRCUIT BREAKER TRIGGERED\n"
                f"Daily Loss: ₹{abs(todays_pnl):,.2f}\n"
                f"Limit: ₹{limit:,.2f}\n"
                f"Trading STOPPED for today."
            )
            print(f"[Circuit Breaker] TRIGGERED — daily loss ₹{abs(todays_pnl):,.2f}")
            return True
    except Exception as e:
        print(f"[Circuit Breaker] Error: {e}")
    return False

def reset_circuit_breaker():
    global _circuit_broken
    _circuit_broken = False
    print("[Circuit Breaker] Reset for new day")


# ── 4. Duplicate Order Prevention ───────────────────────────
_pending_orders = set()

def is_order_pending(symbol):
    return symbol in _pending_orders

def mark_order_pending(symbol):
    _pending_orders.add(symbol)

def clear_order_pending(symbol):
    _pending_orders.discard(symbol)


# ── 5. Real Order Placement (Upstox) ────────────────────────
def place_real_order(symbol, qty, transaction_type='BUY'):
    try:
        from upstox_integration import load_token
        import requests

        token = load_token()
        if not token:
            print(f"[Order] No Upstox token — paper trade only")
            return None

        # Strip .NS suffix for Upstox
        clean_sym = symbol.replace('.NS', '')

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            "quantity": qty,
            "product": "D",              # Delivery
            "validity": "DAY",
            "price": 0,
            "tag": "RSI_BOT",
            "instrument_token": f"NSE_EQ|INE{clean_sym}",
            "order_type": "MARKET",
            "transaction_type": transaction_type,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False
        }
        r = requests.post(
            'https://api.upstox.com/v2/order/place',
            headers=headers,
            json=payload,
            timeout=10
        )
        data = r.json()
        if data.get('status') == 'success':
            order_id = data['data']['order_id']
            print(f"[Order] {transaction_type} {symbol} qty={qty} → order_id={order_id}")
            return order_id
        else:
            print(f"[Order] FAILED: {data}")
            return None
    except Exception as e:
        print(f"[Order] Error: {e}")
        return None


# ── 6. Order Status Verification ────────────────────────────
def verify_order(order_id, retries=5):
    try:
        from upstox_integration import load_token
        import requests

        token = load_token()
        if not token or not order_id:
            return False

        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

        for attempt in range(retries):
            r = requests.get(
                f'https://api.upstox.com/v2/order/details?order_id={order_id}',
                headers=headers,
                timeout=10
            )
            data = r.json()
            status = data.get('data', {}).get('status', '')
            print(f"[Order] {order_id} status={status} (attempt {attempt+1})")

            if status == 'complete':
                return True
            elif status in ['rejected', 'cancelled']:
                print(f"[Order] REJECTED/CANCELLED: {order_id}")
                return False

            time.sleep(2)  # wait and retry

        return False
    except Exception as e:
        print(f"[Verify] Error: {e}")
        return False


# ── 7. GTT Order for SL/TP ──────────────────────────────────
def place_gtt(symbol, qty, sl_price, tp_price):
    try:
        from upstox_integration import load_token
        import requests

        token = load_token()
        if not token:
            return None

        clean_sym = symbol.replace('.NS', '')
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        # Place GTT stop loss order
        payload = {
            "type": "single",
            "quantity": qty,
            "product": "D",
            "instrument_token": f"NSE_EQ|INE{clean_sym}",
            "transaction_type": "SELL",
            "trigger_price": sl_price,
            "order_type": "LIMIT",
            "price": round(sl_price * 0.99, 2),  # 1% below trigger
        }
        r = requests.post(
            'https://api.upstox.com/v2/gtt/place',
            headers=headers,
            json=payload,
            timeout=10
        )
        data = r.json()
        if data.get('status') == 'success':
            gtt_id = data['data']['id']
            print(f"[GTT] Placed SL GTT for {symbol} @ ₹{sl_price} → id={gtt_id}")
            return gtt_id
        else:
            print(f"[GTT] Failed: {data}")
            return None
    except Exception as e:
        print(f"[GTT] Error: {e}")
        return None


# ── 8. Sync Real P&L from Upstox ────────────────────────────
def sync_real_pnl():
    try:
        from upstox_integration import load_token
        from upstox_db import get_conn
        import requests

        token = load_token()
        if not token:
            return

        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        r = requests.get(
            'https://api.upstox.com/v2/portfolio/short-term-positions',
            headers=headers,
            timeout=10
        )
        data = r.json()
        if data.get('status') != 'success':
            return

        conn = get_conn()
        cur = conn.cursor()

        for p in data.get('data', []):
            sym   = p.get('tradingsymbol', '') + '.NS'
            ltp   = p.get('last_price', 0)
            pnl   = p.get('pnl', 0)
            pnl_pct = p.get('day_change_percentage', 0)

            cur.execute("""
                UPDATE upstox_positions
                SET ltp=%s, pnl=%s, pnl_pct=%s, synced_at=%s
                WHERE symbol=%s AND broker='Upstox'
            """, (ltp, pnl, pnl_pct, datetime.now(), sym))
            print(f"[PnL Sync] {sym}: LTP={ltp} PnL={pnl}")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[PnL Sync] Error: {e}")


# ── 9. Auto Restart Wrapper ──────────────────────────────────
def run_with_auto_restart(func, name="Bot"):
    from telegram_alerts import send_telegram as send_alert
    while True:
        try:
            print(f"[{name}] Starting...")
            func()
        except KeyboardInterrupt:
            print(f"[{name}] Stopped by user")
            break
        except Exception as e:
            msg = f"[{name}] CRASHED: {e}\nRestarting in 60 seconds..."
            print(msg)
            try:
                send_alert(f"🔴 BOT CRASHED\n{e}\nAuto-restarting in 60s...")
            except:
                pass
            time.sleep(60)
            continue
