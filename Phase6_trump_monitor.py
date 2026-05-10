# ============================================================
# TRADING BOT — PHASE 6 (Trump Market Monitor)
#
# Donald Trump is the most market-moving person on the planet.
# One post on Truth Social can move a stock 20-40% in minutes.
# This phase catches those moments and emails you INSTANTLY.
#
# ── WHAT IT MONITORS ────────────────────────────────────────
#
#   SOURCE 1 — CNN Truth Social Archive (ix.cnn.io)
#     CNN maintains a live JSON archive of every Trump Truth
#     Social post, updated every 5 minutes. Public, no key.
#     This is the fastest reliable source available.
#
#   SOURCE 2 — trumpstruth.org RSS Feed
#     Independent archive with an RSS feed. Acts as backup
#     if CNN's archive is slow or down.
#
#   SOURCE 3 — Google News RSS (Trump + stock/market)
#     Catches mainstream media stories about Trump mentioning
#     specific companies — tariffs, deals, endorsements etc.
#     Google News RSS is free, no key, works from any server.
#
# ── WHAT TRIGGERS AN EMAIL ──────────────────────────────────
#
#   The script scans every post/article for:
#     • Company names (Apple, Tesla, Nvidia etc.)
#     • Stock ticker symbols ($AAPL, $TSLA etc.)
#     • Market-moving keywords (tariff, deal, ban, buy etc.)
#     • Sector mentions (AI, oil, defence, pharma etc.)
#
#   Email fires ONLY when a post contains something
#   that could move a stock. Pure political posts = ignored.
#
# ── THE "TRUMP EFFECT" — HOW TO USE THIS ────────────────────
#
#   When Trump mentions a company positively:
#     → Stock often spikes 5-40% within minutes of the post
#     → Buy within the first 30-60 minutes for best gains
#     → Set a stop loss at -5% immediately after buying
#     → Take profit at +15-25% or when the news cycle moves on
#     → Hold no longer than 1-3 days for Trump-pump trades
#
#   When Trump attacks a company (tariffs, boycotts):
#     → Stock often drops 5-20% immediately
#     → Do NOT buy the dip immediately — let it stabilize
#     → Wait 2-3 days, then consider buying if fundamentals good
#
#   When Trump mentions a SECTOR (AI, oil, defence):
#     → ETFs and sector leaders move together
#     → Broader play, lower risk than single stock
#
# ── TIMING ──────────────────────────────────────────────────
#   Runs every 5 minutes via GitHub Actions.
#   De-duplicates: you will NOT get the same post twice.
#   No email = nothing market-moving detected. Go live your life.
#
# SECRETS (GitHub → Settings → Secrets → Actions):
#   EMAIL_SENDER    — your Gmail address
#   EMAIL_PASSWORD  — Gmail App Password (16 chars)
#   EMAIL_RECIPIENT — where to receive alerts
# ============================================================

import os
import re
import json
import hashlib
import smtplib
import requests
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from xml.etree import ElementTree as ET

# ── SECRETS ──────────────────────────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")

SEEN_FILE = "/tmp/phase6_seen_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TradingBot/6.0; research)",
    "Accept":     "application/json, text/html, application/xml, */*",
}

# ══════════════════════════════════════════════════════════════
# STOCK & COMPANY KNOWLEDGE BASE
#
# Maps company names and keywords → ticker symbols.
# When Trump mentions any of these, the bot fires an alert.
#
# Format:
#   "keyword to detect in post": ("TICKER", "Full Company Name",
#                                  "why this matters", sentiment_bias)
#
# sentiment_bias:
#   "positive"  — Trump praise usually pumps this stock
#   "negative"  — Trump attacking this usually dumps it
#   "neutral"   — could go either way depending on context
#   "sector"    — broad sector mention, multiple stocks move
# ══════════════════════════════════════════════════════════════

