from db_state import load_state, save_state
s = load_state()
for sym in ['SBIN.NS', 'BHARTIARTL.NS']:
    if sym in s['positions']:
        del s['positions'][sym]
        print(f'Removed: {sym}')
save_state(s)
print('Done. Positions:', list(s['positions'].keys()))