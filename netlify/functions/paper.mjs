/* paper.mjs: the paper-trading game (/paper/).
 *
 * Everyone starts with US$100,000 of play money and trades the names Be The Puck
 * covers at Yahoo's latest price (delayed up to 15 minutes; the last close when
 * the market is shut). Toronto-listed names trade in C$ and are converted at the
 * live USD/CAD rate. Long only, no margin, no fees. Accounts are a username and
 * a password (PBKDF2, never stored in the clear); nothing else is asked for.
 *
 *   POST /api/paper/signup    {name, password, share}   -> sets the "pt" cookie
 *   POST /api/paper/login     {name, password}
 *   POST /api/paper/logout
 *   GET  /api/paper/me                                  -> the portfolio, valued live
 *   POST /api/paper/trade     {sym, side, qty}          -> fills at the latest price
 *   POST /api/paper/import    {items: [{sym, qty?}], amount?} -> buy a list at once (real holdings, or an even split)
 *   POST /api/paper/share     {on}                      -> show it on the leaderboard
 *   POST /api/paper/password  {old, password}
 *   POST /api/paper/reset     {confirm: "RESET"}        -> back to $100,000 (once a day)
 *   POST /api/paper/delete    {password}                -> removes the account
 *   GET  /api/paper/quote?sym=                          -> {price, cur, time, open, usd_per}
 *   GET  /api/paper/player?u=                           -> a shared portfolio
 *   GET  /api/paper/board                               -> the leaderboard (built nightly)
 *   Bearer PICKS_STATE_TOKEN (the nightly build):
 *   GET  /api/paper/admin/export                        -> every portfolio's holdings
 *   POST /api/paper/admin/snapshot {date, rows, board}  -> nightly values + leaderboard
 *   POST /api/paper/admin/hide    {u, hidden}           -> moderation: off the board and profile
 *
 * Blobs store "paper": u/<name> account (password hash, token version),
 * p/<name> portfolio, h/<name> nightly values, board, rl/<hash> rate limits.
 * The names that can be traded come from /data/paper.json (built nightly).
 */
