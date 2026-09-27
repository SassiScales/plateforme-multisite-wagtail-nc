/* Améliorations progressives : tout fonctionne sans ce script (formulaires classiques).
   - apparition des éléments au défilement ;
   - compteurs animés sur les tuiles ;
   - filtre instantané des tableaux (le serveur reste la source : on recharge le fragment). */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function observer(els) {
    if (calme || !("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("vu"); }); return; }
    var io = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("vu"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    els.forEach(function (e) { io.observe(e); });
  }

  function compter(el) {
    var fin = parseInt(el.getAttribute("data-compte"), 10), fmt = new Intl.NumberFormat("fr-FR");
    if (calme || !fin) { el.textContent = fmt.format(fin || 0); return; }
    var t0 = null, duree = 1100;
    function pas(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / duree, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt.format(Math.round(fin * e));
      if (p < 1) requestAnimationFrame(pas);
    }
    requestAnimationFrame(pas);
  }

  function filtreInstantane(section) {
    var form = section.querySelector("[data-recherche-live]");
    if (!form) return;
    var champ = form.querySelector("input[name=q]"), minuterie = null, derniere = champ.value, controleur = null;
    champ.addEventListener("input", function () {
      clearTimeout(minuterie);
      minuterie = setTimeout(function () {
        var q = champ.value.trim();
        if (q === derniere) return;
        derniere = q;
        var url = new URL(window.location.href);
        url.searchParams.delete("p");
        if (q) url.searchParams.set("q", q); else url.searchParams.delete("q");
        var zone = section.querySelector("[data-zone]");
        zone.classList.add("charge");
        if (controleur) controleur.abort();
        controleur = new AbortController();
        fetch(url, { signal: controleur.signal, headers: { "X-Requested-With": "fetch" } })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var doc = new DOMParser().parseFromString(html, "text/html");
            var neuf = doc.getElementById(section.id);
            if (!neuf) return;
            ["[data-zone]", "[data-zone-maj]", ".tableau-compte", ".pagination"].forEach(function (sel) {
              var a = section.querySelector(sel), b = neuf.querySelector(sel);
              if (a && b) a.replaceWith(b);
              else if (a && !b) a.remove();
              else if (!a && b) section.querySelector("[data-zone]").after(b);
            });
            history.replaceState(null, "", url);
          })
          .catch(function () { /* requête annulée ou réseau : le formulaire classique reste disponible */ })
          .finally(function () { var z = section.querySelector("[data-zone]"); if (z) z.classList.remove("charge"); });
      }, 250);
    });
    form.addEventListener("submit", function (e) { e.preventDefault(); champ.dispatchEvent(new Event("input")); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    observer(Array.prototype.slice.call(document.querySelectorAll(".apparait")));
    document.querySelectorAll("[data-compte]").forEach(compter);
    document.querySelectorAll("[data-tableau]").forEach(filtreInstantane);
  });
})();

/* Itération 2 : exemples de recherche tapés, bandeau en direct, horloge de Nouméa. */
(function () {
  "use strict";
  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function exemplesTapes(input) {
    var ex = (input.getAttribute("data-exemples") || "").split("|").filter(Boolean);
    if (!ex.length || calme) return;
    var base = input.getAttribute("placeholder"), i = 0, j = 0, efface = false, timer;
    function tick() {
      if (document.activeElement === input || input.value) { input.setAttribute("placeholder", base); timer = setTimeout(tick, 1200); return; }
      var mot = ex[i];
      j += efface ? -1 : 1;
      input.setAttribute("placeholder", "Par exemple : " + mot.slice(0, j) + (efface ? "" : "▏"));
      var pause = 45;
      if (!efface && j >= mot.length) { efface = true; pause = 1700; }
      else if (efface && j <= 0) { efface = false; i = (i + 1) % ex.length; pause = 350; }
      else if (efface) { pause = 22; }
      timer = setTimeout(tick, pause);
    }
    timer = setTimeout(tick, 1400);
  }

  function bandeau(section) {
    // Défilement continu sans bouton : pause au survol, au clavier (focus) et au toucher ;
    // aucun mouvement si l'utilisateur a demandé à réduire les animations (RGAA 13.8).
    var liste = section.querySelector(".direct-liste"), rail = section.querySelector("[data-rail]");
    if (!liste || !rail) return;
    Array.prototype.slice.call(liste.children).forEach(function (li) {
      var c = li.cloneNode(true); c.setAttribute("aria-hidden", "true");
      c.querySelectorAll("a").forEach(function (a) { a.setAttribute("tabindex", "-1"); });
      liste.appendChild(c);
    });
    if (calme) { section.classList.add("en-pause"); return; }
    rail.addEventListener("touchstart", function () { section.classList.toggle("en-pause"); }, { passive: true });
  }

  function horloge(el) {
    var fmt = new Intl.DateTimeFormat("fr-FR", { timeZone: "Pacific/Noumea", weekday: "long", hour: "2-digit", minute: "2-digit" });
    function maj() { el.textContent = fmt.format(new Date()); }
    maj(); setInterval(maj, 20000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input[data-exemples]").forEach(exemplesTapes);
    document.querySelectorAll(".direct").forEach(bandeau);
    document.querySelectorAll("[data-horloge]").forEach(horloge);
  });
})();
