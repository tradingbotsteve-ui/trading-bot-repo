# ============================================================
# PHASE 6 — COMPLETE MARKET MOVERS LIST
# ============================================================
#
# DROP-IN REPLACEMENT for MARKET_MOVERS in phase6_trump_monitor.py
#
# HOW TO USE:
#   Copy everything below and replace the MARKET_MOVERS = { ... }
#   block in phase6_trump_monitor.py. That's it.
#
# ORGANISED BY PRIORITY:
#   P1 — Donald Trump (alone at top — single most market-moving human)
#   P2 — US Politicians & Government Officials
#   P3 — Federal Reserve & Central Banks
#   P4 — Legendary Investors & Hedge Fund Managers
#   P5 — Big Tech & AI CEOs
#   P6 — Congress Members (known stock traders)
#   P7 — Other Sector CEOs
#   P8 — Canadian Market Movers
#   P9 — Global Macro & Geopolitical Leaders
#
# EACH ENTRY HAS:
#   name          — full name
#   tier          — 1 (moves whole market) to 4 (moves sectors)
#   emoji         — visual identifier in email
#   role          — current title as of May 2026
#   why           — why they move markets (plain English)
#   keywords      — words to detect their name/actions in news
#   primary_stocks— dict of ticker → (company, reason for movement)
#   hold_thesis   — when to HOLD after their buy signal
#   sell_thesis   — when to SELL after their signal
#   color / bg    — card colour in email
#   source        — "truth_social" (Trump only) or "news"
#   priority      — lower = shown first in email
# ============================================================

