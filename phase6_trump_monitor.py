# ============================================================
# TRADING BOT — PHASE 6 (Market Movers Monitor)
#
# Tracks statements from the 20 most market-moving people
# on the planet — right now, in 2026.
#
# When any of them says something that could move stocks,
# you get an email instantly with exactly what to buy,
# what direction the stock will likely move, and why.
#
# ── THE 20 PEOPLE WE TRACK ──────────────────────────────────
#
#  TIER 1 — Can move entire markets with one sentence
#   1. Donald Trump      — President, tariffs, trade, energy
#   2. Elon Musk         — Tesla, SpaceX, X, DOGE, AI
#   3. Kevin Warsh       — New Fed Chair (May 15, 2026), rates
#   4. Jerome Powell     — Outgoing Fed Chair, still on board
#   5. Warren Buffett    — Oracle of Omaha, Berkshire, markets
#
#  TIER 2 — Move sectors or specific stocks significantly
#   6. Jensen Huang      — Nvidia CEO, AI chips, export controls
#   7. Jamie Dimon       — JPMorgan CEO, banking, economy
#   8. Sam Altman        — OpenAI CEO, AI regulation, Microsoft
#   9. Scott Bessent     — Treasury Secretary, tariffs, dollar
#  10. Mark Zuckerberg   — Meta CEO, AI, social media regulation
#
#  TIER 3 — Move their industry or specific companies
#  11. Tim Cook          — Apple CEO, China, supply chain
#  12. Satya Nadella     — Microsoft CEO, Azure, AI, OpenAI
#  13. Andy Jassy        — Amazon CEO, AWS, retail, labour
#  14. Larry Ellison     — Oracle CEO, AI infrastructure, cloud
#  15. RFK Jr (Robert Kennedy Jr) — HHS Secretary, pharma/vaccines
#
#  TIER 4 — Macro, geopolitical, sector specialists
#  16. Xi Jinping        — China President, trade war, Taiwan
#  17. Mario Draghi      — EU economy, Europe policy
#  18. MBS (Mohammed bin Salman) — Saudi Arabia, OPEC, oil
#  19. Cathie Wood       — ARK Invest, tech/innovation, sentiment
#  20. Michael Burry     — Short seller, market crash signals
#
# ── DATA SOURCES (all free, all work from GitHub Actions) ───
#  • CNN Truth Social Archive — Trump posts, 5-min updates
#  • trumpstruth.org RSS     — Backup Trump source
#  • Google News RSS         — All 20 people, real-time news
#  • Yahoo Finance RSS       — Market-moving quotes + headlines
#
# ── WHAT YOU GET IN EVERY EMAIL ─────────────────────────────
#  • WHO said it (photo emoji, tier, why they matter)
#  • WHAT they said (the exact quote/headline)
#  • WHICH stocks move (ticker, company name, direction)
#  • WHY it matters (plain English, no jargon)
#  • WHAT TO DO (specific action for your TFSA)
#  • HOW LONG TO HOLD (and the exit signal)
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

SEEN_FILE = "/tmp/phase6_seen.json"
HEADERS   = {
    "User-Agent": "Mozilla/5.0 (compatible; TradingBot/6.0; research)",
    "Accept":     "application/json, text/html, application/xml, */*",
}


# ══════════════════════════════════════════════════════════════
# THE 20 MARKET MOVERS
#
# Each person has:
#   tier       — 1 (moves whole market) to 4 (moves sectors)
#   emoji      — visual identifier in emails
#   role       — current title as of May 2026
#   why        — why they move markets
#   keywords   — words that identify their statements in news
#   stocks     — stocks most affected by their statements
#   sentiment_bias — does positive news from them = markets up?
# ══════════════════════════════════════════════════════════════

