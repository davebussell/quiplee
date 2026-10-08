/* alerts-nightly.mjs: emails free subscribers when the Start/Stop light flips.
 *
 * Runs every hour. It does nothing until /data/reads.json carries a new close
 * (the nightly price refresh lands at a different time each night), then:
 *   1. sends any confirm links that couldn't go out when people signed up, and
 *   2. for every confirmed subscriber, compares each stock's light with the one
 *      last emailed (last[SYM]) and sends one email listing every flip.
 * A stock seen for the first time only records its light. Needs RESEND_API_KEY.
 *
 * Then the same for Be The Puck accounts (netlify/lib/account.mjs): pending confirm
 * links, and one "your stocks tonight" email per account with alerts on, listing
 * Start/Stop flips and, at level "all" while member tools are open to the account,
 * every play that got in or out on the stocks it follows (lib/alerts.mjs compare).
 * What was last emailed sits in the paper store under as/<name>.
 */
import { getStore } from "@netlify/blobs";
import { siteUrl } from "../lib/qm.mjs";
import * as mail from "../lib/mail.mjs";
import { STORE, confirmEmail, flipEmail, sendAll } from "../lib/freealerts.mjs";
import { compare } from "../lib/alerts.mjs";
import { store as acctStore, membership, updateAccount } from "../lib/account.mjs";
import { confirmMsg, nightlyMsg } from "../lib/accountmail.mjs";

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
        msgs.push(confirmEmail(id, rec.email, rec.pending || rec.tickers, R, rec.pending ? rec.pending_weekly : rec.weekly));
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
  const acc = await accounts(R, fresh);
  const { sent } = await sendAll(msgs.concat(acc.msgs));
  for (let i = 0; i < writes.length; i += 25) await Promise.all(writes.slice(i, i + 25).map(([k, v]) => s.setJSON(k, v)));
  // account records are patched (the player may be editing them right now); snapshots are written whole
  for (let i = 0; i < acc.writes.length; i += 25) {
    await Promise.all(acc.writes.slice(i, i + 25).map(([k, v, how]) => (how === "patch" ? updateAccount(acc.s, k, (a) => ({ ...a, ...v })) : acc.s.setJSON(k, v))));
  }
  if (fresh) await s.setJSON("state", { asof: R.asof, run: new Date().toISOString(), emails: sent, subs: keys.length, accounts: acc.n });
  console.log(`alerts-nightly: ${keys.length} subscribers, ${acc.n} accounts, ${msgs.length + acc.msgs.length} emails queued, ${sent} sent, close ${R.asof}${fresh ? "" : " (already done)"}`);
};

/** Accounts: confirm links still owed, and tonight's email for each account with alerts on. */
async function accounts(R, fresh) {
  const s = acctStore();
  const keys = [];
  for await (const page of s.list({ prefix: "u/", paginate: true })) keys.push(...page.blobs.map((b) => b.key));
  const msgs = [], writes = [];
  let D = null;
  for (let i = 0; i < keys.length; i += 25) {
    const recs = await Promise.all(keys.slice(i, i + 25).map((k) => s.get(k, { type: "json" }).catch(() => null)));
    for (let j = 0; j < recs.length; j++) {
      const acct = recs[j];
      if (!acct || !acct.email) continue;
      const u = keys[i + j].slice(2);
      if (!acct.email_ok && !acct.confirm_sent) {
        msgs.push(confirmMsg(u, acct));
        writes.push([u, { confirm_sent: new Date().toISOString() }, "patch"]);
        continue;
      }
      const al = acct.alerts || { on: false, level: "all" };
      if (!fresh || !acct.email_ok || al.on !== true || !(acct.follow || []).length) continue;
      const snap = (await s.get("as/" + u, { type: "json" }).catch(() => null)) || {};
      if (snap.asof === R.asof) continue;
      const L = {}, flips = [];
      for (const sym of acct.follow) {
        const t = R.t[sym];
        if (!t || t.L == null) continue;
        const last = snap.L && snap.L[sym];
        if (last && last[0] !== t.L) flips.push({ sym, t, was: last });
        L[sym] = [t.L, t.k, t.of];
      }
      let plays = [], psnap = snap.p || null;
      const member = membership(acct).active;
      if (al.level !== "light" && member) {
        if (!D) {
          const r = await fetch(siteUrl() + "/data/watch.json", { cache: "no-store" });
          D = r.ok ? await r.json() : { plays: [], t: {} };
        }
        const cmp = compare(D, acct.follow, snap.p || null);
        plays = cmp.changes.map((c) => ({ ...c, items: c.items.filter((x) => x.kind === "in" || x.kind === "out" || x.kind === "near") })).filter((c) => c.items.length);
        psnap = cmp.snap;
      }
      if (snap.asof && (flips.length || plays.length)) {
        msgs.push(nightlyMsg(u, acct, flips, plays, R, member && al.level !== "light"));
        writes.push([u, { last_sent: R.asof }, "patch"]);
      }
      writes.push(["as/" + u, { asof: R.asof, L, p: psnap }]);
    }
  }
  return { s, msgs, writes, n: keys.length };
}

export const config = { schedule: "20 * * * *" };
