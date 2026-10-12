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
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "since": GRADE_YEAR, "n": ns, "min": TOP_MIN_CALLS,
                       "fams": [[k, name] for k, name, _ in FAMILIES], "plays": plays, "t": t},
                      ensure_ascii=False, separators=(",", ":"))


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
<section class="pair-head"><p class="eyebrow">Guide</p><h1 class="h1">Pick the plays you trust</h1>
<p class="lede">Be The Puck runs {len(TIMED)} published trading plays on every stock each night. You don't have to count all of them. This page shows how each play is graded, which ones have been right most often, and how to make every page on the site count only the plays you choose.</p></section>

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

<section aria-labelledby="fam-h"><div class="sec-head"><h2 class="h2" id="fam-h">The most accurate play in each family</h2><p>Ranked by share of calls right on {ns} stocks since {GRADE_YEAR}. The ready-made set <i>Most accurate in each family</i> counts these seven.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Family</th><th>Most accurate play</th><th class="r" data-sort-first="desc">Calls right</th><th class="r" data-sort-first="desc">Family average</th><th class="r">Plays</th></tr></thead>
<tbody>{fam_rows}</tbody></table></div></section>

<section aria-labelledby="all-h" id="every-play"><div class="sec-head"><h2 class="h2" id="all-h">Every play, by how often it was right</h2><p>Tick plays in or out here, or use the chooser. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl ps-all"><thead><tr><th>Play <span class="muted">(tick to count it)</span></th><th>Family</th><th class="r" data-sort-first="desc">Calls right</th><th class="r" data-sort-first="desc">Calls</th><th class="r" data-sort-first="desc">Stocks</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small muted">{DISCLAIMER}</p></section>
"""
    site.add(path, site.shell(path, "Pick the plays you trust · Be The Puck guide",
                              f"How Be The Puck grades its {len(TIMED)} trading plays, which were right most often on {ns} stocks since {GRADE_YEAR}, the Mayer Multiple, "
                              "and how to make every page count only the plays you choose.",
                              body, active="guides/", scripts=("assets/plays.js",)))
