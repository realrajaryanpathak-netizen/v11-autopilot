"""
V11 Backtest — 3-way comparison:
  1. ORIGINAL (VIX + Nifty + Credit signals)
  2. WITHOUT  (Breadth + Vol only)
  3. ENHANCED (Vol Spike + Synth NiftyMom + Breadth Collapse — no external data)

Run: python backtest.py [datafile.csv]
"""
import pandas as pd
import numpy as np
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

LOOKBACK_12M = 252; LOOKBACK_6M = 126; LOOKBACK_3M = 63; LOOKBACK_1M = 21
SMA_LONG = 200; VOL_LOOKBACK = 63; TOP_N = 4; DD_FILTER = -0.40
ACCEL_MIN = -0.10; COST_BPS = 15; REBAL_THRESH = 0.03
VIX_HIGH = 28; VIX_LOW = 15; RVOL_CRASH = 0.35
SAFE_HAVENS = ["GOLDBEES.NS"]

BACKTEST_STOCKS = [
    "ADANIENT.NS","BAJFINANCE.NS","HDFCBANK.NS","HINDUNILVR.NS",
    "ICICIBANK.NS","INFY.NS","ITC.NS","LT.NS","MARUTI.NS",
    "RELIANCE.NS","SBIN.NS","SUNPHARMA.NS","TCS.NS","WIPRO.NS",
    "ASIANPAINT.NS","AXISBANK.NS","BHARTIARTL.NS","DIVISLAB.NS",
    "HCLTECH.NS","JSWSTEEL.NS","KOTAKBANK.NS","NESTLEIND.NS",
    "NTPC.NS","ONGC.NS","POWERGRID.NS","TATASTEEL.NS",
    "TITAN.NS","TRENT.NS","ULTRACEMCO.NS",
    "YESBANK.NS","RCOM.NS","JPPOWER.NS","SUZLON.NS","IDEA.NS",
    "PNB.NS","BANKBARODA.NS","BHEL.NS","ZEEL.NS","SAIL.NS",
    "VEDL.NS","HINDALCO.NS","INDUSINDBK.NS","FEDERALBNK.NS",
    "CANBK.NS","PFC.NS","RECLTD.NS","NATIONALUM.NS",
    "ASTRAL.NS","ATUL.NS","COFORGE.NS","DEEPAKNTR.NS",
    "PERSISTENT.NS","PIIND.NS","MUTHOOTFIN.NS","NAUKRI.NS",
    "PHOENIXLTD.NS","MANAPPURAM.NS","MPHASIS.NS","GODREJPROP.NS",
    "IIFL.NS","OBEROIRLTY.NS",
]

def _sma(p, w): return p.rolling(w, min_periods=w).mean()
def _vol(p, w=63): return np.log(p / p.shift(1)).rolling(w).std() * np.sqrt(252)

# ═══════════════════════════════════════════
# THREE REGIME DETECTORS
# ═══════════════════════════════════════════

def regime_ORIGINAL(prices, sl):
    """Original with VIX + Nifty + Credit (7 signals)."""
    if sl < SMA_LONG: return "MILD", {}
    d = {}
    vix = None
    for col in ["^VIX", "^INDIAVIX", "INDIA VIX"]:
        if col in prices.columns:
            v = prices[col].iloc[sl]
            if not pd.isna(v): vix = v; d["VIX"] = round(v, 1); break
    cs = False
    if "LQD" in prices.columns and "JNK" in prices.columns:
        lqd, jnk = prices["LQD"].iloc[sl], prices["JNK"].iloc[sl]
        if not pd.isna(lqd) and not pd.isna(jnk) and jnk > 0:
            r = lqd / jnk; d["LQD/JNK"] = round(r, 3)
            if r > 1.45: cs = True
    yi = False
    if "^TNX" in prices.columns and "^IRX" in prices.columns:
        y10, y3 = prices["^TNX"].iloc[sl], prices["^IRX"].iloc[sl]
        if not pd.isna(y10) and not pd.isna(y3):
            if (y10 - y3) < 0: yi = True
    it = [t for t in BACKTEST_STOCKS if t in prices.columns]
    br = 0.5
    if len(it) > 5 and sl >= SMA_LONG:
        s2 = _sma(prices[it], SMA_LONG).iloc[sl]; cu = prices[it].iloc[sl]
        v = s2.dropna().index.intersection(cu.dropna().index)
        if len(v) > 0: br = float((cu[v] > s2[v]).mean())
    d["Breadth"] = round(br, 3)
    rv = None
    if len(it) > 5 and sl > VOL_LOOKBACK:
        vs = _vol(prices[it].iloc[max(0, sl-VOL_LOOKBACK):sl+1], VOL_LOOKBACK).iloc[-1].dropna()
        if len(vs) > 0: rv = float(vs.median()); d["RealVol"] = round(rv, 3)
    nm = 0
    for col in ["^NSEI", "NIFTY"]:
        if col in prices.columns and sl > LOOKBACK_3M:
            nn = prices[col].iloc[sl]; n3 = prices[col].iloc[sl - LOOKBACK_3M]
            if not pd.isna(nn) and not pd.isna(n3) and n3 > 0:
                nm = nn / n3 - 1; d["NiftyMom"] = round(nm, 3); break
    c = 0
    if vix and vix > VIX_HIGH: c += 2
    if cs: c += 2
    if rv and rv > RVOL_CRASH: c += 1
    if br < 0.20: c += 1
    if nm < -0.15: c += 1
    d["CrashScore"] = f"{c}/7"
    if c >= 3: return "CRASH", d
    if br > 0.55 and nm > 0.03 and not yi:
        if (vix and vix < VIX_LOW) or (not vix and br > 0.60): return "STRONG", d
    if br > 0.35 and nm > -0.05 and c <= 1: return "MILD", d
    return "CHOPPY", d


