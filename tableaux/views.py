from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Abonnement, SourceDonnees


@require_POST
def abonner(request, source_id):
    source = get_object_or_404(SourceDonnees, pk=source_id)
    email = request.POST.get("email", "").strip()
    if "@" in email:
        Abonnement.objects.get_or_create(source=source, email=email, filtre=request.POST.get("filtre", "").strip()[:200])
        messages.success(request, "Alerte enregistrée. Vous recevrez un e-mail à chaque nouveauté.")
    return redirect(request.POST.get("retour") or "/")


def desinscrire(request, jeton):
    Abonnement.objects.filter(jeton=jeton).delete()
    messages.success(request, "Vous êtes désinscrit de cette alerte.")
    return redirect("/")
