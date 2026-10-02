"""Rule code for every play.

Each function takes finished bars (DataFrame: open, high, low, close, volume,
hc = highest close inside the bar) and a context dict, and returns:

    {"state": Series of 1 (in) / 0 (out) / NaN (not enough history),
     "lines": [(label, Series, role)]   overlays on the price chart,
     "panel": {...} or None              an indicator drawn under the price,
     "extra": {...}}                     play-specific facts (zone, checks)

States are decided on a bar's close; the engine acts on the next session.
Context: crypto, bench (S&P 500 ETF closes on these bars, None for SPY itself),
irx (T-bill yield, annual decimal, on these bars), future (projected sessions).
"""
import numpy as np
import pandas as pd

from . import ind
from .cal import month_positions


# ---------------------------------------------------------------- helpers
def _b(x):
    if isinstance(x, pd.Series):
        return x.to_numpy(dtype=bool) if x.dtype == bool else x.fillna(False).to_numpy(dtype=bool)
    return np.asarray(x, dtype=bool)


def latch(enter, exit_, valid, start_out=True):
    """1 on enter bars, 0 on exit bars (exit wins a tie), held in between.
    start_out: the first valid bar without a signal starts in cash."""
    v = _b(valid)
    en, ex = _b(enter) & v, _b(exit_) & v
    setv = np.full(len(v), np.nan)
    setv[en] = 1.0
    setv[ex] = 0.0
    if start_out and v.any():
        first = int(v.argmax())
        if np.isnan(setv[first]):
            setv[first] = 0.0
    setv[~v] = np.nan
    have = ~np.isnan(setv)
    pos = np.where(have, np.arange(len(setv)), -1)
    np.maximum.accumulate(pos, out=pos)
    out = np.where(pos >= 0, setv[np.maximum(pos, 0)], np.nan)
    out[~v] = np.nan
    return pd.Series(out, index=valid.index)


def level(cond_in, cond_out, valid, start_out=False):
    return latch(cond_in, cond_out, valid, start_out=start_out)


def ok(*series):
    m = None
    for s in series:
        v = s.notna()
        m = v if m is None else (m & v)
    return m


def res(state, lines=(), panel=None, **extra):
    return {"state": state, "lines": list(lines), "panel": panel, "extra": extra}


def panel(label, series, levels=(), fmt="num", lo=None, hi=None):
    return {"label": label, "series": series, "levels": list(levels), "fmt": fmt, "min": lo, "max": hi}


def _arr(s):
    return s.to_numpy(dtype=float)


# ================================================================= trend: averages
def pb_ema(df, ctx):
    return _band(df, ind.ema(df.close, 12), ind.ema(df.close, 21), 42, ("EMA 12", "EMA 21"))


def bmsb(df, ctx):
    return _band(df, ind.sma(df.close, 20), ind.ema(df.close, 21), 42, ("20-week SMA", "21-week EMA"))


def ripster(df, ctx):
    return _band(df, ind.ema(df.close, 34), ind.ema(df.close, 50), 100, ("EMA 34", "EMA 50"))


def _band(df, a, b, warm, labels):
    px = df.close
    hi, lo = np.maximum(a, b), np.minimum(a, b)
    valid = ok(a, b) & (pd.Series(np.arange(len(px)), index=px.index) >= warm)
    st = latch(px > hi, px < lo, valid, start_out=False)
    zone = None
    if len(px):
        p = px.iloc[-1]
        zone = "above" if p > hi.iloc[-1] else ("below" if p < lo.iloc[-1] else "between")
    return res(st, [(labels[0], a, "s1"), (labels[1], b, "s2")], zone=zone)


TEMPLATE_LABELS = [
    "Price above the 150 and 200-day averages",
    "150-day above the 200-day",
    "200-day higher than a month ago",
    "50-day above the 150 and 200-day",
    "Price above the 50-day",
    "At least 30% above the 52-week low",
    "Within 25% of the 52-week high",
]