import { getStore } from "@netlify/blobs";
import { pbkdf2, randomBytes, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { env, now, DAY, sign, verify, readCookie, json, readBody, hashId, checkPassword } from "../lib/qm.mjs";

const pbkdf2p = promisify(pbkdf2);
const START = 100000;
const COOKIE = "pt";
const COOKIE_DAYS = 180;
const ITER = 310000;
const NAME_RX = /^[A-Za-z0-9_]{3,20}$/;
const RESERVED = new Set(["admin", "administrator", "bethepuck", "puck", "support", "help", "root", "moderator", "mod", "system",
  "staff", "official", "anonymous", "null", "undefined", "me", "api", "paper", "leaders", "player", "dave", "claude"]);
const BLOCKED = ["fuck", "shit", "cunt", "nigg", "fag", "rape", "nazi", "hitler", "whore", "slut", "kike", "spic", "chink", "retard"];
const MAX_TRADES_KEPT = 1000;
const TRADE_BURST = 40;               // trades per 10 minutes per player
const QUOTE_TTL = 15 * 1000;
const UNIVERSE_TTL = 10 * 60 * 1000;

const store = () => getStore({ name: "paper", consistency: "strong" });
const r2 = (x) => Math.round(x * 100) / 100;
const lc = (s) => String(s || "").toLowerCase();

// ------------------------------------------------------------------ helpers
async function hashPassword(pw) {
  const salt = randomBytes(16);
  const h = await pbkdf2p(String(pw).slice(0, 200), salt, ITER, 32, "sha256");
  return `pbkdf2-sha256$${ITER}$${salt.toString("base64url")}$${h.toString("base64url")}`;
}

const cookie = (token, days) => `${COOKIE}=${token}; Path=/; Max-Age=${Math.round(days * DAY)}; HttpOnly; Secure; SameSite=Lax`;
const clearCookie = () => `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
const issue = (u, v) => { const t = now(); return cookie(sign({ k: "pt", u, v, iat: t, exp: t + COOKIE_DAYS * DAY }, env("QM_SECRET")), COOKIE_DAYS); };

function nameProblem(name) {
  if (!NAME_RX.test(name || "")) return "Usernames are 3 to 20 letters, numbers or underscores.";
  const l = lc(name);
  if (RESERVED.has(l) || BLOCKED.some((w) => l.includes(w))) return "That username isn't available. Try another.";
  return null;
}

function ipKey(req, context, what) {
  const ip = (context && context.ip) || req.headers.get("x-nf-client-connection-ip") || "unknown";
  return "rl/" + hashId(what + ":" + ip, env("QM_SECRET"));
}

/** A fixed-window counter: true if this attempt is over the limit. */
async function overLimit(s, key, max, windowSec, bump = true) {
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

/** Same-site check for anything that changes state (cookies are SameSite=Lax as well). */
function crossSite(req) {
  const o = req.headers.get("origin");
  if (!o) return false;
  try { return new URL(o).host !== new URL(req.url).host; } catch (e) { return true; }
}

async function session(req, s) {
  const p = verify(readCookie(req, COOKIE), env("QM_SECRET"));
  if (!p || p.k !== "pt" || !p.u || !(p.exp > now())) return null;
  const acct = await s.get("u/" + p.u, { type: "json" });
  if (!acct || acct.v !== p.v) return null;
  return { u: p.u, acct };
}

function freshPortfolio(name, share, t = new Date().toISOString()) {
  return { name, share: !!share, hidden: false, created: t, start: START, cash: START, pos: {}, trades: [], realized: 0, n_trades: 0, recent: [], resets: 0 };
}

// ------------------------------------------------------------------ universe + quotes
let UNIV = { at: 0, data: null, origin: "" };
async function universe(req) {
  const origin = new URL(req.url).origin;
  if (UNIV.data && UNIV.origin === origin && Date.now() - UNIV.at < UNIVERSE_TTL) return UNIV.data;
  const r = await fetch(origin + "/data/paper.json", { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error("universe " + r.status);
  const data = await r.json();
  UNIV = { at: Date.now(), data, origin };
  return data;
}

const QUOTES = new Map();
const UA = "Mozilla/5.0 (compatible; BeThePuck/1.0; +https://bethepuck.com)";
async function quote(sym, crypto = false) {
  const hit = QUOTES.get(sym);
  if (hit && Date.now() - hit.at < QUOTE_TTL) return hit.q;
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(sym) + "?range=5d&interval=1d";
  const r = await fetch(url, { headers: { "user-agent": UA, accept: "application/json" } });
  if (!r.ok) throw new Error("quote " + r.status);
  const j = await r.json();
  const res = j && j.chart && j.chart.result && j.chart.result[0];
  const m = (res && res.meta) || {};
  const price = Number(m.regularMarketPrice);
  if (!(price > 0)) throw new Error("no price");
  const closes = ((res.indicators && res.indicators.quote && res.indicators.quote[0] && res.indicators.quote[0].close) || []).filter((x) => x != null);
  const t = (m.regularMarketTime || 0) * 1000;
  const per = (m.currentTradingPeriod && m.currentTradingPeriod.regular) || {};
  const nowS = Date.now() / 1000;
  const open = crypto || (per.start && per.end ? nowS >= per.start && nowS < per.end : false);
  // the previous session's close: the second-to-last daily close while today's bar is forming or done
  const lastDay = t ? new Date(t).toISOString().slice(0, 10) : "";
  const prev = closes.length > 1 ? closes[closes.length - 2] : (m.chartPreviousClose || null);
  const q = { price, prev: prev ? Number(prev) : null, cur: String(m.currency || "USD").toUpperCase(), time: t, open, day: lastDay };
  QUOTES.set(sym, { at: Date.now(), q });
  return q;
}

/** US dollars per unit of a currency (USD 1; CAD from the live USD/CAD rate). */
async function usdPer(cur, U) {
  if (cur === "USD") return 1;
  if (cur === "CAD") {
    try {
      const q = await quote("CAD=X");
      return 1 / q.price;
    } catch (e) {
      if (U && U.fx && U.fx.CAD) return 1 / U.fx.CAD;
      throw e;
    }
  }
  throw new Error("currency " + cur);
}

/** Every position valued at the latest price (the last close from paper.json if a quote fails).
 * paper.json names[sym] = [short, name, slug, currency, last close, kind, plays in, plays]. */
async function value(port, U) {
  const syms = Object.keys(port.pos || {});
  const rows = [];
  let fxCad = null;
  try { fxCad = await usdPer("CAD", U); } catch (e) { fxCad = U && U.fx && U.fx.CAD ? 1 / U.fx.CAD : null; }
  const info = (U && U.names) || {};
  const quotes = await Promise.all(syms.map(async (s) => {
    const meta = info[s];
    try { return await quote(s, !!meta && meta[5] === "crypto"); } catch (e) { return null; }
  }));
  let invested = 0, day = 0, dayBase = 0;
  syms.forEach((s, i) => {
    const p = port.pos[s];
    const meta = info[s] || [s, s, null, "USD", null, "stock"];
    const q = quotes[i];
    const cur = (q && q.cur) || meta[3];
    const fx = cur === "CAD" ? fxCad : 1;
    const price = q ? q.price : (typeof meta[4] === "number" ? meta[4] : null);
    const val = price != null && fx ? r2(p.q * price * fx) : null;
    if (val != null) invested += val;
    if (q && q.prev && fx && val != null) { day += p.q * (q.price - q.prev) * fx; dayBase += p.q * q.prev * fx; }
    rows.push({
      sym: s, short: meta[0], name: meta[1], slug: meta[2], cur, q: p.q, cost: r2(p.cost), first: p.first,
      price, fx, value: val, gain: val != null ? r2(val - p.cost) : null, gain_pct: val != null && p.cost ? (val - p.cost) / p.cost : null,
      stale: !q, open: q ? q.open : false, prev: q ? q.prev : null,
    });
  });
  const total = r2(port.cash + invested);
  rows.sort((a, b) => (b.value || 0) - (a.value || 0));
  rows.forEach((r) => { r.weight = total && r.value != null ? r.value / total : null; });
  return { rows, cash: r2(port.cash), invested: r2(invested), total, ret: total / port.start - 1, day: r2(day), day_pct: dayBase ? day / (dayBase + port.cash) : null };
}

/** Read-modify-write a portfolio with an ETag check; fn returns {error} or the new value. */
async function update(s, u, fn) {
  for (let i = 0; i < 4; i++) {
    const got = await s.getWithMetadata("p/" + u, { type: "json" });
    if (!got || !got.data) return { error: "No portfolio found.", status: 404 };
    const out = await fn(got.data);
    if (out.error) return out;
    const w = await s.setJSON("p/" + u, out.port, got.etag ? { onlyIfMatch: got.etag } : {});
    if (w.modified !== false) return out;
  }
  return { error: "Busy, please try again.", status: 409 };
}

function publicView(port, v, extra = {}) {
  return {
    name: port.name, created: port.created, share: !!port.share, start: port.start, ...v, realized: r2(port.realized || 0),
    n_trades: port.n_trades || (port.trades || []).length, ...extra,
  };
}

// ------------------------------------------------------------------ routes
async function signup(req, context, s) {
  const b = await readBody(req);
  const name = String(b.name || "").trim();
  const pw = String(b.password || "");
  const bad = nameProblem(name);
  if (bad) return json({ error: bad }, 400);
  if (pw.length < 8 || pw.length > 200) return json({ error: "Passwords need at least 8 characters." }, 400);
  if (lc(pw) === lc(name)) return json({ error: "Pick a password that isn't your username." }, 400);
  if (await overLimit(s, ipKey(req, context, "signup"), 5, 3600)) return json({ error: "Too many new accounts from here. Try again in an hour." }, 429);
  const u = lc(name);
  const acct = { name, pw: await hashPassword(pw), v: 1, created: new Date().toISOString() };
  const w = await s.setJSON("u/" + u, acct, { onlyIfNew: true });
  if (w.modified === false) return json({ error: "That username is taken. Try another." }, 409);
  await s.setJSON("p/" + u, freshPortfolio(name, b.share === true || b.share === "on" || b.share === "true"));
  return json({ ok: true, name }, 200, issue(u, 1));
}

async function login(req, context, s) {
  const b = await readBody(req);
  const u = lc(String(b.name || "").trim());
  const ipk = ipKey(req, context, "plogin");
  const uk = "rl/" + hashId("pu:" + u, env("QM_SECRET"));
  if ((await overLimit(s, ipk, 12, 900, false)) || (await overLimit(s, uk, 10, 900, false))) {
    return json({ error: "Too many tries. Wait 15 minutes and try again." }, 429);
  }
  const acct = NAME_RX.test(u) ? await s.get("u/" + u, { type: "json" }) : null;
  const good = acct ? await checkPassword(String(b.password || ""), acct.pw) : (await hashPassword("x"), false);
  if (!good) {
    await overLimit(s, ipk, 12, 900);
    await overLimit(s, uk, 10, 900);
    return json({ error: "That username and password don't match." }, 401);
  }
  return json({ ok: true, name: acct.name }, 200, issue(u, acct.v));
}

async function me(req, s, sess) {
  const U = await universe(req).catch(() => null);
  const port = await s.get("p/" + sess.u, { type: "json" });
  if (!port) return json({ error: "No portfolio found." }, 404);
  const v = await value(port, U);
  const hist = (await s.get("h/" + sess.u, { type: "json" })) || [];
  return json(publicView(port, v, { me: true, hidden: !!port.hidden, trades: (port.trades || []).slice(-100).reverse(), history: hist,
    reset_ok: !port.reset_at || Date.now() - Date.parse(port.reset_at) > DAY * 1000 }));
}

async function trade(req, s, sess) {
  const b = await readBody(req);
  const sym = String(b.sym || "").toUpperCase().trim();
  const side = b.side === "sell" ? "sell" : b.side === "buy" ? "buy" : null;
  let qty = Number(b.qty);
  if (!side) return json({ error: "Choose buy or sell." }, 400);
  let U;
  try { U = await universe(req); } catch (e) { return json({ error: "Trading is unavailable right now. Try again in a minute." }, 503); }
  const meta = U.names && U.names[sym];
  if (!meta) return json({ error: "Be The Puck doesn't cover that symbol, so it can't be traded here." }, 400);
  const crypto = meta[5] === "crypto";
  if (!(qty > 0) || !isFinite(qty)) return json({ error: "Enter how many shares." }, 400);
  if (crypto) qty = Math.floor(qty * 1e6) / 1e6;
  else if (!Number.isInteger(qty)) return json({ error: "Stocks and funds trade in whole shares." }, 400);
  if (!(qty > 0) || qty > 1e9) return json({ error: "Enter how many shares." }, 400);
  let q, fx;
  try {
    q = await quote(sym, crypto);
    fx = await usdPer(q.cur, U);
  } catch (e) {
    return json({ error: "No live price for " + meta[0] + " right now, so the order wasn't placed. Try again shortly." }, 503);
  }
  const usd = r2(qty * q.price * fx);
  const at = new Date().toISOString();
  const out = await update(s, sess.u, (port) => {
    const recent = (port.recent || []).filter((t) => Date.now() - t < 600000);
    if (recent.length >= TRADE_BURST) return { error: "That's a lot of trades. Take a breather and try again in a few minutes.", status: 429 };
    const pos = port.pos || {};
    const cur = pos[sym] || { q: 0, cost: 0, first: at };
    let pl = null;
    if (side === "buy") {
      if (usd > port.cash + 0.005) return { error: `Not enough cash: that's US$${usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} and you have US$${r2(port.cash).toLocaleString("en-US", { minimumFractionDigits: 2 })}.`, status: 400 };
      port.cash = r2(port.cash - usd);
      cur.q = crypto ? Math.round((cur.q + qty) * 1e6) / 1e6 : cur.q + qty;
      cur.cost = r2(cur.cost + usd);
      pos[sym] = cur;
    } else {
      if (!cur.q || qty > cur.q + 1e-9) return { error: `You hold ${cur.q || 0} ${meta[0]}.`, status: 400 };
      const basis = cur.q ? cur.cost * (qty / cur.q) : 0;
      pl = r2(usd - basis);
      port.realized = r2((port.realized || 0) + pl);
      port.cash = r2(port.cash + usd);
      cur.q = crypto ? Math.round((cur.q - qty) * 1e6) / 1e6 : cur.q - qty;
      cur.cost = r2(cur.cost - basis);
      if (cur.q <= 1e-9) delete pos[sym]; else pos[sym] = cur;
    }
    port.pos = pos;
    const tr = { t: at, sym, side, q: qty, px: q.price, cur: q.cur, fx: Math.round(fx * 1e6) / 1e6, usd, open: q.open };
    if (pl != null) tr.pl = pl;
    port.trades = (port.trades || []).concat([tr]).slice(-MAX_TRADES_KEPT);
    port.n_trades = (port.n_trades || 0) + 1;
    recent.push(Date.now());
    port.recent = recent;
    return { port, tr };
  });
  if (out.error) return json({ error: out.error }, out.status || 400);
  return json({ ok: true, trade: out.tr, cash: out.port.cash });
}

