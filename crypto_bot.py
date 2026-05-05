# ============================================================
# TRADING BOT — PHASE 3 (Kraken Whale Tracker + Buy Advisor)
#
# ► Tracks ONLY fundamentally sound altcoins on Kraken under $2
# ► Coins are hand-curated with investment thesis and tier ratings
# ► Detects whale movements: volume spikes, price momentum, order walls
# ► Scores each coin 0–100 for long-term buy conviction
# ► Sends Gmail with: altseason context, top picks banner, full card analysis
#
# Runs every 15 min via GitHub Actions. No paid API needed.
#
# SECRETS (GitHub → Settings → Secrets → Actions):
#   EMAIL_SENDER    — your Gmail address
#   EMAIL_PASSWORD  — Gmail App Password (16 chars, not your login pw)
#   EMAIL_RECIPIENT — where to receive alerts (can be same as sender)
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

# ── THRESHOLDS ────────────────────────────────────────────────
MAX_PRICE_USD        = 2.00
MIN_VOLUME_USD       = 30_000   # lower than before — some quality coins have less vol
PRICE_MOVE_THRESHOLD = 0.03
ORDER_BOOK_WALL_USD  = 20_000   # slightly lower — these coins have smaller books
TODAY_VOL_RATIO      = 0.55
SIGNALS_REQUIRED     = 2

# ══════════════════════════════════════════════════════════════
# CURATED COIN WHITELIST
#
# These are coins on Kraken under $2 with REAL fundamentals.
# Screened for: utility, active development, strong community,
#               Kraken listing (legitimacy signal), and
#               long-term upside if altseason arrives.
#
# TIERS:
#   S — Blue chip altcoin, proven ecosystem, lowest risk
#   A — Strong fundamentals, high upside, moderate risk
#   B — Good project, speculative but grounded, higher risk
#   C — Meme/narrative coin, high risk, community-driven
#
# YOUR HOLDINGS noted where relevant (PENGU, LUNC).
#
# ⚠️ NOTE ON PENGU: PENGU (Pudgy Penguins) is on Kraken.
#    Current price ~$0.009. It is a meme/NFT token — high risk,
#    high community support. Treat as a C-tier speculative bet.
#
# ⚠️ NOTE ON LUNA: You likely mean LUNC (Terra Classic) on Kraken.
#    The original LUNA collapsed in May 2022. LUNC is the rebranded
#    remnant. It is extremely high risk — treat as lottery-ticket only.
#    New LUNA (Terra 2.0) = LUNA on some exchanges, not Kraken.
# ══════════════════════════════════════════════════════════════

