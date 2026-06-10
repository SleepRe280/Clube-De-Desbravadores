(function () {
  "use strict";

  var doc = document.documentElement;
  doc.classList.add("js");

  var reduceMotion =
    typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) {
    doc.classList.add("reduce-motion");
  }

  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  }

  function dismissFlash(el) {
    if (!el || el.classList.contains("flash-msg--dismissing")) return;
    el.classList.add("flash-msg--dismissing");
    var done = function () {
      el.remove();
      var stack = document.querySelector(".flash-stack");
      if (stack && !stack.querySelector(".flash-msg")) {
        stack.remove();
      }
    };
    el.addEventListener("animationend", done, { once: true });
    window.setTimeout(done, 400);
  }

  function initFlashes() {
    var msgs = document.querySelectorAll(".flash-msg[data-flash]");
    msgs.forEach(function (el, i) {
      if (!reduceMotion) {
        el.style.animationDelay = Math.min(i * 0.06, 0.35) + "s";
      }
      el.setAttribute("data-flash-ready", "1");
      var auto = window.setTimeout(function () {
        dismissFlash(el);
      }, 9000);
      var close = el.querySelector(".flash-msg__close");
      if (close) {
        close.addEventListener("click", function () {
          window.clearTimeout(auto);
          dismissFlash(el);
        });
      }
    });
  }

  function initAdminNav() {
    var toggle = document.getElementById("admin-nav-toggle");
    if (!toggle) return;
    var sidebar = document.querySelector(".admin-sidebar");
    if (!sidebar) return;
    sidebar.querySelectorAll("a.admin-nav-link").forEach(function (link) {
      link.addEventListener("click", function () {
        toggle.checked = false;
      });
    });
    var overlay = document.querySelector(".admin-overlay");
    if (overlay) {
      overlay.addEventListener("click", function () {
        toggle.checked = false;
      });
    }
  }

  function initParentHeaderScroll() {
    var header = document.querySelector(".parent-header");
    var main = document.querySelector(".parent-app > main");
    if (!header || !main) return;
    var ticking = false;
    function update() {
      ticking = false;
      header.classList.toggle("parent-header--scrolled", main.scrollTop > 8);
    }
    main.addEventListener(
      "scroll",
      function () {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(update);
        }
      },
      { passive: true }
    );
    update();
  }

  function initPageEnter() {
    var adminMain = document.querySelector(".admin-main");
    if (adminMain) adminMain.classList.add("admin-main--enter");
    var parentMain = document.querySelector(".parent-app > main");
    if (parentMain) parentMain.classList.add("parent-main--enter");
    var authPanel = document.querySelector("[data-auth-panel]");
    if (authPanel) authPanel.classList.add("auth-panel--enter");
    var authShell = document.querySelector(".auth-shell");
    if (authShell) authShell.classList.add("is-ready");
  }

  /** Corrige favoritos sem porta (http://127.0.0.1/admin → :5055) — causa ERR_CONNECTION_REFUSED. */
  function initLocalDevPortFix() {
    var host = window.location.hostname;
    if (host !== "127.0.0.1" && host !== "localhost") return;
    var port = window.location.port;
    var devPort = "5055";
    if (!port) {
      var dest =
        window.location.protocol +
        "//" +
        host +
        ":" +
        devPort +
        window.location.pathname +
        window.location.search +
        window.location.hash;
      window.location.replace(dest);
      return;
    }
    document.documentElement.setAttribute("data-dev-port", port);
  }

  function showDevOfflineBanner() {
    if (document.getElementById("dev-server-offline")) return;
    var el = document.createElement("div");
    el.id = "dev-server-offline";
    el.setAttribute("role", "alert");
    el.style.cssText =
      "position:fixed;bottom:0;left:0;right:0;z-index:99999;padding:12px 16px;" +
      "background:#7f1d1d;color:#fff;font:600 13px/1.4 system-ui,sans-serif;text-align:center;" +
      "box-shadow:0 -4px 20px rgba(0,0,0,.25);";
    el.innerHTML =
      "Servidor local parado. Execute <strong>run.bat</strong> e abra " +
      "<strong>http://127.0.0.1:5055/login</strong> (mantenha o terminal aberto).";
    document.body.appendChild(el);
  }

  function initDevServerHealthWatch() {
    var host = window.location.hostname;
    if (host !== "127.0.0.1" && host !== "localhost") return;
    if (!window.location.port) return;
    var prefix = document.documentElement.getAttribute("data-url-prefix") || "";
    fetch(prefix + "/health", { cache: "no-store", credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) showDevOfflineBanner();
      })
      .catch(function () {
        showDevOfflineBanner();
      });
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (regs) {
      regs.forEach(function (r) {
        r.unregister();
      });
    });
  }

  initLocalDevPortFix();

  onReady(function () {
    initFlashes();
    initAdminNav();
    initParentHeaderScroll();
    initPageEnter();
    initDevServerHealthWatch();
  });
})();
