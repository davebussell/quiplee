"""/alerts/: free email alerts when Be The Puck's signal (Buy, Hold, Sell) flips on a reader's stocks.

The page signs people up (confirmed by email), lets them change their stocks
from the link in every email, and shows what an alert looks like with tonight's
numbers. The live part is netlify/functions/alerts.mjs and alerts-nightly.mjs. Free
subscribers get the standard weights; accounts get their own (netlify/lib/signal.mjs).
"""
import html

from .content import TICKERS
from .render import DISCLAIMER, dlong, sig_pill, fx_score
from .factors import BUY, SELL, SIG_WORD
from . import stockview as sv
from .media import page_art, PAGE_ART

e = html.escape


def _example(site, depth):
    """What an alert looks like, with tonight's numbers for the covered stock with the highest standard score."""
    h = lambda x: site.href(depth, x)
    best = None
    for t in TICKERS:
        if t.get("index") or t.get("requested") or (t["sym"], "buy-and-hold") not in site.R or t["crypto"]:
            continue
        sc, sg, _ = fx_score(site, t)
        if sc is not None and (best is None or sc > best[1]):
            best = (t, sc, sg)
    if not best:
        return ""
    t, sc, sg = best
    k, n = site.consensus(t)
    meta = site.meta.get(t["sym"])
    read = sv.read_lines(site, t, meta, site.fund.get(t["sym"])) if meta else []
    where = (f"at or above the Buy line of {BUY}" if sg == 1 else f"at or below the Sell line of {SELL}" if sg == -1
             else f"between the Sell line ({SELL}) and the Buy line ({BUY})")
    lis = "".join(f"<li>{e(x)}</li>" for x in read)
    return f"""<section class="card al-example" aria-label="Example alert"><p class="eyebrow">Example: an alert with the {dlong(site.asof)} numbers</p>
<p class="al-subj"><b>Subject:</b> {e(t['name'])} ({e(t['short'])}): the signal turned {SIG_WORD[sg].upper()}</p>
<div class="al-mail"><p class="al-head">{e(t['name'])} {sig_pill(sg)}</p>
<p>{k} of {n} plays hold it. The score is {sc}, {where}.</p><ul>{lis}</ul>
<p><a href="{h('stocks/' + t['slug'] + '/')}">See the full analysis for {e(t['short'])}</a></p>
<p class="small muted">{e(DISCLAIMER)}</p></div></section>"""


def alerts_page(site):
    path, depth = "alerts/", 1
    h = lambda x: site.href(depth, x)
    uni = h("data/tickers.json") + "?v=" + site.ver
    body = f"""<section class="pair-head has-art">{page_art(h, PAGE_ART["alerts/"], "50% 60%")}<p class="eyebrow">Free email alerts</p><h1 class="h1">Get an email when the signal flips</h1>
<p class="lede">Pick the stocks you care about. When Be The Puck's signal on one of them changes between Buy, Hold and Sell, we email you the change and the analysis after the close. Free, and you can stop any time.</p></section>

<div id="al-app" class="al-app" data-api="/api/alerts/" data-universe="{e(uni)}" data-stock="{e(h('stocks/{s}/'))}">
<section class="card al-card" data-al-signup>
<p class="al-acct" data-signed-in hidden>You're signed in: manage the stocks you follow and your emails in <a href="{h('me/')}#alerts">My Puck</a>.</p>
<h2 class="h3">Your stocks</h2>
<form class="pt-form" data-al-form novalidate>
<label>Stocks to follow<textarea name="tickers" rows="3" placeholder="NVDA, TD.TO, Shopify, BTC…" spellcheck="false"></textarea></label>
<div class="al-chips" data-al-chips></div>
<p class="small"><button type="button" class="linkbtn al-wl" data-al-watchlist hidden>Use the stocks on my watchlist</button></p>
<label>Email<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"></label>
<label class="pt-check"><input type="checkbox" name="consent"> Email me when the signal changes on these stocks. I can unsubscribe from any email.</label>
<button class="btn primary" type="submit">Email me the flips</button>
<p class="pt-msg" role="alert" data-al-msg></p>
<p class="small muted">We'll send one email to confirm. After that you only hear from us when the signal on a stock on your list flips: one email per close at most, with every change in it.</p>
<p class="small">Want alerts on your own signal (your weights and plays), play-by-play emails and the member tools? <a href="{h('me/')}">Create a free account</a> instead; member tools are free until January 1, 2027.</p>
</form>
</section>
<section class="card al-card" data-al-manage hidden></section>
</div>

{_example(site, depth)}

<section class="card prose"><h2 class="h3">How the signal works</h2>
<p>The signal is Be The Puck's one call on a stock. Each factor scores it from 0 to 100, and the score is their weighted average. These emails use the standard weights: half the share of the plays that hold the stock, half analysts' upside. Buy at {BUY} or more, Sell at {SELL} or less, Hold in between. With a free account, alerts follow your own weights, your Buy and Sell lines and the plays you count. <a href="{h('method/')}#signal">More on the method</a>.</p>
<p class="small muted">{e(DISCLAIMER)}</p></section>
"""
    site.add(path, site.shell(path, "Free email alerts: get an email when the signal flips",
                              "Pick your stocks and get a free email with the analysis when Be The Puck's signal (Buy, Hold or Sell) changes on one of them.",
                              body, active="stocks/", scripts=("assets/alerts.js",), link=False))
