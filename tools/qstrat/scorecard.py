"""This week's calls, graded (articles/calls-graded/): how the standard signal's Buys, Holds and
Sells did over the latest week, and its running record since the standard weights changed on
October 13, 2026. Rebuilt nightly, free.

Each past day's calls are rebuilt from the data as it stood at that close (prices to that day and
the plays' calls to that day), the way factorgrade.py grades every factor, so the record can't be
tidied up after the fact and doesn't need anything stored. Only the standard weights are graded
(plays, off the high, trend); a reader's own weights may call things differently.
"""
import html

import numpy as np
import pandas as pd

from .content import TICKERS
from .factors import DEFAULT, BUY, SELL, MODEL, MODEL3_SINCE, SIG_WORD

e = html.escape
PATH = "articles/calls-graded/"
TITLE = "This week's calls, graded"
DEK = "How the signal's Buys, Holds and Sells did over the latest week, name by name, and its running record since the standard weights changed."
SINCE = pd.Timestamp("2026-10-13")       # the standard weights of October 13, 2026 (factors.MODEL 2)
WEEK = 5                                 # sessions


def daily_calls(site):
    """DataFrame of (sym, d, price, score, sig) for every covered stock and session since SINCE, point-in-time,
    with the rules in force on each day: the plain Buy and Sell lines before MODEL3_SINCE, the market guard
    and sticky calls from then on (callpath.py)."""
    from .callpath import daily_path
    from .factors import MODEL3_SINCE
    from .render import is_stock
    got = site.__dict__.get("_daily_calls")
    if got is not None:
        return got
    df = daily_path(site)                       # from the warm-up start, so the sticky state is settled by SINCE
    if len(df):
        df = df[df.d >= SINCE]
        stocks = {t["sym"] for t in TICKERS if is_stock(t) and not t.get("requested")}
        df = df[df.sym.isin(stocks)].copy()
        m3 = df.d >= pd.Timestamp(MODEL3_SINCE)
        df["sig"] = np.where(m3, df.call, df.call_plain)
        df.loc[np.where(m3, df.call.isna(), df.call_plain.isna()), "sig"] = np.nan
        df["score"] = np.where(m3, df.score, df.score_plain)
    site.__dict__["_daily_calls"] = df
    return df


def _pct(v, d=1, sign=True):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if sign and v > 0 else s)


def _bench_ret(site, sym, d0, d1):
    c = site.prices.get(sym, {}).get("close") if site.prices else None
    if c is None:
        return None
    a, b = c.loc[:d0], c.loc[:d1]
    return float(b.iloc[-1] / a.iloc[-1] - 1) if len(a) and len(b) and a.iloc[-1] > 0 else None


