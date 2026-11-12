"""The AI sell-off of October and November 2026, in two pieces (Dave, Nov 11, 2026: "The last couple weeks have
resulted in crazy stuff in the market. Can you post a couple new articles and specifically answer if we predicted
what is happening and answer if we would have had an edge."):

* articles/the-ai-sell-off/ (WHAT_*): what happened from the October 6 record to the November 10 close, day by day,
  and where the damage landed among the stocks Be The Puck covers;
* articles/did-we-see-it-coming/ (SEEN_*): what the site said before it started (the gauges, the written pieces)
  and how the standard signal's calls did, U.S. and TSX apart.

Every number about the market and the covered stocks is computed from the site's own data for fixed dates (PEAK,
D0, LOW, END), so a nightly rebuild gives the same answers. The calls are rebuilt point-in-time
(callpath.daily_path: prices and the plays' calls to each close, the market guard and sticky calls), never stored,
as every other test on the site is. The dated news is written and sourced (SOURCES).
"""
import html
import json
import math
import os

import numpy as np
import pandas as pd

e = html.escape
WRITTEN = pd.Timestamp("2026-11-11")
PEAK = pd.Timestamp("2026-10-06")       # the S&P 500's and Nasdaq-100's record close
MID3 = pd.Timestamp("2026-10-21")       # the first close under model version 3 (factors.MODEL3_SINCE)
D0 = pd.Timestamp("2026-10-28")         # the close before Alphabet's and Microsoft's reports (after that day's close)
EVE = pd.Timestamp("2026-11-04")        # the close before the worst day
LOW = pd.Timestamp("2026-11-05")        # the low close
END = pd.Timestamp("2026-11-10")        # the last close before writing
MODEL_START = pd.Timestamp("2026-10-13")   # the standard weights of today began here (scorecard.SINCE)

WHAT_PATH = "articles/the-ai-sell-off/"
WHAT_TITLE = "The AI sell-off: what happened, and where it hit"
WHAT_DEK = ("Chip stocks fell 21% in six sessions and the S&amp;P 500 had its worst day since April 2025, while the average "
            "stock barely moved and the TSX ended about where it started. The events day by day, and where the damage landed among the stocks we cover.")
SEEN_PATH = "articles/did-we-see-it-coming/"
SEEN_TITLE = "Did we see the sell-off coming, and would you have had an edge?"
SEEN_DEK = ("We didn't call the timing. The gauges flagged the kind of risk that broke; the signal was long the chip leaders at the top "
            "and had turned most of them to Sell before the worst day. Every call rebuilt from the data as it stood, U.S. and Canada graded apart.")
BUCKET_WHAT = "macro"
BUCKET_SEEN = "risk"
PATHS = (WHAT_PATH, SEEN_PATH)

# the chip, AI and big-tech names followed call by call
WATCH = ["NVDA", "AMD", "AVGO", "MU", "MRVL", "INTC", "ASML", "GOOGL", "META", "MSFT", "AMZN", "AAPL", "PLTR", "SHOP.TO", "CLS.TO"]
FUNDS = [("^GSPC", "S&amp;P 500"), ("^NDX", "Nasdaq-100"), ("RSP", "Equal-weight S&amp;P 500 (RSP)"), ("SMH", "Chip stocks (SMH)"),
         ("^GSPTSE", "TSX"), ("^RUT", "Russell 2000 (small companies)"), ("XLK", "Technology (XLK)"), ("XLV", "Health care (XLV)"),
         ("XLP", "Consumer staples (XLP)"), ("XLF", "Financials (XLF)"), ("XLE", "Energy (XLE)"), ("XLU", "Utilities (XLU)"),
         ("GLD", "Gold (GLD)"), ("BTC-USD", "Bitcoin")]


# ----------------------------------------------------------------------------------------------- formatting
def pc(v, d=1, sign=True):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    if v < 0 and round(abs(v) * 100, d):
        return "−" + s
    return ("+" + s) if sign and v > 0 and round(abs(v) * 100, d) else s


