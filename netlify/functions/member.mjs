/* member.mjs: Quiplee Members sign-in and the member's saved list.
 *
 * POST /api/member/login     password + next  -> sets the member cookie, back to next
 * GET  /api/member/logout                     -> clears it, to /members/
 * GET  /api/member/me                         -> {member, kind, alerts}
 * GET  /api/member/refresh?next=              -> renews a subscriber's cookie while PayPal says active
 * GET  /api/member/magic?t=                   -> the sign-in link from the welcome / sign-in email
 * POST /api/member/link      email            -> emails a sign-in link to a subscriber (same reply either way)
 * GET  /api/member/list                       -> {tickers, alerts, email}
 * PUT  /api/member/list      {tickers, alerts} -> saves the list the nightly alert email checks
 *
 * Env: QM_SECRET (signs cookies), QM_PASS_HASH (pbkdf2-sha256 of the members'
 * password), QM_OWNER_EMAIL (optional: where the password member's alerts go),
 * plus PAYPAL_* and RESEND_API_KEY for subscribers (see netlify/lib).
 */
import { getStore } from "@netlify/blobs";
import {
  env, now, DAY, PW_DAYS, SUB_DAYS, COOKIE_DAYS, sign, verify, checkPassword, pwTag, hashId, readCookie,
  setCookie, clearCookie, safeNext, member, redirect, json, readBody, activeRecord, linkFor,
} from "../lib/qm.mjs";
import * as paypal from "../lib/paypal.mjs";
import * as mail from "../lib/mail.mjs";

const MAX_TRIES = 8;          // wrong passwords per connection per window
const WINDOW = 15 * 60;
const MAX_LIST = 200;
const VALID = /^\^?[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,2})?(?:[.-][A-Z0-9]{1,4})?$/;
const store = (name) => getStore({ name, consistency: "strong" });

async function limited(key) {
  try {
    const s = store("qm-login");
    let rec = (await s.get(key, { type: "json" })) || { n: 0, t: now() };
    if (now() - rec.t > WINDOW) rec = { n: 0, t: now() };
    return { s, rec, blocked: rec.n >= MAX_TRIES };
  } catch (e) {
    return { s: null, rec: { n: 0, t: now() }, blocked: false };
  }
}

async function login(req, context) {
  const secret = env("QM_SECRET");
  const stored = env("QM_PASS_HASH");
  const form = await readBody(req);
  const next = safeNext(form.next);
  if (!secret || !stored) return redirect(next + "?login=off#lock");
  const ip = (context && context.ip) || req.headers.get("x-nf-client-connection-ip") || "unknown";
  const key = hashId("ip:" + ip, secret);
  const { s, rec, blocked } = await limited(key);
  if (blocked) return redirect(next + "?login=wait#lock");
  if (!(await checkPassword(form.password, stored))) {
    rec.n += 1;
    if (s) await s.setJSON(key, rec).catch(() => {});
    return redirect(next + "?login=bad#lock");
  }
  if (s && rec.n) await s.delete(key).catch(() => {});
  const t = now();
  return redirect(next, setCookie(sign({ k: "pw", h: pwTag(stored), iat: t, exp: t + PW_DAYS * DAY }, secret), PW_DAYS));
}

async function getRecord(id) {
  return store("qm-members").get("sub/" + id, { type: "json" });
}

/** The stored record, re-checked with PayPal when it is more than 12 hours old. */
async function freshRecord(id) {
  let rec = await getRecord(id);
  if (rec && paypal.configured() && Date.now() - Date.parse(rec.checked || 0) > 12 * 3600 * 1000) {
    try {
      const sub = await paypal.getSubscription(id);
      if (sub) {
        rec = paypal.recordFrom(sub, rec);
        await store("qm-members").setJSON("sub/" + id, rec);
      }
    } catch (e) { /* PayPal unreachable: keep the stored record */ }
  }
  return rec;
}

const subCookie = (id) => {
  const t = now();
  return setCookie(sign({ k: "sub", id, iat: t, exp: t + SUB_DAYS * DAY }, env("QM_SECRET")), COOKIE_DAYS);
};

async function refresh(req) {
  const url = new URL(req.url);
  const next = safeNext(url.searchParams.get("next"));
  const p = verify(readCookie(req), env("QM_SECRET"));
  if (!p || p.k !== "sub" || !p.id) return redirect("/members/?login=lapsed#join", clearCookie());
  const rec = await freshRecord(p.id);
  if (!activeRecord(rec)) return redirect("/members/?login=lapsed#join", clearCookie());
  return redirect(next, subCookie(p.id));
}

