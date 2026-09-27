"""Captures d'écran de la démo pour les mémoires (serveur lancé sur le port 8000)."""
import sys
from playwright.sync_api import sync_playwright

MDP = sys.argv[1] if len(sys.argv) > 1 else "demo-gnc-2026"
B, D = "http://gouv.localhost:8000", "http://drhfpnc.localhost:8000"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--host-resolver-rules=MAP *.localhost 127.0.0.1"])
    pg = b.new_page(viewport={"width": 1280, "height": 820}, device_scale_factor=1.5)
    shot = lambda n: pg.screenshot(path=f"captures/{n}.jpg", type="jpeg", quality=78)
    pg.goto(B + "/"); pg.wait_for_timeout(1600); shot("accueil")
    pg.goto(B + "/prix-des-medicaments/"); pg.fill("input[name=q]", "doliprane"); pg.wait_for_timeout(1500); shot("medicaments-recherche")
    pg.goto(D + "/diplomes-etrangers/"); pg.wait_for_timeout(900); shot("diplomes-drh")
    pg.click(".col-fiche a >> nth=0"); pg.wait_for_timeout(900); shot("fiche-detail")
    pg.goto(B + "/admin/login/"); shot("admin-connexion")
    pg.goto(B + "/admin/login/"); pg.fill("#id_username", "admin"); pg.fill("#id_password", MDP); pg.click("button[type=submit]")
    pg.goto(B + "/admin/pages/"); shot("admin-deux-sites")
    pg.goto(B + "/admin/snippets/tableaux/sourcedonnees/"); shot("admin-sources")
    pg.goto(B + "/admin/snippets/tableaux/sourcedonnees/"); pg.click("text=Prix des médicaments"); shot("admin-source-etat")
    b.close()
