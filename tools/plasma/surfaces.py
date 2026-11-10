#!/usr/bin/env python3
"""Maakt de vlakken van de Plasma-stijl "bugos": taakbalk, pop-ups, tooltips, kaarten en lijstregels.

Schrijft naar system_files/usr/share/plasma/desktoptheme/bugos/:

    dialogs/background, widgets/panel-background, widgets/tooltip, widgets/background,
    widgets/translucentbackground, widgets/plasmoidheading, widgets/tasks, widgets/viewitem,
    widgets/listitem, widgets/frame, widgets/margins-highlight
    en dezelfde set als Breeze in opaque/, solid/ en translucent/.

Vormtaal (docs/BRAND.md): rustige, dichte vlakken in de vensterkleur met een haarlijn
(tekstkleur, 10 %) en een zachte brede schaduw, zoals de kaarten in de BugOS-apps.
Pop-ups 22 px hoeken, taakbalk 16, kaarten 16, tooltips en menu's 12. Aanwijzen is een
zachte tint, gekozen is zacht rood (zoals het gekozen onderdeel in de zijbalk) en de
actieve taak krijgt een kort rood streepje onderaan. Kleuren lopen via de ColorScheme-
klassen van KSvg, zodat licht en donker vanzelf volgen; alleen de schaduw is zwart.

De element-id's zijn de API van KSvg en Plasma. Ze volgen de Breeze-bestanden: binnen een
bestand vult Plasma niets aan uit Breeze. Een paar id's zijn extra (taakknoppen bij
aanwijzen, marges per richting); Plasma 6 zoekt die eerst en valt anders terug.

Gebruik:
    python3 tools/plasma/surfaces.py [uitmap]          # schrijf alle bestanden
    python3 tools/plasma/surfaces.py --controleer MAP  # vergelijk de id's met Breeze (uitgepakte .svg's)
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "design"))
from tokens import SYSTEM  # noqa: E402
from surfaces_items import frame, listitem, margins_highlight, tasks, viewitem  # noqa: E402
from surfaces_shapes import A_DOORZICHTIG, NEGEN, Blad  # noqa: E402
from surfaces_windows import (BALK, KAART_VENSTER, POPUP, TIP, plasmoidheading, translucentbackground,  # noqa: E402
                              vensterachtergrond, widgets_background)

UIT = SYSTEM / "usr" / "share" / "plasma" / "desktoptheme" / "bugos"


# ------------------------------------------------------------------ alles ---

def bestanden() -> dict[str, Blad]:
    """Alle bestanden: pad (zonder .svg) -> blad."""
    uit: dict[str, Blad] = {}
    # pop-ups en dialogen
    uit["dialogs/background"] = vensterachtergrond("pop-up", POPUP, alfa=1.0)
    uit["translucent/dialogs/background"] = vensterachtergrond("pop-up (met vervaging)", POPUP, alfa=A_DOORZICHTIG)
    uit["solid/dialogs/background"] = vensterachtergrond("pop-up (dicht)", POPUP, alfa=1.0)
    uit["opaque/dialogs/background"] = vensterachtergrond("pop-up (zonder compositing)", POPUP, alfa=1.0,
                                                          schaduw=False, inset=False, basis=True)
    # taakbalk
    uit["widgets/panel-background"] = vensterachtergrond("taakbalk", BALK, alfa=1.0, dik=True)
    uit["translucent/widgets/panel-background"] = vensterachtergrond("taakbalk (met vervaging)", BALK,
                                                                     alfa=A_DOORZICHTIG, dik=True)
    uit["solid/widgets/panel-background"] = vensterachtergrond("taakbalk (dicht)", BALK, alfa=1.0, dik=True)
    uit["opaque/widgets/panel-background"] = vensterachtergrond("taakbalk (zonder compositing)", BALK, alfa=1.0,
                                                                dik=True, schaduw=False, inset=False, basis=True)
    # tooltips (solid/ is ook het menu van Plasma)
    uit["widgets/tooltip"] = vensterachtergrond("tooltip", TIP, alfa=1.0)
    uit["translucent/widgets/tooltip"] = vensterachtergrond("tooltip (met vervaging)", TIP, alfa=A_DOORZICHTIG)
    uit["solid/widgets/tooltip"] = vensterachtergrond("tooltip en menu (dicht)", TIP, alfa=1.0)
    uit["opaque/widgets/tooltip"] = vensterachtergrond("tooltip (zonder compositing)", TIP, alfa=1.0,
                                                       schaduw=False, inset=False, basis=True)
    # kaarten
    uit["widgets/background"] = widgets_background("kaart op het bureaublad", vervaagd=False)
    uit["translucent/widgets/background"] = widgets_background("kaart op het bureaublad (met vervaging)",
                                                               vervaagd=True)
    uit["solid/widgets/background"] = vensterachtergrond("kaart (dicht)", KAART_VENSTER, alfa=1.0,
                                                         prive_schaduw=True)
    uit["widgets/translucentbackground"] = translucentbackground()
    # binnen de pop-ups en op de taakbalk
    uit["widgets/plasmoidheading"] = plasmoidheading()
    uit["widgets/viewitem"] = viewitem()
    uit["widgets/listitem"] = listitem()
    uit["widgets/frame"] = frame()
    uit["widgets/margins-highlight"] = margins_highlight()
    uit["widgets/tasks"] = tasks()
    return uit


def schrijf(doel: Path = UIT) -> list[Path]:
    geschreven = []
    for rel, blad in bestanden().items():
        p = doel / f"{rel}.svg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(blad.tekst(), encoding="utf-8", newline="\n")
        geschreven.append(p)
    return geschreven


# ------------------------------------------------------------- controle ---

INKSCAPE = re.compile(r"^(rect|path|g|stop|linearGradient|radialGradient|svg|defs|namedview|grid|text|tspan|use|"
                      r"circle|ellipse|filter|feGaussianBlur|metadata|layer|clipPath|mask|image|perspective|title|"
                      r"guide|pattern)[-_]?\d+([-_.]\d+)*$")


def ids_van(pad_: Path) -> set[str]:
    return {el.get("id") for el in ET.parse(pad_).iter() if el.get("id")}


def api_ids(alle: set[str]) -> set[str]:
    """De id's die ertoe doen: zonder Inkscape-namen en zonder Inkscape-dubbelingen (naam-9)."""
    uit = set()
    for i in alle:
        if INKSCAPE.match(i):
            continue
        m = re.match(r"^(.+)-\d+$", i)
        if m and m.group(1) in alle:
            continue
        uit.add(i)
    return uit


