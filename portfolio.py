"""Portfolio state + trade execution (paper & real)."""
import json, os, logging
from datetime import datetime
import numpy as np, pandas as pd
from config import *

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {
        "cash": INITIAL_CAPITAL, "holdings": {},
        "inception": datetime.now().strftime("%Y-%m-%d"),
        "inception_value": INITIAL_CAPITAL,
        "last_rebalance": None, "regime": "UNKNOWN",
        "details": {}, "picks": [], "history": [], "fund_adds": [],
    }

def save_state(st):
    with open(STATE_FILE,'w') as f: json.dump(st,f,indent=2,default=str)

def load_trades():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f: return json.load(f)
    return []

def save_trades(tr):
    with open(TRADES_FILE,'w') as f: json.dump(tr,f,indent=2,default=str)

# ═══════════════════════════════════════════
# PORTFOLIO VALUE
# ═══════════════════════════════════════════
def portfolio_value(st, prices):
    pv = st["cash"]
    last = prices.iloc[-1]
    for t,s in st["holdings"].items():
        if t in last.index and not pd.isna(last[t]) and last[t]>0:
            pv += s*last[t]
    return pv

def holdings_detail(st, prices):
    """Returns list of dicts with ticker, shares, price, value, weight."""
    last = prices.iloc[-1]
    pv = portfolio_value(st, prices)
    rows = []
    for t,s in st["holdings"].items():
        p = last.get(t, np.nan)
        if not pd.isna(p) and p > 0:
            val = s*p
            cat = "🛡️ Safe" if t in SAFE_HAVENS else "🇮🇳 India"
            rows.append({
                "ticker":t, "shares":s, "price":round(p,2),
                "value":round(val,2), "weight":round(val/pv*100,1) if pv>0 else 0,
                "category":cat
            })
    rows.sort(key=lambda x: x["value"], reverse=True)
    return rows

def add_funds(st, amount):
    st["cash"] += amount
    st["fund_adds"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "amount": amount})
    st["inception_value"] += amount  # Adjust inception for accurate return calc
    save_state(st)
    return st

# ═══════════════════════════════════════════
# TRADE EXECUTION
# ═══════════════════════════════════════════
def execute_rebalance(st, target_w, prices, broker=None):
    """Execute delta rebalance. Returns list of trade dicts."""
    last = prices.iloc[-1]
    pv = portfolio_value(st, prices)
    cr = COST_BPS / 10000
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    trades = []

    # Current weights
    cw = {}
    for t,s in st["holdings"].items():
        if t in last.index and not pd.isna(last[t]) and last[t]>0:
            cw[t] = s*last[t]/pv if pv>0 else 0

    deltas = {t: target_w.get(t,0)-cw.get(t,0) for t in set(list(cw)+list(target_w))
              if abs(target_w.get(t,0)-cw.get(t,0)) > REBAL_THRESH}
    if not deltas: return trades

    # Sells first
    for t,d in sorted(deltas.items(), key=lambda x:x[1]):
        if d>=0: continue
        if t not in st["holdings"]: continue
        p = last.get(t)
        if not p or pd.isna(p) or p<=0: continue
        ss = min(st["holdings"][t], int(abs(d)*pv/p))
        if ss<=0: continue

        if broker:
            order_id = broker.place_order(t, ss, "SELL")
        else:
            order_id = f"PAPER-{now[-5:]}"

        st["cash"] += ss*p*(1-cr)
        st["holdings"][t] -= ss
        if st["holdings"][t]<=0: del st["holdings"][t]
        trades.append({"time":now,"action":"SELL","ticker":t,"shares":ss,
                       "price":round(p,2),"value":round(ss*p,2),"order_id":str(order_id)})

    # Buys
    for t,d in sorted(deltas.items(), key=lambda x:x[1], reverse=True):
        if d<=0: continue
        p = last.get(t)
        if not p or pd.isna(p) or p<=0: continue
        bv = min(d*pv, max(0,st["cash"]))
        bs = int(bv/p)
        if bs<=0: continue

        if broker:
            order_id = broker.place_order(t, bs, "BUY")
        else:
            order_id = f"PAPER-{now[-5:]}"

        st["cash"] -= bs*p*(1+cr)
        st["holdings"][t] = st["holdings"].get(t,0)+bs
        trades.append({"time":now,"action":"BUY","ticker":t,"shares":bs,
                       "price":round(p,2),"value":round(bs*p,2),"order_id":str(order_id)})

    return trades
