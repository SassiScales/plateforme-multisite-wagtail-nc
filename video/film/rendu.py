#!/usr/bin/env python3
"""Rend le film image par image (30 i/s, 1920×1080) puis l'assemble avec la musique.

Usage : .venv-scraping/bin/python video/film/rendu.py [--apercu]   (--apercu : une image par formation)
"""
import base64
import json
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
FPS = 30


def main():
    apercu = "--apercu" in sys.argv
    donnees = open(os.path.join(ICI, "donnees.json")).read()
    capture = base64.b64encode(open(os.path.join(ICI, "..", "..", "captures", "accueil.jpg"), "rb").read()).decode()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.add_init_script(f"window.__DONNEES = {donnees}; window.__CAPTURE = 'data:image/jpeg;base64,{capture}';")
        pg.goto("file://" + os.path.join(ICI, "film.html"))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_function("window.pret && window.pret()")
        duree = pg.evaluate("window.DUREE")
        if apercu:
            for t in [1.5, 3.0, 6.5, 12.0, 17.0, 23.0, 26.5, 29.0, 33.5, 39.0, 44.0, 47.5, 52.0, 58.5]:
                pg.evaluate(f"render({t})")
                pg.screenshot(path=os.path.join(ICI, "apercu", f"t{t:05.1f}.jpg"), type="jpeg", quality=80)
            b.close()
            return
        images = os.path.join(ICI, "images")
        os.makedirs(images, exist_ok=True)
        for f in range(int(duree * FPS)):
            pg.evaluate(f"render({f / FPS})")
            pg.screenshot(path=os.path.join(images, f"{f:05d}.jpg"), type="jpeg", quality=92)
        b.close()
    muet = os.path.join(ICI, "film-muet.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(images, "%05d.jpg"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", muet], check=True)
    musique = os.path.join(ICI, "musique-film.wav")
    subprocess.run([sys.executable, os.path.join(ICI, "musique_film.py"), f"{duree:.2f}", musique], check=True)
    final = os.path.join(ICI, "film-plateforme-gnc.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", muet, "-i", musique, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final], check=True)
    print(final)


if __name__ == "__main__":
    main()
