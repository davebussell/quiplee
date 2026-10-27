"""The classics (/classics/): strategies people don't talk about anymore, the people behind them, and the plays on
Be The Puck that descend from them (Dave, Oct 27, 2026: "get into the classics ... I think we can close the gap
between the people and the plays").

Each classic (classics.json, researched and sourced Oct 27, 2026) has the story, the original rule, whether it can be
tested on the site's data, the plays and people it leads to, what couldn't be confirmed, and its sources. Play pages
and analyst pages link back to the classics that mention them (see_also)."""
import html
import json
import os

from .content import PLAY, THINKER, FAMILY
from .render import play_name_html, pct
from .media import page_art, PAGE_ART

e = html.escape
PATH = "classics/"

with open(os.path.join(os.path.dirname(__file__), "classics.json"), encoding="utf-8") as _f:
    CLASSICS = json.load(_f)
for _c in CLASSICS:
    _c["related_plays"] = [s for s in (_c.get("related_plays") or []) if s in PLAY]
    _c["related_thinkers"] = [s for s in (_c.get("related_thinkers") or []) if s in THINKER]

def verdict(c):
    """(word, class): whether the classic's own rule runs on the site already, can be added, or can't be tested yet."""
    t = c.get("testability") or {}
    v, detail = t.get("verdict") or "", t.get("detail") or ""
    if v.startswith("codable now") and detail.lower().startswith("already"):
        return "Tested on the site", "in"
    if v.startswith("codable now") and "already" in detail.lower():
        return "Partly tested on the site", "in"
    if v.startswith("codable now"):
        return "Testable: next to add", "wait"
    if v.startswith("not objective"):
        return "Can't be tested as written", "out"
    if "codable now" in v:
        return "Partly testable", "wait"
    return "Needs data the site doesn't have yet", "out"


def years(c):
    """The short span for a card ("1900-1929"), without the notes the research kept in brackets."""
    y = c.get("years_active") or ""
    return y.split("(")[0].split(";")[0].strip()


def see_also(kind, slug):
    """The classics that mention a play (kind "play") or a person (kind "thinker"), for links back from their pages."""
    key = "related_plays" if kind == "play" else "related_thinkers"
    return [c for c in CLASSICS if slug in c.get(key, [])]


def links_html(h, items, lead="In the Classics"):
    if not items:
        return ""
    return (f'<p class="classic-see small"><span class="eyebrow">{e(lead)}</span> ' +
            " · ".join(f'<a href="{h(PATH + c["slug"] + "/")}">{e(c["name"])}</a>' for c in items) + "</p>")


def _people(h, c):
    out = []
    for p in c.get("people") or []:
        name = e(p.get("name") or "")
        dates = p.get("dates") or ""
        dates = "" if (not dates or "not" in dates) else f' <span class="muted">({e(dates)})</span>'
        out.append(f'<li><b>{name}</b>{dates}<span class="muted small"> · {e(p.get("role") or "")}</span></li>')
    return "<ul class='classic-people'>" + "".join(out) + "</ul>" if out else ""


def _sources(c):
    rows = []
    for s in c.get("sources") or []:
        cit, url = s.get("citation") or "", s.get("url") or ""
        rows.append(f'<li>{e(cit)}' + (f' <a href="{e(url)}" rel="noopener nofollow">Link</a>' if url.startswith("http") else "") + "</li>")
    for s in c.get("extra_sources") or []:
        txt = str(s)
        if "http" in txt:
            cit, url = txt.rsplit("http", 1)
            rows.append(f'<li>{e(cit.rstrip(": ").strip())} <a href="{e("http" + url.strip())}" rel="noopener nofollow">Link</a></li>')
        else:
            rows.append(f"<li>{e(txt)}</li>")
    return "<ol class='classic-src small'>" + "".join(rows) + "</ol>"


