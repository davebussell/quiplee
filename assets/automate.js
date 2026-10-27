/* automate.js: the broker directory's filter (guides/brokers/) and the copy buttons on the automation guides
 * (tools/qstrat/automate.py). Rows and cards carry data-ca / data-us (who can open) and data-paper / data-api /
 * data-ai (1 when the firm has it). Without this script everything shows. */
(function () {
  "use strict";
  // copy buttons: the <pre> just before the button
  document.querySelectorAll("[data-copy-prev]").forEach(function (b) {
    b.addEventListener("click", function () {
      var pre = b.previousElementSibling, txt = pre ? pre.innerText : "";
      var done = function () { var o = b.textContent; b.textContent = "Copied"; setTimeout(function () { b.textContent = o; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, function () { sel(pre); });
      else sel(pre);
    });
  });
  function sel(el) { try { var r = document.createRange(); r.selectNodeContents(el); var s = getSelection(); s.removeAllRanges(); s.addRange(r); } catch (e) {} }

  var box = document.querySelector("[data-auto-filter]");
  if (!box) return;
  box.hidden = false;
  var where = "all", need = {};
  var KEY = "bp.brokers.v1";
  try { var saved = JSON.parse(localStorage.getItem(KEY) || "{}"); if (saved.w) where = saved.w; need = saved.n || {}; } catch (e) {}
  function apply() {
    var shown = 0, total = 0;
    document.querySelectorAll("[data-auto-rows] [data-ca]").forEach(function (el) {
      var ok = where === "all" || el.getAttribute("data-" + where) === "1";
      if (el.hasAttribute("data-paper")) {
        for (var k in need) if (need[k] && el.getAttribute("data-" + k) !== "1") ok = false;
        if (el.tagName === "TR") { total++; if (ok) shown++; }
      }
      el.hidden = !ok;
    });
    box.querySelectorAll("[data-where]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-where") === where)); });
    box.querySelectorAll("[data-need]").forEach(function (c) { c.checked = !!need[c.getAttribute("data-need")]; });
    var n = box.querySelector("[data-auto-count]");
    if (n) n.textContent = shown === total ? total + " brokers" : shown + " of " + total + " brokers";
    try { localStorage.setItem(KEY, JSON.stringify({ w: where, n: need })); } catch (e) {}
  }
  box.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-where]");
    if (b) { where = b.getAttribute("data-where"); apply(); }
  });
  box.addEventListener("change", function (ev) {
    var c = ev.target.closest("[data-need]");
    if (c) { need[c.getAttribute("data-need")] = c.checked; apply(); }
  });
  apply();
})();
