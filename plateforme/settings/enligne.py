"""Réglages de l'instance publique (PythonAnywhere). Secrets lus dans l'environnement, jamais dans le dépôt."""
import os

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ADRESSE = os.environ.get("DEMO_ADRESSE", "sassiscales.pythonanywhere.com")
ALLOWED_HOSTS = [ADRESSE, "gouv.localhost", "drhfpnc.localhost", "dittt.localhost"]
CSRF_TRUSTED_ORIGINS = [f"https://{ADRESSE}"]
WAGTAILADMIN_BASE_URL = f"https://{ADRESSE}"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
INSTALLED_APPS = [*INSTALLED_APPS, "deploiement"]
MIDDLEWARE = ["deploiement.middleware.RemiseQuotidienne", "deploiement.middleware.HoteUnique", *MIDDLEWARE]
REMISE_SCRIPT = os.environ.get("REMISE_SCRIPT", os.path.expanduser("~/remise_a_zero.sh"))
MIDDLEWARE.insert(MIDDLEWARE.index("django.contrib.messages.middleware.MessageMiddleware") + 1,
                  "deploiement.middleware.VisiteurLectureSeule")
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

if os.environ.get("DEMO_TEST_HTTP"):  # essai local sans HTTPS uniquement
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
    CSRF_TRUSTED_ORIGINS.append(f"http://{ADRESSE}")
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
if os.environ.get("DEMO_DB"):
    DATABASES["default"]["NAME"] = os.environ["DEMO_DB"]
