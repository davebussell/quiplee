"""Be The Puck Members: the paywall around the top-picks tracker and the reports.

What is locked
  /picks/          the top-picks tracker (tools/qstrat/picks.py)
  /rules/          the member's own Start/Stop rule and portfolio limits (tools/qstrat/rules.py)
  /articles/<...>  every report: long reads, sector pieces and stock briefs.
                   The /articles/ hub stays open.

How the lock works
  The full pages are built and published as usual. An edge function
  (netlify/edge-functions/member-gate.js) runs in front of the locked paths and
  serves the page only with a valid member cookie. Without one it serves the
  page's locked version instead: the same header (title and opening line) and
  a sign-in / join card. The build writes those under /locked/<path>, rendered
  at the real page's depth, so they work when served at the real URL.

  The cookie is signed with QM_SECRET and set by netlify/functions/member.mjs:
  today by the members' password (only its PBKDF2 hash, QM_PASS_HASH, lives in
  Netlify's environment), and by a PayPal subscription once PAYPAL_* is set.
"""
import html
import os

e = html.escape
PRICE = "$5"
LOCKED_PREFIXES = ("picks/", "articles/", "rules/")
OPEN_PATHS = {"articles/"}          # the hub stays open
LOCK_SVG = ('<svg class="lock-ic" viewBox="0 0 24 24" aria-hidden="true" width="18" height="18"><rect x="5" y="10.5" width="14" height="10" rx="2.2" fill="none" '
            'stroke="currentColor" stroke-width="1.8"/><path d="M8.2 10.5V7.8a3.8 3.8 0 0 1 7.6 0v2.7" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>')


def is_locked(path):
    return path not in OPEN_PATHS and any(path.startswith(p) for p in LOCKED_PREFIXES)


def paypal_conf():
    """PayPal client id and plan id, read at build time. Both are public values
    (they sit in the page for PayPal's button); the secret never leaves the functions."""
    cid, plan = os.environ.get("PAYPAL_CLIENT_ID", ""), os.environ.get("PAYPAL_PLAN_ID", "")
    return (cid, plan) if cid and plan else (None, None)


FREE_UNTIL = "January 1, 2027"


def free_bar(site, depth):
    """The notice on member pages: free with an account until 2027, then $5 a month."""
    h = lambda x: site.href(depth, x)
    return (f'<div class="free-bar"><div class="wrap"><span class="tag mem">{LOCK_SVG}Members</span> '
            f'<span>Free with an account until <b>{FREE_UNTIL}</b>, then {PRICE} a month. '
            f'The screener, the Theory tester and the Start/Stop light stay free.</span> <a href="{h("members/")}">Details</a></div></div>')


def member_tag():
    return f'<span class="tag mem">{LOCK_SVG}Members</span>'


def pw_details(next_path, uid):
    """The shared members' password, tucked away (the owner's way in, from before accounts)."""
    return (f'<details class="pw-details"><summary>Have the members\' password?</summary>'
            f'<form class="lock-form" method="post" action="/api/member/login"><input type="hidden" name="next" value="/{e(next_path)}">'
            f'<label for="{uid}">Members\' password</label><div class="lock-row"><input id="{uid}" type="password" name="password" autocomplete="current-password" required>'
            f'<button type="submit" class="btn">Sign in</button></div><p class="lock-msg small" data-login-msg hidden></p></form></details>')


def lock_card(site, depth, next_path, what="report"):
    h = lambda x: site.href(depth, x)
    perks = "".join(f"<li>{x}</li>" for x in (
        "The top-picks tracker, reviewed every Friday", "Every report and plain-English stock brief",
        "Your own Start/Stop rules and portfolio limits", "Play-by-play emails on the stocks you follow"))
    return f"""<section class="card lock-card" id="lock" aria-labelledby="lock-h">
<div class="lock-top">{member_tag()}<h2 class="h2" id="lock-h">This {e(what)} is for members, and it's free until {FREE_UNTIL}</h2>
<p class="muted">Create a free Be The Puck account and it opens straight away. From {FREE_UNTIL}, membership is {PRICE} a month; nothing is charged unless you choose to subscribe.</p></div>
<div class="lock-split">
<div class="auth-slot" data-auth data-auth-next="reload" data-auth-context="member"><noscript><p><a class="btn primary" href="{h('me/')}">Create your free account</a></p></noscript></div>
<div class="lock-join"><p class="eyebrow">Members get</p><ul class="check-list">{perks}</ul>
<p class="small muted">The screener, the Theory tester, the Start/Stop light and its flip emails are free for good. <a href="{h('members/')}">What's included</a></p>
{pw_details(next_path, "lock-pw")}</div>
</div>
</section>"""


def locked_page(site, path, title, desc, head_html, what="report", active=None, crumbs=""):
    """The locked version of `path`: its header plus the sign-in card. Rendered at
    the real path's depth (it is served at the real URL) and stored under locked/."""
    depth = path.count("/")
    body = f"""{crumbs}
<article class="article is-locked">
{head_html}
{lock_card(site, depth, path, what)}
<p class="note-line">This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Be The Puck reports what published rules and public data say; it doesn't know your goals, taxes or timeline.</p>
</article>"""
    # the base keeps relative links right if the locked copy is ever opened at /locked/<path>
    page = site.shell(path, title, desc, body, active=active, scripts=("assets/members.js",), link=False)
    if not site.preview:
        page = page.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n<base href="/{e(path)}">', 1)
    site.add("locked/" + path, page)