def pts(v, d=1):
    """A gap in percentage points, signed."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:.{d}f}"
    return ("−" if v < 0 and float(s) else "+" if v > 0 and float(s) else "") + s


def share(v):
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{round(100 * v)}%"


def cls(v, band=0.005):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return "up" if v >= band else "down" if v <= -band else ""


def day(d):
    return pd.Timestamp(d).strftime("%b %-d")


def pill(c):
    from .render import sig_pill
    return sig_pill(None if c is None or (isinstance(c, float) and math.isnan(c)) else int(c))


# ----------------------------------------------------------------------------------------------- data
def _close(site, sym):
    p = (site.prices or {}).get(sym)
    if p is not None:
        return p["close"]
    cache = site.__dict__.setdefault("_selloff_px", {})
    if sym not in cache:
        from . import macro
        cache[sym] = macro.px(sym)
    return cache[sym]


def _at(c, d):
    if c is None:
        return None
    x = c[c.index <= pd.Timestamp(d)]
    return float(x.iloc[-1]) if len(x) else None


def _ret(site, sym, d0, d1):
    c = _close(site, sym)
    a, b = _at(c, d0), _at(c, d1)
    return b / a - 1 if a and b else None


def ready(site):
    """True once the data reaches END (a build on older data skips the two pieces' numbers)."""
    return site.asof is not None and pd.Timestamp(site.asof) >= END and _close(site, "SPY") is not None


def _weather(site, when):
    """The Markets page's gauges as they read at the close of `when`: every series cut to that day, the jobless
    rate only once published (about five weeks after its month starts), the index trend with the plays' calls to then."""
    from . import macro
    from .factorgrade import _plays_share
    from .content import TICKERS
    orig = macro._csv
    T = pd.Timestamp(when)

    def cut(path, col=None):
        s = orig(path, col)
        if s is None:
            return None
        if path.endswith("fred_unrate.csv"):
            s = s.copy()
            s.index = s.index + pd.DateOffset(months=1) + pd.DateOffset(days=7)
        return s[s.index <= T]
    plays_in = {}
    for t in TICKERS:
        if t["sym"] in ("^GSPC", "^NDX"):
            k, n = _plays_share(site, t, pd.DatetimeIndex([T]))
            plays_in[t["sym"]] = (int(k[0]), int(n[0]))
    macro._csv = cut
    try:
        return macro.build(plays_in=plays_in)
    finally:
        macro._csv = orig


def _beta(site, t, d0):
    """Beta and annual volatility over the year to d0, against the stock's own index."""
    c, b = _close(site, t["sym"]), _close(site, t.get("bench"))
    if c is None or b is None:
        return np.nan, np.nan
    c = c[c.index <= d0].iloc[-253:]
    bc = b.reindex(c.index, method="ffill")
    r, rb = c.pct_change().iloc[1:], bc.pct_change().iloc[1:]
    ok = r.notna() & rb.notna()
    r, rb = r[ok], rb[ok]
    if len(r) < 120 or rb.var() <= 0:
        return np.nan, np.nan
    return float(np.cov(r, rb)[0, 1] / rb.var()), float(r.std() * np.sqrt(252))


def data(site):
    """Everything both pieces show, computed once per build."""
    got = site.__dict__.get("_selloff")
    if got is not None:
        return got
    from .callpath import daily_path
    from .factorgrade import _stocks, bench_of, market
    from . import secfund
    stocks = {t["sym"]: t for t in _stocks(site)}
    path = daily_path(site)
    path = path[path.sym.isin(stocks)]
    by_day = {d: g.set_index("sym") for d, g in path[path.d.isin([PEAK, MID3, D0, EVE, LOW, END])].groupby("d")}
    # 1. calls at each anchor close, graded to the low and to END, each stock against its market with dividends
    rows = []
    for d0 in (PEAK, MID3, D0, EVE):
        a = by_day.get(d0)
        if a is None:
            continue
        for sym, r in a.iterrows():
            t = stocks[sym]
            out = {"d0": d0, "sym": sym, "mkt": market(t), "call": r.call, "score": r.score}
            for lab, d1 in (("low", LOW), ("end", END)):
                rr, br = _ret(site, sym, d0, d1), _ret(site, bench_of(t), d0, d1)
                out[lab] = rr
                out["x" + lab] = rr - br if rr is not None and br is not None else None
            rows.append(out)
    C = pd.DataFrame(rows)

    def grade(d0, mkt, lab="end"):
        x = C[(C.d0 == d0) & (C.mkt == mkt)] if mkt != "all" else C[C.d0 == d0]
        g = {}
        for c in (1, 0, -1):
            y = x[x.call == c].dropna(subset=[lab])
            g[c] = {"n": len(y), "med": y[lab].median() if len(y) else None,
                    "beat": float((y["x" + lab] > 0).mean()) if len(y) and y["x" + lab].notna().any() else None}
        return g
    G = {(d0, m, lab): grade(d0, m, lab) for d0 in (PEAK, MID3, D0, EVE) for m in ("us", "tsx", "all") for lab in ("low", "end")}

    # 2. following along: equal-weight Buys, Holds and Sells, reset each close (as the scorecard's baskets)
    days = sorted(x for x in path.d.unique() if PEAK <= x <= END)
    calls_by = {d: g.set_index("sym") for d, g in path[path.d.isin(days)].groupby("d")}

    def basket(d0, mkt):
        out = {1: 1.0, 0: 1.0, -1: 1.0}
        dd = [d for d in days if d >= d0]
        for i in range(1, len(dd)):
            a, b = calls_by[dd[i - 1]], calls_by[dd[i]].p
            a = a[[market(stocks[s]) == mkt for s in a.index]]
            r = (b.reindex(a.index) / a.p - 1).dropna()
            g = a.call.reindex(r.index)
            for k in out:
                x = r[g == k]
                out[k] *= 1 + (float(x.mean()) if len(x) else 0.0)
        return {k: v - 1 for k, v in out.items()}
    B = {(d0, m): basket(d0, m) for d0 in (PEAK, D0) for m in ("us", "tsx")}
    mk = {(d0, m): _ret(site, "SPY" if m == "us" else "XIU.TO", d0, END) for d0 in (PEAK, D0) for m in ("us", "tsx")}

    # 3. the stocks that fell most from D0 to the low, and how they were called
    x0 = C[C.d0 == D0].copy()
    eve = by_day.get(EVE)
    x0["call_eve"] = x0.sym.map(eve.call) if eve is not None else np.nan
    hit = {}
    for m in ("us", "tsx"):
        x = x0[x0.mkt == m].dropna(subset=["low"]).sort_values("low")
        n5 = max(1, round(len(x) / 5))
        worst, best = x.head(n5), x.tail(n5)
        hit[m] = {"n": len(x), "n5": n5, "sells": int((worst.call == -1).sum()), "buys": int((worst.call == 1).sum()), "holds": int((worst.call == 0).sum()),
                  "sells_eve": int((worst.call_eve == -1).sum()), "base": float((x.call == -1).mean()) if len(x) else None,
                  "best_sells": int((best.call == -1).sum()), "worst": worst, "best": best, "med_worst": worst.low.median()}

    # 4. measures ranked at D0: which sorted the fallers from the rest
    M = x0[["sym", "mkt", "score", "low", "end"]].copy()
    a = by_day.get(D0)
    for k in ("plays", "offhigh", "trend"):
        M[k] = M.sym.map(a[k]) if a is not None else np.nan
    bv = {s: _beta(site, stocks[s], D0) for s in M.sym}
    M["beta"] = M.sym.map(lambda s: bv[s][0])
    M["vol"] = M.sym.map(lambda s: bv[s][1])
    M["r12"] = M.sym.map(lambda s: _ret(site, s, D0 - pd.DateOffset(years=1), D0))
    val = {}
    for s in M.sym:
        t = stocks[s]
        if market(t) != "us" or not secfund.has(t):
            continue
        rr = secfund.ratios(t, _at(_close(site, s), D0), D0.strftime("%Y-%m-%d"))
        pe = rr.get("pe")
        if pe is None:
            continue
        val[s] = {"ey": (1 / pe) if isinstance(pe, (int, float)) and pe > 0 else -1.0, "rg": rr.get("rg"), "eg": rr.get("eg"),
                  "pe": pe if isinstance(pe, (int, float)) else None}
    for k in ("ey", "rg", "eg", "pe"):
        M[k] = M.sym.map(lambda s: (val.get(s) or {}).get(k)).astype(float)
    us = M.mkt == "us"
    rk = M[us].dropna(subset=["ey"])[["ey", "rg", "eg"]].rank(pct=True)
    mix = rk.mean(axis=1, skipna=True).where(rk.notna().sum(axis=1) >= 2)
    M["mix"] = mix.reindex(M.index)
    for k in ("beta", "vol", "r12"):
        M["neg_" + k] = -M[k]

    def fifths(col, mkt, lab):
        x = M[M.mkt == mkt].dropna(subset=[col, lab])
        if len(x) < 40:
            return None
        q = np.floor(x[col].rank(pct=True, method="first") * 5 - 1e-9)
        top, bot = x[q == 4][lab].median(), x[q == 0][lab].median()
        return {"n": len(x), "top": top, "bot": bot, "gap": top - bot}
    MEAS = [("Off the high", "offhigh", "standard factor: nearest the 1-year high scores most"),
            ("Plays in", "plays", "standard factor: share of plays holding the stock"),
            ("Trend", "trend", "standard factor: furthest above the 200-day average scores most"),
            ("The standard score", "score", "the three together, as the signal weighs them"),
            ("Low P/E", "ey", "cheapest by earnings; money-losers count as dearest (SEC filers)"),
            ("Revenue growth", "rg", "fastest over the last four quarters (SEC filers)"),
            ("Low P/E + revenue + earnings growth", "mix", "the value-with-growth mix from What has an edge"),
            ("Low beta", "neg_beta", "swung least with its market over the past year"),
            ("Low volatility", "neg_vol", "smallest daily swings over the past year"),
            ("Smallest 12-month run-up", "neg_r12", "rose least over the year to Oct 28")]
    F = [(lab, col, note, {m: {lb: fifths(col, m, lb) for lb in ("low", "end")} for m in ("us", "tsx")}) for lab, col, note in MEAS]
    pe5 = None
    xs = M[us & (M.ey > 0)].dropna(subset=["end"])
    if len(xs) >= 40:
        q = np.floor(xs.ey.rank(pct=True, method="first") * 5 - 1e-9)
        pe5 = [{"pe": float((1 / xs[q == k].ey).median()), "end": float(xs[q == k].end.median()), "low": float(xs[q == k].low.median()), "n": int((q == k).sum())} for k in range(4, -1, -1)]
        loss = M[us & (M.ey < 0)].dropna(subset=["end"])
        pe5.append({"pe": None, "end": float(loss.end.median()) if len(loss) else None, "low": float(loss.low.median()) if len(loss) else None, "n": len(loss)})
    cheap_growing = None
    xv = M[us].dropna(subset=["ey", "end"])
    if len(xv) >= 40:
        r_ey, r_rg = xv.ey.rank(pct=True), xv.rg.rank(pct=True)
        cg = xv[(r_ey >= 0.6) & (r_rg >= 0.5)]
        fast = xv[r_rg >= 0.6]
        cheap_growing = {"n": len(cg), "end": float(cg.end.median()) if len(cg) else None, "fast_n": len(fast), "fast_end": float(fast.end.median()) if len(fast) else None,
                         "mix_top": list(M[us].dropna(subset=["mix"]).sort_values("mix").tail(round(us.sum() / 5)).sym)}

    # 5. the chip and big-tech names, call by call
    W = []
    for s in WATCH:
        if s not in stocks:
            continue
        x = path[path.sym == s].set_index("d")
        cells = []
        for d in (PEAK, MID3, D0, EVE, END):
            cells.append((x.call.get(d), x.score.get(d)) if d in x.index else (None, None))
        flip = None
        if x.call.get(PEAK) != -1:
            later = x[(x.index > PEAK) & (x.index <= END) & (x.call == -1)]
            flip = later.index[0] if len(later) else None
        W.append({"sym": s, "t": stocks[s], "cells": cells, "sell_from": flip, "r_peak": _ret(site, s, PEAK, END), "r_d0": _ret(site, s, D0, END),
                  "r_low": _ret(site, s, D0, LOW)})

    # 6. the market guard: how far each index got below its 1-year high
    guard = {}
    from .factors import GUARD
    for b in ("^GSPC", "^GSPTSE"):
        c = _close(site, b)
        if c is None:
            continue
        dd = (c / c.rolling(252, min_periods=120).max() - 1)
        dd = dd[(dd.index >= PEAK) & (dd.index <= END)]
        guard[b] = {"min": float(dd.min()), "day": dd.idxmin(), "need": GUARD}

    # 7. funds and indexes, and the covered stocks by group
    FUNDR = []
    for sym, lab in FUNDS:
        c = _close(site, sym)
        if c is None:
            continue
        FUNDR.append({"sym": sym, "lab": lab, "peak_low": _ret(site, sym, PEAK, LOW), "d0_low": _ret(site, sym, D0, LOW), "d0_end": _ret(site, sym, D0, END),
                      "peak_end": _ret(site, sym, PEAK, END)})
    x0["g"] = x0.sym.map(lambda s: stocks[s]["group"])
    x0["peak_end"] = x0.sym.map(lambda s: _ret(site, s, PEAK, END))
    grp = x0.groupby("g").agg(n=("low", "size"), low=("low", "median"), end=("end", "median"), peak=("peak_end", "median")).sort_values("low")
    grp = grp[grp.n >= 6]
    mkt_med = {m: {"low": x0[x0.mkt == m].low.median(), "end": x0[x0.mkt == m].end.median(), "up": float((x0[x0.mkt == m].end > 0).mean()), "n": int((x0.mkt == m).sum())}
               for m in ("us", "tsx")}
    movers = x0.dropna(subset=["end"]).sort_values("end")

    # 8. the daily moves for the timeline
    def move(d):
        out = {}
        for sym in ("^GSPC", "^NDX", "^GSPTSE", "SMH"):
            c = _close(site, sym)
            if c is None:
                continue
            x = c[c.index <= pd.Timestamp(d)]
            if len(x) >= 2 and x.index[-1] == pd.Timestamp(d):
                out[sym] = float(x.iloc[-1] / x.iloc[-2] - 1)
        return out
    week = {}
    for sym in ("^GSPC", "SMH"):
        c = _close(site, sym)
        if c is not None:
            w = c[c.index <= END].resample("W-FRI").last().pct_change()
            week[sym] = float(w.get(pd.Timestamp("2026-11-06"), np.nan))
    vix = _close(site, "^VIX")
    out = {"C": C, "G": G, "B": B, "mk": mk, "hit": hit, "F": F, "pe5": pe5, "cg": cheap_growing, "W": W, "guard": guard, "FUNDR": FUNDR,
           "grp": grp, "mkt_med": mkt_med, "movers": movers, "move": move, "week": week, "stocks": stocks,
           "vix": {d: _at(vix, d) for d in (PEAK, D0, LOW, END)}, "weather": {d: _weather(site, d) for d in (PEAK, D0, LOW, END)},
           "spx": {d: _at(_close(site, "^GSPC"), d) for d in (PEAK, D0, EVE, LOW, END)}}
    site.__dict__["_selloff"] = out
    return out


def _next_reports(syms):
    """{sym: (YYYY-MM-DD, after the close?)}: the first report after END on Yahoo's calendar (data/events), fixed to
    END so the list doesn't move as reports pass."""
    from .newsevents import EVENTS_DIR
    from .content import TICKERS
    out = {}
    slug = {t["sym"]: t["slug"] for t in TICKERS}
    for s in syms:
        p = os.path.join(EVENTS_DIR, slug.get(s, "") + ".json")
        if not os.path.exists(p):
            continue
        try:
            rows = json.load(open(p)).get("earn") or []
        except Exception:
            continue
        nx = sorted(r[0] for r in rows if r and r[0] > END.strftime("%Y-%m-%dT23:59:59Z") and r[2] is None and r[3] is None)
        if nx:
            if nx[0].endswith("T00:00:00Z"):           # a date with no time
                out[s] = (nx[0][:10], False)
                continue
            et = pd.Timestamp(nx[0]).tz_convert("America/New_York")
            out[s] = (et.strftime("%Y-%m-%d"), et.hour >= 16)
    return out


# ----------------------------------------------------------------------------------------------- piece 1: what happened
SOURCES_WHAT = [
    ("Reuters via The Standard: S&P 500, Nasdaq end sharply lower as revived AI doubts ignite tech selloff (Oct 22, 2026)", "https://www.thestandard.com.hk/finance/article/346283/SP-500-Nasdaq-end-sharply-lower-as-revived-AI-doubts-ignite-tech-selloff"),
    ("Federal Reserve: FOMC statement (Oct 28, 2026)", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm"),
    ("BNN Bloomberg: Bank of Canada raises key interest rate, says another hike possible (Oct 28, 2026)", "https://bnnbloomberg.ca/business/economics/2026/10/28/bank-of-canada-raises-key-interest-rate-says-another-hike-possible"),
    ("TheStreet: Alphabet drops on earnings miss as cash flows turn negative (Oct 28, 2026)", "https://pro.thestreet.com/stock-market-today/alphabet-drops-on-earnings-miss-cash-flows-turn-negative"),
    ("AP via WLOX: Wall Street tumbles to its worst day since June after the sell-off for tech stocks deepens (Oct 30, 2026)", "https://www.wlox.com/2026/10/30/wall-street-tumbles-its-worst-day-since-june-after-sell-off-tech-stocks-deepens/"),
    ("Scripps News via News 5 Cleveland: Democrats will win control of U.S. House (Nov 4, 2026)", "https://www.news5cleveland.com/politics/america-votes/democrats-will-win-control-of-us-house-retaking-control-from-republicans"),
    ("States Newsroom via Daily Montanan: Democrats score control of U.S. Senate (Nov 3–4, 2026)", "https://dailymontanan.com/?p=39937"),
    ("Al Jazeera: US markets rise as Democrats sweep midterm elections (Nov 4, 2026)", "https://www.aljazeera.com/economy/2026/11/4/us-markets-rise-as-democrats-sweep-midterm-elections"),
    ("Reuters via Star-Advertiser: Oil tumbles 9% as investors eye possible end to Iran war (Nov 4, 2026)", "https://www.staradvertiser.com/2026/11/04/breaking-news/oil-tumbles-9-as-investors-eye-possible-end-to-iran-war/"),
    ("AP via Boston.com: A brutal sell-off for AI stocks sends Wall Street reeling and the S&P 500 tumbles 4.4% (Nov 5, 2026)", "https://www.boston.com/news/national-news/2026/11/05/a-brutal-sell-off-for-ai-stocks-sends-wall-street-reeling-and-the-sp-500-tumbles-4-4/"),
    ("AP via AJC: US stocks rally and recover more of last week's losses as oil prices swing lower (Nov 9, 2026)", "https://www.ajc.com/news/2026/11/us-stocks-rally-and-recover-more-of-last-weeks-losses-as-oil-prices-swing-lower/"),
    ("Reuters via Star-Advertiser: Wall Street rallies after last week's AI rout; Nvidia falls (Nov 9, 2026)", "https://www.staradvertiser.com/2026/11/09/breaking-news/wall-street-rallies-after-last-weeks-ai-rout-nvidia-falls/"),
    ("Reuters via AOL: Hot October inflation report rattles markets (Nov 10, 2026)", "https://www.aol.com/articles/hot-october-inflation-report-rattles-135837000.html"),
    ("TheStreet: Stock market today, Nov. 10, 2026", "https://www.thestreet.com/stock-market-today/stock-market-today-dow-jones-sp-500-nasdaq-updates-nov-10-2026"),
    ("Trading Economics: TSX market news (Nov 6 and 10, 2026)", "https://tradingeconomics.com/canada/stock-market/news/599253"),
    ("Yahoo Finance earnings calendar, as stored in Be The Puck's data (data/events)", "https://finance.yahoo.com/calendar/earnings"),
]


def _mv(D, d):
    m = D["move"](d)
    bits = [f"S&amp;P 500 {pc(m['^GSPC'])}" if "^GSPC" in m else "", f"Nasdaq-100 {pc(m['^NDX'])}" if "^NDX" in m else "",
            f"chips (SMH) {pc(m['SMH'])}" if "SMH" in m else "", f"TSX {pc(m['^GSPTSE'])}" if "^GSPTSE" in m else ""]
    return " · ".join(b for b in bits if b)


def _timeline(D):
    spx = D["spx"]
    wk = D["week"]
    items = [
        (PEAK, "The S&amp;P 500 and the Nasdaq-100 close at records",
         f"The S&amp;P 500 closes at {spx[PEAK]:,.2f}. The fall that follows starts in the chip stocks."),
        (pd.Timestamp("2026-10-22"), "Meta's cash and a chip sell-off",
         "Meta beat estimates but reported its first cash outflow in more than a decade, tied to AI spending; chipmakers sold off and the Nasdaq had its steepest fall since June (Reuters)."),
        (D0, "Two central banks, then Alphabet",
         "The Bank of Canada raises its rate a quarter point to 2.50% (BNN Bloomberg). The Federal Reserve holds at 3.75–4.00%, on a 10–2 vote (Federal Reserve). "
         "After the close, Alphabet reports revenue of $127.6 billion, just short of estimates, capital spending of $51.4 billion, more than double a year earlier, and free cash flow of −$9.1 billion; "
         "Microsoft beats, with Azure up 48% (TheStreet)."),
        (pd.Timestamp("2026-10-29"), "Alphabet's worst day on record",
         "Alphabet falls more than 12% after burning more cash in the summer quarter than in the spring (AP)."),
        (pd.Timestamp("2026-10-30"), "Intel, Nvidia and Amazon",
         "Intel falls almost 29%, its worst day since 1974, on a profit forecast below expectations; Nvidia falls 4.9%; Amazon falls 1.9% after weaker profit and $42.4 billion of free cash outflow over 12 months. "
         "The S&amp;P 500's worst day since June. Brent crude is $113 a barrel (AP)."),
        (pd.Timestamp("2026-11-03"), "U.S. midterm elections",
         "The Associated Press projected that Democrats would win the House (Scripps News), and its call of Iowa's Senate race late that night was the one that made a Democratic Senate majority clear (States Newsroom). "
         "The next morning U.S. stocks opened higher; one analyst, Wedbush's Dan Ives, said a Democratic Senate would put hurdles in front of AI and tech legislation (Al Jazeera)."),
        (pd.Timestamp("2026-11-04"), "Oil drops on hopes for an end to the Iran war",
         "Brent falls 8.9% to $94.29 as investors look for an end to the U.S.-Israeli war with Iran; President Trump told the Financial Times the U.S. has no immediate plans to strike Iran (Reuters). "
         "Most stocks rise, the equal-weight S&amp;P 500 to a new high, while chip stocks keep falling."),
        (LOW, "The worst day since April 2025",
         f"The S&amp;P 500 falls to {spx[LOW]:,.2f}. Nvidia falls 9.3% and AMD 17.3%; South Korea's Kospi fell 5.3% that day. AP reported three worries behind it: that expensive borrowing could slow data-centre construction, "
         "that AI stocks had run into a bubble, and that the election results raised the chance of pauses in data-centre building amid concerns about power bills. "
         f"The VIX, the market's fear gauge, jumps to {D['vix'][LOW]:.1f}."),
        (pd.Timestamp("2026-11-06"), "The week",
         f"The S&amp;P 500 ends the week {pc(wk.get('^GSPC'))}, its worst week since April 2025, and the SMH chip fund {pc(wk.get('SMH'))} (Be The Puck's data)."),
        (pd.Timestamp("2026-11-09"), "A rebound, and oil lower again",
         "Brent falls 5.8% to $92.57, from above $112 at the start of the month, after President Trump told CNN a resumption of strikes was highly unlikely if talks progress. "
         "Nvidia falls 4.3% while its board investigates chief executive Jensen Huang over a personal relationship; AMD rebounds 13.3% (AP)."),
        (END, "Inflation runs hot",
         "October consumer prices rise 0.4%, against 0.3% expected, and 0.3% without food and energy, against 0.2%; futures move to price a Fed rate increase in December (Reuters). "
         "Gold falls about 2% and takes the TSX's gold miners down with it (Trading Economics)."),
    ]
    li = "".join(f'<li><span class="when">{day(d)}</span><b>{t}</b> {x}<span class="mv">{_mv(D, d)}</span></li>' for d, t, x in items)
    return f'<ol class="so-tl">{li}</ol>'


def _fund_table(D):
    rows = "".join(f'<tr><td>{r["lab"]}</td><td class="r {cls(r["peak_low"])}">{pc(r["peak_low"])}</td><td class="r {cls(r["d0_low"])}">{pc(r["d0_low"])}</td>'
                   f'<td class="r {cls(r["d0_end"])}">{pc(r["d0_end"])}</td><td class="r adv-col {cls(r["peak_end"])}">{pc(r["peak_end"])}</td></tr>' for r in D["FUNDR"])
    return (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Index or fund</th><th class="r">Oct 6 high to Nov 5 low</th><th class="r">Oct 28 to Nov 5</th>'
            f'<th class="r">Oct 28 to Nov 10</th><th class="r adv-col">Oct 6 to Nov 10</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="small muted">Closing prices; funds include dividends, indexes don\'t. The funds stand in for groups of stocks: SMH holds the largest chipmakers, XLK and the other XL funds the S&amp;P 500\'s sectors.</p>')


def _group_table(D, h):
    rows = "".join(f'<tr><td>{e(g)}</td><td class="r">{int(r.n)}</td><td class="r {cls(r.low)}">{pc(r.low)}</td><td class="r {cls(r.end)}">{pc(r.end)}</td>'
                   f'<td class="r adv-col {cls(r.peak)}">{pc(r.peak)}</td></tr>' for g, r in D["grp"].iterrows())
    return (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Group</th><th class="r">Stocks</th><th class="r" data-sort-first="asc">Median, Oct 28 to Nov 5</th>'
            f'<th class="r">Median, Oct 28 to Nov 10</th><th class="r adv-col">Median, Oct 6 to Nov 10</th></tr></thead><tbody>{rows}</tbody></table></div>')


def _movers(D, h, n=10):
    mv = D["movers"]
    S = D["stocks"]

    def li(x):
        return ", ".join(f'<a href="{h("stocks/" + S[r.sym]["slug"] + "/")}">{e(S[r.sym]["short"])}</a> {pc(r.end, 0)}' for _, r in x.iterrows())
    return (f'<p><b>Fell most, Oct 28 to Nov 10:</b> {li(mv.head(n))}.</p>'
            f'<p><b>Rose most:</b> {li(mv.tail(n).iloc[::-1])}.</p>')


def _calendar(D, h):
    S = D["stocks"]
    nx = _next_reports([s for s in WATCH + ["PANW", "WMT", "RY.TO", "TD.TO", "BMO.TO", "BNS.TO", "CM.TO"] if s in S])
    nx = sorted(((k, v) for k, v in nx.items() if v[0] <= "2026-12-31"), key=lambda kv: kv[1][0])
    items = "".join(f'<li><b>{pd.Timestamp(d).strftime("%b %-d")}</b> <a href="{h("stocks/" + S[s]["slug"] + "/")}">{e(S[s]["short"])}</a> reports'
                    f'{" after the close" if after else ""}</li>' for s, (d, after) in nx[:12])
    return items


def build_what(A):
    s = A.s
    depth = WHAT_PATH.count("/")
    h = A.h(depth)
    if not ready(s):
        body = f'<div class="prose"><p>This piece needs prices to the {END.strftime("%B %-d, %Y")} close.</p></div>'
        A.shell(WHAT_PATH, BUCKET_WHAT, WHAT_TITLE, WHAT_DEK, body, sources=SOURCES_WHAT, date=WRITTEN, free=True)
        return
    D = data(s)
    F = {r["sym"]: r for r in D["FUNDR"]}
    g = lambda sym, k: (F.get(sym) or {}).get(k)
    mm = D["mkt_med"]
    grp = D["grp"]
    worst_g, best_g = grp.index[0], grp.index[-1]
    W0, W1 = D["weather"][D0], D["weather"][LOW]
    gz = lambda M, k: next((x for x in M["gauges"] if x["key"] == k), {})
    cal = _calendar(D, h)
    tiles = "".join(f'<div class="so-stat"><b>{v}</b><span>{lab}</span></div>' for v, lab in [
        (pc(g("^GSPC", "peak_low")), "S&amp;P 500, Oct 6 record to the Nov 5 low"),
        (pc(g("^NDX", "peak_low")), "Nasdaq-100 over the same days"),
        (pc(g("SMH", "peak_low")), "Chip stocks (SMH)"),
        (pc(g("RSP", "peak_low")), "Equal-weight S&amp;P 500, where every company counts the same"),
        (pc(g("^GSPTSE", "peak_low")), "TSX"),
    ])
    body = f"""<div class="prose">
<p>For five weeks the stocks that led the market for two years went the wrong way, and in the last two the fall turned sharp. From its record close on October 6 to the November 5 low, the S&amp;P 500 fell {pc(abs(g("^GSPC", "peak_low") or 0), 1, False)}, the Nasdaq-100 {pc(abs(g("^NDX", "peak_low") or 0), 1, False)} and the chip stocks {pc(abs(g("SMH", "peak_low") or 0), 1, False)}. Yet the equal-weight S&amp;P 500, where a utility counts as much as Nvidia, {"rose" if (g("RSP", "peak_low") or 0) > 0 else "fell"} {pc(abs(g("RSP", "peak_low") or 0), 1, False)}, and the TSX ended about where it started. It was a sell-off in the market's leaders, the companies building and selling AI, more than a sell-off in the market.</p>
<div class="so-stats">{tiles}</div>
<h2 class="h2">Day by day</h2>
<p>The dated events, as the news reported them, with each day's close from Be The Puck's data underneath.</p>
{_timeline(D)}
<h2 class="h2">Where it hit</h2>
{_fund_table(D)}
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show Oct 6 to Nov 10</button>, the whole stretch from the record.</p>
<p>Among the {mm["us"]["n"] + mm["tsx"]["n"]} stocks Be The Puck covers, the median U.S. stock moved {pc(mm["us"]["low"])} from the October 28 close to the November 5 low and the median TSX stock {pc(mm["tsx"]["low"])}. By November 10, {share(mm["us"]["up"])} of the U.S. names and {share(mm["tsx"]["up"])} of the TSX names were higher than on October 28. The damage sat in a few groups: {e(worst_g.lower())} fell most, {e(best_g.lower())} did best.</p>
{_group_table(D, h)}
{_movers(D, h)}
<h2 class="h2">What the gauges did</h2>
<p>The <a href="{h('markets/')}">Markets page</a> watches nine gauges for the conditions that came before past crashes. Through these two weeks:</p>
<ul>
<li><b>Fear spiked, then eased.</b> The VIX went from {D["vix"][D0]:.1f} on October 28 to {D["vix"][LOW]:.1f} on November 5 and back to {D["vix"][END]:.1f} by November 10.</li>
<li><b>Credit stayed calm.</b> Lower-rated companies paid {gz(W0, "credit").get("value", float("nan")):.2f} points over Treasuries on October 28 and {gz(W1, "credit").get("value", float("nan")):.2f} on November 5: lenders didn't treat this as a crisis. In 2008 and 2020 that spread blew out.</li>
<li><b>The trend gauge turned.</b> {_trend_line(D)}</li>
<li><b>Long rates fell, then rose.</b> The 10-year Treasury yield slipped from {gz(W0, "rates").get("value", float("nan")):.2f}% to {gz(W1, "rates").get("value", float("nan")):.2f}% as money moved to bonds, then jumped back toward 5% on the inflation report.</li>
</ul>
<p>Market weather read <b>{e(W0["weather"])}</b> on October 28 and <b>{e(D["weather"][END]["weather"])}</b> on November 10. <a href="{h(SEEN_PATH)}">Did we see it coming?</a> goes through what each gauge said before the fall.</p>
<h2 class="h2">The explanations on offer</h2>
<p>Markets don't announce why they move. These are the reasons given at the time, with what cuts against each.</p>
<ul>
<li><b>AI spending running ahead of the cash it brings in.</b> Alphabet's free cash flow turned negative and Amazon's was negative over 12 months, while Meta reported its first cash outflow in a decade; investors marked down the spenders and, with them, the chipmakers they buy from. Against it: Microsoft beat, its cloud grew 48%, and the spending is someone else's revenue.</li>
<li><b>Rates.</b> U.S. inflation re-accelerated (0.6% in September, 0.4% in October), and futures now expect a Fed increase in December. Higher rates weigh most on stocks valued on profits far in the future. Against it: long yields fell through most of the sell-off, so rates can't explain the worst days.</li>
<li><b>Politics.</b> AP and some analysts tied part of the November 5 fall to the midterm results and the chance of pauses in data-centre construction; others read the same results as easing trade tensions, which helped Canadian stocks (Trading Economics). Against it: U.S. stocks rose the day after the election, and the chip stocks were falling a month before it.</li>
<li><b>Oil and the war.</b> Brent fell from above $112 to about $93 on hopes the Iran war is ending, and the energy fund fell {pc(abs(g("XLE", "d0_end") or 0), 0, False)} from October 28. It explains why energy fell, not why chips did.</li>
</ul>
<h2 class="h2">On the calendar</h2>
<p>Dates as they stand on Yahoo Finance's earnings calendar. The Fed's next decision is in December.</p>
<ul>{cal}</ul>
<p>None of this says where prices go next. For whether Be The Puck's gauges and calls were on the right side, and whether following them would have helped, read <a href="{h(SEEN_PATH)}">Did we see the sell-off coming?</a></p>
<p class="small muted">Covered stocks only (the {mm["us"]["n"]} U.S. and {mm["tsx"]["n"]} TSX stocks graded on the site; funds and names too thin to test left out). Moves are from closing prices adjusted for splits and dividends, to the {END.strftime("%B %-d")} close.</p>
</div>"""
    A.shell(WHAT_PATH, BUCKET_WHAT, WHAT_TITLE, WHAT_DEK, body, sources=SOURCES_WHAT, date=WRITTEN, free=True,
            related=A.related(depth, [SEEN_PATH, "articles/is-this-a-bubble/", "articles/what-has-an-edge/", "articles/calls-graded/"]))


# ----------------------------------------------------------------------------------------------- piece 2: did we see it coming
SOURCES_SEEN = [
    ("Daniel and Moskowitz, Momentum Crashes (NBER working paper 20439, 2014; Journal of Financial Economics, 2016)", "https://www.nber.org/papers/w20439"),
    ("AP via Boston.com: A brutal sell-off for AI stocks sends Wall Street reeling (Nov 5, 2026)", "https://www.boston.com/news/national-news/2026/11/05/a-brutal-sell-off-for-ai-stocks-sends-wall-street-reeling-and-the-sp-500-tumbles-4-4/"),
    ("TheStreet: Alphabet drops on earnings miss as cash flows turn negative (Oct 28, 2026)", "https://pro.thestreet.com/stock-market-today/alphabet-drops-on-earnings-miss-cash-flows-turn-negative"),
]


def _weather_table(D):
    from .markets import fmt_val, STATUS_WORD
    W = D["weather"]
    dates = (PEAK, D0, LOW, END)
    keys = [g["key"] for g in W[D0]["gauges"]]
    rows = ""
    for k in keys:
        cells = ""
        name = ""
        for d in dates:
            g = next((x for x in W[d]["gauges"] if x["key"] == k), None)
            if g is None:
                cells += "<td>–</td>"
                continue
            name = g["name"]
            cells += f'<td class="c"><span class="st-cell st-{g["status"]}">{fmt_val(g, g["value"])}</span><span class="g-status {g["status"]}">{STATUS_WORD[g["status"]]}</span></td>'
        rows += f"<tr><td>{e(name)}</td>{cells}</tr>"
    rows += '<tr class="em-row"><td><b>Market weather</b></td>' + "".join(f'<td class="c"><b>{e(W[d]["weather"])}</b></td>' for d in dates) + "</tr>"
    head = "<tr><th>Gauge</th>" + "".join(f'<th class="c">{day(d)}{" (record)" if d == PEAK else " (low)" if d == LOW else ""}</th>' for d in dates) + "</tr>"
    return f'<div class="tbl-wrap"><table class="tbl so-wx" data-nosort><thead>{head}</thead><tbody>{rows}</tbody></table></div>'


def _calls_table(D, lab="end"):
    G = D["G"]
    anchors = [(PEAK, "Oct 6 (the record)"), (MID3, "Oct 21"), (D0, "Oct 28"), (EVE, "Nov 4 (the eve)")]
    rows = ""
    for m, mlab in (("us", "U.S. stocks"), ("tsx", "TSX stocks")):
        rows += f'<tr class="so-sub"><td colspan="5"><b>{mlab}</b>, against {"the S&amp;P 500 (SPY)" if m == "us" else "the TSX 60 (XIU)"}</td></tr>'
        for d0, dl in anchors:
            g = G.get((d0, m, lab))
            if not g:
                continue
            b, hh, s = g[1], g[0], g[-1]
            gap = (b["med"] - s["med"]) if b["med"] is not None and s["med"] is not None else None
            cell = lambda x: (f'{pc(x["med"])}<span class="so-n">{x["n"]} · {share(x["beat"])} beat</span>' if x["n"] else "–")
            rows += (f'<tr><td>{dl}</td><td class="r {cls(b["med"])}">{cell(b)}</td><td class="r {cls(hh["med"])}">{cell(hh)}</td><td class="r {cls(s["med"])}">{cell(s)}</td>'
                     f'<td class="r {cls(gap)}"><b>{pts(gap)}</b></td></tr>')
    head = (f'<tr><th>Calls made at the close of</th><th class="r">Buys</th><th class="r">Holds</th><th class="r">Sells</th><th class="r">Buys − Sells</th></tr>')
    return (f'<div class="tbl-wrap"><table class="tbl so-calls" data-nosort><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
            f'<p class="small muted">Median move from that close to the {(END if lab == "end" else LOW).strftime("%B %-d")} close; under it, how many stocks had that call and the share that beat their market, dividends included on both sides. '
            'Buys − Sells is the gap between the two medians, in percentage points: positive means the calls were the right way round.</p>')


def _watch_table(D, h):
    rows = ""
    for w in D["W"]:
        t = w["t"]
        cells = "".join(f'<td class="c">{pill(c)}<span class="small muted"> {int(sc) if sc is not None and not (isinstance(sc, float) and math.isnan(sc)) else "–"}</span></td>' for c, sc in w["cells"])
        rows += (f'<tr><td><a href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a></td>{cells}'
                 f'<td class="r {cls(w["r_d0"])}">{pc(w["r_d0"], 0)}</td><td class="r adv-col {cls(w["r_peak"])}">{pc(w["r_peak"], 0)}</td></tr>')
    head = ("<tr><th>Stock</th>" + "".join(f'<th class="c">{lab}</th>' for lab in ("Oct 6", "Oct 21", "Oct 28", "Nov 4", "Nov 10"))
            + '<th class="r">Oct 28 to Nov 10</th><th class="r adv-col">Oct 6 to Nov 10</th></tr>')
    return (f'<div class="tbl-wrap"><table class="tbl so-watch" data-nosort><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
            '<p class="small muted">The standard signal\'s call at each close and its score out of 100 (Buy at 60 or more, Sell at 40 or less; a Buy holds until the score drops below 50, a Sell until it rises above it).</p>')


def _measure_table(D):
    rows = ""
    for lab, col, note, R in D["F"]:
        u, t = R["us"]["end"], R["tsx"]["end"]
        ul = R["us"]["low"]
        if not u:
            continue
        star = ' class="em-row"' if col in ("offhigh", "ey") else ""
        rows += (f'<tr{star}><td>{lab}<span class="small muted"> · {note}</span></td><td class="r {cls(u["top"])}">{pc(u["top"])}</td><td class="r {cls(u["bot"])}">{pc(u["bot"])}</td>'
                 f'<td class="r {cls(u["gap"])}"><b>{pts(u["gap"])}</b></td><td class="r adv-col {cls(ul["gap"] if ul else None)}">{pts(ul["gap"]) if ul else "–"}</td>'
                 f'<td class="r adv-col {cls(t["gap"] if t else None)}">{pts(t["gap"]) if t else "–"}</td></tr>')
    head = ('<tr><th>Ranked at the Oct 28 close on</th><th class="r">Best-ranked fifth</th><th class="r">Worst-ranked fifth</th><th class="r">Gap</th>'
            '<th class="r adv-col">Gap to the Nov 5 low</th><th class="r adv-col">Gap, TSX stocks</th></tr>')
    return (f'<div class="tbl-wrap"><table class="tbl so-meas" data-nosort><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
            '<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the gap to the low and on TSX stocks</button>. '
            'Median move of each fifth of U.S. stocks from the October 28 close to November 10; the gap is in percentage points.</p>')


def build_seen(A):
    s = A.s
    depth = SEEN_PATH.count("/")
    h = A.h(depth)
    srcs = SOURCES_SEEN
    if not ready(s):
        body = f'<div class="prose"><p>This piece needs prices to the {END.strftime("%B %-d, %Y")} close.</p></div>'
        A.shell(SEEN_PATH, BUCKET_SEEN, SEEN_TITLE, SEEN_DEK, body, sources=srcs, date=WRITTEN, free=True)
        return
    D = data(s)
    from .modelcompare import load as mc_load
    from .factors import GUARD
    G, B, mk, hit = D["G"], D["B"], D["mk"], D["hit"]
    gu, gt = G[(D0, "us", "end")], G[(D0, "tsx", "end")]
    pu = G[(PEAK, "us", "end")]
    lu = G[(D0, "us", "low")]
    W0 = D["weather"][D0]
    gz = lambda k: next((x for x in W0["gauges"] if x["key"] == k), {})
    cape = gz("cape").get("value")
    hu = hit["us"]
    gs = ((mc_load().get("models") or {}).get("guardsticky") or {})
    ga, gus, gtsx = gs.get("all") or {}, gs.get("us") or {}, gs.get("tsx") or {}
    bf, sf = (ga.get("buy") or {}).get("fell30"), (ga.get("sell") or {}).get("fell30")
    F = {col: R for _, col, _, R in D["F"]}
    fe = lambda col, m="us", lab="end": ((F.get(col) or {}).get(m) or {}).get(lab) or {}
    oh, tr, ey, rg, beta, mix = fe("offhigh"), fe("trend"), fe("ey"), fe("rg"), fe("neg_beta"), fe("mix")
    pe5, cg = D["pe5"], D["cg"] or {}
    gd = D["guard"]
    spg = gd.get("^GSPC", {})
    W = {w["sym"]: w for w in D["W"]}
    nv = W.get("NVDA")

    def right(g):
        b, s_ = g[1]["med"], g[-1]["med"]
        return None if b is None or s_ is None else b - s_
    gap_us, gap_tsx, gap_peak = right(gu), right(gt), right(pu)
    edge_word = ("Yes, in the U.S., once the fall had started" if (gap_us or 0) > 0.01 else "Not clearly")
    qa = f"""<div class="so-qa">
<div class="card"><p class="q">Did we call the timing?</p><p class="a">No.</p><p>Nothing on Be The Puck forecasts dates or the size of a fall, and nothing here said early November. The market guard, the one rule built for a falling market, never came on: the S&amp;P 500 got {pc(abs(spg.get("min", 0)), 1, False)} below its high, and the guard waits for {GUARD:.0%}.</p></div>
<div class="card"><p class="q">Did we flag the risk?</p><p class="a">Yes, the kind that broke.</p><p>On October 3, <a href="{h('articles/is-this-a-bubble/')}">Is this a bubble?</a> listed AI spending outrunning the giants' cash and an index leaning on a few names. On October 28 the gauges read <b>{e(W0["weather"])}</b>, with valuations higher than all but the dot-com months. The same pieces gave the case against, and said bubbles are hard to time.</p></div>
<div class="card"><p class="q">Would you have had an edge?</p><p class="a">{edge_word}.</p><p>On the calls made at the October 28 close, the median U.S. Buy moved {pc(gu[1]["med"])} to November 10 and the median U.S. Sell {pc(gu[-1]["med"])}. In Canada the Sells did {"better" if (gap_tsx or 0) < 0 else "worse"} ({pc(gt[-1]["med"])} against {pc(gt[1]["med"])}). And at the October 6 top, the signal was long the leaders: those U.S. Buys moved a median {pc(pu[1]["med"])} since.</p></div>
</div>"""
    pe_line = ""
    if pe5:
        top, bot, loss = pe5[0], pe5[4], pe5[5]
        pe_line = (f"<p><b>Cheap held up.</b> The value investor's question is whether good value, low P/E with solid growth, earns its keep. In this sell-off cheap did. Ranked by P/E on October 28 from SEC filings, "
                   f"the cheapest fifth of U.S. companies (a median P/E of {top['pe']:.0f}) moved {pc(top['end'])} to November 10 and the dearest fifth (a median P/E of {bot['pe']:.0f}) {pc(bot['end'])}; "
                   f"the {loss['n']} money-losers moved {pc(loss['end'])}. Growth was the other side of the same trade: the fastest-growing fifth by revenue moved {pc(rg.get('top'))}, the slowest {pc(rg.get('bot'))}. "
                   f"So the value-with-growth mix from <a href=\"{h('articles/what-has-an-edge/')}\">What has an edge</a>, low P/E plus revenue and earnings growth, landed on the AI leaders themselves{_mix_names(D)}, whose fast growth outweighed their P/Es in the ranking, and its top fifth moved {pc(mix.get('top'))}. "
                   f"Cheap stocks whose revenue was still growing faster than the median moved {pc(cg.get('end'))}.</p>")
    body = f"""<div class="prose">
<p>Two questions came in this week: did Be The Puck see the sell-off coming, and would following it have helped? Both have answers in the site's own data. Every call below is rebuilt from the prices and the plays' calls as they stood at that close, the way <a href="{h('articles/calls-graded/')}">the weekly scorecard</a> grades them, so none of it can be tidied up after the fact. What happened, day by day, is in <a href="{h(WHAT_PATH)}">The AI sell-off: what happened, and where it hit</a>.</p>
{qa}
<h2 class="h2">What we said before it started</h2>
<p>Be The Puck doesn't forecast. What it does is keep nine gauges for the conditions that came before past crashes, each read the same way every night. Here is how they read at the record, at the October 28 close just before Alphabet reported, at the low and on November 10, each rebuilt from the data published by that day:</p>
{_weather_table(D)}
{_gauge_story(D)}
<p>The written pieces said more about <i>what</i> could break. <a href="{h('articles/is-this-a-bubble/')}">Is this a bubble?</a> (October 3) put AI spending first among the reasons for concern: Amazon, Alphabet, Meta and Microsoft guiding to $735–750 billion of capital spending in 2026, with their combined free cash flow down 24% in a year, and the ten largest companies at 37.9% of the S&amp;P 500. <a href="{h('articles/what-has-an-edge/')}">What has an edge</a> (published the morning of October 28; Alphabet reported after that day's close) gave the strongest argument against the AI build-out as "spending is running ahead of the cash it earns". That evening Alphabet reported free cash flow of −$9.1 billion (TheStreet). Neither piece said when, and both gave the other side: the giants' core businesses are very profitable, and the suppliers' earnings show the demand is real.</p>
<h2 class="h2">What the signal said, and when</h2>
<p>The standard signal is a trend-following signal: it scores how many plays hold a stock, how close it is to its 1-year high and how strong its trend is against other stocks. That design decides how it behaves in a fall like this one. It owns the leaders at the top, and it gets out as they fall, not before. Both showed.</p>
{_watch_table(D, h)}
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the move since Oct 6</button>.</p>
<p><b>At the record it was long the leaders.</b> On October 6 the signal read Buy on most of the chip and AI names that fell hardest{f", Nvidia among them at {int(nv['cells'][0][1])}" if nv and nv['cells'][0][1] is not None else ""}. Calls in place that day did badly: the median U.S. Buy has moved {pc(pu[1]["med"])} since, the median U.S. Sell {pc(pu[-1]["med"])}.</p>
<p><b>It turned them as they fell.</b> As the chip stocks slid through October, their scores dropped with their prices and distance from the high. By the October 28 close, {hu["sells"]} of the {hu["n5"]} U.S. stocks that would fall most over the next six sessions were already Sells, against {share(hu["base"])} of U.S. stocks overall. Those {hu["n5"]} fell a median {pc(abs(hu["med_worst"] or 0), 1, False)} from October 28 to the November 5 low. By the November 4 close, the eve of the worst day, {hu["sells_eve"]} of them were. Not all: {_misses(D, h)}.</p>
{_calls_table(D)}
<p>Read across the rows and the pattern is plain. Calls made at the record were the wrong way round in the U.S. Calls made from October 21 on, once the fall had begun, were the right way round in the U.S.: from the October 28 close, the median Buy moved {pc(gu[1]["med"])} and the median Sell {pc(gu[-1]["med"])}, and {share(gu[1]["beat"])} of the Buys beat the S&amp;P 500 against {share(gu[-1]["beat"])} of the Sells. To the November 5 low the gap was wider still ({pts(right(lu))} points). On TSX stocks, which barely fell, the calls didn't separate, and the Sells did a little better.</p>
<h2 class="h2">Following along</h2>
<p>A reader who followed the calls as they changed, holding an equal amount of every Buy and resetting each evening, would have seen this (no costs, no taxes):</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Starting at the close of</th><th class="r">Buys</th><th class="r">Holds</th><th class="r">Sells</th><th class="r">The market</th></tr></thead><tbody>
{_basket_rows(B, mk)}
</tbody></table></div>
<p>{_basket_line(B, mk)}</p>
<h2 class="h2">What sorted the fallers from the rest</h2>
<p>Each U.S. stock ranked at the October 28 close on one measure at a time, then the best-ranked fifth set against the worst-ranked fifth. Highlighted: the measure that did the most work inside the signal, and the one value investors care about most.</p>
{_measure_table(D)}
<p><b>Off the high did the work.</b> The stocks nearest their 1-year highs on October 28 moved {pc(oh.get("top"))} to November 10; those 30% or more below their highs, many of them chipmakers already sliding, moved {pc(oh.get("bot"))}. That measure is 30 of the signal's 100 points, and it is what turned the chips to Sell before the worst days.</p>
<p><b>The trend measure pointed the wrong way.</b> The stocks furthest above their 200-day averages, the year's biggest winners, fell most: the top fifth moved {pc(tr.get("top"))} and the bottom fifth {pc(tr.get("bot"))}. Researchers call this a momentum crash: trend and momentum rules earn their keep over years but give back sharply when the leaders reverse all at once (Daniel and Moskowitz, 2016). The same showed in the stocks that swung hardest with the market (high beta, {pc(beta.get("bot"))} against {pc(beta.get("top"))} for the steadiest fifth) and in the year's biggest risers.</p>
{pe_line}
<p>On TSX stocks none of these measures separated much, because so little fell.</p>
<h2 class="h2">So, would you have had an edge?</h2>
<p><b>For U.S. stocks, over these two weeks, yes, from the moment the fall was under way.</b> The calls had turned against most of the stocks that fell hardest before their worst days, and the Buys held up better than the market. <b>Not at the top, and not in Canada.</b> Anyone who bought the signal's Buys at the October 6 record lost more than the market, and on TSX stocks the calls made no useful difference.</p>
<p>Two weeks is noise, and the right way to judge the signal is its long record, which points somewhere else. Since 2006 its Buys have beaten the market {_more(ga.get("edge12"))} than its Sells over the following year, and the split by market runs the other way from this fortnight: {pts(gtsx.get("edge12"))} points on TSX stocks, {pts(gus.get("edge12"))} on U.S. stocks, {'which is no edge at all' if (gus.get("edge12") or 0) <= 0 else 'a smaller one'} (<a href="{h('articles/old-vs-new-signal/')}">the 20-year record</a>). What has held in both markets is the exit: a Sell has been {f"{sf / bf:.1f}" if bf and sf else "about twice"} times as likely as a Buy to fall 30% or more within a year ({_ratio(gus)} on U.S. stocks, {_ratio(gtsx)} on TSX stocks). This episode fits that part of the record. The signal's value is in getting out of stocks that are already falling, and it pays for following trends by owning the leaders when they turn.</p>
<p>Nothing changes because of it. Faster exits were tested in October and rejected: over 20 years each one had a lower edge and more flip-flops, and one good fortnight isn't a reason to change rules tested on twenty years. The <a href="{h('articles/calls-graded/')}">weekly scorecard</a> keeps grading every day's calls in public, good weeks and bad.</p>
<p class="small muted">Standard weights (plays 40, off the high 30, trend 30) with the market guard and sticky calls of model version 3, in force since October 21. Calls for October 6, before today's weights took effect on October 13, are today's rules applied to that day's data. {D["hit"]["us"]["n"]} U.S. and {D["hit"]["tsx"]["n"]} TSX stocks; names too thin to test left out. Each stock graded against its market with dividends (SPY or XIU). P/E and revenue growth from SEC filings public on October 28, U.S. filers only. Prices adjusted for splits and dividends; no costs.</p>
</div>"""
    A.shell(SEEN_PATH, BUCKET_SEEN, SEEN_TITLE, SEEN_DEK, body, sources=srcs, date=WRITTEN, free=True,
            related=A.related(depth, [WHAT_PATH, "articles/calls-graded/", "articles/old-vs-new-signal/", "articles/what-has-an-edge/"]))


def _mix_names(D):
    S = D["stocks"]
    got = [S[x]["short"] for x in (D["cg"] or {}).get("mix_top", []) if x in WATCH]
    return f" ({', '.join(e(x) for x in got[:4])} among them)" if len(got) >= 2 else ""


def _trend_line(D):
    from .markets import STATUS_WORD
    g = lambda d: next((x for x in D["weather"][d]["gauges"] if x["key"] == "trend"), {})
    lo, d0, en = g(LOW), g(D0), g(END)
    ex = lo.get("extra") or {}
    plays = f", and {ex['k']} of {ex['n']} plays still held it" if ex.get("n") else ""
    return (f"At the low the S&amp;P 500 was {pc(lo.get('value'), 1, False)} {'above' if (lo.get('value') or 0) >= 0 else 'below'} its 200-day average{plays}. "
            f"The Trend gauge went from {STATUS_WORD.get(d0.get('status'), '–')} on October 28 to {STATUS_WORD.get(lo.get('status'), '–')} at the low, "
            f"and read {STATUS_WORD.get(en.get('status'), '–')} on November 10: the trend is the gauge that confirms a fall once it has started.")


def _gauge_story(D):
    """What the gauges read before the fall, at the record and at the low, from the statuses computed."""
    from .markets import STATUS_WORD
    W = D["weather"]

    def by(d, st):
        return [x for x in W[d]["gauges"] if x["status"] == st]

    def names(xs):
        n = [x["name"].split(" (")[0].lower() for x in xs]
        return ", ".join(n[:-1]) + " and " + n[-1] if len(n) > 1 else (n[0] if n else "none")
    num = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    w0, h0, c0 = by(D0, "warning"), by(D0, "watch"), by(D0, "calm")
    g0 = {x["key"]: x for x in W[D0]["gauges"]}
    detail = []
    if "cape" in g0 and g0["cape"]["status"] == "warning":
        detail.append(f"the Shiller CAPE was {g0['cape']['value']:.1f}, higher than {share((g0['cape'].get('extra') or {}).get('rank'))} of months since 1871")
    if "rates" in g0 and g0["rates"]["status"] == "warning":
        detail.append(f"the 10-year Treasury yield was {g0['rates']['value']:.2f}%, near its highest since 2007")
    tr = g0.get("trend") or {}
    ex = tr.get("extra") or {}
    trend_bit = (f" The trend gauge was already at Watch: the S&amp;P 500 was {pc(tr.get('value'), 0, False)} above its 200-day average, but only {ex['k']} of {ex['n']} plays held it."
                 if tr.get("status") == "watch" and ex.get("n") else "")
    wp = by(PEAK, "warning")
    low = W[LOW]["weather"]
    return (f"<p>On October 28, {num.get(len(w0), len(w0)).lower()} gauge{'s' if len(w0) != 1 else ''} read Warning ({names(w0)}): {'; '.join(detail)}. "
            f"{num.get(len(h0), len(h0))} read Watch ({names(h0)}) and {num.get(len(c0), len(c0)).lower()} read Calm, among them volatility and credit, the ones that usually move once a fall is under way.{trend_bit}</p>"
            f"<p>At the October 6 record the reading was the same, Unsettled, with {num.get(len(wp), len(wp)).lower()} Warnings ({names(wp)}). On the day of the low it turned <b>{e(low)}</b>, "
            f"as the trend and volatility gauges caught up with prices, and by November 10 it was back to {e(W[END]['weather'])}. "
            "That is how the gauges are built: valuation and rates describe how fragile a market is, sometimes for years; trend, volatility and credit confirm a fall once it has begun. Neither kind names the day.</p>")


def _ratio(r):
    b, s_ = (r.get("buy") or {}).get("fell30"), (r.get("sell") or {}).get("fell30")
    return f"{s_ / b:.1f} times" if b and s_ else "–"


def _more(v):
    if v is None:
        return "–"
    return f"{abs(v) * 100:.1f} points {'more' if v >= 0 else 'less'} often"


def _misses(D, h):
    """The worst-hit U.S. names that weren't Sells at the D0 close, and Sells that rose most."""
    S = D["stocks"]
    w = D["hit"]["us"]["worst"]
    miss = w[w.call != -1]
    from .factors import SIG_WORD
    parts = [f'<a href="{h("stocks/" + S[r.sym]["slug"] + "/")}">{e(S[r.sym]["short"])}</a> ({SIG_WORD.get(int(r.call)) if pd.notna(r.call) else "no call"}, {pc(r.low, 0)})' for _, r in miss.head(6).iterrows()]
    txt = (", ".join(parts[:-1]) + " and " + parts[-1]) if len(parts) > 1 else (parts[0] if parts else "")
    best = D["hit"]["us"]["best"]
    up = best[best.call == -1].sort_values("low", ascending=False).head(1)
    tail = ""
    if len(up):
        r = up.iloc[0]
        tail = f'; the other way, <a href="{h("stocks/" + S[r.sym]["slug"] + "/")}">{e(S[r.sym]["short"])}</a> was a Sell and rose {pc(r.end, 0, False)} by November 10'
    return (f"{txt} fell hard without being Sells" if txt else "every one of them was a Sell") + tail


def _basket_rows(B, mk):
    rows = ""
    for d0, lab in ((PEAK, "Oct 6 (the record)"), (D0, "Oct 28")):
        for m, mlab, blab in (("us", "U.S. stocks", "S&amp;P 500 (SPY)"), ("tsx", "TSX stocks", "TSX 60 (XIU)")):
            b = B.get((d0, m)) or {}
            rows += (f'<tr><td>{lab}, {mlab}</td><td class="r {cls(b.get(1))}">{pc(b.get(1))}</td><td class="r {cls(b.get(0))}">{pc(b.get(0))}</td>'
                     f'<td class="r {cls(b.get(-1))}">{pc(b.get(-1))}</td><td class="r {cls(mk.get((d0, m)))}">{pc(mk.get((d0, m)))} <span class="small muted">{blab}</span></td></tr>')
    return rows


def _basket_line(B, mk):
    u0, u6 = B.get((D0, "us")) or {}, B.get((PEAK, "us")) or {}
    t0 = B.get((D0, "tsx")) or {}
    m0, m6, mt = mk.get((D0, "us")), mk.get((PEAK, "us")), mk.get((D0, "tsx"))
    if not u0 or m0 is None:
        return ""
    a = (f"From October 28, following the U.S. Buys {'lost less than' if u0[1] > m0 and u0[1] < 0 else 'beat' if u0[1] > m0 else 'trailed'} the S&amp;P 500 "
         f"({pc(u0[1])} against {pc(m0)}), and the Sells did worst ({pc(u0[-1])}). ")
    b = (f"Even from the record, following along rather than holding the October 6 list left the U.S. Buys {pc(u6.get(1))}, "
         f"{'close to' if abs(u6.get(1, 0) - (m6 or 0)) < 0.01 else 'better than' if u6.get(1, 0) > (m6 or 0) else 'worse than'} the market's {pc(m6)}, because the falling names were switched to Sell along the way. ") if u6 and m6 is not None else ""
    c = (f"On TSX stocks the Buys moved {pc(t0.get(1))} against {pc(mt)} for the TSX 60." if t0 and mt is not None else "")
    return a + b + c


def build(A):
    build_what(A)
    build_seen(A)
