"""What has an edge, where value fits, and the big shifts (articles/what-has-an-edge/; Dave, Oct 28, 2026:
"I am very invested in the idea of good value stocks ... How do we factor these? What else could I use to get an
edge ... What macro trends am I missing ... How do we tie it all together?").

The tests in it are rebuilt nightly from the site's own data, point-in-time, the way factorgrade.py grades every
factor: each month-end since SEC numbers start (about 2010), every covered U.S. stock that files with the SEC is
ranked on value, growth, quality and price measures from filings and prices public at the time, and the best-ranked
fifth on each measure or mix is followed for a month against the average covered stock (which takes out the list's
own lean). Canadian companies don't file with the SEC and have no stored history of their numbers, so the value
tests are U.S. only. The research, macro and "where things are heading" sections are written and dated (WRITTEN).
"""
import html
import math

import numpy as np
import pandas as pd

e = html.escape
PATH = "articles/what-has-an-edge/"
TITLE = "What has an edge: value, growth, trend and the big shifts"
DEK = ("Most rules we test have a small edge or none. What has held up, where value investing fits and how to measure it, "
       "the long trends behind the market, and one way to tie them together.")
WRITTEN = pd.Timestamp("2026-10-28")
BUCKET = "strategies"
MIN_NAMES = 40          # a month counts once this many stocks have the measure
ERAS = (("2011–14", 2011, 2014), ("2015–20", 2015, 2020), ("2021 on", 2021, 2100))

# the measures and mixes tested: (label, [measures]); each measure is ranked within the month, a mix is the average rank
MIXES = [
    ("Low P/E (high earnings yield)", ["ey"]),
    ("Low P/E within its own sector", ["ey_grp"]),
    ("Value composite: earnings, cash flow, sales and book yields", ["ey", "fy", "sy", "by"]),
    ("Free-cash-flow yield", ["fy"]),
    ("Revenue growth", ["rg"]),
    ("Earnings growth", ["eg"]),
    ("Quality: return on equity, operating margin, low net debt", ["roe", "opm", "lev"]),
    ("Price trend (against its 200-day average)", ["trend"]),
    ("Momentum (12 months, skipping the latest)", ["mom121"]),
    ("Low P/E + revenue growth + earnings growth", ["ey", "rg", "eg"]),
    ("Low P/E + growth + quality", ["ey", "rg", "eg", "roe", "opm"]),
    ("Low P/E + growth + price trend", ["ey", "rg", "eg", "trend"]),
    ("Value + quality + momentum", ["ey", "fy", "sy", "roe", "opm", "mom121"]),
    ("Revenue growth + price trend", ["rg", "trend"]),
    ("Low volatility", ["lowvol"]),
]
KEY_MIX = "Low P/E + revenue growth + earnings growth"


def panel(site):
    """One row per covered U.S. SEC filer and month-end: value, growth, quality and price measures known then, and
    the next month's and next year's return against the stock's market (SPY, with dividends)."""
    got = site.__dict__.get("_edge_panel")
    if got is not None:
        return got
    from . import secfund
    from .engine import _read, PRICE_DIR
    from .factorgrade import _stocks, bench_of, START
    stocks = [t for t in _stocks(site) if secfund.has(t)]
    cal = site.prices["^GSPC"]["close"].index
    last = len(cal) - 1 - 21
    months = pd.Series(cal[:last + 1], index=cal[:last + 1]).groupby(cal[:last + 1].to_period("M")).last()
    dates = pd.DatetimeIndex([d for d in months.values if d >= START])
    try:
        fx = _read("CAD=X", PRICE_DIR)["close"]
    except Exception:
        fx = None
    rows = []
    for t in stocks:
        c = site.prices[t["sym"]]["close"]
        b = site.prices[bench_of(t)]["close"]
        cv, bv = c.values.astype(float), b.values.astype(float)
        ma = c.rolling(200).mean().values
        vol = (c.pct_change().rolling(252, min_periods=120).std() * np.sqrt(252)).values
        pos = c.index.searchsorted(dates, side="right") - 1
        bpos = b.index.searchsorted(dates, side="right") - 1
        for di, d in enumerate(dates):
            i, j = pos[di], bpos[di]
            if i < 252 or j < 0 or cv[i] <= 0 or bv[j] <= 0 or i + 21 >= len(cv) or j + 21 >= len(bv):
                continue
            s = secfund.snap(t, d)
            if not s:
                continue
            p0 = cv[i]
            fxd = float(fx.iloc[fx.index.searchsorted(d, side="right") - 1]) if fx is not None and len(fx) else None
            px = secfund._to_ccy(p0, t.get("cur", "$"), s["ccy"], fxd)
            sh = s.get("shares") or s.get("wsh")
            mcap = px * sh if px and sh else None
            if not mcap or mcap <= 0:
                continue
            ni, rev, eq = s.get("ni"), s.get("rev"), s.get("equity")
            ocf = s.get("ocf")
            r = {"d": d, "sym": t["sym"], "grp": t["group"],
                 "ey": ni / mcap if ni is not None else np.nan,
                 "fy": (ocf - (s.get("capex") or 0)) / mcap if ocf is not None else np.nan,
                 "sy": rev / mcap if rev else np.nan,
                 "by": eq / mcap if eq is not None else np.nan,
                 "rg": rev / s["p_rev"] - 1 if rev and s.get("p_rev") and s["p_rev"] > 0 else np.nan,
                 "eg": s["eps"] / s["p_eps"] - 1 if s.get("eps") is not None and s.get("p_eps") and s["p_eps"] > 0 else np.nan,
                 "roe": ni / eq if ni is not None and eq and eq > 0 else np.nan,
                 "opm": s["opi"] / rev if s.get("opi") is not None and rev and rev > 0 else np.nan,
                 "lev": -((s.get("debt") or 0) - (s.get("cash") or 0)) / mcap,
                 "trend": p0 / ma[i] - 1 if ma[i] > 0 else np.nan,
                 "mom121": cv[i - 21] / cv[i - 252] - 1 if cv[i - 252] > 0 else np.nan,
                 "lowvol": -vol[i] if not math.isnan(vol[i]) else np.nan,
                 "ex1": (cv[i + 21] / p0 - 1) - (bv[j + 21] / bv[j] - 1)}
            if i + 252 < len(cv) and j + 252 < len(bv):
                r["ex12"] = (cv[i + 252] / p0 - 1) - (bv[j + 252] / bv[j] - 1)
            rows.append(r)
    df = pd.DataFrame(rows)
    if len(df):
        df = df[df.groupby("d").sym.transform("count") >= MIN_NAMES].copy()
        # against the average covered stock that month: takes out the list's own lean (it is today's names)
        df["xs1"] = df.ex1 - df.groupby("d").ex1.transform("mean")
        if "ex12" in df:
            df["xs12"] = df.ex12 - df.groupby("d").ex12.transform("median")
        df["ey_grp"] = df.groupby(["d", "grp"]).ey.rank(pct=True)
        for c in ("ey", "fy", "sy", "by", "rg", "eg", "roe", "opm", "lev", "trend", "mom121", "lowvol"):
            df["r_" + c] = df.groupby("d")[c].rank(pct=True)
        df["r_ey_grp"] = df.ey_grp
    site.__dict__["_edge_panel"] = df
    return df


