"""
Data layer — Angel One SmartAPI only. No yfinance.

Flow:
1. Load cache from prices_cache.csv (persisted via git commit)
2. If cache is fresh (< 6 hours) → use it (0 API calls)
3. If cache exists but stale → fetch last 10 days from Angel One, merge
4. If no cache → full download from Angel One (~200 tickers, ~70 seconds)
5. Save cache for next run
"""
import pandas as pd
import numpy as np
import logging
import time
import os

log = logging.getLogger(__name__)

CACHE_FILE = "prices_cache.csv"


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


def _load_cache():
    """Load cached prices if they exist."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        prices = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        age_hours = (time.time() - os.path.getmtime(CACHE_FILE)) / 3600
        log.info(f"Cache loaded: {len(prices.columns)} tickers, {len(prices)} days, {age_hours:.1f}h old")
        return prices
    except Exception as e:
        log.warning(f"Cache read error: {e}")
        return None


def _save_cache(prices):
    """Save prices to cache file."""
    try:
        prices.to_csv(CACHE_FILE)
        log.info(f"Cache saved: {len(prices.columns)} tickers, {len(prices)} days")
    except Exception as e:
        log.warning(f"Cache save error: {e}")


def _get_broker():
    """Login to Angel One and return broker instance."""
    from config import ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET

    if not all([ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET]):
        log.error("Angel One credentials not set! Add them as GitHub Secrets.")
        return None

    from broker import AngelBroker
    b = AngelBroker()
    if not b.login():
        log.error("Angel One login failed")
        return None
    return b


def _fetch_full(broker, tickers, days=500):
    """Full download of all tickers from Angel One."""
    log.info(f"Full download: {len(tickers)} tickers, {days} days of history")

    prices = broker.get_bulk_historical(tickers, days=days)
    if prices is None or prices.empty:
        return None

    # Also fetch index data (India VIX, Nifty)
    from config import SIGNAL_TICKERS
    for idx_name in SIGNAL_TICKERS:
        series = broker.get_historical(idx_name, days=days)
        if series is not None and len(series) > 0:
            prices[idx_name] = series
            log.info(f"  Index {idx_name}: {len(series)} days")
        time.sleep(0.5)

    return prices


def _fetch_incremental(broker, cached_prices, tickers):
    """Fetch only last 10 days and merge with cache."""
    log.info("Incremental update: fetching last 10 days...")

    all_series = {}
    failed = []

    # Fetch recent data for all tickers we have in cache
    fetch_list = list(cached_prices.columns)
    # Add any new tickers not in cache
    for t in tickers:
        if t not in fetch_list:
            fetch_list.append(t)

    for i, ticker in enumerate(fetch_list):
        series = broker.get_historical(ticker, days=10)
        if series is not None and len(series) > 0:
            all_series[ticker] = series
        else:
            failed.append(ticker)

        if (i + 1) % 3 == 0:
            time.sleep(1)

        if (i + 1) % 50 == 0:
            log.info(f"  Incremental progress: {i+1}/{len(fetch_list)}")

    if not all_series:
        log.warning("Incremental fetch got nothing — using cache")
        return cached_prices

    fresh = pd.DataFrame(all_series)

    # Merge: old data + new days
    merged = pd.concat([cached_prices, fresh])
    merged = merged[~merged.index.duplicated(keep='last')]
    merged = merged.sort_index().ffill()

    # Keep last 520 trading days (~2 years)
    if len(merged) > 520:
        merged = merged.iloc[-520:]

    log.info(f"✅ Incremental done: {len(merged.columns)} tickers, {len(merged)} days. Failed: {len(failed)}")
    return merged


def download_prices(tickers=None, period="2y"):
    """
    Smart download — Angel One only, with caching.

    1. Fresh cache (< 6h) → use it (0 API calls)
    2. Stale cache → incremental update (~200 small fetches)
    3. No cache → full download (~200 fetches, ~70 seconds)
    4. Everything fails → old cache if available
    """
    from config import SAFE_HAVENS

    if tickers is None:
        tickers = get_nifty200_tickers()

    all_tickers = list(set(tickers + SAFE_HAVENS))

    # ── Step 1: Check cache ──
    cached = _load_cache()

    if cached is not None:
        age_hours = (time.time() - os.path.getmtime(CACHE_FILE)) / 3600

        # Fresh cache → use directly
        if age_hours < 6:
            log.info("Cache is fresh — using directly (0 API calls)")
            return cached, tickers

        # Stale cache → incremental update
        log.info(f"Cache is {age_hours:.0f}h old — doing incremental update")
        broker = _get_broker()
        if broker:
            updated = _fetch_incremental(broker, cached, all_tickers)
            if updated is not None and len(updated.columns) > 20:
                _save_cache(updated)
                return updated, tickers

        # Broker login failed but we have cache — use it anyway
        log.warning("Broker unavailable — using stale cache")
        return cached, tickers

    # ── Step 2: No cache — full download ──
    log.info("No cache — full download from Angel One")
    broker = _get_broker()
    if broker is None:
        log.error("Cannot fetch data: no cache AND broker login failed!")
        return pd.DataFrame(), tickers

    prices = _fetch_full(broker, all_tickers, days=500)
    if prices is not None and len(prices.columns) > 20:
        _save_cache(prices)
        return prices, tickers

    log.error("Full download failed. No data available.")
    return pd.DataFrame(), tickers