/* mcp.mjs: Be The Puck as a remote MCP server, so Claude, ChatGPT and other assistants can read the signal.
 *
 *   https://bethepuck.com/mcp            the free sample (get_stock_signal, search_stocks; 30 calls a day per address),
 *                                        or every tool with `Authorization: Bearer <key>`
 *   https://bethepuck.com/mcp/k/<key>    the same for a member whose client can't set headers (claude.ai custom connectors)
 *
 * Streamable HTTP, stateless: each POST carries one JSON-RPC 2.0 message (or a batch) and gets plain
 * application/json back (no SSE, no session id). initialize (2025-06-18, 2025-03-26 or 2024-11-05),
 * notifications/initialized, ping, tools/list, tools/call; GET and DELETE get 405. The answers are the read API's
 * (netlify/lib/agentdata.mjs); keys, tiers and limits are netlify/lib/agentkeys.mjs. A key that isn't valid gets
 * the free sample with a note in every answer, not a 401 (which MCP clients take as a cue to start OAuth).
 */
import * as A from "../lib/agentdata.mjs";
import { tierFor, overDaily, limitWords, FREE_UNTIL_LABEL, FREE_PER_DAY, KEY_PER_DAY } from "../lib/agentkeys.mjs";

export const VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];
const HEADER_OK = new Set([...VERSIONS, "2025-11-25"]);
const SERVER = { name: "bethepuck", title: "Be The Puck", version: "1.0.0" };
const META = { "bethepuck/disclaimer": A.DISCLAIMER };
const CORS = { "access-control-allow-origin": "*", "access-control-allow-methods": "POST, GET, DELETE, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, accept, mcp-protocol-version, mcp-session-id, last-event-id",
  "access-control-expose-headers": "mcp-session-id, mcp-protocol-version", "access-control-max-age": "86400" };

// ------------------------------------------------------------------ tools
const WEIGHT_PROPS = {
  weights: { type: "object", additionalProperties: { type: "number", minimum: 0, maximum: 100 },
    description: "Members: factor weights 0-100 to score with instead of the standard ones (plays 40, offhigh 30, trend 30). Factors: plays, upside, rating, pe, fpe, peg, ps, pb, dy, eg, rg, pm, roe, de, offhigh, trend, mom, calm." },
  buy_line: { type: "integer", minimum: 50, maximum: 95, description: "Members: the score at or above which the call is Buy (standard 60)." },
  sell_line: { type: "integer", minimum: 5, maximum: 90, description: "Members: the score at or below which the call is Sell (standard 40)." },
  plays: { type: "string", description: "Members: which plays count toward Plays in: all (standard), top1 (the most accurate in each family), top3, half (right more than half the time), or play slugs joined by dots." },
};
const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const TOOLS = [
  { name: "get_stock_signal", api: "stock", title: "Signal on one stock",
    description: "Be The Puck's signal (Buy, Hold or Sell) on one stock, fund, index or coin it covers, from the latest U.S. close: the score out of 100, how many of its 100 published trading plays hold the name, and the plain-English read (trend, distance from the 1-year high, crash exposure, analysts' targets) and the date of its next earnings report, with whether the call is held by the sticky rule or the market guard is on. Members also get the factor points behind the score, the closes at which the call would change, and scoring with their own weights. Facts, not advice.",
    inputSchema: { type: "object", properties: { ticker: { type: "string", description: "Ticker or company name: MU, SHOP.TO (Toronto), BTC-USD, SPY, ^GSPC, Micron." }, ...WEIGHT_PROPS }, required: ["ticker"] } },
  { name: "search_stocks", api: "search", title: "Find a covered name",
    description: "Find the stocks, funds, indexes and coins Be The Puck covers by ticker or company name, with each one's signal and score. Use it when unsure of a ticker or to check coverage.",
    inputSchema: { type: "object", properties: { query: { type: "string", description: "Part of a ticker or company name, e.g. shop, Royal Bank, semiconductor." },
      limit: { type: "integer", minimum: 1, maximum: 25, description: "How many to return (default 10)." } }, required: ["query"] } },
  { name: "screen_stocks", api: "screen", title: "Screen every covered name",
    description: "Filter and sort every public name Be The Puck covers by its signal, market, group and the share of plays that hold it, e.g. Canadian stocks that read Buy with at least 60% of plays in. Returns up to 50 rows with signal, score, plays in, close and next earnings report; sort by earnings for the soonest reports first.",
    inputSchema: { type: "object", properties: {
      signal: { type: "string", enum: ["buy", "hold", "sell"], description: "Only names with this signal." },
      market: { type: "string", enum: ["us", "ca", "crypto", "fund"], description: "us = U.S. stocks, ca = Toronto-listed, crypto = coins, fund = funds and indexes." },
      group: { type: "string", description: "A group as the site names it, e.g. Semiconductors, Big tech, Banks & insurers, Crypto." },
      min_plays: { type: "number", minimum: 0, maximum: 100, description: "Lowest share of plays in, in percent (60 = at least 60% of the plays hold it)." },
      sort: { type: "string", enum: ["score", "plays", "earnings"], description: "score (default; lowest first when signal is sell), plays (share of plays in) or earnings (the next earnings report, soonest first)." },
      limit: { type: "integer", minimum: 1, maximum: 50, description: "Rows to return (default 20, at most 50)." }, ...WEIGHT_PROPS } } },
  { name: "explain_play", api: "play", title: "Explain one play",
    description: "One of Be The Puck's 100 published trading plays in full: what it reads, its exact in and out rules, its timeframe, the people and source behind it, Be The Puck's assumptions, and how often its calls have been right on real stocks since 2005.",
    inputSchema: { type: "object", properties: { play: { type: "string", description: "The play's name or slug, e.g. Stage Analysis, stage-analysis, Mayer Multiple." } }, required: ["play"] } },
  { name: "list_plays", api: "plays", title: "List the plays",
    description: "Every published trading play Be The Puck runs, by family (trend following, breakouts, momentum, mean reversion, volume, patterns, calendar), with the people behind each and how often its calls have been right.",
    inputSchema: { type: "object", properties: { family: { type: "string", enum: ["trend", "breakout", "momentum", "reversion", "volume", "pattern", "calendar"], description: "Only this family." } } } },
  { name: "market_conditions", api: "market", title: "Market conditions",
    description: "The market as Be The Puck reads it at the latest close: whether the market guard is on for the S&P 500 and the TSX (on at 15% or more below the 1-year high, when the price factors stand down), the nine crash gauges' verdict, and how many covered names read Buy, Hold and Sell.",
    inputSchema: { type: "object", properties: {} } },
];
const FREE_API = new Set(["stock", "search"]);
const MEMBER_NOTE = " Needs a Be The Puck membership key; without one it answers with how to get one.";

