#!/usr/bin/env python3
"""BugOS-kleuren voor Windows-programma's (Wine), licht en donker.

Schrijft:
  system_files/usr/share/bugos/wine/licht.reg
  system_files/usr/share/bugos/wine/donker.reg

Jip-en-Janneke: een Windows-programma tekent zijn knoppen en vensters met de
"systeemkleuren" van Windows (ButtonFace, Window, Hilight...). Wine leest die uit
het register. Standaard zijn dat de grijze kleuren van Windows 2000. Wij zetten
er de BugOS-kleuren in: dezelfde vlakken, randen en zachte selectie als in KDE.
De vensterbalk tekent BugOS zelf (KWin), dus die verandert hier niet.

bugos-exe zet dit in de Windows-map van de gebruiker (en opnieuw als hij wisselt
tussen licht en donker). Een thema dat iemand zelf in winecfg koos, blijft winnen.

Eén bron: tools/ontwerp/tokens.py (dus bugos_ui.py).

Gebruik:  python3 tools/wine/maak.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "ontwerp"))

from tokens import KLEUREN, REPO, rgb  # noqa: E402

UIT = REPO / "system_files" / "usr" / "share" / "bugos" / "wine"


def kleuren(thema: str) -> dict[str, str]:
    k = KLEUREN[thema]
    return {
        # Vlakken
        "Background": k["achter"], "AppWorkSpace": k["achter"], "Window": k["vlak"],
        "Menu": k["vlak"], "MenuBar": k["achter"], "Scrollbar": k["achter"],
        "ButtonFace": k["knop"], "ButtonAlternateFace": k["knop_hover"], "InfoWindow": k["vlak"],
        # Randen en de 3D-randjes van knoppen: rustig, zonder harde zwarte lijnen
        "ButtonHilight": k["vlak"], "ButtonLight": k["vlak_hover"], "ButtonShadow": k["rand_sterk"],
        "ButtonDkShadow": k["rand_sterk"], "WindowFrame": k["rand"], "ActiveBorder": k["rand"],
        "InactiveBorder": k["rand"],
        # Tekst
        "WindowText": k["tekst"], "ButtonText": k["tekst"], "MenuText": k["tekst"],
        "InfoText": k["tekst"], "GrayText": k["tekst3"],
        # Selectie: zacht, met gewone tekst (zoals in KDE en de BugOS-apps)
        "Hilight": k["accent_zacht"], "HilightText": k["tekst"], "MenuHilight": k["accent_zacht"],
        "HotTrackingColor": k["accent"],
        # Titelbalken binnen het programma (MDI-vensters); de echte vensterbalk is van KWin
        "ActiveTitle": k["achter"], "GradientActiveTitle": k["achter"], "TitleText": k["tekst"],
        "InactiveTitle": k["achter"], "GradientInactiveTitle": k["achter"], "InactiveTitleText": k["tekst3"],
    }


def reg(thema: str) -> str:
    regels = ["Windows Registry Editor Version 5.00", "",
              f"; BugOS-kleuren ({thema}) voor Wine. Gemaakt door tools/wine/maak.py: niet met de hand aanpassen.",
              "", "[HKEY_CURRENT_USER\\Control Panel\\Colors]"]
    for naam, kleur in kleuren(thema).items():
        r, g, b = rgb(kleur)
        regels.append(f'"{naam}"="{r} {g} {b}"')
    return "\n".join(regels) + "\n"  # Wine leest ook gewone regeleinden


def main() -> None:
    UIT.mkdir(parents=True, exist_ok=True)
    for thema in ("licht", "donker"):
        pad = UIT / f"{thema}.reg"
        tekst = reg(thema)
        if not pad.exists() or pad.read_bytes().decode("utf-8") != tekst:
            pad.write_bytes(tekst.encode("utf-8"))
            print("geschreven:", pad.relative_to(REPO))


if __name__ == "__main__":
    main()
