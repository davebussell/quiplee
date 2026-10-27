"""How the market read each earnings report (Dave, Oct 27, 2026: "track news on earnings as each of these pass and then
backstop the reasons why the market read the report the way they did").

For every report that has passed, from the data the site already keeps:

  the result      earnings per share against analysts' average estimate going in (Yahoo Finance, data/events)
  the move        the first session after the report against the stock's index, the same frame as "What moved it
                  lately" (newsevents.Series), set against its usual earnings-day move, and the five sessions after
  the outlook     what the company's own release said (data/earnings, read by Claude: tools/fetch_earnings.py) or,
                  without that, what the headlines after the report say about guidance
  expectations    how far it ran against its index in the 20 sessions before the report
  the group       how the other covered stocks in its group moved that session
  the Street      analysts' rating and price-target changes in the three sessions after (their read of the report)
  the coverage    the headlines from the report to three days after (data/news, tools/fetch_news.py), and what they
                  talk about

Then the reasons: each piece of evidence with the way it points, the ones that fit the move first, and the explanation
the evidence supports best. It says what fits and what cuts the other way; it never claims to know for certain, and it
says when nothing in the evidence explains the move.

    reports(site, t)        the stock's measured reports, newest first, each with its reasons and verdict
    section(site, t, h)     the stock page's "Earnings: how the market read each report" section ("" for funds and coins)
    earnings_page(site)     /earnings/: who reports next (soonest first) and how the market read the latest reports
    last_json(site, t)      the latest report in brief, for reads.json (the account page and the API)
"""
import datetime as dt
import html
import re

import numpy as np
import pandas as pd

from . import newsevents as NE
from .content import TICKERS

e = html.escape
PATH = "earnings/"
PRE_N = 20                  # sessions of run-up before a report
AFTER_N = 3                 # sessions after a report in which analysts' changes count as their read of it
NEWS_BEFORE = 2 * 3600      # coverage: from two hours before the report's time (releases go out before the call)...
NEWS_AFTER = 3 * 86400      # ...to three days after
TYPICAL_N, TYPICAL_MIN = 12, 4
RUNUP = 0.10                # a run-up (or a slide) this big against the index in the 20 sessions before sets expectations
QUIET_ABS, QUIET_REL = 0.01, 0.4   # a move under 1%, or under 40% of its usual earnings-day move, is "barely moved"
BIG_SUR = 5.0
RECENT_DAYS = 21            # /earnings/ "Just reported" window
SOON_DAYS = 14              # /earnings/ "Reporting next": the companies counted as reporting soon
SOON_SHOW = 20              # ...and the rows shown before "Show all"
MAX_HL = 8
LATEST_DAYS = 200           # a "latest report" older than this isn't shown as current (a stale calendar)

THEMES = [
    ("outlook", "the outlook", r"\b(guidance|outlook|forecasts?|full[- ]year|next quarter|projections?|targets? for (the )?(year|quarter))\b"),
    ("revenue", "revenue", r"\b(revenue|sales|top[- ]line)\b"),
    ("margins", "margins and profit", r"\b(margins?|profitab\w*|gross profit|operating (income|profit))\b"),
    ("demand", "demand", r"\b(demand|orders?|bookings?|backlog|subscribers?|subscriptions?|users|traffic|volumes?|deliveries)\b"),
    ("ai", "AI and data centers", r"\b(ai|artificial intelligence|data cent(er|re)s?|gpus?|accelerators?)\b"),
    ("costs", "costs and spending", r"\b(costs?|spending|capex|capital (expenditures?|spending)|expenses?)\b"),
    ("trade", "tariffs and trade", r"\b(tariffs?|trade (war|tensions)|export (curbs|controls|restrictions))\b"),
    ("returns", "buybacks and dividends", r"\b(buy-?backs?|repurchases?|dividends?)\b"),
    ("leaders", "management changes", r"\b(ceo|cfo|chief executive|steps? down|resign\w*|succession|retire\w*)\b"),
]
THEMES = [(k, lab, re.compile(rx, re.I)) for k, lab, rx in THEMES]
UP_WORDS = re.compile(r"\b(rises?|rose|jumps?|jumped|soars?|soared|surges?|surged|rall(y|ies|ied)|climbs?|climbed|gains?|gained|pops?|popped|"
                      r"spikes?|spiked|leaps?|leapt|rockets?|higher|up \d)", re.I)
DOWN_WORDS = re.compile(r"\b(falls?|fell|drops?|dropped|sinks?|sank|plunges?|plunged|slides?|slid|tumbles?|tumbled|slumps?|slumped|"
                        r"sheds?|dives?|dived|tanks?|tanked|craters?|cratered|lower|down \d|sell-?off)", re.I)
_W = r"(?:\W+\w+){0,3}?\W+"          # up to three words between
_RU = r"(beats?|beat|tops?|topped|exceeds?|exceeded|above|record|surges?|surged|jumps?|jumped|soars?|soared|strong|stronger|rises?|rose|grows?|grew|climbs?|climbed)"
_RD = r"(miss(es|ed)?|below|short|weak|weaker|declines?|declined|drops?|dropped|falls?|fell|slumps?|slumped|disappoint\w*|shrinks?|shrank)"
REV_UP = re.compile(rf"\b(revenue|sales){_W}{_RU}\b|\b{_RU}{_W}(revenue|sales)\b", re.I)
REV_DOWN = re.compile(rf"\b(revenue|sales){_W}{_RD}\b|\b{_RD}{_W}(revenue|sales)\b", re.I)
PREVIEW = re.compile(r"\?|\b(preview|what to expect|ahead of|expected to|set to report|to report|will report|before (its )?(earnings|results|report)|"
                     r"earnings (date|call schedule)|how to (watch|listen))\b", re.I)


