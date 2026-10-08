"""/weekly/: the week's market weather, on the web and by email.

One page a week's worth of news: the crash gauges, what the plays say about the
S&P 500, and the names whose Start/Stop light flipped in the last seven days
(with a Canadian list of its own). The same content goes out as the free
Saturday email (netlify/functions/weekly-weather.mjs) from data/weather.json,
which this module also writes. Readers sign up on this page or on /alerts/.
"""
import html
import json

import pandas as pd

from .content import TICKERS
from .render import DISCLAIMER, dlong, money, pct, dir_cls, light_badge
from .screen import rows as screen_rows, crash_card

e = html.escape
DAYS = 7
TOP = 8

ANSWER = {"Calm": "Not on these gauges. None is flashing a warning.",
          "Mostly calm": "Not on most of these gauges, though a couple run hot.",
          "Unsettled": "Some warning lights are on. That is not a crash signal, and it isn't an all-clear.",
          "Stormy": "Several warning lights are on at once, including the price trend."}


def _flips(site):
    """Names whose light flipped in the last DAYS days, strongest agreement first."""
    by_sym = {t["sym"]: t for t in TICKERS}
    start, stop = [], []
    for r in screen_rows(site):
        t = by_sym.get(r["sym"])
        if not t or t.get("index") or t.get("requested") or r["L"] is None or not r["since"] or not r["o"]:
            continue
        if (site.asof - pd.Timestamp(r["since"])).days > DAYS:
            continue
        (start if r["L"] == 1 else stop).append(r)
    start.sort(key=lambda r: (-r["k"] / r["o"], r["up"] is None, -(r["up"] or 0), r["s"]))
    stop.sort(key=lambda r: (r["k"] / r["o"], r["s"]))
    return start, stop


def data(site):
    """Everything the page and the email need, in one dict (also data/weather.json)."""
    from .markets import fmt_val
    M = site.macro or {}
    start, stop = _flips(site)
    spx = next((t for t in TICKERS if t["sym"] == "^GSPC"), None)
    sp = None
    if spx and (spx["sym"], "buy-and-hold") in site.R:
        L = site.light(spx)
        k, n = site.consensus(spx)
        sp = {"k": k, "n": n, "L": None if not L["state"] else (1 if L["state"] == "start" else 0), "u": spx["slug"]}
    pick = lambda r: {"s": r["s"], "n": r["n"], "u": r["u"], "k": r["k"], "o": r["o"], "c": r["c"], "p": r["p"], "up": r["up"], "since": r["since"], "m": r["m"]}
    return {
        "asof": site.asof.strftime("%Y-%m-%d"),
        "weather": M.get("weather"),
        "answer": ANSWER.get(M.get("weather"), ""),
        "warning": (M.get("counts") or {}).get("warning", 0),
        "watch": (M.get("counts") or {}).get("watch", 0),
        "gauges": [{"name": g["name"], "v": fmt_val(g, g["value"]), "st": g["status"], "key": g["key"]} for g in M.get("gauges", [])],
        "spx": sp,
        "n_start": len(start), "n_stop": len(stop),
        "start": [pick(r) for r in start[:TOP]],
        "stop": [pick(r) for r in stop[:TOP]],
        "ca_start": [pick(r) for r in start if r["m"] == "ca"][:5],
    }


def weather_json(site):
    return json.dumps(data(site), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _list(site, depth, items, side):
    h = lambda x: site.href(depth, x)
    if not items:
        return '<p class="muted">None this week.</p>'
    li = ""
    for r in items:
        up = f' · analysts <span class="{dir_cls(r["up"])}">{pct(r["up"], d=0)}</span>' if r["up"] is not None else ""
        li += (f'<li><a href="{h("stocks/" + r["u"] + "/")}"><b>{e(r["s"])}</b> {e(r["n"])}</a>'
               f'<span class="muted small"> · {r["k"]} of {r["o"]} plays in · {money(r["p"], r["c"])}{up} · flipped {dlong(pd.Timestamp(r["since"]))}</span></li>')
    return f'<ul class="wk-list {side}">{li}</ul>'


def signup_form(h, where):
    """The weekly sign-up: email and an unticked consent box (CASL wants express consent)."""
    return f"""<form class="pt-form wk-form" data-wk-form data-api="/api/alerts/" data-where="{e(where)}" novalidate>
<label>Email<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"></label>
<label class="pt-check"><input type="checkbox" name="consent"> Email me the weekly market weather every Saturday. I can unsubscribe from any email.</label>
<button class="btn primary" type="submit">Send me the weekly</button>
<p class="pt-msg" role="alert" data-wk-msg></p>
<p class="small muted">One email a week, free. Want an email when a stock you follow flips? <a href="{h('alerts/')}">Pick your stocks</a>.</p>
</form>"""


def _card(site, depth):
    """The home page's crash card, without its step number."""
    import re
    return re.sub(r'<span class="step-n">\d+</span>', '', crash_card(site, depth), count=1)


def weekly_page(site):
    path, depth = "weekly/", 1
    h = lambda x: site.href(depth, x)
    D = data(site)
    sp = ""
    if D["spx"]:
        L = site.light(next(t for t in TICKERS if t["sym"] == "^GSPC"))
        sp = (f'<p>The plays on the S&amp;P 500: <a href="{h("stocks/" + D["spx"]["u"] + "/")}"><b>{D["spx"]["k"]} of {D["spx"]["n"]} hold it</b></a> {light_badge(L)}</p>')
    ca = ""
    if D["ca_start"]:
        ca = (f'<section class="card"><h2 class="h3">Canada: turned Start this week</h2>{_list(site, depth, D["ca_start"], "start")}'
              f'<p class="small"><a href="{h("stocks/?group=tsx")}">All TSX stocks</a></p></section>')
    week = dlong(site.asof)
    body = f"""<section class="pair-head"><p class="eyebrow">The weekly · week to {week}</p><h1 class="h1">This week's market weather</h1>
<p class="lede">The crash gauges, what the plays say about the S&amp;P 500, and every stock whose Start/Stop light flipped in the last {DAYS} days. Updated after every close; emailed free on Saturdays.</p></section>
{_card(site, depth)}
<section class="card"><h2 class="h3">Turned Start this week <span class="muted small">({D['n_start']})</span></h2>
<p class="small muted">The light turns Start when 60% or more of the plays hold a stock. Strongest agreement first.</p>
{_list(site, depth, D['start'], 'start')}</section>
<section class="card"><h2 class="h3">Turned Stop this week <span class="muted small">({D['n_stop']})</span></h2>
<p class="small muted">The light turns Stop when the share of plays in falls to 40% or less.</p>
{_list(site, depth, D['stop'], 'stop')}</section>
{ca}
<section class="card"><h2 class="h3">Get this every Saturday</h2>{sp}{signup_form(h, "weekly")}</section>
<p class="muted small">{e(DISCLAIMER)}</p>
"""
    title = f"Market weather this week: {D['weather'] or 'the crash gauges'}, {D['n_start']} stocks turned Start"
    desc = (f"Week to {week}: {D['warning']} of {len(D['gauges'])} crash gauges flash a warning. "
            f"{D['n_start']} stocks turned Start and {D['n_stop']} turned Stop on Be The Puck's 100 trading plays. Free every Saturday by email.")
    site.add(path, site.shell(path, title, desc, body, active="markets/", scripts=("assets/weekly.js",)))
