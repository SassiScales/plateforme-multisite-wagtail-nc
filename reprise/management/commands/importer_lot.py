"""Interface d'import en masse (livrable du lot 1, utilisée par le lot 2).

Pour chaque enregistrement d'un lot JSON Lines (voir extraire_drupal) :
  1. décide : migrer, à arbitrer (grille service-public.nc) ou supprimer ;
  2. crée la page dans la rubrique cible, en blocs du design system, avec date d'origine et SEO ;
  3. réécrit les liens internes vers les nouvelles adresses ;
  4. pose une redirection 301 depuis l'ancienne adresse, sur l'ancien domaine conservé ;
puis rejoue tout le plan de redirection comme un robot et écrit le plan (CSV) et le rapport.

Rejouable : la rubrique cible est vidée et recréée à chaque lancement.
Usage : manage.py importer_lot migration/lots/dittt.jsonl --site gouv.localhost --ancien-domaine dittt.localhost
          --rubrique "Transports et territoires" --rapport migration/rapports/dittt
"""
import csv
from html import escape
import json
import os
import re
from datetime import datetime

import lxml.html
from django.core.management.base import BaseCommand
from django.test import Client
from django.utils.text import slugify
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Site
from wagtail.rich_text import RichText

from home.models import PageContenu

GARDER = {"p", "ul", "ol", "li", "a", "strong", "b", "em", "i", "br"}


def nettoyer(fragment, remplacer_lien):
    """HTML Drupal -> HTML accepté par l'éditeur (mise en forme du design system uniquement)."""
    el = lxml.html.fragment_fromstring(fragment, create_parent="div")
    for t in el.xpath(".//table"):
        lignes = [" · ".join(c.text_content().strip() for c in tr.xpath("./th|./td")) for tr in t.xpath(".//tr")]
        ul = lxml.html.fromstring("<ul>" + "".join(f"<li>{escape(l)}</li>" for l in lignes if l) + "</ul>")
        t.getparent().replace(t, ul)
    for x in el.iter():
        if x.tag == "a":
            href = remplacer_lien(x.get("href", ""))
            x.attrib.clear()
            if href:
                x.set("href", href)
        elif x.tag in GARDER or x is el:
            x.attrib.clear()
    for x in list(el.iter()):
        if x is not el and x.tag not in GARDER:
            x.drop_tag()
    for li in el.xpath(".//li"):
        if li.text:
            li.text = li.text.lstrip(" ·•-")
    html = "".join(lxml.html.tostring(c, encoding="unicode") for c in el) or (el.text or "")
    if el.text and el.text.strip():
        html = f"<p>{el.text.strip()}</p>" + html
    if not html.lstrip().startswith(("<p", "<ul", "<ol")):
        html = f"<p>{html}</p>"
    return html


ACCUEILS = {"/", "/accueil", "/fr", "/fr/accueil"}


def decision(rec):
    if rec["chemin_source"].rstrip("/") in {x.rstrip("/") for x in ACCUEILS}:
        return "fusionner", "ancien accueil : redirigé vers la rubrique qui reprend le site"
    if re.search(r"/(test|essai|brouillon)(/|$)", rec["chemin_source"]):
        return "supprimer", "page de test publiée par erreur (410)"
    if rec["type_drupal"] == "faq":
        return "à arbitrer", "FAQ : la grille du cadrage oriente vers service-public.nc ; migrée en attendant l'arbitrage"
    if not rec["blocs"]:
        return "à arbitrer", "aucun contenu éditorial extrait (page de liste ou d'index)"
    return "migrer", ""


