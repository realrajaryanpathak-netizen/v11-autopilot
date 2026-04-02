"""Data layer — yfinance + cache fallback for GitHub Actions."""
import pandas as pd
import numpy as np
import logging
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
    from config import SAFE_HAVENS, SIGNAL_TICKERS

    if tickers is None:
        tickers = get_nifty200_tickers()
    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))

    # Try yfinance
    try:
        import yfinance as yf
        log.info(f"yfinance: {len(all_tickers)} tickers...")
        data = yf.download(all_tickers, period=period, auto_adjust=True,
                           threads=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            prices = data['Close']
        else:
            prices = pd.DataFrame(data['Close'])
        prices = prices.ffill().dropna(axis=1, how='all')

        if len(prices.columns) > 10:
            log.info(f"✅ yfinance: {len(prices.columns)} tickers, {len(prices)} days")
            prices.to_csv(CACHE_FILE)
            return prices, tickers

        log.warning(f"yfinance: only {len(prices.columns)} tickers, checking cache...")
    except Exception as e:
        log.warning(f"yfinance failed: {e}")

    # Fallback: read cache
    if os.path.exists(CACHE_FILE):
        log.info("Using cached prices from prices_cache.csv")
        prices = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        log.info(f"✅ Cache: {len(prices.columns)} tickers, {len(prices)} days")
        return prices, tickers

    log.error("No data: yfinance failed and no cache. Run update_prices.py locally first.")
    return pd.DataFrame(), tickers