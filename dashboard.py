from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO
import threading, time

app      = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

from auto_trade_routes import auto_trade_bp
app.register_blueprint(auto_trade_bp)

try:
    from db_state import load_state as _db_load, init_db as _init_db, load_trades as _db_load_trades
    _init_db()
    _saved = _db_load()
    if _saved:
        print(f"[Dashboard] Loaded from DB: capital={_saved.get('capital')}, positions={len(_saved.get('positions',{}))}, trades={len(_saved.get('trades',[]))}")
except Exception as _e:
    print(f"[Dashboard] DB load error: {_e}")
    _saved = None

bot_state = {
    "capital"      : _saved.get("capital", 315102.96) if _saved else 315102.96,
    "positions"    : _saved.get("positions", {}) if _saved else {},
    "trades"       : [],
    "pnl"          : _saved.get("pnl", 0.0) if _saved else 0.0,
    "open_pnl"     : _saved.get("open_pnl", 0.0) if _saved else 0.0,
    "realised_pnl" : _saved.get("realised_pnl", 0.0) if _saved else 0.0,
    "total_trades" : _saved.get("total_trades", 0) if _saved else 0,
    "wins"         : _saved.get("wins", 0) if _saved else 0,
    "losses"       : _saved.get("losses", 0) if _saved else 0,
    "win_rate"     : _saved.get("win_rate", 0) if _saved else 0,
    "return_pct"   : _saved.get("return_pct", 0) if _saved else 0,
    "watchlist"    : _saved.get("watchlist", {}) if _saved else {},
    "paper_mode"   : True,
}

@app.route('/api/trade', methods=['POST'])
def api_trade():
    data = request.get_json(silent=True) or {}
    return jsonify({"status": "ok", "received": data}), 200

@app.route('/api/position/update', methods=['POST'])
def api_position_update():
    try:
        data    = request.get_json(silent=True) or {}
        symbol  = data.get("symbol", "")
        price   = data.get("current_price", 0)
        if symbol and symbol in bot_state.get("positions", {}):
            bot_state["positions"][symbol]["current_price"] = float(price)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/state')