def trend_template(df, ctx):
    px = df.close
    s50, s150, s200 = ind.sma(px, 50), ind.sma(px, 150), ind.sma(px, 200)
    s200p = s200.shift(21)
    low52, high52 = ind.ll(px, 252), ind.hh(px, 252)
    conds = [(px > s150) & (px > s200), s150 > s200, s200 > s200p, (s50 > s150) & (s50 > s200),
             px > s50, px >= 1.3 * low52, px >= 0.75 * high52]
    allok = conds[0]
    for c in conds[1:]:
        allok = allok & c
    valid = ok(s200p, low52)
    st = latch(allok, px < s50, valid, start_out=False)
    checks = [(lab, bool(c.iloc[-1])) for lab, c in zip(TEMPLATE_LABELS, conds)] if len(px) else []
    return res(st, [("50-day SMA", s50, "s1"), ("200-day SMA", s200, "s2")], checks=checks)


def stage(df, ctx):
    px = df.close
    s30 = ind.sma(px, 30)
    rising = s30 > s30.shift(4)
    valid = ok(s30.shift(4)) & (pd.Series(np.arange(len(px)), index=px.index) >= 34)
    st = latch((px > s30) & rising, px < s30, valid, start_out=False)
    return res(st, [("30-week SMA", s30, "s1")])


def faber(df, ctx):
    px = df.close
    s10 = ind.sma(px, 10)
    st = level(px > s10, px <= s10, ok(s10))
    return res(st, [("10-month SMA", s10, "s1")])


def tsmom(df, ctx):
    px = df.close
    irx = ctx["irx_daily"]
    rf_m = irx.groupby(irx.index.to_period("M")).mean()
    rf12 = rf_m.rolling(12).mean()
    rf12 = pd.Series(rf12.reindex(px.index.to_period("M")).values, index=px.index).ffill()
    base = px.shift(12) * (1 + rf12)
    st = level(px > base, px <= base, ok(base))
    return res(st, [("12 months ago + T-bills", base, "s1")])


def hold(df, ctx):
    return res(pd.Series(1.0, index=df.index))


def ptj_200(df, ctx):
    px = df.close
    s = ind.sma(px, 200)
    return res(level(px > s, px < s, ok(s)), [("200-day SMA", s, "s1")])


def golden_cross(df, ctx):
    a, b = ind.sma(df.close, 50), ind.sma(df.close, 200)
    return res(level(a > b, a < b, ok(a, b)), [("50-day SMA", a, "s1"), ("200-day SMA", b, "s2")])


def granville_200(df, ctx):
    px = df.close
    s = ind.sma(px, 200)
    flat_up = s >= s.shift(20)
    st = latch((px > s) & flat_up, px < s, ok(s.shift(20)), start_out=True)
    return res(st, [("200-day SMA", s, "s1")])


def hull_turn(df, ctx):
    h = ind.hma(df.close, 16)
    st = level(h > h.shift(1), h < h.shift(1), ok(h.shift(1)))
    return res(st, [("Hull MA (16 weeks)", h, "s1")])


def kama_dir(df, ctx):
    k = ind.kama(df.close, 10, 2, 30)
    st = level(k > k.shift(1), k < k.shift(1), ok(k.shift(1)) & (pd.Series(np.arange(len(k)), index=k.index) >= 40))
    return res(st, [("KAMA (10, 2, 30)", k, "s1")])


def tema_cross(df, ctx):
    a, b = ind.tema(df.close, 20), ind.tema(df.close, 50)
    valid = pd.Series(np.arange(len(a)), index=a.index) >= 150
    return res(level(a > b, a < b, valid), [("TEMA 20", a, "s1"), ("TEMA 50", b, "s2")])


def seykota(df, ctx):
    a, b = ind.ema_a(df.close, 1 / 15), ind.ema_a(df.close, 1 / 150)
    valid = pd.Series(np.arange(len(a)), index=a.index) >= 300
    return res(level(a > b, a < b, valid), [("Fast average (15)", a, "s1"), ("Slow average (150)", b, "s2")])


