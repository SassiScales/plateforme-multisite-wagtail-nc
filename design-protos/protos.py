"""Trois directions d'accueil pour la démo (captures statiques, pour choisir avant de construire)."""
import os
from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
FONTS = ("<link href='https://fonts.googleapis.com/css2?family=Advent+Pro:wght@500;600;700&family=Public+Sans:wght@400;500;600;700"
         "&display=swap' rel='stylesheet'>")
# Emblème original (pas le logo officiel) : spirale de nautile + pin colonnaire stylisés.
EMBLEME = ("<svg viewBox='0 0 48 48' width='44' height='44' aria-hidden='true'><circle cx='20' cy='28' r='15' fill='none' stroke='{c1}' stroke-width='3'/>"
           "<path d='M20 28 m-9 0 a9 9 0 1 1 9 9 a5.5 5.5 0 1 1 -5.5 -5.5 a2.8 2.8 0 1 1 2.8 2.8' fill='none' stroke='{c2}' stroke-width='2.4' stroke-linecap='round'/>"
           "<path d='M38 44 L38 8 M34 14 L42 14 M33 20 L43 20 M34 26 L42 26 M33 32 L43 32 M35 38 L41 38' stroke='{c3}' stroke-width='2.2' stroke-linecap='round'/>"
           "<circle cx='38' cy='5' r='2.6' fill='#fd9827'/></svg>")
TUILES = [("Travailler dans la fonction publique", "Diplômes étrangers reconnus, concours", "294"),
          ("Importer, exporter", "Tarifs douaniers, formalités, taux", "100"),
          ("Santé et prix", "Prix des médicaments en vigueur", "3 000"),
          ("Textes et données", "Arrêtés, délibérations, jeux de données ouverts", "384")]


def entete(fond, texte, sous, c1, c2, c3, nav):
    liens = "".join(f"<a href='#' style='color:{nav};text-decoration:none;font-weight:600'>{l}</a>" for l in ["Actualités", "Travailler", "Entreprendre", "Se former", "Textes et données"])
    return (f"<header style='background:{fond};color:{texte}'><div class='c' style='display:flex;align-items:center;justify-content:space-between;padding:14px 32px'>"
            f"<div style='display:flex;gap:12px;align-items:center'>{EMBLEME.format(c1=c1, c2=c2, c3=c3)}<div><div style='font-family:Advent Pro;font-weight:700;font-size:22px;line-height:1'>gouv.nc</div>"
            f"<div style='font-size:12px;color:{sous}'>Gouvernement de la Nouvelle-Calédonie</div></div></div>"
            f"<nav style='display:flex;gap:26px;font-size:15px'>{liens}</nav></div></header>")


BASE = "<style>body{margin:0;font-family:'Public Sans',Arial} .c{max-width:1280px;margin:0 auto} h1,h2{font-family:'Advent Pro'}</style>"

