"""Quiplee Members: the paywall around the top-picks tracker and the reports.

What is locked
  /picks/          the top-picks tracker (tools/qstrat/picks.py)
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
LOCKED_PREFIXES = ("picks/", "articles/")
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


def member_tag():
    return f'<span class="tag mem">{LOCK_SVG}Members</span>'


def lock_card(site, depth, next_path, what="report"):
    h = lambda x: site.href(depth, x)
    return f"""<section class="card lock-card" id="lock" aria-labelledby="lock-h">
<div class="lock-top">{member_tag()}<h2 class="h2" id="lock-h">This {e(what)} is for members</h2>
<p class="muted">Quiplee Members get the top-picks tracker, every report and stock brief, and nightly alerts on their own stocks. {PRICE} a month, cancel any time.</p></div>
<div class="lock-split">
<form class="lock-form" method="post" action="/api/member/login">
<input type="hidden" name="next" value="/{e(next_path)}">
<label for="lock-pw">Member password</label>
<div class="lock-row"><input id="lock-pw" type="password" name="password" autocomplete="current-password" required><button type="submit" class="btn primary">Sign in</button></div>
<p class="lock-msg small" data-login-msg hidden></p>
</form>
<div class="lock-join"><p class="small muted">Not a member yet?</p><a class="btn" href="{h('members/')}#join">Join for {PRICE} a month</a><a class="small" href="{h('members/')}">What's included</a></div>
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
<p class="note-line">Education, not financial advice. Quiplee reports what published rules and public data say; it doesn't know your goals, taxes or timeline.</p>
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
        ("Alerts on your stocks", "Save your list once and get an email after the close when a play flips on one of your names, or a price nears "
                                  "the level where the rules would get in or out.", "watchlist/"),
    ]
    cards = "".join(f'<a class="card mem-card" href="{h(u)}"><span class="eyebrow">Included</span><span class="name">{t}</span><span class="muted small">{d}</span></a>'
                    for t, d, u in benefits)
    body = f"""<section class="pair-head"><p class="eyebrow">Quiplee Members</p><h1 class="h1">The picks, the reports, and alerts on your stocks</h1>
<p class="lede">Everything on Quiplee's stock and play pages stays free. Members also get the top-picks tracker, every report, and a nightly email when something changes on their own stocks.</p>
<div class="mem-state" data-mem-state hidden><span class="tag live">Signed in</span> <a href="{h('picks/')}">Open the top-picks tracker</a> · <a href="{h('articles/')}">Reports</a> · <a href="/api/member/logout">Sign out</a></div></section>

<section><div class="grid grid-3">{cards}</div></section>

<section class="split mem-split">
<div class="card prose" id="join"><p class="eyebrow">Join</p><h2 class="h2">{PRICE} a month</h2>
<p>One plan, everything included. Billed monthly through PayPal; cancel any time and keep access to the end of the month you paid for.</p>
{join}</div>
<div class="card" id="signin"><p class="eyebrow">Already a member</p><h2 class="h2">Sign in</h2>
<form class="lock-form" method="post" action="/api/member/login">
<input type="hidden" name="next" value="/picks/">
<label for="mem-pw">Member password</label>
<div class="lock-row"><input id="mem-pw" type="password" name="password" autocomplete="current-password" required><button type="submit" class="btn primary">Sign in</button></div>
<p class="lock-msg small" data-login-msg hidden></p>
</form>
{sub_note}</div>
</section>

<section class="card prose"><p class="eyebrow">Good to know</p><ul>
<li><b>What the picks are.</b> The top five names on Quiplee's public <a href="{h('stocks/?sort=score')}">strongest-setups list</a>, held by a fixed rule and tracked from the close they go in. A rule, not anyone's opinion, and not advice for you.</li>
<li><b>What stays free.</b> Every stock page, every play, the markets page, the watchlist and the Learn tracks.</li>
<li><b>Privacy.</b> Quiplee keeps your email, your PayPal subscription id and your saved list, and nothing else. Payments are handled by PayPal; Quiplee never sees your card.</li>
</ul><p class="small muted">Education, not financial advice. Quiplee doesn't know your goals, taxes or timeline, and takes no positions in the names it covers.</p></section>"""
    site.add(path, site.shell(path, "Members · the picks, the reports and alerts on your stocks",
                              f"Quiplee Members: the top-picks tracker, every report and stock brief, and nightly alerts on your own stocks. {PRICE} a month through PayPal.",
                              body, scripts=("assets/members.js",)))