def gmma(df, ctx):
    px = df.close
    short = [ind.ema(px, n) for n in (3, 5, 8, 10, 12, 15)]
    long_ = [ind.ema(px, n) for n in (30, 35, 40, 45, 50, 60)]
    smin = pd.concat(short, axis=1).min(axis=1)
    lmax = pd.concat(long_, axis=1).max(axis=1)
    smean = pd.concat(short, axis=1).mean(axis=1)
    lmean = pd.concat(long_, axis=1).mean(axis=1)
    valid = pd.Series(np.arange(len(px)), index=px.index) >= 120
    st = latch(smin > lmax, smean < lmean, valid)
    return res(st, [("Trader group (average)", smean, "s1"), ("Investor group (average)", lmean, "s2")])


def ichimoku(df, ctx):
    tenkan, kijun, sa, sb = ind.ichimoku(df)
    top, bot = np.maximum(sa, sb), np.minimum(sa, sb)
    px = df.close
    st = latch((px > top) & (tenkan > kijun), px < bot, ok(sa, sb))
    return res(st, [("Cloud top", top, "s1"), ("Cloud bottom", bot, "s2")])


def supertrend(df, ctx):
    line, d = ind.supertrend(df, 10, 3.0)
    st = level(d == 1, d == -1, ok(d) & (pd.Series(np.arange(len(d)), index=d.index) >= 20))
    return res(st, [("Supertrend (10, 3)", line, "s1")])


def alligator(df, ctx):
    jaw, teeth, lips = ind.alligator(df)
    up = (lips > teeth) & (teeth > jaw)
    st = level(up, ~up, ok(jaw, teeth, lips))
    return res(st, [("Lips (5)", lips, "s1"), ("Teeth (8)", teeth, "s2"), ("Jaw (13)", jaw, "s3")])


def vortex(df, ctx):
    vp, vm = ind.vortex(df, 14)
    st = level(vp > vm, vm > vp, ok(vp, vm))
    return res(st, panel=panel("Vortex (14)", [("VI+", vp, "s1"), ("VI−", vm, "s2")]))


def aroon(df, ctx):
    up, dn = ind.aroon(df, 25)
    st = level(up > dn, dn > up, ok(up, dn))
    return res(st, panel=panel("Aroon (25)", [("Aroon up", up, "s1"), ("Aroon down", dn, "s2")], levels=[50], lo=0, hi=100))


def psar(df, ctx):
    sar, tr = ind.psar(df, 0.02, 0.2)
    st = level(tr == 1, tr == -1, ok(tr) & (pd.Series(np.arange(len(tr)), index=tr.index) >= 10))
    return res(st, [("Parabolic SAR", sar, "s1")])


def dmi_adx(df, ctx):
    pdi, mdi, adx = ind.dmi(df, 14)
    st = latch((pdi > mdi) & (adx > 25), pdi < mdi, ok(pdi, mdi, adx))
    return res(st, panel=panel("Directional movement (14)", [("+DI", pdi, "s1"), ("−DI", mdi, "s2"), ("ADX", adx, "s3")], levels=[25], lo=0))


def macd_signal(df, ctx):
    line, sig, _ = ind.macd(df.close, 12, 26, 9)
    valid = pd.Series(np.arange(len(line)), index=line.index) >= 60
    st = level(line > sig, line < sig, valid)
    return res(st, panel=panel("MACD (12, 26, 9)", [("MACD", line, "s1"), ("Signal", sig, "s2")], levels=[0]))


def macd_zero(df, ctx):
    a, b = ind.ema(df.close, 12), ind.ema(df.close, 26)
    valid = pd.Series(np.arange(len(a)), index=a.index) >= 60
    return res(level(a > b, a < b, valid), [("EMA 12", a, "s1"), ("EMA 26", b, "s2")])


def elder_impulse(df, ctx):
    e13 = ind.ema(df.close, 13)
    _, _, hist = ind.macd(df.close, 12, 26, 9)
    green = (e13 > e13.shift(1)) & (hist > hist.shift(1))
    red = (e13 < e13.shift(1)) & (hist < hist.shift(1))
    valid = pd.Series(np.arange(len(e13)), index=e13.index) >= 60
    st = latch(green, red, valid)
    return res(st, [("EMA 13", e13, "s1")], panel=panel("MACD histogram (12, 26, 9)", [("Histogram", hist, "s1")], levels=[0]))


