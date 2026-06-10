/**
 * Galeria Oficial — interações premium
 */
(function () {
  "use strict";

  var app = document.getElementById("gl-app");
  if (!app) return;

  var canManage = app.getAttribute("data-can-manage") === "1";
  var prefix = app.getAttribute("data-prefix") || "";
  var apiBootstrap = app.getAttribute("data-api-bootstrap");
  var apiUpload = app.getAttribute("data-api-upload");
  var apiAlbums = app.getAttribute("data-api-albums");

  var state = { photos: [], albums: [], lightbox: [], lbIndex: 0, pendingFiles: [] };
  var heroSwiper = null;

  function pfx(path) {
    if (!prefix) return path;
    return prefix.replace(/\/$/, "") + path;
  }

  function loadBootstrap() {
    try {
      var el = document.getElementById("gl-bootstrap");
      if (el) return JSON.parse(el.textContent || "{}");
    } catch (e) {}
    return {};
  }

  function apiUrl(base, id, suffix) {
    var u = base;
    if (id != null) u = u.replace(/\/albums$/, "/albums/" + id) + (suffix || "");
    return pfx(u);
  }

  function renderHero(slides) {
    var wrap = document.getElementById("gl-hero-slides");
    if (!wrap) return;
    wrap.innerHTML = "";
    (slides || []).forEach(function (s) {
      var slide = document.createElement("div");
      slide.className = "swiper-slide gl-hero-slide";
      slide.style.backgroundImage = "url('" + (s.cover_url || "") + "')";
      slide.innerHTML =
        '<div class="gl-hero-slide__body">' +
        '<span class="gl-hero-badge">' + (s.badge || "Destaque") + "</span>" +
        "<h3>" + escapeHtml(s.title) + "</h3>" +
        "<p>" + escapeHtml(s.subtitle || s.description || "") + "</p>" +
        '<div class="gl-hero-meta">' +
        "<span>📷 " + (s.photo_count || 0) + " fotos</span>" +
        "<span>🕐 " + escapeHtml(s.updated_ago || "") + "</span>" +
        "<span>👤 " + escapeHtml(s.responsible || "") + "</span>" +
        "</div>" +
        '<button type="button" class="gl-hero-cta" data-album-id="' +
        s.id +
        '">Ver álbum →</button></div>';
      wrap.appendChild(slide);
    });
    if (typeof Swiper !== "undefined") {
      if (heroSwiper) heroSwiper.destroy(true, true);
      heroSwiper = new Swiper("#gl-hero-swiper", {
        loop: (slides || []).length > 1,
        autoplay: { delay: 6000, disableOnInteraction: false },
        pagination: { el: ".gl-hero-pagination", clickable: true },
        navigation: {
          nextEl: ".gl-hero-nav--next",
          prevEl: ".gl-hero-nav--prev",
        },
        effect: "fade",
        fadeEffect: { crossFade: true },
      });
    }
    wrap.querySelectorAll("[data-album-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openAlbumLightbox(parseInt(btn.getAttribute("data-album-id"), 10));
      });
    });
  }

  function renderAlbums(albums) {
    var el = document.getElementById("gl-albums");
    if (!el) return;
    state.albums = albums || [];
    el.innerHTML = "";
    state.albums.forEach(function (a) {
      var card = document.createElement("article");
      card.className = "gl-album-card";
      card.innerHTML =
        '<div class="gl-album-card__img" style="background-image:url(\'' +
        (a.cover_url || "") +
        "')\">" +
        '<span class="gl-album-card__badge">' +
        (a.photo_count || 0) +
        " fotos</span>" +
        (canManage
          ? '<button type="button" class="gl-album-card__menu" aria-label="Ações">⋮</button>'
          : "") +
        "</div>" +
        '<div class="gl-album-card__body"><h3>' +
        escapeHtml(a.title) +
        "</h3>" +
        '<p class="gl-album-card__meta">' +
        (a.event_label ? "📅 " + escapeHtml(a.event_label) + " · " : "") +
        escapeHtml(a.updated_ago || "") +
        "</p></div>";
      card.addEventListener("click", function (e) {
        if (e.target.closest(".gl-album-card__menu")) return;
        openAlbumLightbox(a.id);
      });
      if (canManage) {
        var menuBtn = card.querySelector(".gl-album-card__menu");
        if (menuBtn) {
          menuBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            showAlbumMenu(menuBtn, a);
          });
        }
      }
      el.appendChild(card);
    });
  }

  function renderPhotos(photos) {
    var masonry = document.getElementById("gl-masonry");
    var skel = document.getElementById("gl-skeleton");
    if (!masonry) return;
    state.photos = photos || [];
    if (skel) skel.classList.add("is-hidden");
    masonry.querySelectorAll(".gl-photo").forEach(function (n) {
      n.remove();
    });
    state.photos.forEach(function (ph, i) {
      var item = document.createElement("figure");
      item.className = "gl-photo gl-photo--" + (ph.aspect || "square");
      item.dataset.photoId = ph.id;
      item.dataset.index = i;
      item.innerHTML =
        '<img src="' +
        (ph.thumb || ph.src) +
        '" alt="" loading="lazy" decoding="async" />' +
        '<div class="gl-photo__overlay">' +
        escapeHtml(ph.album_title || "") +
        " · " +
        escapeHtml(ph.taken_label || "") +
        "</div>" +
        (canManage
          ? '<button type="button" class="gl-photo__menu" aria-label="Ações">⋮</button>'
          : "");
      item.querySelector("img").addEventListener("click", function () {
        openLightboxFromGrid(i);
      });
      if (canManage) {
        var mb = item.querySelector(".gl-photo__menu");
        mb.addEventListener("click", function (e) {
          e.stopPropagation();
          showPhotoMenu(mb, ph, item);
        });
      }
      masonry.appendChild(item);
    });
  }

  function renderActivity(items) {
    var el = document.getElementById("gl-activity");
    if (!el) return;
    el.innerHTML = "";
    (items || []).forEach(function (it) {
      var li = document.createElement("li");
      li.innerHTML =
        '<span class="gl-activity__icon gl-activity__icon--' +
        (it.color || "slate") +
        '">' +
        (it.icon || "•") +
        "</span><span>" +
        escapeHtml(it.message) +
        ' <em style="opacity:.7">' +
        escapeHtml(it.ago || "") +
        "</em></span>";
      el.appendChild(li);
    });
  }

  function fillAlbumSelects(options) {
    var sel = document.getElementById("gl-upload-album");
    var move = document.getElementById("gl-move-album-select");
    var html = '<option value="">Selecione…</option>';
    (options || []).forEach(function (o) {
      html += '<option value="' + o.id + '">' + escapeHtml(o.title) + "</option>";
    });
    if (sel) sel.innerHTML = html;
    if (move) move.innerHTML = html;
  }

  function applyData(data) {
    renderHero(data.hero_slides);
    renderAlbums(data.albums);
    renderPhotos(data.photos);
    renderActivity(data.recent_activity);
    fillAlbumSelects(data.album_options);
  }

  function escapeHtml(s) {
    if (!s) return "";
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function openModal(id) {
    var m = document.getElementById(id);
    if (m) {
      m.classList.add("is-open");
      m.setAttribute("aria-hidden", "false");
    }
  }

  function closeModals() {
    document.querySelectorAll(".gl-modal.is-open").forEach(function (m) {
      m.classList.remove("is-open");
      m.setAttribute("aria-hidden", "true");
    });
  }

  document.querySelectorAll("[data-gl-close]").forEach(function (btn) {
    btn.addEventListener("click", closeModals);
  });

  if (canManage) {
    document.getElementById("gl-btn-new-album")?.addEventListener("click", function () {
      openModal("gl-modal-album");
    });
    document.getElementById("gl-btn-upload")?.addEventListener("click", function () {
      state.pendingFiles = [];
      renderUploadPreview();
      openModal("gl-modal-upload");
    });
    document.querySelectorAll("[data-gl-quick]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var q = btn.getAttribute("data-gl-quick");
        if (q === "album") openModal("gl-modal-album");
        if (q === "upload") document.getElementById("gl-btn-upload")?.click();
        if (q === "trash") alert("Itens na lixeira podem ser restaurados em breve pelo painel.");
      });
    });

    document.getElementById("gl-form-album")?.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData(e.target);
      fetch(apiAlbums, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: fd.get("title"),
          description: fd.get("description"),
          category: fd.get("category"),
          event_date: fd.get("event_date"),
          featured: fd.get("featured") === "on",
        }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (res) {
          if (res.ok) {
            closeModals();
            refreshBootstrap();
          } else alert(res.error || "Erro ao salvar.");
        });
    });
  }

  function refreshBootstrap() {
    var q = document.getElementById("gl-search-input")?.value || "";
    var url = apiBootstrap + (q ? "?q=" + encodeURIComponent(q) : "");
    fetch(url)
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.ok !== false) applyData(data);
      });
  }

  document.getElementById("gl-search-form")?.addEventListener("submit", function (e) {
    e.preventDefault();
    refreshBootstrap();
  });

  document.getElementById("gl-btn-filters")?.addEventListener("click", function () {
    var panel = document.getElementById("gl-filters-panel");
    if (panel) {
      var open = panel.hasAttribute("hidden");
      if (open) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
      this.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });

  /* Upload */
  var dropzone = document.getElementById("gl-dropzone");
  var fileInput = document.getElementById("gl-file-input");

  function renderUploadPreview() {
    var prev = document.getElementById("gl-upload-preview");
    var submit = document.getElementById("gl-upload-submit");
    if (!prev) return;
    prev.innerHTML = "";
    state.pendingFiles.forEach(function (f, i) {
      var img = document.createElement("img");
      img.src = URL.createObjectURL(f);
      img.title = f.name;
      prev.appendChild(img);
    });
    if (submit) submit.disabled = state.pendingFiles.length === 0;
  }

  function addFiles(files) {
    Array.prototype.forEach.call(files, function (f) {
      if (f.type && f.type.indexOf("image/") === 0) state.pendingFiles.push(f);
    });
    renderUploadPreview();
  }

  document.getElementById("gl-pick-files")?.addEventListener("click", function () {
    fileInput?.click();
  });
  fileInput?.addEventListener("change", function () {
    addFiles(fileInput.files);
    fileInput.value = "";
  });
  dropzone?.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone?.addEventListener("dragleave", function () {
    dropzone.classList.remove("is-dragover");
  });
  dropzone?.addEventListener("drop", function (e) {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
    addFiles(e.dataTransfer.files);
  });

  document.getElementById("gl-upload-submit")?.addEventListener("click", function () {
    if (!state.pendingFiles.length) return;
    var albumId = document.getElementById("gl-upload-album")?.value;
    var newTitle = document.getElementById("gl-upload-new-album")?.value?.trim();
    var fd = new FormData();
    if (albumId) fd.append("album_id", albumId);
    if (newTitle) fd.append("new_album_title", newTitle);
    state.pendingFiles.forEach(function (f) {
      fd.append("photos", f);
    });
    var prog = document.getElementById("gl-upload-progress");
    var bar = document.getElementById("gl-upload-pct");
    if (prog) prog.hidden = false;
    var xhr = new XMLHttpRequest();
    xhr.open("POST", apiUpload);
    xhr.upload.onprogress = function (ev) {
      if (ev.lengthComputable && bar) {
        bar.style.width = Math.round((ev.loaded / ev.total) * 100) + "%";
      }
    };
    xhr.onload = function () {
      if (prog) prog.hidden = true;
      try {
        var res = JSON.parse(xhr.responseText);
        if (res.ok) {
          state.pendingFiles = [];
          closeModals();
          refreshBootstrap();
        } else alert(res.error || "Falha no envio.");
      } catch (err) {
        alert("Erro ao processar resposta.");
      }
    };
    xhr.send(fd);
  });

  /* Lightbox */
  var lb = document.getElementById("gl-lightbox");
  function openLightbox(list, index) {
    state.lightbox = list;
    state.lbIndex = index;
    updateLightbox();
    lb?.classList.add("is-open");
    lb?.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    lb?.classList.remove("is-open");
    lb?.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function updateLightbox() {
    var ph = state.lightbox[state.lbIndex];
    if (!ph) return;
    var img = document.getElementById("gl-lb-img");
    var counter = document.getElementById("gl-lb-counter");
    var title = document.getElementById("gl-lb-title");
    var meta = document.getElementById("gl-lb-meta");
    var desc = document.getElementById("gl-lb-desc");
    var dl = document.getElementById("gl-lb-download");
    if (img) img.src = ph.src;
    if (counter)
      counter.textContent = state.lbIndex + 1 + " / " + state.lightbox.length;
    if (title) title.textContent = ph.title || ph.album_title || "Foto";
    if (meta)
      meta.textContent =
        (ph.album_title || "") +
        (ph.taken_label ? " · " + ph.taken_label : "");
    if (desc) desc.textContent = ph.description || "";
    if (dl) {
      dl.href = ph.src;
      dl.download = "";
    }
    var thumbs = document.getElementById("gl-lb-thumbs");
    if (thumbs) {
      thumbs.innerHTML = "";
      state.lightbox.forEach(function (p, i) {
        var t = document.createElement("img");
        t.src = p.thumb || p.src;
        if (i === state.lbIndex) t.classList.add("is-active");
        t.addEventListener("click", function () {
          state.lbIndex = i;
          updateLightbox();
        });
        thumbs.appendChild(t);
      });
    }
  }

  function openLightboxFromGrid(index) {
    openLightbox(state.photos, index);
  }

  function openAlbumLightbox(albumId) {
    var url = pfx(
      (apiBootstrap || "").replace("/api/bootstrap", "/api/album/" + albumId + "/photos")
    );
    fetch(url)
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res.ok && res.photos && res.photos.length) openLightbox(res.photos, 0);
      });
  }

  document.getElementById("gl-lb-close")?.addEventListener("click", closeLightbox);
  document.getElementById("gl-lb-prev")?.addEventListener("click", function () {
    state.lbIndex =
      (state.lbIndex - 1 + state.lightbox.length) % state.lightbox.length;
    updateLightbox();
  });
  document.getElementById("gl-lb-next")?.addEventListener("click", function () {
    state.lbIndex = (state.lbIndex + 1) % state.lightbox.length;
    updateLightbox();
  });
  document.getElementById("gl-lb-share")?.addEventListener("click", function () {
    var ph = state.lightbox[state.lbIndex];
    if (navigator.share && ph) {
      navigator.share({ title: ph.title, url: ph.src }).catch(function () {});
    } else if (ph) {
      navigator.clipboard?.writeText(window.location.origin + ph.src);
      alert("Link copiado.");
    }
  });
  document.getElementById("gl-lb-delete")?.addEventListener("click", function () {
    var ph = state.lightbox[state.lbIndex];
    if (!ph || !confirm("Excluir esta foto?")) return;
    var url = pfx("/admin/galeria/api/photos/" + ph.id);
    fetch(url, { method: "DELETE" })
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res.ok) {
          closeLightbox();
          refreshBootstrap();
        }
      });
  });
  lb?.querySelector(".gl-lightbox__backdrop")?.addEventListener("click", closeLightbox);
  document.addEventListener("keydown", function (e) {
    if (!lb?.classList.contains("is-open")) return;
    if (e.key === "Escape") closeLightbox();
    if (e.key === "ArrowLeft") document.getElementById("gl-lb-prev")?.click();
    if (e.key === "ArrowRight") document.getElementById("gl-lb-next")?.click();
  });

  function showPhotoMenu(anchor, ph, item) {
    closeDropdowns();
    item.classList.add("is-menu-open");
    var dd = document.createElement("div");
    dd.className = "gl-dropdown";
    dd.innerHTML =
      '<button type="button" data-act="view">Ver foto</button>' +
      '<button type="button" data-act="edit">Editar informações</button>' +
      '<button type="button" data-act="move">Mover para outro álbum</button>' +
      '<button type="button" data-act="cover">Definir como capa do álbum</button>' +
      '<button type="button" class="danger" data-act="delete">Excluir foto</button>';
    item.appendChild(dd);
    dd.addEventListener("click", function (e) {
      var act = e.target.getAttribute("data-act");
      if (act === "view") {
        var idx = state.photos.findIndex(function (p) {
          return p.id === ph.id;
        });
        openLightbox(state.photos, idx >= 0 ? idx : 0);
      }
      if (act === "edit") openEditPhoto(ph);
      if (act === "move") openEditPhoto(ph, true);
      if (act === "cover") setCover(ph);
      if (act === "delete") deletePhoto(ph);
      closeDropdowns();
    });
    document.addEventListener(
      "click",
      function handler(ev) {
        if (!item.contains(ev.target)) {
          closeDropdowns();
          document.removeEventListener("click", handler);
        }
      },
      { once: true }
    );
  }

  function showAlbumMenu(anchor, album) {
    closeDropdowns();
    var dd = document.createElement("div");
    dd.className = "gl-dropdown";
    dd.style.position = "absolute";
    dd.innerHTML =
      '<button type="button" data-act="open">Abrir álbum</button>' +
      '<button type="button" data-act="feature">Destacar no carrossel</button>' +
      '<button type="button" class="danger" data-act="trash">Excluir álbum</button>';
    anchor.parentElement.appendChild(dd);
    dd.addEventListener("click", function (e) {
      var act = e.target.getAttribute("data-act");
      if (act === "open") openAlbumLightbox(album.id);
      if (act === "feature") {
        fetch(pfx("/admin/galeria/api/albums/" + album.id), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ set_featured: true }),
        }).then(function () {
          refreshBootstrap();
        });
      }
      if (act === "trash" && confirm("Mover álbum para a lixeira?")) {
        fetch(pfx("/admin/galeria/api/albums/" + album.id), { method: "DELETE" }).then(
          function () {
            refreshBootstrap();
          }
        );
      }
      closeDropdowns();
    });
  }

  function closeDropdowns() {
    document.querySelectorAll(".gl-dropdown").forEach(function (d) {
      d.remove();
    });
    document.querySelectorAll(".gl-photo.is-menu-open").forEach(function (p) {
      p.classList.remove("is-menu-open");
    });
  }

  function openEditPhoto(ph, focusMove) {
    var form = document.getElementById("gl-form-edit-photo");
    if (!form) return;
    form.elements.photo_id.value = ph.id;
    form.elements.title.value = ph.title || "";
    form.elements.description.value = ph.description || "";
    form.elements.tags.value = (ph.tags || []).join(", ");
    form.elements.taken_at.value = ph.taken_at ? ph.taken_at.slice(0, 10) : "";
    var move = document.getElementById("gl-move-album-select");
    if (move) move.value = ph.album_id || "";
    openModal("gl-modal-edit-photo");
    if (focusMove && move) move.focus();
  }

  var formEditPhoto = document.getElementById("gl-form-edit-photo");
  formEditPhoto?.addEventListener("submit", function (e) {
    e.preventDefault();
    var fd = new FormData(e.target);
    var id = fd.get("photo_id");
    var body = {
      title: fd.get("title"),
      description: fd.get("description"),
      tags: fd.get("tags"),
      taken_at: fd.get("taken_at"),
    };
    if (fd.get("album_id")) body.album_id = parseInt(fd.get("album_id"), 10);
    fetch(pfx("/admin/galeria/api/photos/" + id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res.ok) {
          closeModals();
          refreshBootstrap();
        } else alert(res.error || "Erro.");
      });
  });

  function setCover(ph) {
    fetch(pfx("/admin/galeria/api/albums/" + ph.album_id + "/cover"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_id: ph.id }),
    }).then(function () {
      refreshBootstrap();
    });
  }

  function deletePhoto(ph) {
    if (!confirm("Excluir esta foto?")) return;
    fetch(pfx("/admin/galeria/api/photos/" + ph.id), { method: "DELETE" }).then(function () {
      refreshBootstrap();
    });
  }

  /* Init */
  var boot = loadBootstrap();
  applyData(boot);
  if (typeof AOS !== "undefined") {
    AOS.init({ duration: 500, once: true, offset: 40 });
  }
})();
