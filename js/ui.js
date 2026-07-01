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
  function pxMovesHtml(t) {
    var p = window.Q.prices ? Q.prices.get(t) : null;
    if (!p || !p.moves || !p.moves.length) return '';
    var up = p.changePct >= 0;
    var rows = p.moves.map(function (m) {
      var d = new Date(m.date);
      return '<div class="tl"><span class="tl-date">' + (d.getMonth() + 1) + '/' + d.getDate() + '</span>' +
        '<span class="tl-h">$' + m.close.toFixed(2) + '</span>' +
        '<span class="move ' + (m.pct >= 0 ? 'up' : 'down') + '">' + signed(m.pct) + '</span></div>';
    }).join('');
    return '<div class="d-section"><h4>Recent price action — ' + esc(t) + ' <span class="muted" style="text-transform:none;letter-spacing:0">· real daily</span></h4>' +
      '<div class="similar-stat" style="background:var(--bg-2);border-color:var(--border)">Latest close <b>$' + p.price.toFixed(2) + '</b> · today <b style="color:' + (up ? 'var(--bull)' : 'var(--bear)') + '">' + (up ? '+' : '') + p.changePct.toFixed(2) + '%</b></div>' +
      '<div class="timeline">' + rows + '</div></div>';
  }

  // ---------- story card ----------
  function storyCard(s) {
    var im = s.impact;
    var dirCls = im.revenue && im.dir !== 'neutral' ? (im.dir === 'bullish' ? ' d-bull' : ' d-bear') : '';
    var linkHtml = s.link ? '<a class="art-link" href="' + esc(s.link) + '" target="_blank" rel="noopener noreferrer" title="Read the original article">↗</a>' : '';
    return '' +
      '<div class="story' + (s.live ? ' fresh' : '') + dirCls + '" data-id="' + esc(s.id) + '">' +
        '<div class="story-top">' +
          '<span class="src">' + esc(s.src) + '</span>' +
          '<span class="dot-sep"></span><span>' + timeAgo(s.ts) + '</span>' +
          linkHtml +
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
      pxMovesHtml(primary) +
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
    showApp: function (email) { $('#login-view').hidden = true; $('#app-view').hidden = false; $('#user-email').textContent = email || ''; },
    setLoginError: function (m) { $('#login-error').textContent = m || ''; },
    setClock: function () { $('#live-clock').textContent = new Date().toLocaleTimeString(); },

    setView: function (name) {
      ['feed', 'screener', 'alerts', 'watchlist'].forEach(function (v) {
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
      $('#topic-grid').innerHTML = Q.data.TOPICS.map(function (t) {
        var on = store.isArmed(t.name);
        return '<div class="topic' + (on ? ' armed' : '') + '">' +
          '<h3>' + esc(t.name) + '</h3><div class="meta">' + esc(t.desc) + '</div>' +
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
            '<button class="link" data-unwatch="' + esc(sym) + '" style="margin-left:auto">remove</button></div>' +
          '<div class="wt-stories">' + rows + '</div>' +
        '</div>';
      }).join('');
      if (!w.length) $('#watch-tickers').innerHTML = '<div class="empty">No watched tickers. Add one above.</div>';
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
