"""The standard signal's day-by-day path, rebuilt point-in-time (nothing stored).

For every covered stock and every session since a start date, the points the standard weights use
(plays in, off the high, trend) exactly as the signal would have scored them that evening: prices to
that close and the plays' calls to that close. From the path come:

* the market guard (factors.GUARD): while a stock's market (its bench index) is 15% or more below
  its own 1-year high, the price factors stand down and the rest of the weights decide;
* the sticky calls: a Buy holds until the score falls below the middle line (50), a Sell until it
  rises above it, instead of flipping back at the Buy and Sell lines. The state depends on the path,
  so it's run from WARMUP, long enough before today for the starting state not to matter;
* the weekly scorecard (scorecard.py), which grades each day's calls with the rules in force that day.

Both rules are model version 3 (factors.MODEL), live from factors.MODEL3_SINCE.
"""
import numpy as np
import pandas as pd

from .content import TICKERS

WARMUP = pd.Timestamp("2025-01-01")


def _names(site):
    """Every covered name, as factors.compute ranks them (indexes and funds included), so the path's
    trend points match the stock page's."""
    return [t for t in TICKERS if (t["sym"], "buy-and-hold") in site.R and t["sym"] in (site.prices or {})]


def bench_drawdowns(site, dates):
    """{bench sym: Series of how far below its 1-year high the index closed, on each date}."""
    out = {}
    for b in {t.get("bench") for t in TICKERS if t.get("bench")}:
        c = (site.prices or {}).get(b, {}).get("close") if site.prices else None
        if c is None or not len(c):
            continue
        dd = c / c.rolling(252, min_periods=120).max() - 1
        out[b] = dd.reindex(dates, method="ffill")
    return out


