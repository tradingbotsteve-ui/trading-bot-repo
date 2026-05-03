"""
===================================================
  UNIFIED TRADING BOT — Phase 1 + Phase 2 + Phase 3
  ─────────────────────────────────────────────────
  5 AM  → Full Morning Brief:
           • Your watchlist (Phase 1)
           • Full US + Canada market scan (Phase 2)
           • Options alerts under $20 + call/put signals (Phase 3)

  6 PM  → End-of-Day Recap:
           • Watchlist recap
           • Options education tip of the day

  ─────────────────────────────────────────────────
  PHASE 3 OPTIONS LOGIC (research-backed):
  • BUY CALL when: bullish sentiment + stock near 52W low
                   + RSI oversold signal + earnings catalyst
  • BUY PUT  when: bearish sentiment + stock falling hard
                   + overbought signal + risk alert
  • Only shows options plays estimated under $20 premium
  • Explains WHY for every single recommendation
  ===================================================
"""

import os
import time
import smtplib
import argparse
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
#  CONFIGURATION — set via GitHub Secrets
# ─────────────────────────────────────────────
API_KEY        = os.environ.get("ALPHA_VANTAGE_KEY")
EMAIL_SENDER   = os.environ.get("EMAIL_ADDRESS")
_raw_pw        = os.environ.get("EMAIL_PASSWORD")
EMAIL_PASSWORD = "".join(c for c in _raw_pw if c.isascii() and c not in (" ", "\xa0"))
TO_EMAIL       = os.environ.get("TO_EMAIL", EMAIL_SENDER)

# ─────────────────────────────────────────────
#  YOUR PERSONAL WATCHLIST — edit these tickers
# ─────────────────────────────────────────────
WATCHLIST = [
    "AAPL", "NVDA", "MSFT", "SHOP", "TSLA",
    "AMZN", "GOOGL", "AMD", "META", "RY",
]

# ─────────────────────────────────────────────
#  PHASE 2 UNIVERSE — US + Canadian tickers
# ─────────────────────────────────────────────
US_TICKERS = [
    "AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","CSCO","IBM",
    "ORCL","CRM","ADBE","QCOM","TXN","MU","AMAT","LRCX","KLAC","MRVL",
    "JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","COF",
    "AXP","BLK","SCHW","MCO","ICE",
    "JNJ","PFE","MRK","ABBV","LLY","BMY","AMGN","GILD","BIIB","REGN",
    "CVS","UNH","HUM","CI","MOH",
    "XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC","HES","DVN",
    "WMT","COST","TGT","HD","LOW","MCD","SBUX","NKE","PG","KO",
    "PEP","PM","MO","CL","EL",
    "BA","GE","HON","CAT","DE","MMM","UPS","FDX","LMT","RTX",
    "AMT","PLD","EQIX","O","SPG",
    "F","GM","VALE","RIG","CLF","X","AA","FCX","NEM","GOLD",
    "WBA","KHC","T","VZ","PARA","WBD","IVZ","BEN",
]

CA_TICKERS = [
    "RY","TD","BNS","BMO","CM","MFC","SLF","POW","GWO","FFH",
    "ENB","TRP","CNQ","SU","CVE","IMO","ARX","BTE",
    "SHOP","CNR","CP","WN","L","ATD","MRU","DOL",
    "BCE","RCI-B",
    "NTR","CCO","IVN","ABX","FNV","WPM","AEM","KL",
    "BAM","BIP","BEP","GFL",
]

SECTOR_PE = {
    "tech": 28, "finance": 13, "healthcare": 18, "energy": 12,
    "consumer": 22, "industrial": 20, "utility": 17, "default": 20,
}

def get_sector(ticker):
    tech    = ["AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","CSCO",
               "IBM","ORCL","CRM","ADBE","QCOM","TXN","MU","SHOP","MRVL","AMAT"]
    finance = ["JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","COF","AXP",
               "BLK","SCHW","RY","TD","BNS","BMO","CM","MFC","SLF","POW","GWO","FFH"]
    health  = ["JNJ","PFE","MRK","ABBV","LLY","BMY","AMGN","GILD","BIIB","REGN","CVS","UNH"]
    energy  = ["XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC","ENB","TRP","CNQ","SU","CVE"]
    if ticker in tech:    return "tech"
    if ticker in finance: return "finance"
    if ticker in health:  return "healthcare"
    if ticker in energy:  return "energy"
    return "default"

