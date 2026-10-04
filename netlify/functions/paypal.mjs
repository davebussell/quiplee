/* paypal.mjs: PayPal subscriptions for Be The Puck Members ($5 a month).
 *
 * POST /api/paypal/subscribed {subscriptionID}
 *   Called by the PayPal button on /members/ after the buyer approves. Checks the
 *   subscription with PayPal (right plan, active), stores the member record,
 *   signs the buyer in on this device and emails a welcome with a sign-in link.
 * POST /api/paypal/webhook
 *   PayPal's notifications (verified with PayPal before use): cancellations,
 *   suspensions, expiries and renewals update the member record. Access lasts
 *   to the end of the period already paid for.
 *
 * Member records live in Netlify Blobs, store "qm-members":
 *   sub/<subscription id>   {id, plan, status, email, name, paid_through, created, checked}
 *   email/<hashed email>    <subscription id>   (for "email me a sign-in link")
 */
import { getStore } from "@netlify/blobs";
import { env, now, DAY, SUB_DAYS, COOKIE_DAYS, sign, setCookie, hashId, json, activeRecord, linkFor, siteUrl } from "../lib/qm.mjs";
import * as paypal from "../lib/paypal.mjs";
import * as mail from "../lib/mail.mjs";

const members = () => getStore({ name: "qm-members", consistency: "strong" });

async function save(rec) {
  const s = members();
  await s.setJSON("sub/" + rec.id, rec);
  if (rec.email) await s.set("email/" + hashId(rec.email, env("QM_SECRET")), rec.id);
}

async function welcome(rec) {
  if (!rec.email || rec.welcomed) return rec;
  const link = linkFor(rec.id);
  const base = siteUrl();
  const r = await mail.send(rec.email, "Welcome to Be The Puck Members",
    mail.shell("Welcome to Be The Puck Members", `<p>Thanks for joining${rec.name ? ", " + mail.esc(rec.name.split(" ")[0]) : ""}. You're signed in on the device you joined from. On any other device, use this link (it works for 7 days; you can ask for a fresh one on the members page any time):</p>
<p style="margin:18px 0"><a href="${mail.esc(link)}" style="background:#7c6cf5;color:#fff;padding:11px 18px;border-radius:9px;text-decoration:none;font-weight:600">Sign in</a></p>
<ul style="padding-left:18px">
<li><a href="${base}/picks/">The top-picks tracker</a>: five rule-based picks, reviewed after every Friday close.</li>
<li><a href="${base}/articles/">The reports</a>: long reads, sector pieces and a brief on every covered stock.</li>
<li><a href="${base}/watchlist/">Your watchlist</a>: save your stocks there and Be The Puck emails you after the close when a play flips on one of them.</li>
</ul>
<p style="font-size:13px;color:#6b7385">$5 a month through PayPal. Cancel any time from your PayPal account (Settings, Payments, Automatic payments); access runs to the end of the month you paid for.</p>`),
    `Welcome to Be The Puck Members. Sign in on another device: ${link}`);
  return r.ok ? { ...rec, welcomed: new Date().toISOString() } : rec;
}

async function subscribed(req) {
  if (!paypal.configured() || !env("QM_SECRET")) return json({ ok: false, error: "Subscriptions aren't switched on yet." }, 503);
  let body = {};
  try { body = await req.json(); } catch (e) { /* empty */ }
  const id = String(body.subscriptionID || "");
  const sub = await paypal.getSubscription(id);
  if (!sub) return json({ ok: false, error: "PayPal doesn't know that subscription." }, 404);
  if (sub.plan_id !== env("PAYPAL_PLAN_ID")) return json({ ok: false, error: "That subscription is for a different plan." }, 400);
  if (!["ACTIVE", "APPROVED"].includes(sub.status)) return json({ ok: false, error: "PayPal hasn't activated the subscription yet. Refresh in a minute." }, 409);
  const prev = (await members().get("sub/" + id, { type: "json" })) || {};
  let rec = paypal.recordFrom(sub, prev);
  if (rec.status === "APPROVED") rec.status = "ACTIVE";
  rec = await welcome(rec);
  await save(rec);
  const t = now();
  return json({ ok: true }, 200, setCookie(sign({ k: "sub", id, iat: t, exp: t + SUB_DAYS * DAY }, env("QM_SECRET")), COOKIE_DAYS));
}

async function webhook(req) {
  const raw = await req.text();
  if (!paypal.configured()) return json({ ok: false }, 503);
  if (!(await paypal.verifyWebhook(req, raw))) return json({ ok: false }, 400);
  const ev = JSON.parse(raw);
  const type = ev.event_type || "";
  const res = ev.resource || {};
  // subscription events carry the subscription; payment events carry its id
  const id = type.startsWith("BILLING.SUBSCRIPTION") ? res.id : res.billing_agreement_id;
  if (!id) return json({ ok: true, ignored: type });
  const sub = await paypal.getSubscription(id);
  if (!sub || sub.plan_id !== env("PAYPAL_PLAN_ID")) return json({ ok: true, ignored: "plan" });
  const prev = (await members().get("sub/" + id, { type: "json" })) || {};
  let rec = paypal.recordFrom(sub, prev);
  if (type === "BILLING.SUBSCRIPTION.ACTIVATED") rec = await welcome(rec);
  await save(rec);
  return json({ ok: true, status: rec.status, active: activeRecord(rec) });
}

export default async (req) => {
  const route = new URL(req.url).pathname.replace(/\/+$/, "").split("/").pop();
  if (req.method !== "POST") return json({ error: "Not found" }, 404);
  try {
    if (route === "subscribed") return await subscribed(req);
    if (route === "webhook") return await webhook(req);
  } catch (e) {
    console.error("paypal", route, e && e.message);
    return json({ ok: false, error: "We couldn't reach PayPal. Your subscription is safe; refresh in a minute." }, 502);
  }
  return json({ error: "Not found" }, 404);
};

export const config = { path: ["/api/paypal/subscribed", "/api/paypal/webhook"] };
