"""Your signal: the factors a reader can weight, and how each one scores a stock.

Every factor turns into points from 0 to 100, higher meaning more in favour of buying:
  - plays:  the share of the plays the reader counts that hold the stock (worked out in
            the browser by assets/plays.js, since it depends on their choice of plays)
  - upside: analysts' average 12-month target against the price, as in the existing
            score (stockview.upside_points: -20% scores 0, +50% full marks; 3+ analysts)
  - rating: the analysts' average recommendation, strong buy 1.0 = 100, hold 3.0 or worse = 0
  - calm:   100 minus 10 points per point of crash exposure on the storm test (0 to 10)
  - company numbers (P/E, P/S, P/B, dividend yield, growth, margin, ROE, debt) come from the
    company's SEC filings where it files 10-Qs (secfund.py, dated by filing), else Yahoo Finance,
    and every one passes the quality gate (quality.py) first
  - every other factor (P/E, growth, margins, debt, trend, momentum...) scores by rank:
    where the stock sits among every covered company with that number, so a P/E lower
    than 80% of them scores 80. A loss-maker scores 0 on P/E; a stock with no number
    for a factor simply leaves that factor out of its score.

A reader's score is the weighted average of the points they weight, over the factors the
stock has. With less than half their weight available (a fund has no P/E), there's no score.
Buy at or above their buy line (default 60), Sell at or below their sell line (default 40),
Hold in between. The default weights are plays 50, analysts' upside 50. Your signal is the
site's one headline call on a stock (October 2026: it replaced the Start/Stop light).
"""
import math

import pandas as pd

from . import stockview as sv
from .content import TIMED

GROUPS = [("signals", "Plays and analysts"), ("value", "Value"), ("quality", "Growth and quality"), ("price", "Price and risk")]

# key, name, group, what it is (shown in the chooser)
FACTORS = [
    ("plays", "Plays in", "signals", "The share of the plays you count that hold it now."),
    ("upside", "Analysts' upside", "signals", "How far analysts' average 12-month target sits above the price (3+ analysts). −20% scores 0, +50% full marks; at most 50 while the price is below its 200-day average, since targets lag a falling price."),
    ("rating", "Analysts' rating", "signals", "The analysts' average recommendation: strong buy scores 100, hold or worse 0."),
    ("pe", "P/E", "value", "Price over the last four quarters' earnings per share. Lower ranks higher; a loss scores 0."),
    ("fpe", "Forward P/E", "value", "Price over next year's expected earnings. Lower ranks higher; an expected loss scores 0."),
    ("peg", "PEG", "value", "P/E divided by expected earnings growth. Lower ranks higher; around 1 is often read as fair for the growth."),
    ("ps", "Price to sales", "value", "Market value over the last 12 months' revenue. Lower ranks higher."),
    ("pb", "Price to book", "value", "Price over book value (assets minus debts) per share. Lower ranks higher."),
    ("dy", "Dividend yield", "value", "Dividends over the last year as a share of the price. Higher ranks higher; no dividend scores 0."),
    ("eg", "Earnings growth", "quality", "Earnings per share over the last four quarters against the four before (the latest quarter on a year earlier where filings aren't available). Higher ranks higher."),
    ("rg", "Revenue growth", "quality", "Revenue over the last four quarters against the four before (the latest quarter on a year earlier where filings aren't available). Higher ranks higher."),
    ("pm", "Profit margin", "quality", "Net profit as a share of revenue. Higher ranks higher."),
    ("roe", "Return on equity", "quality", "Profit as a share of shareholders' equity. Higher ranks higher."),
    ("de", "Debt to equity", "quality", "Debt against shareholders' equity. Lower ranks higher; negative equity scores 0."),
    ("offhigh", "Off the high", "price", "How far the price sits below its highest close of the last year: 100 points at the high, none at 30% or more below. The exit rule: a stock that keeps falling loses points whatever else it has going for it."),
    ("trend", "Trend", "price", "How far the price sits above its 200-day average. Higher ranks higher."),
    ("mom", "1-year momentum", "price", "The price change over the last 12 months. Higher ranks higher."),
    ("calm", "Low crash exposure", "price", "The storm test: 100 for no exposure, 10 points off per point of exposure."),
]
KEYS = [k for k, _, _, _ in FACTORS]