COMPANY_MAP = {

    # ── Big Tech ──────────────────────────────────────────────
    "apple":       ("AAPL",  "Apple Inc.",           "World's most valuable company. Trump/China tariff tensions directly impact Apple's supply chain.", "neutral"),
    "iphone":      ("AAPL",  "Apple Inc.",           "iPhone = Apple. Any tariff or trade deal news hits AAPL immediately.", "neutral"),
    "microsoft":   ("MSFT",  "Microsoft",            "Azure cloud + OpenAI. Trump AI policy directly affects MSFT.", "positive"),
    "google":      ("GOOGL", "Alphabet (Google)",    "Antitrust and AI regulation. Trump DOJ stance matters enormously.", "neutral"),
    "alphabet":    ("GOOGL", "Alphabet (Google)",    "Same as Google.", "neutral"),
    "meta":        ("META",  "Meta Platforms",       "Facebook/Instagram. Trump was banned from both. Relations are complex.", "neutral"),
    "facebook":    ("META",  "Meta Platforms",       "Same as Meta.", "neutral"),
    "amazon":      ("AMZN",  "Amazon",               "AWS cloud, retail dominance. Trump has historically attacked Amazon/Bezos.", "negative"),
    "bezos":       ("AMZN",  "Amazon",               "Jeff Bezos = Amazon. Trump-Bezos relationship directly affects AMZN.", "neutral"),
    "tesla":       ("TSLA",  "Tesla",                "Elon Musk is Trump's ally. Tesla benefits enormously from positive Trump/Musk news.", "positive"),
    "elon":        ("TSLA",  "Tesla",                "Elon Musk owns Tesla, SpaceX, X. Trump mentions = TSLA moves.", "positive"),
    "musk":        ("TSLA",  "Tesla",                "Elon Musk. TSLA, DOGE, SpaceX all move on Trump-Musk news.", "positive"),
    "nvidia":      ("NVDA",  "Nvidia",               "AI chip king. Export controls, China chip bans — Trump controls these directly.", "neutral"),
    "nvidia chip": ("NVDA",  "Nvidia",               "Chip export ban/allow to China. Trump's single most impactful lever on NVDA.", "neutral"),
    "openai":      ("MSFT",  "Microsoft (OpenAI)",   "Microsoft owns OpenAI stake. AI regulation from Trump = MSFT impact.", "positive"),

    # ── Media & Trump-Related ─────────────────────────────────
    "truth social":("DJT",   "Trump Media & Technology", "Trump's own company. Any mention by Trump = DJT moves violently.", "positive"),
    "trump media": ("DJT",   "Trump Media & Technology", "Same as Truth Social. DJT is Trump's personal brand stock.", "positive"),
    "fox":         ("FOX",   "Fox Corporation",      "Trump's preferred media outlet. Fox news + Trump = high correlation.", "positive"),
    "fox news":    ("FOX",   "Fox Corporation",      "Same as Fox.", "positive"),
    "nbc":         ("CMCSA", "Comcast (NBC)",         "Trump often attacks NBC/Comcast as fake news. Can drop on attacks.", "negative"),
    "cnn":         ("WBD",   "Warner Bros Discovery","Trump attacks CNN constantly. Owned by Warner Bros Discovery.", "negative"),
    "disney":      ("DIS",   "Disney",               "Trump has clashed with Disney over political content. Watch for attacks.", "negative"),
    "netflix":     ("NFLX",  "Netflix",              "Streaming wars + content regulation. Trump mentions = NFLX moves.", "neutral"),

    # ── Finance & Crypto ─────────────────────────────────────
    "bitcoin":     ("MSTR",  "MicroStrategy + BTC",  "Trump is pro-crypto. Any BTC mention from Trump pumps the whole crypto market.", "positive"),
    "crypto":      ("COIN",  "Coinbase",             "Trump pro-crypto stance. Regulatory clarity = COIN pumps.", "positive"),
    "coinbase":    ("COIN",  "Coinbase",             "Largest US crypto exchange. Direct beneficiary of Trump crypto policy.", "positive"),
    "gold":        ("GLD",   "SPDR Gold ETF",        "Safe haven. Trump uncertainty = gold up.", "positive"),
    "federal reserve":("JPM","JPMorgan + Banks",     "Fed policy = bank stocks move. Trump vs Fed is a major market driver.", "neutral"),
    "interest rate":("JPM",  "JPMorgan + Banks",     "Rate commentary from Trump moves entire financial sector.", "neutral"),
    "jpmorgan":    ("JPM",   "JPMorgan Chase",       "Largest US bank. Jamie Dimon relationship with Trump matters.", "neutral"),
    "goldman":     ("GS",    "Goldman Sachs",        "Investment banking giant. Trump admin = Goldman alumni everywhere.", "positive"),
    "blackrock":   ("BLK",   "BlackRock",            "World's largest asset manager. Trump mentions = BLK moves.", "neutral"),

    # ── Energy & Oil ─────────────────────────────────────────
    "oil":         ("XOM",   "ExxonMobil + Sector",  "'Drill baby drill' = oil stocks pump. Trump loves domestic energy production.", "positive"),
    "drill":       ("XOM",   "ExxonMobil",           "Trump's signature energy phrase. DRILL = oil stocks go up immediately.", "positive"),
    "exxon":       ("XOM",   "ExxonMobil",           "Largest US oil company. Trump pro-oil policy benefits XOM directly.", "positive"),
    "chevron":     ("CVX",   "Chevron",              "Major US oil company. Same as Exxon on Trump energy policy.", "positive"),
    "lng":         ("LNG",   "Cheniere Energy",      "Liquefied natural gas exports. Trump pushes LNG — direct LNG beneficiary.", "positive"),
    "natural gas":("LNG",   "Cheniere Energy",       "Same as LNG above.", "positive"),
    "solar":       ("FSLR",  "First Solar",          "US-made solar. Trump tariffs protect domestic solar from China competition.", "positive"),
    "nuclear":     ("CEG",   "Constellation Energy", "Nuclear power for AI data centres. Trump pro-nuclear = CEG pumps.", "positive"),
    "coal":        ("ARCH",  "Arch Resources (Coal)","Trump is pro-coal. Any coal mention = coal stocks spike.", "positive"),

    # ── Defence & Aerospace ───────────────────────────────────
    "lockheed":    ("LMT",   "Lockheed Martin",      "F-35 maker. Trump defence spending and contract news moves LMT.", "positive"),
    "raytheon":    ("RTX",   "Raytheon Technologies","Missiles, Patriot systems. Ukraine/NATO/Middle East spending = RTX up.", "positive"),
    "boeing":      ("BA",    "Boeing",               "Planes + defence. Trump often criticises Boeing pricing on AF One etc.", "neutral"),
    "northrop":    ("NOC",   "Northrop Grumman",     "B-21 bomber, drones. Defence budget = NOC.", "positive"),
    "ukraine":     ("RTX",   "Raytheon",             "Ukraine war aid = defence stocks. Trump ceasefire = defence stocks drop.", "negative"),
    "nato":        ("LMT",   "Lockheed Martin",      "NATO spending commitments = defence stocks move with every Trump statement.", "positive"),
    "military":    ("LMT",   "Lockheed Martin",      "Defence sector umbrella. Trump military spending = sector-wide move.", "positive"),
    "space force": ("LMT",   "Lockheed Martin",      "Space Force = Lockheed and Northrop get contracts.", "positive"),
    "spacex":      ("RKLB",  "Rocket Lab",           "SpaceX competitor. Musk's SpaceX = government contracts, affects RKLB.", "neutral"),

    # ── Pharma & Healthcare ───────────────────────────────────
    "pharma":      ("LLY",   "Eli Lilly + Sector",   "Drug pricing is a Trump battleground. Price caps = pharma drops.", "negative"),
    "drug":        ("PFE",   "Pfizer",               "Drug prices, patents. Trump drug pricing policy = entire pharma sector moves.", "negative"),
    "eli lilly":   ("LLY",   "Eli Lilly",            "Ozempic maker. Weight loss drugs + Medicare negotiation = LLY moves.", "negative"),
    "medicare":    ("UNH",   "UnitedHealth Group",   "Health insurance giant. Medicare policy = UNH moves significantly.", "negative"),
    "fda":         ("MRNA",  "Moderna",              "FDA regulation. Trump FDA head = drug approval/rejection speed changes.", "neutral"),
    "vaccine":     ("MRNA",  "Moderna",              "Moderna, Pfizer COVID vaccines. RFK Jr + Trump vaccine stance = MRNA drops.", "negative"),
    "rfk":         ("MRNA",  "Moderna",              "RFK Jr is Trump's HHS head. Anti-vax = MRNA, PFE, vaccine stocks drop.", "negative"),

    # ── Retail & Consumer ────────────────────────────────────
    "walmart":     ("WMT",   "Walmart",              "World's largest retailer. Tariffs hit Walmart's China-sourced products hard.", "negative"),
    "amazon prime":("AMZN",  "Amazon",               "Amazon Prime = AMZN. Tariffs increase costs.", "negative"),
    "tariff":      ("WMT",   "Retail Sector",        "TARIFFS are Trump's biggest market mover. Retail, consumer goods, tech all react.", "negative"),
    "trade war":   ("WMT",   "Retail + Tech Sector", "Trade war = broad market selloff. China trade = massive cross-sector impact.", "negative"),
    "china":       ("NVDA",  "Nvidia + Tech Sector", "China trade relations = Nvidia export controls, Apple supply chain, Tesla sales.", "negative"),
    "tariffs":     ("WMT",   "Retail Sector",        "Same as tariff.", "negative"),

    # ── Autos & EV ───────────────────────────────────────────
    "ford":        ("F",     "Ford Motor",           "Ford EVs and tariffs. Canadian/Mexican tariffs hurt Ford production.", "negative"),
    "gm":          ("GM",    "General Motors",       "GM makes cars in Mexico. Trump tariffs = GM production cost spike.", "negative"),
    "general motors":("GM",  "General Motors",       "Same as GM.", "negative"),
    "electric vehicle":("TSLA","Tesla + EV Sector",  "EV policy — subsidies, mandates. Trump anti-EV policy hurts sector except TSLA.", "neutral"),
    "ev":          ("RIVN",  "Rivian + EV Sector",   "EV subsidies and mandates. Trump ends EV mandates = Rivian, Lucid drop.", "negative"),
    "rivian":      ("RIVN",  "Rivian",               "EV truck maker. Amazon partnership. Subsidy changes hit RIVN.", "negative"),

    # ── Real Estate & Infrastructure ─────────────────────────
    "real estate": ("VNQ",   "Vanguard Real Estate ETF","Interest rates + zoning. Trump real estate background = sector mentions.", "positive"),
    "infrastructure":("CAT", "Caterpillar",          "Infrastructure spending = CAT, heavy equipment, construction stocks.", "positive"),
    "caterpillar": ("CAT",   "Caterpillar",          "Trump loves big infrastructure. CAT is the pick-and-shovel play.", "positive"),
    "steel":       ("X",     "US Steel",             "Trump protects US steel with tariffs. Any steel mention = X, NUE move.", "positive"),
    "us steel":    ("X",     "US Steel",             "Trump personally involved in US Steel/Nippon Steel deal.", "positive"),

    # ── AI & Semiconductors ───────────────────────────────────
    "artificial intelligence":("NVDA","Nvidia",      "AI = Nvidia chips. Trump AI policy, export controls = NVDA move.", "positive"),
    "ai":          ("NVDA",  "Nvidia + AI Sector",   "AI sector umbrella. Trump AI executive orders move entire AI sector.", "positive"),
    "semiconductor":("NVDA", "Nvidia + Semis",       "Chip Act, export controls, TSMC. Trump semiconductor policy = sector move.", "neutral"),
    "chip":        ("NVDA",  "Nvidia + AMD",         "Chip bans, tariffs, TSMC. Trump chip policy is enormously market-moving.", "neutral"),
    "taiwan":      ("TSM",   "TSMC",                 "Taiwan = TSMC. China-Taiwan tensions = chip stocks move violently.", "negative"),

    # ── Canada/Trade specific (relevant to your TFSA) ─────────
    "canada":      ("ENB",   "Enbridge + Canadian Stocks","Trump-Canada trade = direct TFSA impact. Tariffs, pipelines, energy.", "negative"),
    "pipeline":    ("ENB",   "Enbridge",             "Trump loves pipelines. Keystone XL, Line 5. ENB benefits directly.", "positive"),
    "shopify":     ("SHOP",  "Shopify",              "Canadian e-commerce. US tariffs affect Shopify merchants directly.", "negative"),

    # ── Specific Market Signals ───────────────────────────────
    "stock market":("SPY",   "S&P 500 (SPY)",        "Trump commenting on the stock market = broad market move. Watch SPY.", "positive"),
    "dow jones":   ("DIA",   "Dow Jones ETF",        "Dow mention from Trump = market-wide signal.", "positive"),
    "recession":   ("GLD",   "Gold + Safe Havens",   "Recession talk = gold up, stocks down. Defensive positioning.", "negative"),
    "inflation":   ("GLD",   "Gold",                 "Inflation = gold up, tech/growth stocks down.", "negative"),
    "rate cut":    ("JPM",   "Banks + Growth Stocks","Rate cut = bank stocks up, tech stocks up, gold up.", "positive"),
    "deal":        ("SPY",   "Broad Market",         "Trump loves deals. Trade deal = market-wide pump.", "positive"),
    "great deal":  ("SPY",   "Broad Market",         "'Great deal' from Trump = expect a market rally.", "positive"),
    "sanction":    ("XOM",   "Energy + Defence",     "Sanctions on oil producers = energy prices up, defence up.", "positive"),
    "ban":         ("NVDA",  "Tech + Target Company","Banning a product/company = that stock drops immediately.", "negative"),
}

