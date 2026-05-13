# config.py — RSI Bot v3 (All Instruments Edition) — FIXED
# ═══════════════════════════════════════════════════════════
#
# FIXES v3:
#   1. STOP_LOSS_PCT reduced 0.04→0.02 (adaptive SL used in main.py)
#   2. TARGET_PCT reduced 0.04→0.03 (adaptive TP used in main.py)
#   3. MAX_POSITIONS reduced 8→5 (less exposure, safer)
#   4. MAX_CAPITAL_PER_TRADE raised ₹5000→₹15000 (2026-05-06)
DRAWDOWN_PCT = 0.10  # 10% floor = ₹90,000  # 5% — pause BUY if capital drops below this    
#   5. RISK_PER_TRADE reduced 0.05→0.03 (3% per trade safer)
#   6. RSI_BUY tightened 42→40 (2026-05-06)
#   7. RSI_SELL tightened 65→70 (stronger overbought signal required)
#   8. Removed XRP-USD and LINK-USD from CRYPTO (losing, 2026-05-06)

# ── Telegram ────────────────────────────────────────
TELEGRAM_TOKEN   = "8694229997:AAGfe1savDm39EsXsjuswJdGPbRD_ocGNaU"
TELEGRAM_CHAT_ID = "5782497984"

# ── Capital & Risk ───────────────────────────────────
CAPITAL               = 100_000    # ₹1,00,000 virtual capital
RISK_PER_TRADE        = 0.03       # FIX: 3% per trade (was 5% — too aggressive)
STOP_LOSS_PCT         = 0.02       # FIX: 2% base SL (adaptive SL overrides per type)
TARGET_PCT            = 0.03       # FIX: 3% base TP (adaptive TP overrides per type)
MIN_PRICE             = 1.0        # Skip instruments below ₹1
MAX_POSITIONS         = 5          # FIX: 5 max (was 8 — too many open at once)
MAX_SAME_SECTOR       = 2          # Max 2 per sector
MAX_CAPITAL_PER_TRADE = 15_000     # ✅ RAISED: ₹15,000 per position (was ₹5,000)

# ── Currency Settings ────────────────────────────────
BASE_CURRENCY = "INR"
USD_INR_RATE  = 85.5


def get_usd_inr_rate() -> float:
    """Return USD to INR rate — uses requests fallback, no yfinance."""
    try:
        import requests
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        return float(r.json()["rates"]["INR"])
    except Exception:
        return USD_INR_RATE  # fallback to 85.5   # fallback

# ── Persistence ──────────────────────────────────────
SAVE_POSITIONS       = True
POSITIONS_FILE       = "logs/positions.json"
LOAD_SAVED_POSITIONS = True    # FIX: enabled — crash recovery works now

# ── RSI Settings ────────────────────────────────────
RSI_PERIOD = 14
RSI_BUY    = 35   # ✅ UPDATED: was 42 → 40 (catches more oversold entries)
RSI_SELL   = 70    # FIX: tighter (was 65) — only strong overbought signals
VOICE_ALERTS = True

# ── Scan Intervals (seconds) ─────────────────────────
SCAN_INTERVAL           = 300   # 5 min default
SCAN_INTERVAL_STOCKS    = 300   # 5 min
SCAN_INTERVAL_CRYPTO    = 180   # 3 min (crypto moves fast)
SCAN_INTERVAL_FOREX     = 300   # 5 min
SCAN_INTERVAL_COMMODITY = 300   # 5 min

# ── Paper Trade ──────────────────────────────────────
PAPER_TRADE = True

