// Small progressive enhancements. Every page works without this file.
(function () {
  "use strict";

  var toastTimer;
  function toast(text) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, 2600);
  }

  function selectText(el) {
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  document.addEventListener("click", function (e) {
    // Copy buttons: <button data-copy="#elementId">
    var copyBtn = e.target.closest("[data-copy]");
    if (copyBtn) {
      var src = document.querySelector(copyBtn.getAttribute("data-copy"));
      if (!src) return;
      var fallback = function () { selectText(src); toast("Text selected. Copy it with your device's copy command."); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(src.textContent).then(function () { toast("Copied. Paste it into SMS or Viber."); }, fallback);
      } else {
        fallback();
      }
      return;
    }

    // Two-tap confirmation for destructive buttons: <button data-confirm="Tap again to ...">
    var confirmBtn = e.target.closest("[data-confirm]");
    if (confirmBtn && !confirmBtn.dataset.armed) {
      e.preventDefault();
      confirmBtn.dataset.armed = "1";
      confirmBtn.dataset.label = confirmBtn.textContent;
      confirmBtn.textContent = confirmBtn.getAttribute("data-confirm");
      setTimeout(function () {
        delete confirmBtn.dataset.armed;
        confirmBtn.textContent = confirmBtn.dataset.label;
      }, 5000);
    }
  });

  // Highlight ticked checklist rows.
  document.addEventListener("change", function (e) {
    if (e.target.matches(".check input[type=checkbox]")) {
      var label = e.target.closest("label");
      if (label) label.classList.toggle("on", e.target.checked);
    }
  });

  // Stop double submissions (e.g. tapping "Complete job" twice on a slow connection).
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset.submitting) { e.preventDefault(); return; }
    form.dataset.submitting = "1";
    setTimeout(function () { delete form.dataset.submitting; }, 8000);
  });
})();
