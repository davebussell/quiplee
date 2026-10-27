// Tests for the AI-tools layer: the read API (netlify/functions/api.mjs), the MCP server (netlify/functions/mcp.mjs),
// the API key routes (netlify/functions/account.mjs apikey) and the shared answers (netlify/lib/agentdata.mjs), run
// against a local build's data files with fetch and Netlify Blobs stubbed (tools/stubs/).
//
//   node tools/test_api.mjs [site folder]     default .cache/prev (python tools/dev_render.py render ... writes it)
//   PRIVATE=AMD,COST python tools/dev_render.py render MU,SHOP.TO,SPY && node tools/test_api.mjs
//
// A private (reader-requested) name is needed for its test: render with PRIVATE=... (the first pv name in
// reads.json is used). Exits 1 on any failure.
import { register } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

register("./stubs/hooks.mjs", import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(process.argv[2] || path.join(HERE, "..", ".cache", "prev"));
if (!fs.existsSync(path.join(ROOT, "data", "reads.json"))) {
  console.error(`No data/reads.json under ${ROOT}: render one with tools/dev_render.py, or pass the site folder.`);
  process.exit(2);
}
process.env.QM_SECRET = "test-secret-not-real";
const ORIGIN = "https://bethepuck.test";
let fetches = 0;
globalThis.fetch = async (url) => {
  const u = new URL(String(url));
  if (u.origin !== ORIGIN) throw new Error("unexpected fetch " + u.href);
  fetches++;
  const p = path.join(ROOT, decodeURIComponent(u.pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p)) return new Response("not found", { status: 404 });
  return new Response(fs.readFileSync(p), { status: 200, headers: { "content-type": "application/json" } });
};

const api = (await import("../netlify/functions/api.mjs")).default;
const mcp = (await import("../netlify/functions/mcp.mjs")).default;
const account = (await import("../netlify/functions/account.mjs")).default;
const A = await import("../netlify/lib/agentdata.mjs");
const K = await import("../netlify/lib/agentkeys.mjs");
const L = await import("../netlify/lib/account.mjs");
const SIG = await import("../netlify/lib/signal.mjs");
const { getStore } = await import("@netlify/blobs");
const paper = getStore({ name: "paper" });

const R = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "reads.json"), "utf8"));
const P = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "playset.json"), "utf8"));
const SCR = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "screen.json"), "utf8"));
const PRIV = Object.keys(R.t).find((s) => R.t[s].pv);
const PUBLIC = Object.values(R.t).filter((x) => !x.pv), INDEXES = SCR.t.filter((r) => !R.t[r.sym] && r.sym.startsWith("^"));

let pass = 0, fail = 0;
const ok = (cond, what, extra) => { if (cond) pass++; else { fail++; console.log("FAIL", what, extra === undefined ? "" : JSON.stringify(extra).slice(0, 400)); } };
const section = (s) => console.log("--", s);

let ipn = 0;
const ctx = (ip) => ({ ip: ip || "10.0.0." + (++ipn % 250) + "." + ipn });   // a fresh address per call unless one is given
async function get(p, { key, ip, raw } = {}) {
  const headers = key ? { authorization: "Bearer " + key } : {};
  const res = await api(new Request(ORIGIN + p, { headers }), ctx(ip));
  const text = await res.text();
  return { status: res.status, headers: res.headers, text, body: raw ? null : JSON.parse(text) };
}
async function rpc(msg, { key, url = "/mcp", ip, headers = {} } = {}) {
  const h = { "content-type": "application/json", accept: "application/json, text/event-stream", ...headers };
  if (key) h.authorization = "Bearer " + key;
  const res = await mcp(new Request(ORIGIN + url, { method: "POST", headers: h, body: typeof msg === "string" ? msg : JSON.stringify(msg) }), ctx(ip));
  const text = await res.text();
  return { status: res.status, text, body: text ? JSON.parse(text) : null };
}
const call = (name, args, o) => rpc({ jsonrpc: "2.0", id: 7, method: "tools/call", params: { name, arguments: args } }, o);
const clean = (x) => !A.bannedHit(typeof x === "string" ? x : JSON.stringify(x));
const hasDisc = (x) => (typeof x === "string" ? x : JSON.stringify(x)).includes(A.DISCLAIMER);

