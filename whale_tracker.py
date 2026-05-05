"""
Kraken Whale Movement Tracker
- Fetches all altcoins under $2 on Kraken
- Detects whale movements via volume spikes, large orders, price momentum
- Sends Gmail alerts when whale activity detected
"""

import requests
import smtplib
import json
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONFIG — set these as GitHub Secrets
# ─────────────────────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")
AV_KEY          = os.environ.get("ALPHA_VANTAGE_KEY", "demo")

# ─────────────────────────────────────────────
# WHALE DETECTION THRESHOLDS (tune these)
# ─────────────────────────────────────────────
VOLUME_SPIKE_MULTIPLIER  = 5.0   # current volume must be 5x the 24h average per-minute rate
PRICE_MOVE_THRESHOLD     = 0.03  # 3% price move in last hour triggers alert
MIN_VOLUME_USD           = 50_000  # ignore coins with less than $50k daily volume (too illiquid)
MAX_PRICE_USD            = 2.0   # only altcoins under $2
ORDER_BOOK_WALL_USD      = 25_000  # flag if a single order wall is this large

KRAKEN_API = "https://api.kraken.com/0/public"


def get_all_kraken_pairs():
    """Fetch all USD/USDT tradeable pairs from Kraken."""
    r = requests.get(f"{KRAKEN_API}/AssetPairs", timeout=15)
    r.raise_for_status()
    pairs = r.json().get("result", {})
    
    usd_pairs = []
    for pair_id, info in pairs.items():
        quote = info.get("quote", "")
        # Only USD or USDT quoted pairs
        if quote in ("ZUSD", "USDT") and info.get("status") == "online":
            usd_pairs.append(pair_id)
    return usd_pairs


def get_ticker_data(pairs_chunk):
    """Fetch ticker for a batch of pairs."""
    pair_str = ",".join(pairs_chunk)
    r = requests.get(f"{KRAKEN_API}/Ticker", params={"pair": pair_str}, timeout=15)
    r.raise_for_status()
    return r.json().get("result", {})