def _yearly(x):
    """Monthly average of a basket's return against the average stock, annualised, overall and by era."""
    m = x.groupby("d").xs1.mean()
    out = {"all": 12 * m.mean() if len(m) else None}
    for lab, a, b in ERAS:
        mm = m[(m.index.year >= a) & (m.index.year <= b)]
        out[lab] = 12 * mm.mean() if len(mm) else None
    yrs = m.groupby(m.index.year).mean()
    out["up"], out["n"] = int((yrs > 0).sum()), len(yrs)
    x12 = x["xs12"].dropna() if "xs12" in x else pd.Series(dtype=float)
    out["beat12"] = float((x12 > 0).mean()) if len(x12) else None
    out["months"] = len(m)
    out["names"] = float(x.groupby("d").sym.count().median()) if len(x) else 0
    return out


def mixes(site):
    """{label: {"top": _yearly of the best-ranked fifth, "bottom": of the worst-ranked fifth}} for every MIX."""
    df = panel(site)
    if not len(df):
        return {}
    out = {}
    for lab, cols in MIXES:
        rc = df[["r_" + c for c in cols]]
        need = len(cols) // 2 + len(cols) % 2
        s = rc.mean(axis=1, skipna=True).where(rc.notna().sum(axis=1) >= need)
        x = df.assign(s=s).dropna(subset=["s"])
        x = x[x.groupby("d").s.transform("count") >= MIN_NAMES]
        if not len(x):
            continue
        q = np.floor(x.groupby("d").s.rank(pct=True, method="first") * 5 - 1e-9)
        out[lab] = {"top": _yearly(x[q == 4]), "bottom": _yearly(x[q == 0])}
    return out


def splits(site):
    """The value-trap and growth-at-a-reasonable-price cuts: [(label, _yearly)]."""
    df = panel(site)
    if not len(df):
        return []
    cheap = df.r_ey >= 0.6
    fast = df.r_rg >= 0.6
    cuts = [("Cheap: the 40% with the highest earnings yield", cheap),
            ("Cheap, and revenue growing faster than the median", cheap & (df.r_rg >= 0.5)),
            ("Cheap, and earnings falling or a loss", cheap & ((df.eg < 0) | (df.ey < 0))),
            ("Cheap, and above its 200-day average", cheap & (df.trend > 0)),
            ("Cheap, and below its 200-day average", cheap & (df.trend <= 0)),
            ("Fast revenue growth: the top 40%", fast),
            ("Fast growth, the cheaper half by P/E", fast & (df.r_ey >= 0.5)),
            ("Fast growth, the dearer half by P/E", fast & (df.r_ey < 0.5)),
            ("Losing money", df.ey < 0)]
    return [(lab, _yearly(df[m])) for lab, m in cuts]


def spread(site):
    """The earnings yield of the cheapest and dearest fifth and the median, at the latest month and its average."""
    df = panel(site)
    if not len(df):
        return None
    g = df.dropna(subset=["ey"]).groupby("d").ey
    hi, lo, med = g.quantile(0.8), g.quantile(0.2), g.median()
    gap = hi - lo
    return {"d": gap.index[-1], "hi": float(hi.iloc[-1]), "lo": float(lo.iloc[-1]), "med": float(med.iloc[-1]),
            "gap": float(gap.iloc[-1]), "gap_avg": float(gap.mean()), "med_avg": float(med.mean()),
            "since": gap.index[0], "names": int(g.count().iloc[-1])}


def pts(v, d=1):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "–"
    s = f"{abs(v) * 100:.{d}f}"
    return ("−" if v < 0 and float(s) else "+" if v > 0 and float(s) else "") + s


def vs(v):
    """'beat' or 'trailed', for a number against the average stock."""
    return "beat" if (v or 0) >= 0 else "trailed"


def num(v):
    return "–" if v is None else f"{abs(v) * 100:.1f}"


def pctx(v):
    return "–" if v is None else f"{round(100 * v)}%"


def _cls(v, band=0.01):
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else ("up" if v >= band else "down" if v <= -band else "")


def mix_table(site):
    M = mixes(site)
    if not M:
        return ""
    rows = ""
    for lab, _ in MIXES:
        if lab not in M:
            continue
        t, b = M[lab]["top"], M[lab]["bottom"]
        star = ' class="em-row"' if lab == KEY_MIX else ""
        rows += (f'<tr{star}><td>{e(lab)}</td><td class="r {_cls(t["all"])}" data-v="{t["all"]}"><b>{pts(t["all"])}</b></td>'
                 + "".join(f'<td class="r adv-col {_cls(t[l])}" data-v="{t[l] if t[l] is not None else ""}">{pts(t[l])}</td>' for l, _, _ in ERAS)
                 + f'<td class="r">{t["up"]} of {t["n"]}</td><td class="r {_cls(b["all"])}" data-v="{b["all"]}">{pts(b["all"])}</td></tr>')
    head = ('<tr><th>Ranked on</th><th class="r" data-sort-first="desc">Top fifth, a year</th>'
            + "".join(f'<th class="r adv-col" data-sort-first="desc">{l}</th>' for l, _, _ in ERAS)
            + '<th class="r">Years ahead</th><th class="r" data-sort-first="desc">Bottom fifth</th></tr>')
    return (f'<div class="tbl-wrap"><table class="tbl"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
            '<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the three stretches</button>: 2011–14, 2015–20 and 2021 on.</p>')


def split_table(site):
    S = splits(site)
    if not S:
        return ""
    rows = "".join(f'<tr><td>{e(lab)}</td><td class="r {_cls(y["all"])}" data-v="{y["all"]}"><b>{pts(y["all"])}</b></td>'
                   + "".join(f'<td class="r adv-col {_cls(y[l])}" data-v="{y[l] if y[l] is not None else ""}">{pts(y[l])}</td>' for l, _, _ in ERAS)
                   + f'<td class="r">{y["names"]:.0f}</td></tr>' for lab, y in S)
    head = ('<tr><th>Stocks that were</th><th class="r" data-sort-first="desc">Against the average stock, a year</th>'
            + "".join(f'<th class="r adv-col" data-sort-first="desc">{l}</th>' for l, _, _ in ERAS) + '<th class="r">Names a month</th></tr>')
    return f'<div class="tbl-wrap"><table class="tbl"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'


# ----------------------------------------------------------------------------------------------- the page
def _so_far(site, h):
    """What the site's own tests say so far, from the model study and the factor grades (both rebuilt from the data)."""
    from .modelcompare import load as mc_load
    from .factorgrade import cached
    J = mc_load()
    M = J.get("models") or {}
    gs = M.get("guardsticky") or {}
    a, us, tsx = gs.get("all") or {}, gs.get("us") or {}, gs.get("tsx") or {}
    g = cached(site)
    gf = g.get("factors") or {}
    fe = lambda k: ((gf.get(k) or {}).get("12m") or {}).get("edge")
    if not a or fe("pe") is None:
        return ""
    bf, sf = (a.get("buy") or {}).get("fell30"), (a.get("sell") or {}).get("fell30")
    value_edges = [v for v in (fe("pe"), fe("pb"), fe("dy")) if v is not None]
    return f"""<h2 class="h2">What our own tests say so far</h2>
<p>Be The Puck grades every rule it shows the same way: month by month, from the numbers public at the time, against the stock's market with dividends included (<a href="{h('articles/old-vs-new-signal/')}#measuring-stick">the fairer measuring stick</a>, October 27). Three results matter for what follows.</p>
<ul>
<li><b>The standard signal's edge is small, and it comes from Canada.</b> Since {J['since'][:4]} its Buys have beaten the market {num(a.get('edge12'))} points {"more" if (a.get('edge12') or 0) >= 0 else "less"} often than its Sells over the next year: {pts(us.get('edge12'))} on U.S. stocks and {pts(tsx.get('edge12'))} on TSX stocks, most of that in 2011–2018.</li>
<li><b>Where it does earn its keep is getting out.</b> A stock it called Sell was {sf / bf:.1f} times as likely as a Buy to fall 30% or more within a year ({pctx(sf)} against {pctx(bf)}).</li>
<li><b>Cheap didn't beat dear.</b> Ranked by P/E, price to book or dividend yield, the cheaper stocks did worse than the dearer ones (edges of {pts(min(value_edges))} to {pts(max(value_edges))} points). Revenue growth had the best record of any company number ({pts(fe('rg'))}), and the price measures, trend and momentum, came next ({pts(fe('trend'))} and {pts(fe('mom'))}).</li>
</ul>
<p>That last result runs against one of the best-documented ideas in investing, so it's worth testing harder.</p>"""


