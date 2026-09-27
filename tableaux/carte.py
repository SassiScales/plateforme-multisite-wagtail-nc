"""Projection unique des cartes de la plateforme (accueil, cartes à points, cartes par commune).

Équirectangulaire corrigée en latitude moyenne, cadrée sur l'archipel (Bélep, îles Loyauté,
île des Pins). Le fond de carte est généré par design/carte_nc.py avec ces mêmes constantes.
"""
import math

LON0, LON1, LAT0, LAT1 = 163.4, 168.4, -22.95, -19.45
LARGEUR = 1000
K = math.cos(math.radians((LAT0 + LAT1) / 2))
ECHELLE = LARGEUR / ((LON1 - LON0) * K)
HAUTEUR = (LAT1 - LAT0) * ECHELLE


def projeter(lon, lat):
    return (lon - LON0) * K * ECHELLE, (LAT1 - lat) * ECHELLE


def dans_cadre(lon, lat):
    return LON0 <= lon <= LON1 and LAT0 <= lat <= LAT1
