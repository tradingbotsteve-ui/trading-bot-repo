"""
===================================================
  UNIFIED TRADING BOT — Phase 1 + Phase 2
  5 AM  → Full Morning Brief (Watchlist + Market Scan + Undervalued Picks)
  6 PM  → End-of-Day Watchlist Recap
===================================================

Undervalued scoring uses research-backed criteria:
  - P/E ratio vs sector average (low = good)
  - P/B ratio < 1.5 preferred, < 1.0 = deep value
  - Debt/Equity < 1.0 preferred
  - Free Cash Flow Yield > 5% preferred
  - Dividend yield + payout ratio < 60%
  - 52-week position (near low = opportunity)
  - Analyst upside %
"""

import os
import time
import smtplib
import argparse
import requests
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
#  CONFIGURATION — set via GitHub Secrets
# ─────────────────────────────────────────────
API_KEY       = os.environ.get("ALPHA_VANTAGE_KEY", "")
EMAIL_SENDER  = os.environ.get("EMAIL_ADDRESS", "")
_raw_pw       = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD = "".join(c for c in _raw_pw if c.isascii() and c not in (" ", "\xa0"))
TO_EMAIL      = os.environ.get("TO_EMAIL", EMAIL_SENDER)

# ─────────────────────────────────────────────
#  YOUR PERSONAL WATCHLIST — edit these tickers
# ─────────────────────────────────────────────
WATCHLIST = [
    "AAPL", "NVDA", "MSFT", "SHOP", "TSLA",
    "AMZN", "GOOGL", "AMD", "META", "RY",
]

# ─────────────────────────────────────────────
#  PHASE 2 UNIVERSE — US + Canadian tickers
#  ~200 tickers to stay within free API limits
# ─────────────────────────────────────────────
US_TICKERS = [
    # Tech
    "AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","CSCO","IBM",
    "ORCL","CRM","ADBE","QCOM","TXN","MU","AMAT","LRCX","KLAC","MRVL",
    # Finance
    "JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","COF",
    "AXP","BLK","SCHW","MCO","ICE",
    # Healthcare
    "JNJ","PFE","MRK","ABBV","LLY","BMY","AMGN","GILD","BIIB","REGN",
    "CVS","UNH","HUM","CI","MOH",
    # Energy
    "XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC","HES","DVN",
    # Consumer
    "WMT","COST","TGT","HD","LOW","MCD","SBUX","NKE","PG","KO",
    "PEP","PM","MO","CL","EL",
    # Industrials
    "BA","GE","HON","CAT","DE","MMM","UPS","FDX","LMT","RTX",
    # Real Estate / Utilities
    "AMT","PLD","EQIX","O","SPG",
    # Small/Mid Cap Value plays
    "F","GM","VALE","RIG","CLF","X","AA","FCX","NEM","GOLD",
    "WBA","KHC","T","VZ","PARA","WBD","DISH","SIRI","IVZ","BEN",
]

CA_TICKERS = [
    # TSX Blue Chips
    "RY","TD","BNS","BMO","CM","MFC","SLF","POW","GWO","FFH",
    "ENB","TRP","CNQ","SU","CVE","IMO","MEG","ARX","BTE","PEY",
    "SHOP","CNR","CP","WN","L","ATD","MRU","EMP-A","CTC-A","DOL",
    "BCE","T","RCI-B","QBR-B","MBT",
    "NTR","AGU","CCO","IVN","K","ABX","FNV","WPM","AEM","KL",
    "BAM","BIP","BEP","BIPC","GFL",
]

# Sector average P/E benchmarks for scoring
SECTOR_PE = {
    "tech": 28, "finance": 13, "healthcare": 18, "energy": 12,
    "consumer": 22, "industrial": 20, "utility": 17, "default": 20,
}

