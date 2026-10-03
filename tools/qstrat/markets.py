"""/markets/: the plays and the crash gauges at the level of whole markets.

Same lenses as a stock page, one level up: what the plays say about each index
and sector, nine gauges that have mattered before past crashes, how today
compares with the last four market tops, which covered names would likely feel
a crash first, and an interactive look at cash vs staying invested vs buckets.
"""
import html
import json
import math

import pandas as pd

from . import macro
from . import stockview as sv
from .content import TICKERS, TIMED

e = html.escape
STATUS_WORD = {"calm": "Calm", "watch": "Watch", "warning": "Warning"}


def _js(obj):
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


def _num(v, n=4):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else float(f"{v:.{n}g}")


def classify(key, v):
    """Status of an arbitrary reading on a gauge's own thresholds (for the past-peaks table)."""
    if v is None:
        return ""
    rules = {
        "trend": lambda x: "warning" if x < 0 else "watch" if x < 0.03 else "calm",
        "cape": lambda x: "warning" if x >= 35 else "watch" if x >= 25 else "calm",
        "runup": lambda x: "warning" if x >= 1 else "watch" if x >= 0.5 else "calm",
        "concentration": lambda x: "warning" if x < -0.15 else "watch" if x < -0.05 else "calm",
        "vix": lambda x: "warning" if x >= 30 else "watch" if x >= 22 else "calm",
        "curve": lambda x: "warning" if x < 0 else "watch" if x < 0.5 else "calm",
        "credit": lambda x: "warning" if x >= 3 else "watch" if x >= 2.3 else "calm",
        "sahm": lambda x: "warning" if x >= 0.5 else "watch" if x >= 0.3 else "calm",
        "rates": lambda x: "warning" if x >= 5 else "watch" if x >= 4.5 else "calm",
    }
    return rules[key](v) if key in rules else ""


def fmt_val(g, v):
    if v is None:
        return "–"
    f = g["fmt"]
    if f == "pct":
        return ("−" if v < 0 else "+" if v > 0 and g["key"] in ("trend", "runup", "concentration") else "") + f"{abs(v) * 100:.0f}%"
    if f == "pp":
        return ("−" if v < 0 else "+") + f"{abs(v):.2f}"
    if f == "pctpt":
        return f"{v:.2f}%"
    return f"{v:.1f}"


def gauge_spec(g, recessions):
    s = g["series"]
    if s is None or not len(s):
        return None
    s = s.dropna()
    t0 = s.index[0]
    d = [int((x - t0).days) for x in s.index]
    spec = {"t0": t0.strftime("%Y-%m-%d"), "d": d, "monthly": True, "label": f"{g['name']}, monthly",
            "series": [{"name": g["name"], "role": "s1", "v": [_num(v) for v in s.values]}],
            "levels": [float(x) for x in g["levels"]], "shadeLabel": "U.S. recession"}
    if g["fmt"] == "pct":
        spec["fmt"] = "pct"
    elif g["fmt"] in ("pp", "pctpt"):
        spec.update(fmt="dec", dp=1 if g["fmt"] == "pctpt" else 1, unit="%" if g["fmt"] == "pctpt" else "")
    else:
        spec.update(fmt="dec", dp=0)
    idx = s.index
    shade = []
    for a, b in recessions:
        if b < idx[0] or a > idx[-1]:
            continue
        i0 = int(idx.searchsorted(a))
        i1 = int(min(len(idx) - 1, idx.searchsorted(b)))
        shade.append([i0, i1])
    spec["shade"] = shade
    pins = []
    for lab, dte in macro.PEAKS:
        ts = pd.Timestamp(dte)
        if idx[0] <= ts <= idx[-1]:
            pins.append([int(min(len(idx) - 1, idx.searchsorted(ts))), {"Dot-com peak": "2000", "Pre-financial-crisis peak": "2007",
                                                                       "Pre-COVID peak": "2020", "Pre-2022 peak": "2022"}[lab]])
    spec["pins"] = pins
    return spec


