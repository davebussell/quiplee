"""Three articles on risk and selling, written after the October 2026 change to Your signal
(the default now weights how far a stock is off its high and its trend, and analysts' upside
is held to neutral below the 200-day average). Each one is rebuilt from the prices every night:

  articles/when-to-sell/            what drawdown and trend-break rules have done since 2011
  articles/one-stock-too-many/      what holding one stock, or a few, has done to a year's result
  articles/why-your-signal-changed/ why analysts' upside grows as a stock falls, and the new weights

Facts and tested numbers only: nothing here tells the reader what to do (CLAUDE.md).
"""
import html

import numpy as np
import pandas as pd

from .render import is_stock

e = html.escape
START = pd.Timestamp("2011-01-01")
HORIZONS = (63, 252)          # sessions: about three months and a year
GUARDS = (0.15, 0.20, 0.25, 0.30, 0.40)
GUARD = 0.25                  # the rule the articles single out: 25%+ off the 1-year high and below the 200-day
SIZES = (1, 3, 5, 10, 20)
DRAWS = 4000

PIECES = [
    ("strategies", "articles/when-to-sell/", "When to sell: what drawdown and trend rules have done",
     "Every covered stock, every month since 2011: what happened next to stocks well off their high and below their 200-day average, and what a sell rule costs.", "live", None),
    ("strategies", "articles/one-stock-too-many/", "One stock, most of the money",
     "Thousands of random one-, five- and twenty-stock portfolios from the covered names: how often each lost 30% in a year, and why one position can decide a whole account.", "live", None),
    ("strategies", "articles/why-your-signal-changed/", "Why Your signal stopped leaning on analysts' targets",
     "Targets follow the price down, so a falling stock looks better the further it falls. What changed in the standard weights in October 2026, and what each factor's record is.", "live", None),
]


def pts(v, sign=False):
    """An edge (a difference of two shares) in percentage points: 0.063 -> "6.3"."""
    x = round(100 * v, 1)
    return ("−" if x < 0 else "+" if sign and x > 0 else "") + f"{abs(x):.1f}"


def pc(v, d=0, sign=True):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if sign and v > 0 else s)


def _stocks(site):
    return [t for t in site.universe if is_stock(t) and t["sym"] in site.prices and t.get("bench") in site.prices]


def study(site):
    """Month-end facts for every covered stock since START, cached on the site:
    {"rows": DataFrame(sym, date, off, below, x63, x252, r252), "since", "to", "stocks"}.
    off = price / highest close of the past year - 1; below = under the 200-day average;
    xH = return over the next H sessions less the stock's market's; r252 = the stock's own next-year return."""
    c = site.__dict__.get("_riskstudy")
    if c is not None:
        return c
    cal = site.prices["^GSPC"]["close"].index
    me = pd.Series(cal, index=cal).groupby(cal.to_period("M")).last()
    dates = pd.DatetimeIndex([d for d in me.values if d >= START])
    recs = []
    names = set()
    for t in _stocks(site):
        cs, bs = site.prices[t["sym"]]["close"], site.prices[t["bench"]]["close"]
        cv, bv = cs.values.astype(float), bs.values.astype(float)
        ii, jj = cs.index.searchsorted(dates, side="right") - 1, bs.index.searchsorted(dates, side="right") - 1
        ma = cs.rolling(200).mean().values
        hi = cs.rolling(252).max().values
        for d, i, j in zip(dates, ii, jj):
            if i < 251 or j < 0 or cv[i] <= 0 or not np.isfinite(hi[i]) or not np.isfinite(ma[i]):
                continue
            r = {"sym": t["sym"], "date": d, "off": cv[i] / hi[i] - 1, "below": cv[i] < ma[i]}
            for h in HORIZONS:
                ok = i + h < len(cv) and j + h < len(bv) and bv[j] > 0
                r[f"x{h}"] = (cv[i + h] / cv[i] - bv[j + h] / bv[j]) if ok else np.nan
            r["r252"] = cv[i + 252] / cv[i] - 1 if i + 252 < len(cv) else np.nan
            recs.append(r)
            names.add(t["sym"])
    df = pd.DataFrame(recs)
    out = {"rows": df, "since": dates[0] if len(dates) else START, "to": df["date"].max() if len(df) else None, "stocks": len(names)}
    site.__dict__["_riskstudy"] = out
    return out


