/* prices.js — real price layer. Fetches /.netlify/functions/prices and caches
 * per-ticker quotes + recent real daily moves. Used by story cards (current
 * price + today's move) and the detail panel (real recent price action).
 * No-ops gracefully when the function isn't reachable (local demo). */
(function () {
  window.Q = window.Q || {};
  var ENDPOINT = '/.netlify/functions/prices';
  var cache = {};

  Q.prices = {
    available: false,
    get: function (t) { return cache[t] || null; },
    load: function (tickers) {
      tickers = (tickers || []).filter(function (t) { return t && Q.data.TICKERS[t]; });
      if (!tickers.length) return Promise.resolve(cache);
      var url = ENDPOINT + '?tickers=' + encodeURIComponent(tickers.join(','));
      return fetch(url).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (j) {
          if (j && j.prices) {
            Q.prices.available = true;
            Object.keys(j.prices).forEach(function (k) { cache[k] = j.prices[k]; });
          }
          return cache;
        });
    }
  };
})();
