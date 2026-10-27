// Local stand-in for bethepuck.com: serves a preview folder (tools/dev_render.py) and fakes the
// account API for a signed-in test account, so signed-in features can be tested without the live site.
//   node tools/dev_serve.mjs .cache/prev 8792
// Like netlify.toml, a stock x play address with no page forwards to the stock page's row.
// The AI-tools API (/api/v1/*) and MCP server (/mcp) run for real, on an in-memory Blobs store (tools/stubs/), reading
// this folder's data; an API key made on the account page here works with them (free until FREE_UNTIL, like the site).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { register } from "node:module";

register("./stubs/hooks.mjs", import.meta.url);
const agentApi = (await import("../netlify/functions/api.mjs")).default;
const agentMcp = (await import("../netlify/functions/mcp.mjs")).default;
const KEYS = await import("../netlify/lib/agentkeys.mjs");
const { getStore } = await import("@netlify/blobs");

const ROOT = path.resolve(process.argv[2] || ".cache/prev"), PORT = +process.argv[3] || 8792;
const LOG = path.join(ROOT, "..", "api.log");
let ACCT = {
  signed_in: true, name: "tester", created: "2026-10-01T00:00:00Z", email: "tester@example.test", email_ok: true,
  follow: ["MU", "MSTR", "NVDA", "SHOP.TO", "BTC-USD"], alerts: { on: true, level: "light" }, rules: null, plays: null, signal: null,
  member: { active: true, kind: "free" }, free_until: "January 1, 2027", mail_on: false, last_sent: null,
};
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };
const VALID = /^\^?[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,2})?(?:[.-][A-Z0-9]{1,4})?$/;
const covered = () => { try { return JSON.parse(fs.readFileSync(path.join(ROOT, "data", "reads.json"), "utf8")).t; } catch (e) { return null; } };
const json = (res, code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };

/** Run a Netlify Function (a (Request, context) => Response handler) for a Node request. */
async function runFunction(fn, req, res) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = chunks.length && !["GET", "HEAD"].includes(req.method) ? Buffer.concat(chunks) : undefined;
  const headers = Object.fromEntries(Object.entries(req.headers).filter(([, v]) => typeof v === "string"));
  const out = await fn(new Request(`http://localhost:${PORT}${req.url}`, { method: req.method, headers, body }), { ip: req.socket.remoteAddress || "127.0.0.1" });
  res.writeHead(out.status, Object.fromEntries(out.headers));
  res.end(Buffer.from(await out.arrayBuffer()));
}
/** The fake account's API key, kept in the in-memory store the API reads (account.mjs apikey, agentkeys.mjs). */
async function fakeKey(action) {
  const s = getStore({ name: "paper" });
  const old = ACCT._keyHash;
  if (old) await s.delete("k/" + old);
  ACCT._keyHash = null;
  ACCT.apikey = null;
  if (action !== "create") return { ok: true, apikey: null };
  const key = KEYS.newKey(), h = KEYS.keyHash(key), at = new Date().toISOString();
  ACCT._keyHash = h;
  ACCT.apikey = { pre: KEYS.keyPrefix(key), at };
  await s.setJSON("k/" + h, { u: "tester", at });
  await s.setJSON("u/tester", { name: "tester", v: 1, email: ACCT.email, email_ok: true, created: ACCT.created, apikey: { h, pre: ACCT.apikey.pre, at } });
  return { ok: true, key, mcp_url: `http://localhost:${PORT}/mcp/k/${key}`, apikey: ACCT.apikey };
}

http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname === "/api/v1" || url.pathname.startsWith("/api/v1/")) return void runFunction(agentApi, req, res).catch((e) => json(res, 500, { error: String(e) }));
  if (url.pathname === "/mcp" || url.pathname.startsWith("/mcp/k/")) return void runFunction(agentMcp, req, res).catch((e) => json(res, 500, { error: String(e) }));
  if (url.pathname.startsWith("/api/account/")) {
    const route = url.pathname.slice(13);
    if (route === "me") {                   // names asked for that are covered now join the list (account.mjs promote)
      const cov = covered();
      if (cov && (ACCT.asked || []).some((x) => cov[x.s])) {
        ACCT.follow = [...new Set((ACCT.follow || []).concat(ACCT.asked.filter((x) => cov[x.s]).map((x) => x.s)))].slice(0, 100);
        ACCT.asked = ACCT.asked.filter((x) => !cov[x.s]);
      }
      const { _keyHash, ...shown } = ACCT;
      return json(res, 200, shown);
    }
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const b = body ? JSON.parse(body) : {};
      if (route === "apikey") { fs.appendFileSync(LOG, route + " " + body + "\n"); return void fakeKey(b.action).then((j) => json(res, 200, j)); }
      if (route === "plays") { if ("plays" in b) ACCT.plays = b.plays; if ("signal" in b) ACCT.signal = b.signal; }
      if (route === "alerts") ACCT.alerts = { ...ACCT.alerts, ...b };
      if (route === "follow") {             // as netlify/functions/account.mjs follow(): covered names only (data/reads.json), 100 at most;
        const cov = covered();              // a ticker that isn't covered is "asked" (queued for the nightly run)
        const all = (x) => (Array.isArray(x) ? x : [x]).map((v) => String(v).trim().toUpperCase()).filter(Boolean);
        const up = (x) => all(x).filter((v) => !cov || cov[v]);
        if (b.add && cov) for (const v of all(b.add)) if (!cov[v] && VALID.test(v) && !(ACCT.asked || []).some((y) => y.s === v)) (ACCT.asked = ACCT.asked || []).push({ s: v, at: new Date().toISOString() });
        if (b.remove) { const rm = new Set(all(b.remove)); ACCT.asked = (ACCT.asked || []).filter((y) => !rm.has(y.s)); }
        let list = ACCT.follow || [];
        if (b.tickers !== undefined) list = up(b.tickers);
        if (b.add) list = list.concat(up(b.add));
        if (b.remove) { const rm = new Set((Array.isArray(b.remove) ? b.remove : [b.remove]).map((v) => String(v).toUpperCase())); list = list.filter((x) => !rm.has(x)); }
        list = [...new Set(list)].slice(0, 100);
        const gone = (ACCT.follow || []).filter((x) => !list.includes(x));
        if (b.tickers !== undefined && gone.length >= 3) ACCT.follow_was = { at: new Date().toISOString(), list: ACCT.follow };
        if (b.clear_was) delete ACCT.follow_was;
        ACCT.follow = list;
      }
      fs.appendFileSync(LOG, route + " " + body + "\n");
      json(res, 200, { ok: true, plays: ACCT.plays, signal: ACCT.signal, follow: ACCT.follow, follow_was: ACCT.follow_was || null, asked: ACCT.asked || [], alerts: ACCT.alerts });
    });
    return;
  }
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/.netlify/functions/")) return json(res, 200, {});
  let p = path.join(ROOT, decodeURIComponent(url.pathname));
  if (!p.startsWith(ROOT)) { res.writeHead(403); return res.end("403"); }
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "index.html");
  if (!fs.existsSync(p)) {
    const m = url.pathname.match(/^\/stocks\/([^/]+)\/([^/]+)\/?$/);
    if (m && !m[2].includes(".")) { res.writeHead(301, { location: `/stocks/${m[1]}/?play=${m[2]}` }); return res.end(); }
    res.writeHead(404); return res.end("404");
  }
  res.writeHead(200, { "content-type": TYPES[path.extname(p)] || "application/octet-stream" });
  fs.createReadStream(p).pipe(res);
}).listen(PORT, () => console.log(`Be The Puck preview on http://localhost:${PORT} from ${ROOT}`));
