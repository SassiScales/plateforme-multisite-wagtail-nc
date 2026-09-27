"""Module « tableaux de données » pour Wagtail.

Une SourceDonnees décrit d'où viennent les lignes (API Opendatasoft comme
data.gouv.nc, API REST JSON, ou fichier CSV déposé). La commande
`lire_sources` les lit, les met en cache (modèle Ligne) et les indexe pour la
recherche du site. Le contributeur affiche une source dans n'importe quelle page
avec le bloc TableauBlock, en choisissant les colonnes de la liste et de la
fiche détail, sans code.
"""
import csv
import hashlib
import io
import json

import requests
from django.db import models, transaction
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, HelpPanel, MultiFieldPanel
from wagtail.search import index
from wagtail.snippets.models import register_snippet

TIMEOUT = 30
MAX_LIGNES_DEFAUT = 5000


class SourceDonnees(index.Indexed, models.Model):
    TYPES = [
        ("opendatasoft", "API Opendatasoft (data.gouv.nc)"),
        ("rest", "API REST JSON"),
        ("csv", "Fichier CSV (adresse ou document déposé)"),
    ]
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default="opendatasoft")
    url_base = models.URLField(
        "adresse", help_text="Opendatasoft : https://data.gouv.nc ; REST : adresse complète de l'API ; CSV : adresse du fichier")
    jeu = models.CharField("identifiant du jeu de données", max_length=200, blank=True,
                           help_text="Opendatasoft uniquement, par exemple sempex_prix_medicaments_en_vigueur")
    filtre = models.CharField("filtre à la lecture (Opendatasoft)", max_length=300, blank=True,
                              help_text="Clause ODSQL « where », ex. prix_cfp is not null")
    chemin_liste = models.CharField("chemin de la liste (REST)", max_length=200, blank=True,
                                    help_text="Clés séparées par des points menant à la liste de lignes, ex. data.items")
    cle = models.CharField("champ identifiant", max_length=100, blank=True,
                           help_text="Champ unique d'une ligne ; sert aux alertes « nouvelle ligne ». Vide : empreinte de la ligne.")
    max_lignes = models.PositiveIntegerField(default=MAX_LIGNES_DEFAUT)
    frequence_heures = models.PositiveIntegerField("fréquence de lecture (heures)", default=24)
    licence = models.CharField(max_length=200, blank=True, default="Licence ouverte")
    champs = models.JSONField(default=list, blank=True, editable=False)
    derniere_lecture = models.DateTimeField(null=True, blank=True, editable=False)
    derniere_erreur = models.TextField(blank=True, editable=False)
    nb_lignes = models.PositiveIntegerField(default=0, editable=False)

    panels = [
        MultiFieldPanel([FieldPanel("nom"), FieldPanel("type"), FieldPanel("url_base"), FieldPanel("jeu"),
                         FieldPanel("filtre"), FieldPanel("chemin_liste")], heading="Origine des données"),
        MultiFieldPanel([FieldPanel("cle"), FieldPanel("max_lignes"), FieldPanel("frequence_heures"),
                         FieldPanel("licence")], heading="Lecture"),
        HelpPanel(template="tableaux/panneau_etat.html", heading="État de la source"),
    ]
    search_fields = [index.SearchField("nom")]

    class Meta:
        verbose_name = "source de données"
        verbose_name_plural = "sources de données"

    def __str__(self):
        return self.nom

    # ------------------------------------------------------------ lecture
    def _opendatasoft(self):
        base = self.url_base.rstrip("/")
        url = f"{base}/api/explore/v2.1/catalog/datasets/{self.jeu}/exports/json"
        params = {"limit": self.max_lignes}
        if self.filtre:
            params["where"] = self.filtre
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _rest(self):
        r = requests.get(self.url_base, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for k in filter(None, self.chemin_liste.split(".")):
            data = data[k]
        return data

    def _csv(self):
        r = requests.get(self.url_base, timeout=TIMEOUT)
        r.raise_for_status()
        texte = r.content.decode("utf-8-sig", "replace")
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters=",;\t")
        return list(csv.DictReader(io.StringIO(texte), dialect=dialecte))

    def lire(self):
        """Lit la source, remplace le cache, renvoie les identifiants des lignes nouvelles.

        En cas d'échec, le cache précédent est conservé (le site continue d'afficher
        la dernière version valide) et l'erreur est notée sur la source.
        """
        try:
            lignes = {"opendatasoft": self._opendatasoft, "rest": self._rest, "csv": self._csv}[self.type]()
            if not isinstance(lignes, list):
                raise ValueError("la source ne renvoie pas une liste de lignes")
            lignes = [l for l in lignes if isinstance(l, dict)][: self.max_lignes]
        except Exception as e:  # noqa: BLE001 - toute panne de source est rapportée, jamais propagée au site
            self.derniere_erreur = f"{timezone.now():%d/%m/%Y %H:%M} : {e}"[:2000]
            self.save(update_fields=["derniere_erreur"])
            return []

        anciennes = set(self.lignes.values_list("identifiant", flat=True))
        champs = list(dict.fromkeys(k for l in lignes for k in l.keys()))
        objets = []
        for i, l in enumerate(lignes):
            ident = str(l.get(self.cle)) if self.cle and l.get(self.cle) is not None else \
                hashlib.sha1(json.dumps(l, sort_keys=True, default=str).encode()).hexdigest()[:16]
            texte = " ".join(str(v) for v in l.values() if v not in (None, ""))[:4000]
            objets.append(Ligne(source=self, rang=i, identifiant=ident, donnees=l, texte=texte))
        with transaction.atomic():
            self.lignes.all().delete()
            Ligne.objects.bulk_create(objets, batch_size=1000)
            self.champs, self.nb_lignes = champs, len(objets)
            self.derniere_lecture, self.derniere_erreur = timezone.now(), ""
            self.save(update_fields=["champs", "nb_lignes", "derniere_lecture", "derniere_erreur"])
        # Réindexation : sans elle, la recherche du site (UC022) ignorerait les lignes relues.
        from wagtail.search.backends import get_search_backend
        get_search_backend().add_bulk(Ligne, list(self.lignes.all()))
        nouvelles = [o.identifiant for o in objets if o.identifiant not in anciennes]
        return nouvelles if anciennes else []

    def a_relire(self):
        if not self.derniere_lecture:
            return True
        return (timezone.now() - self.derniere_lecture).total_seconds() >= self.frequence_heures * 3600


