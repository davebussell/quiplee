/* account.mjs: one Be The Puck account for the game, My Puck, alerts and member tools.
 *
 *   GET  /api/account/me                       -> {signed_in, name, email, email_ok, follow, alerts, rules, member, ...}
 *   POST /api/account/signup  {email, password, name?, share?}   -> signs in; emails a confirm link
 *   POST /api/account/login   {id (email or username), password}
 *   POST /api/account/logout
 *   POST /api/account/follow  {tickers} | {add} | {remove}       -> the stocks you follow (and get emails about)
 *   POST /api/account/alerts  {on, level: "light"|"all"}
 *   POST /api/account/email   {email, password}                  -> add or change the address (re-confirm)
 *   POST /api/account/resend                                     -> send the confirm link again
 *   GET  /api/account/confirm?t=                                 -> confirms, back to /me/?confirmed=1
 *   POST /api/account/forgot  {id}                               -> emails a reset link (same reply either way)
 *   POST /api/account/reset   {t, password}                      -> new password from that link
 *   POST /api/account/password {old, password}
 *   POST /api/account/delete  {password}
 *   GET|POST /api/account/unsubscribe?t=                         -> stop the emails (POST = one-click from mail apps)
 *
 * Storage and cookies: netlify/lib/account.mjs. Emails go through Resend (RESEND_API_KEY);
 * without it, sign-up still works and the confirm link goes out on the first hourly run
 * after the key is set (alerts-nightly.mjs).
 */
import { env, now, hashId, readBody } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { sendOne } from "../lib/freealerts.mjs";
import {
  store, lc, emailKey, emailTag, hashPassword, nameProblem, passwordProblem, signInCookies, signOutCookies, reply, redirectWith,
  session, updateAccount, freshPortfolio, overLimit, ipKey, crossSite, membership, readLink, NAME_RX, EMAIL_RX, MAX_FOLLOW,
  FREE_UNTIL_LABEL, ptCookie, cleanRules, memberCookie, hasPaidCookie,
} from "../lib/account.mjs";
import { checkPassword } from "../lib/qm.mjs";
import { confirmMsg, resetMsg } from "../lib/accountmail.mjs";

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
    if (s && (!R || R.t[s]) && /^\^?[A-Z0-9.\-=]{1,15}$/.test(s) && !out.includes(s)) out.push(s);
  }
  return out.slice(0, MAX_FOLLOW);
}

/** What the page needs to draw My Puck (never the password hash). */
function view(acct) {
  return {
    signed_in: true, name: acct.name, created: acct.created, email: acct.email || null, email_ok: !!acct.email_ok,
    confirm_sent: acct.confirm_sent || null, follow: acct.follow || [], alerts: acct.alerts || { on: false, level: "all" },
    rules: acct.rules || null, member: membership(acct), free_until: FREE_UNTIL_LABEL, mail_on: mail.configured(),
    last_sent: acct.last_sent || null,
  };
}

/** A free username from an email address: dave.b@x.com -> dave_b, then dave_b2, dave_b3... */
async function nameFromEmail(s, email) {
  let stem = lc(email.split("@")[0]).replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 16);
  if (stem.length < 3) stem = (stem + "player").slice(0, 16);
  if (nameProblem(stem)) stem = "player";
  for (let i = 0; i < 12; i++) {
    const cand = i ? stem + (i < 6 ? i + 1 : Math.floor(Math.random() * 9000 + 1000)) : stem;
    if (!nameProblem(cand) && !(await s.get("u/" + lc(cand), { type: "json" }))) return cand;
  }
  return null;
}

async function sendConfirm(s, u, acct) {
  if (!mail.configured() || !acct.email) return false;
  const r = await sendOne(confirmMsg(u, acct));
  if (r.sent) {
    await updateAccount(s, u, (a) => ({ ...a, confirm_sent: new Date().toISOString() }));
    return true;
  }
  return false;
}