# ─────────────────────────────────────────────
#  API HELPERS
# ─────────────────────────────────────────────
BASE = "https://www.alphavantage.co/query"

def av_get(params, pause=13):
    params["apikey"] = API_KEY
    try:
        r    = requests.get(BASE, params=params, timeout=15)
        data = r.json()
        time.sleep(pause)
        return data
    except Exception as e:
        print(f"  API error: {e}")
        time.sleep(pause)
        return {}

def get_overview(ticker):
    return av_get({"function": "OVERVIEW", "symbol": ticker})

def get_quote(ticker):
    data = av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    return data.get("Global Quote", {})

def get_news(ticker):
    data = av_get({"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": "5"})
    return data.get("feed", [])

def get_earnings_calendar():
    try:
        params = {"function": "EARNINGS_CALENDAR", "horizon": "3month", "apikey": API_KEY}
        r      = requests.get(BASE, params=params, timeout=15)
        lines  = r.text.strip().split("\n")
        result = {}
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) >= 3:
                result[parts[0].strip()] = parts[2].strip()
        time.sleep(13)
        return result
    except:
        return {}

# ─────────────────────────────────────────────
#  UNDERVALUED SCORING ENGINE
# ─────────────────────────────────────────────
def score_undervalue(overview, quote):
    score   = 0
    details = {}

    def sf(val):
        try: return float(val)
        except: return None

    ticker  = overview.get("Symbol", "")
    sect_pe = SECTOR_PE.get(get_sector(ticker), 20)

    # P/E — 25 pts
    pe = sf(overview.get("PERatio"))
    if pe and pe > 0:
        pts = 25 if pe < sect_pe*0.5 else 20 if pe < sect_pe*0.7 else 14 if pe < sect_pe*0.85 else 8 if pe < sect_pe else 0
        score += pts
        details["P/E"] = f"{pe:.1f} (sector avg {sect_pe}) → +{pts}pts"
    else:
        details["P/E"] = "N/A"

    # P/B — 20 pts
    pb = sf(overview.get("PriceToBookRatio"))
    if pb and pb > 0:
        pts = 20 if pb < 1.0 else 14 if pb < 1.5 else 7 if pb < 2.5 else 2 if pb < 4.0 else 0
        score += pts
        details["P/B"] = f"{pb:.2f} → +{pts}pts"
    else:
        details["P/B"] = "N/A"

    # Debt/Equity — 15 pts
    de = sf(overview.get("DebtToEquityRatio"))
    if de is not None:
        pts = 15 if de < 0.3 else 11 if de < 0.6 else 7 if de < 1.0 else 3 if de < 1.5 else 0
        score += pts
        details["Debt/Equity"] = f"{de:.2f} → +{pts}pts"
    else:
        details["Debt/Equity"] = "N/A"

    # 52-week position — 15 pts
    try:
        low   = sf(overview.get("52WeekLow"))
        high  = sf(overview.get("52WeekHigh"))
        price = sf(quote.get("05. price"))
        if low and high and price and high > low:
            pct = (price - low) / (high - low)
            pts = 15 if pct < 0.15 else 11 if pct < 0.30 else 6 if pct < 0.50 else 2 if pct < 0.70 else 0
            score += pts
            details["52W Position"] = f"{pct*100:.0f}% from low → +{pts}pts"
    except:
        details["52W Position"] = "N/A"

    # Analyst upside — 15 pts
    target = sf(overview.get("AnalystTargetPrice"))
    price2 = sf(quote.get("05. price"))
    if target and price2 and price2 > 0:
        upside = (target - price2) / price2 * 100
        pts = 15 if upside > 40 else 11 if upside > 25 else 7 if upside > 15 else 3 if upside > 5 else 0
        score += pts
        details["Analyst Upside"] = f"+{upside:.1f}% → +{pts}pts"
    else:
        details["Analyst Upside"] = "N/A"

    # Dividend — 10 pts
    div_yield = sf(overview.get("DividendYield"))
    payout    = sf(overview.get("PayoutRatio"))
    if div_yield and div_yield > 0:
        dy = div_yield * 100
        pts = 10 if dy > 4 and (payout is None or payout < 0.6) else 6 if dy > 2 else 3
        score += pts
        po  = f", payout {payout*100:.0f}%" if payout else ""
        details["Dividend"] = f"{dy:.1f}%{po} → +{pts}pts"
    else:
        details["Dividend"] = "None"

    return min(score, 100), details

