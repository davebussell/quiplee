# Be The Puck (bethepuck.com): working rules

Read this first in every session. The README explains how the site works; this file
says how to work on it. Requests and open work live in Linear (team Audit Demand,
project **Be The Puck**, https://linear.app/auditdemand/project/be-the-puck-935312b13bf3): check it at the start of a session, add anything Dave asks
for that isn't there, and move an issue to Done only once the change is live.

## Standing rules (from Dave)

- **"Done" means live.** A change is done when it's on bethepuck.com and has been checked
  at **390px and 1280px** wide: no horizontal scroll, no script errors, every page loads.
  `python tools/smoke.py https://bethepuck.com` does that check (see Testing).
- **Ship with example or filler data**, so a first visit shows a populated, working state, never an empty shell.
- **Disclaimer wording**, exactly: "This analysis does not constitute trading advice. Please meet
  with an advisor or independently review sources before making any decision." (`DISCLAIMER` in render.py.)
  It is on **every page** (the footer, and the site's own 404). The build refuses to publish a page
  without it and smoke.py checks it, so a new page type must use `Site.shell`.
- Financial content states facts and evidence, never a recommendation addressed to the reader.
- **Never label any ticker as Dave's own holding** on the site.
- **WSC, Transcat (TRNS) and McGrath RentCorp (MGRC) are never on the site**, in any form: a conflict
  of interest for Dave. Not in the universe or the request queue (`content.EXCLUDED`, mirrored in
  `netlify/lib/watchq.mjs`), not in a news item (`newsevents._news` drops any that mention
  them), not in an article, a list or an email. `content.banned_hit` is the one
  test; the build refuses to publish a file that mentions them and smoke.py checks the live pages.
- **The account page is "Login"** in the menu and header when signed out and "Account" when signed
  in (never "My Puck"); its own heading is "Your account".
- **Credentials:** never type a password, PIN, API key or token into anything. Dave enters
  PayPal, Stripe, Resend, Netlify and Anthropic keys himself (Netlify env vars or GitHub
  secrets). Never sign in to the live site's owner gate or create accounts on the live site;
  test accounts only on localhost (`tools/dev_serve.mjs` fakes the account API). The owner
  gate's password exists only as a PBKDF2 hash in `QM_PASS_HASH`; the owner stats token only as
  its hash in the repo.
- **Ask Dave first** before: changing Netlify settings (including DNS), sending any email on
  his behalf, or editing Canva designs.
- **Commits:** author `Claude <noreply@anthropic.com>`, ending with
  the `Co-Authored-By:` line for the Claude model in use (the session's reminder gives it) and
  the session's `Claude-Session:` line.

## Product rules (from the October 2026 review)

- **Your signal is the one headline verdict** (Buy / Hold / Sell from the reader's own
  weights, `tools/qstrat/factors.py` + `assets/plays.js`). Everything else on a stock page
  explains it. Don't add a new parallel score, light or ranking: extend the signal (a new
  factor) or its explanation instead.
- **No more stock × play pages.** A stock has pages only for its headline plays (the most
  accurate play in each family, plus `render.HEADLINE_EXTRA`), and every play keeps one full
  example on SPY for the Learn lessons (`render.EXTRA_PAIRS`). Any other
  `/stocks/<stock>/<play>/` address forwards to that play's row on the stock page (netlify.toml).
  Link with `site.pair_link(t, play)`, never by building the path by hand.
- Every factor and play shows how often it has been right (`calls right`). New factors
  get graded the same way before they get a slider.
- **The standard weights use only graded factors** (`factors.DEFAULT`: plays 40, off the high 30,
  trend 30; AUD-30). Change them only with a better graded record (`factorgrade.grade(site,
  extra_presets=...)`), and bump `factors.MODEL` whenever the standard weights or a factor's
  scoring change, so saved old-standard weights migrate and alerts re-baseline instead of
  mailing every flip the change caused. Test a change with `tools/model_compare.py` first (12-month
  edge since 2006 and by era, Sells that fell 30%+, flips a year), add it to `modelcompare.MODELS`,
  and rerun it after the change so `/articles/old-vs-new-signal/` stays current.
- **The signal grades itself in public.** `/articles/calls-graded/` rebuilds every day's standard
  calls since Oct 13, 2026 (`callpath.daily_path`) and scores them weekly, each day by the rules in
  force that day (`factors.MODEL3_SINCE`); a change to the standard weights or `MODEL` must be
  dated the same way (or `scorecard.SINCE` moved). Never store calls to grade later; rebuild them
  point-in-time, as every other test on the site does.
- **Model version 3 (Oct 21, 2026, AUD-34): the market guard and sticky calls** sit on top of the
  weights (`factors.GUARD`, `PRICE_KEYS`, `MID`; the state from `callpath.py`). The guard applies to
  every set of weights; the sticky rule only to the standard setup, because only it has a day-by-day
  path. Any page, email or tool that scores a stock must apply both the same way as `factors.score`
  (browser `BPPlays.score`, server `signal.mjs signalFor`), and say when a call is held or the guard
  is on.
- **Reader-requested names are private (Oct 26, 2026).** A ticker a reader adds that Be The Puck doesn't cover
  (account page, watchlist) is queued (`netlify/lib/watchq.mjs`; the account keeps it as `asked` and adds it to
  their list once covered) and analysed nightly like any other, but shown only to the readers who follow it: never
  in a public list, the screener, the sitemap or search engines (`render.PRIVATE_SLUGS`, noindex), never in the
  account page's Find, and ranked against the public names without joining them (`factors._rank`, the trend rank
  in `callpath.daily_path`), so adding one never moves a public score. A new public list must use
  `render.universe()` or skip `t.get("requested")`.
- **My stocks never loses a stock.** Signed in, a browser's saved stocks join the account (`assets/mine.js`); no
  page deletes a browser's list or replaces an account's list without a tap, and a replace that drops 3+ stocks
  keeps `follow_was` so the account page can put them back.
- **Faster exits were tested (Oct 20, 2026) and rejected:** 50-day trend, trend capped under the
  50-day, 20% floor, 3-month-high exit, half-and-half all have a lower 20-year edge and more
  flips (`modelcompare.MODELS`). Don't speed the exit rule up on the strength of one week.

## When a Netlify build fails

Netlify's build log needs a login, and its failure message says "exit code 2" whatever the cause
(a `sys.exit` in the build script shows as 2 too). Two things make a failed build readable from here:
the build pings the live site once per stage (`ping` in `tools/build_strategies.py`, user agent
`bethepuck-build/<stage>`, then `bethepuck-build/done`), so the site's request logs (Netlify MCP,
observability reader, top user agents in the build's time window) show how far it got; and
`.github/workflows/build-check.yml` runs the exact build command on GitHub Actions with a readable
log. Only the production build can read the picks and top-10 histories (`/api/picks-state`), so a
build can fail on Netlify and pass everywhere else when those histories hold something the rules
refuse; `picks.scrub` and `top10.scrub` keep excluded companies out of them.

## How it fits together

- `tools/build_strategies.py` builds the whole site into `_site/` from `data/` (no network).
  The engine (`tools/qstrat/engine.py`) runs every play on every ticker since 2005, then
  `tools/qstrat/render.py` and friends write the pages.
- `.github/workflows/refresh-prices.yml` refreshes `data/` twice a day (prices, macro,
  fundamentals, news, earnings and ratings) and commits; that push triggers a deploy.
- Deploys: Netlify builds each push (~7 minutes) until the build moves to GitHub Actions
  (`.github/workflows/deploy.yml`, waiting on the `NETLIFY_AUTH_TOKEN` secret; the steps to
  switch over are at the top of that file). Every push costs a deploy, so batch your commits
  and push once per piece of work.
- Company numbers: `tools/fetch_sec.py` keeps each SEC filer's quarters in `data/sec/` (dated by
  filing, so backtests never see the future); `tools/qstrat/secfund.py` turns them into P/E,
  growth, margins and debt. Yahoo (`tools/fetch_fundamentals.py`) covers the rest (TSX-only
  names, forward estimates, analyst targets). Prefer SEC numbers wherever a company files 10-Qs.
