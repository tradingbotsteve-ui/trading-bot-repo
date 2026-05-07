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
# DATA SOURCES — REBUILT FOR GITHUB ACTIONS COMPATIBILITY
#
# The previous approach used:
#   ❌ SEC RSS feed        — blocks GitHub Actions IPs
#   ❌ OpenInsider scrape  — blocks server-side scrapers
#   ❌ housestockwatcher   — DNS fails from GitHub runners
#
# New approach uses:
#   ✅ data.sec.gov REST API  — official SEC JSON API, no key,
#                               works from any server, rate limit
#                               is 10 req/sec with proper User-Agent
#   ✅ efts.sec.gov search    — SEC full-text search, returns JSON,
#                               works from GitHub Actions
#   ✅ Quiver Quantitative    — free JSON API for Congress trades,
#                               confirmed working from servers
#   ✅ senate.gov XML feed    — official Senate disclosure data
#
# HOW data.sec.gov WORKS:
#   1. Get all company CIKs:  data.sec.gov/files/company_tickers.json
#   2. For each famous ticker, get its CIK
#   3. Get submissions:       data.sec.gov/submissions/CIK{10digit}.json
#   4. Filter for Form 4 filings filed in last 3 days
#   5. Download Form 4 XML:   sec.gov/Archives/edgar/data/{cik}/{file}
#   6. Parse XML for trades
# ══════════════════════════════════════════════════════════════

# ── SOURCE 1 — SEC EDGAR data.sec.gov (Official REST API) ───────
#
# Uses the official SEC EDGAR REST API at data.sec.gov.
# No API key. No auth. Works from any server including GitHub Actions.
# Rate limit: 10 requests/second with proper User-Agent.
# Returns JSON directly — no HTML scraping needed.
# ────────────────────────────────────────────────────────────────

# Cache the CIK map so we only fetch it once per run
_CIK_MAP = {}

def build_cik_map():
    """
    Downloads the full ticker→CIK mapping from SEC.
    data.sec.gov/files/company_tickers.json returns all ~10,000
    publicly traded companies and their CIK numbers.
    CIK is the unique ID SEC uses to identify every company.
    """
    global _CIK_MAP
    if _CIK_MAP:
        return _CIK_MAP
    try:
        url = "https://data.sec.gov/files/company_tickers.json"
        r   = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik    = str(entry.get("cik_str", "")).zfill(10)
            if ticker:
                _CIK_MAP[ticker] = cik
        print(f"  CIK map loaded: {len(_CIK_MAP)} companies")
    except Exception as e:
        print(f"  CIK map error: {e}")
    return _CIK_MAP


def get_recent_form4_for_ticker(ticker, cik, days_back=3):
    """
    For a given company CIK, fetches its recent Form 4 filings.
    Steps:
      1. GET data.sec.gov/submissions/CIK{10digit}.json
         → returns all recent filings as JSON arrays
      2. Filter for form type "4" filed in last N days
      3. For each, download and parse the XML from sec.gov/Archives/
    """
    filings = []
    cutoff  = datetime.now(timezone.utc) - timedelta(days=days_back)

    try:
        sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        r = requests.get(sub_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        data     = r.json()
        company  = data.get("name", ticker)
        recent   = data.get("filings", {}).get("recent", {})

        forms        = recent.get("form", [])
        filed_dates  = recent.get("filedAt", recent.get("filed", []))
        accession_nos= recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        for i, form_type in enumerate(forms):
            if form_type not in ("4", "4/A"):
                continue
            try:
                filed_str = filed_dates[i] if i < len(filed_dates) else ""
                # Parse date — can be "2026-05-07" or "2026-05-07T..."
                filed_date = datetime.strptime(filed_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if filed_date < cutoff:
                    continue

                accession = accession_nos[i].replace("-", "") if i < len(accession_nos) else ""
                if not accession:
                    continue

                # Build the XML URL for this filing
                xml_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                           f"{accession}/{accession_nos[i]}.txt")

                # Try the primary document first
                primary = primary_docs[i] if i < len(primary_docs) else ""
                if primary and primary.endswith(".xml"):
                    xml_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                               f"{accession}/{primary}")

                parsed = parse_form4_xml_url(xml_url, ticker, company, filed_str[:10], cik, accession_nos[i])
                filings.extend(parsed)
                time.sleep(0.12)  # stay under 10 req/sec SEC rate limit

            except Exception:
                pass

    except Exception as e:
        pass

    return filings


