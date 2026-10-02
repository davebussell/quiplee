"""HTML renderer for the strategy site. Pure functions over engine results.

Links are relative so the same output works on quiplee.com and in a static
preview; `preview=True` spells out index.html for hosts without directory
indexes.
"""
import html
import json
import math

import numpy as np
import pandas as pd

from .content import (TICKERS, THINKERS, THINKER, STRATEGIES, STRATEGY, TIMED,
                      GROUP_ORDER, BAR_WORD)

e = html.escape
TK = {t["sym"]: t for t in TICKERS}
BASE = "https://quiplee.com/"
FONTS = ("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700"
         "&family=Geist+Mono:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap")
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' "
        "fill='%230b0f17'/%3E%3Ctext x='13' y='44' font-family='Arial,sans-serif' font-size='38' font-weight='800' fill='%23e7edf7'%3Eq%3C/text%3E"
        "%3Cpath d='M40 40 L48 26 L56 40 Z' fill='%231fd093'/%3E%3C/svg%3E")
NAV = [("", "Signals"), ("strategies/", "Strategies"), ("thinkers/", "Thinkers"),
       ("stocks/", "Stocks"), ("stories/", "Stories"), ("desk/", "Live desk"), ("method/", "Method")]


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------
def money(v, cur="$"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{cur}{v:,.0f}" if abs(v) >= 10000 else f"{cur}{v:,.2f}"


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


def sig5(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(f"{v:.5g}")


# --------------------------------------------------------------------------
# the "next move" sentence
# --------------------------------------------------------------------------
BAR_CLOSE = {"D": "a daily close", "W": "a weekly close", "M": "a month-end close"}
BAR_PERIOD = {"W": "week", "M": "month"}


def next_move(res, strat, t):
    cur, price, trig, bar = t["cur"], res["price"], res["trigger"], res["bar"]
    out = {"headline": "", "level": None, "dist": None, "check": "", "alert": None, "notes": [], "checks": trig.get("checks")}
    nc = res["next_check"]
    if bar == "D":
        out["check"] = f"Next check: the {dlong(nc)} close"
    elif res["bar_complete"]:
        out["check"] = f"Next check: the {BAR_PERIOD[bar]} ending {dlong(nc)}"
    else:
        out["check"] = f"Next check: this {BAR_PERIOD[bar]}'s close, {dlong(nc)}"
    if strat["kind"] == "hold":
        out["headline"] = "Always in. Nothing in this rule ever sells."
        out["check"] = "No check needed"
        return out
    st = res["state"]
    if st == 1:
        lvl = trig["exit"]
        out["headline"] = f"Stays in unless {BAR_CLOSE[bar]} lands below {money(lvl, cur)}."
        out["level"], out["dist"] = lvl, lvl / price - 1
        if bar != "D" and not res["bar_complete"] and price < lvl:
            out["alert"] = f"The latest close ({money(price, cur)}) is already below this level. If the {BAR_PERIOD[bar]} ended today, the rule would exit."
    else:
        lvl = trig.get("enter")
        if lvl is None:
            out["headline"] = "Stays out. The uptrend structure isn't in place yet, so no single close can flip it."
        else:
            out["headline"] = f"Stays out until {BAR_CLOSE[bar]} lands above {money(lvl, cur)}."
            out["level"], out["dist"] = lvl, lvl / price - 1
            if bar != "D" and not res["bar_complete"] and price > lvl:
                out["alert"] = f"The latest close ({money(price, cur)}) is already above this level. If the {BAR_PERIOD[bar]} ended today, the rule would re-enter."
            if strat["kind"] == "stage" and trig["enter"] > trig["exit"] + 1e-9:
                out["notes"].append(f"Price must also keep the 30-week average rising, which sets the bar above the average itself ({money(trig['exit'], cur)}).")
            if strat["kind"] == "template":
                out["notes"].append("That is the lowest close that would pass every price condition at once.")
    if strat["kind"] == "band" and trig.get("zone") == "between":
        other = trig["enter"] if st == 1 else trig["exit"]
        verb = "confirms above" if st == 1 else "gets worse below"
        out["notes"].append(f"Price is inside the band, so the rule is holding its last call. It {verb} {money(other, cur)}.")
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


def price_spec(res, strat, t, with_rule=True):
    win = res["window"]["price"]
    t0 = win.index[0]
    spec = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((d - t0).days) for d in win.index], "cur": t["cur"], "fmt": "price",
            "label": f"{t['short']} price, last three years", "series": [{"name": t["short"], "role": "price", "v": [sig5(v) for v in win.values]}]}
    if with_rule and strat["kind"] != "hold":
        lines = res["window"]["lines"]
        keys = list(lines.keys())
        if strat["kind"] == "template":
            keys = ["50-day SMA", "200-day SMA"]
        for k, role in zip(keys, ["s1", "s2"]):
            s = lines[k].reindex(win.index, method="ffill")
            spec["series"].append({"name": k, "role": role, "v": [sig5(v) for v in s.values]})
        spec["runs"] = _runs(res["window"]["pos"])
        spec["label"] = f"{t['short']} price with the {strat['name']} rule, last three years"
    return spec


def equity_spec(res, strat, t):
    eq = res["equity"]
    t0 = pd.Timestamp(eq["dates"][0])
    return {"t0": t0.strftime("%Y-%m-%d"), "d": [int((pd.Timestamp(d) - t0).days) for d in eq["dates"]], "cur": t["cur"],
            "fmt": "money", "log": True, "label": f"Growth of 10,000 in {t['short']}",
            "series": [{"name": strat["name"], "role": "s1", "v": [sig5(v * 10000) for v in eq["strat"]]},
                       {"name": "Buy & hold", "role": "bench", "v": [sig5(v * 10000) for v in eq["bh"]]}]}