# ─────────────────────────────────────────────
#  PHASE 3 — OPTIONS SIGNAL ENGINE
# ─────────────────────────────────────────────
def options_signal(overview, quote, news_items, earnings_date=None):
    """
    Generates a CALL / PUT / HOLD signal based on:
    - 52-week position  - Analyst upside
    - News sentiment    - Today's price change
    - Earnings proximity (catalyst warning)
    """
    def sf(val):
        try: return float(val)
        except: return None

    bullish, bearish = [], []

    # 1. 52-week position
    try:
        low   = sf(overview.get("52WeekLow"))
        high  = sf(overview.get("52WeekHigh"))
        price = sf(quote.get("05. price"))
        if low and high and price and high > low:
            pct = (price - low) / (high - low)
            if pct < 0.25:
                bullish.append(f"Near 52-week LOW ({pct*100:.0f}% from bottom) — potential bounce")
            elif pct > 0.80:
                bearish.append(f"Near 52-week HIGH ({pct*100:.0f}% from low) — may pull back")
    except: pass

    # 2. Analyst target
    target = sf(overview.get("AnalystTargetPrice"))
    price2 = sf(quote.get("05. price"))
    if target and price2 and price2 > 0:
        upside = (target - price2) / price2 * 100
        if upside > 20:
            bullish.append(f"Analysts see +{upside:.1f}% upside to ${target:.2f}")
        elif upside < -10:
            bearish.append(f"Stock is {abs(upside):.1f}% above analyst target — overvalued")

    # 3. News sentiment
    net = sum(
        1 if "bullish" in n.get("overall_sentiment_label","").lower() or
             "positive" in n.get("overall_sentiment_label","").lower()
        else -1 if "bearish" in n.get("overall_sentiment_label","").lower() or
                   "negative" in n.get("overall_sentiment_label","").lower()
        else 0
        for n in news_items
    )
    if net >= 2:
        bullish.append(f"Strongly POSITIVE news sentiment ({net} bullish headlines)")
    elif net <= -2:
        bearish.append(f"Strongly NEGATIVE news sentiment ({net} bearish headlines)")

    # 4. Today's move
    try:
        chg = sf(quote.get("10. change percent", "0").replace("%", ""))
        if chg and chg > 3:
            bullish.append(f"Strong momentum today (+{chg:.1f}%)")
        elif chg and chg < -3:
            bearish.append(f"Falling hard today ({chg:.1f}%) — put opportunity or avoid")
    except: pass

    # 5. Earnings catalyst
    if earnings_date:
        try:
            ed   = datetime.strptime(earnings_date, "%Y-%m-%d").date()
            days = (ed - datetime.now().date()).days
            if 1 <= days <= 7:
                bullish.append(f"Earnings in {days}d — volatility catalyst coming")
                bearish.append(f"⚠️ Earnings risk — option premiums will be HIGH near earnings")
        except: pass

    # Decide
    b, c = len(bullish), len(bearish)
    if b >= 2 and b > c:
        signal      = "CALL 📈"
        confidence  = "High" if b >= 3 else "Medium"
        reasons     = bullish
        explanation = (
            "A <strong>CALL</strong> lets you profit if the stock goes UP. "
            "You pay a premium (the option price) for the right to buy shares at today's "
            "price later. If the stock rises, your call gains value fast. "
            "If it falls, you only lose the premium — nothing more."
        )
    elif c >= 2 and c > b:
        signal      = "PUT 📉"
        confidence  = "High" if c >= 3 else "Medium"
        reasons     = bearish
        explanation = (
            "A <strong>PUT</strong> lets you profit if the stock goes DOWN. "
            "You pay a premium for the right to sell shares at today's price later. "
            "If the stock drops, your put gains value. "
            "If it rises, you only lose the premium you paid."
        )
    else:
        signal      = "HOLD / WATCH ⏸️"
        confidence  = "Low"
        reasons     = bullish + bearish
        explanation = (
            "Mixed signals — no clear call or put setup right now. "
            "Watch for a clearer trend before buying any option."
        )

    # Estimated premium
    pv = sf(quote.get("05. price")) or 0
    if pv < 30:
        premium_est = "~$0.50–$3 per contract ($50–$300 total) ✅ Under $20 target"
        expiry_tip  = "Look for 2–4 week expiry"
    elif pv < 100:
        premium_est = "~$1–$8 per contract ($100–$800 total) ✅ Can find under $20"
        expiry_tip  = "Look for 3–5 week expiry to reduce time decay"
    elif pv < 300:
        premium_est = "~$3–$15 per contract ($300–$1,500 total) — shop carefully for under $20"
        expiry_tip  = "Buy slightly in-the-money, 4–6 week expiry"
    else:
        premium_est = "⚠️ Premium likely over $20 for this stock — expensive for options"
        expiry_tip  = "Consider a cheaper stock, or wait for a dip in share price"

    return {
        "signal": signal, "confidence": confidence,
        "reasons": reasons, "explanation": explanation,
        "premium_est": premium_est, "expiry_tip": expiry_tip,
    }

