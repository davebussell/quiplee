/* mail.mjs: sending email through Resend (https://resend.com).
 * Env: RESEND_API_KEY, QM_FROM (default "Be The Puck <alerts@bethepuck.com>"; the
 * domain has to be verified in Resend first).
 */
import { env } from "./qm.mjs";

export const configured = () => !!env("RESEND_API_KEY");

export async function send(to, subject, html, text) {
  if (!configured() || !to) return { ok: false, skipped: true };
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: "Bearer " + env("RESEND_API_KEY"), "content-type": "application/json" },
    body: JSON.stringify({ from: env("QM_FROM") || "Be The Puck <alerts@bethepuck.com>", to: [to], subject, html, text }),
  });
  return { ok: r.ok, status: r.status };
}

export const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** The branded email shell: a dark masthead, a white card and a grey footer. Mail clients
 * ignore most CSS, so everything is inline and table-based. pre = the inbox preview line. */
export function shell(title, bodyHtml, footer, pre) {
  const foot = footer || "This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Be The Puck reports what published trading rules say; it doesn't know your goals, taxes or timeline.";
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"></head>
<body style="margin:0;padding:0;background:#eef0f5;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#141821">
${pre ? `<div style="display:none;max-height:0;overflow:hidden;opacity:0">${esc(pre)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>` : ""}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef0f5"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #e1e4ec;border-radius:14px;overflow:hidden">
<tr><td style="background:#0b0f17;padding:18px 24px">
<a href="https://bethepuck.com/" style="text-decoration:none;font:800 20px/1 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#eef2f9">be<span style="color:#8a95a9;font-weight:600">the</span>puck<span style="color:#1fd093;font-size:11px;vertical-align:super">&#9650;</span></a>
</td></tr>
<tr><td style="padding:26px 24px 8px">
<h1 style="font:600 23px/1.28 Georgia,'Times New Roman',serif;margin:0 0 14px;color:#141821">${esc(title)}</h1>
${bodyHtml}
</td></tr>
<tr><td style="padding:18px 24px 22px;background:#f7f8fb;border-top:1px solid #e9ecf2;font-size:12px;line-height:1.5;color:#6b7385">${foot}</td></tr>
</table></td></tr></table></body></html>`;
}

/** A violet call-to-action button for emails. */
export const button = (href, label) =>
  `<p style="margin:20px 0 22px"><a href="${esc(href)}" style="display:inline-block;background:#7c6cf5;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:600">${esc(label)}</a></p>`;
