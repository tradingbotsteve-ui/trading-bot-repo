# ============================================================
#  TRADING BOT — PHASE 4: CRYPTO ALTCOIN BRIEF
#  File: crypto_bot.py
#
#  Runs at 9:00 AM Pacific via GitHub Actions.
#  Sends one email: "🪙 Crypto Altcoin Brief"
#
#  What it does:
#    - Scans Kraken exchange for all altcoins under $2 USD
#    - Fetches live price, volume, 24h change from Kraken API
#    - Calculates momentum, volume spikes, RSI-style signals
#    - Fetches news headlines and sentiment per coin
#    - Explains in plain English WHY each coin is trending
#    - Gives a clear verdict: BUY WATCH / AVOID
#    - Same card-style email as your Phase 1 morning report
#
#  Canada-specific:
#    - Uses Kraken (FINTRAC registered, available in all provinces)
#    - CAD and USD pairs supported
#    - No options, no margin — spot trading research only
#
#  GitHub Secrets needed (same as your other bots):
#    ALPHA_VANTAGE_KEY, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT
#
#  ⚠️ Crypto is extremely volatile. This is for research only.
#  Always do your own research before buying anything.
#  Kraken charges 0.25% maker / 0.40% taker in Canada.
# ============================================================

import os, sys, smtplib, requests, time, json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from statistics import mean

# ── SECRETS ────────────────────────────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")
AV_KEY          = os.environ.get("ALPHA_VANTAGE_KEY", "demo")

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════
MAX_PRICE_USD  = 2.00       # skip anything at or above this price
MIN_VOL_USD    = 100_000    # minimum $100K daily volume (ensures liquidity)
TOP_N_COINS    = 20         # max coins to show in the email

# ══════════════════════════════════════════════════════════════
#  ALTCOIN UNIVERSE
#  All coins available on Kraken Canada that typically trade
#  under $2 USD. Bot always re-checks live price at runtime
#  and auto-skips anything that moved above $2.
#
#  Format: (kraken_ticker, symbol, category, plain_english_description)
# ══════════════════════════════════════════════════════════════

UNIVERSE = [
    # ── Established Layer 1s (lower risk, real utility) ──────
    ("HBARUSD",  "HBAR",  "Layer 1",    "Hedera Hashgraph",
     "Enterprise blockchain governed by Google, IBM & Boeing. Uses Hashgraph "
     "consensus for 10,000+ TPS at near-zero fees. Big in tokenization and "
     "corporate data use cases."),

    ("ADAUSD",   "ADA",   "Layer 1",    "Cardano",
     "Peer-reviewed proof-of-stake blockchain. One of the most academically "
     "rigorous crypto projects. Active DeFi and NFT ecosystem in Africa and "
     "developing markets."),

    ("ALGOUSD",  "ALGO",  "Layer 1",    "Algorand",
     "Pure proof-of-stake L1 with instant finality. Partnered with FIFA, "
     "Marshall Islands for CBDC, and major payment networks. Fast and cheap "
     "transactions."),

    ("XRPUSD",   "XRP",   "Payments",   "Ripple XRP",
     "Cross-border payment network used by major banks. Post-SEC legal "
     "clarity in the US has opened institutional floodgates. Very high daily "
     "volume on Kraken."),

    ("XLMUSD",   "XLM",   "Payments",   "Stellar Lumens",
     "Fast payment network built for the unbanked. IBM WorldWire uses Stellar "
     "rails. Competes with XRP for institutional cross-border settlement."),

    ("XDGUSD",   "DOGE",  "Meme / L1",  "Dogecoin",
     "Original meme coin with real payment adoption. Supported by Elon Musk "
     "and Tesla. One of the highest volume coins on any exchange — very liquid "
     "for trading."),

    ("VETUSD",   "VET",   "Enterprise", "VeChain",
     "Supply chain blockchain used by LVMH, Walmart China, BMW. Tracks "
     "real-world goods on-chain. Two-token system (VET + VTHO) is unique."),

    ("ZILUSD",   "ZIL",   "Layer 1",    "Zilliqa",
     "Sharding pioneer — first blockchain to implement sharding in production. "
     "Active gaming and DeFi ecosystem. Often follows ETH moves closely."),

    # ── DeFi / Web3 Infrastructure ───────────────────────────
    ("GRTUSD",   "GRT",   "DeFi",       "The Graph",
     "Indexing protocol — essentially a Google for blockchains. Used by "
     "Uniswap, Aave, Compound and most major DeFi protocols. Revenue grows "
     "with DeFi activity."),

    ("ANKRUSD",  "ANKR",  "DeFi",       "Ankr",
     "Decentralized RPC node provider. When developers build apps, they use "
     "Ankr infrastructure. Revenue scales with Web3 adoption."),

    ("BATUSD",   "BAT",   "Web3",       "Basic Attention Token",
     "Brave browser's privacy-first ad ecosystem. 60M+ monthly Brave users "
     "earn BAT for watching ads. Direct path to mainstream crypto "
     "adoption."),

    ("LRCUSD",   "LRC",   "DeFi",       "Loopring",
     "zkRollup-powered DEX on Ethereum. Processes trades at Ethereum speed "
     "but a fraction of the gas cost. Backed by Google engineers."),

    ("CRVUSD",   "CRV",   "DeFi",       "Curve Finance",
     "Largest stablecoin DEX in crypto — processes billions in swaps daily. "
     "veCRV governance model gives holders real yield from protocol fees."),

    ("ROSEUSD",  "ROSE",  "Privacy",    "Oasis Network",
     "Privacy-preserving DeFi and AI data platform. Unique Sapphire "
     "paratime allows confidential smart contracts. Growing in data "
     "marketplace niche."),

    ("CHZUSD",   "CHZ",   "Sports",     "Chiliz",
     "Fan token platform for sport clubs — Barcelona, PSG, Juventus, "
     "UFC, NBA. Fan engagement coin with real-world redemption through "
     "Socios.com app."),

    ("ONTUSD",   "ONT",   "Identity",   "Ontology",
     "Decentralized identity and data sovereignty platform. Used by "
     "government digital ID pilots in Asia. Pairs with WING for DeFi."),

    ("AUDIOUSD", "AUDIO", "Web3",       "Audius",
     "Decentralized music streaming — Deadmau5, Rezz, Katy Perry are on it. "
     "Rival to Spotify with artists keeping 90% of revenue. TikTok "
     "integration drove a major price spike in 2021."),

    # ── Gaming / Metaverse ────────────────────────────────────
    ("MANAUSD",  "MANA",  "Metaverse",  "Decentraland",
     "Virtual world where you own land as NFTs. Samsung, JP Morgan, and "
     "Atari have bought virtual plots. Moves hard when metaverse narratives "
     "heat up."),

    ("SANDUSD",  "SAND",  "Metaverse",  "The Sandbox",
     "Gaming metaverse — Snoop Dogg, Paris Hilton, Adidas have all bought "
     "virtual land here. Strong brand partners make this a go-to "
     "metaverse play."),

    ("ENJUSD",   "ENJ",   "Gaming",     "Enjin Coin",
     "NFT gaming ecosystem. Every in-game item is backed 1:1 by ENJ. "
     "Microsoft Azure partnership. Spun off Polkadot-based Efinity for "
     "cross-game NFTs."),

    # ── Meme Coins (high volatility, fast moves) ─────────────
    ("SHIBUSD",  "SHIB",  "Meme",       "Shiba Inu",
     "Second largest meme coin by market cap. Ethereum-based, with active "
     "DeFi (ShibaSwap) and Layer 2 (Shibarium). Whale movements and "
     "burn events drive sharp pumps."),

    ("PEPEUSD",  "PEPE",  "Meme",       "Pepe",
     "ERC-20 meme coin with no utility — pure sentiment play. Massive "
     "trading volume on Kraken. Very sensitive to BTC moves, Elon "
     "tweets, and meme cycles."),

    ("FLOKIUSD", "FLOKI", "Meme",       "Floki Inu",
     "Meme coin with an actual ecosystem — Valhalla gaming, FlokiFi "
     "DeFi, and FlokiPlaces NFT marketplace. More utility than most "
     "meme coins."),

    ("BONKUSD",  "BONK",  "Meme",       "Bonk",
     "Solana's first community meme coin — airdropped to Solana "
     "developers and NFT holders. Moves in lockstep with Solana "
     "ecosystem sentiment."),

    ("WIFUSD",   "WIF",   "Meme",       "dogwifhat",
     "Solana meme coin — just a dog with a hat. Top 50 by market cap. "
     "No utility whatsoever — pure hype and momentum. Very high "
     "volatility."),

    # ── Newer Narratives ──────────────────────────────────────
    ("JASMYUSD", "JASMY", "Data",       "JasmyCoin",
     "Data sovereignty platform — Sony veterans team. IoT data "
     "marketplace where users own and monetize their own data. "
     "Growing slowly but steadily."),

    ("KASUSD",   "KAS",   "Layer 1",    "Kaspa",
     "Fastest proof-of-work blockchain — blockDAG architecture allows "
     "1 block per second. Often called 'the fastest PoW coin'. Gaining "
     "serious miner interest."),

    ("ACAUSD",   "ACA",   "DeFi",       "Acala",
     "DeFi hub of the Polkadot ecosystem. Native stablecoin aUSD. "
     "Moves with DOT ecosystem news and Polkadot parachain "
     "developments."),
]

