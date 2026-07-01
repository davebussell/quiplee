/* news.js — Quiplee ingestion proxy (Netlify Function, zero dependencies).
 *
 * GET /.netlify/functions/news?tickers=NVDA,AAPL&topics=Cloud&names=NVDA:Nvidia;AAPL:Apple
 *
 * Pulls real headlines from Google News RSS (per ticker + per topic) and recent
 * SEC EDGAR 8-K filings (per ticker), normalizes them, and returns raw stories.
 * Impact scoring is intentionally left to the client (it runs Q.data.evaluate),
 * so there is exactly one impact engine. Runs server-side, so there is no
 * browser CORS problem fetching SEC/Google. Node 18+ global fetch, no npm deps.
 */
'use strict';

var UA = 'Quiplee/1.0 (+https://quiplee.com; contact dave@clickshift.ca)';
var DEFAULT_NAMES = {
  NVDA: 'Nvidia', AMD: 'AMD', AVGO: 'Broadcom', MU: 'Micron', MSFT: 'Microsoft',
  AMZN: 'Amazon', GOOGL: 'Alphabet', META: 'Meta', AAPL: 'Apple', TSLA: 'Tesla',
  LLY: 'Eli Lilly', PFE: 'Pfizer', JPM: 'JPMorgan', XOM: 'Exxon'
};
var CIK_CACHE = null; // ticker -> 10-digit CIK (lazy, cached across warm invocations)

function decodeEntities(s) {
  return String(s)
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&#0?39;/g, "'").replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}
function clean(s) { return decodeEntities(String(s || '').replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim(); }
function field(block, tag) { var m = block.match(new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)<\\/' + tag + '>')); return m ? m[1] : ''; }

function parseRss(xml) {
  var items = [], re = /<item\b[\s\S]*?<\/item>/g, m;
  while ((m = re.exec(xml))) {
    var b = m[0];
    items.push({
      title: clean(field(b, 'title')),
      link: clean(field(b, 'link')),
      pub: clean(field(b, 'pubDate')),
      source: clean(field(b, 'source'))
    });
  }
  return items;
}
function parseAtom(xml) {
  var items = [], re = /<entry\b[\s\S]*?<\/entry>/g, m;
  while ((m = re.exec(xml))) {
    var b = m[0];
    var href = (b.match(/<link[^>]*href="([^"]*)"/) || [])[1] || '';
    var form = clean(field(b, 'filing-type')) || (b.match(/<category[^>]*term="([^"]*)"/) || [])[1] || '8-K';
    items.push({ title: clean(field(b, 'title')), updated: clean(field(b, 'updated')), href: href, form: clean(form) });
  }
  return items;
}

function fetchText(url, headers) {
  return fetch(url, { headers: Object.assign({ 'User-Agent': UA, 'Accept': '*/*' }, headers || {}) })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); });
}

function splitPublisher(it) {
  var src = it.source, title = it.title;
  if (!src) { var i = title.lastIndexOf(' - '); if (i > 0) { src = title.slice(i + 3); title = title.slice(0, i); } }
  return { headline: title, src: src || 'Google News' };
}

function googleTicker(sym, name) {
  var url = 'https://news.google.com/rss/search?q=' + encodeURIComponent('"' + name + '" stock') + '&hl=en-US&gl=US&ceid=US:en';
  return fetchText(url).then(function (xml) {
    return parseRss(xml).slice(0, 6).map(function (it) {
      var p = splitPublisher(it);
      return { headline: p.headline, src: p.src, ts: Date.parse(it.pub) || Date.now(), link: it.link, tickers: [sym], topicHint: null, origin: 'news' };
    });
  });
}
function googleTopic(topic) {
  var url = 'https://news.google.com/rss/search?q=' + encodeURIComponent(topic.replace(' / ', ' ') + ' stocks') + '&hl=en-US&gl=US&ceid=US:en';
  return fetchText(url).then(function (xml) {
    return parseRss(xml).slice(0, 4).map(function (it) {
      var p = splitPublisher(it);
      return { headline: p.headline, src: p.src, ts: Date.parse(it.pub) || Date.now(), link: it.link, tickers: [], topicHint: topic, origin: 'news' };
    });
  });
}

// ---- optional tagged-news APIs (activate by setting env vars in Netlify) ----
// FINNHUB_KEY  -> per-ticker company news (free tier: 60 calls/min)
// MARKETAUX_KEY -> one multi-ticker call with entity tags (free tier: ~100/day)
function ymd(offsetDays) { return new Date(Date.now() - offsetDays * 864e5).toISOString().slice(0, 10); }

