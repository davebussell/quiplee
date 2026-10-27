"""Rule code for the trial plays from the Classics (Oct 27, 2026, AUD-49 step 3): forgotten rules
coded from classics.json's research, run on every stock and graded like any other play, but kept
out of Your signal and the play counts until their records are in (plays.TRIAL).

Same contract as plays_fn: each function takes finished bars (open, high, low, close, volume, hc)
and a context dict and returns res(state, lines, panel, **extra). States are decided on a bar's
close and acted on at the next session.
"""
import numpy as np
import pandas as pd

from . import ind
from .plays_fn import level, ok, res, panel


def _arr(s):
    return s.to_numpy(dtype=float)


def _bars(df):
    return pd.Series(np.arange(len(df)), index=df.index)


# ================================================================= Livermore's Market Key
UT, NRA, SRA, SRE, NRE, DT = "UT", "NRA", "SRA", "SRE", "NRE", "DT"
LIV_R, LIV_C = 0.06, 0.03          # stand-ins for Livermore's six and three points
LIV_WARM = 50


def livermore(df, ctx):
    """Livermore's Market Key (How to Trade in Stocks, 1940, as summarised secondhand): six columns
    of closes, pivots where recording switches column, In on entering Upward Trend, Out on entering
    Downward Trend."""
    c = _arr(df.close)
    n = len(c)
    st = np.full(n, np.nan)
    piv_up, piv_dn = np.full(n, np.nan), np.full(n, np.nan)
    if n <= LIV_WARM:
        return res(pd.Series(st, index=df.index))
    ma = _arr(ind.sma(df.close, LIV_WARM))
    R, C = LIV_R, LIV_C
    i0 = LIV_WARM - 1
    col = UT if c[i0] > ma[i0] else DT
    call = 1 if col == UT else 0
    ext = c[i0]
    p_ut = p_dt = p_nra = p_nre = None     # the last marked pivots of each kind

    def rally_col(x):
        """A rebound goes in Natural Rally unless it stays below the last Natural Rally pivot."""
        return SRA if (p_nra is not None and x < p_nra) else NRA

    def reaction_col(x):
        """A decline goes in Natural Reaction unless it holds above the last Natural Reaction pivot."""
        return SRE if (p_nre is not None and x > p_nre) else NRE

    def to_ut(x):
        return (p_ut is not None and x > p_ut) or (p_nra is not None and x >= p_nra * (1 + C))

    def to_dt(x):
        return (p_dt is not None and x < p_dt) or (p_nre is not None and x <= p_nre * (1 - C))

    st[i0] = call
    for i in range(i0 + 1, n):
        x = c[i]
        if col == UT:
            if x > ext:
                ext = x
            elif x <= ext * (1 - R):
                p_ut = ext                        # a reaction from the trend column always starts a Natural Reaction
                col, ext = NRE, x
                if to_dt(x):
                    col = DT
        elif col == DT:
            if x < ext:
                ext = x
            elif x >= ext * (1 + R):
                p_dt = ext                        # and a rally from it a Natural Rally
                col, ext = NRA, x
                if to_ut(x):
                    col = UT
        elif col in (NRA, SRA):
            if col == SRA and p_nra is not None and x > p_nra:
                col = NRA                     # a secondary rally that passes the last natural rally top becomes one
            if x > ext:
                ext = x
            if to_ut(x):
                col, ext = UT, max(ext, x)
            elif x <= ext * (1 - R):
                if col == NRA:
                    p_nra = ext
                col, ext = reaction_col(x), x
                if to_dt(x):
                    col = DT
        else:                                  # NRE, SRE
            if col == SRE and p_nre is not None and x < p_nre:
                col = NRE
            if x < ext:
                ext = x
            if to_dt(x):
                col, ext = DT, min(ext, x)
            elif x >= ext * (1 + R):
                if col == NRE:
                    p_nre = ext
                col, ext = rally_col(x), x
                if to_ut(x):
                    col = UT
        if col == UT:
            if call == 0:
                p_nre = None      # reaction lows from before the new up trend no longer count (Be The Puck's reading)
            call = 1
        elif col == DT:
            if call == 1:
                p_nra = None      # nor rally tops from before the new down trend
            call = 0
        st[i] = call
        # the levels that would change the call next
        up = [v for v in ((p_ut,) + ((p_nra * (1 + C),) if p_nra is not None else ())) if v is not None]
        dn = [v for v in ((p_dt,) + ((p_nre * (1 - C),) if p_nre is not None else ())) if v is not None]
        if call == 0 and up:
            piv_up[i] = min(up)
        if call == 1 and dn:
            piv_dn[i] = max(dn)
    idx = df.index
    return res(pd.Series(st, index=idx), [("Close that turns it to Upward Trend", pd.Series(piv_up, index=idx), "s1"),
                                          ("Close that turns it to Downward Trend", pd.Series(piv_dn, index=idx), "s2")])


