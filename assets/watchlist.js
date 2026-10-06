/* watchlist.js — the /watchlist/ app. Reads data/watch.json (every covered ticker's
 * calls), keeps the reader's list in localStorage (or a shared ?t= link), parses
 * pasted text and broker CSV exports in the browser, and posts tickers Be The Puck
 * doesn't cover yet to /api/watch so the nightly run can add them. */
(function () {
  'use strict';
  var root = document.getElementById('wl');
  if (!root || !window.QW) return;
  var Q = window.QW, el = Q.el;
  var BASE = root.getAttribute('data-base') || '../';
  var API = root.getAttribute('data-api');
  var STOCK = root.getAttribute('data-stock'), PAIR = root.getAttribute('data-pair');
  var MODE_KEY = 'quiplee.watch.plays.v1';
  var EXAMPLE = ['NVDA', 'AAPL', 'SHOP.TO', 'RY.TO', 'XIU.TO', 'HTZ', 'MU', 'BTC-USD'];
  var VALID = /^\^?[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,2})?(?:[.-][A-Z0-9]{1,4})?$/;
  var D = null, queue = {}, rejected = {}, posted = {}, notes = {};
  var HINTS = {
    'Stock': 'The company, fund or index. Click a name for its chart and every play\u2019s call.',
    'Price': 'The latest closing price.',
    'Day': 'Change from the previous day\u2019s close.',
    '1 year': 'Price change over the last 12 months.',
    'vs 200-day': 'How far the price sits above (+) or below (\u2212) its average close of the last 200 trading days. Above usually means a long uptrend.',
    'Plays in': 'How many of the plays you chose to count hold it right now.',
    'Target': 'How far analysts\u2019 average 12-month price target sits above (+) or below (\u2212) today\u2019s price. Needs 3 or more analysts.',
    'Strip': 'One square per play, in family order: green means the play holds it, red means it is out.',
    'Light': 'Start or Stop, summing up every play: Start when 60% or more hold it, Stop once that falls to 40% or less.',
    'Crash': 'The storm test: how hard a market crash would likely hit it, from market swings, past crashes, debt and recent run-up.',
    'Weight': 'Its share of your list by value, from the quantities or values in your file.'
  };
  var st = { items: [], example: false, shared: false, mode: 'all', pick: [] };

  function $(id) { return document.getElementById(id); }
  function msg(t, kind) { var m = $('wl-msg'); m.textContent = t; m.className = 'small ' + (kind || 'muted'); }
  function getJSON(url) { return fetch(url, { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  var mem = null, syncTimer = null;   // the member's saved list, once signed in
  function save() {
    if (st.shared || st.example) return;
    Q.watchSet({ items: st.items });
    if (mem && mem.synced) { clearTimeout(syncTimer); syncTimer = setTimeout(function () { putList({}); }, 800); }
  }
  function loadMode() {
    try { var m = JSON.parse(localStorage.getItem(MODE_KEY) || 'null'); if (m) { st.mode = m.mode === 'pick' ? 'pick' : 'all'; st.pick = m.pick || []; } } catch (e) {}
  }
  function saveMode() { try { localStorage.setItem(MODE_KEY, JSON.stringify({ mode: st.mode, pick: st.pick })); } catch (e) {} }

  // ---------------------------------------------------------------- matching what people type
  var EXCH = { TSX: '.TO', TSE: '.TO', XTSE: '.TO', 'TORONTO STOCK EXCHANGE': '.TO', TOR: '.TO', TSXV: '.V', 'TSX-V': '.V', XTSX: '.V', 'TSX VENTURE': '.V', CVE: '.V',
    CSE: '.CN', XCNQ: '.CN', CNSX: '.CN', NEO: '.NE', NEOE: '.NE', XNEO: '.NE', 'CBOE CANADA': '.NE', 'CBOE CA': '.NE', AEQUITAS: '.NE' };
  function resolve(raw, exch, name, type) {
    var s = String(raw || '').trim().toUpperCase().replace(/^\$/, '').replace(/\s+/g, ' ');
    if (!s) return null;
    var note = '';
    var m = s.match(/^(TSX|TSE|TSXV|CVE|NEO|CSE|NASDAQ|NYSE|NYSEARCA|ARCA|AMEX|BATS)\s*:\s*(.+)$/);
    if (m) { exch = m[1]; s = m[2]; }
    if (D.t[s]) return { sym: s };
    if (D.alias[s]) { var tg = D.alias[s]; return { sym: tg, note: tg !== s && tg.split(/[.-]/)[0] === s ? 'Matched to ' + tg : '' }; }
    if (type && /crypto/i.test(type) && /^[A-Z0-9]{2,6}$/.test(s)) return { sym: s + '-USD' };
    var ex = String(exch || '').trim().toUpperCase(), suf = EXCH[ex];
    var cdr = /CDR|DEPOSITARY RECEIPT/i.test((name || '') + ' ' + (type || ''));
    if (suf === '.NE' && cdr) {
      var base = s.replace(/\.NE$/, '');
      return { sym: base, note: 'CDR: showing the U.S. shares it tracks' };
    }
    if (suf && s.indexOf('.') < 0) s = s.replace(/\.([A-Z])$/, '-$1') + suf;
    else if (suf && /^[A-Z]+\.[A-Z]$/.test(s)) s = s.replace('.', '-') + suf;
    else if (!suf && /^[A-Z]+\.[A-Z]$/.test(s) && !/\.(V|TO|NE|CN)$/.test(s)) s = s.replace('.', '-');
    if (D.t[s]) return { sym: s, note: note };
    if (D.alias[s]) return { sym: D.alias[s] };
    return VALID.test(s) ? { sym: s, note: note } : { bad: raw };
  }

  // CSV with quotes
  function csvRows(text) {
    var rows = [], row = [], cell = '', q = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
        else cell += c;
      } else if (c === '"') q = true;
      else if (c === ',' || c === ';' || c === '\t') { row.push(cell); cell = ''; }
      else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
      else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (x) { return String(x).trim(); }); });
  }
  function num(v) { if (v == null) return null; var x = parseFloat(String(v).replace(/[$,\s]|CAD|USD/gi, '')); return isNaN(x) ? null : x; }
  function parseCSV(text) {
    var rows = csvRows(text), hi = -1, col = {};
    for (var i = 0; i < Math.min(rows.length, 15); i++) {
      var r = rows[i].map(function (x) { return String(x).trim().toLowerCase(); });
      var si = r.findIndex(function (x) { return /^(symbol|ticker|ticker symbol|security symbol)$/.test(x); });
      if (si >= 0) {
        hi = i; col.sym = si;
        r.forEach(function (x, j) {
          if (col.ex == null && /^(exchange|mic|market|listing exchange)$/.test(x)) col.ex = j;
          if (col.qty == null && /^(quantity|qty|shares|units|position)$/.test(x)) col.qty = j;
          if (col.mv == null && /^market value( \(cad\))?$|^value$|^current value$/.test(x)) col.mv = j;
          if (col.name == null && /^(name|security name|description|security)$/.test(x)) col.name = j;
          if (col.type == null && /^(security type|type|asset type|asset class)$/.test(x)) col.type = j;
        });
        break;
      }
    }
    if (hi < 0) return null;
    var out = [];
    rows.slice(hi + 1).forEach(function (r) {
      var raw = (r[col.sym] || '').trim();
      var type = col.type != null ? r[col.type] : '';
      if (!raw || /option|cash|bond|gic/i.test(type || '')) return;
      out.push({ raw: raw, ex: col.ex != null ? r[col.ex] : '', name: col.name != null ? r[col.name] : '', type: type,
        qty: col.qty != null ? num(r[col.qty]) : null, mv: col.mv != null ? num(r[col.mv]) : null });
    });
    return out;
  }
  function parseText(text) {
    if (/\n/.test(text) && /symbol|ticker/i.test(text.split('\n')[0])) { var c = parseCSV(text); if (c) return c; }
    var out = [];
    text.split(/[\n,;|]+/).forEach(function (piece) {
      piece = piece.trim();
      if (!piece) return;
      var whole = piece.toUpperCase();
      if (D.t[whole] || D.alias[whole] || /^[A-Z]{2,6}\s*:\s*\S+$/i.test(piece)) { out.push({ raw: piece }); return; }
      piece.split(/\s+/).forEach(function (w) { if (w) out.push({ raw: w }); });
    });
    return out;
  }
  function addEntries(entries, source) {
    if (st.example) { st.items = []; st.example = false; }
    if (st.shared) { st.shared = false; history.replaceState(null, '', location.pathname); }
    var added = 0, bad = [], fresh = [];
    var have = {}; st.items.forEach(function (x) { have[x.sym] = x; });
    entries.forEach(function (en) {
      var r = resolve(en.raw, en.ex, en.name, en.type);
      if (!r) return;
      if (r.bad) { bad.push(r.bad); return; }
      if (r.note) notes[r.sym] = r.note;
      var cur = have[r.sym];
      if (cur) {
        if (en.qty != null) cur.qty = (cur.qty || 0) + en.qty;
        if (en.mv != null) cur.mv = (cur.mv || 0) + en.mv;
        return;
      }
      var it = { sym: r.sym };
      if (en.qty != null) it.qty = en.qty;
      if (en.mv != null) it.mv = en.mv;
      st.items.push(it); have[r.sym] = it; added++;
      if (!D.t[r.sym]) fresh.push(r.sym);
    });
    save();
    var parts = [];
    parts.push(added ? 'Added ' + added + (added === 1 ? ' name' : ' names') + (source ? ' from ' + source : '') + '.' : 'Nothing new to add.');
    if (bad.length) parts.push("Couldn't read: " + bad.slice(0, 6).join(', ') + (bad.length > 6 ? '…' : '') + '.');
    msg(parts.join(' '), bad.length ? 'warn-text' : 'muted');
    if (fresh.length) sendQueue(fresh);
    render();
  }

  // ---------------------------------------------------------------- the queue
  function sendQueue(syms) {
    syms = syms.filter(function (s) { return !rejected[s] && !posted[s]; });
    if (!syms.length) return;
    var chunks = [];
    for (var i = 0; i < syms.length; i += 25) chunks.push(syms.slice(i, i + 25));
    chunks.forEach(function (c) {
      c.forEach(function (s) { posted[s] = 'sending'; });
      fetch(API, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ tickers: c }) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); })
        .then(function (j) {
          (j.queued || []).forEach(function (s) { posted[s] = 'queued'; queue[s] = queue[s] || { first: new Date().toISOString(), count: 1 }; });
          (j.rejected || []).forEach(function (s) { posted[s] = 'bad'; });
          (j.unavailable || []).forEach(function (s) { posted[s] = 'excluded'; });
          render();
        })
        .catch(function () { c.forEach(function (s) { posted[s] = 'error'; }); render(); });
    });
    render();
  }
  function nextRun() {
    // the nightly job runs every day at 21:45 UTC; pages publish about half an hour later
    var d = new Date(), t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 21, 45));
    if (d >= t) t.setUTCDate(t.getUTCDate() + 1);
    return t;
  }
  function whenText() {
    var t = nextRun(), now = new Date(), same = t.toDateString() === now.toDateString();
    var tm = t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    return (same ? 'tonight after ' : t.toLocaleDateString([], { weekday: 'long' }) + ' after ') + tm;
  }

  // ---------------------------------------------------------------- reading the list
  function selected() {
    if (st.mode === 'all') return D.plays.map(function (p, i) { return i; });
    if (st.mode === 'pick' && st.pick.length) return D.plays.map(function (p, i) { return st.pick.indexOf(p.s) >= 0 ? i : -1; }).filter(function (i) { return i >= 0; });
    return D.plays.map(function (p, i) { return p.c ? i : -1; }).filter(function (i) { return i >= 0; });
  }
  function count(t, sel) {
    var k = 0, n = 0;
    sel.forEach(function (i) { var c = t.c[i]; if (c === '1') { k++; n++; } else if (c === '0') n++; });
    return [k, n];
  }
  // half the plays in, half analysts' upside scored from -20% (0) to +50% (1); names without a target count as 0% upside
  function upPts(u) { return (Math.min(Math.max(u, -0.2), 0.5) + 0.2) / 0.7; }
  function score(t, sel) { var kn = count(t, sel); return 0.5 * (kn[1] ? kn[0] / kn[1] : 0) + 0.5 * upPts(t.up == null ? 0 : t.up); }
  function status(sym) {
    if (D.t[sym]) return 'covered';
    if (posted[sym] === 'excluded') return 'excluded';
    if (rejected[sym] || posted[sym] === 'bad') return 'rejected';
    if (posted[sym] === 'error') return 'error';
    if (queue[sym] || posted[sym] === 'queued') return 'queued';
    if (posted[sym] === 'sending') return 'sending';
    return 'new';
  }
  function fill(k, n) { return el('span', { 'class': 'fillbar', 'aria-hidden': 'true' }, [el('i', { style: 'width:' + (n ? Math.round(100 * k / n) : 0) + '%' })]); }
  function cls(v) { return v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''; }
  var LVL = { Low: 'calm', Moderate: 'watch', High: 'warning', 'Very high': 'warning' };

  function weights() {
    var cov = st.items.filter(function (x) { return D.t[x.sym]; });
    var vals = cov.map(function (x) { return x.mv != null ? x.mv : (x.qty != null && D.t[x.sym].p ? x.qty * D.t[x.sym].p : null); });
    var useVal = vals.length && vals.every(function (v) { return v != null && v > 0; });
    var tot = 0, w = {};
    cov.forEach(function (x, i) { var v = useVal ? vals[i] : 1; w[x.sym] = v; tot += v; });
    Object.keys(w).forEach(function (s) { w[s] = tot ? w[s] / tot : 0; });
    return { w: w, byValue: useVal };
  }

  function render() {
    var sel = selected();
    var list = $('wl-list'), sum = $('wl-sum');
    list.innerHTML = ''; sum.innerHTML = '';
    if (!st.items.length) {
      list.appendChild(el('div', { 'class': 'card wl-empty' }, [el('p', { 'class': 'h3', text: 'Your list is empty.' }),
        el('p', { 'class': 'muted small', text: 'Add a few tickers above, or ' }, [el('button', { type: 'button', 'class': 'linkish', text: 'load an example list', on: { click: function () { loadExample(); } } }), '.'])]));
      return;
    }
    var W = weights();
    // summary
    var cov = st.items.filter(function (x) { return D.t[x.sym]; });
    var qd = st.items.filter(function (x) { var s = status(x.sym); return s === 'queued' || s === 'sending' || s === 'new'; });
    var bands = { in: 0, split: 0, out: 0 }, risk = { calm: 0, watch: 0, warning: 0, none: 0 }, up = 0, avg = 0;
    cov.forEach(function (x) {
      var t = D.t[x.sym], kn = count(t, sel), r = kn[1] ? kn[0] / kn[1] : 0, w = W.w[x.sym];
      avg += r * w;
      bands[r >= 0.67 ? 'in' : r <= 0.33 ? 'out' : 'split'] += w;
      risk[t.r ? LVL[t.r[1]] : 'none'] += w;
      if (t.ma != null && t.ma >= 0) up += w;
    });
    function stack(parts) {
      var bar = el('div', { 'class': 'wl-stack' });
      parts.forEach(function (p) { if (p[1] > 0.0005) bar.appendChild(el('i', { 'class': p[0], style: 'width:' + (p[1] * 100).toFixed(1) + '%', title: p[2] + ': ' + Math.round(p[1] * 100) + '%' })); });
      return bar;
    }
    function key(parts) {
      return el('div', { 'class': 'wl-key' }, parts.filter(function (p) { return p[1] > 0.0005; }).map(function (p) {
        return el('span', {}, [el('i', { 'class': p[0] }), p[2] + ' ' + Math.round(p[1] * 100) + '%']);
      }));
    }
    var by = W.byValue ? 'of your money' : 'of your list';
    var pb = [['in', bands.in, 'Most plays in'], ['split', bands.split, 'Split'], ['out', bands.out, 'Most plays out']];
    var rb = [['calm', risk.calm, 'Low'], ['watch', risk.watch, 'Moderate'], ['warning', risk.warning, 'High'], ['none', risk.none, 'n/a']];
    sum.appendChild(el('div', { 'class': 'card tile' }, [el('span', { 'class': 'tile-label', text: 'Names' }),
      el('span', { 'class': 'tile-value', text: String(st.items.length) }),
      el('span', { 'class': 'tile-note', text: cov.length + ' covered' + (qd.length ? ' · ' + qd.length + ' in the queue' : '') + (st.example ? ' · example list' : '') })]));
    sum.appendChild(el('div', { 'class': 'card tile' }, [el('span', { 'class': 'tile-label', text: 'Plays in, ' + (W.byValue ? 'weighted by value' : 'on average') }),
      el('span', { 'class': 'tile-value', text: Math.round(avg * 100) + '%' }), fill(avg, 1),
      el('span', { 'class': 'tile-note', text: sel.length + ' plays counted' })]));
    sum.appendChild(el('div', { 'class': 'card tile wide' }, [el('span', { 'class': 'tile-label', text: 'What the plays say, share ' + by }), stack(pb), key(pb)]));
    sum.appendChild(el('div', { 'class': 'card tile wide' }, [el('span', { 'class': 'tile-label', text: 'Crash exposure, share ' + by }), stack(rb), key(rb)]));
    var tb2 = [['in', up, 'Above'], ['out', Math.max(0, 1 - up - risk.none * 0), 'Below']];
    var covW = cov.reduce(function (a, x) { return a + (D.t[x.sym].ma != null ? W.w[x.sym] : 0); }, 0);
    tb2[1][1] = Math.max(0, covW - up);
    sum.appendChild(el('div', { 'class': 'card tile wide' }, [el('span', { 'class': 'tile-label', text: 'Long trend: price against the 200-day average, share ' + by }), stack(tb2), key(tb2)]));

    // rows
    var showW = W.byValue;
    var head = ['Stock', 'Light', 'Price', 'Day', '1 year', 'vs 200-day', 'Plays in', 'Target', 'Strip', 'Crash', showW ? 'Weight' : null, ''].filter(function (x) { return x !== null; });
    var tbl = el('table', { 'class': 'tbl wl-tbl' });
    var thead = el('thead', {}, [el('tr', {}, head.map(function (hd, i) {
      var at = { 'class': i >= 2 && i <= 5 || hd === 'Weight' || hd === 'Target' ? 'r' : '', text: hd };
      if (HINTS[hd]) at['data-hint'] = HINTS[hd];
      return el('th', at);
    }))]);
    var tb = el('tbody');
    var rows = st.items.slice().sort(function (a, b) {
      var A = D.t[a.sym], B = D.t[b.sym];
      if (!!A !== !!B) return A ? -1 : 1;
      if (!A) return a.sym < b.sym ? -1 : 1;
      if (showW) return (W.w[b.sym] || 0) - (W.w[a.sym] || 0);
      return score(B, sel) - score(A, sel);
    });
    rows.forEach(function (it) {
      var t = D.t[it.sym], s = status(it.sym);
      var rm = el('button', { type: 'button', 'class': 'wl-x', 'aria-label': 'Remove ' + it.sym, text: '×', on: { click: function () { st.items = st.items.filter(function (x) { return x.sym !== it.sym; }); if (st.example) st.example = false; save(); render(); } } });
      if (!t) {
        var txt = { queued: 'In the queue: analysis ' + whenText() + ', ready the next day.', sending: 'Sending to the queue…', new: 'Not covered yet.',
          rejected: 'No price history found for this symbol. Check the ticker (Canadian names need .TO or .V).', error: "Couldn't reach the queue. ",
          excluded: "Be The Puck doesn't cover this name." }[s];
        var cell = el('td', { colspan: String(head.length - 2), 'class': 'wl-status ' + s, text: txt });
        if (s === 'error' || s === 'new') cell.appendChild(el('button', { type: 'button', 'class': 'linkish', text: 'Send it again', on: { click: function () { delete posted[it.sym]; sendQueue([it.sym]); } } }));
        tb.appendChild(el('tr', { 'class': 'wl-pending' }, [el('td', {}, [el('b', { 'class': 'sym', text: it.sym }), el('span', { 'class': 'sym-sub', text: s === 'rejected' ? 'Not found' : s === 'excluded' ? 'Not covered' : 'Analysis pending' })]), cell, el('td', {}, [rm])]));
        return;
      }
      var kn = count(t, sel);
      var strip = el('span', { 'class': 'wl-strip', 'aria-label': kn[0] + ' of ' + kn[1] + ' in' });
      var lastF = null;
      sel.forEach(function (i) {
        var p = D.plays[i], c = t.c[i];
        if (lastF !== null && p.f !== lastF) strip.appendChild(el('b'));
        lastF = p.f;
        var a = el(p.c || !(t.req || t.co) ? 'a' : 'span', { 'class': c === '1' ? 'in' : c === '0' ? 'out' : 'na', title: p.n + ': ' + (c === '1' ? 'IN' : c === '0' ? 'OUT' : 'no call') + (t.m && t.m[p.s] ? ' · ' + t.m[p.s] : '') });
        if (a.tagName === 'A') a.href = PAIR.replace('{u}', t.u).replace('{s}', p.s);
        strip.appendChild(a);
      });
      var href = STOCK.replace('{u}', t.u);
      var sub = t.n + (notes[it.sym] ? ' · ' + notes[it.sym] : '') + (t.req ? ' · added by a reader' : '');
      var cells = [
        el('td', {}, [el('a', { 'class': 'sym', href: href, text: t.s }), el('span', { 'class': 'sym-sub', text: sub })]),
        el('td', {}, [t.L == null ? el('span', { 'class': 'muted', text: '–' }) : el('a', { 'class': 'light-pill ' + (t.L ? 'start' : 'stop'), href: href, title: 'Start when 60% or more of the plays hold it; Stop once that falls to 40% or less.' }, [el('i'), t.L ? 'Start' : 'Stop'])]),
        el('td', { 'class': 'r mono', text: Q.money(t.p, t.cur) }),
        el('td', { 'class': 'r ' + cls(t.d1), text: Q.pct(t.d1) }),
        el('td', { 'class': 'r ' + cls(t.y1), text: Q.pct(t.y1, 0) }),
        el('td', { 'class': 'r ' + cls(t.ma), text: Q.pct(t.ma, 0) }),
        el('td', {}, [el('span', { 'class': 'consensus' }, [fill(kn[0], kn[1]), kn[0] + ' of ' + kn[1]])]),
        el('td', { 'class': 'r ' + (t.up == null ? 'muted' : t.up > 0.02 ? 'up' : t.up < 0 ? 'down' : ''), title: t.up == null ? 'Fewer than 3 analysts, or no target' : 'Average 12-month target from ' + t.na + ' analysts', text: t.up == null ? '–' : Q.pct(t.up, 0) }),
        el('td', {}, [strip]),
        el('td', {}, [t.r ? el('span', { 'class': 'lvl lvl-' + LVL[t.r[1]], text: t.r[1] }) : el('span', { 'class': 'muted', text: '–' })])
      ];
      if (showW) cells.push(el('td', { 'class': 'r', text: Math.round((W.w[it.sym] || 0) * 1000) / 10 + '%' }));
      cells.push(el('td', {}, [rm]));
      tb.appendChild(el('tr', {}, cells));
    });
    tbl.appendChild(thead); tbl.appendChild(tb);
    list.appendChild(el('div', { 'class': 'tbl-wrap' }, [tbl]));
    if (st.example) list.appendChild(el('p', { 'class': 'small muted', text: 'This is an example list. Add your own tickers above and it will be replaced.' }));
  }

  // ---------------------------------------------------------------- play picker
  function picker() {
    var box = $('wl-picker');
    box.innerHTML = '';
    if (!st.pick.length) st.pick = D.plays.filter(function (p) { return p.c; }).map(function (p) { return p.s; });
    D.fams.forEach(function (f) {
      var g = el('fieldset', { 'class': 'wl-fam' }, [el('legend', { text: f[1] })]);
      D.plays.forEach(function (p) {
        if (p.f !== f[0]) return;
        var cb = el('input', { type: 'checkbox', value: p.s });
        cb.checked = st.pick.indexOf(p.s) >= 0;
        cb.addEventListener('change', function () {
          st.pick = st.pick.filter(function (x) { return x !== p.s; });
          if (cb.checked) st.pick.push(p.s);
          saveMode(); render();
        });
        g.appendChild(el('label', {}, [cb, p.n]));
      });
      box.appendChild(g);
    });
  }
  function setMode(m) {
    st.mode = m; saveMode();
    [].forEach.call($('wl-mode').children, function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-v') === m)); });
    $('wl-picker').hidden = m !== 'pick';
    if (m === 'pick') picker();
    render();
  }

  // ---------------------------------------------------------------- readers' additions
  function readers() {
    var box = $('wl-readers');
    var req = Object.keys(D.t).filter(function (s) { return D.t[s].req; });
    var waiting = Object.keys(queue).filter(function (s) { return !D.t[s] && !rejected[s]; });
    if (!req.length && !waiting.length) return;
    box.innerHTML = '';
    box.appendChild(el('div', { 'class': 'sec-head' }, [el('h2', { 'class': 'h2', text: 'Added by readers' }),
      el('p', { text: 'Every name a reader adds is analysed for everyone. Newest first.' })]));
    var chips = el('div', { 'class': 'chips' });
    req.sort(function (a, b) { return String(D.t[b].req) < String(D.t[a].req) ? -1 : 1; }).slice(0, 60).forEach(function (s) {
      chips.appendChild(el('a', { href: STOCK.replace('{u}', D.t[s].u), text: D.t[s].s }));
    });
    if (req.length) box.appendChild(chips);
    if (waiting.length) box.appendChild(el('p', { 'class': 'small muted', text: 'In the queue for ' + whenText() + ': ' + waiting.slice(0, 40).join(', ') + (waiting.length > 40 ? '…' : '') }));
  }

  // ---------------------------------------------------------------- members: the list the alert email checks
  function alMsg(t) { var m = $('wl-al-msg'); if (m) m.textContent = t; }
  function alState() {
    if (!mem) return;
    var n = (mem.tickers || []).length;
    if (!mem.email) alMsg('This sign-in has no email on file, so no alerts can be sent. Subscribers get them at their PayPal email.');
    else if (!n) alMsg('Save your list once; after that it stays in step as you add or remove stocks.');
    else alMsg('Saved: ' + n + ' stock' + (n === 1 ? '' : 's') + '. ' + (mem.alerts ? 'Alerts are on: Be The Puck checks after each close and emails only when something changed.' : 'Alerts are off.'));
  }
  function putList(extra) {
    var body = { tickers: st.items.map(function (x) { return x.sym; }) };
    Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return fetch('/api/member/list', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); })
      .then(function (j) { mem.tickers = j.tickers; mem.alerts = j.alerts; mem.email = j.email; mem.synced = true; alState(); })
      .catch(function (e) { alMsg("Couldn't save: " + e.message); });
  }
  function memberInit() {
    var box = $('wl-alerts');
    if (!box || location.protocol === 'file:') return;
    fetch('/api/member/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.member) return null;
        box.querySelector('.wl-al-guest').hidden = true;
        box.querySelector('.wl-al-mem').hidden = false;
        return fetch('/api/member/list', { credentials: 'same-origin', cache: 'no-store' }).then(function (r) { return r.json(); });
      })
      .then(function (L) {
        if (!L) return;
        mem = { tickers: L.tickers || [], alerts: L.alerts !== false, email: !!L.email, synced: (L.tickers || []).length > 0 };
        $('wl-al-on').checked = mem.alerts;
        // a list saved on another device fills an empty (or example) list here
        if (mem.tickers.length && !st.shared && (st.example || !st.items.length)) {
          st.items = mem.tickers.map(function (s) { return { sym: s }; });
          st.example = false; Q.watchSet({ items: st.items }); render();
          msg('Loaded your saved list.');
        }
        alState();
      })
      .catch(function () {});
    $('wl-al-save').addEventListener('click', function () {
      if (!mem) return;
      if (st.example || !st.items.length) { alMsg('Add your own stocks first.'); return; }
      alMsg('Saving…'); putList({ alerts: $('wl-al-on').checked });
    });
    $('wl-al-on').addEventListener('change', function () { if (mem && mem.synced) putList({ alerts: this.checked }); });
  }

  function loadExample() { st.items = EXAMPLE.filter(function (s) { return D.t[s]; }).map(function (s) { return { sym: s }; }); st.example = true; render(); }

  function init() {
    loadMode();
    var params = new URLSearchParams(location.search), shared = params.get('t');
    if (shared) {
      st.shared = true;
      st.items = shared.split(',').map(function (s) { return s.trim().toUpperCase(); }).filter(function (s) { return VALID.test(s); }).slice(0, 100).map(function (s) { return { sym: s }; });
      msg('Viewing a shared list. Adding a stock saves it as your own list in this browser.');
    } else {
      st.items = Q.watchGet().items || [];
      if (!st.items.length) loadExample();
    }
    [].forEach.call($('wl-mode').children, function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-v')); }); });
    $('wl-go').addEventListener('click', function () {
      var v = $('wl-in').value; if (!v.trim()) { msg('Type or paste at least one ticker.', 'warn-text'); return; }
      addEntries(parseText(v)); $('wl-in').value = '';
    });
    $('wl-in').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) $('wl-go').click(); });
    $('wl-file').addEventListener('change', function () {
      var f = this.files && this.files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var rows = parseCSV(String(rd.result));
        if (!rows) { msg("Couldn't find a Symbol or Ticker column in that file. Try pasting the symbols instead.", 'warn-text'); return; }
        addEntries(rows.map(function (r) { return r; }), f.name);
      };
      rd.readAsText(f);
      this.value = '';
    });
    $('wl-share').addEventListener('click', function () {
      if (!st.items.length) { msg('Add some stocks first.', 'warn-text'); return; }
      var url = location.origin + location.pathname + '?t=' + st.items.map(function (x) { return x.sym; }).join(',');
      var done = function () { msg('Link copied. It shares the tickers only, never quantities or values.'); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () { msg(url); }); else msg(url);
    });
    $('wl-clear').addEventListener('click', function () { st.items = []; st.example = false; st.shared = false; Q.watchSet({ items: [] }); history.replaceState(null, '', location.pathname); render(); msg('List cleared.'); });
    setMode(st.mode);
    memberInit();
    var add = params.get('add');
    if (add && !shared) { addEntries(parseText(add)); history.replaceState(null, '', location.pathname); }
    // queue state + names that failed checks
    getJSON(BASE + 'data/universe/rejected.json').then(function (j) { (j.tickers || []).forEach(function (r) { rejected[r.sym] = r.reason || true; }); render(); }).catch(function () {});
    if (API) getJSON(API).then(function (j) { (j.requests || []).forEach(function (r) { queue[r.sym] = r; }); render(); readers(); }).catch(function () { readers(); });
    // anything in the list not covered and not yet known to the queue: send it
    setTimeout(function () {
      var fresh = st.items.filter(function (x) { return !D.t[x.sym] && !queue[x.sym] && !rejected[x.sym]; }).map(function (x) { return x.sym; });
      if (fresh.length && !st.example) sendQueue(fresh);
    }, 1500);
  }

  getJSON(BASE + 'data/watch.json').then(function (j) { D = j; init(); })
    .catch(function (err) { if (window.console) console.error(err); msg("Couldn't load Be The Puck's data. Refresh the page to try again.", "warn-text"); });
})();
