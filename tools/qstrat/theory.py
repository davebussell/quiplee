"""The Theory tester (/theory/): pick a stock and a theory, get the reading and the
rationale, then roll through every play's reason to buy or not.

A theory is one play, one family of plays, or all of them. For each covered name
the build writes data/theory/<slug>.json: every play's call tonight, why (the rule
that applies, the latest indicator readings and any checks), since when, what would
change its mind and its record on that stock. The page itself carries the plays'
descriptions and renders a default stock, so it reads fully without JavaScript;
assets/theory.js takes over from there. The markup here and in theory.js must match.
"""
import html
import json
import math

import pandas as pd

from .content import TICKERS, TIMED, FAMILIES, credit

e = html.escape
FAM = {k: name for k, name, _ in FAMILIES}
DEFAULT = "NVDA"
POPULAR = ["NVDA", "AAPL", "TSLA", "SHOP.TO", "RY.TO", "BTC-USD", "SPY", "GLD"]
ON, OFF = 0.6, 0.4


def _f(v, d=4):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else round(v, d)


def play_meta():
    out = []
    for p in TIMED:
        r = p.get("rules") or []
        out.append({"p": p["slug"], "name": p["name"], "f": p["family"], "idea": p["short"],
                    "rin": r[0] if r else "", "rout": r[1] if len(r) > 1 else "", "by": credit(p)})
    return out


def _reading(x):
    from .render import pct
    pn = x["window"].get("panel")
    if not pn:
        return ""
    parts = []
    for lab, ser, _ in pn["series"]:
        v = ser.dropna()
        if len(v):
            val = float(v.iloc[-1])
            parts.append(f"{lab} {pct(val, sign=False) if pn['fmt'] == 'pct' else f'{val:,.2f}'.replace('-', '−')}")
    return " · ".join(parts)


def stock_data(site, t):
    """Every play's call on one stock, in TIMED order (the same order as play_meta)."""
    from .render import next_move
    rows = []
    for p in TIMED:
        x = site.r(t["sym"], p["slug"])
        nm = next_move(x, p, t)
        st = x["state"]
        sp = x.get("since_price")
        stats = x.get("stats") or {}
        full = stats.get("full") or {}
        a, b = full.get("strat") or {}, full.get("bh") or {}
        bat = x.get("batting") or {}
        rows.append({
            "s": st, "d": x["since"].strftime("%Y-%m-%d") if x.get("since") is not None else None, "dp": _f(sp),
            "mv": _f(x["price"] / sp - 1) if sp else None, "rd": _reading(x),
            "ck": [[lab, bool(ok)] for lab, ok in (nm.get("checks") or [])],
            "nx": nm.get("headline") or "", "ds": _f(nm.get("dist")),
            "ok": int(bat.get("right") or 0), "nc": int(bat.get("n") or 0),
            "cg": _f(a.get("cagr")), "bc": _f(b.get("cagr")), "y": stats["start"].year if stats.get("start") is not None else None,
        })
    L = site.light(t)
    k, n = site.consensus(t)
    return {"sym": t["sym"], "s": t["short"], "n": t["name"], "u": t["slug"], "c": t["cur"], "p": _f(site.r(t["sym"], "buy-and-hold")["price"]),
            "asof": site.asof.strftime("%Y-%m-%d"), "L": None if not L["state"] else (1 if L["state"] == "start" else 0), "k": k, "o": n, "x": rows}


def files(site):
    """{slug: json} for every covered name."""
    return {t["slug"]: json.dumps(stock_data(site, t), ensure_ascii=False, separators=(",", ":"))
            for t in TICKERS if (t["sym"], "buy-and-hold") in site.R}


# ------------------------------------------------------------------ rendering (theory.js draws the same)
def _money(v, cur):
    from .render import money
    return money(v, cur)


def _pct(v, d=1):
    from .render import pct
    return pct(v, d=d)


def _date(s):
    return pd.Timestamp(s).strftime("%b %-d, %Y") if s else ""