def _R():
    from . import render
    return render


def pct(v, sign=True, d=1):
    return NE.pct(v, sign=sign, d=d)


def _day(ts64):
    return pd.Timestamp(ts64).strftime("%a %b %-d")


def _st(site):
    return NE._state(site)


# ------------------------------------------------------------------ the group's move on any session
def _peer(site, t, date):
    """(average move of the other covered stocks in its group that session, how many), or (None, n)."""
    cache = site.__dict__.setdefault("_er_grp", {})
    g = t.get("group")
    if g not in cache:
        cols = {}
        for x in _R().universe():
            if x["group"] == g and NE.is_stock(x) and x["sym"] in (site.prices or {}):
                cols[x["sym"]] = site.prices[x["sym"]]["close"].iloc[-800:]
        cache[g] = pd.DataFrame(cols).pct_change(fill_method=None) if cols else None
    df = cache[g]
    if df is None or date not in df.index:
        return None, 0
    row = df.loc[date].drop(labels=[t["sym"]], errors="ignore").dropna()
    return (float(row.mean()), len(row)) if len(row) >= NE.PEER_MIN else (None, len(row))


# ------------------------------------------------------------------ the coverage
def _coverage(t, ts):
    """Headlines from just before the report to three days after, newest last, without previews, questions or
    fund-holding filler (and never one that names a company the site doesn't: newsevents._news)."""
    seen, out = set(), []
    for it in NE._news(t["slug"]):
        if it.get("k") != "news":
            continue
        s = NE._secs(it.get("t"))
        h = (it.get("h") or "").strip()
        if not s or not h or not (ts - NEWS_BEFORE <= s <= ts + NEWS_AFTER):
            continue
        if PREVIEW.search(h) or NE.FILLER.search(h):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", h.lower()).strip()[:70]
        if key in seen:
            continue
        seen.add(key)
        way = 1 if UP_WORDS.search(h) and not DOWN_WORDS.search(h) else -1 if DOWN_WORDS.search(h) and not UP_WORDS.search(h) else 0
        ru, rd = bool(REV_UP.search(h)), bool(REV_DOWN.search(h))
        out.append({"ts": s, "h": h, "s": it.get("s") or "", "u": it.get("u") or "", "cat": NE.news_cat(h), "way": way,
                    "th": [k for k, _, rx in THEMES if rx.search(h)], "rev": 1 if ru and not rd else -1 if rd and not ru else 0})
    out.sort(key=lambda x: x["ts"])
    return out


# ------------------------------------------------------------------ one report
def _measure(site, t, x, prior):
    """The record of one report (an earnings event from newsevents) and its evidence; None until its first session is in."""
    st = _st(site)
    S = st.S(t)
    i = x["r"]
    if S is None or x["d1"] is None or i is None or i >= S.n or i < PRE_N + 1:
        return None
    b = i - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        pre = (S.c[b] / S.c[b - PRE_N]) - (S.bc[b] / S.bc[b - PRE_N])
    pre = float(pre) if np.isfinite(pre) else None
    typ_xs = [abs(p["d1"]) for p in prior[-TYPICAL_N:] if p.get("d1") is not None]
    typ = float(np.median(typ_xs)) if len(typ_xs) >= TYPICAL_MIN else None
    date = S.dates[i]
    peer, n_peer = _peer(site, t, date)
    rep_et = NE._et(x["ts"])
    rec = {"ts": x["ts"], "rday": rep_et.strftime("%Y-%m-%d"), "tm": NE._timing(rep_et), "i": i, "date": date,
           "est": x["x"].get("est"), "act": x["x"].get("act"), "sur": x["x"].get("sur"), "cat": x["cat"],
           "ab": float(x["d1"]), "raw": float(S.raw[i]), "mkt": float(S.mkt[i]), "d5": x["d5"], "z": x["z"],
           "typ": typ, "pre": pre, "peer": peer, "n_peer": n_peer,
           "peer_ab": None if peer is None else float(peer - S.mkt[i])}
    with np.errstate(divide="ignore", invalid="ignore"):
        gap = S.o[i] / S.c[i - 1] - 1          # the opening price after the report against the last close before it
    rec["gap"] = float(gap) if np.isfinite(gap) else None
    # the company's own release (read by Claude), the headlines, and the analysts after
    evs = st.E(t)
    rel = [y for y in evs if y["s"] == "release" and abs(y["r"] - i) <= 1]
    rec["rel"] = ({"dir": rel[0]["x"].get("dir"), "h": rel[0]["h"], "period": rel[0]["x"].get("period", "")} if rel else None)
    hl = _coverage(t, x["ts"])
    rec["hl"] = hl
    rec["g_up"] = sum(1 for y in hl if y["cat"] == "n-guide-up")
    rec["g_down"] = sum(1 for y in hl if y["cat"] == "n-guide-down")
    th = {}
    for y in hl:
        for k in y["th"]:
            th[k] = th.get(k, 0) + (2 if y["way"] else 1)       # headlines that describe the move count double
    rec["themes"] = sorted(((k, n) for k, n in th.items()), key=lambda kv: -kv[1])
    rec["rev_up"] = sum(1 for y in hl if y["rev"] > 0)
    rec["rev_down"] = sum(1 for y in hl if y["rev"] < 0)
    rec["hl_up"] = sum(1 for y in hl if y["way"] > 0)
    rec["hl_down"] = sum(1 for y in hl if y["way"] < 0)
    up = down = 0
    ex = []
    for y in evs:
        if y["s"] != "rating" or not (i <= y["r"] <= i + AFTER_N - 1):
            continue
        d = NE.CATS[y["cat"]][2]
        n = len(y["x"].get("firms") or [1])
        if d > 0:
            up += n
        elif d < 0:
            down += n
        for f in (y["x"].get("firms") or [])[:2]:
            ex.append((y["cat"], f))
    rec["st_up"], rec["st_down"], rec["st_ex"] = up, down, ex[:4]
    rec["dir"] = _dir(rec)
    rec["reasons"] = reasons(rec, t, _cur(site, t))
    rec["verdict"], rec["lead"] = verdict(rec, t)
    return rec


