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
revenue-impacting hits fire alerts). If it's unreachable (e.g. local `serve`,
which doesn't run functions) → **DEMO** mode (synthetic generator). The header
pill shows which. Seed stories stay on as the historical *memory* for lookback /
similar. No API key required (Google News + EDGAR are free); add a tagged-news
API (Benzinga/Marketaux/Finnhub) next for cleaner ticker tags + lower latency.

**Local dev:** `npx serve` shows DEMO mode (no functions). To run the function
locally, use `netlify dev` instead.

## Roadmap
- Tagged-news API (Benzinga via Polygon / Marketaux / Finnhub) for reliable ticker
  tags, sentiment, and real-time webhooks.
- Real realized outcomes: join story timestamps to price data so lookback/similar
  use actual returns.
- Server-side `evaluate()` + a DB (Supabase) so verdicts are stored and pushed
  via realtime instead of recomputed per client.

## Notes
- Heuristic impact model — **not financial advice**.
- `node --check js/*.js` and `netlify/functions/*.js` pass (plain ES5-ish, no build).
