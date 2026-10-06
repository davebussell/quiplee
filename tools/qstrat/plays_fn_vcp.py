"""Rule code for the volume, calendar and pattern plays added in October 2026 (the move to 100 plays).

Same contract as plays_fn: each function takes finished bars (open, high, low,
close, volume, hc) and a context dict and returns res(state, lines, panel, **extra).
States are decided on a bar's close and acted on at the next session.
"""
import datetime as dt

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as _win

from . import ind
from .cal import nyse_holidays
from .calendar_data import FOMC, FULL_MOONS
from .plays_fn import latch, level, ok, res, panel, _ext, _cal_result


# ---------------------------------------------------------------- helpers
def _arr(s):
    return s.to_numpy(dtype=float)


def _bars(df):
    """Bar number (0, 1, 2 ...) as a Series, for warm-up gates."""
    return pd.Series(np.arange(len(df)), index=df.index)


def _rsum(s, n):
    """Exact rolling sum over n bars (no running total, so a short tail of the
    history gives exactly the same values as the full history)."""
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = _win(x, n).sum(axis=1)
    return pd.Series(out, index=s.index)


def _days(idx):
    """Calendar-day numbers (days since 1970-01-01) for a DatetimeIndex."""
    return idx.values.astype("datetime64[D]").astype(np.int64)


# ================================================================= volume
def nvi(df, ctx):
    """Fosback's Negative Volume Index against its 255-day EMA."""
    c, v = _arr(df.close), _arr(df.volume)
    ratio = np.ones(len(c))
    if len(c) > 1:
        ratio[1:] = np.where(v[1:] < v[:-1], c[1:] / c[:-1], 1.0)
    nv = pd.Series(1000.0 * np.cumprod(ratio), index=df.index)
    sig = ind.ema(nv, 255)
    st = level(nv > sig, nv < sig, _bars(df) >= 255)
    return res(st, panel=panel("Negative Volume Index", [("NVI", nv, "s1"), ("255-day EMA", sig, "s2")]))


def force_index(df, ctx):
    """Elder's Force Index: 13-day EMA of (close change x volume), above or below zero."""
    f13 = ind.ema(df.close.diff() * df.volume, 13)
    st = level(f13 > 0, f13 < 0, ok(f13) & (_bars(df) >= 26))
    return res(st, panel=panel("Force Index (13-day EMA)", [("Force Index", f13, "s1")], levels=[0]))


def _vwma(df, n):
    return _rsum(df.close * df.volume, n) / _rsum(df.volume, n).replace(0, np.nan)


def buff(df, ctx):
    """Dormeier's Buff Averages: 5-day VWMA against the 20-day VWMA."""
    f, s = _vwma(df, 5), _vwma(df, 20)
    st = level(f > s, f < s, ok(f, s))
    return res(st, [("5-day VWMA", f, "s1"), ("20-day VWMA", s, "s2")])


def chaikin_osc(df, ctx):
    """Chaikin Oscillator: 3-day minus 10-day EMA of the Accumulation/Distribution line."""
    h, l_, c = df.high, df.low, df.close
    mfm = (((c - l_) - (h - c)) / (h - l_).replace(0, np.nan)).fillna(0.0)
    adl = (mfm * df.volume).cumsum()
    co = ind.ema(adl, 3) - ind.ema(adl, 10)
    st = level(co > 0, co < 0, _bars(df) >= 20)
    return res(st, panel=panel("Chaikin Oscillator (3, 10)", [("Oscillator", co, "s1")], levels=[0]))


def vfi(df, ctx):
    """Katsanos' Volume Flow Indicator (130, 0.2, 2.5, 3) above or below zero."""
    c, v = df.close, df.volume
    tp = (df.high + df.low + c) / 3
    inter = np.log(tp).diff()
    vinter = inter.rolling(30).std(ddof=0)        # StdDev in the published TradeStation/MetaStock code is the population form
    cutoff = 0.2 * vinter * c
    vave = ind.sma(v, 130).shift(1)
    vc = np.minimum(v, 2.5 * vave)
    mf = tp.diff()
    vcp = pd.Series(np.where(mf > cutoff, vc, np.where(mf < -cutoff, -vc, 0.0)), index=df.index)
    vcp = vcp.where(cutoff.notna() & vave.notna())
    raw = _rsum(vcp, 130) / vave.replace(0, np.nan)
    vf = ind.ema(raw, 3)
    st = level(vf > 0, vf < 0, ok(raw))
    return res(st, panel=panel("Volume Flow Indicator (130)", [("VFI", vf, "s1")], levels=[0]))


