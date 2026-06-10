(function () {
  "use strict";

  document.documentElement.classList.add("login-premium");
  document.body.classList.add("login-premium");

  requestAnimationFrame(function () {
    document.body.classList.add("login-premium--ready");
  });

  var passwordInput = document.getElementById("login-password");
  var toggleBtn = document.getElementById("toggle-password");

  if (passwordInput && toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      var show = passwordInput.type === "password";
      passwordInput.type = show ? "text" : "password";
      toggleBtn.setAttribute("aria-pressed", show ? "true" : "false");
      toggleBtn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
    });
  }

  var flashCloseButtons = document.querySelectorAll(".flash-msg__close");
  flashCloseButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var msg = btn.closest(".flash-msg");
      if (msg) msg.remove();
    });
  });
})();
