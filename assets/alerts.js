/* alerts.js: the /alerts/ page. Sign up for free Start/Stop emails, or change or
 * stop them from the link in an email (?m=<token>). Talks to /api/alerts/
 * (netlify/functions/alerts.mjs); names come from data/tickers.json. */
(function () {
  'use strict';
  var app = document.getElementById('al-app');
  if (!app) return;
  var API = app.getAttribute('data-api');
  var STOCK = app.getAttribute('data-stock');
  var U = null, BY = {};
  var q = new URLSearchParams(location.search);

  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function msg(el, t, ok) { el.textContent = t || ''; el.className = 'pt-msg' + (ok ? ' ok' : ''); }
  function post(path, body) {
    return fetch(API + path, { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }); });
  }

  /** Symbols from free text: tickers (TD, TD.TO), page slugs or names. */
  function parse(text) {
    var out = [], bad = [];
    String(text || '').split(/[\n,;]+/).forEach(function (raw) {
      var w = raw.trim();
      if (!w) return;
      var u = w.toUpperCase();
      var sym = BY[u] || BY[u + '.TO'] || BY[w.toLowerCase()] || null;
      if (!sym) {
        // a name typed out: the first covered name that starts with it
        var low = w.toLowerCase();
        Object.keys(U ? U.names : {}).some(function (s) { if (U.names[s][1].toLowerCase().indexOf(low) === 0) { sym = s; return true; } return false; });
      }
      if (sym) { if (out.indexOf(sym) < 0) out.push(sym); } else bad.push(w);
    });
    return { syms: out, bad: bad };
  }

  function chips(syms, bad) {
    var box = $('[data-al-chips]');
    if (!box) return;
    box.innerHTML = syms.map(function (s) {
      var m = U.names[s], L = m[9];
      return '<a class="al-chip" href="' + esc(STOCK.replace('{s}', m[2])) + '">' + (L == null ? '' : '<span class="light-pill ' + (L ? 'start' : 'stop') + '"><i></i>' + (L ? 'Start' : 'Stop') + '</span>') +
        '<b>' + esc(m[0]) + '</b><span>' + esc(m[1]) + '</span></a>';
    }).join('') + (bad.length ? '<p class="small down">Not covered: ' + esc(bad.join(', ')) + '. <a href="' + esc(STOCK.replace('{s}/', '')) + '">See every name</a>.</p>' : '');
  }

  function signup() {
    var f = $('[data-al-form]'), ta = f.querySelector('textarea'), out = $('[data-al-msg]');
    function refresh() { var p = parse(ta.value); chips(p.syms, p.bad); }
    ta.addEventListener('input', refresh);
    var want = q.get('t');
    if (want) { var sym = BY[want.toLowerCase()] || BY[want.toUpperCase()]; if (sym) ta.value = U.names[sym][0] + (ta.value ? ', ' + ta.value : ''); }
    try {
      var wl = JSON.parse(localStorage.getItem('quiplee.watch.v1') || 'null');
      var items = (wl && wl.items || []).map(function (x) { return x.sym; }).filter(function (s) { return U.names[s]; });
      if (items.length) {
        var b = $('[data-al-watchlist]');
        b.hidden = false;
        b.textContent = 'Use the ' + items.length + ' stock' + (items.length === 1 ? '' : 's') + ' on my watchlist';
        b.addEventListener('click', function () { ta.value = items.map(function (s) { return U.names[s][0]; }).join(', '); refresh(); });
        if (q.get('from') === 'watchlist') { ta.value = items.map(function (s) { return U.names[s][0]; }).join(', '); }
      }
    } catch (e) { /* storage off */ }
    refresh();
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var p = parse(ta.value), email = f.email.value.trim();
      var weekly = !!(f.weekly && f.weekly.checked);
      if (!p.syms.length && !weekly) { msg(out, 'Add at least one stock Be The Puck covers.'); return; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { msg(out, "That email address doesn't look right."); return; }
      if (!f.consent.checked) { msg(out, 'Tick the box to agree to the emails.'); return; }
      var btn = f.querySelector('button[type=submit]');
      btn.disabled = true;
      msg(out, 'Sending…', true);
      post('subscribe', { email: email, tickers: p.syms, weekly: weekly, consent: true }).then(function (j) {
        btn.disabled = false;
        if (!j.ok) { msg(out, j.error || "That didn't work. Try again."); return; }
        msg(out, j.mail ? 'Check your inbox: tap the link in the email from Be The Puck to start your alerts.'
          : "Got it. We'll email you a link to confirm as soon as alerts switch on.", true);
        f.reset(); chips([], []);
        try { if (window.gtag) window.gtag('event', 'sign_up', { method: 'alerts' }); } catch (e) { /* no analytics */ }
      }).catch(function () { btn.disabled = false; msg(out, "Couldn't reach the server. Check your connection and try again."); });
    });
  }

  function manageView(tok) {
    var box = $('[data-al-manage]');
    box.hidden = false;
    $('[data-al-signup]').hidden = true;
    var unsub = q.get('unsub') === '1';
    box.innerHTML = '<p class="muted">Loading your alerts…</p>';
    fetch(API + 'manage?t=' + encodeURIComponent(tok)).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.tickers) { box.innerHTML = '<p>' + esc(j.error || 'This link no longer works.') + '</p>'; $('[data-al-signup]').hidden = false; return; }
      var names = j.tickers.filter(function (s) { return U.names[s]; }).map(function (s) { return U.names[s][0]; });
      box.innerHTML = (q.get('confirmed') ? '<p class="al-ok"><b>You\'re set.</b> We\'ll email ' + esc(j.email) + (j.tickers.length ? ' when the light flips on these stocks' : '') + (j.weekly ? (j.tickers.length ? ', and' : '') + ' the weekly market weather on Saturdays' : '') + '.</p>' : '') +
        (unsub ? '<p><b>Unsubscribe ' + esc(j.email) + '?</b> You won\'t get any more alerts.</p><p><button type="button" class="btn primary" data-al-unsub>Unsubscribe</button> <a href="?m=' + esc(encodeURIComponent(tok)) + '">Change my stocks instead</a></p><p class="pt-msg" data-al-umsg></p>'
          : '<h2 class="h3">Your alerts for ' + esc(j.email) + '</h2><form class="pt-form" data-al-edit novalidate><label>Stocks to follow<textarea name="tickers" rows="3">' + esc(names.join(', ')) + '</textarea></label>' +
            '<div class="al-chips" data-al-chips></div><label class="pt-check"><input type="checkbox" name="weekly"' + (j.weekly ? ' checked' : '') + '> The weekly market weather on Saturdays</label><div class="hero-links"><button class="btn primary" type="submit">Save my stocks</button><button type="button" class="btn" data-al-unsub>Unsubscribe</button></div>' +
            '<p class="pt-msg" role="alert" data-al-umsg></p></form>');
      var ta = box.querySelector('textarea');
      if (ta) {
        var refresh = function () { var p = parse(ta.value); chips(p.syms, p.bad); };
        ta.addEventListener('input', refresh); refresh();
        box.querySelector('[data-al-edit]').addEventListener('submit', function (ev) {
          ev.preventDefault();
          var p = parse(ta.value);
          var wk = box.querySelector('input[name=weekly]');
          post('update', { t: tok, tickers: p.syms, weekly: !!(wk && wk.checked) }).then(function (r) { msg($('[data-al-umsg]'), r.ok ? 'Saved. ' + r.tickers.length + ' stocks on your list' + (r.weekly ? ', plus the weekly.' : '.') : (r.error || "That didn't save."), r.ok); });
        });
      }
      var ub = box.querySelector('[data-al-unsub]');
      ub.addEventListener('click', function () {
        post('unsubscribe', { t: tok }).then(function (r) {
          box.innerHTML = r.ok ? '<p><b>Unsubscribed.</b> You won\'t get any more alerts. You can sign up again any time.</p>' : '<p>' + esc(r.error || "That didn't work.") + '</p>';
        });
      });
    }).catch(function () { box.innerHTML = '<p>Couldn\'t load your alerts. Refresh to try again.</p>'; });
  }

  fetch(app.getAttribute('data-universe')).then(function (r) { return r.json(); }).then(function (j) {
    U = j;
    Object.keys(j.names).forEach(function (s) { var m = j.names[s]; BY[s] = s; BY[m[0].toUpperCase()] = BY[m[0].toUpperCase()] || s; BY[m[2]] = s; });
    if (q.get('expired')) { var o = $('[data-al-msg]'); msg(o, 'That link has expired or was already used. Sign up again below.'); }
    if (q.get('m')) manageView(q.get('m'));
    signup();
  }).catch(function () { msg($('[data-al-msg]'), "Couldn't load the list of stocks. Refresh to try again."); });
})();
