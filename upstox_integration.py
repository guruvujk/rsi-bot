import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()
from upstox_db import save_token, sync_positions_to_db, load_token as db_load_token

UPSTOX_API_KEY    = "936905f2-69df-464c-94d2-966b9997adbb"
UPSTOX_API_SECRET = "n4u02df4xg"
UPSTOX_REDIRECT   = "http://localhost:5000/upstox/callback"
UPSTOX_TOKEN_FILE = "logs/upstox_token.json"

def get_login_url():
    return (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code"
        f"&client_id={UPSTOX_API_KEY}"
        f"&redirect_uri={UPSTOX_REDIRECT}"
    )


def get_access_token(auth_code: str) -> str:
    url = "https://api.upstox.com/v2/login/authorization/token"
    data = {
        "code":          auth_code,
        "client_id":     UPSTOX_API_KEY,
        "client_secret": UPSTOX_API_SECRET,
        "redirect_uri":  UPSTOX_REDIRECT,
        "grant_type":    "authorization_code",
    }
    r = requests.post(url, data=data)
    if r.status_code == 200:
        token = r.json().get("access_token")
        os.makedirs("logs", exist_ok=True)
        with open(UPSTOX_TOKEN_FILE, "w") as f:
            json.dump({"access_token": token}, f)
        print(f"Upstox token saved")
        try:
            save_token(token)
            print("[Upstox] Token saved to Neon DB ✅")
        except Exception as e:
            print(f"[Upstox] DB token save failed: {e}")
        return token
    else:
        print(f"Token error: {r.text}")
        return None
        

def load_token() -> str:
    try:
        db_token = db_load_token()
        if db_token:
            return db_token
    except Exception as e:
        print(f"[Upstox] DB load failed, trying file: {e}")
    try:
        with open(UPSTOX_TOKEN_FILE) as f:
            return json.load(f).get("access_token")
    except:
        return None

def get_positions(token: str) -> list:
    url = "https://api.upstox.com/v2/portfolio/short-term-positions"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("data", [])
    print(f"Positions error: {r.text}")
    return []

def get_holdings(token: str) -> list:
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("data", [])
    print(f"Holdings error: {r.text}")
    return []


        
def sync_to_bot(token: str):
    from db_state import load_state, save_state
    positions = get_positions(token)
    holdings  = get_holdings(token)
    all_pos   = positions + holdings
    if not all_pos:
        print("No positions found in Upstox")
        return
    state = load_state() or {}
    bot_positions = state.get("positions", {})
    cleaned = []
    for p in all_pos:
        symbol    = p.get("tradingsymbol", "") + ".NS"
        qty       = p.get("quantity", 0)
        avg_price = p.get("average_price", 0)
        ltp       = p.get("last_price", avg_price)
        if qty <= 0:
            continue
        if symbol not in bot_positions:
            bot_positions[symbol] = {
                "symbol":     symbol,
                "qty":        qty,
                "buy_price":  avg_price,
                "sl_price":   round(avg_price * 0.95, 2),
                "tsl_active": False,
                "peak_price": ltp,
                "tsl_price":  None,
                "allocation": round(avg_price * qty, 2),
                "brokerage":  0,
                "entry_time": "Upstox Import",
                "itype":      "STOCK",
                "source":     "UPSTOX",
            }
            print(f"Imported {symbol} qty={qty} avg={avg_price}")
        else:
            print(f"Skipped {symbol} already in bot")
        cleaned.append({
            "symbol"    : symbol,
            "itype"     : "STOCK",
            "qty"       : qty,
            "buy_price" : avg_price,
            "ltp"       : ltp,
            "pnl"       : round((ltp - avg_price) * qty, 2),
            "pnl_pct"   : round((ltp - avg_price) / avg_price * 100, 2) if avg_price else 0,
            "sl_price"  : round(avg_price * 0.95, 2),
            "tp_price"  : 0,
            "tsl_active": False,
        })
    state["positions"] = bot_positions
    save_state(state)
    try:
        sync_positions_to_db(cleaned)
        print(f"[Upstox] {len(cleaned)} positions saved to Neon DB ✅")
    except Exception as e:
        print(f"[Upstox] DB position sync failed: {e}")
    print(f"Sync complete — {len(bot_positions)} positions in DB")

if __name__ == "__main__":
    print(f"Login URL:\n{get_login_url()}")
   