MARKET_MOVERS = {

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 1 — MOVES ENTIRE MARKET WITH ONE SENTENCE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    "trump": {
        "name":    "Donald Trump",
        "tier":    1,
        "emoji":   "🇺🇸",
        "role":    "47th US President",
        "why":     "Controls tariffs, trade deals, energy policy, sanctions, and regulatory appointments. Single most market-moving person alive. A single Truth Social post has moved the S&P 500 by 3-5% in minutes.",
        "keywords": ["trump", "donald trump", "white house", "president trump", "truth social", "mar-a-lago", "executive order", "tariff", "trade deal"],
        "primary_stocks": {
            "SPY":  ("S&P 500 ETF",    "Broad market — moves on anything Trump says about economy"),
            "XOM":  ("ExxonMobil",     "'Drill baby drill' — Trump loves US energy production"),
            "LMT":  ("Lockheed Martin","Defence spending — Trump = more military contracts"),
            "DJT":  ("Trump Media",    "His own company — pumps on any positive Trump attention"),
            "COIN": ("Coinbase",       "Trump is pro-crypto — any crypto policy statement"),
        },
        "color": "#B71C1C",
        "bg":    "#FFEBEE",
        "source": "truth_social",
    },

    "musk": {
        "name":    "Elon Musk",
        "tier":    1,
        "emoji":   "🚀",
        "role":    "CEO Tesla/SpaceX/X · DOGE Advisor",
        "why":     "Owns Tesla, SpaceX, X (Twitter). His tweets have moved markets billions of dollars in minutes. SpaceX IPO coming in 2026. DOGE government cuts affect defence and gov't contractor stocks. Musk-Trump relationship is the most powerful in business.",
        "keywords": ["elon musk", "elon", "musk", "tesla", "spacex", "x.com", "doge", "grok", "xai", "starship", "starlink", "neuralink", "optimus robot"],
        "primary_stocks": {
            "TSLA": ("Tesla",          "His flagship company — every Musk statement moves TSLA"),
            "RKLB": ("Rocket Lab",     "SpaceX competitor — SpaceX news affects the whole sector"),
            "DOGE": ("Dogecoin proxy", "Musk invented the DOGE meme — crypto pumps on his mentions"),
            "NVDA": ("Nvidia",         "xAI uses Nvidia chips — Grok/AI news moves NVDA"),
        },
        "color": "#1a1a2e",
        "bg":    "#E8EAF6",
        "source": "news",
    },

    "warsh": {
        "name":    "Kevin Warsh",
        "tier":    1,
        "emoji":   "🏦",
        "role":    "New Federal Reserve Chair (from May 15, 2026)",
        "why":     "Replacing Jerome Powell as Fed Chair on May 15, 2026. Controls US interest rates — the single most important variable for ALL stock valuations. Warsh wants to shrink the Fed's $6.7 trillion balance sheet, which could push rates UP. First statements as Chair will be enormously market-moving. Every word he says will be analysed by every trader on earth.",
        "keywords": ["kevin warsh", "warsh", "federal reserve", "fed chair", "fomc", "interest rate", "rate cut", "rate hike", "quantitative", "balance sheet", "monetary policy", "fed meeting"],
        "primary_stocks": {
            "JPM":  ("JPMorgan Chase", "Banks love rate clarity — Warsh statements move all banks"),
            "SPY":  ("S&P 500",        "Rate changes affect every stock — broad market impact"),
            "GLD":  ("Gold ETF",       "Gold moves inversely to rate expectations"),
            "TLT":  ("Treasury Bonds", "Bond prices move directly on Fed balance sheet decisions"),
            "SCHW": ("Charles Schwab", "Brokerage stocks sensitive to interest rate environment"),
        },
        "color": "#0d47a1",
        "bg":    "#E3F2FD",
        "source": "news",
    },

    "powell": {
        "name":    "Jerome Powell",
        "tier":    1,
        "emoji":   "🏛️",
        "role":    "Outgoing Fed Chair · Fed Governor until 2028",
        "why":     "Still on the Fed board after stepping down as Chair May 15. His votes and public statements can contradict new Chair Warsh, creating market confusion and volatility. Described as potentially the most disruptive 'ex-chair still in the room' in Fed history.",
        "keywords": ["jerome powell", "powell", "fed governor", "fomc vote", "rate decision", "inflation target", "federal reserve"],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "Broad market — rate uncertainty = volatility across all stocks"),
            "TLT":  ("Treasury Bonds", "Bond yields react immediately to Powell statements"),
            "GLD":  ("Gold",           "Safe haven — uncertainty from Powell vs Warsh = gold up"),
        },
        "color": "#37474f",
        "bg":    "#ECEFF1",
        "source": "news",
    },

    "buffett": {
        "name":    "Warren Buffett",
        "tier":    1,
        "emoji":   "🏆",
        "role":    "CEO Berkshire Hathaway · Oracle of Omaha",
        "why":     "When Buffett speaks, institutions listen. He predicted the 2025 market rout by selling $134B in stocks in 2024 and holding $334B cash. Up $12.7B in 2026 while others lost billions. When he buys or sells, the stock moves 10-30%. His annual letter and Berkshire AGM move markets globally.",
        "keywords": ["warren buffett", "buffett", "berkshire hathaway", "berkshire", "omaha", "value investing", "oracle of omaha", "buy american", "annual letter"],
        "primary_stocks": {
            "BRK.B":("Berkshire Hathaway","His company — any Buffett news moves BRK directly"),
            "AAPL": ("Apple",          "Berkshire's #1 holding — Buffett buy/sell = AAPL moves"),
            "BAC":  ("Bank of America","Major Berkshire holding — Buffett banking stance matters"),
            "OXY":  ("Occidental Petroleum","Buffett's oil bet — he's been buying heavily"),
            "KO":   ("Coca-Cola",      "Classic Buffett holding since 1988 — long-term signal"),
        },
        "color": "#1B5E20",
        "bg":    "#E8F5E9",
        "source": "news",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 2 — MOVE SECTORS OR SPECIFIC STOCKS SIGNIFICANTLY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    "jensen": {
        "name":    "Jensen Huang",
        "tier":    2,
        "emoji":   "🤖",
        "role":    "CEO Nvidia · King of AI Chips",
        "why":     "Controls the picks-and-shovels of the AI gold rush. Every data centre being built uses Nvidia chips. His guidance calls move NVDA 10-20% in after-hours. Export controls on chips to China = $15B+ revenue impact. His word is law in AI.",
        "keywords": ["jensen huang", "jensen", "nvidia", "h100", "h200", "blackwell", "cuda", "gpu", "ai chip", "data center chip", "export control chip"],
        "primary_stocks": {
            "NVDA": ("Nvidia",         "His company — Jensen statements are the #1 NVDA catalyst"),
            "AMD":  ("AMD",            "Nvidia competitor — NVDA news moves AMD in same direction"),
            "SMCI": ("Super Micro",    "Builds servers using Nvidia GPUs — moves with NVDA"),
            "DELL": ("Dell",           "Major AI server vendor — moves with AI infrastructure news"),
        },
        "color": "#4527A0",
        "bg":    "#EDE7F6",
        "source": "news",
    },

    "dimon": {
        "name":    "Jamie Dimon",
        "tier":    2,
        "emoji":   "🏦",
        "role":    "CEO JPMorgan Chase · Wall Street's most powerful banker",
        "why":     "Head of the world's most systemically important bank. His warnings about recessions, credit crises, and market bubbles carry enormous weight. In May 2026 warned about an overdue credit recession. When Dimon talks, markets listen — he usually knows something.",
        "keywords": ["jamie dimon", "dimon", "jpmorgan", "jp morgan", "chase bank", "credit recession", "banking crisis", "wall street warning", "financial crisis"],
        "primary_stocks": {
            "JPM":  ("JPMorgan Chase", "His own bank — always moves most on his statements"),
            "BAC":  ("Bank of America","All big banks move together on credit/economy warnings"),
            "GS":   ("Goldman Sachs",  "Investment banking — moves with financial sector warnings"),
            "XLF":  ("Financial ETF",  "The whole financial sector moves on Dimon's economic calls"),
        },
        "color": "#004D40",
        "bg":    "#E0F2F1",
        "source": "news",
    },

    "altman": {
        "name":    "Sam Altman",
        "tier":    2,
        "emoji":   "🧠",
        "role":    "CEO OpenAI · Father of ChatGPT",
        "why":     "Controls the world's most influential AI company. Microsoft owns ~49% of OpenAI. Every OpenAI product launch, funding round, or regulation statement moves MSFT, NVDA, and the entire AI sector. In 2026, his Musk trial testimony is market-moving. AI regulation = his word matters.",
        "keywords": ["sam altman", "altman", "openai", "chatgpt", "gpt-5", "gpt5", "o3", "o4", "ai regulation", "openai funding", "artificial general intelligence", "agi"],
        "primary_stocks": {
            "MSFT": ("Microsoft",      "Owns ~49% of OpenAI — direct beneficiary of OpenAI success"),
            "NVDA": ("Nvidia",         "OpenAI runs on Nvidia chips — NVDA moves on OpenAI news"),
            "GOOGL":("Alphabet",       "OpenAI's biggest competitor — competitive threat signals"),
            "PLTR": ("Palantir",       "AI for enterprise — sector moves with OpenAI milestones"),
        },
        "color": "#00695C",
        "bg":    "#E0F7FA",
        "source": "news",
    },

    "bessent": {
        "name":    "Scott Bessent",
        "tier":    2,
        "emoji":   "💰",
        "role":    "US Treasury Secretary",
        "why":     "Controls tariff negotiations, dollar policy, and US debt management. The person who actually implements Trump's trade war. His statements on China tariffs, trade deals, and the dollar directly affect global markets. He can pause or escalate tariffs unilaterally.",
        "keywords": ["scott bessent", "bessent", "treasury secretary", "treasury department", "tariff negotiation", "trade deal", "us dollar", "debt ceiling", "treasury bonds"],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "Tariff pauses or escalations = broad market move"),
            "WMT":  ("Walmart",        "Tariffs hit retail supply chains — Bessent news moves retail"),
            "AAPL": ("Apple",          "China tariff deals directly impact Apple supply chain"),
            "UUP":  ("US Dollar ETF",  "Treasury policy = dollar strength or weakness"),
        },
        "color": "#4A148C",
        "bg":    "#F3E5F5",
        "source": "news",
    },

    "zuckerberg": {
        "name":    "Mark Zuckerberg",
        "tier":    2,
        "emoji":   "📱",
        "role":    "CEO Meta Platforms · Facebook/Instagram/WhatsApp",
        "why":     "Controls the world's largest social network. Meta's ad revenue is a direct barometer of the entire economy. Zuckerberg's AI push (Llama) is his bid to rival OpenAI. Any antitrust ruling, ad regulation, or AI product launch moves META significantly.",
        "keywords": ["mark zuckerberg", "zuckerberg", "meta", "facebook", "instagram", "whatsapp", "llama", "threads", "metaverse", "ray-ban meta", "antitrust meta"],
        "primary_stocks": {
            "META": ("Meta Platforms", "His company — every statement moves META directly"),
            "SNAP": ("Snapchat",       "Direct Meta competitor — moves inversely to Meta news"),
            "GOOGL":("Alphabet",       "Ad revenue competitor — Meta vs Google ad news matters"),
        },
        "color": "#1565C0",
        "bg":    "#E3F2FD",
        "source": "news",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 3 — MOVE THEIR INDUSTRY OR SPECIFIC COMPANIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    "cook": {
        "name":    "Tim Cook",
        "tier":    3,
        "emoji":   "🍎",
        "role":    "CEO Apple Inc.",
        "why":     "Apple is the world's most valuable company. Cook's China relationship, supply chain commentary, and product announcements move AAPL 3-8%. Apple Intelligence (AI) launch = AAPL re-rating story for 2026.",
        "keywords": ["tim cook", "tim apple", "apple ceo", "apple earnings", "apple china", "iphone sales", "apple intelligence", "apple vision"],
        "primary_stocks": {
            "AAPL": ("Apple",          "His company — Cook statements are the #1 AAPL catalyst"),
            "QCOM": ("Qualcomm",       "Makes chips for iPhone — AAPL supply chain moves QCOM"),
            "TSM":  ("TSMC",           "Makes all Apple chips — AAPL demand = TSM revenue"),
        },
        "color": "#212121",
        "bg":    "#F5F5F5",
        "source": "news",
    },

    "nadella": {
        "name":    "Satya Nadella",
        "tier":    3,
        "emoji":   "☁️",
        "role":    "CEO Microsoft · Azure Cloud · Copilot AI",
        "why":     "Microsoft is the world's second most valuable company. Azure cloud + OpenAI partnership = AI plays through MSFT. Copilot is being embedded into every Office product used by 1.4 billion people. His AI guidance moves MSFT 3-6%.",
        "keywords": ["satya nadella", "nadella", "microsoft ceo", "azure", "copilot", "office ai", "teams", "activision", "bing ai"],
        "primary_stocks": {
            "MSFT": ("Microsoft",      "His company — Nadella statements move MSFT directly"),
            "NVDA": ("Nvidia",         "Azure runs on Nvidia chips — MSFT cloud growth = NVDA growth"),
        },
        "color": "#01579B",
        "bg":    "#E1F5FE",
        "source": "news",
    },

    "jassy": {
        "name":    "Andy Jassy",
        "tier":    3,
        "emoji":   "📦",
        "role":    "CEO Amazon · AWS Cloud",
        "why":     "AWS is the world's largest cloud provider (31% market share). Amazon's retail + logistics business is the world's largest. Jassy's commentary on AI spending, AWS growth, and consumer demand is a bellwether for the entire tech and retail sector.",
        "keywords": ["andy jassy", "jassy", "amazon ceo", "aws", "amazon web services", "amazon prime", "amazon earnings", "fulfillment"],
        "primary_stocks": {
            "AMZN": ("Amazon",         "His company — Jassy statements move AMZN directly"),
            "MSFT": ("Microsoft",      "Azure competitor — AWS growth commentary moves MSFT inversely"),
        },
        "color": "#E65100",
        "bg":    "#FFF3E0",
        "source": "news",
    },

    "ellison": {
        "name":    "Larry Ellison",
        "tier":    3,
        "emoji":   "🗄️",
        "role":    "CTO & Co-founder Oracle",
        "why":     "Oracle has become the surprise winner of the AI infrastructure boom. Major cloud contracts with OpenAI, xAI, and the US government. ORCL up 80%+ as AI companies race to store data. Ellison's announcements of new AI data centre deals have moved ORCL 10-20%.",
        "keywords": ["larry ellison", "ellison", "oracle", "orcl", "oracle cloud", "oracle ai", "ellison foundation", "oracle health"],
        "primary_stocks": {
            "ORCL": ("Oracle",         "His company — Ellison deal announcements move ORCL 10-20%"),
            "MSFT": ("Microsoft",      "Oracle-Microsoft partnership on AI infrastructure"),
        },
        "color": "#B71C1C",
        "bg":    "#FFEBEE",
        "source": "news",
    },

    "rfk": {
        "name":    "Robert F Kennedy Jr (RFK)",
        "tier":    3,
        "emoji":   "💊",
        "role":    "HHS Secretary · Vaccine Skeptic",
        "why":     "Controls the FDA, CDC, and NIH. His anti-vaccine stance has directly impacted pharma stocks. Any FDA approval slowing, vaccine mandate rollback, or drug pricing policy change comes through RFK. Moderna lost 40% after he was confirmed. He is the most dangerous person to pharma stocks.",
        "keywords": ["rfk", "rfk jr", "robert kennedy", "kennedy hhs", "fda approval", "vaccine mandate", "hhs secretary", "cdc policy", "drug approval", "make america healthy"],
        "primary_stocks": {
            "MRNA": ("Moderna",        "RFK is the biggest threat to vaccine revenue — MRNA drops on his statements"),
            "PFE":  ("Pfizer",         "Vaccine + drug revenue at risk from RFK regulatory stance"),
            "LLY":  ("Eli Lilly",      "FDA drug approval pace directly affected by RFK at HHS"),
            "UNH":  ("UnitedHealth",   "Healthcare policy overhaul = UNH moves on RFK statements"),
        },
        "color": "#880E4F",
        "bg":    "#FCE4EC",
        "source": "news",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 4 — MACRO, GEOPOLITICAL, SENTIMENT LEADERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    "xi": {
        "name":    "Xi Jinping",
        "tier":    4,
        "emoji":   "🐉",
        "role":    "President of China · Communist Party General Secretary",
        "why":     "Controls the world's second largest economy. China-US trade war, Taiwan tensions, chip export bans, and TikTok fate all flow through Xi. A single Taiwan military statement can drop global markets 5%. China stimulus announcements pump commodity and EV stocks.",
        "keywords": ["xi jinping", "xi", "china president", "beijing", "taiwan strait", "china stimulus", "pboc", "china trade", "chinese economy", "trade war china"],
        "primary_stocks": {
            "NVDA": ("Nvidia",         "China chip export controls = $15B+ revenue impact on NVDA"),
            "AAPL": ("Apple",          "Apple makes 90% of products in China — Xi policy = AAPL"),
            "TSM":  ("TSMC",           "Taiwan = TSMC. Xi Taiwan threats move TSM violently"),
            "LMT":  ("Lockheed Martin","US-China tensions = defence stocks immediately pump"),
        },
        "color": "#B71C1C",
        "bg":    "#FFEBEE",
        "source": "news",
    },

    "mbs": {
        "name":    "MBS (Mohammed bin Salman)",
        "tier":    4,
        "emoji":   "🛢️",
        "role":    "Saudi Crown Prince · OPEC de facto leader",
        "why":     "Controls Saudi Aramco and OPEC+ oil production decisions. One OPEC+ production cut can push oil up 5-10% overnight. With the Iran war in 2026, oil market is already volatile — MBS statements are critically market-moving for energy stocks and the entire inflation outlook.",
        "keywords": ["mbs", "mohammed bin salman", "saudi arabia", "opec", "aramco", "oil production", "oil cut", "opec plus", "saudi vision 2030", "crude oil decision"],
        "primary_stocks": {
            "XOM":  ("ExxonMobil",     "Oil production decisions directly set XOM revenue"),
            "CVX":  ("Chevron",        "Same as Exxon — OPEC output moves all major oil stocks"),
            "LNG":  ("Cheniere Energy","Oil prices affect natural gas and LNG markets together"),
            "GLD":  ("Gold",           "Oil price inflation = gold up as inflation hedge"),
        },
        "color": "#33691E",
        "bg":    "#F1F8E9",
        "source": "news",
    },

    "cathie": {
        "name":    "Cathie Wood",
        "tier":    4,
        "emoji":   "📈",
        "role":    "CEO ARK Invest · Innovation investor",
        "why":     "ARK ETFs hold billions in disruptive tech. When ARK buys or sells, it signals conviction on future tech. Her price targets (Tesla $2000, Bitcoin $1.5M) move retail investor sentiment massively. ARK buy/sell filings are watched daily by millions of retail investors.",
        "keywords": ["cathie wood", "cathie", "ark invest", "ark etf", "arkk", "ark buy", "ark sell", "innovation etf", "disruptive technology"],
        "primary_stocks": {
            "TSLA": ("Tesla",          "ARK's biggest holding — Cathie buy/sell moves TSLA"),
            "COIN": ("Coinbase",       "Major ARK holding — ARK crypto conviction moves COIN"),
            "RBLX": ("Roblox",         "ARK gaming/metaverse play — held in ARKK"),
            "ROKU": ("Roku",           "Streaming tech — major ARK holding"),
        },
        "color": "#0277BD",
        "bg":    "#E1F5FE",
        "source": "news",
    },

    "burry": {
        "name":    "Michael Burry",
        "tier":    4,
        "emoji":   "🐻",
        "role":    "Scion Asset Management · 'The Big Short' investor",
        "why":     "Famous for predicting and profiting from the 2008 housing crash. When Burry tweets or files a 13F showing massive short positions, markets pay attention. He predicted the 2022 crash, and his current warnings about US debt are being watched carefully in 2026.",
        "keywords": ["michael burry", "burry", "scion", "big short", "burry short", "market crash warning", "13f burry", "put options burry"],
        "primary_stocks": {
            "SPY":  ("S&P 500",        "His broad market shorts affect sentiment across all stocks"),
            "GLD":  ("Gold",           "Burry holds gold as inflation/crash hedge — moves on his buys"),
            "GME":  ("GameStop",       "Burry famously made GME famous — retail follows his GME moves"),
        },
        "color": "#37474F",
        "bg":    "#ECEFF1",
        "source": "news",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CANADA — MARKET MOVERS AFFECTING TSX + TFSA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    "carney": {
        "name":    "Mark Carney",
        "tier":    2,
        "emoji":   "🍁",
        "role":    "Prime Minister of Canada (2025–)",
        "why":     "Former Bank of Canada and Bank of England governor. Now Canada's PM. His trade policy with the US (tariffs, USMCA), carbon tax decisions, and housing policy directly affect the entire TSX. The Trump-Carney relationship is the most important bilateral relationship for Canadian stocks. Any Canada-US trade statement = TSX moves.",
        "keywords": ["mark carney", "carney", "prime minister canada", "canadian government", "usmca canada", "canada tariff", "canada trade", "carbon tax canada"],
        "primary_stocks": {
            "SHOP": ("Shopify",        "Canada's most valuable company — trade policy affects SHOP"),
            "ENB":  ("Enbridge",       "Pipeline policy = Carney's biggest energy decision"),
            "RY":   ("Royal Bank",     "Canada's biggest bank — moves on PM economic policy"),
            "XIU":  ("iShares S&P/TSX","Entire TSX ETF — Carney macro policy = broad Canada move"),
            "SU":   ("Suncor Energy",  "Oil sands — Canadian energy policy affects SU directly"),
        },
        "color": "#B71C1C",
        "bg":    "#FFEBEE",
        "source": "news",
    },

    "macklem": {
        "name":    "Tiff Macklem",
        "tier":    2,
        "emoji":   "🏦",
        "role":    "Governor, Bank of Canada",
        "why":     "Canada's equivalent of the Fed Chair. Controls Canadian interest rates. Rate decisions move ALL Canadian bank stocks (RY, TD, BNS, BMO, CM) plus the housing market and REIT sector. Bank of Canada rate decisions happen 8 times per year and each one moves the TSX.",
        "keywords": ["tiff macklem", "macklem", "bank of canada", "boc rate", "canadian interest rate", "boc decision", "overnight rate canada", "canadian inflation"],
        "primary_stocks": {
            "RY":   ("Royal Bank",     "Largest Canadian bank — rate moves hit RY hardest"),
            "TD":   ("TD Bank",        "Second largest — rates affect mortgage book"),
            "BNS":  ("Scotiabank",     "Big Five bank — rate sensitive"),
            "BMO":  ("BMO",            "Big Five bank — rate sensitive"),
            "REI.UN":("RioCan REIT",   "Canadian real estate — rates directly = REIT values"),
        },
        "color": "#0d47a1",
        "bg":    "#E3F2FD",
        "source": "news",
    },

    "watsa": {
        "name":    "Prem Watsa",
        "tier":    3,
        "emoji":   "🦁",
        "role":    "CEO Fairfax Financial · Canada's Warren Buffett",
        "why":     "Known as Canada's Warren Buffett. Fairfax Financial holds massive positions in Canadian and global stocks. When Watsa makes a large buy or sell, Bay Street follows. His macro calls on inflation and interest rates have been remarkably accurate. 13F filings watched by every Canadian institutional investor.",
        "keywords": ["prem watsa", "watsa", "fairfax financial", "fairfax", "blackberry fairfax", "watsa buys", "watsa sells"],
        "primary_stocks": {
            "FFH":  ("Fairfax Financial","His company — Watsa statements move FFH directly on TSX"),
            "BB":   ("BlackBerry",     "Fairfax is BlackBerry's largest shareholder"),
            "RY":   ("Royal Bank",     "Fairfax holds Canadian financials — moves on Watsa macro calls"),
        },
        "color": "#4527A0",
        "bg":    "#EDE7F6",
        "source": "news",
    },

    "thomson": {
        "name":    "David Thomson",
        "tier":    4,
        "emoji":   "📰",
        "role":    "Chair Thomson Reuters · Richest Canadian",
        "why":     "Canada's richest person. Thomson Reuters controls global financial data and news infrastructure. TRI.TO is a proxy for global information services. Thomson family moves at Woodbridge (holding company) affect TRI and broader Canadian market sentiment.",
        "keywords": ["david thomson", "thomson reuters", "woodbridge", "thomson family", "tri", "reuters"],
        "primary_stocks": {
            "TRI":  ("Thomson Reuters", "His family company — Thomson news moves TRI on NYSE/TSX"),
        },
        "color": "#1B5E20",
        "bg":    "#E8F5E9",
        "source": "news",
    },
}


# ══════════════════════════════════════════════════════════════
# COMPANY → TICKER SIGNAL MAP
# When any of these words appear in a statement, the listed
# stocks are flagged. This works across ALL 20 people.
# ══════════════════════════════════════════════════════════════

TICKER_SIGNALS = {
    # Direction: "up", "down", "watch"
    "tariff":         [("SPY","down"),("WMT","down"),("AAPL","down"),("XOM","up")],
    "tariffs":        [("SPY","down"),("WMT","down"),("AAPL","down"),("XOM","up")],
    "trade deal":     [("SPY","up"),("AAPL","up"),("NVDA","up"),("WMT","up")],
    "rate cut":       [("SPY","up"),("TLT","up"),("JPM","up"),("GLD","watch")],
    "rate hike":      [("SPY","down"),("TLT","down"),("GLD","up"),("USD","up")],
    "interest rate":  [("SPY","watch"),("JPM","watch"),("TLT","watch")],
    "bitcoin":        [("COIN","up"),("MSTR","up"),("MARA","up"),("RIOT","up")],
    "crypto":         [("COIN","up"),("HOOD","up"),("MSTR","up")],
    "oil":            [("XOM","up"),("CVX","up"),("COP","up"),("LNG","up")],
    "drill":          [("XOM","up"),("CVX","up"),("COP","up")],
    "opec":           [("XOM","watch"),("CVX","watch"),("USO","watch")],
    "china":          [("NVDA","down"),("AAPL","down"),("TSM","down"),("LMT","up")],
    "taiwan":         [("TSM","down"),("NVDA","down"),("LMT","up"),("RTX","up")],
    "nvidia":         [("NVDA","watch"),("AMD","watch"),("SMCI","watch")],
    "ai":             [("NVDA","up"),("MSFT","up"),("GOOGL","up"),("PLTR","up")],
    "artificial intelligence": [("NVDA","up"),("MSFT","up"),("META","up")],
    "spacex":         [("RKLB","watch"),("BA","watch"),("LMT","watch")],
    "tesla":          [("TSLA","watch")],
    "apple":          [("AAPL","watch"),("QCOM","watch"),("TSM","watch")],
    "amazon":         [("AMZN","watch"),("MSFT","watch")],
    "microsoft":      [("MSFT","watch"),("NVDA","watch")],
    "google":         [("GOOGL","watch"),("META","watch")],
    "meta":           [("META","watch"),("SNAP","watch")],
    "openai":         [("MSFT","up"),("NVDA","up"),("GOOGL","down")],
    "vaccine":        [("MRNA","down"),("PFE","down"),("BNTX","down")],
    "drug":           [("LLY","watch"),("PFE","watch"),("MRK","watch")],
    "pharma":         [("LLY","watch"),("PFE","watch"),("ABBV","watch")],
    "defence":        [("LMT","up"),("RTX","up"),("NOC","up"),("GD","up")],
    "defense":        [("LMT","up"),("RTX","up"),("NOC","up"),("GD","up")],
    "military":       [("LMT","up"),("RTX","up"),("NOC","up")],
    "nuclear":        [("CEG","up"),("VST","up"),("CCJ","up")],
    "solar":          [("FSLR","up"),("ENPH","up"),("NEE","up")],
    "energy":         [("XOM","watch"),("CVX","watch"),("NEE","watch"),("ENB","watch"),("SU","watch")],
    "recession":      [("GLD","up"),("TLT","up"),("SPY","down"),("XIU","down")],
    "inflation":      [("GLD","up"),("TLT","down"),("SPY","down")],
    "deal":           [("SPY","up"),("DJT","watch"),("XIU","up")],
    "sanction":       [("XOM","up"),("LMT","up"),("RTX","up")],
    "ban":            [("NVDA","watch"),("SPY","watch")],
    "steel":          [("X","up"),("NUE","up")],
    "gold":           [("GLD","up"),("NEM","up"),("ABX","up")],
    "bank":           [("JPM","watch"),("BAC","watch"),("GS","watch"),("RY","watch"),("TD","watch")],
    # ── Canada-specific signals ──────────────────────────────
    "shopify":        [("SHOP","watch")],
    "canada":         [("ENB","watch"),("SU","watch"),("SHOP","watch"),("RY","watch"),("TD","watch"),("CNR","watch")],
    "canadian":       [("ENB","watch"),("SU","watch"),("CP","watch"),("CNR","watch")],
    "bank of canada": [("RY","watch"),("TD","watch"),("BNS","watch"),("BMO","watch"),("CM","watch")],
    "interest rate canada": [("RY","watch"),("TD","watch"),("XIU","watch")],
    "tsx":            [("XIU","watch"),("SHOP","watch"),("RY","watch")],
    "pipeline":       [("ENB","up"),("TRP","up"),("PPL","up")],
    "oil sands":      [("SU","up"),("CNQ","up"),("IMO","up")],
    "potash":         [("NTR","watch"),("MOS","watch")],
    "lumber":         [("WFG","watch"),("WY","watch")],
    "railways":       [("CNR","watch"),("CP","watch")],
    "housing canada": [("RY","watch"),("TD","watch"),("BNS","watch")],
    "mark carney":    [("RY","watch"),("TD","watch"),("SHOP","watch"),("XIU","watch")],
    "carney":         [("RY","watch"),("TD","watch"),("XIU","watch")],
    "tariff canada":  [("SHOP","down"),("CNR","down"),("SU","watch"),("ENB","watch")],
    "usmca":          [("GM","watch"),("F","watch"),("ENB","watch"),("SU","watch")],
}

TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')


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
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_set)[-4000:], f)
    except Exception:
        pass


