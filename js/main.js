(function () {
  "use strict";
  var root = document.documentElement;

  /* Thème clair / sombre */
  var themeBtn = document.querySelector(".theme-toggle");
  function syncThemeLabel() {
    var light = root.getAttribute("data-theme") === "light";
    themeBtn.setAttribute("aria-label", light ? "Activer le thème sombre" : "Activer le thème clair");
  }
  if (themeBtn) {
    themeBtn.hidden = false;
    syncThemeLabel();
    themeBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      syncThemeLabel();
    });
  }

  /* Menu mobile */
  var menuBtn = document.querySelector(".menu-toggle");
  var nav = document.getElementById("menu");
  var mq = window.matchMedia("(max-width: 860px)");
  function closeMenu() {
    nav.classList.remove("is-open");
    menuBtn.setAttribute("aria-expanded", "false");
  }
  function syncMenu() {
    menuBtn.hidden = !mq.matches;
    if (!mq.matches) closeMenu();
  }
  if (menuBtn && nav) {
    syncMenu();
    mq.addEventListener ? mq.addEventListener("change", syncMenu) : mq.addListener(syncMenu);
    menuBtn.addEventListener("click", function () {
      var open = menuBtn.getAttribute("aria-expanded") !== "true";
      menuBtn.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
      if (open) { var first = nav.querySelector("a"); if (first) first.focus(); }
    });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) closeMenu(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) { closeMenu(); menuBtn.focus(); }
    });
    document.addEventListener("click", function (e) {
      if (nav.classList.contains("is-open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) closeMenu();
    });
  }

  /* Bordure du header au défilement */
  var header = document.querySelector(".site-header");
  function onScroll() { header.classList.toggle("is-scrolled", window.scrollY > 8); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* Lien actif dans le menu */
  var links = Array.prototype.slice.call(document.querySelectorAll(".site-nav a[href^='#']"));
  if ("IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) {
          if (a.getAttribute("href") === "#" + entry.target.id) a.setAttribute("aria-current", "true");
          else a.removeAttribute("aria-current");
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    links.forEach(function (a) {
      var target = document.querySelector(a.getAttribute("href"));
      if (target) spy.observe(target);
    });
  }

  /* Apparition au défilement */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* Filtres des projets */
  var filterBar = document.querySelector(".filters");
  var status = document.getElementById("filter-status");
  if (filterBar) {
    filterBar.hidden = false;
    var buttons = filterBar.querySelectorAll(".filter");
    var projects = document.querySelectorAll(".project");
    filterBar.addEventListener("click", function (e) {
      var btn = e.target.closest(".filter");
      if (!btn) return;
      var f = btn.getAttribute("data-filter");
      buttons.forEach(function (b) {
        var on = b === btn;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", String(on));
      });
      var count = 0;
      projects.forEach(function (p) {
        var show = f === "all" || p.getAttribute("data-cat").split(" ").indexOf(f) !== -1;
        p.classList.toggle("is-hidden", !show);
        if (show) { count++; p.classList.add("is-visible"); }
      });
      if (status) status.textContent = count + (count > 1 ? " projets affichés" : " projet affiché");
    });
  }

  /* Copier l'e-mail */
  document.querySelectorAll(".copy-btn").forEach(function (btn) {
    if (!navigator.clipboard) return;
    btn.hidden = false;
    var label = btn.innerHTML;
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(btn.getAttribute("data-copy")).then(function () {
        btn.textContent = "Copié !";
        setTimeout(function () { btn.innerHTML = label; }, 1800);
      });
    });
  });

  /* Année du pied de page */
  var year = document.getElementById("annee");
  if (year) year.textContent = new Date().getFullYear();
})();
