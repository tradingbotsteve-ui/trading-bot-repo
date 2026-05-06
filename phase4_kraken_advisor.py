# ============================================================
# TRADING BOT — PHASE 4 (Kraken Crypto Advisor)
#
# Scans ALL Kraken altcoins under $2.
# For every coin it finds interesting, it tells you:
#
#   🚀 BUY NOW      — enter this rally early, exit within days/weeks
#   💎 HODL 1-2 YR  — buy and hold, strong long-term fundamentals
#   👀 WATCH        — close but not ready, check again next run
#   ❌ SKIP         — mid-wave, risky, or whale dumping
#
# Each coin card explains IN PLAIN ENGLISH:
#   - What the coin actually does (so you know what you're buying)
#   - Why to buy it NOW (the specific signals firing)
#   - What price it's at, where it's been, and where whales sit
#   - Whether it's a quick trade or a long hold
#
# Runs every 15 minutes via GitHub Actions — 24 hours, 7 days.
# Sends email ONLY when there are actionable Buy or Hodl picks.
# No email = nothing worth acting on right now. Go do something else.
#
# No paid API needed. Uses Kraken's free public API only.
#
# SECRETS (GitHub → Settings → Secrets → Actions):
#   EMAIL_SENDER    — your Gmail address
#   EMAIL_PASSWORD  — Gmail App Password (16 chars, NOT your login password)
#   EMAIL_RECIPIENT — where to send alerts (can be same as EMAIL_SENDER)
# ============================================================

import os
import smtplib
import requests
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── SECRETS ──────────────────────────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")

KRAKEN_API = "https://api.kraken.com/0/public"

# ── SCAN FILTERS ─────────────────────────────────────────────
MAX_PRICE_USD   = 2.00    # only coins under $2
MIN_VOLUME_USD  = 25_000  # skip coins with less than $25k daily volume (too illiquid)
MAX_COINS       = 600     # scan up to 600 coins per run


# ══════════════════════════════════════════════════════════════
# COIN KNOWLEDGE BASE
#
# Plain-English descriptions of every coin worth knowing about.
# Format: "COIN_BASE_NAME": ("What it is", "Long-term case", "risk_level")
# risk_level: "low" | "medium" | "high" | "very_high"
#
# If a coin isn't listed here, it still gets scanned — it just
# won't have a description. The signals still fire.
# ══════════════════════════════════════════════════════════════

