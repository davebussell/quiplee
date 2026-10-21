"""Three free pieces on risk and selling (October 13, 2026), rebuilt nightly from the site's data:

    articles/why-your-signal-changed/   the new standard weights, the exit rule and the upside cap, and what they changed
    articles/when-to-sell/              what happened after sharp drops, and the exit rules the signal now carries
    articles/one-stock-too-many/        what one big position does to an account, from every covered stock's history
    articles/old-vs-new-signal/         the old and new standard signals tested side by side (modelcompare.py)

They're free (netlify/edge-functions/member-gate.js leaves them out of the paywall) because they
explain how the site's one verdict works. Every number is computed from data/prices and the
factor grading (factorgrade.py), and none of it refers to anyone's own holdings.
"""
import html

import numpy as np
import pandas as pd

from .content import TICKERS
from . import stockview as sv

e = html.escape
DATE = pd.Timestamp("2026-10-13")
SINCE = pd.Timestamp("2006-01-01")
PIECES = [
    ("articles/why-your-signal-changed/", "Why your signal changed on October 13",
     "The standard Buy, Hold and Sell now rest only on factors with a tested record, and they carry an exit rule. What changed, why, and how many stocks it moved."),
    ("articles/when-to-sell/", "When to sell: what an exit rule would have done",
     "A Buy is not a plan for getting out. What happened after thousands of sharp drops in the stocks we cover, and the three exit rules your signal now reads."),
    ("articles/one-stock-too-many/", "One stock too many: what concentration does to an account",
     "No signal on one stock can protect an account that rides on it. The arithmetic of a big position, and how often single stocks fall hard."),
    ("articles/calls-graded/", "This week's calls, graded",
     "How the signal's Buys, Holds and Sells did over the latest week, name by name, and its running record since the standard weights changed."),
    ("articles/old-vs-new-signal/", "Old signal vs new: the calls compared, and what we're testing next",
     "We rebuilt the old Buy, Hold and Sell from two years of analysts' price targets and ran it against the new one, and tested the new one back to 2006. Where the new signal is better, where the old one did better, and the refinements that held up."),
]
FREE = {p for p, _, _ in PIECES}


def _stocks(site):
    from .render import is_stock
    return [t for t in TICKERS if is_stock(t) and t["sym"] in (site.prices or {}) and not t.get("requested")
            and (t["sym"], "buy-and-hold") in site.R]


def pct(v, d=0, sign=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if sign and v > 0 else s)


def pts(v):
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f} pts"


def _cached(site, key, fn):
    got = site.__dict__.get(key)
    if got is None:
        got = site.__dict__[key] = fn()
    return got


# ------------------------------------------------------------------ the numbers
def old_signal(site, t):
    """The signal under the standard weights before October 13 (plays 50, analysts' upside 50, no cap)."""
    from .factors import _rnd, BUY, SELL
    k, n = site.consensus(t)
    parts = []
    if n:
        parts.append((50, _rnd(100 * k / n)))
    ol = sv.outlook(site, t)
    if ol["ok"]:
        parts.append((50, _rnd(100 * sv.upside_points(ol["upside"]))))
    avail = sum(w for w, _ in parts)
    if avail < 50:
        return None, None
    s = _rnd(sum(w * p for w, p in parts) / avail)
    return s, (1 if s >= BUY else -1 if s <= SELL else 0)


def signal_shift(site):
    """Old and new standard signal for every covered stock, fund and coin."""
    from .factors import score

    def run():
        rows = []
        for t in TICKERS:
            if (t["sym"], "buy-and-hold") not in site.R or t.get("requested"):
                continue
            s0, g0 = old_signal(site, t)
            s1, g1, _ = score(site, t)
            rows.append({"t": t, "s0": s0, "g0": g0, "s1": s1, "g1": g1})
        return rows
    return _cached(site, "_signal_shift", run)


def drop_study(site):
    """Every week since 2006 in which a covered stock fell 10% or more, and how it did against
    its market over the next 13 and 52 weeks, with what the setup looked like at the time."""
    def run():
        out = []
        for t in _stocks(site):
            c = site.prices[t["sym"]]["close"]
            b = site.prices.get(t["bench"], {})
            if not len(c) or "close" not in b:
                continue
            b = b["close"]
            wk = c.resample("W-FRI").last().dropna()
            bw = b.resample("W-FRI").last().reindex(wk.index).ffill()
            ma = c.rolling(200).mean().resample("W-FRI").last().reindex(wk.index)
            yr = wk.shift(52)
            r = wk.pct_change()
            v, bv = wk.values, bw.values
            for i in np.where((r.values <= -0.10) & (wk.index >= SINCE))[0]:
                if i + 52 >= len(wk) or i < 1:
                    continue
                run_up = v[i - 1] / yr.values[i - 1] - 1 if yr.values[i - 1] > 0 else np.nan
                out.append((t["sym"], wk.index[i], r.values[i], bv[i] / bv[i - 1] - 1,
                            (v[i + 13] / v[i] - 1) - (bv[i + 13] / bv[i] - 1), (v[i + 52] / v[i] - 1) - (bv[i + 52] / bv[i] - 1),
                            v[i + 13] / v[i] - 1, run_up, bool(v[i] > ma.values[i]) if ma.values[i] > 0 else None))
        return pd.DataFrame(out, columns=["sym", "d", "drop", "mkt", "ex13", "ex52", "ab13", "run", "above"])
    return _cached(site, "_drop_study", run)


def last_week_drops(site):
    """Covered stocks that fell 10% or more in the latest week, with their setup now."""
    out = []
    for t in _stocks(site):
        c = site.prices[t["sym"]]["close"]
        if len(c) < 260:
            continue
        wk = c.resample("W-FRI").last().dropna()
        if len(wk) < 2:
            continue
        r = wk.iloc[-1] / wk.iloc[-2] - 1
        if r <= -0.10:
            ma = float(c.iloc[-200:].mean())
            out.append({"t": t, "r": float(r), "run": float(c.iloc[-1 - 5] / c.iloc[-253] - 1) if len(c) > 260 else None,
                        "above": bool(c.iloc[-1] > ma), "off": float(c.iloc[-1] / c.iloc[-252:].max() - 1)})
    return sorted(out, key=lambda x: x["r"])


