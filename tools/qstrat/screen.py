"""The home page: one question about the market, then a screener for the plays.

Step 1 answers "is the market about to crash?" from the nine crash gauges (macro.py)
and the plays on the S&P 500. Steps 2 to 4 walk a visitor through a screener of
every covered name: buying or selling, where to look, and how many of the plays
must agree. The first page of results is rendered here so the page works (and
reads well to search engines) before assets/screen.js takes over with
data/screen.json. The filter rules below and in screen.js must match.
"""
import html
import json

import pandas as pd

from .content import TICKERS, TIMED, FAMILIES, GROUP_ORDER
from . import stockview as sv

e = html.escape
RISK = ["Low", "Moderate", "High", "Very high"]
RISK_CLS = ["calm", "watch", "warning", "warning"]
MARKETS = [("", "All"), ("us", "U.S."), ("ca", "Canada"), ("crypto", "Crypto"), ("fund", "Funds & indexes")]
FUND_GROUPS = ("Market indexes", "Sectors", "Indexes & ETFs")
SORTS = [("agree", "Most plays agree"), ("day", "Biggest move today"), ("y1", "Best year"), ("up", "Most analyst upside"),
         ("risk", "Least crash exposure"), ("az", "A to Z")]
DEFAULT_MIN = 60
PAGE = 25
FRESH_DAYS = 7


def market(t):
    if t["crypto"] or t["group"] == "Crypto":
        return "crypto"
    if t.get("index") or t["group"] in FUND_GROUPS:
        return "fund"
    return "ca" if t["cur"] == "C$" else "us"


def rows(site):
    """One dict per covered name, in the shape data/screen.json carries."""
    cache = site.__dict__.get("_screen_rows")
    if cache is not None:
        return cache
    fams = [[p for p in TIMED if p["family"] == k] for k, _, _ in FAMILIES]
    out = []
    for t in TICKERS:
        sym = t["sym"]
        if (sym, "buy-and-hold") not in site.R:
            continue
        x = site.r(sym, "buy-and-hold")
        meta = site.meta.get(sym) or {}
        oh = meta.get("ohlc")
        d1 = float(oh["close"].iloc[-1] / oh["close"].iloc[-2] - 1) if oh is not None and len(oh) > 1 else None
        L = site.light(t)
        k, n = site.consensus(t)
        try:
            y1 = site.one_year(t)
        except Exception:
            y1 = None
        ol = sv.outlook(site, t)
        lvl = (meta.get("risk") or {}).get("level")
        since = L.get("since")
        out.append({
            "sym": sym, "s": t["short"], "n": t["name"], "u": t["slug"], "g": t["group"], "m": market(t), "c": t["cur"],
            "p": round(float(x["price"]), 4), "d": None if d1 is None else round(d1, 4), "y": None if y1 is None else round(float(y1), 4),
            "L": None if not L["state"] else (1 if L["state"] == "start" else 0), "k": k, "o": n,
            "f": [list(site.consensus(t, ps)) for ps in fams],
            "r": RISK.index(lvl) if lvl in RISK else None,
            "up": round(float(ol["upside"]), 4) if ol["ok"] and ol["upside"] is not None else None,
            "since": pd.Timestamp(since).strftime("%Y-%m-%d") if since is not None else None,
        })
    site.__dict__["_screen_rows"] = out
    return out


def screen_json(site):
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "fam": [[k, name, len([p for p in TIMED if p["family"] == k])] for k, name, _ in FAMILIES],
                       "t": rows(site)}, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ the same filter and sort as screen.js
def agree(r, side):
    return r["k"] if side == "buy" else r["o"] - r["k"]


def matches(site, r, st):
    if not r["o"]:
        return False
    if 100 * agree(r, st["side"]) / r["o"] < st["min"] - 1e-9:
        return False
    if st["mkt"] and r["m"] != st["mkt"]:
        return False
    if st["sec"] and r["g"] != st["sec"]:
        return False
    if st["risk"] == "low" and r["r"] not in (0, 1):
        return False
    if st["risk"] == "high" and r["r"] not in (2, 3):
        return False
    if st["fresh"]:
        if not r["since"] or (site.asof - pd.Timestamp(r["since"])).days > FRESH_DAYS:
            return False
        if r["L"] != (1 if st["side"] == "buy" else 0):
            return False
    return True


