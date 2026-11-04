#!/usr/bin/env python3
"""Contactvel van het BugOS-pictogramthema, met Breeze ernaast ter vergelijking.

    proef_iconen.py [naam ...]       (zonder namen: alles wat in het thema zit)

Per map een plaatje: /uit/iconen-<map>-<thema>.png. Eenkleurige pictogrammen
krijgen de tekstkleur van licht of donker, net zoals KDE ze inkleurt.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tokens import KLEUREN  # noqa: E402

THEMA = os.environ.get("BUGOS_THEMA", "licht")
K = KLEUREN["donker" if THEMA == "donker" else "licht"]
UIT = Path(os.environ.get("BUGOS_UIT", "/uit"))
BUGOS = Path("/usr/share/icons/BugOS")
BREEZE = Path("/usr/share/icons/breeze-dark" if THEMA == "donker" else "/usr/share/icons/breeze")
LETTER = next((str(p) for p in Path("/usr/share/fonts/bugos").glob("Inter*.ttf")), None)

STIJL = re.compile(r'<style[^>]*id="current-color-scheme"[^>]*>.*?</style>', re.S)


def kleur_in(svg: str) -> str:
    nieuw = ('<style id="current-color-scheme" type="text/css">'
             f".ColorScheme-Text{{color:{K['tekst']};}}.ColorScheme-Background{{color:{K['achter']};}}"
             f".ColorScheme-Highlight{{color:{K['accent']};}}.ColorScheme-ViewText{{color:{K['tekst']};}}"
             f".ColorScheme-ViewBackground{{color:{K['vlak']};}}.ColorScheme-ButtonText{{color:{K['tekst']};}}"
             f".ColorScheme-NegativeText{{color:{K['fout']};}}.ColorScheme-PositiveText{{color:{K['goed']};}}"
             f".ColorScheme-NeutralText{{color:{K['let_op']};}}</style>")
    return STIJL.sub(nieuw, svg, count=1)


def teken(pad: Path, px: int) -> Image.Image | None:
    try:
        svg = kleur_in(pad.read_text(encoding="utf-8", errors="replace"))
        png = subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px)], input=svg.encode(),
                             capture_output=True, check=True).stdout
        return Image.open(io.BytesIO(png)).convert("RGBA")
    except (subprocess.CalledProcessError, OSError):
        return None


def zoek_breeze(naam: str, voorkeur: list[str]) -> Path | None:
    for m in voorkeur:
        p = BREEZE / m / f"{naam}.svg"
        if p.exists():
            return p.resolve()
    hits = sorted(BREEZE.glob(f"*/*/{naam}.svg"))
    return hits[0].resolve() if hits else None


def vel(mapnaam: str, namen: list[str]) -> Path:
    groot = 48 if mapnaam.split("/")[0] in ("apps", "places", "mimetypes", "preferences", "categories") else 22
    maten = [16, 22, 32, 48] if groot == 22 else [22, 48, 96]
    cel_b, cel_h = max(170, sum(maten) + 16 * len(maten) + 60), max(maten) + 46
    kol = 5
    rijen = (len(namen) + kol - 1) // kol
    im = Image.new("RGB", (kol * cel_b + 24, rijen * cel_h + 64), K["achter"])
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(LETTER, 12) if LETTER else ImageFont.load_default()
    fk = ImageFont.truetype(LETTER, 16) if LETTER else ImageFont.load_default()
    d.text((12, 12), f"BugOS {mapnaam}  ({THEMA})   rechts in elke cel: Breeze ter vergelijking",
           fill=K["tekst"], font=fk)
    for i, naam in enumerate(namen):
        x0, y0 = 12 + (i % kol) * cel_b, 44 + (i // kol) * cel_h
        d.rounded_rectangle([x0, y0, x0 + cel_b - 8, y0 + cel_h - 8], 12, fill=K["vlak"], outline=K["rand"])
        x = x0 + 8
        bron = BUGOS / mapnaam / f"{naam}.svg"
        for px in maten:
            ic = teken(bron, px)
            if ic:
                im.paste(ic, (x, y0 + 6 + (max(maten) - px) // 2), ic)
            x += px + 12
        br = zoek_breeze(naam, [mapnaam.replace("scalable", s) for s in ("22", "24", "48", "32", "64", "16")])
        if br:
            ic = teken(br, maten[1])
            if ic:
                im.paste(ic, (x0 + cel_b - 8 - maten[1] - 8, y0 + 6), ic)
        d.text((x0 + 8, y0 + cel_h - 30), naam[:30], fill=K["tekst2"], font=f)
    doel = UIT / f"iconen-{mapnaam.replace('/', '-')}-{THEMA}.png"
    im.save(doel)
    return doel


def main(namen: list[str]) -> int:
    if not (BUGOS / "index.theme").exists():
        print("Geen BugOS-pictogramthema gevonden (eerst: python3 tools/iconen/maak.py)")
        return 1
    # "onderdeel=status": alleen wat dat onderdeel maakte (tools/iconen/lijsten/status.txt).
    alleen_bestanden: set[str] | None = None
    for n in list(namen):
        if n.startswith("onderdeel="):
            namen.remove(n)
            lijst = Path("/repo/tools/iconen/lijsten") / f"{n.split('=', 1)[1]}.txt"
            alleen_bestanden = set(lijst.read_text(encoding="utf-8").split()) if lijst.exists() else set()
    per_map: dict[str, list[str]] = {}
    for pad in sorted(BUGOS.rglob("*.svg")):
        naam = pad.stem
        if naam.endswith("-symbolic"):
            continue
        if namen and naam not in namen:
            continue
        rel = pad.relative_to(BUGOS).as_posix()
        if alleen_bestanden is not None and rel not in alleen_bestanden:
            continue
        per_map.setdefault(pad.parent.relative_to(BUGOS).as_posix(), []).append(naam)
    for m, lijst in per_map.items():
        # Grote vellen in stukken van 60, zodat ze leesbaar blijven.
        for start in range(0, len(lijst), 60):
            stuk = lijst[start:start + 60]
            doel = vel(m if start == 0 else m, stuk)
            if start:
                doel = doel.rename(doel.with_name(doel.stem + f"-{start // 60 + 1}.png"))
            print(doel, len(stuk))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
