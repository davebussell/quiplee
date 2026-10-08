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
      // SPY (the S&P 500) is the yardstick each story's move is measured against
      if (tickers.indexOf('SPY') === -1) tickers.push('SPY');
      var batches = [];
      for (var i = 0; i < tickers.length; i += 12) batches.push(tickers.slice(i, i + 12));
      return Promise.all(batches.map(function (b) {
        return fetch(ENDPOINT + '?tickers=' + encodeURIComponent(b.join(','))).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then(function (j) {
            if (j && j.prices) {
              Q.prices.available = true;
              Object.keys(j.prices).forEach(function (k) { cache[k] = j.prices[k]; });
            }
          });
      })).then(function () { return cache; });
    }
  };
})();