def _dir(r):
    lim = max(QUIET_ABS, QUIET_REL * r["typ"]) if r["typ"] else QUIET_ABS
    return 0 if abs(r["ab"]) < lim else (1 if r["ab"] > 0 else -1)


def reports(site, t):
    """Every measured report on t, newest first (cached on the site)."""
    cache = site.__dict__.setdefault("_er", {})
    if t["sym"] in cache:
        return cache[t["sym"]]
    out = []
    if NE.is_stock(t):
        st = _st(site)
        if st.S(t) is not None:
            earn = [x for x in st.E(t) if x["s"] == "earn"]
            earn.sort(key=lambda x: x["ts"])
            for j, x in enumerate(earn):
                rec = _measure(site, t, x, earn[:j])
                if rec:
                    out.append(rec)
    out.reverse()
    cache[t["sym"]] = out
    return out


# ------------------------------------------------------------------ the reasons
IN_LINE = -2.0              # EPS from 2% under the estimate to 5% over it counts as in line
WEAK_MISS = -5.0            # a miss smaller than this explains little of a big move
BIG_MOVE = 0.03             # "a bigger move than usual" needs at least this much against the index
CUR_SIGN = {"USD": "$", "CAD": "C$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$", "CHF": "CHF ", "DKK": "DKK ", "TWD": "NT$"}


def _theme_words(r, n=2):
    lab = dict((k, l) for k, l, _ in THEMES)
    top = [(lab[k], c) for k, c in r["themes"][:n] if c >= 2]
    return " and ".join(l for l, _ in top)


def _cur(site, t):
    """The sign of the currency a company reports in (its EPS and Yahoo's estimates are in it), or "" when unknown."""
    code = ((site.fund or {}).get(t["sym"]) or {}).get("financialCurrency") if site is not None else None
    return CUR_SIGN.get(code, (code + " ") if code else "")


def _eps(v, cur="$", d=2):
    if v is None:
        return "–"
    return ("−" if v < 0 else "") + f"{cur}{abs(v):,.{d}f}"


def _pair(r, cur):
    """'$1.85 against $1.77' (three decimals when the two would print the same)."""
    a, b = r["act"], r["est"]
    d = 3 if (a is not None and b is not None and round(a, 2) == round(b, 2) and a != b) else 2
    return f"{_eps(a, cur, d)} against {_eps(b, cur, d)}"


def _n(k, one, many=None):
    return f"{'no' if k == 0 else k} {one if k == 1 else (many or one + 's')}"


def _say(k, what):
    """'One headline after the report says X' / '3 headlines after the report say X'."""
    return f"{'One headline' if k == 1 else str(k) + ' headlines'} after the report {'says' if k == 1 else 'say'} {what}"


def result_way(r):
    """(+1 beat, 0 in line, -1 miss, or None with no result; whether a miss is small)."""
    est, act, sur = r["est"], r["act"], r["sur"]
    if act is None or est is None:
        return None, False
    if est <= 0 or act < 0:           # a loss expected or reported: a percentage means little, so the amounts decide
        dif, tol = act - est, max(0.02, 0.05 * abs(est))
        return (1 if dif > tol else -1 if dif < -tol else 0), False
    if sur is None:
        return None, False
    if sur >= BIG_SUR:
        return 1, False
    if sur >= IN_LINE:
        return 0, False
    return -1, sur > WEAK_MISS


