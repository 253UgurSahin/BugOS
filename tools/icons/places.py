"""Mappen, plekken, apparaten en bestandssoorten voor het BugOS-pictogramthema.

Doel: Dolphin, de bestandskiezer, het bureaublad en de pop-up "Schijven en apparaten"
laten dezelfde mappen en bestanden zien als BugOS Bestanden (usr/bin/bugos-files):

  - mappen vanaf 32 px: de zachte BugOS-map uit teken_map(), met het tekentje erop;
  - mappen en plekken op 16 en 22 px (en elke naam-symbolic): BugOS-lijniconen, net als in
    de zijbalk van Bestanden (huis, scherm, document, ...); een bijzondere map is klein
    alleen zijn tekentje (een tekentje ín een mapomtrek is op 16 px een vlekje);
  - apparaten: lijniconen in de tekstkleur (schijf, USB-stick, telefoon, ...), met de namen
    die Solid en het systeemvak vragen (ook multimedia-player voor een Android-telefoon);
  - bestandssoorten: het papiertje met het gekleurde labeltje uit teken_papier(), met
    dezelfde kleuren en tekentjes (SOORTEN uit bugos-files). Op 16 en 22 px een
    lijnpapiertje met de kleur van het labeltje erin;
  - de actie "Nieuwe map" (folder-new): de map met plusje, zoals de knop in Bestanden.

16 en 22 px staan ook in <map>@2x en @3x: anders kiest KDE op een HiDPI-scherm (125 % en
meer) de grote versie, ook in de zijbalk en de lijstweergave.

Meekleuren met licht en donker: KDE vervangt de klassen ColorScheme-Background en -Text
door de venster- en tekstkleur van het kleurenschema (gemeten in de testbank). Highlight
gebruiken we niet: in de BugOS-schema's is dat het zachte rood van een gekozen regel, niet
het rood zelf, en dat kan nog veranderen. Een map is daarom een stapel lagen: de
vensterkleur, daarover een vast grijs en daarover het BugOS-rood (ROOD uit bugos_ui.py),
elk met een eigen dekking. pas_aan() rekent die dekkingen uit, zodat licht en donker zo
dicht mogelijk uitkomen bij map_voor, map_achter en map_teken uit bugos_ui.py. Verandert
daar een kleur (of in de kleurenschema's), dan volgen de pictogrammen vanzelf bij de
volgende keer maken. Gekozen (Dolphin, lijstweergave): KDE maakt de tekstkleur dan rood,
dus lijniconen en het tekentje op de map worden rood, net als in de zijbalk van Bestanden.

Labeltjes: tekst in een pictogram mag geen lettertype gebruiken, dus de letters (PDF, ZIP,
MP3, ...) zijn kleine lijntekeningen (LETTERS in places_paper.py), even dik en ruim als Inter Bold in
Bestanden. Net als in Bestanden staat de extensie op elk papiertje waarvan we die kennen (LABELS,
anders EXTENSIES uit shared-mime-info); zonder extensie komt er geen labeltje.
"""

from __future__ import annotations

import base as basis
from base import klein, symbolisch
from places_colors import kleurverslag
from places_folders import APPARATEN, KLEURMAPPEN, MAPPEN, _lijnset, map_svg, prullenbak_svg, server_svg
from places_mimetypes import BREEZE_SOORTEN, LABELS, _familie
from places_paper import papier_klein, papier_svg
from places_svg import EIGEN
from tokens import LIJN


# ------------------------------------------------------------------ mappen in index.theme ---
# Klein (16 en 22) zijn het lijniconen, zoals Breeze ook doet; vanaf 32 px de zachte map.
basis.map_erbij("places/22", Size=22, Context="Places", Type="Fixed")
basis.map_erbij("mimetypes/16", Size=16, Context="MimeTypes", Type="Fixed")
basis.map_erbij("mimetypes/22", Size=22, Context="MimeTypes", Type="Fixed")