def piece(A):
    """Write the page through the articles shell (A: articles.Articles)."""
    site = A.s
    depth = PATH.count("/")
    h = A.h(depth)
    df = daily_calls(site)
    from .render import DISCLAIMER
    if not len(df) or df.d.nunique() < 2:
        body = f'<div class="prose"><p>The standard weights changed on {SINCE.strftime("%B %-d, %Y")}. The first graded week appears once there are five sessions of calls to grade.</p><p class="small muted">{DISCLAIMER}</p></div>'
        A.shell(PATH, "risk", TITLE, DEK, body, live=True, free=True, related=A.related(depth, ["articles/old-vs-new-signal/", "articles/why-your-signal-changed/"]))
        return
    days = sorted(df.d.unique())
    T = days[-1]
    last = pd.DataFrame({"sym": df[df.d == T].sym.values, "pT": df[df.d == T].p.values}).set_index("sym").pT
    # the latest week: calls at the close WEEK sessions ago, measured to T
    i0 = max(0, len(days) - 1 - WEEK)
    d0 = days[i0]
    wk = df[df.d == d0].copy()
    wk["r"] = wk.sym.map(last) / wk.p - 1
    wk = wk.dropna(subset=["r", "sig"])
    spy_r, tsx_r = _bench_ret(site, "SPY", d0, T), _bench_ret(site, "^GSPTSE", d0, T)
    wk["bench_r"] = wk.b.map(lambda b: _bench_ret(site, b, d0, T) if b else None)
    wk["ex"] = wk.r - wk.bench_r.astype(float)

    def grp(g):
        x = wk[wk.sig == g]
        if not len(x):
            return None
        return {"n": len(x), "med": x.r.median(), "mean": x.r.mean(), "up": (x.r > 0).mean(), "beat": (x.ex > 0).mean() if x.ex.notna().any() else None}
    G = {g: grp(g) for g in (1, 0, -1)}
    rows = "".join(f'<tr><td><span class="sig-pill {["sell", "hold", "buy"][g + 1]}">{SIG_WORD[g]}</span></td><td class="r">{G[g]["n"]}</td><td class="r">{_pct(G[g]["med"])}</td>'
                   f'<td class="r">{_pct(G[g]["mean"])}</td><td class="r">{_pct(G[g]["up"], 0, False)}</td><td class="r">{_pct(G[g]["beat"], 0, False) if G[g]["beat"] is not None else "–"}</td></tr>'
                   for g in (1, 0, -1) if G[g])
    edge = (G[1]["med"] - G[-1]["med"]) if G[1] and G[-1] else None
    verdict = ("" if edge is None else
               f"The Buys did better than the Sells by {_pct(abs(edge))}: the right way round." if edge > 0.002 else
               f"The Sells did better than the Buys by {_pct(abs(edge))}: the wrong way round this week." if edge < -0.002 else
               "Buys and Sells finished level this week.")

    def names(x, n=6):
        return ", ".join(f'<a href="{h("stocks/" + r.u + "/")}">{e(r.s)}</a> {_pct(r.r, 0)}' for _, r in x.head(n).iterrows())
    buys, sells = wk[wk.sig == 1].sort_values("r"), wk[wk.sig == -1].sort_values("r")
    hits = []
    if len(buys):
        hits.append(f"<li><b>Buys that rose most:</b> {names(buys.iloc[::-1])}.</li><li><b>Buys that fell most:</b> {names(buys)}.</li>")
    if len(sells):
        hits.append(f"<li><b>Sells that fell most:</b> {names(sells)}.</li><li><b>Sells that rose most:</b> {names(sells.iloc[::-1])}.</li>")
    # the running record: every day's calls over the following WEEK sessions
    rec_rows, run = "", []
    for i, d in enumerate(days):
        if i + WEEK >= len(days):
            break
        dT = days[i + WEEK]
        a = df[df.d == d].set_index("sym")
        b = df[df.d == dT].set_index("sym").p
        r = (b / a.p - 1).dropna()
        g = a.sig.reindex(r.index)
        bm = r[g == 1].median() if (g == 1).any() else np.nan
        sm = r[g == -1].median() if (g == -1).any() else np.nan
        run.append({"d": d, "nb": int((g == 1).sum()), "nh": int((g == 0).sum()), "ns": int((g == -1).sum()), "bm": bm, "sm": sm, "bu": (r[g == 1] > 0).mean() if (g == 1).any() else np.nan,
                    "su": (r[g == -1] > 0).mean() if (g == -1).any() else np.nan})
    R = pd.DataFrame(run)
    # daily baskets: equal-weight Buys, Holds, Sells and SPY, rebalanced each close
    bask = {1: [1.0], 0: [1.0], -1: [1.0]}
    spyb = [1.0]
    spy = site.prices["SPY"]["close"]
    for i in range(1, len(days)):
        a = df[df.d == days[i - 1]].set_index("sym")
        b = df[df.d == days[i]].set_index("sym").p
        r = (b / a.p - 1).dropna()
        g = a.sig.reindex(r.index)
        for k in bask:
            x = r[g == k]
            bask[k].append(bask[k][-1] * (1 + (x.mean() if len(x) else 0)))
        spyb.append(spyb[-1] * float(spy.loc[days[i]] / spy.loc[days[i - 1]]))
    end = {k: v[-1] - 1 for k, v in bask.items()}
    spy_end = spyb[-1] - 1
    if len(R):
        rr = "".join(f'<tr><td>{r.d.strftime("%b %-d")}</td><td class="r">{r.nb}</td><td class="r">{r.nh}</td><td class="r">{r.ns}</td><td class="r">{_pct(r.bm)}</td><td class="r">{_pct(r.sm)}</td>'
                     f'<td class="r {"up" if r.bm - r.sm > 0 else "down" if r.bm - r.sm < 0 else ""}">{_pct(r.bm - r.sm)}</td></tr>' for _, r in R.iterrows())
        agg = (f"Across every day's calls so far, the median Buy did {_pct(R.bm.median())} over the following week and the median Sell {_pct(R.sm.median())}; "
               f"the Buys beat the Sells on {int((R.bm > R.sm).sum())} of {len(R)} days.")
        run_tbl = (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Calls made at the close of</th><th class="r">Buys</th><th class="r">Holds</th><th class="r">Sells</th>'
                   f'<th class="r">Median Buy, next 5 sessions</th><th class="r">Median Sell</th><th class="r">Buys − Sells</th></tr></thead><tbody>{rr}</tbody></table></div>')
    else:
        agg, run_tbl = "The running record starts once a week of calls has a week of results behind it.", ""
    counts = df[df.d == T].sig.value_counts()
    body = f"""<div class="prose">
<p>Every evening the standard signal makes one call on each covered stock: Buy, Hold or Sell. This page grades those calls, the latest week first, so the question "did the signal work?" has a running answer. Each past day's calls are rebuilt from the data as it stood at that close, not from a stored list, so the record can't be tidied up afterwards.</p>
<h2 class="h2">The latest week: calls at the {d0.strftime("%B %-d")} close, measured at the {T.strftime("%B %-d")} close</h2>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Call</th><th class="r">Stocks</th><th class="r">Median move</th><th class="r">Average move</th><th class="r">Rose</th><th class="r">Beat their market</th></tr></thead><tbody>{rows}</tbody></table></div>
<p><b>{verdict}</b> Over the same sessions the S&amp;P 500 (SPY) moved {_pct(spy_r)} and the TSX {_pct(tsx_r)}. "Beat their market" compares each stock with the S&amp;P 500, or the TSX for Canadian names.</p>
<ul>{"".join(hits)}</ul>
<h2 class="h2">Since the standard weights changed ({SINCE.strftime("%B %-d, %Y")})</h2>
<p class="small muted">Each day is graded by the rules in force that day: the plain Buy and Sell lines until {pd.Timestamp(MODEL3_SINCE).strftime("%B %-d")}, and from then the market guard and sticky calls of model version {MODEL} (<a href="{h('articles/old-vs-new-signal/')}">why</a>).</p>
<p>{agg}</p>
{run_tbl}
<p>Put another way: $1 split equally across each day's Buys, reset every close, is worth {_pct(end[1])} more or less now than on {SINCE.strftime("%b %-d")}; the same for the Holds {_pct(end[0])}, for the Sells {_pct(end[-1])}, and for the S&amp;P 500 {_pct(spy_end)}. Tonight the signal reads Buy on {int(counts.get(1, 0))} names, Hold on {int(counts.get(0, 0))} and Sell on {int(counts.get(-1, 0))}.</p>
<h2 class="h2">What a week can and can't tell you</h2>
<p>A week is noise. The signal's tested edge, how much more often its Buys beat the market than its Sells, is a few points over a year (<a href="{h('articles/old-vs-new-signal/')}">the 20-year record, with the refinements tried</a>), and in any one week it can run the wrong way round. What the record does show over long stretches is which stocks fell hardest: since 2006 the signal's Sells were about twice as likely as its Buys to fall 30% or more within a year. This page is here so the recent record is visible, good weeks and bad.</p>
<p class="small muted">Standard weights only ({", ".join(f"{k} {w}" for k, w in DEFAULT.items())}; model version {MODEL}); your own weights may call a stock differently, and the plays you count change the plays factor. Prices adjusted for splits and dividends; no costs. {DISCLAIMER}</p>
</div>"""
    A.shell(PATH, "risk", TITLE, DEK, body, live=True, free=True,
            related=A.related(depth, ["articles/old-vs-new-signal/", "articles/why-your-signal-changed/", "articles/when-to-sell/"]))
