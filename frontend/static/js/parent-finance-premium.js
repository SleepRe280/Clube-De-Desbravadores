/**
 * Financeiro dos Pais — tabs, cópia PIX e toast
 */
(function () {
  "use strict";

  var app = document.getElementById("fn-parent-app");
  if (!app) return;

  /* —— Tabs —— */
  var tabs = app.querySelectorAll(".fn-parent-tab");
  var panels = app.querySelectorAll(".fn-parent-tabpanel");

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var target = tab.getAttribute("data-tab");
      tabs.forEach(function (t) {
        var active = t === tab;
        t.classList.toggle("is-active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
      });
      panels.forEach(function (panel) {
        var show = panel.getAttribute("data-panel") === target;
        panel.classList.toggle("is-active", show);
        if (show) {
          panel.removeAttribute("hidden");
        } else {
          panel.setAttribute("hidden", "");
        }
      });
    });
  });

  /* —— Toast —— */
  var toast = document.getElementById("fn-parent-toast");
  var toastTimer;

  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.removeAttribute("hidden");
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.classList.remove("is-visible");
      setTimeout(function () { toast.setAttribute("hidden", ""); }, 300);
    }, 2500);
  }

  /* —— Copy PIX —— */
  function copyText(text, msg) {
    if (!text) return;
    var done = function () { showToast(msg); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else {
      fallback();
    }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); done(); }
      catch (e) { /* silent */ }
      document.body.removeChild(ta);
    }
  }

  var pixInput = document.getElementById("fn-parent-pix-key");
  var copyBtn = document.getElementById("fn-parent-copy-pix");
  if (copyBtn && pixInput) {
    copyBtn.addEventListener("click", function () {
      copyText(pixInput.value.trim(), "Chave PIX copiada!");
    });
  }
})();