# ── Install deps ───────────────────────────────────────────────
def _install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:    from textblob import TextBlob
except: _install("textblob"); from textblob import TextBlob


# ══════════════════════════════════════════════════════════════
#  KRAKEN PUBLIC API  — no key needed for market data
# ══════════════════════════════════════════════════════════════

KRAKEN_BASE = "https://api.kraken.com/0/public"

def kraken_get(endpoint, params=None):
    """Generic Kraken public API call with retry."""
    for attempt in range(3):
        try:
            r = requests.get(f"{KRAKEN_BASE}/{endpoint}", params=params, timeout=15)
            data = r.json()
            if data.get("error"):
                return None
            return data.get("result")
        except Exception as e:
            if attempt == 2:
                print(f"    Kraken API error ({endpoint}): {e}")
            time.sleep(2)
    return None


def get_ticker_data(pair):
    """
    Fetch live ticker for a Kraken pair.
    Returns dict with price, volume, 24h change, bid, ask.
    """
    result = kraken_get("Ticker", {"pair": pair})
    if not result:
        return None
    try:
        key   = list(result.keys())[0]
        t     = result[key]
        price = float(t["c"][0])          # last trade price
        ask   = float(t["a"][0])          # ask
        bid   = float(t["b"][0])          # bid
        vol   = float(t["v"][1])          # 24h volume in base currency
        vwap  = float(t["p"][1])          # 24h VWAP
        high  = float(t["h"][1])          # 24h high
        low   = float(t["l"][1])          # 24h low
        open_ = float(t["o"])             # today's opening price
        trades= int(t["t"][1])            # number of trades 24h

        vol_usd    = vol * vwap           # approximate USD volume
        change_24h = ((price - open_) / open_ * 100) if open_ > 0 else 0
        spread_pct = ((ask - bid) / ask * 100) if ask > 0 else 0
        price_vs_high = ((price - high) / high * 100) if high > 0 else 0
        price_vs_low  = ((price - low)  / low  * 100) if low  > 0 else 0
        range_pct  = ((high - low) / low * 100) if low > 0 else 0  # 24h range = volatility

        return {
            "price":        price,
            "ask":          ask,
            "bid":          bid,
            "vol_usd":      vol_usd,
            "vol_coin":     vol,
            "vwap":         vwap,
            "high_24h":     high,
            "low_24h":      low,
            "open":         open_,
            "change_24h":   round(change_24h, 2),
            "spread_pct":   round(spread_pct, 3),
            "trades_24h":   trades,
            "price_vs_high": round(price_vs_high, 2),
            "price_vs_low":  round(price_vs_low,  2),
            "range_pct":    round(range_pct, 2),
        }
    except Exception as e:
        print(f"    Ticker parse error: {e}")
        return None


