/**
 * Portal Família — Progresso gamificado
 */
(function () {
  "use strict";

  var root = document.getElementById("pg-app");
  if (!root) return;

  var prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var CIRC = 2 * Math.PI * 42;

  function animateBars() {
    root.querySelectorAll("[data-pg-progress]").forEach(function (el) {
      var span = el.querySelector("span");
      if (!span) return;
      var pct = parseFloat(el.getAttribute("data-pg-progress") || "0");
      pct = Math.max(0, Math.min(100, pct));
      if (prefersReduced) {
        span.style.width = pct + "%";
        return;
      }
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          span.style.width = pct + "%";
        });
      });
    });
  }

  function animateRings() {
    root.querySelectorAll(".pg-spec-ring__fill").forEach(function (circle) {
      var pct = parseFloat(circle.getAttribute("data-percent") || "0");
      pct = Math.max(0, Math.min(100, pct));
      var offset = CIRC * (1 - pct / 100);
      if (prefersReduced) {
        circle.style.strokeDashoffset = String(offset);
        return;
      }
      requestAnimationFrame(function () {
        circle.style.strokeDashoffset = String(offset);
      });
    });
  }

  function pulseLevelShield() {
    var shield = root.querySelector(".pg-level-shield");
    if (!shield || prefersReduced) return;
    shield.addEventListener("animationend", function () {
      shield.style.animation = "none";
    });
  }

  function observeAchievements() {
    if (!("IntersectionObserver" in window) || prefersReduced) {
      root.querySelectorAll("[data-pg-achievement]").forEach(function (el) {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
      return;
    }
    var obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("pg-achievement--visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    root.querySelectorAll("[data-pg-achievement]").forEach(function (el) {
      obs.observe(el);
    });
  }

  animateBars();
  animateRings();
  pulseLevelShield();
  observeAchievements();
})();
