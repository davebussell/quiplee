"""Editorial content: the stock universe, the thinkers and the strategies.

Everything a reader sees about a person or a rule lives here, so it can be
reviewed in one place. Keep claims factual and sourced; paraphrase, don't quote.
"""

# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------
# kind: etf | crypto | stock    cur: display currency prefix
TICKERS = [
    {"sym": "SPY", "name": "S&P 500 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "QQQ", "name": "Nasdaq-100 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "IWM", "name": "Russell 2000 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "XIU.TO", "name": "S&P/TSX 60 ETF", "group": "Indexes & ETFs", "cur": "C$"},
    {"sym": "GLD", "name": "Gold ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "TLT", "name": "20+ Year Treasury ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "BTC-USD", "name": "Bitcoin", "group": "Crypto", "cur": "$"},
    {"sym": "ETH-USD", "name": "Ether", "group": "Crypto", "cur": "$"},
    {"sym": "NVDA", "name": "Nvidia", "group": "US stocks", "cur": "$"},
    {"sym": "AMD", "name": "AMD", "group": "US stocks", "cur": "$"},
    {"sym": "AVGO", "name": "Broadcom", "group": "US stocks", "cur": "$"},
    {"sym": "MU", "name": "Micron", "group": "US stocks", "cur": "$"},
    {"sym": "MSFT", "name": "Microsoft", "group": "US stocks", "cur": "$"},
    {"sym": "AAPL", "name": "Apple", "group": "US stocks", "cur": "$"},
    {"sym": "AMZN", "name": "Amazon", "group": "US stocks", "cur": "$"},
    {"sym": "GOOGL", "name": "Alphabet", "group": "US stocks", "cur": "$"},
    {"sym": "META", "name": "Meta Platforms", "group": "US stocks", "cur": "$"},
    {"sym": "TSLA", "name": "Tesla", "group": "US stocks", "cur": "$"},
    {"sym": "LLY", "name": "Eli Lilly", "group": "US stocks", "cur": "$"},
    {"sym": "PFE", "name": "Pfizer", "group": "US stocks", "cur": "$"},
    {"sym": "JPM", "name": "JPMorgan Chase", "group": "US stocks", "cur": "$"},
    {"sym": "XOM", "name": "Exxon Mobil", "group": "US stocks", "cur": "$"},
    {"sym": "SHOP.TO", "name": "Shopify", "group": "Canadian stocks", "cur": "C$"},
    {"sym": "RY.TO", "name": "Royal Bank of Canada", "group": "Canadian stocks", "cur": "C$"},
]
GROUP_ORDER = ["Indexes & ETFs", "Crypto", "US stocks", "Canadian stocks"]

for t in TICKERS:
    t["slug"] = t["sym"].lower().replace(".", "-")
    t["crypto"] = t["sym"].endswith("-USD")
    t["short"] = t["sym"].replace("-USD", "").replace(".TO", "")


# --------------------------------------------------------------------------
# Thinkers
# --------------------------------------------------------------------------
THINKERS = [
    {
        "slug": "bitcoin-playboy",
        "name": "Bitcoin Playboy",
        "role": "Founder of the PlayBit trading community",
        "bio": "Runs PlayBit, a paid Discord community that trades stocks, options and crypto and sends members daily signals and watchlists. The PB EMA was published on TradingView by the developer FFriZz as the community's staple indicator and a personal favourite of Bitcoin Playboy.",
        "argues": [
            "A simple two-EMA band shows the trend regime at a glance: price above it is strength, below it is weakness.",
            "The band doubles as support and resistance, so pullbacks into it are where decisions get made.",
        ],
        "sources": [
            ("PlayBit EMA on TradingView (taken down 30 Sep 2026)", "https://www.tradingview.com/scripts/pb-ema/"),
            ("PlayBit reviews on Trustpilot", "https://www.trustpilot.com/review/playbit.info"),
        ],
        "strategies": ["pb-ema"],
    },
    {
        "slug": "benjamin-cowen",
        "name": "Benjamin Cowen",
        "role": "Crypto analyst, Into The Cryptoverse",
        "bio": "Runs the Into The Cryptoverse YouTube channel and research service. He popularised the \"bull market support band\" for Bitcoin: the 20-week simple and 21-week exponential moving averages read together.",
        "argues": [
            "In a healthy bull market, price holds above the band and corrections tend to find support at it.",
            "Losing the band on a weekly close has historically preceded extended weakness.",
            "He has also said that in the current cycle the 50-week average has been the more reliable support.",
        ],
        "sources": [
            ("Bull Market Support Band on LuxAlgo", "https://www.luxalgo.com/library/indicator/uSBR7cFa-bull-market-support-band-20w-sma-21w-ema/"),
            ("Cowen's band update (video summary)", "https://rosetta.to/u/intothecryptoverse/bitcoin-bull-market-support-band-2025-10-23"),
        ],
        "strategies": ["bull-market-support-band"],
    },
    {
        "slug": "ripster",
        "name": "Ripster",
        "role": "Creator of the EMA Cloud system",
        "bio": "Trader and TradingView author (ripster47) behind the EMA Cloud system, which shades the space between pairs of EMAs so trend and pullback zones are easy to see. His clouds are widely used by day and swing traders.",
        "argues": [
            "Short clouds such as 5/12 act as a fluid trendline for day trades.",
            "Price holding above the 34/50 cloud confirms a bullish bias on any timeframe; below it, bearish.",
        ],
        "sources": [("Ripster EMA Clouds on TradingView", "https://www.tradingview.com/scripts/ripster/")],
        "strategies": ["ripster-ema-clouds"],
    },
    {
        "slug": "mark-minervini",
        "name": "Mark Minervini",
        "role": "Stock trader and author",
        "bio": "Won the 1997 U.S. Investing Championship and wrote Trade Like a Stock Market Wizard. His Trend Template is a checklist of moving-average and 52-week-range conditions a stock must meet before he will consider buying it.",
        "argues": [
            "Only buy stocks already in a confirmed Stage 2 uptrend, with price above rising 50, 150 and 200-day averages.",
            "Leaders trade near their 52-week highs and well above their 52-week lows.",
        ],
        "sources": [
            ("Mark Minervini's Trend Template on TradingView", "https://www.tradingview.com/script/22JWROvE-Mark-Minervini-s-Trend-Template/"),
            ("Trend Template criteria (ProRealCode)", "https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini"),
        ],
        "strategies": ["trend-template"],
    },
    {
        "slug": "stan-weinstein",
        "name": "Stan Weinstein",
        "role": "Author of Secrets for Profiting in Bull and Bear Markets",
        "bio": "Technical analyst whose 1988 book laid out Stage Analysis: every stock cycles through basing, advancing, topping and declining stages, and the 30-week moving average tells you which one you are in.",
        "argues": [
            "Buy in Stage 2, when price breaks above a 30-week average that has flattened and turned up.",
            "Get out when price closes back below the 30-week average; never hold a Stage 4 decline.",
        ],
        "sources": [("Stan Weinstein 30-week moving average on TradingView", "https://www.tradingview.com/script/BSLCP2eI-Stan-Weinstein-30-week-Moving-Average/")],
        "strategies": ["stage-analysis"],
    },
    {
        "slug": "meb-faber",
        "name": "Meb Faber",
        "role": "Co-founder and CIO, Cambria Investment Management",
        "bio": "Author of A Quantitative Approach to Tactical Asset Allocation (Journal of Wealth Management, 2007), one of the most downloaded papers on SSRN. It holds an asset only while its month-end price is above its 10-month average.",
        "argues": [
            "A 10-month average filter gives equity-like returns with far smaller drawdowns across asset classes.",
            "His 10-year revisit found the rule shone in 2008-09, then trailed stocks in six of the next eight years.",
        ],
        "sources": [
            ("Swedroe on Faber's rule, 10 years later (ETF.com)", "https://www.etf.com/sections/index-investor-corner/swedroe-why-financial-trends-persist"),
            ("CXO Advisory review of the 2013 update", "https://www.cxoadvisory.com/?p=1115"),
        ],
        "strategies": ["ten-month-sma"],
    },
    {
        "slug": "moskowitz-ooi-pedersen",
        "name": "Moskowitz, Ooi & Pedersen",
        "role": "Authors of Time Series Momentum (2012)",
        "bio": "Tobias Moskowitz, Yao Hua Ooi and Lasse Heje Pedersen documented time-series momentum in the Journal of Financial Economics in 2012: an asset's own past 12-month excess return predicts its next month, across equity, bond, currency and commodity futures.",
        "argues": [
            "Trends persist: assets that rose over the last year tend to keep rising in the near term, then partly reverse over longer horizons.",
            "A diversified time-series momentum portfolio performed best in extreme markets.",
        ],
        "sources": [
            ("Time Series Momentum (AQR library)", "https://www.aqr.com/library/journal-articles/time-series-momentum"),
            ("Time Series Momentum (SSRN)", "https://papers.ssrn.com/abstract=2089463"),
        ],
        "strategies": ["time-series-momentum"],
    },
    {
        "slug": "john-bogle",
        "name": "John C. Bogle",
        "role": "Founder of Vanguard",
        "bio": "Founded Vanguard in 1975 and launched the first index mutual fund for individual investors the following year. He argued that most investors do better by owning the market cheaply and staying put than by trying to time it.",
        "argues": [
            "Costs and bad timing are the two biggest drags on investor returns.",
            "Buy the whole market, keep fees low and hold it.",
        ],
        "sources": [("John Bogle, Vanguard founder who urged low fees (WealthManagement.com)", "https://www.wealthmanagement.com/people/john-bogle-vanguard-founder-who-urged-low-fees-dies-89")],
        "strategies": ["buy-and-hold"],
        "benchmark": True,
    },
    {
        "slug": "valeriy-zakamulin",
        "name": "Valeriy Zakamulin",
        "role": "Professor of Finance, University of Agder",
        "bio": "Author of Market Timing with Moving Averages (2017) and a series of papers testing moving-average rules on up to 155 years of U.S. stock data, with trading costs and out-of-sample methods designed to avoid data-mining.",
        "argues": [
            "Found no statistically significant outperformance from timing rules in the second half of his long sample.",
            "Timing rules generate many false signals in both bull and bear markets, but tend to beat the market in bear states.",
            "Most of their edge comes from a handful of severe bear markets, so investors can lag buy-and-hold for years.",
        ],
        "sources": [
            ("A Comprehensive Look at the Empirical Performance of Moving Average Trading Strategies (SSRN)", "https://papers.ssrn.com/abstract=2677212"),
            ("Swedroe: Beware the lure of market timing (ETF.com)", "https://www.etf.com/node/94433.md"),
        ],
        "strategies": [],
        "skeptic": True,
    },
]
THINKER = {t["slug"]: t for t in THINKERS}


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------
# kind drives the engine: band | template | stage | faber | tsmom | hold
STRATEGIES = [
    {
        "slug": "pb-ema", "name": "PB EMA", "long": "PB EMA band", "thinker": "bitcoin-playboy",
        "kind": "band", "bar": "D", "fast": (12, "ema"), "slow": (21, "ema"),
        "lines": ["EMA 12", "EMA 21"],
        "short": "Two exponential moving averages with a shaded band between them. Above the band is bullish, below is bearish, inside is undecided.",
        "rules": [
            "In when a daily close is above both EMAs.",
            "Out when a daily close is below both EMAs.",
            "Inside the band, the rule keeps its last call.",
        ],
        "assumptions": [
            "The PB EMA's lengths were never stated in its public description, and the TradingView page was taken down on 30 Sep 2026. Quiplee tests the two-EMA band with 12 and 21 days until the real lengths are confirmed.",
        ],
        "flag": "Lengths unconfirmed",
    },
    {
        "slug": "bull-market-support-band", "name": "Bull Market Support Band", "long": "Bull Market Support Band",
        "thinker": "benjamin-cowen", "kind": "band", "bar": "W", "fast": (20, "sma"), "slow": (21, "ema"),
        "lines": ["20-week SMA", "21-week EMA"],
        "short": "The 20-week simple and 21-week exponential moving averages read as one band. Bull markets tend to hold above it.",
        "rules": [
            "In when a weekly close is above both averages.",
            "Out when a weekly close is below both averages.",
            "Inside the band, the rule keeps its last call.",
        ],
        "assumptions": ["Weeks end on Friday for stocks and ETFs, and on Sunday for crypto."],
    },
    {
        "slug": "ripster-ema-clouds", "name": "Ripster EMA Cloud", "long": "Ripster 34/50 EMA Cloud",
        "thinker": "ripster", "kind": "band", "bar": "D", "fast": (34, "ema"), "slow": (50, "ema"),
        "lines": ["EMA 34", "EMA 50"],
        "short": "The 34/50 EMA cloud that Ripster uses to set a bullish or bearish bias, tested here on the daily chart.",
        "rules": [
            "In when a daily close is above the 34/50 cloud.",
            "Out when a daily close is below the cloud.",
            "Inside the cloud, the rule keeps its last call.",
        ],
        "assumptions": ["Ripster uses several clouds and timeframes. Quiplee grades the 34/50 bias cloud on daily bars."],
    },
    {
        "slug": "trend-template", "name": "Trend Template", "long": "Minervini Trend Template",
        "thinker": "mark-minervini", "kind": "template", "bar": "D",
        "lines": ["50-day SMA", "150-day SMA", "200-day SMA"],
        "short": "A seven-point checklist of moving-average and 52-week-range conditions that marks a stock in a confirmed uptrend.",
        "rules": [
            "In when all seven conditions pass: price above the 50, 150 and 200-day averages; 150-day above 200-day; 200-day higher than a month ago; 50-day above the 150 and 200-day; price at least 30% above its 52-week low and within 25% of its 52-week high.",
            "Out on a daily close below the 50-day average.",
        ],
        "assumptions": [
            "Minervini's eighth condition, a relative-strength rating of 70 or more, needs a full-market ranking and is left out.",
            "The template is a buy screen, not an exit system. The 50-day exit is Quiplee's assumption.",
            "The 52-week range uses closing prices.",
        ],
    },
    {
        "slug": "stage-analysis", "name": "Stage Analysis", "long": "Weinstein Stage Analysis",
        "thinker": "stan-weinstein", "kind": "stage", "bar": "W",
        "lines": ["30-week SMA"],
        "short": "The 30-week moving average splits a stock's life into four stages. Own it only in Stage 2, when price is above a rising average.",
        "rules": [
            "In when a weekly close is above a rising 30-week average.",
            "Out when a weekly close is below the 30-week average.",
        ],
        "assumptions": ["Rising means higher than it was four weeks earlier."],
    },
    {
        "slug": "ten-month-sma", "name": "10-Month SMA", "long": "Faber 10-month SMA",
        "thinker": "meb-faber", "kind": "faber", "bar": "M",
        "lines": ["10-month SMA"],
        "short": "Check once a month. Hold the asset while its month-end price is above its 10-month average; otherwise sit in Treasury bills.",
        "rules": [
            "In when the month-end close is above the 10-month average.",
            "Out, in T-bills, when it closes below.",
        ],
        "assumptions": ["Signals are acted on the first trading day of the next month."],
    },
    {
        "slug": "time-series-momentum", "name": "12-Month Momentum", "long": "Time-series momentum (12-month)",
        "thinker": "moskowitz-ooi-pedersen", "kind": "tsmom", "bar": "M",
        "lines": ["Price 12 months ago + T-bill return"],
        "short": "Hold the asset while its return over the last 12 months beats Treasury bills. Otherwise sit in bills.",
        "rules": [
            "In when the 12-month return at month-end beats the 12-month T-bill return.",
            "Out, in T-bills, when it doesn't.",
        ],
        "assumptions": ["The paper also goes short. Quiplee tests the long-only version an individual investor can run."],
    },
    {
        "slug": "buy-and-hold", "name": "Buy & Hold", "long": "Buy and hold (benchmark)",
        "thinker": "john-bogle", "kind": "hold", "bar": "D",
        "lines": [],
        "short": "Own it and never sell. Every other strategy on Quiplee is graded against this one.",
        "rules": ["Always in."],
        "assumptions": [],
        "benchmark": True,
    },
]
STRATEGY = {s["slug"]: s for s in STRATEGIES}
TIMED = [s for s in STRATEGIES if not s.get("benchmark")]

BAR_WORD = {"D": "daily", "W": "weekly", "M": "month-end"}