def _beat(x):
    x = x.dropna()
    return (float((x > 0).mean()) if len(x) else None), (float(x.median()) if len(x) else None), len(x)


def guard_table(df):
    """[(threshold, share of stock-months flagged, {h: (beat, median, n)} flagged, {h: ...} not flagged)]"""
    out = []
    for g in GUARDS:
        hit = (df["off"] <= -g) & df["below"]
        out.append((g, float(hit.mean()), {h: _beat(df.loc[hit, f"x{h}"]) for h in HORIZONS}, {h: _beat(df.loc[~hit, f"x{h}"]) for h in HORIZONS}))
    return out


def rebounds(df, g=GUARD):
    """Of the flagged stock-months with a known next year: how many more than doubled, and how many fell
    another 30% or more in the year after."""
    hit = df[((df["off"] <= -g) & df["below"])]["r252"].dropna()
    if not len(hit):
        return None
    return {"n": len(hit), "doubled": float((hit >= 1).mean()), "fell30": float((hit <= -0.3).mean()), "median": float(hit.median())}


def flagged_now(site, g=GUARD):
    """Covered stocks that meet the rule on tonight's close: [(t, off, vs 200-day)], furthest off first."""
    out = []
    for t in _stocks(site):
        c = site.prices[t["sym"]]["close"]
        if len(c) < 252:
            continue
        p, hi, ma = float(c.iloc[-1]), float(c.iloc[-252:].max()), float(c.iloc[-200:].mean())
        if hi > 0 and ma > 0 and p / hi - 1 <= -g and p < ma:
            out.append((t, p / hi - 1, p / ma - 1))
    return sorted(out, key=lambda x: x[1])


def portfolios(site, seed=2026):
    """Random equal-weight portfolios of 1 to 20 covered stocks, held a year from a random month-end since START.
    {size: {"lost30": share losing 30%+, "median", "p5", "p95", "worst"}} and the S&P 500's own record over the same starts."""
    c = site.__dict__.get("_riskports")
    if c is not None:
        return c
    df = study(site)["rows"].dropna(subset=["r252"])
    if df.empty:
        return {}
    by_date = {d: g["r252"].values for d, g in df.groupby("date") if len(g) >= max(SIZES)}
    dates = sorted(by_date)
    rng = np.random.default_rng(seed)
    out = {}
    for n in SIZES:
        res = np.empty(DRAWS)
        for k in range(DRAWS):
            v = by_date[dates[rng.integers(len(dates))]]
            res[k] = v[rng.choice(len(v), n, replace=False)].mean()
        out[n] = {"lost30": float((res <= -0.3).mean()), "lost": float((res < 0).mean()), "median": float(np.median(res)),
                  "p5": float(np.percentile(res, 5)), "p95": float(np.percentile(res, 95))}
    spx = site.prices["^GSPC"]["close"]
    sr = []
    for d in dates:
        i = spx.index.searchsorted(d, side="right") - 1
        if i + 252 < len(spx):
            sr.append(spx.iloc[i + 252] / spx.iloc[i] - 1)
    sr = np.array(sr)
    out["spx"] = {"lost30": float((sr <= -0.3).mean()), "lost": float((sr < 0).mean()), "median": float(np.median(sr)),
                  "p5": float(np.percentile(sr, 5)), "p95": float(np.percentile(sr, 95))} if len(sr) else None
    out["starts"] = len(dates)
    site.__dict__["_riskports"] = out
    return out


