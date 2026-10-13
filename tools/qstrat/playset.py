"""Choose the plays that count.

Every count on Be The Puck (how many plays hold a stock, the home screener, the stock
list and its score, each stock page, the watchlist and My Puck) can use only the plays
a reader picks. assets/plays.js keeps the choice (this browser, or the account when
signed in) and draws the chooser; it reads data/playset.json, written here:

  plays[i]  {s: slug, n: name, f: family, a: share of calls right on the real stocks,
             c: finished calls, k: stocks with a finished call, e: 1 if it can be ranked,
             t: 1 if it is its family's most accurate}
  t[sym]    every covered name's call on every play, one character per play in the
            order of plays: 1 in, 0 out, - no call
  fx, fg, wp, wd, x[sym], v[sym]   the factors a reader can weight (tools/qstrat/factors.py):
            their names and groups, the ready-made weightings, the defaults, and every
            name's points (0-100) and shown value on each factor, in the order of fx

/guides/your-plays/ explains it to readers: how a play is graded, the Mayer Multiple,
every play by how often it was right, and the three steps to use the filter.
"""
import html
import json

from .content import TICKERS, TIMED, FAMILIES, FAMILY
from .render import (universe, is_stock, n_stocks, rankable, pct, dlong, fill_bar, GRADE_YEAR, TOP_MIN_CALLS, DISCLAIMER, ps_bar)
from .icons import icon

e = html.escape
PRESETS = [("top1", "Most accurate in each family"), ("top3", "Top 3 in each family"), ("half", "Right more than half the time"), ("all", "All plays")]


