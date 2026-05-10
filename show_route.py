with open('auto_trade_routes.py') as f:
    src = f.read()
idx = src.find('upstox_positions_from_db')
print(src[idx:idx+1200])