async function signup(req, context, s) {
  const b = await readBody(req);
  const email = String(b.email || "").trim();
  const pw = String(b.password || "");
  if (!EMAIL_RX.test(email) || email.length > 254) return reply({ error: "That email address doesn't look right." }, 400);
  let name = String(b.name || "").trim();
  if (name) { const bad = nameProblem(name); if (bad) return reply({ error: bad }, 400); }
  const pbad = passwordProblem(pw, name, email);
  if (pbad) return reply({ error: pbad }, 400);
  if (await overLimit(s, ipKey(req, context, "signup"), 6, 3600)) return reply({ error: "Too many new accounts from here. Try again in an hour." }, 429);
  if (await s.get(emailKey(email), { type: "json" })) return reply({ error: "That email already has an account. Sign in, or reset your password." }, 409);
  if (!name) { name = await nameFromEmail(s, email); if (!name) return reply({ error: "Pick a username." }, 400); }
  const u = lc(name);
  const t = new Date().toISOString();
  const acct = { name, pw: await hashPassword(pw), v: 1, created: t, email, email_ok: false, email_at: t, confirm_sent: null,
    follow: cleanTickers(b.follow, null).slice(0, 40), rules: null,
    // emails about followed stocks only with a ticked box (CASL: express consent, never pre-checked)
    alerts: { on: b.alerts === true || b.alerts === "on" || b.alerts === "true", level: "all" } };
  const w = await s.setJSON("u/" + u, acct, { onlyIfNew: true });
  if (w.modified === false) return reply({ error: "That username is taken. Try another." }, 409);
  const we = await s.setJSON(emailKey(email), { u }, { onlyIfNew: true });
  if (we.modified === false) { await s.delete("u/" + u).catch(() => {}); return reply({ error: "That email already has an account. Sign in, or reset your password." }, 409); }
  await s.setJSON("p/" + u, freshPortfolio(name, b.share === true || b.share === "on" || b.share === "true"));
  const sent = await sendConfirm(s, u, acct).catch(() => false);
  return reply({ ok: true, name, mail: sent }, 200, signInCookies(req, u, acct));
}

async function findAccount(s, id) {
  id = String(id || "").trim();
  if (id.includes("@")) {
    const rec = EMAIL_RX.test(id) ? await s.get(emailKey(id), { type: "json" }) : null;
    if (!rec) return null;
    const acct = await s.get("u/" + rec.u, { type: "json" });
    return acct && lc(acct.email) === lc(id) ? { u: rec.u, acct } : null;
  }
  const u = lc(id);
  if (!NAME_RX.test(u)) return null;
  const acct = await s.get("u/" + u, { type: "json" });
  return acct ? { u, acct } : null;
}

async function login(req, context, s) {
  const b = await readBody(req);
  const id = String(b.id || b.name || b.email || "").trim();
  const ipk = ipKey(req, context, "plogin");
  const uk = "rl/" + hashId("pu:" + lc(id), env("QM_SECRET"));
  if ((await overLimit(s, ipk, 12, 900, false)) || (await overLimit(s, uk, 10, 900, false))) {
    return reply({ error: "Too many tries. Wait 15 minutes and try again." }, 429);
  }
  const found = await findAccount(s, id);
  const good = found ? await checkPassword(String(b.password || ""), found.acct.pw) : (await hashPassword("x"), false);
  if (!good) {
    await overLimit(s, ipk, 12, 900);
    await overLimit(s, uk, 10, 900);
    return reply({ error: "That email or username and password don't match." }, 401);
  }
  return reply({ ok: true, name: found.acct.name, email: !!found.acct.email }, 200, signInCookies(req, found.u, found.acct));
}

async function follow(req, s, sess) {
  const b = await readBody(req);
  let R = null;
  try { R = await reads(req); } catch (e) { /* keep going without the check */ }
  const out = await updateAccount(s, sess.u, (a) => {
    let list = a.follow || [];
    if (b.tickers !== undefined) list = cleanTickers(b.tickers, R);
    if (b.add) list = cleanTickers(list.concat(Array.isArray(b.add) ? b.add : [b.add]), R);
    if (b.remove) { const rm = new Set((Array.isArray(b.remove) ? b.remove : [b.remove]).map((x) => String(x).toUpperCase())); list = list.filter((x) => !rm.has(x)); }
    return { ...a, follow: list.slice(0, MAX_FOLLOW) };
  });
  if (out.error) return reply({ error: out.error }, out.status || 400);
  return reply({ ok: true, follow: out.acct.follow });
}

async function alerts(req, s, sess) {
  const b = await readBody(req);
  const out = await updateAccount(s, sess.u, (a) => ({
    ...a, alerts: { on: b.on !== undefined ? !!(b.on === true || b.on === "true" || b.on === "on") : (a.alerts || {}).on !== false,
      level: b.level === "light" ? "light" : b.level === "all" ? "all" : (a.alerts || {}).level || "all" },
  }));
  if (out.error) return reply({ error: out.error }, out.status || 400);
  return reply({ ok: true, alerts: out.acct.alerts });
}