def state(**kw):
    st = {"side": "buy", "mkt": "", "sec": "", "risk": "", "min": DEFAULT_MIN, "fresh": False, "q": "", "sort": "agree"}
    st.update(kw)
    return st


def ranked(site, st):
    got = [r for r in rows(site) if matches(site, r, st)]
    got.sort(key=lambda r: (-agree(r, st["side"]) / r["o"], -r["o"], r["s"]))
    return got


# ------------------------------------------------------------------ markup (screen.js draws the same)
def light_html(r):
    if r["L"] is None:
        return '<span class="light-pill">–</span>'
    st = "start" if r["L"] == 1 else "stop"
    return f'<span class="light-pill {st}"><i aria-hidden="true"></i>{"Start" if r["L"] == 1 else "Stop"}</span>'


def row_html(site, r, side, depth):
    from .render import money, pct, dir_cls
    h = lambda x: site.href(depth, x)
    a, o = agree(r, side), r["o"]
    w = round(100 * a / o) if o else 0
    fams = "".join(
        f'<i style="height:{max(8, round(100 * (kk if side == "buy" else nn - kk) / nn)) if nn else 8}%" title="{e(name)}: {kk if side == "buy" else nn - kk} of {nn}"></i>'
        for (kk, nn), (_, name, _) in zip(r["f"], FAMILIES))
    risk = (f'<span class="lvl lvl-{RISK_CLS[r["r"]]}">{RISK[r["r"]]}</span>' if r["r"] is not None else '<span class="muted">–</span>')
    up = f'<span class="{dir_cls(r["up"])}">{pct(r["up"], d=0)}</span>' if r["up"] is not None else '<span class="muted">–</span>'
    return (f'<li class="scr-row" data-sym="{e(r["sym"])}"><a class="scr-main" href="{h("stocks/" + r["u"] + "/")}">'
            f'<span class="scr-sym"><b>{e(r["s"])}</b><span>{e(r["n"])}</span></span>'
            f'<span class="scr-light">{light_html(r)}</span>'
            f'<span class="scr-agree {side}"><span class="scr-num"><b>{a}</b> of {o}</span><span class="fillbar" aria-hidden="true"><i style="width:{w}%"></i></span></span>'
            f'<span class="scr-fams {side}" aria-hidden="true">{fams}</span>'
            f'<span class="scr-px mono">{money(r["p"], r["c"])} <small class="{dir_cls(r["d"])}">{pct(r["d"])}</small></span>'
            f'<span class="scr-y1 {dir_cls(r["y"])}"><em>1 yr</em>{pct(r["y"], d=0)}</span>'
            f'<span class="scr-risk"><em>Crash</em>{risk}</span>'
            f'<span class="scr-up"><em>Analysts</em>{up}</span></a>'
            f'<button type="button" class="scr-star" aria-pressed="false" aria-label="Follow {e(r["s"])}" title="Follow {e(r["s"])}">☆</button></li>')


def summary(n, st):
    who = "buying" if st["side"] == "buy" else "selling"
    where = dict(MARKETS)[st["mkt"]] if st["mkt"] else ""
    bits = [b for b in (where, st["sec"]) if b]
    return (f'<b>{n} name{"" if n == 1 else "s"}</b> where at least <b>{st["min"]} of 100</b> plays agree with <b>{who}</b>'
            + (f' · {e(" · ".join(bits))}' if bits else ""))


