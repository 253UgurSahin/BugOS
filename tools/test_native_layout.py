#!/usr/bin/env python3
"""Test van de basis van de BugOS-apps (pakket 'layout'): de maten (compact zoals Windows 11, met de ronde hoeken),
de gedeelde bouwstenen (Groep, KeuzeKaart, Rij, ActieBalk, sectie_met_knop, vraag_ja, vraag_tekst), de tabjes van
Instellingen, en: past elk venster op een laptop van 1280 x 800, bij 75, 100, 125 en 150 %?

Er verandert niets aan je computer: alles draait in de voorbeeldstand, zonder scherm (Qt 'offscreen').
De schermtest draait per schaal in een eigen proces (QT_SCALE_FACTOR kan maar één keer per proces).

Gebruik:  python3 tools/test_native_layout.py            (alles)
          python3 tools/test_native_layout.py --pas 1.5  (alleen de schermtest bij 150 %, drukt 'PAS ...' af)
"""

from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
TMP = Path(tempfile.mkdtemp(prefix="bugos-layout-test-"))

SCALES = ("0.75", "1", "1.25", "1.5")
SCHERM = (1280, 800)


def taakbalk_hoogte() -> int:
    """De hoogte van de BugOS-taakbalk, uit de Plasma-indeling zelf (niet uit bugos_ui: anders toetst de test de code
    met haar eigen getal). Plasma: gridUnit = 18 bij de gewone letter."""
    import math
    import re
    js = (ROOT / "system_files/usr/share/plasma/look-and-feel/org.bugos.desktop/contents/layouts/"
          "org.kde.plasma.desktop-layout.js").read_text(encoding="utf-8")
    m = re.search(r"panel\.height\s*=\s*2\s*\*\s*Math\.floor\(gridUnit\s*\*\s*([\d.]+)\s*/\s*2\)", js)
    return 2 * math.floor(18 * float(m.group(1)) / 2) if m else 48


TAAKBALK_ECHT = taakbalk_hoogte()
TITELBALK_ECHT = 30   # de titelbalk die KWin (Breeze, zonder randen) boven een venster zet

# Bekende problemen in bestanden van een ander pakket (staan in het verslag, met de precieze wijziging). Ze tellen
# niet als fout, maar worden wel gemeld; zodra ze opgelost zijn, verschijnen ze vanzelf niet meer. Elk probleem
# precies: (ronde of None, app, staat, het begin van de melding, iets wat er verderop in moet staan, reden). Een
# ánder probleem op dezelfde pagina telt dus gewoon als fout. Komt een regel in geen enkele ronde meer voor, dan
# meldt de test 'OPGELOST?': dan mag hij hier weg (zo blijft de lijst niet stilletjes iets toestaan).
# (Opgelost en weggehaald: D05 Uiterlijk, D13 Welkom, R03 Back-up en Overstap, R13 Taakbeheer met grote letters.)
BEKEND: list = []   # nu leeg: alles wat hier stond is opgelost


# Welke regels van BEKEND deze keer echt voorkwamen (hun plek in de lijst). De rest is opgelost: 'OPGELOST?'.
BEKEND_GEZIEN: set[int] = set()


def bekend(regel: str, ronde: str = "") -> str:
    """De reden als deze 'PAS app staat melding'-regel (in deze ronde) een bekend probleem is, anders ''."""
    d = regel.split(" ", 3)
    if len(d) < 4:
        return ""
    for i, (ronde_, app_, staat_, begin_, ook_, reden) in enumerate(BEKEND):
        if ronde_ in (None, ronde) and d[1] == app_ and d[2] == staat_ and d[3].startswith(begin_) and ook_ in d[3]:
            BEKEND_GEZIEN.add(i)     # deze bekende regel bestaat nog: hij moet dus (nog) in de lijst blijven
            return reden
    return ""


# Teksten die in het Nederlands en het Engels hetzelfde zijn, en dat ook moeten zijn (namen, merken).
ZELFDE_MAG = {
    "Bugie's HP LaserJet", "Canon PIXMA", "Intel Core i5-1235U", "LibreOffice Writer", "Haruna (video)",
    # Namen die het systeem zelf geeft (PipeWire, BlueZ): die vertaalt BugOS niet, ook niet in de voorbeeldstand.
    "Bugie's headphones", "Built-in speakers", "TV (HDMI)",
}
# Nederlandse namen in de voorbeeldstand die andere pakketten nog vertalen (D08 in het verslag). Tot dan: gemeld,
# geen fout. Zodra ze vertaald zijn, verschijnen ze vanzelf niet meer (en meldt de test 'OPGELOST?': haal ze weg).
# (De namen van wifi, bluetooth, printers en programma's zijn vertaald en staan nu vast in D08_VOORBEELD, onderaan.)
NL_BEKEND: dict = {}   # nu leeg: ook de namen van Taakbeheer (D08 tools) zijn vertaald


def omgeving(thuis: Path) -> dict:
    """Wat elk proces van deze test nodig heeft (vóór Qt geladen wordt)."""
    (thuis / ".config").mkdir(parents=True, exist_ok=True)
    for m in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
        (thuis / m).mkdir(exist_ok=True)
    (thuis / "Documents" / "Letter.odt").write_bytes(b"")
    stick, schijf = thuis.parent / "stick", thuis.parent / "schijf"
    for d in (stick, schijf):
        d.mkdir(exist_ok=True)
    (stick / "BugOS-Switch").mkdir(exist_ok=True)
    (stick / "BugOS-Switch" / "bugos-switch.json").write_text(
        json.dumps({"gebruiker": "Bugie", "computer": "LIVING-ROOM-PC"}), encoding="utf-8")
    return {
        "HOME": str(thuis), "XDG_CONFIG_HOME": str(thuis / ".config"), "XDG_DATA_HOME": str(thuis / ".local/share"),
        "BUGOS_INSTELLINGEN_VOORBEELD": "1", "BUGOS_TAKEN_VOORBEELD": "1", "BUGOS_MEERDERE": "1",
        "BUGOS_THEMA": "licht", "BUGOS_LETTERS": str(ROOT / "system_files/usr/share/fonts/bugos"),
        # Met de echte achtergronden: anders toont Uiterlijk geen plaatjes en zie je niet of ze passen (review R05).
        "BUGOS_ACHTERGRONDEN": str(ROOT / "system_files/usr/share/wallpapers/bugos/contents"),
        "BUGOS_SCHIJVEN": f"{stick}:{schijf}", "BUGOS_LSBLK": "", "BUGOS_GEINSTALLEERD": "org.mozilla.firefox",
        "BUGOS_SYS": str(thuis.parent / "sys"), "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8",
    }


# ===================================================================== schermtest (in een eigen proces) ===

HALF_SCHERM = 640   # Instellingen naast een ander venster (Windows-toets + pijl links): de helft van 1280 px (B-02)