def regime_WITHOUT(prices, sl):
    """Minimal: Breadth + RealVol only."""
    if sl < SMA_LONG: return "MILD", {}
    d = {}
    it = [t for t in BACKTEST_STOCKS if t in prices.columns]
    br = 0.5
    if len(it) > 5 and sl >= SMA_LONG:
        s2 = _sma(prices[it], SMA_LONG).iloc[sl]; cu = prices[it].iloc[sl]
        v = s2.dropna().index.intersection(cu.dropna().index)
        if len(v) > 0: br = float((cu[v] > s2[v]).mean())
    d["Breadth"] = round(br, 3)
    rv = None
    if len(it) > 5 and sl > VOL_LOOKBACK:
        vs = _vol(prices[it].iloc[max(0, sl-VOL_LOOKBACK):sl+1], VOL_LOOKBACK).iloc[-1].dropna()
        if len(vs) > 0: rv = float(vs.median()); d["RealVol"] = round(rv, 3)
    c = 0
    if rv and rv > RVOL_CRASH: c += 1
    if br < 0.20: c += 1
    d["CrashScore"] = f"{c}/2"
    if c >= 2: return "CRASH", d
    if br > 0.55: return "STRONG", d
    if br > 0.35 and c == 0: return "MILD", d
    return "CHOPPY", d


def regime_ENHANCED(prices, sl):
    """Enhanced: Vol Spike + Synth NiftyMom + Breadth Collapse (no external data)."""
    if sl < SMA_LONG: return "MILD", {}
    d = {}
    it = [t for t in BACKTEST_STOCKS if t in prices.columns]

    # Breadth
    br = 0.5
    if len(it) > 5 and sl >= SMA_LONG:
        s2 = _sma(prices[it], SMA_LONG).iloc[sl]; cu = prices[it].iloc[sl]
        v = s2.dropna().index.intersection(cu.dropna().index)
        if len(v) > 0: br = float((cu[v] > s2[v]).mean())
    d["Breadth"] = round(br, 3)

    # RealVol
    rv = None
    if len(it) > 5 and sl > VOL_LOOKBACK:
        vs = _vol(prices[it].iloc[max(0, sl - VOL_LOOKBACK):sl + 1], VOL_LOOKBACK).iloc[-1].dropna()
        if len(vs) > 0: rv = float(vs.median()); d["RealVol"] = round(rv, 3)

    # Vol Spike (replaces VIX)
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

    # Synthetic NiftyMom (replaces ^NSEI)
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

    # Breadth Collapse (replaces credit stress)
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


# ═══════════════════════════════════════════
# SIGNAL GENERATION + EXECUTION
# ═══════════════════════════════════════════

def safe_pick(prices, sl):
    av = [t for t in SAFE_HAVENS if t in prices.columns]
    if not av: return {}
    return {t: 1.0 / len(av) for t in av}

