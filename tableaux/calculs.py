"""Calculs sur les lignes d'une source : repères chiffrés, facettes, cartes. Aucun chiffre n'est saisi à la main."""
import json
import os
import unicodedata
from collections import Counter

from .carte import dans_cadre, projeter

COMMUNES = json.load(open(os.path.join(os.path.dirname(__file__), "communes_nc.json")))


def nombre(v):
    try:
        return float(str(v).replace(",", ".").replace(" ", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def fr(x, dec=0, sep="\u00a0"):
    """Nombre à la française. Espace insécable normale : l'espace fine est trop étroite dans la police des titres."""
    s = f"{x:,.{dec}f}".replace(",", sep).replace(".", ",")
    return s


def indicateur(conf, donnees):
    """donnees : liste de dicts. Renvoie (valeur affichée, libellé) ou None si incalculable."""
    t, ch, ch2, lib = conf["type"], conf.get("champ"), conf.get("champ2"), conf.get("libelle") or ""
    if t == "nombre":
        return fr(len(donnees)), lib or "lignes"
    vals = [d.get(ch) for d in donnees if d.get(ch) not in (None, "")]
    if t == "distincts":
        return fr(len(set(map(str, vals)))), lib or f"valeurs distinctes de {ch}"
    if t == "frequent":
        if not vals:
            return None
        v, n = Counter(map(str, vals)).most_common(1)[0]
        return v.capitalize() if v.isupper() else v, lib or f"le plus fréquent ({fr(n)} lignes)"
    if t == "moyenne":
        nums = [n for n in map(nombre, vals) if n is not None]
        return (fr(sum(nums) / len(nums)), lib) if nums else None
    if t == "ecart":
        paires = [(nombre(d.get(ch)), nombre(d.get(ch2))) for d in donnees]
        ecarts = [(b - a) / a * 100 for a, b in paires if a and b is not None and a > 0]
        if not ecarts:
            return None
        m = sum(ecarts) / len(ecarts)
        return f"{'+' if m >= 0 else ''}{fr(m, 1)} %", lib or f"écart moyen de {ch2} par rapport à {ch}"
    return None


def facettes(donnees, champ, n=10):
    c = Counter(str(d.get(champ)) for d in donnees if d.get(champ) not in (None, "") and not isinstance(d.get(champ), (list, dict)))
    return c.most_common(n)


def points(lignes, libelle_champ, max_points=1500):
    """Points projetés sur la carte commune : [(x, y, libellé, identifiant)]."""
    out = []
    for l in lignes:
        if l.lat is None or l.lon is None or not dans_cadre(l.lon, l.lat):
            continue
        x, y = projeter(l.lon, l.lat)
        out.append((round(x, 1), round(y, 1), str(l.donnees.get(libelle_champ) or ""), l.identifiant))
        if len(out) >= max_points:
            break
    return out


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return "".join(ch for ch in s if ch.isalnum())


_INDEX = {_norm(c["nom_maj"]): code for code, c in COMMUNES["communes"].items()}
_INDEX.update({_norm(c["nom"]): code for code, c in COMMUNES["communes"].items()})
# Variantes courantes dans les jeux de données
_INDEX.update({_norm("ILE DES PINS"): _INDEX.get(_norm("Ile des Pins")), _norm("L'ILE DES PINS"): _INDEX.get(_norm("Ile des Pins")),
               _norm("HOUAILOU"): _INDEX.get(_norm("Houailou")), _norm("KAALA-GOMEN"): _INDEX.get(_norm("Kaala Gomen"))})

# Échelle séquentielle d'une seule teinte (lagon), du clair au foncé.
PALETTE = ["#e3f1f7", "#a9d6e8", "#5fb3d3", "#1f86b3", "#00496e"]


def par_commune(donnees, champ):
    """Comptes par commune (code INSEE) + lignes non rattachées."""
    c, hors = Counter(), 0
    for d in donnees:
        code = _INDEX.get(_norm(d.get(champ, "")))
        if code:
            c[code] += 1
        else:
            hors += 1
    return c, hors


def classes(valeurs, n=5):
    """Seuils par quantiles (bornes supérieures), sans doublon."""
    v = sorted(x for x in valeurs if x > 0)
    if not v:
        return []
    seuils = sorted(set(v[min(len(v) - 1, int(len(v) * (i + 1) / n))] for i in range(n)))
    return seuils


def couleur(v, seuils):
    if v <= 0 or not seuils:
        return "#f3f1ec"
    for i, s in enumerate(seuils):
        if v <= s:
            return PALETTE[min(i, len(PALETTE) - 1) if len(seuils) >= len(PALETTE) else round(i * (len(PALETTE) - 1) / max(len(seuils) - 1, 1))]
    return PALETTE[-1]
