"""Grading Your signal's factors and presets the way the plays are graded.

At every month-end since START, each stock gets its points on each factor exactly as Your
signal would have scored it then, from numbers public at the time: prices up to that close,
the plays' calls up to that close, and SEC filings filed by that date (secfund). A factor
"says buy" at 60 points or more and "says avoid" at 40 or less. Each call is checked against the stock's market, with
dividends (SPY for U.S. names, XIU.TO for Canadian ones: content.TR_BENCH; the stocks' own closes include
dividends, so a price index would flatter every call by 2-3 points a year), over the next three months and
the next year: how often the buys beat the market, how often the avoids did, and the gap between the two
(the edge). Every record is also kept for U.S. and TSX names apart, and with a range from the year-by-year
edges (rec()). Names whose prices are too thin to test (quality.price_check) are left out.
Because the covered stocks beat their market more often than not (they're today's names,
which flatters every test), the edge, not the raw hit rate, is what tells a factor apart.
Spread is the median return of the buys against the market less that of the avoids.

Analysts' targets and ratings, forward P/E, PEG and crash exposure have no record of past
values, so they can't be graded; a preset is graded on the factors that can be, and says so.
Like every backtest here it uses today's list of covered stocks, which flatters every
factor alike.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd

from .content import TICKERS, TIMED
from . import secfund
from .quality import BOUNDS

START = pd.Timestamp("2006-01-01")   # the first month-end with a year of every play's history (prices from 2004)
HORIZONS = (63, 252)    # sessions: about three months and a year
BUY, AVOID = 60, 40
COMPANY = ("pe", "ps", "pb", "dy", "eg", "rg", "pm", "roe", "de")
GRADED = ("plays", "offhigh", "trend", "mom") + COMPANY
LOWER_BETTER = {"pe", "fpe", "peg", "ps", "pb", "de"}
NO_HISTORY = {"upside": "no record of past analyst targets", "rating": "no record of past analyst ratings",
              "fpe": "no record of past earnings estimates", "peg": "no record of past growth estimates",
              "calm": "the storm test is built from today's balance sheet"}


def _rank(vals, higher_better):
    if not vals:
        return {}
    s = pd.Series(vals, dtype=float)
    if len(s) == 1:
        return {s.index[0]: 50}
    pts = (s.rank(method="average") - 1) / (len(s) - 1)
    if not higher_better:
        pts = 1 - pts
    return (100 * pts).round().astype(int).to_dict()


def _stocks(site):
    from .render import is_stock
    return [t for t in TICKERS if is_stock(t) and (t["sym"], "buy-and-hold") in site.R and bench_of(t) in site.prices
            and not t.get("requested") and not t.get("unreliable") and t["sym"] in site.prices]


def bench_of(t):
    """The market a stock is graded against: its index's total-return fund (SPY, XIU.TO)."""
    return t.get("tr_bench") or t.get("bench")


def market(t):
    return "tsx" if t.get("bench") == "^GSPTSE" else "us"


MARKETS = ("us", "tsx")


