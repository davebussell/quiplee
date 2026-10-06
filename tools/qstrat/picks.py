"""/picks/: the top-picks tracker, for members.

The rules (also printed on the page)
  * Candidates are the public "strongest setups": covered stocks (no ETFs,
    indexes or coins) with 3+ analysts and at least half the plays in, ranked
    by the outlook score (half plays in, half analysts' upside; stockview.py).
  * Five picks. The model starts at 100 split into five equal slots; a pick
    takes one slot and keeps whatever that slot is worth when it leaves.
  * Reviewed after each Friday close (or the first close after, if Friday is a
    holiday). A pick stays while it ranks in the top 10 and still qualifies.
    Otherwise it leaves at that close and the best-ranked name not held takes
    its slot. Nothing changes between reviews.
  * Entries and exits at the review day's closing price. No fees, taxes,
    dividends or slippage. Hypothetical, not advice.

Where the history lives
  The picks history is the tracker's paid content, so it is kept out of the
  public repo: it sits in Netlify Blobs behind /api/picks-state
  (netlify/functions/picks-state.mjs, bearer token PICKS_STATE_TOKEN). The
  production build reads it, applies any review that is due, and writes it
  back. Other builds read it and never write. For local work set
  QUIPLEE_PICKS_FILE to a JSON file and the build reads and writes that file.
  Returns are always recomputed from the current price files (so splits don't
  distort them); the stored prices are only the record of the day.
"""
import html
import json
import math
import os
import urllib.error
import urllib.request

import pandas as pd

from . import stockview as sv
from .content import TIMED
from .members import locked_page, member_tag
from .render import money, pct, dir_cls, count_in, next_move, chart_block, key_line, dlong, dshort, sig, _days

e = html.escape
SLOTS = 5
HOLD_RANK = 10
MIN_TREND = 0.5
BENCH = "^GSPC"
VERSION = 1


# --------------------------------------------------------------------------
# state storage
# --------------------------------------------------------------------------
def _state_urls():
    """Where /api/picks-state lives: the site's main address, then its netlify.app
    address (always has a certificate, e.g. while a new domain's is being issued)."""
    if os.environ.get("QUIPLEE_PICKS_URL"):
        return [os.environ["QUIPLEE_PICKS_URL"]]
    out = [(os.environ.get("URL") or "https://bethepuck.com").rstrip("/") + "/api/picks-state"]
    if os.environ.get("SITE_NAME"):
        out.append(f"https://{os.environ['SITE_NAME']}.netlify.app/api/picks-state")
    return out


_STORE = {"url": None}


def load_state():
    """(state or None, status): status is 'ok', 'missing' (no history yet), 'error' or 'none' (no store configured)."""
    fp = os.environ.get("QUIPLEE_PICKS_FILE")
    if fp:
        if not os.path.exists(fp):
            return None, "missing"
        with open(fp, encoding="utf-8") as f:
            return json.load(f), "ok"
    tok = os.environ.get("PICKS_STATE_TOKEN")
    if not tok:
        return None, "none"
    for url in _state_urls():
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                _STORE["url"] = url
                return json.loads(r.read().decode("utf-8")), "ok"
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", "replace")[:200]
            # only the store's own answer means "no history yet"; any other 404 is an error
            if ex.code == 404 and "no history yet" in body:
                _STORE["url"] = url
                return None, "missing"
            print(f"picks: state read from {url} failed ({ex.code})")
        except (urllib.error.URLError, OSError, ValueError) as ex:
            print(f"picks: state read from {url} failed ({ex.__class__.__name__})")
    return None, "error"


