"""HTML renderer for the plays site. Pure functions over engine results.

Links are relative so the same output works on quiplee.com and in a static
preview; `preview=True` spells out index.html for hosts without directory
indexes.
"""
import html
import json
import math

import numpy as np
import pandas as pd

from .linker import link_terms
from . import stockview as sv
from .content import (TICKERS, THINKERS, THINKER, PLAYS, PLAY, TIMED, GROUP_ORDER, BAR_WORD,
                      FAMILIES, FAMILY, FAMILY_ORDER, credit)

e = html.escape
TK = {t["sym"]: t for t in TICKERS}


def universe():
    """The curated list. Reader-requested tickers get their own pages but stay out
    of the cross-stock tables and counts, which would otherwise shift as readers add names."""
    return [t for t in TICKERS if not t.get("requested")]


def plays_for(t):
    """Plays that get a page of their own on this ticker (core 20 for reader requests)."""
    return [p for p in TIMED if p.get("core")] if t.get("requested") else TIMED
BASE = "https://quiplee.com/"
FONTS = ("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700"
         "&family=Geist+Mono:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap")
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' "
        "fill='%230b0f17'/%3E%3Ctext x='13' y='44' font-family='Arial,sans-serif' font-size='38' font-weight='800' fill='%23e7edf7'%3Eq%3C/text%3E"
        "%3Cpath d='M40 40 L48 26 L56 40 Z' fill='%231fd093'/%3E%3C/svg%3E")
NAV = [("markets/", "Markets"), ("stocks/", "Stocks"), ("strategies/", "Plays"), ("thinkers/", "Analysts"),
       ("learn/", "Learn"), ("articles/", "Articles"), ("watchlist/", "Watchlist"), ("desk/", "Live desk")]
ROLE_VAR = {"s1": "--s1", "s2": "--s2", "s3": "--s3", "price": "--s-price", "bench": "--s-bench"}


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------
def money(v, cur="$"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if abs(v) >= 10000:
        return f"{cur}{v:,.0f}"
    if 0 < abs(v) < 1:            # sub-dollar and penny stocks: keep 3 significant digits
        places = min(6, max(2, -int(math.floor(math.log10(abs(v)))) + 2))
        return f"{cur}{v:.{places}f}"
    return f"{cur}{v:,.2f}"


def pct(v, sign=True, d=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:,.{d}f}%"
    if v < 0 and round(abs(v) * 100, d) != 0:
        return "−" + s
    return ("+" + s) if (sign and v > 0) else s


def ratio(v):
    return "–" if v is None else f"{v:.2f}".replace("-", "−")


def dlong(ts):
    return "–" if ts is None else pd.Timestamp(ts).strftime("%b %-d, %Y")


def dshort(ts):
    return "–" if ts is None else pd.Timestamp(ts).strftime("%b %-d")


def dir_cls(v):
    return "" if v is None else ("up" if v > 0 else "down" if v < 0 else "")


def pill(state, lg=False):
    if state is None:
        return '<span class="pill">–</span>'
    cls = "in" if state == 1 else "out"
    return f'<span class="pill {cls}{" lg" if lg else ""}">{"IN" if state == 1 else "OUT"}</span>'


def sortv(v):
    """Raw value for a cell's data-v sort attribute; blank sorts last."""
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.6g}"


BAND_MARK = '<span class="band-mark" title="Inside the band"></span>'


def flag_tag(s):
    return f' <span class="tag warn">{e(s["flag"])}</span>' if s.get("flag") else ""


def sig(v, n=5):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        return None
    return float(f"{v:.{n}g}")


sig5 = sig


def n_people():
    """Analysts behind at least one play (not the benchmark, not 'market tradition')."""
    return len([a for a in THINKERS if a["strategies"] and not a.get("benchmark") and a["slug"] != "market-tradition"])


def fill_bar(k, n):
    w = 0 if not n else round(100 * k / n)
    return (f'<span class="fillbar" aria-hidden="true"><i style="width:{w}%"></i></span>')


def count_in(k, n, word="in"):
    return f'<span class="consensus">{fill_bar(k, n)}{k} of {n} {word}</span>'


# --------------------------------------------------------------------------
# the "next move" sentence
# --------------------------------------------------------------------------
BAR_CLOSE = {"D": "a daily close", "W": "a weekly close", "M": "a month-end close"}
BAR_PERIOD = {"W": "week", "M": "month"}
WAIT = {
    "rsi-30-70": "It needs RSI to cross 30 or 70, which takes more than one day from here.",
    "stochastic-20-80": "It needs a %K/%D crossover inside the 20 or 80 zone, which takes more than one day from here.",
    "williams-percent-r": "It needs %R to cross −80 or −20, which takes more than one day from here.",
    "money-flow-index": "It needs the MFI to cross 20 or 80, which takes more than one day from here.",
    "demark-setup-9": "It needs a full nine-day setup to complete.",
    "williams-alligator": "The Alligator's lines are shifted forward in time, so tomorrow's close can't move them.",
    "twelve-one-momentum": "The rule skips the most recent month, so the next close doesn't count. Its next call is already set by closes you can see.",
    "golden-cross": "The 50- and 200-day averages are too far apart for one close to cross them.",
    "seykota-crossover": "The two averages are too far apart for one close to cross them.",
    "on-balance-volume": "On-balance volume moves by one day's volume at most, which isn't enough here.",
    "chaikin-money-flow": "Money flow would need to move past ±0.05, more than one day can do from here.",
    "coppock-curve": "The curve moves slowly; one month-end won't turn it.",
    "rsi-2-pullback": "It needs a dip that drives the 2-day RSI under 10 while the stock holds above its 200-day average.",
    "double-7s": "It needs a close at a 7-day low while the stock holds above its 200-day average.",
    "mayer-multiple": "The price would need to reach 2.4 times its 200-day average.",
    "trend-template": "Several conditions are failing at once, so no single close passes them all.",
    "darvas-box": "It needs a confirmed box first: three days without a new high, then three without a new low.",
    "adx-directional-movement": "It needs +DI above −DI with ADX above 25, and ADX moves slowly.",
    "best-six-months-macd": "The buy window is open, but it needs a fresh MACD crossover, which takes more than one day from here.",
    "seasonal-timing-strategy": "The window is open, but MACD would need to cross its signal line, which takes more than one day from here.",
    "cci-100": "It needs the CCI to cross +100, which takes more than one day from here.",
    "elder-impulse": "It needs the 13-day EMA and the MACD histogram to move together, which takes more than one day from here.",
}


def next_move(res, s, t):
    cur, price, trig, bar = t["cur"], res["price"], res["trigger"], res["bar"]
    out = {"headline": "", "short": "", "level": None, "dist": None, "check": "", "alert": None, "notes": [],
           "checks": trig.get("extra", {}).get("checks"), "kind": trig.get("kind")}
    nc = res["next_check"]
    if bar == "D":
        out["check"] = f"Next check: the {dlong(nc)} close"
    elif res["bar_complete"]:
        out["check"] = f"Next check: the {BAR_PERIOD[bar]} ending {dlong(nc)}"
    else:
        out["check"] = f"Next check: this {BAR_PERIOD[bar]}'s close, {dlong(nc)}"
    if s.get("benchmark"):
        out.update(headline="Always in. Nothing in this rule ever sells.", short="Always in", check="No check needed")
        return out
    st = res["state"]
    if st is None:
        out.update(headline="Not enough price history yet for this play to make a call.", short="Not enough history")
        return out
    kind = trig.get("kind")
    if kind == "date":
        d = trig.get("date")
        if d is None:
            out.update(headline="No calendar change in the next year.", short="–")
            return out
        verb = "buys" if trig["to"] == 1 else "sells"
        out.update(headline=f"Stays {'in' if st == 1 else 'out'} until the close on {dlong(d)}, when the calendar says it {verb}. No price can change that.",
                   short=f"{'Buys' if trig['to'] == 1 else 'Sells'} {dshort(d)}", check=f"Next change: the {dlong(d)} close",
                   date=d)
        out["dist_days"] = (pd.Timestamp(d) - res["asof"]).days
        return out
    if kind == "window":
        d, which = trig["date"], trig["which"]
        if which == "buy":
            out.update(headline=f"Stays out until the buy window opens on {dlong(d)}. From then it waits for a MACD buy signal.", short=f"Window opens {dshort(d)}")
        else:
            out.update(headline=f"Stays in until the sell window opens on {dlong(d)}. From then it waits for a MACD sell signal.", short=f"Window opens {dshort(d)}")
        out["dist_days"] = (pd.Timestamp(d) - res["asof"]).days
        return out
    segs = trig.get("segments") or []
    bc = BAR_CLOSE[bar]
    if not segs:
        lo, hi = trig.get("span", (None, None))
        rng = f", not even one as low as {money(lo, cur)} or as high as {money(hi, cur)}" if lo else ""
        out["headline"] = f"No single {bc[2:]} can flip this call{rng}. {WAIT.get(s['slug'], 'It needs a bigger move, or more time, than one close can deliver.')}"
        out["short"] = "Not on one close"
    else:
        def gap(seg):
            a, b = seg
            if a is not None and b is not None and a <= price <= b:
                return 0.0
            return min(abs(np.log(x / price)) for x in (a, b) if x is not None) if (a or b) else 9.0
        seg = min(segs, key=gap)
        a, b = seg
        exit_ = st == 1
        if a is None and b is None:
            out["headline"] = f"The next check flips it whatever the price: the rule will {'sell' if exit_ else 'buy'}."
            out["short"] = "Flips at next check"
        elif a is None:
            lvl = b
            out["headline"] = (f"Stays in unless {bc} lands below {money(b, cur)}." if exit_ else f"Buys on {bc} below {money(b, cur)}.")
            out["short"] = f"{'Exit' if exit_ else 'Buy'} below {money(b, cur)}"
            out["level"] = lvl
        elif b is None:
            lvl = a
            out["headline"] = (f"Sells on {bc} above {money(a, cur)}." if exit_ else f"Stays out until {bc} lands above {money(a, cur)}.")
            out["short"] = f"{'Sell' if exit_ else 'Enter'} above {money(a, cur)}"
            out["level"] = lvl
        else:
            lvl = a if abs(np.log(a / price)) < abs(np.log(b / price)) else b
            out["headline"] = f"{'Sells' if exit_ else 'Buys'} on {bc} between {money(a, cur)} and {money(b, cur)}."
            out["short"] = f"{'Sell' if exit_ else 'Buy'} {money(a, cur)}–{money(b, cur)}"
            out["level"] = lvl
        if out["level"] is not None:
            out["dist"] = out["level"] / price - 1
        for o in segs:
            if o is seg:
                continue
            oa, ob = o
            if oa is None and ob is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close below {money(ob, cur)}.")
            elif ob is None and oa is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close above {money(oa, cur)}.")
            elif oa is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close between {money(oa, cur)} and {money(ob, cur)}.")
        if s["slug"] == "stocks-on-the-move" and exit_ and any(o[1] is None for o in segs):
            out["notes"].append("A one-day jump of more than 15% also breaks this play's rules, which is why a big up day can trigger a sell.")
    now = trig.get("now")
    if bar != "D" and not res["bar_complete"] and now is not None and now != st:
        out["alert"] = (f"At the latest close ({money(price, cur)}) the rule would already {'sell' if st == 1 else 'buy'} "
                        f"if the {BAR_PERIOD[bar]} ended today.")
    zone = trig.get("extra", {}).get("zone")
    if s.get("band") and zone == "between":
        out["notes"].append("Price is inside the band, so the rule is holding its last call.")
    if s["slug"] == "trend-template" and st == 0 and out["level"] is not None:
        out["notes"].append("That is the lowest close that would pass every price condition at once.")
    return out


