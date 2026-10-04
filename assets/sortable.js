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

/* Phone layout for tables. Any .tbl that is wider than its box on a narrow
 * screen turns into stacked cards: the first cell becomes the card title and
 * every other cell shows its column name above the value. Cells with nothing
 * in them ("–") are dropped on phones so a card never reads as a row of
 * dashes. Sortable tables get a "Sort by" menu, since the header row is hidden.
 * Opt a table out with data-nostack. Works on the plays site (.tbl) and the
 * live desk (.atable); the CSS is injected here so both stylesheets get it. */
(function () {
  'use strict';
  var MAX = 640;
  var NIL = /^(|–|—|-|n\/a)$/i;
  var lastW = (typeof WeakMap === 'function') ? new WeakMap() : null;
  var SEL = 'table.tbl, table.atable';
  var CSS = '.stack-sort{display:none}@media (max-width:640px){.stack-sort{display:flex;align-items:center;gap:8px;align-self:flex-start;margin-bottom:8px;font-size:12.5px;color:var(--muted)}.stack-sort[hidden]{display:none}.stack-sort select{font:500 13px var(--ui,inherit);color:var(--ink,var(--text));background:var(--panel-2);border:1px solid var(--line-2,var(--border));border-radius:8px;padding:6px 8px;max-width:70vw}table.stacked thead{display:none}table.stacked,table.stacked tbody{display:block;width:100%}table.stacked tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 14px;padding:12px 14px;border-bottom:1px solid var(--line,var(--border));position:relative}table.stacked tr:last-child{border-bottom:none}table.stacked td,table.stacked tbody th{display:block;min-width:0!important;padding:0;border:0;text-align:left;white-space:normal;position:static;background:none}table.stacked td::before,table.stacked tbody th::before{content:attr(data-label);display:block;margin-bottom:3px;font:600 10.5px/1.25 var(--data,ui-monospace,monospace);letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}table.stacked td[data-label=""]::before,table.stacked tbody th[data-label=""]::before{content:none}table.stacked tr>:first-child{grid-column:1/-1;font-size:14px}table.stacked td.wide,table.stacked td.why-col{grid-column:1/-1}table.stacked td.nil{display:none}table.stacked tbody tr:hover td{background:none}table.stacked tr.stack-grp,table.stacked tr.grp{display:block;padding:0;background:var(--bg-2)}table.stacked tr.stack-grp td,table.stacked tr.grp td{display:block;padding:8px 14px}table.stacked tr.stack-grp td:empty,table.stacked tr.grp td:empty{display:none}table.stacked .consensus{display:flex;flex-direction:column;align-items:flex-start;gap:5px;white-space:nowrap}table.stacked .fam-cell a{display:flex;flex-direction:column;align-items:flex-start;gap:4px;white-space:normal}table.stacked .fillbar{width:100%;max-width:120px}table.stacked .stick{min-width:0}table.stacked td.nowrap,table.stacked td .nowrap,table.stacked td.r,table.stacked td.c{white-space:normal;text-align:left}table.stacked td:has(>.wl-x:only-child){position:absolute;top:10px;right:12px}table.stacked td:has(>.wl-x:only-child)::before{content:none}}';

  function injectStyle() {
    if (document.getElementById('stack-css')) return;
    var st = document.createElement('style');
    st.id = 'stack-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function clean(t) { return (t || '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim(); }

  function headLabels(table) {
    var head = table.tHead;
    if (!head || !head.rows.length) return null;
    var out = [];
    [].forEach.call(head.rows[head.rows.length - 1].cells, function (th) {
      var a = th.querySelector('a:not(.sort-btn)');
      var txt;
      if (a) txt = clean(a.textContent);
      else {
        var c = th.cloneNode(true);
        [].forEach.call(c.querySelectorAll('.sort-ind, .sym-sub'), function (x) { x.remove(); });
        txt = clean(c.textContent);
      }
      for (var i = 0; i < (th.colSpan || 1); i++) out.push(txt);
    });
    return out;
  }

  function label(table) {
    var labels = headLabels(table);
    if (!labels) return false;
    [].forEach.call(table.tBodies, function (tb) {
      [].forEach.call(tb.rows, function (tr) {
        if (tr.dataset.stackLbl) return;
        tr.dataset.stackLbl = '1';
        var spans = [].some.call(tr.cells, function (c) { return (c.colSpan || 1) > 1; });
        if (spans) { tr.classList.add('stack-grp'); return; }
        var col = 0;
        [].forEach.call(tr.cells, function (c) {
          c.setAttribute('data-label', col === 0 ? '' : (labels[col] || ''));
          var t = clean(c.textContent);
          if (col > 0 && NIL.test(t) && !c.querySelector('input, select, button, img, svg, .fillbar, .pill')) c.classList.add('nil');
          if (col > 0 && t.length > 26) c.classList.add('wide');
          col += c.colSpan || 1;
        });
      });
    });
    return true;
  }

  function sortMenu(table) {
    if (table.dataset.stackMenu || table.hasAttribute('data-nosort') || table.classList.contains('st-tbl')) return;
    var ths = [].slice.call(table.querySelectorAll('thead th[data-sort-col]'));
    if (ths.length < 2) return;
    table.dataset.stackMenu = '1';
    var wrap = table.closest('.tbl-wrap') || table;
    var box = document.createElement('label');
    box.className = 'stack-sort';
    var sel = document.createElement('select');
    sel.innerHTML = '<option value="">Original order</option>' + ths.map(function (th) {
      var lb = clean((th.querySelector('a:not(.sort-btn)') || th).textContent.replace('↕', '').replace('↑', '').replace('↓', ''));
      return '<option value="' + th.getAttribute('data-sort-col') + '">' + lb.replace(/</g, '&lt;') + '</option>';
    }).join('');
    sel.addEventListener('change', function () {
      var on = table.querySelector('thead th[aria-sort]');
      if (!sel.value) { for (var i = 0; on && i < 3; i++) { on.click(); on = table.querySelector('thead th[aria-sort]'); } return; }
      var th = table.querySelector('thead th[data-sort-col="' + sel.value + '"]');
      if (!th) return;
      th.click();
      if (!th.hasAttribute('aria-sort')) th.click();
    });
    box.appendChild(document.createTextNode('Sort by '));
    box.appendChild(sel);
    wrap.parentNode.insertBefore(box, wrap);
  }

  function fit(table) {
    if (table.hasAttribute('data-nostack') || table.classList.contains('fund-tbl')) return;
    var wrap = table.closest('.tbl-wrap') || table.parentElement;
    if (!wrap || !wrap.clientWidth) return;
    var was = table.classList.contains('stacked');
    table.classList.remove('stacked');
    var need = window.innerWidth <= MAX && table.scrollWidth > wrap.clientWidth + 4;
    if (need && label(table)) {
      table.classList.add('stacked');
      sortMenu(table);
    }
    if (was !== table.classList.contains('stacked')) {
      var m = wrap.previousElementSibling;
      if (m && m.classList.contains('stack-sort')) m.hidden = !table.classList.contains('stacked');
    }
  }

  var ro = window.ResizeObserver ? new ResizeObserver(function (ents) {
    ents.forEach(function (en) {
      var w = Math.round(en.contentRect.width);
      if (lastW && lastW.get(en.target) === w) return;
      if (lastW) lastW.set(en.target, w);
      var t = en.target.querySelector(SEL);
      if (t) fit(t);
    });
  }) : null;

  function watch(table) {
    if (!table.matches || !table.matches(SEL) || table.dataset.stackWatch) return;
    table.dataset.stackWatch = '1';
    var wrap = table.closest('.tbl-wrap') || table.parentElement;
    if (ro && wrap) ro.observe(wrap);
    fit(table);
  }

  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.tagName === 'TABLE') watch(root);
    else [].forEach.call(root.querySelectorAll(SEL), watch);
    if (root.tagName === 'TR' || root.tagName === 'TBODY') {        // rows added to a table already on the page
      var t = root.closest(SEL);
      if (t && !t.dataset.stackQ) {
        t.dataset.stackQ = '1';
        requestAnimationFrame(function () { delete t.dataset.stackQ; fit(t); if (t.classList.contains('stacked')) label(t); });
      }
    }
  }

  function init() {
    injectStyle();
    scan(document.body);
    if (window.MutationObserver) {
      new MutationObserver(function (muts) {
        muts.forEach(function (m) { [].forEach.call(m.addedNodes, scan); });
      }).observe(document.body, { childList: true, subtree: true });
    }
    var tmr;
    window.addEventListener('resize', function () {
      clearTimeout(tmr);
      tmr = setTimeout(function () { [].forEach.call(document.querySelectorAll(SEL), fit); }, 150);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
