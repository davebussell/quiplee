"""Rule code for the momentum and mean-reversion plays added in October 2026 (the move to 100 plays).

Same contract as plays_fn: each function takes finished bars and a context dict
and returns res(state, lines, panel, **extra). See plays_fn's docstring.
"""
import math

import numpy as np
import pandas as pd

from . import ind
from .plays_fn import latch, level, ok, res, panel, _ext, _arr


def _from(s, n):
    """True from the n-th bar on (a warm-up gate for recursive indicators)."""
    return pd.Series(np.arange(len(s)), index=s.index) >= n


def _bench_or_self(df, ctx):
    """SPY closes on these bars, or the stock's own closes when the stock is SPY."""
    b = ctx.get("bench")
    return df.close if b is None else b


# ================================================================= momentum
def trix_cross(df, ctx):
    t3 = ind.ema(ind.ema(ind.ema(df.close, 15), 15), 15)
    trix = 100 * (t3 / t3.shift(1) - 1)
    sig = ind.ema(trix, 9)
    st = level(trix > sig, trix < sig, ok(trix, sig) & _from(trix, 100))
    return res(st, panel=panel("TRIX (15) and signal (9)", [("TRIX", trix, "s1"), ("Signal", sig, "s2")], levels=[0]))


def tsi_zero(df, ctx):
    pc = df.close.diff()
    num = ind.ema(ind.ema(pc, 25), 13)
    den = ind.ema(ind.ema(pc.abs(), 25), 13)
    tsi = 100 * num / den.replace(0, np.nan)
    st = level(tsi > 0, tsi < 0, ok(tsi) & _from(tsi, 100))
    return res(st, panel=panel("True Strength Index (25, 13)", [("TSI", tsi, "s1")], levels=[0]))


def keller_13612w(df, ctx):
    px = df.close

    def r(n):
        return px / px.shift(n) - 1

    score = (12 * r(1) + 4 * r(3) + 2 * r(6) + r(12)) / 4
    st = level(score > 0, score <= 0, ok(score))
    return res(st, panel=panel("13612W score: the 1, 3, 6 and 12-month returns at a yearly pace, averaged", [("13612W", score, "s1")],
                               levels=[0], fmt="pct"))


def market_state_mom(df, ctx):
    px = df.close
    mom = px.shift(1) / px.shift(12) - 1
    mkt_px = _bench_or_self(df, ctx)
    mkt = mkt_px / mkt_px.shift(36) - 1
    good = (mom > 0) & (mkt > 0)
    st = level(good, ~good, ok(mom, mkt))
    return res(st, panel=panel("Stock's 12-1 return and SPY's 3-year return",
                               [("Stock 12-1 return", mom, "s1"), ("SPY 36-month return", mkt, "s2")], levels=[0], fmt="pct"))


def frog_pan(df, ctx):
    """Daily bars, decided on the last session of each month: 12-1 return
    positive and more up days than down days in the same window."""
    _, _, _, last = _ext(df, ctx)
    n = len(df)
    c = _arr(df.close)
    me = np.flatnonzero(last[:n] == 1)
    st = np.full(n, np.nan)
    pret_s = np.full(n, np.nan)
    tilt_s = np.full(n, np.nan)
    if len(me) > 12:
        r = np.empty(n)
        r[0] = np.nan
        r[1:] = c[1:] / c[:-1] - 1
        cpos = np.cumsum(np.nan_to_num(r) > 0)
        cneg = np.cumsum(np.nan_to_num(r) < 0)
        j = np.arange(12, len(me))
        a, b = me[j - 12], me[j - 1]          # window: sessions after month-end t-12 through month-end t-1
        pret = c[b] / c[a] - 1
        days = (b - a).astype(float)
        share_up = (cpos[b] - cpos[a]) / days
        share_dn = (cneg[b] - cneg[a]) / days
        fid = np.sign(pret) * (share_dn - share_up)   # the paper's information discreteness
        dec = ((pret > 0) & (fid < 0)).astype(float)
        dec[np.isnan(pret)] = np.nan
        at = me[j]
        st[at] = dec
        pret_s[at] = pret
        tilt_s[at] = share_up - share_dn
        st = pd.Series(st).ffill().to_numpy(copy=True)
        pret_s = pd.Series(pret_s).ffill().to_numpy(copy=True)
        tilt_s = pd.Series(tilt_s).ffill().to_numpy(copy=True)
    idx = df.index
    return res(pd.Series(st, index=idx),
               panel=panel("12-1 return and up-day share minus down-day share (set at each month-end)",
                           [("12-1 return", pd.Series(pret_s, index=idx), "s1"),
                            ("Up days minus down days", pd.Series(tilt_s, index=idx), "s2")], levels=[0], fmt="pct"))