# --------------------------------------------------------------------------
# chart specs
# --------------------------------------------------------------------------
def _runs(pos):
    runs, start, prev = [], None, None
    vals = pos.values
    for i, v in enumerate(vals):
        v = None if (v is None or (isinstance(v, float) and math.isnan(v))) else int(v)
        if v != prev:
            if prev is not None:
                runs.append([start, i - 1, prev])
            start, prev = i, v
    if prev is not None:
        runs.append([start, len(vals) - 1, prev])
    return runs


def _days(idx):
    t0 = idx[0]
    return t0.strftime("%Y-%m-%d"), [int((d - t0).days) for d in idx]


def price_spec(res, s, t, with_rule=True):
    win = res["window"]["price"]
    t0, d = _days(win.index)
    yrs = "two" if not s.get("benchmark") else "three"
    spec = {"t0": t0, "d": d, "cur": t["cur"], "fmt": "price",
            "label": f"{t['short']} price, last {yrs} years", "series": [{"name": t["short"], "role": "price", "v": [sig(v) for v in win.values]}]}
    if with_rule and not s.get("benchmark"):
        for lab, ser, role in res["window"]["lines"]:
            spec["series"].append({"name": lab, "role": role, "v": [sig(v) for v in ser.values]})
        spec["runs"] = _runs(res["window"]["pos"])
        spec["label"] = f"{t['short']} price with the {s['name']} play, last two years"
    return spec


def panel_spec(res, s, t):
    pn = res["window"].get("panel")
    if not pn:
        return None
    win = res["window"]["price"]
    t0, d = _days(win.index)
    spec = {"t0": t0, "d": d, "cur": "", "fmt": "pct" if pn["fmt"] == "pct" else "num", "label": pn["label"],
            "series": [{"name": lab, "role": role, "v": [sig(v, 4) for v in ser.values]} for lab, ser, role in pn["series"]],
            "levels": pn["levels"], "runs": _runs(res["window"]["pos"]), "small": True}
    if pn.get("min") is not None:
        spec["ymin"] = pn["min"]
    if pn.get("max") is not None:
        spec["ymax"] = pn["max"]
    return spec


def equity_spec(res, s, t):
    eq = res["equity"]
    dates = pd.DatetimeIndex(eq["dates"])
    step = max(1, len(dates) // 320)
    keep = list(range(0, len(dates), step))
    if keep and keep[-1] != len(dates) - 1:
        keep.append(len(dates) - 1)
    idx = dates[keep]
    t0, d = _days(idx)
    return {"t0": t0, "d": d, "cur": t["cur"], "fmt": "money", "log": True, "label": f"Growth of 10,000 in {t['short']}",
            "series": [{"name": s["name"], "role": "s1", "v": [sig(eq["strat"][i] * 10000, 4) for i in keep]},
                       {"name": "Buy & hold", "role": "bench", "v": [sig(eq["bh"][i] * 10000, 4) for i in keep]}]}


def chart_block(cid, spec, keys_html, title, note=None, small=False):
    data = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class="card chart-card"><div class="chart-top"><h3 class="h3">{title}</h3>'
            f'<div class="legend-row">{keys_html}</div></div>'
            f'<div class="chart{" chart-sm" if small else ""}" data-chart="{cid}" aria-label="{e(spec.get("label", title))}"></div>'
            f'<script type="application/json" id="{cid}">{data}</script>'
            + (f'<p class="chart-note">{note}</p>' if note else "") + "</div>")


def key_line(color_var, label):
    return f'<span class="key"><i style="background:var({color_var})"></i>{e(label)}</span>'


def key_wash(kind, label):
    bg = "var(--in-wash)" if kind == "in" else "var(--out-wash)"
    edge = "var(--in-edge)" if kind == "in" else "var(--out-edge)"
    return f'<span class="key"><s style="background:{bg};box-shadow:inset 0 0 0 1px {edge}"></s>{e(label)}</span>'


# --------------------------------------------------------------------------
# site
# --------------------------------------------------------------------------
class Site:
    def __init__(self, results, preview=False, built=None, prices=None, irx=None, meta=None):
        self.R = results
        self.meta = meta or {}
        self.universe = universe()
        self.macro = None
        from .risk import load_fundamentals
        self.fund = load_fundamentals(TICKERS)
        self.preview = preview
        self.built = built
        self.prices = prices
        self.irx = irx
        self.asof = max(r["asof"] for r in results.values())
        self.pages = {}   # path -> html
        self.ver = self.asof.strftime("%Y%m%d")
        self._sum = {}
        from .learn import Learn
        self.learn = Learn(self)

    # ----- helpers -----
    def r(self, sym, slug):
        return self.R[(sym, slug)]

    def href(self, depth, target):
        path = target
        if self.preview and (target == "" or target.endswith("/")):
            path += "index.html"
        elif self.preview and "/#" in target:
            a, _, b = target.partition("#")
            if a.endswith("/"):
                path = a + "index.html#" + b
        return ("../" * depth + path) or "./"

    def pair_path(self, t, s):
        return f"stocks/{t['slug']}/{s['slug']}/"

    def shell(self, path, title, desc, body, active=None, charts=False, extra_head="", lesson=None, glossary=False, scripts=(), link=True):
        depth = path.count("/")
        if link:
            body = link_terms(body, self.learn.href_for(depth, "glossary" if glossary else lesson))
        h = lambda target: self.href(depth, target)
        cur_attr = ' aria-current="page"'
        nav = "".join(f'<a href="{h(p)}"{cur_attr if p == active else ""}>{lab}</a>' for p, lab in NAV)
        full_title = f"{title} · Quiplee" if path else title
        more = "".join(f'<script src="{h(sx)}?v={self.ver}" defer></script>\n' for sx in scripts)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:type" content="website">