COIN_WHITELIST = {

    # ── TIER S — Blue Chip Infrastructure ─────────────────────

    "ADAUSD":  {"name": "Cardano",       "tier": "S", "thesis": "Peer-reviewed PoS chain. Academic rigour, Hydra scaling live, strong dev activity. ADA at ~$0.25 is a deep-value entry vs its $3 ATH. Pure infrastructure play."},
    "ADAUSDT": {"name": "Cardano",       "tier": "S", "thesis": "Same as ADAUSD — buy whichever pair has more liquidity on Kraken."},
    "XRPUSD":  {"name": "XRP",           "tier": "S", "thesis": "SEC lawsuit fully resolved. Institutional adoption growing. Ripple's On-Demand Liquidity used by 30+ banks. XRP ETF under review. One of the safest under-$2 bets."},
    "XRPUSDT": {"name": "XRP",           "tier": "S", "thesis": "Same as XRPUSD."},
    "XLMUSD":  {"name": "Stellar",       "tier": "S", "thesis": "Cross-border payments infrastructure. ISO 20022 compliant. Used by MoneyGram, IBM. Moves with XRP but lags it — often offers better entry timing."},
    "XLMUSDT": {"name": "Stellar",       "tier": "S", "thesis": "Same as XLMUSD."},
    "ALGOUSD": {"name": "Algorand",      "tier": "S", "thesis": "Carbon-negative PoS chain. Pure-proof-of-stake, instant finality. Used by sovereign nations for CBDCs. ALGO under $0.30 = historically undervalued vs fundamentals."},
    "ALGOUSDT":{"name": "Algorand",      "tier": "S", "thesis": "Same as ALGOUSD."},
    "HBARUSD": {"name": "Hedera",        "tier": "S", "thesis": "Enterprise-grade distributed ledger. Governed by Google, IBM, Boeing, LG. 10,000 TPS, near-zero fees. HBAR is an institution-first play for the next cycle."},
    "HBARUSDT":{"name": "Hedera",        "tier": "S", "thesis": "Same as HBARUSD."},

    # ── TIER A — Strong Fundamentals, High Upside ─────────────

    "MATICUSD": {"name": "Polygon",      "tier": "A", "thesis": "Ethereum's #1 scaling layer. Used by Nike, Starbucks, Reddit NFTs. POL migration underway. Deeply undervalued vs. usage metrics. When ETH runs, MATIC runs harder."},
    "MATICUSDT":{"name": "Polygon",      "tier": "A", "thesis": "Same as MATICUSD."},
    "DOTUSD":  {"name": "Polkadot",      "tier": "A", "thesis": "Parachain ecosystem connecting blockchains. JAM upgrade improves scalability dramatically. DOT under $5 is historically cheap. Slower but steady accumulation pattern."},
    "DOTUSDT": {"name": "Polkadot",      "tier": "A", "thesis": "Same as DOTUSD."},
    "LINKUSD": {"name": "Chainlink",     "tier": "A", "thesis": "The oracle network that every DeFi protocol depends on. CCIP cross-chain protocol growing rapidly. LINK has a history of exploding in late bull cycles. Critical infrastructure."},
    "LINKUSDT":{"name": "Chainlink",     "tier": "A", "thesis": "Same as LINKUSD."},
    "ARBUSD":  {"name": "Arbitrum",      "tier": "A", "thesis": "Ethereum's largest L2 by TVL. Robinhood uses it for tokenized stocks. 2.4M+ DeFi users, 53M+ monthly transactions. ARB under $0.50 is a strong accumulation zone."},
    "ARBUSDT": {"name": "Arbitrum",      "tier": "A", "thesis": "Same as ARBUSD."},
    "OPUSD":   {"name": "Optimism",      "tier": "A", "thesis": "OP Stack powers Coinbase's Base chain and dozens of L2s. Revenue shared back to token holders. Ecosystem TVL growing. OP is the infrastructure behind much of Ethereum scaling."},
    "OPUSDT":  {"name": "Optimism",      "tier": "A", "thesis": "Same as OPUSD."},
    "ICPUSD":  {"name": "Internet Computer","tier": "A", "thesis": "Full-stack decentralized compute. Can host entire apps on-chain. ICP under $5 is historically cheap. Long-term thesis: cloud computing disruption. High risk/reward."},
    "ICPUSDT": {"name": "Internet Computer","tier": "A", "thesis": "Same as ICPUSD."},
    "GRTUSD":  {"name": "The Graph",     "tier": "A", "thesis": "The Google of blockchain data. Every major DeFi and NFT protocol indexes with The Graph. GRT is essential infrastructure that gets more valuable as on-chain data grows."},
    "GRTUSDT": {"name": "The Graph",     "tier": "A", "thesis": "Same as GRTUSD."},
    "ENJUSD":  {"name": "Enjin",         "tier": "A", "thesis": "Gaming NFT infrastructure. Samsung partnership. JumpNet for gas-free transactions. Gaming sector is a major 2026 narrative — ENJ is well-positioned early."},
    "ENJUSDT": {"name": "Enjin",         "tier": "A", "thesis": "Same as ENJUSD."},

    # ── TIER B — Solid Projects, More Speculative ─────────────

    "VETUSD":  {"name": "VeChain",       "tier": "B", "thesis": "Supply chain blockchain. Walmart China, BMW, PwC partnerships. VET+VTHO dual-token model. Niche but real enterprise adoption. Moves explosively in bull markets."},
    "VETUSDT": {"name": "VeChain",       "tier": "B", "thesis": "Same as VETUSD."},
    "CHZUSD":  {"name": "Chiliz",        "tier": "B", "thesis": "Sports fan token infrastructure. 50+ football clubs including PSG, Barca, Man City. Millions of active users on Socios. Seasonal spikes around major sports events."},
    "CHZUSDT": {"name": "Chiliz",        "tier": "B", "thesis": "Same as CHZUSD."},
    "CRVUSD":  {"name": "Curve DAO",     "tier": "B", "thesis": "The backbone of stablecoin liquidity in DeFi. crvUSD stablecoin growing. If DeFi TVL returns in altseason, CRV explodes. Risky due to founder loan saga but fundamentals intact."},
    "CRVUSDT": {"name": "Curve DAO",     "tier": "B", "thesis": "Same as CRVUSD."},
    "SNXUSD":  {"name": "Synthetix",     "tier": "B", "thesis": "On-chain synthetic assets and perpetuals. Powers Kwenta, Lyra, and others. SNX is a high-beta DeFi play — bleeds in bear, rockets in bull. Entry now = pre-rotation positioning."},
    "SNXUSDT": {"name": "Synthetix",     "tier": "B", "thesis": "Same as SNXUSD."},
    "BALUSD":  {"name": "Balancer",      "tier": "B", "thesis": "Automated portfolio management and DEX. veBAL model aligns incentives well. Balancer v3 improving capital efficiency. A DeFi-infrastructure play for altseason."},
    "BALUSDT": {"name": "Balancer",      "tier": "B", "thesis": "Same as BALUSD."},
    "STORJUSD":{"name": "Storj",         "tier": "B", "thesis": "Decentralized cloud storage. Cheaper and faster than AWS S3. Real paying customers. Data sovereignty narrative growing. STORJ is a quiet utility token with real revenue."},
    "STORJUSDT":{"name": "Storj",        "tier": "B", "thesis": "Same as STORJUSD."},

    # ── TIER C — Meme / Narrative / Community-Driven ──────────
    # Higher risk. Buy small. Ride waves fast, exit fast.

    "PENGUSUSD": {"name": "PENGU (YOUR HOLDING)", "tier": "C",
                  "thesis": "Pudgy Penguins ecosystem token. Massive loyal community (The Huddle). Pudgy Party mobile game onboarding mainstream users. Real-world toys in Walmart. PENGU ETF acknowledged by SEC. High meme risk but stronger than average community. Treat as a speculative position — ride whale waves, set a clear exit target."},
    "LUNCUSD": {"name": "LUNC/Terra Classic (YOUR HOLDING)", "tier": "C",
                "thesis": "Terra Classic (LUNC) is what remained after the original LUNA collapsed in May 2022. The supply was hyperinflated (trillions of tokens). Burns via 1.2% tax on transactions. Community-driven revival attempt. EXTREMELY HIGH RISK — treat as a lottery ticket with money you can afford to lose entirely. If altseason comes, speculative coins like LUNC can 5-10x quickly — but they can also go to zero. Ride momentum only, never hold long-term."},
    "LUNCUSDT":{"name": "LUNC/Terra Classic (YOUR HOLDING)", "tier": "C",
                "thesis": "Same as LUNCUSD."},
    "BONKUSD": {"name": "BONK",          "tier": "C", "thesis": "Solana's original meme dog coin. Strong liquidity and whale activity. Moves with Solana ecosystem sentiment. Short-term whale ride candidate — don't hold for months."},
    "BONKUSDT":{"name": "BONK",          "tier": "C", "thesis": "Same as BONKUSD."},
    "PEPEUSD": {"name": "PEPE",          "tier": "C", "thesis": "Ethereum meme coin. ETF speculation driving attention in 2026. Pure community/sentiment play. High liquidity makes it tradeable. Whale activity here is meaningful — but exit fast."},
    "PEPEUSDT":{"name": "PEPE",          "tier": "C", "thesis": "Same as PEPEUSD."},
    "SHIBUSDT":{"name": "Shiba Inu",     "tier": "C", "thesis": "Large community. Shibarium L2 adds utility. SHIB burns ongoing. Slow burner that explodes in retail-driven phases. C-tier but with massive brand recognition."},
    "SHIBUSD": {"name": "Shiba Inu",     "tier": "C", "thesis": "Same as SHIBUSDT."},
    "FLRUSD":  {"name": "Flare",         "tier": "C", "thesis": "Smart contract platform for XRP, LTC, DOGE holders. FAssets bringing BTC/XRP into DeFi. Moves with XRP narrative. B-C tier hybrid — more utility than pure meme but still speculative."},
    "FLRUSDT": {"name": "Flare",         "tier": "C", "thesis": "Same as FLRUSD."},
}

