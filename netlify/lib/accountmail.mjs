/* accountmail.mjs: the emails a Be The Puck account gets.
 *   confirmMsg   confirm an email address (sent on sign-up or when the address changes)
 *   resetMsg     a one-hour link to set a new password
 *   ownerMsg     to the site owner (QM_OWNER_EMAIL): a new account, with the running total
 *   nightlyMsg   "your stocks tonight": Start/Stop flips (always free) and, for members
 *                (free for every account until FREE_UNTIL), every play that got in or out
 * Each returns {to, subject, html, text, headers}. Senders: freealerts.sendAll / sendOne.
 */
import { env, siteUrl } from "./qm.mjs";
import * as mail from "./mail.mjs";
import { confirmUrl, resetUrl, stopUrl, manageUrl, FREE_UNTIL_LABEL, freeNow } from "./account.mjs";

const esc = mail.esc;
const DISCLAIMER = "This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision.";
const fmtDate = (iso) => (iso ? new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : "");
const sender = () => { const a = env("QM_MAIL_ADDRESS"); return `Be The Puck (bethepuck.com) is made by Click Shift Marketing${a ? ", " + esc(a) : ""}.`; };

export function confirmMsg(u, acct) {
  const url = confirmUrl(u, acct.email);
  const html = mail.shell("Confirm your email",
    `<p>Hi ${esc(acct.name)}. Tap the button to confirm this is your address. Once it's confirmed, Be The Puck can email you when the Start/Stop light flips on the stocks you follow, and you can reset your password if you ever forget it.</p>` +
    mail.button(url, "Confirm my email") +
    `<p style="color:#6b7385;font-size:13px">The link works for 14 days. If you didn't make a Be The Puck account, ignore this email and nothing more will be sent.</p>`,
    `${DISCLAIMER}<br><br>${sender()}`, "One tap to switch on your stock alerts.");
  const text = `Hi ${acct.name}. Confirm your email for Be The Puck: ${url}\n\nIf you didn't make an account, ignore this email.\n\n${DISCLAIMER}`;
  return { to: acct.email, subject: "Confirm your email for Be The Puck", html, text };
}

export function resetMsg(u, acct) {
  const url = resetUrl(u, acct.v);
  const html = mail.shell("Reset your password",
    `<p>Someone (hopefully you) asked to reset the password for <b>${esc(acct.name)}</b> on Be The Puck.</p>` +
    mail.button(url, "Choose a new password") +
    `<p style="color:#6b7385;font-size:13px">The link works for one hour and only once. If you didn't ask, ignore this email: your password stays as it is.</p>`,
    `${DISCLAIMER}<br><br>${sender()}`, "A link to choose a new password, good for one hour.");
  const text = `Reset your Be The Puck password (${acct.name}): ${url}\n\nThe link works for one hour. If you didn't ask, ignore this email.`;
  return { to: acct.email, subject: "Reset your Be The Puck password", html, text };
}

