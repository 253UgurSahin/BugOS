#!/usr/bin/env python3
"""Maakt de knoppen van de Plasma-stijl "bugos" (pop-ups van het systeemvak en widgets).

Schrijft de SVG's voor de bedieningselementen van PlasmaComponents 3 naar
system_files/usr/share/plasma/desktoptheme/bugos/widgets/:

    button, actionbutton, toolbar, slider, switch, tabbar, lineedit, checkmarks,
    radiobutton, scrollbar, scrollwidget, bar_meter_horizontal, bar_meter_vertical,
    busywidget, menubaritem, arrows, line

Dezelfde vormtaal als de eigen BugOS-apps en het snelmenu: vlakke warmgrijze
knoppen, rood alleen als accent (aan, gekozen, focus), schuif en schakelaar met
het koraal-naar-rood verloop en een wit bolletje. Kleuren lopen via de
ColorScheme-klassen van KSvg, zodat licht en donker vanzelf volgen.

De namen van de elementen (normal-center, groove-highlight, hint-*, ...) zijn de
API van Plasma: we houden dezelfde namen aan als Breeze.

Gebruik:  python3 tools/plasma/buttons.py [uitmap]
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "design"))
from tokens import SYSTEM  # noqa: E402
from buttons_controls import actionbutton, button, checkmarks, radiobutton, slider, switch, toolbar  # noqa: E402
from buttons_fields import (arrows, bar_meter, busywidget, lineedit, line, menubaritem, scrollbar,  # noqa: E402
                            scrollwidget, tabbar)

UIT = SYSTEM / "usr" / "share" / "plasma" / "desktoptheme" / "bugos" / "widgets"


BESTANDEN = {
    "button": (button, "knoppen"),
    "actionbutton": (actionbutton, "ronde knoppen"),
    "toolbar": (toolbar, "werkbalk"),
    "slider": (slider, "schuif"),
    "switch": (switch, "schakelaar"),
    "tabbar": (tabbar, "tabs"),
    "lineedit": (lineedit, "invoerveld"),
    "checkmarks": (checkmarks, "vinkjes"),
    "radiobutton": (radiobutton, "keuzerondjes"),
    "scrollbar": (scrollbar, "schuifbalk"),
    "scrollwidget": (scrollwidget, "rand van een schuifvlak"),
    "bar_meter_horizontal": (lambda: bar_meter("horizontal"), "voortgangsbalk"),
    "bar_meter_vertical": (lambda: bar_meter("vertical"), "staande voortgangsbalk"),
    "busywidget": (busywidget, "bezig-rondje"),
    "menubaritem": (menubaritem, "menubalk"),
    "arrows": (arrows, "pijltjes"),
    "line": (line, "lijnen"),
}


def main(args: list[str]) -> int:
    uit = Path(args[0]) if args else UIT
    uit.mkdir(parents=True, exist_ok=True)
    for naam, (maker, titel) in BESTANDEN.items():
        maker().schrijf(uit / f"{naam}.svg", titel)
    print(len(BESTANDEN), "bestanden in", uit)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