def get_ohlc_data(pair, interval=60):
    """Fetch 1h OHLC to compute recent price change."""
    r = requests.get(f"{KRAKEN_API}/OHLC", params={"pair": pair, "interval": interval}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    # Result key is the pair name (not always identical to input)
    for key, val in result.items():
        if key != "last":
            return val  # list of [time, open, high, low, close, vwap, volume, count]
    return []


def get_order_book(pair, count=10):
    """Fetch top N levels of order book."""
    r = requests.get(f"{KRAKEN_API}/Depth", params={"pair": pair, "count": count}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        return val  # {"asks": [...], "bids": [...]}
    return {}


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def compute_price_change(ohlc_data):
    """Return % price change from oldest to newest candle in the dataset."""
    if not ohlc_data or len(ohlc_data) < 2:
        return 0.0
    open_price  = float(ohlc_data[0][1])
    close_price = float(ohlc_data[-1][4])
    if open_price == 0:
        return 0.0
    return (close_price - open_price) / open_price


def detect_order_book_whale(order_book, current_price, wall_usd=ORDER_BOOK_WALL_USD):
    """Check if any single order in top-10 book is a whale wall."""
    whales = []
    for side in ("bids", "asks"):
        for level in order_book.get(side, []):
            price  = float(level[0])
            volume = float(level[1])
            usd_value = price * volume
            if usd_value >= wall_usd:
                whales.append({
                    "side": "BUY wall" if side == "bids" else "SELL wall",
                    "price": price,
                    "volume": volume,
                    "usd_value": usd_value
                })
    return whales


def scan_for_whales():
    """Main scan — returns list of alert dicts."""
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Starting whale scan...")

    all_pairs = get_all_kraken_pairs()
    print(f"  Found {len(all_pairs)} USD/USDT pairs on Kraken")

    alerts = []
    scanned = 0

    # Batch ticker requests (Kraken allows many pairs at once)
    for batch in chunk_list(all_pairs, 50):
        try:
            ticker_data = get_ticker_data(batch)
        except Exception as e:
            print(f"  Ticker batch error: {e}")
            continue

        for pair_id, t in ticker_data.items():
            try:
                last_price   = float(t["c"][0])   # last trade price
                volume_24h   = float(t["v"][1])    # 24h volume in base currency
                vwap_24h     = float(t["p"][1])    # 24h VWAP
                volume_usd   = volume_24h * vwap_24h
                num_trades_24h = int(t["t"][1])    # number of trades in 24h

                # Filter: must be under $2 and have enough liquidity
                if last_price >= MAX_PRICE_USD or last_price <= 0:
                    continue
                if volume_usd < MIN_VOLUME_USD:
                    continue

                scanned += 1

                # ── SIGNAL 1: Volume spike ──────────────────────
                # Average volume per minute over 24h vs last-hour volume rate
                # Kraken gives us today's volume vs yesterday's volume
                volume_today     = float(t["v"][0])  # volume since midnight UTC
                volume_yesterday = float(t["v"][1])  # rolling 24h volume
                # If today's volume is already > X% of 24h volume in a short window → spike
                avg_per_min_24h = volume_24h / (24 * 60)
                # Use high trade price as proxy for recent activity weight
                high_24h = float(t["h"][1])
                low_24h  = float(t["l"][1])
                price_range_pct = (high_24h - low_24h) / low_24h if low_24h > 0 else 0

                volume_spike = False
                spike_ratio  = 1.0
                # Simple heuristic: if today volume > 60% of 24h rolling volume, unusual activity
                if volume_yesterday > 0:
                    spike_ratio = volume_today / volume_yesterday
                    if spike_ratio >= 0.6:  # 60%+ of 24h done already today
                        volume_spike = True

                # ── SIGNAL 2: Price momentum ────────────────────
                price_change = 0.0
                try:
                    ohlc = get_ohlc_data(pair_id, interval=60)  # 1h candles
                    price_change = compute_price_change(ohlc)
                except Exception:
                    pass

                strong_move = abs(price_change) >= PRICE_MOVE_THRESHOLD

                # ── SIGNAL 3: Order book whale wall ────────────
                ob_whales = []
                if volume_spike or strong_move:
                    try:
                        ob = get_order_book(pair_id, count=10)
                        ob_whales = detect_order_book_whale(ob, last_price)
                    except Exception:
                        pass

                # ── Combine signals ─────────────────────────────
                signal_count = sum([volume_spike, strong_move, bool(ob_whales)])
                if signal_count >= 2:  # need at least 2 signals to alert
                    alerts.append({
                        "pair":         pair_id,
                        "price":        last_price,
                        "price_change": price_change,
                        "volume_usd":   volume_usd,
                        "spike_ratio":  spike_ratio,
                        "volume_spike": volume_spike,
                        "strong_move":  strong_move,
                        "ob_whales":    ob_whales,
                        "signal_count": signal_count,
                        "high_24h":     high_24h,
                        "low_24h":      low_24h,
                        "range_pct":    price_range_pct * 100,
                    })

            except Exception as e:
                pass

        time.sleep(0.5)  # be polite to Kraken API

    print(f"  Scanned {scanned} eligible coins. Found {len(alerts)} whale alerts.")
    return alerts


def build_email_html(alerts):
    """Build a nicely formatted HTML email."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for a in sorted(alerts, key=lambda x: -x["signal_count"]):
        signals = []
        if a["volume_spike"]:
            signals.append(f"🔥 Volume spike ({a['spike_ratio']:.1%} of 24h done today)")
        if a["strong_move"]:
            direction = "📈 UP" if a["price_change"] > 0 else "📉 DOWN"
            signals.append(f"{direction} {abs(a['price_change']):.1%} in last hour")
        for w in a["ob_whales"]:
            signals.append(f"🐋 {w['side']} ${w['usd_value']:,.0f} @ ${w['price']:.6f}")

        signal_html = "<br>".join(signals)
        change_color = "#00c853" if a["price_change"] >= 0 else "#d32f2f"

        rows += f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #333;font-weight:bold;color:#e0e0e0;">
            {a['pair']}
          </td>
          <td style="padding:12px;border-bottom:1px solid #333;color:#e0e0e0;">
            ${a['price']:.6f}
          </td>
          <td style="padding:12px;border-bottom:1px solid #333;color:{change_color};font-weight:bold;">
            {'+' if a['price_change'] >= 0 else ''}{a['price_change']:.2%}
          </td>
          <td style="padding:12px;border-bottom:1px solid #333;color:#e0e0e0;">
            ${a['volume_usd']:,.0f}
          </td>
          <td style="padding:12px;border-bottom:1px solid #333;color:#e0e0e0;font-size:13px;">
            {signal_html}
          </td>
        </tr>
        """

    html = f"""
    <html><body style="background:#121212;font-family:Arial,sans-serif;margin:0;padding:20px;">
      <div style="max-width:900px;margin:auto;background:#1e1e1e;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.5);">
        
        <div style="background:linear-gradient(135deg,#1a237e,#4a148c);padding:24px;">
          <h1 style="color:#fff;margin:0;font-size:24px;">🐋 Whale Alert — Kraken</h1>
          <p style="color:#ce93d8;margin:8px 0 0;">{now} — {len(alerts)} coin(s) flagged</p>
        </div>

        <div style="padding:20px;">
          <p style="color:#bdbdbd;font-size:14px;">
            These altcoins under $2 on Kraken are showing <strong style="color:#ce93d8;">unusual whale activity</strong>.
            At least 2 of 3 signals triggered: volume spike, price momentum, or large order walls.
            <br><strong style="color:#ff9800;">⚠️ Not financial advice. Do your own research before trading.</strong>
          </p>

          <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <thead>
              <tr style="background:#2d2d2d;">
                <th style="padding:12px;text-align:left;color:#ce93d8;">Pair</th>
                <th style="padding:12px;text-align:left;color:#ce93d8;">Price</th>
                <th style="padding:12px;text-align:left;color:#ce93d8;">1h Change</th>
                <th style="padding:12px;text-align:left;color:#ce93d8;">24h Vol (USD)</th>
                <th style="padding:12px;text-align:left;color:#ce93d8;">Signals</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>

          <div style="margin-top:24px;padding:16px;background:#2d2d2d;border-radius:8px;border-left:4px solid #7c4dff;">
            <p style="color:#bdbdbd;margin:0;font-size:13px;">
              <strong style="color:#ce93d8;">Signal Legend:</strong><br>
              🔥 Volume Spike — Today's volume is abnormally high vs. 24h average<br>
              📈/📉 Price Move — 3%+ move in the last hour<br>
              🐋 Order Wall — Large single order ($25k+) sitting in the book
            </p>
          </div>
        </div>

        <div style="padding:16px 20px;background:#1a1a1a;text-align:center;">
          <p style="color:#616161;font-size:12px;margin:0;">
            Kraken Whale Tracker • Runs every 5 min via GitHub Actions • 
            <a href="https://www.kraken.com/trade" style="color:#7c4dff;">Open Kraken</a>
          </p>
        </div>
      </div>
    </body></html>
    """
    return html


def send_email(subject, html_body):
    """Send HTML email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ALERT_TO
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())

    print(f"  ✅ Email sent to {ALERT_TO}")


def main():
    alerts = scan_for_whales()

    if not alerts:
        print("  No whale activity detected this run. No email sent.")
        return

    subject = f"🐋 Whale Alert: {len(alerts)} Kraken Altcoin(s) Moving — {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    html    = build_email_html(alerts)

    if not GMAIL_USER or not GMAIL_PASS:
        print("  ⚠️  GMAIL_USER or GMAIL_PASS not set. Printing alerts instead:")
        for a in alerts:
            print(f"    {a['pair']} | ${a['price']:.6f} | {a['price_change']:.2%} | Vol ${a['volume_usd']:,.0f}")
        return

    send_email(subject, html)


if __name__ == "__main__":
    main()