def conc_stats(site):
    def run():
        dd, wk10, yrs, vol = [], 0, 0.0, []
        for t in _stocks(site):
            c = site.prices[t["sym"]]["close"]
            c = c[c.index >= SINCE]
            if len(c) < 500:
                continue
            dd.append(float((c / c.cummax() - 1).min()))
            w = c.resample("W-FRI").last().pct_change().dropna()
            wk10 += int((w <= -0.10).sum())
            yrs += len(w) / 52
            vol.append(float(c.iloc[-756:].pct_change().std() * np.sqrt(252)))
        s = site.prices["^GSPC"]["close"]
        s = s[s.index >= SINCE]
        sw = s.resample("W-FRI").last().pct_change().dropna()

        def corr(group):
            syms = [t["sym"] for t in _stocks(site) if t["group"] == group]
            if len(syms) < 3:
                return None, 0
            df = pd.DataFrame({x: site.prices[x]["close"] for x in syms})
            df = df[df.index >= df.index[-1] - pd.Timedelta(days=3 * 365)].resample("W-FRI").last().pct_change().dropna(how="all")
            C = df.corr().values
            iu = np.triu_indices(len(syms), 1)
            return float(np.nanmean(C[iu])), len(syms)
        allsyms = [t["sym"] for t in _stocks(site)]
        df = pd.DataFrame({x: site.prices[x]["close"] for x in allsyms})
        df = df[df.index >= df.index[-1] - pd.Timedelta(days=3 * 365)].resample("W-FRI").last().pct_change().dropna(how="all")
        C = df.corr().values
        iu = np.triu_indices(len(allsyms), 1)
        dd = np.array(dd)
        return {"n": len(dd), "med_dd": float(np.median(dd)), "dd50": float((dd <= -0.5).mean()), "dd70": float((dd <= -0.7).mean()),
                "wk10": wk10 / yrs if yrs else None, "sp_dd": float((s / s.cummax() - 1).min()), "sp_wk10": int((sw <= -0.10).sum()),
                "sp_years": len(sw) / 52, "vol": float(np.median(vol)), "sp_vol": float(s.iloc[-756:].pct_change().std() * np.sqrt(252)),
                "corr": {g: corr(g) for g in ("Semiconductors", "Metals & mining", "Big tech", "Financials", "Energy & power")},
                "corr_all": float(np.nanmean(C[iu]))}
    return _cached(site, "_conc_stats", run)


# ------------------------------------------------------------------ the pieces
def build(A):
    """A: the articles.Articles instance (its shell, helpers and registry)."""
    why_changed(A)
    when_to_sell(A)
    one_stock(A)
    old_vs_new(A)
    from .scorecard import piece as scorecard
    scorecard(A)


def _grade(site):
    from .factorgrade import cached
    return cached(site)


