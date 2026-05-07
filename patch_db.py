from db_state import load_state, save_state
from auto_trade_engine import FIXED_SL_PCT, TAKE_PROFIT_PCT
state = load_state() or {}
positions = state.get('positions', {})
for sym, pos in positions.items():
    bp = pos['buy_price']
    pos['tp_price'] = round(bp * (1 + TAKE_PROFIT_PCT), 2)
    pos['sl_price'] = round(bp * (1 - FIXED_SL_PCT), 2)
    print(sym, 'sl=', pos['sl_price'], 'tp=', pos['tp_price'])
state['positions'] = positions
save_state(state)
print('DB patched')
