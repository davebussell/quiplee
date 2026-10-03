/* picks-state.mjs: the top-picks history (members-only data, kept out of the repo).
 *
 * GET /api/picks-state  -> the history JSON, or 404 before the first review
 * PUT /api/picks-state  -> replaces it (also kept as a dated copy, for the record)
 * Both need "Authorization: Bearer <PICKS_STATE_TOKEN>". Only the site build
 * (tools/qstrat/picks.py) calls this; the /picks/ page is rendered at build time.
 */
import { getStore } from "@netlify/blobs";
import { createHash, timingSafeEqual } from "node:crypto";

const env = (k) => {
  try { const v = globalThis.Netlify?.env?.get(k); if (v) return v; } catch (e) { /* local */ }
  return process.env[k] || "";
};
const json = (body, status = 200) =>
  new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const digest = (s) => createHash("sha256").update(String(s)).digest();

export default async (req) => {
  const tok = env("PICKS_STATE_TOKEN");
  if (!tok) return json({ error: "not configured" }, 503);
  const given = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!timingSafeEqual(digest(given), digest(tok))) return json({ error: "unauthorized" }, 401);
  const store = getStore({ name: "picks", consistency: "strong" });
  if (req.method === "GET") {
    const v = await store.get("state", { type: "text" });
    return v ? json(v) : json({ error: "no history yet" }, 404);
  }
  if (req.method === "PUT") {
    const text = await req.text();
    let st;
    try { st = JSON.parse(text); } catch (e) { return json({ error: "bad json" }, 400); }
    if (!st || st.v !== 1 || !Array.isArray(st.positions) || !st.last_review || text.length > 2_000_000) return json({ error: "bad state" }, 400);
    await store.set("state", text);
    await store.set("history/" + st.last_review, text);
    return json({ ok: true, last_review: st.last_review });
  }
  return json({ error: "method" }, 405);
};

export const config = { path: "/api/picks-state" };