def chart_block(cid, spec, keys_html, title, note=None):
    data = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class="card chart-card"><div class="chart-top"><h3 class="h3">{title}</h3>'
            f'<div class="legend-row">{keys_html}</div></div>'
            f'<div class="chart" data-chart="{cid}" aria-label="{e(spec.get("label", title))}"></div>'
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
    def __init__(self, results, preview=False, built=None):
        self.R = results
        self.preview = preview
        self.built = built
        self.asof = max(r["asof"] for r in results.values())
        self.pages = {}   # path -> html
        self.ver = self.asof.strftime("%Y%m%d")

    # ----- helpers -----
    def r(self, sym, slug):
        return self.R[(sym, slug)]

    def href(self, depth, target):
        path = target
        if self.preview and (target == "" or target.endswith("/")):
            path += "index.html"
        return ("../" * depth + path) or "./"

    def pair_path(self, t, s):
        return f"stocks/{t['slug']}/{s['slug']}/"

    def shell(self, path, title, desc, body, active=None, charts=False, extra_head=""):
        depth = path.count("/")
        h = lambda target: self.href(depth, target)
        cur_attr = ' aria-current="page"'
        nav = "".join(f'<a href="{h(p)}"{cur_attr if p == active else ""}>{lab}</a>' for p, lab in NAV)
        full_title = f"{title} · Quiplee" if path else title
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
<p>Quiplee runs published trading rules on real prices and shows what each rule says now. These are rule outputs, not financial advice, and Quiplee takes no positions in the names it covers.</p>
<p>Closes through {dlong(self.asof)} · Prices from Yahoo Finance · Rebuilt after each U.S. close · <a href="{h('method/')}">How we test</a></p>
</div></footer>
<script src="{h('assets/site.js')}?v={self.ver}" defer></script>
<script src="{h('assets/sortable.js')}?v={self.ver}" defer></script>
</body>
</html>
"""

    def add(self, path, html_):
        self.pages[path] = html_

    # ----- aggregates -----
    def strat_summary(self, s):
        rows = [self.r(t["sym"], s["slug"]) for t in TICKERS]
        n = len(rows)
        full = [(x["stats"]["full"]["strat"], x["stats"]["full"]["bh"]) for x in rows]
        ok = [(a, b) for a, b in full if a and b]
        right = sum(x["batting"]["right"] for x in rows)
        calls = sum(x["batting"]["n"] for x in rows)
        return {
            "n": n,
            "in_now": sum(1 for x in rows if x["state"] == 1),
            "beat_sharpe": sum(1 for a, b in ok if a["sharpe"] is not None and b["sharpe"] is not None and a["sharpe"] > b["sharpe"]),
            "beat_cagr": sum(1 for a, b in ok if a["cagr"] > b["cagr"]),
            "cut_dd": sum(1 for a, b in ok if a["maxdd"] > b["maxdd"]),
            "bat": right / calls if calls else None, "calls": calls,
        }

    def consensus(self, t):
        states = [self.r(t["sym"], s["slug"])["state"] for s in TIMED]
        return sum(1 for x in states if x == 1), len(states)

    def meter(self, k, n):
        bars = "".join(f'<i class="{"on" if i < k else ""}"></i>' for i in range(n))
        return f'<span class="consensus"><span class="meter" aria-hidden="true">{bars}</span>{k} of {n} in</span>'

    # ======================================================================
    # pages
    # ======================================================================
    def build(self):
        self.home()
        self.strategies_index()
        for s in STRATEGIES:
            self.strategy_page(s)
        self.thinkers_index()
        for th in THINKERS:
            self.thinker_page(th)
        self.stocks_index()
        for t in TICKERS:
            self.stock_page(t)
            for s in TIMED:
                self.pair_page(t, s)
        self.method_page()
        return self.pages

    # ---------------------------------------------------------------- home
    def home(self):
        path, depth = "", 0
        h = lambda x: self.href(depth, x)
        timed_pairs = [(t, s, self.r(t["sym"], s["slug"])) for t in TICKERS for s in TIMED]
        total = len(timed_pairs)
        dd = sum(1 for _, _, x in timed_pairs if x["stats"]["full"]["strat"] and x["stats"]["full"]["strat"]["maxdd"] > x["stats"]["full"]["bh"]["maxdd"])
        cg = sum(1 for _, _, x in timed_pairs if x["stats"]["full"]["strat"] and x["stats"]["full"]["strat"]["cagr"] > x["stats"]["full"]["bh"]["cagr"])
        sh = sum(1 for _, _, x in timed_pairs if x["stats"]["full"]["strat"] and (x["stats"]["full"]["strat"]["sharpe"] or -9) > (x["stats"]["full"]["bh"]["sharpe"] or -9))

        # picker
        opt_s = "".join(f'<option value="{s["slug"]}">{e(s["name"])} · {e(THINKER[s["thinker"]]["name"])}</option>' for s in TIMED)
        opt_t = ""
        for g in GROUP_ORDER:
            opt_t += f'<optgroup label="{e(g)}">' + "".join(
                f'<option value="{t["slug"]}"{" selected" if t["sym"] == "NVDA" else ""}>{e(t["short"])} · {e(t["name"])}</option>'
                for t in TICKERS if t["group"] == g) + "</optgroup>"
        tmpl = self.href(depth, "stocks/{t}/{s}/")

        # board
        head = "".join(f'<th class="col" scope="col"><a href="{h("strategies/" + s["slug"] + "/")}">{e(s["name"])}</a>'
                       f'<span class="sym-sub">{e(THINKER[s["thinker"]]["name"])}</span></th>' for s in TIMED)
        rows = ""
        for g in GROUP_ORDER:
            rows += f'<tr class="grp"><td class="stick">{e(g)}</td><td colspan="{len(TIMED) + 1}"></td></tr>'
            for t in [x for x in TICKERS if x["group"] == g]:
                cells = ""
                for s in TIMED:
                    x = self.r(t["sym"], s["slug"])
                    band = x["trigger"].get("zone") == "between"
                    tip = f'{s["name"]} on {t["short"]}: {"in" if x["state"] == 1 else "out"} since {dlong(x["since"])}'
                    cells += (f'<td class="cell"><a href="{h(self.pair_path(t, s))}" title="{e(tip)}">{pill(x["state"])}'
                              f'{BAND_MARK if band else ""}</a></td>')
                k, n = self.consensus(t)
                rows += (f'<tr><td class="stick"><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a>'
                         f'<span class="sym-sub">{e(t["name"])}</span></td>{cells}<td class="c">{self.meter(k, n)}</td></tr>')

        # recent flips
        flips = []
        cutoff = self.asof - pd.Timedelta(days=30)
        for t, s, x in timed_pairs:
            if x["calls"] and x["calls"][-1]["date"] >= cutoff:
                c = x["calls"][-1]
                flips.append((c["date"], t, s, c))
        flips.sort(key=lambda z: (z[0], z[1]["sym"]), reverse=True)
        flip_html = "".join(
            f'<li><a href="{h(self.pair_path(t, s))}"><span class="when">{dshort(d)}</span>{pill(c["state"])}'
            f'<span class="what"><b>{e(s["name"])} on {e(t["short"])}</b><span>{"Went in" if c["state"] == 1 else "Went out"} at {money(c["price"], t["cur"])} · {e(THINKER[s["thinker"]]["name"])}</span></span></a></li>'
            for d, t, s, c in flips[:12]) or '<li class="muted">No rule changed its call in the last 30 days.</li>'

        # thinkers
        cards = "".join(self.thinker_card(th, depth) for th in THINKERS)

        body = f"""