/** Buy a list of names in one go: the player's real holdings (share counts, scaled to fit the cash)
 * or an even split of an amount. body {items: [{sym, qty?}], amount?} */
async function importHoldings(req, s, sess) {
  const b = await readBody(req);
  let U;
  try { U = await universe(req); } catch (e) { return json({ error: "Trading is unavailable right now. Try again in a minute." }, 503); }
  const seen = new Set(), items = [], skipped = [];
  for (const it of Array.isArray(b.items) ? b.items.slice(0, 60) : []) {
    const sym = String((it && it.sym) || "").toUpperCase().trim();
    if (!sym || seen.has(sym)) continue;
    seen.add(sym);
    if (!U.names[sym]) { skipped.push({ sym, why: "not covered" }); continue; }
    const q = Number(it.qty);
    items.push({ sym, qty: q > 0 && isFinite(q) ? q : null });
  }
  if (!items.length) return json({ error: "None of those are names Be The Puck covers." }, 400);
  if (items.length > 50) return json({ error: "Up to 50 names at a time." }, 400);
  const byCount = items.every((x) => x.qty);
  const quotes = await Promise.all(items.map(async (x) => {
    const crypto = U.names[x.sym][5] === "crypto";
    try { const q = await quote(x.sym, crypto); return { q, fx: await usdPer(q.cur, U), crypto }; } catch (e) { return null; }
  }));
  const at = new Date().toISOString();
  const out = await update(s, sess.u, (port) => {
    const sk = skipped.slice();
    const cash = port.cash;
    const budget = byCount ? cash : Math.min(cash, Number(b.amount) > 0 ? Number(b.amount) : cash);
    const live = items.map((x, i) => ({ ...x, ...(quotes[i] || {}) })).filter((x, i) => {
      if (!quotes[i]) { sk.push({ sym: x.sym, why: "no live price" }); return false; }
      return true;
    });
    if (!live.length) return { error: "No live prices right now, so nothing was bought. Try again shortly.", status: 503 };
    // share counts: scale down to fit the cash; even split: the same dollars in each
    let scale = 1;
    if (byCount) {
      const want = live.reduce((a, x) => a + x.qty * x.q.price * x.fx, 0);
      scale = want > budget ? budget / want : 1;
    }
    const per = budget / live.length;
    const bought = [];
    let spent = 0;
    for (const x of live) {
      const each = x.q.price * x.fx;
      let qty = byCount ? x.qty * scale : per / each;
      qty = x.crypto ? Math.floor(qty * 1e6) / 1e6 : Math.floor(qty + 1e-9);
      const usd = r2(qty * each);
      if (!(qty > 0) || spent + usd > budget + 0.01) { sk.push({ sym: x.sym, why: "too dear for the cash left" }); continue; }
      spent = r2(spent + usd);
      const pos = port.pos[x.sym] || { q: 0, cost: 0, first: at };
      pos.q = x.crypto ? Math.round((pos.q + qty) * 1e6) / 1e6 : pos.q + qty;
      pos.cost = r2(pos.cost + usd);
      port.pos[x.sym] = pos;
      const tr = { t: at, sym: x.sym, side: "buy", q: qty, px: x.q.price, cur: x.q.cur, fx: Math.round(x.fx * 1e6) / 1e6, usd, open: x.q.open, via: "import" };
      port.trades = (port.trades || []).concat([tr]).slice(-MAX_TRADES_KEPT);
      port.n_trades = (port.n_trades || 0) + 1;
      bought.push(tr);
    }
    if (!bought.length) return { error: "Nothing fit in the cash you have.", status: 400 };
    port.cash = r2(port.cash - spent);
    port.recent = (port.recent || []).filter((t) => Date.now() - t < 600000).concat([Date.now()]);
    return { port, bought, scale, sk };
  });
  if (out.error) return json({ error: out.error }, out.status || 400);
  return json({ ok: true, bought: out.bought, skipped: out.sk, scaled: out.scale < 1 ? out.scale : null, cash: out.port.cash });
}

