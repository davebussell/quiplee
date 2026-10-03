"""Crash Watch: the market-level gauges behind /markets/.

Each gauge is a reading with a long history, a plain status (calm / watch /
warning) and the evidence for why it matters. None of them times a crash on
its own; together they describe how stretched and how fragile the market is.
Sources for the thresholds and the history are cited on the page.
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MACRO = os.path.join(ROOT, "data", "macro")
PRICES = os.path.join(ROOT, "data", "prices")

# Peaks of past U.S. bear markets (S&P 500 closing highs; Yardeni tables) and the 2026 reading
PEAKS = [("Dot-com peak", "2000-03-24"), ("Pre-financial-crisis peak", "2007-10-09"), ("Pre-COVID peak", "2020-02-19"), ("Pre-2022 peak", "2022-01-03")]
RECESSIONS = []  # filled from USREC


def _csv(path, col=None):
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    s = d[col or d.columns[-1]] if col or len(d.columns) == 1 else d["close"]
    s = pd.to_numeric(s, errors="coerce").dropna()
    return s[~s.index.duplicated(keep="last")]


def px(sym):
    return _csv(os.path.join(PRICES, sym.replace("^", "_").replace(".", "-").lower() + ".csv"), "close")


def at(s, date):
    if s is None:
        return None
    s2 = s[s.index <= pd.Timestamp(date)]
    return float(s2.iloc[-1]) if len(s2) else None


def monthly(s, start="1990-01-01"):
    if s is None:
        return None
    s = s[s.index >= pd.Timestamp(start)]
    m = s.groupby(s.index.to_period("M")).last()
    m.index = m.index.to_timestamp(how="end").normalize()
    return m


def pct_rank(s, v):
    s = s.dropna()
    return float((s <= v).mean()) if len(s) and v is not None else None


def recession_spans():
    r = _csv(os.path.join(MACRO, "fred_usrec.csv"))
    if r is None:
        return []
    r = r[r.index >= "1985-01-01"]
    spans, start = [], None
    for d, v in r.items():
        if v >= 1 and start is None:
            start = d
        elif v < 1 and start is not None:
            spans.append((start, d))
            start = None
    if start is not None:
        spans.append((start, r.index[-1]))
    return spans


def sahm(unrate):
    m3 = unrate.rolling(3).mean()
    return (m3 - m3.shift(1).rolling(12).min()).dropna()


def two_year_return(close):
    c = close.copy()
    past = c.reindex(c.index - pd.DateOffset(years=2), method="ffill")
    past.index = c.index
    return (c / past - 1).dropna()


def gauge(key, name, question, value, fmt, status, reading, why, source, series=None, levels=(), peaks=None, unit="", lo=None, hi=None, extra=None):
    return {"key": key, "name": name, "question": question, "value": value, "fmt": fmt, "status": status, "reading": reading,
            "why": why, "source": source, "series": series, "levels": list(levels), "peaks": peaks or {}, "unit": unit,
            "min": lo, "max": hi, "extra": extra or {}}


def build(results=None, plays_in=None):
    """All gauges. plays_in: {sym: (k_in, n)} from the engine for index trend readings."""
    out = []
    spx, ndx, vix, tnx = px("^GSPC"), px("^NDX"), px("^VIX"), px("^TNX")
    rsp, spy, hyg, ief = px("RSP"), px("SPY"), px("HYG"), px("IEF")
    cape = _csv(os.path.join(MACRO, "cape.csv"))
    t10y3m = _csv(os.path.join(MACRO, "fred_t10y3m.csv"))
    baa = _csv(os.path.join(MACRO, "fred_baa10y.csv"))
    unrate = _csv(os.path.join(MACRO, "fred_unrate.csv"))
    asof = spx.index[-1] if spx is not None else pd.Timestamp.today()

    # 1. trend
    if spx is not None:
        s200 = spx.rolling(200).mean()
        dist = spx / s200 - 1
        k, n = (plays_in or {}).get("^GSPC", (None, None))
        kq, nq = (plays_in or {}).get("^NDX", (None, None))
        share = k / n if k is not None and n else None
        d_now = float(dist.iloc[-1])
        status = "warning" if d_now < 0 or (share is not None and share < 0.4) else ("watch" if d_now < 0.03 or (share is not None and share < 0.6) else "calm")
        reading = (f"The S&P 500 is {abs(d_now) * 100:.1f}% {'above' if d_now >= 0 else 'below'} its 200-day average"
                   + (f", and {k} of {n} plays hold it" if share is not None else "")
                   + (f" ({kq} of {nq} on the Nasdaq-100)." if kq is not None else "."))
        out.append(gauge("trend", "Trend", "Is the market's own trend still up?", d_now, "pct", status, reading,
                         "Every major bear market started with prices breaking below their long averages. Trend is a late signal, but it is the one that tells you the fall has actually begun.",
                         [("Meb Faber, A Quantitative Approach to Tactical Asset Allocation (2007)", "https://papers.ssrn.com/abstract=962461")],
                         monthly(dist), levels=[0], peaks={p: at(dist, d) for p, d in PEAKS}, extra={"share": share, "k": k, "n": n}))

    # 2. valuation
    if cape is not None:
        v = float(cape.iloc[-1])
        rank = pct_rank(cape, v)
        status = "warning" if v >= 35 else ("watch" if v >= 25 else "calm")
        out.append(gauge("cape", "Valuation (CAPE)", "How expensive are stocks against ten years of earnings?", v, "num", status,
                         f"The S&P 500's cyclically adjusted P/E is {v:.1f}, higher than {rank * 100:.0f}% of months since 1871. Only the 1999–2000 dot-com peak (44.2) was higher; the long-run average is about 17.",
                         "High valuations have been followed by low returns over the next ten years. They say little about next month: CAPE was 'high' through most of the late 1990s while prices doubled.",
                         [("Campbell & Shiller, Valuation Ratios and the Long-Run Stock Market Outlook (NBER, 2001)", "https://www.nber.org/papers/w8221"),
                          ("Shiller CAPE by month (multpl.com)", "https://www.multpl.com/shiller-pe/table/by-month")],
                         monthly(cape, "1900-01-01"), levels=[17.4, 30], peaks={p: at(cape, d) for p, d in PEAKS}, extra={"rank": rank}))

    # 3. run-up (Greenwood, Shleifer & You)
    if ndx is not None:
        r2 = two_year_return(ndx)
        v = float(r2.iloc[-1])
        status = "warning" if v >= 1.0 else ("watch" if v >= 0.5 else "calm")
        out.append(gauge("runup", "Run-up", "Has the market risen so far, so fast, that history says to be careful?", v, "pct", status,
                         f"The Nasdaq-100 is up {v * 100:.0f}% over two years. In Greenwood, Shleifer & You's study, U.S. industries up 100% or more in two years crashed by 40% or more within the next two years about half the time; at 50% the rate was about one in five.",
                         "Big run-ups don't predict low average returns, but they do raise the odds of a crash, especially when volatility is rising, new shares are flooding in and the rise is accelerating. Even then, prices kept rising for about six months on average before the peak.",
                         [("Greenwood, Shleifer & You, Bubbles for Fama (Journal of Financial Economics, 2019; NBER w23191)", "https://www.nber.org/papers/w23191")],
                         monthly(r2), levels=[0.5, 1.0], peaks={p: at(r2, d) for p, d in PEAKS}))

    # 4. concentration
    if rsp is not None and spy is not None:
        ratio = (rsp / spy.reindex(rsp.index, method="ffill")).dropna()
        past = ratio.reindex(ratio.index - pd.DateOffset(years=3), method="ffill")
        past.index = ratio.index
        rel3 = (ratio / past - 1).dropna()
        ch3 = float(rel3.iloc[-1])
        ch1 = float(ratio.iloc[-1] / at(ratio, asof - pd.DateOffset(years=1)) - 1)
        status = "warning" if ch3 < -0.15 else ("watch" if ch3 < -0.05 else "calm")
        out.append(gauge("concentration", "Concentration", "Is the rally carried by a few giants or by most stocks?", ch3, "pct", status,
                         f"Over three years the average S&P 500 stock (the equal-weight index) has {'lagged' if ch3 < 0 else 'beaten'} the cap-weighted index by {abs(ch3) * 100:.0f}%; over the last year it has {'lagged' if ch1 < 0 else 'beaten'} it by {abs(ch1) * 100:.0f}%. The top 10 stocks were 37.9% of the S&P 500 in June 2026, against about 27% at the 2000 peak.",
                         "A market leaning on a handful of companies is less diversified than it looks: if the leaders stumble, the index has little underneath it. Concentration is a fragility measure, not a tested crash signal.",
                         [("RBC Wealth Management, The great narrowing (Jan 2026)", "https://www.rbcwealthmanagement.com/en-us/insights/the-great-narrowing-sp-500-concentration"),
                          ("S&P 500 concentration (chartrow, June 2026 filing)", "https://chartrow.com/sp500/concentration")],
                         monthly(rel3, "2006-06-01"), levels=[0, -0.15], peaks={p: at(rel3, d) for p, d in PEAKS}, extra={"ch1": ch1}))

    # 5. volatility
    if vix is not None:
        v = float(vix.iloc[-1])
        yr = vix[vix.index > asof - pd.DateOffset(years=1)]
        calm_share = float((yr < 15).mean())
        status = "warning" if v >= 30 else ("watch" if v >= 22 or calm_share > 0.6 else "calm")
        out.append(gauge("vix", "Volatility (VIX)", "Is fear high now, or has calm lasted suspiciously long?", v, "num", status,
                         f"The VIX is {v:.1f}. Over the past year it spent {calm_share * 100:.0f}% of days below 15.",
                         "The VIX mostly spikes during a crash rather than before it (82.7 in March 2020, 80.9 in November 2008). The research warning is about long stretches of very low volatility, which tend to encourage borrowing and risk-taking.",
                         [("Danielsson, Valenzuela & Zer, Learning from History: Volatility and Financial Crises (Review of Financial Studies, 2018)", "https://www.riskresearch.org/papers/DanielssonValenzuelaZer2015/")],
                         monthly(vix), levels=[15, 30], peaks={p: at(vix, d) for p, d in PEAKS}, extra={"calm_share": calm_share}))

    # 6. yield curve
    if t10y3m is not None:
        v = float(t10y3m.iloc[-1])
        inv = t10y3m[t10y3m < 0]
        last_inv = inv.index[-1] if len(inv) else None
        months_since = (asof - last_inv).days / 30.4 if last_inv is not None else None
        status = "warning" if v < 0 else ("watch" if months_since is not None and months_since < 12 else "calm")
        out.append(gauge("curve", "Yield curve", "Do bond markets expect a recession?", v, "pp", status,
                         f"The 10-year Treasury yields {v:+.2f} percentage points over the 3-month bill." + (f" It was last inverted in {last_inv.strftime('%B %Y')}." if last_inv is not None else ""),
                         "An inverted curve (short rates above long rates) came before every U.S. recession since 1969, typically by 5 to 16 months. The 2022–24 inversion, the longest on record, has not been followed by a recession so far. It is a recession signal, not a crash timer.",
                         [("Estrella & Mishkin, The Yield Curve as a Predictor of U.S. Recessions (NY Fed, 1996)", "https://www.newyorkfed.org/research/current_issues/ci2-7.pdf"),
                          ("FRED: 10-Year minus 3-Month Treasury (T10Y3M)", "https://fred.stlouisfed.org/series/T10Y3M")],
                         monthly(t10y3m), levels=[0], peaks={p: at(t10y3m, d) for p, d in PEAKS}, unit="pp"))

    # 7. credit
    if baa is not None:
        v = float(baa.iloc[-1])
        ch3 = v - at(baa, asof - pd.DateOffset(months=3))
        rank = pct_rank(baa[baa.index >= "1990-01-01"], v)
        status = "warning" if v >= 3.0 or ch3 >= 0.75 else ("watch" if v >= 2.3 or ch3 >= 0.4 else "calm")
        out.append(gauge("credit", "Credit stress", "Are lenders demanding more to lend to companies?", v, "pp", status,
                         f"Baa-rated companies pay {v:.2f} percentage points over 10-year Treasuries ({ch3:+.2f} in three months), tighter than {100 - rank * 100:.0f}% of days since 1990.",
                         "Widening credit spreads have led declines in economic activity and stock prices (Gilchrist & Zakrajšek, 2012). But spreads are often tightest just before trouble, as in early 2007, so a calm reading is not an all-clear.",
                         [("Gilchrist & Zakrajšek, Credit Spreads and Business Cycle Fluctuations (American Economic Review, 2012)", "https://www.aeaweb.org/articles?id=10.1257/aer.102.4.1692"),
                          ("FRED: Moody's Baa minus 10-Year Treasury (BAA10Y)", "https://fred.stlouisfed.org/series/BAA10Y")],
                         monthly(baa), levels=[2.3, 3.0], peaks={p: at(baa, d) for p, d in PEAKS}, unit="pp"))

    # 8. jobs (Sahm rule)
    if unrate is not None:
        sr = sahm(unrate)
        v = float(sr.iloc[-1])
        status = "warning" if v >= 0.5 else ("watch" if v >= 0.3 else "calm")
        out.append(gauge("sahm", "Jobs (Sahm rule)", "Is unemployment rising fast enough to signal a recession?", v, "pp", status,
                         f"The Sahm rule reads {v:+.2f} (it triggers at +0.50). Unemployment was {float(unrate.iloc[-1]):.1f}% in {unrate.index[-1].strftime('%B %Y')}.",
                         "Claudia Sahm's rule (2019) has triggered early in every U.S. recession since 1960. It fired in August 2024 without a recession, when immigration was swelling the labour force.",
                         [("Congressional Research Service on the Sahm rule", "https://www.everycrsreport.com/reports/IN12410.html"),
                          ("FRED: Unemployment rate (UNRATE)", "https://fred.stlouisfed.org/series/UNRATE")],
                         monthly(sr), levels=[0.5], peaks={p: at(sr, d) for p, d in PEAKS}, unit="pp"))

    # 9. long rates
    if tnx is not None:
        v = float(tnx.iloc[-1])
        ch = v - at(tnx, asof - pd.DateOffset(years=1))
        hi_since = tnx[tnx >= v]
        prev = hi_since[hi_since.index < asof - pd.DateOffset(months=6)]
        status = "warning" if v >= 5 and ch >= 0.75 else ("watch" if v >= 4.5 or ch >= 0.75 else "calm")
        since = prev.index[-1].strftime("%Y") if len(prev) else None
        out.append(gauge("rates", "Long rates", "Are rising bond yields squeezing what stocks are worth?", v, "pctpt", status,
                         f"The 10-year Treasury yields {v:.2f}% ({ch:+.2f} points in a year)" + (f", the highest since {since}." if since else "."),
                         "Higher long-term rates make future profits worth less today and give investors a safer alternative to stocks. Rising rates have punctured many bubbles, from Japan in 1989–90 to the 2000 and 2022 tops.",
                         [("FRED: 10-Year Treasury yield", "https://fred.stlouisfed.org/series/DGS10")],
                         monthly(tnx), levels=[5.0], peaks={p: at(tnx, d) for p, d in PEAKS}, unit="%"))

    counts = {"warning": sum(g["status"] == "warning" for g in out), "watch": sum(g["status"] == "watch" for g in out), "calm": sum(g["status"] == "calm" for g in out)}
    score = counts["warning"] * 2 + counts["watch"]
    trend_bad = any(g["key"] == "trend" and g["status"] == "warning" for g in out)
    # the trend gauge is what confirms a fall has started, so "stormy" needs it (or almost everything) flashing
    weather = ("Stormy" if (trend_bad and score >= 7) or score >= 12 else "Unsettled" if score >= 5
               else "Mostly calm" if score >= 2 else "Calm")
    return {"asof": asof, "gauges": out, "counts": counts, "weather": weather, "recessions": recession_spans()}


# --------------------------------------------------------------------------
# Positioning data for the what-if simulator and the best-days table
# --------------------------------------------------------------------------
def positioning_data():
    """Monthly total-return series for stocks (SPY), long bonds (TLT), gold (GLD)
    and cash (T-bills), plus the 10-month rule's monthly call on SPY."""
    spy, tlt, gld, irx = px("SPY"), px("TLT"), px("GLD"), px("^IRX")
    m = pd.concat({"stocks": monthly(spy, "2004-01-01"), "bonds": monthly(tlt, "2004-01-01"), "gold": monthly(gld, "2004-01-01")}, axis=1)
    cash_y = monthly(irx, "2004-01-01").reindex(m.index, method="ffill") / 100.0
    rets = m.pct_change()
    rets["cash"] = cash_y.shift(1) / 12
    sma10 = m["stocks"].rolling(10).mean()
    rule = (m["stocks"] > sma10).astype(float).where(sma10.notna())
    rets = rets.iloc[1:]
    return {"dates": [d.strftime("%Y-%m") for d in rets.index],
            "stocks": [round(float(x), 5) if pd.notna(x) else None for x in rets["stocks"]],
            "bonds": [round(float(x), 5) if pd.notna(x) else None for x in rets["bonds"]],
            "gold": [round(float(x), 5) if pd.notna(x) else None for x in rets["gold"]],
            "cash": [round(float(x), 5) if pd.notna(x) else 0.0 for x in rets["cash"]],
            "rule": [None if pd.isna(x) else int(x) for x in rule.shift(1).iloc[1:]]}


