# ============================================================
# TRADING BOT — PHASE 3 (Kraken Whale Tracker)
#
# Monitors ALL altcoins under $2 on Kraken (600+).
# Detects whale movements via volume spikes, price momentum,
# and large order book walls.
# Sends a Gmail alert ONLY when whale activity is detected.
#
# Runs automatically via GitHub Actions every 15 minutes, 24/7.
# Also works manually in Google Colab.
#
# SECRETS (set in GitHub → Settings → Secrets, NOT here):
#   EMAIL_SENDER    — your Gmail address
#   EMAIL_PASSWORD  — your Gmail App Password (16 chars)
#   EMAIL_RECIPIENT — where to send alerts (can be same as sender)
#
# No paid API key required — uses Kraken's free public API.
# ============================================================

import os
import smtplib
import requests
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── SECRETS (pulled from GitHub Actions environment) ──────────
_raw_pw = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")

# ──────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════
# WHALE DETECTION THRESHOLDS — tune these to your preference
#
#   Lower PRICE_MOVE_THRESHOLD  → more alerts (catches smaller moves)
#   Raise ORDER_BOOK_WALL_USD   → fewer alerts (only bigger whales)
#   Lower MIN_VOLUME_USD        → includes lower-liquidity coins
# ══════════════════════════════════════════════════════════════

MAX_PRICE_USD        = 2.00    # only altcoins under $2
MIN_VOLUME_USD       = 50_000  # skip coins with < $50k daily volume (too illiquid)
PRICE_MOVE_THRESHOLD = 0.03    # 3% price move in recent candles = signal
ORDER_BOOK_WALL_USD  = 25_000  # single order >= $25k in top-10 book = whale wall
TODAY_VOL_RATIO      = 0.60    # today's vol >= 60% of rolling 24h vol = volume spike
SIGNALS_REQUIRED     = 2       # must trigger at least 2 of 3 signals to fire an alert

KRAKEN_API = "https://api.kraken.com/0/public"


# ══════════════════════════════════════════════════════════════
# KRAKEN DATA LAYER
# ══════════════════════════════════════════════════════════════

def get_all_kraken_pairs():
    """Return all online USD/USDT-quoted pairs from Kraken."""
    r = requests.get(f"{KRAKEN_API}/AssetPairs", timeout=15)
    r.raise_for_status()
    pairs = r.json().get("result", {})
    return [
        pair_id for pair_id, info in pairs.items()
        if info.get("quote") in ("ZUSD", "USDT") and info.get("status") == "online"
    ]


def get_ticker_batch(pair_ids):
    """Fetch ticker data for up to 50 pairs in a single API call."""
    r = requests.get(f"{KRAKEN_API}/Ticker", params={"pair": ",".join(pair_ids)}, timeout=15)
    r.raise_for_status()
    return r.json().get("result", {})


