"""Editorial content: the stock universe, the thinkers and the strategies.

Everything a reader sees about a person or a rule lives here, so it can be
reviewed in one place. Keep claims factual and sourced; paraphrase, don't quote.
"""

# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------
# kind: etf | crypto | stock    cur: display currency prefix
TICKERS = [
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
    {"sym": "MGRC", "name": "McGrath RentCorp", "group": "Industrials & rentals", "cur": "$"},
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
GROUP_ORDER = ["Indexes & ETFs", "Crypto", "Big tech", "Semiconductors", "Software & devices", "Healthcare",
               "Financials", "Industrials & rentals", "Energy & power", "Metals & mining", "Crypto miners", "Micro caps"]

for t in TICKERS:
    t["slug"] = t["sym"].lower().replace(".", "-")
    t["crypto"] = t["sym"].endswith("-USD")
    t["short"] = t["sym"].replace("-USD", "").replace(".TO", "").replace(".V", "")


# --------------------------------------------------------------------------
# Analysts (verified bios, books and sources live in analysts.json) and plays
# --------------------------------------------------------------------------
import json as _json
import os as _os

from .plays import PLAYS, PLAY, TIMED, BAR_WORD, FAMILIES, FAMILY, FAMILY_ORDER, by_family  # noqa: E402,F401

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
