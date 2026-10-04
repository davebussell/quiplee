/* site.js — renders Be The Puck's strategy charts from embedded JSON and wires the
 * home-page picker. Zero dependencies. Charts size to their container, redraw on
 * resize, and carry a crosshair + tooltip (mouse, touch and arrow keys). */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function node(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function day(t0, d) { var x = new Date(t0 + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + d); return x; }
  function fmtDate(dt) { return MON[dt.getUTCMonth()] + ' ' + dt.getUTCDate() + ', ' + dt.getUTCFullYear(); }
  function fmtNum(v, cur, money) {
    if (v == null || isNaN(v)) return '–';
    var a = Math.abs(v), s;
    if (money && a >= 1e6) s = (v / 1e6).toFixed(a >= 1e7 ? 1 : 2).replace(/\.0+$/, '') + 'M';
    else if (money && a >= 1e4) s = Math.round(v / 1e3).toLocaleString('en-US') + 'K';
    else if (money && a >= 1e3) s = (v / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
    else if (a >= 1e4) s = Math.round(v).toLocaleString('en-US');
    else if (a > 0 && a < 1) { var pl = Math.min(6, Math.max(2, -Math.floor(Math.log10(a)) + 2)); s = v.toFixed(pl); }
    else s = v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (cur || '') + s;
  }
  function niceTicks(lo, hi, n) {
    var span = hi - lo || Math.abs(hi) || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).find(function (s) { return span / s <= n; }) || 10 * mag;
    var out = [];
    for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function logTicks(lo, hi) {
    var out = [], e0 = Math.floor(Math.log10(lo)), e1 = Math.ceil(Math.log10(hi));
    var mult = (e1 - e0) > 3 ? [1] : [1, 2, 5];
    for (var e = e0; e <= e1; e++) mult.forEach(function (m) { var v = m * Math.pow(10, e); if (v >= lo && v <= hi) out.push(v); });
    return out;
  }
  function fmtPct(v) {
    if (v == null || isNaN(v)) return '–';
    var p = Math.round(v * 100);
    return (p < 0 ? '−' : '') + Math.abs(p) + '%';
  }
  function fmtFor(spec) {
    if (spec.fmt === 'pct') return spec.pctd ? function (v) { return v == null || isNaN(v) ? '–' : (v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(spec.pctd) + '%'; } : fmtPct;
    if (spec.fmt === 'dec') return function (v) { return v == null || isNaN(v) ? '–' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(spec.dp == null ? 1 : spec.dp) + (spec.unit || ''); };
    return function (v) { return fmtNum(v, spec.cur, spec.fmt === 'money'); };
  }
  function roleColor(role) {
    return { price: css('--s-price'), s1: css('--s1'), s2: css('--s2'), s3: css('--s3'), bench: css('--s-bench') }[role] || css('--s1');
  }

  function draw(box, spec) {
    box.innerHTML = '';
    var W = box.clientWidth, H = box.clientHeight;
    if (W < 40 || H < 40) return;
    var narrow = W < 520;
    var m = { l: narrow ? 46 : 58, r: 14, t: 10, b: 26 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var d = spec.d, n = d.length, dmax = d[n - 1] || 1;
    var lo = Infinity, hi = -Infinity;
    var vis = spec.cut != null ? Math.min(n - 1, spec.cut) : n - 1;
    spec.series.forEach(function (s) { s.v.forEach(function (v, i) { if (v != null && i <= vis) { if (v < lo) lo = v; if (v > hi) hi = v; } }); });
    var log = !!spec.log;
    (spec.levels || []).forEach(function (v) { if (v < lo) lo = v; if (v > hi) hi = v; });
    if (lo === Infinity) { lo = 0; hi = 1; }
    if (log) { lo = lo * 0.92; hi = hi * 1.08; } else { var pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad; }
    if (spec.ymin != null) lo = spec.ymin;
    if (spec.ymax != null) hi = spec.ymax;
    var X = function (i) { return m.l + (d[i] / dmax) * iw; };
    var Y = log
      ? function (v) { return m.t + ih - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * ih; }
      : function (v) { return m.t + ih - (v - lo) / (hi - lo) * ih; };

    var svg = node('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': spec.label || 'chart' }, box);

    // state shading (the rule's in/out calls)
    (spec.runs || []).forEach(function (r) {
      var x0 = X(r[0]), x1 = X(Math.min(r[1] + 1, n - 1));
      node('rect', { x: x0, y: m.t, width: Math.max(1, x1 - x0), height: ih,
        fill: r[2] === 1 ? css('--in-wash') : css('--out-wash') }, svg);
    });

    // grey spans (e.g. recessions)
    (spec.shade || []).forEach(function (r) {
      var x0 = X(Math.max(0, r[0])), x1 = X(Math.min(n - 1, r[1]));
      node('rect', { x: x0, y: m.t, width: Math.max(2, x1 - x0), height: ih, fill: css('--line'), opacity: 0.55 }, svg);
    });

    // grid + y ticks
    var ticks = log ? logTicks(lo, hi) : niceTicks(lo, hi, narrow ? 4 : 5);
    ticks.forEach(function (v) {
      var y = Y(v);
      node('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: css('--line'), 'stroke-width': 1 }, svg);
      var t = node('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end', fill: css('--muted'),
        'font-size': 11, 'font-family': css('--data') }, svg);
      t.textContent = fmtFor(spec)(v).replace('.00', '');
    });

    // x ticks: years for long spans, quarters otherwise
    var t0 = spec.t0, first = day(t0, 0), last = day(t0, dmax);
    var years = (last - first) / 3.156e10, marks = [];
    var y0 = first.getUTCFullYear(), y1 = last.getUTCFullYear();
    if (years > 2.5) {
      var every = years > 80 ? 20 : years > 40 ? 10 : years > 12 ? (narrow ? 8 : 4) : years > 6 ? 2 : 1;
      if (narrow && years > 4 && every < 2) every = 2;
      for (var y = y0 + 1; y <= y1; y++) if ((every >= 10 ? y % every : (y - y0 - 1) % every) === 0) marks.push([Date.UTC(y, 0, 1), String(y)]);
    } else {
      for (var yy = y0; yy <= y1; yy++) for (var q = 0; q < 12; q += 3) {
        var tq = Date.UTC(yy, q, 1);
        if (tq > first.getTime() && tq < last.getTime()) marks.push([tq, MON[q] + " '" + String(yy).slice(2)]);
      }
      if (narrow) marks = marks.filter(function (_, i) { return i % 2 === 0; });
    }
    marks.forEach(function (mk) {
      var dd = (mk[0] - first.getTime()) / 864e5, x = m.l + dd / dmax * iw;
      node('line', { x1: x, x2: x, y1: m.t + ih, y2: m.t + ih + 4, stroke: css('--line-2'), 'stroke-width': 1 }, svg);
      var t = node('text', { x: x, y: H - 6, 'text-anchor': 'middle', fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg);
      t.textContent = mk[1];
    });
    node('line', { x1: m.l, x2: W - m.r, y1: m.t + ih, y2: m.t + ih, stroke: css('--line-2'), 'stroke-width': 1 }, svg);

    // reference levels (e.g. RSI 30/70)
    (spec.levels || []).forEach(function (v) {
      var yl = Y(v);
      if (yl < m.t || yl > m.t + ih) return;
      node('line', { x1: m.l, x2: W - m.r, y1: yl, y2: yl, stroke: css('--band'), 'stroke-width': 1, 'stroke-dasharray': '4 4', opacity: 0.75 }, svg);
    });
    // labelled vertical pins (e.g. past market peaks)
    (spec.pins || []).forEach(function (pn, k) {
      if (pn[0] < 0 || pn[0] >= n) return;
      var xp = X(pn[0]);
      node('line', { x1: xp, x2: xp, y1: m.t, y2: m.t + ih, stroke: css('--muted'), 'stroke-width': 1, 'stroke-dasharray': '2 3', opacity: 0.8 }, svg);
      if (!narrow || k % 2 === 0) {
        var tp = node('text', { x: xp + 3, y: m.t + 10 + (k % 2) * 12, fill: css('--muted'), 'font-size': 10, 'font-family': css('--data') }, svg);
        tp.textContent = pn[1];
      }
    });
    // a vertical marker (practice mode: where the question stops)
    if (spec.mark != null && spec.mark < n) {
      var xm = X(spec.mark);
      node('line', { x1: xm, x2: xm, y1: m.t, y2: m.t + ih, stroke: css('--violet-ink'), 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }, svg);
    }

    // series (draw the primary last so it sits on top)
    var order = spec.series.map(function (s, i) { return i; }).reverse();
    order.forEach(function (si) {
      var s = spec.series[si], path = '', pen = false;
      var lastI = spec.cut != null ? Math.min(n - 1, spec.cut) : n - 1;
      for (var i = 0; i <= lastI; i++) {
        var v = s.v[i];
        if (v == null || (log && v <= 0)) { pen = false; continue; }
        path += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1);
        pen = true;
      }
      node('path', { d: path, fill: 'none', stroke: roleColor(s.role), 'stroke-width': s.role === 'price' ? 1.6 : 2,
        'stroke-linejoin': 'round', 'stroke-linecap': 'round', opacity: s.role === 'bench' ? 0.95 : 1 }, svg);
    });
    // end dot on the first series
    var p = spec.series[0];
    for (var k = (spec.cut != null ? Math.min(n - 1, spec.cut) : n - 1); k >= 0; k--) if (p.v[k] != null) {
      node('circle', { cx: X(k), cy: Y(p.v[k]), r: 4.5, fill: roleColor(p.role), stroke: css('--panel'), 'stroke-width': 2 }, svg);
      break;
    }

    // hover layer
    var cross = node('line', { x1: 0, x2: 0, y1: m.t, y2: m.t + ih, stroke: css('--ink-2'), 'stroke-width': 1, opacity: 0 }, svg);
    var dots = spec.series.map(function (s) {
      return node('circle', { r: 4, fill: roleColor(s.role), stroke: css('--panel'), 'stroke-width': 2, opacity: 0 }, svg);
    });
    var tt = document.createElement('div');
    tt.className = 'tt'; tt.hidden = true; box.appendChild(tt);
    var cur = null;

    function show(i) {
      cur = i;
      var x = X(i);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('opacity', 0.6);
      tt.textContent = '';
      var dl = document.createElement('div'); dl.className = 'd';
      var state = null;
      (spec.runs || []).forEach(function (r) { if (i >= r[0] && i <= r[1]) state = r[2]; });
      var shaded = (spec.shade || []).some(function (r) { return i >= r[0] && i <= r[1]; });
      dl.textContent = (spec.monthly ? MON[day(spec.t0, d[i]).getUTCMonth()] + ' ' + day(spec.t0, d[i]).getUTCFullYear() : fmtDate(day(spec.t0, d[i])))
        + (state == null ? '' : state === 1 ? ' · rule in' : ' · rule out') + (shaded ? ' · ' + (spec.shadeLabel || 'shaded') : '');
      tt.appendChild(dl);
      spec.series.forEach(function (s, si) {
        var v = s.v[i];
        if (v == null) { dots[si].setAttribute('opacity', 0); return; }
        dots[si].setAttribute('cx', x); dots[si].setAttribute('cy', Y(v)); dots[si].setAttribute('opacity', 1);
        var row = document.createElement('div'); row.className = 'row';
        var key = document.createElement('i'); key.style.background = roleColor(s.role);
        var val = document.createElement('b'); val.textContent = fmtFor(spec)(v);
        var lab = document.createElement('span'); lab.textContent = s.name;
        row.appendChild(key); row.appendChild(val); row.appendChild(lab); tt.appendChild(row);
      });
      tt.hidden = false;
      var tw = tt.offsetWidth;
      var left = x + 14 + tw > W ? x - 14 - tw : x + 14;
      tt.style.left = Math.max(0, left) + 'px';
    }
    function hide() {
      cur = null; tt.hidden = true; cross.setAttribute('opacity', 0);
      dots.forEach(function (c) { c.setAttribute('opacity', 0); });
    }
    function nearest(px) {
      var target = (px - m.l) / iw * dmax, lo2 = 0, hi2 = spec.cut != null ? Math.min(n - 1, spec.cut) : n - 1;
      if (spec.cut != null && target > d[hi2]) return hi2;
      while (hi2 - lo2 > 1) { var mid = (lo2 + hi2) >> 1; if (d[mid] < target) lo2 = mid; else hi2 = mid; }
      return Math.abs(d[lo2] - target) <= Math.abs(d[hi2] - target) ? lo2 : hi2;
    }
    var hit = node('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent' }, svg);
    hit.addEventListener('pointermove', function (e) {
      var r = svg.getBoundingClientRect();
      show(nearest((e.clientX - r.left) * (W / r.width)));
    });
    hit.addEventListener('pointerleave', hide);
    box.onkeydown = function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var step = Math.max(1, Math.round(n / 60)), top = spec.cut != null ? Math.min(n - 1, spec.cut) : n - 1;
      show(Math.max(0, Math.min(top, (cur == null ? top : cur) + (e.key === 'ArrowRight' ? step : -step))));
    };
    box.onblur = hide;
  }

  function initCharts() {
    [].forEach.call(document.querySelectorAll('.chart[data-chart]'), function (box) {
      var src = document.getElementById(box.getAttribute('data-chart'));
      if (!src) return;
      var spec = JSON.parse(src.textContent);
      box.tabIndex = 0;
      var redraw = function () { draw(box, spec); };
      redraw();
      if (window.ResizeObserver) {
        var w = box.clientWidth;
        new ResizeObserver(function () { if (Math.abs(box.clientWidth - w) > 2) { w = box.clientWidth; redraw(); } }).observe(box);
      }
    });
  }

  // <select data-nav>: each option's value is a URL to open
  function initNav() {
    [].forEach.call(document.querySelectorAll('select[data-nav]'), function (sel) {
      var tmpl = sel.getAttribute('data-tmpl');
      sel.addEventListener('change', function () { if (sel.value) location.href = tmpl ? tmpl.replace('{v}', sel.value) : sel.value; });
    });
  }

  window.QChart = { draw: draw };

  function initPicker() {
    var f = document.getElementById('picker');
    if (!f) return;
    var tmpl = f.getAttribute('data-href');
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var s = document.getElementById('pick-strategy').value, t = document.getElementById('pick-stock').value;
      location.href = tmpl.replace('{t}', t).replace('{s}', s);
    });
  }

  // header menus: hover or focus on desktop; on touch screens the first tap opens the menu, the second follows the link
  function initMenus() {
    var items = document.querySelectorAll('.nav-item.has-dd');
    if (!items.length) return;
    var touch = window.matchMedia && window.matchMedia('(hover: none)').matches;
    function closeAll(except) {
      [].forEach.call(items, function (it) { if (it !== except) { it.classList.remove('open'); it.querySelector('.nav-top').setAttribute('aria-expanded', 'false'); } });
    }
    [].forEach.call(items, function (it) {
      var top = it.querySelector('.nav-top');
      top.addEventListener('click', function (e) {
        if (touch && !it.classList.contains('open')) {
          e.preventDefault(); closeAll(it); it.classList.add('open'); top.setAttribute('aria-expanded', 'true');
        }
      });
      it.addEventListener('mouseenter', function () { if (!touch) top.setAttribute('aria-expanded', 'true'); });
      it.addEventListener('mouseleave', function () { if (!touch) top.setAttribute('aria-expanded', 'false'); });
    });
    document.addEventListener('click', function (e) { if (!e.target.closest || !e.target.closest('.nav-item')) closeAll(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeAll(); if (document.activeElement && document.activeElement.closest && document.activeElement.closest('.nav-item')) document.activeElement.blur(); } });
  }

  function init() { initCharts(); initPicker(); initNav(); initMenus(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