def _klinger(df):
    h, l_, c, v = _arr(df.high), _arr(df.low), _arr(df.close), _arr(df.volume)
    n = len(c)
    hlc = h + l_ + c
    trend = np.full(n, -1.0)
    if n > 1:
        trend[1:] = np.where(hlc[1:] > hlc[:-1], 1.0, -1.0)
    dm = h - l_
    # cm: dm summed over the current run of same-direction days, plus the day before
    # the run started (cm[t] = cm[t-1] + dm[t] if the trend held, else dm[t-1] + dm[t]).
    start = np.r_[True, trend[1:] != trend[:-1]] if n else np.zeros(0, dtype=bool)
    run = np.cumsum(start) - 1
    cs = np.cumsum(dm)
    csp = np.r_[0.0, 0.0, cs]                      # csp[k + 2] = cs[k]; cs[-1] = cs[-2] = 0
    base = csp[np.flatnonzero(start)]              # cs[s - 2] for a run starting at s
    cm = cs - base[run] if n else cs
    with np.errstate(divide="ignore", invalid="ignore"):
        vf = np.where(cm > 0, v * np.abs(2 * (dm / cm - 1)) * trend * 100, 0.0)
    vf = pd.Series(vf, index=df.index)
    kvo = ind.ema(vf, 34) - ind.ema(vf, 55)
    return kvo, ind.ema(kvo, 13)


def klinger(df, ctx):
    """Klinger Volume Oscillator (34, 55) against its 13-day trigger line."""
    kvo, sig = _klinger(df)
    st = level(kvo > sig, kvo < sig, _bars(df) >= 110)
    return res(st, panel=panel("Klinger Oscillator (34, 55, 13)", [("KVO", kvo, "s1"), ("Trigger", sig, "s2")], levels=[0]))


# ================================================================= calendar
def presidential(df, ctx):
    """Q4 of the midterm year through Q2 of the pre-election year."""
    idx, m, first, last = _ext(df, ctx)
    y = np.asarray(idx.year)
    setv = np.full(len(idx), np.nan)
    setv[(y % 4 == 2) & (m == 9) & (last == 1)] = 1.0      # midterm year: buy at the last September close
    setv[(y % 4 == 3) & (m == 6) & (last == 1)] = 0.0      # pre-election year: sell at the last June close
    y0, m0 = idx[0].year, idx[0].month
    start = 1.0 if (y0 % 4 == 2 and m0 >= 10) or (y0 % 4 == 3 and m0 <= 6) else 0.0
    return _cal_result(df, idx, setv, start)


def _nyse_pre_holidays(y0, y1):
    """The last NYSE session before each regular NYSE holiday, years y0..y1."""
    one = dt.timedelta(days=1)
    hol = set()
    for y in range(y0 - 1, y1 + 2):
        hs = set(nyse_holidays(y))
        if y < 1998:                                   # the NYSE first closed for MLK Day in 1998
            d = dt.date(y, 1, 1)
            d += dt.timedelta(days=(0 - d.weekday()) % 7)
            hs.discard(d + dt.timedelta(weeks=2))
        hol |= hs
    pre = set()
    for h in hol:
        d = h - one
        while d.weekday() >= 5 or d in hol:
            d -= one
        pre.add(d)
    return np.array(sorted(pre), dtype="datetime64[D]").astype(np.int64)


def pre_holiday(df, ctx):
    """Hold only for the last NYSE session before each regular NYSE holiday."""
    idx, m, first, last = _ext(df, ctx)
    pre = np.isin(_days(idx), _nyse_pre_holidays(idx[0].year, idx[-1].year))
    setv = np.full(len(idx), np.nan)
    setv[pre] = 0.0                                    # sell at the pre-holiday close
    setv[np.r_[pre[1:], False]] = 1.0                  # buy one session earlier (wins back-to-back cases)
    return _cal_result(df, idx, setv, 0.0)