def kst(df, ctx):
    k, s = ind.kst(df.close)
    st = level(k > s, k < s, ok(k, s))
    return res(st, panel=panel("Know Sure Thing", [("KST", k, "s1"), ("Signal", s, "s2")], levels=[0]))


def coppock(df, ctx):
    c = ind.coppock(df.close)
    cp = c.shift(1)
    st = latch((cp < 0) & (c > cp), (c < 0) & (c < cp), ok(cp))
    return res(st, panel=panel("Coppock curve (monthly)", [("Coppock", c, "s1")], levels=[0]))


def clenow_trend(df, ctx):
    c = _arr(df.close)
    e50, e100 = ind.ema(df.close, 50), ind.ema(df.close, 100)
    hi50 = _arr(ind.hh(df.close, 50))
    a20 = _arr(ind.atr(df, 20))
    f, s = _arr(e50), _arr(e100)
    n = len(c)
    st = np.full(n, np.nan)
    stop = np.full(n, np.nan)
    state, top = 0, None
    for i in range(n):
        if i < 100 or np.isnan(hi50[i]) or np.isnan(a20[i]):
            continue
        if state == 0:
            if f[i] > s[i] and c[i] >= hi50[i]:
                state, top = 1, c[i]
        else:
            top = max(top, c[i])
            if c[i] < top - 3 * a20[i]:
                state = 0
        if state == 1:
            stop[i] = top - 3 * a20[i]
        st[i] = state
    idx = df.index
    return res(pd.Series(st, index=idx), [("EMA 50", e50, "s1"), ("EMA 100", e100, "s2"), ("3-ATR trailing stop", pd.Series(stop, index=idx), "s3")])


def stocks_on_move(df, ctx):
    px = df.close
    score = ind.logslope_r2(px, 90, 365 if ctx["crypto"] else 252)
    s100 = ind.sma(px, 100)
    gap = px.pct_change().abs().rolling(90).max()
    gap_ok = gap <= 0.15
    bench = ctx["bench"]
    if bench is None:
        idx_ok = px > ind.sma(px, 200)
    else:
        idx_ok = bench > ind.sma(ctx["bench_full"], 200).reindex(px.index, method="ffill")
    enter = idx_ok & (px > s100) & gap_ok & (score > 0)
    exit_ = (px < s100) | ~gap_ok | (score <= 0)
    st = latch(enter, exit_, ok(score, s100, gap))
    return res(st, [("100-day SMA", s100, "s1")],
               panel=panel("Momentum score (90-day trend × fit)", [("Score", score, "s1")], levels=[0], fmt="pct"))


# ================================================================= breakout
def donchian(df, ctx):
    hi = df.high.rolling(20).max().shift(1)
    lo = df.low.rolling(20).min().shift(1)
    st = latch(df.close > hi, df.close < lo, ok(hi, lo))
    return res(st, [("Prior 20-day high", hi, "s1"), ("Prior 20-day low", lo, "s2")])


