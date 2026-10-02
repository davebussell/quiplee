"""Strategy engine: prices, rules, backtests, call history and next-move triggers.

Every rule is evaluated on completed bars only (daily, weekly or month-end),
acted on at the next session, charged a trading cost, and credited the T-bill
yield while out of the market. The "next move" is the exact close that would
flip the rule on its next bar, solved from the moving-average formulas.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from .content import TICKERS, STRATEGIES

ET = ZoneInfo("America/New_York")
LOAD_START = "2004-01-01"      # warm-up history
GRADE_START = pd.Timestamp("2005-01-01")
COST_BPS = {"crypto": 10, "default": 5}   # per position change


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def _close(sym):
    d = yf.download(sym, start=LOAD_START, progress=False, auto_adjust=True)
    if d is None or d.empty:
        raise RuntimeError(f"no data for {sym}")
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    c = d["Close"].dropna().astype(float)
    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
    return c[~c.index.duplicated(keep="last")]


def _drop_partial(c, crypto, now):
    """Drop today's still-forming bar so every signal uses a finished close."""
    last = c.index[-1].date()
    if crypto:
        if last >= dt.datetime.now(dt.timezone.utc).date():
            return c.iloc[:-1]
    elif last >= now.date() and (now.hour, now.minute) < (16, 30):
        return c.iloc[:-1]
    return c


def load_all(now=None):
    now = now or dt.datetime.now(ET)
    irx = _close("^IRX") / 100.0          # 13-week T-bill, annualised decimal
    prices = {}
    for t in TICKERS:
        prices[t["sym"]] = _drop_partial(_close(t["sym"]), t["crypto"], now)
    return prices, irx, now


# --------------------------------------------------------------------------
# Bars and averages
# --------------------------------------------------------------------------
def to_bars(c, bar, crypto, now):
    """Resample daily closes to the rule's bar. Each bar is stamped with the
    date of its last actual session. Returns (bars, last_bar_complete, bar_end)."""
    if bar == "D":
        return c.copy(), True, c.index[-1]
    freq = ("W-SUN" if crypto else "W-FRI") if bar == "W" else "M"
    key = c.index.to_period(freq)
    g = c.groupby(key)
    last_dates = g.apply(lambda s: s.index[-1])
    px = pd.Series(g.last().values, index=pd.DatetimeIndex(last_dates.values))
    per = key[-1]
    end = per.end_time.normalize()
    asof = c.index[-1]
    if bar == "W":
        complete = asof >= end or (not crypto and asof.weekday() == 4) or now.date() > end.date()
    else:
        if crypto:
            complete = asof >= end
        else:
            complete = (asof + pd.offsets.BDay(1)).month != asof.month or now.date() > end.date()
        if not crypto:
            end = (end - pd.offsets.BDay(0)) if end.weekday() < 5 else end - pd.offsets.BDay(1)
    return px, bool(complete), end


def ma(s, n, kind):
    return s.ewm(span=n, adjust=False).mean() if kind == "ema" else s.rolling(n).mean()


def next_thresh(s, n, kind):
    """The close on the next bar at which price exactly equals the average
    computed with that close included."""
    if kind == "ema":   # P > EMA_next  <=>  P > EMA_now
        return float(s.ewm(span=n, adjust=False).mean().iloc[-1])
    return float(s.iloc[-(n - 1):].mean())      # P > SMA_next  <=>  P > mean(last n-1)


def _warm(n, kind):
    return n if kind == "sma" else 2 * n


def _hold(set_series):
    """Turn a 1/0/NaN 'set' series into a held state (NaN until first set)."""
    return set_series.ffill()


# --------------------------------------------------------------------------
# Rules — each returns state (at completed bars), chart lines and a trigger
# --------------------------------------------------------------------------
def rule_band(px, s):
    (nf, kf), (ns, ks) = s["fast"], s["slow"]
    a, b = ma(px, nf, kf), ma(px, ns, ks)
    hi, lo = np.maximum(a, b), np.minimum(a, b)
    setv = pd.Series(np.nan, index=px.index)
    setv[px > hi] = 1.0
    setv[px < lo] = 0.0
    warm = max(_warm(nf, kf), _warm(ns, ks))
    setv.iloc[:warm] = np.nan
    state = _hold(setv)
    ta, tb = next_thresh(px, nf, kf), next_thresh(px, ns, ks)
    p = px.iloc[-1]
    zone = "above" if p > hi.iloc[-1] else ("below" if p < lo.iloc[-1] else "between")
    trig = {"exit": min(ta, tb), "enter": max(ta, tb), "zone": zone}
    return state, {s["lines"][0]: a, s["lines"][1]: b}, trig


TEMPLATE_LABELS = [
    "Price above the 150 and 200-day averages",
    "150-day above the 200-day",
    "200-day higher than a month ago",
    "50-day above the 150 and 200-day",
    "Price above the 50-day",
    "At least 30% above the 52-week low",
    "Within 25% of the 52-week high",
]


