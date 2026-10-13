"""Grading Your signal's factors and presets the way the plays are graded.

At every month-end since START, each stock gets its points on each factor exactly as Your
signal would have scored it then, from numbers public at the time: prices up to that close,
the plays' calls up to that close, and SEC filings filed by that date (secfund). A factor
"says buy" at 60 points or more and "says avoid" at 40 or less. Each call is checked against the stock's market (the S&P 500,
or the TSX for Canadian names) over the next three months and the next year: how often the
buys beat the market, how often the avoids did, and the gap between the two (the edge).
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

START = pd.Timestamp("2011-01-01")
HORIZONS = (63, 252)    # sessions: about three months and a year
BUY, AVOID = 60, 40
COMPANY = ("pe", "ps", "pb", "dy", "eg", "rg", "pm", "roe", "de")
GRADED = ("plays", "trend", "mom") + COMPANY
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
    return [t for t in TICKERS if is_stock(t) and (t["sym"], "buy-and-hold") in site.R and t.get("bench") in site.prices
            and not t.get("requested") and t["sym"] in site.prices]


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


def grade(site):
    """{"since", "to", "months", "factors": {key: record}, "presets": {key: record}}, each record
    {"3m": {...}, "12m": {...}} (see rec())."""
    from .factors import PRESETS
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
        b = site.prices[t["bench"]]["close"]
        rows[t["sym"]] = (t, c.values.astype(float), c.rolling(200).mean().values, c.index.searchsorted(dates, side="right") - 1,
                          b.values.astype(float), b.index.searchsorted(dates, side="right") - 1)
    plays = {t["sym"]: _plays_share(site, t, dates) for t in stocks}
    hz = {h: {"f": {k: ([], []) for k in GRADED}, "p": {pk: ([], []) for pk, _, _ in PRESETS}} for h in HORIZONS}
    names = {k: set() for k in GRADED}
    for di, d in enumerate(dates):
        raw = {k: {} for k in GRADED}
        fixed = {k: {} for k in GRADED}
        excess = {h: {} for h in HORIZONS}
        fxd = float(fx.iloc[fx.index.searchsorted(d, side="right") - 1]) if fx is not None and len(fx) else None
        for sym, (t, c, ma, pos, b, bpos) in rows.items():
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
            p.update({s_: int(round(100 * v)) for s_, v in raw[key].items()} if key == "plays" else _rank(raw[key], key not in LOWER_BETTER))
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
        for h in HORIZONS:
            ex = excess[h]
            for key in GRADED:
                buys, avoids = hz[h]["f"][key]
                for sym, v in pts[key].items():
                    if sym in ex:
                        if v >= BUY:
                            buys.append(ex[sym])
                        elif v <= AVOID:
                            avoids.append(ex[sym])
            for pk, sc in scores.items():
                buys, avoids = hz[h]["p"][pk]
                for sym, v in sc.items():
                    if sym in ex:
                        if v >= BUY:
                            buys.append(ex[sym])
                        elif v <= AVOID:
                            avoids.append(ex[sym])

    def rec(buys, avoids):
        if not buys or not avoids:
            return None
        b, a = np.array(buys), np.array(avoids)
        bb, ab = float((b > 0).mean()), float((a > 0).mean())
        return {"buys": len(b), "avoids": len(a), "buys_beat": round(bb, 4), "avoids_beat": round(ab, 4),
                "edge": round(bb - ab, 4), "right": round((float((b > 0).sum()) + float((a < 0).sum())) / (len(b) + len(a)), 4),
                "buy_med": round(float(np.median(b)), 4), "avoid_med": round(float(np.median(a)), 4),
                "spread": round(float(np.median(b) - np.median(a)), 4)}
    label = {63: "3m", 252: "12m"}
    factors = {k: {label[h]: rec(*hz[h]["f"][k]) for h in HORIZONS} | {"stocks": len(names[k])} for k in GRADED}
    for k, why in NO_HISTORY.items():
        factors[k] = {"why": why}
    presets = {}
    for pk, _, w in PRESETS:
        tot = sum(w.values())
        gw = sum(v for k, v in w.items() if k in GRADED)
        presets[pk] = {label[h]: rec(*hz[h]["p"][pk]) for h in HORIZONS} | {
            "graded_weight": round(100 * gw / tot) if tot else 0, "left_out": [k for k in w if k not in GRADED]}
    return {"since": dates[0].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d"), "months": len(dates),
            "built": dt.date.today().isoformat(), "factors": factors, "presets": presets}


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
