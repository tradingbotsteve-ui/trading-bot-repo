# ============================================================
#  TRADING BOT — PHASE 2
#  Full US + Canadian Market Scanner
#  Undervaluation Scoring + News Alert Engine
#
#  Runs at 7:00 AM Pacific via GitHub Actions (separate job).
#  Sends its own email — does NOT depend on Phase 1.
#
#  GitHub Secrets required (same ones as Phase 1):
#    ALPHA_VANTAGE_KEY
#    EMAIL_SENDER
#    EMAIL_PASSWORD
#    EMAIL_RECIPIENT
#
#  To add/remove tickers: edit the sector dictionaries below.
# ============================================================

import os, smtplib, requests, time, json
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import defaultdict

# ── SECRETS (pulled from GitHub Actions environment) ──────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",     "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT",  "your@gmail.com")
AV_KEY          = os.environ.get("ALPHA_VANTAGE_KEY","demo")
# ──────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════
#  MARKET UNIVERSE  — US + CANADA
#  Organized by sector so we can benchmark P/E correctly.
#  Add or remove tickers freely — just keep the format.
# ══════════════════════════════════════════════════════════════

US_UNIVERSE = {
    "Technology": [
        "AAPL","MSFT","GOOGL","META","NVDA","AMD","INTC","QCOM","TXN","ADI",
        "MCHP","SWKS","MU","STX","WDC","CSCO","ORCL","IBM","AMAT","LRCX",
        "KLAC","ASML","SNPS","CDNS","ADBE","CRM","NOW","WDAY","VEEV",
        "ZM","DOCU","BOX","DDOG","SNOW","PLTR","PATH","AI","HPQ",
        "DELL","PSTG","NTAP","FFIV","JNPR","AKAM","NET","FSLY","ESTC",
    ],
    "Consumer Cyclical": [
        "AMZN","TSLA","HD","LOW","TJX","ROST","BURL","NKE","LULU","PVH",
        "RL","VFC","GPS","ANF","AEO","URBN","CHWY","ETSY","EBAY",
        "BABA","JD","PDD","W","RH","BBY","DKS","ULTA","BOOT","SHAK",
        "CMG","MCD","SBUX","YUM","QSR","DPZ","WEN","JACK","DENN",
    ],
    "Consumer Defensive": [
        "WMT","COST","KR","TGT","DG","DLTR","SYY","KO","PEP","MDLZ",
        "GIS","K","CPB","CAG","MKC","HRL","SJM","POST","LANC","CALM",
        "PM","MO","BTI","UL","PG","CL","CHD","ENR","KMB","CLX",
    ],
    "Healthcare": [
        "UNH","CVS","CI","HUM","CNC","MOH","ELV","ABC","MCK","CAH",
        "JNJ","PFE","MRK","ABBV","LLY","BMY","GILD","AMGN","BIIB","VRTX",
        "REGN","SGEN","ALNY","MRNA","BNTX","NVAX","SRPT","BLUE","EDIT",
        "MDT","ABT","BSX","SYK","ZBH","HOLX","ISRG","DXCM","PODD",
    ],
    "Financials": [
        "JPM","BAC","WFC","C","GS","MS","USB","PNC","TFC","COF",
        "AXP","DFS","SYF","ALLY","SCHW","IBKR","HOOD","SOFI","LC",
        "BLK","BEN","IVZ","AMP","LNC","PRU","MET","AFL","ALL","TRV",
        "CB","AON","MMC","WTW","CINF","PGR","HIG","EIG","ERIE",
        "V","MA","PYPL","SQ","FIS","FI","GPN","WEX","FLYW",
    ],
    "Energy": [
        "XOM","CVX","COP","EOG","PXD","DVN","FANG","MRO","APA","HAL",
        "SLB","BKR","NOV","OXY","MPC","VLO","PSX","HES","KMI","WMB",
        "ET","EPD","MPLX","PAA","OKE","LNG","CQP","RRC","EQT","AR",
    ],
    "Industrials": [
        "GE","HON","MMM","CAT","DE","EMR","ITW","PH","ROK","AME",
        "FTV","XYL","XYLEM","NDSN","GNRC","MIDD","CFX","KNX","CHRW",
        "UPS","FDX","XPO","SAIA","ODFL","JBHT","WERN","HTLD",
        "LMT","RTX","NOC","GD","L3T","HEI","TDG","SPR","KTOS",
        "BA","AIR","AAL","DAL","UAL","LUV","ALK","SAVE",
    ],
    "Communication Services": [
        "GOOGL","META","NFLX","DIS","PARA","WBD","FOX","FOXA","NWSA",
        "T","VZ","TMUS","LBRDA","LBRDK","DISH","SIRI","IACI",
        "SNAP","PINS","TWTR","RDDT","BMBL","MTCH",
    ],
    "Real Estate": [
        "AMT","PLD","EQIX","CCI","DLR","SBAC","WELL","VTR","HR","NHI",
        "SPG","O","VICI","GLPI","PENN","MGM","WYNN","LVS","CZR",
        "EQR","AVB","ESS","UDR","CPT","MAA","NMD","INVH","AMH",
    ],
    "Utilities": [
        "NEE","DUK","SO","D","EXC","AEP","XEL","WEC","CMS","NI",
        "ED","ETR","FE","PPL","PNW","AES","AWK","SRE","PCG","EIX",
    ],
    "Basic Materials": [
        "LIN","APD","ECL","SHW","PPG","NEM","GOLD","AEM","WPM","PAN",
        "FCX","AA","CENX","X","NUE","STLD","RS","CMC","CLF","MT",
        "MOS","CF","NTR","FMC","ALB","LTHM","LAC","SGML",
    ],
}

