"""Angel One broker integration."""
import logging, os
from config import *

log = logging.getLogger(__name__)

class AngelBroker:
    def __init__(self):
        self.api = None; self.logged_in = False; self.symbols = {}

    def login(self):
        if not all([ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET]):
            log.error("Missing Angel One credentials"); return False
        try:
            from SmartApi import SmartConnect
            import pyotp
            self.api = SmartConnect(api_key=ANGEL_API_KEY)
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
        try:
            import requests
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            for inst in requests.get(url, timeout=30).json():
                if inst.get('exch_seg')=='NSE' and inst.get('symbol'):
                    sym = inst['symbol'].replace('-EQ','')
                    self.symbols[f"{sym}.NS"] = {
                        'token':inst['token'],'symbol':inst['symbol'],'exchange':'NSE'
                    }
            log.info(f"Loaded {len(self.symbols)} symbols")
        except Exception as e:
            log.error(f"Symbol load error: {e}")

    def place_order(self, ticker, qty, side):
        if not self.logged_in or ticker not in self.symbols:
            log.error(f"Cannot order: {ticker}"); return None
        info = self.symbols[ticker]
        try:
            result = self.api.placeOrder({
                "variety":"NORMAL","tradingsymbol":info['symbol'],
                "symboltoken":info['token'],"transactiontype":side,
                "exchange":"NSE","ordertype":"MARKET",
                "producttype":"DELIVERY","duration":"DAY","quantity":qty,"price":"0"
            })
            log.info(f"Order: {side} {qty} {ticker} → {result}")
            return result
        except Exception as e:
            log.error(f"Order error: {e}"); return None
