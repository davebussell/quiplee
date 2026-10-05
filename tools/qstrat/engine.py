"""Play engine: cached prices in, graded backtests and next moves out.

Every play is evaluated on finished bars only (daily, weekly or month-end),
acted on at the next session, charged a trading cost per switch, and credited
the T-bill yield while out. The "next move" is found by asking the play itself
what it would say after one more bar at a range of hypothetical closes, then
narrowing each flip point down to a fraction of a cent.
"""
import datetime as dt
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .cal import future_sessions
from .content import TICKERS, PLAYS
from . import risk

ET = ZoneInfo("America/New_York")
GRADE_START = pd.Timestamp("2005-01-01")
COST_BPS = {"crypto": 10, "micro": 30, "default": 5}   # per position change
PRICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "prices")
BENCH = "SPY"
HEAVY = ("window", "calls")   # the bulky parts of a result: the chart window and the full call list


class Result(dict):
    """One play x ticker result. With run(spill=folder), the bulky parts (HEAVY)
    are kept in one file per ticker instead of in memory, and load on first use;
    "last_call" and "n_calls" stay in memory for the cross-stock pages."""
    __slots__ = ()

    def __missing__(self, key):
        path = dict.get(self, "_spill")
        if key in HEAVY and path:
            return _heavy(path)[self["strategy"]][key]
        raise KeyError(key)


_HEAVY_CACHE = {}


def _heavy(path):
    """The spilled parts of one ticker's results (the last ticker read stays cached)."""
    hit = _HEAVY_CACHE.get(path)
    if hit is None:
        import pickle
        with open(path, "rb") as f:
            hit = pickle.load(f)
        _HEAVY_CACHE.clear()
        _HEAVY_CACHE[path] = hit
    return hit


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def price_file(sym, base=PRICE_DIR):
    return os.path.join(base, sym.replace("^", "_").replace(".", "-").lower() + ".csv")


def _read(sym, base):
    d = pd.read_csv(price_file(sym, base), index_col="date", parse_dates=["date"])
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["close"])
    for c in ["open", "high", "low"]:
        d[c] = d[c].fillna(d["close"])
    d["high"] = d[["high", "open", "close"]].max(axis=1)
    d["low"] = d[["low", "open", "close"]].min(axis=1)
    d["volume"] = d["volume"].fillna(0).astype(float)
    return d[["open", "high", "low", "close", "volume"]].astype(float)


def _drop_partial(d, crypto, now):
    """Drop today's still-forming bar so every signal uses a finished close."""
    last = d.index[-1].date()
    if crypto:
        if last >= dt.datetime.now(dt.timezone.utc).date():
            return d.iloc[:-1]
    elif last >= now.date() and (now.hour, now.minute) < (16, 30):
        return d.iloc[:-1]
    return d


def load_all(now=None, base=PRICE_DIR):
    """Prices for every ticker that has enough history. Tickers without a usable
    price file (e.g. a reader request whose download failed) are dropped from the
    shared TICKERS list in place, so no page or link refers to them."""
    now = now or dt.datetime.now(ET)
    irx = _read("^IRX", base)["close"] / 100.0
    prices, keep = {}, []
    for t in TICKERS:
        try:
            d = _drop_partial(_read(t["sym"], base), t["crypto"], now)
        except (OSError, ValueError, KeyError) as ex:
            print(f"skipping {t['sym']}: no usable price file ({ex.__class__.__name__})")
            continue
        if len(d) < 60:
            print(f"skipping {t['sym']}: only {len(d)} sessions of history")
            continue
        prices[t["sym"]] = d
        keep.append(t)
    TICKERS[:] = keep
    return prices, irx, now


# --------------------------------------------------------------------------
# Bars
# --------------------------------------------------------------------------
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "hc": "max"}


