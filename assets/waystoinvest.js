/* waystoinvest.js: the country picker on /guides/ways-to-invest/ (tools/qstrat/waystoinvest.py).
 * Without script every country shows, one after another. With it, one shows at a time: the one in
 * the address (#uk), else the last one picked, else a guess from the browser's language. */
(function () {
  var root = document.querySelector('[data-wti-root]');
  if (!root) return;
  var btns = root.querySelectorAll('[data-wti-pick]'), secs = document.querySelectorAll('[data-wti]');
  function show(k, remember) {
    var found = false;
    secs.forEach(function (s) { var on = s.getAttribute('data-wti') === k; s.hidden = !on; found = found || on; });
    if (!found) return false;
    btns.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-wti-pick') === k ? 'true' : 'false'); });
    if (remember) {
      try { localStorage.setItem('bp.country', k); } catch (e) { /* private mode */ }
      if (history.replaceState) history.replaceState(null, '', '#' + k);
    }
    return true;
  }
  btns.forEach(function (b) { b.addEventListener('click', function () { show(b.getAttribute('data-wti-pick'), true); }); });
  window.addEventListener('hashchange', function () { show(location.hash.slice(1), true); });
  var stored = null;
  try { stored = localStorage.getItem('bp.country'); } catch (e) { /* private mode */ }
  var lang = (navigator.language || '').toUpperCase();
  var guess = /-US$/.test(lang) ? 'us' : /-GB$/.test(lang) ? 'uk' : /-AU$/.test(lang) ? 'australia' : 'canada';
  if (!show(location.hash.slice(1)) && !(stored && show(stored))) show(guess);
  root.hidden = false;
})();