def options_card_html(ticker, price, sig):
    s   = sig["signal"]
    bc  = "#27ae60" if "CALL" in s else "#e74c3c" if "PUT" in s else "#95a5a6"
    bg  = "#eafaf1" if "CALL" in s else "#fef9f9" if "PUT" in s else "#f8f9fa"
    try:  pd = f"${float(price):.2f}"
    except: pd = f"${price}"

    reasons_html = "".join(
        f"<li style='margin:3px 0;font-size:12px;color:#444;'>✔ {r}</li>"
        for r in sig["reasons"]
    )

    return f"""
    <div style="border:2px solid {bc};border-radius:10px;margin-bottom:16px;overflow:hidden;">
      <div style="background:{bg};padding:12px 16px;border-bottom:1px solid {bc};">
        <span style="font-size:18px;font-weight:bold;">{ticker}</span>
        <span style="font-size:14px;color:#666;margin-left:8px;">{pd}</span>
        <span style="float:right;background:{bc};color:white;padding:3px 12px;
                     border-radius:12px;font-size:13px;font-weight:bold;">{s}</span>
      </div>
      <div style="padding:14px 16px;">
        <div style="font-size:12px;color:{bc};font-weight:bold;margin-bottom:6px;">
          Confidence: {sig['confidence']}
        </div>
        <div style="font-size:12px;font-weight:bold;color:#333;margin-bottom:4px;">Why this signal:</div>
        <ul style="margin:0 0 10px;padding-left:18px;">{reasons_html}</ul>
        <div style="background:#f8f9fa;border-radius:6px;padding:10px;
                    font-size:12px;color:#555;margin-bottom:10px;">
          <strong>💡 What this means:</strong><br>{sig['explanation']}
        </div>
        <div style="font-size:12px;margin-bottom:4px;">
          💰 <strong>Estimated premium:</strong> {sig['premium_est']}
        </div>
        <div style="font-size:12px;color:#666;">
          📅 <strong>Expiry tip:</strong> {sig['expiry_tip']}
        </div>
        <div style="margin-top:10px;font-size:11px;color:#e74c3c;">
          ⚠️ Options can expire worthless. Never risk more than you can afford to lose.
          Educational only — not financial advice.
        </div>
      </div>
    </div>"""

