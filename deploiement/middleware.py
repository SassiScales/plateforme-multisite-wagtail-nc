"""Instance publique sur une seule adresse (hébergement gratuit) : les sites restent distingués par hôte.

En local, gouv, drhfpnc et l'ancien dittt ont chacun leur nom (gouv.localhost...). En ligne, une seule
adresse est disponible : ce middleware choisit l'hôte interne d'après un cookie posé par /_site/<nom>/,
rejoue les anciennes adresses par /_ancien/dittt/<chemin>, et réécrit les liens absolus entre sites.
Activé uniquement par les réglages « enligne ». La base et le code métier ne changent pas.
"""
import re

from django.http import HttpResponseRedirect

SITES = {"gouv": "gouv.localhost:8000", "drhfpnc": "drhfpnc.localhost:8000"}
ANCIENS = {"dittt": "dittt.localhost:8000"}
ABSOLU = re.compile(r"https?://(gouv|drhfpnc|dittt)\.localhost:8000/?")
COOKIE = "site_demo"


def lien(m):
    nom = m.group(1)
    return f"/_ancien/{nom}/" if nom in ANCIENS else f"/_site/{nom}/"


class HoteUnique:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        p = request.path_info
        m = re.match(r"^/_site/(\w+)(/.*)?$", p)
        if m and m.group(1) in SITES:
            r = HttpResponseRedirect(m.group(2) or "/")
            r.set_cookie(COOKIE, m.group(1), samesite="Lax", secure=request.is_secure(), httponly=True)
            return r
        m = re.match(r"^/_ancien/(\w+)(/.*)?$", p)
        if m and m.group(1) in ANCIENS:
            request.META["HTTP_HOST"] = ANCIENS[m.group(1)]
            request.path_info = request.path = m.group(2) or "/"
        else:
            request.META["HTTP_HOST"] = SITES.get(request.COOKIES.get(COOKIE), SITES["gouv"])
        reponse = self.get_response(request)
        if reponse.has_header("Location"):
            reponse["Location"] = ABSOLU.sub(lien, reponse["Location"])
        if reponse.get("Content-Type", "").startswith("text/html") and not getattr(reponse, "streaming", False):
            reponse.content = ABSOLU.sub(lien, reponse.content.decode()).encode()
            if reponse.has_header("Content-Length"):
                reponse["Content-Length"] = str(len(reponse.content))
        return reponse


class VisiteurLectureSeule:
    """Le compte public « visiteur » ouvre tout le back-office mais n'enregistre rien."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if (request.method not in ("GET", "HEAD", "OPTIONS") and u is not None and u.is_authenticated
                and u.groups.filter(name="Visiteurs").exists()
                and not request.path_info.startswith(("/admin/login", "/admin/logout", "/admin/editing-sessions/"))):
            from django.contrib import messages
            messages.warning(request, "Compte de démonstration en lecture seule : rien n'a été enregistré.")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/admin/")
        return self.get_response(request)