def get_ohlc(pair, interval=60):
    """
    Fetch OHLC candles for trend calculation.
    interval: 60 = hourly candles
    Returns list of closing prices (most recent last).
    """
    result = kraken_get("OHLC", {"pair": pair, "interval": interval})
    if not result:
        return []
    try:
        key    = [k for k in result.keys() if k != "last"][0]
        candles = result[key]
        closes = [float(c[4]) for c in candles[-48:]]  # last 48 hourly closes
        volumes= [float(c[6]) for c in candles[-48:]]  # last 48 volumes
        return closes, volumes
    except:
        return [], []


# ══════════════════════════════════════════════════════════════
#  TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════

def calc_rsi(closes, period=14):
    """
    RSI — Relative Strength Index.
    < 30 = oversold (potential buy)
    30-50 = neutral/recovering
    50-70 = bullish momentum
    > 70 = overbought (potential reversal)
    """
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = mean(gains[-period:])
    avg_loss = mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs  = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calc_momentum(closes):
    """
    Price momentum over different timeframes.
    Returns (1h_change, 4h_change, 12h_change) in %.
    """
    if len(closes) < 13:
        return None, None, None
    def pct(old, new): return round((new - old) / old * 100, 2) if old > 0 else 0
    c = closes
    h1  = pct(c[-2],  c[-1])   if len(c) >= 2  else None
    h4  = pct(c[-5],  c[-1])   if len(c) >= 5  else None
    h12 = pct(c[-13], c[-1])   if len(c) >= 13 else None
    return h1, h4, h12


def calc_volume_spike(volumes):
    """
    Compares latest volume to average.
    > 2× average = significant spike (attention signal).
    """
    if len(volumes) < 10:
        return None
    avg = mean(volumes[:-1])
    if avg == 0:
        return None
    return round(volumes[-1] / avg, 2)


def calc_ema(closes, period):
    """Exponential Moving Average."""
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 8)


def trend_direction(closes):
    """
    Simple trend: is EMA9 above or below EMA21?
    Returns 'UP', 'DOWN', or 'SIDEWAYS'.
    """
    ema9  = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    if not ema9 or not ema21:
        return "SIDEWAYS"
    diff_pct = (ema9 - ema21) / ema21 * 100
    if diff_pct > 0.5:   return "UP"
    elif diff_pct < -0.5: return "DOWN"
    return "SIDEWAYS"


# ══════════════════════════════════════════════════════════════
#  NEWS + SENTIMENT
# ══════════════════════════════════════════════════════════════

def get_news(symbol, display_name):
    """
    Fetch news for a crypto coin.
    Tries Alpha Vantage crypto news, falls back to CryptoPanic (free).
    """
    headlines = []

    # Try Alpha Vantage crypto news
    try:
        url  = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
                f"&tickers=CRYPTO:{symbol}&limit=8&apikey={AV_KEY}")
        data = requests.get(url, timeout=10).json()
        for item in data.get("feed", [])[:8]:
            title = item.get("title", "")
            pub   = item.get("time_published", "")[:8]
            try:   pub_fmt = datetime.strptime(pub, "%Y%m%d").strftime("%b %d")
            except: pub_fmt = pub

            # Try AV score first, fallback to TextBlob
            score = None
            for ts in item.get("ticker_sentiment", []):
                if symbol.upper() in ts.get("ticker", "").upper():
                    score = float(ts.get("ticker_sentiment_score", 0)); break
            if score is None:
                score = TextBlob(title).sentiment.polarity

            headlines.append({
                "title":  title[:110],
                "score":  round(score, 3),
                "url":    item.get("url", "#"),
                "date":   pub_fmt,
                "source": item.get("source", ""),
            })
    except: pass

    # CryptoPanic fallback — free tier, no key needed for basics
    if not headlines:
        try:
            url  = f"https://cryptopanic.com/api/v1/posts/?currencies={symbol}&kind=news&public=true"
            data = requests.get(url, timeout=10).json()
            for item in data.get("results", [])[:8]:
                title  = item.get("title", "")
                pub    = item.get("published_at", "")[:10]
                try:   pub_fmt = datetime.strptime(pub, "%Y-%m-%d").strftime("%b %d")
                except: pub_fmt = pub
                score  = TextBlob(title).sentiment.polarity
                source = item.get("source", {}).get("title", "")
                url_   = item.get("url", "#")
                headlines.append({
                    "title":  title[:110],
                    "score":  round(score, 3),
                    "url":    url_,
                    "date":   pub_fmt,
                    "source": source,
                })
        except: pass

    return headlines


def avg_sentiment(headlines):
    if not headlines: return 0.0
    return round(sum(h["score"] for h in headlines) / len(headlines), 3)


# ══════════════════════════════════════════════════════════════
#  TREND REASON ENGINE
#  This is what makes the email useful — plain English explanation
#  of WHY each coin is moving and WHAT is driving it.
# ══════════════════════════════════════════════════════════════

