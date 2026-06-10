(function () {
  "use strict";

  var sidebar = document.getElementById("ap-sidebar");
  var overlay = document.getElementById("ap-overlay");
  var menuBtns = document.querySelectorAll("[data-ap-menu]");
  var STORAGE_PREFIX = "ap-nav-group:";

  function setSidebarOpen(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("ap-sidebar--open", open);
    if (overlay) overlay.classList.toggle("ap-overlay--visible", open);
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) {
      document.body.style.removeProperty("overflow");
    }
  }

  menuBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setSidebarOpen(!sidebar.classList.contains("ap-sidebar--open"));
    });
  });

  if (overlay) {
    overlay.addEventListener("click", function () {
      setSidebarOpen(false);
    });
  }

  document.querySelectorAll("[data-ap-close-sidebar]").forEach(function (el) {
    el.addEventListener("click", function () {
      setSidebarOpen(false);
    });
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth >= 1024) setSidebarOpen(false);
  });

  /* —— Accordion navigation groups —— */
  function setGroupOpen(group, open, persist) {
    if (!group) return;
    var panel = group.querySelector(".ap-nav-group__panel");
    var trigger = group.querySelector("[data-ap-nav-group-trigger]");
    var groupId = group.getAttribute("data-ap-nav-group") || "";

    group.classList.toggle("is-open", open);
    if (panel) panel.setAttribute("aria-hidden", open ? "false" : "true");
    if (trigger) trigger.setAttribute("aria-expanded", open ? "true" : "false");

    if (persist && groupId) {
      try {
        sessionStorage.setItem(STORAGE_PREFIX + groupId, open ? "1" : "0");
      } catch (e) {
        /* ignore */
      }
    }
  }

  function readStoredOpen(groupId, serverOpen) {
    if (serverOpen) return true;
    try {
      var stored = sessionStorage.getItem(STORAGE_PREFIX + groupId);
      if (stored === "1") return true;
      if (stored === "0") return false;
    } catch (e) {
      /* ignore */
    }
    return serverOpen;
  }

  function initNavGroups() {
    document.querySelectorAll("[data-ap-nav-group]").forEach(function (group) {
      var groupId = group.getAttribute("data-ap-nav-group") || "";
      var serverOpen = group.classList.contains("is-open");
      var open = readStoredOpen(groupId, serverOpen);
      setGroupOpen(group, open, false);

      var trigger = group.querySelector("[data-ap-nav-group-trigger]");
      if (!trigger) return;

      trigger.addEventListener("click", function () {
        var next = !group.classList.contains("is-open");
        setGroupOpen(group, next, true);
      });
    });
  }

  function openNavGroup(groupId) {
    var group = document.querySelector('[data-ap-nav-group="' + groupId + '"]');
    if (!group) return;
    setGroupOpen(group, true, true);
  }

  document.querySelectorAll("[data-ap-open-nav-group]").forEach(function (el) {
    el.addEventListener("click", function (ev) {
      var groupId = el.getAttribute("data-ap-open-nav-group");
      if (!groupId) return;
      if (window.innerWidth < 1024) {
        ev.preventDefault();
        openNavGroup(groupId);
        setSidebarOpen(true);
      }
    });
  });

  /* —— User dropdown —— */
  var userMenus = document.querySelectorAll("[data-ap-user-menu]");
  function closeUserMenus() {
    userMenus.forEach(function (menu) {
      var trigger = menu.querySelector("[data-ap-user-menu-trigger]");
      var dropdown = menu.querySelector("[data-ap-user-menu-dropdown]");
      if (dropdown) dropdown.hidden = true;
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  }

  userMenus.forEach(function (menu) {
    var trigger = menu.querySelector("[data-ap-user-menu-trigger]");
    var dropdown = menu.querySelector("[data-ap-user-menu-dropdown]");
    if (!trigger || !dropdown) return;
    trigger.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var willOpen = dropdown.hidden;
      closeUserMenus();
      dropdown.hidden = !willOpen;
      trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  });

  document.addEventListener("click", function () {
    closeUserMenus();
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closeUserMenus();
    if ((ev.ctrlKey || ev.metaKey) && ev.key === "/") {
      var searchInput = document.querySelector(".ap-search input");
      if (searchInput) {
        ev.preventDefault();
        searchInput.focus();
      }
    }
  });

  initNavGroups();
})();