def best_days():
    """Growth of 10,000 in SPY since 2005: all days vs missing the best/worst days."""
    spy = px("SPY")
    s = spy[spy.index >= "2005-01-01"]
    r = s.pct_change().dropna()
    base = float((1 + r).prod())
    out = [("Stayed invested every day", base)]
    for n in (10, 20, 30):
        out.append((f"Missed the {n} best days", float((1 + r.drop(r.nlargest(n).index)).prod())))
    out.append(("Missed the 10 worst days", float((1 + r.drop(r.nsmallest(10).index)).prod())))
    out.append(("Missed the 10 best and 10 worst", float((1 + r.drop(r.nlargest(10).index.union(r.nsmallest(10).index))).prod())))
    # how many of the best days came during bear markets (20%+ below a prior high)?
    dd = s / s.cummax() - 1
    best = r.nlargest(20)
    in_bear = int((dd.reindex(best.index) <= -0.2).sum())
    worst = r.nsmallest(20)
    gap = [abs((b - w).days) for b in best.index for w in worst.index]
    near = sum(1 for b in best.index if min(abs((b - w).days) for w in worst.index) <= 14)
    return {"rows": [(lab, 10000 * v) for lab, v in out], "start": s.index[0], "end": s.index[-1],
            "best20_in_bear": in_bear, "best20_near_worst": near, "years": (s.index[-1] - s.index[0]).days / 365.25}