def reasons(r, t, cur="$"):
    """[{k, text, way (+1 up, -1 down, 0 neither), kind ('cause' | 'street' | 'context')}]: the evidence, one line each.
    A 'cause' line counts for or against the move; 'street' is analysts afterward; 'context' never decides."""
    bench = NE.BENCH_NAME.get(t.get("bench"), "its index")
    d = r["dir"]
    out = []
    rw, weak = result_way(r)
    if rw is not None:
        loss = r["est"] <= 0 or r["act"] < 0
        if loss:
            word = {1: "came in above", -1: "came in below", 0: "matched"}[rw]
            txt = f"Earnings per share {word} analysts' average estimate: {_pair(r, cur)}."
        elif rw > 0:
            txt = f"Earnings per share beat analysts' average estimate by {r['sur']:.0f}% ({_pair(r, cur)})."
        elif rw == 0:
            txt = f"Earnings per share were in line with analysts' average estimate ({r['sur']:+.1f}%, {_pair(r, cur)})."
        else:
            txt = f"Earnings per share missed analysts' average estimate by {abs(r['sur']):.0f}% ({_pair(r, cur)})."
        out.append({"k": "result", "way": rw, "kind": "cause", "weak": weak, "text": txt})
    rel = r["rel"]
    if rel and rel["dir"] in ("raised", "cut", "withdrawn", "kept", "started"):
        way = {"raised": 1, "cut": -1, "withdrawn": -1}.get(rel["dir"], 0)
        word = {"raised": "raised its outlook", "cut": "cut its outlook", "withdrawn": "withdrew its outlook", "kept": "kept its outlook",
                "started": "gave an outlook for the first time"}[rel["dir"]]
        out.append({"k": "outlook", "way": way, "kind": "cause", "text": f"The company's own release {word} (read from the release by Claude)."})
    elif r["g_up"] and not r["g_down"]:
        out.append({"k": "outlook", "way": 1, "kind": "cause", "text": _say(r["g_up"], "the outlook was raised or strong") + "."})
    elif r["g_down"] and not r["g_up"]:
        out.append({"k": "outlook", "way": -1, "kind": "cause", "text": _say(r["g_down"], "the outlook was cut or weak, or warn") + "."})
    elif r["g_up"] and r["g_down"]:
        out.append({"k": "outlook", "way": 0, "kind": "cause", "text": f"Headlines disagree on the outlook: {r['g_up']} {'says' if r['g_up'] == 1 else 'say'} raised or strong, "
                                                                     f"{r['g_down']} {'says' if r['g_down'] == 1 else 'say'} cut or weak."})
    if r["rev_up"] and not r["rev_down"]:
        out.append({"k": "revenue", "way": 1, "kind": "cause", "text": _say(r["rev_up"], "revenue beat or grew strongly") + "."})
    elif r["rev_down"] and not r["rev_up"]:
        out.append({"k": "revenue", "way": -1, "kind": "cause", "text": _say(r["rev_down"], "revenue missed, fell or disappointed") + "."})
    pre = r["pre"]
    if pre is not None and abs(pre) >= RUNUP:
        up = pre > 0
        txt = (f"It had {'run up' if up else 'fallen'} {pct(abs(pre), sign=False, d=0)} against {bench} in the {PRE_N} sessions before the report, "
               f"which set a {'high' if up else 'low'} bar.")
        # expectations decide only when the result met them: a beat or an in-line report after a run-up that still fell,
        # or a miss or an in-line report after a slide that still rose
        if up and rw in (1, 0) and d < 0:
            out.append({"k": "expect", "way": -1, "kind": "cause", "text": txt})
        elif not up and rw in (-1, 0) and d > 0:
            out.append({"k": "expect", "way": 1, "kind": "cause", "text": txt})
        else:
            out.append({"k": "expect", "way": 0, "kind": "context", "text": txt})
    pab = r["peer_ab"]
    if pab is not None and abs(pab) >= 0.01:
        if (pab > 0) == (r["ab"] > 0) and abs(pab) >= 0.5 * abs(r["ab"]) and d:
            out.append({"k": "group", "way": 1 if pab > 0 else -1, "kind": "cause",
                        "text": f"Its group moved the same way: the other {r['n_peer']} {t['group']} stocks Be The Puck covers averaged {pct(pab)} against the index that "
                                "session. Part of the move was shared, though the evidence can't tell whether the group was reacting to this report or to something else."})
        elif (pab > 0) != (r["ab"] > 0) and d:
            out.append({"k": "group", "way": 0, "kind": "context",
                        "text": f"Its group went the other way ({pct(pab)} against the index on average), so this move was its own."})
    if r["tm"] in ("a", "b") and r["gap"] is not None:
        if abs(r["gap"]) >= 0.02 and (r["gap"] > 0) == (r["raw"] > 0) and abs(r["raw"]) <= 0.5 * abs(r["gap"]):
            out.append({"k": "fade", "way": 0, "kind": "context", "text": f"It opened {pct(r['gap'])} and closed {pct(r['raw'])}: the first read faded during the session."})
        elif abs(r["raw"]) >= 0.02 and abs(r["gap"]) >= 0.01 and (r["gap"] > 0) != (r["raw"] > 0):
            out.append({"k": "fade", "way": 0, "kind": "context", "text": f"It opened {pct(r['gap'])} but closed {pct(r['raw'])}: the read changed during the session."})
    if d and r["d5"] is not None:
        if (r["d5"] > 0) != (r["ab"] > 0) and abs(r["d5"]) >= 0.02:
            out.append({"k": "after", "way": 0, "kind": "context", "text": f"Over five sessions it finished {pct(r['d5'])} against the index: the first session's read didn't last."})
        elif (r["d5"] > 0) == (r["ab"] > 0) and abs(r["d5"]) >= 1.5 * abs(r["ab"]) and abs(r["d5"]) >= 0.03:
            out.append({"k": "after", "way": 0, "kind": "context", "text": f"Over five sessions it went further, to {pct(r['d5'])} against the index."})
    if abs(r["mkt"]) >= 0.015:
        out.append({"k": "market", "way": 0, "kind": "context", "text": f"{bench[0].upper() + bench[1:]} itself moved {pct(r['mkt'])} that session; the move above is net of it."})
    if r["st_up"] + r["st_down"] >= 2:
        way = 1 if r["st_up"] > r["st_down"] else -1 if r["st_down"] > r["st_up"] else 0
        out.append({"k": "street", "way": way, "kind": "street",
                    "text": f"In the first {AFTER_N} sessions after the report, analysts made {_n(r['st_up'], 'upgrade or target raise', 'upgrades or target raises')} and "
                            f"{_n(r['st_down'], 'downgrade or target cut', 'downgrades or target cuts')}."})
    tw = _theme_words(r)
    if tw:
        out.append({"k": "coverage", "way": 0, "kind": "context", "text": f"The coverage after the report ({_n(len(r['hl']), 'headline')}) talked most about {tw}."})
    return out