def playset_json(site):
    ns = n_stocks()
    top = {p["slug"] for _, p, _ in site.top_plays()}
    plays = []
    for p in TIMED:
        a = site.play_accuracy(p)
        d = {"s": p["slug"], "n": p["name"], "f": p["family"], "a": None if a["bat"] is None else round(a["bat"], 4),
             "c": a["calls"], "k": a["stocks"], "e": 1 if rankable(a, ns) else 0}
        if p["slug"] in top:
            d["t"] = 1
        plays.append(d)
    t = {}
    for x in TICKERS:
        sym = x["sym"]
        if (sym, "buy-and-hold") not in site.R:
            continue
        t[sym] = "".join("-" if site.R.get((sym, p["slug"])) is None or site.R[(sym, p["slug"])]["state"] is None
                         else str(site.R[(sym, p["slug"])]["state"]) for p in TIMED)
    from .factors import factors_json
    out = {"asof": site.asof.strftime("%Y-%m-%d"), "since": GRADE_YEAR, "n": ns, "min": TOP_MIN_CALLS,
           "fams": [[k, name] for k, name, _ in FAMILIES], "plays": plays, "t": t}
    out.update(factors_json(site))
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def signal_section(site, h):
    """The guide's Your signal section: what each factor measures and scores, the ready-made weightings, a worked example."""
    from .factors import FACTORS, GROUPS, PRESETS, BUY, SELL, score, SIG_WORD
    gname = dict(GROUPS)
    from .factorgrade import cached
    grade = cached(site)
    gf, gp = grade.get("factors", {}), grade.get("presets", {})

    def ptx(v):
        """An edge in percentage points: "+4.4 pts"."""
        return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f} pts"

    def edge_cells(r):
        if not r or r.get("why"):
            return f'<td class="r muted" data-v="">–</td><td class="r muted" data-v="">–</td>', f'Not graded: {e((r or {}).get("why", "no history"))}.'
        y, q = r.get("12m") or {}, r.get("3m") or {}
        ey, eq = y.get("edge"), q.get("edge")
        cls = lambda v: "up" if v is not None and v >= 0.03 else ("down" if v is not None and v <= 0 else "")
        return (f'<td class="r {cls(eq)}" data-v="{eq if eq is not None else ""}">{ptx(eq) if eq is not None else "–"}</td>'
                f'<td class="r {cls(ey)}" data-v="{ey if ey is not None else ""}"><b>{ptx(ey) if ey is not None else "–"}</b></td>'), \
            f'Over a year its Buys beat the market {round(100 * y["buys_beat"])}% of the time, its Avoids {round(100 * y["avoids_beat"])}%.'
    def frow(k, n, g, d):
        cells, rec_txt = edge_cells(gf.get(k))
        return f'<tr><td><b>{e(n)}</b><span class="sym-sub">{e(gname[g])}</span></td>{cells}<td class="small">{e(d)}<span class="sym-sub">{rec_txt}</span></td></tr>'
    rows = "".join(frow(k, n, g, d) for k, n, g, d in FACTORS)
    fname = {k: n for k, n, _, _ in FACTORS}
    graded = sorted([(k, n, gf[k]["12m"]["edge"]) for k, n, _, _ in FACTORS if gf.get(k, {}).get("12m")], key=lambda z: -z[2])
    low = lambda n: n if n == "P/E" else n[0].lower() + n[1:]
    best = ", ".join(f"{low(n)} ({ptx(v)})" for _, n, v in graded[:3])
    worst = [(low(n), v) for _, n, v in graded if v <= 0]
    since = grade.get("since", "")[:4]
    pbest = max(((k, n, gp[k]["12m"]["edge"]) for k, n, _ in PRESETS if (gp.get(k) or {}).get("12m")), key=lambda z: z[2], default=None)
    finding = ""
    if graded:
        finding = (f'<p><b>How each factor has done.</b> Every month since {since}, each stock got its points on each factor from the numbers public at the time '
                   f'(prices, the plays\' calls, and company figures as filed with the SEC), then we checked whether it beat its market over the next three months and the next year. '
                   f'The <b>edge</b> is how much more often a factor\'s Buys (60 points or more) beat the market than its Avoids (40 or less). '
                   f'The strongest over a year: {e(best)}.'
                   + (f' {e((" and ".join(n for n, _ in worst)).capitalize())} had no edge at all: the stocks {"they" if len(worst) > 1 else "it"} rated highly did no better.' if worst else "")
                   + (f' Of the ready-made mixes, {e(pbest[1])} has the best record ({ptx(pbest[2])}).' if pbest else "")
                   + ' Small edges are the norm, and these use today\'s list of stocks, which flatters every factor alike. '
                   + 'Analysts\' targets and ratings, forward P/E, PEG and crash exposure have no record of past values, so they can\'t be tested this way.</p>')
    def pedge(k):
        r = (gp.get(k) or {}).get("12m")
        if not r:
            return ""
        part = f' (graded on {gp[k]["graded_weight"]}% of its weight)' if gp[k].get("graded_weight", 100) < 100 else ""
        return f' · <b class="{"up" if r["edge"] >= 0.03 else "down" if r["edge"] <= 0 else ""}">edge {ptx(r["edge"])}</b> over a year{part}'
    presets = "".join(f'<li><button type="button" class="chip-btn" data-ps-wset="{k}">{e(n)}</button> <span class="small muted">'
                      + e(", ".join(f"{fname[f]} {w}" for f, w in sorted(w.items(), key=lambda z: -z[1]))) + pedge(k) + '</span></li>' for k, n, w in PRESETS)
    ex = ""
    t = next((x for x in TICKERS if x["sym"] == "SHOP.TO"), None)
    if t and (t["sym"], "buy-and-hold") in site.R:
        s1, g1, p1 = score(site, t)
        s2, g2, _ = score(site, t, {"plays": 100})
        up = next((x for x in p1 if x["k"] == "upside"), None)
        pl = next((x for x in p1 if x["k"] == "plays"), None)
        if s1 is not None and s2 is not None and up and pl and up["p"] is not None:
            ex = (f'<p><b>An example.</b> On the {dlong(site.asof)} close, {pl["v"]} of the plays held {e(t["name"])} ({e(t["short"])}), so the plays alone said buy. '
                  f'But analysts\' average target sat at {e(up["v"].split(" (")[0])} from the price, which scores {up["p"]}. With the standard weights its score is {s1}: {SIG_WORD[g1]}. '
                  f'Set analysts\' upside to 0 and it scores {s2}: {SIG_WORD[g2]}. Neither is right or wrong; the weights say what you think matters.</p>')
    return f"""<section class="card prose" id="your-signal"><p class="eyebrow">Your signal</p><h2 class="h2">Build your own Buy, Hold and Sell</h2>
<p><b>Your signal</b> is Be The Puck's one call on a stock, and it's yours to set: weight any of {len(FACTORS)} factors, from the plays and analysts to P/E, growth, debt, trend and crash exposure. Each factor scores a stock from 0 to 100, higher meaning more in favour of buying. Your score is the weighted average of the factors you weight, and your lines turn it into a signal: <b>Buy</b> at {BUY} or more, <b>Sell</b> at {SELL} or less and <b>Hold</b> in between, unless you move them.</p>
<p>Company numbers like P/E score by rank: a P/E lower than 80% of the {n_stocks()} stocks we cover scores 80. A loss-maker scores 0 on P/E. A stock with no number for a factor (a fund has no P/E) is scored on the rest, and gets no score if less than half your weight applies. The standard weights are half plays, half analysts' upside. Put every weight on the plays and you get the old plays-only reading.</p>
{ex}
<div class="ps-steps-row"><button type="button" class="btn sm primary" data-ps-open="weights">Set your weights</button><span class="small muted">Or start from a ready-made mix:</span></div>
<ul class="sig-presets">{presets}</ul>
{finding}
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Factor</th><th class="r" data-sort-first="desc">Edge, 3 months</th><th class="r" data-sort-first="desc">Edge, 1 year</th><th>What it measures, and its record</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small muted">Signals and scores are mechanical summaries of the numbers you choose to weight, not advice. {DISCLAIMER}</p></section>"""


