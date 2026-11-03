(function () {
  "use strict";
  var key = "nfl-theme";
  try {
    var stored = localStorage.getItem(key);
    if (stored === "light" || stored === "dark") document.documentElement.setAttribute("data-theme", stored);
  } catch (err) { /* private mode can block storage */ }
  function pressed() {
    var theme = document.documentElement.getAttribute("data-theme");
    var dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
    });
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var theme = document.documentElement.getAttribute("data-theme");
    var dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem(key, next); } catch (err) { /* ignore */ }
    pressed();
  });
  pressed();
})();