LEAD_WORDS = {"outlook": "the outlook", "result": "the result itself", "revenue": "revenue", "expect": "expectations going in", "group": "a move across its group"}


def verdict(r, t):
    """(one to three sentences on why it moved, the key of the best fit or None)."""
    d = r["dir"]
    rs = r["reasons"]
    causes = [x for x in rs if x["kind"] == "cause"]
    street = next((x for x in rs if x["kind"] == "street"), None)
    res = next((x for x in causes if x["k"] == "result"), None)
    unchecked = not r["hl"] and not r["rel"]
    if d == 0:
        txt = (f"By the close of its first session after the report it had barely moved against its index ({pct(r['ab'])}; "
               f"{'±' + pct(r['typ'], sign=False) + ' is usual for its earnings days' if r['typ'] else 'a small move'}).")
        if r["tm"] in ("a", "b") and r["gap"] is not None and abs(r["gap"]) >= max(0.02, r["typ"] or 0):
            txt += f" It had opened {pct(r['gap'])}."
        if r["d5"] is not None and abs(r["d5"]) >= max(0.03, r["typ"] or 0):
            txt += f" Over five sessions it moved {pct(r['d5'])} against the index."
        if res and res["way"] == 0:
            txt += " The result was in line with the estimate."
        elif res and r["sur"] is not None and not (r["est"] <= 0 or r["act"] < 0):
            txt += f" A {'beat' if res['way'] > 0 else 'miss'} of {abs(r['sur']):.0f}% didn't move it much by the close."
        return txt, None
    fit = [x for x in causes if x["way"] == d]
    against = [x for x in causes if x["way"] == -d]
    lead = None
    for k in ("outlook", "result", "revenue", "expect", "group"):
        if any(x["k"] == k for x in fit):
            lead = k
            break
    word = "rose" if d > 0 else "fell"
    if lead is None:
        tw = _theme_words(r)
        if unchecked:
            txt = (f"Nothing in the result, the run-up before or its group explains why it {word}. No headlines from those days are in "
                   "Be The Puck's archive, so the outlook and the coverage weren't checked.")
        else:
            txt = (f"Nothing in the result, the outlook, the run-up before or its group explains why it {word}"
                   + (f"; the coverage talked most about {tw} (see the headlines)." if tw else "; the headlines from those days don't point to one theme."))
    else:
        txt = f"Best fit from the evidence: {LEAD_WORDS[lead]}."
        if lead == "result" and res and res.get("weak") and abs(r["ab"]) >= max(BIG_MOVE, r["typ"] or 0):
            txt = f"Best fit from the evidence: the result itself, though a miss of {abs(r['sur']):.0f}% explains little of a move this size."
        if lead == "expect" and res and res["way"] in (0, -d):
            txt = (f"Best fit from the evidence: expectations going in. The result {'met them' if res['way'] == 0 else ('beat them' if d < 0 else 'missed them')}, "
                   f"yet it {word} after {'a big run-up' if d < 0 else 'a long slide'} before the report.")
        others = [LEAD_WORDS[x["k"]] for x in fit if x["k"] != lead and x["k"] in LEAD_WORDS]
        if others:
            txt += f" Also fits: {', '.join(others)}."
        if against:
            txt += " Cut the other way: " + ", ".join(LEAD_WORDS.get(x["k"], x["k"]) for x in against) + "."
        if unchecked:
            txt += " The outlook wasn't checked: no headlines from those days are in Be The Puck's archive."
    if street and street["way"] == d:
        txt += " Analysts' changes afterward went the same way as the stock."
    elif street and street["way"] == -d:
        txt += " Analysts' changes afterward went the other way."
    if r["typ"] and abs(r["ab"]) >= max(BIG_MOVE, 1.5 * r["typ"]):
        txt += " It was a bigger move than usual for its earnings days."
    return txt, lead