async function setShare(req, s, sess) {
  const b = await readBody(req);
  const on = b.on === true || b.on === "true" || b.on === "on";
  const out = await update(s, sess.u, (port) => { port.share = on; return { port }; });
  if (out.error) return json({ error: out.error }, out.status || 400);
  return json({ ok: true, share: on });
}

async function changePassword(req, s, sess) {
  const b = await readBody(req);
  if (!(await checkPassword(String(b.old || ""), sess.acct.pw))) return json({ error: "Your current password doesn't match." }, 401);
  const pw = String(b.password || "");
  if (pw.length < 8 || pw.length > 200) return json({ error: "Passwords need at least 8 characters." }, 400);
  const acct = { ...sess.acct, pw: await hashPassword(pw), v: (sess.acct.v || 1) + 1 };
  await s.setJSON("u/" + sess.u, acct);
  return json({ ok: true }, 200, issue(sess.u, acct.v));
}

async function reset(req, s, sess) {
  const b = await readBody(req);
  if (b.confirm !== "RESET") return json({ error: "Type RESET to start over." }, 400);
  const out = await update(s, sess.u, (port) => {
    if (port.reset_at && Date.now() - Date.parse(port.reset_at) < DAY * 1000) return { error: "You can start over once a day.", status: 429 };
    const fresh = freshPortfolio(port.name, port.share);
    fresh.hidden = !!port.hidden;
    fresh.resets = (port.resets || 0) + 1;
    fresh.reset_at = fresh.created;
    return { port: fresh };
  });
  if (out.error) return json({ error: out.error }, out.status || 400);
  await s.delete("h/" + sess.u).catch(() => {});
  return json({ ok: true });
}

