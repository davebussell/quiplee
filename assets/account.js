/* account.js: the Be The Puck account on every page.
 *  - the header button (name and initial once signed in) and [data-signed-in] / [data-signed-out] bits
 *  - the sign-up / sign-in / forgot-password widget in any [data-auth] slot:
 *      data-auth-mode="signup|login"  which form shows first
 *      data-auth-next="reload|/path/" where to go after (default: reload)
 *      data-auth-context="member|alerts|me|theory" small wording changes
 *  - window.BPAuth: name(), signedIn(), me() and follow(sym, on)
 * Talks to /api/account/ (netlify/functions/account.mjs). The session cookie is
 * HttpOnly; the readable bp_name cookie only tells pages who is signed in. */
(function () {
  'use strict';
  var API = '/api/account/';
  var FREE = 'January 1, 2027';

  function cookie(name) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function post(path, body) {
    return fetch(API + path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j._status = r.status; return j; }); });
  }
  var mePromise = null;
  var BP = window.BPAuth = {
    name: function () { return cookie('bp_name'); },
    signedIn: function () { return !!cookie('bp_name'); },
    me: function (fresh) {
      if (location.protocol === 'file:') return Promise.resolve({ signed_in: false });
      if (!mePromise || fresh) mePromise = fetch(API + 'me', { credentials: 'same-origin', cache: 'no-store' }).then(function (r) { return r.json(); }).catch(function () { return { signed_in: false }; });
      return mePromise;
    },
    follow: function (sym, on) { return post('follow', on === false ? { remove: sym } : { add: sym }); },
    post: post
  };

  // ------------------------------------------------------------ header and signed-in bits
  function paintHeader() {
    var n = BP.name();
    [].forEach.call(document.querySelectorAll('[data-acct-btn]'), function (b) {
      b.classList.toggle('in', !!n);
      var lab = b.querySelector('[data-acct-label]'), ava = b.querySelector('.acct-ava');
      if (lab) lab.textContent = n ? 'My Puck' : 'Sign in';
      if (ava) ava.textContent = n ? n.charAt(0).toUpperCase() : '';
      b.setAttribute('title', n ? 'Signed in as ' + n : 'Sign in or create a free account');
    });
    [].forEach.call(document.querySelectorAll('[data-signed-out]'), function (el) { el.hidden = !!n; });
    [].forEach.call(document.querySelectorAll('[data-signed-in]'), function (el) { el.hidden = !n; });
  }

  // ------------------------------------------------------------ the widget
  var COPY = {
    theory: { go: 'Create my free account', lead: 'Follow the stocks you test and get an email when their light flips.' },
    member: { go: 'Create my free account', lead: 'Member tools open straight away and stay free until ' + FREE + '.' },
    alerts: { go: 'Create my free account', lead: 'Follow your stocks and get an email when the light flips.' },
    me: { go: 'Create my free account', lead: 'One account for your stocks, your emails and every member tool.' }
  };
  function watchSyms() {
    try { var v = JSON.parse(localStorage.getItem('quiplee.watch.v1') || 'null'); return ((v && v.items) || []).map(function (x) { return x.sym; }).slice(0, 40); } catch (e) { return []; }
  }
  function widget(slot) {
    if (slot._auth) return;
    slot._auth = true;
    var ctx = slot.getAttribute('data-auth-context') || 'me', c = COPY[ctx] || COPY.me;
    var next = slot.getAttribute('data-auth-next') || 'reload';
    var uid = 'au' + Math.random().toString(36).slice(2, 7);
    slot.innerHTML =
      '<div class="auth">' +
      '<div class="auth-tabs" role="tablist"><button type="button" role="tab" data-tab="signup">Create free account</button><button type="button" role="tab" data-tab="login">Sign in</button></div>' +
      '<form class="auth-form" data-form="signup" novalidate>' +
      '<label for="' + uid + 'e">Email</label><input id="' + uid + 'e" name="email" type="email" autocomplete="email" required placeholder="you@example.com">' +
      '<label for="' + uid + 'p">Password</label><div class="pw-row"><input id="' + uid + 'p" name="password" type="password" autocomplete="new-password" minlength="8" required placeholder="At least 8 characters"><button type="button" class="pw-eye" aria-label="Show password">Show</button></div>' +
      '<label for="' + uid + 'n">Username <span class="opt">optional, shown when you sign in</span></label><input id="' + uid + 'n" name="name" autocomplete="username" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" placeholder="We\'ll make one from your email">' +
      '<label class="auth-check"><input type="checkbox" name="alerts"><span>Email me when the Start/Stop light flips on stocks I follow. I can stop any time.</span></label>' +
      '<button class="btn primary glow" type="submit">' + esc(c.go) + '</button>' +
      '<p class="auth-msg" role="alert"></p>' +
      '<p class="auth-fine">' + esc(c.lead) + ' From ' + FREE + ', member tools are $5 a month; the screener, the Theory tester and Start/Stop emails stay free.</p>' +
      '</form>' +
      '<form class="auth-form" data-form="login" novalidate hidden>' +
      '<label for="' + uid + 'i">Email or username</label><input id="' + uid + 'i" name="id" autocomplete="username" required>' +
      '<label for="' + uid + 'q">Password</label><div class="pw-row"><input id="' + uid + 'q" name="password" type="password" autocomplete="current-password" required><button type="button" class="pw-eye" aria-label="Show password">Show</button></div>' +
      '<button class="btn primary" type="submit">Sign in</button>' +
      '<p class="auth-msg" role="alert"></p>' +
      '<p class="auth-fine"><button type="button" class="linkish" data-goto="forgot">Forgot your password?</button></p>' +
      '</form>' +
      '<form class="auth-form" data-form="forgot" novalidate hidden>' +
      '<p class="small muted">Enter your email or username. If the account has an email, we\'ll send a link to choose a new password.</p>' +
      '<label for="' + uid + 'f">Email or username</label><input id="' + uid + 'f" name="id" autocomplete="username" required>' +
      '<button class="btn primary" type="submit">Email me a reset link</button>' +
      '<p class="auth-msg" role="alert"></p>' +
      '<p class="auth-fine"><button type="button" class="linkish" data-goto="login">Back to sign in</button></p>' +
      '</form></div>';
    var tabs = slot.querySelectorAll('[data-tab]'), forms = slot.querySelectorAll('[data-form]');
    function show(which) {
      [].forEach.call(forms, function (f) { f.hidden = f.getAttribute('data-form') !== which; });
      [].forEach.call(tabs, function (t) { t.setAttribute('aria-selected', String(t.getAttribute('data-tab') === which || (which === 'forgot' && t.getAttribute('data-tab') === 'login'))); });
    }
    [].forEach.call(tabs, function (t) { t.addEventListener('click', function () { show(t.getAttribute('data-tab')); var i = slot.querySelector('[data-form="' + t.getAttribute('data-tab') + '"] input'); if (i) i.focus(); }); });
    [].forEach.call(slot.querySelectorAll('[data-goto]'), function (b) { b.addEventListener('click', function () { show(b.getAttribute('data-goto')); }); });
    [].forEach.call(slot.querySelectorAll('.pw-eye'), function (b) {
      b.addEventListener('click', function () { var i = b.previousElementSibling; var on = i.type === 'password'; i.type = on ? 'text' : 'password'; b.textContent = on ? 'Hide' : 'Show'; });
    });
    show(slot.getAttribute('data-auth-mode') === 'login' ? 'login' : 'signup');
    [].forEach.call(forms, function (f) {
      f.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var kind = f.getAttribute('data-form'), out = f.querySelector('.auth-msg'), btn = f.querySelector('button[type=submit]');
        var body = {};
        [].forEach.call(f.querySelectorAll('input'), function (i) { body[i.name] = i.type === 'checkbox' ? i.checked : i.value.trim(); });
        function say(t, ok) { out.textContent = t || ''; out.className = 'auth-msg' + (ok ? ' ok' : ''); }
        if (kind === 'signup') {
          if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email)) return say("That email address doesn't look right.");
          if (String(body.password).length < 8) return say('Passwords need at least 8 characters.');
          if (body.name && !/^[A-Za-z0-9_]{3,20}$/.test(body.name)) return say('Usernames are 3 to 20 letters, numbers or underscores.');
          var w = watchSyms(); if (w.length) body.follow = w;
        } else if (kind === 'login' && (!body.id || !body.password)) return say('Enter your email or username and your password.');
        else if (kind === 'forgot' && !body.id) return say('Enter your email or username.');
        btn.disabled = true;
        say(kind === 'signup' ? 'Setting up your account…' : 'One moment…', true);
        post(kind, body).then(function (j) {
          btn.disabled = false;
          if (!j.ok) return say(j.error || "That didn't work. Try again.");
          if (kind === 'forgot') return say(j.mail === false ? "Emails aren't switched on yet, so we can't send a reset link today. Try again soon." : 'If that account has an email, a reset link is on its way. Check your inbox.', true);
          say(kind === 'signup' ? 'Welcome, ' + j.name + '. Opening…' : 'Signed in. Opening…', true);
          paintHeader();
          setTimeout(function () { if (next === 'reload') location.reload(); else location.href = next; }, 350);
        }).catch(function () { btn.disabled = false; say("Couldn't reach the server. Check your connection and try again."); });
      });
    });
  }

  function init() {
    paintHeader();
    [].forEach.call(document.querySelectorAll('[data-auth]'), widget);
  }
  BP.mount = widget;
  BP.paint = paintHeader;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
