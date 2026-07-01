/* app.js — boot, the real-time story loop, alert logic, and event wiring. */
(function () {
  var Q = window.Q, $ = function (s) { return document.querySelector(s); };
  var TICK_MS = 7000;       // synthetic demo cadence
  var LIVE_MS = 60000;      // real-news poll cadence (gentle on free feeds)
  var state = { view: 'feed', timer: null, clock: null, mode: 'demo', seen: {} };

  // ---------- render dispatch ----------
  function renderCurrent() {
    if (state.view === 'feed') Q.ui.renderFeed();
    else if (state.view === 'screener') Q.ui.renderScreener();
    else if (state.view === 'alerts') Q.ui.renderAlerts();
    else if (state.view === 'watchlist') Q.ui.renderWatchlist();
    Q.ui.refreshChrome();
  }
  function gotoView(name) {
    state.view = name;
    Q.ui.setView(name);
    if (name === 'alerts') { Q.store.markAllSeen(); }
    renderCurrent();
  }

  // ---------- demo loop (synthetic) ----------
  function tickDemo() {
    var story = Q.data.generate({ preferTickers: Q.store.getWatched(), preferTopics: Q.store.getArmed() });
    Q.store.addStory(story);
    maybeAlert(story);
    renderCurrent();
  }

  // ---------- live loop (real news) ----------
  function addLive(stories, alertNew) {
    // oldest-first so the newest ends up on top after unshift; dedupe by id
    stories.slice().sort(function (a, b) { return a.ts - b.ts; }).forEach(function (s) {
      if (state.seen[s.id] || Q.store.hasStory(s.id)) return;
      state.seen[s.id] = 1;
      Q.store.addStory(s);
      if (alertNew) maybeAlert(s);
    });
  }
  function pollLive() {
    Q.live.fetchStories(Q.store.getWatched(), Q.store.getArmed())
      .then(function (stories) { addLive(stories, true); renderCurrent(); refreshPrices(); })
      .catch(function () { /* transient feed error — keep showing what we have */ });
  }

  // ---------- real prices ----------
  function feedTickers() {
    var set = {};
    Q.store.getWatched().forEach(function (t) { set[t] = 1; });
    Q.store.allStories().slice(0, 40).forEach(function (s) { (s.tickers || []).forEach(function (t) { if (Q.data.TICKERS[t]) set[t] = 1; }); });
    return Object.keys(set);
  }
  function refreshPrices() {
    if (!window.Q.prices) return;
    Q.prices.load(feedTickers()).then(function () {
      // join real prices to story timestamps -> realized outcomes -> scoreboard
      var changed = Q.outcomes.apply(Q.store.allStories());
      if (changed) Q.store.persistNow();
      renderCurrent();
    }).catch(function () {});
  }

  // ---------- browser notifications ----------
  function notifEnabled() { try { return localStorage.getItem('q_notif') === '1'; } catch (e) { return false; } }
  function setNotifEnabled(b) { try { localStorage.setItem('q_notif', b ? '1' : '0'); } catch (e) {} }
  function osNotify(alert) {
    if (!notifEnabled() || typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    try {
      new Notification('Quiplee — ' + (alert.trigger === 'stock' ? alert.match : alert.match), {
        body: alert.story.headline,
        tag: alert.story.id
      });
    } catch (e) { /* some browsers restrict constructor — ignore */ }
  }

  // "if revenue-impacting for a selected stock or topic → report the stock / fire the alert"
  function maybeAlert(s) {
    if (!s.impact.revenue) return;
    var stockHit = s.tickers.filter(function (t) { return Q.store.isWatched(t); });
    var topicHit = s.topics.filter(function (t) { return Q.store.isArmed(t); });
    var alert = null;
    if (stockHit.length) alert = { story: s, trigger: 'stock', match: stockHit[0], ts: Date.now() };
    else if (topicHit.length) alert = { story: s, trigger: 'topic', match: topicHit[0], ts: Date.now() };
    if (alert) { Q.store.addAlert(alert); Q.ui.toast(alert); osNotify(alert); }
  }

  function startLoop() {
    stopLoop();
    state.timer = setInterval(state.mode === 'live' ? pollLive : tickDemo, state.mode === 'live' ? LIVE_MS : TICK_MS);
  }
  function stopLoop() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }

  function setMode(mode) {
    state.mode = mode;
    Q.store.setLiveMode(mode === 'live');
    var el = $('#data-mode');
    if (el) { el.textContent = mode === 'live' ? 'LIVE' : 'DEMO'; el.className = 'mode-pill ' + mode; }
    var dot = $('#live-dot'); if (dot) dot.title = mode === 'live' ? 'Live news feed' : 'Demo data (synthetic)';
  }

  // ---------- lifecycle ----------
  function startApp(email) {
    Q.ui.showApp(email);
    Q.ui.renderTypeChips();
    Q.ui.setClock();
    state.clock = setInterval(Q.ui.setClock, 1000);
    // remember persisted stories so re-fetches don't duplicate or re-alert them
    Q.store.allStories().forEach(function (s) { if (s.real) state.seen[s.id] = 1; });
    // notifications toggle reflects saved preference (only if permission still granted)
    var nt = $('#notif-toggle');
    if (nt) nt.checked = notifEnabled() && typeof Notification !== 'undefined' && Notification.permission === 'granted';
    setMode('demo');                 // default; upgraded to live if the function answers
    gotoView('feed');
    Q.ui.showFeedSkeleton();         // loading state while the first live fetch runs
    // try real news first; fall back to synthetic if the ingestion function isn't reachable
    Q.live.fetchStories(Q.store.getWatched(), Q.store.getArmed())
      .then(function (stories) {
        if (!stories.length) throw new Error('no live stories');
        setMode('live');
        addLive(stories, false);     // backfill silently (no alert storm on first load)
        renderCurrent();
        refreshPrices();
        startLoop();
      })
      .catch(function () { setMode('demo'); tickDemo(); startLoop(); });
  }
  function signOut() {
    stopLoop(); if (state.clock) clearInterval(state.clock);
    Q.auth.logout();
    Q.ui.showLogin();
  }

  // ---------- wiring ----------
  function wire() {
    $('#login-form').addEventListener('submit', function (e) {
      e.preventDefault();
      Q.ui.setLoginError('');
      var r = Q.auth.login($('#login-email').value, $('#login-password').value);
      if (r.ok) { this.reset(); startApp(r.session.email); } else Q.ui.setLoginError(r.error);
    });
    $('#logout-btn').addEventListener('click', signOut);

    // tabs
    $('#tabs').addEventListener('click', function (e) {
      var t = e.target.closest('[data-view]'); if (t) gotoView(t.getAttribute('data-view'));
    });

    // filters
    $('#search').addEventListener('input', function () { Q.store.setFilter('search', this.value); if (state.view === 'feed') Q.ui.renderFeed(); });
    $('#f-revenue').addEventListener('change', function () { Q.store.setFilter('revenueOnly', this.checked); renderCurrent(); });
    $('#f-watched').addEventListener('change', function () { Q.store.setFilter('watchedOnly', this.checked); renderCurrent(); });
    $('#f-direction').addEventListener('click', function (e) {
      var b = e.target.closest('[data-dir]'); if (!b) return;
      Q.store.setFilter('direction', b.getAttribute('data-dir'));
      [].forEach.call(this.children, function (c) { c.classList.toggle('active', c === b); });
      renderCurrent();
    });
    $('#type-chips').addEventListener('click', function (e) {
      var b = e.target.closest('[data-type]'); if (!b) return;
      Q.store.toggleType(b.getAttribute('data-type'));
      Q.ui.renderTypeChips(); renderCurrent();
    });
    $('#types-clear').addEventListener('click', function () { Q.store.clearTypes(); Q.ui.renderTypeChips(); renderCurrent(); });

    // feed sort: Latest | Impact
    $('#feed-sort').addEventListener('click', function (e) {
      var b = e.target.closest('[data-sort]'); if (!b) return;
      Q.store.setFilter('sort', b.getAttribute('data-sort'));
      [].forEach.call(this.children, function (c) { c.classList.toggle('active', c === b); });
      Q.ui.renderFeed();
    });

    // browser notifications (permission requested on the user's gesture)
    $('#notif-toggle').addEventListener('change', function () {
      var box = this;
      if (!box.checked) { setNotifEnabled(false); return; }
      if (typeof Notification === 'undefined') { box.checked = false; return; }
      Notification.requestPermission().then(function (p) {
        if (p === 'granted') setNotifEnabled(true);
        else { setNotifEnabled(false); box.checked = false; }
      });
    });

    // story clicks (feed, screener, live-mini, alerts) via delegation on document
    document.addEventListener('click', function (e) {
      if (e.target.closest('a')) return; // real links (read article) navigate, not modal
      var open = e.target.closest('[data-id]');
      if (!open) return;
      // inside the modal, only timeline rows re-open (jump between stories)
      if (e.target.closest('.modal') && !open.classList.contains('tl')) return;
      Q.ui.openDetail(open.getAttribute('data-id'));
    });

    // screener arm
    $('#topic-grid').addEventListener('click', function (e) {
      var b = e.target.closest('[data-arm]'); if (!b) return;
      Q.store.toggleArmed(b.getAttribute('data-arm'));
      Q.ui.renderScreener(); Q.ui.renderWatchSummary();
    });

    // alerts clear
    $('#alerts-clear').addEventListener('click', function () { Q.store.clearAlerts(); Q.ui.renderAlerts(); Q.ui.refreshChrome(); });

    // watchlist add/remove
    $('#watch-add').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = $('#watch-input').value;
      if (!Q.data.isValidTicker(v)) { $('#watch-input').value = ''; $('#watch-input').placeholder = 'Unknown ticker — try NVDA, MSFT…'; return; }
      Q.store.addWatched(v); $('#watch-input').value = '';
      Q.ui.renderWatchlist(); Q.ui.renderWatchSummary();
    });
    $('#watch-tickers').addEventListener('click', function (e) {
      var b = e.target.closest('[data-unwatch]'); if (!b) return;
      Q.store.removeWatched(b.getAttribute('data-unwatch'));
      Q.ui.renderWatchlist(); Q.ui.renderWatchSummary();
    });

    // detail close
    $('#detail-close').addEventListener('click', Q.ui.closeDetail);
    $('#detail-modal').addEventListener('click', function (e) { if (e.target === this) Q.ui.closeDetail(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') Q.ui.closeDetail(); });

    // pause when tab hidden
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) stopLoop();
      else if (Q.auth.getSession()) { renderCurrent(); if (state.mode === 'live') pollLive(); startLoop(); }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    Q.ui.bind(Q.store);
    wire();
    var s = Q.auth.getSession();
    if (s) startApp(s.email); else Q.ui.showLogin();
  });
})();
