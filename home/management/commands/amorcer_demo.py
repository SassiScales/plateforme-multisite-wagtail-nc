"""Construit la démonstration de bout en bout (idempotent : repart de zéro à chaque lancement).

Deux sites dans un seul back-office, des sources data.gouv.nc lues en direct, des
droits hérités par direction, un circuit de validation et une redirection 301.
Usage : python manage.py amorcer_demo [--mot-de-passe X] [--port 8000]
"""
import os
import secrets

from django.conf import settings
from django.core.files import File
from wagtail.documents.models import Document

from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import GroupPagePermission, Page, Site
from wagtail.rich_text import RichText

from home.models import HomePage, PageContenu
from tableaux.models import SourceDonnees

ODS = "https://data.gouv.nc"


def rep(type, champ="", champ2="", libelle=""):
    return {"type": type, "champ": champ, "champ2": champ2, "libelle": libelle}


def tableau(source, titre, colonnes, detail=(), abonnement=False, par_page=25, affichage="tableau", filtre="", reperes=()):
    return ("tableau", {"source": source, "titre": titre, "recherche": True, "par_page": par_page, "abonnement": abonnement,
                        "affichage": affichage, "filtre_champ": filtre, "indicateurs": list(reperes),
                        "colonnes": [{"champ": c, "libelle": l} for c, l in colonnes],
                        "colonnes_detail": [{"champ": c, "libelle": l} for c, l in detail]})


def para(t):
    return ("paragraphe", RichText(t))