function finnhubTicker(sym, key) {
  var url = 'https://finnhub.io/api/v1/company-news?symbol=' + encodeURIComponent(sym) +
    '&from=' + ymd(3) + '&to=' + ymd(0) + '&token=' + encodeURIComponent(key);
  return fetchText(url).then(function (txt) {
    var arr = JSON.parse(txt);
    if (!Array.isArray(arr)) return [];
    return arr.slice(0, 6).map(function (a) {
      return { headline: clean(a.headline), src: a.source || 'Finnhub', ts: (a.datetime || 0) * 1000 || Date.now(), link: a.url || '', tickers: [sym], topicHint: null, origin: 'api' };
    });
  });
}

function marketauxBatch(tickers, key) {
  var url = 'https://api.marketaux.com/v1/news/all?symbols=' + encodeURIComponent(tickers.join(',')) +
    '&filter_entities=true&language=en&limit=10&api_token=' + encodeURIComponent(key);
  return fetchText(url).then(function (txt) {
    var j = JSON.parse(txt);
    if (!j || !Array.isArray(j.data)) return [];
    return j.data.map(function (a) {
      var syms = (a.entities || []).map(function (e) { return e.symbol; }).filter(Boolean);
      return { headline: clean(a.title), src: a.source || 'Marketaux', ts: Date.parse(a.published_at) || Date.now(), link: a.url || '', tickers: syms.slice(0, 3), topicHint: null, origin: 'api' };
    });
  });
}

function loadCiks() {
  if (CIK_CACHE) return Promise.resolve(CIK_CACHE);
  return fetchText('https://www.sec.gov/files/company_tickers.json').then(function (txt) {
    var obj = JSON.parse(txt), map = {};
    Object.keys(obj).forEach(function (k) { var e = obj[k]; map[e.ticker] = String(e.cik_str).padStart(10, '0'); });
    CIK_CACHE = map; return map;
  }).catch(function () { CIK_CACHE = {}; return CIK_CACHE; });
}
function edgarTicker(sym, name) {
  return loadCiks().then(function (ciks) {
    var cik = ciks[sym]; if (!cik) return [];
    var url = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' + cik + '&type=8-K&count=3&output=atom';
    return fetchText(url).then(function (xml) {
      return parseAtom(xml).slice(0, 3).map(function (it) {
        return { headline: name + ' files ' + it.form + ' (SEC material event)', src: 'SEC EDGAR', ts: Date.parse(it.updated) || Date.now(), link: it.href, tickers: [sym], topicHint: null, origin: 'sec' };
      });
    });
  });
}

exports.handler = function (event) {
  var qs = event.queryStringParameters || {};
  var tickers = (qs.tickers || '').split(',').map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean).slice(0, 8);
  var topics = (qs.topics || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 3);
  var wantEdgar = qs.edgar !== '0';
  var names = Object.assign({}, DEFAULT_NAMES);
  (qs.names || '').split(';').forEach(function (p) { var i = p.indexOf(':'); if (i > 0) names[p.slice(0, i).toUpperCase()] = p.slice(i + 1); });

  var jobs = [];
  var FINNHUB = process.env.FINNHUB_KEY, MARKETAUX = process.env.MARKETAUX_KEY;
  tickers.forEach(function (sym) {
    jobs.push(googleTicker(sym, names[sym] || sym).catch(function () { return []; }));
    if (wantEdgar) jobs.push(edgarTicker(sym, names[sym] || sym).catch(function () { return []; }));
    if (FINNHUB) jobs.push(finnhubTicker(sym, FINNHUB).catch(function () { return []; }));
  });
  if (MARKETAUX && tickers.length) jobs.push(marketauxBatch(tickers, MARKETAUX).catch(function () { return []; }));
  topics.forEach(function (tp) { jobs.push(googleTopic(tp).catch(function () { return []; })); });

  return Promise.all(jobs).then(function (results) {
    var stories = [];
    results.forEach(function (arr) { stories = stories.concat(arr); });
    stories.sort(function (a, b) { return b.ts - a.ts; });
    stories = stories.slice(0, 60);
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=45' },
      body: JSON.stringify({ ok: true, count: stories.length, stories: stories })
    };
  }).catch(function (e) {
    return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: false, error: String(e), stories: [] }) };
  });
};
