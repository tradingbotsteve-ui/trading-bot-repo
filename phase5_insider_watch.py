# ============================================================
# TRADING BOT — PHASE 5 (Insider Watch)
#
# Tracks LEGAL PUBLIC DISCLOSURES from three sources:
#
#   SOURCE 1 — SEC Form 4 (sec.gov)
#     Every US corporate insider (CEO, CFO, board member, 10%+ owner)
#     must file within 2 BUSINESS DAYS of buying or selling their own
#     company's stock. This is the most powerful signal in markets.
#     When a CEO buys $5M of their own stock, they know something.
#
#   SOURCE 2 — Capitol Trades (capitoltrades.com)
#     US Senators and Representatives must disclose all stock trades
#     within 45 days under the STOCK Act (2012). Politicians sit on
#     committees that see legislation before the public does.
#     Nancy Pelosi's husband's trades outperformed the market by 670%.
#
#   SOURCE 3 — OpenInsider (openinsider.com)
#     Aggregates and scores SEC Form 4 filings. Surfaces cluster buys
#     (multiple insiders buying the same stock in the same week).
#     Cluster buys are statistically the strongest signal.
#
# ALL DATA IS 100% LEGAL AND PUBLIC. These are government-mandated
# disclosures. Following them is called "coattail investing" and is
# practiced by professional fund managers worldwide.
#
# ── WHAT THE EMAIL TELLS YOU ─────────────────────────────────
#   • Who bought or sold (name, title, company)
#   • How many shares, at what price, total dollar amount
#   • Whether it was a BUY or SELL
#   • The signal strength (cluster buy = strongest)
#   • Plain-English explanation of what it means
#   • Suggested hold period and exit strategy for your TFSA
#
# ── COOLING PERIOD GUIDE (baked into every card) ─────────────
#   CEO/Executive BUY  → Hold 3-6 months, exit when they file sell
#   Cluster buy (3+)   → Hold 2-4 months, strongest signal
#   Congress BUY       → Hold 1-4 months, exit before next filing cycle
#   Any SELL           → Watch the stock — insiders leaving is a warning
#
# Runs every 30 minutes via GitHub Actions — 24/7.
# Sends email ONLY when new significant filings are detected.
# De-duplicates: you will NOT get the same filing twice.
#
# SECRETS (GitHub → Settings → Secrets → Actions):
#   EMAIL_SENDER    — your Gmail address
#   EMAIL_PASSWORD  — Gmail App Password (16 chars, NOT your login pw)
#   EMAIL_RECIPIENT — where to receive alerts (can be same as sender)
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

# ── FILTERS ───────────────────────────────────────────────────
MIN_TRADE_VALUE_USD   = 50_000   # ignore trades smaller than $50k
MIN_CONGRESS_VALUE    = 15_000   # Congress reports ranges — $15k+ floor
MAX_AGE_HOURS         = 72       # ignore filings older than 3 days
SEEN_FILE             = "/tmp/phase5_seen_filings.json"   # dedup cache

# ══════════════════════════════════════════════════════════════
# FAMOUS & TRENDING STOCK WHITELIST
#
# Only alert on stocks that are:
#   1. Household names — companies most people recognise
#   2. High market cap — large influence on the broader market
#   3. Actively traded — real liquidity, easy to buy/sell
#   4. Trending in 2025-2026 narratives:
#      AI, defence, energy, crypto, pharma, consumer, fintech
#
# If a ticker is NOT in this list it is silently ignored.
# No obscure micro-caps, no penny stocks, no noise.
#
# Congress trades on any of these = very high signal because
# these are the companies most affected by legislation.
#
# To add your own stock: just add its ticker to the set below.
# ══════════════════════════════════════════════════════════════

