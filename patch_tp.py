from auto_trade_engine import load_open_positions, save_open_positions, FIXED_SL_PCT, TAKE_PROFIT_PCT
positions = load_open_positions()
for sym, pos in positions.items():
    bp = pos['buy_price']
    pos['tp_price'] = round(bp * (1 + TAKE_PROFIT_PCT), 2)
    pos['sl_price'] = round(bp * (1 - FIXED_SL_PCT), 2)
    print(sym, 'sl=', pos['sl_price'], 'tp=', pos['tp_price'])
save_open_positions(positions)
print('Done')
