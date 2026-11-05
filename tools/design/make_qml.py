#!/usr/bin/env python3
"""Maakt Design.qml: de BugOS-ontwerptaal (kleuren, maten, letters) voor de QML-menu's.

Eén bron: KLEUREN en MATEN uit bugos_ui.py (via tokens.py). Het startmenu en het
snelmenu krijgen allebei precies hetzelfde bestand, zodat ze er net zo uitzien als
de eigen apps, de KDE-stijl en de Plasma-stijl.

    python3 tools/design/make_qml.py          # schrijf de bestanden
    python3 tools/design/make_qml.py --check  # geef fout als ze niet kloppen (CI)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tokens import KLEUREN, LETTERS, MATEN, ROOD_VERLOOP, ROOD_VERLOOP_DONKER, SYSTEM  # noqa: E402

DOELEN = [SYSTEM / "usr/share/plasma/plasmoids" / p / "contents/ui/Design.qml"
          for p in ("org.bugos.startmenu", "org.bugos.quickmenu")]

# Lettermaten in px, dezelfde als het stijlblad van bugos_ui.py.
LETTERMATEN = {
    "klein": 13,   # uitleg onder een regel, sectiekopjes
    "tekst": 14,   # gewone tekst en knoppen
    "rij": 15,     # de naam in een regel of tegel
    "kop": 20,     # kop van een pop-up of menu (zoals de app-naam in de zijbalk)
    "held": 26,    # de begroeting bovenin het startmenu
}

# Hoogtes in px, dezelfde als in de eigen apps.
HOOGTES = {
    "knopHoogte": 40,    # gewone knop (14 px tekst + 10 px boven en onder + rand)
    "veldHoogte": 44,    # zoek- en invoerveld
    "regelHoogte": 48,   # regel in een lijst
    "rondeKnop": 36,     # rond knopje met alleen een icoon
}


def qml_naam(sleutel: str) -> str:
    delen = sleutel.split("_")
    return delen[0] + "".join(d[:1].upper() + d[1:] for d in delen[1:])


def maak() -> str:
    licht, donker = KLEUREN["licht"], KLEUREN["donker"]
    r = ["// Gemaakt door tools/design/make_qml.py uit bugos_ui.py (KLEUREN, MATEN).",
         "// Niet met de hand aanpassen: verander bugos_ui.py en draai de maker opnieuw.",
         "import QtQuick", "", "QtObject {",
         "    property bool donker: false", ""]
    for k in licht:
        if k not in donker:
            continue
        a, b = licht[k], donker[k]
        if a.startswith("rgba") or b.startswith("rgba"):
            continue  # schaduwen: QML tekent die zelf niet
        r.append(f'    readonly property color {qml_naam(k)}: donker ? "{b}" : "{a}"')
    r.append(f'    readonly property color verloopBegin: donker ? "{ROOD_VERLOOP_DONKER[0]}" : "{ROOD_VERLOOP[0]}"')
    r.append(f'    readonly property color verloopEind: donker ? "{ROOD_VERLOOP_DONKER[1]}" : "{ROOD_VERLOOP[1]}"')
    r.append("")
    r.append(f"    readonly property int rKnop: {MATEN['knop']}     // knoppen, velden, regels")
    r.append(f"    readonly property int rKaart: {MATEN['kaart']}    // kaarten en tegels")
    r.append(f"    readonly property int rGroot: {MATEN['groot']}    // pop-ups en panelen")
    r.append(f"    readonly property int schuifSpoor: {MATEN['schuif_spoor']}")
    r.append(f"    readonly property int schuifKnop: {MATEN['schuif_knop']}")
    for k, v in HOOGTES.items():
        r.append(f"    readonly property int {k}: {v}")
    r.append("")
    for k, v in LETTERMATEN.items():
        r.append(f"    readonly property int {qml_naam('letter_' + k)}: {v}")
    r.append(f'    readonly property string letter: "{LETTERS["tekst"]}"')
    r.append(f'    readonly property string kopLetter: "{LETTERS["kop"]}"')
    r.append("}")
    return "\n".join(r) + "\n"


def main(args: list[str]) -> int:
    inhoud = maak()
    fout = 0
    for d in DOELEN:
        if "--check" in args:
            if not d.exists() or d.read_text(encoding="utf-8") != inhoud:
                print(f"Niet bijgewerkt: {d} (draai python3 tools/design/make_qml.py)")
                fout = 1
        else:
            d.write_text(inhoud, encoding="utf-8", newline="\n")
            print(d)
    return fout


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
