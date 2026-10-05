/* stocks.js — the /stocks/ list: search, group filter, one-click sorts and the
 * list / by-family switch. Column sorting itself comes from sortable.js; the
 * sort buttons press the right column header until it sorts high to low.
 * Supports ?sort=score|plays|upside|crash|year, ?group=<group> (or ndx for the Nasdaq-100) and ?view=families. */
(function () {
  'use strict';
  var tbl = document.getElementById('st-tbl');
  if (!tbl) return;
  var rows = [].slice.call(tbl.tBodies[0].rows);
  var q = document.getElementById('st-q'), count = document.getElementById('st-count');
  var st = { group: '', q: '', min: 0 };
  var COL = { score: 9, plays: 7, upside: 8, crash: 10, year: 4 };
  var params = new URLSearchParams(location.search);

  function apply() {
    var shown = 0;
    rows.forEach(function (r) {
      var grp = !st.group || (st.group === 'ndx' ? r.getAttribute('data-ndx') === '1' : r.getAttribute('data-group') === st.group);
      var ok = grp && (!st.q || r.getAttribute('data-q').indexOf(st.q) >= 0)
        && (+r.getAttribute('data-share') >= st.min);
      r.hidden = !ok;
      if (ok) shown++;
    });
    count.textContent = (shown === rows.length ? rows.length + ' names.' : shown + ' of ' + rows.length + ' names shown.')
      + (st.min ? ' Strongest setups only include stocks at least half the plays hold.' : '');
  }
  function setPressed(sel, el) { [].forEach.call(document.querySelectorAll(sel), function (b) { b.setAttribute('aria-pressed', String(b === el)); }); }

  function sortBy(key) {
    st.min = key === 'score' ? 0.5 : 0;
    apply();
    var th = tbl.tHead.rows[0].cells[COL[key]];
    var btn = th && (th.querySelector('.sort-btn') || th);
    if (!btn) return;
    for (var i = 0; i < 3 && th.getAttribute('aria-sort') !== 'descending'; i++) btn.click();
    var b = document.querySelector('.st-sorts [data-sort="' + key + '"]');
    if (b) setPressed('.st-sorts [data-sort]', b);
  }

  [].forEach.call(document.querySelectorAll('.st-groups [data-group]'), function (b) {
    b.addEventListener('click', function () { st.group = b.getAttribute('data-group'); setPressed('.st-groups [data-group]', b); apply(); });
  });
  [].forEach.call(document.querySelectorAll('.st-sorts [data-sort]'), function (b) {
    b.addEventListener('click', function () { sortBy(b.getAttribute('data-sort')); });
  });
  q.addEventListener('input', function () { st.q = q.value.trim().toLowerCase(); apply(); });

  // list / by-family views
  var views = document.querySelectorAll('.st-views [data-view]');
  function view(v) {
    document.getElementById('list').hidden = v !== 'list';
    document.getElementById('families').hidden = v !== 'families';
    [].forEach.call(views, function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-view') === v)); });
  }
  [].forEach.call(views, function (b) { b.addEventListener('click', function () { view(b.getAttribute('data-view')); }); });

  // deep links from the menu
  function start() {
    if (params.get('view') === 'families') view('families');
    var g = params.get('group');
    if (g) { var gb = document.querySelector('.st-groups [data-group="' + g + '"]'); if (gb) gb.click(); }
    var s = params.get('sort');
    if (s && COL[s] != null) sortBy(s);
    apply();
  }
  // sortable.js adds its header buttons on DOMContentLoaded; run after it
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(start, 0); });
  else setTimeout(start, 0);
})();
