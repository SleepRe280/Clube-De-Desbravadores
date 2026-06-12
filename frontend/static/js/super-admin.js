(function () {
  "use strict";

  var sidebar = document.getElementById("sa-sidebar");
  var overlay = document.getElementById("sa-overlay");
  var menuBtn = document.getElementById("sa-menu-btn");

  function setSidebarOpen(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("sa-sidebar--open", open);
    if (overlay) overlay.classList.toggle("sa-overlay--visible", open);
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) document.body.style.removeProperty("overflow");
  }

  if (menuBtn) {
    menuBtn.addEventListener("click", function () {
      setSidebarOpen(!sidebar.classList.contains("sa-sidebar--open"));
    });
  }

  if (overlay) {
    overlay.addEventListener("click", function () {
      setSidebarOpen(false);
    });
  }

  document.querySelectorAll("[data-sa-close-sidebar]").forEach(function (el) {
    el.addEventListener("click", function () {
      setSidebarOpen(false);
    });
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth >= 1024) setSidebarOpen(false);
  });

  /* Date/time widget */
  var dtEl = document.getElementById("sa-datetime");
  if (dtEl) {
    var days = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
    var months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    function tick() {
      var now = new Date();
      var h = String(now.getHours()).padStart(2, "0");
      var m = String(now.getMinutes()).padStart(2, "0");
      dtEl.textContent =
        now.getDate() + " de " + months[now.getMonth()] + ", " + now.getFullYear() +
        " | " + days[now.getDay()] + ", " + h + ":" + m;
    }
    tick();
    setInterval(tick, 30000);
  }

  /* Charts */
  function initCharts() {
    if (typeof Chart === "undefined") return;

    var growthEl = document.getElementById("sa-chart-growth");
    if (growthEl) {
      var labels = JSON.parse(growthEl.dataset.labels || "[]");
      var values = JSON.parse(growthEl.dataset.values || "[]");
      new Chart(growthEl, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: "Clubes",
            data: values,
            borderColor: "#003580",
            backgroundColor: "rgba(0, 53, 128, 0.08)",
            fill: true,
            tension: 0.35,
            pointBackgroundColor: "#003580",
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.04)" } },
            x: { grid: { display: false } }
          }
        }
      });
    }

    var healthEl = document.getElementById("sa-chart-health");
    if (healthEl) {
      var excellent = parseInt(healthEl.dataset.excellent || "0", 10);
      var good = parseInt(healthEl.dataset.good || "0", 10);
      var attention = parseInt(healthEl.dataset.attention || "0", 10);
      var critical = parseInt(healthEl.dataset.critical || "0", 10);
      new Chart(healthEl, {
        type: "doughnut",
        data: {
          labels: ["Excelente", "Bom", "Atenção", "Crítico"],
          datasets: [{
            data: [excellent, good, attention, critical],
            backgroundColor: ["#22c55e", "#003580", "#FFD700", "#CC0000"],
            borderWidth: 0,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          plugins: {
            legend: { display: false },
            tooltip: { enabled: true }
          }
        },
        plugins: [{
          id: "centerText",
          beforeDraw: function (chart) {
            var ctx = chart.ctx;
            var total = excellent + good + attention + critical;
            ctx.save();
            ctx.font = "bold 1.25rem Plus Jakarta Sans, sans-serif";
            ctx.fillStyle = "#003580";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            var centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
            var centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
            ctx.fillText(total, centerX, centerY - 6);
            ctx.font = "600 0.7rem Plus Jakarta Sans, sans-serif";
            ctx.fillStyle = "#64748b";
            ctx.fillText("total", centerX, centerY + 12);
            ctx.restore();
          }
        }]
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCharts);
  } else {
    initCharts();
  }

  /* Confirm dialogs enhancement */
  document.querySelectorAll("form[data-sa-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var msg = form.getAttribute("data-sa-confirm");
      if (msg && !confirm(msg)) e.preventDefault();
    });
  });
})();
