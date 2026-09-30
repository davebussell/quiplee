/* analysts.js — the accountability layer. Captures WHO is behind each story
 * (named analyst firm from the headline, SEC EDGAR for filings, else the
 * publisher), groups their coverage, and computes a public batting average:
 * of their revenue-impacting directional calls that have aged into a realized
 * next-day move, how many called the direction right. Same grading rule as the
 * model scoreboard — one standard for everyone, including us. */
(function () {
  window.Q = window.Q || {};

  var FIRMS = [
    'Morgan Stanley', 'Goldman Sachs', 'Goldman', 'J.P. Morgan', 'JPMorgan', 'Bank of America', 'BofA',
    'Citigroup', 'Citi', 'Wedbush', 'UBS', 'Barclays', 'Jefferies', 'Piper Sandler', 'Bernstein',
    'Evercore', 'Oppenheimer', 'Mizuho', 'Truist', 'Wells Fargo', 'Deutsche Bank', 'HSBC',
    'Loop Capital', 'Rosenblatt', 'KeyBanc', 'Raymond James', 'Stifel', 'Needham', 'Benchmark',
    'Wolfe Research', 'Melius', 'TD Cowen', 'Cantor', 'BTIG', 'Baird', 'William Blair',
    "Moody's", 'S&P Global', 'Fitch'
  ];
  var CANON = { 'Goldman': 'Goldman Sachs', 'BofA': 'Bank of America', 'Citi': 'Citigroup', 'J.P. Morgan': 'JPMorgan' };

  function extract(story) {
    if (story.analyst) return story.analyst;
    var h = story.headline || '', found = null;
    for (var i = 0; i < FIRMS.length; i++) {
      if (h.indexOf(FIRMS[i]) !== -1) { found = { name: CANON[FIRMS[i]] || FIRMS[i], kind: 'analyst' }; break; }
    }
    if (!found && story.src === 'SEC EDGAR') found = { name: 'SEC EDGAR', kind: 'filing' };
    if (!found) found = { name: story.src || 'Unknown', kind: 'source' };
    story.analyst = found;
    return found;
  }

  /** Group all stories by who's behind them; grade each voice's directional record. */
  function profiles(stories) {
    var map = {};
    (stories || []).forEach(function (s) {
      if (!s.impact) return;
      var a = extract(s);
      var p = map[a.name] || (map[a.name] = { name: a.name, kind: a.kind, stories: [], calls: 0, graded: 0, hits: 0, last: 0 });
      p.stories.push(s);
      if (s.ts > p.last) p.last = s.ts;
      if (s.impact.revenue && s.impact.dir !== 'neutral') {
        p.calls++;
        if (s.outcome && s.outcome.real && s.outcome.d1 != null && s.outcome.d1 !== 0) {
          p.graded++;
          if ((s.impact.dir === 'bullish') === (s.outcome.d1 > 0)) p.hits++;
        }
      }
    });
    var list = Object.keys(map).map(function (k) {
      var p = map[k];
      p.avg = p.graded ? Math.round(p.hits / p.graded * 100) : null;
      p.stories.sort(function (x, y) { return y.ts - x.ts; });
      return p;
    });
    list.sort(function (a, b) {
      if (a.graded !== b.graded) return b.graded - a.graded;
      if (a.calls !== b.calls) return b.calls - a.calls;
      return b.last - a.last;
    });
    return list;
  }

  Q.analysts = {
    extract: extract,
    profiles: profiles,
    get: function (name, stories) {
      var list = profiles(stories);
      for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
      return null;
    }
  };
})();
