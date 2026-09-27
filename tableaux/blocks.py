"""Bloc StreamField « Tableau de données » : configuration sans code, page par page."""
from django.core.paginator import Paginator
from django.db.models import Q
from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock


def lisible(v):
    """Valeur affichable : les listes deviennent un texte séparé par des points-virgules."""
    if isinstance(v, list):
        return " ; ".join(str(x) for x in v)
    if isinstance(v, dict):
        return " ; ".join(f"{k} : {x}" for k, x in v.items())
    return v


class ColonneBlock(blocks.StructBlock):
    champ = blocks.CharBlock(help_text="Nom du champ de la source (voir « État de la source »)")
    libelle = blocks.CharBlock(required=False, help_text="Intitulé affiché ; vide = nom du champ")

    class Meta:
        icon = "list-ul"


class TableauBlock(blocks.StructBlock):
    source = SnippetChooserBlock("tableaux.SourceDonnees")
    titre = blocks.CharBlock(required=False)
    colonnes = blocks.ListBlock(ColonneBlock(), label="Colonnes de la liste", min_num=1)
    colonnes_detail = blocks.ListBlock(ColonneBlock(), label="Champs de la fiche détail", required=False,
                                       help_text="Vide : tous les champs de la ligne")
    recherche = blocks.BooleanBlock(required=False, default=True, label="Champ de recherche")
    par_page = blocks.IntegerBlock(default=25, min_value=5, max_value=200, label="Lignes par page")
    abonnement = blocks.BooleanBlock(required=False, default=False, label="Proposer l'alerte e-mail")

    class Meta:
        icon = "table"
        template = "tableaux/bloc_tableau.html"
        label = "Tableau de données"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        request = (parent_context or {}).get("request")
        source = value["source"]
        q = (request.GET.get("q", "") if request else "").strip()
        lignes = source.lignes.all()
        if q:
            cond = Q()
            for mot in q.split():
                cond &= Q(texte__icontains=mot)
            lignes = lignes.filter(cond)
        page = Paginator(lignes, value["par_page"]).get_page(request.GET.get("p") if request else 1)
        cols = [(c["champ"], c["libelle"] or c["champ"]) for c in value["colonnes"]]
        ctx.update({
            "source": source, "q": q, "page_lignes": page, "colonnes": cols,
            "rangees": [(l, [lisible(l.donnees.get(ch)) for ch, _ in cols]) for l in page.object_list],
            "page": (parent_context or {}).get("page"),
        })
        return ctx