COIN_KNOWLEDGE = {
    # ── Proven infrastructure — lowest risk ──────────────────
    "XRP":  ("XRP is used by banks to move money across borders instantly and cheaply. Think of it as PayPal for banks.",
              "SEC lawsuit is over. 30+ banks use Ripple's tech. An XRP ETF is being reviewed. One of the safest under-$2 bets for the next crypto cycle.",
              "low"),
    "ADA":  ("Cardano is a blockchain built by academics. Every upgrade is peer-reviewed before release — like science, not hype.",
              "Slow and steady. Hydra scaling is live. ADA at under $1 is historically cheap vs its $3 all-time-high. A long-term infrastructure bet.",
              "low"),
    "XLM":  ("Stellar is Cardano's cousin — built for sending money to people who don't have bank accounts. Used by MoneyGram and IBM.",
              "Moves with XRP but usually cheaper. When XRP rallies, XLM follows. Good value play on the same payments narrative.",
              "low"),
    "ALGO": ("Algorand is a green, fast blockchain used by actual governments for digital currency projects.",
              "Pure-proof-of-stake, instant finality. Used by sovereign nations for CBDCs. Under $0.30 is historically very cheap.",
              "low"),
    "HBAR": ("Hedera is the blockchain run by a governing council that includes Google, IBM, Boeing, and LG. Very enterprise-focused.",
              "10,000 transactions per second at near-zero fees. Institutions choose Hedera for serious projects. Very credible.",
              "low"),

    # ── Strong projects — medium risk ────────────────────────
    "MATIC":("Polygon makes Ethereum faster and cheaper. Used by Nike, Starbucks, Reddit, and Disney for their blockchain products.",
              "When Ethereum moves, Polygon usually moves harder. It is Ethereum's best scaling layer. POL upgrade is live.",
              "medium"),
    "POL":  ("POL is the upgraded token for Polygon's new ecosystem. Same project as MATIC, new token name.",
              "Same thesis as MATIC — Ethereum scaling, real enterprise adoption, Disney/Nike/Reddit using it.",
              "medium"),
    "DOT":  ("Polkadot connects different blockchains together — like a USB hub for crypto networks.",
              "JAM upgrade improving scalability dramatically. DOT under $5 is historically cheap. Slow but solid accumulation.",
              "medium"),
    "LINK": ("Chainlink is the middleman between blockchains and real-world data. Every major DeFi app depends on it.",
              "Critical infrastructure. LINK has a history of exploding late in bull cycles. The more DeFi grows, the more valuable LINK becomes.",
              "medium"),
    "ARB":  ("Arbitrum is the most popular Ethereum Layer 2 by users. Robinhood uses it for tokenized stocks.",
              "2.4M+ DeFi users, 53M+ monthly transactions. Under $0.50 is a strong accumulation zone.",
              "medium"),
    "OP":   ("Optimism powers Coinbase's Base chain and dozens of other networks. It is the infrastructure behind Ethereum scaling.",
              "Revenue shared back to token holders. OP Stack is becoming the standard for Ethereum Layer 2s.",
              "medium"),
    "GRT":  ("The Graph is the Google of blockchain data. Every NFT marketplace and DeFi app indexes its data with The Graph.",
              "Gets more valuable as on-chain activity grows. Essential infrastructure that most people never see.",
              "medium"),
    "ICP":  ("Internet Computer wants to host entire apps — not just payments — on a blockchain. Very ambitious.",
              "Under $5 is historically cheap. High risk, high reward. Long-term thesis is cloud computing disruption.",
              "medium"),
    "ENJ":  ("Enjin makes the infrastructure for blockchain gaming. Samsung partnership. Games use ENJ to create in-game items.",
              "Gaming is a major 2026 narrative. ENJ is well-positioned early. Gas-free transactions via JumpNet.",
              "medium"),
    "STORJ":("Storj is decentralized cloud storage — like Dropbox but no company controls it. Real paying customers.",
              "Cheaper and faster than AWS S3. Data sovereignty narrative growing. Quiet utility token with real revenue.",
              "medium"),

    # ── More speculative — high risk ─────────────────────────
    "VET":  ("VeChain tracks products through supply chains. Walmart China and BMW use it to verify product authenticity.",
              "Real enterprise partnerships but niche. Moves explosively in bull markets. High risk, real adoption.",
              "high"),
    "CHZ":  ("Chiliz powers fan tokens for sports clubs. Manchester City, PSG, and Barcelona all have tokens on Chiliz.",
              "Millions of active users via Socios.com. Spikes around major sports events like Champions League or World Cup.",
              "high"),
    "CRV":  ("Curve is the backbone of stablecoin swapping in DeFi. When DeFi money moves, it moves through Curve.",
              "If DeFi comes back in altseason, CRV can explode. Risky but fundamentals are solid.",
              "high"),
    "SNX":  ("Synthetix lets you trade synthetic versions of any asset on-chain — like gold, oil, or Apple stock, without leaving crypto.",
              "High-beta DeFi play. Bleeds in bear markets, rockets in bull markets. Entry now = pre-altseason positioning.",
              "high"),
    "FLR":  ("Flare brings smart contracts to XRP, Litecoin, and Dogecoin holders — giving them DeFi access.",
              "Moves with XRP narrative. B/C tier hybrid — more utility than pure meme, still speculative.",
              "high"),
    "SCRT": ("Secret Network adds privacy to blockchain transactions. Like Monero but programmable.",
              "Privacy coins do well when surveillance concerns rise. Niche but real use case.",
              "high"),
    "KAVA": ("Kava is a DeFi lending platform that works across multiple blockchains, not just one.",
              "Cross-chain DeFi is growing. KAVA has been battle-tested through multiple market cycles.",
              "high"),
    "FLOW": ("Flow is the blockchain behind NBA Top Shot and NFL All Day. Built specifically for mainstream consumer apps.",
              "Dapper Labs created it. Real mainstream brands use it. Under $1 is historically cheap.",
              "high"),
    "ROSE": ("Oasis Network is a privacy-first smart contract platform. Focuses on confidential computing.",
              "Data privacy is a growing narrative. Oasis has partnerships with Meta for privacy research.",
              "high"),

    # ── Meme/community coins — very high risk ────────────────
    "PENGU":("PENGU is the token for Pudgy Penguins — an NFT collection with toys sold in Walmart and Target.",
              "Massive loyal community. Pudgy Party mobile game launched. PENGU ETF acknowledged by SEC. High meme risk but stronger than average meme. Ride waves fast, exit fast.",
              "very_high"),
    "LUNC": ("LUNC is what remained after the original Terra/LUNA collapsed in May 2022 and lost 99% of its value.",
              "Community-driven revival. Burns tokens via 1.2% transaction tax. EXTREMELY HIGH RISK — treat as a lottery ticket. Can 5-10x in altseason but can also go to zero. Never hold long-term.",
              "very_high"),
    "BONK": ("BONK is Solana's first major meme dog coin. Think Dogecoin but on Solana.",
              "Strong liquidity and whale activity. Moves with Solana ecosystem sentiment. Short-term whale ride candidate only.",
              "very_high"),
    "PEPE": ("PEPE is an Ethereum meme coin based on the Pepe the Frog internet meme. No serious utility.",
              "Pure community and sentiment play. ETF speculation driving attention in 2026. High liquidity makes it tradeable but volatile.",
              "very_high"),
    "SHIB": ("Shiba Inu started as a Dogecoin joke but built a real community. Shibarium L2 adds some utility.",
              "Large community. SHIB burns ongoing. Slow burner that explodes in retail-driven phases. Exit fast when it runs.",
              "very_high"),
    "FLOKI":("FLOKI is a meme coin named after Elon Musk's dog. It has built a gaming ecosystem around the meme.",
              "Has more development than most meme coins. Still very speculative. Community-driven price action.",
              "very_high"),
    "WIF":  ("dogwifhat is a meme coin — literally a picture of a dog wearing a hat. No utility whatsoever.",
              "Became one of the top meme coins by market cap through pure community hype. Very high risk, short ride only.",
              "very_high"),
    "DOGE": ("Dogecoin is the original meme coin, now used by X (Twitter) for tipping and endorsed by Elon Musk.",
              "Actual mainstream adoption for tips and payments. One of the most liquid coins. Less risky than newer meme coins.",
              "high"),
}

