/* sortable.js — makes every table on Be The Puck sortable by clicking its column
 * headers. Zero dependencies; works on static pages and on tables the live desk
 * redraws (the chosen sort is re-applied after each redraw).
 *
 * Click cycle per column: best-first (high→low for numbers and dates, A→Z for
 * text) → reversed → original order. Missing values ("–", "—", blanks) always
 * sort last. Group header rows (tr.grp) hide while a sort is active and come
 * back with the original order. A cell can override its sort value with
 * data-v="…" (a number or an ISO date); a header can set its first-click
 * direction with data-sort-first="asc|desc". Opt a table out with data-nosort. */
(function () {
  'use strict';

  var MONTHS = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };
  var MISSING = /^(|–|—|-|n\/a|not yet graded)$/i;
  var DATE_RE = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})/i;
  var ISO_RE = /^\d{4}-\d{2}-\d{2}/;
  var AGO_RE = /^(just now|(\d+)\s*(m|h|d)\s+ago)$/i;
  var NUM_START = /^[+\-−]?\s?(?:[A-Z]{0,2}\$)?\d/;
  var state = {};   // table key -> { col, dir }

  function injectStyle() {
    if (document.getElementById('sortable-css')) return;
    var s = document.createElement('style');
    s.id = 'sortable-css';
    s.textContent =
      '.sort-btn{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:5px;' +
      'color:inherit;font:inherit;letter-spacing:inherit;text-transform:inherit;line-height:inherit;border-radius:4px}' +
      '.sort-btn:hover{color:var(--ink,var(--text,inherit))}' +
      '.sort-btn:focus-visible{outline:2px solid currentColor;outline-offset:2px}' +
      '.sort-ind{display:inline-block;min-width:.8em;opacity:.4;font-size:1em;line-height:1;text-align:center}' +
      'th[aria-sort] .sort-ind{opacity:1;color:var(--violet-ink,var(--violet-2,inherit))}' +
      'th.sort-ready{cursor:pointer;user-select:none}' +
      'th.sort-ready a{cursor:pointer}';
    document.head.appendChild(s);
  }

  function clean(t) { return (t || '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim(); }

  // ---- value parsing ------------------------------------------------------
  function parseNumber(t) {
    var m = t.replace(/−/g, '-').replace(/,/g, '').match(/[+\-]?\s?(?:[A-Z]{0,2}\$)?(\d+(?:\.\d+)?)/);
    if (!m) return null;
    var v = parseFloat(m[1]);
    return /^[^\d]*-/.test(m[0]) ? -v : v;
  }
  function parseDate(t) {
    var m = t.match(DATE_RE);
    return m ? Date.UTC(+m[3], MONTHS[m[1].slice(0, 3).toLowerCase()], +m[2]) : null;
  }
  function parseAgo(t) {   // returns a timestamp-like value: more recent = larger
    var m = t.match(AGO_RE);
    if (!m) return null;
    if (/just now/i.test(m[1])) return 0;
    var mult = { m: 1, h: 60, d: 1440 }[m[3].toLowerCase()];
    return -(+m[2]) * mult;
  }

  // Classify a raw cell into {kind, v}. kind: missing|num|date|ago|state|text|ov
  function read(td) {
    if (!td) return { kind: 'missing' };
    if (td.hasAttribute('data-v')) {
      var dv = td.getAttribute('data-v');
      if (dv === '') return { kind: 'missing' };
      if (!isNaN(+dv)) return { kind: 'ov', v: +dv };
      if (ISO_RE.test(dv)) return { kind: 'ov', v: Date.parse(dv) };
      return { kind: 'text', v: dv };
    }
    var t = clean(td.textContent);
    if (MISSING.test(t)) return { kind: 'missing' };
    if (t === 'IN' || t === 'OUT') return { kind: 'state', v: t === 'IN' ? 1 : 0 };
    var d = parseDate(t);
    if (d != null) return { kind: 'date', v: d };
    var a = parseAgo(t);
    if (a != null) return { kind: 'ago', v: a };
    if (NUM_START.test(t)) { var n = parseNumber(t); if (n != null) return { kind: 'num', v: n }; }
    return { kind: 'text', v: t };
  }

  // Map visual column index -> the cell covering it (handles colspan).
  function cellAt(tr, col) {
    var i = 0;
    for (var k = 0; k < tr.cells.length; k++) {
      var c = tr.cells[k], span = c.colSpan || 1;
      if (col >= i && col < i + span) return span > 1 ? null : c;
      i += span;
    }
    return null;
  }

  function dataRows(table) {
    var out = [];
    [].forEach.call(table.tBodies, function (tb) {
      [].forEach.call(tb.rows, function (tr) { if (!tr.classList.contains('grp')) out.push(tr); });
    });
    return out;
  }

  // A column sorts as values (not text) when most of its present cells do.
  function columnType(rows, col) {
    var counts = { value: 0, text: 0 };
    rows.forEach(function (tr) {
      var r = read(cellAt(tr, col));
      if (r.kind === 'missing') return;
      counts[r.kind === 'text' ? 'text' : 'value']++;
    });
    return counts.value >= counts.text && counts.value > 0 ? 'value' : 'text';
  }

  function keyFor(table) {
    var host = table.closest('[id]');
    var heads = [].map.call(headerCells(table), function (th) {
      return th.dataset.sortLabel != null ? th.dataset.sortLabel : clean(th.textContent);   // label without the arrow
    }).join('|');
    return (host ? host.id : location.pathname) + '::' + heads;
  }

  function headerCells(table) {
    var thead = table.tHead;
    if (!thead || !thead.rows.length) return [];
    return [].slice.call(thead.rows[thead.rows.length - 1].cells);
  }

  // ---- sorting ------------------------------------------------------------
  function apply(table, col, dir) {
    var rows = dataRows(table);
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var ths = headerCells(table);
    ths.forEach(function (th, i) {
      var ind = th.querySelector('.sort-ind');
      if (i === col && dir) {
        th.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : 'descending');
        if (ind) ind.textContent = dir === 'asc' ? '↑' : '↓';
      } else {
        th.removeAttribute('aria-sort');
        if (ind) ind.textContent = '↕';
      }
    });
    var groups = [].slice.call(table.querySelectorAll('tbody tr.grp'));

    if (!dir) {   // restore original order and group headers
      var all = [].slice.call(tbody.rows).sort(function (a, b) { return (+a.dataset.sortI) - (+b.dataset.sortI); });
      all.forEach(function (tr) { tbody.appendChild(tr); });
      groups.forEach(function (g) { g.hidden = false; });
      return;
    }
    var type = columnType(rows, col);
    var sign = dir === 'asc' ? 1 : -1;
    var keyed = rows.map(function (tr) { return { tr: tr, r: read(cellAt(tr, col)), i: +tr.dataset.sortI }; });
    keyed.sort(function (a, b) {
      var am = a.r.kind === 'missing' || (type === 'value' && a.r.kind === 'text');
      var bm = b.r.kind === 'missing' || (type === 'value' && b.r.kind === 'text');
      if (am || bm) return am === bm ? a.i - b.i : (am ? 1 : -1);
      var c = type === 'value'
        ? (a.r.v - b.r.v)
        : String(a.r.v).localeCompare(String(b.r.v), undefined, { numeric: true, sensitivity: 'base' });
      return c ? c * sign : a.i - b.i;
    });
    groups.forEach(function (g) { g.hidden = true; });
    keyed.forEach(function (k) { tbody.appendChild(k.tr); });
  }

  function cycle(table, col) {
    var key = keyFor(table), cur = state[key] || {};
    var rows = dataRows(table);
    var th = table.querySelector('th[data-sort-col="' + col + '"]');
    var first = (th && th.getAttribute('data-sort-first')) || (columnType(rows, col) === 'value' ? 'desc' : 'asc');
    var next;
    if (cur.col !== col || !cur.dir) next = first;
    else if (cur.dir === first) next = first === 'asc' ? 'desc' : 'asc';
    else next = null;
    state[key] = { col: col, dir: next };
    apply(table, col, next);
  }

  // ---- decoration ---------------------------------------------------------
  function decorate(table) {
    if (table.dataset.sortReady || table.hasAttribute('data-nosort')) return;
    var ths = headerCells(table);
    if (!ths.length || !table.tBodies.length) return;
    table.dataset.sortReady = '1';
    var idx = 0;
    [].forEach.call(table.tBodies, function (tb) {
      [].forEach.call(tb.rows, function (tr) { tr.dataset.sortI = idx++; });
    });

    ths.forEach(function (th) { th.dataset.sortLabel = clean(th.textContent); });
    var col = 0;
    ths.forEach(function (th) {
      var c = col;
      col += th.colSpan || 1;
      if ((th.colSpan || 1) > 1 || !clean(th.textContent)) return;   // spanning or empty header: not a sort column
      var label = clean(th.textContent);
      th.classList.add('sort-ready');
      th.setAttribute('data-sort-col', c);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sort-btn';
      btn.setAttribute('aria-label', 'Sort by ' + label);
      var ind = document.createElement('span');
      ind.className = 'sort-ind';
      ind.setAttribute('aria-hidden', 'true');
      ind.textContent = '↕';
      if (th.querySelector('a')) {
        th.appendChild(document.createTextNode(' '));
        btn.appendChild(ind);
        th.appendChild(btn);
      } else {
        while (th.firstChild) btn.appendChild(th.firstChild);
        btn.appendChild(ind);
        th.appendChild(btn);
      }
      th.addEventListener('click', function (e) {
        if (e.target.closest('a')) return;            // header links still navigate
        e.preventDefault();
        e.stopPropagation();
        cycle(table, c);
      });
    });

    var saved = state[keyFor(table)];                 // re-apply after a live redraw
    if (saved && saved.dir) apply(table, saved.col, saved.dir);
  }

  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.tagName === 'TABLE') decorate(root);
    else [].forEach.call(root.querySelectorAll('table'), decorate);
  }

  function init() {
    injectStyle();
    scan(document.body);
    if (window.MutationObserver) {
      new MutationObserver(function (muts) {
        muts.forEach(function (m) { [].forEach.call(m.addedNodes, scan); });
      }).observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