def summary_sentence(M):
    by = {g["key"]: g for g in M["gauges"]}
    warn = [g["name"].split(" (")[0].lower() for g in M["gauges"] if g["status"] == "warning"]
    calm = [g["name"].split(" (")[0].lower() for g in M["gauges"] if g["status"] == "calm"]

    def join(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    c = M["counts"]
    out = f"{c['warning']} of {len(M['gauges'])} gauges flash a warning, {c['watch']} say watch and {c['calm']} are calm."
    if warn:
        out += f" Warnings: {join(warn)}."
    if calm:
        out += f" Calm: {join(calm)}."
    return out


def market_rows(site, tickers, depth):
    h = lambda x: site.href(depth, x)
    core = [p for p in TIMED if p.get("core")]
    rows = ""
    for t in tickers:
        x = site.R.get((t["sym"], "buy-and-hold"))
        meta = site.meta.get(t["sym"]) or {}
        if x is None or meta.get("ohlc") is None:
            continue
        c = meta["ohlc"]["close"]
        day = float(c.iloc[-1] / c.iloc[-2] - 1) if len(c) > 1 else None
        gap = float(c.iloc[-1] / c.iloc[-200:].mean() - 1) if len(c) >= 200 else None
        y1 = site.one_year(t)
        kc, nc = site.consensus(t, core)
        k, n = site.consensus(t)
        rk = meta.get("risk") or {}
        lvl = rk.get("level")
        from .render import money, pct, sortv, count_in, dir_cls
        label = t.get("sector") or t["name"]
        rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(label)}</span></td>'
                 f'<td class="r mono">{money(x["price"], t["cur"])}</td>'
                 f'<td class="r {dir_cls(day)}" data-v="{sortv(day)}">{pct(day)}</td>'
                 f'<td class="r {dir_cls(y1)}" data-v="{sortv(y1)}">{pct(y1, d=0)}</td>'
                 f'<td class="r {dir_cls(gap)}" data-v="{sortv(gap)}">{pct(gap, d=0)}</td>'
                 f'<td data-v="{kc / nc if nc else ""}">{count_in(kc, nc)}</td>'
                 f'<td class="r" data-v="{k / n if n else ""}">{k}/{n}</td>'
                 f'<td class="r" data-v="{sortv(rk.get("runup2y"))}">{pct(rk.get("runup2y"), d=0)}</td>'
                 f'<td data-v="{rk.get("score", "")}">' + (f'<span class="lvl lvl-{sv.LEVEL_CLASS[lvl]}">{e(lvl)}</span>' if lvl else "–") + "</td></tr>")
    return rows


