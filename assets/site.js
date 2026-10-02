/* site.js — renders Quiplee's strategy charts from embedded JSON and wires the
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
    else if (a >= 1e4) s = Math.round(v).toLocaleString('en-US');
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
  function roleColor(role) {
    return { price: css('--s-price'), s1: css('--s1'), s2: css('--s2'), bench: css('--s-bench') }[role] || css('--s1');
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
    spec.series.forEach(function (s) { s.v.forEach(function (v) { if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; } }); });
    var log = !!spec.log;
    if (log) { lo = lo * 0.92; hi = hi * 1.08; } else { var pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad; }
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

    // grid + y ticks
    var ticks = log ? logTicks(lo, hi) : niceTicks(lo, hi, narrow ? 4 : 5);
    ticks.forEach(function (v) {
      var y = Y(v);
      node('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: css('--line'), 'stroke-width': 1 }, svg);
      var t = node('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end', fill: css('--muted'),
        'font-size': 11, 'font-family': css('--data') }, svg);
      t.textContent = fmtNum(v, spec.cur, spec.fmt === 'money').replace('.00', '');
    });

    // x ticks: years for long spans, quarters otherwise
    var t0 = spec.t0, first = day(t0, 0), last = day(t0, dmax);
    var years = (last - first) / 3.156e10, marks = [];
    var y0 = first.getUTCFullYear(), y1 = last.getUTCFullYear();
    if (years > 2.5) {
      var every = years > 12 ? 4 : years > 6 ? 2 : 1;
      for (var y = y0 + 1; y <= y1; y++) if ((y - y0 - 1) % every === 0) marks.push([Date.UTC(y, 0, 1), String(y)]);
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

    // series (draw the primary last so it sits on top)
    var order = spec.series.map(function (s, i) { return i; }).reverse();
    order.forEach(function (si) {
      var s = spec.series[si], path = '', pen = false;
      for (var i = 0; i < n; i++) {
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
    for (var k = n - 1; k >= 0; k--) if (p.v[k] != null) {
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
      dl.textContent = fmtDate(day(spec.t0, d[i])) + (state == null ? '' : state === 1 ? ' · rule in' : ' · rule out');
      tt.appendChild(dl);
      spec.series.forEach(function (s, si) {
        var v = s.v[i];
        if (v == null) { dots[si].setAttribute('opacity', 0); return; }
        dots[si].setAttribute('cx', x); dots[si].setAttribute('cy', Y(v)); dots[si].setAttribute('opacity', 1);
        var row = document.createElement('div'); row.className = 'row';
        var key = document.createElement('i'); key.style.background = roleColor(s.role);
        var val = document.createElement('b'); val.textContent = fmtNum(v, spec.cur, spec.fmt === 'money');
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
      var target = (px - m.l) / iw * dmax, lo2 = 0, hi2 = n - 1;
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
      var step = Math.max(1, Math.round(n / 60));
      show(Math.max(0, Math.min(n - 1, (cur == null ? n - 1 : cur) + (e.key === 'ArrowRight' ? step : -step))));
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

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { initCharts(); initPicker(); });
  else { initCharts(); initPicker(); }
})();
