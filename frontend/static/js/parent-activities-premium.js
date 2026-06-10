/**
 * Portal Família — Atividades (lista limpa, filtros, modal)
 */
(function () {
  "use strict";

  const root = document.getElementById("pa-app");
  if (!root) return;

  const activities = Array.from(root.querySelectorAll(".pa-activity[data-category]"));
  const catBtns = root.querySelectorAll(".pa-cat-btn");
  const sortSelect = root.querySelector("#pa-sort");
  const list = root.querySelector("#pa-activity-list");
  const listTitle = root.querySelector("#pa-list-title");
  const toggleAllBtn = root.querySelector("#pa-toggle-all");
  const showCompletedBtn = root.querySelector("#pa-show-completed");
  const modal = document.getElementById("pa-evidence-modal");
  const modalForm = document.getElementById("pa-evidence-form");
  const modalTitle = document.getElementById("pa-modal-title");
  const modalSub = modal?.querySelector(".pa-modal__sub");

  let activeCategory = "todas";
  let showAll = false;
  let showOnlyCompleted = false;

  function isPendingItem(el) {
    return el.dataset.pending === "1";
  }

  function applyVisibility() {
    activities.forEach((el) => {
      const catMatch = activeCategory === "todas" || el.dataset.category === activeCategory;
      let statusMatch = true;

      if (showOnlyCompleted) {
        statusMatch = el.dataset.statusKey === "completed";
      } else if (!showAll) {
        statusMatch = isPendingItem(el);
      }

      el.classList.toggle("is-hidden", !(catMatch && statusMatch));
    });

    const visible = activities.filter((el) => !el.classList.contains("is-hidden"));
    if (listTitle) {
      if (showOnlyCompleted) {
        listTitle.textContent = "Atividades concluídas";
      } else if (showAll) {
        listTitle.textContent = activeCategory === "todas" ? "Todas as atividades" : "Atividades filtradas";
      } else {
        listTitle.textContent = "Atividades pendentes";
      }
    }

    if (toggleAllBtn) {
      const hasExtra = activities.some((el) => !isPendingItem(el));
      toggleAllBtn.style.display = hasExtra && !showOnlyCompleted ? "" : "none";
      toggleAllBtn.textContent = showAll ? "Mostrar apenas pendentes" : "Ver todas as atividades";
      toggleAllBtn.setAttribute("aria-expanded", showAll ? "true" : "false");
    }
  }

  function setCategory(slug) {
    activeCategory = slug;
    catBtns.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.category === slug);
    });
    applyVisibility();
    sortActivities();
  }

  function sortActivities() {
    const mode = sortSelect?.value || "status";
    const parent = list;
    if (!parent) return;

    const visible = activities.filter((el) => !el.classList.contains("is-hidden"));
    const sorted = [...visible].sort((a, b) => {
      if (mode === "title") {
        return (a.dataset.title || "").localeCompare(b.dataset.title || "", "pt");
      }
      if (mode === "status") {
        return (a.dataset.statusOrder || "9").localeCompare(b.dataset.statusOrder || "9");
      }
      return (parseInt(b.dataset.sortTs, 10) || 0) - (parseInt(a.dataset.sortTs, 10) || 0);
    });

    sorted.forEach((el) => parent.appendChild(el));
  }

  catBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      showOnlyCompleted = false;
      setCategory(btn.dataset.category || "todas");
    });
  });

  sortSelect?.addEventListener("change", sortActivities);

  toggleAllBtn?.addEventListener("click", () => {
    showAll = !showAll;
    showOnlyCompleted = false;
    applyVisibility();
    sortActivities();
  });

  showCompletedBtn?.addEventListener("click", () => {
    showOnlyCompleted = true;
    showAll = true;
    activeCategory = "todas";
    catBtns.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.category === "todas");
    });
    applyVisibility();
    sortActivities();
    list?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function getActivityData(btn) {
    const item = btn.closest(".pa-activity");
    return {
      title: btn.dataset.title || "Atividade",
      homeworkId: btn.dataset.homeworkId,
      action: btn.dataset.paAction,
      status: btn.dataset.status || item?.querySelector(".pa-status")?.textContent?.trim() || "",
      statusClass: btn.dataset.statusClass || item?.querySelector(".pa-status")?.className || "",
      desc: btn.dataset.desc || item?.querySelector(".pa-activity__desc-hidden")?.textContent?.trim() || "",
      due: btn.dataset.due || item?.querySelector(".pa-activity__due")?.textContent?.trim() || "",
      xp: btn.dataset.xp || item?.querySelector(".pa-activity__xp-hidden")?.textContent?.trim() || "",
    };
  }

  root.querySelectorAll("[data-pa-action]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const data = getActivityData(btn);

      if (data.action === "submit" && data.homeworkId && modal && modalForm) {
        e.preventDefault();
        const input = modalForm.querySelector('input[name="assignment_id"]');
        if (input) input.value = data.homeworkId;
        if (modalTitle) modalTitle.textContent = data.title;
        if (modalSub) modalSub.style.display = "";
        modalForm.style.display = "";
        const slot = modal.querySelector(".pa-detail-slot");
        if (slot) slot.remove();
        modal.classList.add("is-open");
        document.body.style.overflow = "hidden";
        return;
      }

      if (data.action === "details" || data.action === "certificate") {
        if (!modal || !modalForm) return;
        if (modalTitle) modalTitle.textContent = data.title;
        if (modalSub) modalSub.style.display = "none";

        const detailHtml =
          '<div class="pa-detail-view">' +
          (data.status
            ? '<p class="pa-status ' +
              data.statusClass +
              '" style="display:inline-block;margin-bottom:0.75rem">' +
              data.status +
              "</p>"
            : "") +
          (data.desc ? '<p class="text-sm text-slate-600 mb-3">' + data.desc + "</p>" : "") +
          (data.due ? '<p class="text-xs text-slate-500 mb-1">' + data.due + "</p>" : "") +
          (data.xp ? '<p class="text-xs font-semibold text-navy-900">' + data.xp + "</p>" : "") +
          (data.action === "certificate"
            ? '<p class="text-sm font-semibold text-green-700 mt-3">✓ Atividade concluída e registrada no caderno.</p>'
            : "") +
          "</div>";

        modalForm.style.display = "none";
        let slot = modal.querySelector(".pa-detail-slot");
        if (!slot) {
          slot = document.createElement("div");
          slot.className = "pa-detail-slot";
          modalForm.parentElement?.appendChild(slot);
        }
        slot.innerHTML = detailHtml;
        modal.classList.add("is-open");
        document.body.style.overflow = "hidden";
      }
    });
  });

  function closeModal() {
    modal?.classList.remove("is-open");
    document.body.style.overflow = "";
    if (modalForm) modalForm.style.display = "";
    if (modalSub) modalSub.style.display = "";
    modal?.querySelector(".pa-detail-slot")?.remove();
  }

  modal?.querySelector(".pa-modal__backdrop")?.addEventListener("click", closeModal);
  modal?.querySelector(".pa-modal__close")?.addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  const bar = root.querySelector(".pa-banner__progress-fill");
  if (bar) {
    const target = bar.style.width;
    bar.style.width = "0%";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        bar.style.width = target;
      });
    });
  }

  root.querySelectorAll("[data-pa-count]").forEach((el) => {
    const end = parseInt(el.dataset.paCount, 10) || 0;
    if (end <= 0) {
      el.textContent = "0";
      return;
    }
    let cur = 0;
    const step = Math.max(1, Math.ceil(end / 20));
    const tick = () => {
      cur = Math.min(end, cur + step);
      el.textContent = String(cur);
      if (cur < end) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  setCategory("todas");
})();