A = BASE + entete("#fff", "#0b2b3c", "#4d6572", "#006699", "#3cbcdd", "#1f6b46", "#0b2b3c") + """
<div style='height:4px;background:linear-gradient(90deg,#006699 0 60%,#3cbcdd 60% 90%,#fd9827 90%)'></div>
<section style='background:#006699;color:#fff;position:relative;overflow:hidden'>
<svg viewBox='0 0 1280 380' style='position:absolute;inset:0;width:100%;height:100%' aria-hidden='true'><path d='M0 300 C200 260 380 330 640 290 C900 250 1080 320 1280 280 L1280 380 L0 380Z' fill='#0a5a86'/><path d='M0 340 C260 310 460 360 700 330 C940 300 1100 350 1280 330 L1280 380 L0 380Z' fill='#3cbcdd' opacity='.35'/>
<circle cx='1080' cy='150' r='120' fill='none' stroke='#3cbcdd' stroke-opacity='.35' stroke-width='2'/><circle cx='1080' cy='150' r='80' fill='none' stroke='#3cbcdd' stroke-opacity='.25' stroke-width='2'/><circle cx='1080' cy='150' r='44' fill='none' stroke='#fd9827' stroke-opacity='.6' stroke-width='2'/></svg>
<div class='c' style='position:relative;padding:56px 32px 110px'><h1 style='font-size:54px;margin:0 0 10px;font-weight:700'>Que cherchez-vous ?</h1>
<p style='font-size:19px;opacity:.9;margin:0 0 24px'>Les informations et les données du gouvernement, au même endroit.</p>
<div style='display:flex;max-width:720px;background:#fff;border-radius:10px;padding:6px;box-shadow:0 10px 30px rgba(0,0,0,.18)'><input style='flex:1;border:0;font-size:18px;padding:12px 14px' value='prix du paracétamol'><button style='background:#fd9827;color:#1b1b1b;border:0;border-radius:8px;padding:0 26px;font-weight:700;font-size:16px'>Rechercher</button></div>
<p style='margin-top:14px;font-size:14px;opacity:.9'>Souvent recherché : <u>offres d'emploi</u> · <u>tarifs douaniers</u> · <u>concours</u> · <u>prix des médicaments</u></p></div></section>
<section class='c' style='padding:36px 32px'><h2 style='font-size:30px;margin:0 0 18px;color:#0b2b3c'>Par besoin</h2><div style='display:grid;grid-template-columns:repeat(4,1fr);gap:18px'>""" + "".join(
    f"<a style='display:block;border:1px solid #d6e2ea;border-radius:12px;padding:20px;text-decoration:none;color:#0b2b3c'><div style='font-family:Advent Pro;font-size:34px;color:#006699;font-weight:700'>{n}</div><div style='font-weight:700;font-size:17px;margin:4px 0'>{t}</div><div style='color:#4d6572;font-size:14px'>{s}</div></a>" for t, s, n in TUILES) + "</div></section>"

B = BASE + entete("#0b2b3c", "#fff", "#a9c7d6", "#3cbcdd", "#fff", "#8fd3a8", "#e6f3f8") + """
<section style='background:#f6f1e7'><div class='c' style='display:grid;grid-template-columns:1.2fr 1fr;gap:40px;padding:56px 32px;align-items:center'>
<div><p style='color:#1f6b46;font-weight:700;letter-spacing:.08em;font-size:13px;margin:0'>NOUVELLE-CALÉDONIE</p><h1 style='font-size:56px;line-height:1.02;margin:8px 0 14px;color:#0b2b3c'>Le service public,<br>du lagon aux îles.</h1>
<p style='font-size:18px;color:#3e5561;max-width:520px'>Emplois, prix, textes et données du gouvernement, à jour et consultables en quelques secondes.</p>
<div style='display:flex;max-width:560px;border:2px solid #0b2b3c;border-radius:999px;padding:5px;background:#fff;margin-top:18px'><input style='flex:1;border:0;font-size:17px;padding:10px 16px;border-radius:999px' value='offres d’emploi'><button style='background:#0b2b3c;color:#fff;border:0;border-radius:999px;padding:0 24px;font-weight:700'>Rechercher</button></div></div>
<div style='display:grid;grid-template-columns:1fr 1fr;gap:14px'>""" + "".join(
    f"<div style='background:#fff;border-radius:16px;padding:18px;box-shadow:0 1px 0 #e7dccb'><div style='font-family:Advent Pro;font-size:36px;font-weight:700;color:{c}'>{n}</div><div style='font-size:14px;color:#3e5561'>{t}</div></div>"
    for (t, s, n), c in zip(TUILES, ["#1f6b46", "#006699", "#b86a00", "#0b2b3c"])) + """</div></div>
<svg viewBox='0 0 1280 40' style='display:block;width:100%' aria-hidden='true'><path d='M0 20 Q40 0 80 20 T160 20 T240 20 T320 20 T400 20 T480 20 T560 20 T640 20 T720 20 T800 20 T880 20 T960 20 T1040 20 T1120 20 T1200 20 T1280 20 V40 H0Z' fill='#fff'/></svg></section>
<section class='c' style='padding:26px 32px'><h2 style='font-size:28px;color:#0b2b3c;margin:0 0 14px'>Accès directs</h2><div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px'>""" + "".join(
    f"<a style='display:block;border-radius:14px;background:#f6f1e7;padding:18px;color:#0b2b3c'><div style='font-weight:700'>{t}</div><div style='font-size:14px;color:#3e5561;margin-top:4px'>{s}</div><div style='margin-top:12px;color:#1f6b46;font-weight:700'>Consulter →</div></a>" for t, s, n in TUILES) + "</div></section>"

