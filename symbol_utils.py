# symbol_utils.py - Shared symbol cleaning utility

def clean_symbol(symbol):
    """
    Remove broker suffix from symbol for yfinance.
    
    Examples:
        'SUNPHARMA.NS_GROWW' -> 'SUNPHARMA.NS'
        'SUNPHARMA.NS_KITE' -> 'SUNPHARMA.NS'
        'SUNPHARMA.NS_UPSTOX' -> 'SUNPHARMA.NS'
        'AAPL_US_STOCK' -> 'AAPL'
        'ITC.NS' -> 'ITC.NS' (unchanged)
    """
    if not symbol:
        return symbol
    
    symbol = str(symbol)
    
    # Remove everything after first underscore (broker suffix)
    if '_' in symbol:
        symbol = symbol.split('_')[0]
    
    return symbol


def get_display_symbol(symbol, broker=None):
    """Get display symbol (with broker for UI if needed)"""
    if broker:
        return f"{clean_symbol(symbol)}_{broker}"
    return clean_symbol(symbol)