def guide_page(site):
    path, depth = "guides/your-plays/", 2
    h = lambda x: site.href(depth, x)
    ns = n_stocks()
    acc = [(p, site.play_accuracy(p)) for p in TIMED]
    calls = sum(a["calls"] for _, a in acc)
    top = {p["slug"] for _, p, _ in site.top_plays()}
    mayer = next(((p, a) for p, a in acc if p["slug"] == "mayer-multiple"), None)

    # the families at a glance
    fam_rows = ""
    for fk, p, a in site.top_plays():
        fa = [x for q, x in acc if q["family"] == fk]
        r, c = sum(x["right"] for x in fa), sum(x["calls"] for x in fa)
        fam_rows += (f'<tr><td>{icon(fk)} {e(FAMILY[fk][0])}</td><td><a href="{h("guides/" + p["slug"] + "/")}"><b>{e(p["name"])}</b></a></td>'
                     f'<td class="r" data-v="{a["bat"]:.4f}"><b>{pct(a["bat"], sign=False, d=0)}</b></td><td class="r" data-v="{r / c if c else 0:.4f}">{pct(r / c if c else None, sign=False, d=0)}</td>'
                     f'<td class="r">{len(fa)}</td></tr>')

    # every play, most often right first
    rows = ""
    for p, a in sorted(acc, key=lambda z: (-(z[1]["bat"] or 0), z[0]["name"])):
        ok = rankable(a, ns)
        tag = '<span class="tag">Top in family</span>' if p["slug"] in top else ("" if ok else '<span class="tag muted-tag" title="Fewer than '
                                                                                   f'{TOP_MIN_CALLS} calls, or calls on fewer than half the stocks">Too few calls to rank</span>')
        rows += (f'<tr data-ps-row-play="{p["slug"]}"><td><span class="ps-pickrow"><input type="checkbox" data-ps-toggle="{p["slug"]}" checked aria-label="Count {e(p["name"])}">'
                 f'<a href="{h("guides/" + p["slug"] + "/")}"><b>{e(p["name"])}</b></a></span> {tag}</td><td class="small">{icon(p["family"])} {e(FAMILY[p["family"]][0])}</td>'
                 f'<td class="r nowrap" data-v="{a["bat"] if a["bat"] is not None else ""}"><span class="ps-accbar" aria-hidden="true"><i style="width:{round(100 * (a["bat"] or 0))}%"></i></span> '
                 f'<b>{pct(a["bat"], sign=False, d=0)}</b></td><td class="r" data-v="{a["calls"]}">{a["calls"]:,}</td><td class="r" data-v="{a["stocks"]}">{a["stocks"]}</td></tr>')

    presets = "".join(f'<button type="button" class="chip-btn" data-ps-set="{k}">{e(lab)}</button>' for k, lab in PRESETS)
    m_line = ""
    if mayer:
        mp, ma = mayer
        m_line = (f"Across the {ns} stocks its calls were right {pct(ma['bat'], sign=False, d=0)} of the time, but on only {ma['calls']:,} calls on {ma['stocks']} stocks: "
                  "few stocks ever run to 2.4 times their average, so it rarely says anything. That's why it has its own tile instead of a place in the rankings.")
    ex = next((t for t in TICKERS if t["sym"] == "NVDA"), TICKERS[0])
    body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>Your plays</span></nav>
<section class="pair-head"><p class="eyebrow">Guide</p><h1 class="h1">Pick your plays, build your signal</h1>
<p class="lede">Be The Puck runs {len(TIMED)} published trading plays on every stock each night. You don't have to count all of them, and you decide what makes a Buy: weight the plays, analysts, P/E, growth, debt, trend and more. This page shows how each play is graded, which ones have been right most often, how your signal is scored, and how to make every page on the site follow your choices.</p></section>

