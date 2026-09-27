"""Balises de l'accueil : lignes « en direct », sites du réseau."""
import random

from django import template
from wagtail.models import Site

from home.models import PageContenu
from tableaux.blocks import lisible

register = template.Library()

# Sites de direction annoncés au § 3.2.a du cahier des charges (extension après le MVP).
A_VENIR = ["denc", "dass", "davar", "dimenc", "sap", "djs", "sécurité civile", "dam", "archives", "dgrac", "numérique", "dbaf"]


@register.simple_tag(takes_context=True)
def lignes_en_direct(context, n=16):
    """Échantillon de vraies lignes des tableaux du site courant, avec la page qui les affiche."""
    site = Site.find_for_request(context["request"])
    if not site:
        return []
    sorties = []
    for p in PageContenu.objects.live().descendant_of(site.root_page).specific():
        for b in p.corps:
            if b.block_type != "tableau":
                continue
            cols = [c["champ"] for c in b.value["colonnes"]]
            src = b.value["source"]
            ids = list(src.lignes.values_list("pk", flat=True)[:400])
            for l in src.lignes.filter(pk__in=random.sample(ids, min(len(ids), n // 2 + 2))):
                vals = [str(lisible(l.donnees.get(c)) or "").strip() for c in cols]
                vals = [v for v in vals if v][:2]
                sorties.append({"texte": " · ".join(vals), "rubrique": p.title, "url": p.url})
    random.shuffle(sorties)
    return sorties[:n]


@register.simple_tag
def sites_reseau():
    return {"actifs": Site.objects.order_by("-is_default_site", "site_name"), "a_venir": A_VENIR}


@register.simple_tag(takes_context=True)
def exemples_recherche(context, n=5):
    """Exemples tapés dans la recherche de l'accueil, tirés des données du site courant (jamais inventés).

    Une rubrique après l'autre, en privilégiant les libellés courts, pour montrer l'étendue du site.
    """
    par_rub = {}
    for d in lignes_en_direct(context, 60):
        v = next((x.strip() for x in d["texte"].split(" · ") if sum(ch.isalpha() for ch in x) > 3), "")
        if 3 < len(v) <= 36 and "inutilis" not in v.lower():
            par_rub.setdefault(d["rubrique"], set()).add(v.capitalize() if v.isupper() else v)
    files = [sorted(vs, key=len) for vs in par_rub.values()]
    sortie = []
    while files and len(sortie) < n:
        for f in list(files):
            if f:
                sortie.append(f.pop(0))
            else:
                files.remove(f)
            if len(sortie) >= n:
                break
    return "|".join(sortie)
