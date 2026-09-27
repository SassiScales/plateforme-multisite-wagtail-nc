"""Compteur d'audience, encart du tableau de bord et liste des liens morts dans le back-office."""
import re
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from django.template.loader import render_to_string
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import LienMort, PageVue

ROBOTS = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|headless", re.I)


@hooks.register("before_serve_page")
def compter_la_vue(page, request, serve_args, serve_kwargs):
    # Visites humaines seulement : robots d'indexation et outils automatiques ne sont pas comptés
    if request.method == "GET" and not request.GET.get("p") and not ROBOTS.search(request.headers.get("User-Agent", "")):
        PageVue.compter(page)


class LiensMortsPanneau(Component):
    order = 50

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context):
        u = self.request.user
        liens = LienMort.objects.select_related("page")
        vues = PageVue.objects.filter(jour__gte=timezone.localdate() - timedelta(days=30))
        # Le compte public de démonstration voit tout, comme un administrateur (il ne peut rien modifier).
        if not (u.is_superuser or u.groups.filter(name="Visiteurs").exists()):
            liens, vues = liens.filter(page__owner=u), vues.filter(page__owner=u)
        top = list(vues.values("page_id", "page__title").annotate(n=Sum("vues")).order_by("-n")[:6])
        return render_to_string("suivi/panneau_liens.html", {
            "liens": liens[:8], "total": liens.count(), "top": top,
            "total_vues": vues.aggregate(t=Sum("vues"))["t"] or 0})


@hooks.register("construct_homepage_panels")
def ajouter_panneau(request, panels):
    panels.append(LiensMortsPanneau(request))


class LienMortViewSet(SnippetViewSet):
    model = LienMort
    icon = "warning"
    menu_label = "Liens morts"
    add_to_admin_menu = True
    list_display = ["page", "url", "libelle", "vu_le"]
    inspect_view_enabled = True


register_snippet(LienMortViewSet)