def rule_template(px, s):
    s50, s150, s200 = px.rolling(50).mean(), px.rolling(150).mean(), px.rolling(200).mean()
    s200p = s200.shift(21)
    low52, high52 = px.rolling(252).min(), px.rolling(252).max()
    conds = [
        (px > s150) & (px > s200),
        s150 > s200,
        s200 > s200p,
        (s50 > s150) & (s50 > s200),
        px > s50,
        px >= 1.3 * low52,
        px >= 0.75 * high52,
    ]
    allok = conds[0]
    for c in conds[1:]:
        allok = allok & c
    valid = s200p.notna() & low52.notna()
    setv = pd.Series(np.nan, index=px.index)
    setv[allok] = 1.0
    setv[px < s50] = 0.0
    setv[~valid] = np.nan
    state = _hold(setv)
    checks = [(lab, bool(c.iloc[-1])) for lab, c in zip(TEMPLATE_LABELS, conds)]
    t50, t150, t200 = next_thresh(px, 50, "sma"), next_thresh(px, 150, "sma"), next_thresh(px, 200, "sma")
    structural_ok = checks[1][1] and checks[2][1] and checks[3][1]
    enter = max(t50, t150, t200, 1.3 * float(low52.iloc[-1]), 0.75 * float(high52.iloc[-1])) if structural_ok else None
    trig = {"exit": t50, "enter": enter, "checks": checks, "structural_ok": structural_ok}
    return state, {"50-day SMA": s50, "150-day SMA": s150, "200-day SMA": s200}, trig


def rule_stage(px, s):
    s30 = px.rolling(30).mean()
    rising = s30 > s30.shift(4)
    setv = pd.Series(np.nan, index=px.index)
    setv[(px > s30) & rising] = 1.0
    setv[px < s30] = 0.0
    setv.iloc[:34] = np.nan
    state = _hold(setv)
    thr = next_thresh(px, 30, "sma")
    sum29 = float(px.iloc[-29:].sum())
    rise_need = 30 * float(s30.iloc[-4]) - sum29     # next close that keeps the average rising
    trig = {"exit": thr, "enter": max(thr, rise_need), "rising": bool(rising.iloc[-1])}
    return state, {"30-week SMA": s30}, trig


def rule_faber(px, s):
    s10 = px.rolling(10).mean()
    setv = pd.Series(np.where(px > s10, 1.0, 0.0), index=px.index)
    setv[s10.isna()] = np.nan
    state = _hold(setv)
    thr = next_thresh(px, 10, "sma")
    return state, {"10-month SMA": s10}, {"exit": thr, "enter": thr}


def rule_tsmom(px, s, irx):
    rf_m = irx.groupby(irx.index.to_period("M")).mean()
    rf12 = rf_m.rolling(12).mean()
    rf12 = pd.Series(rf12.reindex(px.index.to_period("M")).values, index=px.index).ffill()
    base = px.shift(12) * (1 + rf12)
    setv = pd.Series(np.where(px > base, 1.0, 0.0), index=px.index)
    setv[base.isna()] = np.nan
    state = _hold(setv)
    thr = float(px.iloc[-12]) * (1 + float(rf12.iloc[-1]))
    return state, {"12 months ago + T-bills": base}, {"exit": thr, "enter": thr}


def rule_hold(px, s):
    state = pd.Series(1.0, index=px.index)
    return state, {}, {}


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------
def _perf(ret, rf, periods):
    ret = ret.dropna()
    if len(ret) < periods // 2:
        return None
    rf = rf.reindex(ret.index).fillna(0)
    eq = (1 + ret).cumprod()
    yrs = len(ret) / periods
    sd = ret.std()
    return {
        "cagr": float(eq.iloc[-1] ** (1 / yrs) - 1),
        "total": float(eq.iloc[-1] - 1),
        "vol": float(sd * np.sqrt(periods)),
        "sharpe": float((ret - rf).mean() / sd * np.sqrt(periods)) if sd > 0 else None,
        "maxdd": float((eq / eq.cummax() - 1).min()),
        "years": float(yrs),
    }


def _next_check(bar, asof, crypto, bar_end, complete):
    if bar == "D":
        return asof + (pd.Timedelta(days=1) if crypto else pd.offsets.BDay(1))
    if not complete:
        return bar_end
    if bar == "W":
        return asof + pd.Timedelta(days=7)
    nxt = (asof + pd.offsets.MonthEnd(1)).normalize()
    if not crypto and nxt.weekday() >= 5:
        nxt = nxt - pd.offsets.BDay(1)
    return nxt


def _calls(state, px, live_price, live_date):
    ch = state.dropna()
    if ch.empty:
        return []
    flips = ch[ch.ne(ch.shift())]
    out = []
    for i, (d, v) in enumerate(flips.items()):
        p0 = float(px.loc[d])
        if i + 1 < len(flips):
            d1 = flips.index[i + 1]
            p1, closed = float(px.loc[d1]), True
        else:
            d1, p1, closed = live_date, live_price, False
        move = p1 / p0 - 1
        out.append({
            "date": d, "state": int(v), "price": p0, "end": d1, "end_price": p1,
            "move": move, "closed": closed,
            "right": (move > 0) if v == 1 else (move < 0),
        })
    return out


