/* members.js: the sign-in messages on locked pages, the signed-in state on
 * /members/, and the PayPal subscription button (only when the page carries a
 * PayPal client id and plan, set at build time). The member cookie itself is
 * HttpOnly; this script only asks /api/member/me whether it is there. */
(function () {
  'use strict';
  var params = new URLSearchParams(location.search);
  var MSG = {
    bad: ["That password didn't work. Check it and try again.", false],
    wait: ['Too many tries from this connection. Wait a few minutes, then try again.', false],
    out: ["You're signed out.", true],
    lapsed: ['Your membership has ended. Join again below to pick up where you left off.', false],
    off: ['Sign-in is not switched on yet.', false],
    expired: ['That sign-in link has expired. Ask for a new one below.', false],
    sent: ['If that email has an active membership, a sign-in link is on its way.', true]
  };
  var m = MSG[params.get('login')];
  if (m) {
    [].forEach.call(document.querySelectorAll('[data-login-msg]'), function (el) {
      el.textContent = m[0];
      el.classList.toggle('ok', m[1]);
      el.hidden = false;
    });
    var pw = document.querySelector('.lock-form input[type=password]');
    if (pw && !m[1]) pw.focus();
    params.delete('login');
    var q = params.toString();
    history.replaceState(null, '', location.pathname + (q ? '?' + q : '') + location.hash);
  }

  var state = document.querySelector('[data-mem-state]');
  if (state && location.protocol !== 'file:') {
    fetch('/api/member/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j && j.member) state.hidden = false; })
      .catch(function () {});
  }

  // PayPal subscription button
  var box = document.getElementById('pp-box');
  if (!box) return;
  var say = box.querySelector('[data-pp-msg]');
  function tell(t, ok) { say.textContent = t; say.style.color = ok ? 'var(--in)' : 'var(--out)'; say.hidden = false; }
  var s = document.createElement('script');
  s.src = 'https://www.paypal.com/sdk/js?client-id=' + encodeURIComponent(box.getAttribute('data-client')) + '&vault=true&intent=subscription';
  s.onerror = function () { tell("PayPal didn't load. Check your connection or ad blocker and refresh."); };
  s.onload = function () {
    /* global paypal */
    paypal.Buttons({
      style: { shape: 'rect', color: 'gold', layout: 'vertical', label: 'subscribe' },
      createSubscription: function (data, actions) {
        return actions.subscription.create({ plan_id: box.getAttribute('data-plan') });
      },
      onApprove: function (data) {
        tell('Confirming your subscription…', true);
        return fetch(box.getAttribute('data-api'), {
          method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subscriptionID: data.subscriptionID })
        }).then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
          .then(function (res) {
            if (res[0] && res[1].ok) { location.href = '/picks/?welcome=1'; return; }
            tell((res[1] && res[1].error) || 'We could not confirm the subscription yet. It can take a minute: refresh this page shortly.');
          })
          .catch(function () { tell('We could not reach Be The Puck to confirm. Your PayPal subscription is safe; refresh in a minute.'); });
      },
      onError: function () { tell('PayPal reported a problem. Nothing was charged; please try again.'); }
    }).render('#pp-buttons');
  };
  document.head.appendChild(s);
})();