def reason_card(D, i, meta, depth, h):
    m, x = meta[i], D["x"][i]
    st = x["s"]
    cls = "in" if st == 1 else "out" if st == 0 else "none"
    say = "Says buy" if st == 1 else "Says don't buy" if st == 0 else "No call yet"
    rule = m["rin"] if st == 1 else m["rout"] if st == 0 else "Not enough price history yet for this play to make a call."
    why = e(rule) + (f' <span class="th-rd">Tonight: {e(x["rd"])}.</span>' if x["rd"] else "")
    checks = ""
    if x["ck"]:
        checks = ('<dt>Checks</dt><dd><ul class="checks">' + "".join(
            f'<li><span class="{"ok" if ok else "no"}">{"✓" if ok else "✕"}</span>{e(lab)}</li>' for lab, ok in x["ck"]) + "</ul></dd>")
    since = ""
    if st is not None and x["d"]:
        since = (f'<dt>Since</dt><dd>Has said {"buy" if st == 1 else "don&#39;t buy"} since {_date(x["d"])}'
                 + (f', at {_money(x["dp"], D["c"])}. {e(D["s"])} has moved <b class="{"up" if (x["mv"] or 0) > 0 else "down" if (x["mv"] or 0) < 0 else ""}">{_pct(x["mv"])}</b> since.' if x["dp"] else ".") + "</dd>")
    nxt = f'<dt>Changes its mind</dt><dd>{e(x["nx"])}' + (f' <span class="muted">({_pct(x["ds"])} from tonight&#39;s close)</span>' if x["ds"] is not None else "") + "</dd>" if x["nx"] else ""
    rec = ""
    if x["nc"]:
        rec = f'Right on {x["ok"]} of {x["nc"]} calls.'
        if x["cg"] is not None and x["bc"] is not None and x["y"]:
            rec += f' {_pct(x["cg"])} a year, against {_pct(x["bc"])} for buying and holding, since {x["y"]}.'
        rec = f'<dt>Its record on {e(D["s"])}</dt><dd>{rec}</dd>'
    href = h(f'stocks/{D["u"]}/{m["p"]}/')
    return (f'<article class="th-card {cls}"><header class="th-card-h"><span class="th-say {cls}">{say}</span>'
            f'<a class="th-name" href="{href}">{e(m["name"])}</a><span class="th-by">{e(FAM[m["f"]])} · {e(m["by"])}</span></header>'
            f'<p class="th-idea">{e(m["idea"])}</p><dl class="th-why"><dt>Why</dt><dd>{why}</dd>{checks}{since}{nxt}{rec}</dl>'
            f'<a class="th-more" href="{href}">Chart and every call</a></article>')


def order(D, idx):
    """Best record on this stock first: (right + 1) / (calls + 2), then the name."""
    meta = play_meta()
    return sorted(idx, key=lambda i: (-(D["x"][i]["ok"] + 1) / (D["x"][i]["nc"] + 2), meta[i]["name"]))


def verdict_html(D, theory, meta):
    idx = pick(theory, meta)
    ins = [i for i in idx if D["x"][i]["s"] == 1]
    outs = [i for i in idx if D["x"][i]["s"] == 0]
    n = len(ins) + len(outs)
    share = len(ins) / n if n else 0
    if theory.startswith("play:"):
        m = meta[idx[0]]
        st = D["x"][idx[0]]["s"]
        word, cls = ("Buy", "buy") if st == 1 else ("Don't buy", "no") if st == 0 else ("No call yet", "split")
        line = f'{e(m["name"])} {"holds" if st == 1 else "is out of" if st == 0 else "has no call on"} {e(D["s"])} tonight.'
        label = m["name"]
    else:
        word, cls = ("Buy", "buy") if share >= ON else ("Don't buy", "no") if share <= OFF else ("Split", "split")
        label = "All the plays" if theory == "all" else FAM[theory[4:]] + " plays"
        line = f'<b>{len(ins)} of {n}</b> {"plays" if theory == "all" else e(FAM[theory[4:]].lower()) + " plays"} say buy {e(D["s"])} tonight; {len(outs)} say don&#39;t.'
        if theory == "all" and D["L"] is not None:
            line += f' The Start/Stop light is on <b>{"Start" if D["L"] == 1 else "Stop"}</b>.'
    w = round(100 * share)
    meter = "" if theory.startswith("play:") else (f'<div class="th-meter" aria-hidden="true"><i style="width:{w}%"></i></div>'
                                                   f'<div class="th-meter-l"><span>Buy {len(ins)}</span><span>Don&#39;t buy {len(outs)}</span></div>')
    return (f'<div class="th-verdict {cls}"><p class="th-step"><span class="step-n">3</span>The reading</p>'
            f'<p class="th-q">{e(label)} on <b>{e(D["s"])}</b> <span class="muted">· {e(D["n"])}, {_money(D["p"], D["c"])}</span></p>'
            f'<p class="th-big">{e(word)}</p><p class="th-line">{line}</p>{meter}</div>')


def pick(theory, meta):
    if theory.startswith("play:"):
        return [i for i, m in enumerate(meta) if m["p"] == theory[5:]][:1] or list(range(len(meta)))
    if theory.startswith("fam:"):
        return [i for i, m in enumerate(meta) if m["f"] == theory[4:]]
    return list(range(len(meta)))


