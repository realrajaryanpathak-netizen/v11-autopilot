"""Data layer — full Nifty 200, rate-limit safe for GitHub Actions."""
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
        "FEDERALBNK.NS","MANAPPURAM.NS","MPHASIS.NS","ATUL.NS","NATIONALUM.NS",
        "DRREDDY.NS","CIPLA.NS","EICHERMOT.NS","M&M.NS","TECHM.NS",
        "SHRIRAMFIN.NS","CHOLAFIN.NS","SBILIFE.NS","HDFCLIFE.NS","INDIGO.NS",
        "TVSMOTOR.NS","BHARATFORG.NS","OBEROIRLTY.NS","PHOENIXLTD.NS",
        "HAL.NS","BEL.NS","POLYCAB.NS","DIXON.NS","BSE.NS",
    ]

def download_prices(tickers=None, period="2y"):
    """Download prices in tiny batches with long delays — GitHub Actions safe."""
    import yfinance as yf
    from config import SAFE_HAVENS, SIGNAL_TICKERS

    if tickers is None:
        tickers = get_nifty200_tickers()

    all_tickers = list(set(tickers + SAFE_HAVENS + SIGNAL_TICKERS))
    total = len(all_tickers)
    log.info(f"Downloading {total} tickers (batch=5, delay=15s, ~{total//5 * 15 // 60} min)...")

    BATCH = 5
    DELAY = 15
    all_dfs = []
    failed = []

    for i in range(0, total, BATCH):
        batch = all_tickers[i:i+BATCH]
        batch_num = i // BATCH + 1
        total_batches = (total + BATCH - 1) // BATCH
        success = False

        for attempt in range(3):
            try:
                data = yf.download(batch, period=period, auto_adjust=True,
                                   threads=False, progress=False)

                if data.empty:
                    raise ValueError("Empty result")

                if len(batch) == 1:
                    # Single ticker returns Series, not DataFrame
                    df = pd.DataFrame(data['Close'])
                    df.columns = batch
                elif isinstance(data.columns, pd.MultiIndex):
                    df = data['Close']
                else:
                    df = pd.DataFrame(data['Close'])

                if not df.empty:
                    all_dfs.append(df)
                    log.info(f"  [{batch_num}/{total_batches}] {list(df.columns)}")
                    success = True
                    break

            except Exception as e:
                wait = DELAY * (attempt + 1)
                log.warning(f"  [{batch_num}] attempt {attempt+1} failed: {str(e)[:60]}. Wait {wait}s")
                time.sleep(wait)

        if not success:
            failed.extend(batch)

        # Delay between batches
        if i + BATCH < total:
            time.sleep(DELAY)

    if not all_dfs:
        log.error("All downloads failed!")
        return pd.DataFrame(), tickers

    prices = pd.concat(all_dfs, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()].sort_index().ffill()
    prices = prices.dropna(axis=1, how='all')

    log.info(f"✅ Done: {len(prices.columns)}/{total} tickers, {len(prices)} days")
    if failed:
        log.warning(f"Failed ({len(failed)}): {failed[:10]}...")

    return prices, tickers