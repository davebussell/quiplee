/* store.js — app state: watched tickers, armed screener topics, filters,
 * the live story buffer, and fired alerts. Watched/armed persist to localStorage. */
(function () {
  window.Q = window.Q || {};
  var LS = { watched: 'q_watched', armed: 'q_armed' };

  function read(k, fb) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : fb; } catch (e) { return fb; } }
  function write(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  var state = {
    watched: read(LS.watched, ['NVDA', 'LLY', 'AAPL']),
    armed: read(LS.armed, ['AI / Data Center']),
    filters: { search: '', revenueOnly: false, direction: 'all', watchedOnly: false, types: [] },
    stories: [],     // live/synthetic, newest first
    alerts: [],      // newest first
    liveMode: false  // true once real news is flowing (seed stays for lookback/similar only)
  };

  Q.store = {
    setLiveMode: function (b) { state.liveMode = !!b; },
    isLive: function () { return state.liveMode; },
    // ---- watched tickers ----
    getWatched: function () { return state.watched.slice(); },
    isWatched: function (s) { return state.watched.indexOf(s) !== -1; },
    addWatched: function (s) {
      s = String(s || '').toUpperCase().replace(/[^A-Z.]/g, '').slice(0, 6);
      if (s && state.watched.indexOf(s) === -1) { state.watched.push(s); write(LS.watched, state.watched); }
      return s;
    },
    removeWatched: function (s) { state.watched = state.watched.filter(function (x) { return x !== s; }); write(LS.watched, state.watched); },

    // ---- armed screener topics ----
    getArmed: function () { return state.armed.slice(); },
    isArmed: function (t) { return state.armed.indexOf(t) !== -1; },
    toggleArmed: function (t) {
      var i = state.armed.indexOf(t);
      if (i === -1) state.armed.push(t); else state.armed.splice(i, 1);
      write(LS.armed, state.armed); return this.isArmed(t);
    },

    // ---- filters ----
    getFilters: function () { return state.filters; },
    setFilter: function (k, v) { state.filters[k] = v; },
    toggleType: function (t) {
      var a = state.filters.types, i = a.indexOf(t);
      if (i === -1) a.push(t); else a.splice(i, 1);
    },
    clearTypes: function () { state.filters.types = []; },

    // ---- stories ----
    addStory: function (s) { state.stories.unshift(s); if (state.stories.length > 80) state.stories.pop(); },
    allStories: function () {
      // live mode: feed is real news only. demo mode: include seed for content.
      var base = state.liveMode ? state.stories.slice() : state.stories.concat(Q.data.seed());
      return base.sort(function (a, b) { return b.ts - a.ts; });
    },
    hasStory: function (id) {
      for (var i = 0; i < state.stories.length; i++) if (state.stories[i].id === id) return true;
      return false;
    },
    findStory: function (id) {
      var all = this.allStories();
      for (var i = 0; i < all.length; i++) if (all[i].id === id) return all[i];
      // alerts keep their own snapshots
      for (var j = 0; j < state.alerts.length; j++) if (state.alerts[j].story.id === id) return state.alerts[j].story;
      return null;
    },

    // ---- alerts ----
    addAlert: function (a) { a.seen = false; state.alerts.unshift(a); if (state.alerts.length > 60) state.alerts.pop(); },
    getAlerts: function () { return state.alerts.slice(); },
    unseenCount: function () { return state.alerts.filter(function (a) { return !a.seen; }).length; },
    markAllSeen: function () { state.alerts.forEach(function (a) { a.seen = true; }); },
    clearAlerts: function () { state.alerts = []; }
  };
})();
