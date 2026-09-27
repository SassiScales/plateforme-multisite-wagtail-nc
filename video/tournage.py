#!/usr/bin/env python3
"""Tournage automatique de la vidéo de démonstration, synchronisé sur la narration.

Chaque scène : sous-titre, actions à l'écran, puis attente de la fin de sa phrase (video/voix/NN-id.wav).
L'instant de départ de chaque phrase est noté, puis le montage final pose la voix et la nappe musicale
(video/musique.py, synthétisée, sans droits tiers) sous l'image, la musique baissant quand la voix parle.
Serveur de démonstration lancé sur le port 8000.
Usage : .venv-scraping/bin/python video/tournage.py [mot_de_passe]
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
MDP = sys.argv[1] if len(sys.argv) > 1 else "demo-gnc-2026"
B, D, ANCIEN = "http://gouv.localhost:8000", "http://drhfpnc.localhost:8000", "http://dittt.localhost:8000"
W, H = 1440, 900
FFMPEG = shutil.which("ffmpeg") or os.path.expanduser("~/.local/bin/ffmpeg")
PY = sys.executable
NARRATION = json.load(open(os.path.join(ICI, "narration.json")))

HABILLAGE = """
window.__habiller = () => {
  if (document.getElementById('__style_video')) return;
  const st = document.createElement('style'); st.id = '__style_video';
  st.textContent = `#__sous{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);max-width:1100px;z-index:99999;
    background:rgba(16,42,56,.92);color:#fff;font:600 22px/1.35 'Public Sans',system-ui,sans-serif;padding:14px 26px;border-radius:14px;
    box-shadow:0 10px 30px rgba(0,0,0,.3);text-align:center}
    #__sous small{display:block;font-weight:400;font-size:15px;color:#9fd7ea;margin-top:3px}
    #__curseur{position:fixed;width:22px;height:22px;border-radius:50%;background:rgba(253,152,39,.85);border:3px solid #fff;
    box-shadow:0 2px 8px rgba(0,0,0,.35);z-index:100000;pointer-events:none;transform:translate(-50%,-50%);transition:width .12s,height .12s}
    #__curseur.clic{width:34px;height:34px;background:rgba(253,152,39,.5)}`;
  document.documentElement.appendChild(st);
  const c = document.createElement('div'); c.id='__curseur'; c.style.left='-50px'; document.documentElement.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX+'px'; c.style.top = e.clientY+'px'; }, true);
  document.addEventListener('mousedown', () => c.classList.add('clic'), true);
  document.addEventListener('mouseup', () => c.classList.remove('clic'), true);
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', window.__habiller); else window.__habiller();
"""


def duree(f):
    out = subprocess.run([FFMPEG, "-i", f], capture_output=True, text=True).stderr
    h, m, s = out.split("Duration: ")[1].split(",")[0].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


VOIX = {}
for i, n in enumerate(NARRATION):
    f = os.path.join(ICI, "voix", f"{i:02d}-{n['id']}.wav")
    VOIX[n["id"]] = (f, duree(f))


class Tournage:
    def __init__(self, pg):
        self.pg, self.t0, self.pistes = pg, time.monotonic(), []

    def sous_titre(self, texte, detail=""):
        self.pg.evaluate("() => window.__habiller && window.__habiller()")
        self.pg.evaluate("""([t, d]) => { let s = document.getElementById('__sous');
          if (!s) { s = document.createElement('div'); s.id='__sous'; document.documentElement.appendChild(s); }
          s.innerHTML = t + (d ? '<small>' + d + '</small>' : ''); }""", [texte, detail])

    def scene(self, ident, texte, detail="", actions=None, marge=0.6):
        """Lance la phrase `ident`, joue les actions, attend la fin de la phrase."""
        f, d = VOIX[ident]
        debut = time.monotonic()
        self.pistes.append((f, debut - self.t0))
        if texte:
            self.sous_titre(texte, detail)
        if actions:
            actions()
        reste = d + marge - (time.monotonic() - debut)
        if reste > 0:
            self.pg.wait_for_timeout(int(reste * 1000))


def carton(pg, titre, sous):
    pg.set_content(f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>
      body{{margin:0;height:100vh;display:grid;place-items:center;background:radial-gradient(120% 90% at 70% 40%,#0a6f9e,#00496e 50%,#00293d);
      color:#fff;font-family:'Public Sans',system-ui,sans-serif;text-align:center}}
      h1{{font-size:64px;margin:0 0 18px;letter-spacing:-.01em}} p{{font-size:26px;color:#bfe6f3;margin:0;line-height:1.5}} .k{{color:#fd9827}}</style></head>
      <body><div><h1>{titre}</h1><p>{sous}</p></div></body></html>""")