# ── ALTSEASON CONTEXT (updated from current data) ─────────────
# This gets included in every email so you always know where we are in the cycle.
ALTSEASON_CONTEXT = {
    "index":        37,           # CoinMarketCap Altcoin Season Index (May 2026)
    "btc_dominance": 60.7,        # BTC.D % (higher = worse for altcoins)
    "phase":        "Bitcoin Season",
    "status":       "NOT YET",
    "enter_window": "Q3–Q4 2026 (Jul–Oct) if BTC reclaims $100k and Fed cuts rates",
    "exit_window":  "Watch for BTC.D rising back above 60% after altcoin run",
    "historical_pattern": {
        "2017": {"enter": "Aug–Sep", "exit": "Jan 2018",   "duration": "~5 months"},
        "2021": {"enter": "Jan–Feb", "exit": "Apr–May",    "duration": "~4 months (Wave 1)"},
        "2021b":{"enter": "Aug–Sep", "exit": "Nov 2021",   "duration": "~3 months (Wave 2)"},
        "2026e":{"enter": "Q3 2026", "exit": "Q4 2026?",   "duration": "Estimated 2–4 months"},
    },
    "key_trigger":  "BTC.D falls decisively below 54% → altseason begins. Watch weekly.",
    "warning":      "BTC.D just broke above 60% (May 2026) — capital flowing BACK to BTC. We are in Bitcoin Season. Altseason not yet confirmed. Use this time to ACCUMULATE quality coins at lows, not to chase pumps.",
}


# ══════════════════════════════════════════════════════════════
# KRAKEN DATA LAYER
# ══════════════════════════════════════════════════════════════

def get_all_whitelisted_pairs():
    """Return only the pairs in our curated whitelist."""
    return list(COIN_WHITELIST.keys())


def get_ticker_batch(pair_ids):
    r = requests.get(f"{KRAKEN_API}/Ticker", params={"pair": ",".join(pair_ids)}, timeout=15)
    r.raise_for_status()
    return r.json().get("result", {})


def get_ohlc(pair, interval=60):
    r = requests.get(f"{KRAKEN_API}/OHLC", params={"pair": pair, "interval": interval}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        if key != "last":
            return val
    return []


def get_order_book(pair, count=10):
    r = requests.get(f"{KRAKEN_API}/Depth", params={"pair": pair, "count": count}, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    for key, val in result.items():
        return val
    return {}


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ══════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ══════════════════════════════════════════════════════════════

def detect_volume_spike(ticker_data):
    try:
        vol_today = float(ticker_data["v"][0])
        vol_24h   = float(ticker_data["v"][1])
        if vol_24h <= 0: return False, 0.0
        ratio = vol_today / vol_24h
        return ratio >= TODAY_VOL_RATIO, ratio
    except Exception:
        return False, 0.0


def detect_price_momentum(pair_id):
    try:
        candles = get_ohlc(pair_id, interval=60)
        if not candles or len(candles) < 2: return False, 0.0, []
        open_price  = float(candles[0][1])
        close_price = float(candles[-1][4])
        if open_price == 0: return False, 0.0, []
        change = (close_price - open_price) / open_price
        return abs(change) >= PRICE_MOVE_THRESHOLD, change, candles
    except Exception:
        return False, 0.0, []


def detect_order_book_whales(pair_id):
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
                        "side":      "BUY wall" if side == "bids" else "SELL wall",
                        "price":     price,
                        "volume":    volume,
                        "usd_value": usd_value,
                    })
        return whales
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# CONVICTION SCORER
# ══════════════════════════════════════════════════════════════