class Command(BaseCommand):
    help = "Construit la démonstration de la plateforme"

    def add_arguments(self, p):
        p.add_argument("--mot-de-passe", default=None)
        p.add_argument("--port", type=int, default=8000)
        p.add_argument("--sans-lecture", action="store_true", help="Ne pas lire les sources (hors ligne)")

    def handle(self, *a, **o):
        mdp = o["mot_de_passe"] or secrets.token_urlsafe(9)
        port = o["port"]
        racine = Page.get_first_root_node()

        # Repartir de zéro
        Site.objects.all().delete()
        for p in racine.get_children():
            p.delete()
        Redirect.objects.all().delete()
        SourceDonnees.objects.all().delete()
        racine.refresh_from_db()

        # --- Sources data.gouv.nc (licence ouverte)
        douane = SourceDonnees.objects.create(nom="Tarif douanier : chapitres (SH2)", type="opendatasoft", url_base=ODS,
                                              jeu="referentiel-douanier-tarif-douanier-chapitres-unhs2tab", cle="hs2_cod", max_lignes=500)
        medic = SourceDonnees.objects.create(nom="Prix des médicaments en vigueur (Sempex)", type="opendatasoft", url_base=ODS,
                                             jeu="sempex_prix_medicaments_en_vigueur", filtre="prix_cfp is not null", cle="cip13",
                                             max_lignes=3000)
        sante = SourceDonnees.objects.create(nom="Établissements de santé", type="opendatasoft", url_base=ODS,
                                             jeu="situation_etablissements_sante", max_lignes=1500, champ_geo="latitude,longitude",
                                             champs_conserves="denomination,type_etablissement,secteur,commune,adresse,situation,champactivite,contact_telephonique_1")
        bornes = SourceDonnees.objects.create(nom="Bornes de recharge pour véhicules électriques", type="opendatasoft", url_base=ODS,
                                              jeu="bornes-de-recharge-pour-vehicules-electriques", max_lignes=500, champ_geo="geo_point_2d",
                                              cle="id_station", champs_conserves="nom_station,nom_commercial,adresse_station,commune,nb_points_charge,id_station")
        artisans = SourceDonnees.objects.create(nom="Établissements artisanaux actifs au 31/12/2023", type="opendatasoft", url_base=ODS,
                                                jeu="etablissements-artisanaux-actifs-au-31-12-2023", max_lignes=12000,
                                                champs_conserves="commune,province,secteur_d_activite,libelle_nafa,forme_juridique,anciennete")
        diplomes = SourceDonnees.objects.create(nom="Assimilation des diplômes étrangers (fonction publique)", type="opendatasoft",
                                                url_base=ODS, jeu="assimilation_diplomes_etrangers_fp", max_lignes=1000)

        # --- Site gouv.nc
        gouv = racine.add_child(instance=HomePage(
            title="Gouvernement de la Nouvelle-Calédonie", slug="gouv", gabarit="accueil",
            chapo="Point d'entrée unique des informations du gouvernement : actualités, politiques publiques, textes et données.",
            corps=[para("<p>Cette page d'accueil de démonstration est gérée dans le même back-office que le site de la DRH. "
                        "Les démarches restent sur <a href=\"https://service-public.nc\">service-public.nc</a>.</p>")]))
        tarifs = gouv.add_child(instance=PageContenu(
            title="Tarifs douaniers", slug="tarifs-douaniers", pictogramme="douane", gabarit="large", show_in_menus=True,
            chapo="Les chapitres du tarif douanier, lus en direct sur data.gouv.nc et consultables sans téléchargement.",
            corps=[tableau(douane, "Chapitres du tarif douanier", [("hs2_cod", "Chapitre"), ("hs2_dsc", "Libellé"), ("hs1_cod", "Section")], filtre="hs1_cod",
                           reperes=[rep("nombre", libelle="chapitres du tarif"), rep("distincts", "hs1_cod", libelle="sections")],
                           detail=[("hs2_cod", "Chapitre"), ("hs2_dsc", "Libellé"), ("hs1_cod", "Section"), ("valid_from", "En vigueur depuis")])]))
        gouv.add_child(instance=PageContenu(
            title="Prix des médicaments", slug="prix-des-medicaments", pictogramme="sante", gabarit="large", show_in_menus=True,
            chapo="Prix de vente des médicaments en Nouvelle-Calédonie (Nouméa, brousse, îles), selon la base Sempex.",
            corps=[("alerte", {"niveau": "info", "message": RichText("<p>Démonstration : seuls les médicaments dotés d'un prix, dans la limite de 3 000 lignes, sont chargés.</p>")}),
                   tableau(medic, "Médicaments et prix", reperes=[rep("nombre", libelle="médicaments avec un prix"),
                                                                  rep("moyenne", "prix_cfp", libelle="F CFP : prix moyen à Nouméa"),
                                                                  rep("ecart", "prix_cfp", "prix_brousse", "de plus en brousse qu'à Nouméa, en moyenne"),
                                                                  rep("ecart", "prix_cfp", "prix_iles", "de plus aux îles qu'à Nouméa, en moyenne")],
                           colonnes=[("libelle_court", "Médicament"), ("dci", "Substance"), ("prix_cfp", "Prix Nouméa (F)"),
                                                          ("prix_brousse", "Brousse (F)"), ("prix_iles", "Îles (F)")],
                           detail=[("libelle_long", "Désignation"), ("dci", "Substance active"), ("cip13", "Code CIP13"), ("prix_cfp", "Prix Nouméa (F CFP)"),
                            ("prix_brousse", "Prix brousse (F CFP)"), ("prix_iles", "Prix îles (F CFP)"), ("date_application", "Applicable au")],
                           abonnement=True)]))
        actus = gouv.add_child(instance=PageContenu(
            title="Actualités", slug="actualites", pictogramme="actualites", show_in_menus=True,
            chapo="Exemple de page éditoriale : l'éditeur ne propose que les mises en forme autorisées par le design system.",
            corps=[("intertitre", "Une mise en forme verrouillée"),
                   para("<p>Titres, paragraphes, listes et encadrés suivent automatiquement le design system. Le contributeur choisit parmi "
                        "trois gabarits et ne peut pas modifier les polices ni les couleurs.</p>"),
                   ("encadre", {"titre": "À savoir", "texte": RichText("<p>Chaque page conserve son historique : toute version peut être comparée et restaurée.</p>")})]))

        gouv.add_child(instance=PageContenu(
            title="Établissements de santé", slug="etablissements-de-sante", pictogramme="soins", gabarit="large", show_in_menus=True,
            chapo="Où se soigner : les établissements et cabinets de santé du pays, sur la carte et dans le tableau.",
            corps=[tableau(sante, "Établissements de santé", [("denomination", "Établissement"), ("type_etablissement", "Type"), ("commune", "Commune"), ("situation", "Situation")],
                           [("denomination", "Établissement"), ("type_etablissement", "Type"), ("secteur", "Secteur"), ("champactivite", "Activité"),
                            ("adresse", "Adresse"), ("commune", "Commune"), ("contact_telephonique_1", "Téléphone"), ("situation", "Situation")],
                           affichage="carte", filtre="secteur",
                           reperes=[rep("nombre", libelle="établissements"), rep("distincts", "commune", libelle="communes couvertes"),
                                    rep("frequent", "type_etablissement", libelle="type le plus courant")])]))
        gouv.add_child(instance=PageContenu(
            title="Bornes de recharge", slug="bornes-de-recharge", pictogramme="mobilite", gabarit="large", show_in_menus=True,
            chapo="Les stations de recharge pour véhicules électriques déclarées en Nouvelle-Calédonie.",
            corps=[tableau(bornes, "Stations de recharge", [("nom_station", "Station"), ("nom_commercial", "Opérateur"), ("commune", "Commune"), ("nb_points_charge", "Points de charge")],
                           [("nom_station", "Station"), ("nom_commercial", "Opérateur"), ("adresse_station", "Adresse"), ("commune", "Commune"),
                            ("nb_points_charge", "Points de charge"), ("id_station", "Identifiant")],
                           affichage="carte", filtre="commune",
                           reperes=[rep("nombre", libelle="stations"), rep("distincts", "commune", libelle="communes équipées"),
                                    rep("frequent", "nom_commercial", libelle="opérateur principal")])]))
        gouv.add_child(instance=PageContenu(
            title="Artisanat", slug="artisanat", pictogramme="artisanat", gabarit="large", show_in_menus=True,
            chapo="Les établissements artisanaux actifs au 31 décembre 2023, par commune et par secteur.",
            corps=[("carte_communes", {"source": artisans, "titre": "Où sont les artisans ?", "champ_commune": "commune", "mesure": "établissements"}),
                   tableau(artisans, "Établissements artisanaux", [("libelle_nafa", "Activité"), ("secteur_d_activite", "Secteur"), ("commune", "Commune"), ("anciennete", "Ancienneté (ans)")],
                           filtre="secteur_d_activite",
                           reperes=[rep("nombre", libelle="établissements actifs"), rep("frequent", "secteur_d_activite", libelle="secteur le plus représenté"),
                                    rep("moyenne", "anciennete", libelle="ans d'ancienneté moyenne")])]))

        # Code du travail : PDF intégral de la DTENC découpé en articles (reprise/convertir_code_travail), déposé en CSV
        csv_code = os.path.join(settings.BASE_DIR, "migration", "code-travail.csv")
        if os.path.exists(csv_code):
            with open(csv_code, "rb") as f:
                doc = Document(title="Code du travail de Nouvelle-Calédonie, articles (mise à jour du 12/06/2026)")
                doc.file.save("code-travail-nc.csv", File(f), save=True)
            code = SourceDonnees.objects.create(nom="Code du travail de Nouvelle-Calédonie (DTENC, mise à jour du 12/06/2026)", type="csv",
                                                document=doc, cle="numero", max_lignes=5000, licence="Texte officiel publié par la DTENC")
            gouv.add_child(instance=PageContenu(
                title="Code du travail", slug="code-du-travail", pictogramme="donnees", gabarit="large", show_in_menus=True,
                chapo="Le code du travail de Nouvelle-Calédonie, article par article : recherche dans le texte, filtre par livre, une adresse par article.",
                corps=[("alerte", {"niveau": "info", "message": RichText("<p>Démonstration : les 799 pages du PDF intégral publié par la DTENC ont été découpées automatiquement en articles. Le texte officiel reste celui du PDF.</p>")}),
                       tableau(code, "Articles du code du travail", [("numero", "Article"), ("chapitre", "Chapitre"), ("extrait", "Début du texte")],
                               detail=[("numero", "Article"), ("nature", "Nature"), ("livre", "Livre"), ("chapitre", "Chapitre"), ("texte", "Texte"), ("page", "Page du PDF")],
                               filtre="livre", par_page=20,
                               reperes=[rep("nombre", libelle="articles"), rep("distincts", "chapitre", libelle="chapitres"),
                                        rep("frequent", "nature", libelle="nature la plus fréquente")])]))

        # --- Site drhfpnc (même back-office, adresse dédiée)
        drh = racine.add_child(instance=HomePage(
            title="Fonction publique de la Nouvelle-Calédonie", slug="drhfpnc", gabarit="accueil",
            chapo="Recrutement, concours et carrière dans la fonction publique de la Nouvelle-Calédonie."))
        concours = drh.add_child(instance=PageContenu(
            title="Diplômes étrangers et concours", slug="diplomes-etrangers", pictogramme="emploi", gabarit="large", show_in_menus=True,
            chapo="Les diplômes étrangers reconnus et les concours auxquels ils donnent accès.",
            corps=[("alerte", {"niveau": "attention", "message": RichText("<p>Exemple de bandeau non bloquant : un arrêté plus récent peut modifier cette liste.</p>")}),
                   tableau(diplomes, "Diplômes assimilés", [("diplome", "Diplôme"), ("pays", "Pays"), ("type", "Niveau"), ("arrete", "Arrêté")], filtre="pays",
                           reperes=[rep("nombre", libelle="diplômes étrangers assimilés"), rep("distincts", "pays", libelle="pays de délivrance"),
                                    rep("frequent", "pays", libelle="pays le plus représenté")],
                           detail=[("diplome", "Diplôme"), ("organisme_de_delivrance_du_diplome", "Délivré par"), ("pays", "Pays"), ("type", "Niveau"),
                            ("modes_dacces_possibles", "Concours accessibles"), ("arrete", "Arrêté")], abonnement=True)]))

        Site.objects.create(hostname="gouv.localhost", port=port, root_page=gouv, is_default_site=True, site_name="gouv.nc")
        Site.objects.create(hostname="drhfpnc.localhost", port=port, root_page=drh, site_name="drhfpnc.gouv.nc")

        # --- Redirection 301 d'exemple (ancienne adresse Drupal -> nouvelle page)
        Redirect.objects.create(old_path="/fr/douane/tarif-douanier", redirect_page=tarifs, is_permanent=True)

        # --- Droits hérités : pôle communication sur tout, éditeurs DRH sur leur site seulement
        acces = Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin")
        perms = {c: Permission.objects.get(content_type__app_label="wagtailcore", codename=c)
                 for c in ("add_page", "change_page", "publish_page", "lock_page", "unlock_page")}
        U = get_user_model()
        U.objects.filter(username__in=["admin", "pole-com", "editeur-drh"]).delete()
        for nom, pages, codes in (("Pôle communication", [gouv, drh], perms.keys()), ("Éditeurs DRH", [drh], ("add_page", "change_page"))):
            g, _ = Group.objects.get_or_create(name=nom)
            g.permissions.add(acces)
            GroupPagePermission.objects.filter(group=g).delete()
            for p in pages:
                for c in codes:
                    GroupPagePermission.objects.create(group=g, page=p, permission=perms[c])
        U.objects.create_superuser("admin", "admin@plateforme.demo", mdp)
        u = U.objects.create_user("pole-com", "com@plateforme.demo", mdp, first_name="Pôle", last_name="Communication")
        u.groups.add(Group.objects.get(name="Pôle communication"))
        u = U.objects.create_user("editeur-drh", "drh@plateforme.demo", mdp, first_name="Éditeur", last_name="DRH")
        u.groups.add(Group.objects.get(name="Éditeurs DRH"))

        from wagtail.models import Workflow
        Workflow.objects.filter(name="Moderators approval").update(name="Validation par un administrateur")

        if not o["sans_lecture"]:
            call_command("lire_sources", "--toutes")
        call_command("update_index")
        self.stdout.write(self.style.SUCCESS(
            f"\nDémo prête. http://gouv.localhost:{port}/  ·  http://drhfpnc.localhost:{port}/  ·  admin : http://gouv.localhost:{port}/admin/\n"
            f"Comptes : admin, pole-com, editeur-drh  ·  mot de passe : {mdp}"))
