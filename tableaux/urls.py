from django.urls import path

from . import views

urlpatterns = [
    path("abonner/<int:source_id>/", views.abonner, name="tableaux_abonner"),
    path("desinscription/<str:jeton>/", views.desinscrire, name="tableaux_desinscrire"),
]