def why_changed(A):
    s = A.s
    path, depth = PIECES[0][0], 2
    h = A.h(depth)
    from .factors import DEFAULT, OLD_DEFAULT, FACTORS, UPSIDE_CAP, OFFHIGH_FLOOR, SIG_WORD
    fname = {k: n for k, n, _, _ in FACTORS}
    g = _grade(s)
    gf, gp = g.get("factors", {}), g.get("presets", {})
    since = (g.get("since") or "2011")[:4]
    rows = signal_shift(s)
    word = {1: "Buy", 0: "Hold", -1: "Sell", None: "No score"}
    cnt0 = {k: sum(1 for r in rows if r["g0"] == k) for k in (1, 0, -1, None)}
    cnt1 = {k: sum(1 for r in rows if r["g1"] == k) for k in (1, 0, -1, None)}
    moved = [r for r in rows if r["g0"] != r["g1"]]
    down = sorted([r for r in moved if r["g0"] is not None and r["g1"] is not None and r["g1"] < r["g0"]], key=lambda r: (r["s1"] - r["s0"]))
    up_ = sorted([r for r in moved if r["g0"] is not None and r["g1"] is not None and r["g1"] > r["g0"]], key=lambda r: -(r["s1"] - r["s0"]))
    tbl = "".join(f'<tr><td>{word[k]}</td><td class="r">{cnt0[k]}</td><td class="r"><b>{cnt1[k]}</b></td></tr>' for k in (1, 0, -1, None))

    def lst(rs):
        return "".join(f'<li><a href="{h("stocks/" + r["t"]["slug"] + "/")}">{e(r["t"]["short"])}</a> <span class="muted small">{e(r["t"]["name"])}</span>: '
                       f'{word[r["g0"]]} {r["s0"]} → <b>{word[r["g1"]]} {r["s1"]}</b></li>' for r in rs[:10])
    y = lambda k, src: (src.get(k) or {}).get("12m") or {}
    new_r, old_r = y("default", gp), y("analysts", gp)
    off_r, tr_r, pl_r = y("offhigh", gf), y("trend", gf), y("plays", gf)
    mix = ", ".join(f"{fname[k].lower() if k != 'plays' else 'the plays'} {w}" for k, w in DEFAULT.items())
    from .modelcompare import load as _mc_load
    MC = (_mc_load() or {}).get("models") or {}
    mc_edge = lambda k: ((MC.get(k) or {}).get("all") or {}).get("edge12") or 0
    mc_flips = lambda k: (MC.get(k) or {}).get("flips") or 0
    # a worked example of the old upside problem: a stock falls while its target stays put
    ex_up0 = sv.upside_points(0.20)
    tgt_up_after = 1.20 / 0.85 - 1
    body = f"""<div class="prose">
<p>Until October 13, the standard signal on every stock was half the plays and half <b>analysts' upside</b>: how far their average 12-month target sat above the price. Two things were wrong with that, and a falling week showed both.</p>
<ul>
<li><b>Half the verdict had no record.</b> Every play on Be The Puck is graded against what happened next, and since this week every factor is too (<a href="{h('guides/your-plays/')}#your-signal">the edges are in the guide</a>). Analysts' targets can't be: no one keeps a record of past targets for every stock, so there's nothing to test them against. Half of the default Buy or Sell rested on a number we couldn't check.</li>
<li><b>It leaned the wrong way in a fall.</b> Targets move slowly. When a stock drops 15% in a week, the target usually hasn't changed yet, so the gap to it widens: if the target was 20% above the price, after a 15% fall it's {pct(tgt_up_after)} above, and the stock's upside points rise from {round(100 * ex_up0)} to {round(100 * sv.upside_points(tgt_up_after))}. The worse the week, the stronger that half of the score said Buy.</li>
<li><b>There was no exit rule.</b> Nothing in the standard weights took points away from a stock just because it kept falling. The plays do get out, one by one, but slowly, and analysts' upside pulled the other way.</li>
</ul>
<h2 class="h2">What changed</h2>
<ul>
<li><b>New standard weights:</b> {e(mix)}. Every one has a tested record since {since}.</li>
<li><b>A new factor, Off the high:</b> 100 points at the stock's highest close of the last year, falling in a straight line to none at {round(OFFHIGH_FLOOR * 100)}% below it. It doesn't rank stocks against each other, so in a broad sell-off every stock loses points. On its own it was the best-tested factor: over a year, stocks it scored 60 or more beat their market {pct(off_r.get('buys_beat'))} of the time, against {pct(off_r.get('avoids_beat'))} for those it scored 40 or less ({pts(off_r.get('edge', 0))}).</li>
<li><b>Trend</b> (the price against its 200-day average) carries the rest of the exit side: {pts(tr_r.get('edge', 0))} over a year.</li>
<li><b>Analysts' upside is capped</b> at {UPSIDE_CAP} points while a stock is below its 200-day average, wherever you use it, so a broken trend can't be talked up by a stale target.</li>
<li><b>Every signal says how much of it is tested.</b> Under the score on each stock page: "Every factor in this score has a tested record", or how much doesn't.</li>
</ul>
<h2 class="h2">The record, old and new</h2>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Standard weights</th><th class="r">Buys beat the market (1 year)</th><th class="r">Avoids beat it</th><th class="r">Edge</th><th>Tested</th></tr></thead><tbody>
<tr><td>Before: plays 50, analysts' upside 50</td><td class="r">{pct(old_r.get('buys_beat'))}</td><td class="r">{pct(old_r.get('avoids_beat'))}</td><td class="r">{pts(old_r.get('edge', 0))}</td><td>Only the plays half ({gp.get('analysts', {}).get('graded_weight', 50)}%)</td></tr>
<tr><td><b>Now: {e(mix)}</b></td><td class="r">{pct(new_r.get('buys_beat'))}</td><td class="r">{pct(new_r.get('avoids_beat'))}</td><td class="r"><b>{pts(new_r.get('edge', 0))}</b></td><td>All of it</td></tr>
</tbody></table></div>
<p class="small muted">Each month since {since}, every stock got its points from numbers public at the time; a Buy (60 or more) or an Avoid (40 or less) was then checked against the stock's market over the next year. The "before" row can only be graded on its plays half. Edges this size are normal and small: a better default tilts the odds a few points, it doesn't remove risk. The test uses today's list of covered stocks, which flatters every rule alike.</p>
<h2 class="h2">What it did to the signals tonight</h2>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Signal</th><th class="r">Old standard</th><th class="r">New standard</th></tr></thead><tbody>{tbl}</tbody></table></div>
<p>{len(moved)} of {len(rows)} names changed signal with the {s.asof.strftime('%b %-d')} close. {why_moved(s, down, up_)}</p>
{f'<p class="eyebrow">Moved down the most</p><ul class="flip-list">{lst(down)}</ul>' if down else ''}
{f'<p class="eyebrow">Moved up the most</p><ul class="flip-list">{lst(up_)}</ul>' if up_ else ''}
<h2 class="h2">October 21: two rules on top of the weights</h2>
<p>A week later, two of the refinements <a href="{h('articles/old-vs-new-signal/')}">tested month by month since 2006</a> went into the standard (model version 3). The <b>market guard</b>: while a stock's own market is 15% or more below its 1-year high, Off the high, Trend and 1-year momentum stand down and the rest of the weights decide, so the exit rule doesn't sell a whole market at its bottom; it lifted the 20-year edge from {pts(mc_edge("new"))} to {pts(mc_edge("guard"))} and changed nothing in calm years. <b>Sticky calls</b>, on the standard weights with every play counted: a Buy holds until the score drops below 50, a Sell until it rises above 50, which cut the flips from {mc_flips("guard"):.1f} to {mc_flips("guardsticky"):.1f} a year for a small cost in edge ({pts(mc_edge("guardsticky"))} for the two together). The stock page says when either rule is deciding, and the <a href="{h('articles/calls-graded/')}">weekly scorecard</a> grades each day by the rules in force that day.</p>
<h2 class="h2">If you set your own weights</h2>
<p>Nothing you chose has changed. If you were simply on the old standard, you've been moved to the new one, and the weights panel says so; the old mix is still there as <b>Plays + analysts</b>. The market guard applies to your weights too; the sticky rule only to the standard setup. Alerts reset quietly with each change, so nobody gets an email about a "flip" that was really just the new rules.</p>
<p>Your signal is a summary of the numbers you choose to weight, not a recommendation, and it knows nothing about your account. <a href="{h('articles/when-to-sell/')}">When to sell</a> and <a href="{h('articles/one-stock-too-many/')}">One stock too many</a> cover the two things it can't do for you.</p>
</div>"""
    A.shell(path, "risk", PIECES[0][1], PIECES[0][2], body, live=True, free=True,
            related=A.related(depth, [p for p, _, _ in PIECES[1:]]))


