/**
 * Membros premium — busca, filtros, ordenação e favoritos locais
 */
(function () {
  "use strict";

  const app = document.getElementById("mb-app");
  if (!app) return;

  const grid = document.getElementById("mb-cards-grid");
  const cards = () => Array.from(grid?.querySelectorAll("[data-mb-card]") || []);
  const searchEl = document.getElementById("mb-search");
  const filterUnit = document.getElementById("mb-filter-unit");
  const filterClass = document.getElementById("mb-filter-class");
  const filterRole = document.getElementById("mb-filter-role");
  const filterStatus = document.getElementById("mb-filter-status");
  const sortEl = document.getElementById("mb-sort");
  const metaEl = document.getElementById("mb-results-meta");
  const emptyFilter = document.getElementById("mb-empty-filter");
  const clearBtn = document.getElementById("mb-clear-filters");

  const FAV_KEY = "mb_favorites_v1";

  function loadFavs() {
    try {
      return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));
    } catch {
      return new Set();
    }
  }

  function saveFavs(set) {
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify([...set]));
    } catch (_) {}
  }

  const favs = loadFavs();

  function applyFavStars() {
    document.querySelectorAll("[data-mb-fav]").forEach((btn) => {
      const id = btn.getAttribute("data-mb-fav");
      btn.classList.toggle("is-fav", favs.has(id));
    });
  }

  document.querySelectorAll("[data-mb-fav]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.getAttribute("data-mb-fav");
      if (favs.has(id)) favs.delete(id);
      else favs.add(id);
      saveFavs(favs);
      btn.classList.toggle("is-fav", favs.has(id));
    });
  });

  applyFavStars();

  function getFilters() {
    return {
      q: (searchEl?.value || "").trim().toLowerCase(),
      unit: filterUnit?.value || "",
      cls: filterClass?.value || "",
      role: filterRole?.value || "",
      status: filterStatus?.value || "",
      sort: sortEl?.value || "name",
    };
  }

  function cardMatches(el, f) {
    if (f.q && !(el.dataset.search || "").includes(f.q)) return false;
    if (f.unit && el.dataset.unit !== f.unit) return false;
    if (f.cls && !(el.dataset.class || "").includes(f.cls)) return false;
    if (f.status && el.dataset.status !== f.status) return false;
    if (f.role === "lider" && el.dataset.role !== "lider") return false;
    if (f.role === "desbravador" && el.dataset.role === "lider") return false;
    return true;
  }

  function sortCards(list, sort) {
    const arr = [...list];
    arr.sort((a, b) => {
      if (sort === "performance") {
        return Number(b.dataset.performance) - Number(a.dataset.performance);
      }
      if (sort === "score") {
        return Number(b.dataset.score) - Number(a.dataset.score);
      }
      if (sort === "frequency") {
        return Number(b.dataset.frequency) - Number(a.dataset.frequency);
      }
      const na = a.querySelector(".mb-card__name")?.textContent || "";
      const nb = b.querySelector(".mb-card__name")?.textContent || "";
      return na.localeCompare(nb, "pt-BR");
    });
    return arr;
  }

  function applyFilters() {
    const f = getFilters();
    const all = cards();
    let visible = 0;

    all.forEach((el) => {
      const show = cardMatches(el, f);
      el.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });

    const sorted = sortCards(all.filter((el) => !el.classList.contains("is-hidden")), f.sort);
    sorted.forEach((el) => grid?.appendChild(el));

    if (metaEl) {
      if (all.length) {
        metaEl.hidden = false;
        metaEl.textContent = `${visible} de ${all.length} desbravadores`;
      } else {
        metaEl.hidden = true;
      }
    }

    if (emptyFilter && all.length) {
      emptyFilter.hidden = visible > 0;
    }
  }

  ["input", "change"].forEach((ev) => {
    searchEl?.addEventListener(ev, applyFilters);
    filterUnit?.addEventListener(ev, applyFilters);
    filterClass?.addEventListener(ev, applyFilters);
    filterRole?.addEventListener(ev, applyFilters);
    filterStatus?.addEventListener(ev, applyFilters);
    sortEl?.addEventListener(ev, applyFilters);
  });

  clearBtn?.addEventListener("click", () => {
    if (searchEl) searchEl.value = "";
    [filterUnit, filterClass, filterRole, filterStatus, sortEl].forEach((el) => {
      if (el) el.selectedIndex = 0;
    });
    applyFilters();
  });

  document.querySelectorAll("[data-mb-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-mb-view");
      document.querySelectorAll("[data-mb-view]").forEach((b) => {
        const on = b === btn;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      grid?.classList.toggle("is-list", view === "list");
    });
  });

  applyFilters();
})();
