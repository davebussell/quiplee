"""/rules/: members set their own Start/Stop rule and check their portfolio against it.

The site's light counts every play, turns Start at 60% and Stop at 40% (render.Site.light).
Members can choose which plays count (a preset or their own pick), move both
thresholds, and set four portfolio limits: the biggest single stock, the biggest
sector or group, the least in names that are Start under their rule, and the most
in names with high crash exposure. assets/rules.js does the work in the browser:
it reads data/watch.json (today's calls), data/hist/<slug>.json (two years of
weekly calls, so the light can be walked forward exactly like the site's own),
the reader's watchlist (localStorage, with quantities or values when their file
had them) and the member's saved list and rule (/api/member/list).

The page is locked like /picks/ (netlify/edge-functions/member-gate.js); the
locked copy shows a worked example built here from tonight's data.
"""
import html
import json
import os

from .content import TICKERS, TIMED
from .render import DISCLAIMER, LIGHT_ON, LIGHT_OFF, light_badge, dlong
from .members import member_tag, locked_page
from . import paper

e = html.escape
PRESET_N = 20
EXAMPLE = ["NVDA", "AAPL", "MSFT", "SHOP.TO", "RY.TO", "XIU.TO", "MU", "BTC-USD"]
FX_FALLBACK = 1.38      # CAD per USD, only if the night's rate is missing


def presets(site, guides):
    """(key, label, description, [slugs]) for each ready-made choice of plays."""
    ms = [(p, guides.play_metrics(p)) for p in TIMED]
    ms = [(p, m) for p, m in ms if m["n"]]
    best = [p["slug"] for p, m in sorted(ms, key=lambda z: -(z[1]["beat_sh"] / z[1]["n"]))[:PRESET_N]]
    protect = [p["slug"] for p, m in sorted(ms, key=lambda z: -(z[1]["cut"] / z[1]["n"]))[:PRESET_N]]

    def fam(*ks):
        return [p["slug"] for p in TIMED if p["family"] in ks]
    return [
        ("all", "Every play", f"All {len(TIMED)} plays: the site's own light.", [p["slug"] for p in TIMED]),
        ("best", "Best record", f"The {PRESET_N} plays that beat simply holding most often on risk-adjusted return in the backtests. Updated nightly.", best),
        ("protect", "Crash protection", f"The {PRESET_N} plays that cut the worst fall most often in the backtests. Updated nightly.", protect),
        ("trend", "Trend riders", "Trend following, breakouts and momentum: bets that a move keeps going.", fam("trend", "breakout", "momentum")),
        ("dip", "Dip buyers", "Mean reversion: bets that a sharp drop snaps back.", fam("reversion")),
    ]


def custom_light(site, t, slugs, on=LIGHT_ON, off=LIGHT_OFF):
    """Site.light with a chosen set of plays and thresholds (the same walk as rules.js)."""
    sym = t["sym"]
    want = set(slugs)
    sel = [p for p in TIMED if p["slug"] in want]
    hs = [(site.R.get((sym, p["slug"])) or {}).get("hist") or "" for p in sel]
    L = max((len(h) for h in hs), default=0)
    weeks = (site.meta.get(sym) or {}).get("weeks") or []
    min_n = min(5, len(sel))
    mid = (on + off) / 2
    state, since = None, None

    def step(k, n, when):
        nonlocal state, since
        if n < min_n or n == 0:
            return
        sh = k / n
        new = state
        if state is None:
            new = "start" if sh >= mid else "stop"
        elif state == "stop" and sh >= on:
            new = "start"
        elif state == "start" and sh <= off:
            new = "stop"
        if new != state:
            state, since = new, when
    for j in range(-L, 0):
        col = [h[j] for h in hs if len(h) >= -j]
        step(sum(1 for c in col if c == "1"), sum(1 for c in col if c in "01"), weeks[j] if len(weeks) >= -j else None)
    k, n = site.consensus(t, sel) if sel else (0, 0)
    step(k, n, site.r(sym, "buy-and-hold")["asof"])
    return {"state": state, "share": (k / n) if n else None, "k": k, "n": n, "since": since}


def hist_json(site, t):
    """Two years of weekly calls for one stock, in data/watch.json's play order, plus today's."""
    sym = t["sym"]
    weeks = (site.meta.get(sym) or {}).get("weeks") or []
    W = len(weeks)
    rows = []
    for p in TIMED:
        h = (site.R.get((sym, p["slug"])) or {}).get("hist") or ""
        rows.append(("-" * max(0, W - len(h)) + h)[-W:] if W else "")
    today = "".join("-" if (site.R.get((sym, p["slug"])) or {}).get("state") is None else str(site.R[(sym, p["slug"])]["state"]) for p in TIMED)
    return json.dumps({"a": site.r(sym, "buy-and-hold")["asof"].strftime("%Y-%m-%d"), "w": [w.strftime("%Y-%m-%d") for w in weeks],
                       "h": rows, "c": today}, separators=(",", ":"))


