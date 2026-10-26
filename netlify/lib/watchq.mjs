/* watchq.mjs: the queue of tickers Be The Puck doesn't cover yet (Netlify Blobs "watch-requests").
 * Written by /api/watch (the watchlist page) and by /api/account/follow (a member adding a name that isn't
 * covered); read nightly by tools/sync_requests.py, which checks each has a price history and adds it to
 * data/universe/requested.json. Requested names are private on the site: analysed every night, shown only to
 * the readers who follow them (tools/qstrat/render.py PRIVATE_SLUGS). Only symbols are stored, nothing personal. */
import { getStore } from "@netlify/blobs";

// Tickers Be The Puck doesn't cover even on request (kept in step with EXCLUDED in tools/qstrat/content.py)
export const EXCLUDED = new Set(["MGRC", "WSC", "TRNS"]);
// AAPL, BRK-B, SHOP.TO, LEAP.V, BTC-USD, ^GSPC, CTC-A.TO
export const VALID = /^\^?[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,2})?(?:[.-][A-Z0-9]{1,4})?$/;
export const MAX_KEYS = 3000;

export function queueStore() {
  return getStore({ name: "watch-requests", consistency: "strong" });
}

/** Record each ticker as requested (first/last time, count). Returns {queued, rejected, unavailable}. */
export async function enqueue(syms, store = queueStore()) {
  const { blobs } = await store.list();
  const known = new Set(blobs.map((b) => b.key));
  const queued = [], rejected = [], unavailable = [];
  const now = new Date().toISOString();
  for (const s of syms) {
    if (!VALID.test(s)) { rejected.push(s); continue; }
    if (EXCLUDED.has(s)) { unavailable.push(s); continue; }
    const key = encodeURIComponent(s);
    if (!known.has(key) && known.size >= MAX_KEYS) { rejected.push(s); continue; }
    const prev = known.has(key) ? await store.get(key, { type: "json" }) : null;
    await store.setJSON(key, { first: (prev && prev.first) || now, last: now, count: ((prev && prev.count) || 0) + 1 });
    known.add(key);
    queued.push(s);
  }
  return { queued, rejected, unavailable };
}
