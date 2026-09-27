"""Avant mise en ligne : mots de passe réels pour les comptes de travail, compte « visiteur » public en lecture seule.

Usage : manage.py durcir_demo --visiteur-mdp <mot de passe publié>
Les nouveaux mots de passe des comptes admin, pole-com et editeur-drh sont tirés au hasard et affichés une fois.
"""
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from wagtail.models import GroupPagePermission


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("--visiteur-mdp", required=True)

    def handle(self, *a, **o):
        U = get_user_model()
        for nom in ("admin", "pole-com", "editeur-drh"):
            u = U.objects.filter(username=nom).first()
            if u:
                mdp = secrets.token_urlsafe(14)
                u.set_password(mdp)
                u.save()
                self.stdout.write(f"{nom} : {mdp}")
        # Visiteurs : mêmes droits de consultation que le pôle communication, écritures bloquées par middleware.
        source = Group.objects.get(name="Pôle communication")
        g, _ = Group.objects.get_or_create(name="Visiteurs")
        g.permissions.set(source.permissions.all())
        GroupPagePermission.objects.filter(group=g).delete()
        for gpp in GroupPagePermission.objects.filter(group=source):
            GroupPagePermission.objects.create(group=g, page=gpp.page, permission=gpp.permission)
        v = U.objects.filter(username="visiteur").first() or U.objects.create_user("visiteur", "", None, first_name="Visiteur")
        v.set_password(o["visiteur_mdp"])
        v.is_superuser = v.is_staff = False
        v.save()
        v.groups.set([g])
        Session.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Comptes durcis ; compte public : visiteur (lecture seule)."))