def pas(schaal: str, groot: bool = False, teksten: bool = False, smal: bool = False) -> int:
    """Bouw elke app op een scherm van 1280 x 800 bij deze schaal en druk af wat niet past ('PAS app staat wat').
    groot: met 'Grote letters' (1,5x). teksten: druk in plaats daarvan elke zichtbare tekst af ('TEKST app staat x').
    smal: alleen Instellingen, op de helft van het scherm (640 px breed), zoals na Windows-toets + pijl links (B-02).
    De VM-test zag toen op Energie, Scherm, Uiterlijk en Geluid een balk om opzij te schuiven en afgeknipte knoppen;
    de gewone ronde zag dat niet, want daar is het venster 1120 px breed."""
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import (
        QAbstractButton, QAbstractItemView, QAbstractScrollArea, QApplication, QLabel, QPushButton, QWidget,
    )

    import bugos_ui

    echt_maak = bugos_ui.maak_app
    if groot:
        bugos_ui.letter_schaal = lambda _f: 1.5     # zoals KDE 'Grote letters' (12 punten in plaats van 10)

    def maak_een(*a, **k):
        """Eén QApplication voor alle apps in dit proces."""
        return QApplication.instance() or echt_maak(*a, **k)

    bugos_ui.maak_app = maak_een
    meldingen: list[str] = []

    def wacht(ms: int = 120) -> None:
        lus = QEventLoop()
        QTimer.singleShot(ms, lus.quit)
        lus.exec()
        QApplication.processEvents()

    def kijk(app_naam: str, staat: str, venster: QWidget, hoofdknop_in_beeld: bool = False) -> None:
        wacht()
        if teksten:
            gezien = set()
            for w in venster.findChildren(QWidget):
                if w.isVisible() and isinstance(w, (QLabel, QAbstractButton)) and w.text().strip():
                    gezien.add(" ".join(w.text().split()))
            for x in sorted(gezien):
                print(f"TEKST {app_naam} {staat} {x}", flush=True)
            return
        scherm = venster.screen() or QApplication.primaryScreen()
        hoog = scherm.geometry().height() - TAAKBALK_ECHT - TITELBALK_ECHT
        breed = scherm.geometry().width()
        fout: list[str] = []
        if venster.width() > breed or venster.height() > hoog:
            fout.append(f"venster {venster.width()}x{venster.height()} > {breed}x{hoog}")
        for w in venster.findChildren(QWidget):
            if not w.isVisible():
                continue
            if w.visibleRegion().isEmpty():
                # Een rode hoofdknop (Back-up maken, Volgende) hoort altijd in beeld, niet pas na schuiven (R03).
                if hoofdknop_in_beeld and isinstance(w, QPushButton) and w.property("soort") == "hoofd":
                    fout.append(f"hoofdknop buiten beeld {w.text()[:40]!r}")
                continue
            if isinstance(w, QAbstractScrollArea) and not isinstance(w, QAbstractItemView):
                if w.horizontalScrollBar().maximum() > 1:
                    fout.append(f"schuift opzij {w.horizontalScrollBar().maximum()} px ({type(w).__name__})")
            elif isinstance(w, QLabel) and w.text() and w.wordWrap() and (w.pixmap() is None or w.pixmap().isNull()):
                if w.heightForWidth(w.width()) > w.height() + 1:
                    fout.append(f"tekst afgeknipt {w.text()[:40]!r}")
            elif isinstance(w, QPushButton) and w.text() and w.sizeHint().width() > w.width() + 1:
                fout.append(f"knop te smal {w.text()[:40]!r} {w.width()}<{w.sizeHint().width()}")
        for f in fout:
            meldingen.append(f"PAS {app_naam} {staat} {f}")

    def staten(app_naam: str, venster: QWidget, g: dict) -> None:
        if app_naam == "settings" and smal:
            # Zoals KWin het venster tegen de linkerkant zet: de helft van het scherm breed, zo hoog als er vrij is.
            # KWin houdt zich daarbij niet aan de kleinste maat van het venster, dus die zetten we hier ook opzij.
            venster.setMinimumSize(0, 0)
            scherm = venster.screen() or QApplication.primaryScreen()
            venster.resize(HALF_SCHERM, scherm.geometry().height() - TAAKBALK_ECHT - TITELBALK_ECHT)
            wacht(200)
            for klasse in g["PAGINAS"]:
                venster.ga_naar(klasse.sleutel)
                kijk(app_naam, f"{klasse.sleutel}@{HALF_SCHERM}", venster)
        elif app_naam == "settings":
            for klasse in g["PAGINAS"]:
                venster.ga_naar(klasse.sleutel)
                kijk(app_naam, klasse.sleutel, venster)
        elif app_naam == "welcome":
            for i in range(venster.stapels.count()):
                venster.stapels.setCurrentIndex(i)
                kijk(app_naam, ("hallo", "internet", "uiterlijk", "updates", "jij", "klaar")[i], venster, True)
        elif app_naam == "tasks":
            for s in ("programmas", "prestaties", "opstarten"):
                venster.ga_naar(s)
                if s == "programmas" and teksten and hasattr(venster, "wissel_achtergrond"):
                    venster.wissel_achtergrond()      # ook de achtergrondtaken (review R04)
                kijk(app_naam, s, venster)
        elif app_naam == "files":
            kijk(app_naam, "thuis", venster)
            venster.ga_naar(Path(os.environ["HOME"]) / "Documents")
            wacht(400)
            venster.lijst.selectAll()
            kijk(app_naam, "alles-gekozen", venster)
        elif app_naam == "backup":
            kijk(app_naam, "begin", venster, True)
            # Een back-up die deels lukte: de gele melding en de balk erbij. De knoppen moeten nog te zien zijn (R03).
            venster.melding.zet(g["DEELS_UITLEG"].format(mappen="Documents, Pictures"), "let_op")
            venster.balk.setValue(42)
            venster.balk.show()
            kijk(app_naam, "deels", venster, True)
        else:
            kijk(app_naam, "begin", venster, app_naam == "switch")

    APPS = {"settings": "bugos-settings", "welcome": "bugos-welcome", "help": "bugos-help", "store": "bugos-store",
            "backup": "bugos-backup", "switch": "bugos-switch", "tasks": "bugos-task-manager", "files": "bugos-files"}
    if teksten:
        APPS = {k: APPS[k] for k in ("settings", "tasks")}
    if smal:
        APPS = {"settings": APPS["settings"]}
    echt_uitvoeren = bugos_ui.uitvoeren
    for app_naam, programma in APPS.items():
        g: dict = {}

        def uitvoeren(app, venster, app_naam=app_naam, g=g):
            # De echte uitvoeren (die het venster passend maakt), alleen 'exec' kijkt en stopt meteen.
            app.exec = lambda: (staten(app_naam, venster, g), 0)[1]
            try:
                return echt_uitvoeren(app, venster)
            finally:
                del app.exec

        bugos_ui.uitvoeren = uitvoeren
        sys.argv = [str(BIN / programma)] + ([os.environ["HOME"]] if app_naam == "files" else [])
        try:
            g.update(runpy.run_path(str(BIN / programma), run_name="layout_test"))
            if app_naam == "help":
                Uitslag, OK = g["Uitslag"], g["OK"]
                g["CONTROLES"][:] = [lambda: Uitslag("Internet", OK, "You are connected to the internet.")]
            if app_naam == "store":   # (runpy geeft een kopie: de functies kijken in hun eigen globals)
                echt_lees = g["lees_catalogus"]
                g["main"].__globals__["lees_catalogus"] = \
                    lambda pad=ROOT / "system_files/usr/share/bugos/store.json": echt_lees(pad)
            (g.get("main") or g["venster"])()
        except Exception as e:  # noqa: BLE001
            meldingen.append(f"PAS {app_naam} start kapot: {type(e).__name__}: {e}")
        print(f"KLAAR {app_naam}", flush=True)
    for m in meldingen:
        print(m, flush=True)
    sys.stdout.flush()
    os._exit(0)   # niet wachten op draadjes van de apps die nog lopen (Hulp, Winkel): die doen er hier niet toe