<meta property="og:image" content="{BASE}og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b0f17">
<link rel="icon" type="image/svg+xml" href="{ICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{h('assets/site.css')}?v={self.ver}">
{extra_head}</head>
<body>
<header class="site-head"><div class="wrap head-row">
<a class="logo" href="{h('')}">quiplee<span class="logo-tick">▲</span></a>
<nav class="site-nav" aria-label="Main">{nav}</nav>
<span class="head-meta">Closes to {dshort(self.asof)}</span>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site-foot"><div class="wrap foot-row">
<p>Quiplee runs published trading rules on real prices and shows what each one says now. These are rule outputs, not financial advice, and Quiplee takes no positions in the names it covers.</p>
<p>Closes through {dlong(self.asof)} · Prices from Yahoo Finance, macro data from FRED and multpl · Rebuilt after each U.S. close · <a href="{h('method/')}">How we test</a> · <a href="{h('articles/')}">Articles and stories</a></p>
</div></footer>
<script src="{h('assets/site.js')}?v={self.ver}" defer></script>
<script src="{h('assets/sortable.js')}?v={self.ver}" defer></script>
<script src="{h('assets/glossary.js')}?v={self.ver}" defer></script>
{more}</body>
</html>
"""

    def add(self, path, html_):
        self.pages[path] = html_

    # ----- aggregates -----
    def strat_summary(self, s):
        if s["slug"] in self._sum:
            return self._sum[s["slug"]]
        rows = [self.r(t["sym"], s["slug"]) for t in universe()]
        n = len(rows)
        full = [(x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}) for x in rows]
        ok = [(a, b) for a, b in full if a and b]
        right = sum(x["batting"]["right"] for x in rows)
        calls = sum(x["batting"]["n"] for x in rows)
        sw = [x["stats"]["switches_per_year"] for x in rows if x["stats"]["start"] is not None]
        out = {
            "n": n, "graded": len(ok),
            "in_now": sum(1 for x in rows if x["state"] == 1),
            "beat_sharpe": sum(1 for a, b in ok if a["sharpe"] is not None and b["sharpe"] is not None and a["sharpe"] > b["sharpe"]),
            "beat_cagr": sum(1 for a, b in ok if a["cagr"] > b["cagr"]),
            "cut_dd": sum(1 for a, b in ok if a["maxdd"] > b["maxdd"]),
            "bat": right / calls if calls else None, "calls": calls,
            "switches": float(np.median(sw)) if sw else None,
            "med_cagr_gap": float(np.median([a["cagr"] - b["cagr"] for a, b in ok])) if ok else None,
            "med_dd_gap": float(np.median([a["maxdd"] - b["maxdd"] for a, b in ok])) if ok else None,
        }
        self._sum[s["slug"]] = out
        return out

    def consensus(self, t, plays=None):
        states = [self.r(t["sym"], s["slug"])["state"] for s in (plays or TIMED)]
        return sum(1 for x in states if x == 1), sum(1 for x in states if x is not None)

    def meter(self, k, n):
        return count_in(k, n)

    def play_options(self, selected=None, value=None):
        out = ""
        for fk, fname, _ in FAMILIES:
            opts = "".join(f'<option value="{e(value(p) if value else p["slug"])}"{" selected" if p["slug"] == selected else ""}>{e(p["name"])} · {e(credit(p))}</option>'
                           for p in TIMED if p["family"] == fk)
            out += f'<optgroup label="{e(fname)}">{opts}</optgroup>'
        return out

    def stock_options(self, selected=None, value=None):
        out = ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
            out += f'<optgroup label="{e(g)}">' + "".join(
                f'<option value="{e(value(t) if value else t["slug"])}"{" selected" if t["sym"] == selected else ""}>{e(t["short"])} · {e(t["name"])}</option>'
                for t in universe() if t["group"] == g) + "</optgroup>"
        return out

    # ======================================================================
    # pages
    # ======================================================================
    def build(self):
        from .markets import markets_page
        from .watchlist import watchlist_page
        markets_page(self)
        watchlist_page(self)
        from .articles import Articles
        Articles(self).build()
        self.home()
        self.strategies_index()
        for s in PLAYS:
            self.strategy_page(s)
        self.thinkers_index()
        for th in THINKERS:
            self.thinker_page(th)
        self.stocks_index()
        for t in TICKERS:
            self.stock_page(t)
        for s in TIMED:            # warm the per-play summaries before forking
            self.strat_summary(s)
        self.render_pairs()
        self.learn.build()
        self.method_page()
        return self.pages

    # ---------------------------------------------------------------- home
    def home(self):
        path, depth = "", 0
        h = lambda x: self.href(depth, x)
        timed_pairs = [(t, s, self.r(t["sym"], s["slug"])) for t in universe() for s in TIMED]
        graded = [(a, b) for _, _, x in timed_pairs for a, b in [(x["stats"]["full"]["strat"], x["stats"]["full"]["bh"])] if a and b]
        total = len(graded)
        dd = sum(1 for a, b in graded if a["maxdd"] > b["maxdd"])
        cg = sum(1 for a, b in graded if a["cagr"] > b["cagr"])
        sh = sum(1 for a, b in graded if (a["sharpe"] or -9) > (b["sharpe"] or -9))

        tmpl = self.href(depth, "stocks/{t}/{s}/")
        fams = [(k, name, [p for p in TIMED if p["family"] == k]) for k, name, _ in FAMILIES]

        # board: stocks x families
        head = "".join(f'<th class="c" scope="col"><a href="{h("strategies/")}#fam-{k}">{e(name)}</a><span class="sym-sub">{len(ps)} plays</span></th>' for k, name, ps in fams)
        rows = ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
            rows += f'<tr class="grp"><td class="stick">{e(g)}</td><td colspan="{len(fams) + 1}"></td></tr>'
            for t in [x for x in universe() if x["group"] == g]:
                cells = ""
                for k, name, ps in fams:
                    kk, nn = self.consensus(t, ps)
                    cells += (f'<td class="c fam-cell" data-v="{sortv(kk / nn if nn else None)}"><a href="{h("stocks/" + t["slug"] + "/")}#fam-{k}" title="{e(name)} on {e(t["short"])}: {kk} of {nn} in">'
                              f'{fill_bar(kk, nn)}<span>{kk}/{nn}</span></a></td>')
                k_, n_ = self.consensus(t)
                rows += (f'<tr><td class="stick"><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a>'
                         f'<span class="sym-sub">{e(t["name"])}</span></td>{cells}<td class="r" data-v="{sortv(k_ / n_ if n_ else None)}">{count_in(k_, n_)}</td></tr>')

        # recent calls, spread across plays and stocks
        flips = []
        for t, s, x in timed_pairs:
            if x["calls"] and x["calls"][-1]["date"] >= self.asof - pd.Timedelta(days=21):
                c = x["calls"][-1]
                flips.append((c["date"], self.strat_summary(s)["switches"] or 99, t, s, c))
        flips.sort(key=lambda z: (z[0], -z[1]), reverse=True)
        per_s, per_t, pick = {}, {}, []
        for z in flips:
            _, _, t, s, c = z
            if per_s.get(s["slug"], 0) >= 1 or per_t.get(t["sym"], 0) >= 2:
                continue
            per_s[s["slug"]] = per_s.get(s["slug"], 0) + 1
            per_t[t["sym"]] = per_t.get(t["sym"], 0) + 1
            pick.append(z)
            if len(pick) >= 12:
                break
        flip_html = "".join(
            f'<li><a href="{h(self.pair_path(t, s))}"><span class="when">{dshort(d)}</span>{pill(c["state"])}'
            f'<span class="what"><b>{e(s["name"])} on {e(t["short"])}</b><span>{"Went in" if c["state"] == 1 else "Went out"} at {money(c["price"], t["cur"])} · {e(credit(s))}</span></span></a></li>'
            for d, _, t, s, c in pick) or '<li class="muted">No play changed its call in the last three weeks.</li>'

        featured = ["meb-faber", "richard-dennis-william-eckhardt", "j-welles-wilder", "stan-weinstein", "larry-connors", "gary-antonacci"]
        cards = "".join(self.thinker_card(THINKER[x], depth) for x in featured if x in THINKER)
        n_an = n_people()

        body = f"""
<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">Published trading rules, run on real prices every night</p>
    <h1 class="h1">See what the rules say about your stocks.</h1>
    <p class="lede">Quiplee runs {len(TIMED)} trading plays from {n_an} named analysts, from the Turtles' breakouts to Meb Faber's 10-month average, on {len(universe())} stocks, ETFs, indexes and coins. For each one you get which way the plays lean, the price that would change their mind, how exposed it is to a crash, and how the whole market looks.</p>
    <div class="hero-links"><a class="btn primary" href="{h('learn/')}">New? Start with the basics</a><a class="btn" href="{h('markets/')}">Read the market</a></div>
  </div>
  <div class="card picker">
    <form class="home-check" action="{h('watchlist/')}" method="get">
      <label for="home-add" class="h3">Check your stocks</label>
      <input id="home-add" name="add" type="text" placeholder="NVDA, SHOP.TO, Hertz…" autocomplete="off" spellcheck="false">
      <button type="submit">See the read</button>
      <p class="picker-out">Or upload a Wealthsimple or broker CSV on the <a href="{h('watchlist/')}">watchlist</a>. Names Quiplee doesn't cover yet are analysed after the next close.</p>
    </form>
    <form class="home-pick" id="picker" data-href="{e(tmpl)}">
      <p class="small muted">Or look up one play on one stock</p>
      <label for="pick-strategy">Play<select id="pick-strategy">{self.play_options("200-day-rule")}</select></label>
      <label for="pick-stock">Stock<select id="pick-stock">{self.stock_options("NVDA")}</select></label>
      <button type="submit" class="secondary">Show the call</button>
    </form>
  </div>
</section>
{self.home_market(depth)}
{self.home_signals(depth)}
<section aria-labelledby="reads-h"><div class="sec-head"><h2 class="h2" id="reads-h">Long reads</h2><p><a href="{h('articles/')}">All articles and stories</a></p></div>
<div class="grid grid-3">
  <a class="card art-card" href="{h('articles/is-this-a-bubble/')}"><span class="eyebrow">Macro</span><span class="name">Is this a bubble? The gauges in October 2026</span><span class="muted small">Valuations and concentration rival 2000; credit, jobs and volatility are calm; rates are the highest since 2007. What history says to make of it.</span></a>
  <a class="card art-card" href="{h('articles/bubbles-and-crashes/')}"><span class="eyebrow">Macro</span><span class="name">A century of bubbles and crashes</span><span class="muted small">From 1929 to 2022: what fell, how far, what set it off, and which warning signs had a real track record.</span></a>
  <a class="card art-card" href="{h('articles/cash-or-invested/')}"><span class="eyebrow">Macro</span><span class="name">Cash, stay invested, or buckets?</span><span class="muted small">What selling, holding, rebalancing and a trend rule did through 2008, 2020 and 2022.</span></a>
  <a class="card art-card" href="{h('articles/debt-and-crashes/')}"><span class="eyebrow">Stocks · live</span><span class="name">Debt decides who survives a crash</span><span class="muted small">The Hertz lens on every covered stock, ranked by balance sheet.</span></a>
  <a class="card art-card" href="{h('articles/green-across-the-board/')}"><span class="eyebrow">Stocks · live</span><span class="name">Green across the board</span><span class="muted small">The names most plays agree on: room to grow, the backdrop, and where the rules get out.</span></a>
  <a class="card art-card" href="{h('stories/the-hertz-lesson.html')}"><span class="eyebrow">Story</span><span class="name">The Hertz lesson</span><span class="muted small">Why a crash doesn't care about your revenue: the four pipes and the five-check scorecard.</span></a>
</div></section>
<section aria-labelledby="tracks-h"><div class="sec-head"><h2 class="h2" id="tracks-h">Learn it properly</h2><p>Three short tracks with hands-on widgets, real prices and quizzes.</p></div>
<div class="grid grid-3">
  <a class="card practice-card" href="{h('learn/')}#track-basics"><span class="eyebrow">Track 1</span><span class="name">Stock basics</span><span class="muted small">What a stock is, candlesticks, trends, P/E, balance sheets and position size.</span></a>
  <a class="card practice-card" href="{h('learn/')}#track-plays"><span class="eyebrow">Track 2</span><span class="name">The plays</span><span class="muted small">How the {len(TIMED)} published rules work, family by family, and how to read their record.</span></a>
  <a class="card practice-card" href="{h('learn/')}#track-markets"><span class="eyebrow">Track 3</span><span class="name">Markets and risk</span><span class="muted small">Indexes, bubbles and crashes, and cash versus staying invested.</span></a>
</div></section>

<section aria-labelledby="score-h">
  <div class="sec-head"><h2 class="h2" id="score-h">Does timing beat Bogle?</h2>
  <p>{total:,} play–stock pairs with enough history, each graded against simply buying and holding over the same dates, with trading costs and T-bill interest while out.</p></div>
  <div class="tiles">
    <div class="card tile"><span class="tile-label">Cut the worst drawdown</span><span class="tile-value">{dd:,} of {total:,}</span><span class="tile-note">Smaller peak-to-trough loss than buy and hold.</span></div>
    <div class="card tile"><span class="tile-label">Beat buy and hold on risk-adjusted return</span><span class="tile-value">{sh:,} of {total:,}</span><span class="tile-note">Higher Sharpe ratio over the full test.</span></div>
    <div class="card tile"><span class="tile-label">Beat buy and hold on raw return</span><span class="tile-value">{cg:,} of {total:,}</span><span class="tile-note">Higher annual growth. <a href="{h('thinkers/valeriy-zakamulin/')}">What the skeptic says</a></span></div>
  </div>
</section>

<section aria-labelledby="board-h">
  <div class="sec-head"><h2 class="h2" id="board-h">What the plays say now</h2>
  <p>How many plays in each family hold each stock, as of the {dlong(self.asof)} close. Click a column to sort; tap a cell for every call on that stock.</p></div>
  <div class="tbl-wrap"><table class="tbl board"><thead><tr><th class="stick" scope="col">Stock</th>{head}<th class="r" scope="col">All plays</th></tr></thead>
  <tbody>{rows}</tbody></table></div>
</section>

<section aria-labelledby="flips-h">
  <div class="sec-head"><h2 class="h2" id="flips-h">Fresh calls</h2><p>Recent changes of mind, one per play, slower plays first.</p></div>
  <ul class="flips">{flip_html}</ul>
</section>

<section aria-labelledby="thinkers-h">
  <div class="sec-head"><h2 class="h2" id="thinkers-h">Some of the analysts</h2>
  <p>Every play is tied to the person who published or popularised it, checked against their own books, papers and interviews. <a href="{h('thinkers/')}">All {n_an} analysts</a></p></div>
  <div class="grid grid-3">{cards}</div>
