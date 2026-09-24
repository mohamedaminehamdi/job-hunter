/* The picker, the theme, and the movement.
   No framework: this is one static page on GitHub Pages, and a library would
   be most of its weight. */

(function () {
  "use strict";

  var root = document.documentElement;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function stored(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function remember(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private window */ }
  }

  // --- theme --------------------------------------------------------------
  // Three states, like the OS: light, dark, and whatever the system says. The
  // saved one is applied by the inline script in <head>, before first paint.

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

  // Come back to the agent you picked last time: installing on a second
  // machine should not mean finding your row again.
  var last = stored("jobhunt-agent");
  if (last && buttons.some(function (b) { return b.dataset.agent === last; })) {
    show(last);
  }
  // Deep link, so the README can point straight at one: /#install?agent=codex
  var asked = (location.hash.split("agent=")[1] || "").split("&")[0];
  if (asked && buttons.some(function (b) { return b.dataset.agent === asked; })) {
    show(asked);
  }

  // --- copy ---------------------------------------------------------------

  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest(".copy") : null;
    if (!button) return;

    var label = button.querySelector("span");
    function settle(text) {
      if (label) label.textContent = text;
      setTimeout(function () {
        button.dataset.state = "";
        if (label) label.textContent = "Copy";
      }, 1900);
    }
    // Clipboard access is refused over plain http and inside some embedded
    // views. Selecting the text is the honest fallback - they press Cmd+C.
    function select() {
      var code = button.parentNode.querySelector("code");
      if (!code) return settle("Copy");
      var range = document.createRange();
      range.selectNodeContents(code);
      var selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      settle("Press Cmd+C");
    }

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(button.dataset.copy || "").then(function () {
        button.dataset.state = "copied";
        settle("Copied");
      }, select);
    } else {
      select();
    }
  });

  // --- the bar ------------------------------------------------------------

  var bar = document.querySelector(".bar");
  if (bar) {
    var stick = function () { bar.classList.toggle("stuck", window.scrollY > 8); };
    stick();
    window.addEventListener("scroll", stick, { passive: true });
  }

  // --- arrivals -----------------------------------------------------------

  var arriving = document.querySelectorAll(".up, .stagger");
  if (still || !("IntersectionObserver" in window)) {
    Array.prototype.forEach.call(arriving, function (el) { el.classList.add("in"); });
  } else {
    var watcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        watcher.unobserve(entry.target);
        if (entry.target.classList.contains("proof")) fillScore();
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.1 });
    Array.prototype.forEach.call(arriving, function (el) { watcher.observe(el); });
  }

  // --- the two numbers ----------------------------------------------------
  // They count up because the point of the pair is that one moves and one
  // does not, and watching them settle says that faster than a caption.

  var counted = false;
  function fillScore() {
    if (counted) return;
    counted = true;
    // Set directly rather than inside requestAnimationFrame. The bar starts at
    // width 0 in the stylesheet and has already been laid out, so the
    // transition runs either way - and the rAF made the state impossible to
    // observe, which is how this shipped broken twice.
    document.querySelectorAll(".score-bar").forEach(function (bar) {
      bar.querySelector("i").style.width = (bar.dataset.fill || 0) + "%";
    });
    document.querySelectorAll(".score-num").forEach(function (el) {
      var to = parseInt(el.dataset.count, 10) || 0;
      var tail = el.querySelector("small");
      var suffix = tail ? tail.outerHTML : "";
      if (still) { el.innerHTML = to + suffix; return; }
      var at = 0;
      var tick = setInterval(function () {
        at += 1;
        el.innerHTML = at + suffix;
        if (at >= to) clearInterval(tick);
      }, 520 / Math.max(to, 1));
    });
  }
  if (still) fillScore();

  // --- the rail -----------------------------------------------------------
  // One continuous fill down the steps as you scroll past them, and each badge
  // lights as the fill reaches it. Cheaper than four separate observers, and
  // it reads as one movement rather than four.

  var steps = document.querySelector(".steps");
  var rail = steps && steps.querySelector(".rail i");
  if (steps && rail && !still) {
    var badges = Array.prototype.slice.call(steps.querySelectorAll(".step"));

    // Synchronous, not throttled through requestAnimationFrame: the browser
    // already coalesces scroll events to the frame rate, and this reads five
    // rects. The rAF version bought nothing and made the state impossible to
    // observe - which is to say, impossible to test.
    var draw = function () {
      var box = steps.getBoundingClientRect();
      var middle = window.innerHeight * 0.62;
      var past = middle - box.top;
      var fraction = Math.max(0, Math.min(1, past / box.height));
      rail.style.height = (fraction * 100).toFixed(1) + "%";

      var reached = box.top + box.height * fraction;
      badges.forEach(function (step) {
        var at = step.getBoundingClientRect();
        step.classList.toggle("lit", reached >= at.top + at.height / 2);
      });
    };
    draw();
    window.addEventListener("scroll", draw, { passive: true });
    window.addEventListener("resize", draw, { passive: true });
  } else if (steps) {
    Array.prototype.forEach.call(steps.querySelectorAll(".step"), function (s) {
      s.classList.add("lit");
    });
  }
})();
