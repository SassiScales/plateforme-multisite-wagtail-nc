#!/usr/bin/env python3
"""Fabrique les cartes de la Nouvelle-Calédonie à partir des LIMITES COMMUNALES publiées sur data.gouv.nc.

Source : jeu « communes-nc-limites-terrestres-simplifiees » (33 communes, export GeoJSON).
Sorties :
  plateforme/templates/carte_nc.svg     fond de l'accueil : communes + courbes de distance à la côte
  tableaux/communes_nc.json             contours simplifiés par commune, pour les cartes par commune

Les lignes autour des îles sont des courbes de DISTANCE À LA CÔTE (3 à 40 km), calculées ;
ce ne sont pas des profondeurs mesurées.
Usage : .venv-scraping/bin/python design/carte_nc.py design/sources/communes-nc.geojson
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage
from skimage import draw, measure

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, ".."))
from tableaux.carte import HAUTEUR, K, LARGEUR, LAT0, LAT1, LON0, LON1, projeter  # noqa: E402

RES = 0.012
DISTANCES_KM = [3, 8, 15, 25, 40]


def anneaux(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [ring for poly in polys for ring in poly]


def chemin(points, tol, ferme=True):
    pts = measure.approximate_polygon(np.array(points), tolerance=tol)
    if len(pts) < (4 if ferme else 2):
        return ""
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if ferme else "")


def main(src):
    feats = json.load(open(src))["features"]
    W, H = int((LON1 - LON0) / RES), int((LAT1 - LAT0) / RES)
    terre = np.zeros((H, W), bool)
    communes = {}
    for f in feats:
        p = f["properties"]
        paths = []
        for ring in anneaux(f["geometry"]):
            rr = [(LAT1 - la) / RES for lo, la in ring]
            cc = [(lo - LON0) / RES for lo, la in ring]
            r, c = draw.polygon(rr, cc, (H, W))
            terre[r, c] = True
            d = chemin([projeter(lo, la) for lo, la in ring], 0.5)
            if d:
                paths.append(d)
        centre = p["geo_point_2d"]
        communes[p["code_com"]] = {"nom": p["nom_minus"], "nom_maj": p["nom"], "d": " ".join(paths),
                                   "centre": [round(v, 1) for v in projeter(centre["lon"], centre["lat"])]}
    km = RES * 111.32
    dist = ndimage.distance_transform_edt(~terre, sampling=(km, km * K))
    courbes = []
    for d in DISTANCES_KM:
        segs = []
        for c in measure.find_contours(dist, d):
            if len(c) >= 12:
                seg = chemin([projeter(LON0 + cc * RES, LAT1 - rr * RES) for rr, cc in c], 0.9, ferme=False)
                if seg:
                    segs.append(seg)
        courbes.append(" ".join(segs))

    nx, ny = projeter(166.4572, -22.2758)
    svg = [f'<svg class="carte-nc" viewBox="0 0 {LARGEUR} {HAUTEUR:.0f}" role="img" aria-label="Carte de la Nouvelle-Calédonie et de ses 33 communes, '
           'entourées de lignes de distance à la côte">']
    svg += [f'<path class="courbe c{i}" style="--k:{i}" d="{p}" pathLength="1"/>' for i, p in enumerate(courbes)]
    svg.append('<g class="iles">' + "".join(f'<path data-commune="{code}" d="{c["d"]}"/>' for code, c in sorted(communes.items())) + "</g>")
    svg.append(f'<g class="noumea" transform="translate({nx:.1f},{ny:.1f})"><circle class="onde" r="6"/><circle class="point" r="4.5"/>'
               '<text x="10" y="18">Nouméa</text></g></svg>')
    out_svg = os.path.join(ICI, "..", "plateforme", "templates", "carte_nc.svg")
    open(out_svg, "w").write("".join(svg))
    out_json = os.path.join(ICI, "..", "tableaux", "communes_nc.json")
    json.dump({"viewbox": [LARGEUR, round(HAUTEUR)], "courbes": courbes, "communes": communes}, open(out_json, "w"), ensure_ascii=False)
    print(f"{out_svg} : {os.path.getsize(out_svg) // 1024} Ko ; {out_json} : {len(communes)} communes, {os.path.getsize(out_json) // 1024} Ko")


if __name__ == "__main__":
    main(sys.argv[1])
