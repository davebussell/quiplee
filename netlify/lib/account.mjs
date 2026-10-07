/* account.mjs: the one Be The Puck account, shared by My Puck (account.mjs), the
 * member tools (member.mjs) and the nightly emails.
 *
 * An account lives in the Blobs store "paper" (it began as the paper-trading game's,
 * which was retired in October 2026; old p/ and h/ records are left as they were):
 *   u/<name>  {name, pw, v, created, email, email_ok, email_at, confirm_sent,
 *              follow: [SYM], alerts: {on, level: "light"|"all"}, rules, seen}
 *   p/<name>  the paper portfolio      h/<name> its nightly values
 *   e/<hash>  {u}: who owns an email address (hash keyed with QM_SECRET)
 *   as/<name> the calls last emailed (so an email only goes out on a change)
 * <name> is the lower-cased username. Accounts made for the old game have no email until the
 * player adds one in My Puck.
 *
 * Cookies, all signed with QM_SECRET (see qm.mjs):
 *   pt       {k: "pt", u, v}    the account session (HttpOnly, 180 days)
 *   qm       {k: "acct", u}     member pages, free for every account until FREE_UNTIL
 *   bp_name  the display name, readable by the page so the header can say who's in
 * Email links: {k: "ec", u, e} confirm an address (14 days), {k: "pr", u, v} reset a
 * password (1 hour, dies once the password changes), {k: "au", u} stop the emails.
 */
import { getStore } from "@netlify/blobs";
import { pbkdf2, randomBytes } from "node:crypto";
import { promisify } from "node:util";
import { env, now, DAY, sign, verify, readCookie, hashId, siteUrl } from "./qm.mjs";

