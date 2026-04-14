"""
V11 Strategy — Acceleration Momentum. 31.4% CAGR, 1.22 Sharpe.
Enhanced crash detection: RealVol + Vol Spike + Synthetic NiftyMom + Breadth Collapse.
No VIX or external index data needed — everything derived from stock prices.
"""
import numpy as np, pandas as pd
import logging
from config import *

log = logging.getLogger(__name__)

def _sma(p, w): return p.rolling(w, min_periods=w).mean()
def _vol(p, w=63): return np.log(p / p.shift(1)).rolling(w).std() * np.sqrt(252)


def detect_regime(prices, sl=None):
    """
    Enhanced crash detection using only stock prices:
    1. Breadth (% above 200 SMA)
    2. RealVol (median stock volatility)
    3. Vol Spike (RealVol surging vs recent average?) — replaces VIX
    4. Synthetic NiftyMom (median 3m return of stocks) — replaces ^NSEI
    5. Breadth Collapse (breadth dropping fast?) — replaces credit stress
    CrashScore out of 7 — same threshold as original.
    """
    if sl is None: sl = len(prices) - 1
    if sl < SMA_LONG: return "MILD", {}
    d = {}

    it = [t for t in BACKTEST_STOCKS if t in prices.columns]

    # 1. Breadth
    br = 0.5
    if len(it) > 5 and sl >= SMA_LONG:
        s2 = _sma(prices[it], SMA_LONG).iloc[sl]
        cu = prices[it].iloc[sl]
        v = s2.dropna().index.intersection(cu.dropna().index)
        if len(v) > 0: br = float((cu[v] > s2[v]).mean())
    d["Breadth"] = round(br, 3)

    # 2. RealVol
    rv = None
    if len(it) > 5 and sl > VOL_LOOKBACK:
        vs = _vol(prices[it].iloc[max(0, sl - VOL_LOOKBACK):sl + 1], VOL_LOOKBACK).iloc[-1].dropna()
        if len(vs) > 0: rv = float(vs.median()); d["RealVol"] = round(rv, 3)

    # 3. Vol Spike
    vol_spike = False
    if len(it) > 5 and sl > VOL_LOOKBACK + 63:
        vol_history = []
        for lookback_sl in range(max(VOL_LOOKBACK + 1, sl - 63), sl + 1, 5):
            vs_hist = _vol(prices[it].iloc[max(0, lookback_sl - VOL_LOOKBACK):lookback_sl + 1], VOL_LOOKBACK).iloc[-1].dropna()
            if len(vs_hist) > 0: vol_history.append(float(vs_hist.median()))
        if vol_history and rv:
            avg_vol = np.mean(vol_history)
            if avg_vol > 0:
                vol_ratio = rv / avg_vol
                d["VolSpike"] = round(vol_ratio, 2)
                if vol_ratio > 1.4: vol_spike = True

    # 4. Synthetic NiftyMom
    nm = 0
    if len(it) > 10 and sl > LOOKBACK_3M:
        returns_3m = []
        for t in it:
            try:
                p_now = prices[t].iloc[sl]; p_3m = prices[t].iloc[sl - LOOKBACK_3M]
                if not pd.isna(p_now) and not pd.isna(p_3m) and p_3m > 0:
                    returns_3m.append(p_now / p_3m - 1)
            except: continue
        if len(returns_3m) > 5:
            returns_3m.sort(reverse=True)
            nm = float(np.median(returns_3m[:min(30, len(returns_3m))]))
            d["SynthNiftyMom"] = round(nm, 3)

    # 5. Breadth Collapse
    breadth_collapse = False
    if len(it) > 5 and sl >= SMA_LONG + LOOKBACK_1M:
        s2_old = _sma(prices[it], SMA_LONG).iloc[sl - LOOKBACK_1M]
        cu_old = prices[it].iloc[sl - LOOKBACK_1M]
        v_old = s2_old.dropna().index.intersection(cu_old.dropna().index)
        if len(v_old) > 0:
            br_old = float((cu_old[v_old] > s2_old[v_old]).mean())
            br_drop = br - br_old
            d["BreadthDelta"] = round(br_drop, 3)
            if br_drop < -0.15: breadth_collapse = True

    # Crash Score (out of 7)
    c = 0
    if vol_spike:              c += 2
    if breadth_collapse:       c += 2
    if rv and rv > RVOL_CRASH: c += 1
    if br < 0.20:             c += 1
    if nm < -0.15:            c += 1
    d["CrashScore"] = f"{c}/7"

    if c >= 3: return "CRASH", d
    if br > 0.55 and nm > 0.03 and not vol_spike:
        if br > 0.60 or (rv and rv < 0.20): return "STRONG", d
    if br > 0.35 and nm > -0.05 and c <= 1: return "MILD", d
    return "CHOPPY", d