def main():
    brut = os.path.join(ICI, "brut")
    shutil.rmtree(brut, ignore_errors=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--host-resolver-rules=MAP *.localhost 127.0.0.1"])
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=brut, record_video_size={"width": W, "height": H})
        ctx.add_init_script(HABILLAGE)
        pg = ctx.new_page()
        T = Tournage(pg)

        def glisser(sel, pas=18):
            box = pg.locator(sel).first.bounding_box()
            if box:
                pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=pas)

        def clic(sel, attente=900):
            glisser(sel)
            pg.wait_for_timeout(200)
            pg.locator(sel).first.click()
            pg.wait_for_timeout(attente)

        def defiler(dy, fois=1, pause=450):
            for _ in range(fois):
                pg.mouse.wheel(0, dy)
                pg.wait_for_timeout(pause)

        carton(pg, "Plateforme unique des sites du GNC", "Démonstration Sassi Scales LLC · consultation 2026-DINUM-52051")
        T.scene("intro", "")

        pg.goto(B + "/"); pg.wait_for_timeout(500); pg.mouse.move(700, 450)
        T.scene("accueil", "Un seul back-office pour tous les sites du gouvernement",
                "La carte est tracée depuis les limites des 33 communes publiées sur data.gouv.nc")
        T.scene("recherche", "La recherche propose de vrais exemples, tirés des données du site", actions=lambda: glisser("#q-lagon"))
        T.scene("direct", "En direct de data.gouv.nc : de vraies lignes, lues à la source", actions=lambda: defiler(420, 1, 700))
        T.scene("tuiles", "Chaque rubrique affiche le volume de données qu'elle tient à jour", actions=lambda: defiler(420, 2, 600))

        pg.goto(B + "/prix-des-medicaments/"); pg.wait_for_timeout(400); defiler(330, 1, 300)
        T.scene("reperes", "Des repères calculés sur 3 000 médicaments, jamais saisis à la main",
                "En moyenne +5 % en brousse et +7 % aux îles par rapport à Nouméa")

        def filtrer():
            glisser("input[name=q]")
            pg.locator("input[name=q]").first.click()
            pg.keyboard.type("doliprane", delay=140)
        T.scene("filtre", "Le tableau se filtre pendant la frappe, sans recharger la page", actions=filtrer)

        def trier():
            pg.locator("input[name=q]").first.fill("")
            pg.wait_for_timeout(700)
            clic("th .tri >> text=Îles", 1200)
            clic("th .tri >> text=Îles", 800)
        T.scene("tri", "Tri par colonne : les prix les plus élevés aux îles", actions=trier)

        pg.goto(B + "/etablissements-de-sante/"); pg.wait_for_timeout(400)
        T.scene("sante", "Mode carte : 1 239 établissements de santé sur les limites communales officielles",
                "Aucun fournisseur de fonds de carte tiers", actions=lambda: pg.locator(".carte-points").scroll_into_view_if_needed())

        def pharmacies():
            clic(".facettes a >> text=Pharmacie d'officine", 900)
            pg.locator(".carte-points").scroll_into_view_if_needed()
        T.scene("pharmacies", "Un filtre en un clic : les pharmacies", actions=pharmacies)

        def fiche():
            pg.locator(".col-fiche a").first.scroll_into_view_if_needed()
            clic(".col-fiche a", 800)
        T.scene("fiche", "Chaque ligne a sa fiche, avec sa localisation", actions=fiche)

        pg.goto(B + "/artisanat/"); pg.wait_for_timeout(400); defiler(300, 1, 300)

        def survol():
            top = pg.evaluate("[...document.querySelectorAll('.choro-carte path')].map((p,i)=>[+p.dataset.n,i]).sort((a,b)=>b[0]-a[0]).slice(0,4).map(x=>x[1])")
            for i in top:
                box = pg.locator(".choro-carte path").nth(i).bounding_box()
                if box:
                    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=22)
                pg.wait_for_timeout(900)
        T.scene("artisanat", "Carte par commune : 11 174 établissements artisanaux",
                "Légende, classement et tableau complet pour l'accessibilité", actions=survol)

        pg.goto(B + "/code-du-travail/"); pg.wait_for_timeout(400); defiler(330, 1, 300)

        def code():
            glisser("input[name=q]")
            pg.locator("input[name=q]").first.click()
            pg.keyboard.type("licenciement", delay=110)
            pg.wait_for_timeout(1400)
            clic(".col-fiche a", 600)
        T.scene("code", "Code du travail : 799 pages de PDF devenues 2 400 articles",
                "Recherche dans le texte, filtre par livre, une adresse par article", actions=code)

        pg.goto(D + "/"); pg.wait_for_timeout(500)
        T.scene("drh", "Même plateforme, autre site : drhfpnc garde son adresse et ses données")
        pg.goto(D + "/diplomes-etrangers/"); pg.wait_for_timeout(400); defiler(300, 1, 300)
        T.scene("diplomes", "Diplômes étrangers reconnus, filtrés par pays", actions=lambda: clic(".facettes a >> text=Australie", 600))

        pg.goto(ANCIEN + "/acces-et-horaires"); pg.wait_for_timeout(300)
        T.scene("migration", "Une ancienne adresse de dittt.gouv.nc arrive en une seule redirection 301 sur la page reprise",
                "60 pages reprises, 60 redirections vérifiées par un robot")

        pg.goto(B + "/admin/login/"); pg.wait_for_timeout(400)
        T.scene("connexion", "Espace contributeurs : connexion prévue par Agent Connect (UC002)")
        pg.fill("#id_username", "admin"); pg.fill("#id_password", MDP)
        clic("button[type=submit]", 1200)
        pg.goto(B + "/admin/pages/"); pg.wait_for_timeout(400)
        T.scene("backoffice", "Un back-office, plusieurs sites, des droits hérités par direction")
        pg.goto(B + "/admin/snippets/tableaux/sourcedonnees/"); pg.wait_for_timeout(400)

        def source():
            clic("text=Établissements de santé", 1000)
            defiler(420, 1, 500)
        T.scene("source", "Une source se configure sans code, en ne gardant que les champs utiles",
                "Minimisation des données (RGPD) dès la lecture", actions=source)

        carton(pg, "Le code est public", "<span class='k'>github.com/SassiScales/plateforme-multisite-wagtail-nc</span><br><br>"
                                        "Wagtail 7 · 0 violation WCAG 2.1 AA · aucun appel à un tiers")
        T.scene("fin", "", marge=2.0)
        ctx.close()
        b.close()

    webm = max(glob.glob(os.path.join(brut, "*.webm")), key=os.path.getmtime)
    total = duree(webm)
    musique = os.path.join(ICI, "brut", "musique.wav")
    subprocess.run([PY, os.path.join(ICI, "musique.py"), f"{total:.2f}", musique], check=True)

    # Montage : voix posées à leurs instants, musique baissée sous la voix (compression par la voix).
    entrees, filtres = ["-i", webm, "-i", musique], []
    for k, (f, t) in enumerate(T.pistes):
        entrees += ["-i", f]
        ms = int(max(t, 0) * 1000)
        filtres.append(f"[{k + 2}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
    n = len(T.pistes)
    filtres.append("".join(f"[v{k}]" for k in range(n)) + f"amix=inputs={n}:normalize=0,volume=1.6[voix]")
    filtres.append("[voix]asplit=2[voixa][voixb]")
    filtres.append("[1:a]volume=0.55[mus]")
    filtres.append("[mus][voixb]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=500[musb]")
    filtres.append("[voixa][musb]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    mp4 = os.path.join(ICI, "demo-plateforme-gnc.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *entrees, "-filter_complex", ";".join(filtres),
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", mp4], check=True)
    json.dump([(os.path.basename(f), round(t, 2)) for f, t in T.pistes], open(os.path.join(ICI, "brut", "chronologie.json"), "w"), indent=1)
    print(mp4, os.path.getsize(mp4) // 1024, "Ko", f"{duree(mp4):.1f} s")


if __name__ == "__main__":
    main()