def why_moved(site, down, up_):
    """One or two sentences on what the names that moved have in common, from their numbers."""
    from .factors import compute
    pts = compute(site)

    def share(rs, test):
        rs = [r for r in rs if r["t"]["sym"] in pts]
        return (sum(1 for r in rs if test(pts[r["t"]["sym"]])) / len(rs)) if rs else None
    below = lambda p: (p.get("trend") or (None,))[0] is not None and (p.get("offhigh") or (None,))[0] is not None and (p["offhigh"][0] <= 33)
    no_an = lambda p: (p.get("upside") or (None,))[0] is None
    near = lambda p: (p.get("offhigh") or (None,))[0] is not None and p["offhigh"][0] >= 67
    out = []
    a = share(down, below)
    if a is not None:
        out.append(f"Of the {len(down)} that moved toward Sell, {pct(a)} were 20% or more below their 1-year high.")
    b, c = share(up_, near), share(up_, no_an)
    if b is not None:
        out.append(f"Of the {len(up_)} that moved toward Buy, {pct(b)} were within 10% of their high"
                   + (f", and {pct(c)} have fewer than three analysts, so the old standard scored them on the plays alone." if c else "."))
    return " ".join(out)


def when_to_sell(A):
    s = A.s
    path, depth = PIECES[1][0], 2
    h = A.h(depth)
    df = drop_study(s)
    g = _grade(s)
    off_r = ((g.get("factors") or {}).get("offhigh") or {}).get("12m") or {}
    tr_r = ((g.get("factors") or {}).get("trend") or {}).get("12m") or {}
    since = (g.get("since") or "2011")[:4]

    def row(x, label):
        if not len(x):
            return ""
        return (f'<tr><td>{label}</td><td class="r">{len(x):,}</td><td class="r">{pct((x.ex13 > 0).mean())}</td><td class="r">{pct((x.ex52 > 0).mean())}</td>'
                f'<td class="r">{pct(x.ex52.median(), d=0, sign=True)}</td><td class="r">{pct((x.ab13 < 0).mean())}</td></tr>')
    alone = df[df.mkt > -0.03]
    hot = df[df.run > 1.0]
    hot_broke = hot[hot.above == False]  # noqa: E712
    hot_held = hot[hot.above == True]  # noqa: E712
    rows = (row(df, "Every 10%+ weekly drop") + row(alone, "The market fell less than 3% that week") + row(df[df.mkt <= -0.03], "The market fell 3% or more too")
            + row(hot, "After the stock had more than doubled in a year") + row(hot_held, "… and it was still above its 200-day average")
            + row(hot_broke, "… and the drop took it below its 200-day average"))
    lw = last_week_drops(s)
    lw_rows = "".join(f'<tr><td><a class="sym" href="{h("stocks/" + x["t"]["slug"] + "/")}">{e(x["t"]["short"])}</a><span class="sym-sub">{e(x["t"]["name"])}</span></td>'
                      f'<td class="r down">{pct(x["r"], d=1)}</td><td class="r">{pct(x["off"], d=0)}</td><td class="r">{pct(x["run"], d=0, sign=True) if x["run"] is not None else "–"}</td>'
                      f'<td>{"above" if x["above"] else "<b>below</b>"}</td></tr>' for x in lw[:25])
    hb52 = (hot_broke.ex52 > 0).mean() if len(hot_broke) else None
    body = f"""<div class="prose">
<p>Most trading rules, and most of what people read about stocks, are about when to buy. The harder call is when to get out, and a Buy signal doesn't make it for you. This piece looks at what actually happened after sharp drops in the {df.sym.nunique() if len(df) else 0} stocks Be The Puck covers, and at the exit rules your signal now carries.</p>
<h2 class="h2">After a 10% week</h2>
<p>Since 2006 the covered stocks had {len(df):,} weeks in which they fell 10% or more. Here is how each kind did against its market (the S&amp;P 500, or the TSX for Canadian names) afterwards:</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>The drop</th><th class="r">Times</th><th class="r">Beat the market, 3 months</th><th class="r">Beat it, 1 year</th><th class="r">Median vs market, 1 year</th><th class="r">Fell further in 3 months</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>Three things stand out.</p>
<ul>
<li><b>A sharp drop on its own isn't a sell signal.</b> Taken together, stocks did about as well as their market afterwards, and better after market-wide crashes, because markets bounced back from 2008, 2020 and 2022. That flatters the drop: the stocks we test today are the ones that survived, and the ones that went to zero after a 10% week aren't in the list.</li>
<li><b>A drop of its own, in a calm market, was a coin flip</b> afterwards: the market didn't hand it back.</li>
<li><b>A drop after a big run that broke the trend was the warning.</b> When a stock that had more than doubled in a year fell 10% in a week and finished below its 200-day average, it beat its market over the next year only {pct(hb52)} of the time{f", lagging by a median {pct(-hot_broke.ex52.median())}" if len(hot_broke) and hot_broke.ex52.median() < 0 else ""}. While the trend held, the same drop was close to a coin flip.</li>
</ul>
<h2 class="h2">The exit rules in your signal</h2>
<ol>
<li><b>Off the high</b> (new): points fall as the price falls below its 1-year high, to none at 30% below. Tested monthly since {since}, stocks it scored low beat their market over the next year {pct(off_r.get('avoids_beat'))} of the time, against {pct(off_r.get('buys_beat'))} for those near their highs.</li>
<li><b>Trend</b>: the price against its 200-day average, ranked across every covered stock ({pts(tr_r.get('edge', 0))} over a year). It's the line the table above says mattered most after a big run.</li>
<li><b>The plays' own exits.</b> Every play that holds a stock has a price where it gets out, on each stock page under "Next move", and every stock brief lists the nearest one.</li>
</ol>
<p>Both price rules are in the <a href="{h('articles/why-your-signal-changed/')}">new standard weights</a>, so a stock that keeps falling now loses points whatever its analysts say. None of them can tell you whether a drop is the start of something or noise; they tell you how drops like it have played out.</p>
<h2 class="h2">The latest week's 10% drops</h2>
{f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">The week</th><th class="r">From 1-year high</th><th class="r">1 year before</th><th>200-day average</th></tr></thead><tbody>{lw_rows}</tbody></table></div><p class="small muted">Weeks end on Friday; the latest week may be partial. Each stock page has the full picture.</p>' if lw_rows else '<p>No covered stock fell 10% or more in the latest week.</p>'}
</div>"""
    A.shell(path, "risk", PIECES[1][1], PIECES[1][2], body, live=True, free=True,
            related=A.related(depth, [PIECES[0][0], PIECES[2][0]]))


