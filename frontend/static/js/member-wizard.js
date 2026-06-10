/**
 * Wizard de cadastro — novo desbravador (admin)
 */
(function () {
  const form = document.getElementById("mw-form");
  if (!form) return;

  const TOTAL = 5;
  let current = 1;
  const panels = form.querySelectorAll(".mw-step-panel");
  const stepperItems = document.querySelectorAll(".mw-stepper__item");
  const progressList = document.querySelectorAll(".mw-progress-list li");
  const ring = document.querySelector(".mw-ring__progress");
  const pctEl = document.getElementById("mw-ring-pct") || document.querySelector(".mw-ring__pct strong");
  const mobileBar = document.getElementById("mw-mobile-bar");
  const mobileStep = document.getElementById("mw-mobile-step");
  const mobileTitle = document.getElementById("mw-mobile-title");
  const btnPrev = document.getElementById("mw-btn-prev");
  const btnNext = document.getElementById("mw-btn-next");
  const btnSave = document.getElementById("mw-btn-save");
  const guardiansList = document.getElementById("mw-guardians-list");
  const guardiansJson = document.getElementById("guardians_json");
  const photoInput = document.getElementById("mw-photo-input");
  const photoDrop = document.getElementById("mw-photo-drop");
  const photoPreview = document.getElementById("mw-photo-preview-img");
  const photoPlaceholder = document.getElementById("mw-photo-placeholder");
  const successOverlay = document.getElementById("mw-success");
  const infoBanner = document.getElementById("mw-info-banner");
  const mapEl = document.getElementById("mw-map");

  const stepTitles = [];
  stepperItems.forEach((el) => {
    const label = el.querySelector(".mw-stepper__label");
    if (label) stepTitles[Number(el.dataset.step)] = label.textContent.trim();
  });

  function setStep(n) {
    current = Math.max(1, Math.min(TOTAL, n));
    panels.forEach((p) => {
      p.classList.toggle("is-active", Number(p.dataset.step) === current);
    });
    stepperItems.forEach((el) => {
      const s = Number(el.dataset.step);
      el.classList.toggle("is-active", s === current);
      el.classList.toggle("is-done", s < current);
      el.classList.toggle("is-locked", s > current);
      el.setAttribute("aria-current", s === current ? "step" : "false");
    });
    progressList.forEach((el) => {
      const s = Number(el.dataset.step);
      el.classList.remove("is-active", "is-done", "is-locked");
      if (s === current) el.classList.add("is-active");
      else if (s < current) el.classList.add("is-done");
      else el.classList.add("is-locked");
    });
    const pct = Math.round((current / TOTAL) * 100);
    if (ring) ring.setAttribute("stroke-dashoffset", String(283 - (283 * pct) / 100));
    if (pctEl) pctEl.textContent = pct + "%";
    if (mobileBar) mobileBar.style.width = pct + "%";
    if (mobileStep) mobileStep.textContent = String(current);
    if (mobileTitle) mobileTitle.textContent = stepTitles[current] || "";
    if (btnPrev) btnPrev.style.visibility = current === 1 ? "hidden" : "visible";
    if (btnNext) {
      btnNext.hidden = current >= TOTAL;
      btnNext.style.display = current >= TOTAL ? "none" : "inline-flex";
    }
    if (btnSave) {
      btnSave.hidden = current < TOTAL;
      btnSave.style.display = current >= TOTAL ? "inline-flex" : "none";
    }
    if (current === 5) fillReview();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function digitsOnly(s) {
    return (s || "").replace(/\D/g, "");
  }

  function calcAge(isoDate) {
    if (!isoDate) return "";
    const d = new Date(isoDate + "T12:00:00");
    if (isNaN(d.getTime())) return "";
    const today = new Date();
    let age = today.getFullYear() - d.getFullYear();
    const m = today.getMonth() - d.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age--;
    return age >= 0 ? String(age) : "";
  }

  const birthInput = form.querySelector('[name="birth_date"]');
  const ageInput = form.querySelector('[name="age_display"]');
  if (birthInput && ageInput) {
    birthInput.addEventListener("change", () => {
      ageInput.value = calcAge(birthInput.value);
    });
    if (birthInput.value) ageInput.value = calcAge(birthInput.value);
  }

  function maskCpf(el) {
    if (!el) return;
    el.addEventListener("input", () => {
      let v = digitsOnly(el.value).slice(0, 11);
      if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{0,2})/, "$1.$2.$3-$4");
      else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{0,3})/, "$1.$2.$3");
      else if (v.length > 3) v = v.replace(/(\d{3})(\d{0,3})/, "$1.$2");
      el.value = v;
    });
  }
  maskCpf(form.querySelector('[name="cpf"]'));

  function maskPhone(el) {
    if (!el) return;
    el.addEventListener("input", () => {
      let v = digitsOnly(el.value).slice(0, 11);
      if (v.length > 10) v = v.replace(/(\d{2})(\d{5})(\d{0,4})/, "($1) $2-$3");
      else if (v.length > 6) v = v.replace(/(\d{2})(\d{4})(\d{0,4})/, "($1) $2-$3");
      else if (v.length > 2) v = v.replace(/(\d{2})(\d{0,5})/, "($1) $2");
      el.value = v;
    });
  }
  form.querySelectorAll('[data-mask="phone"]').forEach(maskPhone);

  function maskCep(el) {
    if (!el) return;
    el.addEventListener("input", () => {
      let v = digitsOnly(el.value).slice(0, 8);
      if (v.length > 5) v = v.replace(/(\d{5})(\d{0,3})/, "$1-$2");
      el.value = v;
    });
  }
  const cepInput = form.querySelector('[name="address_cep"]');
  maskCep(cepInput);
  const cepLoading = document.getElementById("mw-cep-loading");

  function updateMap() {
    if (!mapEl) return;
    const street = form.querySelector('[name="address_street"]')?.value?.trim();
    const city = form.querySelector('[name="address_city"]')?.value?.trim();
    const state = form.querySelector('[name="address_state"]')?.value?.trim();
    const parts = [street, city, state, "Brasil"].filter(Boolean);
    if (parts.length < 2) {
      mapEl.innerHTML = '<p class="mw-map__empty">Informe o CEP ou cidade para ver o mapa</p>';
      return;
    }
    const q = encodeURIComponent(parts.join(", "));
    mapEl.innerHTML =
      '<iframe title="Mapa do endereço" loading="lazy" src="https://maps.google.com/maps?q=' +
      q +
      '&z=15&output=embed"></iframe>';
  }

  ["address_street", "address_city", "address_state"].forEach((name) => {
    form.querySelector('[name="' + name + '"]')?.addEventListener("blur", updateMap);
  });

  if (cepInput) {
    cepInput.addEventListener("blur", async () => {
      const cep = digitsOnly(cepInput.value);
      if (cep.length !== 8) return;
      if (cepLoading) cepLoading.classList.add("is-visible");
      try {
        const res = await fetch("https://viacep.com.br/ws/" + cep + "/json/");
        const data = await res.json();
        if (!data.erro) {
          const set = (n, v) => {
            const el = form.querySelector('[name="' + n + '"]');
            if (el && v) el.value = v;
          };
          set("address_street", data.logradouro);
          set("address_neighborhood", data.bairro);
          set("address_city", data.localidade);
          set("address_state", data.uf);
          updateMap();
        }
      } catch (_) {
        /* ignore */
      } finally {
        if (cepLoading) cepLoading.classList.remove("is-visible");
      }
    });
  }

  function showPreview(file) {
    if (!file || !file.type.startsWith("image/")) return;
    if (file.size > 5 * 1024 * 1024) {
      alert("A imagem deve ter no máximo 5 MB.");
      return;
    }
    const url = URL.createObjectURL(file);
    if (photoPreview) {
      photoPreview.src = url;
      photoPreview.hidden = false;
    }
    if (photoPlaceholder) photoPlaceholder.hidden = true;
  }

  if (photoInput && photoDrop) {
    photoDrop.addEventListener("click", () => photoInput.click());
    photoDrop.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        photoInput.click();
      }
    });
    photoInput.addEventListener("change", () => {
      if (photoInput.files[0]) showPreview(photoInput.files[0]);
    });
    ["dragenter", "dragover"].forEach((ev) => {
      photoDrop.addEventListener(ev, (e) => {
        e.preventDefault();
        photoDrop.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((ev) => {
      photoDrop.addEventListener(ev, (e) => {
        e.preventDefault();
        photoDrop.classList.remove("is-dragover");
      });
    });
    photoDrop.addEventListener("drop", (e) => {
      const f = e.dataTransfer?.files?.[0];
      if (f) {
        const dt = new DataTransfer();
        dt.items.add(f);
        photoInput.files = dt.files;
        showPreview(f);
      }
    });
  }

  function guardianInitials(name) {
    const parts = (name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function bindGuardianCard(card) {
    const nameIn = card.querySelector('[data-g="name"]');
    const av = card.querySelector(".mw-guardian-card__avatar");
    if (nameIn && av) {
      nameIn.addEventListener("input", () => {
        av.textContent = guardianInitials(nameIn.value);
      });
    }
    const rm = card.querySelector("[data-g-remove]");
    if (rm) {
      rm.addEventListener("click", () => {
        if (guardiansList.children.length <= 1) return;
        card.remove();
      });
    }
  }

  function collectGuardians() {
    const cards = guardiansList.querySelectorAll(".mw-guardian-card");
    const out = [];
    cards.forEach((card) => {
      const name = (card.querySelector('[data-g="name"]')?.value || "").trim();
      if (!name) return;
      out.push({
        name,
        relation: (card.querySelector('[data-g="relation"]')?.value || "").trim(),
        phone: (card.querySelector('[data-g="phone"]')?.value || "").trim(),
        whatsapp: (card.querySelector('[data-g="whatsapp"]')?.value || "").trim(),
        email: (card.querySelector('[data-g="email"]')?.value || "").trim(),
      });
    });
    return out;
  }

  function syncGuardiansJson() {
    if (guardiansJson) guardiansJson.value = JSON.stringify(collectGuardians());
  }

  guardiansList.querySelectorAll(".mw-guardian-card").forEach(bindGuardianCard);

  document.getElementById("mw-add-guardian")?.addEventListener("click", () => {
    const tpl = document.getElementById("mw-guardian-tpl");
    if (!tpl || guardiansList.children.length >= 4) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = tpl.innerHTML.trim();
    const card = wrap.firstElementChild;
    guardiansList.appendChild(card);
    const title = card.querySelector(".mw-guardian-card__title");
    if (title) title.textContent = "Responsável " + guardiansList.children.length;
    bindGuardianCard(card);
    card.querySelectorAll('[data-mask="phone"]').forEach(maskPhone);
  });

  function clearFieldError(field) {
    const wrap = field.closest(".mw-field");
    if (wrap) wrap.classList.remove("is-error");
    field.classList.remove("is-invalid");
  }

  function setFieldError(field, msg) {
    const wrap = field.closest(".mw-field");
    if (wrap) {
      wrap.classList.add("is-error");
      const err = wrap.querySelector(".mw-field-error");
      if (err) err.textContent = msg;
    }
    field.classList.add("is-invalid");
  }

  function validateStep(step) {
    let ok = true;
    const panel = form.querySelector('.mw-step-panel[data-step="' + step + '"]');
    if (!panel) return true;
    panel.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    panel.querySelectorAll(".mw-field.is-error").forEach((el) => el.classList.remove("is-error"));

    panel.querySelectorAll("[data-required]").forEach((field) => {
      clearFieldError(field);
      const v = (field.value || "").trim();
      if (!v) {
        setFieldError(field, "Campo obrigatório");
        ok = false;
      }
    });

    if (step === 1) {
      const cpf = form.querySelector('[name="cpf"]');
      if (cpf && cpf.value.trim()) {
        if (digitsOnly(cpf.value).length !== 11) {
          setFieldError(cpf, "CPF deve ter 11 dígitos");
          ok = false;
        }
      }
      const email = form.querySelector('[name="email"]');
      if (email && email.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
        setFieldError(email, "E-mail inválido");
        ok = false;
      }
    }

    if (step === 3) {
      syncGuardiansJson();
      if (!collectGuardians().length) {
        const first = guardiansList.querySelector('[data-g="name"]');
        if (first) setFieldError(first, "Informe ao menos um responsável");
        ok = false;
      }
      const emPhone = form.querySelector('[name="emergency_contact_phone"]');
      if (emPhone && digitsOnly(emPhone.value).length < 10) {
        setFieldError(emPhone, "Telefone inválido");
        ok = false;
      }
    }

    if (!ok) {
      panel.querySelector(".is-invalid")?.focus();
    }
    return ok;
  }

  function formatDateBr(iso) {
    if (!iso) return "—";
    const p = iso.split("-");
    if (p.length !== 3) return iso;
    return p[2] + "/" + p[1] + "/" + p[0];
  }

  function fillReview() {
    const g = collectGuardians();
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text || "—";
    };
    set("rv-name", form.querySelector('[name="full_name"]')?.value);
    set("rv-birth", formatDateBr(form.querySelector('[name="birth_date"]')?.value));
    const age = form.querySelector('[name="age_display"]')?.value;
    set("rv-age", age ? age + " anos" : "");
    set("rv-cpf", form.querySelector('[name="cpf"]')?.value || "Não informado");
    set("rv-sex", form.querySelector('[name="sex"]')?.selectedOptions?.[0]?.text);
    set("rv-blood", form.querySelector('[name="blood_type"]')?.value);
    set("rv-phone", form.querySelector('[name="phone"]')?.value || "Não informado");
    set("rv-email", form.querySelector('[name="email"]')?.value || "Não informado");
    set("rv-unit", form.querySelector('[name="unit"]')?.value);
    set("rv-class", form.querySelector('[name="notebook_current"]')?.value);
    const statusEl = form.querySelector('[name="member_status"]:checked');
    const statusLabel = statusEl?.nextElementSibling?.textContent || "—";
    set("rv-status-badge", statusLabel);
    set("rv-joined", formatDateBr(form.querySelector('[name="joined_at"]')?.value));
    set("rv-role", form.querySelector('[name="unit_role"]')?.selectedOptions?.[0]?.text);
    const addr = [
      form.querySelector('[name="address_street"]')?.value,
      form.querySelector('[name="address_number"]')?.value,
      form.querySelector('[name="address_neighborhood"]')?.value,
      form.querySelector('[name="address_city"]')?.value,
      form.querySelector('[name="address_state"]')?.value,
    ]
      .filter(Boolean)
      .join(", ");
    set("rv-address", addr || "—");
    set(
      "rv-guardian",
      g.map((x) => x.name + (x.relation ? " (" + x.relation + ")" : "")).join(" · ") || "—"
    );
    const emName = form.querySelector('[name="emergency_contact_name"]')?.value;
    const emRel = form.querySelector('[name="emergency_relation"]')?.value;
    set("rv-emergency", emName ? emName + (emRel ? " — " + emRel : "") : "—");

    const rvImg = document.getElementById("rv-photo");
    if (rvImg) {
      if (photoPreview && !photoPreview.hidden && photoPreview.src) rvImg.src = photoPreview.src;
      else if (photoPreview?.dataset.existing) rvImg.src = photoPreview.dataset.existing;
    }
  }

  btnPrev?.addEventListener("click", () => setStep(current - 1));
  btnNext?.addEventListener("click", () => {
    if (!validateStep(current)) return;
    if (current === 4) fillReview();
    setStep(current + 1);
  });

  stepperItems.forEach((el) => {
    el.addEventListener("click", () => {
      const target = Number(el.dataset.step);
      if (target <= current) setStep(target);
    });
  });

  document.querySelectorAll("[data-edit-step]").forEach((btn) => {
    btn.addEventListener("click", () => setStep(Number(btn.dataset.editStep)));
  });

  document.getElementById("mw-dismiss-banner")?.addEventListener("click", () => {
    infoBanner?.classList.add("is-hidden");
    try {
      localStorage.setItem("mw_banner_dismissed", "1");
    } catch (_) {
      /* ignore */
    }
  });

  try {
    if (localStorage.getItem("mw_banner_dismissed") === "1") {
      infoBanner?.classList.add("is-hidden");
    }
  } catch (_) {
    /* ignore */
  }

  function showSuccessOverlay() {
    if (!successOverlay) return;
    successOverlay.classList.add("is-visible");
    successOverlay.setAttribute("aria-hidden", "false");
  }

  form.addEventListener("submit", (e) => {
    syncGuardiansJson();
    for (let s = 1; s <= 4; s++) {
      if (!validateStep(s)) {
        e.preventDefault();
        setStep(s);
        return;
      }
    }
    fillReview();
    showSuccessOverlay();
  });

  setStep(1);
})();