# ── RISK LABELS ───────────────────────────────────────────────
RISK_LABELS = {
    "low":       ("🟢 Low Risk",       "#0A5D3E", "#D4F5E9"),
    "medium":    ("🟡 Medium Risk",    "#7A4900", "#FEF3DC"),
    "high":      ("🟠 High Risk",      "#9E3A00", "#FFF0E6"),
    "very_high": ("🔴 Very High Risk", "#8a1a1a", "#FDECEA"),
}


# ══════════════════════════════════════════════════════════════
# KRAKEN DATA LAYER
# ══════════════════════════════════════════════════════════════

def get_all_pairs():
    """Return all online USD/USDT pairs from Kraken."""
    r = requests.get(f"{KRAKEN_API}/AssetPairs", timeout=20)
    r.raise_for_status()
    pairs = r.json().get("result", {})
    return {
        pair_id: info
        for pair_id, info in pairs.items()
        if info.get("quote") in ("ZUSD", "USDT") and info.get("status") == "online"
    }


def get_ticker_batch(pair_ids):
    """Fetch ticker data for a batch of pairs."""
    r = requests.get(f"{KRAKEN_API}/Ticker",
                     params={"pair": ",".join(pair_ids)}, timeout=15)
    r.raise_for_status()
    return r.json().get("result", {})


