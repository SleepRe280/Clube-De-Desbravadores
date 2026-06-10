/**
 * Almoxarifado premium — abas, filtros, drawers
 */
(function () {
  "use strict";

  var app = document.getElementById("wh-app");
  if (!app) return;

  var drawerRoot = document.getElementById("wh-drawer-root");
  var drawers = {
    item: document.getElementById("wh-drawer-item"),
    edit: document.getElementById("wh-drawer-edit"),
    move: document.getElementById("wh-drawer-move"),
    hist: document.getElementById("wh-drawer-hist"),
  };
  var activeDrawer = null;
  var itemsData = [];
  var movementsData = [];

  try {
    var itemsEl = document.getElementById("wh-items-data");
    if (itemsEl && itemsEl.textContent) {
      itemsData = JSON.parse(itemsEl.textContent);
    }
  } catch (e) {
    itemsData = [];
  }

  try {
    var mvEl = document.getElementById("wh-movements-data");
    if (mvEl && mvEl.textContent) {
      movementsData = JSON.parse(mvEl.textContent);
    }
  } catch (e2) {
    movementsData = [];
  }

  /* Tabs */
  var tabs = app.querySelectorAll("[data-wh-tab]");
  var panels = app.querySelectorAll("[data-wh-panel]");

  function setTab(name) {
    tabs.forEach(function (t) {
      t.classList.toggle("is-active", t.getAttribute("data-wh-tab") === name);
    });
    panels.forEach(function (p) {
      p.classList.toggle("is-active", p.getAttribute("data-wh-panel") === name);
    });
    var url = new URL(window.location.href);
    url.searchParams.set("tab", name);
    window.history.replaceState({}, "", url);
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      setTab(tab.getAttribute("data-wh-tab"));
    });
  });

  var initialTab = app.getAttribute("data-active-tab") || "dashboard";
  setTab(initialTab);

  /* Drawer */
  function openDrawer(which) {
    if (!drawerRoot || !drawers[which]) return;
    Object.keys(drawers).forEach(function (k) {
      if (drawers[k]) drawers[k].hidden = k !== which;
    });
    activeDrawer = which;
    drawerRoot.classList.add("is-open");
    drawerRoot.setAttribute("aria-hidden", "false");
    document.body.classList.add("wh-drawer-open");
  }

  function closeDrawer() {
    if (!drawerRoot) return;
    drawerRoot.classList.remove("is-open");
    drawerRoot.setAttribute("aria-hidden", "true");
    document.body.classList.remove("wh-drawer-open");
    activeDrawer = null;
  }

  document.querySelectorAll("[data-wh-drawer-close]").forEach(function (el) {
    el.addEventListener("click", closeDrawer);
  });
  var backdrop = document.getElementById("wh-drawer-backdrop");
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawerRoot && drawerRoot.classList.contains("is-open")) {
      closeDrawer();
    }
  });

  var btnNew = document.getElementById("wh-btn-new-item");
  if (btnNew) {
    btnNew.addEventListener("click", function () {
      var form = document.getElementById("wh-form-item");
      if (form) form.reset();
      var title = document.getElementById("wh-drawer-item-title");
      if (title) title.textContent = "Novo item";
      openDrawer("item");
    });
  }

  /* Upload label */
  var photoInput = document.getElementById("wh-i-photo");
  var uploadLabel = document.getElementById("wh-upload-label");
  var uploadZone = document.getElementById("wh-upload-zone");
  if (photoInput && uploadLabel) {
    photoInput.addEventListener("change", function () {
      if (photoInput.files && photoInput.files[0]) {
        uploadLabel.textContent = photoInput.files[0].name;
      }
    });
  }
  if (uploadZone) {
    ["dragenter", "dragover"].forEach(function (ev) {
      uploadZone.addEventListener(ev, function (e) {
        e.preventDefault();
        uploadZone.classList.add("is-drag");
      });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      uploadZone.addEventListener(ev, function (e) {
        e.preventDefault();
        uploadZone.classList.remove("is-drag");
      });
    });
  }

  /* Edit / move / hist */
  var prefix = document.documentElement.getAttribute("data-url-prefix") || "";
  var clubeId = app.getAttribute("data-clube-id") || "";

  function deleteMovementFormHtml(m) {
    if (!m.can_delete) return "";
    var action = prefix + "/admin/almoxarifado/movimento/" + m.id + "/excluir";
    var clubInput = clubeId
      ? '<input type="hidden" name="clube_id" value="' + clubeId + '" />'
      : "";
    return (
      '<form method="post" action="' +
      action +
      '" class="wh-mv-delete-form" onsubmit="return confirm(\'Excluir este lançamento? O estoque será recalculado.\');">' +
      clubInput +
      '<input type="hidden" name="tab" value="items" />' +
      '<button type="submit" class="wh-mini wh-mini--del" title="Excluir lançamento">Excluir</button></form>'
    );
  }

  function itemById(id) {
    return itemsData.find(function (it) {
      return String(it.id) === String(id);
    });
  }

  app.addEventListener("click", function (e) {
    var editBtn = e.target.closest("[data-wh-edit]");
    if (editBtn) {
      var id = editBtn.getAttribute("data-wh-edit");
      var item = itemById(id);
      if (!item) return;
      var form = document.getElementById("wh-form-edit");
      if (!form) return;
      form.action = prefix + "/admin/almoxarifado/item/" + id;
      document.getElementById("wh-e-name").value = item.name || "";
      document.getElementById("wh-e-code").value = item.internal_code === "—" ? "" : item.internal_code;
      document.getElementById("wh-e-cat").value = item.category_id || 0;
      document.getElementById("wh-e-unit").value = item.unit || "un";
      document.getElementById("wh-e-min").value = item.min_stock || 0;
      document.getElementById("wh-e-loc").value = item.location === "—" ? "" : item.location;
      document.getElementById("wh-e-price").value = item.unit_price_label
        ? item.unit_price_label.replace("R$", "").trim()
        : "";
      document.getElementById("wh-e-notes").value = item.notes || "";
      openDrawer("edit");
      return;
    }

    var moveBtn = e.target.closest("[data-wh-move]");
    if (moveBtn) {
      var mid = moveBtn.getAttribute("data-id");
      var dir = moveBtn.getAttribute("data-wh-move");
      var mname = moveBtn.getAttribute("data-name") || "";
      var mform = document.getElementById("wh-form-move");
      if (!mform) return;
      mform.action = prefix + "/admin/almoxarifado/item/" + mid + "/movimento";
      document.getElementById("wh-move-direction").value = dir === "out" ? "out" : "in";
      document.getElementById("wh-move-sub").textContent = mname;
      var mtitle = document.getElementById("wh-drawer-move-title");
      var msubmit = document.getElementById("wh-move-submit");
      if (mtitle) mtitle.textContent = dir === "out" ? "Saída de estoque" : "Entrada de estoque";
      if (msubmit) msubmit.textContent = dir === "out" ? "Registrar saída" : "Registrar entrada";
      document.getElementById("wh-m-qty").value = 1;
      document.getElementById("wh-m-notes").value = "";
      openDrawer("move");
      return;
    }

    var histBtn = e.target.closest("[data-wh-hist]");
    if (histBtn) {
      var hid = histBtn.getAttribute("data-wh-hist");
      var hit = itemById(hid);
      document.getElementById("wh-hist-sub").textContent = hit ? hit.name : "";
      var tbody = document.querySelector("#wh-hist-item-table tbody");
      var empty = document.getElementById("wh-hist-empty");
      if (!tbody) return;
      tbody.innerHTML = "";
      var rows = movementsData.filter(function (m) {
        return String(m.item_id) === String(hid);
      });
      rows.forEach(function (m) {
        var tr = document.createElement("tr");
        var dirClass = m.direction === "in" ? "wh-dir-in" : "wh-dir-out";
        tr.innerHTML =
          "<td>" +
          (m.created_label || "") +
          "</td><td class=\"" +
          dirClass +
          "\">" +
          (m.direction_label || "") +
          "</td><td>" +
          m.quantity +
          "</td><td>" +
          (m.balance_after != null ? m.balance_after : "—") +
          "</td><td>" +
          (m.notes || "—") +
          '</td><td class="wh-table__actions">' +
          deleteMovementFormHtml(m) +
          "</td>";
        tbody.appendChild(tr);
      });
      if (empty) {
        empty.classList.toggle("is-hidden", rows.length > 0);
      }
      openDrawer("hist");
    }
  });

  /* Filtros itens */
  var searchInput = document.getElementById("wh-search");
  var filterCat = document.getElementById("wh-filter-cat");
  var filterStatus = document.getElementById("wh-filter-status");
  var sortSelect = document.getElementById("wh-sort");
  var grid = document.getElementById("wh-items-grid");
  var noResults = document.getElementById("wh-no-results");
  var loading = document.getElementById("wh-grid-loading");

  function applyFilters() {
    if (!grid) return;
    var q = (searchInput && searchInput.value || "").toLowerCase().trim();
    var cat = filterCat && filterCat.value || "";
    var st = filterStatus && filterStatus.value || "";
    var cards = Array.prototype.slice.call(grid.querySelectorAll("[data-wh-item]"));

    cards.forEach(function (card) {
      var name = card.getAttribute("data-name") || "";
      var code = card.getAttribute("data-code") || "";
      var category = card.getAttribute("data-category") || "";
      var status = card.getAttribute("data-status") || "";
      var match =
        (!q || name.indexOf(q) >= 0 || code.indexOf(q) >= 0 || category.indexOf(q) >= 0) &&
        (!cat || category === cat.toLowerCase()) &&
        (!st || status === st);
      card.classList.toggle("is-hidden", !match);
    });

    var sort = sortSelect && sortSelect.value || "name";
    cards.sort(function (a, b) {
      if (sort === "qty-asc") return (+a.getAttribute("data-qty") || 0) - (+b.getAttribute("data-qty") || 0);
      if (sort === "qty-desc") return (+b.getAttribute("data-qty") || 0) - (+a.getAttribute("data-qty") || 0);
      var na = a.getAttribute("data-name") || "";
      var nb = b.getAttribute("data-name") || "";
      if (sort === "name-desc") return nb.localeCompare(na);
      return na.localeCompare(nb);
    });
    cards.forEach(function (c) {
      grid.appendChild(c);
    });

    var visible = cards.filter(function (c) {
      return !c.classList.contains("is-hidden");
    }).length;
    if (noResults) {
      noResults.classList.toggle("is-hidden", visible > 0 || cards.length === 0);
    }
  }

  if (loading && grid) {
    loading.classList.add("is-visible");
    setTimeout(function () {
      loading.classList.remove("is-visible");
    }, 280);
  }

  [searchInput, filterCat, filterStatus, sortSelect].forEach(function (el) {
    if (el) el.addEventListener("input", applyFilters);
    if (el && el.tagName === "SELECT") el.addEventListener("change", applyFilters);
  });
  applyFilters();

  /* Histórico search */
  var histSearch = document.getElementById("wh-hist-search");
  if (histSearch) {
    histSearch.addEventListener("input", function () {
      var q = histSearch.value.toLowerCase().trim();
      document.querySelectorAll("[data-hist-row]").forEach(function (tr) {
        var text = tr.getAttribute("data-text") || "";
        tr.style.display = !q || text.indexOf(q) >= 0 ? "" : "none";
      });
    });
  }
})();