def build_trend_reasons(coin_data, ticker_data, closes, volumes, rsi,
                         h1, h4, h12, vol_spike, trend, avg_sent, headlines):
    """
    Builds a list of plain-English reasons explaining what is
    driving this coin right now. Each reason has a category tag.
    """
    reasons = []
    price   = ticker_data["price"]
    ch24    = ticker_data["change_24h"]
    range_  = ticker_data["range_pct"]
    low24   = ticker_data["low_24h"]
    high24  = ticker_data["high_24h"]

    # ── Price vs 24h range ──────────────────────────────────────
    pct_from_low = ((price - low24) / (high24 - low24) * 100) if high24 > low24 else 50

    # ── Momentum reasons ────────────────────────────────────────
    if h1 and h1 > 1.5:
        reasons.append({"tag": "📈 Momentum", "color": "#0F6E56",
            "text": f"Up {h1:+.1f}% in the last hour — strong short-term buying pressure. "
                    f"Price is accelerating above the hourly open."})
    elif h1 and h1 > 0.5:
        reasons.append({"tag": "📈 Momentum", "color": "#3B6D11",
            "text": f"Up {h1:+.1f}% this hour — mild positive momentum building."})
    elif h1 and h1 < -1.5:
        reasons.append({"tag": "📉 Selling", "color": "#A32D2D",
            "text": f"Down {h1:.1f}% in the last hour — short-term selling pressure. "
                    f"Watch for a bounce at the 24h low of {fmt_price(low24)}."})

    if h4 and abs(h4) > 3:
        tag   = "📈 4h trend" if h4 > 0 else "📉 4h decline"
        col   = "#0F6E56" if h4 > 0 else "#A32D2D"
        txt   = (f"Up {h4:+.1f}% over the last 4 hours — sustained buying, not a one-candle spike."
                 if h4 > 0 else
                 f"Down {h4:.1f}% over the last 4 hours — sustained selling, not just a blip.")
        reasons.append({"tag": tag, "color": col, "text": txt})

    # ── 24h change context ──────────────────────────────────────
    if ch24 > 8:
        reasons.append({"tag": "🚀 Strong rally", "color": "#0F6E56",
            "text": f"Up {ch24:+.1f}% in 24 hours — this is a significant single-day move. "
                    f"24h range was {range_:.1f}%, showing high volatility."})
    elif ch24 > 3:
        reasons.append({"tag": "📈 Gaining", "color": "#3B6D11",
            "text": f"Up {ch24:+.1f}% today — solid 24h performance with good upward momentum."})
    elif ch24 < -8:
        reasons.append({"tag": "🔴 Sharp drop", "color": "#A32D2D",
            "text": f"Down {abs(ch24):.1f}% in 24 hours — significant sell-off. "
                    f"Could be a buying opportunity if fundamentals are intact, "
                    f"or a warning sign to wait for stabilisation."})
    elif ch24 < -3:
        reasons.append({"tag": "📉 Declining", "color": "#7A4900",
            "text": f"Down {abs(ch24):.1f}% today — mild negative pressure. Watch for support at {fmt_price(low24)}."})

    # ── RSI context ─────────────────────────────────────────────
    if rsi:
        if rsi < 25:
            reasons.append({"tag": "💎 Oversold RSI", "color": "#0F6E56",
                "text": f"RSI is {rsi} — deeply oversold territory. This means the coin has "
                        f"been sold heavily and a bounce is statistically more likely than "
                        f"continued selling. Classic buy-the-dip signal."})
        elif rsi < 35:
            reasons.append({"tag": "📊 RSI low", "color": "#3B6D11",
                "text": f"RSI at {rsi} — approaching oversold. Selling pressure is fading."})
        elif 45 <= rsi <= 60:
            reasons.append({"tag": "📊 RSI healthy", "color": "#555",
                "text": f"RSI at {rsi} — healthy mid-range. Room to run without being overbought."})
        elif rsi > 75:
            reasons.append({"tag": "⚠️ Overbought RSI", "color": "#A32D2D",
                "text": f"RSI at {rsi} — overbought territory. The rally may be overextended. "
                        f"Latecomers risk buying the top. Consider waiting for a pullback."})
        elif rsi > 65:
            reasons.append({"tag": "⚠️ RSI elevated", "color": "#7A4900",
                "text": f"RSI at {rsi} — getting hot. Momentum is strong but watch for short-term exhaustion."})

    # ── Volume spike ────────────────────────────────────────────
    if vol_spike and vol_spike > 3.0:
        reasons.append({"tag": "🔊 Huge volume spike", "color": "#0F6E56",
            "text": f"Trading volume is {vol_spike:.1f}× higher than the 24h average — "
                    f"a massive spike. This is NOT normal activity. Something is driving "
                    f"serious attention: news, whale accumulation, or social media. "
                    f"High volume with price rising = strong confirmation."})
    elif vol_spike and vol_spike > 1.8:
        reasons.append({"tag": "🔊 Volume spike", "color": "#3B6D11",
            "text": f"Volume is {vol_spike:.1f}× above average — elevated activity. "
                    f"More buyers/sellers than usual are entering this coin right now."})
    elif vol_spike and vol_spike < 0.5:
        reasons.append({"tag": "😴 Low volume", "color": "#888",
            "text": f"Volume is only {vol_spike:.1f}× of average — quiet market. "
                    f"Price moves on low volume are less reliable and easier to reverse."})

    # ── Trend (EMA9 vs EMA21) ───────────────────────────────────
    if trend == "UP":
        reasons.append({"tag": "📈 Uptrend (EMA)", "color": "#0F6E56",
            "text": "Short-term EMA (9 period) is above the longer EMA (21 period) — "
                    "this is a bullish crossover signal. The hourly trend is pointing up."})
    elif trend == "DOWN":
        reasons.append({"tag": "📉 Downtrend (EMA)", "color": "#A32D2D",
            "text": "Short-term EMA is below the longer EMA — bearish structure. "
                    "The path of least resistance is still down on the hourly chart."})

    # ── 24h price range position ────────────────────────────────
    if pct_from_low < 15 and ch24 > 0:
        reasons.append({"tag": "🎯 Near 24h low", "color": "#0F6E56",
            "text": f"Price is only {pct_from_low:.0f}% above today's low of {fmt_price(low24)} "
                    f"but still showing positive daily change. This means it dipped and recovered — "
                    f"a show of strength and a possible entry point."})
    elif pct_from_low > 85:
        reasons.append({"tag": "⚠️ Near 24h high", "color": "#7A4900",
            "text": f"Price is {pct_from_low:.0f}% of the way to today's high of {fmt_price(high24)}. "
                    f"Chasing near the daily high is risky — wait for a pullback if interested."})

    # ── News sentiment reasons ──────────────────────────────────
    if avg_sent > 0.20:
        reasons.append({"tag": "📰 Positive news", "color": "#0F6E56",
            "text": f"Recent headlines are overwhelmingly positive (avg sentiment {avg_sent:+.2f}). "
                    f"Positive news flow attracts buyers and sustains rallies. "
                    f"Check headlines below for specific catalysts."})
    elif avg_sent > 0.10:
        reasons.append({"tag": "📰 Mild positive news", "color": "#3B6D11",
            "text": f"Slightly more positive than negative headlines (avg {avg_sent:+.2f})."})
    elif avg_sent < -0.20:
        reasons.append({"tag": "📰 Negative news", "color": "#A32D2D",
            "text": f"Recent headlines are predominantly negative (avg {avg_sent:+.2f}). "
                    f"Bad news drives selling. Be cautious — the market may not have "
                    f"fully priced in the negative yet."})
    elif avg_sent < -0.10:
        reasons.append({"tag": "📰 Slightly negative news", "color": "#7A4900",
            "text": f"More negative than positive headlines recently (avg {avg_sent:+.2f})."})

    return reasons


