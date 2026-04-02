"""
V11 AutoPilot — Flask Dashboard + Scheduler + Telegram
Deploy on Railway and forget. It trades for you.
"""
import os, logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler

from config import *
from data import download_prices, get_nifty200_tickers
from strategy import generate_signals, detect_regime, safe_pick
from portfolio import (load_state, save_state, load_trades, save_trades,
                       portfolio_value, holdings_detail, execute_rebalance, add_funds)
from broker import AngelBroker
import alerts

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)
broker = None

# ═══════════════════════════════════════════
# SCHEDULED JOBS
# ═══════════════════════════════════════════
def job_rebalance():
    log.info("🔄 MONTHLY REBALANCE")
    try:
        universe = get_nifty200_tickers()
        prices, _ = download_prices(universe)
        st = load_state()
        target, regime, picks, details = generate_signals(prices, universe)

        st["regime"] = regime; st["details"] = details; st["picks"] = picks
        real_broker = broker if MODE == "real" and broker and broker.logged_in else None
        trades = execute_rebalance(st, target, prices, real_broker)
        pv = portfolio_value(st, prices)

        st["last_rebalance"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        st["history"].append({"date":datetime.now().strftime("%Y-%m-%d"),"value":round(pv,2),"regime":regime})
        save_state(st)
        tl = load_trades(); tl.extend(trades); save_trades(tl)

        ret = (pv/st["inception_value"]-1)*100 if st["inception_value"]>0 else 0
        alerts.alert_rebalance(regime, pv, ret, picks, trades, MODE)
        log.info(f"✅ Done. PV=₹{pv:,.0f} regime={regime} trades={len(trades)}")
    except Exception as e:
        log.error(f"Rebalance error: {e}")
        alerts.send(f"❌ Rebalance failed: {e}")

def job_crash_check():
    log.info("🔍 DAILY CRASH CHECK")
    try:
        universe = get_nifty200_tickers()
        prices, _ = download_prices(universe)
        regime, details = detect_regime(prices)
        st = load_state()
        st["regime"] = regime; st["details"] = details; save_state(st)

        pv = portfolio_value(st, prices)
        ret = (pv/st["inception_value"]-1)*100 if st["inception_value"]>0 else 0

        if regime == "CRASH" and st["holdings"]:
            log.info("⚠️ CRASH — emergency exit!")
            target = safe_pick(prices, len(prices)-1)
            real_broker = broker if MODE=="real" and broker and broker.logged_in else None
            trades = execute_rebalance(st, target, prices, real_broker)
            pv = portfolio_value(st, prices)
            st["history"].append({"date":datetime.now().strftime("%Y-%m-%d"),"value":round(pv,2),"regime":"CRASH_EXIT"})
            save_state(st)
            tl = load_trades(); tl.extend(trades); save_trades(tl)
            alerts.alert_crash(regime, details, trades, MODE)
        else:
            alerts.alert_daily(regime, pv, ret, details, MODE)
            log.info(f"✅ No crash. regime={regime} PV=₹{pv:,.0f}")
    except Exception as e:
        log.error(f"Crash check error: {e}")

# ═══════════════════════════════════════════
# DASHBOARD HTML
# ═══════════════════════════════════════════
DASH = """<!DOCTYPE html><html><head>
<title>V11 AutoPilot</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#060d1a;color:#e2e8f0;font-family:-apple-system,system-ui,sans-serif;padding:16px;max-width:1200px;margin:0 auto}
.hdr{text-align:center;padding:20px 0;border-bottom:1px solid #1e293b;margin-bottom:20px}
.hdr h1{color:#22d3ee;font-size:26px;font-weight:700}
.hdr .sub{color:#64748b;font-size:13px;margin-top:4px}
.mode{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;margin-left:8px}
.mode-paper{background:#1e3a5f;color:#67e8f9}
.mode-real{background:#7f1d1d;color:#fca5a5}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.kpi{background:#0c1528;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center}
.kpi .l{color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px}
.kpi .v{color:#22d3ee;font-size:22px;font-weight:700;margin-top:2px}
.kpi .v.g{color:#10b981}.kpi .v.r{color:#ef4444}.kpi .v.o{color:#f59e0b}
.card{background:#0c1528;border:1px solid #1e293b;border-radius:10px;padding:16px;margin:12px 0}
.card h3{color:#94a3b8;font-size:13px;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
table{width:100%;border-collapse:collapse}
th{color:#64748b;font-size:10px;text-transform:uppercase;text-align:left;padding:6px 8px;border-bottom:1px solid #1e293b}
td{padding:8px;border-bottom:1px solid #0f1729;font-size:13px}
.buy{color:#10b981;font-weight:700}.sell{color:#ef4444;font-weight:700}
.bar{height:16px;border-radius:3px;background:#22d3ee;display:inline-block;vertical-align:middle}
.btn{background:#1e3a5f;color:#67e8f9;border:1px solid #22d3ee33;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin:4px}
.btn:hover{background:#22d3ee22}
.btn-danger{background:#7f1d1d;color:#fca5a5;border-color:#ef444433}
.signals span{display:inline-block;margin:2px 8px;font-size:12px}
input[type=number]{background:#0f1729;color:white;border:1px solid #1e293b;padding:8px;border-radius:6px;width:140px}
.footer{text-align:center;color:#334155;font-size:11px;margin-top:24px;padding:12px}
</style></head><body>

<div class="hdr">
  <h1>V11 AutoPilot <span class="mode mode-{{mode}}">{{mode}}</span></h1>
  <div class="sub">Acceleration Momentum | 31% CAGR Backtest | Auto-rebalancing</div>
</div>

<div class="grid">
  <div class="kpi"><div class="l">Portfolio</div><div class="v">₹{{"{:,.0f}".format(pv)}}</div></div>
  <div class="kpi"><div class="l">Return</div><div class="v {{'g' if ret>=0 else 'r'}}">{{"{:+.1f}%".format(ret)}}</div></div>
  <div class="kpi"><div class="l">Regime</div><div class="v {{'r' if regime=='CRASH' else 'o' if regime=='CHOPPY' else 'g'}}">{{regime}}</div></div>
  <div class="kpi"><div class="l">Cash</div><div class="v">₹{{"{:,.0f}".format(cash)}}</div></div>
  <div class="kpi"><div class="l">Positions</div><div class="v">{{n_pos}}</div></div>
  <div class="kpi"><div class="l">Last Rebal</div><div class="v" style="font-size:13px">{{last_reb or 'Never'}}</div></div>
</div>

{% if details %}
<div class="card"><h3>📊 Market Signals</h3>
<div class="signals">{% for k,v in details.items() %}<span><b>{{k}}:</b> {{v}}</span>{% endfor %}</div>
</div>{% endif %}

{% if holdings %}
<div class="card"><h3>💼 Holdings</h3>
<table><tr><th>Stock</th><th>Shares</th><th>Price</th><th>Value</th><th>Weight</th></tr>
{% for h in holdings %}
<tr><td><b>{{h.ticker}}</b> <small style="color:#64748b">{{h.category}}</small></td>
<td>{{h.shares}}</td><td>₹{{"{:,.2f}".format(h.price)}}</td>
<td>₹{{"{:,.0f}".format(h.value)}}</td>
<td>{{h.weight}}% <span class="bar" style="width:{{h.weight*2}}px"></span></td></tr>
{% endfor %}</table></div>{% endif %}

{% if picks %}
<div class="card"><h3>🏆 Current Picks</h3>
<table><tr><th>#</th><th>Stock</th><th>Momentum</th><th>Acceleration</th></tr>
{% for p in picks %}
<tr><td>{{loop.index}}</td><td><b>{{p.ticker}}</b></td>
<td class="g">+{{p.momentum}}%</td><td>{{p.acceleration}}%</td></tr>
{% endfor %}</table></div>{% endif %}

{% if trades %}
<div class="card"><h3>📝 Recent Trades</h3>
<table><tr><th>Date</th><th>Action</th><th>Stock</th><th>Shares</th><th>Value</th></tr>
{% for t in trades %}
<tr><td style="font-size:11px">{{t.time}}</td>
<td class="{{'buy' if t.action=='BUY' else 'sell'}}">{{t.action}}</td>
<td>{{t.ticker}}</td><td>{{t.shares}}</td><td>₹{{"{:,.0f}".format(t.value)}}</td></tr>
{% endfor %}</table></div>{% endif %}

{% if history %}
<div class="card"><h3>📈 Value History</h3>
<table><tr><th>Date</th><th>Value</th><th>Regime</th></tr>
{% for h in history %}
<tr><td>{{h.date}}</td><td>₹{{"{:,.0f}".format(h.value)}}</td><td>{{h.get('regime','')}}</td></tr>
{% endfor %}</table></div>{% endif %}

<div class="card"><h3>⚙️ Actions</h3>
<form action="/add-funds" method="post" style="display:inline">
  <input type="number" name="amount" placeholder="Amount ₹" min="1000">
  <button class="btn" type="submit">💰 Add Funds</button>
</form>
<a href="/api/rebalance" class="btn" onclick="return confirm('Run rebalance now?')">🔄 Rebalance Now</a>
<a href="/api/crash-check" class="btn">🔍 Crash Check</a>
<a href="/api/reset" class="btn btn-danger" onclick="return confirm('Reset portfolio? This cannot be undone.')">🗑️ Reset</a>
</div>

<div class="footer">Auto-refreshes every 5 min | Daily crash check 9:30AM | Monthly rebalance 1st</div>
</body></html>"""

# ═══════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════
@app.route('/')
def dashboard():
    st = load_state()
    try:
        prices, _ = download_prices(period="5d")  # Quick fetch for current prices
        pv = portfolio_value(st, prices)
        hold = holdings_detail(st, prices)
    except:
        pv = st["cash"] + sum(0 for _ in st["holdings"])  # Fallback
        hold = []

    ret = (pv/st["inception_value"]-1)*100 if st["inception_value"]>0 else 0
    trades = load_trades()

    return render_template_string(DASH,
        mode=MODE, pv=pv, ret=ret, regime=st.get("regime","?"),
        cash=st.get("cash",0), n_pos=len(st.get("holdings",{})),
        last_reb=(st.get("last_rebalance") or "")[:16],
        details=st.get("details",{}), holdings=hold,
        picks=st.get("picks",[]),
        trades=trades[-10:][::-1],
        history=st.get("history",[])[-12:][::-1],
    )

@app.route('/api/status')
def api_status():
    return jsonify(load_state())

@app.route('/api/rebalance')
def api_rebalance():
    job_rebalance()
    return redirect('/')

@app.route('/api/crash-check')
def api_crash():
    job_crash_check()
    return redirect('/')

@app.route('/api/reset')
def api_reset():
    st = {
        "cash":INITIAL_CAPITAL,"holdings":{},
        "inception":datetime.now().strftime("%Y-%m-%d"),
        "inception_value":INITIAL_CAPITAL,
        "last_rebalance":None,"regime":"UNKNOWN",
        "details":{},"picks":[],"history":[],"fund_adds":[],
    }
    save_state(st); save_trades([])
    return redirect('/')

@app.route('/add-funds', methods=['POST'])
def route_add_funds():
    amount = int(request.form.get('amount', 0))
    if amount >= 1000:
        st = load_state()
        add_funds(st, amount)
        alerts.send(f"💰 Funds added: ₹{amount:,.0f}")
    return redirect('/')

@app.route('/api/trades')
def api_trades():
    return jsonify(load_trades())

# ═══════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════
def create_app():
    global broker

    # Init state if first run
    if not os.path.exists(STATE_FILE):
        save_state(load_state())

    # Angel One login (real mode only)
    if MODE == "real":
        broker = AngelBroker()
        if not broker.login():
            log.warning("Angel One login failed — falling back to paper mode")

    # Scheduler
    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(job_rebalance, 'cron', day=1, hour=10, minute=0, id='monthly')
    sched.add_job(job_crash_check, 'cron', day_of_week='mon-fri', hour=9, minute=30, id='daily')
    sched.start()
    log.info(f"Scheduler started: daily crash 9:30AM, monthly rebalance 1st 10AM")

    alerts.alert_startup(MODE)
    return app

if __name__ == '__main__':
    create_app()
    log.info(f"🚀 V11 AutoPilot [{MODE}] on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)