def item_hash(content, source):
    return hashlib.md5(f"{source}:{content[:120]}".encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
# DATA SOURCES
# ══════════════════════════════════════════════════════════════

def fetch_trump_truth_social():
    """CNN's live Trump Truth Social archive — updated every 5 min."""
    posts = []
    try:
        r = requests.get(
            "https://ix.cnn.io/data/truth-social/truth_archive.json",
            headers=HEADERS, timeout=25
        )
        if r.status_code != 200:
            return []

        data   = r.json()
        items  = data if isinstance(data, list) else data.get("posts", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

        for item in items[:150]:
            try:
                content = re.sub(r'<[^>]+>', ' ', item.get("content", item.get("text", "")))
                content = re.sub(r'\s+', ' ', content).strip()
                if not content or len(content) < 15:
                    continue
                ts = item.get("created_at", "")
                try:
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    t = datetime.now(timezone.utc) - timedelta(minutes=30)
                if t < cutoff:
                    break
                posts.append({
                    "person_key": "trump",
                    "content":    content,
                    "time":       t,
                    "url":        item.get("url", "https://truthsocial.com/@realDonaldTrump"),
                    "source":     "Truth Social",
                    "likes":      item.get("favourites_count", 0),
                    "reposts":    item.get("reblogs_count", 0),
                })
            except Exception:
                pass

        print(f"  Truth Social (CNN): {len(posts)} new posts")
    except Exception as e:
        print(f"  Truth Social error: {e}")
    return posts


def fetch_trumpstruth_rss():
    """Backup Trump source: trumpstruth.org RSS."""
    posts = []
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        yest  = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        r = requests.get(
            f"https://www.trumpstruth.org/feed?start_date={yest}&end_date={today}",
            headers=HEADERS, timeout=20
        )
        if r.status_code != 200:
            return []
        root   = ET.fromstring(r.content)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        for item in root.findall(".//item")[:30]:
            try:
                content = re.sub(r'<[^>]+>', ' ', item.findtext("description") or item.findtext("title") or "")
                content = re.sub(r'\s+', ' ', content).strip()
                if not content:
                    continue
                from email.utils import parsedate_to_datetime
                try:
                    t = parsedate_to_datetime(item.findtext("pubDate") or "")
                    if t.tzinfo is None:
                        t = t.replace(tzinfo=timezone.utc)
                except Exception:
                    t = datetime.now(timezone.utc) - timedelta(hours=1)
                if t < cutoff:
                    continue
                posts.append({
                    "person_key": "trump",
                    "content":    content,
                    "time":       t,
                    "url":        item.findtext("link") or "https://trumpstruth.org",
                    "source":     "Truth Social (trumpstruth.org)",
                    "likes":      0,
                    "reposts":    0,
                })
            except Exception:
                pass
        print(f"  trumpstruth.org: {len(posts)} posts")
    except Exception as e:
        print(f"  trumpstruth.org error: {e}")
    return posts


def fetch_google_news_for_person(person_key, person_data):
    """Fetch Google News RSS for a specific market mover."""
    articles = []
    name     = person_data["name"]
    keywords = person_data["keywords"]

    # Use first 2 keywords as search queries
    queries = [name, keywords[0]] if len(keywords) > 1 else [name]

    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)

    for query in queries[:2]:
        try:
            encoded = requests.utils.quote(f"{query} stock market")
            url     = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            r       = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue

            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                try:
                    title   = item.findtext("title") or ""
                    desc    = re.sub(r'<[^>]+>', '', item.findtext("description") or "")
                    link    = item.findtext("link") or ""
                    pub     = item.findtext("pubDate") or ""
                    src     = item.findtext("source") or "Google News"

                    content = f"{title}. {desc}".strip()

                    # Must actually mention the person
                    name_lower = name.lower()
                    if not any(kw in content.lower() for kw in keywords[:3]):
                        continue

                    from email.utils import parsedate_to_datetime
                    try:
                        t = parsedate_to_datetime(pub)
                        if t.tzinfo is None:
                            t = t.replace(tzinfo=timezone.utc)
                    except Exception:
                        t = datetime.now(timezone.utc) - timedelta(hours=2)

                    if t < cutoff:
                        continue

                    articles.append({
                        "person_key": person_key,
                        "content":    content,
                        "time":       t,
                        "url":        link,
                        "source":     f"Google News ({src})",
                        "likes":      0,
                        "reposts":    0,
                    })
                except Exception:
                    pass

            time.sleep(0.3)
        except Exception:
            pass

    return articles


def fetch_yahoo_finance_rss():
    """Yahoo Finance RSS — broad market news with influential person mentions."""
    articles = []
    feeds = [
        "https://finance.yahoo.com/rss/topstories",
        "https://finance.yahoo.com/rss/headline?s=SPY",
    ]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)

    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:15]:
                try:
                    title   = item.findtext("title") or ""
                    desc    = re.sub(r'<[^>]+>', '', item.findtext("description") or "")
                    link    = item.findtext("link") or ""
                    pub     = item.findtext("pubDate") or ""
                    content = f"{title}. {desc}".strip()

                    from email.utils import parsedate_to_datetime
                    try:
                        t = parsedate_to_datetime(pub)
                        if t.tzinfo is None:
                            t = t.replace(tzinfo=timezone.utc)
                    except Exception:
                        t = datetime.now(timezone.utc) - timedelta(hours=1)

                    if t < cutoff:
                        continue

                    # Identify which person this is about
                    person_key = None
                    content_lower = content.lower()
                    for pk, pd in MARKET_MOVERS.items():
                        if any(kw in content_lower for kw in pd["keywords"][:3]):
                            person_key = pk
                            break

                    if not person_key:
                        continue

                    articles.append({
                        "person_key": person_key,
                        "content":    content,
                        "time":       t,
                        "url":        link,
                        "source":     "Yahoo Finance",
                        "likes":      0,
                        "reposts":    0,
                    })
                except Exception:
                    pass
            time.sleep(0.5)
        except Exception as e:
            pass

    print(f"  Yahoo Finance: {len(articles)} relevant articles")
    return articles