# ================================================================= Gann's two-bar swing trend
def gann_swing(df, ctx):
    """Gann's swing chart trend indicator (1933 course, as read by later interpreters): the swing turns
    after two straight up bars or two straight down bars; In on a close above the last swing top,
    Out on a close below the last swing bottom."""
    h, l_, c = _arr(df.high), _arr(df.low), _arr(df.close)
    n = len(c)
    st = np.full(n, np.nan)
    tops, bots = np.full(n, np.nan), np.full(n, np.nan)
    if n < 3:
        return res(pd.Series(st, index=df.index))
    swing = 1 if c[1] >= c[0] else -1        # the first swing's direction (Be The Puck's choice)
    run = 0                                   # consecutive bars against the swing
    hi_sw, lo_sw = max(h[0], h[1]), min(l_[0], l_[1])
    top = bot = None
    call = None
    for i in range(1, n):
        up = h[i] > h[i - 1] and l_[i] >= l_[i - 1]
        dn = l_[i] < l_[i - 1] and h[i] <= h[i - 1]
        # inside and outside bars neither count nor reset the run
        if swing == 1:
            hi_sw = max(hi_sw, h[i])
            if dn:
                run += 1
                if run >= 2:
                    top, swing, run, lo_sw = hi_sw, -1, 0, min(l_[i], l_[i - 1])
            elif up:
                run = 0
        else:
            lo_sw = min(lo_sw, l_[i])
            if up:
                run += 1
                if run >= 2:
                    bot, swing, run, hi_sw = lo_sw, 1, 0, max(h[i], h[i - 1])
            elif dn:
                run = 0
        if top is not None and c[i] > top:
            call = 1
        elif bot is not None and c[i] < bot:
            call = 0
        elif call is None and top is not None and bot is not None:
            call = 0
        if call is not None:
            st[i] = call
        if top is not None:
            tops[i] = top
        if bot is not None:
            bots[i] = bot
    idx = df.index
    return res(pd.Series(st, index=idx), [("Last swing top", pd.Series(tops, index=idx), "s1"),
                                          ("Last swing bottom", pd.Series(bots, index=idx), "s2")])


# ================================================================= volume
def pvi(df, ctx):
    """Positive Volume Index (Dysart, Fosback) against its 255-day EMA: the mirror of the NVI play."""
    c, v = _arr(df.close), _arr(df.volume)
    ratio = np.ones(len(c))
    if len(c) > 1:
        ratio[1:] = np.where(v[1:] > v[:-1], c[1:] / c[:-1], 1.0)
    pv = pd.Series(1000.0 * np.cumprod(ratio), index=df.index)
    sig = ind.ema(pv, 255)
    st = level(pv > sig, pv < sig, _bars(df) >= 255)
    return res(st, panel=panel("Positive Volume Index", [("PVI", pv, "s1"), ("255-day EMA", sig, "s2")]))


def emv(df, ctx):
    """Arms' Ease of Movement, 14-day simple average, above or below zero."""
    h, l_, v = df.high, df.low, df.volume
    mid = (h + l_) / 2
    dist = mid - mid.shift(1)
    rng = (h - l_)
    box = (v / 1e8) / rng.replace(0, np.nan)
    one = (dist / box.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    one[(rng == 0) | (v == 0)] = 0.0
    e14 = one.rolling(14).mean()
    st = level(e14 > 0, e14 < 0, ok(e14) & (_bars(df) >= 15))
    return res(st, panel=panel("Ease of Movement (14-day average)", [("EMV", e14, "s1")], levels=[0]))
