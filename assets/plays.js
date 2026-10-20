/* plays.js: the play filter every dashboard shares (window.BPPlays).
 *
 * A reader picks which of the plays count. The home screener, the stock list (Plays in,
 * Score, the family board), each stock page, the watchlist and My Puck then count only
 * those. The choice is {p: "all"|"top1"|"top3"|"half"|"custom", s: [slugs for custom]}:
 *   - kept in this browser (localStorage) and, when signed in, on the account (/api/account/plays)
 *   - ?plays=top1|top3|half|all, or slugs joined by ".", applies a shared view for one visit
 * Data: data/playset.json (tools/qstrat/playset.py): every play's share of calls right on the
 * real stocks, whether it can be ranked, and every covered name's call on every play.
 *
 * Your signal: the reader also weights factors (plays in, analysts, P/E and other value
 * measures, growth and quality, trend, momentum, crash exposure; tools/qstrat/factors.py).
 * A stock's score is the weighted average of its points (0-100) on the weighted factors it
 * has; Buy at or above the buy line, Sell at or below the sell line, Hold between. Kept like
 * the plays ({w: {factor: weight}, buy, sell}), and ?w=plays50.pe20&buy=60&sell=40 shares a view.
 *
 * Markup it looks after on any page:
 *   [data-ps-open]      opens the chooser (="weights" on the weights tab)
 *   [data-ps-label]     the plays choice, short    [data-ps-wlabel]  the weights, short
 *   [data-ps-set=top1]  applies a ready-made set   [data-ps-toggle=slug] a checkbox for one play
 *   tr[data-sym|data-ps-row] with td[data-ps-plays] / td[data-ps-scorecell] / td[data-ps-signal] / td[data-ps-fam=k]:
 *                       recounted for the choice, and the table re-sorted */
