#!/usr/bin/env python3
"""Nappe musicale de fond, entièrement synthétisée (aucun droit tiers).

Quatre accords en ré majeur (Dmaj9, Bm9, Gmaj9, Asus2), 8 s chacun, voix légèrement désaccordées,
filtre passe-bas doux, arpège discret, souffle de houle. Stéréo 48 kHz.
Usage : .venv-scraping/bin/python video/musique.py <durée_s> <sortie.wav>
"""
import sys
import wave

import numpy as np

SR = 48000


def note(n):
    return 440.0 * 2 ** ((n - 69) / 12)


ACCORDS = [[50, 57, 62, 66, 69, 76], [47, 54, 62, 66, 69, 73], [43, 55, 59, 62, 66, 69], [45, 57, 59, 64, 69, 71]]
DUREE_ACCORD = 8.0


def enveloppe(n, attaque, relache):
    e = np.ones(n)
    a, r = int(attaque * SR), int(relache * SR)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def passe_bas(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):          # un pôle, suffisant pour adoucir
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def main(duree, sortie):
    n_total = int(duree * SR)
    g, d = np.zeros(n_total), np.zeros(n_total)
    rng = np.random.default_rng(7)
    t_acc = int(DUREE_ACCORD * SR)
    k = 0
    for debut in range(0, n_total, t_acc):
        acc = ACCORDS[k % len(ACCORDS)]
        k += 1
        n = min(int((DUREE_ACCORD + 2.5) * SR), n_total - debut)
        t = np.arange(n) / SR
        env = enveloppe(n, 2.2, 3.0)
        for j, m in enumerate(acc):
            f = note(m)
            for det, pan in ((-0.12, 0.3), (0.12, 0.7)):
                s = np.sin(2 * np.pi * (f + det) * t) * 0.6 + np.sin(2 * np.pi * 2 * (f + det) * t) * 0.12
                amp = 0.05 * env * (0.9 if j else 1.2)
                g[debut:debut + n] += s * amp * (1 - pan)
                d[debut:debut + n] += s * amp * pan
        # arpège discret : une note de l'accord toutes les 1 s, attaque douce
        for i in range(8):
            p = debut + int(i * SR)
            if p >= n_total:
                break
            m = acc[2 + (i % 4)] + 12
            ln = min(int(1.6 * SR), n_total - p)
            tt = np.arange(ln) / SR
            s = np.sin(2 * np.pi * note(m) * tt) * np.exp(-tt * 2.6) * (1 - np.exp(-tt * 60)) * 0.035
            pan = 0.35 + 0.3 * (i % 2)
            g[p:p + ln] += s * (1 - pan)
            d[p:p + ln] += s * pan
    # souffle de houle : bruit filtré, modulé lentement
    bruit = passe_bas(rng.normal(0, 1, n_total), 500)
    houle = 0.5 + 0.5 * np.sin(2 * np.pi * np.arange(n_total) / SR / 9.0)
    g += bruit * 0.012 * houle
    d += np.roll(bruit, 2400) * 0.012 * houle
    st = np.stack([passe_bas(g, 3200), passe_bas(d, 3200)], axis=1)
    fondu = enveloppe(n_total, 2.5, 4.0)[:, None]
    st = st * fondu
    st = st / np.max(np.abs(st)) * 0.8
    with wave.open(sortie, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print(sortie, f"{duree:.1f} s")


if __name__ == "__main__":
    main(float(sys.argv[1]), sys.argv[2])
