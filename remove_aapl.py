from db_state import load_state, save_state

state = load_state()
keys_to_remove = [k for k in state['positions'] if 'AAPL' in k]
for k in keys_to_remove:
    print(f'Removing: {k}')
    del state['positions'][k]
save_state(state)
print('Done.')