def safe_pick(prices, sl):
    av = [t for t in SAFE_HAVENS if t in prices.columns]
    if not av: return {}
    return {t: 1.0 / len(av) for t in av}


def generate_signals(prices, universe=None, sl=None):
    if sl is None: sl = len(prices) - 2
    if sl < LOOKBACK_12M: return safe_pick(prices, sl), "WAIT", [], {}

    regime, details = detect_regime(prices, sl)
    if regime == "CRASH": return safe_pick(prices, sl), regime, [], details

    if universe is None:
        universe = [t for t in BACKTEST_STOCKS + SAFE_HAVENS if t in prices.columns]
    else:
        universe = [t for t in universe + SAFE_HAVENS if t in prices.columns]

    cands = []
    for t in universe:
        try:
            pn = prices[t].iloc[sl]; p1 = prices[t].iloc[sl - LOOKBACK_1M]
            p6 = prices[t].iloc[sl - LOOKBACK_6M]; p12 = prices[t].iloc[sl - LOOKBACK_12M]
        except: continue
        if any(pd.isna(x) for x in [pn, p1, p6, p12]) or p12 <= 0 or p6 <= 0: continue
        m12 = p1 / p12 - 1
        if m12 <= 0: continue
        s2 = _sma(prices[[t]], SMA_LONG).iloc[sl][t]
        if pd.isna(s2) or pn <= s2: continue
        p52 = prices[t].iloc[max(0, sl - 252):sl + 1].dropna()
        if len(p52) <= 10 or ((p52 - p52.cummax()) / p52.cummax()).min() <= DD_FILTER: continue
        acc = (pn/p6 - 1)*2 - (p6/p12 - 1)*2
        if acc <= ACCEL_MIN: continue
        score = m12 * (1 + max(0, acc))
        cands.append({"ticker": t, "score": score, "momentum": round(m12*100, 1), "acceleration": round(acc*100, 1)})

    if len(cands) < 2: return safe_pick(prices, sl), regime, [], details
    cands.sort(key=lambda x: x["score"], reverse=True)
    top = cands[:TOP_N]
    picks = [{"ticker": c["ticker"], "momentum": c["momentum"], "acceleration": c["acceleration"]} for c in top]
    tks = [c["ticker"] for c in top]

    vd = _vol(prices[tks].iloc[max(0, sl - VOL_LOOKBACK):sl + 1], VOL_LOOKBACK).iloc[-1].replace(0, np.nan).dropna()
    if len(vd) > 0: iv = 1.0 / vd; w = (iv / iv.sum()).to_dict()
    else: w = {t: 1.0 / len(tks) for t in tks}
    tot = sum(w.values())
    if tot > 0: w = {t: v / tot for t, v in w.items()}

    if regime == "CHOPPY":
        av = [t for t in SAFE_HAVENS if t in prices.columns]
        if av:
            for t in w: w[t] *= 0.80
            for t in av: w[t] = w.get(t, 0) + 0.20 / len(av)

    return w, regime, picks, details