/* qm.mjs: Quiplee Members helpers shared by the Node functions.
 *
 * A member cookie ("qm") is  v1.<base64url JSON payload>.<base64url HMAC-SHA256>
 * signed with QM_SECRET. Payloads:
 *   {k: "pw",  h, iat, exp}   signed in with the members' password; h ties it to
 *                             the current QM_PASS_HASH, so changing the password
 *                             signs everyone out
 *   {k: "sub", id, iat, exp}  a PayPal subscriber (id = subscription id); exp is
 *                             short and /api/member/refresh renews it while the
 *                             subscription is active
 *   {k: "ml",  id, exp}       a one-time sign-in link sent by email (not a cookie)
 * netlify/edge-functions/member-gate.js checks the same format (Deno, Web Crypto).
 */
import { createHmac, createHash, pbkdf2, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";

const pbkdf2p = promisify(pbkdf2);
export const COOKIE = "qm";
export const DAY = 86400;
export const PW_DAYS = 30;
export const SUB_DAYS = 3;
export const COOKIE_DAYS = 400;

export const env = (k) => {
  try {
    const v = globalThis.Netlify?.env?.get(k);
    if (v != null && v !== "") return v;
  } catch (e) { /* not on Netlify */ }
  return process.env[k] || "";
};
export const now = () => Math.floor(Date.now() / 1000);
export const pwTag = (passHash) => createHash("sha256").update(passHash).digest("base64url").slice(0, 12);
export const hashId = (s, secret) => createHash("sha256").update(String(s) + "|" + secret).digest("base64url").slice(0, 24);

export function sign(payload, secret) {
  const body = "v1." + Buffer.from(JSON.stringify(payload)).toString("base64url");
  return body + "." + createHmac("sha256", secret).update(body).digest("base64url");
}

/** The payload if the signature is good (expiry is the caller's call), else null. */
export function verify(token, secret) {
  if (!token || !secret || typeof token !== "string" || token.length > 2000) return null;
  const i = token.lastIndexOf(".");
  if (i < 4 || !token.startsWith("v1.")) return null;
  const body = token.slice(0, i);
  const sig = Buffer.from(token.slice(i + 1), "base64url");
  const want = createHmac("sha256", secret).update(body).digest();
  if (sig.length !== want.length || !timingSafeEqual(sig, want)) return null;
  try {
    return JSON.parse(Buffer.from(body.slice(3), "base64url").toString("utf8"));
  } catch (e) {
    return null;
  }
}

/** stored: pbkdf2-sha256$<iterations>$<salt b64url>$<hash b64url> */
export async function checkPassword(pw, stored) {
  const parts = String(stored || "").split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2-sha256") return false;
  const iter = parseInt(parts[1], 10);
  if (!(iter >= 10000 && iter <= 2000000)) return false;
  const salt = Buffer.from(parts[2], "base64url");
  const want = Buffer.from(parts[3], "base64url");
  if (!want.length) return false;
  const got = await pbkdf2p(String(pw || "").slice(0, 200), salt, iter, want.length, "sha256");
  return timingSafeEqual(got, want);
}

export function readCookie(req, name = COOKIE) {
  const h = req.headers.get("cookie") || "";
  for (const part of h.split(";")) {
    const j = part.indexOf("=");
    if (j > 0 && part.slice(0, j).trim() === name) return part.slice(j + 1).trim();
  }
  return null;
}

export const setCookie = (token, days) => `${COOKIE}=${token}; Path=/; Max-Age=${Math.round(days * DAY)}; HttpOnly; Secure; SameSite=Lax`;
export const clearCookie = () => `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;

/** Only same-site paths: /picks/, /articles/stocks/nvda/ ... */
export function safeNext(n, fallback = "/picks/") {
  if (typeof n !== "string" || n.length > 300 || !/^\/[A-Za-z0-9\-._~/]*$/.test(n) || n.startsWith("//") || n.includes("..")) return fallback;
  return n;
}

/** {ok, kind, id, payload, expired} for the request's cookie. */
export function member(req) {
  const secret = env("QM_SECRET");
  const p = verify(readCookie(req), secret);
  if (!p) return { ok: false };
  const live = typeof p.exp === "number" && p.exp > now();
  if (p.k === "pw") {
    const stored = env("QM_PASS_HASH");
    return { ok: live && !!stored && p.h === pwTag(stored), kind: "pw", id: "owner", payload: p };
  }
  if (p.k === "sub" && p.id) return { ok: live, kind: "sub", id: p.id, payload: p, expired: !live };
  return { ok: false };
}

export const redirect = (location, cookie, status = 303) => {
  const headers = { location, "cache-control": "no-store" };
  if (cookie) headers["set-cookie"] = cookie;
  return new Response(null, { status, headers });
};
export const json = (body, status = 200, cookie) => {
  const headers = { "content-type": "application/json", "cache-control": "no-store" };
  if (cookie) headers["set-cookie"] = cookie;
  return new Response(JSON.stringify(body), { status, headers });
};

export async function readBody(req) {
  const type = req.headers.get("content-type") || "";
  const text = (await req.text()).slice(0, 20000);
  if (type.includes("application/json")) {
    try { return JSON.parse(text) || {}; } catch (e) { return {}; }
  }
  return Object.fromEntries(new URLSearchParams(text));
}

/** A member record is active while PayPal says so, or until the end of the period already paid for. */
export function activeRecord(rec) {
  if (!rec) return false;
  if (rec.status === "ACTIVE") return true;
  return !!rec.paid_through && Date.parse(rec.paid_through) > Date.now();
}

export const siteUrl = () => (env("URL") || "https://quiplee.com").replace(/\/$/, "");

/** A one-time sign-in link for a subscriber, good for 7 days. */
export function linkFor(id, next = "/picks/") {
  const t = sign({ k: "ml", id, next, exp: now() + 7 * DAY }, env("QM_SECRET"));
  return siteUrl() + "/api/member/magic?t=" + encodeURIComponent(t);
}
