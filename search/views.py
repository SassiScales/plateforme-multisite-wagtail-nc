"""Recherche du site : pages du site courant ET lignes des tableaux de données (UC018, UC022)."""
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from wagtail.models import Page, Site
from wagtail.search.backends import get_search_backend

from home.models import PageContenu
from tableaux.blocks import lisible
from tableaux.models import Ligne


def pages_par_source(site):
    """source_id -> page du site courant qui affiche cette source dans un tableau."""
    carte = {}
    for p in PageContenu.objects.live().descendant_of(site.root_page, inclusive=True).specific():
        for b in p.corps:
            if b.block_type == "tableau":
                carte.setdefault(b.value["source"].pk, (p, b.value))
    return carte


def search(request):
    q = (request.GET.get("query") or "").strip()
    site = Site.find_for_request(request)
    pages, lignes = [], []
    if q and site:
        pages = Page.objects.live().descendant_of(site.root_page, inclusive=True).search(q)
        carte = pages_par_source(site)
        for l in get_search_backend().search(q, Ligne.objects.filter(source_id__in=carte.keys()))[:60]:
            page, conf = carte[l.source_id]
            cols = [c["champ"] for c in conf["colonnes"]][:3]
            lignes.append({"ligne": l, "page": page, "resume": " · ".join(str(lisible(l.donnees.get(c)) or "") for c in cols)})
    resultats = Paginator(list(pages), 10).get_page(request.GET.get("page", 1))
    return TemplateResponse(request, "search/search.html", {
        "search_query": q, "search_results": resultats, "lignes": lignes, "nb_lignes": len(lignes)})
