/**
 * Gestão da Liderança — drawers, delegação, permissões
 */
(function () {
  "use strict";

  var app = document.getElementById("ld-app");
  if (!app) return;

  var cfg = {};
  try {
    cfg = JSON.parse(app.getAttribute("data-config") || "{}");
  } catch (e) {
    cfg = {};
  }

  var prefix = (document.documentElement.getAttribute("data-url-prefix") || "").replace(/\/$/, "");
  var urls = cfg.urls || {};
  var toastRoot = document.getElementById("ld-toast-root");

  function apiUrl(path) {
    return prefix + path;
  }

  function toast(msg) {
    if (!toastRoot || !msg) return;
    var el = document.createElement("div");
    el.className = "ld-toast";
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

  function openDrawer(name) {
    var overlay = document.getElementById("ld-drawer-" + name + "-overlay");
    if (!overlay) return;
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer(name) {
    var overlay = document.getElementById("ld-drawer-" + name + "-overlay");
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  document.querySelectorAll(".ld-drawer-close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      closeDrawer(btn.getAttribute("data-target"));
    });
  });

  ["member", "profile", "perms"].forEach(function (name) {
    var overlay = document.getElementById("ld-drawer-" + name + "-overlay");
    if (!overlay) return;
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closeDrawer(name);
    });
  });

  var memberForm = document.getElementById("ld-member-form");
  var memberTitle = document.getElementById("ld-drawer-member-title");

  function resetMemberForm() {
    if (!memberForm) return;
    memberForm.reset();
    var idEl = document.getElementById("ld-member-id");
    if (idEl) idEl.value = "";
    if (memberTitle) memberTitle.textContent = "Novo membro da liderança";
  }

  function fillMemberForm(data) {
    if (!memberForm || !data) return;
    Object.keys(data).forEach(function (key) {
      var el = memberForm.elements[key];
      if (!el) return;
      if (el.type === "checkbox") {
        el.checked = !!data[key];
      } else if (el.type !== "file") {
        el.value = data[key] || "";
      }
    });
    var idEl = document.getElementById("ld-member-id");
    if (idEl) idEl.value = data.id || "";
    if (data.account_email) {
      var acc = document.getElementById("ld-member-account-email");
      if (acc) acc.value = data.account_email;
    }
    if (memberTitle) memberTitle.textContent = "Editar — " + (data.full_name || "");
  }

  function openNewMember() {
    resetMemberForm();
    openDrawer("member");
  }

  document.getElementById("ld-open-new")?.addEventListener("click", openNewMember);
  document.getElementById("ld-empty-new")?.addEventListener("click", openNewMember);

  function loadMember(id, cb) {
    var tpl = urls.memberTpl || "";
    var url = tpl.replace("/0", "/" + id);
    fetch(apiUrl(url), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(cb)
      .catch(function () {
        toast("Erro ao carregar membro.");
      });
  }

  document.querySelectorAll(".ld-btn-edit").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-id");
      if (!id) return;
      loadMember(id, function (data) {
        fillMemberForm(data);
        openDrawer("member");
      });
    });
  });

  document.querySelectorAll(".ld-btn-profile").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-id");
      if (!id) return;
      var body = document.getElementById("ld-profile-body");
      if (body) body.innerHTML = '<div class="ld-skeleton"></div>';
      openDrawer("profile");
      loadMember(id, function (data) {
        if (!body) return;
        var hist = (data.delegation_history || [])
          .map(function (h) {
            return "<li>" + h.role_label + " — " + h.start + " até " + h.end + "</li>";
          })
          .join("");
        body.innerHTML =
          '<div class="flex gap-4 mb-4">' +
          (data.photo_url
            ? '<img src="' + data.photo_url + '" class="w-20 h-20 rounded-full object-cover" alt="" />'
            : '<span class="ld-avatar">' + (data.initials || "?") + "</span>") +
          "<div><h3 class=\"font-bold text-lg m-0\">" +
          (data.full_name || "") +
          '</h3><span class="ld-tag ' +
          (data.role_tag_css || "") +
          '">' +
          (data.cargo || "") +
          "</span></div></div>" +
          "<p><strong>Status:</strong> " +
          (data.status_label || "") +
          "</p>" +
          "<p><strong>E-mail:</strong> " +
          (data.email || "—") +
          "</p>" +
          "<p><strong>Telefone:</strong> " +
          (data.phone || "—") +
          "</p>" +
          "<p><strong>Unidade:</strong> " +
          (data.unit || "—") +
          "</p>" +
          "<p><strong>Área:</strong> " +
          (data.responsible_area || "—") +
          "</p>" +
          (data.bio ? "<p class=\"mt-3\">" + data.bio + "</p>" : "") +
          (hist ? "<h4 class=\"font-bold mt-4\">Histórico de cargos</h4><ul class=\"text-sm\">" + hist + "</ul>" : "");
      });
    });
  });

  if (memberForm && cfg.canEdit) {
    memberForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData(memberForm);
      if (cfg.clubeId) fd.append("clube_id", cfg.clubeId);
      fetch(apiUrl(urls.saveMember), {
        method: "POST",
        body: fd,
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, data: j };
          });
        })
        .then(function (res) {
          if (!res.ok || !res.data.ok) {
            toast(res.data.error || "Erro ao salvar.");
            return;
          }
          toast("Membro salvo com sucesso.");
          closeDrawer("member");
          window.location.reload();
        })
        .catch(function () {
          toast("Falha na comunicação com o servidor.");
        });
    });
  }

  /* Delegação */
  var delegateQ = document.getElementById("ld-delegate-q");
  var delegateAc = document.getElementById("ld-delegate-ac");
  var delegatePreview = document.getElementById("ld-delegate-preview");
  var delegateUserId = document.getElementById("ld-delegate-user-id");
  var delegateSubmit = document.getElementById("ld-delegate-submit");
  var delegateForm = document.getElementById("ld-delegate-form");
  var selectedDelegate = null;
  var debounceTimer = null;

  function renderDelegateResults(items) {
    if (!delegateAc) return;
    delegateAc.innerHTML = "";
    if (!items.length) {
      delegateAc.classList.remove("is-open");
      return;
    }
    items.forEach(function (u) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ld-ac-item";
      btn.innerHTML =
        '<span class="ld-avatar" style="width:2rem;height:2rem;font-size:0.7rem">' +
        (u.initials || "?") +
        "</span><span><strong>" +
        (u.full_name || "") +
        "</strong><br><small>" +
        (u.email || "") +
        "</small></span>";
      btn.addEventListener("click", function () {
        selectDelegateUser(u);
        delegateAc.classList.remove("is-open");
      });
      delegateAc.appendChild(btn);
    });
    delegateAc.classList.add("is-open");
  }

  function selectDelegateUser(u) {
    selectedDelegate = u;
    if (delegateUserId) delegateUserId.value = u.id;
    if (delegatePreview) {
      delegatePreview.classList.remove("is-hidden");
      var av = document.getElementById("ld-delegate-avatar");
      if (av) {
        if (u.photo_url) av.innerHTML = '<img src="' + u.photo_url + '" alt="" />';
        else av.textContent = u.initials || "?";
      }
      var nm = document.getElementById("ld-delegate-name");
      var em = document.getElementById("ld-delegate-email");
      if (nm) nm.textContent = u.full_name || "";
      if (em) em.textContent = u.email || "";
    }
    if (delegateSubmit) delegateSubmit.disabled = false;
    if (delegateQ) delegateQ.value = u.full_name || u.email || "";
  }

  function searchDelegate(q) {
    if (!urls.searchUsers || q.length < 2) {
      if (delegateAc) delegateAc.classList.remove("is-open");
      return;
    }
    fetch(apiUrl(urls.searchUsers + "?q=" + encodeURIComponent(q)), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json();
      })
      .then(renderDelegateResults)
      .catch(function () {});
  }

  if (delegateQ) {
    delegateQ.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        searchDelegate(delegateQ.value.trim());
      }, 280);
    });
  }
  document.getElementById("ld-delegate-search-btn")?.addEventListener("click", function () {
    if (delegateQ) searchDelegate(delegateQ.value.trim());
  });

  if (delegateForm && cfg.canDelegate) {
    delegateForm.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!delegateUserId || !delegateUserId.value) {
        toast("Selecione um membro na busca.");
        return;
      }
      var fd = new FormData(delegateForm);
      if (cfg.clubeId) fd.append("clube_id", cfg.clubeId);
      fetch(apiUrl(urls.delegate), {
        method: "POST",
        body: fd,
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, data: j };
          });
        })
        .then(function (res) {
          if (!res.ok || !res.data.ok) {
            toast(res.data.error || "Erro ao delegar.");
            return;
          }
          toast("Função delegada com sucesso.");
          window.location.reload();
        })
        .catch(function () {
          toast("Falha na delegação.");
        });
    });
  }

  document.querySelectorAll(".ld-btn-role").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var uid = btn.getAttribute("data-user-id");
      if (uid && delegateUserId) {
        delegateUserId.value = uid;
        if (delegateSubmit) delegateSubmit.disabled = false;
        delegateForm?.scrollIntoView({ behavior: "smooth" });
      }
      toast("Use o painel «Delegar função» para alterar o cargo.");
    });
  });

  /* Permissões */
  var permsRoot = document.getElementById("ld-perms-root");
  var permLabels = cfg.permissionLabels || {};
  var storedPerms = {};

  function renderPerms(perms) {
    if (!permsRoot) return;
    storedPerms = perms || {};
    permsRoot.innerHTML = "";
    (cfg.allowedRoles || []).forEach(function (pair) {
      var code = pair[0];
      var label = pair[1];
      var rolePerms = storedPerms[code] || {};
      var block = document.createElement("div");
      block.className = "ld-perm-role";
      block.innerHTML = "<h4>" + label + "</h4>";
      var checks = document.createElement("div");
      checks.className = "ld-perm-checks";
      Object.keys(permLabels).forEach(function (key) {
        var lbl = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.dataset.role = code;
        cb.dataset.perm = key;
        cb.checked = !!rolePerms[key];
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(permLabels[key]));
        checks.appendChild(lbl);
      });
      block.appendChild(checks);
      permsRoot.appendChild(block);
    });
  }

  document.getElementById("ld-open-permissions")?.addEventListener("click", function () {
    if (!cfg.canDelegate) return;
    fetch(apiUrl(urls.permissions), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.permissions) renderPerms(data.permissions);
        openDrawer("perms");
      })
      .catch(function () {
        toast("Erro ao carregar permissões.");
      });
  });

  document.getElementById("ld-perms-save")?.addEventListener("click", function () {
    if (!permsRoot) return;
    var out = {};
    permsRoot.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      var role = cb.dataset.role;
      var perm = cb.dataset.perm;
      if (!role || !perm) return;
      if (!out[role]) out[role] = {};
      out[role][perm] = cb.checked;
    });
    fetch(apiUrl(urls.permissions), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ permissions: out }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.ok) {
          toast("Permissões salvas.");
          closeDrawer("perms");
        } else toast(data.error || "Erro ao salvar.");
      })
      .catch(function () {
        toast("Falha ao salvar permissões.");
      });
  });
})();
