/* auth.js — local cookie session gate (client-side demo).
 * Sign in sets a `q_session` cookie; the app reads it on load. For production,
 * validate server-side and set an HttpOnly cookie (a Netlify Function). */
(function () {
  window.Q = window.Q || {};
  var COOKIE = 'q_session', MAX_AGE = 60 * 60 * 24 * 7;

  function setCookie(v) {
    var secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = COOKIE + '=' + encodeURIComponent(v) + '; Max-Age=' + MAX_AGE + '; Path=/; SameSite=Lax' + secure;
  }
  function getCookie() { var m = document.cookie.match('(?:^|; )' + COOKIE + '=([^;]*)'); return m ? decodeURIComponent(m[1]) : null; }
  function del() { document.cookie = COOKIE + '=; Max-Age=0; Path=/; SameSite=Lax'; }
  function enc(o) { return btoa(unescape(encodeURIComponent(JSON.stringify(o)))).replace(/=+$/, ''); }
  function dec(s) { try { return JSON.parse(decodeURIComponent(escape(atob(s)))); } catch (e) { return null; } }
  function now() { return Math.floor(Date.now() / 1000); }

  Q.auth = {
    login: function (email, password) {
      email = String(email || '').trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return { ok: false, error: 'Enter a valid email.' };
      if (!password) return { ok: false, error: 'Password is required.' };
      var s = { email: email, exp: now() + MAX_AGE };
      setCookie(enc(s));
      return { ok: true, session: s };
    },
    getSession: function () { var r = getCookie(); if (!r) return null; var s = dec(r); if (!s || !s.exp || s.exp < now()) { del(); return null; } return s; },
    logout: function () { del(); }
  };
})();
