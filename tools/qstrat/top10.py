"""/articles/top-10/: Be The Puck's weekly stake in the ground, and how every week's ten did.

The rule (also printed on the page)
  * Stocks only: no funds, indexes, sectors or coins.
  * The Start/Stop light must be on Start at the close the list is made.
  * Ranked by the share of the plays that hold the stock that night; ties go to the
    bigger 13-week price gain.
  * At most two names from any one group, so ten picks are not one bet ten times.
  * A new list after each Friday close (or the week's last close, when Friday is a
    holiday). Each list is tracked from its own close, equal-weight, against the
    S&P 500 over the same days. No fees, taxes or dividends.

Analysts' targets are shown beside this week's names as context but play no part in
the ranking: there is no record of past targets, so a rule that used them could not
be checked honestly against its own history.

Frozen record
  A list is never recomputed once made. The record lives in Netlify Blobs behind
  /api/picks-state?doc=top10 (same token and rules as the top-picks tracker in picks.py:
  production builds read and write, other builds only read; QUIPLEE_TOP10_FILE points
  local builds at a JSON file). The first run also reconstructs what the rule would
  have picked one year, six months and three months earlier, from each play's weekly
  calls and prices up to that week's close only, labels them "reconstructed" and
  freezes them with the launch list. Returns are always recomputed from the price files.
"""
import html
import json
import os
import urllib.error
import urllib.request

import pandas as pd

from .content import TIMED
from .picks import candidates, market_date, review_due, _close, _at, _state_urls, BENCH

e = html.escape
TOP = 10
PER_GROUP = 2
MOM_DAYS = 91
VERSION = 1
BACKDATES = [("1 year earlier", 52), ("6 months earlier", 26), ("3 months earlier", 13)]   # weeks before launch


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------
_STORE = {"url": None}


def _urls():
    return [u + ("&" if "?" in u else "?") + "doc=top10" for u in _state_urls()]


def load_state():
    """(state or None, status): 'ok', 'missing' (nothing yet), 'error' or 'none' (no store configured)."""
    fp = os.environ.get("QUIPLEE_TOP10_FILE")
    if fp:
        if not os.path.exists(fp):
            return None, "missing"
        with open(fp, encoding="utf-8") as f:
            return json.load(f), "ok"
    tok = os.environ.get("PICKS_STATE_TOKEN")
    if not tok:
        return None, "none"
    for url in _urls():
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                _STORE["url"] = url
                return json.loads(r.read().decode("utf-8")), "ok"
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", "replace")[:200]
            if ex.code == 404 and "no history yet" in body:
                _STORE["url"] = url
                return None, "missing"
            print(f"top10: read from {url} failed ({ex.code})")
        except (urllib.error.URLError, OSError, ValueError) as ex:
            print(f"top10: read from {url} failed ({ex.__class__.__name__})")
    return None, "error"


def save_state(state, status):
    body = json.dumps(state, separators=(",", ":"), allow_nan=False)
    fp = os.environ.get("QUIPLEE_TOP10_FILE")
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
        print(f"top10: write failed ({ex})")
        return "failed"


# --------------------------------------------------------------------------
# the rule, today and at any past week
# --------------------------------------------------------------------------
def _mom(ser, day):
    a, b = _at(ser, pd.Timestamp(day) - pd.Timedelta(days=MOM_DAYS)), _at(ser, day)
    return (b / a - 1) if a and b else None


def _walk(site, t, upto):
    """(light, k, n) for a stock as of the week whose last session is `upto`, from the plays' weekly calls."""
    sym = t["sym"]
    hs = [(site.R.get((sym, p["slug"])) or {}).get("hist") or "" for p in TIMED]
    weeks = [pd.Timestamp(w) for w in ((site.meta.get(sym) or {}).get("weeks") or [])]
    if not weeks:
        return None, 0, 0
    L = max((len(h) for h in hs), default=0)
    from .render import LIGHT_ON, LIGHT_OFF
    state, k, n = None, 0, 0
    for j in range(-min(L, len(weeks)), 0):
        if weeks[j] > upto:
            break
        col = [h[j] for h in hs if len(h) >= -j]
        k, n = sum(1 for c in col if c == "1"), sum(1 for c in col if c in "01")
        if n < 5:
            continue
        sh = k / n
        if state is None:
            state = "start" if sh >= 0.5 else "stop"
        elif state == "stop" and sh >= LIGHT_ON:
            state = "start"
        elif state == "start" and sh <= LIGHT_OFF:
            state = "stop"
    return state, k, n