def pmo_cross(df, ctx):
    roc1 = df.close / df.close.shift(1) * 100 - 100
    s35 = ind.ema_a(roc1, 2 / 35)
    pmo = ind.ema_a(10 * s35, 2 / 20)
    sig = ind.ema(pmo, 10)
    st = level(pmo > sig, pmo < sig, ok(pmo, sig) & _from(pmo, 150))
    return res(st, panel=panel("Price Momentum Oscillator and 10-day signal", [("PMO", pmo, "s1"), ("Signal", sig, "s2")], levels=[0]))


# ================================================================= mean reversion
def _streak(c):
    """Consecutive up closes (+1, +2, ...), down closes (-1, -2, ...), 0 on an unchanged close."""
    d = np.nan_to_num(np.sign(np.diff(c, prepend=np.nan)))
    if not len(d):
        return d
    start = np.ones(len(d), dtype=bool)
    start[1:] = d[1:] != d[:-1]
    run_id = np.cumsum(start) - 1
    first = np.flatnonzero(start)
    length = np.arange(len(d)) - first[run_id] + 1
    return d * length


def _pct_rank(x, n):
    """Share (0-100) of the previous n values that are below the current one."""
    out = np.full(len(x), np.nan)
    if len(x) > n:
        w = np.lib.stride_tricks.sliding_window_view(x, n + 1)
        cur = w[:, -1:]
        cnt = (w[:, :-1] < cur).sum(axis=1).astype(float)
        bad = np.isnan(w).any(axis=1)
        cnt[bad] = np.nan
        out[n:] = 100.0 * cnt / n
    return out


def _connors_rsi(df):
    c = _arr(df.close)
    idx = df.index
    r3 = ind.rsi(df.close, 3)
    rs = ind.rsi(pd.Series(_streak(c), index=idx), 2)
    roc = np.full(len(c), np.nan)
    roc[1:] = c[1:] / c[:-1] - 1
    pr = pd.Series(_pct_rank(roc, 100), index=idx)
    return (r3 + rs + pr) / 3


def connorsrsi_pullback(df, ctx):
    crsi = _connors_rsi(df)
    adx = ind.dmi(df, 10)[2]
    rng = (df.high - df.low).replace(0, np.nan)
    pos = (df.close - df.low) / rng
    enter = (adx > 30) & (df.low <= 0.96 * df.close.shift(1)) & (pos <= 0.25) & (crsi < 10)
    exit_ = crsi > 70
    st = latch(enter, exit_, ok(crsi, adx) & _from(crsi, 150))
    return res(st, panel=panel("ConnorsRSI (3, 2, 100) and 10-day ADX", [("ConnorsRSI", crsi, "s1"), ("ADX (10)", adx, "s2")],
                               levels=[10, 30, 70], lo=0, hi=100))


def _laguerre_rsi(c, g=0.5):
    n = len(c)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    x = c.tolist()
    l0 = l1 = l2 = l3 = x[0]
    prev = np.nan
    for i in range(1, n):
        p0, p1, p2 = l0, l1, l2
        l0 = (1 - g) * x[i] + g * p0
        l1 = -g * l0 + p0 + g * l1
        l2 = -g * l1 + p1 + g * l2
        l3 = -g * l2 + p2 + g * l3
        cu = max(l0 - l1, 0.0) + max(l1 - l2, 0.0) + max(l2 - l3, 0.0)
        cd = max(l1 - l0, 0.0) + max(l2 - l1, 0.0) + max(l3 - l2, 0.0)
        if cu + cd != 0:
            prev = cu / (cu + cd)
        out[i] = prev
    return out


