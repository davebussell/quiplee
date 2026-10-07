/* screen.js: the home page screener. Steps 2 to 4 (your play, where to look, how
 * many plays must agree) filter every covered name live; data/screen.json comes from
 * tools/qstrat/screen.py, whose filter rules and row markup this mirrors.
 * URL: ?side=buy|sell&mkt=us|ca|crypto|fund&sec=<group>&risk=low|high&min=0-100&fresh=1&q=&sort=
 * The ☆ on a row follows the name: on the account when signed in, else in this
 * browser's watchlist (with a nudge to make a free account for the emails). */
(function () {
  'use strict';
  var root = document.getElementById('screen');
  if (!root) return;
  var SRC = root.getAttribute('data-src'), STOCK = root.getAttribute('data-stock'), ME = root.getAttribute('data-me');
  var PAGE = +root.getAttribute('data-page') || 25;
  var list = document.getElementById('scr-list'), sum = document.getElementById('scr-sum'), more = document.getElementById('scr-more');
  var empty = document.getElementById('scr-empty'), reset = document.getElementById('scr-reset');
  var minIn = document.getElementById('scr-min'), minOut = document.getElementById('scr-min-out');
  var secSel = document.getElementById('scr-sec'), qIn = document.getElementById('scr-q'), sortSel = document.getElementById('scr-sort');
  var fresh = document.getElementById('scr-fresh'), goBtn = document.getElementById('scr-go');
  var DEF = { side: 'buy', mkt: '', sec: '', risk: '', min: 60, fresh: false, q: '', sort: 'up' };
  var S = Object.assign({}, DEF), DATA = null, shown = PAGE, FAMS = [];
  var MKT = { '': '', us: 'U.S.', ca: 'Canada', crypto: 'Crypto', fund: 'Funds & indexes' };
  var RISK = ['Low', 'Moderate', 'High', 'Very high'], RISK_CLS = ['calm', 'watch', 'warning', 'warning'];
  var following = {}, acct = !!(window.BPAuth && window.BPAuth.signedIn());

  // ---------------------------------------------------------------- formatting (as render.py)
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function money(v, cur) {
    if (v == null) return '–';
    var a = Math.abs(v);
    if (a >= 10000) return cur + Math.round(v).toLocaleString('en-US');
    if (a > 0 && a < 1) { var pl = Math.min(6, Math.max(2, -Math.floor(Math.log10(a)) + 2)); return cur + v.toFixed(pl); }
    return cur + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function pct(v, d) {
    if (v == null) return '–';
    d = d == null ? 1 : d;
    var s = (Math.abs(v) * 100).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) + '%';
    if (v < 0 && +(Math.abs(v) * 100).toFixed(d) !== 0) return '−' + s;
    return v > 0 ? '+' + s : s;
  }
  function dir(v) { return v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''; }

  // ---------------------------------------------------------------- filter and sort (as screen.py)
  function agree(r) { return S.side === 'buy' ? r.k : r.o - r.k; }
  function days(a, b) { return Math.round((Date.parse(b) - Date.parse(a)) / 864e5); }
  function match(r) {
    if (!r.o) return false;
    if (100 * agree(r) / r.o < S.min - 1e-9) return false;
    if (S.mkt && r.m !== S.mkt) return false;
    if (S.sec && r.g !== S.sec) return false;
    if (S.risk === 'low' && !(r.r === 0 || r.r === 1)) return false;
    if (S.risk === 'high' && !(r.r === 2 || r.r === 3)) return false;
    if (S.fresh && (!r.since || days(r.since, DATA.asof) > 7 || r.L !== (S.side === 'buy' ? 1 : 0))) return false;
    if (S.q) {
      var q = S.q.toLowerCase();
      if ((r.s + ' ' + r.sym + ' ' + r.n).toLowerCase().indexOf(q) < 0) return false;
    }
    return true;
  }
  function cmpNum(a, b, desc) {
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return desc ? b - a : a - b;
  }
  function sorted(rows) {
    var by = {
      agree: function (a, b) { return agree(b) / b.o - agree(a) / a.o || b.o - a.o || (a.s < b.s ? -1 : 1); },
      day: function (a, b) { return cmpNum(Math.abs(a.d || 0) || null, Math.abs(b.d || 0) || null, true); },
      y1: function (a, b) { return cmpNum(a.y, b.y, true); },
      up: function (a, b) { return cmpNum(a.up, b.up, true) || agree(b) / b.o - agree(a) / a.o || (a.s < b.s ? -1 : 1); },
      risk: function (a, b) { return cmpNum(a.r, b.r, false) || agree(b) / b.o - agree(a) / a.o; },
      az: function (a, b) { return a.s < b.s ? -1 : a.s > b.s ? 1 : 0; }
    }[S.sort] || null;
    return rows.slice().sort(by);
  }

  // ---------------------------------------------------------------- markup (as screen.py)
  function light(r) {
    if (r.L == null) return '<span class="light-pill">–</span>';
    return '<span class="light-pill ' + (r.L === 1 ? 'start' : 'stop') + '"><i aria-hidden="true"></i>' + (r.L === 1 ? 'Start' : 'Stop') + '</span>';
  }
  function row(r) {
    var a = agree(r), w = r.o ? Math.round(100 * a / r.o) : 0, side = S.side;
    var fams = r.f.map(function (f, i) {
      var kk = side === 'buy' ? f[0] : f[1] - f[0];
      return '<i style="height:' + (f[1] ? Math.max(8, Math.round(100 * kk / f[1])) : 8) + '%" title="' + esc(FAMS[i]) + ': ' + kk + ' of ' + f[1] + '"></i>';
    }).join('');
    var risk = r.r != null ? '<span class="lvl lvl-' + RISK_CLS[r.r] + '">' + RISK[r.r] + '</span>' : '<span class="muted">–</span>';
    var up = r.up != null ? '<span class="' + dir(r.up) + '">' + pct(r.up, 0) + '</span>' : '<span class="muted">–</span>';
    var on = !!following[r.sym];
    return '<li class="scr-row" data-sym="' + esc(r.sym) + '"><a class="scr-main" href="' + esc(STOCK.replace('{u}', r.u)) + '">' +
      '<span class="scr-sym"><b>' + esc(r.s) + '</b><span>' + esc(r.n) + '</span></span>' +
      '<span class="scr-light">' + light(r) + '</span>' +
      '<span class="scr-agree ' + side + '"><span class="scr-num"><b>' + a + '</b> of ' + r.o + '</span><span class="fillbar" aria-hidden="true"><i style="width:' + w + '%"></i></span></span>' +
      '<span class="scr-fams ' + side + '" aria-hidden="true">' + fams + '</span>' +
      '<span class="scr-px mono">' + money(r.p, r.c) + ' <small class="' + dir(r.d) + '">' + pct(r.d) + '</small></span>' +
      '<span class="scr-y1 ' + dir(r.y) + '"><em>1 yr</em>' + pct(r.y, 0) + '</span>' +
      '<span class="scr-risk"><em>Crash</em>' + risk + '</span>' +
      '<span class="scr-up"><em>Analysts</em>' + up + '</span></a>' +
      '<button type="button" class="scr-star' + (on ? ' on' : '') + '" aria-pressed="' + on + '" aria-label="' + (on ? 'Stop following ' : 'Follow ') + esc(r.s) + '" title="' + (on ? 'Following' : 'Follow') + ' ' + esc(r.s) + '">' + (on ? '★' : '☆') + '</button></li>';
  }
  function summary(n) {
    var bits = [MKT[S.mkt], S.sec, S.risk === 'low' ? 'low or moderate crash exposure' : S.risk === 'high' ? 'high crash exposure' : '', S.fresh ? 'flipped this week' : '', S.q ? '“' + S.q + '”' : ''].filter(Boolean);
    return '<b>' + n + ' name' + (n === 1 ? '' : 's') + '</b> where at least <b>' + S.min + ' of 100</b> plays agree with <b>' + (S.side === 'buy' ? 'buying' : 'selling') + '</b>' +
      (bits.length ? ' · ' + esc(bits.join(' · ')) : '');
  }

  // ---------------------------------------------------------------- draw
  function draw() {
    if (!DATA) return;
    var got = sorted(DATA.t.filter(match));
    list.innerHTML = got.slice(0, shown).map(row).join('');
    sum.innerHTML = summary(got.length);
    goBtn.textContent = got.length ? 'See the ' + got.length + ' name' + (got.length === 1 ? '' : 's') : 'No names match yet';
    empty.hidden = got.length > 0;
    more.hidden = got.length <= shown;
    more.textContent = 'Show ' + Math.min(PAGE, got.length - shown) + ' more';
    reset.hidden = JSON.stringify(S) === JSON.stringify(DEF);
    sync();
  }
  function paintControls() {
    [].forEach.call(root.querySelectorAll('[data-side]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-side') === S.side)); });
    [].forEach.call(root.querySelectorAll('[data-mkt]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-mkt') === S.mkt)); });
    [].forEach.call(root.querySelectorAll('[data-risk]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-risk') === S.risk)); });
    [].forEach.call(root.querySelectorAll('[data-min]'), function (b) { b.setAttribute('aria-pressed', String(+b.getAttribute('data-min') === S.min)); });
    minIn.value = S.min;
    minOut.innerHTML = S.min ? 'At least <b>' + S.min + '</b> of 100' : 'Any number';
    fresh.checked = S.fresh;
    qIn.value = S.q;
    sortSel.value = S.sort;
    // the sectors that have names in the chosen market
    if (DATA) {
      var have = {};
      DATA.t.forEach(function (r) { if (!S.mkt || r.m === S.mkt) have[r.g] = 1; });
      [].forEach.call(secSel.options, function (o) { if (o.value) { o.hidden = !have[o.value]; o.disabled = !have[o.value]; } });
      if (S.sec && !have[S.sec]) S.sec = '';
    }
    secSel.value = S.sec;
    root.classList.toggle('selling', S.side === 'sell');
  }
  function sync() {
    var p = new URLSearchParams();
    Object.keys(DEF).forEach(function (k) { if (S[k] !== DEF[k]) p.set(k, k === 'fresh' ? '1' : S[k]); });
    var qs = p.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }

  // ---------------------------------------------------------------- the walk-through: mark steps done and point at the next one
  var steps = ['step-2', 'step-3', 'step-4'].map(function (id) { return document.getElementById(id); });
  function touched(n) {
    steps.forEach(function (el, i) {
      if (!el) return;
      if (i + 2 <= n) el.classList.add('is-done');
      el.classList.toggle('is-next', i + 2 === n + 1 && !el.classList.contains('is-done'));
    });
  }
  function change(patch, stepN) {
    Object.assign(S, patch);
    shown = PAGE;
    paintControls();
    draw();
    if (stepN) touched(stepN);
  }

  root.addEventListener('click', function (ev) {
    var b = ev.target.closest('button');
    if (!b || !root.contains(b)) return;
    if (b.hasAttribute('data-side')) change({ side: b.getAttribute('data-side') }, 2);
    else if (b.hasAttribute('data-mkt')) change({ mkt: b.getAttribute('data-mkt') }, 3);
    else if (b.hasAttribute('data-risk')) change({ risk: b.getAttribute('data-risk') }, 3);
    else if (b.hasAttribute('data-min')) change({ min: +b.getAttribute('data-min') }, 4);
    else if (b.hasAttribute('data-preset')) {
      var p = JSON.parse(b.getAttribute('data-preset'));
      change(Object.assign({}, DEF, p), 4);
      document.getElementById('scr-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (b === reset) { change(Object.assign({}, DEF)); steps.forEach(function (el, i) { if (el) { el.classList.remove('is-done'); el.classList.toggle('is-next', i === 0); } }); }
    else if (b === more) { shown += PAGE; draw(); }
    else if (b === goBtn) document.getElementById('scr-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    else if (b.classList.contains('scr-star')) star(b);
  });
  minIn.addEventListener('input', function () { change({ min: +minIn.value }, 4); });
  secSel.addEventListener('change', function () { change({ sec: secSel.value }, 3); });
  sortSel.addEventListener('change', function () { change({ sort: sortSel.value }); });
  fresh.addEventListener('change', function () { change({ fresh: fresh.checked }, 4); });
  var qt = null;
  qIn.addEventListener('input', function () { clearTimeout(qt); qt = setTimeout(function () { change({ q: qIn.value.trim() }, 3); }, 150); });

  // ---------------------------------------------------------------- follow
  var WKEY = 'quiplee.watch.v1';
  function localGet() { try { var v = JSON.parse(localStorage.getItem(WKEY) || 'null'); return v && v.items ? v : { items: [] }; } catch (e) { return { items: [] }; } }
  function localSet(v) { try { localStorage.setItem(WKEY, JSON.stringify(v)); } catch (e) { /* private mode */ } }
  function toast(html) {
    var t = document.querySelector('.scr-toast');
    if (!t) { t = document.createElement('div'); t.className = 'scr-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.innerHTML = html; t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('on'); }, 5200);
  }
  function star(b) {
    var sym = b.closest('.scr-row').getAttribute('data-sym'), on = !following[sym];
    following[sym] = on;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); b.textContent = on ? '★' : '☆';
    var r = DATA && DATA.t.find(function (x) { return x.sym === sym; }), short = r ? r.s : sym;
    if (acct) {
      window.BPAuth.follow(sym, on).then(function (j) {
        if (!j.ok) { following[sym] = !on; draw(); toast(esc(j.error || "That didn't save. Try again.")); return; }
        toast(on ? 'Following ' + esc(short) + '. You&#39;ll get an email the evening its light flips. <a href="' + esc(ME) + '">My Puck</a>' : 'Stopped following ' + esc(short) + '.');
      });
      return;
    }
    var w = localGet();
    w.items = w.items.filter(function (x) { return x.sym !== sym; });
    if (on) w.items.push({ sym: sym });
    localSet(w);
    toast(on ? 'Saved ' + esc(short) + ' to this browser. <a href="' + esc(ME) + '">Create a free account</a> to get an email when its light flips.' : 'Removed ' + esc(short) + '.');
  }
  function loadFollowing() {
    localGet().items.forEach(function (x) { following[x.sym] = true; });
    if (acct) return window.BPAuth.me().then(function (a) { if (a && a.signed_in) { following = {}; (a.follow || []).forEach(function (s) { following[s] = true; }); } });
    return Promise.resolve();
  }

  // ---------------------------------------------------------------- start
  var p = new URLSearchParams(location.search);
  Object.keys(DEF).forEach(function (k) {
    if (!p.has(k)) return;
    var v = p.get(k);
    if (k === 'min') S.min = Math.max(0, Math.min(100, Math.round((+v || 0) / 5) * 5));
    else if (k === 'fresh') S.fresh = v === '1';
    else if (k === 'side') S.side = v === 'sell' ? 'sell' : 'buy';
    else S[k] = v;
  });
  if (location.protocol === 'file:') return;
  Promise.all([fetch(SRC).then(function (r) { return r.json(); }), loadFollowing()]).then(function (res) {
    DATA = res[0];
    FAMS = DATA.fam.map(function (f) { return f[1]; });
    paintControls();
    draw();
  }).catch(function () { /* the server-rendered first page stays */ });
})();
