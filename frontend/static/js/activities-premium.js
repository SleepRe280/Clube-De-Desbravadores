/**
 * Atividades — dashboard, modal de tarefa (requisitos oficiais), AJAX de status
 */
(function () {
  const app = document.getElementById("act-app");
  if (!app) return;

  const modal = document.getElementById("act-modal-homework");
  const btnNew = document.getElementById("act-btn-new-homework");
  const reqIdInput = document.getElementById("act-hw-req-id");
  const reqsWrap = document.getElementById("act-hw-reqs-wrap");
  const reqTree = document.getElementById("act-hw-req-tree");
  const loader = document.getElementById("act-hw-loader");
  const targetWrap = document.getElementById("act-hw-target-wrap");
  const detailsWrap = document.getElementById("act-hw-details-wrap");
  const foot = document.getElementById("act-hw-foot");
  const submitBtn = document.getElementById("act-hw-submit");
  const clubeId = app.dataset.clubeId;

  let selectedClassSlug = "";

  function closeModal() {
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    resetHomeworkModal();
  }

  function resetHomeworkModal() {
    selectedClassSlug = "";
    if (reqIdInput) reqIdInput.value = "";
    if (reqTree) reqTree.innerHTML = "";
    [reqsWrap, targetWrap, detailsWrap, foot].forEach((el) => {
      if (el) el.hidden = true;
    });
    if (submitBtn) submitBtn.disabled = true;
    document.querySelectorAll(".act-hw-class-btn.is-selected").forEach((b) => {
      b.classList.remove("is-selected");
    });
  }

  function requirementsUrl(slug) {
    const base = `/admin/atividades/catalogo/${encodeURIComponent(slug)}/requisitos.json`;
    if (clubeId) return `${base}?clube_id=${encodeURIComponent(clubeId)}`;
    return base;
  }

  async function loadRequirements(slug) {
    if (!reqTree || !loader) return;
    reqsWrap.hidden = false;
    loader.hidden = false;
    reqTree.innerHTML = "";
    try {
      const res = await fetch(requirementsUrl(slug), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "load_failed");
      renderRequirementTree(data);
      targetWrap.hidden = false;
      detailsWrap.hidden = false;
      foot.hidden = false;
    } catch {
      reqTree.innerHTML =
        '<p class="act-hw-error">Não foi possível carregar os requisitos. Tente novamente.</p>';
    } finally {
      loader.hidden = true;
    }
  }

  function renderRequirementTree(data) {
    const frag = document.createDocumentFragment();
    (data.sections || []).forEach((sec) => {
      const block = document.createElement("div");
      block.className = "act-hw-section";
      const title = document.createElement("p");
      title.className = "act-hw-section__title";
      title.textContent = sec.is_advanced
        ? `Classe avançada — ${sec.title}`
        : `${sec.code}. ${sec.title}`;
      block.appendChild(title);

      (sec.requirements || []).forEach((req) => {
        const label = document.createElement("label");
        label.className = "act-hw-req-option";
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "hw_requirement_pick";
        radio.value = String(req.id);
        radio.addEventListener("change", () => {
          if (reqIdInput) reqIdInput.value = radio.value;
          if (submitBtn) submitBtn.disabled = false;
          document.querySelectorAll(".act-hw-req-option").forEach((l) => {
            l.classList.toggle("is-selected", l.querySelector("input")?.checked);
          });
        });
        const body = document.createElement("span");
        body.className = "act-hw-req-option__body";
        body.innerHTML = `<span class="act-hw-req-num">${req.number_label}</span> <strong>${escapeHtml(req.title)}</strong>`;
        if (req.is_optional) {
          body.innerHTML += ' <em class="act-hw-opt">opcional</em>';
        }
        label.append(radio, body);
        block.appendChild(label);
      });
      frag.appendChild(block);
    });
    reqTree.appendChild(frag);
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  if (btnNew && modal) {
    btnNew.addEventListener("click", () => {
      resetHomeworkModal();
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
    });
    modal.querySelectorAll("[data-act-close-modal]").forEach((el) => {
      el.addEventListener("click", closeModal);
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.querySelectorAll(".act-hw-class-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slug = btn.dataset.classSlug;
      if (!slug) return;
      selectedClassSlug = slug;
      document.querySelectorAll(".act-hw-class-btn").forEach((b) => {
        b.classList.toggle("is-selected", b === btn);
      });
      if (reqIdInput) reqIdInput.value = "";
      if (submitBtn) submitBtn.disabled = true;
      loadRequirements(slug);
    });
  });

  document.querySelectorAll('input[name="target_mode"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      const unitsPanel = document.getElementById("act-hw-units-panel");
      const membersPanel = document.getElementById("act-hw-members-panel");
      if (unitsPanel) unitsPanel.hidden = radio.value !== "units";
      if (membersPanel) membersPanel.hidden = radio.value !== "members";
    });
  });

  document.querySelectorAll("[data-act-req-form]").forEach((form) => {
    form.addEventListener("submit", async function (e) {
      const btn = e.submitter;
      if (!btn || btn.type !== "submit") return;
      e.preventDefault();
      const status = btn.value || btn.getAttribute("name");
      const body = new FormData(form);
      body.set("status", status);
      const action = form.getAttribute("action");
      try {
        const res = await fetch(action, {
          method: "POST",
          body,
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        const data = await res.json();
        if (data.ok) window.location.reload();
        else form.submit();
      } catch {
        form.submit();
      }
    });
  });

  const detail = document.getElementById("act-member-detail");
  if (detail) detail.scrollIntoView({ behavior: "smooth", block: "start" });
})();
