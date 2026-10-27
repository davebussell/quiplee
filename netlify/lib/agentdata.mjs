/* agentdata.mjs: Be The Puck's answers for AI tools, shared by the public read API (netlify/functions/api.mjs,
 * /api/v1/*) and the MCP server (netlify/functions/mcp.mjs, /mcp). Pure: it reads the site's own public JSON
 * (cached 10 minutes, like account.mjs reads()) and returns plain objects plus a plain-English text for each.
 *
 *   const D = await load(origin, ["R", "P", "S"]);
 *   stock(D, "MU", { member: true })   -> { status, body }   (body.text is the plain-English answer)
 *
 * Rules (CLAUDE.md): facts, never advice; every answer carries DISCLAIMER; the three companies the site never
 * names are treated like any unknown ticker and never echoed (BANNED_RE mirrors tools/qstrat/content.py
 * _BANNED_RE); reader-requested names (reads.json "pv") are private and never returned, listed or searched.
 * Tiers: the free sample answers stock and search without factor points or flip prices; a membership key
 * (netlify/lib/agentkeys.mjs) gets everything.
 */
import { resolve as resolvePlays, count, signalFor, weights as effWeights, SIG_WORD } from "./signal.mjs";

export const SITE = "https://bethepuck.com";
export const DEV_URL = SITE + "/developers/";
export const DISCLAIMER = "This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.";
export const UPGRADE = "The full data (the screener, factor points, plays, market conditions, flip prices and custom weights) needs a Be The Puck membership key: " + DEV_URL;
export const STANCE = "Be The Puck is not a broker or an adviser and never places trades. An assistant can read the signal and draft an order, but nothing is placed until the person approves it in their own broker, and paper trading comes first.";
export const NOT_COVERED = "Be The Puck doesn't cover that name, or it isn't public. Search by company name, or see " + SITE + "/stocks/ for every covered name.";
export const FREE_TOOLS = new Set(["stock", "search"]);

// tools/qstrat/content.py _BANNED_RE: whole words, any case ("transcatheter" is not one)
const BANNED_RE = /\b(?:MGRC|WSC|TRNS|McGrath|WillScot|Transcat)\b/i;
export const bannedHit = (text) => { const m = BANNED_RE.exec(String(text == null ? "" : text)); return m ? m[0] : null; };

// ------------------------------------------------------------------ the site's public JSON
const FILES = { R: "/data/reads.json", P: "/data/playset.json", S: "/data/screen.json", A: "/data/api.json" };
const TTL = 10 * 60 * 1000;
let CACHE = new Map();
export const clearCache = () => { CACHE = new Map(); };

async function file(origin, k) {
  const url = origin + FILES[k];
  const hit = CACHE.get(url);
  if (hit && Date.now() - hit.at < TTL) return hit.data;
  const r = await fetch(url, { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error(FILES[k] + " " + r.status);
  const data = await r.json();
  CACHE.set(url, { at: Date.now(), data });
  return data;
}

/** {R: reads.json, P: playset.json, S: screen.json, A: api.json} for the keys asked. */
export async function load(origin, keys) {
  const D = { origin };
  await Promise.all(keys.map(async (k) => { D[k] = await file(origin, k); }));
  return D;
}

// ------------------------------------------------------------------ words and numbers
export const MARKET_WORD = { us: "U.S.", ca: "Canada", crypto: "Crypto", fund: "Funds & indexes" };
const FUND_GROUPS = new Set(["Market indexes", "Sectors", "Indexes & ETFs"]);
const ALIAS = { SPX: "^GSPC", "S&P500": "^GSPC", "S&P 500": "^GSPC", GSPC: "^GSPC", TSX: "^GSPTSE", GSPTSE: "^GSPTSE", NDX: "^NDX",
  "NASDAQ 100": "^NDX", "NASDAQ-100": "^NDX", DJI: "^DJI", DOW: "^DJI", RUT: "^RUT", "RUSSELL 2000": "^RUT" };
const sigWord = (s) => (s == null ? "No score" : SIG_WORD[s]);
const curCode = (c) => (c === "C$" ? "CAD" : "USD");
const num = (v, d) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const money = (v, cur) => (v == null ? "n/a" : (cur == null ? "$" : cur) + num(v, Math.abs(v) < 1 ? 4 : 2));   // cur "" for an index level
export const pct = (v, d = 1) => (v == null ? "n/a" : (v > 0 ? "+" : v < 0 ? "-" : "") + num(Math.abs(v * 100), d) + "%");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const NE_WORD = { b: "before the open", a: "after the close", d: "during the day" }, NE_ORD = { b: 0, d: 1, a: 2 };
/** The next earnings report (reads.json ne: [New York date, b|a|d|""], from newsevents.next_reports) as the answers carry it. */
export function nextEarnings(ne) {
  if (!Array.isArray(ne) || !/^\d{4}-\d{2}-\d{2}$/.test(ne[0] || "")) return null;
  return { date: ne[0], timing: NE_WORD[ne[1]] || null, source: "Yahoo Finance's earnings calendar; dates can move, and some are estimates until the company confirms them" };
}
const neKey = (ne) => (ne ? ne[0] + ":" + (NE_ORD[ne[1]] == null ? 1 : NE_ORD[ne[1]]) : null);
export const day = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || ""); return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : String(iso || ""); };
const r4 = (v) => (v == null ? null : Math.round(v * 10000) / 10000);
const stockUrl = (u) => `${SITE}/stocks/${u}/`;

