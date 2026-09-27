"""Audience interne (UC007) et liens morts (UC023).

L'audience est comptée par la plateforme elle-même, page par page et jour par jour : aucun outil tiers,
aucune donnée personnelle (ni adresse IP, ni cookie), seulement un compteur par page et par jour.
"""
from django.db import models
from django.db.models import F
from django.utils import timezone
from wagtail.models import Page


class PageVue(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="+")
    jour = models.DateField(db_index=True)
    vues = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("page", "jour")]

    @classmethod
    def compter(cls, page):
        jour = timezone.localdate()
        n = cls.objects.filter(page=page, jour=jour).update(vues=F("vues") + 1)
        if not n:
            cls.objects.get_or_create(page=page, jour=jour, defaults={"vues": 1})


class LienMort(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="+")
    url = models.URLField(max_length=1000)
    statut = models.CharField(max_length=40, help_text="Code HTTP ou erreur réseau")
    vu_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "lien mort"
        verbose_name_plural = "liens morts"
        ordering = ["page__title", "url"]

    @property
    def libelle(self):
        if self.statut == "404":
            return "Page introuvable (404)"
        if self.statut == "410":
            return "Page supprimée (410)"
        if self.statut.isdigit():
            return f"Erreur {self.statut}"
        if "Timeout" in self.statut:
            return "Le site ne répond pas"
        return "Site injoignable"

    def __str__(self):
        return f"{self.page.title} -> {self.url} ({self.libelle})"
