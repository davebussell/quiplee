/* mine.js: "My stocks" on every page (loaded after account.js).
 *
 * One list. Signed in, it's the stocks your account follows (the ones your signal emails are about);
 * signed out, it's this browser's watchlist (quiplee.watch.v1). Any element marked data-mine whose rows
 * (tbody tr or li) carry data-sym gets:
 *   - a star in each row's first cell to add or remove the stock (unless data-mine="filter": the list
 *     draws its own, as the screener does);
 *   - an "All · My stocks" switch just above it. "My stocks" hides every other row (class mine-out) and
 *     any group heading left with nothing under it.
 * The switch is one setting for the whole site (bp.mine.only), so the stock list, the home board, the
 * play pages and the screener narrow together. Rows a list adds later are picked up.
 *
 *   window.BPMine: ready(fn), has(sym), list(), toggle(sym[, on]) -> Promise, onChange(fn), only(), setOnly(on), signedIn()
 *
 * Other scripts announce a change with the bp:follow event ({sym, on}); this one listens for it and sends it. */
(function () {
  'use strict';
  var WKEY = 'quiplee.watch.v1', OKEY = 'bp.mine.only';
  var A = window.BPAuth, acct = !!(A && A.signedIn());
  var mine = {}, loaded = false, waiting = [], subs = [], boxes = [], mail = false;

  function lget(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function lset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: lasts until reload */ } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function localItems() { var v = lget(WKEY); return (v && v.items) || []; }
  function setLocal(sym, on) {
    var v = lget(WKEY) || {};
    v.items = (v.items || []).filter(function (x) { return x.sym !== sym; });
    if (on) v.items.push({ sym: sym });
    lset(WKEY, v);
  }
  function toast(html) {
    var t = document.querySelector('.scr-toast');
    if (!t) { t = document.createElement('div'); t.className = 'scr-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.innerHTML = html;
    t.classList.add('on');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('on'); }, 5200);
  }
  function changed() {
    subs.forEach(function (f) { try { f(); } catch (e) { /* keep going */ } });
    boxes.forEach(paint);
  }

  // ------------------------------------------------------------ the list
  function load() {
    localItems().forEach(function (x) { mine[x.sym] = true; });
    if (!acct) return done();
    A.me().then(function (a) {
      if (a && a.signed_in) { mail = !!(a.email && a.email_ok && a.alerts && a.alerts.on); mine = {}; (a.follow || []).forEach(function (s) { mine[s] = true; }); }
      else acct = false;
      done();
    }, done);
  }
  function done() {
    loaded = true;
    var w = waiting;
    waiting = [];
    w.forEach(function (f) { try { f(); } catch (e) { /* keep going */ } });
    changed();
  }
  function set(sym, on) { if (on) mine[sym] = true; else delete mine[sym]; }
  var M = window.BPMine = {
    ready: function (f) { if (loaded) f(); else waiting.push(f); },
    has: function (sym) { return !!mine[sym]; },
    list: function () { return Object.keys(mine); },
    signedIn: function () { return acct; },
    only: function () { return lget(OKEY) === true; },
    setOnly: function (on) { lset(OKEY, !!on); changed(); },
    onChange: function (f) { subs.push(f); },
    /** Add several at once (a pasted list, a broker file): one request, one note. Resolves to the syms added. */
    addMany: function (syms, quiet) {
      syms = (syms || []).filter(function (x) { return x && !mine[x]; });
      if (!syms.length) return Promise.resolve([]);
      syms.forEach(function (x) { set(x, true); setLocal(x, true); });
      changed();
      if (!acct) return Promise.resolve(syms);
      return A.post('follow', { add: syms }).then(function (j) {
        if (!j || !j.ok) {
          syms.forEach(function (x) { set(x, false); });
          changed();
          toast(esc((j && j.error) || "Those didn't save to your account. Try again."));
          return [];
        }
        mine = {};
        (j.follow || []).forEach(function (x) { mine[x] = true; });
        changed();
        var got = syms.filter(function (x) { return mine[x]; });
        if (!quiet && got.length) toast('Added ' + got.length + ' to <a href="/me/#stocks">My stocks</a>.');
        return got;
      });
    },
    /** Add (on true) or remove a stock; signed in it goes to the account, else to this browser. */
    toggle: function (sym, on, label) {
      if (on == null) on = !mine[sym];
      set(sym, on);
      setLocal(sym, on);
      document.dispatchEvent(new CustomEvent('bp:follow', { detail: { sym: sym, on: on, from: 'mine' } }));
      changed();
      var name = esc(label || sym);
      if (!acct) {
        toast(on ? 'Saved ' + name + ' on this browser. <a href="/me/">Log in or create a free account</a> to keep My stocks everywhere and get an email when your signal on it flips.'
          : 'Removed ' + name + '.');
        return Promise.resolve({ ok: true });
      }
      return A.follow(sym, on).then(function (j) {
        if (!j || !j.ok) {
          set(sym, !on);
          setLocal(sym, !on);
          document.dispatchEvent(new CustomEvent('bp:follow', { detail: { sym: sym, on: !on, from: 'mine' } }));
          changed();
          toast(esc((j && j.error) || "That didn't save. Try again."));
          return j || {};
        }
        toast(on ? 'Added ' + name + ' to <a href="/me/#stocks">My stocks</a>.' + (mail ? ' You’ll get an email the evening your signal on it flips.' : ' <a href="/me/#alerts">Switch on email alerts</a> to hear when your signal on it flips.') : 'Removed ' + name + ' from My stocks.');
        return j;
      });
    }
  };
  // a follow button elsewhere on the page (the stock page's, the screener's) changed the list
  document.addEventListener('bp:follow', function (ev) {
    var d = ev.detail || {};
    if (!d.sym || d.from === 'mine') return;
    set(d.sym, !!d.on);
    changed();
  });

  // ------------------------------------------------------------ lists marked data-mine
  function rowsOf(box) { return [].slice.call(box.querySelectorAll('tbody tr[data-sym], li[data-sym]')); }
  function label(tr) {
    var b = tr.querySelector('.sym, .me-sym b, b, a');
    return b ? b.textContent.trim() : tr.getAttribute('data-sym');
  }
  function addStar(tr) {
    if (tr._mineStar) return;
    var cell = tr.cells ? tr.cells[0] : tr;
    if (!cell) return;
    // the stock column sorts on the name, not on the star (sortable.js reads data-v first)
    if (tr.cells && !cell.hasAttribute('data-v')) cell.setAttribute('data-v', cell.textContent.replace(/\s+/g, ' ').trim());
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'mine-star';
    b.setAttribute('data-mine-star', tr.getAttribute('data-sym'));
    cell.insertBefore(b, cell.firstChild);
    tr._mineStar = b;
  }
  function paintStar(tr) {
    var b = tr._mineStar;
    if (!b) return;
    var sym = tr.getAttribute('data-sym'), on = !!mine[sym], name = label(tr), glyph = on ? '★' : '☆';
    if (b.textContent === glyph && b._label === name) return;   // unchanged: touch nothing (the row watcher sees every text change)
    b._label = name;
    b.textContent = glyph;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', String(on));
    b.setAttribute('aria-label', (on ? 'Remove ' + name + ' from' : 'Add ' + name + ' to') + ' My stocks');
    b.title = on ? 'In My stocks' : 'Add to My stocks';
  }
  function paint(box) {
    var only = M.only(), rows = rowsOf(box), n = 0;
    rows.forEach(function (tr) {
      var on = !!mine[tr.getAttribute('data-sym')];
      if (on) n++;
      tr.classList.toggle('mine-out', only && !on);
      paintStar(tr);
    });
    // a group heading with nothing left under it hides too
    [].forEach.call(box.querySelectorAll('tbody'), function (tb) {
      var head = null, any = false;
      [].forEach.call(tb.rows, function (tr) {
        if (tr.classList.contains('grp') || tr.classList.contains('stack-grp')) {
          if (head) head.classList.toggle('mine-out', only && !any);
          head = tr;
          any = false;
        } else if (!tr.classList.contains('mine-out')) any = true;
      });
      if (head) head.classList.toggle('mine-out', only && !any);
    });
    if (window.BPStack) [].forEach.call(box.tagName === 'TABLE' ? [box] : box.querySelectorAll('table'), window.BPStack.recap);   // the phone's "Show all" cap counts what's showing
    var bar = box._mineBar;
    if (bar) {
      [].forEach.call(bar.querySelectorAll('[data-mine-only]'), function (b) { b.setAttribute('aria-pressed', String((b.getAttribute('data-mine-only') === '1') === only)); });
      var c = bar.querySelector('[data-mine-n]');
      if (c) c.textContent = loaded ? String(n) : '';
    }
    if (box._mineEmpty) {
      box._mineEmpty.hidden = !(only && loaded && n === 0);
      box._mineEmpty.innerHTML = M.list().length
        ? 'None of My stocks are in this list. <button type="button" class="linkish" data-mine-only="0">Show all</button>'
        : 'My stocks is empty. Tap ☆ on any stock to add it' + (acct ? ', or <a href="/me/#find">find stocks to add</a>.' : ', or <a href="/me/">log in</a> to bring your list.') + ' <button type="button" class="linkish" data-mine-only="0">Show all</button>';
    }
  }
  function enhance(box) {
    if (!box._mine) {
      box._mine = true;
      boxes.push(box);
      var anchor = box.closest('.tbl-wrap') || box;
      if (box.getAttribute('data-mine') !== 'bare') {
        var bar = document.createElement('div');
        bar.className = 'mine-bar';
        bar.setAttribute('role', 'group');
        bar.setAttribute('aria-label', 'Which stocks to show');
        bar.innerHTML = '<button type="button" class="chip-btn" data-mine-only="0">All</button>' +
          '<button type="button" class="chip-btn" data-mine-only="1">★ My stocks <span class="muted" data-mine-n></span></button>';
        anchor.parentNode.insertBefore(bar, anchor);
        box._mineBar = bar;
        var empty = document.createElement('p');
        empty.className = 'mine-empty small';
        empty.hidden = true;
        anchor.parentNode.insertBefore(empty, anchor.nextSibling);
        box._mineEmpty = empty;
      }
      if (window.MutationObserver) {
        // only rows the list adds or moves (a redraw, a re-sort) need a star and a repaint
        new MutationObserver(function (muts) {
          var rows = muts.some(function (m) {
            return [].some.call(m.addedNodes, function (nd) {
              return nd.nodeType === 1 && (nd.matches('tr[data-sym], li[data-sym]') || !!(nd.querySelector && nd.querySelector('tr[data-sym], li[data-sym]')));
            });
          });
          if (rows) { stars(box); paint(box); }
        }).observe(box, { childList: true, subtree: true });
      }
    }
    stars(box);
    paint(box);
  }
  function stars(box) { if (box.getAttribute('data-mine') !== 'filter') rowsOf(box).forEach(addStar); }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-mine-star], [data-mine-only]') : null;
    if (!t) return;
    e.preventDefault();
    e.stopPropagation();
    if (t.hasAttribute('data-mine-only')) { M.setOnly(t.getAttribute('data-mine-only') === '1'); return; }
    var tr = t.closest('[data-sym]');
    M.toggle(t.getAttribute('data-mine-star'), null, tr ? label(tr) : null);
  }, true);

  function start() {
    [].forEach.call(document.querySelectorAll('[data-mine]'), enhance);
    load();
  }
  if (location.protocol === 'file:') return;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