# ------------------------------------------------------------------ the stock page
def _when(r):
    d = dt.date.fromisoformat(r["rday"])
    tm = {"a": ", after the close", "b": ", before the open", "d": ", during the day"}.get(r["tm"], "")
    return d.strftime("%a %b %-d, %Y") + tm


def _move_line(r, bench):
    cls = "up" if r["ab"] > 0 else "down"
    typ = f" · ±{pct(r['typ'], sign=False)} is its usual earnings-day move" if r["typ"] else ""
    d5 = f" · {pct(r['d5'])} over five sessions" if r["d5"] is not None else ""
    return (f'<p class="er-move"><b class="{cls}">{pct(r["ab"])}</b> against {e(bench)} on {_day(r["date"])}'
            f'<span class="muted small"> (the stock {pct(r["raw"])}, {e(bench)} {pct(r["mkt"])}){typ}{d5}</span></p>')


def _sur_text(r):
    """'+12%' against the estimate, or the amounts when a loss was expected or reported (a percentage means little then)."""
    if r["act"] is None or r["est"] is None:
        return None
    if r["est"] <= 0 or r["act"] < 0 or r["sur"] is None:
        return f'{_eps(r["act"], "")} vs {_eps(r["est"], "")}'
    return format(r["sur"], "+.0f") + "%"


def _facts(r, t, bench, cur="$"):
    bits = []
    rw, _ = result_way(r)
    if rw is not None:
        cls = {1: "up", -1: "down", 0: ""}[rw]
        loss = r["est"] <= 0 or r["act"] < 0
        bits.append(("Result", (f'<b class="{cls}">{_pair(r, cur)}</b>' if loss else
                                f'<b class="{cls}">{r["sur"]:+.0f}%</b> vs estimate <span class="muted">({_pair(r, cur).replace(" against ", " vs ")})</span>')))
    if r["rel"] and r["rel"]["dir"]:
        bits.append(("Outlook", e({"raised": "Raised", "cut": "Cut", "withdrawn": "Withdrawn", "kept": "Kept", "started": "First given", "mixed": "Mixed", "none": "None given"}.get(r["rel"]["dir"], r["rel"]["dir"]))
                     + ' <span class="muted">(release)</span>'))
    elif r["g_up"] or r["g_down"]:
        bits.append(("Outlook", f'{r["g_up"]} up · {r["g_down"]} down <span class="muted">(headlines)</span>'))
    if r["pre"] is not None:
        bits.append((f"{PRE_N} sessions before", f'<span class="{"up" if r["pre"] > 0 else "down"}">{pct(r["pre"], d=0)}</span> vs index'))
    if r["peer_ab"] is not None:
        bits.append(("Its group vs index", pct(r["peer_ab"])))
    if r["st_up"] or r["st_down"]:
        bits.append(("Analysts after", f'{r["st_up"]} raised · {r["st_down"]} cut'))
    return '<dl class="er-facts">' + "".join(f"<div><dt>{e(k)}</dt><dd>{v}</dd></div>" for k, v in bits) + "</dl>"


def _reasons_html(r):
    d = r["dir"]
    lis = ""
    for x in sorted(r["reasons"], key=lambda x: (0 if (d and x["way"] == d) else 2 if (d and x["way"] == -d) else 1)):
        tag = ("fit", "Fits the move") if d and x["way"] == d else ("against", "Cuts the other way") if d and x["way"] == -d else ("ctx", "Context")
        lis += f'<li class="er-r {tag[0]}"><span class="er-tag">{tag[1]}</span><span>{e(x["text"])}</span></li>'
    return f'<ul class="er-reasons">{lis}</ul>' if lis else ""


def _news_html(r, short):
    hl = r["hl"]
    if not hl:
        return '<p class="small muted">No coverage from those days is in Be The Puck\'s news archive yet.</p>'
    shown = sorted(hl, key=lambda y: (-(1 if y["way"] else 0) - (1 if y["cat"] else 0) - len(y["th"]) * 0.1, y["ts"]))[:MAX_HL]
    shown.sort(key=lambda y: y["ts"])
    lis = "".join(f'<li><a href="{e(y["u"])}" rel="noopener nofollow" target="_blank">{e(y["h"])}</a>'
                  f'<span class="muted small"> · {e(y["s"])} · {e(NE._et(y["ts"]).strftime("%b %-d, %-I:%M %p"))}</span></li>' for y in shown)
    more = len(hl) - len(shown)
    return (f'<details class="er-news"><summary>The coverage: {_n(len(hl), "headline")} from the report to three days after</summary>'
            f'<ul>{lis}</ul>' + (f'<p class="small muted">And {more} more in the archive.</p>' if more > 0 else "") + "</details>")


def _short_why(r):
    if r["dir"] == 0:
        return "Barely moved"
    if r["lead"] is None:
        return "Not explained by the evidence"
    return LEAD_WORDS[r["lead"]][0].upper() + LEAD_WORDS[r["lead"]][1:]