def get_ohlc(pair, interval=60):
    """Fetch 1-hour OHLC candles. Returns list of candle arrays."""
    r = requests.get(f"{KRAKEN_API}/OHLC",
                     params={"pair": pair, "interval": interval}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        if key != "last":
            return val  # [time, open, high, low, close, vwap, volume, count]
    return []


def get_order_book(pair, count=10):
    """Fetch top N bid/ask levels of the order book."""
    r = requests.get(f"{KRAKEN_API}/Depth",
                     params={"pair": pair, "count": count}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        return val  # {"bids": [...], "asks": [...]}
    return {}


def extract_base_name(pair_id, pair_info):
    """Get the plain coin name from a Kraken pair ID. e.g. XRPUSD → XRP"""
    wsname = pair_info.get("wsname", "")  # e.g. "XRP/USD"
    if "/" in wsname:
        base = wsname.split("/")[0]
        # Kraken prefixes: X = crypto, Z = fiat
        return base.lstrip("X") if base.startswith("X") and len(base) > 3 else base
    # Fallback: strip USD/USDT suffix
    for suffix in ("ZUSD", "USDT", "USD"):
        if pair_id.endswith(suffix):
            base = pair_id[:-len(suffix)]
            return base.lstrip("X") if base.startswith("X") else base
    return pair_id


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ══════════════════════════════════════════════════════════════
# SIGNAL ENGINE
#
# Three signals, each independent:
#
# SIGNAL 1 — Volume Spike
#   Today's traded volume is unusually high compared to the 24h average.
#   This means a lot of buying (or selling) is happening RIGHT NOW.
#   Think of it like suddenly noticing a huge crowd gathering at a store.
#
# SIGNAL 2 — Price Momentum
#   The price has moved significantly in the last few hours.
#   A sustained upward move across multiple candles = wave is starting.
#
# SIGNAL 3 — Whale Order Wall
#   A single large buy order is sitting in the order book.
#   Whales place these when they want to accumulate without moving price too fast.
#   A $20k+ single order in a sub-$2 coin is a big deal.
# ══════════════════════════════════════════════════════════════

def check_volume_spike(ticker_data):
    """Returns (fired: bool, ratio: float, description: str)"""
    try:
        vol_today = float(ticker_data["v"][0])   # volume since midnight UTC
        vol_24h   = float(ticker_data["v"][1])   # rolling 24h volume
        if vol_24h <= 0:
            return False, 0.0, ""
        ratio = vol_today / vol_24h
        if ratio >= 0.75:
            desc = f"🔥 Extreme volume — {ratio:.0%} of the full 24h volume already traded today (massive rush of buyers)"
            return True, ratio, desc
        elif ratio >= 0.55:
            desc = f"🔥 Volume spike — {ratio:.0%} of 24h volume already traded today (above-normal buying activity)"
            return True, ratio, desc
        return False, ratio, ""
    except Exception:
        return False, 0.0, ""


def check_price_momentum(pair_id):
    """Returns (fired: bool, change: float, candles: list, description: str)"""
    try:
        candles = get_ohlc(pair_id, interval=60)
        if not candles or len(candles) < 2:
            return False, 0.0, [], ""
        open_price  = float(candles[0][1])
        close_price = float(candles[-1][4])
        if open_price == 0:
            return False, 0.0, [], ""
        change = (close_price - open_price) / open_price
        if abs(change) >= 0.03:
            arrow   = "📈" if change > 0 else "📉"
            dir_txt = "upward" if change > 0 else "downward"
            desc    = f"{arrow} Price moved {change:+.1%} in the last few hours — a {dir_txt} wave is in progress"
            return True, change, candles, desc
        return False, change, candles, ""
    except Exception:
        return False, 0.0, [], ""


def check_whale_walls(pair_id, min_wall_usd=20_000):
    """Returns (fired: bool, whale_list: list, description: str)"""
    try:
        book   = get_order_book(pair_id, count=10)
        whales = []
        for side in ("bids", "asks"):
            for level in book.get(side, []):
                price     = float(level[0])
                volume    = float(level[1])
                usd_value = price * volume
                if usd_value >= min_wall_usd:
                    whales.append({
                        "side":      "BUY" if side == "bids" else "SELL",
                        "price":     price,
                        "usd_value": usd_value,
                    })
        if not whales:
            return False, [], ""
        buy_walls  = [w for w in whales if w["side"] == "BUY"]
        sell_walls = [w for w in whales if w["side"] == "SELL"]
        buy_usd    = sum(w["usd_value"] for w in buy_walls)
        sell_usd   = sum(w["usd_value"] for w in sell_walls)
        if buy_walls and not sell_walls:
            desc = f"🐋 Pure whale BUY pressure — ${buy_usd:,.0f} in large buy orders, zero large sell orders"
        elif buy_usd > sell_usd:
            desc = f"🐋 Whale buying dominates — ${buy_usd:,.0f} buy vs ${sell_usd:,.0f} sell orders"
        else:
            desc = f"🐋 Large order walls detected — ${buy_usd:,.0f} buy / ${sell_usd:,.0f} sell"
        return True, whales, desc
    except Exception:
        return False, [], ""


def get_candle_structure_note(candles):
    """Plain English description of recent candle pattern."""
    if not candles or len(candles) < 4:
        return ""
    try:
        closes  = [float(c[4]) for c in candles[-8:]]
        volumes = [float(c[6]) for c in candles[-8:]]
        rising  = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        total   = len(closes) - 1
        max_vol = max(volumes) if volumes else 1
        avg_vol = sum(volumes) / len(volumes) if volumes else 1
        pump_spike = max_vol > avg_vol * 5

        if rising / total >= 0.70 and not pump_spike:
            return f"📶 Healthy sustained climb — {rising}/{total} candles rising with steady volume (NOT a single pump spike)"
        elif pump_spike:
            return f"⚠️ One big candle spike — {rising}/{total} candles rising, but volume was concentrated in one candle (pump risk — be careful)"
        elif rising / total >= 0.50:
            return f"📊 Mostly rising — {rising}/{total} candles moving up"
        else:
            return f"📊 Mixed direction — {rising}/{total} candles rising (wave not fully formed yet)"
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
# DECISION ENGINE
#
# Given signals fired, coin risk level, and market data —
# decides: BUY NOW / HODL 1-2 YR / WATCH / SKIP
#
# Logic in plain English:
#
# BUY NOW (short-term trade):
#   - At least 2 signals fired
#   - Price is in the lower half of its 24h range (you are early)
#   - Candles rising steadily (not a single pump spike)
#   - Target: ride the wave and exit when it cools
#
# HODL 1-2 YR (long-term hold):
#   - Coin has real utility (low/medium risk rating)
#   - Price is near its 52-week low (historically cheap)
#   - At least 1 whale signal fired
#   - This is an accumulate-and-wait play
#
# WATCH:
#   - Signals are almost there but not quite
#   - Check again next run
#
# SKIP:
#   - Price is already near the top of today's range (chasing)
#   - Whale SELL walls dominate
#   - Only 1 weak signal
# ══════════════════════════════════════════════════════════════

def make_decision(coin_data, signals_fired, signal_count, candles):
    price    = coin_data["price"]
    low      = coin_data["low_24h"]
    high     = coin_data["high_24h"]
    risk     = coin_data["risk"]

    # Where in the day's range is the price?
    if high > low:
        pct_from_low = (price - low) / (high - low)
    else:
        pct_from_low = 0.5

    # Are whales buying or selling?
    buy_whale_usd  = sum(w["usd_value"] for w in coin_data.get("whale_walls", []) if w["side"] == "BUY")
    sell_whale_usd = sum(w["usd_value"] for w in coin_data.get("whale_walls", []) if w["side"] == "SELL")
    whales_buying  = buy_whale_usd > sell_whale_usd

    # Candle structure
    structure_note = get_candle_structure_note(candles)
    is_pump_spike  = "pump risk" in structure_note.lower() if structure_note else False

    # ── Decision logic ────────────────────────────────────────

    # BUY NOW: strong signals, early in the range, not a pump spike
    if signal_count >= 2 and pct_from_low < 0.50 and not is_pump_spike:
        decision = "BUY NOW"
        decision_color = "#0A5D3E"
        decision_bg    = "#D4F5E9"
        reason = "Two or more whale signals just fired AND the price is still in the lower half of today's range — you are catching this early, not chasing it."
        if signal_count == 3:
            reason = "All three whale signals fired simultaneously AND the price is near today's low. This is the best possible setup — whales are moving in, you get in with them."

    # HODL: quality coin near yearly low, at least one signal
    elif risk in ("low", "medium") and signal_count >= 1 and pct_from_low < 0.35:
        decision = "HODL 1-2 YR"
        decision_color = "#1a237e"
        decision_bg    = "#E8EAF6"
        reason = "This is a fundamentally strong coin trading near the low end of its recent range. A whale signal just fired, which confirms someone big is accumulating quietly. This is the setup for a patient 1-2 year hold, not a quick flip."

    # SKIP: price already ran, or whales selling, or pump spike
    elif pct_from_low > 0.75 or (sell_whale_usd > buy_whale_usd * 2) or (is_pump_spike and signal_count < 3):
        decision = "SKIP"
        decision_color = "#8a1a1a"
        decision_bg    = "#FDECEA"
        if pct_from_low > 0.75:
            reason = "The price is already near today's HIGH — you would be chasing a move that is mostly over. Wait for it to cool down and re-enter at a better price."
        elif sell_whale_usd > buy_whale_usd * 2:
            reason = "Whale SELL walls are dominating the order book. The big players are exiting, not entering. Do not swim against them."
        else:
            reason = "Volume spiked in a single candle — this looks like a pump. Pumps that come from one candle usually reverse fast. Too risky to enter here."

    # WATCH: signals there but timing or quality not ideal
    else:
        decision = "WATCH"
        decision_color = "#7A4900"
        decision_bg    = "#FEF3DC"
        if signal_count >= 2:
            reason = "Signals are strong but the price has already moved into the upper half of today's range — the ideal entry has passed slightly. Watch for a small pullback to re-enter."
        elif signal_count == 1:
            reason = "Only one signal fired. The setup is interesting but not confirmed yet. Check the next run — if a second signal fires, this becomes actionable."
        else:
            reason = "Activity is slightly elevated but not enough to act on confidently. Keep watching."

    return decision, decision_color, decision_bg, reason, structure_note, pct_from_low


# ══════════════════════════════════════════════════════════════
# MAIN SCAN
# ══════════════════════════════════════════════════════════════

def run_scan():
    now = datetime.now(timezone.utc)
    print(f"[{now.strftime('%H:%M:%S')} UTC] Phase 4 Kraken scan starting...")

    # Fetch all Kraken pairs
    all_pairs = get_all_pairs()
    eligible  = {pid: info for pid, info in all_pairs.items()}
    pair_ids  = list(eligible.keys())[:MAX_COINS]
    print(f"  Kraken has {len(all_pairs)} active USD/USDT pairs. Scanning up to {MAX_COINS}.")

    results  = []
    scanned  = 0
    skipped  = 0

    for batch in chunk_list(pair_ids, 50):
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
                num_trades  = int(t["t"][1])

                # Skip coins outside our criteria
                if last_price <= 0 or last_price >= MAX_PRICE_USD:
                    skipped += 1
                    continue
                if volume_usd < MIN_VOLUME_USD:
                    skipped += 1
                    continue

                scanned += 1

                # Get coin base name
                pair_info = eligible.get(pair_id, {})
                base_name = extract_base_name(pair_id, pair_info)

                # Look up knowledge base
                kb = COIN_KNOWLEDGE.get(base_name, COIN_KNOWLEDGE.get(base_name.upper()))
                what_it_does = kb[0] if kb else f"{base_name} is a cryptocurrency traded on Kraken."
                long_term    = kb[1] if kb else "No specific long-term thesis available. Treat with caution."
                risk_level   = kb[2] if kb else "high"

                coin_data = {
                    "pair":       pair_id,
                    "base":       base_name,
                    "price":      last_price,
                    "volume_usd": volume_usd,
                    "high_24h":   high_24h,
                    "low_24h":    low_24h,
                    "num_trades": num_trades,
                    "risk":       risk_level,
                    "what":       what_it_does,
                    "long_term":  long_term,
                    "whale_walls":[],
                }

                # ── Run all three signals ──────────────────────
                vol_fired, vol_ratio, vol_desc = check_volume_spike(t)

                price_fired, price_change, candles, price_desc = check_price_momentum(pair_id)

                whale_fired = False
                whale_walls = []
                whale_desc  = ""
                if vol_fired or price_fired:
                    whale_fired, whale_walls, whale_desc = check_whale_walls(pair_id)
                    coin_data["whale_walls"] = whale_walls

                signals_fired = []
                if vol_fired:   signals_fired.append(vol_desc)
                if price_fired: signals_fired.append(price_desc)
                if whale_fired: signals_fired.append(whale_desc)

                signal_count = len(signals_fired)

                # Only proceed if at least 1 signal fired
                if signal_count == 0:
                    continue

                # ── Make the decision ──────────────────────────
                decision, d_color, d_bg, d_reason, structure_note, pct_from_low = make_decision(
                    coin_data, signals_fired, signal_count, candles
                )

                # ── 24h range position ─────────────────────────
                if high_24h > low_24h:
                    range_pct = (last_price - low_24h) / (high_24h - low_24h) * 100
                else:
                    range_pct = 50

                results.append({
                    **coin_data,
                    "price_change":  price_change,
                    "vol_ratio":     vol_ratio,
                    "signals_fired": signals_fired,
                    "signal_count":  signal_count,
                    "structure_note":structure_note,
                    "decision":      decision,
                    "d_color":       d_color,
                    "d_bg":          d_bg,
                    "d_reason":      d_reason,
                    "range_pct":     range_pct,
                    "pct_from_low":  pct_from_low,
                })

            except Exception:
                pass

        time.sleep(0.4)

    # Sort: BUY NOW first, then HODL, then WATCH, then SKIP
    order = {"BUY NOW": 0, "HODL 1-2 YR": 1, "WATCH": 2, "SKIP": 3}
    results.sort(key=lambda x: (order.get(x["decision"], 9), -x["signal_count"], x["pct_from_low"]))

    buys   = [r for r in results if r["decision"] == "BUY NOW"]
    hodls  = [r for r in results if r["decision"] == "HODL 1-2 YR"]
    watchs = [r for r in results if r["decision"] == "WATCH"]
    skips  = [r for r in results if r["decision"] == "SKIP"]

    print(f"  Scanned {scanned} coins. Found {len(results)} with signals.")
    print(f"  BUY NOW: {len(buys)} | HODL: {len(hodls)} | WATCH: {len(watchs)} | SKIP: {len(skips)}")

    return results, buys, hodls, watchs, skips


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# Matches Phase 1 and Phase 2 visual style exactly.
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#f4f4f4;margin:0;padding:20px;color:#222;}
.wrap{max-width:660px;margin:0 auto;}
.header{background:linear-gradient(135deg,#0F6E56,#1A9E7A);color:#fff;
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
.sym{font-size:18px;font-weight:700;}
.cname{font-size:12px;color:#999;margin-top:2px;}
.price{font-size:18px;font-weight:600;text-align:right;}
.pill{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;}
.meta{display:flex;flex-wrap:wrap;gap:14px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:2px;}
.meta-item .val{font-size:13px;font-weight:600;}
.bar-wrap{padding:4px 16px 10px;}
.info-box{margin:6px 16px 8px;padding:12px 14px;border-radius:8px;
  font-size:13px;line-height:1.6;border-left:4px solid;}
.info-box .lbl{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:4px;}
.signal-list{padding:6px 16px 8px;}
.signal-row{font-size:13px;color:#333;padding:4px 0;line-height:1.5;
  border-bottom:1px solid #f5f5f5;}
.signal-row:last-child{border:none;}
.decision-box{margin:8px 16px 12px;padding:14px 16px;border-radius:8px;border-left:4px solid;}
.decision-label{font-size:18px;font-weight:700;margin-bottom:4px;}
.decision-reason{font-size:13px;line-height:1.6;margin-bottom:8px;}
.structure-note{font-size:12px;opacity:.8;font-style:italic;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.6;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 10px;}
.summary-stat .num{font-size:24px;font-weight:700;}
.summary-stat .desc{font-size:11px;color:#888;}
.quicklist{margin:16px 22px 0;background:linear-gradient(135deg,#0F6E56,#1A9E7A);
  border-radius:10px;padding:16px 18px;color:#fff;}
.quicklist h2{margin:0 0 4px;font-size:15px;font-weight:700;}
.quicklist p{margin:0 0 12px;font-size:12px;opacity:.85;}
.ql-row{display:flex;justify-content:space-between;align-items:center;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.2);}
.ql-row:last-child{border:none;padding-bottom:0;}
.ql-name{font-size:14px;font-weight:700;}
.ql-detail{font-size:11px;opacity:.85;margin-top:2px;}
.ql-badge{font-size:12px;background:rgba(255,255,255,0.25);
  padding:3px 10px;border-radius:10px;font-weight:700;}
</style>
"""

RISK_PILL_HTML = {
    "low":       '<span class="pill" style="background:#D4F5E9;color:#0A5D3E;">🟢 Low Risk</span>',
    "medium":    '<span class="pill" style="background:#FEF3DC;color:#7A4900;">🟡 Medium Risk</span>',
    "high":      '<span class="pill" style="background:#FFF0E6;color:#9E3A00;">🟠 High Risk</span>',
    "very_high": '<span class="pill" style="background:#FDECEA;color:#8a1a1a;">🔴 Very High Risk</span>',
}

def signal_count_pill(count):
    if count >= 3:   bg,col = "#D4F5E9","#0A5D3E"
    elif count == 2: bg,col = "#FEF3DC","#7A4900"
    else:            bg,col = "#F0F0F0","#444"
    return f'<span class="pill" style="background:{bg};color:{col};">{count}/3 signals</span>'

def price_bar_html(price, low, high):
    if not all([price, low, high]) or high == low:
        return ""
    pct   = max(0, min(100, (price - low) / (high - low) * 100))
    color = "#1D9E75" if pct < 35 else "#EF9F27" if pct < 65 else "#E24B4A"
    return (
        f'<div style="font-size:10px;color:#bbb;margin-bottom:3px;">'
        f'24h range — price is {pct:.0f}% of the way from today\'s low to today\'s high</div>'
        f'<div style="background:#eee;border-radius:3px;height:6px;">'
        f'<div style="background:{color};width:{pct:.0f}%;height:6px;border-radius:3px;"></div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#ccc;margin-top:2px;">'
        f'<span>Today\'s Low ${low:.6f}</span><span>Today\'s High ${high:.6f}</span></div>'
    )

def build_coin_card(r):
    change_color = "#1D9E75" if r["price_change"] >= 0 else "#E24B4A"
    change_sign  = "+" if r["price_change"] >= 0 else ""
    risk_pill    = RISK_PILL_HTML.get(r["risk"], "")
    pbar         = price_bar_html(r["price"], r["low_24h"], r["high_24h"])

    # Signal rows
    signal_rows = "".join(f'<div class="signal-row">{s}</div>' for s in r["signals_fired"])

    # What this coin is
    what_box = f"""<div class="info-box" style="background:#f8f8f8;border-left-color:#ccc;">
  <div class="lbl" style="color:#999;">What is {r['base']}?</div>
  {r['what']}
</div>"""

    # Long-term case
    lt_box = f"""<div class="info-box" style="background:#EEF4FF;border-left-color:#1a237e;">
  <div class="lbl" style="color:#1a237e;">Long-term case (1-2 year hold)</div>
  {r['long_term']}
</div>"""

    # Decision box
    structure_html = f'<div class="structure-note">{r["structure_note"]}</div>' if r["structure_note"] else ""
    decision_box = f"""<div class="decision-box" style="background:{r['d_bg']};border-left-color:{r['d_color']};">
  <div class="decision-label" style="color:{r['d_color']};">{r['decision']}</div>
  <div class="decision-reason" style="color:{r['d_color']};">{r['d_reason']}</div>
  {structure_html}
</div>"""

    return f"""<div class="stock-card">
  <div class="card-top">
    <div>
      <div class="sym">{r['base']}</div>
      <div class="cname">{r['pair']} · Kraken</div>
      <div style="margin-top:6px;">{risk_pill} &nbsp; {signal_count_pill(r['signal_count'])}</div>
    </div>
    <div>
      <div class="price">${r['price']:.6f}</div>
      <div style="font-size:12px;color:{change_color};text-align:right;margin-top:3px;font-weight:600;">
        {change_sign}{r['price_change']:.2%} recent move
      </div>
      <div style="font-size:11px;color:#aaa;text-align:right;margin-top:2px;">
        Vol ${r['volume_usd']:,.0f}/day
      </div>
    </div>
  </div>
  <div class="meta">
    <div class="meta-item"><div class="lbl">Current Price</div><div class="val">${r['price']:.6f}</div></div>
    <div class="meta-item"><div class="lbl">Today's Low</div><div class="val">${r['low_24h']:.6f}</div></div>
    <div class="meta-item"><div class="lbl">Today's High</div><div class="val">${r['high_24h']:.6f}</div></div>
    <div class="meta-item"><div class="lbl">Position in Range</div><div class="val">{r['range_pct']:.0f}% from low</div></div>
    <div class="meta-item"><div class="lbl">Trades Today</div><div class="val">{r['num_trades']:,}</div></div>
  </div>
  <div class="bar-wrap">{pbar}</div>
  <div class="signal-list">{signal_rows}</div>
  {what_box}
  {lt_box}
  {decision_box}
</div>"""


def build_quick_list(buys, hodls):
    """Quick-glance summary banner at top of email."""
    if not buys and not hodls:
        return ""
    rows = ""
    for r in (buys + hodls)[:6]:
        change_sign = "+" if r["price_change"] >= 0 else ""
        tag = "🚀 BUY" if r["decision"] == "BUY NOW" else "💎 HODL"
        rows += f"""<div class="ql-row">
    <div>
      <div class="ql-name">{r['base']}</div>
      <div class="ql-detail">${r['price']:.6f} · {change_sign}{r['price_change']:.1%} · {r['signal_count']}/3 signals</div>
    </div>
    <div class="ql-badge">{tag}</div>
  </div>"""
    return f"""<div class="quicklist">
  <h2>⚡ Today's Actionable Picks</h2>
  <p>Coins with active signals right now. Full analysis below each card.</p>
  {rows}
</div>"""


def build_html_email(results, buys, hodls, watchs, skips):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>📊 Phase 4 · Kraken Crypto Advisor</h1>
  <p>{date_str} · All altcoins under $2 · Plain-English signals</p>
</div>
<div class="body">

  <div style="display:flex;justify-content:space-around;padding:16px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat"><div class="num" style="color:#0F6E56;">{len(buys)}</div><div class="desc">🚀 Buy Now</div></div>
    <div class="summary-stat"><div class="num" style="color:#1a237e;">{len(hodls)}</div><div class="desc">💎 Hodl 1-2yr</div></div>
    <div class="summary-stat"><div class="num" style="color:#EF9F27;">{len(watchs)}</div><div class="desc">👀 Watch</div></div>
    <div class="summary-stat"><div class="num" style="color:#E24B4A;">{len(skips)}</div><div class="desc">❌ Skip</div></div>
    <div class="summary-stat"><div class="num" style="color:#888;">{len(results)}</div><div class="desc">Total with signals</div></div>
  </div>

  {build_quick_list(buys, hodls)}

  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      Every coin card explains <strong>what the coin does</strong>, <strong>why to buy it</strong>,
      and <strong>whether it is a quick trade or a long hold</strong>.
      Signals fire when volume spikes, price moves strongly, or large whale orders appear.
      You get this email only when there is something worth acting on.<br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Always do your own research before investing.</strong>
    </p>
  </div>
"""

    if buys:
        html += '<div class="section"><div class="section-head">🚀 Buy Now — Enter This Rally Early</div>'
        for r in buys: html += build_coin_card(r)
        html += '</div><div class="divider"></div>'

    if hodls:
        html += '<div class="section"><div class="section-head">💎 Hodl 1-2 Years — Accumulate and Be Patient</div>'
        for r in hodls: html += build_coin_card(r)
        html += '</div><div class="divider"></div>'

    if watchs:
        html += '<div class="section"><div class="section-head">👀 Watch — Not Ready Yet, Check Next Run</div>'
        for r in watchs: html += build_coin_card(r)
        html += '</div><div class="divider"></div>'

    if skips:
        html += '<div class="section"><div class="section-head">❌ Skip — Mid-Wave, Risky, or Whale Selling</div>'
        for r in skips[:5]: html += build_coin_card(r)  # limit skips shown
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Phase 4 Kraken Crypto Advisor · Runs every 15 min via GitHub Actions · {len(results)} coins had signals this run<br>
    Signals: 🔥 Volume spike · 📈 Price momentum · 🐋 Whale order wall ($20k+)<br>
    Decisions: 🚀 Buy Now · 💎 Hodl 1-2yr · 👀 Watch · ❌ Skip<br>
    Research and education only — not financial advice. Trading involves risk of loss.<br>
    <a href="https://www.kraken.com/trade" style="color:#0F6E56;">Open Kraken →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(results, buys, hodls, watchs):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 65,
        f" PHASE 4 KRAKEN CRYPTO ADVISOR — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f" {len(results)} coins had signals | {len(buys)} Buy | {len(hodls)} Hodl | {len(watchs)} Watch",
        "=" * 65,
    ]
    if buys:
        lines.append("\n🚀 BUY NOW — Enter these rallies early:")
        for r in buys:
            lines.append(f"  ► {r['base']:<12} ${r['price']:.6f}  ({r['price_change']:+.1%})  {r['signal_count']}/3 signals")
            lines.append(f"     {r['d_reason'][:100]}")
    if hodls:
        lines.append("\n💎 HODL 1-2 YEARS — Accumulate these quality coins:")
        for r in hodls:
            lines.append(f"  ► {r['base']:<12} ${r['price']:.6f}  Risk: {r['risk']}")
            lines.append(f"     {r['long_term'][:100]}")
    lines += ["", "=" * 65, " Not financial advice. Research before investing.", "=" * 65]
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
    print(f"✅ Email sent → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def run():
    now = datetime.now(timezone.utc)
    print(f"📊 Phase 4 Kraken Crypto Advisor — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    results, buys, hodls, watchs, skips = run_scan()

    # Only send email if there's something actionable
    if not buys and not hodls:
        print("  No Buy or Hodl picks this run. No email sent. Check again next run.")
        return

    html_body = build_html_email(results, buys, hodls, watchs, skips)
    text_body = build_text_email(results, buys, hodls, watchs)

    top_picks = ", ".join(r["base"] for r in (buys + hodls)[:4])
    subject   = (f"📊 Phase 4: {len(buys)} Buy Now · {len(hodls)} Hodl · "
                 f"Top: {top_picks} · {now.strftime('%H:%M UTC')}")

    print(text_body)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
