/* live.js — pulls real headlines from the Netlify ingestion function and enriches
 * each one with Quiplee's own brain: classifyType() -> topic map -> evaluate().
 * Returns scored stories in the same shape as the synthetic generator. If the
 * function isn't reachable (e.g. local `serve` with no functions), the caller
 * falls back to demo mode — this module just rejects. */
(function () {
  window.Q = window.Q || {};
  var ENDPOINT = '/.netlify/functions/news';

  function hash(str) { var h = 2166136261 >>> 0; for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function keyOf(raw) { return (raw.link || '') + '|' + (raw.headline || '').toLowerCase().slice(0, 90); }

  function topicsFor(tickers, hint) {
    var set = {};
    (tickers || []).forEach(function (s) { var m = Q.data.TICKERS[s]; if (m) m.topics.forEach(function (t) { set[t] = 1; }); });
    if (hint) set[hint] = 1;
    return Object.keys(set);
  }

  function enrich(raw) {
    var tickers = (raw.tickers || []).filter(function (t) { return Q.data.TICKERS[t]; });
    if (!tickers.length) tickers = raw.tickers || [];
    var story = {
      id: 'l-' + hash(keyOf(raw)).toString(36),
      src: raw.src || 'News',
      type: raw.origin === 'sec' ? 'Regulatory' : Q.data.classifyType(raw.headline),
      tickers: tickers,
      topics: topicsFor(raw.tickers, raw.topicHint),
      headline: raw.headline,
      ts: raw.ts || Date.now(),
      ago: 0, outcome: null, live: true, link: raw.link || null
    };
    story.impact = Q.data.evaluate(story);
    return story;
  }

  Q.live = {
    available: false,
    fetchStories: function (tickers, topics) {
      var names = tickers.map(function (s) { return s + ':' + (Q.data.TICKERS[s] ? Q.data.TICKERS[s].name : s); }).join(';');
      var url = ENDPOINT +
        '?tickers=' + encodeURIComponent(tickers.join(',')) +
        '&topics=' + encodeURIComponent(topics.join(',')) +
        '&names=' + encodeURIComponent(names);
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        if (!j || !j.stories) throw new Error('bad payload');
        Q.live.available = true;
        return j.stories.map(enrich).filter(function (s) { return s.headline && s.headline.length > 8; });
      });
    }
  };
})();