def kind(schaal: str, *extra: str, taal: str = "en_US.UTF-8") -> list[str]:
    """Draai pas() in een eigen proces (QT_SCALE_FACTOR kan maar één keer per proces) en geef de uitvoer."""
    sleutel = "-".join((schaal,) + extra + (taal[:2],)).replace("--", "")
    thuis = TMP / f"thuis-{sleutel}" / "thuis"
    thuis.mkdir(parents=True)
    conf = TMP / f"scherm-{sleutel}.json"
    conf.write_text(json.dumps({"screens": [{"name": "s", "x": 0, "y": 0, "width": SCHERM[0], "height": SCHERM[1],
                                             "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}))
    env = dict(os.environ)
    env.pop("LANGUAGE", None)
    env.update(omgeving(thuis))
    env.update(QT_QPA_PLATFORM=f"offscreen:configfile={conf}", QT_SCALE_FACTOR=schaal, PYTHONDONTWRITEBYTECODE="1",
               LC_ALL=taal, LANG=taal)
    try:
        p = subprocess.run([sys.executable, __file__, "--pas", schaal, *extra], env=env, capture_output=True,
                           text=True, timeout=300, cwd=str(TMP))
        regels = p.stdout.splitlines()
        if p.returncode != 0:
            regels.append(f"PAS proces stopte met code {p.returncode}: {p.stderr.strip()[-400:]}")
    except subprocess.TimeoutExpired:
        regels = ["PAS proces bleef hangen (300 s)"]
    return regels


def schermtest() -> list[tuple[str, list[str], list[str]]]:
    """Elke schaal, en 100 % met grote letters: (naam, problemen, klaar-gemelde apps).
    Daarna Instellingen op een half scherm (640 px, B-02), in het Nederlands (zoals de VM-test, en de Nederlandse
    woorden zijn vaak langer) en in het Engels."""
    uit = []
    rondes = [(s, (), s, "en_US.UTF-8") for s in SCALES] + [("1", ("--groot",), "1 grote letters", "en_US.UTF-8")]
    rondes += [("1", ("--smal",), "1 half scherm nl", "nl_NL.UTF-8"), ("1", ("--smal",), "1 half scherm en", "en_US.UTF-8")]
    for schaal, extra, naam, taal in rondes:
        regels = kind(schaal, *extra, taal=taal)
        uit.append((naam, [r for r in regels if r.startswith("PAS ")],
                    [r.split()[1] for r in regels if r.startswith("KLAAR ")]))
    return uit


if len(sys.argv) > 2 and sys.argv[1] == "--pas":
    sys.exit(pas(sys.argv[2], groot="--groot" in sys.argv, teksten="--teksten" in sys.argv, smal="--smal" in sys.argv))


# ============================================================================================ in dit proces ===

os.environ.pop("LANGUAGE", None)
os.environ.update(omgeving(TMP / "thuis"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402

import bugos_ui  # noqa: E402
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QVBoxLayout, QWidget  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = QColor(h)
        uit = []
        for v in (c.redF(), c.greenF(), c.blueF()):
            uit.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * uit[0] + 0.7152 * uit[1] + 0.0722 * uit[2]
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def verwerk(n: int = 3) -> None:
    for _ in range(n):
        QApplication.processEvents()


app = bugos_ui.maak_app("bugos-layout-test", "bugos-layout-test", ["test"])
from bugos_ui import (  # noqa: E402
    K, KLEUREN, LIJN, MATEN, ActieBalk, Groep, KeuzeKaart, Knop, Rij, Schuif, Zijbalk, Zoekveld, label, px,
    sectie_met_knop, vraag_ja, vraag_tekst,
)
import bugos_shell  # noqa: E402
import bugos_widgets  # noqa: E402
from bugos_settings_onderdelen import Keuzes, stijl  # noqa: E402

css = app.styleSheet()

# ------------------------------------------------------------------------------------------- de maten ---
# De keuze van de eigenaar: "Compact, de ronde hoeken blijven". P01-P10 wel, T01-T04 niet.
klopt(Knop("x").minimumHeight() == px(36), f"P01: een gewone knop is 36 px hoog ({Knop('x').minimumHeight()})")
klopt(Knop("x", groot=True).minimumHeight() == px(44), "P02: de grote hoofdknop is 44 px hoog")
klopt("padding: 6px 16px; font-size: 14px" in css and "padding: 5px 15px" in css,
      "P01: knoppen hebben 6 px 16 px binnenruimte (5 px 15 px met de rode focusrand), dus de maat springt niet")
klopt('QPushButton[groot="true"] { padding: 10px 22px;' in css, "P02: de grote knop heeft 10 px 22 px binnenruimte")
klopt(Zoekveld("zoek").minimumHeight() == px(36) and "padding: 7px 12px;\n  font-size: 14px" in css,
      "P03: een zoek- of invoerveld is 36 px hoog, met 14 px letters")
klopt("QComboBox {" in css and "padding: 6px 12px; font-size: 14px" in css, "P04: een keuzelijstje is compact (6 px 12 px)")
_zb = Zijbalk()
_it = _zb.voeg_toe("lijn:huis", "Home", "start")
klopt(_it.sizeHint().height() == px(40) and "QListWidget#zijbalk::item { padding: 8px 12px;" in css,
      "P05: een regel in de zijbalk is 40 px hoog")
klopt('QLabel[rol="titel"] { font-family: "Funnel Display"; font-size: 28px;' in css
      and "QLabel[rol=\"sub\"] { color: " in css and "font-size: 14px; }" in css.split('QLabel[rol="sub"]')[1].split("\n")[0],
      "P06: paginatitel 28 px, de regel eronder 14 px")
klopt(Schuif().sizeHint() == QSize(44, 24) and Schuif().size() == QSize(44, 24), "P07: het aan/uit-schuifje is 44 x 24")
klopt("QPushButton#rond { min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; border-radius: 18px;" in css
      and "QPushButton#rond_klein { min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px; border-radius: 16px;" in css,
      "P08: ronde knopjes 36 en 32 px")
_m = bugos_shell.Melding()
klopt(_m.knop.minimumHeight() == px(32), "P10: de knop in een melding is 32 px")
# T01-T02 blijven zoals ze waren (de eigenaar koos ervoor).
klopt(MATEN["knop"] == 12 and MATEN["kaart"] == 16 and MATEN["groot"] == 22,
      "T01: de ronde hoeken blijven 12/16/22 (en daarmee alles wat de makers eruit bouwen)")
klopt("border-radius: 12px;\n  padding: 6px 16px" in css and 'QFrame[kaart="true"] { background:' in css
      and "border-radius: 16px; }" in css, "T01: knoppen 12 px rond, kaarten 16 px")
klopt('QLabel[rol="rij"] { font-size: 15px; font-weight: 500; }' in css
      and "QLabel[rol=\"klein\"] { color: " in css and "font-size: 13px; }" in css.split('QLabel[rol="klein"]')[1].split("\n")[0],
      "T02: de titel van een regel blijft 15 px, de uitleg 13 px")

# Grote letters: de knoppen groeien mee (anders zat een letter van 21 px klem in 36 px).
bugos_ui.SCHAAL = 1.5
klopt(Knop("x").minimumHeight() == 54 and Zoekveld("z").minimumHeight() == 54,
      "P01/P03: met 'Grote letters' (1,5x) groeien knop en zoekveld mee (54 px)")
_sk = sectie_met_knop("Your devices", Knop("Pair a new device", "stil"))
_knop = _sk.findChildren(Knop)[0]
klopt(_sk.height() == 48 and _knop.minimumHeight() == 48, "R06: het kopje met knop groeit mee met grote letters (48 px)")
bugos_ui.SCHAAL = 1.0

# ------------------------------------------------------------------------------------ twee nieuwe iconen ---
for _naam in ("telefoon", "microfoon"):
    klopt(_naam in LIJN, f"lijn-icoon '{_naam}' bestaat (voor wifi/bluetooth en geluid)")
    _beeld: QImage = bugos_ui.lijn_pixmap(_naam, "#000000", 96).toImage()
    _xs, _ys = [], []
    for _y in range(_beeld.height()):
        for _x in range(_beeld.width()):
            if _beeld.pixelColor(_x, _y).alpha() > 40:
                _xs.append(_x)
                _ys.append(_y)
    _ok = bool(_xs) and min(_xs) >= 4 and max(_xs) <= 92 and min(_ys) >= 4 and max(_ys) <= 92
    # Even groot als de buren (computer, muis): tussen 50 en 90 % van het vak hoog.
    _hoog = (max(_ys) - min(_ys)) / 96 if _xs else 0
    klopt(_ok and 0.5 <= _hoog <= 0.92, f"lijn-icoon '{_naam}' tekent binnen het 24-raster, zo groot als de rest ({_hoog:.2f})")

# ------------------------------------------------------------------------- R11 schijf-tegeltje (Back-up) ---
_sk_kiezer = bugos_ui.SchijfKiezer("Plug in a USB stick")
_sk_kiezer.zet([("stick", "USB stick", "180 GB free of 256 GB")])
_chips = [c for c in _sk_kiezer.findChildren(bugos_widgets.IcoonChip) if c.neutraal]
klopt(bool(_chips) and all(c.lijn == "usb" and not c.vol for c in _chips),
      "R11: een schijf staat als lijnicoon op een grijs tegeltje; het volgt de tekstkleur, ook in het donker")

# ---------------------------------------------------------------------------------------- D01 lijntjes ---
_g = Groep()
_a, _b, _c = (_g.voeg(label(x)) for x in ("A", "B", "C"))
_g.show()
verwerk()


def _lijnen(g) -> int:
    return sum(1 for i in range(g.lay.count()) if g.lay.itemAt(i).widget() is not None
               and g.lay.itemAt(i).widget().objectName() == "lijn" and not g.lay.itemAt(i).widget().isHidden())


klopt(_lijnen(_g) == 2, f"D01: drie regels, twee lijntjes ({_lijnen(_g)})")
_b.hide()
klopt(_lijnen(_g) == 1, "D01: een verborgen regel laat geen lege strook met een lijntje achter")
_b.show()
klopt(_lijnen(_g) == 2, "D01: komt de regel terug, dan ook zijn lijntje")
_a.hide()
klopt(_lijnen(_g) == 1, "D01: eerste regel weg: geen lijntje bovenaan")
_a.show()
_c.hide()
klopt(_lijnen(_g) == 1, "D01: laatste regel weg: geen lijntje onderaan")
_b.hide()
klopt(_lijnen(_g) == 0, "D01: twee verborgen regels onder elkaar: geen lijntje")
_g.hide()

# --------------------------------------------------------------------------------------- D02 KeuzeKaart ---
_houder = QWidget()
_hl = QVBoxLayout(_houder)
_binnen = QWidget()
_bl = QVBoxLayout(_binnen)
_bl.addWidget(label("I choose when", "kop3"))
_uitleg = label("BugOS asks before it updates. Update your apps with 'Update now' in Settings, whenever it suits "
                "you. You can always change this later.", "klein")
_bl.addWidget(_uitleg)
_kaart = KeuzeKaart(_binnen)
_hl.addWidget(_kaart)
_hl.addStretch(1)
_houder.resize(300, 600)
_houder.show()
verwerk()
_houder.resize(280, 600)
verwerk()
klopt(_uitleg.height() >= _uitleg.heightForWidth(_uitleg.width()) - 1,
      f"D02: een keuzekaart groeit mee met zijn afgebroken uitleg ({_uitleg.height()} >= {_uitleg.heightForWidth(_uitleg.width())})")
_houder.hide()

# ---------------------------------------------------------------------------------------- D03 Rij stapelt ---
_rijhouder = QWidget()
_rl = QVBoxLayout(_rijhouder)
_rl.setContentsMargins(0, 0, 0, 0)
_rg = Groep()
_keuzes = Keuzes([(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min"), (0, "Never")])
_rij = Rij("klok", "Sleep when you do nothing", "Saves power.", _keuzes)
_rg.voeg(_rij)
_schuifrij = Rij("wifi", "Wi-Fi", "On", Schuif(True))
_rg.voeg(_schuifrij)


class _Getal(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(label("12 %", "klein", wrap=False))
        self.setFixedWidth(200)


_getalrij = Rij("app", "Firefox", "", _Getal())
_rg.voeg(_getalrij)
_rl.addWidget(_rg)
_rijhouder.resize(500, 400)
_rijhouder.show()
verwerk(5)
klopt(_rij._gestapeld and _rij.rechts.geometry().top() >= _rij.titel.geometry().bottom(),
      "D03: te smal (500 px): de keuzes gaan onder de tekst, zoals Windows 11")
klopt(_rij.rechts.geometry().right() <= _rij.width() <= 500, "D03: gestapeld valt er niets rechts buiten de regel")
_eenregel = 26 + 24 + 28 + _rij.titel.sizeHint().width() + _rij.rechts.sizeHint().width()
klopt(_rij.minimumSizeHint().width() < _eenregel,
      f"D03: de regel mag smaller dan één regel breed ({_rij.minimumSizeHint().width()} < {_eenregel}; nooit smaller "
      f"dan de keuzes zelf)")
klopt(not _getalrij._gestapeld, "D03: getallen (zoals in Taakbeheer) blijven altijd rechts onder hun kopjes")
_rijhouder.resize(1000, 400)
verwerk(5)
klopt(not _rij._gestapeld and abs(_rij.rechts.geometry().center().y() - _rij.height() // 2) <= 4,
      "D03: weer breed genoeg (1000 px): de keuzes staan weer rechts, in het midden")
for _ in range(3):   # heen en weer: niets blijft achter
    _rijhouder.resize(500, 400)
    verwerk(3)
    _rijhouder.resize(1000, 400)
    verwerk(3)
klopt(_rij.layout().itemAt(1).layout().count() == 2, "D03: na vaak heen en weer staan er geen lege plekken in de regel")
_rijhouder.resize(320, 400)
verwerk(5)
klopt(not _schuifrij._gestapeld, "D03: een regel met alleen een schuifje stapelt niet (ook niet bij 320 px)")
# Een titel die zelfs gestapeld niet op één regel past (grote letters, 150 %): hij breekt af, nooit afgeknipt.
_lang = Rij("muis", "Lost the pointer? Shake the mouse quickly and it grows for a moment", "", Schuif(False))
_rg.voeg(_lang)
_rijhouder.resize(340, 500)
verwerk(5)
klopt(_lang.titel.wordWrap() and _lang.titel.height() >= _lang.titel.heightForWidth(_lang.titel.width()) - 1
      and _lang.titel.geometry().right() <= _lang.width(),
      f"R10: een te lange titel breekt af in plaats van afgeknipt te worden ({_lang.titel.width()} px breed)")
_rijhouder.resize(1000, 500)
verwerk(5)
klopt(not _lang.titel.wordWrap() and not _lang._gestapeld, "R10: weer breed genoeg: de titel staat weer op één regel")


class _NooitStapel(Rij):
    STAPELBAAR = False


_nooit = _NooitStapel("klok", "Sleep when you do nothing", "", Keuzes([(1, "One"), (2, "Two"), (3, "Three")]))
klopt(not _nooit._kan_stapelen(), "D03: met STAPELBAAR = False blijft wat rechts staat rechts")
_rijhouder.hide()

# ------------------------------------------------------------------------------------ D04 knoppenbalk ---
_venster = QWidget()
_venster.resize(1400, 400)
_balk = ActieBalk(_venster)
for _s, _ic, _w in (("open", "openen", "Open"), ("kopie", "kopieer", "Copy"), ("knip", "schaar", "Cut"),
                    ("naam", "potlood", "Rename"), ("weg", "prullenbak", "Delete")):
    _balk.knop(_s, _ic, _w, lambda: None)
_balk.klaar()
_venster.show()
_balk.toon(2)
_balk.plaats(QRect(0, 0, 400, 300))
verwerk()
klopt(all(not k.text() and k.toolTip() and k.accessibleName() == k.toolTip() for k in _balk.knoppen.values()),
      "D04: te smal: alleen icoontjes, met het woord als tip en voor de schermlezer")
_balk.plaats(QRect(0, 0, 1400, 300))
verwerk()
klopt([k.text() for k in _balk.knoppen.values()] == ["Open", "Copy", "Cut", "Rename", "Delete"],
      "D04: weer breed genoeg: de woorden staan er weer")
_balk.knoppen["weg"].setText("Stop")
_balk.plaats(QRect(0, 0, 400, 300))
_balk.plaats(QRect(0, 0, 1400, 300))
klopt(_balk.knoppen["weg"].text() == "Stop", "D04: een tekst die de app later zet, blijft (bijv. 'Stop' in Taakbeheer)")
_weg = _balk.knoppen["weg"]
klopt(not _weg.accessibleName() and not _weg.toolTip(),
      "D04: met woorden geen vaste naam: de schermlezer leest het woord dat er nu staat")
_weg.setText("End")                         # zoals Taakbeheer: 'Sluiten' wordt 'Beëindigen'
_balk.plaats(QRect(0, 0, 1400, 300))
klopt(_weg.text() == "End" and not _weg.accessibleName(), "D04: de app zet 'End': de schermlezer zegt 'End', niet 'Delete'")
_balk.plaats(QRect(0, 0, 400, 300))
klopt(not _weg.text() and _weg.accessibleName() == "End" and _weg.toolTip() == "End",
      "D04: daarna te smal: het icoontje heet 'End' (tip en schermlezer), niet het oude woord")
_balk.plaats(QRect(0, 0, 1400, 300))
_weg.setText("Close")
_balk.plaats(QRect(0, 0, 400, 300))
klopt(_weg.accessibleName() == "Close" and _weg.toolTip() == "Close",
      "D04: smal - breed - nieuw woord - smal: de naam loopt niet een stap achter")
_weg.setText("Stop")
_balk.plaats(QRect(0, 0, 400, 300))
klopt(not _weg.text() and _weg.accessibleName() == "Stop", "D04: een nieuw woord terwijl alleen icoontjes passen: tip en naam volgen")
_balk.plaats(QRect(0, 0, 1400, 300))
klopt(_weg.text() == "Stop" and not _weg.toolTip(), "D04: weer breed: het nieuwe woord staat er, zonder overbodige tip")
_venster.hide()

# ---------------------------------------------------------------------------------- D09 gekozen keuze ---
def _streep(knop) -> tuple[bool, bool]:
    """Teken een gekozen StreepKnop: is er onderaan in het midden een rode streep, en zijn de hoeken onderaan vrij
    (een korte rechte streep, geen rand die in de ronde hoeken omhoog buigt)?"""
    beeld = knop.grab().toImage()
    rood = QColor(K["accent"])

    def is_rood(x, y) -> bool:
        c = beeld.pixelColor(x, y)
        return abs(c.red() - rood.red()) < 40 and abs(c.green() - rood.green()) < 40 and abs(c.blue() - rood.blue()) < 40

    h = beeld.height()
    midden = any(is_rood(beeld.width() // 2, y) for y in range(h - 7, h))
    # Een rand onderaan buigt in de ronde hoeken omhoog (tot ~12 px hoog); daar staat nooit tekst.
    hoeken = any(is_rood(x, y) for x in list(range(0, 12)) + list(range(beeld.width() - 12, beeld.width()))
                 for y in range(h - 12, h))
    return midden, not hoeken


for _thema in ("licht", "donker"):
    K.clear()
    K.update(KLEUREN[_thema])
    _st = stijl()
    _regel = next((r for r in _st.split("}") if "QPushButton#keus:checked" in r), "")
    klopt(K["accent_gekozen"] in _regel and K["accent_zacht"] in _regel and "border-bottom" not in _regel,
          f"D09 ({_thema}): de gekozen keuze is zacht rood met rode letters (zoals de zijbalk), geen gebogen rand")
    klopt(contrast(K["accent_gekozen"], K["accent_zacht"]) >= 4.5,
          f"D09 ({_thema}): de rode letters halen 4,5:1 op het zachtrode vlak "
          f"({contrast(K['accent_gekozen'], K['accent_zacht']):.2f}:1)")
    klopt(contrast(K["accent"], K["accent_zacht"]) >= 3.0,
          f"D09 ({_thema}): de streep haalt 3:1 tegen het zachtrode vlak "
          f"({contrast(K['accent'], K['accent_zacht']):.2f}:1, WCAG 1.4.11)")
    _kz = Keuzes([(1, "5 min"), (2, "10 min")])
    _kz.setStyleSheet(_st)
    _kz.zet(2)
    _k2 = _kz.knoppen[2]
    klopt(isinstance(_k2, bugos_ui.StreepKnop), f"D09 ({_thema}): elke keuze is een StreepKnop")
    _mid, _vrij = _streep(_k2)
    klopt(_mid and _vrij, f"D09 ({_thema}): gekozen = een korte rechte streep onderaan in het midden, de hoeken vrij")
    _mid, _ = _streep(_kz.knoppen[1])
    klopt(not _mid, f"D09 ({_thema}): een keuze die niet gekozen is, heeft geen streep")
K.clear()
K.update(KLEUREN["licht"])

# ------------------------------------------------------------------------------------- D10 kopje + knop ---
_sk = sectie_met_knop("Printers", Knop("Add a printer", "stil"))
_knop = _sk.findChildren(Knop)[0]
klopt(_sk.height() == 32 and _knop.height() <= 32 and _knop.property("klein") == "true",
      "D10: een kopje met een knop is even hoog als een kopje (32 px), met een compacte stille knop")
klopt('QPushButton[klein="true"] { padding: 4px 8px; }' in css, "D10: de compacte knop heeft weinig binnenruimte")
klopt(hasattr(bugos_ui, "sectie_met_knop") and hasattr(bugos_ui, "vraag_ja") and hasattr(bugos_ui, "vraag_tekst"),
      "D10/D11: de nieuwe hulpjes komen ook uit bugos_ui")

# -------------------------------------------------------------------------------------------- D11 vragen ---
_gezien: list = []
_echt_exec = QDialog.exec


def _nep_exec(antwoord, tekst=None):
    def exec_(self):
        _gezien.append(self)
        if tekst is not None and getattr(self, "veld", None) is not None:
            self.veld.setText(tekst)
        return QDialog.DialogCode.Accepted if antwoord else QDialog.DialogCode.Rejected
    return exec_


QDialog.exec = _nep_exec(True)
klopt(vraag_ja(None, "Remove printer?", "It is gone afterwards.", "Remove") is True, "D11: vraag_ja: 'ja' geeft True")
_d = _gezien[-1]
_knoppen = [w for w in _d.findChildren(Knop)]
klopt(_d.kop.property("rol") == "kop2" and _d.layout().contentsMargins().left() == 24,
      "D11: de vraag heeft een kop en ruime marges, zoals KiesDialoog")
klopt([k.text() for k in _knoppen] == ["Cancel", "Remove"] and _knoppen[1].property("soort") == "hoofd"
      and _knoppen[0].property("soort") == "stil", "D11: rechts 'Annuleren' (stil) en dan de rode knop")
klopt(_d.standaard == "Remove", "D11: Enter kiest gewoon 'ja'")
QDialog.exec = _nep_exec(False)
klopt(vraag_ja(None, "Go back?", "…", "Go back", enter_is_nee=True) is False and _gezien[-1].standaard == "Cancel",
      "D11: enter_is_nee: Enter doet niets (Annuleren), en Annuleren geeft False (U380)")
QDialog.exec = _nep_exec(True, "Bugie")
klopt(vraag_tekst(None, "Your name", "How should BugOS call you?", "Old") == "Bugie",
      "D11: vraag_tekst geeft de getypte tekst")
QDialog.exec = _nep_exec(True)
vraag_tekst(None, "Rename", "New name", "Letter.odt", kies_tot=6)
klopt(_gezien[-1].veld.selectedText() == "Letter", "D11: kies_tot: alleen de naam zonder '.odt' is gekozen")
vraag_tekst(None, "Wi-Fi password", "For Home-5G", wachtwoord=True)
_d = _gezien[-1]
klopt(_d.veld.echoMode() == QLineEdit.EchoMode.Password and _d.oog is not None and not _d.veld.toolTip(),
      "D11: wachtwoord: bolletjes, 'Laten zien' erbij, en het staat nergens in een tip")
QDialog.exec = _nep_exec(False)
klopt(vraag_tekst(None, "Your name", "?", "Bugie") is None, "D11: Annuleren bij vraag_tekst geeft None")
QDialog.exec = _echt_exec


def _druk(d, wie, toets=Qt.Key.Key_Return) -> str:
    """Open de vraag echt, zet de focus op 'wie' (zoals met Tab) en druk op een toets: wat gebeurt er?"""
    def doe():
        w_ = getattr(d, wie)
        w_.setFocus(Qt.FocusReason.TabFocusReason)
        verwerk()
        QTest.keyClick(w_, toets)
    QTimer.singleShot(50, doe)
    QTimer.singleShot(3000, d.reject)    # nooit blijven hangen
    return "ja" if d.exec() == QDialog.DialogCode.Accepted else "nee"


_V = bugos_shell.VraagDialoog
klopt(_druk(_V(None, "Remove printer?", "x", "Remove"), "nee") == "nee",
      "D11: Tab naar 'Annuleren' + Enter = annuleren (de printer blijft)")
klopt(_druk(_V(None, "Remove printer?", "x", "Remove"), "ja") == "ja", "D11: Tab naar 'Verwijderen' + Enter = verwijderen")
klopt(_druk(_V(None, "Go back?", "x", "Go back", enter_is_nee=True), "ja") == "ja",
      "D11: enter_is_nee, Tab naar 'Teruggaan' + Enter = teruggaan (Enter doet de knop waar je op staat)")
klopt(_druk(_V(None, "Go back?", "x", "Go back", enter_is_nee=True), "nee") == "nee",
      "D11: enter_is_nee, Enter op 'Annuleren' = annuleren")
klopt(_druk(_V(None, "Rename", "New name", "Rename", veld=True, waarde="Letter.odt"), "nee") == "nee",
      "D11: vraag_tekst, Tab naar 'Annuleren' + Enter = annuleren (de naam blijft)")
klopt(_druk(_V(None, "Rename", "New name", "Rename", veld=True, waarde="Letter.odt"), "veld") == "ja",
      "D11: vraag_tekst, Enter in het tekstveld = OK")
klopt(_druk(_V(None, "Wi-Fi", "pw", "Connect", veld=True, wachtwoord=True), "oog") == "ja",
      "D11: Enter op 'Laten zien' verstuurt (het is een vinkje, geen eigen knop); spatie zet het om")
_d = _V(None, "Wi-Fi", "pw", "Connect", veld=True, wachtwoord=True)
_d.show()
verwerk()
_d.oog.setFocus()
QTest.keyClick(_d.oog, Qt.Key.Key_Space)
klopt(_d.oog.isChecked() and _d.isVisible(), "D11: spatie op 'Laten zien' laat het wachtwoord zien en sluit de vraag niet")
_d.close()
for _uitleg in ("Sure?", "Your computer restarts with the previous version of BugOS. Your files stay where they are.",
                "A much longer explanation that goes on. " * 6):
    _d = _V(None, "Go back to the previous version?", _uitleg, "Go back", enter_is_nee=True)
    _d.show()
    verwerk()
    _gat = _d.ja.geometry().top() - _d.uitleg.geometry().bottom()
    klopt(_gat <= 24 and _d.uitleg.height() >= _d.uitleg.heightForWidth(_d.uitleg.width()) - 1,
          f"D11: geen lege strook boven de knoppen ({_gat} px) en de uitleg is heel ({len(_uitleg)} tekens)")
    _d.close()

# ----------------------------------------------------------------------------- op het scherm (helper) ---
_scherm = QApplication.primaryScreen()
_vrij = bugos_ui.vrije_ruimte(_scherm)
klopt(_vrij is not None and (_scherm.availableGeometry() != _scherm.geometry()
                            or _vrij.height() == _scherm.geometry().height() - bugos_ui.TAAKBALK),
      "R02: zegt het scherm niet waar de taakbalk is (Wayland), dan gaat die er zelf af (48 px)")
(_b2, _h2), _min = bugos_ui.schermmaat((5000, 5000), (5000, 5000))
klopt(_b2 <= _vrij.width() and _h2 <= _vrij.height() - bugos_ui.TITELBALK and _min == (_b2, _h2),
      "R02/R09: een te groot venster wordt zo groot als er vrij is, met ruimte voor de titelbalk")
_groot = QWidget()
_groot.resize(4000, 3000)
bugos_ui.pas_in_scherm(_groot)
klopt(_groot.width() <= _vrij.width() and _groot.height() <= _vrij.height() - bugos_ui.TITELBALK,
      "R02: pas_in_scherm (in uitvoeren) maakt ook Welkom, Hulp en Back-up passend")
_klein = QWidget()
_klein.resize(300, 200)
bugos_ui.pas_in_scherm(_klein)
klopt(_klein.size() == QSize(300, 200), "R02: een venster dat past, blijft zoals het is")

# ------------------------------------------------------------------------------- Instellingen zelf ---
lader = importlib.machinery.SourceFileLoader("bugos_settings_layout", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("bugos_settings_layout", lader)
inst = importlib.util.module_from_spec(spec)
sys.modules["bugos_settings_layout"] = inst
lader.exec_module(inst)
w = inst.Instellingen()
w.show()
verwerk()
klopt(w.height() <= _vrij.height() - bugos_ui.TITELBALK, f"R09: Instellingen laat ruimte voor zijn titelbalk ({w.height()})")
_tabs = [k for g in w.groepen.values() for k in g.tabs.values()]
_ts = inst.tab_stijl()
klopt(K["accent_zacht"] in _ts and K["accent_gekozen"] in _ts and "border-bottom" not in _ts
      and "background: transparent" in _ts and all(isinstance(k, bugos_ui.StreepKnop) for k in _tabs),
      "D12: stille tabjes: gekozen = zacht rood met rode letters en een korte streep eronder (StreepKnop)")
_mid, _vrij = _streep(next(k for k in _tabs if k.isChecked()))
klopt(_mid and _vrij, "D12: de streep onder het gekozen tabje is kort en recht, in het midden")
K.clear()
K.update(KLEUREN["donker"])
_ts_donker = inst.tab_stijl()
K.clear()
K.update(KLEUREN["licht"])
klopt("#DE2F3E" not in _ts_donker and KLEUREN["donker"]["accent_gekozen"] in _ts_donker,
      "D12: in het donker de kleuren van het donkere thema (geen vaste #DE2F3E meer)")
klopt(all(k.minimumHeight() == px(32) and k.objectName() == "tab" and k.isCheckable() for k in _tabs),
      "D12/P09: elk tabje is 32 px hoog")
klopt(contrast(K["accent"], K["achter"]) >= 3.0, "D12: de streep onder het gekozen tabje haalt 3:1 tegen de achtergrond")
_dl = w.groepen["apparaten"].layout().itemAt(0).layout()
_breed, _smal = _dl.heightForWidth(2000), _dl.heightForWidth(px(300))
_dl.setGeometry(QRect(0, 0, px(300), _smal))
_ab = list(w.groepen["apparaten"].tabs.values())
klopt(isinstance(_dl, inst.Doorloop) and _smal > _breed
      and all(k.width() >= k.sizeHint().width() and k.geometry().right() < px(300) for k in _ab),
      f"R07: passen de tabjes niet naast elkaar (grote letters, 150 %), dan gaan ze naar een tweede regel, heel "
      f"({_breed} -> {_smal} px hoog)")
_dl.setGeometry(QRect(0, 0, 2000, _breed))
klopt(len({k.y() for k in _ab}) == 1, "R07: met ruimte staan alle tabjes op één regel")
# B-02: Kolommen (Start: vier snelle schuifjes, Energie: drie kaarten). Breed: alles naast elkaar; smal: 4 -> 2 -> 1,
# nooit 3 + 1; een verborgen kaart laat geen gat achter.
_kol = inst.Kolommen(12)
_kaartjes = []
for _i in range(4):
    _kj = QWidget()
    _kj.setMinimumWidth(120)
    _kaartjes.append(_kol.voeg(_kj))
_kol.show()
for _breed, _verwacht in ((600, 4), (500, 2), (260, 2), (200, 1)):
    _kol.resize(_breed, 300)
    verwerk()
    klopt(_kol.kolommen == _verwacht, f"B-02: Kolommen met vier kaarten op {_breed} px: {_verwacht} naast elkaar "
                                      f"({_kol.kolommen})")
_kol.resize(600, 300)
_kaartjes[1].hide()
verwerk()
klopt(_kol.kolommen == 3 and _kaartjes[2].x() < _kaartjes[3].x() and _kaartjes[0].x() < _kaartjes[2].x(),
      "B-02: een verborgen kaart (geen wifi) laat geen gat achter: de andere drie schuiven op")
klopt(_kol.minimumSizeHint().width() == 120, "B-02: Kolommen wordt zo smal als de breedste kaart (dan onder elkaar)")
_kol.hide()
# B-02: een rij keuzes loopt door naar een tweede regel in plaats van de pagina breder te maken.
_kz = Keuzes([(1, "5 min"), (2, "10 min"), (3, "30 min"), (4, "1 hour"), (0, "Never")])
klopt(isinstance(_kz.layout(), inst.Doorloop) and _kz.minimumSizeHint().width() < _kz.sizeHint().width() // 2
      and _kz.heightForWidth(_kz.minimumSizeHint().width()) > _kz.heightForWidth(_kz.sizeHint().width()),
      "B-02: Keuzes zijn smaller te maken dan alles naast elkaar (dan meer regels)")
w.ga_naar("wifi")
verwerk()
_enkel = w.paginas["wifi"].titel.mapTo(w, QPoint(0, 0)).y()
w.ga_naar("bluetooth")
verwerk()
_groep = w.paginas["bluetooth"].titel.mapTo(w, QPoint(0, 0)).y()
klopt(0 < _groep - _enkel <= 40, f"D12: de titel onder de tabjes staat bijna even hoog als zonder tabjes ({_enkel} -> {_groep})")
# D01 in het echt: wifi heeft een verborgen regel 'Kabel'
w.ga_naar("wifi")
verwerk()
_wifi = w.paginas["wifi"]
for _g in _wifi.findChildren(Groep):
    for _i in range(_g.lay.count()):
        _x = _g.lay.itemAt(_i).widget()
        if _x is not None and _x.objectName() == "lijn" and not _x.isHidden():
            _na = _g.lay.itemAt(_i + 1).widget() if _i + 1 < _g.lay.count() else None
            klopt(_na is not None and not _na.isHidden(), "D01: op Wifi staat geen lijntje boven een verborgen regel")
# D07: Over deze computer
w.ga_naar("over")
verwerk()
_over = w.paginas["over"]
klopt(len(_over.info) == 6 and _over.info[0][1] == "44.20261110" and "fc44" in _over.info[-1][1],
      "D07: de voorbeeldstand toont zes geloofwaardige regels (niet de computer waarop de test draait)")
_rijen = [x for x in _over.findChildren(QWidget, "info") if x.isVisible()]
_waarden = [x.findChildren(QLabel)[1] for x in _rijen]
klopt(_rijen and all(lab.width() > 300 and lab.height() < 30 for lab in _waarden),
      "D07: een waarde krijgt de vrije breedte en past op één regel")
# D08: Engelse voorbeeldnamen
import bugos_config as bi  # noqa: E402

bi._VB["aanwijzers"] = None
klopt(bi.aanwijzers()[0].naam == "Logitech mouse", "D08: de voorbeeldmuis heeft een Engelse naam op een Engels scherm")
# D11 in Instellingen: 'Terug naar de vorige versie' is de BugOS-vraag (Enter = Annuleren)
QDialog.exec = _nep_exec(False)
_gestart: list = []
_up = w.paginas["updates"]
_oud = _up.updates
_up.updates = lambda wat: _gestart.append(wat)
_up.vraag_terug()
klopt(isinstance(_gezien[-1], bugos_shell.VraagDialoog) and _gezien[-1].standaard == "Cancel" and not _gestart,
      "D11: 'Terug naar de vorige versie?' is de gedeelde vraag; Enter doet niets")
_up.updates = _oud
QDialog.exec = _echt_exec

# D05: Uiterlijk. Drie plaatjes van 176 x 99 met 'Eigen foto kiezen' ernaast pasten niet (de pagina schoof opzij,
# de knop werd afgeknipt). Nu: plaatjes van 144 x 81 in een Doorloop, de knop op een eigen regel eronder. Of het
# echt past, ziet T-FIT hieronder (elke schaal); hier staat de opbouw vast, ook voor wat T-FIT niet draait (150 %
# met grote letters: dan is er naast de zijbalk maar 391 px vrij).
w.ga_naar("uiterlijk")
verwerk()
_ui = w.paginas["uiterlijk"]
# getattr: is de opbouw ooit anders, dan een gewone FOUT (en loopt de rest van de test door) in plaats van een crash.
_plaatjes, _eigen = getattr(_ui, "plaatjes", None), getattr(_ui, "eigen", None)
_pl = [_plaatjes.itemAt(_i).widget() for _i in range(_plaatjes.count())] if _plaatjes is not None else []
klopt(isinstance(_plaatjes, inst.Doorloop) and len(_pl) == 3 and all(k.iconSize() == QSize(144, 81) for k in _pl),
      f"D05: Uiterlijk: {len(_pl)} plaatjes van 144 x 81, in een Doorloop (ze gaan door naar een volgende regel)")
klopt(bool(_pl) and _eigen is not None and _eigen.geometry().top() > max(k.geometry().bottom() for k in _pl)
      and _eigen.x() == _pl[0].x() and _eigen.width() >= _eigen.sizeHint().width(),
      "D05: 'Eigen foto kiezen' staat onder de plaatjes, links, met zijn hele breedte")
if isinstance(_plaatjes, inst.Doorloop) and _pl:
    # De Doorloop zelf, op een vaste breedte (hoe breed de pagina hier is, hangt af van het scherm van de test).
    _plek = _plaatjes.geometry()     # waar de plaatjes nu echt liggen: straks weer terug
    for _breed, _regels in ((600, 1), (391, 2)):
        _plaatjes.setGeometry(QRect(_plek.x(), _plek.y(), _breed, _plaatjes.heightForWidth(_breed)))
        klopt(len({k.y() for k in _pl}) == _regels and all(k.geometry().right() < _plek.x() + _breed for k in _pl),
              f"D05: {_breed} px breed: de plaatjes staan op {_regels} regel(s) en niets steekt rechts uit")
    _plaatjes.setGeometry(_plek)
# De kaarten Licht en Donker: hoogstens 264 px; bij weinig ruimte delen ze de regel (hun minimum won het nooit).
klopt(all(k.maximumWidth() == 264 for k in _ui.thema.values()),
      "D05: de kaarten Licht en Donker worden niet breder dan 264 px (zoals altijd bij 100 %)")

# T-ALIGN: op elke pagina beginnen de kaarten (en keuzekaarten) links op dezelfde lijn als de titel. Kaarten naast
# elkaar (Energie: drie profielen) tellen per regel: de linkse moet op de lijn staan (D06: 9 px ingesprongen).
from bugos_ui import KeuzeKaart as _KK  # noqa: E402

BEKEND_UITLIJNING: dict = {}   # nu leeg: D06 (Energie) is opgelost
_uitlijning_gezien: set[str] = set()   # welke bekende meldingen er deze keer echt waren
_scheef = []
for _klasse in inst.PAGINAS:
    w.ga_naar(_klasse.sleutel)
    verwerk()
    _blad = w.paginas[_klasse.sleutel]
    _binnen = _blad.widget()
    if _blad.titel is None:
        continue
    _x0 = _blad.titel.mapTo(_binnen, QPoint(0, 0)).x()
    _regels: dict[int, int] = {}
    for _k in _binnen.findChildren(QWidget):
        if not _k.isVisible() or not (_k.property("kaart") or isinstance(_k, _KK)):
            continue
        _ouder, _genest = _k.parentWidget(), False
        while _ouder is not None and _ouder is not _binnen:
            if _ouder.property("kaart") or isinstance(_ouder, _KK):
                _genest = True     # een kaart in een kaart: die volgt de buitenste
                break
            _ouder = _ouder.parentWidget()
        if _genest:
            continue
        _p = _k.mapTo(_binnen, QPoint(0, 0))
        _regels[_p.y()] = min(_regels.get(_p.y(), 10 ** 6), _p.x())
    _fout = sorted({_x for _x in _regels.values() if abs(_x - _x0) > 1})
    if _fout:
        _melding = f"{_klasse.sleutel}: titel op x={_x0}, kaarten op x={_fout}"
        if _melding in BEKEND_UITLIJNING:
            print(f"BEKEND T-ALIGN {_melding}  <- {BEKEND_UITLIJNING[_melding]}")
            _uitlijning_gezien.add(_melding)
        else:
            _scheef.append(_melding)
klopt(not _scheef, "T-ALIGN: op elke pagina beginnen de kaarten op dezelfde lijn als de titel"
      + "".join(f"\n        {x}" for x in _scheef))
for _melding, _reden in BEKEND_UITLIJNING.items():
    if _melding not in _uitlijning_gezien:   # geen fout: wel een teken dat de regel weg mag
        print(f"OPGELOST? BEKEND_UITLIJNING {_melding!r} kwam niet meer voor: haal hem weg  <- {_reden}")

w.close()
verwerk()

# ------------------------------------------------------------------------- past elk venster? (T-FIT) ---
for _naam, _problemen, _klaar in schermtest():
    # De ronde 'half scherm' bouwt alleen Instellingen (B-02); de andere rondes alle acht apps.
    klopt(len(_klaar) == (1 if "half" in _naam else 8),
          f"T-FIT {_naam}: alle apps van deze ronde zijn gebouwd en bekeken ({', '.join(_klaar)})")
    _echt = []
    for _p in _problemen:
        _reden = bekend(_p, _naam)
        if _reden:
            print(f"BEKEND {_p}  <- {_reden}")
        else:
            _echt.append(_p)
    klopt(not _echt, f"T-FIT {_naam}: op 1280x800 past alles: geen venster te groot (taakbalk {TAAKBALK_ECHT} px, "
                     f"titelbalk {TITELBALK_ECHT} px), niets schuift opzij, niets afgeknipt, de hoofdknop in beeld"
                     + "".join(f"\n        {x}" for x in _echt[:25]))
# Een bekende regel die in geen enkele ronde meer voorkwam, is opgelost: geen fout, maar hij mag uit BEKEND (anders
# zou hij later stilletjes hetzelfde probleem weer toestaan).
for _i, _b in enumerate(BEKEND):
    if _i not in BEKEND_GEZIEN:
        print(f"OPGELOST? BEKEND {_b[1]} {_b[2]} {_b[3]!r} kwam in geen enkele ronde meer voor: haal hem weg  "
              f"<- {_b[5]}")

# ----------------------------------------------------------- Engels scherm, geen Nederlandse woorden (T-NL) ---
# Taalgestuurd (review R04): elke zichtbare tekst van Instellingen en Taakbeheer, in het Engels én in het
# Nederlands. Wat in beide talen precies hetzelfde is en uit meer dan één woord bestaat, is vergeten te vertalen.
# Namen en merken mogen (ZELFDE_MAG); wat andere pakketten nog vertalen, wordt gemeld (NL_BEKEND).
_talen = {}
for _taal in ("en_US.UTF-8", "nl_NL.UTF-8"):
    _talen[_taal[:2]] = {tuple(r.split(" ", 3)[1:]) for r in kind("1", "--teksten", taal=_taal)
                         if r.startswith("TEKST ") and len(r.split(" ", 3)) == 4}
klopt(len(_talen["en"]) > 300 and len(_talen["nl"]) > 300,
      f"T-NL: Instellingen en Taakbeheer gaven hun teksten in beide talen ({len(_talen['en'])}/{len(_talen['nl'])})")
_nl_tekst = {x[2] for x in _talen["nl"]}
_verdacht = []
for _app, _staat, _tekst in sorted(_talen["en"]):
    if _tekst in NL_BEKEND:
        print(f"BEKEND T-NL {_app} {_staat} {_tekst!r}  <- {NL_BEKEND[_tekst]}")
        continue
    if _tekst not in _nl_tekst or " " not in _tekst or sum(c.isalpha() for c in _tekst) < 4 \
            or _tekst.startswith("BugOS ") or any(x in _tekst for x in ZELFDE_MAG):
        continue        # één woord (een naam als 'Firefox') of een getal is vaak in beide talen hetzelfde
    _verdacht.append(f"{_app} {_staat} {_tekst!r}")
klopt(not _verdacht, "T-NL: op een Engels scherm staat niets wat in het Nederlands precies hetzelfde is (vergeten te "
                     "vertalen)" + "".join(f"\n        {x}" for x in _verdacht[:30]))
for _tekst, _reden in NL_BEKEND.items():
    if not any(x[2] == _tekst for x in _talen["en"]):   # geen fout: wel een teken dat de regel weg mag
        print(f"OPGELOST? NL_BEKEND {_tekst!r} staat niet meer op het Engelse scherm: haal hem weg  <- {_reden}")
# D08 (netwerk en printers): de namen uit de voorbeeldstand (voor foto's en tests) staan in het Engels op het Engelse
# scherm. De vergelijking hierboven slaat losse woorden ('Buren', 'Muis') en namen met een merk ('Canon PIXMA (boven)')
# over, dus hier precies: (pagina, Nederlands, Engels). Het Engels moet op zijn pagina staan (anders keek de test niet
# naar die namen), het Nederlands nergens op het Engelse scherm.
D08_VOORBEELD = [
    ("wifi", "Buren", "Neighbours"),                                    # bugos_config_netwerk.py: netwerken()
    ("wifi", "Bibliotheek gratis", "Library free Wi-Fi"),
    ("bluetooth", "Muis", "Mouse"),                                     # bugos_config_netwerk.py: bt_apparaten()
    ("bluetooth", "Telefoon", "Phone"),
    ("printers", "Canon PIXMA (boven)", "Canon PIXMA (upstairs)"),      # bugos_config_meldingen.py: printers()
    ("programmas", "Gwenview (foto's bekijken)", "Gwenview (view photos)"),   # bugos_config_meldingen.py: _VB_APPS
    ("programmas", "Elisa (muziek)", "Elisa (music)"),
    ("programmas", "Okular (documenten)", "Okular (documents)"),
    ("programmas", "Kate (tekst)", "Kate (text)"),
]
_d08 = [f"{_pagina}: {_nl!r} -> {_en!r}" for _pagina, _nl, _en in D08_VOORBEELD
        if ("settings", _pagina, _en) not in _talen["en"] or any(x[2] == _nl for x in _talen["en"])]
klopt(not _d08, "D08: wifi, bluetooth, printers en programma's tonen hun voorbeeldnamen in het Engels op een Engels "
                "scherm" + "".join(f"\n        {x}" for x in _d08))
klopt(any(x[2].startswith("Logitech mouse") for x in _talen["en"]),
      "D08: de voorbeeldmuis heet 'Logitech mouse' op het Engelse scherm")

print(f"\n{fouten} fout(en).")
sys.exit(1 if fouten else 0)