# ─────────────────────────────────────────────
#  OPTIONS EDUCATION — ROTATING DAILY TIPS
# ─────────────────────────────────────────────
OPTIONS_TIPS = [
    {
        "title": "What is a Call Option?",
        "body": (
            "A <strong>call option</strong> gives you the RIGHT (not obligation) to BUY "
            "a stock at a fixed price (the strike) before expiry.<br><br>"
            "<strong>Example:</strong> AAPL is at $180. You buy a $185 call for $2 "
            "(= $200 per contract). If AAPL hits $195, your call is worth ~$10 — a 5x gain. "
            "If AAPL stays below $185, you lose your $200. That's your max loss."
        ),
    },
    {
        "title": "What is a Put Option?",
        "body": (
            "A <strong>put option</strong> gives you the RIGHT to SELL at the strike price "
            "even if the stock has crashed below it.<br><br>"
            "<strong>Example:</strong> TSLA at $250. You buy a $245 put for $3 ($300 total). "
            "If TSLA crashes to $210, your put is worth ~$35 — over 10x. "
            "If TSLA goes UP, you lose your $300. That's it."
        ),
    },
    {
        "title": "Time Decay — The Biggest Enemy of Option Buyers",
        "body": (
            "Every option loses value every day just from time passing — this is called "
            "<strong>theta decay</strong>. Options lose value fastest in the last 2 weeks.<br><br>"
            "<strong>Rule for beginners:</strong> Never buy options expiring in under 2 weeks "
            "unless you're very confident the move is happening immediately. "
            "Give yourself 3–6 weeks for the trade to work."
        ),
    },
    {
        "title": "Strike Price — In the Money vs Out of the Money",
        "body": (
            "<strong>In-the-money (ITM):</strong> Option already has real value. "
            "More expensive but safer.<br>"
            "<strong>Out-of-the-money (OTM):</strong> Only has hope value. "
            "Very cheap but expires worthless most of the time.<br><br>"
            "<strong>Beginner rule:</strong> Start with slightly ITM or at-the-money options. "
            "The $0.50 OTM lottery tickets sound exciting but are how most beginners lose money."
        ),
    },
    {
        "title": "The 3 Things That Move an Option's Price",
        "body": (
            "1. <strong>Stock price movement</strong> — bigger move = bigger gain/loss.<br>"
            "2. <strong>Time decay (theta)</strong> — loses value every single day.<br>"
            "3. <strong>Implied volatility (IV)</strong> — buy when IV is LOW "
            "(cheap), not when everyone is panicking (IV is high and overpriced).<br><br>"
            "<strong>Key insight:</strong> You can be right about direction and still lose money "
            "if time decay kills your option before the stock moves."
        ),
    },
    {
        "title": "When to Buy CALL vs PUT — Simple Rules",
        "body": (
            "<strong>Buy a CALL when:</strong><br>"
            "• Stock trending up or near 52-week low<br>"
            "• Positive earnings/news catalyst coming<br>"
            "• Analysts raised price targets recently<br><br>"
            "<strong>Buy a PUT when:</strong><br>"
            "• Stock near 52-week high or overvalued<br>"
            "• Bad earnings, macro risk, or sector rotation<br>"
            "• You own the stock and want downside protection"
        ),
    },
    {
        "title": "Always Check Volume + Open Interest Before Buying",
        "body": (
            "Two numbers on every options chain:<br>"
            "<strong>Volume:</strong> Contracts traded today. Higher = more liquid.<br>"
            "<strong>Open Interest:</strong> Total open contracts. Higher = easier to exit.<br><br>"
            "<strong>Rule:</strong> Only buy options with Volume &gt; 100 and "
            "Open Interest &gt; 500. Low liquidity options have huge bid/ask spreads — "
            "you lose money the moment you buy because the spread eats your premium."
        ),
    },
]

def get_tip_of_day():
    return OPTIONS_TIPS[datetime.now().weekday() % len(OPTIONS_TIPS)]

# ─────────────────────────────────────────────
#  SENTIMENT HELPERS
# ─────────────────────────────────────────────
def score_sentiment(label):
    label = label.lower()
    if "bullish" in label or "positive" in label: return 1
    if "bearish" in label or "negative" in label: return -1
    return 0

def sentiment_emoji(s):
    return "🟢" if s > 0 else "🔴" if s < 0 else "⚪"

# ─────────────────────────────────────────────
#  HTML EMAIL BUILDER
# ─────────────────────────────────────────────
def build_email_html(title, sections):
    today = datetime.now().strftime("%A, %B %d, %Y")
    body  = "\n".join(f"""
      <div style="margin-bottom:28px;">
        <h2 style="color:#1a1a2e;border-bottom:2px solid #4CAF50;
                   padding-bottom:6px;font-size:18px;">{h}</h2>
        {c}
      </div>""" for h, c in sections)

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f6f9;margin:0;padding:20px;">
  <div style="max-width:700px;margin:auto;background:white;border-radius:10px;
              overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                color:white;padding:24px 28px;">
      <h1 style="margin:0;font-size:22px;">📊 {title}</h1>
      <p style="margin:6px 0 0;opacity:0.75;font-size:13px;">{today}</p>
      <p style="margin:4px 0 0;opacity:0.6;font-size:11px;">
        ⚠️ Educational only — not financial advice. Always verify before trading.
      </p>
    </div>
    <div style="padding:24px 28px;">{body}</div>
    <div style="background:#f0f0f0;padding:14px 28px;font-size:11px;
                color:#888;text-align:center;">
      Your Trading Bot · Phase 1 + 2 + 3 Active · Data via Alpha Vantage
    </div>
  </div>