</section>

<section>
  <div class="card teaser">
    <div class="prose"><p class="eyebrow">Live desk</p><p class="h2" style="color:var(--ink)">News breaks. We tell you what it's worth.</p>
    <p>The original Quiplee desk scores every market story for revenue impact and grades each call against the next day's move.</p></div>
    <a class="btn primary" href="{h('desk/')}">Open the live desk</a>
  </div>
</section>
"""
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "@id": BASE + "#organization", "name": "Quiplee", "url": BASE, "logo": BASE + "og-default.png"},
            {"@type": "WebSite", "@id": BASE + "#website", "name": "Quiplee", "url": BASE, "inLanguage": "en", "publisher": {"@id": BASE + "#organization"}}]}
        extra = f'<script type="application/ld+json">{json.dumps(ld)}</script>\n'
        self.add(path, self.shell(path, "Quiplee · What the trading rules say about your stocks", f"{len(TIMED)} published trading plays from {n_an} analysts, run nightly on stocks, ETFs, indexes and crypto: which way they lean, the price that flips each one, crash exposure, market weather and a watchlist for your own stocks.", body, active="", extra_head=extra))

    def home_market(self, depth):
        M = self.macro
        if not M:
            return ""
        h = lambda x: self.href(depth, x)
        from .markets import fmt_val
        wcls = {"Calm": "calm", "Mostly calm": "calm", "Unsettled": "watch", "Stormy": "warning"}[M["weather"]]
        chips = "".join(f'<a class="gchip {g["status"]}" href="{h("markets/")}#g-{g["key"]}"><i></i><span>{e(g["name"])}</span><b>{fmt_val(g, g["value"])}</b></a>' for g in M["gauges"])
        core = [p for p in TIMED if p.get("core")]
        idx = ""
        for t in [x for x in TICKERS if x.get("index")]:
            kc, nc = self.consensus(t, core)
            y1 = self.one_year(t)
            idx += (f'<a class="card idx-card" href="{h("stocks/" + t["slug"] + "/")}"><span class="sym">{e(t["short"])}</span>'
                    f'<span class="px mono">{money(self.r(t["sym"], "buy-and-hold")["price"], "")}</span><span class="small {dir_cls(y1)}">{pct(y1, d=0)} in a year</span>'
                    f'{count_in(kc, nc, "core in")}</a>')
        return f"""<section aria-labelledby="mkt-h"><div class="sec-head"><h2 class="h2" id="mkt-h">Market weather: <span class="wx {wcls}">{e(M['weather'])}</span></h2>
<p>{M['counts']['warning']} of {len(M['gauges'])} crash gauges flash a warning. <a href="{h('markets/')}">Read the market</a> · <a href="{h('articles/is-this-a-bubble/')}">Is this a bubble?</a></p></div>
<div class="gchips">{chips}</div><div class="idx-row">{idx}</div></section>"""

    def home_signals(self, depth):
        h = lambda x: self.href(depth, x)
        cands = [t for t in self.universe if not t.get("index") and t["group"] != "Sectors"]

        def share(t):
            k, n = self.consensus(t)
            return k / n if n else 0
        top = sorted(cands, key=lambda t: (-share(t), t["short"]))[:6]
        eq = [t for t in cands if not t["crypto"] and t["group"] != "Indexes & ETFs" and (self.meta.get(t["sym"]) or {}).get("risk")]
        risky = sorted(eq, key=lambda t: (-self.meta[t["sym"]]["risk"]["score"], t["short"]))[:6]

        def card(t, extra):
            k, n = self.consensus(t)
            x = self.r(t["sym"], "buy-and-hold")
            return (f'<a class="card stock-card" href="{h("stocks/" + t["slug"] + "/")}"><div class="top"><span class="sym">{e(t["short"])}</span>'
                    f'<span class="px">{money(x["price"], t["cur"])}</span></div><span class="muted small">{e(t["name"])}</span>{count_in(k, n, "plays in")}{extra}</a>')
        g = "".join(card(t, "") for t in top)
        r = "".join(card(t, f'<span class="small lvl-{sv.LEVEL_CLASS[self.meta[t["sym"]]["risk"]["level"]]}">{e(self.meta[t["sym"]]["risk"]["level"])} crash exposure</span>') for t in risky)
        return f"""<section aria-labelledby="sig-h"><div class="sec-head"><h2 class="h2" id="sig-h">Strongest signals</h2>
<p>The names most plays agree on tonight. A broad uptrend, not a promise. <a href="{h('articles/green-across-the-board/')}">Room to grow, and where the rules get out</a></p></div>
<div class="grid grid-3">{g}</div>
<div class="sec-head"><h3 class="h3">Most exposed if the market cracks</h3><p>Highest crash exposure: market swings, past crashes, debt and run-up. <a href="{h('articles/debt-and-crashes/')}">The Hertz lens</a></p></div>
<div class="grid grid-3">{r}</div></section>"""

    def thinker_card(self, th, depth):
        h = lambda x: self.href(depth, x)
        if th.get("skeptic"):
            rec = '<div class="rec"><span><b>No play</b>audits the others</span></div>'
            strat = "The skeptic"
        elif th.get("benchmark"):
            rec = '<div class="rec"><span><b>Benchmark</b>every play is graded against this</span></div>'
            strat = "Buy & Hold"
        else:
            ss = [PLAY[x] for x in th["strategies"]]
            strat = " · ".join(p["name"] for p in ss)
            sms = [self.strat_summary(p) for p in ss]
            calls = sum(m["calls"] for m in sms)
            right = sum((m["bat"] or 0) * m["calls"] for m in sms)
            n = sum(m["n"] for m in sms)
            rec = (f'<div class="rec"><span><b>{pct(right / calls if calls else None, sign=False, d=0)}</b>calls right</span>'
                   f'<span><b>{sum(m["beat_sharpe"] for m in sms)} of {sum(m["graded"] for m in sms)}</b>beat buy &amp; hold (Sharpe)</span>'
                   f'<span><b>{sum(m["in_now"] for m in sms)} of {n}</b>in now</span></div>')
        return (f'<a class="card thinker-card" href="{h("thinkers/" + th["slug"] + "/")}"><span class="strat">{e(strat)}</span>'
                f'<span class="name">{e(th["name"])}</span><span class="role">{e(th["role"])}</span>{rec}</a>')

    # ------------------------------------------------------- plays
    def strategies_index(self):
        path, depth = "strategies/", 1
        h = lambda x: self.href(depth, x)
        chips = "".join(f'<a href="#fam-{k}">{e(name)} <span class="muted">{len([p for p in TIMED if p["family"] == k])}</span></a>' for k, name, _ in FAMILIES)
        secs = ""
        for k, name, desc in FAMILIES:
            rows = ""
            for s in [p for p in TIMED if p["family"] == k]:
                sm = self.strat_summary(s)
                rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}"><b>{e(s["name"])}</b></a>{flag_tag(s)}'
                         f'<span class="sym-sub">{e(credit(s))}</span></td>'
                         f'<td class="nowrap">{BAR_WORD[s["bar"]].capitalize()}</td>'
                         f'<td class="r" data-v="{sm["in_now"]}">{sm["in_now"]} of {sm["n"]}</td><td class="r">{pct(sm["bat"], sign=False, d=0)}</td>'
                         f'<td class="r" data-v="{sm["beat_sharpe"] / sm["graded"] if sm["graded"] else ""}">{sm["beat_sharpe"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["cut_dd"] / sm["graded"] if sm["graded"] else ""}">{sm["cut_dd"]} of {sm["graded"]}</td>'
                         f'<td class="r">{sm["switches"]:.1f}</td></tr>')
            secs += f"""<section id="fam-{k}" class="fam-sec"><div class="sec-head"><h2 class="h2">{e(name)}</h2><p>{e(desc)}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Checks</th><th class="r">In now</th><th class="r">Calls right</th><th class="r">Beat B&amp;H Sharpe</th><th class="r">Cut drawdown</th><th class="r">Switches / yr</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>"""
        bh = PLAY["buy-and-hold"]
        body = f"""
<section class="pair-head"><p class="eyebrow">Plays</p><h1 class="h1">{len(TIMED)} plays, one scorecard</h1>
<p class="lede">Each play is written down exactly as Quiplee tests it, run on every stock in the universe, and graded against buying and holding the same stock over the same dates. They fall into six families.</p>
<div class="chips fam-chips">{chips}</div></section>
{secs}
<section class="card teaser"><div class="prose"><p class="eyebrow">The benchmark</p><p class="h3" style="color:var(--ink)">{e(bh['long'])}</p><p>{e(bh['short'])}</p></div>
<a class="btn" href="{h('strategies/buy-and-hold/')}">Buy and hold by stock</a></section>
<p class="muted small">Calls right: the share of closed calls where an in call was followed by a higher price, or an out call by a lower one. Trend plays often win well under half their calls and make it back on a few long trends. Switches per year is the median across stocks.</p>
"""
        self.add(path, self.shell(path, "Plays", f"All {len(TIMED)} trading plays Quiplee tests, grouped into six families, with who they come from and how they have scored.", body, active="strategies/"))

    def strategy_page(self, s):
        path, depth = f"strategies/{s['slug']}/", 2
        h = lambda x: self.href(depth, x)
        by = " &amp; ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in s["analysts"])
        rule_card = self.rule_card(s)
        if s.get("benchmark"):
            rows = ""
            for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
                rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
                for t in [x for x in universe() if x["group"] == g]:
                    b = self.r(t["sym"], s["slug"])["stats"]["full"]["bh"] or {}
                    rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td class="r {dir_cls(b.get("cagr"))}">{pct(b.get("cagr"))}</td><td class="r">{pct(b.get("maxdd"))}</td><td class="r">{ratio(b.get("sharpe"))}</td>'
                             f'<td class="r nowrap">{dlong(self.r(t["sym"], s["slug"])["stats"]["start"])}</td></tr>')
            body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Plays</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">The benchmark</p><h1 class="h1">{e(s['long'])}</h1><div class="byline"><span>Championed by {by}</span></div><p class="lede">{e(s['short'])}</p></section>
<section><h2 class="h2">Buy and hold, stock by stock</h2>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Since</th></tr></thead><tbody>{rows}</tbody></table></div></section>
"""
            self.add(path, self.shell(path, s["long"], s["short"], body, active="strategies/"))
            return

        sm = self.strat_summary(s)
        now_rows, rec_rows = "", ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
            now_rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
            rec_rows += f'<tr class="grp"><td colspan="6">{e(g)}</td></tr>'
            for t in [x for x in universe() if x["group"] == g]:
                x = self.r(t["sym"], s["slug"])
                nm = next_move(x, s, t)
                band = BAND_MARK if s.get("band") and x["trigger"].get("extra", {}).get("zone") == "between" else ""
                link = h(self.pair_path(t, s))
                dv = abs(nm["dist"]) if nm["dist"] is not None else (nm.get("dist_days", 0) / 365 if nm.get("dist_days") is not None else None)
                lvl = nm["short"] + (f' <span class="muted">({pct(nm["dist"])})</span>' if nm["dist"] is not None else "")
                now_rows += (f'<tr><td><a class="sym" href="{link}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td>{pill(x["state"])}{band}</td><td class="nowrap">{dlong(x["since"])}</td>'
                             f'<td class="nowrap" data-v="{sortv(dv)}">{lvl}</td><td class="nowrap muted">{dlong(x["next_check"])}</td></tr>')
                a, b = x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}
                bat = x["batting"]
                rec_rows += (f'<tr><td><a class="sym" href="{link}">{e(t["short"])}</a></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("cagr"))}">{pct(a.get("cagr"))} <span class="muted">/ {pct(b.get("cagr"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("maxdd"))}">{pct(a.get("maxdd"))} <span class="muted">/ {pct(b.get("maxdd"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("sharpe"))}">{ratio(a.get("sharpe"))} <span class="muted">/ {ratio(b.get("sharpe"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(bat["avg"])}">{pct(bat["avg"], sign=False, d=0)} <span class="muted">of {bat["n"]}</span></td>'
                             f'<td class="r">{x["stats"]["switches_per_year"]:.1f}</td></tr>')
        fam = FAMILY[s["family"]][0]
        body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Plays</a><span>/</span><a href="{h('strategies/')}#fam-{s['family']}">{e(fam)}</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head">
  <p class="eyebrow">{e(fam)} · {e(BAR_WORD[s['bar']])} rule{" · " + e(s['flag']) if s.get('flag') else ""}</p>
  <h1 class="h1">{e(s['long'])}</h1>
  <div class="byline"><span>From {by}</span>{"<span>·</span><span>" + e(s["origin"]) + "</span>" if s.get("origin") else ""}</div>
  <p class="lede">{e(s['short'])}</p>
