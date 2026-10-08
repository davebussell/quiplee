/* weekly-weather.mjs: the free Saturday email, "This week's market weather".
 *
 * Runs Saturday mornings. Reads /data/weather.json (written by the build from
 * tools/qstrat/weekly.py: the crash gauges, the plays on the S&P 500 and every
 * light that flipped in the last seven days) and sends it to every confirmed
 * subscriber in the "alerts" store with weekly: true. The close it sent is kept
 * under weekly-state, so a re-run never sends the same week twice.
 * Needs RESEND_API_KEY (and QM_SECRET for the unsubscribe links).
 */
import { getStore } from "@netlify/blobs";
import { siteUrl } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { STORE, sendAll, footer, headers } from "../lib/freealerts.mjs";

const esc = mail.esc;
const COLOR = { warning: "#c4304a", watch: "#b7791f", calm: "#14895f" };
const fmtDate = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const pct = (v) => (v == null ? "" : (v >= 0 ? "+" : "−") + Math.abs(Math.round(v * 100)) + "%");
const money = (p, c) => (c || "$") + Number(p).toLocaleString("en-US", { maximumFractionDigits: 2 });

function list(items, base) {
  if (!items.length) return `<p style="color:#6b7385;margin:0 0 12px">None this week.</p>`;
  return `<ul style="margin:0 0 14px;padding-left:18px">` + items.map((r) =>
    `<li style="margin:0 0 6px"><a href="${esc(base + "/stocks/" + r.u + "/")}" style="color:#141821;font-weight:600">${esc(r.s)}</a> ${esc(r.n)}` +
    `<span style="color:#6b7385"> · ${r.k} of ${r.o} plays · ${esc(money(r.p, r.c))}${r.up != null ? " · analysts " + pct(r.up) : ""}</span></li>`).join("") + `</ul>`;
}

export function weeklyEmail(id, email, W) {
  const base = siteUrl();
  const week = fmtDate(W.asof);
  const subject = `Market weather: ${W.weather || "this week"} · ${W.n_start} stocks turned Start`;
  const gauges = W.gauges.map((g) =>
    `<tr><td style="padding:4px 8px 4px 0"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${COLOR[g.st] || "#8a95a9"}"></span> ${esc(g.name)}</td>` +
    `<td style="padding:4px 0;text-align:right;font-family:Menlo,monospace">${esc(g.v)}</td></tr>`).join("");
  const sp = W.spx ? `<p style="margin:0 0 16px">The plays on the S&amp;P 500: <b>${W.spx.k} of ${W.spx.n} hold it</b> (${W.spx.L === 1 ? "Start" : W.spx.L === 0 ? "Stop" : "–"}).</p>` : "";
  const h2 = (t) => `<h2 style="font:600 17px/1.3 Georgia,serif;margin:18px 0 8px">${t}</h2>`;
  const body =
    `<p style="margin:0 0 6px;color:#6b7385;font-size:13px">Week to ${esc(week)}</p>` +
    `<p style="margin:0 0 12px"><b>${esc(W.weather || "")}.</b> ${esc(W.answer || "")} ${W.warning} of ${W.gauges.length} crash gauges flash a warning.</p>` +
    `<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:14px;margin:0 0 14px">${gauges}</table>` + sp +
    h2(`Turned Start this week (${W.n_start})`) + list(W.start, base) +
    h2(`Turned Stop this week (${W.n_stop})`) + list(W.stop, base) +
    (W.ca_start && W.ca_start.length ? h2("Canada: turned Start") + list(W.ca_start, base) : "") +
    mail.button(base + "/weekly/", "See the full week");
  const text = `Market weather, week to ${week}: ${W.weather}. ${W.warning} of ${W.gauges.length} crash gauges flash a warning.\n\n` +
    `Turned Start: ${W.start.map((r) => r.s).join(", ") || "none"}\nTurned Stop: ${W.stop.map((r) => r.s).join(", ") || "none"}\n\n${base}/weekly/`;
  const html = mail.shell("This week's market weather", body, footer(id, "to email you the weekly market weather"), `${W.weather}: ${W.n_start} turned Start, ${W.n_stop} turned Stop`);
  return { to: email, subject, html, text: text + "\n\nNot trading advice.", headers: headers(id) };
}

export default async () => {
  if (!mail.configured()) { console.log("weekly-weather: RESEND_API_KEY not set, nothing to send"); return; }
  const r = await fetch(siteUrl() + "/data/weather.json", { cache: "no-store" });
  if (!r.ok) throw new Error("weather.json " + r.status);
  const W = await r.json();
  const s = getStore({ name: STORE, consistency: "strong" });
  const st = (await s.get("weekly-state", { type: "json" })) || {};
  if (st.asof === W.asof) { console.log("weekly-weather: already sent for", W.asof); return; }
  const keys = [];
  for await (const page of s.list({ prefix: "sub/", paginate: true })) keys.push(...page.blobs.map((b) => b.key));
  const msgs = [];
  for (let i = 0; i < keys.length; i += 25) {
    const recs = await Promise.all(keys.slice(i, i + 25).map((k) => s.get(k, { type: "json" }).catch(() => null)));
    recs.forEach((rec, j) => { if (rec && rec.confirmed && rec.weekly) msgs.push(weeklyEmail(keys[i + j].slice(4), rec.email, W)); });
  }
  const { sent } = await sendAll(msgs);
  await s.setJSON("weekly-state", { asof: W.asof, run: new Date().toISOString(), emails: sent });
  console.log(`weekly-weather: ${msgs.length} queued, ${sent} sent, close ${W.asof}`);
};

// Saturdays 14:00 UTC (10 am Eastern in summer, 9 am in winter)
export const config = { schedule: "0 14 * * 6" };
