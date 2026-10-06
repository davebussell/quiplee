"""Rule code for the trend and breakout plays added in October 2026 (the move to 100 plays).

Same contract as plays_fn: each function takes finished bars and a context dict
and returns res(state, lines, panel, **extra). States are decided on a bar's
close and acted on at the next session; nothing looks past the bar it is on.
Recursive filters and stateful rules run as plain loops over Python floats,
with everything that can be precomputed done in numpy first.
"""
import math

import numpy as np
import pandas as pd

from . import ind
from .plays_fn import latch, level, ok, res, panel

_W = np.lib.stride_tricks.sliding_window_view


def _arr(s):
    return s.to_numpy(dtype=float)


def _n(df):
    return pd.Series(np.arange(len(df)), index=df.index)


def _s(x, idx):
    return pd.Series(x, index=idx)


# ================================================================= trend
def _mama(price, fast=0.5, slow=0.05):
    """Ehlers' MESA Adaptive Moving Average and its Following line (MAMA.pdf).

    A straight port of the EasyLanguage: every recursive variable starts at 0
    and the loop starts on the sixth bar (CurrentBar > 5). MAMA and FAMA are
    seeded with price instead of 0 so the first values are usable."""
    n = len(price)
    mama = np.full(n, np.nan)
    fama = np.full(n, np.nan)
    if n < 7:
        return mama, fama
    PAD = 10
    p = [0.0] * PAD + price.tolist()
    sm = [0.0] * (n + PAD)
    de = [0.0] * (n + PAD)
    i1 = [0.0] * (n + PAD)
    q1 = [0.0] * (n + PAD)
    i2p = q2p = rep = imp = per = phase = 0.0
    m = f = price[5]
    atan, deg = math.atan, 180.0 / math.pi
    a0, a1 = 0.0962, 0.5769
    for t in range(5 + PAD, n + PAD):
        sm[t] = (4 * p[t] + 3 * p[t - 1] + 2 * p[t - 2] + p[t - 3]) / 10
        adj = 0.075 * per + 0.54
        d = (a0 * sm[t] + a1 * sm[t - 2] - a1 * sm[t - 4] - a0 * sm[t - 6]) * adj
        de[t] = d
        q = (a0 * d + a1 * de[t - 2] - a1 * de[t - 4] - a0 * de[t - 6]) * adj
        q1[t] = q
        ii = de[t - 3]
        i1[t] = ii
        ji = (a0 * ii + a1 * i1[t - 2] - a1 * i1[t - 4] - a0 * i1[t - 6]) * adj
        jq = (a0 * q + a1 * q1[t - 2] - a1 * q1[t - 4] - a0 * q1[t - 6]) * adj
        i2 = 0.2 * (ii - jq) + 0.8 * i2p
        q2 = 0.2 * (q + ji) + 0.8 * q2p
        re = 0.2 * (i2 * i2p + q2 * q2p) + 0.8 * rep
        im = 0.2 * (i2 * q2p - q2 * i2p) + 0.8 * imp
        i2p, q2p, rep, imp = i2, q2, re, im
        pn = per
        if im != 0 and re != 0:
            a = atan(im / re) * deg
            if a != 0:
                pn = 360.0 / a
        if pn > 1.5 * per:
            pn = 1.5 * per
        if pn < 0.67 * per:
            pn = 0.67 * per
        if pn < 6:
            pn = 6.0
        if pn > 50:
            pn = 50.0
        per = 0.2 * pn + 0.8 * per
        ph = atan(q / ii) * deg if ii != 0 else phase
        dp = phase - ph
        phase = ph
        if dp < 1:
            dp = 1.0
        alpha = fast / dp
        if alpha < slow:
            alpha = slow
        m = alpha * p[t] + (1 - alpha) * m
        f = 0.5 * alpha * m + (1 - 0.5 * alpha) * f
        mama[t - PAD] = m
        fama[t - PAD] = f
    return mama, fama


def ehlers_mama(df, ctx):
    price = _arr((df.high + df.low) / 2)
    m, f = _mama(price)
    m, f = _s(m, df.index), _s(f, df.index)
    valid = ok(m, f) & (_n(df) >= 60)
    st = level(m > f, m < f, valid)
    return res(st, [("MAMA (0.5, 0.05)", m, "s1"), ("FAMA", f, "s2")])