# ── Keywords that indicate market relevance (secondary filter)
MARKET_KEYWORDS = {
    # Direct financial
    "stock", "stocks", "market", "wall street", "nasdaq", "nyse",
    "invest", "trillion", "billion", "million", "economy", "gdp",
    "tariff", "tariffs", "trade", "sanction", "ban", "deal", "agreement",
    # Sectors
    "oil", "energy", "tech", "technology", "crypto", "bitcoin",
    "defence", "defense", "pharma", "drug", "chip", "semiconductor",
    "ai", "artificial intelligence", "bank", "finance", "steel",
    "coal", "solar", "nuclear", "pipeline", "ev", "electric",
    # Actions
    "buy", "sell", "build", "manufacture", "produce", "export", "import",
    "tax", "subsidy", "regulate", "approve", "reject", "announce",
    # People/places with market impact
    "china", "russia", "iran", "taiwan", "opec", "fed", "powell",
    "elon", "musk", "bezos", "gates", "buffett", "dimon",
}

# Ticker pattern — catches $AAPL, $TSLA etc. in posts
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')

# ── KNOWN TICKERS SET (for fast lookup from ticker pattern)
KNOWN_TICKERS = {
    "AAPL","MSFT","GOOGL","GOOG","META","AMZN","TSLA","NVDA","NFLX",
    "COIN","MSTR","DJT","FOX","FOXA","WBD","DIS","CMCSA","JPM","GS",
    "BAC","WFC","BLK","XOM","CVX","COP","LNG","FSLR","NEE","CEG",
    "LMT","RTX","NOC","GD","BA","KTOS","F","GM","RIVN","LCID",
    "LLY","PFE","MRK","MRNA","ABBV","JNJ","UNH","CAT","X","NUE",
    "WMT","TGT","COST","NKE","SBUX","SPY","GLD","DIA","VNQ",
    "SHOP","ENB","RY","TD","SU","ARCH","RKLB","AMD","INTC","TSM",
    "MARA","RIOT","HOOD","SOFI","PYPL","SQ","V","MA","AXP","SCHW",
}