def get_sector(ticker):
    tech = ["AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","CSCO",
            "IBM","ORCL","CRM","ADBE","QCOM","TXN","MU","SHOP","MRVL","AMAT"]
    finance = ["JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","COF","AXP",
               "BLK","SCHW","RY","TD","BNS","BMO","CM","MFC","SLF","POW","GWO","FFH"]
    health = ["JNJ","PFE","MRK","ABBV","LLY","BMY","AMGN","GILD","BIIB","REGN","CVS","UNH"]
    energy = ["XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC","ENB","TRP","CNQ","SU","CVE"]
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
    """Call Alpha Vantage with rate-limit pause (free = 5/min)."""
    params["apikey"] = API_KEY
    try:
        r = requests.get(BASE, params=params, timeout=15)
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
    """Fetch upcoming earnings for the next 30 days."""
    try:
        params = {"function": "EARNINGS_CALENDAR", "horizon": "3month", "apikey": API_KEY}
        r = requests.get(BASE, params=params, timeout=15)
        lines = r.text.strip().split("\n")
        results = {}
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) >= 3:
                sym, name, date = parts[0], parts[1], parts[2]
                results[sym.strip()] = date.strip()
        time.sleep(13)
        return results
    except:
        return {}

# ─────────────────────────────────────────────
#  UNDERVALUED SCORING ENGINE
#  Based on: P/E, P/B, D/E, FCF yield, dividend,
#            52-week position, analyst upside
# ─────────────────────────────────────────────
def score_undervalue(overview, quote):
    """
    Returns (score 0-100, details_dict).
    Higher score = more undervalued / better value.

    Criteria (research-backed):
    ┌─────────────────────────────────────────────────────┐
    │ P/E vs sector avg     → up to 25 pts                │
    │ P/B ratio             → up to 20 pts                │
    │ Debt/Equity           → up to 15 pts                │
    │ 52-week low proximity → up to 15 pts                │
    │ Analyst target upside → up to 15 pts                │
    │ Dividend + payout     → up to 10 pts                │
    └─────────────────────────────────────────────────────┘
    """
    score = 0
    details = {}

    def safe_float(val):
        try: return float(val)
        except: return None

    ticker  = overview.get("Symbol", "")
    sector  = get_sector(ticker)
    sect_pe = SECTOR_PE.get(sector, 20)

    # 1. P/E ratio (up to 25 pts)
    pe = safe_float(overview.get("PERatio"))
    if pe and pe > 0:
        if pe < sect_pe * 0.5:   pts = 25
        elif pe < sect_pe * 0.7: pts = 20
        elif pe < sect_pe * 0.85:pts = 14
        elif pe < sect_pe:       pts = 8
        else:                    pts = 0
        score += pts
        details["P/E"] = f"{pe:.1f} (sector avg {sect_pe}) → +{pts}pts"
    else:
        details["P/E"] = "N/A"

    # 2. P/B ratio (up to 20 pts)
    pb = safe_float(overview.get("PriceToBookRatio"))
    if pb and pb > 0:
        if pb < 1.0:   pts = 20
        elif pb < 1.5: pts = 14
        elif pb < 2.5: pts = 7
        elif pb < 4.0: pts = 2
        else:          pts = 0
        score += pts
        details["P/B"] = f"{pb:.2f} → +{pts}pts"
    else:
        details["P/B"] = "N/A"

    # 3. Debt/Equity (up to 15 pts)
    de = safe_float(overview.get("DebtToEquityRatio"))
    if de is not None:
        if de < 0.3:   pts = 15
        elif de < 0.6: pts = 11
        elif de < 1.0: pts = 7
        elif de < 1.5: pts = 3
        else:          pts = 0
        score += pts
        details["Debt/Equity"] = f"{de:.2f} → +{pts}pts"
    else:
        details["Debt/Equity"] = "N/A"

    # 4. 52-week position (up to 15 pts)
    try:
        low  = safe_float(overview.get("52WeekLow"))
        high = safe_float(overview.get("52WeekHigh"))
        price= safe_float(quote.get("05. price"))
        if low and high and price and high > low:
            pct = (price - low) / (high - low)  # 0=at low, 1=at high
            if pct < 0.15:   pts = 15
            elif pct < 0.30: pts = 11
            elif pct < 0.50: pts = 6
            elif pct < 0.70: pts = 2
            else:             pts = 0
            score += pts
            details["52W Position"] = f"{pct*100:.0f}% from low → +{pts}pts"
    except:
        details["52W Position"] = "N/A"

    # 5. Analyst price target upside (up to 15 pts)
    target = safe_float(overview.get("AnalystTargetPrice"))
    price2 = safe_float(quote.get("05. price"))
    if target and price2 and price2 > 0:
        upside = (target - price2) / price2 * 100
        if upside > 40:   pts = 15
        elif upside > 25: pts = 11
        elif upside > 15: pts = 7
        elif upside > 5:  pts = 3
        else:             pts = 0
        score += pts
        details["Analyst Upside"] = f"+{upside:.1f}% → +{pts}pts"
    else:
        details["Analyst Upside"] = "N/A"

    # 6. Dividend yield + payout ratio (up to 10 pts)
    div_yield = safe_float(overview.get("DividendYield"))
    payout    = safe_float(overview.get("PayoutRatio"))
    if div_yield and div_yield > 0:
        dy_pct = div_yield * 100
        if dy_pct > 4 and (payout is None or payout < 0.6):  pts = 10
        elif dy_pct > 2:                                       pts = 6
        elif dy_pct > 0:                                       pts = 3
        else:                                                  pts = 0
        score += pts
        pout_str = f", payout {payout*100:.0f}%" if payout else ""
        details["Dividend"] = f"{dy_pct:.1f}%{pout_str} → +{pts}pts"
    else:
        details["Dividend"] = "None"

    return min(score, 100), details