<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">Strategies, graded in public</p>
    <h1 class="h1">Pick a thinker. Pick a stock. See the next move.</h1>
    <p class="lede">Quiplee takes the trading rules people actually follow, from Meb Faber's 10-month average to Ben Cowen's bull market support band, runs each one on {len(TICKERS)} stocks, ETFs and coins from 2005 or their first trading day, grades every call it made, and shows the exact close that would flip it next.</p>
  </div>
  <form class="card picker" id="picker" data-href="{e(tmpl)}">
    <label for="pick-strategy">Strategy<select id="pick-strategy">{opt_s}</select></label>
    <label for="pick-stock">Stock<select id="pick-stock">{opt_t}</select></label>
    <button type="submit">Show the call</button>
    <p class="picker-out">Rule outputs, not advice. Every number links to the rule and the data behind it.</p>
  </form>
</section>

<section aria-labelledby="score-h">
  <div class="sec-head"><h2 class="h2" id="score-h">Does timing beat Bogle?</h2>
  <p>{total} strategy–stock pairs, each graded against simply buying and holding over the same dates, with trading costs and T-bill interest while out.</p></div>
  <div class="tiles">
    <div class="card tile"><span class="tile-label">Cut the worst drawdown</span><span class="tile-value">{dd} of {total}</span><span class="tile-note">Smaller peak-to-trough loss than buy and hold.</span></div>
    <div class="card tile"><span class="tile-label">Beat buy and hold on risk-adjusted return</span><span class="tile-value">{sh} of {total}</span><span class="tile-note">Higher Sharpe ratio over the full test.</span></div>
    <div class="card tile"><span class="tile-label">Beat buy and hold on raw return</span><span class="tile-value">{cg} of {total}</span><span class="tile-note">Higher annual growth. <a href="{h('thinkers/valeriy-zakamulin/')}">What the skeptic says</a></span></div>
  </div>
</section>

<section aria-labelledby="board-h">
  <div class="sec-head"><h2 class="h2" id="board-h">What every rule says now</h2>
  <p>Each cell is one rule on one stock, as of the {dlong(self.asof)} close. Tap it for the history, the record and the next move.</p></div>
  <div class="tbl-wrap"><table class="tbl board"><thead><tr><th class="stick" scope="col">Stock</th>{head}<th class="c" scope="col">Rules in</th></tr></thead>
  <tbody>{rows}</tbody></table></div>
  <div class="legend-row">{pill(1)} the rule holds the stock {pill(0)} the rule sits in T-bills <span><span class="band-mark"></span> price is inside the band and the rule is holding its last call</span></div>
</section>

<section aria-labelledby="flips-h">
  <div class="sec-head"><h2 class="h2" id="flips-h">Calls that changed in the last 30 days</h2></div>
  <ul class="flips">{flip_html}</ul>
</section>

