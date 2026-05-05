# ============================================================
# TRADING BOT — PHASE 3 (Kraken Whale Tracker + Buy Advisor)
#
# Monitors ALL altcoins under $2 on Kraken (600+).
# Detects whale movements via volume spikes, price momentum,
# and large order book walls.
# Scores each coin for LONG-TERM buy potential and recommends
# which ones are worth entering for a sustained ride.
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
    Returns (triggered: bool, change: float, candles: list)
    """
    try:
        candles = get_ohlc(pair_id, interval=60)
        if not candles or len(candles) < 2:
            return False, 0.0, []
        open_price  = float(candles[0][1])
        close_price = float(candles[-1][4])
        if open_price == 0:
            return False, 0.0, []
        change = (close_price - open_price) / open_price
        return abs(change) >= PRICE_MOVE_THRESHOLD, change, candles
    except Exception:
        return False, 0.0, []


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
# LONG-TERM BUY CONVICTION SCORER
#
# Scores each flagged coin 0–100 for long-term buy potential.
# Uses data already pulled — no extra API calls.
#
# PILLARS (what makes a coin worth holding, not just a pump):
#   1. Price position in 24h range  — buying near the low = better entry
#   2. BUY wall vs SELL wall ratio  — whales positioning to buy = bullish
#   3. Volume spike strength        — how explosive the accumulation is
#   4. Price momentum direction     — upward move = trend confirmation
#   5. Candle structure             — steady climb vs one big spike (pump risk)
#
# VERDICT:
#   80–100 → 🟢 STRONG BUY   — all signals aligned, enter early
#   60–79  → 🟡 WATCH        — good setup, wait for one more candle to confirm
#   0–59   → 🔴 SKIP         — too risky, mid-wave, or whale selling
# ══════════════════════════════════════════════════════════════

def score_long_term_conviction(alert, candles):
    """
    Returns (score: int 0-100, verdict: str, verdict_color: str,
             verdict_bg: str, verdict_note: str, reasons: list[str])
    """
    score   = 0
    reasons = []

    price  = alert["price"]
    low    = alert["low_24h"]
    high   = alert["high_24h"]
    change = alert["price_change"]

    # ── Pillar 1: Entry position in 24h range (25 pts) ───────
    # Buying near the low = entering early, not chasing a pump
    if high > low:
        pct_from_low = (price - low) / (high - low)
        if pct_from_low < 0.25:
            score += 25
            reasons.append("📍 Price near 24h low — excellent early entry, wave likely just starting")
        elif pct_from_low < 0.45:
            score += 18
            reasons.append("📍 Price in lower half of 24h range — still a good entry point")
        elif pct_from_low < 0.65:
            score += 10
            reasons.append("📍 Price mid-range — acceptable entry but not ideal")
        else:
            score += 3
            reasons.append("⚠️ Price near 24h high — risk of chasing the top of the move")

    # ── Pillar 2: BUY wall vs SELL wall dominance (25 pts) ───
    # More whale buy pressure = whales are accumulating, not distributing
    buy_walls  = [w for w in alert["ob_whales"] if w["side"] == "BUY wall"]
    sell_walls = [w for w in alert["ob_whales"] if w["side"] == "SELL wall"]
    buy_usd    = sum(w["usd_value"] for w in buy_walls)
    sell_usd   = sum(w["usd_value"] for w in sell_walls)

    if buy_usd > 0 and sell_usd == 0:
        score += 25
        reasons.append(f"🐋 Pure BUY pressure — ${buy_usd:,.0f} whale buy walls, zero sell walls")
    elif buy_usd > sell_usd * 2:
        score += 20
        reasons.append(f"🐋 BUY walls dominate (${buy_usd:,.0f} buy vs ${sell_usd:,.0f} sell)")
    elif buy_usd > sell_usd:
        score += 12
        reasons.append(f"🐋 More buy than sell pressure (${buy_usd:,.0f} vs ${sell_usd:,.0f})")
    elif sell_usd > buy_usd * 2:
        score += 0
        reasons.append(f"🚧 SELL walls dominate (${sell_usd:,.0f}) — whales may be exiting, caution")
    else:
        score += 8  # no walls but other signals strong
        reasons.append("📊 No large order walls — momentum driven by volume/price alone")

    # ── Pillar 3: Volume spike strength (20 pts) ──────────────
    # Stronger volume anomaly = more conviction behind the move
    ratio = alert["spike_ratio"]
    if ratio >= 0.85:
        score += 20
        reasons.append(f"🔥 Extreme volume — {ratio:.0%} of 24h already traded (massive accumulation)")
    elif ratio >= 0.70:
        score += 15
        reasons.append(f"🔥 Strong volume spike — {ratio:.0%} of 24h traded today")
    elif ratio >= 0.60:
        score += 10
        reasons.append(f"🔥 Volume spike triggered — {ratio:.0%} of 24h traded today")
    else:
        score += 4
        reasons.append(f"📊 Mild volume — {ratio:.0%} of 24h traded today")

    # ── Pillar 4: Price momentum direction (15 pts) ───────────
    # Upward move confirms the wave is going the right way
    if change > 0.08:
        score += 15
        reasons.append(f"📈 Strong upward move +{change:.1%} — trend clearly established")
    elif change > 0.03:
        score += 11
        reasons.append(f"📈 Upward momentum +{change:.1%} — move in progress")
    elif change > 0:
        score += 7
        reasons.append(f"📈 Slight upward drift +{change:.1%} — possible early stage")
    elif change > -0.03:
        score += 5
        reasons.append(f"📊 Flat move {change:.1%} — volume leading price (watch for breakout)")
    else:
        score += 0
        reasons.append(f"📉 Downward move {change:.1%} — possible whale selling, high caution")

    # ── Pillar 5: Candle structure — sustained vs spike (15 pts)
    # Steady climb across multiple candles = healthier than one big pump candle
    if candles and len(candles) >= 4:
        try:
            closes  = [float(c[4]) for c in candles[-8:]]
            volumes = [float(c[6]) for c in candles[-8:]]
            rising  = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
            rising_pct = rising / (len(closes) - 1)
            max_vol    = max(volumes) if volumes else 1
            avg_vol    = sum(volumes) / len(volumes) if volumes else 1
            pump_spike = max_vol > avg_vol * 5  # single candle 5x avg = likely pump

            if rising_pct >= 0.70 and not pump_spike:
                score += 15
                reasons.append(f"📶 Healthy sustained climb — {rising}/{len(closes)-1} candles rising, volume spread evenly")
            elif rising_pct >= 0.50 and not pump_spike:
                score += 10
                reasons.append(f"📶 Mostly rising candles ({rising}/{len(closes)-1}) — decent structure")
            elif pump_spike:
                score += 3
                reasons.append("⚠️ Single-candle volume spike detected — pump risk, not a sustained wave")
            else:
                score += 5
                reasons.append(f"📊 Mixed candle structure ({rising}/{len(closes)-1} candles rising)")
        except Exception:
            score += 5

    score = min(score, 100)

    if score >= 80:
        verdict       = "🟢 STRONG BUY"
        verdict_color = "#0A5D3E"
        verdict_bg    = "#D4F5E9"
        verdict_note  = "All signals aligned — enter early and ride the wave"
    elif score >= 60:
        verdict       = "🟡 WATCH"
        verdict_color = "#7A4900"
        verdict_bg    = "#FEF3DC"
        verdict_note  = "Good setup — wait for one more confirming candle before entering"
    else:
        verdict       = "🔴 SKIP"
        verdict_color = "#8a1a1a"
        verdict_bg    = "#FDECEA"
        verdict_note  = "Too risky, mid-wave, or whale selling — let this one go"

    return score, verdict, verdict_color, verdict_bg, verdict_note, reasons


# ══════════════════════════════════════════════════════════════
# MAIN SCAN
# ══════════════════════════════════════════════════════════════

def scan_for_whales():
    """
    Scans all Kraken USD/USDT altcoins under $2.
    Returns a sorted list of alert dicts enriched with long-term buy verdicts.
    Sorted: Strong Buy first, then Watch, then Skip; by conviction score within each group.
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

                # ── Signal 2: Price momentum + candles ───────────
                price_move, price_change, candles = detect_price_momentum(pair_id)

                # ── Signal 3: Order book whale walls ──────────────
                ob_whales = []
                if vol_spike or price_move:
                    ob_whales = detect_order_book_whales(pair_id)

                # ── Combine + threshold ───────────────────────────
                signal_count = sum([vol_spike, price_move, bool(ob_whales)])

                if signal_count >= SIGNALS_REQUIRED:
                    range_pct = ((high_24h - low_24h) / low_24h * 100) if low_24h > 0 else 0

                    alert = {
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
                    }

                    # ── Score for long-term buy potential ─────────
                    (conv_score, verdict, verdict_color,
                     verdict_bg, verdict_note, conv_reasons) = score_long_term_conviction(alert, candles)

                    alert["conviction_score"] = conv_score
                    alert["verdict"]          = verdict
                    alert["verdict_color"]    = verdict_color
                    alert["verdict_bg"]       = verdict_bg
                    alert["verdict_note"]     = verdict_note
                    alert["conv_reasons"]     = conv_reasons

                    alerts.append(alert)

            except Exception:
                pass

        time.sleep(0.5)  # be polite to Kraken's API

    # Sort: Strong Buy → Watch → Skip, then by conviction score descending
    verdict_order = {"🟢 STRONG BUY": 0, "🟡 WATCH": 1, "🔴 SKIP": 2}
    alerts.sort(key=lambda x: (verdict_order.get(x["verdict"], 9), -x["conviction_score"]))

    print(f"  Scanned {scanned} eligible coins. Found {len(alerts)} whale alert(s).")
    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    print(f"  Strong Buy recommendations: {len(strong_buys)}")
    return alerts


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# — matches visual style of Phase 1 / Phase 2
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
.stock-card{border:1px solid #eaeaea;border-radius:10px;margin-bottom:14px;overflow:hidden;}
.card-top{background:#fafafa;padding:12px 16px;display:flex;
  justify-content:space-between;align-items:flex-start;border-bottom:1px solid #eee;}
.sym{font-size:17px;font-weight:700;}
.price{font-size:17px;font-weight:600;text-align:right;}
.score-pill{display:inline-block;padding:3px 11px;border-radius:12px;font-size:12px;font-weight:700;}
.meta{display:flex;flex-wrap:wrap;gap:14px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:1px;}
.meta-item .val{font-size:12px;font-weight:600;}
.bar-wrap{padding:4px 16px 8px;}
.signals{padding:6px 16px 6px;}
.signal-row{font-size:13px;color:#333;padding:4px 0;line-height:1.5;
  border-bottom:1px solid #f5f5f5;}
.signal-row:last-child{border:none;}
.verdict-box{margin:10px 16px 12px;padding:14px 16px;border-radius:8px;border-left:4px solid;}
.verdict-label{font-size:17px;font-weight:700;margin-bottom:3px;}
.verdict-score{font-size:12px;margin-bottom:5px;opacity:.8;}
.verdict-note{font-size:13px;font-weight:600;margin-bottom:10px;}
.reason-row{font-size:12px;padding:2px 0;color:#444;line-height:1.6;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.6;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 10px;}
.summary-stat .num{font-size:24px;font-weight:700;}
.summary-stat .desc{font-size:11px;color:#888;}
.top-picks-banner{background:linear-gradient(135deg,#0A5D3E,#1D9E75);
  margin:16px 22px 0;padding:16px 18px;border-radius:10px;color:#fff;}
.top-picks-banner h2{margin:0 0 4px;font-size:16px;font-weight:700;}
.top-picks-banner p{margin:0 0 12px;font-size:12px;opacity:.85;}
.pick-row{display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.2);}
.pick-row:last-child{border:none;padding-bottom:0;}
.pick-name{font-size:15px;font-weight:700;}
.pick-detail{font-size:12px;opacity:.85;margin-top:1px;}
.pick-score{font-size:13px;background:rgba(255,255,255,0.25);
  padding:3px 10px;border-radius:10px;font-weight:700;white-space:nowrap;}
</style>
"""


def signal_pill(count):
    if count >= 3:   bg, col = "#D4F5E9", "#0A5D3E"
    elif count == 2: bg, col = "#FEF3DC", "#7A4900"
    else:            bg, col = "#F0F0F0", "#444"
    return f'<span class="score-pill" style="background:{bg};color:{col};">{count}/3 whale signals</span>'


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

    # Whale signal rows
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

    # Long-term conviction reasons
    conv_reasons_html = "".join(
        f'<div class="reason-row">• {r}</div>' for r in a["conv_reasons"]
    )

    verdict_box = f"""<div class="verdict-box"
  style="background:{a['verdict_bg']};border-left-color:{a['verdict_color']};">
  <div class="verdict-label" style="color:{a['verdict_color']};">{a['verdict']}</div>
  <div class="verdict-score" style="color:{a['verdict_color']};">
    Long-term conviction score: <strong>{a['conviction_score']}/100</strong>
  </div>
  <div class="verdict-note" style="color:{a['verdict_color']};">{a['verdict_note']}</div>
  {conv_reasons_html}
</div>"""

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
  {verdict_box}
</div>"""


def build_top_picks_banner(strong_buys):
    """Prominent green banner at the top of the email — your quick-glance buy list."""
    if not strong_buys:
        return ""
    rows = ""
    for a in strong_buys[:5]:
        change_sign = "+" if a["price_change"] >= 0 else ""
        rows += f"""<div class="pick-row">
    <div>
      <div class="pick-name">{a['pair']}</div>
      <div class="pick-detail">${a['price']:.6f} &nbsp;·&nbsp; {change_sign}{a['price_change']:.2%} &nbsp;·&nbsp; Vol ${a['volume_usd']:,.0f}</div>
    </div>
    <div class="pick-score">{a['conviction_score']}/100</div>
  </div>"""

    return f"""<div class="top-picks-banner">
  <h2>🟢 Strong Buy Picks — {len(strong_buys)} Coin{'s' if len(strong_buys)>1 else ''} to Enter Now</h2>
  <p>These have the best long-term entry conditions right now. Full analysis below each card.</p>
  {rows}
</div>"""


def build_html_email(alerts):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    watches     = [a for a in alerts if a["verdict"] == "🟡 WATCH"]
    skips       = [a for a in alerts if a["verdict"] == "🔴 SKIP"]

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">

<div class="header">
  <h1>🐋 Phase 3 · Kraken Whale Alert + Buy Advisor</h1>
  <p>{date_str}</p>
</div>

<div class="body">

  <div style="display:flex;justify-content:space-around;padding:18px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat">
      <div class="num" style="color:#4a148c;">{len(alerts)}</div>
      <div class="desc">Coins flagged</div>
    </div>
    <div class="summary-stat">
      <div class="num" style="color:#0F6E56;">{len(strong_buys)}</div>
      <div class="desc">🟢 Strong Buy</div>
    </div>
    <div class="summary-stat">
      <div class="num" style="color:#EF9F27;">{len(watches)}</div>
      <div class="desc">🟡 Watch</div>
    </div>
    <div class="summary-stat">
      <div class="num" style="color:#E24B4A;">{len(skips)}</div>
      <div class="desc">🔴 Skip</div>
    </div>
  </div>

  {build_top_picks_banner(strong_buys)}

  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      Each coin gets a <strong>0–100 long-term conviction score</strong> based on:
      entry position in range, whale order direction, volume strength, price momentum,
      and candle structure. Only coins with whale signals AND early-entry conditions
      score Strong Buy.<br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Always do your own research before trading.</strong>
    </p>
  </div>
"""

    if strong_buys:
        html += '<div class="section"><div class="section-head">🟢 Strong Buy — Enter Early, Ride the Wave</div>'
        for a in strong_buys:
            html += build_coin_card(a)
        html += '</div><div class="divider"></div>'

    if watches:
        html += '<div class="section"><div class="section-head">🟡 Watch — Good Setup, Wait for Confirmation</div>'
        for a in watches:
            html += build_coin_card(a)
        html += '</div><div class="divider"></div>'

    if skips:
        html += '<div class="section"><div class="section-head">🔴 Skip — Mid-Wave, Risky or Whale Selling</div>'
        for a in skips:
            html += build_coin_card(a)
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Kraken Whale Tracker + Buy Advisor (Phase 3) · Runs every 15 min via GitHub Actions<br>
    Whale signals: 🔥 Volume spike · 📈 Price momentum · 🐋 Order wall ($25k+)<br>
    Conviction score: entry position · whale order direction · volume · candle structure<br>
    Research and education only — not financial advice.<br>
    <a href="https://www.kraken.com/trade" style="color:#7c4dff;">Open Kraken →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(alerts):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 65,
        f" KRAKEN WHALE ALERT + BUY ADVISOR (Phase 3)",
        f" {now.strftime('%Y-%m-%d %H:%M UTC')} — {len(alerts)} coin(s) flagged",
        "=" * 65,
    ]

    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    if strong_buys:
        lines.append("\n🟢 STRONG BUY — Enter these now:")
        for a in strong_buys:
            lines.append(f"  ► {a['pair']:<20} ${a['price']:.6f}  conviction {a['conviction_score']}/100")

    lines.append("\n── FULL DETAILS ─────────────────────────────────────────────")
    for a in alerts:
        lines.append(f"\n  {a['pair']:<20}  ${a['price']:.6f}  ({a['price_change']:+.2%})")
        lines.append(f"  24h Vol: ${a['volume_usd']:,.0f}  |  Whale signals: {a['signal_count']}/3")
        lines.append(f"  {a['verdict']}  (conviction {a['conviction_score']}/100)")
        lines.append(f"  → {a['verdict_note']}")
        if a["vol_spike"]:
            lines.append(f"    🔥 Volume spike — {a['spike_ratio']:.1%} of 24h done today")
        if a["price_move"]:
            lines.append(f"    📈 Price move — {a['price_change']:+.2%}")
        for w in a["ob_whales"]:
            lines.append(f"    🐋 {w['side']} ${w['usd_value']:,.0f} @ ${w['price']:.6f}")
        for r in a["conv_reasons"]:
            lines.append(f"    • {r}")

    lines += ["", "=" * 65, " Research only — not financial advice.", "=" * 65]
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
    print(f"🐋 Kraken Whale Tracker + Buy Advisor (Phase 3) — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    alerts = scan_for_whales()

    if not alerts:
        print("  No whale activity detected this run. No email sent.")
        return

    html_body   = build_html_email(alerts)
    text_body   = build_text_email(alerts)
    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]

    buy_tag = f" · 🟢 BUY: {', '.join(a['pair'] for a in strong_buys[:3])}" if strong_buys else ""
    subject = (f"🐋 Whale Alert: {len(alerts)} coins · "
               f"{len(strong_buys)} Strong Buy{buy_tag} · "
               f"{now.strftime('%H:%M UTC')}")

    print(text_body)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Email not sent — set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
