from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base
from datetime import datetime

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)
    time = Column(String)
    symbol = Column(String, index=True)
    direction = Column(String)
    action = Column(String)
    price = Column(Float)
    qty = Column(Integer)
    investment = Column(Float)
    stop_loss = Column(Float)
    target = Column(Float)
    pnl = Column(Float, default=0)
    result = Column(String)
    rsi_value = Column(Float)
    reason = Column(String)
    instrument_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    qty = Column(Integer)
    buy_price = Column(Float)
    current_price = Column(Float, default=0)
    stop_loss = Column(Float)
    target = Column(Float)
    investment = Column(Float)
    unrealized_pnl = Column(Float, default=0)
    rsi_at_entry = Column(Float)
    entry_time = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    capital = Column(Float)
    portfolio_value = Column(Float)
    total_positions = Column(Integer)
    realized_pnl = Column(Float)
    unrealized_pnl = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)