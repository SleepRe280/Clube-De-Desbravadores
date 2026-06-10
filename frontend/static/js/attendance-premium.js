/**
 * Presenças premium — filtros, busca, ciclo de status e marcação em lote (client-side)
 */
(function () {
  "use strict";

  const STATUS_CYCLE = [
    "nao_registrado",
    "presente",
    "falta",
    "atrasado",
    "justificado",
    "dispensa",
  ];

  const STATUS_LABELS = {
    presente: "Presente",
    falta: "Falta",
    atrasado: "Atrasado",
    justificado: "Justificado",
    dispensa: "Dispensa",
    nao_registrado: "Não registrado",
  };

  const app = document.getElementById("att-app");
  if (!app) return;

  const form = document.getElementById("att-roll-form");
  if (form) {
    form.addEventListener("submit", () => {
      const md = document.getElementById("att-meeting-date");
      const hidden = form.querySelector('input[name="meeting_date"]');
      if (md && hidden && md.value) hidden.value = md.value;
    });
  }
  const searchInput = document.getElementById("att-search");
  const tabs = app.querySelectorAll(".att-tab");
  const rows = () => Array.from(app.querySelectorAll("[data-att-row]"));

  let activeFilter = "all";

  function badgeClass(status) {
    return "att-badge att-badge--" + (status || "nao_registrado");
  }

  function updateBadge(btn, status) {
    btn.className = badgeClass(status);
    btn.textContent = STATUS_LABELS[status] || status;
    btn.setAttribute("data-status", status);
    const mid = btn.getAttribute("data-member-id");
    const hidden = form && form.querySelector('input[name="status_' + mid + '"]');
    if (hidden) hidden.value = status;
  }

  function cycleStatus(current) {
    const i = STATUS_CYCLE.indexOf(current);
    const next = STATUS_CYCLE[(i + 1) % STATUS_CYCLE.length];
    return next;
  }

  function rowMatchesFilter(row) {
    const status = row.getAttribute("data-status");
    if (activeFilter === "all") return true;
    if (activeFilter === "presente") return status === "presente";
    if (activeFilter === "falta") return status === "falta";
    if (activeFilter === "atrasado") return status === "atrasado";
    if (activeFilter === "justificado") return status === "justificado";
    if (activeFilter === "dispensa") return status === "dispensa";
    return true;
  }

  function rowMatchesSearch(row, q) {
    if (!q) return true;
    const hay = (row.getAttribute("data-search") || "").toLowerCase();
    return hay.includes(q);
  }

  function applyFilters() {
    const q = (searchInput && searchInput.value || "").trim().toLowerCase();
    rows().forEach((row) => {
      const ok = rowMatchesFilter(row) && rowMatchesSearch(row, q);
      row.classList.toggle("is-hidden", !ok);
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      activeFilter = tab.getAttribute("data-filter") || "all";
      applyFilters();
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
  }

  app.querySelectorAll("[data-att-status-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cur = btn.getAttribute("data-status") || "nao_registrado";
      const next = cycleStatus(cur);
      updateBadge(btn, next);
      const row = btn.closest("[data-att-row]");
      if (row) row.setAttribute("data-status", next);
      applyFilters();
    });
  });

  app.querySelectorAll("[data-att-cycle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.closest("[data-att-row]");
      if (!row) return;
      const statusBtn = row.querySelector("[data-att-status-btn]");
      if (!statusBtn) return;
      const cur = statusBtn.getAttribute("data-status") || "nao_registrado";
      const next = cycleStatus(cur);
      updateBadge(statusBtn, next);
      row.setAttribute("data-status", next);
      applyFilters();
    });
  });

  const markAllBtn = document.getElementById("att-mark-all");
  if (markAllBtn) {
    markAllBtn.addEventListener("click", () => {
      rows().forEach((row) => {
        const statusBtn = row.querySelector("[data-att-status-btn]");
        if (statusBtn) {
          updateBadge(statusBtn, "presente");
          row.setAttribute("data-status", "presente");
        }
      });
      applyFilters();
    });
  }

  app.querySelectorAll("[data-att-alert-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.getAttribute("data-att-alert-filter");
      if (filter && tabs.length) {
        const tab = app.querySelector('.att-tab[data-filter="' + filter + '"]');
        if (tab) tab.click();
        else if (filter === "all") tabs[0].click();
      }
    });
  });

  const meetingDateInput = document.getElementById("att-meeting-date");
  if (meetingDateInput && form) {
    meetingDateInput.addEventListener("change", () => {
      const v = meetingDateInput.value;
      if (!v) return;
      const url = new URL(window.location.href);
      url.searchParams.set("meeting_date", v);
      window.location.href = url.toString();
    });
  }
})();
