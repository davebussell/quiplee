/* alerts-nightly.mjs: emails free subscribers when the Start/Stop light flips.
 *
 * Runs every hour. It does nothing until /data/reads.json carries a new close
 * (the nightly price refresh lands at a different time each night), then:
 *   1. sends any confirm links that couldn't go out when people signed up, and
 *   2. for every confirmed subscriber, compares each stock's light with the one
 *      last emailed (last[SYM]) and sends one email listing every flip.
 * A stock seen for the first time only records its light. Needs RESEND_API_KEY.
 */
import { getStore } from "@netlify/blobs";
import { siteUrl } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { STORE, confirmEmail, flipEmail, sendAll } from "../lib/freealerts.mjs";

export default async () => {
  if (!mail.configured()) {
    console.log("alerts-nightly: RESEND_API_KEY not set, nothing to send");
    return;
  }
  const r = await fetch(siteUrl() + "/data/reads.json", { cache: "no-store" });
  if (!r.ok) throw new Error("reads.json " + r.status);
  const R = await r.json();
  const s = getStore({ name: STORE, consistency: "strong" });
  const state = (await s.get("state", { type: "json" })) || {};
  const fresh = R.asof && R.asof !== state.asof;

  const keys = [];
  for await (const page of s.list({ prefix: "sub/", paginate: true })) keys.push(...page.blobs.map((b) => b.key));
  const msgs = [], writes = [];
  for (let i = 0; i < keys.length; i += 25) {
    const recs = await Promise.all(keys.slice(i, i + 25).map((k) => s.get(k, { type: "json" }).catch(() => null)));
    recs.forEach((rec, j) => {
      if (!rec) return;
      const id = keys[i + j].slice(4);
      if (!rec.confirm_sent && (!rec.confirmed || rec.pending)) {
        msgs.push(confirmEmail(id, rec.email, rec.pending || rec.tickers, R));
        rec.confirm_sent = new Date().toISOString();
        writes.push([keys[i + j], rec]);
        return;
      }
      if (!fresh || !rec.confirmed) return;
      const last = rec.last || {};
      const flips = [];
      let changed = false;
      for (const sym of rec.tickers || []) {
        const t = R.t[sym];
        if (!t || t.L == null) continue;
        const now = [t.L, t.k, t.of];
        if (!last[sym]) { last[sym] = now; changed = true; continue; }
        if (last[sym][0] !== t.L) flips.push({ sym, t, was: last[sym] });
        if (last[sym][0] !== t.L || last[sym][1] !== t.k) { last[sym] = now; changed = true; }
      }
      if (flips.length) {
        msgs.push(flipEmail(id, rec.email, flips, R));
        rec.sent = (rec.sent || 0) + 1;
        rec.last_sent = R.asof;
      }
      if (changed || flips.length) { rec.last = last; writes.push([keys[i + j], rec]); }
    });
  }
  const { sent } = await sendAll(msgs);
  for (let i = 0; i < writes.length; i += 25) await Promise.all(writes.slice(i, i + 25).map(([k, v]) => s.setJSON(k, v)));
  if (fresh) await s.setJSON("state", { asof: R.asof, run: new Date().toISOString(), emails: sent, subs: keys.length });
  console.log(`alerts-nightly: ${keys.length} subscribers, ${msgs.length} emails queued, ${sent} sent, close ${R.asof}${fresh ? "" : " (already done)"}`);
};

export const config = { schedule: "20 * * * *" };
