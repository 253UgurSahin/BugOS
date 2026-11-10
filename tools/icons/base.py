"""Gedeelde hulpjes voor het BugOS-pictogramthema (system_files/usr/share/icons/BugOS).

Elk onderdeel (apps.py, status.py, places.py, settings.py) heeft een
functie maak(b: Bouwer). Die tekent zijn pictogrammen met de hulpjes hieronder;
make.py roept ze allemaal aan en schrijft daarna index.theme.

Huisstijl (docs/BRAND.md, "Shapes"): BugOS-lijniconen op een raster van
24 x 24, lijn 2, ronde uiteinden. Eenkleurige pictogrammen (systeemvak, knoppen,
instellingen) gebruiken de klasse ColorScheme-Text met currentColor: KDE kleurt
ze dan vanzelf mee met licht en donker. Alles wat niet in BugOS zit, valt terug
op Breeze (Inherits=breeze).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "design"))
from tokens import KLEUREN, LIJN, MATEN, ROOD_VERLOOP, SYSTEM  # noqa: E402

UIT = SYSTEM / "usr" / "share" / "icons" / "BugOS"

# Standaardkleuren in het stijlblad. KDE vervangt dit stijlblad door de kleuren
# van het actieve kleurenschema; deze waarden zijn alleen voor programma's die
# dat niet doen (en voor de proefkaart).
_L = KLEUREN["licht"]
STIJLBLAD = (
    '<style id="current-color-scheme" type="text/css">'
    f".ColorScheme-Text{{color:{_L['tekst']};}}"
    f".ColorScheme-Background{{color:{_L['achter']};}}"
    f".ColorScheme-Highlight{{color:{_L['accent']};}}"
    f".ColorScheme-ViewText{{color:{_L['tekst']};}}"
    f".ColorScheme-ViewBackground{{color:{_L['vlak']};}}"
    f".ColorScheme-ButtonText{{color:{_L['tekst']};}}"
    f".ColorScheme-NegativeText{{color:{_L['fout']};}}"
    f".ColorScheme-PositiveText{{color:{_L['goed']};}}"
    f".ColorScheme-NeutralText{{color:{_L['let_op']};}}"
    "</style>"
)

# map -> eigenschappen in index.theme. Onderdelen mogen er meer bij zetten met map_erbij().
MAPPEN: dict[str, dict] = {
    "apps/scalable": {"Size": 48, "Context": "Applications", "Type": "Scalable", "MinSize": 8, "MaxSize": 512},
    "preferences/scalable": {"Size": 32, "Context": "Applications", "Type": "Scalable", "MinSize": 8, "MaxSize": 512},
    "categories/scalable": {"Size": 32, "Context": "Categories", "Type": "Scalable", "MinSize": 8, "MaxSize": 512},
    "status/16": {"Size": 16, "Context": "Status", "Type": "Fixed"},
    "status/scalable": {"Size": 22, "Context": "Status", "Type": "Scalable", "MinSize": 17, "MaxSize": 512},
    "actions/16": {"Size": 16, "Context": "Actions", "Type": "Fixed"},
    "actions/scalable": {"Size": 22, "Context": "Actions", "Type": "Scalable", "MinSize": 17, "MaxSize": 512},
    "devices/16": {"Size": 16, "Context": "Devices", "Type": "Fixed"},
    "devices/scalable": {"Size": 22, "Context": "Devices", "Type": "Scalable", "MinSize": 17, "MaxSize": 512},
    "places/16": {"Size": 16, "Context": "Places", "Type": "Fixed"},
    "places/scalable": {"Size": 48, "Context": "Places", "Type": "Scalable", "MinSize": 17, "MaxSize": 512},
    "mimetypes/scalable": {"Size": 48, "Context": "MimeTypes", "Type": "Scalable", "MinSize": 8, "MaxSize": 512},
    "emblems/scalable": {"Size": 16, "Context": "Emblems", "Type": "Scalable", "MinSize": 8, "MaxSize": 512},
}

_NAAM = re.compile(r"^[a-z0-9][a-z0-9._+-]*$")


class Bouwer:
    """Schrijft pictogrammen en houdt bij welke mappen en namen er zijn."""

    def __init__(self, uit: Path = UIT):
        self.uit = uit
        self.gebruikte_mappen: set[str] = set()
        self.namen: dict[tuple[str, str], str] = {}   # (map, naam) -> wie hem schreef

    # ------------------------------------------------------------ schrijven ---
    def schrijf(self, map_: str, naam: str, svg: str, *, door: str = "", symbolic_ook: bool = False) -> None:
        """Zet <map>/<naam>.svg neer. symbolic_ook: ook <naam>-symbolic.svg (KDE vraagt soms die naam)."""
        if map_ not in MAPPEN:
            raise ValueError(f"onbekende map {map_!r}: voeg hem eerst toe met map_erbij()")
        if not _NAAM.match(naam):
            raise ValueError(f"ongeldige pictogramnaam {naam!r}")
        ET.fromstring(svg)  # gooit een fout bij kapotte SVG
        sleutel = (map_, naam)
        if sleutel in self.namen and self.namen[sleutel] != door:
            raise ValueError(f"{map_}/{naam} wordt al gemaakt door {self.namen[sleutel]!r} (nu ook door {door!r})")
        self.namen[sleutel] = door
        pad = self.uit / map_ / f"{naam}.svg"
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text(svg, encoding="utf-8", newline="\n")
        self.gebruikte_mappen.add(map_)
        if symbolic_ook and not naam.endswith("-symbolic"):
            self.schrijf(map_, naam + "-symbolic", svg, door=door)

    def alias(self, map_: str, naam: str, *anderen: str, door: str = "") -> None:
        """Dezelfde tekening onder andere namen (als kopie: symlinks werken niet overal in git)."""
        svg = (self.uit / map_ / f"{naam}.svg").read_text(encoding="utf-8")
        for ander in anderen:
            self.schrijf(map_, ander, svg, door=door)

    # ------------------------------------------------------------- index ---
    def schrijf_index(self) -> Path:
        mappen = sorted(self.gebruikte_mappen)
        regels = [
            "[Icon Theme]",
            "Name=BugOS",
            "Comment=BugOS line icons (falls back to Breeze)",
            "Comment[nl]=BugOS-lijnpictogrammen (de rest komt van Breeze)",
            "Inherits=breeze,hicolor",
            "Example=folder",
            "FollowsColorScheme=true",
            "DisplayDepth=32",
            "DesktopDefault=48",
            "DesktopSizes=16,22,32,48,64,128,256",
            "ToolbarDefault=22",
            "ToolbarSizes=16,22,32,48",
            "MainToolbarDefault=22",
            "MainToolbarSizes=16,22,32,48",
            "SmallDefault=16",
            "SmallSizes=16,22,32,48",
            "PanelDefault=48",
            "PanelSizes=16,22,32,48,64,128,256",
            "DialogDefault=32",
            "DialogSizes=16,22,32,48,64,128,256",
            "KDE-Extensions=.svg",
            "",
            "Directories=" + ",".join(mappen),
            "",
        ]
        for m in mappen:
            regels.append(f"[{m}]")
            regels += [f"{k}={v}" for k, v in MAPPEN[m].items()]
            regels.append("")
        pad = self.uit / "index.theme"
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text("\n".join(regels), encoding="utf-8", newline="\n")
        return pad


def map_erbij(map_: str, **eigenschappen) -> None:
    """Een extra map in index.theme (bijv. status/22 met Type=Fixed)."""
    MAPPEN.setdefault(map_, eigenschappen)


# -------------------------------------------------------------- tekenen ---

def lijn(naam_of_binnen: str) -> str:
    """De binnenkant van een BugOS-lijnicoon (naam uit LIJN, of zelf geschreven SVG-elementen)."""
    return LIJN.get(naam_of_binnen, naam_of_binnen)


def symbolisch(binnen: str, *, raster: int = 24, dikte: float = MATEN["lijn"], klasse: str = "ColorScheme-Text",
               maat: int | None = None) -> str:
    """Eenkleurig lijnpictogram dat meekleurt met het kleurenschema.

    binnen: SVG-elementen op het raster (lijnen). Een element mag een eigen klasse
    hebben (bijv. class="ColorScheme-NegativeText") voor een gekleurd stukje.
    Gevulde stukjes: geef dat element zelf fill="currentColor" stroke="none".
    maat: width/height van het bestand (standaard het raster)."""
    m = maat or raster
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{m}" height="{m}" viewBox="0 0 {raster} {raster}">'
            f"{STIJLBLAD}"
            f'<g class="{klasse}" fill="none" stroke="currentColor" stroke-width="{dikte}" '
            f'stroke-linecap="round" stroke-linejoin="round">{binnen}</g></svg>')


def klein(binnen: str, klasse: str = "ColorScheme-Text") -> str:
    """Dezelfde lijntekening voor 16 x 16 (lijn 1,5 op het 24-raster = 1 pixel op 16)."""
    return symbolisch(binnen, dikte=1.5, klasse=klasse, maat=16)


def controleer(uit: Path = UIT, volledig: bool = True) -> list[str]:
    """Zelfcontrole: is elke SVG geldig, staat elke map in index.theme, en (volledig)
    staat geen naam in twee soorten mappen (bijv. apps/ én preferences/: dan is het
    toeval welke KDE kiest). Dezelfde naam in <soort>/16 en <soort>/scalable mag wel."""
    fouten = []
    index = (uit / "index.theme").read_text(encoding="utf-8") if (uit / "index.theme").exists() else ""
    mappen = set()
    for regel in index.splitlines():
        if regel.startswith("Directories="):
            mappen = set(regel.split("=", 1)[1].split(","))
    soort_van: dict[str, set[str]] = {}
    for pad in sorted(uit.rglob("*.svg")):
        rel = pad.parent.relative_to(uit).as_posix()
        if rel not in mappen:
            fouten.append(f"{rel} staat niet in index.theme ({pad.name})")
        try:
            ET.fromstring(pad.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            fouten.append(f"kapotte SVG {pad}: {e}")
        soort_van.setdefault(pad.stem, set()).add(rel.split("/")[0])
    if volledig:
        for naam, soorten in sorted(soort_van.items()):
            if len(soorten) > 1:
                fouten.append(f"{naam} staat in meer soorten mappen: {', '.join(sorted(soorten))}")
    return fouten
