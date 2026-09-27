#!/usr/bin/env python3
"""Fabrique la carte SVG de la Nouvelle-Calédonie utilisée par l'accueil de la démonstration.

Source : trait de côte Natural Earth 1:10m (domaine public), diffusé par le paquet npm
world-atlas (countries-10m.json). Les lignes autour des îles sont des courbes de
DISTANCE À LA CÔTE (3 à 40 km), calculées, évoquant les isobathes d'une carte marine ;
ce ne sont pas des profondeurs mesurées, et la légende de la page le dit.

Usage : .venv-scraping/bin/python carte_nc.py <countries-10m.json> <sortie.svg>
"""
import json
import math
import sys

import numpy as np
from scipy import ndimage
from skimage import draw, measure

LON0, LON1, LAT0, LAT1 = 163.4, 168.4, -22.95, -19.45   # cadre : Bélep, Loyauté, île des Pins
RES = 0.012                                                # degrés par pixel de calcul (~1,3 km)
DISTANCES_KM = [3, 8, 15, 25, 40]
LARGEUR = 1000


def decoder(topo, nom="New Caledonia"):
    """Anneaux (lon, lat) de la géométrie `nom` d'un TopoJSON quantifié."""
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    geom = next(g for g in topo["objects"]["countries"]["geometries"] if g.get("properties", {}).get("name") == nom)
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
    anneaux = []
    for poly in polys:
        for anneau in poly:
            pts = []
            for i in anneau:
                a = arcs[i] if i >= 0 else arcs[~i][::-1]
                pts.extend(a if not pts else a[1:])
            anneaux.append(pts)
    return anneaux


def main(src, out):
    anneaux = decoder(json.load(open(src)))
    k = math.cos(math.radians((LAT0 + LAT1) / 2))            # correction équirectangulaire
    W = int((LON1 - LON0) / RES)
    H = int((LAT1 - LAT0) / RES)
    terre = np.zeros((H, W), bool)
    for a in anneaux:
        rr = [(LAT1 - la) / RES for lo, la in a]
        cc = [(lo - LON0) / RES for lo, la in a]
        r, c = draw.polygon(rr, cc, (H, W))
        terre[r, c] ^= True
    km_par_px = RES * 111.32
    dist = ndimage.distance_transform_edt(~terre, sampling=(km_par_px, km_par_px * k)) if True else None

    echelle = LARGEUR / ((LON1 - LON0) * k)
    hauteur = (LAT1 - LAT0) * echelle

    def xy(lo, la):
        return (lo - LON0) * k * echelle, (LAT1 - la) * echelle

    def chemin(points, ferme=True):
        s = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
        return s + ("Z" if ferme else "")

    iles = []
    for a in anneaux:
        pts = [xy(lo, la) for lo, la in a]
        pts = measure.approximate_polygon(np.array(pts), tolerance=0.6)
        if len(pts) >= 4:
            iles.append(chemin(pts))

    courbes = []
    for d in DISTANCES_KM:
        paths = []
        for c in measure.find_contours(dist, d):
            if len(c) < 12:
                continue
            pts = [xy(LON0 + cc * RES, LAT1 - rr * RES) for rr, cc in c]
            pts = measure.approximate_polygon(np.array(pts), tolerance=0.9)
            paths.append(chemin(pts, ferme=False))
        courbes.append((d, " ".join(paths)))

    nx, ny = xy(166.4572, -22.2758)                            # Nouméa
    svg = [f'<svg class="carte-nc" viewBox="0 0 {LARGEUR} {hauteur:.0f}" role="img" '
           'aria-label="Carte de la Nouvelle-Calédonie : Grande Terre, îles Loyauté, île des Pins et Bélep, entourées de lignes de distance à la côte">']
    for i, (d, p) in enumerate(courbes):
        svg.append(f'<path class="courbe c{i}" style="--k:{i}" d="{p}" pathLength="1"/>')
    svg.append('<g class="iles">' + "".join(f'<path d="{p}"/>' for p in iles) + "</g>")
    svg.append(f'<g class="noumea" transform="translate({nx:.1f},{ny:.1f})"><circle class="onde" r="6"/><circle class="point" r="4.5"/>'
               f'<text x="10" y="18">Nouméa</text></g>')
    svg.append("</svg>")
    open(out, "w").write("".join(svg))
    print(f"{out} : {len(iles)} îles, {sum(len(p) > 0 for _, p in courbes)} courbes, {len(''.join(svg)) // 1024} Ko")


if __name__ == "__main__":
    main(*sys.argv[1:3])
