"""/watchlist/: bring your own stocks.

The page is an app (assets/watchlist.js) over one export, data/watch.json, which
carries every covered ticker's calls on every play, its trend and crash
exposure, plus aliases for matching what people paste. Tickers Quiplee doesn't
cover yet are posted to /api/watch (netlify/functions/watch.mjs); the nightly
job (tools/sync_requests.py) adds them, and the next build analyses them.
Lists live in the reader's browser; the analysis of every ticker is public.
"""
import html
import json
import math

from .content import TICKERS, TIMED, FAMILIES
from .render import next_move
from . import stockview as sv

e = html.escape
EXTRA_ALIASES = {"BITCOIN": "BTC-USD", "BTC": "BTC-USD", "ETHEREUM": "ETH-USD", "ETH": "ETH-USD", "ETHER": "ETH-USD",
                 "SPX": "^GSPC", "S&P": "^GSPC", "S&P500": "^GSPC", "S&P 500": "^GSPC", "NASDAQ": "^NDX", "NASDAQ 100": "^NDX", "NDX": "^NDX",
                 "DOW": "^DJI", "DOW JONES": "^DJI", "DJIA": "^DJI", "RUSSELL 2000": "^RUT", "RUT": "^RUT", "TSX": "^GSPTSE",
                 "GOOG": "GOOGL", "GOOGLE": "GOOGL", "FACEBOOK": "META", "RBC": "RY.TO", "ROYAL BANK": "RY.TO"}


def _r(v, n=5):
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) or math.isinf(v) else float(f"{v:.{n}g}")


def watch_json(site):
    plays = [{"s": p["slug"], "n": p["name"], "f": p["family"], "c": 1 if p.get("core") else 0} for p in TIMED]
    out, alias = {}, {}
    for t in TICKERS:
        sym = t["sym"]
        if (sym, "buy-and-hold") not in site.R:
            continue
        bh = site.R[(sym, "buy-and-hold")]
        meta = site.meta.get(sym) or {}
        states = "".join("-" if site.R.get((sym, p["slug"])) is None or site.R[(sym, p["slug"])]["state"] is None
                         else str(site.R[(sym, p["slug"])]["state"]) for p in TIMED)
        d1 = ma = None
        o = meta.get("ohlc")
        if o is not None and len(o) > 1:
            c = o["close"]
            d1 = float(c.iloc[-1] / c.iloc[-2] - 1)
            ma = float(c.iloc[-1] / c.iloc[-200:].mean() - 1) if len(c) >= 200 else None
        rk = meta.get("risk") or {}
        moves = {}
        for p in TIMED:
            if not p.get("core"):
                continue
            x = site.R.get((sym, p["slug"]))
            if x is not None:
                moves[p["slug"]] = next_move(x, p, t)["short"]
        out[sym] = {"n": t["name"], "s": t["short"], "g": t["group"], "u": t["slug"], "cur": t["cur"],
                    "p": _r(bh["price"], 6), "d1": _r(d1, 4), "y1": _r(site.one_year(t), 4), "ma": _r(ma, 4), "c": states,
                    "r": [rk.get("score"), rk.get("level")] if rk.get("level") else None, "m": moves}
        ol = sv.outlook(site, t)
        if ol["ok"]:
            out[sym]["up"] = _r(ol["upside"], 4)
            out[sym]["na"] = ol["n_an"]
        if t.get("requested"):
            out[sym]["req"] = t.get("since") or 1
        for a in {t["name"].upper(), t["short"].upper()}:
            if a and a != sym and a not in alias:
                alias[a] = sym
        f = site.fund.get(sym) or {}
        for a in (f.get("shortName"), f.get("longName")):
            if a and a.upper() not in alias:
                alias[a.upper()] = sym
    for a, s in EXTRA_ALIASES.items():
        if s in out:
            alias.setdefault(a, s)
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "plays": plays, "fams": [[k, n] for k, n, _ in FAMILIES],
                       "t": out, "alias": alias}, separators=(",", ":"), allow_nan=False)