# ─────────────────────────────────────────────
#  SENTIMENT SCORING
# ─────────────────────────────────────────────
def score_sentiment(label):
    label = label.lower()
    if "bullish" in label or "positive" in label: return 1
    if "bearish" in label or "negative" in label: return -1
    return 0

def sentiment_emoji(score):
    if score > 0:  return "🟢"
    if score < 0:  return "🔴"
    return "⚪"

# ─────────────────────────────────────────────
#  HTML EMAIL BUILDER
# ─────────────────────────────────────────────
def build_email_html(title, sections):
    """sections = list of (heading, html_content)"""
    today = datetime.now().strftime("%A, %B %d, %Y")
    body_parts = []
    for heading, content in sections:
        body_parts.append(f"""
        <div style="margin-bottom:28px;">
          <h2 style="color:#1a1a2e;border-bottom:2px solid #4CAF50;
                     padding-bottom:6px;font-size:18px;">{heading}</h2>
          {content}
        </div>""")
    body = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f6f9;
             margin:0;padding:20px;">
  <div style="max-width:700px;margin:auto;background:white;
              border-radius:10px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.1);">
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                color:white;padding:24px 28px;">
      <h1 style="margin:0;font-size:22px;">📊 {title}</h1>
      <p style="margin:6px 0 0;opacity:0.75;font-size:13px;">{today}</p>
      <p style="margin:4px 0 0;opacity:0.6;font-size:11px;">
        ⚠️ Educational only — not financial advice. Always verify before trading.
      </p>
    </div>
    <!-- Body -->
    <div style="padding:24px 28px;">
      {body}
    </div>
    <!-- Footer -->
    <div style="background:#f0f0f0;padding:14px 28px;font-size:11px;
                color:#888;text-align:center;">
      Your Trading Bot · Data via Alpha Vantage · Not financial advice
    </div>
  </div>
