#!/usr/bin/env python3
"""Maak de deelafbeelding (website/assets/og.png, 1200x630) en de README-banner (docs/images/banner.webp,
1600x900) opnieuw: een foto van de bovenkant van de website zelf, in donker.

Zo zijn ze altijd gelijk aan de site (zelfde tekst, zelfde taal, echte schermfoto's van BugOS), in plaats
van met de hand gemaakte plaatjes die achterblijven.

    python3 tools/website/og.py            (bouw eerst de site: python3 tools/website/build.py)

Nodig: een Chromium-browser die zonder venster kan draaien (Chrome, Chromium of Edge) en Pillow.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website" / "index.html"
KANDIDATEN = [
    "chromium", "chromium-browser", "google-chrome", "chrome", "msedge",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def browser() -> str:
    for k in KANDIDATEN:
        pad = shutil.which(k) or (k if os.path.isfile(k) else None)
        if pad:
            return pad
    sys.exit("Geen Chromium, Chrome of Edge gevonden.")


def foto(breed: int, hoog: int, schaal: int, doel: Path) -> None:
    """Foto van de bovenkant van de site in donker (?theme=dark zet het donkere thema, zie page.html)."""
    with tempfile.TemporaryDirectory() as tmp:
        uit = Path(tmp) / "foto.png"
        url = SITE.resolve().as_uri() + "?theme=dark"
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--force-device-scale-factor={schaal}", f"--window-size={breed},{hoog}",
                        "--virtual-time-budget=4000", f"--screenshot={uit}", url],
                       check=True, capture_output=True, timeout=120)
        im = Image.open(uit).convert("RGB").resize((breed, hoog), Image.LANCZOS)
        doel.parent.mkdir(parents=True, exist_ok=True)
        if doel.suffix == ".webp":
            im.save(doel, quality=88, method=6)
        else:
            im.save(doel, optimize=True)
        print(doel.relative_to(ROOT), im.size)


def main() -> int:
    if not SITE.exists():
        sys.exit("Eerst de site bouwen: python3 tools/website/build.py")
    foto(1200, 630, 2, ROOT / "website" / "assets" / "og.png")
    foto(1600, 900, 2, ROOT / "docs" / "images" / "banner.webp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