# HiDPI: bij een schaal van 125 tot 200 % zoekt KDE eerst in <maat>@2x, vanaf 225 % in @3x
# (gemeten met KIconLoader 6.31 in de testbank). Zonder die mappen kiest KDE op zo'n scherm de
# grote versie (de zachte map, het papiertje met label) waar de lijnversie hoort. Breeze heeft
# ze ook. Inhoud: een kopie van 16 en 22 (git en OSTree bewaren gelijke bestanden maar één keer).
SCHALEN = (2, 3)
GESCHAALD = ("places/16", "places/22", "mimetypes/16", "mimetypes/22")
for _map in GESCHAALD:
    _soort, _maat = _map.split("/")
    for _s in SCHALEN:
        basis.map_erbij(f"{_map}@{_s}x", Size=int(_maat), Scale=_s,
                        Context="Places" if _soort == "places" else "MimeTypes", Type="Fixed")


def _mappen_instellen() -> None:
    basis.MAPPEN["places/scalable"]["MinSize"] = 32
    basis.MAPPEN["mimetypes/scalable"]["MinSize"] = 32


# ------------------------------------------------------------------------- maken ---

def maak(b: basis.Bouwer) -> None:
    _mappen_instellen()
    gedaan: set[tuple[str, str]] = set()

    def schrijf(map_: str, naam: str, svg: str) -> None:
        if (map_, naam) in gedaan:
            raise ValueError(f"plaatsen: {map_}/{naam} twee keer")
        gedaan.add((map_, naam))
        b.schrijf(map_, naam, svg)
        if map_ in GESCHAALD:
            for s in SCHALEN:
                b.schrijf(f"{map_}@{s}x", naam, svg)

    def plek(namen: list[str], groot: str, klein_set: dict[str, str]) -> None:
        for naam in namen:
            schrijf("places/scalable", naam, groot)
            schrijf("places/scalable", naam + "-symbolic", klein_set["scalable"])
            for maat in ("16", "22"):
                schrijf(f"places/{maat}", naam, klein_set[maat])
                schrijf(f"places/{maat}", naam + "-symbolic", klein_set[maat])

    # Mappen en plekken.
    for namen, teken, (soort, glyph) in MAPPEN:
        plek(namen, map_svg(teken, open_=(soort == "open")), _lijnset(soort, glyph))
    for naam, tint in KLEURMAPPEN.items():
        plek([naam], map_svg(None, tint=tint), _lijnset("map", None))
    plek(["user-trash"], prullenbak_svg(), _lijnset("teken", "prullenbak"))
    plek(["user-trash-full"], prullenbak_svg(vol=True), _lijnset("teken", "prullenbak-vol"))
    plek(["network-server"], server_svg(), _lijnset("teken", "server"))

    # De actie "Nieuwe map" (Dolphin, elke KDE-bestandskiezer): de map met plusje, net als de
    # knop "Nieuwe map" in Bestanden. Een actie, dus een lijnicoon op elke maat.
    for naam in ("folder-new", "folder-add"):
        for map_, svg in (("actions/16", klein(LIJN["map-plus"])), ("actions/scalable", symbolisch(LIJN["map-plus"]))):
            schrijf(map_, naam, svg)
            schrijf(map_, naam + "-symbolic", svg)

    # Apparaten: lijniconen in de tekstkleur.
    for glyph, namen in APPARATEN.items():
        binnen = EIGEN.get(glyph) or LIJN[glyph]
        for naam in namen:
            for map_, svg in (("devices/16", klein(binnen)), ("devices/scalable", symbolisch(binnen))):
                schrijf(map_, naam, svg)
                schrijf(map_, naam + "-symbolic", svg)

    # Bestandssoorten.
    namen = list(dict.fromkeys(list(LABELS) + BREEZE_SOORTEN))
    for naam in namen:
        fam, label = _familie(naam)
        schrijf("mimetypes/scalable", naam, papier_svg(fam, label))
        schrijf("mimetypes/22", naam, symbolisch(papier_klein(fam), maat=22))
        schrijf("mimetypes/16", naam, klein(papier_klein(fam)))
    # Netwerkplekken die als bestandssoort binnenkomen (smb://).
    for naam, groot, glyph in (("application-x-smb-workgroup", map_svg("wereld"), "wereld"),
                               ("application-x-smb-server", server_svg(), "server")):
        set_ = _lijnset("teken", glyph)
        schrijf("mimetypes/scalable", naam, groot)
        schrijf("mimetypes/22", naam, set_["22"])
        schrijf("mimetypes/16", naam, set_["16"])

    print(kleurverslag())
