/**
 * Comunicados premium — drawer, preview, hero carousel, detalhes
 */
(function () {
  "use strict";

  var root = document.getElementById("cm-app");
  if (!root) return;

  var drawerRoot = document.getElementById("cm-drawer-root");
  var drawerForm = document.getElementById("cm-drawer-form");
  var openBtn = document.getElementById("cm-btn-new");
  var closeBtns = document.querySelectorAll("[data-cm-drawer-close]");
  var previewTitle = document.getElementById("cm-preview-title");
  var previewBody = document.getElementById("cm-preview-body");
  var previewTag = document.getElementById("cm-preview-tag");
  var previewImg = document.getElementById("cm-preview-img");
  var defaultHeroImg = root.getAttribute("data-default-img") || "";

  function openDrawer() {
    if (!drawerRoot) return;
    drawerRoot.classList.add("is-open");
    drawerRoot.setAttribute("aria-hidden", "false");
    document.body.classList.add("cm-drawer-open");
  }

  function closeDrawer() {
    if (!drawerRoot) return;
    drawerRoot.classList.remove("is-open");
    drawerRoot.setAttribute("aria-hidden", "true");
    document.body.classList.remove("cm-drawer-open");
  }

  if (openBtn) openBtn.addEventListener("click", openDrawer);
  closeBtns.forEach(function (btn) {
    btn.addEventListener("click", closeDrawer);
  });
  var backdrop = document.getElementById("cm-drawer-backdrop");
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  if (root.getAttribute("data-open-drawer") === "1") {
    openDrawer();
  }

  function syncPreview() {
    if (!drawerForm) return;
    var title = drawerForm.querySelector('[name="title"]');
    var body = drawerForm.querySelector('[name="body"]');
    var cat = drawerForm.querySelector('[name="category"]:checked');
    var banner = drawerForm.querySelector('[name="image"], [name="banner"]');
    if (previewTitle && title) previewTitle.textContent = title.value.trim() || "Título do comunicado";
    if (previewBody && body) {
      var t = body.value.trim();
      previewBody.textContent = t ? t.slice(0, 120) + (t.length > 120 ? "…" : "") : "Uma mensagem acolhedora para as famílias…";
    }
    if (previewTag && cat) {
      var lbl = cat.closest(".cm-cat-opt");
      previewTag.textContent = lbl ? lbl.textContent.trim() : "Aviso";
    }
    if (previewImg && banner && banner.files && banner.files[0]) {
      var reader = new FileReader();
      reader.onload = function (e) {
        previewImg.style.backgroundImage = "url(" + e.target.result + ")";
      };
      reader.readAsDataURL(banner.files[0]);
    }
  }

  if (drawerForm) {
    drawerForm.addEventListener("input", syncPreview);
    drawerForm.addEventListener("change", syncPreview);
    syncPreview();
  }

  /* Hero carousel */
  var heroItems = [];
  try {
    var dataEl = document.getElementById("cm-hero-data");
    if (dataEl) heroItems = JSON.parse(dataEl.textContent || "[]");
  } catch (e) {
    heroItems = [];
  }

  var heroBg = document.getElementById("cm-hero-bg");
  var heroTitle = document.getElementById("cm-hero-title");
  var heroDesc = document.getElementById("cm-hero-desc");
  var heroDate = document.getElementById("cm-hero-date");
  var heroLoc = document.getElementById("cm-hero-location");
  var heroLink = document.getElementById("cm-hero-detail");
  var dotsWrap = document.getElementById("cm-hero-dots");
  var heroIdx = 0;

  function showHero(i) {
    if (!heroItems.length) return;
    heroIdx = (i + heroItems.length) % heroItems.length;
    var item = heroItems[heroIdx];
    if (heroBg) heroBg.style.backgroundImage = "url(" + (item.image_url || defaultHeroImg) + ")";
    if (heroTitle) heroTitle.textContent = item.title || "";
    if (heroDesc) heroDesc.textContent = item.excerpt || "";
    if (heroDate) heroDate.textContent = item.event_date_label || "";
    if (heroLoc) heroLoc.textContent = item.location || "";
    if (heroLink) heroLink.setAttribute("data-cm-detail", String(item.id || ""));
    if (dotsWrap) {
      dotsWrap.querySelectorAll(".cm-hero__dot").forEach(function (dot, j) {
        dot.classList.toggle("is-active", j === heroIdx);
      });
    }
  }

  if (heroItems.length > 1 && dotsWrap) {
    heroItems.forEach(function (_, i) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.className = "cm-hero__dot" + (i === 0 ? " is-active" : "");
      dot.setAttribute("aria-label", "Destaque " + (i + 1));
      dot.addEventListener("click", function () {
        showHero(i);
      });
      dotsWrap.appendChild(dot);
    });
    setInterval(function () {
      showHero(heroIdx + 1);
    }, 8000);
  }

  /* Detail modal */
  var detailModal = document.getElementById("cm-detail-modal");
  var detailTitle = document.getElementById("cm-detail-title");
  var detailBody = document.getElementById("cm-detail-body");
  var detailTag = document.getElementById("cm-detail-tag");
  var detailPanel = detailModal ? detailModal.querySelector(".cm-detail-panel") : null;

  function openDetail(id) {
    var card = root.querySelector('.cm-card[data-id="' + id + '"]');
    if (!card || !detailModal) return;
    if (detailTitle) detailTitle.textContent = card.getAttribute("data-title") || "";
    if (detailBody) detailBody.textContent = card.getAttribute("data-body") || "";
    if (detailTag) {
      var catEl = card.querySelector(".cm-tag");
      detailTag.textContent = catEl ? catEl.textContent.trim() : "Comunicado";
      if (catEl) {
        detailTag.className = catEl.className;
      }
    }
    detailModal.classList.add("is-open");
    detailModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("cm-detail-open");
    var closeBtn = detailModal.querySelector("[data-cm-detail-close]");
    if (closeBtn) closeBtn.focus();
  }

  function closeDetail() {
    if (!detailModal) return;
    detailModal.classList.remove("is-open");
    detailModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("cm-detail-open");
  }

  if (detailModal) {
    detailModal.addEventListener("click", function (e) {
      if (e.target === detailModal) closeDetail();
    });
    if (detailPanel) {
      detailPanel.addEventListener("click", function (e) {
        e.stopPropagation();
      });
    }
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && detailModal && detailModal.classList.contains("is-open")) {
      closeDetail();
    }
  });

  root.addEventListener("click", function (e) {
    var detailBtn = e.target.closest("[data-cm-detail]");
    if (detailBtn) {
      e.preventDefault();
      openDetail(detailBtn.getAttribute("data-cm-detail"));
    }
    if (e.target.closest("[data-cm-detail-close]")) {
      e.preventDefault();
      closeDetail();
    }
  });

  if (heroLink) {
    heroLink.addEventListener("click", function (e) {
      e.preventDefault();
      var id = heroLink.getAttribute("data-cm-detail");
      if (id) openDetail(id);
    });
  }

  /* Favoritos (local) */
  var bookmarkKey = "cm-bookmarks";
  function loadBookmarks() {
    try {
      return JSON.parse(localStorage.getItem(bookmarkKey) || "[]");
    } catch (e) {
      return [];
    }
  }
  function saveBookmarks(ids) {
    try {
      localStorage.setItem(bookmarkKey, JSON.stringify(ids));
    } catch (e) {
      /* ignore */
    }
  }
  function syncBookmarks() {
    var ids = loadBookmarks();
    root.querySelectorAll("[data-cm-bookmark]").forEach(function (btn) {
      var id = btn.getAttribute("data-cm-bookmark");
      var on = ids.indexOf(id) >= 0;
      btn.classList.toggle("is-saved", on);
      btn.textContent = on ? "★" : "☆";
    });
  }
  root.addEventListener("click", function (e) {
    var bm = e.target.closest("[data-cm-bookmark]");
    if (!bm) return;
    e.preventDefault();
    e.stopPropagation();
    var id = bm.getAttribute("data-cm-bookmark");
    var ids = loadBookmarks();
    var i = ids.indexOf(id);
    if (i >= 0) ids.splice(i, 1);
    else ids.push(id);
    saveBookmarks(ids);
    syncBookmarks();
  });
  syncBookmarks();

  /* Load more (client-side show hidden) */
  var loadBtn = document.getElementById("cm-load-more");
  if (loadBtn) {
    loadBtn.addEventListener("click", function () {
      root.querySelectorAll(".cm-card.is-hidden").forEach(function (el) {
        el.classList.remove("is-hidden");
      });
      loadBtn.style.display = "none";
    });
  }
})();
