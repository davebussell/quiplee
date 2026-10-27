/* artmine.js: the articles hub for a signed-in reader (loaded after mine.js and plays.js).
 *
 * Signed in, the hub shows only what's about My stocks: a brief per stock (with your signal on it) and the pieces
 * that mention them, from data/articles.json (articles.py index_json: every piece with the stocks it links to).
 * A switch shows every article again; the choice is kept per browser (bp.art.view). Signed out, the hub is as it was. */
(function () {
  'use strict';
  var box = document.querySelector('[data-art-mine]'), M = window.BPMine, PS = window.BPPlays;
  if (!box || !M || location.protocol === 'file:') return;
  var KEY = 'bp.art.view', ROOT = box.getAttribute('data-root') || '/';
  var IDX = null, R = null;
  var SIG = { '1': ['Buy', 'buy'], '0': ['Hold', 'hold'], '-1': ['Sell', 'sell'] };
  function lget() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function lset(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* private mode */ } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function getJSON(u) { return fetch(u, { credentials: 'same-origin' }).then(function (r) { return r.json(); }); }
  function view() { return lget() === 'all' ? 'all' : 'mine'; }

  // your signal on a stock: your weights once plays.js has loaded, else the standard one from reads.json
  function sig(s) {
    if (PS && PS.loaded() && PS.data().x[s]) { var r = PS.score(s); return { s: r.s, sig: r.sig }; }
    var t = R.t[s];
    return t && t.sc != null ? { s: t.sc, sig: t.S } : { s: null, sig: null };
  }
  function pill(r) {
    var w = r && r.sig != null ? SIG[String(r.sig)] : null;
    return w ? '<span class="sig-pill ' + w[1] + '">' + w[0] + '</span> <b class="sig-n ' + w[1] + '">' + r.s + '</b>' : '<span class="sig-pill na">–</span>';
  }
  function apply() {
    var mine = M.list().filter(function (s) { return R.t[s]; }), v = mine.length ? view() : 'all';
    [].forEach.call(document.querySelectorAll('[data-art-all]'), function (el) { el.hidden = v === 'mine'; });
    [].forEach.call(box.querySelectorAll('[data-art-view]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-art-view') === v)); });
    var body = box.querySelector('[data-art-body]');
    if (body) body.hidden = v !== 'mine';
  }
  function draw() {
    if (!IDX || !R) return;
    var mine = M.list().filter(function (s) { return R.t[s]; });
    var have = {};
    mine.forEach(function (s) { have[s] = true; });
    if (!mine.length) {
      box.innerHTML = '<div class="sec-head"><h2 class="h2">About your stocks</h2><p>Add stocks to My stocks and this page leads with a brief on each one and the pieces that mention them.</p></div>' +
        '<p><a class="btn" href="' + esc(ROOT) + 'me/#find">Find stocks to add</a></p>';
      box.hidden = false;
      apply();
      return;
    }
    var briefs = mine.slice().sort(function (a, b) { return R.t[a].s.localeCompare(R.t[b].s); }).map(function (s) {
      // the line that says where your signal would change, else the first that isn't the plays count shown above it
      var t = R.t[s], lines = t.read || [];
      var read = lines.filter(function (l) { return /^Your signal/.test(l); })[0] || lines.filter(function (l) { return !/plays hold/.test(l); })[0] || '';
      return '<a class="card art-card art-brief" href="' + esc(ROOT + IDX.bf.replace('{u}', t.u)) + '"><span class="eyebrow">Brief · rebuilt nightly</span>' +
        '<span class="name">' + esc(t.s) + ' <span class="muted">' + esc(t.n) + '</span></span>' +
        '<span class="art-sig">' + pill(sig(s)) + (t.of ? ' <span class="muted small">' + t.k + ' of ' + t.of + ' plays hold it</span>' : '') + '</span>' +
        (read ? '<span class="muted small">' + esc(read) + '</span>' : '') + '</a>';
    }).join('');
    var bucket = {};
    (IDX.b || []).forEach(function (x) { bucket[x[0]] = x[1]; });
    var pieces = IDX.a.map(function (a) { return { a: a, hit: a[5].filter(function (s) { return have[s]; }) }; })
      .filter(function (x) { return x.hit.length; })
      // most about your stocks first: a sector brief with three of yours beats a 300-name table with ten
      .sort(function (x, y) { return y.hit.length / Math.sqrt(y.a[5].length) - x.hit.length / Math.sqrt(x.a[5].length); });
    var cards = pieces.map(function (x) {
      var a = x.a, names = x.hit.map(function (s) { return R.t[s].s; });
      var kind = a[0].indexOf('/sectors/') >= 0 ? 'Sector brief' : (bucket[a[3]] || 'Article');
      return '<a class="card art-card" href="' + esc(ROOT + a[0]) + '"><span class="eyebrow">' + esc(kind) + (a[4] === 'live' ? ' · live' : '') + '</span>' +
        '<span class="name">' + esc(a[1]) + '</span><span class="muted small">' + esc(a[2]) + '</span>' +
        '<span class="art-hits small">Mentions ' + esc(names.slice(0, 6).join(', ') + (names.length > 6 ? ' and ' + (names.length - 6) + ' more' : '')) + '</span></a>';
    }).join('');
    box.innerHTML = '<div class="sec-head"><h2 class="h2">About your stocks</h2><p>A brief on each of the ' + mine.length + ' stocks in My stocks, and every piece that mentions them.</p></div>' +
      '<div class="mine-bar" role="group" aria-label="Which articles to show"><button type="button" class="chip-btn" data-art-view="mine">★ Your stocks</button>' +
      '<button type="button" class="chip-btn" data-art-view="all">All articles</button></div>' +
      '<div data-art-body><h3 class="h3 art-sub">Briefs</h3><div class="grid grid-3">' + briefs + '</div>' +
      '<h3 class="h3 art-sub">Pieces that mention your stocks</h3>' +
      (cards ? '<div class="grid grid-3">' + cards + '</div>' : '<p class="muted">None of this week’s pieces mention your stocks. Their briefs above are rebuilt every night.</p>') + '</div>';
    box.hidden = false;
    apply();
  }
  box.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-art-view]') : null;
    if (!b) return;
    lset(b.getAttribute('data-art-view'));
    apply();
    if (b.getAttribute('data-art-view') === 'mine') box.scrollIntoView({ block: 'start' });
  });

  M.ready(function () {
    if (!M.signedIn()) return;                 // signed out: the hub as it was
    Promise.all([getJSON(box.getAttribute('data-src')), getJSON(box.getAttribute('data-reads'))]).then(function (res) {
      IDX = res[0];
      R = res[1];
      draw();
      M.onChange(draw);
      if (PS) { PS.ready(draw); PS.onChange(draw); }
    }).catch(function () { /* the hub as it was */ });
  });
})();
