# V11 AutoPilot — Acceleration Momentum Trading System

**31.4% CAGR | 1.22 Sharpe | -29.7% Max DD | Fully Autonomous**

## What It Does
- **Daily 9:30 AM**: Crash check. If VIX spikes + breadth collapses → exits to gold (GOLDBEES)
- **Monthly 1st**: Rebalances. Downloads Nifty 200 prices, picks top 4 accelerating stocks, trades
- **Always**: Web dashboard showing portfolio, holdings, signals, trades
- **Telegram**: Alerts for every rebalance, crash exit, and daily status

## Architecture
```
config.py       ─ Settings, env vars, universe
strategy.py     ─ V11 acceleration momentum engine
data.py         ─ yfinance + Nifty 200 universe
portfolio.py    ─ State management, trade execution
broker.py       ─ Angel One SmartAPI
alerts.py       ─ Telegram notifications
app.py          ─ Flask dashboard + APScheduler
```

## Deploy on Railway (10 minutes)

### Step 1: Telegram Bot (2 min)
```
Telegram → @BotFather → /newbot → copy TOKEN
Telegram → @userinfobot → /start → copy CHAT_ID
```

### Step 2: Push to GitHub
```bash
# Extract the tar.gz
tar xzf v11_deploy.tar.gz
cd v11_deploy

# Init git
git init
git add .
git commit -m "V11 autopilot"

# Push
git remote add origin https://github.com/YOUR_USER/v11-autopilot.git
git push -u origin main
```

### Step 3: Deploy on Railway
```
1. Go to https://railway.app
2. New Project → Deploy from GitHub Repo → select your repo
3. Go to Variables tab, add:

   TELEGRAM_BOT_TOKEN = your_token_from_botfather
   TELEGRAM_CHAT_ID   = your_chat_id
   TRADE_MODE         = paper
   INITIAL_CAPITAL    = 1000000
   PORT               = 8080

4. Deploy → Railway gives you a URL like:
   https://v11-autopilot-production.up.railway.app
```

### Step 4: Open Dashboard
Visit your Railway URL. You'll see the portfolio dashboard.
Click "Rebalance Now" to trigger the first run.

## Switch to Real Money (Angel One)

### Get Angel One API
```
1. Open account: https://www.angelone.in (free)
2. SmartAPI: https://smartapi.angelone.in → Create App → get API Key
3. Enable TOTP → save secret key
```

### Add to Railway Variables
```
ANGEL_API_KEY       = your_api_key
ANGEL_CLIENT_ID     = your_client_id (e.g., D12345)
ANGEL_PASSWORD      = your_password
ANGEL_TOTP_SECRET   = your_totp_secret
TRADE_MODE          = real          ← change this from "paper" to "real"
```

Redeploy. It now places real orders on Angel One.

## Dashboard Features
- **Portfolio value** with return % since inception
- **Current holdings** with weights and bar chart
- **Market regime** (CRASH/CHOPPY/MILD/STRONG) with signals
- **Top 4 picks** with momentum + acceleration scores
- **Recent trades** log
- **Value history** over time
- **Add Funds** button (paper mode: adds to cash balance)
- **Rebalance Now** button (trigger manual rebalance)
- **Crash Check** button (manual crash detection)
- **Reset** button (start over)

## Telegram Alerts You'll Get
```
📅 REBALANCE [PAPER]
Regime: MILD
Value: ₹12,45,000 (+24.5%)

Picks:
  BAJFINANCE.NS: +45% (acc:+12%)
  PERSISTENT.NS: +38% (acc:+8%)
  PFC.NS: +33% (acc:+15%)
  ADANIENT.NS: +29% (acc:+5%)

Trades:
  SELL DEEPAKNTR.NS ×12
  BUY BAJFINANCE.NS ×8
  BUY PFC.NS ×200
```

## Run Locally (optional)
```bash
pip install -r requirements.txt
export TRADE_MODE=paper
export INITIAL_CAPITAL=1000000
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_id
python app.py
# Open http://localhost:8080
```

## Cost
- Railway: $5/month (or free tier 500hrs)
- Angel One API: Free
- yfinance: Free
- Telegram: Free
