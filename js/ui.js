/* ui.js — all rendering + view switching for Quiplee. */
(function () {
  window.Q = window.Q || {};
  var $ = function (s) { return document.querySelector(s); };
  var store = null; // bound at boot

  // ---------- helpers ----------
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]; }); }
  function timeAgo(ts) {
    var s = Math.max(0, (Date.now() - ts) / 1000);
    if (s < 60) return 'just now';
    var m = Math.floor(s / 60); if (m < 60) return m + 'm ago';
    var h = Math.floor(m / 60); if (h < 24) return h + 'h ago';
    return Math.floor(h / 24) + 'd ago';
  }
  function dirClass(d) { return d === 'bullish' ? 'bull' : d === 'bearish' ? 'bear' : 'neutral'; }
  function arrow(d) { return d === 'bullish' ? '▲' : d === 'bearish' ? '▼' : '■'; }
  function rangeStr(mv) {
    var lo = Math.abs(mv[0]), hi = Math.abs(mv[1]);
    if (lo > hi) { var t = lo; lo = hi; hi = t; }
    return fmt(lo) + '–' + fmt(hi) + '%';
  }
  function fmt(n) { return (Math.round(n * 10) / 10).toString(); }
  function signed(n) { return (n >= 0 ? '+' : '−') + Math.abs(Math.round(n * 10) / 10) + '%'; }
  function fmtVal(h) {
    var v = h.value >= 100 ? Math.round(h.value).toLocaleString('en-US') : h.value.toFixed(2);
    return v + ' ' + (h.valueCur || '');
  }
  function impactText(im) {
    if (im.dir === 'neutral') return 'No clear move';
    return (im.dir === 'bullish' ? '+' : '−') + rangeStr(im.movePct);
  }
  function confColor(d) { return d === 'bullish' ? 'var(--bull)' : d === 'bearish' ? 'var(--bear)' : 'var(--warn)'; }

  function impactPill(im) {
    return '<span class="impact ' + dirClass(im.dir) + '"><span class="arrow">' + arrow(im.dir) + '</span>' + esc(impactText(im)) + '</span>';
  }
  function tickerChips(tickers) {
    return '<div class="tickers">' + tickers.map(function (t) {
      return '<span class="tk' + (store.isWatched(t) ? ' watched' : '') + '">' + esc(t) + '</span>';
    }).join('') + '</div>';
  }

  // ---------- real price helpers ----------
  function priceChip(t) {
    var p = window.Q.prices ? Q.prices.get(t) : null;
    if (!p) return '';
    var up = p.changePct >= 0;
    return '<span class="px ' + (up ? 'up' : 'down') + '" title="' + esc(t) + ' latest daily close">$' + p.price.toFixed(2) + ' <b>' + (up ? '+' : '') + p.changePct.toFixed(2) + '%</b></span>';
  }
  /** SVG price line; optional storyTs draws a marker where the story landed. */
  function priceChart(series, storyTs, stroke) {
    if (!series || series.length < 2) return '';
    var idx = -1;
    if (storyTs) { for (var i = 0; i < series.length; i++) { if (series[i].t <= storyTs) idx = i; else break; } }
    var win = idx >= 0 ? series.slice(Math.max(0, idx - 14), Math.min(series.length, idx + 15)) : series.slice(-30);
    var mIdx = idx >= 0 ? Math.min(idx, 14, idx - Math.max(0, idx - 14)) : -1;
    var w = 560, h = 84, pad = 6;
    var lo = Infinity, hi = -Infinity;
    win.forEach(function (p) { if (p.c < lo) lo = p.c; if (p.c > hi) hi = p.c; });
    var span = (hi - lo) || 1;
    var step = (w - pad * 2) / (win.length - 1);
    function X(i) { return (pad + i * step).toFixed(1); }
    function Y(c) { return (pad + (h - pad * 2) * (1 - (c - lo) / span)).toFixed(1); }
    var pts = win.map(function (p, i) { return X(i) + ',' + Y(p.c); }).join(' ');
    var marker = '';
    if (mIdx >= 0 && win[mIdx]) {
      marker = '<line x1="' + X(mIdx) + '" y1="' + pad + '" x2="' + X(mIdx) + '" y2="' + (h - pad) + '" stroke="var(--violet)" stroke-width="1" stroke-dasharray="3,3"/>' +
        '<circle cx="' + X(mIdx) + '" cy="' + Y(win[mIdx].c) + '" r="4" fill="var(--violet)"/>';
    }
    return '<svg class="d-chart" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none">' +
      '<polyline points="' + pts + '" fill="none" stroke="' + stroke + '" stroke-width="1.8" stroke-linejoin="round"/>' + marker + '</svg>' +
      (mIdx >= 0 ? '<div class="chart-cap muted">● story published — line shows real daily closes around it</div>' : '');
  }

  function pxMovesHtml(t, storyTs) {
    var p = window.Q.prices ? Q.prices.get(t) : null;
    if (!p || !p.moves || !p.moves.length) return '';
    var up = p.changePct >= 0;
    var stroke = up ? 'var(--bull)' : 'var(--bear)';
    var rows = p.moves.slice(0, 5).map(function (m) {
      var d = new Date(m.date);
      return '<div class="tl"><span class="tl-date">' + (d.getMonth() + 1) + '/' + d.getDate() + '</span>' +
        '<span class="tl-h">$' + m.close.toFixed(2) + '</span>' +
        '<span class="move ' + (m.pct >= 0 ? 'up' : 'down') + '">' + signed(m.pct) + '</span></div>';
    }).join('');
    return '<div class="d-section"><h4>Price action — ' + esc(t) + ' <span class="muted" style="text-transform:none;letter-spacing:0">· real daily closes</span></h4>' +
      '<div class="similar-stat" style="background:var(--bg-2);border-color:var(--border)">Latest close <b>$' + p.price.toFixed(2) + '</b> · today <b style="color:' + (up ? 'var(--bull)' : 'var(--bear)') + '">' + (up ? '+' : '') + p.changePct.toFixed(2) + '%</b></div>' +
      priceChart(p.series, storyTs, stroke) +
      '<div class="timeline">' + rows + '</div></div>';
  }

  function miniSpark(t) {
    var p = window.Q.prices ? Q.prices.get(t) : null;
    if (!p || !p.series || p.series.length < 2) return '';
    var win = p.series.slice(-30), w = 120, h = 30, pad = 2;
    var lo = Infinity, hi = -Infinity;
    win.forEach(function (x) { if (x.c < lo) lo = x.c; if (x.c > hi) hi = x.c; });
    var span = (hi - lo) || 1, step = (w - pad * 2) / (win.length - 1);
    var pts = win.map(function (x, i) {
      return (pad + i * step).toFixed(1) + ',' + (pad + (h - pad * 2) * (1 - (x.c - lo) / span)).toFixed(1);
    }).join(' ');
    var stroke = p.changePct >= 0 ? 'var(--bull)' : 'var(--bear)';
    return '<svg class="wt-spark" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none"><polyline points="' + pts + '" fill="none" stroke="' + stroke + '" stroke-width="1.6"/></svg>';
  }

  // ---------- story card ----------
  function storyCard(s) {
    var im = s.impact;
    var dirCls = im.revenue && im.dir !== 'neutral' ? (im.dir === 'bullish' ? ' d-bull' : ' d-bear') : '';
    var linkHtml = s.link ? '<a class="art-link" href="' + esc(s.link) + '" target="_blank" rel="noopener noreferrer" title="Read the original article">↗</a>' : '';
    var an = window.Q.analysts ? Q.analysts.extract(s) : null;
    var anHtml = an && an.kind === 'analyst' ? '<button class="an-chip" data-analyst="' + esc(an.name) + '" title="Track this analyst’s record">' + esc(an.name) + ' ▸</button>' : '';
    return '' +
      '<div class="story' + (s.live ? ' fresh' : '') + dirCls + '" data-id="' + esc(s.id) + '">' +
        '<div class="story-top">' +
          '<span class="src">' + esc(s.src) + '</span>' +
          '<span class="dot-sep"></span><span>' + timeAgo(s.ts) + '</span>' +
          linkHtml + anHtml +
          '<span class="type-tag">' + esc(s.type) + '</span>' +
        '</div>' +
        '<div class="headline">' + esc(s.headline) + '</div>' +
        '<div class="story-bottom">' +
          tickerChips(s.tickers) +
          priceChip(s.tickers[0]) +
          impactPill(im) +
          (im.revenue ? '<span class="rev-flag">Revenue</span>' : '') +
          '<div class="conf">' + im.conf + '%<div class="conf-bar"><div class="conf-fill" style="width:' + im.conf + '%;background:' + confColor(im.dir) + '"></div></div></div>' +
        '</div>' +
        '<div class="why"><b>Why:</b> ' + esc(im.mechanism) + ' · ' + (im.dir === 'neutral' ? 'no clear directional read' : 'anticipated ' + esc(impactText(im)) + ' over ' + im.horizon) + '</div>' +
      '</div>';
  }

  function renderFeedInto(el, stories, emptyEl) {
    el.innerHTML = stories.map(storyCard).join('');
    if (emptyEl) emptyEl.hidden = stories.length > 0;
    el.hidden = stories.length === 0;
  }

  // ---------- detail overlay ----------
  function affectedRow(sym, im) {
    return '<div class="d-aff-row"><span class="sym">' + esc(sym) + '</span><span class="muted">' + esc(Q.data.tickerName(sym)) + '</span>' +
      '<span class="impact ' + dirClass(im.dir) + '" style="margin-left:auto"><span class="arrow">' + arrow(im.dir) + '</span>' + esc(impactText(im)) + '</span></div>';
  }
  function tlRow(s) {
    var o = s.outcome;
    var moveHtml;
    if (!o || (o.d5 == null && o.d1 == null)) {
      moveHtml = '<span class="muted">developing</span>';
    } else {
      var mv = o.d5 != null ? o.d5 : o.d1;
      var span = o.d5 != null ? '5d' : '1d';
      moveHtml = '<span class="move ' + (mv >= 0 ? 'up' : 'down') + '" title="' + span + ' move' + (o.real ? ', realized from real prices' : ', demo history') + '">' +
        signed(mv) + (o.real ? ' <i class="real-tag">✓</i>' : '') + '</span>';
    }
    return '<div class="tl" data-id="' + esc(s.id) + '">' +
      '<span class="tl-date">' + timeAgo(s.ts) + '</span>' +
      '<span class="tl-h">' + esc(s.headline) + '</span>' +
      moveHtml + '</div>';
  }

  function detailHtml(s) {
    var im = s.impact;
    var primary = s.tickers[0];
    var realPool = store.realHistory ? store.realHistory() : [];
    var lb = Q.data.lookback(primary, realPool);
    var sim = Q.data.similar(s, realPool);
    var artLink = s.link ? ' · <a class="d-art" href="' + esc(s.link) + '" target="_blank" rel="noopener noreferrer">Read the article ↗</a>' : '';

    var html = '' +
      '<div class="d-source">' + esc(s.src) + ' · ' + timeAgo(s.ts) + ' · ' + esc(s.type) + artLink + '</div>' +
      '<div class="d-headline">' + esc(s.headline) + '</div>' +
      '<div class="d-verdict">' +
        (im.revenue ? '<span class="rev-flag">Revenue-impacting</span>' : '<span class="rev-flag" style="color:var(--muted);border-color:var(--border)">Sentiment</span>') +
        impactPill(im) +
        '<span class="conf">' + im.conf + '% confidence<div class="conf-bar"><div class="conf-fill" style="width:' + im.conf + '%;background:' + confColor(im.dir) + '"></div></div></span>' +
      '</div>' +
      '<div class="d-section"><h4>Anticipated impact</h4>' +
        '<div class="d-mech">' + esc(im.mechanism) + '. ' +
        (im.dir === 'neutral' ? 'No clear directional read for the stock.' :
          'Anticipated move of <b>' + esc(impactText(im)) + '</b> over ' + im.horizon + ', at ' + im.conf + '% model confidence.') +
        '</div></div>' +
      (s.outcome && s.outcome.real ?
        '<div class="d-section"><h4>Realized so far <span class="muted" style="text-transform:none;letter-spacing:0">· from real prices</span></h4>' +
          '<div class="realized-strip">' +
            '<span>Next day <b class="move ' + (s.outcome.d1 >= 0 ? 'up' : 'down') + '">' + signed(s.outcome.d1) + '</b></span>' +
            (s.outcome.d5 != null ? '<span>5 days <b class="move ' + (s.outcome.d5 >= 0 ? 'up' : 'down') + '">' + signed(s.outcome.d5) + '</b></span>' : '<span class="muted">5-day still developing</span>') +
            (im.dir !== 'neutral' && im.revenue && s.outcome.d1 != null && s.outcome.d1 !== 0 ?
              ((im.dir === 'bullish') === (s.outcome.d1 > 0)
                ? '<span class="call-hit">✓ direction call correct</span>'
                : '<span class="call-miss">✗ direction call missed</span>') : '') +
          '</div></div>' : '') +
      '<div class="d-section"><h4>Affected stocks</h4><div class="d-affected">' +
        s.tickers.map(function (t) { return affectedRow(t, im); }).join('') +
      '</div></div>' +
      pxMovesHtml(primary, s.ts) +
      '<div class="d-section"><h4>Lookback — how past stories moved ' + esc(primary) + '</h4>' +
        (lb.length ? '<div class="timeline">' + lb.map(tlRow).join('') + '</div>' : '<div class="muted">No prior scored stories for ' + esc(primary) + ' yet.</div>') +
      '</div>' +
      '<div class="d-section"><h4>Similar stories — comparable events</h4>' +
        (sim.n ? '<div class="similar-stat">Comparable ' + esc(s.type !== 'Macro' ? s.type.toLowerCase() : 'macro') + ' / topic events moved peers a median <b>' + signed(sim.medianD5) + '</b> over 5 days (n=' + sim.n + ').</div>' +
          '<div class="timeline">' + sim.list.map(tlRow).join('') + '</div>'
          : '<div class="muted">No close comparables in the history set.</div>') +
      '</div>' +
      '<div class="disclaimer">Heuristic impact model for demo purposes — <b>not financial advice</b>. Confidence reflects model uncertainty, not a guarantee. Sources shown for transparency.</div>';
    return html;
  }

  // ---------- toasts ----------
  function toast(alert) {
    var el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('data-id', alert.story.id);
    el.innerHTML = '<div class="t-head">' + (alert.trigger === 'stock' ? 'Watched · ' : 'Topic · ') + esc(alert.match) + '</div>' +
      '<div class="t-headline">' + esc(alert.story.headline) + '</div>';
    $('#toasts').appendChild(el);
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 8000);
  }

  Q.ui = {
    bind: function (s) { store = s; },
    $: $,

    showLogin: function () { $('#login-view').hidden = false; $('#app-view').hidden = true; },
    showApp: function (email) {
      $('#login-view').hidden = true; $('#app-view').hidden = false;
      $('#user-email').textContent = email || '';
      $('#logout-btn').hidden = !email; // guests see no sign-out — there's no gate anymore
    },
    setLoginError: function (m) { $('#login-error').textContent = m || ''; },
    setClock: function () { $('#live-clock').textContent = new Date().toLocaleTimeString(); },
    renderMarket: function () {
      var el = $('#market-pill'); if (!el || !window.Q.market) return;
      var st = Q.market.status();
      el.className = 'market-pill ' + st.state;
      el.innerHTML = '<span class="mdot"></span>' + st.label;
    },

    setView: function (name) {
      ['feed', 'screener', 'alerts', 'watchlist', 'analysts', 'portfolio'].forEach(function (v) {
        $('#view-' + v).hidden = v !== name;
      });
      [].forEach.call(document.querySelectorAll('.tab'), function (t) {
        t.classList.toggle('active', t.getAttribute('data-view') === name);
      });
    },

    setAlertBadge: function (n) {
      var b = $('#alert-badge');
      b.textContent = n; b.hidden = n === 0;
    },

    renderTypeChips: function () {
      var f = store.getFilters();
      $('#type-chips').innerHTML = Q.data.TYPES.map(function (t) {
        var on = f.types.indexOf(t) !== -1;
        return '<button class="tchip' + (on ? ' on' : '') + '" data-type="' + esc(t) + '">' + esc(t) + '</button>';
      }).join('');
    },

    renderWatchSummary: function () {
      var w = store.getWatched(), a = store.getArmed();
      $('#watch-summary').innerHTML =
        '<span class="wpill"><b>' + w.length + '</b> tickers</span>' +
        '<span class="wpill"><b>' + a.length + '</b> topics armed</span>';
    },

    // feed with filters applied
    renderFeed: function () {
      var f = store.getFilters();
      var q = f.search.trim().toLowerCase();
      var stories = store.allStories().filter(function (s) {
        if (f.revenueOnly && !s.impact.revenue) return false;
        if (f.direction !== 'all' && s.impact.dir !== f.direction) return false;
        if (f.types.length && f.types.indexOf(s.type) === -1) return false;
        if (f.watchedOnly) {
          var watchHit = s.tickers.some(function (t) { return store.isWatched(t); });
          var topicHit = s.topics.some(function (t) { return store.isArmed(t); });
          if (!watchHit && !topicHit) return false;
        }
        if (q) {
          var hay = (s.headline + ' ' + s.tickers.join(' ') + ' ' + s.type + ' ' + s.topics.join(' ')).toLowerCase();
          if (hay.indexOf(q) === -1) return false;
        }
        return true;
      });
      if (f.sort === 'impact') {
        stories.sort(function (a, b) {
          var ar = a.impact.revenue && a.impact.dir !== 'neutral' ? 1 : 0;
          var br = b.impact.revenue && b.impact.dir !== 'neutral' ? 1 : 0;
          if (ar !== br) return br - ar;
          if (a.impact.conf !== b.impact.conf) return b.impact.conf - a.impact.conf;
          return b.ts - a.ts;
        });
      }
      renderFeedInto($('#feed'), stories, $('#feed-empty'));
      $('#feed-count').textContent = stories.length + ' stories';
    },

    showFeedSkeleton: function () {
      var sk = '';
      for (var i = 0; i < 4; i++) {
        sk += '<div class="story skel"><div class="skel-line w40"></div><div class="skel-line w90"></div><div class="skel-line w70"></div></div>';
      }
      $('#feed').hidden = false;
      $('#feed').innerHTML = sk;
      $('#feed-count').textContent = 'fetching live stories…';
    },

    renderScoreboard: function () {
      var el = $('#scoreboard'); if (!el) return;
      var sb = Q.outcomes.scoreboard(store.allStories());
      if (!sb.n) {
        el.innerHTML = '<div class="muted" style="line-height:1.5">Collecting evidence — directional calls are graded here against real next-day moves as stories age.</div>';
        return;
      }
      var good = sb.rate >= 50;
      el.innerHTML =
        '<div class="sb-rate ' + (good ? 'up' : 'down') + '">' + sb.rate + '%</div>' +
        '<div class="muted">direction calls correct · ' + sb.hits + ' of ' + sb.n + ' graded vs real next-day moves</div>';
    },

    renderScreener: function () {
      var armed = store.getArmed();
      var all = store.allStories();
      $('#topic-grid').innerHTML = Q.data.TOPICS.map(function (t) {
        var on = store.isArmed(t.name);
        var matching = all.filter(function (s) { return (s.topics || []).indexOf(t.name) !== -1; });
        var rev = matching.filter(function (s) { return s.impact.revenue; }).length;
        var counts = matching.length
          ? '<div class="topic-counts">' + matching.length + ' stories' + (rev ? ' · <b>' + rev + ' revenue</b>' : '') + '</div>'
          : '<div class="topic-counts muted">quiet</div>';
        return '<div class="topic' + (on ? ' armed' : '') + '">' +
          '<h3>' + esc(t.name) + '</h3><div class="meta">' + esc(t.desc) + '</div>' +
          counts +
          '<button class="btn btn-ghost arm" data-arm="' + esc(t.name) + '">' + (on ? '✓ Armed' : 'Arm topic') + '</button>' +
          '</div>';
      }).join('');
      // matching stream: stories touching any armed topic
      var stories = store.allStories().filter(function (s) {
        return s.topics.some(function (tp) { return armed.indexOf(tp) !== -1; });
      });
      renderFeedInto($('#screener-feed'), stories, $('#screener-empty'));
      if (!armed.length) { $('#screener-empty').hidden = false; $('#screener-empty').textContent = 'Arm a topic above to start screening.'; }
    },

    renderAlerts: function () {
      var alerts = store.getAlerts();
      $('#alerts-empty').hidden = alerts.length > 0;
      $('#alerts-list').innerHTML = alerts.map(function (a) {
        var im = a.story.impact;
        return '<div class="alert-row">' +
          '<div class="a-body" data-id="' + esc(a.story.id) + '">' +
            '<div class="a-trigger">' + (a.trigger === 'stock' ? 'Watched ticker · ' : 'Armed topic · ') + esc(a.match) + '</div>' +
            '<div class="headline" style="font-size:14px;margin:3px 0 6px">' + esc(a.story.headline) + '</div>' +
            '<div>' + impactPill(im) + (im.revenue ? ' <span class="rev-flag">Revenue</span>' : '') + '</div>' +
          '</div>' +
          '<div class="a-when">' + timeAgo(a.ts) + '</div>' +
        '</div>';
      }).join('');
    },

    renderWatchlist: function () {
      var w = store.getWatched();
      $('#watch-tickers').innerHTML = w.map(function (sym) {
        var lb = Q.data.lookback(sym, store.realHistory ? store.realHistory() : []);
        var rows = lb.length ? lb.slice(0, 4).map(tlRow).join('') : '<div class="muted" style="padding:6px 0">No scored stories yet.</div>';
        return '<div class="wt-card">' +
          '<div class="wt-head"><span class="wt-sym">' + esc(sym) + '</span>' +
            '<span class="wt-mini">' + esc(Q.data.tickerName(sym)) + ' · ' + esc((Q.data.TICKERS[sym] ? Q.data.TICKERS[sym].topics.join(', ') : '')) + '</span>' +
            miniSpark(sym) + priceChip(sym) +
            '<button class="link" data-unwatch="' + esc(sym) + '">remove</button></div>' +
          '<div class="wt-stories">' + rows + '</div>' +
        '</div>';
      }).join('');
      if (!w.length) $('#watch-tickers').innerHTML = '<div class="empty">No watched tickers. Add one above.</div>';
    },

    renderAnalysts: function (selected) {
      var el = $('#analyst-board'); if (!el) return;
      var all = store.allStories();
      if (selected) {
        var p = Q.analysts.get(selected, all);
        if (!p) { el.innerHTML = '<div class="empty">No record for ' + esc(selected) + ' yet.</div>'; return; }
        var kindLabel = p.kind === 'analyst' ? 'Analyst / research firm' : p.kind === 'filing' ? 'Regulatory filings' : 'Publisher';
        var bat = p.avg == null ? '<span class="muted">not yet graded</span>' :
          '<span class="sb-rate ' + (p.avg >= 50 ? 'up' : 'down') + '">' + p.avg + '%</span>';
        el.innerHTML =
          '<button class="link" data-analyst-back="1">← all analysts</button>' +
          '<div class="an-profile">' +
            '<div class="an-head"><span class="an-name">' + esc(p.name) + '</span><span class="muted">' + kindLabel + '</span></div>' +
            '<div class="an-stats">' + bat +
              '<span class="muted">batting average · ' + p.hits + ' of ' + p.graded + ' graded directional calls correct (vs real next-day moves) · ' + p.calls + ' directional calls · ' + p.stories.length + ' stories tracked</span>' +
            '</div>' +
          '</div>' +
          '<div class="view-head" style="margin-top:18px"><h2 style="font-size:14px">What else they’re saying</h2></div>' +
          '<div class="timeline">' + p.stories.slice(0, 20).map(tlRow).join('') + '</div>';
        return;
      }
      var profiles = Q.analysts.profiles(all);
      if (!profiles.length) { el.innerHTML = '<div class="empty">No tracked voices yet — stories populate this as they arrive.</div>'; return; }
      el.innerHTML =
        '<table class="atable"><thead><tr><th>Voice</th><th>Kind</th><th>Stories</th><th>Calls</th><th>Graded</th><th>Batting avg</th><th>Last seen</th></tr></thead><tbody>' +
        profiles.slice(0, 30).map(function (p) {
          var bat = p.avg == null ? '<span class="muted">—</span>' :
            '<b class="' + (p.avg >= 50 ? 'tag-up' : 'tag-down') + '">' + p.avg + '%</b>';
          var kindLabel = p.kind === 'analyst' ? 'Analyst' : p.kind === 'filing' ? 'Filings' : 'Publisher';
          return '<tr data-analyst="' + esc(p.name) + '"><td class="an-name">' + esc(p.name) + '</td><td class="muted">' + kindLabel + '</td>' +
            '<td>' + p.stories.length + '</td><td>' + p.calls + '</td><td>' + p.graded + '</td><td>' + bat + '</td>' +
            '<td class="muted">' + timeAgo(p.last) + '</td></tr>';
        }).join('') + '</tbody></table>' +
        '<p class="muted" style="margin-top:12px;line-height:1.5">Batting average = directional, revenue-impacting calls whose anticipated direction matched the real next-day move, once the story aged into a graded outcome. Same rule the model scoreboard uses on itself.</p>';
    },

    renderPortfolio: function (selectedSym) {
      var el = $('#portfolio-board'); if (!el) return;
      var pf = Q.portfolio.get();

      if (!pf) {
        el.innerHTML =
          '<div class="pf-import">' +
            '<h3>Import your holdings</h3>' +
            '<p class="muted">Export a holdings CSV from your broker and drop it here. Works with the standard Canadian-broker layout (Symbol, Name, Quantity, Market Price, Market Value columns).</p>' +
            '<label class="btn btn-primary pf-file-label">Choose holdings CSV<input type="file" id="pf-file" accept=".csv,text/csv" hidden /></label>' +
            '<p id="pf-error" class="login-error"></p>' +
            '<div class="pf-privacy"><b>Private by design:</b> the file is read in your browser and stays in your browser (localStorage). Nothing is uploaded — no server, no account, no analytics. “Clear data” deletes it completely.</div>' +
          '</div>';
        return;
      }

      // ---- selected holding: full play-by-play ----
      if (selectedSym) {
        var h = null;
        for (var i = 0; i < pf.holdings.length; i++) if (pf.holdings[i].sym === selectedSym) { h = pf.holdings[i]; break; }
        if (!h) { el.innerHTML = '<div class="empty">Holding not found.</div>'; return; }
        var pb = Q.theories.playbook(h.sym, h.name, h.type);
        var cards = pb.scenarios.map(function (s) {
          return '<div class="pf-scenario">' +
            '<div class="pf-sc-head"><b>' + esc(s.name) + '</b><span class="pf-band">' + esc(s.band) + '</span></div>' +
            '<div class="pf-theory muted">Theory: ' + esc(s.theory) + '</div>' +
            '<div class="pf-play">' + esc(s.play) + '</div>' +
            (s.prec && s.prec !== '—' ? '<div class="pf-meta"><b>Precedent:</b> ' + esc(s.prec) + '</div>' : '') +
            (s.watch && s.watch !== '—' ? '<div class="pf-meta"><b>Watch:</b> ' + esc(s.watch) + '</div>' : '') +
          '</div>';
        }).join('');
        el.innerHTML =
          '<button class="link" data-pf-back="1">← all holdings</button>' +
          '<div class="an-profile">' +
            '<div class="an-head"><span class="an-name">' + esc(h.sym) + '</span><span class="muted">' + esc(h.name) + ' · ' + fmtVal(h) + '</span></div>' +
            '<div class="pf-arch"><span class="badge neutral">' + esc(pb.label) + '</span><span class="muted"> ' + esc(pb.desc) + (pb.known ? '' : ' · auto-classified — verify') + '</span></div>' +
          '</div>' +
          '<div class="view-head" style="margin-top:16px"><h2 style="font-size:14px">If it happens, the play-by-play for shares like this</h2></div>' +
          cards +
          '<p class="muted" style="margin-top:12px;line-height:1.5">Bands are historical base rates for the archetype, approximate, for education — not predictions and not financial advice.</p>';
        return;
      }

      // ---- overview: summary + risk mix + holdings table ----
      var sm = Q.portfolio.summarize(pf);
      var riskArchs = { 'leveraged-cyclical': 1, 'pre-profit-burner': 1, 'micro-spec': 1, 'crypto-proxy': 1 };
      var riskPct = sm.mix.filter(function (m) { return riskArchs[m.arch]; }).reduce(function (a, m) { return a + m.pct; }, 0);
      var totalsTxt = Object.keys(sm.totals).map(function (c) { return Math.round(sm.totals[c]).toLocaleString('en-US') + ' ' + c; }).join(' + ');
      var mixBars = sm.mix.map(function (m) {
        var hot = riskArchs[m.arch] ? ' hot' : '';
        return '<div class="pf-mix-row"><span class="pf-mix-label">' + esc(m.label) + ' · ' + m.count + '</span>' +
          '<div class="pf-mix-bar"><div class="pf-mix-fill' + hot + '" style="width:' + Math.max(2, m.pct) + '%"></div></div>' +
          '<span class="pf-mix-pct">' + m.pct + '%</span></div>';
      }).join('');
      var crashCells = Q.theories.SCENARIOS[0].cells;
      var rows = pf.holdings.map(function (h) {
        var band = h.arch && crashCells[h.arch] ? crashCells[h.arch].band : '—';
        return '<tr data-pf-sym="' + esc(h.sym) + '"><td class="an-name">' + esc(h.sym) + '</td>' +
          '<td class="muted">' + esc(h.name.slice(0, 34)) + '</td>' +
          '<td>' + fmtVal(h) + '</td>' +
          '<td><span class="muted">' + esc(h.archLabel || '') + '</span></td>' +
          '<td class="tag-down">' + esc(band) + '</td></tr>';
      }).join('');

      el.innerHTML =
        '<div class="pf-summary">' +
          '<div><b>' + sm.count + ' positions</b> · ' + totalsTxt + (pf.asOf ? ' · as of ' + esc(pf.asOf) : '') + '</div>' +
          '<div class="pf-actions"><label class="link pf-file-label">re-import<input type="file" id="pf-file" accept=".csv,text/csv" hidden /></label>' +
          '<button class="link" id="pf-clear">clear data</button></div>' +
        '</div>' +
        '<p id="pf-error" class="login-error"></p>' +
        '<div class="pf-callout' + (riskPct >= 50 ? ' hot' : '') + '"><b>' + riskPct + '%</b> of this book sits in the archetypes crashes punish hardest (leveraged cyclicals, cash burners, micro-caps, crypto proxies). The Hertz Lesson applies here first.</div>' +
        '<div class="pf-mix">' + mixBars + '</div>' +
        '<table class="atable"><thead><tr><th>Symbol</th><th>Name</th><th>Value</th><th>Archetype</th><th>Crash band</th></tr></thead><tbody>' + rows + '</tbody></table>' +
        '<p class="muted" style="margin-top:10px">Click any holding for its full play-by-play (crash, earnings misses, rate shock, AI winter, commodity bust). Data stays in this browser only.</p>';
    },

    renderLiveMini: function () {
      var recent = store.allStories().filter(function (s) { return s.impact.revenue; }).slice(0, 6);
      $('#live-mini').innerHTML = recent.map(function (s) {
        return '<div class="lm" data-id="' + esc(s.id) + '">' +
          '<div class="lm-head">' + impactPill(s.impact) + '<span class="muted">' + timeAgo(s.ts) + '</span></div>' +
          '<div>' + esc(s.tickers.join(', ')) + ' — ' + esc(s.type) + '</div>' +
        '</div>';
      }).join('');
    },

    openDetail: function (id) {
      var s = store.findStory(id); if (!s) return;
      $('#detail-body').innerHTML = detailHtml(s);
      $('#detail-modal').hidden = false;
    },
    closeDetail: function () { $('#detail-modal').hidden = true; },

    toast: toast,

    // re-render whatever's visible + chrome
    refreshChrome: function () {
      this.renderWatchSummary();
      this.renderLiveMini();
      this.renderScoreboard();
      this.setAlertBadge(store.unseenCount());
    }
  };
})();
