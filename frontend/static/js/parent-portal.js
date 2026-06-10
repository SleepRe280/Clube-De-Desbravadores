/**
 * Portal Família — interações UI premium
 */
(function () {
  "use strict";

  var prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Sidebar mobile */
  var sidebar = document.getElementById("pp-sidebar");
  var backdrop = document.getElementById("pp-backdrop");
  var menuBtn = document.getElementById("pp-menu-btn");

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("pp-sidebar--open");
    backdrop?.classList.add("pp-backdrop--visible");
    document.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("pp-sidebar--open");
    backdrop?.classList.remove("pp-backdrop--visible");
    document.body.style.removeProperty("overflow");
  }

  menuBtn?.addEventListener("click", function () {
    if (sidebar?.classList.contains("pp-sidebar--open")) closeSidebar();
    else openSidebar();
  });
  backdrop?.addEventListener("click", closeSidebar);

  document.querySelectorAll("[data-pp-close-sidebar]").forEach(function (el) {
    el.addEventListener("click", closeSidebar);
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth >= 1024) closeSidebar();
  });

  /* Troca de filho */
  var childSelect = document.getElementById("pp-child-select");
  if (childSelect) {
    childSelect.addEventListener("change", function () {
      var id = this.value;
      if (!id) return;
      var url = new URL(window.location.href);
      url.searchParams.set("filho", id);
      window.location.href = url.toString();
    });
  }

  /* Contadores animados */
  function animateCount(el, target, duration) {
    target = parseInt(target, 10);
    if (isNaN(target)) return;
    if (prefersReduced) {
      el.textContent = String(target);
      return;
    }
    var start = 0;
    var startTime = null;
    duration = duration || 900;

    function step(ts) {
      if (!startTime) startTime = ts;
      var p = Math.min(1, (ts - startTime) / duration);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(start + (target - start) * eased));
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = String(target);
    }
    requestAnimationFrame(step);
  }

  document.querySelectorAll("[data-pp-count]").forEach(function (el) {
    var target = el.getAttribute("data-pp-count");
    if (target !== null) animateCount(el, target);
  });

  /* Barras de progresso */
  function initProgressBars() {
    document.querySelectorAll("[data-pp-progress]").forEach(function (wrap) {
      var span = wrap.querySelector("span");
      if (!span) return;
      var pct = parseFloat(wrap.getAttribute("data-pp-progress") || "0");
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
  initProgressBars();

  /* Gráfico desempenho */
  var chartEl = document.getElementById("ppChartAttendance");
  if (chartEl && typeof Chart !== "undefined") {
    try {
      var labels = JSON.parse(chartEl.getAttribute("data-labels") || "[]");
      var values = JSON.parse(chartEl.getAttribute("data-values") || "[]");
      var peak = parseInt(chartEl.getAttribute("data-peak") || "0", 10);

      new Chart(chartEl, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Frequência %",
              data: values,
              borderColor: "#22c55e",
              backgroundColor: function (context) {
                var chart = context.chart;
                var ctx = chart.ctx;
                var gradient = ctx.createLinearGradient(0, 0, 0, chart.height);
                gradient.addColorStop(0, "rgba(34, 197, 94, 0.35)");
                gradient.addColorStop(1, "rgba(34, 197, 94, 0.02)");
                return gradient;
              },
              fill: true,
              tension: 0.42,
              borderWidth: 3,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointBackgroundColor: "#22c55e",
              pointBorderColor: "#fff",
              pointBorderWidth: 2,
              pointHoverBackgroundColor: "#f9bc15",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: prefersReduced
            ? false
            : {
                duration: 1200,
                easing: "easeOutQuart",
              },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: "#0b132b",
              titleFont: { family: "'Plus Jakarta Sans', sans-serif", weight: "700" },
              bodyFont: { family: "'Plus Jakarta Sans', sans-serif" },
              padding: 12,
              cornerRadius: 10,
              callbacks: {
                label: function (ctx) {
                  return " " + ctx.parsed.y + "% de frequência";
                },
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                color: "#94a3b8",
                font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
              },
            },
            y: {
              min: 0,
              max: 100,
              grid: { color: "rgba(148, 163, 184, 0.15)" },
              ticks: {
                color: "#94a3b8",
                callback: function (v) {
                  return v + "%";
                },
                font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
              },
            },
          },
        },
      });

      if (peak >= 80 && !prefersReduced) {
        chartEl.setAttribute("aria-label", "Gráfico de frequência com pico de " + peak + "%");
      }
    } catch (err) {
      console.warn("Gráfico do portal:", err);
    }
  }

  /* Curtidas no feed */
  document.querySelectorAll("[data-pp-like]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var n = parseInt(btn.getAttribute("data-count") || "0", 10);
      var liked = btn.classList.toggle("text-rose-500");
      var next = liked ? n + 1 : Math.max(0, n - 1);
      btn.setAttribute("data-count", String(next));
      var span = btn.querySelector("[data-like-count]");
      if (span) span.textContent = String(next);
    });
  });

  /* Ícones do header — leve bounce no hover */
  if (!prefersReduced) {
    document.querySelectorAll(".pp-header__icon-btn").forEach(function (btn) {
      btn.addEventListener("mouseenter", function () {
        btn.style.transform = "translateY(-2px) scale(1.04)";
      });
      btn.addEventListener("mouseleave", function () {
        btn.style.transform = "";
      });
    });
  }

  /* Service workers antigos */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (regs) {
      regs.forEach(function (r) {
        r.unregister();
      });
    });
  }
})();