def score_long_term_conviction(alert, candles):
    score   = 0
    reasons = []
    price   = alert["price"]
    low     = alert["low_24h"]
    high    = alert["high_24h"]
    change  = alert["price_change"]
    tier    = alert["tier"]

    # Tier bonus (quality coins start with a base advantage)
    tier_bonus = {"S": 12, "A": 8, "B": 4, "C": 0}
    score += tier_bonus.get(tier, 0)
    reasons.append(f"🏆 Tier {tier} coin — {['Blue chip infrastructure', 'Strong fundamentals', 'Solid project', 'Meme/narrative play'][['S','A','B','C'].index(tier) if tier in ['S','A','B','C'] else 3]}")

    # Pillar 1: Entry position (22 pts)
    if high > low:
        pct_from_low = (price - low) / (high - low)
        if pct_from_low < 0.25:
            score += 22
            reasons.append("📍 Near 24h low — excellent early entry, wave barely started")
        elif pct_from_low < 0.45:
            score += 16
            reasons.append("📍 Lower half of 24h range — still a good entry")
        elif pct_from_low < 0.65:
            score += 8
            reasons.append("📍 Mid-range price — acceptable but not ideal")
        else:
            score += 2
            reasons.append("⚠️ Near 24h high — risk of chasing a move that's half over")

    # Pillar 2: BUY vs SELL wall dominance (22 pts)
    buy_walls  = [w for w in alert["ob_whales"] if w["side"] == "BUY wall"]
    sell_walls = [w for w in alert["ob_whales"] if w["side"] == "SELL wall"]
    buy_usd    = sum(w["usd_value"] for w in buy_walls)
    sell_usd   = sum(w["usd_value"] for w in sell_walls)

    if buy_usd > 0 and sell_usd == 0:
        score += 22
        reasons.append(f"🐋 Pure BUY pressure — ${buy_usd:,.0f} whale buy walls, zero sell walls")
    elif buy_usd > sell_usd * 2:
        score += 17
        reasons.append(f"🐋 BUY walls dominate (${buy_usd:,.0f} buy vs ${sell_usd:,.0f} sell)")
    elif buy_usd > sell_usd:
        score += 10
        reasons.append(f"🐋 More buy than sell walls (${buy_usd:,.0f} vs ${sell_usd:,.0f})")
    elif sell_usd > buy_usd * 2:
        score += 0
        reasons.append(f"🚧 SELL walls dominate (${sell_usd:,.0f}) — whales may be exiting")
    else:
        score += 7
        reasons.append("📊 No large order walls — momentum driven by volume/price")

    # Pillar 3: Volume spike strength (18 pts)
    ratio = alert["spike_ratio"]
    if ratio >= 0.85:
        score += 18
        reasons.append(f"🔥 Extreme volume — {ratio:.0%} of 24h traded today (massive accumulation)")
    elif ratio >= 0.70:
        score += 13
        reasons.append(f"🔥 Strong volume spike — {ratio:.0%} of 24h traded today")
    elif ratio >= 0.55:
        score += 9
        reasons.append(f"🔥 Volume spike — {ratio:.0%} of 24h already traded")
    else:
        score += 3
        reasons.append(f"📊 Mild volume — {ratio:.0%} of 24h traded today")

    # Pillar 4: Price direction (14 pts)
    if change > 0.08:
        score += 14
        reasons.append(f"📈 Strong upward move +{change:.1%} — trend confirmed up")
    elif change > 0.03:
        score += 10
        reasons.append(f"📈 Upward momentum +{change:.1%} — wave in progress")
    elif change > 0:
        score += 6
        reasons.append(f"📈 Slight upward drift +{change:.1%} — possible early stage")
    elif change > -0.03:
        score += 4
        reasons.append(f"📊 Flat {change:.1%} — volume leading price (watch for breakout)")
    else:
        score += 0
        reasons.append(f"📉 Downward {change:.1%} — possible distribution, caution")

    # Pillar 5: Candle structure (12 pts)
    if candles and len(candles) >= 4:
        try:
            closes  = [float(c[4]) for c in candles[-8:]]
            volumes = [float(c[6]) for c in candles[-8:]]
            rising  = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
            rising_pct = rising / (len(closes) - 1)
            max_vol    = max(volumes) if volumes else 1
            avg_vol    = sum(volumes) / len(volumes) if volumes else 1
            pump_spike = max_vol > avg_vol * 5

            if rising_pct >= 0.70 and not pump_spike:
                score += 12
                reasons.append(f"📶 Healthy sustained climb — {rising}/{len(closes)-1} candles rising, spread volume")
            elif rising_pct >= 0.50 and not pump_spike:
                score += 8
                reasons.append(f"📶 Mostly rising ({rising}/{len(closes)-1} candles) — decent structure")
            elif pump_spike:
                score += 2
                reasons.append("⚠️ Single-candle spike — pump risk, not sustained momentum")
            else:
                score += 4
                reasons.append(f"📊 Mixed candle structure ({rising}/{len(closes)-1} rising)")
        except Exception:
            score += 4

    # C-tier penalty: community/meme coins need stronger signals
    if tier == "C":
        score = int(score * 0.85)
        reasons.append("⚠️ C-tier: meme/narrative coin — treat as short ride, not long hold")

    score = min(score, 100)

    if score >= 80:
        verdict, vc, vb = "🟢 STRONG BUY", "#0A5D3E", "#D4F5E9"
        note = "All signals aligned + quality coin — enter early, hold for the wave"
    elif score >= 60:
        verdict, vc, vb = "🟡 WATCH", "#7A4900", "#FEF3DC"
        note = "Good setup — wait for one more candle to confirm before entering"
    else:
        verdict, vc, vb = "🔴 SKIP", "#8a1a1a", "#FDECEA"
        note = "Too risky, mid-wave, or whale selling — sit this one out"

    return score, verdict, vc, vb, note, reasons


