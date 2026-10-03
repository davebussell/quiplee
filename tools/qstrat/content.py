"""Editorial content: the stock universe, the thinkers and the strategies.

Everything a reader sees about a person or a rule lives here, so it can be
reviewed in one place. Keep claims factual and sourced; paraphrase, don't quote.
"""

# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------
# kind: etf | crypto | stock    cur: display currency prefix
TICKERS = [
    # Market indexes (benchmarks: not directly tradable; buy them through an index ETF)
    {"sym": "^GSPC", "name": "S&P 500 index", "short": "S&P 500", "slug": "sp500", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^NDX", "name": "Nasdaq-100 index", "short": "Nasdaq-100", "slug": "nasdaq-100", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^DJI", "name": "Dow Jones Industrial Average", "short": "Dow", "slug": "dow", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^RUT", "name": "Russell 2000 index", "short": "Russell 2000", "slug": "russell-2000", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^GSPTSE", "name": "S&P/TSX Composite index", "short": "TSX", "slug": "tsx", "group": "Market indexes", "cur": "", "index": True},
    # US sector ETFs (Select Sector SPDRs, plus a semiconductor ETF)
    {"sym": "XLK", "name": "Technology Select Sector ETF", "short": "XLK", "group": "Sectors", "cur": "$", "sector": "Technology"},
    {"sym": "SMH", "name": "VanEck Semiconductor ETF", "short": "SMH", "group": "Sectors", "cur": "$", "sector": "Semiconductors"},
    {"sym": "XLC", "name": "Communication Services Select Sector ETF", "short": "XLC", "group": "Sectors", "cur": "$", "sector": "Communication services"},
    {"sym": "XLY", "name": "Consumer Discretionary Select Sector ETF", "short": "XLY", "group": "Sectors", "cur": "$", "sector": "Consumer discretionary"},
    {"sym": "XLF", "name": "Financial Select Sector ETF", "short": "XLF", "group": "Sectors", "cur": "$", "sector": "Financials"},
    {"sym": "XLV", "name": "Health Care Select Sector ETF", "short": "XLV", "group": "Sectors", "cur": "$", "sector": "Health care"},
    {"sym": "XLI", "name": "Industrial Select Sector ETF", "short": "XLI", "group": "Sectors", "cur": "$", "sector": "Industrials"},
    {"sym": "XLE", "name": "Energy Select Sector ETF", "short": "XLE", "group": "Sectors", "cur": "$", "sector": "Energy"},
    {"sym": "XLB", "name": "Materials Select Sector ETF", "short": "XLB", "group": "Sectors", "cur": "$", "sector": "Materials"},
    {"sym": "XLP", "name": "Consumer Staples Select Sector ETF", "short": "XLP", "group": "Sectors", "cur": "$", "sector": "Consumer staples"},
    {"sym": "XLU", "name": "Utilities Select Sector ETF", "short": "XLU", "group": "Sectors", "cur": "$", "sector": "Utilities"},
    {"sym": "XLRE", "name": "Real Estate Select Sector ETF", "short": "XLRE", "group": "Sectors", "cur": "$", "sector": "Real estate"},
    # Indexes & ETFs
    {"sym": "SPY", "name": "S&P 500 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "QQQ", "name": "Nasdaq-100 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "IWM", "name": "Russell 2000 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "XIU.TO", "name": "S&P/TSX 60 ETF", "group": "Indexes & ETFs", "cur": "C$"},
    {"sym": "GLD", "name": "Gold ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "SLV", "name": "Silver ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "TLT", "name": "20+ Year Treasury ETF", "group": "Indexes & ETFs", "cur": "$"},
    # Crypto
    {"sym": "BTC-USD", "name": "Bitcoin", "group": "Crypto", "cur": "$"},
    {"sym": "ETH-USD", "name": "Ether", "group": "Crypto", "cur": "$"},
    # Big tech
    {"sym": "AAPL", "name": "Apple", "group": "Big tech", "cur": "$"},
    {"sym": "MSFT", "name": "Microsoft", "group": "Big tech", "cur": "$"},
    {"sym": "AMZN", "name": "Amazon", "group": "Big tech", "cur": "$"},
    {"sym": "GOOGL", "name": "Alphabet", "group": "Big tech", "cur": "$"},
    {"sym": "META", "name": "Meta Platforms", "group": "Big tech", "cur": "$"},
    {"sym": "TSLA", "name": "Tesla", "group": "Big tech", "cur": "$"},
    # Semiconductors
    {"sym": "NVDA", "name": "Nvidia", "group": "Semiconductors", "cur": "$"},
    {"sym": "AMD", "name": "AMD", "group": "Semiconductors", "cur": "$"},
    {"sym": "AVGO", "name": "Broadcom", "group": "Semiconductors", "cur": "$"},
    {"sym": "MU", "name": "Micron", "group": "Semiconductors", "cur": "$"},
    {"sym": "INTC", "name": "Intel", "group": "Semiconductors", "cur": "$"},
    {"sym": "LSCC", "name": "Lattice Semiconductor", "group": "Semiconductors", "cur": "$"},
    {"sym": "STM", "name": "STMicroelectronics", "group": "Semiconductors", "cur": "$"},
    {"sym": "STHH", "name": "STMicroelectronics (currency-hedged ETF)", "group": "Semiconductors", "cur": "$"},
    # Software & devices
    {"sym": "SHOP.TO", "name": "Shopify", "group": "Software & devices", "cur": "C$"},
    {"sym": "BB.TO", "name": "BlackBerry", "group": "Software & devices", "cur": "C$"},
    {"sym": "SUPX", "name": "SuperX AI Technology", "group": "Software & devices", "cur": "$"},
    {"sym": "GPRO", "name": "GoPro", "group": "Software & devices", "cur": "$"},
    # Healthcare
    {"sym": "LLY", "name": "Eli Lilly", "group": "Healthcare", "cur": "$"},
    {"sym": "PFE", "name": "Pfizer", "group": "Healthcare", "cur": "$"},
    {"sym": "BSX", "name": "Boston Scientific", "group": "Healthcare", "cur": "$"},
    {"sym": "MDT", "name": "Medtronic", "group": "Healthcare", "cur": "$"},
    {"sym": "NPCE", "name": "NeuroPace", "group": "Healthcare", "cur": "$"},
    # Financials
    {"sym": "JPM", "name": "JPMorgan Chase", "group": "Financials", "cur": "$"},
    {"sym": "RY.TO", "name": "Royal Bank of Canada", "group": "Financials", "cur": "C$"},
    # Industrials & rentals
    {"sym": "CARR", "name": "Carrier Global", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "URI", "name": "United Rentals", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "R", "name": "Ryder System", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "WSC", "name": "WillScot", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "HTZ", "name": "Hertz", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "CAR", "name": "Avis Budget", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "TRNS", "name": "Transcat", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "FLXS", "name": "Flexsteel Industries", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "FC", "name": "Franklin Covey", "group": "Industrials & rentals", "cur": "$"},
    # Energy & power
    {"sym": "XOM", "name": "Exxon Mobil", "group": "Energy & power", "cur": "$"},
    {"sym": "APA", "name": "APA Corp", "group": "Energy & power", "cur": "$"},
    {"sym": "CVE.TO", "name": "Cenovus Energy", "group": "Energy & power", "cur": "C$"},
    {"sym": "WCP.TO", "name": "Whitecap Resources", "group": "Energy & power", "cur": "C$"},
    {"sym": "EIX", "name": "Edison International", "group": "Energy & power", "cur": "$"},
    {"sym": "FLNC", "name": "Fluence Energy", "group": "Energy & power", "cur": "$"},
    {"sym": "EOSE", "name": "Eos Energy", "group": "Energy & power", "cur": "$"},
    # Metals & mining
    {"sym": "AEM.TO", "name": "Agnico Eagle Mines", "group": "Metals & mining", "cur": "C$"},
    {"sym": "IMG.TO", "name": "IAMGOLD", "group": "Metals & mining", "cur": "C$"},
    {"sym": "HBM.TO", "name": "Hudbay Minerals", "group": "Metals & mining", "cur": "C$"},
    {"sym": "CS.TO", "name": "Capstone Copper", "group": "Metals & mining", "cur": "C$"},
    # Crypto miners
    {"sym": "MARA", "name": "MARA Holdings", "group": "Crypto miners", "cur": "$"},
    {"sym": "RIOT", "name": "Riot Platforms", "group": "Crypto miners", "cur": "$"},
    {"sym": "BTDR", "name": "Bitdeer Technologies", "group": "Crypto miners", "cur": "$"},
    # Micro caps (under $100M)
    {"sym": "OPTT", "name": "Ocean Power Technologies", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "PRSO", "name": "Peraso", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "HOLO", "name": "MicroCloud Hologram", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "NAMM", "name": "Namib Minerals", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "LEAP.V", "name": "Quantum Critical Metals", "group": "Micro caps", "cur": "C$", "micro": True},
    {"sym": "QUTX", "name": "Quantum X", "group": "Micro caps", "cur": "$", "micro": True},
]
GROUP_ORDER = ["Market indexes", "Sectors", "Indexes & ETFs", "Crypto", "Big tech", "Semiconductors", "Software & devices", "Healthcare",
               "Financials", "Industrials & rentals", "Energy & power", "Metals & mining", "Crypto miners", "Micro caps"]

# Tickers Quiplee doesn't cover, even if a reader asks for them
EXCLUDED = {"MGRC"}

# Reader-requested tickers (added by the nightly queue; see tools/sync_requests.py)
import json as _json0
import os as _os0
_REQ = _os0.path.join(_os0.path.dirname(_os0.path.dirname(_os0.path.dirname(_os0.path.abspath(__file__)))), "data", "universe", "requested.json")
_known = {t["sym"] for t in TICKERS}
if _os0.path.exists(_REQ):
    for _r in _json0.load(open(_REQ)).get("tickers", []):
        if _r.get("status") == "ok" and _r["sym"] not in _known and _r["sym"] not in EXCLUDED:
            TICKERS.append({"sym": _r["sym"], "name": _r.get("name") or _r["sym"], "group": "Reader-requested",
                            "cur": _r.get("cur", "$"), "requested": True, "since": _r.get("added")})
            _known.add(_r["sym"])
GROUP_ORDER.append("Reader-requested")


def _short(sym):
    return sym.replace("-USD", "").replace(".TO", "").replace(".V", "").replace(".NE", "").replace("^", "")


for t in TICKERS:
    t.setdefault("slug", t["sym"].lower().replace(".", "-").replace("^", ""))
    t["crypto"] = t["sym"].endswith("-USD")
    t.setdefault("short", _short(t["sym"]))
    t["canadian"] = t["sym"].endswith((".TO", ".V", ".NE")) or t["sym"] == "^GSPTSE"
    # benchmark for beta and crash comparisons
    if t["sym"] == "^GSPC":
        t["bench"] = None
    elif t["canadian"]:
        t["bench"] = "^GSPTSE" if t["sym"] != "^GSPTSE" else "^GSPC"
    else:
        t["bench"] = "^GSPC"
TK_BY_SYM = {t["sym"]: t for t in TICKERS}
INDEXES = [t for t in TICKERS if t.get("index")]


# --------------------------------------------------------------------------
# Analysts (verified bios, books and sources live in analysts.json) and plays
# --------------------------------------------------------------------------
import json as _json
import os as _os

from .plays import PLAYS, PLAY, TIMED, CORE, CORE_SLUGS, BAR_WORD, FAMILIES, FAMILY, FAMILY_ORDER, by_family  # noqa: E402,F401

with open(_os.path.join(_os.path.dirname(__file__), "analysts.json"), encoding="utf-8") as _f:
    THINKERS = _json.load(_f)
for _a in THINKERS:
    _a["sources"] = [tuple(x) for x in _a["sources"]]
    _a["strategies"] = [p["slug"] for p in PLAYS if _a["slug"] in p["analysts"]]
for _p in PLAYS:
    _p["thinker"] = _p["analysts"][0]
THINKER = {t["slug"]: t for t in THINKERS}
_missing = {a for p in PLAYS for a in p["analysts"]} - set(THINKER)
assert not _missing, f"plays credit unknown analysts: {_missing}"

STRATEGIES = PLAYS
STRATEGY = PLAY


def credit(p):
    """'A' or 'A & B' for a play's analysts."""
    return " & ".join(THINKER[a]["name"] for a in p["analysts"])
