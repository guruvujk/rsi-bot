from db_state import load_state, save_state
state = load_state()
for sym, pos in state['positions'].items():
    buy = pos.get('buy_price', 0)
    peak = pos.get('peak_price', buy)
    pos['tsl_active'] = True
    pos['peak_price'] = peak
    pos['tsl_price'] = round(peak * 0.95, 2)
    pos['tsl_activates_at'] = round(buy * 1.10, 2)
    print(f"{sym}: tsl_price={pos['tsl_price']}, activates_at={pos['tsl_activates_at']}")
save_state(state)
print('TSL enabled.')
