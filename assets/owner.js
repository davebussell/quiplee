/* owner.js: fills /owner/ from /api/owner/stats (owner's members-password cookie only). */
(function () {
  'use strict';
  var box = document.querySelector('[data-owner]');
  if (!box) return;
  var $ = function (s) { return box.querySelector(s); };
  var msg = $('[data-owner-msg]');
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function when(iso) {
    if (!iso) return '–';
    try { return new Date(iso).toLocaleString('en-US', { timeZone: 'America/Toronto', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch (e) { return iso; }
  }
  function tile(label, value, note) {
    return '<div class="card tile"><span class="tile-label">' + esc(label) + '</span><span class="tile-value">' + esc(value) + '</span>' +
      (note ? '<span class="tile-note">' + esc(note) + '</span>' : '') + '</div>';
  }
  if (location.protocol === 'file:') { msg.textContent = 'Open this page on the live site to see the numbers.'; return; }
  fetch('/api/owner/stats', { credentials: 'same-origin', cache: 'no-store' })
    .then(function (r) { return r.json().then(function (j) { return { r: r, j: j }; }); })
    .then(function (x) {
      if (x.r.status === 401) { msg.hidden = true; $('[data-owner-lock]').hidden = false; var i = box.querySelector('input[type=password]'); if (i) i.focus(); return; }
      if (!x.r.ok) { msg.textContent = x.j.error || "Couldn't load the numbers. Refresh to try again."; return; }
      var a = x.j.accounts, s = x.j.subscribers;
      msg.textContent = 'As of ' + when(x.j.asof) + '.';
      var t = $('[data-owner-tiles]');
      t.innerHTML = tile('Accounts', a.total.toLocaleString('en-US'), a.email_confirmed + ' confirmed their email') +
        tile('New today', a.new_24h, 'last 24 hours') +
        tile('New this week', a.new_7d, a.new_30d + ' in the last 30 days') +
        tile('Start/Stop emails', s.total, s.confirmed + ' confirmed, without an account');
      t.hidden = false;
      $('[data-owner-rows]').innerHTML = (x.j.recent || []).map(function (u) {
        return '<tr><td><b>' + esc(u.name) + '</b></td><td class="nowrap">' + esc(when(u.created)) + '</td><td>' + esc(u.email || '–') + '</td>' +
          '<td>' + (u.email_confirmed ? 'Yes' : '<span class="muted">Not yet</span>') + '</td><td class="r">' + esc(u.follows) + '</td>' +
          '<td>' + (u.alerts ? 'On' : '<span class="muted">Off</span>') + '</td></tr>';
      }).join('') || '<tr><td colspan="6" class="muted">No accounts yet.</td></tr>';
      $('[data-owner-list]').hidden = false;
    })
    .catch(function () { msg.textContent = "Couldn't reach the server. Refresh to try again."; });
})();
