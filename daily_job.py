"""
V11 Daily Job — downloads all tickers, saves enriched state for dashboard.
"""
import sys, os, logging
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import *
from data import download_prices, get_nifty200_tickers
from strategy import generate_signals, detect_regime, safe_pick
from portfolio import *
import alerts

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

def main():
    force_rebalance = "--rebalance" in sys.argv
    today = datetime.now()
    is_first = today.day == 1

    log.info(f"V11 Daily Job | {today.strftime('%Y-%m-%d %H:%M')} | Rebalance: {is_first or force_rebalance}")

    universe = get_nifty200_tickers()
    prices, _ = download_prices(universe)

    if prices.empty or len(prices) < 10:
        log.error("No price data — aborting")
        alerts.send("❌ V11 Bot: price download failed. Will retry tomorrow.")
        return

    st = load_state()
    # Ensure buy_prices exists (migration from old state)
    if "buy_prices" not in st:
        st["buy_prices"] = {}
    if "holdings_snapshot" not in st:
        st["holdings_snapshot"] = []

    regime, details = detect_regime(prices)
    st["regime"] = regime
    st["details"] = details
    pv = portfolio_value(st, prices)
    ret = (pv / st["inception_value"] - 1) * 100 if st["inception_value"] > 0 else 0

    log.info(f"PV=₹{pv:,.0f} | Regime={regime} | Return={ret:+.1f}%")

    if is_first or force_rebalance:
        log.info("🔄 Running rebalance...")
        target, regime, picks, details = generate_signals(prices, universe)
        st["regime"] = regime
        st["details"] = details
        st["picks"] = picks
        trades = execute_rebalance(st, target, prices)
        pv = portfolio_value(st, prices)
        ret = (pv / st["inception_value"] - 1) * 100 if st["inception_value"] > 0 else 0
        st["last_rebalance"] = today.strftime("%Y-%m-%d %H:%M")
        st["history"].append({"date": today.strftime("%Y-%m-%d"), "value": round(pv, 2), "regime": regime})
        st["holdings_snapshot"] = snapshot_holdings(st, prices)
        save_state(st)
        tl = load_trades(); tl.extend(trades); save_trades(tl)
        alerts.alert_rebalance(regime, pv, ret, picks, trades, MODE)
        log.info(f"✅ Rebalance done. {len(trades)} trades.")

    elif regime == "CRASH" and st["holdings"]:
        log.info("🚨 CRASH detected — exiting!")
        target = safe_pick(prices, len(prices) - 1)
        trades = execute_rebalance(st, target, prices)
        pv = portfolio_value(st, prices)
        st["history"].append({"date": today.strftime("%Y-%m-%d"), "value": round(pv, 2), "regime": "CRASH_EXIT"})
        st["holdings_snapshot"] = snapshot_holdings(st, prices)
        save_state(st)
        tl = load_trades(); tl.extend(trades); save_trades(tl)
        alerts.alert_crash(regime, details, trades, MODE)

    else:
        # Normal day — update snapshot with fresh prices
        st["holdings_snapshot"] = snapshot_holdings(st, prices)
        st["history"].append({"date": today.strftime("%Y-%m-%d"), "value": round(pv, 2), "regime": regime})
        save_state(st)
        alerts.alert_daily(regime, pv, ret, details, MODE)
        log.info("✅ No action needed.")

if __name__ == "__main__":
    main()