def to_bars(d, bar, crypto, now):
    """Resample daily OHLCV to the play's bar. Each bar is stamped with the date
    of its last actual session. Returns (bars, last_bar_complete, bar_end)."""
    d = d.assign(hc=d["close"])
    if bar == "D":
        return d, True, d.index[-1]
    freq = ("W-SUN" if crypto else "W-FRI") if bar == "W" else "M"
    key = d.index.to_period(freq)
    g = d.groupby(key)
    bars = g.agg(AGG)
    last_dates = g.apply(lambda s: s.index[-1])
    bars.index = pd.DatetimeIndex(last_dates.values)
    per = key[-1]
    end = per.end_time.normalize()
    asof = d.index[-1]
    if bar == "W":
        complete = asof >= end or (not crypto and asof.weekday() == 4) or now.date() > end.date()
    else:
        if crypto:
            complete = asof >= end
        else:
            complete = (asof + pd.offsets.BDay(1)).month != asof.month or now.date() > end.date()
        if not crypto:
            end = (end - pd.offsets.BDay(0)) if end.weekday() < 5 else end - pd.offsets.BDay(1)
    return bars, bool(complete), end


# --------------------------------------------------------------------------
# Context and the next-move solver
# --------------------------------------------------------------------------
def make_ctx(t, idx, bench_close, irx, future=None):
    is_bench = t["sym"] == BENCH
    return {
        "crypto": t["crypto"],
        "bench": None if is_bench else bench_close.reindex(idx, method="ffill"),
        "bench_full": bench_close,
        "irx_daily": irx,
        "future": future,
    }


def _hyp_row(done, partial, P, nxt_date):
    if partial is not None:
        o, h, l_, v, hc = partial["open"], max(partial["high"], P), min(partial["low"], P), partial["volume"], max(partial["hc"], P)
        date = partial.name
    else:
        last = float(done["close"].iloc[-1])
        o, h, l_, hc = last, max(last, P), min(last, P), P
        v = float(done["volume"].iloc[-20:].mean()) if len(done) else 0.0
        date = nxt_date
    return pd.DataFrame({"open": [o], "high": [h], "low": [l_], "close": [P], "volume": [v], "hc": [hc]},
                        index=pd.DatetimeIndex([date]))


