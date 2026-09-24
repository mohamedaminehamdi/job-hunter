/* The picker, the theme, and one entrance animation.
   No framework: the page is 40KB of static HTML on GitHub Pages and a
   dependency would be most of its weight. */

(function () {
  "use strict";

  // --- theme --------------------------------------------------------------
  // Three states, like the OS: light, dark, and "whatever the system says".
  // Stored so it survives a reload; wrapped because a browser set to block
  // site data throws on the read rather than returning null.

  var root = document.documentElement;

  function stored(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function remember(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private window */ }
  }

  // The saved theme is applied by the inline script in <head>, before first
  // paint, so the page does not flash the wrong one.

  var toggle = document.getElementById("theme");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var now = root.getAttribute("data-theme") || (dark ? "dark" : "light");
      var next = now === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      remember("jobhunt-theme", next);
    });
  }

  // --- the picker ---------------------------------------------------------

  var buttons = Array.prototype.slice.call(
    document.querySelectorAll(".agents button[data-agent]"));
  var panels = Array.prototype.slice.call(document.querySelectorAll(".agent-panel"));
  var empty = document.getElementById("panel-empty");

  function show(id) {
    buttons.forEach(function (b) {
      b.setAttribute("aria-selected", String(b.dataset.agent === id));
    });
    panels.forEach(function (p) { p.hidden = p.dataset.for !== id; });
    if (empty) empty.hidden = true;
    remember("jobhunt-agent", id);
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () { show(button.dataset.agent); });
    button.addEventListener("keydown", function (event) {
      var at = buttons.indexOf(button);
      var to = event.key === "ArrowDown" ? at + 1
             : event.key === "ArrowUp" ? at - 1 : -1;
      if (to < 0 || to >= buttons.length) return;
      event.preventDefault();
      buttons[to].focus();
      show(buttons[to].dataset.agent);
    });
  });

  // Come back to the agent you picked last time. A person installing on a
  // second machine should not have to find their row again.
  var last = stored("jobhunt-agent");
  if (last && buttons.some(function (b) { return b.dataset.agent === last; })) {
    show(last);
  }

  // Deep link: /#install?agent=codex, so the README can point straight at one.
  var asked = (location.hash.split("agent=")[1] || "").split("&")[0];
  if (asked && buttons.some(function (b) { return b.dataset.agent === asked; })) {
    show(asked);
  }

  // --- copy ---------------------------------------------------------------

  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest(".copy") : null;
    if (!button) return;

    var text = button.dataset.copy || "";
    var label = button.querySelector("span");

    function done(ok) {
      button.dataset.state = ok ? "copied" : "";
      if (label) label.textContent = ok ? "Copied" : "Press Cmd+C";
      setTimeout(function () {
        button.dataset.state = "";
        if (label) label.textContent = "Copy";
      }, 1800);
    }

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); },
                                               function () { select(button); });
    } else {
      select(button);
    }
  });

  // Clipboard access is refused over plain http and in some embedded views.
  // Selecting the text is the honest fallback - the person presses Cmd+C.
  function select(button) {
    var code = button.parentNode.querySelector("code");
    if (!code) return;
    var range = document.createRange();
    range.selectNodeContents(code);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var label = button.querySelector("span");
    if (label) label.textContent = "Press Cmd+C";
    setTimeout(function () { if (label) label.textContent = "Copy"; }, 2400);
  }

  // --- chrome -------------------------------------------------------------

  var bar = document.querySelector(".bar");
  if (bar) {
    var onScroll = function () {
      bar.classList.toggle("stuck", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  var rising = document.querySelectorAll(".rise");
  if (!("IntersectionObserver" in window)) {
    Array.prototype.forEach.call(rising, function (el) { el.classList.add("in"); });
  } else {
    var watcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        watcher.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    Array.prototype.forEach.call(rising, function (el) { watcher.observe(el); });
  }
})();