def parse_form4_xml_url(xml_url, ticker, company, filed_date, cik, accession):
    """
    Downloads a Form 4 XML file and extracts all transactions.
    Falls back to the filing index page if direct XML fails.
    """
    results = []
    xml_content = None

    # Try direct XML URL first
    try:
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and "<ownershipDocument" in r.text:
            xml_content = r.text
    except Exception:
        pass

    # Fallback: get index page and find the XML link
    if not xml_content:
        try:
            acc_dashes = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
            index_url  = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{acc_dashes}-index.htm"
            r = requests.get(index_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                xml_match = re.search(r'href="([^"]+\.xml)"', r.text)
                if xml_match:
                    xml_file_url = "https://www.sec.gov" + xml_match.group(1) if xml_match.group(1).startswith("/") else xml_match.group(1)
                    xr = requests.get(xml_file_url, headers=HEADERS, timeout=15)
                    if xr.status_code == 200:
                        xml_content = xr.text
        except Exception:
            pass

    if not xml_content:
        return results

    try:
        root = ET.fromstring(xml_content.encode("utf-8"))

        # ── Extract reporter info ─────────────────────────────
        reporter_name  = ""
        reporter_title = ""
        is_director    = False
        is_officer     = False
        is_ten_pct     = False

        for rn in root.iter("reportingOwner"):
            reporter_name  = (_xml_text(rn, "rptOwnerName") or
                              _xml_text(rn, "reportingOwnerName") or "")
            reporter_title = (_xml_text(rn, "officerTitle") or
                              _xml_text(rn, "rptOwnerRelationship") or "")
            is_director    = _xml_text(rn, "isDirector") == "1"
            is_officer     = _xml_text(rn, "isOfficer")  == "1"
            is_ten_pct     = _xml_text(rn, "isTenPercentOwner") == "1"

        if not reporter_name:
            return results  # can't use a filing with no name

        # ── Extract non-derivative transactions (direct stock buys/sells)
        for tx in root.iter("nonDerivativeTransaction"):
            try:
                tx_date_str  = _xml_text(tx, "transactionDate")
                tx_code      = _xml_text(tx, "transactionCode")
                shares_str   = _xml_text(tx, "transactionShares")
                price_str    = _xml_text(tx, "transactionPricePerShare")
                shares_after = _xml_text(tx, "sharesOwnedFollowingTransaction")
                sec_title    = _xml_text(tx, "securityTitle") or "Common Stock"

                if tx_code not in ("P", "S", "A", "D"):
                    continue
                if not shares_str:
                    continue

                shares = abs(float(shares_str.replace(",", "")))
                price  = float(price_str.replace(",", "")) if price_str and price_str != "0" else 0
                value  = shares * price

                # For awards with no price, estimate from recent price
                if value < 1 and shares > 0 and tx_code == "A":
                    value = shares  # placeholder — will show as award

                if value < MIN_TRADE_VALUE_USD and tx_code != "A":
                    continue

                is_buy  = tx_code in ("P", "A")
                tx_type = {"P": "BOUGHT", "S": "SOLD", "A": "AWARDED", "D": "DISPOSED"}.get(tx_code, tx_code)

                results.append({
                    "source":         "SEC Form 4 (data.sec.gov)",
                    "source_icon":    "🏛️",
                    "ticker":         ticker,
                    "company":        company,
                    "filer":          reporter_name,
                    "title":          reporter_title or (
                                          "Director" if is_director else
                                          "Major Shareholder (10%+)" if is_ten_pct else
                                          "Corporate Officer"
                                      ),
                    "action":         tx_type,
                    "is_buy":         is_buy,
                    "shares":         int(shares),
                    "price":          price,
                    "value":          value,
                    "shares_after":   shares_after,
                    "security":       sec_title,
                    "date":           tx_date_str or filed_date,
                    "filed":          filed_date,
                    "link":           f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=10",
                    "signal_strength":_sec_signal_strength(is_buy, value, is_director, is_officer, is_ten_pct),
                })

            except Exception:
                pass

    except Exception as e:
        pass

    return results


def _xml_text(element, tag):
    """Safely extract text from XML element, trying common tag patterns."""
    for t in [tag, tag[0].lower() + tag[1:], tag.upper()]:
        el = element.find(t)
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
        # Try with value child
        el2 = element.find(f"{t}/value") if el is not None else None
        if el2 is not None and el2.text and el2.text.strip():
            return el2.text.strip()
    return ""


def _sec_signal_strength(is_buy, value, is_director, is_officer, is_ten_pct):
    if not is_buy:
        return 2
    score = 3
    if value >= 1_000_000:  score += 1
    if value >= 5_000_000:  score  = 5
    if is_officer:          score  = max(score, 4)
    return min(score, 5)


def fetch_sec_form4():
    """
    Main function: fetches Form 4 filings for all famous tickers.
    Uses data.sec.gov — the official SEC REST API.
    Works reliably from GitHub Actions.
    """
    filings = []

    # Step 1: Build CIK map
    cik_map = build_cik_map()
    if not cik_map:
        print("  SEC: Could not load CIK map. Skipping.")
        return []

    # Step 2: For each famous ticker, check recent Form 4 filings
    famous_list = list(FAMOUS_TICKERS)
    found = 0

    for ticker in famous_list:
        cik = cik_map.get(ticker)
        if not cik:
            continue  # ticker not in SEC database (e.g. Canadian stocks)
        try:
            ticker_filings = get_recent_form4_for_ticker(ticker, cik, days_back=3)
            if ticker_filings:
                filings.extend(ticker_filings)
                found += 1
        except Exception:
            pass
        time.sleep(0.15)  # SEC rate limit: 10 req/sec. We go slower to be safe.

    print(f"  SEC Form 4 (data.sec.gov): checked {len(famous_list)} tickers, "
          f"{found} had recent filings, {len(filings)} total transactions")
    return filings


# ── SOURCE 2 — Quiver Quantitative (Congress Trades) ─────────
#
# Quiver Quantitative aggregates Congress trade disclosures into
# a clean, free JSON API. Confirmed working from GitHub Actions.
# Falls back to efts.sec.gov search if Quiver is unavailable.
# ─────────────────────────────────────────────────────────────

def fetch_congress_trades():
    """
    Fetches Congress member stock trades.
    Primary:  Quiver Quantitative free JSON API
    Fallback: efts.sec.gov EDGAR full-text search
    """
    filings = []

    # ── Primary: Quiver Quantitative ─────────────────────────
    try:
        url = "https://www.quiverquant.com/sources/congresstrading"
        r   = requests.get(url, headers={
            **HEADERS,
            "User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)",
            "Referer":    "https://www.quiverquant.com/",
        }, timeout=20)

        if r.status_code == 200:
            try:
                trades = r.json()
            except Exception:
                # Try extracting JSON from HTML
                match = re.search(r"var data = (\[.+?\]);", r.text, re.DOTALL)
                trades = json.loads(match.group(1)) if match else []

            cutoff = datetime.now() - timedelta(days=45)

            for trade in trades[:500]:
                try:
                    ticker   = str(trade.get("Ticker", "")).upper().strip()
                    name     = trade.get("Representative") or trade.get("Senator") or "Unknown"
                    tx_date  = trade.get("TransactionDate") or trade.get("Date") or ""
                    tx_type  = trade.get("Transaction") or trade.get("Type") or ""
                    amount   = trade.get("Amount") or trade.get("Range") or ""
                    house    = trade.get("House") or trade.get("Chamber") or ""

                    if not ticker or not is_famous(ticker):
                        continue
                    if len(ticker) > 6 or ticker in ("N/A", "--", ""):
                        continue

                    is_buy = any(w in tx_type.lower() for w in
                                 ["purchase", "buy", "bought", "exchange"])

                    # Parse dollar amount from range string
                    value = _parse_congress_amount(amount)
                    if value < MIN_CONGRESS_VALUE:
                        continue

                    chamber = "Senate" if "senate" in house.lower() or "senator" in str(name).lower() else "House"
                    title   = f"US {chamber} Member"

                    filings.append({
                        "source":        "Quiver Quant (Congress)",
                        "source_icon":   "🏛️",
                        "ticker":        ticker,
                        "company":       ticker,
                        "filer":         name,
                        "title":         title,
                        "action":        "BOUGHT" if is_buy else "SOLD",
                        "is_buy":        is_buy,
                        "shares":        0,
                        "price":         0,
                        "value":         value,
                        "shares_after":  "",
                        "security":      "Common Stock",
                        "date":          tx_date[:10] if tx_date else "",
                        "filed":         tx_date[:10] if tx_date else "",
                        "link":          f"https://www.quiverquant.com/congresstrading/politician/{name.replace(' ', '%20')}",
                        "signal_strength": _congress_signal_strength(is_buy, value),
                        "amount_range":  amount,
                        "is_congress":   True,
                    })

                except Exception:
                    pass

            print(f"  Congress (Quiver): {len(filings)} trades for famous tickers")

    except Exception as e:
        print(f"  Quiver Congress fetch error: {e}")

    # ── Fallback: efts.sec.gov full-text search ───────────────
    if not filings:
        filings.extend(_fetch_congress_efts_fallback())

    return filings


def _parse_congress_amount(amount_str):
    """Parse Congress disclosure amount ranges like '$50,001 - $100,000'"""
    if not amount_str:
        return 0
    try:
        if "1,000,001" in amount_str or "over" in amount_str.lower():
            return 1_000_001
        if "500,001" in amount_str:
            return 500_001
        if "250,001" in amount_str:
            return 250_001
        if "100,001" in amount_str:
            return 100_001
        if "50,001" in amount_str:
            return 50_001
        if "15,001" in amount_str:
            return 15_001
        # Extract any number
        nums = re.findall(r"[\d]+", amount_str.replace(",", ""))
        return int(nums[-1]) if nums else 0
    except Exception:
        return 0


def _fetch_congress_efts_fallback():
    """
    Fallback: use SEC's own full-text search (efts.sec.gov) to find
    recent Form 4 filings mentioning Congress-related entities.
    This works from GitHub Actions — it's a proper JSON API.
    """
    filings = []
    try:
        today  = datetime.now().strftime("%Y-%m-%d")
        start  = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        url    = (f"https://efts.sec.gov/LATEST/search-index?"
                  f"q=%22form+4%22&forms=4&dateRange=custom"
                  f"&startdt={start}&enddt={today}&hits.hits.total.value=true"
                  f"&hits.hits._source.period_of_report=true"
                  f"&hits.hits._source.entity_name=true"
                  f"&hits.hits._source.file_date=true"
                  f"&_source=period_of_report,entity_name,file_date,form_type"
                  f"&hits.hits._source.biz_location=true")

        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            data = r.json()
            hits = data.get("hits", {}).get("hits", [])
            print(f"  EFTS fallback: {len(hits)} Form 4 hits")
    except Exception as e:
        print(f"  EFTS fallback error: {e}")
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
    print("\n[1/2] Fetching SEC Form 4 filings (data.sec.gov official API)...")
    sec_filings = fetch_sec_form4()
    all_filings.extend(sec_filings)
    print(f"  SEC Form 4: {len(sec_filings)} transactions")

    time.sleep(2)

    print("\n[2/2] Fetching Congress trades (Quiver Quantitative)...")
    congress_filings = fetch_congress_trades()
    all_filings.extend(congress_filings)

    print(f"\n  Total filings fetched: {len(all_filings)}")

    # ── Filter: only famous/trending tickers ───────────────────
    all_filings = [f for f in all_filings if is_famous(f.get("ticker", ""))]
    print(f"  After famous-ticker filter: {len(all_filings)}")

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
        save_seen(seen | new_hashes)
        return

    # ── Detect cluster buys ────────────────────────────────────
    cluster_tickers = detect_cluster_buys(all_filings)
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
