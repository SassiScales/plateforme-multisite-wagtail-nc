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
import re

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
        ("page_html", "Tableaux d'une page web (connecteur transitoire)"),
    ]
    SCHEMAS = [("", "Aucun"), ("JobPosting", "Offre d'emploi (JobPosting)")]
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default="opendatasoft")
    document = models.ForeignKey("wagtaildocs.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                 help_text="CSV : fichier déposé dans la médiathèque (prioritaire sur l'adresse)")
    url_base = models.URLField(
        "adresse", blank=True, help_text="Opendatasoft : https://data.gouv.nc ; REST : adresse complète de l'API ; CSV : adresse du fichier")
    jeu = models.CharField("identifiant du jeu de données", max_length=200, blank=True,
                           help_text="Opendatasoft uniquement, par exemple sempex_prix_medicaments_en_vigueur")
    filtre = models.CharField("filtre à la lecture (Opendatasoft)", max_length=300, blank=True,
                              help_text="Clause ODSQL « where », ex. prix_cfp is not null")
    chemin_liste = models.CharField("chemin de la liste (REST) ou modèle de lien (page web)", max_length=200, blank=True,
                                    help_text="REST : clés séparées par des points menant à la liste, ex. data.items. "
                                              "Page web : lien de chaque ligne, avec ses attributs data-, ex. /avis/download/{pdf}")
    champs_conserves = models.CharField(
        "champs conservés", max_length=500, blank=True,
        help_text="Minimisation (RGPD) : liste des champs gardés, séparés par des virgules ; les autres ne sont ni stockés ni indexés. Vide : tous.")
    champ_geo = models.CharField(
        "champ de localisation", max_length=120, blank=True,
        help_text="Pour la carte : champ point {lon, lat} (ex. geo_point_2d) ou deux champs « latitude,longitude »")
    cle = models.CharField("champ identifiant", max_length=100, blank=True,
                           help_text="Champ unique d'une ligne ; sert aux alertes « nouvelle ligne ». Vide : empreinte de la ligne.")
    max_lignes = models.PositiveIntegerField(default=MAX_LIGNES_DEFAUT)
    frequence_heures = models.PositiveIntegerField("fréquence de lecture (heures)", default=24)
    licence = models.CharField(max_length=200, blank=True, default="Licence ouverte")
    schema_ligne = models.CharField("données structurées de la fiche", max_length=40, blank=True, default="", choices=SCHEMAS,
                                    help_text="Type schema.org publié sur chaque fiche (moteurs de recherche, assistants IA)")
    correspondance_schema = models.CharField(
        "correspondance des champs", max_length=400, blank=True,
        help_text="propriété=champ, séparés par des virgules, ex. title=poste,hiringOrganization=employeur,validThrough=cloture")
    champs = models.JSONField(default=list, blank=True, editable=False)
    derniere_lecture = models.DateTimeField(null=True, blank=True, editable=False)
    derniere_erreur = models.TextField(blank=True, editable=False)
    nb_lignes = models.PositiveIntegerField(default=0, editable=False)

    panels = [
        MultiFieldPanel([FieldPanel("nom"), FieldPanel("type"), FieldPanel("url_base"), FieldPanel("document"), FieldPanel("jeu"),
                         FieldPanel("filtre"), FieldPanel("chemin_liste")], heading="Origine des données"),
        MultiFieldPanel([FieldPanel("champs_conserves"), FieldPanel("champ_geo")], heading="Données gardées et carte"),
        MultiFieldPanel([FieldPanel("cle"), FieldPanel("max_lignes"), FieldPanel("frequence_heures"),
                         FieldPanel("licence")], heading="Lecture"),
        MultiFieldPanel([FieldPanel("schema_ligne"), FieldPanel("correspondance_schema")], heading="Référencement des fiches"),
        HelpPanel(template="tableaux/panneau_etat.html", heading="État de la source"),
    ]
    search_fields = [index.SearchField("nom")]

    class Meta:
        verbose_name = "source de données"
        verbose_name_plural = "sources de données"

    def __str__(self):
        return self.nom

    @property
    def origine(self):
        """Où les lignes sont lues, pour la mention sous chaque tableau."""
        if self.document_id and self.type == "csv":
            return "un fichier déposé dans la médiathèque"
        from urllib.parse import urlsplit
        return urlsplit(self.url_base).hostname or "la source configurée"

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
        if self.document_id:
            with self.document.file.open("rb") as f:
                texte = f.read().decode("utf-8-sig", "replace")
        else:
            r = requests.get(self.url_base, timeout=TIMEOUT)
            r.raise_for_status()
            texte = r.content.decode("utf-8-sig", "replace")
        # Séparateur lu sur la seule ligne d'en-tête : le détecteur automatique échoue sur les textes longs.
        entete = texte.split("\n", 1)[0]
        sep = max(";,\t", key=entete.count)
        return list(csv.DictReader(io.StringIO(texte), delimiter=sep))

    def _page_html(self):
        """Lit les tableaux d'une page publique (en-têtes <th>), en attendant l'API de l'application métier.

        Une requête par lecture, avec un agent identifié ; les dates jj/mm/aaaa gagnent une copie triable
        (champ suffixé _iso) ; le lien de chaque ligne se construit à partir de ses attributs data-.
        """
        import re
        import unicodedata
        from urllib.parse import urljoin

        import lxml.html

        def cle(t):
            t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
            return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "colonne"

        r = requests.get(self.url_base, timeout=TIMEOUT,
                         headers={"User-Agent": "plateforme-gnc-demo/1.0 (connecteur transitoire ; une lecture par jour)"})
        r.raise_for_status()
        doc = lxml.html.fromstring(r.content)
        lignes = []
        for tb in doc.xpath("//table[.//th]"):
            entetes = [cle(" ".join(th.text_content().split())) for th in tb.xpath(".//thead//th") or tb.xpath(".//tr[1]/th")]
            for tr in tb.xpath(".//tbody/tr[td]"):
                cellules = [" ".join(td.text_content().split()) for td in tr.xpath("./td")]
                l = dict(zip(entetes, cellules))
                for k, v in list(l.items()):
                    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", v or "")
                    if m:
                        l[f"{k}_iso"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                if "{" in self.chemin_liste:
                    attrs = {k[5:]: v for k, v in tr.attrib.items() if k.startswith("data-")}
                    if attrs:
                        l["reference"] = "-".join(attrs.values())
                    try:
                        l["lien"] = urljoin(self.url_base, self.chemin_liste.format(**attrs))
                    except KeyError:
                        pass
                lignes.append(l)
        return lignes

    def json_ld_ligne(self, donnees):
        """Données structurées d'une fiche selon schema_ligne et la correspondance déclarée."""
        if not self.schema_ligne:
            return None
        corr = dict(p.split("=", 1) for p in self.correspondance_schema.split(",") if "=" in p)
        obj = {"@context": "https://schema.org", "@type": self.schema_ligne}
        for prop, champ in corr.items():
            v = donnees.get(champ.strip())
            if v in (None, ""):
                continue
            obj[prop.strip()] = {"@type": "Organization", "name": v} if prop.strip() == "hiringOrganization" else v
        if self.schema_ligne == "JobPosting":
            obj.setdefault("jobLocation", {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "NC"}})
            obj.setdefault("datePosted", self.derniere_lecture.date().isoformat() if self.derniere_lecture else None)
            obj.setdefault("description", donnees.get("poste") or "")
        return json.dumps(obj, ensure_ascii=False)

    def _position(self, l):
        """(lat, lon) d'une ligne selon champ_geo, ou (None, None)."""
        if not self.champ_geo:
            return None, None
        try:
            if "," in self.champ_geo:
                a, b = [c.strip() for c in self.champ_geo.split(",")]
                return float(l.get(a)), float(l.get(b))
            v = l.get(self.champ_geo)
            if isinstance(v, str):
                v = json.loads(v.replace("'", '"'))
            if isinstance(v, dict) and "geometry" in v:
                lon, lat = v["geometry"]["coordinates"][:2]
                return float(lat), float(lon)
            if isinstance(v, dict):
                return float(v["lat"]), float(v["lon"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            pass
        return None, None

    def lire(self):
        """Lit la source, remplace le cache, renvoie les identifiants des lignes nouvelles.

        En cas d'échec, le cache précédent est conservé (le site continue d'afficher
        la dernière version valide) et l'erreur est notée sur la source.
        """
        try:
            lignes = {"opendatasoft": self._opendatasoft, "rest": self._rest, "csv": self._csv,
                      "page_html": self._page_html}[self.type]()
            if not isinstance(lignes, list):
                raise ValueError("la source ne renvoie pas une liste de lignes")
            lignes = [l for l in lignes if isinstance(l, dict)][: self.max_lignes]
        except Exception as e:  # noqa: BLE001 - toute panne de source est rapportée, jamais propagée au site
            self.derniere_erreur = f"{timezone.now():%d/%m/%Y %H:%M} : {e}"[:2000]
            self.save(update_fields=["derniere_erreur"])
            return []

        anciennes = set(self.lignes.values_list("identifiant", flat=True))
        positions = [self._position(l) for l in lignes]
        garder = [c.strip() for c in self.champs_conserves.split(",") if c.strip()]
        if garder:
            lignes = [{k: l.get(k) for k in garder} for l in lignes]
        champs = list(dict.fromkeys(k for l in lignes for k in l.keys()))
        objets, vus = [], {}
        for i, l in enumerate(lignes):
            ident = str(l.get(self.cle)) if self.cle and l.get(self.cle) is not None else \
                hashlib.sha1(json.dumps(l, sort_keys=True, default=str).encode()).hexdigest()[:16]
            # Adresse de fiche : Wagtail n'accepte que lettres, chiffres, « - » et « _ » dans un segment d'adresse
            ident = re.sub(r"[^\w-]", "_", ident)[:120] or "ligne"
            # Deux lignes identiques (fréquent après minimisation) reçoivent chacune une adresse de fiche distincte
            n = vus.get(ident, 0)
            vus[ident] = n + 1
            if n:
                ident = f"{ident}-{n + 1}"
            texte = " ".join(str(v) for v in l.values() if v not in (None, ""))[:20000]
            lat, lon = positions[i]
            objets.append(Ligne(source=self, rang=i, identifiant=ident, donnees=l, texte=texte, lat=lat, lon=lon))
        with transaction.atomic():
            anciens_ids = list(self.lignes.values_list("pk", flat=True))
            for i in range(0, len(anciens_ids), 5000):
                Ligne.objects.filter(pk__in=anciens_ids[i:i + 5000]).delete()
            Ligne.objects.bulk_create(objets, batch_size=1000)
            self.champs, self.nb_lignes = champs, len(objets)
            self.derniere_lecture, self.derniere_erreur = timezone.now(), ""
            self.save(update_fields=["champs", "nb_lignes", "derniere_lecture", "derniere_erreur"])
        # Réindexation : sans elle, la recherche du site (UC022) ignorerait les lignes relues.
        from wagtail.search.backends import get_search_backend
        ids = list(self.lignes.values_list("pk", flat=True))
        for i in range(0, len(ids), 5000):  # par paquets : SQLite limite le nombre de variables d'une requête
            get_search_backend().add_bulk(Ligne, list(Ligne.objects.filter(pk__in=ids[i:i + 5000])))
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
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

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
