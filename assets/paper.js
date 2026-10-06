/* paper.js: the paper-trading game (/paper/), its leaderboard (/paper/leaders/)
 * and shared portfolios (/paper/player/?u=). Talks to /api/paper/ (see
 * netlify/functions/paper.mjs); the tradable names come from data/paper.json. */
(function () {
  'use strict';
  var app = document.getElementById('pt-app');
  if (!app) return;
  var API = app.getAttribute('data-api');
  var MODE = app.getAttribute('data-mode');
  var STOCK = app.getAttribute('data-stock') || '';
  var PLAYER = app.getAttribute('data-player') || '';
  var U = null;            // data/paper.json
  var BY_SLUG = {}, BY_SHORT = {};
  var ME = null;
  var sel = null;          // the symbol in the trade ticket
  var side = 'buy';
  var lastQuote = null;

  // ---------------------------------------------------------------- helpers
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function $(q, root) { return (root || document).querySelector(q); }
  function $$(q, root) { return [].slice.call((root || document).querySelectorAll(q)); }
  function num(v, d) { return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function usd(v, d) { if (v == null || isNaN(v)) return '–'; var s = (v < 0 ? '−' : '') + 'US$' + num(Math.abs(v), d == null ? 2 : d); return s; }
  function px(v, cur) { if (v == null || isNaN(v)) return '–'; var p = cur === 'CAD' ? 'C$' : '$'; var d = Math.abs(v) < 1 ? 4 : 2; return p + num(v, d); }
  function pct(v, d) { if (v == null || isNaN(v)) return '–'; var s = num(Math.abs(v * 100), d == null ? 1 : d) + '%'; return (v > 0 ? '+' : v < 0 ? '−' : '') + s; }
  function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : ''; }
  function qty(q) { return Number.isInteger(q) ? num(q, 0) : String(+q.toFixed(6)); }
  function when(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return '';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' }) +
      ', ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }
  function day(iso) { var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  function stockHref(slug) { return slug ? STOCK.replace('{s}', slug) : null; }
  function playerHref(name) { return PLAYER + '?u=' + encodeURIComponent(name); }
  var HINT = {
    Shares: 'How many shares (or coins) are held.', Price: 'The latest price in the stock\'s own currency, delayed up to 15 minutes.',
    Value: 'What the holding is worth now, in US dollars.', Cost: 'What was paid for the shares still held, in US dollars.',
    Gain: 'Value minus cost, in US dollars and as a percentage.', Weight: 'The holding\'s share of the whole portfolio.',
    Return: 'Change in the portfolio\'s value since it started with US$100,000.', Cash: 'Share of the portfolio held in cash.',
    Total: 'The trade\'s value in US dollars (Toronto names converted at the USD/CAD rate at the time).',
    'Biggest holdings': 'The three largest positions by value.', Since: 'When the player started (or last started over).'
  };
  function th(label, c, extra) {
    return '<th' + (c ? ' class="' + c + '"' : '') + (HINT[label] ? ' data-hint="' + esc(HINT[label]) + '"' : '') + (extra || '') + '>' + label + '</th>';
  }
  function api(path, body) {
    var opt = body === undefined ? { credentials: 'same-origin', headers: { accept: 'application/json' } }
      : { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json', accept: 'application/json' }, body: JSON.stringify(body) };
    return fetch(API + path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { j._status = r.status; return j; });
    });
  }
  function loading(on) { var l = $('[data-pt-loading]', app); if (l) l.hidden = !on; }
  function msg(el, text, ok) { if (!el) return; el.textContent = text || ''; el.className = 'pt-msg' + (ok ? ' ok' : ''); }
  function loadUniverse() {
    var src = app.getAttribute('data-universe');
    if (!src) return Promise.resolve(null);
    return fetch(src).then(function (r) { return r.json(); }).then(function (j) {
      U = j;
      Object.keys(j.names).forEach(function (s) { BY_SLUG[j.names[s][2]] = s; BY_SHORT[j.names[s][0].toUpperCase()] = BY_SHORT[j.names[s][0].toUpperCase()] || s; });
      return j;
    }).catch(function () { return null; });
  }
  function meta(sym) { return U && U.names[sym]; }

  // ---------------------------------------------------------------- shared views
  /** Change since last night's recorded value (or since the start, for a portfolio begun today). */
  function today(d) {
    var t = new Date().toISOString().slice(0, 10), base = null;
    (d.history || []).forEach(function (x) { if (x[0] < t) base = x[1]; });
    if (base == null) base = d.start;
    return { v: d.total - base, p: base ? d.total / base - 1 : null };
  }

  function tiles(d, mine) {
    var bench = benchReturn(d), td = today(d);
    var t = [
      ['Portfolio value', usd(d.total, 0), '<span class="' + cls(d.ret) + '">' + pct(d.ret) + '</span> since ' + esc(day(d.created))],
      ['Against the S&amp;P 500', bench == null ? '–' : '<span class="' + cls(d.ret - bench) + '">' + pct(d.ret - bench) + '</span>',
        bench == null ? 'Compared from the first nightly close after the start.' : 'The S&amp;P 500 (SPY) is ' + pct(bench) + ' over the same nights.'],
      ['Cash', usd(d.cash, 0), d.total ? pct(d.cash / d.total, 0).replace('+', '') + ' of the portfolio' : ''],
      ['Today', '<span class="' + cls(Math.round(td.v)) + '">' + (Math.round(td.v) ? (td.v > 0 ? '+' : '') + usd(td.v, 0) : 'US$0') + '</span>',
        td.p != null ? pct(td.p, 2) + ' since the last close' : ''],
    ];
    return '<div class="grid grid-4 pt-tiles">' + t.map(function (x) {
      return '<div class="card tile"><span class="tile-label">' + x[0] + '</span><span class="tile-value">' + x[1] + '</span><span class="tile-note">' + x[2] + '</span></div>';
    }).join('') + '</div>';
  }

  /** The S&P 500's change since the portfolio's first nightly value (null until there are two). */
  function benchReturn(d) {
    var h = (d.history || []).filter(function (x) { return x[2] != null; });
    if (h.length < 2) return null;
    return h[h.length - 1][2] / h[0][2] - 1;
  }

  function holdings(d, mine) {
    if (!d.rows.length) return '<section><div class="sec-head"><h2 class="h2">Holdings</h2></div><p class="muted">' +
      (mine ? 'Nothing yet. Pick a stock above and place your first trade.' : 'All in cash right now.') + '</p></section>';
    var rows = d.rows.map(function (r) {
      var href = stockHref(r.slug);
      return '<tr><td class="stick">' + (href ? '<a class="sym" href="' + esc(href) + '">' + esc(r.short) + '</a>' : '<span class="sym">' + esc(r.short) + '</span>') +
        '<span class="sym-sub">' + esc(r.name) + '</span></td>' +
        '<td class="r mono" data-v="' + r.q + '">' + qty(r.q) + '</td>' +
        '<td class="r mono" data-v="' + (r.price || '') + '">' + px(r.price, r.cur) + (r.stale ? ' <span class="muted small" title="No live quote: last close">*</span>' : '') + '</td>' +
        '<td class="r mono" data-v="' + (r.value || '') + '">' + usd(r.value) + '</td>' +
        '<td class="r mono" data-v="' + r.cost + '">' + usd(r.cost) + '</td>' +
        '<td class="r ' + cls(r.gain) + '" data-v="' + (r.gain_pct || '') + '">' + (r.gain == null ? '–' : (r.gain > 0 ? '+' : '') + usd(r.gain) + ' <span class="small">' + pct(r.gain_pct) + '</span>') + '</td>' +
        '<td class="r" data-v="' + (r.weight || '') + '">' + (r.weight == null ? '–' : pct(r.weight, 0).replace('+', '')) + '</td>' +
        (mine ? '<td class="r"><button type="button" class="btn sm" data-pt-pick="' + esc(r.sym) + '">Trade</button></td>' : '') + '</tr>';
    }).join('');
    return '<section><div class="sec-head"><h2 class="h2">Holdings</h2><p>Valued at the latest price, delayed up to 15 minutes. Totals in US dollars.</p></div>' +
      '<div class="tbl-wrap"><table class="tbl pt-hold"><thead><tr>' + th('Stock', 'stick') + th('Shares', 'r') + th('Price', 'r') + th('Value', 'r') +
      th('Cost', 'r') + th('Gain', 'r') + th('Weight', 'r') + (mine ? '<th class="r" aria-label="Trade"></th>' : '') +
      '</tr></thead><tbody>' + rows + '</tbody></table></div></section>';
  }

  function trades(d, mine) {
    var list = d.trades || [];
    if (!list.length) return '';
    var rows = list.slice(0, 50).map(function (t) {
      var m = meta(t.sym);
      var href = m ? stockHref(m[2]) : null;
      var name = m ? m[0] : t.sym;
      return '<tr><td class="mono small">' + esc(when(t.t)) + '</td><td><span class="tag ' + (t.side === 'buy' ? 'pt-buy' : 'pt-sell') + '">' + (t.side === 'buy' ? 'Bought' : 'Sold') + '</span></td>' +
        '<td>' + (href ? '<a class="sym" href="' + esc(href) + '">' + esc(name) + '</a>' : '<span class="sym">' + esc(name) + '</span>') + '</td>' +
        '<td class="r mono">' + qty(t.q) + '</td><td class="r mono">' + px(t.px, t.cur) + (t.open === false ? ' <span class="muted small" title="Market closed: the last close">close</span>' : '') + '</td>' +
        '<td class="r mono">' + usd(t.usd) + '</td><td class="r ' + cls(t.pl) + '">' + (t.pl == null ? '' : (t.pl > 0 ? '+' : '') + usd(t.pl)) + '</td></tr>';
    }).join('');
    return '<section><div class="sec-head"><h2 class="h2">' + (mine ? 'Your trades' : 'Trades') + '</h2><p>The latest ' + Math.min(50, list.length) + ' of ' + (d.n_trades || list.length) + '. Gains on sales are against the average cost.</p></div>' +
      '<div class="tbl-wrap"><table class="tbl"><thead><tr>' + th('When') + th('Trade') + th('Stock') + th('Shares', 'r') + th('Price', 'r') + th('Total', 'r') + th('Gain', 'r') + '</tr></thead><tbody>' +
      rows + '</tbody></table></div></section>';
  }

  function chartCard() {
    return '<div class="card chart-card pt-chart"><div class="chart-top"><h3 class="h3">Portfolio value</h3><div class="legend-row">' +
      '<span class="key"><i style="background:var(--s1)"></i>Portfolio</span><span class="key"><i style="background:var(--s-bench)"></i>S&amp;P 500, same start</span></div></div>' +
      '<div class="chart" data-pt-chart></div><p class="chart-note" data-pt-chart-note></p></div>';
  }

  function drawChart(d) {
    var box = $('[data-pt-chart]', app), note = $('[data-pt-chart-note]', app);
    if (!box) return;
    var card = box.closest('.pt-chart');
    var h = (d.history || []).slice();
    var start = (d.created || '').slice(0, 10);
    if (start && (!h.length || h[0][0] > start)) h.unshift([start, d.start, null]);
    var today = new Date().toISOString().slice(0, 10);
    if (!h.length || h[h.length - 1][0] < today) h.push([today, d.total, null]);
    if (h.length < 2 || h[0][0] === h[h.length - 1][0] || !window.QChart) { card.hidden = true; return; }
    card.hidden = false;
    var t0 = new Date(h[0][0] + 'T00:00:00Z');
    var dd = h.map(function (x) { return Math.round((new Date(x[0] + 'T00:00:00Z') - t0) / 864e5); });
    var i0 = -1;
    h.forEach(function (x, i) { if (i0 < 0 && x[2] != null) i0 = i; });
    var bench = h.map(function (x, i) { return i0 >= 0 && i >= i0 && x[2] != null ? Math.round(h[i0][1] * x[2] / h[i0][2]) : null; });
    var series = [{ name: 'Portfolio', role: 's1', v: h.map(function (x) { return x[1]; }) }];
    if (bench.filter(function (v) { return v != null; }).length > 1) series.push({ name: 'S&P 500', role: 'bench', v: bench });
    var spec = { t0: h[0][0], d: dd, cur: '$', fmt: 'money', label: 'Portfolio value against the S&P 500', series: series };
    window.QChart.draw(box, spec);
    if (window.ResizeObserver && !box._ro) {
      var w = box.clientWidth;
      box._ro = new ResizeObserver(function () { if (Math.abs(box.clientWidth - w) > 2) { w = box.clientWidth; window.QChart.draw(box, spec); } });
      box._ro.observe(box);
    }
    if (note) note.textContent = series.length > 1 ? 'Each night\'s close, plus the latest value. The S&P 500 line starts at the portfolio\'s value on the first night it was recorded.'
      : 'Each night\'s close, plus the latest value. The S&P 500 comparison starts after the first nightly close.';
  }

  // ---------------------------------------------------------------- game
  function renderGame() {
    var d = ME;
    var box = $('[data-pt-in]', app);
    var link = location.origin + '/paper/player/?u=' + encodeURIComponent(d.name);
    box.innerHTML =
      '<div class="pt-bar"><span>Signed in as <b>' + esc(d.name) + '</b></span>' +
      '<span class="tag">' + (d.share && !d.hidden ? 'On the leaderboard' : 'Private') + '</span>' +
      '<button type="button" class="linkbtn" data-pt-act="logout">Sign out</button></div>' +
      tiles(d, true) +
      '<div class="pt-grid">' + ticket() + ideas() + '</div>' + chartCard() +
      (d.rows.length ? '' : importCard(true)) + holdings(d, true) + trades(d, true) + (d.rows.length ? importCard(false) : '') + settings(d, link);
    box.hidden = false;
    drawChart(d);
    wireTicket();
    wireSettings(link);
    wireImport();
    $$('[data-pt-pick]', box).forEach(function (b) {
      b.addEventListener('click', function () {
        choose(b.getAttribute('data-pt-pick'));
        var r = $('#pt-ticket').getBoundingClientRect();
        if (r.top < 0 || r.top > window.innerHeight * 0.6) $('#pt-ticket').scrollIntoView({ behavior: 'smooth', block: 'start' });
        $('#pt-qty').focus({ preventScroll: true });
      });
    });
  }

  /** Quick picks: the stocks most of the plays hold right now (from data/paper.json). */
  function ideas() {
    if (!U) return '<div></div>';
    var list = Object.keys(U.names).filter(function (s) { var m = U.names[s]; return m[5] === 'stock' && m[7]; })
      .sort(function (a, b) { var x = U.names[a], y = U.names[b]; return (y[6] / y[7]) - (x[6] / x[7]) || x[0].localeCompare(y[0]); }).slice(0, 10);
    return '<div class="card pt-ideas"><h2 class="h3">Where the plays agree</h2><p class="small muted">The stocks most of the ' + (U.names[list[0]] ? U.names[list[0]][7] : '') +
      ' plays hold right now. A place to start looking, not trading advice: meet with an advisor or independently review sources before making any decision.</p><div class="pt-idea-list">' +
      list.map(function (s) { var m = U.names[s]; return '<button type="button" class="pt-idea" data-pt-pick="' + esc(s) + '"><b>' + esc(m[0]) + '</b><span>' + esc(m[1]) + '</span><i>' + m[6] + '/' + m[7] + '</i></button>'; }).join('') +
      '</div><p class="small"><a href="' + esc(STOCK.replace('{s}/', '')) + '?sort=score">All the strongest setups</a></p></div>';
  }

  function ticket() {
    return '<div class="card pt-ticket" id="pt-ticket"><h2 class="h3">Trade</h2>' +
      '<div class="pt-search"><label for="pt-q" class="small muted">Stock, fund or coin</label>' +
      '<input id="pt-q" type="search" autocomplete="off" spellcheck="false" placeholder="Search: NVDA, Shopify, Royal Bank, bitcoin…" aria-controls="pt-results">' +
      '<div class="pt-results" id="pt-results" role="listbox" hidden></div></div>' +
      '<div class="pt-quote" data-pt-quote><p class="muted small">Pick a name to see its price and what the plays say.</p></div>' +
      '<form class="pt-order" data-pt-order hidden novalidate>' +
      '<div class="seg seg-sm" role="group" aria-label="Buy or sell"><button type="button" aria-pressed="true" data-side="buy">Buy</button><button type="button" aria-pressed="false" data-side="sell">Sell</button></div>' +
      '<label class="small muted" for="pt-qty">Shares</label><div class="lock-row"><input id="pt-qty" name="qty" inputmode="decimal" autocomplete="off" placeholder="0">' +
      '<button type="button" class="btn sm" data-pt-max>Max</button></div>' +
      '<p class="small muted" data-pt-est></p>' +
      '<button type="submit" class="btn primary" data-pt-submit>Place order</button>' +
      '<p class="pt-msg" role="alert" data-pt-ordermsg></p></form></div>';
  }

  function matches(q) {
    if (!U) return [];
    q = q.trim().toLowerCase();
    if (!q) return [];
    var out = [];
    Object.keys(U.names).forEach(function (s) {
      var m = U.names[s], short = m[0].toLowerCase(), name = m[1].toLowerCase();
      var score = short === q || s.toLowerCase() === q ? 0 : short.indexOf(q) === 0 ? 1 : name.indexOf(q) === 0 ? 2 : name.indexOf(q) >= 0 || short.indexOf(q) >= 0 ? 3 : -1;
      if (score >= 0) out.push([score, m[0].length, s]);
    });
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out.slice(0, 8).map(function (x) { return x[2]; });
  }

  function wireTicket() {
    var q = $('#pt-q'), res = $('#pt-results');
    var active = -1;
    function show() {
      var list = matches(q.value);
      active = -1;
      res.innerHTML = list.map(function (s) {
        var m = meta(s);
        return '<button type="button" role="option" data-sym="' + esc(s) + '"><b>' + esc(m[0]) + '</b><span>' + esc(m[1]) + '</span><i>' + (m[3] === 'CAD' ? 'TSX' : esc(m[8] || '')) + '</i></button>';
      }).join('') || (q.value.trim() ? '<p class="muted small">Be The Puck doesn\'t cover that one. <a href="' + esc(STOCK.replace('{s}/', '')) + '">See every name</a>.</p>' : '');
      res.hidden = !q.value.trim();
    }
    q.addEventListener('input', show);
    q.addEventListener('focus', function () { if (q.value.trim()) show(); });
    q.addEventListener('keydown', function (ev) {
      var opts = $$('button', res);
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        active = Math.max(0, Math.min(opts.length - 1, active + (ev.key === 'ArrowDown' ? 1 : -1)));
        opts.forEach(function (o, i) { o.classList.toggle('on', i === active); });
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        var o = opts[active >= 0 ? active : 0];
        if (o) choose(o.getAttribute('data-sym'));
      } else if (ev.key === 'Escape') { res.hidden = true; }
    });
    res.addEventListener('click', function (ev) { var b = ev.target.closest('button[data-sym]'); if (b) choose(b.getAttribute('data-sym')); });
    document.addEventListener('click', function (ev) { if (!ev.target.closest('.pt-search')) res.hidden = true; });

    var form = $('[data-pt-order]');
    $$('[data-side]', form).forEach(function (b) {
      b.addEventListener('click', function () {
        side = b.getAttribute('data-side');
        $$('[data-side]', form).forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        estimate();
      });
    });
    $('#pt-qty').addEventListener('input', estimate);
    $('[data-pt-max]').addEventListener('click', function () {
      if (!sel || !lastQuote) return;
      var m = meta(sel), crypto = m[5] === 'crypto';
      var held = ME.rows.filter(function (r) { return r.sym === sel; })[0];
      var n;
      if (side === 'sell') n = held ? held.q : 0;
      else {
        var each = lastQuote.price * lastQuote.usd_per;
        n = each > 0 ? ME.cash / each : 0;
        n = crypto ? Math.floor(n * 1e6) / 1e6 : Math.floor(n);
      }
      $('#pt-qty').value = n > 0 ? String(n) : '0';
      estimate();
    });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var n = Number(String($('#pt-qty').value).replace(/,/g, ''));
      var out = $('[data-pt-ordermsg]');
      if (!sel) return;
      if (!(n > 0)) { msg(out, 'Enter how many shares.'); return; }
      var btn = $('[data-pt-submit]');
      btn.disabled = true;
      msg(out, side === 'buy' ? 'Buying…' : 'Selling…', true);
      api('trade', { sym: sel, side: side, qty: n }).then(function (j) {
        btn.disabled = false;
        if (!j.ok) { msg(out, j.error || 'The order didn\'t go through.'); if (j._status === 401) start(); return; }
        var t = j.trade, m = meta(t.sym);
        var done = (t.side === 'buy' ? 'Bought ' : 'Sold ') + qty(t.q) + ' ' + m[0] + ' at ' + px(t.px, t.cur) + ' (' + usd(t.usd) + ')' + (t.open === false ? ', the last close' : '') + '.';
        refresh().then(function () { choose(t.sym, true); msg($('[data-pt-ordermsg]'), done, true); });
      }).catch(function () { btn.disabled = false; msg(out, 'Couldn\'t reach the server. Check your connection and try again.'); });
    });
  }

  function estimate() {
    var el = $('[data-pt-est]'), btn = $('[data-pt-submit]');
    if (!el || !sel) return;
    var m = meta(sel), n = Number(String($('#pt-qty').value).replace(/,/g, ''));
    var held = ME.rows.filter(function (r) { return r.sym === sel; })[0];
    var label = (side === 'buy' ? 'Buy ' : 'Sell ') + (n > 0 ? qty(n) + ' ' : '') + m[0];
    btn.textContent = label;
    if (!lastQuote || !(n > 0)) {
      el.textContent = side === 'sell' ? (held ? 'You hold ' + qty(held.q) + '.' : 'You don\'t hold any ' + m[0] + '.') : 'Cash available: ' + usd(ME.cash) + '.';
      return;
    }
    var total = n * lastQuote.price * lastQuote.usd_per;
    var fx = lastQuote.cur === 'CAD' ? ' (' + px(n * lastQuote.price, 'CAD') + ' at ' + num(1 / lastQuote.usd_per, 4) + ' C$ per US$)' : '';
    el.innerHTML = 'About <b>' + usd(total) + '</b>' + esc(fx) + '. ' +
      (side === 'buy' ? (total > ME.cash ? '<span class="down">More than your cash (' + usd(ME.cash) + ').</span>' : 'Cash after: ' + usd(ME.cash - total) + '.')
        : (held ? 'You hold ' + qty(held.q) + '.' : '<span class="down">You don\'t hold any.</span>'));
  }

  function choose(sym, keepMsg) {
    var m = meta(sym);
    if (!m) return;
    sel = sym;
    lastQuote = null;
    var q = $('#pt-q'), res = $('#pt-results'), box = $('[data-pt-quote]'), form = $('[data-pt-order]');
    if (!box) return;
    q.value = m[0] + ' · ' + m[1];
    res.hidden = true;
    form.hidden = false;
    if (!keepMsg) { msg($('[data-pt-ordermsg]'), ''); $('#pt-qty').value = ''; }
    var href = stockHref(m[2]);
    var plays = (m[9] != null ? '<span class="light-pill ' + (m[9] ? 'start' : 'stop') + '"><i></i>' + (m[9] ? 'Start' : 'Stop') + '</span> ' : '') +
      (m[7] ? '<b>' + m[6] + ' of ' + m[7] + '</b> plays hold it now' : '');
    box.innerHTML = '<div class="pt-q-head"><span class="sym">' + esc(m[0]) + '</span><span class="muted">' + esc(m[1]) + '</span></div>' +
      '<div class="pt-q-px"><b data-pt-px>' + px(m[4], m[3]) + '</b> <span class="muted small" data-pt-when>last close · loading the latest price…</span></div>' +
      '<p class="small">' + plays + (href ? (plays ? ' · ' : '') + '<a href="' + esc(href) + '">See the full analysis</a>' : '') + '</p>';
    api('quote?sym=' + encodeURIComponent(sym)).then(function (j) {
      if (sel !== sym) return;
      var w = $('[data-pt-when]');
      if (j.price) {
        lastQuote = j;
        $('[data-pt-px]').textContent = px(j.price, j.cur);
        var chg = j.prev ? j.price / j.prev - 1 : null;
        w.innerHTML = (chg != null ? '<span class="' + cls(chg) + '">' + pct(chg, 2) + '</span> · ' : '') +
          (j.open ? 'market open, delayed up to 15 min' : 'market closed: orders fill at this close') + (j.cur === 'CAD' ? ' · in C$' : '');
      } else {
        w.textContent = 'No live price right now. Try again shortly.';
      }
      estimate();
    }).catch(function () { var w = $('[data-pt-when]'); if (w) w.textContent = 'No live price right now.'; });
    estimate();
  }

  // ---------------------------------------------------------------- copy in real holdings
  function wlItems() {
    try {
      var v = JSON.parse(localStorage.getItem('quiplee.watch.v1') || 'null');
      return (v && v.items || []).filter(function (x) { return meta(x.sym); });
    } catch (e) { return []; }
  }
  function importCard(first) {
    var wl = wlItems();
    var inner = '<p class="small muted">Paper-trade the names you really own. Type them with share counts, like <span class="mono">NVDA 20, TD.TO 50, BTC 0.1</span>, ' +
      'or use your watchlist (it reads a broker CSV: upload one on the <a href="' + esc(STOCK.replace('stocks/{s}/', 'watchlist/')) + '">watchlist</a>).</p>' +
      '<textarea data-pt-imp rows="3" spellcheck="false" placeholder="NVDA 20, TD.TO 50, BTC 0.1"></textarea>' +
      (wl.length ? '<p><button type="button" class="btn sm" data-pt-impwl>Use my watchlist (' + wl.length + ' name' + (wl.length === 1 ? '' : 's') + ')</button></p>' : '') +
      '<div class="al-chips" data-pt-impprev></div>' +
      '<div class="pt-impmode" data-pt-impmode hidden><label class="pt-check"><input type="radio" name="impmode" value="count" checked> Match my share counts (scaled down if they cost more than my cash)</label>' +
      '<label class="pt-check"><input type="radio" name="impmode" value="split"> Split my cash evenly instead</label></div>' +
      '<button type="button" class="btn primary" data-pt-impgo disabled>Buy them</button><p class="pt-msg" role="alert" data-pt-impmsg></p>';
    return first ? '<section class="card pt-import"><h2 class="h3">Start from your real stocks</h2>' + inner + '</section>'
      : '<details class="card pt-import"><summary class="h3">Copy in more of your real stocks</summary>' + inner + '</details>';
  }
  function parseImport(text) {
    var out = [], bad = [];
    String(text || '').split(/[\n,;]+/).forEach(function (piece) {
      var w = piece.trim().split(/\s+/);
      if (!w[0]) return;
      var u = w[0].toUpperCase(), q = w[1] != null ? parseFloat(String(w[1]).replace(/[,$]/g, '')) : null;
      var sym = meta(u) ? u : BY_SHORT[u] || BY_SHORT[u.replace(/\.TO$/, '')] || (meta(u + '.TO') ? u + '.TO' : null) || BY_SLUG[w[0].toLowerCase()];
      if (!sym) { bad.push(w[0]); return; }
      if (!out.some(function (x) { return x.sym === sym; })) out.push({ sym: sym, qty: q > 0 ? q : null });
    });
    return { items: out, bad: bad };
  }
  function wireImport() {
    var ta = $('[data-pt-imp]');
    if (!ta) return;
    var prev = $('[data-pt-impprev]'), mode = $('[data-pt-impmode]'), go = $('[data-pt-impgo]'), out = $('[data-pt-impmsg]');
    function show() {
      var p = parseImport(ta.value), counts = p.items.length && p.items.every(function (x) { return x.qty; });
      prev.innerHTML = p.items.map(function (x) { var m = meta(x.sym); return '<span class="al-chip"><b>' + esc(m[0]) + '</b><span>' + (x.qty ? qty(x.qty) + ' sh' : esc(m[1])) + '</span></span>'; }).join('') +
        (p.bad.length ? '<p class="small down">Not covered: ' + esc(p.bad.join(', ')) + '</p>' : '');
      mode.hidden = !counts;
      go.disabled = !p.items.length;
      go.textContent = p.items.length ? 'Buy ' + p.items.length + ' name' + (p.items.length === 1 ? '' : 's') : 'Buy them';
    }
    ta.addEventListener('input', show);
    var wb = $('[data-pt-impwl]');
    if (wb) wb.addEventListener('click', function () {
      ta.value = wlItems().map(function (x) { return meta(x.sym)[0] + (x.qty ? ' ' + x.qty : ''); }).join(', ');
      show();
    });
    go.addEventListener('click', function () {
      var p = parseImport(ta.value);
      if (!p.items.length) return;
      var split = !mode.hidden && (mode.querySelector('input[value=split]') || {}).checked;
      var items = p.items.map(function (x) { return { sym: x.sym, qty: split ? null : x.qty }; });
      go.disabled = true;
      msg(out, 'Buying at the latest prices…', true);
      api('import', { items: items }).then(function (j) {
        go.disabled = false;
        if (!j.ok) { msg(out, j.error || "That didn't go through."); return; }
        var spent = j.bought.reduce(function (a, t) { return a + t.usd; }, 0);
        var note = 'Bought ' + j.bought.length + ' name' + (j.bought.length === 1 ? '' : 's') + ' for ' + usd(spent) + '.' +
          (j.scaled ? ' Share counts were scaled to ' + Math.round(j.scaled * 100) + '% to fit your cash.' : '') +
          (j.skipped && j.skipped.length ? ' Skipped: ' + j.skipped.map(function (x) { return x.sym + ' (' + x.why + ')'; }).join(', ') + '.' : '');
        refresh().then(function () { var o = $('[data-pt-impmsg]'); if (o) msg(o, note, true); var t = $('#pt-ticket'); if (t) t.scrollIntoView({ block: 'start' }); msg($('[data-pt-ordermsg]'), note, true); });
      }).catch(function () { go.disabled = false; msg(out, "Couldn't reach the server. Try again."); });
    });
    show();
  }

  function settings(d, link) {
    return '<section class="card pt-settings"><h2 class="h3">Your account</h2>' +
      '<label class="pt-check"><input type="checkbox" data-pt-share' + (d.share ? ' checked' : '') + '> Show my portfolio on the leaderboard and at a public link</label>' +
      (d.hidden ? '<p class="small down">This portfolio has been taken off the leaderboard by Be The Puck.</p>' : '') +
      '<div class="pt-share" data-pt-sharebox' + (d.share ? '' : ' hidden') + '><input readonly value="' + esc(link) + '" aria-label="Your public link"><button type="button" class="btn sm" data-pt-copy>Copy link</button>' +
      (navigator.share ? '<button type="button" class="btn sm" data-pt-native>Share</button>' : '') + '</div>' +
      '<p class="pt-msg" data-pt-sharemsg role="status"></p>' +
      '<details class="pt-more"><summary>Change password</summary><form data-pt-form="password" class="pt-form" novalidate>' +
      '<label>Current password<input name="old" type="password" autocomplete="current-password" required></label>' +
      '<label>New password<input name="password" type="password" autocomplete="new-password" minlength="8" required></label>' +
      '<button class="btn sm" type="submit">Change password</button><p class="pt-msg" data-pt-msg role="alert"></p></form></details>' +
      '<details class="pt-more"><summary>Start over with US$100,000</summary><form data-pt-form="reset" class="pt-form" novalidate>' +
      '<p class="small muted">Clears your holdings, trades and chart and gives you US$100,000 again; your return restarts from today. Once a day at most.</p>' +
      '<label>Type RESET to confirm<input name="confirm" autocomplete="off" required></label>' +
      '<button class="btn sm" type="submit"' + (d.reset_ok ? '' : ' disabled') + '>Start over</button><p class="pt-msg" data-pt-msg role="alert"></p></form></details>' +
      '<details class="pt-more"><summary>Delete my account</summary><form data-pt-form="delete" class="pt-form" novalidate>' +
      '<p class="small muted">Removes your account, portfolio and history for good.</p>' +
      '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>' +
      '<button class="btn sm" type="submit">Delete my account</button><p class="pt-msg" data-pt-msg role="alert"></p></form></details>' +
      '</section>';
  }

  function wireSettings(link) {
    var cb = $('[data-pt-share]'), box = $('[data-pt-sharebox]'), out = $('[data-pt-sharemsg]');
    cb.addEventListener('change', function () {
      cb.disabled = true;
      api('share', { on: cb.checked }).then(function (j) {
        cb.disabled = false;
        if (!j.ok) { cb.checked = !cb.checked; msg(out, j.error || 'Couldn\'t save that.'); return; }
        ME.share = j.share;
        box.hidden = !j.share;
        $('.pt-bar .tag').textContent = j.share && !ME.hidden ? 'On the leaderboard' : 'Private';
        msg(out, j.share ? 'Shared. You\'ll appear on the leaderboard after tonight\'s close.' : 'Your portfolio is private.', true);
      });
    });
    var copy = $('[data-pt-copy]');
    if (copy) copy.addEventListener('click', function () {
      (navigator.clipboard ? navigator.clipboard.writeText(link) : Promise.reject()).then(function () { msg(out, 'Link copied.', true); }, function () {
        var i = $('.pt-share input'); i.select(); msg(out, 'Select the link and copy it.', true);
      });
    });
    var nat = $('[data-pt-native]');
    if (nat) nat.addEventListener('click', function () {
      navigator.share({ title: ME.name + ' on Be The Puck', text: 'My paper-trading portfolio: ' + pct(ME.ret) + ' since I started.', url: link }).catch(function () {});
    });
    wireForms($('[data-pt-in]'));
    $('[data-pt-act="logout"]').addEventListener('click', function () { api('logout', {}).then(start); });
  }

  // ---------------------------------------------------------------- forms
  function wireForms(root) {
    $$('form[data-pt-form]', root).forEach(function (f) {
      if (f._wired) return;
      f._wired = true;
      f.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var kind = f.getAttribute('data-pt-form'), out = $('[data-pt-msg]', f), btn = $('button[type=submit]', f);
        var body = {};
        $$('input', f).forEach(function (i) { body[i.name] = i.type === 'checkbox' ? i.checked : i.value; });
        if ((kind === 'signup' || kind === 'login') && (!body.name || !body.password)) { msg(out, 'Enter a username and password.'); return; }
        if (kind === 'signup' && !/^[A-Za-z0-9_]{3,20}$/.test(body.name)) { msg(out, 'Usernames are 3 to 20 letters, numbers or underscores.'); return; }
        if ((kind === 'signup' || kind === 'password') && String(body.password || '').length < 8) { msg(out, 'Passwords need at least 8 characters.'); return; }
        btn.disabled = true;
        msg(out, kind === 'signup' ? 'Setting up your account…' : 'One moment…', true);
        api(kind, body).then(function (j) {
          btn.disabled = false;
          if (!j.ok) { msg(out, j.error || 'That didn\'t work. Try again.'); return; }
          if (kind === 'password') { msg(out, 'Password changed.', true); f.reset(); return; }
          if (kind === 'reset') { msg(out, 'Done. You have US$100,000 again.', true); refresh(); return; }
          if (kind === 'delete') { ME = null; start(); return; }
          start();
        }).catch(function () { btn.disabled = false; msg(out, 'Couldn\'t reach the server. Check your connection and try again.'); });
      });
    });
  }

  // ---------------------------------------------------------------- boot
  function refresh() {
    return api('me').then(function (j) {
      if (j._status === 401 || j.signed_in === false) { ME = null; return showOut(); }
      if (j.error) { loading(false); $('[data-pt-loading]', app).hidden = false; $('[data-pt-loading]', app).textContent = j.error; return; }
      ME = j;
      $('[data-pt-out]', app).hidden = true;
      renderGame();
    });
  }

  function showOut() {
    $('[data-pt-in]', app).hidden = true;
    $('[data-pt-out]', app).hidden = false;
    wireForms(app);
  }

  function start() {
    loading(true);
    return refresh().then(function () {
      loading(false);
      var want = new URLSearchParams(location.search).get('t');
      if (want && ME) {
        var sym = BY_SLUG[want.toLowerCase()] || (meta(want.toUpperCase()) ? want.toUpperCase() : null);
        if (sym) { choose(sym); $('#pt-ticket').scrollIntoView({ block: 'start' }); }
      }
    }).catch(function () {
      loading(true);
      $('[data-pt-loading]', app).textContent = 'Couldn\'t reach the game right now. Refresh to try again.';
    });
  }

  function board() {
    api('board').then(function (j) {
      loading(false);
      var box = $('[data-pt-board]', app);
      var rows = (j.rows || []).slice();
      var hb = document.getElementById('pt-house'), house = [];
      try { house = hb ? JSON.parse(hb.textContent) : []; } catch (e) { house = []; }
      var all = rows.concat(house).sort(function (a, b) { return b.ret - a.ret; });
      var lead = rows.length
        ? 'Valued at the close on ' + esc(day(j.asof + 'T12:00:00Z')) + '. ' + (j.players ? j.players + ' players in all; ' + rows.length + ' shared.' : '')
        : '<b>No players have shared yet.</b> Until they do, the house benchmarks below set the bar: US$100,000 in one fund since the game opened. <a href="' + esc(PLAYER.replace(/player\/(index\.html)?$/, '')) + '">Start playing</a> and share yours to take them on.';
      var rank = 0;
      box.innerHTML = '<p class="muted small pt-board-lead">' + lead + '</p>' +
        '<div class="tbl-wrap"><table class="tbl"><thead><tr>' + th('#', 'r') + th('Player') + th('Return', 'r', ' data-sort-first="desc"') + th('Value', 'r') + th('Biggest holdings') + th('Cash', 'r') + th('Since') + '</tr></thead><tbody>' +
        all.map(function (r) {
          if (r.house) {
            return '<tr class="pt-house"><td class="r mono muted">–</td><td><span class="tag">House</span> <b>' + esc(r.name) + '</b></td>' +
              '<td class="r ' + cls(r.ret) + '" data-v="' + r.ret + '">' + pct(r.ret) + '</td><td class="r mono" data-v="' + r.value + '">' + usd(r.value, 0) + '</td>' +
              '<td class="small muted">All in one fund</td><td class="r" data-v="0">0%</td><td class="small muted">' + esc(day(r.since + 'T12:00:00Z')) + '</td></tr>';
          }
          rank++;
          return '<tr><td class="r mono">' + rank + '</td><td><a class="sym" href="' + esc(playerHref(r.name)) + '">' + esc(r.name) + '</a></td>' +
            '<td class="r ' + cls(r.ret) + '" data-v="' + r.ret + '">' + pct(r.ret) + '</td><td class="r mono" data-v="' + r.value + '">' + usd(r.value, 0) + '</td>' +
            '<td class="small">' + (r.top || []).map(esc).join(', ') + (r.n > 3 ? ' <span class="muted">+' + (r.n - 3) + '</span>' : '') + '</td>' +
            '<td class="r" data-v="' + r.cash + '">' + pct(r.cash, 0).replace('+', '') + '</td><td class="small muted">' + esc(day(r.since)) + '</td></tr>';
        }).join('') + '</tbody></table></div>';
      }).catch(function () { loading(true); $('[data-pt-loading]', app).textContent = 'Couldn\'t load the leaderboard. Refresh to try again.'; });
  }

  function player() {
    var u = new URLSearchParams(location.search).get('u') || '';
    if (!/^[A-Za-z0-9_]{3,20}$/.test(u)) { $('[data-pt-loading]', app).textContent = 'No player named here. Pick one from the leaderboard.'; return; }
    api('player?u=' + encodeURIComponent(u)).then(function (d) {
      loading(false);
      var box = $('[data-pt-in]', app);
      if (!d.name) { loading(true); $('[data-pt-loading]', app).textContent = d.error || 'This portfolio is private.'; return; }
      document.title = d.name + '’s paper portfolio · Be The Puck';
      var c = $('[data-pt-crumb]'); if (c) c.textContent = d.name;
      box.innerHTML = '<section class="pair-head"><p class="eyebrow">Paper trading</p><h1 class="h1">' + esc(d.name) + '’s portfolio</h1>' +
        '<p class="lede">Started with US$100,000 of play money on ' + esc(day(d.created)) + '. ' + (d.n_trades || 0) + ' trades so far.</p></section>' +
        tiles(d, false) + chartCard() + holdings(d, false) + trades(d, false);
      box.hidden = false;
      drawChart(d);
      }).catch(function () { $('[data-pt-loading]', app).textContent = 'Couldn\'t load this portfolio. Refresh to try again.'; });
  }

  if (MODE === 'board') board();
  else if (MODE === 'player') loadUniverse().then(player);
  else loadUniverse().then(start);
})();
