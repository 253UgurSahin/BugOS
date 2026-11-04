"""BugOS-ontwerptaal voor alles buiten de eigen apps (pictogrammen, KDE-stijl, Plasma-stijl).

Eén bron: de kleuren en de lijn-iconen komen rechtstreeks uit
system_files/usr/lib/bugos/python/bugos_ui.py (KLEUREN en LIJN), zodat de
eigen apps en de rest van het systeem nooit uit elkaar lopen. Dit bestand
leest ze zonder Qt te laden (met ast), en voegt de maten uit docs/HUISSTIJL.md toe.

Gebruik:  from tokens import KLEUREN, LIJN, MATEN, ROOD_VERLOOP
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUGOS_UI = REPO / "system_files" / "usr" / "lib" / "bugos" / "python" / "bugos_ui.py"
SYSTEM = REPO / "system_files"


def _lees_constanten(pad: Path, namen: set[str]) -> dict:
    boom = ast.parse(pad.read_text(encoding="utf-8"))
    uit = {}
    for knoop in boom.body:
        doelen = []
        if isinstance(knoop, ast.Assign):
            doelen = [d.id for d in knoop.targets if isinstance(d, ast.Name)]
            waarde = knoop.value
        elif isinstance(knoop, ast.AnnAssign) and isinstance(knoop.target, ast.Name):
            doelen = [knoop.target.id]
            waarde = knoop.value
        for naam in doelen:
            if naam in namen and waarde is not None:
                uit[naam] = ast.literal_eval(waarde)
    return uit


_C = _lees_constanten(BUGOS_UI, {"KLEUREN", "LIJN", "ROOD", "TINTEN", "MATEN"})

#: {"licht": {...}, "donker": {...}}: achter, zijbalk, vlak, rand, tekst, tekst2, accent, ...
KLEUREN: dict[str, dict[str, str]] = _C["KLEUREN"]
#: BugOS-lijniconen: naam -> SVG-binnenkant op een raster van 24 x 24 (lijn 2, ronde uiteinden).
LIJN: dict[str, str] = _C["LIJN"]
ROOD: str = _C["ROOD"]
TINTEN: dict[str, str] = _C["TINTEN"]

#: Het verloop van de lieveheersbeestjesvleugel: koraal -> rood (aan-knoppen, schuifjes).
ROOD_VERLOOP = ("#FF5C50", "#DE2F3E")
ROOD_VERLOOP_DONKER = ("#FF5C50", "#EA3B4B")

#: Maten uit docs/HUISSTIJL.md ("Shapes"), in pixels bij schaal 1.
MATEN: dict = _C["MATEN"]

LETTERS = {"tekst": "Inter", "kop": "Funnel Display", "code": "JetBrains Mono"}


def rgb(hexkleur: str) -> tuple[int, int, int]:
    h = hexkleur.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


if __name__ == "__main__":
    print(len(LIJN), "lijn-iconen:", ", ".join(sorted(LIJN)))
    for thema, k in KLEUREN.items():
        print(thema, {n: k[n] for n in ("achter", "vlak", "rand", "tekst", "tekst2", "accent", "accent_zacht")})
