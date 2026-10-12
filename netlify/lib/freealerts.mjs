/* freealerts.mjs: the free "your signal flipped" email alerts (shared by alerts.mjs and alerts-nightly.mjs).
 *
 * A subscriber is stored in the Blobs store "alerts" under sub/<id>, where id is a
 * keyed hash of the lower-cased email:
 *   {email, tickers, confirmed, created, confirm_sent, pending, last: {SYM: [S, k, of]}}
 * last holds the signal we last told them about (1 Buy, 0 Hold, -1 Sell; the standard
 * weights, since a subscriber without an account has no saved weights) so an email only
 * goes out when it flips. Before October 2026 it held the Start/Stop light (1/0); the
 * first run after the change records the signal without emailing. Links in emails carry signed tokens (QM_SECRET):
 *   {k: "ac", id, x}  confirm (x = the ticker list being confirmed), 14 days
 *   {k: "am", id}     manage / unsubscribe, no expiry (deleting the record kills it)
 */
import { env, sign, verify, hashId, siteUrl, now, DAY } from "./qm.mjs";
import * as mail from "./mail.mjs";
import { SIG_WORD, SIG_COLOR } from "./signal.mjs";

export const STORE = "alerts";
export const MAX_TICKERS = 50;
export const EMAIL_RX = /^[^\s@<>"',;]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$/;
export const subId = (email) => hashId("alert-email:" + String(email).trim().toLowerCase(), env("QM_SECRET"));

export const confirmToken = (id, tickers) => sign({ k: "ac", id, x: tickers, exp: now() + 14 * DAY }, env("QM_SECRET"));
export const manageToken = (id) => sign({ k: "am", id }, env("QM_SECRET"));
export function readToken(t, kind) {
  const p = verify(t, env("QM_SECRET"));
  if (!p || p.k !== kind || !p.id) return null;
  if (p.exp && p.exp < now()) return null;
  return p;
}
export const manageUrl = (id) => siteUrl() + "/alerts/?m=" + encodeURIComponent(manageToken(id));
export const unsubUrl = (id) => siteUrl() + "/api/alerts/unsubscribe?t=" + encodeURIComponent(manageToken(id));

const esc = mail.esc;
const DISCLAIMER = "This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.";

/** Who sent it, why they got it, and how to stop (CASL / CAN-SPAM). */
function footer(id) {
  const addr = env("QM_MAIL_ADDRESS");
  return `${DISCLAIMER}<br><br>You're getting this because you asked Be The Puck to email you when its signal changes on your stocks. ` +
    `<a href="${esc(manageUrl(id))}">Change your stocks</a> · <a href="${esc(unsubUrl(id))}">Unsubscribe</a><br>` +
    `Be The Puck (bethepuck.com) is made by Click Shift Marketing${addr ? ", " + esc(addr) : ""}.`;
}

function headers(id) {
  return { "List-Unsubscribe": `<${unsubUrl(id)}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" };
}

export function confirmEmail(id, email, tickers, R) {
  const url = siteUrl() + "/api/alerts/confirm?t=" + encodeURIComponent(confirmToken(id, tickers));
  const names = tickers.map((s) => (R && R.t[s] ? R.t[s].s : s)).join(", ");
  const html = mail.shell("Confirm your Be The Puck alerts",
    `<p>Tap the button to start getting an email when Be The Puck's signal (Buy, Hold or Sell) changes on: <b>${esc(names)}</b>.</p>` +
    `<p style="margin:22px 0"><a href="${esc(url)}" style="background:#7c6cf5;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:600">Confirm my alerts</a></p>` +
    `<p style="color:#6b7385;font-size:13px">If you didn't ask for this, ignore this email and nothing will be sent. The link works for 14 days.</p>`,
    `${DISCLAIMER}<br><br>Be The Puck (bethepuck.com) is made by Click Shift Marketing.`);
  const text = `Confirm your Be The Puck alerts for ${names}: ${url}\n\nIf you didn't ask for this, ignore this email.\n\n${DISCLAIMER}`;
  return { to: email, subject: "Confirm your Be The Puck alerts", html, text };
}

const fmtDate = (iso) => (iso ? new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : "");

/** One line on why a signal reads what it does. */
export function sigLine(S, sc, k, of, buy = 60, sell = 40) {
  const plays = of ? `${k} of ${of} plays hold it. ` : "";
  if (sc == null) return plays;
  const where = S === 1 ? `at or above the Buy line of ${buy}` : S === -1 ? `at or below the Sell line of ${sell}` : `between the Sell line (${sell}) and the Buy line (${buy})`;
  return `${plays}The score is ${sc}, ${where}.`;
}

/** One email listing every flip on a subscriber's stocks. flips: [{sym, t (reads.json entry), was: [S,k,of]}] */
export function flipEmail(id, email, flips, R) {
  const word = (S) => SIG_WORD[S] || "No score";
  const subject = flips.length === 1
    ? `${flips[0].t.n} (${flips[0].t.s}): the signal turned ${word(flips[0].t.S).toUpperCase()}`
    : `${flips.length} of your stocks changed: ` + flips.slice(0, 3).map((f) => `${f.t.s} ${word(f.t.S)}`).join(", ") + (flips.length > 3 ? "…" : "");
  const blocks = flips.map((f) => {
    const t = f.t;
    const was = f.was && f.was[0] != null ? ` (was ${word(f.was[0])})` : "";
    const read = (t.read || []).map((x) => `<li style="margin:0 0 6px">${esc(x)}</li>`).join("");
    const url = siteUrl() + "/stocks/" + t.u + "/";
    return `<div style="border:1px solid #e3e6ee;border-radius:12px;padding:16px 18px;margin:0 0 14px">` +
      `<p style="margin:0 0 6px;font-size:13px;color:#6b7385">${esc(t.s)} · ${esc(t.cur)}${t.p != null ? Number(t.p).toLocaleString("en-US", { maximumFractionDigits: 2 }) : ""} at the ${esc(fmtDate(R.asof))} close</p>` +
      `<p style="margin:0 0 10px;font-size:18px;font-weight:700">${esc(t.n)}: <span style="color:${SIG_COLOR[t.S] || "#6b7385"}">${esc(word(t.S).toUpperCase())}</span>${esc(was)}</p>` +
      `<p style="margin:0 0 10px">${esc(sigLine(t.S, t.sc, t.k, t.of))}</p>` +
      (read ? `<ul style="margin:0 0 10px;padding-left:20px">${read}</ul>` : "") +
      `<p style="margin:0"><a href="${esc(url)}">See the full analysis for ${esc(t.s)}</a></p></div>`;
  }).join("");
  const intro = "<p>Be The Puck's signal is its one call on a stock: Buy, Hold or Sell from a score of 0 to 100. These use the standard weights, half the plays and half analysts' upside; " +
    `<a href="${esc(siteUrl() + "/me/")}">a free account</a> lets you set your own and get emails on those. Here's what changed on your stocks at the latest close.</p>`;
  const html = mail.shell(subject, intro + blocks, footer(id));
  const text = flips.map((f) => `${f.t.n} (${f.t.s}): ${word(f.t.S).toUpperCase()}. ${sigLine(f.t.S, f.t.sc, f.t.k, f.t.of)} ${(f.t.read || []).join(" ")} ${siteUrl()}/stocks/${f.t.u}/`).join("\n\n") +
    `\n\n${DISCLAIMER}\nChange your stocks: ${manageUrl(id)}\nUnsubscribe: ${unsubUrl(id)}`;
  return { to: email, subject, html, text, headers: headers(id) };
}

/** Send a list of {to, subject, html, text, headers} through Resend's batch endpoint (100 at a time). */
export async function sendAll(msgs) {
  if (!mail.configured() || !msgs.length) return { sent: 0 };
  const from = env("QM_FROM") || "Be The Puck <alerts@bethepuck.com>";
  let sent = 0;
  for (let i = 0; i < msgs.length; i += 100) {
    const chunk = msgs.slice(i, i + 100).map((m) => ({ from, to: [m.to], subject: m.subject, html: m.html, text: m.text, headers: m.headers }));
    const r = await fetch("https://api.resend.com/emails/batch", {
      method: "POST",
      headers: { authorization: "Bearer " + env("RESEND_API_KEY"), "content-type": "application/json" },
      body: JSON.stringify(chunk),
    });
    if (r.ok) sent += chunk.length;
    else console.error("alerts: Resend batch failed", r.status, (await r.text()).slice(0, 300));
  }
  return { sent };
}

export async function sendOne(m) {
  return mail.configured() ? sendAll([m]) : { sent: 0 };
}
