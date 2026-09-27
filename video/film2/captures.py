#!/usr/bin/env python3
"""Captures haute définition (2×) des états de la maquette, matière première du film produit.

Serveur de démonstration lancé sur le port 8000. Toutes les images sont de vraies pages de la maquette.
Usage : .venv-scraping/bin/python video/film2/captures.py [mot_de_passe]
"""
import os
import sys

from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ICI, "plans")
MDP = sys.argv[1] if len(sys.argv) > 1 else "demo-gnc-2026"
B, D, A = "http://gouv.localhost:8000", "http://drhfpnc.localhost:8000", "http://dittt.localhost:8000"
CACHE = "document.querySelectorAll('.bandeau-demo').forEach(e=>e.remove()); document.querySelectorAll('.apparait').forEach(e=>e.classList.add('vu'));"


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--host-resolver-rules=MAP *.localhost 127.0.0.1"])
        pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2, reduced_motion="reduce")

        def shot(nom, plein=False):
            pg.evaluate(CACHE)
            pg.wait_for_timeout(250)
            pg.screenshot(path=os.path.join(OUT, nom + ".jpg"), type="jpeg", quality=90, full_page=plein)

        def aller(u, attente=900):
            pg.goto(u)
            pg.wait_for_timeout(attente)

        # 2. deux sites
        aller(B + "/"); shot("gouv-accueil")
        aller(D + "/"); shot("drh-accueil")
        # 3. recherche : saisie lettre par lettre (accueil), puis résultats
        aller(B + "/")
        mot = "doliprane"
        for i in range(len(mot) + 1):
            pg.fill("#q-lagon", mot[:i]); shot(f"rech-{i:02d}")
        aller(B + "/search/?query=doliprane"); shot("rech-resultats")
        # 4. tableaux : repères, filtre lettre par lettre, tri
        aller(B + "/prix-des-medicaments/"); pg.evaluate("window.scrollTo(0, 330)"); shot("medic-reperes")
        for i in range(len(mot) + 1):
            pg.goto(B + "/prix-des-medicaments/?q=" + mot[:i]); pg.wait_for_timeout(300)
            pg.evaluate("window.scrollTo(0, 330)"); shot(f"medic-filtre-{i:02d}")
        aller(B + "/prix-des-medicaments/?tri=prix_iles&ordre=desc"); pg.evaluate("window.scrollTo(0, 560)"); shot("medic-tri")
        # 5. cartes : santé, filtre pharmacies, fiche
        aller(B + "/etablissements-de-sante/", 1500); pg.locator(".facettes").scroll_into_view_if_needed(); shot("sante-haut")
        pg.locator(".carte-points").scroll_into_view_if_needed(); pg.wait_for_timeout(600); shot("sante-carte")
        aller(B + "/etablissements-de-sante/?f=Pharmacie%20d%27officine", 1500); pg.locator(".facettes").scroll_into_view_if_needed(); shot("sante-pharmacies")
        pg.locator(".col-fiche a").first.click(); pg.wait_for_timeout(900); shot("sante-fiche")
        # 6. artisanat
        aller(B + "/artisanat/"); pg.evaluate("window.scrollTo(0, 300)"); shot("artisanat")
        # 7. code du travail
        aller(B + "/code-du-travail/"); pg.evaluate("window.scrollTo(0, 330)"); shot("code")
        aller(B + "/code-du-travail/?q=licenciement"); pg.evaluate("window.scrollTo(0, 330)"); shot("code-licenciement")
        pg.locator(".col-fiche a").first.click(); pg.wait_for_timeout(700); shot("code-article")
        # 8. migration
        aller(A + "/acces-et-horaires"); shot("migration-arrivee")
        # 9. confiance : connexion, back-office, source, alerte
        aller(B + "/admin/login/"); shot("admin-connexion")
        pg.fill("#id_username", "admin"); pg.fill("#id_password", MDP); pg.click("button[type=submit]"); pg.wait_for_timeout(1200)
        aller(B + "/admin/pages/"); shot("admin-arbre")
        aller(B + "/admin/snippets/tableaux/sourcedonnees/"); pg.click("text=Établissements de santé"); pg.wait_for_timeout(900)
        pg.locator("text=Données gardées et carte").first.scroll_into_view_if_needed()
        pg.evaluate("window.scrollBy(0, -140)"); pg.wait_for_timeout(300); shot("admin-source")
        aller(B + "/prix-des-medicaments/"); pg.locator(".tableau-alerte").scroll_into_view_if_needed(); shot("alerte")
        b.close()
    print(len(os.listdir(OUT)), "plans")


if __name__ == "__main__":
    main()
