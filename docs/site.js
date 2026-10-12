/* chip explainer: the ladder picker and the stepped socket call.
 * No dependencies. Everything degrades to static content without it. */
(function () {
  "use strict";

  // ---- the ladder ---------------------------------------------------------
  var rungs = Array.prototype.slice.call(document.querySelectorAll(".rung"));
  var panes = Array.prototype.slice.call(document.querySelectorAll(".rung-pane"));

  function showRung(n) {
    rungs.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.rung === n)); });
    panes.forEach(function (p) { p.classList.toggle("is-active", p.dataset.rung === n); });
  }
  rungs.forEach(function (b) {
    b.addEventListener("click", function () { showRung(b.dataset.rung); });
  });
  var list = document.querySelector(".rungs");
  if (list) {
    list.addEventListener("keydown", function (e) {
      var i = rungs.indexOf(document.activeElement);
      if (i < 0) return;
      var j = e.key === "ArrowRight" || e.key === "ArrowDown" ? i + 1
            : e.key === "ArrowLeft" || e.key === "ArrowUp" ? i - 1 : -1;
      if (j < 0 || j >= rungs.length) return;
      e.preventDefault();
      rungs[j].focus();
      showRung(rungs[j].dataset.rung);
    });
  }
  showRung("2");

  // ---- the call -------------------------------------------------------------
  var call = document.querySelector(".call");
  if (!call) return;
  var steps = Array.prototype.slice.call(call.querySelectorAll(".steps li"));
  var lines = Array.prototype.slice.call(call.querySelectorAll(".paper .r"));
  var paper = call.querySelector(".paper");
  var next = call.querySelector('[data-action="next"]');
  var reset = call.querySelector('[data-action="reset"]');
  var count = call.querySelector(".step-count");
  var total = steps.length;

  function render(n) {
    call.dataset.step = String(n);
    for (var k = 1; k <= total; k++) call.classList.toggle("s" + k, n >= k);
    steps.forEach(function (li) {
      var s = Number(li.dataset.step);
      li.classList.toggle("is-done", s < n);
      li.classList.toggle("is-current", s === n);
    });
    lines.forEach(function (ln) { ln.classList.toggle("is-printed", Number(ln.dataset.step) <= n); });
    paper.classList.toggle("is-empty", n === 0);
    next.textContent = n === 0 ? "Run one step" : n < total ? "Next step" : "Run again";
    count.textContent = n === 0 ? "" : "step " + n + " of " + total;
  }
  next.addEventListener("click", function () {
    var n = Number(call.dataset.step);
    render(n >= total ? 1 : n + 1);
  });
  reset.addEventListener("click", function () { render(0); });
  render(0);
})();
