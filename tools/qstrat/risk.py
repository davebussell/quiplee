"""Crash exposure: the Hertz lens.

Hertz didn't fall 90% in 2020 because its cars stopped being useful. It fell
because a sudden macro shock met a balance sheet loaded with debt. This module
measures both halves for every ticker, from data Quiplee already has:

  market sensitivity  beta and downside capture against its benchmark index
  crash history       how far it fell in each past market crash vs its index
  run-up              Greenwood, Shleifer & You (2019): two-year run-ups of 100%+
                      crashed 40%+ within two years about half the time
  balance sheet       debt to equity, net debt to EBITDA, interest cover, cash

The result is a plain score with every component shown. It describes how a
stock has behaved and how fragile it looks; it is not a forecast.
"""
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FUND_DIR = os.path.join(ROOT, "data", "fundamentals")

# S&P 500 peak and trough dates (Yardeni bear-market tables)
CRASHES = [
    ("dotcom", "Dot-com bust", "2000-03-24", "2002-10-09"),
    ("gfc", "Financial crisis", "2007-10-09", "2009-03-09"),
    ("covid", "COVID crash", "2020-02-19", "2020-03-23"),
    ("bear2022", "2022 bear market", "2022-01-03", "2022-10-12"),
]


def load_fundamentals(tickers):
    out = {}
    for t in tickers:
        p = os.path.join(FUND_DIR, t["slug"] + ".json")
        if os.path.exists(p):
            try:
                out[t["sym"]] = json.load(open(p))
            except Exception:
                pass
    return out