def _value_tests(site, h):
    M = mixes(site)
    sp = spread(site)
    df = panel(site)
    if not M or not len(df):
        return ""
    k = M.get(KEY_MIX, {}).get("top") or {}
    ey = M.get("Low P/E (high earnings yield)", {})
    tr = M.get("Price trend (against its 200-day average)", {}).get("top") or {}
    rg = M.get("Revenue growth", {}).get("top") or {}
    S = dict(splits(site))
    loss = S.get("Losing money") or {}
    garp_c, garp_d = S.get("Fast growth, the cheaper half by P/E") or {}, S.get("Fast growth, the dearer half by P/E") or {}
    first, last_ = df.d.min(), df.d.max()
    n = int(df.groupby("d").sym.count().median())
    weights = "pe35.rg35.eg30"
    sp_line = ""
    if sp:
        sp_line = (f"<p><b>How far apart cheap and dear are now.</b> On the {sp['d'].strftime('%B %Y')} month-end, the cheapest fifth of these stocks earned {pctx(sp['hi'])} of their price a year "
                   f"(a P/E near {1 / sp['hi']:.0f}) and the dearest fifth {pctx(sp['lo'])}; the middle stock {pctx(sp['med'])}, a P/E near {1 / sp['med']:.0f}. "
                   f"That gap, {num(sp['gap'])} points, is {'narrower' if sp['gap'] < sp['gap_avg'] else 'wider'} than its average since {sp['since'].year} ({num(sp['gap_avg'])}). "
                   "A wide gap is what value investors look for, because there's more room for cheap stocks to catch up; a narrow one means less of that cushion.</p>")
    return f"""<h2 class="h2">Value, tested on the stocks we cover</h2>
<p>Every month-end from {first.strftime('%B %Y')} to {last_.strftime('%B %Y')}, each covered U.S. company that files with the SEC (about {n} a month) was ranked on value, growth, quality and price measures, using only filings and prices public that day. The best-ranked fifth on each measure, or on an equal mix of measures, was then followed for a month against <b>the average covered stock</b>, not the index, so that the list's own lean toward today's winners doesn't flatter every row. Positive means that fifth beat the average stock, in points a year. Rebuilt nightly with the {site.asof.strftime('%b %-d, %Y')} close.</p>
{mix_table(site)}
<p><b>What it shows.</b> The cheapest fifth by P/E {vs(ey['top']['all'])} the average covered stock by {num(ey['top']['all'])} points a year, and the dearest fifth {vs(ey['bottom']['all'])} it by {num(ey['bottom']['all'])}. Adding revenue and earnings growth to low P/E, the mix closest to "good value with solid growth", {'narrowed the gap' if k.get('all') is not None and k['all'] > ey['top']['all'] else 'did no better'} ({pts(k.get('all'))} a year), and {'has been ahead since 2021' if (k.get('2021 on') or 0) > 0 else 'has still trailed since 2021'} ({pts(k.get('2021 on'))}). The steadiest measure was the price trend: the fifth furthest above its 200-day average {vs(tr.get('all'))} the average stock by {num(tr.get('all'))} points a year, ahead in {tr.get('up')} of {tr.get('n')} years. Revenue growth on its own: {pts(rg.get('all'))}.</p>
<p>Two cuts help with the value-trap question, cheap for a reason or cheap by mistake:</p>
{split_table(site)}
<p>Among cheap stocks, the ones whose revenue was still growing did better than cheap stocks overall, and since 2021 they've been ahead of the average stock. A rising price didn't rescue cheap stocks in this list. Among fast growers, the dearer half did better than the cheaper half overall ({pts(garp_d.get('all'))} against {pts(garp_c.get('all'))}), though since 2021 the cheaper half has done about as well ({pts(garp_c.get('2021 on'))} against {pts(garp_d.get('2021 on'))}).</p>
{sp_line}
<p><b>Why not to read too much into it.</b> Look at the last row: companies <i>losing money</i> {vs(loss.get('all'))} the average covered stock by {num(loss.get('all'))} points a year. {"That isn't a strategy; it's hindsight." if (loss.get('all') or 0) > 0 else "Even so, the list carries hindsight."} The list is today's names, so the money-losers in it are the ones that made it (a few became the market's biggest companies), while the ones that failed or were bought cheaply aren't here to count against them. The same lean hurts value: a company cheap in 2012 that stayed cheap shrank and was never added; one that was dear and kept growing is now a large cap we cover. A fair value test needs the companies that dropped out, and filings from before 2011, which is why <a href="{h('articles/old-vs-new-signal/')}#by-market">testing on a list that includes delisted stocks</a> is next on our list. Until then, these numbers describe one unusual stretch in U.S. large caps, value's worst on record, not a verdict on value.</p>
<p>To see how every covered stock scores on low P/E, revenue growth and earnings growth together, <a href="{h('stocks/')}?w={weights}">open the stock list with that mix</a> (P/E 35, revenue growth 35, earnings growth 30). The weights panel on any page changes it, or puts back the standard weights.</p>"""


def _macro(h):
    return MACRO_HTML


def _together(site, h):
    return TOGETHER_HTML.format(stocks=h("stocks/"), method=h("method/"), one=h("articles/one-stock-too-many/"), markets=h("markets/"),
                                storm=h("articles/debt-and-crashes/"), alerts=h("alerts/"), graded=h("articles/calls-graded/"),
                                guide=h("guides/your-plays/") + "#your-signal", sell=h("articles/when-to-sell/"), earnings=h("earnings/"),
                                bubble=h("articles/is-this-a-bubble/"))


def build(A):
    s = A.s
    depth = PATH.count("/")
    h = A.h(depth)
    body = (f'<div class="prose">{_so_far(s, h)}{_value_tests(s, h)}{RESEARCH_HTML}{EDGES_HTML.replace("{earnings}", h("earnings/"))}</div>'
            f'{_macro(h)}<div class="prose">{_together(s, h)}</div>')
    A.shell(PATH, BUCKET, TITLE, DEK, body, sources=SOURCES, date=WRITTEN, free=True,
            related=A.related(depth, ["articles/old-vs-new-signal/", "articles/when-to-sell/", "articles/one-stock-too-many/", "articles/is-this-a-bubble/"]))


