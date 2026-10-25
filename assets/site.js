/* Bästa IPTV HD: theme toggle, statistics consent, pricing ruler reveal. No dependencies. */
(function () {
  var root = document.documentElement;
  function store(k, v) { try { v === undefined ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  // light / dark: follows the OS until the visitor picks one
  var toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) toggle.addEventListener("click", function () {
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    store("theme", root.dataset.theme);
  });

  // statistics only load after "Godkänn"; declining is the default
  function loadStats() {
    var s = document.createElement("script");
    s.src = "https://admin-hub.eddinesalah2007.workers.dev/track.js";
    s.setAttribute("data-site", "bastaiptvhd");
    document.body.appendChild(s);
  }
  var box = document.querySelector("[data-consent]");
  var choice = read("stats-consent");
  if (choice === "yes") loadStats();
  else if (choice !== "no" && box) box.hidden = false;
  if (box) box.addEventListener("click", function (e) {
    var b = e.target.closest("[data-consent-choice]");
    if (!b) return;
    store("stats-consent", b.dataset.consentChoice);
    box.hidden = true;
    if (b.dataset.consentChoice === "yes") loadStats();
  });
  var reset = document.querySelector("[data-consent-reset]");
  if (reset) reset.addEventListener("click", function () { store("stats-consent"); if (box) box.hidden = false; });

  // grow the pricing bars when the ruler scrolls into view
  var ruler = document.querySelector("[data-ruler]");
  if (ruler) {
    if (!("IntersectionObserver" in window)) ruler.classList.add("in");
    else new IntersectionObserver(function (e, o) {
      if (e[0].isIntersecting) { ruler.classList.add("in"); o.disconnect(); }
    }, { threshold: 0.3 }).observe(ruler);
  }
})();
