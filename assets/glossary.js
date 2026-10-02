/* glossary.js — plain-English definitions on hover/tap for every underlined term.
 *
 * 1) Bubble: hovering (or keyboard-focusing) a .term shows its short
 *    definition with a link to the full entry. On touch screens the first tap
 *    shows the bubble and the second follows the link.
 * 2) Live desk: the desk redraws its feed every few seconds, so terms there are
 *    linked in the browser from data/glossary.json. They become <span
 *    class="term"> (a tap opens the bubble instead of the story card).
 * 3) Glossary page: the search box filters entries as you type.
 * Zero dependencies; styles are injected so it works on every page type. */
(function () {
  'use strict';
  var SCRIPT = document.currentScript;
  var bubble, tipEl, moreEl, current = null, hideTimer = null, showTimer = null;
  var coarse = window.matchMedia && window.matchMedia('(hover: none)').matches;

  function injectStyle() {
    if (document.getElementById('gloss-css')) return;
    var s = document.createElement('style');
    s.id = 'gloss-css';
    s.textContent =
      '.term{color:inherit;text-decoration:underline dotted;text-decoration-thickness:1.5px;text-underline-offset:3px;' +
      'text-decoration-color:var(--violet-ink,var(--violet-2,#a99dff));cursor:help}' +
      'a.term:hover,.term:hover,.term.on{color:var(--violet-ink,var(--violet-2,#a99dff));text-decoration-style:solid}' +
      '.term:focus-visible{outline:2px solid var(--violet-ink,var(--violet-2,#a99dff));outline-offset:2px;border-radius:3px}' +
      '.gl-bubble{position:fixed;z-index:200;max-width:min(330px,calc(100vw - 24px));padding:12px 14px;border-radius:10px;' +
      'background:var(--panel-2,var(--panel,#1a2233));color:var(--ink,var(--text,#eef2f9));' +
      'border:1px solid var(--line-2,var(--border,#2d3952));box-shadow:0 16px 40px -14px rgba(0,0,0,.75);' +
      'font:13.5px/1.5 var(--ui,Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif);text-transform:none;letter-spacing:0;' +
      'opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s;pointer-events:none}' +
      '.gl-bubble.show{opacity:1;transform:none;pointer-events:auto}' +
      '.gl-bubble p{margin:0}' +
      '.gl-bubble a{display:inline-block;margin-top:8px;font-weight:600;font-size:12.5px;color:var(--violet-ink,var(--violet-2,#a99dff));text-decoration:none}' +
      '.gl-bubble a:hover{text-decoration:underline}' +
      '@media (prefers-reduced-motion:reduce){.gl-bubble{transition:none}}';
    document.head.appendChild(s);
  }

  // ---------------------------------------------------------------- bubble
  function ensureBubble() {
    if (bubble) return;
    bubble = document.createElement('div');
    bubble.className = 'gl-bubble';
    bubble.setAttribute('role', 'tooltip');
    bubble.id = 'gl-bubble';
    tipEl = document.createElement('p');
    moreEl = document.createElement('a');
    bubble.appendChild(tipEl);
    bubble.appendChild(moreEl);
    document.body.appendChild(bubble);
    bubble.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    bubble.addEventListener('mouseleave', function () { scheduleHide(); });
  }

  function hrefOf(el) { return el.getAttribute('href') || el.getAttribute('data-href') || ''; }

  function place(el) {
    var r = el.getBoundingClientRect(), vw = window.innerWidth, vh = window.innerHeight;
    bubble.style.left = '0px'; bubble.style.top = '0px';
    var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
    var left = Math.min(Math.max(12, r.left + r.width / 2 - bw / 2), vw - bw - 12);
    var top = r.bottom + 8;
    if (top + bh > vh - 8 && r.top - bh - 8 > 8) top = r.top - bh - 8;
    bubble.style.left = left + 'px';
    bubble.style.top = Math.max(8, top) + 'px';
  }

  function show(el) {
    ensureBubble();
    clearTimeout(hideTimer);
    if (current && current !== el) current.classList.remove('on');
    current = el;
    el.classList.add('on');
    tipEl.textContent = el.getAttribute('data-tip') || '';
    var href = hrefOf(el);
    var toLesson = href.indexOf('/learn/') !== -1 && href.indexOf('/learn/glossary/') === -1 && href.charAt(0) !== '#';
    moreEl.textContent = toLesson ? 'Read the lesson →' : 'Full definition →';
    moreEl.href = href || '#';
    moreEl.hidden = !href;
    el.setAttribute('aria-describedby', 'gl-bubble');
    bubble.classList.add('show');
    place(el);
  }

  function hide() {
    clearTimeout(showTimer);
    if (!bubble) return;
    bubble.classList.remove('show');
    if (current) { current.classList.remove('on'); current.removeAttribute('aria-describedby'); }
    current = null;
  }
  function scheduleHide() { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 180); }

  function termOf(t) { return t && t.closest ? t.closest('.term') : null; }

  function wire() {
    document.addEventListener('mouseover', function (e) {
      var el = termOf(e.target);
      if (!el || coarse) return;
      clearTimeout(hideTimer); clearTimeout(showTimer);
      showTimer = setTimeout(function () { show(el); }, 120);
    });
    document.addEventListener('mouseout', function (e) {
      var el = termOf(e.target);
      if (!el || coarse) return;
      if (e.relatedTarget && (el.contains(e.relatedTarget) || (bubble && bubble.contains(e.relatedTarget)))) return;
      clearTimeout(showTimer);
      scheduleHide();
    });
    document.addEventListener('focusin', function (e) {
      var el = termOf(e.target);
      var kb = true;
      try { kb = el && el.matches(':focus-visible'); } catch (_) { kb = true; }
      if (el && kb) show(el);   // keyboard focus only; mouse and touch go through click
    });
    document.addEventListener('focusout', function (e) { if (termOf(e.target)) scheduleHide(); });
    document.addEventListener('click', function (e) {
      var el = termOf(e.target);
      if (el) {
        var isLink = el.tagName === 'A';
        // spans (desk) and first tap on touch screens: open the bubble, don't navigate
        if (!isLink || (coarse && current !== el)) {
          e.preventDefault();
          e.stopPropagation();
          show(el);   // clicking elsewhere or Escape closes it
        }
        return;
      }
      if (bubble && !bubble.contains(e.target)) hide();
    }, true);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') hide();
      var el = termOf(e.target);
      if (el && el.tagName !== 'A' && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); show(el); }
    });
    window.addEventListener('scroll', function () {
      if (!current) return;
      var r = current.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight || !document.body.contains(current)) hide(); else place(current);
    }, { passive: true });
    window.addEventListener('resize', function () { if (current) place(current); });
  }

  // ---------------------------------------------------------- desk linking
  var DESK_AREAS = ['#feed', '#screener-feed', '#alerts-list', '#analyst-board', '#portfolio-board',
                    '#detail-body', '#live-mini', '#scoreboard', '#intro-strip', '#topic-grid'];
  var SKIP = 'a,button,input,select,option,textarea,label,script,style,h1,h2,th,code,.term,.pill,.badge-count,.tab,.logo,.mode-pill,.market-pill';

  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'); }

  function buildMatcher(entries) {
    var ci = [], cs = [], map = {};
    entries.forEach(function (g) {
      g.aliases.forEach(function (a) {
        var sens = a !== a.toLowerCase();
        map[(sens ? 'S:' + a : 'I:' + a.toLowerCase()).replace(/\s+/g, ' ')] = g;
        (sens ? cs : ci).push(a);
      });
    });
    function rx(list, flags) {
      if (!list.length) return null;
      list.sort(function (x, y) { return y.length - x.length; });
      return new RegExp('(?<![\\w\\-&])(?:' + list.map(esc).join('|') + ')(?![\\w\\-])', flags);
    }
    return { ci: rx(ci, 'gi'), cs: rx(cs, 'g'), map: map };
  }

  function matchesIn(text, M) {
    var out = [];
    [[M.cs, 'S:'], [M.ci, 'I:']].forEach(function (pair) {
      var re = pair[0]; if (!re) return;
      re.lastIndex = 0;
      var m;
      while ((m = re.exec(text))) {
        var key = pair[1] + (pair[1] === 'I:' ? m[0].toLowerCase() : m[0]).replace(/\s+/g, ' ');
        var g = M.map[key];
        if (g) out.push({ s: m.index, e: m.index + m[0].length, g: g });
      }
    });
    out.sort(function (a, b) { return a.s - b.s || (b.e - b.s) - (a.e - a.s); });
    var keep = [], last = -1;
    out.forEach(function (x) { if (x.s >= last) { keep.push(x); last = x.e; } });
    return keep;
  }

  function linkArea(area, M) {
    var used = {};
    [].forEach.call(area.querySelectorAll('.term[data-slug]'), function (t) { used[t.getAttribute('data-slug')] = 1; });
    var walker = document.createTreeWalker(area, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        var p = n.parentElement;
        return p && !p.closest(SKIP) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (n) {
      var text = n.nodeValue, ms = matchesIn(text, M).filter(function (x) { return !used[x.g.slug]; });
      if (!ms.length) return;
      var frag = document.createDocumentFragment(), pos = 0;
      ms.forEach(function (x) {
        if (used[x.g.slug]) return;
        used[x.g.slug] = 1;
        frag.appendChild(document.createTextNode(text.slice(pos, x.s)));
        var sp = document.createElement('span');
        sp.className = 'term';
        sp.tabIndex = 0;
        sp.setAttribute('role', 'button');
        sp.setAttribute('data-slug', x.g.slug);
        sp.setAttribute('data-tip', x.g.tip);
        sp.setAttribute('data-href', x.g.href);
        sp.textContent = text.slice(x.s, x.e);
        frag.appendChild(sp);
        pos = x.e;
      });
      frag.appendChild(document.createTextNode(text.slice(pos)));
      n.parentNode.replaceChild(frag, n);
    });
  }

  function initDesk() {
    if (!document.getElementById('app-view') || !SCRIPT) return;
    var url = new URL('../data/glossary.json', SCRIPT.src).toString();
    fetch(url).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.terms) return;
      var M = buildMatcher(data.terms);
      DESK_AREAS.forEach(function (sel) {
        var area = document.querySelector(sel);
        if (!area) return;
        var pending = false;
        var run = function () { pending = false; linkArea(area, M); };
        run();
        new MutationObserver(function () {
          if (pending) return;
          pending = true;
          (window.queueMicrotask || setTimeout)(run);
        }).observe(area, { childList: true, subtree: true });
      });
    }).catch(function () { /* glossary is an enhancement; the desk works without it */ });
  }

  // ------------------------------------------------------- glossary search
  function initSearch() {
    var input = document.getElementById('gl-search');
    if (!input) return;
    var entries = [].slice.call(document.querySelectorAll('.gl-entry'));
    var topics = [].slice.call(document.querySelectorAll('.gl-topic'));
    var empty = document.getElementById('gl-empty');
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase(), any = false;
      var wordStart = new RegExp('(^|[^a-z0-9])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
      entries.forEach(function (el) {
        var hit = !q || el.getAttribute('data-search').indexOf(q) !== -1 || wordStart.test(el.textContent.toLowerCase());
        el.hidden = !hit; any = any || hit;
      });
      topics.forEach(function (t) { t.hidden = !t.querySelector('.gl-entry:not([hidden])'); });
      if (empty) empty.hidden = any;
    });
  }

  function init() { injectStyle(); wire(); initDesk(); initSearch(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
