"""/alerts/: free email alerts when the Start/Stop light flips on a reader's stocks.

The page signs people up (confirmed by email), lets them change their stocks
from the link in every email, and shows a real example of an alert. The live
part is netlify/functions/alerts.mjs and alerts-nightly.mjs.
"""
import html

from .content import TICKERS
from .render import DISCLAIMER, LIGHT_ON, LIGHT_OFF, light_badge, dlong
from . import stockview as sv
from .media import page_art, PAGE_ART

e = html.escape


def _example(site, depth):
    """The most recent real flip, shown as the alert it would have sent."""
    h = lambda x: site.href(depth, x)
    best = None
    for t in TICKERS:
        if t.get("index") or t.get("requested") or (t["sym"], "buy-and-hold") not in site.R:
            continue
        L = site.light(t)
        if not L["state"] or L.get("since") is None:
            continue
        if best is None or L["since"] > best[1]["since"] or (L["since"] == best[1]["since"] and t.get("bulk") and not best[0].get("bulk")):
            best = (t, L)
    if not best:
        return ""
    t, L = best
    meta = site.meta.get(t["sym"])
    read = sv.read_lines(site, t, meta, site.fund.get(t["sym"])) if meta else []
    word = "START" if L["state"] == "start" else "STOP"
    why = (f"The light turns Start when {round(LIGHT_ON * 100)}% or more of the plays are in." if L["state"] == "start"
           else f"The light turns Stop when the share falls to {round(LIGHT_OFF * 100)}% or less.")
    lis = "".join(f"<li>{e(x)}</li>" for x in read)
    return f"""<section class="card al-example" aria-label="Example alert"><p class="eyebrow">Example: a real flip from {dlong(L['since'])}</p>
<p class="al-subj"><b>Subject:</b> {e(t['name'])} ({e(t['short'])}): the light turned {word}</p>
<div class="al-mail"><p class="al-head">{e(t['name'])} {light_badge(L)}</p>
<p>{L['k']} of {L['n']} plays now hold it. {e(why)}</p><ul>{lis}</ul>
<p><a href="{h('stocks/' + t['slug'] + '/')}">See the full analysis for {e(t['short'])}</a></p>
<p class="small muted">{e(DISCLAIMER)}</p></div></section>"""


def alerts_page(site):
    path, depth = "alerts/", 1
    h = lambda x: site.href(depth, x)
    uni = h("data/tickers.json") + "?v=" + site.ver
    body = f"""<section class="pair-head has-art">{page_art(h, PAGE_ART["alerts/"], "50% 60%")}<p class="eyebrow">Free email alerts</p><h1 class="h1">Get an email when the light flips</h1>
<p class="lede">Pick the stocks you care about. When the Start/Stop light changes on one of them, because enough of Be The Puck's plays have moved in or out, we email you the change and the analysis after the close. Free, and you can stop any time.</p></section>

<div id="al-app" class="al-app" data-api="/api/alerts/" data-universe="{e(uni)}" data-stock="{e(h('stocks/{s}/'))}">
<section class="card al-card" data-al-signup>
<p class="al-acct" data-signed-in hidden>You're signed in: manage the stocks you follow and your emails in <a href="{h('me/')}#alerts">My Puck</a>.</p>
<h2 class="h3">Your stocks</h2>
<form class="pt-form" data-al-form novalidate>
<label>Stocks to follow<textarea name="tickers" rows="3" placeholder="NVDA, TD.TO, Shopify, BTC…" spellcheck="false"></textarea></label>
<div class="al-chips" data-al-chips></div>
<p class="small"><button type="button" class="linkbtn al-wl" data-al-watchlist hidden>Use the stocks on my watchlist</button></p>
<label>Email<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"></label>
<label class="pt-check"><input type="checkbox" name="consent"> Email me when the Start/Stop light changes on these stocks. I can unsubscribe from any email.</label>
<button class="btn primary" type="submit">Email me the flips</button>
<p class="pt-msg" role="alert" data-al-msg></p>
<p class="small muted">We'll send one email to confirm. After that you only hear from us when a light on your list flips: one email per close at most, with every change in it.</p>
<p class="small">Want play-by-play emails and the member tools too? <a href="{h('me/')}">Create a free account</a> instead; member tools are free until January 1, 2027.</p>
</form>
</section>
<section class="card al-card" data-al-manage hidden></section>
</div>

{_example(site, depth)}

<section class="card prose"><h2 class="h3">How the light works</h2>
<p>Every stock gets one light that sums up all the plays Be The Puck runs on it. It reads <b>Start</b> when {round(LIGHT_ON * 100)}% or more of the plays with a call hold the stock, and stays Start until that falls to {round(LIGHT_OFF * 100)}% or less, when it turns <b>Stop</b>. The gap in the middle stops a stock that hovers around half from flipping every few days, so an alert means a real shift. <a href="{h('method/')}#light">More on the method</a>.</p>
<p class="small muted">{e(DISCLAIMER)}</p></section>
"""
    site.add(path, site.shell(path, "Free email alerts: get an email when the light flips",
                              "Pick your stocks and get a free email with the analysis when Be The Puck's Start/Stop light changes on one of them.",
                              body, active="stocks/", scripts=("assets/alerts.js",), link=False))