</body></html>"""

def stock_card_html(ticker, price, change_pct, pe, pb, week52_low, week52_high,
                     earnings_date, earnings_alert, news_items,
                     uv_score=None, uv_details=None, analyst_target=None):
    """Render a single stock card as HTML."""

    # 52-week bar
    bar_html = ""
    try:
        low, high, p = float(week52_low), float(week52_high), float(price)
        if high > low:
            pct = max(0, min(100, (p - low) / (high - low) * 100))
            color = "#e74c3c" if pct > 70 else ("#f39c12" if pct > 40 else "#27ae60")
            bar_html = f"""
            <div style="margin:8px 0 4px;font-size:11px;color:#666;">
              52W: ${low:.2f} <span style="color:#999;">◄</span>
              <span style="display:inline-block;width:120px;height:8px;
                background:#ddd;border-radius:4px;vertical-align:middle;
                position:relative;margin:0 4px;">
                <span style="position:absolute;left:{pct:.0f}%;
                  width:10px;height:10px;background:{color};
                  border-radius:50%;top:-1px;transform:translateX(-50%);"></span>
              </span>
              <span style="color:#999;">►</span> ${high:.2f}
            </div>"""
    except: pass

    # Undervalue badge
    uv_html = ""
    if uv_score is not None:
        if uv_score >= 70:   badge_color, badge_label = "#27ae60", "🔥 Deep Value"
        elif uv_score >= 50: badge_color, badge_label = "#2980b9", "💎 Undervalued"
        elif uv_score >= 30: badge_color, badge_label = "#f39c12", "👀 Watch"
        else:                badge_color, badge_label = "#95a5a6", "Fair/Overvalued"
        uv_html = f"""
        <div style="margin:6px 0;">
          <span style="background:{badge_color};color:white;padding:3px 10px;
            border-radius:12px;font-size:12px;font-weight:bold;">
            {badge_label} · Score {uv_score}/100
          </span>
        </div>"""
        if uv_details:
            detail_rows = "".join(
                f"<tr><td style='color:#666;font-size:11px;padding:1px 8px 1px 0;'>{k}</td>"
                f"<td style='font-size:11px;'>{v}</td></tr>"
                for k, v in uv_details.items()
            )
            uv_html += f"<table style='margin-top:4px;'>{detail_rows}</table>"

    # Earnings alert
    earn_html = ""
    if earnings_date:
        today = datetime.now().date()
        try:
            ed = datetime.strptime(earnings_date, "%Y-%m-%d").date()
            days_away = (ed - today).days
            if days_away <= 1:
                earn_html = f"""<div style="background:#fff3cd;border-left:4px solid #f39c12;
                  padding:6px 10px;margin:6px 0;font-size:12px;">
                  ⚠️ <strong>EARNINGS ALERT:</strong> {earnings_date}
                  ({days_away} day{'s' if days_away!=1 else ''} away!)
                </div>"""
            else:
                earn_html = f"<div style='font-size:11px;color:#888;margin:4px 0;'>📅 Next earnings: {earnings_date} ({days_away}d)</div>"
        except:
            earn_html = f"<div style='font-size:11px;color:#888;'>📅 Earnings: {earnings_date}</div>"

    # News items
    news_html = ""
    if news_items:
        items = []
        for n in news_items[:4]:
            title = n.get("title", "")[:90]
            url   = n.get("url", "#")
            s     = score_sentiment(n.get("overall_sentiment_label", ""))
            em    = sentiment_emoji(s)
            items.append(f"<li style='margin:3px 0;font-size:12px;'>"
                         f"{em} <a href='{url}' style='color:#2980b9;text-decoration:none;'>{title}</a>"
                         f"</li>")
        news_html = "<ul style='margin:6px 0;padding-left:18px;'>" + "".join(items) + "</ul>"

    # Price change color
    try:
        chg = float(change_pct)
        chg_color  = "#27ae60" if chg >= 0 else "#e74c3c"
        chg_str    = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
    except:
        chg_color, chg_str = "#666", "—"

    target_html = ""
    if analyst_target:
        try:
            t = float(analyst_target)
            p = float(price)
            upside = (t - p) / p * 100
            upside_color = "#27ae60" if upside > 0 else "#e74c3c"
            target_html = f"<span style='color:{upside_color};font-size:11px;margin-left:8px;'>🎯 Target: ${t:.2f} ({upside:+.1f}%)</span>"
        except: pass

    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:8px;
                padding:14px 16px;margin-bottom:14px;background:#fafafa;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:17px;font-weight:bold;color:#1a1a2e;">{ticker}</span>
        <span style="font-size:17px;font-weight:bold;">${float(price):.2f}
          <span style="font-size:13px;color:{chg_color};">{chg_str}</span>
          {target_html}
        </span>
      </div>
      <div style="font-size:11px;color:#888;margin:3px 0;">
        P/E: {pe or 'N/A'} &nbsp;|&nbsp; P/B: {pb or 'N/A'}
      </div>
      {bar_html}
      {uv_html}
      {earn_html}
      {news_html}
    </div>"""

# ─────────────────────────────────────────────
#  SEND EMAIL
# ─────────────────────────────────────────────
def send_email(subject, html_body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not TO_EMAIL:
        print("⚠️  Email credentials missing — skipping send.")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Your Trading Bot <{EMAIL_SENDER}>"
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, TO_EMAIL, msg.as_string())
        print(f"✅  Email sent: {subject}")
    except Exception as e:
        print(f"❌  Email failed: {e}")