// ---------------------------------------------------------------------------------- a signed-in member
const now = new Date().toISOString();
await paper.setJSON("u/tester", { name: "tester", pw: "x", v: 1, created: now, email: "tester@example.test", email_ok: true, follow: ["MU"] });
const cookie = L.ptCookie("tester", 1).split(";")[0];
async function acct(route, body) {
  const res = await account(new Request(ORIGIN + "/api/account/" + route, { method: "POST", body: JSON.stringify(body || {}),
    headers: { "content-type": "application/json", cookie, origin: ORIGIN } }), { ip: "10.9.9.9" });
  return { status: res.status, body: await res.json() };
}

section("REST, free sample");
{
  const r = await get("/api/v1/stock/MU");
  ok(r.status === 200, "MU 200", r.body);
  ok(["Buy", "Hold", "Sell"].includes(r.body.signal) && typeof r.body.score === "number", "MU has a signal and score", r.body);
  ok(r.body.signal === { 1: "Buy", 0: "Hold", "-1": "Sell" }[R.t.MU.S] && r.body.score === R.t.MU.sc, "MU matches reads.json");
  ok(r.body.plays_in.k === R.t.MU.k && r.body.plays_in.of === R.t.MU.of, "MU plays in");
  ok(Array.isArray(r.body.read) && r.body.read.length > 2 && !r.body.read.some((l) => /^Your signal /.test(l)), "free read lines, flip price left out", r.body.read);
  ok(!("factors" in r.body) && !("flip" in r.body), "no factor points or flip price on the free tier");
  ok(r.body.disclaimer === A.DISCLAIMER && r.body.text.includes(A.DISCLAIMER), "disclaimer, exactly");
  ok(r.body.membership === A.UPGRADE && r.body.text.trim().endsWith(A.UPGRADE), "free answer ends with the membership line", r.body.text.slice(-200));
  ok(r.body.url === "https://bethepuck.com/stocks/mu/" && r.body.as_of === R.asof, "page url and as-of");
  ok(/private/.test(r.headers.get("cache-control")) && r.headers.get("access-control-allow-origin") === "*", "cache and CORS headers");
  const w = await get("/api/v1/stock/MU?w=plays100");
  ok(w.status === 200 && w.body.weights === "standard" && w.body.weights_note, "custom weights on the free tier: standard signal with a note", w.body);
  const shop = await get("/api/v1/stock/shop.to");
  ok(shop.status === 200 && shop.body.symbol === "SHOP.TO" && shop.body.market === "ca" && shop.body.currency === "CAD", "SHOP.TO by symbol, Canada", shop.body);
  const name = await get("/api/v1/stock/" + encodeURIComponent(R.t.MU.n));
  ok(name.status === 200 && name.body.symbol === "MU", "lookup by exact company name");
  const spx = await get("/api/v1/stock/" + encodeURIComponent("^GSPC"));
  ok(spx.status === 200 && spx.body.market === "fund" && spx.body.symbol === "^GSPC", "an index (from screen.json)", spx.body);
  const s = await get("/api/v1/search?q=shop");
  ok(s.status === 200 && s.body.results.some((x) => x.symbol === "SHOP.TO"), "search finds Shopify", s.body.results);
  ok(s.body.text.trim().endsWith(A.UPGRADE) && hasDisc(s.body), "search: disclaimer and membership line");
  const s0 = await get("/api/v1/search");
  ok(s0.status === 400 && hasDisc(s0.body), "search without q: 400 with the disclaimer");
  for (const route of ["screen", "plays", "plays/stage-analysis", "market"]) {
    const x = await get("/api/v1/" + route);
    ok(x.status === 403 && x.body.code === "membership_required" && x.body.text.includes(A.UPGRADE) && hasDisc(x.body), "free tier refused: " + route, x.body);
  }
  const ix = await get("/api/v1/");
  ok(ix.status === 200 && ix.body.mcp && ix.body.openapi && hasDisc(ix.body), "API index");
  const nf = await get("/api/v1/nope");
  ok(nf.status === 404 && hasDisc(nf.body), "unknown endpoint 404 with disclaimer");
  const post = await api(new Request(ORIGIN + "/api/v1/stock/MU", { method: "POST", body: "{}" }), ctx());
  const pb = await post.json();
  ok(post.status === 405 && hasDisc(pb), "POST refused with the disclaimer");
  const opt = await api(new Request(ORIGIN + "/api/v1/stock/MU", { method: "OPTIONS" }), ctx());
  ok(opt.status === 204 && opt.headers.get("access-control-allow-headers").includes("authorization"), "CORS preflight");
}

