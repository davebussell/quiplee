/* alerts.mjs: free email alerts when the Start/Stop light flips on a reader's stocks.
 *
 *   POST /api/alerts/subscribe   {email, tickers, consent}  -> stores the request and emails a confirm link
 *   GET  /api/alerts/confirm?t=                             -> confirms, back to /alerts/?confirmed=1&m=<manage token>
 *   GET  /api/alerts/manage?t=                              -> {email (masked), tickers, confirmed}
 *   POST /api/alerts/update      {t, tickers}               -> changes the list (token proves it's theirs)
 *   POST /api/alerts/unsubscribe?t=                         -> deletes the subscription (also one-click from mail apps);
 *                                                              a GET only opens the page with the unsubscribe button
 *
 * Nothing is sent until the address is confirmed. Emails need RESEND_API_KEY
 * (and bethepuck.com verified in Resend); without it requests are kept and the
 * nightly job (alerts-nightly.mjs) sends the confirm links once it is set.
 * The tickers that can be followed come from /data/reads.json (built nightly).
 */
import { getStore } from "@netlify/blobs";
import { env, now, json, readBody, redirect, hashId } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { STORE, MAX_TICKERS, EMAIL_RX, subId, readToken, manageToken, confirmEmail, sendOne } from "../lib/freealerts.mjs";

const store = () => getStore({ name: STORE, consistency: "strong" });