def write_hist(site, out):
    """data/hist/<slug>.json for every covered name (the rules page fetches only the ones on a list)."""
    folder = os.path.join(out, "data", "hist")
    os.makedirs(folder, exist_ok=True)
    n = 0
    for t in TICKERS:
        if (t["sym"], "buy-and-hold") not in site.R:
            continue
        with open(os.path.join(folder, t["slug"] + ".json"), "w", encoding="utf-8") as f:
            f.write(hist_json(site, t))
        n += 1
    return n


def _pill(L):
    if not L or not L.get("state"):
        return '<span class="light-pill">–</span>'
    word = "Start" if L["state"] == "start" else "Stop"
    return f'<span class="light-pill {L["state"]}"><i aria-hidden="true"></i>{word}</span>'


def _example(site, pre, depth):
    """A worked example for the locked page: eight well-known names, the site's light and
    the light under whichever ready-made rule differs most on them."""
    h = lambda x: site.href(depth, x)
    names = [next((t for t in TICKERS if t["sym"] == s), None) for s in EXAMPLE]
    names = [t for t in names if t and (t["sym"], "buy-and-hold") in site.R]
    if not names:
        return ""
    best = None
    for key, label, desc, slugs in pre:
        if key not in ("best", "protect", "trend"):
            continue
        for on in (0.6, 0.7):
            ls = [custom_light(site, t, slugs, on, LIGHT_OFF) for t in names]
            diff = sum(1 for t, L in zip(names, ls) if L["state"] != site.light(t)["state"])
            mixed = len({L["state"] for L in ls}) > 1      # an example with both lights reads better
            if best is None or (mixed, diff) > best[0]:
                best = ((mixed, diff), label, on, slugs, ls)
    (_, diff), label, on, slugs, ls = best
    more = " and needs more of them to agree before a stock turns Start" if on > LIGHT_ON else ""
    rows = "".join(f'<tr{" class=ru-diff" if L["state"] != site.light(t)["state"] else ""}><td><a href="{h("stocks/" + t["slug"] + "/")}"><b>{e(t["short"])}</b></a> '
                   f'<span class="muted small">{e(t["name"])}</span></td><td>{light_badge(site.light(t))}</td><td>{_pill(L)}</td>'
                   f'<td class="r nowrap">{L["k"]} of {L["n"]}</td></tr>' for t, L in zip(names, ls))
    return f"""<section class="card ru-example"><p class="eyebrow">Example, from the {dlong(site.asof)} close</p>
<h2 class="h3">"{e(label)}", Start at {round(on * 100)}%, Stop at {round(LIGHT_OFF * 100)}%</h2>
<p class="small muted">The site's light counts all {len(TIMED)} plays. This rule counts {len(slugs)} of them{more}; it changes the light on {diff} of these {len(names)} names.</p>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th>Site's light</th><th>Under this rule</th><th class="r">Plays in</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""


def rules_page(site, guides):
    path, depth = "rules/", 1
    h = lambda x: site.href(depth, x)
    pre = presets(site, guides)
    fx = paper.cad_per_usd() or FX_FALLBACK
    title = "Your own rules: set the Start/Stop light and check your portfolio"
    desc = (f"Be The Puck Members choose which of the {len(TIMED)} plays count, set when the light turns Start or Stop, "
            "and check their portfolio against their own limits.")
    head = f"""<section class="pair-head"><p class="eyebrow">{member_tag()} Your rules</p><h1 class="h1">Your own Start/Stop rules</h1>
<p class="lede">Choose which of the {len(TIMED)} plays count, decide how many must agree before a stock turns Start or Stop, and set limits for your portfolio. Then see every stock on your list under your rules, and where your portfolio stands against them.</p></section>"""
    pj = json.dumps([{"k": k, "n": n, "d": d, "p": s} for k, n, d, s in pre], separators=(",", ":"))
    lim_rows = [
        ("pos", "No single stock over", "% of the portfolio", 10, 1, 100),
        ("group", "No sector or group over", "% of the portfolio", 30, 5, 100),
        ("start", "At least", "% in stocks that are Start under my rule", 50, 0, 100),
        ("crash", "No more than", "% in stocks with high crash exposure", 25, 0, 100),
    ]
    lims = "".join(f'<div class="ru-lim"><label class="ru-lim-on"><input type="checkbox" data-ru-lim="{k}" checked><span>{e(a)}</span></label>'
                   f'<span class="ru-num"><input type="number" inputmode="numeric" data-ru-limv="{k}" value="{v}" min="{lo}" max="{hi}" step="1" aria-label="{e(a + " " + b)}">'
                   f'<span>{e(b)}</span></span></div>' for k, a, b, v, lo, hi in lim_rows)
    body = f"""{head}