class Command(BaseCommand):
    help = "Importe un lot de contenus, pose les redirections et produit le plan de redirection"

    def add_arguments(self, p):
        p.add_argument("lot")
        p.add_argument("--site", required=True, help="hôte du site cible, ex. gouv.localhost")
        p.add_argument("--ancien-domaine", required=True, help="hôte de l'ancien site conservé, ex. dittt.localhost")
        p.add_argument("--rubrique", required=True)
        p.add_argument("--rapport", required=True)
        p.add_argument("--port", type=int, default=8000)

    def handle(self, *a, **o):
        recs = [json.loads(l) for l in open(o["lot"])]
        site = Site.objects.get(hostname=o["site"])
        accueil = site.root_page.specific

        # Rubrique cible, recréée à chaque passe (reprise rejouable jusqu'à la bascule)
        slug_rub = slugify(o["rubrique"])
        for ancienne in accueil.get_children().filter(slug=slug_rub):
            ancienne.delete()
        accueil.refresh_from_db()
        rub = accueil.add_child(instance=PageContenu(
            title=o["rubrique"], slug=slug_rub, show_in_menus=True, pictogramme="donnees",
            chapo=f"Contenus repris automatiquement depuis {recs[0]['url_source'].split('/')[2] if recs else ''} : démonstration de migration du lot 2."))

        # Ancien domaine conservé : il ne sert plus que des redirections adresse par adresse
        Site.objects.filter(hostname=o["ancien_domaine"]).delete()
        ancien = Site.objects.create(hostname=o["ancien_domaine"], port=o["port"], root_page=accueil,
                                     site_name=f"{o['ancien_domaine']} (ancien site, redirections)")

        # Passe 1 : décisions et correspondance des adresses
        plan, a_creer, slugs = [], [], set()
        for r in recs:
            d, motif = decision(r)
            s = slugify(r["titre"])[:70] or "page"
            base, k = s, 2
            while s in slugs:
                s, k = f"{base}-{k}", k + 1
            slugs.add(s)
            r["_slug"], r["_decision"], r["_motif"] = s, d, motif
            if d not in ("supprimer", "fusionner"):
                a_creer.append(r)
        hote_src = recs[0]["url_source"].split("/")[2] if recs else ""
        base_rub = rub.relative_url(site)
        nouveau = {r["url_source"]: f"{base_rub}{r['_slug']}/" for r in a_creer}
        nouveau.update({r["url_source"]: base_rub for r in recs if r["_decision"] == "fusionner"})

        def remplacer_lien(href):
            if href in nouveau:
                return nouveau[href]
            return href

        # Passe 2 : création des pages
        controles = []
        for r in a_creer:
            corps, vus, doublons = [], [], 0
            for b in r["blocs"]:
                txt = re.sub(r"\s+", " ", lxml.html.fromstring(b["html"]).text_content() if b["type"] != "intertitre" else b["texte"]).strip(" ·")
                if txt and any(txt in v for v in vus):
                    doublons += 1          # même texte déjà repris plus haut (bloc visuel + texte dans Drupal)
                    continue
                vus.append(txt)
                if b["type"] == "intertitre":
                    corps.append(("intertitre", b["texte"][:250]))
                else:
                    corps.append(("paragraphe", RichText(nettoyer(b["html"], remplacer_lien))))
            p = PageContenu(title=r["titre"][:255] or "Sans titre", slug=r["_slug"], corps=corps,
                            chapo=r["description"][:500], search_description=r["description"][:300])
            rub.add_child(instance=p)
            if r["publie_le"]:
                p.first_published_at = datetime.fromisoformat(r["publie_le"])
                p.save(update_fields=["first_published_at"])
            Redirect.objects.create(old_path=Redirect.normalise_path(r["chemin_source"]), site=ancien,
                                    redirect_page=p, is_permanent=True)
            pb = []
            if not r["titre"]:
                pb.append("titre manquant")
            if not r["blocs"]:
                pb.append("aucun contenu extrait")
            sans_alt = sum(1 for i in r["images"] if not i["alt"])
            if sans_alt:
                pb.append(f"{sans_alt} image(s) sans alternative")
            if not r["description"]:
                pb.append("meta description absente")
            if doublons:
                pb.append(f"{doublons} bloc(s) en double retiré(s)")
            controles.append((r["url_source"], p.relative_url(site), "; ".join(pb)))

        for r in recs:
            if r["_decision"] == "fusionner":
                Redirect.objects.create(old_path=Redirect.normalise_path(r["chemin_source"]), site=ancien,
                                        redirect_page=rub, is_permanent=True)

        # Passe 3 : le robot rejoue le plan sur l'ancien domaine
        c = Client()
        hote = f"{o['ancien_domaine']}:{o['port']}"
        for r in recs:
            ancienne = r["url_source"]
            if r["_decision"] == "supprimer":
                plan.append([ancienne, "", r["_decision"], "410", "à poser au niveau du serveur", r["_motif"]])
                continue
            rep = c.get(r["chemin_source"], HTTP_HOST=hote)
            cible = rep.headers.get("Location", "")
            ok = rep.status_code == 301 and cible.rstrip("/").endswith(nouveau[ancienne].rstrip("/"))
            fin = c.get(nouveau[ancienne], HTTP_HOST=f"{o['site']}:{o['port']}").status_code if ok else 0
            plan.append([ancienne, f"http://{o['site']}:{o['port']}{nouveau[ancienne]}", r["_decision"],
                         str(rep.status_code), "OK en une étape" if ok and fin == 200 else f"ÉCHEC ({rep.status_code} -> {fin})", r["_motif"]])

        os.makedirs(o["rapport"], exist_ok=True)
        with open(os.path.join(o["rapport"], "plan_redirection.csv"), "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["ancienne adresse", "nouvelle adresse", "décision", "code HTTP", "test", "motif"])
            w.writerows(plan)
        with open(os.path.join(o["rapport"], "controles.csv"), "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["ancienne adresse", "nouvelle page", "points à corriger"])
            w.writerows(controles)
        ok = sum(1 for p in plan if p[4] == "OK en une étape")
        stats = {"pages_lot": len(recs), "importees": len(a_creer), "supprimees": sum(1 for r in recs if r["_decision"] == "supprimer"),
                 "fusionnees": sum(1 for r in recs if r["_decision"] == "fusionner"),
                 "a_arbitrer": sum(1 for r in recs if r["_decision"] == "à arbitrer"),
                 "redirections_testees_ok": ok, "redirections_attendues": sum(1 for r in recs if r["_decision"] != "supprimer"),
                 "pages_avec_points": sum(1 for x in controles if x[2]),
                 "blocs": sum(len(r["blocs"]) for r in a_creer), "documents_lies": sum(len(r["documents"]) for r in a_creer)}
        json.dump(stats, open(os.path.join(o["rapport"], "bilan.json"), "w"), ensure_ascii=False, indent=1)
        self.stdout.write(json.dumps(stats, ensure_ascii=False))