function toolList(member) {
  return TOOLS.map(({ api, ...t }) => ({ ...t, description: t.description + (!member && !FREE_API.has(api) ? MEMBER_NOTE : ""),
    annotations: { title: t.title, ...RO } }));
}

function instructions(t) {
  const tier = t.tier === "member" ? "This connection uses a membership key: every tool is available." :
    `This connection is the free sample: get_stock_signal and search_stocks, ${FREE_PER_DAY} calls a day. ${A.UPGRADE}`;
  return "Be The Puck runs 100 published trading plays and a factor score on every covered stock, fund, index and coin after each U.S. close, " +
    "and makes one call per name: Buy, Hold or Sell. Report what the tools return as facts with their date; don't turn them into advice for the person. " +
    A.STANCE + " " + tier + (t.note ? " " + t.note : "") + " " + A.DISCLAIMER;
}

// ------------------------------------------------------------------ JSON-RPC
const rpcError = (id, code, message) => ({ jsonrpc: "2.0", id: id === undefined ? null : id, error: { code, message, data: { disclaimer: A.DISCLAIMER } } });
const rpcResult = (id, result) => ({ jsonrpc: "2.0", id, result });
const textResult = (ans, isError, note) => {
  const text = (note ? note + "\n" : "") + ans.body.text;
  const { text: _t, ...structured } = ans.body;
  if (note) structured.key_note = note;
  return { content: [{ type: "text", text }], structuredContent: structured, isError: !!isError, _meta: META };
};

async function callTool(req, t, params) {
  const name = params && typeof params.name === "string" ? params.name : null;
  const tool = TOOLS.find((x) => x.name === name);
  if (!tool) return { error: [-32602, "Unknown tool. tools/list names the six tools."] };
  const args = params.arguments && typeof params.arguments === "object" && !Array.isArray(params.arguments) ? params.arguments : {};
  const member = t.tier === "member";
  if (!member && !FREE_API.has(tool.api)) {
    const what = { screen: "The screener", play: "Explaining a play", plays: "The list of plays", market: "Market conditions" }[tool.api];
    return { result: textResult(A.membersOnly(what, FREE_UNTIL_LABEL), true, t.note) };
  }
  const need = (k) => { const v = args[k]; return typeof v === "string" && v.trim() ? v : null; };
  if (tool.api === "stock" && !need("ticker")) return { result: textResult(A.errorAnswer(400, "Give a ticker or company name in `ticker`.", t.tier), true, t.note) };
  if (tool.api === "search" && !need("query")) return { result: textResult(A.errorAnswer(400, "Give a company name or ticker in `query`.", t.tier), true, t.note) };
  if (tool.api === "play" && !need("play")) return { result: textResult(A.errorAnswer(400, "Give a play's name or slug in `play`.", t.tier), true, t.note) };
  if (await overDaily(t)) return { result: textResult(A.errorAnswer(429, limitWords(t), t.tier), true, t.note) };
  let D;
  try {
    D = await A.load(new URL(req.url).origin, tool.api === "plays" || tool.api === "play" ? ["A"] : tool.api === "market" ? ["R", "P", "S", "A"] : ["R", "P", "S"]);
  } catch (e) {
    console.error("mcp data", e);
    return { result: textResult(A.errorAnswer(503, "Be The Puck's data is unavailable for a moment. Try again shortly.", t.tier), true, t.note) };
  }
  let ans;
  if (tool.api === "stock") ans = A.stock(D, args.ticker, { member, weights: args });
  else if (tool.api === "search") ans = A.search(D, args.query, { limit: args.limit, member });
  else if (tool.api === "screen") ans = A.screen(D, args);
  else if (tool.api === "play") ans = A.explainPlay(D, args.play);
  else if (tool.api === "plays") ans = A.listPlays(D, { family: args.family });
  else ans = A.market(D);
  // the backstop: an answer never names a company the site never names
  if (A.bannedHit(JSON.stringify(ans.body))) ans = A.errorAnswer(404, A.NOT_COVERED, t.tier);
  return { result: textResult(ans, ans.status >= 400, t.note) };
}

