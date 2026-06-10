/**
 * Gestão de especialidades — modal catálogo e toggle AJAX de requisitos
 */
(function () {
  const modal = document.getElementById("sp-modal-catalog");
  const btnNew = document.getElementById("sp-btn-new-specialty");

  if (btnNew && modal) {
    btnNew.addEventListener("click", () => {
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
    });
    modal.querySelectorAll("[data-sp-close-modal]").forEach((el) => {
      el.addEventListener("click", () => {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
      });
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
      }
    });
  }

  const iconInput = document.getElementById("sp-icon-photo");
  const iconPreview = document.getElementById("sp-icon-preview");
  if (iconInput && iconPreview) {
    iconInput.addEventListener("change", () => {
      const file = iconInput.files?.[0];
      if (!file) {
        iconPreview.hidden = true;
        iconPreview.innerHTML = "";
        return;
      }
      const url = URL.createObjectURL(file);
      iconPreview.innerHTML = `<img src="${url}" alt="Pré-visualização" />`;
      iconPreview.hidden = false;
    });
  }

  document.querySelectorAll("[data-sp-req-toggle]").forEach((checkbox) => {
    checkbox.addEventListener("change", async function () {
      const enrollmentId = this.dataset.enrollment;
      const reqId = this.dataset.req;
      const form = this.closest("form");
      if (!form || !enrollmentId || !reqId) return;

      const csrf = form.querySelector('input[name="csrf_token"]')?.value;
      const body = new FormData();
      if (csrf) body.append("csrf_token", csrf);
      body.append("requirement_id", reqId);
      body.append("completed", this.checked ? "1" : "0");

      const action = form.getAttribute("action");
      try {
        const res = await fetch(action, {
          method: "POST",
          body,
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        const data = await res.json();
        if (data.ok) {
          const bar = document.getElementById("sp-main-progress");
          if (bar && data.summary) {
            bar.style.width = data.summary.progress_percent + "%";
          }
          const pctEl = form.closest("[style*='margin-bottom']")?.querySelector("span[style*='color:#1d4ed8']");
          if (pctEl && data.progress_percent != null) {
            pctEl.textContent = data.progress_percent + "%";
          }
          const innerBar = form.previousElementSibling?.querySelector?.("span");
          if (innerBar && data.progress_percent != null) {
            innerBar.style.width = data.progress_percent + "%";
          }
        }
      } catch (err) {
        form.submit();
      }
    });
  });
})();
