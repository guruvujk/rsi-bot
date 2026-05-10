from upstox_db import load_positions

all_positions = load_positions()
REAL_BROKERS = ['kite', 'groww', 'upstox', 'zerodha', 'angel']

real_positions = []
for pos in all_positions:
    source = pos.get('source', '').lower()
    broker = pos.get('broker', '').lower()
    is_paper = pos.get('paper_mode', False)
    is_real_broker = (source in REAL_BROKERS or broker in REAL_BROKERS)
    is_not_paper = not is_paper and source not in ['paper', 'manual'] and broker not in ['paper', 'manual']
    print(f"{pos['symbol']} | broker={broker} | source={source} | paper={is_paper} | is_real={is_real_broker} | is_not_paper={is_not_paper} | PASS={is_real_broker and is_not_paper}")

print(f"\nTotal passing filter: {len(real_positions)}")