# Canadian stocks — TSX listed (yfinance uses .TO suffix)
CANADA_UNIVERSE = {
    "Technology": [
        "SHOP.TO","CSU.TO","DCBO.TO","LSPD.TO","NVEI.TO","KXS.TO",
        "DSG.TO","BBTV.TO","MTRG.TO","CAND.TO",
    ],
    "Financials": [
        "RY.TO","TD.TO","BNS.TO","BMO.TO","CM.TO","NA.TO",
        "MFC.TO","SLF.TO","GWO.TO","IFC.TO","FFH.TO","EFN.TO",
    ],
    "Energy": [
        "SU.TO","CNQ.TO","CVE.TO","IMO.TO","MEG.TO","TOU.TO",
        "ARX.TO","BTE.TO","ERF.TO","SGY.TO","PEY.TO","TPZ.TO",
        "ENB.TO","TRP.TO","PPL.TO","KEY.TO","GEI.TO",
    ],
    "Mining & Materials": [
        "ABX.TO","AGI.TO","K.TO","AEM.TO","FNV.TO","WPM.TO",
        "G.TO","EDV.TO","NGT.TO","BTG.TO","SSO.TO",
        "TECK.TO","CS.TO","FM.TO","LUN.TO","HBM.TO","CG.TO",
        "NTR.TO","AGU.TO","MOS.TO",
    ],
    "Industrials": [
        "CNR.TO","CP.TO","TIH.TO","WSP.TO","STN.TO","SNC.TO",
        "CAE.TO","MDA.TO","HRX.TO","TFII.TO",
    ],
    "Consumer": [
        "ATD.TO","DOL.TO","MRU.TO","EMP-A.TO","L.TO",
        "CTC-A.TO","QSR.TO","RECP.TO","MTY.TO",
    ],
    "Healthcare": [
        "NVO.TO","DND.TO","WELL.TO","NVEI.TO","CXI.TO",
    ],
    "Real Estate": [
        "RioCan.TO","REI-UN.TO","CAR-UN.TO","GRT-UN.TO","AP-UN.TO",
        "CHP-UN.TO","HOM-UN.TO","HR-UN.TO","D-UN.TO",
    ],
    "Utilities": [
        "FTS.TO","H.TO","AQN.TO","EMA.TO","NPI.TO","BLX.TO",
        "INE.TO","CPX.TO","ALA.TO","BEP-UN.TO","BIP-UN.TO",
    ],
}

# Sector median P/E benchmarks
SECTOR_PE_BENCHMARKS = {
    "Technology":             28,
    "Consumer Cyclical":      22,
    "Consumer Defensive":     20,
    "Healthcare":             18,
    "Financials":             13,
    "Financial Services":     13,
    "Energy":                 11,
    "Industrials":            19,
    "Communication Services": 16,
    "Real Estate":            30,
    "Utilities":              17,
    "Basic Materials":        14,
    "Mining & Materials":     14,
    "Consumer":               20,
    "Unknown":                18,
}


# ══════════════════════════════════════════════════════════════
#  INSTALL DEPENDENCIES
# ══════════════════════════════════════════════════════════════

def _install(pkg):
    import subprocess, sys
    subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q"])

try:    import yfinance as yf
except: _install("yfinance"); import yfinance as yf

try:    from textblob import TextBlob
except: _install("textblob"); from textblob import TextBlob


# ══════════════════════════════════════════════════════════════
#  DATA LAYER
# ══════════════════════════════════════════════════════════════