def _turtle(df, entry_n, exit_n, skip, fail_n=55):
    c, h, l_ = _arr(df.close), _arr(df.high), _arr(df.low)
    N = _arr(ind.atr_ema(df, 20))
    hh_e = _arr(df.high.rolling(entry_n).max().shift(1))
    ll_e = _arr(df.low.rolling(entry_n).min().shift(1))
    ll_x = _arr(df.low.rolling(exit_n).min().shift(1))
    hh_x = _arr(df.high.rolling(exit_n).max().shift(1))
    hh_f = _arr(df.high.rolling(fail_n).max().shift(1))
    n = len(c)
    st = np.full(n, np.nan)
    v_pos, v_entry, v_n, last_win = 0, 0.0, 0.0, False
    state, entry, n_e = 0, 0.0, 0.0
    for i in range(n):
        if np.isnan(hh_e[i]) or np.isnan(ll_x[i]) or np.isnan(N[i]) or (skip and np.isnan(hh_f[i])):
            continue
        # the shadow trader takes every breakout, long or short, to grade the filter
        if v_pos == 1:
            if c[i] <= v_entry - 2 * v_n:
                v_pos, last_win = 0, False
            elif c[i] < ll_x[i]:
                v_pos, last_win = 0, True
        elif v_pos == -1:
            if c[i] >= v_entry + 2 * v_n:
                v_pos, last_win = 0, False
            elif c[i] > hh_x[i]:
                v_pos, last_win = 0, True
        prev_win = last_win
        long_bo, short_bo = c[i] > hh_e[i], c[i] < ll_e[i]
        if v_pos == 0 and (long_bo or short_bo):
            v_pos, v_entry, v_n = (1 if long_bo else -1), c[i], N[i]
        if state == 1:
            if c[i] < ll_x[i] or c[i] <= entry - 2 * n_e:
                state = 0
        else:
            if long_bo and (not skip or not prev_win):
                state, entry, n_e = 1, c[i], N[i]
            elif skip and prev_win and c[i] > hh_f[i]:
                state, entry, n_e = 1, c[i], N[i]
        st[i] = state
    return pd.Series(st, index=df.index), pd.Series(hh_e, index=df.index), pd.Series(ll_x, index=df.index)


def turtle1(df, ctx):
    st, hi, lo = _turtle(df, 20, 10, True)
    return res(st, [("Prior 20-day high", hi, "s1"), ("Prior 10-day low", lo, "s2")])


def turtle2(df, ctx):
    st, hi, lo = _turtle(df, 55, 20, False)
    return res(st, [("Prior 55-day high", hi, "s1"), ("Prior 20-day low", lo, "s2")])


def darvas(df, ctx):
    c, h, l_ = _arr(df.close), _arr(df.high), _arr(df.low)
    n = len(c)
    st = np.full(n, np.nan)
    tops, bots = np.full(n, np.nan), np.full(n, np.nan)
    state, stop = 0, None
    H, hcnt, top, L, lcnt, bot, lmin = None, 0, None, None, 0, None, None

    def reset(i):
        return h[i], 0, None, None, 0, None, l_[i]

    for i in range(n):
        if i < 20:
            H, hcnt, top, L, lcnt, bot, lmin = reset(i)
            continue
        if state == 1 and c[i] < stop:
            state, stop = 0, None
            H, hcnt, top, L, lcnt, bot, lmin = reset(i)
            st[i] = 0
            continue
        if state == 0 and top is not None and bot is not None:
            if c[i] > top:
                state, stop = 1, bot
                H, hcnt, top, L, lcnt, bot, lmin = reset(i)
                st[i] = 1
                continue
            if c[i] < bot:
                H, hcnt, top, L, lcnt, bot, lmin = reset(i)
                st[i] = 0
                continue
        # build the next box
        if top is None:
            if H is None or h[i] > H:
                H, hcnt, lmin = h[i], 0, l_[i]
            else:
                hcnt += 1
                lmin = min(lmin, l_[i])
                if hcnt >= 3:
                    top, L, lcnt = H, lmin, 0
        elif bot is None:
            if h[i] > top:
                H, hcnt, top, L, lcnt, bot, lmin = h[i], 0, None, None, 0, None, l_[i]
            elif l_[i] < L:
                L, lcnt = l_[i], 0
            else:
                lcnt += 1
                if lcnt >= 3:
                    bot = L
                    if state == 1 and bot > stop:
                        stop = bot
        elif state == 1 and h[i] > top:     # in a trade: a new high starts the next box
            H, hcnt, top, L, lcnt, bot, lmin = h[i], 0, None, None, 0, None, l_[i]
        st[i] = state
        if top is not None:
            tops[i] = top
        if state == 1:
            bots[i] = stop
        elif bot is not None:
            bots[i] = bot
    idx = df.index
    return res(pd.Series(st, index=idx), [("Box top", pd.Series(tops, index=idx), "s1"), ("Box bottom / stop", pd.Series(bots, index=idx), "s2")])