# ════════════════════════════════════════════════════
# SECTOR MAP
# ════════════════════════════════════════════════════
SECTOR_MAP = {
    # NSE Stocks
    "HDFCBANK.NS"  : "BANKING",
    "ICICIBANK.NS" : "BANKING",
    "SBIN.NS"      : "BANKING",
    "BAJFINANCE.NS": "BANKING",
    "TCS.NS"       : "IT",
    "INFY.NS"      : "IT",
    "WIPRO.NS"     : "IT",
    "RELIANCE.NS"  : "ENERGY",
    "NTPC.NS"      : "ENERGY",
    "ONGC.NS"      : "ENERGY",
    "HINDUNILVR.NS": "FMCG",
    "ITC.NS"       : "FMCG",
    "MARUTI.NS"    : "AUTO",
    "BAJAJ-AUTO.NS": "AUTO",
    "SUNPHARMA.NS" : "PHARMA",
    "CIPLA.NS"     : "PHARMA",
    "TATASTEEL.NS" : "METALS",
    "LT.NS"        : "INFRA",
    "BHARTIARTL.NS": "TELECOM",

    # NSE Indices
    "^NSEI"        : "INDEX_NIFTY50",
    "^NSEBANK"     : "INDEX_BANK",
    "^CNXIT"       : "INDEX_IT",
    "^CNXPHARMA"   : "INDEX_PHARMA",
    "^CNXAUTO"     : "INDEX_AUTO",
    "^CNXFMCG"     : "INDEX_FMCG",
    "^CNXMETAL"    : "INDEX_METAL",
    "^CNXENERGY"   : "INDEX_ENERGY",
    "^CNXREALTY"   : "INDEX_REALTY",

    # ETFs
    "NIFTYBEES.NS" : "ETF_NIFTY",
    "BANKBEES.NS"  : "ETF_BANK",
    "GOLDBEES.NS"  : "ETF_GOLD",
    "JUNIORBEES.NS": "ETF_JUNIOR",
    "ITBEES.NS"    : "ETF_IT",
    "PHARMABEES.NS": "ETF_PHARMA",
    "LIQUIDBEES.NS": "ETF_LIQUID",

    # Commodities
    "GC=F"         : "PRECIOUS_METALS",
    "SI=F"         : "PRECIOUS_METALS",
    "PL=F"         : "PRECIOUS_METALS",
    "PA=F"         : "PRECIOUS_METALS",
    "CL=F"         : "ENERGY_COMMODITY",
    "BZ=F"         : "ENERGY_COMMODITY",
    "NG=F"         : "ENERGY_COMMODITY",
    "RB=F"         : "ENERGY_COMMODITY",
    "ZW=F"         : "AGRICULTURE",
    "ZC=F"         : "AGRICULTURE",
    "ZS=F"         : "AGRICULTURE",
    "KC=F"         : "AGRICULTURE",
    "CT=F"         : "AGRICULTURE",
    "SB=F"         : "AGRICULTURE",
    "HG=F"         : "BASE_METALS",
    "ALI=F"        : "BASE_METALS",

    # Forex
    "USDINR=X"     : "FOREX_INR",
    "EURINR=X"     : "FOREX_INR",
    "GBPINR=X"     : "FOREX_INR",
    "JPYINR=X"     : "FOREX_INR",
    "EURUSD=X"     : "FOREX_MAJOR",
    "GBPUSD=X"     : "FOREX_MAJOR",
    "USDJPY=X"     : "FOREX_MAJOR",
    "USDCHF=X"     : "FOREX_MAJOR",
    "AUDUSD=X"     : "FOREX_MAJOR",
    "USDCAD=X"     : "FOREX_MAJOR",
    "NZDUSD=X"     : "FOREX_MAJOR",
    "EURGBP=X"     : "FOREX_CROSS",
    "EURJPY=X"     : "FOREX_CROSS",
    "GBPJPY=X"     : "FOREX_CROSS",
    "USDSGD=X"     : "FOREX_EXOTIC",
    "USDHKD=X"     : "FOREX_EXOTIC",
    "USDCNY=X"     : "FOREX_EXOTIC",

    # Crypto
    "BTC-USD"      : "CRYPTO_MAJOR",
    "ETH-USD"      : "CRYPTO_MAJOR",
    "BNB-USD"      : "CRYPTO_MAJOR",
    "SOL-USD"      : "CRYPTO_MAJOR",
    "ADA-USD"      : "CRYPTO_MAJOR",
    "AVAX-USD"     : "CRYPTO_MAJOR",
    "DOGE-USD"     : "CRYPTO_MAJOR",
    "DOT-USD"      : "CRYPTO_MAJOR",
    "AAVE-USD"     : "CRYPTO_DEFI",
    "CRV-USD"      : "CRYPTO_DEFI",
    "OP-USD"       : "CRYPTO_L2",
    "BTC-INR"      : "CRYPTO_INR",
    "ETH-INR"      : "CRYPTO_INR",

    # US Stocks
    "AAPL"         : "US_TECH",
    "MSFT"         : "US_TECH",
    "GOOGL"        : "US_TECH",
    "AMZN"         : "US_TECH",
    "META"         : "US_TECH",
    "NVDA"         : "US_TECH",
    "TSLA"         : "US_TECH",
    "NFLX"         : "US_TECH",
    "JPM"          : "US_FINANCE",
    "BAC"          : "US_FINANCE",
    "GS"           : "US_FINANCE",
    "V"            : "US_FINANCE",
    "MA"           : "US_FINANCE",
    "JNJ"          : "US_HEALTHCARE",
    "PFE"          : "US_HEALTHCARE",
    "UNH"          : "US_HEALTHCARE",
    "WMT"          : "US_CONSUMER",
    "KO"           : "US_CONSUMER",
    "MCD"          : "US_CONSUMER",
    "XOM"          : "US_ENERGY",
    "CVX"          : "US_ENERGY",
    "SPY"          : "US_ETF",
    "QQQ"          : "US_ETF",
    "GLD"          : "US_ETF",
}

