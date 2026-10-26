/* watch.mjs — the "add your stocks" queue (Netlify Function + Netlify Blobs).
 *
 * POST /api/watch  {"tickers": ["KO", "SHOP.TO"]}  -> {"queued": [...], "rejected": [...], "unavailable": [...]}
 *   Records each requested ticker (first/last request time, request count).
 *   Nothing personal is stored: only the ticker symbols.
 * GET  /api/watch  -> {"requests": [{"sym": "KO", "first": "...", "last": "...", "count": 3}, ...]}
 *   Read by the nightly GitHub Action (tools/sync_requests.py), which checks each
 *   symbol has price history, adds it to the universe, and the next build
 *   publishes its analysis. The watchlist page also reads it to show what's queued.
 */
import { queueStore, enqueue } from "../lib/watchq.mjs";

const MAX_PER_REQUEST = 25;   // EXCLUDED, VALID and the queue itself live in netlify/lib/watchq.mjs
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", "access-control-allow-origin": "*" },
  });

export default async (req) => {
  let store;
  try {
    store = queueStore();
  } catch (e) {
    return json({ error: "The request queue is unavailable right now." }, 503);
  }
  try {
    if (req.method === "GET") {
      const { blobs } = await store.list();
      const out = [];
      for (const b of blobs) {
        const v = await store.get(b.key, { type: "json" });
        if (v) out.push({ sym: decodeURIComponent(b.key), ...v });
      }
      out.sort((a, b) => (a.first < b.first ? -1 : 1));
      return json({ requests: out });
    }
    if (req.method === "POST") {
      let body;
      try { body = await req.json(); } catch (e) { return json({ error: "Send JSON like {\"tickers\": [\"KO\"]}." }, 400); }
      const list = Array.isArray(body && body.tickers) ? body.tickers : [];
      const syms = [...new Set(list.map((s) => String(s).trim().toUpperCase()).filter(Boolean))].slice(0, MAX_PER_REQUEST);
      return json(await enqueue(syms, store));
    }
    if (req.method === "OPTIONS") return json({}, 204);
    return json({ error: "Use GET or POST." }, 405);
  } catch (e) {
    return json({ error: "The request queue hit an error. Try again in a minute." }, 500);
  }
};

export const config = { path: "/api/watch" };
