/* rules.js: the members' /rules/ page. A member picks which plays count toward the
 * Start/Stop light, sets the two thresholds and four portfolio limits, and sees their
 * list under that rule. Reads data/watch.json (today's calls), data/hist/<slug>.json
 * (two years of weekly calls for each stock on the list, so the light is walked
 * forward exactly like the site's own: tools/qstrat/rules.py custom_light), the
 * watchlist in this browser, and the member's saved list and rule (/api/member/list). */
(function () {
  'use strict';
  var app = document.getElementById('ru-app');
  if (!app || !window.QW) return;
  var Q = window.QW, el = Q.el;
  var KEY = 'quiplee.rules.v1';
  var EXAMPLE = ['NVDA', 'AAPL', 'MSFT', 'SHOP.TO', 'RY.TO', 'XIU.TO', 'MU', 'BTC-USD'];
  var FX = parseFloat(app.getAttribute('data-fx')) || 1.38;
  var STOCK = app.getAttribute('data-stock'), HIST = app.getAttribute('data-hist');
  var SITE_ON = parseFloat(app.getAttribute('data-on')) || 0.6, SITE_OFF = parseFloat(app.getAttribute('data-off')) || 0.4;
  var PRESETS = JSON.parse(document.getElementById('ru-presets').textContent);
  var LIM_DEF = { pos: 0.10, group: 0.30, start: 0.50, crash: 0.25 };
  var HIGH = { 'High': 1, 'Very high': 1 };
  var D = null, H = {}, items = [], src = '', mem = null, dirty = false;
  var R = def();

  function def() { return { preset: 'all', plays: [], on: SITE_ON, off: SITE_OFF, lim: JSON.parse(JSON.stringify(LIM_DEF)) }; }
  function $(s) { return app.querySelector(s); }
  function $$(s) { return [].slice.call(app.querySelectorAll(s)); }
  function msg(t, ok) { var m = $('[data-ru-msg]'); m.textContent = t || ''; m.className = 'small ' + (ok === false ? 'down' : 'muted'); }
  function pc(v, d) { return v == null || isNaN(v) ? '–' : (100 * v).toFixed(d || 0) + '%'; }
  function getJSON(u, opt) { return fetch(u, opt || {}).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fdate(s) { return s ? Q.fdate(new Date(s + 'T00:00:00Z')) : ''; }

  // ---------------------------------------------------------------- the rule
  function preset(k) { for (var i = 0; i < PRESETS.length; i++) if (PRESETS[i].k === k) return PRESETS[i]; return null; }
  /** Indices into D.plays of the plays that count. */
  function chosen() {
    var p = R.preset !== 'custom' && preset(R.preset);
    var slugs = p ? p.p : R.plays;
    var want = {}; slugs.forEach(function (s) { want[s] = 1; });
    return D.plays.map(function (p, i) { return want[p.s] ? i : -1; }).filter(function (i) { return i >= 0; });
  }
  function clean(r) {
    var out = def();
    if (!r || typeof r !== 'object') return out;
    if (r.preset === 'custom' || preset(r.preset)) out.preset = r.preset;
    out.plays = Array.isArray(r.plays) ? r.plays.slice(0, 200) : [];
    if (out.preset === 'custom' && !out.plays.length) out.preset = 'all';
    var on = Number(r.on), off = Number(r.off);
    if (on >= 0.5 && on <= 0.95) out.on = Math.round(on * 100) / 100;
    if (off >= 0.05 && off < out.on) out.off = Math.round(off * 100) / 100; else out.off = Math.min(SITE_OFF, out.on - 0.05);
    if (r.lim && typeof r.lim === 'object') Object.keys(LIM_DEF).forEach(function (k) { var v = r.lim[k]; out.lim[k] = v === null ? null : (Number(v) >= 0 && Number(v) <= 1 ? Number(v) : LIM_DEF[k]); });
    return out;
  }
  function isSite(r) { return r.preset === 'all' && Math.abs(r.on - SITE_ON) < 1e-9 && Math.abs(r.off - SITE_OFF) < 1e-9; }

  /** The latched light for one stock under the rule: Site.light with chosen plays and thresholds. */
  function lightFor(sym, sel) {
    var h = H[sym], t = D.t[sym];
    if (!h || !t || !sel.length) return null;
    var on = R.on, off = R.off, mid = (on + off) / 2, minN = Math.min(5, sel.length);
    var state = null, since = null, W = h.w.length;
    function step(k, n, when) {
      if (n < minN || n === 0) return;
      var sh = k / n, nw = state;
      if (state === null) nw = sh >= mid ? 'start' : 'stop';
      else if (state === 'stop' && sh >= on) nw = 'start';
      else if (state === 'start' && sh <= off) nw = 'stop';
      if (nw !== state) { state = nw; since = when; }
    }
    function count(get) {
      var k = 0, n = 0;
      for (var i = 0; i < sel.length; i++) { var c = get(sel[i]); if (c === '1') { k++; n++; } else if (c === '0') n++; }
      return [k, n];
    }
    for (var j = 0; j < W; j++) { var kn = count(function (i) { return (h.h[i] || '').charAt(j); }); step(kn[0], kn[1], h.w[j]); }
    var now = count(function (i) { return (h.c || t.c).charAt(i); });
    step(now[0], now[1], h.a);
    return { state: state, since: since, first: since === h.w[0] && W >= 100, k: now[0], n: now[1], share: now[1] ? now[0] / now[1] : null };
  }

  // ---------------------------------------------------------------- the list
  function weights(list) {
    var vals = list.map(function (x) {
      var t = D.t[x.sym];
      if (x.mv != null && x.mv > 0) return x.mv;
      if (x.qty != null && x.qty > 0 && t.p) return x.qty * t.p * (t.cur === 'C$' ? 1 : FX);
      return null;
    });
    var byValue = vals.length > 0 && vals.every(function (v) { return v != null; });
    var w = {}, tot = 0;
    list.forEach(function (x, i) { var v = byValue ? vals[i] : 1; w[x.sym] = (w[x.sym] || 0) + v; tot += v; });
    Object.keys(w).forEach(function (s) { w[s] = tot ? w[s] / tot : 0; });
    return { w: w, byValue: byValue };
  }
  function loadItems() {
    var local = (Q.watchGet().items || []).filter(function (x) { return D.t[x.sym]; });
    if (local.length) { items = local; src = 'local'; return; }
    if (mem && mem.tickers && mem.tickers.length) {
      items = mem.tickers.filter(function (s) { return D.t[s]; }).map(function (s) { return { sym: s }; });
      if (items.length) { src = 'saved'; return; }
    }
    items = EXAMPLE.filter(function (s) { return D.t[s]; }).map(function (s) { return { sym: s }; });
    src = 'example';
  }
  function fetchHist() {
    var need = items.map(function (x) { return x.sym; }).filter(function (s) { return !H[s]; });
    var i = 0;
    function next() {
      if (i >= need.length) return Promise.resolve();
      var batch = need.slice(i, i + 10); i += 10;
      return Promise.all(batch.map(function (s) {
        return getJSON(HIST.replace('{u}', D.t[s].u)).then(function (j) { H[s] = j; }).catch(function () { H[s] = null; });
      })).then(next);
    }
    return next();
  }

  // ---------------------------------------------------------------- controls
  function paintControls() {
    var sel = chosen();
    $$('[data-ru-presets] button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-v') === R.preset)); });
    var p = preset(R.preset);
    $('[data-ru-pdesc]').textContent = p ? p.d : 'Your own choice of plays.';
    $('[data-ru-pcount]').textContent = '(' + sel.length + ' of ' + D.plays.length + ' chosen)';
    var on = {}; sel.forEach(function (i) { on[D.plays[i].s] = 1; });
    $$('[data-ru-picker] input[type=checkbox]').forEach(function (cb) { cb.checked = !!on[cb.value]; });
    $('[data-ru-on]').value = Math.round(R.on * 100);
    $('[data-ru-off]').value = Math.round(R.off * 100);
    Object.keys(LIM_DEF).forEach(function (k) {
      var cb = $('[data-ru-lim="' + k + '"]'), inp = $('[data-ru-limv="' + k + '"]');
      cb.checked = R.lim[k] != null;
      inp.disabled = R.lim[k] == null;
      inp.value = Math.round(100 * (R.lim[k] != null ? R.lim[k] : LIM_DEF[k]));
    });
  }
  function changed() {
    dirty = true;
    $('[data-ru-save]').disabled = false;
    msg(chosen().length ? 'Not saved yet.' : 'Choose at least one play.', chosen().length ? undefined : false);
    paintControls(); render();
  }
  function buildControls() {
    var seg = $('[data-ru-presets]');
    PRESETS.forEach(function (p) { seg.appendChild(el('button', { type: 'button', 'data-v': p.k, 'aria-pressed': 'false', text: p.n })); });
    seg.appendChild(el('button', { type: 'button', 'data-v': 'custom', 'aria-pressed': 'false', text: 'My own' }));
    seg.addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      var k = b.getAttribute('data-v');
      if (k === 'custom') {
        if (R.preset !== 'custom') R.plays = chosen().map(function (i) { return D.plays[i].s; });
        $('[data-ru-pickbox]').open = true;
      }
      R.preset = k; changed();
    });
    var box = $('[data-ru-picker]');
    D.fams.forEach(function (f) {
      var ps = D.plays.filter(function (p) { return p.f === f[0]; });
      if (!ps.length) return;
      var all = el('button', { type: 'button', 'class': 'linkish small', text: 'all' }), none = el('button', { type: 'button', 'class': 'linkish small', text: 'none' });
      var g = el('fieldset', { 'class': 'wl-fam' }, [el('legend', {}, [f[1] + ' ', all, ' · ', none])]);
      function setFam(v) {
        var cur = chosen().map(function (i) { return D.plays[i].s; });
        var fam = {}; ps.forEach(function (p) { fam[p.s] = 1; });
        cur = cur.filter(function (s) { return !fam[s]; });
        if (v) ps.forEach(function (p) { cur.push(p.s); });
        R.preset = 'custom'; R.plays = cur; changed();
      }
      all.addEventListener('click', function () { setFam(true); });
      none.addEventListener('click', function () { setFam(false); });
      ps.forEach(function (p) {
        var cb = el('input', { type: 'checkbox', value: p.s });
        cb.addEventListener('change', function () {
          var cur = chosen().map(function (i) { return D.plays[i].s; }).filter(function (s) { return s !== p.s; });
          if (cb.checked) cur.push(p.s);
          R.preset = 'custom'; R.plays = cur; changed();
        });
        g.appendChild(el('label', {}, [cb, p.n]));
      });
      box.appendChild(g);
    });
    function thr() {
      var on = parseInt($('[data-ru-on]').value, 10), off = parseInt($('[data-ru-off]').value, 10);
      if (!(on >= 50 && on <= 95)) on = Math.round(R.on * 100);
      if (!(off >= 5 && off <= 90)) off = Math.round(R.off * 100);
      if (off >= on) off = on - 5;
      R.on = on / 100; R.off = off / 100; changed();
    }
    $('[data-ru-on]').addEventListener('change', thr);
    $('[data-ru-off]').addEventListener('change', thr);
    Object.keys(LIM_DEF).forEach(function (k) {
      $('[data-ru-lim="' + k + '"]').addEventListener('change', function () {
        R.lim[k] = this.checked ? (parseInt($('[data-ru-limv="' + k + '"]').value, 10) || Math.round(LIM_DEF[k] * 100)) / 100 : null; changed();
      });
      $('[data-ru-limv="' + k + '"]').addEventListener('change', function () {
        var v = parseInt(this.value, 10);
        if (!(v >= 0 && v <= 100)) v = Math.round(100 * LIM_DEF[k]);
        R.lim[k] = v / 100; changed();
      });
    });
    $('[data-ru-save]').addEventListener('click', save);
    $('[data-ru-reset]').addEventListener('click', function () { R = def(); changed(); });
  }

  function save() {
    if (!chosen().length) { msg('Choose at least one play first.', false); return; }
    var body = JSON.stringify({ preset: R.preset, plays: R.preset === 'custom' ? R.plays : [], on: R.on, off: R.off, lim: R.lim });
    try { localStorage.setItem(KEY, body); } catch (e) { /* storage off */ }
    var btn = $('[data-ru-save]');
    btn.disabled = true;
    msg('Saving…');
    if (!mem) { dirty = false; msg('Saved in this browser.'); return; }
    fetch('/api/member/list', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rules: JSON.parse(body) }) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); })
      .then(function () { dirty = false; msg('Saved to your membership. It applies on any device you sign in on.'); })
      .catch(function (e) { btn.disabled = false; msg("Couldn't save to your membership (" + e.message + "). It's kept in this browser for now.", false); });
  }

  // ---------------------------------------------------------------- output
  function pill(L) {
    if (!L || !L.state) return el('span', { 'class': 'light-pill', text: '–' });
    return el('span', { 'class': 'light-pill ' + L.state }, [el('i', { 'aria-hidden': 'true' }), L.state === 'start' ? 'Start' : 'Stop']);
  }
  function sitePill(t) {
    if (t.L == null) return el('span', { 'class': 'light-pill', text: '–' });
    return pill({ state: t.L ? 'start' : 'stop' });
  }
  function names(list, max) {
    var s = list.slice(0, max || 4).map(function (x) { return x[0] + ' ' + pc(x[1], x[1] < 0.1 ? 1 : 0); }).join(', ');
    return list.length > (max || 4) ? s + ' and ' + (list.length - (max || 4)) + ' more' : s;
  }
  function render() {
    if (!D) return;
    var sel = chosen();
    var W = weights(items), w = W.w;
    var rows = items.map(function (x) {
      var t = D.t[x.sym];
      return { sym: x.sym, t: t, L: lightFor(x.sym, sel), w: w[x.sym] || 0, crash: t.r ? t.r[1] : null };
    }).filter(function (r) { return r.t; });
    // where the list comes from
    var wl = app.getAttribute('data-wl');
    var loading = rows.some(function (r) { return H[r.sym] === undefined; });
    var srcBox = $('[data-ru-src]');
    srcBox.innerHTML = '';
    var how = W.byValue ? ', weighted by value from your file' : ', each counted equally';
    if (src === 'local') srcBox.append('The ' + rows.length + ' stock' + (rows.length === 1 ? '' : 's') + ' on your watchlist in this browser' + how + '. ');
    else if (src === 'saved') srcBox.append('The ' + rows.length + ' stocks on the list saved to your membership' + how + '. ');
    else srcBox.append('An example list. Add your own stocks on the watchlist and they show up here. ');
    srcBox.appendChild(el('a', { href: wl, text: src === 'example' ? 'Add your stocks' : 'Change the list' }));

    var known = rows.filter(function (r) { return r.L && r.L.state; });
    var start = known.filter(function (r) { return r.L.state === 'start'; });
    var startW = start.reduce(function (a, r) { return a + r.w; }, 0);
    var diff = known.filter(function (r) { return r.t.L != null && (r.t.L ? 'start' : 'stop') !== r.L.state; });

    // limits
    var checks = [];
    if (R.lim.pos != null) {
      var over = rows.filter(function (r) { return r.w > R.lim.pos + 1e-9; }).sort(function (a, b) { return b.w - a.w; });
      var top = rows.slice().sort(function (a, b) { return b.w - a.w; })[0];
      checks.push({ ok: !over.length, t: 'No single stock over ' + pc(R.lim.pos),
        d: over.length ? 'Over the limit: ' + names(over.map(function (r) { return [r.t.s, r.w]; })) + '.' : (top ? 'Biggest: ' + top.t.s + ' at ' + pc(top.w) + '.' : '') });
    }
    if (R.lim.group != null) {
      var g = {};
      rows.forEach(function (r) { g[r.t.g] = (g[r.t.g] || 0) + r.w; });
      var gl = Object.keys(g).map(function (k) { return [k, g[k]]; }).sort(function (a, b) { return b[1] - a[1]; });
      var gover = gl.filter(function (x) { return x[1] > R.lim.group + 1e-9; });
      checks.push({ ok: !gover.length, t: 'No sector or group over ' + pc(R.lim.group),
        d: gover.length ? 'Over the limit: ' + names(gover) + '.' : (gl.length ? 'Biggest: ' + gl[0][0] + ' at ' + pc(gl[0][1]) + '.' : '') });
    }
    if (R.lim.start != null) {
      var stops = known.filter(function (r) { return r.L.state === 'stop'; }).sort(function (a, b) { return b.w - a.w; });
      checks.push({ ok: startW >= R.lim.start - 1e-9, t: 'At least ' + pc(R.lim.start) + ' in stocks that are Start under your rule',
        d: pc(startW) + ' is in Start names' + (stops.length ? '. Stop under your rule: ' + names(stops.map(function (r) { return [r.t.s, r.w]; })) + '.' : '.') });
    }
    if (R.lim.crash != null) {
      var hi = rows.filter(function (r) { return HIGH[r.crash]; }).sort(function (a, b) { return b.w - a.w; });
      var hiW = hi.reduce(function (a, r) { return a + r.w; }, 0);
      checks.push({ ok: hiW <= R.lim.crash + 1e-9, t: 'No more than ' + pc(R.lim.crash) + ' in high crash exposure',
        d: pc(hiW) + ' is in names rated High or Very high' + (hi.length ? ': ' + names(hi.map(function (r) { return [r.t.s, r.w]; })) + '.' : '.') });
    }
    var met = checks.filter(function (c) { return c.ok; }).length;

    // tiles
    var p = preset(R.preset);
    var tiles = $('[data-ru-tiles]');
    tiles.innerHTML = '';
    function tile(label, value, note, cls) {
      tiles.appendChild(el('div', { 'class': 'card tile' + (cls ? ' ' + cls : '') }, [el('span', { 'class': 'tile-label', text: label }),
        el('span', { 'class': 'tile-value', html: value }), el('span', { 'class': 'tile-note', text: note })]));
    }
    if (loading) {
      ['Start under your rule', 'Different from the site\u2019s light', 'Limits met', 'Plays counted'].forEach(function (x) { tile(x, '\u2026', 'Working it out'); });
    } else {
    tile('Start under your rule', start.length + ' <small>of ' + known.length + '</small>', pc(startW) + ' of the portfolio' + (W.byValue ? ' by value' : ''));
    tile('Different from the site’s light', String(diff.length), diff.length ? diff.slice(0, 4).map(function (r) { return r.t.s; }).join(', ') + (diff.length > 4 ? '…' : '') : 'Same calls as the site on every stock');
    tile('Limits met', checks.length ? met + ' <small>of ' + checks.length + '</small>' : '–', checks.length ? (met === checks.length ? 'Your portfolio is inside every limit' : (checks.length - met) + ' outside, details below') : 'No limits switched on', checks.length && met < checks.length ? 'ru-warn' : '');
    tile('Plays counted', sel.length + ' <small>of ' + D.plays.length + '</small>', (p ? p.n : 'Your own choice') + ': Start at ' + pc(R.on) + ', Stop at ' + pc(R.off));
    }

    // checks
    var cb = $('[data-ru-checks]');
    cb.innerHTML = '';
    if (!loading) checks.forEach(function (c) {
      cb.appendChild(el('div', { 'class': 'sc-row ' + (c.ok ? 'ok' : 'warn') }, [el('span', { 'class': 'sc-dot', 'aria-hidden': 'true' }),
        el('div', {}, [el('b', { text: (c.ok ? 'Inside: ' : 'Outside: ') + c.t }), el('p', { 'class': 'small muted', text: c.d })])]));
    });

    // table
    var tb = $('[data-ru-table]');
    tb.innerHTML = '';
    var head = ['Stock', 'Your light', 'Site’s light', 'Plays in', 'Since', 'Weight', 'Crash', 'Group'];
    var tbody = el('tbody');
    rows.slice().sort(function (a, b) { return b.w - a.w || (a.t.s < b.t.s ? -1 : 1); }).forEach(function (r) {
      var L = r.L, d = L && L.state && r.t.L != null && (r.t.L ? 'start' : 'stop') !== L.state;
      var share = L && L.n ? L.k / L.n : 0;
      tbody.appendChild(el('tr', { 'class': d ? 'ru-diff' : null }, [
        el('td', {}, [el('a', { href: STOCK.replace('{u}', r.t.u) }, [el('b', { text: r.t.s })]), ' ', el('span', { 'class': 'muted small', text: r.t.n })]),
        el('td', {}, [H[r.sym] === undefined ? el('span', { 'class': 'muted small', text: '…' }) : pill(L)]),
        el('td', {}, [sitePill(r.t)]),
        el('td', { 'class': 'nowrap' }, L ? [el('span', { 'class': 'fillbar', 'aria-hidden': 'true' }, [el('i', { style: 'width:' + Math.round(100 * share) + '%' })]), ' ' + L.k + ' of ' + L.n] : ['–']),
        el('td', { 'class': 'nowrap small' , text: L && L.since ? (L.first ? 'over 2 years' : fdate(L.since)) : '–' }),
        el('td', { 'class': 'r', text: pc(r.w, r.w < 0.1 ? 1 : 0) }),
        el('td', { 'class': 'nowrap small', text: r.crash || '–' }),
        el('td', { 'class': 'small', text: r.t.g })
      ]));
    });
    tb.appendChild(el('div', { 'class': 'tbl-wrap' }, [el('table', { 'class': 'tbl ru-tbl' }, [el('thead', {}, [el('tr', {}, head.map(function (x, i) { return el('th', { 'class': i === 5 ? 'r' : null, text: x }); }))]), tbody])]));
    if (diff.length) tb.appendChild(el('p', { 'class': 'small muted ru-key', html: '<span class="ru-swatch"></span> Highlighted rows: your rule gives a different light from the site’s.' }));
  }

  // ---------------------------------------------------------------- start
  function start() {
    var local = null;
    try { local = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { /* storage off */ }
    if (local) R = clean(local);
    buildControls();
    loadItems();
    paintControls();
    $('[data-ru-save]').disabled = true;
    render();
    var memP = location.protocol === 'file:' ? Promise.resolve(null) :
      fetch('/api/member/list', { credentials: 'same-origin', cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    memP.then(function (L) {
      if (L && !L.error) {
        mem = L;
        if (L.rules && !dirty) { R = clean(L.rules); paintControls(); }
        if (src === 'example') loadItems();
        if (!L.rules && local && !isSite(R)) msg('Using the rule saved in this browser. Save it to keep it on your membership.');
      }
      render();
      return fetchHist();
    }).then(render);
  }

  getJSON(app.getAttribute('data-watch')).then(function (j) { D = j; start(); })
    .catch(function () { $('[data-ru-src]').textContent = "Couldn't load Be The Puck's data. Refresh the page to try again."; });
})();
