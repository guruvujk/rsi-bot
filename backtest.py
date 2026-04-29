# backtest.py — RSI Strategy Backtesting Engine
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import os
import warnings
import config

warnings.filterwarnings('ignore')

# ── Configuration ───────────────────────────────────
class BacktestConfig:
    """Backtest settings - mirrors config.py for consistency"""
    STARTING_CAPITAL = 100000
    RISK_PER_TRADE = config.RISK_PER_TRADE      # 5% from config
    STOP_LOSS_PCT = config.STOP_LOSS_PCT        # 2% from config
    TARGET_PCT = config.TARGET_PCT              # 4% from config
    MAX_POSITIONS = config.MAX_POSITIONS        # 5 from config
    RSI_PERIOD = config.RSI_PERIOD              # 14 from config
    RSI_BUY = config.RSI_BUY                    # 30 from config
    RSI_SELL = config.RSI_SELL                  # 70 from config
    
    # Backtest-specific
    START_DATE = "2024-01-01"
    END_DATE = datetime.now().strftime("%Y-%m-%d")
    INTERVAL = "1h"  # 1h, 4h, 1d
    SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]  # Test subset
    
    # Output
    SAVE_PLOTS = True
    SAVE_TRADES = True
    OUTPUT_DIR = "logs/backtests"

