"""Trading-calendar helpers: projected future sessions and month/position flags.

History always uses the real sessions in the price file. Only dates after the
last close are projected, using the U.S. (NYSE) holiday calendar for stocks
and every calendar day for crypto.
"""
import datetime as dt

import numpy as np
import pandas as pd


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return dt.date(y, month, day)


def _nth_weekday(y, m, wd, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(wd - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(y, m, wd):
    d = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


def _observed(d):
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def nyse_holidays(y):
    hs = {
        _observed(dt.date(y, 1, 1)),
        _nth_weekday(y, 1, 0, 3),          # MLK
        _nth_weekday(y, 2, 0, 3),          # Presidents
        _easter(y) - dt.timedelta(days=2),  # Good Friday
        _last_weekday(y, 5, 0),            # Memorial
        _observed(dt.date(y, 7, 4)),
        _nth_weekday(y, 9, 0, 1),          # Labor
        _nth_weekday(y, 11, 3, 4),         # Thanksgiving
        _observed(dt.date(y, 12, 25)),
    }
    if y >= 2022:
        hs.add(_observed(dt.date(y, 6, 19)))
    # New Year's Day on a Saturday is not observed on the prior Friday
    if dt.date(y, 1, 1).weekday() == 5:
        hs.discard(dt.date(y - 1, 12, 31))
    nxt = dt.date(y + 1, 1, 1)
    if nxt.weekday() == 5:
        hs.discard(dt.date(y, 12, 31))
    return hs


def future_sessions(last, crypto, n=420):
    """The next n sessions after `last` (a Timestamp)."""
    out, d = [], pd.Timestamp(last).date()
    hol = {}
    while len(out) < n:
        d += dt.timedelta(days=1)
        if not crypto:
            if d.weekday() >= 5:
                continue
            if d.year not in hol:
                hol[d.year] = nyse_holidays(d.year)
            if d in hol[d.year]:
                continue
        out.append(pd.Timestamp(d))
    return pd.DatetimeIndex(out)


def month_positions(idx):
    """For each session: (k-th session of its month from the start, 1-based;
    k-th from the end, 1-based). idx must already include projected sessions
    so the current month's count from the end is right."""
    per = idx.to_period("M")
    s = pd.Series(1, index=idx)
    first = s.groupby(per).cumsum().to_numpy()
    last = s[::-1].groupby(per[::-1]).cumsum()[::-1].to_numpy()
    return first, last


def month_of(idx):
    return np.asarray(idx.month)
