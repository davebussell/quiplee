/* playview.js: a stock page under the play filter (plays.js). It redraws Your signal
 * (score, Buy/Hold/Sell, why, and the factor-by-factor breakdown) for the reader's
 * weights. With the reader's own choice of plays, it recounts the Plays in tile, picks
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
  var grid = top && top.querySelector('.tp-grid'), grid0 = grid ? grid.innerHTML.replace(/ rv(-in)?\b/g, '') : '';   // without the fade-in classes, so a redraw never comes back hidden
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

  // ------------------------------------------------------------ your signal
  var card = document.getElementById('your-signal');
  // a factor's value as a plain phrase about the stock: the same words as factors.friendly (keep the two in step)
  function numIn(v) {
    var m = String(v == null ? '' : v).match(/([+\-\u2212]?)(\d[\d,]*\.?\d*)/);
    if (!m) return null;
    var x = parseFloat(m[2].replace(/,/g, ''));
    return m[1] === '-' || m[1] === '\u2212' ? -x : x;
  }
  function friendly(k, v) {
    v = v == null ? '' : String(v);
    var x = numIn(v), ax = x == null ? null : Math.abs(x);
    var a = ax == null ? null : (ax >= 10 || ax % 1 === 0 ? Math.round(ax).toLocaleString('en-US') : ax.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
    var up = (x || 0) >= 0, word;
    switch (k) {
      case 'plays': return v + ' of the plays own it';
      case 'offhigh': return v.indexOf('at ') === 0 ? 'it\u2019s at its high of the past year' : 'it\u2019s ' + (x != null && Math.abs(x) < 15 ? 'only ' : '') + a + '% below its high of the past year';
      case 'trend': return !x ? 'it\u2019s right at its average price of the last 200 days' : 'it\u2019s ' + a + '% ' + (x > 0 ? 'above' : 'below') + ' its average price of the last 200 days';
      case 'mom': return 'it\u2019s ' + (up ? 'up' : 'down') + ' ' + a + '% over the past year';
      case 'upside': return x != null && Math.abs(x) < 3 ? 'analysts\u2019 average target is close to the price' : 'analysts\u2019 average target is ' + a + '% ' + ((x || 0) > 0 ? 'above' : 'below') + ' the price';
      case 'rating': word = v.indexOf('\u00b7') >= 0 ? v.split('\u00b7').pop().trim() : v; return 'analysts rate it a ' + word + ' on average';
      case 'pe': return v === 'loss' ? 'it\u2019s losing money' : 'it costs ' + a + ' times its yearly profit';
      case 'fpe': return v.indexOf('loss') >= 0 ? 'it\u2019s expected to lose money next year' : 'it costs ' + a + ' times next year\u2019s expected profit';
      case 'peg': return 'its price for its growth (PEG) is ' + v;
      case 'ps': return 'it costs ' + a + ' times its yearly sales';
      case 'pb': return v.indexOf('negative') >= 0 ? 'its book value is negative' : 'it costs ' + a + ' times its book value';
      case 'dy': return v === 'none' ? 'it pays no dividend' : 'it pays a ' + v + ' dividend';
      case 'eg': return (x || 0) <= -100 ? 'its profit fell sharply over the year (' + v + ')' : 'its profit ' + (up ? 'grew' : 'fell') + ' ' + a + '% over the year';
      case 'rg': return 'its sales ' + (up ? 'grew' : 'fell') + ' ' + a + '% over the year';
      case 'pm': return (x || 0) < 0 ? 'it loses money on its sales' : 'it keeps ' + a + ' cents of every sales dollar as profit';
      case 'roe': return (x || 0) < 0 ? 'it loses money on its shareholders\u2019 equity' : 'it earns ' + a + '% a year on its shareholders\u2019 equity';
      case 'de': return v.indexOf('negative') >= 0 ? 'its debts are bigger than its assets' : 'it carries ' + ((x || 0) < 0.5 ? 'little' : (x || 0) < 1.5 ? 'moderate' : 'heavy') + ' debt (' + v + ' its equity)';
      case 'calm': word = v.indexOf('\u00b7') >= 0 ? v.split('\u00b7').pop().trim() : ''; return word ? 'its crash exposure is ' + word + ' (' + v.split('\u00b7')[0].trim() + ')' : 'its crash exposure is ' + v;
    }
    return k + ' is ' + v;
  }
  function why(r, W) {
    var have = r.parts.filter(function (p) { return p.p != null && !p.stood; });
    if (r.s == null) {
      var miss = r.parts.filter(function (p) { return p.p == null && !p.stood; }).map(function (p) { return p.n; });
      return miss.length ? 'Not enough data for these weights: ' + H.s + ' has no ' + miss.slice(0, 4).join(', ') + '.' : 'Weight at least one factor to get a score.';
    }
    var out;
    if (r.held) out = P.heldWords(r, W);                     // the sticky rule holds the call (factors.held_words)
    else {
      var where = r.sig === 1 ? 'at or above your Buy line of ' + W.buy : r.sig === -1 ? 'at or below your Sell line of ' + W.sell
        : 'between your Sell line (' + W.sell + ') and Buy line (' + W.buy + ')';
      out = P.sigWord(r.sig) + ': ' + H.s + ' scores ' + r.s + ' out of 100, ' + where + '.';
    }
    if (have.length === 1) return out + ' It rests on one thing: ' + friendly(have[0].k, have[0].v) + '.';
    // the same pick as factors.why: max/min keep the first of equal points
    var hi = have.reduce(function (a, b) { return b.p > a.p ? b : a; }), lo = have.reduce(function (a, b) { return b.p < a.p ? b : a; });
    var upw = hi.p >= 50 ? 'What helps most: ' : 'Even its best point is weak: ', dnw = lo.p < 50 ? 'What holds it back: ' : 'Its weakest point: ';
    return out + ' ' + upw + friendly(hi.k, hi.v) + '. ' + dnw + friendly(lo.k, lo.v) + '.';
  }
  function drawSignal(D) {
    if (!card || !D.x[H.sym]) return;
    var r = P.score(H.sym), W = P.weights();
    var b = card.querySelector('[data-sig-badge]');
    b.className = 'sig-badge ' + P.sigClass(r.sig);
    b.textContent = P.sigWord(r.sig);
    card.querySelector('[data-sig-score]').textContent = r.s == null ? '–' : r.s;
    var z = card.querySelectorAll('[data-sig-scale] .sig-zone'), dot = card.querySelector('[data-sig-scale] .sig-dot');
    if (z.length === 3) { z[0].style.width = W.sell + '%'; z[1].style.width = (W.buy - W.sell) + '%'; z[2].style.width = (100 - W.buy) + '%'; }
    if (dot) { dot.style.left = (r.s == null ? 50 : r.s) + '%'; dot.hidden = r.s == null; }
    card.querySelector('[data-sig-why]').textContent = why(r, W);
    // the market guard line (its words come from the build: which market, how far below its high); shown while a weighted factor stands down
    var gl = card.querySelector('[data-sig-state]');
    if (gl) gl.hidden = !(r.guard && r.parts.some(function (q) { return q.stood; }));
    var tl = card.querySelector('[data-sig-tested]');
    if (tl) {
      var share = P.tested(r.parts), un = r.parts.filter(function (q) { var f = D.fx.filter(function (x) { return x.k === q.k; })[0]; return q.p != null && !q.stood && !(f && f.r && !f.r.why); }).map(function (q) { return q.n; });
      tl.textContent = (P.migrated() ? 'The standard weights changed on Oct 13, 2026: you’re now on the new ones. ' : '') +
        (share == null ? '' : share >= 0.995 ? 'Every factor in this score has a tested record: each was checked month by month since ' + D.gs + ' on numbers public at the time.'
          : share < 0.005 ? 'None of this score rests on a factor with a tested record.'
          : Math.round(100 * share) + '% of this score rests on factors with a tested record; the rest (' + un.join(', ') + ') has none.');
      tl.classList.toggle('warn', share != null && share < 0.75);
    }
    var fe = card.querySelector('[data-sig-flip]');
    if (fe) { var pin = D.pi && D.pi[H.sym]; fe.textContent = pin ? P.flipWords(P.flips(H.sym), H.cur || '$', pin.p) : ''; }
    card.querySelector('[data-sig-rows]').innerHTML = r.parts.map(function (p) {
      return '<tr' + (p.stood ? ' class="sig-stood"' : '') + '><td>' + esc(p.n) + (p.stood ? ' <small class="muted">stands down</small>' : '') + '</td><td>' + esc(p.v == null ? '–' : p.v) + '</td><td class="r">' + (p.p == null ? '–' : p.p) + '</td><td class="r">' + p.w + '</td><td class="r">' + (p.add == null ? '–' : p.add) + '</td></tr>';
    }).join('');
    var pr = card.querySelector('tr[data-sig-f="plays"]');
    if (pr) { var c = P.count(H.sym), v = c.n ? Math.round(100 * c.k / c.n) : null; pr.cells[1].textContent = v == null ? '–' : v + '%'; pr.cells[2].textContent = v == null ? '–' : v; }
  }

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
      var href = (H.keep || []).indexOf(p.s) >= 0 ? H.pair.replace('{s}', p.s) : '#play-' + p.s;
      cards += '<a class="card tp" data-fam="' + f[0] + '" href="' + esc(href) + '"><span class="tp-fam">' + (icons[f[0]] || '') + esc(f[1]) + '</span>' +
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
    drawSignal(D);
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
    [].forEach.call(document.querySelectorAll('tr[data-ps-play]'), function (tr) {
      var slug = tr.getAttribute('data-ps-play');
      tr.hidden = !showAll && !P.onSlug(slug) && slug !== focus;
      if (slug === focus) { var g = document.querySelector('tr[data-ps-grp="' + tr.getAttribute('data-fam') + '"]'); if (g) g.hidden = false; }
    });
    if (allSub) {
      allSub.innerHTML = all ? allSub0 : (showAll ? 'All ' + D.plays.length + ' plays, by family. <button type="button" class="linkish" data-ps-mine>Show only your ' + P.size() + '</button>'
        : 'Your ' + P.size() + ' of the ' + D.plays.length + ' plays, by family. <button type="button" class="linkish" data-ps-every>Show all ' + D.plays.length + '</button>');
    }
  }
  // a link to one play on this stock (#play-<slug>, or ?play=<slug> from a retired stock x play
  // address): show its row even if the reader's filter hides it, scroll to it and mark it
  var focus = null;
  function wanted() {
    var m = /[?&]play=([a-z0-9-]+)/.exec(location.search), h = /^#play-([a-z0-9-]+)$/.exec(location.hash);
    return m ? m[1] : h ? h[1] : null;
  }
  function goTo(slug, smooth) {
    var tr = slug && document.getElementById('play-' + slug);
    if (!tr) return;
    focus = slug;
    tr.hidden = false;
    var g = document.querySelector('tr[data-ps-grp="' + (tr.getAttribute('data-fam') || '') + '"]');
    if (g) g.hidden = false;
    [].forEach.call(document.querySelectorAll('tr.ps-focus'), function (x) { x.classList.remove('ps-focus'); });
    tr.classList.add('ps-focus');
    if (/[?&]play=/.test(location.search) && history.replaceState) history.replaceState(null, '', location.pathname + '#play-' + slug);
    setTimeout(function () { tr.scrollIntoView({ block: 'center', behavior: smooth ? 'smooth' : 'auto' }); }, smooth ? 0 : 60);
  }
  window.addEventListener('hashchange', function () { goTo(wanted(), true); });
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-ps-every], [data-ps-mine]');
    if (!b) return;
    showAll = b.hasAttribute('data-ps-every');
    draw();
  });
  P.ready(function (D) { draw(D); goTo(wanted(), false); });
  P.onChange(function () { showAll = false; draw(); });
})();
