"""BugOS Knipprogramma: de logica zonder vensters (tools/test_knip.py test dit los).

Zoals het Knipprogramma van Windows 11: Print Screen (of Windows+Shift+S) bevriest het scherm, je sleept een stuk,
en dat stuk staat meteen op het klembord en in Afbeeldingen > Schermafbeeldingen. Daarna kun je erop tekenen.

De foto zelf maakt Spectacle van KDE, stil op de achtergrond (spectacle -b -n -f): op Wayland mag alleen een
programma dat KWin vertrouwt het scherm fotograferen, en Spectacle is dat. De rest (de keuze, het bijsnijden, het
tekenen, opslaan) doet BugOS zelf.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from bugos_base import t

# Voor de test: in plaats van Spectacle een vaste foto gebruiken.
BRON_VOOR_TEST = "BUGOS_KNIP_BRON"


def werkmap() -> Path:
    """Een eigen map voor de tijdelijke foto (alleen van jou: XDG_RUNTIME_DIR)."""
    basis = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(tempfile.mkdtemp(prefix="bugos-knip-", dir=basis))


def vang_alles(doel: Path, timeout: int = 20) -> bool:
    """Een foto van het hele bureaublad (alle schermen) in doel (PNG). False als het niet lukte."""
    bron = os.environ.get(BRON_VOOR_TEST)
    if bron:
        try:
            shutil.copyfile(bron, doel)
            return True
        except OSError:
            return False
    if not shutil.which("spectacle"):
        return False
    try:
        r = subprocess.run(["spectacle", "--background", "--nonotify", "--fullscreen", "--output", str(doel)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return False
    try:
        return r.returncode == 0 and doel.is_file() and doel.stat().st_size > 0
    except OSError:
        return False


def map_schermafbeeldingen() -> Path:
    """Afbeeldingen > Schermafbeeldingen (zoals Windows: Afbeeldingen > Schermopnamen), in de taal van de map."""
    from bugos_files_plekken import xdg_map
    return xdg_map("PICTURES", "Pictures") / t("Schermafbeeldingen", "Screenshots")


def nieuwe_naam(map_: Path, nu: datetime | None = None) -> Path:
    """'Schermafbeelding 2026-11-27 170512.png'; bestaat die al, dan '... (2).png'."""
    nu = nu or datetime.now()
    basis = f"{t('Schermafbeelding', 'Screenshot')} {nu:%Y-%m-%d %H%M%S}"
    pad = map_ / f"{basis}.png"
    n = 2
    while pad.exists():
        pad = map_ / f"{basis} ({n}).png"
        n += 1
    return pad


def factor(beeld_breed: int, beeld_hoog: int, virtueel_breed: int, virtueel_hoog: int) -> tuple[float, float]:
    """Hoeveel beeldpunten van de foto er in één beeldpunt van het bureaublad gaan (bij 150 %: 1,5)."""
    if virtueel_breed <= 0 or virtueel_hoog <= 0:
        return 1.0, 1.0
    return beeld_breed / virtueel_breed, beeld_hoog / virtueel_hoog


def naar_beeld(x: float, y: float, b: float, h: float, links: int, boven: int,
               fx: float, fy: float, beeld_breed: int, beeld_hoog: int) -> tuple[int, int, int, int]:
    """Een rechthoek op het bureaublad (x, y vanaf linksboven van alle schermen samen: links, boven) naar
    beeldpunten in de foto, binnen de foto gehouden. Geeft (x, y, breed, hoog)."""
    bx = max(0, min(beeld_breed, round((x - links) * fx)))
    by = max(0, min(beeld_hoog, round((y - boven) * fy)))
    ex = max(0, min(beeld_breed, round((x + b - links) * fx)))
    ey = max(0, min(beeld_hoog, round((y + h - boven) * fy)))
    return bx, by, max(0, ex - bx), max(0, ey - by)


def genoeg(b: float, h: float) -> bool:
    """Een sleep van een paar beeldpunten is een klik, geen knipsel."""
    return b >= 4 and h >= 4
