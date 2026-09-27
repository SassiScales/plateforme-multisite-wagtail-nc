"""Lit les sources dues (ou toutes avec --toutes) et envoie les alertes des nouvelles lignes.

En production : tâche planifiée (Celery beat ou cron) toutes les heures.
"""
from django.core.management.base import BaseCommand

from tableaux.alertes import envoyer_alertes
from tableaux.models import SourceDonnees


class Command(BaseCommand):
    help = "Relit les sources de données et notifie les abonnés"

    def add_arguments(self, parser):
        parser.add_argument("--toutes", action="store_true")

    def handle(self, *args, **o):
        for s in SourceDonnees.objects.all():
            if not (o["toutes"] or s.a_relire()):
                continue
            nouvelles = s.lire()
            etat = s.derniere_erreur or f"{s.nb_lignes} lignes, {len(nouvelles)} nouvelles"
            self.stdout.write(f"{s.nom} : {etat}")
            if nouvelles:
                self.stdout.write(f"  alertes envoyées : {envoyer_alertes(s, nouvelles)}")