def jan_barometer(df, ctx):
    """Month-end bars. SPY's January return decides February to December; always in for January."""
    px = df.close
    b = ctx["bench"] if ctx["bench"] is not None else px
    bv = _arr(b)
    idx = df.index
    m, y = np.asarray(idx.month), np.asarray(idx.year)
    n = len(idx)
    prev_dec = np.zeros(n, dtype=bool)
    if n > 1:
        prev_dec[1:] = (m[:-1] == 12) & (y[:-1] == y[1:] - 1)
    jan = (m == 1) & prev_dec
    prevb = np.r_[np.nan, bv[:-1]] if n else bv
    with np.errstate(divide="ignore", invalid="ignore"):
        jr = np.where(jan, bv / prevb - 1, np.nan)
    setv = np.full(n, np.nan)
    setv[m == 12] = 1.0                                # in for January while the new reading forms
    dec = jan & ~np.isnan(jr)
    setv[dec] = (jr[dec] > 0).astype(float)
    st = pd.Series(setv, index=idx).ffill()
    jan_line = pd.Series(jr, index=idx).ffill()
    return res(st, panel=panel("S&P 500 (SPY) January return", [("January return", jan_line, "s1")], levels=[0], fmt="pct"))


def weekend(df, ctx):
    """Out from the week's last close to the next week's first close."""
    idx, m, first, last = _ext(df, ctx)
    setv = np.full(len(idx), np.nan)
    if ctx["crypto"]:
        # crypto trades every day: skip the same Friday-close to Monday-close stretch as stocks
        wd = np.asarray(idx.weekday)
        setv[wd == 0] = 1.0
        setv[wd == 4] = 0.0
    else:
        wk = _days(idx) - np.asarray(idx.weekday)     # the Monday of each session's week
        new = wk[1:] != wk[:-1]
        firstw = np.r_[False, new]                     # the very first bar starts out
        lastw = np.r_[new, False]
        setv[firstw] = 1.0                             # buy at the week's first close
        setv[lastw] = 0.0                              # sell at the week's last close (wins a one-session week)
    return _cal_result(df, idx, setv, 0.0)


_FOMC_D = np.array(FOMC, dtype="datetime64[D]").astype(np.int64)


def pre_fomc(df, ctx):
    """Hold only for the session of each scheduled FOMC announcement."""
    idx, m, first, last = _ext(df, ctx)
    ann = np.isin(_days(idx), _FOMC_D)
    setv = np.full(len(idx), np.nan)
    setv[np.r_[ann[1:], False]] = 1.0                  # buy at the close before the announcement day
    setv[ann] = 0.0                                    # sell at the announcement-day close
    return _cal_result(df, idx, setv, 0.0)


_FM_D = np.array(FULL_MOONS, dtype="datetime64[D]").astype(np.int64)


def lunar(df, ctx):
    """Out for the 15 days centred on each full moon, in for the rest of the lunar month."""
    idx, m, first, last = _ext(df, ctx)
    d = _days(idx)
    k = len(_FM_D)
    j = np.searchsorted(_FM_D, d)
    prev = _FM_D[np.clip(j - 1, 0, k - 1)]
    nxt = _FM_D[np.clip(j, 0, k - 1)]
    use_prev = (j > 0) & ((j >= k) | (d - prev <= nxt - d))
    sd = np.where(use_prev, d - prev, d - nxt).astype(float)   # days from the nearest full moon: + after, - before
    sd[(d < _FM_D[0] - 14) | (d > _FM_D[-1] + 14)] = np.nan    # outside the table
    infull = np.where(np.isnan(sd), np.nan, (np.abs(sd) <= 7).astype(float))
    st = np.full(len(idx), np.nan)
    if len(idx) > 1:
        st[:-1] = 1.0 - infull[1:]                     # the call at a close is the position for the next session
        st[-1] = st[-2]
    s = pd.Series(st, index=idx)
    days = pd.Series(sd, index=idx).iloc[:len(df)]
    return res(s.iloc[:len(df)], panel=panel("Days from the nearest full moon", [("Days", days, "s1")], levels=[-7, 7], lo=-15, hi=15),
               calendar=s.dropna())


# ================================================================= pattern
def engulfing(df, ctx):
    """Nison's engulfing patterns: in on a bullish engulfing after a decline, out on a bearish one after a rise."""
    c, o = df.close, df.open
    c1, o1 = c.shift(1), o.shift(1)
    if ctx["crypto"]:
        o, o1 = c1, c.shift(2)                         # a 24-hour market's daily open is just the prior close
    dn, up = c1 < c.shift(6), c1 > c.shift(6)
    bull = (c1 < o1) & (c > o) & (o <= c1) & (c >= o1) & ((o < c1) | (c > o1)) & dn
    bear = (c1 > o1) & (c < o) & (o >= c1) & (c <= o1) & ((o > c1) | (c < o1)) & up
    valid = ok(c.shift(6))
    st = latch(bull, bear, valid)
    sig = pd.Series(np.where(bull, 1.0, np.where(bear, -1.0, 0.0)), index=df.index).where(valid)
    return res(st, panel=panel("Engulfing patterns (+1 bullish, −1 bearish)", [("Pattern", sig, "s1")], levels=[0], lo=-1, hi=1))


