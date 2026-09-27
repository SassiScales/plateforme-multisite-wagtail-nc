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


CORPS = [
    ("alerte", AlerteBlock()),
    ("intertitre", blocks.CharBlock(icon="title", template="home/blocs/intertitre.html", label="Titre de section")),
    ("paragraphe", blocks.RichTextBlock(features=TEXTE, icon="pilcrow", label="Paragraphe")),
    ("encadre", EncadreBlock()),
    ("tableau", TableauBlock()),
    ("carte_communes", CarteCommunesBlock()),
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
