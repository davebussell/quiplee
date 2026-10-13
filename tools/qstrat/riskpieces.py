"""Three free pieces on risk and selling (October 13, 2026), rebuilt nightly from the site's data:

    articles/why-your-signal-changed/   the new standard weights, the exit rule and the upside cap, and what they changed
    articles/when-to-sell/              what happened after sharp drops, and the exit rules the signal now carries
    articles/one-stock-too-many/        what one big position does to an account, from every covered stock's history

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
<h2 class="h2">If you set your own weights</h2>
<p>Nothing you chose has changed. If you were simply on the old standard, you've been moved to the new one, and the weights panel says so; the old mix is still there as <b>Plays + analysts</b>. Alerts reset quietly with this change, so nobody gets an email about a "flip" that was really just the new weights.</p>
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