def evaluate(sym, strat, close, irx, now):
    t = next(x for x in TICKERS if x["sym"] == sym)
    crypto = t["crypto"]
    periods = 365 if crypto else 252
    bars, complete, bar_end = to_bars(close, strat["bar"], crypto, now)
    done = bars if complete else bars.iloc[:-1]
    kind = strat["kind"]
    if kind == "band":
        state, lines, trig = rule_band(done, strat)
    elif kind == "template":
        state, lines, trig = rule_template(done, strat)
    elif kind == "stage":
        state, lines, trig = rule_stage(done, strat)
    elif kind == "faber":
        state, lines, trig = rule_faber(done, strat)
    elif kind == "tsmom":
        state, lines, trig = rule_tsmom(done, strat, irx)
    else:
        state, lines, trig = rule_hold(done, strat)

    # daily positions: act on the session after the signal bar
    pos = state.reindex(close.index, method="ffill").shift(1)
    if kind == "hold":
        pos = pd.Series(1.0, index=close.index)
    pos = pos[pos.index >= GRADE_START]
    pos = pos[pos.notna()]
    r = close.pct_change().reindex(pos.index)
    rf = (irx.reindex(close.index, method="ffill").fillna(0) / periods).reindex(pos.index)
    cost = (COST_BPS["crypto"] if crypto else COST_BPS["default"]) / 1e4
    strat_r = pos * r + (1 - pos) * rf - pos.diff().abs().fillna(0) * cost
    bh_r = r.copy()
    if len(strat_r):
        strat_r.iloc[0] = np.nan      # first day has no prior close in-window
        bh_r.iloc[0] = np.nan

    asof = close.index[-1]
    live = float(close.iloc[-1])
    five = asof - pd.DateOffset(years=5)
    stats = {
        "full": {"strat": _perf(strat_r, rf, periods), "bh": _perf(bh_r, rf, periods)},
        "5y": {"strat": _perf(strat_r[strat_r.index > five], rf, periods), "bh": _perf(bh_r[bh_r.index > five], rf, periods)},
    }
    yrs = len(pos) / periods if len(pos) else 1
    stats["switches_per_year"] = float((pos.diff().abs() > 0).sum() / yrs)
    stats["invested"] = float(pos.mean()) if len(pos) else None
    stats["start"] = pos.index[0] if len(pos) else None

    calls = _calls(state[state.index >= GRADE_START - pd.Timedelta(days=40)], done, live, asof) if kind != "hold" else []
    closed = [c for c in calls if c["closed"]]
    bat = {
        "n": len(closed),
        "right": sum(1 for c in closed if c["right"]),
        "in_avg": float(np.mean([c["move"] for c in closed if c["state"] == 1])) if any(c["state"] == 1 for c in closed) else None,
        "out_avg": float(np.mean([c["move"] for c in closed if c["state"] == 0])) if any(c["state"] == 0 for c in closed) else None,
    }
    bat["avg"] = bat["right"] / bat["n"] if bat["n"] else None

    cur_state = int(state.dropna().iloc[-1]) if state.notna().any() else None
    cur_call = calls[-1] if calls else None
    nxt = _next_check(strat["bar"], asof, crypto, bar_end, complete)

    # equity curves (weekly samples) for the chart
    eq_s = (1 + strat_r.fillna(0)).cumprod()
    eq_b = (1 + bh_r.fillna(0)).cumprod()
    wk = eq_s.groupby(eq_s.index.to_period("W")).tail(1).index
    equity = {"dates": list(wk), "strat": eq_s.loc[wk].tolist(), "bh": eq_b.loc[wk].tolist()}

    # price window (last ~3 years) with rule lines and positions
    w0 = asof - pd.DateOffset(years=3)
    win = close[close.index > w0]
    line_win = {}
    for k, s in lines.items():
        s = s.dropna()
        s = s[s.index > w0 - pd.Timedelta(days=40)]
        line_win[k] = s
    pos_win = state.reindex(win.index, method="ffill")

    return {
        "sym": sym, "strategy": strat["slug"], "asof": asof, "price": live,
        "state": cur_state, "since": cur_call["date"] if cur_call else stats["start"],
        "since_price": cur_call["price"] if cur_call else None,
        "trigger": trig, "bar": strat["bar"], "next_check": nxt,
        "bar_complete": complete, "stats": stats, "calls": calls, "batting": bat,
        "equity": equity, "window": {"price": win, "lines": line_win, "pos": pos_win},
        "periods": periods,
    }


def run(prices, irx, now):
    results = {}
    for t in TICKERS:
        c = prices[t["sym"]]
        for s in STRATEGIES:
            results[(t["sym"], s["slug"])] = evaluate(t["sym"], s, c, irx, now)
    return results
