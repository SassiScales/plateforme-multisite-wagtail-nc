"""Habillage du back-office aux couleurs de la plateforme (variables de couleur documentées par Wagtail)."""
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from wagtail import hooks
from wagtail.admin.ui.components import Component

COULEURS = """
:root {
  --w-color-primary: #00496e; --w-color-primary-200: #00374f;
  --w-color-secondary: #006699; --w-color-secondary-400: #00496e; --w-color-secondary-600: #00374f;
  --w-color-secondary-50: #eef7fb; --w-color-secondary-75: #d7ecf5; --w-color-secondary-100: #b9dcec;
}
.login .login-agentconnect { display:block; margin:1.5rem 0 .5rem; padding:.9rem 1rem; border-radius:.4rem;
  background:#000091; color:#fff; font-weight:700; text-align:center; text-decoration:none; }
.login .login-agentconnect small { display:block; font-weight:400; font-size:.8rem; opacity:.85; }
.login .login-separateur { text-align:center; font-size:.85rem; opacity:.8; margin:.8rem 0 0; }
"""


@hooks.register("insert_global_admin_css")
def couleurs_plateforme():
    return format_html("<style>{}</style>", COULEURS)


class AccueilEvaluateur(Component):
    """Encart d'accueil du compte d'évaluation : ce qu'il peut faire, et la remise à neuf nocturne."""
    order = 10

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        return mark_safe(
            '<section class="w-panel" style="margin:0 0 2rem;padding:1.1rem 1.25rem;border-radius:.5rem;'
            'background:var(--w-color-secondary-50);border:1px solid var(--w-color-secondary-100)">'
            '<h2 class="w-h3" style="margin:0 0 .4rem">Compte d\'évaluation</h2>'
            '<p style="margin:0 0 .5rem">Vous avez les droits d\'un contributeur du pôle communication : modifier une page, '
            'soumettre à validation, publier, ajouter une image, configurer une source de données.</p>'
            '<p style="margin:0">Essayez sans crainte : la base est remise à neuf chaque jour, à la première visite après 3 h (heure de Nouméa).</p></section>')


@hooks.register("construct_homepage_panels")
def encart_evaluateur(request, panels):
    if request.user.groups.filter(name="Évaluateurs").exists():
        panels.insert(0, AccueilEvaluateur(request))