</body></html>"""

def stock_card_html(ticker, price, change_pct, pe, pb, w52low, w52high,
                     earn_date, earn_alert, news, uv_score=None,
                     uv_details=None, target=None):
    # 52-week bar
    bar = ""
    try:
        lo, hi, p = float(w52low), float(w52high), float(price)
        if hi > lo:
            pct   = max(0, min(100, (p - lo) / (hi - lo) * 100))
            color = "#e74c3c" if pct > 70 else "#f39c12" if pct > 40 else "#27ae60"
            bar   = f"""<div style="margin:8px 0 4px;font-size:11px;color:#666;">
              52W: ${lo:.2f}
              <span style="display:inline-block;width:120px;height:8px;background:#ddd;
                border-radius:4px;vertical-align:middle;position:relative;margin:0 4px;">
                <span style="position:absolute;left:{pct:.0f}%;width:10px;height:10px;
                  background:{color};border-radius:50%;top:-1px;
                  transform:translateX(-50%);"></span>
              </span>
              ${hi:.2f}</div>"""
    except: pass

    # Undervalue badge
    uv = ""
    if uv_score is not None:
        bc2, bl = (("#27ae60","🔥 Deep Value") if uv_score >= 70
                   else ("#2980b9","💎 Undervalued") if uv_score >= 50
                   else ("#f39c12","👀 Watch") if uv_score >= 30
                   else ("#95a5a6","Fair/Overvalued"))
        uv = f"""<div style="margin:6px 0;">
          <span style="background:{bc2};color:white;padding:3px 10px;
            border-radius:12px;font-size:12px;font-weight:bold;">
            {bl} · Score {uv_score}/100</span></div>"""
        if uv_details:
            rows = "".join(
                f"<tr><td style='color:#666;font-size:11px;padding:1px 8px 1px 0;'>{k}</td>"
                f"<td style='font-size:11px;'>{v}</td></tr>"
                for k, v in uv_details.items()
            )
            uv += f"<table style='margin-top:4px;'>{rows}</table>"

    # Earnings
    earn = ""
    if earn_date:
        try:
            ed   = datetime.strptime(earn_date, "%Y-%m-%d").date()
            days = (ed - datetime.now().date()).days
            earn = (
                f"""<div style="background:#fff3cd;border-left:4px solid #f39c12;
                  padding:6px 10px;margin:6px 0;font-size:12px;">
                  ⚠️ <strong>EARNINGS ALERT:</strong> {earn_date} ({days}d away!)</div>"""
                if days <= 1 else
                f"<div style='font-size:11px;color:#888;margin:4px 0;'>📅 Earnings: {earn_date} ({days}d)</div>"
            )
        except:
            earn = f"<div style='font-size:11px;color:#888;'>📅 Earnings: {earn_date}</div>"

    # News
    news_html = ""
    if news:
        items = "".join(
            f"<li style='margin:3px 0;font-size:12px;'>"
            f"{sentiment_emoji(score_sentiment(n.get('overall_sentiment_label','')))} "
            f"<a href='{n.get('url','#')}' style='color:#2980b9;text-decoration:none;'>"
            f"{n.get('title','')[:90]}</a></li>"
            for n in news[:4]
        )
        news_html = f"<ul style='margin:6px 0;padding-left:18px;'>{items}</ul>"

    try:
        chg = float(change_pct)
        cc  = "#27ae60" if chg >= 0 else "#e74c3c"
        cs  = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
    except:
        cc, cs = "#666", "—"

    th = ""
    if target:
        try:
            t  = float(target); p2 = float(price)
            up = (t - p2) / p2 * 100
            uc = "#27ae60" if up > 0 else "#e74c3c"
            th = f"<span style='color:{uc};font-size:11px;margin-left:8px;'>🎯 ${t:.2f} ({up:+.1f}%)</span>"
        except: pass

    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:8px;
                padding:14px 16px;margin-bottom:14px;background:#fafafa;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:17px;font-weight:bold;color:#1a1a2e;">{ticker}</span>
        <span style="font-size:17px;font-weight:bold;">${float(price):.2f}
          <span style="font-size:13px;color:{cc};">{cs}</span>{th}
        </span>
      </div>
      <div style="font-size:11px;color:#888;margin:3px 0;">
        P/E: {pe or 'N/A'} &nbsp;|&nbsp; P/B: {pb or 'N/A'}
      </div>
      {bar}{uv}{earn}{news_html}
    </div>"""