def fetch_fundamentals(ticker, sector_hint="Unknown"):
    """Pull all fundamentals for a single ticker. Returns dict or None."""
    try:
        info = yf.Ticker(ticker).info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price or price <= 0:
            return None
        return {
            "ticker":          ticker,
            "name":            info.get("shortName", ticker),
            "sector":          info.get("sector", sector_hint),
            "country":         info.get("country", "US"),
            "currency":        info.get("currency", "USD"),
            "price":           price,
            "pe":              info.get("trailingPE"),
            "fwd_pe":          info.get("forwardPE"),
            "pb":              info.get("priceToBook"),
            "ps":              info.get("priceToSalesTrailing12Months"),
            "peg":             info.get("pegRatio"),
            "roe":             info.get("returnOnEquity"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin":   info.get("profitMargins"),
            "debt_equity":     info.get("debtToEquity"),
            "current_ratio":   info.get("currentRatio"),
            "free_cashflow":   info.get("freeCashflow"),
            "mktcap":          info.get("marketCap"),
            "52low":           info.get("fiftyTwoWeekLow"),
            "52high":          info.get("fiftyTwoWeekHigh"),
            "analyst_target":  info.get("targetMeanPrice"),
            "analyst_count":   info.get("numberOfAnalystOpinions"),
            "rec_mean":        info.get("recommendationMean"),
            "dividend_yield":  info.get("dividendYield"),
            "beta":            info.get("beta"),
        }
    except Exception as e:
        return None


def fetch_news_sentiment(ticker, max_items=8):
    """
    Fetch news headlines + sentiment for a ticker.
    Uses Alpha Vantage NEWS_SENTIMENT endpoint.
    Falls back to yfinance .news if AV returns nothing.
    """
    headlines = []

    # Try Alpha Vantage first
    try:
        url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
               f"&tickers={ticker}&limit=10&apikey={AV_KEY}")
        data = requests.get(url, timeout=10).json()
        for item in data.get("feed", [])[:max_items]:
            title = item.get("title","")
            pub   = item.get("time_published","")[:8]
            try:   pub_fmt = datetime.strptime(pub,"%Y%m%d").strftime("%b %d")
            except: pub_fmt = pub

            # Try AV ticker-specific score first, fall back to TextBlob
            score = None
            for ts in item.get("ticker_sentiment",[]):
                if ts.get("ticker","").upper() == ticker.upper().replace(".TO",""):
                    score = float(ts.get("ticker_sentiment_score", 0))
                    break
            if score is None:
                score = TextBlob(title).sentiment.polarity

            headlines.append({
                "date":  pub_fmt,
                "title": title[:120],
                "score": round(score, 3),
                "url":   item.get("url","#"),
                "source": item.get("source",""),
            })
    except Exception:
        pass

    # Fallback: yfinance news (no score, so TextBlob only)
    if not headlines:
        try:
            yf_news = yf.Ticker(ticker).news or []
            for item in yf_news[:max_items]:
                title = item.get("title","")
                ts    = item.get("providerPublishTime", 0)
                pub_fmt = datetime.fromtimestamp(ts).strftime("%b %d") if ts else "—"
                score = TextBlob(title).sentiment.polarity
                headlines.append({
                    "date":  pub_fmt,
                    "title": title[:120],
                    "score": round(score, 3),
                    "url":   item.get("link","#"),
                    "source": item.get("publisher",""),
                })
        except Exception:
            pass

    return headlines


def avg_sentiment(headlines):
    """Returns average sentiment score across headlines."""
    if not headlines:
        return 0.0
    return round(sum(h["score"] for h in headlines) / len(headlines), 3)


# ══════════════════════════════════════════════════════════════
#  UNDERVALUATION SCORING ENGINE
# ══════════════════════════════════════════════════════════════