def roll_html(D, theory, meta, depth, h):
    idx = list(range(len(meta))) if theory.startswith("play:") else pick(theory, meta)
    ins = order(D, [i for i in idx if D["x"][i]["s"] == 1])
    outs = order(D, [i for i in idx if D["x"][i]["s"] == 0])
    side = ins if ins else outs
    first = reason_card(D, side[0], meta, depth, h) if side else '<p class="muted">No play has a call on this stock yet.</p>'

    def li(i, k):
        x = D["x"][i]
        rec = f'right {x["ok"]}/{x["nc"]}' if x["nc"] else "no closed calls yet"
        cur = ' aria-current="true"' if k == 0 else ""
        return (f'<li><button type="button" data-i="{i}"{cur}><span class="th-li-n">{e(meta[i]["name"])}</span>'
                f'<span class="th-li-m">{e(FAM[meta[i]["f"]])} · {rec}</span></button></li>')
    return (f'<div class="th-roll" id="th-roll"><p class="th-step"><span class="step-n">4</span>Roll through every reason</p>'
            f'<div class="th-tabs" role="tablist"><button type="button" role="tab" data-side="in" aria-selected="{"true" if side is ins else "false"}">Reasons to buy <b>{len(ins)}</b></button>'
            f'<button type="button" role="tab" data-side="out" aria-selected="{"true" if side is outs else "false"}">Reasons not to <b>{len(outs)}</b></button></div>'
            f'<div class="th-body"><div class="th-stage" aria-live="polite">{first}'
            f'<div class="th-nav"><button type="button" class="btn sm" data-go="-1" aria-label="Previous reason">←</button>'
            f'<span class="th-pos">1 of {len(side)}</span><button type="button" class="btn sm" data-go="1" aria-label="Next reason">→</button>'
            f'<button type="button" class="btn sm th-auto" aria-pressed="false">▶ Roll through</button></div></div>'
            f'<ol class="th-list">{"".join(li(i, k) for k, i in enumerate(side))}</ol></div>'
            f'<p class="small muted th-order">Best record on {e(D["s"])} first. A play agrees with buying when it holds the stock tonight.</p></div>')


def theory_page(site):
    from .render import dlong
    path, depth = "theory/", 1
    h = lambda x: site.href(depth, x)
    meta = play_meta()
    t0 = next((t for t in TICKERS if t["sym"] == DEFAULT), None)
    D = stock_data(site, t0) if t0 and (t0["sym"], "buy-and-hold") in site.R else None
    names = [[t["slug"], t["short"], t["name"], t["sym"]] for t in TICKERS if (t["sym"], "buy-and-hold") in site.R]
    fam_opts = "".join(f'<option value="fam:{k}">{e(name)} ({len([p for p in TIMED if p["family"] == k])} plays)</option>' for k, name, _ in FAMILIES)
    play_groups = "".join(f'<optgroup label="{e(name)}">' + "".join(f'<option value="play:{p["slug"]}">{e(p["name"])}</option>' for p in TIMED if p["family"] == k) + "</optgroup>"
                          for k, name, _ in FAMILIES)
    chips = ('<button type="button" class="chip-btn" data-theory="all" aria-pressed="true">All 100</button>'
             + "".join(f'<button type="button" class="chip-btn" data-theory="fam:{k}" aria-pressed="false">{e(name)}</button>' for k, name, _ in FAMILIES))
    out = (verdict_html(D, "all", meta) + roll_html(D, "all", meta, depth, h)) if D else ""
    pop = "".join(f'<a class="chip-btn" href="?s={e(t["slug"])}" data-pick="{e(t["slug"])}">{e(t["short"])}</a>'
                  for sym in POPULAR for t in TICKERS if t["sym"] == sym and (sym, "buy-and-hold") in site.R)
    data = json.dumps({"plays": meta, "fams": [[k, name] for k, name, _ in FAMILIES], "names": names, "default": t0["slug"] if t0 else None},
                      ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = f"""<section class="pair-head th-head"><p class="eyebrow">Theory tester</p>
<h1 class="h1">Put a theory to the test on any stock</h1>
<p class="lede">Pick a stock and a theory. See what it says tonight, why, and the price that would change its mind. Then roll through every play's reason to buy or not, best record first.</p></section>

<section class="th-app" id="th-app" data-src="{e(h('data/theory/'))}" data-v="{site.ver}" data-stock="{e(h('stocks/'))}">
<div class="th-pick card">
  <div class="th-field"><p class="th-step"><span class="step-n">1</span>Pick a stock</p>
    <div class="th-search"><input type="search" id="th-q" value="{e(D['s'] + ' · ' + D['n']) if D else ''}" placeholder="NVDA, Shopify, gold, bitcoin…" autocomplete="off" spellcheck="false" aria-label="Pick a stock" aria-autocomplete="list" aria-controls="th-sug">
    <ul class="th-sug" id="th-sug" role="listbox" hidden></ul></div>
    <div class="chips th-pop"><span class="small muted">Try</span>{pop}</div></div>
  <div class="th-field"><p class="th-step"><span class="step-n">2</span>Pick a theory</p>
    <select id="th-theory" aria-label="Pick a theory"><option value="all">All 100 plays</option><optgroup label="A family of plays">{fam_opts}</optgroup>{play_groups}</select>
    <div class="chips th-chips">{chips}</div></div>
</div>
<div class="th-out" id="th-out">{out}</div>
<p class="small muted">Readings use the {dlong(site.asof)} close. A play's record counts every call it would have made on this stock since its history allows, after trading costs. This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.</p>
<script type="application/json" id="th-data">{data}</script>
</section>"""
    site.add(path, site.shell(path, "Theory tester: test a trading theory on any stock",
                              f"Pick any of {len(names)} stocks, funds and coins and a theory: one of {len(TIMED)} published trading plays, a family of them, or all of them. "
                              "Get the reading, the rationale and the price that would change its mind, then roll through every reason to buy or not.",
                              body, active="theory/", scripts=("assets/theory.js",)))
