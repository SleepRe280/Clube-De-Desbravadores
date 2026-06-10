(function () {
  const root = document.querySelector("[data-mp-tabs]");
  if (!root) return;

  const tabs = root.querySelectorAll("[data-mp-tab]");
  const panels = document.querySelectorAll("[data-mp-panel]");

  function activate(id) {
    tabs.forEach((t) => {
      const on = t.getAttribute("data-mp-tab") === id;
      t.classList.toggle("mp-tab--active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((p) => {
      p.classList.toggle("mp-panel--active", p.getAttribute("data-mp-panel") === id);
    });
    if (history.replaceState) {
      const url = new URL(window.location.href);
      url.searchParams.set("aba", id);
      history.replaceState(null, "", url);
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.getAttribute("data-mp-tab")));
  });

  document.querySelectorAll("[data-mp-copy]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const text = btn.getAttribute("data-mp-copy");
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
        const prev = btn.textContent;
        btn.textContent = "Copiado!";
        setTimeout(() => {
          btn.textContent = prev;
        }, 1500);
      });
    });
  });

  const params = new URLSearchParams(window.location.search);
  const initial = params.get("aba") || "visao";
  if (document.querySelector(`[data-mp-panel="${initial}"]`)) {
    activate(initial);
  }
})();
