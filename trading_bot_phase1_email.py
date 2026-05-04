# ============================================================
#  TRADING BOT — PHASE 1  (with Email Report)
#
#  Runs automatically via GitHub Actions at 6 AM and 5 PM PT.
#  Also works manually in Google Colab.
#
#  SECRETS (set in GitHub → Settings → Secrets, NOT here):
#    ALPHA_VANTAGE_KEY  — your Alpha Vantage API key
#    EMAIL_SENDER       — your Gmail address
#    EMAIL_PASSWORD     — your Gmail App Password (16 chars)
#    EMAIL_RECIPIENT    — where to send the report (can be same as sender)
#
#  WATCHLIST — edit the list below directly.
# ============================================================

import os
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── CONFIGURATION ────────────────────────────────────────────
# Tickers you want to track — edit this list anytime
WATCHLIST = ["SOFI", "COIN", "HOOD", "MSTR", "NOK", "GME","EBAY","ORCL","LLY","BBAI"]

# Alert this many days before earnings (1 = alert the day before)
ALERT_DAYS_BEFORE_EARNINGS = 1

# These are pulled from GitHub Secrets automatically — do NOT paste keys here
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "YOUR_KEY_HERE")
EMAIL_SENDER      = os.environ.get("EMAIL_SENDER",      "your@gmail.com")
_raw_pw = os.environ.get("EMAIL_PASSWORD", "your_app_password")
EMAIL_PASSWORD = "".join(c for c in _raw_pw if c.isascii() and c not in (" ", "\xa0"))
EMAIL_RECIPIENT   = os.environ.get("EMAIL_RECIPIENT",   "your@gmail.com")
# ──────────────────────────────────────────────────────────────

# ── Install dependencies if needed (Colab / fresh environment) ─
def install(pkg):
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    import yfinance as yf
except ImportError:
    install("yfinance"); import yfinance as yf

try:
    from textblob import TextBlob
except ImportError:
    install("textblob"); from textblob import TextBlob


# ── DATA FETCHING ─────────────────────────────────────────────

def get_price_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        price  = info.get("currentPrice") or info.get("regularMarketPrice", None)
        pe     = info.get("trailingPE", None)
        low52  = info.get("fiftyTwoWeekLow", None)
        high52 = info.get("fiftyTwoWeekHigh", None)
        mktcap = info.get("marketCap", None)
        name   = info.get("shortName", ticker)
        sector = info.get("sector", "—")

        def fmt_price(v): return f"${v:,.2f}" if v else "N/A"
        def fmt_cap(v):
            if not v: return "N/A"
            if v >= 1e12: return f"${v/1e12:.1f}T"
            if v >= 1e9:  return f"${v/1e9:.1f}B"
            return f"${v/1e6:.0f}M"

        return {
            "name":   name,
            "price":  fmt_price(price),
            "pe":     f"{pe:.1f}x" if pe else "N/A",
            "52wk":   f"{fmt_price(low52)} – {fmt_price(high52)}",
            "mktcap": fmt_cap(mktcap),
            "sector": sector,
            "raw_price": price,
            "raw_52low": low52,
            "raw_52high": high52,
        }
    except Exception as e:
        return {"name": ticker, "price": "N/A", "pe": "N/A",
                "52wk": "N/A", "mktcap": "N/A", "sector": "N/A",
                "raw_price": None, "raw_52low": None, "raw_52high": None}


def get_earnings_info(ticker):
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is not None and not cal.empty:
            if "Earnings Date" in cal.index:
                earn_date = cal.loc["Earnings Date"].iloc[0]
            elif hasattr(cal, "columns") and "Earnings Date" in cal.columns:
                earn_date = cal["Earnings Date"].iloc[0]
            else:
                return None, None
            if hasattr(earn_date, "date"):
                earn_date = earn_date.date()
            days_until = (earn_date - datetime.today().date()).days
            return earn_date, days_until
    except Exception:
        pass
    return None, None


def get_news(ticker):
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT&tickers={ticker}"
        f"&limit=5&apikey={ALPHA_VANTAGE_KEY}"
    )
    try:
        data = requests.get(url, timeout=10).json()
        results = []
        for item in data.get("feed", [])[:5]:
            title = item.get("title", "")
            pub   = item.get("time_published", "")[:8]
            try:   pub_fmt = datetime.strptime(pub, "%Y%m%d").strftime("%b %d")
            except: pub_fmt = pub

            score = None
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker") == ticker:
                    score = float(ts.get("ticker_sentiment_score", 0))
                    break
            if score is None:
                score = TextBlob(title).sentiment.polarity

            if score > 0.15:    sentiment, color, icon = "Positive", "#1D9E75", "▲"
            elif score < -0.15: sentiment, color, icon = "Negative", "#E24B4A", "▼"
            else:               sentiment, color, icon = "Neutral",  "#888780", "●"

            results.append({
                "date": pub_fmt, "title": title[:100],
                "sentiment": sentiment, "color": color, "icon": icon,
                "score": round(score, 3),
                "url": item.get("url", "#"),
            })
        return results
    except Exception as e:
        return [{"date": "—", "title": f"Could not fetch news: {e}",
                 "sentiment": "—", "color": "#888780", "icon": "●",
                 "score": 0, "url": "#"}]


