# ============================================================
#  TRADING BOT — PHASE 3: OPTIONS BRIEF
#
#  Runs at 8:00 AM Pacific via GitHub Actions.
#  Sends ONE email: "Options Brief"
#
#  THREE HARD RULES enforced in this file:
#    1. Stock price must be UNDER $20 USD at runtime
#       (auto-skips anything that moved above $20)
#    2. ONE options contract costs UNDER $80
#       (premium per share < $0.80, since 1 contract = 100 shares)
#    3. NO ETFs — individual stocks only
#
#  GitHub Secrets: ALPHA_VANTAGE_KEY, EMAIL_SENDER,
#                  EMAIL_PASSWORD, EMAIL_RECIPIENT
# ============================================================

import os, sys, smtplib, requests, time
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── SECRETS ────────────────────────────────────────────────────
_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")
AV_KEY          = os.environ.get("ALPHA_VANTAGE_KEY", "demo")

# ══════════════════════════════════════════════════════════════
#  HARD LIMITS  — do not change these
# ══════════════════════════════════════════════════════════════
MAX_STOCK_PRICE    = 20.00   # skip any stock at or above this price at runtime
MAX_CONTRACT_COST  = 80.00   # 1 contract = 100 shares × premium → must be < $80
MAX_PREMIUM        = MAX_CONTRACT_COST / 100  # = $0.80 per share

MIN_DAYS_TO_EXPIRY = 14      # avoid same-week lotto tickets
MAX_DAYS_TO_EXPIRY = 60      # avoid expensive long-dated contracts
MIN_OPEN_INTEREST  = 75      # minimum contracts outstanding (liquidity check)
MIN_VOLUME         = 5       # minimum daily volume

ALERT_DAYS_BEFORE_EARNINGS = 1

