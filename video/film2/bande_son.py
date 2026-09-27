#!/usr/bin/env python3
"""Bande-son du film produit : musique en parties + bruitages propres à chaque action (cues.json).

Tout est synthétisé (aucun droit tiers). Tempo 100, ré majeur.
Parties : intro (nappe) · groove léger (sites, recherche) · montée (tableaux, cartes, communes) ·
respiration (pages) · relance (migration, confiance) · final (accord tenu).
Usage : .venv-scraping/bin/python bande_son.py <durée_s> <cues.json> <sortie.wav>
"""
import json
import sys
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 48000
TEMPS = 0.6
MESURE = 2.4
ACCORDS = [[50, 57, 62, 66, 69, 76], [47, 54, 62, 66, 69, 73], [43, 55, 59, 62, 66, 69], [45, 57, 59, 64, 69, 71]]
GAMME = [62, 64, 66, 69, 71, 74, 76, 78, 81, 83, 86]      # ré majeur pentatonique élargie
rng = np.random.default_rng(5)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def filtre(x, fc, t="low", o=2):
    b, a = butter(o, float(np.clip(fc / (SR / 2), 1e-4, .999)), btype=t)
    return lfilter(b, a, x)


def env(n, att, dec):
    t = np.arange(n) / SR
    return (1 - np.exp(-t / max(att, 1e-4))) * np.exp(-t / dec)


def poser(p, t0, s, g=1.0, pan=.5):
    i = int(t0 * SR)
    if i < 0 or i >= len(p):
        return
    n = min(len(s), len(p) - i)
    p[i:i + n, 0] += s[:n] * g * (1 - pan) * 2
    p[i:i + n, 1] += s[:n] * g * pan * 2


def sinus(f, d, harm=((1, 1),)):
    t = np.arange(int(d * SR)) / SR
    return sum(a * np.sin(2 * np.pi * f * k * t) for k, a in harm)


# ------------------------------------------------------------------ bruitages
def touche(i):
    n = int(.045 * SR)
    s = filtre(rng.normal(0, 1, n), 3000 + (i % 5) * 700, "high") * env(n, .0005, .008)
    s += sinus(900 + (i % 4) * 140, .045) * env(n, .001, .006) * .4
    return s * .5


def clic():
    n = int(.08 * SR)
    return (sinus(1800, .08) * env(n, .0005, .012) + filtre(rng.normal(0, 1, n), 5000, "high") * env(n, .0003, .004)) * .6


def glisse(k):
    d = [.9, .7, 1.1, .8, 1.2, .6, 1.0, .75, 1.3, .9, .8][k % 11]
    n = int(d * SR)
    t = np.arange(n) / SR
    bruit = rng.normal(0, 1, n)
    f0, f1 = [(400, 3200), (2800, 500), (600, 2400), (3000, 800)][k % 4]
    fc = f0 * (f1 / f0) ** (t / d)
    out = np.zeros(n)
    for j in range(0, n, 512):                        # filtre balayé par tranches
        out[j:j + 512] = filtre(bruit[j:j + 512], fc[j], "low", 1)
    return out * np.sin(np.pi * t / d) ** 1.5 * .9


def point(i):
    m = GAMME[i % len(GAMME)] + (12 if i > 30 else 0)
    n = int(.35 * SR)
    return sinus(hz(m), .35, ((1, 1), (2, .3), (3, .1))) * env(n, .002, .09) * .45


def commune(i):
    m = GAMME[(i * 3) % len(GAMME)] - 12
    n = int(.5 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * hz(m) * t) + .5 * np.sin(2 * np.pi * hz(m) * 4 * t) * np.exp(-t * 30)) * env(n, .001, .12) * .5


def page(k):
    n = int(.28 * SR)
    t = np.arange(n) / SR
    s = filtre(rng.normal(0, 1, n), 1500 + k * 90, "high") * np.sin(np.pi * t / .28) ** 2
    return filtre(s, 6000) * .55


def redirection():
    n = int(.9 * SR)
    t = np.arange(n) / SR
    f = 300 * (6 ** (t / .9))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / .9) * .35 + glisse(0)[:n] * .5


def carillon(notes, d=1.6, g=.4):
    return sum(sinus(hz(m), d, ((1, 1), (2.76, .25), (5.4, .08))) * env(int(d * SR), .002, .5) for m in notes) * g


def badge(i):
    return carillon([81 + [0, 4, 7][i]], 1.0, .35)


def loupe_son():
    n = int(.5 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(200 + 900 * t / .5) / SR) * env(n, .01, .12) * .25


def tri():
    return carillon([74, 78], .6, .25)


def section(i):
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    grave = np.sin(2 * np.pi * (36 + 26 * np.exp(-t * 7)) * t) * np.exp(-t * 2.2)
    return grave * [.5, .6, .55, .6, .7, .55, .35, .7, .6, .8][i % 10]