# ════════════════════════════════════════════════════
# SECTOR FILTER
# ════════════════════════════════════════════════════
def can_enter_trade(symbol: str, open_positions: dict) -> tuple:
    sector = get_sector(symbol)
    same_sector_count = sum(
        1 for s in open_positions
        if get_sector(s) == sector
    )
    if same_sector_count >= MAX_SAME_SECTOR:
        blocking = [s.replace(".NS","") for s in open_positions
                    if get_sector(s) == sector]
        return False, (
            f"Sector limit ({MAX_SAME_SECTOR}) reached for "
            f"[{sector}] — already holding {blocking}"
        )
    return True, ""


def get_sector(symbol: str) -> str:
    if symbol in SECTOR_MAP:
        return SECTOR_MAP[symbol]
    if symbol.endswith(".NS"): return "STOCK_OTHER"
    if symbol.endswith("=F"): return "COMMODITY_OTHER"
    if symbol.endswith("=X"): return "FOREX_OTHER"
    if "-USD" in symbol:      return "CRYPTO_OTHER"
    if "-INR" in symbol:      return "CRYPTO_INR"
    return "OTHER"


# ════════════════════════════════════════════════════
# INSTRUMENT GROUPS
# ════════════════════════════════════════════════════
STOCKS = {
    "enabled": True,
    "symbols": [
        "HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","BAJFINANCE.NS",
        "TCS.NS","INFY.NS","WIPRO.NS",
        "RELIANCE.NS","NTPC.NS","ONGC.NS",
        "HINDUNILVR.NS","ITC.NS",
        "MARUTI.NS","BAJAJ-AUTO.NS",
        "SUNPHARMA.NS","CIPLA.NS",
        "TATASTEEL.NS","LT.NS",
        "BHARTIARTL.NS",
    ]
}

INDICES = {
    "enabled": False,
    "symbols": [
        "^NSEI","^NSEBANK","^CNXIT","^CNXPHARMA","^CNXAUTO",
        "^CNXFMCG","^CNXMETAL","^CNXENERGY","^CNXREALTY",
    ]
}

ETFS = {
    "enabled": False,
    "symbols": [
        "NIFTYBEES.NS","BANKBEES.NS","GOLDBEES.NS",
        "JUNIORBEES.NS","ITBEES.NS","PHARMABEES.NS","LIQUIDBEES.NS",
    ]
}

COMMODITIES = {
    "enabled": False,
    "symbols": [
        "GC=F","SI=F","PL=F","PA=F",
        "CL=F","BZ=F","NG=F","RB=F",
        "ZW=F","ZC=F","ZS=F","KC=F",
        "CT=F","SB=F",
        "HG=F","ALI=F",
    ]
}

FOREX = {
    "enabled": False,
    "symbols": [
        "USDINR=X","EURINR=X","GBPINR=X","JPYINR=X",
        "EURUSD=X","GBPUSD=X","USDJPY=X","USDCHF=X",
        "AUDUSD=X","USDCAD=X","NZDUSD=X",
        "EURGBP=X","EURJPY=X","GBPJPY=X",
        "USDSGD=X","USDHKD=X","USDCNY=X",
    ]
}

CRYPTO = {
    "enabled": False,
    "symbols": [
        # ✅ REMOVED: XRP-USD and LINK-USD (consistent losers)
        "BTC-USD","ETH-USD","BNB-USD","SOL-USD",
        "ADA-USD","AVAX-USD","DOGE-USD","DOT-USD",
        "AAVE-USD","CRV-USD",
        "OP-USD",
    ]
}

US_STOCKS = {
    "enabled": True,
    "symbols": [
        "AAPL",
        "MSFT",
    ]
}

# ── Master watchlist ─────────────────────────────────
def build_watchlist():
    wl = []
    for group in [STOCKS, INDICES, ETFS, COMMODITIES, FOREX, CRYPTO, US_STOCKS]:
        if group["enabled"]:
            wl.extend(group["symbols"])
    return wl

WATCHLIST = build_watchlist()

# ── Instrument type classifier ───────────────────────
def get_instrument_type(symbol: str) -> str:
    if symbol in STOCKS["symbols"]:      return "STOCK"
    if symbol in INDICES["symbols"]:     return "INDEX"
    if symbol in ETFS["symbols"]:        return "ETF"
    if symbol in COMMODITIES["symbols"]: return "COMMODITY"
    if symbol in FOREX["symbols"]:       return "FOREX"
    if symbol in CRYPTO["symbols"]:      return "CRYPTO"
    if symbol in US_STOCKS["symbols"]:   return "US_STOCK"
    if symbol.endswith(".NS"):           return "STOCK"
    if symbol.endswith("=F"):            return "COMMODITY"
    if symbol.endswith("=X"):            return "FOREX"
    if "-USD" in symbol or "-INR" in symbol: return "CRYPTO"
    return "STOCK"

# ════════════════════════════════════════════════════
# WATCHLIST SUMMARY
# Total: ~105 instruments (XRP-USD, LINK-USD removed from CRYPTO)
# ════════════════════════════════════════════════════
