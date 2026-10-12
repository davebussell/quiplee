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
 * Markup it looks after on any page:
 *   [data-ps-open]      opens the chooser          [data-ps-label]   the current choice, short
 *   [data-ps-set=top1]  applies a ready-made set   [data-ps-toggle=slug] a checkbox for one play
 *   tr[data-sym|data-ps-row] with td[data-ps-plays] / td[data-ps-scorecell] (+ tr[data-upp]) / td[data-ps-fam=k]:
 *                       recounted for the choice, and the table re-sorted */
(function () {
  'use strict';
  if (window.BPPlays) return;
  var KEY = 'bp.plays.v1';
  var me = document.currentScript, src = (me && me.src) || '';
  var ver = (src.split('?v=')[1] || '');
  var DATA_URL = src.replace(/assets\/plays\.js(\?.*)?$/, 'data/playset.json') + (ver ? '?v=' + ver : '');
  var GUIDE = src.replace(/assets\/plays\.js(\?.*)?$/, 'guides/your-plays/');
  var NAME = { all: 'All plays', top1: 'Most accurate in each family', top3: 'Top 3 in each family', half: 'Right more than half the time', custom: 'Your own pick' };
  var TREND_WEIGHT = 0.5;   // the Score: half plays in, half analysts' upside (stockview.py)
  var D = null, IDX = {}, FAMI = {}, sel = null, choice = { p: 'all', s: [] }, origin = 'default';
  var subs = [], waiting = [], here = null, sortBy = 'acc', ov = null, opener = null, saveT = null;

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pc(v) { return v == null ? '–' : Math.round(v * 100) + '%'; }
  function num(v) { return Number(v).toLocaleString('en-US'); }
  function lsGet() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }
  function lsSet(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* private mode */ } }
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
  function paint() {
    if (!D) return;
    [].forEach.call(document.querySelectorAll('[data-ps-label]'), function (el) { el.textContent = label(false); });
    [].forEach.call(document.querySelectorAll('[data-ps-set]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-ps-set') === choice.p)); });
    [].forEach.call(document.querySelectorAll('[data-ps-toggle]'), function (cb) { var i = IDX[cb.getAttribute('data-ps-toggle')]; if (i != null) cb.checked = !!sel[i]; });
    [].forEach.call(document.querySelectorAll('[data-ps-open]'), function (b) { b.classList.toggle('ps-on', choice.p !== 'all'); });
    var tables = [];
    [].forEach.call(document.querySelectorAll('tr[data-sym], tr[data-ps-row]'), function (tr) {
      var cell = tr.querySelector('td[data-ps-plays]'), sc = tr.querySelector('td[data-ps-scorecell]'), fams = tr.querySelectorAll('td[data-ps-fam]');
      if (!cell && !sc && !fams.length) return;
      var sym = tr.getAttribute('data-sym') || tr.getAttribute('data-ps-row');
      if (!D.t[sym]) return;
      var c = count(sym), share = c.n ? c.k / c.n : null;
      if (cell) { cell.innerHTML = consensus(c.k, c.n); cell.setAttribute('data-v', share == null ? '' : share.toFixed(4)); }
      if (tr.hasAttribute('data-share')) tr.setAttribute('data-share', (share || 0).toFixed(3));
      var upp = tr.getAttribute('data-upp');
      if (sc && upp) { var v = Math.round(100 * (TREND_WEIGHT * (share || 0) + (1 - TREND_WEIGHT) * +upp)); sc.innerHTML = '<b>' + v + '</b>'; sc.setAttribute('data-v', v); }
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
    if (ov && !ov.hidden) paintPanel();
  }

  // ------------------------------------------------------------ the chooser
  function build() {
    if (ov) return;
    ov = document.createElement('div');
    ov.className = 'ps-ov';
    ov.hidden = true;
    ov.innerHTML =
      '<div class="ps-panel" role="dialog" aria-modal="true" aria-labelledby="ps-h" tabindex="-1">' +
      '<header class="ps-head"><div><h2 id="ps-h">Choose the plays that count</h2>' +
      '<p class="ps-lede">Every count on Be The Puck uses only the plays you tick: how many plays hold a stock, the screener, the stock list and your dashboard. ' +
      'The % is how often each play’s calls went the right way on ' + D.n + ' stocks since ' + D.since + '.</p></div>' +
      '<button type="button" class="ps-x" aria-label="Close">×</button></header>' +
      '<div class="ps-presets" role="group" aria-label="Ready-made sets"></div>' +
      '<div class="ps-tools"><span class="small muted">Order</span><div class="seg seg-sm ps-sort" role="group" aria-label="Order the plays"></div></div>' +
      '<div class="ps-body"></div>' +
      '<footer class="ps-foot"><span class="ps-count" aria-live="polite"></span><span class="ps-saved small muted"></span>' +
      '<a class="small ps-guide" href="' + esc(GUIDE) + '">How this works</a><button type="button" class="btn primary sm ps-done">Done</button></footer></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (ev) {
      if (ev.target === ov) return close();
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.classList.contains('ps-x') || b.classList.contains('ps-done')) close();
      else if (b.hasAttribute('data-ps-set')) apply({ p: b.getAttribute('data-ps-set'), s: [] }, 'user');
      else if (b.hasAttribute('data-ps-sort')) { sortBy = b.getAttribute('data-ps-sort'); paintPanel(); }
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
  function paintPanel() {
    var pres = [['top1'], ['top3'], ['half'], ['all']].map(function (x) {
      var n = 0, s = resolve({ p: x[0], s: [] });
      for (var i = 0; i < s.length; i++) n += s[i];
      return '<button type="button" class="chip-btn" data-ps-set="' + x[0] + '" aria-pressed="' + (choice.p === x[0]) + '">' + esc(NAME[x[0]]) + ' <span class="muted">' + n + '</span></button>';
    }).join('');
    ov.querySelector('.ps-presets').innerHTML = pres;
    var sorts = [['acc', 'Most accurate']].concat(here ? [['here', 'Right on ' + here.s]] : []).concat([['az', 'A to Z']]);
    if (!here && sortBy === 'here') sortBy = 'acc';
    ov.querySelector('.ps-sort').innerHTML = sorts.map(function (s) { return '<button type="button" data-ps-sort="' + s[0] + '" aria-pressed="' + (sortBy === s[0]) + '">' + esc(s[1]) + '</button>'; }).join('');
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
    var body = ov.querySelector('.ps-body'), top = body.scrollTop;
    var had = document.activeElement, hadPlay = had && had.getAttribute && (had.getAttribute('data-ps-play') || had.getAttribute('data-ps-fam'));
    body.innerHTML = html;
    body.scrollTop = top;
    // keep the keyboard where it was after a redraw
    if (!ov.hidden && (!document.activeElement || document.activeElement === document.body)) {
      var back = hadPlay && body.querySelector('[data-ps-play="' + hadPlay + '"], [data-ps-fam="' + hadPlay + '"]');
      (back || ov.querySelector('.ps-panel')).focus();
    }
    [].forEach.call(body.querySelectorAll('input[data-ps-fam]'), function (cb) {
      var fk = cb.getAttribute('data-ps-fam'), tot = 0, k = 0;
      D.plays.forEach(function (p, i) { if (p.f === fk) { tot++; k += sel[i]; } });
      cb.indeterminate = k > 0 && k < tot;
    });
    ov.querySelector('.ps-count').innerHTML = '<b>' + size() + '</b> of ' + D.plays.length + ' plays counted';
    ov.querySelector('.ps-saved').textContent = auth() ? 'Saved to your account' : origin === 'link' ? 'From a shared link' : 'Saved in this browser';
  }
  function open(ev) {
    if (!D) { waiting.push(function () { open(ev); }); return; }
    build();
    opener = document.activeElement;
    paintPanel();
    ov.hidden = false;
    document.documentElement.classList.add('ps-lock');
    var p = ov.querySelector('.ps-panel');
    p.focus();
  }
  function close() {
    if (!ov) return;
    ov.hidden = true;
    document.documentElement.classList.remove('ps-lock');
    if (opener && opener.focus) opener.focus();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-ps-open], [data-ps-set]');
    if (!b || (ov && ov.contains(b))) return;
    ev.preventDefault();
    if (b.hasAttribute('data-ps-open')) open();
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
    /** The account's saved choice: used unless this browser already has one, or a link set it. */
    adopt: function (c) { c = clean(c); if (!c || !D || origin !== 'default') return; origin = 'account'; lsSet(c); apply(c, 'account'); }
  };

  // ------------------------------------------------------------ start
  if (location.protocol === 'file:') return;
  fetch(DATA_URL).then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    D.plays.forEach(function (p, i) { IDX[p.s] = i; });
    D.fams.forEach(function (f, i) { FAMI[f[0]] = i; });
    var link = fromParam(new URLSearchParams(location.search).get('plays')), mine = clean(lsGet());
    if (link) { origin = 'link'; choice = link; }
    else if (mine) { origin = 'browser'; choice = mine; }
    choice = normal(choice);
    sel = resolve(choice);
    paint();
    var w = waiting; waiting = [];
    w.forEach(function (f) { try { f(D); } catch (e) { /* keep going */ } });
    var A = auth();
    if (A && origin === 'default') A.me().then(function (a) { if (a && a.plays) window.BPPlays.adopt(a.plays); }).catch(function () {});
  }).catch(function () { /* the counts printed on the page stay */ });
})();