def generate_signals(prices, universe, sl, regime_func):
    if sl < LOOKBACK_12M: return safe_pick(prices, sl), "WAIT", [], {}
    regime, details = regime_func(prices, sl)
    if regime == "CRASH": return safe_pick(prices, sl), regime, [], details

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
        p52 = prices[t].iloc[max(0, sl-252):sl+1].dropna()
        if len(p52) <= 10 or ((p52 - p52.cummax()) / p52.cummax()).min() <= DD_FILTER: continue
        acc = (pn/p6 - 1)*2 - (p6/p12 - 1)*2
        if acc <= ACCEL_MIN: continue
        score = m12 * (1 + max(0, acc))
        cands.append({"ticker": t, "score": score})

    if len(cands) < 2: return safe_pick(prices, sl), regime, [], details
    cands.sort(key=lambda x: x["score"], reverse=True)
    tks = [c["ticker"] for c in cands[:TOP_N]]

    vd = _vol(prices[tks].iloc[max(0, sl-VOL_LOOKBACK):sl+1], VOL_LOOKBACK).iloc[-1].replace(0, np.nan).dropna()
    if len(vd) > 0: iv = 1.0 / vd; w = (iv / iv.sum()).to_dict()
    else: w = {t: 1.0 / len(tks) for t in tks}
    tot = sum(w.values())
    if tot > 0: w = {t: v/tot for t, v in w.items()}

    if regime == "CHOPPY":
        av = [t for t in SAFE_HAVENS if t in prices.columns]
        if av:
            for t in w: w[t] *= 0.80
            for t in av: w[t] = w.get(t, 0) + 0.20 / len(av)
    return w, regime, cands[:TOP_N], details

def _execute(cash, holdings, target_w, last_row, pv, cost_rate):
    cw = {}
    for t, s in holdings.items():
        p = last_row.get(t, np.nan)
        if not pd.isna(p) and p > 0: cw[t] = s * p / pv if pv > 0 else 0
    deltas = {}
    for t in set(list(cw) + list(target_w)):
        d = target_w.get(t, 0) - cw.get(t, 0)
        if abs(d) > REBAL_THRESH: deltas[t] = d
    new_holdings = dict(holdings)
    for t, d in sorted(deltas.items(), key=lambda x: x[1]):
        if d >= 0: continue
        if t not in new_holdings: continue
        p = last_row.get(t, np.nan)
        if pd.isna(p) or p <= 0: continue
        ss = min(new_holdings[t], int(abs(d) * pv / p))
        if ss <= 0: continue
        cash += ss * p * (1 - cost_rate)
        new_holdings[t] -= ss
        if new_holdings[t] <= 0: del new_holdings[t]
    for t, d in sorted(deltas.items(), key=lambda x: x[1], reverse=True):
        if d <= 0: continue
        p = last_row.get(t, np.nan)
        if pd.isna(p) or p <= 0: continue
        bv = min(d * pv, max(0, cash))
        bs = int(bv / p)
        if bs <= 0: continue
        cash -= bs * p * (1 + cost_rate)
        new_holdings[t] = new_holdings.get(t, 0) + bs
    return cash, new_holdings


# ═══════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════