# ══════════════════════════════════════════════════════════════
#  VERDICT ENGINE
#  Buy / Watch / Avoid with plain-English explanation
# ══════════════════════════════════════════════════════════════

def get_verdict(ticker_data, rsi, trend, vol_spike, avg_sent, h1, h4):
    """
    Scores coin signals and returns a verdict.
    Returns (verdict, color, bg, explanation, score)
    """
    score = 0

    ch24 = ticker_data["change_24h"]
    spread = ticker_data["spread_pct"]

    # Price momentum
    if ch24 > 5:    score += 20
    elif ch24 > 2:  score += 10
    elif ch24 < -5: score -= 20
    elif ch24 < -2: score -= 10

    # RSI
    if rsi:
        if rsi < 30:    score += 20  # oversold = buy opportunity
        elif rsi < 45:  score += 10
        elif rsi > 75:  score -= 20  # overbought = risky entry
        elif rsi > 60:  score -= 5

    # Trend
    if trend == "UP":   score += 15
    elif trend == "DOWN": score -= 15

    # Volume
    if vol_spike:
        if vol_spike > 3.0:  score += 20
        elif vol_spike > 1.8: score += 10
        elif vol_spike < 0.5: score -= 10

    # News sentiment
    if avg_sent > 0.20:   score += 15
    elif avg_sent > 0.10: score += 7
    elif avg_sent < -0.20: score -= 15
    elif avg_sent < -0.10: score -= 7

    # Short-term momentum
    if h1 and h1 > 1:    score += 5
    elif h1 and h1 < -1: score -= 5
    if h4 and h4 > 3:    score += 10
    elif h4 and h4 < -3: score -= 10

    # Spread penalty (wide spread = bad for scalping)
    if spread > 1.0:  score -= 10
    elif spread > 0.5: score -= 5

    score = max(-100, min(100, score))

    if score >= 35:
        return ("BUY WATCH 🚀", "#0F6E56", "#D5F5EA",
                "Multiple signals are aligned bullishly. "
                "This does NOT mean buy blindly — it means this coin is worth "
                "serious attention right now. Consider a small position or "
                "set a price alert. Always use a stop-loss.",
                score)
    elif score >= 15:
        return ("WORTH WATCHING 👀", "#3B6D11", "#E5F2DA",
                "More positive signals than negative. Not a strong conviction "
                "setup, but worth keeping on your radar. Wait for a clearer "
                "signal or a dip before entering.",
                score)
    elif score <= -35:
        return ("AVOID NOW ⛔", "#A32D2D", "#FDECEA",
                "Multiple bearish signals present. This coin is in a weak "
                "position right now. Avoid buying here — wait for the selling "
                "to stop and for momentum to reverse before considering entry.",
                score)
    elif score <= -15:
        return ("CAUTION ⚠️", "#7A4900", "#FEF3DA",
                "More negative signals than positive. Not a good time to buy. "
                "Watch from the sidelines — the picture may improve in a few hours.",
                score)
    else:
        return ("NEUTRAL ⚪", "#555", "#F0F0F0",
                "Mixed signals — no clear edge in either direction. "
                "The coin is consolidating. Save your money for a clearer setup.",
                score)


# ══════════════════════════════════════════════════════════════
#  MAIN SCAN
# ══════════════════════════════════════════════════════════════

def run_scan():
    """Scans the full universe and returns enriched results."""
    results  = []
    skipped  = []

    total = len(UNIVERSE)
    print(f"  Scanning {total} Kraken altcoins under ${MAX_PRICE_USD}...")

    for i, (pair, symbol, category, display_name, description) in enumerate(UNIVERSE):
        print(f"  [{i+1}/{total}] {symbol}...", end=" ")

        # Fetch live ticker
        ticker = get_ticker_data(pair)
        if not ticker:
            print("no data")
            time.sleep(1)
            continue

        price = ticker["price"]

        # HARD RULE: skip if price >= $2
        if price >= MAX_PRICE_USD:
            print(f"${price:.4f} — skipped (above ${MAX_PRICE_USD})")
            skipped.append(f"{symbol} (${price:.2f})")
            time.sleep(1)
            continue

        # HARD RULE: skip if volume too low
        if ticker["vol_usd"] < MIN_VOL_USD:
            print(f"${price:.6f} — skipped (low volume ${ticker['vol_usd']:,.0f})")
            time.sleep(1)
            continue

        # Fetch OHLC for technical analysis
        closes, volumes = get_ohlc(pair, interval=60)
        time.sleep(1)

        # Technical indicators
        rsi       = calc_rsi(closes) if closes else None
        h1, h4, h12 = calc_momentum(closes) if closes else (None, None, None)
        vol_spike = calc_volume_spike(volumes) if volumes else None
        trend     = trend_direction(closes) if closes else "SIDEWAYS"

        # Fetch news
        news     = get_news(symbol, display_name)
        avg_sent = avg_sentiment(news)
        time.sleep(2)

        # Build reasons
        reasons = build_trend_reasons(
            (pair, symbol, category, display_name, description),
            ticker, closes, volumes, rsi,
            h1, h4, h12, vol_spike, trend, avg_sent, news
        )

        # Get verdict
        verdict, vcol, vbg, vexp, score = get_verdict(
            ticker, rsi, trend, vol_spike, avg_sent, h1, h4
        )

        print(f"${price:.6f} | {ticker['change_24h']:+.1f}% | RSI {rsi} | {verdict}")

        results.append({
            "pair":        pair,
            "symbol":      symbol,
            "category":    category,
            "name":        display_name,
            "description": description,
            "ticker":      ticker,
            "rsi":         rsi,
            "h1":          h1,
            "h4":          h4,
            "h12":         h12,
            "vol_spike":   vol_spike,
            "trend":       trend,
            "news":        news,
            "avg_sent":    avg_sent,
            "reasons":     reasons,
            "verdict":     verdict,
            "verdict_color": vcol,
            "verdict_bg":    vbg,
            "verdict_explanation": vexp,
            "score":       score,
        })

        time.sleep(1)

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, skipped