def solve(play, t, done, partial, state0, ref, bench_close, irx, future, bar):
    """Find the closes on the next bar that would flip the play.

    Returns {"segments": [(lo, hi), ...], "span": (lo, hi), "now": state if
    the current partial bar closed at today's price}. lo/hi of None mean the
    segment runs off the searched range."""
    L = play.get("warm", 420) if bar == "D" else 100000
    tail = done.iloc[-L:]
    if len(tail) < len(done) and state0 is not None:
        # path-dependent rules must agree with the full history on today's call
        chk = play["fn"](tail, make_ctx(t, tail.index, bench_close, irx, future))["state"].iloc[-1]
        if pd.isna(chk) or int(chk) != state0:
            tail = done
    nxt = future[0] if future is not None and len(future) else done.index[-1] + pd.Timedelta(days=1)
    fut2 = future[1:] if future is not None and len(future) else None
    df2 = pd.concat([tail, _hyp_row(tail, partial, float(tail["close"].iloc[-1]), nxt)])
    ctx2 = make_ctx(t, df2.index, bench_close, irx, fut2)
    h0 = df2.iloc[-1].copy()
    ci = {c: df2.columns.get_loc(c) for c in df2.columns}

    def f(P):
        """The play's call if the next bar closed at P (the bar is reused in place)."""
        if partial is not None:
            hi, lo_, hc = max(partial["high"], P), min(partial["low"], P), max(partial["hc"], P)
        else:
            hi, lo_, hc = max(h0["open"], P), min(h0["open"], P), P
        df2.iat[-1, ci["close"]] = P
        df2.iat[-1, ci["high"]] = hi
        df2.iat[-1, ci["low"]] = lo_
        df2.iat[-1, ci["hc"]] = hc
        st = play["fn"](df2, ctx2)["state"]
        v = st.iloc[-1]
        return None if pd.isna(v) else int(v)

    wide = t["crypto"] or t.get("micro") or bar == "M"
    lo_m, hi_m = (0.5, 2.0) if wide else ((0.6, 1.6) if bar == "W" else (0.7, 1.4))
    grid = np.unique(np.concatenate([np.exp(np.linspace(np.log(lo_m), np.log(hi_m), 11)), [1.0]])) * ref
    vals = [f(P) for P in grid]
    if state0 is not None and not any(v is not None and v != state0 for v in vals):
        # nothing nearby: look further out so slow rules still show a level
        far = np.array([0.25, (0.25 * lo_m) ** 0.5, lo_m * 0.85, hi_m * 1.2, (4.0 * hi_m) ** 0.5, 4.0]) * ref
        grid = np.concatenate([far[:3], grid, far[3:]])
        vals = [f(P) for P in far[:3]] + vals + [f(P) for P in far[3:]]
    out = {"segments": [], "span": (float(grid[0]), float(grid[-1])), "now": vals[list(grid).index(ref)] if ref in grid else f(ref)}
    if state0 is None:
        return out

    def edge(a, b):
        """a: a grid close that keeps the call, b: one that flips it."""
        fa = vals_map[a]
        for _ in range(40):
            if abs(np.log(b / a)) < 2e-5:
                break
            m = (a * b) ** 0.5
            if f(m) == fa:
                a = m
            else:
                b = m
        return (a * b) ** 0.5

    vals_map = dict(zip(grid, vals))
    flip = [v is not None and v != state0 for v in vals]
    i = 0
    while i < len(grid):
        if not flip[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(grid) and flip[j + 1]:
            j += 1
        lo = None if i == 0 else edge(grid[i - 1], grid[i])
        hi = None if j == len(grid) - 1 else edge(grid[j + 1], grid[j])
        out["segments"].append((lo, hi))
        i = j + 1
    return out


def next_calendar_flip(cal_series, last_date, state0):
    fut = cal_series[cal_series.index > last_date]
    ch = fut[fut != state0]
    return (ch.index[0], int(ch.iloc[0])) if len(ch) else (None, None)


def next_window(season, asof, state0):
    """For MACD-timed seasonal plays: the date the relevant window opens."""
    (bm, bd), (sm, sd) = season
    md = asof.month * 100 + asof.day
    b, s = bm * 100 + bd, sm * 100 + sd
    in_buy = (md >= b) or (md < s)
    if state0 == 0 and not in_buy:
        return pd.Timestamp(asof.year, bm, bd), "buy"
    if state0 == 1 and in_buy:
        y = asof.year + (1 if md >= b else 0)
        return pd.Timestamp(y, sm, sd), "sell"
    return None, ("buy" if in_buy else "sell")


# --------------------------------------------------------------------------
# Grading
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


def _next_check(bar, asof, crypto, bar_end, complete, future):
    if bar == "D":
        return future[0] if future is not None and len(future) else asof + pd.offsets.BDay(1)
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
    idx = list(flips.index)
    for i, (d, v) in enumerate(flips.items()):
        p0 = float(px.loc[d])
        if i + 1 < len(idx):
            d1 = idx[i + 1]
            p1, closed = float(px.loc[d1]), True
        else:
            d1, p1, closed = live_date, live_price, False
        move = p1 / p0 - 1
        out.append({"date": d, "state": int(v), "price": p0, "end": d1, "end_price": p1,
                    "move": move, "closed": closed, "right": (move > 0) if v == 1 else (move < 0)})
    return out


def evaluate(t, play, d, bench_close, irx, now, future):
    crypto = t["crypto"]
    periods = 365 if crypto else 252
    bar = play["bar"]
    bars, complete, bar_end = to_bars(d, bar, crypto, now)
    done = bars if complete else bars.iloc[:-1]
    partial = None if complete else bars.iloc[-1]
    close = d["close"]
    asof, live = close.index[-1], float(close.iloc[-1])
    hold = play.get("benchmark", False)

    out = play["fn"](done, make_ctx(t, done.index, bench_close, irx, future if bar == "D" else None)) if len(done) else {"state": pd.Series(dtype=float), "lines": [], "panel": None, "extra": {}}
    state = out["state"]

    # daily positions: act on the session after the signal bar
    if hold:
        pos = pd.Series(1.0, index=close.index)
    else:
        pos = state.reindex(close.index, method="ffill").shift(1)
    pos = pos[(pos.index >= GRADE_START) & pos.notna()]
    r = close.pct_change().reindex(pos.index)
    rf = (irx.reindex(close.index, method="ffill").fillna(0) / periods).reindex(pos.index)
    cost = (COST_BPS["micro"] if t.get("micro") else COST_BPS["crypto"] if crypto else COST_BPS["default"]) / 1e4
    strat_r = pos * r + (1 - pos) * rf - pos.diff().abs().fillna(0) * cost
    bh_r = r.copy()
    if len(strat_r):
        strat_r.iloc[0] = np.nan
        bh_r.iloc[0] = np.nan

    five = asof - pd.DateOffset(years=5)
    stats = {
        "full": {"strat": _perf(strat_r, rf, periods), "bh": _perf(bh_r, rf, periods)},
        "5y": {"strat": _perf(strat_r[strat_r.index > five], rf, periods), "bh": _perf(bh_r[bh_r.index > five], rf, periods)},
    }
    yrs = len(pos) / periods if len(pos) else 1
    stats["switches_per_year"] = float((pos.diff().abs() > 0).sum() / yrs) if len(pos) else 0.0
    stats["invested"] = float(pos.mean()) if len(pos) else None
    stats["start"] = pos.index[0] if len(pos) else None

    calls = [] if hold else _calls(state[state.index >= GRADE_START - pd.Timedelta(days=40)], done["close"], live, asof)
    closed = [c for c in calls if c["closed"]]
    ins = [c["move"] for c in closed if c["state"] == 1]
    outs = [c["move"] for c in closed if c["state"] == 0]
    bat = {"n": len(closed), "right": sum(1 for c in closed if c["right"]),
           "in_avg": float(np.mean(ins)) if ins else None, "out_avg": float(np.mean(outs)) if outs else None}
    bat["avg"] = bat["right"] / bat["n"] if bat["n"] else None

    cur_state = None if hold or not state.notna().any() else int(state.dropna().iloc[-1])
    if hold:
        cur_state = 1
    cur_call = calls[-1] if calls else None

    # next move
    trig = {"kind": "none", "extra": out.get("extra", {})}
    if not hold and cur_state is not None:
        if play.get("calendar"):
            cal = out["extra"].get("calendar")
            dte, to = next_calendar_flip(cal, done.index[-1], cur_state) if cal is not None else (None, None)
            trig.update(kind="date", date=dte, to=to)
        else:
            sv = solve(play, t, done, partial, cur_state, live, bench_close, irx, future if bar == "D" else None, bar)
            trig.update(kind="price", **sv)
            if play.get("season") and not sv["segments"]:
                wd, which = next_window(play["season"], asof, cur_state)
                if wd is not None:
                    trig.update(kind="window", date=wd, which=which)
    trig["extra"] = {k: v for k, v in out.get("extra", {}).items() if k != "calendar"}

    # equity curves (weekly samples) for the chart
    eq_s = (1 + strat_r.fillna(0)).cumprod()
    eq_b = (1 + bh_r.fillna(0)).cumprod()
    wk = eq_s.groupby(eq_s.index.to_period("W")).tail(1).index
    equity = {"dates": wk, "strat": eq_s.loc[wk].to_numpy(dtype=np.float32), "bh": eq_b.loc[wk].to_numpy(dtype=np.float32)}

    # price window with lines, panel and positions
    yrs_win = 3 if hold else 2
    w0 = asof - pd.DateOffset(years=yrs_win)
    win = close[close.index > w0]
    lines = []
    for lab, s, role in out.get("lines", []):
        s = s.reindex(win.index, method="ffill") if len(s) else s
        lines.append((lab, s.astype(np.float32), role))
    pnl = None
    if out.get("panel"):
        pn = dict(out["panel"])
        pn["series"] = [(lab, s.reindex(win.index, method="ffill").astype(np.float32), role) for lab, s, role in pn["series"]]
        pnl = pn
    pos_win = state.reindex(win.index, method="ffill") if not hold else None
    # weekly call history (last two years) for the plays-over-time heatmap
    if hold:
        hist = "1" * 104
    else:
        st_d = state.reindex(close.index, method="ffill")
        wk = st_d.groupby(st_d.index.to_period("W-FRI")).last().iloc[-104:]
        hist = "".join("-" if pd.isna(v) else str(int(v)) for v in wk.values)

    return Result({
        "sym": t["sym"], "strategy": play["slug"], "asof": asof, "price": live,
        "state": cur_state, "since": cur_call["date"] if cur_call else stats["start"],
        "since_price": cur_call["price"] if cur_call else None,
        "trigger": trig, "bar": bar, "next_check": _next_check(bar, asof, crypto, bar_end, complete, future),
        "bar_complete": complete, "stats": stats, "calls": calls, "batting": bat,
        "equity": equity, "window": {"price": win, "lines": lines, "panel": pnl, "pos": pos_win},
        "periods": periods, "hist": hist,
        "last_call": calls[-1] if calls else None, "n_calls": len(calls),
    })


# --------------------------------------------------------------------------
# Running everything (one process per ticker)
# --------------------------------------------------------------------------
_G = {}


def _run_ticker(sym):
    t = next(x for x in TICKERS if x["sym"] == sym)
    d = _G["prices"][sym]
    bench = _G["prices"][BENCH]["close"]
    future = future_sessions(d.index[-1], t["crypto"])
    out = {}
    for p in _G["plays"]:
        out[(sym, p["slug"])] = evaluate(t, p, d, bench, _G["irx"], _G["now"], future)
    # per-ticker extras: crash exposure, three years of candles, the heatmap's week axis
    bclose = _G["prices"][t["bench"]]["close"] if t.get("bench") in _G["prices"] else None
    yr = d[d.index > d.index[-1] - pd.DateOffset(years=3)]    # 2 years shown + a year to warm up the 200-day average
    weeks = d["close"].groupby(d.index.to_period("W-FRI")).last().index[-104:]
    out[(sym, "__meta")] = {
        "risk": risk.assess(t, d["close"], bclose, _G.get("fund", {}).get(sym)),
        "ohlc": yr[["open", "high", "low", "close", "volume"]].astype("float32"),
        "weeks": [w.end_time.normalize() for w in weeks],
        "first": d.index[0],
    }
    _share(out)
    if _G.get("spill"):
        _spill(sym, out, _G["spill"])
    return out


def _share(out):
    """Plays on the same ticker often have identical equity dates and buy-and-hold
    curves; point them all at one copy."""
    import hashlib
    seen = {}
    for k, r in out.items():
        if k[1] == "__meta":
            continue
        eq = r["equity"]
        for f in ("dates", "bh"):
            v = eq[f]
            raw = v.asi8.tobytes() if f == "dates" else np.ascontiguousarray(v).tobytes()
            eq[f] = seen.setdefault((f, hashlib.blake2b(raw, digest_size=16).digest()), v)


def _spill(sym, out, folder):
    """Move each result's bulky parts into one file for the ticker (buy and hold keeps
    its price window in memory: the stock lists read its one-year change)."""
    import pickle
    path = os.path.join(folder, sym.replace("^", "_").replace("/", "_") + ".pkl")
    heavy = {}
    for k, r in out.items():
        if k[1] == "__meta" or k[1] == "buy-and-hold":
            continue
        heavy[k[1]] = {f: r.pop(f) for f in HEAVY}
        r["_spill"] = path
    with open(path, "wb") as f:
        pickle.dump(heavy, f, protocol=pickle.HIGHEST_PROTOCOL)


def run(prices, irx, now, plays=None, tickers=None, workers=None, spill=None):
    """Every play on every ticker. spill: a folder for the bulky parts of each result
    (see Result), which keeps the build's memory flat as the universe grows."""
    if spill:
        os.makedirs(spill, exist_ok=True)
    _G.update(prices=prices, irx=irx, now=now, plays=plays or PLAYS, fund=risk.load_fundamentals(TICKERS), spill=spill)
    syms = [t["sym"] for t in (tickers or TICKERS)]
    workers = workers or max(1, min(len(syms), os.cpu_count() or 1))
    results = {}
    if workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        with ctx.Pool(workers) as pool:
            for part in pool.imap_unordered(_run_ticker, syms):
                results.update(part)
    else:
        for s in syms:
            results.update(_run_ticker(s))
    return results