</section>
<section><div class="tiles">
  <div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
  <div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">Across {sm['calls']:,} closed calls.</span></div>
  <div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['graded']}</span><span class="tile-note">Cut the worst drawdown on {sm['cut_dd']} of {sm['graded']}.</span></div>
</div></section>
<section class="split">{rule_card}{self.against_card(depth)}</section>
<section class="card practice-strip"><p><b>Practise this play.</b> See if you can read its call on real charts, or drill its rule on a flashcard.</p>
<div class="chips"><a href="{h('learn/call-it/')}?play={s['slug']}">Call it: {e(s['name'])}</a><a href="{h('learn/flashcards/')}?deck=plays#{s['slug']}">Flashcard</a></div></section>
<section><div class="sec-head"><h2 class="h2">What it says now</h2><p>The close that would flip each call on its next {BAR_WORD[s['bar']]} check.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th>Next check</th></tr></thead><tbody>{now_rows}</tbody></table></div></section>
<section><div class="sec-head"><h2 class="h2">The record</h2><p>Play / buy and hold over the same dates, since 2005 or the first date with enough history.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Calls right</th><th class="r">Switches / yr</th></tr></thead><tbody>{rec_rows}</tbody></table></div></section>
"""
        self.add(path, self.shell(path, s["long"], f"{s['long']} from {credit(s)}: {s['short']} Current calls and full record on {len(universe())} stocks.", body, active="strategies/"))

    def rule_card(self, s):
        rules = "".join(f"<li>{e(x)}</li>" for x in s["rules"])
        ass = "".join(f"<p>{e(x)}</p>" for x in s["assumptions"])
        return (f'<div class="card rule-card prose"><p class="eyebrow">How the play works</p><ol>{rules}</ol>'
                + (f'<div class="assume">{ass}</div>' if ass else "") + "</div>")

    def against_card(self, depth):
        h = lambda x: self.href(depth, x)
        return (f'<div class="card prose"><p class="eyebrow">The case against</p><div class="against">'
                f'<p>Valeriy Zakamulin tested moving-average timing on up to 155 years of U.S. stock data and found no statistically significant edge in the second half of that record. The rules earned their keep in a few severe bear markets and lagged buy and hold for long stretches in between.</p>'
                f'<p><a href="{h("thinkers/valeriy-zakamulin/")}">Read the skeptic\'s scoreboard</a></p></div></div>')

    # ---------------------------------------------------------- analysts
    def analyst_family(self, th):
        if not th["strategies"]:
            return None
        return PLAY[th["strategies"][0]]["family"]

    def thinkers_index(self):
        path, depth = "thinkers/", 1
        h = lambda x: self.href(depth, x)
        secs = ""
        chips = ""
        for k, name, desc in FAMILIES:
            group = [th for th in THINKERS if self.analyst_family(th) == k]
            if not group:
                continue
            chips += f'<a href="#fam-{k}">{e(name)} <span class="muted">{len(group)}</span></a>'
            cards = "".join(self.thinker_card(th, depth) for th in group)
            secs += f'<section id="fam-{k}" class="fam-sec"><div class="sec-head"><h2 class="h2">{e(name)}</h2><p>{e(desc)}</p></div><div class="grid grid-3">{cards}</div></section>'
        extra = "".join(self.thinker_card(th, depth) for th in THINKERS if th.get("benchmark") or th.get("skeptic"))
        n_an = n_people()
        body = f"""
<section class="pair-head"><p class="eyebrow">Analysts</p><h1 class="h1">The people behind the plays</h1>
<p class="lede">{n_an} traders, authors and researchers, from Richard Donchian's 1950s rules to Ben Cowen's crypto band, plus the golden cross, which has no single author. Each bio and rule was checked against their books, papers or interviews, and every play is graded the same way, whoever published it.</p>
<div class="chips fam-chips">{chips}<a href="#yardsticks">Benchmark &amp; skeptic</a><a href="{h('learn/reading-list/')}">Reading list</a></div></section>
{secs}
<section id="yardsticks" class="fam-sec"><div class="sec-head"><h2 class="h2">The yardsticks</h2><p>The benchmark every play is graded against, and the researcher who says timing rarely beats it.</p></div><div class="grid grid-3">{extra}</div></section>
"""
        self.add(path, self.shell(path, "Analysts", f"The {n_an} traders, analysts and academics behind every play Quiplee tests, with verified bios, books and sources.", body, active="thinkers/"))

    def thinker_page(self, th):
        path, depth = f"thinkers/{th['slug']}/", 2
        h = lambda x: self.href(depth, x)
        argues = "".join(f"<li>{e(x)}</li>" for x in th["argues"])
        srcs = "".join(f'<a href="{e(u)}" rel="noopener" target="_blank">{e(lab)}</a>' for lab, u in th["sources"])
        books = "".join(f'<li><b>{e(b["title"])}</b>{" <span class=muted>(" + str(b["year"]) + ")</span>" if b.get("year") else ""}</li>' for b in th.get("books", []))
        books_card = (f'<div class="card prose"><p class="eyebrow">Books and papers</p><ul class="books">{books}</ul>'
                      f'<p class="muted small"><a href="{h("learn/reading-list/")}">The full reading list</a></p></div>') if books else ""
        extra = ""
        if th.get("skeptic"):
            rows = ""
            for s in TIMED:
                sm = self.strat_summary(s)
                rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}">{e(s["name"])}</a><span class="sym-sub">{e(credit(s))}</span></td>'
                         f'<td>{e(FAMILY[s["family"]][0])}</td>'
                         f'<td class="r" data-v="{sm["beat_cagr"] / max(1, sm["graded"])}">{sm["beat_cagr"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["beat_sharpe"] / max(1, sm["graded"])}">{sm["beat_sharpe"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["cut_dd"] / max(1, sm["graded"])}">{sm["cut_dd"]} of {sm["graded"]}</td></tr>')
            extra = f"""<section><div class="sec-head"><h2 class="h2">The skeptic's scoreboard</h2><p>How often each play beat simply holding the stock, over the same dates, after costs. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Family</th><th class="r">Beat on return</th><th class="r">Beat on Sharpe</th><th class="r">Cut drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted small">A play that cuts drawdowns but loses on return is doing what Zakamulin's research predicts: paying for crash protection with years of lag.</p></section>"""
        else:
            for slug in th["strategies"]:
                s = PLAY[slug]
                if s.get("benchmark"):
                    extra += f"""<section><div class="card teaser"><div class="prose"><p class="eyebrow">The benchmark</p><p class="h2" style="color:var(--ink)">Every play on Quiplee is graded against buy and hold.</p></div>
<a class="btn" href="{h('strategies/' + slug + '/')}">See buy and hold by stock</a></div></section>"""
                    continue
                sm = self.strat_summary(s)
                score = lambda t: ((self.r(t["sym"], slug)["stats"]["full"]["strat"] or {}).get("sharpe") or -9) - ((self.r(t["sym"], slug)["stats"]["full"]["bh"] or {}).get("sharpe") or -9)
                best = sorted(universe(), key=score, reverse=True)[:12]
                chips = "".join(f'<a href="{h(self.pair_path(t, s))}">{e(t["short"])}{pill(self.r(t["sym"], slug)["state"])}</a>' for t in best)
                co = [a for a in s["analysts"] if a != th["slug"]]
                with_ = (" · with " + ", ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in co)) if co else ""
                extra += f"""<section><div class="sec-head"><h2 class="h2">{e(s['long'])}</h2><a class="btn" href="{h('strategies/' + slug + '/')}">Rule and full record</a></div>
<p class="muted small">{e(FAMILY[s['family']][0])} · {e(BAR_WORD[s['bar']])}{with_}</p>
<p>{e(s['short'])}</p>
<div class="tiles">
<div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">{sm['calls']:,} closed calls on {sm['n']} stocks.</span></div>
<div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['graded']}</span><span class="tile-note">On raw return: {sm['beat_cagr']} of {sm['graded']}.</span></div>
<div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
</div>
<p class="muted small">Best risk-adjusted results against buy and hold:</p><div class="chips">{chips}<a href="{h('strategies/' + slug + '/')}">All {len(universe())} stocks →</a></div></section>"""
        body = f"""