async function magic(req) {
  const url = new URL(req.url);
  const p = verify(url.searchParams.get("t"), env("QM_SECRET"));
  if (!p || p.k !== "ml" || !p.id || !(p.exp > now())) return redirect("/members/?login=expired#signin");
  const rec = await freshRecord(p.id);
  if (!activeRecord(rec)) return redirect("/members/?login=lapsed#join", clearCookie());
  return redirect(safeNext(p.next || "/picks/"), subCookie(p.id));
}

async function sendLink(req, context) {
  const secret = env("QM_SECRET");
  const form = await readBody(req);
  const email = String(form.email || "").trim().toLowerCase().slice(0, 200);
  const done = redirect("/members/?login=sent#signin");
  if (!secret || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return done;
  const ip = (context && context.ip) || "unknown";
  const key = hashId("link:" + ip, secret);
  const { s, rec, blocked } = await limited(key);
  if (blocked) return done;
  rec.n += 1;
  if (s) await s.setJSON(key, rec).catch(() => {});
  try {
    const id = await store("qm-members").get("email/" + hashId(email, secret), { type: "text" });
    const r = id ? await freshRecord(id) : null;
    if (r && activeRecord(r)) {
      const link = linkFor(id);
      await mail.send(email, "Your Quiplee sign-in link",
        mail.shell("Sign in to Quiplee Members", `<p>Tap the button to sign in on this device. The link works for 7 days.</p>
<p style="margin:18px 0"><a href="${mail.esc(link)}" style="background:#7c6cf5;color:#fff;padding:11px 18px;border-radius:9px;text-decoration:none;font-weight:600">Sign in</a></p>
<p style="font-size:13px;color:#6b7385">Didn't ask for this? You can ignore it.</p>`),
        "Sign in to Quiplee Members: " + link);
    }
  } catch (e) { /* same reply either way */ }
  return done;
}

function cleanList(tickers) {
  const out = [];
  for (const t of Array.isArray(tickers) ? tickers : []) {
    const s = String(t || "").trim().toUpperCase();
    if (VALID.test(s) && !out.includes(s)) out.push(s);
    if (out.length >= MAX_LIST) break;
  }
  return out;
}

async function list(req, m) {
  const s = store("qm-lists");
  const cur = (await s.get(m.id, { type: "json" })) || { tickers: [], alerts: true };
  let email = "";
  if (m.kind === "sub") email = ((await getRecord(m.id)) || {}).email || "";
  else email = env("QM_OWNER_EMAIL");
  if (req.method === "GET") return json({ tickers: cur.tickers || [], alerts: cur.alerts !== false, email: !!email, updated: cur.updated || null });
  const body = await readBody(req);
  const next = {
    tickers: body.tickers !== undefined ? cleanList(body.tickers) : cur.tickers || [],
    alerts: body.alerts !== undefined ? !!body.alerts : cur.alerts !== false,
    updated: new Date().toISOString(),
  };
  await s.setJSON(m.id, next);
  return json({ ok: true, tickers: next.tickers, alerts: next.alerts, email: !!email });
}

export default async (req, context) => {
  const path = new URL(req.url).pathname.replace(/\/+$/, "");
  const route = path.slice(path.lastIndexOf("/") + 1);
  try {
    if (route === "login" && req.method === "POST") return await login(req, context);
    if (route === "logout") return redirect("/members/?login=out", clearCookie());
    if (route === "refresh") return await refresh(req);
    if (route === "magic") return await magic(req);
    if (route === "link" && req.method === "POST") return await sendLink(req, context);
    const m = member(req);
    if (route === "me") {
      if (m.ok && m.kind === "sub") return json({ member: true, kind: "sub" });
      if (m.ok) return json({ member: true, kind: m.kind });
      return json({ member: false, renew: !!m.expired });
    }
    if (route === "list") {
      if (!m.ok) return json({ error: "Sign in as a member first." }, 401);
      if (req.method === "GET" || req.method === "PUT" || req.method === "POST") return await list(req, m);
    }
    return json({ error: "Not found" }, 404);
  } catch (e) {
    console.error("member", route, e && e.message);
    return json({ error: "Something went wrong. Please try again." }, 500);
  }
};

export const config = { path: ["/api/member/*"] };