section("private and excluded names");
{
  ok(!!PRIV, "the build has a private (pv) name to test with (render with PRIVATE=AMD,COST)");
  if (PRIV) {
    const r = await get("/api/v1/stock/" + encodeURIComponent(PRIV));
    ok(r.status === 404 && r.body.code === "not_covered", "a private name is not found", r.body);
    ok(!r.text.includes(R.t[PRIV].n), "its name is never in the answer");
    const s = await get("/api/v1/search?q=" + encodeURIComponent(PRIV));
    ok(!s.body.results.some((x) => x.symbol === PRIV), "search never lists it", s.body.results);
    const s2 = await get("/api/v1/search?q=" + encodeURIComponent(R.t[PRIV].n));
    ok(!s2.body.results.some((x) => x.symbol === PRIV), "search by its name never lists it");
  }
  for (const q of ["WSC", "trns", "MGRC", "McGrath RentCorp", "WillScot Holdings", "Transcat", "$WSC"]) {
    const r = await get("/api/v1/stock/" + encodeURIComponent(q));
    ok(r.status === 404 && clean(r.text) && !r.body.suggestions, "excluded, not echoed: " + q, r.text.slice(0, 200));
    const s = await get("/api/v1/search?q=" + encodeURIComponent(q));
    ok(s.status === 200 && s.body.results.length === 0 && clean(s.text), "excluded search, not echoed: " + q);
    const m = await call("get_stock_signal", { ticker: q });
    ok(clean(m.text) && m.body.result.isError, "MCP: excluded, not echoed: " + q);
  }
  const m = await rpc({ jsonrpc: "2.0", id: "WSC", method: "ping" });
  ok(m.status === 400 && clean(m.text), "a JSON-RPC id that names one is refused, not echoed");
}