OFFHIGH_FLOOR = 0.30      # this far below the 1-year high scores 0 on Off the high
UPSIDE_CAP = 50           # analysts' upside points while the price is below its 200-day average
MODEL = 2                 # bumped when the standard weights or a factor's scoring change (alerts re-baseline quietly)
# The standard weights (October 13, 2026): only factors with a track record (factorgrade.py), and
# 60% of them the price's own exit rules. Before that they were plays 50 / analysts' upside 50,
# half of it on targets that can't be tested and that look better the further a stock falls.
DEFAULT = {"plays": 40, "offhigh": 30, "trend": 30}
OLD_DEFAULT = {"plays": 50, "upside": 50}
BUY, SELL = 60, 40


def default_words(w=None):
    """The standard weights in words for pages and emails: "40% Plays in, 30% Off the high and 30% Trend"."""
    w = w or DEFAULT
    label = {k: lab for k, lab, _, _ in FACTORS}
    tot = sum(w.values()) or 1
    bits = [f"{round(100 * v / tot)}% {label[k]}" for k, v in w.items()]
    return bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]


PRESETS = [
    ("default", "Plays + exit rules", DEFAULT),
    ("analysts", "Plays + analysts", OLD_DEFAULT),
    ("plays", "Plays only", {"plays": 100}),
    ("value", "Value", {"plays": 20, "pe": 20, "fpe": 20, "ps": 15, "pb": 10, "dy": 15}),
    ("growth", "Growth", {"plays": 25, "rg": 25, "eg": 25, "peg": 15, "upside": 10}),
    ("quality", "Quality", {"plays": 20, "roe": 20, "pm": 20, "de": 20, "calm": 20}),
    ("momentum", "Momentum", {"plays": 40, "trend": 30, "mom": 30}),
    ("balanced", "Balanced", {"plays": 30, "upside": 10, "fpe": 10, "eg": 10, "roe": 10, "de": 10, "mom": 10, "calm": 10}),
]


def offhigh_points(dd):
    """Points on Off the high for a drawdown dd (0 at the high, -0.3 for 30% below)."""
    return _rnd(100 * max(0.0, min(1.0, 1 + dd / OFFHIGH_FLOOR)))


def _rnd(x):
    """Round half up, as JavaScript's Math.round does, so a score is the same in the page, the emails and here."""
    return int(math.floor(x + 0.5))


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _x(v, d=1):
    return f"{v:,.{d}f}×"


def _p(v, sign=True, d=0):
    if v is None:
        return None
    s = f"{abs(v) * 100:,.{d}f}%"
    return ("−" + s) if v < 0 else (("+" if sign and v > 0 else "") + s)


def _rank(vals, higher_better):
    """{sym: points 0-100} by rank among the values given."""
    if not vals:
        return {}
    s = pd.Series(vals, dtype=float)
    if len(s) == 1:
        return {s.index[0]: 50}
    r = s.rank(method="average")
    pts = (r - 1) / (len(s) - 1)
    if not higher_better:
        pts = 1 - pts
    return {k: int(round(100 * v)) for k, v in pts.items()}