# ── RSI Calculator (Same as live bot) ───────────────
def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using same method as paper_trade.py"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 0.0001)
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ── Backtest Engine ─────────────────────────────────
class RSIBacktester:
    def __init__(self, config_class=BacktestConfig):
        self.cfg = config_class
        self.trades = []
        self.equity_curve = []
        self.stats = {}
        os.makedirs(self.cfg.OUTPUT_DIR, exist_ok=True)
    
    def fetch_data(self, symbol: str) -> pd.DataFrame:
        print(f"📥 Fetching {symbol} ({self.cfg.START_DATE} to {self.cfg.END_DATE})...")
        try:
            df = yf.download(
                symbol,
                start=self.cfg.START_DATE,
                end=self.cfg.END_DATE,
                interval=self.cfg.INTERVAL,
                progress=False
            )
            if df.empty or len(df) < self.cfg.RSI_PERIOD + 10:
                print(f"  ⚠️ Insufficient data for {symbol}")
                return None
            return df
        except Exception as e:
            print(f"  ❌ Error fetching {symbol}: {e}")
            return None
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['RSI'] = calculate_rsi(df['Close'], self.cfg.RSI_PERIOD)
        df['BUY_SIGNAL'] = df['RSI'] < self.cfg.RSI_BUY
        df['SELL_SIGNAL'] = df['RSI'] > self.cfg.RSI_SELL
        return df
    
    def simulate_trades(self, df: pd.DataFrame, symbol: str) -> list:
        trades = []
        capital = self.cfg.STARTING_CAPITAL
        positions = {}
        
        for idx, row in df.iterrows():
            current_price = row['Close']
            current_rsi = row['RSI']
            timestamp = idx
            
            # ── Check Exits First ───────────────────
            if symbol in positions:
                pos = positions[symbol]
                exit_reason = None
                pnl = 0
                
                if current_price <= pos['sl']:
                    exit_reason = 'Stop Loss'
                    pnl = (current_price - pos['entry']) * pos['qty']
                elif current_price >= pos['target']:
                    exit_reason = 'Target Hit'
                    pnl = (current_price - pos['entry']) * pos['qty']
                elif row['SELL_SIGNAL']:
                    exit_reason = 'RSI Exit'
                    pnl = (current_price - pos['entry']) * pos['qty']
                
                if exit_reason:
                    trades.append({
                        'symbol': symbol,
                        'entry_date': pos['entry_date'],
                        'exit_date': timestamp,
                        'entry_price': pos['entry'],
                        'exit_price': current_price,
                        'qty': pos['qty'],
                        'pnl': pnl,
                        'return_pct': (pnl / (pos['entry'] * pos['qty'])) * 100,
                        'exit_reason': exit_reason,
                        'entry_rsi': pos['entry_rsi'],
                        'exit_rsi': current_rsi
                    })
                    capital += current_price * pos['qty']
                    del positions[symbol]
                    continue
            
            # ── Check Entries ───────────────────────
            if row['BUY_SIGNAL'] and symbol not in positions:
                if len(positions) >= self.cfg.MAX_POSITIONS:
                    continue
                
                risk_amount = capital * self.cfg.RISK_PER_TRADE
                qty = int(risk_amount // current_price)
                if qty <= 0: continue
                
                sl_price = current_price * (1 - self.cfg.STOP_LOSS_PCT)
                target_price = current_price * (1 + self.cfg.TARGET_PCT)
                
                positions[symbol] = {
                    'entry': current_price, 'qty': qty,
                    'sl': sl_price, 'target': target_price,
                    'entry_date': timestamp, 'entry_rsi': current_rsi
                }
                capital -= current_price * qty
            
            # ── Track Equity ────────────────────────
            total_value = capital
            for sym, pos in positions.items():
                total_value += current_price * pos['qty']
            
            self.equity_curve.append({
                'timestamp': timestamp, 'capital': capital,
                'portfolio_value': total_value, 'open_positions': len(positions)
            })
        
        return trades
    
    def calculate_stats(self, trades: list) -> dict:
        if not trades: return {"error": "No trades executed"}
        df_trades = pd.DataFrame(trades)
        total_trades = len(df_trades)
        winning_trades = df_trades[df_trades['pnl'] > 0]
        losing_trades = df_trades[df_trades['pnl'] <= 0]
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        total_pnl = df_trades['pnl'].sum()
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
        profit_factor = abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
        
        starting_capital = self.cfg.STARTING_CAPITAL
        ending_capital = starting_capital + total_pnl
        total_return = (ending_capital - starting_capital) / starting_capital * 100
        
        equity_df = pd.DataFrame(self.equity_curve)
        max_drawdown = 0
        sharpe = 0
        if not equity_df.empty:
            equity_df['peak'] = equity_df['portfolio_value'].cummax()
            equity_df['drawdown'] = (equity_df['portfolio_value'] - equity_df['peak']) / equity_df['peak']
            max_drawdown = equity_df['drawdown'].min() * 100
            
            equity_df['returns'] = equity_df['portfolio_value'].pct_change()
            sharpe = (np.sqrt(252) * equity_df['returns'].mean() / equity_df['returns'].std()) if equity_df['returns'].std() > 0 else 0

        return {
            'total_trades': total_trades, 'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2), 'return_pct': round(total_return, 2),
            'max_drawdown_pct': round(max_drawdown, 2), 'sharpe_ratio': round(sharpe, 2),
            'ending_capital': round(ending_capital, 2)
        }

    def run(self, symbol: str = None) -> dict:
        symbols = [symbol] if symbol else self.cfg.SYMBOLS
        all_stats = {}
        
        print(f"\n🚀 Starting RSI Backtest")
        print(f"📅 Period: {self.cfg.START_DATE} to {self.cfg.END_DATE}")
        print(f"⏱️  Interval: {self.cfg.INTERVAL}")
        print(f"🎯 Strategy: RSI < {self.cfg.RSI_BUY} BUY | RSI > {self.cfg.RSI_SELL} SELL")
        print("=" * 70)
        
        for sym in symbols:
            print(f"\n🔍 Backtesting {sym}...")
            df = self.fetch_data(sym)
            if df is None: continue
            
            df = self.generate_signals(df)
            self.trades = []
            self.equity_curve = []
            
            trades = self.simulate_trades(df, sym)
            self.trades = trades
            stats = self.calculate_stats(trades)
            all_stats[sym] = stats
            
            print(f"   Trades: {stats['total_trades']}")
            print(f"   Win Rate: {stats['win_rate']}%")
            print(f"   Total P&L: ₹{stats['total_pnl']:,.2f}")
            print(f"   Return: {stats['return_pct']:.2f}%")
            
        return all_stats

# ── Command Line Interface ───────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RSI Strategy Backtester")
    parser.add_argument('--symbol', type=str, help='Single symbol to test (e.g., BTC-USD)')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--interval', type=str, choices=['1h','4h','1d'], help='Candle interval')
    args = parser.parse_args()
    
    if args.start: BacktestConfig.START_DATE = args.start
    if args.end: BacktestConfig.END_DATE = args.end
    if args.interval: BacktestConfig.INTERVAL = args.interval
    
    backtester = RSIBacktester()
    backtester.run(symbol=args.symbol)





