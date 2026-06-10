/**
 * Financeiro premium — gráfico, drawers, PIX
 */
(function () {
  "use strict";

  var app = document.getElementById("fn-app");
  if (!app) return;

  var drawerRoot = document.getElementById("fn-drawer-root");
  var drawers = {
    ledger: document.getElementById("fn-drawer-ledger"),
    fee: document.getElementById("fn-drawer-fee"),
    bulk: document.getElementById("fn-drawer-bulk"),
  };
  var activeDrawer = null;
  var dirSelect = document.getElementById("fn-ledger-dir-select");
  var dirHidden = document.getElementById("fn-ledger-direction");

  function openDrawer(which) {
    if (!drawerRoot || !drawers[which]) return;
    Object.keys(drawers).forEach(function (k) {
      if (drawers[k]) {
        drawers[k].hidden = k !== which;
      }
    });
    activeDrawer = which;
    drawerRoot.classList.add("is-open");
    drawerRoot.setAttribute("aria-hidden", "false");
    document.body.classList.add("fn-drawer-open");
  }

  function closeDrawer() {
    if (!drawerRoot) return;
    drawerRoot.classList.remove("is-open");
    drawerRoot.setAttribute("aria-hidden", "true");
    document.body.classList.remove("fn-drawer-open");
    activeDrawer = null;
  }

  document.querySelectorAll("[data-fn-drawer-close]").forEach(function (el) {
    el.addEventListener("click", closeDrawer);
  });
  var backdrop = document.getElementById("fn-drawer-backdrop");
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawerRoot && drawerRoot.classList.contains("is-open")) {
      closeDrawer();
    }
  });

  var btnLedger = document.getElementById("fn-btn-ledger");
  var btnFee = document.getElementById("fn-btn-fee");
  var btnBulk = document.getElementById("fn-btn-bulk");
  var quickFee = document.getElementById("fn-quick-fee");
  var quickExpense = document.getElementById("fn-quick-expense");
  var quickBulk = document.getElementById("fn-quick-bulk");

  if (btnLedger) btnLedger.addEventListener("click", function () { openDrawer("ledger"); });
  if (btnFee) btnFee.addEventListener("click", function () { openDrawer("fee"); });
  if (btnBulk) btnBulk.addEventListener("click", function () { openDrawer("bulk"); });
  if (quickFee) quickFee.addEventListener("click", function () { openDrawer("fee"); });
  if (quickBulk) quickBulk.addEventListener("click", function () { openDrawer("bulk"); });
  if (quickExpense) {
    quickExpense.addEventListener("click", function () {
      openDrawer("ledger");
      if (dirSelect) dirSelect.value = "expense";
      if (dirHidden) dirHidden.value = "expense";
    });
  }

  if (dirSelect && dirHidden) {
    dirSelect.addEventListener("change", function () {
      dirHidden.value = dirSelect.value;
    });
    dirHidden.value = dirSelect.value;
  }

  /* Cobrança: um desbravador ou todos */
  var feeForm = document.getElementById("fn-fee-form");
  var sendAllInput = document.getElementById("fn-fee-send-all");
  var memberWrap = document.getElementById("fn-fee-member-wrap");
  var memberSelect = document.getElementById("fn-f-member");
  var targetHint = document.getElementById("fn-target-hint");
  var feeSubmit = document.getElementById("fn-fee-submit");
  var targetBtns = document.querySelectorAll("[data-fn-target]");

  function setFeeTarget(mode) {
    var all = mode === "all";
    if (sendAllInput) sendAllInput.value = all ? "1" : "0";
    targetBtns.forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-fn-target") === mode);
    });
    if (memberWrap) memberWrap.classList.toggle("is-hidden", all);
    if (memberSelect) {
      memberSelect.required = !all;
      if (all) memberSelect.removeAttribute("name");
      else memberSelect.setAttribute("name", "member_id");
    }
    if (targetHint) {
      targetHint.textContent = all
        ? "A cobrança será criada para todos os desbravadores ativos. Ficará pendente (laranja) até o diretor confirmar o pagamento."
        : "Selecione quem receberá esta cobrança. Visível no portal do responsável assim que for lançada.";
    }
    if (feeSubmit) {
      feeSubmit.textContent = all ? "Enviar para todos" : "Criar cobrança";
    }
  }

  targetBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setFeeTarget(btn.getAttribute("data-fn-target") === "all" ? "all" : "one");
    });
  });
  setFeeTarget("one");

  function copyText(text, msg) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        if (msg) alert(msg);
      });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      if (msg) alert(msg);
    }
  }

  var copyPix = document.getElementById("fn-copy-pix");
  var pixKeyEl = document.getElementById("fn-pix-key-text");
  if (copyPix && pixKeyEl) {
    copyPix.addEventListener("click", function () {
      copyText(pixKeyEl.textContent.trim(), "Chave PIX copiada!");
    });
  }

  var copyPayload = document.getElementById("fn-copy-payload");
  var payloadEl = document.getElementById("fn-pix-payload");
  if (copyPayload && payloadEl) {
    copyPayload.addEventListener("click", function () {
      try {
        var payload = JSON.parse(payloadEl.textContent || '""');
        copyText(payload, "Código PIX copiado!");
      } catch (e) {
        copyText(payloadEl.textContent, "Código PIX copiado!");
      }
    });
  }

  /* Chart.js fluxo */
  var canvas = document.getElementById("fn-flow-chart");
  var dataEl = document.getElementById("fn-flow-data");
  if (canvas && dataEl && typeof Chart !== "undefined") {
    try {
      var flow = JSON.parse(dataEl.textContent || "{}");
      var ctx = canvas.getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: flow.labels || [],
          datasets: [
            {
              label: "Entradas",
              data: flow.income || [],
              borderColor: "#059669",
              backgroundColor: "rgba(5, 150, 105, 0.08)",
              tension: 0.35,
              fill: true,
            },
            {
              label: "Saídas",
              data: flow.expense || [],
              borderColor: "#dc2626",
              backgroundColor: "rgba(220, 38, 38, 0.06)",
              tension: 0.35,
              fill: true,
            },
            {
              label: "Saldo acumulado",
              data: flow.balance || [],
              borderColor: "#2563eb",
              borderDash: [4, 4],
              tension: 0.35,
              fill: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } },
          },
          scales: {
            y: {
              ticks: {
                callback: function (v) {
                  return "R$ " + (v / 100).toLocaleString("pt-BR", { minimumFractionDigits: 0 });
                },
              },
            },
          },
        },
      });
    } catch (err) {
      console.warn("fn chart", err);
    }
  }
})();