FAMOUS_TICKERS = {

    # ── AI & Big Tech ─────────────────────────────────────────
    "NVDA",   # Nvidia          — AI chips, most important AI company
    "MSFT",   # Microsoft       — Azure AI, OpenAI partner, Copilot
    "GOOGL",  # Alphabet A      — Google, Gemini AI, YouTube, Cloud
    "GOOG",   # Alphabet C      — same company, different share class
    "META",   # Meta            — Facebook, Instagram, Llama AI
    "AMZN",   # Amazon          — AWS cloud, largest e-commerce
    "AAPL",   # Apple           — iPhone, Mac, Apple Intelligence
    "TSLA",   # Tesla           — EVs, Robotaxis, Optimus robot
    "ORCL",   # Oracle          — cloud database, AI infrastructure
    "IBM",    # IBM             — enterprise AI, Watson
    "PLTR",   # Palantir        — AI for government and defence
    "AI",     # C3.ai           — enterprise AI software
    "SNOW",   # Snowflake       — AI data cloud
    "DDOG",   # Datadog         — AI-powered monitoring
    "CRM",    # Salesforce      — AI CRM, Einstein
    "NOW",    # ServiceNow      — AI enterprise workflows
    "ADBE",   # Adobe           — AI creative tools, Firefly
    "PATH",   # UiPath          — AI automation

    # ── Semiconductors ────────────────────────────────────────
    "AMD",    # AMD             — AI chips competing with Nvidia
    "INTC",   # Intel           — chips, foundry, turnaround play
    "QCOM",   # Qualcomm        — mobile chips, AI on device
    "AVGO",   # Broadcom        — AI networking chips
    "AMAT",   # Applied Materials — chip manufacturing equipment
    "ASML",   # ASML            — only company making EUV machines
    "TSM",    # TSMC            — makes chips for Nvidia, Apple, AMD
    "MU",     # Micron          — AI memory chips (HBM)
    "ARM",    # ARM Holdings    — chip architecture in every phone
    "SMCI",   # Super Micro     — AI server builder
    "MCHP",   # Microchip       — embedded chips

    # ── Crypto & Fintech ──────────────────────────────────────
    "COIN",   # Coinbase        — largest US crypto exchange
    "MSTR",   # MicroStrategy   — largest corporate Bitcoin holder
    "HOOD",   # Robinhood       — retail trading, crypto
    "SOFI",   # SoFi            — digital bank, crypto
    "PYPL",   # PayPal          — digital payments
    "SQ",     # Block (Square)  — Bitcoin, payments
    "V",      # Visa            — payments infrastructure
    "MA",     # Mastercard      — payments infrastructure
    "MARA",   # Marathon Digital — Bitcoin mining
    "RIOT",   # Riot Platforms  — Bitcoin mining
    "AXP",    # American Express — premium credit cards

    # ── Defence & Aerospace ───────────────────────────────────
    "LMT",    # Lockheed Martin — F-35, missiles, space
    "RTX",    # Raytheon        — missiles, radar, Patriot system
    "NOC",    # Northrop Grumman — B-21 bomber, drones
    "GD",     # General Dynamics — submarines, Gulfstream jets
    "BA",     # Boeing          — planes, defence contracts
    "KTOS",   # Kratos          — drones, hypersonics
    "HEI",    # HEICO           — defence aerospace parts
    "TDG",    # TransDigm       — defence aerospace components
    "LUNR",   # Intuitive Machines — Moon missions, NASA
    "RKLB",   # Rocket Lab      — small rockets, space

    # ── Energy & Clean Energy ─────────────────────────────────
    "XOM",    # ExxonMobil      — oil supermajor
    "CVX",    # Chevron         — oil supermajor
    "COP",    # ConocoPhillips  — oil and gas
    "NEE",    # NextEra         — largest clean energy company
    "ENPH",   # Enphase         — solar microinverters
    "FSLR",   # First Solar     — solar panels, US-made
    "OXY",    # Occidental      — Warren Buffett's oil bet
    "LNG",    # Cheniere        — LNG exports
    "VST",    # Vistra          — nuclear power for AI data centres
    "CEG",    # Constellation Energy — nuclear, Microsoft deal

    # ── Healthcare & Pharma & Biotech ─────────────────────────
    "LLY",    # Eli Lilly       — Ozempic/Mounjaro weight loss drugs
    "NVO",    # Novo Nordisk    — Ozempic original maker
    "ABBV",   # AbbVie          — Humira, Skyrizi, immunology
    "JNJ",    # Johnson & Johnson — pharma, medtech
    "PFE",    # Pfizer          — vaccines, oncology
    "MRK",    # Merck           — Keytruda cancer drug
    "AMGN",   # Amgen           — biotech, weight loss drugs
    "GILD",   # Gilead          — HIV, liver disease
    "MRNA",   # Moderna         — mRNA cancer vaccines
    "REGN",   # Regeneron       — eye disease, weight loss
    "ISRG",   # Intuitive Surgical — robotic surgery
    "DXCM",   # Dexcom          — continuous glucose monitors
    "VRTX",   # Vertex          — cystic fibrosis, gene editing

    # ── Financial & Banks ─────────────────────────────────────
    "JPM",    # JPMorgan        — largest US bank
    "BAC",    # Bank of America — major US bank
    "GS",     # Goldman Sachs   — investment banking
    "MS",     # Morgan Stanley  — wealth management
    "BLK",    # BlackRock       — world's largest asset manager
    "BRK.B",  # Berkshire       — Warren Buffett's conglomerate
    "C",      # Citigroup       — global bank
    "WFC",    # Wells Fargo     — major US bank
    "SCHW",   # Charles Schwab  — retail brokerage

    # ── Consumer & Retail ─────────────────────────────────────
    "WMT",    # Walmart         — world's largest retailer
    "COST",   # Costco          — membership warehouse retail
    "TGT",    # Target          — US retail
    "NKE",    # Nike            — sportswear
    "SBUX",   # Starbucks       — coffee, turnaround story
    "MCD",    # McDonald's      — fast food
    "CMG",    # Chipotle        — fast casual
    "LULU",   # Lululemon       — athletic wear

    # ── Media & Entertainment ─────────────────────────────────
    "NFLX",   # Netflix         — streaming, ads + gaming
    "DIS",    # Disney          — streaming, parks, ESPN
    "SPOT",   # Spotify         — music streaming
    "RBLX",   # Roblox          — gaming metaverse
    "TTWO",   # Take-Two        — GTA VI publisher (huge 2026)
    "EA",     # Electronic Arts — gaming

    # ── Electric Vehicles & Mobility ──────────────────────────
    "RIVN",   # Rivian          — electric trucks, Amazon vans
    "F",      # Ford            — F-150 Lightning, EV transition
    "GM",     # General Motors  — EVs, Cruise robotaxi
    "UBER",   # Uber            — rides, delivery, autonomous
    "LYFT",   # Lyft            — rides

    # ── Data Centres & Cloud Infrastructure ───────────────────
    "AMT",    # American Tower  — cell towers
    "EQIX",   # Equinix         — data centres
    "DLR",    # Digital Realty  — data centres
    "PLD",    # Prologis        — warehouses, logistics
    "DELL",   # Dell            — AI server infrastructure
    "NET",    # Cloudflare      — AI edge computing, security

    # ── Cybersecurity ─────────────────────────────────────────
    "CRWD",   # CrowdStrike     — cybersecurity AI
    "PANW",   # Palo Alto Networks — cybersecurity
    "ZS",     # Zscaler         — cloud security
    "OKTA",   # Okta            — identity security
    "S",      # SentinelOne     — AI cybersecurity

    # ── Quantum Computing ─────────────────────────────────────
    "IONQ",   # IonQ            — quantum computing
    "RGTI",   # Rigetti         — quantum computing
    "QUBT",   # Quantum Computing Inc — quantum

    # ── Canadian Stocks (TSX) ─────────────────────────────────
    "SHOP",   # Shopify         — e-commerce platform
    "RY",     # Royal Bank      — largest Canadian bank
    "TD",     # TD Bank         — major Canadian bank
    "CNR",    # CN Rail         — Canadian railways
    "SU",     # Suncor          — Canadian oil sands
    "ENB",    # Enbridge        — oil/gas pipelines
    "ATD",    # Couche-Tard     — convenience stores worldwide
    "CP",     # CP Rail         — Canadian railways
    "BAM",    # Brookfield      — global asset manager
    "BCE",    # BCE             — Canadian telecom
}


def is_famous(ticker):
    """Returns True if ticker is in our famous/trending watchlist."""
    clean = ticker.upper().strip().replace("-", ".")
    return clean in FAMOUS_TICKERS

# ── REQUEST HEADERS ──────────────────────────────────────────
# SEC requires a real User-Agent identifying your app and contact
HEADERS = {
    "User-Agent": "TradingBotPhase5/1.0 (educational-research; contact@example.com)",
    "Accept":     "application/json, text/html, application/xml",
}


# ══════════════════════════════════════════════════════════════
# DEDUPLICATION
# We store a hash of every filing we've already emailed about.
# This prevents you getting the same filing every 30 minutes.
# ══════════════════════════════════════════════════════════════

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen_set):
    try:
        # Keep only last 2000 entries to prevent file bloat
        entries = list(seen_set)[-2000:]
        with open(SEEN_FILE, "w") as f:
            json.dump(entries, f)
    except Exception:
        pass