def _plays_share(site, t, dates):
    """For each date, (plays in, plays with a call) from every play's calls up to that date."""
    k = np.zeros(len(dates), int)
    n = np.zeros(len(dates), int)
    dv = dates.values
    days = (dv.astype("datetime64[D]").astype(np.int64)).astype(np.int32)
    for p in TIMED:
        x = site.R.get((t["sym"], p["slug"]))
        if not x:
            continue
        cd, st = dict.get(x, "call_days"), dict.get(x, "call_states")
        if cd is None:            # results from before the engine kept these in memory: read the full call list
            calls = x["calls"]
            cd = np.array([c["date"].value // 86_400_000_000_000 for c in calls], dtype=np.int32)
            st = np.array([c["state"] for c in calls], dtype=np.int8)
        if not len(cd):
            continue
        i = np.searchsorted(cd, days, side="right") - 1
        has = i >= 0
        n += has
        k += has & (st[np.clip(i, 0, None)] == 1)
    return k, n


def grade(site, extra_presets=None):
    """{"since", "to", "months", "factors": {key: record}, "presets": {key: record}}, each record
    {"3m": {...}, "12m": {...}} (see rec())."""
    from .factors import PRESETS, offhigh_points
    PRESETS = list(PRESETS) + list(extra_presets or [])
    from .engine import _read, PRICE_DIR
    stocks = _stocks(site)
    if not stocks:
        return {}
    cal = site.prices["^GSPC"]["close"].index
    last = len(cal) - 1 - HORIZONS[0]
    months = pd.Series(cal[:last + 1], index=cal[:last + 1]).groupby(cal[:last + 1].to_period("M")).last()
    dates = pd.DatetimeIndex([d for d in months.values if d >= START])
    try:
        fx = _read("CAD=X", PRICE_DIR)["close"]
    except Exception:
        fx = None
    # per stock: closes as arrays, the 200-day average, and where each month-end falls
    rows = {}
    for t in stocks:
        c = site.prices[t["sym"]]["close"]
        b = site.prices[bench_of(t)]["close"]
        rows[t["sym"]] = (t, c.values.astype(float), c.rolling(200).mean().values, c.index.searchsorted(dates, side="right") - 1,
                          b.values.astype(float), b.index.searchsorted(dates, side="right") - 1, c.rolling(252, min_periods=120).max().values)
    plays = {t["sym"]: _plays_share(site, t, dates) for t in stocks}
    # each call kept as (excess return, year, market), so a record can be split by market and by year
    hz = {h: {"f": {k: ([], []) for k in GRADED}, "p": {pk: ([], []) for pk, _, _ in PRESETS}} for h in HORIZONS}
    mkt = {t["sym"]: market(t) for t in stocks}
    names = {k: set() for k in GRADED}
    for di, d in enumerate(dates):
        raw = {k: {} for k in GRADED}
        fixed = {k: {} for k in GRADED}
        excess = {h: {} for h in HORIZONS}
        fxd = float(fx.iloc[fx.index.searchsorted(d, side="right") - 1]) if fx is not None and len(fx) else None
        for sym, (t, c, ma, pos, b, bpos, hi) in rows.items():
            i, j = pos[di], bpos[di]
            if i < 0 or j < 0 or c[i] <= 0 or b[j] <= 0:
                continue
            for h in HORIZONS:
                if i + h < len(c) and j + h < len(b):
                    excess[h][sym] = (c[i + h] / c[i] - 1) - (b[j + h] / b[j] - 1)
            if sym not in excess[HORIZONS[0]]:
                continue
            p0 = c[i]
            if i >= 199 and ma[i] > 0:
                raw["trend"][sym] = p0 / ma[i] - 1
            if i >= 252 and c[i - 252] > 0:
                raw["mom"][sym] = p0 / c[i - 252] - 1
            if hi[i] > 0:
                raw["offhigh"][sym] = p0 / hi[i] - 1
            k, n = plays[sym][0][di], plays[sym][1][di]
            if n >= 20:
                raw["plays"][sym] = k / n
            if secfund.has(t):
                r = secfund.ratios(t, p0, d, fxd)
                for key in COMPANY:
                    v = r.get(key)
                    if isinstance(v, str):
                        fixed[key][sym] = 0
                    elif v is not None:
                        lo, hi = BOUNDS.get(key, (-1e18, 1e18))
                        if lo <= v <= hi:
                            raw[key][sym] = v
        pts = {}
        for key in GRADED:
            p = dict(fixed[key])
            if key == "plays":
                p.update({s_: int(round(100 * v)) for s_, v in raw[key].items()})
            elif key == "offhigh":
                p.update({s_: offhigh_points(v) for s_, v in raw[key].items()})
            else:
                p.update(_rank(raw[key], key not in LOWER_BETTER))
            pts[key] = p
            names[key].update(p)
        scores = {}
        for pk, _, w in PRESETS:
            gw = {k: v for k, v in w.items() if k in GRADED}
            tot = sum(gw.values())
            if not tot:
                continue
            sc = {}
            for sym in excess[HORIZONS[0]]:
                have = [(wi, pts[k][sym]) for k, wi in gw.items() if sym in pts[k]]
                avail = sum(wi for wi, _ in have)
                if avail >= tot / 2:
                    sc[sym] = sum(wi * p for wi, p in have) / avail
            scores[pk] = sc
        yr = d.year
        for h in HORIZONS:
            ex = excess[h]
            for key in GRADED:
                buys, avoids = hz[h]["f"][key]
                for sym, v in pts[key].items():
                    if sym in ex:
                        if v >= BUY:
                            buys.append((ex[sym], yr, mkt[sym]))
                        elif v <= AVOID:
                            avoids.append((ex[sym], yr, mkt[sym]))
            for pk, sc in scores.items():
                buys, avoids = hz[h]["p"][pk]
                for sym, v in sc.items():
                    if sym in ex:
                        if v >= BUY:
                            buys.append((ex[sym], yr, mkt[sym]))
                        elif v <= AVOID:
                            avoids.append((ex[sym], yr, mkt[sym]))

    label = {63: "3m", 252: "12m"}

    def recs(buys, avoids):
        """A record for all names and one per market."""
        out = {"all": rec(buys, avoids)}
        for m in MARKETS:
            out[m] = rec([x for x in buys if x[2] == m], [x for x in avoids if x[2] == m])
        return out

    def by_h(lists):
        r = {h: recs(*lists[h]) for h in HORIZONS}
        out = {label[h]: r[h]["all"] for h in HORIZONS}
        for m in MARKETS:
            out[m] = {label[h]: r[h][m] for h in HORIZONS}
        return out
    factors = {k: by_h({h: hz[h]["f"][k] for h in HORIZONS}) | {"stocks": len(names[k])} for k in GRADED}
    for k, why in NO_HISTORY.items():
        factors[k] = {"why": why}
    presets = {}
    for pk, _, w in PRESETS:
        tot = sum(w.values())
        gw = sum(v for k, v in w.items() if k in GRADED)
        presets[pk] = by_h({h: hz[h]["p"][pk] for h in HORIZONS}) | {
            "graded_weight": round(100 * gw / tot) if tot else 0, "left_out": [k for k in w if k not in GRADED]}
    return {"since": dates[0].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d"), "months": len(dates),
            "built": dt.date.today().isoformat(), "bench": {"us": "SPY", "tsx": "XIU.TO"}, "factors": factors, "presets": presets}


YEAR_MIN = 10   # a year counts toward the range once it has this many Buys and this many Avoids


def year_range(buys, avoids):
    """The edge year by year: its mean and a rough 95% range (two standard errors of the yearly
    edges), so a record that rests on one good stretch shows a wide range. Calls a year apart
    overlap, so the range is a floor on the real uncertainty."""
    by = {}
    for x, y, _ in buys:
        by.setdefault(y, ([], []))[0].append(x)
    for x, y, _ in avoids:
        by.setdefault(y, ([], []))[1].append(x)
    edges = {y: float((np.array(b) > 0).mean() - (np.array(a) > 0).mean()) for y, (b, a) in sorted(by.items())
             if len(b) >= YEAR_MIN and len(a) >= YEAR_MIN}
    if len(edges) < 3:
        return None
    v = np.array(list(edges.values()))
    se = float(v.std(ddof=1) / np.sqrt(len(v)))
    return {"n": len(v), "mean": round(float(v.mean()), 4), "pm": round(2 * se, 4), "pos": int((v > 0).sum()),
            "years": {str(y): round(x, 4) for y, x in edges.items()}}


def rec(buys, avoids):
    """{"buys", "avoids", "buys_beat", "avoids_beat", "edge", "right", "buy_med", "avoid_med", "spread",
    "yr": year_range()}; buys and avoids are (excess return, year, market) tuples."""
    if not buys or not avoids:
        return None
    b, a = np.array([x[0] for x in buys]), np.array([x[0] for x in avoids])
    bb, ab = float((b > 0).mean()), float((a > 0).mean())
    return {"buys": len(b), "avoids": len(a), "buys_beat": round(bb, 4), "avoids_beat": round(ab, 4),
            "edge": round(bb - ab, 4), "right": round((float((b > 0).sum()) + float((a < 0).sum())) / (len(b) + len(a)), 4),
            "buy_med": round(float(np.median(b)), 4), "avoid_med": round(float(np.median(a)), 4),
            "spread": round(float(np.median(b) - np.median(a)), 4), "yr": year_range(buys, avoids)}


def cached(site):
    g = site.__dict__.get("_factorgrade")
    if g is None:
        try:
            g = grade(site)
        except Exception as ex:      # grading must never stop a build
            print("factor grading skipped:", ex)
            g = {}
        site.__dict__["_factorgrade"] = g
    return g


def grade_json(site):
    return json.dumps(cached(site), separators=(",", ":"))