async function rules(req, s, sess) {
  const b = await readBody(req);
  const out = await updateAccount(s, sess.u, (a) => ({ ...a, rules: cleanRules(b.rules) }));
  if (out.error) return reply({ error: out.error }, out.status || 400);
  return reply({ ok: true, rules: out.acct.rules });
}

async function changeEmail(req, s, sess) {
  const b = await readBody(req);
  const email = String(b.email || "").trim();
  if (!EMAIL_RX.test(email) || email.length > 254) return reply({ error: "That email address doesn't look right." }, 400);
  if (!(await checkPassword(String(b.password || ""), sess.acct.pw))) return reply({ error: "Your password doesn't match." }, 401);
  if (sess.acct.email && lc(sess.acct.email) === lc(email)) return reply({ ok: true, email, email_ok: !!sess.acct.email_ok });
  const we = await s.setJSON(emailKey(email), { u: sess.u }, { onlyIfNew: true });
  if (we.modified === false) return reply({ error: "That email is already on another account." }, 409);
  const old = sess.acct.email;
  const out = await updateAccount(s, sess.u, (a) => ({ ...a, email, email_ok: false, email_at: new Date().toISOString(), confirm_sent: null }));
  if (out.error) { await s.delete(emailKey(email)).catch(() => {}); return reply({ error: out.error }, out.status || 400); }
  if (old) await s.delete(emailKey(old)).catch(() => {});
  const sent = await sendConfirm(s, sess.u, out.acct).catch(() => false);
  return reply({ ok: true, email, email_ok: false, mail: sent }, 200, hasPaidCookie(req) ? [] : [memberCookie(sess.u)]);
}

async function resend(req, context, s, sess) {
  if (!sess.acct.email) return reply({ error: "Add an email address first." }, 400);
  if (sess.acct.email_ok) return reply({ ok: true, already: true });
  if (!mail.configured()) return reply({ error: "Emails switch on shortly. Your confirm link will arrive as soon as they do." }, 503);
  if (await overLimit(s, "rl/" + hashId("resend:" + sess.u, env("QM_SECRET")), 3, 3600)) return reply({ error: "We've just sent one. Check your inbox and spam folder." }, 429);
  const sent = await sendConfirm(s, sess.u, sess.acct).catch(() => false);
  return sent ? reply({ ok: true }) : reply({ error: "That didn't send. Try again in a minute." }, 502);
}

async function confirm(url, s) {
  const p = readLink(url.searchParams.get("t"), "ec");
  if (!p) return redirectWith("/me/?confirm=expired");
  let ok = false;
  await updateAccount(s, p.u, (a) => {
    if (!a.email || emailTag(a.email) !== p.e) return { error: "changed" };
    ok = true;
    return { ...a, email_ok: true, email_confirmed: a.email_confirmed || new Date().toISOString() };
  });
  return redirectWith(ok ? "/me/?confirmed=1" : "/me/?confirm=expired");
}

async function forgot(req, context, s) {
  const b = await readBody(req);
  const done = reply({ ok: true, mail: mail.configured() });
  if (await overLimit(s, ipKey(req, context, "forgot"), 6, 3600)) return done;
  const found = await findAccount(s, b.id);
  if (!found || !found.acct.email || !mail.configured()) return done;
  if (await overLimit(s, "rl/" + hashId("forgot:" + found.u, env("QM_SECRET")), 3, 3600)) return done;
  await sendOne(resetMsg(found.u, found.acct)).catch(() => {});
  return done;
}

async function resetPassword(req, s) {
  const b = await readBody(req);
  const p = readLink(b.t, "pr");
  if (!p) return reply({ error: "That reset link has expired. Ask for a new one." }, 400);
  const pw = String(b.password || "");
  let acctOut = null, err = null;
  const out = await updateAccount(s, p.u, async (a) => {
    if ((a.v || 1) !== p.v) { err = "That reset link was already used. Ask for a new one."; return { error: err }; }
    const bad = passwordProblem(pw, a.name, a.email);
    if (bad) { err = bad; return { error: bad }; }
    // a reset link proves the inbox, so the address counts as confirmed too
    acctOut = { ...a, pw: await hashPassword(pw), v: (a.v || 1) + 1, email_ok: true };
    return acctOut;
  });
  if (out.error) return reply({ error: err || out.error }, 400);
  return reply({ ok: true, name: out.acct.name }, 200, signInCookies(req, p.u, out.acct));
}