# ══════════════════════════════════════════════════════════════
# DEDUPLICATION
# ══════════════════════════════════════════════════════════════

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen_set):
    try:
        entries = list(seen_set)[-3000:]
        with open(SEEN_FILE, "w") as f:
            json.dump(entries, f)
    except Exception:
        pass


def post_hash(post_id, source):
    return hashlib.md5(f"{source}:{post_id}".encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
# SOURCE 1 — CNN Truth Social Archive
# Updated every 5 minutes. Public JSON. No auth needed.
# This is the fastest available source.
# ══════════════════════════════════════════════════════════════

def fetch_cnn_truth_archive(hours_back=1):
    """
    Fetches Trump's Truth Social posts from CNN's live archive.
    URL: https://ix.cnn.io/data/truth-social/truth_archive.json
    Updated every 5 minutes by CNN's scraper.
    Returns list of post dicts.
    """
    posts = []
    try:
        url = "https://ix.cnn.io/data/truth-social/truth_archive.json"
        r   = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"  CNN archive HTTP {r.status_code}")
            return []

        data    = r.json()
        cutoff  = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        # Data is a list sorted newest first
        all_posts = data if isinstance(data, list) else data.get("posts", data.get("items", []))

        for item in all_posts[:200]:  # only check recent 200
            try:
                post_id    = str(item.get("id", ""))
                content    = item.get("content", item.get("text", ""))
                created_at = item.get("created_at", item.get("date", ""))

                # Strip HTML tags from content
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()

                if not content or len(content) < 10:
                    continue

                # Parse date
                try:
                    post_time = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except Exception:
                    post_time = datetime.now(timezone.utc) - timedelta(hours=2)

                if post_time < cutoff:
                    break  # sorted newest first, stop when we go past cutoff

                posts.append({
                    "id":       post_id,
                    "content":  content,
                    "time":     post_time,
                    "url":      item.get("url", f"https://truthsocial.com/@realDonaldTrump/{post_id}"),
                    "source":   "Truth Social (CNN Archive)",
                    "reposts":  item.get("reblogs_count", 0),
                    "likes":    item.get("favourites_count", 0),
                })

            except Exception:
                pass

        print(f"  CNN Truth Archive: {len(posts)} posts in last {hours_back}h")

    except Exception as e:
        print(f"  CNN Truth Archive error: {e}")

    return posts


# ══════════════════════════════════════════════════════════════
# SOURCE 2 — trumpstruth.org RSS Feed (Backup)
# Independent archive with RSS. Used as fallback if CNN is slow.
# ══════════════════════════════════════════════════════════════

def fetch_trumpstruth_rss():
    """
    Fetches from trumpstruth.org RSS feed.
    Returns list of post dicts.
    """
    posts = []
    try:
        today  = datetime.now().strftime("%Y-%m-%d")
        yest   = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        url    = f"https://www.trumpstruth.org/feed?start_date={yest}&end_date={today}"

        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  trumpstruth.org HTTP {r.status_code}")
            return []

        root  = ET.fromstring(r.content)
        items = root.findall(".//item")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

        for item in items[:50]:
            try:
                post_id  = item.findtext("guid") or item.findtext("link") or ""
                title    = item.findtext("title") or ""
                desc     = item.findtext("description") or ""
                pub_date = item.findtext("pubDate") or ""
                link     = item.findtext("link") or ""

                content = re.sub(r'<[^>]+>', ' ', desc or title)
                content = re.sub(r'\s+', ' ', content).strip()

                if not content:
                    continue

                # Parse RFC 2822 date
                try:
                    from email.utils import parsedate_to_datetime
                    post_time = parsedate_to_datetime(pub_date)
                    if post_time.tzinfo is None:
                        post_time = post_time.replace(tzinfo=timezone.utc)
                except Exception:
                    post_time = datetime.now(timezone.utc) - timedelta(hours=1)

                if post_time < cutoff:
                    continue

                posts.append({
                    "id":      post_id or content[:50],
                    "content": content,
                    "time":    post_time,
                    "url":     link,
                    "source":  "Truth Social (trumpstruth.org)",
                    "reposts": 0,
                    "likes":   0,
                })

            except Exception:
                pass

        print(f"  trumpstruth.org: {len(posts)} posts")

    except Exception as e:
        print(f"  trumpstruth.org error: {e}")

    return posts