def compute(site):
    """{sym: {key: (points or None, shown value or None)}} for every covered name (plays left to the browser)."""
    cache = site.__dict__.get("_factors")
    if cache is not None:
        return cache
    from .content import TICKERS
    names = [t for t in TICKERS if (t["sym"], "buy-and-hold") in site.R]
    out = {t["sym"]: {} for t in names}
    from . import secfund, quality
    from .engine import cad_per_usd
    gate = site.__dict__["_gate"] = quality.Gate(site.asof, cad_per_usd())
    src_map = site.__dict__["_factor_src"] = {}   # {sym: {key: where the number came from}}
    used = site.__dict__["_factor_val"] = {}      # {sym: {key: the number used, or "loss"/"negative"}} for the fundamentals card
    raw = {k: {} for k in KEYS}           # values to rank: {key: {sym: value}}
    fixed = {k: {} for k in KEYS}         # points set without ranking (losses, no dividend...)
    shown = {k: {} for k in KEYS}
    for t in names:
        sym = t["sym"]
        f = site.fund.get(sym) or {}
        eq = sv.is_equity(t, f)
        meta = site.meta.get(sym) or {}
        # analysts
        ol = sv.outlook(site, t)
        if ol["ok"]:
            fixed["upside"][sym] = int(round(100 * sv.upside_points(ol["upside"])))
            shown["upside"][sym] = _p(ol["upside"]) + f" · {ol['n_an']} analysts"
        rm, na = _num(f.get("recommendationMean")), _num(f.get("numberOfAnalystOpinions")) or 0
        if eq and rm is not None and na >= sv.MIN_ANALYSTS:
            fixed["rating"][sym] = int(round(100 * min(1, max(0, (3 - rm) / 2))))
            word = "strong buy" if rm < 1.5 else "buy" if rm < 2.5 else "hold" if rm < 3.5 else "sell"
            shown["rating"][sym] = f"{rm:.1f} · {word}"
        if eq:
            # company numbers: from SEC filings where the company files 10-Qs (secfund), else Yahoo;
            # every one passes the quality gate (quality.py) first
            yf = {} if gate.stale(t, f) else f
            sec = secfund.ratios(t, site.r(sym, "buy-and-hold")["price"], site.asof, gate.fx) if secfund.has(t) else {}
            srcs = src_map.setdefault(sym, {})

            def pick(key, yv):
                if key in sec:
                    srcs[key] = sec["src"]
                    return gate.check(t, key, sec[key], "SEC filings")
                if yv is not None:
                    srcs[key] = "Yahoo Finance"
                    return gate.check(t, key, yv, "Yahoo Finance")
                return None

            def put(key, v, show, neg_word=None):
                if v is not None:
                    used.setdefault(sym, {})[key] = v
                if isinstance(v, str):
                    fixed[key][sym], shown[key][sym] = 0, neg_word or v
                elif v is not None:
                    raw[key][sym], shown[key][sym] = v, show(v)

            pe_y, eps_y = _num(yf.get("trailingPE")), _num(yf.get("trailingEps"))
            put("pe", pick("pe", pe_y if pe_y and pe_y > 0 else ("loss" if eps_y is not None and eps_y < 0 else None)), _x)
            fpe = _num(yf.get("forwardPE"))
            if fpe is not None:
                srcs["fpe"] = "Yahoo Finance"
            put("fpe", gate.check(t, "fpe", fpe if fpe is None or fpe > 0 else "loss expected", "Yahoo Finance"), _x)
            peg = _num(yf.get("trailingPegRatio")) or _num(yf.get("pegRatio"))
            if peg is not None:
                srcs["peg"] = "Yahoo Finance"
                peg = gate.check(t, "peg", peg, "Yahoo Finance")
                if peg is not None and peg > 0:
                    raw["peg"][sym], shown["peg"][sym] = peg, f"{peg:.2f}"
                elif peg is not None:
                    fixed["peg"][sym], shown["peg"][sym] = 0, f"{peg:.2f}"
            ps_y = _num(yf.get("priceToSalesTrailing12Months"))
            ps_y = gate.ps_currency(t, yf, ps_y) if ps_y is not None and ps_y > 0 and "ps" not in sec else None
            put("ps", pick("ps", ps_y), _x)
            pb_y = _num(yf.get("priceToBook"))
            put("pb", pick("pb", pb_y if pb_y is None or pb_y > 0 else "negative"), _x, "negative book")
            dy_y = _num(yf.get("dividendYield"))          # Yahoo gives it in percent
            dy = pick("dy", None if dy_y is None else dy_y / 100)
            if dy is not None:
                used.setdefault(sym, {})["dy"] = dy
            if dy is not None and dy > 0:
                raw["dy"][sym], shown["dy"][sym] = dy, f"{dy * 100:.1f}%"
            elif dy is not None:
                fixed["dy"][sym], shown["dy"][sym] = 0, "none"
            for k, fld in (("eg", "earningsGrowth"), ("rg", "revenueGrowth"), ("pm", "profitMargins"), ("roe", "returnOnEquity")):
                put(k, pick(k, _num(yf.get(fld))), lambda v, k=k: _p(v, sign=k in ("eg", "rg")))
            de_y = _num(yf.get("debtToEquity"))           # Yahoo gives it in percent
            put("de", pick("de", None if de_y is None else (de_y / 100 if de_y >= 0 else "negative")), lambda v: _x(v, 2), "negative equity")
        # price and risk: every name
        o = meta.get("ohlc")
        gap = None
        if o is not None and len(o) >= 200:
            c = o["close"]
            gap = float(c.iloc[-1] / c.iloc[-200:].mean() - 1)
            raw["trend"][sym], shown["trend"][sym] = gap, _p(gap) + " vs 200-day"
        # off the high: an absolute exit rule, not a ranking (in a broad sell-off every stock loses points)
        pc_ = (site.prices or {}).get(sym)
        if pc_ is not None and len(pc_) >= 120:
            cl = pc_["close"].iloc[-252:]
            dd = float(cl.iloc[-1] / cl.max() - 1)
            fixed["offhigh"][sym], shown["offhigh"][sym] = offhigh_points(dd), ("at its 1-year high" if dd > -0.005 else _p(dd) + " from its 1-year high")
        # analysts' targets lag a falling price, so their upside counts for at most half while the trend is broken
        if gap is not None and gap < 0 and fixed["upside"].get(sym, 0) > UPSIDE_CAP:
            fixed["upside"][sym] = UPSIDE_CAP
            shown["upside"][sym] = (shown["upside"].get(sym) or "") + " · capped: below 200-day"
        try:
            y1 = site.one_year(t)
        except Exception:
            y1 = None
        if y1 is not None:
            raw["mom"][sym], shown["mom"][sym] = float(y1), _p(float(y1))
        rk = meta.get("risk") or {}
        if rk.get("score") is not None:
            fixed["calm"][sym] = int(max(0, 100 - 10 * rk["score"]))
            shown["calm"][sym] = f"{rk['score']}/10 · {rk.get('level', '').lower()}"
    lower_better = {"pe", "fpe", "peg", "ps", "pb", "de"}
    for k in KEYS:
        pts = dict(fixed[k])
        pts.update(_rank(raw[k], k not in lower_better))
        for sym, p in pts.items():
            out[sym][k] = (p, shown[k].get(sym))
    site.__dict__["_factors"] = out
    return out