def one_stock(A):
    s = A.s
    path, depth = PIECES[2][0], 2
    h = A.h(depth)
    C = conc_stats(s)
    falls = (0.10, 0.20, 0.40, 0.70)
    weights = (0.10, 0.25, 0.50, 0.75)
    grid = "".join(f'<tr><td>{pct(w)} of the account</td>' + "".join(f'<td class="r">{pct(-w * f, d=1)}</td>' for f in falls) + '</tr>' for w in weights)
    corr = C["corr"]
    corr_rows = "".join(f'<tr><td>{e(g)}</td><td class="r">{n}</td><td class="r">{v:.2f}</td></tr>' for g, (v, n) in corr.items() if v is not None)
    body = f"""<div class="prose">
<p>A signal is about one stock. An account is about all of them together, and how much of it rides on each. No Buy, Hold or Sell, however good, can keep an account steady when most of it sits in one or two stocks and those stocks have a bad week. This piece is about the arithmetic, using the price history of every stock Be The Puck covers.</p>
<h2 class="h2">The arithmetic</h2>
<p>An account moves by each position's share times that position's move. A stock that's half the account and falls 20% takes 10% off the whole account by itself, whatever everything else does:</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>One stock is…</th>{''.join(f'<th class="r">It falls {pct(f)}</th>' for f in falls)}</tr></thead><tbody>{grid}</tbody></table></div>
<p class="small muted">The change in the whole account from that one stock alone.</p>
<h2 class="h2">How often single stocks fall hard</h2>
<ul>
<li>A typical covered stock had a week of 10% or worse about <b>{C['wk10']:.1f} times a year</b> since 2006. The S&amp;P 500 had {C['sp_wk10']} such weeks in {C['sp_years']:.0f} years.</li>
<li><b>{pct(C['dd50'])}</b> of the {C['n']} stocks with that history fell 50% or more from a peak at some point, and <b>{pct(C['dd70'])}</b> fell 70% or more. The median stock's worst fall was {pct(C['med_dd'])}. The S&amp;P 500's worst, in 2008–09, was {pct(C['sp_dd'])}.</li>
<li>Over the last three years the median stock swung about <b>{pct(C['vol'])}</b> a year (annualised volatility), against {pct(C['sp_vol'])} for the S&amp;P 500.</li>
</ul>
<p>And these are the survivors: stocks that went to zero aren't on the list, so the real history of single stocks is worse.</p>
<h2 class="h2">Two stocks in the same business are close to one</h2>
<p>Owning several stocks only spreads the risk if they don't fall together. Within a sector they often do. The average correlation of weekly moves over the last three years (1 means they move together every week, 0 means no relation):</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Covered stocks in</th><th class="r">Stocks</th><th class="r">Average correlation</th></tr></thead><tbody>{corr_rows}
<tr><td>Any two covered stocks</td><td class="r">–</td><td class="r">{C['corr_all']:.2f}</td></tr></tbody></table></div>
<p>Two chip stocks, two gold miners or two bitcoin-linked stocks tend to have their bad weeks together.</p>
<h2 class="h2">What Be The Puck does about it</h2>
<ul>
<li>If you load your holdings into the <a href="{h('watchlist/')}">watchlist</a> with quantities or values, it now says when one name is a quarter or more of the list, and what a 20% fall in it alone would do. That stays in your browser.</li>
<li>The signal now carries exit rules (<a href="{h('articles/when-to-sell/')}">when to sell</a>), so a falling stock loses points. That helps with the stock, not with how much of an account it is.</li>
</ul>
<p>How much to put in any one name depends on your goals, your timeline and what else you own, which Be The Puck doesn't know. It's the kind of question an advisor is for.</p>
</div>"""
    A.shell(path, "risk", PIECES[2][1], PIECES[2][2], body, live=True, free=True,
            related=A.related(depth, [PIECES[0][0], PIECES[1][0]]))


# ------------------------------------------------------------------ old vs new, tested
def _year_chart(years, label):
    """A small bar chart of the 12-month edge by year (positive up, negative down), with the numbers underneath."""
    ys = [(y, v) for y, v in years.items() if v is not None]
    if not ys:
        return ""
    m = max(0.25, max(abs(v) for _, v in ys))
    cols = "".join(f'<div class="yb-col" title="{y}: {pts(v)}"><div class="yb-top">{f"""<i class="yb-up" style="height:{100 * v / m:.0f}%"></i>""" if v >= 0 else ""}</div>'
                   f'<div class="yb-bot">{f"""<i class="yb-down" style="height:{100 * -v / m:.0f}%"></i>""" if v < 0 else ""}</div>'
                   f'<span class="yb-lab">{"’" + y[2:]}</span></div>' for y, v in ys)
    rows = "".join(f'<tr><td>{y}</td><td class="r">{pts(v)}</td></tr>' for y, v in ys)
    return (f'<div class="yb" role="img" aria-label="{e(label)}" style="--n:{len(ys)}">{cols}</div>'
            f'<details class="small"><summary>The numbers, year by year</summary><div class="tbl-wrap"><table class="tbl" data-nosort>'
            f'<thead><tr><th>Calls made in</th><th class="r">Edge over the next year</th></tr></thead><tbody>{rows}</tbody></table></div></details>')


