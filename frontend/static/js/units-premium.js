/**
 * Unidades premium — filtros, grade/lista, sparklines e modais
 */
(function () {
  const grid = document.getElementById("un-cards-grid");
  const searchInput = document.getElementById("un-search-input");
  const filterStatus = document.getElementById("un-filter-status");
  const sortSelect = document.getElementById("un-sort");
  const emptyFilter = document.getElementById("un-empty-filter");

  function drawSparkline(svg) {
    const raw = svg.getAttribute("data-trend") || "";
    const vals = raw.split(",").map((v) => parseInt(v, 10) || 0);
    if (!vals.length) return;
    const w = 120;
    const h = 36;
    const pad = 4;
    const max = Math.max(...vals, 1);
    const min = Math.min(...vals, 0);
    const range = max - min || 1;
    const step = vals.length > 1 ? (w - pad * 2) / (vals.length - 1) : 0;
    const points = vals.map((v, i) => {
      const x = pad + i * step;
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x},${y}`;
    });
    const stroke = getComputedStyle(svg.closest(".un-card") || document.documentElement)
      .getPropertyValue("--un-accent")
      .trim() || "#6941c6";
    const gradId = "un-spark-" + Math.random().toString(36).slice(2, 9);
    let html = `<defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${stroke}" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
      </linearGradient></defs>`;
    if (points.length >= 2) {
      const area = `M${points[0]} L${points.slice(1).join(" L")} L${pad + (vals.length - 1) * step},${h} L${pad},${h} Z`;
      html += `<path d="${area}" fill="url(#${gradId})"/>`;
    }
    html += `<polyline fill="none" stroke="${stroke}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${points.join(" ")}"/>`;
    svg.innerHTML = html;
  }

  document.querySelectorAll(".un-sparkline").forEach(drawSparkline);

  function filterCards() {
    if (!grid) return;
    const q = (searchInput?.value || "").trim().toLowerCase();
    const status = filterStatus?.value || "";
    let visible = 0;
    const cards = [...grid.querySelectorAll(".un-card")];
    cards.forEach((card) => {
      const name = card.getAttribute("data-name") || "";
      const st = card.getAttribute("data-status") || "";
      const show = (!q || name.includes(q)) && (!status || st === status);
      card.classList.toggle("un-hidden", !show);
      if (show) visible++;
    });
    if (emptyFilter) {
      emptyFilter.classList.toggle("un-hidden", visible > 0 || !cards.length);
    }
  }

  function sortCards() {
    if (!grid || !sortSelect) return;
    const mode = sortSelect.value;
    const cards = [...grid.querySelectorAll(".un-card")];
    cards.sort((a, b) => {
      if (mode === "attendance") {
        return (
          parseInt(b.getAttribute("data-attendance"), 10) -
          parseInt(a.getAttribute("data-attendance"), 10)
        );
      }
      if (mode === "members") {
        return (
          parseInt(b.getAttribute("data-members"), 10) -
          parseInt(a.getAttribute("data-members"), 10)
        );
      }
      return (a.getAttribute("data-name") || "").localeCompare(
        b.getAttribute("data-name") || ""
      );
    });
    cards.forEach((c) => grid.appendChild(c));
  }

  searchInput?.addEventListener("input", filterCards);
  filterStatus?.addEventListener("change", filterCards);
  sortSelect?.addEventListener("change", () => {
    sortCards();
    filterCards();
  });

  document.querySelectorAll("[data-un-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-un-view");
      document.querySelectorAll("[data-un-view]").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      grid?.classList.toggle("is-list", view === "list");
    });
  });

  const memberSearch = document.getElementById("un-member-search");
  const roleFilter = document.getElementById("un-role-filter");
  const membersTable = document.getElementById("un-members-table");

  function filterMembers() {
    if (!membersTable) return;
    const q = (memberSearch?.value || "").trim().toLowerCase();
    const role = roleFilter?.value || "";
    membersTable.querySelectorAll("tbody tr[data-name]").forEach((row) => {
      const name = row.getAttribute("data-name") || "";
      const r = row.getAttribute("data-role") || "";
      const show = (!q || name.includes(q)) && (!role || r === role);
      row.classList.toggle("un-hidden", !show);
    });
  }

  memberSearch?.addEventListener("input", filterMembers);
  roleFilter?.addEventListener("change", filterMembers);

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModals() {
    document.querySelectorAll(".un-modal.is-open").forEach((m) => {
      m.classList.remove("is-open");
      m.setAttribute("aria-hidden", "true");
    });
  }

  document.getElementById("un-btn-add-member")?.addEventListener("click", () => openModal("un-modal-member"));

  document.querySelectorAll("[data-un-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModals);
  });

  document.querySelectorAll(".un-modal").forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModals();
    });
  });

  const roleModal = document.getElementById("un-modal-role");
  const roleForm = document.getElementById("un-role-form");
  document.querySelectorAll("[data-un-edit-role]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const roleId = btn.getAttribute("data-un-edit-role");
      const name = btn.getAttribute("data-role-name");
      const color = btn.getAttribute("data-role-color");
      if (!roleForm || !roleModal) return;
      const base = roleForm.getAttribute("data-create-url") || roleForm.action;
      roleForm.action = base.replace(/\/cargos$/, `/cargos/${roleId}/editar`);
      document.getElementById("un-modal-role-title").textContent = "Editar cargo";
      roleForm.querySelector('[name="name"]').value = name || "";
      const colorSel = roleForm.querySelector('[name="color_key"]');
      if (colorSel && color) colorSel.value = color;
      openModal("un-modal-role");
    });
  });

  function openNewRoleModal() {
    if (roleForm) {
      roleForm.action = roleForm.getAttribute("data-create-url") || roleForm.action;
      const title = document.getElementById("un-modal-role-title");
      if (title) title.textContent = "Novo cargo";
      const nameInput = roleForm.querySelector('[name="name"]');
      if (nameInput) nameInput.value = "";
    }
    openModal("un-modal-role");
  }

  document.getElementById("un-btn-new-role")?.addEventListener("click", openNewRoleModal);
  document.getElementById("un-btn-new-role-side")?.addEventListener("click", openNewRoleModal);

  if (roleForm && roleModal) {
    roleModal.querySelector('[type="submit"]')?.addEventListener("click", () => {
      if (!roleForm.action.includes("/editar") && !roleForm.querySelector('[name="name"]')?.value) return;
    });
  }
})();
