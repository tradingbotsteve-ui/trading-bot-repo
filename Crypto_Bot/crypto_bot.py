import requests
import time
from datetime import datetime, timezone


KRAKEN_BASE = "https://api.kraken.com/0/public"


def fetch_asset_pairs():
    """Fetch all spot asset pairs from Kraken."""
    resp = requests.get(f"{KRAKEN_BASE}/AssetPairs", timeout=10)
    resp.raise_for_status()
    data = resp.json()["result"]
    # Keep only crypto vs USD/USDT pairs (simpler for now)
    pairs = {
        name: info
        for name, info in data.items()
        if info.get("quote") in ("ZUSD", "USDT")
    }
    return pairs


def fetch_tickers(pairs):
    """Fetch ticker info for given pairs."""
    pair_list = ",".join(pairs.keys())
    resp = requests.get(
        f"{KRAKEN_BASE}/Ticker",
        params={"pair": pair_list},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["result"]


def fetch_ohlc(pair, interval=1440):
    """Fetch OHLC candles (daily by default)."""
    params = {"pair": pair, "interval": interval}
    resp = requests.get(f"{KRAKEN_BASE}/OHLC", params=params, timeout=15)
    resp.raise_for_status()
    result = resp.json()["result"]
    candles = result[pair]
    # candles: [time, open, high, low, close, vwap, volume, count]
    return [
        {
            "time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "vwap": float(c[5]),
            "volume": float(c[6]),
            "count": int(c[7]),
        }
        for c in candles
    ]


def simple_moving_average(values, window):
    if len(values) < window:
        return [None] * len(values)
    sma = []
    for i in range(len(values)):
        if i + 1 < window:
            sma.append(None)
        else:
            window_vals = values[i + 1 - window : i + 1]
            sma.append(sum(window_vals) / window)
    return sma


def rsi(values, period=14):
    if len(values) < period + 1:
        return [None] * len(values)

    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsis = [None] * (period)  # first 'period' entries are None

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rs = float("inf")
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100 - (100 / (1 + rs))
        rsis.append(rsi_val)

    # align length with original prices
    rsis.insert(0, None)
    return rsis


def analyze_pair(pair_name, ticker_info):
    """Compute metrics for a single pair."""
    last_price = float(ticker_info["c"][0])
    if last_price >= 1.0:
        return None

    vol_24h = float(ticker_info["v"][1])
    if vol_24h < 50000:  # tune this if you want
        return None

    candles = fetch_ohlc(pair_name, interval=1440)
    if len(candles) < 25:
        return None

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]

    ma7 = simple_moving_average(closes, 7)
    ma21 = simple_moving_average(closes, 21)
    rsi14 = rsi(closes, period=14)

    # simple 3-day volume MA
    vol_ma3 = simple_moving_average(volumes, 3)

    # use last and previous index
    last_idx = len(closes) - 1
    prev_idx = len(closes) - 2

    if (
        ma7[last_idx] is None
        or ma21[last_idx] is None
        or rsi14[last_idx] is None
        or vol_ma3[last_idx] is None
        or rsi14[prev_idx] is None
        or vol_ma3[prev_idx] is None
    ):
        return None

    ma_bullish = ma7[last_idx] > ma21[last_idx]
    rsi_rising = rsi14[last_idx] > rsi14[prev_idx]
    vol_rising = vol_ma3[last_idx] > vol_ma3[prev_idx]

    score = 0
    if ma_bullish:
        score += 1
    if rsi_rising:
        score += 1
    if vol_rising:
        score += 1

    return {
        "pair": pair_name,
        "price": last_price,
        "vol_24h": vol_24h,
        "ma_bullish": ma_bullish,
        "rsi_latest": rsi14[last_idx],
        "rsi_prev": rsi14[prev_idx],
        "vol_rising": vol_rising,
        "score": score,
    }


def main():
    print("=== Kraken < $1 Scanner (Daily) ===")
    print("Run time (UTC):", datetime.now(timezone.utc).isoformat())

    pairs = fetch_asset_pairs()
    print(f"Total USD/USDT pairs: {len(pairs)}")

    tickers = fetch_tickers(pairs)

    results = []
    for pair_name, tinfo in tickers.items():
        try:
            res = analyze_pair(pair_name, tinfo)
            if res and res["score"] >= 2:  # at least 2 bullish signals
                results.append(res)
            time.sleep(0.5)  # be nice to API
        except Exception as e:
            print(f"Error analyzing {pair_name}: {e}")

    results.sort(key=lambda x: (x["score"], x["vol_24h"]), reverse=True)

    print("\n=== Top Candidates (2–3 week swing bias, under $1) ===")
    if not results:
        print("No candidates today with current filters.")
        return

    for r in results[:10]:
        print(
            f"{r['pair']}: price=${r['price']:.4f}, "
            f"score={r['score']}, "
            f"RSI {r['rsi_prev']:.1f}→{r['rsi_latest']:.1f}, "
            f"24h vol={r['vol_24h']:.0f}"
        )

    print("\nThis is a momentum/volume scan, not guaranteed profit. Always size risk properly.")


if __name__ == "__main__":
    main()
