"""Data layer — downloads prices in batches to avoid rate limits."""
import pandas as pd
import numpy as np
import logging
import time

log = logging.getLogger(__name__)

def get_nifty200_tickers():
    """Get current Nifty 200 constituents from NSE."""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        df = pd.read_csv(url)
        tickers = [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
        log.info(f"Loaded {len(tickers)} Nifty 200 tickers from NSE")
        return tickers
    except Exception as e:
        log.warning(f"NSE download failed ({e}), using fallback")
    
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
    ]

def download_prices(tickers=None, period="2y"):
    """Download prices in batches of 20 to avoid rate limits."""
    import yfinance as yf
    from config import SAFE_HAVENS, SIGNAL_TICKERS
    
    if tickers is None:
        tickers = get_nifty200_tickers()
    
    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))
    log.info(f"Downloading {len(all_tickers)} tickers in batches...")
    
    # Download in batches of 20
    BATCH = 20
    all_dfs = []
    
    for i in range(0, len(all_tickers), BATCH):
        batch = all_tickers[i:i+BATCH]
        attempt = 0
        while attempt < 3:
            try:
                data = yf.download(batch, period=period, auto_adjust=True,
                                   threads=True, progress=False)
                if isinstance(data.columns, pd.MultiIndex):
                    df = data['Close']
                elif not data.empty:
                    df = pd.DataFrame(data['Close'])
                else:
                    df = pd.DataFrame()
                
                if not df.empty:
                    all_dfs.append(df)
                    log.info(f"  Batch {i//BATCH+1}: {len(df.columns)} tickers OK")
                break
            except Exception as e:
                attempt += 1
                wait = 5 * attempt
                log.warning(f"  Batch {i//BATCH+1} failed (attempt {attempt}): {e}. Waiting {wait}s...")
                time.sleep(wait)
        
        # Small delay between batches
        if i + BATCH < len(all_tickers):
            time.sleep(2)
    
    if not all_dfs:
        log.error("All downloads failed!")
        return pd.DataFrame(), tickers
    
    prices = pd.concat(all_dfs, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()].sort_index().ffill()
    prices = prices.dropna(axis=1, how='all')
    log.info(f"Got {len(prices.columns)} tickers, {len(prices)} days")
    return prices, tickers