# ══════════════════════════════════════════════════════════════
# MARKET IMPACT ANALYSER
# ══════════════════════════════════════════════════════════════

def analyse(item):
    """
    Given a news item with a person_key, determine market impact.
    Returns enriched dict or None if not market-relevant.
    """
    person    = MARKET_MOVERS.get(item["person_key"])
    if not person:
        return None

    content_lower = item["content"].lower()
    content_raw   = item["content"]

    # ── Find affected stocks ──────────────────────────────────
    affected = {}  # ticker → {direction, reason}

    # 1. Explicit $TICKER mentions
    for t in TICKER_PATTERN.findall(content_raw):
        if len(t) <= 5:
            affected[t] = {"direction": "watch", "reason": f"Explicitly mentioned ${t}"}

    # 2. Keyword → ticker mapping
    for keyword, ticker_list in TICKER_SIGNALS.items():
        if keyword in content_lower:
            for ticker, direction in ticker_list:
                if ticker not in affected:
                    affected[ticker] = {"direction": direction, "reason": f"Post mentions '{keyword}'"}

    # 3. Person's primary stocks always get flagged
    for ticker, (name, reason) in person["primary_stocks"].items():
        if ticker not in affected:
            affected[ticker] = {"direction": "watch", "reason": reason}

    if not affected:
        return None

    # ── Sentiment analysis ────────────────────────────────────
    positive_words = ["great", "amazing", "deal", "approve", "build", "win", "growth",
                      "boom", "record", "strong", "best", "love", "tremendous", "surge",
                      "rally", "soar", "beat", "profit", "gain", "invest", "buy"]
    negative_words = ["bad", "ban", "tariff", "attack", "crash", "war", "sanction",
                      "recession", "inflation", "fraud", "fail", "drop", "concern",
                      "risk", "threat", "loss", "miss", "cut", "layoff", "crisis"]

    pos = sum(1 for w in positive_words if w in content_lower)
    neg = sum(1 for w in negative_words if w in content_lower)

    if pos > neg + 1:
        sentiment, s_emoji, s_color, s_bg = "BULLISH 📈", "📈", "#0A5D3E", "#D4F5E9"
    elif neg > pos + 1:
        sentiment, s_emoji, s_color, s_bg = "BEARISH 📉", "📉", "#8a1a1a", "#FDECEA"
    else:
        sentiment, s_emoji, s_color, s_bg = "MIXED 👀",  "👀", "#7A4900", "#FEF3DC"

    # ── Urgency ───────────────────────────────────────────────
    tier = person["tier"]
    if tier == 1 and item["source"] == "Truth Social":
        urgency, u_color, u_bg = "🚨 ACT WITHIN MINUTES", "#B71C1C", "#FFCDD2"
    elif tier == 1:
        urgency, u_color, u_bg = "⚡ ACT TODAY",          "#E65100", "#FFE0B2"
    elif tier == 2:
        urgency, u_color, u_bg = "📊 ACT THIS WEEK",      "#1565C0", "#BBDEFB"
    else:
        urgency, u_color, u_bg = "👀 MONITOR",            "#555555", "#F5F5F5"

    # ── What to do ────────────────────────────────────────────
    actions = []
    for ticker, info in list(affected.items())[:5]:
        d = info["direction"]
        if d == "up":
            actions.append(f"<strong>${ticker}</strong> — Consider BUYING. Set -5% stop loss. Target +15-25% gain. Hold max 1-3 days for news-driven trades.")
        elif d == "down":
            actions.append(f"<strong>${ticker}</strong> — Expect a DROP. Do NOT buy immediately. Wait 2-3 days for stability. Then consider entry if fundamentals still good.")
        else:
            actions.append(f"<strong>${ticker}</strong> — WATCH closely. Direction unclear. Wait for confirmation before entering a position.")

    # ── Hold period based on person ───────────────────────────
    hold_periods = {
        "trump":        "1-3 days (Trump news fades fast)",
        "musk":         "1-5 days (Musk pumps are short-lived)",
        "warsh":        "1-4 weeks (Fed policy is slower-moving)",
        "powell":       "1-2 weeks (Fed statement impact lingers)",
        "buffett":      "3-12 months (Buffett moves = long-term signal)",
        "jensen":       "1-4 weeks (Nvidia guidance = earnings cycle)",
        "dimon":        "2-8 weeks (Economic warnings take time to play out)",
        "altman":       "1-4 weeks (AI news moves quickly then stabilises)",
        "bessent":      "1-7 days (Tariff news = immediate but short-lived)",
        "zuckerberg":   "1-4 weeks (Ad revenue and AI moves at quarterly pace)",
        "cook":         "1-4 weeks (Supply chain and product news = weeks)",
        "nadella":      "1-4 weeks (Cloud growth = quarterly story)",
        "jassy":        "1-4 weeks (AWS and retail = quarterly pace)",
        "ellison":      "1-8 weeks (Deal announcements take time to validate)",
        "rfk":          "2-12 weeks (Regulatory changes are slow)",
        "xi":           "1-2 weeks (Geopolitical tension ebbs and flows)",
        "mbs":          "1-7 days (Oil production decisions immediate)",
        "cathie":       "1-4 weeks (ARK positioning = medium-term signal)",
        "burry":        "1-6 months (Burry shorts play out over quarters)",
    }
    hold = hold_periods.get(item["person_key"], "1-2 weeks")

    exit_signals = {
        "trump":    "When Trump's next post changes the subject or market cools",
        "musk":     "When Musk stops talking about it or TSLA reaches +20%",
        "warsh":    "After the next FOMC meeting clarifies Fed direction",
        "powell":   "After Warsh's first press conference as Chair",
        "buffett":  "When Buffett files next 13F showing position change",
        "jensen":   "After next Nvidia earnings call confirms or denies guidance",
        "dimon":    "When next bank earnings show actual credit data",
        "altman":   "When the AI news cycle moves to next product/regulation",
        "bessent":  "When tariff deal is signed or falls apart",
        "xi":       "When US-China tension indicator changes direction",
        "mbs":      "After next OPEC+ meeting decision",
        "rfk":      "When FDA ruling or policy change is officially announced",
        "cathie":   "When ARK files next position update (weekly)",
        "burry":    "When his 13F shows position closed or reduced",
    }
    exit_sig = exit_signals.get(item["person_key"], "When the news cycle moves on")

    return {
        **item,
        "person":    person,
        "affected":  affected,
        "sentiment": sentiment,
        "s_emoji":   s_emoji,
        "s_color":   s_color,
        "s_bg":      s_bg,
        "urgency":   urgency,
        "u_color":   u_color,
        "u_bg":      u_bg,
        "actions":   actions,
        "hold":      hold,
        "exit":      exit_sig,
        "pos":       pos,
        "neg":       neg,
    }


