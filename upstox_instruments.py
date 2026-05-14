# upstox_instruments.py — Symbol to Instrument Token mapper
# Downloads Upstox NSE JSON, builds symbol→token map for watchlist
# Usage:
#   from upstox_instruments import get_token
#   token = get_token("RELIANCE")  → "NSE_EQ|INE002A01018"

import os
import json
import gzip
import requests
from config import WATCHLIST

INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
CACHE_FILE      = "logs/upstox_instruments.json"

# Manual fallback map for your watchlist
MANUAL_TOKEN_MAP = {
    "HDFCBANK"   : "NSE_EQ|INE040A01034",
    "ICICIBANK"  : "NSE_EQ|INE090A01021",
    "SBIN"       : "NSE_EQ|INE062A01020",
    "BAJFINANCE" : "NSE_EQ|INE296A01024",
    "TCS"        : "NSE_EQ|INE467B01029",
    "INFY"       : "NSE_EQ|INE009A01021",
    "WIPRO"      : "NSE_EQ|INE075A01022",
    "RELIANCE"   : "NSE_EQ|INE002A01018",
    "NTPC"       : "NSE_EQ|INE733E01010",
    "ONGC"       : "NSE_EQ|INE213A01029",
    "HINDUNILVR" : "NSE_EQ|INE030A01027",
    "ITC"        : "NSE_EQ|INE154A01025",
    "MARUTI"     : "NSE_EQ|INE585B01010",
    "BAJAJ-AUTO" : "NSE_EQ|INE917I01010",
    "SUNPHARMA"  : "NSE_EQ|INE044A01036",
    "CIPLA"      : "NSE_EQ|INE059A01026",
    "TATASTEEL"  : "NSE_EQ|INE081A01020",
    "LT"         : "NSE_EQ|INE018A01030",
    "BHARTIARTL" : "NSE_EQ|INE397D01024",
}

_token_map = {}


def _load_from_cache() -> dict:
    """Load instrument map from local cache."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_to_cache(data: dict):
    """Save instrument map to local cache."""
    try:
        os.makedirs("logs", exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"  [Instruments] Cache save error: {e}")


def _download_instruments() -> dict:
    """Download and parse Upstox NSE instrument JSON."""
    try:
        print("  [Instruments] Downloading NSE instrument tokens...")
        r = requests.get(INSTRUMENTS_URL, timeout=30)
        if r.status_code != 200:
            print(f"  [Instruments] Download failed: {r.status_code}")
            return {}

        data     = json.loads(gzip.decompress(r.content))
        tok_map  = {}

        for item in data:
            if item.get("segment") != "NSE_EQ":
                continue
            if item.get("instrument_type") != "EQ":
                continue
            sym = item.get("trading_symbol", "").upper()
            key = item.get("instrument_key", "")
            if sym and key:
                tok_map[sym] = key

        print(f"  [Instruments] Loaded {len(tok_map)} NSE_EQ tokens")
        return tok_map

    except Exception as e:
        print(f"  [Instruments] Download error: {e}")
        return {}


def load_instruments(force_refresh: bool = False) -> dict:
    """Load instrument token map — from cache or download fresh."""
    global _token_map

    if _token_map and not force_refresh:
        return _token_map

    # Try cache first
    cached = _load_from_cache()
    if cached and not force_refresh:
        _token_map = cached
        return _token_map

    # Download fresh
    downloaded = _download_instruments()
    if downloaded:
        _save_to_cache(downloaded)
        _token_map = downloaded
    else:
        # Fall back to manual map
        print("  [Instruments] Using manual token map as fallback")
        _token_map = MANUAL_TOKEN_MAP

    return _token_map


def get_token(symbol: str) -> str | None:
    """
    Get Upstox instrument token for a symbol.
    symbol can be 'RELIANCE', 'RELIANCE.NS', or 'AAPL'
    Returns 'NSE_EQ|INE002A01018' or None if not found.
    """
    # Clean symbol
    clean = symbol.replace(".NS", "").replace(".BSE", "").upper()

    # US stocks not on NSE
    us_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"]
    if clean in us_stocks:
        return None  # Upstox doesn't support US stocks directly

    tokens = load_instruments()

    # Direct match
    if clean in tokens:
        return tokens[clean]

    # Manual fallback
    if clean in MANUAL_TOKEN_MAP:
        return MANUAL_TOKEN_MAP[clean]

    print(f"  [Instruments] Token not found for: {symbol}")
    return None


def print_watchlist_tokens():
    """Print instrument tokens for all watchlist symbols."""
    print("\n  Watchlist Instrument Tokens:")
    print("  " + "="*50)
    tokens = load_instruments()
    for sym in WATCHLIST:
        clean = sym.replace(".NS", "").upper()
        token = get_token(sym)
        status = "✅" if token else "❌"
        print(f"  {status} {clean:<20} {token or 'NOT FOUND'}")
    print("  " + "="*50)


if __name__ == "__main__":
    load_instruments(force_refresh=True)
    print_watchlist_tokens()
