"""Habillage du back-office aux couleurs de la plateforme (variables de couleur documentées par Wagtail)."""
from django.utils.html import format_html
from wagtail import hooks

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
