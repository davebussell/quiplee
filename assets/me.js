/* me.js: the account page (/me/). Signed out, the page shows the sign-up widget (account.js).
 * Signed in, it draws the dashboard from /api/account/me (the account) and
 * data/reads.json (every covered name's standard signal and read): the stocks you follow,
 * your email alerts, a shortcut into the Theory tester, the member tools and settings.
 * Also handles the links in emails: ?reset= (new password), ?stop= (stop emails),
 * ?confirmed=1 / ?confirm=expired and ?welcome=1. */
(function () {
  'use strict';
  var app = document.getElementById('me-app');
  if (!app || !window.BPAuth) return;
  var BP = window.BPAuth;
  var STOCK = app.getAttribute('data-stock'), FREE = app.getAttribute('data-free') || 'January 1, 2027';
  var POPULAR = ['NVDA', 'AAPL', 'MSFT', 'SHOP.TO', 'RY.TO', 'BTC-USD', 'TSLA', 'TD.TO'];
  var q = new URLSearchParams(location.search);
  var R = null, A = null;

  function $(s, r) { return (r || app).querySelector(s); }
  function $$(s, r) { return [].slice.call((r || app).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function num(v, d) { return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function pct(v, d) { if (v == null || isNaN(v)) return '–'; return (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v * 100), d == null ? 1 : d) + '%'; }
  function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : ''; }
  function money(v, cur) { if (v == null) return '–'; var d = Math.abs(v) < 1 ? 4 : 2; return (cur || '$') + num(v, d); }
  function day(iso) { if (!iso) return ''; var d = new Date(iso + 'T12:00:00Z'); return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }); }
  function daysBetween(a, b) { return Math.round((new Date(b + 'T12:00:00Z') - new Date(a + 'T12:00:00Z')) / 864e5); }
  function bar(k, n) { return '<span class="fillbar" aria-hidden="true"><i style="width:' + (n ? Math.round(100 * k / n) : 0) + '%"></i></span>'; }
  function toast(text, kind) {
    var t = document.createElement('div');
    t.className = 'toast' + (kind ? ' ' + kind : '');
    t.setAttribute('role', 'status');
    t.textContent = text;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('on'); });
    setTimeout(function () { t.classList.remove('on'); setTimeout(function () { t.remove(); }, 400); }, 4200);
  }
  function getJSON(u) { return fetch(u, { credentials: 'same-origin', cache: 'no-store' }).then(function (r) { return r.json(); }); }
  function clean(keys) { keys.forEach(function (k) { q.delete(k); }); var s = q.toString(); history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash); }
  function greeting() { var h = new Date().getHours(); return h < 5 ? 'Good evening' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; }

  // ---------------------------------------------------------------- links from emails
  function resetFlow() {
    var t = q.get('reset');
    if (!t) return false;
    var box = $('[data-me-reset]');
    box.hidden = false;
    $('[data-me-out]').hidden = true;
    var f = $('[data-reset-form]'), out = $('.auth-msg', f);
    $('.pw-eye', f).addEventListener('click', function () { var i = $('input', f); var on = i.type === 'password'; i.type = on ? 'text' : 'password'; this.textContent = on ? 'Hide' : 'Show'; });
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var pw = $('input', f).value;
      if (pw.length < 8) { out.textContent = 'Passwords need at least 8 characters.'; return; }
      $('button[type=submit]', f).disabled = true;
      BP.post('reset', { t: t, password: pw }).then(function (j) {
        if (!j.ok) { out.textContent = j.error || "That didn't work."; $('button[type=submit]', f).disabled = false; return; }
        location.href = location.pathname + '?pwreset=1';
      });
    });
    return true;
  }
  function notices() {
    if (q.get('welcome')) { toast('Welcome to Be The Puck. Follow a few stocks to get started.'); clean(['welcome']); }
    if (q.get('confirmed')) { toast('Email confirmed. Alerts can reach you now.'); clean(['confirmed']); }
    if (q.get('confirm') === 'expired') { toast('That confirm link has expired or was replaced. Send a new one below.', 'warn'); clean(['confirm']); }
    if (q.get('pwreset')) { toast('New password saved. You are signed in.'); clean(['pwreset']); }
  }

  // ---------------------------------------------------------------- dashboard
  // plays in for a name: the plays the reader counts (plays.js), else every play from reads.json
  var PS = window.BPPlays;
  function kn(s) {
    var t = R.t[s];
    if (PS && PS.loaded() && !PS.isAll() && PS.data().t[s]) { var c = PS.count(s); return [c.k, c.n]; }
    return [t.k || 0, t.of || 0];
  }
  // the reader's signal on a name (plays.js), or null before it loads
  // your signal on a name: the reader's weights once plays.js has loaded, else the standard one from reads.json
  var SIGW = { '1': ['Buy', 'buy'], '0': ['Hold', 'hold'], '-1': ['Sell', 'sell'] };
  function sg(s) {
    if (PS && PS.loaded() && PS.data().x[s]) return PS.score(s);
    var t = R.t[s];
    return t && t.sc != null ? { s: t.sc, sig: t.S } : { s: null, sig: null };
  }
  function pillOnly(sig) { var w = SIGW[sig]; return w ? '<span class="sig-pill ' + w[1] + '">' + w[0] + '</span>' : '<span class="sig-pill na">–</span>'; }
  function sgPill(r) {
    var w = r && r.sig != null ? SIGW[r.sig] : null;
    return w ? '<span class="sig-pill ' + w[1] + '">' + w[0] + '</span> <b class="sig-n ' + w[1] + '">' + r.s + '</b>' : '<span class="sig-pill na">–</span>';
  }
  function psChip() {
    return '<button type="button" class="ps-chip ps-chip-sm" data-ps-open aria-haspopup="dialog"><span class="ps-chip-k">Plays counted</span><b data-ps-label>' +
      esc(PS && PS.loaded() ? PS.label(false) : 'All 100') + '</b><span class="ps-caret" aria-hidden="true">▾</span></button>';
  }
  // signals that changed on the stocks you follow since this browser last looked (plays.js changes())
  function changesHtml(list) {
    if (!PS || !PS.loaded()) return '';
    var ch = PS.changes('me', list);
    if (!ch || !ch.since) return '';
    var when = day(ch.since);
    if (!ch.list.length) return '<p class="small muted me-ch-none">No signal changed on your stocks since the ' + esc(when) + ' close.</p>';
    return '<div class="me-changes"><p class="h3">Changed since the ' + esc(when) + ' close</p><ul>' + ch.list.map(function (c) {
      var t = R.t[c.sym];
      return '<li><a href="' + esc(STOCK.replace('{u}', t.u)) + '"><b>' + esc(t.s) + '</b></a> ' + pillOnly(c.from) + ' → ' + sgPill({ sig: c.to, s: c.s }) + '</li>';
    }).join('') + '</ul></div>';
  }
  function followRows() {
    var list = (A.follow || []).filter(function (s) { return R.t[s]; });
    if (!list.length) {
      return '<div class="me-empty"><p><b>Follow a few stocks to get started.</b> You\'ll see your signal on each one here, and get an email the evening it flips.</p>' +
        '<div class="me-chips">' + POPULAR.filter(function (s) { return R.t[s]; }).map(function (s) { return '<button type="button" class="chip-btn" data-add="' + esc(s) + '">+ ' + esc(R.t[s].s) + '</button>'; }).join('') + '</div></div>';
    }
    var D = fxD(), all = rowsData();
    return changesHtml(list) + '<div data-vtools>' + toolsHtml(all, D) + '</div><div data-vtbl>' + tableHtml(all, D) + '</div>';
  }

  // ------------------------------------------------------------ your stocks: a table you can widen and filter
  // Any of the factors your signal can weight, as columns you choose (plays.js data: each name's points 0-100 and
  // the value shown); filters by your signal, group, name, and "favours buying" (60+ points) or "counts against"
  // (40 or fewer) on any factor. The headers sort (sortable.js). The view is kept per browser.
  var VKEY = 'bp.me.view.v1', FF_OPEN = false, PICK_OPEN = false;
  var V = (function () { try { var v = JSON.parse(localStorage.getItem(VKEY) || 'null'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } })();
  function vsave() { try { localStorage.setItem(VKEY, JSON.stringify(V)); } catch (e) { /* storage off: the view lasts until reload */ } }
  var SHORT = { upside: 'Upside', rating: 'Analysts', pe: 'P/E', fpe: 'Fwd P/E', peg: 'PEG', ps: 'P/S', pb: 'P/B', dy: 'Yield', eg: 'EPS growth',
    rg: 'Sales growth', pm: 'Margin', roe: 'ROE', de: 'Debt/equity', offhigh: 'Off high', trend: 'vs 200\u2011day', mom: '1-yr move', calm: 'Crash exposure' };
  var DEF_COLS = ['pe', 'rg', 'dy', 'calm'];
  var CONDS = { hi: 'favours buying (60+ points)', lo: 'counts against (40 or fewer)' };
  function fxD() { return PS && PS.loaded() ? PS.data() : null; }
  function fxAt(D, k) { for (var i = 0; i < D.fx.length; i++) if (D.fx[i].k === k) return i; return -1; }
  function myFactors() {
    var W = PS && PS.loaded() ? PS.weights() : null;
    return W ? Object.keys(W.w).filter(function (k) { return W.w[k] > 0 && k !== 'plays'; }) : [];
  }
  function viewCols(D) {
    if (!D) return [];
    var c = V.cols && V.cols.length ? V.cols : myFactors().concat(DEF_COLS), out = [];
    c.forEach(function (k) { if (k !== 'plays' && fxAt(D, k) >= 0 && out.indexOf(k) < 0) out.push(k); });
    return out;
  }
  function vshort(k, v) {                 // "−7% from its 1-year high" -> "−7%"; "1.3 · strong buy" -> "strong buy"
    if (v == null || v === '') return '–';
    var p = String(v).split(' · ');
    if (/^at its /.test(p[0])) return 'at high';
    return k === 'rating' ? (p[1] || p[0]) : p[0].split(/ from | vs /)[0];
  }
  function ptsCls(p) { return p == null ? '' : p >= 60 ? ' fx-good' : p <= 40 ? ' fx-bad' : ''; }
  function rowsData() {
    var D = fxD();
    return (A.follow || []).filter(function (s) { return R.t[s]; }).map(function (s) {
      return { s: s, t: R.t[s], r: sg(s), c: kn(s), x: D && D.x[s], v: D && D.v[s] };
    });
  }
  function passes(o, D) {
    if (V.sig != null && (o.r.sig == null || String(o.r.sig) !== String(V.sig))) return false;
    if (V.g && o.t.g !== V.g) return false;
    if (V.q) { var q = String(V.q).trim().toUpperCase(); if (q && o.t.s.toUpperCase().indexOf(q) < 0 && o.t.n.toUpperCase().indexOf(q) < 0) return false; }
    if (D) {
      for (var i = 0; i < (V.ff || []).length; i++) {
        var j = fxAt(D, V.ff[i][0]);
        if (j < 0) continue;
        var p = o.x ? o.x[j] : null;
        if (V.ff[i][1] === 'hi' && !(p != null && p >= 60)) return false;
        if (V.ff[i][1] === 'lo' && !(p != null && p <= 40)) return false;
      }
    }
    return true;
  }
  function filtered() { return V.sig != null || !!V.g || !!(V.q && String(V.q).trim()) || !!(V.ff && V.ff.length); }
  function fxOptions(D) {
    return D.fg.map(function (g) {
      var o = D.fx.filter(function (f) { return f.g === g[0] && f.k !== 'plays'; }).map(function (f) { return '<option value="' + esc(f.k) + '">' + esc(f.n) + '</option>'; }).join('');
      return o ? '<optgroup label="' + esc(g[1]) + '">' + o + '</optgroup>' : '';
    }).join('');
  }
  function toolsHtml(all, D) {
    var n = { '': all.length, '1': 0, '0': 0, '-1': 0 }, cur = V.sig == null ? '' : String(V.sig);
    all.forEach(function (o) { if (o.r.sig != null) n[String(o.r.sig)]++; });
    var segs = [['', 'All'], ['1', 'Buy'], ['0', 'Hold'], ['-1', 'Sell']].map(function (x) {
      return '<button type="button" class="chip-btn" data-vsig="' + x[0] + '" aria-pressed="' + (cur === x[0]) + '">' + x[1] + ' <span class="muted">' + n[x[0]] + '</span></button>';
    }).join('');
    var groups = [];
    all.forEach(function (o) { if (o.t.g && groups.indexOf(o.t.g) < 0) groups.push(o.t.g); });
    groups.sort();
    if (V.g && groups.indexOf(V.g) < 0) V.g = '';
    var gsel = groups.length > 1 ? '<select class="me-vsel" data-vg aria-label="Group"><option value="">All groups</option>' +
      groups.map(function (g) { return '<option' + (g === V.g ? ' selected' : '') + '>' + esc(g) + '</option>'; }).join('') + '</select>' : '';
    var find = '<input type="search" class="me-vq" data-vq placeholder="Find in your list" value="' + esc(V.q || '') + '" aria-label="Find in your stocks" autocomplete="off">';
    var more = D ? '<button type="button" class="chip-btn" data-vff-open aria-expanded="' + FF_OPEN + '">+ Factor filter</button>' +
      '<button type="button" class="chip-btn" data-vcols aria-expanded="' + PICK_OPEN + '">Columns ▾</button>' : '';
    var chips = D ? (V.ff || []).map(function (f, i) {
      var j = fxAt(D, f[0]);
      return j < 0 ? '' : '<span class="me-ffchip">' + esc(D.fx[j].n) + ' ' + esc(CONDS[f[1]] || '') + '<button type="button" data-vff-del="' + i + '" aria-label="Remove this filter">×</button></span>';
    }).join('') : '';
    var add = D && FF_OPEN ? '<div class="me-ffadd"><select class="me-vsel" data-vff-k aria-label="Factor">' + fxOptions(D) + '</select>' +
      '<select class="me-vsel" data-vff-c aria-label="Condition"><option value="hi">' + CONDS.hi + '</option><option value="lo">' + CONDS.lo + '</option></select>' +
      '<button type="button" class="btn sm" data-vff-add>Add filter</button></div>' : '';
    return '<div class="me-tools"><div class="me-seg" role="group" aria-label="Your signal">' + segs + '</div>' + gsel + find + more + '</div>' +
      (chips || add ? '<div class="me-ff">' + chips + add + '</div>' : '') + pickHtml(D);
  }
  function pickHtml(D) {
    if (!D || !PICK_OPEN) return '';
    var on = viewCols(D);
    var presets = [['mine', 'Your weights'], ['value', 'Value'], ['quality', 'Growth and quality'], ['price', 'Price and risk'], ['signals', 'Analysts'], ['all', 'All'], ['default', 'Default']]
      .map(function (x) { return '<button type="button" class="chip-btn" data-vpreset="' + x[0] + '">' + x[1] + '</button>'; }).join('');
    var groups = D.fg.map(function (g) {
      var boxes = D.fx.filter(function (f) { return f.g === g[0] && f.k !== 'plays'; }).map(function (f) {
        return '<label class="me-colbox" title="' + esc(f.d) + '"><input type="checkbox" data-vcol="' + esc(f.k) + '"' + (on.indexOf(f.k) >= 0 ? ' checked' : '') + '> ' + esc(f.n) + '</label>';
      }).join('');
      return boxes ? '<fieldset><legend>' + esc(g[1]) + '</legend>' + boxes + '</fieldset>' : '';
    }).join('');
    return '<div class="me-colpick"><div class="me-presets"><span class="small muted">Quick picks</span>' + presets + '</div><div class="me-colgrid">' + groups + '</div></div>';
  }
  function tableHtml(all, D) {
    var rows = all.filter(function (o) { return passes(o, D); }), cs = viewCols(D);
    var head = '<tr><th class="stick">Stock</th><th data-sort-first="desc">Your signal</th><th data-sort-first="desc">Plays in</th>' +
      '<th class="r" data-sort-first="desc" title="The latest close, and the change on the day; sorts by the day">Price</th><th class="r" data-sort-first="desc">1 year</th>' +
      cs.map(function (k) {
        var f = D.fx[fxAt(D, k)];
        return '<th class="r" data-sort-first="desc" title="' + esc(f.n + '. ' + f.d + ' Sorts by points: most in favour of buying first.') + '">' + esc(SHORT[k] || f.n) + '</th>';
      }).join('') + '<th aria-label="Remove"></th></tr>';
    var body = rows.map(function (o) {
      var t = o.t, r = o.r;
      return '<tr><td class="stick"><a class="me-sym" href="' + esc(STOCK.replace('{u}', t.u)) + '"><b>' + esc(t.s) + '</b><span>' + esc(t.n) + '</span></a></td>' +
        '<td class="nowrap" data-v="' + (r.s == null ? '' : r.s) + '">' + sgPill(r) + (r.held ? '<small class="me-held" title="A Buy holds until the score drops below 50, a Sell until it rises above 50">held</small>' : '') + '</td>' +
        '<td class="nowrap" data-v="' + (o.c[1] ? (o.c[0] / o.c[1]).toFixed(4) : '') + '" title="' + o.c[0] + ' of ' + o.c[1] + ' plays hold it">' + bar(o.c[0], o.c[1]) + ' <span class="mono small">' + (o.c[1] ? Math.round(100 * o.c[0] / o.c[1]) + '%' : '–') + '</span></td>' +
        '<td class="r nowrap" data-v="' + (t.d1 == null ? '' : t.d1) + '"><span class="mono">' + money(t.p, t.cur) + '</span>' + (t.d1 != null ? '<small class="me-d1 ' + cls(t.d1) + '">' + pct(t.d1) + '</small>' : '') + '</td>' +
        '<td class="r nowrap ' + cls(t.y1) + '" data-v="' + (t.y1 == null ? '' : t.y1) + '">' + pct(t.y1, 0) + '</td>' +
        cs.map(function (k) {
          var j = fxAt(D, k), p = o.x ? o.x[j] : null, v = o.v ? o.v[j] : null;
          return '<td class="r nowrap fx' + ptsCls(p) + '" data-v="' + (p == null ? '' : p) + '" title="' + esc(v ? v + ' · ' + p + ' points' : 'No number for this stock') + '">' + esc(vshort(k, v)) + '</td>';
        }).join('') +
        '<td class="c"><button type="button" class="me-x" data-remove="' + esc(o.s) + '" aria-label="Stop following ' + esc(t.s) + '">×</button></td></tr>';
    }).join('');
    var none = rows.length ? '' : '<p class="me-vnone">No stocks match these filters. <button type="button" class="linkish" data-vreset>Clear filters</button></p>';
    var foot = '<p class="small muted me-vfoot">' + (filtered() ? 'Showing ' + rows.length + ' of ' + all.length + ' · <button type="button" class="linkish" data-vreset>Clear filters</button> · ' : '') +
      (D ? '<span class="fx-key fx-good">Green</span>: the factor favours buying (60+ points) · <span class="fx-key fx-bad">red</span>: it counts against (40 or fewer). ' : '') +
      'Click a header to sort.</p>';
    return (rows.length ? '<div class="tbl-wrap me-tblwrap"><table class="tbl me-tbl"><thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>' : none) + foot;
  }
  function vRefresh(tools) {
    var D = fxD(), all = rowsData();
    if (tools) { var tb = $('[data-vtools]'); if (tb) tb.innerHTML = toolsHtml(all, D); }
    var tt = $('[data-vtbl]');
    if (tt) tt.innerHTML = tableHtml(all, D);
  }
  function vPreset(name, D) {
    if (name === 'default') { delete V.cols; return; }
    if (name === 'mine') { V.cols = myFactors().length ? myFactors() : DEF_COLS.slice(); return; }
    V.cols = D.fx.filter(function (f) { return f.k !== 'plays' && (name === 'all' || f.g === name); }).map(function (f) { return f.k; });
  }
  function sigTile(list) {
    var n = { '1': 0, '0': 0, '-1': 0 };
    list.forEach(function (s) { var r = sg(s); if (r && r.sig != null) n[r.sig]++; });
    var wl = PS && PS.loaded() ? PS.wlabel() : 'Plays + exit rules';
    return '<div class="card tile"><span class="tile-label">Your signal on your stocks</span><span class="tile-value"><b class="sig-n buy" data-count="' + n['1'] + '">' + n['1'] + '</b><small> Buy of ' + list.length + '</small></span>' +
      bar(n['1'], list.length || 1) + '<span class="tile-note">' + (list.length ? n['0'] + ' Hold · ' + n['-1'] + ' Sell · weights: ' + esc(wl) : 'Follow a few to begin') + '</span></div>';
  }
  function playsTile(avg) {
    return '<div class="card tile"><span class="tile-label">Plays holding your stocks</span><span class="tile-value">' + (avg == null ? '–' : avg + '<small>%</small>') + '</span><span class="tile-note">' + (avg == null ? 'Follow a few to see it' : 'On average across your list') + '</span></div>';
  }
  function kpis() {
    var list = (A.follow || []).filter(function (s) { return R.t[s]; });
    var al = A.alerts || {};
    var mailState = !A.email ? ['Add your email', 'warn'] : !A.email_ok ? ['Confirm your email', 'warn'] : al.on ? ['On', 'on'] : ['Off', ''];
    var k = 0, n = 0;
    list.forEach(function (s) { var c = kn(s); k += c[0]; n += c[1]; });
    var avg = n ? Math.round(100 * k / n) : null;
    return '<div class="me-kpis">' +
      sigTile(list) + playsTile(avg) +
      '<div class="card tile"><span class="tile-label">Email alerts</span><span class="tile-value me-mail ' + mailState[1] + '">' + mailState[0] + '</span><span class="tile-note">' + (A.last_sent ? 'Last sent after the ' + esc(day(A.last_sent)) + ' close' : 'Sent after the close, only on a change') + '</span></div>' +
      '</div>';
  }
  function notice() {
    if (!A.email) {
      return '<div class="me-note warn"><b>Add your email to unlock the member tools</b> and get alerts. Your username stays as it is.' +
        ' <a href="#account">Add it below</a></div>';
    }
    if (!A.email_ok) {
      return '<div class="me-note"><b>Confirm your email</b> to switch on alerts. ' +
        (A.mail_on ? 'We sent a link to ' + esc(A.email) + '. <button type="button" class="linkish" data-resend>Send it again</button>'
          : 'Emails switch on shortly; your link to ' + esc(A.email) + ' will arrive as soon as they do.') + '</div>';
    }
    return '';
  }
  function alertsCard() {
    var al = A.alerts || {}, member = A.member && A.member.active;
    var stop = q.get('stop');
    var body;
    if (!A.email) {
      body = '<p class="small muted">Alerts need an email address. Add one under <a href="#account">Account</a>.</p>';
    } else {
      body = '<p class="small">Emails go to <b>' + esc(A.email) + '</b>' + (A.email_ok ? ' <span class="tag">Confirmed</span>' : ' <span class="tag warn">Not confirmed yet</span>') + '</p>' +
        '<label class="switch"><input type="checkbox" data-al-on' + (al.on ? ' checked' : '') + '><span class="sw" aria-hidden="true"></span><span>Email me when something changes on my stocks</span></label>' +
        '<fieldset class="me-level"' + (al.on ? '' : ' disabled') + '><legend class="small muted">What to send</legend>' +
        '<label class="radio"><input type="radio" name="lvl" value="light"' + (al.level === 'light' ? ' checked' : '') + '><span><b>When your signal flips</b><small>Free for good</small></span></label>' +
        '<label class="radio"><input type="radio" name="lvl" value="all"' + (al.level !== 'light' ? ' checked' : '') + (member ? '' : ' disabled') + '><span><b>Flips, every play that moves, and prices near a play\'s line</b><small>Member tool · free until ' + esc(FREE) + '</small></span></label>' +
        '</fieldset><p class="small muted">Sent after the U.S. close, only when something changed. Every email has a one-click unsubscribe.</p>';
    }
    if (stop) {
      body = '<div class="me-note warn"><b>Stop all Be The Puck emails?</b> <button type="button" class="btn sm" data-stop>Stop emails</button></div>' + body;
    }
    return '<section class="card me-card" id="alerts"><div class="me-card-h"><h2 class="h3">Email alerts</h2></div>' + body + '<p class="pt-msg" data-al-msg role="status"></p></section>';
  }
  function theoryCard() {
    var list = (A.follow || []).filter(function (s) { return R.t[s]; });
    var opts = list.map(function (s) { return '<option value="' + esc(R.t[s].u) + '">' + esc(R.t[s].s) + ' · ' + esc(R.t[s].n) + '</option>'; }).join('');
    var fams = [['all', 'All 100 plays'], ['fam:trend', 'Trend following'], ['fam:breakout', 'Breakouts & channels'], ['fam:momentum', 'Momentum'],
      ['fam:reversion', 'Mean reversion'], ['fam:volume', 'Volume & money flow'], ['fam:pattern', 'Candles & chart patterns'], ['fam:calendar', 'Calendar']];
    return '<section class="card me-card" id="theory"><div class="me-card-h"><h2 class="h3">Test a theory</h2></div>' +
      '<p class="small muted">Pick one of your stocks and a theory: see the reading, why, and every play\'s reason to buy or not.</p>' +
      (list.length ? '<form class="me-th" action="/theory/" method="get"><label class="small muted" for="me-th-s">Stock</label><select id="me-th-s" name="s">' + opts + '</select>' +
        '<label class="small muted" for="me-th-t">Theory</label><select id="me-th-t" name="t">' + fams.map(function (f) { return '<option value="' + f[0] + '">' + esc(f[1]) + '</option>'; }).join('') + '</select>' +
        '<button class="btn primary" type="submit">Test it</button></form>'
        : '<a class="btn primary" href="/theory/">Open the Theory tester</a>') + '</section>';
  }
  function rulesLine() {
    var r = A.rules;
    if (!r) return 'Check your holdings against your own limits: biggest stock, biggest sector, crash exposure.';
    var names = { all: 'Every play', best: 'Best record', protect: 'Crash protection', trend: 'Trend riders', dip: 'Dip buyers', custom: 'Your own pick of plays' };
    return (names[r.preset] || 'Your plays') + ': Start at ' + Math.round(r.on * 100) + '%, Stop at ' + Math.round(r.off * 100) + '%.';
  }
  function toolsCard() {
    var m = A.member || {};
    var badge = m.kind === 'paid' ? '<span class="tag live">Member</span>' : m.active ? '<span class="tag mem">Free until ' + esc(FREE) + '</span>' : '<span class="tag">$5 a month</span>';
    var tools = [['/picks/', 'Top picks', 'Five rule-based picks, reviewed every Friday.'], ['/rules/', 'Portfolio limits', rulesLine()],
      ['/articles/', 'Reports', 'Every long read and plain-English stock brief.'], ['/guides/', 'Which predictions work?', 'Guides to all ' + (R && R.n ? R.n : 100) + ' plays. Free for everyone.']];
    return '<section class="me-tools"><div class="sec-head"><h2 class="h2">Member tools</h2>' + badge + '</div><div class="grid grid-4">' +
      tools.map(function (t) { return '<a class="card mem-card" href="' + t[0] + '"><span class="name">' + esc(t[1]) + '</span><span class="muted small">' + esc(t[2]) + '</span></a>'; }).join('') +
      '</div>' + (m.kind === 'free' ? '<p class="small muted">From ' + esc(FREE) + ' member tools are $5 a month. We\'ll email you before then; nothing is charged unless you choose to subscribe.</p>' : '') + '</section>';
  }
  function accountCard() {
    return '<section class="card me-card me-acct" id="account"><div class="me-card-h"><h2 class="h3">Account</h2><button type="button" class="btn sm" data-signout>Sign out</button></div>' +
      '<dl class="me-dl"><dt>Username</dt><dd>' + esc(A.name) + '</dd><dt>Email</dt><dd>' + (A.email ? esc(A.email) : '<span class="muted">None yet</span>') + '</dd>' +
      '<dt>Member since</dt><dd>' + esc(new Date(A.created).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })) + '</dd></dl>' +
      '<details class="pt-more"' + (A.email ? '' : ' open') + '><summary>' + (A.email ? 'Change email' : 'Add your email') + '</summary><form class="auth-form" data-acct="email" novalidate>' +
      '<label>Email<input name="email" type="email" autocomplete="email" required></label>' +
      '<label>Your password<input name="password" type="password" autocomplete="current-password" required></label>' +
      (A.email ? '' : '<label class="auth-check"><input type="checkbox" name="alerts"><span>Email me when my signal flips on stocks I follow. I can stop any time.</span></label>') +
      '<button class="btn primary" type="submit">' + (A.email ? 'Change email' : 'Add email') + '</button><p class="auth-msg" role="alert"></p></form></details>' +
      '<details class="pt-more"><summary>Change password</summary><form class="auth-form" data-acct="password" novalidate>' +
      '<label>Current password<input name="old" type="password" autocomplete="current-password" required></label>' +
      '<label>New password<input name="password" type="password" autocomplete="new-password" minlength="8" required></label>' +
      '<button class="btn" type="submit">Change password</button><p class="auth-msg" role="alert"></p></form></details>' +
      '<details class="pt-more"><summary>Delete my account</summary><form class="auth-form" data-acct="delete" novalidate>' +
      '<p class="small muted">Removes your account, followed stocks and emails for good.</p>' +
      '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>' +
      '<button class="btn" type="submit">Delete my account</button><p class="auth-msg" role="alert"></p></form></details></section>';
  }
  // ------------------------------------------------------------ following stocks: what people type
  // One name or ticker ("NVDA", "Shopify"), or several split by commas, semicolons or new lines
  // ("NVDA, AMD, Shopify"); plain tickers split by spaces work too ("NVDA AMD MU").
  function norm(x) { return String(x || '').trim().toUpperCase().replace(/^\$/, '').replace(/^(TSX|TSE|TSXV|NASDAQ|NYSE|NYSEARCA|ARCA|AMEX|BATS)\s*:\s*/, ''); }
  function exact(x) {                      // a ticker as typed -> the covered symbol, or null
    var s = norm(x);
    if (!s) return null;
    if (R.t[s]) return s;
    var hit = null;
    Object.keys(R.t).forEach(function (k) { if (!hit && R.t[k].s.toUpperCase() === s) hit = k; });
    if (hit) return hit;
    var dash = s.replace(/\.([A-Z])$/, '-$1');            // BRK.B -> BRK-B
    if (R.t[dash]) return dash;
    if (R.t[s + '.TO']) return s + '.TO';                 // RY -> RY.TO
    if (R.t[s + '-USD']) return s + '-USD';               // BTC -> BTC-USD
    return null;
  }
  function pieces(text) {
    var out = [];
    String(text || '').split(/[,;\n]+/).forEach(function (p) {
      p = p.trim();
      if (!p) return;
      var words = p.split(/\s+/);
      if (words.length > 1 && words.every(exact)) words.forEach(function (w) { out.push(w); });
      else out.push(p);
    });
    return out;
  }
  function rank(qs, all) {                 // [[score, length, sym]], best first; all: keep stocks already followed
    qs = norm(qs);
    if (!qs) return [];
    var out = [], ex = exact(qs);
    Object.keys(R.t).forEach(function (s) {
      var t = R.t[s], sh = t.s.toUpperCase(), nm = t.n.toUpperCase();
      var score = s === ex || sh === qs || s === qs ? 0 : sh.indexOf(qs) === 0 ? 1 : nm.indexOf(qs) === 0 ? 2 : nm.indexOf(' ' + qs) >= 0 ? 3 : -1;
      if (score >= 0 && (all || (A.follow || []).indexOf(s) < 0)) out.push([score, sh.length, s]);
    });
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out;
  }
  function suggest(qs) { return rank(qs).slice(0, 7).map(function (x) { return x[2]; }); }
  // one piece of a list -> {sym} when it's a ticker or names one stock clearly, else {bad, many}
  function resolveOne(p) {
    var s = exact(p);
    if (s) return { sym: s };
    var r = rank(p, true);
    if (r.length === 1 || (r.length > 1 && r[0][0] < r[1][0])) return { sym: r[0][2] };
    return { bad: p.trim(), many: r.length > 1 };
  }
  function draw() {
    var box = $('[data-me-in]');
    var local = [];
    try { var v = JSON.parse(localStorage.getItem('quiplee.watch.v1') || 'null'); local = ((v && v.items) || []).map(function (x) { return x.sym; }).filter(function (s) { return R.t[s] && (A.follow || []).indexOf(s) < 0; }); } catch (e) { /* storage off */ }
    box.innerHTML =
      '<div class="me-top"><div><p class="eyebrow">Your account</p><h1 class="h1 me-hi">' + greeting() + ', <em>' + esc(A.name) + '</em></h1>' +
      '<p class="muted">The ' + esc(day(R.asof)) + ' close · ' + (A.follow || []).length + ' stock' + ((A.follow || []).length === 1 ? '' : 's') + ' followed</p></div>' +
      '<div class="hero-links"><a class="btn primary glow" href="/theory/">Theory tester</a><a class="btn" href="/#screen">Screener</a></div></div>' +
      notice() + kpis() +
      '<section class="card me-card me-stocks" id="stocks"><div class="me-card-h"><h2 class="h3">Your stocks</h2><span class="small muted">' + (A.follow || []).length + ' of 100</span></div>' +
      '<div class="ps-bar ps-bar-me">' + psChip() + '<p class="small muted">Plays in counts only the plays you pick, here and across the site.</p></div>' +
      '<div class="me-add"><input type="search" data-add-q placeholder="Follow stocks: NVDA, Shopify, RY…" autocomplete="off" enterkeyhint="done" aria-label="Follow stocks: one name or ticker, or several separated by commas"><div class="me-sug" data-sug hidden></div></div>' +
      '<p class="small muted me-add-msg" data-add-msg hidden></p>' +
      (local.length ? '<p class="small"><button type="button" class="linkish" data-import>Follow the ' + local.length + ' stock' + (local.length === 1 ? '' : 's') + ' on this browser\'s watchlist</button></p>' : '') +
      '<div data-rows>' + followRows() + '</div></section>' +
      '<div class="me-grid me-grid2">' + alertsCard() + theoryCard() + '</div>' +
      toolsCard() + accountCard();
    box.hidden = false;
    wire(box, local);
  }
  function setFollow(list) { A.follow = list; $('[data-rows]').innerHTML = followRows(); draw(); }
  function names(syms) {
    var n = syms.map(function (x) { return R.t[x] ? R.t[x].s : x; });
    return n.length < 2 ? n.join('') : n.slice(0, -1).join(', ') + ' and ' + n[n.length - 1];
  }
  var LOCAL = [], BUSY = false;
  // follow every stock in what was typed; anything that couldn't be matched stays in the box, with a note under it
  function addText(text) {
    var ps = pieces(text), syms = [], bad = [], many = [], had = [];
    ps.forEach(function (p) {
      var r = resolveOne(p);
      if (!r.sym) (r.many ? many : bad).push(r.bad);
      else if ((A.follow || []).indexOf(r.sym) >= 0) had.push(r.sym);
      else if (syms.indexOf(r.sym) < 0) syms.push(r.sym);
    });
    var room = 100 - (A.follow || []).length, over = syms.length > room ? syms.slice(room) : [];
    if (over.length) syms = syms.slice(0, room);
    var keep = bad.concat(many).concat(over.map(function (x) { return R.t[x].s; }));
    function report() {
      var msg = [];
      if (had.length) msg.push('Already following ' + names(had) + '.');
      if (many.length) msg.push('"' + many.join('", "') + '" matches more than one stock: pick one from the list.');
      if (over.length) msg.push('Your list holds 100 stocks; ' + names(over) + " didn't fit.");
      var note = $('[data-add-msg]');
      if (note) {
        note.innerHTML = (bad.length ? 'Not covered yet: <b>' + esc(bad.join(', ')) + '</b>. <a href="/watchlist/?t=' + encodeURIComponent(bad.map(norm).join(',')) +
          '">Request ' + (bad.length === 1 ? 'it' : 'them') + ' on the watchlist</a>; new names are analysed overnight. ' : '') + esc(msg.join(' '));
        note.hidden = !note.innerHTML;
      }
      var i = $('[data-add-q]');
      if (i) { i.value = keep.join(', '); i.focus(); }
    }
    if (!syms.length) { report(); return; }
    if (BUSY) return;
    BUSY = true;
    BP.post('follow', { add: syms }).then(function (j) {
      BUSY = false;
      if (!j.ok) return toast(j.error || "Couldn't add that.", 'warn');
      var added = syms.filter(function (x) { return (j.follow || []).indexOf(x) >= 0; });
      setFollow(j.follow);
      if (added.length) toast('Following ' + names(added) + '.');
      report();
    }, function () { BUSY = false; toast("Couldn't reach your account. Try again in a moment.", 'warn'); });
  }
  function wire(box, local) {
    LOCAL = local;
    var input = $('[data-add-q]', box), sug = $('[data-sug]', box);
    input.addEventListener('input', function () {
      var ps = pieces(input.value), multi = ps.length > 1 || /[,;]\s*$/.test(input.value);
      var last = /[,;]\s*$/.test(input.value) ? '' : (ps[ps.length - 1] || '');
      var list = suggest(last), html = '';
      if (multi) {
        var ok = ps.map(resolveOne).filter(function (r) { return r.sym && (A.follow || []).indexOf(r.sym) < 0; }).map(function (r) { return r.sym; });
        ok = ok.filter(function (x, i) { return ok.indexOf(x) === i; });
        if (ok.length) html += '<button type="button" class="me-sug-all" data-add-all><b>Follow ' + (ok.length === 1 ? 'it' : ok.length === 2 ? 'both' : 'all ' + ok.length) + ':</b><span>' + esc(names(ok)) + '</span></button>';
      }
      // with a list, picking a suggestion fills in the name being typed; with one name it follows it
      html += list.map(function (s) { var t = R.t[s]; return '<button type="button" ' + (multi ? 'data-pick' : 'data-add') + '="' + esc(s) + '"><b>' + esc(t.s) + '</b><span>' + esc(t.n) + '</span></button>'; }).join('');
      sug.innerHTML = html;
      sug.hidden = !html;
    });
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      var ps = pieces(input.value);
      if (ps.length > 1) return addText(input.value);
      var l = suggest(input.value);
      if (l.length) addText(R.t[l[0]].s);
      else addText(input.value);
    });
    if (box.getAttribute('data-wired')) return;   // the page's buttons are wired once; the box is redrawn often
    box.setAttribute('data-wired', '1');
    box.addEventListener('input', function (e) {
      if (!e.target.hasAttribute || !e.target.hasAttribute('data-vq')) return;
      V.q = e.target.value;
      vsave();
      vRefresh(false);                            // the table only, so the box keeps its focus
    });
    box.addEventListener('change', function (e) {
      var el = e.target;
      if (!el.hasAttribute) return;
      if (el.hasAttribute('data-vg')) { V.g = el.value; vsave(); vRefresh(false); }
      else if (el.hasAttribute('data-vcol')) {
        var D = fxD(), on = viewCols(D), k = el.getAttribute('data-vcol');
        on = el.checked ? (on.indexOf(k) < 0 ? on.concat([k]) : on) : on.filter(function (x) { return x !== k; });
        V.cols = on.length ? on : ['pe'];
        vsave();
        vRefresh(false);
      }
    });
    box.addEventListener('click', function (e) {
      var v = e.target.closest ? e.target.closest('[data-vsig],[data-vff-open],[data-vff-add],[data-vff-del],[data-vcols],[data-vpreset],[data-vreset]') : null;
      if (v) {
        var D = fxD();
        if (v.hasAttribute('data-vsig')) { var x = v.getAttribute('data-vsig'); V.sig = x === '' ? null : +x; }
        else if (v.hasAttribute('data-vff-open')) { FF_OPEN = !FF_OPEN; PICK_OPEN = false; }
        else if (v.hasAttribute('data-vcols')) { PICK_OPEN = !PICK_OPEN; FF_OPEN = false; }
        else if (v.hasAttribute('data-vff-add')) {
          var fk = $('[data-vff-k]'), fc = $('[data-vff-c]');
          if (fk && fc) {
            V.ff = (V.ff || []).filter(function (f) { return f[0] !== fk.value; });
            V.ff.push([fk.value, fc.value]);
          }
          FF_OPEN = false;
        } else if (v.hasAttribute('data-vff-del')) { (V.ff || []).splice(+v.getAttribute('data-vff-del'), 1); }
        else if (v.hasAttribute('data-vpreset') && D) vPreset(v.getAttribute('data-vpreset'), D);
        else if (v.hasAttribute('data-vreset')) { V = { cols: V.cols }; FF_OPEN = false; }
        vsave();
        vRefresh(true);
        return;
      }
      var t = e.target.closest ? e.target.closest('[data-add],[data-add-all],[data-pick],[data-remove],[data-import],[data-resend],[data-signout],[data-stop]') : null;
      if (!t) return;
      var inp = $('[data-add-q]');
      if (t.hasAttribute('data-add')) addText(R.t[t.getAttribute('data-add')].s);
      else if (t.hasAttribute('data-add-all')) addText(inp ? inp.value : '');
      else if (t.hasAttribute('data-pick')) {
        if (!inp) return;
        var parts = inp.value.split(/[,;]/);
        parts[parts.length - 1] = ' ' + R.t[t.getAttribute('data-pick')].s;
        inp.value = parts.join(',').replace(/^\s+/, '') + ', ';
        inp.focus();
        inp.dispatchEvent(new Event('input'));
      }
      else if (t.hasAttribute('data-remove')) {
        e.preventDefault();
        BP.follow(t.getAttribute('data-remove'), false).then(function (j) { if (j.ok) setFollow(j.follow); });
      } else if (t.hasAttribute('data-import')) {
        BP.post('follow', { tickers: (A.follow || []).concat(LOCAL) }).then(function (j) { if (j.ok) { setFollow(j.follow); toast('Your watchlist is on your account now.'); } });
      } else if (t.hasAttribute('data-resend')) {
        BP.post('resend', {}).then(function (j) { toast(j.ok ? 'Sent. Check your inbox (and spam folder).' : (j.error || "That didn't send."), j.ok ? '' : 'warn'); });
      } else if (t.hasAttribute('data-signout')) {
        BP.post('logout', {}).then(function () { location.href = '/me/'; });
      } else if (t.hasAttribute('data-stop')) {
        BP.post('unsubscribe', { t: q.get('stop') }).then(function () { clean(['stop']); A.alerts = { on: false, level: (A.alerts || {}).level }; draw(); toast('Emails stopped. Switch them back on here any time.'); });
      }
    });
    var on = $('[data-al-on]', box);
    if (on) on.addEventListener('change', function () {
      BP.post('alerts', { on: on.checked }).then(function (j) { if (j.ok) { A.alerts = j.alerts; draw(); toast(j.alerts.on ? 'Alerts on.' : 'Alerts off.'); } });
    });
    $$('input[name=lvl]', box).forEach(function (r) {
      r.addEventListener('change', function () { BP.post('alerts', { level: r.value }).then(function (j) { if (j.ok) { A.alerts = j.alerts; toast('Saved.'); } }); });
    });
    $$('form[data-acct]', box).forEach(function (f) {
      f.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var kind = f.getAttribute('data-acct'), out = $('.auth-msg', f), body = {};
        $$('input', f).forEach(function (i) { body[i.name] = i.type === 'checkbox' ? i.checked : i.value.trim(); });
        $('button[type=submit]', f).disabled = true;
        BP.post(kind, body).then(function (j) {
          $('button[type=submit]', f).disabled = false;
          if (!j.ok) { out.textContent = j.error || "That didn't work."; return; }
          if (kind === 'delete') { location.href = '/me/'; return; }
          if (kind === 'password') { out.className = 'auth-msg ok'; out.textContent = 'Password changed.'; f.reset(); return; }
          var after = body.alerts ? BP.post('alerts', { on: true }) : Promise.resolve();
          after.then(function () { return BP.me(true); }).then(function (a) { A = a; draw(); toast(j.mail ? 'Check your inbox to confirm the new address.' : 'Email saved.'); });
        });
      });
    });
  }

  function start() {
    notices();
    if (resetFlow()) return;
    BP.me().then(function (a) {
      if (!a || !a.signed_in) { $('[data-me-out]').hidden = false; return; }
      A = a;
      $('[data-me-out]').hidden = true;
      $('[data-me-in]').hidden = false;
      $('[data-me-in]').innerHTML = '<div class="me-skel"><div></div><div></div><div></div></div>';
      return getJSON(app.getAttribute('data-reads')).catch(function () { return { asof: null, t: {} }; }).then(function (res) {
        R = res;
        draw();
        if (PS) {
          PS.ready(function () { if (A.plays || A.signal) PS.adopt(A.plays, A.signal); draw(); });
          PS.onChange(function () { draw(); });
        }
        if (location.hash) { var el = document.getElementById(location.hash.slice(1)); if (el) el.scrollIntoView({ block: 'start' }); }
      });
    });
  }
  start();
})();
