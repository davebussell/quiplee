/* widgets.js — Be The Puck's interactive pieces beyond the line charts in site.js:
 *   [data-candles]   candlestick chart with volume, range buttons and overlay toggles
 *   [data-heatmap]   every play's call, week by week (canvas)
 *   [data-sim]       what-if positioning simulator (Markets)
 *   [data-widget]    Learn widgets: slice, orderbook, pe, stress, candle, maplay, bestdays
 * Each reads its data from a <script type="application/json"> referenced by the
 * element's attribute, draws with SVG or canvas, and redraws on resize. */
(function () {
  'use strict';
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function css(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function svgEl(tag, attrs, parent) {
    var n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'html') n.innerHTML = attrs[k];
      else if (k === 'on') for (var ev in attrs.on) n.addEventListener(ev, attrs.on[ev]);
      else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function data(node, attr) {
    var id = node.getAttribute(attr);
    var s = id && document.getElementById(id);
    return s ? JSON.parse(s.textContent) : null;
  }
  function day(t0, d) { var x = new Date(t0 + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + d); return x; }
  function fdate(dt) { return MON[dt.getUTCMonth()] + ' ' + dt.getUTCDate() + ', ' + dt.getUTCFullYear(); }
  function money(v, cur) {
    if (v == null || isNaN(v)) return '–';
    var a = Math.abs(v), s;
    if (a >= 10000) s = Math.round(v).toLocaleString('en-US');
    else if (a > 0 && a < 1) s = v.toFixed(Math.min(6, Math.max(2, -Math.floor(Math.log10(a)) + 2)));
    else s = v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (cur || '') + s;
  }
  function pct(v, d) { if (v == null || isNaN(v)) return '–'; var s = Math.abs(v * 100).toFixed(d == null ? 1 : d) + '%'; return v > 0 ? '+' + s : v < 0 ? '−' + s : s; }
  function bigNum(v) {
    if (v == null) return '–';
    var a = Math.abs(v);
    if (a >= 1e12) return (v / 1e12).toFixed(2) + 'T';
    if (a >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (a >= 1e3) return (v / 1e3).toFixed(0) + 'K';
    return String(Math.round(v));
  }
  function sma(a, n) {
    var out = new Array(a.length).fill(null), s = 0;
    for (var i = 0; i < a.length; i++) { s += a[i]; if (i >= n) s -= a[i - n]; if (i >= n - 1) out[i] = s / n; }
    return out;
  }
  function ema(a, n) {
    var out = new Array(a.length).fill(null), k = 2 / (n + 1), e = null;
    for (var i = 0; i < a.length; i++) { e = e == null ? a[i] : a[i] * k + e * (1 - k); out[i] = e; }
    return out;
  }
  function stdev(a, n) {
    var m = sma(a, n), out = new Array(a.length).fill(null);
    for (var i = n - 1; i < a.length; i++) { var s = 0; for (var j = i - n + 1; j <= i; j++) s += (a[j] - m[i]) * (a[j] - m[i]); out[i] = Math.sqrt(s / n); }
    return out;
  }
  function onResize(box, fn) {
    fn();
    if (window.ResizeObserver) {
      var w = box.clientWidth;
      new ResizeObserver(function () { if (Math.abs(box.clientWidth - w) > 2) { w = box.clientWidth; fn(); } }).observe(box);
    }
  }
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  // ---- news on the candle chart: when each bar's close was set, and how a story moved the stock
  var NYH = null;
  function nyHour(ms) {
    if (!NYH) NYH = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hourCycle: 'h23' });
    return +NYH.format(new Date(ms));
  }
  /** UTC ms when each bar's close was set: 4 pm New York (the TSX closes then too), midnight UTC for crypto. */
  function closeTimes(D) {
    return D.d.map(function (dd) {
      var x = day(D.t0, dd), base = Date.UTC(x.getUTCFullYear(), x.getUTCMonth(), x.getUTCDate());
      if (D.crypto) return base + 864e5;
      return nyHour(base + 20 * 36e5) === 16 ? base + 20 * 36e5 : base + 21 * 36e5;
    });
  }
  /** The move from the last close before the story (b) to the next close and five closes later, against
   *  the market's closes on the same days, and the stock's normal daily swing (60 sessions up to b). */
  function measureNews(D, it) {
    var c = D.c, n = c.length, b = it.b, bc = D.bc, s = {};
    for (var k in it) s[k] = it[k];
    s.r = b + 1 < n ? b + 1 : null;
    s.mi = s.r != null ? s.r : b;
    function mv(a, i, j) { return a && a[i] && a[j] ? a[j] / a[i] - 1 : null; }
    s.d1 = s.r != null ? mv(c, b, b + 1) : null;
    s.m1 = s.r != null ? mv(bc, b, b + 1) : null;
    s.d5 = b + 5 < n ? mv(c, b, b + 5) : null;
    s.m5 = b + 5 < n ? mv(bc, b, b + 5) : null;
    var rr = [];
    for (var q = Math.max(1, b - 59); q <= b; q++) if (c[q] && c[q - 1]) rr.push(c[q] / c[q - 1] - 1);
    var mean = rr.reduce(function (a, v) { return a + v; }, 0) / (rr.length || 1);
    s.sd = rr.length > 10 ? Math.sqrt(rr.reduce(function (a, v) { return a + (v - mean) * (v - mean); }, 0) / rr.length) : null;
    s.ex = s.d1 == null ? null : s.d1 - (s.m1 || 0);
    s.z = s.ex != null && s.sd ? Math.abs(s.ex) / s.sd : null;
    return s;
  }
  function nkey(h) { return String(h || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 70); }
  function etTime(t) {
    try { return new Date(t).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ET'; } catch (e) { return t; }
  }
  function shortDate(t) { try { return new Date(t).toLocaleDateString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric' }); } catch (e) { return t; } }
  function dirc(v) { return v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''; }

  function niceTicks(lo, hi, n) {
    var span = hi - lo || Math.abs(hi) || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).find(function (s) { return span / s <= n; }) || 10 * mag;
    var out = []; for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  // ======================================================== candlesticks
  var OVERLAYS = {
    sma20: { label: '20-day SMA', color: '--s3', calc: function (c) { return [sma(c, 20)]; } },
    sma50: { label: '50-day SMA', color: '--s1', calc: function (c) { return [sma(c, 50)]; } },
    sma200: { label: '200-day SMA', color: '--s2', calc: function (c) { return [sma(c, 200)]; } },
    ema21: { label: '21-day EMA', color: '--s3', calc: function (c) { return [ema(c, 21)]; } },
    bb: { label: 'Bollinger Bands', color: '--muted', calc: function (c) {
      var m = sma(c, 20), s = stdev(c, 20);
      return [m.map(function (x, i) { return x == null ? null : x + 2 * s[i]; }), m, m.map(function (x, i) { return x == null ? null : x - 2 * s[i]; })];
    } }
  };
  function Candles(box) {
    var D = data(box, 'data-candles');
    if (!D) return;
    var n = D.c.length;
    var ranges = D.ranges || [['3M', 63], ['6M', 126], ['1Y', 252], ['2Y', 504]];
    var state = { range: D.range || 126, on: {} };
    (D.overlays || ['sma50', 'sma200']).forEach(function (k) { state.on[k] = true; });
    var bar = el('div', { 'class': 'cd-bar' });
    var rg = el('div', { 'class': 'seg seg-sm', role: 'group', 'aria-label': 'Range' });
    ranges.forEach(function (r) {
      if (r[1] > n && r[1] !== ranges[0][1]) return;
      var b = el('button', { type: 'button', text: r[0], 'aria-pressed': String(state.range === r[1]) });
      b.addEventListener('click', function () { state.range = r[1]; [].forEach.call(rg.children, function (x) { x.setAttribute('aria-pressed', 'false'); }); b.setAttribute('aria-pressed', 'true'); draw(); });
      rg.appendChild(b);
    });
    var ov = el('div', { 'class': 'cd-ov' });
    (D.allow || ['sma20', 'sma50', 'sma200', 'bb']).forEach(function (k) {
      var o = OVERLAYS[k];
      var b = el('button', { type: 'button', 'class': 'cd-chip', 'aria-pressed': String(!!state.on[k]) }, [el('i', { style: 'background:var(' + o.color + ')' }), o.label]);
      b.addEventListener('click', function () { state.on[k] = !state.on[k]; b.setAttribute('aria-pressed', String(state.on[k])); draw(); });
      ov.appendChild(b);
    });
    bar.appendChild(rg); bar.appendChild(ov);
    var plot = el('div', { 'class': 'cd-plot', tabindex: '0' });
    var tip = el('div', { 'class': 'cd-tip', 'aria-live': 'polite' });
    box.appendChild(bar); box.appendChild(plot); box.appendChild(tip);
    var lines = {};
    Object.keys(OVERLAYS).forEach(function (k) { lines[k] = OVERLAYS[k].calc(D.c); });
    var cur = null;

    // ---- news markers (stock pages): a dot over the first close after each story; hover or tap for the story
    // and the move, measured from the last close before it against the market on the same days
    var news = null, groups = {}, clusters = [], card = null, list = null, hideT = null, pinned = false, geo = null, viewI0 = 0, listAll = false;
    var SYM = String(D.sym || '').replace(/^\^/, ''), BN = D.bn || null;
    if (D.news) {
      news = D.news.map(function (it) { return measureNews(D, it); });
      regroup();
      card = el('div', { 'class': 'cd-news', role: 'dialog', 'aria-label': 'News on ' + SYM });
      card.hidden = true;
      card.addEventListener('pointerenter', function () { clearTimeout(hideT); });
      card.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !pinned) hideSoon(); });
      card.addEventListener('click', function (e) { if (e.target.closest('.cn-x')) hide(); });
      list = el('div', { 'class': 'cd-newslist' });
      list.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        if (b.hasAttribute('data-all')) { listAll = !listAll; paintList(); return; }
        var mi = +b.getAttribute('data-mi');
        if (!isNaN(mi)) { plot.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); openMi(mi, true); }
      });
      document.addEventListener('pointerdown', function (e) { if (!card.hidden && !card.contains(e.target) && !(e.target.closest && e.target.closest('.cd-mk'))) hide(); });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !card.hidden) hide(); });
    }
    function regroup() { groups = {}; news.forEach(function (x) { (groups[x.mi] = groups[x.mi] || []).push(x); }); }
    function hide() { clearTimeout(hideT); pinned = false; if (card) card.hidden = true; }
    function hideSoon() { clearTimeout(hideT); hideT = setTimeout(hide, 280); }
    function row(label, d, m) {
      return '<div class="cn-row"><span class="cn-l">' + label + '</span><b class="' + dirc(d) + '">' + (d == null ? '–' : pct(d)) + '</b>' +
        '<span class="cn-m">' + (d == null ? 'still developing' : m != null && BN ? esc(BN) + ' ' + (Math.abs(m) < 0.0005 ? '0.0%' : pct(m)) : '') + '</span></div>';
    }
    function verdict(x) {
      var beyond = BN ? ' beyond the ' + esc(BN) : '';
      if (x.z == null) return '<b class="' + dirc(x.ex) + '">' + pct(x.ex) + '</b>' + beyond + '.';
      var zz = x.z.toFixed(1) + '× a normal day for ' + esc(SYM);
      if (x.z >= 2) return '<b class="' + dirc(x.ex) + '">' + pct(x.ex) + '</b>' + beyond + ', ' + zz + ': the news moved the stock.';
      if (x.z >= 1) return '<b class="' + dirc(x.ex) + '">' + pct(x.ex) + '</b>' + beyond + ', ' + zz + ': a real but modest reaction.';
      return pct(x.ex) + beyond + ', inside a normal day\'s swing for ' + esc(SYM) + ' (±' + (x.sd * 100).toFixed(1) + '%): more noise than news.';
    }
    function storiesHtml(g, max) {
      return g.slice(0, max).map(function (it) {
        return '<p class="cn-meta">' + esc(etTime(it.t)) + (it.s ? ' · ' + esc(it.s) : '') + '</p>' +
          (it.u ? '<a class="cn-h" href="' + esc(it.u) + '" target="_blank" rel="noopener noreferrer">' + esc(it.h) + '</a>' : '<p class="cn-h">' + esc(it.h) + '</p>');
      }).join('') + (g.length > max ? '<p class="cn-more">+ ' + (g.length - max) + ' more before the same close</p>' : '');
    }
    function impactHtml(x) {
      var base = fdate(day(D.t0, D.d[x.b]));
      return x.d1 == null
        ? '<p class="cn-verdict">Too fresh to measure: it came after the ' + base + ' close, so the next close is the first read on the impact.</p>'
        : '<div class="cn-rows">' + row('Next day', x.d1, x.m1) + row('5 days', x.d5, x.m5) + '</div><p class="cn-verdict">' + verdict(x) + '</p>';
    }
    // a cluster is one marker: the stories before one close, or (when markers would overlap) a few nearby closes
    function cardHtml(cl) {
      var gs = cl.mis.slice().sort(function (a, b) { return b - a; }).map(function (mi) { return groups[mi]; });
      var how = '<p class="cn-how">Each move is measured from the last close before the story to the next close and five closes later' +
        (BN ? ', minus the ' + esc(BN) + ' over the same days' : '') + '. Several stories before one close share its move.</p>';
      if (gs.length === 1) {
        var g = gs[0];
        return '<button type="button" class="cn-x" aria-label="Close">×</button>' + storiesHtml(g, 4) + '<div class="cn-imp">' + impactHtml(g[0]) + '</div>' +
          '<p class="cn-how">Measured from the ' + fdate(day(D.t0, D.d[g[0].b])) + ' close, the last before ' + (g.length > 1 ? 'these stories; together they share the move' : 'the story') +
          (BN ? ', minus the ' + esc(BN) + ' over the same days' : '') + '.</p>';
      }
      return '<button type="button" class="cn-x" aria-label="Close">×</button>' + gs.map(function (g) {
        return '<div class="cn-sec">' + storiesHtml(g, 2) + '<div class="cn-imp">' + impactHtml(g[0]) + '</div></div>';
      }).join('') + how;
    }
    function markerY(mi) { return Math.max(geo.m.t + 8, geo.Y(D.h[mi]) - 12); }
    function clusterOf(mi) { for (var i = 0; i < clusters.length; i++) if (clusters[i].mis.indexOf(mi) >= 0) return i; return -1; }
    function open(ci, pin) {
      clearTimeout(hideT);
      var cl = clusters[ci];
      if (!cl || !geo) return;
      pinned = !!pin;
      card.innerHTML = cardHtml(cl);
      card.hidden = false;
      var bw = box.clientWidth, cw = card.offsetWidth, ch = card.offsetHeight;
      var left = Math.max(0, Math.min(bw - cw, plot.offsetLeft + cl.x - cw / 2));
      var top = plot.offsetTop + cl.y + 14;
      if (top + ch > plot.offsetTop + plot.clientHeight + 40 && plot.offsetTop + cl.y - 14 - ch > 0) top = plot.offsetTop + cl.y - 14 - ch;
      card.style.left = left + 'px'; card.style.top = top + 'px';
    }
    function openMi(mi, pin) { var ci = clusterOf(mi); if (ci >= 0) open(ci, pin); }
    function drawNews(svg, X, Y, i0, m) {
      geo = { X: X, Y: Y, m: m }; viewI0 = i0; clusters = [];
      var gap = 16, cur2 = null;
      Object.keys(groups).map(Number).filter(function (mi) { return mi >= i0; }).sort(function (a, b) { return a - b; }).forEach(function (mi) {
        if (cur2 && X(mi) - X(cur2.mis[cur2.mis.length - 1]) < gap) cur2.mis.push(mi);
        else { cur2 = { mis: [mi] }; clusters.push(cur2); }
      });
      clusters.forEach(function (cl, ci) {
        var last = cl.mis[cl.mis.length - 1], x = X(last), y = Math.min.apply(null, cl.mis.map(markerY));
        cl.x = x; cl.y = y;
        var items = [], x0 = groups[last][0];
        cl.mis.forEach(function (mi) { items = items.concat(groups[mi]); });
        var nn = items.length, pend = x0.ex == null, multi = cl.mis.length > 1;
        var col = multi ? css('--violet-ink') : pend ? css('--violet-ink') : x0.sd && Math.abs(x0.ex) < 0.5 * x0.sd ? css('--muted') : x0.ex > 0 ? css('--candle-up') : css('--candle-down');
        var hollow = pend && !multi;
        var gg = svgEl('g', { 'class': 'cd-mk', tabindex: '0', role: 'button', 'aria-label': (nn > 1 ? nn + ' stories, latest: ' : 'Story: ') + groups[last][groups[last].length - 1].h }, svg);
        svgEl('line', { x1: x, x2: x, y1: y + (nn > 1 ? 7 : 5), y2: Math.max(y + 6, Y(D.h[last]) - 2), stroke: col, 'stroke-width': 1, opacity: 0.6 }, gg);
        svgEl('circle', { cx: x, cy: y, r: 13, fill: 'transparent' }, gg);
        svgEl('circle', { cx: x, cy: y, r: nn > 1 ? 7 : 5, fill: hollow ? css('--panel') : col, stroke: hollow ? col : css('--panel'), 'stroke-width': hollow ? 2 : 1.5 }, gg);
        if (nn > 1) {
          var tx = svgEl('text', { x: x, y: y + 3.2, 'text-anchor': 'middle', 'font-size': 9, 'font-weight': 700, 'font-family': css('--data'), fill: hollow ? col : '#fff' }, gg);
          tx.textContent = nn > 9 ? '9+' : nn;
        }
        gg.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse' && !pinned) open(ci, false); });
        gg.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !pinned) hideSoon(); });
        gg.addEventListener('pointerdown', function (e) { e.stopPropagation(); open(ci, true); });
        gg.addEventListener('focus', function () { if (!pinned) open(ci, false); });
        gg.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(ci, true); } });
      });
      paintList();
    }
    function paintList() {
      if (!list) return;
      var vis = news.filter(function (x) { return x.mi >= viewI0; }).sort(function (a, b) { return a.t < b.t ? 1 : -1; });
      if (!vis.length) { list.innerHTML = '<p class="nl-empty">No news or filings on ' + esc(SYM) + ' in this range yet.</p>'; return; }
      var rows = (listAll ? vis : vis.slice(0, 5)).map(function (x) {
        var mv = x.ex == null ? '<span class="nl-pend">too fresh</span>' : '<b class="' + dirc(x.ex) + '">' + pct(x.ex) + '</b>';
        return '<li><button type="button" data-mi="' + x.mi + '"><span class="nl-d">' + esc(shortDate(x.t)) + '</span><span class="nl-h">' + esc(x.h) + '</span>' + mv + '</button></li>';
      }).join('');
      list.innerHTML = '<div class="nl-head"><b>News and filings on the chart</b><span>next-day move' + (BN ? ' beyond the ' + esc(BN) : '') + '</span></div><ul>' + rows + '</ul>' +
        (vis.length > 5 ? '<button type="button" class="linkish nl-all" data-all>' + (listAll ? 'Show fewer' : 'Show all ' + vis.length) + '</button>' : '');
    }
    function setRange(r) {
      state.range = r;
      [].forEach.call(rg.children, function (x) { x.setAttribute('aria-pressed', String(x.textContent === (ranges.filter(function (q) { return q[1] === r; })[0] || [])[0])); });
    }
    function deepLink() {
      var q = new URLSearchParams(location.search).get('news');
      if (!q || !news) return;
      var ts = /^\d+$/.test(q) ? +q : Date.parse(q), best = null;
      if (!ts) return;
      news.forEach(function (x) { var dd = Math.abs(Date.parse(x.t) - ts); if (dd < 36 * 36e5 && (!best || dd < best.d)) best = { x: x, d: dd }; });
      if (!best) return;
      var need = n - best.x.mi + 3;
      if (need > state.range) { var fit = ranges.filter(function (r) { return r[1] >= need && r[1] <= n + 5; })[0]; if (fit) { setRange(fit[1]); draw(); } }
      box.scrollIntoView({ block: 'center' });
      setTimeout(function () { openMi(best.x.mi, true); }, 350);
    }
    function liveNews() {
      if (!news || !D.live || !D.sym || location.protocol === 'file:') { deepLink(); return; }
      var url = '/.netlify/functions/news?edgar=0&tickers=' + encodeURIComponent(D.sym) + '&names=' + encodeURIComponent(D.sym + ':' + (D.name || D.sym));
      fetch(url).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (j && j.stories && j.stories.length) {
          var have = {}, closes = closeTimes(D), added = 0;
          news.forEach(function (x) { have[nkey(x.h)] = 1; });
          j.stories.forEach(function (st) {
            var h = String(st.headline || ''), src = st.src || '';
            if (src && h.slice(-(src.length + 3)) === ' - ' + src) h = h.slice(0, -(src.length + 3));
            if (h.length < 12 || have[nkey(h)] || !st.ts) return;
            var b = -1;
            for (var i = closes.length - 1; i >= 0; i--) if (closes[i] <= st.ts) { b = i; break; }
            if (b < 1 || b < n - 520) return;
            have[nkey(h)] = 1; added++;
            news.push(measureNews(D, { b: b, t: new Date(st.ts).toISOString(), h: h, s: src || 'News', u: st.link || '', k: 'news', ty: 'News' }));
          });
          if (added) { regroup(); draw(); }
        }
        deepLink();
      }).catch(deepLink);
    }

    function draw() {
      plot.innerHTML = '';
      var W = plot.clientWidth, H = plot.clientHeight;
      if (W < 50) return;
      var narrow = W < 520, m = { l: narrow ? 44 : 56, r: 10, t: 8, b: 24 };
      var volH = Math.round((H - m.t - m.b) * 0.18), gap = 6;
      var ph = H - m.t - m.b - volH - gap;
      var i0 = Math.max(0, n - state.range), cnt = n - i0;
      var lo = Infinity, hi = -Infinity, vmax = 0;
      for (var i = i0; i < n; i++) { lo = Math.min(lo, D.l[i]); hi = Math.max(hi, D.h[i]); vmax = Math.max(vmax, D.v[i] || 0); }
      // averages can widen the scale a little, but never squash the candles; beyond that they are clipped
      var span0 = hi - lo, lo0 = lo - span0 * 0.25, hi0 = hi + span0 * 0.25;
      for (var i1 = i0; i1 < n; i1++) {
        Object.keys(state.on).forEach(function (k) { if (!state.on[k]) return; lines[k].forEach(function (s) { var x = s[i1]; if (x != null) { lo = Math.min(lo, Math.max(x, lo0)); hi = Math.max(hi, Math.min(x, hi0)); } }); });
      }
      var pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
      var iw = W - m.l - m.r, step = iw / cnt, bw = Math.max(1, Math.min(14, step * 0.68));
      var X = function (i) { return m.l + (i - i0 + 0.5) * step; };
      var Y = function (v) { return m.t + ph - (v - lo) / (hi - lo) * ph; };
      var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': D.label || 'Candlestick chart' }, plot);
      var cid = 'cdclip' + Math.random().toString(36).slice(2, 8);
      var defs = svgEl('defs', {}, svg), cp = svgEl('clipPath', { id: cid }, defs);
      svgEl('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: ph }, cp);
      niceTicks(lo, hi, narrow ? 4 : 6).forEach(function (v) {
        var y = Y(v);
        svgEl('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: css('--line'), 'stroke-width': 1 }, svg);
        var t = svgEl('text', { x: m.l - 7, y: y + 4, 'text-anchor': 'end', fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg);
        t.textContent = money(v, '').replace('.00', '');
      });
      // month ticks
      var lastM = -1, every = cnt > 300 ? 3 : cnt > 130 ? 2 : 1, mc = 0;
      for (var j = i0; j < n; j++) {
        var dt = day(D.t0, D.d[j]), mm = dt.getUTCMonth();
        if (mm !== lastM) {
          if (lastM !== -1 && (mc++ % every === 0)) {
            var tx = svgEl('text', { x: X(j), y: H - 6, 'text-anchor': 'middle', fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg);
            tx.textContent = MON[mm] + (mm === 0 ? " '" + String(dt.getUTCFullYear()).slice(2) : '');
          }
          lastM = mm;
        }
      }
      var up = css('--candle-up'), dn = css('--candle-down');
      var vb = m.t + ph + gap + volH;
      for (var k = i0; k < n; k++) {
        var o = D.o[k], c = D.c[k], isUp = c >= o, col = isUp ? up : dn, x = X(k);
        svgEl('line', { x1: x, x2: x, y1: Y(D.h[k]), y2: Y(D.l[k]), stroke: col, 'stroke-width': 1 }, svg);
        var yt = Y(Math.max(o, c)), yb = Y(Math.min(o, c));
        svgEl('rect', { x: x - bw / 2, y: yt, width: bw, height: Math.max(1, yb - yt), fill: isUp ? (bw > 3 ? css('--panel') : col) : col, stroke: col, 'stroke-width': 1 }, svg);
        if (vmax > 0 && D.v[k]) { var vh = D.v[k] / vmax * volH; svgEl('rect', { x: x - bw / 2, y: vb - vh, width: bw, height: vh, fill: col, opacity: 0.35 }, svg); }
      }
      (D.marks || []).forEach(function (mk) {
        if (mk.i < i0) return;
        var x2 = X(mk.i), y2 = Y(D.l[mk.i]) + 14;
        svgEl('path', { d: 'M' + x2 + ' ' + (y2 - 8) + 'l-5 8h10z', fill: css('--violet-ink') }, svg);
      });
      Object.keys(state.on).forEach(function (key) {
        if (!state.on[key]) return;
        lines[key].forEach(function (s, si) {
          var p = '', pen = false;
          for (var q = i0; q < n; q++) { var v = s[q]; if (v == null) { pen = false; continue; } p += (pen ? 'L' : 'M') + X(q).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; }
          svgEl('path', { d: p, fill: 'none', stroke: css(OVERLAYS[key].color), 'stroke-width': key === 'bb' && si !== 1 ? 1 : 1.6, 'stroke-dasharray': key === 'bb' && si !== 1 ? '3 3' : '', opacity: 0.95, 'clip-path': 'url(#' + cid + ')' }, svg);
        });
      });
      var cross = svgEl('line', { x1: 0, x2: 0, y1: m.t, y2: vb, stroke: css('--ink-2'), 'stroke-width': 1, opacity: 0 }, svg);
      var hit = svgEl('rect', { x: m.l, y: m.t, width: iw, height: vb - m.t, fill: 'transparent' }, svg);
      function show(i) {
        cur = i; var x3 = X(i);
        cross.setAttribute('x1', x3); cross.setAttribute('x2', x3); cross.setAttribute('opacity', 0.5);
        var ch = i > 0 ? D.c[i] / D.c[i - 1] - 1 : null;
        var parts = [fdate(day(D.t0, D.d[i])), 'O ' + money(D.o[i], D.cur), 'H ' + money(D.h[i], D.cur), 'L ' + money(D.l[i], D.cur), 'C ' + money(D.c[i], D.cur) + (ch != null ? ' (' + pct(ch) + ')' : '')];
        if (D.v[i]) parts.push('Vol ' + bigNum(D.v[i]));
        if (news && groups[i]) parts.push(groups[i].length + (groups[i].length > 1 ? ' stories' : ' story') + ' (dot above)');
        tip.textContent = parts.join('  ·  ');
      }
      function nearest(e) { var r = svg.getBoundingClientRect(); var px = (e.clientX - r.left) * (W / r.width); return Math.max(i0, Math.min(n - 1, Math.round((px - m.l) / step - 0.5) + i0)); }
      hit.addEventListener('pointermove', function (e) { show(nearest(e)); });
      hit.addEventListener('pointerdown', function (e) { show(nearest(e)); });
      plot.onkeydown = function (e) {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        e.preventDefault(); show(Math.max(i0, Math.min(n - 1, (cur == null ? n - 1 : cur) + (e.key === 'ArrowRight' ? 1 : -1))));
      };
      if (news) { drawNews(svg, X, Y, i0, m); if (card && !card.hidden) hide(); }
      show(cur != null && cur >= i0 ? cur : n - 1);
    }
    onResize(plot, draw);
    if (list) { box.appendChild(card); box.appendChild(list); }
    liveNews();
  }

  // ======================================================== plays-over-time heatmap
  function Heatmap(box) {
    var D = data(box, 'data-heatmap');
    if (!D) return;
    var hasCore = D.rows.some(function (r) { return r.core; }) && D.rows.some(function (r) { return !r.core; });
    var st = { core: hasCore };
    if (hasCore) {
      var seg = el('div', { 'class': 'seg seg-sm hm-seg', role: 'group', 'aria-label': 'Which plays' });
      [['core', 'Core ' + D.rows.filter(function (r) { return r.core; }).length], ['all', 'All ' + D.rows.length]].forEach(function (o) {
        var b = el('button', { type: 'button', text: o[1], 'aria-pressed': String((o[0] === 'core') === st.core) });
        b.addEventListener('click', function () { st.core = o[0] === 'core'; [].forEach.call(seg.children, function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); });
        seg.appendChild(b);
      });
      box.appendChild(seg);
    }
    var canvas = el('canvas', { 'class': 'hm-canvas', role: 'img', 'aria-label': D.label || 'Every play, week by week' });
    var tip = el('div', { 'class': 'hm-tip', 'aria-live': 'polite', text: 'Hover or tap a cell to see a play\'s call that week.' });
    box.appendChild(canvas); box.appendChild(tip);
    var W0 = D.weeks.length, geo = null, rows = D.rows;
    function fit(ctx, s, w) {
      if (ctx.measureText(s).width <= w) return s;
      while (s.length > 3 && ctx.measureText(s + '…').width > w) s = s.slice(0, -1);
      return s + '…';
    }
    function draw() {
      rows = st.core ? D.rows.filter(function (r) { return r.core; }) : D.rows;
      var W = box.clientWidth, narrow = W < 560;
      var lab = narrow ? 96 : 176, top = 46, rh = st.core ? (narrow ? 14 : 16) : (narrow ? 9 : 11), famGap = st.core ? 4 : 6;
      var H = top + 6, last = null;
      rows.forEach(function (r) { if (last !== null && r.fam !== last) H += famGap; last = r.fam; H += rh; });
      var dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
      var ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var cw = (W - lab - 2) / W0;
      var cin = css('--in'), cout = css('--out'), cna = css('--line'), ink = css('--muted');
      // share-in line across the top
      var share = [];
      for (var w = 0; w < W0; w++) { var k = 0, nn = 0; rows.forEach(function (r) { var c = r.h[w]; if (c === '1') { k++; nn++; } else if (c === '0') nn++; }); share.push(nn ? k / nn : null); }
      ctx.strokeStyle = css('--line'); ctx.lineWidth = 1;
      [top - 8, top - 38].forEach(function (yy) { ctx.beginPath(); ctx.moveTo(lab, yy + 0.5); ctx.lineTo(W, yy + 0.5); ctx.stroke(); });
      ctx.strokeStyle = css('--violet-ink'); ctx.lineWidth = 1.6; ctx.beginPath();
      var pen = false;
      share.forEach(function (v, i) { if (v == null) { pen = false; return; } var x = lab + (i + 0.5) * cw, y = top - 8 - v * 30; if (!pen) ctx.moveTo(x, y); else ctx.lineTo(x, y); pen = true; });
      ctx.stroke();
      ctx.fillStyle = ink; ctx.font = (narrow ? '9.5px ' : '11px ') + css('--data');
      ctx.fillText('100% in', 0, top - 34); ctx.fillText('0% in', 0, top - 6);
      var ys = [], y = top; last = null;
      ctx.textBaseline = 'middle';
      rows.forEach(function (r) {
        if (last !== null && r.fam !== last) y += famGap;
        last = r.fam; ys.push(y);
        ctx.fillStyle = r.core ? css('--ink-2') : ink;
        ctx.font = (r.core && !st.core ? '600 ' : '') + (narrow ? '10px ' : (rh >= 14 ? '12px ' : '10.5px ')) + css('--ui');
        ctx.fillText(fit(ctx, r.name, lab - 8), 0, y + rh / 2);
        for (var w2 = 0; w2 < W0; w2++) {
          var c = r.h[w2];
          ctx.fillStyle = c === '1' ? cin : c === '0' ? cout : cna;
          ctx.globalAlpha = c === '-' ? 0.5 : 0.82;
          ctx.fillRect(lab + w2 * cw, y + 0.5, Math.max(1, cw - (cw > 3 ? 0.8 : 0.3)), rh - (rh > 10 ? 2 : 1));
        }
        ctx.globalAlpha = 1;
        y += rh;
      });
      ctx.textBaseline = 'alphabetic';
      geo = { lab: lab, cw: cw, ys: ys, rh: rh };
    }
    function at(e) {
      var r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      if (!geo) return null;
      var w = x < geo.lab ? W0 - 1 : Math.floor((x - geo.lab) / geo.cw);
      for (var i = 0; i < geo.ys.length; i++) if (y >= geo.ys[i] && y < geo.ys[i] + geo.rh) return { r: rows[i], w: Math.max(0, Math.min(W0 - 1, w)) };
      return null;
    }
    function show(e) {
      var h = at(e);
      if (!h) return;
      var c = h.r.h[h.w];
      tip.textContent = h.r.name + ' · week of ' + D.weeks[h.w] + ' · ' + (c === '1' ? 'IN' : c === '0' ? 'OUT' : 'no call yet') + ' ';
      if (h.r.href) tip.appendChild(el('a', { href: h.r.href, text: 'Open this play →' }));
    }
    canvas.addEventListener('pointermove', function (e) { if (e.pointerType === 'mouse') show(e); });
    canvas.addEventListener('pointerdown', show);
    onResize(box, draw);
  }

  // ======================================================== positioning simulator
  function Sim(box) {
    var D = data(box, 'data-sim');
    if (!D) return;
    var scen = D.scenarios, mixes = D.mixes;
    var st = { scen: scen[0].key, mix: { stocks: 60, bonds: 30, gold: 0, cash: 10 }, plan: 'hold' };
    var ui = el('div', { 'class': 'sim-ui' });
    var scSel = el('select', { 'aria-label': 'Scenario' });
    scen.forEach(function (s) { scSel.appendChild(el('option', { value: s.key, text: s.label })); });
    scSel.addEventListener('change', function () { st.scen = scSel.value; run(); });
    var planSel = el('select', { 'aria-label': 'Plan' });
    [['hold', 'Stay invested, never rebalance'], ['rebal', 'Stay invested, rebalance yearly'], ['cash', 'Sell all stocks at the start, back in after 12 months'], ['rule', 'Stocks follow the 10-month rule (T-bills when out)']].forEach(function (p) { planSel.appendChild(el('option', { value: p[0], text: p[1] })); });
    planSel.addEventListener('change', function () { st.plan = planSel.value; run(); });
    var sliders = el('div', { 'class': 'sim-sliders' });
    var outs = {};
    ['stocks', 'bonds', 'gold', 'cash'].forEach(function (k) {
      var lab = { stocks: 'Stocks (S&P 500)', bonds: 'Long bonds (TLT)', gold: 'Gold (GLD)', cash: 'Cash (T-bills)' }[k];
      var inp = el('input', { type: 'range', min: 0, max: 100, step: 5, value: st.mix[k], 'aria-label': lab });
      var o = el('b', { text: st.mix[k] + '%' }); outs[k] = { inp: inp, o: o };
      inp.addEventListener('input', function () { setMix(k, +inp.value); });
      sliders.appendChild(el('label', { 'class': 'sim-sl' }, [el('span', { text: lab }), inp, o]));
    });
    var presets = el('div', { 'class': 'chips sim-presets' });
    mixes.forEach(function (mx) {
      presets.appendChild(el('button', { type: 'button', 'class': 'chip-btn', text: mx.label, on: { click: function () { st.mix = Object.assign({}, mx.mix); syncSliders(); run(); } } }));
    });
    function setMix(k, v) {
      var others = ['stocks', 'bonds', 'gold', 'cash'].filter(function (x) { return x !== k; });
      st.mix[k] = v;
      var rest = 100 - v, sum = others.reduce(function (a, x) { return a + st.mix[x]; }, 0);
      others.forEach(function (x) { st.mix[x] = sum ? Math.round(st.mix[x] / sum * rest / 5) * 5 : (x === 'cash' ? rest : 0); });
      var tot = ['stocks', 'bonds', 'gold', 'cash'].reduce(function (a, x) { return a + st.mix[x]; }, 0);
      st.mix.cash += 100 - tot;
      if (st.mix.cash < 0) { st.mix.bonds += st.mix.cash; st.mix.cash = 0; }
      syncSliders(); run();
    }
    function syncSliders() { Object.keys(outs).forEach(function (k) { outs[k].inp.value = st.mix[k]; outs[k].o.textContent = st.mix[k] + '%'; }); }
    ui.appendChild(el('div', { 'class': 'sim-row' }, [el('label', { 'class': 'small muted' }, ['Crash or period', scSel]), el('label', { 'class': 'small muted' }, ['Plan', planSel])]));
    ui.appendChild(presets);
    ui.appendChild(sliders);
    var chart = el('div', { 'class': 'chart' });
    var stats = el('div', { 'class': 'sim-stats', 'aria-live': 'polite' });
    box.appendChild(ui); box.appendChild(chart); box.appendChild(stats);

    function series(sc, mix, plan) {
      var i0 = D.dates.indexOf(sc.from), i1 = sc.to ? D.dates.indexOf(sc.to) : D.dates.length - 1;
      if (i0 < 0) i0 = 0; if (i1 < 0) i1 = D.dates.length - 1;
      var w = { stocks: mix.stocks / 100, bonds: mix.bonds / 100, gold: mix.gold / 100, cash: mix.cash / 100 };
      var val = { stocks: w.stocks, bonds: w.bonds, gold: w.gold, cash: w.cash }, port = [1], bench = [1], b = 1;
      for (var i = i0; i <= i1; i++) {
        var r = { stocks: D.stocks[i] || 0, bonds: D.bonds[i] || 0, gold: D.gold[i] || 0, cash: D.cash[i] || 0 };
        b *= 1 + r.stocks;
        var k = i - i0;
        var sr = r.stocks;
        if (plan === 'cash' && k < 12) sr = r.cash;
        if (plan === 'rule' && D.rule[i] === 0) sr = r.cash;
        val.stocks *= 1 + sr; val.bonds *= 1 + r.bonds; val.gold *= 1 + r.gold; val.cash *= 1 + r.cash;
        var tot = val.stocks + val.bonds + val.gold + val.cash;
        if (plan === 'rebal' && (k + 1) % 12 === 0) { val.stocks = tot * w.stocks; val.bonds = tot * w.bonds; val.gold = tot * w.gold; val.cash = tot * w.cash; }
        port.push(tot); bench.push(b);
      }
      return { port: port, bench: bench, i0: i0, i1: i1 };
    }
    function maxdd(a) { var pk = a[0], m = 0; a.forEach(function (v) { pk = Math.max(pk, v); m = Math.min(m, v / pk - 1); }); return m; }
    function recover(a) { var pk = a[0], low = Infinity, li = 0; a.forEach(function (v, i) { if (v < low) { low = v; li = i; } }); for (var i = li; i < a.length; i++) if (a[i] >= a[0]) return i; return null; }
    function run() {
      var sc = scen.find(function (s) { return s.key === st.scen; });
      var r = series(sc, st.mix, st.plan);
      var t0 = sc.from + '-01', d = [];
      for (var i = 0; i < r.port.length; i++) { var dt = new Date(t0 + 'T00:00:00Z'); dt.setUTCMonth(dt.getUTCMonth() + i); d.push(Math.round((dt - new Date(t0 + 'T00:00:00Z')) / 864e5)); }
      var spec = { t0: t0, d: d, cur: '$', fmt: 'money', label: 'Growth of $10,000', series: [
        { name: 'Your mix', role: 's1', v: r.port.map(function (v) { return Math.round(v * 10000); }) },
        { name: '100% stocks, held', role: 'bench', v: r.bench.map(function (v) { return Math.round(v * 10000); }) }] };
      chart.innerHTML = '';
      if (window.QChart) window.QChart.draw(chart, spec);
      chart._spec = spec;
      var mp = maxdd(r.port), mb = maxdd(r.bench), rp = recover(r.port), rb = recover(r.bench);
      stats.innerHTML = '';
      function tile(lab, a, b2) { return el('div', { 'class': 'tile' }, [el('span', { 'class': 'tile-label', text: lab }), el('span', { 'class': 'tile-value', text: a }), el('span', { 'class': 'tile-note', text: '100% stocks: ' + b2 })]); }
      stats.appendChild(tile('Worst fall', pct(mp, 0), pct(mb, 0)));
      stats.appendChild(tile('Back to $10,000 after', rp == null ? 'not yet' : rp + ' months', rb == null ? 'not yet' : rb + ' months'));
      stats.appendChild(tile('Value at the end', money(r.port[r.port.length - 1] * 10000, '$'), money(r.bench[r.bench.length - 1] * 10000, '$')));
    }
    if (window.ResizeObserver) { var w0 = chart.clientWidth; new ResizeObserver(function () { if (Math.abs(chart.clientWidth - w0) > 2 && chart._spec) { w0 = chart.clientWidth; window.QChart.draw(chart, chart._spec); } }).observe(chart); }
    run();
  }

  // ======================================================== core-20 / all toggle on play tables
  function CoreToggle(g) {
    var tgt = document.getElementById(g.getAttribute('data-coretoggle'));
    if (!tgt) return;
    var bs = g.querySelectorAll('button');
    [].forEach.call(bs, function (b) {
      b.addEventListener('click', function () {
        [].forEach.call(bs, function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        tgt.classList.toggle('core-only', b.getAttribute('data-v') === 'core');
      });
    });
  }

  // ======================================================== watchlist storage (this browser only)
  var WKEY = 'quiplee.watch.v1';
  function watchGet() {
    try { var v = JSON.parse(localStorage.getItem(WKEY) || 'null'); return v && v.items ? v : { items: [] }; }
    catch (e) { return { items: [] }; }
  }
  function watchSet(v) { try { localStorage.setItem(WKEY, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function WatchAdd(b) {
    var sym = b.getAttribute('data-watch-add'), href = b.getAttribute('data-watch-href');
    var link = el('a', { 'class': 'small', href: href, text: 'Open my watchlist', hidden: '' });
    b.parentNode.insertBefore(link, b.nextSibling);
    // signed in: following lives on the account (and gets the emails); signed out: this browser's watchlist
    var acct = window.BPAuth && window.BPAuth.signedIn(), following = null;
    if (acct) link.href = '/me/#stocks';
    function has() { return following != null ? following : watchGet().items.some(function (x) { return x.sym === sym; }); }
    function paint() {
      var on = has(); b.classList.toggle('is-on', on);
      var short = !!(b.closest && b.closest('.act-bar'));
      b.textContent = acct || short ? (on ? '✓ ' + (acct ? 'Following' : 'Watching') : '+ ' + (acct ? 'Follow' : 'Watch')) : (on ? '✓ On your watchlist' : '+ Add to my watchlist');
      link.textContent = acct ? 'Open My Puck' : 'Open my watchlist';
      link.hidden = !on;
    }
    b.addEventListener('click', function () {
      var w = watchGet(), on = has();
      if (on) w.items = w.items.filter(function (x) { return x.sym !== sym; });
      else if (!w.items.some(function (x) { return x.sym === sym; })) w.items.push({ sym: sym });
      watchSet(w);
      if (acct) {
        tell(!on);
        window.BPAuth.follow(sym, !on).then(function (j) { if (!j.ok) tell(on); });
        return;
      }
      tell(!on);
    });
    // keep every button for this stock on the page in step (the read card and the mobile action bar)
    function tell(on) { document.dispatchEvent(new CustomEvent('bp:follow', { detail: { sym: sym, on: on } })); }
    document.addEventListener('bp:follow', function (ev) {
      if (!ev.detail || ev.detail.sym !== sym) return;
      if (acct) following = ev.detail.on;
      paint();
    });
    if (acct) window.BPAuth.me().then(function (a) { if (a && a.signed_in) { following = (a.follow || []).indexOf(sym) >= 0; paint(); } });
    paint();
  }

  window.QW = { el: el, svgEl: svgEl, css: css, money: money, pct: pct, bigNum: bigNum, sma: sma, ema: ema, stdev: stdev, onResize: onResize, data: data, day: day, fdate: fdate, niceTicks: niceTicks, Candles: Candles, watchGet: watchGet, watchSet: watchSet };

  function init() {
    [].forEach.call(document.querySelectorAll('[data-candles]'), Candles);
    [].forEach.call(document.querySelectorAll('[data-heatmap]'), Heatmap);
    [].forEach.call(document.querySelectorAll('[data-sim]'), Sim);
    [].forEach.call(document.querySelectorAll('[data-coretoggle]'), CoreToggle);
    [].forEach.call(document.querySelectorAll('[data-watch-add]'), WatchAdd);
    if (window.QLearnWidgets) window.QLearnWidgets();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
