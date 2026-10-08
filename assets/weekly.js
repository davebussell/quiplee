/* weekly.js: the "Send me the weekly" form on /weekly/ (and anywhere else it is
 * dropped in). Signs up for the free Saturday market-weather email through
 * /api/alerts/subscribe with weekly: true and no stocks. */
(function () {
  'use strict';
  document.querySelectorAll('[data-wk-form]').forEach(function (f) {
    var out = f.querySelector('[data-wk-msg]');
    function msg(t, ok) { out.textContent = t || ''; out.className = 'pt-msg' + (ok ? ' ok' : ''); }
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var email = f.email.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { msg("That email address doesn't look right."); return; }
      if (!f.consent.checked) { msg('Tick the box to agree to the emails.'); return; }
      var btn = f.querySelector('button[type=submit]');
      btn.disabled = true;
      msg('Sending…', true);
      fetch(f.getAttribute('data-api') + 'subscribe', {
        method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email: email, tickers: [], weekly: true, consent: true, src: f.getAttribute('data-where') || '' })
      }).then(function (r) { return r.json().catch(function () { return {}; }); }).then(function (j) {
        btn.disabled = false;
        if (!j.ok) { msg(j.error || "That didn't work. Try again."); return; }
        msg(j.mail ? 'Check your inbox: tap the link in the email from Be The Puck to start the weekly.'
          : "Got it. We'll email you a link to confirm as soon as emails switch on.", true);
        f.reset();
        try { if (window.gtag) window.gtag('event', 'sign_up', { method: 'weekly' }); } catch (e) { /* no analytics */ }
      }).catch(function () { btn.disabled = false; msg("Couldn't reach the server. Check your connection and try again."); });
    });
  });
})();