def run_backtest(prices, regime_func, label, universe):
    INITIAL = 1_000_000
    cash = INITIAL; holdings = {}; cost_rate = COST_BPS / 10000
    history = []; crash_exits = 0; regimes_seen = {}; yearly_returns = {}
    start_sl = LOOKBACK_12M + 1
    if start_sl >= len(prices): return None
    last_rebal_month = None; year_start_value = INITIAL

    for sl in range(start_sl, len(prices)):
        date = prices.index[sl]; last_row = prices.iloc[sl]
        pv = cash
        for t, s in holdings.items():
            p = last_row.get(t, np.nan)
            if not pd.isna(p) and p > 0: pv += s * p

        current_year = date.year
        if history and history[-1]["date"].year != current_year:
            prev_year = history[-1]["date"].year
            yearly_returns[prev_year] = round((history[-1]["value"] / year_start_value - 1) * 100, 1)
            year_start_value = history[-1]["value"]

        regime, details = regime_func(prices, sl)
        regimes_seen[regime] = regimes_seen.get(regime, 0) + 1

        if regime == "CRASH" and holdings:
            crash_exits += 1
            target = safe_pick(prices, sl)
            cash, holdings = _execute(cash, holdings, target, last_row, pv, cost_rate)
            pv = cash
            for t, s in holdings.items():
                p = last_row.get(t, np.nan)
                if not pd.isna(p) and p > 0: pv += s * p

        current_month = (date.year, date.month)
        if current_month != last_rebal_month:
            last_rebal_month = current_month
            target, reg, picks, det = generate_signals(prices, universe, sl, regime_func)
            cash, holdings = _execute(cash, holdings, target, last_row, pv, cost_rate)
            pv = cash
            for t, s in holdings.items():
                p = last_row.get(t, np.nan)
                if not pd.isna(p) and p > 0: pv += s * p

        history.append({"date": date, "value": pv, "regime": regime})
        if len(history) % 500 == 0:
            log.info(f"  [{label[:12]}] Day {len(history)}: {date.date()} PV=Rs{pv:,.0f}")

    if not history: return None
    last_year = history[-1]["date"].year
    if last_year not in yearly_returns:
        yearly_returns[last_year] = round((history[-1]["value"] / year_start_value - 1) * 100, 1)

    values = pd.Series([h["value"] for h in history], index=[h["date"] for h in history])
    total_return = (values.iloc[-1] / INITIAL - 1) * 100
    days = (values.index[-1] - values.index[0]).days; years = days / 365.25
    cagr = ((values.iloc[-1] / INITIAL) ** (1 / max(years, 0.01)) - 1) * 100
    daily_ret = values.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
    drawdowns = (values - values.cummax()) / values.cummax()
    max_dd = drawdowns.min() * 100; max_dd_date = drawdowns.idxmin()
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0
    monthly_vals = values.resample('ME').last().dropna()
    monthly_ret = monthly_vals.pct_change().dropna()
    win_rate = (monthly_ret > 0).mean() * 100

    return {
        "label": label, "total_return": round(total_return, 2), "cagr": round(cagr, 2),
        "sharpe": round(sharpe, 2), "max_dd": round(max_dd, 2),
        "max_dd_date": str(max_dd_date.date()) if hasattr(max_dd_date, 'date') else str(max_dd_date),
        "calmar": round(calmar, 2), "win_rate": round(win_rate, 1),
        "crash_exits": crash_exits, "regimes": regimes_seen,
        "final_value": round(values.iloc[-1]), "days_traded": len(history),
        "years": round(years, 1), "yearly_returns": yearly_returns,
    }


