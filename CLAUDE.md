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
- Financial content states facts and evidence, never a recommendation addressed to the reader.
- **Never label any ticker as Dave's own holding** on the site.
- **MGRC stays excluded** from the universe.
- **Credentials:** never type a password, PIN, API key or token into anything. Dave enters
  PayPal, Stripe, Resend, Netlify and Anthropic keys himself (Netlify env vars or GitHub
  secrets). Never sign in to the live site's owner gate or create accounts on the live site;
  test accounts only on localhost (`tools/dev_serve.mjs` fakes the account API). The owner
  gate's password exists only as a PBKDF2 hash in `QM_PASS_HASH`; the owner stats token only as
  its hash in the repo.
- **Ask Dave first** before: changing Netlify settings (including DNS), sending any email on
  his behalf, or editing Canva designs.
- **Commits:** author `Claude <noreply@anthropic.com>`, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and the session's
  `Claude-Session:` line.

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

## How it fits together

- `tools/build_strategies.py` builds the whole site into `_site/` from `data/` (no network).
  The engine (`tools/qstrat/engine.py`) runs every play on every ticker since 2005, then
  `tools/qstrat/render.py` and friends write the pages.
- `.github/workflows/refresh-prices.yml` refreshes `data/` twice a day (prices, macro,
  fundamentals, news, earnings and ratings) and commits; that push triggers a deploy.
- Company numbers: `tools/fetch_sec.py` keeps each SEC filer's quarters in `data/sec/` (dated by
  filing, so backtests never see the future); `tools/qstrat/secfund.py` turns them into P/E,
  growth, margins and debt. Yahoo (`tools/fetch_fundamentals.py`) covers the rest (TSX-only
  names, forward estimates, analyst targets). Prefer SEC numbers wherever a company files 10-Qs.
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
