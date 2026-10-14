/* acctcheck.js: the account check on /watchlist/ (tools/qstrat/accountplan.py writes the data).
 * Runs the reader's own mix, at their own amounts, through the weekly closes since 2006
 * (data/px/<slug>.json) and shows what it did, next to the same mix with a per-stock cap and an
 * index core. Everything runs in the browser; nothing about the list is sent anywhere.
 *
 *   BPAcct.render(box, holdings, base)   holdings: [{sym, s, u, g, w}] with w summing to 1
 */
(function () {
  'use strict';
  var cache = {};
  var CRASH = [['2008–09 crisis', '2007-10-12', '2009-03-06'], ['2020 crash', '2020-02-21', '2020-03-20'], ['2022 fall', '2021-12-31', '2022-10-14']];
  var CORES = [['SPY', 'S&P 500 (SPY)', 'spy'], ['XIU.TO', 'TSX 60 (XIU)', 'xiu-to']];
  var st = { core: 'SPY', cap: 100, coreShare: 0, holdings: null, box: null, base: '../', seq: 0 };

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'on') Object.keys(attrs.on).forEach(function (ev) { n.addEventListener(ev, attrs.on[ev]); });
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function pc(v, d) {
    if (v == null || !isFinite(v)) return '–';
    var t = Math.abs(v * 100).toFixed(d || 0), z = parseFloat(t) === 0;
    return (z ? '' : v < 0 ? '−' : '+') + t + '%';
  }
  function pcu(v) { return v == null ? '–' : Math.round(v * 100) + '%'; }
  function get(slug) {
    if (!cache[slug]) cache[slug] = fetch(st.base + 'data/px/' + slug + '.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return cache[slug];
  }
  function rets(w) {
    var r = new Array(w.length);
    r[0] = null;
    for (var i = 1; i < w.length; i++) r[i] = (w[i] != null && w[i - 1] != null && w[i - 1] > 0) ? w[i] / w[i - 1] - 1 : null;
    return r;
  }
  // weekly return of a fixed-weight mix, reset every week; names that hadn't started trading sit out
  // and the rest are scaled up, as long as at least half the weight is trading
  function mix(parts, n) {
    var out = new Array(n), tot = parts.reduce(function (a, p) { return a + p.w; }, 0);
    for (var i = 0; i < n; i++) {
      var s = 0, ws = 0;
      parts.forEach(function (p) { var r = p.r[i]; if (r != null) { s += p.w * r; ws += p.w; } });
      out[i] = ws >= tot / 2 && ws > 0 ? s / ws : null;
    }
    return out;
  }
  function stats(r, d0, from, to) {
    var i0 = -1;
    for (var i = Math.max(1, from || 1); i < r.length; i++) if (r[i] != null) { i0 = i; break; }
    if (i0 < 0) return null;
    var end = to == null ? r.length - 1 : Math.min(to, r.length - 1);
    var g = 1, peak = 1, dd = 0, wk = 0, path = [1], n = 0;
    for (var j = i0; j <= end; j++) {
      var x = r[j] == null ? 0 : r[j];
      g *= 1 + x; n++;
      if (g > peak) peak = g;
      dd = Math.min(dd, g / peak - 1);
      wk = Math.min(wk, x);
      path.push(g);
    }
    return { start: i0, cagr: n > 26 ? Math.pow(g, 52 / n) - 1 : null, total: g - 1, dd: dd, wk: wk, path: path, years: n / 52 };
  }
  function weekOf(d0, iso) { return Math.round((new Date(iso + 'T12:00:00Z') - new Date(d0 + 'T12:00:00Z')) / (7 * 864e5)); }
  function dateOf(d0, i) { var d = new Date(d0 + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + 7 * i); return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }); }

  function adjusted(holdings, cap, coreShare) {
    var w = {}, excess = 0;
    holdings.forEach(function (h) { var x = h.w * (1 - coreShare); if (x > cap) { excess += x - cap; x = cap; } w[h.sym] = x; });
    return { w: w, core: coreShare + excess };
  }

  function chart(paths, d0, start) {
    var W = 640, H = 280, pad = 6, n = Math.max.apply(null, paths.map(function (p) { return p.path.length; }));
    var all = []; paths.forEach(function (p) { all = all.concat(p.path); });
    var lo = Math.log(Math.min.apply(null, all)), hi = Math.log(Math.max.apply(null, all)), span = hi - lo || 1;
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="acct-chart" role="img" aria-label="Growth of $10,000 in each mix, log scale">';
    [0.25, 0.5, 0.75].forEach(function (f) { var y = pad + f * (H - 2 * pad); svg += '<line x1="0" x2="' + W + '" y1="' + y + '" y2="' + y + '" class="acct-grid"/>'; });
    paths.forEach(function (p) {
      var pts = p.path.map(function (v, i) { return (i / (n - 1) * W).toFixed(1) + ',' + (pad + (1 - (Math.log(v) - lo) / span) * (H - 2 * pad)).toFixed(1); });
      svg += '<polyline fill="none" class="' + p.cls + '" points="' + pts.join(' ') + '"/>';
    });
    svg += '</svg>';
    var w = el('div', { 'class': 'acct-chart-wrap' });
    w.innerHTML = svg;
    w.appendChild(el('div', { 'class': 'acct-chart-axis small muted' }, [el('span', { text: dateOf(d0, start) }), el('span', { text: 'now' })]));
    return w;
  }

  function draw() {
    var box = st.box, H = st.holdings, my = ++st.seq;
    var core = CORES.filter(function (c) { return c[0] === st.core; })[0] || CORES[0];
    var need = H.map(function (h) { return get(h.u); }).concat([get(core[2])]);
    Promise.all(need).then(function (got) {
      if (my !== st.seq) return;
      var cpx = got.pop();
      var have = [], missing = [];
      H.forEach(function (h, i) { if (got[i] && got[i].w) have.push({ h: h, px: got[i] }); else missing.push(h.s); });
      var out = box.querySelector('[data-acct-out]');
      out.innerHTML = '';
      if (!have.length || !cpx) { out.appendChild(el('p', { 'class': 'small muted', text: 'No price history for these names yet.' })); return; }
      var d0 = cpx.d0, n = cpx.w.length, cr = rets(cpx.w);
      var parts = have.map(function (x) { return { sym: x.h.sym, w: x.h.w, r: rets(x.px.w) }; });
      var mine = mix(parts, n);
      var A = adjusted(have.map(function (x) { return x.h; }), st.cap / 100, st.coreShare / 100);
      var adjParts = parts.map(function (p) { return { sym: p.sym, w: A.w[p.sym], r: p.r }; }).concat([{ sym: core[0], w: A.core, r: cr }]);
      var alt = mix(adjParts, n);
      var s1 = stats(mine, d0), from = s1 ? s1.start : 1;
      var s2 = stats(alt, d0, from), s3 = stats(cr, d0, from);
      var changed = st.cap < 100 || st.coreShare > 0;
      var crashes = CRASH.map(function (c) {
        var a = weekOf(d0, c[1]), b = weekOf(d0, c[2]);
        return [c[0], a >= from ? stats(mine, d0, a + 1, b) : null, a >= from ? stats(alt, d0, a + 1, b) : null, stats(cr, d0, a + 1, b)];
      });
      var last = stats(mine, d0, n - 52), lastAlt = stats(alt, d0, n - 52), lastCore = stats(cr, d0, n - 52);
      function row(label, f, a, b, c) { return el('tr', {}, [el('td', { text: label }), el('td', { 'class': 'r', text: f(a) }), el('td', { 'class': 'r', text: changed ? f(b) : '–' }), el('td', { 'class': 'r', text: f(c) })]); }
      var body = el('tbody', {}, [
        row('Yearly return', function (s) { return s ? pc(s.cagr, 1) : '–'; }, s1, s2, s3),
        row('Worst fall', function (s) { return s ? pc(s.dd) : '–'; }, s1, s2, s3),
        row('Worst week', function (s) { return s ? pc(s.wk, 1) : '–'; }, s1, s2, s3),
        row('Last 12 months', function (s) { return s ? pc(s.total) : '–'; }, last, lastAlt, lastCore)
      ].concat(crashes.map(function (c) { return row(c[0], function (s) { return s ? pc(s.total) : 'not held'; }, c[1], c[2], c[3]); })));
      var head = el('thead', {}, [el('tr', {}, [el('th', { text: 'Since ' + dateOf(d0, from) }), el('th', { 'class': 'r', text: 'Your mix' }),
        el('th', { 'class': 'r', text: 'With the changes' }), el('th', { 'class': 'r', text: core[1] + ' alone' })])]);
      out.appendChild(el('div', { 'class': 'tbl-wrap' }, [el('table', { 'class': 'tbl acct-tbl', 'data-nosort': '' }, [head, body])]));
      var lines = [{ path: s1.path, cls: 'acct-l-mine' }, { path: s3.path, cls: 'acct-l-core' }];
      if (changed && s2) lines.splice(1, 0, { path: s2.path, cls: 'acct-l-alt' });
      out.appendChild(chart(lines, d0, from));
      out.appendChild(el('p', { 'class': 'acct-key small' }, [el('i', { 'class': 'k-mine' }), 'Your mix ', changed ? el('i', { 'class': 'k-alt' }) : null, changed ? 'With the changes ' : null, el('i', { 'class': 'k-core' }), core[1]]));
      if (changed && s1 && s2) {
        var top = Math.max.apply(null, have.map(function (x) { return A.w[x.h.sym]; }));
        out.appendChild(el('p', { 'class': 'small', text: 'With ' + (st.coreShare ? st.coreShare + '% in ' + core[1] : 'no core') + (st.cap < 100 ? ' and no name above ' + st.cap + '%' : '') +
          ' (the biggest name ' + pcu(top) + ', the core ' + pcu(A.core) + '), the worst fall would have been ' + pc(s2.dd) + ' instead of ' + pc(s1.dd) +
          ', and the yearly return ' + pc(s2.cagr, 1) + ' instead of ' + pc(s1.cagr, 1) + '.' }));
      }
      var notes = 'Weekly closes, adjusted for splits and dividends, with the mix reset to its amounts every week; no costs or taxes. A name joins when it started trading. Each price is in its own currency.';
      if (missing.length) notes += ' No history yet for ' + missing.join(', ') + '.';
      out.appendChild(el('p', { 'class': 'small muted', text: notes + ' What a mix did isn’t what it will do, and this knows nothing about your goals, timeline or other money.' }));
    });
  }

  function render(box, holdings, base) {
    st.box = box; st.holdings = holdings; st.base = base || '../';
    box.innerHTML = '';
    if (!holdings.length) return;
    var byVal = holdings.byValue;
    // what's in it
    var sorted = holdings.slice().sort(function (a, b) { return b.w - a.w; });
    var eff = 1 / holdings.reduce(function (a, h) { return a + h.w * h.w; }, 0);
    var sect = {};
    holdings.forEach(function (h) { sect[h.g || 'Other'] = (sect[h.g || 'Other'] || 0) + h.w; });
    var sectors = Object.keys(sect).sort(function (a, b) { return sect[b] - sect[a]; });
    var comp = el('div', { 'class': 'acct-comp' }, [
      el('div', {}, [el('p', { 'class': 'eyebrow', text: byVal ? 'By value, in Canadian dollars' : 'Equal amounts (add quantities or values to use yours)' }),
        el('ul', { 'class': 'acct-bars' }, sorted.slice(0, 12).map(function (h) {
          return el('li', {}, [el('span', { 'class': 'acct-n', text: h.s }), el('span', { 'class': 'acct-b' }, [el('i', { style: 'width:' + Math.max(2, Math.round(h.w * 100)) + '%' })]), el('span', { 'class': 'acct-v', text: pcu(h.w) })]);
        }))]),
      el('div', {}, [el('p', { 'class': 'eyebrow', text: 'By sector' }),
        el('ul', { 'class': 'acct-bars' }, sectors.slice(0, 8).map(function (g) {
          return el('li', {}, [el('span', { 'class': 'acct-n', text: g }), el('span', { 'class': 'acct-b' }, [el('i', { style: 'width:' + Math.max(2, Math.round(sect[g] * 100)) + '%' })]), el('span', { 'class': 'acct-v', text: pcu(sect[g]) })]);
        }))])
    ]);
    var top = sorted[0];
    var lede = holdings.length + ' name' + (holdings.length > 1 ? 's' : '') + ', which behave' + (holdings.length > 1 ? '' : 's') + ' like ' + eff.toFixed(1) + ' equal positions. The biggest, ' + top.s + ', is ' + pcu(top.w) +
      '; the biggest sector, ' + sectors[0] + ', is ' + pcu(sect[sectors[0]]) + '.';
    var coreSel = el('select', { id: 'acct-core', on: { change: function () { st.core = this.value; draw(); } } }, CORES.map(function (c) { var o = el('option', { value: c[0], text: c[1] }); if (c[0] === st.core) o.selected = true; return o; }));
    function slider(id, label, min, max, step, val, fmt, set) {
      var o = el('output', { 'for': id, text: fmt(val) });
      var inp = el('input', { type: 'range', id: id, min: min, max: max, step: step, value: val });
      var t = null;
      inp.addEventListener('input', function () { o.textContent = fmt(+this.value); set(+this.value); clearTimeout(t); t = setTimeout(draw, 120); });
      return el('label', { 'class': 'acct-sl', 'for': id }, [el('span', {}, [label, ' ', o]), inp]);
    }
    var controls = el('div', { 'class': 'acct-ctl' }, [
      slider('acct-cap', 'Cap on any one name:', 5, 100, 5, st.cap, function (v) { return v >= 100 ? 'none' : v + '%'; }, function (v) { st.cap = v; }),
      slider('acct-cs', 'In an index core:', 0, 90, 5, st.coreShare, function (v) { return v + '%'; }, function (v) { st.coreShare = v; }),
      el('label', { 'class': 'acct-sl', 'for': 'acct-core' }, [el('span', { text: 'The core' }), coreSel])
    ]);
    box.appendChild(el('div', { 'class': 'card acct', id: 'account' }, [
      el('p', { 'class': 'eyebrow', text: 'Account check' }),
      el('h2', { 'class': 'h2', text: 'How this mix has behaved' }),
      el('p', { 'class': 'small', text: lede }),
      comp,
      el('p', { 'class': 'small muted', text: 'Try a cap on any one name, or an index core, and compare. The excess over a cap goes into the core.' }),
      controls,
      el('div', { 'data-acct-out': '' }, [el('p', { 'class': 'small muted', text: 'Loading the price history…' })]),
      el('p', { 'class': 'small' }, [el('a', { href: st.base + 'guides/plan-an-account/', text: 'What 1 to 30 stocks, a core and caps did across thousands of portfolios' })])
    ]));
    draw();
  }

  window.BPAcct = { render: render };
})();
