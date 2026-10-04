/* paypal.mjs: the few PayPal REST calls Be The Puck Members needs.
 * Env: PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_PLAN_ID, PAYPAL_WEBHOOK_ID,
 *      PAYPAL_ENV ("sandbox" for testing, anything else is live).
 */
import { env } from "./qm.mjs";

const base = () => (env("PAYPAL_ENV") === "sandbox" ? "https://api-m.sandbox.paypal.com" : "https://api-m.paypal.com");
export const configured = () => !!(env("PAYPAL_CLIENT_ID") && env("PAYPAL_CLIENT_SECRET") && env("PAYPAL_PLAN_ID"));

async function token() {
  const auth = Buffer.from(env("PAYPAL_CLIENT_ID") + ":" + env("PAYPAL_CLIENT_SECRET")).toString("base64");
  const r = await fetch(base() + "/v1/oauth2/token", {
    method: "POST",
    headers: { authorization: "Basic " + auth, "content-type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
  });
  if (!r.ok) throw new Error("paypal auth " + r.status);
  return (await r.json()).access_token;
}

export async function getSubscription(id) {
  if (!/^I-[A-Z0-9]{6,40}$/.test(String(id || ""))) return null;
  const r = await fetch(base() + "/v1/billing/subscriptions/" + encodeURIComponent(id), {
    headers: { authorization: "Bearer " + (await token()), "content-type": "application/json" },
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("paypal subscription " + r.status);
  return r.json();
}

/** The member record Be The Puck keeps for a subscription. */
export function recordFrom(sub, prev = {}) {
  const s = sub.subscriber || {};
  const name = s.name ? [s.name.given_name, s.name.surname].filter(Boolean).join(" ") : "";
  const next = sub.billing_info && sub.billing_info.next_billing_time;
  return {
    ...prev,
    id: sub.id,
    plan: sub.plan_id,
    status: sub.status,
    email: (s.email_address || prev.email || "").toLowerCase(),
    name: name || prev.name || "",
    // access runs to the end of the period paid for, even after a cancel
    paid_through: next || prev.paid_through || null,
    created: prev.created || sub.create_time || new Date().toISOString(),
    checked: new Date().toISOString(),
  };
}

/** PayPal's own check that a webhook came from PayPal. */
export async function verifyWebhook(req, rawBody) {
  const id = env("PAYPAL_WEBHOOK_ID");
  if (!id) return false;
  const h = (k) => req.headers.get(k);
  let event;
  try { event = JSON.parse(rawBody); } catch (e) { return false; }
  const r = await fetch(base() + "/v1/notifications/verify-webhook-signature", {
    method: "POST",
    headers: { authorization: "Bearer " + (await token()), "content-type": "application/json" },
    body: JSON.stringify({
      auth_algo: h("paypal-auth-algo"), cert_url: h("paypal-cert-url"), transmission_id: h("paypal-transmission-id"),
      transmission_sig: h("paypal-transmission-sig"), transmission_time: h("paypal-transmission-time"),
      webhook_id: id, webhook_event: event,
    }),
  });
  if (!r.ok) return false;
  return (await r.json()).verification_status === "SUCCESS";
}
