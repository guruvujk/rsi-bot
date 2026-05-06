content = open('dashboard.py', encoding='utf-8').read()

import_line = 'from flask import Flask, render_template_string, request, jsonify'
new_import = import_line + '\nfrom auto_trade_routes import auto_trade_bp'

socket_line = 'socketio = SocketIO(app, cors_allowed_origins="*")'
new_socket = socket_line + '\napp.register_blueprint(auto_trade_bp)'

positions_route = '\n@app.route("/api/positions")\ndef api_positions():\n    from dashboard import bot_state as s\n    raw = s.get("positions", {})\n    pos_list = []\n    if isinstance(raw, dict):\n        for sym, p in raw.items():\n            pos_list.append({"symbol": sym, "qty": p.get("qty",0), "buy_price": p.get("buy_price",0), "ltp": p.get("current_price", p.get("buy_price",0)), "pnl": p.get("pnl",0), "stop_loss": p.get("stop_loss",0)})\n    from flask import jsonify\n    return jsonify({"positions": pos_list, "count": len(pos_list)})\n'

if 'auto_trade_routes' not in content:
    content = content.replace(import_line, new_import)
    print('Blueprint import added')
else:
    print('Blueprint import already exists')

if 'register_blueprint' not in content:
    content = content.replace(socket_line, new_socket)
    print('Blueprint registered')
else:
    print('Blueprint already registered')

if '/api/positions' not in content:
    content = content.replace('@app.route("/portfolio")', positions_route + '@app.route("/portfolio")')
    print('/api/positions route added')
else:
    print('/api/positions already exists')

open('dashboard.py', 'w', encoding='utf-8').write(content)
print('Done')