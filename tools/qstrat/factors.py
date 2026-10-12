"""Your signal: the factors a reader can weight, and how each one scores a stock.

Every factor turns into points from 0 to 100, higher meaning more in favour of buying:
  - plays:  the share of the plays the reader counts that hold the stock (worked out in
            the browser by assets/plays.js, since it depends on their choice of plays)
  - upside: analysts' average 12-month target against the price, as in the existing
            score (stockview.upside_points: -20% scores 0, +50% full marks; 3+ analysts)
  - rating: the analysts' average recommendation, strong buy 1.0 = 100, hold 3.0 or worse = 0
  - calm:   100 minus 10 points per point of crash exposure on the storm test (0 to 10)
  - every other factor (P/E, growth, margins, debt, trend, momentum...) scores by rank:
    where the stock sits among every covered company with that number, so a P/E lower
    than 80% of them scores 80. A loss-maker scores 0 on P/E; a stock with no number
    for a factor simply leaves that factor out of its score.

A reader's score is the weighted average of the points they weight, over the factors the
stock has. With less than half their weight available (a fund has no P/E), there's no score.
Buy at or above their buy line (default 60), Sell at or below their sell line (default 40),
Hold in between. The default weights (plays 50, analysts' upside 50) give the site's existing
score; the Start/Stop light stays as it was, the plays' own reading.
"""
import math

import pandas as pd

from . import stockview as sv

GROUPS = [("signals", "Plays and analysts"), ("value", "Value"), ("quality", "Growth and quality"), ("price", "Price and risk")]

# key, name, group, what it is (shown in the chooser)
FACTORS = [
    ("plays", "Plays in", "signals", "The share of the plays you count that hold it now."),
    ("upside", "Analysts' upside", "signals", "How far analysts' average 12-month target sits above the price (3+ analysts). −20% scores 0, +50% full marks."),
    ("rating", "Analysts' rating", "signals", "The analysts' average recommendation: strong buy scores 100, hold or worse 0."),
    ("pe", "P/E", "value", "Price over the last 12 months' earnings per share. Lower ranks higher; a loss scores 0."),
    ("fpe", "Forward P/E", "value", "Price over next year's expected earnings. Lower ranks higher; an expected loss scores 0."),
    ("peg", "PEG", "value", "P/E divided by expected earnings growth. Lower ranks higher; around 1 is often read as fair for the growth."),
    ("ps", "Price to sales", "value", "Market value over the last 12 months' revenue. Lower ranks higher."),
    ("pb", "Price to book", "value", "Price over book value (assets minus debts) per share. Lower ranks higher."),
    ("dy", "Dividend yield", "value", "Dividends over the last year as a share of the price. Higher ranks higher; no dividend scores 0."),
    ("eg", "Earnings growth", "quality", "Earnings growth on the same quarter a year ago. Higher ranks higher."),
    ("rg", "Revenue growth", "quality", "Revenue growth on the same quarter a year ago. Higher ranks higher."),
    ("pm", "Profit margin", "quality", "Net profit as a share of revenue. Higher ranks higher."),
    ("roe", "Return on equity", "quality", "Profit as a share of shareholders' equity. Higher ranks higher."),
    ("de", "Debt to equity", "quality", "Debt against shareholders' equity. Lower ranks higher; negative equity scores 0."),
    ("trend", "Trend", "price", "How far the price sits above its 200-day average. Higher ranks higher."),
    ("mom", "1-year momentum", "price", "The price change over the last 12 months. Higher ranks higher."),
    ("calm", "Low crash exposure", "price", "The storm test: 100 for no exposure, 10 points off per point of exposure."),
]
KEYS = [k for k, _, _, _ in FACTORS]