def _stc(close, cycle=10, fast=23, slow=50, factor=0.5):
    """Schaff Trend Cycle, from Schaff's released code: a MACD line run through
    two rounds of a stochastic, each smoothed by half."""
    xmac = ind.ema(close, fast) - ind.ema(close, slow)
    lo1, hi1 = ind.ll(xmac, cycle), ind.hh(xmac, cycle)
    rng1 = hi1 - lo1
    frac1 = (100 * (xmac - lo1) / rng1).where(rng1 > 0)
    frac1 = frac1.ffill().where(lo1.notna()).fillna(0.0).where(lo1.notna())
    pf = frac1.ewm(alpha=factor, adjust=False).mean()
    lo2, hi2 = ind.ll(pf, cycle), ind.hh(pf, cycle)
    rng2 = hi2 - lo2
    frac2 = (100 * (pf - lo2) / rng2).where(rng2 > 0)
    frac2 = frac2.ffill().where(lo2.notna()).fillna(0.0).where(lo2.notna())
    return frac2.ewm(alpha=factor, adjust=False).mean()


def schaff_stc(df, ctx):
    stc = _stc(df.close)
    s1, s2 = stc.shift(1), stc.shift(2)
    turn_up = (stc > s1) & (s1 <= s2) & (s1 < 25)
    turn_dn = (stc < s1) & (s1 >= s2) & (s1 > 75)
    n = _n(df)
    # pending trigger levels: the latest setup bar, unless an opposite setup came after it
    last_up = n.where(turn_up).ffill()
    last_dn = n.where(turn_dn).ffill()
    buy_lv = df.high.where(turn_up).ffill()
    sell_lv = df.low.where(turn_dn).ffill()
    buy_on = last_up.notna() & ~(last_dn >= last_up)
    sell_on = last_dn.notna() & ~(last_up >= last_dn)
    buy_lv, sell_lv = buy_lv.where(buy_on), sell_lv.where(sell_on)
    # a setup arms the trigger for later closes only
    enter = df.close > buy_lv.shift(1)
    exit_ = df.close < sell_lv.shift(1)
    valid = ok(s2) & (n >= 150)
    st = latch(enter, exit_, valid)
    return res(st, [("Buy trigger (setup-day high)", buy_lv, "s1"), ("Sell trigger (setup-day low)", sell_lv, "s2")],
               panel=panel("Schaff Trend Cycle (10, 23, 50)", [("STC", stc, "s1")], levels=[25, 75], lo=0, hi=100))


def _zero_lag(close, length=32, gain_limit=22):
    """Ehlers & Way error-correcting EMA. The published code tries every gain
    from -GainLimit/10 to +GainLimit/10 in steps of 0.1 and keeps the one that
    leaves the smallest error; the error is linear in the gain, so the best grid
    gain is the nearest step to the exact solution (lower one on a tie)."""
    c = close.to_numpy(dtype=float)
    n = len(c)
    e = ind.ema(close, length).to_numpy(dtype=float)
    ec = np.full(n, np.nan)
    least = np.full(n, np.nan)
    if not n:
        return ec, e, least
    a = 2.0 / (length + 1)
    cl, el = c.tolist(), e.tolist()
    x = cl[0]
    ec[0], least[0] = x, 0.0
    ceil = math.ceil
    for t in range(1, n):
        ct = cl[t]
        base = a * el[t] + (1 - a) * x
        dd = ct - x
        if dd != 0:
            k = ceil((ct - base) / (a * dd) * 10 - 0.5)
            k = -gain_limit if k < -gain_limit else (gain_limit if k > gain_limit else k)
        else:
            k = -gain_limit
        x = base + a * (k / 10) * dd
        ec[t] = x
        least[t] = abs(ct - x)
    return ec, e, least


def ehlers_zero_lag(df, ctx):
    ec, e, least = _zero_lag(df.close, 32, 22)
    idx = df.index
    ec, e = _s(ec, idx), _s(e, idx)
    big = _s(100 * least / df.close.to_numpy(dtype=float), idx) > 0.75
    enter = ind.cross_up(ec, e) & big
    exit_ = ind.cross_dn(ec, e) & big
    st = latch(enter, exit_, _n(df) >= 100)
    return res(st, [("Error-corrected EMA (32)", ec, "s1"), ("EMA (32)", e, "s2")])


