/* theory.js: the Theory tester (/theory/). Pick a stock and a theory (one play, a
 * family of plays or all of them) and get the reading, the rationale and every
 * play's reason to buy or not, one at a time. Data: the page's #th-data (the plays,
 * the families and every covered name) and data/theory/<slug>.json per stock,
 * written by tools/qstrat/theory.py, whose markup this mirrors.
 * URL: ?s=<stock slug>&t=all|fam:<family>|play:<play slug> */
(function () {
  'use strict';
  var app = document.getElementById('th-app');
  if (!app) return;
  var META = JSON.parse(document.getElementById('th-data').textContent);
  var P = META.plays, FAM = {}, NAMES = META.names;
  var FIC = {};
  META.fams.forEach(function (f) { FAM[f[0]] = f[1]; FIC[f[0]] = f[2] || ''; });
  var SRC = app.getAttribute('data-src'), VER = app.getAttribute('data-v'), STOCK = app.getAttribute('data-stock');
  var out = document.getElementById('th-out'), qIn = document.getElementById('th-q'), sug = document.getElementById('th-sug');
  var sel = document.getElementById('th-theory');
  var cache = {}, D = null, S = { slug: META['default'], theory: 'all', side: 'in', pos: 0, list: [] }, timer = null;

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
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function day(s) { if (!s) return ''; var p = s.split('-'); return MON[+p[1] - 1] + ' ' + (+p[2]) + ', ' + p[0]; }
  function dir(v) { return v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''; }

  // ---------------------------------------------------------------- the theory
  function pick(theory) {
    var all = P.map(function (_, i) { return i; });
    if (theory.indexOf('play:') === 0) { var i = P.findIndex(function (m) { return m.p === theory.slice(5); }); return i >= 0 ? [i] : all; }
    if (theory.indexOf('fam:') === 0) return all.filter(function (i) { return P[i].f === theory.slice(4); });
    return all;
  }
  function order(idx) {
    return idx.slice().sort(function (a, b) {
      var A = (D.x[a].ok + 1) / (D.x[a].nc + 2), B = (D.x[b].ok + 1) / (D.x[b].nc + 2);
      return B - A || (P[a].name < P[b].name ? -1 : 1);
    });
  }

  function verdict() {
    var idx = pick(S.theory), ins = idx.filter(function (i) { return D.x[i].s === 1; }), outs = idx.filter(function (i) { return D.x[i].s === 0; });
    var n = ins.length + outs.length, share = n ? ins.length / n : 0, word, cls, line, label;
    if (S.theory.indexOf('play:') === 0) {
      var m = P[idx[0]], st = D.x[idx[0]].s;
      word = st === 1 ? 'Buy' : st === 0 ? "Don't buy" : 'No call yet'; cls = st === 1 ? 'buy' : st === 0 ? 'no' : 'split';
      line = esc(m.name) + ' ' + (st === 1 ? 'holds' : st === 0 ? 'is out of' : 'has no call on') + ' ' + esc(D.s) + ' tonight.';
      label = m.name;
    } else {
      word = share >= 0.6 ? 'Buy' : share <= 0.4 ? "Don't buy" : 'Split'; cls = share >= 0.6 ? 'buy' : share <= 0.4 ? 'no' : 'split';
      var fam = S.theory === 'all' ? null : FAM[S.theory.slice(4)];
      label = fam ? fam + ' plays' : 'All the plays';
      line = '<b>' + ins.length + ' of ' + n + '</b> ' + (fam ? esc(fam.toLowerCase()) + ' plays' : 'plays') + ' say buy ' + esc(D.s) + ' tonight; ' + outs.length + " say don&#39;t.";
      if (!fam && D.L != null) line += ' The Start/Stop light is on <b>' + (D.L === 1 ? 'Start' : 'Stop') + '</b>.';
    }
    return '<div class="th-verdict ' + cls + '"><p class="th-step"><span class="step-n">3</span>The reading</p>' +
      '<p class="th-q">' + esc(label) + ' on <b>' + esc(D.s) + '</b> <span class="muted">· ' + esc(D.n) + ', ' + money(D.p, D.c) + '</span></p>' +
      '<p class="th-big">' + esc(word) + '</p><p class="th-line">' + line + '</p>' +
      (S.theory.indexOf('play:') === 0 ? '' : '<div class="th-meter" aria-hidden="true"><i style="width:' + Math.round(100 * share) + '%"></i></div>' +
      '<div class="th-meter-l"><span>Buy ' + ins.length + '</span><span>Don&#39;t buy ' + outs.length + '</span></div>') + '</div>';
  }

  function card(i) {
    var m = P[i], x = D.x[i], st = x.s, cls = st === 1 ? 'in' : st === 0 ? 'out' : 'none';
    var say = st === 1 ? 'Says buy' : st === 0 ? "Says don't buy" : 'No call yet';
    var rule = st === 1 ? m.rin : st === 0 ? m.rout : 'Not enough price history yet for this play to make a call.';
    var why = esc(rule) + (x.rd ? ' <span class="th-rd">Tonight: ' + esc(x.rd) + '.</span>' : '');
    var checks = x.ck && x.ck.length ? '<dt>Checks</dt><dd><ul class="checks">' + x.ck.map(function (c) {
      return '<li><span class="' + (c[1] ? 'ok' : 'no') + '">' + (c[1] ? '✓' : '✕') + '</span>' + esc(c[0]) + '</li>'; }).join('') + '</ul></dd>' : '';
    var since = st != null && x.d ? '<dt>Since</dt><dd>Has said ' + (st === 1 ? 'buy' : 'don&#39;t buy') + ' since ' + day(x.d) +
      (x.dp ? ', at ' + money(x.dp, D.c) + '. ' + esc(D.s) + ' has moved <b class="' + dir(x.mv) + '">' + pct(x.mv) + '</b> since.' : '.') + '</dd>' : '';
    var nxt = x.nx ? '<dt>Changes its mind</dt><dd>' + esc(x.nx) + (x.ds != null ? ' <span class="muted">(' + pct(x.ds) + ' from tonight&#39;s close)</span>' : '') + '</dd>' : '';
    var rec = '';
    if (x.nc) {
      rec = 'Right on ' + x.ok + ' of ' + x.nc + ' calls.';
      if (x.cg != null && x.bc != null && x.y) rec += ' ' + pct(x.cg) + ' a year, against ' + pct(x.bc) + ' for buying and holding, since ' + x.y + '.';
      rec = '<dt>Its record on ' + esc(D.s) + '</dt><dd>' + rec + '</dd>';
    }
    var href = STOCK + D.u + '/' + m.p + '/';
    return '<article class="th-card ' + cls + '"><header class="th-card-h"><span class="th-say ' + cls + '">' + say + '</span>' +
      '<a class="th-name" href="' + esc(href) + '">' + esc(m.name) + '</a><span class="th-by">' + (FIC[m.f] || '') + esc(FAM[m.f]) + ' · ' + esc(m.by) + '</span></header>' +
      '<p class="th-idea">' + esc(m.idea) + '</p><dl class="th-why"><dt>Why</dt><dd>' + why + '</dd>' + checks + since + nxt + rec + '</dl>' +
      '<a class="th-more" href="' + esc(href) + '">Chart and every call</a></article>';
  }

  function lists() {
    var idx = S.theory.indexOf('play:') === 0 ? P.map(function (_, i) { return i; }) : pick(S.theory);
    return {
      'in': order(idx.filter(function (i) { return D.x[i].s === 1; })),
      'out': order(idx.filter(function (i) { return D.x[i].s === 0; }))
    };
  }

  function roll() {
    var L = lists();
    if (!L[S.side].length) S.side = S.side === 'in' ? 'out' : 'in';
    S.list = L[S.side];
    if (S.pos >= S.list.length) S.pos = 0;
    var single = S.theory.indexOf('play:') === 0 ? pick(S.theory)[0] : null;
    var lead = single != null ? '<div class="th-solo">' + card(single) + '</div>' : '';
    var items = S.list.map(function (i, k) {
      var x = D.x[i];
      return '<li><button type="button" data-i="' + k + '"' + (k === S.pos ? ' aria-current="true"' : '') + '><span class="th-li-n">' + esc(P[i].name) + '</span>' +
        '<span class="th-li-m">' + esc(FAM[P[i].f]) + ' · ' + (x.nc ? 'right ' + x.ok + '/' + x.nc : 'no closed calls yet') + '</span></button></li>';
    }).join('');
    return lead + '<div class="th-roll" id="th-roll"><p class="th-step"><span class="step-n">4</span>' + (single != null ? 'How the other plays see it' : 'Roll through every reason') + '</p>' +
      '<div class="th-tabs" role="tablist"><button type="button" role="tab" data-side="in" aria-selected="' + (S.side === 'in') + '">Reasons to buy <b>' + L['in'].length + '</b></button>' +
      '<button type="button" role="tab" data-side="out" aria-selected="' + (S.side === 'out') + '">Reasons not to <b>' + L['out'].length + '</b></button></div>' +
      '<div class="th-body"><div class="th-stage" aria-live="polite">' + (S.list.length ? card(S.list[S.pos]) : '<p class="muted">No play has a call on this stock yet.</p>') +
      '<div class="th-nav"><button type="button" class="btn sm" data-go="-1" aria-label="Previous reason">←</button>' +
      '<span class="th-pos">' + (S.list.length ? S.pos + 1 : 0) + ' of ' + S.list.length + '</span><button type="button" class="btn sm" data-go="1" aria-label="Next reason">→</button>' +
      '<button type="button" class="btn sm th-auto" aria-pressed="' + (!!timer) + '">' + (timer ? '❚❚ Pause' : '▶ Roll through') + '</button></div></div>' +
      '<ol class="th-list">' + items + '</ol></div>' +
      '<p class="small muted th-order">Best record on ' + esc(D.s) + ' first. A play agrees with buying when it holds the stock tonight.</p></div>';
  }

  function draw() {
    if (!D) return;
    out.innerHTML = verdict() + roll();
    wireRoll();
  }
  // only the card, the counter and the list's current marker change when stepping
  function step() {
    var stage = out.querySelector('.th-stage');
    if (!stage || !S.list.length) return;
    var old = stage.querySelector('.th-card');
    var tmp = document.createElement('div'); tmp.innerHTML = card(S.list[S.pos]);
    stage.replaceChild(tmp.firstChild, old);
    stage.querySelector('.th-pos').textContent = (S.pos + 1) + ' of ' + S.list.length;
    [].forEach.call(out.querySelectorAll('.th-list button'), function (b) {
      var on = +b.getAttribute('data-i') === S.pos;
      if (on) { b.setAttribute('aria-current', 'true'); } else b.removeAttribute('aria-current');
    });
    var cur = out.querySelector('.th-list [aria-current]');
    var list = out.querySelector('.th-list');
    if (cur && list && list.scrollHeight > list.clientHeight) list.scrollTop = cur.parentNode.offsetTop - list.offsetTop - 40;
  }
  function go(d) { if (!S.list.length) return; S.pos = (S.pos + d + S.list.length) % S.list.length; step(); }
  function stopAuto() {
    if (!timer) return;
    clearInterval(timer); timer = null;
    var b = out.querySelector('.th-auto'); if (b) { b.setAttribute('aria-pressed', 'false'); b.textContent = '▶ Roll through'; }
  }
  function wireRoll() {
    var r = out.querySelector('#th-roll');
    if (!r) return;
    r.addEventListener('click', function (ev) {
      var t = ev.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-side')) { stopAuto(); S.side = t.getAttribute('data-side'); S.pos = 0; draw(); return; }
      if (t.hasAttribute('data-go')) { stopAuto(); go(+t.getAttribute('data-go')); return; }
      if (t.hasAttribute('data-i')) { stopAuto(); S.pos = +t.getAttribute('data-i'); step(); return; }
      if (t.classList.contains('th-auto')) {
        if (timer) { stopAuto(); return; }
        timer = setInterval(function () { go(1); }, 4200);
        t.setAttribute('aria-pressed', 'true'); t.textContent = '❚❚ Pause';
      }
    });
    r.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowRight') { stopAuto(); go(1); ev.preventDefault(); }
      if (ev.key === 'ArrowLeft') { stopAuto(); go(-1); ev.preventDefault(); }
    });
  }

  // ---------------------------------------------------------------- state, URL and loading
  function sync() {
    var p = new URLSearchParams(location.search);
    p.set('s', S.slug); if (S.theory === 'all') p.delete('t'); else p.set('t', S.theory);
    history.replaceState(null, '', location.pathname + '?' + p.toString() + location.hash);
    sel.value = S.theory;
    [].forEach.call(app.querySelectorAll('[data-theory]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-theory') === S.theory)); });
  }
  function load(slug) {
    if (cache[slug]) return Promise.resolve(cache[slug]);
    out.classList.add('loading');
    return fetch(SRC + slug + '.json?v=' + VER).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { cache[slug] = j; out.classList.remove('loading'); return j; });
  }
  function setStock(slug) {
    stopAuto();
    return load(slug).then(function (j) {
      D = j; S.slug = slug; S.pos = 0; S.side = 'in';
      qIn.value = D.s + ' · ' + D.n;
      draw(); sync();
    }).catch(function () { out.classList.remove('loading'); out.insertAdjacentHTML('afterbegin', '<p class="me-note warn">That stock didn&#39;t load. Check your connection and try again.</p>'); });
  }
  function setTheory(t) { stopAuto(); S.theory = t; S.pos = 0; S.side = 'in'; draw(); sync(); }

  // ---------------------------------------------------------------- the stock search
  var hits = [], hi = -1;
  function find(q) {
    q = q.trim().toLowerCase().replace(/\s+·.*$/, '');
    if (!q) return [];
    var res = [];
    NAMES.forEach(function (n) {
      var s = n[1].toLowerCase(), nm = n[2].toLowerCase(), sym = n[3].toLowerCase(), score = 0;
      if (s === q || sym === q) score = 100; else if (s.indexOf(q) === 0 || sym.indexOf(q) === 0) score = 60; else if (nm.indexOf(q) === 0) score = 50;
      else if (nm.indexOf(q) >= 0) score = 20;
      if (score) res.push([score, n]);
    });
    res.sort(function (a, b) { return b[0] - a[0] || (a[1][1] < b[1][1] ? -1 : 1); });
    return res.slice(0, 8).map(function (r) { return r[1]; });
  }
  function showSug() {
    hits = find(qIn.value); hi = hits.length ? 0 : -1;
    if (!hits.length) { sug.hidden = true; return; }
    sug.innerHTML = hits.map(function (n, k) {
      return '<li role="option"' + (k === hi ? ' aria-selected="true"' : '') + '><button type="button" data-slug="' + esc(n[0]) + '"><b>' + esc(n[1]) + '</b><span>' + esc(n[2]) + '</span></button></li>';
    }).join('');
    sug.hidden = false;
  }
  function choose(slug) { sug.hidden = true; qIn.blur(); setStock(slug); }
  qIn.addEventListener('focus', function () { qIn.select(); });
  qIn.addEventListener('input', showSug);
  qIn.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      if (!hits.length) return;
      hi = (hi + (ev.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
      [].forEach.call(sug.children, function (li, k) { if (k === hi) li.setAttribute('aria-selected', 'true'); else li.removeAttribute('aria-selected'); });
      ev.preventDefault();
    } else if (ev.key === 'Enter') {
      if (!hits.length) showSug();
      if (hits.length) choose(hits[Math.max(0, hi)][0]);
      ev.preventDefault();
    } else if (ev.key === 'Escape') { sug.hidden = true; }
  });
  sug.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
  sug.addEventListener('click', function (ev) { var b = ev.target.closest('[data-slug]'); if (b) choose(b.getAttribute('data-slug')); });
  qIn.addEventListener('blur', function () { setTimeout(function () { sug.hidden = true; if (D) qIn.value = D.s + ' · ' + D.n; }, 150); });

  [].forEach.call(app.querySelectorAll('[data-pick]'), function (a) {
    a.addEventListener('click', function (ev) { ev.preventDefault(); setStock(a.getAttribute('data-pick')); });
  });
  sel.addEventListener('change', function () { setTheory(sel.value); });
  [].forEach.call(app.querySelectorAll('[data-theory]'), function (b) { b.addEventListener('click', function () { setTheory(b.getAttribute('data-theory')); }); });

  // ---------------------------------------------------------------- start
  var p = new URLSearchParams(location.search);
  var want = p.get('s'), t = p.get('t');
  if (want) {
    var w = want.toLowerCase();
    var hit = NAMES.find(function (n) { return n[0] === w || n[1].toLowerCase() === w || n[3].toLowerCase() === w; });
    want = hit ? hit[0] : null;
  }
  if (t && (t === 'all' || pick(t).length && (t.indexOf('fam:') === 0 ? FAM[t.slice(4)] : P.some(function (m) { return 'play:' + m.p === t; })))) S.theory = t;
  sel.value = S.theory;
  setStock(want || S.slug);
})();