def watchlist_page(site):
    path, depth = "watchlist/", 1
    h = lambda x: site.href(depth, x)
    n_cov = len([t for t in TICKERS])
    body = f"""
<section class="pair-head"><p class="eyebrow">Watchlist</p><h1 class="h1">Check your stocks against every play</h1>
<p class="lede">Paste your tickers or upload a holdings file from Wealthsimple or another broker. Names Quiplee already covers show their full read at once. New names join the queue, get analysed after the next U.S. close, and are ready the next day, for you and everyone else.</p></section>

<section class="wl" id="wl" data-base="{'../' * depth}" data-api="/api/watch" data-stock="{e(h('stocks/{u}/'))}" data-pair="{e(h('stocks/{u}/{s}/'))}">
<div class="card wl-add">
<label for="wl-in" class="h3">Add stocks</label>
<textarea id="wl-in" rows="3" placeholder="NVDA, SHOP.TO, Apple, BTC&#10;or one per line, or paste rows from a spreadsheet" spellcheck="false" autocomplete="off"></textarea>
<div class="wl-actions">
<button type="button" class="btn primary" id="wl-go">Add to my list</button>
<label class="btn" for="wl-file">Upload a CSV<input type="file" id="wl-file" accept=".csv,text/csv,text/plain" hidden></label>
<button type="button" class="btn" id="wl-share">Copy share link</button>
<button type="button" class="linkish small" id="wl-clear">Clear list</button>
</div>
<p class="small muted" id="wl-msg" aria-live="polite">Your list is saved in this browser only. A file is read on your device: Quiplee keeps only the symbols, and sends just the ones it doesn't cover yet to the queue.</p>
</div>
<noscript><p class="note-line">The watchlist needs JavaScript. Every covered stock also has its own page under <a href="{h('stocks/')}">Stocks</a>.</p></noscript>
<div class="wl-plays"><span class="small muted">Plays to count</span>
<div class="seg seg-sm" role="group" aria-label="Plays to count" id="wl-mode"><button type="button" data-v="core" aria-pressed="true">Core 20</button><button type="button" data-v="all" aria-pressed="false">All {len(TIMED)}</button><button type="button" data-v="pick" aria-pressed="false">Pick plays</button></div>
</div>
<div class="card wl-picker" id="wl-picker" hidden></div>
<div id="wl-sum" class="wl-sum"></div>
<div id="wl-list"></div>
</section>

<section class="split how">
<div class="card prose"><p class="eyebrow">How it works</p><ol>
<li><b>Add your tickers.</b> Type them, paste them or upload a CSV. Canadian listings use .TO (Toronto) or .V (Venture); a file's exchange column is read for you.</li>
<li><b>Covered names answer at once.</b> Quiplee covers {n_cov} stocks, ETFs, indexes and coins, each with every play's call, its trend and its crash exposure.</li>
<li><b>New names join the queue.</b> After the next U.S. close Quiplee checks each one has a price history, runs all {len(TIMED)} plays on it and publishes its page. The 20 core plays get a full page each.</li>
</ol></div>
<div class="card prose"><p class="eyebrow">What the columns mean</p><ul>
<li><b>Plays in:</b> how many of the plays you picked hold the stock now. Most in usually means a strong, broad trend; a split means the plays disagree.</li>
<li><b>Strip:</b> one square per play, green for in, red for out, in family order.</li>
<li><b>Crash exposure:</b> the storm test of market swings, past crashes, debt and run-up. <a href="{h('markets/')}#ex-h">More on Markets</a>.</li>
<li><b>Target:</b> how far analysts' average 12-month price target sits above the price (3+ analysts). The list is sorted half on plays in and half on this upside, the same score as <a href="{h('articles/green-across-the-board/')}">Green across the board</a>.</li>
<li><b>Weight:</b> your share of the list by value, when your file includes quantities or market values. Otherwise every name counts equally.</li>
</ul><p class="small muted">What published rules say, not advice. Quiplee doesn't know your goals, taxes or timeline.</p></div>
</section>
<section id="wl-readers"></section>
"""
    site.add(path, site.shell(path, "Watchlist · check your stocks against every play",
                              "Paste tickers or upload a Wealthsimple or broker CSV. See what 59 published trading plays, the trend and crash exposure say about each name; new names are analysed after the next close.",
                              body, active="watchlist/", scripts=("assets/widgets.js", "assets/watchlist.js")))
