"""/owner/: the site owner's private numbers (who has signed up, and how many).

Not linked from anywhere, not in the sitemap, and marked noindex. The page itself is
an empty frame: assets/owner.js asks /api/owner/stats (netlify/functions/owner.mjs),
which answers only to the members'-password cookie. Without it the page shows that
password form, which signs in and comes straight back here.
"""
from .members import pw_details


def owner_page(site):
    path, depth = "owner/", 1
    body = f"""<section class="pair-head"><p class="eyebrow">Owner</p><h1 class="h1">Sign-ups</h1>
<p class="lede">Every Be The Puck account, newest first, and the running totals. Only you can see this page.</p></section>
<section class="owner" data-owner>
<div class="card owner-lock" data-owner-lock hidden><p>Sign in with the members' password to see the numbers.</p>{pw_details("owner/", "own-pw").replace("<details ", "<details open ")}</div>
<p class="muted small" data-owner-msg>Loading…</p>
<div class="sum-tiles" data-owner-tiles hidden></div>
<div class="card" data-owner-list hidden><div class="sec-head"><h2 class="h2">Latest sign-ups</h2><p>Newest first, up to 50. Times are Toronto time.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Username</th><th>Signed up</th><th>Email</th><th>Confirmed</th><th class="r">Follows</th><th>Alerts</th></tr></thead><tbody data-owner-rows></tbody></table></div></div>
</section>"""
    site.add(path, site.shell(path, "Owner · sign-ups", "Private.", body, active="",
                              extra_head='<meta name="robots" content="noindex, nofollow">\n',
                              scripts=("assets/members.js", "assets/owner.js"), link=False))