def api_state():
    from db_state import load_state as _db
    s = _db() or {}
    return jsonify({'capital': s.get('capital', 315102.96), 'positions': len(s.get('positions', {}))})

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
 <title>RSI Bot Dashboard</title>
 <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"></script>
 <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #f5f7fa; color: #1a1a2e; padding-bottom: 40px; }
    .header { background: #fff; padding: 14px 28px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
    .paper-badge { background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; border: 1px solid #bfdbfe; }
    .stats { display: grid; grid-template-columns: repeat(4,1fr); gap:14px; padding:20px 28px; }
    .stats2 { display: grid; grid-template-columns: repeat(4,1fr); gap:14px; padding:0 28px 20px; }
    .stat { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:16px 20px; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
    .stat2 { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 16px; display:flex; flex-direction:column; align-items:center; }
    .label { font-size:11px; color:#64748b; text-transform:uppercase; margin-bottom:6px; }
    .value { font-size:22px; font-weight:600; }
    .green{color:#16a34a} .red{color:#dc2626} .blue{color:#2563eb} .gray{color:#475569}
    .grid1 { display:grid; grid-template-columns:1fr; gap:14px; padding:0 28px 20px; }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:0 28px 20px; }
    .box { background:#fff; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }
    .box-title { padding:11px 16px; font-size:12px; font-weight:600; color:#64748b; border-bottom:1px solid #f1f5f9; background:#f8fafc; display:flex; justify-content:space-between; align-items:center; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th { padding:9px 16px; text-align:left; font-size:11px; color:#94a3b8; border-bottom:1px solid #f1f5f9; background:#f8fafc; }
    td { padding:9px 16px; border-bottom:1px solid #f8fafc; }
    .badge { padding:2px 10px; border-radius:20px; font-size:11px; font-weight:600; }
    .badge-buy { background:#dcfce7; color:#16a34a; }
    .badge-hold { background:#f1f5f9; color:#64748b; }
    .win-bar-wrap { width:100%; height:8px; background:#fee2e2; border-radius:4px; margin-top:6px; }
    .win-bar { height:100%; border-radius:4px; background:#16a34a; }
 </style>
</head>
<body>

<div class="header">
  <div style="display:flex;align-items:center;gap:12px;">
    <h1 style="font-size:18px;color:#2563eb;">📈 RSI Algo Bot</h1>
    <span class="paper-badge">📄 Paper Trade</span>
  </div>
  <div style="font-size:13px;color:#64748b;">Live &nbsp;|&nbsp; <span id="clock">--:--:--</span></div>
</div>

<div class="stats">
  <div class="stat"><div class="label">Available Capital</div><div class="value blue" id="capital">...</div></div>
  <div class="stat"><div class="label">Portfolio Value</div><div class="value" id="portfolio_val">...</div></div>
  <div class="stat"><div class="label">Realised P&L</div><div class="value green" id="pnl">₹0</div></div>
  <div class="stat"><div class="label">Unrealised P&L</div><div class="value gray" id="open_pnl">₹0</div></div>
</div>

<div class="stats2">
  <div class="stat2"><div class="label">Closed Trades</div><div class="value gray" id="total_trades">0</div></div>
  <div class="stat2"><div class="label">Win Rate</div><div class="value green" id="win_rate">0%</div><div class="win-bar-wrap"><div class="win-bar" id="win-bar" style="width:0%"></div></div></div>
  <div class="stat2"><div class="label">Wins / Losses</div><div class="value" id="wins_losses">0 / 0</div></div>
  <div class="stat2"><div class="label">Return</div><div class="value gray" id="return_pct">0%</div></div>
</div>

<div class="grid2">
  <div class="box">
    <div class="box-title">Watchlist — RSI Scanner <span id="wl-count"></span></div>
    <table><thead><tr><th>Symbol</th><th>Price</th><th>RSI</th><th>Signal</th></tr></thead><tbody id="watchlist-body"></tbody></table>
  </div>
  <div class="box">
    <div class="box-title">Open Positions <span id="pos-count"></span></div>
    <table><thead><tr><th>Symbol</th><th>Qty</th><th>Buy @</th><th>LTP</th><th>P&L</th><th>TSL</th><th>Broker</th><th></th></tr></thead><tbody id="positions-body"></tbody></table>
  </div>
</div>

<div class="grid1">
  <div class="box">
    <div class="box-title" style="background:#f0fdf4;color:#16a34a;">➕ Add Manual Position</div>
    <div style="padding:14px 16px;display:flex;gap:10px;align-items:flex-end;">
       <input id="m-symbol" placeholder="SYMBOL" style="padding:6px;width:120px;border:1px solid #e2e8f0;border-radius:4px;">
       <input id="m-qty" type="number" placeholder="Qty" style="padding:6px;width:60px;border:1px solid #e2e8f0;border-radius:4px;">
       <input id="m-price" type="number" placeholder="Price" style="padding:6px;width:100px;border:1px solid #e2e8f0;border-radius:4px;">
       <select id="m-broker" style="padding:6px;border:1px solid #e2e8f0;border-radius:4px;"><option>Kite</option><option>Groww</option><option>Upstox</option></select>
       <select id="m-itype" style="padding:6px;border:1px solid #e2e8f0;border-radius:4px;"><option value="STOCK">STOCK</option><option value="US_STOCK">US_STOCK</option></select>
       <button onclick="addManualPosition()" style="padding:7px 15px;background:#16a34a;color:#fff;border:none;border-radius:4px;cursor:pointer;">Add</button>
       <span id="m-msg" style="font-size:12px;"></span>
    </div>
  </div>
</div>

<div class="grid1">
  <div class="box">
    <div class="box-title" style="background:#eff6ff;color:#2563eb;">
      🔗 Upstox — Real Portfolio
      <div style="display:flex;gap:8px;align-items:center;">
        <span id="upstox-token-status" class="badge" style="background:#dcfce7;color:#16a34a;">Token OK</span>
        <button onclick="upstoxLogin()" style="padding:4px 10px;cursor:pointer;border:1px solid #bfdbfe;border-radius:4px;background:#fff;color:#2563eb;">🔑 Login</button>
        <button onclick="upstoxSync()" style="padding:4px 10px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">🔄 Sync</button>
      </div>
    </div>
    <table>
      <thead>
        <tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Buy @</th><th>LTP</th><th>P&L</th><th>SL Price</th><th>TSL</th><th>Synced</th><th></th></tr>
      </thead>
      <tbody id="upstox-body">
        <tr><td colspan="10" style="text-align:center;padding:20px;color:#94a3b8;">Click Sync to load positions</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
var socket = io();

function addManualPosition() {
  const symbol    = document.getElementById('m-symbol').value.trim().toUpperCase();
  const qty       = document.getElementById('m-qty').value;
  const buy_price = document.getElementById('m-price').value;
  const broker    = document.getElementById('m-broker').value;
  const itype     = document.getElementById('m-itype').value;
  const msg       = document.getElementById('m-msg');
  if (!symbol || !qty || !buy_price) { msg.textContent = '❌ Fill all fields'; return; }
  fetch('/api/auto/manual/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol, qty: parseInt(qty), buy_price: parseFloat(buy_price), broker, itype})
  }).then(r => r.json()).then(d => {
    if (d.status === 'added') {
      msg.textContent = '✅ Added — SL: ₹' + d.sl_price;
      msg.style.color = '#16a34a';
      document.getElementById('m-symbol').value = '';
      document.getElementById('m-qty').value    = '';
      document.getElementById('m-price').value  = '';
      loadUpstoxPositions();
    } else {
      msg.textContent = '❌ ' + (d.error || 'Failed');
      msg.style.color = '#dc2626';
    }
  });
}

function removeManualPosition(symbol, broker) {
  if (!confirm('Remove ' + symbol + '?')) return;
  fetch('/api/auto/manual/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol, broker})
  }).then(r => r.json()).then(d => { if (d.status === 'removed') loadUpstoxPositions(); });
}

function upstoxLogin() {
  fetch('/api/auto/upstox/login').then(r => r.json()).then(d => window.open(d.login_url, '_blank'));
}

function upstoxSync() {
  fetch('/api/auto/upstox/sync', {method:'POST'}).then(() => loadUpstoxPositions());
}

function deleteUpstoxPosition(symbol, broker) {
  if (!confirm('🗑 Delete ' + symbol + ' (' + broker + ') from DB?\\nThis cannot be undone.')) return;
  fetch('/api/auto/upstox/position/delete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol, broker})
  }).then(r => r.json()).then(d => {
    if (d.status === 'deleted') loadUpstoxPositions();
    else alert('Error: ' + (d.error || 'Unknown'));
  });
}

function loadUpstoxPositions() {
  fetch('/api/auto/upstox/token').then(r => r.json()).then(t => {
    const el = document.getElementById('upstox-token-status');
    if (t.is_valid) {
      el.textContent = '✅ TOKEN VALID TILL ' + t.expires_at;
      el.style.background = '#dcfce7'; el.style.color = '#16a34a';
    } else {
      el.textContent = '❌ Token expired — Login';
      el.style.background = '#fee2e2'; el.style.color = '#dc2626';
    }
  });

  fetch('/api/auto/upstox/positions').then(r => r.json()).then(d => {
    const tbody = document.getElementById('upstox-body');
    if (!d.positions || d.positions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:20px;color:#94a3b8;">No positions in DB</td></tr>';
      return;
    }
    tbody.innerHTML = d.positions.map(p => {
      const pnlClass = p.pnl > 0 ? 'green' : p.pnl < 0 ? 'red' : 'gray';
      const buyFmt   = p.itype === 'US_STOCK' ? '$' + p.buy_price : '₹' + Number(p.buy_price).toLocaleString('en-IN');
      const ltpFmt   = p.itype === 'US_STOCK' ? '$' + p.ltp       : '₹' + Number(p.ltp).toLocaleString('en-IN');
      const slFmt    = p.sl_price > 0 ? '₹' + Number(p.sl_price).toLocaleString('en-IN') : '—';
      const pnlFmt   = (p.pnl >= 0 ? '+₹' : '-₹') + Math.abs(p.pnl).toLocaleString('en-IN');
      const broker   = p.broker || '';
      return \`<tr>
        <td style="font-weight:600">\${p.symbol}</td>
        <td><span class="badge" style="background:#eff6ff;color:#2563eb">\${p.itype}</span></td>
        <td>\${p.qty}</td>
        <td>\${buyFmt}</td>
        <td>\${ltpFmt}</td>
        <td class="\${pnlClass}" style="font-weight:600">\${pnlFmt}</td>
        <td style="color:#dc2626">\${slFmt}</td>
        <td>\${p.tsl_active ? '<span class="badge badge-buy">ON</span>' : '<span class="badge badge-hold">OFF</span>'}</td>
        <td style="font-size:11px;color:#94a3b8">\${p.synced_at || '—'}</td>
        <td><button onclick="deleteUpstoxPosition('\${p.symbol}','\${broker}')"
          style="background:none;border:1px solid #fca5a5;color:#dc2626;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:12px;"
          title="Delete from DB">🗑</button></td>
      </tr>\`;
    }).join('');
  });
}

socket.on('state_update', (d) => {
  document.getElementById('capital').textContent    = '₹' + Number(d.capital||0).toLocaleString('en-IN');
  document.getElementById('pnl').textContent        = '₹' + Number(d.realised_pnl||0).toLocaleString('en-IN');
  document.getElementById('open_pnl').textContent   = '₹' + Number(d.open_pnl||0).toLocaleString('en-IN');
  document.getElementById('win_rate').textContent   = (d.win_rate||0) + '%';
  document.getElementById('wins_losses').textContent= (d.wins||0) + ' / ' + (d.losses||0);
  document.getElementById('win-bar').style.width    = Math.min(d.win_rate||0,100) + '%';
  document.getElementById('total_trades').textContent = d.total_trades||0;
});

setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-IN');
}, 1000);

loadUpstoxPositions();
setInterval(loadUpstoxPositions, 30000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

def push_updates():
    while True:
        try:
            from db_state import load_state as _fresh, load_trades as _lt
            _fs = _fresh() or {}
            trades  = _lt()
            closed  = [t for t in trades if t.get("action") == "SELL"]
            wins    = [t for t in closed if (t.get("pnl") or 0) > 0]
            losses  = [t for t in closed if (t.get("pnl") or 0) <= 0]
            _fs["total_trades"] = len(closed)
            _fs["wins"]         = len(wins)
            _fs["losses"]       = len(losses)
            _fs["win_rate"]     = round(len(wins)/len(closed)*100,1) if closed else 0
            _fs["trades"]       = trades
            socketio.emit('state_update', _fs)
        except Exception as e:
            print(f"[push] {e}")
        time.sleep(5)

def start_dashboard():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    threading.Thread(target=push_updates, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    start_dashboard()
