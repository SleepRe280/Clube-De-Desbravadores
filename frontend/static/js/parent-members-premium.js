/**
 * Portal Família — Membros do Clube (filtros em tempo real)
 */
(function () {
  "use strict";

  const root = document.getElementById("pm-app");
  if (!root) return;

  const searchInput = root.querySelector("#pm-search");
  const unitSelect = root.querySelector("#pm-filter-unit");
  const roleSelect = root.querySelector("#pm-filter-role");
  const cards = Array.from(root.querySelectorAll(".pm-card[data-name]"));
  const emptyFilter = root.querySelector(".pm-empty--filter");
  const emptyInitial = root.querySelector(".pm-empty--initial");

  function normalize(value) {
    return (value || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function applyFilters() {
    const query = normalize(searchInput?.value);
    const unit = unitSelect?.value || "";
    const role = roleSelect?.value || "";
    let visible = 0;

    cards.forEach((card) => {
      const name = normalize(card.dataset.name || "");
      const cardUnit = card.dataset.unit || "";
      const cardRole = card.dataset.role || "";
      const matchName = !query || name.includes(query);
      const matchUnit = !unit || cardUnit === unit;
      const matchRole = !role || cardRole === role;
      const show = matchName && matchUnit && matchRole;
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });

    if (emptyFilter) {
      emptyFilter.classList.toggle("is-visible", cards.length > 0 && visible === 0);
    }
    if (emptyInitial) {
      emptyInitial.classList.toggle("is-hidden", cards.length > 0);
    }
  }

  searchInput?.addEventListener("input", applyFilters);
  unitSelect?.addEventListener("change", applyFilters);
  roleSelect?.addEventListener("change", applyFilters);

  applyFilters();
})();
