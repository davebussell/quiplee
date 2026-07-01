/* outcomes.js — joins story timestamps to the real daily price series so
 * lookback / similar / the scoreboard use ACTUAL returns, not estimates.
 *
 * For each story: baseline = last close at/before publication; d1 = next
 * trading day's close vs baseline; d5 = five trading days out. Partial ages
 * get what's available (d1 only) and stay "developing" for the rest.
 * Only stories from the real feed (s.real) are ever overwritten. */
(function () {
  window.Q = window.Q || {};

  function computeFromSeries(ts, series) {
    if (!series || series.length < 2) return null;
    var idx = -1;
    for (var i = 0; i < series.length; i++) { if (series[i].t <= ts) idx = i; else break; }
    if (idx < 0) return null;                       // story predates the series
    var base = series[idx].c;
    if (!base) return null;
    var d1 = (idx + 1 < series.length) ? round1((series[idx + 1].c - base) / base * 100) : null;
    var d5 = (idx + 5 < series.length) ? round1((series[idx + 5].c - base) / base * 100) : null;
    if (d1 == null) return null;                    // too fresh — still developing
    return { d1: d1, d5: d5, real: true };
  }
  function round1(n) { return Math.round(n * 10) / 10; }

  Q.outcomes = {
    /** Attach realized outcomes to every real story whose primary ticker has a price series. */
    apply: function (stories) {
      var changed = 0;
      (stories || []).forEach(function (s) {
        if (!s.real || !s.tickers || !s.tickers.length) return;
        var p = Q.prices.get(s.tickers[0]);
        if (!p || !p.series) return;
        var o = computeFromSeries(s.ts, p.series);
        if (o) { s.outcome = o; changed++; }
      });
      return changed;
    },

    /** Calibration: of real, revenue-impacting, directional stories with a realized d1,
     *  how often did the anticipated direction match the actual move? */
    scoreboard: function (stories) {
      var n = 0, hits = 0;
      (stories || []).forEach(function (s) {
        if (!s.real || !s.outcome || !s.outcome.real || !s.impact) return;
        if (!s.impact.revenue || s.impact.dir === 'neutral') return;
        var d1 = s.outcome.d1;
        if (d1 == null || d1 === 0) return;
        n++;
        if ((s.impact.dir === 'bullish' && d1 > 0) || (s.impact.dir === 'bearish' && d1 < 0)) hits++;
      });
      return { n: n, hits: hits, rate: n ? Math.round(hits / n * 100) : null };
    },

    compute: computeFromSeries
  };
})();