function marketOf(t) {
  if (t.g === "Crypto" || /-USD$/.test(t.sym)) return "crypto";
  if (t.sym.startsWith("^") || FUND_GROUPS.has(t.g)) return "fund";
  return t.cur === "C$" ? "ca" : "us";
}
const canadian = (sym) => /\.(TO|V|NE)$/.test(sym);
const benchName = (sym) => (sym === "^GSPC" ? null : sym === "^GSPTSE" ? "the S&P 500" : canadian(sym) ? "the TSX" : "the S&P 500");

// ------------------------------------------------------------------ the public names
const IDX = new WeakMap();
/** Every public name: reads.json without the private (pv) ones, plus the market indexes (screen.json only). */
function index(D) {
  const key = D.R;
  let I = IDX.get(key);
  if (I) return I;
  const rows = new Map((D.S ? D.S.t : []).map((r) => [r.sym, r]));
  const names = [];
  for (const [sym, x] of Object.entries(D.R.t || {})) {
    if (x.pv || bannedHit(sym + " " + x.n + " " + x.s)) continue;
    const row = rows.get(sym);
    const t = { sym, s: x.s, n: x.n, u: x.u, g: x.g, cur: x.cur, p: x.p, d1: x.d1, y1: x.y1, S: x.S, sc: x.sc, k: x.k, of: x.of,
      read: x.read || [], hd: !!x.hd, gd: !!x.gd, ne: Array.isArray(x.ne) ? x.ne : null };
    t.m = row ? row.m : marketOf(t);
    names.push(t);
  }
  for (const r of rows.values()) {               // the indexes have no read in reads.json; the screener row has the rest
    if (D.R.t[r.sym] || !r.sym.startsWith("^") || bannedHit(r.sym + " " + r.n + " " + r.s)) continue;
    const wd = D.P && D.P.wd ? D.P.wd : { buy: 60, sell: 40 };
    const plain = r.sc == null ? null : r.sc >= wd.buy ? 1 : r.sc <= wd.sell ? -1 : 0;
    names.push({ sym: r.sym, s: r.s, n: r.n, u: r.u, g: r.g, cur: r.c || "$", p: r.p, d1: r.d, y1: r.y, S: r.sg, sc: r.sc, k: r.k, of: r.o,
      read: [`${r.k} of the ${r.o} plays hold the ${r.s} right now.`], hd: r.sg != null && plain != null && r.sg !== plain,
      gd: !!(D.P && D.P.gd && D.P.gd[r.sym]), m: "fund" });
  }
  const bySym = new Map(), bySlug = new Map(), byShort = new Map(), byName = new Map();
  const order = { us: 0, ca: 1, crypto: 2, fund: 3 };
  names.sort((a, b) => order[a.m] - order[b.m] || a.sym.localeCompare(b.sym));
  for (const t of names) {
    bySym.set(t.sym.toUpperCase(), t);
    bySlug.set(t.u, t);
    const sh = t.s.toUpperCase();
    if (!byShort.has(sh)) byShort.set(sh, []);
    byShort.get(sh).push(t);
    byName.set(t.n.toLowerCase(), t);
  }
  I = { names, bySym, bySlug, byShort, byName };
  IDX.set(key, I);
  return I;
}

/** One public name for a ticker, slug, short ticker or exact name; null for anything else (never says why). */
export function findName(D, q) {
  q = String(q == null ? "" : q).trim().replace(/^\$/, "");
  if (!q || q.length > 60 || bannedHit(q)) return null;
  const I = index(D), up = q.toUpperCase();
  const sym = ALIAS[up] || up;
  return I.bySym.get(sym) || I.bySym.get("^" + sym) || I.bySlug.get(q.toLowerCase()) || (I.byShort.get(up) || [])[0] ||
    I.byName.get(q.toLowerCase()) || null;
}