section("API keys: create, member tier, revoke, lapsed");
let key;
{
  const c = await acct("apikey", { action: "create" });
  ok(c.status === 200 && K.KEY_RX.test(c.body.key) && c.body.mcp_url.endsWith("/mcp/k/" + c.body.key), "a member makes a key", c.body);
  key = c.body.key;
  const stored = await paper.get("u/tester", { type: "json" });
  ok(stored.apikey && stored.apikey.h === K.keyHash(key) && !JSON.stringify(stored).includes(key), "only the key's hash is kept on the account");
  ok((await paper.get("k/" + K.keyHash(key), { type: "json" })).u === "tester", "k/<hash> points at the account");
  const me = await account(new Request(ORIGIN + "/api/account/me", { headers: { cookie } }), { ip: "10.9.9.9" });
  const mj = await me.json();
  ok(mj.apikey && mj.apikey.pre === key.slice(0, 8) && !JSON.stringify(mj).includes(key), "the account page sees the prefix, never the key", mj.apikey);
  const bad = await acct("apikey", { action: "nope" });
  ok(bad.status === 400, "unknown key action refused");

  const r = await get("/api/v1/stock/MU", { key });
  ok(r.status === 200 && r.body.tier === "member" && !r.body.membership, "member tier with the key", r.body.tier);
  ok(Array.isArray(r.body.factors) && r.body.factors.length === P.fx.length, "factor points for members");
  ok(typeof r.body.flip === "string" && /^The standard signal (turns|stays) /i.test(r.body.flip), "flip price for members", r.body.flip);
  const plays = r.body.factors.find((f) => f.key === "plays");
  ok(plays.points === Math.round((100 * R.t.MU.k) / R.t.MU.of), "plays points match plays in", plays);
  const std = await get("/api/v1/stock/MU?w=plays40.offhigh30.trend30&buy=60&sell=40", { key });
  ok(std.body.weights === "standard" && std.body.score === R.t.MU.sc, "the standard weights spelled out = the standard signal");
  const w = await get("/api/v1/stock/MU?w=plays100", { key });
  const guard = !!(P.gd && P.gd.MU);
  ok(w.status === 200 && w.body.weights.w.plays === 100 && w.body.score === Math.round((100 * R.t.MU.k) / R.t.MU.of), "custom weights: plays only", w.body.score);
  ok(w.body.flip === null && w.body.flip_note, "custom weights: no flip price, says why");
  const w2 = await get("/api/v1/stock/MU?w=plays50.eg50.bogus10&buy=70&sell=30", { key });
  ok(w2.body.lines.buy === 70 && w2.body.lines.sell === 30 && (w2.body.ignored || []).includes("bogus10"), "custom lines and an ignored factor", w2.body);
  const direct = SIG.signalFor(P, "MU", null, { w: { plays: 50, eg: 50 }, buy: 70, sell: 30, mv: P.mv });
  ok(w2.body.score === direct.s, "custom score = signal.mjs signalFor", [w2.body.score, direct.s]);
  const w3 = await get("/api/v1/stock/MU?w=wsc.plays50.mcgrath20", { key });
  ok(w3.status === 200 && clean(w3.text) && w3.body.weights.w.plays === 50, "an excluded name in the weights is dropped, never echoed", w3.body.ignored);
  const w4 = await call("get_stock_signal", { ticker: "MU", weights: { plays: 50, WillScot: 10, "<b>x</b>": 5 } }, { key });
  ok(!w4.body.result.isError && clean(w4.text) && !w4.text.includes("<b>"), "MCP weights: odd keys dropped, never echoed");
  const t1 = await get("/api/v1/stock/MU?plays=top1", { key });
  const sel = SIG.resolve(P, { p: "top1" }), c1 = SIG.count(P, "MU", sel);
  ok(t1.body.plays_in.k === c1.k && t1.body.plays_in.of === c1.n, "plays=top1 counts the top play in each family", t1.body.plays_in);

  const sc = await get("/api/v1/screen?limit=500", { key });
  ok(sc.status === 200 && sc.body.shown === 50 && sc.body.rows.length === 50, "screen limit capped at 50", sc.body.shown);
  ok(!sc.body.rows.some((x) => x.symbol === PRIV), "screen never lists a private name");
  const all = await get("/api/v1/screen?limit=50&sort=plays", { key });
  ok(all.body.count === PUBLIC.length + INDEXES.length, "screen covers every public name and index, nothing else", [all.body.count, PUBLIC.length, INDEXES.length]);
  const buy = await get("/api/v1/screen?signal=buy&market=ca&min_plays=60", { key });
  ok(buy.status === 200 && buy.body.rows.every((x) => x.signal === "Buy" && x.market === "ca" && x.plays_in.k / x.plays_in.of >= 0.6), "screen filters", buy.body.rows.slice(0, 3));
  const sc2 = buy.body.rows.map((x) => x.score);
  ok(sc2.every((v, i) => i === 0 || v <= sc2[i - 1]), "screen sorted by score, highest first");
  const sell = await get("/api/v1/screen?signal=sell&limit=10", { key });
  const sc3 = sell.body.rows.map((x) => x.score);
  ok(sell.body.rows.every((x) => x.signal === "Sell") && sc3.every((v, i) => i === 0 || v >= sc3[i - 1]), "sells sorted lowest first");
  // the next earnings report (reads.json ne): on the stock answer, on screen rows, and sort=earnings soonest first
  const neSym = Object.keys(R.t).find((x) => R.t[x].ne && !R.t[x].pv && /^[A-Z]+$/.test(x));
  ok(!!neSym, "the build carries a next earnings report for a public stock");
  if (neSym) {
    const st = await get("/api/v1/stock/" + neSym, { key });
    ok(st.body.next_earnings && st.body.next_earnings.date === R.t[neSym].ne[0] && /Next earnings report: /.test(st.body.text), "stock answer has the next earnings report", st.body.next_earnings);
  }
  const fundAns = await get("/api/v1/stock/SPY", { key });
  ok(fundAns.status === 200 && fundAns.body.next_earnings === null, "a fund has no next earnings report", fundAns.body.next_earnings);
  const er = await get("/api/v1/screen?limit=50&sort=earnings", { key });
  const ds = er.body.rows.map((x) => (x.next_earnings ? x.next_earnings.date : "~"));
  ok(er.status === 200 && er.body.rows.length && ds.every((d, i) => i === 0 || ds[i - 1] <= d) && er.body.rows[0].next_earnings, "sort=earnings: soonest first, none last", ds.slice(0, 8));
  ok(/next earnings/.test(er.body.text), "screen text names the next reports");
  const bg = await get("/api/v1/screen?signal=maybe", { key });
  ok(bg.status === 400 && hasDisc(bg.body), "bad screen filter: 400");
  const grp = await get("/api/v1/screen?group=" + encodeURIComponent(R.t.MU.g), { key });
  ok(grp.body.rows.length > 0 && grp.body.rows.every((x) => x.group === R.t.MU.g), "screen by group");
  const nog = await get("/api/v1/screen?group=Nope", { key });
  ok(nog.body.count === 0 && Array.isArray(nog.body.groups) && nog.body.groups.length > 3, "an unknown group lists the groups");

  const pl = await get("/api/v1/plays", { key });
  ok(pl.status === 200 && pl.body.count >= 50 && pl.body.plays.every((p) => p.people.length && p.family), "plays list", pl.body.count);
  const fam = await get("/api/v1/plays?family=trend", { key });
  ok(fam.body.plays.every((p) => p.family === "trend") && fam.body.count > 3, "plays by family");
  const one = await get("/api/v1/plays/stage-analysis", { key });
  ok(one.status === 200 && one.body.rules.length && one.body.people[0].name && one.body.record.calls > 0, "one play in full", one.body.record);
  const byname = await get("/api/v1/plays/" + encodeURIComponent("Stage Analysis"), { key });
  ok(byname.status === 200 && byname.body.slug === "stage-analysis", "a play by name");
  const mk = await get("/api/v1/market", { key });
  ok(mk.status === 200 && mk.body.guards.length === 2 && mk.body.guards.every((g) => typeof g.guard === "boolean"), "market guard on both indexes", mk.body.guards);
  ok(mk.body.signals.all.buy === PUBLIC.filter((x) => x.S === 1).length + INDEXES.filter((x) => x.sg === 1).length &&
     mk.body.signals.all.names === PUBLIC.length + INDEXES.length, "market counts: public names and indexes only (private names left out)", mk.body.signals.all);

  // a member's daily limit
  const rl = "rl/agentkey:" + K.keyHash(key).slice(0, 32);
  await paper.setJSON(rl, { n: K.KEY_PER_DAY, t: Math.floor(Date.now() / 1000) });
  const lim = await get("/api/v1/stock/MU", { key });
  ok(lim.status === 429 && lim.body.code === "rate_limited" && hasDisc(lim.body), "member key over its daily limit: 429", lim.body);
  await paper.delete(rl);

  // the secret MCP URL
  const sm = await call("screen_stocks", { signal: "buy", limit: 3 }, { url: "/mcp/k/" + key });
  ok(sm.status === 200 && !sm.body.result.isError && sm.body.result.structuredContent.rows.length <= 3, "secret MCP URL: member tools", sm.body.result);
  const hm = await call("market_conditions", {}, { key });
  ok(!hm.body.result.isError && hasDisc(hm.body.result.content[0].text), "MCP with the header: member tools");

  // lapsed: after the free months, with no paid membership
  const realNow = Date.now;
  Date.now = () => Date.UTC(2027, 1, 1);
  const lp = await get("/api/v1/stock/MU", { key });
  ok(lp.status === 200 && lp.body.tier === "free" && lp.body.key_note === K.LAPSED && !lp.body.factors, "lapsed member: free tier with a note", lp.body.key_note);
  const lps = await get("/api/v1/screen", { key });
  ok(lps.status === 403 && lps.body.key_note === K.LAPSED, "lapsed member: member endpoints refused");
  const lpm = await call("screen_stocks", {}, { key });
  ok(lpm.body.result.isError && lpm.body.result.content[0].text.includes(K.LAPSED), "lapsed member over MCP: refused with the note");
  const lpc = await acct("apikey", { action: "create" });
  ok(lpc.status === 403, "a lapsed member can't make a key");
  Date.now = realNow;

  // revoke
  const rv = await acct("apikey", { action: "revoke" });
  ok(rv.status === 200 && rv.body.apikey === null, "revoke");
  ok(!(await paper.get("k/" + K.keyHash(key), { type: "json" })), "k/<hash> deleted on revoke");
  const rk = await get("/api/v1/stock/MU", { key });
  ok(rk.status === 401 && rk.body.code === "bad_key" && hasDisc(rk.body), "a revoked key: 401", rk.body);
  const rm = await call("get_stock_signal", { ticker: "MU" }, { key });
  ok(!rm.body.result.isError && rm.body.result.content[0].text.includes(K.BAD_KEY) && rm.body.result.structuredContent.tier === "free", "a revoked key over MCP: free sample with a note");
  const ru = await call("screen_stocks", {}, { url: "/mcp/k/" + key });
  ok(ru.body.result.isError && ru.body.result.content[0].text.includes(A.UPGRADE), "a revoked secret URL: member tools refused");
  const junk = await get("/api/v1/stock/MU", { key: "not-a-key" });
  ok(junk.status === 401, "a malformed key: 401");
  // replace: a new key retires the old one
  const k1 = (await acct("apikey", { action: "create" })).body.key, k2 = (await acct("apikey", { action: "create" })).body.key;
  ok((await get("/api/v1/stock/MU", { key: k1 })).status === 401 && (await get("/api/v1/stock/MU", { key: k2 })).body.tier === "member", "a new key replaces the old one");
  key = k2;
}