def dp_ittm(df, ctx):
    e20, e50 = ind.ema(df.close, 20), ind.ema(df.close, 50)
    st = level(e20 > e50, e20 < e50, _n(df) >= 100)
    return res(st, [("20-day EMA", e20, "s1"), ("50-day EMA", e50, "s2")])


def _week_key(idx, crypto):
    """Week number per session: weeks end on Friday for stocks, Sunday for crypto
    (the engine's W-FRI / W-SUN bars)."""
    d = np.asarray(idx.values.astype("datetime64[D]").astype(np.int64))
    return (d - (4 if crypto else 2)) // 7


def _weeks(df, ctx):
    """Weekly closes built from daily bars, and for each session the position of
    the latest week that had finished by that session's close (-1 if none).
    A week is finished on its last session; inside a week the previous week is
    the latest one known. For the frame's last row the next session (from
    ctx['future']) says whether the week ends today."""
    idx = df.index
    n = len(idx)
    if not n:
        return pd.Series(dtype=float), np.zeros(0, np.int64)
    crypto = bool(ctx.get("crypto"))
    key = _week_key(idx, crypto)
    brk = key[1:] != key[:-1]
    grp = np.cumsum(np.r_[True, brk]) - 1
    last = np.r_[brk, True]
    wclose = pd.Series(df.close.to_numpy(dtype=float)[last])
    fut = ctx.get("future")
    if fut is not None and len(fut):
        nxt = fut[fut > idx[-1]]
        done_wk = (not len(nxt)) or _week_key(nxt[:1], crypto)[0] != key[-1]
    else:
        done_wk = idx[-1].weekday() == (6 if crypto else 4)
    last[-1] = bool(done_wk)
    return wclose, np.where(last, grp, grp - 1)


def elder_triple(df, ctx):
    idx = df.index
    c, h, l_ = _arr(df.close), _arr(df.high), _arr(df.low)
    n = len(c)
    wclose, wi = _weeks(df, ctx)
    hw = ind.macd(wclose, 12, 26, 9)[2].to_numpy(dtype=float) if n else np.zeros(0)
    known = wi >= 35                      # enough finished weeks for the weekly MACD to settle
    hist_w = np.where(known, hw[np.maximum(wi, 0)], np.nan)
    prev_w = np.where(known, hw[np.maximum(wi - 1, 0)], np.nan)
    tide = hist_w > prev_w
    tide_known = known
    fi2 = _arr(ind.ema(df.close.diff() * df.volume, 2))
    wave = fi2 < 0
    st = np.full(n, np.nan)
    stop = np.full(n, np.nan)
    state, s_lv = 0, 0.0
    tl, wl, kl = tide.tolist(), wave.tolist(), tide_known.tolist()
    cl, hl, ll = c.tolist(), h.tolist(), l_.tolist()
    for i in range(1, n):
        if not kl[i - 1]:
            continue
        if state == 0:
            # screens 1 and 2 met yesterday, the tide still up today, and a close through yesterday's high
            if tl[i - 1] and wl[i - 1] and tl[i] and cl[i] > hl[i - 1]:
                state, s_lv = 1, min(ll[i], ll[i - 1])
        elif not tl[i] or cl[i] < s_lv:
            state = 0
        st[i] = state
        if state == 1:
            stop[i] = s_lv
    checks = []
    if n:
        checks = [("Weekly MACD histogram rising (the tide)", bool(tide[-1])),
                  ("2-day Force Index below zero (the pullback)", bool(wave[-1]))]
    return res(_s(st, idx), [("Protective stop", _s(stop, idx), "s1")],
               panel=panel("Weekly MACD histogram (12, 26, 9)", [("Histogram", _s(hist_w, idx), "s1")], levels=[0]),
               checks=checks)