// ------------------------------------------------------------------ weights (members)
/** The reader-style weights from API or tool input: w "plays40.offhigh30.trend30" or {plays: 40, ...}, buy, sell, plays. */
export function parseWeights(P, inp) {
  if (!inp) return null;
  let w = inp.w != null ? inp.w : inp.weights;
  const buy = inp.buy != null ? inp.buy : inp.buy_line, sell = inp.sell != null ? inp.sell : inp.sell_line;
  const plays = inp.plays;
  if (w == null && buy == null && sell == null && (plays == null || plays === "" || plays === "all")) return null;
  const known = new Set(P.fx.map((f) => f.k)), ignored = [];
  const skip = (x) => { x = String(x).trim().slice(0, 20); if (/^[A-Za-z0-9_-]+$/.test(x) && !bannedHit(x)) ignored.push(x); };   // never echo anything else
  let obj = null;
  if (typeof w === "string" && w.trim()) {
    obj = {};
    for (const part of w.split(/[.,\s]+/)) {
      const m = /^([a-z]+)(\d+)$/.exec(part.trim());
      if (m && known.has(m[1])) obj[m[1]] = +m[2]; else if (part.trim()) skip(part);
    }
  } else if (w && typeof w === "object" && !Array.isArray(w)) {
    obj = {};
    for (const [k, v] of Object.entries(w).slice(0, 40)) {
      if (known.has(k) && Number(v) >= 0) obj[k] = Number(v); else skip(k);
    }
  }
  const signal = { w: obj || { ...P.wd.w }, buy: buy == null ? P.wd.buy : Number(buy), sell: sell == null ? P.wd.sell : Number(sell), mv: P.mv };
  let choice = null;
  if (typeof plays === "string" && plays && plays !== "all") {
    if (["top1", "top3", "half"].includes(plays)) choice = { p: plays, s: [] };
    else {
      const slugs = new Set(P.plays.map((x) => x.s));
      const s = plays.split(/[.,\s]+/).filter((x) => slugs.has(x));
      choice = s.length ? { p: "custom", s } : null;
    }
  }
  const W = effWeights(P, signal);
  return { signal: { ...W, mv: P.mv }, choice, W, ignored };
}

const wordsFor = (P, w) => {
  const tot = Object.values(w).reduce((a, b) => a + b, 0) || 1;
  const name = Object.fromEntries(P.fx.map((f) => [f.k, f.n]));
  const bits = Object.entries(w).filter(([, v]) => v > 0).map(([k, v]) => `${Math.round((100 * v) / tot)}% ${name[k] || k}`);
  return bits.length < 2 ? bits.join("") : bits.slice(0, -1).join(", ") + " and " + bits[bits.length - 1];
};
const isDefault = (P, W, choice) => !choice && Object.keys(W.w).length === Object.keys(P.wd.w).length &&
  Object.entries(P.wd.w).every(([k, v]) => W.w[k] === v) && W.buy === P.wd.buy && W.sell === P.wd.sell;

function heldWords(sig, s, buy, sell, mid) {
  if (sig === 1) return `Held at Buy: the score of ${s} is under the Buy line of ${buy}, and a Buy holds until the score drops below ${mid}.`;
  if (sig === -1) return `Held at Sell: the score of ${s} is over the Sell line of ${sell}, and a Sell holds until the score rises above ${mid}.`;
  return null;
}
function guardWords(P, t) {
  const b = benchName(t.sym), dd = P && P.gb ? P.gb[t.sym] : null;
  const names = (P ? P.fx.filter((f) => (P.pk || []).includes(f.k)).map((f) => f.n) : ["Off the high", "Trend", "1-year momentum"]);
  const list = names.length > 1 ? names.slice(0, -1).join(", ") + " and " + names[names.length - 1] : names.join("");
  return `Market guard on: ${b || "its market"} is ${dd != null ? Math.round(Math.abs(dd) * 100) + "% " : ""}below its 1-year high, so ${list} stand down and the rest of the weights decide.`;
}