def get_ohlc(pair, interval=60):
    """Fetch 1-hour OHLC candles. Returns list of candle arrays."""
    r = requests.get(f"{KRAKEN_API}/OHLC", params={"pair": pair, "interval": interval}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        if key != "last":
            return val  # [time, open, high, low, close, vwap, volume, count]
    return []


def get_order_book(pair, count=10):
    """Fetch top N bid/ask levels of the order book."""
    r = requests.get(f"{KRAKEN_API}/Depth", params={"pair": pair, "count": count}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        return val  # {"bids": [...], "asks": [...]}
    return {}


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ══════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ══════════════════════════════════════════════════════════════

def detect_volume_spike(ticker_data):
    """
    Signal 1 — Volume Spike.
    Today's volume >= TODAY_VOL_RATIO of the full rolling 24h volume.
    Indicates abnormally fast accumulation compared to recent baseline.
    Returns (triggered: bool, ratio: float)
    """
    try:
        vol_today = float(ticker_data["v"][0])   # volume since midnight UTC
        vol_24h   = float(ticker_data["v"][1])   # rolling 24h volume
        if vol_24h <= 0:
            return False, 0.0
        ratio = vol_today / vol_24h
        return ratio >= TODAY_VOL_RATIO, ratio
    except Exception:
        return False, 0.0


def detect_price_momentum(pair_id):
    """
    Signal 2 — Price Momentum.
    Measures % move from the open of the oldest 1h candle to the latest close.
    Fires when the absolute move exceeds PRICE_MOVE_THRESHOLD.
    Returns (triggered: bool, change: float)
    """
    try:
        candles = get_ohlc(pair_id, interval=60)
        if not candles or len(candles) < 2:
            return False, 0.0
        open_price  = float(candles[0][1])
        close_price = float(candles[-1][4])
        if open_price == 0:
            return False, 0.0
        change = (close_price - open_price) / open_price
        return abs(change) >= PRICE_MOVE_THRESHOLD, change
    except Exception:
        return False, 0.0


def detect_order_book_whales(pair_id):
    """
    Signal 3 — Whale Order Wall.
    Checks top-10 bid/ask levels for any single order >= ORDER_BOOK_WALL_USD.
    Returns list of whale order dicts.
    """
    try:
        book   = get_order_book(pair_id, count=10)
        whales = []
        for side in ("bids", "asks"):
            for level in book.get(side, []):
                price     = float(level[0])
                volume    = float(level[1])
                usd_value = price * volume
                if usd_value >= ORDER_BOOK_WALL_USD:
                    whales.append({
                        "side":      "BUY wall"  if side == "bids" else "SELL wall",
                        "price":     price,
                        "volume":    volume,
                        "usd_value": usd_value,
                    })
        return whales
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# MAIN SCAN
# ══════════════════════════════════════════════════════════════

def scan_for_whales():
    """
    Scans all Kraken USD/USDT altcoins under $2.
    Returns a sorted list of alert dicts for coins with >= SIGNALS_REQUIRED signals.
    """
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Starting Kraken whale scan...")

    all_pairs = get_all_kraken_pairs()
    print(f"  Found {len(all_pairs)} USD/USDT pairs on Kraken")

    alerts  = []
    scanned = 0

    for batch in chunk_list(all_pairs, 50):
        try:
            ticker_data = get_ticker_batch(batch)
        except Exception as e:
            print(f"  Ticker batch error: {e}")
            continue

        for pair_id, t in ticker_data.items():
            try:
                last_price = float(t["c"][0])
                vwap_24h   = float(t["p"][1])
                vol_24h    = float(t["v"][1])
                volume_usd = vol_24h * vwap_24h
                high_24h   = float(t["h"][1])
                low_24h    = float(t["l"][1])

                # ── Pre-filters ──────────────────────────────────
                if last_price <= 0 or last_price >= MAX_PRICE_USD:
                    continue
                if volume_usd < MIN_VOLUME_USD:
                    continue

                scanned += 1

                # ── Signal 1: Volume spike ────────────────────────
                vol_spike, spike_ratio = detect_volume_spike(t)

                # ── Signal 2: Price momentum ──────────────────────
                price_move, price_change = detect_price_momentum(pair_id)

                # ── Signal 3: Order book whale walls ──────────────
                # Only fetch order book if at least 1 signal already triggered (saves calls)
                ob_whales = []
                if vol_spike or price_move:
                    ob_whales = detect_order_book_whales(pair_id)

                # ── Combine + threshold ───────────────────────────
                signal_count = sum([vol_spike, price_move, bool(ob_whales)])

                if signal_count >= SIGNALS_REQUIRED:
                    range_pct = ((high_24h - low_24h) / low_24h * 100) if low_24h > 0 else 0
                    alerts.append({
                        "pair":         pair_id,
                        "price":        last_price,
                        "price_change": price_change,
                        "volume_usd":   volume_usd,
                        "spike_ratio":  spike_ratio,
                        "vol_spike":    vol_spike,
                        "price_move":   price_move,
                        "ob_whales":    ob_whales,
                        "signal_count": signal_count,
                        "high_24h":     high_24h,
                        "low_24h":      low_24h,
                        "range_pct":    range_pct,
                    })

            except Exception:
                pass

        time.sleep(0.5)  # be polite to Kraken's API

    alerts.sort(key=lambda x: -x["signal_count"])
    print(f"  Scanned {scanned} eligible coins. Found {len(alerts)} whale alert(s).")
    return alerts


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# — matches the visual style of your Phase 1 / Phase 2 emails
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#f4f4f4;margin:0;padding:20px;color:#222;}
.wrap{max-width:660px;margin:0 auto;}
.header{background:linear-gradient(135deg,#0d1b4b,#4a148c);color:#fff;
  padding:26px 28px;border-radius:14px 14px 0 0;}
.header h1{margin:0;font-size:21px;font-weight:700;}
.header p{margin:6px 0 0;font-size:13px;opacity:.8;}
.body{background:#fff;border:1px solid #e2e2e2;border-top:none;
  border-radius:0 0 14px 14px;padding-bottom:24px;}
.section{padding:20px 22px 0;}
.section-head{font-size:12px;font-weight:700;color:#666;text-transform:uppercase;
  letter-spacing:.7px;border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:12px;}
.stock-card{border:1px solid #eaeaea;border-radius:10px;margin-bottom:12px;overflow:hidden;}
.card-top{background:#fafafa;padding:12px 16px;display:flex;
  justify-content:space-between;align-items:flex-start;border-bottom:1px solid #eee;}
.sym{font-size:17px;font-weight:700;}
.price{font-size:17px;font-weight:600;text-align:right;}
.score-pill{display:inline-block;padding:3px 11px;border-radius:12px;font-size:12px;font-weight:700;}
.meta{display:flex;flex-wrap:wrap;gap:14px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:1px;}
.meta-item .val{font-size:12px;font-weight:600;}
.bar-wrap{padding:4px 16px 8px;}
.signals{padding:6px 16px 10px;}
.signal-row{font-size:13px;color:#333;padding:4px 0;line-height:1.5;
  border-bottom:1px solid #f5f5f5;}
.signal-row:last-child{border:none;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.6;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 10px;}
.summary-stat .num{font-size:24px;font-weight:700;}
.summary-stat .desc{font-size:11px;color:#888;}
</style>
"""


def signal_pill(count):
    if count >= 3:   bg, col = "#D4F5E9", "#0A5D3E"
    elif count == 2: bg, col = "#FEF3DC", "#7A4900"
    else:            bg, col = "#F0F0F0", "#444"
    return f'<span class="score-pill" style="background:{bg};color:{col};">{count}/3 signals</span>'


def price_bar_html(price, low, high):
    if not all([price, low, high]) or high == low:
        return ""
    pct   = max(0, min(100, (price - low) / (high - low) * 100))
    color = "#1D9E75" if pct < 35 else "#EF9F27" if pct < 65 else "#E24B4A"
    return (f'<div style="font-size:10px;color:#bbb;margin-bottom:3px;">'
            f'24h range position — {pct:.0f}% from low</div>'
            f'<div style="background:#eee;border-radius:3px;height:5px;">'
            f'<div style="background:{color};width:{pct:.0f}%;height:5px;border-radius:3px;"></div></div>')


def build_coin_card(a):
    change_color = "#1D9E75" if a["price_change"] >= 0 else "#E24B4A"
    change_sign  = "+" if a["price_change"] >= 0 else ""

    signal_rows = ""
    if a["vol_spike"]:
        signal_rows += (f'<div class="signal-row">🔥 <strong>Volume spike</strong> — '
                        f'{a["spike_ratio"]:.1%} of 24h volume already traded today</div>')
    if a["price_move"]:
        arrow = "📈" if a["price_change"] > 0 else "📉"
        signal_rows += (f'<div class="signal-row">{arrow} <strong>Price momentum</strong> — '
                        f'{change_sign}{a["price_change"]:.2%} move in recent candles</div>')
    for w in a["ob_whales"]:
        signal_rows += (f'<div class="signal-row">🐋 <strong>{w["side"]}</strong> — '
                        f'${w["usd_value"]:,.0f} order @ ${w["price"]:.6f}</div>')

    pbar = price_bar_html(a["price"], a["low_24h"], a["high_24h"])

    return f"""<div class="stock-card">
  <div class="card-top">
    <div>
      <div class="sym">{a['pair']}</div>
      <div style="font-size:11px;color:#999;margin-top:2px;">Kraken · altcoin under $2</div>
    </div>
    <div>
      <div class="price">${a['price']:.6f}</div>
      <div style="font-size:11px;color:{change_color};text-align:right;margin-top:2px;font-weight:600;">
        {change_sign}{a['price_change']:.2%} recent move
      </div>
      <div style="text-align:right;margin-top:4px;">{signal_pill(a['signal_count'])}</div>
    </div>
  </div>
  <div class="meta">
    <div class="meta-item"><div class="lbl">24h Volume</div><div class="val">${a['volume_usd']:,.0f}</div></div>
    <div class="meta-item"><div class="lbl">24h High</div><div class="val">${a['high_24h']:.6f}</div></div>
    <div class="meta-item"><div class="lbl">24h Low</div><div class="val">${a['low_24h']:.6f}</div></div>
    <div class="meta-item"><div class="lbl">24h Range</div><div class="val">{a['range_pct']:.1f}%</div></div>
  </div>
  <div class="bar-wrap">{pbar}</div>
  <div class="signals">{signal_rows}</div>
</div>"""


def build_html_email(alerts):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    top3 = [a for a in alerts if a["signal_count"] == 3]
    top2 = [a for a in alerts if a["signal_count"] == 2]

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">

<div class="header">
  <h1>🐋 Phase 3 · Kraken Whale Alert</h1>
  <p>{date_str}</p>
</div>

<div class="body">

  <div style="display:flex;justify-content:space-around;padding:18px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat">
      <div class="num" style="color:#4a148c;">{len(alerts)}</div>
      <div class="desc">Coins flagged</div>
    </div>
    <div class="summary-stat">
      <div class="num" style="color:#0F6E56;">{len(top3)}</div>
      <div class="desc">All 3 signals 🔥</div>
    </div>
    <div class="summary-stat">
      <div class="num" style="color:#EF9F27;">{len(top2)}</div>
      <div class="desc">2 signals 📈</div>
    </div>
  </div>

  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      These Kraken altcoins under $2 triggered at least <strong>2 of 3 whale signals</strong>
      simultaneously: volume spike, price momentum, and/or large order walls.<br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Do your own research before trading.</strong>
    </p>
  </div>
"""

    if top3:
        html += '<div class="section"><div class="section-head">🔥 All 3 Signals — Highest Conviction</div>'
        for a in top3:
            html += build_coin_card(a)
        html += '</div><div class="divider"></div>'

    if top2:
        html += '<div class="section"><div class="section-head">📈 2 Signals — Worth Watching</div>'
        for a in top2:
            html += build_coin_card(a)
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Kraken Whale Tracker (Phase 3) · Runs every 15 min via GitHub Actions<br>
    Signals: 🔥 Volume spike (60%+ of 24h done today) ·
    📈 Price momentum (3%+ move) ·
    🐋 Order wall ($25k+ single order)<br>
    Research and education only — not financial advice.<br>
    <a href="https://www.kraken.com/trade" style="color:#7c4dff;">Open Kraken →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(alerts):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 60,
        f" KRAKEN WHALE ALERT (Phase 3) — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f" {len(alerts)} coin(s) flagged",
        "=" * 60,
    ]
    for a in alerts:
        lines.append(f"\n  {'─'*55}")
        lines.append(f"  {a['pair']:<20}  ${a['price']:.6f}  ({a['price_change']:+.2%})")
        lines.append(f"  24h Volume: ${a['volume_usd']:,.0f}  |  Signals: {a['signal_count']}/3")
        if a["vol_spike"]:
            lines.append(f"    🔥 Volume spike — {a['spike_ratio']:.1%} of 24h done today")
        if a["price_move"]:
            lines.append(f"    📈 Price move — {a['price_change']:+.2%}")
        for w in a["ob_whales"]:
            lines.append(f"    🐋 {w['side']} ${w['usd_value']:,.0f} @ ${w['price']:.6f}")
    lines += ["", "=" * 60, " Research only — not financial advice.", "=" * 60]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# SEND EMAIL
# ══════════════════════════════════════════════════════════════

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

    print(f"✅ Whale alert sent → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def run():
    now = datetime.now(timezone.utc)
    print(f"🐋 Kraken Whale Tracker (Phase 3) — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    alerts = scan_for_whales()

    if not alerts:
        print("  No whale activity detected this run. No email sent.")
        return

    html_body  = build_html_email(alerts)
    text_body  = build_text_email(alerts)
    top_pair   = alerts[0]["pair"]
    top_sigs   = alerts[0]["signal_count"]
    subject    = (f"🐋 Whale Alert: {len(alerts)} Kraken Altcoin(s) Moving · "
                  f"Top: {top_pair} ({top_sigs}/3 signals) · "
                  f"{now.strftime('%H:%M UTC')}")

    print(text_body)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Email not sent — set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