def market_table(rows):
    return (f'<div class="tbl-wrap"><table class="tbl mkt-tbl"><thead><tr><th>Market</th><th class="r">Level</th><th class="r">Day</th><th class="r">1 year</th>'
            f'<th class="r">vs 200-day</th><th>Core plays in</th><th class="r">All plays</th><th class="r">2-yr run-up</th><th>Crash exposure</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


SCENARIOS = [
    {"key": "gfc", "label": "2008: bought at the October 2007 peak", "from": "2007-11", "to": "2012-12"},
    {"key": "covid", "label": "2020: bought at the February 2020 peak", "from": "2020-03", "to": "2021-08"},
    {"key": "y2022", "label": "2022: bought at the January 2022 peak", "from": "2022-01", "to": "2024-06"},
    {"key": "all", "label": "Everything since 2005", "from": "2005-01", "to": None},
    {"key": "last5", "label": "The last five years", "from": None, "to": None},
]
MIXES = [
    {"label": "All stocks", "mix": {"stocks": 100, "bonds": 0, "gold": 0, "cash": 0}},
    {"label": "60/40", "mix": {"stocks": 60, "bonds": 40, "gold": 0, "cash": 0}},
    {"label": "Three buckets", "mix": {"stocks": 60, "bonds": 25, "gold": 0, "cash": 15}},
    {"label": "Cautious", "mix": {"stocks": 40, "bonds": 30, "gold": 10, "cash": 20}},
    {"label": "All cash", "mix": {"stocks": 0, "bonds": 0, "gold": 0, "cash": 100}},
]


def sim_block(cid="sim"):
    P = macro.positioning_data()
    scen = []
    for sc in SCENARIOS:
        sc = dict(sc)
        if sc["key"] == "last5":
            sc["from"] = P["dates"][-60]
        scen.append(sc)
    P.update(scenarios=scen, mixes=MIXES)
    return (f'<div class="card sim-card"><div class="sim" data-sim="{cid}"></div><script type="application/json" id="{cid}">{_js(P)}</script>'
            f'<p class="chart-note">Monthly total returns: SPY for stocks, TLT for long Treasury bonds, GLD for gold, 13-week T-bills for cash. '
            f'No taxes or fees. "Rebalance yearly" resets the mix every 12 months. The 10-month rule is <a href="{{rule}}">Meb Faber\'s play</a>, '
            f'checked at each month-end. Past paths, not a forecast.</p></div>')


def best_days_block():
    B = macro.best_days()
    base = B["rows"][0][1]
    mx = max(v for _, v in B["rows"])
    rows = ""
    for lab, v in B["rows"]:
        w = 100 * v / mx
        rows += (f'<div class="bd-row"><span class="bd-lab">{e(lab)}</span><span class="bd-track"><i class="{"base" if v == base else ("more" if v > base else "less")}" style="width:{w:.1f}%"></i></span>'
                 f'<b>${v:,.0f}</b></div>')
    return B, (f'<div class="card bd-card"><p class="eyebrow">$10,000 in the S&amp;P 500 (SPY), {B["start"].strftime("%b %Y")} to {B["end"].strftime("%b %Y")}</p>'
               f'<div class="bd">{rows}</div>'
               f'<p class="small">Of the 20 best days, <b>{B["best20_in_bear"]}</b> came while the market was in a bear market (20% or more below its high), and '
               f'<b>{B["best20_near_worst"]}</b> came within two weeks of one of the 20 worst days. The days you would most want to miss and the days you can least afford to miss arrive together.</p></div>')


def markets_page(site):
    path, depth = "markets/", 1
    h = lambda x: site.href(depth, x)
    from .render import pct, ratio, count_in, sortv
    plays_in = {t["sym"]: site.consensus(t) for t in TICKERS if t.get("index")}
    M = macro.build(plays_in=plays_in)
    site.macro = M
    gs = M["gauges"]
    weather_cls = {"Calm": "calm", "Mostly calm": "calm", "Unsettled": "watch", "Stormy": "warning"}[M["weather"]]

    chips = "".join(f'<a class="gchip {g["status"]}" href="#g-{g["key"]}"><i></i><span>{e(g["name"])}</span><b>{fmt_val(g, g["value"])}</b></a>' for g in gs)

    idx = [t for t in TICKERS if t.get("index")]
    sectors = [t for t in TICKERS if t["group"] == "Sectors"]
    sectors.sort(key=lambda t: -((site.meta.get(t["sym"], {}).get("risk") or {}).get("runup2y") or -9))

    cards = ""
    for g in gs:
        spec = gauge_spec(g, M["recessions"])
        cid = "gc-" + g["key"]
        chart = ""
        if spec:
            chart = (f'<div class="chart chart-sm" data-chart="{cid}" aria-label="{e(spec["label"])}"></div>'
                     f'<script type="application/json" id="{cid}">{_js(spec)}</script>')
        peaks = "".join(f'<li><span>{e(lab.replace("Pre-financial-crisis", "2007").replace("Pre-COVID", "2020").replace("Pre-2022", "2022").replace("Dot-com", "2000"))}</span>'
                        f'<b class="st-{classify(g["key"], v)}">{fmt_val(g, v)}</b></li>' for lab, v in g["peaks"].items())
        src = " · ".join(f'<a href="{e(u)}" rel="noopener" target="_blank">{e(lab)}</a>' for lab, u in g["source"])
        cards += f"""<article class="card gauge {g['status']}" id="g-{g['key']}">
<div class="g-top"><div><p class="eyebrow">{e(g['question'])}</p><h3 class="h3">{e(g['name'])}</h3></div>
<div class="g-val"><span class="g-status {g['status']}">{STATUS_WORD[g['status']]}</span><b>{fmt_val(g, g['value'])}</b></div></div>
<p class="g-reading">{e(g['reading'])}</p>
{chart}
<ul class="g-peaks"><li class="lab">At past tops</li>{peaks}<li><span>Now</span><b class="st-{g['status']}">{fmt_val(g, g['value'])}</b></li></ul>
<details><summary>Why it matters</summary><p>{e(g['why'])}</p><p class="small muted">Sources: {src}</p></details>
</article>"""

    # past tops table
    peak_cols = [("2000", "Dot-com peak"), ("2007", "Pre-financial-crisis peak"), ("2020", "Pre-COVID peak"), ("2022", "Pre-2022 peak")]
    trows = ""
    for g in gs:
        cells = "".join(f'<td class="c"><span class="st-cell st-{classify(g["key"], g["peaks"].get(k))}">{fmt_val(g, g["peaks"].get(k))}</span></td>' for _, k in peak_cols)
        trows += (f'<tr><td><a href="#g-{g["key"]}">{e(g["name"])}</a></td>{cells}'
                  f'<td class="c"><span class="st-cell st-{g["status"]} now">{fmt_val(g, g["value"])}</span></td></tr>')
    lit = {k: sum(1 for g in gs if classify(g["key"], g["peaks"].get(k)) == "warning") for _, k in peak_cols}
    lit_row = "".join(f'<td class="c"><b>{lit[k]}</b></td>' for _, k in peak_cols)
    tops = f"""<div class="tbl-wrap"><table class="tbl tops" data-nosort><thead><tr><th>Gauge</th>{''.join(f"<th class='c'>{y} top</th>" for y, _ in peak_cols)}<th class="c">Now</th></tr></thead>
<tbody>{trows}<tr class="sumrow"><td>Warnings lit</td>{lit_row}<td class="c"><b>{M['counts']['warning']}</b></td></tr></tbody></table></div>"""

    # who feels a crash first (covered equities)
    eq = [t for t in site.universe if not t.get("index") and not t["crypto"] and t["group"] not in ("Indexes & ETFs", "Sectors")
          and (site.meta.get(t["sym"]) or {}).get("risk")]
    eq.sort(key=lambda t: (-site.meta[t["sym"]]["risk"]["score"], t["short"]))
    core = [p for p in TIMED if p.get("core")]
    crows = ""
    for t in eq[:15]:
        rk = site.meta[t["sym"]]["risk"]
        kc, nc = site.consensus(t, core)
        crows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}#crash">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                  f'<td data-v="{rk["score"]}"><span class="lvl lvl-{sv.LEVEL_CLASS[rk["level"]]}">{e(rk["level"])}</span> <span class="muted">{rk["score"]}/10</span></td>'
                  f'<td class="r" data-v="{sortv(rk.get("beta"))}">{ratio(rk.get("beta"))}</td>'
                  f'<td class="r" data-v="{sortv(rk.get("runup2y"))}">{pct(rk.get("runup2y"), d=0)}</td>'
                  f'<td data-v="{kc}">{count_in(kc, nc)}</td><td class="small muted why-col">{e("; ".join((rk.get("why") or [])[:2]))}</td></tr>')

    B, bd = best_days_block()
    sim = sim_block().replace("{rule}", h("strategies/ten-month-sma/"))
    by = {g["key"]: g for g in gs}
    tst = by.get("trend", {}).get("status")
    trend_line = {"calm": "The trend is still up, and the trend is what has historically confirmed that a fall has actually begun.",
                  "watch": "The index is still above its long average, but fewer plays agree than usual: the trend is up, not unanimous.",
                  "warning": "The trend has broken: the index is below its long average or most plays have stepped aside, which is how past falls announced themselves."}.get(tst, "")

    body = f"""
<section class="pair-head"><p class="eyebrow">Markets · closes to {M['asof'].strftime('%b %-d, %Y')}</p>
<h1 class="h1">Market weather: <span class="wx {weather_cls}">{e(M['weather'])}</span></h1>
<p class="lede">{e(summary_sentence(M))} {trend_line}</p>
<div class="gchips">{chips}</div>
<p class="muted small">Nine gauges that mattered before past crashes. None times a crash on its own: markets can stay expensive for years. They describe how stretched and how fragile things are. <a href="{h('articles/is-this-a-bubble/')}">Read: is this a bubble?</a></p>
</section>

<section aria-labelledby="idx-h"><div class="sec-head"><h2 class="h2" id="idx-h">The plays on whole markets</h2>
<p>The same {len(TIMED)} plays that run on every stock, run on the indexes. Open one for its chart, every call and the names most exposed to a crash.</p></div>
{market_table(market_rows(site, idx, depth))}
<div class="sec-head"><h3 class="h3">Sectors, hottest two years first</h3><p>U.S. sector funds. A two-year run-up of 100% or more is the bubble line in Greenwood, Shleifer &amp; You's research.</p></div>
{market_table(market_rows(site, sectors, depth))}
</section>

<section aria-labelledby="g-h"><div class="sec-head"><h2 class="h2" id="g-h">Crash watch: the nine gauges</h2>
<p>Monthly history with U.S. recessions shaded and the last four market tops marked. Tap a chart to read any month.</p></div>
<div class="gauges">{cards}</div></section>

<section aria-labelledby="tops-h"><div class="sec-head"><h2 class="h2" id="tops-h">Today against the last four tops</h2>
<p>Each gauge's reading on the day the S&amp;P 500 peaked before the dot-com bust, the financial crisis, COVID and 2022, coloured by the same thresholds used today.</p></div>
{tops}
<p class="muted small">No two tops looked alike. 2000 was about valuation; 2007 about credit; 2020 was a shock nothing on this list could see; 2022 was rates. The point is not to match a pattern but to see which kinds of fragility are present now.</p></section>

<section aria-labelledby="ex-h"><div class="sec-head"><h2 class="h2" id="ex-h">Who would feel a crash first</h2>
<p>The covered stocks with the highest crash exposure: how hard they swing with the market, how they fared in past crashes, their debt and their run-up. This is the storm test: shocks hurt most where debt is heavy.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th data-sort-first="desc">Exposure</th><th class="r">Beta</th><th class="r">2-yr change</th><th>Core plays in</th><th>Why</th></tr></thead><tbody>{crows}</tbody></table></div>
<p class="muted small">Every stock page has its full crash card. Index pages list every covered name on that market. <a href="{h('articles/debt-and-crashes/')}">How the storm test works</a></p></section>

<section aria-labelledby="pos-h" id="positioning"><div class="sec-head"><h2 class="h2" id="pos-h">Cash, stay in, or buckets?</h2>
<p>What different choices would have done through real crashes. Pick a period, a mix and a plan. Educational, not advice: the right mix depends on when you need the money.</p></div>
{sim}
<div class="grid grid-3 buckets">
<div class="card prose"><p class="eyebrow">Bucket 1 · cash</p><p class="h3" style="color:var(--ink)">What you'll spend in the next year or two</p><p>Held in savings or T-bills, so a crash never forces you to sell stocks at the bottom to pay the bills.</p></div>
<div class="card prose"><p class="eyebrow">Bucket 2 · bonds</p><p class="h3" style="color:var(--ink)">Money for years three to seven</p><p>Steadier than stocks and usually earning more than cash. Refills bucket 1 when stocks are down.</p></div>
<div class="card prose"><p class="eyebrow">Bucket 3 · stocks</p><p class="h3" style="color:var(--ink)">Money you won't touch for years</p><p>Left to ride out crashes, which have historically recovered given time. Trimmed into the other buckets after good years.</p></div>
</div>
<p class="muted small">The bucket approach is a planning habit popularised by financial planner Harold Evensky. It doesn't make crashes smaller; it makes them survivable, because nothing you need soon is in stocks.</p>
<div class="sec-head"><h3 class="h3">The cost of jumping out</h3><p>Selling to wait out a storm means guessing twice: when to leave and when to come back.</p></div>
{bd}
</section>
"""
    site.add(path, site.shell(path, "Markets · crash watch and the plays on whole markets",
                              f"Market weather: {M['weather']}. Nine crash gauges with history, the plays on the S&P 500, Nasdaq-100, Dow, Russell 2000, TSX and sectors, who would feel a crash first, and cash vs invested vs buckets.",
                              body, active="markets/", scripts=("assets/widgets.js",)))
    return M
