"""Convertit le code du travail de Nouvelle-Calédonie (PDF publié par la DTENC) en un article par ligne.

Le PDF intégral (près de 800 pages, mise à jour du 12/06/2026) porte sur chaque page un en-tête courant
(livre, « SOMMAIRE », chapitre, date de mise à jour, numéro de page). On le retire, on garde le livre et
le chapitre comme hiérarchie, puis on découpe le texte à chaque « Article Lp. … » ou « Article R. … ».
Le résultat (CSV) alimente le module de tableaux : recherche plein texte, filtre par livre, fiche par article.

Usage : manage.py convertir_code_travail code.pdf --sortie migration/code-travail.csv
"""
import csv
import re

import fitz
from django.core.management.base import BaseCommand

ARTICLE = re.compile(r"^\s*Article\s+(Lp\.?|R\.)\s*(\d+(?:-\d+)+)\s*$")
PAGE = re.compile(r"^\s*Page\s+(\d+)\s*$")


# Les en-têtes du PDF sont en capitales non accentuées, avec quelques variantes : on ramène chaque livre
# à son intitulé, en comparant sans accents ni casse.
LIVRES = ["Les relations individuelles du travail", "Les relations collectives du travail",
          "Durée du travail et santé et sécurité au travail", "L'emploi", "La formation professionnelle tout au long de la vie",
          "Contrôle de l'application de la législation du travail", "Statuts particuliers"]


def cle(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s.replace("’", "'")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s).replace("de travail", "du travail").replace("detravail", "dutravail")


INDEX_LIVRES = {cle(l): l for l in LIVRES}


def livre_canonique(s):
    k = cle(s)
    if k in INDEX_LIVRES:
        return INDEX_LIVRES[k]
    for kk, l in INDEX_LIVRES.items():
        if k.replace("de", "du", 1) == kk or k[:25] == kk[:25]:
            return l
    return s.capitalize()


def propre(s):
    return re.sub(r"\s+", " ", s).strip()


class Command(BaseCommand):
    help = "Découpe le code du travail (PDF) en articles"

    def add_arguments(self, p):
        p.add_argument("pdf")
        p.add_argument("--sortie", required=True)

    def handle(self, *a, **o):
        doc = fitz.open(o["pdf"])
        articles, courant = [], None
        for num in range(doc.page_count):
            lignes = doc[num].get_text().splitlines()
            idx = next((i for i, l in enumerate(lignes[:10]) if PAGE.match(l)), None)
            if idx is None:
                continue
            entete = [propre(l) for l in lignes[:idx] if propre(l)]
            if any("TABLE DES MATIERES" in e for e in entete):
                continue
            livre = entete[0] if entete else ""
            chapitre = entete[2] if len(entete) > 2 and entete[1] == "SOMMAIRE" else (entete[-2] if len(entete) > 1 else "")
            for l in lignes[idx + 1:]:
                m = ARTICLE.match(l)
                if m:
                    nature = "Lp." if m.group(1).lower().startswith("lp") else "R."
                    courant = {"numero": f"{nature} {m.group(2)}", "nature": "Loi du pays" if nature == "Lp." else "Partie réglementaire",
                               "livre": livre_canonique(livre), "chapitre": chapitre.capitalize(), "page": num + 1, "texte": []}
                    articles.append(courant)
                elif courant is not None:
                    courant["texte"].append(l)
        vus, sortie = set(), []
        for a_ in articles:
            texte = propre(" ".join(a_["texte"]))
            if a_["numero"] in vus or not texte:
                continue
            vus.add(a_["numero"])
            a_["texte"] = texte
            a_["extrait"] = texte[:160] + ("…" if len(texte) > 160 else "")
            sortie.append(a_)
        with open(o["sortie"], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["numero", "nature", "livre", "chapitre", "extrait", "texte", "page"], delimiter=";")
            w.writeheader()
            w.writerows(sortie)
        livres = sorted({a_["livre"] for a_ in sortie})
        self.stdout.write(f"{len(sortie)} articles, {len(livres)} livres -> {o['sortie']}")
