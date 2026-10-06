/* member-gate.js: the Be The Puck Members paywall.
 *
 * Runs in front of /picks/, /rules/ and every report under /articles/ (the hub stays
 * open). With a valid member cookie the page is served as built. Without one,
 * the page's locked version is served at the same URL: its title and opening
 * line plus a sign-in / join card, built under /locked/<path> by
 * tools/qstrat/members.py. A subscriber whose short-lived cookie has run out
 * is sent to /api/member/refresh, which renews it while PayPal says active.
 *
 * The cookie format is documented in netlify/lib/qm.mjs; this file repeats the
 * check with Web Crypto because edge functions run on Deno.
 */
const enc = new TextEncoder();

function unb64u(s) {
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  const out = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
  return out;
}

function b64u(bytes) {
  let s = "";
  for (const x of new Uint8Array(bytes)) s += String.fromCharCode(x);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function readCookie(req, name) {
  for (const part of (req.headers.get("cookie") || "").split(";")) {
    const j = part.indexOf("=");
    if (j > 0 && part.slice(0, j).trim() === name) return part.slice(j + 1).trim();
  }
  return null;
}

async function memberState(req) {
  const secret = Netlify.env.get("QM_SECRET");
  const token = readCookie(req, "qm");
  if (!secret || !token || token.length > 2000 || !token.startsWith("v1.")) return "none";
  const i = token.lastIndexOf(".");
  const body = token.slice(0, i);
  let payload;
  try {
    const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["verify"]);
    if (!(await crypto.subtle.verify("HMAC", key, unb64u(token.slice(i + 1)), enc.encode(body)))) return "none";
    payload = JSON.parse(new TextDecoder().decode(unb64u(body.slice(3))));
  } catch (e) {
    return "none";
  }
  const live = typeof payload.exp === "number" && payload.exp > Date.now() / 1000;
  if (payload.k === "pw") {
    const stored = Netlify.env.get("QM_PASS_HASH");
    if (!stored || !live) return "none";
    const tag = b64u(await crypto.subtle.digest("SHA-256", enc.encode(stored))).slice(0, 12);
    return payload.h === tag ? "member" : "none";
  }
  if (payload.k === "sub" && payload.id) return live ? "member" : "renew";
  // a Be The Puck account with an email: member tools are free until midnight, January 1, 2027 (Toronto)
  if (payload.k === "acct" && payload.u) return live && Date.now() < FREE_UNTIL ? "member" : "none";
  return "none";
}

const FREE_UNTIL = Date.UTC(2027, 0, 1, 5, 0, 0);
const PRIVATE = { "cache-control": "private, no-store", vary: "cookie" };
const OLD_HOSTS = new Set(["quiplee.com", "www.quiplee.com"]);

export default async (req, context) => {
  const url = new URL(req.url);
  const path = url.pathname;
  // the old domain forwards to the same page on bethepuck.com
  if (OLD_HOSTS.has(url.hostname)) {
    return new Response(null, { status: 301, headers: { location: "https://bethepuck.com" + path + url.search } });
  }
  // directory pages always end in a slash (relative links depend on it)
  if (!path.endsWith("/") && !/\.[a-z0-9]{1,5}$/i.test(path)) {
    return new Response(null, { status: 301, headers: { location: path + "/" + url.search } });
  }
  const state = await memberState(req);
  if (state === "member") {
    const res = await context.next();
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(PRIVATE)) out.headers.set(k, v);
    return out;
  }
  if (state === "renew") {
    return new Response(null, { status: 302, headers: { location: "/api/member/refresh?next=" + encodeURIComponent(path), ...PRIVATE } });
  }
  const locked = await fetch(new URL("/locked" + path, url), { headers: { accept: "text/html" } });
  if (!locked.ok) return new Response("Not found", { status: 404, headers: { "content-type": "text/plain", ...PRIVATE } });
  return new Response(locked.body, { status: 200, headers: { "content-type": "text/html; charset=utf-8", ...PRIVATE } });
};

export const config = {
  path: ["/picks", "/picks/*", "/articles/*", "/rules", "/rules/*"],
  excludedPath: ["/articles/", "/articles/index.html"],
};
