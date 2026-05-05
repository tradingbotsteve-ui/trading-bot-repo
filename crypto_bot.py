#  TRADING BOT — PHASE 4: CRYPTO ALTCOIN BRIEF  (v2)
#  File: crypto_bot.py
#
#  KEY UPGRADE: Auto-discovers EVERY coin on Kraken live.
#  Uses Kraken public AssetPairs API — no hardcoded list.
#  YOUR HOLDINGS (PENGU, LUNA) always appear first.
#
#  Hard rules:
#    Price strictly under $2.00 USD at runtime
#    Min $50K daily volume (liquid enough to trade)
#    No stablecoins auto-filtered
#    Coins above $2 auto-skipped and listed at bottom
#
#  Coins from $0.0000001 to $1.9999 all handled.
#  9:00 AM Pacific email: "Crypto Altcoin Brief"
#
#  GitHub Secrets: ALPHA_VANTAGE_KEY, EMAIL_SENDER,
#                  EMAIL_PASSWORD, EMAIL_RECIPIENT
# ============================================================

import os, sys, smtplib, requests, time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from statistics import mean

_raw_pw         = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_PASSWORD  = "".join(c for c in _raw_pw if ord(c) < 128 and c not in (" ", "\\xa0"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER",    "your@gmail.com")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "your@gmail.com")
AV_KEY          = os.environ.get("ALPHA_VANTAGE_KEY", "demo")

MAX_PRICE_USD  = 2.00
MIN_VOL_USD    = 50_000
TOP_N_EMAIL    = 25

# Your personal holdings — always shown first regardless of price filter
MY_HOLDINGS = ["PENGUUSD", "LUNAUSD"]

STABLECOINS = {
    "USDT","USDC","DAI","BUSD","TUSD","USDP","GUSD","FRAX","LUSD",
    "SUSD","ALUSD","MUSD","HUSD","OUSD","USDX","EURS","XSGD",
    "USDD","USDQ","USDR","USD1","AUSD","EURC","PYUSD","RLUSD",
    "FIDD","EUROP","PAX","PAXG","XAUT","TBTC",
}

# Coin knowledge base — (category, display_name, description)
COIN_INFO = {
    "PENGU":("Meme/NFT","Pudgy Penguins",
             "NFT collection turned coin — Pudgy Penguins toys sold in 5,000+ US retail stores generating ~$40M annual revenue. "
             "Active Kraken volume (~$163M/day). Moves hard on NFT hype cycles, whale activity and community events."),
    "LUNA": ("Speculative","Terra Classic (LUNC)",
             "Original Terra blockchain token that collapsed in May 2022 when UST depegged. "
             "Now Terra Classic with a community burn mechanism (0.5% burn tax per transaction). "
             "Extremely speculative — 5.5 trillion token supply. Trades purely on burn rate news and speculation."),
    "ADA":  ("Layer 1","Cardano",
             "Peer-reviewed proof-of-stake L1. Strong developer community, growing DeFi and NFT ecosystem "
             "especially in Africa and developing markets. Slow and methodical but resilient."),
    "XRP":  ("Payments","Ripple XRP",
             "Cross-border payment network used by major banks. Post-SEC legal clarity opened institutional adoption. "
             "Very high daily volume — one of Kraken\'s most traded pairs."),
    "DOGE": ("Meme/L1","Dogecoin",
             "Original meme coin with real payment adoption. Supported by Tesla and SpaceX. "
             "One of the highest-volume coins on any exchange — very liquid for scalping."),
    "XLM":  ("Payments","Stellar Lumens",
             "Fast cross-border payment network for the unbanked. IBM WorldWire uses Stellar rails. "
             "Competing with XRP for institutional cross-border settlement."),
    "HBAR": ("Layer 1","Hedera Hashgraph",
             "Enterprise blockchain governed by Google, IBM and Boeing. 10,000+ TPS at near-zero fees. "
             "Growing use in tokenization and corporate data applications."),
    "ALGO": ("Layer 1","Algorand",
             "Pure proof-of-stake L1 with instant finality. FIFA, Marshall Islands CBDC, and major payment partnerships."),
    "TRX":  ("Layer 1","Tron",
             "High-throughput blockchain. More USDT transacts on Tron than Ethereum. "
             "Justin Sun ecosystem — high volume despite controversy."),
    "VET":  ("Enterprise","VeChain",
             "Supply chain blockchain used by LVMH, Walmart China, BMW. Two-token model (VET + VTHO gas)."),
    "ZIL":  ("Layer 1","Zilliqa",
             "Sharding pioneer — first blockchain to implement sharding in production. Gaming and DeFi ecosystem."),
    "KAS":  ("Layer 1","Kaspa",
             "Fastest proof-of-work blockchain — blockDAG allows 1 block per second. "
             "Growing miner interest. Called \'the fastest PoW coin\'."),
    "XDC":  ("Enterprise","XDC Network",
             "Enterprise blockchain for trade finance. ISO 20022 compliant. Used by TradeFinex platform."),
    "ASTR": ("Layer 1","Astar Network",
             "Polkadot\'s leading smart contract hub. Multi-VM (EVM + WASM). Japan-focused, major corporate backing."),
    "GLMR": ("Layer 1","Moonbeam",
             "Ethereum-compatible Polkadot parachain. Ethereum dApps deploy here without code changes."),
    "GRT":  ("DeFi","The Graph",
             "Blockchain indexing — Google for Web3 data. Used by Uniswap, Aave, Compound. Revenue scales with DeFi."),
    "CRV":  ("DeFi","Curve Finance",
             "Largest stablecoin DEX. Processes billions in swaps daily. veCRV holders earn real protocol fee yield."),
    "SNX":  ("DeFi","Synthetix",
             "Synthetic asset protocol — trade synthetic stocks, commodities, forex on-chain. High staking yield."),
    "PERP": ("DeFi","Perpetual Protocol",
             "Decentralized perpetual futures on Optimism. Growing as DeFi derivatives gain vs centralized exchanges."),
    "DYDX": ("DeFi","dYdX",
             "Leading decentralized derivatives exchange on its own Cosmos chain. Real fee revenue to stakers."),
    "BADGER":("DeFi","Badger DAO",
             "Bitcoin DeFi — BTC holders earn yield in DeFi. BTC wrappers and vaults for the Ethereum ecosystem."),
    "CVX":  ("DeFi","Convex Finance",
             "Curve booster — holds massive CRV to amplify Curve yields. Moves closely with CRV."),
    "SUSHI":("DeFi","SushiSwap",
             "Multi-chain DEX and DeFi hub. SUSHI rewards liquidity providers. Cross-chain expansion."),
    "KNC":  ("DeFi","Kyber Network Crystal",
             "On-chain liquidity aggregator powering many DeFi aggregator back-ends."),
    "ANKR": ("DeFi","Ankr",
             "Decentralized RPC node provider. Used by Web3 developers. Revenue scales with Web3 adoption."),
    "LRC":  ("DeFi","Loopring",
             "zkRollup DEX on Ethereum. Processes trades fast at fraction of gas cost. Backed by Google engineers."),
    "REN":  ("DeFi","Ren Protocol",
             "Cross-chain liquidity — wraps BTC, ZEC for Ethereum DeFi. Speculative post-Alameda headwinds."),
    "OCEAN":("DeFi","Ocean Protocol",
             "Data marketplace — monetize and share data on-chain. AI + data sovereignty narrative. ASI Alliance."),
    "FET":  ("AI","Fetch.ai",
             "AI agent network. Part of ASI Alliance merger with OCEAN and AGIX. Real autonomous agent use cases."),
    "AGIX": ("AI","SingularityNET",
             "AI marketplace by Ben Goertzel. Part of ASI Alliance. Moves hard on AI narrative cycles."),
    "CTSI": ("DeFi","Cartesi",
             "Blockchain OS — smart contracts in Python, C++ instead of Solidity. Lowers developer barrier."),
    "OGN":  ("Web3","Origin Protocol",
             "Decentralized commerce and DeFi yields. OUSD stablecoin earns yield natively."),
    "STORJ":("Web3","Storj",
             "Decentralized cloud storage — pay with STORJ tokens. Competing with Filecoin."),
    "BAT":  ("Web3","Basic Attention Token",
             "Brave browser privacy-first ad system. 60M+ monthly Brave users earn BAT for watching ads."),
    "MASK": ("Web3","Mask Network",
             "Browser extension adding Web3 features to Twitter/X and Facebook. NFTs, DeFi on social media."),
    "REQ":  ("Web3","Request Network",
             "Decentralized crypto invoicing and payment requests. Steady developer adoption."),
    "OXT":  ("Privacy","Orchid",
             "Decentralized VPN marketplace. Pay-as-you-go bandwidth with OXT. Small but loyal user base."),
    "SCRT": ("Privacy","Secret Network",
             "Privacy-preserving smart contracts via trusted execution environments. Computations are private."),
    "ROSE": ("Privacy","Oasis Network",
             "Privacy DeFi and AI data platform. Confidential smart contracts via Sapphire paratime."),
    "NYM":  ("Privacy","Nym",
             "Privacy mixnet — anonymises internet traffic stronger than a VPN. Growing privacy communities."),
    "MANA": ("Metaverse","Decentraland",
             "Virtual world where land is NFTs. Samsung, JP Morgan, Atari own virtual plots. Spikes on metaverse hype."),
    "SAND": ("Metaverse","The Sandbox",
             "Gaming metaverse — Snoop Dogg, Paris Hilton, Adidas own virtual land. Strong brand partnerships."),
    "ENJ":  ("Gaming","Enjin Coin",
             "NFT gaming ecosystem. Every in-game item backed 1:1 by ENJ. Microsoft Azure partnership."),
    "GALA": ("Gaming","Gala Games",
             "Web3 gaming ecosystem with 20+ games. GALA used for in-game purchases and governance."),
    "IMX":  ("Gaming","Immutable X",
             "L2 for NFT gaming — zero gas fees for minting and trading. Used by Gods Unchained and major studios."),
    "CHZ":  ("Sports","Chiliz",
             "Fan token platform — Barcelona, PSG, UFC, NBA. Real-world redemption via Socios.com."),
    "ALICE":("Gaming","My Neighbor Alice",
             "Multiplayer builder game with virtual island NFTs. Casual gaming audience."),
    "GODS": ("Gaming","Gods Unchained",
             "On-chain trading card game on Immutable X. Cards are NFTs players truly own."),
    "HIGH": ("Gaming","Highstreet",
             "Phygital commerce metaverse — buy real-world products in-game. Physical + digital NFT model."),
    "SHIB": ("Meme","Shiba Inu",
             "Second largest meme coin. Ethereum-based with DeFi (ShibaSwap) and L2 (Shibarium). "
             "Burn events and whale moves drive sharp pumps."),
    "PEPE": ("Meme","Pepe",
             "ERC-20 meme coin — pure sentiment, no utility. Massive Kraken volume. "
             "Very sensitive to BTC moves, Elon tweets, and meme cycles."),
    "FLOKI":("Meme","Floki Inu",
             "Meme coin with ecosystem — Valhalla gaming, FlokiFi DeFi, FlokiPlaces NFT marketplace."),
    "BONK": ("Meme","Bonk",
             "Solana\'s first community meme coin — airdropped to Solana developers. Follows Solana sentiment."),
    "WIF":  ("Meme","dogwifhat",
             "Solana meme coin — just a dog with a hat. Top 50 by market cap. Pure hype and momentum."),
    "SPELL":("DeFi","Spell Token",
             "Governance token for Abracadabra.money. Earns fees when users borrow against collateral."),
    "DENT": ("Telecom","DENT Wireless",
             "Decentralized mobile data marketplace. Buy and sell mobile data with DENT."),
    "HOT":  ("Web3","Holo",
             "Distributed cloud hosting for Holochain apps. HOT redeemable for hosting credits."),
    "WIN":  ("Gaming","WINkLink",
             "Tron-based gaming and oracle network. Very cheap — allows large unit accumulation."),
    "JASMY":("Data","JasmyCoin",
             "IoT data sovereignty platform — Sony veterans team. Users own and monetize their device data."),
    "POWR": ("Energy","Power Ledger",
             "Peer-to-peer renewable energy trading. Buy/sell solar power with POWR. ESG narrative coin."),
    "CELR": ("Layer 2","Celer Network",
             "L2 scaling and cross-chain messaging. Powers cBridge for fast cross-chain transfers."),
    "POND": ("Web3","Marlin",
             "High-performance network layer for DeFi and Web3 apps. Reduces transaction latency."),
    "TRAC": ("Web3","OriginTrail",
             "Decentralized knowledge graph for supply chains and AI. Used by BSI and EU blockchain initiative."),
    "SUPER":("Gaming","SuperFarm",
             "Cross-chain NFT farming and gaming platform. Farm NFTs by staking tokens."),
    "RARE": ("NFT","SuperRare",
             "Governance token for curated digital art marketplace. RARE holders vote on curation and fees."),
    "RARI": ("NFT","Rarible",
             "Multi-chain NFT marketplace. Open to all creators — less curated than SuperRare."),
    "AUDIO":("Web3","Audius",
             "Decentralized music streaming. Artists keep 90% of revenue. TikTok integration history."),
    "FLOW": ("Gaming","Flow",
             "Blockchain for NFTs and games — NBA Top Shot, UFC Strike run on Flow."),
    "STX":  ("Bitcoin L2","Stacks",
             "Smart contracts for Bitcoin. Settles on Bitcoin — DeFi and NFTs on BTC. sBTC unlocks BTC liquidity."),
    "XTZ":  ("Layer 1","Tezos",
             "Self-amending PoS blockchain with on-chain governance. Used by Ubisoft, McLaren for NFTs."),
    "KAVA": ("DeFi","Kava",
             "Cosmos DeFi chain with EVM. Kava Lend allows borrowing against BTC, BNB, XRP collateral."),
    "BAND": ("DeFi","Band Protocol",
             "Decentralized oracle on Cosmos. Feeds real-world data to blockchains across Cosmos ecosystem."),
    "API3": ("DeFi","API3",
             "First-party oracles — APIs connect directly to blockchains. Quantifiable security guarantees."),
    "ONT":  ("Identity","Ontology",
             "Decentralized identity and data sovereignty. Government digital ID pilots in Asia."),
    "CFG":  ("DeFi","Centrifuge",
             "Real-world asset tokenization — invoices, mortgages, royalties as on-chain collateral."),
    "ARB":  ("Layer 2","Arbitrum",
             "Largest Ethereum L2 by TVL. Low fees, EVM compatible, biggest DeFi ecosystem outside mainnet."),
    "OP":   ("Layer 2","Optimism",
             "Ethereum L2 using optimistic rollups. Powers Superchain — Base, Worldchain built on OP Stack."),
    "MAGIC":("Gaming","Treasure DAO",
             "Decentralized gaming on Arbitrum. MAGIC is reserve currency for the Treasure metaverse."),
    "BLUR": ("NFT","Blur",
             "Pro NFT trading platform that overtook OpenSea in volume. Governance and airdrop rewards."),
    "ACA":  ("DeFi","Acala",
             "DeFi hub of Polkadot. Native stablecoin aUSD. Moves with DOT ecosystem news."),
    "FLUX": ("Web3","Flux",
             "Decentralized cloud computing — FluxOS on 14,000+ nodes. Direct AWS/GCP competitor, decentralized."),
    "POLS": ("DeFi","Polkastarter",
             "Cross-chain launchpad for IDOs. Projects raise funding through Polkastarter pools."),
    "RLY":  ("Gaming","Rally",
             "Creator coin platform — streamers, musicians, athletes monetize fan bases with custom tokens."),
    "KEEP": ("Privacy","Keep Network",
             "Privacy layer for public blockchains. Powers tBTC — decentralized Bitcoin bridge with no custodian."),
    "IOTX": ("IoT","IoTeX",
             "Blockchain for IoT devices. MachineFi — machines earn tokens for providing data."),
    "CFG":  ("DeFi","Centrifuge",
             "Real-world asset (RWA) tokenization. Invoices, mortgages, royalties on-chain for DeFi lending."),
    "MINA": ("Layer 1","Mina Protocol",
             "World\'s lightest blockchain — always 22KB. zk-SNARKs allow full verification without downloading chain."),
    "INJ":  ("DeFi","Injective",
             "Layer 1 built for DeFi — DEX, derivatives, prediction markets. Zero gas fees for traders."),
    "MOVR": ("Layer 1","Moonriver",
             "Kusama parachain — Moonbeam\'s canary network. Higher risk, higher reward. EVM compatible."),
    "PARA": ("DeFi","Parallel Finance",
             "Polkadot DeFi hub — lending, staking, AMM in one. DOT and KSM collateral for borrowing."),
    "KIN":  ("Web3","Kin",
             "Digital currency for consumer apps. Mobile app rewards currency ecosystem."),
}

def _install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:    from textblob import TextBlob
except: _install("textblob"); from textblob import TextBlob

KRAKEN = "https://api.kraken.com/0/public"

def kraken_get(endpoint, params=None):
    for attempt in range(3):
        try:
            r    = requests.get(f"{KRAKEN}/{endpoint}", params=params, timeout=15)
            data = r.json()
            if data.get("error"): return None
            return data.get("result")
        except Exception as e:
            if attempt == 2: print(f"    Kraken {endpoint} error: {e}")
            time.sleep(2)
    return None

def discover_usd_pairs():
    """Calls Kraken AssetPairs — returns every coin vs USD automatically."""
    result = kraken_get("AssetPairs")
    if not result: return []
    pairs = []
    for pair_name, info in result.items():
        if info.get("quote") not in ("ZUSD","USD"): continue
        if ".d" in pair_name or pair_name.endswith("_d"): continue
        symbol = info.get("altname","").replace("USD","").replace("XBT","BTC")
        if not symbol or symbol in STABLECOINS: continue
        if symbol in {"BTC","ETH","LTC","BCH","BSV","ETC","XMR","ZEC","DASH",
                      "MLN","NMR","REP","REPV2","WBTC","WETH","BETH"}: continue
        pairs.append((pair_name, symbol))
    return pairs

def get_ticker(pair):
    result = kraken_get("Ticker", {"pair": pair})
    if not result: return None
    try:
        key   = list(result.keys())[0]
        t     = result[key]
        price = float(t["c"][0])
        ask   = float(t["a"][0]); bid = float(t["b"][0])
        vol   = float(t["v"][1]); vwap = float(t["p"][1])
        high  = float(t["h"][1]); low  = float(t["l"][1])
        open_ = float(t["o"]); trades = int(t["t"][1])
        vol_usd = vol * vwap
        change  = round((price-open_)/open_*100,2) if open_>0 else 0
        spread  = round((ask-bid)/ask*100,3) if ask>0 else 0
        rng     = round((high-low)/low*100,2) if low>0 else 0
        return {"price":price,"ask":ask,"bid":bid,"vol_usd":vol_usd,
                "vol_coin":vol,"vwap":vwap,"high_24h":high,"low_24h":low,
                "open":open_,"change_24h":change,"spread_pct":spread,
                "trades_24h":trades,"range_pct":rng}
    except: return None

def get_ohlc(pair):
    result = kraken_get("OHLC", {"pair": pair, "interval": 60})
    if not result: return [],[]
    try:
        key = [k for k in result if k!="last"][0]
        c = result[key]
        return [float(x[4]) for x in c[-48:]], [float(x[6]) for x in c[-48:]]
    except: return [],[]

def calc_rsi(closes, p=14):
    if len(closes)<p+1: return None
    g=[]; l=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=mean(g[-p:]); al=mean(l[-p:])
    if al==0: return 100.0
    return round(100-100/(1+ag/al),1)

def calc_momentum(closes):
    if len(closes)<13: return None,None
    def pct(a,b): return round((b-a)/a*100,2) if a>0 else 0
    return (pct(closes[-2],closes[-1]) if len(closes)>=2 else None,
            pct(closes[-5],closes[-1]) if len(closes)>=5 else None)

def calc_vol_spike(vols):
    if len(vols)<10: return None
    avg=mean(vols[:-1])
    return round(vols[-1]/avg,2) if avg>0 else None

def calc_ema(closes,p):
    if len(closes)<p: return None
    k=2/(p+1); e=closes[0]
    for x in closes[1:]: e=x*k+e*(1-k)
    return e

def trend_dir(closes):
    e9=calc_ema(closes,9); e21=calc_ema(closes,21)
    if not e9 or not e21: return "SIDEWAYS"
    d=(e9-e21)/e21*100
    return "UP" if d>0.5 else "DOWN" if d<-0.5 else "SIDEWAYS"

def get_news(symbol):
    headlines=[]
    try:
        url=(f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
             f"&tickers=CRYPTO:{symbol}&limit=8&apikey={AV_KEY}")
        data=requests.get(url,timeout=10).json()
        for item in data.get("feed",[])[:8]:
            title=item.get("title",""); pub=item.get("time_published","")[:8]
            try: pub_fmt=datetime.strptime(pub,"%Y%m%d").strftime("%b %d")
            except: pub_fmt=pub
            score=None
            for ts in item.get("ticker_sentiment",[]):
                if symbol.upper() in ts.get("ticker","").upper():
                    score=float(ts.get("ticker_sentiment_score",0)); break
            if score is None: score=TextBlob(title).sentiment.polarity
            headlines.append({"title":title[:110],"score":round(score,3),
                               "url":item.get("url","#"),"date":pub_fmt,
                               "source":item.get("source","")})
    except: pass
    if not headlines:
        try:
            url=f"https://cryptopanic.com/api/v1/posts/?currencies={symbol}&kind=news&public=true"
            data=requests.get(url,timeout=10).json()
            for item in data.get("results",[])[:8]:
                title=item.get("title",""); pub=item.get("published_at","")[:10]
                try: pub_fmt=datetime.strptime(pub,"%Y-%m-%d").strftime("%b %d")
                except: pub_fmt=pub
                headlines.append({"title":title[:110],"score":round(TextBlob(title).sentiment.polarity,3),
                                   "url":item.get("url","#"),"date":pub_fmt,
                                   "source":item.get("source",{}).get("title","")})
        except: pass
    return headlines

def avg_sent(h):
    return round(sum(x["score"] for x in h)/len(h),3) if h else 0.0

def fmt_price(v):
    if v is None: return "N/A"
    if v<0.000001: return f"${v:.10f}"
    if v<0.0001:   return f"${v:.8f}"
    if v<0.01:     return f"${v:.6f}"
    if v<0.10:     return f"${v:.5f}"
    if v<1.0:      return f"${v:.4f}"
    return f"${v:.3f}"

def fmt_vol(v):
    if v is None: return "N/A"
    if v>=1e9: return f"${v/1e9:.1f}B"
    if v>=1e6: return f"${v/1e6:.1f}M"
    if v>=1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

def cc(v): return "#0F6E56" if (v or 0)>0 else "#A32D2D" if (v or 0)<0 else "#888"

def build_reasons(ticker, rsi, h1, h4, vol_spike, trend, avg_sentiment_score):
    reasons=[]; price=ticker["price"]; ch=ticker["change_24h"]
    low=ticker["low_24h"]; high=ticker["high_24h"]
    pfl=((price-low)/(high-low)*100) if high>low else 50
    if h1 and h1>1.5: reasons.append({"tag":"📈 1h Momentum","color":"#0F6E56","text":f"Up {h1:+.2f}% in the last hour — active buying pressure building right now."})
    elif h1 and h1<-1.5: reasons.append({"tag":"📉 1h Selling","color":"#A32D2D","text":f"Down {abs(h1):.2f}% this hour — selling pressure. Watch for support at {fmt_price(low)}."})
    if h4 and h4>5: reasons.append({"tag":"📈 4h Trend","color":"#0F6E56","text":f"Up {h4:+.1f}% over 4 hours — sustained buying, not just one candle."})
    elif h4 and h4<-5: reasons.append({"tag":"📉 4h Decline","color":"#A32D2D","text":f"Down {abs(h4):.1f}% over 4 hours — sustained selling pressure."})
    if ch>8: reasons.append({"tag":"🚀 Strong Rally","color":"#0F6E56","text":f"Up {ch:+.1f}% in 24 hours — significant move. 24h range: {ticker['range_pct']:.1f}%."})
    elif ch>3: reasons.append({"tag":"📈 Gaining","color":"#3B6D11","text":f"Up {ch:+.1f}% today — solid positive momentum."})
    elif ch<-8: reasons.append({"tag":"🔴 Sharp Drop","color":"#A32D2D","text":f"Down {abs(ch):.1f}% in 24 hours — heavy sell-off. Could be entry opportunity or warning — wait for stability."})
    elif ch<-3: reasons.append({"tag":"📉 Declining","color":"#7A4900","text":f"Down {abs(ch):.1f}% today. Watch for support at {fmt_price(low)}."})
    elif abs(ch)<1: reasons.append({"tag":"😴 Flat","color":"#888","text":"Less than 1% movement today — consolidating. Low volatility often precedes a big move."})
    if rsi:
        if rsi<25: reasons.append({"tag":"💎 Deeply Oversold RSI","color":"#0F6E56","text":f"RSI at {rsi} — deeply oversold. Statistically more likely to bounce. Classic buy-the-dip signal."})
        elif rsi<35: reasons.append({"tag":"📊 Oversold RSI","color":"#3B6D11","text":f"RSI at {rsi} — approaching oversold. Selling pressure is fading."})
        elif 45<=rsi<=58: reasons.append({"tag":"📊 Healthy RSI","color":"#555","text":f"RSI at {rsi} — healthy momentum. Room to run without being overbought."})
        elif rsi>78: reasons.append({"tag":"⚠️ Overbought RSI","color":"#A32D2D","text":f"RSI at {rsi} — overbought. Rally may be overextended. Risk of buying near the top."})
        elif rsi>65: reasons.append({"tag":"⚠️ RSI Elevated","color":"#7A4900","text":f"RSI at {rsi} — getting hot. Watch for short-term exhaustion."})
    if vol_spike and vol_spike>3.0: reasons.append({"tag":"🔊 Massive Volume Spike","color":"#0F6E56","text":f"Volume is {vol_spike:.1f}× above average — major attention event. News, whale accumulation, or social virality. High vol + rising price = strong confirmation."})
    elif vol_spike and vol_spike>1.8: reasons.append({"tag":"🔊 Volume Spike","color":"#3B6D11","text":f"Volume is {vol_spike:.1f}× above average — more buyers/sellers than usual entering now."})
    elif vol_spike and vol_spike<0.4: reasons.append({"tag":"😴 Low Volume","color":"#888","text":f"Only {vol_spike:.1f}× of average volume — thin market. Moves less reliable."})
    if trend=="UP": reasons.append({"tag":"📈 Uptrend EMA","color":"#0F6E56","text":"Short-term EMA above long-term EMA — hourly chart is in an uptrend."})
    elif trend=="DOWN": reasons.append({"tag":"📉 Downtrend EMA","color":"#A32D2D","text":"Short-term EMA below long-term EMA — hourly downtrend in place."})
    if pfl<12 and ch>0: reasons.append({"tag":"🎯 Dip & Recovery","color":"#0F6E56","text":f"{pfl:.0f}% from today\'s low but positive daily change — dipped and recovered. Show of strength."})
    elif pfl>90: reasons.append({"tag":"⚠️ Near 24h High","color":"#7A4900","text":f"Price near today\'s high {fmt_price(high)}. Chasing highs is risky — wait for a pullback."})
    s=avg_sentiment_score
    if s>0.20: reasons.append({"tag":"📰 Strong Positive News","color":"#0F6E56","text":f"Headlines overwhelmingly positive (sentiment {s:+.2f}). Positive news attracts buyers."})
    elif s>0.10: reasons.append({"tag":"📰 Positive News","color":"#3B6D11","text":f"More positive than negative headlines (sentiment {s:+.2f})."})
    elif s<-0.20: reasons.append({"tag":"📰 Negative News","color":"#A32D2D","text":f"Headlines predominantly negative (sentiment {s:+.2f}). Bad news drives selling."})
    elif s<-0.10: reasons.append({"tag":"📰 Slightly Negative","color":"#7A4900","text":f"More negative than positive headlines (sentiment {s:+.2f})."})
    return reasons

def get_verdict(ticker, rsi, trend, vol_spike, avg_s, h1, h4):
    sc=0; ch=ticker["change_24h"]; spread=ticker["spread_pct"]
    if ch>6: sc+=20
    elif ch>2: sc+=10
    elif ch<-6: sc-=20
    elif ch<-2: sc-=10
    if rsi:
        if rsi<28: sc+=22
        elif rsi<42: sc+=11
        elif rsi>78: sc-=22
        elif rsi>65: sc-=8
    if trend=="UP": sc+=15
    elif trend=="DOWN": sc-=15
    if vol_spike:
        if vol_spike>3.0: sc+=20
        elif vol_spike>1.8: sc+=10
        elif vol_spike<0.4: sc-=10
    if avg_s>0.20: sc+=15
    elif avg_s>0.10: sc+=7
    elif avg_s<-0.20: sc-=15
    elif avg_s<-0.10: sc-=7
    if h1 and h1>1: sc+=5
    elif h1 and h1<-1: sc-=5
    if h4 and h4>4: sc+=10
    elif h4 and h4<-4: sc-=10
    if spread>1.5: sc-=12
    elif spread>0.8: sc-=5
    sc=max(-100,min(100,sc))
    if sc>=35: return ("🚀 BUY WATCH","#0F6E56","#D5F5EA","Multiple bullish signals aligned. Worth serious attention. Consider a small position — always set a stop-loss.",sc)
    elif sc>=15: return ("👀 WORTH WATCHING","#3B6D11","#E5F2DA","More positive than negative signals. Wait for a dip or clearer signal before entering.",sc)
    elif sc<=-35: return ("⛔ AVOID NOW","#A32D2D","#FDECEA","Multiple bearish signals. Avoid buying here — wait for selling to stop and momentum to reverse.",sc)
    elif sc<=-15: return ("⚠️ CAUTION","#7A4900","#FEF3DA","More negative than positive signals. Watch from the sidelines.",sc)
    return ("⚪ NEUTRAL","#555","#F0F0F0","Mixed signals — no clear edge. Save your capital for a clearer setup.",sc)

CSS = """<style>
body{font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;background:#f2f2f2;margin:0;padding:14px;color:#1a1a1a;}
.wrap{max-width:660px;margin:0 auto;}
.header{padding:22px 24px;border-radius:12px 12px 0 0;background:linear-gradient(135deg,#0d1f3c,#1a3a6e);}
.header h1{margin:0;font-size:20px;font-weight:700;color:#fff;}
.header p{margin:5px 0 0;font-size:13px;color:rgba(255,255,255,0.6);}
.body{background:#fff;border:1px solid #ddd;border-top:none;border-radius:0 0 12px 12px;padding-bottom:24px;}
.stat-row{display:flex;justify-content:space-around;padding:14px 8px 8px;border-bottom:1px solid #f0f0f0;}
.stat .num{font-size:22px;font-weight:700;}.stat .desc{font-size:11px;color:#aaa;}
.section{padding:16px 18px 0;}
.sec-title{font-size:11px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.8px;padding-bottom:7px;border-bottom:1px solid #eee;margin-bottom:10px;}
.card{border:1px solid #e8e8e8;border-radius:10px;margin-bottom:12px;overflow:hidden;}
.hcard{border:2px solid #185FA5;}
.card-head{background:#f7f7f7;padding:12px 15px;border-bottom:1px solid #eee;}
.ctop{display:flex;justify-content:space-between;align-items:flex-start;}
.sym{font-size:17px;font-weight:700;}.sym-sub{font-size:11px;color:#999;margin-top:2px;}
.cbadge{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:6px;margin-top:4px;background:#E6F1FB;color:#185FA5;}
.hbadge{background:#185FA5;color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;margin-left:6px;}
.pb{text-align:right;}.price{font-size:17px;font-weight:700;}
.vbox{margin:10px 15px 0;padding:11px 13px;border-radius:8px;}
.vlbl{font-size:14px;font-weight:700;margin-bottom:4px;}.vwhy{font-size:12px;line-height:1.6;}
.mrow{display:flex;flex-wrap:wrap;gap:14px;padding:10px 15px 6px;}
.ml{font-size:10px;color:#bbb;margin-bottom:1px;}.mv{font-size:12px;font-weight:600;}
.bwrap{padding:2px 15px 6px;}.bbg{background:#eee;border-radius:3px;height:5px;}
.blbl{display:flex;justify-content:space-between;font-size:10px;color:#ccc;margin-top:2px;}
.dbox{margin:0 15px 8px;padding:9px 12px;background:#f9f9f9;border-radius:7px;font-size:12px;color:#555;line-height:1.6;border-left:3px solid #e0e0e0;}
.rsns{padding:0 15px 8px;}
.ri{padding:7px 0;border-bottom:1px solid #f5f5f5;}.ri:last-child{border:none;}
.rtag{font-size:10px;font-weight:700;padding:1px 7px;border-radius:6px;display:inline-block;margin-bottom:3px;}
.rtext{font-size:12px;color:#444;line-height:1.55;}
.nsec{padding:4px 15px 10px;}.nlbl{font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;}
.ni{padding:5px 0;border-bottom:1px solid #f5f5f5;}.ni:last-child{border:none;}
.nr{display:flex;gap:6px;align-items:center;margin-bottom:2px;}
.nd{font-size:10px;color:#ccc;}.nb{font-size:10px;font-weight:600;padding:1px 6px;border-radius:5px;}
.nt{font-size:12px;color:#333;line-height:1.4;}.nt a{color:#185FA5;text-decoration:none;}
.divider{height:1px;background:#f0f0f0;margin:16px 18px 0;}
.footer{text-align:center;padding:14px 18px 0;font-size:11px;color:#bbb;line-height:1.7;}
.kbar{background:#EEF3FB;border-radius:8px;padding:10px 14px;margin:12px 18px 0;font-size:12px;color:#185FA5;}
.tbanner{padding:8px 14px;border-radius:8px;margin:8px 18px 0;font-size:12px;font-weight:500;}
</style>"""

def news_html(headlines):
    out=""
    for h in headlines[:4]:
        s=h["score"]
        bg,c,icon,lbl=("#E6F8F2","#1D9E75","▲","Positive") if s>0.15 else ("#FEF0F0","#E24B4A","▼","Negative") if s<-0.15 else ("#F0F0F0","#888","●","Neutral")
        src=f\'<span style="font-size:10px;color:#ccc;"> · {h["source"]}</span>\' if h.get("source") else ""
        out+=f\'\'\'<div class="ni"><div class="nr"><span class="nd">{h[\'date\']}</span><span class="nb" style="background:{bg};color:{c};">{icon} {lbl}</span>{src}</div><div class="nt"><a href="{h[\'url\']}" target="_blank">{h[\'title\']}</a></div></div>\'\'\'
    return out

def price_bar(price,low,high):
    if not all([price,low,high]) or high==low: return ""
    pct=max(0,min(100,(price-low)/(high-low)*100))
    col="#1D9E75" if pct<35 else "#EF9F27" if pct<65 else "#E24B4A"
    return f\'\'\'<div class="bwrap"><div style="font-size:10px;color:#ccc;margin-bottom:2px;">24h range — {pct:.0f}% from low</div><div class="bbg"><div style="background:{col};width:{pct:.0f}%;height:5px;border-radius:3px;"></div></div><div class="blbl"><span>{fmt_price(low)}</span><span>{fmt_price(high)}</span></div></div>\'\'\'

def rc(v): return "#0F6E56" if v and v<35 else "#A32D2D" if v and v>70 else "#555"

def coin_card(r):
    t=r["ticker"]; p=t["price"]; ch=t["change_24h"]; ih=r.get("is_holding",False)
    info=COIN_INFO.get(r["symbol"],None)
    cat=info[0] if info else "Altcoin"; nm=info[1] if info else r["symbol"]; desc=info[2] if info else f"{r[\'symbol\']} — auto-discovered on Kraken."
    hb=\'<span class="hbadge">★ YOUR HOLDING</span>\' if ih else ""
    h1s=f"{r[\'h1\']:+.2f}%" if r["h1"] is not None else "—"
    h4s=f"{r[\'h4\']:+.2f}%" if r["h4"] is not None else "—"
    vs=f"{r[\'vol_spike\']:.1f}×" if r["vol_spike"] else "—"
    ts={"UP":"↑ Up","DOWN":"↓ Down","SIDEWAYS":"→ Flat"}.get(r["trend"],"—")
    rs_html="".join(f\'<div class="ri"><div><span class="rtag" style="background:{x["color"]}22;color:{x["color"]};">{x["tag"]}</span></div><div class="rtext">{x["text"]}</div></div>\' for x in r["reasons"]) or \'<div style="font-size:12px;color:#bbb;padding:4px 0;">No strong signals — coin is quiet.</div>\'
    nh=news_html(r["news"])
    rsi_s=f"{r[\'rsi\']}" if r["rsi"] else "N/A"
    return f\'\'\'<div class="{"card hcard" if ih else "card"}">
<div class="card-head"><div class="ctop">
<div><div class="sym">{r["symbol"]}{hb}</div><div class="sym-sub">{nm}</div><div><span class="cbadge">{cat}</span></div></div>
<div class="pb"><div class="price">{fmt_price(p)}</div><div style="font-size:14px;font-weight:700;color:{cc(ch)};">{ch:+.2f}% today</div><div style="font-size:10px;color:#bbb;">Vol {fmt_vol(t["vol_usd"])} · {t["trades_24h"]:,} trades</div></div>
</div></div>
<div class="vbox" style="background:{r["verdict_bg"]};border-left:4px solid {r["verdict_color"]};"><div class="vlbl" style="color:{r["verdict_color"]};">{r["verdict"]}</div><div class="vwhy">{r["verdict_explanation"]}</div></div>
<div class="mrow"><div><div class="ml">1h</div><div class="mv" style="color:{cc(r["h1"])};">{h1s}</div></div><div><div class="ml">4h</div><div class="mv" style="color:{cc(r["h4"])};">{h4s}</div></div><div><div class="ml">RSI</div><div class="mv" style="color:{rc(r["rsi"])};">{rsi_s}</div></div><div><div class="ml">Vol spike</div><div class="mv">{vs}</div></div><div><div class="ml">Trend</div><div class="mv">{ts}</div></div><div><div class="ml">Spread</div><div class="mv">{t["spread_pct"]:.2f}%</div></div></div>
{price_bar(p,t["low_24h"],t["high_24h"])}
<div class="dbox"><strong>What is {r["symbol"]}?</strong> {desc}</div>
<div class="rsns"><div style="font-size:10px;color:#bbb;text-transform:uppercase;letter-spacing:.5px;padding:4px 0 5px;">Why it\'s moving — signal breakdown</div>{rs_html}</div>
{\'<div class="nsec"><div class="nlbl">Recent news</div>\'+nh+\'</div>\' if nh else ""}
</div>\'\'\'

def build_email(holdings, results, skipped):
    now=datetime.now(); ds=now.strftime("%A, %B %d %Y  ·  %I:%M %p PT")
    all_r=holdings+results
    bw=[r for r in all_r if "BUY WATCH" in r["verdict"]]
    wa=[r for r in all_r if "WORTH WATCHING" in r["verdict"]]
    ca=[r for r in all_r if "CAUTION" in r["verdict"] or "AVOID" in r["verdict"]]
    tg=max(all_r,key=lambda x:x["ticker"]["change_24h"],default=None)
    tv=max(all_r,key=lambda x:x.get("vol_spike") or 0,default=None)
    html=f\'\'\'<!DOCTYPE html><html><head><meta charset="UTF-8">{CSS}</head>
<body><div class="wrap">
<div class="header"><h1>🪙 Crypto Altcoin Brief</h1><p>{ds} · Kraken Canada · Auto-discovered coins under $2 USD</p></div>
<div class="body">
<div class="stat-row">
<div class="stat"><div class="num" style="color:#0F6E56;">{len(all_r)}</div><div class="desc">Coins scanned</div></div>
<div class="stat"><div class="num" style="color:#0F6E56;">{len(bw)}</div><div class="desc">Buy watch 🚀</div></div>
<div class="stat"><div class="num" style="color:#EF9F27;">{len(wa)}</div><div class="desc">Watching 👀</div></div>
<div class="stat"><div class="num" style="color:#E24B4A;">{len(ca)}</div><div class="desc">Avoid ⛔</div></div>
</div>
<div class="kbar">🇨🇦 <strong>Kraken Canada</strong> — FINTRAC registered · EFT CAD deposits · Maker 0.25% / Taker 0.40% · Pairs auto-discovered live from Kraken API</div>\'\'\'
    if tg: html+=f\'<div class="tbanner" style="background:#E6F8F2;color:#0F6E56;">🏆 Top gainer: <strong>{tg["symbol"]}</strong> {tg["ticker"]["change_24h"]:+.2f}% · Vol {fmt_vol(tg["ticker"]["vol_usd"])}</div>\'
    if tv and tv.get("vol_spike") and tv["vol_spike"]>1.8: html+=f\'<div class="tbanner" style="background:#FFF3CD;color:#7a5200;">🔊 Volume spike: <strong>{tv["symbol"]}</strong> {tv["vol_spike"]:.1f}× avg · {tv["ticker"]["change_24h"]:+.2f}%</div>\'
    if holdings:
        html+=\'<div class="section"><div class="sec-title">★ Your Holdings — PENGU & LUNA</div>\'
        for r in holdings: html+=coin_card(r)
        html+=\'</div><div class="divider"></div>\'
    bwnr=[r for r in results if "BUY WATCH" in r["verdict"]]
    if bwnr:
        html+=\'<div class="section"><div class="sec-title">🚀 Buy Watch — Bullish Signals Aligned</div>\'
        for r in bwnr: html+=coin_card(r)
        html+=\'</div><div class="divider"></div>\'
    wanr=[r for r in results if "WORTH WATCHING" in r["verdict"]]
    if wanr:
        html+=\'<div class="section"><div class="sec-title">👀 Worth Watching — Building Momentum</div>\'
        for r in wanr: html+=coin_card(r)
        html+=\'</div><div class="divider"></div>\'
    canr=[r for r in results if "CAUTION" in r["verdict"] or "AVOID" in r["verdict"]]
    if canr:
        html+=\'<div class="section"><div class="sec-title">⛔ Caution / Avoid</div>\'
        for r in canr: html+=coin_card(r)
        html+=\'</div><div class="divider"></div>\'
    nenr=[r for r in results if r["verdict"].startswith("⚪")]
    if nenr:
        nl=", ".join(r["symbol"] for r in nenr)
        html+=f\'<div class="section"><div class="sec-title">⚪ Quiet / Neutral</div><div style="font-size:12px;color:#888;padding:4px 0 12px;">{nl}</div></div>\'
    if skipped: html+=f\'<div style="margin:10px 18px 0;padding:9px 13px;background:#f5f5f5;border-radius:7px;font-size:12px;color:#888;">⛔ Skipped (above $2): {", ".join(skipped[:12])}{"..." if len(skipped)>12 else ""}</div>\'
    html+=\'\'\'<div class="footer"><strong>Crypto Altcoin Brief — research and education only. NOT financial advice.</strong><br>
Crypto is extremely volatile. Never invest more than you can afford to lose.<br>
Kraken Canada is FINTRAC-registered. Report crypto gains on your Canadian tax return.<br>
Coins auto-discovered via Kraken public API — list updates automatically with new listings.</div></div></div></body></html>\'\'\'
    return html

def send_email(subject, html_body, text_body):
    msg=MIMEMultipart("alternative"); msg["Subject"]=subject; msg["From"]=EMAIL_SENDER; msg["To"]=EMAIL_RECIPIENT
    msg.attach(MIMEText(text_body,"plain")); msg.attach(MIMEText(html_body,"html"))
    with smtplib.SMTP_SSL("smtp.gmail.com",465) as srv:
        srv.login(EMAIL_SENDER,EMAIL_PASSWORD); srv.sendmail(EMAIL_SENDER,EMAIL_RECIPIENT,msg.as_string())
    print(f"✅ Sent → {EMAIL_RECIPIENT}")

def run():
    now=datetime.now()
    print(f"🪙 Crypto Altcoin Brief — {now.strftime(\'%Y-%m-%d %H:%M PT\')}")
    print(f"   Price < ${MAX_PRICE_USD} · Vol > {fmt_vol(MIN_VOL_USD)} · no stables · holdings: {MY_HOLDINGS}")
    print("  Discovering all Kraken USD pairs via API...")
    all_pairs=discover_usd_pairs()
    print(f"  Found {len(all_pairs)} USD pairs on Kraken")
    hset=set(MY_HOLDINGS)
    ordered=[(p,s) for p,s in all_pairs if p in hset]+[(p,s) for p,s in all_pairs if p not in hset]
    holdings=[]; results=[]; skipped=[]; req=0

    def throttle():
        nonlocal req; req+=1
        time.sleep(1.5) if req%3!=0 else time.sleep(3)

    for i,(pair,symbol) in enumerate(ordered):
        ih=pair in hset
        print(f"  [{i+1}/{len(ordered)}] {symbol}{'  ★' if ih else ''}...",end=" ")
        ticker=get_ticker(pair); throttle()
        if not ticker: print("no data"); continue
        price=ticker["price"]; vol_usd=ticker["vol_usd"]
        if price>=MAX_PRICE_USD and not ih: print(f"{fmt_price(price)} skipped (≥$2)"); skipped.append(f"{symbol}({fmt_price(price)})"); continue
        if vol_usd<MIN_VOL_USD and not ih: print(f"{fmt_price(price)} low vol"); continue
        closes,volumes=get_ohlc(pair); throttle()
        rsi=calc_rsi(closes) if closes else None
        h1,h4=calc_momentum(closes) if closes else (None,None)
        vs=calc_vol_spike(volumes) if volumes else None
        td=trend_dir(closes) if closes else "SIDEWAYS"
        news=get_news(symbol); avs=avg_sent(news); throttle()
        reasons=build_reasons(ticker,rsi,h1,h4,vs,td,avs)
        v,vc,vb,ve,vscore=get_verdict(ticker,rsi,td,vs,avs,h1,h4)
        print(f"{fmt_price(price)} {ticker[\'change_24h\']:+.1f}% RSI={rsi} {v}")
        entry={"pair":pair,"symbol":symbol,"ticker":ticker,"rsi":rsi,"h1":h1,"h4":h4,
               "vol_spike":vs,"trend":td,"news":news,"avg_sent":avs,"reasons":reasons,
               "verdict":v,"verdict_color":vc,"verdict_bg":vb,"verdict_explanation":ve,
               "score":vscore,"is_holding":ih}
        if ih: holdings.append(entry)
        else: results.append(entry)

    results.sort(key=lambda x:x["score"],reverse=True)
    results=results[:TOP_N_EMAIL]
    all_r=holdings+results
    html_body=build_email(holdings,results,skipped)
    bw=len([r for r in all_r if "BUY WATCH" in r["verdict"]])
    av=len([r for r in all_r if "AVOID" in r["verdict"]])
    pg=next((r["ticker"]["change_24h"] for r in holdings if r["symbol"]=="PENGU"),0)
    lg=next((r["ticker"]["change_24h"] for r in holdings if r["symbol"]=="LUNA"),0)
    top_r=sorted(all_r,key=lambda x:x["ticker"]["change_24h"],reverse=True)
    top_s=top_r[0]["symbol"] if top_r else "—"; top_c=top_r[0]["ticker"]["change_24h"] if top_r else 0
    text_body="\\n".join(["="*64,f"CRYPTO BRIEF · {now.strftime(\'%b %d %Y %I:%M %p PT\')}",
        f"{len(all_r)} coins scanned · Kraken Canada · under $2 USD","="*64,
        "\\n★ YOUR HOLDINGS:"]+[f"  {r[\'symbol\']:<8} {fmt_price(r[\'ticker\'][\'price\']):<16} {r[\'ticker\'][\'change_24h\']:+.2f}%  {r[\'verdict\']}" for r in holdings]+
        ["\\nMARKET:"]+[f"  {r[\'symbol\']:<8} {fmt_price(r[\'ticker\'][\'price\']):<16} {r[\'ticker\'][\'change_24h\']:+.2f}%  {r[\'verdict\']}" for r in results]+
        ["","Research only — not financial advice.","="*64])
    subject=(f"🪙 Crypto · {now.strftime(\'%b %d\')} | ★ PENGU {pg:+.1f}% LUNA {lg:+.1f}% | "
             f"🚀{bw} buy · ⛔{av} avoid · Top: {top_s} {top_c:+.1f}%")
    print(text_body)
    if EMAIL_SENDER!="your@gmail.com": send_email(subject,html_body,text_body)
    else: print("⚠️  Set GitHub Secrets.")
