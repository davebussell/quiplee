/* view.js: Simple or Detailed, on every page (Dave, Oct 27: "a simple view by default, with the numbers and
 * jargon one tap away").
 *
 * <html data-view="simple"> is the default; a tiny script in each page's head switches it to "full" before the
 * page paints when this browser chose Detailed (localStorage bp.view). In Simple view:
 *   - any element marked data-adv="what it holds" hides behind a one-line button ("Show the numbers: ..."); a tap
 *     opens just that one, and "Always show details" switches the whole site to Detailed;
 *   - table columns marked .adv-col hide; [data-adv-cols] shows them on that table.
 * The footer's "View: Simple · Detailed" switches for good. */
(function () {
  'use strict';
  var root = document.documentElement, KEY = 'bp.view';
  function mode() { return root.getAttribute('data-view') === 'full' ? 'full' : 'simple'; }
  function save(m) { try { localStorage.setItem(KEY, m); } catch (e) { /* private mode: this page only */ } }
  function paint() {
    var simple = mode() === 'simple';
    [].forEach.call(document.querySelectorAll('[data-adv]'), function (el) {
      var b = el._advBtn;
      if (!b) {
        b = document.createElement('p');
        b.className = 'adv-tap';
        b.innerHTML = '<button type="button" class="adv-open"><span class="adv-plus" aria-hidden="true">+</span> <span></span></button>' +
          ' <button type="button" class="linkish adv-always">Always show details</button>';
        b.querySelector('.adv-open span:last-child').textContent = 'Show the details: ' + el.getAttribute('data-adv');
        el.parentNode.insertBefore(b, el);
        el._advBtn = b;
        b.querySelector('.adv-open').addEventListener('click', function () {
          el.classList.add('adv-shown');
          b.hidden = true;
          window.dispatchEvent(new Event('resize'));        // tables that were hidden size themselves now (sortable.js)
        });
        b.querySelector('.adv-always').addEventListener('click', function () { set('full'); });
      }
      b.hidden = !simple || el.classList.contains('adv-shown');
    });
    [].forEach.call(document.querySelectorAll('[data-view-set]'), function (x) {
      var on = x.getAttribute('data-view-set') === mode();
      x.setAttribute('aria-pressed', String(on));
      x.classList.toggle('on', on);
    });
  }
  function set(m) {
    root.setAttribute('data-view', m);
    save(m);
    if (m === 'simple') [].forEach.call(document.querySelectorAll('.adv-shown'), function (el) { el.classList.remove('adv-shown'); });
    [].forEach.call(document.querySelectorAll('.cols-shown'), function (el) { if (m === 'simple') el.classList.remove('cols-shown'); });
    paint();
    window.dispatchEvent(new Event('resize'));
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-view-set], [data-adv-cols]') : null;
    if (!t) return;
    if (t.hasAttribute('data-view-set')) { set(t.getAttribute('data-view-set')); return; }
    // the columns kept for Detailed, on this table only
    var p = t.closest('.adv-cols-note'), tbl = null, prev = p && p.previousElementSibling;
    while (prev && !tbl) { tbl = prev.matches('table') ? prev : prev.querySelector('table'); prev = prev.previousElementSibling; }   // the table just above (other notes may sit between)
    if (tbl) { tbl.classList.add('cols-shown'); p.hidden = true; window.dispatchEvent(new Event('resize')); }
  });
  window.BPView = { mode: mode, set: set };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paint);
  else paint();
})();
