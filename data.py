"""Data layer — downloads prices, manages Nifty 200 universe."""
import pandas as pd
import numpy as np
import logging

log = logging.getLogger(__name__)

def get_nifty200_tickers():
    """Get current Nifty 200 constituents from NSE website."""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        df = pd.read_csv(url)
        tickers = [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
        log.info(f"Loaded {len(tickers)} Nifty 200 tickers from NSE")
        return tickers
    except Exception as e:
        log.warning(f"NSE download failed ({e}), trying backup...")
    
    try:
        url = "https://www1.nseindia.com/content/indices/ind_nifty200list.csv"
        df = pd.read_csv(url)
        tickers = [f"{s.strip()}.NS" for s in df['Symbol'].tolist()]
        return tickers
    except:
        pass
    
    # Hardcoded fallback — top 100 liquid NSE stocks
    log.warning("Using hardcoded fallback universe")
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
        "ZEEL.NS","FEDERALBNK.NS","MANAPPURAM.NS","MPHASIS.NS","ATUL.NS",
        "SBILIFE.NS","HDFCLIFE.NS","BAJAJHLDNG.NS","CHOLAFIN.NS","SHRIRAMFIN.NS",
        "INDIGO.NS","TVSMOTOR.NS","DRREDDY.NS","CIPLA.NS","EICHERMOT.NS",
        "HEROMOTOCO.NS","BPCL.NS","IOC.NS","GAIL.NS","TATAPOWER.NS",
        "M&M.NS","TECHM.NS","LTIM.NS","DABUR.NS","BRITANNIA.NS",
        "APOLLOHOSP.NS","MAXHEALTH.NS","TORNTPHARM.NS","LUPIN.NS","DMART.NS",
        "POLYCAB.NS","DIXON.NS","OBEROIRLTY.NS","PHOENIXLTD.NS","IIFL.NS",
    ]

def download_prices(tickers=None, period="2y"):
    """Download daily prices via yfinance."""
    import yfinance as yf
    from config import SAFE_HAVENS, SIGNAL_TICKERS
    
    if tickers is None:
        tickers = get_nifty200_tickers()
    
    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))
    log.info(f"Downloading {len(all_tickers)} tickers ({period})...")
    
    data = yf.download(all_tickers, period=period, auto_adjust=True,
                       threads=True, progress=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = pd.DataFrame(data['Close'])
    
    prices = prices.ffill().dropna(axis=1, how='all')
    log.info(f"Got {len(prices.columns)} tickers, {len(prices)} days")
    return prices, tickers
