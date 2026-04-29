# rsi_engine.py — Fetch OHLCV + compute RSI/MACD/BB signals
# FIXES:
#   1. fetch_ohlcv returns None (not empty DataFrame) on failure
#      so callers can do: if df is None → skip cleanly
#   2. Delisted/bad symbols caught silently — no crash
#   3. nan guard on RSI + price before returning signal
#   4. MultiIndex column fix for newer yfinance versions

import pandas as pd
import yfinance as yf
from config import RSI_PERIOD, RSI_BUY, RSI_SELL


def fetch_ohlcv(symbol: str, period: str = "5d",
                interval: str = "5m") -> pd.DataFrame | None:
    """
    Fetch OHLCV data from Yahoo Finance.
    Returns DataFrame on success, None on failure/empty/delisted.
    """
    try:
        df = yf.download(
            symbol, period=period, interval=interval,
            progress=False, auto_adjust=True, threads=False
        )
        # Empty or no data (delisted, bad symbol, network error)
        if df is None or df.empty:
            return None

        # Fix MultiIndex columns from newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.dropna(inplace=True)

        # Still not enough rows after dropping NaN
        if len(df) < 15:
            return None

        return df

    except Exception as e:
        # Silent fail — main.py will skip this symbol
        print(f"  [fetch] {symbol}: {e}")
        return None


def compute_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Compute RSI using Wilder's smoothing (EWM)."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-9)   # avoid div/0
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series, fast: int = 12,
                 slow: int = 26, signal: int = 9) -> tuple:
    """Compute MACD line, signal line, histogram."""
    ema_fast    = series.ewm(span=fast,   adjust=False).mean()
    ema_slow    = series.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(series: pd.Series, period: int = 20,
                      std_dev: float = 2) -> tuple:
    """Compute Bollinger Bands + %B."""
    sma   = series.rolling(window=period).mean()
    std   = series.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    band_width = (upper - lower).replace(0, 1e-9)
    pct_b = (series - lower) / band_width * 100
    return upper, sma, lower, pct_b


def _safe_float(val, default: float = 0.0) -> float:
    """Convert to float safely — return default on nan/inf/error."""
    try:
        f = float(val)
        if f != f or f == float('inf') or f == float('-inf'):
            return default
        return f
    except Exception:
        return default


def get_signal(df: pd.DataFrame) -> tuple:
    """
    Compute RSI + MACD + Bollinger Band signals.

    Returns:
        (signal, rsi_value, price, indicators_dict)
        signal ∈ {"BUY", "SELL", "HOLD"}
    """
    # Normalise MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close'].squeeze()

    # Need at least 30 bars for meaningful indicators
    if len(close) < 30:
        price = _safe_float(close.iloc[-1])
        return "HOLD", 50.0, price, {}

    # ── RSI ──────────────────────────────────────────────────────────────────
    rsi     = compute_rsi(close)
    rsi_val = _safe_float(rsi.iloc[-1], default=50.0)

    # ── MACD ─────────────────────────────────────────────────────────────────
    macd, sig, hist = compute_macd(close)
    macd_val  = _safe_float(macd.iloc[-1])
    macd_sig  = _safe_float(sig.iloc[-1])
    macd_bull = macd_val > macd_sig   # True = bullish momentum

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    upper, sma, lower, pct_b = compute_bollinger(close)
    bb_pct   = _safe_float(pct_b.iloc[-1])
    bb_upper = _safe_float(upper.iloc[-1])
    bb_lower = _safe_float(lower.iloc[-1])
    bb_sma   = _safe_float(sma.iloc[-1])

    price = _safe_float(close.iloc[-1])

    # Guard: if price is still 0 or RSI is still 50 default (bad data)
    if price <= 0:
        return "HOLD", rsi_val, 0.0, {}

    # ── Signal Logic ─────────────────────────────────────────────────────────
    # RSI is primary signal; MACD is confirmation
    if rsi_val < RSI_BUY and macd_bull:
        signal = "BUY"             # Strong: oversold + bullish momentum
    elif rsi_val < RSI_BUY:
        signal = "BUY"             # Oversold — buy even without MACD confirm
    elif rsi_val > RSI_SELL and not macd_bull:
        signal = "SELL"            # Strong: overbought + bearish momentum
    elif rsi_val > RSI_SELL:
        signal = "SELL"            # Overbought — sell even without MACD confirm
    else:
        signal = "HOLD"

    indicators = {
        "rsi"      : round(rsi_val, 2),
        "macd"     : round(macd_val, 4),
        "macd_sig" : round(macd_sig, 4),
        "macd_bull": macd_bull,
        "bb_upper" : round(bb_upper, 4),
        "bb_sma"   : round(bb_sma, 4),
        "bb_lower" : round(bb_lower, 4),
        "bb_pct"   : round(bb_pct, 2),
    }

    return signal, round(rsi_val, 2), round(price, 4), indicators