def holy_grail(df, ctx):
    idx = df.index
    pdi, mdi, adx = ind.dmi(df, 14)
    e20 = ind.ema(df.close, 20)
    swing = df.high.rolling(20).max().shift(1)
    touch = (adx > 30) & (pdi > mdi) & (df.low <= e20)
    c, h, l_ = _arr(df.close), _arr(df.high), _arr(df.low)
    a, sw = _arr(adx), _arr(swing)
    n = len(c)
    valid = (ok(adx, swing) & (_n(df) >= 60)).to_numpy()
    tch = touch.to_numpy(dtype=bool)
    st = np.full(n, np.nan)
    stop, tgt = np.full(n, np.nan), np.full(n, np.nan)
    state, t_i, t_hi, t_lo, t_tg, s_lv, g_lv = 0, -10, 0.0, 0.0, 0.0, 0.0, 0.0
    for i in range(n):
        if not valid[i]:
            continue
        if state == 0:
            if 1 <= i - t_i <= 5 and a[i] > 30 and c[i] > t_hi:
                state, s_lv, g_lv = 1, t_lo, t_tg
                if c[i] >= g_lv:        # already at the target: no trade
                    state = 0
        elif c[i] < s_lv or c[i] >= g_lv:
            state = 0
        if tch[i]:
            t_i, t_hi, t_lo, t_tg = i, h[i], l_[i], sw[i]
        st[i] = state
        if state == 1:
            stop[i], tgt[i] = s_lv, g_lv
    return res(_s(st, idx), [("20-day EMA", e20, "s1"), ("Stop (pullback-day low)", _s(stop, idx), "s2"),
                             ("Target (prior swing high)", _s(tgt, idx), "s3")],
               panel=panel("ADX (14)", [("ADX", adx, "s1")], levels=[30], lo=0))


# ================================================================= breakout
def wilder_vol(df, ctx):
    idx = df.index
    c = _arr(df.close)
    a7 = _arr(ind.atr(df, 7))
    n = len(c)
    st = np.full(n, np.nan)
    sar = np.full(n, np.nan)
    if not n:
        return res(_s(st, idx))
    cl, al = c.tolist(), a7.tolist()
    state, sic = 0, cl[0]
    for i in range(1, n):
        x = cl[i]
        arc = 3.0 * al[i - 1]
        if arc != arc:          # ATR still warming up: track the low close
            sic = min(sic, x)
            continue
        if state == 1:
            if x < sic - arc:
                state, sic = 0, x
            elif x > sic:
                sic = x
        else:
            if x > sic + arc:
                state, sic = 1, x
            elif x < sic:
                sic = x
        st[i] = state
        sar[i] = sic - 3.0 * al[i] if state == 1 else sic + 3.0 * al[i]
    st[:20] = np.nan
    return res(_s(st, idx), [("Stop-and-reverse point", _s(sar, idx), "s1")])


def pf_double_top(df, ctx, box=0.02, rev=3):
    """Three-box-reversal point & figure from daily highs and lows (high-low
    method), with percentage boxes on a fixed log grid: box k is price 1.02**k."""
    idx = df.index
    B = math.log(1 + box)
    lh = np.log(_arr(df.high)) / B
    lo = np.log(_arr(df.low)) / B
    up = np.floor(lh + 1e-9).astype(np.int64).tolist()    # highest box the high reached
    dn = np.ceil(lo - 1e-9).astype(np.int64).tolist()     # lowest box the low reached
    n = len(up)
    st = np.full(n, np.nan)
    buy_lv, sell_lv = np.full(n, np.nan), np.full(n, np.nan)
    if not n:
        return res(_s(st, idx))
    col, top, bot, pxt, pob, state = 1, up[0], None, None, None, None
    for i in range(1, n):
        if col == 1:
            if up[i] > top:
                top = up[i]
            elif dn[i] <= top - rev:
                pxt, col, bot = top, -1, dn[i]
        else:
            if dn[i] < bot:
                bot = dn[i]
            elif up[i] >= bot + rev:
                pob, col, top = bot, 1, up[i]
        if col == 1 and pxt is not None and top > pxt:
            state = 1
        elif col == -1 and pob is not None and bot < pob:
            state = 0
        if state is None:
            continue
        st[i] = state
        # the intraday level that would flip the standing signal
        if state == 0 and pxt is not None:
            k = pxt + 1 if col == 1 else max(pxt + 1, bot + rev)
            buy_lv[i] = (1 + box) ** k
        elif state == 1 and pob is not None:
            k = pob - 1 if col == -1 else min(pob - 1, top - rev)
            sell_lv[i] = (1 + box) ** k
    return res(_s(st, idx), [("Double-top buy level", _s(buy_lv, idx), "s1"), ("Double-bottom sell level", _s(sell_lv, idx), "s2")])


