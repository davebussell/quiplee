/* agentkeys.mjs: who is asking the AI-tools API (/api/v1/*) and MCP server (/mcp), and how often.
 *
 * Two tiers:
 *   free    no key: get_stock_signal and search_stocks only (no factor points, flip prices or custom weights),
 *           FREE_PER_DAY calls a day from one address (ipKey, as the sign-up limit)
 *   member  a personal API key ("btp_" + 32 characters) made on the account page (POST /api/account/apikey),
 *           sent as `Authorization: Bearer <key>` or, for MCP clients that can't set headers (claude.ai custom
 *           connectors), in the URL /mcp/k/<key>. Everything, KEY_PER_DAY calls a day per key.
 *
 * Only a SHA-256 of a key is kept (like the owner stats token): on the account (u/<name>.apikey = {h, pre, at},
 * pre = the first 8 characters, for display) and as k/<hash> -> {u} in the same Blobs store, written on create
 * and deleted on revoke, so a key is looked up in one read. A key whose account is no longer a member
 * (membership() in account.mjs: free for every account until FREE_UNTIL, $5 a month after) gets the free tier,
 * with a note saying so.
 */
import { createHash, randomBytes } from "node:crypto";
import { store as acctStore, membership, overLimit, ipKey, FREE_UNTIL_LABEL } from "./account.mjs";

export const FREE_PER_DAY = 30;
export const KEY_PER_DAY = 2000;
export const KEY_RX = /^btp_[A-Za-z0-9_-]{32}$/;
export { FREE_UNTIL_LABEL };

export const newKey = () => "btp_" + randomBytes(24).toString("base64url");
export const keyHash = (key) => createHash("sha256").update(String(key)).digest("hex");
export const keyPrefix = (key) => String(key).slice(0, 8);

export const BAD_KEY = "That API key isn't valid: it may have been revoked or mistyped. Make a new one on your account page (https://bethepuck.com/me/#apikey), or leave the key out for the free sample.";
export const LAPSED = "This API key's account isn't a Be The Puck member right now, so it gets the free sample only. Membership is $5 a month: https://bethepuck.com/members/";
export const BUSY = "Be The Puck couldn't check that key just now, so this answer is the free sample. Try again in a minute.";

/** The key a request carries: the MCP secret URL's, else the Authorization header's (Bearer or bare). */
export function keyOf(req, fromPath = null) {
  if (fromPath) return String(fromPath).trim();
  const h = (req.headers.get("authorization") || "").trim();
  return h ? h.replace(/^Bearer\s+/i, "").trim() : null;
}

/** {tier: "free"|"member"|"bad", u?, note?, rl: the rate-limit key}. "bad" = a key was sent that isn't one (revoked, mistyped). */
export async function tierFor(req, context, fromPath = null) {
  const key = keyOf(req, fromPath);
  const free = (note) => ({ tier: "free", note: note || null, rl: ipKey(req, context, "agentfree") });
  if (!key) return free();
  if (!KEY_RX.test(key)) return { tier: "bad", note: BAD_KEY, rl: ipKey(req, context, "agentfree") };
  const h = keyHash(key);
  let s, rec, acct;
  try {
    s = acctStore();
    rec = await s.get("k/" + h, { type: "json" });
    acct = rec && rec.u ? await s.get("u/" + rec.u, { type: "json" }) : null;
  } catch (e) {
    return free(BUSY);
  }
  if (!acct || !acct.apikey || acct.apikey.h !== h) return { tier: "bad", note: BAD_KEY, rl: ipKey(req, context, "agentfree") };
  if (!membership(acct).active || !acct.email_ok) return free(LAPSED);   // a member with a confirmed email (account.mjs apikey)
  return { tier: "member", u: rec.u, note: null, rl: "rl/agentkey:" + h.slice(0, 32) };
}

/** True if this call is over the tier's daily limit (and counts it if not). */
export async function overDaily(t) {
  let s;
  try { s = acctStore(); } catch (e) { return false; }      // no Blobs (local): no limit
  return overLimit(s, t.rl, t.tier === "member" ? KEY_PER_DAY : FREE_PER_DAY, 86400);
}

export const limitWords = (t) => t.tier === "member"
  ? `This key has used its ${KEY_PER_DAY.toLocaleString("en-US")} calls for today. The count starts again 24 hours after the first call of the day.`
  : `The free sample is ${FREE_PER_DAY} calls a day from one address, and they're used up for today. A Be The Puck membership key gives ${KEY_PER_DAY.toLocaleString("en-US")} a day: https://bethepuck.com/developers/`;

/** Create (or replace) and revoke an account's key, for POST /api/account/apikey. Returns the new key once. */
export async function createKey(s, u, updateAccount) {
  const key = newKey(), h = keyHash(key), at = new Date().toISOString();
  await s.setJSON("k/" + h, { u, at });
  let old = null;
  const out = await updateAccount(s, u, (a) => { old = a.apikey || null; return { ...a, apikey: { h, pre: keyPrefix(key), at } }; });
  if (out.error) { await s.delete("k/" + h).catch(() => {}); return out; }
  if (old && old.h && old.h !== h) await s.delete("k/" + old.h).catch(() => {});
  return { key, apikey: { pre: keyPrefix(key), at } };
}
export async function revokeKey(s, u, updateAccount) {
  let old = null;
  const out = await updateAccount(s, u, (a) => { old = a.apikey || null; const n = { ...a }; delete n.apikey; return n; });
  if (out.error) return out;
  if (old && old.h) await s.delete("k/" + old.h).catch(() => {});
  return { ok: true };
}
