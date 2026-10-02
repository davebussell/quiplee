"""Indicator library for the plays. Pure functions over pandas objects.

Inputs are a price Series (usually closes) or an OHLCV DataFrame with
lower-case columns open/high/low/close/volume. Outputs are aligned to the
input index; warm-up values are NaN.

Smoothing conventions (they matter for exact thresholds):
  ema(s, n)        alpha = 2/(n+1), seeded with the first value (pandas adjust=False)
  ema_a(s, a)      alpha given directly (Seykota uses 1/lag)
  rma(s, n)        Wilder smoothing, alpha = 1/n, seeded with the SMA of the first n values
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as _win


# ---------------------------------------------------------------- averages
def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def ema_a(s, a):
    return s.ewm(alpha=a, adjust=False).mean()


def rma(s, n):
    """Wilder's smoothing, seeded with a simple average of the first n valid values."""
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    ok_ = ~np.isnan(x)
    if ok_.sum() < n:
        return pd.Series(out, index=s.index)
    first = int(ok_.argmax())
    z = x[first + n - 1:].copy()
    z[0] = x[first:first + n].mean()
    out[first + n - 1:] = pd.Series(z).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()
    return pd.Series(out, index=s.index)


def wma(s, n):
    """Linearly weighted moving average (weights 1..n, newest heaviest)."""
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        w = np.arange(1, n + 1, dtype=float)
        out[n - 1:] = _win(x, n) @ w / w.sum()
    return pd.Series(out, index=s.index)


def hma(s, n):
    half, root = max(1, n // 2), max(1, int(np.floor(np.sqrt(n))))
    return wma(2 * wma(s, half) - wma(s, n), root)


def tema(s, n):
    e1 = ema(s, n)
    e2 = ema(e1, n)
    e3 = ema(e2, n)
    return 3 * e1 - 3 * e2 + e3


def kama(s, er_n=10, fast=2, slow=30):
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) <= er_n:
        return pd.Series(out, index=s.index)
    fsc, ssc = 2.0 / (fast + 1), 2.0 / (slow + 1)
    change = np.abs(x[er_n:] - x[:-er_n])
    vol = pd.Series(np.abs(np.diff(x, prepend=np.nan))).rolling(er_n).sum().to_numpy()[er_n:]
    er = np.divide(change, vol, out=np.zeros_like(change), where=vol > 0)
    sc = (er * (fsc - ssc) + ssc) ** 2
    k = x[:er_n].mean()
    out[er_n - 1] = k
    for i in range(er_n, len(x)):
        k = k + sc[i - er_n] * (x[i] - k)
        out[i] = k
    return pd.Series(out, index=s.index)


# ---------------------------------------------------------------- ranges
def hh(s, n):
    return s.rolling(n, min_periods=n).max()


def ll(s, n):
    return s.rolling(n, min_periods=n).min()


def true_range(df):
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df, n):
    tr = true_range(df)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return rma(tr, n)


def atr_ema(df, n):
    """Turtle 'N': exponential average of true range (alpha = 1/n)."""
    tr = true_range(df)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return rma(tr, n)


# ---------------------------------------------------------------- oscillators
def rsi(s, n):
    d = s.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    au, ad = rma(up.iloc[1:], n).reindex(s.index), rma(dn.iloc[1:], n).reindex(s.index)
    rs = au / ad
    out = 100 - 100 / (1 + rs)
    out[(ad == 0) & au.notna()] = 100.0
    out[(ad == 0) & (au == 0)] = 50.0
    return out


def macd(s, f=12, sl=26, sig=9):
    line = ema(s, f) - ema(s, sl)
    signal = ema(line, sig)
    return line, signal, line - signal


def stoch(df, k=14, slow=3, d=3):
    lo, hi = ll(df["low"], k), hh(df["high"], k)
    rng = (hi - lo).replace(0, np.nan)
    fast = 100 * (df["close"] - lo) / rng
    ks = sma(fast, slow)
    return ks, sma(ks, d)


def willr(df, n=14):
    lo, hi = ll(df["low"], n), hh(df["high"], n)
    return -100 * (hi - df["close"]) / (hi - lo).replace(0, np.nan)


def cci(df, n=20, c=0.015):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    x = tp.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        w = _win(x, n)
        m = w.mean(axis=1)
        md = np.abs(w - m[:, None]).mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n - 1:] = (x[n - 1:] - m) / (c * md)
    return pd.Series(out, index=df.index)