(function () {
  'use strict';
  if (window.BPPlays) return;
  var KEY = 'bp.plays.v1', WKEY = 'bp.signal.v1';
  var me = document.currentScript, src = (me && me.src) || '';
  var ver = (src.split('?v=')[1] || '');
  var DATA_URL = src.replace(/assets\/plays\.js(\?.*)?$/, 'data/playset.json') + (ver ? '?v=' + ver : '');
  var GUIDE = src.replace(/assets\/plays\.js(\?.*)?$/, 'guides/your-plays/');
  var NAME = { all: 'All plays', top1: 'Most accurate in each family', top3: 'Top 3 in each family', half: 'Right more than half the time', custom: 'Your own pick' };
  var SIG_WORD = { '1': 'Buy', '0': 'Hold', '-1': 'Sell' }, SIG_CLS = { '1': 'buy', '0': 'hold', '-1': 'sell' };
  var D = null, IDX = {}, FAMI = {}, FXI = {}, sel = null, choice = { p: 'all', s: [] }, origin = 'default';
  var wts = null, worigin = 'default', tab = 'plays', migrated = false;
  var subs = [], waiting = [], here = null, sortBy = 'acc', ov = null, opener = null, saveT = null, wsaveT = null;

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pc(v) { return v == null ? '–' : Math.round(v * 100) + '%'; }
  function num(v) { return Number(v).toLocaleString('en-US'); }
  function lsGet(k) { try { return JSON.parse(localStorage.getItem(k || KEY) || 'null'); } catch (e) { return null; } }
  function lsSet(v, k) { try { localStorage.setItem(k || KEY, JSON.stringify(v)); } catch (e) { /* private mode */ } }
  function auth() { return window.BPAuth && window.BPAuth.signedIn() ? window.BPAuth : null; }

  function clean(c) {
    if (!c || typeof c !== 'object') return null;
    var p = NAME[c.p] ? c.p : 'custom';
    var s = Array.isArray(c.s) ? c.s.filter(function (x) { return typeof x === 'string' && /^[a-z0-9-]{1,48}$/.test(x); }).slice(0, 300) : [];
    if (p === 'custom' && !s.length) p = 'all';
    return { p: p, s: p === 'custom' ? s : [] };
  }
  function fromParam(v) {
    if (!v) return null;
    if (NAME[v] && v !== 'custom') return { p: v, s: [] };
    return clean({ p: 'custom', s: v.split(/[.,]/) });
  }

  // ------------------------------------------------------------ your signal: weights, lines and the score
  function cleanW(c) {
    if (!c || typeof c !== 'object' || !D) return null;
    var w = {}, any = false;
    D.fx.forEach(function (f) { var v = c.w && +c.w[f.k]; if (v > 0) { w[f.k] = Math.min(100, Math.round(v)); any = true; } });
    if (!any) w = Object.assign({}, D.wd.w);
    var buy = Math.min(95, Math.max(50, Math.round(+c.buy || D.wd.buy)));
    var sell = Math.min(buy - 5, Math.max(5, Math.round(+c.sell || D.wd.sell)));
    return { w: w, buy: buy, sell: sell, mv: D.mv || 1 };
  }
  // weights saved before the standard changed (model version D.mv) that were simply the old
  // standard move to the new one; anything the reader set themselves is kept
  function migrate(c) {
    if (!c || !D || !D.wo || (c.mv || 1) >= (D.mv || 1) || !sameW(c.w, D.wo)) return c;
    migrated = true;
    return { w: Object.assign({}, D.wd.w), buy: c.buy, sell: c.sell, mv: D.mv };
  }
  // signal changes since this browser last looked: {since: the earlier close, list: [{sym, from, to, s}]}.
  // Kept per page (scope) and reset whenever the reader's weights or plays change, so only the
  // market can produce a "change". A reload on the same close shows the same list again.
  function changes(scope, syms) {
    if (!D || !wts) return null;
    var key = JSON.stringify([D.mv || 1, Object.keys(wts.w).sort().map(function (k) { return k + wts.w[k]; }), wts.buy, wts.sell, choice.p, (choice.s || []).join('.')]);
    var store = 'bp.seen.' + scope, seen = lsGet(store) || {}, same = seen.key === key;
    if (same && seen.asof === D.asof) return { since: seen.since || null, list: seen.last || [] };
    var out = [], sig = {};
    syms.forEach(function (sym) {
      var r = score(sym);
      if (r.sig == null) return;
      sig[sym] = r.sig;
      var was = same && seen.sig ? seen.sig[sym] : undefined;
      if (was != null && was !== r.sig) out.push({ sym: sym, from: was, to: r.sig, s: r.s });
    });
    var since = same ? seen.asof : null;
    lsSet({ key: key, asof: D.asof, since: since, sig: sig, last: out }, store);
    return { since: since, list: out };
  }
  // how much of a score rests on factors with a track record (factorgrade.py), 0 to 1
  function tested(parts) {
    var a = 0, g = 0;
    parts.forEach(function (q) { if (q.p == null) return; a += q.w; var f = D.fx[FXI[q.k]]; if (f && f.r && !f.r.why) g += q.w; });
    return a ? g / a : null;
  }
  function wFromParam(q) {
    var v = q.get('w');
    if (!v && !q.get('buy') && !q.get('sell')) return null;
    var w = {};
    (v || '').split(/[.,]/).forEach(function (x) { var m = x.match(/^([a-z]+)(\d+)$/); if (m) w[m[1]] = +m[2]; });
    return cleanW({ w: v ? w : (wts || D.wd).w, buy: q.get('buy'), sell: q.get('sell') });
  }
  function sameW(a, b) {
    var ka = Object.keys(a).filter(function (k) { return a[k] > 0; }), kb = Object.keys(b).filter(function (k) { return b[k] > 0; });
    if (ka.length !== kb.length) return false;
    // weights that differ only in scale give the same score
    var r = null;
    for (var i = 0; i < ka.length; i++) { var k = ka[i]; if (!b[k]) return false; var x = a[k] / b[k]; if (r == null) r = x; else if (Math.abs(x - r) > 1e-9) return false; }
    return true;
  }
  function wPreset() { for (var i = 0; i < D.wp.length; i++) if (sameW(wts.w, D.wp[i].w)) return D.wp[i]; return null; }
  function wlabel() { if (!D || !wts) return 'Plays + exit rules'; var p = wPreset(); return p ? p.n : 'Your weights'; }
  function isDefaultW() { return !wts || (sameW(wts.w, D.wd.w) && wts.buy === D.wd.buy && wts.sell === D.wd.sell); }
  /** A name's score with the reader's weights: {s: 0-100 or null, sig: 1|0|-1|null, parts: [{k, n, v, p, w, add}], cov}. */
  function score(sym, wIn) {
    var W = (wIn || wts || D.wd), w = W.w, x = D.x[sym], v = D.v[sym], tot = 0, avail = 0, acc = 0, parts = [];
    if (!x) return { s: null, sig: null, parts: [], cov: 0 };
    D.fx.forEach(function (f, i) {
      var wi = w[f.k] || 0;
      if (!wi) return;
      tot += wi;
      var p = x[i], val = v[i];
      if (f.k === 'plays') { var c = count(sym); p = c.n ? Math.round(100 * c.k / c.n) : null; val = p == null ? null : p + '%'; }
      parts.push({ k: f.k, n: f.n, v: val, p: p, w: wi, add: null });
      if (p != null) { avail += wi; acc += wi * p; }
    });
    if (!tot || avail < tot / 2) return { s: null, sig: null, parts: parts, cov: tot ? avail / tot : 0 };
    var s = Math.round(acc / avail);
    parts.forEach(function (q) { if (q.p != null) q.add = Math.round(10 * q.w * q.p / avail) / 10; });
    return { s: s, sig: s >= W.buy ? 1 : s <= W.sell ? -1 : 0, parts: parts, cov: avail / tot };
  }
  // ---------------------------------------------------------------- the price that would change the signal's mind
  // The same arithmetic as factors.flip_lines: re-score a candidate price with the plays and company numbers held
  // where they are; off the high, trend, momentum and analysts' upside move with the price.
  function offPts(dd) { return Math.round(100 * Math.min(Math.max(1 + dd / 0.30, 0), 1)); }
  function rankAt(v, vals, own) {
    var lo = 0, hi = 0, n = 0, skipped = false;
    for (var i = 0; i < vals.length; i++) {
      if (!skipped && own != null && vals[i] === own) { skipped = true; continue; }
      n++;
      if (vals[i] < v) lo++; else if (vals[i] === v) hi++;
    }
    n++;                                            // this stock
    if (n <= 1) return 50;
    var r = lo + 1 + hi / 2;
    return Math.round(100 * (r - 1) / (n - 1));
  }
  function upPtsAt(u) { return Math.round(100 * (Math.min(Math.max(u, -0.2), 0.5) + 0.2) / 0.7); }
  function flips(sym, wIn) {
    var W = (wIn || wts || D.wd), w = W.w, x = D.x[sym], pin = D.pi && D.pi[sym];
    if (!x || !pin || !pin.p || !D.rk) return null;
    var c = count(sym), plays = c.n ? Math.round(100 * c.k / c.n) : null;
    function sigAt(price) {
      var tot = 0, avail = 0, acc = 0;
      D.fx.forEach(function (f, i) {
        var wi = w[f.k] || 0;
        if (!wi) return;
        tot += wi;
        var p = x[i];
        if (f.k === 'plays') p = plays;
        else if (f.k === 'offhigh' && pin.hi) p = offPts(price / Math.max(pin.hi, price) - 1);
        else if (f.k === 'trend' && pin.ma) p = rankAt(price / pin.ma - 1, D.rk.trend, pin.gap);
        else if (f.k === 'mom' && pin.py) p = rankAt(price / pin.py - 1, D.rk.mom, pin.y1);
        else if (f.k === 'upside' && pin.tgt) {
          var u = pin.tgt / price - 1;
          p = u <= 1 ? upPtsAt(u) : null;
          if (p != null && pin.ma && price < pin.ma && p > (D.uc || 50)) p = D.uc || 50;
        }
        if (p != null) { avail += wi; acc += wi * p; }
      });
      if (!tot || avail < tot / 2) return null;
      var s = Math.round(acc / avail);
      return s >= W.buy ? 1 : s <= W.sell ? -1 : 0;
    }
    var p0 = pin.p, now = sigAt(p0), out = { now: now, down: null, up: null }, i, px, sg;
    if (now == null) return null;
    for (i = 1; i <= 80; i++) { px = p0 * (1 - i * 0.005); sg = sigAt(px); if (sg != null && sg !== now) { out.down = [px, sg]; break; } }
    for (i = 1; i <= 160; i++) { px = p0 * (1 + i * 0.005); sg = sigAt(px); if (sg != null && sg !== now) { out.up = [px, sg]; break; } }
    return out;
  }
  function flipWords(fl, cur, p0) {
    if (!fl) return '';
    var bits = [];
    [['down', 'below'], ['up', 'above']].forEach(function (z) {
      var x = fl[z[0]];
      if (!x) return;
      var pct = x[0] / p0 - 1;
      bits.push('turns ' + SIG_WORD[x[1]] + ' ' + z[1] + ' ' + (cur || '$') + x[0].toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
        ' (' + (pct > 0 ? '+' : '\u2212') + Math.round(Math.abs(pct) * 100) + '%)');
    });
    if (!bits.length) return 'Stays ' + SIG_WORD[fl.now] + ' anywhere from 40% below to 80% above the latest close.';
    var out = bits.join(' \u00b7 ');
    return out.charAt(0).toUpperCase() + out.slice(1);
  }
  function sigPill(sig) { return sig == null ? '<span class="sig-pill na">–</span>' : '<span class="sig-pill ' + SIG_CLS[sig] + '">' + SIG_WORD[sig] + '</span>'; }
  function applyW(c, why) {
    c = cleanW(c) || cleanW(D.wd);
    wts = c;
    if (why === 'user') {
      worigin = 'user';
      lsSet(c, WKEY);
      var A = auth();
      if (A) { clearTimeout(wsaveT); wsaveT = setTimeout(function () { A.post('plays', { signal: c }).catch(function () {}); }, 800); }
      var q = new URLSearchParams(location.search);
      if (q.has('w') || q.has('buy') || q.has('sell')) {
        q.set('w', Object.keys(c.w).map(function (k) { return k + c.w[k]; }).join('.')); q.set('buy', c.buy); q.set('sell', c.sell);
        history.replaceState(null, '', location.pathname + '?' + q.toString() + location.hash);
      }
    }
    paint(true);
    subs.forEach(function (f) { try { f(choice); } catch (e) { /* one widget must not stop the rest */ } });
  }

  // ------------------------------------------------------------ which plays a choice counts (0/1 over D.plays)
  function resolve(c) {
    var n = D.plays.length, out = new Uint8Array(n), i, any = false;
    if (c.p === 'all') { for (i = 0; i < n; i++) out[i] = 1; return out; }
    if (c.p === 'half') D.plays.forEach(function (p, i) { if (p.e && p.a != null && p.a > 0.5) out[i] = 1; });
    else if (c.p === 'top1' || c.p === 'top3') {
      var per = c.p === 'top1' ? 1 : 3;
      D.fams.forEach(function (f) {
        var ix = [];
        D.plays.forEach(function (p, i) { if (p.f === f[0] && p.e) ix.push(i); });
        ix.sort(function (a, b) { return D.plays[b].a - D.plays[a].a || D.plays[b].c - D.plays[a].c; });
        ix.slice(0, per).forEach(function (i) { out[i] = 1; });
      });
    } else c.s.forEach(function (s) { if (IDX[s] != null) out[IDX[s]] = 1; });
    for (i = 0; i < n; i++) if (out[i]) { any = true; break; }
    if (!any) for (i = 0; i < n; i++) out[i] = 1;
    return out;
  }
  function same(a, b) { for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false; return true; }
  // a hand-picked set that happens to match a ready-made one is called by its name
  function normal(c) {
    if (c.p !== 'custom') return c;
    var mine = resolve(c), ps = ['all', 'top1', 'top3', 'half'];
    for (var j = 0; j < ps.length; j++) if (same(mine, resolve({ p: ps[j], s: [] }))) return { p: ps[j], s: [] };
    return c;
  }
  function size() { var k = 0; if (sel) for (var i = 0; i < sel.length; i++) k += sel[i]; return k; }

  // ------------------------------------------------------------ counting a name
  function count(sym) {
    var st = D && D.t[sym];
    var r = { k: 0, n: 0, f: D ? D.fams.map(function () { return [0, 0]; }) : [], w: null };
    if (!st || !sel) return r;
    var wk = 0, wn = 0;
    for (var i = 0; i < st.length; i++) {
      if (!sel[i]) continue;
      var ch = st.charAt(i);
      if (ch === '-') continue;
      var fi = FAMI[D.plays[i].f], a = D.plays[i].a || 0;
      r.n++; r.f[fi][1]++; wn += a;
      if (ch === '1') { r.k++; r.f[fi][0]++; wk += a; }
    }
    r.w = wn ? wk / wn : null;
    return r;
  }

  // ------------------------------------------------------------ labels
  function label(long) {
    if (!D) return 'All';
    var n = size(), N = D.plays.length;
    if (choice.p === 'all') return long ? 'All ' + N + ' plays' : 'All ' + N;
    if (choice.p === 'custom') return long ? 'Your ' + n + ' plays' : 'Your ' + n;
    return long ? NAME[choice.p] + ' (' + n + ')' : NAME[choice.p] + ' · ' + n;
  }

  // ------------------------------------------------------------ applying a choice
  function apply(c, why) {
    c = normal(clean(c) || { p: 'all', s: [] });
    choice = c;
    sel = resolve(c);
    if (why === 'user') {
      origin = 'user';
      lsSet(c);
      var A = auth();
      if (A) { clearTimeout(saveT); saveT = setTimeout(function () { A.post('plays', { plays: c }).catch(function () {}); }, 600); }
      var q = new URLSearchParams(location.search);
      if (q.has('plays')) { q.set('plays', c.p === 'custom' ? c.s.join('.') : c.p); history.replaceState(null, '', location.pathname + '?' + q.toString() + location.hash); }
    }
    paint();
    subs.forEach(function (f) { try { f(c); } catch (e) { /* one widget must not stop the rest */ } });
  }
  function current() { var out = []; if (sel) D.plays.forEach(function (p, i) { if (sel[i]) out.push(p.s); }); return out; }
  function toggle(slug, on) {
    if (IDX[slug] == null) return;
    var s = current().filter(function (x) { return x !== slug; });
    if (on) s.push(slug);
    if (!s.length) return false;        // keep at least one play
    apply({ p: 'custom', s: s }, 'user');
    return true;
  }
  function setFam(fk, on) {
    var s = current().filter(function (x) { return D.plays[IDX[x]].f !== fk; });
    if (on) D.plays.forEach(function (p) { if (p.f === fk) s.push(p.s); });
    if (!s.length) return false;
    apply({ p: 'custom', s: s }, 'user');
    return true;
  }

  // ------------------------------------------------------------ the page: labels, buttons and counted tables
  function consensus(k, n) {
    var w = n ? Math.round(100 * k / n) : 0;
    return '<span class="consensus"><span class="fillbar" aria-hidden="true"><i style="width:' + w + '%"></i></span>' + k + ' of ' + n + ' in</span>';
  }
  function paint(live) {
    if (!D) return;
    [].forEach.call(document.querySelectorAll('[data-ps-label]'), function (el) { el.textContent = label(false); });
    [].forEach.call(document.querySelectorAll('[data-ps-wlabel]'), function (el) { el.textContent = wlabel(); });
    var wp = wPreset();
    [].forEach.call(document.querySelectorAll('[data-ps-wset]'), function (b) { if (!ov || !ov.contains(b)) b.setAttribute('aria-pressed', String(!!wp && wp.k === b.getAttribute('data-ps-wset'))); });
    [].forEach.call(document.querySelectorAll('[data-ps-set]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-ps-set') === choice.p)); });
    [].forEach.call(document.querySelectorAll('[data-ps-toggle]'), function (cb) { var i = IDX[cb.getAttribute('data-ps-toggle')]; if (i != null) cb.checked = !!sel[i]; });
    [].forEach.call(document.querySelectorAll('[data-ps-open]'), function (b) { b.classList.toggle('ps-on', b.getAttribute('data-ps-open') === 'weights' ? !isDefaultW() : choice.p !== 'all'); });
    var tables = [];
    [].forEach.call(document.querySelectorAll('tr[data-sym], tr[data-ps-row]'), function (tr) {
      var cell = tr.querySelector('td[data-ps-plays]'), sc = tr.querySelector('td[data-ps-scorecell]'), sg = tr.querySelector('td[data-ps-signal]'), fams = tr.querySelectorAll('td[data-ps-fam]');
      if (!cell && !sc && !sg && !fams.length) return;
      var sym = tr.getAttribute('data-sym') || tr.getAttribute('data-ps-row');
      if (!D.t[sym]) return;
      var c = count(sym), share = c.n ? c.k / c.n : null;
      if (cell) { cell.innerHTML = consensus(c.k, c.n); cell.setAttribute('data-v', share == null ? '' : share.toFixed(4)); }
      if (tr.hasAttribute('data-share')) tr.setAttribute('data-share', (share || 0).toFixed(3));
      if (sc || sg) {
        var r = score(sym);
        if (sc) { sc.innerHTML = r.s == null ? '–' : '<b>' + r.s + '</b>'; sc.setAttribute('data-v', r.s == null ? '' : r.s); }
        if (sg && sg.hasAttribute('data-with-score')) { sg.innerHTML = sigPill(r.sig) + (r.s == null ? '' : ' <b class="sig-n">' + r.s + '</b>'); sg.setAttribute('data-v', r.s == null ? '' : r.s); }
        else if (sg) { sg.innerHTML = sigPill(r.sig); sg.setAttribute('data-v', r.sig == null ? '' : r.sig); }
        if (tr.hasAttribute('data-sig')) tr.setAttribute('data-sig', r.sig == null ? '' : r.sig);
      }
      [].forEach.call(fams, function (td) {
        var f = c.f[FAMI[td.getAttribute('data-ps-fam')]];
        if (!f) return;
        var bar = td.querySelector('.fillbar i'), txt = td.querySelector('a > span:last-child'), a = td.querySelector('a');
        if (bar) bar.style.width = (f[1] ? Math.round(100 * f[0] / f[1]) : 0) + '%';
        if (txt) txt.textContent = f[0] + '/' + f[1];
        td.setAttribute('data-v', f[1] ? (f[0] / f[1]).toFixed(4) : '');
        td.classList.toggle('ps-none', !f[1]);
        if (a && a.title) a.title = a.title.replace(/: \d+ of \d+ in$/, ': ' + f[0] + ' of ' + f[1] + ' in');
      });
      var tb = tr.closest('table');
      if (tables.indexOf(tb) < 0) tables.push(tb);
    });
    tables.forEach(function (tb) { if (window.BPSort) window.BPSort.resort(tb); });
    if (ov && !ov.hidden) { if (live && tab === 'weights') paintWeightsLive(); else paintPanel(); }
  }

  // ------------------------------------------------------------ the chooser: two tabs, Your signal (weights) and Plays
  function build() {
    if (ov) return;
    ov = document.createElement('div');
    ov.className = 'ps-ov';
    ov.hidden = true;
    ov.innerHTML =
      '<div class="ps-panel" role="dialog" aria-modal="true" aria-labelledby="ps-h" tabindex="-1">' +
      '<header class="ps-head"><div><h2 id="ps-h"></h2><p class="ps-lede"></p></div>' +
      '<button type="button" class="ps-x" aria-label="Close">×</button></header>' +
      '<div class="ps-tabs seg seg-sm" role="tablist" aria-label="Settings"><button type="button" role="tab" data-ps-tab="weights">Your signal</button><button type="button" role="tab" data-ps-tab="plays">Plays counted</button></div>' +
      '<div class="ps-presets" role="group" aria-label="Ready-made sets"></div>' +
      '<div class="ps-tools"></div>' +
      '<div class="ps-body"></div>' +
      '<footer class="ps-foot"><span class="ps-count" aria-live="polite"></span><span class="ps-saved small muted"></span>' +
      '<a class="small ps-guide" href="' + esc(GUIDE) + '">How this works</a><button type="button" class="btn primary sm ps-done">Done</button></footer></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (ev) {
      if (ev.target === ov) return close();
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.classList.contains('ps-x') || b.classList.contains('ps-done')) close();
      else if (b.hasAttribute('data-ps-tab')) { tab = b.getAttribute('data-ps-tab'); ov.querySelector('.ps-body').scrollTop = 0; paintPanel(); }
      else if (b.hasAttribute('data-ps-set')) apply({ p: b.getAttribute('data-ps-set'), s: [] }, 'user');
      else if (b.hasAttribute('data-ps-wset')) {
        var pr = D.wp.filter(function (x) { return x.k === b.getAttribute('data-ps-wset'); })[0];
        if (pr) { applyW({ w: pr.w, buy: wts.buy, sell: wts.sell }, 'user'); paintPanel(); }
      } else if (b.hasAttribute('data-ps-wreset')) { applyW(D.wd, 'user'); paintPanel(); }
      else if (b.hasAttribute('data-ps-sort')) { sortBy = b.getAttribute('data-ps-sort'); paintPanel(); }
    });
    ov.addEventListener('input', function (ev) {
      var t = ev.target;
      if (t.hasAttribute('data-ps-w')) {
        var w = Object.assign({}, wts.w), k = t.getAttribute('data-ps-w'), v = +t.value;
        if (v > 0) w[k] = v; else delete w[k];
        if (!Object.keys(w).length) { t.value = 5; w[k] = 5; }
        applyW({ w: w, buy: wts.buy, sell: wts.sell }, 'user');
      } else if (t.hasAttribute('data-ps-line')) {
        var c = { w: wts.w, buy: wts.buy, sell: wts.sell }, which = t.getAttribute('data-ps-line');
        c[which] = +t.value;
        if (c.sell >= c.buy) { if (which === 'buy') c.sell = c.buy - 5; else c.buy = c.sell + 5; }
        applyW(c, 'user');
      }
    });
    ov.addEventListener('change', function (ev) {
      var t = ev.target;
      if (t.hasAttribute('data-ps-play')) { if (toggle(t.getAttribute('data-ps-play'), t.checked) === false) { t.checked = true; hint('Keep at least one play.'); } }
      else if (t.hasAttribute('data-ps-fam')) { if (setFam(t.getAttribute('data-ps-fam'), t.checked) === false) { paintPanel(); hint('Keep at least one play.'); } }
    });
    document.addEventListener('keydown', function (ev) {
      if (ov.hidden) return;
      if (ev.key === 'Escape') { ev.preventDefault(); close(); }
      if (ev.key === 'Tab') {   // keep focus inside the chooser
        var f = [].filter.call(ov.querySelectorAll('button, input, a[href]'), function (x) { return x.offsetParent !== null; });
        if (!f.length) return;
        if (ev.shiftKey && document.activeElement === f[0]) { ev.preventDefault(); f[f.length - 1].focus(); }
        else if (!ev.shiftKey && document.activeElement === f[f.length - 1]) { ev.preventDefault(); f[0].focus(); }
      }
    });
  }
  function hint(t) { var c = ov.querySelector('.ps-count'); c.textContent = t; setTimeout(paintPanel, 1600); }
  function hereOf(i) { if (!here || !here.b || !here.b[i]) return null; var b = here.b[i]; return b[1] ? { r: b[0], n: b[1], a: b[0] / b[1] } : { r: 0, n: 0, a: null }; }
  function keepFocus(body, html, attr) {
    var top = body.scrollTop, had = document.activeElement, key = had && had.getAttribute && (attr.map(function (x) { return had.getAttribute(x) && x + '="' + had.getAttribute(x) + '"'; }).filter(Boolean)[0]);
    body.innerHTML = html;
    body.scrollTop = top;
    if (!ov.hidden && (!document.activeElement || document.activeElement === document.body)) {
      var back = key && body.querySelector('[' + key + ']');
      (back || ov.querySelector('.ps-panel')).focus();
    }
  }
  function paintPanel() {
    [].forEach.call(ov.querySelectorAll('[data-ps-tab]'), function (b) { var on = b.getAttribute('data-ps-tab') === tab; b.setAttribute('aria-pressed', String(on)); b.setAttribute('aria-selected', String(on)); });
    if (tab === 'weights') return paintWeights();
    ov.querySelector('#ps-h').textContent = 'Choose the plays that count';
    ov.querySelector('.ps-lede').textContent = 'Every count on Be The Puck uses only the plays you tick: how many plays hold a stock, the screener, the stock list and your dashboard. ' +
      'The % is how often each play’s calls went the right way on ' + D.n + ' stocks since ' + D.since + '.';
    var pres = [['top1'], ['top3'], ['half'], ['all']].map(function (x) {
      var n = 0, s = resolve({ p: x[0], s: [] });
      for (var i = 0; i < s.length; i++) n += s[i];
      return '<button type="button" class="chip-btn" data-ps-set="' + x[0] + '" aria-pressed="' + (choice.p === x[0]) + '">' + esc(NAME[x[0]]) + ' <span class="muted">' + n + '</span></button>';
    }).join('');
    ov.querySelector('.ps-presets').innerHTML = pres;
    var sorts = [['acc', 'Most accurate']].concat(here ? [['here', 'Right on ' + here.s]] : []).concat([['az', 'A to Z']]);
    if (!here && sortBy === 'here') sortBy = 'acc';
    ov.querySelector('.ps-tools').innerHTML = '<span class="small muted">Order</span><div class="seg seg-sm ps-sort" role="group" aria-label="Order the plays">' +
      sorts.map(function (s) { return '<button type="button" data-ps-sort="' + s[0] + '" aria-pressed="' + (sortBy === s[0]) + '">' + esc(s[1]) + '</button>'; }).join('') + '</div>';
    var html = '';
    D.fams.forEach(function (f) {
      var ix = [];
      D.plays.forEach(function (p, i) { if (p.f === f[0]) ix.push(i); });
      ix.sort(function (a, b) {
        var A = D.plays[a], B = D.plays[b];
        if (sortBy === 'az') return A.n < B.n ? -1 : A.n > B.n ? 1 : 0;
        if (sortBy === 'here') { var ha = hereOf(a), hb = hereOf(b); var va = ha && ha.a != null ? ha.a : -1, vb = hb && hb.a != null ? hb.a : -1; if (vb !== va) return vb - va; }
        return (B.e - A.e) || ((B.a || 0) - (A.a || 0)) || (B.c - A.c);
      });
      var on = ix.filter(function (i) { return sel[i]; }), wc = 0, wa = 0;
      on.forEach(function (i) { var p = D.plays[i]; wc += p.c; wa += (p.a || 0) * p.c; });
      html += '<section class="ps-fam" data-fam="' + f[0] + '"><div class="ps-fam-h"><label class="ps-fam-l"><input type="checkbox" data-ps-fam="' + f[0] + '"' + (on.length ? ' checked' : '') + '>' +
        '<b>' + esc(f[1]) + '</b></label><span class="ps-fam-n">' + on.length + ' of ' + ix.length + (on.length ? ' · ' + pc(wc ? wa / wc : null) + ' right' : '') + '</span></div><ul class="ps-list">';
      ix.forEach(function (i) {
        var p = D.plays[i], hh = hereOf(i);
        html += '<li><label class="ps-row' + (sel[i] ? ' on' : '') + '"><input type="checkbox" data-ps-play="' + p.s + '"' + (sel[i] ? ' checked' : '') + '>' +
          '<span class="ps-nm">' + esc(p.n) + (p.t ? ' <span class="ps-top">Top</span>' : '') + (p.e ? '' : ' <span class="ps-few" title="Fewer than ' + D.min + ' calls, or calls on fewer than half the stocks">few calls</span>') + '</span>' +
          '<span class="ps-acc"><span class="ps-accbar" aria-hidden="true"><i style="width:' + Math.round(100 * (p.a || 0)) + '%"></i></span><b>' + pc(p.a) + '</b></span>' +
          '<span class="ps-calls">' + num(p.c) + ' calls</span>' +
          (hh ? '<span class="ps-here" title="On ' + esc(here.s) + ': right ' + hh.r + ' of ' + hh.n + '">' + esc(here.s) + ' <b>' + pc(hh.a) + '</b> <span>' + hh.r + '/' + hh.n + '</span></span>' : '') +
          '</label></li>';
      });
      html += '</ul></section>';
    });
    var body = ov.querySelector('.ps-body');
    keepFocus(body, html, ['data-ps-play', 'data-ps-fam']);
    [].forEach.call(body.querySelectorAll('input[data-ps-fam]'), function (cb) {
      var fk = cb.getAttribute('data-ps-fam'), tot = 0, k = 0;
      D.plays.forEach(function (p, i) { if (p.f === fk) { tot++; k += sel[i]; } });
      cb.indeterminate = k > 0 && k < tot;
    });
    ov.querySelector('.ps-count').innerHTML = '<b>' + size() + '</b> of ' + D.plays.length + ' plays counted';
    ov.querySelector('.ps-saved').textContent = auth() ? 'Saved to your account' : origin === 'link' ? 'From a shared link' : 'Saved in this browser';
  }
  function hereScore() { return here && D.x[here.sym] ? score(here.sym) : null; }
  // a factor's or preset's record (factorgrade.py): Buys and Avoids against the market over a year
  function recText(r, preset) {
    if (!r) return '';
    if (r.why) return 'Not graded: ' + r.why + '.';
    var e = (r.e > 0 ? '+' : '') + Number(r.e).toFixed(1);
    var t = 'Since ' + D.gs + ', its Buys beat the market over the next year ' + r.bb + '% of the time and its Avoids ' + r.ab + '%: edge ' + e + ' pts.';
    if (preset && r.gw != null && r.gw < 100) t += ' Graded on ' + r.gw + '% of its weight (' + r.lo.join(', ') + (r.lo.length > 1 ? ' have' : ' has') + ' no history).';
    return t;
  }
  function recCls(r) { return !r || r.why ? 'na' : r.e >= 3 ? 'good' : r.e <= 0 ? 'poor' : 'some'; }
  function presetRec() {
    var pr = wPreset(), el = ov && ov.querySelector('.ps-prec');
    if (!el) return;
    el.innerHTML = pr && pr.r ? '<b>' + esc(pr.n) + '.</b> ' + esc(recText(pr.r, true)) : 'Your own mix: it hasn’t been graded as a whole. Each factor’s record is under its slider.';
  }
  function paintWeights() {
    ov.querySelector('#ps-h').textContent = 'Your signal';
    ov.querySelector('.ps-lede').textContent = (migrated ? 'The standard weights changed on October 13, 2026, to factors with a tested record. You were on the old standard (plays and analysts’ upside), so you’re now on the new one; pick “Plays + analysts” to go back. ' : '') +
      'Weight what matters to you. Each factor scores a stock from 0 to 100; your score is the weighted average, ' +
      'and your Buy and Sell lines turn it into a signal on every page. P/E, growth and the other company numbers score by rank against the ' + D.n + ' stocks we cover.';
    var pr = wPreset();
    ov.querySelector('.ps-presets').innerHTML = D.wp.map(function (x) {
      var e = x.r && !x.r.why ? ' <span class="ps-edge ' + recCls(x.r) + '">' + (x.r.e > 0 ? '+' : '') + Number(x.r.e).toFixed(1) + '</span>' : '';
      return '<button type="button" class="chip-btn" data-ps-wset="' + x.k + '" aria-pressed="' + (!!pr && pr.k === x.k) + '">' + esc(x.n) + e + '</button>';
    }).join('') + '<p class="small ps-prec" aria-live="polite"></p>';
    ov.querySelector('.ps-tools').innerHTML =
      '<label class="ps-line">Buy at or above <b data-ps-lv="buy">' + wts.buy + '</b><input type="range" min="50" max="95" step="5" value="' + wts.buy + '" data-ps-line="buy" aria-label="Buy line"></label>' +
      '<label class="ps-line">Sell at or below <b data-ps-lv="sell">' + wts.sell + '</b><input type="range" min="5" max="50" step="5" value="' + wts.sell + '" data-ps-line="sell" aria-label="Sell line"></label>';
    var html = '', tot = 0;
    D.fx.forEach(function (f) { tot += wts.w[f.k] || 0; });
    var hx = here && D.x[here.sym] ? { x: D.x[here.sym], v: D.v[here.sym] } : null;
    D.fg.forEach(function (g) {
      var gw = 0;
      D.fx.forEach(function (f) { if (f.g === g[0]) gw += wts.w[f.k] || 0; });
      html += '<section class="ps-fam ps-wgrp" data-g="' + g[0] + '"><div class="ps-fam-h"><b>' + esc(g[1]) + '</b><span class="ps-fam-n" data-ps-gshare="' + g[0] + '">' + (tot ? Math.round(100 * gw / tot) : 0) + '% of the score</span></div><ul class="ps-list">';
      D.fx.forEach(function (f, i) {
        if (f.g !== g[0]) return;
        var wv = wts.w[f.k] || 0, hv = '';
        if (hx) {
          var p = hx.x[i], v = hx.v[i];
          if (f.k === 'plays') { var c = count(here.sym); p = c.n ? Math.round(100 * c.k / c.n) : null; v = p == null ? null : p + '%'; }
          hv = '<span class="ps-here">' + esc(here.s) + ' ' + (v == null ? 'no data' : esc(v) + ' · <b>' + p + '</b> pts') + '</span>';
        }
        html += '<li class="ps-wrow' + (wv ? ' on' : '') + '" data-f="' + f.k + '"><div class="ps-wtop"><span class="ps-nm">' + esc(f.n) + '</span>' +
          '<span class="ps-wval"><b data-ps-wv="' + f.k + '">' + wv + '</b> <span class="muted" data-ps-ws="' + f.k + '">' + (tot && wv ? Math.round(100 * wv / tot) + '%' : '') + '</span></span></div>' +
          '<input type="range" min="0" max="100" step="5" value="' + wv + '" data-ps-w="' + f.k + '" aria-label="Weight for ' + esc(f.n) + '">' +
          '<div class="ps-wsub"><span class="ps-wd">' + esc(f.d) + '</span>' + hv + '</div>' +
          (f.r ? '<p class="ps-rec ' + recCls(f.r) + '">' + esc(recText(f.r)) + '</p>' : '') + '</li>';
      });
      html += '</ul></section>';
    });
    html += '<p class="small ps-wnote">Edge: how much more often a factor’s Buys beat the market over the next year than its Avoids did, tested monthly since ' + D.gs +
      ' on numbers public at the time. Small edges are the norm; none of these is a sure thing. Weights are relative: 20 and 20 count the same as 50 and 50. A stock without a number for a factor (a fund has no P/E) is scored on the rest, ' +
      'and gets no score if less than half your weight applies. <button type="button" class="linkish" data-ps-wreset>Back to the standard weights</button></p>';
    keepFocus(ov.querySelector('.ps-body'), html, ['data-ps-w']);
    paintWeightsLive();
  }
  function paintWeightsLive() {
    var tot = 0;
    D.fx.forEach(function (f) { tot += wts.w[f.k] || 0; });
    D.fx.forEach(function (f) {
      var wv = wts.w[f.k] || 0, a = ov.querySelector('[data-ps-wv="' + f.k + '"]'), b = ov.querySelector('[data-ps-ws="' + f.k + '"]'), row = ov.querySelector('.ps-wrow[data-f="' + f.k + '"]');
      if (a) a.textContent = wv;
      if (b) b.textContent = tot && wv ? Math.round(100 * wv / tot) + '%' : '';
      if (row) row.classList.toggle('on', !!wv);
    });
    D.fg.forEach(function (g) {
      var gw = 0, el = ov.querySelector('[data-ps-gshare="' + g[0] + '"]');
      D.fx.forEach(function (f) { if (f.g === g[0]) gw += wts.w[f.k] || 0; });
      if (el) el.textContent = (tot ? Math.round(100 * gw / tot) : 0) + '% of the score';
    });
    ['buy', 'sell'].forEach(function (k) { var el = ov.querySelector('[data-ps-lv="' + k + '"]'), r = ov.querySelector('[data-ps-line="' + k + '"]'); if (el) el.textContent = wts[k]; if (r && +r.value !== wts[k]) r.value = wts[k]; });
    var pr = wPreset();
    [].forEach.call(ov.querySelectorAll('[data-ps-wset]'), function (b) { b.setAttribute('aria-pressed', String(!!pr && pr.k === b.getAttribute('data-ps-wset'))); });
    presetRec();
    var hs = hereScore(), n = Object.keys(wts.w).length;
    ov.querySelector('.ps-count').innerHTML = hs ? esc(here.s) + ': <b>' + (hs.s == null ? 'no score' : hs.s) + '</b>' + (hs.sig == null ? '' : ' ' + sigPill(hs.sig))
      : '<b>' + n + '</b> factor' + (n === 1 ? '' : 's') + ' weighted';
    ov.querySelector('.ps-saved').textContent = auth() ? 'Saved to your account' : worigin === 'link' ? 'From a shared link' : 'Saved in this browser';
  }
  function open(which) {
    if (!D) { waiting.push(function () { open(which); }); return; }
    build();
    if (which === 'weights' || which === 'plays') tab = which;
    opener = document.activeElement;
    paintPanel();
    ov.hidden = false;
    document.documentElement.classList.add('ps-lock');
    ov.querySelector('.ps-panel').focus();
  }
  function close() {
    if (!ov) return;
    ov.hidden = true;
    document.documentElement.classList.remove('ps-lock');
    if (opener && opener.focus) opener.focus();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-ps-open], [data-ps-set], [data-ps-wset]');
    if (!b || (ov && ov.contains(b))) return;
    ev.preventDefault();
    if (b.hasAttribute('data-ps-wset')) {
      if (!D) return;
      var pr = D.wp.filter(function (x) { return x.k === b.getAttribute('data-ps-wset'); })[0];
      if (pr) applyW({ w: pr.w, buy: wts.buy, sell: wts.sell }, 'user');
      return;
    }
    if (b.hasAttribute('data-ps-open')) open(b.getAttribute('data-ps-open') === 'weights' ? 'weights' : 'plays');
    else if (D) apply({ p: b.getAttribute('data-ps-set'), s: [] }, 'user');
  });
  document.addEventListener('change', function (ev) {
    var t = ev.target;
    if (!t.hasAttribute || !t.hasAttribute('data-ps-toggle') || (ov && ov.contains(t)) || !D) return;
    if (toggle(t.getAttribute('data-ps-toggle'), t.checked) === false) t.checked = true;
  });

  // ------------------------------------------------------------ public
  window.BPPlays = {
    ready: function (cb) { if (D) cb(D); else waiting.push(cb); },
    onChange: function (cb) { subs.push(cb); },
    data: function () { return D; },
    loaded: function () { return !!D; },
    isAll: function () { return !D || choice.p === 'all'; },
    size: size,
    total: function () { return D ? D.plays.length : 0; },
    on: function (i) { return !!(sel && sel[i]); },
    onSlug: function (s) { return !!(sel && IDX[s] != null && sel[IDX[s]]); },
    slugs: current,
    count: count,
    label: label,
    choice: function () { return choice; },
    set: function (c) { if (D) apply(c, 'user'); },
    toggle: toggle,
    here: function (h) { here = h; },
    open: open,
    hadChoice: function () { return origin !== 'default'; },
    /** The account's saved choices: used unless this browser already has its own, or a link set them. */
    adopt: function (c, sig) {
      if (!D) return;
      c = clean(c);
      if (c && origin === 'default') { origin = 'account'; lsSet(c); apply(c, 'account'); }
      var raw = sig;
      sig = cleanW(sig);
      if (sig) { sig.mv = (raw && raw.mv) || 1; sig = migrate(sig); }
      if (sig && worigin === 'default') { worigin = 'account'; lsSet(sig, WKEY); applyW(sig, 'account'); }
    },
    // your signal
    score: score,
    flips: flips,
    flipWords: flipWords,
    weights: function () { return wts; },
    wlabel: wlabel,
    isDefaultWeights: isDefaultW,
    migrated: function () { return migrated; },
    changes: changes,
    tested: tested,
    setWeights: function (c) { if (D) applyW(c, 'user'); },
    sigWord: function (sig) { return sig == null ? 'No score' : SIG_WORD[sig]; },
    sigClass: function (sig) { return sig == null ? 'na' : SIG_CLS[sig]; }
  };

  // ------------------------------------------------------------ start
  if (location.protocol === 'file:') return;
  fetch(DATA_URL).then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    D.plays.forEach(function (p, i) { IDX[p.s] = i; });
    D.fams.forEach(function (f, i) { FAMI[f[0]] = i; });
    D.fx.forEach(function (f, i) { FXI[f.k] = i; });
    var q = new URLSearchParams(location.search), wl = wFromParam(q), stored = lsGet(WKEY), wm = cleanW(stored);
    if (wm && stored) wm.mv = stored.mv || 1;
    wm = migrate(wm);
    if (migrated) lsSet(wm, WKEY);
    if (wl) { worigin = 'link'; wts = wl; } else if (wm) { worigin = 'browser'; wts = wm; } else wts = cleanW(D.wd);
    var link = fromParam(q.get('plays')), mine = clean(lsGet());
    if (link) { origin = 'link'; choice = link; }
    else if (mine) { origin = 'browser'; choice = mine; }
    choice = normal(choice);
    sel = resolve(choice);
    paint();
    var w = waiting; waiting = [];
    w.forEach(function (f) { try { f(D); } catch (e) { /* keep going */ } });
    var A = auth();
    if (A && (origin === 'default' || worigin === 'default')) A.me().then(function (a) { if (a && (a.plays || a.signal)) window.BPPlays.adopt(a.plays, a.signal); }).catch(function () {});
  }).catch(function () { /* the counts printed on the page stay */ });
})();