# ─────────────────────────────────────────────
#  SEND EMAIL
# ─────────────────────────────────────────────
def send_email(subject, html_body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not TO_EMAIL:
        print("⚠️  Email credentials missing — skipping send.")
        return
    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Your Trading Bot <{EMAIL_SENDER}>"
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, TO_EMAIL, msg.as_string())
        print(f"✅  Email sent: {subject}")
    except Exception as e:
        print(f"❌  Email failed: {e}")

# ─────────────────────────────────────────────
#  PHASE 1 — WATCHLIST
# ─────────────────────────────────────────────
def run_watchlist(earnings_cal):
    print("\n📋 Running watchlist...")
    cards, opt_cards, alerts = [], [], []

    for ticker in WATCHLIST:
        print(f"  → {ticker}")
        overview = get_overview(ticker)
        quote    = get_quote(ticker)
        news     = get_news(ticker)
        if not quote.get("05. price"): continue

        price  = quote.get("05. price", "0")
        chg    = quote.get("10. change percent", "0%").replace("%", "")
        pe     = overview.get("PERatio", "N/A")
        pb     = overview.get("PriceToBookRatio", "N/A")
        lo     = overview.get("52WeekLow", "0")
        hi     = overview.get("52WeekHigh", "0")
        tgt    = overview.get("AnalystTargetPrice")
        ed     = earnings_cal.get(ticker)
        uv, ud = score_undervalue(overview, quote)

        if ed:
            try:
                if (datetime.strptime(ed, "%Y-%m-%d").date() - datetime.now().date()).days <= 1:
                    alerts.append(ticker)
            except: pass

        cards.append(stock_card_html(ticker, price, chg, pe, pb, lo, hi,
                                      ed, ticker in alerts, news, uv, ud, tgt))

        sig = options_signal(overview, quote, news, ed)
        if "HOLD" not in sig["signal"]:
            opt_cards.append(options_card_html(ticker, price, sig))

    return "".join(cards), "".join(opt_cards), alerts

# ─────────────────────────────────────────────
#  PHASE 2 — MARKET SCAN
# ─────────────────────────────────────────────
def run_market_scan():
    print("\n🔍 Running full market scan...")
    results     = []
    all_tickers = US_TICKERS + CA_TICKERS

    for i, ticker in enumerate(all_tickers, 1):
        if i % 20 == 0:
            print(f"   {i}/{len(all_tickers)}")
        try:
            overview = get_overview(ticker)
            quote    = get_quote(ticker)
            price    = quote.get("05. price")
            if not price: continue

            chg    = quote.get("10. change percent", "0%").replace("%", "")
            pe     = overview.get("PERatio", "N/A")
            pb     = overview.get("PriceToBookRatio", "N/A")
            lo     = overview.get("52WeekLow", "0")
            hi     = overview.get("52WeekHigh", "0")
            tgt    = overview.get("AnalystTargetPrice")
            uv, ud = score_undervalue(overview, quote)
            try: cf = float(chg)
            except: cf = 0.0

            news = []
            if uv >= 55 or abs(cf) > 3:
                news = get_news(ticker)

            results.append({
                "ticker": ticker, "price": price,
                "change_pct": chg, "chg_float": cf,
                "pe": pe, "pb": pb, "w52low": lo, "w52high": hi,
                "target": tgt, "uv_score": uv, "uv_details": ud,
                "news": news, "is_ca": ticker in CA_TICKERS,
                "overview": overview, "quote": quote,
            })
        except Exception as e:
            print(f"   Error {ticker}: {e}")

    return results

