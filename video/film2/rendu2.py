#!/usr/bin/env python3
"""Rendu du film produit, image par image (30 i/s), puis bande-son (musique + bruitages) calée sur window.CUES.

Usage : .venv-scraping/bin/python rendu2.py [--apercu t1,t2,...]
"""
import json
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
FPS = 30


def main():
    apercu = None
    if "--apercu" in sys.argv:
        apercu = [float(x) for x in sys.argv[sys.argv.index("--apercu") + 1].split(",")]
    donnees = open(os.path.join(ICI, "..", "film", "donnees.json")).read()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.add_init_script(f"window.__DONNEES = {donnees};")
        pg.goto("file://" + os.path.join(ICI, "film2.html"))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_function("window.pret && window.pret()", timeout=60000)
        duree = pg.evaluate("window.DUREE")
        json.dump(pg.evaluate("window.CUES"), open(os.path.join(ICI, "cues.json"), "w"))
        if apercu:
            os.makedirs(os.path.join(ICI, "apercu"), exist_ok=True)
            for t in apercu:
                pg.evaluate(f"render({t})")
                pg.wait_for_timeout(60)
                pg.screenshot(path=os.path.join(ICI, "apercu", f"t{t:05.1f}.jpg"), type="jpeg", quality=80)
            b.close()
            return
        images = os.path.join(ICI, "images")
        os.makedirs(images, exist_ok=True)
        de, a_ = 0, int(duree * FPS)
        if "--plage" in sys.argv:                       # re-rendre seulement une plage (secondes)
            x, y = sys.argv[sys.argv.index("--plage") + 1].split(",")
            de, a_ = int(float(x) * FPS), int(float(y) * FPS)
        if de > 0:
            pg.evaluate(f"render({(de - 1) / FPS})")
        for f in range(de, a_):
            pg.evaluate(f"render({f / FPS})")
            pg.screenshot(path=os.path.join(images, f"{f:05d}.jpg"), type="jpeg", quality=92)
        b.close()
    muet = os.path.join(ICI, "film2-muet.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(images, "%05d.jpg"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", muet], check=True)
    son = os.path.join(ICI, "bande-son.wav")
    subprocess.run([sys.executable, os.path.join(ICI, "bande_son.py"), f"{duree:.2f}", os.path.join(ICI, "cues.json"), son], check=True)
    final = os.path.join(ICI, "film-produit-gnc.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", muet, "-i", son, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final], check=True)
    print(final)


if __name__ == "__main__":
    main()
