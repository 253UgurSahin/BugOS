#!/usr/bin/env python3
"""BugOS-programmastijl voor KDE- en Qt-programma's (Kvantum), licht en donker.

Schrijft:
  system_files/usr/share/Kvantum/BugOS/BugOS.kvconfig + BugOS.svg              (licht)
  system_files/usr/share/Kvantum/BugOSDark/BugOSDark.kvconfig + .svg       (donker)
en zet in de KDE-kleurenschema's (BugOSLight.colors, BugOSDark.colors) de
kleuren die bij deze stijl horen: venster, kaart, knop en de zachte selectie.

Eén bron: alle kleuren en maten komen uit tools/design/tokens.py (dus uit
bugos_ui.py, net als de eigen BugOS-apps). Licht en donker komen uit dezelfde
code, zodat ze nooit uit elkaar lopen.

Hoe Kvantum werkt (kort): elk onderdeel (knop, invoerveld, lijst...) is een
"negenvlak" in de SVG: 4 hoeken, 4 randen en een binnenkant, per toestand
(normal = rust, focused = muis erop, pressed = ingedrukt, toggled = aan/gekozen,
disabled = uit). Ronde hoeken van 12 px krijgen we met "frame.expansion": dan
tekent Kvantum de hoeken op expansion/2 px, als het element expand-<naam>-<toestand>
bestaat; zo blijft de binnenruimte klein (frame.top=3) en worden de hoeken toch rond.

Gebruik:  python3 tools/kvantum/make.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "design"))

from tokens import REPO  # noqa: E402
from colorscheme import schema_bijwerken, schema_kleuren  # noqa: E402
from kvconfig import maak_kvconfig  # noqa: E402
from palette import PALETTEN, THEMAS, contrast  # noqa: E402
from svg_theme import maak_svg  # noqa: E402

KVANTUM = REPO / "system_files" / "usr" / "share" / "Kvantum"
SCHEMAS = REPO / "system_files" / "usr" / "share" / "color-schemes"


def main() -> int:
    for thema, (kvnaam, schema) in THEMAS.items():
        k = PALETTEN[thema]
        doel = KVANTUM / kvnaam
        doel.mkdir(parents=True, exist_ok=True)
        (doel / f"{kvnaam}.kvconfig").write_text(maak_kvconfig(thema, k), encoding="utf-8", newline="\n")
        (doel / f"{kvnaam}.svg").write_text(maak_svg(k), encoding="utf-8", newline="\n")
        pad = SCHEMAS / f"{schema}.colors"
        pad.write_text(schema_bijwerken(pad, schema_kleuren(thema, k)), encoding="utf-8", newline="\n")
        print(f"{thema}: {doel.relative_to(REPO)}  selectie {k['selectie']} / tekst {k['selectie_tekst']} "
              f"(contrast {contrast(k['selectie_tekst'], k['selectie']):.2f}:1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