def high52(df, ctx):
    top = df.hc.rolling(12).max()
    r = df.close / top
    st = latch(r >= 0.95, r < 0.85, ok(top))
    return res(st, [("52-week closing high", top, "s1"), ("95% of the high", 0.95 * top, "s2")])


def keltner(df, ctx):
    mid = ind.ema(df.close, 20)
    up = mid + 2 * ind.atr(df, 10)
    valid = ok(up) & (pd.Series(np.arange(len(mid)), index=mid.index) >= 40)
    st = latch(df.close > up, df.close < mid, valid)
    return res(st, [("Upper channel", up, "s2"), ("20-day EMA", mid, "s1")])


def bb_break(df, ctx):
    mid = ind.sma(df.close, 20)
    sd = df.close.rolling(20).std(ddof=0)
    up = mid + 2 * sd
    st = latch(df.close > up, df.close < mid, ok(up))
    return res(st, [("Upper band", up, "s2"), ("20-day SMA", mid, "s1")])


def chandelier(df, ctx):
    ce = df.high.rolling(22).max() - 3 * ind.atr(df, 22)
    prev_hi = df.close.rolling(22).max().shift(1)
    st = latch(df.close > prev_hi, df.close < ce.shift(1), ok(ce.shift(1), prev_hi))
    return res(st, [("Chandelier stop", ce, "s1")])


def zweig(df, ctx):
    c = _arr(df.close)
    n = len(c)
    st = np.full(n, np.nan)
    trig = np.full(n, np.nan)
    if n:
        state, ref = 0, c[0]
        for i in range(n):
            if state == 0:
                ref = min(ref, c[i])
                if c[i] >= ref * 1.04:
                    state, ref = 1, c[i]
            else:
                ref = max(ref, c[i])
                if c[i] <= ref * 0.96:
                    state, ref = 0, c[i]
            st[i] = state
            trig[i] = ref * (0.96 if state == 1 else 1.04)
        st[:4] = np.nan
    idx = df.index
    return res(pd.Series(st, index=idx), [("4% trigger", pd.Series(trig, index=idx), "s1")])


# ================================================================= momentum
def mom_12_1(df, ctx):
    r = df.close.shift(1) / df.close.shift(12) - 1
    return res(level(r > 0, r <= 0, ok(r)), panel=panel("Return from 12 months to 1 month ago", [("12-1 return", r, "s1")], levels=[0], fmt="pct"))


def _tbill12(df, ctx):
    irx = ctx["irx_daily"]
    rf_m = irx.groupby(irx.index.to_period("M")).mean()
    g = (1 + rf_m / 12).rolling(12).apply(np.prod, raw=True) - 1
    return pd.Series(g.reindex(df.index.to_period("M")).values, index=df.index).ffill()


def dual_mom(df, ctx):
    r = df.close / df.close.shift(12) - 1
    tb = _tbill12(df, ctx)
    if ctx["bench"] is None:
        rb = r
        enter = r > tb
    else:
        rb = ctx["bench"] / ctx["bench"].shift(12) - 1
        enter = (r > tb) & (r > rb)
    st = level(enter, ~enter, ok(r, tb, rb))
    return res(st, panel=panel("12-month returns", [("This stock", r, "s1"), ("S&P 500 (SPY)", rb, "s2"), ("T-bills", tb, "s3")], levels=[0], fmt="pct"))


def mansfield(df, ctx):
    px = df.close
    s30 = ind.sma(px, 30)
    if ctx["bench"] is None:
        mrs = pd.Series(0.0, index=px.index).where(s30.notna())
        good = px > s30
    else:
        rs = px / ctx["bench"]
        mrs = rs / ind.sma(rs, 52) - 1
        good = (px > s30) & (mrs > 0)
    bad = (px < s30) | (mrs < 0)
    st = latch(good, bad, ok(s30, mrs))
    return res(st, [("30-week SMA", s30, "s1")],
               panel=panel("Mansfield relative strength vs SPY", [("Mansfield RS", mrs, "s1")], levels=[0], fmt="pct"))


