/* lab.js — hands-on widgets for the Learn tracks, and the step-by-step lesson
 * layout. Each widget is a [data-lab="name"] element whose data sits in a
 * <script type="application/json"> named by data-src. Uses helpers from widgets.js. */
(function () {
  'use strict';
  if (!window.QW) return;
  var Q = window.QW, el = Q.el, svgEl = Q.svgEl, css = Q.css;
  function fmt(v, cur, d) { return Q.money(v, cur == null ? '$' : cur).replace(/\.00$/, d === 0 ? '' : '.00'); }
  function pc(v, d) { return Q.pct(v, d == null ? 0 : d); }
  function slider(label, min, max, step, val, fmtFn, onInput) {
    var out = el('b', { text: fmtFn(val) });
    var inp = el('input', { type: 'range', min: min, max: max, step: step, value: val, 'aria-label': label });
    inp.addEventListener('input', function () { out.textContent = fmtFn(+inp.value); onInput(+inp.value); });
    var wrap = el('label', { 'class': 'lab-sl' }, [el('span', { text: label }), inp, out]);
    wrap.set = function (v) { inp.value = v; out.textContent = fmtFn(v); };
    wrap.get = function () { return +inp.value; };
    return wrap;
  }
  function select(label, opts, onChange, val) {
    var s = el('select', { 'aria-label': label });
    opts.forEach(function (o) { var op = el('option', { value: o[0], text: o[1] }); if (o[0] === val) op.selected = true; s.appendChild(op); });
    s.addEventListener('change', function () { onChange(s.value); });
    return el('label', { 'class': 'lab-sel small muted' }, [label, s]);
  }
  function stat(label, value, note, cls) {
    return el('div', { 'class': 'lab-stat' }, [el('span', { 'class': 'tile-label', text: label }), el('b', { 'class': cls || '', text: value }), note ? el('span', { 'class': 'small muted', text: note }) : null]);
  }
  function big(v) { return Q.bigNum(v); }

  // ------------------------------------------------------------ 1. a slice of the company
  function Slice(box, D) {
    var st = { i: 0, amt: 1000 };
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'lab-out' }), bars = el('div', { 'class': 'lab-bars' });
    ui.appendChild(select('Company', D.cos.map(function (c, i) { return [String(i), c.n + ' (' + c.s + ')']; }), function (v) { st.i = +v; draw(); }));
    ui.appendChild(slider('You invest', 100, 100000, 100, st.amt, function (v) { return '$' + v.toLocaleString('en-US'); }, function (v) { st.amt = v; draw(); }));
    box.appendChild(ui); box.appendChild(out); box.appendChild(bars);
    function draw() {
      var c = D.cos[st.i], shares = st.amt / c.p, own = shares / c.sh;
      out.innerHTML = '';
      out.appendChild(stat('Share price', fmt(c.p, c.cur), 'What one slice costs'));
      out.appendChild(stat('Shares outstanding', big(c.sh), 'Slices the company is cut into'));
      out.appendChild(stat('Market cap', c.cur + big(c.p * c.sh), 'Price × shares: the whole company'));
      out.appendChild(stat('You would own', shares >= 1 ? shares.toFixed(shares < 10 ? 2 : 0) + ' shares' : shares.toFixed(4) + ' of a share', '1 part in ' + big(1 / own) + ' of the company'));
      if (c.eps != null) out.appendChild(stat('Your slice of last year\'s profit', fmt(shares * c.eps, c.cur), c.eps > 0 ? 'Earnings per share × your shares' : 'The company lost money, so your slice is a loss', c.eps > 0 ? 'up' : 'down'));
      bars.innerHTML = '';
      var mx = Math.max.apply(null, D.cos.map(function (x) { return x.p * x.sh; }));
      bars.appendChild(el('p', { 'class': 'small muted', text: 'Same companies by size. Notice the share price says nothing about how big a company is.' }));
      D.cos.forEach(function (x, i) {
        var w = 100 * x.p * x.sh / mx;
        bars.appendChild(el('div', { 'class': 'lab-bar' + (i === st.i ? ' on' : '') }, [el('span', { text: x.s + ' · ' + fmt(x.p, x.cur) + '/share' }), el('span', { 'class': 'trk' }, [el('i', { style: 'width:' + Math.max(0.6, w).toFixed(1) + '%' })]), el('b', { text: x.cur + big(x.p * x.sh) })]));
      });
    }
    draw();
  }

  // ------------------------------------------------------------ 2. order book
  function OrderBook(box) {
    var st, log = el('p', { 'class': 'lab-log', 'aria-live': 'polite' });
    var book = el('div', { 'class': 'ob' }), chart = el('div', { 'class': 'ob-chart' }), info = el('div', { 'class': 'lab-out' });
    var btns = el('div', { 'class': 'lab-btns' });
    function reset() {
      st = { bids: [], asks: [], last: 50, hist: [50] };
      for (var i = 1; i <= 8; i++) { st.bids.push([+(50 - i * 0.02).toFixed(2), 100 + Math.round(Math.random() * 6) * 100]); st.asks.push([+(50 + i * 0.02 - 0.01).toFixed(2), 100 + Math.round(Math.random() * 6) * 100]); }
      log.textContent = 'Buyers (bids, left) and sellers (asks, right) are waiting at their prices. Try a market order.';
      draw();
    }
    function trade(side, qty) {
      var levels = side === 'buy' ? st.asks : st.bids, left = qty, cost = 0, fills = [];
      while (left > 0 && levels.length) {
        var lv = levels[0], take = Math.min(left, lv[1]);
        lv[1] -= take; left -= take; cost += take * lv[0]; fills.push(take + ' at $' + lv[0].toFixed(2)); st.last = lv[0]; st.hist.push(lv[0]);
        if (lv[1] === 0) levels.shift();
      }
      refill();
      var avg = cost / (qty - left);
      log.textContent = 'You ' + (side === 'buy' ? 'bought' : 'sold') + ' ' + (qty - left) + ' shares: ' + fills.join(', ') + '. Average $' + avg.toFixed(3) + '. ' +
        (side === 'buy' ? 'You used up the cheapest sellers, so the next trade happens higher: that is how buying pushes a price up.' : 'You used up the highest buyers, so the next trade happens lower: that is how selling pushes a price down.');
      draw();
    }
    function refill() {
      while (st.asks.length < 8) { var a = st.asks.length ? st.asks[st.asks.length - 1][0] + 0.02 : st.last + 0.01; st.asks.push([+a.toFixed(2), 100 + Math.round(Math.random() * 6) * 100]); }
      while (st.bids.length < 8) { var b = st.bids.length ? st.bids[st.bids.length - 1][0] - 0.02 : st.last - 0.01; st.bids.push([+b.toFixed(2), 100 + Math.round(Math.random() * 6) * 100]); }
    }
    function news(dir) {
      var shift = dir * (0.3 + Math.random() * 0.3);
      st.bids.forEach(function (l) { l[0] = +(l[0] + shift).toFixed(2); });
      st.asks.forEach(function (l) { l[0] = +(l[0] + shift).toFixed(2); });
      st.last = +(st.last + shift).toFixed(2); st.hist.push(st.last);
      log.textContent = dir > 0 ? 'Good news: buyers raise what they will pay and sellers ask for more. No shares had to trade for the price to jump.' : 'Bad news: sellers accept less and buyers pull back. The price gaps down before anyone trades.';
      draw();
    }
    [['Buy 600 at market', function () { trade('buy', 600); }], ['Sell 600 at market', function () { trade('sell', 600); }],
     ['Good news', function () { news(1); }], ['Bad news', function () { news(-1); }], ['Reset', reset]].forEach(function (b) {
      btns.appendChild(el('button', { type: 'button', 'class': 'btn sm', text: b[0], on: { click: b[1] } }));
    });
    box.appendChild(btns); box.appendChild(log); box.appendChild(el('div', { 'class': 'ob-wrap' }, [book, chart])); box.appendChild(info);
    function draw() {
      book.innerHTML = '';
      var mx = Math.max.apply(null, st.bids.concat(st.asks).map(function (l) { return l[1]; }));
      var head = el('div', { 'class': 'ob-row ob-head' }, [el('span', { text: 'Bid size' }), el('span', { text: 'Bid' }), el('span', { text: 'Ask' }), el('span', { text: 'Ask size' })]);
      book.appendChild(head);
      for (var i = 0; i < 8; i++) {
        var b = st.bids[i], a = st.asks[i];
        book.appendChild(el('div', { 'class': 'ob-row' }, [
          el('span', { 'class': 'ob-sz bid' }, [el('i', { style: 'width:' + (b ? 100 * b[1] / mx : 0) + '%' }), b ? String(b[1]) : '']),
          el('span', { 'class': 'ob-px bid', text: b ? '$' + b[0].toFixed(2) : '' }),
          el('span', { 'class': 'ob-px ask', text: a ? '$' + a[0].toFixed(2) : '' }),
          el('span', { 'class': 'ob-sz ask' }, [el('i', { style: 'width:' + (a ? 100 * a[1] / mx : 0) + '%' }), a ? String(a[1]) : ''])]));
      }
      info.innerHTML = '';
      info.appendChild(stat('Last trade', '$' + st.last.toFixed(2)));
      info.appendChild(stat('Spread', '$' + (st.asks[0][0] - st.bids[0][0]).toFixed(2), 'Gap between best ask and best bid'));
      drawChart();
    }
    function drawChart() {
      chart.innerHTML = '';
      var W = chart.clientWidth;
      if (!W) return;
      var H = 150, h = st.hist.slice(-40), lo = Math.min.apply(null, h) - 0.05, hi = Math.max.apply(null, h) + 0.05;
      var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Recent trades' }, chart);
      var p = h.map(function (v, i) { return (i ? 'L' : 'M') + (8 + i * (W - 16) / Math.max(1, h.length - 1)).toFixed(1) + ' ' + (8 + (hi - v) / (hi - lo) * (H - 16)).toFixed(1); }).join('');
      svgEl('path', { d: p, fill: 'none', stroke: css('--s1'), 'stroke-width': 2 }, svg);
      var t = svgEl('text', { x: 8, y: H - 4, fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg); t.textContent = 'Trade prices';
    }
    reset();
    Q.onResize(chart, drawChart);
  }

  // ------------------------------------------------------------ 3. candle builder
  var PRESETS = { 'Big up day': [20, 82, 18, 80], 'Big down day': [80, 82, 18, 20], 'Doji': [50, 75, 25, 50], 'Hammer': [62, 74, 20, 72], 'Shooting star': [38, 80, 29, 31], 'Spinning top': [48, 70, 30, 53] };
  function candleName(o, h, l, c) {
    var rng = h - l || 1, body = Math.abs(c - o), up = h - Math.max(o, c), dn = Math.min(o, c) - l, b = body / rng;
    if (b < 0.07) {
      if (up > 0.65 * rng) return ['Gravestone doji', 'Opened and closed near the low after buyers pushed it far higher: the rally was rejected. After a rise it can warn of a turn down.'];
      if (dn > 0.65 * rng) return ['Dragonfly doji', 'Opened and closed near the high after sellers pushed it far lower: the selling was rejected. After a fall it can hint at a turn up.'];
      return ['Doji', 'Open and close almost equal: buyers and sellers fought to a draw. After a long run it can mean the move is tiring.'];
    }
    if (b <= 0.35 && dn >= 2 * body && up <= 0.15 * rng) return ['Hammer', 'Sellers pushed it well down, buyers pushed it back up to close near the high. After a fall it hints that buyers are stepping in.'];
    if (b <= 0.35 && up >= 2 * body && dn <= 0.15 * rng) return ['Shooting star', 'Buyers pushed it well up but it closed near the low. After a rise it hints that sellers are stepping in.'];
    if (b > 0.85) return [c > o ? 'Big up day (marubozu)' : 'Big down day (marubozu)', c > o ? 'Opened near the low and closed near the high: buyers in control all day.' : 'Opened near the high and closed near the low: sellers in control all day.'];
    if (b < 0.35) return ['Spinning top', 'Small body, wicks both ways: an undecided day.'];
    return [c > o ? 'Up day' : 'Down day', c > o ? 'Closed above where it opened.' : 'Closed below where it opened.'];
  }
  function CandleBuilder(box) {
    var st = { o: 40, h: 75, l: 25, c: 65 };
    // sliders run 0-100; shown as prices between $95 and $105 so the moves look like a real day
    function px(v) { return 95 + v / 10; }
    var ui = el('div', { 'class': 'lab-ui lab-ui-4' }), pre = el('div', { 'class': 'chips' }), pic = el('div', { 'class': 'cb-pic' }), txt = el('div', { 'class': 'cb-txt' });
    var sl = {};
    [['o', 'Open'], ['h', 'High'], ['l', 'Low'], ['c', 'Close']].forEach(function (k) {
      sl[k[0]] = slider(k[1], 0, 100, 1, st[k[0]], function (v) { return '$' + px(v).toFixed(2); }, function (v) { st[k[0]] = v; fix(k[0]); draw(); });
      ui.appendChild(sl[k[0]]);
    });
    Object.keys(PRESETS).forEach(function (n) {
      pre.appendChild(el('button', { type: 'button', 'class': 'chip-btn', text: n, on: { click: function () { var p = PRESETS[n]; st = { o: p[0], h: Math.max(p[1], p[0], p[3]), l: Math.min(p[2], p[0], p[3]), c: p[3] }; Object.keys(sl).forEach(function (k) { sl[k].set(st[k]); }); draw(); } } }));
    });
    function fix(k) {
      if (k === 'h') st.h = Math.max(st.h, st.o, st.c); else if (k === 'l') st.l = Math.min(st.l, st.o, st.c);
      else { st.h = Math.max(st.h, st[k]); st.l = Math.min(st.l, st[k]); }
      Object.keys(sl).forEach(function (x) { sl[x].set(st[x]); });
    }
    box.appendChild(pre); box.appendChild(el('div', { 'class': 'cb-wrap' }, [pic, txt])); box.appendChild(ui);
    function draw() {
      pic.innerHTML = '';
      var W = 250, H = 260, Y = function (v) { return 12 + (100 - v) / 100 * (H - 24); };
      var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Candle' }, pic);
      var up = st.c >= st.o, col = css(up ? '--candle-up' : '--candle-down'), x = 90;
      svgEl('line', { x1: x, x2: x, y1: Y(st.h), y2: Y(st.l), stroke: col, 'stroke-width': 3 }, svg);
      var yt = Y(Math.max(st.o, st.c)), yb = Y(Math.min(st.o, st.c));
      svgEl('rect', { x: x - 26, y: yt, width: 52, height: Math.max(2, yb - yt), fill: up ? css('--panel') : col, stroke: col, 'stroke-width': 3, rx: 2 }, svg);
      // labels sorted top to bottom and pushed apart so they never overlap; a leader line joins each to its price
      var labs = [['High', st.h], [up ? 'Close' : 'Open', Math.max(st.o, st.c)], [up ? 'Open' : 'Close', Math.min(st.o, st.c)], ['Low', st.l]]
        .map(function (p) { return { t: p[0] + ' $' + px(p[1]).toFixed(2), y: Y(p[1]) }; });
      var gap = 16, i2;
      for (i2 = 0; i2 < labs.length; i2++) labs[i2].ly = i2 ? Math.max(labs[i2].y, labs[i2 - 1].ly + gap) : Math.max(labs[i2].y, 10);
      for (i2 = labs.length - 1; i2 >= 0; i2--) labs[i2].ly = Math.min(labs[i2].ly, i2 < labs.length - 1 ? labs[i2 + 1].ly - gap : H - 8);
      labs.forEach(function (lb) {
        svgEl('path', { d: 'M' + (x + 30) + ' ' + lb.y + 'H' + (x + 38) + 'L' + (x + 46) + ' ' + lb.ly + 'H' + (x + 50), fill: 'none', stroke: css('--muted'), 'stroke-width': 1 }, svg);
        var t = svgEl('text', { x: x + 54, y: lb.ly + 4, fill: css('--ink-2'), 'font-size': 12, 'font-family': css('--data') }, svg);
        t.textContent = lb.t;
      });
      var nm = candleName(st.o, st.h, st.l, st.c);
      txt.innerHTML = '';
      txt.appendChild(el('p', { 'class': 'eyebrow', text: 'This candle' }));
      txt.appendChild(el('p', { 'class': 'h3', text: nm[0] }));
      txt.appendChild(el('p', { text: nm[1] }));
      txt.appendChild(el('p', { 'class': 'small muted', text: 'Body $' + (Math.abs(st.c - st.o) / 10).toFixed(2) + ' · upper wick $' + ((st.h - Math.max(st.o, st.c)) / 10).toFixed(2) + ' · lower wick $' + ((Math.min(st.o, st.c) - st.l) / 10).toFixed(2) + '. Closed ' + pc((px(st.c) - px(st.o)) / px(st.o), 1) + ' from the open; the day\'s range was ' + pc((px(st.h) - px(st.l)) / px(st.l), 1).replace('+', '') + '.' }));
    }
    draw();
  }

  // ------------------------------------------------------------ 4. swing points and the MA playground
  function series(D, key) { var s = D.series[key]; return { t0: s.t0, d: s.d, c: s.c, cur: s.cur, name: s.name }; }
  function zigzag(c, th) {
    // swing points: a high is confirmed once price falls th below it, a low once price rises th above it
    var piv = [], dir = 0, hi = 0, lo = 0;
    for (var i = 1; i < c.length; i++) {
      if (dir !== -1 && c[i] > c[hi]) hi = i;
      if (dir !== 1 && c[i] < c[lo]) lo = i;
      if (dir !== -1 && c[i] <= c[hi] * (1 - th)) { piv.push([hi, 'H']); dir = -1; lo = i; continue; }
      if (dir !== 1 && c[i] >= c[lo] * (1 + th)) { piv.push([lo, 'L']); dir = 1; hi = i; }
    }
    return piv;
  }
  function lineChart(box, S, extra, opts) {
    box.innerHTML = '';
    var W = box.clientWidth || 600, H = opts && opts.h || 300, m = { l: 50, r: 10, t: 10, b: 22 };
    var n = S.c.length, lo = Infinity, hi = -Infinity;
    S.c.forEach(function (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); });
    (extra || []).forEach(function (s) { s.v.forEach(function (v) { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }); });
    var pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
    var X = function (i) { return m.l + i / (n - 1) * (W - m.l - m.r); }, Y = function (v) { return m.t + (hi - v) / (hi - lo) * (H - m.t - m.b); };
    var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': S.name + ' price' }, box);
    Q.niceTicks(lo, hi, 4).forEach(function (v) {
      svgEl('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: css('--line') }, svg);
      var t = svgEl('text', { x: m.l - 6, y: Y(v) + 4, 'text-anchor': 'end', fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg); t.textContent = Q.money(v, '').replace('.00', '');
    });
    var y0 = +S.t0.slice(0, 4), last = Q.day(S.t0, S.d[n - 1]).getUTCFullYear();
    for (var yy = y0 + 1; yy <= last; yy++) {
      var dd = (Date.UTC(yy, 0, 1) - Date.parse(S.t0 + 'T00:00:00Z')) / 864e5, idx = S.d.findIndex(function (x) { return x >= dd; });
      if (idx > 0) { var tx = svgEl('text', { x: X(idx), y: H - 5, 'text-anchor': 'middle', fill: css('--muted'), 'font-size': 11, 'font-family': css('--data') }, svg); tx.textContent = String(yy); }
    }
    return { svg: svg, X: X, Y: Y, W: W, H: H, m: m };
  }
  function path(X, Y, v) { var p = '', pen = false; v.forEach(function (x, i) { if (x == null) { pen = false; return; } p += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(x).toFixed(1); pen = true; }); return p; }
  function Swings(box, D) {
    var st = { key: D.def || Object.keys(D.series)[0], th: 0.1 };
    var ui = el('div', { 'class': 'lab-ui' }), plot = el('div', { 'class': 'lab-plot' }), txt = el('p', { 'class': 'lab-log', 'aria-live': 'polite' });
    ui.appendChild(select('Chart', Object.keys(D.series).map(function (k) { return [k, D.series[k].name]; }), function (v) { st.key = v; draw(); }, st.key));
    ui.appendChild(slider('Swing size', 3, 25, 1, 10, function (v) { return v + '%'; }, function (v) { st.th = v / 100; draw(); }));
    box.appendChild(ui); box.appendChild(plot); box.appendChild(txt);
    function draw() {
      var S = series(D, st.key), g = lineChart(plot, S);
      svgEl('path', { d: path(g.X, g.Y, S.c), fill: 'none', stroke: css('--s-price'), 'stroke-width': 1.4 }, g.svg);
      var piv = zigzag(S.c, st.th), lastH = null, lastL = null, labels = [];
      var zp = piv.map(function (p, i) { return (i ? 'L' : 'M') + g.X(p[0]).toFixed(1) + ' ' + g.Y(S.c[p[0]]).toFixed(1); }).join('');
      svgEl('path', { d: zp, fill: 'none', stroke: css('--violet-ink'), 'stroke-width': 1.5, 'stroke-dasharray': '4 3' }, g.svg);
      piv.forEach(function (p) {
        var v = S.c[p[0]], lab;
        if (p[1] === 'H') { lab = lastH == null ? 'H' : v > lastH ? 'HH' : 'LH'; lastH = v; } else { lab = lastL == null ? 'L' : v > lastL ? 'HL' : 'LL'; lastL = v; }
        labels.push(lab);
        var good = lab === 'HH' || lab === 'HL';
        svgEl('circle', { cx: g.X(p[0]), cy: g.Y(v), r: 4, fill: good ? css('--in') : (lab.length === 1 ? css('--muted') : css('--out')) }, g.svg);
        var t = svgEl('text', { x: g.X(p[0]), y: g.Y(v) + (p[1] === 'H' ? -8 : 16), 'text-anchor': 'middle', fill: css('--ink-2'), 'font-size': 10.5, 'font-family': css('--data') }, g.svg);
        t.textContent = lab;
      });
      var tail = labels.slice(-2).sort().join(' + ');
      var read = tail === 'HH + HL' ? 'The latest swings are a higher high and a higher low: an uptrend.' : tail === 'LH + LL' ? 'The latest swings are a lower high and a lower low: a downtrend.' : 'The latest swings disagree: the trend is changing or the price is moving sideways.';
      txt.textContent = piv.length + ' swings of ' + Math.round(st.th * 100) + '% or more. ' + read + ' Raise the swing size and only the big turns remain; lower it and every wiggle counts.';
    }
    Q.onResize(plot, draw);
  }
  function MaPlay(box, D) {
    var st = { key: D.def || Object.keys(D.series)[0], n: 50, kind: 'sma' };
    var ui = el('div', { 'class': 'lab-ui' }), plot = el('div', { 'class': 'lab-plot' }), out = el('div', { 'class': 'lab-out' });
    ui.appendChild(select('Chart', Object.keys(D.series).map(function (k) { return [k, D.series[k].name]; }), function (v) { st.key = v; draw(); }, st.key));
    ui.appendChild(slider('Average length (days)', 5, 250, 5, st.n, function (v) { return v + ' days'; }, function (v) { st.n = v; draw(); }));
    ui.appendChild(select('Type', [['sma', 'Simple'], ['ema', 'Exponential']], function (v) { st.kind = v; draw(); }, 'sma'));
    box.appendChild(ui); box.appendChild(plot); box.appendChild(out);
    function draw() {
      var S = series(D, st.key), ma = st.kind === 'sma' ? Q.sma(S.c, st.n) : Q.ema(S.c, st.n);
      if (st.kind === 'ema') for (var z = 0; z < st.n - 1 && z < ma.length; z++) ma[z] = null;
      var g = lineChart(plot, S, [{ v: ma }]);
      // shade the days the rule is in
      var start = null;
      for (var i = 1; i <= S.c.length; i++) {
        var on = i < S.c.length && ma[i - 1] != null && S.c[i - 1] > ma[i - 1];
        if (on && start == null) start = i;
        if (!on && start != null) { svgEl('rect', { x: g.X(start), y: g.m.t, width: Math.max(1, g.X(i - 1) - g.X(start)), height: g.H - g.m.t - g.m.b, fill: css('--in-wash') }, g.svg); start = null; }
      }
      svgEl('path', { d: path(g.X, g.Y, S.c), fill: 'none', stroke: css('--s-price'), 'stroke-width': 1.3 }, g.svg);
      svgEl('path', { d: path(g.X, g.Y, ma), fill: 'none', stroke: css('--s1'), 'stroke-width': 2 }, g.svg);
      var cross = 0, inDays = 0, eqR = 1, first = null;
      for (var j = 1; j < S.c.length; j++) {
        if (ma[j - 1] == null) continue;
        if (first == null) first = j - 1;
        var wasIn = S.c[j - 1] > ma[j - 1];
        if (wasIn) { inDays++; eqR *= S.c[j] / S.c[j - 1]; }
        if (j > 1 && ma[j - 2] != null && (S.c[j - 2] > ma[j - 2]) !== wasIn) cross++;
      }
      var bh = first != null ? S.c[S.c.length - 1] / S.c[first] - 1 : null, days = first != null ? S.c.length - 1 - first : 1;
      out.innerHTML = '';
      out.appendChild(stat('Times the price crossed it', String(cross), 'Each one is a buy or sell for a "be in above the average" rule'));
      out.appendChild(stat('Time above the average', Math.round(100 * inDays / days) + '%', 'Green shading'));
      out.appendChild(stat('That simple rule', pc(eqR - 1), 'Before costs, no interest while out', eqR - 1 >= (bh || 0) ? 'up' : 'down'));
      out.appendChild(stat('Just holding', pc(bh), 'Same dates'));
    }
    Q.onResize(plot, draw);
  }

  // ------------------------------------------------------------ 5. P/E explorer
  function PE(box, D) {
    var st = { i: 0, g: 10, pe: null };
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'lab-out' }), txt = el('p', { 'class': 'lab-log', 'aria-live': 'polite' });
    var gS = slider('Profit growth over the next year', -60, 100, 1, st.g, function (v) { return (v > 0 ? '+' : '') + v + '%'; }, function (v) { st.g = v; draw(); });
    var pS = slider('P/E buyers will pay a year from now', 4, 80, 1, 20, function (v) { return v + '×'; }, function (v) { st.pe = v; draw(); });
    ui.appendChild(select('Company', D.cos.map(function (c, i) { return [String(i), c.n + ' (' + c.s + ')']; }), function (v) { st.i = +v; st.pe = null; seed(); draw(); }));
    ui.appendChild(gS); ui.appendChild(pS);
    box.appendChild(ui); box.appendChild(out); box.appendChild(txt);
    function seed() { var c = D.cos[st.i]; st.pe = Math.round(Math.min(80, Math.max(4, c.pe || 20))); pS.set(st.pe); st.g = c.feps && c.eps > 0 ? Math.round(Math.max(-60, Math.min(100, (c.feps / c.eps - 1) * 100))) : 10; gS.set(st.g); }
    function draw() {
      var c = D.cos[st.i], eps1 = c.eps * (1 + st.g / 100), px1 = eps1 * st.pe, ret = px1 / c.p - 1;
      out.innerHTML = '';
      out.appendChild(stat('Price now', fmt(c.p, c.cur)));
      out.appendChild(stat('Earnings per share, last year', fmt(c.eps, c.cur)));
      out.appendChild(stat('P/E now', c.pe ? c.pe.toFixed(1) + '×' : 'n/a', c.pe ? 'Price ÷ earnings per share' : 'No profit to divide by'));
      if (c.fpe) out.appendChild(stat('Forward P/E', c.fpe.toFixed(1) + '×', 'On analysts\' estimate for next year'));
      out.appendChild(stat('Price in a year, if…', fmt(px1, c.cur), (st.g >= 0 ? '+' : '') + st.g + '% profit × ' + st.pe + '× P/E', ret >= 0 ? 'up' : 'down'));
      out.appendChild(stat('Return', pc(ret), 'Before dividends', ret >= 0 ? 'up' : 'down'));
      if (c.eps > 0) {
        var mult = c.pe ? st.pe / c.pe - 1 : 0;
        txt.textContent = 'Price = earnings per share × P/E. Your return comes from two places: profit growth (' + pc(st.g / 100) + ') and the change in what buyers pay for each dollar of profit (' + pc(mult) + '). ' +
          (c.pe && c.pe > 35 ? 'At a high P/E, a lot of growth is already in the price: if the P/E falls back, strong profit growth can still mean a falling stock.' : 'Try growth of 20% with the P/E falling by a third: the stock still drops.');
      } else txt.textContent = 'This company lost money last year, so the P/E means nothing. Investors value it on sales or on the profits they expect later, which makes the price swing more on every forecast.';
    }
    seed(); draw();
  }

  // ------------------------------------------------------------ 6. balance-sheet stress test
  function Stress(box, D) {
    var st = { i: 0, ev: 20, op: 30, rate: 2 };
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'lab-out' }), txt = el('p', { 'class': 'lab-log', 'aria-live': 'polite' });
    ui.appendChild(select('Company', D.cos.map(function (c, i) { return [String(i), c.n + ' (' + c.s + ')']; }), function (v) { st.i = +v; draw(); }));
    ui.appendChild(slider('Whole business marked down', 0, 60, 5, st.ev, function (v) { return '−' + v + '%'; }, function (v) { st.ev = v; draw(); }));
    ui.appendChild(slider('Operating profit falls', 0, 90, 5, st.op, function (v) { return '−' + v + '%'; }, function (v) { st.op = v; draw(); }));
    ui.appendChild(slider('Interest rates rise', 0, 6, 0.5, st.rate, function (v) { return '+' + v + ' pts'; }, function (v) { st.rate = v; draw(); }));
    box.appendChild(ui); box.appendChild(out); box.appendChild(txt);
    function draw() {
      var c = D.cos[st.i], net = (c.debt || 0) - (c.cash || 0), ev = c.mcap + net, ev1 = ev * (1 - st.ev / 100), eq1 = ev1 - net;
      var stockMove = eq1 / c.mcap - 1;
      var r0 = c.debt && c.interest ? c.interest / c.debt : 0.05, int1 = (c.debt || 0) * (r0 + st.rate / 100);
      var ebit1 = c.ebit != null ? c.ebit * (1 - st.op / 100) : null, cov0 = c.interest ? c.ebit / c.interest : null, cov1 = ebit1 != null && int1 > 0 ? ebit1 / int1 : null;
      out.innerHTML = '';
      out.appendChild(stat('Net debt', c.cur + big(net), net < 0 ? 'Net cash: more cash than debt' : 'Debt minus cash'));
      out.appendChild(stat('Stock if the business is marked down ' + st.ev + '%', eq1 > 0 ? pc(stockMove) : 'wiped out', 'Debt gets paid first; shareholders take the rest of the hit', stockMove < -0.5 || eq1 <= 0 ? 'down' : ''));
      out.appendChild(stat('Interest cover now', cov0 != null ? cov0.toFixed(1) + '×' : '–', 'Operating profit ÷ interest'));
      out.appendChild(stat('Interest cover after the shock', cov1 != null ? (cov1 < 0 ? 'losing money' : cov1.toFixed(1) + '×') : '–', cov1 != null && cov1 < 2 ? 'Under 2×: interest becomes hard to pay' : '', cov1 != null && cov1 < 2 ? 'down' : 'up'));
      var lev = (stockMove / -(st.ev / 100));
      txt.textContent = st.ev ? 'A ' + st.ev + '% markdown of the whole business moves this stock ' + (eq1 > 0 ? pc(stockMove) : 'to zero') + ', ' + (isFinite(lev) && eq1 > 0 ? lev.toFixed(1) + '× the markdown' : 'because debt soaks up everything') + '. ' +
        (net > 0 ? 'Debt magnifies every move in the business: shareholders absorb the whole hit.' : 'With net cash, the stock moves less than the business: cash cushions the fall.') : 'Move the sliders to stress the company.';
    }
    draw();
  }

  // ------------------------------------------------------------ 7. scorecard
  function Scorecard(box, D) {
    var st = { i: Math.max(0, D.cos.findIndex(function (c) { return c.s === (D.def || 'NVDA'); })) };
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'sc-list' });
    ui.appendChild(select('Stock', D.cos.map(function (c, i) { return [String(i), c.n + ' (' + c.s + ')']; }), function (v) { st.i = +v; draw(); }, String(st.i)));
    box.appendChild(ui); box.appendChild(out);
    function row(q, ans, verdict, why) {
      return el('div', { 'class': 'sc-row ' + verdict }, [el('span', { 'class': 'sc-dot' }), el('div', {}, [el('p', { 'class': 'sc-q', text: q }), el('p', { 'class': 'sc-a', text: ans }), why ? el('p', { 'class': 'small muted', text: why }) : null])]);
    }
    function draw() {
      var c = D.cos[st.i];
      out.innerHTML = '';
      out.appendChild(row('1. What is it, and how big?', c.n + (c.ind ? ', ' + c.ind : '') + '. Worth ' + c.cur + big(c.mcap) + '.', 'info', c.mcap < 3e8 ? 'A micro cap: small companies swing harder and cost more to trade.' : ''));
      if (c.pe) out.appendChild(row('2. What are you paying?', c.pe.toFixed(0) + '× last year\'s profit' + (c.fpe ? ', ' + c.fpe.toFixed(0) + '× next year\'s' : '') + '.', c.pe > 40 ? 'warn' : c.pe < 25 ? 'ok' : 'mid', c.pe > 40 ? 'A lot of future growth is priced in.' : c.pe < 15 ? 'Cheap on earnings, often because growth is low or the business is cyclical.' : 'In the normal range for a growing company.'));
      else out.appendChild(row('2. What are you paying?', 'No profit last year, so no P/E.', 'warn', 'Valued on hopes of future profit: expect bigger swings.'));
      if (c.rg != null || c.margin != null) out.appendChild(row('3. Is the business growing and profitable?', (c.rg != null ? 'Sales ' + pc(c.rg) + ' on a year earlier' : '') + (c.margin != null ? (c.rg != null ? '; ' : '') + 'keeps ' + Math.round(c.margin * 100) + '% of sales as profit' : '') + '.', (c.rg > 0.1 && c.margin > 0.1) ? 'ok' : (c.rg < 0 || c.margin < 0) ? 'warn' : 'mid', ''));
      out.appendChild(row('4. Can it survive a bad year?', c.neg ? 'Negative equity: it owes more than it owns.' : (c.de != null ? 'Debt is ' + c.de.toFixed(2) + '× equity' : 'No debt data') + (c.cover != null ? '; profit covers interest ' + Math.max(0, c.cover).toFixed(1) + '×' : '') + '.', c.neg || (c.de > 3) || (c.cover != null && c.cover < 2) ? 'warn' : (c.de > 1.5 || (c.cover != null && c.cover < 4)) ? 'mid' : 'ok', ''));
      out.appendChild(row('5. Which way is the trend?', (c.ma != null ? Math.abs(Math.round(c.ma * 100)) + '% ' + (c.ma >= 0 ? 'above' : 'below') + ' its 200-day average; ' : '') + c.k + ' of ' + c.n20 + ' plays in.', c.k / c.n20 >= 0.6 ? 'ok' : c.k / c.n20 <= 0.35 ? 'warn' : 'mid', c.k / c.n20 <= 0.35 ? 'Most rules are out: buying here is betting against the trend.' : ''));
      if (c.risk) out.appendChild(row('6. How hard would a crash hit it?', c.risk + ' crash exposure' + (c.why ? ': it ' + c.why : '') + '.', c.risk === 'Low' ? 'ok' : c.risk === 'Moderate' ? 'mid' : 'warn', ''));
      if (c.tgt) out.appendChild(row('7. What do analysts expect?', 'Average target ' + c.cur + c.tgt.toFixed(2) + ' (' + pc(c.tgt / c.p - 1) + '), from ' + c.na + ' analysts.', 'info', 'Targets lean optimistic and change with the price. Treat them as one opinion.'));
      out.appendChild(row('8. What is your plan?', 'Decide before you buy: how much, where you would sell if wrong, and what would make you sell if right.', 'info', 'The stock\'s page lists where each play would get out.'));
      out.appendChild(el('p', { 'class': 'small' }, [el('a', { href: D.href.replace('{u}', c.u), text: 'Open ' + c.s + '\'s full page →' })]));
    }
    draw();
  }

  // ------------------------------------------------------------ 8. drawdown math and position size
  function Drawdown(box) {
    var out = el('div', { 'class': 'lab-out' }), bar = el('div', { 'class': 'dd-bars' });
    var s = slider('Your portfolio falls', 5, 90, 5, 30, function (v) { return '−' + v + '%'; }, draw);
    box.appendChild(s); box.appendChild(bar); box.appendChild(out);
    function draw(v) {
      v = v == null ? s.get() : v;
      var need = 1 / (1 - v / 100) - 1, yrs = Math.log(1 + need) / Math.log(1.07);
      bar.innerHTML = '';
      var mx = Math.max(v, need * 100);
      bar.appendChild(el('div', { 'class': 'lab-bar' }, [el('span', { text: 'Fall' }), el('span', { 'class': 'trk' }, [el('i', { 'class': 'neg', style: 'width:' + (100 * v / mx).toFixed(1) + '%' })]), el('b', { text: '−' + v + '%' })]));
      bar.appendChild(el('div', { 'class': 'lab-bar' }, [el('span', { text: 'Gain to get back' }), el('span', { 'class': 'trk' }, [el('i', { style: 'width:' + (100 * need * 100 / mx).toFixed(1) + '%' })]), el('b', { text: '+' + Math.round(need * 100) + '%' })]));
      out.innerHTML = '';
      out.appendChild(stat('$10,000 becomes', '$' + Math.round(10000 * (1 - v / 100)).toLocaleString('en-US')));
      out.appendChild(stat('Gain needed to get back', '+' + Math.round(need * 100) + '%'));
      out.appendChild(stat('Years at 7% a year', yrs.toFixed(1), 'A typical long-run stock return'));
    }
    draw();
  }
  function Sizer(box) {
    var st = { acct: 50000, risk: 1, entry: 100, stop: 88 };
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'lab-out' }), txt = el('p', { 'class': 'lab-log' });
    ui.appendChild(slider('Account size', 5000, 500000, 5000, st.acct, function (v) { return '$' + v.toLocaleString('en-US'); }, function (v) { st.acct = v; draw(); }));
    ui.appendChild(slider('Most you\'ll lose on this idea', 0.25, 5, 0.25, st.risk, function (v) { return v + '% of the account'; }, function (v) { st.risk = v; draw(); }));
    ui.appendChild(slider('Buy price', 5, 500, 1, st.entry, function (v) { return '$' + v; }, function (v) { st.entry = v; draw(); }));
    ui.appendChild(slider('Exit if it closes below', 1, 499, 1, st.stop, function (v) { return '$' + v; }, function (v) { st.stop = v; draw(); }));
    box.appendChild(ui); box.appendChild(out); box.appendChild(txt);
    function draw() {
      out.innerHTML = '';
      if (st.stop >= st.entry) { txt.textContent = 'Set the exit below the buy price.'; return; }
      var riskD = st.acct * st.risk / 100, per = st.entry - st.stop, sh = Math.floor(riskD / per), pos = sh * st.entry;
      out.appendChild(stat('Shares', sh.toLocaleString('en-US')));
      out.appendChild(stat('Position', '$' + Math.round(pos).toLocaleString('en-US'), Math.round(100 * pos / st.acct) + '% of the account'));
      out.appendChild(stat('Loss if the exit hits', '−$' + Math.round(sh * per).toLocaleString('en-US'), st.risk + '% of the account'));
      txt.textContent = 'The exit is ' + Math.round(100 * per / st.entry) + '% below the buy price. ' + (pos > st.acct ? 'The position is bigger than the account: widen the exit less, or accept a smaller position.' : 'A tighter exit allows a bigger position for the same risk, but gets hit more often by normal wiggles.') + ' Real exits can gap past the level, so the loss can be larger.';
    }
    draw();
  }

  // ------------------------------------------------------------ 9. index toy
  function IndexToy(box, D) {
    var cos = D.cos.map(function (c) { return { s: c.s, cap: c.cap, mv: 0 }; });
    var ui = el('div', { 'class': 'lab-ui' }), out = el('div', { 'class': 'lab-out' }), txt = el('p', { 'class': 'lab-log' });
    cos.forEach(function (c) { ui.appendChild(slider(c.s + ' moves', -50, 50, 5, 0, function (v) { return (v > 0 ? '+' : '') + v + '%'; }, function (v) { c.mv = v; draw(); })); });
    box.appendChild(ui); box.appendChild(out); box.appendChild(txt);
    function draw() {
      var tot = cos.reduce(function (a, c) { return a + c.cap; }, 0);
      var cw = cos.reduce(function (a, c) { return a + c.cap / tot * c.mv / 100; }, 0), ew = cos.reduce(function (a, c) { return a + c.mv / 100 / cos.length; }, 0);
      out.innerHTML = '';
      cos.forEach(function (c) { out.appendChild(stat(c.s + ' weight', Math.round(100 * c.cap / tot) + '%')); });
      out.appendChild(stat('Cap-weighted index', pc(cw, 1), 'Like the S&P 500', cw >= 0 ? 'up' : 'down'));
      out.appendChild(stat('Equal-weighted index', pc(ew, 1), 'Every stock counts the same', ew >= 0 ? 'up' : 'down'));
      txt.textContent = 'In a cap-weighted index the biggest companies dominate. Move only the largest one and watch the index follow, even if the others go the other way.';
    }
    draw();
  }

  // ------------------------------------------------------------ 10. bucket builder
  function Buckets(box) {
    var st = { sav: 500000, spend: 40000, cash: 2, bonds: 5 };
    var ui = el('div', { 'class': 'lab-ui' }), bar = el('div', { 'class': 'wl-stack bk-stack' }), out = el('div', { 'class': 'lab-out' }), txt = el('p', { 'class': 'lab-log' });
    ui.appendChild(slider('Savings', 50000, 3000000, 25000, st.sav, function (v) { return '$' + v.toLocaleString('en-US'); }, function (v) { st.sav = v; draw(); }));
    ui.appendChild(slider('Spending taken from savings each year', 0, 200000, 5000, st.spend, function (v) { return '$' + v.toLocaleString('en-US'); }, function (v) { st.spend = v; draw(); }));
    ui.appendChild(slider('Years of spending in cash', 0, 4, 0.5, st.cash, function (v) { return v + ' yrs'; }, function (v) { st.cash = v; draw(); }));
    ui.appendChild(slider('Years after that in bonds', 0, 10, 1, st.bonds, function (v) { return v + ' yrs'; }, function (v) { st.bonds = v; draw(); }));
    box.appendChild(ui); box.appendChild(bar); box.appendChild(out); box.appendChild(txt);
    function draw() {
      var c = Math.min(st.sav, st.spend * st.cash), b = Math.min(st.sav - c, st.spend * st.bonds), s = st.sav - c - b;
      bar.innerHTML = '';
      [['calm', c], ['watch', b], ['in', s]].forEach(function (p) { if (p[1] > 0) bar.appendChild(el('i', { 'class': p[0], style: 'width:' + (100 * p[1] / st.sav).toFixed(1) + '%' })); });
      out.innerHTML = '';
      out.appendChild(stat('Bucket 1 · cash', '$' + Math.round(c).toLocaleString('en-US'), Math.round(100 * c / st.sav) + '%'));
      out.appendChild(stat('Bucket 2 · bonds', '$' + Math.round(b).toLocaleString('en-US'), Math.round(100 * b / st.sav) + '%'));
      out.appendChild(stat('Bucket 3 · stocks', '$' + Math.round(s).toLocaleString('en-US'), Math.round(100 * s / st.sav) + '%'));
      var cover = st.spend ? (c + b) / st.spend : Infinity;
      txt.textContent = st.spend ? 'Cash and bonds cover ' + cover.toFixed(1) + ' years of spending. The longest stretch the S&P 500 took to regain its old high since 2000 was about seven years (2000–2007 and again 2007–2013), so many planners aim to cover several years outside stocks.' : 'With no spending from savings, everything can stay long-term. Buckets matter once you draw on the money.';
    }
    draw();
  }

  // ------------------------------------------------------------ steps and checkpoints
  function Stepper(root) {
    var steps = [].slice.call(root.querySelectorAll(':scope > .step'));
    if (steps.length < 2) return;
    var key = 'quiplee.steps.' + (root.getAttribute('data-stepper') || location.pathname), seen = 1;
    try { seen = Math.max(1, +(localStorage.getItem(key) || 1)); } catch (e) {}
    var bar = el('div', { 'class': 'st-bar' }, [el('span', { 'class': 'st-label small muted' }), el('span', { 'class': 'st-trk' }, [el('i')]),
      el('button', { type: 'button', 'class': 'linkish small', text: 'Show all', on: { click: function () { show(steps.length); } } })]);
    root.insertBefore(bar, steps[0]);
    steps.forEach(function (s, i) {
      if (i < steps.length - 1) {
        var b = el('button', { type: 'button', 'class': 'btn st-next', text: 'Continue →' });
        b.addEventListener('click', function () { show(i + 2); steps[i + 1].scrollIntoView({ behavior: 'smooth', block: 'start' }); b.hidden = true; });
        s.appendChild(b);
      }
    });
    function show(n) {
      seen = Math.max(seen, n);
      steps.forEach(function (s, i) { s.hidden = i >= seen; var b = s.querySelector('.st-next'); if (b) b.hidden = i < seen - 1; });
      bar.querySelector('.st-label').textContent = 'Step ' + Math.min(seen, steps.length) + ' of ' + steps.length;
      bar.querySelector('.st-trk i').style.width = (100 * Math.min(seen, steps.length) / steps.length) + '%';
      try { localStorage.setItem(key, String(seen)); } catch (e) {}
      // charts in newly shown steps need a size
      window.dispatchEvent(new Event('resize'));
    }
    show(seen);
  }
  function Check(box) {
    var c = +box.getAttribute('data-c'), opts = box.querySelectorAll('.ck-opt'), why = box.querySelector('.ck-why');
    [].forEach.call(opts, function (b, i) {
      b.addEventListener('click', function () {
        if (box.classList.contains('done')) return;
        box.classList.add('done');
        [].forEach.call(opts, function (o, j) { o.disabled = true; if (j === c) o.classList.add('is-right'); else if (j === i) o.classList.add('is-wrong'); });
        why.hidden = false; why.className = 'ck-why quiz-why ' + (i === c ? 'ok' : 'no');
        why.textContent = (i === c ? 'Right. ' : 'Not quite. ') + why.textContent.replace(/^(Right\. |Not quite\. )/, '');
      });
    });
  }

  var LABS = { slice: Slice, orderbook: OrderBook, candle: CandleBuilder, swings: Swings, maplay: MaPlay, pe: PE, stress: Stress, scorecard: Scorecard,
    drawdown: Drawdown, sizer: Sizer, indextoy: IndexToy, buckets: Buckets };
  function init() {
    [].forEach.call(document.querySelectorAll('[data-stepper]'), Stepper);
    [].forEach.call(document.querySelectorAll('.check[data-c]'), Check);
    [].forEach.call(document.querySelectorAll('[data-lab]'), function (box) {
      var f = LABS[box.getAttribute('data-lab')];
      if (!f) return;
      var src = box.getAttribute('data-src'), D = src ? JSON.parse(document.getElementById(src).textContent) : null;
      try { f(box, D); } catch (e) { if (window.console) console.error(e); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
