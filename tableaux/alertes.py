"""Envoi des alertes e-mail filtrées (UC024) : un seul message par abonné et par lecture."""
from django.conf import settings
from django.core.mail import send_mass_mail


def envoyer_alertes(source, identifiants):
    lignes = list(source.lignes.filter(identifiant__in=identifiants))
    messages = []
    for ab in source.abonnements.all():
        retenues = [l for l in lignes if not ab.filtre or ab.filtre.lower() in l.texte.lower()]
        if not retenues:
            continue
        corps = "\n".join(f"- {l.texte[:160]}" for l in retenues[:50])
        messages.append((f"{len(retenues)} nouveauté(s) : {source.nom}",
                         f"{corps}\n\nSe désinscrire : /tableaux/desinscription/{ab.jeton}/",
                         settings.DEFAULT_FROM_EMAIL, [ab.email]))
    return send_mass_mail(messages, fail_silently=False) if messages else 0