section("rate limit, free sample");
{
  const ip = "192.0.2.77";
  let last;
  for (let i = 0; i < K.FREE_PER_DAY; i++) last = await get("/api/v1/stock/MU", { ip });
  ok(last.status === 200, "30 free calls a day", last.status);
  const over = await get("/api/v1/stock/MU", { ip });
  ok(over.status === 429 && over.headers.get("retry-after") && hasDisc(over.body) && over.body.text.includes("membership key"), "the 31st: 429", over.body);
  const m = await call("get_stock_signal", { ticker: "MU" }, { ip });
  ok(m.body.result.isError && /free sample is 30 calls/.test(m.body.result.content[0].text), "MCP shares the same free count");
  const mem = await get("/api/v1/stock/MU", { ip, key });
  ok(mem.status === 200 && mem.body.tier === "member", "a member key from the same address is fine");
}

section("MCP protocol");
{
  for (const v of ["2025-06-18", "2025-03-26"]) {
    const r = await rpc({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: v, capabilities: {}, clientInfo: { name: "t", version: "0" } } });
    ok(r.status === 200 && r.body.result.protocolVersion === v && r.body.result.capabilities.tools, "initialize negotiates " + v, r.body);
    ok(r.body.result.serverInfo.name === "bethepuck" && r.body.result.instructions.includes(A.DISCLAIMER) && clean(r.body), "initialize: server info, instructions, disclaimer");
  }
  const fut = await rpc({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2099-01-01" } });
  ok(fut.body.result.protocolVersion === "2025-06-18", "an unknown version gets the latest supported");
  const n = await rpc({ jsonrpc: "2.0", method: "notifications/initialized" });
  ok(n.status === 202 && n.text === "", "notifications/initialized: 202, no body");
  const p = await rpc({ jsonrpc: "2.0", id: 2, method: "ping" }, { headers: { "mcp-protocol-version": "2025-06-18" } });
  ok(p.status === 200 && p.body.id === 2 && p.body.result, "ping");
  const bv = await rpc({ jsonrpc: "2.0", id: 2, method: "ping" }, { headers: { "mcp-protocol-version": "1999-01-01" } });
  ok(bv.status === 400, "unsupported MCP-Protocol-Version header: 400");
  const tl = await rpc({ jsonrpc: "2.0", id: 3, method: "tools/list" });
  const names = tl.body.result.tools.map((t) => t.name).sort();
  ok(JSON.stringify(names) === JSON.stringify(["explain_play", "get_stock_signal", "list_plays", "market_conditions", "screen_stocks", "search_stocks"]), "tools/list: six tools", names);
  ok(tl.body.result.tools.every((t) => t.inputSchema && t.inputSchema.type === "object" && t.description.length > 60 && t.annotations.readOnlyHint), "tool schemas, descriptions, read-only");
  ok(tl.body.result.tools.find((t) => t.name === "screen_stocks").description.includes("membership key") &&
     !tl.body.result.tools.find((t) => t.name === "get_stock_signal").description.includes("membership key"), "free tier: member tools say they need a key");
  const tlm = await rpc({ jsonrpc: "2.0", id: 3, method: "tools/list" }, { key });
  ok(!tlm.body.result.tools.some((t) => t.description.includes("membership key")), "member tier: no key notes");
  ok(clean(tl.body) && clean(tlm.body), "tools/list names no excluded company");
  const g = await call("get_stock_signal", { ticker: "MU" });
  const res = g.body.result, txt = res.content[0].text;
  ok(res.content[0].type === "text" && !res.isError && res.structuredContent.symbol === "MU", "tools/call get_stock_signal", res.structuredContent && res.structuredContent.signal);
  ok(txt.includes(A.DISCLAIMER) && txt.trim().endsWith(A.UPGRADE) && !("text" in res.structuredContent), "free tool text: disclaimer, then the membership line");
  const s = await call("search_stocks", { query: "micron", limit: 3 });
  ok(!s.body.result.isError && s.body.result.structuredContent.results[0].symbol === "MU", "tools/call search_stocks");
  const f = await call("screen_stocks", { signal: "buy" });
  ok(f.body.result.isError && f.body.result.content[0].text.includes(A.UPGRADE), "free tier: screen_stocks refused with the membership line");
  const e1 = await call("explain_play", { play: "stage-analysis" }, { key });
  ok(!e1.body.result.isError && e1.body.result.content[0].text.includes("The rule:"), "explain_play (member)");
  const l1 = await call("list_plays", { family: "calendar" }, { key });
  ok(!l1.body.result.isError && l1.body.result.structuredContent.plays.every((x) => x.family === "calendar"), "list_plays (member)");
  const gw = await call("get_stock_signal", { ticker: "MU", weights: { plays: 100 } }, { key });
  ok(gw.body.result.structuredContent.weights.w.plays === 100, "get_stock_signal with weights (member)");
  const miss = await call("get_stock_signal", {});
  ok(miss.body.result.isError && hasDisc(miss.body.result.content[0].text), "missing argument: a tool error");
  const ut = await call("no_such_tool", {});
  ok(ut.body.error && ut.body.error.code === -32602, "unknown tool: -32602");
  const um = await rpc({ jsonrpc: "2.0", id: 9, method: "resources/list" });
  ok(um.body.error && um.body.error.code === -32601 && hasDisc(um.body), "unknown method: -32601 with the disclaimer");
  const pe = await rpc("{not json");
  ok(pe.status === 400 && pe.body.error.code === -32700 && pe.body.id === null, "malformed JSON: -32700");
  const ir = await rpc({ id: 1, method: "ping" });
  ok(ir.status === 400 && ir.body.error.code === -32600, "no jsonrpc: -32600");
  const ir2 = await rpc({ jsonrpc: "2.0", id: null, method: "ping" });
  ok(ir2.status === 400 && ir2.body.error.code === -32600, "id null: -32600");
  const ir3 = await rpc([]);
  ok(ir3.status === 400, "empty batch: 400");
  const b = await rpc([{ jsonrpc: "2.0", id: 1, method: "ping" }, { jsonrpc: "2.0", method: "notifications/initialized" }, { jsonrpc: "2.0", id: 2, method: "tools/list" }]);
  ok(b.status === 200 && Array.isArray(b.body) && b.body.length === 2 && b.body[1].result.tools, "batch: replies for the requests only");
  const gt = await mcp(new Request(ORIGIN + "/mcp", { method: "GET" }), ctx());
  const gtb = await gt.json();
  ok(gt.status === 405 && hasDisc(gtb) && gt.headers.get("allow").includes("POST"), "GET /mcp: 405");
  const del = await mcp(new Request(ORIGIN + "/mcp", { method: "DELETE" }), ctx());
  ok(del.status === 405, "DELETE /mcp: 405");
}

section("same arithmetic as the site");
{
  let bad = 0, n = 0;
  for (const [sym, x] of Object.entries(R.t)) {
    if (x.sc == null) continue;
    n++;
    const r = SIG.signalFor(P, sym, null, null);
    if (r.s !== x.sc || r.sig !== x.S) bad++;
  }
  ok(bad === 0, `signal.mjs scores every name as the build did (${n} names)`, bad);
}

console.log(`\n${pass} passed, ${fail} failed (${fetches} data fetches; data from ${ROOT})`);
process.exit(fail ? 1 : 0);