# ── Your personal watchlist (included regardless of price filter) ──
MY_WATCHLIST = ["AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "SHOP"]
# Note: watchlist stocks above $20 still get scored and reported,
# but the bot won't find cheap contracts for them at this budget.

# ══════════════════════════════════════════════════════════════
#  OPTIONS UNIVERSE
#  ALL individual stocks — NO ETFs.
#  Verified as typically trading under $20 in 2026.
#  The bot ALWAYS re-checks live price at runtime and skips
#  any ticker that has moved above $20.
# ══════════════════════════════════════════════════════════════

OPTIONS_UNIVERSE = {

    # ── Fintech / Finance ────────────────────────────────────
    # SOFI ~$15: digital bank with growing membership; very active options
    # NU   ~$13: Nu Holdings, Brazilian fintech; strong user growth
    # OPEN ~$2:  Opendoor, real-estate fintech; speculative, high vol options
    # FUBO ~$3:  FuboTV, streaming + sports gambling; high volatility
    "Fintech": ["SOFI", "NU", "OPEN", "FUBO"],

    # ── Tech / Software / AI ────────────────────────────────
    # PATH  ~$14: UiPath, automation AI; growing enterprise adoption
    # HIMS  ~$16: Hims & Hers, telehealth; high growth, active options
    # ZETA  ~$17: Zeta Global, marketing AI; decent options liquidity
    # SNAP  ~$9:  Snapchat; large retail option flow, cheap contracts common
    # IONQ  ~$18: IonQ, quantum computing; speculative, very active
    # RGTI  ~$9:  Rigetti, quantum computing; high volatility options
    # QBTS  ~$7:  D-Wave Quantum; speculative growth
    # APLD  ~$5:  Applied Digital, AI datacenter; cheap and active
    # IREN  ~$4:  Iris Energy, AI/Bitcoin; high vol, cheap options
    # BB    ~$3:  BlackBerry, enterprise security; legacy brand options
    "Tech": ["PATH", "HIMS", "ZETA", "SNAP", "IONQ", "RGTI",
             "QBTS", "APLD", "IREN", "BB"],

    # ── Crypto / Bitcoin Miners ──────────────────────────────
    # RIOT  ~$10: Riot Platforms, largest US Bitcoin miner; huge option volume
    # MARA  ~$14: Marathon Digital; high beta to Bitcoin price, active options
    # CIFR  ~$4:  Cipher Mining; small miner, cheap options, high volatility
    # WULF  ~$5:  TeraWulf; sustainable Bitcoin mining
    # CLSK  ~$9:  CleanSpark; Bitcoin miner with active options chain
    # HUT   ~$11: Hut 8 Mining; Canadian Bitcoin miner listed in US
    "Crypto Mining": ["RIOT", "MARA", "CIFR", "WULF", "CLSK", "HUT"],

    # ── Electric Vehicles / Clean Energy ────────────────────
    # RIVN  ~$12: Rivian; Amazon-backed EV; well-established options market
    # NIO   ~$4:  NIO, Chinese EV maker; huge retail options volume
    # LCID  ~$2:  Lucid Motors; Saudi-backed luxury EV; speculative
    # CHPT  ~$2:  ChargePoint, EV charging; high short interest, active puts
    # QS    ~$5:  QuantumScape, solid-state batteries; pre-revenue, speculative
    # ACHR  ~$9:  Archer Aviation, eVTOL; speculative growth
    # JOBY  ~$5:  Joby Aviation, air taxi; pre-revenue, active options
    # AUR   ~$4:  Aurora Innovation, autonomous trucking; active options
    "EV / Clean Energy": ["RIVN", "NIO", "LCID", "CHPT", "QS", "ACHR", "JOBY", "AUR"],

    # ── Airlines / Travel / Cruise ───────────────────────────
    # AAL   ~$11: American Airlines; one of the most active airline options
    # JBLU  ~$7:  JetBlue; cheap contracts, reasonable liquidity
    # NCLH  ~$17: Norwegian Cruise; recovering travel play, active options
    # CCL   ~$18: Carnival; largest cruise company, liquid options
    "Airlines / Travel": ["AAL", "JBLU", "NCLH", "CCL"],

    # ── Auto / Industrials ───────────────────────────────────
    # F     ~$11: Ford; one of the most liquid option markets in US equities
    # STLA  ~$12: Stellantis; European automaker, trades on NYSE
    "Auto": ["F", "STLA"],

    # ── Telecom / Media ──────────────────────────────────────
    # T     ~$18: AT&T; massive dividend stock, near $20 — high vol options
    # PARA  ~$11: Paramount; streaming + traditional media, speculative
    # WBD   ~$9:  Warner Bros Discovery; deep debt, high volatility options
    # NOK   ~$4:  Nokia; legacy telecom, cheap options, decent OI
    # VOD   ~$9:  Vodafone; UK telecom listed in US, dividend + options
    # GRAB  ~$4:  Grab Holdings, SE Asia super-app; active options
    # BBD   ~$2:  Banco Bradesco; Brazilian bank, cheap options
    "Telecom / Media": ["T", "WBD", "NOK", "VOD", "GRAB", "BBD"],

    # ── Mining / Commodities ─────────────────────────────────
    # CLF   ~$11: Cleveland Cliffs, US steel; high beta, active options
    # BTG   ~$4:  B2Gold, gold miner; cheap options, decent liquidity
    # KGC   ~$11: Kinross Gold; well-established miner, liquid options
    # VALE  ~$10: Vale, Brazilian iron ore; huge miner, active US options
    # RIG   ~$4:  Transocean, offshore drilling; high vol, cheap options
    "Mining / Commodities": ["CLF", "BTG", "KGC", "VALE", "RIG"],

    # ── Healthcare / Biotech ─────────────────────────────────
    # PFE   ~$24: NOTE — above $20, included for contract discovery only
    #             (will be skipped by price filter)
    # MRNA  ~$35: NOTE — above $20, skipped
    # NVAX  ~$9:  Novavax; vaccine company, speculative, active options
    # SNDL  ~$2:  SNDL Inc (formerly cannabis, now pharma retail)
    # ARDS  ~$5:  Aridis Pharma; speculative biotech
    "Biotech": ["NVAX", "SNDL"],

    # ── Retail / Consumer ────────────────────────────────────
    # GME   ~$20: GameStop; massive retail options activity, meme stock
    # BBBY  ~$0.01: bankrupt — excluded
    # WBA   ~$10: Walgreens; turnaround story, liquid options
    "Retail": ["GME"],

    # ── Quantum / Emerging Tech ──────────────────────────────
    # QUBT  ~$8:  Quantum Computing Inc; speculative
    "Emerging Tech": ["QUBT"],
}

# Flatten universe to a deduplicated list
def build_universe():
    seen = set()
    result = []
    for sector, tickers in OPTIONS_UNIVERSE.items():
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append((t, sector))
    return result

# ══════════════════════════════════════════════════════════════
#  SECTOR P/E BENCHMARKS (for scoring)
# ══════════════════════════════════════════════════════════════
SECTOR_PE = {
    "Technology":28,"Fintech":22,"Consumer Cyclical":22,
    "Consumer Defensive":20,"Healthcare":18,"Financials":13,
    "Financial Services":13,"Energy":11,"Industrials":19,
    "Communication Services":16,"Real Estate":30,"Utilities":17,
    "Basic Materials":14,"Mining":14,"Consumer":20,"Auto":15,
    "Airlines / Travel":18,"Biotech":30,"Retail":20,
    "Telecom / Media":16,"EV / Clean Energy":25,
    "Crypto Mining":20,"Emerging Tech":30,"Unknown":18,
}

# ── Install deps ───────────────────────────────────────────────
def _install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:    import yfinance as yf
except: _install("yfinance"); import yfinance as yf

try:    from textblob import TextBlob
except: _install("textblob"); from textblob import TextBlob

try:    import pandas as pd
except: _install("pandas"); import pandas as pd


# ══════════════════════════════════════════════════════════════
#  DATA LAYER
# ══════════════════════════════════════════════════════════════

def get_signals(ticker, sector_hint="Unknown"):
    """
    Pulls all data needed for PUT/CALL scoring.
    Returns None if stock is at or above $20 (hard rule).
    """
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")

        if not price or price <= 0:
            return None

        # ── HARD RULE 1: skip if price >= $20 ──────────────────
        if price >= MAX_STOCK_PRICE:
            print(f"    {ticker}: ${price:.2f} — SKIPPED (above ${MAX_STOCK_PRICE:.0f})")
            return None

        low52  = info.get("fiftyTwoWeekLow")
        high52 = info.get("fiftyTwoWeekHigh")
        pct_from_low = None
        if low52 and high52 and high52 > low52:
            pct_from_low = (price - low52) / (high52 - low52) * 100

        target     = info.get("targetMeanPrice")
        n_analysts = info.get("numberOfAnalystOpinions") or 0
        analyst_upside = None
        if target and price > 0 and n_analysts >= 2:  # lower bar for sub-$20 stocks
            analyst_upside = (target - price) / price * 100

        # Earnings date
        earn_date, days_to_earn = None, None
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                if "Earnings Date" in cal.index:
                    ed = cal.loc["Earnings Date"].iloc[0]
                elif hasattr(cal,"columns") and "Earnings Date" in cal.columns:
                    ed = cal["Earnings Date"].iloc[0]
                else: ed = None
                if ed is not None:
                    if hasattr(ed,"date"): ed = ed.date()
                    earn_date = ed
                    days_to_earn = (ed - datetime.today().date()).days
        except: pass

        # News sentiment
        headlines = []
        try:
            url  = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
                    f"&tickers={ticker}&limit=8&apikey={AV_KEY}")
            data = requests.get(url, timeout=10).json()
            for item in data.get("feed",[])[:8]:
                title = item.get("title","")
                score = None
                for ts in item.get("ticker_sentiment",[]):
                    if ts.get("ticker","").upper() == ticker.upper():
                        score = float(ts.get("ticker_sentiment_score",0)); break
                if score is None: score = TextBlob(title).sentiment.polarity
                headlines.append({
                    "title": title[:100], "score": score,
                    "url":   item.get("url","#"),
                    "date":  item.get("time_published","")[:8]
                })
        except: pass

        avg_sent = round(sum(h["score"] for h in headlines)/len(headlines),3) if headlines else 0.0

        return {
            "ticker":          ticker,
            "name":            info.get("shortName", ticker),
            "sector":          info.get("sector") or sector_hint,
            "price":           price,
            "pe":              info.get("trailingPE"),
            "fwd_pe":          info.get("forwardPE"),
            "pb":              info.get("priceToBook"),
            "beta":            info.get("beta"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "debt_equity":     info.get("debtToEquity"),
            "free_cashflow":   info.get("freeCashflow"),
            "mktcap":          info.get("marketCap"),
            "52low":           low52,
            "52high":          high52,
            "pct_from_low":    pct_from_low,
            "analyst_target":  target,
            "analyst_upside":  analyst_upside,
            "n_analysts":      n_analysts,
            "earn_date":       earn_date,
            "days_to_earn":    days_to_earn,
            "avg_sentiment":   avg_sent,
            "headlines":       headlines[:5],
        }
    except Exception as e:
        print(f"    {ticker} error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  PUT vs CALL SCORING ENGINE
# ══════════════════════════════════════════════════════════════

def score_put_call(sig):
    """
    Score -100 (strong PUT) to +100 (strong CALL).
    Every signal includes a plain-English reason.
    """
    if not sig: return 0,"NEUTRAL","⚪ SKIP","#555","#F0F0F0","Mixed signals.",[]

    score   = 0
    reasons = []
    sp      = SECTOR_PE.get(sig.get("sector","Unknown"), 18)

    # ── 1. 52-week position ─────────────────────────────────────
    pfl = sig.get("pct_from_low")
    if pfl is not None:
        if pfl < 15:
            score += 25
            reasons.append({"side":"CALL","icon":"📉→📈","title":"Near 52-week low",
                "why": f"Stock is only {pfl:.0f}% above its 52-week low — lots of room to bounce. Good CALL setup."})
        elif pfl < 35:
            score += 12
            reasons.append({"side":"CALL","icon":"📊","title":"Lower half of 52-week range",
                "why": f"At {pfl:.0f}% from 52-week low — more upside room than downside."})
        elif pfl > 85:
            score -= 25
            reasons.append({"side":"PUT","icon":"⚠️","title":"Near 52-week high",
                "why": f"At {pfl:.0f}% above 52-week low — near the top, gravity often pulls stocks back. PUT setup."})
        elif pfl > 65:
            score -= 12
            reasons.append({"side":"PUT","icon":"📊","title":"Upper half of 52-week range",
                "why": f"At {pfl:.0f}% from 52-week low — more downside risk than upside from here."})

    # ── 2. Analyst price target ─────────────────────────────────
    au = sig.get("analyst_upside")
    na = sig.get("n_analysts", 0)
    if au is not None and na >= 2:
        if au > 35:
            score += 25
            reasons.append({"side":"CALL","icon":"🎯","title":f"Analysts see {au:.0f}% upside ({na} analysts)",
                "why": f"Consensus target ${sig['analyst_target']:.2f} is {au:.0f}% above the current ${sig['price']:.2f}. Strong CALL signal."})
        elif au > 15:
            score += 14
            reasons.append({"side":"CALL","icon":"🎯","title":f"Analyst upside: {au:.0f}%",
                "why": f"{na} analysts targeting ${sig['analyst_target']:.2f}."})
        elif au < -10:
            score -= 20
            reasons.append({"side":"PUT","icon":"🎯","title":f"Analysts below current price: {au:.0f}%",
                "why": f"Analysts expect the stock to FALL — PUT signal."})

    # ── 3. News sentiment ────────────────────────────────────────
    sent = sig.get("avg_sentiment", 0)
    if sent > 0.20:
        score += 20
        reasons.append({"side":"CALL","icon":"📰","title":f"Strong positive news ({sent:+.2f})",
            "why": "Headlines are overwhelmingly positive — buying pressure likely to push price up."})
    elif sent > 0.10:
        score += 9
        reasons.append({"side":"CALL","icon":"📰","title":f"Positive sentiment ({sent:+.2f})",
            "why": "More positive than negative headlines — mild bullish signal."})
    elif sent < -0.20:
        score -= 22
        reasons.append({"side":"PUT","icon":"📰","title":f"Negative news flow ({sent:+.2f})",
            "why": "Headlines are predominantly negative — selling pressure likely to push price down. PUT setup."})
    elif sent < -0.10:
        score -= 10
        reasons.append({"side":"PUT","icon":"📰","title":f"Slightly negative sentiment ({sent:+.2f})",
            "why": "More negative than positive headlines — mild bearish signal."})

    # ── 4. Forward P/E vs trailing (earnings trajectory) ────────
    fwd = sig.get("fwd_pe"); pe = sig.get("pe")
    if fwd and pe and 0 < fwd < 300 and 0 < pe < 300:
        impr = (pe - fwd) / pe
        if impr > 0.25:
            score += 18
            reasons.append({"side":"CALL","icon":"⚡","title":"Earnings accelerating",
                "why": f"Fwd P/E {fwd:.1f}x vs trailing {pe:.1f}x — earnings expected to GROW {impr*100:.0f}%. Bullish for CALL."})
        elif impr > 0.10:
            score += 9
            reasons.append({"side":"CALL","icon":"📈","title":"Improving earnings outlook",
                "why": f"Fwd P/E {fwd:.1f}x improving vs trailing {pe:.1f}x."})
        elif impr < -0.20:
            score -= 18
            reasons.append({"side":"PUT","icon":"📉","title":"Earnings shrinking",
                "why": f"Fwd P/E {fwd:.1f}x is HIGHER than trailing {pe:.1f}x — earnings expected to decline. PUT signal."})

    # ── 5. Revenue growth ────────────────────────────────────────
    rg = sig.get("revenue_growth")
    if rg is not None:
        if rg > 0.20:
            score += 15
            reasons.append({"side":"CALL","icon":"💰","title":f"Revenue growing {rg*100:.0f}% YoY",
                "why": f"Fast revenue growth attracts buyers — bullish CALL signal."})
        elif rg > 0.05:
            score += 6
            reasons.append({"side":"CALL","icon":"💰","title":f"Revenue up {rg*100:.0f}% YoY",
                "why": "Steady growth — mild bullish signal."})
        elif rg < -0.10:
            score -= 18
            reasons.append({"side":"PUT","icon":"📉","title":f"Revenue declining {abs(rg)*100:.0f}%",
                "why": "Shrinking revenue usually leads to falling stock prices — PUT signal."})
        elif rg < 0:
            score -= 7
            reasons.append({"side":"PUT","icon":"📉","title":f"Revenue slightly negative {abs(rg)*100:.0f}%",
                "why": "Mild revenue decline — slight bearish signal."})

    # ── 6. Earnings catalyst check ───────────────────────────────
    dte = sig.get("days_to_earn")
    if dte is not None and 0 < dte <= 21:
        if score > 10:
            score += 12
            reasons.append({"side":"CALL","icon":"📅","title":f"Earnings in {dte} days — bullish setup",
                "why": f"Earnings {dte} days away with positive signals. A beat could send the stock up fast. "
                       "⚠️ Close the option BEFORE earnings — premiums collapse right after (IV crush)."})
        elif score < -10:
            score -= 12
            reasons.append({"side":"PUT","icon":"📅","title":f"Earnings in {dte} days — bearish setup",
                "why": f"Earnings in {dte} days with negative signals. A miss could cause a sharp drop. "
                       "⚠️ Same IV crush warning — close BEFORE the report."})
        else:
            reasons.append({"side":"NEUTRAL","icon":"📅","title":f"Earnings in {dte} days — unclear",
                "why": "Signals too mixed. Consider waiting until after earnings when premiums are cheaper."})

    # ── 7. Valuation check ───────────────────────────────────────
    pe = sig.get("pe")
    if pe and 0 < pe < 500:
        if pe > sp * 3:
            score -= 14
            reasons.append({"side":"PUT","icon":"💸","title":f"Extremely expensive P/E {pe:.0f}x (sector: {sp}x)",
                "why": "3× the sector P/E. Overvalued stocks drop fast when growth misses."})
        elif pe < sp * 0.5:
            score += 11
            reasons.append({"side":"CALL","icon":"💎","title":f"Cheap P/E {pe:.0f}x vs sector {sp}x",
                "why": "Trading at half the sector P/E — undervalued with rerating potential. CALL signal."})

    # ── 8. High debt risk ────────────────────────────────────────
    de = sig.get("debt_equity")
    if de is not None and de > 300:
        score -= 10
        reasons.append({"side":"PUT","icon":"⚠️","title":f"Very high debt (D/E: {de:.0f}%)",
            "why": "Heavy debt load is dangerous if revenue slips or rates stay high."})

    score = max(-100, min(100, score))

    if score >= 30:
        v,vl,vc,vbg = "CALL","📈 BUY CALL","#0F6E56","#D5F5EA"
        ve = ("Majority of signals point UP. A CALL option profits if the stock rises. "
              "You pay the premium upfront — that's your maximum loss. "
              "Your profit is unlimited if the stock runs.")
    elif score >= 10:
        v,vl,vc,vbg = "CALL","🟡 LEAN CALL","#3B6D11","#E5F2DA"
        ve = ("More bullish than bearish, but not a strong conviction. "
              "If you trade this, keep size small — use 1 contract only.")
    elif score <= -30:
        v,vl,vc,vbg = "PUT","📉 BUY PUT","#8a0000","#FDECEA"
        ve = ("Majority of signals point DOWN. A PUT option profits if the stock falls. "
              "You pay the premium upfront — maximum loss is what you paid. "
              "The bigger the drop, the more your PUT is worth.")
    elif score <= -10:
        v,vl,vc,vbg = "PUT","🟡 LEAN PUT","#7A4900","#FEF3DA"
        ve = "More bearish than bullish, but mixed. Keep size small — 1 contract only."
    else:
        v,vl,vc,vbg = "NEUTRAL","⚪ SKIP THIS","#555","#F0F0F0"
        ve = ("Signals are too mixed. The best options trade is sometimes no trade. "
              "Waiting for a clearer setup saves your money for better opportunities.")

    return score, v, vl, vc, vbg, ve, reasons


# ══════════════════════════════════════════════════════════════
#  OPTIONS CHAIN FETCHER
#  Finds contracts under $80 per contract ($0.80/share)
# ══════════════════════════════════════════════════════════════

def find_cheap_contracts(ticker, direction, price):
    """
    Scans the options chain for contracts where:
      - 1 contract (100 shares × premium) costs < $80
      - Expiry is 14–60 days away
      - Open interest >= 75
      - Strike is within 30% of current price
    """
    contracts = []
    today = date.today()

    try:
        stock       = yf.Ticker(ticker)
        expiry_list = stock.options
        if not expiry_list:
            return []

        # Find expiries in the target window
        target_expiries = []
        for exp_str in expiry_list:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if MIN_DAYS_TO_EXPIRY <= dte <= MAX_DAYS_TO_EXPIRY:
                target_expiries.append((exp_str, dte))

        if not target_expiries:
            return []

        for exp_str, dte in target_expiries[:4]:
            try:
                chain = stock.option_chain(exp_str)
                df = chain.calls if direction == "CALL" else chain.puts

                if df is None or df.empty:
                    continue

                # ── HARD RULE 2: contract must cost < $80 ────────
                filtered = df[
                    (df["ask"] > 0.01) &
                    (df["ask"] <= MAX_PREMIUM) &      # ← $0.80 max per share
                    (df["openInterest"] >= MIN_OPEN_INTEREST) &
                    (df["volume"].fillna(0) >= MIN_VOLUME) &
                    (df["strike"] >= price * 0.70) &  # within 30% below
                    (df["strike"] <= price * 1.35)    # within 35% above
                ].copy()

                if filtered.empty:
                    continue

                filtered["atm_dist"] = abs(filtered["strike"] - price) / price
                filtered["score_val"] = (
                    (1 / (filtered["ask"] + 0.01)) * 0.35 +
                    (filtered["openInterest"] / 5000) * 0.40 +
                    (1 / (filtered["atm_dist"] + 0.05)) * 0.25
                )
                filtered = filtered.sort_values("score_val", ascending=False)

                for _, row in filtered.head(2).iterrows():
                    contract_cost = round(row["ask"] * 100, 2)  # actual $ you pay
                    if contract_cost > MAX_CONTRACT_COST:
                        continue  # double-check hard limit

                    moneyness = "in-the-money" if (
                        (direction=="CALL" and row["strike"] < price) or
                        (direction=="PUT"  and row["strike"] > price)
                    ) else "out-of-the-money"

                    contracts.append({
                        "expiry":       exp_str,
                        "dte":          dte,
                        "strike":       row["strike"],
                        "premium":      row["ask"],
                        "contract_cost": contract_cost,
                        "open_int":     int(row.get("openInterest", 0)),
                        "volume":       int(row.get("volume", 0) or 0),
                        "iv":           row.get("impliedVolatility"),
                        "delta":        row.get("delta"),
                        "moneyness":    moneyness,
                    })
            except:
                continue

    except Exception as e:
        print(f"    {ticker} options chain error: {e}")

    contracts.sort(key=lambda x: x["contract_cost"])
    return contracts[:3]


# ══════════════════════════════════════════════════════════════
#  EMAIL HTML
# ══════════════════════════════════════════════════════════════

CSS = """<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#f0f0f0;margin:0;padding:14px;color:#1a1a1a;}
.wrap{max-width:660px;margin:0 auto;}
.header{padding:22px 24px;border-radius:12px 12px 0 0;
        background:linear-gradient(135deg,#14104a,#241e8a);}
.header h1{margin:0;font-size:20px;font-weight:700;color:#fff;}
.header p{margin:5px 0 0;font-size:13px;color:rgba(255,255,255,0.65);}
.body{background:#fff;border:1px solid #ddd;border-top:none;
      border-radius:0 0 12px 12px;padding-bottom:26px;}
.stat-row{display:flex;justify-content:space-around;padding:14px 8px 8px;
          border-bottom:1px solid #f0f0f0;}
.stat .num{font-size:22px;font-weight:700;}
.stat .desc{font-size:11px;color:#aaa;}
.section{padding:16px 18px 0;}
.sec-title{font-size:11px;font-weight:700;color:#666;text-transform:uppercase;
           letter-spacing:.8px;padding-bottom:7px;border-bottom:1px solid #eee;margin-bottom:10px;}
.card{border:1px solid #e8e8e8;border-radius:10px;margin-bottom:12px;overflow:hidden;}
.card-head{background:#f7f7f7;padding:11px 14px;border-bottom:1px solid #eee;
           display:flex;justify-content:space-between;align-items:flex-start;}
.sym{font-size:16px;font-weight:700;}
.cname{font-size:11px;color:#999;margin-top:2px;}
.price-block{text-align:right;}
.price{font-size:16px;font-weight:700;}
.price-note{font-size:10px;color:#bbb;margin-top:2px;}
.verdict-box{margin:10px 14px 0;padding:11px 13px;border-radius:8px;}
.verdict-lbl{font-size:15px;font-weight:700;margin-bottom:4px;}
.verdict-why{font-size:12px;line-height:1.6;}
.bar-wrap{padding:8px 14px 0;}
.bar-row{background:#eee;border-radius:4px;height:7px;}
.bar-labels{display:flex;justify-content:space-between;font-size:10px;color:#bbb;margin-top:2px;}
.signals{padding:2px 14px 6px;}
.sig-item{padding:7px 0;border-bottom:1px solid #f4f4f4;}
.sig-item:last-child{border:none;}
.sig-head{display:flex;align-items:center;gap:7px;margin-bottom:2px;}
.badge{font-size:10px;font-weight:700;padding:1px 7px;border-radius:6px;}
.sig-title{font-size:12px;font-weight:600;color:#333;}
.sig-why{font-size:12px;color:#555;line-height:1.5;}
.contracts{padding:2px 14px 10px;}
.c-lbl{font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px;}
.c-row{background:#fafafa;border:1px solid #eee;border-radius:8px;
       padding:9px 12px;margin-bottom:6px;}
.c-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}
.c-type{font-size:12px;font-weight:700;}
.c-cost{font-size:14px;font-weight:700;}
.c-meta{font-size:11px;color:#888;display:flex;gap:10px;flex-wrap:wrap;}
.badge-sm{font-size:10px;font-weight:600;padding:1px 6px;border-radius:5px;}
.news-section{padding:2px 14px 8px;}
.news-lbl{font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;}
.n-item{padding:5px 0;border-bottom:1px solid #f5f5f5;}
.n-item:last-child{border:none;}
.n-row{display:flex;gap:6px;align-items:center;margin-bottom:2px;}
.n-date{font-size:10px;color:#ccc;}
.n-badge{font-size:10px;font-weight:600;padding:1px 6px;border-radius:5px;}
.n-title{font-size:12px;color:#333;line-height:1.4;}
.n-title a{color:#185FA5;text-decoration:none;}
.primer{background:#F7F7F7;border:1px solid #EBEBEB;border-radius:9px;
        padding:14px 16px;margin:14px 18px 0;font-size:12px;color:#444;line-height:1.7;}
.primer h3{margin:0 0 10px;font-size:13px;color:#222;}
.primer strong{color:#222;}
.risk-banner{background:#FFF0E6;border-left:4px solid #D85A30;border-radius:0 7px 7px 0;
             padding:9px 13px;margin:10px 18px 0;font-size:12px;color:#6B2800;font-weight:600;}
.divider{height:1px;background:#f0f0f0;margin:16px 18px 0;}
.skip-section{padding:6px 18px 12px;font-size:12px;color:#999;}
.footer{text-align:center;padding:14px 18px 0;font-size:11px;color:#bbb;line-height:1.7;}
</style>"""

def fmt(v, prefix="$"):
    return f"{prefix}{v:,.2f}" if isinstance(v,(int,float)) else "N/A"
def fmt_cap(v):
    if not v: return "N/A"
    if v>=1e12: return f"${v/1e12:.1f}T"
    if v>=1e9:  return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"

def score_bar(score):
    pct = (score + 100) / 2
    col = "#0F6E56" if score>=20 else "#3B6D11" if score>=5 else "#A32D2D" if score<=-20 else "#7A4900" if score<=-5 else "#888"
    return f"""<div class="bar-wrap">
  <div style="font-size:10px;color:#bbb;margin-bottom:2px;">Signal strength: {score:+d}/100</div>
  <div class="bar-row"><div style="background:{col};width:{pct:.0f}%;height:7px;border-radius:4px;"></div></div>
  <div class="bar-labels"><span>← Strong PUT</span><span>Strong CALL →</span></div>
</div>"""

def badge(side):
    if side=="CALL":    return '<span class="badge" style="background:#D5F5EA;color:#0F6E56;">CALL</span>'
    elif side=="PUT":   return '<span class="badge" style="background:#FDECEA;color:#8a0000;">PUT</span>'
    return                     '<span class="badge" style="background:#F0F0F0;color:#555;">NEUTRAL</span>'

def news_items(headlines):
    out = ""
    for h in headlines[:4]:
        s = h["score"]
        bg,c,icon,lbl = ("#E6F8F2","#1D9E75","▲","Positive") if s>0.15 else \
                        ("#FEF0F0","#E24B4A","▼","Negative") if s<-0.15 else \
                        ("#F0F0F0","#888","●","Neutral")
        pub = h.get("date","")
        try: pub = datetime.strptime(pub,"%Y%m%d").strftime("%b %d")
        except: pass
        out += f"""<div class="n-item">
  <div class="n-row"><span class="n-date">{pub}</span>
  <span class="n-badge" style="background:{bg};color:{c};">{icon} {lbl}</span></div>
  <div class="n-title"><a href="{h.get('url','#')}">{h.get('title','')}</a></div>
</div>"""
    return out

def contract_html(c, direction):
    col  = "#0F6E56" if direction=="CALL" else "#A32D2D"
    bg   = "#D5F5EA" if direction=="CALL" else "#FDECEA"
    icon = "📈" if direction=="CALL" else "📉"
    iv   = f"{c['iv']*100:.0f}%" if c.get("iv") else "N/A"
    dlt  = f"{c['delta']:.2f}" if c.get("delta") else "N/A"
    warn = f'<div style="font-size:11px;color:#7A4900;margin-top:4px;">⚠️ Only {c["dte"]}d to expiry — high time decay</div>' if c["dte"]<=21 else ""
    return f"""<div class="c-row">
  <div class="c-head">
    <div><span class="c-type" style="color:{col};">{icon} {direction} ${c['strike']:.2f} strike</span>
    <span style="font-size:11px;color:#bbb;margin-left:7px;">Exp {c['expiry']} · {c['dte']}d</span></div>
    <div><span class="c-cost" style="color:{col};">${c['contract_cost']:.2f} / contract</span></div>
  </div>
  <div class="c-meta">
    <span>Ask ${c['premium']:.2f}/share</span>
    <span>OI: {c['open_int']:,}</span>
    <span>Vol: {c['volume']:,}</span>
    <span>IV: {iv}</span>
    <span>Δ {dlt}</span>
    <span class="badge-sm" style="background:{bg};color:{col};">{c['moneyness']}</span>
  </div>{warn}
</div>"""

def stock_card(r):
    sig  = r["signals"]
    sc   = r["score"]
    verd = r["verdict"]
    vlbl = r["verdict_label"]
    vcol = r["verdict_color"]
    vbg  = r["verdict_bg"]
    vexp = r["verdict_explanation"]
    reas = r["reasons"]
    cons = r["contracts"]

    price = sig.get("price",0)
    pfl   = sig.get("pct_from_low")
    pfl_s = f"{pfl:.0f}% above 52wk low" if pfl is not None else ""
    au    = sig.get("analyst_upside")
    au_s  = f" · {au:+.0f}% analyst target" if au is not None else ""

    sigs_html = ""
    for rsn in reas:
        sigs_html += f"""<div class="sig-item">
  <div class="sig-head">{badge(rsn['side'])}<span class="sig-title">{rsn['icon']} {rsn['title']}</span></div>
  <div class="sig-why">{rsn['why']}</div>
</div>"""

    cons_html = ""
    if cons:
        cons_html = '<div class="contracts"><div class="c-lbl">Contracts under $80 — found these:</div>'
        for c in cons:
            cons_html += contract_html(c, verd if verd != "NEUTRAL" else "CALL")
        cons_html += '</div>'
    else:
        cons_html = '<div style="padding:6px 14px 8px;font-size:12px;color:#bbb;">No contracts found under $80 for this expiry window — check again tomorrow or try a different strike range.</div>'

    earn_html = ""
    dte = sig.get("days_to_earn")
    if dte is not None and 0 < dte <= 30:
        earn_html = f'<div style="padding:3px 14px 0;font-size:11px;color:#7A4900;">📅 Earnings in {dte} days ({sig["earn_date"]}) — IV elevated</div>'

    return f"""<div class="card">
  <div class="card-head">
    <div><div class="sym">{sig['ticker']}</div>
    <div class="cname">{sig['name']} · {sig['sector']}</div></div>
    <div class="price-block">
      <div class="price" style="color:#222;">${price:.2f}</div>
      <div class="price-note">{pfl_s}{au_s}</div>
      <div class="price-note">Cap {fmt_cap(sig.get('mktcap'))}</div>
    </div>
  </div>
  <div class="verdict-box" style="background:{vbg};border-left:4px solid {vcol};">
    <div class="verdict-lbl" style="color:{vcol};">{vlbl}</div>
    <div class="verdict-why">{vexp}</div>
  </div>
  {score_bar(sc)}
  {earn_html}
  <div class="signals"><div style="font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;padding:6px 0 3px;">Signal breakdown — why this verdict</div>
  {sigs_html}</div>
  {cons_html}
  {'<div class="news-section"><div class="news-lbl">Recent headlines</div>' + news_items(sig.get('headlines',[])) + '</div>' if sig.get('headlines') else ''}
</div>"""

PRIMER = """<div class="primer">
<h3>📚 Options 101 — What you need to know before trading</h3>
<p><strong>CALL</strong> — you believe the stock goes <span style="color:#0F6E56;font-weight:700;">UP</span>. You pay a premium for the right to buy 100 shares at the strike price. If the stock rises above strike, your CALL gains value.</p>
<p><strong>PUT</strong> — you believe the stock goes <span style="color:#A32D2D;font-weight:700;">DOWN</span>. You pay a premium for the right to sell 100 shares at the strike. If the stock falls below strike, your PUT gains value.</p>
<p><strong>Contract cost</strong> = ask price × 100 shares. All contracts shown here cost <strong>under $80 each</strong>. That is your maximum loss on 1 contract.</p>
<p><strong>Out-of-the-money (OTM)</strong> — the stock hasn't hit the strike yet. Cheaper, but requires a bigger move to profit. Most OTM cheap options expire worthless.</p>
<p><strong>IV crush ⚠️</strong> — implied volatility (and therefore premium) spikes before earnings and collapses right after. Never buy options the day before earnings expecting to hold through them. Close before the report.</p>
<p style="color:#A32D2D;font-weight:600;">Most cheap options expire worthless. Only risk money you can afford to lose entirely. Start with 1 contract to learn the mechanics before risking more.</p>
</div>"""

def build_email(results, skipped_above_20):
    now      = datetime.now()
    date_str = now.strftime("%A, %B %d %Y  ·  %I:%M %p PT")

    calls     = [r for r in results if r["verdict"]=="CALL"]
    puts      = [r for r in results if r["verdict"]=="PUT"]
    neutral   = [r for r in results if r["verdict"]=="NEUTRAL"]
    has_cons  = [r for r in results if r["contracts"]]
    strong    = [r for r in results if abs(r["score"])>=30]
    s_calls   = [r for r in calls  if r["score"]>=30]
    s_puts    = [r for r in puts   if r["score"]<=-30]
    lean      = [r for r in results if 10<=abs(r["score"])<30]

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header">
  <h1>📊 Options Brief</h1>
  <p>{date_str} · stocks under $20 · contracts under $80</p>
</div>
<div class="body">
<div class="stat-row">
  <div class="stat"><div class="num" style="color:#0F6E56;">{len(calls)}</div><div class="desc">CALL setups 📈</div></div>
  <div class="stat"><div class="num" style="color:#A32D2D;">{len(puts)}</div><div class="desc">PUT setups 📉</div></div>
  <div class="stat"><div class="num" style="color:#185FA5;">{len(has_cons)}</div><div class="desc">Under $80 contracts</div></div>
  <div class="stat"><div class="num" style="color:#7A4900;">{len(skipped_above_20)}</div><div class="desc">Skipped (above $20)</div></div>
</div>"""

    if skipped_above_20:
        html += f'<div class="risk-banner">⛔ {len(skipped_above_20)} tickers automatically skipped — price moved above $20: {", ".join(skipped_above_20)}</div>'

    html += PRIMER
    html += '<div class="risk-banner">⚠️ Options trading is high risk. Most cheap contracts expire worthless. This is for education only — not financial advice. Never risk more than you can afford to lose completely.</div>'

    if s_calls:
        html += '<div class="section"><div class="sec-title">📈 Strong CALL Setups — Bullish Signals</div>'
        for r in s_calls: html += stock_card(r)
        html += '</div><div class="divider"></div>'

    if s_puts:
        html += '<div class="section"><div class="sec-title">📉 Strong PUT Setups — Bearish Signals</div>'
        for r in s_puts: html += stock_card(r)
        html += '</div><div class="divider"></div>'

    if lean:
        html += '<div class="section"><div class="sec-title">🟡 Moderate Setups — Weaker Signal</div>'
        for r in lean: html += stock_card(r)
        html += '</div><div class="divider"></div>'

    if neutral:
        skip_list = ", ".join(r["signals"]["ticker"] for r in neutral)
        html += f'<div class="section"><div class="sec-title">⚪ Skip — No Clear Direction</div>'
        html += f'<div class="skip-section">Signals too mixed to have conviction: {skip_list}. Skipping is a valid strategy — it preserves your capital for better setups.</div>'
        html += '</div>'

    html += """<div class="footer">
<strong>Options Brief is for research and education only — NOT financial advice.</strong><br>
All contracts shown cost under $80. All stocks verified under $20 at scan time.<br>
Options involve high risk — most cheap contracts expire worthless.<br>
Paper trade first. Never risk money you cannot afford to lose entirely.
</div></div></div></body></html>"""
    return html

def build_text(results, skipped):
    now = datetime.now()
    lines = ["="*62,
             f"  OPTIONS BRIEF — {now.strftime('%b %d %Y %I:%M %p PT')}",
             f"  Stocks < $20  ·  Contracts < $80 per contract",
             "="*62]
    if skipped:
        lines.append(f"  SKIPPED (above $20): {', '.join(skipped)}")
    for r in results:
        sig = r["signals"]
        lines.append(f"\n  {sig['ticker']:<8} ${sig['price']:.2f}  →  {r['verdict_label']} (score {r['score']:+d})")
        for rsn in r["reasons"][:2]:
            lines.append(f"    {rsn['icon']} [{rsn['side']}] {rsn['title']}")
        for c in r["contracts"][:1]:
            lines.append(f"    Contract: ${c['contract_cost']:.2f} total · strike ${c['strike']:.2f} · exp {c['expiry']}")
    lines += ["","="*62,"  Research only — not financial advice.","="*62]
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
    print(f"✅ Options Brief → {EMAIL_RECIPIENT}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def run():
    now = datetime.now()
    print(f"📊 Options Brief — {now.strftime('%Y-%m-%d %H:%M PT')}")
    print(f"   Rules: stock < ${MAX_STOCK_PRICE:.0f}  ·  contract < ${MAX_CONTRACT_COST:.0f}  ·  no ETFs")

    universe = build_universe()
    # Add watchlist tickers not already in universe
    in_univ  = {t for t,s in universe}
    extra    = [(t,"Watchlist") for t in MY_WATCHLIST if t not in in_univ]
    all_tickers = extra + universe

    print(f"   Scanning {len(all_tickers)} tickers...")

    results        = []
    skipped_above  = []  # tickers that moved above $20
    req_count      = 0

    for i, (ticker, sector) in enumerate(all_tickers):
        print(f"  [{i+1}/{len(all_tickers)}] {ticker}...", end=" ")

        sig = get_signals(ticker, sector)
        if sig is None:
            # Check if it was skipped due to price or just no data
            try:
                p = yf.Ticker(ticker).info.get("currentPrice") or \
                    yf.Ticker(ticker).info.get("regularMarketPrice", 0)
                if p and p >= MAX_STOCK_PRICE:
                    skipped_above.append(f"{ticker}(${p:.0f})")
            except: pass
            req_count += 1
            if req_count % 5 == 0: time.sleep(15)
            else: time.sleep(1)
            continue

        sc, verdict, vlbl, vcol, vbg, vexp, reasons = score_put_call(sig)
        print(f"${sig['price']:.2f} → {vlbl} ({sc:+d})")

        contracts = []
        if verdict != "NEUTRAL":
            contracts = find_cheap_contracts(ticker, verdict, sig["price"])
            print(f"    Found {len(contracts)} contracts under ${MAX_CONTRACT_COST:.0f}")

        results.append({
            "signals":              sig,
            "score":                sc,
            "verdict":              verdict,
            "verdict_label":        vlbl,
            "verdict_color":        vcol,
            "verdict_bg":           vbg,
            "verdict_explanation":  vexp,
            "reasons":              reasons,
            "contracts":            contracts,
        })

        req_count += 1
        if req_count % 5 == 0: time.sleep(15)
        else: time.sleep(2)

    # Sort: strong signal + has contracts first
    results.sort(key=lambda x: (len(x["contracts"])>0, abs(x["score"])), reverse=True)

    html_body = build_email(results, skipped_above)
    text_body = build_text(results, skipped_above)

    calls  = len([r for r in results if r["verdict"]=="CALL"])
    puts   = len([r for r in results if r["verdict"]=="PUT"])
    cheap  = len([r for r in results if r["contracts"]])
    strong = len([r for r in results if abs(r["score"])>=30])

    subject = (f"📊 Options Brief · {now.strftime('%b %d')} | "
               f"📈{calls} CALL · 📉{puts} PUT · "
               f"💰{cheap} under $80 · {strong} strong · "
               f"⛔{len(skipped_above)} above $20")

    print(text_body)
    if EMAIL_SENDER != "your@gmail.com":
        send_email(subject, html_body, text_body)
    else:
        print("⚠️  Set EMAIL secrets in GitHub.")

if __name__ == "__main__":
    run()
