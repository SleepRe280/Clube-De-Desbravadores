/**
 * Responsáveis e vínculos — autocomplete, preview, busca em tempo real
 */
(function () {
  "use strict";

  var app = document.getElementById("pr-app");
  if (!app) return;

  var cfg = {};
  try {
    cfg = JSON.parse(app.getAttribute("data-config") || "{}");
  } catch (e) {
    cfg = {};
  }

  var prefix = (document.documentElement.getAttribute("data-url-prefix") || "").replace(/\/$/, "");

  function apiUrl(path) {
    return prefix + path;
  }

  var toastRoot = document.getElementById("pr-toast-root");

  function toast(msg) {
    if (!toastRoot || !msg) return;
    var el = document.createElement("div");
    el.className = "pr-toast";
    el.setAttribute("role", "status");
    el.textContent = msg;
    toastRoot.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transition = "opacity 0.3s";
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 300);
    }, 4200);
  }

  if (cfg.flashSuccess) toast(cfg.flashSuccess);

  var linkForm = document.getElementById("pr-link-form");
  var parentInput = document.getElementById("pr-parent-search");
  var memberInput = document.getElementById("pr-member-search");
  var parentHidden = document.getElementById("pr-parent-id");
  var memberHidden = document.getElementById("pr-member-id");
  var parentList = document.getElementById("pr-parent-ac");
  var memberList = document.getElementById("pr-member-ac");
  var parentPreview = document.getElementById("pr-parent-preview");
  var memberPreview = document.getElementById("pr-member-preview");
  var linkBtn = document.getElementById("pr-link-submit");
  var suggestionsEl = document.getElementById("pr-suggestions");

  var selectedParent = null;
  var selectedMember = null;
  var debounceTimer = null;

  function badgeHtml(status, text) {
    var cls = "pr-badge--slate";
    if (status === "ativo" || status === "vinculado") cls = "pr-badge--green";
    else if (status === "pendente") cls = "pr-badge--amber";
    else if (status === "sem_responsavel") cls = "pr-badge--red";
    return '<span class="pr-badge ' + cls + '">' + text + "</span>";
  }

  function fixPersonCard(el, person, type) {
    if (!el) return;
    if (!person) {
      el.classList.remove("is-selected");
      el.innerHTML =
        '<p style="margin:0;font-size:0.82rem;color:#64748b">Selecione ' +
        (type === "parent" ? "um responsável" : "um desbravador") +
        " na busca acima.</p>";
      return;
    }
    el.classList.add("is-selected");
    var metaParts = [];
    if (type === "parent") {
      if (person.email) metaParts.push(person.email);
      if (person.n_children != null) {
        metaParts.push(
          badgeHtml(
            "vinculado",
            person.n_children + " filho" + (person.n_children === 1 ? "" : "s")
          )
        );
      }
      metaParts.push(
        badgeHtml(person.status, person.status === "ativo" ? "Ativo" : "Pendente")
      );
    } else {
      var info = [];
      if (person.unit) info.push(person.unit);
      if (person.age != null) info.push(person.age + " anos");
      if (info.length) metaParts.push(info.join(" · "));
      metaParts.push(badgeHtml("sem_responsavel", "Sem responsável"));
    }
    var av = document.createElement("div");
    av.className = "pr-avatar";
    av.textContent = person.initials || "?";
    var body = document.createElement("div");
    body.className = "pr-person-meta";
    body.innerHTML =
      '<strong style="display:block;font-weight:700;color:#0d1b3e;font-size:0.9rem">' +
      (person.name || person.full_name || "—") +
      '</strong><span style="margin-top:0.2rem;font-size:0.78rem;color:#64748b;display:flex;flex-wrap:wrap;gap:0.25rem;align-items:center">' +
      metaParts.join(" ") +
      "</span>";
    el.innerHTML = "";
    el.appendChild(av);
    el.appendChild(body);
  }

  function updateLinkBtn() {
    if (!linkBtn) return;
    linkBtn.disabled = !(selectedParent && selectedMember);
  }

  function closeLists() {
    if (parentList) parentList.classList.remove("is-open");
    if (memberList) memberList.classList.remove("is-open");
  }

  function renderAcList(listEl, items, onPick) {
    if (!listEl) return;
    listEl.innerHTML = "";
    if (!items.length) {
      listEl.classList.remove("is-open");
      return;
    }
    items.forEach(function (item) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pr-ac-item";
      var sub = item.email || item.unit || "";
      btn.innerHTML =
        '<span class="pr-avatar" style="width:2rem;height:2rem;font-size:0.7rem">' +
        (item.initials || "?") +
        "</span><span><strong>" +
        (item.name || item.full_name) +
        "</strong><br><span style='font-size:0.75rem;color:#64748b'>" +
        sub +
        "</span></span>";
      btn.addEventListener("click", function () {
        onPick(item);
        listEl.classList.remove("is-open");
      });
      listEl.appendChild(btn);
    });
    listEl.classList.add("is-open");
  }

  function fetchJson(url) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(function (r) {
      return r.json();
    });
  }

  function searchParents(q) {
    return fetchJson(
      apiUrl("/admin/responsaveis/api/search-parents?q=" + encodeURIComponent(q || ""))
    );
  }

  function searchMembers(q) {
    return fetchJson(
      apiUrl("/admin/responsaveis/api/search-members?q=" + encodeURIComponent(q || ""))
    );
  }

  function loadSuggestions(memberId) {
    if (!suggestionsEl || !memberId) {
      if (suggestionsEl) suggestionsEl.innerHTML = "";
      return;
    }
    fetchJson(apiUrl("/admin/responsaveis/api/suggest/" + memberId)).then(function (items) {
      suggestionsEl.innerHTML = "";
      if (!items.length) return;
      var label = document.createElement("span");
      label.textContent = "Sugestões da ficha: ";
      suggestionsEl.appendChild(label);
      items.forEach(function (s) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = (s.name || "") + " (" + (s.relation || "responsável") + ")";
        b.addEventListener("click", function () {
          selectedParent = s;
          if (parentHidden) parentHidden.value = s.id;
          if (parentInput) parentInput.value = s.name + " — " + s.email;
          fixPersonCard(parentPreview, s, "parent");
          updateLinkBtn();
        });
        suggestionsEl.appendChild(b);
      });
    });
  }

  if (parentInput) {
    parentInput.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        searchParents(parentInput.value).then(function (items) {
          renderAcList(parentList, items, function (item) {
            selectedParent = item;
            if (parentHidden) parentHidden.value = item.id;
            parentInput.value = item.name + " — " + item.email;
            fixPersonCard(parentPreview, item, "parent");
            updateLinkBtn();
          });
        });
      }, 220);
    });
    parentInput.addEventListener("focus", function () {
      searchParents(parentInput.value).then(function (items) {
        renderAcList(parentList, items, function (item) {
          selectedParent = item;
          if (parentHidden) parentHidden.value = item.id;
          parentInput.value = item.name + " — " + item.email;
          fixPersonCard(parentPreview, item, "parent");
          updateLinkBtn();
        });
      });
    });
  }

  if (memberInput) {
    memberInput.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        searchMembers(memberInput.value).then(function (items) {
          renderAcList(memberList, items, function (item) {
            selectedMember = item;
            if (memberHidden) memberHidden.value = item.id;
            memberInput.value = item.full_name + (item.unit ? " — " + item.unit : "");
            fixPersonCard(memberPreview, item, "member");
            updateLinkBtn();
            loadSuggestions(item.id);
          });
        });
      }, 220);
    });
    memberInput.addEventListener("focus", function () {
      searchMembers(memberInput.value).then(function (items) {
        renderAcList(memberList, items, function (item) {
          selectedMember = item;
          if (memberHidden) memberHidden.value = item.id;
          memberInput.value = item.full_name + (item.unit ? " — " + item.unit : "");
          fixPersonCard(memberPreview, item, "member");
          updateLinkBtn();
          loadSuggestions(item.id);
        });
      });
    });
  }

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".pr-search-wrap")) closeLists();
  });

  document.querySelectorAll(".pr-unlinked-card").forEach(function (card) {
    card.addEventListener("click", function () {
      var id = card.getAttribute("data-member-id");
      var name = card.getAttribute("data-member-name") || "";
      var unit = card.getAttribute("data-member-unit") || "";
      var age = card.getAttribute("data-member-age");
      var initials = card.getAttribute("data-member-initials") || "?";
      if (!id || !memberInput) return;
      selectedMember = {
        id: parseInt(id, 10),
        full_name: name,
        unit: unit,
        age: age ? parseInt(age, 10) : null,
        initials: initials,
      };
      if (memberHidden) memberHidden.value = id;
      memberInput.value = name + (unit ? " — " + unit : "");
      fixPersonCard(memberPreview, selectedMember, "member");
      updateLinkBtn();
      loadSuggestions(id);
      if (linkForm) linkForm.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  if (linkForm && linkBtn) {
    linkForm.addEventListener("submit", function () {
      if (!selectedParent || !selectedMember) return;
      linkBtn.classList.add("is-loading");
      linkBtn.textContent = "Vinculando…";
    });
  }

  var tableSearch = document.getElementById("pr-table-search");
  var tableBody = document.getElementById("pr-table-body");
  if (tableSearch && tableBody) {
    tableSearch.addEventListener("input", function () {
      var q = tableSearch.value.trim().toLowerCase();
      tableBody.querySelectorAll("tr[data-search]").forEach(function (row) {
        var hay = (row.getAttribute("data-search") || "").toLowerCase();
        row.hidden = q.length > 0 && hay.indexOf(q) === -1;
      });
    });
  }

  updateLinkBtn();
})();