def kaders_kloppen(pad_: Path) -> list[str]:
    """Elk kader heeft 9 stukken en de hoeken passen op de randen (zo leest KSvg de maten)."""
    maten = {}
    for el in ET.parse(pad_).iter():
        eid = el.get("id")
        kind = list(el)
        if eid and el.tag.endswith("}g") and kind and kind[0].tag.endswith("}rect") and kind[0].get("fill") == "none":
            r = kind[0]
            maten[eid] = (float(r.get("width")), float(r.get("height")))
    namen = [n for rij in NEGEN for n in rij]
    fouten = []
    for eid in maten:
        if not eid.endswith("center") or eid in ("thick-center", "toolbutton-pressed-center", "shadow-center"):
            continue
        v = eid[:-len("center")]
        if any(v + n not in maten for n in namen):
            fouten.append(f"{v}*: niet alle negen stukken")
            continue
        m = {n: maten[v + n] for n in namen}
        L, R, T, B = m["left"][0], m["right"][0], m["top"][1], m["bottom"][1]
        goed = (m["topleft"] == (L, T) and m["topright"] == (R, T) and m["bottomleft"] == (L, B)
                and m["bottomright"] == (R, B) and m["top"][0] == m["center"][0] == m["bottom"][0]
                and m["left"][1] == m["center"][1] == m["right"][1])
        if not goed:
            fouten.append(f"{v}*: hoeken passen niet op de randen")
    return fouten


def controleer(breeze: Path, doel: Path = UIT) -> int:
    fouten = 0
    for rel in bestanden():
        mijn = doel / f"{rel}.svg"
        if mijn.exists():
            for fout in kaders_kloppen(mijn):
                fouten += 1
                print(f"FOUT  {rel}: {fout}")
        ref = breeze / f"{rel}.svg"
        if not ref.exists():
            print(f"??    {rel}: geen Breeze-bestand om mee te vergelijken")
            continue
        if not mijn.exists():
            print(f"FOUT  {rel}: ontbreekt")
            fouten += 1
            continue
        nodig = api_ids(ids_van(ref))
        heb = ids_van(mijn)
        mist = sorted(nodig - heb)
        extra = sorted(api_ids(heb) - nodig)
        if mist:
            fouten += 1
            print(f"FOUT  {rel}: mist {len(mist)}: {' '.join(mist)}")
        else:
            print(f"ok    {rel}: alle {len(nodig)} id's van Breeze" + (f", plus {len(extra)} eigen" if extra else ""))
    return fouten


def main(args: list[str]) -> int:
    if args and args[0] == "--controleer":
        breeze = Path(args[1]) if len(args) > 1 else None
        if not breeze or not breeze.is_dir():
            print("gebruik: surfaces.py --controleer <map met de uitgepakte Breeze-stijl (.svg)> [uitmap]")
            return 2
        return 1 if controleer(breeze, Path(args[2]) if len(args) > 2 else UIT) else 0
    doel = Path(args[0]) if args else UIT
    for p in schrijf(doel):
        print("geschreven:", p.relative_to(doel).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