def num(v):
    if v is None or isinstance(v, str):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def crash_window(close, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if close.index[0] > start + pd.Timedelta(days=7):
        return None
    pre = close[close.index <= start]
    if not len(pre):
        return None
    p0 = float(pre.iloc[-1])
    win = close[(close.index >= start) & (close.index <= end)]
    if not len(win):
        return None
    low_i = int(np.argmin(win.values))
    low, low_d = float(win.iloc[low_i]), win.index[low_i]
    after = close[close.index > low_d]
    rec = after[after >= p0]
    return {"dd": low / p0 - 1, "low_date": low_d, "recovered": rec.index[0] if len(rec) else None}


def weekly(close):
    return close.groupby(close.index.to_period("W-FRI")).last()


def beta_and_capture(close, bench, years=3):
    if bench is None or len(close) < 120:
        return None, None
    end = close.index[-1]
    c = close[close.index > end - pd.DateOffset(years=years)]
    b = bench[bench.index > end - pd.DateOffset(years=years)]
    w = pd.concat([weekly(c).pct_change(), weekly(b).pct_change()], axis=1).dropna()
    beta = None
    if len(w) >= 40 and w.iloc[:, 1].var() > 0:
        beta = float(w.cov().iloc[0, 1] / w.iloc[:, 1].var())
    m = pd.concat([c.groupby(c.index.to_period("M")).last().pct_change(),
                   b.groupby(b.index.to_period("M")).last().pct_change()], axis=1).dropna()
    down = m[m.iloc[:, 1] < 0]
    cap = float(down.iloc[:, 0].mean() / down.iloc[:, 1].mean()) if len(down) >= 6 else None
    return beta, cap


def runup(close):
    end = close.index[-1]
    past = close[close.index <= end - pd.DateOffset(years=2)]
    if not len(past):
        return None, None
    r2 = float(close.iloc[-1] / past.iloc[-1] - 1)
    one = close[close.index <= end - pd.DateOffset(years=1)]
    accel = None
    if len(one):
        r_recent = float(close.iloc[-1] / one.iloc[-1] - 1)
        r_prior = float(one.iloc[-1] / past.iloc[-1] - 1)
        accel = r_recent - r_prior
    return r2, accel


def assess(t, close, bench_close, fund):
    """Crash-exposure facts and a 0–10 score for one ticker."""
    beta, capture = beta_and_capture(close, bench_close)
    crashes = []
    for key, label, s, e in CRASHES:
        mine = crash_window(close, s, e)
        if mine is None:
            continue
        idx = crash_window(bench_close, s, e) if bench_close is not None else None
        crashes.append({"key": key, "label": label, "start": s, "end": e, "dd": mine["dd"], "low_date": mine["low_date"],
                        "recovered": mine["recovered"], "bench_dd": idx["dd"] if idx else None})
    r2, accel = runup(close)
    ret = close.pct_change().dropna()
    vol = float(ret[-252:].std() * math.sqrt(365 if t["crypto"] else 252)) if len(ret) > 60 else None
    hi = close[close.index > close.index[-1] - pd.DateOffset(weeks=52)].max()
    off_high = float(close.iloc[-1] / hi - 1) if hi else None

    f = fund or {}
    equity = num(f.get("equity"))
    debt = num(f.get("totalDebt")) or num(f.get("total_debt_bs"))
    cash = num(f.get("totalCash")) or num(f.get("cash_bs"))
    ebitda = num(f.get("ebitda"))
    de = (debt / equity) if (debt is not None and equity and equity > 0) else None
    neg_equity = equity is not None and equity <= 0
    nd_ebitda = ((debt - (cash or 0)) / ebitda) if (debt is not None and ebitda and ebitda > 0) else None
    cover = num(f.get("interest_cover"))
    current = num(f.get("currentRatio"))

    pts, why = {}, []
    s_mkt = 0
    if beta is not None:
        s_mkt += 2 if beta > 1.5 else 1 if beta > 1.1 else 0
    if capture is not None:
        s_mkt += 1 if capture > 1.3 else 0
    pts["market"] = min(s_mkt, 3)
    ratios = [c["dd"] / c["bench_dd"] for c in crashes if c["bench_dd"] and c["bench_dd"] < -0.05]
    avg_ratio = float(np.mean(ratios)) if ratios else None
    pts["history"] = (2 if avg_ratio > 1.5 else 1 if avg_ratio > 1.1 else 0) if avg_ratio is not None else 0
    s_bs = 0
    if fund:
        if neg_equity or (de is not None and de > 3) or (cover is not None and cover < 2):
            s_bs = 3
        elif (de is not None and de > 1.5) or (cover is not None and cover < 4) or (nd_ebitda is not None and nd_ebitda > 4):
            s_bs = 2 if (nd_ebitda is not None and nd_ebitda > 4) else 1
    pts["balance"] = s_bs
    pts["runup"] = (2 if r2 > 1.5 else 1 if r2 > 1.0 else 0) if r2 is not None else 0
    score = sum(pts.values())
    level = "Very high" if score >= 7 else "High" if score >= 5 else "Moderate" if score >= 3 else "Low"

    if beta is not None and beta > 1.1:
        why.append(f"moves about {beta:.1f}× its index")
    if avg_ratio is not None and avg_ratio > 1.1:
        why.append(f"fell about {avg_ratio:.1f}× as far as its index in past crashes")
    if neg_equity:
        why.append("owes more than it owns (negative equity)")
    elif de is not None and de > 1.5:
        why.append(f"carries {de:.1f}× as much debt as equity")
    if cover is not None and cover < 4:
        why.append(f"operating profit covers interest only {max(cover, 0):.1f}×" if cover > 0 else "operating profit doesn't cover its interest")
    if r2 is not None and r2 > 1.0:
        why.append(f"is up {r2 * 100:.0f}% in two years, a run-up size that crashed about half the time in history")
    return {
        "beta": beta, "capture": capture, "crashes": crashes, "avg_ratio": avg_ratio, "runup2y": r2, "accel": accel,
        "vol": vol, "off_high": off_high, "de": de, "neg_equity": neg_equity, "nd_ebitda": nd_ebitda, "cover": cover,
        "current": current, "debt": debt, "cash": cash, "equity": equity, "points": pts, "score": score, "level": level,
        "why": why, "has_fund": bool(fund),
    }