RESEARCH_HTML = """<h2 class="h2" id="research">What the wider research says about value</h2>
<p><b>Over the long run, cheap has beaten dear, but not evenly and not lately.</b> In the U.S. data most research uses (the Ken French Data Library, back to 1926), a portfolio holding the cheapest stocks by book value and shorting the dearest earned about 4% a year over the full century. Then came the worst stretch in its history: from 2007 to 2020 it lost more than half its value, a 55% drawdown by mid-2020 in the count of Arnott, Harvey, Kalesnik and Linnainmaa. Value came back strongly in 2021 and 2022, gave some of it back in 2023 and 2024, and has led again in 2026 so far. Our test window, 2011 on, sits mostly inside that slump.</p>
<p><b>Why it slumped: prices more than businesses.</b> Cheap stocks got cheaper relative to dear ones. Arnott and co-authors found the widening valuation gap accounts for the whole drawdown. AQR's Cliff Asness found the gap in 2020 was the widest on record, even leaving out technology and the largest companies, and that the cheap companies' profits and debt were near normal. Accounting played a part: book value leaves out research spending and brands, and value measures that add them back did better (Eisfeldt, Kim and Papanikolaou, 2022). Interest rates explain less than is often said (Maloney and Moskowitz, 2021).</p>
<p><b>Large companies are where value has been weakest.</b> The value premium shrinks with company size in every region studied (Fama and French, 2012; Israel and Moskowitz, 2013), and the stocks Be The Puck covers are large companies. In Canada, low-P/E stocks returned 11.7% a year from 1985 to 2005 against 5.4% for high-P/E stocks, with the gap halving in the second decade (Athanassakos, 2009). A 2024 study of the TSX found value's premium explained away by profitability and investment once those were counted (Assoe, Attig and Sy).</p>
<h3 class="h3">Measuring value better</h3>
<ul>
<li><b>Earnings and cash flow beat book value, and enterprise value beats market value.</b> Over 1971–2010, the cheapest fifth of U.S. stocks by operating earnings against enterprise value (market value plus debt, less cash) returned 17.7% a year against 8.0% for the dearest fifth; forward-earnings estimates did worst of the measures tested (Gray and Vogel, 2012). Dividend yield has been the weakest of the common measures in the long-run U.S. data.</li>
<li><b>Use today's price.</b> Standard academic value uses prices up to 18 months old; current prices did better (Asness and Frazzini, 2013).</li>
<li><b>Blend measures and compare within industries.</b> A bank and a software company are never on the same P/E. Professional value measures blend several yields and rank each company against its own industry (Asness, Porter and Stevens). In our table, low P/E within its own sector lost less than plain low P/E.</li>
</ul>
<h3 class="h3">Value works best alongside quality and momentum</h3>
<ul>
<li><b>Profitability.</b> Profitable companies earn more despite looking expensive, and controlling for profitability improves value, especially among the largest stocks (Novy-Marx, 2013). Once profitability and investment are in the model, plain value adds little (Fama and French, 2015). "Quality" (profitable, growing and safe) has earned returns in the U.S. and across 24 countries (Asness, Frazzini and Pedersen, 2019).</li>
<li><b>Financial health among cheap stocks.</b> Piotroski's nine-point F-score (profits, cash flow, debt, margins, share issuance) separated cheap winners from cheap losers by 23% a year in 1976–1996, mostly in small, little-followed companies. A test outside the U.S. over 2000–2018 found about 10% a year, and a U.S. version built to be tradable kept about two-thirds of the paper return.</li>
<li><b>Momentum.</b> Value and momentum tend to work at different times, so a blend of the two has been steadier than either (Asness, Moskowitz and Pedersen, 2013). Value works best among stocks that have been falling, momentum among expensive ones (Asness, 1997), which is why researchers blend the two into one score rather than screening cheap stocks for rising prices. In the U.S. since 2007, even the blend struggled.</li>
</ul>
<h3 class="h3">"Solid growth" is the hard part to measure</h3>
<p>Growth that has happened is evidence; growth that is forecast mostly isn't. The stocks with the most optimistic long-term growth forecasts have earned less than those with the most pessimistic ones (Bordalo, Gennaioli, La Porta and Shleifer, 2019, confirming La Porta's 1996 finding); long-term growth persists about as often as chance would predict (Chan, Karceski and Lakonishok, 2003); and rules built on the PEG ratio have had the weakest link to later returns of the valuation methods analysts use (Bradshaw, 2004). Companies growing their assets fastest have tended to do worse, not better. That fits our table: realised revenue growth had the best record, earnings growth was mixed, and the site's PEG and forward P/E, which rest on forecasts, can't be graded at all.</p>"""
EDGES_HTML = """<h2 class="h2" id="edges">Other edges, and how much they fade</h2>
<p>A warning first. Published edges shrink. Across 97 published predictors, returns were 26% lower after the study period ended and 58% lower after publication (McLean and Pontiff, 2016), and most of the 452 anomalies one team re-tested failed once the tiniest stocks were handled properly (Hou, Xue and Zhang, 2020). Another team found most factors do replicate, including in 93 countries (Jensen, Kelly and Pedersen, 2023). Either way, a backtest is a ceiling, not a forecast.</p>
<ul>
<li><b>Momentum and price trend</b> have held up out of sample since the 1990s (Jegadeesh and Titman, 2001), and in Canada as well as the U.S. They also crash, mostly in sharp rebounds after a fall: the U.S. momentum factor lost 83% in 2009 (Daniel and Moskowitz, 2016). In our tests trend was the steadiest measure, and the exit side of the signal is where it earns its keep.</li>
<li><b>Buybacks and share issuance.</b> Companies that bought back shares beat the market by 12% over the next four years (45% for cheap companies) in 1980–1990 (Ikenberry, Lakonishok and Vermaelen, 1995), and companies issuing lots of new shares have done poorly in 41 countries (McLean, Pontiff and Watanabe, 2009). Shrinking share counts are one of the most persistent results there is.</li>
<li><b>Insider buying.</b> Executives' unusual purchases of their own stock earned 0.8% a month more than the market; routine ones earned nothing (Cohen, Malloy and Pomorski, 2012).</li>
<li><b>Earnings surprises.</b> Stocks used to keep drifting in the direction of an earnings surprise for weeks after the report. In large companies that drift has been gone since about 2006 (Martineau, 2022), which is why our <a href="{earnings}">earnings pages</a> explain moves rather than predict them.</li>
<li><b>Analysts' estimate changes</b> have predicted returns beyond price momentum (Chan, Jegadeesh and Lakonishok, 1996); the site keeps collecting rating and target changes so this can be graded.</li>
<li><b>Low volatility</b> is documented, but much of it sits in tiny stocks (Novy-Marx and Velikov, 2022). In our list the calmest stocks lagged badly.</li>
<li><b>Accounting accruals</b>, once a famous edge, have faded to nothing reliable (Green, Hand and Soliman, 2011).</li>
</ul>
<h3 class="h3">The edges that are certain</h3>
<ul>
<li><b>Costs.</b> Searching for better returns cost U.S. investors about 0.67% of the market's value a year (French, 2008). Over the 10 years to 2025, 98.8% of Canadian equity funds trailed the S&amp;P/TSX Composite (SPIVA Canada).</li>
<li><b>Trading less.</b> Among 66,465 U.S. households in 1991–1996, the most active traders earned 11.4% a year against the market's 17.9% (Barber and Odean, 2000).</li>
<li><b>Behaviour.</b> The average dollar in U.S. funds earned 8.7% a year over the 10 years to December 2025, against 9.9% for the funds themselves, because money moved in and out at the wrong times; the gap was widest in the most volatile funds (Morningstar, Mind the Gap 2026).</li>
<li><b>Taxes.</b> Selling losers to offset gains added about 1% a year in a U.S. study of the 500 largest stocks (Chaudhuri, Burnham and Lo, 2020). In Canada, a loss doesn't count if the same shares are bought back within 30 days (the CRA's superficial loss rule).</li>
<li><b>Diversification.</b> Most U.S. stocks since 1926 earned less than Treasury bills over their lifetimes; 4% of companies account for all the net wealth the market created (Bessembinder, 2018). Owning too few names mostly means missing the few that matter.</li>
</ul>"""
def _card(title, facts, touches, against):
    return (f'<div class="card"><h3>{title}</h3>' + "".join(f"<p>{f}</p>" for f in facts)
            + f'<p class="small"><b>Touches:</b> {touches}</p><p class="small"><b>The other side:</b> {against}</p></div>')