# ─────────────────────────────────────────────
#  PHASE 1 — WATCHLIST ANALYSIS
# ─────────────────────────────────────────────
def run_watchlist(earnings_calendar):
    print("\n📋 Running watchlist analysis...")
    cards = []
    earnings_alerts = []

    for ticker in WATCHLIST:
        print(f"  → {ticker}")
        overview = get_overview(ticker)
        quote    = get_quote(ticker)
        news     = get_news(ticker)

        if not quote.get("05. price"):
            print(f"     No data for {ticker}, skipping.")
            continue

        price      = quote.get("05. price", "0")
        change_pct = quote.get("10. change percent", "0%").replace("%", "")
        pe         = overview.get("PERatio", "N/A")
        pb         = overview.get("PriceToBookRatio", "N/A")
        w52low     = overview.get("52WeekLow", "0")
        w52high    = overview.get("52WeekHigh", "0")
        target     = overview.get("AnalystTargetPrice")

        earn_date = earnings_calendar.get(ticker)
        uv_score, uv_details = score_undervalue(overview, quote)

        # Check for earnings alert
        if earn_date:
            try:
                ed = datetime.strptime(earn_date, "%Y-%m-%d").date()
                if (ed - datetime.now().date()).days <= 1:
                    earnings_alerts.append(ticker)
            except: pass

        cards.append(stock_card_html(
            ticker, price, change_pct, pe, pb, w52low, w52high,
            earn_date, ticker in earnings_alerts, news,
            uv_score, uv_details, target
        ))

    return "".join(cards), earnings_alerts

# ─────────────────────────────────────────────
#  PHASE 2 — FULL MARKET SCAN
# ─────────────────────────────────────────────
def run_market_scan():
    """
    Scan US + Canadian tickers, score each for undervalue,
    return top picks in different categories.
    """
    print("\n🔍 Running full market scan (US + Canada)...")
    all_results = []

    all_tickers = US_TICKERS + CA_TICKERS
    total = len(all_tickers)

    for i, ticker in enumerate(all_tickers, 1):
        if i % 20 == 0:
            print(f"   Progress: {i}/{total}")
        try:
            overview = get_overview(ticker)
            quote    = get_quote(ticker)

            price = quote.get("05. price")
            if not price:
                continue

            change_pct = quote.get("10. change percent", "0%").replace("%", "")
            pe         = overview.get("PERatio", "N/A")
            pb         = overview.get("PriceToBookRatio", "N/A")
            w52low     = overview.get("52WeekLow", "0")
            w52high    = overview.get("52WeekHigh", "0")
            target     = overview.get("AnalystTargetPrice")

            uv_score, uv_details = score_undervalue(overview, quote)

            # Upside/Downside news flag
            try:
                chg = float(change_pct)
            except:
                chg = 0.0

            news = []
            # Only fetch news for high-scoring or big movers (save API calls)
            if uv_score >= 55 or abs(chg) > 3:
                news = get_news(ticker)

            all_results.append({
                "ticker":     ticker,
                "price":      price,
                "change_pct": change_pct,
                "chg_float":  chg,
                "pe":         pe,
                "pb":         pb,
                "w52low":     w52low,
                "w52high":    w52high,
                "target":     target,
                "uv_score":   uv_score,
                "uv_details": uv_details,
                "news":       news,
                "is_ca":      ticker in CA_TICKERS,
            })
        except Exception as e:
            print(f"   Error on {ticker}: {e}")
            continue

    return all_results