def save_state(state, status):
    fp = os.environ.get("QUIPLEE_PICKS_FILE")
    body = json.dumps(state, separators=(",", ":"), allow_nan=False)
    if fp:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(body)
        return "file"
    tok = os.environ.get("PICKS_STATE_TOKEN")
    if not tok or os.environ.get("CONTEXT") != "production" or status not in ("ok", "missing") or not _STORE["url"]:
        return "skipped"
    req = urllib.request.Request(_STORE["url"], data=body.encode("utf-8"), method="PUT",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"saved ({r.status})"
    except (urllib.error.URLError, OSError) as ex:
        print(f"picks: state write failed ({ex})")
        return "failed"


# --------------------------------------------------------------------------
# ranking and the weekly review
# --------------------------------------------------------------------------
def candidates(site):
    return [t for t in site.universe if not t.get("index") and not t["crypto"] and t["group"] not in ("Sectors", "Indexes & ETFs")
            and (t["sym"], "buy-and-hold") in site.R]


def ranked(site):
    """[(ticker, outlook)] for every name that qualifies, best first."""
    out = []
    for t in candidates(site):
        o = sv.outlook(site, t)
        if o["ok"] and o["trend"] >= MIN_TREND:
            out.append((t, o))
    out.sort(key=lambda z: (-z[1]["score"], z[0]["short"]))
    return out


def market_date(site):
    x = site.R.get((BENCH, "buy-and-hold"))
    return pd.Timestamp(x["asof"] if x else site.asof).normalize()


def review_due(state, mkt):
    if state is None:
        return True
    last = pd.Timestamp(state["last_review"])
    return mkt > last and (mkt.weekday() == 4 or (mkt - last).days >= 7)


def next_review(mkt):
    days = (4 - mkt.weekday()) % 7 or 7
    return mkt + pd.Timedelta(days=days)


def _why_out(site, sym, rank):
    from .render import TK
    t = TK.get(sym)
    if t is None or (sym, "buy-and-hold") not in site.R or t not in candidates(site):
        return "No longer covered"
    o = sv.outlook(site, t)
    if not o["ok"]:
        return f"Analysts' target no longer usable ({o['why']})"
    if o["trend"] < MIN_TREND:
        return f"Fewer than half the plays hold it ({o['k']} of {o['n']})"
    return f"Slipped to #{rank} on the score" if rank else "Dropped out of the ranking"


def review(state, site, rk, mkt):
    """Apply one review at the market close `mkt`. Returns the new state (the input is not modified)."""
    st = json.loads(json.dumps(state)) if state else {
        "v": VERSION, "started": mkt.strftime("%Y-%m-%d"), "last_review": None,
        "positions": [], "log": [], "next_id": 1}
    d = mkt.strftime("%Y-%m-%d")
    rank = {t["sym"]: i + 1 for i, (t, _) in enumerate(rk)}
    outs, ins = [], []
    for p in st["positions"]:
        if p["exit"] is not None:
            continue
        r = rank.get(p["sym"])
        if r is not None and r <= HOLD_RANK:
            continue
        x = site.R.get((p["sym"], "buy-and-hold"))
        p["exit"], p["px_out"] = d, (sig(x["price"], 6) if x else p["px_in"])
        p["why_out"] = _why_out(site, p["sym"], r)
        p["rank_out"] = r
        outs.append(p["sym"])
    held = {p["sym"] for p in st["positions"] if p["exit"] is None}
    busy = {p["slot"] for p in st["positions"] if p["exit"] is None}
    free = [i for i in range(SLOTS) if i not in busy]
    for t, o in rk:
        if not free:
            break
        if t["sym"] in held:
            continue
        x = site.R[(t["sym"], "buy-and-hold")]
        st["positions"].append({
            "id": st["next_id"], "slot": free.pop(0), "sym": t["sym"], "entry": d, "px_in": sig(x["price"], 6),
            "rank_in": rank[t["sym"]], "score_in": round(o["score"], 4), "k_in": o["k"], "n_in": o["n"],
            "up_in": round(o["upside"], 4), "exit": None, "px_out": None, "why_out": None, "rank_out": None})
        st["next_id"] += 1
        held.add(t["sym"])
        ins.append(t["sym"])
    st["log"].append({"date": d, "in": ins, "out": outs, "kept": sorted(held - set(ins))})
    st["last_review"] = d
    return st


def run(site):
    """Load the history, apply a due review, save it (production only). Returns (state, info)."""
    state, status = load_state()
    mkt = market_date(site)
    rk = ranked(site)
    info = {"status": status, "reviewed": False, "saved": None, "mkt": mkt, "rk": rk}
    if status == "error":
        return None, info
    if review_due(state, mkt):
        state = review(state, site, rk, mkt)
        info["reviewed"] = True
        info["saved"] = save_state(state, status)
    print(f"picks: history {status}, review {'applied' if info['reviewed'] else 'not due'}, save {info['saved']}")
    return state, info


# --------------------------------------------------------------------------
# returns, recomputed from the price files
# --------------------------------------------------------------------------
def _close(site, sym):
    d = (site.prices or {}).get(sym)
    return None if d is None else d["close"].dropna()


def _at(ser, day):
    if ser is None:
        return None
    v = ser.asof(pd.Timestamp(day))
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def growth(site, p, upto=None):
    """Price growth factor of a pick from its entry close to its exit close (or `upto`, or the latest close)."""
    ser = _close(site, p["sym"])
    a = _at(ser, p["entry"])
    end = p["exit"] or upto
    b = _at(ser, end) if end else (float(ser.iloc[-1]) if ser is not None and len(ser) else None)
    if a and b:
        return b / a
    if p["exit"] and p["px_out"] and p["px_in"]:
        return p["px_out"] / p["px_in"]
    return 1.0


def bench_growth(site, start, end=None):
    ser = _close(site, BENCH)
    a, b = _at(ser, start), (_at(ser, end) if end else (float(ser.iloc[-1]) if ser is not None and len(ser) else None))
    return b / a if a and b else None


def curve(site, state):
    """Daily value of the model (starts at 100) and of the S&P 500 on the same scale."""
    cal = _close(site, BENCH)
    if cal is None or not state:
        return None
    start = pd.Timestamp(state["started"])
    cal = cal[cal.index >= start]
    if not len(cal):
        return None
    by_slot = {}
    for p in state["positions"]:
        by_slot.setdefault(p["slot"], []).append(p)
    for v in by_slot.values():
        v.sort(key=lambda p: p["entry"])
    model = []
    for day in cal.index:
        tot = 0.0
        for s in range(SLOTS):
            val = 100.0 / SLOTS
            for p in by_slot.get(s, []):
                if pd.Timestamp(p["entry"]) > day:
                    break
                if p["exit"] and pd.Timestamp(p["exit"]) <= day:
                    val *= growth(site, p)
                else:
                    val *= growth(site, p, upto=day)
                    break
            tot += val
        model.append(tot)
    spx = [100.0 * float(c) / float(cal.iloc[0]) for c in cal.values]
    return cal.index, model, spx


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------
def _exits(site, t):
    out = []
    for p in TIMED:
        if not p.get("core"):
            continue
        x = site.R.get((t["sym"], p["slug"]))
        if not x or x["state"] != 1:
            continue
        nm = next_move(x, p, t)
        if nm["level"] is not None and nm["dist"] is not None and nm["dist"] < 0:
            out.append((p, nm["level"], nm["dist"]))
    out.sort(key=lambda z: -z[2])
    return out


def _mini_spec(site, t, entry):
    ser = _close(site, t["sym"])
    if ser is None:
        return None
    start = min(pd.Timestamp(entry) - pd.DateOffset(months=6), ser.index[-1] - pd.DateOffset(months=6))
    w = ser[ser.index >= start]
    if len(w) < 5:
        return None
    t0, d = _days(w.index)
    i_in = int((w.index <= pd.Timestamp(entry)).sum()) - 1
    return {"t0": t0, "d": d, "cur": t["cur"], "fmt": "price", "small": True, "label": f"{t['short']} price, last six months, marked where it became a pick",
            "series": [{"name": t["short"], "role": "price", "v": [sig(v) for v in w.values]}], "pins": [[max(i_in, 0), "Picked"]]}


def _ret(v):
    return f'<b class="{dir_cls(v)}">{pct(v)}</b>' if v is not None else "–"


def picks_page(site, state, info):
    from .render import TK
    path, depth = "picks/", 1
    h = lambda x: site.href(depth, x)
    mkt, rk = info["mkt"], info["rk"]
    head = f"""<header class="pair-head"><p class="eyebrow">Members · Top picks</p><h1 class="h1">Top picks tracker</h1>
<p class="lede">Five stocks picked by rule from the strongest setups and tracked from the close they go in. Reviewed after every Friday close; a pick stays while it ranks in the top {HOLD_RANK}.</p></header>"""
    desc = "Five stocks picked by rule from Be The Puck's strongest setups, tracked against the S&P 500 from the close they go in. For Be The Puck Members."
    locked_page(site, path, "Top picks tracker", desc, head, what="tracker",
                crumbs=f'<nav class="crumbs"><a href="{h("stocks/")}">Stocks</a><span>/</span><span>Top picks</span></nav>')

    if state is None:
        body = (f'<nav class="crumbs"><a href="{h("stocks/")}">Stocks</a><span>/</span><span>Top picks</span></nav>{head}'
                '<p class="note-line">The tracker\'s history couldn\'t be loaded for this build. It will be back after the next rebuild.</p>')
        site.add(path, site.shell(path, "Top picks tracker", desc, body, active="stocks/", scripts=("assets/members.js",)))
        return

    rank = {t["sym"]: (i + 1, o) for i, (t, o) in enumerate(rk)}
    open_ps = [p for p in state["positions"] if p["exit"] is None]
    closed = sorted([p for p in state["positions"] if p["exit"]], key=lambda p: (p["exit"], p["id"]), reverse=True)
    started = pd.Timestamp(state["started"])
    cv = curve(site, state)
    model_ret = (cv[1][-1] / 100 - 1) if cv else None
    spx_ret = (cv[2][-1] / 100 - 1) if cv else None
    nxt = next_review(pd.Timestamp(state["last_review"]) if mkt <= pd.Timestamp(state["last_review"]) else mkt)
    beat = sum(1 for p in closed if (bench_growth(site, p["entry"], p["exit"]) or 1) < growth(site, p))

    gap = (model_ret - spx_ret) if model_ret is not None and spx_ret is not None else None
    tiles = (f'<div class="card tile"><span class="tile-label">Model since {dshort(started)}</span><span class="tile-value {dir_cls(model_ret)}">{pct(model_ret)}</span>'
             f'<span class="tile-note">S&amp;P 500 {pct(spx_ret)} over the same closes</span></div>'
             f'<div class="card tile"><span class="tile-label">Against the S&amp;P 500</span><span class="tile-value {dir_cls(gap)}">{pct(gap)}</span>'
             f'<span class="tile-note">{"Ahead" if (gap or 0) > 0 else "Behind" if (gap or 0) < 0 else "Level"}, in percentage points</span></div>'
             f'<div class="card tile"><span class="tile-label">Open picks</span><span class="tile-value">{len(open_ps)}</span>'
             f'<span class="tile-note">{len(closed)} closed so far{f", {beat} beat the S&amp;P 500" if closed else ""}</span></div>'
             f'<div class="card tile"><span class="tile-label">Next review</span><span class="tile-value">{nxt.strftime("%a %b %-d")}</span>'
             f'<span class="tile-note">After that day\'s close</span></div>')

    cards = ""
    for p in sorted(open_ps, key=lambda p: rank.get(p["sym"], (99, None))[0]):
        t = TK.get(p["sym"])
        if t is None:
            continue
        g = growth(site, p) - 1
        bg = bench_growth(site, p["entry"])
        vs = (g - (bg - 1)) if bg else None
        r_now, o = rank.get(p["sym"], (None, None))
        o = o or sv.outlook(site, t)
        rk_risk = (site.meta.get(t["sym"]) or {}).get("risk") or {}
        ex = _exits(site, t)
        ex_txt = (f'Nearest core exit: <a href="{h(site.pair_path(t, ex[0][0]))}">{e(ex[0][0]["name"])}</a> gets out below {money(ex[0][1], t["cur"])} '
                  f'<span class="muted">({pct(ex[0][2], d=1)})</span>') if ex else "No core play that holds it has a price exit nearby."
        ser = _close(site, t["sym"])
        entry_px = _at(ser, p["entry"]) or p["px_in"]
        now_px = float(ser.iloc[-1]) if ser is not None and len(ser) else site.R[(t["sym"], "buy-and-hold")]["price"]
        spec = _mini_spec(site, t, p["entry"])
        chart = chart_block(f"pk-{t['slug']}", spec, key_line("--s-price", t["short"]), "Last six months", small=True) if spec else ""
        lvl = rk_risk.get("level")
        up = o.get("upside")
        cards += f"""<div class="card pk-card">
<div class="pk-top"><a class="pk-sym" href="{h('stocks/' + t['slug'] + '/')}">{e(t['short'])}</a><span class="muted small">{e(t['name'])}</span>
<span class="tag">{"#" + str(r_now) + " now" if r_now else "Out of the ranking"}</span></div>
<div class="pk-nums">
<div><span class="tile-label">Since {dshort(pd.Timestamp(p['entry']))}</span>{_ret(g)}</div>
<div><span class="tile-label">S&amp;P 500</span>{_ret(bg - 1 if bg else None)}</div>
<div><span class="tile-label">Ahead by</span>{_ret(vs)}</div>
</div>
<p class="small">In at {money(entry_px, t['cur'])} on {dshort(pd.Timestamp(p['entry']))} · now {money(now_px, t['cur'])}</p>
<p class="small">{count_in(o['k'], o['n'], 'plays in')}</p>
<p class="small">Analysts' target <b class="{dir_cls(up)}">{pct(up, d=0) if up is not None else '–'}</b> · Score <b>{round(o['score'] * 100) if o.get('score') is not None else '–'}</b></p>
<p class="small">{f'<span class="lvl-{sv.LEVEL_CLASS[lvl]}">{e(lvl)} crash exposure</span> ({rk_risk.get("score")} of 10 on the storm test)' if lvl else ''}</p>
<p class="small">{ex_txt}</p>
{chart}
</div>"""

    held = {p["sym"] for p in open_ps}
    bench_rows = ""
    for i, (t, o) in enumerate(rk[:HOLD_RANK + 2]):
        mark = '<span class="tag live">Pick</span>' if t["sym"] in held else ""
        bench_rows += (f'<tr><td class="r">{i + 1}</td><td><a href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a> <span class="muted small pk-nm">{e(t["name"])}</span> {mark}</td>'
                       f'<td class="r">{round(o["score"] * 100)}</td><td>{count_in(o["k"], o["n"])}</td><td class="r {dir_cls(o["upside"])}">{pct(o["upside"], d=0)}</td></tr>')

    closed_rows = ""
    for p in closed:
        t = TK.get(p["sym"])
        nm = e(t["short"]) if t else e(p["sym"])
        link = f'<a href="{h("stocks/" + t["slug"] + "/")}">{nm}</a>' if t else nm
        g = growth(site, p) - 1
        bg = bench_growth(site, p["entry"], p["exit"])
        closed_rows += (f'<tr><td>{link}</td><td class="nowrap">{dshort(pd.Timestamp(p["entry"]))} → {dshort(pd.Timestamp(p["exit"]))}</td>'
                        f'<td class="r">{_ret(g)}</td><td class="r">{_ret(bg - 1 if bg else None)}</td><td class="small">{e(p["why_out"] or "")}</td></tr>')
    closed_html = (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th>Held</th><th class="r">Return</th><th class="r">S&amp;P 500</th><th>Why it left</th></tr></thead>'
                   f'<tbody>{closed_rows}</tbody></table></div>') if closed_rows else '<p class="muted">None yet. The first review is after the next Friday close.</p>'

    def names(syms):
        return ", ".join(e(TK[s]["short"]) if s in TK else e(s) for s in syms) or "none"
    log = "".join(f'<li><b>{dlong(pd.Timestamp(r["date"]))}</b>: '
                  + ("Started with " + names(r["in"]) if r is state["log"][0] else
                     f'in: {names(r["in"])} · out: {names(r["out"])}' if (r["in"] or r["out"]) else "no changes, all five kept")
                  + "</li>" for r in reversed(state["log"][-12:]))

    chart = ""
    if cv and len(cv[0]) >= 3:
        t0, d = _days(cv[0])
        spec = {"t0": t0, "d": d, "cur": "", "fmt": "dec", "dp": 1, "label": "The top-picks model against the S&P 500, both starting at 100",
                "series": [{"name": "Top picks", "role": "s1", "v": [round(v, 2) for v in cv[1]]},
                           {"name": "S&P 500", "role": "bench", "v": [round(v, 2) for v in cv[2]]}]}
        chart = chart_block("pk-curve", spec, key_line("--s1", "Top picks") + key_line("--s-bench", "S&P 500"),
                            "The model against the S&amp;P 500", note="Both start at 100 on the first pick day. Closing prices, no fees or dividends.")
    else:
        chart = (f'<p class="note-line">The model started on the {dlong(started)} close. Its chart against the S&amp;P 500 fills in from the next few closes.</p>')

    body = f"""<nav class="crumbs"><a href="{h("stocks/")}">Stocks</a><span>/</span><span>Top picks</span></nav>
{head}
<div class="pk-bar">{member_tag()}<span class="small muted">Prices to the {dlong(mkt)} close.</span><a class="small" href="/api/member/logout">Sign out</a></div>
<section class="sum-tiles">{tiles}</section>
<section>{chart}</section>
<section aria-labelledby="open-h"><div class="sec-head"><h2 class="h2" id="open-h">The five picks</h2>
<p>Each one's return since it went in, the S&amp;P 500 over the same closes, and what the plays and analysts say now. Ordered by today's rank.</p></div>
<div class="grid grid-3 pk-grid">{cards}</div></section>
<section aria-labelledby="line-h"><div class="sec-head"><h2 class="h2" id="line-h">Next in line</h2>
<p>Today's top of the ranking. A pick below #{HOLD_RANK} at a review makes way for the best name not held.</p></div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th class="r">Rank</th><th>Stock</th><th class="r">Score</th><th>Plays in</th><th class="r">Analysts' target</th></tr></thead><tbody>{bench_rows}</tbody></table></div></section>
<section aria-labelledby="closed-h"><div class="sec-head"><h2 class="h2" id="closed-h">Closed picks</h2><p>Every pick that has left, and why.</p></div>{closed_html}</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Review log</p><ul>{log}</ul></div>
<div class="card prose"><p class="eyebrow">The rules</p><ol>
<li><b>Candidates.</b> The <a href="{h('stocks/?sort=score')}">strongest setups</a>: covered stocks with 3+ analysts and at least half the plays in, scored half on plays in and half on analysts' upside. <a href="{h('articles/green-across-the-board/')}">How the score works</a>.</li>
<li><b>Five picks.</b> The model starts at 100 in five equal slots. A pick takes a slot and keeps whatever the slot is worth when it leaves.</li>
<li><b>Weekly review.</b> After each Friday close. A pick stays while it ranks in the top {HOLD_RANK} and still qualifies; otherwise it leaves and the best-ranked name not held comes in.</li>
<li><b>Prices.</b> In and out at the review day's close. No fees, taxes, dividends or slippage.</li>
</ol><p class="small muted">A hypothetical model run by fixed rules, not a record of real trades. This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Be The Puck takes no positions in the names it covers.</p></div>
</section>"""
    site.add(path, site.shell(path, "Top picks tracker", desc, body, active="stocks/", charts=True, scripts=("assets/members.js",)))