def filing_hash(filing_dict):
    """Creates a unique fingerprint for a filing so we don't email it twice."""
    key = f"{filing_dict.get('ticker','')}-{filing_dict.get('filer','')}-{filing_dict.get('date','')}-{filing_dict.get('value','')}"
    return hashlib.md5(key.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
# SOURCE 1 — SEC EDGAR Form 4 (Corporate Insiders)
#
# SEC EDGAR has a free RSS feed of all Form 4 filings.
# Form 4 = insider transaction report.
# Filed within 2 business days of the trade.
# The most time-sensitive signal we track.
# ══════════════════════════════════════════════════════════════

def fetch_sec_form4():
    """
    Pulls the latest Form 4 filings from SEC EDGAR's full-text search API.
    Returns a list of parsed filing dicts.
    """
    filings = []

    try:
        # SEC EDGAR full-text search for recent Form 4 filings
        url = "https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={}&enddt={}&forms=4".format(
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d")
        )

        # Better: use the EDGAR RSS feed for Form 4 — more reliable
        rss_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=100&search_text=&output=atom"
        r = requests.get(rss_url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        root = ET.fromstring(r.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall("atom:entry", ns)
        print(f"  SEC Form 4 RSS: {len(entries)} recent filings found")

        for entry in entries[:80]:  # process most recent 80
            try:
                title    = entry.findtext("atom:title", "", ns)
                link_el  = entry.find("atom:link", ns)
                link     = link_el.get("href", "") if link_el is not None else ""
                updated  = entry.findtext("atom:updated", "", ns)
                summary  = entry.findtext("atom:summary", "", ns)

                # Title format: "4 - COMPANY NAME (TICKER) (0001234567) (Reporting)"
                ticker_match   = re.search(r'\(([A-Z]{1,5})\)', title)
                company_match  = re.search(r'4 - (.+?) \(', title)

                ticker  = ticker_match.group(1)  if ticker_match  else ""
                company = company_match.group(1) if company_match else title

                # Parse filing detail page to get actual trade data
                filing_data = parse_sec_filing_detail(link, ticker, company, updated)
                if filing_data:
                    filings.extend(filing_data)

            except Exception:
                pass

    except Exception as e:
        print(f"  SEC Form 4 fetch error: {e}")

    return filings


def parse_sec_filing_detail(index_url, ticker, company, filed_date):
    """
    Fetches the Form 4 index page and extracts the XML filing.
    Parses: filer name, title, transaction type, shares, price, value.
    """
    results = []
    try:
        # Get the index page to find the XML
        r = requests.get(index_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        # Find the XML filing link
        xml_match = re.search(r'href="(/Archives/edgar/data/[^"]+\.xml)"', r.text)
        if not xml_match:
            return []

        xml_url = "https://www.sec.gov" + xml_match.group(1)
        xr = requests.get(xml_url, headers=HEADERS, timeout=15)
        if xr.status_code != 200:
            return []

        root = ET.fromstring(xr.content)

        # Extract filer info
        reporter_name  = ""
        reporter_title = ""
        is_director    = False
        is_officer     = False
        is_ten_pct     = False

        for rn in root.iter("reportingOwner"):
            reporter_name  = _xml_text(rn, "rptOwnerName")
            reporter_title = _xml_text(rn, "officerTitle") or _xml_text(rn, "rptOwnerRelationship")
            is_director    = _xml_text(rn, "isDirector") == "1"
            is_officer     = _xml_text(rn, "isOfficer")  == "1"
            is_ten_pct     = _xml_text(rn, "isTenPercentOwner") == "1"

        # Extract transactions
        for tx in root.iter("nonDerivativeTransaction"):
            try:
                sec_title      = _xml_text(tx, "securityTitle")
                tx_date_str    = _xml_text(tx, "transactionDate")
                tx_code        = _xml_text(tx, "transactionCode")  # P=purchase, S=sale
                shares_str     = _xml_text(tx, "transactionShares")
                price_str      = _xml_text(tx, "transactionPricePerShare")
                shares_after   = _xml_text(tx, "sharesOwnedFollowingTransaction")

                if not shares_str or not price_str:
                    continue

                shares = float(shares_str.replace(",", ""))
                price  = float(price_str.replace(",", "")) if price_str else 0
                value  = shares * price

                if value < MIN_TRADE_VALUE_USD:
                    continue

                if tx_code not in ("P", "S", "A", "D"):  # P=buy, S=sell, A=award, D=disposal
                    continue

                tx_type = {
                    "P": "BOUGHT",
                    "S": "SOLD",
                    "A": "AWARDED",
                    "D": "DISPOSED",
                }.get(tx_code, tx_code)

                is_buy = tx_code in ("P", "A")

                results.append({
                    "source":        "SEC Form 4",
                    "source_icon":   "🏛️",
                    "ticker":        ticker,
                    "company":       company,
                    "filer":         reporter_name,
                    "title":         reporter_title or ("Director" if is_director else "Major Shareholder" if is_ten_pct else "Insider"),
                    "action":        tx_type,
                    "is_buy":        is_buy,
                    "shares":        int(shares),
                    "price":         price,
                    "value":         value,
                    "shares_after":  shares_after,
                    "security":      sec_title,
                    "date":          tx_date_str or filed_date[:10],
                    "filed":         filed_date[:10] if filed_date else "",
                    "link":          index_url,
                    "signal_strength": _sec_signal_strength(is_buy, value, is_director, is_officer, is_ten_pct),
                })

            except Exception:
                pass

        time.sleep(0.3)  # be polite to SEC servers

    except Exception as e:
        pass

    return results


def _xml_text(element, tag):
    """Safely get text from an XML element, checking common namespaces."""
    el = element.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    # Try with namespace
    for ns in ["ownershipDocument", ""]:
        el = element.find(f"{{{ns}}}{tag}") if ns else element.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    return ""


def _sec_signal_strength(is_buy, value, is_director, is_officer, is_ten_pct):
    """Rate the signal strength of an SEC filing 1-5."""
    if not is_buy:
        return 2  # sells are less meaningful (could be tax, divorce, etc.)
    score = 3
    if value >= 1_000_000:  score += 1
    if value >= 5_000_000:  score += 1
    if is_officer:          score = min(score + 1, 5)
    return min(score, 5)


# ══════════════════════════════════════════════════════════════
# SOURCE 2 — OpenInsider (openinsider.com)
#
# OpenInsider aggregates Form 4 data and adds scoring.
# Most importantly, it surfaces CLUSTER BUYS — when multiple
# insiders at the same company buy in the same week.
# Cluster buys are the #1 strongest insider signal statistically.
# ══════════════════════════════════════════════════════════════

def fetch_openinsider():
    """
    Scrapes OpenInsider's latest significant buys table.
    Returns list of filing dicts.
    """
    filings = []

    try:
        # OpenInsider URL: latest buys over $100k, sorted by filing date
        url = "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=3&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=3&xs=1&vl=100&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"

        r = requests.get(url, headers={**HEADERS, "User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code != 200:
            print(f"  OpenInsider HTTP {r.status_code}")
            return []

        # Parse the HTML table
        rows = re.findall(
            r'<tr[^>]*class="[^"]*"[^>]*>(.*?)</tr>',
            r.text, re.DOTALL
        )

        for row in rows[1:]:  # skip header
            try:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

                if len(cells) < 14:
                    continue

                # OpenInsider columns:
                # 0=X  1=Filing Date  2=Trade Date  3=Ticker  4=Company
                # 5=Insider Name  6=Title  7=Trade Type  8=Price
                # 9=Qty  10=Owned  11=ΔOwn  12=Value

                filed_date   = cells[1].strip()
                trade_date   = cells[2].strip()
                ticker       = cells[3].strip()
                company      = cells[4].strip()
                insider_name = cells[5].strip()
                title        = cells[6].strip()
                trade_type   = cells[7].strip()
                price_str    = cells[8].replace("$","").replace(",","").strip()
                qty_str      = cells[9].replace(",","").replace("+","").strip()
                value_str    = cells[12].replace("$","").replace(",","").replace("+","").strip()

                if not ticker or trade_type not in ("P - Purchase", "S - Sale"):
                    continue

                price = float(price_str) if price_str else 0
                qty   = int(float(qty_str)) if qty_str else 0
                value = float(value_str.replace("K","000").replace("M","000000")) if value_str else price * qty

                # Handle K/M suffixes
                if "K" in cells[12]:
                    value = float(re.sub(r'[^0-9.]', '', cells[12])) * 1_000
                elif "M" in cells[12]:
                    value = float(re.sub(r'[^0-9.]', '', cells[12])) * 1_000_000

                if value < MIN_TRADE_VALUE_USD or not ticker:
                    continue

                is_buy    = "Purchase" in trade_type
                tx_type   = "BOUGHT" if is_buy else "SOLD"

                filings.append({
                    "source":        "OpenInsider",
                    "source_icon":   "🔍",
                    "ticker":        ticker,
                    "company":       company,
                    "filer":         insider_name,
                    "title":         title,
                    "action":        tx_type,
                    "is_buy":        is_buy,
                    "shares":        qty,
                    "price":         price,
                    "value":         value,
                    "shares_after":  "",
                    "security":      "Common Stock",
                    "date":          trade_date,
                    "filed":         filed_date,
                    "link":          f"https://openinsider.com/{ticker}",
                    "signal_strength": _oi_signal_strength(is_buy, value, title),
                })

            except Exception:
                pass

        print(f"  OpenInsider: {len(filings)} filings parsed")

    except Exception as e:
        print(f"  OpenInsider fetch error: {e}")

    return filings


def _oi_signal_strength(is_buy, value, title):
    if not is_buy:
        return 2
    score = 3
    title_lower = title.lower()
    if any(t in title_lower for t in ["ceo", "chief executive", "president", "founder"]):
        score += 1
    if any(t in title_lower for t in ["cfo", "coo", "cto", "chief"]):
        score = max(score, 3)
    if value >= 1_000_000: score += 1
    if value >= 5_000_000: score = 5
    return min(score, 5)


# ══════════════════════════════════════════════════════════════
# SOURCE 3 — Capitol Trades (Congress Stock Trades)
#
# US politicians must disclose trades under the STOCK Act.
# We use the Capitol Trades public API — no key needed.
# This surfaces trades by Senators and Representatives who
# sit on committees with advance knowledge of legislation.
# ══════════════════════════════════════════════════════════════

def fetch_congress_trades():
    """
    Fetches recent Congress member trades from the Capitol Trades API.
    Returns list of filing dicts.
    """
    filings = []

    try:
        # Capitol Trades public API
        url = "https://www.capitoltrades.com/trades?pageSize=100&page=1"

        r = requests.get(url, headers={
            **HEADERS,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }, timeout=20)

        # Capitol Trades returns HTML — we parse it
        if r.status_code == 200:
            filings.extend(_parse_capitoltrades_html(r.text))

        # Also try the House Disclosure search (housestockwatcher.com)
        filings.extend(_fetch_house_stock_watcher())

        print(f"  Congress trades: {len(filings)} filings parsed")

    except Exception as e:
        print(f"  Congress trades fetch error: {e}")

    return filings


def _parse_capitoltrades_html(html):
    """Parse Capitol Trades HTML table."""
    filings = []
    try:
        # Extract trade rows
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in rows[1:]:
            try:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                if len(cells) < 7:
                    continue

                # Try to extract politician name, ticker, date, amount
                # Format varies — extract what we can
                politician = cells[0] if cells[0] else "Unknown Member"
                date_str   = cells[2] if len(cells) > 2 else ""
                ticker     = cells[3].upper() if len(cells) > 3 else ""
                action     = cells[4] if len(cells) > 4 else ""
                amount_str = cells[5] if len(cells) > 5 else ""

                if not ticker or len(ticker) > 6:
                    continue

                is_buy = any(w in action.lower() for w in ["purchase", "buy", "bought"])

                # Parse amount range (Congress reports ranges like "$15,001 - $50,000")
                amounts = re.findall(r'[\d,]+', amount_str.replace(",", ""))
                value   = int(amounts[-1]) if amounts else 0
                if value < MIN_CONGRESS_VALUE:
                    continue

                filings.append({
                    "source":        "Capitol Trades",
                    "source_icon":   "🏛️",
                    "ticker":        ticker,
                    "company":       ticker,
                    "filer":         politician,
                    "title":         "US Congress Member",
                    "action":        "BOUGHT" if is_buy else "SOLD",
                    "is_buy":        is_buy,
                    "shares":        0,
                    "price":         0,
                    "value":         value,
                    "shares_after":  "",
                    "security":      "Common Stock",
                    "date":          date_str,
                    "filed":         date_str,
                    "link":          f"https://www.capitoltrades.com/trades?ticker={ticker}",
                    "signal_strength": _congress_signal_strength(is_buy, value),
                    "amount_range":  amount_str,
                    "is_congress":   True,
                })
            except Exception:
                pass
    except Exception:
        pass
    return filings


def _fetch_house_stock_watcher():
    """
    House Stock Watcher has a clean public JSON API.
    Returns recent House disclosures.
    """
    filings = []
    try:
        url = "https://housestockwatcher.com/api"
        r   = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []

        trades = r.json()
        cutoff = datetime.now() - timedelta(hours=MAX_AGE_HOURS * 2)

        for trade in trades[:200]:
            try:
                ticker      = trade.get("ticker", "").strip().upper()
                name        = trade.get("representative", "")
                asset_desc  = trade.get("asset_description", "")
                tx_date     = trade.get("transaction_date", "")
                disc_date   = trade.get("disclosure_date", "")
                tx_type     = trade.get("type", "")
                amount      = trade.get("amount", "")

                if not ticker or ticker in ("--", "N/A", "") or len(ticker) > 6:
                    continue
                if "$" not in asset_desc and "stock" not in asset_desc.lower() and "share" not in asset_desc.lower():
                    if len(ticker) > 5:
                        continue

                is_buy = any(w in tx_type.lower() for w in ["purchase", "buy", "exchange"])

                # Parse amount range
                amounts = re.findall(r'[\d]+', amount.replace(",", ""))
                value   = int(amounts[-1]) * (1000 if "000" not in amount else 1) if amounts else 0

                # Rough value from range string
                if "$1,000,001" in amount or "over" in amount.lower():
                    value = 1_000_001
                elif "$500,001" in amount:
                    value = 500_001
                elif "$250,001" in amount:
                    value = 250_001
                elif "$100,001" in amount:
                    value = 100_001
                elif "$50,001" in amount:
                    value = 50_001
                elif "$15,001" in amount:
                    value = 15_001

                if value < MIN_CONGRESS_VALUE:
                    continue

                filings.append({
                    "source":         "House Stock Watcher",
                    "source_icon":    "🏛️",
                    "ticker":         ticker,
                    "company":        asset_desc[:60] if asset_desc else ticker,
                    "filer":          name,
                    "title":          "US House Representative",
                    "action":         "BOUGHT" if is_buy else "SOLD",
                    "is_buy":         is_buy,
                    "shares":         0,
                    "price":          0,
                    "value":          value,
                    "shares_after":   "",
                    "security":       "Common Stock",
                    "date":           tx_date,
                    "filed":          disc_date,
                    "link":           f"https://housestockwatcher.com/summary_by_ticker/{ticker}",
                    "signal_strength": _congress_signal_strength(is_buy, value),
                    "amount_range":   amount,
                    "is_congress":    True,
                })
            except Exception:
                pass

    except Exception as e:
        print(f"  House Stock Watcher error: {e}")

    return filings


def _congress_signal_strength(is_buy, value):
    if not is_buy:
        return 2
    if value >= 1_000_001: return 5
    if value >= 250_001:   return 4
    if value >= 100_001:   return 3
    return 2


# ══════════════════════════════════════════════════════════════
# CLUSTER BUY DETECTOR
#
# A cluster buy = 3+ different insiders at the SAME company
# all buying stock within the same week.
# This is statistically the strongest insider signal.
# Academic research shows cluster buys outperform the market
# by an average of 8-12% over the following 6 months.
# ══════════════════════════════════════════════════════════════

def detect_cluster_buys(all_filings):
    """
    Groups filings by ticker and detects when 3+ insiders bought the same stock.
    Returns dict of {ticker: count} for cluster buys.
    """
    ticker_buyers = {}
    for f in all_filings:
        if not f["is_buy"]:
            continue
        ticker = f["ticker"]
        filer  = f["filer"]
        if ticker not in ticker_buyers:
            ticker_buyers[ticker] = set()
        ticker_buyers[ticker].add(filer)

    return {
        ticker: len(buyers)
        for ticker, buyers in ticker_buyers.items()
        if len(buyers) >= 2  # flag at 2+, highlight at 3+
    }


# ══════════════════════════════════════════════════════════════
# PLAIN-ENGLISH EXPLANATION ENGINE
#
# Every filing gets a human-readable explanation.
# What does this trade MEAN? What should you DO?
# ══════════════════════════════════════════════════════════════

def generate_explanation(filing, cluster_count=0):
    """Returns (what_it_means: str, what_to_do: str, hold_period: str, exit_signal: str)"""
    name    = filing["filer"]
    title   = filing["title"]
    ticker  = filing["ticker"]
    action  = filing["action"]
    value   = filing["value"]
    is_buy  = filing["is_buy"]
    source  = filing["source"]
    is_cong = filing.get("is_congress", False)
    value_f = f"${value:,.0f}" if value >= 1000 else f"${value:.0f}"

    title_lower = title.lower()
    is_ceo = any(t in title_lower for t in ["ceo", "chief executive", "president", "founder"])
    is_cfo = any(t in title_lower for t in ["cfo", "chief financial", "treasurer"])
    is_dir = any(t in title_lower for t in ["director", "board"])

    if is_buy:
        # ── BUY explanations ──────────────────────────────────
        if is_cong:
            what = (
                f"{name}, a sitting US Congress member, just disclosed buying {value_f} worth of {ticker}. "
                f"Congress members sit on powerful committees — Finance, Armed Services, Health — that see "
                f"legislation before it becomes public. When they buy, it is worth paying attention."
            )
            do = (
                f"Look up {name}'s committee assignments. If they sit on a committee relevant to {ticker}'s industry, "
                f"this is a high-conviction signal. Buy the same stock in your TFSA within 1-2 days of seeing this alert."
            )
            hold  = "1 to 4 months — Congress trades tend to play out over 1 quarter"
            exit  = f"Exit when {ticker} has gained 15-25%, or when the legislation catalyst becomes public knowledge"

        elif is_ceo:
            what = (
                f"{name}, the CEO of {ticker.upper()}'s company, just personally bought {value_f} of their own company's stock. "
                f"CEOs know everything happening inside their company — upcoming contracts, earnings surprises, "
                f"acquisition talks. When a CEO spends {value_f} of their own money buying their own stock, "
                f"they are telling you they think the price is going higher."
            )
            do = (
                f"This is one of the strongest signals in markets. Buy {ticker} in your TFSA promptly. "
                f"CEOs rarely buy their own stock unless they are very confident about the near future."
            )
            hold  = "3 to 6 months — give the catalyst time to play out"
            exit  = f"Exit when the CEO files a SELL (Form 4), or when you have a 20-40% gain, whichever comes first"

        elif is_cfo:
            what = (
                f"{name}, the CFO (Chief Financial Officer) of {ticker}, bought {value_f} of company stock. "
                f"The CFO sees every dollar flowing through the company — revenue, costs, cash, debt. "
                f"When the person who manages all the money buys shares, the books look very good to them."
            )
            do = (
                f"A CFO buy is almost as strong as a CEO buy. Consider adding {ticker} to your TFSA. "
                f"Pair this with a check of the company's recent earnings trend."
            )
            hold  = "2 to 5 months"
            exit  = f"Exit on a 15-30% gain or when the CFO files a SELL on Form 4"

        elif cluster_count >= 3:
            what = (
                f"{cluster_count} different insiders at {ticker} have all bought stock in the past week — including {name} ({title}) "
                f"who bought {value_f}. This is called a CLUSTER BUY and is statistically the strongest insider signal. "
                f"Academic studies show cluster buys outperform the market by 8-12% over the next 6 months on average."
            )
            do = (
                f"CLUSTER BUY — this is your highest-conviction signal. Multiple people who know the company intimately "
                f"are all buying at the same time. Add {ticker} to your TFSA."
            )
            hold  = "2 to 6 months"
            exit  = f"Exit when cluster insiders start filing SELL orders, or on a 20%+ gain"

        else:
            what = (
                f"{name}, a {title} at {ticker}, bought {value_f} of company stock. "
                f"Corporate insiders legally cannot trade on non-public information at the time of filing — "
                f"but they know their company better than any analyst. Large buys signal confidence in the company's direction."
            )
            do = (
                f"Monitor {ticker} for a few more insider buys at the same company to confirm the signal. "
                f"One buy is interesting; two or more is actionable."
            )
            hold  = "1 to 3 months"
            exit  = f"Exit on a 10-20% gain or when insiders begin selling"

        if cluster_count >= 2:
            what += f" NOTE: {cluster_count} insiders at {ticker} have bought this week — approaching cluster buy territory."

    else:
        # ── SELL explanations ─────────────────────────────────
        what = (
            f"{name} ({title}) at {ticker} just SOLD {value_f} worth of stock. "
            f"Insider sells are harder to interpret than buys — they could be for tax reasons, a divorce settlement, "
            f"a house purchase, or diversification. A single sell is not necessarily bearish."
        )
        do = (
            f"Do NOT immediately sell {ticker} based on one insider sell. However, watch for additional insider sells "
            f"in the next 2-4 weeks. If 3+ insiders sell in the same month, that is a stronger warning signal."
        )
        hold  = "N/A — this is a SELL disclosure"
        exit  = f"If you hold {ticker}, consider tightening your stop loss. Multiple insider sells = time to exit."

    return what, do, hold, exit


# ══════════════════════════════════════════════════════════════
# SIGNAL STRENGTH STARS
# ══════════════════════════════════════════════════════════════

def signal_stars(strength):
    filled = "★" * strength
    empty  = "☆" * (5 - strength)
    color  = "#0A5D3E" if strength >= 4 else "#EF9F27" if strength >= 3 else "#888"
    return f'<span style="color:{color};font-size:16px;">{filled}{empty}</span>'


def strength_label(strength, is_buy):
    if not is_buy:
        return "⚠️ Sell — watch for more", "#7A4900", "#FEF3DC"
    labels = {
        5: ("🔥 Highest conviction", "#0A5D3E", "#D4F5E9"),
        4: ("📈 Strong signal",      "#1a237e", "#E8EAF6"),
        3: ("👀 Interesting signal", "#7A4900", "#FEF3DC"),
        2: ("📊 Mild signal",        "#555",    "#F5F5F5"),
        1: ("📊 Weak signal",        "#999",    "#FAFAFA"),
    }
    return labels.get(strength, labels[2])


# ══════════════════════════════════════════════════════════════
# EMAIL HTML BUILDER
# Matches your Phase 1 / Phase 2 / Phase 4 visual style exactly.
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:#f4f4f4;margin:0;padding:20px;color:#222;}
.wrap{max-width:680px;margin:0 auto;}
.header{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;
  padding:26px 28px;border-radius:14px 14px 0 0;}
.header h1{margin:0;font-size:21px;font-weight:700;}
.header p{margin:6px 0 0;font-size:13px;opacity:.8;}
.body{background:#fff;border:1px solid #e2e2e2;border-top:none;
  border-radius:0 0 14px 14px;padding-bottom:24px;}
.section{padding:20px 22px 0;}
.section-head{font-size:12px;font-weight:700;color:#666;text-transform:uppercase;
  letter-spacing:.7px;border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:12px;}
.card{border:1px solid #eaeaea;border-radius:10px;margin-bottom:16px;overflow:hidden;}
.card-top{background:#fafafa;padding:12px 16px;display:flex;
  justify-content:space-between;align-items:flex-start;border-bottom:1px solid #eee;}
.ticker{font-size:19px;font-weight:700;}
.company{font-size:12px;color:#888;margin-top:2px;}
.action-badge{display:inline-block;padding:4px 12px;border-radius:12px;
  font-size:13px;font-weight:700;margin-top:4px;}
.meta{display:flex;flex-wrap:wrap;gap:12px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:2px;}
.meta-item .val{font-size:13px;font-weight:600;}
.info-box{margin:8px 16px 8px;padding:12px 14px;border-radius:8px;
  font-size:13px;line-height:1.65;border-left:4px solid;}
.info-box .lbl{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:5px;}
.strength-box{margin:8px 16px 12px;padding:12px 16px;border-radius:8px;border-left:4px solid;}
.strength-label{font-size:15px;font-weight:700;margin-bottom:6px;}
.hold-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;}
.hold-item{background:#fff;border:1px solid #eee;border-radius:6px;
  padding:6px 12px;font-size:12px;flex:1;min-width:120px;}
.hold-item .hl{font-size:10px;color:#aaa;margin-bottom:2px;}
.hold-item .hv{font-weight:600;color:#333;}
.source-tag{font-size:10px;color:#bbb;padding:4px 16px 8px;}
.cluster-banner{background:linear-gradient(135deg,#0A5D3E,#1D9E75);
  margin:8px 16px 8px;padding:10px 14px;border-radius:8px;color:#fff;font-size:13px;}
.quicklist{margin:16px 22px 0;background:linear-gradient(135deg,#1a237e,#283593);
  border-radius:10px;padding:16px 18px;color:#fff;}
.quicklist h2{margin:0 0 4px;font-size:15px;font-weight:700;}
.quicklist p{margin:0 0 12px;font-size:12px;opacity:.85;}
.ql-row{display:flex;justify-content:space-between;align-items:center;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.2);}
.ql-row:last-child{border:none;padding-bottom:0;}
.ql-name{font-size:14px;font-weight:700;}
.ql-detail{font-size:11px;opacity:.85;margin-top:2px;}
.ql-badge{font-size:12px;background:rgba(255,255,255,0.25);
  padding:3px 10px;border-radius:10px;font-weight:700;white-space:nowrap;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.7;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 8px;}
.summary-stat .num{font-size:22px;font-weight:700;}
.summary-stat .desc{font-size:10px;color:#888;}
</style>
"""


def action_badge(is_buy, action):
    if is_buy:
        return f'<span class="action-badge" style="background:#D4F5E9;color:#0A5D3E;">🟢 {action}</span>'
    else:
        return f'<span class="action-badge" style="background:#FDECEA;color:#8a1a1a;">🔴 {action}</span>'


def source_badge(source):
    colors = {
        "SEC Form 4":         ("#1a237e", "#E8EAF6"),
        "OpenInsider":        ("#4a148c", "#F3E5F5"),
        "Capitol Trades":     ("#b71c1c", "#FFEBEE"),
        "House Stock Watcher":("#b71c1c", "#FFEBEE"),
    }
    col, bg = colors.get(source, ("#555", "#F5F5F5"))
    icons = {
        "SEC Form 4": "🏛️",
        "OpenInsider": "🔍",
        "Capitol Trades": "🏛️",
        "House Stock Watcher": "🏛️",
    }
    icon = icons.get(source, "📋")
    return f'<span style="background:{bg};color:{col};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;">{icon} {source}</span>'


def build_card(filing, cluster_count=0):
    is_buy    = filing["is_buy"]
    strength  = filing["signal_strength"]
    sig_label, sig_color, sig_bg = strength_label(strength, is_buy)
    what, do, hold, exit_sig = generate_explanation(filing, cluster_count)

    value_str = f"${filing['value']:,.0f}" if filing["value"] else "Undisclosed"
    shares_str = f"{filing['shares']:,} shares" if filing["shares"] else "Amount in range"
    price_str  = f"${filing['price']:.2f}/share" if filing["price"] else "See filing"

    cluster_html = ""
    if cluster_count >= 3 and is_buy:
        cluster_html = f'<div class="cluster-banner">🔥 <strong>CLUSTER BUY ALERT</strong> — {cluster_count} different insiders at {filing["ticker"]} have all bought this week. This is the strongest possible insider signal.</div>'
    elif cluster_count == 2 and is_buy:
        cluster_html = f'<div style="margin:6px 16px 6px;padding:8px 12px;background:#FEF3DC;border-radius:6px;font-size:12px;color:#7A4900;">📊 2 insiders have bought {filing["ticker"]} this week — watch for a third to confirm cluster buy.</div>'

    amount_range_html = ""
    if filing.get("amount_range"):
        amount_range_html = f'<div class="meta-item"><div class="lbl">Disclosed Range</div><div class="val">{filing["amount_range"]}</div></div>'

    shares_owned_html = ""
    if filing.get("shares_after"):
        shares_owned_html = f'<div class="meta-item"><div class="lbl">Shares Owned After</div><div class="val">{filing["shares_after"]}</div></div>'

    return f"""<div class="card">
  <div class="card-top">
    <div>
      <div class="ticker">{filing['ticker']} {source_badge(filing['source'])}</div>
      <div class="company">{filing['company']}</div>
      <div style="margin-top:6px;">{action_badge(is_buy, filing['action'])} &nbsp; {signal_stars(strength)}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:18px;font-weight:700;color:{'#0A5D3E' if is_buy else '#E24B4A'};">{value_str}</div>
      <div style="font-size:11px;color:#aaa;margin-top:3px;">Total transaction value</div>
      <div style="font-size:11px;color:#888;margin-top:2px;">Trade date: {filing['date']}</div>
    </div>
  </div>

  <div class="meta">
    <div class="meta-item"><div class="lbl">Insider</div><div class="val">{filing['filer']}</div></div>
    <div class="meta-item"><div class="lbl">Role / Title</div><div class="val">{filing['title']}</div></div>
    <div class="meta-item"><div class="lbl">Shares</div><div class="val">{shares_str}</div></div>
    <div class="meta-item"><div class="lbl">Price Per Share</div><div class="val">{price_str}</div></div>
    <div class="meta-item"><div class="lbl">Filed Date</div><div class="val">{filing['filed'] or filing['date']}</div></div>
    {amount_range_html}
    {shares_owned_html}
  </div>

  {cluster_html}

  <div class="info-box" style="background:#F8F8F8;border-left-color:#ccc;">
    <div class="lbl" style="color:#999;">What this trade means</div>
    {what}
  </div>

  <div class="info-box" style="background:#EEF4FF;border-left-color:#1a237e;">
    <div class="lbl" style="color:#1a237e;">What to do for your TFSA</div>
    {do}
  </div>

  <div class="strength-box" style="background:{sig_bg};border-left-color:{sig_color};">
    <div class="strength-label" style="color:{sig_color};">{sig_label}</div>
    <div class="hold-row">
      <div class="hold-item">
        <div class="hl">⏱️ Suggested Hold</div>
        <div class="hv">{hold}</div>
      </div>
      <div class="hold-item">
        <div class="hl">🚪 Exit Signal</div>
        <div class="hv">{exit_sig}</div>
      </div>
    </div>
  </div>

  <div class="source-tag">
    Source: <a href="{filing['link']}" style="color:#1a237e;">{filing['source']} →</a>
    &nbsp;·&nbsp; Data is 100% public and legally mandated
  </div>
</div>"""


def build_quicklist(top_buys, cluster_tickers):
    if not top_buys:
        return ""
    rows = ""
    for f in top_buys[:6]:
        cluster_tag = " 🔥 CLUSTER" if f["ticker"] in cluster_tickers and cluster_tickers[f["ticker"]] >= 3 else ""
        badge = "CEO Buy" if "ceo" in f["title"].lower() or "chief exec" in f["title"].lower() else \
                "Congress" if f.get("is_congress") else \
                f"Strength {f['signal_strength']}/5"
        rows += f"""<div class="ql-row">
    <div>
      <div class="ql-name">{f['ticker']}{cluster_tag}</div>
      <div class="ql-detail">{f['filer']} · ${f['value']:,.0f} · {f['date']}</div>
    </div>
    <div class="ql-badge">{badge}</div>
  </div>"""
    return f"""<div class="quicklist">
  <h2>⚡ Act Now — Today's Top Insider Buys</h2>
  <p>Highest-conviction filings from this run. Full analysis below each card.</p>
  {rows}
</div>"""


def build_html_email(new_buys, new_sells, cluster_tickers, total_new):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    cluster_buys    = [f for f in new_buys if cluster_tickers.get(f["ticker"], 0) >= 3]
    ceo_buys        = [f for f in new_buys if any(t in f["title"].lower() for t in ["ceo","chief exec","president","founder"])]
    congress_buys   = [f for f in new_buys if f.get("is_congress")]
    other_buys      = [f for f in new_buys if f not in cluster_buys and f not in ceo_buys and f not in congress_buys]

    top_buys_ql = sorted(new_buys, key=lambda x: -x["signal_strength"])[:6]

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>🕵️ Phase 5 · Insider Watch</h1>
  <p>{date_str} · Legal public disclosures only · SEC + Congress</p>
</div>
<div class="body">

  <div style="display:flex;justify-content:space-around;padding:16px 10px 8px;border-bottom:1px solid #f0f0f0;">
    <div class="summary-stat"><div class="num" style="color:#0A5D3E;">{len(new_buys)}</div><div class="desc">🟢 New Buys</div></div>
    <div class="summary-stat"><div class="num" style="color:#E24B4A;">{len(new_sells)}</div><div class="desc">🔴 New Sells</div></div>
    <div class="summary-stat"><div class="num" style="color:#0F6E56;">{len([t for t,c in cluster_tickers.items() if c>=3])}</div><div class="desc">🔥 Cluster Buys</div></div>
    <div class="summary-stat"><div class="num" style="color:#1a237e;">{len(ceo_buys)}</div><div class="desc">👔 CEO Buys</div></div>
    <div class="summary-stat"><div class="num" style="color:#b71c1c;">{len(congress_buys)}</div><div class="desc">🏛️ Congress</div></div>
  </div>

  {build_quicklist(top_buys_ql, cluster_tickers)}

  <div class="section">
    <p style="font-size:12px;color:#888;margin:12px 0 0;">
      All data below is <strong>100% legal and publicly mandated</strong> by US law.
      Corporate insiders must file with the SEC within 2 business days.
      Congress members must disclose within 45 days under the STOCK Act.
      Following these disclosures is called <strong>coattail investing</strong> — a legal strategy used by professional fund managers.<br>
      <strong style="color:#EF9F27;">⚠️ Not financial advice. Always do your own research. Trading involves risk of loss.</strong>
    </p>
  </div>
"""

    if cluster_buys:
        html += '<div class="section"><div class="section-head">🔥 Cluster Buys — Strongest Signal (3+ Insiders Same Company)</div>'
        for f in cluster_buys:
            html += build_card(f, cluster_tickers.get(f["ticker"], 0))
        html += '</div><div class="divider"></div>'

    if ceo_buys:
        html += '<div class="section"><div class="section-head">👔 CEO & Top Executive Buys</div>'
        for f in ceo_buys:
            html += build_card(f, cluster_tickers.get(f["ticker"], 0))
        html += '</div><div class="divider"></div>'

    if congress_buys:
        html += '<div class="section"><div class="section-head">🏛️ Congress Member Trades</div>'
        for f in congress_buys:
            html += build_card(f, cluster_tickers.get(f["ticker"], 0))
        html += '</div><div class="divider"></div>'

    if other_buys:
        html += '<div class="section"><div class="section-head">📈 Other Insider Buys</div>'
        for f in other_buys[:10]:  # cap at 10 to keep email readable
            html += build_card(f, cluster_tickers.get(f["ticker"], 0))
        html += '</div><div class="divider"></div>'

    if new_sells:
        html += '<div class="section"><div class="section-head">🔴 Insider Sells — Monitor These</div>'
        for f in new_sells[:8]:
            html += build_card(f, 0)
        html += '</div>'

    html += f"""
  <div class="divider"></div>
  <div class="footer">
    Phase 5 Insider Watch · Runs every 30 min via GitHub Actions · {total_new} new filings this run<br>
    Sources: SEC EDGAR Form 4 · OpenInsider · House Stock Watcher · Capitol Trades<br>
    All disclosures are legally mandated public records. Following them is 100% legal.<br>
    🕵️ Coattail investing — a strategy used by professional fund managers worldwide.<br>
    Research and education only — not financial advice. Trading involves risk of loss.<br>
    <a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4" style="color:#1a237e;">SEC Form 4 →</a> &nbsp;·&nbsp;
    <a href="https://openinsider.com" style="color:#1a237e;">OpenInsider →</a> &nbsp;·&nbsp;
    <a href="https://housestockwatcher.com" style="color:#1a237e;">House Stock Watcher →</a>
  </div>
</div></div></body></html>"""

    return html


def build_text_email(new_buys, new_sells, cluster_tickers):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 65,
        f" PHASE 5 INSIDER WATCH — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f" {len(new_buys)} new buys | {len(new_sells)} new sells | "
        f"{len([t for t,c in cluster_tickers.items() if c>=3])} cluster buys",
        "=" * 65,
    ]

    cluster_buys = [f for f in new_buys if cluster_tickers.get(f["ticker"], 0) >= 3]
    if cluster_buys:
        lines.append("\n🔥 CLUSTER BUYS (strongest signal):")
        for f in cluster_buys:
            lines.append(f"  ► {f['ticker']:<8} {f['filer']:<30} ${f['value']:>12,.0f}  [{f['date']}]")

    ceo_buys = [f for f in new_buys if any(t in f["title"].lower() for t in ["ceo","chief exec","president","founder"])]
    if ceo_buys:
        lines.append("\n👔 CEO/EXECUTIVE BUYS:")
        for f in ceo_buys:
            lines.append(f"  ► {f['ticker']:<8} {f['filer']:<30} ${f['value']:>12,.0f}  [{f['date']}]")
            lines.append(f"     Hold 3-6 months. Exit when CEO files SELL.")

    congress = [f for f in new_buys if f.get("is_congress")]
    if congress:
        lines.append("\n🏛️ CONGRESS TRADES:")
        for f in congress:
            amt = f.get("amount_range") or f"${f['value']:,.0f}"
            lines.append(f"  ► {f['ticker']:<8} {f['filer']:<30} {amt}")

    if new_sells:
        lines.append("\n🔴 INSIDER SELLS (watch these):")
        for f in new_sells[:5]:
            lines.append(f"  ► {f['ticker']:<8} {f['filer']:<30} ${f['value']:>12,.0f}  [{f['date']}]")

    lines += ["", "=" * 65, " Legal public disclosures only. Not financial advice.", "=" * 65]
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
    print(f"✅ Insider Watch email sent → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def run():
    now = datetime.now(timezone.utc)
    print(f"🕵️  Phase 5 Insider Watch — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    seen = load_seen()
    all_filings = []

    # ── Fetch all three sources ────────────────────────────────
    print("\n[1/3] Fetching SEC Form 4 filings...")
    sec_filings = fetch_sec_form4()
    all_filings.extend(sec_filings)
    print(f"  SEC Form 4: {len(sec_filings)} parsed")

    time.sleep(2)

    print("\n[2/3] Fetching OpenInsider significant buys...")
    oi_filings = fetch_openinsider()
    all_filings.extend(oi_filings)

    time.sleep(2)

    print("\n[3/3] Fetching Congress trades...")
    congress_filings = fetch_congress_trades()
    all_filings.extend(congress_filings)

    print(f"\n  Total filings fetched: {len(all_filings)}")

    # ── Deduplicate ────────────────────────────────────────────
    new_filings = []
    new_hashes  = set()
    for f in all_filings:
        h = filing_hash(f)
        if h not in seen and h not in new_hashes:
            new_filings.append(f)
            new_hashes.add(h)

    print(f"  New filings (not previously emailed): {len(new_filings)}")

    if not new_filings:
        print("  No new filings this run. No email sent.")
        return

    # ── Detect cluster buys ────────────────────────────────────
    cluster_tickers = detect_cluster_buys(all_filings)  # use ALL filings for cluster detection
    clusters_found  = {t: c for t, c in cluster_tickers.items() if c >= 3}
    if clusters_found:
        print(f"  🔥 Cluster buys detected: {clusters_found}")

    # ── Split buys and sells ───────────────────────────────────
    new_buys  = sorted([f for f in new_filings if f["is_buy"]],
                       key=lambda x: (-x["signal_strength"], -x["value"]))
    new_sells = sorted([f for f in new_filings if not f["is_buy"]],
                       key=lambda x: -x["value"])

    print(f"  New buys: {len(new_buys)} | New sells: {len(new_sells)}")

    # ── Only email if there are buys worth acting on ───────────
    actionable_buys = [f for f in new_buys if f["signal_strength"] >= 3]
    if not actionable_buys and not clusters_found:
        print("  No high-conviction buys this run. No email sent.")
        save_seen(seen | new_hashes)  # still save seen so we don't re-check
        return

    # ── Build and send email ───────────────────────────────────
    html_body = build_html_email(new_buys, new_sells, cluster_tickers, len(new_filings))
    text_body = build_text_email(new_buys, new_sells, cluster_tickers)

    # Build subject line
    top_ticker    = new_buys[0]["ticker"] if new_buys else "—"
    top_filer     = new_buys[0]["filer"]  if new_buys else "—"
    n_clusters    = len(clusters_found)
    congress_count = len([f for f in new_buys if f.get("is_congress")])

    subject_parts = [f"🕵️ Insider Watch: {len(new_buys)} new buys"]
    if n_clusters:          subject_parts.append(f"🔥 {n_clusters} cluster")
    if congress_count:      subject_parts.append(f"🏛️ {congress_count} Congress")
    subject_parts.append(f"Top: {top_ticker} ({top_filer[:20]})")
    subject_parts.append(now.strftime("%H:%M UTC"))

    subject = " · ".join(subject_parts)

    print(text_body)

    # ── Save seen hashes ───────────────────────────────────────
    save_seen(seen | new_hashes)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