def score(site, t, weights=None, plays_share=None):
    """(score 0-100 or None, signal 1 Buy / 0 Hold / -1 Sell / None, parts) for one stock and one set of weights."""
    w = weights or DEFAULT
    pts = compute(site).get(t["sym"], {})
    if plays_share is None:
        k, n = site.consensus(t)
        plays_share = k / n if n else None
    tot = avail = acc = 0.0
    parts = []
    for key, name, _, _ in FACTORS:
        wi = w.get(key, 0)
        if not wi:
            continue
        tot += wi
        if key == "plays":
            p, v = (None, None) if plays_share is None else (_rnd(100 * plays_share), f"{_rnd(100 * plays_share)}%")
        else:
            p, v = pts.get(key, (None, None))
        parts.append({"k": key, "n": name, "w": wi, "p": p, "v": v})
        if p is not None:
            avail += wi
            acc += wi * p
    if not tot or avail < tot / 2:
        return None, None, parts
    s = _rnd(acc / avail)
    for x in parts:
        x["add"] = None if x["p"] is None else round(x["w"] * x["p"] / avail, 1)
    return s, (1 if s >= BUY else -1 if s <= SELL else 0), parts


def factors_json(site):
    """The factor half of data/playset.json: metadata, presets and every name's points and shown values."""
    pts = compute(site)
    x, v = {}, {}
    for sym, d in pts.items():
        x[sym] = [None if k == "plays" else d.get(k, (None, None))[0] for k in KEYS]
        v[sym] = [None if k == "plays" else d.get(k, (None, None))[1] for k in KEYS]
    from .factorgrade import cached
    g = cached(site)

    def rec(r):
        """A factor's or preset's graded record, short for the chooser (assets/plays.js)."""
        if not r:
            return None
        if r.get("why"):
            return {"why": r["why"]}
        y, q = r.get("12m"), r.get("3m")
        if not y:
            return None
        out = {"bb": round(100 * y["buys_beat"]), "ab": round(100 * y["avoids_beat"]), "e": round(100 * y["edge"], 1),
               "e3": round(100 * q["edge"], 1) if q else None}
        if "graded_weight" in r:
            out["gw"] = r["graded_weight"]
            out["lo"] = [next(n for k2, n, _, _ in FACTORS if k2 == k) for k in r.get("left_out", [])]
        return out
    gf, gp = g.get("factors", {}), g.get("presets", {})
    return {"fx": [{"k": k, "n": n, "g": g_, "d": d, "r": rec(gf.get(k))} for k, n, g_, d in FACTORS], "fg": [list(x) for x in GROUPS],
            "wp": [{"k": k, "n": n, "w": w, "r": rec(gp.get(k))} for k, n, w in PRESETS], "wd": {"w": DEFAULT, "buy": BUY, "sell": SELL},
            "wo": OLD_DEFAULT, "mv": MODEL, "gs": g.get("since", "")[:4], "x": x, "v": v}