/** Every factor's points and shown value for one name, with the weight each carries in W. */
function factorRows(P, t, W, sel, guard) {
  const x = P.x[t.sym], v = P.v[t.sym];
  if (!x) return [];
  const pk = P.pk || [];
  return P.fx.map((f, i) => {
    let p = x[i], shown = v ? v[i] : null;
    if (f.k === "plays") {
      const c = count(P, t.sym, sel);
      p = c.n ? Math.round((100 * c.k) / c.n) : null;
      shown = c.n ? `${c.k} of ${c.n} plays in` : null;
    }
    const wt = W.w[f.k] || 0;
    const row = { key: f.k, name: f.n, points: p, shown, weight: wt };
    if (wt && guard && pk.includes(f.k)) row.stands_down = true;
    return row;
  });
}

// ------------------------------------------------------------------ answers
const done = (status, body, text, tier) => {
  body.as_of = body.as_of || null;
  body.disclaimer = DISCLAIMER;
  if (tier === "free") body.membership = UPGRADE;
  body.text = text + "\n\n" + DISCLAIMER + (tier === "free" ? "\n" + UPGRADE : "");
  return { status, body };
};
export const answer = done;
export const errorAnswer = (status, message, tier, extra = {}) =>
  done(status, { error: message, ...extra }, message, tier);
/** A member tool asked for without a member key. freeUntil: account.mjs FREE_UNTIL_LABEL (member tools are free until then). */
export const membersOnly = (what, freeUntil) => errorAnswer(403, `${what} is part of the Be The Puck membership, with a personal API key from the account page` +
  (freeUntil ? ` (member tools are free for every account until ${freeUntil}, then $5 a month).` : " ($5 a month)."), "free", { code: "membership_required" });

