/* signal.mjs: Your signal on the server, for the alert emails. The same arithmetic as
 * assets/plays.js (score, resolve, count) over the same data/playset.json, so an email
 * says what the reader's own stock page says.
 *
 *   const D = await loadPlayset();
 *   signalFor(D, "MU", acct.plays, acct.signal)  ->  { s: 0-100 | null, sig: 1 | 0 | -1 | null }
 *
 * plays: {p: all|top1|top3|half|custom, s: [slugs]} (null = every play)
 * signal: {w: {factor: weight}, buy, sell}       (null = the standard weights)
 */
import { siteUrl } from "./qm.mjs";

export async function loadPlayset() {
  const r = await fetch(siteUrl() + "/data/playset.json", { cache: "no-store" });
  if (!r.ok) throw new Error("playset.json " + r.status);
  return r.json();
}

/** Which plays a choice counts, as 0/1 over D.plays (assets/plays.js resolve). */
export function resolve(D, c) {
  const n = D.plays.length, out = new Uint8Array(n);
  const p = c && c.p ? c.p : "all";
  if (p === "all") { out.fill(1); return out; }
  if (p === "half") D.plays.forEach((x, i) => { if (x.e && x.a != null && x.a > 0.5) out[i] = 1; });
  else if (p === "top1" || p === "top3") {
    const per = p === "top1" ? 1 : 3;
    for (const f of D.fams) {
      const ix = [];
      D.plays.forEach((x, i) => { if (x.f === f[0] && x.e) ix.push(i); });
      ix.sort((a, b) => D.plays[b].a - D.plays[a].a || D.plays[b].c - D.plays[a].c);
      ix.slice(0, per).forEach((i) => { out[i] = 1; });
    }
  } else {
    const idx = Object.fromEntries(D.plays.map((x, i) => [x.s, i]));
    for (const s of c.s || []) if (idx[s] != null) out[idx[s]] = 1;
  }
  if (!out.some((x) => x)) out.fill(1);
  return out;
}

/** Plays in: how many of the chosen plays hold the stock, of those with a call. */
export function count(D, sym, sel) {
  const st = D.t[sym] || "";
  let k = 0, n = 0;
  for (let i = 0; i < st.length; i++) {
    if (!sel[i] || st[i] === "-") continue;
    n++;
    if (st[i] === "1") k++;
  }
  return { k, n };
}

/** The standard weights unless the reader saved valid ones (assets/plays.js cleanW). */
const sameW = (a, b) => {
  const ka = Object.keys(a || {}).filter((k) => a[k] > 0), kb = Object.keys(b || {}).filter((k) => b[k] > 0);
  if (ka.length !== kb.length || !ka.length) return false;
  const r = a[ka[0]] / (b[ka[0]] || NaN);
  return ka.every((k) => b[k] && Math.abs(a[k] / b[k] - r) < 1e-9);
};

export function weights(D, c) {
  // weights saved before the standard changed that were just the old standard move to the new one (as in plays.js)
  if (c && D.wo && (c.mv || 1) < (D.mv || 1) && sameW(c.w, D.wo)) c = { ...c, w: { ...D.wd.w } };
  const w = {};
  let any = false;
  for (const f of D.fx) {
    const v = c && c.w ? +c.w[f.k] : 0;
    if (v > 0) { w[f.k] = Math.min(100, Math.round(v)); any = true; }
  }
  const W = any ? w : { ...D.wd.w };
  const buy = Math.min(95, Math.max(50, Math.round(+(c && c.buy) || D.wd.buy)));
  const sell = Math.min(buy - 5, Math.max(5, Math.round(+(c && c.sell) || D.wd.sell)));
  return { w: W, buy, sell };
}

/** The standard setup: the standard weights and lines with every play counted (assets/plays.js isStandard).
 *  It is the one setup with a day-by-day path behind it, so the only one whose calls the sticky rule holds. */
export function isStandard(D, W, plays) {
  return !!D.st && (!plays || !plays.p || plays.p === "all") && sameW(W.w, D.wd.w) && W.buy === D.wd.buy && W.sell === D.wd.sell;
}

/** {s, sig, gd: the market guard is on, hd: the call is held by the sticky rule}, as assets/plays.js score(). */
export function signalFor(D, sym, plays, signal, sel) {
  const x = D.x[sym];
  if (!x) return { s: null, sig: null };
  const W = weights(D, signal);
  const chosen = sel || resolve(D, plays);
  const guard = !!(D.gd && D.gd[sym]), pk = D.pk || [];
  let tot = 0, avail = 0, acc = 0;
  D.fx.forEach((f, i) => {
    const wi = W.w[f.k] || 0;
    if (!wi || (guard && pk.includes(f.k))) return;     // a price factor stands down while the guard is on
    tot += wi;
    let p = x[i];
    if (f.k === "plays") { const c = count(D, sym, chosen); p = c.n ? Math.round((100 * c.k) / c.n) : null; }
    if (p != null) { avail += wi; acc += wi * p; }
  });
  if (!tot || avail < tot / 2) return { s: null, sig: null, gd: guard };
  const s = Math.round(acc / avail);
  const plain = s >= W.buy ? 1 : s <= W.sell ? -1 : 0;
  let sig = plain;
  // the standard setup follows the path's sticky call, as long as the path scored the same number today
  if (isStandard(D, W, plays) && D.st[sym] && D.st[sym][1] === s && D.st[sym][0] != null) sig = D.st[sym][0];
  return { s, sig, gd: guard, hd: sig !== plain };
}

export const SIG_WORD = { 1: "Buy", 0: "Hold", "-1": "Sell" };
export const SIG_COLOR = { 1: "#14895f", 0: "#b7791f", "-1": "#c4304a" };
