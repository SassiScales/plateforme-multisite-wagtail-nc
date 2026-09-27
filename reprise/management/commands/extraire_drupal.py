"""Construit un lot d'import (JSON Lines) à partir de l'inventaire d'un site Drupal.

Lit les pages HTML en 200 de l'inventaire (audit/crawl.py), respecte robots.txt et son délai,
et écrit un enregistrement par page. Reprenable : les URL déjà présentes dans le lot sont sautées.

Usage : manage.py extraire_drupal --inventaire inv_dittt.gouv.nc.sqlite --hote dittt.gouv.nc
          --sortie migration/lots/dittt.jsonl [--max 40] [--motif /node/]
"""
import json
import os
import sqlite3
import time
import urllib.robotparser

import requests
from django.core.management.base import BaseCommand

from reprise.drupal import extraire

UA = "Mozilla/5.0 (compatible; reprise-sassiscales/1.0; démonstration de migration)"


class Command(BaseCommand):
    help = "Extrait les pages publiques d'un site Drupal vers un lot d'import"

    def add_arguments(self, p):
        p.add_argument("--inventaire", required=True)
        p.add_argument("--hote", required=True)
        p.add_argument("--sortie", required=True)
        p.add_argument("--max", type=int, default=40)
        p.add_argument("--motif", default="", help="Ne garder que les URL contenant ce texte")

    def handle(self, *a, **o):
        db = sqlite3.connect(f"file:{o['inventaire']}?mode=ro", uri=True)
        urls = [r[0] for r in db.execute(
            "SELECT url FROM pages WHERE hote=? AND statut=200 AND type LIKE '%html%' AND url_finale=url ORDER BY url", (o["hote"],))]
        if o["motif"]:
            urls = [u for u in urls if o["motif"] in u]
        os.makedirs(os.path.dirname(o["sortie"]) or ".", exist_ok=True)
        deja = set()
        if os.path.exists(o["sortie"]):
            deja = {json.loads(l)["url_source"] for l in open(o["sortie"])}
        rp = urllib.robotparser.RobotFileParser(f"https://{o['hote']}/robots.txt")
        rp.read()
        delai = max(float(rp.crawl_delay(UA) or rp.crawl_delay("*") or 0), 2.0)
        faits = 0
        with open(o["sortie"], "a") as f:
            for u in urls:
                if faits >= o["max"]:
                    break
                if u in deja or not rp.can_fetch(UA, u):
                    continue
                r = requests.get(u, headers={"User-Agent": UA}, timeout=40)
                if r.status_code == 200:
                    f.write(json.dumps(extraire(u, r.text), ensure_ascii=False) + "\n")
                    faits += 1
                time.sleep(delai)
        self.stdout.write(f"{faits} page(s) extraite(s) vers {o['sortie']} (délai {delai} s)")