def build_scan_sections(results):
    if not results:
        return [("⚠️ Scan Results", "<p>No data — API may be rate-limited.</p>")]

    by_uv      = sorted(results, key=lambda x: x["uv_score"], reverse=True)
    us_picks   = [r for r in by_uv if not r["is_ca"]][:5]
    ca_picks   = [r for r in by_uv if r["is_ca"]][:5]
    deep_val   = [r for r in by_uv if r["uv_score"] >= 70][:8]
    up_movers  = sorted([r for r in results if r["chg_float"] > 3],
                        key=lambda x: x["chg_float"], reverse=True)[:5]
    risk       = sorted([r for r in results if r["chg_float"] < -3],
                        key=lambda x: x["chg_float"])[:5]

    def cards(lst):
        h = [stock_card_html(r["ticker"], r["price"], r["change_pct"],
                              r["pe"], r["pb"], r["w52low"], r["w52high"],
                              None, False, r["news"],
                              r["uv_score"], r["uv_details"], r["target"])
             for r in lst]
        return "".join(h) if h else "<p style='color:#888;'>None today.</p>"

    # Phase 3 options signals from scan
    opt_scan = []
    for r in (deep_val + up_movers + risk)[:6]:
        sig = options_signal(r["overview"], r["quote"], r["news"])
        if "HOLD" not in sig["signal"]:
            opt_scan.append(options_card_html(r["ticker"], r["price"], sig))

    sections = []
    if deep_val:
        sections.append(("🔥 Deep Value Gems (Score 70+)", cards(deep_val)))
    sections.append(("🇺🇸 Top 5 US Undervalued Picks", cards(us_picks)))
    sections.append(("🇨🇦 Top 5 Canadian Undervalued Picks", cards(ca_picks)))
    if up_movers:
        sections.append(("🚀 Big Upside Movers Today (+3%+)", cards(up_movers)))
    if risk:
        sections.append(("⚠️ Risk Alerts — Falling Hard", cards(risk)))
    if opt_scan:
        sections.append(("🎯 Phase 3 — Options Signals from Market Scan",
                          "".join(opt_scan)))

    sections.append(("📖 Scoring Methodology", """
    <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;
                padding:14px;font-size:12px;">
      <strong>Undervalued Score (0–100):</strong><br><br>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📊 P/E vs Sector Avg</td><td>25 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📚 Price-to-Book (P/B &lt;1 = deep value)</td><td>20 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">💰 Debt-to-Equity (&lt;1.0 preferred)</td><td>15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📉 52-Week Position (near low)</td><td>15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">🎯 Analyst Target Upside</td><td>15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">💵 Dividend + Payout &lt;60%</td><td>10 pts</td></tr>
      </table>
    </div>"""))
    return sections

# ─────────────────────────────────────────────
#  MAIN RUNNERS
# ─────────────────────────────────────────────
def run_morning():
    print("🌅 5 AM Morning Brief (Phase 1 + 2 + 3)...")
    today        = datetime.now().strftime("%b %d")
    earnings_cal = get_earnings_calendar()

    wl_html, opt_wl, alerts = run_watchlist(earnings_cal)
    scan                    = run_market_scan()
    scan_sections           = build_scan_sections(scan)

    tip     = get_tip_of_day()
    tip_html = f"""
    <div style="background:#eaf4fb;border-left:4px solid #2980b9;
                border-radius:8px;padding:14px 16px;font-size:13px;">
      <strong>📚 {tip['title']}</strong><br><br>{tip['body']}
    </div>"""

    alert_tag = f" ⚠️ {len(alerts)} Earnings Alert{'s' if len(alerts)!=1 else ''}!" if alerts else ""
    subject   = f"📊 Morning Brief | {today}{alert_tag} | Watchlist + Market Scan + Options"

    sections = (
        [("📚 Options Lesson of the Day", tip_html),
         ("👀 Your Watchlist", wl_html)]
        + ([("🎯 Options Signals — Your Watchlist", opt_wl)] if opt_wl else [])
        + scan_sections
    )
    send_email(subject, build_email_html(f"Morning Brief — {today}", sections))

def run_eod():
    print("🌆 6 PM End-of-Day Recap (Phase 1 + Options Tip)...")
    today        = datetime.now().strftime("%b %d")
    earnings_cal = get_earnings_calendar()

    wl_html, opt_wl, alerts = run_watchlist(earnings_cal)

    tip      = get_tip_of_day()
    tip_html = f"""
    <div style="background:#eaf4fb;border-left:4px solid #2980b9;
                border-radius:8px;padding:14px 16px;font-size:13px;">
      <strong>📚 Options Tip: {tip['title']}</strong><br><br>{tip['body']}
    </div>"""

    alert_tag = f" ⚠️ Earnings Tomorrow: {', '.join(alerts)}!" if alerts else ""
    subject   = f"📈 End-of-Day Recap | {today}{alert_tag} | How Your Stocks Closed"

    sections = [("📋 Your Watchlist — End of Day", wl_html),
                ("📚 Options Education", tip_html)]
    if opt_wl:
        sections.append(("🎯 Options Signals — End of Day", opt_wl))

    send_email(subject, build_email_html(f"End-of-Day Recap — {today}", sections))

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["morning", "eod"], default="morning")
    args = parser.parse_args()
    run_morning() if args.phase == "morning" else run_eod()