def pick(site, day=None):
    """The ten for the close `day` (None: tonight's close, from the live calls)."""
    rows = []
    for t in candidates(site):
        ser = _close(site, t["sym"])
        if day is None:
            L = site.light(t)
            state, k, n = L["state"], L["k"], L["n"]
            when = market_date(site)
        else:
            state, k, n = _walk(site, t, pd.Timestamp(day))
            when = pd.Timestamp(day)
        px = _at(ser, when)
        if state != "start" or not n or not px:
            continue
        rows.append({"sym": t["sym"], "short": t["short"], "name": t["name"], "group": t["group"], "slug": t["slug"], "cur": t["cur"],
                     "k": k, "n": n, "px": round(px, 4), "m13": _mom(ser, when)})
    rows.sort(key=lambda r: (-r["k"] / r["n"], -(r["m13"] if r["m13"] is not None else -9), r["short"]))
    out, per = [], {}
    for r in rows:
        if per.get(r["group"], 0) >= PER_GROUP:
            continue
        per[r["group"]] = per.get(r["group"], 0) + 1
        out.append(r)
        if len(out) == TOP:
            break
    for r in out:
        if r["m13"] is not None:
            r["m13"] = round(r["m13"], 4)
    return out


def _week_close(site, weeks_back, mkt):
    """The last session of the week `weeks_back` weeks before the one holding `mkt`."""
    ser = _close(site, BENCH)
    target = mkt - pd.Timedelta(weeks=weeks_back)
    fri = target - pd.Timedelta(days=(target.weekday() - 4) % 7)     # the Friday on or before

    ser = ser[ser.index <= fri]
    return pd.Timestamp(ser.index[-1]).normalize() if len(ser) else None


def run(site):
    """Load the record, make whatever list is due, save it. Returns (state, info)."""
    state, status = load_state()
    if state is not None and not isinstance(state.get("lists"), list):
        # not a top-10 record (e.g. an older store answered with the top-picks tracker): never build on it
        print("top10: the store answered with something else; using an unsaved list this build")
        state, status = None, "error"
    mkt = market_date(site)
    info = {"status": status, "saved": "no change"}
    if state is None or state.get("v") != VERSION:
        lists = []
        for label, wk in BACKDATES:
            day = _week_close(site, wk, mkt)
            if day is not None:
                lists.append({"date": day.strftime("%Y-%m-%d"), "kind": "reconstructed", "label": label, "picks": pick(site, day)})
        lists.append({"date": mkt.strftime("%Y-%m-%d"), "kind": "live", "label": "Launch", "picks": pick(site)})
        state = {"v": VERSION, "started": mkt.strftime("%Y-%m-%d"), "last_review": mkt.strftime("%Y-%m-%d"), "lists": lists}
        info["saved"] = save_state(state, status) if status in ("ok", "missing", "none") else "not saved (store unreachable or wrong)"
    elif review_due(state, mkt):
        state["lists"].append({"date": mkt.strftime("%Y-%m-%d"), "kind": "live", "label": "Weekly", "picks": pick(site)})
        state["last_review"] = mkt.strftime("%Y-%m-%d")
        info["saved"] = save_state(state, status)
    print(f"top10: record {status}, {len(state['lists'])} lists, {info['saved']}")
    return state, info


# --------------------------------------------------------------------------
# how a list has done
# --------------------------------------------------------------------------
def result(site, lst):
    """Per pick and for the list: growth from its close to the latest, against the S&P 500."""
    start = pd.Timestamp(lst["date"])
    picks = []
    for p in lst["picks"]:
        ser = _close(site, p["sym"])
        a = _at(ser, start) or p["px"]
        b = float(ser.iloc[-1]) if ser is not None and len(ser) else None
        g = (b / a - 1) if a and b else None
        picks.append(dict(p, last=b, ret=g))
    rets = [p["ret"] for p in picks if p["ret"] is not None]
    bser = _close(site, BENCH)
    ba, bb = _at(bser, start), (float(bser.iloc[-1]) if bser is not None and len(bser) else None)
    bench = (bb / ba - 1) if ba and bb else None
    avg = sum(rets) / len(rets) if rets else None
    beat = sum(1 for r in rets if bench is not None and r > bench)
    return {"picks": picks, "avg": avg, "bench": bench, "beat": beat, "n": len(rets),
            "days": (pd.Timestamp(site.asof).normalize() - start).days}


def curve(site, lst):
    """Daily equal-weight value of the list and the S&P 500, both from 100 at the list's close."""
    start = pd.Timestamp(lst["date"])
    b = _close(site, BENCH)
    if b is None:
        return None
    b = b[b.index >= start]
    if len(b) < 2:
        return None
    cols = []
    for p in lst["picks"]:
        s = _close(site, p["sym"])
        if s is None:
            continue
        s = s.reindex(b.index, method="ffill")
        a = _at(_close(site, p["sym"]), start)
        if a:
            cols.append(s / a)
    if not cols:
        return None
    basket = pd.concat(cols, axis=1).mean(axis=1) * 100
    return pd.DataFrame({"ten": basket, "spx": b / b.iloc[0] * 100}).dropna()