SIG_WORD = {1: "Buy", 0: "Hold", -1: "Sell", None: "No score"}
SIG_CLS = {1: "buy", 0: "hold", -1: "sell", None: "na"}


def why(short, s, sig, parts, buy=BUY, sell=SELL):
    """One or two plain sentences on why the score lands where it does (assets/playview.js says the same)."""
    have = [x for x in parts if x["p"] is not None]
    if s is None:
        miss = [x["n"] for x in parts if x["p"] is None]
        return f"Not enough data for these weights: {short} has no {', '.join(miss[:4])}." if miss else "Weight at least one factor to get a score."
    where = (f"at or above your Buy line of {buy}" if sig == 1 else f"at or below your Sell line of {sell}" if sig == -1
             else f"between your Sell line ({sell}) and Buy line ({buy})")
    out = f"{SIG_WORD[sig]}: {s} is {where}."
    if len(have) == 1:
        x = have[0]
        return out + f" {x['n']} ({x['v']}) scores {x['p']}."
    hi, lo = max(have, key=lambda x: x["p"]), min(have, key=lambda x: x["p"])
    return out + f" {hi['n']} ({hi['v']}) scores {hi['p']} and lifts it; {lo['n']} ({lo['v']}) scores {lo['p']} and holds it back."


def signal_card(site, t, h):
    """The stock page's Your signal card, drawn with the default weights; assets/playview.js redraws it for the reader's."""
    import html
    e = html.escape
    s, sig, parts = score(site, t)
    pts = compute(site).get(t["sym"], {})
    k, n = site.consensus(t)
    rows = "".join(f'<tr><td>{e(x["n"])}</td><td>{e(x["v"] or "–")}</td><td class="r">{"–" if x["p"] is None else x["p"]}</td>'
                   f'<td class="r">{x["w"]}</td><td class="r">{"–" if x.get("add") is None else x["add"]}</td></tr>' for x in parts)
    allrows = ""
    for key, name, _, desc in FACTORS:
        p, v = ((_rnd(100 * k / n) if n else None), (f"{_rnd(100 * k / n)}%" if n else None)) if key == "plays" else pts.get(key, (None, None))
        src = (site.__dict__.get("_factor_src") or {}).get(t["sym"], {}).get(key)
        allrows += (f'<tr data-sig-f="{key}"><td>{e(name)}</td><td>{e(v or "–")}</td><td class="r">{"–" if p is None else p}</td>'
                    f'<td class="small muted">{e(desc)}{(" <b class=sig-src>Source: " + e(src) + ".</b>") if src else ""}</td></tr>')
    pos = 50 if s is None else s
    alert = "" if t.get("index") else (f'<a class="btn sm sig-alert" href="{h("alerts/")}?t={e(t["slug"])}" data-signed-out>Email me when it flips</a>'
                                       f'<a class="btn sm sig-alert" href="{h("me/")}#alerts" data-signed-in hidden>My alerts</a>')
    return f"""<section class="card sig-card" id="your-signal">
<div class="sig-head"><div class="sig-l"><p class="eyebrow">Your signal</p>
<div class="sig-row"><span class="sig-badge {SIG_CLS[sig]}" data-sig-badge>{SIG_WORD[sig]}</span><span class="sig-score"><b data-sig-score>{"–" if s is None else s}</b><small> / 100</small></span></div></div>
<div class="sig-scale" aria-hidden="true" data-sig-scale><span class="sig-zone sell" style="width:{SELL}%"></span><span class="sig-zone hold" style="width:{BUY - SELL}%"></span><span class="sig-zone buy" style="width:{100 - BUY}%"></span><i class="sig-dot" style="left:{pos}%"></i></div></div>
<p class="sig-why" data-sig-why>{e(why(t["short"], s, sig, parts))}</p>
<p class="small sig-tested" data-sig-tested>{e(tested_line(site, parts))}</p>
<div class="tbl-wrap"><table class="tbl sig-tbl"><thead><tr><th>Factor you weight</th><th>{e(t["short"])}</th><th class="r">Points</th><th class="r">Weight</th><th class="r">Adds</th></tr></thead><tbody data-sig-rows>{rows}</tbody></table></div>
<div class="sig-acts"><span class="ps-chips"><button type="button" class="ps-chip" data-ps-open="weights" aria-haspopup="dialog"><span class="ps-chip-k">Weights</span><b data-ps-wlabel>Plays + exit rules</b><span class="ps-caret" aria-hidden="true">▾</span></button>
<button type="button" class="ps-chip" data-ps-open aria-haspopup="dialog"><span class="ps-chip-k">Plays counted</span><b data-ps-label>All {len(TIMED)}</b><span class="ps-caret" aria-hidden="true">▾</span></button></span>
{alert}</div>
<p class="small muted sig-note">Your signal is the one call Be The Puck makes on a stock, and you set it: weight the plays, analysts, P/E, growth, debt, trend and more, and move the Buy and Sell lines. Every page follows your choice. <a href="{h("guides/your-plays/")}#your-signal">How the score works</a></p>
<details class="sig-all"><summary>All {len(FACTORS)} factors for {e(t["short"])}</summary><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Factor</th><th>{e(t["short"])}</th><th class="r">Points</th><th>What it is</th></tr></thead><tbody data-sig-all>{allrows}</tbody></table></div></details>
</section>"""


def card_numbers(site, t):
    """The company numbers Your signal used for this stock (SEC filings or quality-checked Yahoo),
    so the stock page's business card shows the same P/E, growth and the rest: ({key: value}, {key: source})."""
    compute(site)
    return (site.__dict__.get("_factor_val") or {}).get(t["sym"], {}), (site.__dict__.get("_factor_src") or {}).get(t["sym"], {})


def tested_line(site, parts):
    """How much of a score rests on factors with a track record (factorgrade.py); assets/playview.js says the same."""
    from .factorgrade import cached, GRADED
    since = (cached(site).get("since") or "2011")[:4]
    have = [x for x in parts if x["p"] is not None]
    a = sum(x["w"] for x in have)
    if not a:
        return ""
    g = sum(x["w"] for x in have if x["k"] in GRADED)
    share = round(100 * g / a)
    if share >= 100:
        return f"Every factor in this score has a tested record: each was checked month by month since {since} on numbers public at the time."
    if share == 0:
        return "None of this score rests on a factor with a tested record."
    return f"{share}% of this score rests on factors with a tested record; the rest ({', '.join(x['n'] for x in have if x['k'] not in GRADED)}) has none."
