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

/** A plain, dark-on-light email shell (mail clients ignore most CSS). */
export function shell(title, bodyHtml, footer) {
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#f4f5f8;font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;color:#141821">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;border:1px solid #e3e6ee">
<p style="margin:0 0 14px;font-weight:800;font-size:18px">be<span style="color:#6b7385;font-weight:600">the</span>puck<span style="color:#1fa274">&#9650;</span></p>
<h1 style="font:600 21px/1.3 Georgia,serif;margin:0 0 14px">${esc(title)}</h1>
${bodyHtml}
<p style="margin:22px 0 0;font-size:12px;color:#6b7385">${footer || "Education, not financial advice. Be The Puck reports what published trading rules say; it doesn't know your goals, taxes or timeline."}</p>
</div></body></html>`;
}
