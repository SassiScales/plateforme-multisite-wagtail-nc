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

from home.models import PageContenu

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