def section(site, t, h):
    """'Earnings: how the market read each report' on a stock page; "" for funds, indexes and coins, or with no report."""
    reps = reports(site, t)
    if not reps or (site.asof - pd.Timestamp(reps[0]["date"])).days > LATEST_DAYS:      # no report in the last ~6 months: nothing current to read
        return ""
    bench = NE.BENCH_NAME.get(t.get("bench"), "its index")
    nx = NE.next_reports(site).get(t["sym"])
    nxt = f" Next report: {e(NE.next_words(nx, site.asof.year))}." if nx else ""
    r = reps[0]
    last = (f'<article class="card er-last"><p class="eyebrow">Latest report · {e(_when(r))}</p>{_move_line(r, bench)}{_facts(r, t, bench, _cur(site, t))}'
            f'<p class="er-verdict">{e(r["verdict"])}</p>{_reasons_html(r)}{_news_html(r, t["short"])}</article>')
    rows = ""
    for x in reps[:8]:
        cls = "up" if x["ab"] > 0 else "down"
        sur = _sur_text(x) or "–"
        rows += (f'<tr><td data-v="{x["ts"]}">{e(dt.date.fromisoformat(x["rday"]).strftime("%b %-d, %Y"))}</td>'
                 f'<td class="r" data-v="{x["sur"] if x["sur"] is not None else ""}">{sur}</td>'
                 f'<td class="r {cls}" data-v="{x["ab"]:.5f}">{pct(x["ab"])}</td>'
                 f'<td class="r adv-col" data-v="{x["d5"] if x["d5"] is not None else ""}">{pct(x["d5"])}</td>'
                 f'<td class="r adv-col" data-v="{x["pre"] if x["pre"] is not None else ""}">{pct(x["pre"], d=0)}</td>'
                 f'<td>{e(_short_why(x))}</td></tr>')
    table = (f'<div class="tbl-wrap"><table class="tbl er-tbl"><thead><tr><th>Report</th><th class="r" data-sort-first="desc">EPS vs estimate</th>'
             f'<th class="r" data-sort-first="desc">First session vs index</th><th class="r adv-col" data-sort-first="desc">Five sessions</th>'
             f'<th class="r adv-col" data-sort-first="desc">{PRE_N} sessions before</th><th>Best fit from the evidence</th></tr></thead><tbody>{rows}</tbody></table></div>'
             f'<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the other two columns</button>: five sessions after, and the run-up before.</p>'
             if len(reps) > 1 else "")
    return (f'<section class="er" id="earnings" aria-labelledby="er-h"><div class="sec-head"><h2 class="h2" id="er-h">Earnings: how the market read each report</h2>'
            f'<p>The result, the first session\'s move against {e(bench)}, and the evidence for why it went that way: the outlook, what was expected going in, '
            f'its group, analysts\' changes after and the coverage.{nxt} <a href="{h(PATH)}">Every company\'s next report</a></p></div>'
            f'{last}{table}<p class="small muted">EPS estimates and results from Yahoo Finance; headlines from Be The Puck\'s news archive. '
            f'"Best fit" weighs the evidence the site has; it can\'t see everything a trader saw that day, and it says when nothing fits.</p></section>')


# ------------------------------------------------------------------ the account page and the API
def last_json(site, t):
    """The latest report in brief ({d, tm, sur, ab, mv, why, dir}) for reads.json, or None."""
    reps = reports(site, t)
    if not reps or (site.asof - pd.Timestamp(reps[0]["date"])).days > LATEST_DAYS:
        return None
    r = reps[0]
    return {"d": r["rday"], "tm": r["tm"], "sur": None if r["sur"] is None else round(float(r["sur"]), 1), "ab": round(r["ab"], 4),
            "raw": round(r["raw"], 4), "why": r["verdict"], "lead": _short_why(r), "dir": r["dir"]}