# ------------------------------------------------------------------ musique
def pad(d, notes):
    t = np.arange(int(d * SR)) / SR
    s = sum(np.sin(2 * np.pi * (hz(m) + dd) * t) for m in notes for dd in (-.14, .14))
    return filtre(s * np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.2), 2600) / len(notes) / 2


def pluck(f, d=.4):
    t = np.arange(int(d * SR)) / SR
    return (np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 10) * (1 - np.exp(-t * 400))


def caisse(fort=1.0):
    t = np.arange(int(.35 * SR)) / SR
    return np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 10) * fort


def charley(ouvert=False):
    n = int((.18 if ouvert else .05) * SR)
    t = np.arange(n) / SR
    return filtre(rng.normal(0, 1, n), 7500, "high") * np.exp(-t * (18 if ouvert else 80))


def claque():
    n = int(.2 * SR)
    t = np.arange(n) / SR
    return filtre(rng.normal(0, 1, n), 1800, "high") * np.exp(-t * 25) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * .5


def basse(f, d):
    t = np.arange(int(d * SR)) / SR
    return filtre(np.tanh(2 * np.sin(2 * np.pi * f * t)) * np.exp(-t * 3) * (1 - np.exp(-t * 300)), 700)


def partie(t):
    """0 intro, 1 groove léger, 2 montée, 3 respiration, 4 relance, 5 final"""
    for lim, p in ((7.0, 0), (26.2, 1), (54.0, 2), (62.4, 3), (81.8, 4)):
        if t < lim:
            return p
    return 5


def main(duree, cues_f, sortie):
    n = int(duree * SR)
    mus, sfx = np.zeros((n, 2)), np.zeros((n, 2))
    for m in range(int(np.ceil(duree / MESURE))):
        t0 = m * MESURE
        p = partie(t0)
        acc = ACCORDS[m % 4] if p != 3 else [ACCORDS[m % 4][0]] + ACCORDS[(m + 2) % 4][2:]
        poser(mus, t0, pad(MESURE + 1.2, acc), .5 if p in (0, 3, 5) else .38)
        if p == 5:
            continue
        # arpège : densité selon la partie
        pas = {0: 4, 1: 8, 2: 16, 3: 4, 4: 16}[p]
        for k in range(pas):
            note = acc[(2 + (k * 3) % 4) % len(acc)] + (12 if p in (2, 4) else 0)
            poser(mus, t0 + k * MESURE / pas, pluck(hz(note)), .09 if p in (2, 4) else .07, .3 + .4 * (k % 2))
        if p in (1, 2, 4):
            for b in range(4):
                poser(mus, t0 + b * TEMPS, caisse(.8 if p == 1 else 1.0), .5)
                poser(mus, t0 + b * TEMPS, basse(hz(acc[0] - 12), TEMPS * .9), .3)
                if p in (2, 4):
                    poser(mus, t0 + b * TEMPS + TEMPS / 2, basse(hz(acc[0] - 12 + (7 if b % 2 else 0)), TEMPS * .4), .18)
            for c in range(8):
                poser(mus, t0 + c * TEMPS / 2 + TEMPS / 4, charley(c % 4 == 3 and p == 4), .06, .65)
            if p in (2, 4):
                for b in (1, 3):
                    poser(mus, t0 + b * TEMPS, claque(), .12, .45)
    poser(mus, 81.8, carillon([62, 66, 69, 74, 78], 5.0, .5), 1.0)
    for t, typ, prm in json.load(open(cues_f)):
        s, g, pan = {
            "touche": (lambda: (touche(prm), .5, .45 + .1 * (prm % 3) / 2)),
            "clic": (lambda: (clic(), .7, .55)),
            "glisse": (lambda: (glisse(prm), .45, .3 + .4 * (prm % 2))),
            "point": (lambda: (point(prm), .35, .25 + .5 * ((prm * 7) % 10) / 10)),
            "commune": (lambda: (commune(prm), .35, .3 + .4 * ((prm * 3) % 10) / 10)),
            "page": (lambda: (page(prm), .5, .6)),
            "redirection": (lambda: (redirection(), .6, .5)),
            "succes": (lambda: (carillon([74, 78, 81, 86], 1.8, .45), 1.0, .5)),
            "badge": (lambda: (badge(prm), .8, .4 + .1 * prm)),
            "loupe": (lambda: (loupe_son(), .7, .5)),
            "tri": (lambda: (tri(), .8, .6)),
            "section": (lambda: (section(prm), .8, .5)),
            "final": (lambda: (section(9), .9, .5)),
        }[typ]()
        poser(sfx, t, s, g, pan)
    mix = mus * .8 + sfx
    mix = np.stack([filtre(mix[:, 0], 14000), filtre(mix[:, 1], 14000)], axis=1)
    e = np.minimum(1, np.arange(n) / SR / 1.0) * np.minimum(1, (duree - np.arange(n) / SR) / 3.0)
    mix *= e[:, None]
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.4) * .9
    with wave.open(sortie, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    print(sortie, f"{duree:.1f} s")


if __name__ == "__main__":
    main(float(sys.argv[1]), sys.argv[2], sys.argv[3])