def page(site, c):
    path, depth = PATH + c["slug"] + "/", 2
    h = lambda x: site.href(depth, x)
    word, cls = verdict(c)
    q = c.get("quote") or None
    quote = (f'<blockquote class="classic-quote"><p>“{e(q["text"])}”</p><footer class="small muted">{e(q.get("by") or "")}</footer></blockquote>'
             if q and q.get("text") else "")
    plays = ""
    for s in c["related_plays"]:
        p = PLAY[s]
        sm = site.strat_summary(p) if not p.get("benchmark") else None
        rec = (f'<span class="classic-rec"><b>{pct(sm["bat"], sign=False, d=0)}</b> of {sm["calls"]:,} calls right · in on {sm["in_now"]} of {sm["n"]} stocks now</span>'
               if sm and sm.get("bat") is not None else "")
        plays += (f'<a class="card classic-play" href="{h("strategies/" + s + "/")}"><span class="eyebrow">{e(FAMILY[p["family"]][0] if p["family"] in FAMILY else "The benchmark")}</span>'
                  f'<span class="play-nm">{play_name_html(p)}</span><span class="small">{e(p.get("oneline") or "")}</span>{rec}</a>')
    people_on = "".join(f'<a href="{h("thinkers/" + t + "/")}">{e(THINKER[t]["name"])}</a>' for t in c["related_thinkers"])
    unv = "".join(f"<li>{e(x)}</li>" for x in (c.get("unverified") or []))
    test = c.get("testability") or {}
    unlock = c.get("unlocked_by") or {}
    body = f"""
<nav class="crumbs"><a href="{h(PATH)}">Classics</a><span>/</span><span>{e(c["name"])}</span></nav>
<section class="pair-head"><p class="eyebrow">Classics · {e(years(c))}</p>
<h1 class="h1">{e(c["name"])}</h1>
<p class="lede">{e(c.get("hook") or "")}</p>
{_people(h, c)}</section>
<section class="prose classic-story"><h2 class="h2">The story</h2><p>{e(c["story"])}</p>{quote}</section>
<section class="split classic-rule-sec"><div class="card rule-card"><p class="eyebrow">The original rule</p><p>{e(c.get("original_rule") or "")}</p></div>
<div class="card"><p class="eyebrow">Can it be tested here?</p><p><span class="classic-verdict {cls}">{e(word)}</span></p><p class="small">{e(test.get("detail") or "")}</p>
{f'<p class="small muted">What would unlock it: {e(unlock.get("missing") or "")}.</p>' if unlock.get("missing") else ""}</div></section>
<section><div class="sec-head"><h2 class="h2">Where it lives on</h2><p>{e(c.get("lineage_note") or "")}</p></div>
{f'<div class="grid grid-3">{plays}</div>' if plays else '<p class="muted">No play on the site descends from it yet.</p>'}
{f'<p class="classic-ppl small"><span class="eyebrow">The people behind those plays</span> {people_on}</p>' if people_on else ""}</section>
{f'<section class="card classic-unv"><p class="eyebrow">What we couldn’t confirm</p><ul class="small">{unv}</ul><p class="small muted">Stories about famous traders grow in the retelling. Where sources disagree, we say so rather than pick the better tale.</p></section>' if unv else ""}
<section class="prose"><h2 class="h3">Sources</h2>{_sources(c)}</section>
"""
    title = f"{c['name']}: the classic and where it lives on"
    desc = (c.get("hook") or "")[:300]
    site.add(path, site.shell(path, title, desc, body, active="strategies/"))


def hub(site):
    path, depth = PATH, 1
    h = lambda x: site.href(depth, x)
    cards = ""
    for c in CLASSICS:
        word, cls = verdict(c)
        n = len(c["related_plays"])
        cards += (f'<a class="card classic-card" href="{h(PATH + c["slug"] + "/")}"><span class="eyebrow">{e(years(c))}</span>'
                  f'<span class="name">{e(c["name"])}</span><span class="muted small">{e(c.get("hook") or "")}</span>'
                  f'<span class="classic-meta small"><span class="classic-verdict {cls}">{e(word)}</span>'
                  f'{(" · 1 play on the site descends from it" if n == 1 else f" · {n} plays on the site descend from it") if n else ""}</span></a>')
    body = f"""<section class="pair-head has-art">{page_art(h, PAGE_ART["strategies/"], "60% 60%")}<p class="eyebrow">Classics</p>
<h1 class="h1">The strategies people stopped talking about</h1>
<p class="lede">Before screeners and backtests there were editors, dancers, bucket-shop speculators and newsletter writers with a rule and a story. Here are {len(CLASSICS)} of them: who they were, what the rule said, why it faded, and the plays on Be The Puck that carry it on, with how often those have been right.</p></section>
<section><div class="grid grid-3">{cards}</div></section>
<section class="card prose"><p class="eyebrow">How we told these</p><p>Each story was checked against the original books, the newspapers of the day or later research, and the sources are on every page. Where the famous version of a story isn't backed by a record, we say so. The rules are stated as their authors wrote them; whether each can be tested on Be The Puck's data is marked, and the ones that can't yet say what's missing.</p></section>"""
    site.add(path, site.shell(path, "Classics: forgotten strategies and the people behind them",
                              f"{len(CLASSICS)} market strategies people don't talk about anymore: Dow Theory, Livermore's Market Key, the Darvas box, the Turtles, Graham's rules and more, with the plays they inspired.",
                              body, active="strategies/"))


def build(site):
    hub(site)
    for c in CLASSICS:
        page(site, c)