# ------------------------------------------------------------------ /earnings/
def earnings_page(site):
    R = _R()
    path, depth = PATH, 1
    h = lambda x: site.href(depth, x)
    from .factors import score as fx_score, SIG_WORD, SIG_CLS
    NX = NE.next_reports(site)
    asof = site.asof
    soon, recent = [], []
    for t in R.universe():
        if not NE.is_stock(t) or (t["sym"], "buy-and-hold") not in site.R:
            continue
        reps = reports(site, t)
        last = reps[0] if reps and (asof - pd.Timestamp(reps[0]["date"])).days <= LATEST_DAYS else None
        typ = last["typ"] if last else (reps[0]["typ"] if reps else None)
        if t["sym"] in NX:
            soon.append((NX[t["sym"]], t, last, typ))
        if last is not None and (asof - pd.Timestamp(last["date"])).days <= RECENT_DAYS:
            recent.append((last, t))
    soon.sort(key=lambda x: x[0][2])
    recent.sort(key=lambda x: -x[0]["ts"])

    def sig_cell(t):
        sc, sg, _ = fx_score(site, t)
        return (f'<td class="nowrap" data-v="{sc if sc is not None else ""}" data-ps-signal data-with-score>'
                + (f'<span class="sig-pill {SIG_CLS[sg]}">{SIG_WORD[sg]}</span> <b class="sig-n">{sc}</b>' if sc is not None else "–") + "</td>")

    def stock_cell(t, anchor=""):
        return (f'<td class="stick"><a class="sym" href="{h("stocks/" + t["slug"] + "/")}{anchor}">{e(t["short"])}</a>'
                f'<span class="sym-sub">{e(t["name"])}</span></td>')

    srows = ""
    for k, (nx, t, last, typ) in enumerate(soon):
        within = k < SOON_SHOW
        lastmv = (f'<span class="{"up" if last["ab"] > 0 else "down"}">{pct(last["ab"])}</span>'
                  + (f' <span class="muted small">EPS {_sur_text(last)}</span>' if _sur_text(last) else "")) if last else '<span class="muted">–</span>'
        srows += (f'<tr data-sym="{e(t["sym"])}"{"" if within else " data-later"}>{stock_cell(t)}'
                  + R.next_cell(nx, asof.year) + sig_cell(t) +
                  f'<td class="r" data-v="{typ if typ is not None else ""}">{("±" + pct(typ, sign=False)) if typ else "–"}</td>'
                  f'<td class="r adv-col" data-v="{last["ab"] if last else ""}">{lastmv}</td>'
                  f'<td class="small adv-col">{e(t["group"])}</td></tr>')
    rrows = ""
    for r, t in recent:
        cls = "up" if r["ab"] > 0 else "down"
        rrows += (f'<tr data-sym="{e(t["sym"])}">{stock_cell(t, "#earnings")}'
                  f'<td class="nowrap ne-cell" data-v="{r["ts"]}">{e(dt.date.fromisoformat(r["rday"]).strftime("%b %-d"))}'
                  f'<small class="ne-t">{ {"a": "after close", "b": "before open", "d": "during day"}.get(r["tm"], "") }</small></td>'
                  f'<td class="r" data-v="{r["sur"] if r["sur"] is not None else ""}">{_sur_text(r) or "–"}</td>'
                  f'<td class="r {cls}" data-v="{r["ab"]:.5f}"><b>{pct(r["ab"])}</b></td>'
                  f'<td class="er-why">{e(r["verdict"])}</td></tr>')
    n_soon = sum(1 for nx, *_ in soon if (dt.date.fromisoformat(nx[0]) - asof.date()).days <= SOON_DAYS)
    body = f"""<section class="pair-head"><p class="eyebrow">Earnings</p><h1 class="h1">Who reports next, and how the market read the last reports</h1>
<p class="lede">Every covered company's next earnings report, soonest first, with how much its stock usually moves on the day. Below, the reports of the last three weeks: the result, the first session's move against the index, and the evidence for why the market read it that way.</p>
<div class="chips fam-chips"><a href="#next">Reporting next</a><a href="#reported">Just reported ({len(recent)})</a></div></section>

<section id="next" aria-labelledby="er-next-h"><div class="sec-head"><h2 class="h2" id="er-next-h">Reporting next</h2>
<p>{n_soon} companies report in the next {SOON_DAYS} days. The usual move is the median size of its first-session moves against its index over its last {TYPICAL_N} reports, either way.</p></div>
<div class="tbl-wrap"><table class="tbl er-soon" data-mine><thead><tr><th class="stick">Stock</th><th data-sort-first="asc">Reports</th><th data-sort-first="desc">Your signal</th>
<th class="r" data-sort-first="desc">Usual move</th><th class="r adv-col" data-sort-first="desc">Last time</th><th class="adv-col">Group</th></tr></thead><tbody>{srows}</tbody></table></div>
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the other two columns</button>: the move after its last report, and its group.</p>
<p class="small"><button type="button" class="linkish" data-er-later>Show all {len(soon)} upcoming reports</button></p></section>

<section id="reported" aria-labelledby="er-past-h"><div class="sec-head"><h2 class="h2" id="er-past-h">Just reported: how the market read it</h2>
<p>The reports of the last {RECENT_DAYS} days, newest first. Each stock page has the full read: the evidence line by line and the headlines.</p></div>
{f'<div class="tbl-wrap"><table class="tbl er-past" data-mine><thead><tr><th class="stick">Stock</th><th data-sort-first="desc">Reported</th><th class="r" data-sort-first="desc">EPS vs estimate</th><th class="r" data-sort-first="desc">First session vs index</th><th>Why, from the evidence</th></tr></thead><tbody>{rrows}</tbody></table></div>' if rrows else '<p class="muted">No covered company has reported in the last three weeks.</p>'}
</section>

<section class="card prose"><p class="eyebrow">How it's read</p>
<p>The move is the first session after the report against the stock's index (the S&amp;P 500, or the S&amp;P/TSX for Toronto listings), so news after the close is read on the next day. The evidence is the result against analysts' average estimate, the outlook (from the company's own release where Be The Puck has read it, otherwise from the headlines), how far the stock had run against its index in the {PRE_N} sessions before, how its group moved that day, analysts' rating and target changes in the {AFTER_N} sessions after, and what the coverage talked about. The best fit is the strongest piece of evidence that points the way the stock moved; when none does, it says so. <a href="{h(NE.GUIDE)}">How each kind of news has moved stocks</a>.</p>
<p class="small muted">Report dates, estimates and results from Yahoo Finance's calendar; dates can move, and some are estimates until the company confirms them. Headlines from Be The Puck's news archive. This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.</p></section>"""
    site.add(path, site.shell(path, "Earnings calendar: who reports next, and how the market read the last reports",
                              "Every covered company's next earnings report, soonest first, with its usual move, and how the market read the latest reports: "
                              "the result, the first session against the index, and the evidence for why.",
                              body, active="stocks/", scripts=("assets/plays.js", "assets/earnings.js")))
