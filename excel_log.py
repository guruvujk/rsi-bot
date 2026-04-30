import openpyxl, os
from datetime import datetime

EXCEL_FILE = "logs/trades.xlsx"

def log_trade(trade: dict):
    os.makedirs("logs", exist_ok=True)
    if os.path.exists(EXCEL_FILE):
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Trades"
        ws.append(["Date","Time","Symbol","Action","Price","Qty","RSI","P&L","Reason"])
    ws.append([
        datetime.now().strftime("%d-%b-%Y"),
        trade.get("time",""),
        trade.get("symbol",""),
        trade.get("action",""),
        trade.get("price",0),
        trade.get("qty",0),
        round(trade.get("rsi",0),1),
        trade.get("pnl",""),
        trade.get("reason",""),
    ])
    wb.save(EXCEL_FILE)