DEFAULT = {"plays": 50, "upside": 50}
BUY, SELL = 60, 40
PRESETS = [
    ("default", "Plays + analysts", DEFAULT),
    ("plays", "Plays only", {"plays": 100}),
    ("value", "Value", {"plays": 20, "pe": 20, "fpe": 20, "ps": 15, "pb": 10, "dy": 15}),
    ("growth", "Growth", {"plays": 25, "rg": 25, "eg": 25, "peg": 15, "upside": 10}),
    ("quality", "Quality", {"plays": 20, "roe": 20, "pm": 20, "de": 20, "calm": 20}),
    ("momentum", "Momentum", {"plays": 40, "trend": 30, "mom": 30}),
    ("balanced", "Balanced", {"plays": 30, "upside": 10, "fpe": 10, "eg": 10, "roe": 10, "de": 10, "mom": 10, "calm": 10}),
]


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
            pe, eps = _num(f.get("trailingPE")), _num(f.get("trailingEps"))
            if pe is not None and pe > 0:
                raw["pe"][sym], shown["pe"][sym] = pe, _x(pe)
            elif eps is not None and eps < 0:
                fixed["pe"][sym], shown["pe"][sym] = 0, "loss"
            fpe = _num(f.get("forwardPE"))
            if fpe is not None and fpe > 0:
                raw["fpe"][sym], shown["fpe"][sym] = fpe, _x(fpe)
            elif fpe is not None and fpe < 0:
                fixed["fpe"][sym], shown["fpe"][sym] = 0, "loss expected"
            peg = _num(f.get("trailingPegRatio")) or _num(f.get("pegRatio"))
            if peg is not None and peg > 0:
                raw["peg"][sym], shown["peg"][sym] = peg, f"{peg:.2f}"
            elif peg is not None:
                fixed["peg"][sym], shown["peg"][sym] = 0, f"{peg:.2f}"
            ps = _num(f.get("priceToSalesTrailing12Months"))
            if ps is not None and ps > 0:
                raw["ps"][sym], shown["ps"][sym] = ps, _x(ps)
            pb = _num(f.get("priceToBook"))
            if pb is not None and pb > 0:
                raw["pb"][sym], shown["pb"][sym] = pb, _x(pb)
            elif pb is not None:
                fixed["pb"][sym], shown["pb"][sym] = 0, "negative book"
            dy = _num(f.get("dividendYield"))       # yfinance gives it in percent
            if dy is not None and dy > 0:
                raw["dy"][sym], shown["dy"][sym] = dy, f"{dy:.1f}%"
            elif dy is not None:
                fixed["dy"][sym], shown["dy"][sym] = 0, "none"
            for k, fld in (("eg", "earningsGrowth"), ("rg", "revenueGrowth"), ("pm", "profitMargins"), ("roe", "returnOnEquity")):
                v = _num(f.get(fld))
                if v is not None:
                    raw[k][sym], shown[k][sym] = v, _p(v, sign=k in ("eg", "rg"))
            de = _num(f.get("debtToEquity"))         # yfinance gives it in percent
            if de is not None and de >= 0:
                raw["de"][sym], shown["de"][sym] = de / 100, _x(de / 100, 2)
            elif de is not None:
                fixed["de"][sym], shown["de"][sym] = 0, "negative equity"
        # price and risk: every name
        o = meta.get("ohlc")
        if o is not None and len(o) >= 200:
            c = o["close"]
            gap = float(c.iloc[-1] / c.iloc[-200:].mean() - 1)
            raw["trend"][sym], shown["trend"][sym] = gap, _p(gap) + " vs 200-day"
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
            p, v = (None, None) if plays_share is None else (round(100 * plays_share), f"{round(100 * plays_share)}%")
        else:
            p, v = pts.get(key, (None, None))
        parts.append({"k": key, "n": name, "w": wi, "p": p, "v": v})
        if p is not None:
            avail += wi
            acc += wi * p
    if not tot or avail < tot / 2:
        return None, None, parts
    s = round(acc / avail)
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
    return {"fx": [{"k": k, "n": n, "g": g, "d": d} for k, n, g, d in FACTORS], "fg": [list(g) for g in GROUPS],
            "wp": [{"k": k, "n": n, "w": w} for k, n, w in PRESETS], "wd": {"w": DEFAULT, "buy": BUY, "sell": SELL}, "x": x, "v": v}


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
        p, v = ((round(100 * k / n) if n else None), (f"{round(100 * k / n)}%" if n else None)) if key == "plays" else pts.get(key, (None, None))
        allrows += (f'<tr data-sig-f="{key}"><td>{e(name)}</td><td>{e(v or "–")}</td><td class="r">{"–" if p is None else p}</td>'
                    f'<td class="small muted">{e(desc)}</td></tr>')
    pos = 50 if s is None else s
    return f"""<section class="card sig-card" id="your-signal">
<div class="sig-head"><div class="sig-l"><p class="eyebrow">Your signal</p>
<div class="sig-row"><span class="sig-badge {SIG_CLS[sig]}" data-sig-badge>{SIG_WORD[sig]}</span><span class="sig-score"><b data-sig-score>{"–" if s is None else s}</b><small> / 100</small></span></div></div>
<div class="sig-scale" aria-hidden="true" data-sig-scale><span class="sig-zone sell" style="width:{SELL}%"></span><span class="sig-zone hold" style="width:{BUY - SELL}%"></span><span class="sig-zone buy" style="width:{100 - BUY}%"></span><i class="sig-dot" style="left:{pos}%"></i></div></div>
<p class="sig-why" data-sig-why>{e(why(t["short"], s, sig, parts))}</p>
<div class="tbl-wrap"><table class="tbl sig-tbl"><thead><tr><th>Factor you weight</th><th>{e(t["short"])}</th><th class="r">Points</th><th class="r">Weight</th><th class="r">Adds</th></tr></thead><tbody data-sig-rows>{rows}</tbody></table></div>
<div class="sig-acts"><button type="button" class="ps-chip" data-ps-open="weights" aria-haspopup="dialog"><span class="ps-chip-k">Weights</span><b data-ps-wlabel>Plays + analysts</b><span class="ps-caret" aria-hidden="true">▾</span></button>
<span class="small muted">Weight P/E, growth, debt, trend and more; your Buy and Sell lines move every page. <a href="{h("guides/your-plays/")}#your-signal">How the score works</a></span></div>
<details class="sig-all"><summary>All {len(FACTORS)} factors for {e(t["short"])}</summary><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Factor</th><th>{e(t["short"])}</th><th class="r">Points</th><th>What it is</th></tr></thead><tbody data-sig-all>{allrows}</tbody></table></div></details>
</section>"""