# ══════════════════════════════════════════════════════════════
# EMAIL HTML — BEAUTIFUL, CLEAR, EASY TO READ
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
*{box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:#F0F2F5;margin:0;padding:16px;color:#1a1a1a;}
.wrap{max-width:700px;margin:0 auto;}

/* ── HEADER ── */
.header{background:#1a237e;padding:28px 28px 22px;border-radius:16px 16px 0 0;
  border-bottom:4px solid #E53935;}
.header-top{display:flex;justify-content:space-between;align-items:flex-start;}
.header h1{margin:0;font-size:22px;font-weight:800;letter-spacing:-.3px;
  color:#FFFFFF !important;}
.header .sub{margin:6px 0 0;font-size:13px;color:#C5CAE9 !important;}
.live-badge{background:#E53935;color:#ffffff;font-size:11px;font-weight:700;
  padding:4px 12px;border-radius:20px;letter-spacing:.5px;}

/* ── SUMMARY BAR ── */
.summary-bar{background:#fff;border:1px solid #e0e0e0;border-top:none;
  padding:16px 20px;display:flex;justify-content:space-around;flex-wrap:wrap;gap:8px;}
.stat{text-align:center;min-width:80px;}
.stat .num{font-size:26px;font-weight:800;line-height:1;}
.stat .lbl{font-size:10px;color:#888;margin-top:3px;text-transform:uppercase;letter-spacing:.4px;}

/* ── SECTION HEADERS ── */
.section{padding:20px 20px 0;}
.section-title{font-size:11px;font-weight:800;color:#666;text-transform:uppercase;
  letter-spacing:1px;border-bottom:2px solid #eee;padding-bottom:8px;margin-bottom:14px;}

/* ── PERSON CARD ── */
.card{background:#fff;border:1px solid #e8e8e8;border-radius:14px;
  margin-bottom:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06);}

.card-header{padding:14px 18px;display:flex;align-items:center;gap:14px;}
.person-emoji{font-size:32px;line-height:1;}
.person-info{flex:1;}
.person-name{font-size:18px;font-weight:800;line-height:1.2;}
.person-role{font-size:12px;color:#777;margin-top:2px;}
.tier-badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;
  border-radius:10px;margin-top:4px;text-transform:uppercase;letter-spacing:.4px;}
.urgency-badge{font-size:13px;font-weight:700;padding:6px 14px;border-radius:20px;
  white-space:nowrap;text-align:center;}

/* ── QUOTE BOX ── */
.quote-box{margin:0 18px;padding:14px 16px;border-radius:10px;
  background:#FFFDE7;border-left:4px solid #F9A825;
  font-size:14px;line-height:1.65;color:#333;font-style:italic;}
.quote-meta{display:flex;gap:16px;padding:8px 18px;flex-wrap:wrap;}
.q-meta{font-size:11px;color:#aaa;}
.q-meta strong{color:#666;}

/* ── WHY IT MATTERS ── */
.why-box{margin:8px 18px;padding:12px 14px;background:#F8F9FF;border-radius:8px;
  font-size:13px;line-height:1.6;color:#444;border:1px solid #e8eaf6;}
.why-label{font-size:10px;font-weight:700;color:#5c6bc0;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:4px;}

/* ── STOCKS GRID ── */
.stocks-label{font-size:10px;font-weight:700;color:#555;text-transform:uppercase;
  letter-spacing:.5px;padding:10px 18px 6px;}
.stocks-grid{display:flex;flex-wrap:wrap;gap:8px;padding:0 18px 10px;}
.stock-chip{border-radius:10px;padding:10px 14px;border:1px solid #e0e0e0;
  min-width:120px;flex:1;max-width:160px;}
.chip-ticker{font-size:16px;font-weight:800;}
.chip-name{font-size:10px;color:#999;margin:2px 0;}
.chip-dir{font-size:11px;font-weight:700;margin-top:4px;}
.dir-up{color:#0A5D3E;}
.dir-down{color:#C62828;}
.dir-watch{color:#F57F17;}

/* ── ACTION BOX ── */
.action-box{margin:8px 18px 12px;padding:14px 16px;border-radius:10px;border-left:4px solid;}
.action-title{font-size:13px;font-weight:800;margin-bottom:10px;}
.action-item{font-size:13px;padding:5px 0;border-bottom:1px solid rgba(0,0,0,.06);
  line-height:1.6;color:#333;}
.action-item:last-child{border:none;}
.hold-row{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;}
.hold-chip{background:rgba(255,255,255,.7);border:1px solid rgba(0,0,0,.1);
  border-radius:8px;padding:8px 12px;flex:1;min-width:140px;}
.hold-chip .hl{font-size:10px;color:#888;margin-bottom:2px;}
.hold-chip .hv{font-size:12px;font-weight:600;color:#333;}

/* ── QUICK LIST ── */
.quick{background:#1a237e;
  border-radius:12px;padding:18px 20px;color:#fff;margin:16px 20px 0;}
.quick h2{margin:0 0 4px;font-size:15px;font-weight:800;color:#ffffff;}
.quick p{margin:0 0 14px;font-size:12px;color:#C5CAE9;}
.ql-row{display:flex;align-items:center;gap:12px;padding:9px 0;
  border-bottom:1px solid rgba(255,255,255,.2);}
.ql-row:last-child{border:none;padding-bottom:0;}
.ql-emoji{font-size:22px;flex-shrink:0;}
.ql-text{flex:1;}
.ql-person{font-size:13px;font-weight:700;color:#ffffff;}
.ql-snippet{font-size:11px;color:#C5CAE9;margin-top:1px;}
.ql-badge{font-size:11px;background:rgba(255,255,255,.25);
  padding:3px 10px;border-radius:10px;font-weight:700;white-space:nowrap;color:#ffffff;}

/* ── FOOTER ── */
.footer-bar{background:#fff;border:1px solid #e0e0e0;border-top:none;
  border-radius:0 0 16px 16px;padding:16px 20px;text-align:center;
  font-size:11px;color:#aaa;line-height:1.8;}
.divider{height:1px;background:#f0f0f0;margin:20px 20px 0;}
</style>
"""

TIER_STYLES = {
    1: ("🔴 Tier 1 · Moves entire market",    "#B71C1C", "#FFCDD2"),
    2: ("🟠 Tier 2 · Moves sectors",          "#E65100", "#FFE0B2"),
    3: ("🟡 Tier 3 · Moves specific stocks",   "#F57F17", "#FFF9C4"),
    4: ("🔵 Tier 4 · Macro & sentiment",       "#1565C0", "#BBDEFB"),
}

DIR_STYLES = {
    "up":    ("background:#E8F5E9;border-color:#A5D6A7;", "dir-up",    "📈 Likely UP"),
    "down":  ("background:#FFEBEE;border-color:#EF9A9A;", "dir-down",  "📉 Likely DOWN"),
    "watch": ("background:#FFF8E1;border-color:#FFE082;", "dir-watch", "👀 Watch"),
}


def build_card(a):
    person   = a["person"]
    tier_lbl, tier_col, tier_bg = TIER_STYLES.get(person["tier"], TIER_STYLES[4])

    # Urgency badge
    urgency_html = f'<div class="urgency-badge" style="background:{a["u_bg"]};color:{a["u_color"]};">{a["urgency"]}</div>'

    # Stock chips
    chips = ""
    for ticker, info in list(a["affected"].items())[:6]:
        style, css_class, label = DIR_STYLES.get(info["direction"], DIR_STYLES["watch"])
        reason_short = info["reason"][:50]
        chips += f"""<div class="stock-chip" style="{style}">
      <div class="chip-ticker" style="color:{'#0A5D3E' if info['direction']=='up' else '#C62828' if info['direction']=='down' else '#F57F17'};">${ticker}</div>
      <div class="chip-name">{reason_short}</div>
      <div class="chip-dir {css_class}">{label}</div>
    </div>"""

    # Actions
    actions_html = "".join(
        f'<div class="action-item">• {act}</div>' for act in a["actions"][:4]
    )

    # Quote meta
    time_str    = a["time"].strftime("%b %d · %H:%M UTC") if hasattr(a["time"], "strftime") else ""
    source_str  = a["source"]
    likes_html  = f'<div class="q-meta">❤️ <strong>{a.get("likes",0):,}</strong></div>' if a.get("likes") else ""
    reposts_html= f'<div class="q-meta">🔁 <strong>{a.get("reposts",0):,}</strong></div>' if a.get("reposts") else ""

    # Quote content
    quote = a["content"][:500] + ("..." if len(a["content"]) > 500 else "")

    return f"""<div class="card">
  <div class="card-header" style="background:{tier_bg};border-bottom:1px solid #eee;">
    <div class="person-emoji">{person['emoji']}</div>
    <div class="person-info">
      <div class="person-name" style="color:{tier_col};">{person['name']}</div>
      <div class="person-role">{person['role']}</div>
      <div class="tier-badge" style="background:{tier_col};color:#fff;">{tier_lbl}</div>
    </div>
    {urgency_html}
  </div>

  <div class="quote-box">"{quote}"</div>
  <div class="quote-meta">
    <div class="q-meta">📅 <strong>{time_str}</strong></div>
    <div class="q-meta">📡 <strong>{source_str}</strong></div>
    {likes_html}{reposts_html}
    <div class="q-meta"><a href="{a['url']}" style="color:#1565C0;">View original →</a></div>
  </div>

  <div class="why-box">
    <div class="why-label">Why {person['name'].split()[0]} moves markets</div>
    {person['why']}
  </div>

  <div class="stocks-label">📊 Stocks affected by this statement</div>
  <div class="stocks-grid">{chips}</div>

  <div class="action-box" style="background:{a['s_bg']};border-left-color:{a['s_color']};">
    <div class="action-title" style="color:{a['s_color']};">
      {a['s_emoji']} Overall Signal: {a['sentiment']} — What to do for your TFSA
    </div>
    {actions_html}
    <div class="hold-row">
      <div class="hold-chip">
        <div class="hl">⏱️ Suggested Hold</div>
        <div class="hv">{a['hold']}</div>
      </div>
      <div class="hold-chip">
        <div class="hl">🚪 Exit Signal</div>
        <div class="hv">{a['exit']}</div>
      </div>
    </div>
  </div>
</div>"""


def build_quicklist(top_items):
    if not top_items:
        return ""
    rows = ""
    for a in top_items[:6]:
        snippet = a["content"][:70].replace('"', "'")
        tickers = " ".join(f"${t}" for t in list(a["affected"].keys())[:3])
        rows += f"""<div class="ql-row">
    <div class="ql-emoji">{a['person']['emoji']}</div>
    <div class="ql-text">
      <div class="ql-person">{a['person']['name']}</div>
      <div class="ql-snippet">"{snippet}..." · {tickers}</div>
    </div>
    <div class="ql-badge">{a['urgency'].split()[0]}</div>
  </div>"""
    return f"""<div class="quick">
  <h2>⚡ Today's Market-Moving Statements</h2>
  <p>Click any card below for full analysis and what to buy.</p>
  {rows}
</div>"""


def build_consolidated_table(all_items):
    """
    Builds the consolidated action table shown at the BOTTOM of every email.
    One row per unique ticker. Shows:
      - Stock ticker + name
      - Action (BUY / SELL / WATCH)
      - Why (which person + reason, plain English)
      - Exchange (NYSE/TSX)
      - Urgency
    This is your quick-reference cheat sheet for the whole email.
    """
    if not all_items:
        return ""

    # Aggregate all affected stocks across all items
    ticker_data = {}  # ticker → {action, reasons, urgency, people}
    for a in all_items:
        person_name = a["person"]["name"].split()[0]  # first name only
        urgency     = a["urgency"]
        for ticker, info in a["affected"].items():
            if ticker not in ticker_data:
                ticker_data[ticker] = {
                    "direction": info["direction"],
                    "reasons":   [],
                    "urgency":   urgency,
                    "people":    [],
                    "sentiment": a["sentiment"],
                }
            ticker_data[ticker]["reasons"].append(info["reason"][:60])
            if person_name not in ticker_data[ticker]["people"]:
                ticker_data[ticker]["people"].append(person_name)
            # Escalate urgency if needed
            u_order = {"🚨 ACT WITHIN MINUTES": 0, "⚡ ACT TODAY": 1, "📊 ACT THIS WEEK": 2, "👀 MONITOR": 3}
            if u_order.get(urgency, 9) < u_order.get(ticker_data[ticker]["urgency"], 9):
                ticker_data[ticker]["urgency"] = urgency

    if not ticker_data:
        return ""

    # Sort: buys first, then by urgency
    dir_order = {"up": 0, "down": 1, "watch": 2}
    sorted_tickers = sorted(ticker_data.items(),
                            key=lambda x: (dir_order.get(x[1]["direction"], 9), x[0]))

    # Known exchange map (TSX tickers)
    tsx_tickers = {"SHOP","RY","TD","BNS","BMO","CM","ENB","SU","CNR","CP","TRP",
                   "PPL","ABX","NTR","WFG","XIU","FFH","BB","TRI","MFC","SLF",
                   "CNQ","IMO","REI.UN","ATD","BCE","T","TECK","FM","G","K"}

    rows = ""
    for ticker, data in sorted_tickers[:25]:  # cap at 25 rows
        direction = data["direction"]
        people    = ", ".join(data["people"][:3])
        reason    = data["reasons"][0] if data["reasons"] else "Market-moving statement detected"
        exchange  = "TSX" if ticker in tsx_tickers else "NYSE/NASDAQ"
        urgency_short = data["urgency"].split()[0]  # just the emoji

        if direction == "up":
            action_html = '<span style="background:#D4F5E9;color:#0A5D3E;font-weight:700;padding:3px 10px;border-radius:6px;font-size:12px;">✅ BUY</span>'
        elif direction == "down":
            action_html = '<span style="background:#FFEBEE;color:#C62828;font-weight:700;padding:3px 10px;border-radius:6px;font-size:12px;">🔴 SELL/AVOID</span>'
        else:
            action_html = '<span style="background:#FFF8E1;color:#F57F17;font-weight:700;padding:3px 10px;border-radius:6px;font-size:12px;">👀 WATCH</span>'

        exch_color = "#B71C1C" if exchange == "TSX" else "#1565C0"

        rows += f"""<tr style="border-bottom:1px solid #f0f0f0;">
      <td style="padding:10px 12px;font-weight:800;font-size:15px;color:#1a1a1a;">${ticker}</td>
      <td style="padding:10px 12px;">{action_html}</td>
      <td style="padding:10px 12px;font-size:12px;color:#555;">{people}</td>
      <td style="padding:10px 12px;font-size:12px;color:#444;max-width:220px;">{reason}</td>
      <td style="padding:10px 12px;text-align:center;">
        <span style="background:{'#FFEBEE' if exchange=='TSX' else '#E3F2FD'};color:{exch_color};
          font-size:10px;font-weight:700;padding:2px 7px;border-radius:5px;">{exchange}</span>
      </td>
      <td style="padding:10px 12px;text-align:center;font-size:15px;">{urgency_short}</td>
    </tr>"""

    buy_count   = sum(1 for _, d in sorted_tickers if d["direction"] == "up")
    sell_count  = sum(1 for _, d in sorted_tickers if d["direction"] == "down")
    watch_count = sum(1 for _, d in sorted_tickers if d["direction"] == "watch")

    return f"""
<div class="divider"></div>
<div class="section" style="padding-bottom:20px;">
  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:14px;overflow:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,.06);">

    <!-- Table Header -->
    <div style="background:#1a237e;padding:16px 20px;">
      <div style="font-size:16px;font-weight:800;color:#ffffff;">
        📋 Consolidated Action Table — Full Stock Summary
      </div>
      <div style="font-size:12px;color:#C5CAE9;margin-top:4px;">
        Every stock mentioned in this email · sorted by action · US &amp; Canadian markets
      </div>
      <div style="display:flex;gap:16px;margin-top:10px;flex-wrap:wrap;">
        <span style="background:#D4F5E9;color:#0A5D3E;font-size:12px;font-weight:700;
          padding:4px 12px;border-radius:20px;">✅ BUY: {buy_count} stocks</span>
        <span style="background:#FFEBEE;color:#C62828;font-size:12px;font-weight:700;
          padding:4px 12px;border-radius:20px;">🔴 SELL/AVOID: {sell_count} stocks</span>
        <span style="background:#FFF8E1;color:#F57F17;font-size:12px;font-weight:700;
          padding:4px 12px;border-radius:20px;">👀 WATCH: {watch_count} stocks</span>
      </div>
    </div>

    <!-- Key: holding period reminder -->
    <div style="background:#FFFDE7;padding:10px 20px;border-bottom:1px solid #f0f0f0;
      font-size:12px;color:#555;line-height:1.6;">
      <strong>📌 Reminder:</strong>
      🚨 Act Now = enter within 30-60 min, hold 1-3 days, stop loss -5% &nbsp;|&nbsp;
      ⚡ Act Today = enter today, hold 3-14 days &nbsp;|&nbsp;
      📊 This Week = hold weeks to months &nbsp;|&nbsp;
      👀 Monitor = wait for more signals &nbsp;|&nbsp;
      <strong>All TFSA gains are tax-free in Canada.</strong>
    </div>

    <!-- Table -->
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-family:-apple-system,sans-serif;">
        <thead>
          <tr style="background:#f8f9fa;border-bottom:2px solid #e0e0e0;">
            <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Ticker</th>
            <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Action</th>
            <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Who Said It</th>
            <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Why</th>
            <th style="padding:10px 12px;text-align:center;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Market</th>
            <th style="padding:10px 12px;text-align:center;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;">Speed</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div style="padding:12px 20px;background:#f8f9fa;font-size:11px;color:#999;line-height:1.6;">
      Not financial advice · Research before investing · TFSA losses are not tax-deductible ·
      Stop losses protect your capital · Never invest more than you can afford to lose
    </div>
  </div>
</div>"""


def build_html_email(by_urgency, total_scanned):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y · %H:%M UTC")

    act_now  = by_urgency.get("act_now",  [])
    act_today= by_urgency.get("act_today",[])
    act_week = by_urgency.get("act_week", [])
    monitor  = by_urgency.get("monitor",  [])

    all_items = act_now + act_today + act_week + monitor
    total_act  = len(act_now) + len(act_today) + len(act_week)

    bullish  = sum(1 for a in all_items if "BULLISH" in a["sentiment"])
    bearish  = sum(1 for a in all_items if "BEARISH" in a["sentiment"])

    # Count unique people
    people_seen = len(set(a["person_key"] for a in all_items))

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market Movers Alert</title>
{CSS}
</head>
<body><div class="wrap">

<!-- HEADER -->
<div class="header">
  <div class="header-top">
    <div>
      <h1>📡 Market Movers Monitor</h1>
      <div class="sub">Phase 6 · 20 Most Influential People · {date_str}</div>
    </div>
    <div class="live-badge">LIVE</div>
  </div>
</div>

<!-- SUMMARY BAR -->
<div class="summary-bar">
  <div class="stat"><div class="num" style="color:#B71C1C;">{len(act_now)}</div><div class="lbl">🚨 Act Now</div></div>
  <div class="stat"><div class="num" style="color:#E65100;">{len(act_today)}</div><div class="lbl">⚡ Act Today</div></div>
  <div class="stat"><div class="num" style="color:#1565C0;">{len(act_week)}</div><div class="lbl">📊 This Week</div></div>
  <div class="stat"><div class="num" style="color:#0A5D3E;">{bullish}</div><div class="lbl">📈 Bullish</div></div>
  <div class="stat"><div class="num" style="color:#C62828;">{bearish}</div><div class="lbl">📉 Bearish</div></div>
  <div class="stat"><div class="num" style="color:#555;">{people_seen}</div><div class="lbl">👤 People</div></div>
</div>

{build_quicklist(act_now + act_today)}

<div class="section">
  <div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:10px;
    padding:16px 18px;margin-top:14px;border-left:4px solid #1a237e;">
    <p style="font-size:13px;color:#333;margin:0 0 10px;line-height:1.7;">
      We track the <strong style="color:#1a237e;">20 most market-moving people</strong> affecting
      <strong>US &amp; Canadian markets</strong> — including Trump, Elon Musk, Fed Chair Kevin Warsh,
      Warren Buffett, CEOs, Treasury officials, OPEC leaders, and Canadian market figures
      (Mark Carney, Prem Watsa, Bank of Canada). Each card below explains exactly what was said,
      which <strong>TSX and NYSE stocks</strong> are affected, and what to do in your TFSA.
    </p>
    <p style="font-size:12px;color:#E65100;margin:0 0 6px;font-weight:700;">
      ⚡ For 🚨 ACT NOW alerts — check your broker within 30-60 minutes. These move fast.
    </p>
    <p style="font-size:11px;color:#888;margin:0;">
      ⚠️ Not financial advice. Always do your own research. Losses are possible. TFSA gains are tax-free but losses are not deductible.
    </p>
  </div>
</div>"""

    if act_now:
        html += '<div class="section"><div class="section-title">🚨 Act Within Minutes — Tier 1 Statements</div>'
        for a in act_now: html += build_card(a)
        html += '</div><div class="divider"></div>'

    if act_today:
        html += '<div class="section"><div class="section-title">⚡ Act Today — High Impact Statements</div>'
        for a in act_today: html += build_card(a)
        html += '</div><div class="divider"></div>'

    if act_week:
        html += '<div class="section"><div class="section-title">📊 Act This Week — Sector & Company Moves</div>'
        for a in act_week: html += build_card(a)
        html += '</div><div class="divider"></div>'

    if monitor:
        html += '<div class="section"><div class="section-title">👀 Monitor — Macro & Sentiment Signals</div>'
        for a in monitor[:3]: html += build_card(a)
        html += '</div>'

    # ── CONSOLIDATED ACTION TABLE ─────────────────────────────
    html += build_consolidated_table(all_items)

    html += f"""
<div class="divider"></div>
<div class="footer-bar">
  <strong>Phase 6 Market Movers Monitor</strong> · Runs every 5 min via GitHub Actions<br>
  People tracked: Trump · Musk · Warsh · Powell · Buffett · Jensen · Dimon · Altman · Bessent
  · Zuckerberg · Cook · Nadella · Jassy · Ellison · RFK · Xi · MBS · Cathie Wood · Burry
  · Carney · Macklem · Watsa + more (US &amp; Canada)<br>
  Sources: Truth Social (CNN) · trumpstruth.org · Google News · Yahoo Finance<br>
  Research and education only — not financial advice. Trading involves risk of loss.<br>
  <a href="https://truthsocial.com/@realDonaldTrump" style="color:#1565C0;">Trump's Truth Social</a> &nbsp;·&nbsp;
  <a href="https://finance.yahoo.com" style="color:#1565C0;">Yahoo Finance</a>
</div>
</div></body></html>"""

    return html


def build_text_email(by_urgency):
    now   = datetime.now(timezone.utc)
    lines = [
        "=" * 65,
        f" PHASE 6 MARKET MOVERS — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 65,
    ]
    for category, label in [("act_now","🚨 ACT NOW"),("act_today","⚡ ACT TODAY"),("act_week","📊 THIS WEEK")]:
        items = by_urgency.get(category, [])
        if not items:
            continue
        lines.append(f"\n{label}:")
        for a in items:
            lines.append(f"\n  {a['person']['emoji']} {a['person']['name']} ({a['person']['role']})")
            lines.append(f"  \"{a['content'][:120]}...\"")
            lines.append(f"  Signal: {a['sentiment']} | Source: {a['source']}")
            tickers = ", ".join(f"${t}({info['direction'].upper()})" for t,info in list(a["affected"].items())[:4])
            lines.append(f"  Stocks: {tickers}")
            lines.append(f"  Hold: {a['hold']} | Exit: {a['exit']}")
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
    print(f"📡 Phase 6 Market Movers Monitor — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Tracking {len(MARKET_MOVERS)} influential people")

    seen      = load_seen()
    all_items = []
    new_hashes= set()

    # ── Source 1: Trump Truth Social ─────────────────────────
    print("\n[1/4] Truth Social (CNN archive)...")
    for post in fetch_trump_truth_social():
        h = item_hash(post["content"], post["source"])
        if h not in seen and h not in new_hashes:
            all_items.append(post)
            new_hashes.add(h)

    # ── Source 2: Trump RSS backup ────────────────────────────
    print("[2/4] trumpstruth.org RSS backup...")
    for post in fetch_trumpstruth_rss():
        h = item_hash(post["content"], post["source"])
        if h not in seen and h not in new_hashes:
            all_items.append(post)
            new_hashes.add(h)

    # ── Source 3: Google News for each person ─────────────────
    print("[3/4] Google News for all 20 people...")
    for person_key, person_data in MARKET_MOVERS.items():
        if person_data.get("source") == "news":
            articles = fetch_google_news_for_person(person_key, person_data)
            for a in articles:
                h = item_hash(a["content"], a["source"])
                if h not in seen and h not in new_hashes:
                    all_items.append(a)
                    new_hashes.add(h)
            time.sleep(0.5)

    # ── Source 4: Yahoo Finance ───────────────────────────────
    print("[4/4] Yahoo Finance top stories...")
    for a in fetch_yahoo_finance_rss():
        h = item_hash(a["content"], a["source"])
        if h not in seen and h not in new_hashes:
            all_items.append(a)
            new_hashes.add(h)

    print(f"\n  New items: {len(all_items)}")

    if not all_items:
        print("  Nothing new. No email sent.")
        return

    # ── Analyse each item ─────────────────────────────────────
    by_urgency = {"act_now": [], "act_today": [], "act_week": [], "monitor": []}

    for item in all_items:
        result = analyse(item)
        if result is None:
            continue
        if "MINUTES" in result["urgency"]:   by_urgency["act_now"].append(result)
        elif "TODAY"  in result["urgency"]:   by_urgency["act_today"].append(result)
        elif "WEEK"   in result["urgency"]:   by_urgency["act_week"].append(result)
        else:                                 by_urgency["monitor"].append(result)

    total_act = sum(len(v) for v in by_urgency.values())
    print(f"  Actionable: {total_act} | Act Now: {len(by_urgency['act_now'])} | Today: {len(by_urgency['act_today'])} | Week: {len(by_urgency['act_week'])}")

    # ── Only email if something actionable ────────────────────
    act_count = len(by_urgency["act_now"]) + len(by_urgency["act_today"])
    if act_count == 0 and not by_urgency["act_week"]:
        print("  No actionable signals. No email sent.")
        save_seen(seen | new_hashes)
        return

    # ── Build email ────────────────────────────────────────────
    html_body = build_html_email(by_urgency, len(all_items))
    text_body = build_text_email(by_urgency)

    # ── Subject line ──────────────────────────────────────────
    top_people = []
    for a in (by_urgency["act_now"] + by_urgency["act_today"])[:3]:
        top_people.append(a["person"]["name"].split()[0])

    urgency_tag = "🚨 ACT NOW" if by_urgency["act_now"] else "⚡ ACT TODAY" if by_urgency["act_today"] else "📊 THIS WEEK"
    subject = (f"📡 {urgency_tag}: {' · '.join(top_people) or 'Market Movers'} "
               f"— {act_count} alerts · {now.strftime('%H:%M UTC')}")

    print(text_body)
    save_seen(seen | new_hashes)

    if EMAIL_SENDER != "your@gmail.com" and EMAIL_PASSWORD:
        send_email(subject, html_body, text_body)
    else:
        print("\n⚠️  Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in GitHub Secrets.")


if __name__ == "__main__":
    run()
