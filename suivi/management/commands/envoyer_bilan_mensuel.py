"""Bilan mensuel envoyé à chaque contributeur (UC007) : vues de ses pages et liens morts à corriger."""
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

from home.models import PageContenu
from suivi.models import LienMort, PageVue


class Command(BaseCommand):
    help = "Envoie à chaque contributeur le bilan de ses pages sur les 30 derniers jours"

    def add_arguments(self, p):
        p.add_argument("--jours", type=int, default=30)

    def handle(self, *a, **o):
        depuis = timezone.localdate() - timedelta(days=o["jours"])
        envoyes = 0
        for u in get_user_model().objects.filter(is_active=True).exclude(email=""):
            pages = PageContenu.objects.live().filter(owner=u)
            if not pages.exists():
                continue
            vues = dict(PageVue.objects.filter(page__in=pages, jour__gte=depuis).values_list("page").annotate(n=Sum("vues")))
            lignes = sorted(({"page": p, "vues": vues.get(p.pk, 0)} for p in pages), key=lambda x: -x["vues"])
            morts = defaultdict(list)
            for l in LienMort.objects.filter(page__in=pages):
                morts[l.page_id].append(l)
            ctx = {"u": u, "lignes": lignes, "total": sum(x["vues"] for x in lignes), "depuis": depuis,
                   "morts": [(p, morts[p.pk]) for p in pages if morts[p.pk]], "nb_morts": sum(len(v) for v in morts.values())}
            texte = render_to_string("suivi/bilan.txt", ctx)
            html = render_to_string("suivi/bilan.html", ctx)
            n = ctx["nb_morts"]
            sujet = f"Vos pages ce mois-ci : {ctx['total']} vue{'s' if ctx['total'] > 1 else ''}, " + (
                f"{n} lien{'s' if n > 1 else ''} à corriger" if n else "aucun lien à corriger")
            m = EmailMultiAlternatives(sujet,
                                       texte, settings.DEFAULT_FROM_EMAIL, [u.email])
            m.attach_alternative(html, "text/html")
            m.send()
            envoyes += 1
        self.stdout.write(f"{envoyes} bilan(s) envoyé(s)")
