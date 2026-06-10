/**
 * Agenda premium — calendário, modais, filtros e RSVP
 */
(function () {
  const root = document.getElementById("agenda-app");
  if (!root) return;

  const dataEl = document.getElementById("agenda-events-data");
  let events = [];
  try {
    events = JSON.parse(dataEl?.textContent || "[]");
  } catch (_) {
    events = [];
  }

  const cfg = {
    canWrite: root.dataset.canWrite === "1",
    year: parseInt(root.dataset.year, 10),
    month: parseInt(root.dataset.month, 10),
    selected: root.dataset.selected || "",
    today: root.dataset.today || "",
    view: root.dataset.view || "month",
    baseUrl: root.dataset.baseUrl || "",
    navKw: root.dataset.navQuery || "",
    newUrl: root.dataset.newUrl || "",
    editUrlTpl: root.dataset.editUrlTpl || "",
    deleteUrlTpl: root.dataset.deleteUrlTpl || "",
    rsvpUrlTpl: root.dataset.rsvpUrlTpl || "",
    isParent: root.dataset.isParent === "1",
    csrfToken: root.dataset.csrfToken || "",
    childId: root.dataset.childId || "",
  };

  let currentView = cfg.view;
  let filterCategory = "";
  let filterUnit = "";
  let filterStatus = "";
  let selectedDate = cfg.selected;

  const $ = (sel, ctx) => (ctx || root).querySelector(sel);
  const $$ = (sel, ctx) => Array.from((ctx || root).querySelectorAll(sel));

  function filteredEvents() {
    return events.filter((e) => {
      if (filterCategory && e.category !== filterCategory) return false;
      if (filterUnit && e.unit !== filterUnit) return false;
      if (filterStatus && e.status !== filterStatus) return false;
      return true;
    });
  }

  function eventsOnDate(iso) {
    return filteredEvents().filter((e) => e.date === iso);
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function isoDate(y, m, d) {
    return y + "-" + pad(m) + "-" + pad(d);
  }

  function monthLabel(y, m) {
    const names = [
      "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ];
    return names[m - 1] + " " + y;
  }

  function navigate(y, m, sel) {
    const u = new URL(cfg.baseUrl, window.location.origin);
    u.searchParams.set("year", y);
    u.searchParams.set("month", m);
    if (sel) u.searchParams.set("selected", sel);
    if (currentView !== "month") u.searchParams.set("view", currentView);
    if (cfg.navKw) {
      cfg.navKw.split("&").forEach((pair) => {
        const [k, v] = pair.split("=");
        if (k) u.searchParams.set(k, decodeURIComponent(v || ""));
      });
    }
    window.location.href = u.pathname + u.search;
  }

  function renderMonthGrid() {
    const grid = $("#ag-cal-grid");
    if (!grid) return;
    grid.innerHTML = "";
    const y = cfg.year;
    const m = cfg.month;
    const first = new Date(y, m - 1, 1);
    let startDow = first.getDay();
    startDow = startDow === 0 ? 6 : startDow - 1;
    const daysInMonth = new Date(y, m, 0).getDate();
    const prevMonth = m === 1 ? 12 : m - 1;
    const prevYear = m === 1 ? y - 1 : y;
    const prevDays = new Date(prevYear, prevMonth, 0).getDate();

    const cells = [];
    for (let i = 0; i < startDow; i++) {
      const d = prevDays - startDow + i + 1;
      cells.push({ y: prevYear, m: prevMonth, d, other: true });
    }
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ y, m, d, other: false });
    }
    while (cells.length % 7 !== 0) {
      const n = cells.length - (startDow + daysInMonth) + 1;
      cells.push({
        y: m === 12 ? y + 1 : y,
        m: m === 12 ? 1 : m + 1,
        d: n,
        other: true,
      });
    }

    cells.forEach((c) => {
      const iso = isoDate(c.y, c.m, c.d);
      const evs = eventsOnDate(iso);
      const cell = document.createElement("div");
      cell.className = "ag-cal-day";
      if (c.other) cell.classList.add("is-other");
      if (iso === cfg.today) cell.classList.add("is-today");
      if (iso === selectedDate) cell.classList.add("is-selected");
      cell.dataset.date = iso;
      cell.innerHTML =
        '<span class="ag-cal-day__num">' +
        c.d +
        "</span>" +
        evs
          .slice(0, 3)
          .map(
            (e) =>
              '<div class="ag-ev-pill" style="background:' +
              (e.color_hex || e.category_color) +
              '" title="' +
              escapeHtml(e.title) +
              '"><span class="ag-ev-time">' +
              (e.time || "") +
              '</span> <span class="ag-ev-title">' +
              escapeHtml(e.title) +
              "</span></div>"
          )
          .join("");
      cell.addEventListener("click", () => {
        selectedDate = iso;
        renderMonthGrid();
        renderDayList();
      });
      grid.appendChild(cell);
    });
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function getClubeId() {
    const m = cfg.navKw.match(/clube_id=([^&]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function adminActionsHtml(e, compact) {
    if (!cfg.canWrite) return "";
    const editIcon =
      '<svg class="ag-action-btn__icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>';
    const delIcon =
      '<svg class="ag-action-btn__icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>';
    const editLabel = compact ? "Editar" : "Editar evento";
    const delLabel = compact ? "Excluir" : "Excluir evento";
    return (
      '<button type="button" class="ag-action-btn ag-action-btn--edit" data-edit-id="' +
      e.id +
      '" title="Editar">' +
      editIcon +
      "<span>" +
      editLabel +
      "</span></button>" +
      '<form method="post" class="ag-action-form" action="' +
      cfg.deleteUrlTpl.replace("__ID__", e.id) +
      '" onsubmit="return confirm(\'Excluir este evento permanentemente?\');">' +
      (cfg.navKw ? '<input type="hidden" name="clube_id" value="' + escapeHtml(getClubeId()) + '" />' : "") +
      '<button type="submit" class="ag-action-btn ag-action-btn--delete" title="Excluir">' +
      delIcon +
      "<span>" +
      delLabel +
      "</span></button></form>"
    );
  }

  function bindAdminActions(container) {
    if (!container || !cfg.canWrite) return;
    container.querySelectorAll("[data-edit-id]").forEach((btn) => {
      btn.addEventListener("click", (evClick) => {
        evClick.stopPropagation();
        const id = Number(btn.dataset.editId);
        const ev = events.find((x) => x.id === id);
        if (!ev) return;
        closeModal("ag-detail-modal");
        openForm(ev);
      });
    });
    container.querySelectorAll(".ag-action-form").forEach((form) => {
      form.addEventListener("click", (evClick) => evClick.stopPropagation());
    });
  }

  function renderDayList() {
    const list = $("#ag-day-events");
    if (!list) return;
    const evs = eventsOnDate(selectedDate);
    const label = $("#ag-day-label");
    if (label) {
      const p = selectedDate.split("-");
      label.textContent = p[2] + "/" + p[1] + "/" + p[0];
    }
    if (!evs.length) {
      list.innerHTML = '<p class="ag-empty">Nenhum evento neste dia.</p>';
      return;
    }
    list.innerHTML = evs.map((e) => eventCardHtml(e, true)).join("");
    list.querySelectorAll(".ag-event-card__main").forEach((el) => {
      el.addEventListener("click", () => openDetail(Number(el.closest("[data-event-id]").dataset.eventId)));
    });
    bindAdminActions(list);
  }

  function badgeClass(variant) {
    return "ag-badge ag-badge--" + (variant || "muted");
  }

  function eventCardHtml(e, compact) {
    const spots =
      e.max_capacity != null
        ? '<span class="text-xs text-slate-500">' +
          e.confirmed_count +
          "/" +
          e.max_capacity +
          " confirmados</span>"
        : "";
    const actions = cfg.canWrite
      ? '<div class="ag-event-card__actions">' + adminActionsHtml(e, true) + "</div>"
      : "";
    return (
      '<article class="ag-event-card" data-event-id="' +
      e.id +
      '">' +
      '<div class="ag-event-card__main">' +
      '<div class="flex justify-between gap-2 items-start">' +
      "<div><span class=\"text-lg\">" +
      e.category_icon +
      '</span> <span class="' +
      badgeClass(e.status_variant) +
      '">' +
      escapeHtml(e.status_label) +
      "</span></div>" +
      '<h4 class="font-bold text-navy-900 text-sm mt-1">' +
      escapeHtml(e.title) +
      "</h4>" +
      (e.time ? '<p class="text-xs text-slate-500 mt-0.5">🕐 ' + e.time + "</p>" : "") +
      (e.location && !compact ? '<p class="text-xs text-slate-500">📍 ' + escapeHtml(e.location) + "</p>" : "") +
      spots +
      "</div>" +
      actions +
      "</article>"
    );
  }

  function openDetail(id) {
    const e = events.find((x) => x.id === id);
    if (!e) return;
    const modal = $("#ag-detail-modal");
    const body = $("#ag-detail-body");
    if (!modal || !body) return;

    let rsvpHtml = "";
    if (cfg.isParent && e.status !== "cancelado" && e.status !== "rascunho") {
      const confirmed = e.user_rsvp && e.user_rsvp.status === "confirmed";
      const csrfInput = cfg.csrfToken
        ? '<input type="hidden" name="csrf_token" value="' + escapeHtml(cfg.csrfToken) + '" />'
        : "";
      const childInput = cfg.childId
        ? '<input type="hidden" name="member_id" value="' + escapeHtml(cfg.childId) + '" />'
        : "";
      rsvpHtml =
        '<form method="post" action="' +
        cfg.rsvpUrlTpl.replace("__ID__", e.id) +
        '" class="mt-3 ag-rsvp-form">' +
        csrfInput +
        childInput +
        '<button type="submit" class="ag-btn ag-btn--gold w-full">' +
        (confirmed ? "Cancelar presença" : "Confirmar presença") +
        "</button></form>";
      if (!cfg.childId) {
        rsvpHtml +=
          '<p class="text-xs text-amber-700 mt-2">Selecione um desbravador no menu lateral para confirmar presença.</p>';
      }
    }

    const adminActions = cfg.canWrite
      ? '<div class="ag-admin-actions">' + adminActionsHtml(e, false) + "</div>"
      : "";
    const headActions = document.getElementById("ag-detail-head-actions");
    if (headActions && cfg.canWrite) {
      headActions.innerHTML = adminActionsHtml(e, false);
      bindAdminActions(headActions);
    } else if (headActions) {
      headActions.innerHTML = "";
    }

    body.innerHTML =
      (e.banner_url
        ? '<img src="' + e.banner_url + '" alt="" class="ag-banner-preview mb-3 w-full h-36 object-cover rounded-xl" />'
        : "") +
      '<span class="' +
      badgeClass(e.status_variant) +
      '">' +
      escapeHtml(e.status_label) +
      "</span> " +
      '<span class="text-xs font-bold text-slate-500 ml-1">' +
      e.category_icon +
      " " +
      escapeHtml(e.category_label) +
      "</span>" +
      '<h3 class="text-xl font-extrabold text-navy-900 mt-2">' +
      escapeHtml(e.title) +
      "</h3>" +
      '<p class="text-sm text-slate-600 mt-2">' +
      formatDateBr(e.date) +
      (e.time ? " · " + e.time : "") +
      "</p>" +
      (e.location ? '<p class="text-sm mt-1">📍 ' + escapeHtml(e.location) + "</p>" : "") +
      (e.unit ? '<p class="text-sm text-slate-500">🛡 ' + escapeHtml(e.unit) + "</p>" : "") +
      (e.responsible_name ? '<p class="text-sm text-slate-500">👤 ' + escapeHtml(e.responsible_name) + "</p>" : "") +
      (e.body ? '<p class="text-sm text-slate-700 mt-3 whitespace-pre-line">' + escapeHtml(e.body) + "</p>" : "") +
      '<p class="text-xs text-slate-500 mt-2">' +
      e.confirmed_count +
      " confirmado(s)" +
      (e.spots_left != null ? " · " + e.spots_left + " vagas" : "") +
      "</p>" +
      rsvpHtml +
      adminActions +
      (cfg.isParent && !cfg.canWrite
        ? '<p class="text-xs text-slate-500 mt-4 pt-3 border-t border-slate-100">Somente visualização — alterações pela diretoria do clube.</p>'
        : "");

    bindAdminActions(body);

    openModal("ag-detail-modal");
  }

  function formatDateBr(iso) {
    const p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }

  function openForm(ev) {
    if (!cfg.canWrite) return;
    if (window.AgendaEventDrawer && window.AgendaEventDrawer.open) {
      window.AgendaEventDrawer.open(
        ev || null,
        selectedDate || cfg.today,
        cfg.editUrlTpl,
        cfg.newUrl
      );
      return;
    }
    const modal = $("#ag-form-modal");
    const form = $("#ag-event-form");
    if (!modal || !form) return;
    form.reset();
    $("#ag-form-title").textContent = ev ? "Editar evento" : "Novo evento";
    form.action = ev ? cfg.editUrlTpl.replace("__ID__", ev.id) : cfg.newUrl;
    if (ev) {
      form.title.value = ev.title;
      form.body.value = ev.body || "";
      form.event_date.value = ev.date;
      form.event_time.value = ev.time || "";
      form.category.value = ev.category;
      form.status.value = ev.status;
      form.location.value = ev.location || "";
      form.unit.value = ev.unit || "";
      form.responsible_name.value = ev.responsible_name || "";
      form.max_capacity.value = ev.max_capacity || "";
    } else {
      form.event_date.value = selectedDate || cfg.today;
    }
    openModal("ag-form-modal");
  }

  function openModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  $$("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      closeModal(btn.dataset.closeModal);
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    $$(".ag-modal-backdrop.is-open").forEach((bd) => closeModal(bd.id));
  });

  $$(".ag-modal-backdrop").forEach((bd) => {
    bd.addEventListener("click", (e) => {
      if (e.target === bd) closeModal(bd.id);
    });
  });

  $("#ag-btn-new")?.addEventListener("click", () => openForm(null));

  $("#ag-prev-month")?.addEventListener("click", () => {
    let y = cfg.year,
      m = cfg.month - 1;
    if (m < 1) {
      m = 12;
      y--;
    }
    navigate(y, m, selectedDate);
  });
  $("#ag-next-month")?.addEventListener("click", () => {
    let y = cfg.year,
      m = cfg.month + 1;
    if (m > 12) {
      m = 1;
      y++;
    }
    navigate(y, m, selectedDate);
  });

  $$(".ag-view-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      currentView = tab.dataset.view;
      $$(".ag-view-tab").forEach((t) => t.classList.toggle("is-active", t === tab));
      $("#ag-cal-month")?.classList.toggle("hidden", currentView !== "month");
    });
  });

  $$(".ag-chip[data-filter]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const type = chip.dataset.filter;
      const val = chip.dataset.value || "";
      if (type === "category") {
        filterCategory = filterCategory === val ? "" : val;
      } else if (type === "unit") {
        filterUnit = filterUnit === val ? "" : val;
      } else if (type === "status") {
        filterStatus = filterStatus === val ? "" : val;
      }
      $$('.ag-chip[data-filter="' + type + '"]').forEach((c) =>
        c.classList.toggle("is-active", c.dataset.value === (type === "category" ? filterCategory : type === "unit" ? filterUnit : filterStatus))
      );
      renderMonthGrid();
      renderDayList();
    });
  });

  const bannerInput = $("#ag-banner-input");
  bannerInput?.addEventListener("change", () => {
    const f = bannerInput.files[0];
    const prev = $("#ag-banner-preview");
    if (f && prev) {
      prev.src = URL.createObjectURL(f);
      prev.hidden = false;
    }
  });

  function initCountdown() {
    const el = $("#ag-countdown");
    const target = el?.dataset.target;
    if (!el || !target) return;
    function tick() {
      const end = new Date(target + "T12:00:00");
      const now = new Date();
      let diff = Math.max(0, end - now);
      const days = Math.floor(diff / 86400000);
      diff -= days * 86400000;
      const hours = Math.floor(diff / 3600000);
      diff -= hours * 3600000;
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff - mins * 60000) / 1000);
      el.innerHTML =
        '<div><strong>' + days + '</strong><small>dias</small></div>' +
        '<div><strong>' + pad(hours) + '</strong><small>hrs</small></div>' +
        '<div><strong>' + pad(mins) + '</strong><small>min</small></div>' +
        '<div><strong>' + pad(secs) + '</strong><small>seg</small></div>';
    }
    tick();
    setInterval(tick, 1000);
  }

  function initTimelineItems() {
    document.querySelectorAll(".ag-timeline__item[data-event-id]").forEach((item) => {
      const id = Number(item.dataset.eventId);
      const ev = events.find((x) => x.id === id);
      if (!ev) return;
      if (cfg.canWrite) {
        let wrap = item.querySelector(".ag-timeline__actions");
        if (!wrap) {
          wrap = document.createElement("div");
          wrap.className = "ag-timeline__actions";
          item.appendChild(wrap);
        }
        wrap.innerHTML = adminActionsHtml(ev, true);
        bindAdminActions(wrap);
      }
      item.addEventListener("click", (evClick) => {
        if (evClick.target.closest(".ag-action-btn, .ag-action-form")) return;
        openDetail(id);
      });
      item.addEventListener("keydown", (evKey) => {
        if (evKey.key === "Enter" || evKey.key === " ") {
          evKey.preventDefault();
          openDetail(id);
        }
      });
    });
  }

  renderMonthGrid();
  renderDayList();
  initCountdown();
  initTimelineItems();

  const openNew = new URLSearchParams(window.location.search).get("open_new");
  const editId = new URLSearchParams(window.location.search).get("edit");
  if (cfg.canWrite && openNew === "1") openForm(null);
  if (cfg.canWrite && editId) {
    const ev = events.find((e) => String(e.id) === editId);
    if (ev) openForm(ev);
  }

  window.openAgendaDetail = openDetail;

  document.addEventListener("ag-open-detail", (e) => {
    if (e.detail?.id) openDetail(e.detail.id);
  });
})();