# ══════════════════════════════════════════════════════════════
# SOURCE 3 — Google News RSS (Trump + market news)
# Free, no key, works from any server.
# Catches mainstream media reporting on Trump stock-moving news.
# ══════════════════════════════════════════════════════════════

def fetch_google_news():
    """
    Fetches Google News RSS for Trump-related market/stock news.
    Multiple queries to cover different angles.
    Returns list of article dicts.
    """
    articles = []
    queries  = [
        "Trump stock market",
        "Trump tariff stocks",
        "Trump trade deal market",
        "Trump mentions company stock",
        "Trump Truth Social market reaction",
    ]

    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)

    for query in queries:
        try:
            encoded = requests.utils.quote(query)
            url     = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            r       = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue

            root  = ET.fromstring(r.content)
            items = root.findall(".//item")

            for item in items[:10]:
                try:
                    title   = item.findtext("title") or ""
                    desc    = item.findtext("description") or ""
                    link    = item.findtext("link") or ""
                    pub     = item.findtext("pubDate") or ""
                    source  = item.findtext("source") or "Google News"

                    content = f"{title}. {re.sub(r'<[^>]+>', '', desc)}".strip()

                    if not content or "trump" not in content.lower():
                        continue

                    try:
                        from email.utils import parsedate_to_datetime
                        art_time = parsedate_to_datetime(pub)
                        if art_time.tzinfo is None:
                            art_time = art_time.replace(tzinfo=timezone.utc)
                    except Exception:
                        art_time = datetime.now(timezone.utc) - timedelta(hours=1)

                    if art_time < cutoff:
                        continue

                    articles.append({
                        "id":      link or content[:60],
                        "content": content,
                        "time":    art_time,
                        "url":     link,
                        "source":  f"Google News ({source})",
                        "reposts": 0,
                        "likes":   0,
                        "is_news": True,
                    })

                except Exception:
                    pass

            time.sleep(0.5)  # polite to Google

        except Exception as e:
            pass

    # Deduplicate articles by title
    seen_titles = set()
    unique = []
    for a in articles:
        key = a["content"][:80].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(a)

    print(f"  Google News: {len(unique)} relevant articles")
    return unique


# ══════════════════════════════════════════════════════════════
# MARKET IMPACT ANALYSER
#
# Given a post/article, determines:
#   1. Is this market-relevant at all?
#   2. Which specific stocks/tickers does it affect?
#   3. What is the likely direction (up/down/neutral)?
#   4. How urgent is this — act NOW or monitor?
#   5. Plain-English explanation of what to do
# ══════════════════════════════════════════════════════════════