# ------------------------------------------------------------------ step 1: the market
def crash_card(site, depth):
    from .render import dlong, light_badge
    from .markets import fmt_val
    h = lambda x: site.href(depth, x)
    M = site.macro
    if not M:
        return ""
    cls = {"Calm": "calm", "Mostly calm": "calm", "Unsettled": "watch", "Stormy": "warning"}[M["weather"]]
    answer = {"Calm": "Not on these gauges. None is flashing a warning.",
              "Mostly calm": "Not on most of these gauges, though a couple run hot.",
              "Unsettled": "Some warning lights are on. That is not a crash signal, and it isn't an all-clear.",
              "Stormy": "Several warning lights are on at once, including the price trend."}[M["weather"]]
    c = M["counts"]
    watch = f', {c["watch"]} more worth watching' if c["watch"] else ""
    gauges = "".join(f'<li class="{g["status"]}"><a href="{h("markets/")}#g-{g["key"]}"><i></i><span>{e(g["name"])}</span><b>{fmt_val(g, g["value"])}</b></a></li>'
                     for g in M["gauges"])
    spx = next((t for t in TICKERS if t["sym"] == "^GSPC"), None)
    plays = ""
    if spx and (spx["sym"], "buy-and-hold") in site.R:
        L = site.light(spx)
        k, n = site.consensus(spx)
        plays = (f'<a class="cc-plays" href="{h("stocks/" + spx["slug"] + "/")}"><span>The plays on the S&amp;P 500</span>'
                 f'<b>{k} of {n} hold it</b>{light_badge(L)}</a>')
    return f"""<div class="card crash-card" id="step-1">
  <div class="cc-top"><span class="step-tag"><span class="step-n">1</span>The market</span><span class="mono small muted">{dlong(M['asof'])}</span></div>
  <h2 class="cc-q">Is the market about to crash?</h2>
  <p class="cc-verdict"><span class="wx {cls}">{e(M['weather'])}.</span> {e(answer)}</p>
  <p class="cc-count">{c['warning']} of {len(M['gauges'])} crash gauges flash a warning{watch}.</p>
  <ul class="cc-gauges">{gauges}</ul>
  {plays}
  <p class="cc-fine">Nobody can time a crash. These gauges ran hot before past tops, and sometimes with no crash after. <a href="{h('markets/')}">All nine, with a century of history</a></p>
</div>"""


# ------------------------------------------------------------------ steps 2 to 4: the screener
PRESETS = [
    ("Canada, most plays buying", dict(mkt="ca", min=75)),
    ("U.S. names nearly all plays like", dict(mkt="us", min=90)),
    ("What the plays are selling", dict(side="sell", min=75)),
    ("Fresh Starts this week", dict(fresh=True, min=60)),
    ("Lower crash risk, most plays in", dict(risk="low", min=60)),
    ("Gold and miners", dict(sec="Metals & mining", min=60)),
    ("Semiconductors", dict(sec="Semiconductors", min=60)),
]


