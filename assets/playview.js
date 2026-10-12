/* playview.js: a stock page under the play filter (plays.js). With the reader's own
 * choice of plays, it recounts the Plays in tile and the plays + analysts' score, picks
 * the most accurate of those plays in each family (with each one's record on this stock),
 * recounts the family tiles and shows only those plays in the full list.
 * #ps-here (render.py stock_page) carries this stock's record on every play:
 * b[i] = [calls right, finished calls, in/out since], in the order of data/playset.json. */
(function () {
  'use strict';
  var cfg = document.getElementById('ps-here'), P = window.BPPlays;
  if (!cfg || !P) return;
  var H = JSON.parse(cfg.textContent);
  P.here(H);
  var top = document.getElementById('top-plays');
  var grid = top && top.querySelector('.tp-grid'), grid0 = grid ? grid.innerHTML : '';
  var head = top && top.querySelector('#tp-h'), head0 = head ? head.textContent : '';
  var sub = top && top.querySelector('[data-ps-tp-sub]'), sub0 = sub ? sub.innerHTML : '';
  var allSub = document.querySelector('[data-ps-all-sub]'), allSub0 = allSub ? allSub.innerHTML : '';
  var tile = document.querySelector('[data-ps-tile]'), note0 = tile ? tile.querySelector('[data-note]').textContent : '';
  var icons = {}, showAll = false;
  if (grid) [].forEach.call(grid.querySelectorAll('.tp[data-fam]'), function (a) {
    var f = a.querySelector('.tp-fam svg'); icons[a.getAttribute('data-fam')] = f ? f.outerHTML : '';
  });

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pc(v) { return v == null ? '–' : Math.round(v * 100) + '%'; }
  function day(iso) { return iso ? new Date(iso + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }) : ''; }
  function fill(el, k, n) { var i = el && el.querySelector('.fillbar i'); if (i) i.style.width = (n ? Math.round(100 * k / n) : 0) + '%'; }
  function pill(ch) { return ch === '1' ? '<span class="pill in">IN</span>' : ch === '0' ? '<span class="pill out">OUT</span>' : '<span class="pill">–</span>'; }

  function drawTop(D, st) {
    if (!grid) return;
    if (P.isAll()) { grid.innerHTML = grid0; head.textContent = head0; sub.innerHTML = sub0; return; }
    var cards = '';
    D.fams.forEach(function (f) {
      var ix = [];
      D.plays.forEach(function (p, i) { if (p.f === f[0] && P.on(i)) ix.push(i); });
      if (!ix.length) return;
      ix.sort(function (a, b) { var A = D.plays[a], B = D.plays[b]; return (B.e - A.e) || ((B.a || 0) - (A.a || 0)) || (B.c - A.c); });
      var i = ix[0], p = D.plays[i], b = H.b[i] || [0, 0, null], ch = st ? st.charAt(i) : '-';
      var hereTxt = b[1] ? 'On ' + esc(H.s) + ': right ' + b[0] + ' of ' + b[1] : 'No finished calls on ' + esc(H.s) + ' yet';
      var since = (ch === '1' || ch === '0') && b[2] ? (ch === '1' ? 'In' : 'Out') + ' since ' + day(b[2]) : '';
      cards += '<a class="card tp" data-fam="' + f[0] + '" href="' + esc(H.pair.replace('{s}', p.s)) + '"><span class="tp-fam">' + (icons[f[0]] || '') + esc(f[1]) + '</span>' +
        '<span class="tp-name"><b>' + esc(p.n) + '</b>' + pill(ch) + '</span>' +
        '<span class="tp-acc"><b>' + pc(p.a) + '</b> of ' + Number(p.c).toLocaleString('en-US') + ' calls right' + (p.e ? '' : ' <span class="ps-few">few calls</span>') + '</span>' +
        '<span class="tp-here">' + hereTxt + (since ? ' · ' + since : '') + '</span></a>';
    });
    grid.innerHTML = cards;
    head.textContent = 'The most accurate of your plays in each family';
    sub.innerHTML = 'Among the ' + P.size() + ' plays you count: each family’s most accurate, tested on ' + D.n + ' stocks since ' + D.since + ', and what it says about ' + esc(H.s) + ' now. ' +
      '<button type="button" class="linkish" data-ps-open>Change your plays</button>';
  }

  function draw() {
    var D = P.data();
    if (!D) return;
    var c = P.count(H.sym), all = P.isAll(), st = D.t[H.sym];
    if (tile) {
      tile.querySelector('[data-k]').textContent = c.k;
      tile.querySelector('[data-n]').textContent = c.n;
      fill(tile, c.k, c.n);
      tile.querySelector('[data-note]').textContent = all ? note0 : 'Of the ' + P.size() + ' plays you count: ' + P.label(true) + '.';
    }
    var sc = document.querySelector('[data-ps-score]');
    if (sc && H.upp != null) {
      var v = Math.round(100 * (H.tw * (c.n ? c.k / c.n : 0) + (1 - H.tw) * H.upp));
      sc.querySelector('[data-v]').textContent = v;
      fill(sc, v, 100);
    }
    drawTop(D, st);
    // the family tiles and the full list
    D.fams.forEach(function (f, fi) {
      var t = document.querySelector('[data-ps-ftile="' + f[0] + '"]');
      if (!t) return;
      var k = c.f[fi][0], n = c.f[fi][1], any = false;
      D.plays.forEach(function (p, i) { if (p.f === f[0] && P.on(i)) any = true; });
      t.querySelector('[data-k]').textContent = k;
      t.querySelector('[data-n]').textContent = n;
      fill(t, k, n);
      t.classList.toggle('ps-none', !any);
      var g = document.querySelector('tr[data-ps-grp="' + f[0] + '"]');
      if (g) g.hidden = !any && !showAll;
    });
    [].forEach.call(document.querySelectorAll('tr[data-ps-play]'), function (tr) { tr.hidden = !showAll && !P.onSlug(tr.getAttribute('data-ps-play')); });
    if (allSub) {
      allSub.innerHTML = all ? allSub0 : (showAll ? 'All ' + D.plays.length + ' plays, by family. <button type="button" class="linkish" data-ps-mine>Show only your ' + P.size() + '</button>'
        : 'Your ' + P.size() + ' of the ' + D.plays.length + ' plays, by family. <button type="button" class="linkish" data-ps-every>Show all ' + D.plays.length + '</button>');
    }
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-ps-every], [data-ps-mine]');
    if (!b) return;
    showAll = b.hasAttribute('data-ps-every');
    draw();
  });
  P.ready(draw);
  P.onChange(function () { showAll = false; draw(); });
})();