# ══════════════════════════════════════════════════════════════
# MAIN SCAN
# ══════════════════════════════════════════════════════════════

def scan_for_whales():
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Starting curated whitelist whale scan...")
    pairs = get_all_whitelisted_pairs()
    print(f"  Monitoring {len(pairs)} curated Kraken pairs")

    alerts  = []
    scanned = 0

    for batch in chunk_list(pairs, 50):
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

                if last_price <= 0 or last_price >= MAX_PRICE_USD: continue
                if volume_usd < MIN_VOLUME_USD: continue

                # Match to whitelist (Kraken may return slightly different pair IDs)
                coin_info = COIN_WHITELIST.get(pair_id) or COIN_WHITELIST.get(pair_id.upper())
                if not coin_info:
                    # Try fuzzy match — Kraken sometimes appends/changes casing
                    for wl_key in COIN_WHITELIST:
                        if wl_key.upper() in pair_id.upper() or pair_id.upper() in wl_key.upper():
                            coin_info = COIN_WHITELIST[wl_key]
                            break
                if not coin_info:
                    continue  # not in our curated list

                scanned += 1

                vol_spike, spike_ratio = detect_volume_spike(t)
                price_move, price_change, candles = detect_price_momentum(pair_id)

                ob_whales = []
                if vol_spike or price_move:
                    ob_whales = detect_order_book_whales(pair_id)

                signal_count = sum([vol_spike, price_move, bool(ob_whales)])
                if signal_count < SIGNALS_REQUIRED:
                    continue

                range_pct = ((high_24h - low_24h) / low_24h * 100) if low_24h > 0 else 0
                alert = {
                    "pair":         pair_id,
                    "name":         coin_info["name"],
                    "tier":         coin_info["tier"],
                    "thesis":       coin_info["thesis"],
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

                (conv_score, verdict, vc, vb, note, reasons) = score_long_term_conviction(alert, candles)
                alert.update({"conviction_score": conv_score, "verdict": verdict,
                               "verdict_color": vc, "verdict_bg": vb,
                               "verdict_note": note, "conv_reasons": reasons})
                alerts.append(alert)

            except Exception:
                pass

        time.sleep(0.5)

    verdict_order = {"🟢 STRONG BUY": 0, "🟡 WATCH": 1, "🔴 SKIP": 2}
    tier_order    = {"S": 0, "A": 1, "B": 2, "C": 3}
    alerts.sort(key=lambda x: (
        verdict_order.get(x["verdict"], 9),
        tier_order.get(x["tier"], 9),
        -x["conviction_score"]
    ))

    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    print(f"  Scanned {scanned} curated coins. Whale alerts: {len(alerts)}. Strong Buys: {len(strong_buys)}")
    return alerts


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#f4f4f4;margin:0;padding:20px;color:#222;}
.wrap{max-width:680px;margin:0 auto;}
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
.sym{font-size:16px;font-weight:700;}
.coin-name{font-size:12px;color:#888;margin-top:1px;}
.price{font-size:16px;font-weight:600;text-align:right;}
.pill{display:inline-block;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;}
.meta{display:flex;flex-wrap:wrap;gap:12px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:1px;}
.meta-item .val{font-size:12px;font-weight:600;}
.bar-wrap{padding:4px 16px 8px;}
.signals{padding:4px 16px 4px;}
.signal-row{font-size:13px;color:#333;padding:3px 0;line-height:1.5;
  border-bottom:1px solid #f5f5f5;}
.signal-row:last-child{border:none;}
.thesis-box{margin:6px 16px 8px;padding:10px 14px;background:#f8f8f8;
  border-radius:8px;font-size:12px;color:#555;line-height:1.6;border-left:3px solid #ddd;}
.verdict-box{margin:8px 16px 12px;padding:12px 16px;border-radius:8px;border-left:4px solid;}
.verdict-label{font-size:16px;font-weight:700;margin-bottom:3px;}
.verdict-score{font-size:12px;margin-bottom:5px;opacity:.8;}
.verdict-note{font-size:13px;font-weight:600;margin-bottom:8px;}
.reason-row{font-size:12px;padding:2px 0;color:#444;line-height:1.6;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.6;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 8px;}
.summary-stat .num{font-size:22px;font-weight:700;}
.summary-stat .desc{font-size:10px;color:#888;}
/* Altseason banner */
.altseason-box{margin:16px 22px 0;border-radius:10px;overflow:hidden;}
.alt-header{padding:14px 16px 10px;color:#fff;}
.alt-header h2{margin:0 0 4px;font-size:15px;font-weight:700;}
.alt-header p{margin:0;font-size:12px;opacity:.85;}
.alt-body{background:#fff;border:1px solid #e0e0e0;border-top:none;
  border-radius:0 0 10px 10px;padding:12px 16px;}
.alt-row{display:flex;justify-content:space-between;padding:6px 0;
  border-bottom:1px solid #f0f0f0;font-size:13px;}
.alt-row:last-child{border:none;}
.alt-lbl{color:#888;font-size:12px;}
.alt-val{font-weight:600;}
.history-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px;}
.history-table th{background:#f5f5f5;padding:6px 10px;text-align:left;
  font-weight:600;color:#555;border-bottom:1px solid #eee;}
.history-table td{padding:6px 10px;border-bottom:1px solid #f5f5f5;color:#444;}
/* Top picks */
.top-picks{background:linear-gradient(135deg,#0A5D3E,#1D9E75);
  margin:16px 22px 0;padding:16px 18px;border-radius:10px;color:#fff;}
.top-picks h2{margin:0 0 4px;font-size:15px;font-weight:700;}
.top-picks p{margin:0 0 12px;font-size:12px;opacity:.85;}
.pick-row{display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.2);}
.pick-row:last-child{border:none;padding-bottom:0;}
.pick-name{font-size:14px;font-weight:700;}
.pick-detail{font-size:11px;opacity:.85;margin-top:1px;}
.pick-badge{font-size:12px;background:rgba(255,255,255,0.25);
  padding:3px 10px;border-radius:10px;font-weight:700;}
</style>
"""

TIER_COLORS = {"S": ("#1a237e","#e8eaf6"), "A": ("#1b5e20","#e8f5e9"),
               "B": ("#e65100","#fff3e0"), "C": ("#880e4f","#fce4ec")}

def tier_pill(tier):
    bg_dark, bg_light = TIER_COLORS.get(tier, ("#555","#eee"))
    labels = {"S":"S — Blue Chip","A":"A — Strong","B":"B — Solid","C":"C — Speculative"}
    return f'<span class="pill" style="background:{bg_light};color:{bg_dark};">{labels.get(tier,tier)}</span>'

def signal_pill(count):
    if count >= 3:   bg,col = "#D4F5E9","#0A5D3E"
    elif count == 2: bg,col = "#FEF3DC","#7A4900"
    else:            bg,col = "#F0F0F0","#444"
    return f'<span class="pill" style="background:{bg};color:{col};">{count}/3 whale signals</span>'

def price_bar_html(price, low, high):
    if not all([price, low, high]) or high == low: return ""
    pct   = max(0, min(100, (price - low) / (high - low) * 100))
    color = "#1D9E75" if pct < 35 else "#EF9F27" if pct < 65 else "#E24B4A"
    return (f'<div style="font-size:10px;color:#bbb;margin-bottom:3px;">24h range position — {pct:.0f}% from low</div>'
            f'<div style="background:#eee;border-radius:3px;height:5px;">'
            f'<div style="background:{color};width:{pct:.0f}%;height:5px;border-radius:3px;"></div></div>')

def build_altseason_banner():
    ac = ALTSEASON_CONTEXT
    index_color = "#0A5D3E" if ac["index"] >= 75 else "#EF9F27" if ac["index"] >= 50 else "#E24B4A"
    btcd_color  = "#E24B4A" if ac["btc_dominance"] >= 55 else "#EF9F27" if ac["btc_dominance"] >= 50 else "#0A5D3E"
    header_bg   = "#1a237e" if ac["index"] < 50 else "#0A5D3E"

    history_rows = ""
    for cycle, data in ac["historical_pattern"].items():
        label = {"2017":"2017 Cycle","2021":"2021 Wave 1","2021b":"2021 Wave 2","2026e":"2026 Estimate"}.get(cycle, cycle)
        history_rows += f"""<tr>
      <td><strong>{label}</strong></td>
      <td style="color:#0A5D3E;">{data['enter']}</td>
      <td style="color:#E24B4A;">{data['exit']}</td>
      <td>{data['duration']}</td>
    </tr>"""

    return f"""<div class="altseason-box">
  <div class="alt-header" style="background:{header_bg};">
    <h2>📊 Altseason Status — {ac['phase']}</h2>
    <p>Use this to time WHEN to buy and when to exit. Updated each run.</p>
  </div>
  <div class="alt-body">
    <div class="alt-row">
      <span class="alt-lbl">Altseason Index (need 75+ to confirm)</span>
      <span class="alt-val" style="color:{index_color};">{ac['index']}/100 — {ac['status']}</span>
    </div>
    <div class="alt-row">
      <span class="alt-lbl">BTC Dominance (need &lt;54% for altseason)</span>
      <span class="alt-val" style="color:{btcd_color};">{ac['btc_dominance']}% — {"Too High ⚠️" if ac['btc_dominance'] >= 55 else "Getting Better" if ac['btc_dominance'] >= 50 else "Altcoin Friendly ✅"}</span>
    </div>
    <div class="alt-row">
      <span class="alt-lbl">Estimated Entry Window</span>
      <span class="alt-val">{ac['enter_window']}</span>
    </div>
    <div class="alt-row">
      <span class="alt-lbl">Exit Signal to Watch</span>
      <span class="alt-val">{ac['exit_window']}</span>
    </div>
    <div class="alt-row">
      <span class="alt-lbl">Key Trigger</span>
      <span class="alt-val">{ac['key_trigger']}</span>
    </div>
    <div style="background:#fff8e1;padding:10px 12px;border-radius:6px;
      margin-top:10px;font-size:12px;color:#7A4900;border-left:3px solid #EF9F27;">
      ⚠️ <strong>Current Warning:</strong> {ac['warning']}
    </div>
    <div style="margin-top:12px;">
      <div style="font-size:11px;font-weight:700;color:#666;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">Historical Altseason Windows</div>
      <table class="history-table">
        <thead><tr><th>Cycle</th><th>🟢 Enter</th><th>🔴 Exit</th><th>Duration</th></tr></thead>
        <tbody>{history_rows}</tbody>
      </table>
    </div>
    <div style="margin-top:10px;font-size:12px;color:#555;line-height:1.6;">
      <strong>Strategy for now:</strong> We are in Bitcoin Season. Use whale alerts to accumulate
      Tier S and A coins at low prices. <strong>Do NOT chase pumps right now.</strong>
      When BTC.D drops below 54% and stays there, that's your green light to go heavy on altcoins.
      Set a calendar reminder to check BTC dominance weekly on
      <a href="https://www.blockchaincenter.net/altcoin-season-index/" style="color:#4a148c;">BlockchainCenter</a>.
    </div>
  </div>
</div>"""


def build_top_picks_banner(strong_buys):
    if not strong_buys: return ""
    rows = ""
    for a in strong_buys[:5]:
        change_sign = "+" if a["price_change"] >= 0 else ""
        tier_label  = {"S":"🏆 Blue Chip","A":"⭐ Strong","B":"📌 Solid","C":"🎲 Speculative"}.get(a["tier"],"")
        rows += f"""<div class="pick-row">
    <div>
      <div class="pick-name">{a['name']} ({a['pair']})</div>
      <div class="pick-detail">${a['price']:.6f} · {change_sign}{a['price_change']:.2%} · {tier_label}</div>
    </div>
    <div class="pick-badge">{a['conviction_score']}/100</div>
  </div>"""
    return f"""<div class="top-picks">
  <h2>🟢 Strong Buy Picks — {len(strong_buys)} Quality Coin{'s' if len(strong_buys)>1 else ''}</h2>
  <p>Curated coins with whale activity AND early-entry conditions. Full analysis below.</p>
  {rows}
</div>"""


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
                        f'{change_sign}{a["price_change"]:.2%} in recent candles</div>')
    for w in a["ob_whales"]:
        signal_rows += (f'<div class="signal-row">🐋 <strong>{w["side"]}</strong> — '
                        f'${w["usd_value"]:,.0f} order @ ${w["price"]:.6f}</div>')

    reasons_html = "".join(f'<div class="reason-row">• {r}</div>' for r in a["conv_reasons"])
    pbar = price_bar_html(a["price"], a["low_24h"], a["high_24h"])
    tier_dark, _ = TIER_COLORS.get(a["tier"], ("#555","#eee"))

    return f"""<div class="stock-card">
  <div class="card-top">
    <div>
      <div class="sym">{a['name']}</div>
      <div class="coin-name">{a['pair']} · Kraken</div>
      <div style="margin-top:5px;">{tier_pill(a['tier'])} &nbsp; {signal_pill(a['signal_count'])}</div>
    </div>
    <div style="text-align:right;">
      <div class="price">${a['price']:.6f}</div>
      <div style="font-size:11px;color:{change_color};margin-top:2px;font-weight:600;">
        {change_sign}{a['price_change']:.2%} recent move
      </div>
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
  <div class="thesis-box">
    <strong style="color:{tier_dark};">Investment Thesis:</strong> {a['thesis']}
  </div>
  <div class="verdict-box" style="background:{a['verdict_bg']};border-left-color:{a['verdict_color']};">
    <div class="verdict-label" style="color:{a['verdict_color']};">{a['verdict']}</div>
    <div class="verdict-score" style="color:{a['verdict_color']};">Conviction score: <strong>{a['conviction_score']}/100</strong></div>
    <div class="verdict-note" style="color:{a['verdict_color']};">{a['verdict_note']}</div>
    {reasons_html}
  </div>
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
  <h1>🐋 Phase 3 · Whale Alert + Buy Advisor</h1>
  <p>{date_str} · Curated Kraken Quality Coins Only</p>
</div>
<div class="body">
  <div style="display:flex;justify-content:space-around;padding:16px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat"><div class="num" style="color:#4a148c;">{len(alerts)}</div><div class="desc">Coins flagged</div></div>
    <div class="summary-stat"><div class="num" style="color:#0F6E56;">{len(strong_buys)}</div><div class="desc">🟢 Strong Buy</div></div>
    <div class="summary-stat"><div class="num" style="color:#EF9F27;">{len(watches)}</div><div class="desc">🟡 Watch</div></div>
    <div class="summary-stat"><div class="num" style="color:#E24B4A;">{len(skips)}</div><div class="desc">🔴 Skip</div></div>
    <div class="summary-stat"><div class="num" style="color:#1a237e;">{ALTSEASON_CONTEXT['index']}</div><div class="desc">Alt Index</div></div>
  </div>
  {build_altseason_banner()}
  {build_top_picks_banner(strong_buys)}
  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      Only <strong>fundamentally sound Kraken altcoins</strong> under $2 are tracked.
      Each card includes the investment thesis, whale signals, and a 0–100 conviction score
      based on entry position, whale order direction, volume, momentum, and candle structure.<br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Always do your own research.</strong>
    </p>
  </div>"""

    if strong_buys:
        html += '<div class="section"><div class="section-head">🟢 Strong Buy — Quality Coins, Early Entry</div>'
        for a in strong_buys: html += build_coin_card(a)
        html += '</div><div class="divider"></div>'

    if watches:
        html += '<div class="section"><div class="section-head">🟡 Watch — Wait for Confirmation</div>'
        for a in watches: html += build_coin_card(a)
        html += '</div><div class="divider"></div>'

    if skips:
        html += '<div class="section"><div class="section-head">🔴 Skip — Mid-Wave, Risky, or Distributing</div>'
        for a in skips: html += build_coin_card(a)
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Kraken Whale Tracker + Buy Advisor (Phase 3) · Curated quality coins only · Runs every 15 min<br>
    Whale signals: 🔥 Volume spike · 📈 Momentum · 🐋 Order wall ($20k+)<br>
    Tiers: S=Blue Chip · A=Strong · B=Solid · C=Speculative<br>
    Research and education only — not financial advice.<br>
    <a href="https://www.kraken.com/trade" style="color:#7c4dff;">Open Kraken →</a> &nbsp;·&nbsp;
    <a href="https://www.blockchaincenter.net/altcoin-season-index/" style="color:#7c4dff;">Altseason Index →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(alerts):
    now   = datetime.now(timezone.utc)
    ac    = ALTSEASON_CONTEXT
    lines = [
        "=" * 65,
        f" KRAKEN WHALE ALERT + BUY ADVISOR (Phase 3) — Curated Coins",
        f" {now.strftime('%Y-%m-%d %H:%M UTC')} — {len(alerts)} alert(s)",
        "=" * 65,
        f"\n📊 ALTSEASON STATUS: {ac['phase']} ({ac['status']})",
        f"   Index: {ac['index']}/100 (need 75+ for altseason)",
        f"   BTC Dominance: {ac['btc_dominance']}% (need <54% for altseason)",
        f"   Estimated entry: {ac['enter_window']}",
        f"   ⚠️  {ac['warning']}",
    ]
    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    if strong_buys:
        lines.append("\n🟢 STRONG BUY — Enter these now:")
        for a in strong_buys:
            lines.append(f"  ► {a['name']:<25} ({a['pair']}) Tier {a['tier']} · ${a['price']:.6f} · conviction {a['conviction_score']}/100")
    lines.append("\n── FULL DETAILS ─────────────────────────────────────────────")
    for a in alerts:
        lines.append(f"\n  {a['name']} ({a['pair']}) — Tier {a['tier']}")
        lines.append(f"  ${a['price']:.6f}  ({a['price_change']:+.2%})  Vol: ${a['volume_usd']:,.0f}")
        lines.append(f"  {a['verdict']}  (conviction {a['conviction_score']}/100) — {a['verdict_note']}")
        for r in a["conv_reasons"]: lines.append(f"    • {r}")
    lines += ["", "=" * 65, " Research only. Not financial advice.", "=" * 65]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# SEND EMAIL & MAIN
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
    print(f"✅ Alert sent → {EMAIL_RECIPIENT}")


def run():
    now = datetime.now(timezone.utc)
    print(f"🐋 Kraken Whale Tracker + Buy Advisor (Phase 3) — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    alerts = scan_for_whales()

    if not alerts:
        print("  No whale activity on curated coins this run. No email sent.")
        return

    html_body   = build_html_email(alerts)
    text_body   = build_text_email(alerts)
    strong_buys = [a for a in alerts if a["verdict"] == "🟢 STRONG BUY"]
    buy_tag     = f" · BUY: {', '.join(a['name'] for a in strong_buys[:3])}" if strong_buys else ""
    subject     = (f"🐋 Whale Alert: {len(alerts)} Quality Coins · "
                   f"{len(strong_buys)} Strong Buy{buy_tag} · {now.strftime('%H:%M UTC')}")

    print(text_body)
    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