async function handle(req, t, msg) {
  if (!msg || typeof msg !== "object" || Array.isArray(msg)) return rpcError(null, -32600, "Invalid Request: send a JSON-RPC 2.0 object.");
  const hasId = "id" in msg;
  const idOk = !hasId || ((typeof msg.id === "string" && !A.bannedHit(msg.id) && msg.id.length <= 200) || Number.isFinite(msg.id));   // MCP: never null
  if (msg.jsonrpc !== "2.0" || !idOk) return rpcError(null, -32600, "Invalid Request: jsonrpc must be \"2.0\" and id a string or number.");
  if (typeof msg.method !== "string") {
    if ("result" in msg || "error" in msg) return null;               // a client's reply to us: nothing to say
    return rpcError(hasId ? msg.id : null, -32600, "Invalid Request: no method.");
  }
  if (!hasId) return null;                                            // a notification (notifications/initialized and the rest)
  const id = msg.id, p = msg.params && typeof msg.params === "object" ? msg.params : {};
  switch (msg.method) {
    case "initialize": {
      const want = typeof p.protocolVersion === "string" ? p.protocolVersion : "";
      return rpcResult(id, { protocolVersion: VERSIONS.includes(want) ? want : VERSIONS[0], capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER, instructions: instructions(t), _meta: META });
    }
    case "ping": return rpcResult(id, { _meta: META });
    case "tools/list": return rpcResult(id, { tools: toolList(t.tier === "member"), _meta: META });
    case "tools/call": {
      const out = await callTool(req, t, p);
      return out.error ? rpcError(id, out.error[0], out.error[1]) : rpcResult(id, out.result);
    }
    default: return rpcError(id, -32601, "Method not found. This server offers initialize, ping, tools/list and tools/call.");
  }
}

const reply = (status, body, extra = {}) => new Response(body == null ? null : JSON.stringify(body),
  { status, headers: { ...(body == null ? {} : { "content-type": "application/json; charset=utf-8" }), "cache-control": "no-store", ...CORS, ...extra } });

export default async (req, context) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (req.method !== "POST") {
    return reply(405, { error: "This MCP server answers JSON-RPC over POST (Streamable HTTP, no event stream). How to connect: " + A.DEV_URL, disclaimer: A.DISCLAIMER },
      { allow: "POST, OPTIONS" });
  }
  const pv = req.headers.get("mcp-protocol-version");
  if (pv && !HEADER_OK.has(pv)) return reply(400, rpcError(null, -32600, "Unsupported MCP-Protocol-Version. Supported: " + VERSIONS.join(", ") + "."));
  const m = /^\/mcp\/k\/([^/]+)\/?$/.exec(new URL(req.url).pathname);
  let body;
  try {
    const raw = await req.text();
    if (raw.length > 100000) return reply(413, rpcError(null, -32600, "Request too large."));
    body = JSON.parse(raw);
  } catch (e) {
    return reply(400, rpcError(null, -32700, "Parse error: the body isn't JSON."));
  }
  const t = await tierFor(req, context, m ? decodeURIComponent(m[1]) : null);
  if (t.tier === "bad") { t.tier = "free"; }                         // a wrong key: the free sample, with t.note in every answer
  if (Array.isArray(body)) {
    if (!body.length) return reply(400, rpcError(null, -32600, "Invalid Request: empty batch."));
    const out = (await Promise.all(body.slice(0, 20).map((x) => handle(req, t, x)))).filter(Boolean);
    return out.length ? reply(200, out) : reply(202, null);
  }
  const out = await handle(req, t, body);
  return out ? reply(out.error && [-32700, -32600].includes(out.error.code) ? 400 : 200, out) : reply(202, null);
};

export const config = { path: ["/mcp", "/mcp/k/*"] };