# ══════════════════════════════════════════════════════════════
#  FORMAT HELPERS
# ══════════════════════════════════════════════════════════════

def fmt_price(v):
    """Smart price formatting — handles everything from $0.0000001 to $1.99"""
    if v is None: return "N/A"
    if v < 0.000001: return f"${v:.10f}"
    if v < 0.0001:   return f"${v:.8f}"
    if v < 0.01:     return f"${v:.6f}"
    if v < 0.10:     return f"${v:.4f}"
    return f"${v:.4f}"

def fmt_vol(v):
    if v is None: return "N/A"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    if v >= 1e6:  return f"${v/1e6:.1f}M"
    if v >= 1e3:  return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def change_color(ch):
    if ch > 0: return "#0F6E56"
    if ch < 0: return "#A32D2D"
    return "#888"

def trend_icon(trend):
    return {"UP": "↑ Uptrend", "DOWN": "↓ Downtrend", "SIDEWAYS": "→ Sideways"}.get(trend, "—")

def rsi_label(rsi):
    if rsi is None: return "N/A", "#888"
    if rsi < 30:    return f"RSI {rsi} (Oversold)", "#0F6E56"
    if rsi < 45:    return f"RSI {rsi} (Low)", "#3B6D11"
    if rsi <= 60:   return f"RSI {rsi} (Neutral)", "#555"
    if rsi <= 75:   return f"RSI {rsi} (Elevated)", "#7A4900"
    return f"RSI {rsi} (Overbought)", "#A32D2D"


# ══════════════════════════════════════════════════════════════
#  EMAIL HTML
# ══════════════════════════════════════════════════════════════

CSS = """<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#f2f2f2;margin:0;padding:14px;color:#1a1a1a;}
.wrap{max-width:660px;margin:0 auto;}
.header{padding:22px 24px;border-radius:12px 12px 0 0;
        background:linear-gradient(135deg,#0d1f3c,#1a3a6e);}
.header h1{margin:0;font-size:20px;font-weight:700;color:#fff;}
.header p{margin:5px 0 0;font-size:13px;color:rgba(255,255,255,0.65);}
.body{background:#fff;border:1px solid #ddd;border-top:none;
      border-radius:0 0 12px 12px;padding-bottom:24px;}
.stat-row{display:flex;justify-content:space-around;padding:14px 8px 8px;
          border-bottom:1px solid #f0f0f0;}
.stat .num{font-size:22px;font-weight:700;}
.stat .desc{font-size:11px;color:#aaa;}
.section{padding:16px 18px 0;}
.sec-title{font-size:11px;font-weight:700;color:#666;text-transform:uppercase;
           letter-spacing:.8px;padding-bottom:7px;border-bottom:1px solid #eee;margin-bottom:10px;}
.card{border:1px solid #e8e8e8;border-radius:10px;margin-bottom:12px;overflow:hidden;}
.card-head{background:#f7f7f7;padding:12px 15px;border-bottom:1px solid #eee;}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;}
.sym{font-size:17px;font-weight:700;}
.sym-sub{font-size:11px;color:#999;margin-top:2px;}
.price{font-size:16px;font-weight:700;text-align:right;}
.cat-badge{display:inline-block;font-size:10px;font-weight:600;
           padding:2px 8px;border-radius:6px;margin-top:3px;
           background:#E6F1FB;color:#185FA5;}
.verdict-box{margin:10px 15px 0;padding:11px 13px;border-radius:8px;}
.verdict-lbl{font-size:14px;font-weight:700;margin-bottom:4px;}
.verdict-why{font-size:12px;line-height:1.6;}
.meta-row{display:flex;flex-wrap:wrap;gap:14px;padding:10px 15px 6px;}
.meta-lbl{font-size:10px;color:#bbb;margin-bottom:1px;}
.meta-val{font-size:12px;font-weight:600;}
.bar-wrap{padding:2px 15px 6px;}
.bar-bg{background:#eee;border-radius:3px;height:5px;}
.bar-lbl{display:flex;justify-content:space-between;font-size:10px;color:#ccc;margin-top:2px;}
.desc-box{margin:0 15px 8px;padding:9px 12px;background:#f9f9f9;
          border-radius:7px;font-size:12px;color:#555;line-height:1.6;
          border-left:3px solid #e0e0e0;}
.reasons{padding:0 15px 8px;}
.rsn-item{padding:7px 0;border-bottom:1px solid #f5f5f5;}
.rsn-item:last-child{border:none;}
.rsn-tag{font-size:10px;font-weight:700;padding:1px 7px;border-radius:6px;
         display:inline-block;margin-bottom:3px;}
.rsn-text{font-size:12px;color:#444;line-height:1.55;}
.news-section{padding:4px 15px 10px;}
.news-lbl{font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;}
.n-item{padding:5px 0;border-bottom:1px solid #f5f5f5;}
.n-item:last-child{border:none;}
.n-row{display:flex;gap:6px;align-items:center;margin-bottom:2px;}
.n-date{font-size:10px;color:#ccc;}
.n-badge{font-size:10px;font-weight:600;padding:1px 6px;border-radius:5px;}
.n-title{font-size:12px;color:#333;line-height:1.4;}
.n-title a{color:#185FA5;text-decoration:none;}
.n-source{font-size:10px;color:#ccc;}
.skip-box{margin:10px 18px 0;padding:9px 13px;background:#f5f5f5;
          border-radius:7px;font-size:12px;color:#888;}
.divider{height:1px;background:#f0f0f0;margin:16px 18px 0;}
.footer{text-align:center;padding:14px 18px 0;font-size:11px;color:#bbb;line-height:1.7;}
.kraken-note{background:#EEF3FB;border-radius:8px;padding:10px 14px;
             margin:12px 18px 0;font-size:12px;color:#185FA5;}
</style>"""