def main():
    if len(sys.argv) > 1: data_file = sys.argv[1]
    elif os.path.exists("backtest_20y.csv"): data_file = "backtest_20y.csv"
    elif os.path.exists("prices_cache.csv"): data_file = "prices_cache.csv"
    else: log.error("No data file!"); return

    prices = pd.read_csv(data_file, index_col=0, parse_dates=True)
    log.info(f"Loaded: {data_file} | {len(prices.columns)} tickers | {len(prices)} days | {prices.index[0].date()} -> {prices.index[-1].date()}")

    universe = [t for t in BACKTEST_STOCKS + SAFE_HAVENS if t in prices.columns]

    print("\n" + "=" * 75)
    print("  V11 BACKTEST — 3-WAY COMPARISON")
    print("  ORIGINAL (VIX+Nifty+Credit) vs WITHOUT vs ENHANCED (Vol Spike proxy)")
    print("=" * 75)

    log.info("Running ORIGINAL...")
    r1 = run_backtest(prices, regime_ORIGINAL, "ORIGINAL", universe)
    log.info("Running WITHOUT...")
    r2 = run_backtest(prices, regime_WITHOUT, "WITHOUT", universe)
    log.info("Running ENHANCED...")
    r3 = run_backtest(prices, regime_ENHANCED, "ENHANCED", universe)

    if not r1 or not r2 or not r3: log.error("Backtest failed"); return

    start = prices.index[LOOKBACK_12M + 1].date()
    end = prices.index[-1].date()
    print(f"\n  Period: {start} -> {end} ({r1['years']} years)")
    print(f"  Initial: Rs 10,00,000\n")

    fmt = "  {:<24} {:>15} {:>15} {:>15}"
    print(fmt.format("", "ORIGINAL", "WITHOUT", "ENHANCED"))
    print("  " + "-" * 62)
    print(fmt.format("CAGR", f"{r1['cagr']:+.1f}%", f"{r2['cagr']:+.1f}%", f"{r3['cagr']:+.1f}%"))
    print(fmt.format("Sharpe", f"{r1['sharpe']:.2f}", f"{r2['sharpe']:.2f}", f"{r3['sharpe']:.2f}"))
    print(fmt.format("Max Drawdown", f"{r1['max_dd']:.1f}%", f"{r2['max_dd']:.1f}%", f"{r3['max_dd']:.1f}%"))
    print(fmt.format("Max DD Date", r1['max_dd_date'], r2['max_dd_date'], r3['max_dd_date']))
    print(fmt.format("Calmar", f"{r1['calmar']:.2f}", f"{r2['calmar']:.2f}", f"{r3['calmar']:.2f}"))
    print(fmt.format("Win Rate (monthly)", f"{r1['win_rate']:.0f}%", f"{r2['win_rate']:.0f}%", f"{r3['win_rate']:.0f}%"))
    print(fmt.format("Crash Exits", str(r1['crash_exits']), str(r2['crash_exits']), str(r3['crash_exits'])))
    print(fmt.format("Final Value", f"Rs {r1['final_value']:,}", f"Rs {r2['final_value']:,}", f"Rs {r3['final_value']:,}"))

    # Regime breakdown
    print(f"\n  Regimes:")
    for label, r in [("ORIGINAL", r1), ("WITHOUT", r2), ("ENHANCED", r3)]:
        parts = [f"{k}={v}({v/r['days_traded']*100:.0f}%)" for k, v in sorted(r['regimes'].items())]
        print(f"  {label:12} {' | '.join(parts)}")

    # Year by year
    all_years = sorted(set(list(r1['yearly_returns'].keys()) + list(r2['yearly_returns'].keys()) + list(r3['yearly_returns'].keys())))
    if len(all_years) > 2:
        print(f"\n  Year-by-Year Returns:")
        yfmt = "  {:<6} {:>10} {:>10} {:>10}    {}"
        print(yfmt.format("Year", "ORIGINAL", "WITHOUT", "ENHANCED", "Best"))
        print("  " + "-" * 56)
        orig_wins = 0; without_wins = 0; enhanced_wins = 0
        for y in all_years:
            y1 = r1['yearly_returns'].get(y); y2 = r2['yearly_returns'].get(y); y3 = r3['yearly_returns'].get(y)
            s1 = f"{y1:+.1f}%" if y1 is not None else "---"
            s2 = f"{y2:+.1f}%" if y2 is not None else "---"
            s3 = f"{y3:+.1f}%" if y3 is not None else "---"
            vals = {k: v for k, v in [("O", y1), ("W", y2), ("E", y3)] if v is not None}
            best = max(vals, key=vals.get) if vals else ""
            if best == "O": orig_wins += 1; best = "ORIGINAL"
            elif best == "W": without_wins += 1; best = "WITHOUT"
            elif best == "E": enhanced_wins += 1; best = "ENHANCED"
            print(yfmt.format(y, s1, s2, s3, best))
        print(f"\n  Wins: ORIGINAL={orig_wins} | WITHOUT={without_wins} | ENHANCED={enhanced_wins}")

    # Verdict
    print("\n" + "=" * 75)
    print("  VERDICT")
    print("=" * 75)
    results = [("ORIGINAL", r1), ("WITHOUT", r2), ("ENHANCED", r3)]
    best_cagr = max(results, key=lambda x: x[1]['cagr'])
    best_sharpe = max(results, key=lambda x: x[1]['sharpe'])
    best_dd = max(results, key=lambda x: x[1]['max_dd'])  # least negative

    print(f"  Best CAGR:     {best_cagr[0]} ({best_cagr[1]['cagr']:+.1f}%)")
    print(f"  Best Sharpe:   {best_sharpe[0]} ({best_sharpe[1]['sharpe']:.2f})")
    print(f"  Best MaxDD:    {best_dd[0]} ({best_dd[1]['max_dd']:.1f}%)")

    e_vs_o_cagr = r3['cagr'] - r1['cagr']
    e_vs_o_dd = r3['max_dd'] - r1['max_dd']
    print(f"\n  ENHANCED vs ORIGINAL: CAGR {e_vs_o_cagr:+.1f}% | MaxDD {e_vs_o_dd:+.1f}%")

    if abs(e_vs_o_cagr) < 2 and abs(e_vs_o_dd) < 5:
        print("  -> ENHANCED matches ORIGINAL closely. Use it — zero external data needed!")
    elif e_vs_o_cagr >= 0 and e_vs_o_dd >= 0:
        print("  -> ENHANCED is BETTER than ORIGINAL. Use it!")
    elif e_vs_o_cagr >= -2:
        print("  -> ENHANCED is close enough. Small tradeoff for zero API dependency.")
    else:
        print("  -> ORIGINAL is noticeably better. Consider finding VIX data source.")
    print()


if __name__ == "__main__":
    main()