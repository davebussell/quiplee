/* portfolio.js — import a broker holdings CSV and stress-test every position
 * through the theories engine. PRIVACY BY DESIGN: the file is parsed in this
 * browser, stored only in this browser's localStorage (q_portfolio), and never
 * sent anywhere — no upload, no server, no analytics. Clearing it deletes it. */
(function () {
  window.Q = window.Q || {};
  var LS = 'q_portfolio';

  function read() { try { var v = localStorage.getItem(LS); return v ? JSON.parse(v) : null; } catch (e) { return null; } }
  function write(v) { try { localStorage.setItem(LS, JSON.stringify(v)); } catch (e) {} }

  // quote-aware CSV line splitter
  function splitLine(line) {
    var out = [], cur = '', q = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (q) {
        if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else q = false; }
        else cur += ch;
      } else {
        if (ch === '"') q = true;
        else if (ch === ',') { out.push(cur); cur = ''; }
        else cur += ch;
      }
    }
    out.push(cur);
    return out;
  }

  /** Parse a holdings export. Understands the common Canadian-broker layout
   * (Symbol / Name / Security Type / Quantity / Market Price / Market Value +
   * currency columns) by reading the header row; skips cash rows. */
  function parseCsv(text) {
    var lines = String(text || '').split(/\r?\n/).filter(function (l) { return l.trim(); });
    if (!lines.length) return { error: 'Empty file.' };
    var header = splitLine(lines[0]).map(function (h) { return h.trim().toLowerCase(); });
    function col(names) {
      for (var i = 0; i < header.length; i++) {
        for (var j = 0; j < names.length; j++) if (header[i] === names[j]) return i;
      }
      return -1;
    }
    var cSym = col(['symbol']), cName = col(['name']), cType = col(['security type']),
        cQty = col(['quantity']), cPx = col(['market price']), cPxCur = col(['market price currency']),
        cVal = col(['market value']), cValCur = col(['market value currency']);
    if (cSym < 0 || cVal < 0) return { error: 'Could not find Symbol / Market Value columns — is this a holdings export?' };

    var holdings = [], asOf = null;
    for (var i = 1; i < lines.length; i++) {
      var f = splitLine(lines[i]);
      if (f.length < 3) { var m = lines[i].match(/as of ([0-9‑-]+[^"]*)/i); if (m) asOf = m[1].trim(); continue; }
      var sym = (f[cSym] || '').trim();
      var type = cType >= 0 ? (f[cType] || '').trim() : 'EQUITY';
      if (!sym || type === 'CURRENCY') continue;
      var h = {
        sym: sym,
        name: cName >= 0 ? (f[cName] || '').trim() : sym,
        type: type,
        qty: cQty >= 0 ? parseFloat(f[cQty]) || 0 : 0,
        price: cPx >= 0 ? parseFloat(f[cPx]) || 0 : 0,
        priceCur: cPxCur >= 0 ? (f[cPxCur] || '').trim() : '',
        value: parseFloat(f[cVal]) || 0,
        valueCur: cValCur >= 0 ? (f[cValCur] || '').trim() : ''
      };
      if (h.value > 0 || h.qty > 0) holdings.push(h);
    }
    if (!holdings.length) return { error: 'No equity positions found in the file.' };
    holdings.sort(function (a, b) { return b.value - a.value; });
    return { holdings: holdings, asOf: asOf, importedAt: Date.now() };
  }

  function summarize(pf) {
    var byArch = {}, totals = {};
    (pf.holdings || []).forEach(function (h) {
      var c = Q.theories.classify(h.sym, h.name, h.type);
      if (!c) return;
      h.arch = c.arch; h.archLabel = c.label; h.known = c.known;
      byArch[c.arch] = byArch[c.arch] || { arch: c.arch, label: c.label, value: 0, count: 0 };
      // rough single-currency roll-up: treat each currency separately for totals,
      // but archetype mix uses raw numbers (CAD/USD close enough for a mix view)
      byArch[c.arch].value += h.value; byArch[c.arch].count++;
      totals[h.valueCur || '?'] = (totals[h.valueCur || '?'] || 0) + h.value;
    });
    var mix = Object.keys(byArch).map(function (k) { return byArch[k]; })
      .sort(function (a, b) { return b.value - a.value; });
    var grand = mix.reduce(function (a, m) { return a + m.value; }, 0) || 1;
    mix.forEach(function (m) { m.pct = Math.round(m.value / grand * 100); });
    return { mix: mix, totals: totals, count: (pf.holdings || []).length };
  }

  Q.portfolio = {
    get: read,
    clear: function () { try { localStorage.removeItem(LS); } catch (e) {} },
    importText: function (text) {
      var r = parseCsv(text);
      if (r.error) return r;
      write(r);
      return r;
    },
    summarize: summarize
  };
})();