MACRO_HTML = (
    """<div class="prose"><h2 class="h2" id="shifts">The big shifts behind the market</h2>
<p>These are the trends most likely to move whole groups of stocks over the next few years, as they stood on October 28, 2026. Each comes with dated facts, the kinds of company it touches and the strongest argument against it. They move quickly, so the dates matter. The Bank of Canada raised its rate on the morning of October 28; the Federal Reserve announces its decision that afternoon, so the U.S. rate here is from before it.</p></div>
<div class="edge-trend">"""
    + _card("The AI build-out",
            ["In April, Alphabet, Microsoft, Amazon and Meta together guided to about $725 billion of capital spending for 2026, mostly data centres and chips (Yahoo Finance, Apr 29).",
             "The suppliers are being paid: Nvidia's quarter to July 26 brought $96.2 billion of revenue, up 106% in a year, $89.0 billion of it from data centres (Nvidia, Aug 26).",
             "On October 13 the IMF said a sharp fall in AI investment could take 1.1% off global output by 2028, and described the world economy as \"standing on one leg, the AI leg\"."],
            "chips, memory, networking, cloud software, power and electrical equipment, utilities and data-centre property; in Canada, power producers, pipelines, uranium and copper.",
            "Spending is running ahead of the cash it earns (BofA estimates the four biggest spenders' free cash flow near zero in 2026, as reported by investingLive). The answer from the other side: their core businesses are highly profitable, and the suppliers' earnings show the demand is real.")
    + _card("An oil shock, and rising power demand",
            ["Shipping through the Strait of Hormuz has been constrained since the war with Iran began on February 28; the IEA counted a fall in world oil supply of 10.1 million barrels a day in March.",
             "The EIA expects Brent to average $105 a barrel in the fourth quarter of 2026 and $84 in 2027, assuming flows from the Gulf stay constrained through year-end (Short-Term Energy Outlook, Oct 6).",
             "Electricity use is growing for slower reasons: world power demand rose 3% in 2025 and data-centre demand 17% (IEA), and U.S. data centres could use 9.5% to 15.3% of the country's electricity by 2030 (Lawrence Berkeley National Laboratory, June 2026)."],
            "oil and gas producers, pipelines, LNG, refiners, utilities, grid equipment and uranium, which the TSX holds a lot of; airlines, chemicals and transport pay more for fuel.",
            "A price driven by a war can reverse quickly once ships move (the EIA's own path falls toward $74 by late 2027), and power-demand forecasts span a wide range.")
    + _card("Inflation and rates turned up again",
            ["The Fed raised its rate to 3.75–4.00% on September 16, its first increase since 2023. U.S. consumer prices rose 3.7% in the year to September; core prices, without food and energy, 2.6%. The 10-year Treasury yield was near 5% in late October.",
             "On October 28 the Bank of Canada raised its rate by a quarter point to 2.50%, its first increase since July 2023, to keep high energy prices from spilling into wider inflation, and said another increase may be needed (BNN Bloomberg). Canadian prices rose 3.1% in the year to September, even as the economy lost 68,000 jobs that month, taking unemployment to 6.5% (Statistics Canada)."],
            "banks, insurers, utilities, real estate, homebuilders and the highest-valued growth stocks, whose worth rests most on earnings far in the future.",
            "Core inflation is far below the headline. If oil falls as the EIA expects, the case for higher rates weakens.")
    + _card("Government debt",
            ["The U.S. ran a deficit of $1.99 trillion in the year to September, and its net interest bill was $1.14 trillion, up 11% (Congressional Budget Office, Oct 8). The CBO projects federal debt at 101% of GDP in 2026, rising to 120% by 2036.",
             "Canada's Parliamentary Budget Officer projects a federal deficit of $63.3 billion in 2026–27 (Oct 20); the next federal budget is on November 5."],
            "mostly through bond yields, which set the price of every future dollar of earnings; also government contractors and banks.",
            "Economists disagree about how much debt is too much, and when it starts to matter for rates.")
    + _card("Tariffs and trade",
            ["In February the U.S. Supreme Court ruled that the emergency-powers law did not authorize tariffs; the administration rebuilt them under other laws. Since July 24, most countries face 10% or 12.5% duties under Section 301, with goods that qualify under the U.S.-Mexico-Canada agreement excluded; steel, aluminum and copper face 50% and autos 25% under Section 232.",
             "On August 22 the U.S. put 50% duties on a range of Canadian goods under Section 338, the first use of that law, including goods that qualify under the agreement. Canada answered with counter-tariffs on C$27.6 billion of U.S. goods from September 8 and a C$7.5 billion support package. The agreement stays in force to 2036, now with annual reviews.",
             "The U.S. administration says tariffs rebuild American manufacturing and is seeking more access to Canada's dairy, wine and spirits markets. Canada's government calls the measures unfair, says it will match them dollar for dollar, and is signing trade agreements elsewhere."],
            "autos and parts, steel and aluminum, forestry, food, Canadian manufacturers and exporters, U.S. importers and retailers.",
            "The legal basis for the tariffs has changed three times this year, and a deal or an escalation could change the picture just as fast.")
    + _card("Ageing, and slower population growth",
            ["Canada's population grew 0.5% in the year to July 1, 2026, the slowest since 1944–45; one person in five is 65 or older, and the fertility rate is 1.26 (Statistics Canada).",
             "U.S. net international migration fell from 2.7 million in 2024 to 1.3 million in the year to July 2025 (Census Bureau). U.S. health spending is projected to reach about 20.6% of GDP by 2034 (CMS)."],
            "health care, seniors' housing, insurers, rental housing and labour-heavy industries, plus consumer demand in general.",
            "Immigration policy can reverse quickly, and automation may make up for fewer workers.")
    + _card("New medicines for obesity",
            ["Eli Lilly's second-quarter revenue rose 48% to $23.0 billion on its two obesity and diabetes drugs; the FDA approved its first obesity pill on April 1, and about one American in eight has used an injectable GLP-1 drug (KFF).",
             "Canada approved its first generic semaglutide on April 28, the first G7 country to do so, with prices set to fall to about 35% of the brand once there are three or more generics."],
            "drug makers, generic makers, medical devices, food and drink companies, insurers and pharmacies.",
            "Prices are falling and generics are coming; how long people stay on the drugs is still uncertain.")
    + _card("Defence spending",
            ["NATO members agreed to aim for 5% of GDP by 2035: 3.5% on core defence and 1.5% on related spending. Canada reached 2% in March 2026.",
             "Reaching 3.5% would mean Canada spending $159.1 billion on defence in 2035–36, $68.2 billion more than at 2% (Parliamentary Budget Officer)."],
            "aerospace, shipbuilding, munitions, electronics, cyber and space; in Canada, aerospace and steel.",
            "Budgets are already stretched, and defence buying is often delayed or cut.")
    + _card("Canadian housing",
            ["Home sales in September were 7.7% lower than a year earlier and the benchmark price 3.4% lower (CREA, Oct 16); housing starts ran at an annual pace of 248,896 (CMHC)."],
            "banks, mortgage insurers, homebuilders, apartment owners, building materials and lumber.",
            "A long-run housing shortage and a slowing market pull in opposite directions; the Bank of Canada's next moves matter.")
    + _card("The rising cost of weather",
            ["Canadian insured losses topped $3.7 billion in the summer of 2026, the third costliest summer on record; four of the five costliest summers have come in the last six years (Insurance Bureau of Canada, Oct 22)."],
            "property insurers and reinsurers, building products, water infrastructure, utilities with wildfire exposure and mortgage lenders.",
            "Losses swing a lot from year to year: worldwide, the first half of 2026 was the cheapest since 2020 (Swiss Re). Insurers can reprice every year.")
    + _card("Concentration, and value's comeback",
            ["The S&P 500 traded at 18.7 times next year's expected earnings on October 23, close to its 10-year average, but only because analysts expect earnings to grow 33% in 2026; on the past year's earnings it was 25.7 times (FactSet).",
             "Value has led in 2026. To September 30, MSCI's U.S. value index rose 14.6% against 12.3% for the whole U.S. market; in Canada, the value index rose 23.9% against 1.5% for growth (MSCI)."],
            "index funds, which now ride heavily on a few technology companies, and the cheaper sectors: energy, materials and banks.",
            "The forward P/E looks normal only if record earnings growth arrives. Value has had good years before (2021 and 2022) and given them back.")
    + _card("Canada's resources",
            ["Copper has cost about 40% more this year than last on average (COCHILCO, Oct 14), with mine output disrupted and tariffs drawing metal into U.S. warehouses.",
             "Potash, energy and critical minerals are exempt from the Section 338 duties. China refines more than 90% of the world's rare earths, and Canada has signed deals with 12 countries to build other supply."],
            "TSX miners and royalty companies, fertilizer, railways and ports.",
            "Commodity prices swing hard, and tariffs and stockpiling are distorting some of them; a resource company's profits can halve as fast as they doubled.")
    + """</div>
<div class="prose"><h3 class="h3">Where things are heading</h3>
<p>Six shifts run for a decade or more, and most serious forecasters agree on their direction: <b>older populations</b> and slower growth in the number of workers; <b>more electricity</b>, for data centres, vehicles and industry; <b>higher public debt</b> and a bigger share of budgets going to interest; <b>AI and digital infrastructure</b> as the largest single theme in business investment; <b>security-driven economics</b>, from defence budgets to supply chains, critical minerals and trading blocs; and <b>rising losses from extreme weather</b>.</p>
<p>Where they disagree is just as useful: whether AI spending earns its cost; whether inflation and rates stay higher or fall back once oil does; where oil goes after the war (the EIA sees $74 by late 2027; the IMF's bad case has it above $130); how fast the move to cleaner energy goes now that U.S. tax support has been cut back; what happens to the trade agreement with the U.S.; and which valuation gauge to trust, next year's earnings or the last ten years'.</p>
<p><b>How this connects to value.</b> Value's two best recent stretches, 2021–22 and 2026 so far, both came with rising inflation and dearer energy, which favour companies that earn cash today (energy, materials, banks) over ones valued on earnings far in the future. The growth-led decade before it came with falling rates and the build-out of the internet's largest companies. Research finds interest rates on their own explain little of value's ups and downs, so treat this as a pattern to watch, not a rule. It does say why a single decade of data, ours included, can't settle the question.</p></div>""")
TOGETHER_HTML = """<h2 class="h2" id="together">Tying it together</h2>
<p>None of the pieces above is enough on its own. Cheap stocks can stay cheap for a decade; trends break; the long shifts play out over years and don't say which company wins. What the evidence supports is a way of using each piece for the job it's good at. Written down as steps, it looks like this. It's a description of how the parts fit, not a recommendation for any account.</p>
<ol class="edge-steps">
<li><b>Know what you own: the business.</b> The company numbers say whether a business is cheap, growing and sound: price against earnings and cash flow, revenue growth, margins, debt. In the research they pay off over long stretches, best in combination; in our recent U.S. data, growth mattered more than cheapness. Each stock page shows its numbers and where they rank, and <a href="{guide}">Your signal</a> can weight any of them.</li>
<li><b>Let the price tell you when the market disagrees.</b> Trend and momentum had the steadiest record in our tests, and the exit side is where the signal earns its keep: its Sells were about twice as likely as its Buys to fall 30% or more. In the research, pairing cheapness with price trend screened out many value traps; in our recent U.S. data it didn't, which is one more reason to treat a single decade with care (<a href="{sell}">when to sell</a>).</li>
<li><b>Size it so being wrong is survivable.</b> No measure here stops one stock from halving. How much rides on a single name matters more than any edge in this piece (<a href="{one}">one stock too many</a>, and the <a href="{storm}">storm test</a> for debt).</li>
<li><b>Use the big shifts as questions, not forecasts.</b> For each holding: which of these trends does it depend on (rates, energy prices, tariffs, AI spending, an ageing population), and does the price already assume they keep going? The <a href="{markets}">Markets page</a> tracks the gauges and <a href="{bubble}">Is this a bubble?</a> reads them.</li>
<li><b>Count the costs, taxes and turnover.</b> Unlike any factor, what they take is certain. A rule that trades less often keeps more of what it earns.</li>
<li><b>Write the rule down before the trade, then grade it.</b> That's what every page on this site does for the plays and factors. You can do the same with your own mix: set the weights, follow the names, get an <a href="{alerts}">email when a call changes</a>, and check it against <a href="{graded}">the weekly scorecard</a>. Earnings reports are when the numbers change; the <a href="{earnings}">earnings calendar</a> lists the next ones.</li>
</ol>
<p>Be The Puck is not a broker or an adviser and never places trades. What's next on our side: a test on a list that includes stocks that no longer trade, better value measures (cash-flow yield and value within each sector) graded the same way before they get a slider, and a daily record of the signal's own calls.</p>"""
RESEARCH_SOURCES = [
    ("Ken French Data Library (U.S. factor and portfolio returns since 1926)", "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"),
    ("Arnott, Harvey, Kalesnik and Linnainmaa, 'Reports of Value's Death May Be Greatly Exaggerated', Financial Analysts Journal (2021)", "https://ideas.repec.org/a/taf/ufajxx/v77y2021i1p44-67.html"),
    ("Asness, 'Is (Systematic) Value Investing Dead?', AQR (2020)", "https://www.aqr.com/Insights/Perspectives/Is-Systematic-Value-Investing-Dead"),
    ("Eisfeldt, Kim and Papanikolaou, 'Intangible Value', Critical Finance Review (2022)", "https://nowpublishers.com/article/Details/CFR-0113"),
    ("Maloney and Moskowitz, 'Value and Interest Rates', Journal of Portfolio Management (2021)", "https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Interest-Rates-Are-Rates-to-Blame-for-Values-Torments"),
    ("Fama and French, 'Size, value, and momentum in international stock returns', Journal of Financial Economics (2012)", "https://ideas.repec.org/a/eee/jfinec/v105y2012i3p457-472.html"),
    ("Israel and Moskowitz, 'The role of shorting, firm size, and time on market anomalies', Journal of Financial Economics (2013)", "https://ideas.repec.org/a/eee/jfinec/v108y2013i2p275-301.html"),
    ("Athanassakos, 'Value versus growth stock returns and the value premium: the Canadian experience', Canadian Journal of Administrative Sciences (2009)", "https://www.ivey.uwo.ca/cmsmedia/3775496/value_vs_growth_stock_returns_and_the_value_premium.pdf"),
    ("Assoe, Attig and Sy, 'Navigating Canada's Factor Zoo', CFA Society Toronto (2024)", "https://cfatoronto.ca/docs/default-source/cfast-hillsdale-research-paper/navigating-canada's-factor-zoo---research-paper"),
    ("Gray and Vogel, 'Analyzing Valuation Measures', Journal of Portfolio Management (2012)", "https://alphaarchitect.com/wp-content/uploads/2022/11/AAJPMFall12AnalyzingValuationMeasures.pdf"),
    ("Asness and Frazzini, 'The Devil in HML's Details', Journal of Portfolio Management (2013)", "https://www.aqr.com/Insights/Research/Journal-Article/The-Devil-in-HMLs-Details"),
    ("Asness, Porter and Stevens, 'Predicting Stock Returns Using Industry-Relative Firm Characteristics', AQR working paper (2000)", "https://www.aqr.com/Insights/Research/Working-Paper/Predicting-Stock-Returns-Using-IndustryRelative-Firm-Characteristics"),
    ("Novy-Marx, 'The other side of value: The gross profitability premium', Journal of Financial Economics (2013)", "https://ideas.repec.org/a/eee/jfinec/v108y2013i1p1-28.html"),
    ("Fama and French, 'A five-factor asset pricing model', Journal of Financial Economics (2015)", "https://academicnewsletter.sufe.edu.cn/info/356476"),
    ("Asness, Frazzini and Pedersen, 'Quality Minus Junk', Review of Accounting Studies (2019)", "https://ideas.repec.org/a/spr/reaccs/v24y2019i1d10.1007_s11142-018-9470-2.html"),
    ("Piotroski, 'Value Investing: The Use of Historical Financial Statement Information' (2000), summarised by Chicago Booth Review", "https://www.chicagobooth.edu/review/separating-winners-losers"),
    ("Walkshäusl, 'Piotroski's FSCORE: international evidence', Journal of Asset Management (2020)", "https://ideas.repec.org/a/pal/assmgt/v21y2020i2d10.1057_s41260-020-00157-2.html"),
    ("Asness, Moskowitz and Pedersen, 'Value and Momentum Everywhere', Journal of Finance (2013)", "https://www.aqr.com/library/journal-articles/value-and-momentum-everywhere"),
    ("Asness, 'The Interaction of Value and Momentum Strategies', Financial Analysts Journal (1997)", "https://ideas.repec.org/a/taf/ufajxx/v53y1997i2p29-36.html"),
    ("Bordalo, Gennaioli, La Porta and Shleifer, 'Diagnostic Expectations and Stock Returns', Journal of Finance (2019)", "https://www.nber.org/papers/w23863"),
    ("Chan, Karceski and Lakonishok, 'The Level and Persistence of Growth Rates', Journal of Finance (2003)", "https://www.nber.org/papers/W8282"),
    ("Bradshaw, 'How Do Analysts Use Their Earnings Forecasts in Generating Stock Recommendations?', The Accounting Review (2004)", "https://academicnewsletter.sufe.edu.cn/info/416180"),
    ("McLean and Pontiff, 'Does Academic Research Destroy Stock Return Predictability?', Journal of Finance (2016)", "https://academicnewsletter.sufe.edu.cn/info/359722"),
    ("Hou, Xue and Zhang, 'Replicating Anomalies', Review of Financial Studies (2020)", "https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html"),
    ("Jensen, Kelly and Pedersen, 'Is There a Replication Crisis in Finance?', Journal of Finance (2023)", "https://www.nber.org/papers/w28432"),
    ("Jegadeesh and Titman, 'Profitability of Momentum Strategies: An Evaluation of Alternative Explanations', Journal of Finance (2001)", "https://ideas.repec.org/a/bla/jfinan/v56y2001i2p699-720.html"),
    ("Daniel and Moskowitz, 'Momentum crashes', Journal of Financial Economics (2016)", "https://www.nber.org/papers/w20439"),
    ("Ikenberry, Lakonishok and Vermaelen, 'Market underreaction to open market share repurchases', Journal of Financial Economics (1995)", "https://ideas.repec.org/a/eee/jfinec/v39y1995i2-3p181-208.html"),
    ("McLean, Pontiff and Watanabe, 'Share issuance and cross-sectional returns: International evidence', Journal of Financial Economics (2009)", "https://ideas.repec.org/a/eee/jfinec/v94y2009i1p1-17.html"),
    ("Cohen, Malloy and Pomorski, 'Decoding Inside Information', Journal of Finance (2012)", "https://www.nber.org/papers/w16454"),
    ("Martineau, 'Rest in Peace Post-Earnings Announcement Drift', Critical Finance Review (2022)", "https://ideas.repec.org/a/now/jnlcfr/104.00000122.html"),
    ("Chan, Jegadeesh and Lakonishok, 'Momentum Strategies', Journal of Finance (1996)", "https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1681-1713.html"),
    ("Novy-Marx and Velikov, 'Betting against betting against beta', Journal of Financial Economics (2022)", "https://ideas.repec.org/a/eee/jfinec/v143y2022i1p80-106.html"),
    ("Green, Hand and Soliman, 'Going, Going, Gone? The Apparent Demise of the Accruals Anomaly', Management Science (2011)", "https://ideas.repec.org/a/inm/ormnsc/v57y2011i5p797-816.html"),
    ("French, 'Presidential Address: The Cost of Active Investing', Journal of Finance (2008)", "https://ideas.repec.org/a/bla/jfinan/v63y2008i4p1537-1573.html"),
    ("S&P Dow Jones Indices, SPIVA Canada Year-End 2025", "https://www.spglobal.com/spdji/en/spiva/article/spiva-canada-year-end-2025/"),
    ("Barber and Odean, 'Trading Is Hazardous to Your Wealth', Journal of Finance (2000)", "https://ideas.repec.org/a/bla/jfinan/v55y2000i2p773-806.html"),
    ("Morningstar, Mind the Gap 2026", "https://www.morningstar.com/content/cs-assets/v3/assets/blt9415ea4cc4157833/blt852a4301adc2f5db/6a7373d51f7b5ae2da78e1e8/US_Mind_the_Gap_2026.pdf"),
    ("Chaudhuri, Burnham and Lo, 'An Empirical Evaluation of Tax-Loss-Harvesting Alpha', Financial Analysts Journal (2020)", "https://ideas.repec.org/a/taf/ufajxx/v76y2020i3p99-108.html"),
    ("Canada Revenue Agency: capital losses and the superficial loss rule", "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html"),
    ("Bessembinder, 'Do stocks outperform Treasury bills?', Journal of Financial Economics (2018)", "https://academicnewsletter.sufe.edu.cn/info/356102"),
]
MACRO_SOURCES = [
    ("Yahoo Finance: hyperscaler capex set to reach $725 billion in 2026 (Apr 29, 2026)", "https://finance.yahoo.com/markets/article/magnificent-7-earnings-rush-reveals-ai-spending-surge-with-hyperscaler-capex-set-to-reach-725-billion-in-2026-224901707.html"),
    ("Nvidia second-quarter fiscal 2027 results (SEC filing, Aug 26, 2026)", "https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000073/q2fy27pr.htm"),
    ("investingLive: BofA on AI capex and free cash flow (Aug 4, 2026)", "https://investinglive.com/stocks/if-you-think-ai-capex-is-insane-this-year-wait-until-2027-as-bofa-sees-a-nearly-50-rise/"),
    ("Khaleej Times (Reuters): IMF on AI investment, war and debt (Oct 13, 2026)", "https://www.khaleejtimes.com/business/ai-investment-props-up-global-growth-but-war-and-debt-threaten-outlook-imf-says"),
    ("Seatrade Maritime: IEA on the largest oil supply disruption in history (April 2026)", "https://www.seatrade-maritime.com/tankers/iea-cuts-oil-outlook-on-largest-disruption-in-history-"),
    ("U.S. EIA, Short-Term Energy Outlook (Oct 6, 2026)", "https://www.eia.gov/outlooks/steo/archives/oct26.pdf"),
    ("Bloomberg Law: IEA on 2025 power demand (Apr 20, 2026)", "https://news.bloomberglaw.com/environment-and-energy/global-2025-power-demand-rose-as-ev-data-centers-grew-iea-says"),
    ("Lawrence Berkeley National Laboratory: U.S. data center energy use (June 2026)", "https://eta-publications.lbl.gov/publications/united-states-data-center-energy-2025"),
    ("Federal Reserve FOMC statement (Sep 16, 2026)", "https://federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm"),
    ("investingLive: U.S. September CPI (Oct 14, 2026)", "https://investinglive.com/news/us-september-cpi-vs-3-6-expected-0/"),
    ("BNN Bloomberg: Bank of Canada raises key interest rate, says another hike possible (Oct 28, 2026)", "https://bnnbloomberg.ca/business/economics/2026/10/28/bank-of-canada-raises-key-interest-rate-says-another-hike-possible"),
    ("The Star (Xinhua): Canada's CPI rises 3.1% in September (Oct 20, 2026)", "https://www.thestar.com.my/news/world/2026/10/20/canada039s-cpi-rises-31-pct-in-september"),
    ("The Hub: Canada shed 68,000 jobs in September (Oct 9, 2026)", "https://thehub.ca/2026/10/09/canada-shed-68000-jobs-in-september-statistics-canada-reports/"),
    ("Congressional Budget Office, Monthly Budget Review (Oct 8, 2026)", "https://www.cbo.gov/system/files/2026-10/61985-MBR.pdf"),
    ("Congressional Budget Office testimony on the budget outlook (Mar 11, 2026)", "https://www.cbo.gov/publication/62207"),
    ("Advisor.ca: PBO trims economic forecast amid new U.S. tariffs (Oct 20, 2026)", "https://www.advisor.ca/economy/economic-indicators/pbo-trims-economic-forecast-amid-new-u-s-tariffs/"),
    ("Morgan Lewis: U.S. rebuilds global tariff program under Section 301 (Jul 27, 2026)", "https://www.morganlewis.com/pubs/2026/07/us-administration-rebuilds-global-tariff-program-under-section-301"),
    ("Great Lakes Customs Law: tariff timeline (Apr 18, 2026)", "https://greatlakescustomslaw.com/trump-tariff-timeline-report/"),
    ("Covington: Section 338 tariffs on Canada take effect as Canada announces retaliatory response (Aug 2026)", "https://www.cov.com/en/news-and-insights/insights/2026/08/section-338-tariffs-on-canada-take-effect-as-canada-announces-retaliatory-response"),
    ("Blakes: Canada imposes counter-tariffs on $27.6 billion of U.S. imports (Aug 25, 2026)", "https://www.blakes.com/insights/canada-imposes-counter-tariffs-on-27-6-billion-of-u-s-imports-effective-september-8-2026/"),
    ("Willson International: CUSMA joint review (Jul 10, 2026)", "https://www.willsonintl.com/news/cusma-joint-review-u-s-triggers-annual-review-process-while-pacts-remain-in-force/"),
    ("Euronews: Carney on new U.S. tariffs (Aug 23, 2026)", "https://euronews.com/2026/08/23/canadian-pm-carney-says-new-us-tariffs-are-designed-to-hurt-us-and-divide-us"),
    ("Global News (Statistics Canada): population growth to July 2026", "https://globalnews.ca/news/12070197/canada-population-growth-july-2026/"),
    ("U.S. Census Bureau: historic decline in net international migration (Jan 2026)", "https://census.gov/newsroom/blogs/random-samplings/2026/01/historic-decline-in-net-international-migration.html"),
    ("CMS national health spending projections, via Health Systems Facts (Jun 24, 2026)", "https://healthsystemsfacts.org/2026/06/24/us-health-spending-projected-to-reach-nearly-nine-trillion-dollars-by-2034/"),
    ("American Pharmaceutical Review: Lilly second-quarter 2026 results", "https://www.americanpharmaceuticalreview.com/1315-News/627249-Lilly-Q2-Revenue-Jumps-48-as-Mounjaro-and-Zepbound-Drive-Guidance-Raise/"),
    ("AP: FDA approves Lilly's obesity pill (Apr 1, 2026)", "https://www.adn.com/nation-world/2026/04/01/fda-grants-approval-to-eli-lillys-weight-loss-pill-for-obesity/"),
    ("BNN Bloomberg: Health Canada approves first generic semaglutide (Apr 29, 2026)", "https://www.bnnbloomberg.ca/business/2026/04/29/health-canada-approves-1st-generic-version-of-ozempic-in-the-country/"),
    ("ICDS: defence spending, who is doing what (Jul 9, 2026)", "https://icds.ee/en/defence-spending-who-is-doing-what-july-2026/"),
    ("CDA Institute: Canada hits 2% defence spending (Apr 7, 2026)", "https://cdainstitute.ca/canada-hits-2-defence-spending-substance-or-symbolism/"),
    ("Parliamentary Budget Officer: fiscal implications of NATO's 5% commitment (Feb 5, 2026)", "https://www.pbo-dpb.ca/en/publications/RP-2526-022-S--fiscal-implications-meeting-nato-5-commitment"),
    ("BNN Bloomberg (CREA): home sales forecast cut (Oct 16, 2026)", "https://www.bnnbloomberg.ca/business/real-estate/2026/10/16/crea-downgrades-home-sales-forecast-for-the-third-time-this-year/"),
    ("CMHC: housing starts, September 2026", "https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/housing-starts-construction-data-september-2026"),
    ("Insurance Business (IBC/CatIQ): summer 2026 insured losses (Oct 22, 2026)", "https://www.insurancebusinessmag.com/ca/news/catastrophe/summer-2026-cost-insurers-3-7-billion-thirdworst-on-record-ibc-594674.aspx"),
    ("Artemis (Swiss Re): first-half 2026 insured catastrophe losses (Aug 11, 2026)", "https://artemis.bm/news/global-insured-cat-losses-reach-42bn-in-h1-2026-lowest-first-half-since-2020-swiss-re"),
    ("FactSet Earnings Insight (Oct 23, 2026)", "https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_102326.pdf"),
    ("MSCI USA Value index factsheet (Sep 30, 2026)", "https://www.msci.com/documents/10199/18ebb88c-a162-4800-ad07-1bbd5f3b9eb3"),
    ("MSCI Canada Value index factsheet, CAD (Sep 30, 2026)", "https://www.msci.com/documents/10199/7bfd48bf-16f2-41e7-af5b-d60afd8c5853"),
    ("MSCI Canada Growth index factsheet, CAD (Sep 30, 2026)", "https://www.msci.com/documents/10199/a3b04724-ba92-4b20-aaac-a9b8f47079de"),
    ("Reporte Minero (COCHILCO): copper price (Oct 14, 2026)", "https://www.reporteminero.cl/noticia/noticias/2026/10/precio-cobre-alza-anual-40-porciento-cotizacion-bolsa-londres-inventarios"),
    ("Mining Weekly: Canada on critical minerals supply (Mar 4, 2026)", "https://www.miningweekly.com/article/canada-advocates-buyers-alliance-to-tackle-critical-minerals-supply-concentration-2026-03-04"),
    ("UN World Population Prospects 2024: key messages", "https://population.un.org/WPP/Publications/Files/WPP2024_Key-Messages.pdf"),
]
SOURCES = RESEARCH_SOURCES + MACRO_SOURCES