def mfi(df, n=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw = tp * df["volume"]
    d = tp.diff()
    pos = raw.where(d > 0, 0.0).rolling(n).sum()
    neg = raw.where(d < 0, 0.0).rolling(n).sum()
    out = 100 - 100 / (1 + pos / neg)
    out[(neg == 0) & pos.notna()] = 100.0
    out.iloc[:n] = np.nan
    return out


def cmf(df, n=21):
    rng = (df["high"] - df["low"])
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng.replace(0, np.nan)
    mfm = mfm.fillna(0.0)
    vol = df["volume"]
    den = vol.rolling(n).sum()
    return (mfm * vol).rolling(n).sum() / den.replace(0, np.nan)


def obv(df):
    d = np.sign(df["close"].diff().fillna(0))
    return (d * df["volume"]).cumsum()


def roc(s, n):
    return 100 * (s / s.shift(n) - 1)


def kst(s):
    r = (sma(roc(s, 10), 10) * 1 + sma(roc(s, 15), 10) * 2 + sma(roc(s, 20), 10) * 3 + sma(roc(s, 30), 15) * 4)
    return r, sma(r, 9)


def coppock(s, l1=14, l2=11, w=10):
    return wma(roc(s, l1) + roc(s, l2), w)


# ---------------------------------------------------------------- trend systems
def dmi(df, n=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = up.where((up > dn) & (up > 0), 0.0)
    minus = dn.where((dn > up) & (dn > 0), 0.0)
    tr = true_range(df)
    a = rma(tr.iloc[1:], n).reindex(df.index)
    pdi = 100 * rma(plus.iloc[1:], n).reindex(df.index) / a
    mdi = 100 * rma(minus.iloc[1:], n).reindex(df.index) / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pdi, mdi, rma(dx, n)


def aroon(df, n=25):
    hi, lo = df["high"].to_numpy(dtype=float), df["low"].to_numpy(dtype=float)
    up = np.full(len(hi), np.nan)
    dn = np.full(len(hi), np.nan)
    if len(hi) > n:
        wh, wl = _win(hi, n + 1), _win(lo, n + 1)
        # most recent extreme on ties: search the reversed window
        since_h = np.argmax(wh[:, ::-1], axis=1)
        since_l = np.argmin(wl[:, ::-1], axis=1)
        up[n:] = 100.0 * (n - since_h) / n
        dn[n:] = 100.0 * (n - since_l) / n
    return pd.Series(up, index=df.index), pd.Series(dn, index=df.index)


def vortex(df, n=14):
    vp = (df["high"] - df["low"].shift(1)).abs()
    vm = (df["low"] - df["high"].shift(1)).abs()
    tr = true_range(df)
    s = tr.rolling(n).sum()
    return vp.rolling(n).sum() / s, vm.rolling(n).sum() / s


def ichimoku(df, t=9, k=26, b=52, disp=26):
    tenkan = (hh(df["high"], t) + ll(df["low"], t)) / 2
    kijun = (hh(df["high"], k) + ll(df["low"], k)) / 2
    span_a = ((tenkan + kijun) / 2).shift(disp)
    span_b = ((hh(df["high"], b) + ll(df["low"], b)) / 2).shift(disp)
    return tenkan, kijun, span_a, span_b


def alligator(df):
    med = (df["high"] + df["low"]) / 2
    return rma(med, 13).shift(8), rma(med, 8).shift(5), rma(med, 5).shift(3)


def psar(df, step=0.02, mx=0.2):
    """Wilder's Parabolic SAR. Returns (sar, trend) with trend +1 long / -1 short."""
    hi, lo = df["high"].to_numpy(dtype=float), df["low"].to_numpy(dtype=float)
    n = len(hi)
    sar = np.full(n, np.nan)
    trend = np.full(n, np.nan)
    if n < 3:
        return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)
    up = hi[1] >= hi[0]
    ep = hi[1] if up else lo[1]
    s = lo[0] if up else hi[0]
    af = step
    sar[1], trend[1] = s, 1 if up else -1
    for i in range(2, n):
        s = s + af * (ep - s)
        if up:
            s = min(s, lo[i - 1], lo[i - 2])
            if lo[i] <= s:                 # flip to short
                up, s, ep, af = False, ep, lo[i], step
            elif hi[i] > ep:
                ep, af = hi[i], min(af + step, mx)
        else:
            s = max(s, hi[i - 1], hi[i - 2])
            if hi[i] >= s:                 # flip to long
                up, s, ep, af = True, ep, hi[i], step
            elif lo[i] < ep:
                ep, af = lo[i], min(af + step, mx)
        sar[i], trend[i] = s, 1 if up else -1
    return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)


def supertrend(df, n=10, mult=3.0):
    a = atr(df, n).to_numpy()
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    bu, bl = hl2 + mult * a, hl2 - mult * a
    m = len(c)
    fu, fl = np.full(m, np.nan), np.full(m, np.nan)
    dirn = np.full(m, np.nan)
    line = np.full(m, np.nan)
    start = int(np.argmax(~np.isnan(a))) if np.any(~np.isnan(a)) else m
    for i in range(start, m):
        if i == start:
            fu[i], fl[i], d = bu[i], bl[i], 1
        else:
            fu[i] = bu[i] if (bu[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
            fl[i] = bl[i] if (bl[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
            d = dirn[i - 1]
            if d == -1 and c[i] > fu[i]:
                d = 1
            elif d == 1 and c[i] < fl[i]:
                d = -1
        dirn[i] = d
        line[i] = fl[i] if d == 1 else fu[i]
    return pd.Series(line, index=df.index), pd.Series(dirn, index=df.index)


def logslope_r2(s, n=90, ann=252):
    """Annualised exponential regression slope times R^2 (Clenow)."""
    y = np.log(s.to_numpy(dtype=float))
    out = np.full(len(y), np.nan)
    if len(y) >= n:
        w = _win(y, n)
        x = np.arange(n, dtype=float)
        xm = x - x.mean()
        ym = w - w.mean(axis=1, keepdims=True)
        sxx = (xm ** 2).sum()
        b = (ym @ xm) / sxx
        ss_tot = (ym ** 2).sum(axis=1)
        r2 = np.divide((b ** 2) * sxx, ss_tot, out=np.zeros_like(b), where=ss_tot > 0)
        out[n - 1:] = (np.exp(b) ** ann - 1) * r2
    return pd.Series(out, index=s.index)


# ---------------------------------------------------------------- helpers
def cross_up(a, b):
    """a crosses above b on this bar (b may be a scalar)."""
    bp = b.shift(1) if isinstance(b, pd.Series) else b
    return (a > b) & (a.shift(1) <= bp)


def cross_dn(a, b):
    bp = b.shift(1) if isinstance(b, pd.Series) else b
    return (a < b) & (a.shift(1) >= bp)