def score_stock(f):
    """
    Score a stock 0–100 for undervaluation potential.

    Five pillars × 20 pts each = 100 max, plus bonuses:
      1. P/E vs sector median
      2. Forward P/E improvement (earnings acceleration)
      3. PEG ratio (cheap relative to growth)
      4. Price-to-book (asset value)
      5. Analyst upside to price target
    Bonuses: revenue growth, free cash flow, low debt, dividend
    """
    if not f or not f.get("price"):
        return 0, "No data", []

    score   = 0
    reasons = []
    sector  = f.get("sector","Unknown")
    sp      = SECTOR_PE_BENCHMARKS.get(sector, 18)

    # ── Pillar 1: P/E vs sector ──────────────────────────────
    pe = f.get("pe")
    if pe and 0 < pe < 200:
        ratio = pe / sp
        if ratio < 0.40:   pts = 20; reasons.append(f"P/E {pe:.1f}x — less than 40% of sector avg ({sp}x) 🔥")
        elif ratio < 0.60: pts = 17; reasons.append(f"P/E {pe:.1f}x — well below sector avg ({sp}x)")
        elif ratio < 0.80: pts = 13; reasons.append(f"P/E {pe:.1f}x — below sector avg ({sp}x)")
        elif ratio < 1.00: pts = 8;  reasons.append(f"P/E {pe:.1f}x — slightly below sector avg")
        elif ratio < 1.20: pts = 4
        else:              pts = 0
        score += pts

    # ── Pillar 2: Forward P/E improvement ────────────────────
    fwd = f.get("fwd_pe")
    if fwd and pe and 0 < fwd < 200 and 0 < pe < 200:
        impr = (pe - fwd) / pe
        if impr > 0.30:   pts = 20; reasons.append(f"Fwd P/E {fwd:.1f}x vs trailing {pe:.1f}x — earnings surging ⚡")
        elif impr > 0.15: pts = 14; reasons.append(f"Fwd P/E {fwd:.1f}x — improving earnings outlook")
        elif impr > 0.05: pts = 8;  reasons.append(f"Fwd P/E {fwd:.1f}x — slight improvement expected")
        elif impr > 0:    pts = 4
        elif fwd < sp:    pts = 6;  reasons.append(f"Fwd P/E {fwd:.1f}x below sector avg")
        else:             pts = 0
        score += pts

    # ── Pillar 3: PEG ratio ───────────────────────────────────
    peg = f.get("peg")
    if peg and 0 < peg < 10:
        if peg < 0.5:   pts = 20; reasons.append(f"PEG {peg:.2f} — extremely cheap vs growth rate 🔥")
        elif peg < 1.0: pts = 15; reasons.append(f"PEG {peg:.2f} — undervalued vs growth")
        elif peg < 1.5: pts = 9;  reasons.append(f"PEG {peg:.2f} — fair value relative to growth")
        elif peg < 2.0: pts = 4
        else:           pts = 0
        score += pts

    # ── Pillar 4: Price-to-book ───────────────────────────────
    pb = f.get("pb")
    if pb and pb > 0:
        if pb < 0.8:   pts = 20; reasons.append(f"P/B {pb:.2f} — trading BELOW book value 🔥")
        elif pb < 1.2: pts = 17; reasons.append(f"P/B {pb:.2f} — near book value (rare)")
        elif pb < 2.0: pts = 12; reasons.append(f"P/B {pb:.2f} — reasonable asset value")
        elif pb < 3.5: pts = 7
        elif pb < 6:   pts = 3
        else:          pts = 0
        score += pts

    # ── Pillar 5: Analyst upside ──────────────────────────────
    target  = f.get("analyst_target")
    price   = f.get("price")
    nanalysts = f.get("analyst_count") or 0
    if target and price and price > 0 and nanalysts >= 3:
        upside = (target - price) / price * 100
        if upside > 50:   pts = 20; reasons.append(f"Analyst consensus target ${target:.0f} = {upside:.0f}% upside ({nanalysts} analysts) 🚀")
        elif upside > 30: pts = 16; reasons.append(f"Analyst target ${target:.0f} = {upside:.0f}% upside")
        elif upside > 20: pts = 12; reasons.append(f"Analyst target ${target:.0f} = {upside:.0f}% upside")
        elif upside > 10: pts = 7;  reasons.append(f"Analyst target ${target:.0f} = {upside:.0f}% upside")
        elif upside > 0:  pts = 3
        else:             pts = 0
        score += pts

    # ── Bonuses ───────────────────────────────────────────────
    rg = f.get("revenue_growth")
    if rg and rg > 0.20: score += 5; reasons.append(f"Revenue growing {rg*100:.0f}% YoY 📈")
    elif rg and rg > 0.10: score += 3; reasons.append(f"Revenue growing {rg*100:.0f}% YoY")

    fcf = f.get("free_cashflow")
    if fcf and fcf > 0: score += 3; reasons.append("Positive free cash flow ✅")

    de = f.get("debt_equity")
    if de is not None and 0 <= de < 30:  score += 3; reasons.append("Very low debt-to-equity")
    elif de is not None and de < 80:     score += 1

    div = f.get("dividend_yield")
    if div and div > 0.03: score += 2; reasons.append(f"Dividend yield {div*100:.1f}%")

    roe = f.get("roe")
    if roe and roe > 0.20: score += 2; reasons.append(f"Strong ROE {roe*100:.0f}%")

    score = min(score, 100)

    if score >= 70:   label = "🔥 Deeply undervalued"
    elif score >= 55: label = "📈 Potentially undervalued"
    elif score >= 40: label = "🟡 Worth watching"
    elif score >= 25: label = "⚪ Fairly valued"
    else:             label = "🔴 Expensive / avoid"

    return score, label, reasons