/** get_stock_signal / GET /api/v1/stock/{ticker} */
export function stock(D, q, { member = false, weights = null } = {}) {
  const tier = member ? "member" : "free";
  const t = findName(D, q);
  if (!t) {
    const sug = bannedHit(q) ? [] : search(D, q, { limit: 5 }).body.results || [];
    const text = NOT_COVERED + (sug.length ? " Close matches: " + sug.map((x) => `${x.ticker} (${x.name})`).join(", ") + "." : "");
    return done(404, { error: text, code: "not_covered", ...(sug.length ? { suggestions: sug } : {}), as_of: D.R.asof }, text, tier);
  }
  const P = D.P;
  const asked = weights ? parseWeights(P, weights) : null;
  const custom = member ? asked : null;
  const useCustom = custom && !isDefault(P, custom.W, custom.choice);
  let S = t.S, sc = t.sc, hd = t.hd, k = t.k, of = t.of;
  const guard = t.gd;
  let W = { w: { ...P.wd.w }, buy: P.wd.buy, sell: P.wd.sell }, sel = resolvePlays(P, null);
  if (useCustom) {
    W = custom.W;
    sel = resolvePlays(P, custom.choice);
    const r = signalFor(P, t.sym, custom.choice, custom.signal, sel);
    S = r.sig; sc = r.s; hd = !!r.hd;
    const c = count(P, t.sym, sel);
    k = c.k; of = c.n;
  }
  const read = (t.read || []).filter((l) => !/^Your signal /.test(l));
  const flipLine = (t.read || []).find((l) => /^Your signal /.test(l));
  const flip = flipLine ? flipLine.replace(/^Your signal /, "The standard signal ") : null;     // "Your signal" is the site's name for it
  const isIndex = t.sym.startsWith("^");
  const body = {
    ticker: t.s, symbol: t.sym, name: t.n, group: t.g, market: t.m, market_name: MARKET_WORD[t.m], currency: isIndex ? null : curCode(t.cur),
    close: t.p, close_date: D.R.asof, change_1d: r4(t.d1), change_1y: r4(t.y1),
    signal: sigWord(S), score: sc,
    weights: useCustom ? { w: W.w, buy: W.buy, sell: W.sell, plays: custom.choice ? (custom.choice.p === "custom" ? custom.choice.s.join(".") : custom.choice.p) : "all" } : "standard",
    weights_words: useCustom ? wordsFor(P, W.w) : D.R.wt || wordsFor(P, P.wd.w),
    lines: { buy: W.buy, sell: W.sell },
    held: !!hd, held_words: hd ? heldWords(S, sc, W.buy, W.sell, P.mid == null ? 50 : P.mid) : null,
    guard: !!guard, guard_words: guard ? guardWords(P, t) : null,
    plays_in: { k, of, words: `${k} of the ${of} ${useCustom && custom.choice ? "chosen " : ""}plays hold ${t.s} right now.` },
    next_earnings: nextEarnings(t.ne),
    read: useCustom && custom.choice ? read.slice(1) : read,     // the first line counts every play
    url: stockUrl(t.u), as_of: D.R.asof, tier,
  };
  if (useCustom && custom.ignored.length) body.ignored = custom.ignored;
  if (!member && asked) body.weights_note = "Scoring with your own weights is for members; this is the standard signal.";
  if (member) {
    body.factors = factorRows(P, t, W, sel, guard);
    body.flip = useCustom ? null : flip;
    if (useCustom) body.flip_note = "Flip prices are worked out for the standard weights only.";
  }
  // the text
  const L = [];
  const moves = [t.d1 != null ? `${pct(t.d1)} on the day` : "", t.y1 != null ? `${pct(t.y1, 0)} over a year` : ""].filter(Boolean).join(", ");
  L.push(`${t.n} (${t.s}${t.sym !== t.s ? ", " + t.sym : ""}) · ${t.g} · ${MARKET_WORD[t.m]} · close ${money(t.p, isIndex ? "" : t.cur)} on ${day(D.R.asof)}` +
    (moves ? ` (${moves})` : "") + ".");
  L.push(`Be The Puck's signal: ${sigWord(S)}` + (sc != null ? `, score ${sc} of 100` : "") + ` (${useCustom ? "custom" : "standard"} weights: ${body.weights_words}; Buy at ${W.buy} or more, Sell at ${W.sell} or less).`);
  if (body.held_words) L.push(body.held_words);
  if (body.guard_words) L.push(body.guard_words);
  if (!body.read.length || (useCustom && custom.choice)) L.push(body.plays_in.words);     // otherwise the read's first line says it
  if (body.read.length) L.push("The read:\n" + body.read.map((l) => "- " + l).join("\n"));
  if (body.next_earnings) L.push(`Next earnings report: ${day(body.next_earnings.date)}${body.next_earnings.timing ? ", " + body.next_earnings.timing : ""} (Yahoo Finance's calendar; dates can move).`);
  if (member && body.factors && body.factors.length) {
    const fmt = (f) => `${f.name} ${f.points == null ? "n/a" : f.points}${f.shown ? " (" + f.shown + ")" : ""}`;
    const on = body.factors.filter((f) => f.weight), off = body.factors.filter((f) => !f.weight && f.points != null);
    L.push("Factor points (0 to 100, higher favours buying): " + on.map((f) => fmt(f) + `, weight ${f.weight}` + (f.stands_down ? ", stands down" : "")).join("; ") + ".");
    if (off.length) L.push("Not weighted: " + off.map(fmt).join("; ") + ".");
  }
  if (member && body.flip) L.push(body.flip);
  if (member && useCustom) L.push(body.flip_note);
  if (body.weights_note) L.push(body.weights_note);
  if (body.ignored) L.push("Ignored (not a factor): " + body.ignored.join(", ") + ". Factors: " + P.fx.map((f) => f.k).join(", ") + ".");
  L.push(`Page: ${body.url}`);
  L.push(`Data as of the ${day(D.R.asof)} close.`);
  return done(200, body, L.join("\n"), tier);
}

