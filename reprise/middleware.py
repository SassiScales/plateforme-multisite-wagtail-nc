"""Anciens domaines conservés : ils ne servent QUE des redirections permanentes, adresse par adresse.

Le middleware de redirection de Wagtail n'agit que sur les 404 ; sur un ancien domaine, la
redirection doit passer AVANT tout (l'ancienne page d'accueil « / » existe aussi sur le nouveau site).
Un site est un ancien domaine quand son nom se termine par « (ancien site, redirections) ».
"""
from django.http import HttpResponsePermanentRedirect
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Site

MARQUE = "(ancien site, redirections)"


class AncienDomaine:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        site = Site.find_for_request(request)
        if site and site.site_name.endswith(MARQUE):
            r = Redirect.get_for_site(site).filter(old_path=Redirect.normalise_path(request.path)).first()
            if r:
                return HttpResponsePermanentRedirect(r.link)
        return self.get_response(request)