<nav class="crumbs"><a href="{h('thinkers/')}">Analysts</a><span>/</span><span>{e(th['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(th['role'])}</p><h1 class="h1">{e(th['name'])}</h1><p class="lede">{e(th['bio'])}</p></section>
<section class="split"><div class="card prose"><p class="eyebrow">What they argue</p><ul>{argues}</ul></div>
<div class="card prose"><p class="eyebrow">Sources</p><div class="sources">{srcs}</div>
<p class="muted small">Summaries are Quiplee's paraphrase of public material. Quiplee has no affiliation with the people listed.</p></div></section>
{f'<section class="split">{books_card}</section>' if books_card else ''}
{extra}
"""
        n_plays = len([x for x in th["strategies"] if not PLAY[x].get("benchmark")])
        desc = f"{th['name']}, {th['role']}: " + (f"{n_plays} play{'s' if n_plays != 1 else ''} tested on {len(universe())} stocks, and what they say now." if n_plays else "background, sources and books.")
        self.add(path, self.shell(path, th["name"], desc, body, active="thinkers/"))

    # ------------------------------------------------------------ stocks
    def one_year(self, t):
        x = self.r(t["sym"], "buy-and-hold")
        w = x["window"]["price"]
        past = w[w.index <= x["asof"] - pd.DateOffset(years=1)]
        return (x["price"] / float(past.iloc[-1]) - 1) if len(past) else None

    def stocks_index(self):
        path, depth = "stocks/", 1
        h = lambda x: self.href(depth, x)
        secs = ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in TICKERS)]:
            cards = ""
            for t in [x for x in TICKERS if x["group"] == g]:
                k, n = self.consensus(t)
                x = self.r(t["sym"], "buy-and-hold")
                y1 = self.one_year(t)
                cards += (f'<a class="card stock-card" href="{h("stocks/" + t["slug"] + "/")}"><div class="top"><span class="sym">{e(t["short"])}</span>'
                          f'<span class="px">{money(x["price"], t["cur"])}</span></div><span class="muted small">{e(t["name"])} · 1 yr <span class="{dir_cls(y1)}">{pct(y1)}</span></span>'
                          f'{count_in(k, n, "plays in")}</a>')
            note = ('<p class="muted small">Added by readers through the <a href="' + h("watchlist/") + '">watchlist</a>. Every play runs on them each night.</p>') if g == "Reader-requested" else ""
            secs += f'<section><h2 class="h2">{e(g)}</h2>{note}<div class="grid grid-4">{cards}</div></section>'
        body = f"""
<section class="pair-head"><p class="eyebrow">Stocks</p><h1 class="h1">{len(TICKERS)} stocks, ETFs and coins</h1>
<p class="lede">Open any name to see all {len(TIMED)} plays' calls on it, the level that flips each one, and how each has done on it since 2005.</p></section>
{secs}"""
        self.add(path, self.shell(path, "Stocks", f"Every stock, ETF and coin Quiplee covers, with how many of {len(TIMED)} plays hold it right now.", body, active="stocks/"))

    def stock_page(self, t):
        path, depth = f"stocks/{t['slug']}/", 2
        h = lambda x: self.href(depth, x)
        sym = t["sym"]
        bh = self.r(sym, "buy-and-hold")
        meta = self.meta.get(sym) or {}
        fund = self.fund.get(sym)
        rk = meta.get("risk")
        core = [p for p in TIMED if p.get("core")]
        k, n = self.consensus(t)
        kc, nc = self.consensus(t, core)
        own_pages = {p["slug"] for p in plays_for(t)}
        tiles, rows = "", ""
        for fk, fname, _ in FAMILIES:
            ps = [p for p in TIMED if p["family"] == fk]
            kk, nn = self.consensus(t, ps)
            tiles += (f'<a class="card fam-tile" href="#fam-{fk}"><span class="tile-label">{e(fname)}</span>'
                      f'<span class="fam-n"><b>{kk}</b> of {nn} in</span>{fill_bar(kk, nn)}</a>')
            has_core = any(p.get("core") for p in ps)
            rows += f'<tr class="grp{"" if has_core else " nc"}" id="fam-{fk}"><td colspan="6">{e(fname)}</td></tr>'
            for s in ps:
                x = self.r(sym, s["slug"])
                nm = next_move(x, s, t)
                since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
                dv = abs(nm["dist"]) if nm["dist"] is not None else (nm.get("dist_days", 0) / 365 if nm.get("dist_days") is not None else None)
                nxt = nm["short"] + (f' <span class="muted">({pct(nm["dist"])})</span>' if nm["dist"] is not None else "")
                a, b = x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}
                band = BAND_MARK if s.get("band") and x["trigger"].get("extra", {}).get("zone") == "between" else ""
                name = (f'<a href="{h(self.pair_path(t, s))}"><b>{e(s["name"])}</b></a>' if s["slug"] in own_pages else f'<b>{e(s["name"])}</b>')
                core_tag = ' <span class="core-tag" title="One of the 20 core plays">core</span>' if s.get("core") else ""
                rows += (f'<tr class="{"" if s.get("core") else "nc"}"><td>{name}{core_tag}<span class="sym-sub">{e(credit(s))} · {BAR_WORD[s["bar"]]}</span></td>'
                         f'<td>{pill(x["state"])}{band}</td><td class="nowrap" data-v="{pd.Timestamp(x["since"]).strftime("%Y-%m-%d") if x["since"] is not None else ""}">{dlong(x["since"])} <span class="{dir_cls(since_move)}">{pct(since_move)}</span></td>'
                         f'<td class="nowrap" data-v="{sortv(dv)}">{nxt}</td><td class="r nowrap" data-v="{sortv(a.get("cagr"))}">{pct(a.get("cagr"))} <span class="muted">/ {pct(b.get("cagr"))}</span></td>'
                         f'<td class="r nowrap" data-v="{sortv(a.get("maxdd"))}">{pct(a.get("maxdd"))} <span class="muted">/ {pct(b.get("maxdd"))}</span></td></tr>')
        b = bh["stats"]["full"]["bh"] or {}
        rows += (f'<tr class="grp"><td colspan="6">Benchmark</td></tr><tr><td><a href="{h("strategies/buy-and-hold/")}"><b>Buy &amp; Hold</b></a><span class="sym-sub">John C. Bogle · benchmark</span></td>'
                 f'<td>{pill(1)}</td><td class="nowrap">{dlong(bh["stats"]["start"])}</td><td class="muted">Always in</td>'
                 f'<td class="r">{pct(b.get("cagr"))}</td><td class="r">{pct(b.get("maxdd"))}</td></tr>')
        others = self.stock_options(t["sym"])
        start_y = bh['stats']['start'].year if bh['stats']['start'] is not None else ""

        # price facts
        day_ch = None
        if meta.get("ohlc") is not None and len(meta["ohlc"]) > 1:
            cc = meta["ohlc"]["close"]
            day_ch = float(cc.iloc[-1] / cc.iloc[-2] - 1)
        y1 = self.one_year(t)
        if meta.get("ohlc") is not None and len(meta["ohlc"]):
            chart = sv.candles_block(t, meta, learn=h("learn/candlesticks/"))
            heat = sv.heatmap_block(self, t, meta, lambda p: h(self.pair_path(t, p)) if p["slug"] in own_pages else None)
        else:
            chart = chart_block("px-" + t["slug"], price_spec(bh, PLAY["buy-and-hold"], t, with_rule=False), "", f"{e(t['short'])} over the last three years")
            heat = ""
        read = sv.read_lines(self, t, meta, fund) if meta else []
        read_html = "".join(f"<li>{e(x)}</li>" for x in read)
        lvl = rk["level"] if rk else None
        trend_tile = ""
        if meta.get("ohlc") is not None and len(meta["ohlc"]) >= 200:
            cc = meta["ohlc"]["close"]
            gap = float(cc.iloc[-1] / cc.iloc[-200:].mean() - 1)
            trend_tile = (f'<div class="card tile"><span class="tile-label">Against its 200-day average</span><span class="tile-value {dir_cls(gap)}">{pct(gap, d=0)}</span>'
                          f'<span class="tile-note">{"Above: the long trend is up." if gap >= 0 else "Below: the long trend is down."}</span></div>')
        crash_tile = (f'<a class="card tile tile-link" href="#crash"><span class="tile-label">Crash exposure</span><span class="tile-value lvl-{sv.LEVEL_CLASS[lvl]}">{e(lvl)}</span>'
                      f'<span class="tile-note">{rk["score"]} of 10 on the Hertz checklist</span></a>') if lvl else ""
        summary = f"""<section class="sum-tiles">
<div class="card tile"><span class="tile-label">Core plays in</span><span class="tile-value">{kc}<small> / {nc}</small></span>{fill_bar(kc, nc)}<span class="tile-note">The 20 most-followed plays.</span></div>
<div class="card tile"><span class="tile-label">All plays in</span><span class="tile-value">{k}<small> / {n}</small></span>{fill_bar(k, n)}<span class="tile-note">Every play Quiplee tests.</span></div>
{crash_tile}{trend_tile}
</section>"""
        req_note = ""
        if t.get("requested"):
            req_note = (f'<p class="note-line">Added by a reader{(" on " + dlong(t["since"])) if t.get("since") else ""}. Quiplee runs every play on it each night; '
                        f'the 20 core plays get a full page each.</p>')
        idx_note = ""
        if t.get("index"):
            idx_note = ('<p class="note-line">An index is a scoreboard, not something you can buy directly. Investors hold it through an index fund or ETF, '
                        'which tracks it closely. The plays read the index itself.</p>')
        fund_html = sv.fundamentals_card(t, fund, bh["price"], learn=h("learn/valuation/"))
        crash_html = sv.crash_card(t, rk, h) if rk else ""
        deep = ""
        if fund_html or crash_html:
            deep = f'<section class="deep" id="crash">{crash_html}{fund_html}</section>'
        exposed = self.index_exposed(t, depth) if t.get("index") else ""
        arts = self.articles_for(t, depth)
        watch_btn = (f'<button type="button" class="btn sm" data-watch-add="{e(sym)}" data-watch-href="{e(h("watchlist/"))}">+ Add to my watchlist</button>')
        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><span>{e(t['short'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(t['group'])}</p><h1 class="h1">{e(t['name'])} <span class="muted">({e(t['short'])})</span></h1>
<div class="byline"><span class="mono" style="color:var(--ink);font-size:18px">{money(bh['price'], t['cur'])}</span>
<span class="{dir_cls(day_ch)}">{pct(day_ch)} on the day</span><span>·</span><span class="{dir_cls(y1)}">{pct(y1)} in a year</span><span>·</span><span>close {dlong(bh['asof'])}</span></div>
{idx_note}{req_note}</section>
<section class="card read-card"><div class="read-top"><p class="eyebrow">The read</p>{watch_btn}</div><ul class="read">{read_html}</ul>
<p class="muted small">What published rules and the numbers say, not a recommendation. <a href="{h('learn/')}">New to this? Start with the basics.</a></p></section>
{summary}
{chart}
{heat}
<section><div class="sec-head"><h2 class="h2">Every play on {e(t['short'])}</h2>
<div class="seg seg-sm" role="group" aria-label="Which plays" data-coretoggle="plays-tbl"><button type="button" aria-pressed="true" data-v="core">Core 20</button><button type="button" aria-pressed="false" data-v="all">All {len(TIMED)}</button></div></div>
<div class="fam-tiles">{tiles}</div>
<p class="muted small">Record columns: play / buy and hold, annual return and worst drawdown since {start_y}. Click a column to sort.</p>
<div class="tbl-wrap core-only" id="plays-tbl"><table class="tbl"><thead><tr><th>Play</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th class="r">Annual return</th><th class="r">Worst drawdown</th></tr></thead><tbody>{rows}</tbody></table></div></section>
{deep}
{exposed}
{arts}
<section class="jump"><label class="small muted" for="jump-stock">Another stock</label><select id="jump-stock" data-nav data-tmpl="{e(h('stocks/{v}/'))}">{others}</select></section>
"""
        self.add(path, self.shell(path, f"{t['name']} ({t['short']}) · plays, chart and crash exposure", f"What {len(TIMED)} published trading plays say about {t['name']} ({t['short']}) now, the exact levels that flip them, its candlestick chart, fundamentals and crash exposure.", body, active="stocks/", scripts=("assets/widgets.js",)))

    def articles_for(self, t, depth):
        h = lambda x: self.href(depth, x)
        links = [(f"articles/stocks/{t['slug']}/", f"{t['short']}: the brief", "What the plays, the levels and the business say, in plain English. Rebuilt nightly.")]
        eq = [x for x in self.universe if x["group"] == t["group"] and not x.get("index") and not x["crypto"] and x["group"] not in ("Indexes & ETFs", "Sectors")]
        if len(eq) >= 3 and t in eq:
            from .articles import slugify
            links.append((f"articles/sectors/{slugify(t['group'])}/", f"{t['group']}: what the plays say", "Every covered name in the sector, side by side."))
        links.append(("articles/debt-and-crashes/", "Debt decides who survives a crash", "The Hertz lens on every covered stock."))
        links.append(("articles/is-this-a-bubble/", "Is this a bubble?", "The gauges in October 2026, and what history says about timing."))
        cards = "".join(f'<a class="card art-card" href="{h(u)}"><span class="name">{e(a)}</span><span class="muted small">{e(b)}</span></a>' for u, a, b in links)
        return f'<section><div class="sec-head"><h2 class="h2">Read more</h2></div><div class="grid grid-4">{cards}</div></section>'

    def index_exposed(self, t, depth):
        """On an index page: the covered names that trade on that market, by crash exposure."""
        h = lambda x: self.href(depth, x)
        canada = t["sym"] == "^GSPTSE"
        names = [x for x in universe() if not x.get("index") and not x["crypto"] and x["group"] not in ("Indexes & ETFs", "Sectors")
                 and x["canadian"] == canada and self.meta.get(x["sym"], {}).get("risk")]
        if not names:
            return ""
        names.sort(key=lambda x: (-self.meta[x["sym"]]["risk"]["score"], x["short"]))
        rows = ""
        for x in names:
            rk = self.meta[x["sym"]]["risk"]
            kc, nc = self.consensus(x, [p for p in TIMED if p.get("core")])
            rows += (f'<tr><td><a class="sym" href="{h("stocks/" + x["slug"] + "/")}">{e(x["short"])}</a><span class="sym-sub">{e(x["name"])}</span></td>'
                     f'<td data-v="{rk["score"]}"><span class="lvl lvl-{sv.LEVEL_CLASS[rk["level"]]}">{e(rk["level"])}</span> <span class="muted">{rk["score"]}/10</span></td>'
                     f'<td class="r" data-v="{sortv(rk.get("beta"))}">{ratio(rk.get("beta"))}</td>'
                     f'<td class="r" data-v="{sortv(rk.get("runup2y"))}">{pct(rk.get("runup2y"), d=0)}</td>'
                     f'<td data-v="{kc}">{count_in(kc, nc)}</td><td class="small muted why-col">{e("; ".join(rk.get("why") or [])[:140])}</td></tr>')
        market = "Canadian" if canada else "U.S."
        return f"""<section><div class="sec-head"><h2 class="h2">Who would feel a crash first</h2>
<p>The {market} stocks Quiplee covers, ranked by crash exposure. Quiplee covers a sample of names, not the full index.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th data-sort-first="desc">Exposure</th><th class="r">Beta</th><th class="r">2-yr change</th><th>Core plays</th><th>Why</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""

    # -------------------------------------------------------------- pair
    def render_pairs(self, workers=None):
        """Every stock x play page; one worker process per batch of tickers."""
        import os
        workers = workers or min(8, os.cpu_count() or 1)
        if workers <= 1:
            for t in TICKERS:
                for s in plays_for(t):
                    self.pair_page(t, s)
            return
        import multiprocessing as mp
        global _SITE
        _SITE = self
        with mp.get_context("fork").Pool(workers) as pool:
            for part in pool.imap_unordered(_pairs_for, [t["sym"] for t in TICKERS]):
                self.pages.update(part)

    def pair_page(self, t, s):
        path, depth = self.pair_path(t, s), 3
        h = lambda x: self.href(depth, x)
        x = self.r(t["sym"], s["slug"])
        nm = next_move(x, s, t)
        cur = t["cur"]
        st = x["stats"]
        since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
        st_word = "in" if x["state"] == 1 else ("out" if x["state"] == 0 else "undecided")
        state_line = (f"holds {t['short']}" if x["state"] == 1 else ("sits in T-bills" if x["state"] == 0 else "has no call yet"))

        level_html = ""
        if nm["level"] is not None:
            level_html = (f'<div><span class="level">{money(nm["level"], cur)}</span></div>'
                          f'<span class="level-sub">{pct(nm["dist"])} from the {dshort(x["asof"])} close of {money(x["price"], cur)}</span>')
        elif nm.get("date") is not None:
            level_html = f'<div><span class="level">{dshort(nm["date"])}</span></div><span class="level-sub">{nm.get("dist_days")} days from the {dshort(x["asof"])} close</span>'
        checks_html = ""
        if nm["checks"]:
            checks_html = '<ul class="checks">' + "".join(
                f'<li><span class="{"ok" if ok_ else "no"}">{"✓" if ok_ else "✕"}</span>{e(lab)}</li>' for lab, ok_ in nm["checks"]) + "</ul>"
        notes = "".join(f'<p class="muted small">{e(n_)}</p>' for n_ in nm["notes"])
        alert = f'<p class="alert-line">{e(nm["alert"])}</p>' if nm["alert"] else ""
        facts = ""
        if x["state"] is not None:
            facts = (f'<div class="facts"><span>{"In" if x["state"] == 1 else "Out"} since <b>{dlong(x["since"])}</b></span>'
                     f'<span>at <b>{money(x["since_price"], cur)}</b></span><span>{t["short"]} since then <b class="{dir_cls(since_move)}">{pct(since_move)}</b></span></div>')
        pn = x["window"].get("panel")
        reading = ""
        if pn:
            parts = []
            for lab, ser, _ in pn["series"]:
                v = ser.dropna()
                if len(v):
                    val = float(v.iloc[-1])
                    parts.append(f"{e(lab)} <b>{pct(val, sign=False) if pn['fmt'] == 'pct' else f'{val:,.2f}'.replace('-', '−')}</b>")
            if parts:
                reading = f'<p class="muted small reading">Latest reading: {" · ".join(parts)}</p>'
        verdict = f"""<section class="verdict">
<div class="card"><p class="eyebrow">What the play says</p>
<div class="byline">{pill(x['state'], lg=True)}<span class="big" style="color:var(--ink)">The play {state_line}.</span></div>
{facts}{checks_html}{reading}</div>
<div class="card next-card"><p class="eyebrow">Next move</p><p class="h3" style="font-size:17px;line-height:1.45">{e(nm['headline'])}</p>
{level_html}{alert}{notes}<p class="muted small">{e(nm['check'])}</p></div>
</section>"""

        keys = [key_line("--s-price", t["short"])]
        for lab, _, role in x["window"]["lines"]:
            keys.append(key_line(ROLE_VAR.get(role, "--s1"), lab))
        keys += [key_wash("in", "Play in"), key_wash("out", "Play out")]
        pchart = chart_block("px", price_spec(x, s, t), "".join(keys), f"{e(t['short'])} with the play, last two years",
                             "Shading shows the play's call from the close that triggered it.")
        pspec = panel_spec(x, s, t)
        panel_html = ""
        if pspec:
            pkeys = "".join(key_line(ROLE_VAR.get(sr["role"], "--s1"), sr["name"]) for sr in pspec["series"])
            lv = ", ".join(str(v).replace("-", "−") for v in pspec.get("levels", []))
            panel_html = chart_block("ind", pspec, pkeys, e(pspec["label"]), f"Dashed line{'s' if len(pspec.get('levels', [])) > 1 else ''} at {lv}." if lv else None, small=True)
        echart = ""
        if st["start"] is not None:
            echart = chart_block("eq", equity_spec(x, s, t), key_line("--s1", s["name"]) + key_line("--s-bench", "Buy & hold"),
                                 f"Growth of {cur}10,000 since {st['start'].year}", "Log scale. After trading costs, with T-bill interest while out.")

        def cell(dct, key, fmt):
            v = (dct or {}).get(key)
            return fmt(v) if v is not None else "–"
        rows = ""
        for lab, key, fmt in [("Annual return", "cagr", pct), ("Total return", "total", lambda v: pct(v, d=0)), ("Worst drawdown", "maxdd", pct),
                              ("Volatility", "vol", lambda v: pct(v, sign=False)), ("Sharpe ratio", "sharpe", ratio)]:
            rows += (f'<tr><td>{lab}</td><td class="r">{cell(st["full"]["strat"], key, fmt)}</td><td class="r muted">{cell(st["full"]["bh"], key, fmt)}</td>'
                     f'<td class="r">{cell(st["5y"]["strat"], key, fmt)}</td><td class="r muted">{cell(st["5y"]["bh"], key, fmt)}</td></tr>')
        rows += f'<tr><td>Time invested</td><td class="r">{pct(st["invested"], sign=False, d=0)}</td><td class="r muted">100%</td><td></td><td></td></tr>'
        rows += f'<tr><td>Switches per year</td><td class="r">{st["switches_per_year"]:.1f}</td><td class="r muted">0</td><td></td><td></td></tr>'
        start_y = st["start"].year if st["start"] is not None else "–"
        stats_tbl = (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th></th><th class="r">Play, since {start_y}</th><th class="r">Buy &amp; hold</th>'
                     f'<th class="r">Play, 5 yrs</th><th class="r">Buy &amp; hold</th></tr></thead><tbody>{rows}</tbody></table></div>')

        bat = x["batting"]
        shown = 12
        calls = x["calls"][-shown:][::-1]
        crow = ""
        for c in calls:
            res_ = ('<span class="muted">open</span>' if not c["closed"] else
                    ('<span class="up">✓ right</span>' if c["right"] else '<span class="down">✕ wrong</span>'))
            crow += (f'<tr><td class="nowrap">{dlong(c["date"])}</td><td>{pill(c["state"])}</td><td class="r">{money(c["price"], cur)}</td>'
                     f'<td class="nowrap" data-v="{pd.Timestamp(c["end"]).strftime("%Y-%m-%d")}">{dlong(c["end"]) if c["closed"] else "now"}</td>'
                     f'<td class="r {dir_cls(c["move"])}">{pct(c["move"])}</td><td data-v="{(1 if c["right"] else 0) if c["closed"] else ""}">{res_}</td></tr>')
        bat_line = (f'Right on <b>{bat["right"]}</b> of <b>{bat["n"]}</b> closed calls ({pct(bat["avg"], sign=False, d=0)}). '
                    f'In calls averaged {pct(bat["in_avg"])}; out calls saw {t["short"]} move {pct(bat["out_avg"])} on average.') if bat["n"] else "No closed calls yet."
        calls_sec = f"""<section><div class="sec-head"><h2 class="h2">Every call, graded</h2><p>{bat_line}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Called</th><th>Call</th><th class="r">Price</th><th>Until</th><th class="r">{e(t['short'])} moved</th><th>Result</th></tr></thead><tbody>{crow}</tbody></table></div>
<p class="muted small">An in call is right when the price rose before the next call; an out call is right when it fell. The latest {min(shown, len(x['calls']))} of {len(x['calls'])} calls shown.</p></section>""" if x["calls"] else ""

        by = " &amp; ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in s["analysts"])
        play_sel = self.play_options(s["slug"])
        stock_sel = self.stock_options(t["sym"])
        play_tmpl = e(h("stocks/" + t["slug"] + "/{v}/"))
        stock_tmpl = e(h("stocks/{v}/" + s["slug"] + "/"))
        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><a href="{h('stocks/' + t['slug'] + '/')}">{e(t['short'])}</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(FAMILY[s['family']][0])} · {e(BAR_WORD[s['bar']])} rule · {e(t['group'])}</p>
<h1 class="h1">{e(s['name'])} on {e(t['name'])}</h1>
<div class="byline"><span>Play from {by}</span><span>·</span><a href="{h('strategies/' + s['slug'] + '/')}">How it works</a><span>·</span><a href="{h('learn/reading-a-page/')}">How to read this page</a>{flag_tag(s)}</div></section>
{verdict}
{pchart}
{panel_html}
{echart}
<section><div class="sec-head"><h2 class="h2">The record</h2><p>The play against buying and holding {e(t['short'])} over exactly the same dates, after costs.</p></div>{stats_tbl}</section>
{calls_sec}
<section class="split">{self.rule_card(s)}{self.against_card(depth)}</section>
<section class="jump split"><div><label class="small muted" for="jump-play">Another play on {e(t['short'])}</label><select id="jump-play" data-nav data-tmpl="{play_tmpl}">{play_sel}</select></div>
<div><label class="small muted" for="jump-stock">{e(s['name'])} on another stock</label><select id="jump-stock" data-nav data-tmpl="{stock_tmpl}">{stock_sel}</select></div></section>
"""
        title = f"{s['name']} on {t['short']}: the play says {st_word}"
        desc = f"{credit(s)}'s {s['long']} applied to {t['name']} ({t['short']}) since {start_y}: {st_word} since {dlong(x['since'])}. {nm['headline']}"
        self.add(path, self.shell(path, title, desc, body, active="stocks/"))

    # ------------------------------------------------------------ method
    def method_page(self):
        path, depth = "method/", 1
        h = lambda x: self.href(depth, x)
        body = f"""
<section class="pair-head"><p class="eyebrow">Method</p><h1 class="h1">How Quiplee tests a play</h1>
<p class="lede">The same test for all {len(TIMED)} plays and all {len(universe())} stocks, written down so anyone can check it.</p></section>
<section class="split">
<div class="card prose"><p class="eyebrow">Data</p><ul>
<li>Daily open, high, low, close and volume, adjusted for splits and dividends, from Yahoo Finance since January 2004. Grading starts in January 2005, or once a stock has enough history for the play.</li>
<li>Cash earns the 13-week U.S. Treasury bill yield (^IRX). Canadian names use the same rate, which slightly flatters or penalises them.</li>
<li>Every signal uses finished bars only. Today's price is ignored until the market has closed, and weekly or monthly plays wait for the week or month to end.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">Execution and costs</p><ul>
<li>A call made on a close is acted on at the next session. Plays that buy on the signal day's close, like Connors' RSI(2), are tested the same way.</li>
<li>Each switch in or out costs 0.05% for stocks and ETFs, 0.10% for crypto and 0.30% for micro caps, whose buying and selling prices are far apart.</li>
<li>No leverage, no shorting, no taxes. Every play is long or in T-bills, even where its author also sold short. Each play page lists where Quiplee's version differs from the original.</li>
</ul></div>
</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Grading</p><ul>
<li><b>Calls right:</b> an in call is right if the price was higher when the next call came; an out call is right if it was lower. Open calls are not graded.</li>
<li><b>Annual return, worst drawdown, volatility:</b> computed on the play's daily returns, including T-bill interest while out.</li>
<li><b>Sharpe ratio:</b> average return above T-bills divided by volatility, annualised.</li>
<li>Every play is compared with buying and holding the same stock over exactly the same dates.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">The next move</p><ul>
<li>Quiplee asks each play what it would say after one more bar at a range of hypothetical closes, from about 30% below the latest close to 40% above (wider for crypto, micro caps and monthly plays), then narrows each point where the call flips to a fraction of a cent.</li>
<li>For a daily play the next bar opens at today's close; its high and low are assumed to stretch only as far as the hypothetical close. Plays that use the day's high, low or volume are approximate on that point.</li>
<li>Some plays can't flip on one close, for example when a crossover needs two days or an indicator is shifted forward in time. The page says so instead of showing a level. Calendar plays show the date of their next change.</li>
<li>Daily plays check every close. Weekly plays check the Friday close (Sunday for crypto). Monthly plays check the last close of the month. Future dates use the U.S. market holiday calendar.</li>
</ul></div>
</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Crash exposure</p><ul>
<li>A 10-point checklist per stock: market swings (beta over three years of weekly returns and monthly downside capture against the S&amp;P 500, or the TSX for Canadian names; up to 3 points), past crashes (its fall against its index's in the 2000–02, 2008–09, 2020 and 2022 bear markets; up to 2), debt (negative equity, debt to equity, interest cover and net debt to EBITDA; up to 3) and run-up (two-year gains of 100% or 150%; up to 2).</li>
<li>0–2 is Low, 3–4 Moderate, 5–6 High, 7 or more Very high. It describes fragility, not timing.</li>
<li>Company figures come from Yahoo Finance and are refreshed nightly; banks and insurers borrow as their business, so their debt ratios read high by design.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">Market gauges</p><ul>
<li>Nine monthly series: trend (S&amp;P 500 against its 200-day average, and how many plays hold it), valuation (Shiller CAPE from multpl.com), run-up (Nasdaq-100 two-year return), concentration (equal-weight RSP against SPY over three years), volatility (VIX), the 10-year minus 3-month yield curve, the Baa corporate spread, the Sahm rule and the 10-year Treasury yield, from Yahoo Finance and FRED.</li>
<li>Each gauge is calm, watch or warning on thresholds stated on the Markets page, chosen from the research cited there. The weather word adds them up: two points per warning, one per watch, and "stormy" also needs the trend gauge to have broken.</li>
</ul></div>
</section>
<section class="card prose"><p class="eyebrow">Reader-requested stocks</p>
<p>Tickers added on the watchlist that Quiplee doesn't cover go to a queue holding only the symbol and when it was asked for. Each night, after the U.S. close, up to 25 new symbols are checked for at least 60 sessions of price history on Yahoo Finance, added to the universe, and analysed in the next build: all {len(TIMED)} plays, with a full page for each of the 20 core plays. Reader-requested names are kept out of the cross-stock scoreboards so those counts don't shift as names are added. Watchlists themselves stay in the reader's browser.</p></section>
<section class="card prose"><p class="eyebrow">Sources and attribution</p>
<p>Every play's origin, parameters and the analyst's bio were checked against books, journal papers, the analyst's own site or reputable references such as StockCharts ChartSchool. Where a source was missing or two sources disagreed, the play or analyst page says so. Where a rule needed a choice its author never made, such as an exit for a buy-only signal, the choice is labelled as Quiplee's.</p></section>
<section class="card prose"><p class="eyebrow">What this is not</p>
<p>Quiplee reports what a published rule says. It does not know your goals, taxes or other holdings, and it is not financial advice. Past results come from a backtest on stocks that are still listed today, which flatters every play and buy and hold alike. With {len(TIMED)} plays and {len(universe())} stocks, some pairs will look excellent by luck alone. Summaries of each analyst's views are Quiplee's paraphrase of public material, and Quiplee has no affiliation with them.</p>
<p>Rebuilt automatically after each U.S. market close. <a href="{h('strategies/')}">See every play</a> or <a href="{h('thinkers/valeriy-zakamulin/')}">the case against timing</a>.</p></section>
"""
        self.add(path, self.shell(path, "Method", "How Quiplee tests every trading play: data, execution, costs, grading and the next-move math.", body, active="method/"))

    # ------------------------------------------------------------ exports
    def signals_json(self):
        out = []
        for t in TICKERS:
            for s in PLAYS:
                x = self.r(t["sym"], s["slug"])
                nm = next_move(x, s, t)
                out.append({"sym": t["sym"], "play": s["slug"], "family": s["family"], "analysts": s["analysts"], "state": x["state"],
                            "since": x["since"].strftime("%Y-%m-%d") if x["since"] is not None else None,
                            "next": nm["short"], "level": nm["level"],
                            "next_check": x["next_check"].strftime("%Y-%m-%d"), "price": x["price"],
                            "asof": x["asof"].strftime("%Y-%m-%d")})
        return json.dumps({"asof": self.asof.strftime("%Y-%m-%d"), "signals": out}, separators=(",", ":"))

    def sitemap(self):
        urls = "".join(f"  <url><loc>{BASE}{p}</loc><lastmod>{self.asof.strftime('%Y-%m-%d')}</lastmod></url>\n"
                       for p in sorted(list(self.pages.keys()) + ["desk/", "stories/the-hertz-lesson.html"]))
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


_SITE = None


def _pairs_for(sym):
    site = _SITE
    t = TK[sym]
    before = set(site.pages)
    for s in plays_for(t):
        site.pair_page(t, s)
    return {k: v for k, v in site.pages.items() if k not in before}