<section aria-labelledby="thinkers-h">
  <div class="sec-head"><h2 class="h2" id="thinkers-h">The thinkers</h2>
  <p>Every rule is tied to the person who published or popularised it. Same test, same costs, same scorecard for all of them.</p></div>
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
        self.add(path, self.shell(path, "Quiplee · Every trading rule, graded", "Famous trading rules from named thinkers, tested on stocks, ETFs and crypto since 2005, with every call graded and the exact level that flips each rule next.", body, active="", extra_head=extra))

    def thinker_card(self, th, depth):
        h = lambda x: self.href(depth, x)
        if th.get("skeptic"):
            rec = f'<div class="rec"><span><b>No rule</b>audits the others</span></div>'
            strat = "The skeptic"
        elif th.get("benchmark"):
            rec = f'<div class="rec"><span><b>Benchmark</b>every rule is graded against this</span></div>'
            strat = "Buy & Hold"
        else:
            s = STRATEGY[th["strategies"][0]]
            sm = self.strat_summary(s)
            strat = s["name"]
            rec = (f'<div class="rec"><span><b>{pct(sm["bat"], sign=False, d=0)}</b>calls right</span>'
                   f'<span><b>{sm["beat_sharpe"]} of {sm["n"]}</b>beat buy &amp; hold (Sharpe)</span>'
                   f'<span><b>{sm["in_now"]} of {sm["n"]}</b>in now</span></div>')
        return (f'<a class="card thinker-card" href="{h("thinkers/" + th["slug"] + "/")}"><span class="strat">{e(strat)}</span>'
                f'<span class="name">{e(th["name"])}</span><span class="role">{e(th["role"])}</span>{rec}</a>')

    # ------------------------------------------------------- strategies
    def strategies_index(self):
        path, depth = "strategies/", 1
        h = lambda x: self.href(depth, x)
        rows = ""
        for s in STRATEGIES:
            th = THINKER[s["thinker"]]
            if s.get("benchmark"):
                rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}"><b>{e(s["name"])}</b></a><span class="sym-sub">{e(s["short"])}</span></td>'
                         f'<td><a href="{h("thinkers/" + th["slug"] + "/")}">{e(th["name"])}</a></td><td>–</td><td class="c" colspan="4">The benchmark</td></tr>')
                continue
            sm = self.strat_summary(s)
            rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}"><b>{e(s["name"])}</b></a>'
                     f'{flag_tag(s)}<span class="sym-sub">{e(s["short"])}</span></td>'
                     f'<td><a href="{h("thinkers/" + th["slug"] + "/")}">{e(th["name"])}</a></td><td class="nowrap">{BAR_WORD[s["bar"]].capitalize()}</td>'
                     f'<td class="r">{sm["in_now"]} of {sm["n"]}</td><td class="r">{pct(sm["bat"], sign=False, d=0)}</td>'
                     f'<td class="r">{sm["beat_sharpe"]} of {sm["n"]}</td><td class="r">{sm["cut_dd"]} of {sm["n"]}</td></tr>')
        body = f"""
<section class="pair-head"><p class="eyebrow">Strategies</p><h1 class="h1">Seven rules, one scorecard</h1>
<p class="lede">Each rule is written down exactly as Quiplee tests it, run on every stock in the universe, and graded against buying and holding the same stock over the same dates.</p></section>
<section><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th>Thinker</th><th>Checks</th><th class="r">In now</th><th class="r">Calls right</th><th class="r">Beat B&amp;H Sharpe</th><th class="r">Cut drawdown</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="muted small">Calls right: the share of closed calls where an in call was followed by a higher price, or an out call by a lower one. Trend rules often win well under half their calls and make it back on a few long trends.</p></section>
"""
        self.add(path, self.shell(path, "Strategies", "Every trading rule Quiplee tests, with who it comes from and how it has scored.", body, active="strategies/"))

    def strategy_page(self, s):
        path, depth = f"strategies/{s['slug']}/", 2
        h = lambda x: self.href(depth, x)
        th = THINKER[s["thinker"]]
        rule_card = self.rule_card(s)
        if s.get("benchmark"):
            rows = ""
            for g in GROUP_ORDER:
                rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
                for t in [x for x in TICKERS if x["group"] == g]:
                    b = self.r(t["sym"], s["slug"])["stats"]["full"]["bh"]
                    rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td class="r {dir_cls(b["cagr"])}">{pct(b["cagr"])}</td><td class="r">{pct(b["maxdd"])}</td><td class="r">{ratio(b["sharpe"])}</td>'
                             f'<td class="r nowrap">{dlong(self.r(t["sym"], s["slug"])["stats"]["start"])}</td></tr>')
            body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Strategies</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(th['name'])} · the benchmark</p><h1 class="h1">{e(s['long'])}</h1><p class="lede">{e(s['short'])}</p></section>
