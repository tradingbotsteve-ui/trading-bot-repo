import requests
import time
import pandas as pd
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


def fetch_ohlc(pair, interval=1440, since=None):
    """Fetch OHLC candles (daily by default)."""
    params = {"pair": pair, "interval": interval}
    if since:
        params["since"] = since
    resp = requests.get(f"{KRAKEN_BASE}/OHLC", params=params, timeout=15)
    resp.raise_for_status()
    result = resp.json()["result"]
    # result has {pair: [[time, open, high, low, close, vwap, volume, count], ...], 'last': ...}
    candles = result[pair]
    df = pd.DataFrame(
        candles,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "count",
        ],
    )
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df


def rsi(series, period=14):
    """Simple RSI implementation."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val


def analyze_pair(pair_name, ticker_info):
    """Compute metrics for a single pair."""
    last_price = float(ticker_info["c"][0])
    # Filter by price < 1
    if last_price >= 1.0:
        return None

    # Basic 24h volume filter (in quote currency)
    vol_24h = float(ticker_info["v"][1])
    if vol_24h < 50000:  # you can tune this
        return None

    # Fetch last ~40 days of daily candles
    df = fetch_ohlc(pair_name, interval=1440)
    if len(df) < 25:
        return None

    df = df.sort_values("time")
    df["ma7"] = df["close"].rolling(window=7).mean()
    df["ma21"] = df["close"].rolling(window=21).mean()
    df["rsi14"] = rsi(df["close"], period=14)
    df["vol_ma3"] = df["volume"].rolling(window=3).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    ma_bullish = latest["ma7"] > latest["ma21"]
    rsi_rising = latest["rsi14"] > prev["rsi14"]
    vol_rising = latest["vol_ma3"] > prev["vol_ma3"]

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
        "rsi_latest": latest["rsi14"],
        "rsi_prev": prev["rsi14"],
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
            # Be nice to API
            time.sleep(0.5)
        except Exception as e:
            print(f"Error analyzing {pair_name}: {e}")

    # Sort by score then volume
    results.sort(key=lambda x: (x["score"], x["vol_24h"]), reverse=True)

    print("\n=== Top Candidates (swing-style, 2–3 week bias) ===")
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

    print("\nNOTE: This is NOT guaranteed prediction. It’s just momentum/volume structure under $1 on Kraken.")


if __name__ == "__main__":
    main()