C = BASE + entete("#fff", "#0b2b3c", "#4d6572", "#006699", "#3cbcdd", "#1f6b46", "#0b2b3c") + """
<section style='background:linear-gradient(135deg,#00374f,#006699 60%,#2aa6c8)'><div class='c' style='padding:44px 32px;color:#fff'>
<div style='display:grid;grid-template-columns:1.3fr 1fr;gap:36px;align-items:end'><div><h1 style='font-size:48px;margin:0 0 12px'>Données publiques, en direct.</h1>
<div style='display:flex;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.35);border-radius:12px;padding:6px'><input style='flex:1;background:transparent;border:0;color:#fff;font-size:18px;padding:12px' value='Chapitre 30 · produits pharmaceutiques'><button style='background:#fd9827;border:0;border-radius:8px;padding:0 24px;font-weight:700'>Rechercher</button></div></div>
<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>""" + "".join(
    f"<div style='border:1px solid rgba(255,255,255,.3);border-radius:12px;padding:14px'><div style='font-family:Advent Pro;font-size:34px;font-weight:700'>{n}</div><div style='font-size:13px;opacity:.85'>{t}</div></div>" for t, s, n in TUILES) + """</div></div></div></section>
<section class='c' style='padding:28px 32px'><div style='display:flex;justify-content:space-between;align-items:baseline'><h2 style='font-size:28px;color:#0b2b3c;margin:0'>Tarifs douaniers</h2><span style='font-size:13px;color:#4d6572'>● mis à jour il y a 2 h · data.gouv.nc</span></div>
<table style='width:100%;border-collapse:collapse;margin-top:12px;font-size:15px'><tr style='text-align:left;color:#4d6572;font-size:13px'><th style='padding:10px;border-bottom:2px solid #0b2b3c'>Chapitre</th><th style='padding:10px;border-bottom:2px solid #0b2b3c'>Libellé</th><th style='padding:10px;border-bottom:2px solid #0b2b3c'>Section</th></tr>""" + "".join(
    f"<tr><td style='padding:10px;border-bottom:1px solid #e1e8ed'><span style='background:#e3f3f8;color:#006699;border-radius:6px;padding:2px 8px;font-weight:700'>{a}</span></td><td style='padding:10px;border-bottom:1px solid #e1e8ed'>{b}</td><td style='padding:10px;border-bottom:1px solid #e1e8ed;color:#4d6572'>{c}</td></tr>"
    for a, b, c in [("30", "Produits pharmaceutiques", "VI"), ("38", "Produits divers des industries chimiques", "VI"), ("84", "Machines et appareils mécaniques", "XVI"), ("87", "Voitures automobiles, tracteurs", "XVII")]) + "</table></section>"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        for nom, corps in (("A-lagon", A), ("B-terre-et-lagon", B), ("C-donnees-en-direct", C)):
            pg.set_content(f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>{FONTS}</head><body>{corps}</body></html>", wait_until="networkidle")
            pg.screenshot(path=os.path.join(ICI, f"{nom}.png"))
            print(nom)
        b.close()


if __name__ == "__main__":
    main()
