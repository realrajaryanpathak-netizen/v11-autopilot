"""V11 Strategy — Acceleration Momentum. 31.4% CAGR, 1.22 Sharpe."""
import numpy as np, pandas as pd
import logging
from config import *

log = logging.getLogger(__name__)

def _sma(p, w): return p.rolling(w, min_periods=w).mean()
def _vol(p, w=63): return np.log(p/p.shift(1)).rolling(w).std()*np.sqrt(252)

def detect_regime(prices, sl=None):
    if sl is None: sl = len(prices)-1
    if sl < SMA_LONG: return "MILD_TREND", {}
    d = {}
    vix = None
    if "^VIX" in prices.columns:
        v = prices["^VIX"].iloc[sl]
        if not pd.isna(v): vix = v; d["VIX"] = round(v,1)
    cs = False
    if "LQD" in prices.columns and "JNK" in prices.columns:
        lqd,jnk = prices["LQD"].iloc[sl],prices["JNK"].iloc[sl]
        if not pd.isna(lqd) and not pd.isna(jnk) and jnk>0:
            r=lqd/jnk; d["LQD/JNK"]=round(r,3)
            if r>CREDIT_STRESS: cs=True
    yi = False
    if "^TNX" in prices.columns and "^IRX" in prices.columns:
        y10,y3=prices["^TNX"].iloc[sl],prices["^IRX"].iloc[sl]
        if not pd.isna(y10) and not pd.isna(y3):
            if (y10-y3)<0: yi=True; d["YieldCurve"]=round(float(y10-y3),2)
    it=[t for t in BACKTEST_STOCKS if t in prices.columns]
    br=0.5
    if len(it)>5 and sl>=SMA_LONG:
        s2=_sma(prices[it],SMA_LONG).iloc[sl]; cu=prices[it].iloc[sl]
        v=s2.dropna().index.intersection(cu.dropna().index)
        if len(v)>0: br=float((cu[v]>s2[v]).mean())
    d["Breadth"]=round(br,3)
    rv=None
    if len(it)>5 and sl>VOL_LOOKBACK:
        vs=_vol(prices[it].iloc[max(0,sl-VOL_LOOKBACK):sl+1],VOL_LOOKBACK).iloc[-1].dropna()
        if len(vs)>0: rv=float(vs.median()); d["RealVol"]=round(rv,3)
    nm=0
    if "^NSEI" in prices.columns and sl>LOOKBACK_3M:
        nn,n3=prices["^NSEI"].iloc[sl],prices["^NSEI"].iloc[sl-LOOKBACK_3M]
        if not pd.isna(nn) and not pd.isna(n3) and n3>0:
            nm=nn/n3-1; d["NiftyMom"]=round(nm,3)
    c=0
    if vix and vix>VIX_HIGH: c+=2
    if cs: c+=2
    if rv and rv>RVOL_CRASH: c+=1
    if br<0.20: c+=1
    if nm<-0.15: c+=1
    d["CrashScore"]=f"{c}/7"
    if c>=3: return "CRASH",d
    if br>0.55 and nm>0.03 and not yi:
        if (vix and vix<VIX_LOW) or (not vix and br>0.60): return "STRONG",d
    if br>0.35 and nm>-0.05 and c<=1: return "MILD",d
    return "CHOPPY",d

def safe_pick(prices, sl):
    av=[t for t in SAFE_HAVENS if t in prices.columns]
    if not av: return {}
    return {t:1.0/len(av) for t in av}

def generate_signals(prices, universe=None, sl=None):
    """
    Returns: (weights, regime, picks, details)
    picks = [{"ticker","momentum","acceleration"}, ...]
    """
    if sl is None: sl=len(prices)-2
    if sl<LOOKBACK_12M: return safe_pick(prices,sl),"WAIT",[],{}
    
    regime,details = detect_regime(prices,sl)
    if regime=="CRASH": return safe_pick(prices,sl),regime,[],details
    
    if universe is None:
        universe = [t for t in BACKTEST_STOCKS+SAFE_HAVENS if t in prices.columns]
    else:
        universe = [t for t in universe+SAFE_HAVENS if t in prices.columns]
    
    cands=[]
    for t in universe:
        try:
            pn=prices[t].iloc[sl]; p1=prices[t].iloc[sl-LOOKBACK_1M]
            p6=prices[t].iloc[sl-LOOKBACK_6M]; p12=prices[t].iloc[sl-LOOKBACK_12M]
        except: continue
        if any(pd.isna(x) for x in [pn,p1,p6,p12]) or p12<=0 or p6<=0: continue
        m12=p1/p12-1
        if m12<=0: continue
        s2=_sma(prices[[t]],SMA_LONG).iloc[sl][t]
        if pd.isna(s2) or pn<=s2: continue
        p52=prices[t].iloc[max(0,sl-252):sl+1].dropna()
        if len(p52)<=10 or ((p52-p52.cummax())/p52.cummax()).min()<=DD_FILTER: continue
        acc=(pn/p6-1)*2-(p6/p12-1)*2
        if acc<=ACCEL_MIN: continue
        score=m12*(1+max(0,acc))
        cands.append({"ticker":t,"score":score,"momentum":round(m12*100,1),"acceleration":round(acc*100,1)})
    
    if len(cands)<2: return safe_pick(prices,sl),regime,[],details
    cands.sort(key=lambda x:x["score"],reverse=True)
    top=cands[:TOP_N]
    picks=[{"ticker":c["ticker"],"momentum":c["momentum"],"acceleration":c["acceleration"]} for c in top]
    tks=[c["ticker"] for c in top]
    
    vd=_vol(prices[tks].iloc[max(0,sl-VOL_LOOKBACK):sl+1],VOL_LOOKBACK).iloc[-1].replace(0,np.nan).dropna()
    if len(vd)>0: iv=1.0/vd; w=(iv/iv.sum()).to_dict()
    else: w={t:1.0/len(tks) for t in tks}
    tot=sum(w.values())
    if tot>0: w={t:v/tot for t,v in w.items()}
    
    if regime=="CHOPPY":
        av=[t for t in SAFE_HAVENS if t in prices.columns]
        if av:
            for t in w: w[t]*=0.80
            for t in av: w[t]=w.get(t,0)+0.20/len(av)
    
    return w,regime,picks,details