def news_html(headlines):
    rows = ""
    for h in headlines[:5]:
        s = h["score"]
        if s > 0.15:   bg,c,icon,lbl = "#E6F8F2","#1D9E75","▲","Positive"
        elif s<-0.15:  bg,c,icon,lbl = "#FEF0F0","#E24B4A","▼","Negative"
        else:          bg,c,icon,lbl = "#F0F0F0","#888","●","Neutral"
        src = f'<span class="n-source"> · {h["source"]}</span>' if h.get("source") else ""
        rows += f"""<div class="n-item">
  <div class="n-row">
    <span class="n-date">{h['date']}</span>
    <span class="n-badge" style="background:{bg};color:{c};">{icon} {lbl}</span>{src}
  </div>
  <div class="n-title"><a href="{h['url']}" target="_blank">{h['title']}</a></div>
</div>"""
    return rows


def price_bar(price, low, high):
    if not all([price, low, high]) or high == low: return ""
    pct = max(0, min(100, (price-low)/(high-low)*100))
    col = "#1D9E75" if pct < 35 else "#EF9F27" if pct < 65 else "#E24B4A"
    return f"""<div class="bar-wrap">
  <div style="font-size:10px;color:#ccc;margin-bottom:2px;">24h range position — {pct:.0f}% from low</div>
  <div class="bar-bg"><div style="background:{col};width:{pct:.0f}%;height:5px;border-radius:3px;"></div></div>
  <div class="bar-lbl"><span>{fmt_price(low)}</span><span>{fmt_price(high)}</span></div>
</div>"""


def coin_card(r):
    t       = r["ticker"]
    price   = t["price"]
    ch      = t["change_24h"]
    ch_col  = change_color(ch)
    ch_str  = f"{ch:+.2f}%"
    rsi_str, rsi_col = rsi_label(r["rsi"])
    vol_str  = fmt_vol(t["vol_usd"])
    h1s      = f"{r['h1']:+.2f}%" if r["h1"] is not None else "—"
    h4s      = f"{r['h4']:+.2f}%" if r["h4"] is not None else "—"
    vs       = f"{r['vol_spike']:.1f}×" if r["vol_spike"] else "—"
    trend_s  = trend_icon(r["trend"])

    reasons_html = ""
    for rsn in r["reasons"]:
        reasons_html += f"""<div class="rsn-item">
  <div><span class="rsn-tag" style="background:{rsn['color']}22;color:{rsn['color']};">{rsn['tag']}</span></div>
  <div class="rsn-text">{rsn['text']}</div>
</div>"""

    news_rows = news_html(r["news"])

    return f"""<div class="card">
  <div class="card-head">
    <div class="card-top">
      <div>
        <div class="sym">{r['symbol']} <span style="font-size:13px;color:#999;font-weight:400;">— {r['name']}</span></div>
        <div class="sym-sub">{r['description']}</div>
        <div style="margin-top:4px;"><span class="cat-badge">{r['category']}</span></div>
      </div>
      <div style="text-align:right;">
        <div class="price">{fmt_price(price)}</div>
        <div style="font-size:14px;font-weight:700;color:{ch_col};">{ch_str} today</div>
        <div style="font-size:10px;color:#bbb;">Vol {vol_str} · {t['trades_24h']:,} trades</div>
      </div>
    </div>
  </div>

  <div class="verdict-box" style="background:{r['verdict_bg']};border-left:4px solid {r['verdict_color']};">
    <div class="verdict-lbl" style="color:{r['verdict_color']};">{r['verdict']}</div>
    <div class="verdict-why">{r['verdict_explanation']}</div>
  </div>

  <div class="meta-row">
    <div><div class="meta-lbl">1h change</div><div class="meta-val" style="color:{change_color(r['h1'] or 0)};">{h1s}</div></div>
    <div><div class="meta-lbl">4h change</div><div class="meta-val" style="color:{change_color(r['h4'] or 0)};">{h4s}</div></div>
    <div><div class="meta-lbl">RSI (14h)</div><div class="meta-val" style="color:{rsi_col};">{rsi_str}</div></div>
    <div><div class="meta-lbl">Volume spike</div><div class="meta-val">{vs}</div></div>
    <div><div class="meta-lbl">Trend (EMA)</div><div class="meta-val">{trend_s}</div></div>
    <div><div class="meta-lbl">24h spread</div><div class="meta-val">{t['spread_pct']:.2f}%</div></div>
  </div>

  {price_bar(price, t['low_24h'], t['high_24h'])}

  <div class="desc-box">
    <strong>What is {r['symbol']}?</strong> {r['description']}
  </div>

  <div class="reasons">
    <div style="font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;padding:4px 0 5px;">
      Why it's moving — signal breakdown
    </div>
    {reasons_html if reasons_html else '<div style="font-size:12px;color:#bbb;">No significant signals detected — coin is quiet.</div>'}
  </div>

  {'<div class="news-section"><div class="news-lbl">Recent news</div>' + news_rows + '</div>' if news_rows else ''}
</div>"""


def build_email(results, skipped):
    now      = datetime.now()
    date_str = now.strftime("%A, %B %d %Y  ·  %I:%M %p PT")

    buy_watch = [r for r in results if "BUY WATCH" in r["verdict"]]
    watching  = [r for r in results if "WORTH WATCHING" in r["verdict"]]
    caution   = [r for r in results if "CAUTION" in r["verdict"] or "AVOID" in r["verdict"]]
    neutral   = [r for r in results if r["verdict"].startswith("NEUTRAL")]

    top_gainer  = max(results, key=lambda x: x["ticker"]["change_24h"], default=None)
    top_vol_spk = max(results, key=lambda x: x.get("vol_spike") or 0, default=None)

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>🪙 Crypto Altcoin Brief</h1>
  <p>{date_str} · Kraken Canada · All coins under $2 USD</p>
</div>
<div class="body">

