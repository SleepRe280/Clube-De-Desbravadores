/**
 * Portal Família — Álbum de Especialidades
 */
(function () {
  "use strict";

  var root = document.getElementById("ps-app");
  if (!root) return;

  var cardsData = [];
  try {
    var dataEl = document.getElementById("ps-cards-data");
    if (dataEl) cardsData = JSON.parse(dataEl.textContent || "[]");
  } catch (e) {
    cardsData = [];
  }

  var cardsById = {};
  cardsData.forEach(function (c) {
    cardsById[String(c.id)] = c;
  });

  var filterBtns = root.querySelectorAll(".ps-filter");
  var sections = root.querySelectorAll(".ps-section");
  var cardEls = root.querySelectorAll(".ps-card");
  var detail = document.getElementById("ps-detail");
  var detailBackdrop = detail && detail.querySelector(".ps-detail__backdrop");
  var detailClose = detail && detail.querySelector(".ps-detail__close");
  var activeFilter = "todas";

  function esc(text) {
    var d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  function setFilter(slug) {
    activeFilter = slug;
    filterBtns.forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.category === slug);
    });

    cardEls.forEach(function (el) {
      var cat = el.dataset.category || "";
      var match = slug === "todas" || cat === slug;
      el.classList.toggle("is-hidden", !match);
    });

    sections.forEach(function (sec) {
      var secSlug = sec.dataset.category || "";
      if (slug === "todas") {
        var visible = sec.querySelectorAll(".ps-card:not(.is-hidden)").length;
        sec.classList.toggle("is-hidden", visible === 0);
      } else {
        sec.classList.toggle("is-hidden", secSlug !== slug);
      }
    });
  }

  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setFilter(btn.dataset.category || "todas");
    });
  });

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "—";
      return d.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch (e) {
      return "—";
    }
  }

  function statusLabel(card) {
    if (card.status_label) return card.status_label;
    if (card.status === "concluida") return "Concluída";
    if (card.status === "em_andamento") return "Em andamento";
    return "Bloqueada";
  }

  function statusClass(status) {
    if (status === "concluida") return "ps-detail__status--done";
    if (status === "em_andamento") return "ps-detail__status--progress";
    return "ps-detail__status--locked";
  }

  function emblemHtml(card, size) {
    size = size || "card";
    var cls = size === "detail" ? "ps-detail__emblem" : "ps-card__emblem";
    var hexCls = size === "detail" ? "ps-detail__emblem-hex" : "ps-card__emblem-hex";
    var locked = card.locked || card.status === "bloqueada";
    var gray = locked ? ' style="filter:grayscale(1);opacity:0.45"' : "";
    if (card.icon_url) {
      return (
        '<div class="' +
        cls +
        '"><img src="' +
        card.icon_url +
        '" alt=""' +
        gray +
        " /></div>"
      );
    }
    var bg = card.color_hex || "#3b82f6";
    return (
      '<div class="' +
      cls +
      '"><span class="' +
      hexCls +
      '" style="background:' +
      bg +
      '18"' +
      gray +
      ">" +
      (card.icon_emoji || "🏅") +
      "</span></div>"
    );
  }

  function openDetail(cardId) {
    var card = cardsById[String(cardId)];
    if (!card || !detail) return;

    var body = detail.querySelector(".ps-detail__body");
    if (!body) return;

    var reqsHtml = "";
    if (card.requirements && card.requirements.length) {
      reqsHtml =
        '<div class="ps-detail__section"><h4>Requisitos</h4><ul class="ps-detail__reqs">' +
        card.requirements
          .map(function (r) {
            var done = r.completed;
            return (
              '<li class="ps-detail__req">' +
              '<span class="ps-detail__req-check ' +
              (done ? "ps-detail__req-check--done" : "ps-detail__req-check--pending") +
              '">' +
              (done ? "✓" : "") +
              "</span>" +
              "<span>" +
              esc(r.description) +
              "</span></li>"
            );
          })
          .join("") +
        "</ul></div>";
    } else if (card.requirements_count > 0 && card.locked) {
      reqsHtml =
        '<div class="ps-detail__section"><h4>Requisitos</h4>' +
        '<p class="ps-detail__desc">' +
        card.requirements_count +
        " requisitos serão liberados quando a diretoria iniciar esta especialidade.</p></div>";
    }

    var historyHtml = "";
    if (card.history && card.history.length) {
      historyHtml =
        '<div class="ps-detail__section"><h4>Histórico</h4><ul class="ps-detail__history">' +
        card.history
          .map(function (h) {
            return (
              "<li><strong>" +
              esc(h.label) +
              "</strong>" +
              esc(formatDate(h.date)) +
              "</li>"
            );
          })
          .join("") +
        "</ul></div>";
    }

    var metaRows = "";
    if (card.difficulty_label) {
      metaRows +=
        '<div class="ps-detail__meta-row"><dt>Dificuldade</dt><dd>' +
        esc(card.difficulty_label) +
        "</dd></div>";
    }
    if (card.points) {
      metaRows +=
        '<div class="ps-detail__meta-row"><dt>Pontos</dt><dd>' +
        esc(card.points) +
        "</dd></div>";
    }
    if (card.completed_at) {
      metaRows +=
        '<div class="ps-detail__meta-row"><dt>Conclusão</dt><dd>' +
        esc(formatDate(card.completed_at)) +
        "</dd></div>";
    }
    if (card.approved_by) {
      metaRows +=
        '<div class="ps-detail__meta-row"><dt>Avaliador</dt><dd>' +
        esc(card.approved_by) +
        "</dd></div>";
    }

    var progressHtml = "";
    if (card.status === "em_andamento" && !card.locked) {
      progressHtml =
        '<div class="ps-detail__progress-mini"><div class="ps-detail__progress-mini-fill" style="width:' +
        (card.progress || 0) +
        '%"></div></div>' +
        '<p class="ps-detail__desc" style="margin-top:0.35rem;font-size:0.75rem;font-weight:700;color:#d97706">' +
        (card.progress || 0) +
        "% concluído</p>";
    }

    body.innerHTML =
      '<div class="ps-detail__hero">' +
      emblemHtml(card, "detail") +
      '<h3 class="ps-detail__title" id="ps-detail-title">' +
      esc(card.name) +
      "</h3>" +
      '<p class="ps-detail__category">' +
      esc(card.category) +
      "</p>" +
      '<span class="ps-detail__status ' +
      statusClass(card.status) +
      '">' +
      statusLabel(card) +
      "</span>" +
      progressHtml +
      "</div>" +
      (card.description
        ? '<div class="ps-detail__section"><h4>Sobre</h4><p class="ps-detail__desc">' +
          esc(card.description) +
          "</p></div>"
        : "") +
      (metaRows
        ? '<div class="ps-detail__section"><h4>Informações</h4><dl class="ps-detail__meta">' +
          metaRows +
          "</dl></div>"
        : "") +
      reqsHtml +
      historyHtml;

    detail.classList.add("is-open");
    detail.setAttribute("aria-hidden", "false");
    document.body.classList.add("ps-detail-open");
  }

  function closeDetail() {
    if (!detail) return;
    detail.classList.remove("is-open");
    detail.setAttribute("aria-hidden", "true");
    document.body.classList.remove("ps-detail-open");
  }

  cardEls.forEach(function (el) {
    el.addEventListener("click", function () {
      openDetail(el.dataset.id);
    });
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openDetail(el.dataset.id);
      }
    });
  });

  if (detailClose) detailClose.addEventListener("click", closeDetail);
  if (detailBackdrop) detailBackdrop.addEventListener("click", closeDetail);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDetail();
  });

  var ringFill = root.querySelector(".ps-ring__fill");
  if (ringFill) {
    var pct = parseFloat(ringFill.dataset.percent || "0");
    var circumference = 2 * Math.PI * 42;
    ringFill.style.strokeDasharray = String(circumference);
    ringFill.style.strokeDashoffset = String(circumference * (1 - pct / 100));
  }

  var barFill = root.querySelector(".ps-hero__bar-fill");
  if (barFill) {
    var barPct = barFill.dataset.percent || "0";
    requestAnimationFrame(function () {
      barFill.style.width = barPct + "%";
    });
  }
})();