<div id="ru-app" class="ru-app" data-watch="{e(h('data/watch.json'))}?v={site.ver}" data-hist="{e(h('data/hist/{u}.json'))}?v={site.ver}"
 data-stock="{e(h('stocks/{u}/'))}" data-wl="{e(h('watchlist/'))}" data-guide="{e(h('guides/{s}/'))}" data-fx="{fx:.4f}" data-on="{LIGHT_ON}" data-off="{LIGHT_OFF}">
<script type="application/json" id="ru-presets">{pj}</script>
<div class="ru-grid">
<section class="card ru-card" aria-labelledby="ru-h1">
<h2 class="h3" id="ru-h1"><span class="ru-n">1</span>Which plays count</h2>
<div class="seg seg-sm ru-presets" role="group" aria-label="Ready-made choices" data-ru-presets></div>
<p class="small muted" data-ru-pdesc></p>
<details class="ru-pick" data-ru-pickbox><summary>Choose plays one by one <span class="muted" data-ru-pcount></span></summary><div class="wl-picker ru-picker" data-ru-picker></div></details>
<h2 class="h3 ru-h-gap"><span class="ru-n">2</span>When the light turns</h2>
<div class="ru-thr">
<p class="small muted">The share of your chosen plays that hold the stock:</p>
<label class="ru-num"><span class="ru-lab">Start when</span><input type="number" inputmode="numeric" data-ru-on value="{round(LIGHT_ON * 100)}" min="50" max="95" step="5"><span>% or more hold it</span></label>
<label class="ru-num"><span class="ru-lab">Stop when</span><input type="number" inputmode="numeric" data-ru-off value="{round(LIGHT_OFF * 100)}" min="5" max="90" step="5"><span>% or fewer hold it</span></label>
</div>
<p class="small muted">Between the two, a stock keeps the light it had, so one that hovers near the line doesn't flip every few days. The site's own light is every play, {round(LIGHT_ON * 100)}% and {round(LIGHT_OFF * 100)}%.</p>
</section>
<section class="card ru-card" aria-labelledby="ru-h3">
<h2 class="h3" id="ru-h3"><span class="ru-n">3</span>Your portfolio limits</h2>
<div class="ru-lims">{lims}</div>
<p class="small muted">Untick a limit to stop checking it. Weights come from the quantities or values in the file you added on the <a href="{h('watchlist/')}">watchlist</a>; without them every stock counts equally.</p>
<div class="ru-save"><button type="button" class="btn primary" data-ru-save>Save my rules</button><button type="button" class="btn" data-ru-reset>Back to the site's rule</button></div>
<p class="small" role="status" data-ru-msg></p>
</section>
</div>
<section class="ru-out" aria-live="polite">
<div class="sec-head"><h2 class="h2">Your stocks under your rules</h2><p data-ru-src>Loading your list…</p></div>
<div class="sum-tiles ru-tiles" data-ru-tiles></div>
<div class="ru-checks" data-ru-checks></div>
<div data-ru-table></div>
</section>
</div>
<noscript><p class="note-line">This tool needs JavaScript.</p></noscript>

<section class="card prose"><p class="eyebrow">How it works</p>
<ul>
<li><b>The light.</b> For each stock, Be The Puck counts how many of your chosen plays hold it. The light turns Start when the share reaches your Start level and stays Start until it falls to your Stop level. It is walked through two years of weekly calls and then today's, exactly like the site's own light, so "since" is the date it last turned under your rule.</li>
<li><b>Ready-made choices.</b> "Best record" and "Crash protection" come from the <a href="{h('guides/')}">guides</a>, which test every play against simply holding the same stock since 2005. They are re-ranked every night.</li>
<li><b>Your limits.</b> They describe your portfolio as it stands. Be The Puck doesn't know your taxes, costs, goals or other accounts, and a limit that's out doesn't mean you should trade.</li>
<li><b>Where it's kept.</b> Your rule is saved to your membership, so it follows you to any device. Your quantities and values stay in this browser.</li>
</ul>
<p class="small muted">{e(DISCLAIMER)}</p></section>
"""
    site.add(path, site.shell(path, title, desc, body, active="stocks/", scripts=("assets/widgets.js", "assets/rules.js"), link=False))
    locked_page(site, path, title, desc, head + _example(site, pre, depth), what="tool", active="stocks/")
