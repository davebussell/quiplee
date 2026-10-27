/* api.mjs: Be The Puck's public read API for AI tools and anyone else (JSON, GET only, CORS open).
 * Described in /openapi.json (for ChatGPT Actions and others) and on /developers/; the same answers as the MCP
 * server (mcp.mjs), from netlify/lib/agentdata.mjs.
 *
 *   GET /api/v1/                      what's here
 *   GET /api/v1/stock/{ticker}        the standard signal, score, plays in and the read     (free sample + members)
 *       ?w=plays40.offhigh30.trend30&buy=60&sell=40&plays=top1   members: scored with these weights (signal.mjs)
 *   GET /api/v1/search?q=             public names by ticker or name                         (free sample + members)
 *   GET /api/v1/screen?signal=buy|hold|sell&market=us|ca|crypto|fund&group=&min_plays=0-100&sort=score|plays|earnings&limit=1-50
 *   GET /api/v1/plays[?family=]       every play: family, the people behind it, calls right  (members)
 *   GET /api/v1/plays/{slug}          one play in full                                       (members)
 *   GET /api/v1/market                the market guard on the S&P 500 and the TSX, and the Buy/Hold/Sell count (members)
 *
 * Members send `Authorization: Bearer <key>` (a key from the account page; netlify/lib/agentkeys.mjs); a key
 * that isn't valid gets 401. Without a key: the free sample, 30 calls a day from one address. Every answer,
 * errors included, carries the disclaimer; free answers end with how to get the full data.
 */
import * as A from "../lib/agentdata.mjs";
import { tierFor, overDaily, limitWords, FREE_UNTIL_LABEL, KEY_PER_DAY, FREE_PER_DAY } from "../lib/agentkeys.mjs";

const CORS = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS", "access-control-allow-headers": "authorization, content-type",
  "access-control-max-age": "86400" };

function send(ans, extra = {}) {
  let { status, body } = ans;
  // never name a company the site never names, whatever was asked (the answers don't echo input; this is the backstop)
  if (A.bannedHit(JSON.stringify(body))) ({ status, body } = A.errorAnswer(404, A.NOT_COVERED, body.tier === "member" ? "member" : "free"));
  const ok = status < 300;
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8",
    "cache-control": ok ? "private, max-age=300" : "no-store", vary: "authorization", ...CORS, ...extra } });
}

function about(tier) {
  const ep = (path, what, who) => ({ path, what, tier: who });
  const text = "Be The Puck read API, version 1: " + A.SITE + "/openapi.json describes it and " + A.DEV_URL + " explains how to connect.";
  return A.answer(200, {
    name: "Be The Puck read API", version: "1",
    about: "Facts from 100 published trading plays and Be The Puck's signal on every covered stock, fund, index and coin, rebuilt after each U.S. close.",
    docs: A.DEV_URL, openapi: A.SITE + "/openapi.json", mcp: A.SITE + "/mcp", llms: A.SITE + "/llms.txt",
    tiers: { free: `No key: stock and search, ${FREE_PER_DAY} calls a day from one address.`,
      member: `A personal key from your account page (Authorization: Bearer <key>): everything, ${KEY_PER_DAY.toLocaleString("en-US")} calls a day.` },
    endpoints: [ep("/api/v1/stock/{ticker}", "The standard signal, score, plays in and the read on one name", "free"),
      ep("/api/v1/search?q=", "Covered names by ticker or company name", "free"),
      ep("/api/v1/screen", "Filter and sort every public name by signal, market, group and plays in", "member"),
      ep("/api/v1/plays", "Every play, its family, the people behind it and how often it has been right", "member"),
      ep("/api/v1/plays/{slug}", "One play in full", "member"),
      ep("/api/v1/market", "The market guard on the S&P 500 and the TSX, and the Buy/Hold/Sell count", "member")],
    stance: A.STANCE,
  }, text, tier);
}

export default async (req, context) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const url = new URL(req.url);
  const parts = url.pathname.replace(/^\/api\/v1\/?/, "").replace(/\/+$/, "").split("/").filter(Boolean).map((x) => {
    try { return decodeURIComponent(x); } catch (e) { return ""; }
  });
  if (req.method !== "GET" && req.method !== "HEAD") return send(A.errorAnswer(405, "This API is read-only: use GET.", "free"), { allow: "GET, OPTIONS" });
  const route = parts[0] || "";
  const known = { "": 0, stock: 1, search: 1, screen: 1, plays: 1, market: 1 };
  if (!(route in known) || (route === "stock" && parts.length !== 2) || (route === "plays" && parts.length > 2) ||
      (["search", "screen", "market"].includes(route) && parts.length > 1)) {
    return send(A.errorAnswer(404, "No such endpoint. See " + A.SITE + "/api/v1/ or " + A.SITE + "/openapi.json.", "free"));
  }
  const t = await tierFor(req, context);
  if (t.tier === "bad") return send(A.errorAnswer(401, t.note, "free", { code: "bad_key" }), { "www-authenticate": 'Bearer realm="bethepuck"' });
  const member = t.tier === "member";
  if (!route) return send(about(t.tier));
  const freeRoute = route === "stock" || route === "search";
  if (!member && !freeRoute) {
    const what = { screen: "The screener", plays: "The plays", market: "Market conditions" }[route];
    const ans = A.membersOnly(what, FREE_UNTIL_LABEL);
    if (t.note) { ans.body.key_note = t.note; ans.body.text = t.note + "\n" + ans.body.text; }
    return send(ans);
  }
  if (await overDaily(t)) return send(A.errorAnswer(429, limitWords(t), t.tier, { code: "rate_limited" }), { "retry-after": "3600" });
  let D;
  try {
    D = await A.load(url.origin, route === "plays" ? ["A"] : route === "market" ? ["R", "P", "S", "A"] : ["R", "P", "S"]);
  } catch (e) {
    console.error("api data", e);
    return send(A.errorAnswer(503, "Be The Puck's data is unavailable for a moment. Try again shortly.", t.tier));
  }
  const q = Object.fromEntries(url.searchParams);
  let ans;
  if (route === "stock") ans = A.stock(D, parts[1], { member, weights: q });
  else if (route === "search") ans = A.search(D, q.q, { limit: q.limit, member });
  else if (route === "screen") ans = A.screen(D, q);
  else if (route === "plays") ans = parts[1] ? A.explainPlay(D, parts[1]) : A.listPlays(D, { family: q.family });
  else ans = A.market(D);
  if (t.note) { ans.body.key_note = t.note; ans.body.text = t.note + "\n" + ans.body.text; }
  return send(ans);
};

export const config = { path: ["/api/v1", "/api/v1/*"] };