def hikkake(df, ctx):
    """Chesler's hikkake: buy the reversal after a false breakdown from an inside day."""
    hs, ls = df.high, df.low
    inside = (hs.shift(1) < hs.shift(2)) & (ls.shift(1) > ls.shift(2))      # bar t-1 inside bar t-2
    bullf = (inside & (hs < hs.shift(1)) & (ls < ls.shift(1))).tolist()
    bearf = (inside & (hs > hs.shift(1)) & (ls > ls.shift(1))).tolist()
    h, l_, c = hs.tolist(), ls.tolist(), df.close.tolist()
    n = len(c)
    nan = float("nan")
    st, trig, stops = [nan] * n, [nan] * n, [nan] * n
    state, stop = 0, 0.0
    b0, b_hi, b_lo = -1, 0.0, 0.0                      # live bullish setup: start bar, inside-day high, pattern low
    r0, r_lo = -1, 0.0                                 # live bearish setup: start bar, inside-day low
    for t in range(n):
        if bullf[t]:
            b0, b_hi, b_lo = t, h[t - 1], min(l_[t - 1], l_[t])
        if bearf[t]:
            r0, r_lo = t, l_[t - 1]
        if b0 >= 0 and t > b0 + 3:                     # confirmation window: the 3 bars after the false move
            b0 = -1
        if r0 >= 0 and t > r0 + 3:
            r0 = -1
        if b0 >= 0 and l_[t] < b_lo:
            b_lo = l_[t]
        if state == 0 and b0 >= 0 and t > b0 and c[t] > b_hi:
            state, stop, b0 = 1, b_lo, -1
        elif state == 1 and (c[t] < stop or (r0 >= 0 and t > r0 and c[t] < r_lo)):
            state, r0 = 0, -1
        if t >= 3:
            st[t] = state
            if state == 1:
                stops[t] = stop
            elif b0 >= 0:
                trig[t] = b_hi
    idx = df.index
    return res(pd.Series(st, index=idx, dtype=float),
               [("Inside-day high (buy trigger)", pd.Series(trig, index=idx, dtype=float), "s1"),
                ("Stop (pattern low)", pd.Series(stops, index=idx, dtype=float), "s2")])


def turtle_soup(df, ctx):
    """Raschke & Connors' Turtle Soup Plus One: buy the close back above an old 20-day low."""
    c, lo = _arr(df.close), _arr(df.low)
    n = len(c)
    pl = np.full(n, np.nan)                            # lowest low of the 20 sessions before this one
    age = np.full(n, np.nan)                           # sessions since that low was set (0 = the day before)
    if n > 20:
        w = _win(lo[:-1], 20)                          # row k covers low[k .. k+19], the window for bar k+20
        pl[20:] = w.min(axis=1)
        age[20:] = np.argmin(w[:, ::-1], axis=1)       # the most recent bar on ties
    with np.errstate(invalid="ignore"):
        day1 = (c < pl) & (age >= 2)                   # close under the old low, set at least 3 sessions back
        entry = np.zeros(n, dtype=bool)
        entry[1:] = day1[:-1] & (c[1:] > pl[:-1])      # day 2 closes back above that low
    st = np.zeros(n)
    st[:min(n, 21)] = np.nan
    stop_line = np.full(n, np.nan)
    free = 0
    for e in np.flatnonzero(entry):
        if e < free:
            continue
        stop = min(lo[e - 1], lo[e])
        end = n
        for k in range(1, 7):                          # out on a close under the stop, or after 6 sessions
            t = e + k
            if t >= n:
                break
            if c[t] < stop or k == 6:
                end = t
                break
        st[e:end] = 1.0
        stop_line[e:end] = stop
        free = end + 1
    idx = df.index
    return res(pd.Series(st, index=idx), [("Prior 20-day low", pd.Series(pl, index=idx), "s1"),
                                          ("Stop", pd.Series(stop_line, index=idx), "s2")])