MARKET_MOVERS = {

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P1 — DONALD TRUMP                                       ║
    # ║  Single most market-moving person alive.                 ║
    # ║  One Truth Social post has moved S&P 500 by 3-5%.        ║
    # ╚══════════════════════════════════════════════════════════╝

    "trump": {
        "name":     "Donald Trump",
        "tier":     1,
        "emoji":    "🇺🇸",
        "priority": 1,
        "role":     "47th President of the United States",
        "why":      (
            "Controls tariffs, trade deals, energy policy, sanctions, and "
            "regulatory appointments. When Trump posts on Truth Social, stocks "
            "move within MINUTES — not hours. A single post on tariffs wiped "
            "$2 trillion off global markets in April 2025. His endorsement of "
            "a company can pump it 20-40%. His attack can drop it 15%. "
            "No person on Earth has more immediate market impact."
        ),
        "hold_thesis": (
            "Hold Trump-pump trades for 1-3 DAYS maximum. The news cycle moves "
            "fast. Take profit at +15-25%. If he posts follow-up support, "
            "you can extend to 5-7 days. For policy changes (tariff deals, "
            "energy orders), hold 1-4 WEEKS as the market reprices."
        ),
        "sell_thesis": (
            "SELL when: (1) Trump stops talking about it, (2) you hit +15-25% "
            "gain, (3) a contradictory post appears, (4) media cycle shifts. "
            "For tariff-driven drops — wait 2-3 days for panic to settle, "
            "then buy quality companies at discount."
        ),
        "keywords": [
            "trump", "donald trump", "white house", "president trump",
            "truth social", "mar-a-lago", "executive order", "tariff",
            "trade deal", "trump signs", "trump announces", "trump says",
        ],
        "primary_stocks": {
            "SPY":  ("S&P 500 ETF",          "Broad market — ANY Trump economic statement moves SPY"),
            "DJT":  ("Trump Media & Tech",   "His own company — pumps hard on Trump attention"),
            "XOM":  ("ExxonMobil",           "'Drill baby drill' — Trump loves US energy"),
            "LMT":  ("Lockheed Martin",      "Defence spending — Trump = more military contracts"),
            "COIN": ("Coinbase",             "Trump is pro-crypto — any crypto policy pumps COIN"),
            "GLD":  ("Gold ETF",             "Trump uncertainty = gold rises as safe haven"),
        },
        "color":  "#B71C1C",
        "bg":     "#FFEBEE",
        "source": "truth_social",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P2 — US POLITICIANS & GOVERNMENT OFFICIALS              ║
    # ╚══════════════════════════════════════════════════════════╝

    "bessent": {
        "name":     "Scott Bessent",
        "tier":     1,
        "emoji":    "💵",
        "priority": 2,
        "role":     "US Treasury Secretary",
        "why":      (
            "Implements Trump's tariff policy and controls the US dollar. "
            "His announcements on China tariff pauses or escalations move "
            "the entire market. He can unilaterally pause tariffs — when he "
            "did this in April 2025, S&P 500 jumped 9.5% in one day. "
            "Most powerful economic official after Trump."
        ),
        "hold_thesis": (
            "Tariff pause or deal news: hold broad market (SPY, QQQ) for "
            "1-2 weeks as repricing plays out. Retail and tech recover fastest."
        ),
        "sell_thesis": (
            "Sell if tariff pause ends or new tariffs announced. Watch for "
            "Treasury bond auction results — weak demand = sell everything."
        ),
        "keywords": [
            "scott bessent", "bessent", "treasury secretary", "us treasury",
            "tariff deal", "tariff pause", "treasury department", "dollar policy",
        ],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "Tariff news = whole market moves instantly"),
            "WMT":  ("Walmart",        "Retail supply chain — tariff relief pumps WMT"),
            "AAPL": ("Apple",          "China tariff deal directly saves billions in Apple costs"),
            "NVDA": ("Nvidia",         "Export controls on chips — Bessent controls these too"),
        },
        "color":  "#1A237E",
        "bg":     "#E8EAF6",
        "source": "news",
    },

    "pelosi": {
        "name":     "Nancy Pelosi",
        "tier":     2,
        "emoji":    "🏛️",
        "priority": 3,
        "role":     "US House Representative (Retiring 2027) · Most-Tracked Congress Trader",
        "why":      (
            "Posted 54% return in 2024 and 20%+ in 2025 — outperforming most "
            "hedge funds. Sits on committees with advance knowledge of tech "
            "regulation, CHIPS Act, AI legislation. Her husband Paul Pelosi's "
            "option trades are legendary — he bought NVDA calls weeks before "
            "the CHIPS Act passed. 1.2 million people follow her trades "
            "on PelosiTracker. She is the most copied politician in markets."
        ),
        "hold_thesis": (
            "Follow her stock buys for 1-3 MONTHS. She typically holds for "
            "legislation to pass or regulatory clarity to emerge. Her NVDA, "
            "MSFT, and GOOGL buys have all been multi-month winners."
        ),
        "sell_thesis": (
            "Sell when Pelosi files a sale disclosure. Also sell when the "
            "legislation catalyst she was trading on gets resolved "
            "(bill passes or dies). Check pelositracker.app for real-time filings."
        ),
        "keywords": [
            "nancy pelosi", "pelosi", "paul pelosi", "pelosi trade",
            "pelosi buys", "pelosi sells", "pelosi disclosure",
        ],
        "primary_stocks": {
            "NVDA": ("Nvidia",     "Her #1 trade — bought before CHIPS Act, still holds"),
            "MSFT": ("Microsoft",  "Major holding — bought during AI regulation discussions"),
            "GOOGL":("Alphabet",   "Holds Google — antitrust committee insight"),
            "AAPL": ("Apple",      "Long-term Pelosi holding"),
        },
        "color":  "#4A148C",
        "bg":     "#F3E5F5",
        "source": "news",
    },

    "rfk": {
        "name":     "RFK Jr (Robert F. Kennedy Jr.)",
        "tier":     2,
        "emoji":    "💊",
        "priority": 4,
        "role":     "US Secretary of Health & Human Services (HHS)",
        "why":      (
            "Controls FDA, CDC, and NIH — three agencies that decide whether "
            "drugs get approved or banned. His anti-vaccine stance caused "
            "Moderna to drop 40% in weeks. Any FDA approval slowdown, "
            "vaccine mandate rollback, or drug pricing policy change goes "
            "through RFK. He is the single biggest threat to pharma stocks. "
            "His 'Make America Healthy Again' agenda attacks processed food, "
            "chemicals, and pharmaceutical companies systematically."
        ),
        "hold_thesis": (
            "For RFK-driven drops on pharma: wait 2-4 weeks for panic to "
            "subside. Companies with non-vaccine revenue (LLY's Ozempic, "
            "ABBV's Humira) recover faster. Don't catch falling knives."
        ),
        "sell_thesis": (
            "SELL pharma immediately on any RFK policy announcement targeting "
            "a specific drug or company. These drops are real and sustained. "
            "Hold your sell until RFK's next statement changes direction."
        ),
        "keywords": [
            "rfk", "rfk jr", "robert kennedy", "kennedy hhs", "hhs secretary",
            "fda approval", "vaccine mandate", "make america healthy", "cdc policy",
            "drug approval fda", "food dyes ban", "chemical food",
        ],
        "primary_stocks": {
            "MRNA": ("Moderna",        "Biggest victim of RFK — vaccine revenue at risk"),
            "PFE":  ("Pfizer",         "Vaccine + drug revenue directly threatened"),
            "LLY":  ("Eli Lilly",      "FDA approval pace for new drugs affected"),
            "UNH":  ("UnitedHealth",   "Health policy overhaul hits insurance stocks"),
            "MDLZ": ("Mondelez",       "Processed food maker — RFK targets ingredients"),
            "KHC":  ("Kraft Heinz",    "Processed food attack = KHC drops on RFK news"),
        },
        "color":  "#880E4F",
        "bg":     "#FCE4EC",
        "source": "news",
    },

    "mtg": {
        "name":     "Marjorie Taylor Greene",
        "tier":     3,
        "emoji":    "🏛️",
        "priority": 5,
        "role":     "US House Representative · Homeland Security Committee",
        "why":      (
            "Sits on Homeland Security Committee and Subcommittee on "
            "Counterterrorism — giving her advance knowledge of defence "
            "and cybersecurity contracts. Her PLTR (Palantir) buy before "
            "a $480M government contract was flagged by Unusual Whales. "
            "Active trader — discloses frequently. Follow her defence buys."
        ),
        "hold_thesis": (
            "Follow her defence/cybersecurity buys for 1-3 months. "
            "Government contracts take time to announce. PLTR, CRWD, "
            "and LMT are her most common targets."
        ),
        "sell_thesis": (
            "Sell when she discloses a sale. Or after the government "
            "contract she was anticipating gets publicly announced."
        ),
        "keywords": [
            "marjorie taylor greene", "mtg", "greene trade", "greene buys",
            "greene disclosure", "homeland security committee",
        ],
        "primary_stocks": {
            "PLTR": ("Palantir",       "Her most famous trade — defence AI contracts"),
            "CRWD": ("CrowdStrike",    "Cybersecurity — Homeland Security committee insight"),
            "LMT":  ("Lockheed Martin","Defence — committee knowledge of contracts"),
        },
        "color":  "#B71C1C",
        "bg":     "#FFEBEE",
        "source": "news",
    },

    "rick_scott": {
        "name":     "Senator Rick Scott",
        "tier":     3,
        "emoji":    "🏛️",
        "priority": 6,
        "role":     "US Senator (Florida) · +54.8% return in 2025",
        "why":      (
            "One of the top-performing Congress traders in 2025 with "
            "+54.8% return. Sits on Commerce Committee and Armed Services "
            "Committee. Active trader who discloses frequently. "
            "His trades in healthcare and defence have been well-timed "
            "relative to Senate committee activity."
        ),
        "hold_thesis": (
            "Follow Rick Scott buys for 4-8 weeks. His healthcare and "
            "defence bets tend to be event-driven around committee votes."
        ),
        "sell_thesis": (
            "Sell when he discloses a sale or after Senate committee "
            "action resolves the catalyst."
        ),
        "keywords": [
            "rick scott", "senator scott", "scott senate trade",
            "scott disclosure",
        ],
        "primary_stocks": {
            "UNH":  ("UnitedHealth",   "Healthcare giant — Senate health committee insight"),
            "LMT":  ("Lockheed Martin","Armed Services Committee = defence knowledge"),
            "AMZN": ("Amazon",         "Commerce Committee = tech/retail regulatory knowledge"),
        },
        "color":  "#37474F",
        "bg":     "#ECEFF1",
        "source": "news",
    },

    "davidson": {
        "name":     "Rep. Warren Davidson",
        "tier":     3,
        "emoji":    "🏛️",
        "priority": 7,
        "role":     "US House Representative (Ohio) · #1 Congress Trader 2025 (+78.8%)",
        "why":      (
            "The single best-performing Congress stock trader in 2025 with "
            "+78.8% return. Made his gains primarily through GE and "
            "GE Vernova (energy infrastructure). Pro-crypto legislator "
            "who introduced the Keep Innovation in America Act. "
            "His crypto and energy trades are most actionable."
        ),
        "hold_thesis": (
            "Follow Davidson's energy and crypto buys for 1-3 months. "
            "His GE Vernova bet shows he thinks energy infrastructure "
            "is a multi-year story."
        ),
        "sell_thesis": (
            "Sell when Davidson discloses a sale or when energy/crypto "
            "regulatory catalysts he anticipated get resolved."
        ),
        "keywords": [
            "warren davidson", "davidson congress", "davidson trade",
            "davidson disclosure", "keep innovation america",
        ],
        "primary_stocks": {
            "GEV":  ("GE Vernova",     "His #1 trade in 2025 — energy infrastructure"),
            "GE":   ("GE Aerospace",   "His second biggest 2025 winner"),
            "COIN": ("Coinbase",       "Pro-crypto — follows his crypto legislation"),
        },
        "color":  "#1B5E20",
        "bg":     "#E8F5E9",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P3 — FEDERAL RESERVE & CENTRAL BANKS                   ║
    # ╚══════════════════════════════════════════════════════════╝

    "warsh": {
        "name":     "Kevin Warsh",
        "tier":     1,
        "emoji":    "🏦",
        "priority": 8,
        "role":     "Federal Reserve Chair (from May 15, 2026)",
        "why":      (
            "Replaced Powell as Fed Chair May 15, 2026. Controls US interest "
            "rates — the single most important number for ALL stock valuations. "
            "Wants to shrink the Fed's $6.7 trillion balance sheet, which "
            "could push rates UP and drag stocks DOWN. His every word is "
            "analysed by every trader on earth. First statements as Chair "
            "will be the most market-moving of 2026."
        ),
        "hold_thesis": (
            "Rate cut signal → BUY and hold growth stocks (MSFT, NVDA, AMZN) "
            "for 4-12 weeks. Banks also benefit. Hold until next FOMC meeting "
            "confirms direction. Rate pause → hold for 2-4 weeks watching data."
        ),
        "sell_thesis": (
            "Rate hike or balance sheet reduction signal → SELL growth stocks "
            "immediately. Rotate into GLD, TLT (bonds), and defensive stocks "
            "(WMT, JNJ, KO). Sell when 10-year Treasury yield spikes above 4.5%."
        ),
        "keywords": [
            "kevin warsh", "warsh", "fed chair", "federal reserve", "fomc",
            "interest rate", "rate cut", "rate hike", "quantitative tightening",
            "balance sheet", "monetary policy", "fed meeting", "fomc decision",
        ],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "Rate changes affect every stock — broadest impact"),
            "JPM":  ("JPMorgan",       "Banks love rate clarity — move hardest on Fed news"),
            "TLT":  ("Treasury Bonds", "Moves directly inverse to rate expectations"),
            "GLD":  ("Gold ETF",       "Rate hike = gold down. Rate cut = gold up"),
            "QQQ":  ("Nasdaq ETF",     "Tech is most rate-sensitive — QQQ moves ±3% on Fed day"),
        },
        "color":  "#0D47A1",
        "bg":     "#E3F2FD",
        "source": "news",
    },

    "powell": {
        "name":     "Jerome Powell",
        "tier":     1,
        "emoji":    "🏛️",
        "priority": 9,
        "role":     "Former Fed Chair · Fed Governor until 2028",
        "why":      (
            "Still sits on the Fed board after stepping down May 15. "
            "His votes can contradict new Chair Warsh, creating confusion "
            "and volatility. 66 press conferences of market-moving experience. "
            "His dissent votes at FOMC meetings will be front-page news."
        ),
        "hold_thesis": (
            "Powell dissent against Warsh rate cuts = rates stay higher longer "
            "= hold defensive stocks (GLD, WMT, JNJ) over growth stocks."
        ),
        "sell_thesis": (
            "If Powell signals he supports Warsh's direction = rate certainty "
            "returns = sell GLD, buy back growth. Sell TLT on Powell hawkish signals."
        ),
        "keywords": [
            "jerome powell", "powell fed", "fed governor powell",
            "powell dissent", "powell vote", "powell statement",
        ],
        "primary_stocks": {
            "TLT":  ("Treasury Bonds", "Powell bond policy = TLT moves"),
            "GLD":  ("Gold",           "Rate uncertainty = gold safe haven"),
            "SPY":  ("S&P 500",        "Any Powell vs Warsh conflict = broad market volatility"),
        },
        "color":  "#37474F",
        "bg":     "#ECEFF1",
        "source": "news",
    },

    "macklem": {
        "name":     "Tiff Macklem",
        "tier":     2,
        "emoji":    "🍁",
        "priority": 10,
        "role":     "Governor, Bank of Canada",
        "why":      (
            "Canada's Fed Chair equivalent. Controls Canadian interest rates "
            "— 8 decisions per year. Each move affects ALL Canadian bank "
            "stocks (RY, TD, BNS, BMO, CM), the housing market, REITs, "
            "and the Canadian dollar. Rate cuts = TSX rallies. "
            "Rate hikes = TSX drops, especially real estate and financials."
        ),
        "hold_thesis": (
            "BoC rate cut → BUY Canadian banks (RY, TD, BNS) and REITs "
            "for 4-8 weeks. Canadian housing stocks also benefit. "
            "Hold until next BoC decision or economic data changes outlook."
        ),
        "sell_thesis": (
            "BoC rate hike or hawkish signal → SELL Canadian REITs and "
            "smaller banks immediately. Hold RY/TD as they're more diversified. "
            "Watch for CAD/USD rate to confirm direction."
        ),
        "keywords": [
            "tiff macklem", "macklem", "bank of canada", "boc rate",
            "canadian interest rate", "overnight rate", "canadian inflation",
            "boc decision", "bank of canada meeting",
        ],
        "primary_stocks": {
            "RY":     ("Royal Bank of Canada",  "Canada's biggest bank — most rate sensitive"),
            "TD":     ("TD Bank",               "Second largest — mortgage book = rate sensitive"),
            "BNS":    ("Scotiabank",            "Big Five — moves with rate decisions"),
            "BMO":    ("BMO Financial",         "Big Five — rate sensitive"),
            "XIU":    ("iShares S&P/TSX ETF",   "Whole TSX — broad Canadian market signal"),
        },
        "color":  "#B71C1C",
        "bg":     "#FFEBEE",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P4 — LEGENDARY INVESTORS & HEDGE FUND MANAGERS         ║
    # ╚══════════════════════════════════════════════════════════╝

    "buffett": {
        "name":     "Warren Buffett",
        "tier":     1,
        "emoji":    "🏆",
        "priority": 11,
        "role":     "CEO Berkshire Hathaway · Oracle of Omaha",
        "why":      (
            "Predicted the 2025 market rout by selling $134B in stocks in 2024 "
            "and holding $334B cash. Up $12.7B in 2026 while peers lost billions. "
            "When Buffett BUYS a stock, it typically jumps 5-15% immediately. "
            "When he SELLS, institutional investors follow. His annual letter "
            "and Berkshire AGM are the most-read investor documents on earth. "
            "His 13F filings are released quarterly and move markets."
        ),
        "hold_thesis": (
            "When Buffett buys — hold for 12-36 MONTHS minimum. He buys for "
            "long-term value, not short-term trades. His OXY buy has been "
            "ongoing for 3 years. His AAPL trimming in 2024 was a 12-month "
            "warning before the tariff selloff."
        ),
        "sell_thesis": (
            "Sell when Buffett files a sale disclosure. If he's selling, "
            "it's usually because the stock is overvalued or fundamentals "
            "have changed. His Apple trim before the tariff selloff is a "
            "classic example. Never argue with Buffett's exit."
        ),
        "keywords": [
            "warren buffett", "buffett", "berkshire hathaway", "berkshire",
            "oracle of omaha", "annual letter", "buffett buys", "buffett sells",
            "berkshire agm", "13f berkshire", "buffett warning",
        ],
        "primary_stocks": {
            "BRK.B":("Berkshire Hathaway","His company — moves directly on any Buffett news"),
            "AAPL": ("Apple",          "His biggest holding — trimmed in 2024, a warning signal"),
            "OXY":  ("Occidental",     "Multi-year buy — still accumulating in 2026"),
            "BAC":  ("Bank of America","Second largest — Buffett's bank bet"),
            "KO":   ("Coca-Cola",      "Held since 1988 — never sold, ultimate hold signal"),
            "CVX":  ("Chevron",        "Energy bet — follows his value investing thesis"),
        },
        "color":  "#1B5E20",
        "bg":     "#E8F5E9",
        "source": "news",
    },

    "druckenmiller": {
        "name":     "Stanley Druckenmiller",
        "tier":     2,
        "emoji":    "🐂",
        "priority": 12,
        "role":     "Duquesne Family Office · 30-year 30% avg return, zero losing years",
        "why":      (
            "Arguably the greatest trader alive. 30-year run at Duquesne with "
            "30% average annual returns and NO losing years — a record no other "
            "manager has matched. His 13F moves are followed by thousands of "
            "institutional investors. He bought Amazon, Meta, and Alphabet in "
            "Q3 2025 (all AI plays). He sold Nvidia entirely in late 2024 and "
            "Palantir in early 2025 — both at near-peaks. When Druckenmiller "
            "moves, markets take notice."
        ),
        "hold_thesis": (
            "Follow Druckenmiller buys for 3-9 MONTHS. He takes concentrated "
            "positions and holds through volatility. His NTRA (Natera) is "
            "his largest position — a precision medicine multi-year bet. "
            "He favours macro themes, not short-term trades."
        ),
        "sell_thesis": (
            "When Druckenmiller's 13F shows he's SOLD a position entirely, "
            "that's a strong exit signal. His Nvidia and Palantir exits were "
            "both near the top. Quarterly 13F releases are the key dates."
        ),
        "keywords": [
            "stanley druckenmiller", "druckenmiller", "duquesne", "druckenmiller buys",
            "druckenmiller sells", "druckenmiller 13f", "druckenmiller portfolio",
        ],
        "primary_stocks": {
            "AMZN": ("Amazon",         "Bought Q3 2025 — AI infrastructure + consumer play"),
            "META": ("Meta Platforms", "Bought Q3 2025 — AI-powered ad revenue bet"),
            "GOOGL":("Alphabet",       "Major position — AI + search dominance conviction"),
            "NTRA": ("Natera",         "Largest holding — precision medicine/oncology diagnostics"),
            "TSM":  ("TSMC",           "AI chip manufacturing monopoly — held in top 5"),
        },
        "color":  "#004D40",
        "bg":     "#E0F2F1",
        "source": "news",
    },

    "ackman": {
        "name":     "Bill Ackman",
        "tier":     2,
        "emoji":    "🎯",
        "priority": 13,
        "role":     "CEO Pershing Square Capital Management",
        "why":      (
            "One of Wall Street's most vocal investors — he tweets constantly "
            "and his opinions move markets. Famous for: shorting Herbalife "
            "($1B bet), calling the 2020 COVID crash on CNBC (market fell 30% "
            "after), and his $2.2B Amazon position. He is an activist investor "
            "who publicly pressures companies to change. His tweets during "
            "market crises are particularly market-moving — institutions watch "
            "his feed in real time."
        ),
        "hold_thesis": (
            "Ackman holds for 2-5 YEARS on his activist bets. His UBER bet "
            "is a long-duration play on platform economics. His BN "
            "(Brookfield) is a 19% position he's held for years. "
            "Follow his buys for medium to long-term holds."
        ),
        "sell_thesis": (
            "Sell when Ackman publicly announces he's exiting a position or "
            "files a 13F showing reduction. His GOOGL trim in early 2026 "
            "was a notable rebalancing signal. Watch his Twitter/X for "
            "real-time intent signals."
        ),
        "keywords": [
            "bill ackman", "ackman", "pershing square", "ackman buys",
            "ackman sells", "ackman tweet", "ackman 13f",
        ],
        "primary_stocks": {
            "UBER": ("Uber",           "His largest US holding — long-duration platform bet"),
            "BN":   ("Brookfield",     "19% of portfolio — asset management compounder"),
            "AMZN": ("Amazon",         "Added $2.2B position — AWS + AI conviction"),
            "GOOGL":("Alphabet",       "Major position despite partial trim"),
            "CMG":  ("Chipotle",       "Long-term hold — brand + unit economics compounder"),
            "QSR":  ("Restaurant Brands","Tim Hortons parent — Canadian relevance for TFSA"),
        },
        "color":  "#E65100",
        "bg":     "#FFF3E0",
        "source": "news",
    },

    "burry": {
        "name":     "Michael Burry",
        "tier":     2,
        "emoji":    "🐻",
        "priority": 14,
        "role":     "Scion Asset Management · 'The Big Short' investor",
        "why":      (
            "Predicted and profited from the 2008 housing crash. Warned about "
            "2021 meme stock bubble and 2022 tech crash. In 2026, warning about "
            "US debt levels and S&P 500 overvaluation. When Burry puts on a "
            "massive short position (via put options), retail investors panic. "
            "His 13F filings often contain cryptic single-word tweets that go "
            "viral and crash specific stocks within hours."
        ),
        "hold_thesis": (
            "Burry shorts play out over 3-18 MONTHS. Do not buy stocks he's "
            "heavily shorting. His GLD position is a multi-year inflation hedge. "
            "If he goes long on a stock, hold 3-6 months minimum."
        ),
        "sell_thesis": (
            "If Burry tweets a warning or his 13F shows new put positions on "
            "a stock you hold — take profits immediately. His track record on "
            "macro calls is exceptional. Never hold against Burry's shorts."
        ),
        "keywords": [
            "michael burry", "burry", "scion", "big short", "burry short",
            "burry warning", "13f burry", "burry put options", "market crash warning",
        ],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "His macro shorts affect broad market sentiment"),
            "GLD":  ("Gold",           "Inflation/debt hedge — Burry has held gold positions"),
            "BABA": ("Alibaba",        "Burry has held Chinese stocks as contrarian bet"),
            "GME":  ("GameStop",       "Made famous by Burry — retail follows his GME signals"),
        },
        "color":  "#37474F",
        "bg":     "#ECEFF1",
        "source": "news",
    },

    "cathie": {
        "name":     "Cathie Wood",
        "tier":     2,
        "emoji":    "🚀",
        "priority": 15,
        "role":     "CEO ARK Invest · Innovation ETF Manager",
        "why":      (
            "ARK ETFs hold billions in disruptive tech — TSLA, COIN, RBLX, ROKU. "
            "Her daily buy/sell filings are published every night and followed "
            "by 1M+ retail investors. When ARK buys = retail piles in next day. "
            "Her price targets (Tesla $2000, Bitcoin $1.5M by 2030) move retail "
            "sentiment massively. She's a bellwether for innovation/speculative "
            "stock sentiment."
        ),
        "hold_thesis": (
            "ARK buys signal 5-year conviction on disruptive tech. Follow her "
            "buys for 3-12 MONTHS for trend trades. Best during risk-on markets "
            "when retail investors are buying aggressively."
        ),
        "sell_thesis": (
            "ARK sells are often forced by redemptions, not conviction. "
            "However, if she consistently sells a stock for 5+ days in a row, "
            "the thesis may have changed. Exit when ARK has sold 30%+ of a position."
        ),
        "keywords": [
            "cathie wood", "cathie", "ark invest", "arkk", "ark buys",
            "ark sells", "ark etf", "innovation etf", "ark daily trades",
        ],
        "primary_stocks": {
            "TSLA": ("Tesla",          "ARK's biggest conviction — $2000 price target"),
            "COIN": ("Coinbase",       "Major ARK holding — crypto adoption thesis"),
            "RBLX": ("Roblox",         "Gaming metaverse — ARK innovation bet"),
            "ROKU": ("Roku",           "Streaming tech — major ARK holding"),
            "PATH": ("UiPath",         "AI automation — ARK favourite"),
        },
        "color":  "#0277BD",
        "bg":     "#E1F5FE",
        "source": "news",
    },

    "soros": {
        "name":     "George Soros",
        "tier":     2,
        "emoji":    "💰",
        "priority": 16,
        "role":     "Founder Soros Fund Management · Legendary macro trader",
        "why":      (
            "The man who 'broke the Bank of England' in 1992, making $1B in "
            "one day. Soros Fund Management manages $28B+. His quarterly "
            "13F filings reveal macro bets on currencies, commodities, and "
            "geopolitics. Now largely managed by his son Alexander Soros. "
            "His political donations and public statements on democracy "
            "occasionally move media and political stocks."
        ),
        "hold_thesis": (
            "Follow Soros macro bets for 6-18 months. His positions are "
            "long-term macro calls on currencies, commodities, and geopolitics. "
            "His gold positions are a multi-year inflation hedge."
        ),
        "sell_thesis": (
            "Exit when 13F shows Soros sold. His European and EM bets "
            "can reverse sharply on political events."
        ),
        "keywords": [
            "george soros", "soros", "soros fund", "soros buys",
            "soros 13f", "alexander soros",
        ],
        "primary_stocks": {
            "GLD":  ("Gold ETF",       "Soros is a consistent gold bull"),
            "SPY":  ("S&P 500",        "His broad macro positions affect market sentiment"),
        },
        "color":  "#4A148C",
        "bg":     "#F3E5F5",
        "source": "news",
    },

    "klarman": {
        "name":     "Seth Klarman",
        "tier":     3,
        "emoji":    "📚",
        "priority": 17,
        "role":     "CEO Baupost Group · Value investing legend",
        "why":      (
            "'Margin of Safety' author. Manages $30B+ at Baupost with "
            "legendary discretion. His 13F reveals deep value bets that "
            "often play out over 2-5 years. In early 2026, bought a new "
            "$490M Amazon position — one of his largest ever tech bets. "
            "Institutional investors treat his 13F as a must-read."
        ),
        "hold_thesis": (
            "Klarman buys for 2-5 YEAR value thesis. Follow his bets for "
            "long-term TFSA positions. His AMZN buy is a multi-year cloud + "
            "AI infrastructure bet."
        ),
        "sell_thesis": (
            "Sell when 13F shows full exit. Klarman rarely sells unless "
            "the thesis is completely broken or valuation gets extreme."
        ),
        "keywords": [
            "seth klarman", "klarman", "baupost", "baupost group",
            "klarman buys", "klarman 13f",
        ],
        "primary_stocks": {
            "AMZN": ("Amazon",         "New $490M position — AWS + AI multi-year bet"),
            "GOOGL":("Alphabet",       "Deep value + AI infrastructure thesis"),
        },
        "color":  "#1B5E20",
        "bg":     "#E8F5E9",
        "source": "news",
    },

    "tudor_jones": {
        "name":     "Paul Tudor Jones",
        "tier":     3,
        "emoji":    "📊",
        "priority": 18,
        "role":     "CEO Tudor Investment Corp · Macro trader",
        "why":      (
            "Known for predicting the 1987 market crash and tripling his "
            "money while markets collapsed. Said in 2025 that Bitcoin would "
            "perform well under Trump and called inflation the 'biggest threat' "
            "to markets. His macro calls on gold and crypto move those markets. "
            "Called Buffett the 'OG of compound interest' — a bullish signal "
            "for Berkshire when mentioned."
        ),
        "hold_thesis": (
            "Follow Jones on macro themes: gold, Bitcoin, inflation protection. "
            "His calls tend to be 6-18 month macro trends."
        ),
        "sell_thesis": (
            "Sell inflation hedges (GLD, BTC proxy) when Jones signals "
            "deflation or recession is the bigger risk."
        ),
        "keywords": [
            "paul tudor jones", "tudor jones", "tudor investment",
            "tudor jones bitcoin", "tudor jones gold", "tudor jones macro",
        ],
        "primary_stocks": {
            "GLD":  ("Gold ETF",       "His #1 inflation hedge — long-term bull"),
            "MSTR": ("MicroStrategy",  "Bitcoin proxy — Tudor Jones is pro-crypto"),
            "BRK.B":("Berkshire",      "Praised Buffett — signals Berkshire conviction"),
        },
        "color":  "#E65100",
        "bg":     "#FFF3E0",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P5 — BIG TECH & AI CEOs                                ║
    # ╚══════════════════════════════════════════════════════════╝

    "musk": {
        "name":     "Elon Musk",
        "tier":     1,
        "emoji":    "🚀",
        "priority": 19,
        "role":     "CEO Tesla/SpaceX/X · DOGE Advisor · Richest person on Earth",
        "why":      (
            "Controls Tesla, SpaceX, X (Twitter), xAI (Grok), Neuralink, "
            "and The Boring Company. His tweets have moved markets by billions "
            "in minutes — Dogecoin +800% in 2021, GameStop, crypto. SpaceX IPO "
            "is coming in 2026 (est. $250B valuation). DOGE budget cuts affect "
            "defence contractors. Trump-Musk relationship is the most important "
            "in business. His Optimus robot and Starship milestones move TSLA."
        ),
        "hold_thesis": (
            "TSLA: Hold 1-5 days for tweet-driven pumps. Hold 3-12 months "
            "for product milestone plays (Optimus, Robotaxi). SpaceX IPO "
            "will be a 12-month story — position in Rocket Lab as proxy."
        ),
        "sell_thesis": (
            "Sell TSLA when: Musk's attention shifts away, TSLA misses "
            "delivery numbers, or regulators move on self-driving. "
            "His political activities (DOGE) have hurt TSLA brand in Europe — "
            "watch European delivery data as exit signal."
        ),
        "keywords": [
            "elon musk", "elon", "musk", "tesla", "spacex", "x.com",
            "doge", "grok", "xai", "starship", "starlink", "optimus robot",
            "neuralink", "boring company", "musk tweet",
        ],
        "primary_stocks": {
            "TSLA": ("Tesla",          "His flagship — every Musk statement moves TSLA"),
            "RKLB": ("Rocket Lab",     "SpaceX competitor/partner — SpaceX IPO proxy"),
            "NVDA": ("Nvidia",         "xAI uses Nvidia chips — Grok AI news moves NVDA"),
            "DOGE": ("Dogecoin",       "Musk-crypto link — he invented the DOGE meme"),
        },
        "color":  "#1a1a2e",
        "bg":     "#E8EAF6",
        "source": "news",
    },

    "jensen": {
        "name":     "Jensen Huang",
        "tier":     1,
        "emoji":    "🤖",
        "priority": 20,
        "role":     "CEO & Co-Founder Nvidia · King of AI Chips",
        "why":      (
            "Controls the picks-and-shovels of the AI gold rush. Every AI "
            "data centre being built worldwide runs on Nvidia chips. His "
            "quarterly earnings guidance moves NVDA 10-20% in after-hours. "
            "China chip export controls are a $15B+ revenue question. "
            "His CES and GTC keynotes are the most market-moving tech speeches "
            "outside of Apple. The entire AI sector trades on his words."
        ),
        "hold_thesis": (
            "Jensen guidance on data centre demand → hold NVDA and AMD for "
            "4-12 weeks through earnings cycle. AI infrastructure spending "
            "is a multi-year megatrend — NVDA is a core long-term hold."
        ),
        "sell_thesis": (
            "Sell NVDA when: Jensen warns about demand slowdown, China export "
            "controls tighten unexpectedly, or AMD closes the gap significantly. "
            "Take partial profits after any 20%+ post-earnings spike."
        ),
        "keywords": [
            "jensen huang", "jensen", "nvidia", "h100", "h200", "blackwell",
            "cuda", "gpu", "ai chip", "data center nvidia", "nvidia guidance",
            "export control nvidia", "nvidia earnings",
        ],
        "primary_stocks": {
            "NVDA": ("Nvidia",         "His company — Jensen is the #1 NVDA catalyst"),
            "AMD":  ("AMD",            "Nvidia competitor — NVDA news moves AMD together"),
            "SMCI": ("Super Micro",    "Builds servers with Nvidia GPUs — follows NVDA"),
            "AVGO": ("Broadcom",       "AI networking chips — moves with NVDA guidance"),
        },
        "color":  "#4527A0",
        "bg":     "#EDE7F6",
        "source": "news",
    },

    "dimon": {
        "name":     "Jamie Dimon",
        "tier":     2,
        "emoji":    "🏦",
        "priority": 21,
        "role":     "CEO JPMorgan Chase · Wall Street's most powerful banker",
        "why":      (
            "Head of the world's most systemically important bank. In May 2026 "
            "warned of an overdue credit recession. His annual letter to "
            "shareholders is the most-read banking document. When Dimon says "
            "'storm clouds are coming', the market takes notice. He also "
            "controls $3.9 trillion in assets — his trading desk IS the market "
            "in many fixed income products."
        ),
        "hold_thesis": (
            "When Dimon is bullish on economy — hold bank stocks (JPM, BAC, GS) "
            "for 2-4 months. His bullish calls tend to coincide with Fed rate "
            "certainty and strong loan growth."
        ),
        "sell_thesis": (
            "When Dimon warns of recession, credit crisis, or market bubble — "
            "SELL financials immediately and rotate into GLD, TLT, and "
            "defensive stocks. His warnings have historically been 6-12 months "
            "early but eventually correct."
        ),
        "keywords": [
            "jamie dimon", "dimon", "jpmorgan", "jp morgan", "chase bank",
            "dimon warning", "credit recession", "banking crisis",
            "jpmorgan earnings", "dimon letter",
        ],
        "primary_stocks": {
            "JPM":  ("JPMorgan Chase", "His bank — moves most on his statements"),
            "BAC":  ("Bank of America","All big banks move together on credit warnings"),
            "GS":   ("Goldman Sachs",  "Investment banking sector follows Dimon's macro calls"),
            "XLF":  ("Financial ETF",  "Whole financial sector = fastest Dimon trade"),
        },
        "color":  "#004D40",
        "bg":     "#E0F2F1",
        "source": "news",
    },

    "altman": {
        "name":     "Sam Altman",
        "tier":     2,
        "emoji":    "🧠",
        "priority": 22,
        "role":     "CEO OpenAI · Father of ChatGPT",
        "why":      (
            "Controls the world's most influential AI company. Microsoft owns "
            "~49% of OpenAI. Every OpenAI product launch (GPT-5, Sora, o3) "
            "moves MSFT and NVDA. His 2026 Musk trial testimony about OpenAI's "
            "founding is market-moving. AI safety regulation — his testimony "
            "to Congress moves the entire AI sector. First person to make "
            "AGI mainstream — when he announces milestones, markets react."
        ),
        "hold_thesis": (
            "OpenAI product launch → hold MSFT for 2-4 weeks. AI regulation "
            "clarity → hold entire AI sector (NVDA, MSFT, META) for 4-8 weeks. "
            "OpenAI funding round = long-term MSFT buy signal."
        ),
        "sell_thesis": (
            "Sell MSFT if Altman signals OpenAI is diversifying away from "
            "Microsoft infrastructure. Sell AI sector broadly if Altman "
            "warns about AGI safety requiring regulation pauses."
        ),
        "keywords": [
            "sam altman", "altman", "openai", "chatgpt", "gpt-5", "gpt5",
            "o3", "o4", "openai funding", "agi", "openai product",
            "altman testimony", "openai microsoft",
        ],
        "primary_stocks": {
            "MSFT": ("Microsoft",      "Owns ~49% of OpenAI — direct beneficiary"),
            "NVDA": ("Nvidia",         "OpenAI runs on Nvidia — AI product = NVDA demand"),
            "GOOGL":("Alphabet",       "OpenAI's main competitor — competitive threat"),
            "PLTR": ("Palantir",       "Enterprise AI — sector moves with OpenAI milestones"),
        },
        "color":  "#00695C",
        "bg":     "#E0F7FA",
        "source": "news",
    },

    "zuckerberg": {
        "name":     "Mark Zuckerberg",
        "tier":     2,
        "emoji":    "📱",
        "priority": 23,
        "role":     "CEO Meta Platforms · Facebook/Instagram/WhatsApp/Llama AI",
        "why":      (
            "Controls the world's largest social network with 3.3B daily users. "
            "Meta's ad revenue is the most direct barometer of the entire "
            "digital economy. His Llama AI model is the open-source alternative "
            "to OpenAI. Meta is spending $70B+ on AI in 2025 alone. "
            "Any antitrust ruling, ad market guidance, or AI product launch "
            "moves META ±5-15%."
        ),
        "hold_thesis": (
            "Hold META for earnings cycles (quarterly). His AI spending "
            "guidance is a 2-year story. META has compounded at 40%+ since "
            "his 2022 'year of efficiency' pivot."
        ),
        "sell_thesis": (
            "Sell META if: ad revenue disappoints, EU regulation bites, "
            "or TikTok ban reversal brings competition back. "
            "Take profit after any 20%+ earnings pop."
        ),
        "keywords": [
            "mark zuckerberg", "zuckerberg", "meta", "facebook", "instagram",
            "whatsapp", "llama", "threads", "metaverse", "ray-ban meta",
            "meta earnings", "meta ai",
        ],
        "primary_stocks": {
            "META": ("Meta Platforms", "His company — every statement moves META directly"),
            "SNAP": ("Snapchat",       "Direct competitor — META good news = SNAP drops"),
            "GOOGL":("Alphabet",       "Ad revenue rival — META guidance = GOOGL reaction"),
        },
        "color":  "#1565C0",
        "bg":     "#E3F2FD",
        "source": "news",
    },

    "cook": {
        "name":     "Tim Cook",
        "tier":     2,
        "emoji":    "🍎",
        "priority": 24,
        "role":     "CEO Apple Inc.",
        "why":      (
            "Apple is the world's most valuable company ($3T+). Cook's "
            "China relationship, supply chain commentary, and product "
            "guidance move AAPL ±3-8%. Apple Intelligence (AI) is his "
            "biggest 2026 bet — its success/failure moves the stock by "
            "tens of billions. 1.4B active Apple devices = largest consumer "
            "hardware install base on Earth. His India manufacturing push "
            "is the anti-China tariff hedge the market watches."
        ),
        "hold_thesis": (
            "Hold AAPL through product upgrade cycles (iPhone 17, 18). "
            "Apple Intelligence adoption is a 2-3 year earnings story. "
            "Buy AAPL dips caused by China tariff fears — Cook always finds "
            "a way to protect the supply chain."
        ),
        "sell_thesis": (
            "Sell AAPL if: China production gets fully disrupted, "
            "Apple Intelligence flops at launch, or iPhone sales miss "
            "for 2+ consecutive quarters. Take profit after major product "
            "launches (sell the news)."
        ),
        "keywords": [
            "tim cook", "apple ceo", "apple china", "iphone sales",
            "apple intelligence", "apple earnings", "apple vision pro",
            "apple india", "apple supply chain",
        ],
        "primary_stocks": {
            "AAPL": ("Apple",          "His company — Cook statements are the #1 AAPL catalyst"),
            "QCOM": ("Qualcomm",       "Makes iPhone modem chips — AAPL guidance = QCOM move"),
            "TSM":  ("TSMC",           "Makes all Apple chips — AAPL demand = TSM revenue"),
        },
        "color":  "#212121",
        "bg":     "#F5F5F5",
        "source": "news",
    },

    "nadella": {
        "name":     "Satya Nadella",
        "tier":     2,
        "emoji":    "☁️",
        "priority": 25,
        "role":     "CEO Microsoft · Azure Cloud · Copilot AI",
        "why":      (
            "Microsoft is the world's second most valuable company. Azure "
            "cloud is growing 33%+ YoY driven by AI workloads. Copilot is "
            "embedded in Office 365 used by 1.4B people — his AI monetisation "
            "guidance moves MSFT ±5%. OpenAI partnership is the biggest "
            "enterprise AI bet. His quarterly earnings calls are the most "
            "important indicator of enterprise AI spending."
        ),
        "hold_thesis": (
            "Hold MSFT through quarterly earnings cycles. Azure growth rate "
            "is the key metric — if accelerating, hold 4-12 weeks. "
            "Copilot monetisation is a 2-3 year revenue story."
        ),
        "sell_thesis": (
            "Sell if Azure growth decelerates below 28%, Copilot adoption "
            "disappoints, or OpenAI partnership frays. Take profit after "
            "earnings beats that push MSFT above 35x P/E."
        ),
        "keywords": [
            "satya nadella", "nadella", "microsoft ceo", "azure", "copilot",
            "office ai", "teams microsoft", "activision", "bing ai",
            "microsoft earnings", "azure growth",
        ],
        "primary_stocks": {
            "MSFT": ("Microsoft",      "His company — Nadella statements move MSFT directly"),
            "NVDA": ("Nvidia",         "Azure runs on Nvidia — MSFT cloud growth = NVDA demand"),
        },
        "color":  "#01579B",
        "bg":     "#E1F5FE",
        "source": "news",
    },

    "ellison": {
        "name":     "Larry Ellison",
        "tier":     2,
        "emoji":    "🗄️",
        "priority": 26,
        "role":     "CTO & Co-Founder Oracle",
        "why":      (
            "Oracle is the surprise winner of the AI infrastructure boom. "
            "ORCL signed massive cloud contracts with OpenAI, xAI, and the "
            "US government. Stock up 80%+ as AI companies race to store data. "
            "Ellison's personal announcements of new AI data centre contracts "
            "have moved ORCL 10-20% in single sessions. He is quietly building "
            "the data backbone of the AI economy."
        ),
        "hold_thesis": (
            "Hold ORCL on new AI contract announcements for 4-12 weeks. "
            "Multi-cloud deals with government and AI labs are a 2-5 year "
            "revenue story."
        ),
        "sell_thesis": (
            "Take profit after any 15%+ pop on contract news. "
            "Sell if contract execution disappoints in earnings."
        ),
        "keywords": [
            "larry ellison", "ellison", "oracle", "orcl", "oracle cloud",
            "oracle ai", "oracle contract", "oracle openai", "oracle xai",
        ],
        "primary_stocks": {
            "ORCL": ("Oracle",         "His company — Ellison deal announcements = 10-20% move"),
            "MSFT": ("Microsoft",      "Oracle-Microsoft AI infrastructure partnership"),
        },
        "color":  "#B71C1C",
        "bg":     "#FFEBEE",
        "source": "news",
    },

    "jassy": {
        "name":     "Andy Jassy",
        "tier":     2,
        "emoji":    "📦",
        "priority": 27,
        "role":     "CEO Amazon · AWS Cloud",
        "why":      (
            "AWS is the world's largest cloud provider (31% market share). "
            "Amazon's planned $200B in capex for 2026 (doubled) signals "
            "the biggest AI infrastructure bet in corporate history. "
            "Jassy's commentary on AI spending, AWS growth, and consumer "
            "demand is the single best bellwether for the entire tech sector. "
            "His earnings calls move AMZN ±8% and ripple through all tech."
        ),
        "hold_thesis": (
            "Hold AMZN through quarterly cycles. AWS growth acceleration "
            "is a multi-year story. $200B capex will produce AI revenue "
            "for 5+ years — Jassy confirmed this timeline."
        ),
        "sell_thesis": (
            "Sell if AWS growth drops below 18%, or retail margins compress "
            "unexpectedly. Take profit after any 15%+ earnings pop."
        ),
        "keywords": [
            "andy jassy", "jassy", "amazon ceo", "aws", "amazon web services",
            "amazon earnings", "amazon capex", "amazon ai", "fulfillment amazon",
        ],
        "primary_stocks": {
            "AMZN": ("Amazon",         "His company — Jassy statements move AMZN ±8%"),
            "MSFT": ("Microsoft",      "AWS competitor — AMZN guidance moves Azure expectations"),
        },
        "color":  "#E65100",
        "bg":     "#FFF3E0",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P7 — OTHER SECTOR CEOs WITH MARKET-MOVING POWER        ║
    # ╚══════════════════════════════════════════════════════════╝

    "pichai": {
        "name":     "Sundar Pichai",
        "tier":     2,
        "emoji":    "🔍",
        "priority": 28,
        "role":     "CEO Alphabet (Google)",
        "why":      (
            "Controls Google Search (90% global market share), YouTube (2B users), "
            "Google Cloud (fastest growing major cloud), and DeepMind AI. "
            "His Gemini AI model is in a direct race with ChatGPT. "
            "Google's ad revenue is the global economy's health indicator. "
            "Antitrust rulings against Google (ongoing DOJ case) are the "
            "biggest risk — Pichai's response moves the stock immediately."
        ),
        "hold_thesis": (
            "Hold GOOGL through ad revenue cycles and AI product launches. "
            "Google Cloud growth at 28%+ is a multi-year story. "
            "Buy antitrust dips — Google always wins these cases historically."
        ),
        "sell_thesis": (
            "Sell if DOJ forces Google to break up Search from YouTube/Chrome. "
            "Sell if Gemini AI loses meaningful market share to ChatGPT/Claude. "
            "Take profit after any 20%+ run."
        ),
        "keywords": [
            "sundar pichai", "pichai", "google ceo", "alphabet ceo",
            "google search", "gemini ai", "google cloud", "youtube revenue",
            "google antitrust", "alphabet earnings",
        ],
        "primary_stocks": {
            "GOOGL":("Alphabet",       "His company — Pichai guidance moves GOOGL ±6%"),
            "META": ("Meta Platforms", "Competing for same ad dollars — Google guidance = META"),
        },
        "color":  "#0D47A1",
        "bg":     "#E3F2FD",
        "source": "news",
    },

    "bezos": {
        "name":     "Jeff Bezos",
        "tier":     2,
        "emoji":    "🛒",
        "priority": 29,
        "role":     "Amazon Founder · Blue Origin · Washington Post owner",
        "why":      (
            "Still Amazon's largest individual shareholder (9.7%). His Blue Origin "
            "space company is competing with SpaceX for NASA contracts. His "
            "Washington Post creates political influence. Trump has historically "
            "attacked Bezos/Amazon — when Trump attacks, AMZN drops. "
            "Bezos returning to Seattle and stepping away from WaPo in 2024 "
            "reduces his political footprint but his AMZN stake still makes "
            "him one of the most watched insiders in markets."
        ),
        "hold_thesis": (
            "Blue Origin NASA wins = hold RKLB, BA sector. Amazon stake "
            "changes = 3-12 month AMZN signal."
        ),
        "sell_thesis": (
            "Trump attacking Bezos/Amazon = AMZN drops 3-8%. "
            "If Bezos sells large blocks of AMZN = near-term signal."
        ),
        "keywords": [
            "jeff bezos", "bezos", "blue origin", "amazon founder",
            "bezos sells", "bezos blue origin", "new shepard", "new glenn",
        ],
        "primary_stocks": {
            "AMZN": ("Amazon",         "His company — Bezos moves = Amazon SEC filing"),
            "RKLB": ("Rocket Lab",     "Blue Origin competitor — Bezos space news moves sector"),
        },
        "color":  "#E65100",
        "bg":     "#FFF3E0",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P8 — CANADIAN MARKET MOVERS                            ║
    # ║  Specific to TSX and TFSA investing                     ║
    # ╚══════════════════════════════════════════════════════════╝

    "carney": {
        "name":     "Mark Carney",
        "tier":     1,
        "emoji":    "🍁",
        "priority": 30,
        "role":     "Prime Minister of Canada (2025–)",
        "why":      (
            "Former Bank of Canada and Bank of England governor — the only "
            "person to lead two G7 central banks. Now Canada's PM. "
            "His trade policy with Trump (tariffs, USMCA renegotiation), "
            "carbon tax decisions, housing policy, and defence spending "
            "directly affect the entire TSX. The Trump-Carney relationship "
            "is the most important bilateral relationship for Canadian stocks. "
            "Any Canada-US trade news = TSX moves immediately."
        ),
        "hold_thesis": (
            "US-Canada trade deal → BUY TSX broadly (XIU) + energy (ENB, SU) "
            "for 4-12 weeks. Carney infrastructure spending = hold CNR, CP, "
            "CAT for 2-6 months."
        ),
        "sell_thesis": (
            "Trade war escalation with US → SELL CAD-denominated exporters "
            "(SHOP, CNR) immediately. Rotate into gold (ABX) and domestic "
            "Canadian companies less exposed to US tariffs."
        ),
        "keywords": [
            "mark carney", "carney", "prime minister canada", "canadian government",
            "usmca canada", "canada tariff", "canada trade deal", "carbon tax",
            "canadian budget", "carney housing", "canada us relations",
        ],
        "primary_stocks": {
            "SHOP": ("Shopify",          "Canada's most valuable company — trade policy = SHOP"),
            "ENB":  ("Enbridge",         "Pipeline policy = Carney's biggest energy decision"),
            "RY":   ("Royal Bank",       "Canada's biggest bank — PM economic policy"),
            "XIU":  ("iShares S&P/TSX",  "Entire TSX ETF — Carney macro = broad Canada move"),
            "SU":   ("Suncor Energy",    "Oil sands — Canadian energy policy affects SU directly"),
            "CNR":  ("CN Rail",          "Infrastructure/trade = rail traffic follows trade volumes"),
        },
        "color":  "#C62828",
        "bg":     "#FFEBEE",
        "source": "news",
    },

    "watsa": {
        "name":     "Prem Watsa",
        "tier":     2,
        "emoji":    "🦁",
        "priority": 31,
        "role":     "CEO Fairfax Financial · Canada's Warren Buffett",
        "why":      (
            "Known as Canada's Warren Buffett. Fairfax Financial holds massive "
            "positions in Canadian and global stocks. His contrarian bets "
            "on inflation, Indian markets, and Greek debt have paid off hugely. "
            "When Watsa makes a large buy — Bay Street follows. His 13F and "
            "Fairfax annual report are must-reads for Canadian investors. "
            "His $5B+ in Indian equities (Digit Insurance) is the biggest "
            "Canadian India bet ever made."
        ),
        "hold_thesis": (
            "Follow Watsa buys for 12-36 MONTHS. He is a long-term value "
            "investor. His Indian market bet is a decade-long conviction. "
            "Fairfax Financial itself (FFH.TO) is a compound machine."
        ),
        "sell_thesis": (
            "Sell when Watsa publicly discloses a position reduction in his "
            "annual report or 13F. His macro hedges (shorting markets) are "
            "early warning signals — he was early on 2007 crisis."
        ),
        "keywords": [
            "prem watsa", "watsa", "fairfax financial", "fairfax",
            "watsa buys", "watsa india", "blackberry fairfax", "ffh",
        ],
        "primary_stocks": {
            "FFH":  ("Fairfax Financial","His company on TSX — Watsa statements move FFH"),
            "BB":   ("BlackBerry",       "Fairfax is BlackBerry's largest shareholder"),
            "RY":   ("Royal Bank",       "Fairfax holds Canadian financials broadly"),
        },
        "color":  "#4527A0",
        "bg":     "#EDE7F6",
        "source": "news",
    },

    "lutke": {
        "name":     "Tobi Lütke",
        "tier":     2,
        "emoji":    "🛍️",
        "priority": 32,
        "role":     "CEO Shopify · Canada's most important tech CEO",
        "why":      (
            "Shopify is Canada's most valuable company and the biggest "
            "Canadian stock in your TFSA universe. His product launches, "
            "US-Canada trade commentary, and AI integration announcements "
            "move SHOP ±10%. His 'reflexive' management style creates high "
            "volatility around earnings. His Twitter/X presence is active "
            "and market-moving for SHOP specifically."
        ),
        "hold_thesis": (
            "Hold SHOP through GMV (Gross Merchandise Volume) growth cycles. "
            "Shopify Payments and international expansion are 2-5 year stories. "
            "Buy SHOP on US tariff-driven dips — merchants move to Shopify "
            "regardless of trade policy."
        ),
        "sell_thesis": (
            "Sell SHOP if: GMV growth decelerates below 20%, Amazon/TikTok "
            "Shop takes meaningful merchant share, or Lütke signals "
            "major strategic pivot. Take profit after 30%+ runs."
        ),
        "keywords": [
            "tobi lutke", "lutke", "shopify ceo", "shopify earnings",
            "shopify gmv", "shopify ai", "shopify payment", "shopify merchants",
        ],
        "primary_stocks": {
            "SHOP": ("Shopify",          "His company — Lütke is the #1 SHOP catalyst"),
        },
        "color":  "#00695C",
        "bg":     "#E0F7FA",
        "source": "news",
    },

    # ╔══════════════════════════════════════════════════════════╗
    # ║  P9 — GLOBAL MACRO & GEOPOLITICAL LEADERS               ║
    # ╚══════════════════════════════════════════════════════════╝

    "xi": {
        "name":     "Xi Jinping",
        "tier":     1,
        "emoji":    "🐉",
        "priority": 33,
        "role":     "President of China · Communist Party General Secretary",
        "why":      (
            "Controls the world's second largest economy. China-US trade war, "
            "Taiwan tensions, chip export bans, and PBOC stimulus all flow "
            "through Xi. A single Taiwan military statement can drop global "
            "markets 5% in hours. China stimulus announcements pump commodities, "
            "copper, oil, and EV stocks. His relationship with Trump determines "
            "whether the tariff war escalates or resolves."
        ),
        "hold_thesis": (
            "China stimulus announcement → BUY copper miners (FCX, TECK), "
            "oil stocks, and luxury brands for 2-6 weeks. US-China trade "
            "deal → BUY AAPL, NVDA, and broad market (SPY) for 1-4 weeks."
        ),
        "sell_thesis": (
            "Taiwan military action or sabre-rattling → SELL TSMC (TSM), "
            "NVDA (China revenue risk), AAPL (supply chain risk). "
            "Buy LMT, RTX, NOC as defence stocks spike on China tension."
        ),
        "keywords": [
            "xi jinping", "xi", "china president", "beijing", "taiwan strait",
            "china stimulus", "pboc", "china trade", "chinese economy",
            "china tariff", "taiwan military", "trade war china",
        ],
        "primary_stocks": {
            "NVDA": ("Nvidia",           "China chip export controls = $15B+ revenue impact"),
            "AAPL": ("Apple",            "90% of products made in China — Xi policy = AAPL"),
            "TSM":  ("TSMC",             "Taiwan = TSMC. Xi Taiwan threats = TSM drops violently"),
            "LMT":  ("Lockheed Martin",  "US-China tensions = defence stocks pump immediately"),
            "FCX":  ("Freeport-McMoRan","Copper = China economy barometer. Xi stimulus = FCX up"),
        },
        "color":  "#B71C1C",
        "bg":     "#FFEBEE",
        "source": "news",
    },

    "mbs": {
        "name":     "MBS (Mohammed bin Salman)",
        "tier":     2,
        "emoji":    "🛢️",
        "priority": 34,
        "role":     "Saudi Crown Prince · OPEC+ de facto leader",
        "why":      (
            "Controls Saudi Aramco and OPEC+ oil production. One OPEC+ "
            "production cut announcement can push oil up 5-10% overnight. "
            "With the Iran war in 2026 disrupting Strait of Hormuz shipping, "
            "MBS statements are critically market-moving for energy stocks "
            "AND the broader inflation outlook. High oil = high inflation = "
            "Fed can't cut rates = tech stocks drop."
        ),
        "hold_thesis": (
            "OPEC cut → BUY XOM, CVX, COP, LNG for 1-4 weeks. "
            "Saudi-US deal (arms for normalization with Israel) = "
            "hold defence stocks (LMT, RTX) for 1-3 months."
        ),
        "sell_thesis": (
            "OPEC production increase or Saudi-Iran peace → SELL oil stocks "
            "immediately. Oil drop = inflation falls = good for tech (buy QQQ). "
            "Sell energy on any ceasefire news in the Middle East."
        ),
        "keywords": [
            "mbs", "mohammed bin salman", "saudi arabia", "opec", "aramco",
            "oil production cut", "opec plus", "saudi vision 2030",
            "saudi us deal", "oil supply",
        ],
        "primary_stocks": {
            "XOM":  ("ExxonMobil",       "OPEC decisions directly set XOM quarterly revenue"),
            "CVX":  ("Chevron",          "Same as Exxon — OPEC output moves all major oil stocks"),
            "LNG":  ("Cheniere Energy",  "Oil prices affect LNG markets together"),
            "GLD":  ("Gold",             "Oil price inflation = gold up as inflation hedge"),
            "SU":   ("Suncor",           "Canadian oil — OPEC price sets Suncor's revenue"),
        },
        "color":  "#33691E",
        "bg":     "#F1F8E9",
        "source": "news",
    },
}

# ── PRIORITY ORDER (for reference / sorting) ──────────────────
# The email sorts by the "priority" field above — lower = shown first.
# Current order:
#   1   = Trump (always first)
#   2   = Bessent (implements Trump policy)
#   3   = Pelosi (most-followed Congress trader)
#   4   = RFK (pharma sector destroyer)
#   5-7 = Active Congress traders (MTG, Rick Scott, Davidson)
#   8-10= Fed officials (Warsh, Powell, Macklem)
#  11-18= Legendary investors (Buffett, Druckenmiller, Ackman, Burry, etc.)
#  19-27= Tech CEOs (Musk, Jensen, Dimon, Altman, Zuckerberg, Cook, Nadella, Ellison, Jassy)
#  28-29= Other big CEOs (Pichai, Bezos)
#  30-32= Canadian figures (Carney, Watsa, Lütke)
#  33-34= Global macro (Xi, MBS)