def spark(df, w=420, hgt=150):
    """A two-line SVG: the ten (violet) and the S&P 500 (grey)."""
    if df is None or len(df) < 2:
        return ""
    lo, hi = float(df.min().min()), float(df.max().max())
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = 6

    def pts(col):
        n = len(df) - 1
        return " ".join(f"{pad + (w - 2 * pad) * i / n:.1f},{hgt - pad - (hgt - 2 * pad) * (float(v) - lo) / (hi - lo):.1f}"
                        for i, v in enumerate(df[col]))
    base = hgt - pad - (hgt - 2 * pad) * (100 - lo) / (hi - lo)
    return (f'<svg class="t10-spark" viewBox="0 0 {w} {hgt}" preserveAspectRatio="none" role="img" aria-label="The ten against the S&amp;P 500 since the list was made">'
            f'<line x1="{pad}" x2="{w - pad}" y1="{base:.1f}" y2="{base:.1f}" class="t10-base"/>'
            f'<polyline points="{pts("spx")}" class="t10-spx"/><polyline points="{pts("ten")}" class="t10-ten"/></svg>')


# --------------------------------------------------------------------------
# the article
# --------------------------------------------------------------------------
TITLE = "Top 10 this week: our stake in the ground"
DEK = ("The ten stocks the most plays agree on, set after every Friday close and tracked against the S&P 500 from that close. "
       "Plus what the same rule would have picked one year, six months and three months ago, and how those did.")


