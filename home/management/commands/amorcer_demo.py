"""Construit la démonstration de bout en bout (idempotent : repart de zéro à chaque lancement).

Deux sites dans un seul back-office, des sources data.gouv.nc lues en direct, des
droits hérités par direction, un circuit de validation et une redirection 301.
Usage : python manage.py amorcer_demo [--mot-de-passe X] [--port 8000]
"""
import secrets

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


def tableau(source, titre, colonnes, detail=(), abonnement=False, par_page=25):
    return ("tableau", {"source": source, "titre": titre, "recherche": True, "par_page": par_page, "abonnement": abonnement,
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
        diplomes = SourceDonnees.objects.create(nom="Assimilation des diplômes étrangers (fonction publique)", type="opendatasoft",
                                                url_base=ODS, jeu="assimilation_diplomes_etrangers_fp", max_lignes=1000)

        # --- Site gouv.nc
        gouv = racine.add_child(instance=HomePage(
            title="Gouvernement de la Nouvelle-Calédonie", slug="gouv", gabarit="accueil",
            chapo="Point d'entrée unique des informations du gouvernement : actualités, politiques publiques, textes et données.",
            corps=[para("<p>Cette page d'accueil de démonstration est gérée dans le même back-office que le site de la DRH. "
                        "Les démarches restent sur <a href=\"https://service-public.nc\">service-public.nc</a>.</p>")]))
        tarifs = gouv.add_child(instance=PageContenu(
            title="Tarifs douaniers", slug="tarifs-douaniers", gabarit="large", show_in_menus=True,
            chapo="Les chapitres du tarif douanier, lus en direct sur data.gouv.nc et consultables sans téléchargement.",
            corps=[tableau(douane, "Chapitres du tarif douanier", [("hs2_cod", "Chapitre"), ("hs2_dsc", "Libellé"), ("hs1_cod", "Section")],
                           [("hs2_cod", "Chapitre"), ("hs2_dsc", "Libellé"), ("hs1_cod", "Section"), ("valid_from", "En vigueur depuis")])]))
        gouv.add_child(instance=PageContenu(
            title="Prix des médicaments", slug="prix-des-medicaments", gabarit="large", show_in_menus=True,
            chapo="Prix de vente des médicaments en Nouvelle-Calédonie (Nouméa, brousse, îles), selon la base Sempex.",
            corps=[("alerte", {"niveau": "info", "message": RichText("<p>Démonstration : seuls les médicaments dotés d'un prix, dans la limite de 3 000 lignes, sont chargés.</p>")}),
                   tableau(medic, "Médicaments et prix", [("libelle_court", "Médicament"), ("dci", "Substance"), ("prix_cfp", "Prix Nouméa (F)"),
                                                          ("prix_brousse", "Brousse (F)"), ("prix_iles", "Îles (F)")],
                           [("libelle_long", "Désignation"), ("dci", "Substance active"), ("cip13", "Code CIP13"), ("prix_cfp", "Prix Nouméa (F CFP)"),
                            ("prix_brousse", "Prix brousse (F CFP)"), ("prix_iles", "Prix îles (F CFP)"), ("date_application", "Applicable au")],
                           abonnement=True)]))
        actus = gouv.add_child(instance=PageContenu(
            title="Actualités", slug="actualites", show_in_menus=True,
            chapo="Exemple de page éditoriale : l'éditeur ne propose que les mises en forme autorisées par le design system.",
            corps=[("intertitre", "Une mise en forme verrouillée"),
                   para("<p>Titres, paragraphes, listes et encadrés suivent automatiquement le design system. Le contributeur choisit parmi "
                        "trois gabarits et ne peut pas modifier les polices ni les couleurs.</p>"),
                   ("encadre", {"titre": "À savoir", "texte": RichText("<p>Chaque page conserve son historique : toute version peut être comparée et restaurée.</p>")})]))

        # --- Site drhfpnc (même back-office, adresse dédiée)
        drh = racine.add_child(instance=HomePage(
            title="Fonction publique de la Nouvelle-Calédonie", slug="drhfpnc", gabarit="accueil",
            chapo="Recrutement, concours et carrière dans la fonction publique de la Nouvelle-Calédonie."))
        concours = drh.add_child(instance=PageContenu(
            title="Diplômes étrangers et concours", slug="diplomes-etrangers", gabarit="large", show_in_menus=True,
            chapo="Les diplômes étrangers reconnus et les concours auxquels ils donnent accès.",
            corps=[("alerte", {"niveau": "attention", "message": RichText("<p>Exemple de bandeau non bloquant : un arrêté plus récent peut modifier cette liste.</p>")}),
                   tableau(diplomes, "Diplômes assimilés", [("diplome", "Diplôme"), ("pays", "Pays"), ("type", "Niveau"), ("arrete", "Arrêté")],
                           [("diplome", "Diplôme"), ("organisme_de_delivrance_du_diplome", "Délivré par"), ("pays", "Pays"), ("type", "Niveau"),
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
