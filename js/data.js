/* data.js — universe, seed stories, the impact engine, lookback & similar lookups,
 * and the live story generator. This is the brain behind every verdict. */
(function () {
  window.Q = window.Q || {};

  // ----------------------------- universe -----------------------------
  var TICKERS = {
    NVDA: { name: 'Nvidia', topics: ['AI / Data Center', 'Semiconductors'] },
    AMD:  { name: 'AMD', topics: ['AI / Data Center', 'Semiconductors'] },
    AVGO: { name: 'Broadcom', topics: ['AI / Data Center', 'Semiconductors'] },
    MU:   { name: 'Micron', topics: ['Semiconductors'] },
    MSFT: { name: 'Microsoft', topics: ['Cloud', 'AI / Data Center'] },
    AMZN: { name: 'Amazon', topics: ['Cloud', 'Consumer Demand'] },
    GOOGL:{ name: 'Alphabet', topics: ['Cloud', 'AI / Data Center'] },
    META: { name: 'Meta', topics: ['AI / Data Center'] },
    AAPL: { name: 'Apple', topics: ['Consumer Demand'] },
    TSLA: { name: 'Tesla', topics: ['EV & Autos', 'AI / Data Center'] },
    LLY:  { name: 'Eli Lilly', topics: ['FDA / Drug Approvals'] },
    PFE:  { name: 'Pfizer', topics: ['FDA / Drug Approvals'] },
    JPM:  { name: 'JPMorgan', topics: ['Interest Rates'] },
    XOM:  { name: 'Exxon', topics: ['Energy'] }
  };
  var TOPICS = [
    { name: 'AI / Data Center', desc: 'Accelerators, sovereign AI, capex' },
    { name: 'Semiconductors', desc: 'Chips, memory, foundry, HBM' },
    { name: 'Cloud', desc: 'AWS / Azure / GCP growth & margins' },
    { name: 'Consumer Demand', desc: 'Units, China, holiday demand' },
    { name: 'EV & Autos', desc: 'Pricing, deliveries, demand' },
    { name: 'FDA / Drug Approvals', desc: 'Approvals, trials, holds' },
    { name: 'Tariffs & Trade', desc: 'Duties, export controls' },
    { name: 'Interest Rates', desc: 'NII, Fed, credit' },
    { name: 'Energy', desc: 'Crude, OPEC, realizations' },
    { name: 'M&A', desc: 'Deals, blocks, synergies' }
  ];
  var TYPES = ['Earnings', 'Guidance', 'M&A', 'Regulatory', 'Product', 'Supply Chain', 'Analyst', 'Macro', 'Legal', 'Buyback'];
  var SOURCES = ['Bloomberg', 'Reuters', 'CNBC', 'WSJ', 'Dow Jones', 'Nikkei', 'The Information'];

  function imp(revenue, dir, mag, lo, hi, conf, mechanism, horizon) {
    return { revenue: revenue, dir: dir, mag: mag, movePct: [lo, hi], conf: conf, mechanism: mechanism, horizon: horizon || 'days' };
  }
  var MIN = 60000, HR = 60 * MIN, DAY = 24 * HR;

  // ----------------------------- seed stories -----------------------------
  // agoMin = how long ago; outcome = realized move (past stories only)
  var SEED = [
    { id: 's1', src: 'Bloomberg', type: 'Guidance', tickers: ['NVDA'], topics: ['AI / Data Center', 'Semiconductors'], ago: 5 * 1440,
      headline: 'Nvidia guides Q3 data-center revenue well above Street on sovereign-AI demand',
      impact: imp(true, 'bullish', 'high', 4, 7, 84, 'Raises the full-year data-center revenue outlook', 'days'), outcome: { d1: 6.2, d5: 9.1 } },
    { id: 's2', src: 'Reuters', type: 'Regulatory', tickers: ['LLY'], topics: ['FDA / Drug Approvals'], ago: 8 * 1440,
      headline: "FDA grants priority review to Lilly's oral GLP-1 obesity pill",
      impact: imp(true, 'bullish', 'high', 3, 6, 80, 'Pulls forward a multi-billion-dollar revenue catalyst', 'weeks'), outcome: { d1: 4.1, d5: 6.0 } },
    { id: 's3', src: 'Nikkei', type: 'Supply Chain', tickers: ['AAPL'], topics: ['Consumer Demand'], ago: 12 * 1440,
      headline: 'Apple cuts iPhone 16 build orders ~10% on soft China demand',
      impact: imp(true, 'bearish', 'med', -4, -2, 68, 'Signals weaker unit revenue this quarter', 'days'), outcome: { d1: -3.4, d5: -2.1 } },
    { id: 's4', src: 'CNBC', type: 'Guidance', tickers: ['MU'], topics: ['Semiconductors'], ago: 6 * 1440,
      headline: 'Micron lifts DRAM pricing outlook as HBM shortage tightens',
      impact: imp(true, 'bullish', 'high', 3, 6, 79, 'Higher memory ASPs flow straight to revenue', 'days'), outcome: { d1: 5.0, d5: 7.4 } },
    { id: 's5', src: 'WSJ', type: 'M&A', tickers: ['AVGO'], topics: ['Semiconductors', 'M&A'], ago: 15 * 1440,
      headline: "DOJ moves to block Broadcom's $61B networking acquisition",
      impact: imp(true, 'bearish', 'med', -3, -1, 71, 'Removes an expected revenue & synergy stream', 'weeks'), outcome: { d1: -2.1, d5: -1.4 } },
    { id: 's6', src: 'Bloomberg', type: 'Earnings', tickers: ['AMZN'], topics: ['Cloud'], ago: 20 * 1440,
      headline: 'Amazon AWS growth re-accelerates to 19%; cloud margins expand',
      impact: imp(true, 'bullish', 'high', 3, 6, 82, 'Cloud reacceleration lifts high-margin revenue', 'days'), outcome: { d1: 4.5, d5: 5.2 } },
    { id: 's7', src: 'Reuters', type: 'Product', tickers: ['TSLA'], topics: ['EV & Autos'], ago: 10 * 1440,
      headline: 'Tesla cuts Model Y prices across Europe',
      impact: imp(true, 'bearish', 'med', -3, -1, 64, 'Pricing pressure weighs on auto gross revenue', 'days'), outcome: { d1: -1.8, d5: -3.0 } },
    { id: 's8', src: 'Dow Jones', type: 'Macro', tickers: ['NVDA', 'AMD', 'AVGO'], topics: ['Tariffs & Trade', 'Semiconductors'], ago: 18 * 1440,
      headline: 'US weighs 25% tariff on imported advanced chips',
      impact: imp(true, 'bearish', 'med', -3, -1, 60, 'Cost & demand headwind across chip revenue', 'weeks'), outcome: { d1: -2.5, d5: -1.0 } },
    { id: 's9', src: 'CNBC', type: 'Guidance', tickers: ['JPM'], topics: ['Interest Rates'], ago: 22 * 1440,
      headline: 'JPMorgan beats Q2 and raises full-year net-interest-income guidance',
      impact: imp(true, 'bullish', 'med', 2, 4, 77, 'Higher NII guidance lifts revenue', 'days'), outcome: { d1: 3.0, d5: 3.6 } },
    { id: 's10', src: 'The Information', type: 'Analyst', tickers: ['META'], topics: ['AI / Data Center'], ago: 9 * 1440,
      headline: 'Morgan Stanley raises Meta price target to $700 on Reels monetization',
      impact: imp(false, 'bullish', 'low', 0.5, 1.5, 55, 'Sentiment / price-target change — not a direct revenue event', 'days'), outcome: { d1: 1.2, d5: 0.4 } },
    { id: 's11', src: 'Reuters', type: 'Regulatory', tickers: ['PFE'], topics: ['FDA / Drug Approvals'], ago: 14 * 1440,
      headline: 'FDA places clinical hold on Pfizer gene-therapy trial',
      impact: imp(true, 'bearish', 'med', -3, -1, 66, 'Delays a future revenue stream', 'weeks'), outcome: { d1: -2.7, d5: -2.0 } },
    { id: 's12', src: 'Bloomberg', type: 'Macro', tickers: ['XOM'], topics: ['Energy'], ago: 11 * 1440,
      headline: 'Brent jumps 4% as OPEC+ extends supply cuts',
      impact: imp(true, 'bullish', 'med', 1, 3, 62, 'Higher realized prices lift upstream revenue', 'days'), outcome: { d1: 2.0, d5: 1.2 } },
    { id: 's13', src: 'WSJ', type: 'Product', tickers: ['MSFT'], topics: ['Cloud', 'AI / Data Center'], ago: 16 * 1440,
      headline: 'Microsoft signs $10B multi-year Azure AI capacity deal',
      impact: imp(true, 'bullish', 'med', 2, 4, 75, 'Backlog converts to recurring cloud revenue', 'weeks'), outcome: { d1: 2.8, d5: 3.1 } },
    { id: 's14', src: 'Reuters', type: 'Legal', tickers: ['GOOGL'], topics: ['M&A'], ago: 25 * 1440,
      headline: 'Judge rules Google violated antitrust law in ad-tech case',
      impact: imp(false, 'bearish', 'med', -3, -1, 63, 'Remedy risk to the ad-revenue model', 'weeks'), outcome: { d1: -2.3, d5: -1.1 } },
    { id: 's15', src: 'CNBC', type: 'Product', tickers: ['AMD'], topics: ['AI / Data Center', 'Semiconductors'], ago: 7 * 1440,
      headline: 'AMD unveils MI400 AI accelerator; hyperscaler OEMs line up',
      impact: imp(true, 'bullish', 'med', 2, 4, 70, 'New product expands data-center revenue', 'days'), outcome: { d1: 3.3, d5: 2.0 } },
    { id: 's16', src: 'Dow Jones', type: 'Buyback', tickers: ['AAPL'], topics: ['Consumer Demand'], ago: 30 * 1440,
      headline: 'Apple authorizes record $110B share buyback',
      impact: imp(false, 'bullish', 'low', 0.5, 1.5, 52, 'Capital return — lifts EPS, not revenue', 'days'), outcome: { d1: 1.0, d5: 0.6 } },
    // developing (recent, no outcome yet)
    { id: 's17', src: 'The Information', type: 'Supply Chain', tickers: ['NVDA', 'AMD'], topics: ['AI / Data Center', 'Semiconductors'], ago: 14,
      headline: 'TSMC flags record AI-chip orders into Q4, supplier checks show',
      impact: imp(true, 'bullish', 'med', 2, 4, 72, 'Supply signal points to higher AI-chip revenue', 'days'), outcome: null },
    { id: 's18', src: 'Bloomberg', type: 'Regulatory', tickers: ['LLY'], topics: ['FDA / Drug Approvals'], ago: 32,
      headline: "Lilly's tirzepatide hits primary endpoint in heart-failure trial",
      impact: imp(true, 'bullish', 'high', 3, 5, 76, 'Label expansion opens a new revenue indication', 'weeks'), outcome: null }
  ];
  // stamp ts from ago (minutes)
  SEED.forEach(function (s) { s.ts = Date.now() - s.ago * MIN; });

  // ----------------------------- impact engine -----------------------------
  var BULL = /(rais|above|beat|tops|approv|surg|jump|record|wins?|expand|re-?accel|priority review|upgrade|strong|higher|hits? primary|acquir|merger|unveil|launch|deal)/;
  var BEAR = /(cut|trim|miss|below|block|sues?|halt|recall|short(age)?|soft|weak|down(grade)?|delay|hold|probe|tariff|lawsuit|class action|antitrust|loses?|violat|disappoint)/;

  function mechFor(type, dir) {
    var up = dir === 'bullish';
    switch (type) {
      case 'Guidance': return up ? 'Raises the forward revenue outlook' : 'Cuts the forward revenue outlook';
      case 'Earnings': return up ? 'Beat resets the revenue trajectory higher' : 'Miss resets the revenue trajectory lower';
      case 'M&A': return up ? 'Adds an expected revenue stream' : 'Removes an expected revenue stream';
      case 'Regulatory': return up ? 'Clears the path to a new revenue catalyst' : 'Threatens an existing or future revenue stream';
      case 'Product': return 'Shifts the product revenue mix';
      case 'Supply Chain': return up ? 'Signals higher unit/volume revenue' : 'Signals lower unit/volume revenue';
      case 'Macro': return 'Sector-wide demand / cost shift';
      case 'Analyst': return 'Sentiment / price-target change — not a direct revenue event';
      case 'Legal': return 'Litigation risk to the revenue model';
      case 'Buyback': return 'Capital return — affects EPS, not revenue';
      default: return 'Potential impact on the revenue outlook';
    }
  }

  // Evaluate a story we weren't handed a verdict for (e.g. live-generated).
  function evaluate(s) {
    var t = (s.headline || '').toLowerCase(), type = s.type;
    var revenueTypes = { Earnings: 1, Guidance: 1, 'M&A': 1, Regulatory: 1, Product: 1, 'Supply Chain': 1, Macro: 1 };
    var revenue = !!revenueTypes[type];
    var b = BULL.test(t), r = BEAR.test(t);
    var dir = (b && !r) ? 'bullish' : (r && !b) ? 'bearish' : 'neutral';
    var mag = 'med';
    if (type === 'Earnings' || type === 'Guidance' || type === 'M&A' || type === 'Regulatory') mag = 'high';
    if (type === 'Analyst' || type === 'Buyback') mag = 'low';
    if (/record|well above|soar|block|halt|approv/.test(t)) mag = 'high';
    if (type === 'Analyst' || type === 'Buyback' || type === 'Legal') revenue = false;
    if (dir === 'neutral') revenue = false;
    var moveMap = { low: [0.5, 1.5], med: [1.5, 3.5], high: [3.5, 7] };
    var mv = moveMap[mag].slice();
    if (dir === 'bearish') mv = [-mv[1], -mv[0]];
    var conf = Math.min(92, 55 + (mag === 'high' ? 18 : mag === 'med' ? 8 : 0) + (revenue ? 6 : 0));
    return imp(revenue, dir, mag, mv[0], mv[1], conf, mechFor(type, dir), type === 'Macro' ? 'weeks' : 'days');
  }

  // ----------------------------- lookups -----------------------------
  function median(arr) {
    if (!arr.length) return 0;
    var a = arr.slice().sort(function (x, y) { return x - y; });
    var m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }

  // past stories for a ticker, with realized outcomes
  function lookback(ticker) {
    return SEED.filter(function (s) { return s.outcome && s.tickers.indexOf(ticker) !== -1; })
      .sort(function (a, b) { return b.ts - a.ts; });
  }

  // comparable past events (same type or shared topic), preferring other tickers
  function similar(story) {
    var list = SEED.filter(function (s) {
      if (s.id === story.id || !s.outcome) return false;
      var sameType = s.type === story.type;
      var sharedTopic = s.topics.some(function (tp) { return story.topics.indexOf(tp) !== -1; });
      return sameType || sharedTopic;
    });
    // prefer different tickers, then most recent
    list.sort(function (a, b) {
      var aOther = a.tickers.indexOf(story.tickers[0]) === -1 ? 0 : 1;
      var bOther = b.tickers.indexOf(story.tickers[0]) === -1 ? 0 : 1;
      if (aOther !== bOther) return aOther - bOther;
      return b.ts - a.ts;
    });
    var top = list.slice(0, 6);
    var moves = top.map(function (s) { return s.outcome.d5; });
    return { list: top, medianD5: median(moves), n: top.length };
  }

  // ----------------------------- live generator -----------------------------
  var TEMPLATES = [
    { type: 'Guidance', h: '{NAME} raises full-year revenue guidance above consensus' },
    { type: 'Guidance', h: '{NAME} trims revenue outlook on softening demand' },
    { type: 'Earnings', h: '{NAME} tops Q{Q} estimates as revenue accelerates' },
    { type: 'Earnings', h: '{NAME} misses on revenue; next-quarter guidance disappoints' },
    { type: 'Product', h: '{NAME} unveils next-gen platform; early orders look strong' },
    { type: 'Supply Chain', h: 'Supplier checks show {NAME} order cuts on weak demand' },
    { type: 'Supply Chain', h: '{NAME} suppliers signal record orders into Q{Q}' },
    { type: 'Regulatory', h: 'Regulators approve {NAME} flagship ahead of schedule' },
    { type: 'Regulatory', h: 'Regulators open a probe into {NAME}; shares pressured' },
    { type: 'M&A', h: '{NAME} to acquire rival in ${B}B cash-and-stock deal' },
    { type: 'Analyst', h: '{BANK} upgrades {NAME} to Overweight and lifts target' },
    { type: 'Macro', h: 'Washington weighs new tariffs on {TOPIC} imports' },
    { type: 'Legal', h: 'Court lets class action against {NAME} proceed' }
  ];
  var BANKS = ['Morgan Stanley', 'Goldman', 'JPMorgan', 'BofA', 'Citi'];
  var gen = 0;
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function symbolsForTopic(topic) {
    return Object.keys(TICKERS).filter(function (k) { return TICKERS[k].topics.indexOf(topic) !== -1; });
  }

  // opts.preferTickers / opts.preferTopics bias selection so alerts are demonstrable
  function generate(opts) {
    opts = opts || {};
    var tpl = pick(TEMPLATES);
    var sym;
    if (opts.preferTickers && opts.preferTickers.length && Math.random() < 0.55) {
      sym = pick(opts.preferTickers);
    } else if (opts.preferTopics && opts.preferTopics.length && Math.random() < 0.5) {
      var cands = symbolsForTopic(pick(opts.preferTopics));
      sym = cands.length ? pick(cands) : pick(Object.keys(TICKERS));
    } else {
      sym = pick(Object.keys(TICKERS));
    }
    var meta = TICKERS[sym];
    var topics = meta.topics.slice();
    var tickers = [sym];
    var topicForMacro = pick(topics);
    if (tpl.type === 'Macro') {
      topics = ['Tariffs & Trade', topicForMacro];
      tickers = symbolsForTopic(topicForMacro).slice(0, 3);
      if (tickers.indexOf(sym) === -1) tickers.unshift(sym);
      tickers = tickers.slice(0, 3);
    }
    var headline = tpl.h
      .replace('{NAME}', meta.name)
      .replace('{Q}', pick(['3', '4']))
      .replace('{B}', String(8 + Math.floor(Math.random() * 52)))
      .replace('{BANK}', pick(BANKS))
      .replace('{TOPIC}', topicForMacro.replace(' / ', '/'));
    var story = {
      id: 'g' + (++gen) + '-' + Date.now(),
      src: pick(SOURCES), type: tpl.type, tickers: tickers, topics: topics,
      headline: headline, ts: Date.now(), ago: 0, outcome: null, live: true
    };
    story.impact = evaluate(story);
    return story;
  }

  // classify a real headline into one of TYPES (used by the live-news path before evaluate)
  function classifyType(headline) {
    var t = (headline || '').toLowerCase();
    if (/\b8-?k\b|10-?q|10-?k|files? .*(sec|form)|material event/.test(t)) return 'Regulatory';
    if (/upgrade|downgrade|price target|\bpt\b|initiate|overweight|underweight|buy rating|sell rating|analyst|raises? target|cuts? target/.test(t)) return 'Analyst';
    if (/acqui|merger|\bto buy\b|takeover|buyout|stake in/.test(t)) return 'M&A';
    if (/guidance|outlook|forecast|guides|raises? full-year|cuts? full-year|lowers? full-year/.test(t)) return 'Guidance';
    if (/earnings|beats?|misses?|\beps\b|quarterly results|q[1-4]\b|revenue (rose|fell|jump|beat|miss)/.test(t)) return 'Earnings';
    if (/fda|approv|clinical|trial|probe|antitrust|investigat|regulat|sanction|export control/.test(t)) return 'Regulatory';
    if (/recall|shortage|supplier|supply|order cuts|production|output|factory|foundry|wafer/.test(t)) return 'Supply Chain';
    if (/launch|unveil|introduc|releases?|rolls out|new (chip|gpu|model|product|drug|platform)/.test(t)) return 'Product';
    if (/tariff|\bfed\b|interest rate|inflation|opec|crude|jobs report|gdp|macro/.test(t)) return 'Macro';
    if (/buyback|repurchase|dividend|stock split/.test(t)) return 'Buyback';
    if (/lawsuit|class action|court|judge|verdict|settle|fine\b/.test(t)) return 'Legal';
    return 'Product';
  }

  Q.data = {
    TICKERS: TICKERS, TOPICS: TOPICS, TYPES: TYPES,
    seed: function () { return SEED.slice(); },
    evaluate: evaluate, classifyType: classifyType, lookback: lookback, similar: similar, generate: generate,
    tickerName: function (s) { return (TICKERS[s] && TICKERS[s].name) || s; },
    isValidTicker: function (s) { return !!TICKERS[String(s || '').toUpperCase()]; }
  };
})();