def worst_falls(site):
    """Each covered stock's worst fall from a high since START: (share that fell 50%+, share 70%+, median worst fall, n)."""
    w = []
    for t in _stocks(site):
        c = site.prices[t["sym"]]["close"]
        c = c[c.index >= START]
        if len(c) < 252:
            continue
        w.append(float((c / c.cummax() - 1).min()))
    if not w:
        return None
    w = np.array(w)
    return float((w <= -0.5).mean()), float((w <= -0.7).mean()), float(np.median(w)), len(w)


def spx_worst(site):
    c = site.prices["^GSPC"]["close"]
    c = c[c.index >= START]
    return float((c / c.cummax() - 1).min())


def _grades(site):
    from .factorgrade import cached
    return cached(site) or {}


# ------------------------------------------------------------------ the pages
class RiskArticles:
    def __init__(self, arts):
        self.a = arts
        self.s = arts.s

    def build(self):
        for name in ("when_to_sell", "concentration", "signal_change"):
            try:
                getattr(self, name)()
            except Exception as ex:          # an article must never stop a build
                print(f"article {name} skipped:", ex)

    def _tbl(self, head, rows, note=""):
        th = "".join(f'<th{" class=r" if i else ""}>{x}</th>' for i, x in enumerate(head))
        return (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>'
                + (f'<p class="small muted">{note}</p>' if note else ""))

    def when_to_sell(self):
        b, path, title, dek, _, _ = PIECES[0]
        depth = path.count("/")
        h = self.a.h(depth)
        st = study(self.s)
        df = st["rows"]
        if df.empty:
            return
        G = guard_table(df)
        rows = ""
        for g, share, hit, rest in G:
            (b3, m3, _), (b12, m12, n12) = hit[63], hit[252]
            (rb3, _, _), (rb12, rm12, _) = rest[63], rest[252]
            rows += (f'<tr{" class=hl" if g == GUARD else ""}><td>{pc(g, sign=False)}+ off the high, below the 200-day</td><td class="r">{pc(share, sign=False)}</td>'
                     f'<td class="r">{pc(b3, sign=False)} <span class="sym-sub">others {pc(rb3, sign=False)}</span></td>'
                     f'<td class="r">{pc(b12, sign=False)} <span class="sym-sub">others {pc(rb12, sign=False)}</span></td>'
                     f'<td class="r">{pc(m12, 1)} <span class="sym-sub">others {pc(rm12, 1)}</span></td></tr>')
        table = self._tbl(["Rule on a month-end close", "Months flagged", "Beat their market, 3 months", "Beat their market, 1 year", "Median vs market, 1 year"], rows,
                          f"Every covered stock at every month-end from {st['since'].strftime('%b %Y')}, {len(df):,} stock-months in all, against the S&amp;P 500 (or the TSX for Canadian names). "
                          "\"Others\" is every stock-month the rule didn't flag.")
        g25 = next(x for x in G if x[0] == GUARD)
        rb = rebounds(df)
        grade = _grades(self.s)
        fdd = ((grade.get("factors") or {}).get("dd") or {}).get("12m")
        fdd3 = ((grade.get("factors") or {}).get("dd") or {}).get("3m")
        grade_p = ""
        if fdd:
            grade_p = (f"Scored as a factor, by rank among every covered stock, the stocks nearest their high (60 points or more) beat their market over the next year "
                       f"{pc(fdd['buys_beat'], sign=False)} of the time and the ones furthest off it (40 or less) {pc(fdd['avoids_beat'], sign=False)}: an edge of {pts(fdd['edge'])} points"
                       + (f", and {pts(fdd3['edge'])} over three months." if fdd3 else ".")
                       + f" That's how <a href='{h('guides/your-plays/')}#your-signal'>Off the high</a> earns its place in the standard weights.")
        now = flagged_now(self.s)
        now_rows = "".join(f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                           f'<td class="r down">{pc(off)}</td><td class="r down">{pc(ma)}</td></tr>' for t, off, ma in now[:40])
        now_tbl = (self._tbl(["Stock", "From 1-year high", "Vs 200-day average"], now_rows,
                             f"{len(now)} of the covered stocks meet the 25% rule on the {self.s.asof.strftime('%b %-d')} close"
                             + (f"; the 40 furthest off their high are listed." if len(now) > 40 else "."))
                   if now else "<p>No covered stock meets the 25% rule on tonight's close.</p>")
        reb = ""
        if rb:
            reb = (f"The cost shows up in the rebounds. Of the {rb['n']:,} flagged stock-months with a full year after them, {pc(rb['doubled'], sign=False)} more than doubled in the next year, "
                   f"and {pc(rb['fell30'], sign=False)} fell another 30% or more. The median stock rose {pc(rb['median'])}. A sell rule gives up the first group to get out of the second, and you can't tell them apart on the day.")
        b3, _, _ = g25[2][63]
        b12, _, _ = g25[2][252]
        rb12, _, _ = g25[3][252]
        rb3, _, _ = g25[3][63]
        body = f"""
<div class="prose">
{self.a_P("Most trading plays say when to buy. Fewer say when to stop holding, and that's the decision that decides how much a bad stretch costs. The simplest sell rules look at two things anyone can check: how far a stock has fallen from its high, and whether it's still above its 200-day average, the line most trend plays use to tell an uptrend from a downtrend.",
          f"So we tested them. At the end of every month since {st['since'].year}, every covered stock was checked against five versions of the rule, and its next three months and next year were compared with its market.")}
<h2 class="h2">What happened next</h2>
</div>
{table}
<div class="prose">
{self.a_P(f"Stocks 25% or more off their high and below the 200-day beat their market over the next year {pc(b12, sign=False)} of the time, against {pc(rb12, sign=False)} for everything else, and {pc(b3, sign=False)} of the time over three months, against {pc(rb3, sign=False)}. The rule tilts the odds; it doesn't predict. Most flagged stocks carry on roughly in line with the market, and a few rebound hard.",
          reb, grade_p)}
<h2 class="h2">Why this test flatters holding on</h2>
{self.a_P("The test uses today's list of covered stocks. A company that fell 90% and was delisted isn't in it, so every stock that was ever flagged here survived. That makes holding through a fall look better than it was for the market as a whole: the losers that never came back are exactly the ones missing.")}
<h2 class="h2">Which covered stocks meet the 25% rule tonight</h2>
</div>
{now_tbl}
<div class="prose">
<h2 class="h2">Questions worth answering before a fall, not during one</h2>
<ul>
<li>What would make me sell this? Write it down when you buy, in numbers: a percentage off the high, a close under an average, or a signal turning to Sell.</li>
<li>If the rule fires and the stock doubles a year later, would I still follow it next time? A rule only helps if it's kept through the times it's wrong.</li>
<li>How much of the account is in the position the rule is watching? The <a href="{h('articles/one-stock-too-many/')}">concentration article</a> shows why that matters more than the rule itself.</li>
</ul>
<p>Be The Puck's <a href="{h('alerts/')}">alerts</a> email you when a stock's signal flips, and the <a href="{h('guides/your-plays/')}#your-signal">Plays + exit rule</a> weights lean hardest on Off the high and trend.</p>
</div>"""
        self.a.shell(path, b, title, dek, body, [("Be The Puck calculation from daily closes (Yahoo Finance)", "https://finance.yahoo.com/"),
                                                 ("Meb Faber, A Quantitative Approach to Tactical Asset Allocation", "https://papers.ssrn.com/abstract=962461"),
                                                 ("George & Hwang, The 52-Week High and Momentum Investing (Journal of Finance, 2004)", "https://doi.org/10.1111/j.1540-6261.2004.00695.x")],
                     live=True, related=self.a.related(depth, ["articles/one-stock-too-many/", "articles/why-your-signal-changed/", "articles/cash-or-invested/"]))

    def a_P(self, *paras):
        return "".join(f"<p>{x}</p>" for x in paras if x)

    def concentration(self):
        b, path, title, dek, _, _ = PIECES[1]
        depth = path.count("/")
        h = self.a.h(depth)
        R = portfolios(self.s)
        if not R:
            return
        st = study(self.s)
        rows = ""
        for n in SIZES:
            r = R[n]
            rows += (f'<tr><td>{n} stock{"s" if n > 1 else ""}, equal amounts</td><td class="r">{pc(r["lost30"], 1, sign=False)}</td><td class="r">{pc(r["lost"], sign=False)}</td>'
                     f'<td class="r">{pc(r["p5"])}</td><td class="r">{pc(r["median"])}</td><td class="r">{pc(r["p95"])}</td></tr>')
        if R.get("spx"):
            r = R["spx"]
            rows += (f'<tr><td>The S&amp;P 500</td><td class="r">{pc(r["lost30"], 1, sign=False)}</td><td class="r">{pc(r["lost"], sign=False)}</td>'
                     f'<td class="r">{pc(r["p5"])}</td><td class="r">{pc(r["median"])}</td><td class="r">{pc(r["p95"])}</td></tr>')
        table = self._tbl(["Portfolio, held one year", "Lost 30%+", "Lost money", "Bad year (1 in 20)", "Typical year", "Good year (1 in 20)"], rows,
                          f"{DRAWS:,} random portfolios per row, each bought at a random month-end from {st['since'].strftime('%b %Y')} on and held a year, from the {st['stocks']} covered stocks. Before fees, tax and currency.")
        r1, r20 = R[1], R[20]
        wf = worst_falls(self.s)
        wf_p = ""
        if wf:
            f50, f70, med, n = wf
            wf_p = (f"Over the same years, {pc(f50, sign=False)} of the {n} covered stocks fell 50% or more from a high at some point, and {pc(f70, sign=False)} fell 70% or more. "
                    f"The median stock's worst fall was {pc(med)}. The S&amp;P 500's worst was {pc(spx_worst(self.s))}.")
        body = f"""
<div class="prose">
{self.a_P("A signal can be right about a stock more often than not and still leave an account badly hurt, if most of the account sits in one name on the day it's wrong. That's not a flaw in any one signal; it's arithmetic. A position that is 60% of an account turns a 12% fall in the stock into a 7% fall in the account, in a week when the market may barely move.",
          "So how big is the risk of holding one stock, or a few? We drew thousands of random portfolios from the stocks Be The Puck covers and held each for a year.")}
<h2 class="h2">One stock against twenty</h2>
</div>
{table}
<div class="prose">
{self.a_P(f"A single covered stock lost 30% or more in {pc(r1['lost30'], 1, sign=False)} of its random years. Twenty stocks in equal amounts did it in {pc(r20['lost30'], 1, sign=False)}. The typical year barely changes with the number of stocks ({pc(r1['median'])} for one, {pc(r20['median'])} for twenty). What changes is the spread: a one-in-twenty bad year was {pc(r1['p5'])} for one stock and {pc(r20['p5'])} for twenty.",
          wf_p)}
<h2 class="h2">Why it flatters the single stock</h2>
{self.a_P("These are today's covered names, so every company in the draw survived to 2026. The ones that went bankrupt or were bought out at a low aren't there. Real single-stock risk is worse than this table shows. And stocks in the same industry fall together: five chipmakers behave more like one big position than like five.")}
<h2 class="h2">What people use to keep one position from deciding everything</h2>
<ul>
<li><b>A cap per position.</b> A fixed share of the account no single stock may exceed, trimmed back when a winner grows past it.</li>
<li><b>Sizing by the exit.</b> If you'd sell 20% below where you buy and accept losing 2% of the account on one idea, the position is at most 10% of the account.</li>
<li><b>A cap per theme.</b> Chips, crypto, rates: count names on one story as one position.</li>
<li><b>Rebalancing on a calendar.</b> Once a quarter or once a year, back to the targets, whatever the news. The <a href="{h('articles/cash-or-invested/')}">cash, invested or buckets</a> piece shows what rebalancing did through three crashes.</li>
</ul>
{self.a_P("Which cap is right depends on the money, the timeline and the person, which is why Be The Puck shows the trade-offs rather than a number for you.")}
</div>"""
        self.a.shell(path, b, title, dek, body, [("Be The Puck calculation from daily closes (Yahoo Finance)", "https://finance.yahoo.com/"),
                                                 ("Hendrik Bessembinder, Do Stocks Outperform Treasury Bills? (Journal of Financial Economics, 2018)", "https://doi.org/10.1016/j.jfineco.2018.06.004")],
                     live=True, related=self.a.related(depth, ["articles/when-to-sell/", "articles/cash-or-invested/", "articles/debt-and-crashes/"]))

    def signal_change(self):
        from . import factors as F
        from . import stockview as sv
        b, path, title, dek, _, _ = PIECES[2]
        depth = path.count("/")
        h = self.a.h(depth)
        pts = F.compute(self.s)
        grade = _grades(self.s)
        gf, gp = grade.get("factors") or {}, grade.get("presets") or {}
        fname = {k: n for k, n, _, _ in F.FACTORS}
        # names held to neutral tonight: upside above the cap, but below the 200-day
        capped = []
        for t in _stocks(self.s):
            ol = sv.outlook(self.s, t)
            p = (pts.get(t["sym"]) or {}).get("upside", (None, None))
            if ol.get("ok") and p[1] and "held to 50" in p[1]:
                capped.append((t, ol["upside"], int(round(100 * sv.upside_points(ol["upside"])))))
        capped.sort(key=lambda x: -x[1])
        cap_rows = "".join(f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                           f'<td class="r">{pc(u)}</td><td class="r">{raw}</td><td class="r">{F.UPSIDE_CAP}</td></tr>' for t, u, raw in capped[:30])
        cap_tbl = (self._tbl(["Stock", "To analysts' target", "Points before", "Points now"], cap_rows,
                             f"{len(capped)} covered stocks on the {self.s.asof.strftime('%b %-d')} close: below their 200-day average with analysts' upside worth more than {F.UPSIDE_CAP} points"
                             + ("; the 30 with the most upside are listed." if len(capped) > 30 else "."))
                   if capped else "")

        def frow(k):
            r = gf.get(k) or {}
            if r.get("why"):
                return f'<tr><td>{e(fname[k])}</td><td class="r">{F.DEFAULT.get(k, 0)}</td><td class="r muted">–</td><td class="small muted">Can\'t be graded: {e(r["why"])}.</td></tr>'
            y = r.get("12m")
            if not y:
                return f'<tr><td>{e(fname[k])}</td><td class="r">{F.DEFAULT.get(k, 0)}</td><td class="r muted">–</td><td class="small muted">Not graded in this build.</td></tr>'
            return (f'<tr><td>{e(fname[k])}</td><td class="r">{F.DEFAULT.get(k, 0)}</td><td class="r {"up" if y["edge"] > 0 else "down"}">{pts(y["edge"], True)} pts</td>'
                    f'<td class="small muted">Buys beat their market {pc(y["buys_beat"], sign=False)} of the time over a year, avoids {pc(y["avoids_beat"], sign=False)}.</td></tr>')
        ftbl = self._tbl(["Factor", "Standard weight", "Edge, 1 year", "Record since " + (grade.get("since") or "2011")[:4]],
                         "".join(frow(k) for k in ("plays", "dd", "trend", "upside", "mom")),
                         "Edge: how much more often the stocks a factor scored 60+ beat their market over the next year than the ones it scored 40 or less, in points. Today's covered stocks, every month-end, numbers public at the time.")

        def prow(k, n):
            r = gp.get(k) or {}
            y = r.get("12m")
            if not y:
                return ""
            return (f'<tr><td>{e(n)}</td><td class="r">{r.get("graded_weight", 100)}%</td><td class="r {"up" if y["edge"] > 0 else "down"}">{pts(y["edge"], True)} pts</td>'
                    f'<td class="r">{pc(y["buys_beat"], sign=False)}</td></tr>')
        prows = "".join(prow(k, n) for k, n, _ in F.PRESETS if k in ("default", "analysts", "exit", "plays"))
        ptbl = self._tbl(["Weights", "Share graded", "Edge, 1 year", "Buys beat market"], prows,
                         "Each mix graded on the factors that have a past record; analysts' upside has none, so a mix that leans on it is only partly tested.") if prows else ""
        body = f"""
<div class="prose">
{self.a_P("Until October 2026, Be The Puck's standard signal was half the share of plays that hold a stock and half how far analysts' average 12-month target sits above the price. That second half had a problem we hadn't tested for, because it can't be tested: there's no public record of past targets to grade it against.",
          "The problem is in how a target moves. Analysts revise slowly, so when a stock falls 15% in a week, the average target usually hasn't moved yet. The gap between price and target widens, and the upside score rises, purely because the price fell. A signal that leans on that number leans toward Buy the further a stock drops, until the targets catch up.")}
<h2 class="h2">What changed</h2>
<ul>
<li><b>New standard weights.</b> Plays {F.DEFAULT['plays']}, Off the high {F.DEFAULT['dd']}, Trend {F.DEFAULT['trend']}, Analysts' upside {F.DEFAULT['upside']}. Four-fifths of the call now rests on factors graded month by month since 2011.</li>
<li><b>A new factor, Off the high.</b> How far the price sits below its highest close of the past year, ranked against every covered stock. It's the part of the signal that turns a stock that keeps falling toward Sell. <a href="{h('articles/when-to-sell/')}">What the drawdown rules have done</a>.</li>
<li><b>Analysts' upside held to neutral in a downtrend.</b> While a stock is below its 200-day average, upside scores at most {F.UPSIDE_CAP} points, so a falling price can't lift the score through the targets.</li>
<li><b>The old mix is still there.</b> Pick <i>Plays + analysts</i> in the weights to get the 50/50 split back, or set your own. Alerts follow the new standard weights from October 13, 2026; the change itself didn't send any flip emails.</li>
</ul>
<h2 class="h2">Each standard factor's record</h2>
</div>
{ftbl}
{('<div class="prose"><h2 class="h2">The old mix and the new, graded</h2></div>' + ptbl) if ptbl else ""}
{('<div class="prose"><h2 class="h2">Where the new rule bites tonight</h2>' + self.a_P("These covered stocks are below their 200-day average with analysts' targets far enough above the price to have scored more than neutral under the old rule.") + '</div>' + cap_tbl) if cap_tbl else ""}
<div class="prose">
<h2 class="h2">What it still can't do</h2>
<ul>
<li><b>It works on closes.</b> The signal is rebuilt after the close twice a day; it doesn't see a fall during the session.</li>
<li><b>It scores one stock at a time.</b> It has no idea how much of an account a stock is. <a href="{h('articles/one-stock-too-many/')}">One stock, most of the money</a> covers that.</li>
<li><b>Every test uses today's covered stocks</b>, which flatters every factor alike, and an edge of a few points is a tilt in the odds, not a forecast.</li>
</ul>
</div>"""
        self.a.shell(path, b, title, dek, body, [("George & Hwang, The 52-Week High and Momentum Investing (Journal of Finance, 2004)", "https://doi.org/10.1111/j.1540-6261.2004.00695.x"),
                                                 ("Bradshaw, Brown & Huang, Do sell-side analysts exhibit differential target price forecasting ability? (Review of Accounting Studies, 2013)", "https://doi.org/10.1007/s11142-013-9225-0")],
                     live=True, related=self.a.related(depth, ["articles/when-to-sell/", "articles/one-stock-too-many/", "articles/green-across-the-board/"]))