# ══════════════════════════════════════════════════════════════
#  MAIN SCAN  — runs both universes
# ══════════════════════════════════════════════════════════════

def run_full_scan():
    """Scans all US + Canadian tickers. Returns sorted results list."""
    results = []
    request_count = 0

    def throttle():
        nonlocal request_count
        request_count += 1
        if request_count % 5 == 0:
            time.sleep(15)   # stay under AV free tier (5 req/min)
        else:
            time.sleep(1)    # small pause between yfinance calls

    # Build combined list: [(ticker, sector, country), ...]
    all_tickers = []
    for sector, tickers in US_UNIVERSE.items():
        for t in tickers:
            all_tickers.append((t, sector, "US"))
    for sector, tickers in CANADA_UNIVERSE.items():
        for t in tickers:
            all_tickers.append((t, sector, "CA"))

    # Deduplicate
    seen = set()
    unique_tickers = []
    for item in all_tickers:
        if item[0] not in seen:
            seen.add(item[0])
            unique_tickers.append(item)

    total = len(unique_tickers)
    print(f"  Scanning {total} tickers across US + Canadian markets...")

    for i, (ticker, sector, country) in enumerate(unique_tickers):
        try:
            f = fetch_fundamentals(ticker, sector)
            if not f:
                throttle()
                continue

            sc, label, reasons = score_stock(f)
            results.append({
                **f,
                "score":    sc,
                "label":    label,
                "reasons":  reasons,
                "country":  country,
                "sector_hint": sector,
            })

            if (i + 1) % 25 == 0:
                print(f"    Progress: {i+1}/{total} scanned, "
                      f"{len([r for r in results if r['score']>=55])} candidates so far...")
            throttle()

        except Exception as e:
            print(f"    {ticker}: error — {e}")
            throttle()

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def fetch_news_for_top_picks(scored_results, top_n=40):
    """
    Fetch news for top N undervalued picks + classify as upside/downside movers.
    Returns (upside_movers, downside_movers)
    """
    print(f"  Fetching news for top {top_n} picks...")
    enriched = []
    candidates = [r for r in scored_results if r["score"] >= 35][:top_n]

    for i, stock in enumerate(candidates):
        ticker    = stock["ticker"]
        headlines = fetch_news_sentiment(ticker, max_items=8)
        avg_score = avg_sentiment(headlines)

        # Tag upside/downside news movers
        positive_headlines = [h for h in headlines if h["score"] > 0.20]
        negative_headlines = [h for h in headlines if h["score"] < -0.20]

        enriched.append({
            **stock,
            "headlines":          headlines,
            "avg_sentiment":      avg_score,
            "positive_headlines": positive_headlines,
            "negative_headlines": negative_headlines,
        })

        if i % 5 == 4:
            time.sleep(15)   # respect AV rate limit
        else:
            time.sleep(2)

    # Upside movers: high valuation score + strong positive news
    upside = sorted(
        [e for e in enriched if e["avg_sentiment"] > 0.10 and e["score"] >= 40],
        key=lambda x: (x["score"] * 0.6 + x["avg_sentiment"] * 200),
        reverse=True
    )[:8]

    # Downside/risk movers: any score but strong negative news
    downside = sorted(
        [e for e in enriched if e["avg_sentiment"] < -0.10],
        key=lambda x: x["avg_sentiment"]
    )[:8]

    return upside, downside