# ── PRICE POSITION BAR (where price sits in 52-week range) ────
def price_bar_html(raw_price, raw_low, raw_high):
    if not all([raw_price, raw_low, raw_high]) or raw_high == raw_low:
        return ""
    pct = max(0, min(100, (raw_price - raw_low) / (raw_high - raw_low) * 100))
    color = "#1D9E75" if pct < 40 else "#EF9F27" if pct < 70 else "#E24B4A"
    return f"""
    <div style="margin:6px 0 2px;font-size:11px;color:#888;">52-week position</div>
    <div style="background:#eee;border-radius:4px;height:6px;position:relative;margin-bottom:4px;">
      <div style="background:{color};width:{pct:.0f}%;height:6px;border-radius:4px;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#aaa;">
      <span>52W Low</span><span>{pct:.0f}% from low</span><span>52W High</span>
    </div>"""


# ── EMAIL HTML BUILDER ────────────────────────────────────────

def build_html_report(results):
    now     = datetime.now()
    session = "Morning" if now.hour < 12 else "Afternoon"
    date_str = now.strftime("%A, %B %d %Y  ·  %I:%M %p PT")
    alert_count = sum(1 for r in results if r.get("is_earnings_alert"))

    # Header
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;margin:0;padding:20px;color:#222;}}
  .wrap{{max-width:640px;margin:0 auto;}}
  .header{{background:#0F6E56;color:#fff;padding:24px 28px;border-radius:12px 12px 0 0;}}
  .header h1{{margin:0;font-size:20px;font-weight:600;}}
  .header p{{margin:6px 0 0;font-size:13px;opacity:.8;}}
  .body{{background:#fff;padding:0 0 20px;border-radius:0 0 12px 12px;border:1px solid #e5e5e5;border-top:none;}}
  .ticker-card{{margin:20px 20px 0;border:1px solid #e8e8e8;border-radius:10px;overflow:hidden;}}
  .ticker-head{{padding:14px 16px;background:#f9f9f9;border-bottom:1px solid #eee;display:flex;align-items:center;justify-content:space-between;}}
  .ticker-symbol{{font-size:18px;font-weight:700;color:#222;}}
  .ticker-name{{font-size:12px;color:#888;margin-top:2px;}}
  .ticker-price{{font-size:20px;font-weight:600;color:#222;text-align:right;}}
  .ticker-sector{{font-size:11px;color:#aaa;text-align:right;}}
  .meta-row{{display:flex;gap:16px;padding:12px 16px 4px;flex-wrap:wrap;}}
  .meta-item{{font-size:12px;}}
  .meta-label{{color:#aaa;margin-bottom:2px;}}
  .meta-value{{color:#222;font-weight:500;}}
  .alert-box{{margin:8px 16px;padding:10px 14px;border-radius:8px;font-size:13px;font-weight:500;}}
  .alert-earnings{{background:#FFF3CD;border-left:4px solid #EF9F27;color:#7a5200;}}
  .alert-today{{background:#FFE0E0;border-left:4px solid #E24B4A;color:#7a0000;}}
  .alert-past{{background:#f0f0f0;border-left:4px solid #bbb;color:#555;}}
  .news-section{{padding:8px 16px 4px;}}
  .news-label{{font-size:11px;color:#aaa;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;}}
  .news-item{{padding:7px 0;border-bottom:1px solid #f0f0f0;}}
  .news-item:last-child{{border-bottom:none;}}
  .news-meta{{display:flex;align-items:center;gap:8px;margin-bottom:3px;}}
  .news-date{{font-size:11px;color:#aaa;}}
  .news-badge{{font-size:10px;font-weight:600;padding:1px 7px;border-radius:10px;}}
  .news-title{{font-size:13px;color:#333;line-height:1.4;}}
  .news-title a{{color:#185FA5;text-decoration:none;}}
  .footer{{text-align:center;padding:16px 20px 0;font-size:11px;color:#aaa;}}
  .summary-bar{{background:#0F6E56;color:#fff;margin:0 20px 0;padding:10px 16px;border-radius:8px;font-size:13px;display:flex;justify-content:space-between;}}
</style></head><body><div class="wrap">
<div class="header">
  <h1>📊 Trading Bot — {session} Report</h1>
  <p>{date_str}</p>
</div>
<div class="body">
"""

    # Summary bar
    if alert_count > 0:
        html += f'<div style="margin:16px 20px 0;padding:10px 16px;background:#FFF3CD;border-radius:8px;font-size:13px;color:#7a5200;font-weight:500;">⚠️ {alert_count} earnings alert{"s" if alert_count>1 else ""} in this report — check highlighted cards below.</div>'

    # Per-ticker cards
    for r in results:
        info   = r["info"]
        earn   = r["earn"]
        news   = r["news"]

        # Price bar
        pbar = price_bar_html(info["raw_price"], info["raw_52low"], info["raw_52high"])

        # Earnings alert
        alert_html = ""
        days = earn["days_until"]
        date = earn["earn_date"]
        if days is not None:
            if days == 0:
                alert_html = f'<div class="alert-box alert-today">🚨 EARNINGS TODAY ({date}) — stay alert and check your position!</div>'
            elif 0 < days <= ALERT_DAYS_BEFORE_EARNINGS:
                alert_html = f'<div class="alert-box alert-earnings">⚠️ Earnings in {days} day(s) — {date} — consider your position before market open.</div>'
            elif days < 0:
                alert_html = f'<div class="alert-box alert-past">📅 Earnings were {abs(days)} days ago ({date})</div>'
            else:
                alert_html = f'<div style="padding:6px 16px;font-size:12px;color:#aaa;">📅 Next earnings: {date} (in {days} days)</div>'

        # News rows
        news_rows = ""
        for n in news:
            news_rows += f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-date">{n["date"]}</span>
            <span class="news-badge" style="background:{n["color"]}22;color:{n["color"]};">{n["icon"]} {n["sentiment"]}</span>
          </div>
          <div class="news-title"><a href="{n["url"]}" target="_blank">{n["title"]}</a></div>
        </div>"""

        html += f"""
  <div class="ticker-card">
    <div class="ticker-head">
      <div>
        <div class="ticker-symbol">{r["ticker"]}</div>
        <div class="ticker-name">{info["name"]} · {info["sector"]}</div>
      </div>
      <div>
        <div class="ticker-price">{info["price"]}</div>
        <div class="ticker-sector">Mkt cap: {info["mktcap"]}</div>
      </div>
    </div>
    <div class="meta-row">
      <div class="meta-item"><div class="meta-label">P/E Ratio</div><div class="meta-value">{info["pe"]}</div></div>
      <div class="meta-item"><div class="meta-label">52-week range</div><div class="meta-value">{info["52wk"]}</div></div>
    </div>
    <div style="padding:0 16px 8px;">{pbar}</div>
    {alert_html}
    <div class="news-section">
      <div class="news-label">Latest news &amp; sentiment</div>
      {news_rows}
    </div>
  </div>"""

    html += """
  <div class="footer">
    This report is for research and learning purposes only — not financial advice.<br>
    Trading involves risk. Always do your own research before making decisions.
  </div>
</div>
</div></body></html>"""
    return html


# ── PLAIN TEXT FALLBACK ───────────────────────────────────────

def build_text_report(results):
    now = datetime.now()
    lines = [
        "=" * 60,
        f"  TRADING BOT REPORT — {now.strftime('%A %B %d %Y %I:%M %p PT')}",
        "=" * 60,
    ]
    for r in results:
        info = r["info"]
        earn = r["earn"]
        news = r["news"]
        lines += [
            f"\n{'─'*60}",
            f"  {r['ticker']}  —  {info['name']}",
            f"  Price: {info['price']}  |  P/E: {info['pe']}  |  52wk: {info['52wk']}",
        ]
        days = earn["days_until"]
        if days is not None:
            if days == 0:   lines.append(f"  *** EARNINGS TODAY ({earn['earn_date']}) ***")
            elif days <= 1: lines.append(f"  *** EARNINGS IN {days} DAY: {earn['earn_date']} ***")
            else:           lines.append(f"  Next earnings: {earn['earn_date']} (in {days} days)")
        lines.append("  News:")
        for n in news:
            lines.append(f"    [{n['date']}] {n['icon']} {n['sentiment']}  {n['title'][:80]}")
    lines += ["", "=" * 60, "  Research only — not financial advice.", "=" * 60]
    return "\n".join(lines)


# ── SEND EMAIL ────────────────────────────────────────────────

def send_email(subject, html_body, text_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
    print(f"✅ Email sent to {EMAIL_RECIPIENT}")


# ── MAIN ──────────────────────────────────────────────────────

def run():
    now = datetime.now()
    session = "Morning" if now.hour < 12 else "Afternoon"
    print(f"📊 Trading Bot running — {now.strftime('%Y-%m-%d %H:%M')}")

    results = []
    alert_count = 0

    for ticker in WATCHLIST:
        print(f"  Fetching {ticker}...")
        info = get_price_info(ticker)
        earn_date, days_until = get_earnings_info(ticker)
        news = get_news(ticker)
        import time; time.sleep(13)

        is_alert = days_until is not None and 0 <= days_until <= ALERT_DAYS_BEFORE_EARNINGS
        if is_alert:
            alert_count += 1

        results.append({
            "ticker": ticker,
            "info": info,
            "earn": {"earn_date": earn_date, "days_until": days_until},
            "news": news,
            "is_earnings_alert": is_alert,
        })

    html_body = build_html_report(results)
    text_body = build_text_report(results)

    alert_tag = f" ⚠️ {alert_count} EARNINGS ALERT" if alert_count else ""
    subject = f"📊 Trading Bot {session} Report · {now.strftime('%b %d')}{alert_tag}"

    print(text_body)  # also print to console / Actions log

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD != "your_app_password":
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Email not sent — set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in env/secrets.")


if __name__ == "__main__":
    run()