def chande_kroll(df, ctx):
    tr = ind.true_range(df)
    tr.iloc[:1] = (df.high - df.low).iloc[:1]
    a10 = ind.sma(tr, 10)
    ls = (ind.hh(df.high, 10) - 3 * a10).rolling(20).max()
    ss = (ind.ll(df.low, 10) + 3 * a10).rolling(20).min()
    st = latch(df.close > np.maximum(ls, ss), df.close < ls, ok(ls, ss))
    return res(st, [("Long stop", ls, "s1"), ("Short stop", ss, "s2")])


def accel_bands(df, ctx):
    h, l_ = df.high, df.low
    w = (h - l_) / (h + l_)
    upper = ind.sma(h * (1 + 4 * w), 20)
    lower = ind.sma(l_ * (1 - 4 * w), 20)
    mid = ind.sma(df.close, 20)
    above = df.close > upper
    st = latch(above & above.shift(1, fill_value=False), df.close < upper, ok(upper.shift(1)))
    return res(st, [("Upper band", upper, "s1"), ("20-day SMA", mid, "s2"), ("Lower band", lower, "s3")])


def _mean_sd(s, n):
    """Rolling mean and population standard deviation computed window by window,
    so the values don't depend on how much history came before (pandas' running
    sums drift slightly with the start of the frame)."""
    x = s.to_numpy(dtype=float)
    m, sd = np.full(len(x), np.nan), np.full(len(x), np.nan)
    if len(x) >= n:
        w = _W(x, n)
        m[n - 1:] = w.mean(axis=1)
        sd[n - 1:] = w.std(axis=1)
    return pd.Series(m, index=s.index), pd.Series(sd, index=s.index)


def _linreg(s, n):
    """Least-squares line through the last n values, read at the latest bar."""
    y = s.to_numpy(dtype=float)
    out = np.full(len(y), np.nan)
    if len(y) >= n:
        w = _W(y, n)
        x = np.arange(n, dtype=float)
        xm = x - x.mean()
        b = (w @ xm) / (xm @ xm)
        out[n - 1:] = w.mean(axis=1) + b * xm[-1]
    return pd.Series(out, index=s.index)


def ttm_squeeze(df, ctx):
    c = df.close
    mid, sd = _mean_sd(c, 20)
    tr = ind.true_range(df)
    tr.iloc[:1] = (df.high - df.low).iloc[:1]
    rng = _mean_sd(tr, 20)[0]
    on = (2 * sd < 1.5 * rng).where(ok(sd, rng))
    fired = (on.shift(1) == 1) & (on == 0)
    delta = c - ((ind.hh(df.high, 20) + ind.ll(df.low, 20)) / 2 + mid) / 2
    mom = _linreg(delta, 20)
    m1, m2 = mom.shift(1), mom.shift(2)
    enter = fired & (mom > 0) & (mom > m1)
    exit_ = ((mom < m1) & (m1 < m2)) | (mom < 0)
    st = latch(enter, exit_, ok(m2, on.shift(1)))
    return res(st, [("Bollinger upper (20, 2)", mid + 2 * sd, "s1"), ("Keltner upper (20, 1.5 ATR)", mid + 1.5 * rng, "s2")],
               panel=panel("Squeeze momentum (20)", [("Momentum", mom, "s1")], levels=[0]))


def crabel_nr7(df, ctx):
    r = df.high - df.low
    nr7 = r < r.shift(1).rolling(6).min()
    hi = df.high.where(nr7).ffill()
    lo = df.low.where(nr7).ffill()
    # the latest NR7 day before today sets the levels a close must break
    hi1, lo1 = hi.shift(1), lo.shift(1)
    st = latch(df.close > hi1, df.close < lo1, ok(hi1, lo1))
    return res(st, [("NR7 day high", hi, "s1"), ("NR7 day low", lo, "s2")])


def bb_squeeze(df, ctx):
    c = df.close
    mid, sd = _mean_sd(c, 20)
    up, lo = mid + 2 * sd, mid - 2 * sd
    bw = (up - lo) / mid
    low6 = bw.rolling(125).min()
    sq = (bw <= low6).where(low6.notna())
    recent = sq.rolling(5).max() == 1
    st = latch((c > up) & recent, c < mid, ok(low6))
    return res(st, [("Upper band", up, "s1"), ("20-day SMA", mid, "s2")],
               panel=panel("BandWidth (20, 2)", [("BandWidth", bw, "s1"), ("125-day low", low6, "s2")], fmt="pct"))