def laguerre_rsi(df, ctx):
    lr = pd.Series(_laguerre_rsi(_arr(df.close)), index=df.index)
    st = latch(ind.cross_up(lr, 0.2), ind.cross_dn(lr, 0.8), ok(lr.shift(1)) & _from(lr, 40))
    return res(st, panel=panel("Laguerre RSI (gamma 0.5)", [("Laguerre RSI", lr, "s1")], levels=[0.2, 0.8], lo=0, hi=1))


def stochrsi(df, ctx):
    r = ind.rsi(df.close, 14)
    lo, hi = ind.ll(r, 14), ind.hh(r, 14)
    s = (r - lo) / (hi - lo).replace(0, np.nan)
    st = latch(ind.cross_up(s, 0.2), ind.cross_dn(s, 0.8), ok(r.shift(14)) & _from(r, 40))
    return res(st, panel=panel("StochRSI (14)", [("StochRSI", s, "s1")], levels=[0.2, 0.8], lo=0, hi=1))


def ibs(df, ctx):
    v = (df.close - df.low) / (df.high - df.low).replace(0, np.nan)
    low = (v < 0.2).fillna(False)
    st = level(low, ~low, pd.Series(True, index=df.index))
    return res(st, panel=panel("Internal bar strength (0 = closed at the low)", [("IBS", v, "s1")], levels=[0.2], lo=0, hi=1))


def connors_pctb(df, ctx):
    px = df.close
    mid = ind.sma(px, 20)
    sd = px.rolling(20).std(ddof=0)
    lo, up = mid - 2 * sd, mid + 2 * sd
    pb = (px - lo) / (up - lo).replace(0, np.nan)
    s200 = ind.sma(px, 200)
    low3 = (pb < 0.2) & (pb.shift(1) < 0.2) & (pb.shift(2) < 0.2)
    st = latch((px > s200) & low3, pb > 0.8, ok(s200, pb.shift(2)))
    return res(st, [("200-day SMA", s200, "s1"), ("Lower band", lo, "s2"), ("Upper band", up, "s3")],
               panel=panel("Bollinger %b (20, 2)", [("%b", pb, "s1")], levels=[0.2, 0.8]))


def _fisher(df, n=10):
    """Ehlers' Fisher transform of the high-low midpoint's place in its n-day range."""
    mid = (df.high + df.low) / 2
    p = _arr(mid).tolist()
    mx = _arr(ind.hh(mid, n)).tolist()
    mn = _arr(ind.ll(mid, n)).tolist()
    fish = np.full(len(p), np.nan)
    v, f = 0.0, 0.0
    for i in range(n - 1, len(p)):
        rng = mx[i] - mn[i]
        x = (p[i] - mn[i]) / rng - 0.5 if rng > 0 else 0.0
        v = 0.33 * 2 * x + 0.67 * v
        if v > 0.99:
            v = 0.999
        elif v < -0.99:
            v = -0.999
        f = 0.5 * math.log((1 + v) / (1 - v)) + 0.5 * f
        fish[i] = f
    return fish


def fisher(df, ctx):
    f = pd.Series(_fisher(df, 10), index=df.index)
    trig = f.shift(1)
    st = level(f > trig, f < trig, ok(trig) & _from(f, 60))
    return res(st, panel=panel("Fisher transform (10)", [("Fisher", f, "s1"), ("Trigger (yesterday)", trig, "s2")], levels=[0]))


def st_reversal(df, ctx):
    r = df.close / df.close.shift(1) - 1
    if ctx.get("bench") is None:
        # SPY itself: a down month stands in for trailing the market
        rb = pd.Series(0.0, index=df.index).where(r.notna())
        series = [("SPY", r, "s1")]
    else:
        rb = ctx["bench"] / ctx["bench"].shift(1) - 1
        series = [("This stock", r, "s1"), ("SPY", rb, "s2")]
    lag = r < rb
    st = level(lag, ~lag, ok(r, rb))
    return res(st, panel=panel("Return for the month just ended", series, levels=[0], fmt="pct"))
