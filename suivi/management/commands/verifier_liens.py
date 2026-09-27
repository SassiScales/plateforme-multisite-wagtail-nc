"""Contrôle des liens de toutes les pages publiées (UC023), à planifier chaque semaine.

Liens internes : vérifiés par la plateforme elle-même (sans réseau). Liens externes : requête HEAD
(repli GET), une seconde entre deux requêtes vers un même domaine. Les liens cassés sont enregistrés
et remontent dans le tableau de bord du contributeur propriétaire de la page.
"""
import re
import time
import urllib.parse

import requests
from django.core.management.base import BaseCommand
from django.test import Client
from wagtail.models import Site

from home.models import PageContenu
from suivi.models import LienMort

HREF = re.compile(r'href="([^"]+)"')
UA = "Mozilla/5.0 (compatible; controle-liens-plateforme-gnc/1.0)"


def liens(page):
    out = set()
    for b in page.corps:
        v = b.value
        textes = []
        if b.block_type == "paragraphe":
            textes.append(v.source)
        elif b.block_type in ("encadre",):
            textes.append(v["texte"].source)
        elif b.block_type == "alerte":
            textes.append(v["message"].source)
        for t in textes:
            out.update(HREF.findall(t))
    return {l for l in out if not l.startswith(("mailto:", "tel:", "#"))}


class Command(BaseCommand):
    help = "Détecte les liens morts dans les pages publiées"

    def handle(self, *a, **o):
        LienMort.objects.all().delete()
        client, derniers, nb, morts = Client(), {}, 0, 0
        hotes = {f"{s.hostname}:{s.port}": s for s in Site.objects.all()}
        for p in PageContenu.objects.live().specific():
            site = p.get_site()
            for l in sorted(liens(p)):
                nb += 1
                u = urllib.parse.urlsplit(l)
                interne = not u.netloc or f"{u.hostname}:{u.port or 80}" in hotes
                try:
                    if interne:
                        chemin = u.path or "/"
                        statut = client.get(chemin, HTTP_HOST=f"{site.hostname}:{site.port}", follow=True).status_code
                    else:
                        attente = 1 - (time.time() - derniers.get(u.netloc, 0))
                        if attente > 0:
                            time.sleep(attente)
                        r = requests.head(l, allow_redirects=True, timeout=12, headers={"User-Agent": UA})
                        if r.status_code in (403, 405):
                            r = requests.get(l, allow_redirects=True, timeout=12, headers={"User-Agent": UA}, stream=True)
                        derniers[u.netloc] = time.time()
                        statut = r.status_code
                except requests.RequestException as e:
                    statut = type(e).__name__
                if not (isinstance(statut, int) and statut < 400):
                    LienMort.objects.create(page=p, url=l if u.netloc else f"http://{site.hostname}:{site.port}{l}", statut=str(statut))
                    morts += 1
        self.stdout.write(f"{nb} liens contrôlés, {morts} liens morts")