def analyse_market_impact(post):
    """
    Analyses a Trump post for market-moving content.
    Returns None if not market-relevant.
    Returns a dict with full analysis if it is.
    """
    content_lower = post["content"].lower()
    content_raw   = post["content"]

    affected_stocks = {}  # ticker → {name, reason, sentiment, keyword}

    # ── Step 1: Scan for company/keyword matches ──────────────
    for keyword, (ticker, name, reason, sentiment) in COMPANY_MAP.items():
        if keyword in content_lower:
            if ticker not in affected_stocks:
                affected_stocks[ticker] = {
                    "name":      name,
                    "reason":    reason,
                    "sentiment": sentiment,
                    "keyword":   keyword,
                }

    # ── Step 2: Scan for explicit $TICKER mentions ─────────────
    ticker_matches = TICKER_PATTERN.findall(content_raw)
    for t in ticker_matches:
        if t in KNOWN_TICKERS and t not in affected_stocks:
            affected_stocks[t] = {
                "name":      t,
                "reason":    f"Trump explicitly mentioned ${t} in this post.",
                "sentiment": "positive",  # explicit mention usually positive
                "keyword":   f"${t}",
            }

    # ── Step 3: If no specific stocks, check for market keywords
    has_market_keyword = any(kw in content_lower for kw in MARKET_KEYWORDS)

    if not affected_stocks and not has_market_keyword:
        return None  # purely political — not relevant

    # If market keyword but no specific stock, flag as broad market
    if not affected_stocks and has_market_keyword:
        affected_stocks["SPY"] = {
            "name":      "S&P 500 (Broad Market)",
            "reason":    "This post contains market-relevant language that could affect the broader market.",
            "sentiment": "neutral",
            "keyword":   "market",
        }

    # ── Step 4: Determine overall sentiment ───────────────────
    positive_words = ["great", "amazing", "beautiful", "winning", "best", "love",
                      "deal", "approve", "build", "invest", "boom", "tremendous",
                      "perfect", "fantastic", "congratulations", "thank", "strong"]
    negative_words = ["bad", "terrible", "horrible", "failing", "fake", "witch hunt",
                      "ban", "sanction", "tariff", "tax", "attack", "enemy", "fraud",
                      "corrupt", "disaster", "worst", "threat", "illegal", "crooked"]

    pos_count = sum(1 for w in positive_words if w in content_lower)
    neg_count = sum(1 for w in negative_words if w in content_lower)

    if pos_count > neg_count + 1:
        overall_sentiment = "POSITIVE"
        sentiment_color   = "#0A5D3E"
        sentiment_bg      = "#D4F5E9"
        sentiment_emoji   = "📈"
    elif neg_count > pos_count + 1:
        overall_sentiment = "NEGATIVE"
        sentiment_color   = "#8a1a1a"
        sentiment_bg      = "#FDECEA"
        sentiment_emoji   = "📉"
    else:
        overall_sentiment = "MIXED / WATCH"
        sentiment_color   = "#7A4900"
        sentiment_bg      = "#FEF3DC"
        sentiment_emoji   = "👀"

    # ── Step 5: Urgency rating ────────────────────────────────
    # Explicit tickers = maximum urgency
    # CEO names / company names = high urgency
    # Sector keywords only = medium urgency
    if ticker_matches or any(k in ["elon", "musk", "bezos", "truth social", "tesla"] for k in content_lower.split()):
        urgency = "🚨 ACT NOW"
        urgency_note = "Trump directly named a company or person. These posts move stocks within MINUTES. Check the market immediately."
    elif len(affected_stocks) >= 3:
        urgency = "⚡ HIGH"
        urgency_note = "Multiple stocks affected. Broad market-moving post. Check pre-market or market open."
    elif any(v["sentiment"] in ("positive", "negative") for v in affected_stocks.values()):
        urgency = "📊 MEDIUM"
        urgency_note = "Clear directional signal on specific stocks. Monitor opening and consider entry."
    else:
        urgency = "👀 LOW"
        urgency_note = "General market language. Watch for follow-up posts before acting."

    # ── Step 6: Generate what-to-do ───────────────────────────
    action_lines = []
    for ticker, info in list(affected_stocks.items())[:5]:
        sent = info["sentiment"]
        if sent == "positive":
            action_lines.append(f"${ticker} ({info['name']}) — Consider BUYING. Hold 1-3 days max for Trump-pump trades. Set stop loss at -5%.")
        elif sent == "negative":
            action_lines.append(f"${ticker} ({info['name']}) — Expect a DROP. Do not buy immediately. Wait 2-3 days for stability before considering entry.")
        elif sent == "sector":
            action_lines.append(f"${ticker} ({info['name']}) — SECTOR MOVE expected. Multiple stocks in this sector will react together.")
        else:
            action_lines.append(f"${ticker} ({info['name']}) — Watch closely. Direction depends on further context.")

    return {
        "post":             post,
        "affected_stocks":  affected_stocks,
        "overall_sentiment":overall_sentiment,
        "sentiment_color":  sentiment_color,
        "sentiment_bg":     sentiment_bg,
        "sentiment_emoji":  sentiment_emoji,
        "pos_count":        pos_count,
        "neg_count":        neg_count,
        "urgency":          urgency,
        "urgency_note":     urgency_note,
        "action_lines":     action_lines,
        "ticker_count":     len(affected_stocks),
    }


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# Matches your Phase 1-5 visual style exactly.
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#f4f4f4;margin:0;padding:20px;color:#222;}
.wrap{max-width:680px;margin:0 auto;}
.header{background:linear-gradient(135deg,#B71C1C,#D32F2F);color:#fff;
  padding:26px 28px;border-radius:14px 14px 0 0;}
.header h1{margin:0;font-size:21px;font-weight:700;}
.header p{margin:6px 0 0;font-size:13px;opacity:.8;}
.body{background:#fff;border:1px solid #e2e2e2;border-top:none;
  border-radius:0 0 14px 14px;padding-bottom:24px;}
.section{padding:20px 22px 0;}
.section-head{font-size:12px;font-weight:700;color:#666;text-transform:uppercase;
  letter-spacing:.7px;border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:12px;}
.post-card{border:1px solid #eaeaea;border-radius:10px;margin-bottom:16px;overflow:hidden;}
.post-top{background:#fafafa;padding:14px 16px;border-bottom:1px solid #eee;}
.post-content{font-size:15px;font-weight:500;line-height:1.6;
  color:#1a1a1a;background:#fff8e1;padding:14px 16px;
  border-left:4px solid #D32F2F;margin:0;font-style:italic;}
.urgency-bar{padding:10px 16px;display:flex;align-items:center;gap:10px;
  border-bottom:1px solid #f0f0f0;}
.urgency-label{font-size:15px;font-weight:700;}
.urgency-note{font-size:12px;color:#555;}
.stock-grid{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px 4px;}
.stock-chip{border-radius:8px;padding:8px 12px;border:1px solid #eee;min-width:130px;flex:1;}
.chip-ticker{font-size:16px;font-weight:700;}
.chip-name{font-size:11px;color:#888;margin-top:1px;}
.chip-dir{font-size:12px;font-weight:600;margin-top:4px;}
.info-box{margin:8px 16px 8px;padding:12px 14px;border-radius:8px;
  font-size:13px;line-height:1.65;border-left:4px solid;}
.action-box{margin:8px 16px 12px;padding:14px 16px;border-radius:8px;border-left:4px solid;}
.action-title{font-size:14px;font-weight:700;margin-bottom:8px;}
.action-row{font-size:13px;padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06);line-height:1.6;}
.action-row:last-child{border:none;}
.meta-row{display:flex;gap:16px;padding:8px 16px 10px;flex-wrap:wrap;}
.meta-item{font-size:11px;color:#aaa;}
.meta-item strong{color:#555;}
.quicklist{margin:16px 22px 0;background:linear-gradient(135deg,#B71C1C,#D32F2F);
  border-radius:10px;padding:16px 18px;color:#fff;}
.quicklist h2{margin:0 0 4px;font-size:15px;font-weight:700;}
.quicklist p{margin:0 0 12px;font-size:12px;opacity:.85;}
.ql-row{display:flex;justify-content:space-between;align-items:center;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,.2);}
.ql-row:last-child{border:none;padding-bottom:0;}
.ql-content{font-size:13px;font-weight:600;flex:1;margin-right:10px;}
.ql-badge{font-size:12px;background:rgba(255,255,255,.25);
  padding:3px 10px;border-radius:10px;font-weight:700;white-space:nowrap;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.7;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 8px;}
.summary-stat .num{font-size:22px;font-weight:700;}
.summary-stat .desc{font-size:10px;color:#888;}
.source-tag{font-size:10px;color:#bbb;padding:4px 16px 8px;}
</style>
"""

SENTIMENT_ARROW = {"POSITIVE": "📈", "NEGATIVE": "📉", "MIXED / WATCH": "👀"}

def sentiment_chip_style(sentiment):
    styles = {
        "positive": ("background:#D4F5E9;border-color:#1D9E75;", "#0A5D3E", "📈 Likely UP"),
        "negative": ("background:#FDECEA;border-color:#E24B4A;", "#8a1a1a", "📉 Likely DOWN"),
        "sector":   ("background:#EEF4FF;border-color:#1a237e;", "#1a237e", "🔄 Sector Move"),
        "neutral":  ("background:#F5F5F5;border-color:#ccc;",    "#555",    "👀 Watch"),
    }
    return styles.get(sentiment, styles["neutral"])


def build_post_card(analysis):
    post     = analysis["post"]
    stocks   = analysis["affected_stocks"]
    urgency  = analysis["urgency"]
    is_news  = post.get("is_news", False)

    # Post content box
    source_icon = "📰" if is_news else "📣"
    time_str    = post["time"].strftime("%b %d %Y · %H:%M UTC") if hasattr(post["time"], "strftime") else ""

    # Urgency bar color
    urgency_colors = {
        "🚨 ACT NOW": ("#B71C1C", "#FFEBEE"),
        "⚡ HIGH":    ("#E65100", "#FFF3E0"),
        "📊 MEDIUM":  ("#1a237e", "#E8EAF6"),
        "👀 LOW":     ("#555",    "#F5F5F5"),
    }
    u_color, u_bg = urgency_colors.get(urgency, ("#555", "#F5F5F5"))

    # Stock chips
    chips_html = ""
    for ticker, info in list(stocks.items())[:6]:
        chip_style, chip_color, chip_dir = sentiment_chip_style(info["sentiment"])
        chips_html += f"""<div class="stock-chip" style="{chip_style}">
      <div class="chip-ticker" style="color:{chip_color};">${ticker}</div>
      <div class="chip-name">{info['name'][:30]}</div>
      <div class="chip-dir" style="color:{chip_color};">{chip_dir}</div>
    </div>"""

    # Action box
    actions_html = "".join(
        f'<div class="action-row">• {line}</div>'
        for line in analysis["action_lines"]
    )

    # Meta (likes/reposts only for Truth Social)
    meta_html = ""
    if not is_news and (post.get("likes", 0) or post.get("reposts", 0)):
        meta_html = f"""<div class="meta-row">
      <div class="meta-item">❤️ <strong>{post.get('likes',0):,}</strong> likes</div>
      <div class="meta-item">🔁 <strong>{post.get('reposts',0):,}</strong> reposts</div>
      <div class="meta-item">📅 <strong>{time_str}</strong></div>
    </div>"""
    else:
        meta_html = f'<div class="meta-row"><div class="meta-item">📅 <strong>{time_str}</strong></div></div>'

    return f"""<div class="post-card">
  <div class="post-top">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <span style="font-size:14px;font-weight:700;">{source_icon} {'Donald Trump · Truth Social' if not is_news else post['source']}</span>
        <div style="font-size:11px;color:#999;margin-top:2px;">{time_str}</div>
      </div>
      <div style="text-align:right;">
        <span style="font-size:20px;">{analysis['sentiment_emoji']}</span>
        <div style="font-size:12px;font-weight:700;color:{analysis['sentiment_color']};">{analysis['overall_sentiment']}</div>
      </div>
    </div>
  </div>

  <div class="post-content">"{post['content'][:600]}{'...' if len(post['content']) > 600 else ''}"</div>

  <div class="urgency-bar" style="background:{u_bg};">
    <div class="urgency-label" style="color:{u_color};">{urgency}</div>
    <div class="urgency-note">{analysis['urgency_note']}</div>
  </div>

  <div class="stock-grid">{chips_html}</div>

  <div class="info-box" style="background:#EEF4FF;border-left-color:#1a237e;">
    <div style="font-size:10px;font-weight:700;color:#1a237e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;">Why these stocks move</div>
    {'<br>'.join(f'<strong>${t}</strong> — {info["reason"]}' for t, info in list(stocks.items())[:4])}
  </div>

  <div class="action-box" style="background:{analysis['sentiment_bg']};border-left-color:{analysis['sentiment_color']};">
    <div class="action-title" style="color:{analysis['sentiment_color']};">💼 What to do for your TFSA</div>
    {actions_html}
    <div style="font-size:11px;color:#888;margin-top:8px;padding-top:8px;border-top:1px solid rgba(0,0,0,.08);">
      ⏱️ Trump-pump trades: hold 1-3 days max · Set stop loss at -5% immediately after buying ·
      Take profit at +15-25% · News cycle moves fast — exit before it fades
    </div>
  </div>

  {meta_html}
  <div class="source-tag">Source: <a href="{post['url']}" style="color:#B71C1C;">View original →</a></div>
</div>"""


def build_quicklist(analyses):
    if not analyses:
        return ""
    rows = ""
    for a in analyses[:5]:
        content_preview = a["post"]["content"][:80].replace('"', "'")
        tickers = " ".join(f"${t}" for t in list(a["affected_stocks"].keys())[:3])
        rows += f"""<div class="ql-row">
    <div class="ql-content">"{content_preview}..."</div>
    <div class="ql-badge">{a['urgency'].split()[0]} · {tickers}</div>
  </div>"""
    return f"""<div class="quicklist">
  <h2>⚡ Trump just posted — act fast</h2>
  <p>Market-moving posts detected. Full analysis below each card. Time is critical.</p>
  {rows}
</div>"""


def build_html_email(act_now, high, medium, low, total):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    all_analyses = act_now + high + medium + low
    top_analyses = sorted(all_analyses, key=lambda x: (
        {"🚨 ACT NOW":0,"⚡ HIGH":1,"📊 MEDIUM":2,"👀 LOW":3}.get(x["urgency"],9)
    ))

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>🇺🇸 Phase 6 · Trump Market Monitor</h1>
  <p>{date_str} · Truth Social + News · Auto-detected stock impact</p>
</div>
<div class="body">

  <div style="display:flex;justify-content:space-around;padding:16px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat"><div class="num" style="color:#B71C1C;">{len(act_now)}</div><div class="desc">🚨 Act Now</div></div>
    <div class="summary-stat"><div class="num" style="color:#E65100;">{len(high)}</div><div class="desc">⚡ High</div></div>
    <div class="summary-stat"><div class="num" style="color:#1a237e;">{len(medium)}</div><div class="desc">📊 Medium</div></div>
    <div class="summary-stat"><div class="num" style="color:#888;">{total}</div><div class="desc">Total posts scanned</div></div>
  </div>

  {build_quicklist(top_analyses[:5])}

  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      These posts were detected in the last 60-90 minutes from Trump's Truth Social and mainstream news.
      Each card shows which stocks are affected, whether the move is likely UP or DOWN,
      and exactly what to do for your TFSA.<br>
      <strong style="color:#D32F2F;">⚡ Trump-pump trades are fast. Act within 30-60 minutes of the post for best results.</strong><br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Always do your own research. Trading involves risk of loss.</strong>
    </p>
  </div>
"""

    if act_now:
        html += '<div class="section"><div class="section-head">🚨 Act Now — Check Market Immediately</div>'
        for a in act_now: html += build_post_card(a)
        html += '</div><div class="divider"></div>'

    if high:
        html += '<div class="section"><div class="section-head">⚡ High Priority — Worth Acting On</div>'
        for a in high: html += build_post_card(a)
        html += '</div><div class="divider"></div>'

    if medium:
        html += '<div class="section"><div class="section-head">📊 Medium — Monitor and Watch</div>'
        for a in medium: html += build_post_card(a)
        html += '</div><div class="divider"></div>'

    if low:
        html += '<div class="section"><div class="section-head">👀 Low — General Market Language</div>'
        for a in low[:3]: html += build_post_card(a)  # cap at 3
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Phase 6 Trump Market Monitor · Runs every 5 min via GitHub Actions<br>
    Sources: Truth Social (CNN Archive) · trumpstruth.org · Google News<br>
    Trump-pump strategy: buy within 30-60 min · hold 1-3 days · exit at +15-25% · stop loss at -5%<br>
    Research and education only — not financial advice. Trading involves risk of loss.<br>
    <a href="https://truthsocial.com/@realDonaldTrump" style="color:#B71C1C;">Trump's Truth Social →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(act_now, high, medium):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 65,
        f" PHASE 6 TRUMP MARKET MONITOR — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f" {len(act_now)} Act Now · {len(high)} High · {len(medium)} Medium",
        "=" * 65,
    ]
    for a in (act_now + high + medium)[:10]:
        lines.append(f"\n  {a['urgency']} — {a['overall_sentiment']}")
        lines.append(f"  \"{a['post']['content'][:120]}...\"")
        tickers = ", ".join(f"${t}" for t in a["affected_stocks"])
        lines.append(f"  Stocks affected: {tickers}")
        for line in a["action_lines"][:2]:
            lines.append(f"    → {line[:100]}")
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
    print(f"🇺🇸 Phase 6 Trump Market Monitor — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    seen = load_seen()
    all_posts = []

    # ── Fetch all sources ─────────────────────────────────────
    print("\n[1/3] CNN Truth Social archive (live, 5-min updates)...")
    cnn_posts = fetch_cnn_truth_archive(hours_back=1)
    all_posts.extend(cnn_posts)

    print("\n[2/3] trumpstruth.org RSS (backup source)...")
    rss_posts = fetch_trumpstruth_rss()
    all_posts.extend(rss_posts)

    print("\n[3/3] Google News (Trump market/stock news)...")
    news_posts = fetch_google_news()
    all_posts.extend(news_posts)

    print(f"\n  Total posts/articles fetched: {len(all_posts)}")

    # ── Deduplicate ────────────────────────────────────────────
    new_posts  = []
    new_hashes = set()
    for p in all_posts:
        h = post_hash(p["id"], p["source"])
        if h not in seen and h not in new_hashes:
            new_posts.append(p)
            new_hashes.add(h)

    print(f"  New posts (not previously emailed): {len(new_posts)}")

    if not new_posts:
        print("  No new posts this run. No email sent.")
        return

    # ── Analyse each post ─────────────────────────────────────
    act_now = []
    high    = []
    medium  = []
    low     = []

    for post in new_posts:
        analysis = analyse_market_impact(post)
        if analysis is None:
            continue
        urgency = analysis["urgency"]
        if "ACT NOW"  in urgency: act_now.append(analysis)
        elif "HIGH"   in urgency: high.append(analysis)
        elif "MEDIUM" in urgency: medium.append(analysis)
        else:                     low.append(analysis)

    total_actionable = len(act_now) + len(high) + len(medium) + len(low)
    print(f"  Market-relevant: {total_actionable} | Act Now: {len(act_now)} | High: {len(high)} | Medium: {len(medium)}")

    # ── Only email if actionable content exists ────────────────
    if not act_now and not high and not medium:
        print("  No market-moving posts detected. No email sent.")
        save_seen(seen | new_hashes)
        return

    # ── Build email ────────────────────────────────────────────
    html_body = build_html_email(act_now, high, medium, low, len(new_posts))
    text_body = build_text_email(act_now, high, medium)

    # Subject line — make it feel urgent
    urgency_tag = "🚨 ACT NOW" if act_now else "⚡ HIGH PRIORITY" if high else "📊 MONITOR"
    top_tickers = []
    for a in (act_now + high)[:3]:
        top_tickers.extend(list(a["affected_stocks"].keys())[:2])
    ticker_str  = " ".join(f"${t}" for t in dict.fromkeys(top_tickers)[:4])

    subject = (f"🇺🇸 {urgency_tag}: Trump posted about {ticker_str or 'markets'} · "
               f"{len(act_now)+len(high)} urgent · {now.strftime('%H:%M UTC')}")

    print(text_body)
    save_seen(seen | new_hashes)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
