import os, smtplib, requests, time
from datetime import datetime, timezone
from email.mime.text import MIMEText

# ── EMAIL SECRETS (same style as Phase 2 + 3) ───────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")

# ── Kraken API base ─────────────────────────────────────────────────────────
KRAKEN_BASE = "https://api.kraken.com/0/public"


# ── EMAIL SENDER (same pattern as your Phase 2 + 3 bots) ────────────────────
def send_email(subject, body):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())


# ── Kraken helpers ──────────────────────────────────────────────────────────
def fetch_asset_pairs():
    resp = requests.get(f"{KRAKEN_BASE}/AssetPairs", timeout=10)
    resp.raise_for_status()
    data = resp.json()["result"]
    return {
        name: info
        for name, info in data.items()
        if info.get("quote") in ("ZUSD", "USDT")
    }


def fetch_tickers(pairs):
    pair_list = ",".join(pairs.keys())
    resp = requests.get(f"{KRAKEN_BASE}/Ticker", params={"pair": pair_list}, timeout=15)
    resp.raise_for_status()
    return resp.json()["result"]


def fetch_ohlc(pair, interval=1440):
    resp = requests.get(f"{KRAKEN_BASE}/OHLC", params={"pair": pair, "interval": interval}, timeout=15)
    resp.raise_for_status()
    candles = resp.json()["result"][pair]
    return [
        {
            "time": int(c[0]),
            "close": float(c[4]),
            "volume": float(c[6]),
        }
        for c in candles
    ]


# ── Simple indicators (no pandas) ───────────────────────────────────────────
def sma(values, window):
    if len(values) < window:
        return [None] * len(values)
    out = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(sum(values[i + 1 - window:i + 1]) / window)
    return out


def rsi(values, period=14):
    if len(values) < period + 1:
        return [None] * len(values)

    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsis = [None] * period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsis.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsis.append(100 - (100 / (1 + rs)))

    rsis.insert(0, None)
    return rsis


# ── Analyze each pair ───────────────────────────────────────────────────────
def analyze_pair(pair_name, ticker_info):
    price = float(ticker_info["c"][0])
    if price >= 1:
        return None

    vol_24h = float(ticker_info["v"][1])
    if vol_24h < 50000:
        return None

    candles = fetch_ohlc(pair_name)
    if len(candles) < 25:
        return None

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]

    ma7 = sma(closes, 7)
    ma21 = sma(closes, 21)
    rsi14 = rsi(closes, 14)
    vol3 = sma(volumes, 3)

    i = len(closes) - 1
    j = len(closes) - 2

    if None in (ma7[i], ma21[i], rsi14[i], rsi14[j], vol3[i], vol3[j]):
        return None

    score = 0
    if ma7[i] > ma21[i]: score += 1
    if rsi14[i] > rsi14[j]: score += 1
    if vol3[i] > vol3[j]: score += 1

    return {
        "pair": pair_name,
        "price": price,
        "vol_24h": vol_24h,
        "score": score,
        "rsi_prev": rsi14[j],
        "rsi_now": rsi14[i],
    }


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    pairs = fetch_asset_pairs()
    tickers = fetch_tickers(pairs)

    results = []
    for pair, info in tickers.items():
        try:
            r = analyze_pair(pair, info)
            if r and r["score"] >= 2:
                results.append(r)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {pair} → {e}")

    results.sort(key=lambda x: (x["score"], x["vol_24h"]), reverse=True)

    body = f"Daily Crypto Bot Report\nRun: {datetime.now(timezone.utc)}\n\n"

    if not results:
        body += "No qualifying tokens today."
    else:
        for r in results[:10]:
            body += (
                f"{r['pair']} | ${r['price']:.4f} | score={r['score']} | "
                f"RSI {r['rsi_prev']:.1f}->{r['rsi_now']:.1f} | vol={r['vol_24h']:.0f}\n"
            )

    send_email("Daily Crypto Bot Report", body)


if __name__ == "__main__":
    main()
