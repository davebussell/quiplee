/* prices.js — real US equity prices (Netlify Function, zero deps).
 *
 * GET /.netlify/functions/prices?tickers=NVDA,AAPL
 * Pulls daily candles from the free Yahoo Finance chart API (server-side, so no
 * browser CORS) and returns, per ticker: current price, today's % move, and the
 * most recent real daily moves (for the detail "recent price action" panel). */
'use strict';

var UA = 'Mozilla/5.0 (compatible; Quiplee/1.0; +https://quiplee.com)';
function round2(n) { return Math.round(n * 100) / 100; }
function chartUrl(sym) { return 'https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(sym) + '?range=6mo&interval=1d'; }

function fetchPrice(sym) {
  return fetch(chartUrl(sym), { headers: { 'User-Agent': UA, 'Accept': 'application/json' } })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (j) {
      var res = j && j.chart && j.chart.result && j.chart.result[0];
      if (!res) throw new Error('no result');
      var meta = res.meta || {};
      var ts = res.timestamp || [];
      var closes = (res.indicators && res.indicators.quote && res.indicators.quote[0] && res.indicators.quote[0].close) || [];
      var pairs = [];
      for (var i = 0; i < closes.length; i++) { if (closes[i] != null && ts[i] != null) pairs.push({ t: ts[i] * 1000, c: closes[i] }); }
      // derive from the series — Yahoo's meta.previousClose is the pre-range close, not yesterday
      var price = pairs.length ? pairs[pairs.length - 1].c : meta.regularMarketPrice;
      var prev = pairs.length > 1 ? pairs[pairs.length - 2].c : (meta.chartPreviousClose != null ? meta.chartPreviousClose : price);
      var moves = [];
      for (var k = Math.max(1, pairs.length - 8); k < pairs.length; k++) {
        moves.push({ date: pairs[k].t, pct: round2((pairs[k].c - pairs[k - 1].c) / pairs[k - 1].c * 100), close: round2(pairs[k].c) });
      }
      moves.reverse(); // newest first
      return {
        price: round2(price),
        prevClose: round2(prev),
        changePct: prev ? round2((price - prev) / prev * 100) : 0,
        currency: meta.currency || 'USD',
        asOf: meta.regularMarketTime ? meta.regularMarketTime * 1000 : Date.now(),
        moves: moves,
        // full daily close series (ascending) — used to compute realized story outcomes
        series: pairs.map(function (p) { return { t: p.t, c: round2(p.c) }; })
      };
    });
}

exports.handler = function (event) {
  var qs = event.queryStringParameters || {};
  var tickers = (qs.tickers || '').split(',').map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean).slice(0, 12);
  return Promise.all(tickers.map(function (sym) {
    return fetchPrice(sym).then(function (d) { return { sym: sym, data: d }; }).catch(function () { return null; });
  })).then(function (arr) {
    var prices = {};
    arr.forEach(function (x) { if (x) prices[x.sym] = x.data; });
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=60' },
      body: JSON.stringify({ ok: true, count: Object.keys(prices).length, prices: prices })
    };
  }).catch(function (e) {
    return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: false, error: String(e), prices: {} }) };
  });
};
