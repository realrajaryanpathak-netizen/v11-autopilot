"""Telegram alerts."""
import logging, requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT

log = logging.getLogger(__name__)

def send(msg, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.info(f"[TG disabled] {msg[:80]}...")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT,"text":msg,"parse_mode":parse_mode},
            timeout=10
        )
    except Exception as e:
        log.warning(f"Telegram error: {e}")

def alert_rebalance(regime, pv, ret, picks, trades, mode):
    picks_str = "\n".join(f"  {p['ticker']}: +{p['momentum']}% (acc:{p['acceleration']}%)" for p in picks[:4])
    trades_str = "\n".join(f"  {t['action']} {t['ticker']} ×{t['shares']}" for t in trades[:6])
    send(
        f"📅 <b>REBALANCE [{mode.upper()}]</b>\n"
        f"Regime: <b>{regime}</b>\n"
        f"Value: <b>₹{pv:,.0f}</b> ({ret:+.1f}%)\n\n"
        f"<b>Picks:</b>\n{picks_str}\n\n"
        f"<b>Trades:</b>\n{trades_str if trades else '  No changes'}"
    )

def alert_crash(regime, details, trades, mode):
    send(
        f"🚨 <b>CRASH EXIT [{mode.upper()}]</b>\n"
        f"Score: {details.get('CrashScore','?')}\n"
        f"VIX: {details.get('VIX','?')} | Breadth: {details.get('Breadth','?')}\n\n"
        + "\n".join(f"  {t['action']} {t['ticker']} ×{t['shares']}" for t in trades)
    )

def alert_daily(regime, pv, ret, details, mode):
    send(
        f"📊 <b>DAILY [{mode.upper()}]</b>\n"
        f"Value: ₹{pv:,.0f} ({ret:+.1f}%)\n"
        f"Regime: {regime} | VIX:{details.get('VIX','?')} | Breadth:{details.get('Breadth','?')}"
    )

def alert_startup(mode):
    send(f"🚀 <b>V11 AutoPilot started</b> [{mode.upper()}]")
