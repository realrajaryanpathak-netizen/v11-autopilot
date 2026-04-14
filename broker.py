"""Angel One broker integration — orders + historical data (NO yfinance)."""
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from config import *

log = logging.getLogger(__name__)


class AngelBroker:
    def __init__(self):
        self.api = None
        self.logged_in = False
        self.symbols = {}  # ticker -> {token, symbol, exchange}

    def login(self):
        if not all([ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET]):
            log.error("Missing Angel One credentials")
            return False
        try:
            from SmartApi import SmartConnect
            import pyotp
            self.api = SmartConnect(api_key=ANGEL_API_KEY, timeout=30)
            totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
            data = self.api.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
            if data.get('status'):
                self.logged_in = True
                self._load_symbols()
                log.info(f"Angel One login OK: {ANGEL_CLIENT_ID}")
                return True
            log.error(f"Login failed: {data.get('message')}")
        except Exception as e:
            log.error(f"Login error: {e}")
        return False

    def _load_symbols(self):
        """Load NSE symbol master list from Angel One."""
        try:
            import requests
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            for inst in requests.get(url, timeout=30).json():
                if inst.get('exch_seg') == 'NSE' and inst.get('symbol'):
                    sym = inst['symbol'].replace('-EQ', '')
                    self.symbols[f"{sym}.NS"] = {
                        'token': inst['token'],
                        'symbol': inst['symbol'],
                        'exchange': 'NSE',
                    }
            # Add index tokens from config
            for name, info in INDEX_TOKENS.items():
                self.symbols[name] = info

            log.info(f"Loaded {len(self.symbols)} symbols (incl. indices)")
        except Exception as e:
            log.error(f"Symbol load error: {e}")

    def get_historical(self, ticker, days=500):
        """Fetch historical daily candles for a single ticker."""
        if not self.logged_in:
            return None

        # Check if it's an index or regular stock
        if ticker in INDEX_TOKENS:
            info = INDEX_TOKENS[ticker]
        elif ticker in self.symbols:
            info = self.symbols[ticker]
        else:
            return None

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        params = {
            "exchange": info.get("exchange", "NSE"),
            "symboltoken": info['token'],
            "interval": "ONE_DAY",
            "fromdate": from_date.strftime("%Y-%m-%d 09:15"),
            "todate": to_date.strftime("%Y-%m-%d 15:30"),
        }

        for attempt in range(3):
            try:
                result = self.api.getCandleData(params)

                if result and result.get('status') and result.get('data'):
                    df = pd.DataFrame(
                        result['data'],
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                    return df['close']
                else:
                    msg = result.get('message', '?') if result else 'No response'
                    log.warning(f"No data for {ticker}: {msg}")
                    return None

            except Exception as e:
                if attempt < 2:
                    wait = 5 * (attempt + 1)
                    log.warning(f"Timeout for {ticker}, retry {attempt+1} in {wait}s...")
                    time.sleep(wait)
                else:
                    log.warning(f"Failed {ticker} after 3 attempts: {e}")
                    return None

    def get_bulk_historical(self, tickers, days=500):
        """
        Fetch historical data for multiple tickers.
        Returns DataFrame with Close prices (columns = tickers).
        ~3 requests/sec rate limit.
        """
        if not self.logged_in:
            log.error("Not logged in — cannot fetch data")
            return None

        all_series = {}
        failed = []
        total = len(tickers)

        log.info(f"Fetching {total} tickers from Angel One (~{total // 3}s estimated)...")

        for i, ticker in enumerate(tickers):
            series = self.get_historical(ticker, days=days)
            if series is not None and len(series) > 0:
                all_series[ticker] = series
            else:
                failed.append(ticker)

            # Rate limit: ~3 requests/sec
            if (i + 1) % 3 == 0:
                time.sleep(1)

            # Progress log every 30 tickers
            if (i + 1) % 30 == 0:
                log.info(f"  Progress: {i+1}/{total} ({len(all_series)} ok, {len(failed)} failed)")

        if not all_series:
            log.error("No data fetched from Angel One")
            return None

        prices = pd.DataFrame(all_series)
        prices = prices.sort_index().ffill()
        prices = prices.dropna(axis=1, how='all')

        log.info(f"✅ Angel One done: {len(prices.columns)}/{total} tickers, {len(prices)} days")
        if failed:
            log.warning(f"Failed ({len(failed)}): {failed[:15]}...")
        return prices

    def place_order(self, ticker, qty, side):
        if not self.logged_in or ticker not in self.symbols:
            log.error(f"Cannot order: {ticker}")
            return None
        info = self.symbols[ticker]
        try:
            result = self.api.placeOrder({
                "variety": "NORMAL",
                "tradingsymbol": info['symbol'],
                "symboltoken": info['token'],
                "transactiontype": side,
                "exchange": "NSE",
                "ordertype": "MARKET",
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": qty,
                "price": "0",
            })
            log.info(f"Order: {side} {qty} {ticker} → {result}")
            return result
        except Exception as e:
            log.error(f"Order error: {e}")
            return None