<div class="stat-row">
  <div class="stat"><div class="num" style="color:#0F6E56;">{len(results)}</div><div class="desc">Coins scanned</div></div>
  <div class="stat"><div class="num" style="color:#0F6E56;">{len(buy_watch)}</div><div class="desc">Buy watch 🚀</div></div>
  <div class="stat"><div class="num" style="color:#EF9F27;">{len(watching)}</div><div class="desc">Worth watching 👀</div></div>
  <div class="stat"><div class="num" style="color:#E24B4A;">{len(caution)}</div><div class="desc">Avoid / caution ⛔</div></div>
</div>

<div class="kraken-note">
  🇨🇦 <strong>Kraken Canada</strong> — FINTRAC registered · CAD deposits via EFT ·
  Maker fee 0.25% · Taker fee 0.40% · All coins below tradeable on spot market.
</div>
"""

    if top_gainer:
        g = top_gainer
        html += f"""<div style="margin:12px 18px 0;padding:10px 14px;background:#E6F8F2;border-radius:8px;font-size:12px;color:#0F6E56;">
  🏆 <strong>Top gainer today: {g['symbol']}</strong> — {g['ticker']['change_24h']:+.2f}% |
  Price: {fmt_price(g['ticker']['price'])} | Vol: {fmt_vol(g['ticker']['vol_usd'])}
</div>"""

    if top_vol_spk and top_vol_spk.get("vol_spike") and top_vol_spk["vol_spike"] > 1.5:
        vs = top_vol_spk
        html += f"""<div style="margin:8px 18px 0;padding:10px 14px;background:#FFF3CD;border-radius:8px;font-size:12px;color:#7a5200;">
  🔊 <strong>Biggest volume spike: {vs['symbol']}</strong> — {vs['vol_spike']:.1f}× above average |
  {vs['ticker']['change_24h']:+.2f}% price change
</div>"""

    # BUY WATCH section
    if buy_watch:
        html += '<div class="section"><div class="sec-title">🚀 Buy Watch — Bullish Signals Aligned</div>'
        for r in buy_watch:
            html += coin_card(r)
        html += '</div><div class="divider"></div>'

    # WORTH WATCHING
    if watching:
        html += '<div class="section"><div class="sec-title">👀 Worth Watching — Moderate Signals</div>'
        for r in watching:
            html += coin_card(r)
        html += '</div><div class="divider"></div>'

    # CAUTION / AVOID
    if caution:
        html += '<div class="section"><div class="sec-title">⛔ Caution / Avoid — Bearish or Risky</div>'
        for r in caution:
            html += coin_card(r)
        html += '</div><div class="divider"></div>'

    # NEUTRAL — brief list only
    if neutral:
        nl = ", ".join(r["symbol"] for r in neutral)
        html += f'<div class="section"><div class="sec-title">⚪ Quiet / Neutral — No Clear Signal</div>'
        html += f'<div style="font-size:12px;color:#888;padding:4px 0 12px;">{nl} — No strong signals in either direction. Save your attention for better setups.</div>'
        html += '</div>'

    # Skipped
    if skipped:
        html += f'<div class="skip-box">⛔ Skipped (moved above $2 since last update): {", ".join(skipped)}</div>'

    html += """<div class="footer">
<strong>Crypto Altcoin Brief is for research and education only — NOT financial advice.</strong><br>
Crypto is extremely volatile. Coins can lose 50%+ in hours. Never invest more than you can afford to lose.<br>
Kraken Canada is FINTRAC-registered. Always report crypto gains/losses on your Canadian taxes (T1135 if applicable).<br>
Signal strength: RSI, EMA, volume, sentiment — not guaranteed to predict price movement.
</div>
</div></div></body></html>"""
    return html


def build_text(results, skipped):
    now = datetime.now()
    lines = [
        "="*64,
        f"  🪙 CRYPTO ALTCOIN BRIEF — {now.strftime('%b %d %Y %I:%M %p PT')}",
        f"  Kraken Canada · All coins under $2 USD",
        "="*64,
    ]
    for r in results:
        t   = r["ticker"]
        rsi = f"RSI {r['rsi']}" if r["rsi"] else "RSI N/A"
        vs  = f"Vol {r['vol_spike']:.1f}x" if r["vol_spike"] else ""
        lines.append(
            f"\n  {r['symbol']:<8} {fmt_price(t['price']):<14} {t['change_24h']:+.2f}% today  "
            f"{rsi}  {vs}"
        )
        lines.append(f"  → {r['verdict']}")
        for rsn in r["reasons"][:2]:
            lines.append(f"     {rsn['tag']}: {rsn['text'][:70]}...")
    if skipped:
        lines += ["\nSKIPPED (above $2):", "  " + ", ".join(skipped)]
    lines += ["", "="*64, "  Research only — not financial advice.", "="*64]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  SEND EMAIL
# ══════════════════════════════════════════════════════════════

def send_email(subject, html_body, text_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(EMAIL_SENDER, EMAIL_PASSWORD)
        srv.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
    print(f"✅ Crypto Brief sent → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def run():
    now = datetime.now()
    print(f"🪙 Crypto Altcoin Brief — {now.strftime('%Y-%m-%d %H:%M PT')}")
    print(f"   Hard rules: price < ${MAX_PRICE_USD} · vol > {fmt_vol(MIN_VOL_USD)}")

    results, skipped = run_scan()

    if not results:
        print("No coins passed filters — check API and network.")
        return

    buy_watch = [r for r in results if "BUY WATCH" in r["verdict"]]
    caution   = [r for r in results if "AVOID" in r["verdict"]]
    top       = results[0]["symbol"] if results else "—"
    top_ch    = results[0]["ticker"]["change_24h"] if results else 0

    html_body = build_email(results, skipped)
    text_body = build_text(results, skipped)

    subject = (
        f"🪙 Crypto Brief · {now.strftime('%b %d')} | "
        f"🚀{len(buy_watch)} buy watch · "
        f"⛔{len(caution)} avoid · "
        f"Top: {top} {top_ch:+.1f}%"
    )

    print(text_body)

    if EMAIL_SENDER != "your@gmail.com":
        send_email(subject, html_body, text_body)
    else:
        print("⚠️  Set EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