def _and(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def _times(r):
    return "twice" if 1.8 <= r < 2.2 else "three times" if 2.8 <= r < 3.2 else f"{r:.1f} times"


def old_vs_new(A):
    from .modelcompare import load
    s = A.s
    path, depth = PIECES[4][0], 2
    h = A.h(depth)
    J = load()
    M = J.get("models") or {}
    rows = signal_shift(s)
    word = {1: "Buy", 0: "Hold", -1: "Sell"}
    ct = {(a, b): sum(1 for r in rows if r["g0"] == a and r["g1"] == b) for a in (1, 0, -1) for b in (1, 0, -1)}
    scored = sum(ct.values())
    cross = "".join(f'<tr><td>Old: <b>{word[a]}</b></td>' + "".join(f'<td class="r">{"<b>" if a == b else ""}{ct[(a, b)]}{"</b>" if a == b else ""}</td>' for b in (1, 0, -1))
                    + f'<td class="r">{sum(ct[(a, b)] for b in (1, 0, -1))}</td></tr>' for a in (1, 0, -1))
    same = sum(ct[(a, a)] for a in (1, 0, -1))
    live = f"""<h2 class="h2">Tonight's calls, old and new</h2>
<p>On the {s.asof.strftime('%B %-d')} close, the two signals agree on {same} of the {scored} names both can score ({pct(same / scored) if scored else '–'}). The old signal called {ct[(1, -1)]} stocks a Buy that the new one calls a Sell, and {ct[(-1, 1)]} a Sell that it now calls a Buy.</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th></th><th class="r">New: Buy</th><th class="r">New: Hold</th><th class="r">New: Sell</th><th class="r">All</th></tr></thead><tbody>{cross}
<tr><td>All</td>{"".join(f'<td class="r">{sum(ct[(a, b)] for a in (1, 0, -1))}</td>' for b in (1, 0, -1))}<td class="r">{scored}</td></tr></tbody></table></div>
<p class="small muted">Rows are the old standard (plays 50, analysts' upside 50), columns the new one, on tonight's numbers. The <a href="{h('articles/why-your-signal-changed/')}">names that moved most</a> are listed with the change.</p>"""
    if not M:
        body = f'<div class="prose">{live}</div>'
        A.shell(path, "risk", PIECES[4][1], PIECES[4][2], body, live=True, free=True,
                related=A.related(depth, [p for p, _, _ in PIECES[:3]]))
        return
    g = lambda k, part="all": (M.get(k) or {}).get(part) or {}
    nw, pl, old, oc = g("new"), g("plays"), g("old", "an"), g("oldcap", "an")
    since, to12 = J["since"][:4], pd.Timestamp(J["to12"]).strftime("%B %Y")
    an_from, an_to = pd.Timestamp(J["an_since"]).strftime("%B %Y"), pd.Timestamp(J["to"]).strftime("%B %Y")
    uc = J.get("upside_check") or {}

    def row(label, r, extra=""):
        b, sl = r.get("buy") or {}, r.get("sell") or {}
        return (f'<tr><td>{label}</td><td class="r">{pct(b.get("beat12"))}</td><td class="r">{pct(sl.get("beat12"))}</td><td class="r">{pts(r.get("edge12") or 0)}</td>'
                f'<td class="r">{pct(b.get("fell30"))}</td><td class="r">{pct(sl.get("fell30"))}</td>{extra}</tr>')
    gsa = g("guardsticky")
    t_all = ((row("<b>Today's standard</b>: the October 13 weights with the market guard and sticky calls (from October 21)", gsa, f'<td class="r">{M["guardsticky"]["flips"]:.1f}</td>') if gsa else "")
             + row("<b>The October 13 weights</b>: plays 40, off the high 30, trend 30", nw, f'<td class="r">{M["new"]["flips"]:.1f}</td>')
             + row("Plays only", pl, f'<td class="r">{M["plays"]["flips"]:.1f}</td>'))
    era = lambda k, e_: (M.get(k) or {}).get(e_, {}).get("edge12")
    eras = "".join(f'<tr><td>{lab}</td><td class="r">{pts(era("new", k) or 0)}</td><td class="r">{pts(era("plays", k) or 0)}</td></tr>'
                   for k, lab in (("e1", "2006–2010 (the financial crisis)"), ("e2", "2011–2018"), ("e3", "2019–2025")))
    yrs = M["new"].get("years") or {}
    t_an = (row("Old: plays 50, analysts' upside 50", old) + row("Old, with the upside cap", oc)
            + row("<b>New</b>", g("new", "an")) + row("Plays only", g("plays", "an")))
    d = J.get("disagree") or {}
    ob, os_ = d.get("oldbuy_newsell") or {}, d.get("oldsell_newbuy") or {}
    fa, fa_p = g("new", "fall"), g("plays", "fall")
    ofa = g("old", "an_fall")
    # the refinements tried
    order = [("guardsticky", "Today's standard (from October 21): market guard and sticky calls"), ("new", "The October 13 weights alone"),
             ("guard", "Market guard only: the plays alone while the market is 15%+ off its high"), ("sticky", "Sticky calls only: a call holds until the score crosses 50"),
             ("offrel", "Exit rule measured against the market's own fall"), ("relsticky", "That, with sticky calls"),
             ("off20", "Exit rule at 20% off the high"), ("off40", "Exit rule at 40% off the high"), ("offvol", "Exit rule scaled to each stock's volatility"),
             ("mom121", "12-month momentum, skipping the last month, for trend"), ("quality", "Adding return on equity and debt"),
             ("mktfilter", "A Buy needs 70 while the S&P 500 is below its 200-day"),
             ("trend50", "Faster: trend measured against the 50-day average"), ("trendx", "Faster: trend capped at 40 once under the 50-day"),
             ("off20x", "Faster: exit at 20% off the high, trend capped under the 50-day"), ("off3m", "Faster: exit off the 3-month high (15% floor)"),
             ("halfhalf", "Faster: half 1-year and 200-day, half 3-month and 50-day")]
    crash = lambda k: [(M.get(k) or {}).get("years", {}).get(y) for y in ("2008", "2020", "2022")]

    def rrow(k, lab):
        m_ = M.get(k) or {}
        a = m_.get("all") or {}
        if not a:
            return ""
        c = [x for x in crash(k) if x is not None]
        return (f'<tr><td>{"<b>" if k == "guardsticky" else ""}{e(lab or m_.get("label", k))}{"</b>" if k == "guardsticky" else ""}</td><td class="r">{pts(a.get("edge12") or 0)}</td>'
                f'<td class="r">{pts(era(k, "e3") or 0)}</td><td class="r">{pts(sum(c) / len(c)) if c else "–"}</td>'
                f'<td class="r">{pct((a.get("sell") or {}).get("fell30"))}</td><td class="r">{m_.get("flips", 0):.1f}</td></tr>')
    t_ref = "".join(rrow(k, lab) for k, lab in order)
    up15, rv15 = g("upside15", "an"), g("rev15", "an")
    gd, gs = M.get("guard") or {}, M.get("guardsticky") or {}
    body = f"""<div class="prose">
<p>On October 13 the standard Buy, Hold and Sell changed: from half the plays and half analysts' upside to the plays, an exit rule (<b>Off the high</b>) and the trend (<a href="{h('articles/why-your-signal-changed/')}">what changed and why</a>). The case for it was a test of how often each signal's Buys beat the market. This piece tests the change harder: back to {since}, on how badly things went as well as how often, and against the old signal itself, rebuilt from analysts' price targets for the stretch where we have them. Not all of it flatters the new signal. On October 21 the two best ideas from the tests at the end, a <b>market guard</b> and <b>sticky calls</b>, went into the standard (model version 3); the <a href="{h('articles/calls-graded/')}">weekly scorecard</a> grades every day's calls from here.</p>
{live}
<h2 class="h2">Since {since}: how often, and how badly</h2>
<p>At every month-end since {since}, each covered stock was scored exactly as the signal would have scored it then, from prices and the plays' calls up to that close. Each Buy and Sell was then checked against the stock's market (the S&amp;P 500, or the TSX for Canadian names) over the next year, and against how far the stock fell in that year. "Plays only" is the half of the old signal that can be tested this far back. "Fell 30%+" means the stock was 30% or more below the day of the call at some point in the following year; "flips a year" is how often a stock's call changed, per stock per year.</p>
<div class="tbl-wrap"><table class="tbl ovn" data-nosort><thead><tr><th>Signal</th><th class="r">Buys beat market</th><th class="r">Sells beat it</th><th class="r">Edge</th><th class="r">Buys fell 30%+</th><th class="r">Sells fell 30%+</th><th class="r">Flips a year</th></tr></thead><tbody>{t_all}</tbody></table></div>
<ul>
<li><b>The exit rule does its main job.</b> A stock the October 13 weights called Sell was {_times(nw['sell']['fell30'] / nw['buy']['fell30'])} as likely as a Buy to fall 30% or more at some point in the following year ({pct(nw['sell']['fell30'])} against {pct(nw['buy']['fell30'])}). The worst tenth of its Sells trailed the market by {pct(-nw['sell']['p10'])} or more over the year; the worst tenth of its Buys by {pct(-nw['buy']['p10'])} or more.</li>
<li><b>How often it's right barely moved.</b> The edge, how much more often Buys beat the market than Sells, is {pts(nw['edge12'])} for the October 13 weights against {pts(pl['edge12'])} for the plays alone{f", and {pts(gsa['edge12'])} with the market guard and sticky calls" if gsa else ""}. Many Sells still beat the market: beaten-down stocks often bounce, and the ones that went to zero aren't in today's list to count against them.</li>
<li><b>It changes its mind less.</b> {M['new']['flips']:.1f} changes per stock per year for the October 13 weights, against {M['plays']['flips']:.1f} for the plays alone{f"; the sticky calls bring it to {M['guardsticky']['flips']:.1f}" if gsa else ""}.</li>
</ul>
<h2 class="h2">It depends on the market</h2>
<div class="tbl-wrap"><table class="tbl ovn" data-nosort><thead><tr><th>Calls made in</th><th class="r">New signal's edge</th><th class="r">Plays only</th></tr></thead><tbody>{eras}</tbody></table></div>
{_year_chart(yrs, "The new signal's edge over the following year, by the year the calls were made")}
<p>Calls made in {_and([f"{y} ({pts(yrs[y])})" for y in ("2008", "2020", "2022", "2025") if yrs.get(y) is not None])} did badly: in each of those years a sharp, broad fall was followed by a fast rebound. An exit rule turns stocks to Sell after they've fallen, so when the whole market falls and snaps back, it sells close to the bottom and misses the bounce. In years with a steadier trend it did well. Since 2019 its edge on how often it's right has been about zero, though its Sells were still the ones more likely to fall hard ({pct(M['new']['e3']['sell']['fell30'])} against {pct(M['new']['e3']['buy']['fell30'])} for Buys).</p>
<h2 class="h2">The old signal, rebuilt</h2>
<p>There's no stored history of analysts' consensus targets, which is why the old signal couldn't be tested. But rating changes with price targets are on file from late 2023, so from {an_from} we rebuilt it: each firm's latest target in the past year, averaged over three or more firms{f", for {J['an_stocks']} stocks" if J.get('an_stocks') else ""}. It's an approximation: on tonight's numbers the rebuilt upside and the published consensus agree closely (correlation {uc.get('corr', 0):.2f}, a median gap of {pct(uc.get('med_gap'))}), but not exactly. Year-ahead results run to calls made in {to12}; three-month results to {an_to}.</p>
<div class="tbl-wrap"><table class="tbl ovn" data-nosort><thead><tr><th>Signal, {an_from} on</th><th class="r">Buys beat market</th><th class="r">Sells beat it</th><th class="r">Edge</th><th class="r">Buys fell 30%+</th><th class="r">Sells fell 30%+</th></tr></thead><tbody>{t_an}</tbody></table></div>
<p><b>In this stretch the old signal did better.</b> Its Buys beat its Sells over the following year; the new signal's didn't. Over three months the two were close (edges of {pts(old.get('edge3') or 0)} and {pts(g('new', 'an').get('edge3') or 0)}).</p>
<p>The clearest test is where they disagreed. {ob.get('n', 0):,} times a stock was a Buy under the old signal and a Sell under the new one, typically {pct(-(ob.get('dd') or 0))} below its 1-year high. Those stocks beat their market over the next year {pct(ob.get('beat12'))} of the time, by a median {pct(ob.get('med12'), sign=True)}. The reverse case ({os_.get('n', 0):,} times, old Sell and new Buy) beat it {pct(os_.get('beat12'))} of the time, by a median {pct(os_.get('med12'), sign=True)}.</p>
<p>That stretch had one sharp V: the April 2025 tariff sell-off and its rebound, the kind of market where an exit rule costs the most and where analysts' targets, which barely moved, pointed at the recovery. It's also only about fifteen months of year-ahead results, with no long bear market in it. It's a real result, not a verdict.</p>
<h2 class="h2">Stocks already 20% off their high</h2>
<p>This is where the two disagree most. Since {since}, the new signal called {pct(fa['sell']['share'])} of these Sell and almost none Buy; the plays alone called {pct(fa_p['sell']['share'])} Sell. Over the next year {pct(fa['sell']['fell30'])} of those Sells fell another 30% or more at some point, and {pct(fa['sell']['beat12'])} still beat their market.</p>
<p>From {an_from}, the old signal called {pct(ofa.get('buy', {}).get('share'))} of stocks this far down a Buy. Those Buys beat their market {pct(ofa.get('buy', {}).get('beat12'))} of the time, a median {pct(ofa.get('buy', {}).get('med12'), sign=True)}, but {pct(ofa.get('buy', {}).get('fell30'))} fell another 30% or more first. Buying the fall paid on the typical stock and hurt badly on a third of them; the exit rule gives up some of the first to avoid the second.</p>
<h2 class="h2">The refinements tested, and the two that went in</h2>
<p>Each idea below was scored the same way, month by month since {since}. "Crash years" is the average edge for calls made in 2008, 2020 and 2022. The first two are now the standard: since October 21 the signal carries the market guard and sticky calls (model version 3).</p>
<div class="tbl-wrap"><table class="tbl ovn" data-nosort><thead><tr><th>Change</th><th class="r">Edge since {since}</th><th class="r">Since 2019</th><th class="r">Crash years</th><th class="r">Sells fell 30%+</th><th class="r">Flips a year</th></tr></thead><tbody>{t_ref}</tbody></table></div>
<ul>
<li><b>The market guard (in the standard since October 21).</b> When the stock's whole market is 15% or more below its own high, the exit rule and the trend stand down and the plays decide. It lifts the edge to {pts(gd.get('all', {}).get('edge12') or 0)} by doing less damage in 2008, 2020 and 2022, and changes nothing in calmer years. It applies to every set of weights: Off the high, Trend and 1-year momentum carry no weight while it's on, and the stock page says so.</li>
<li><b>Sticky calls (in the standard since October 21).</b> A Buy stays a Buy until the score falls below 50 (and a Sell until it rises above 50), so signals change {gs.get('flips', 0):.1f} times a year instead of {gd.get('flips', 0):.1f} with the guard alone, for {pts((gs.get('all', {}).get('edge12') or 0) - (gd.get('all', {}).get('edge12') or 0))} of edge. Fewer flips means fewer alerts that reverse a month later. The rule needs a day-by-day history of the score, which only the standard setup has (the standard weights with every play counted); a stock page with its own weights uses the plain Buy and Sell lines.</li>
<li><b>Analysts' upside, capped, at a small weight</b> was the best of the additions in the rebuilt stretch over three months ({pts(up15.get('edge3') or 0)}, against {pts(g('new', 'an').get('edge3') or 0)} for the new signal), but two years is too short to put it back. Analysts' target revisions (raised or cut in the last 90 days) added nothing ({pts(rv15.get('edge3') or 0)}). We keep collecting targets so both can be graded properly.</li>
<li><b>Faster exits don't pay over the long run.</b> After the week of October 13–19, when a stock that had quadrupled sat at Hold while it fell 25% from its high (its 200-day average was still far below), we tested five faster versions: trend on the 50-day average, trend capped once the price breaks its 50-day, a 20% exit floor, an exit off the 3-month high, and a half-and-half. Each would have called that stock Sell a week sooner. Over 20 years every one has a lower edge than today's standard ({pts((M.get("trend50") or {}).get("all", {}).get("edge12") or 0)} to {pts((M.get("trendx") or {}).get("all", {}).get("edge12") or 0)}) and 5–25% more flips: they leave the stocks that keep falling sooner and get whipsawed on the ones that bounce. Each stock page now shows the price at which the signal would turn instead.</li>
<li><b>Small or mixed:</b> moving the exit rule's floor to 20% or 40%, scaling it to each stock's volatility, using 12-month momentum (skipping the latest month) for the trend, adding return on equity and debt, or asking for a 70 to Buy while the S&amp;P 500 is below its 200-day average each land within half a point of today's standard over the whole period; some do better in one stretch and worse in another. Measuring the fall against the market's own fall raised the overall edge but made the crash years worse.</li>
</ul>
<p>Two things would make every one of these tests more honest, and both are on the list: <b>stocks that no longer trade</b> (the test uses today's list, which flatters buying dips and hides the cases an exit rule exists for), and a <b>longer record of analysts' targets</b> and of companies' guidance, which the site has started keeping. Any change to the standard will be published here with its record first.</p>
<h2 class="h2">The fine print</h2>
<p class="small muted">Study run {J.get('built')} on {J.get('stocks')} covered stocks, month-ends {since} to {an_to}, with each stock scored from data public at the time. "Beat the market" compares the stock's return over the next year with its market's. Edges of a few points are normal and noisy; a year can swing by twenty. The rebuilt old signal uses targets that aren't split-adjusted, so any target more than double or less than half the price on its day is dropped. None of this knows anything about an individual account, and a better signal doesn't make one stock a safe place for most of one (<a href="{h('articles/one-stock-too-many/')}">one stock too many</a>).</p>
</div>"""
    A.shell(path, "risk", PIECES[4][1], PIECES[4][2], body, live=True, free=True,
            related=A.related(depth, [PIECES[3][0]] + [p for p, _, _ in PIECES[:3]]))
