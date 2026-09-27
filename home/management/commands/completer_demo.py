"""Complète une base de démonstration déjà amorcée, sans la réamorcer (rejouable, local comme en ligne).

- droits du pôle communication : sources de données, images, documents, liens morts ;
- page Actualités : un fil de publications automatique à la place du texte d'exemple ;
- accueil de gouv.nc : les dernières publications sous les rubriques ;
- compte « evaluateur » : droits d'un contributeur du pôle communication, publication comprise.
Usage : manage.py completer_demo [--evaluateur-mdp <mot de passe>]
"""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from wagtail.models import GroupCollectionPermission, GroupPagePermission, Collection

from wagtail.rich_text import RichText

from home.models import PageContenu
from tableaux.models import SourceDonnees

DROITS = {
    "tableaux": ["view_sourcedonnees", "add_sourcedonnees", "change_sourcedonnees", "view_abonnement"],
    "suivi": ["view_lienmort"],
    "wagtailadmin": ["access_admin"],
}


def fil(titre, nombre):
    return {"type": "fil", "id": str(uuid.uuid4()), "value": {"titre": titre, "rubrique": None, "nombre": nombre}}


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("--evaluateur-mdp")

    def handle(self, *a, **o):
        pole = Group.objects.get(name="Pôle communication")
        for app, codes in DROITS.items():
            for c in codes:
                pole.permissions.add(Permission.objects.get(content_type__app_label=app, codename=c))
        racine = Collection.get_first_root_node()
        for app, codes in (("wagtailimages", ["add_image", "change_image", "choose_image"]),
                           ("wagtaildocs", ["add_document", "change_document", "choose_document"])):
            for c in codes:
                GroupCollectionPermission.objects.get_or_create(
                    group=pole, collection=racine, permission=Permission.objects.get(content_type__app_label=app, codename=c))
        self.stdout.write(f"Pôle communication : {pole.permissions.count()} droits généraux")

        act = PageContenu.objects.get(slug="actualites", depth=3)
        if not any(b.block_type == "fil" for b in act.corps):
            act.chapo = "Les dernières publications des sites du réseau, classées par date ; la liste se met à jour seule à chaque publication."
            act.corps = [fil("Dernières publications", 12)]
            act.save_revision().publish()
            self.stdout.write("Actualités : fil de publications")
        for site_accueil in PageContenu.objects.filter(depth=2, gabarit="accueil").specific():
            if site_accueil.get_children().live().count() > 3 and not any(b.block_type == "fil" for b in site_accueil.corps):
                corps = list(site_accueil.corps.raw_data) + [fil("Dernières publications", 6)]
                site_accueil.corps = corps
                site_accueil.save_revision().publish()
                self.stdout.write(f"{site_accueil.title} : fil sur l'accueil")

        self.offres_emploi()
        self.sources_enrichies()

        if o["evaluateur_mdp"]:
            g, _ = Group.objects.get_or_create(name="Évaluateurs")
            g.permissions.set(pole.permissions.all())
            GroupPagePermission.objects.filter(group=g).delete()
            for gpp in GroupPagePermission.objects.filter(group=pole):
                GroupPagePermission.objects.create(group=g, page=gpp.page, permission=gpp.permission)
            GroupCollectionPermission.objects.filter(group=g).delete()
            for gcp in GroupCollectionPermission.objects.filter(group=pole):
                GroupCollectionPermission.objects.create(group=g, collection=gcp.collection, permission=gcp.permission)
            U = get_user_model()
            u = U.objects.filter(username="evaluateur").first() or U.objects.create_user("evaluateur", "evaluateur@plateforme.demo", None)
            u.first_name, u.last_name, u.is_superuser, u.is_staff = "Évaluateur", "DINUM", False, False
            u.set_password(o["evaluateur_mdp"])
            u.save()
            u.groups.set([g])
            self.stdout.write("Compte evaluateur prêt (droits du pôle communication, publication comprise)")

    def offres_emploi(self):
        """Avis de vacance de poste (AVP) de drhfpnc : 36 % du trafic du site selon le cahier des charges."""
        src, cree = SourceDonnees.objects.get_or_create(nom="Avis de vacance de poste (AVP)", defaults=dict(
            type="page_html", url_base="https://drhfpnc.gouv.nc/avis-vacances-postes-AVP",
            chemin_liste="/avis-vacances-postes-AVP/download/{pdf}", cle="reference", frequence_heures=24, max_lignes=2000,
            licence="Données publiques de la DRHFPNC", schema_ligne="JobPosting",
            correspondance_schema="title=poste,hiringOrganization=employeur,validThrough=date_de_cloture_iso,occupationalCategory=cadre"))
        if src.cle != "reference":
            src.cle = "reference"
            src.save(update_fields=["cle"])
            src.nb_lignes = 0
        if not src.nb_lignes or not src.lignes.filter(identifiant__contains="-").exists():
            src.lire()
        self.stdout.write(f"Source AVP : {src.nb_lignes} avis")
        drh = PageContenu.objects.get(slug="drhfpnc", depth=2)
        if drh.get_children().filter(slug="offres-emploi").exists():
            return
        col = lambda *cs: [{"champ": c, "libelle": l} for c, l in cs]
        rep = lambda t, c="", l="": {"type": t, "champ": c, "champ2": "", "libelle": l}
        page = PageContenu(
            title="Offres d'emploi (AVP)", slug="offres-emploi", pictogramme="emploi", gabarit="large", show_in_menus=True,
            chapo="Les avis de vacance de poste ouverts dans les fonctions publiques de Nouvelle-Calédonie : filtrez par cadre, "
                  "triez par date de clôture, recevez une alerte à chaque nouvel avis.",
            corps=[("alerte", {"niveau": "info", "message": RichText(
                        "<p>Démonstration : les avis sont lus chaque jour sur la page publique actuelle de la DRHFPNC. "
                        "En production, le même tableau lit directement l'API de l'application de gestion des AVP, "
                        "sans ressaisie ni bascule manuelle.</p>")}),
                   ("tableau", {"source": src, "titre": "Avis ouverts", "recherche": True, "par_page": 25, "abonnement": True,
                                "affichage": "tableau", "filtre_champ": "cadre",
                                "indicateurs": [rep("nombre", l="avis de vacance ouverts"), rep("distincts", "employeur", "employeurs"),
                                                rep("frequent", "cadre", "cadre le plus recherché")],
                                "colonnes": col(("poste", "Poste"), ("employeur", "Employeur"), ("cat", "Cat."), ("cadre", "Cadre"),
                                                ("date_de_cloture", "Clôture")),
                                "colonnes_detail": col(("poste", "Poste"), ("cadre", "Cadre ou filière"), ("cat", "Catégorie"),
                                                       ("employeur", "Employeur"), ("direction", "Direction"),
                                                       ("date_de_cloture", "Date de clôture des candidatures"))})])
        drh.add_child(instance=page)
        page.save_revision().publish()
        page.owner = drh.owner
        page.save(update_fields=["owner"])
        self.stdout.write("Page Offres d'emploi (AVP) publiée sur drhfpnc")

    # ------------------------------------------------------------------ jeux plus riches (retours du 28/09)
    @staticmethod
    def remplacer_tableau(page, config):
        corps = []
        for b in page.corps.raw_data:
            if b["type"] == "tableau" and b["value"]["source"] == config["source"].pk:
                b = {**b, "value": {**config, "source": config["source"].pk}}
            corps.append(b)
        page.corps = corps
        page.save_revision().publish()

    def sources_enrichies(self):
        col = lambda *cs: [{"champ": c, "libelle": l} for c, l in cs]
        rep = lambda t, c="", l="": {"type": t, "champ": c, "champ2": "", "libelle": l}
        base = {"recherche": True, "par_page": 25, "abonnement": False, "affichage": "tableau"}

        # Tarif douanier : la compilation publie les taux de chaque droit et taxe par position (6 373 lignes)
        tarif = SourceDonnees.objects.filter(jeu__startswith="referentiel-douanier-tarif-douanier").first()
        if tarif and tarif.jeu != "referentiel-douanier-tarif-douanier-compilation":
            tarif.nom = "Tarif douanier : positions, droits et taxes"
            tarif.jeu = "referentiel-douanier-tarif-douanier-compilation"
            tarif.filtre = "dd is not null or tgc is not null"
            tarif.champs_conserves = ("codification_statistique,position_sh,designation_des_marchandises,unite_supp,dd,tgc,tci,tspa,"
                                      "tat,tap,tpp,tapp,tte,trm,chapitre,titre_du_chapitre,section")
            tarif.cle, tarif.max_lignes = "codification_statistique", 10000
            tarif.save()
            tarif.lire()
            self.remplacer_tableau(PageContenu.objects.get(slug="tarifs-douaniers"), {**base, "source": tarif,
                "titre": "Positions tarifaires, droits et taxes", "filtre_champ": "chapitre",
                "indicateurs": [rep("nombre", l="positions tarifaires"), rep("frequent", "dd", "droit de douane le plus fréquent"),
                                rep("frequent", "tgc", "taux de TGC le plus fréquent")],
                "colonnes": col(("codification_statistique", "Code"), ("designation_des_marchandises", "Désignation"),
                                ("dd", "Droit de douane"), ("tgc", "TGC"), ("chapitre", "Chapitre")),
                "colonnes_detail": col(("codification_statistique", "Code statistique"), ("position_sh", "Position SH"),
                                       ("designation_des_marchandises", "Désignation des marchandises"), ("unite_supp", "Unité supplémentaire"),
                                       ("dd", "DD : droit de douane"), ("tgc", "TGC : taxe générale sur la consommation"),
                                       ("tci", "TCI"), ("tspa", "TSPA"), ("tat", "TAT"), ("tap", "TAP"), ("tpp", "TPP"), ("tapp", "TAPP"),
                                       ("tte", "TTE"), ("trm", "TRM"), ("chapitre", "Chapitre"), ("titre_du_chapitre", "Titre du chapitre"),
                                       ("section", "Section"))})
            self.stdout.write(f"Tarif douanier : {tarif.nb_lignes} positions avec leurs taux")
        page_tarif = PageContenu.objects.get(slug="tarifs-douaniers")
        if "chapitres" in page_tarif.chapo.lower():
            page_tarif.chapo = ("Le droit de douane et la TGC de chaque marchandise, position par position, "
                                "lus chaque jour sur data.gouv.nc (référentiel de la Direction régionale des douanes).")
            page_tarif.search_description = page_tarif.chapo
            page_tarif.save_revision().publish()
            self.stdout.write("Tarifs douaniers : chapô mis à jour")

        # Artisanat : millésime 2024, tous les champs publiés (le jeu ne contient ni nom ni adresse)
        art = SourceDonnees.objects.filter(jeu__startswith="etablissements-artisanaux-actifs").first()
        if art and art.jeu != "etablissements-artisanaux-actifs-au-31-12-2024":
            art.nom = "Établissements artisanaux actifs au 31/12/2024"
            art.jeu = "etablissements-artisanaux-actifs-au-31-12-2024"
            art.champs_conserves = ("commune,province,secteur_d_activite,code_nafa,libelle_nafa,forme_juridique,"
                                    "date_de_declaration,anciennete")
            art.save()
            art.lire()
            page = PageContenu.objects.get(slug="artisanat")
            conf = next(b["value"] for b in page.corps.raw_data if b["type"] == "tableau")
            conf = {**conf, "source": art, "colonnes_detail": col(
                ("libelle_nafa", "Activité"), ("code_nafa", "Code d'activité (NAFA)"), ("secteur_d_activite", "Secteur"),
                ("forme_juridique", "Forme juridique"), ("commune", "Commune"), ("province", "Province"),
                ("date_de_declaration", "Déclaré au répertoire le"), ("anciennete", "Ancienneté (ans)"))}
            self.remplacer_tableau(page, conf)
            self.stdout.write(f"Artisanat 2024 : {art.nb_lignes} établissements")
        page_art = PageContenu.objects.get(slug="artisanat")
        if "2023" in page_art.chapo:
            page_art.chapo = page_art.chapo.replace("31 décembre 2023", "31 décembre 2024").replace("2023", "2024")
            page_art.save_revision().publish()
            self.stdout.write("Artisanat : chapô 2024")

        # Entreprises : répertoire RIDET (dénomination, enseigne, activité, commune)
        gouv = PageContenu.objects.get(slug="gouv", depth=2)
        if not gouv.get_children().filter(slug="entreprises").exists():
            ridet, _ = SourceDonnees.objects.get_or_create(nom="Établissements actifs au RIDET", defaults=dict(
                type="opendatasoft", url_base="https://data.gouv.nc", jeu="etablissements-actifs-au-ridet", max_lignes=50000,
                champs_conserves="rid7,ndegetablissement,denomination,sigle,enseigne,libelle_formjur,code_ape,libelle_naf,"
                                 "libelle_section_naf,libelle_commune,province,date_etablis_actif",
                licence="Licence ouverte v2.0 (ISEE)"))
            if not ridet.nb_lignes:
                ridet.lire()
            page = PageContenu(
                title="Entreprises (RIDET)", slug="entreprises", pictogramme="artisanat", gabarit="large", show_in_menus=True,
                chapo="Les établissements actifs inscrits au répertoire des entreprises (RIDET) : recherchez une entreprise "
                      "par son nom, son enseigne, son activité ou sa commune.",
                corps=[("tableau", {**base, "source": ridet, "titre": "Établissements actifs", "filtre_champ": "libelle_section_naf",
                        "indicateurs": [rep("nombre", l="établissements actifs"), rep("distincts", "libelle_commune", "communes"),
                                        rep("frequent", "libelle_section_naf", "secteur le plus représenté")],
                        "colonnes": col(("denomination", "Dénomination"), ("enseigne", "Enseigne"), ("libelle_naf", "Activité"),
                                        ("libelle_commune", "Commune")),
                        "colonnes_detail": col(("denomination", "Dénomination"), ("sigle", "Sigle"), ("enseigne", "Enseigne"),
                                               ("rid7", "Numéro RIDET"), ("ndegetablissement", "Numéro d'établissement"),
                                               ("libelle_formjur", "Forme juridique"), ("libelle_naf", "Activité"), ("code_ape", "Code APE"),
                                               ("libelle_section_naf", "Secteur"), ("libelle_commune", "Commune"), ("province", "Province"),
                                               ("date_etablis_actif", "Actif à la date du"))})])
            gouv.add_child(instance=page)
            page.save_revision().publish()
            page.owner = gouv.owner
            page.save(update_fields=["owner"])
            self.stdout.write(f"Page Entreprises (RIDET) : {ridet.nb_lignes} établissements")
