# Quiplee

**News breaks. We tell you what it's worth.**

A zero-build static web app: a real-time, news-feel desk that reads every market
story and tells you its **revenue impact** and **anticipated move** on the stock —
with **lookback** (how past stories moved that stock) and **similar-story**
evidence (how comparable events moved peers). Includes a **Story Screener**
(arm a topic, get pinged on revenue-impacting hits) and **smart filters** by
story type, impact, and direction.

See [BRAND.md](BRAND.md) for the full brand & content strategy.

## Run locally

No build step:

```bash
npx serve . -l 5060      # or:  python -m http.server 5060
```

Open <http://localhost:5060>. Sign in with any valid-looking email + any password
(client-side demo auth → local `q_session` cookie).

## Deploy

Static publish to Netlify (point quiplee.com at the site) — `git push` /
`netlify deploy`, no build command.

## How it works

```
index.html      login + app shell (feed / screener / alerts / watchlist) + detail modal
styles.css      newsroom × terminal theme (violet accent; green/red = impact only)
js/auth.js      cookie session gate (client-side demo)
js/data.js      universe, ~18 seed stories w/ outcomes, the IMPACT ENGINE,
                lookback() + similar() lookups, and the live story generator
js/store.js     watched tickers, armed topics, filters, alerts, live buffer
js/ui.js        all rendering: story cards, detail (impact/lookback/similar), toasts
js/app.js       boot, real-time loop, alert logic, event wiring
```

**The impact engine** (`js/data.js → evaluate()`): classifies each story by type +
headline keywords into a verdict — *revenue-impacting?*, direction, magnitude,
expected move range, confidence, and the revenue *mechanism*. Curated seed stories
ship with hand-tuned verdicts and realized outcomes; live-generated stories are
scored by the same `evaluate()` so the desk feels real in real time.

**Alerts** (the spec's core): when a live story is revenue-impacting **and** hits a
**watched ticker**, Quiplee reports the stock; when it hits an **armed topic**, it
fires the alert about the affected stock. Both land in **Alerts** + a toast.

**Lookback & similar:** open any story → see how past stories moved that ticker and
how comparable events (same type / shared topic) moved peers (median 5-day move).

## Live news ingestion (real data)

A Netlify Function pulls **real headlines** and scores them with the same engine:

```
netlify/functions/news.js   server-side fetch of Google News RSS (per ticker +
                            per topic) and recent SEC EDGAR 8-K filings; returns
                            normalized stories. Zero npm deps; no browser CORS.
js/live.js                  fetches /.netlify/functions/news, enriches each item
                            via classifyType() -> topic map -> evaluate()
```

Flow: on load, `app.js` calls the function with your watched tickers + armed
topics. If it answers → **LIVE** mode (real news, polled every 60s; new
revenue-impacting hits fire alerts + optional browser notifications). If it's
unreachable (e.g. local `serve`, which doesn't run functions) → **DEMO** mode
(synthetic generator). The header pill shows which.

**Tagged-news APIs (optional, recommended):** the function also supports
Finnhub and Marketaux — set either env var in Netlify (Site settings →
Environment variables) and redeploy; no code change needed:

- `FINNHUB_KEY` — per-ticker company news, free tier 60 calls/min (finnhub.io)
- `MARKETAUX_KEY` — one multi-ticker call with entity tags, free ~100/day (marketaux.com)

Stories from all sources are deduped client-side by normalized headline.

**Local dev:** `npx serve` shows DEMO mode (no functions). To run the functions
locally, use `netlify dev` instead.

## Real outcomes & the scoreboard

Real stories persist in `localStorage` (`q_stories`, cap 200) and **age into
evidence**: `js/outcomes.js` joins each story's timestamp to the real daily
close series (from `netlify/functions/prices.js`, 6-month range) — baseline =
last close before publication, then realized **next-day** and **5-day** moves.

- **Story detail** shows *Anticipated* vs **Realized so far** (with a
  ✓ correct / ✗ missed direction grade).
- **Lookback / Similar** rank real outcomes (marked ✓) above the demo seed set.
- **Model scoreboard** (right rail) grades every real, revenue-impacting,
  directional call against the actual next-day move — calibration in public,
  per the brand's "honest by design" pillar.

## Roadmap
- Benzinga-via-Polygon WebSocket for trader-grade, low-latency tagged news.
- Server-side `evaluate()` + a DB (Supabase) so verdicts/outcomes are stored
  once and pushed via realtime — and history is shared across devices (today
  it's per-browser via localStorage).
- Real auth (Netlify Function → HttpOnly session cookie).

## Notes
- Heuristic impact model — **not financial advice**.
- `node --check js/*.js` and `netlify/functions/*.js` pass (plain ES5-ish, no build).