/** To the owner: someone just made an account. total = accounts on the site now. */
export function ownerMsg(acct, total, to) {
  const when = new Date(acct.created || Date.now()).toLocaleString("en-US", { timeZone: "America/Toronto", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  const html = mail.shell(`New sign-up: ${acct.name}`,
    `<p><b>${esc(acct.name)}</b> made a Be The Puck account at ${esc(when)} (Toronto time)${acct.email ? ` with an address at <b>${esc(String(acct.email).split("@")[1] || "")}</b>` : ""}.</p>` +
    `<p style="font-size:28px;font-weight:700;margin:8px 0 2px">${total.toLocaleString("en-US")}</p><p style="color:#6b7385;margin:0 0 16px">accounts on the site now</p>` +
    mail.button(siteUrl() + "/owner/", "See every sign-up"),
    "You get this because your address is set as QM_OWNER_EMAIL for bethepuck.com.", `${acct.name} just signed up. ${total} accounts now.`);
  const text = `New Be The Puck sign-up: ${acct.name} (${when} Toronto). ${total} accounts now. Every sign-up: ${siteUrl()}/owner/`;
  return { to, subject: `New sign-up: ${acct.name} · ${total.toLocaleString("en-US")} accounts`, html, text };
}

function footer(u, member) {
  const tier = member && freeNow()
    ? `<br><br>Play-by-play alerts are a member tool, free for every account until ${FREE_UNTIL_LABEL}, then $5 a month. Start/Stop flip emails stay free.`
    : "";
  return `${DISCLAIMER}${tier}<br><br>You're getting this because email alerts are on in your Be The Puck account. ` +
    `<a href="${esc(manageUrl())}">Change your stocks or alerts</a> · <a href="${esc(stopUrl(u))}">Stop these emails</a><br>${sender()}`;
}

const listUnsub = (u) => ({ "List-Unsubscribe": `<${stopUrl(u)}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" });

/** flips: [{sym, t (reads.json entry), was: [L, k, of]}]; plays: compare() changes [{sym, short, name, slug, k, n, items}] */
export function nightlyMsg(u, acct, flips, plays, R, member) {
  const base = siteUrl();
  const word = (L) => (L ? "START" : "STOP");
  const nPlay = plays.reduce((a, c) => a + c.items.filter((i) => i.kind === "in" || i.kind === "out").length, 0);
  let subject;
  if (flips.length === 1 && !nPlay) subject = `${flips[0].t.s} turned ${word(flips[0].t.L)} at the ${fmtDate(R.asof)} close`;
  else if (flips.length) subject = `${flips.map((f) => `${f.t.s} ${word(f.t.L)}`).slice(0, 3).join(", ")}${flips.length > 3 ? "…" : ""}: your stocks at the ${fmtDate(R.asof)} close`;
  else subject = `${nPlay} play${nPlay === 1 ? "" : "s"} moved on your stocks at the ${fmtDate(R.asof)} close`;

  const flipHtml = flips.map((f) => {
    const t = f.t, on = t.L === 1, color = on ? "#14895f" : "#c4304a", bg = on ? "#e8f8f1" : "#fdecef";
    const was = f.was && f.was[2] ? ` (was ${f.was[1]} of ${f.was[2]})` : "";
    const read = (t.read || []).slice(0, 3).map((x) => `<li style="margin:0 0 5px">${esc(x)}</li>`).join("");
    return `<div style="border:1px solid #e3e6ee;border-radius:12px;padding:16px 18px;margin:0 0 12px">` +
      `<p style="margin:0 0 4px;font-size:13px;color:#6b7385">${esc(t.s)} · ${esc(t.cur)}${t.p != null ? Number(t.p).toLocaleString("en-US", { maximumFractionDigits: 2 }) : ""}</p>` +
      `<p style="margin:0 0 10px;font-size:18px;font-weight:700">${esc(t.n)} <span style="display:inline-block;margin-left:6px;padding:3px 10px;border-radius:999px;font-size:12px;letter-spacing:.06em;color:${color};background:${bg}">${on ? "START" : "STOP"}</span></p>` +
      `<p style="margin:0 0 8px">${t.k} of ${t.of} plays now hold it${esc(was)}.</p>` +
      (read ? `<ul style="margin:0 0 8px;padding-left:20px;color:#3b4252">${read}</ul>` : "") +
      `<p style="margin:0"><a href="${esc(base + "/stocks/" + t.u + "/")}" style="color:#5b4bd8">Full analysis for ${esc(t.s)}</a></p></div>`;
  }).join("");

  const color = { in: "#14895f", out: "#c4304a", near: "#9a6a0b", risk: "#9a6a0b", move: "#141821" };
  const playHtml = plays.map((c) => `<div style="padding:10px 0;border-top:1px solid #e9ecf2">` +
    `<p style="margin:0 0 4px"><a href="${esc(base + "/stocks/" + c.slug + "/")}" style="color:#141821;font-weight:700;text-decoration:none">${esc(c.short)}</a> <span style="color:#6b7385;font-size:13px">${esc(c.name)} · ${c.k} of ${c.n} plays in</span></p>` +
    `<ul style="margin:0;padding-left:18px">${c.items.slice(0, 12).map((i) => `<li style="color:${color[i.kind]}">${esc(i.text)}</li>`).join("")}${c.items.length > 12 ? `<li style="color:#6b7385">and ${c.items.length - 12} more</li>` : ""}</ul></div>`).join("");

  const body = `<p>Here's what changed on the ${(acct.follow || []).length} stocks you follow at the ${esc(fmtDate(R.asof))} close.</p>` +
    (flipHtml ? `<p style="margin:18px 0 10px;font:600 12px/1 -apple-system,Segoe UI,Roboto,sans-serif;letter-spacing:.08em;color:#6b7385;text-transform:uppercase">The Start/Stop light</p>${flipHtml}` : "") +
    (playHtml ? `<p style="margin:20px 0 6px;font:600 12px/1 -apple-system,Segoe UI,Roboto,sans-serif;letter-spacing:.08em;color:#6b7385;text-transform:uppercase">Play by play</p>${playHtml}` : "") +
    mail.button(base + "/me/", "Open My Puck");
  const html = mail.shell(subject, body, footer(u, member), flips.length ? "The Start/Stop light changed on your stocks." : "Plays moved on your stocks tonight.");
  const text = [
    ...flips.map((f) => `${f.t.n} (${f.t.s}): ${word(f.t.L)}. ${f.t.k} of ${f.t.of} plays now hold it. ${base}/stocks/${f.t.u}/`),
    ...plays.map((c) => `${c.short}: ${c.items.map((i) => i.text).join("; ")}`),
  ].join("\n\n") + `\n\nMy Puck: ${base}/me/\n\n${DISCLAIMER}\nStop these emails: ${stopUrl(u)}`;
  return { to: acct.email, subject, html, text, headers: listUnsub(u) };
}