async function remove(req, s, sess) {
  const b = await readBody(req);
  if (!(await checkPassword(String(b.password || ""), sess.acct.pw))) return json({ error: "That password doesn't match." }, 401);
  await Promise.all(["u/", "p/", "h/"].map((k) => s.delete(k + sess.u).catch(() => {})));
  return json({ ok: true }, 200, clearCookie());
}

async function quoteRoute(req, url) {
  const sym = String(url.searchParams.get("sym") || "").toUpperCase().trim();
  let U;
  try { U = await universe(req); } catch (e) { return json({ error: "Quotes are unavailable right now." }, 503); }
  const meta = U.names && U.names[sym];
  if (!meta) return json({ error: "Not a covered symbol." }, 404);
  try {
    const q = await quote(sym, meta[5] === "crypto");
    const fx = await usdPer(q.cur, U);
    return json({ sym, price: q.price, prev: q.prev, cur: q.cur, time: q.time, open: q.open, usd_per: fx });
  } catch (e) {
    return json({ error: "No live price right now." }, 503);
  }
}

async function player(req, url, s) {
  const u = lc(url.searchParams.get("u"));
  if (!NAME_RX.test(u)) return json({ error: "No such player." }, 404);
  const port = await s.get("p/" + u, { type: "json" });
  if (!port || !port.share || port.hidden) return json({ error: "This portfolio is private." }, 404);
  const U = await universe(req).catch(() => null);
  const v = await value(port, U);
  const hist = (await s.get("h/" + u, { type: "json" })) || [];
  return json(publicView(port, v, { trades: (port.trades || []).slice(-100).reverse(), history: hist }));
}

