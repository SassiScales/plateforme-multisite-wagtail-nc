#!/usr/bin/env python3
"""Musique du film, entièrement synthétisée (aucun droit tiers), calée sur les transformations.

100 battements par minute (une mesure = 2,4 s). Nappe d'accords en ré majeur, arpège en doubles croches,
basse, grosse caisse douce et charleston à partir de la 2e mesure ; à chaque transformation du film, une
montée de souffle avant le temps puis un impact grave et un scintillement. Stéréo 48 kHz.
Usage : .venv-scraping/bin/python musique_film.py <durée_s> <sortie.wav>
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 48000
BPM = 100
TEMPS = 60 / BPM
MESURE = 4 * TEMPS
TRANSFORMATIONS = [4.8, 9.6, 14.4, 19.2, 24.0, 28.8, 33.6, 38.4, 43.2, 45.6, 52.8]
FIN_RYTHME = 52.8
ACCORDS = [[50, 57, 62, 66, 69, 76], [47, 54, 62, 66, 69, 73], [43, 55, 59, 62, 66, 69], [45, 57, 59, 64, 69, 71]]
rng = np.random.default_rng(3)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def filtre(x, fc, type_="low", ordre=2):
    b, a = butter(ordre, fc / (SR / 2), btype=type_)
    return lfilter(b, a, x)


def poser(piste, debut, son, gain=1.0, pan=0.5):
    i = int(debut * SR)
    if i >= piste.shape[0]:
        return
    n = min(len(son), piste.shape[0] - i)
    piste[i:i + n, 0] += son[:n] * gain * (1 - pan) * 2
    piste[i:i + n, 1] += son[:n] * gain * pan * 2


def pad(duree, notes):
    t = np.arange(int(duree * SR)) / SR
    s = sum(np.sin(2 * np.pi * (hz(m) + d) * t) for m in notes for d in (-.15, .15))
    env = np.minimum(1, t / 1.2) * np.minimum(1, (duree - t) / 1.2)
    return filtre(s * env, 2400) / len(notes) / 2


def pluck(f, duree=.45):
    t = np.arange(int(duree * SR)) / SR
    s = (np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 9) * (1 - np.exp(-t * 400))
    return s


def basse(f, duree):
    t = np.arange(int(duree * SR)) / SR
    s = np.tanh(2.2 * np.sin(2 * np.pi * f * t)) * np.exp(-t * 3.2) * (1 - np.exp(-t * 300))
    return filtre(s, 600)


def caisse():
    t = np.arange(int(.35 * SR)) / SR
    f = 45 + 80 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def charley():
    t = np.arange(int(.06 * SR)) / SR
    return filtre(rng.normal(0, 1, len(t)), 7000, "high") * np.exp(-t * 70)


def montee(duree=1.4):
    t = np.arange(int(duree * SR)) / SR
    s = filtre(rng.normal(0, 1, len(t)), 1800, "high") * (t / duree) ** 2.2
    return s


def impact():
    t = np.arange(int(1.6 * SR)) / SR
    grave = np.sin(2 * np.pi * (38 + 30 * np.exp(-t * 9)) * t) * np.exp(-t * 3)
    scint = sum(np.sin(2 * np.pi * hz(m) * t) for m in (86, 90, 93)) * np.exp(-t * 2.2) * .25
    return grave + scint


def main(duree, sortie):
    n = int(duree * SR)
    mus = np.zeros((n, 2))
    nb_mesures = int(np.ceil(duree / MESURE))
    for m in range(nb_mesures):
        debut = m * MESURE
        acc = ACCORDS[m % 4]
        poser(mus, debut, pad(MESURE + 1.2, acc), .55)
        rythme = 1 <= m and debut < FIN_RYTHME
        dense = 3 <= m and debut < FIN_RYTHME
        for pas in range(16):                              # arpège en doubles croches
            if m == 0 and pas < 8:
                continue
            note = acc[2 + (pas * 3) % 4] + 12
            poser(mus, debut + pas * TEMPS / 4, pluck(hz(note)), .10 if dense else .07, .3 + .4 * (pas % 2))
        if rythme:
            for b in range(4):
                poser(mus, debut + b * TEMPS, caisse(), .55)
                poser(mus, debut + b * TEMPS, basse(hz(acc[0] - 12), TEMPS * .95), .32)
                poser(mus, debut + b * TEMPS + TEMPS / 2, basse(hz(acc[0] - 12), TEMPS * .45), .18)
        if dense:
            for c in range(8):
                poser(mus, debut + c * TEMPS / 2 + TEMPS / 4, charley(), .07, .65)
    for t in TRANSFORMATIONS:
        poser(mus, t - 1.4, montee(), .12)
        poser(mus, t, impact(), .45)
    mus = np.stack([filtre(mus[:, 0], 12000), filtre(mus[:, 1], 12000)], axis=1)
    env = np.minimum(1, np.arange(n) / SR / 1.5) * np.minimum(1, (n / SR - np.arange(n) / SR) / 3.5)
    mus *= env[:, None]
    mus = np.tanh(mus / np.max(np.abs(mus)) * 1.3) * .89
    with wave.open(sortie, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mus * 32767).astype("<i2").tobytes())
    print(sortie, f"{duree:.1f} s")


if __name__ == "__main__":
    main(float(sys.argv[1]), sys.argv[2])
