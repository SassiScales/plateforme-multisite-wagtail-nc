"""Pages de la démonstration : éditeur guidé par blocs, trois gabarits, fiche détail des tableaux."""
import json

from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from tableaux.blocks import CarteCommunesBlock, TableauBlock, lisible
from tableaux import calculs
from tableaux.carte import dans_cadre, projeter
from tableaux.models import Ligne

# Mise en forme limitée (UC015) : le reste est imposé par le design system.
TEXTE = ["bold", "italic", "ol", "ul", "link"]


class AlerteBlock(blocks.StructBlock):
    """Bandeau non bloquant signalant qu'un dispositif décrit n'est plus valide (UC008)."""
    niveau = blocks.ChoiceBlock(choices=[("info", "Information"), ("attention", "Attention")], default="attention")
    message = blocks.RichTextBlock(features=TEXTE)

    class Meta:
        icon = "warning"
        template = "home/blocs/alerte.html"
        label = "Bandeau d'alerte"


class EncadreBlock(blocks.StructBlock):
    titre = blocks.CharBlock()
    texte = blocks.RichTextBlock(features=TEXTE)

    class Meta:
        icon = "doc-full"
        template = "home/blocs/encadre.html"


class FilBlock(blocks.StructBlock):
    """Liste automatique des dernières publications (actualités, pages reprises) : rien à saisir, dates réelles."""
    titre = blocks.CharBlock(default="Dernières publications")
    rubrique = blocks.PageChooserBlock(required=False, help_text="Vide : tout le site")
    nombre = blocks.IntegerBlock(default=6, min_value=3, max_value=24)

    class Meta:
        icon = "list-ul"
        template = "home/blocs/fil.html"
        label = "Fil de publications"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        page = (parent_context or {}).get("page")
        racine = value["rubrique"] or (page.get_site().root_page if page else None)
        qs = PageContenu.objects.none()
        if racine:
            qs = (PageContenu.objects.live().public().descendant_of(racine).exclude(pk=getattr(page, "pk", None))
                  .filter(first_published_at__isnull=False).order_by("-first_published_at"))
        ctx["publications"] = qs[: value["nombre"]]
        return ctx


CORPS = [
    ("alerte", AlerteBlock()),
    ("intertitre", blocks.CharBlock(icon="title", template="home/blocs/intertitre.html", label="Titre de section")),
    ("paragraphe", blocks.RichTextBlock(features=TEXTE, icon="pilcrow", label="Paragraphe")),
    ("encadre", EncadreBlock()),
    ("tableau", TableauBlock()),
    ("carte_communes", CarteCommunesBlock()),
    ("fil", FilBlock()),
]

PICTOS = [("", "Aucun"), ("douane", "Douane et commerce"), ("sante", "Santé"), ("emploi", "Emploi et concours"),
          ("actualites", "Actualités"), ("donnees", "Textes et données"),
          ("mobilite", "Mobilité"), ("artisanat", "Artisanat et entreprises"),
          ("soins", "Soins et établissements"), ("territoire", "Territoire et transports")]

GABARITS = [("standard", "Standard (colonne de lecture)"), ("large", "Large (tableaux, données)"),
            ("accueil", "Accueil de site (chapô et rubriques)")]


class PageContenu(RoutablePageMixin, Page):
    chapo = models.TextField("chapô", blank=True, help_text="Réponse courte à la question de l'usager ; reprise par les moteurs")
    gabarit = models.CharField(max_length=20, choices=GABARITS, default="standard")
    pictogramme = models.CharField(max_length=20, choices=PICTOS, blank=True, default="",
                                   help_text="Pictogramme affiché sur la tuile de la rubrique, à l'accueil")
    corps = StreamField(CORPS, blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("chapo"), FieldPanel("corps")]
    settings_panels = Page.settings_panels + [FieldPanel("gabarit"), FieldPanel("pictogramme")]
    search_fields = Page.search_fields + [index.SearchField("chapo"), index.SearchField("corps")]

    class Meta:
        verbose_name = "page de contenu"

    def get_template(self, request, *a, **k):
        return f"home/page_{self.gabarit}.html"

    def get_context(self, request, *a, **k):
        ctx = super().get_context(request, *a, **k)
        if self.gabarit != "accueil":
            from django.core.paginator import Paginator
            enfants = PageContenu.objects.live().public().child_of(self).order_by("-first_published_at", "title")
            if enfants.exists():
                ctx["sous_pages"] = Paginator(enfants, 12).get_page(request.GET.get("page"))
        return ctx

    def config_tableau(self, source_id):
        for b in self.corps:
            if b.block_type == "tableau" and b.value["source"].pk == source_id:
                return b.value
        return None

    @path("ligne/<int:source_id>/<str:identifiant>/", name="ligne")
    def ligne(self, request, source_id, identifiant):
        conf = self.config_tableau(source_id)
        if not conf:
            raise Http404
        ligne = get_object_or_404(Ligne, source_id=source_id, identifiant=identifiant)
        champs = [(c["champ"], c["libelle"] or c["champ"]) for c in conf["colonnes_detail"]] or \
            [(k, k) for k in ligne.donnees.keys()]
        position = None
        if ligne.lat is not None and ligne.lon is not None and dans_cadre(ligne.lon, ligne.lat):
            position = [round(v, 1) for v in projeter(ligne.lon, ligne.lat)]
        return TemplateResponse(request, "home/ligne_detail.html", {
            "page": self, "ligne": ligne, "conf": conf, "position": position, "communes": calculs.COMMUNES,
            "valeurs": [(lib, lisible(ligne.donnees.get(ch))) for ch, lib in champs]})

    def rubrique_pk(self):
        """Rubrique de premier niveau (sous l'accueil du site) contenant la page, pour le menu."""
        if self.depth < 3:
            return None
        return self.get_ancestors(inclusive=True).filter(depth=3).values_list("pk", flat=True).first()

    def sources(self):
        return [b.value["source"] for b in self.corps if b.block_type == "tableau"]

    def nb_donnees(self):
        """Nombre de lignes de données affichées par la page (tuiles de l'accueil)."""
        return sum(s.nb_lignes for s in self.sources())

    def json_ld(self):
        """Données structurées schema.org (UC026) : la page, et un Dataset par tableau."""
        graph = [{"@type": "WebPage", "name": self.title, "description": self.chapo,
                  "dateModified": self.last_published_at.isoformat() if self.last_published_at else None}]
        if self.depth > 3 and self.first_published_at:
            graph.append({"@type": "Article", "headline": self.title[:110], "description": self.chapo,
                          "datePublished": self.first_published_at.isoformat(),
                          "publisher": {"@type": "GovernmentOrganization", "name": "Gouvernement de la Nouvelle-Calédonie"}})
        for b in self.corps:
            if b.block_type == "tableau":
                s = b.value["source"]
                graph.append({"@type": "Dataset", "name": s.nom, "license": s.licence,
                              "dateModified": s.derniere_lecture.isoformat() if s.derniere_lecture else None})
        return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


class HomePage(PageContenu):
    """Accueil d'un site du réseau (gouv.nc, drhfpnc...) : même modèle, gabarit accueil."""

    class Meta:
        verbose_name = "accueil de site"
