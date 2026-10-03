/* member-alerts.mjs: the nightly email to members about their own stocks.
 *
 * Runs on a schedule after the nightly refresh and rebuild (prices are
 * committed at 21:45 UTC and the site rebuilds from them). For each member list
 * saved from /watchlist/ (store "qm-lists") it compares the new close with the
 * one it saw last time (store "qm-snap") and emails one digest when, on a
 * listed stock:
 *   - a core play got in or got out,
 *   - the price came within 2% of a core play's entry or exit level,
 *   - its crash exposure level changed, or
 *   - it moved 5% or more on the day.
 * The first night after a list is saved only records where things stand.
 * Subscribers get it at their PayPal email while the subscription is active;
 * the password member gets it at QM_OWNER_EMAIL if that is set.
 * Needs RESEND_API_KEY (netlify/lib/mail.mjs); without it nothing is sent.
 */
import { getStore } from "@netlify/blobs";
import { env, activeRecord, siteUrl } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { compare, digest } from "../lib/alerts.mjs";

export default async () => {
  if (!mail.configured()) {
    console.log("member-alerts: RESEND_API_KEY not set, nothing to send");
    return;
  }
  const r = await fetch(siteUrl() + "/data/watch.json", { cache: "no-store" });
  if (!r.ok) throw new Error("watch.json " + r.status);
  const D = await r.json();
  const lists = getStore({ name: "qm-lists", consistency: "strong" });
  const snaps = getStore({ name: "qm-snap", consistency: "strong" });
  const members = getStore({ name: "qm-members", consistency: "strong" });
  const { blobs } = await lists.list();
  let sent = 0;
  for (const b of blobs) {
    const id = b.key;
    const L = await lists.get(id, { type: "json" });
    if (!L || L.alerts === false || !(L.tickers || []).length) continue;
    let email = "";
    if (id === "owner") email = env("QM_OWNER_EMAIL");
    else {
      const rec = await members.get("sub/" + id, { type: "json" });
      if (!activeRecord(rec)) continue;
      email = rec.email;
    }
    if (!email) continue;
    const prev = await snaps.get(id, { type: "json" });
    if (prev && prev.asof === D.asof) continue;          // this close is done already
    const { snap, changes } = compare(D, L.tickers, prev);
    if (changes.length) {
      const m = digest(D, changes);
      const res = await mail.send(email, m.subject, m.html, m.text);
      if (!res.ok) { console.error("member-alerts: send failed", res.status); continue; }
      sent++;
    }
    await snaps.setJSON(id, snap);
  }
  console.log(`member-alerts: ${blobs.length} lists, ${sent} emails, close ${D.asof}`);
};

// after the 21:45 UTC price refresh and the rebuild it triggers
export const config = { schedule: "40 23 * * *" };