- Earnings: `tools/fetch_earnings.py` has Claude read each new earnings press release (8-K
  Exhibit 99.1) into `data/earnings/` (guidance raised/kept/cut, one-offs, a plain headline).
  `.github/workflows/earnings.yml` runs it weekday mornings; the nightly refresh runs it too.
  Needs the `ANTHROPIC_API_KEY` repo secret. Run the workflow by hand with `backfill` to read
  each company's past releases.
- `netlify/functions/` is the live API (accounts, alerts, watchlist queue, PayPal).
- Readers' choices (plays counted, signal weights) live in `localStorage` and, when signed
  in, in their account (`/api/account/plays`).

## Fast local work

```bash
pip install -r requirements.txt playwright
python tools/dev_render.py engine                # run the engine once, cached in .cache/ (~20 min on 2 cores)
python tools/dev_render.py render MU,SHOP.TO     # those stock pages + data files into .cache/prev/ (~1 min)
PAGES=home,stocks,watchlist,me,guide python tools/dev_render.py render SHOP.TO
node tools/dev_serve.mjs .cache/prev 8792        # serve it, with a fake signed-in account
python tools/smoke.py http://localhost:8792 --local
```

Re-run `engine` only when prices or a play's code changed. The cache is a pickle tied
to the code that wrote it; delete `.cache/` if renders start failing after an engine change.

## Testing

`tools/smoke.py <base-url>` opens the key pages at 390 and 1280 wide and fails on: a
page that doesn't load, a script error, a failed request, sideways scroll, a missing
headline, a retired page that doesn't forward, or data older than four days.
`.github/workflows/smoke.yml` runs it against the live site after every deploy and daily,
so GitHub emails Dave when something breaks.

## Data quality

`tools/qstrat/quality.py` checks fundamentals before they're published (P/E over 1,000,
yields over 25%, currency mix-ups, stale data). A failed number is replaced by the last
good one or dropped, and the build log lists what was held back.
