"""
Data layer — auto-selects best source:
  - TWELVE_DATA_API_KEY set → Twelve Data (GitHub Actions, no rate limit)
  - No key → yfinance (local PC, Railway, fast)

One codebase. One branch. Works everywhere.
"""
import pandas as pd
import numpy as np
import logging
import time
import os
import requests as req

log = logging.getLogger(__name__)

TWELVE_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")

# ═══════════════════════════════════════════
# UNIVERSE
# ═══════════════════════════════════════════
def get_nifty200_tickers():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        df = pd.read_csv(url)
        tickers = [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
        log.info(f"Loaded {len(tickers)} Nifty 200 tickers from NSE")
        return tickers
    except Exception as e:
        log.warning(f"NSE list failed ({e}), using fallback")

    return [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
        "BHARTIARTL.NS","SBIN.NS","ITC.NS","LT.NS","BAJFINANCE.NS",
        "HINDUNILVR.NS","MARUTI.NS","KOTAKBANK.NS","HCLTECH.NS","AXISBANK.NS",
        "SUNPHARMA.NS","TITAN.NS","ASIANPAINT.NS","WIPRO.NS","NTPC.NS",
        "ONGC.NS","POWERGRID.NS","TATASTEEL.NS","ADANIENT.NS","JSWSTEEL.NS",
        "ULTRACEMCO.NS","NESTLEIND.NS","DIVISLAB.NS","TRENT.NS","BAJAJFINSV.NS",
        "TATAMOTORS.NS","COALINDIA.NS","INDUSINDBK.NS","VEDL.NS","HINDALCO.NS",
        "PNB.NS","BANKBARODA.NS","CANBK.NS","PFC.NS","RECLTD.NS",
        "BHEL.NS","SAIL.NS","MUTHOOTFIN.NS","PERSISTENT.NS","COFORGE.NS",
        "PIIND.NS","ASTRAL.NS","DEEPAKNTR.NS","NAUKRI.NS","GODREJPROP.NS",
        "FEDERALBNK.NS","MANAPPURAM.NS","MPHASIS.NS","ATUL.NS","NATIONALUM.NS",
        "DRREDDY.NS","CIPLA.NS","EICHERMOT.NS","M&M.NS","TECHM.NS",
        "SHRIRAMFIN.NS","CHOLAFIN.NS","SBILIFE.NS","HDFCLIFE.NS","INDIGO.NS",
        "TVSMOTOR.NS","BHARATFORG.NS","OBEROIRLTY.NS","PHOENIXLTD.NS",
        "HAL.NS","BEL.NS","POLYCAB.NS","DIXON.NS","BSE.NS",
    ]

# ═══════════════════════════════════════════
# TWELVE DATA (GitHub Actions)
# ═══════════════════════════════════════════
INDEX_MAP = {
    "^VIX": ("VIX", ""),
    "^NSEI": ("NIFTY 50", "NSE"),
    "^NSEBANK": ("NIFTY BANK", "NSE"),
    "^INDIAVIX": ("INDIA VIX", "NSE"),
    "^TNX": ("TNX", ""),
    "^IRX": ("IRX", ""),
}

def _to_twelve(ticker):
    if ticker in INDEX_MAP:
        return INDEX_MAP[ticker]
    if ticker.endswith('.NS'):
        return (ticker.replace('.NS', ''), 'NSE')
    return (ticker, '')

def _twelve_batch(tickers, outputsize=500):
    results = {}
    for ticker in tickers:
        symbol, exchange = _to_twelve(ticker)
        params = {
            "symbol": symbol, "interval": "1day",
            "outputsize": outputsize, "apikey": TWELVE_KEY, "dp": 2,
        }
        if exchange:
            params["exchange"] = exchange
        try:
            resp = req.get("https://api.twelvedata.com/time_series", params=params, timeout=15)
            data = resp.json()
            if "values" in data:
                df = pd.DataFrame(data["values"])
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime").sort_index()
                results[ticker] = df["close"].astype(float)
            elif data.get("code") == 429:
                log.warning(f"  Rate limited on {ticker}, waiting 65s...")
                time.sleep(65)
                resp = req.get("https://api.twelvedata.com/time_series", params=params, timeout=15)
                data = resp.json()
                if "values" in data:
                    df = pd.DataFrame(data["values"])
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df = df.set_index("datetime").sort_index()
                    results[ticker] = df["close"].astype(float)
            else:
                log.warning(f"  No data: {ticker} → {data.get('message', '?')}")
        except Exception as e:
            log.warning(f"  Error {ticker}: {str(e)[:50]}")
    return pd.DataFrame(results) if results else pd.DataFrame()

def _download_twelve(all_tickers):
    total = len(all_tickers)
    BATCH, DELAY = 8, 62
    total_batches = (total + BATCH - 1) // BATCH
    log.info(f"Twelve Data: {total} tickers, {total_batches} batches, ~{total_batches}min")

    all_dfs = []
    failed = []
    for i in range(0, total, BATCH):
        batch = all_tickers[i:i+BATCH]
        bn = i // BATCH + 1
        log.info(f"  [{bn}/{total_batches}] {[t.replace('.NS','')[:10] for t in batch]}")
        df = _twelve_batch(batch)
        if not df.empty:
            all_dfs.append(df)
        else:
            failed.extend(batch)
        if i + BATCH < total:
            time.sleep(DELAY)

    if not all_dfs:
        return pd.DataFrame()
    prices = pd.concat(all_dfs, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()].sort_index().ffill()
    prices = prices.dropna(axis=1, how='all')
    log.info(f"✅ Twelve Data: {len(prices.columns)}/{total} tickers, {len(prices)} days")
    if failed:
        log.warning(f"  Failed ({len(failed)}): {failed[:8]}...")
    return prices

# ═══════════════════════════════════════════
# YFINANCE (local PC / Railway)
# ═══════════════════════════════════════════
def _download_yfinance(all_tickers, period="2y"):
    import yfinance as yf
    log.info(f"yfinance: {len(all_tickers)} tickers, {period}")
    data = yf.download(all_tickers, period=period, auto_adjust=True,
                       threads=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = pd.DataFrame(data['Close'])
    prices = prices.ffill().dropna(axis=1, how='all')
    log.info(f"✅ yfinance: {len(prices.columns)} tickers, {len(prices)} days")
    return prices

# ═══════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════
def download_prices(tickers=None, period="2y"):
    """Auto-selects Twelve Data or yfinance based on available API key."""
    from config import SAFE_HAVENS, SIGNAL_TICKERS

    if tickers is None:
        tickers = get_nifty200_tickers()
    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))

    # Try yfinance first (fast), fall back to Twelve Data if it fails
    try:
        prices = _download_yfinance(all_tickers, period)
        if len(prices.columns) > 10:
            return prices, tickers
        log.warning("yfinance got too few tickers, trying Twelve Data...")
    except Exception as e:
        log.warning(f"yfinance failed: {e}")

    if TWELVE_KEY:
        log.info("Falling back to Twelve Data API")
        prices = _download_twelve(all_tickers)
    else:
        log.error("Both sources failed and no TWELVE_DATA_API_KEY set")
        prices = pd.DataFrame()

    return prices, tickers


    return prices, tickers