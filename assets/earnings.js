/* earnings.js: /earnings/ (tools/qstrat/earnreact.py). The "Reporting next" table opens on the soonest 20; a tap
 * shows every upcoming report. Sorting is sortable.js; the My stocks filter is mine.js (data-mine). */
(function () {
  'use strict';
  var tbl = document.querySelector('.er-soon'), btn = document.querySelector('[data-er-later]');
  if (!tbl || !btn) return;
  var n = tbl.querySelectorAll('tr[data-later]').length;
  if (!n) { btn.parentNode.hidden = true; return; }
  var all = btn.textContent;
  function set(on) { tbl.classList.toggle('show-later', on); btn.textContent = on ? 'Show only the soonest' : all; }
  btn.addEventListener('click', function () { set(!tbl.classList.contains('show-later')); });
  // sorting by another column (sortable.js) is over every upcoming report, so show them all
  if (tbl.tHead) tbl.tHead.addEventListener('click', function () { set(true); });
})();
