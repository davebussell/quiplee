// Local stand-in for bethepuck.com: serves a preview folder (tools/dev_render.py) and fakes the
// account API for a signed-in test account, so signed-in features can be tested without the live site.
//   node tools/dev_serve.mjs .cache/prev 8792
// Like netlify.toml, a stock x play address with no page forwards to the stock page's row.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.argv[2] || ".cache/prev"), PORT = +process.argv[3] || 8792;
const LOG = path.join(ROOT, "..", "api.log");
let ACCT = {
  signed_in: true, name: "tester", created: "2026-10-01T00:00:00Z", email: "tester@example.test", email_ok: true,
  follow: ["MU", "MSTR", "NVDA", "SHOP.TO", "BTC-USD"], alerts: { on: true, level: "light" }, rules: null, plays: null, signal: null,
  member: { active: true, kind: "free" }, free_until: "January 1, 2027", mail_on: false, last_sent: null,
};
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };
const json = (res, code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };

http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname.startsWith("/api/account/")) {
    const route = url.pathname.slice(13);
    if (route === "me") return json(res, 200, ACCT);
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const b = body ? JSON.parse(body) : {};
      if (route === "plays") { if ("plays" in b) ACCT.plays = b.plays; if ("signal" in b) ACCT.signal = b.signal; }
      if (route === "alerts") ACCT.alerts = { ...ACCT.alerts, ...b };
      fs.appendFileSync(LOG, route + " " + body + "\n");
      json(res, 200, { ok: true, plays: ACCT.plays, signal: ACCT.signal, follow: ACCT.follow, alerts: ACCT.alerts });
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