const pbkdf2p = promisify(pbkdf2);
export const STORE = "paper";
export const ITER = 310000;
export const PT = "pt";
export const PT_DAYS = 180;
// Member tools are free for every account until midnight on January 1, 2027 (Toronto time).
export const FREE_UNTIL = Date.UTC(2027, 0, 1, 5, 0, 0);
export const FREE_UNTIL_LABEL = "January 1, 2027";
export const freeNow = () => Date.now() < FREE_UNTIL;
export const MAX_FOLLOW = 100;
export const NAME_RX = /^[A-Za-z0-9_]{3,20}$/;
export const EMAIL_RX = /^[^\s@<>"',;]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$/;
const RESERVED = new Set(["admin", "administrator", "bethepuck", "puck", "support", "help", "root", "moderator", "mod", "system",
  "staff", "official", "anonymous", "null", "undefined", "me", "api", "paper", "leaders", "player", "dave", "claude", "house"]);
const BLOCKED = ["fuck", "shit", "cunt", "nigg", "fag", "rape", "nazi", "hitler", "whore", "slut", "kike", "spic", "chink", "retard"];

export const store = () => getStore({ name: STORE, consistency: "strong" });
export const lc = (s) => String(s || "").toLowerCase();
export const emailKey = (email) => "e/" + hashId("acct-email:" + lc(String(email).trim()), env("QM_SECRET"));
export const emailTag = (email) => hashId("tag:" + lc(String(email).trim()), env("QM_SECRET")).slice(0, 10);

export async function hashPassword(pw) {
  const salt = randomBytes(16);
  const h = await pbkdf2p(String(pw).slice(0, 200), salt, ITER, 32, "sha256");
  return `pbkdf2-sha256$${ITER}$${salt.toString("base64url")}$${h.toString("base64url")}`;
}

export function nameProblem(name) {
  if (!NAME_RX.test(name || "")) return "Usernames are 3 to 20 letters, numbers or underscores.";
  const l = lc(name);
  if (RESERVED.has(l) || BLOCKED.some((w) => l.includes(w))) return "That username isn't available. Try another.";
  return null;
}

export function passwordProblem(pw, name, email) {
  if (pw.length < 8 || pw.length > 200) return "Passwords need at least 8 characters.";
  if (lc(pw) === lc(name) || (email && lc(pw) === lc(email))) return "Pick a password that isn't your username or email.";
  return null;
}

// ------------------------------------------------------------------ cookies
const base = "Path=/; Secure; SameSite=Lax";
export const ptCookie = (u, v) => {
  const t = now();
  return `${PT}=${sign({ k: "pt", u, v, iat: t, exp: t + PT_DAYS * DAY }, env("QM_SECRET"))}; ${base}; HttpOnly; Max-Age=${PT_DAYS * DAY}`;
};
export const clearPt = () => `${PT}=; ${base}; HttpOnly; Max-Age=0`;
export const nameCookie = (name) => `bp_name=${encodeURIComponent(name)}; ${base}; Max-Age=${PT_DAYS * DAY}`;
export const clearName = () => `bp_name=; ${base}; Max-Age=0`;

/** The member-pages cookie for an account while member tools are free (null after FREE_UNTIL). */
export function memberCookie(u) {
  if (!freeNow()) return null;
  const t = now(), exp = Math.min(t + PT_DAYS * DAY, Math.floor(FREE_UNTIL / 1000));
  return `qm=${sign({ k: "acct", u, iat: t, exp }, env("QM_SECRET"))}; ${base}; HttpOnly; Max-Age=${exp - t}`;
}
/** True if the request already carries a paid or owner member cookie, which an account sign-in must not replace. */
export function hasPaidCookie(req) {
  const p = verify(readCookie(req, "qm"), env("QM_SECRET"));
  return !!(p && (p.k === "pw" || p.k === "sub") && p.exp > now());
}
/** Session + display name, and the member cookie for accounts with an email (free until FREE_UNTIL). */
export function signInCookies(req, u, acct) {
  const out = [ptCookie(u, acct.v || 1), nameCookie(acct.name)];
  if (acct.email && !hasPaidCookie(req)) { const m = memberCookie(u); if (m) out.push(m); }
  return out;
}
export function signOutCookies(req) {
  const out = [clearPt(), clearName()];
  const p = verify(readCookie(req, "qm"), env("QM_SECRET"));
  if (p && p.k === "acct") out.push(`qm=; ${base}; HttpOnly; Max-Age=0`);
  return out;
}

/** A JSON reply that can set several cookies. */
export function reply(body, status = 200, cookies = []) {
  const h = new Headers({ "content-type": "application/json", "cache-control": "no-store" });
  for (const c of cookies) if (c) h.append("set-cookie", c);
  return new Response(JSON.stringify(body), { status, headers: h });
}
export function redirectWith(location, cookies = []) {
  const h = new Headers({ location, "cache-control": "no-store" });
  for (const c of cookies) if (c) h.append("set-cookie", c);
  return new Response(null, { status: 303, headers: h });
}

// ------------------------------------------------------------------ sessions and records
export async function session(req, s) {
  const p = verify(readCookie(req, PT), env("QM_SECRET"));
  if (!p || p.k !== "pt" || !p.u || !(p.exp > now())) return null;
  const acct = await s.get("u/" + p.u, { type: "json" });
  if (!acct || (acct.v || 1) !== p.v) return null;
  return { u: p.u, acct };
}

/** Read-modify-write an account with an ETag check. fn(acct) returns {error, status} or the new record. */
export async function updateAccount(s, u, fn) {
  for (let i = 0; i < 4; i++) {
    const got = await s.getWithMetadata("u/" + u, { type: "json" });
    if (!got || !got.data) return { error: "No account found.", status: 404 };
    const next = await fn({ ...got.data });
    if (!next || next.error) return next || { error: "No change." };
    const w = await s.setJSON("u/" + u, next, got.etag ? { onlyIfMatch: got.etag } : {});
    if (w.modified !== false) return { acct: next };
  }
  return { error: "Busy, please try again.", status: 409 };
}

/** A fixed-window counter: true if this attempt is over the limit. */
export async function overLimit(s, key, max, windowSec, bump = true) {
  try {
    let rec = (await s.get(key, { type: "json" })) || { n: 0, t: now() };
    if (now() - rec.t > windowSec) rec = { n: 0, t: now() };
    if (rec.n >= max) return true;
    if (bump) { rec.n += 1; await s.setJSON(key, rec); }
    return false;
  } catch (e) {
    return false;
  }
}
export function ipKey(req, context, what) {
  const ip = (context && context.ip) || req.headers.get("x-nf-client-connection-ip") || "unknown";
  return "rl/" + hashId(what + ":" + ip, env("QM_SECRET"));
}
export function crossSite(req) {
  const o = req.headers.get("origin");
  if (!o) return false;
  try { return new URL(o).host !== new URL(req.url).host; } catch (e) { return true; }
}

/** Member status for an account: free until FREE_UNTIL, then a paid subscription (not yet wired). */
export function membership(acct) {
  if (acct && acct.paid_through && Date.parse(acct.paid_through) > Date.now()) return { active: true, kind: "paid", until: acct.paid_through };
  if (freeNow()) return { active: true, kind: "free", until: new Date(FREE_UNTIL).toISOString() };
  return { active: false, kind: "none", until: null };
}

const LIMITS = ["pos", "group", "start", "crash"];
/** A member's own Start/Stop rule (/rules/): presets or play slugs, thresholds and four portfolio limits. */
export function cleanRules(r) {
  if (!r || typeof r !== "object") return null;
  const plays = (Array.isArray(r.plays) ? r.plays : []).map((x) => String(x || "").toLowerCase().replace(/[^a-z0-9-]/g, "").slice(0, 60)).filter(Boolean).slice(0, 200);
  let preset = /^[a-z]{1,16}$/.test(String(r.preset || "")) ? String(r.preset) : "all";
  if (preset === "custom" && !plays.length) preset = "all";
  let on = Number(r.on), off = Number(r.off);
  if (!(on >= 0.5 && on <= 0.95)) on = 0.6;
  if (!(off >= 0.05 && off < on)) off = Math.min(0.4, on - 0.05);
  const lim = {}, src = r.lim && typeof r.lim === "object" ? r.lim : {};
  for (const k of LIMITS) {
    const v = src[k] === null || src[k] === undefined || src[k] === "" ? NaN : Number(src[k]);
    lim[k] = v >= 0 && v <= 1 ? Math.round(v * 1000) / 1000 : null;
  }
  return { preset, plays: preset === "custom" ? [...new Set(plays)] : [], on: Math.round(on * 100) / 100, off: Math.round(off * 100) / 100, lim };
}

// ------------------------------------------------------------------ email links
export const confirmUrl = (u, email) => siteUrl() + "/api/account/confirm?t=" + encodeURIComponent(sign({ k: "ec", u, e: emailTag(email), exp: now() + 14 * DAY }, env("QM_SECRET")));
export const resetUrl = (u, v) => siteUrl() + "/me/?reset=" + encodeURIComponent(sign({ k: "pr", u, v: v || 1, exp: now() + 3600 }, env("QM_SECRET")));
export const stopToken = (u) => sign({ k: "au", u }, env("QM_SECRET"));
export const stopUrl = (u) => siteUrl() + "/api/account/unsubscribe?t=" + encodeURIComponent(stopToken(u));
export const manageUrl = () => siteUrl() + "/me/#alerts";
export function readLink(t, kind) {
  const p = verify(t, env("QM_SECRET"));
  if (!p || p.k !== kind || !p.u) return null;
  if (p.exp && p.exp < now()) return null;
  return p;
}