function bearer(req) {
  const tok = env("PICKS_STATE_TOKEN");
  const got = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!tok || !got) return false;
  const a = Buffer.from(tok), b = Buffer.from(got);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function adminExport(s) {
  const out = [];
  for await (const page of s.list({ prefix: "p/", paginate: true })) {
    const keys = page.blobs.map((b) => b.key);
    for (let i = 0; i < keys.length; i += 25) {
      const got = await Promise.all(keys.slice(i, i + 25).map((k) => s.get(k, { type: "json" }).catch(() => null)));
      got.forEach((p, j) => {
        if (!p) return;
        const pos = {};
        for (const [sym, x] of Object.entries(p.pos || {})) pos[sym] = x.q;
        out.push({ u: keys[i + j].slice(2), name: p.name, share: !!p.share, hidden: !!p.hidden, created: p.created, start: p.start,
          cash: p.cash, pos, n_trades: p.n_trades || 0 });
      });
    }
  }
  return json({ players: out });
}

async function adminSnapshot(req, s) {
  const b = await readBody(req);
  const date = String(b.date || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return json({ error: "date" }, 400);
  const rows = Array.isArray(b.rows) ? b.rows : [];
  let n = 0;
  for (let i = 0; i < rows.length; i += 25) {
    await Promise.all(rows.slice(i, i + 25).map(async ([u, val, bench]) => {
      if (!NAME_RX.test(u || "") || !(val >= 0)) return;
      const h = ((await s.get("h/" + u, { type: "json" }).catch(() => null)) || []).filter((x) => x[0] !== date);
      h.push([date, r2(val), bench == null ? null : Number(bench)]);
      h.sort((a, c) => (a[0] < c[0] ? -1 : 1));
      await s.setJSON("h/" + u, h.slice(-1500));
      n++;
    }));
  }
  if (b.board) await s.setJSON("board", { asof: date, rows: b.board.slice(0, 500), players: b.players || null });
  return json({ ok: true, written: n });
}

async function adminHide(req, s) {
  const b = await readBody(req);
  const u = lc(b.u);
  if (!NAME_RX.test(u)) return json({ error: "u" }, 400);
  const out = await update(s, u, (port) => { port.hidden = b.hidden !== false; return { port }; });
  if (out.error) return json({ error: out.error }, out.status || 400);
  return json({ ok: true, hidden: out.port.hidden });
}

export default async (req, context) => {
  const url = new URL(req.url);
  const route = url.pathname.replace(/^\/api\/paper\/?/, "").replace(/\/$/, "");
  let s;
  try { s = store(); } catch (e) { return json({ error: "The game is unavailable right now." }, 503); }
  if (!env("QM_SECRET")) return json({ error: "The game isn't set up yet." }, 503);
  try {
    if (route.startsWith("admin/")) {
      if (!bearer(req)) return json({ error: "unauthorized" }, 401);
      if (route === "admin/export" && req.method === "GET") return await adminExport(s);
      if (route === "admin/snapshot" && req.method === "POST") return await adminSnapshot(req, s);
      if (route === "admin/hide" && req.method === "POST") return await adminHide(req, s);
      return json({ error: "not found" }, 404);
    }
    if (req.method === "GET") {
      if (route === "quote") return await quoteRoute(req, url);
      if (route === "player") return await player(req, url, s);
      if (route === "board") return json((await s.get("board", { type: "json" })) || { asof: null, rows: [] });
      if (route === "me") {
        const sess = await session(req, s);
        return sess ? await me(req, s, sess) : json({ signed_in: false });
      }
      return json({ error: "not found" }, 404);
    }
    if (req.method !== "POST") return json({ error: "method" }, 405);
    if (crossSite(req)) return json({ error: "Cross-site request refused." }, 403);
    if (route === "signup") return await signup(req, context, s);
    if (route === "login") return await login(req, context, s);
    if (route === "logout") return json({ ok: true }, 200, clearCookie());
    const sess = await session(req, s);
    if (!sess) return json({ error: "Sign in first.", signed_in: false }, 401);
    if (route === "trade") return await trade(req, s, sess);
    if (route === "share") return await setShare(req, s, sess);
    if (route === "import") return await importHoldings(req, s, sess);
    if (route === "password") return await changePassword(req, s, sess);
    if (route === "reset") return await reset(req, s, sess);
    if (route === "delete") return await remove(req, s, sess);
    return json({ error: "not found" }, 404);
  } catch (e) {
    console.error("paper", route, e);
    return json({ error: "Something went wrong. Try again." }, 500);
  }
};

export const config = { path: "/api/paper/*" };