def body(art, state, depth):
    from .render import money, pct, dir_cls, dlong, fill_bar, TK, LIGHT_ON, LIGHT_OFF
    from . import stockview as sv
    site = art.s
    h = art.h(depth)
    lists = sorted(state["lists"], key=lambda x: x["date"], reverse=True)
    live = [x for x in lists if x["kind"] == "live"]
    cur = live[0] if live else lists[0]
    res = {x["date"]: result(site, x) for x in lists}

    # this week's ten
    rows = ""
    for i, p in enumerate(res[cur["date"]]["picks"], 1):
        t = TK.get(p["sym"])
        o = sv.outlook(site, t) if t else {"upside": None, "ok": False}
        up = o["upside"] if o.get("ok") else None
        rk = ((site.meta.get(p["sym"]) or {}).get("risk") or {}).get("level")
        rows += (f'<tr><td class="t10-n">{i}</td><td><a class="sym" href="{h("stocks/" + p["slug"] + "/")}">{e(p["short"])}</a><span class="sym-sub">{e(p["name"])} · {e(p["group"])}</span></td>'
                 f'<td>{fill_bar(p["k"], p["n"])} <span class="mono small">{p["k"]} of {p["n"]}</span></td>'
                 f'<td class="r {dir_cls(p["m13"])}">{pct(p["m13"], d=0)}</td>'
                 f'<td class="r mono">{money(p["px"], p["cur"])}</td>'
                 + (f'<td class="r {dir_cls(p["ret"])}">{pct(p["ret"])}</td>' if res[cur["date"]]["days"] > 0 else '<td class="r muted">–</td>') +
                 f'<td class="r {dir_cls(up) if up is not None else "muted"}">{pct(up, d=0) if up is not None else "–"}</td>'
                 f'<td>{e(rk) if rk else "–"}</td>'
                 f'<td class="nowrap"><a class="small" href="{h("theory/")}?s={e(p["slug"])}">Test a theory</a></td></tr>')
    made = dlong(pd.Timestamp(cur["date"]))
    r0 = res[cur["date"]]
    so_far = ""
    if r0["days"] > 0 and r0["avg"] is not None and r0["bench"] is not None:
        so_far = (f' Since then the ten are <b class="{dir_cls(r0["avg"])}">{pct(r0["avg"])}</b> on average, against '
                  f'<b class="{dir_cls(r0["bench"])}">{pct(r0["bench"])}</b> for the S&amp;P 500.')
    this_week = f"""<section class="t10-now"><div class="sec-head"><h2 class="h2">This week's ten</h2><p>Set at the {made} close.{so_far}</p></div>
<div class="tbl-wrap"><table class="tbl t10-tbl"><thead><tr><th>#</th><th>Stock</th><th>Plays that hold it</th><th class="r">13 weeks</th><th class="r">Entry close</th><th class="r">Since</th>
<th class="r">Analysts' target</th><th>Crash exposure</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted small">Analysts' target is today's average 12-month target against the latest close, shown for context only: it plays no part in the pick.</p></section>"""

    # the scoreboard
    sb = ""
    for x in lists:
        r = res[x["date"]]
        tag = '<span class="tag">Reconstructed</span>' if x["kind"] == "reconstructed" else '<span class="tag live">Live</span>'
        diff = (r["avg"] - r["bench"]) if r["avg"] is not None and r["bench"] is not None else None
        beat = f'{r["beat"]} of {r["n"]}' if r["days"] > 0 else "–"
        sb += (f'<tr><td><a href="#list-{x["date"]}">{dlong(pd.Timestamp(x["date"]))}</a></td><td>{tag} <span class="muted small">{e(x["label"])}</span></td>'
               f'<td class="r {dir_cls(r["avg"])}">{pct(r["avg"]) if r["days"] > 0 else "–"}</td><td class="r {dir_cls(r["bench"])}">{pct(r["bench"]) if r["days"] > 0 else "–"}</td>'
               f'<td class="r {dir_cls(diff)}">{pct(diff) if diff is not None and r["days"] > 0 else "–"}</td>'
               f'<td class="r">{beat}</td></tr>')
    board = f"""<section><div class="sec-head"><h2 class="h2">Every list, and how it has done</h2><p>From each list's own close to the {dlong(site.asof)} close, equal weight, no fees or dividends.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>List made</th><th>Record</th><th class="r">The ten</th><th class="r">S&amp;P 500</th><th class="r">Difference</th><th class="r">Beat the S&amp;P</th></tr></thead><tbody>{sb}</tbody></table></div></section>"""

    # each list in full
    det = ""
    for x in lists:
        r = res[x["date"]]
        prs = "".join(f'<tr><td><a class="sym" href="{h("stocks/" + p["slug"] + "/")}">{e(p["short"])}</a><span class="sym-sub">{e(p["name"])}</span></td>'
                      f'<td class="r mono small">{p["k"]} of {p["n"]}</td><td class="r mono">{money(p["px"], p["cur"])}</td>'
                      f'<td class="r mono">{money(p["last"], p["cur"]) if p["last"] else "–"}</td><td class="r {dir_cls(p["ret"])}">{pct(p["ret"]) if r["days"] > 0 else "–"}</td></tr>'
                      for p in r["picks"])
        head = (f'{dlong(pd.Timestamp(x["date"]))} · {"Reconstructed" if x["kind"] == "reconstructed" else "Live"}'
                + (f' · the ten <b class="{dir_cls(r["avg"])}">{pct(r["avg"])}</b>, S&amp;P 500 <b class="{dir_cls(r["bench"])}">{pct(r["bench"])}</b>' if r["days"] > 0 and r["avg"] is not None and r["bench"] is not None else ""))
        det += (f'<details class="card t10-list" id="list-{x["date"]}"{" open" if x is cur or x["kind"] == "reconstructed" else ""}><summary>{head}</summary>'
                f'<div class="t10-body"><div class="t10-chart">{spark(curve(site, x))}<p class="small muted"><span class="t10-key ten"></span>The ten, equal weight <span class="t10-key spx"></span>S&amp;P 500, both from 100 at the list\'s close</p></div>'
                f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Plays then</th><th class="r">Entry close</th><th class="r">Latest</th><th class="r">Since</th></tr></thead><tbody>{prs}</tbody></table></div></div></details>')
    lists_html = f'<section><div class="sec-head"><h2 class="h2">Each list in full</h2><p>The live lists are the real record. The reconstructed ones show what the rule would have said.</p></div><div class="t10-lists">{det}</div></section>'

    rule = f"""<section class="card prose"><p class="eyebrow">The rule</p><ul>
<li><b>Stocks only.</b> No funds, indexes, sector baskets or coins.</li>
<li><b>Start light on.</b> The same Start/Stop light as every stock page: it turns Start when {round(LIGHT_ON * 100)}% of the plays hold the stock and stays on until that falls to {round(LIGHT_OFF * 100)}%.</li>
<li><b>Most plays first.</b> Ranked by the share of the {len(TIMED)} plays that hold the stock that night; ties go to the bigger 13-week price gain.</li>
<li><b>Two per group, at most.</b> So ten picks are not one bet ten times.</li>
<li><b>Set after each Friday close</b> (or the week's last close, when Friday is a holiday), and never changed afterwards. Each list is tracked from its own close against the S&amp;P 500.</li>
</ul><p class="eyebrow">Read this before the reconstructed lists</p><ul>
<li>They use only each play's calls and prices up to that week's close, so no later price leaks in.</li>
<li>But they use today's list of covered stocks and today's {len(TIMED)} plays. Some names are covered because they did well, and the plays were collected knowing which rules held up, so reconstructed results flatter the rule. The live lists, from the launch on, are the honest record.</li>
</ul><p class="small muted">This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Hypothetical results: no fees, taxes, slippage or dividends.</p></section>"""
    return this_week + board + lists_html + rule
