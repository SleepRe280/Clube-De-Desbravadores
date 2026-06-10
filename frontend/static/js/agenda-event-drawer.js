/**
 * Drawer lateral — criação/edição premium de eventos
 */
(function () {
  "use strict";

  const root = document.getElementById("ag-drawer-root");
  if (!root) return;

  const cfgEl = document.getElementById("agenda-drawer-config");
  let cfg = {};
  try {
    cfg = JSON.parse(cfgEl?.textContent || "{}");
  } catch (_) {
    cfg = {};
  }

  const categories = cfg.categories || {};
  const form = document.getElementById("ag-drawer-form");
  const page = document.getElementById("agenda-app");
  let step = 0;
  let state = {
    category: "reuniao",
    color: "#f9bc15",
    bannerUrl: cfg.default_banner || "",
    editingId: null,
  };

  const $ = (id) => document.getElementById(id);

  function catMeta(id) {
    return categories[id] || categories.reuniao || { label: id, color: "#f9bc15", icon: "📅" };
  }

  function open() {
    root.classList.add("is-open");
    root.setAttribute("aria-hidden", "false");
    page?.classList.add("ag-drawer-open");
    document.body.style.overflow = "hidden";
  }

  function close() {
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
    page?.classList.remove("ag-drawer-open");
    document.body.style.overflow = "";
  }

  function setStep(n) {
    step = Math.max(0, Math.min(3, n));
    document.querySelectorAll(".ag-drawer__step").forEach((btn) => {
      btn.classList.toggle("is-active", Number(btn.dataset.step) === step);
    });
    document.querySelectorAll(".ag-drawer-pane").forEach((pane) => {
      pane.classList.toggle("is-active", Number(pane.dataset.pane) === step);
    });
    $("ag-drawer-next").classList.toggle("hidden", step === 3);
    $("ag-drawer-submit").classList.toggle("hidden", step !== 3);
    if (step === 3) {
      buildReview();
      setPublishLabels(!!state.editingId);
    }
  }

  function buildTypeGrid() {
    const grid = $("ag-type-grid");
    if (!grid) return;
    grid.innerHTML = "";
    (cfg.types || []).forEach((t) => {
      const meta = catMeta(t.id);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ag-type-card" + (state.category === t.id ? " is-active" : "");
      btn.dataset.type = t.id;
      btn.innerHTML =
        '<span class="ag-type-card__icon">' +
        (t.icon || meta.icon) +
        '</span><span class="ag-type-card__label">' +
        (t.label || meta.label) +
        "</span>";
      btn.addEventListener("click", () => selectType(t.id));
      grid.appendChild(btn);
    });
  }

  function selectType(id) {
    state.category = id;
    const meta = catMeta(id);
    state.color = meta.color || state.color;
    $("ag-category-field").value = id;
    $("ag-color-hex").value = state.color;
    document.querySelectorAll(".ag-type-card").forEach((c) => {
      c.classList.toggle("is-active", c.dataset.type === id);
    });
    document.querySelectorAll(".ag-color-dot").forEach((d) => {
      d.classList.toggle("is-active", d.dataset.hex === state.color);
    });
    renderChecklist();
    syncPreview();
  }

  function buildColorDots() {
    const wrap = $("ag-color-dots");
    if (!wrap) return;
    wrap.innerHTML = "";
    (cfg.colors || []).forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ag-color-dot" + (state.color === c.hex ? " is-active" : "");
      b.style.background = c.hex;
      b.dataset.hex = c.hex;
      b.title = c.label;
      b.addEventListener("click", () => {
        state.color = c.hex;
        $("ag-color-hex").value = c.hex;
        document.querySelectorAll(".ag-color-dot").forEach((d) => {
          d.classList.toggle("is-active", d.dataset.hex === c.hex);
        });
        syncPreview();
      });
      wrap.appendChild(b);
    });
  }

  function buildTemplates() {
    const row = $("ag-template-row");
    if (!row) return;
    row.innerHTML = "";
    Object.keys(cfg.templates || {}).forEach((key) => {
      const t = cfg.templates[key];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ag-template-btn";
      btn.textContent = t.label || key;
      btn.addEventListener("click", () => applyTemplate(key));
      row.appendChild(btn);
    });
  }

  function applyTemplate(key) {
    const t = cfg.templates[key];
    if (!t) return;
    $("ag-template-id").value = key;
    if (t.title) $("ag-f-title").value = t.title;
    if (t.body) $("ag-f-body").value = t.body;
    if (t.category) selectType(t.category);
    if (t.start_time) $("ag-f-start-time").value = t.start_time;
    if (t.end_time) $("ag-f-end-time").value = t.end_time;
    if (t.status) $("ag-status-field").value = t.status;
    const sd = $("ag-f-start-date").value;
    if (sd && t.duration_days != null) {
      const d = new Date(sd + "T12:00:00");
      d.setDate(d.getDate() + Number(t.duration_days));
      $("ag-f-end-date").value = d.toISOString().slice(0, 10);
    }
    renderChecklist(t.checklist);
    updateDuration();
    syncPreview();
  }

  function buildLeaders() {
    const grid = $("ag-leader-grid");
    if (!grid) return;
    grid.innerHTML = "";
    (cfg.leaders || []).forEach((l) => {
      const card = document.createElement("div");
      card.className = "ag-leader-card";
      card.dataset.id = l.id;
      card.dataset.name = l.name;
      const ph = l.photo
        ? '<img src="' + l.photo + '" alt="" />'
        : '<span class="ag-leader-ph">' + (l.name[0] || "?") + "</span>";
      card.innerHTML =
        ph +
        '<motion><strong style="display:block;font-size:0.85rem">' +
        l.name +
        '</strong><span style="font-size:0.72rem;opacity:0.75">' +
        l.role +
        "</span></motion>";
      card.innerHTML = card.innerHTML.replace(/<\/?motion>/g, function (m) {
        return m.indexOf("/") === 1 ? "</div>" : "<motion>";
      }).replace("<motion>", "<div>").replace("</motion>", "</div>");
      card.addEventListener("click", () => {
        document.querySelectorAll(".ag-leader-card").forEach((c) => c.classList.remove("is-active"));
        card.classList.add("is-active");
        $("ag-f-responsible-id").value = l.id;
        $("ag-f-responsible-name").value = l.name;
        syncPreview();
      });
      grid.appendChild(card);
    });
  }

  function renderChecklist(items) {
    const list = $("ag-checklist");
    if (!list) return;
    const cat = state.category;
    const rows = items || (cfg.checklists && cfg.checklists[cat]) || [];
    list.innerHTML = rows
      .map(
        (text, i) =>
          '<li><input type="checkbox" name="checklist_done" value="' +
          i +
          '" id="ag-cl-' +
          i +
          '" /><label for="ag-cl-' +
          i +
          '">' +
          text +
          "</label></li>"
      )
      .join("");
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "checklist";
    hidden.value = JSON.stringify(rows);
    hidden.id = "ag-checklist-json";
    const old = $("ag-checklist-json");
    if (old) old.remove();
    hidden.id = "ag-checklist-json";
    list.appendChild(hidden);
  }

  function updateDuration() {
    const sd = $("ag-f-start-date").value;
    const ed = $("ag-f-end-date").value || sd;
    const st = $("ag-f-start-time").value;
    const et = $("ag-f-end-time").value;
    const el = $("ag-duration-label");
    if (!el || !sd) {
      if (el) el.textContent = "Duração: —";
      return;
    }
    const start = new Date(sd + "T" + (st || "00:00") + ":00");
    const end = new Date(ed + "T" + (et || st || "23:59") + ":00");
    let diff = Math.max(0, end - start);
    const days = Math.floor(diff / 86400000);
    diff -= days * 86400000;
    const hours = Math.floor(diff / 3600000);
    diff -= hours * 3600000;
    const mins = Math.floor(diff / 60000);
    let parts = [];
    if (days) parts.push(days + (days === 1 ? " dia" : " dias"));
    if (hours) parts.push(hours + (hours === 1 ? " hora" : " horas"));
    if (mins && !days) parts.push(mins + " min");
    el.textContent = "Duração: " + (parts.length ? parts.join(" e ") : "mesmo dia");
  }

  function syncPreview() {
    const title = $("ag-f-title").value || "Nome do evento";
    const meta = catMeta(state.category);
    $("ag-preview-title").textContent = title;
    $("ag-preview-badge").textContent = meta.label;
    $("ag-preview-badge").style.color = state.color;
    const sd = $("ag-f-start-date").value;
    const ed = $("ag-f-end-date").value;
    const st = $("ag-f-start-time").value;
    const et = $("ag-f-end-time").value;
    let dateTxt = "—";
    if (sd) {
      const p = sd.split("-");
      dateTxt = p[2] + "/" + p[1] + "/" + p[0];
      if (st) dateTxt += " · " + st.slice(0, 5);
      if (ed && ed !== sd) {
        const pe = ed.split("-");
        dateTxt += " → " + pe[2] + "/" + pe[1];
        if (et) dateTxt += " " + et.slice(0, 5);
      }
    }
    $("ag-preview-date").textContent = "📅 " + dateTxt;
    const loc = $("ag-f-location").value || "Local a definir";
    $("ag-preview-location").textContent = "📍 " + loc;
    const banner = $("ag-preview-banner");
    if (banner) {
      banner.style.backgroundImage = "url('" + (state.bannerUrl || cfg.default_banner) + "')";
      banner.style.boxShadow = "inset 0 -40px 60px " + state.color + "55";
    }
    const card = $("ag-preview-card");
    if (card) card.style.borderColor = state.color + "44";

    const cd = $("ag-preview-countdown");
    if (cd && sd) {
      const target = new Date(sd + "T" + (st || "09:00") + ":00");
      const now = new Date();
      let diff = Math.max(0, target - now);
      const d = Math.floor(diff / 86400000);
      diff -= d * 86400000;
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff - h * 3600000) / 60000);
      cd.innerHTML =
        "<span>" + d + "d</span><span>" + h + "h</span><span>" + m + "m</span>";
    }

    const av = $("ag-preview-avatars");
    if (av) {
      const audience = Array.from(document.querySelectorAll('input[name="audience"]:checked')).length;
      const n = Math.min(4, Math.max(1, audience));
      av.innerHTML = Array.from({ length: n }, (_, i) => "<span>" + (i + 1) + "</span>").join("");
    }
  }

  function buildMetaJson() {
    const audience = Array.from(document.querySelectorAll('input[name="audience"]:checked')).map(
      (el) => el.value
    );
    const checklistEl = $("ag-checklist-json");
    let checklist = [];
    try {
      checklist = JSON.parse(checklistEl?.value || "[]");
    } catch (_) {}
    const done = Array.from(document.querySelectorAll('input[name="checklist_done"]:checked')).map(
      (el) => el.value
    );
    return JSON.stringify({
      audience,
      require_rsvp: !!document.querySelector('input[name="require_rsvp"]')?.checked,
      allow_guests: !!document.querySelector('input[name="allow_guests"]')?.checked,
      send_notification: !!document.querySelector('input[name="send_notification"]')?.checked,
      qr_checkin: !!document.querySelector('input[name="qr_checkin"]')?.checked,
      auto_reminder: !!document.querySelector('input[name="auto_reminder"]')?.checked,
      responsible_id: $("ag-f-responsible-id").value || null,
      template_id: $("ag-template-id").value || null,
      checklist,
      checklist_done: done,
    });
  }

  function buildReview() {
    const box = $("ag-review-summary");
    if (!box) return;
    const meta = catMeta(state.category);
    box.innerHTML =
      "<p><strong>Tipo:</strong> " +
      meta.icon +
      " " +
      meta.label +
      "</p>" +
      "<p><strong>Título:</strong> " +
      ($("ag-f-title").value || "—") +
      "</p>" +
      "<p><strong>Data:</strong> " +
      $("ag-preview-date").textContent +
      "</p>" +
      "<p><strong>Local:</strong> " +
      ($("ag-f-location").value || "—") +
      "</p>" +
      "<p><strong>Participantes:</strong> " +
      (Array.from(document.querySelectorAll('input[name="audience"]:checked'))
        .map((e) => e.parentElement.textContent.trim())
        .join(", ") || "Não definido") +
      "</p>";
  }

  function resetForm(selectedDate) {
    form.reset();
    step = 0;
    setStep(0);
    state.category = "reuniao";
    state.color = catMeta("reuniao").color;
    state.bannerUrl = cfg.default_banner || "";
    state.editingId = null;
    $("ag-f-start-date").value = selectedDate || "";
    $("ag-category-field").value = "reuniao";
    $("ag-color-hex").value = state.color;
    $("ag-status-field").value = "planejado";
    $("ag-save-action").value = "publish";
    buildTypeGrid();
    buildColorDots();
    selectType("reuniao");
    renderChecklist();
    document.querySelectorAll(".ag-leader-card").forEach((c) => c.classList.remove("is-active"));
    $("ag-drawer-title").textContent = "Novo Evento";
    setPublishLabels(false);
    syncPreview();
    updateDuration();
  }

  function setPublishLabels(editing) {
    const submit = $("ag-drawer-submit");
    if (submit) submit.textContent = editing ? "Salvar alterações" : "Publicar evento";
    const next = $("ag-drawer-next");
    if (next && step === 3) next.classList.add("hidden");
  }

  function fillFromEvent(ev, editUrl) {
    state.editingId = ev.id;
    $("ag-drawer-title").textContent = "Editar evento";
    form.action = editUrl;
    setPublishLabels(true);
    $("ag-f-title").value = ev.title || "";
    $("ag-f-body").value = ev.body || "";
    $("ag-f-start-date").value = ev.date || "";
    $("ag-f-end-date").value = ev.end_date || "";
    $("ag-f-start-time").value = ev.time || "";
    $("ag-f-end-time").value = ev.end_time || "";
    $("ag-f-location").value = ev.location || "";
    $("ag-f-capacity").value = ev.max_capacity || "";
    selectType(ev.category || "reuniao");
    if (ev.color_hex) {
      state.color = ev.color_hex;
      $("ag-color-hex").value = ev.color_hex;
    }
    $("ag-status-field").value = ev.status || "planejado";
    $("ag-f-responsible-name").value = ev.responsible_name || "";
    if (ev.banner_url) state.bannerUrl = ev.banner_url;
    const meta = ev.meta || {};
    (meta.audience || []).forEach((a) => {
      const inp = document.querySelector('input[name="audience"][value="' + a + '"]');
      if (inp) inp.checked = true;
    });
    if (meta.responsible_id) {
      $("ag-f-responsible-id").value = meta.responsible_id;
      document.querySelectorAll(".ag-leader-card").forEach((c) => {
        c.classList.toggle("is-active", String(c.dataset.id) === String(meta.responsible_id));
      });
    }
    const toggles = {
      require_rsvp: "require_rsvp",
      allow_guests: "allow_guests",
      send_notification: "send_notification",
      qr_checkin: "qr_checkin",
      auto_reminder: "auto_reminder",
    };
    Object.keys(toggles).forEach((key) => {
      const inp = document.querySelector('input[name="' + toggles[key] + '"]');
      if (inp) inp.checked = !!meta[key];
    });
    renderChecklist(meta.checklist);
    (meta.checklist_done || []).forEach((idx) => {
      const cb = document.getElementById("ag-cl-" + idx);
      if (cb) cb.checked = true;
    });
    updateDuration();
    syncPreview();
  }

  function openDrawer(ev, selectedDate, editUrlTpl, newUrl) {
    resetForm(selectedDate);
    form.action = ev ? editUrlTpl.replace("__ID__", ev.id) : newUrl;
    if (ev) fillFromEvent(ev, form.action);
    open();
  }

  $("ag-drawer-close")?.addEventListener("click", close);
  $("ag-drawer-cancel")?.addEventListener("click", close);
  $("ag-drawer-backdrop")?.addEventListener("click", close);
  $("ag-drawer-next")?.addEventListener("click", () => {
    if (step === 0) {
      if (!$("ag-f-title").value.trim()) {
        $("ag-f-title").focus();
        return;
      }
      if (!$("ag-f-start-date").value) {
        $("ag-f-start-date").focus();
        return;
      }
    }
    setStep(step + 1);
  });
  document.querySelectorAll(".ag-drawer__step").forEach((btn) => {
    btn.addEventListener("click", () => setStep(Number(btn.dataset.step)));
  });
  $("ag-drawer-draft")?.addEventListener("click", () => {
    $("ag-save-action").value = "draft";
    $("ag-meta-json").value = buildMetaJson();
    form.requestSubmit();
  });
  form?.addEventListener("submit", () => {
    $("ag-meta-json").value = buildMetaJson();
    $("ag-color-hex").value = state.color;
  });

  ["ag-f-title", "ag-f-body", "ag-f-location", "ag-f-start-date", "ag-f-end-date", "ag-f-start-time", "ag-f-end-time"].forEach(
    (id) => {
      $(id)?.addEventListener("input", () => {
        if (id === "ag-f-body") {
          const c = $("ag-body-count");
          if (c) c.textContent = String($("ag-f-body").value.length);
        }
        updateDuration();
        syncPreview();
      });
    }
  );
  document.querySelectorAll('input[name="audience"]').forEach((el) => {
    el.addEventListener("change", syncPreview);
  });
  $("ag-f-banner")?.addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (f) {
      state.bannerUrl = URL.createObjectURL(f);
      syncPreview();
    }
  });
  $("ag-location-clear")?.addEventListener("click", () => {
    $("ag-f-location").value = "";
    $("ag-f-location").focus();
    syncPreview();
  });

  buildTemplates();
  buildLeaders();

  window.AgendaEventDrawer = {
    open: openDrawer,
    close: close,
  };
})();