register_snippet(SourceDonnees)


class Ligne(index.Indexed, models.Model):
    """Une ligne en cache ; indexée pour la recherche plein texte du site (UC022)."""
    source = models.ForeignKey(SourceDonnees, on_delete=models.CASCADE, related_name="lignes")
    rang = models.PositiveIntegerField()
    identifiant = models.CharField(max_length=200, db_index=True)
    donnees = models.JSONField()
    texte = models.TextField(blank=True)

    search_fields = [index.SearchField("texte"), index.FilterField("source_id")]

    class Meta:
        ordering = ["rang"]
        indexes = [models.Index(fields=["source", "rang"])]

    def __str__(self):
        return f"{self.source} #{self.rang}"


class Abonnement(models.Model):
    """Alerte e-mail sur les nouvelles lignes d'une source, filtrées par un texte (UC024)."""
    source = models.ForeignKey(SourceDonnees, on_delete=models.CASCADE, related_name="abonnements")
    email = models.EmailField()
    filtre = models.CharField(max_length=200, blank=True, help_text="Mot à trouver dans la ligne ; vide = toutes")
    jeton = models.CharField(max_length=40, unique=True, editable=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("source", "email", "filtre")]

    def save(self, *a, **k):
        if not self.jeton:
            self.jeton = hashlib.sha1(f"{self.email}{self.source_id}{self.filtre}{timezone.now()}".encode()).hexdigest()
        super().save(*a, **k)