def levy(df, ctx):
    px = df.close
    ratio = px / ind.sma(px, 27)
    if ctx["bench"] is None:
        br = ratio
        good = ratio > 1
    else:
        br = ctx["bench"] / ind.sma(ctx["bench"], 27)
        good = (ratio > 1) & (ratio > br)
    st = level(good, ~good, ok(ratio, br))
    return res(st, [("27-week average", ind.sma(px, 27), "s1")],
               panel=panel("Price ÷ its 27-week average", [("This stock", ratio, "s1"), ("SPY", br, "s2")], levels=[1]))


def cci100(df, ctx):
    c = ind.cci(df, 20)
    st = latch(ind.cross_up(c, 100), ind.cross_dn(c, 100), ok(c.shift(1)))
    return res(st, panel=panel("Commodity Channel Index (20)", [("CCI", c, "s1")], levels=[100, -100]))


# ================================================================= mean reversion
def rsi_30_70(df, ctx):
    r = ind.rsi(df.close, 14)
    st = latch(ind.cross_up(r, 30), ind.cross_dn(r, 70), ok(r.shift(1)))
    return res(st, panel=panel("RSI (14)", [("RSI", r, "s1")], levels=[30, 70], lo=0, hi=100))


def stochastic(df, ctx):
    k, d = ind.stoch(df, 14, 3, 3)
    st = latch(ind.cross_up(k, d) & (d < 20), ind.cross_dn(k, d) & (d > 80), ok(k.shift(1), d.shift(1)))
    return res(st, panel=panel("Stochastic (14, 3, 3)", [("%K", k, "s1"), ("%D", d, "s2")], levels=[20, 80], lo=0, hi=100))


def willr(df, ctx):
    w = ind.willr(df, 14)
    st = latch(ind.cross_up(w, -80), ind.cross_dn(w, -20), ok(w.shift(1)))
    return res(st, panel=panel("Williams %R (14)", [("%R", w, "s1")], levels=[-20, -80], lo=-100, hi=0))


def demark9(df, ctx):
    c = df.close
    below = (c < c.shift(4)).fillna(False)
    above = (c > c.shift(4)).fillna(False)
    bcount = below.groupby((~below).cumsum()).cumsum()
    scount = above.groupby((~above).cumsum()).cumsum()
    valid = ok(c.shift(5))
    st = latch(bcount == 9, scount == 9, valid)
    return res(st, panel=panel("Setup count", [("Buy setup", bcount.where(valid), "s1"), ("Sell setup", scount.where(valid), "s2")], levels=[9], lo=0))


def bb_revert(df, ctx):
    mid = ind.sma(df.close, 20)
    lo = mid - 2 * df.close.rolling(20).std(ddof=0)
    st = latch(df.close < lo, df.close > mid, ok(lo))
    return res(st, [("20-day SMA", mid, "s1"), ("Lower band", lo, "s2")])


def rsi2(df, ctx):
    px = df.close
    s200, s5 = ind.sma(px, 200), ind.sma(px, 5)
    r = ind.rsi(px, 2)
    st = latch((px > s200) & (r < 10), px > s5, ok(s200, r))
    return res(st, [("200-day SMA", s200, "s1"), ("5-day SMA", s5, "s2")],
               panel=panel("RSI (2)", [("RSI 2", r, "s1")], levels=[10], lo=0, hi=100))


def double7(df, ctx):
    px = df.close
    s200 = ind.sma(px, 200)
    lo7, hi7 = ind.ll(px, 7), ind.hh(px, 7)
    st = latch((px > s200) & (px <= lo7), px >= hi7, ok(s200, lo7))
    return res(st, [("200-day SMA", s200, "s1"), ("7-day closing high", hi7, "s2"), ("7-day closing low", lo7, "s3")])


def mayer(df, ctx):
    s = ind.sma(df.close, 200)
    m = df.close / s
    return res(level(m < 2.4, m >= 2.4, ok(s)), [("200-day SMA", s, "s1"), ("2.4 × the 200-day", 2.4 * s, "s2")])