# ══════════════════════════════════════════════════════════════
#  EMAIL HTML BUILDER
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
.stock-card{border:1px solid #eaeaea;border-radius:10px;margin-bottom:12px;overflow:hidden;}
.card-top{background:#fafafa;padding:12px 16px;display:flex;
          justify-content:space-between;align-items:flex-start;border-bottom:1px solid #eee;}
.sym{font-size:17px;font-weight:700;}
.cname{font-size:11px;color:#999;margin-top:2px;}
.price{font-size:17px;font-weight:600;text-align:right;}
.country-badge{font-size:10px;padding:2px 7px;border-radius:8px;
               font-weight:600;display:inline-block;margin-left:6px;}
.score-pill{display:inline-block;padding:3px 11px;border-radius:12px;
            font-size:12px;font-weight:700;}
.meta{display:flex;flex-wrap:wrap;gap:14px;padding:10px 16px 4px;}
.meta-item .lbl{font-size:10px;color:#aaa;margin-bottom:1px;}
.meta-item .val{font-size:12px;font-weight:600;}
.bar-wrap{padding:4px 16px 8px;}
.reasons{padding:0 16px 8px;}
.rsn{font-size:12px;color:#444;padding:2px 0;line-height:1.5;}
.news-wrap{padding:4px 16px 10px;}
.news-lbl{font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}
.n-item{padding:5px 0;border-bottom:1px solid #f5f5f5;}
.n-item:last-child{border:none;}
.n-meta{display:flex;align-items:center;gap:6px;margin-bottom:2px;}
.n-date{font-size:10px;color:#bbb;}
.n-badge{font-size:10px;font-weight:600;padding:1px 7px;border-radius:8px;}
.n-title{font-size:12px;color:#333;line-height:1.4;}
.n-title a{color:#1a6dba;text-decoration:none;}
.alert-up{background:#E8F8F2;border-left:4px solid #1D9E75;
          padding:10px 14px;margin:8px 16px;border-radius:6px;font-size:12px;color:#0a5d3e;}
.alert-down{background:#FEF0F0;border-left:4px solid #E24B4A;
            padding:10px 14px;margin:8px 16px;border-radius:6px;font-size:12px;color:#8a1a1a;}
.footer{text-align:center;padding:18px 22px 0;font-size:11px;color:#bbb;line-height:1.6;}
.divider{height:1px;background:#f0f0f0;margin:20px 22px 0;}
.summary-stat{text-align:center;padding:4px 10px;}
.summary-stat .num{font-size:24px;font-weight:700;}
.summary-stat .desc{font-size:11px;color:#888;}
</style>
"""

def score_pill(score):
    if score >= 70:   bg,col = "#D4F5E9","#0A5D3E"
    elif score >= 55: bg,col = "#E6F2D9","#2E6010"
    elif score >= 40: bg,col = "#FEF3DC","#7A4900"
    elif score >= 25: bg,col = "#F0F0F0","#444"
    else:             bg,col = "#FDECEA","#8a1a1a"
    return f'<span class="score-pill" style="background:{bg};color:{col};">{score}/100</span>'

def country_badge(country):
    if country == "CA":
        return '<span class="country-badge" style="background:#FF0000;color:#fff;">🍁 CA</span>'
    return '<span class="country-badge" style="background:#3C3B6E;color:#fff;">🇺🇸 US</span>'

def price_bar(price, low, high):
    if not all([price, low, high]) or high == low: return ""
    pct = max(0, min(100, (price-low)/(high-low)*100))
    col = "#1D9E75" if pct < 35 else "#EF9F27" if pct < 65 else "#E24B4A"
    return f"""<div style="font-size:10px;color:#bbb;margin-bottom:3px;">52-week position — {pct:.0f}% from low</div>
<div style="background:#eee;border-radius:3px;height:5px;">
  <div style="background:{col};width:{pct:.0f}%;height:5px;border-radius:3px;"></div>
</div>"""

def fmt_price(v, currency="USD"):
    sym = "CA$" if currency == "CAD" else "$"
    return f"{sym}{v:,.2f}" if v else "N/A"

def fmt_cap(v):
    if not v: return "N/A"
    if v>=1e12: return f"${v/1e12:.1f}T"
    if v>=1e9:  return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"

def headline_html(h):
    score = h["score"]
    if score > 0.15:   bg,col,icon = "#E8F8F2","#1D9E75","▲"
    elif score < -0.15: bg,col,icon = "#FEF0F0","#E24B4A","▼"
    else:               bg,col,icon = "#F0F0F0","#888","●"
    return f"""<div class="n-item">
  <div class="n-meta">
    <span class="n-date">{h['date']}</span>
    <span class="n-badge" style="background:{bg};color:{col};">{icon} {('Positive' if score>0.15 else 'Negative' if score<-0.15 else 'Neutral')}</span>
    {'<span style="font-size:10px;color:#ccc;">'+h['source']+'</span>' if h.get('source') else ''}
  </div>
  <div class="n-title"><a href="{h['url']}" target="_blank">{h['title']}</a></div>
</div>"""

def stock_card_html(s, show_news=True, max_reasons=4, max_news=5):
    currency = s.get("currency","USD")
    price_str = fmt_price(s.get("price"), currency)
    target_str = fmt_price(s.get("analyst_target"), currency) if s.get("analyst_target") else "N/A"
    pe_str  = f"{s['pe']:.1f}x"  if s.get("pe")  else "N/A"
    pb_str  = f"{s['pb']:.2f}"   if s.get("pb")  else "N/A"
    peg_str = f"{s['peg']:.2f}"  if s.get("peg") else "N/A"
    rg_str  = f"{s['revenue_growth']*100:.0f}%" if s.get("revenue_growth") else "N/A"
    cap_str = fmt_cap(s.get("mktcap"))

    reasons_html = "".join(f'<div class="rsn">• {r}</div>' for r in s.get("reasons",[])[:max_reasons])
    news_html    = "".join(headline_html(h) for h in s.get("headlines",[])[:max_news]) if show_news else ""

    pbar = price_bar(s.get("price"), s.get("52low"), s.get("52high"))
    avg_sent = s.get("avg_sentiment", 0)

    sent_alert = ""
    if avg_sent > 0.15:
        sent_alert = f'<div class="alert-up">🚀 Strong positive news sentiment ({avg_sent:+.2f}) — potential catalyst for upside</div>'
    elif avg_sent < -0.15:
        sent_alert = f'<div class="alert-down">⚠️ Negative news sentiment ({avg_sent:+.2f}) — increased downside risk</div>'

    return f"""<div class="stock-card">
  <div class="card-top">
    <div>
      <div class="sym">{s['ticker']}{country_badge(s.get('country','US'))}</div>
      <div class="cname">{s['name']} · {s.get('sector','—')}</div>
    </div>
    <div>
      <div class="price">{price_str}</div>
      <div style="font-size:11px;color:#aaa;text-align:right;margin-top:2px;">Cap: {cap_str}</div>
      <div style="text-align:right;margin-top:4px;">{score_pill(s['score'])}</div>
    </div>
  </div>
  <div class="meta">
    <div class="meta-item"><div class="lbl">P/E</div><div class="val">{pe_str}</div></div>
    <div class="meta-item"><div class="lbl">P/B</div><div class="val">{pb_str}</div></div>
    <div class="meta-item"><div class="lbl">PEG</div><div class="val">{peg_str}</div></div>
    <div class="meta-item"><div class="lbl">Rev Growth</div><div class="val">{rg_str}</div></div>
    <div class="meta-item"><div class="lbl">Analyst Target</div><div class="val">{target_str}</div></div>
  </div>
  <div class="bar-wrap">{pbar}</div>
  {sent_alert}
  <div class="reasons">{reasons_html}</div>
  {'<div class="news-wrap"><div class="news-lbl">Recent news</div>' + news_html + '</div>' if show_news and news_html else ''}
</div>"""


def build_email(scored, upside_movers, downside_movers):
    now = datetime.now()
    date_str = now.strftime("%A, %B %d %Y  ·  %I:%M %p PT")

    top15    = scored[:15]
    us_top   = [s for s in scored if s.get("country")=="US"][:5]
    ca_top   = [s for s in scored if s.get("country")=="CA"][:5]
    gem_picks = [s for s in scored if s["score"]>=70][:5]

    # Stats for summary bar
    total_scanned = len(scored)
    deeply_uv     = len([s for s in scored if s["score"]>=70])
    potentially_uv = len([s for s in scored if 55<=s["score"]<70])
    ca_count      = len([s for s in scored if s.get("country")=="CA"])

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>📊 Phase 2 · Full Market Scan</h1>
  <p>{date_str}</p>
</div>
<div class="body">

<!-- Summary stats -->
<div style="display:flex;justify-content:space-around;padding:18px 10px 8px;border-bottom:1px solid #f0f0f0;">
  <div class="summary-stat"><div class="num" style="color:#0F6E56;">{total_scanned}</div><div class="desc">Stocks scanned</div></div>
  <div class="summary-stat"><div class="num" style="color:#0F6E56;">{deeply_uv}</div><div class="desc">Deeply undervalued</div></div>
  <div class="summary-stat"><div class="num" style="color:#EF9F27;">{potentially_uv}</div><div class="desc">Worth watching</div></div>
  <div class="summary-stat"><div class="num" style="color:#CC0000;">{ca_count}</div><div class="desc">Canadian stocks</div></div>
</div>
"""

    # ── Top 15 overall ─────────────────────────────────────────
    html += '<div class="section"><div class="section-head">🏆 Top 15 Undervalued — US + Canada Combined</div>'
    for s in top15:
        html += stock_card_html(s, show_news=False, max_reasons=3)
    html += '</div><div class="divider"></div>'

    # ── Deep value gems (score >= 70) ──────────────────────────
    if gem_picks:
        html += '<div class="section"><div class="section-head">🔥 Deep Value Gems (Score 70+)</div>'
        html += '<p style="font-size:12px;color:#888;margin:0 0 10px;">These score highest on all five valuation pillars simultaneously. Highest conviction picks.</p>'
        for s in gem_picks:
            html += stock_card_html(s, show_news=True, max_reasons=5, max_news=4)
        html += '</div><div class="divider"></div>'

    # ── US Top 5 ───────────────────────────────────────────────
    html += '<div class="section"><div class="section-head">🇺🇸 Top 5 US Market Picks</div>'
    for s in us_top:
        html += stock_card_html(s, show_news=False, max_reasons=3)
    html += '</div><div class="divider"></div>'

    # ── Canada Top 5 ──────────────────────────────────────────
    if ca_top:
        html += '<div class="section"><div class="section-head">🍁 Top 5 Canadian Market Picks</div>'
        for s in ca_top:
            html += stock_card_html(s, show_news=False, max_reasons=3)
        html += '</div><div class="divider"></div>'

    # ── Upside news movers ─────────────────────────────────────
    if upside_movers:
        html += '<div class="section"><div class="section-head">🚀 Upside News Catalysts</div>'
        html += '<p style="font-size:12px;color:#888;margin:0 0 10px;">Undervalued stocks with strong positive news momentum — potential near-term catalysts.</p>'
        for s in upside_movers[:5]:
            html += stock_card_html(s, show_news=True, max_reasons=2, max_news=4)
        html += '</div><div class="divider"></div>'

    # ── Downside / risk alerts ─────────────────────────────────
    if downside_movers:
        html += '<div class="section"><div class="section-head">⚠️ Downside Risk Alerts</div>'
        html += '<p style="font-size:12px;color:#888;margin:0 0 10px;">Stocks with significant negative news flow — potential downside risk. Avoid or reduce exposure.</p>'
        for s in downside_movers[:5]:
            html += stock_card_html(s, show_news=True, max_reasons=2, max_news=4)
        html += '</div>'

    html += """
<div class="footer">
  Undervaluation scores are generated using public financial data and sector benchmarks.<br>
  This report is for <strong>research and education only</strong> — not financial advice.<br>
  Always do your own research. Trading involves risk of loss.
</div>
</div></div></body></html>"""
    return html


def build_text_summary(scored, upside_movers, downside_movers):
    now = datetime.now()
    lines = [
        "="*65,
        f"  PHASE 2 MARKET SCAN — {now.strftime('%b %d %Y %I:%M %p PT')}",
        f"  {len(scored)} stocks scanned | "
        f"{len([s for s in scored if s['score']>=70])} deeply undervalued",
        "="*65,
        "\nTOP 15 UNDERVALUED:",
    ]
    for s in scored[:15]:
        upside = ""
        if s.get("analyst_target") and s.get("price"):
            up = (s["analyst_target"] - s["price"]) / s["price"] * 100
            upside = f" | {up:.0f}% analyst upside"
        lines.append(f"  {s['score']:>3}/100  {s['ticker']:<12} {s['name'][:30]:<30}{upside}")

    if upside_movers:
        lines += ["\nUPSIDE NEWS MOVERS:"]
        for s in upside_movers[:5]:
            lines.append(f"  🚀 {s['ticker']} — {s['name']} (sentiment: {s['avg_sentiment']:+.2f})")

    if downside_movers:
        lines += ["\nDOWNSIDE RISK ALERTS:"]
        for s in downside_movers[:5]:
            lines.append(f"  ⚠️  {s['ticker']} — {s['name']} (sentiment: {s['avg_sentiment']:+.2f})")

    lines += ["", "="*65, "  Research only — not financial advice.", "="*65]
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
    print(f"✅ Phase 2 email sent → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def run():
    now = datetime.now()
    print(f"📊 Phase 2 Full Market Scan — {now.strftime('%Y-%m-%d %H:%M PT')}")
    print(f"   US universe:     {sum(len(v) for v in US_UNIVERSE.values())} tickers")
    print(f"   Canada universe: {sum(len(v) for v in CANADA_UNIVERSE.values())} tickers")

    # Step 1: Score every ticker
    scored = run_full_scan()
    print(f"\n  Scan complete: {len(scored)} stocks scored successfully.")

    # Step 2: Fetch news for top picks + classify movers
    upside_movers, downside_movers = fetch_news_for_top_picks(scored, top_n=40)

    # Step 3: Build + send report
    html_body  = build_email(scored, upside_movers, downside_movers)
    text_body  = build_text_summary(scored, upside_movers, downside_movers)
    top_ticker = scored[0]["ticker"] if scored else "—"
    top_score  = scored[0]["score"]  if scored else 0
    n_up       = len(upside_movers)
    n_dn       = len(downside_movers)

    subject = (f"📊 Phase 2 Scan · {now.strftime('%b %d')} · "
               f"Top: {top_ticker} {top_score}/100 · "
               f"🚀{n_up} upside · ⚠️{n_dn} risk alerts")

    print(text_body)

    if EMAIL_SENDER != "your@gmail.com":
        send_email(subject, html_body, text_body)
    else:
        print("⚠️  Set EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
