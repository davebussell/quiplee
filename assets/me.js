/* me.js: My Puck (/me/). Signed out, the page shows the sign-up widget (account.js).
 * Signed in, it draws the dashboard from /api/account/me (the account) and
 * data/reads.json (every covered name's light and read): the stocks you follow,
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
  function pill(L) {
    if (L == null) return '<span class="light-pill">–</span>';
    return '<span class="light-pill ' + (L ? 'start' : 'stop') + '"><i aria-hidden="true"></i>' + (L ? 'Start' : 'Stop') + '</span>';
  }
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
  function followRows() {
    var list = (A.follow || []).filter(function (s) { return R.t[s]; });
    if (!list.length) {
      return '<div class="me-empty"><p><b>Follow a few stocks to get started.</b> You\'ll see each one\'s light here, and get an email the evening it flips.</p>' +
        '<div class="me-chips">' + POPULAR.filter(function (s) { return R.t[s]; }).map(function (s) { return '<button type="button" class="chip-btn" data-add="' + esc(s) + '">+ ' + esc(R.t[s].s) + '</button>'; }).join('') + '</div></div>';
    }
    return '<ul class="me-list">' + list.map(function (s) {
      var t = R.t[s], fresh = t.since && R.asof && daysBetween(t.since, R.asof) <= 7;
      return '<li><a class="me-row" href="' + esc(STOCK.replace('{u}', t.u)) + '">' +
        '<span class="mp-sym"><b>' + esc(t.s) + '</b><span>' + esc(t.n) + '</span></span>' + pill(t.L) +
        '<span class="mp-bar">' + bar(t.k, t.of) + '<span>' + t.k + '/' + t.of + '</span></span>' +
        '<span class="mp-px mono">' + money(t.p, t.cur) + (t.d1 != null ? ' <small class="' + cls(t.d1) + '">' + pct(t.d1) + '</small>' : '') + '</span>' +
        '<span class="mp-since">' + (fresh ? '<b class="me-new">Flipped ' + esc(day(t.since)) + '</b>' : t.since ? 'since ' + esc(day(t.since)) : '') + '</span></a>' +
        '<button type="button" class="me-x" data-remove="' + esc(s) + '" aria-label="Stop following ' + esc(t.s) + '">×</button></li>';
    }).join('') + '</ul>';
  }
  function kpis() {
    var list = (A.follow || []).filter(function (s) { return R.t[s]; });
    var on = list.filter(function (s) { return R.t[s].L === 1; });
    var flipped = list.filter(function (s) { var t = R.t[s]; return t.since && daysBetween(t.since, R.asof) <= 7; });
    var al = A.alerts || {};
    var mailState = !A.email ? ['Add your email', 'warn'] : !A.email_ok ? ['Confirm your email', 'warn'] : al.on ? ['On', 'on'] : ['Off', ''];
    var k = 0, n = 0;
    list.forEach(function (s) { k += R.t[s].k || 0; n += R.t[s].of || 0; });
    var avg = n ? Math.round(100 * k / n) : null;
    return '<div class="me-kpis">' +
      '<div class="card tile"><span class="tile-label">Your stocks on Start</span><span class="tile-value"><b data-count="' + on.length + '">' + on.length + '</b><small> of ' + list.length + '</small></span>' + bar(on.length, list.length || 1) + '<span class="tile-note">' + (list.length ? (list.length - on.length) + ' on Stop' : 'Follow a few to begin') + '</span></div>' +
      '<div class="card tile"><span class="tile-label">Flipped in the last week</span><span class="tile-value">' + flipped.length + '</span><span class="tile-note">' + (flipped.length ? flipped.slice(0, 4).map(function (s) { return esc(R.t[s].s); }).join(', ') : 'No changes on your list') + '</span></div>' +
      '<div class="card tile"><span class="tile-label">Plays holding your stocks</span><span class="tile-value">' + (avg == null ? '–' : avg + '<small> of 100</small>') + '</span><span class="tile-note">' + (avg == null ? 'Follow a few to see it' : 'On average, across your list') + '</span></div>' +
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
        '<label class="radio"><input type="radio" name="lvl" value="light"' + (al.level === 'light' ? ' checked' : '') + '><span><b>Start/Stop flips</b><small>Free for good</small></span></label>' +
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
    if (!r) return 'Using the site\'s rule: every play, Start at 60%, Stop at 40%.';
    var names = { all: 'Every play', best: 'Best record', protect: 'Crash protection', trend: 'Trend riders', dip: 'Dip buyers', custom: 'Your own pick of plays' };
    return (names[r.preset] || 'Your plays') + ': Start at ' + Math.round(r.on * 100) + '%, Stop at ' + Math.round(r.off * 100) + '%.';
  }
  function toolsCard() {
    var m = A.member || {};
    var badge = m.kind === 'paid' ? '<span class="tag live">Member</span>' : m.active ? '<span class="tag mem">Free until ' + esc(FREE) + '</span>' : '<span class="tag">$5 a month</span>';
    var tools = [['/picks/', 'Top picks', 'Five rule-based picks, reviewed every Friday.'], ['/rules/', 'Your own rules', rulesLine()],
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
      (A.email ? '' : '<label class="auth-check"><input type="checkbox" name="alerts"><span>Email me when the Start/Stop light flips on stocks I follow. I can stop any time.</span></label>') +
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
  function suggest(qs) {
    qs = qs.trim().toUpperCase();
    if (!qs) return [];
    var out = [];
    Object.keys(R.t).forEach(function (s) {
      var t = R.t[s], sh = t.s.toUpperCase(), nm = t.n.toUpperCase();
      var score = sh === qs || s === qs ? 0 : sh.indexOf(qs) === 0 ? 1 : nm.indexOf(qs) === 0 ? 2 : nm.indexOf(' ' + qs) >= 0 ? 3 : -1;
      if (score >= 0 && (A.follow || []).indexOf(s) < 0) out.push([score, sh.length, s]);
    });
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out.slice(0, 7).map(function (x) { return x[2]; });
  }
  function draw() {
    var box = $('[data-me-in]');
    var local = [];
    try { var v = JSON.parse(localStorage.getItem('quiplee.watch.v1') || 'null'); local = ((v && v.items) || []).map(function (x) { return x.sym; }).filter(function (s) { return R.t[s] && (A.follow || []).indexOf(s) < 0; }); } catch (e) { /* storage off */ }
    box.innerHTML =
      '<div class="me-top"><div><p class="eyebrow">My Puck</p><h1 class="h1 me-hi">' + greeting() + ', <em>' + esc(A.name) + '</em></h1>' +
      '<p class="muted">The ' + esc(day(R.asof)) + ' close · ' + (A.follow || []).length + ' stock' + ((A.follow || []).length === 1 ? '' : 's') + ' followed</p></div>' +
      '<div class="hero-links"><a class="btn primary glow" href="/theory/">Theory tester</a><a class="btn" href="/#screen">Screener</a></div></div>' +
      notice() + kpis() +
      '<div class="me-grid"><section class="card me-card me-stocks" id="stocks"><div class="me-card-h"><h2 class="h3">Your stocks</h2><span class="small muted">' + (A.follow || []).length + ' of 100</span></div>' +
      '<div class="me-add"><input type="search" data-add-q placeholder="Follow a stock: NVDA, Shopify, gold…" autocomplete="off" aria-label="Follow a stock"><div class="me-sug" data-sug hidden></div></div>' +
      (local.length ? '<p class="small"><button type="button" class="linkish" data-import>Follow the ' + local.length + ' stock' + (local.length === 1 ? '' : 's') + ' on this browser\'s watchlist</button></p>' : '') +
      '<div data-rows>' + followRows() + '</div></section>' +
      '<div class="me-side">' + alertsCard() + theoryCard() + '</div></div>' +
      toolsCard() + accountCard();
    box.hidden = false;
    wire(box, local);
  }
  function setFollow(list) { A.follow = list; $('[data-rows]').innerHTML = followRows(); draw(); }
  function wire(box, local) {
    var input = $('[data-add-q]', box), sug = $('[data-sug]', box);
    function add(sym) {
      BP.follow(sym, true).then(function (j) {
        if (!j.ok) return toast(j.error || "Couldn't add that.", 'warn');
        setFollow(j.follow); toast('Following ' + R.t[sym].s + '.');
        var i = $('[data-add-q]'); if (i) i.focus();
      });
    }
    input.addEventListener('input', function () {
      var list = suggest(input.value);
      sug.hidden = !list.length;
      sug.innerHTML = list.map(function (s) { var t = R.t[s]; return '<button type="button" data-add="' + esc(s) + '">' + pill(t.L) + '<b>' + esc(t.s) + '</b><span>' + esc(t.n) + '</span></button>'; }).join('');
    });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { var l = suggest(input.value); if (l.length) add(l[0]); } });
    box.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('[data-add],[data-remove],[data-import],[data-resend],[data-signout],[data-stop]') : null;
      if (!t) return;
      if (t.hasAttribute('data-add')) add(t.getAttribute('data-add'));
      else if (t.hasAttribute('data-remove')) {
        e.preventDefault();
        BP.follow(t.getAttribute('data-remove'), false).then(function (j) { if (j.ok) setFollow(j.follow); });
      } else if (t.hasAttribute('data-import')) {
        BP.post('follow', { tickers: (A.follow || []).concat(local) }).then(function (j) { if (j.ok) { setFollow(j.follow); toast('Your watchlist is on your account now.'); } });
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
        if (location.hash) { var el = document.getElementById(location.hash.slice(1)); if (el) el.scrollIntoView({ block: 'start' }); }
      });
    });
  }
  start();
})();