def daily_path(site, since=WARMUP):
    """DataFrame (sym, d, p, plays, offhigh, trend points, guard, score_plain, score, call_plain, call):
    score is the guarded score, call the sticky call on it; *_plain are the plain Buy/Sell-line calls
    on the unguarded score (the rules before MODEL3_SINCE)."""
    from .factorgrade import _plays_share
    from .factors import DEFAULT, BUY, SELL, GUARD, offhigh_points, _rnd, PRICE_KEYS
    key = ("_callpath", str(since.date()))
    got = site.__dict__.get(key)
    if got is not None:
        return got
    spy = site.prices["SPY"]["close"]
    dates = spy.index[(spy.index >= since) & (spy.index <= pd.Timestamp(site.asof))]   # to the engine's close, never past it
    bdd = bench_drawdowns(site, dates)
    rows = []
    for t in _names(site):
        c = site.prices[t["sym"]]["close"]
        pos = c.index.searchsorted(dates, side="right") - 1
        cv = c.values.astype(float)
        hi = c.rolling(252, min_periods=120).max().values
        ma = c.rolling(200).mean().values
        k, n = _plays_share(site, t, dates)
        g = bdd.get(t.get("bench"))
        for i, d in enumerate(dates):
            j = pos[i]
            if j < 120 or c.index[j] != d or cv[j] <= 0:
                continue
            gd = float(g.iloc[i]) if g is not None and pd.notna(g.iloc[i]) else np.nan
            rows.append({"sym": t["sym"], "s": t["short"], "u": t["slug"], "g": t["group"], "cur": t.get("cur", "$"), "b": t.get("bench"), "d": d, "p": cv[j],
                         "plays": (100 * k[i] / n[i]) if n[i] >= 20 else np.nan,
                         "offhigh": offhigh_points(cv[j] / hi[j] - 1) if hi[j] > 0 else np.nan,
                         "gap": cv[j] / ma[j] - 1 if j >= 199 and ma[j] > 0 else np.nan,
                         "bdd": gd, "guard": bool(gd <= -GUARD) if pd.notna(gd) else False})
    df = pd.DataFrame(rows)
    if not len(df):
        site.__dict__[key] = df
        return df
    # trend points rank each day's gap among the public names; a private (reader-requested) name is placed among
    # them without joining, as factors.compute does, so adding one never moves a public stock's path
    private = {t["sym"] for t in _names(site) if t.get("requested")}
    pv = df.sym.isin(private)
    df["trend"] = np.nan
    if (~pv).any():
        df.loc[~pv, "trend"] = df[~pv].groupby("d")["gap"].transform(lambda x: (100 * (x.rank(method="average") - 1) / (len(x) - 1)).round())
    if pv.any():
        from .factors import _rank_at
        pub = {d: sorted(g.dropna().tolist()) for d, g in df[~pv].groupby("d")["gap"]}
        df.loc[pv, "trend"] = [(_rank_at(gp, pub.get(d, []), len(pub.get(d, [])) + 1) if pd.notna(gp) and pub.get(d) else np.nan)
                               for d, gp in zip(df.loc[pv, "d"], df.loc[pv, "gap"])]
    pts = {"plays": df.plays.round(), "offhigh": df.offhigh, "trend": df.trend}
    missing = [k_ for k_ in DEFAULT if k_ not in pts]
    if missing:                 # a new standard factor needs its day-by-day points here before it can be graded or held
        raise ValueError(f"callpath: no daily points for the standard factor(s) {missing}; add them to daily_path")

    def weighted(keys):
        num = pd.Series(0.0, index=df.index)
        have = pd.Series(0.0, index=df.index)
        tot = 0
        for k_ in keys:
            w = DEFAULT.get(k_, 0)
            if not w or k_ not in pts:
                continue
            tot += w
            ok = pts[k_].notna()
            num += np.where(ok, pts[k_] * w, 0)
            have += np.where(ok, w, 0)
        sc = (num / have.replace(0, np.nan)).map(lambda v: _rnd(v) if pd.notna(v) else np.nan)
        sc[have < tot / 2] = np.nan
        return sc
    plain = weighted(list(DEFAULT))
    guarded = weighted([k_ for k_ in DEFAULT if k_ not in PRICE_KEYS])
    df["score_plain"] = plain
    df["score"] = np.where(df.guard, guarded, plain)
    df.loc[df.score.isna() & ~df.guard, "score"] = np.nan
    call = lambda s: np.select([s >= BUY, s <= SELL], [1, -1], 0)
    df["call_plain"] = call(df.score_plain)
    df.loc[df.score_plain.isna(), "call_plain"] = np.nan
    df["call"] = sticky(df, "score", BUY, SELL)
    site.__dict__[key] = df
    return df


def sticky(df, col, buy, sell):
    """The sticky call along each stock's path: hold a Buy until the score drops below the middle
    line, a Sell until it rises above it (modelcompare.sticky, the version tested since 2006)."""
    mid = (buy + sell) / 2.0
    out = pd.Series(np.nan, index=df.index)
    for _, idx in df.groupby("sym").groups.items():
        idx = df.loc[idx].sort_values("d").index
        prev = None
        for ix in idx:
            sc = df.at[ix, col]
            if pd.isna(sc):
                prev = None
                continue
            c = 1 if sc >= buy else -1 if sc <= sell else 0
            if prev == 1 and c != 1 and sc >= mid:
                c = 1
            elif prev == -1 and c != -1 and sc <= mid:
                c = -1
            out[ix] = c
            prev = c
    return out


def today(site):
    """{sym: {"call": sticky call, "plain": the plain call on the same score, "score", "guard", "bdd"}} at the latest close."""
    df = daily_path(site)
    if not len(df):
        return {}
    from .factors import BUY, SELL
    T = df.d.max()
    x = df[df.d == T]
    out = {}
    for _, r in x.iterrows():
        plain = None if pd.isna(r.score) else (1 if r.score >= BUY else -1 if r.score <= SELL else 0)
        out[r.sym] = {"call": None if pd.isna(r.call) else int(r.call), "plain": plain, "score": None if pd.isna(r.score) else int(r.score),
                      "guard": bool(r.guard), "bdd": None if pd.isna(r.bdd) else float(r.bdd)}
    return out