# ================================================================= volume
def obv(df, ctx):
    o = ind.obv(df)
    sig = ind.sma(o, 20)
    st = level(o > sig, o < sig, ok(sig))
    return res(st, panel=panel("On-balance volume", [("OBV", o, "s1"), ("20-day average", sig, "s2")]))


def cmf(df, ctx):
    c = ind.cmf(df, 21)
    st = latch(c > 0.05, c < -0.05, ok(c))
    return res(st, panel=panel("Chaikin Money Flow (21)", [("CMF", c, "s1")], levels=[0.05, -0.05]))


def mfi(df, ctx):
    m = ind.mfi(df, 14)
    st = latch(ind.cross_up(m, 20), ind.cross_dn(m, 80), ok(m.shift(1)))
    return res(st, panel=panel("Money Flow Index (14)", [("MFI", m, "s1")], levels=[20, 80], lo=0, hi=100))


# ================================================================= calendar
def _ext(df, ctx):
    """Real sessions plus projected ones, so 'last day of the month' is known."""
    fut = ctx.get("future")
    idx = df.index if fut is None or not len(fut) else df.index.append(fut[fut > df.index[-1]])
    first, last = month_positions(idx)
    return idx, np.asarray(idx.month), first, last


def _cal_result(df, idx, setv, start=0.0):
    s = pd.Series(setv, index=idx)
    if np.isnan(s.iloc[0]):
        s.iloc[0] = start
    s = s.ffill()
    return res(s.iloc[:len(df)], calendar=s)


def halloween(df, ctx):
    idx, m, first, last = _ext(df, ctx)
    setv = np.full(len(idx), np.nan)
    setv[(m == 10) & (last == 1)] = 1.0
    setv[(m == 4) & (last == 1)] = 0.0
    start = 1.0 if idx[0].month in (11, 12, 1, 2, 3, 4) else 0.0
    return _cal_result(df, idx, setv, start)


def santa(df, ctx):
    idx, m, first, last = _ext(df, ctx)
    setv = np.full(len(idx), np.nan)
    setv[(m == 12) & (last == 6)] = 1.0
    setv[(m == 1) & (first == 2)] = 0.0
    return _cal_result(df, idx, setv)


def turn_of_month(df, ctx):
    idx, m, first, last = _ext(df, ctx)
    setv = np.full(len(idx), np.nan)
    setv[last == 2] = 1.0
    setv[first == 3] = 0.0
    return _cal_result(df, idx, setv)


def _macd_season(df, ctx, f, s, sig, in_window, out_window, use_cross):
    line, sg, _ = ind.macd(df.close, f, s, sig)
    up = ind.cross_up(line, sg) if use_cross else (line > sg)
    dn = ind.cross_dn(line, sg) if use_cross else (line < sg)
    idx = df.index
    md = np.asarray(idx.month) * 100 + np.asarray(idx.day)
    win_in = in_window(md)
    win_out = out_window(md)
    upv, dnv = up.to_numpy(), dn.to_numpy()
    st = np.full(len(idx), np.nan)
    state = 0
    for i in range(len(idx)):
        if i < 60:
            continue
        if state == 0 and win_in[i] and upv[i]:
            state = 1
        elif state == 1 and win_out[i] and dnv[i]:
            state = 0
        st[i] = state
    return pd.Series(st, index=idx), line, sg


def best_six_macd(df, ctx):
    st, line, sg = _macd_season(df, ctx, 8, 17, 9,
                                lambda md: (md >= 1001) | (md < 400), lambda md: (md >= 401) & (md < 1001), True)
    return res(st, panel=panel("MACD (8, 17, 9)", [("MACD", line, "s1"), ("Signal", sg, "s2")], levels=[0]))


def harding(df, ctx):
    st, line, sg = _macd_season(df, ctx, 12, 26, 9,
                                lambda md: (md >= 1016) | (md < 420), lambda md: (md >= 420) & (md < 1016), False)
    return res(st, panel=panel("MACD (12, 26, 9)", [("MACD", line, "s1"), ("Signal", sg, "s2")], levels=[0]))