def build_scan_sections(results):
    """Build HTML sections from scan results."""
    if not results:
        return [("⚠️ Scan Results", "<p>No data returned — API may be rate-limited.</p>")]

    sorted_uv   = sorted(results, key=lambda x: x["uv_score"], reverse=True)
    us_picks    = [r for r in sorted_uv if not r["is_ca"]][:5]
    ca_picks    = [r for r in sorted_uv if r["is_ca"]][:5]
    deep_value  = [r for r in sorted_uv if r["uv_score"] >= 70][:8]
    upside_move = sorted([r for r in results if r["chg_float"] > 3],
                         key=lambda x: x["chg_float"], reverse=True)[:5]
    risk_alert  = sorted([r for r in results if r["chg_float"] < -3],
                         key=lambda x: x["chg_float"])[:5]

    def make_cards(lst):
        html = []
        for r in lst:
            html.append(stock_card_html(
                r["ticker"], r["price"], r["change_pct"],
                r["pe"], r["pb"], r["w52low"], r["w52high"],
                None, False, r["news"],
                r["uv_score"], r["uv_details"], r["target"]
            ))
        return "".join(html) if html else "<p style='color:#888;'>None today.</p>"

    sections = []

    # Deep value gems
    if deep_value:
        sections.append((
            "🔥 Deep Value Gems (Score 70+) — Best Undervalued Opportunities",
            make_cards(deep_value)
        ))

    sections.append(("🇺🇸 Top 5 US Undervalued Picks", make_cards(us_picks)))
    sections.append(("🇨🇦 Top 5 Canadian Undervalued Picks", make_cards(ca_picks)))

    if upside_move:
        sections.append((
            "🚀 Big Upside Movers Today (+3% or more)",
            make_cards(upside_move)
        ))

    if risk_alert:
        sections.append((
            "⚠️ Risk Alerts — Stocks Falling Hard (-3% or more)",
            make_cards(risk_alert)
        ))

    # Scoring methodology note
    method_html = """
    <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:14px;font-size:12px;">
      <strong>How the Undervalued Score Works (0–100):</strong><br><br>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📊 P/E vs Sector Average</td><td>up to 25 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📚 Price-to-Book (P/B &lt; 1 = deep value)</td><td>up to 20 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">💰 Debt-to-Equity (&lt; 1.0 preferred)</td><td>up to 15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">📉 52-Week Position (near low = opportunity)</td><td>up to 15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">🎯 Analyst Price Target Upside</td><td>up to 15 pts</td></tr>
        <tr><td style="padding:3px 10px 3px 0;color:#555;">💵 Dividend Yield + Payout &lt; 60%</td><td>up to 10 pts</td></tr>
      </table>
      <br>⚠️ This is a quantitative screen — always read the company's fundamentals before investing.
    </div>"""
    sections.append(("📖 Scoring Methodology", method_html))

    return sections

# ─────────────────────────────────────────────
#  MAIN RUNNERS
# ─────────────────────────────────────────────
def run_morning():
    """5 AM — Full morning brief: watchlist + full market scan."""
    print("🌅 Running 5 AM Morning Brief...")
    today_str = datetime.now().strftime("%b %d")

    earnings_cal = get_earnings_calendar()

    # Phase 1: watchlist
    watchlist_html, alerts = run_watchlist(earnings_cal)

    # Phase 2: full scan
    scan_results  = run_market_scan()
    scan_sections = build_scan_sections(scan_results)

    # Build email
    alert_tag = f" ⚠️ {len(alerts)} Earnings Alert{'s' if len(alerts)!=1 else ''}!" if alerts else ""
    subject   = f"📊 Morning Stock Brief | {today_str}{alert_tag} | Watchlist + Market Scan"

    sections = [("👀 Your Watchlist", watchlist_html)] + scan_sections
    html = build_email_html(f"Morning Stock Brief — {today_str}", sections)
    send_email(subject, html)

def run_eod():
    """6 PM — End-of-day watchlist recap only."""
    print("🌆 Running 6 PM End-of-Day Recap...")
    today_str = datetime.now().strftime("%b %d")

    earnings_cal = get_earnings_calendar()
    watchlist_html, alerts = run_watchlist(earnings_cal)

    alert_tag = f" ⚠️ Earnings Tomorrow: {', '.join(alerts)}!" if alerts else ""
    subject   = f"📈 End-of-Day Recap | {today_str}{alert_tag} | How Your Stocks Closed"

    sections = [("📋 Your Watchlist — End of Day", watchlist_html)]
    html = build_email_html(f"End-of-Day Recap — {today_str}", sections)
    send_email(subject, html)

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["morning", "eod"], default="morning",
                        help="morning = 5 AM full brief | eod = 6 PM recap")
    args = parser.parse_args()

    if args.phase == "morning":
        run_morning()
    else:
        run_eod()
