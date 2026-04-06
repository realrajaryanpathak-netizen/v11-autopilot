"""Data layer — yfinance with batching + cache fallback."""
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

def download_prices(tickers=None, period="2y"):
    """Try yfinance (single call first, then batch if fails), cache as final fallback."""
    import yfinance as yf
    from config import SAFE_HAVENS, SIGNAL_TICKERS

    if tickers is None:
        tickers = get_nifty200_tickers()
    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))
    total = len(all_tickers)

    

    # Attempt 2: batch download (5 at a time, 15s delay)
    BATCH = 5
    DELAY = 15
    all_dfs = []
    failed = []
    total_batches = (total + BATCH - 1) // BATCH
    log.info(f"yfinance batch mode: {total} tickers, {total_batches} batches, ~{total_batches * DELAY // 60} min...")

    for i in range(0, total, BATCH):
        batch = all_tickers[i:i+BATCH]
        batch_num = i // BATCH + 1
        success = False

        for attempt in range(3):
            try:
                data = yf.download(batch, period=period, auto_adjust=True,
                                   threads=False, progress=False)
                if data.empty:
                    raise ValueError("Empty result")
                if len(batch) == 1:
                    df = pd.DataFrame(data['Close'])
                    df.columns = batch
                elif isinstance(data.columns, pd.MultiIndex):
                    df = data['Close']
                else:
                    df = pd.DataFrame(data['Close'])
                if not df.empty:
                    all_dfs.append(df)
                    log.info(f"  [{batch_num}/{total_batches}] {[t.replace('.NS','')[:10] for t in batch]}")
                    success = True
                    break
            except Exception as e:
                wait = DELAY * (attempt + 1)
                log.warning(f"  [{batch_num}] attempt {attempt+1} failed: {str(e)[:60]}. Wait {wait}s")
                time.sleep(wait)

        if not success:
            failed.extend(batch)

        if i + BATCH < total:
            time.sleep(DELAY)

    if all_dfs:
        prices = pd.concat(all_dfs, axis=1)
        prices = prices.loc[:, ~prices.columns.duplicated()].sort_index().ffill()
        prices = prices.dropna(axis=1, how='all')
        log.info(f"✅ Batch done: {len(prices.columns)}/{total} tickers, {len(prices)} days")
        if failed:
            log.warning(f"Failed ({len(failed)}): {failed[:10]}...")
        prices.to_csv(CACHE_FILE)
        return prices, tickers

    # Attempt 3: read cache
    if os.path.exists(CACHE_FILE):
        log.info("Using cached prices from prices_cache.csv")
        prices = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        log.info(f"✅ Cache: {len(prices.columns)} tickers, {len(prices)} days")
        return prices, tickers

    log.error("All methods failed. Run update_prices.py locally first.")
    return pd.DataFrame(), tickers
