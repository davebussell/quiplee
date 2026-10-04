/* learn.js — Be The Puck's interactive learning: lesson quizzes, flashcards,
 * "Call it" chart practice, the play quiz and the progress panel.
 * Progress lives in this browser's localStorage only (wrapped so private
 * windows and blocked storage just mean nothing is remembered). */
(function () {
  'use strict';

  // ------------------------------------------------------------ storage
  var KEY = 'quiplee.learn.v1';
  var mem = null;
  function load() {
    if (mem) return mem;
    try { mem = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { mem = {}; }
    mem.lessons = mem.lessons || {}; mem.cards = mem.cards || {}; mem.callit = mem.callit || { n: 0, right: 0, seen: {} };
    mem.pq = mem.pq || { best: null, rounds: 0 };
    return mem;
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(mem)); } catch (e) { /* storage blocked: keep in memory */ } }
  function lesson(slug) { var s = load(); s.lessons[slug] = s.lessons[slug] || {}; return s.lessons[slug]; }

  // ------------------------------------------------------------ helpers
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'html') n.innerHTML = attrs[k];
      else if (k === 'on') Object.keys(attrs.on).forEach(function (ev) { n.addEventListener(ev, attrs.on[ev]); });
      else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function shuffle(a) { a = a.slice(); for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function pick(a, n, not) { return shuffle(a.filter(function (x) { return not.indexOf(x) < 0; })).slice(0, n); }
  function pct(v) { var s = Math.abs(v * 100).toFixed(1) + '%'; return v > 0 ? '+' + s : v < 0 ? '−' + s : s; }
  function param(name) { var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(location.search); return m ? decodeURIComponent(m[1]) : null; }

  // ------------------------------------------------------------ lesson quizzes
  function initQuizzes() {
    [].forEach.call(document.querySelectorAll('.quiz[data-quiz]'), function (box) {
      var slug = box.getAttribute('data-quiz');
      var src = box.querySelector('script[type="application/json"]');
      var qs = JSON.parse(src.textContent);
      var body = box.querySelector('.quiz-body');
      function render() {
        body.textContent = '';
        var answered = 0, right = 0;
        var summary = el('div', { 'class': 'quiz-sum', 'aria-live': 'polite' });
        qs.forEach(function (q, qi) {
          var fs = el('fieldset', { 'class': 'quiz-q' });
          fs.appendChild(el('legend', { text: (qi + 1) + '. ' + q.q }));
          var opts = el('div', { 'class': 'quiz-opts' });
          var why = el('p', { 'class': 'quiz-why', hidden: '' });
          q.a.forEach(function (txt, ai) {
            var b = el('button', { type: 'button', 'class': 'quiz-opt', text: txt });
            b.addEventListener('click', function () {
              if (fs.classList.contains('done')) return;
              fs.classList.add('done');
              var ok = ai === q.c;
              answered++; if (ok) right++;
              [].forEach.call(opts.children, function (o, oi) {
                o.disabled = true;
                if (oi === q.c) o.classList.add('is-right');
                else if (oi === ai) o.classList.add('is-wrong');
              });
              why.textContent = (ok ? 'Right. ' : 'Not quite. ') + q.why;
              why.className = 'quiz-why ' + (ok ? 'ok' : 'no');
              why.hidden = false;
              if (answered === qs.length) {
                var L = lesson(slug);
                var best = L.quiz ? Math.max(L.quiz[0], right) : right;
                L.quiz = [best, qs.length]; L.read = L.read || Date.now(); save();
                summary.textContent = '';
                summary.appendChild(el('p', { 'class': 'h3', text: 'You got ' + right + ' of ' + qs.length + '.' }));
                summary.appendChild(el('button', { type: 'button', 'class': 'btn', text: 'Try again', on: { click: render } }));
              }
            });
            opts.appendChild(b);
          });
          fs.appendChild(opts); fs.appendChild(why);
          body.appendChild(fs);
        });
        body.appendChild(summary);
      }
      render();
    });
    var end = document.querySelector('[data-lesson-end]');
    if (end && 'IntersectionObserver' in window) {
      var slug = end.getAttribute('data-lesson-end');
      var io = new IntersectionObserver(function (ents) {
        ents.forEach(function (en) { if (en.isIntersecting) { var L = lesson(slug); if (!L.read) { L.read = Date.now(); save(); } io.disconnect(); } });
      });
      io.observe(end);
    }
  }

  // ------------------------------------------------------------ hub progress
  function initProgress() {
    var box = document.getElementById('progress');
    if (!box) return;
    var s = load();
    var links = document.querySelectorAll('[data-lesson-link]');
    var read = 0, qsum = 0, qn = 0;
    [].forEach.call(links, function (a) {
      var L = s.lessons[a.getAttribute('data-lesson-link')];
      if (!L) return;
      if (L.read) { read++; a.classList.add('is-read'); var d = a.querySelector('.lesson-done'); if (d) d.hidden = false; }
      if (L.quiz) { qsum += L.quiz[0]; qn += L.quiz[1]; var sc = a.querySelector('.lesson-score'); if (sc) sc.textContent = 'Quiz ' + L.quiz[0] + '/' + L.quiz[1]; }
    });
    var known = 0;
    Object.keys(s.cards).forEach(function (deck) { Object.keys(s.cards[deck]).forEach(function (id) { if (s.cards[deck][id] === 'k') known++; }); });
    var any = read || qn || known || s.callit.n || s.pq.rounds;
    if (!any) return;
    var grid = box.querySelector('.progress-grid');
    function tile(label, value, note) {
      return el('div', { 'class': 'tile' }, [el('span', { 'class': 'tile-label', text: label }), el('span', { 'class': 'tile-value', text: value }), el('span', { 'class': 'tile-note', text: note })]);
    }
    grid.appendChild(tile('Lessons read', read + ' of ' + links.length, read === links.length ? 'The whole course.' : 'Keep going in order.'));
    grid.appendChild(tile('Lesson quizzes', qn ? Math.round(100 * qsum / qn) + '%' : '–', qn ? qsum + ' of ' + qn + ' questions right (best tries).' : 'Each lesson ends with one.'));
    grid.appendChild(tile('Flashcards known', String(known), 'Across plays, terms and analysts.'));
    grid.appendChild(tile('Call it', s.callit.n ? Math.round(100 * s.callit.right / s.callit.n) + '%' : '–', s.callit.n ? s.callit.right + ' of ' + s.callit.n + ' charts read right.' : 'Read real charts.'));
    if (s.pq.rounds) grid.appendChild(tile('Play quiz best', s.pq.best + ' / 10', s.pq.rounds + ' round' + (s.pq.rounds > 1 ? 's' : '') + ' played.'));
    box.hidden = false;
    var reset = document.getElementById('progress-reset');
    if (reset) reset.addEventListener('click', function () { mem = { }; save(); location.reload(); });
  }

  // ------------------------------------------------------------ flashcards
  function initFlashcards() {
    var root = document.getElementById('flashcards');
    if (!root) return;
    var decks = JSON.parse(document.getElementById('flash-data').textContent);
    var stage = root.querySelector('.fc-stage');
    var count = root.querySelector('.fc-count');
    var tabs = root.querySelectorAll('[data-deck]');
    var s = load();
    var deckName = param('deck') || s.lastDeck || 'plays';
    if (!decks[deckName]) deckName = 'plays';
    var queue = [], cur = null, flipped = false;

    function marks() { s.cards[deckName] = s.cards[deckName] || {}; return s.cards[deckName]; }
    function build(startId) {
      var m = marks();
      var cards = decks[deckName].cards.filter(function (c) { return m[c.id] !== 'k'; });
      queue = shuffle(cards);
      if (startId) {
        var i = queue.findIndex(function (c) { return c.id === startId; });
        if (i > 0) queue.unshift(queue.splice(i, 1)[0]);
        if (i < 0) { var c = decks[deckName].cards.find(function (x) { return x.id === startId; }); if (c) queue.unshift(c); }
      }
    }
    function setTabs() {
      [].forEach.call(tabs, function (t) { t.setAttribute('aria-selected', t.getAttribute('data-deck') === deckName ? 'true' : 'false'); });
    }
    function updateCount() {
      var m = marks(), total = decks[deckName].cards.length;
      var known = decks[deckName].cards.filter(function (c) { return m[c.id] === 'k'; }).length;
      count.textContent = known + ' of ' + total + ' known · ' + queue.length + ' to go';
    }
    function show() {
      stage.textContent = '';
      updateCount();
      if (!queue.length) {
        stage.appendChild(el('div', { 'class': 'card fc-done' }, [
          el('p', { 'class': 'h3', text: 'You know every card in this deck.' }),
          el('p', { 'class': 'muted', text: 'Start it again, or try another deck.' }),
          el('button', { type: 'button', 'class': 'btn', text: 'Reset this deck', on: { click: function () { s.cards[deckName] = {}; save(); build(); show(); } } })]));
        return;
      }
      cur = queue[0]; flipped = false;
      var front = el('div', { 'class': 'fc-face fc-front' }, [el('p', { 'class': 'eyebrow', text: decks[deckName].name }), el('p', { 'class': 'fc-title', text: cur.front }), el('p', { 'class': 'muted small', text: cur.sub })]);
      var list = cur.list && cur.list.length ? el('ul', null, cur.list.map(function (x) { return el('li', { text: x }); })) : null;
      var back = el('div', { 'class': 'fc-face fc-back', hidden: '' }, [el('p', { 'class': 'eyebrow', text: cur.front }), el('p', { 'class': 'fc-text', text: cur.back }), list]);
      var card = el('div', { 'class': 'card fc-card', role: 'button', tabindex: '0', 'aria-label': 'Flip card' }, [front, back]);
      var more = el('a', { href: cur.href, 'class': 'small fc-more', text: 'Read more →', hidden: '' });
      card.addEventListener('click', flip);
      function flip() { flipped = !flipped; front.hidden = flipped; back.hidden = !flipped; more.hidden = !flipped; card.classList.toggle('is-flipped', flipped); }
      var again = el('button', { type: 'button', 'class': 'btn fc-again', text: '← Still learning', on: { click: function () { grade(false); } } });
      var got = el('button', { type: 'button', 'class': 'btn primary fc-got', text: 'Got it →', on: { click: function () { grade(true); } } });
      stage.appendChild(card);
      stage.appendChild(el('div', { 'class': 'fc-actions' }, [again, el('button', { type: 'button', 'class': 'btn', text: 'Flip', on: { click: flip } }), got]));
      stage.appendChild(more);
      stage._flip = flip;
    }
    function grade(ok) {
      if (!cur) return;
      var m = marks();
      queue.shift();
      if (ok) m[cur.id] = 'k';
      else { m[cur.id] = 'l'; queue.splice(Math.min(queue.length, 3 + Math.floor(Math.random() * 3)), 0, cur); }
      s.lastDeck = deckName; save(); show();
    }
    [].forEach.call(tabs, function (t) {
      t.addEventListener('click', function () { deckName = t.getAttribute('data-deck'); s.lastDeck = deckName; save(); setTabs(); build(); show(); });
    });
    document.addEventListener('keydown', function (e) {
      if (!cur || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
      if (e.key === ' ' || e.key === 'Enter') { if (document.activeElement.tagName === 'BUTTON' || document.activeElement.tagName === 'A') return; e.preventDefault(); stage._flip && stage._flip(); }
      else if (e.key === 'ArrowRight' || e.key === 'k') grade(true);
      else if (e.key === 'ArrowLeft' || e.key === 'j') grade(false);
    });
    setTabs(); build(location.hash ? location.hash.slice(1) : null); show();
  }

  // ------------------------------------------------------------ call it
  function drawInto(box, spec) {
    if (!window.QChart) return;
    window.QChart.draw(box, spec);
    if (window.ResizeObserver && !box._ro) {
      var w = box.clientWidth;
      box._ro = new ResizeObserver(function () { if (Math.abs(box.clientWidth - w) > 2) { w = box.clientWidth; window.QChart.draw(box, box._spec); } });
      box._ro.observe(box);
    }
    box._spec = spec;
  }
  function initCallIt() {
    var root = document.getElementById('callit');
    if (!root) return;
    var stage = root.querySelector('.ci-stage');
    var score = root.querySelector('.ci-score');
    var famSel = document.getElementById('ci-family'), playSel = document.getElementById('ci-play');
    var plays = root.getAttribute('data-plays');
    var items = [], round = { n: 0, right: 0 }, s = load();
    var want = param('play');
    if (want) playSel.value = want;

    function pool() {
      var f = famSel.value, p = playSel.value;
      return items.filter(function (it) { return (!f || it.family === f) && (!p || it.play === p); });
    }
    function setScore() {
      score.textContent = round.n ? 'This session: ' + round.right + ' of ' + round.n + ' right' : (s.callit.n ? 'All time: ' + s.callit.right + ' of ' + s.callit.n : '');
    }
    function next() {
      var p = pool();
      if (!p.length) { stage.textContent = ''; stage.appendChild(el('p', { 'class': 'muted', text: 'No charts match that filter yet. Try another play or family.' })); return; }
      var fresh = p.filter(function (it) { return !s.callit.seen[it.id]; });
      var it = shuffle(fresh.length ? fresh : p)[0];
      render(it);
    }
    function render(it) {
      stage.textContent = '';
      var head = el('div', { 'class': 'ci-head' }, [
        el('p', { 'class': 'eyebrow', text: it.bar + ' play · ' + it.by }),
        el('h2', { 'class': 'h2', text: it.name + ' on ' + it.stock }),
        el('p', { 'class': 'muted small', text: 'The chart stops at the ' + it.date + ' close (' + it.price + '). What did the play say at that close?' })]);
      var rules = el('div', { 'class': 'card prose ci-rules' }, [el('p', { 'class': 'eyebrow', text: 'The rule' }), el('ol', null, it.rules.map(function (r) { return el('li', { text: r }); }))]);
      var chartBox = el('div', { 'class': 'chart', role: 'img', 'aria-label': it.chart.label });
      var keyVar = { price: '--s-price', s1: '--s1', s2: '--s2', s3: '--s3', bench: '--s-bench' };
      var legend = el('div', { 'class': 'legend-row' }, it.chart.series.map(function (sr) {
        var k = el('span', { 'class': 'key' }, [el('i', { style: 'background:var(' + (keyVar[sr.role] || '--s1') + ')' }), sr.name]);
        return k;
      }));
      var cc = el('div', { 'class': 'card chart-card' }, [legend, chartBox]);
      var panelBox = null, pc = null;
      if (it.panel) { panelBox = el('div', { 'class': 'chart chart-sm', role: 'img', 'aria-label': it.panel.label }); pc = el('div', { 'class': 'card chart-card' }, [el('p', { 'class': 'small muted', text: it.panel.label }), panelBox]); }
      var bIn = el('button', { type: 'button', 'class': 'btn ci-in', html: '<span class="pill in">IN</span> Holding the stock' });
      var bOut = el('button', { type: 'button', 'class': 'btn ci-out', html: '<span class="pill out">OUT</span> In T-bills' });
      var ask = el('div', { 'class': 'ci-ask' }, [bIn, bOut]);
      var result = el('div', { 'class': 'ci-result', hidden: '' });
      stage.appendChild(head);
      stage.appendChild(el('div', { 'class': 'ci-grid' }, [el('div', { 'class': 'ci-charts' }, [cc, pc]), rules]));
      stage.appendChild(ask);
      stage.appendChild(result);
      var spec = JSON.parse(JSON.stringify(it.chart)); spec.cut = it.cut; spec.mark = it.cut;
      drawInto(chartBox, spec);
      if (panelBox) { var ps = JSON.parse(JSON.stringify(it.panel)); ps.cut = it.cut; ps.mark = it.cut; drawInto(panelBox, ps); }

      function answer(v) {
        bIn.disabled = bOut.disabled = true;
        var ok = v === it.answer;
        round.n++; if (ok) round.right++;
        s.callit.n++; if (ok) s.callit.right++; s.callit.seen[it.id] = 1; save(); setScore();
        (v === 1 ? bIn : bOut).classList.add(ok ? 'is-right' : 'is-wrong');
        if (!ok) (it.answer === 1 ? bIn : bOut).classList.add('is-right');
        var full = JSON.parse(JSON.stringify(it.chart)); full.runs = it.runs; full.mark = it.cut;
        drawInto(chartBox, full);
        if (panelBox) { var fp = JSON.parse(JSON.stringify(it.panel)); fp.runs = it.runs; fp.mark = it.cut; drawInto(panelBox, fp); }
        var said = it.answer === 1 ? 'IN' : 'OUT';
        var flipTxt = it.flip ? ' That was a change of mind: the call flipped on that very close.' : ' It had already been ' + said + ' the day before.';
        var dir = it.move >= 0 ? 'rose' : 'fell';
        var outcome = it.sym + ' ' + dir + ' ' + pct(it.move).replace('+', '').replace('−', '') + ' by ' + it.until +
          (it.bars ? ', when the play next changed its call' : '') + '. So this ' + said + ' call turned out ' + (it.right ? 'right' : 'wrong') + '.';
        result.textContent = '';
        result.appendChild(el('p', { 'class': 'h3 ' + (ok ? 'up' : 'down'), text: (ok ? 'Correct: ' : 'Not quite: ') + 'the play said ' + said + ' at that close.' + flipTxt }));
        result.appendChild(el('p', { text: 'What happened next: ' + outcome + ' The shading now shows every call in the window.' }));
        result.appendChild(el('div', { 'class': 'ci-next' }, [
          el('button', { type: 'button', 'class': 'btn primary', text: 'Next chart →', on: { click: next } }),
          el('a', { 'class': 'btn', href: plays + it.play + '/', text: 'About this play' })]));
        result.hidden = false;
        result.querySelector('button').focus({ preventScroll: true });
      }
      bIn.addEventListener('click', function () { answer(1); });
      bOut.addEventListener('click', function () { answer(0); });
    }
    famSel.addEventListener('change', function () { playSel.value = ''; next(); });
    playSel.addEventListener('change', next);
    fetch(root.getAttribute('data-src')).then(function (r) { return r.json(); }).then(function (d) {
      items = d.items || []; setScore(); next();
    }).catch(function () { stage.textContent = 'Could not load the practice charts. Refresh to try again.'; });
  }

  // ------------------------------------------------------------ play quiz
  function initPlayQuiz() {
    var root = document.getElementById('playquiz');
    if (!root) return;
    var data = JSON.parse(document.getElementById('pq-data').textContent);
    var stage = root.querySelector('.pq-stage');
    var plays = root.getAttribute('data-plays');
    var P = data.plays, FAM = data.families;
    var s = load();

    function q_who(p) {
      var others = pick(P.filter(function (x) { return x.by !== p.by; }).map(function (x) { return x.by; }).filter(function (v, i, a) { return a.indexOf(v) === i; }), 3, [p.by]);
      return { q: 'Who is behind ' + p.name + '?', a: shuffle([p.by].concat(others)), right: p.by, p: p };
    }
    function q_what(p) {
      var same = P.filter(function (x) { return x.family === p.family && x.slug !== p.slug; });
      var others = pick((same.length >= 3 ? same : P).map(function (x) { return x.name; }), 3, [p.name]);
      return { q: 'Which play is this? “' + p.short + '”', a: shuffle([p.name].concat(others)), right: p.name, p: p };
    }
    function q_family(p) {
      return { q: 'Which family does ' + p.name + ' belong to?', a: FAM.map(function (f) { return f[1]; }), right: p.familyName, p: p };
    }
    function q_bar(p) {
      return { q: 'How often does ' + p.name + ' check for a signal?', a: ['daily', 'weekly', 'month-end'], right: p.bar, p: p };
    }
    function q_rule(p) {
      var others = pick(P.filter(function (x) { return x.slug !== p.slug; }).map(function (x) { return x.rule; }), 3, [p.rule]);
      return { q: 'What gets ' + p.name + ' IN?', a: shuffle([p.rule].concat(others)), right: p.rule, p: p };
    }
    var kinds = [q_who, q_what, q_family, q_bar, q_rule, q_who, q_rule];
    function round() {
      var chosen = shuffle(P).slice(0, 10);
      var qs = chosen.map(function (p, i) { return kinds[(i + Math.floor(Math.random() * kinds.length)) % kinds.length](p); });
      var i = 0, right = 0;
      function show() {
        stage.textContent = '';
        if (i >= qs.length) {
          s.pq.rounds++; s.pq.best = Math.max(s.pq.best || 0, right); save();
          stage.appendChild(el('p', { 'class': 'h2', text: right + ' of ' + qs.length }));
          stage.appendChild(el('p', { 'class': 'muted', text: right >= 8 ? 'You know your plays.' : right >= 5 ? 'Solid. Another round will mix up the questions.' : 'The flashcards are a quick way to fill the gaps.' }));
          stage.appendChild(el('div', { 'class': 'ci-next' }, [el('button', { type: 'button', 'class': 'btn primary', text: 'New round', on: { click: round } })]));
          return;
        }
        var q = qs[i];
        stage.appendChild(el('p', { 'class': 'eyebrow', text: 'Question ' + (i + 1) + ' of ' + qs.length + ' · ' + right + ' right so far' }));
        stage.appendChild(el('p', { 'class': 'pq-q', text: q.q }));
        var opts = el('div', { 'class': 'quiz-opts' });
        var fb = el('div', { 'class': 'quiz-why', hidden: '' });
        q.a.forEach(function (txt) {
          var b = el('button', { type: 'button', 'class': 'quiz-opt', text: txt });
          b.addEventListener('click', function () {
            if (opts.classList.contains('done')) return;
            opts.classList.add('done');
            var ok = txt === q.right; if (ok) right++;
            [].forEach.call(opts.children, function (o) { o.disabled = true; if (o.textContent === q.right) o.classList.add('is-right'); else if (o === b) o.classList.add('is-wrong'); });
            fb.textContent = '';
            fb.appendChild(document.createTextNode((ok ? 'Right. ' : 'Not quite. ') + q.p.name + ' (' + q.p.by + '): ' + q.p.short + ' '));
            fb.appendChild(el('a', { href: plays + q.p.slug + '/', text: 'See the play →' }));
            fb.className = 'quiz-why ' + (ok ? 'ok' : 'no'); fb.hidden = false;
            var nx = el('button', { type: 'button', 'class': 'btn primary', text: i + 1 < qs.length ? 'Next question →' : 'See your score', on: { click: function () { i++; show(); } } });
            stage.appendChild(el('div', { 'class': 'ci-next' }, [nx])); nx.focus({ preventScroll: true });
          });
          opts.appendChild(b);
        });
        stage.appendChild(opts); stage.appendChild(fb);
      }
      show();
    }
    round();
  }

  function init() { initQuizzes(); initProgress(); initFlashcards(); initCallIt(); initPlayQuiz(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