let READS = { at: 0, data: null, origin: "" };
async function reads(req) {
  const origin = new URL(req.url).origin;
  if (READS.data && READS.origin === origin && Date.now() - READS.at < 10 * 60 * 1000) return READS.data;
  const r = await fetch(origin + "/data/reads.json", { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error("reads " + r.status);
  READS = { at: Date.now(), data: await r.json(), origin };
  return READS.data;
}

function cleanTickers(list, R) {
  const out = [];
  for (const x of Array.isArray(list) ? list : String(list || "").split(/[\s,]+/)) {
    const s = String(x || "").trim().toUpperCase();
    if (s && R.t[s] && !out.includes(s)) out.push(s);
  }
  return out.slice(0, MAX_TICKERS);
}

async function limited(s, key, max, windowSec) {
  try {
    let rec = (await s.get(key, { type: "json" })) || { n: 0, t: now() };
    if (now() - rec.t > windowSec) rec = { n: 0, t: now() };
    if (rec.n >= max) return true;
    rec.n += 1;
    await s.setJSON(key, rec);
  } catch (e) { /* never block on the limiter */ }
  return false;
}

function crossSite(req) {
  const o = req.headers.get("origin");
  if (!o) return false;
  try { return new URL(o).host !== new URL(req.url).host; } catch (e) { return true; }
}

const mask = (email) => email.replace(/^(.)(.*)(@.*)$/, (m, a, b, c) => a + "•".repeat(Math.min(6, b.length)) + c);

/** Today's light for each ticker, so a new subscriber hears only about later flips. */
const lastFor = (tickers, R, prev = {}) => Object.fromEntries(tickers.map((s) => [s, prev[s] || (R.t[s] && R.t[s].L != null ? [R.t[s].L, R.t[s].k, R.t[s].of] : null)]));

async function subscribe(req, context, s) {
  const b = await readBody(req);
  const email = String(b.email || "").trim();
  if (!EMAIL_RX.test(email) || email.length > 254) return json({ error: "That email address doesn't look right." }, 400);
  if (!(b.consent === true || b.consent === "on" || b.consent === "true")) return json({ error: "Tick the box to agree to the emails." }, 400);
  let R;
  try { R = await reads(req); } catch (e) { return json({ error: "Alerts are unavailable right now. Try again in a minute." }, 503); }
  const tickers = cleanTickers(b.tickers, R);
  if (!tickers.length) return json({ error: "Add at least one stock Be The Puck covers." }, 400);
  const ip = (context && context.ip) || req.headers.get("x-nf-client-connection-ip") || "unknown";
  if (await limited(s, "rl/" + hashId("asub:" + ip, env("QM_SECRET")), 8, 3600)) return json({ error: "Too many requests from here. Try again in an hour." }, 429);
  const id = subId(email);
  if (await limited(s, "rl/" + hashId("aem:" + id, env("QM_SECRET")), 4, 3600)) return json({ error: "We've just sent a link to that address. Check your inbox (and spam folder)." }, 429);
  const rec = (await s.get("sub/" + id, { type: "json" })) || { email, tickers: [], confirmed: false, created: new Date().toISOString(), last: {} };
  // an existing, confirmed list only changes through the emailed link (so nobody can edit someone else's)
  if (rec.confirmed) rec.pending = tickers;
  else rec.tickers = tickers;
  rec.email = email;
  rec.confirm_sent = null;
  const m = confirmEmail(id, email, tickers, R);
  if (mail.configured()) {
    const r = await sendOne(m);
    if (r.sent) rec.confirm_sent = new Date().toISOString();
  }
  await s.setJSON("sub/" + id, rec);
  return json({ ok: true, mail: !!rec.confirm_sent, tickers });
}

async function confirm(req, url, s) {
  const p = readToken(url.searchParams.get("t"), "ac");
  if (!p) return redirect("/alerts/?expired=1");
  const rec = await s.get("sub/" + p.id, { type: "json" });
  if (!rec) return redirect("/alerts/?expired=1");
  let R = null;
  try { R = await reads(req); } catch (e) { /* keep going: last states fill in tonight */ }
  const tickers = Array.isArray(p.x) && p.x.length ? p.x.slice(0, MAX_TICKERS) : rec.tickers;
  rec.tickers = tickers;
  rec.confirmed = true;
  rec.confirmed_at = rec.confirmed_at || new Date().toISOString();
  delete rec.pending;
  if (R) rec.last = lastFor(tickers, R, rec.last || {});
  await s.setJSON("sub/" + p.id, rec);
  return redirect("/alerts/?confirmed=1&m=" + encodeURIComponent(manageToken(p.id)));
}

async function manage(url, s) {
  const p = readToken(url.searchParams.get("t"), "am");
  const rec = p && (await s.get("sub/" + p.id, { type: "json" }));
  if (!rec) return json({ error: "This link no longer works. Sign up again below." }, 404);
  return json({ email: mask(rec.email), tickers: rec.tickers, confirmed: !!rec.confirmed });
}

async function update(req, s) {
  const b = await readBody(req);
  const p = readToken(b.t, "am");
  const rec = p && (await s.get("sub/" + p.id, { type: "json" }));
  if (!rec) return json({ error: "This link no longer works. Sign up again below." }, 404);
  let R;
  try { R = await reads(req); } catch (e) { return json({ error: "Alerts are unavailable right now." }, 503); }
  const tickers = cleanTickers(b.tickers, R);
  if (!tickers.length) return json({ error: "Keep at least one stock, or unsubscribe instead." }, 400);
  rec.tickers = tickers;
  rec.last = lastFor(tickers, R, rec.last || {});
  await s.setJSON("sub/" + p.id, rec);
  return json({ ok: true, tickers });
}

async function unsubscribe(req, url, s) {
  let t = url.searchParams.get("t");
  // a plain link (which mail scanners sometimes open on their own) only shows the unsubscribe button
  if (req.method !== "POST") return redirect("/alerts/?unsub=1&m=" + encodeURIComponent(t || ""));
  if (!t) t = (await readBody(req)).t;
  const p = readToken(t, "am");
  if (p) await s.delete("sub/" + p.id).catch(() => {});
  // one-click unsubscribe from a mail client is a POST that wants a plain 200
  if (!req.headers.get("origin")) return new Response("Unsubscribed", { status: 200 });
  return json({ ok: true });
}

export default async (req, context) => {
  const url = new URL(req.url);
  const route = url.pathname.replace(/^\/api\/alerts\/?/, "").replace(/\/$/, "");
  if (!env("QM_SECRET")) return json({ error: "Alerts aren't set up yet." }, 503);
  let s;
  try { s = store(); } catch (e) { return json({ error: "Alerts are unavailable right now." }, 503); }
  try {
    if (route === "confirm" && req.method === "GET") return await confirm(req, url, s);
    if (route === "manage" && req.method === "GET") return await manage(url, s);
    if (route === "unsubscribe") return await unsubscribe(req, url, s);
    if (req.method !== "POST") return json({ error: "not found" }, 404);
    if (crossSite(req)) return json({ error: "Cross-site request refused." }, 403);
    if (route === "subscribe") return await subscribe(req, context, s);
    if (route === "update") return await update(req, s);
    return json({ error: "not found" }, 404);
  } catch (e) {
    console.error("alerts", route, e);
    return json({ error: "Something went wrong. Try again." }, 500);
  }
};

export const config = { path: "/api/alerts/*" };
