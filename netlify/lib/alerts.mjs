/* alerts.mjs: what changed on a member's stocks between two closes, and the
 * email that says so. Used by netlify/functions/member-alerts.mjs. */
import { siteUrl } from "./qm.mjs";
import * as mail from "./mail.mjs";

const NEAR = 0.02;
const BIG_MOVE = 0.05;
const LEVEL = /\b(Exit|Buy|Sell|Enter) (below|above) [^\d]*([\d,]+(?:\.\d+)?)/;

const pct = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v * 100).toFixed(d) + "%";
const fmtDate = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** Where each listed stock stands at this close, and what changed since `prev`. */
export function compare(D, tickers, prev) {
  const core = D.plays.map((p, i) => (p.c ? i : -1)).filter((i) => i >= 0);
  // calls are compared by play, not by position, so adding plays never fakes a flip;
  // a snapshot from before plays were recorded (no prev.plays) only records tonight's calls
  const slugs = core.map((i) => D.plays[i].s);
  const was = prev && Array.isArray(prev.plays) ? Object.fromEntries(prev.plays.map((s, j) => [s, j])) : null;
  const snap = { asof: D.asof, plays: slugs, s: {} };
  const out = [];
  for (const sym of tickers) {
    const t = D.t[sym];
    if (!t) continue;
    const c = core.map((i) => t.c[i]).join("");
    const near = [];
    for (const [slug, txt] of Object.entries(t.m || {})) {
      const m = LEVEL.exec(txt || "");
      if (!m || !t.p) continue;
      const lvl = parseFloat(m[3].replace(/,/g, ""));
      const dist = lvl / t.p - 1;
      if (Math.abs(dist) <= NEAR) near.push([slug, m[1], m[2], lvl, dist]);
    }
    snap.s[sym] = { c, r: t.r ? t.r[1] : null, near: near.map((x) => x[0]) };
    const items = [];
    const old = prev && prev.s && prev.s[sym];
    if (old) {
      core.forEach((pi, j) => {
        if (!was || was[slugs[j]] === undefined) return;
        const a = old.c[was[slugs[j]]], b = c[j];
        if (a === b || (a !== "0" && a !== "1") || (b !== "0" && b !== "1")) return;
        items.push({ kind: b === "1" ? "in" : "out", text: `${D.plays[pi].n} ${b === "1" ? "got in" : "got out"}` });
      });
      for (const [slug, verb, , lvl, dist] of near) {
        if ((old.near || []).includes(slug)) continue;
        const p = D.plays.find((x) => x.s === slug);
        const what = /Exit|Sell/.test(verb) ? "exit" : "entry";
        const at = lvl.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        items.push({ kind: "near", text: `${Math.abs(dist * 100).toFixed(1)}% ${dist < 0 ? "above" : "below"} the ${p ? p.n : slug} ${what} at ${t.cur || "$"}${at}` });
      }
      if (old.r && t.r && old.r !== t.r[1]) items.push({ kind: "risk", text: `Crash exposure now ${t.r[1]} (was ${old.r})` });
    }
    if (t.d1 != null && Math.abs(t.d1) >= BIG_MOVE) items.push({ kind: "move", text: `${pct(t.d1)} on the day` });
    if (items.length) {
      const k = c.split("").filter((x) => x === "1").length, n = c.split("").filter((x) => x === "0" || x === "1").length;
      out.push({ sym, name: t.n, short: t.s, slug: t.u, k, n, items });
    }
  }
  return { snap, changes: out };
}

export function digest(D, changes) {
  const base = siteUrl();
  const nItems = changes.reduce((a, c) => a + c.items.length, 0);
  const subject = `Be The Puck: ${nItems} change${nItems === 1 ? "" : "s"} on your stocks after the ${fmtDate(D.asof)} close`;
  const color = { in: "#14946a", out: "#d23c55", near: "#a8740f", risk: "#a8740f", move: "#141821" };
  const blocks = changes.map((c) => `<div style="padding:12px 0;border-top:1px solid #e3e6ee">
<p style="margin:0 0 6px"><a href="${base}/stocks/${mail.esc(c.slug)}/" style="color:#141821;font-weight:700;text-decoration:none">${mail.esc(c.short)}</a> <span style="color:#6b7385">${mail.esc(c.name)} · ${c.k} of ${c.n} core plays in</span></p>
<ul style="margin:0;padding-left:18px">${c.items.map((i) => `<li style="color:${color[i.kind]}">${mail.esc(i.text)}</li>`).join("")}</ul></div>`).join("");
  const html = mail.shell(`What changed on your stocks after the ${fmtDate(D.asof)} close`, `${blocks}
<p style="margin:16px 0 0"><a href="${base}/watchlist/">Open your watchlist</a> · <a href="${base}/picks/">Top picks</a></p>
<p style="font-size:12px;color:#6b7385;margin-top:10px">You get this because alerts are on for your saved list. Turn them off on the <a href="${base}/watchlist/">watchlist page</a>.</p>`);
  const text = changes.map((c) => `${c.short}: ${c.items.map((i) => i.text).join("; ")}`).join("\n") + `\n\n${base}/watchlist/`;
  return { subject, html, text };
}