def members_page(site):
    path, depth = "members/", 1
    h = lambda x: site.href(depth, x)
    cid, plan = paypal_conf()
    if cid:
        join = (f'<div id="pp-box" class="pp-box" data-client="{e(cid)}" data-plan="{e(plan)}" data-api="/api/paypal/subscribed">'
                f'<p class="small muted">Pay with PayPal or a card through PayPal. You can cancel from your PayPal account at any time.</p>'
                f'<div id="pp-buttons"></div><p class="small" data-pp-msg hidden></p></div>')
    else:
        join = ('<div class="pp-box pp-soon"><p><b>Sign-up opens soon.</b> Subscriptions run through PayPal: '
                f'{PRICE} a month, cancel any time from your PayPal account.</p></div>')
    sub_note = ('<form class="lock-form mem-link" method="post" action="/api/member/link"><label for="mem-em">Subscribed through PayPal? '
                'Get a sign-in link for this device</label><div class="lock-row"><input id="mem-em" type="email" name="email" autocomplete="email" '
                'placeholder="The email on your PayPal account" required><button type="submit" class="btn">Email me a link</button></div></form>') if cid else ""
    benefits = [
        ("Top-picks tracker", "Five stocks picked by rule from the strongest setups, tracked from the close they go in, reviewed after every Friday close. "
                              "See every entry, every exit and the reason, and how the model is doing against the S&amp;P 500.", "picks/"),
        ("Every report", "The long reads on bubbles, crashes, debt and positioning, the sector pieces, and a plain-English brief on every covered stock, "
                         "rebuilt each night with the latest close.", "articles/"),
        ("Your own rules", "Choose which plays count toward the Start/Stop light, set when it turns, and check your portfolio against your own "
                           "limits: biggest stock, biggest sector, share in Start names and crash exposure.", "rules/"),
        ("Play-by-play emails", "On top of the free Start/Stop flips: an email after the close listing every play that got in or out on the stocks you follow, "
                                "and prices that are close to a play's line.", "me/"),
    ]
    cards = "".join(f'<a class="card mem-card" href="{h(u)}"><span class="eyebrow">Included</span><span class="name">{t}</span><span class="muted small">{d}</span></a>'
                    for t, d, u in benefits)
    body = f"""<section class="pair-head"><p class="eyebrow">Be The Puck Members</p><h1 class="h1">Every member tool, free until {FREE_UNTIL}</h1>
<p class="lede">Everything on Be The Puck's stock and play pages stays free, and so do the screener, the Theory tester, the Start/Stop light and its flip emails. Members also get the top-picks tracker, every report, their own rules and play-by-play emails. Create a free account and they're yours until {FREE_UNTIL}; after that, {PRICE} a month.</p>
<div class="mem-state" data-mem-state hidden><span class="tag live">You're a member</span> <a href="{h('me/')}">Open My Puck</a> · <a href="{h('picks/')}">Top picks</a> · <a href="{h('rules/')}">Your rules</a> · <a href="{h('articles/')}">Reports</a></div></section>

<section><div class="grid grid-4">{cards}</div></section>

<section class="split mem-split">
<div class="card prose" id="join"><p class="eyebrow">Join free</p><h2 class="h2">Free until {FREE_UNTIL}</h2>
<p>One account for everything: the stocks you follow, your emails and every member tool.</p>
<div data-signed-out><div class="auth-slot" data-auth data-auth-next="/me/?welcome=1" data-auth-context="member"></div></div>
<div class="mem-in" data-signed-in hidden><p><span class="tag live">Signed in</span> Member tools are open on this account until {FREE_UNTIL}.</p>
<div class="hero-links"><a class="btn primary" href="{h('me/')}">Open My Puck</a><a class="btn" href="{h('picks/')}">Top picks</a><a class="btn" href="{h('rules/')}">Your rules</a></div></div>
{join if cid else ""}</div>
<div class="card" id="signin"><p class="eyebrow">What happens when</p><h2 class="h2">Free now, {PRICE} a month from {FREE_UNTIL}</h2>
<ol class="mem-tl">
<li><b>Today</b><span>Create a free account with your email. Top picks, reports, your own rules and play-by-play emails open straight away.</span></li>
<li><b>Before then</b><span>We'll email every member about the switch, with the date and the price, before anything changes.</span></li>
<li><b>From {FREE_UNTIL}</b><span>Member tools are {PRICE} a month through PayPal, cancel any time. Nothing is charged unless you choose to subscribe.</span></li>
<li><b>Always free</b><span>Your account, the screener, the Theory tester, every stock page and play, the Start/Stop light and its flip emails.</span></li>
</ol>
{pw_details("picks/", "mem-pw")}
{sub_note}</div>
</section>

<section class="card prose"><p class="eyebrow">Good to know</p><ul>
<li><b>What's free for good.</b> Every stock page, every play, the Start/Stop light and its flip emails, the markets page, the screener, the Theory tester, the watchlist, the guides and the Learn tracks.</li>
<li><b>What the picks are.</b> The top five names on Be The Puck's public <a href="{h('stocks/?sort=score')}">strongest-setups list</a>, held by a fixed rule and tracked from the close they go in. A rule, not anyone's opinion, and not advice for you.</li>
<li><b>From {FREE_UNTIL}.</b> {PRICE} a month, billed through PayPal, cancel any time. Your account, the Theory tester and Start/Stop emails carry on either way.</li>
<li><b>Privacy.</b> Be The Puck keeps your email, your username and what you choose to follow, and nothing else. Payments will be handled by PayPal; Be The Puck never sees your card.</li>
</ul><p class="small muted">This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Be The Puck doesn't know your goals, taxes or timeline, and takes no positions in the names it covers.</p></section>"""
    site.add(path, site.shell(path, "Members · free until January 1, 2027",
                              f"Be The Puck Members: the top-picks tracker, every report and stock brief, your own Start/Stop rules and play-by-play emails. Free with an account until January 1, 2027, then {PRICE} a month.",
                              body, scripts=("assets/members.js",)))
