"""Politique de sécurité assouplie pour le seul back-office Wagtail, qui utilise des scripts en ligne.

Le site public garde la politique stricte (script-src 'self'). Placé AVANT le middleware CSP de
Django dans MIDDLEWARE, ce middleware voit la réponse après lui et ne modifie que /admin/.
"""


class CSPBackOffice:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        if request.path.startswith("/admin/") and "Content-Security-Policy" in reponse:
            reponse["Content-Security-Policy"] = reponse["Content-Security-Policy"].replace(
                "script-src 'self'", "script-src 'self' 'unsafe-inline'")
        return reponse