async function changePassword(req, s, sess) {
  const b = await readBody(req);
  if (!(await checkPassword(String(b.old || ""), sess.acct.pw))) return reply({ error: "Your current password doesn't match." }, 401);
  const pw = String(b.password || "");
  const bad = passwordProblem(pw, sess.acct.name, sess.acct.email);
  if (bad) return reply({ error: bad }, 400);
  const hash = await hashPassword(pw);
  const out = await updateAccount(s, sess.u, (a) => ({ ...a, pw: hash, v: (a.v || 1) + 1 }));
  if (out.error) return reply({ error: out.error }, out.status || 400);
  return reply({ ok: true }, 200, [ptCookie(sess.u, out.acct.v)]);
}

async function remove(req, s, sess) {
  const b = await readBody(req);
  if (!(await checkPassword(String(b.password || ""), sess.acct.pw))) return reply({ error: "That password doesn't match." }, 401);
  await Promise.all(["u/", "p/", "h/", "as/"].map((k) => s.delete(k + sess.u).catch(() => {})));
  if (sess.acct.email) await s.delete(emailKey(sess.acct.email)).catch(() => {});
  return reply({ ok: true }, 200, signOutCookies(req));
}

async function unsubscribe(req, url, s) {
  let t = url.searchParams.get("t");
  // a plain link (which mail scanners open on their own) only shows the page with the button
  if (req.method !== "POST") return redirectWith("/me/?stop=" + encodeURIComponent(t || "") + "#alerts");
  if (!t) t = (await readBody(req)).t;
  const p = readLink(t, "au");
  if (p) await updateAccount(s, p.u, (a) => ({ ...a, alerts: { ...(a.alerts || {}), on: false } })).catch(() => {});
  if (!req.headers.get("origin")) return new Response("Unsubscribed", { status: 200 });
  return reply({ ok: !!p });
}

export default async (req, context) => {
  const url = new URL(req.url);
  const route = url.pathname.replace(/^\/api\/account\/?/, "").replace(/\/$/, "");
  if (!env("QM_SECRET")) return reply({ error: "Accounts aren't set up yet." }, 503);
  let s;
  try { s = store(); } catch (e) { return reply({ error: "Accounts are unavailable right now." }, 503); }
  try {
    if (route === "confirm" && req.method === "GET") return await confirm(url, s);
    if (route === "unsubscribe") return await unsubscribe(req, url, s);
    if (req.method === "GET") {
      if (route === "me") {
        const sess = await session(req, s);
        if (!sess) return reply({ signed_in: false, free_until: FREE_UNTIL_LABEL });
        // a game account signed in before accounts existed gets its member cookie and display name here
        const cookies = req.headers.get("cookie") || "";
        const extra = /(?:^|;\s*)bp_name=/.test(cookies) && /(?:^|;\s*)qm=/.test(cookies) ? [] : signInCookies(req, sess.u, sess.acct).slice(1);
        return reply(view(sess.acct), 200, extra);
      }
      return reply({ error: "not found" }, 404);
    }
    if (req.method !== "POST") return reply({ error: "method" }, 405);
    if (crossSite(req)) return reply({ error: "Cross-site request refused." }, 403);
    if (route === "signup") return await signup(req, context, s);
    if (route === "login") return await login(req, context, s);
    if (route === "logout") return reply({ ok: true }, 200, signOutCookies(req));
    if (route === "forgot") return await forgot(req, context, s);
    if (route === "reset") return await resetPassword(req, s);
    const sess = await session(req, s);
    if (!sess) return reply({ error: "Sign in first.", signed_in: false }, 401);
    if (route === "follow") return await follow(req, s, sess);
    if (route === "alerts") return await alerts(req, s, sess);
    if (route === "rules") return await rules(req, s, sess);
    if (route === "email") return await changeEmail(req, s, sess);
    if (route === "resend") return await resend(req, context, s, sess);
    if (route === "password") return await changePassword(req, s, sess);
    if (route === "delete") return await remove(req, s, sess);
    return reply({ error: "not found" }, 404);
  } catch (e) {
    console.error("account", route, e);
    return reply({ error: "Something went wrong. Try again." }, 500);
  }
};

export const config = { path: "/api/account/*" };