/** search_stocks / GET /api/v1/search?q= */
export function search(D, q, { limit = 10, member = false } = {}) {
  const tier = member ? "member" : "free";
  q = String(q == null ? "" : q).trim().replace(/^\$/, "");
  limit = Math.max(1, Math.min(25, Math.round(Number(limit) || 10)));
  if (!q || q.length > 60) return errorAnswer(400, "Give a company name or ticker to search for (up to 60 characters).", tier);
  if (bannedHit(q)) return done(200, { results: [], count: 0, as_of: D.R.asof }, "No covered names match. " + NOT_COVERED, tier);
  const I = index(D), Q = q.toLowerCase(), U = q.toUpperCase();
  const scored = [];
  for (const t of I.names) {
    const n = t.n.toLowerCase(), s = t.s.toUpperCase(), sym = t.sym.toUpperCase();
    let r = null;
    if (sym === U || s === U || t.u === Q || ALIAS[U] === t.sym) r = 0;
    else if (n === Q) r = 1;
    else if (sym.startsWith(U) || s.startsWith(U)) r = 2;
    else if (n.startsWith(Q)) r = 3;
    else if (n.split(/[\s&.,'()-]+/).some((w) => w && w.startsWith(Q))) r = 4;
    else if (Q.length >= 3 && n.includes(Q)) r = 5;
    else if (Q.length >= 3 && t.g.toLowerCase().includes(Q)) r = 6;
    if (r != null) scored.push([r, t]);
  }
  scored.sort((a, b) => a[0] - b[0] || a[1].s.localeCompare(b[1].s));
  const results = scored.slice(0, limit).map(([, t]) => ({ ticker: t.s, symbol: t.sym, name: t.n, group: t.g, market: t.m,
    signal: sigWord(t.S), score: t.sc, held: t.hd, plays_in: { k: t.k, of: t.of }, url: stockUrl(t.u) }));
  const text = results.length
    ? `${scored.length} covered name${scored.length === 1 ? "" : "s"} match${scored.length > results.length ? `; the first ${results.length}` : ""}:\n` +
      results.map((x) => `- ${x.ticker}${x.symbol !== x.ticker ? " (" + x.symbol + ")" : ""}: ${x.name}, ${x.group}, ${MARKET_WORD[x.market]}. Signal ${x.signal}${x.score != null ? " " + x.score : ""}${x.held ? " (held by the sticky rule)" : ""}, ${x.plays_in.k} of ${x.plays_in.of} plays in.`).join("\n") +
      `\nData as of the ${day(D.R.asof)} close.`
    : "No covered names match. " + NOT_COVERED;
  return done(200, { results, count: scored.length, as_of: D.R.asof }, text, tier);
}

const SIGNAL_IN = { buy: 1, hold: 0, sell: -1 };
/** screen_stocks / GET /api/v1/screen (members) */
export function screen(D, p = {}) {
  const P = D.P, I = index(D);
  const sig = p.signal == null || p.signal === "" ? null : String(p.signal).toLowerCase();
  if (sig != null && !(sig in SIGNAL_IN)) return errorAnswer(400, "signal is buy, hold or sell.", "member");
  const mkt = p.market == null || p.market === "" ? null : String(p.market).toLowerCase();
  if (mkt != null && !MARKET_WORD[mkt]) return errorAnswer(400, "market is us, ca, crypto or fund.", "member");
  const minp = p.min_plays == null || p.min_plays === "" ? 0 : Number(p.min_plays);
  if (!(minp >= 0 && minp <= 100)) return errorAnswer(400, "min_plays is a share of plays in, 0 to 100 (60 means at least 60% of the plays hold it).", "member");
  const sort = p.sort == null || p.sort === "" ? "score" : String(p.sort).toLowerCase();
  if (!["score", "plays", "earnings"].includes(sort)) return errorAnswer(400, "sort is score, plays or earnings.", "member");
  const limit = Math.max(1, Math.min(50, Math.round(Number(p.limit) || 20)));
  const grp = p.group == null ? "" : String(p.group).trim().toLowerCase().slice(0, 60);
  const slug = (g) => g.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const custom = parseWeights(P, p);
  const useCustom = custom && !isDefault(P, custom.W, custom.choice);
  const sel = useCustom ? resolvePlays(P, custom.choice) : null;
  let rows = I.names.filter((t) => (!mkt || t.m === mkt) && (!grp || t.g.toLowerCase() === grp || slug(t.g) === slug(grp)));
  rows = rows.map((t) => {
    if (!useCustom) return { t, S: t.S, sc: t.sc, k: t.k, of: t.of };
    const r = signalFor(P, t.sym, custom.choice, custom.signal, sel), c = count(P, t.sym, sel);
    return { t, S: r.sig, sc: r.s, k: c.k, of: c.n };
  }).filter((r) => (sig == null || r.S === SIGNAL_IN[sig]) && (!minp || (r.of && (100 * r.k) / r.of >= minp - 1e-9)));
  const down = sig === "sell" ? 1 : -1, share = (r) => (r.of ? r.k / r.of : 0);
  rows.sort((a, b) => sort === "earnings"          // the next report soonest first; names with none (funds, coins) last
    ? (!a.t.ne) - (!b.t.ne) || (a.t.ne && b.t.ne ? neKey(a.t.ne).localeCompare(neKey(b.t.ne)) : 0) || a.t.s.localeCompare(b.t.s)
    : sort === "plays"
    ? down * (share(a) - share(b)) || a.t.s.localeCompare(b.t.s)
    : (a.sc == null) - (b.sc == null) || down * ((a.sc || 0) - (b.sc || 0)) || down * (share(a) - share(b)) || a.t.s.localeCompare(b.t.s));
  const out = rows.slice(0, limit).map((r) => ({ ticker: r.t.s, symbol: r.t.sym, name: r.t.n, group: r.t.g, market: r.t.m,
    signal: sigWord(r.S), score: r.sc, plays_in: { k: r.k, of: r.of }, close: r.t.p, currency: curCode(r.t.cur),
    change_1d: r4(r.t.d1), change_1y: r4(r.t.y1), next_earnings: nextEarnings(r.t.ne), url: stockUrl(r.t.u) }));
  const filters = { signal: sig, market: mkt, group: p.group ? String(p.group).slice(0, 60) : null, min_plays: minp || null, sort, limit,
    weights: useCustom ? { w: custom.W.w, buy: custom.W.buy, sell: custom.W.sell } : "standard" };
  const body = { count: rows.length, shown: out.length, rows: out, filters, as_of: D.R.asof, tier: "member" };
  if (grp && !rows.length && !I.names.some((t) => t.g.toLowerCase() === grp || slug(t.g) === slug(grp))) {
    body.groups = [...new Set(I.names.map((t) => t.g))].sort();
  }
  const what = [sig ? sigWord(SIGNAL_IN[sig]) + "s" : "Names", mkt ? "in " + MARKET_WORD[mkt] : "", body.filters.group ? "in " + body.filters.group : "",
    minp ? `with at least ${minp}% of plays in` : ""].filter(Boolean).join(" ");
  let text = `${what}: ${rows.length} match` + (rows.length > out.length ? `, the first ${out.length} by ${sort === "plays" ? "plays in" : sort === "earnings" ? "next earnings report" : "score"}` : "") +
    ` (${useCustom ? "custom weights: " + wordsFor(P, custom.W.w) : "standard weights"}).`;
  if (out.length) text += "\n" + out.map((x, i) => `${i + 1}. ${x.ticker}: ${x.name}, ${x.group}. ${x.signal}${x.score != null ? " " + x.score : ""}, ${x.plays_in.k} of ${x.plays_in.of} plays in, close ${money(x.close, x.currency === "CAD" ? "C$" : "$")}` +
    (x.next_earnings ? `, next earnings ${day(x.next_earnings.date)}${x.next_earnings.timing ? " " + x.next_earnings.timing : ""}` : "") + ".").join("\n");
  if (body.groups) text += "\nNo group by that name. Groups: " + body.groups.join(", ") + ".";
  text += `\nData as of the ${day(D.R.asof)} close.`;
  return done(200, body, text, "member");
}

// ------------------------------------------------------------------ plays (data/api.json)
function playSummary(p) {
  return { slug: p.slug, name: p.name, family: p.family, family_name: p.family_name, people: p.people.map((x) => x.name),
    calls_right: p.record ? p.record.calls_right : null, calls: p.record ? p.record.calls : null, ranked: !!(p.record && p.record.ranked),
    top_in_family: !!(p.record && p.record.top), url: p.url };
}
const rightWords = (r) => (r && r.calls_right != null ? `right on ${Math.round(r.calls_right * 100)}% of ${num(r.calls, 0)} finished calls across ${r.stocks} stocks` : "no graded record yet");

/** list_plays / GET /api/v1/plays (members) */
export function listPlays(D, { family = null } = {}) {
  const A = D.A;
  let fam = null;
  if (family != null && family !== "") {
    const f = String(family).toLowerCase();
    fam = A.families.find((x) => x.key === f || x.name.toLowerCase() === f);
    if (!fam) return errorAnswer(400, "family is one of: " + A.families.map((x) => x.key).join(", ") + ".", "member");
  }
  const plays = A.plays.filter((p) => !fam || p.family === fam.key).map(playSummary);
  const fams = A.families.filter((x) => !fam || x.key === fam.key);
  const text = `${plays.length} published plays${fam ? " in " + fam.name : ""}, each a long-or-cash rule run on every covered name since ${A.since || 2005} (calls right = the share of finished calls on real stocks that went the right way):\n` +
    fams.map((f) => `${f.name}: ${f.about}\n` + plays.filter((p) => p.family === f.key)
      .map((p) => `- ${p.name} (${p.slug}), ${p.people.join(" & ")}: ${p.calls_right == null ? "no graded record yet" : Math.round(p.calls_right * 100) + "% right"}${p.top_in_family ? ", the most accurate in its family" : ""}.`).join("\n")).join("\n") +
    `\nAs of the ${day(A.asof)} close.`;
  return done(200, { count: plays.length, families: fams, plays, as_of: A.asof, tier: "member" }, text, "member");
}

/** explain_play / GET /api/v1/plays/{slug} (members) */
export function explainPlay(D, q) {
  const A = D.A;
  const s = String(q == null ? "" : q).trim().toLowerCase().slice(0, 80);
  if (!s) return errorAnswer(400, "Give a play's name or slug, e.g. stage-analysis.", "member");
  let p = A.plays.find((x) => x.slug === s) || A.plays.find((x) => x.name.toLowerCase() === s || (x.long_name || "").toLowerCase() === s);
  if (!p) {
    const hits = A.plays.filter((x) => x.name.toLowerCase().includes(s) || (x.long_name || "").toLowerCase().includes(s) || x.slug.includes(s));
    if (hits.length === 1) p = hits[0];
    else {
      const msg = hits.length ? "More than one play matches: " + hits.slice(0, 8).map((x) => `${x.name} (${x.slug})`).join(", ") + "." :
        "No play by that name. list_plays (GET /api/v1/plays) lists all of them.";
      return errorAnswer(hits.length ? 400 : 404, msg, "member", hits.length ? { matches: hits.slice(0, 8).map(playSummary) } : {});
    }
  }
  const body = { ...p, as_of: A.asof, tier: "member" };
  const L = [`${p.name}${p.long_name && p.long_name !== p.name ? " (" + p.long_name + ")" : ""}: a ${p.family_name.toLowerCase()} play on ${p.timeframe} bars, from ${p.people.map((x) => x.name + (x.role ? ", " + x.role : "")).join("; ")}.`,
    p.about, "The rule:\n" + p.rules.map((r) => "- " + r).join("\n")];
  if (p.assumptions && p.assumptions.length) L.push("Be The Puck's assumptions:\n" + p.assumptions.map((r) => "- " + r).join("\n"));
  if (p.origin) L.push("Source: " + p.origin + ".");
  if (p.flag) L.push("Note: " + p.flag + ".");
  L.push(`Record: ${rightWords(p.record)}` + (p.record && p.record.top ? "; the most accurate play in its family." : p.record && p.record.ranked ? "." : " (too few calls to rank)."));
  L.push(`Page: ${p.url}` + (p.example ? ` · worked example on SPY: ${p.example}` : ""));
  L.push(`As of the ${day(A.asof)} close.`);
  return done(200, body, L.join("\n"), "member");
}

/** market_conditions / GET /api/v1/market (members) */
export function market(D) {
  const A = D.A, I = index(D);
  const tally = (list) => {
    const c = { buy: 0, hold: 0, sell: 0, no_score: 0, held: 0, guard: 0, names: list.length };
    for (const t of list) {
      c[t.S === 1 ? "buy" : t.S === 0 ? "hold" : t.S === -1 ? "sell" : "no_score"]++;
      if (t.hd) c.held++;
      if (t.gd) c.guard++;
    }
    return c;
  };
  const by = {};
  for (const m of Object.keys(MARKET_WORD)) by[m] = tally(I.names.filter((t) => t.m === m));
  const all = tally(I.names);
  const guards = (A.markets || []).map((m) => ({ ...m, words: `${m.name}: closed at ${money(m.close, "")} on ${day(m.date)}, ${Math.round(Math.abs(m.below_high) * 100)}% below its 1-year high of ${money(m.high_1y, "")}. ` +
    (m.guard ? `The market guard is on for its stocks: ${m.name} is ${Math.round(A.guard_at * 100)}% or more below its 1-year high, so the price factors stand down.` : `The market guard is off (it turns on at ${Math.round(A.guard_at * 100)}% below the high).`) }));
  const body = { guards, signals: { all, by_market: by }, weather: A.weather || null, guard_at: A.guard_at, as_of: D.R.asof, tier: "member" };
  const L = guards.map((g) => g.words);
  L.push(`Across the ${all.names} covered names (standard weights): ${all.buy} Buy, ${all.hold} Hold, ${all.sell} Sell` + (all.no_score ? `, ${all.no_score} with no score` : "") + `; ${all.held} held by the sticky rule; ` +
    (all.guard ? `the market guard is on for ${all.guard}.` : "the market guard is on for none of them."));
  L.push("By market: " + Object.entries(by).filter(([, c]) => c.names).map(([m, c]) => `${MARKET_WORD[m]} ${c.buy} Buy / ${c.hold} Hold / ${c.sell} Sell`).join("; ") + ".");
  if (A.weather) L.push(`Crash gauges: ${A.weather.word} (${A.weather.warning} warning, ${A.weather.watch} watch, ${A.weather.calm} calm of nine). ${SITE}/markets/`);
  L.push(`Data as of the ${day(D.R.asof)} close.`);
  return done(200, body, L.join("\n"), "member");
}