<section aria-labelledby="try-h"><div class="sec-head"><h2 class="h2" id="try-h">Try it in three steps</h2><p>Your choice follows you around the site. Signed in, it's saved to your account; otherwise it stays in this browser.</p></div>
<ol class="ps-steps">
<li class="card"><span class="step-n">1</span><b>Choose your plays</b><span class="small muted">Start from a ready-made set, then tick plays in or out. Each one shows how often its calls were right.</span>
{ps_bar(h, "Now counting:", "ps-bar-inline")}<div class="chips">{presets}</div></li>
<li class="card"><span class="step-n">2</span><b>Screen the market with them</b><span class="small muted">On the home page, step 4 counts only your plays. Sort by <i>Most accurate plays agree</i> to give each play a vote in line with its record.</span>
<a class="btn sm" href="{h('')}#step-4">Open the screener</a></li>
<li class="card"><span class="step-n">3</span><b>Check one stock</b><span class="small muted">Each stock page's Plays in tile, its most accurate plays and the full list follow your choice, with how often each play was right on that stock.</span>
<a class="btn sm" href="{h('stocks/' + ex['slug'] + '/')}#top-plays">See {e(ex['short'])}</a></li>
</ol>
<p class="small muted">The <a href="{h('stocks/')}">stock list</a> (Plays in, Score and the sorts), the <a href="{h('watchlist/')}">watchlist</a> and <a href="{h('me/')}">My Puck</a> follow your choice too. To share a view, add <code>?plays=top1</code> (or <code>top3</code>, <code>half</code>, <code>all</code>) to any link.</p>
</section>

<section class="split">
<div class="card prose" id="graded"><p class="eyebrow">How a play is graded</p>
<p>Each time a play switches in or out, that's a call. A call is <b>right</b> when the stock rose while the play was in (from that call to its next one), or fell while it was out.</p>
<p>Every play is tested the same way on the {ns} real stocks Be The Puck covers (no funds, indexes or coins) since {GRADE_YEAR}: {calls:,} finished calls in all. The percentage next to each play is its share of calls that were right.</p>
<p>To be ranked, a play needs at least {TOP_MIN_CALLS} finished calls, on at least half the stocks, so a rule that rarely fires can't top its family on a handful of calls.</p>
<p><b>Right often isn't the same as making the most money.</b> Trend plays are built to take many small losses for a few big wins, so their hit rates run below half. Dip-buying plays win often but small. Each play's record against simply holding is in the <a href="{h('guides/')}">guides</a>.</p></div>
<div class="card prose" id="mayer"><p class="eyebrow">The Mayer Multiple</p>
<p>The price divided by its 200-day average. Trace Mayer found that buying bitcoin below <b>2.4</b> times its 200-day average worked best over time; above it was bubble territory.</p>
<p>On every stock page the Mayer Multiple tile shows where the stock sits now, how often it has been higher since {GRADE_YEAR}, and the 2.4 line. A reading of 1.47, say, means the price is 47% above its 200-day average.</p>
<p>Be The Puck's Mayer play holds below 2.4 and steps aside above it (selling above 2.4 is our reading; Mayer used the line to decide when to keep buying). {m_line}</p>
<p><a href="{h('strategies/mayer-multiple/')}">The Mayer play on every stock</a></p></div>
</section>

{signal_section(site, h)}

<section aria-labelledby="fam-h"><div class="sec-head"><h2 class="h2" id="fam-h">The most accurate play in each family</h2><p>Ranked by share of calls right on {ns} stocks since {GRADE_YEAR}. The ready-made set <i>Most accurate in each family</i> counts these seven.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Family</th><th>Most accurate play</th><th class="r" data-sort-first="desc">Calls right</th><th class="r" data-sort-first="desc">Family average</th><th class="r">Plays</th></tr></thead>
<tbody>{fam_rows}</tbody></table></div></section>

<section aria-labelledby="all-h" id="every-play"><div class="sec-head"><h2 class="h2" id="all-h">Every play, by how often it was right</h2><p>Tick plays in or out here, or use the chooser. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl ps-all"><thead><tr><th>Play <span class="muted">(tick to count it)</span></th><th>Family</th><th class="r" data-sort-first="desc">Calls right</th><th class="r" data-sort-first="desc">Calls</th><th class="r" data-sort-first="desc">Stocks</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small muted">{DISCLAIMER}</p></section>
"""
    site.add(path, site.shell(path, "Pick your plays, build your signal · Be The Puck guide",
                              f"How Be The Puck grades its {len(TIMED)} trading plays, which were right most often on {ns} stocks since {GRADE_YEAR}, the Mayer Multiple, "
                              "and how to make every page count only the plays you choose.",
                              body, active="guides/", scripts=("assets/plays.js",)))