def screener(site, depth):
    h = lambda x: site.href(depth, x)
    st = state()
    got = ranked(site, st)
    first = "".join(row_html(site, r, "buy", depth) for r in got[:PAGE])
    groups = [g for g in GROUP_ORDER if any(r["g"] == g for r in rows(site))]
    sec_opts = '<option value="">Every sector</option>' + "".join(f'<option value="{e(g)}">{e(g)}</option>' for g in groups)
    mkt = "".join(f'<button type="button" class="chip-btn" data-mkt="{k}" aria-pressed="{"true" if not k else "false"}">{e(lab)}</button>' for k, lab in MARKETS)
    mins = "".join(f'<button type="button" class="chip-btn" data-min="{v}" aria-pressed="{"true" if v == DEFAULT_MIN else "false"}">{e(lab)}</button>'
                   for v, lab in [(0, "Any"), (50, "Half"), (60, "Most"), (75, "Strong"), (90, "Nearly all")])
    risk = "".join(f'<button type="button" class="chip-btn" data-risk="{k}" aria-pressed="{"true" if not k else "false"}">{e(lab)}</button>'
                   for k, lab in [("", "Any"), ("low", "Low or moderate"), ("high", "High or very high")])
    presets = ""
    for lab, kw in PRESETS:
        n = len(ranked(site, state(**kw)))
        if n:
            presets += f'<button type="button" class="chip-btn scr-preset" data-preset="{e(json.dumps(kw))}">{e(lab)} <span class="muted">{n}</span></button>'
    sorts = "".join(f'<option value="{k}">{e(lab)}</option>' for k, lab in SORTS)
    n_all = len(rows(site))
    fam_names = " · ".join(name for _, name, _ in FAMILIES)
    return f"""<section class="screen" id="screen" aria-labelledby="scr-h" data-src="{e(h('data/screen.json'))}?v={site.ver}" data-stock="{e(h('stocks/{u}/'))}" data-me="{e(h('me/'))}" data-page="{PAGE}">
<div class="sec-head"><h2 class="h2" id="scr-h">Which stocks do the plays agree on?</h2><p>{n_all} stocks, funds and coins. Three quick steps; the list below updates as you go.</p></div>
<div class="scr-grid">
<div class="scr-steps card">
  <fieldset class="scr-step is-next" id="step-2"><legend><span class="step-n">2</span>What's your play?</legend>
    <div class="scr-side" role="group" aria-label="Your play">
      <button type="button" data-side="buy" aria-pressed="true"><b>Buying</b><span>Count the plays that hold it</span></button>
      <button type="button" data-side="sell" aria-pressed="false"><b>Selling</b><span>Count the plays that are out</span></button>
    </div>
  </fieldset>
  <fieldset class="scr-step" id="step-3"><legend><span class="step-n">3</span>Where are you looking?</legend>
    <div class="chips scr-mkt" role="group" aria-label="Market">{mkt}</div>
    <label class="scr-lab" for="scr-sec">Sector</label><select id="scr-sec">{sec_opts}</select>
    <span class="scr-lab">Crash exposure</span><div class="chips scr-risk" role="group" aria-label="Crash exposure">{risk}</div>
    <label class="scr-lab" for="scr-q">Or look up a name</label><input type="search" id="scr-q" placeholder="NVDA, Shopify, gold…" autocomplete="off" spellcheck="false">
  </fieldset>
  <fieldset class="scr-step" id="step-4"><legend><span class="step-n">4</span>How many of the 100 plays must agree?</legend>
    <div class="scr-min"><output id="scr-min-out" for="scr-min">At least <b>{DEFAULT_MIN}</b> of 100</output>
    <input type="range" id="scr-min" min="0" max="100" step="5" value="{DEFAULT_MIN}" aria-label="Plays that must agree, out of 100"></div>
    <div class="chips scr-mins" role="group" aria-label="Quick picks">{mins}</div>
    <label class="auth-check scr-fresh"><input type="checkbox" id="scr-fresh"><span>Only lights that flipped in the last week</span></label>
  </fieldset>
  <div class="scr-try"><span class="scr-lab">Or start from one of these</span><div class="chips">{presets}</div></div>
  <button type="button" class="btn primary scr-go" id="scr-go">See the {len(got)} names</button>
</div>
<div class="scr-results" id="scr-results">
  <div class="scr-head"><p class="scr-sum" id="scr-sum" aria-live="polite">{summary(len(got), st)}</p>
  <label class="scr-sort"><span class="small muted">Sort</span><select id="scr-sort">{sorts}</select></label>
  <button type="button" class="linkish scr-reset" id="scr-reset" hidden>Start over</button></div>
  <div class="scr-cols" aria-hidden="true"><span>Stock</span><span>Light</span><span>Plays that agree</span><span title="{e(fam_names)}">By family</span><span>Price · today</span><span>1 year</span><span>Crash</span><span>Analysts</span><span></span></div>
  <ol class="scr-list" id="scr-list">{first}</ol>
  <p class="scr-empty" id="scr-empty" hidden>No names match all of that. Try fewer plays in step 4, or a wider market in step 3.</p>
  <div class="scr-foot"><button type="button" class="btn" id="scr-more"{"" if len(got) > PAGE else " hidden"}>Show {PAGE} more</button>
  <p class="small muted">A play agrees with buying when it holds the stock tonight, and with selling when it's out. The seven bars are the plays by family: {e(fam_names)}. Tap ☆ to follow a name and get an email when its light flips. This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.</p></div>
</div>
</div>
</section>"""


def tickers_json(site):
    """data/tickers.json, every name the alerts page can look up:
    names[sym] = [short, name, slug, "USD"|"CAD", last close, "stock"|"fund"|"crypto", plays in, plays, group, light 1|0|null]."""
    from .render import sig
    from .engine import cad_per_usd
    names = {}
    for t in TICKERS:
        if t.get("index") or (t["sym"], "buy-and-hold") not in site.R:
            continue
        x = site.r(t["sym"], "buy-and-hold")
        k, n = site.consensus(t)
        kind = "crypto" if t["crypto"] else ("fund" if t["group"] in ("Indexes & ETFs", "Sectors") else "stock")
        lt = site.light(t)
        names[t["sym"]] = [t["short"], t["name"], t["slug"], "CAD" if t["cur"] == "C$" else "USD", sig(x["price"], 6), kind, k, n, t["group"],
                           None if not lt["state"] else (1 if lt["state"] == "start" else 0)]
    fx = cad_per_usd()
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "fx": {"CAD": fx} if fx else {}, "names": names}, ensure_ascii=False, separators=(",", ":"))
