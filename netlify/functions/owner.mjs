/* owner.mjs: who has signed up, for the site owner only.
 *
 *   GET /api/owner/stats            -> totals, new in the last day/week/month, the latest sign-ups
 *   GET /api/owner/stats?consume=1  -> the same, plus `new`: accounts created since the last
 *                                      consume call (the hourly phone notification uses this, so
 *                                      each sign-up is reported once)
 *
 * Who may ask:
 *   - the owner's members-password cookie (the /owner/ page), which also sees email addresses
 *   - a bearer token whose SHA-256 is OWNER_TOKEN_SHA256 below (or QM_STATS_TOKEN, if set in
 *     Netlify). Only the hash lives in this public repo; the token itself is held by the owner's
 *     scheduled notification task. Token replies carry usernames and dates, never emails.
 *
 * Accounts are the u/<name> records in the "paper" store (netlify/lib/account.mjs); free
 * Start/Stop email subscribers are the sub/<id> records in the "alerts" store.
 */
import { getStore } from "@netlify/blobs";
import { createHash, timingSafeEqual } from "node:crypto";
import { env, member, json } from "../lib/qm.mjs";
import { store as acctStore } from "../lib/account.mjs";
import { STORE as ALERTS } from "../lib/freealerts.mjs";

const OWNER_TOKEN_SHA256 = "4dff5d98058f8d5ca84f7feb6b8a3dc6ca2e245fc3f05fba1199cb1045e228ca";
const CURSOR = "owner/notified_at";
const DAY = 864e5;

const sha = (s) => createHash("sha256").update(String(s)).digest();
function tokenOk(req) {
  const t = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!t) return false;
  const want = [Buffer.from(OWNER_TOKEN_SHA256, "hex")];
  if (env("QM_STATS_TOKEN")) want.push(sha(env("QM_STATS_TOKEN")));
  const got = sha(t);
  return want.some((w) => w.length === got.length && timingSafeEqual(w, got));
}

async function keys(s, prefix) {
  const out = [];
  for await (const page of s.list({ prefix, paginate: true })) out.push(...page.blobs.map((b) => b.key));
  return out;
}
async function readAll(s, ks) {
  const out = [];
  for (let i = 0; i < ks.length; i += 25) {
    const recs = await Promise.all(ks.slice(i, i + 25).map((k) => s.get(k, { type: "json" }).catch(() => null)));
    recs.forEach((r, j) => { if (r) out.push([ks[i + j], r]); });
  }
  return out;
}

/** Everything the owner sees. withEmail adds the address to each recent sign-up. */
export async function stats({ withEmail = false, since = null } = {}) {
  const s = acctStore();
  const accts = await readAll(s, await keys(s, "u/"));
  const t = Date.now();
  const rows = accts.map(([k, a]) => ({
    name: a.name || k.slice(2), created: a.created || null, email: a.email || null, email_ok: !!a.email_ok,
    alerts: !!(a.alerts && a.alerts.on), follow: (a.follow || []).length,
  })).sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));
  const age = (r) => (r.created ? t - Date.parse(r.created) : Infinity);
  let subs = { total: 0, confirmed: 0 };
  try {
    const as = getStore({ name: ALERTS, consistency: "strong" });
    const recs = await readAll(as, await keys(as, "sub/"));
    subs = { total: recs.length, confirmed: recs.filter(([, r]) => r.confirmed).length, weekly: recs.filter(([, r]) => r.confirmed && r.weekly).length };
  } catch (e) { /* the alerts store is optional */ }
  const pick = (r) => {
    const o = { name: r.name, created: r.created, email_confirmed: r.email_ok, alerts: r.alerts, follows: r.follow };
    if (withEmail) o.email = r.email;
    return o;
  };
  const out = {
    asof: new Date(t).toISOString(),
    accounts: {
      total: rows.length,
      with_email: rows.filter((r) => r.email).length,
      email_confirmed: rows.filter((r) => r.email_ok).length,
      alerts_on: rows.filter((r) => r.alerts).length,
      new_24h: rows.filter((r) => age(r) < DAY).length,
      new_7d: rows.filter((r) => age(r) < 7 * DAY).length,
      new_30d: rows.filter((r) => age(r) < 30 * DAY).length,
    },
    subscribers: subs,
    recent: rows.slice(0, withEmail ? 50 : 10).map(pick),
  };
  if (since !== null) out.new = rows.filter((r) => r.created && r.created > since).map(pick).reverse();
  return out;
}

export default async (req) => {
  const url = new URL(req.url);
  if (req.method !== "GET") return json({ error: "method" }, 405);
  if (!url.pathname.endsWith("/stats")) return json({ error: "not found" }, 404);
  const m = member(req);
  const owner = m.ok && m.kind === "pw";
  const bearer = !owner && tokenOk(req);
  if (!owner && !bearer) return json({ error: "Owner only." }, 401);
  try {
    if (bearer && url.searchParams.get("consume") === "1") {
      const s = acctStore();
      const cur = await s.get(CURSOR, { type: "json" });
      const out = await stats({ since: cur ? cur.at : "" });
      // the first check only starts the clock, so the first notification isn't every account ever
      if (!cur) { out.new = []; await s.setJSON(CURSOR, { at: out.asof }); return json(out); }
      if (out.new.length) await s.setJSON(CURSOR, { at: out.new[out.new.length - 1].created });
      return json(out);
    }
    return json(await stats({ withEmail: owner }));
  } catch (e) {
    console.error("owner stats", e);
    return json({ error: "Couldn't read the accounts. Try again." }, 500);
  }
};

export const config = { path: "/api/owner/*" };
