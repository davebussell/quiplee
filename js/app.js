/* app.js — boot, the real-time story loop, alert logic, and event wiring. */
(function () {
  var Q = window.Q, $ = function (s) { return document.querySelector(s); };
  var TICK_MS = 7000;
  var state = { view: 'feed', timer: null, clock: null };

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

  // ---------- real-time loop ----------
  function tick() {
    var story = Q.data.generate({ preferTickers: Q.store.getWatched(), preferTopics: Q.store.getArmed() });
    Q.store.addStory(story);
    maybeAlert(story);
    renderCurrent();
  }

  // "if revenue-impacting for a selected stock or topic → report the stock / fire the alert"
  function maybeAlert(s) {
    if (!s.impact.revenue) return;
    var stockHit = s.tickers.filter(function (t) { return Q.store.isWatched(t); });
    var topicHit = s.topics.filter(function (t) { return Q.store.isArmed(t); });
    var alert = null;
    if (stockHit.length) alert = { story: s, trigger: 'stock', match: stockHit[0], ts: Date.now() };
    else if (topicHit.length) alert = { story: s, trigger: 'topic', match: topicHit[0], ts: Date.now() };
    if (alert) { Q.store.addAlert(alert); Q.ui.toast(alert); }
  }

  function startLoop() { stopLoop(); state.timer = setInterval(tick, TICK_MS); }
  function stopLoop() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }

  // ---------- lifecycle ----------
  function startApp(email) {
    Q.ui.showApp(email);
    Q.ui.renderTypeChips();
    Q.ui.setClock();
    state.clock = setInterval(Q.ui.setClock, 1000);
    gotoView('feed');
    startLoop();
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

    // story clicks (feed, screener, live-mini, alerts) via delegation on document
    document.addEventListener('click', function (e) {
      var open = e.target.closest('[data-id]');
      if (open && !e.target.closest('.modal')) { Q.ui.openDetail(open.getAttribute('data-id')); }
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
      else if (Q.auth.getSession()) { renderCurrent(); startLoop(); }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    Q.ui.bind(Q.store);
    wire();
    var s = Q.auth.getSession();
    if (s) startApp(s.email); else Q.ui.showLogin();
  });
})();
