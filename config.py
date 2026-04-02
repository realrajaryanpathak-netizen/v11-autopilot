
"""Central configuration — all settings in one place."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # GitHub Actions uses real env vars, no .env needed


# ═══════════════════════════════════════════
# ENVIRONMENT (set these on Railway)
# ═══════════════════════════════════════════
ANGEL_API_KEY     = os.environ.get("ANGEL_API_KEY", "")
ANGEL_CLIENT_ID   = os.environ.get("ANGEL_CLIENT_ID", "")
ANGEL_PASSWORD    = os.environ.get("ANGEL_PASSWORD", "")
ANGEL_TOTP_SECRET = os.environ.get("ANGEL_TOTP_SECRET", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT     = os.environ.get("TELEGRAM_CHAT_ID", "")
PORT              = int(os.environ.get("PORT", 8080))
MODE              = os.environ.get("TRADE_MODE", "paper")  # "paper" or "real"
INITIAL_CAPITAL   = int(os.environ.get("INITIAL_CAPITAL", 1000000))

# ═══════════════════════════════════════════
# STRATEGY PARAMS (V11 — do not change)
# ═══════════════════════════════════════════
LOOKBACK_12M  = 252
LOOKBACK_6M   = 126
LOOKBACK_3M   = 63
LOOKBACK_1M   = 21
SMA_LONG      = 200
VOL_LOOKBACK  = 63
TOP_N         = 4
DD_FILTER     = -0.40
ACCEL_MIN     = -0.10
COST_BPS      = 15
REBAL_THRESH  = 0.03
VIX_HIGH      = 28
VIX_LOW       = 15
RVOL_CRASH    = 0.35
CREDIT_STRESS = 1.45
DD_TRIGGER    = -0.25
DD_SCALE      = 0.50

# ═══════════════════════════════════════════
# UNIVERSE
# ═══════════════════════════════════════════
# For LIVE: we download Nifty 200 dynamically
# For BACKTEST: fixed 61 survivorship-free stocks
BACKTEST_STOCKS = [
    "ADANIENT.NS","BAJFINANCE.NS","HDFCBANK.NS","HINDUNILVR.NS",
    "ICICIBANK.NS","INFY.NS","ITC.NS","LT.NS","MARUTI.NS",
    "RELIANCE.NS","SBIN.NS","SUNPHARMA.NS","TCS.NS","WIPRO.NS",
    "ASIANPAINT.NS","AXISBANK.NS","BHARTIARTL.NS","DIVISLAB.NS",
    "HCLTECH.NS","JSWSTEEL.NS","KOTAKBANK.NS","NESTLEIND.NS",
    "NTPC.NS","ONGC.NS","POWERGRID.NS","TATASTEEL.NS",
    "TITAN.NS","TRENT.NS","ULTRACEMCO.NS",
    "YESBANK.NS","RCOM.NS","JPPOWER.NS","SUZLON.NS","IDEA.NS",
    "PNB.NS","BANKBARODA.NS","BHEL.NS","ZEEL.NS","SAIL.NS",
    "VEDL.NS","HINDALCO.NS","INDUSINDBK.NS","FEDERALBNK.NS",
    "CANBK.NS","PFC.NS","RECLTD.NS","NATIONALUM.NS",
    "ASTRAL.NS","ATUL.NS","COFORGE.NS","DEEPAKNTR.NS",
    "PERSISTENT.NS","PIIND.NS","MUTHOOTFIN.NS","NAUKRI.NS",
    "PHOENIXLTD.NS","MANAPPURAM.NS","MPHASIS.NS","GODREJPROP.NS",
    "IIFL.NS","OBEROIRLTY.NS",
]

SAFE_HAVENS    = ["GOLDBEES.NS"]
SIGNAL_TICKERS = ["^VIX","^INDIAVIX","^NSEI","^NSEBANK","^TNX","^IRX","LQD","JNK"]

# Files
STATE_FILE     = "state.json"
TRADES_FILE    = "trades.json"