<section><h2 class="h2">Buy and hold, stock by stock</h2>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Since</th></tr></thead><tbody>{rows}</tbody></table></div></section>
"""
            self.add(path, self.shell(path, s["long"], s["short"], body, active="strategies/"))
            return

        sm = self.strat_summary(s)
        now_rows, rec_rows = "", ""
        for g in GROUP_ORDER:
            now_rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
            rec_rows += f'<tr class="grp"><td colspan="6">{e(g)}</td></tr>'
            for t in [x for x in TICKERS if x["group"] == g]:
                x = self.r(t["sym"], s["slug"])
                nm = next_move(x, s, t)
                lvl = (f'{money(nm["level"], t["cur"])} <span class="muted">({pct(nm["dist"])})</span>' if nm["level"] is not None else '<span class="muted">Structure not in place</span>')
                band = '<span class="band-mark" title="Inside the band"></span>' if x["trigger"].get("zone") == "between" else ""
                link = h(self.pair_path(t, s))
                now_rows += (f'<tr><td><a class="sym" href="{link}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td>{pill(x["state"])}{band}</td><td class="nowrap">{dlong(x["since"])}</td>'
                             f'<td class="nowrap" data-v="{sortv(None if nm["dist"] is None else abs(nm["dist"]))}">{"Exit below " if x["state"] == 1 else "Enter above "}{lvl}</td><td class="nowrap muted">{dlong(x["next_check"])}</td></tr>')
                a, b = x["stats"]["full"]["strat"], x["stats"]["full"]["bh"]
                bat = x["batting"]
                rec_rows += (f'<tr><td><a class="sym" href="{link}">{e(t["short"])}</a></td>'
                             f'<td class="r nowrap">{pct(a["cagr"])} <span class="muted">/ {pct(b["cagr"])}</span></td>'
                             f'<td class="r nowrap">{pct(a["maxdd"])} <span class="muted">/ {pct(b["maxdd"])}</span></td>'
                             f'<td class="r nowrap">{ratio(a["sharpe"])} <span class="muted">/ {ratio(b["sharpe"])}</span></td>'
                             f'<td class="r nowrap">{pct(bat["avg"], sign=False, d=0)} <span class="muted">of {bat["n"]}</span></td>'
                             f'<td class="r">{x["stats"]["switches_per_year"]:.1f}</td></tr>')
        body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Strategies</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head">
  <p class="eyebrow">{e(BAR_WORD[s['bar']])} rule{" · " + e(s['flag']) if s.get('flag') else ""}</p>
  <h1 class="h1">{e(s['long'])}</h1>
  <div class="byline">From <a href="{h('thinkers/' + th['slug'] + '/')}">{e(th['name'])}</a><span>·</span><span>{e(th['role'])}</span></div>
  <p class="lede">{e(s['short'])}</p>
</section>
<section><div class="tiles">
  <div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
  <div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">Across {sm['calls']:,} closed calls.</span></div>
  <div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['n']}</span><span class="tile-note">Cut the worst drawdown on {sm['cut_dd']} of {sm['n']}.</span></div>
</div></section>
<section class="split">{rule_card}{self.against_card(depth)}</section>
<section><div class="sec-head"><h2 class="h2">What it says now</h2><p>The exact close that would flip each call on its next {BAR_WORD[s['bar']]} check.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th>Next check</th></tr></thead><tbody>{now_rows}</tbody></table></div></section>
<section><div class="sec-head"><h2 class="h2">The record</h2><p>Rule / buy and hold over the same dates, since 2005 or the first date with enough history.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Calls right</th><th class="r">Switches / yr</th></tr></thead><tbody>{rec_rows}</tbody></table></div></section>
"""
        self.add(path, self.shell(path, s["long"], f"{s['long']} from {th['name']}: {s['short']} Current calls and full record on {len(TICKERS)} stocks.", body, active="strategies/"))

    def rule_card(self, s):
        rules = "".join(f"<li>{e(x)}</li>" for x in s["rules"])
        ass = "".join(f"<p>{e(x)}</p>" for x in s["assumptions"])
        return (f'<div class="card rule-card prose"><p class="eyebrow">How the rule works</p><ol>{rules}</ol>'
                + (f'<div class="assume">{ass}</div>' if ass else "") + "</div>")

    def against_card(self, depth):
        h = lambda x: self.href(depth, x)
        return (f'<div class="card prose"><p class="eyebrow">The case against</p><div class="against">'
                f'<p>Valeriy Zakamulin tested moving-average timing on up to 155 years of U.S. stock data and found no statistically significant edge in the second half of that record. The rules earned their keep in a few severe bear markets and lagged buy and hold for long stretches in between.</p>'
                f'<p><a href="{h("thinkers/valeriy-zakamulin/")}">Read the skeptic\'s scoreboard</a></p></div></div>')

    # ---------------------------------------------------------- thinkers
    def thinkers_index(self):
        path, depth = "thinkers/", 1
        cards = "".join(self.thinker_card(th, depth) for th in THINKERS)
        body = f"""
<section class="pair-head"><p class="eyebrow">Thinkers</p><h1 class="h1">The people behind the rules</h1>
<p class="lede">A trader, a YouTuber, a fund manager and three academics walk into a backtest. Each rule is graded the same way, whoever published it.</p></section>
<section><div class="grid grid-3">{cards}</div></section>
"""
        self.add(path, self.shell(path, "Thinkers", "The traders, analysts and academics behind every rule Quiplee tests.", body, active="thinkers/"))

    def thinker_page(self, th):
        path, depth = f"thinkers/{th['slug']}/", 2
        h = lambda x: self.href(depth, x)
        argues = "".join(f"<li>{e(x)}</li>" for x in th["argues"])
        srcs = "".join(f'<a href="{e(u)}" rel="noopener" target="_blank">{e(lab)}</a>' for lab, u in th["sources"])
        extra = ""
        if th.get("skeptic"):
            rows = ""
            for s in TIMED:
                sm = self.strat_summary(s)
                rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}">{e(s["name"])}</a><span class="sym-sub">{e(THINKER[s["thinker"]]["name"])}</span></td>'
                         f'<td class="r">{sm["beat_cagr"]} of {sm["n"]}</td><td class="r">{sm["beat_sharpe"]} of {sm["n"]}</td><td class="r">{sm["cut_dd"]} of {sm["n"]}</td></tr>')
            extra = f"""<section><div class="sec-head"><h2 class="h2">The skeptic's scoreboard</h2><p>How often each rule beat simply holding the stock, over the same dates, after costs.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th class="r">Beat on return</th><th class="r">Beat on Sharpe</th><th class="r">Cut drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted small">A rule that cuts drawdowns but loses on return is doing what Zakamulin's research predicts: paying for crash protection with years of lag.</p></section>"""
        else:
            for slug in th["strategies"]:
                s = STRATEGY[slug]
                if s.get("benchmark"):
                    extra += f"""<section><div class="card teaser"><div class="prose"><p class="eyebrow">The benchmark</p><p class="h2" style="color:var(--ink)">Every rule on Quiplee is graded against buy and hold.</p></div>
<a class="btn" href="{h('strategies/' + slug + '/')}">See buy and hold by stock</a></div></section>"""
                    continue
                sm = self.strat_summary(s)
                best = sorted(TICKERS, key=lambda t: -((self.r(t["sym"], slug)["stats"]["full"]["strat"] or {}).get("sharpe") or -9)
                              + ((self.r(t["sym"], slug)["stats"]["full"]["bh"] or {}).get("sharpe") or -9))
                chips = "".join(f'<a href="{h(self.pair_path(t, s))}">{e(t["short"])}{pill(self.r(t["sym"], slug)["state"])}</a>' for t in best)
                extra += f"""<section><div class="sec-head"><h2 class="h2">{e(s['long'])}</h2><a class="btn" href="{h('strategies/' + slug + '/')}">Full record</a></div>
<div class="tiles">
<div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">{sm['calls']:,} closed calls on {sm['n']} stocks.</span></div>
<div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['n']}</span><span class="tile-note">On raw return: {sm['beat_cagr']} of {sm['n']}.</span></div>
<div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
</div>
<p class="muted small">Every stock, best risk-adjusted result first:</p><div class="chips">{chips}</div></section>"""
        body = f"""
<nav class="crumbs"><a href="{h('thinkers/')}">Thinkers</a><span>/</span><span>{e(th['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(th['role'])}</p><h1 class="h1">{e(th['name'])}</h1><p class="lede">{e(th['bio'])}</p></section>
<section class="split"><div class="card prose"><p class="eyebrow">What they argue</p><ul>{argues}</ul></div>
<div class="card prose"><p class="eyebrow">Sources</p><div class="sources">{srcs}</div>
<p class="muted small">Summaries are Quiplee's paraphrase of public material. Quiplee has no affiliation with the people listed.</p></div></section>
{extra}
"""
        self.add(path, self.shell(path, th["name"], f"{th['name']}, {th['role']}: the rule, how it has scored on {len(TICKERS)} stocks, and what it says now.", body, active="thinkers/"))

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
        for g in GROUP_ORDER:
            cards = ""
            for t in [x for x in TICKERS if x["group"] == g]:
                k, n = self.consensus(t)
                x = self.r(t["sym"], "buy-and-hold")
                y1 = self.one_year(t)
                cards += (f'<a class="card stock-card" href="{h("stocks/" + t["slug"] + "/")}"><div class="top"><span class="sym">{e(t["short"])}</span>'
                          f'<span class="px">{money(x["price"], t["cur"])}</span></div><span class="muted small">{e(t["name"])} · 1 yr <span class="{dir_cls(y1)}">{pct(y1)}</span></span>'
                          f'{self.meter(k, n)}</a>')
            secs += f'<section><h2 class="h2">{e(g)}</h2><div class="grid grid-4">{cards}</div></section>'
        body = f"""
<section class="pair-head"><p class="eyebrow">Stocks</p><h1 class="h1">{len(TICKERS)} stocks, ETFs and coins</h1>
<p class="lede">Open any name to see every rule's call on it, the level that flips each one, and how each rule has done on it since 2005.</p></section>
{secs}"""
        self.add(path, self.shell(path, "Stocks", "Every stock, ETF and coin Quiplee covers, with how many rules hold it right now.", body, active="stocks/"))

    def stock_page(self, t):
        path, depth = f"stocks/{t['slug']}/", 2
        h = lambda x: self.href(depth, x)
        bh = self.r(t["sym"], "buy-and-hold")
        k, n = self.consensus(t)
        rows = ""
        for s in TIMED:
            x = self.r(t["sym"], s["slug"])
            nm = next_move(x, s, t)
            since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
            nxt = (f'{"Exit below" if x["state"] == 1 else "Enter above"} {money(nm["level"], t["cur"])} <span class="muted">({pct(nm["dist"])})</span>'
                   if nm["level"] is not None else '<span class="muted">Structure not in place</span>')
            a, b = x["stats"]["full"]["strat"], x["stats"]["full"]["bh"]
            band = '<span class="band-mark" title="Inside the band"></span>' if x["trigger"].get("zone") == "between" else ""
            rows += (f'<tr><td><a href="{h(self.pair_path(t, s))}"><b>{e(s["name"])}</b></a><span class="sym-sub">{e(THINKER[s["thinker"]]["name"])} · {BAR_WORD[s["bar"]]}</span></td>'
                     f'<td>{pill(x["state"])}{band}</td><td class="nowrap">{dlong(x["since"])} <span class="{dir_cls(since_move)}">{pct(since_move)}</span></td>'
                     f'<td class="nowrap" data-v="{sortv(None if nm["dist"] is None else abs(nm["dist"]))}">{nxt}</td><td class="r nowrap">{pct(a["cagr"])} <span class="muted">/ {pct(b["cagr"])}</span></td>'
                     f'<td class="r nowrap">{pct(a["maxdd"])} <span class="muted">/ {pct(b["maxdd"])}</span></td></tr>')
        b = bh["stats"]["full"]["bh"]
        rows += (f'<tr><td><a href="{h("strategies/buy-and-hold/")}"><b>Buy &amp; Hold</b></a><span class="sym-sub">John C. Bogle · benchmark</span></td>'
                 f'<td>{pill(1)}</td><td class="nowrap">{dlong(bh["stats"]["start"])}</td><td class="muted">Always in</td>'
                 f'<td class="r">{pct(b["cagr"])}</td><td class="r">{pct(b["maxdd"])}</td></tr>')
        spec = price_spec(bh, STRATEGY["buy-and-hold"], t, with_rule=False)
        chart = chart_block("px-" + t["slug"], spec, "", f"{e(t['short'])} over the last three years")
        others = "".join(f'<a href="{h("stocks/" + o["slug"] + "/")}">{e(o["short"])}</a>' for o in TICKERS if o["sym"] != t["sym"])
        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><span>{e(t['short'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(t['group'])}</p><h1 class="h1">{e(t['name'])} <span class="muted">({e(t['short'])})</span></h1>
<div class="byline"><span class="mono" style="color:var(--ink);font-size:18px">{money(bh['price'], t['cur'])}</span><span>close {dlong(bh['asof'])}</span><span>·</span>{self.meter(k, n)}</div></section>
{chart}
<section><div class="sec-head"><h2 class="h2">Every rule on {e(t['short'])}</h2><p>Record columns: rule / buy and hold, annual return and worst drawdown since {bh['stats']['start'].year}.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th class="r">Annual return</th><th class="r">Worst drawdown</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2 class="h3">Other stocks</h2><div class="chips">{others}</div></section>
"""
        self.add(path, self.shell(path, f"{t['name']} ({t['short']}) · every rule's call", f"What {len(TIMED)} published trading rules say about {t['name']} ({t['short']}) now, the exact levels that flip them, and how each has done since {bh['stats']['start'].year}.", body, active="stocks/"))

    # -------------------------------------------------------------- pair
    def pair_page(self, t, s):
        path, depth = self.pair_path(t, s), 3
        h = lambda x: self.href(depth, x)
        x = self.r(t["sym"], s["slug"])
        th = THINKER[s["thinker"]]
        nm = next_move(x, s, t)
        cur = t["cur"]
        since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
        st_word = "in" if x["state"] == 1 else "out"
        state_line = (f"holds {t['short']}" if x["state"] == 1 else "sits in T-bills")

        # verdict + next move
        level_html = ""
        if nm["level"] is not None:
            level_html = (f'<div><span class="level">{money(nm["level"], cur)}</span></div>'
                          f'<span class="level-sub">{pct(nm["dist"])} from the {dshort(x["asof"])} close of {money(x["price"], cur)}</span>')
        checks_html = ""
        if nm["checks"]:
            checks_html = '<ul class="checks">' + "".join(
                f'<li><span class="{"ok" if ok else "no"}">{"✓" if ok else "✕"}</span>{e(lab)}</li>' for lab, ok in nm["checks"]) + "</ul>"
        notes = "".join(f'<p class="muted small">{e(n_)}</p>' for n_ in nm["notes"])
        alert = f'<p class="alert-line">{e(nm["alert"])}</p>' if nm["alert"] else ""
        verdict = f"""<section class="verdict">
<div class="card"><p class="eyebrow">What the rule says</p>
<div class="byline">{pill(x['state'], lg=True)}<span class="big" style="color:var(--ink)">The rule {state_line}.</span></div>
<div class="facts"><span>{"In" if x['state'] == 1 else "Out"} since <b>{dlong(x['since'])}</b></span><span>at <b>{money(x['since_price'], cur)}</b></span><span>{t['short']} since then <b class="{dir_cls(since_move)}">{pct(since_move)}</b></span></div>
{checks_html}</div>
<div class="card next-card"><p class="eyebrow">Next move</p><p class="h3" style="font-size:17px;line-height:1.45">{e(nm['headline'])}</p>
{level_html}{alert}{notes}<p class="muted small">{e(nm['check'])}</p></div>
</section>"""

        # charts
        keys = [key_line("--s-price", t["short"])]
        lines = list(x["window"]["lines"].keys())
        if s["kind"] == "template":
            lines = ["50-day SMA", "200-day SMA"]
        for lab, var in zip(lines, ["--s1", "--s2"]):
            keys.append(key_line(var, lab))
        keys += [key_wash("in", "Rule in"), key_wash("out", "Rule out")]
        pchart = chart_block("px", price_spec(x, s, t), "".join(keys), f"{e(t['short'])} with the rule, last three years",
                             "Shading shows the rule's call from the close that triggered it. 150-day average omitted for clarity." if s["kind"] == "template" else None)
        eq = equity_spec(x, s, t)
        echart = chart_block("eq", eq, key_line("--s1", s["name"]) + key_line("--s-bench", "Buy & hold"),
                             f"Growth of {cur}10,000 since {x['stats']['start'].year}", "Log scale. After trading costs, with T-bill interest while out.")

        # stats table
        st = x["stats"]

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
        stats_tbl = (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th></th><th class="r">Rule, since {st["start"].year}</th><th class="r">Buy &amp; hold</th>'
                     f'<th class="r">Rule, 5 yrs</th><th class="r">Buy &amp; hold</th></tr></thead><tbody>{rows}</tbody></table></div>')

        # calls
        bat = x["batting"]
        calls = x["calls"][-14:][::-1]
        crow = ""
        for c in calls:
            res = ('<span class="muted">open</span>' if not c["closed"] else
                   ('<span class="up">✓ right</span>' if c["right"] else '<span class="down">✕ wrong</span>'))
            crow += (f'<tr><td class="nowrap">{dlong(c["date"])}</td><td>{pill(c["state"])}</td><td class="r">{money(c["price"], cur)}</td>'
                     f'<td class="nowrap" data-v="{pd.Timestamp(c["end"]).strftime("%Y-%m-%d")}">{dlong(c["end"]) if c["closed"] else "now"}</td>'
                     f'<td class="r {dir_cls(c["move"])}">{pct(c["move"])}</td><td data-v="{(1 if c["right"] else 0) if c["closed"] else ""}">{res}</td></tr>')
        bat_line = (f'Right on <b>{bat["right"]}</b> of <b>{bat["n"]}</b> closed calls ({pct(bat["avg"], sign=False, d=0)}). '
                    f'In calls averaged {pct(bat["in_avg"])}; out calls saw {t["short"]} move {pct(bat["out_avg"])} on average.') if bat["n"] else "No closed calls yet."
        calls_sec = f"""<section><div class="sec-head"><h2 class="h2">Every call, graded</h2><p>{bat_line}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Called</th><th>Call</th><th class="r">Price</th><th>Until</th><th class="r">{e(t['short'])} moved</th><th>Result</th></tr></thead><tbody>{crow}</tbody></table></div>
<p class="muted small">An in call is right when the price rose before the next call; an out call is right when it fell. The latest {min(14, len(x['calls']))} of {len(x['calls'])} calls shown.</p></section>"""

        other_rules = "".join(f'<a href="{h(self.pair_path(t, o))}">{e(o["name"])}{pill(self.r(t["sym"], o["slug"])["state"])}</a>' for o in TIMED if o["slug"] != s["slug"])
        other_stocks = "".join(f'<a href="{h(self.pair_path(o, s))}">{e(o["short"])}{pill(self.r(o["sym"], s["slug"])["state"])}</a>' for o in TICKERS if o["sym"] != t["sym"])
        flag = f' <span class="tag warn">{e(s["flag"])}</span>' if s.get("flag") else ""

        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><a href="{h('stocks/' + t['slug'] + '/')}">{e(t['short'])}</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(BAR_WORD[s['bar']])} rule · {e(t['group'])}</p>
<h1 class="h1">{e(s['name'])} on {e(t['name'])}</h1>
<div class="byline">Rule from <a href="{h('thinkers/' + th['slug'] + '/')}">{e(th['name'])}</a><span>·</span><a href="{h('strategies/' + s['slug'] + '/')}">How it works</a>{flag}</div></section>
{verdict}
{pchart}
{echart}
<section><div class="sec-head"><h2 class="h2">The record</h2><p>The rule against buying and holding {e(t['short'])} over exactly the same dates, after costs.</p></div>{stats_tbl}</section>
{calls_sec}
<section class="split">{self.rule_card(s)}{self.against_card(depth)}</section>
<section><h2 class="h3">Other rules on {e(t['short'])}</h2><div class="chips">{other_rules}</div></section>
<section><h2 class="h3">{e(s['name'])} on other stocks</h2><div class="chips">{other_stocks}</div></section>
"""
        title = f"{s['name']} on {t['short']}: the rule says {st_word}"
        desc = f"{th['name']}'s {s['long']} applied to {t['name']} ({t['short']}) since {st['start'].year}: {st_word} since {dlong(x['since'])}. {nm['headline']}"
        self.add(path, self.shell(path, title, desc, body, active="stocks/"))

    # ------------------------------------------------------------ method
    def method_page(self):
        path, depth = "method/", 1
        h = lambda x: self.href(depth, x)
        body = f"""
<section class="pair-head"><p class="eyebrow">Method</p><h1 class="h1">How Quiplee tests a rule</h1>
<p class="lede">The same test for every rule and every stock, written down so anyone can check it.</p></section>
<section class="split">
<div class="card prose"><p class="eyebrow">Data</p><ul>
<li>Daily closing prices adjusted for splits and dividends, from Yahoo Finance, since January 2004. Grading starts in January 2005, or once a stock has enough history for the rule.</li>
<li>Cash earns the 13-week U.S. Treasury bill yield (^IRX). Canadian names use the same rate, which slightly flatters or penalises them.</li>
<li>Every signal uses finished bars only. Today's price is ignored until the market has closed, and weekly or monthly rules wait for the week or month to end.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">Execution and costs</p><ul>
<li>A call made on a close is acted on at the next session.</li>
<li>Each switch in or out costs 0.05% (0.10% for crypto).</li>
<li>No leverage, no shorting, no taxes. The time-series momentum rule is tested long-only.</li>
</ul></div>
</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Grading</p><ul>
<li><b>Calls right:</b> an in call is right if the price was higher when the next call came; an out call is right if it was lower. Open calls are not graded.</li>
<li><b>Annual return, worst drawdown, volatility:</b> computed on the rule's daily returns, including T-bill interest while out.</li>
<li><b>Sharpe ratio:</b> average return above T-bills divided by volatility, annualised.</li>
<li>Every rule is compared with buying and holding the same stock over exactly the same dates.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">The next move</p><ul>
<li>The level shown is the exact close that would flip the rule on its next check, solved from the moving-average formulas with that close included.</li>
<li>For an exponential average the flip level is today's average. For a simple average of n bars it is the average of the most recent n − 1 closes.</li>
<li>Daily rules check every close. Weekly rules check the Friday close (Sunday for crypto). Monthly rules check the last close of the month.</li>
</ul></div>
</section>
<section class="card prose"><p class="eyebrow">What this is not</p>
<p>Quiplee reports what a published rule says. It does not know your goals, taxes or other holdings, and it is not financial advice. Past results come from a backtest on stocks that are still listed today, which flatters every rule and buy and hold alike. Summaries of each thinker's views are Quiplee's paraphrase of public material, and Quiplee has no affiliation with them.</p>
<p>Rebuilt automatically after each U.S. market close. <a href="{h('strategies/')}">See every rule</a> or <a href="{h('thinkers/valeriy-zakamulin/')}">the case against timing</a>.</p></section>
"""
        self.add(path, self.shell(path, "Method", "How Quiplee tests every trading rule: data, execution, costs, grading and the next-move math.", body, active="method/"))

    # ------------------------------------------------------------ exports
    def signals_json(self):
        out = []
        for t in TICKERS:
            for s in STRATEGIES:
                x = self.r(t["sym"], s["slug"])
                out.append({"sym": t["sym"], "strategy": s["slug"], "thinker": s["thinker"], "state": x["state"],
                            "since": x["since"].strftime("%Y-%m-%d") if x["since"] is not None else None,
                            "exit": x["trigger"].get("exit"), "enter": x["trigger"].get("enter"),
                            "next_check": x["next_check"].strftime("%Y-%m-%d"), "price": x["price"],
                            "asof": x["asof"].strftime("%Y-%m-%d")})
        return json.dumps({"asof": self.asof.strftime("%Y-%m-%d"), "signals": out}, indent=1)

    def sitemap(self):
        urls = "".join(f"  <url><loc>{BASE}{p}</loc><lastmod>{self.asof.strftime('%Y-%m-%d')}</lastmod></url>\n"
                       for p in sorted(list(self.pages.keys()) + ["desk/", "stories/", "stories/the-hertz-lesson.html"]))
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
