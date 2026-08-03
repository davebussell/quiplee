/* market.js — US equity session status (NYSE/Nasdaq regular hours) in
 * America/New_York wall-clock, correct for any viewer timezone.
 * Regular 09:30–16:00 ET Mon–Fri; pre 04:00–09:30; after 16:00–20:00.
 * Exchange holidays are not modelled. */
(function () {
  window.Q = window.Q || {};

  function nyParts() {
    var fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false
    });
    var o = {};
    fmt.formatToParts(new Date()).forEach(function (p) { o[p.type] = p.value; });
    return o;
  }

  Q.market = {
    status: function () {
      var p = nyParts();
      if (p.weekday === 'Sat' || p.weekday === 'Sun') return { state: 'closed', label: 'Market closed' };
      var mins = (parseInt(p.hour, 10) % 24) * 60 + parseInt(p.minute, 10);
      if (mins >= 570 && mins < 960) return { state: 'open', label: 'Market open' };
      if (mins >= 240 && mins < 570) return { state: 'pre', label: 'Pre-market' };
      if (mins >= 960 && mins < 1200) return { state: 'after', label: 'After-hours' };
      return { state: 'closed', label: 'Market closed' };
    }
  };
})();
