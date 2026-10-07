"""/me/: My Puck, the one place for a Be The Puck account.

Signed out, the page sells the account with a real preview (tonight's lights on a
sample list, clearly labelled as an example) next to the sign-up form. Signed in,
assets/me.js draws the dashboard from /api/account/me and data/reads.json: the
stocks you follow and their lights, your email alerts, a shortcut into the Theory
tester, the member tools (free until January 1, 2027) and your account settings.
"""
import html

from .content import TICKERS, TIMED
from .render import light_badge, money, dlong, fill_bar
from .members import FREE_UNTIL, PRICE

e = html.escape
SAMPLE = ["NVDA", "AAPL", "SHOP.TO", "RY.TO", "MSFT", "BTC-USD"]


def _preview(site, depth):
    """A static picture of the dashboard on a sample list, with tonight's real lights."""
    h = lambda x: site.href(depth, x)
    names = [t for s in SAMPLE for t in TICKERS if t["sym"] == s and (s, "buy-and-hold") in site.R]
    rows, on = "", 0
    for t in names:
        L = site.light(t)
        on += L["state"] == "start"
        x = site.r(t["sym"], "buy-and-hold")
        since = f'since {dlong(L["since"])}' if L.get("since") is not None else ""
        rows += (f'<li><a href="{h("stocks/" + t["slug"] + "/")}"><span class="mp-sym"><b>{e(t["short"])}</b><span>{e(t["name"])}</span></span>'
                 f'{light_badge(L)}<span class="mp-bar">{fill_bar(L["k"], L["n"])}<span>{L["k"]}/{L["n"]}</span></span>'
                 f'<span class="mp-px mono">{money(x["price"], t["cur"])}</span><span class="mp-since">{e(since)}</span></a></li>')
    return f"""<div class="mp-frame" aria-label="Example of My Puck">
<div class="mp-chrome"><i></i><i></i><i></i><span>bethepuck.com/me/</span><b class="tag">Example</b></div>
<div class="mp-body">
<div class="mp-kpis">
<div><span>Your stocks on Start</span><b>{on} <small>of {len(names)}</small></b></div>
<div><span>Plays counted</span><b>{len(TIMED)}</b></div>
<div><span>Email alerts</span><b class="mp-on">On</b></div>
<div><span>Member tools</span><b>Free <small>to 2027</small></b></div>
</div>
<p class="mp-h">Your stocks <span>· the {dlong(site.asof)} close</span></p>
<ul class="mp-list">{rows}</ul>
<p class="mp-foot">You'd get an email the evening any of these lights flips, with the analysis.</p>
</div></div>"""


def me_page(site):
    path, depth = "me/", 1
    h = lambda x: site.href(depth, x)
    body = f"""<div id="me-app" class="me-app" data-reads="{e(h('data/reads.json'))}?v={site.ver}" data-stock="{e(h('stocks/{u}/'))}" data-free="{e(FREE_UNTIL)}" data-price="{e(PRICE)}">

<section class="me-reset card" data-me-reset hidden><h2 class="h3">Choose a new password</h2>
<form class="auth-form" data-reset-form novalidate><label for="me-np">New password</label>
<div class="pw-row"><input id="me-np" name="password" type="password" autocomplete="new-password" minlength="8" required><button type="button" class="pw-eye">Show</button></div>
<button class="btn primary" type="submit">Save and sign in</button><p class="auth-msg" role="alert"></p></form></section>

<section class="me-out" data-me-out>
<div class="me-out-grid">
<div class="me-out-copy"><p class="eyebrow">My Puck</p>
<h1 class="h1 me-h1">Your stocks and their alerts, <em>in one place</em>.</h1>
<p class="lede">One free account follows your stocks with every play Be The Puck runs, emails you the evening a Start/Stop light flips, and opens every member tool until {FREE_UNTIL}.</p>
<ul class="check-list"><li>Follow up to 100 stocks, funds and coins</li><li>An email with the analysis when a light flips, the same evening</li>
<li>Test any theory on the stocks you follow, from one play to all of them</li><li>Top picks, reports, your own rules and play-by-play emails, free until {FREE_UNTIL}</li></ul>
<div class="me-preview">{_preview(site, depth)}</div>
</div>
<div class="card me-auth-card"><div data-auth data-auth-next="/me/?welcome=1" data-auth-context="me"><noscript><p>My Puck needs JavaScript.</p></noscript></div></div>
</div>
</section>

<section class="me-in" data-me-in hidden></section>
</div>

<section class="card prose me-how"><p class="eyebrow">Good to know</p><ul>
<li><b>Free for good:</b> your account, the screener, the Theory tester, the Start/Stop light and its flip emails.</li>
<li><b>Member tools</b> (top picks, reports, your own rules, play-by-play emails) are free until {FREE_UNTIL}, then {PRICE} a month. Nothing is charged unless you choose to subscribe.</li>
<li><b>Emails</b> go out after the U.S. close, only when something changed, and every one has a one-click unsubscribe.</li>
<li><b>Privacy:</b> Be The Puck keeps your email, your username and what you follow, and nothing else.</li>
</ul><p class="small muted">This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.</p></section>
"""
    site.add(path, site.shell(path, "My Puck: your stocks and their alerts",
                              "One free Be The Puck account: follow your stocks, get an email when the Start/Stop light flips, test theories on them, and use every member tool free until January 1, 2027.",
                              body, active="", scripts=("assets/widgets.js", "assets/me.js"), link=False))
