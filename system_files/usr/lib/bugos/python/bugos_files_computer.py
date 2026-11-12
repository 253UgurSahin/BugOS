"""BugOS Bestanden: de pagina 'Deze computer'.

Jip-en-Janneke: hoeveel ruimte je computer nog heeft, wat die ruimte inneemt
(Afbeeldingen, Video's, ...), een knop 'Ruimte maken', en de lijst 'Wat de meeste
ruimte inneemt' in gewone woorden (zonder Filelight van KDE). Dit is een stukje van het
venster (Bestanden in bugos_files_venster.py erft het).

  bugos-files computer:/          -> Deze computer
  bugos-files computer:/ruimte    -> Deze computer, meteen bij 'Wat de meeste ruimte inneemt' (vanuit Hulp)

Het tellen (tel_thuis) loopt in een eigen draad op de achtergrond: het venster loopt nooit vast, en het stopt zodra
je de pagina verlaat of het venster sluit (een halve telling wordt weggegooid, nooit getoond). Het telt zoals
'du -s -x': alleen wat op de schijf van je thuismap staat (geen /proc, /sys, netwerkmappen, andere schijven of de
apps en BugOS-versies van het systeem zelf, die staan buiten je thuismap), volgt geen snelkoppelingen, slaat over wat
het niet mag lezen, en telt een bestand met meer namen (hardlinks) één keer.
"""

from __future__ import annotations

import json
import os
import stat as _stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from bugos_ui import K, Knop, label, lijn, lijn_icoon, lijn_pixmap, platte_tip, px, sectie, sectie_met_knop, start, t
from bugos_desktop import app_info, mooie_naam
from bugos_drives import koppelingen, mooie_maat
from bugos_files_plekken import Afgebroken, RUIMTE_SOORTEN, eigen_ruimte, plekken, tel_map, thuis, voorbeeld_ruimte
from bugos_files_acties import prullenbak, prullenbak_inhoud
from bugos_files_onderdelen import RuimteBalk, SchijfRij, stip_icoon
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QTransform
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QMenu, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

ZICHTBAAR, HOOGSTENS = 5, 12   # zoveel regels eerst, en na 'Meer tonen'
OPNIEUW_TELLEN = 600           # seconden: zolang geldt een telling (opnieuw bij 'Zien wat ruimte inneemt' of vanuit Hulp)
MIN_GROOTTE = 100 * 10**6      # kleiner dan 100 MB: niet de moeite van een eigen regel
WINKEL = Path("/usr/share/bugos/store.json")   # de apps die de BugOS Winkel zelf laat zien


# ============================================================ ruimte tellen ===

@dataclass
class Ruimtegebruik:
    """Eén regel in 'Wat de meeste ruimte inneemt'."""
    soort: str            # map, losse, prullenbak, app, appdata, wees, apps, wine, cache, overig, systeemapp, systeem
    naam: str
    uitleg: str
    icoon: str            # een BugOS-lijnicoon
    pad: Path | None
    grootte: int
    app_id: str = ""      # bij een app: om hem in de Winkel te openen


def _uitleg(soort: str) -> str:
    """De uitleg onder een regel: wat het is, en waar je er iets aan doet."""
    return {
        "prullenbak": t("Wat je weggooide. Leegmaken geeft de ruimte terug.",
                        "What you threw away. Emptying it gives the space back."),
        "app": t("Gegevens van deze app, zoals games of downloads in de app. Ruim op in de app zelf, of verwijder de "
                 "app in de Winkel.", "Data of this app, like games or downloads inside the app. Clean up inside the "
                 "app itself, or remove the app in the Store."),
        "wees": t("Deze app is niet meer geïnstalleerd; zijn gegevens zijn achtergebleven. Klik om de map te zien.",
                  "This app is no longer installed; its data stayed behind. Click to see the folder."),
        "apps": t("Verwijder apps die je niet gebruikt in de Winkel.", "Remove apps you do not use in the Store."),
        "wine": t("Windows-programma's die je hebt geïnstalleerd, met hun bestanden.",
                  "Windows programs you installed, with their files."),
        "cache": t("Apps bewaren hier dingen om sneller te zijn. Ze maken het zelf weer aan als het nodig is.",
                   "Apps keep things here to be faster. They make it again when needed."),
        "systeemapp": t("Een app voor alle accounts op deze computer. Gebruik je hem niet? Verwijder hem in de Winkel.",
                        "An app for all accounts on this computer. Not using it? Remove it in the Store."),
        "systeem": t("BugOS zelf, apps die voor alle accounts zijn geïnstalleerd, en de bestanden van andere accounts.",
                     "BugOS itself, apps installed for all accounts, and the files of other accounts."),
    }.get(soort, "")


def bekende_data() -> dict[str, tuple[str, str, str]]:
    """Grote mappen in ~/.local/share met een gewone naam (review 3). Wat hier niet staat, telt mee bij
    'Instellingen en gegevens van apps': nooit een kale mapnaam met 'verwijder de app in de Winkel'.
    naam -> (naam, uitleg, icoon)"""
    virtueel = (t("Virtuele computers", "Virtual computers"),
                t("Computers die in een venster draaien. Verwijder wat je niet meer gebruikt in de app waarmee je ze "
                  "maakte.", "Computers that run in a window. Remove what you no longer use in the app you made them "
                  "with."), "computer")
    return {
        "containers": (t("Boxen (containers)", "Boxes (containers)"),
                       t("Programma's in een eigen box, bijvoorbeeld van Distrobox of Podman. Ruim op met het programma "
                         "waarmee je ze maakte.", "Programs in their own box, for example from Distrobox or Podman. "
                         "Clean up with the program you made them with."), "apps"),
        "baloo": (t("Zoeklijst van je bestanden", "Search index of your files"),
                  t("Hiermee vindt BugOS je bestanden snel. BugOS maakt hem vanzelf opnieuw.",
                    "With this BugOS finds your files quickly. BugOS makes it again by itself."), "zoek"),
        "Steam": ("Steam", t("Games en gegevens van Steam. Verwijder games die je niet meer speelt in Steam zelf.",
                             "Games and data of Steam. Remove games you no longer play in Steam itself."), "spel"),
        "lutris": ("Lutris", t("Games van Lutris. Verwijder games die je niet meer speelt in Lutris zelf.",
                               "Games of Lutris. Remove games you no longer play in Lutris itself."), "spel"),
        "libvirt": virtueel,
        "gnome-boxes": virtueel,
    }


def _koppelpunten() -> set[str]:
    """Waar iets aan hangt (uit /proc/self/mountinfo): een andere schijf, een netwerkmap, een container. Zo'n map
    wordt niet eens geopend: een netwerkmap die niet meer antwoordt, laat 'stat' anders hangen, en dan stopt het
    tellen nooit (review 4)."""
    return {k.plek for k in koppelingen()}


def _koppel_in(map_: Path, plekken_: set[str] | None = None) -> frozenset[str]:
    """De koppelpunten ín deze map (niet de map zelf), geschreven zoals de map zelf (/home/x of /var/home/x: op
    BugOS is /home een snelkoppeling naar /var/home)."""
    echt = os.path.realpath(map_).rstrip("/")
    eigen = str(map_).rstrip("/")
    uit = set()
    for m in (_koppelpunten() if plekken_ is None else plekken_):
        if m.startswith(echt + "/"):
            uit.add(eigen + m[len(echt):])
            uit.add(m)
    return frozenset(uit)


def _koppelpunt_van(pad: str, plekken_: set[str]) -> str:
    """Aan welk koppelpunt hangt dit pad (het langste dat ervoor past)? Alleen op tekst, zonder het pad aan te
    raken."""
    return max((m for m in plekken_ if pad == m or pad.startswith(m.rstrip("/") + "/")), key=len, default="/")


def _zelfde_koppeling(pad: Path, thuis_: Path, plekken_: set[str]) -> bool:
    """Staat 'pad' (buiten je thuismap) op hetzelfde bestandssysteem als je thuismap? Eerst op tekst: hangt hij
    aan een ander koppelpunt (een netwerkmap, een tweede schijf), dan raken we hem niet aan (een netwerkmap die
    niet antwoordt, liet anders alles hangen). Daarna pas het apparaatnummer."""
    if _koppelpunt_van(os.path.normpath(str(pad)), plekken_) != _koppelpunt_van(os.path.realpath(thuis_), plekken_):
        return False
    try:
        return _apparaat_van(pad) == _apparaat_van(thuis_)
    except OSError:
        return False


def _apparaat_van(pad: Path) -> int:
    """Op welk apparaat (schijf) staat dit? (Eigen functie, zodat een test een tweede schijf kan nadoen.)"""
    return os.stat(pad, follow_symlinks=False).st_dev


def _is_onder(kind: Path, ouder: Path) -> bool:
    try:
        kind.relative_to(ouder)
        return True
    except ValueError:
        return False


def tel_thuis(thuis_: Path | None = None, stop: threading.Event | None = None
              ) -> tuple[list[Ruimtegebruik], dict[str, int]]:
    """Alles in je thuismap, in regels (ook de kleine), en de grootte van Afbeeldingen, Video's, ... en de
    prullenbak voor de gekleurde balk: één keer tellen voor allebei (review 17).

    Samen zijn de regels precies wat 'du -s -x' over je thuismap zegt (zonder de thuismap zelf): elke map, elk
    bestand en elke snelkoppeling telt één keer, en een bestand met meer namen ook (tools/test_native_tools.py
    vergelijkt het met du). Gaat 'stop' aan, dan Afgebroken: een halve telling geeft nooit een uitslag."""
    thuis_ = thuis_ or thuis()
    gezien: set[tuple[int, int]] = set()
    rijen: list[Ruimtegebruik] = []
    try:
        apparaat = _apparaat_van(thuis_)
    except OSError:
        return [], {}
    plek_van = {p: (sl, naam, ic) for sl, naam, ic, p in plekken() if sl != "thuis"}
    bak = prullenbak()
    bekend = bekende_data()
    alle_koppels = _koppelpunten()
    koppel = _koppel_in(thuis_, alle_koppels)
    overig = losse = 0

    def gestopt() -> bool:
        return stop is not None and stop.is_set()

    def ruimte_van(p: Path, koppel_: frozenset[str] = koppel) -> int:
        """Hoeveel ruimte dit ene ding inneemt, met alles erin als het een map is (zoals du). Een koppelpunt (een
        andere schijf, een netwerkmap) of iets op een ander apparaat: 0, en niet aangeraakt. koppel_: de
        koppelpunten die eronder kunnen hangen (standaard die in je thuismap)."""
        if gestopt():
            raise Afgebroken   # meteen ophouden, ook midden in ~/.var/app of ~/.local/share
        if str(p) in koppel_:
            return 0
        try:
            st = os.stat(p, follow_symlinks=False)
            if _apparaat_van(p) != apparaat:
                return 0   # (via _apparaat_van, zodat een test een tweede schijf kan nadoen)
        except OSError:
            return 0
        if _stat.S_ISDIR(st.st_mode):
            return st.st_blocks * 512 + tel_map(p, apparaat, gezien, koppel=koppel_, stop=stop)
        if st.st_nlink > 1:
            if (st.st_dev, st.st_ino) in gezien:
                return 0   # een tweede naam van een bestand dat al geteld is
            gezien.add((st.st_dev, st.st_ino))
        return st.st_blocks * 512

    def kinderen(p: Path) -> list[Path]:
        try:
            with os.scandir(p) as inhoud:
                return sorted((Path(e.path) for e in inhoud), key=lambda x: x.name)
        except OSError:
            return []

    def map_van(p: Path) -> bool:
        """Een echte map (geen snelkoppeling, geen koppelpunt, op dit apparaat)? Alleen dan kijken we erin."""
        if str(p) in koppel:
            return False
        try:
            st = os.stat(p, follow_symlinks=False)
            return _stat.S_ISDIR(st.st_mode) and _apparaat_van(p) == apparaat
        except OSError:
            return False

    def eigen_blokje(p: Path) -> int:
        """Alleen de map zelf (zonder wat erin staat): .var, .local en .local/share tellen we per stuk."""
        try:
            st = os.stat(p, follow_symlinks=False)
            return st.st_blocks * 512 if _apparaat_van(p) == apparaat else 0
        except OSError:
            return 0

    for pad in kinderen(thuis_):
        if gestopt():
            raise Afgebroken
        naam_ = pad.name
        if str(pad) in koppel:
            continue   # een andere schijf of netwerkmap in je thuismap: niet aanraken, telt niet mee
        if not map_van(pad):
            # Een bestand of een snelkoppeling (die volgen we nooit, ook niet naar /usr): telt als zichzelf.
            if naam_.startswith("."):
                overig += ruimte_van(pad)
            else:
                losse += ruimte_van(pad)
            continue
        if naam_ == ".var":
            overig += eigen_blokje(pad)
            for kind in kinderen(pad):
                if kind.name == "app" and map_van(kind):
                    overig += eigen_blokje(kind)
                    for app in kinderen(kind):
                        info = app_info(app.name)
                        grootte = ruimte_van(app)
                        if info:
                            rijen.append(Ruimtegebruik("app", info[0], _uitleg("app"), "apps", app, grootte, app.name))
                        else:
                            rijen.append(Ruimtegebruik("wees", mooie_naam(app.name), _uitleg("wees"), "apps", app,
                                                       grootte, app.name))
                else:
                    overig += ruimte_van(kind)
        elif naam_ == ".local":
            overig += eigen_blokje(pad)
            for kind in kinderen(pad):
                if kind.name != "share" or not map_van(kind):
                    overig += ruimte_van(kind)
                    continue
                overig += eigen_blokje(kind)
                for data in kinderen(kind):
                    if data == bak and map_van(bak):
                        overig += eigen_blokje(bak)
                        rijen.append(Ruimtegebruik("prullenbak", t("Prullenbak", "Trash"), _uitleg("prullenbak"),
                                                   "prullenbak", bak, ruimte_van(bak / "files")))
                        for rest in kinderen(bak):
                            if rest.name != "files":
                                overig += ruimte_van(rest)   # de briefjes waar het vandaan kwam (info/)
                    elif data.name == "flatpak" and map_van(data):
                        rijen.append(Ruimtegebruik("apps", t("Apps die alleen voor jou zijn geïnstalleerd",
                                                             "Apps installed for you only"), _uitleg("apps"), "apps",
                                                   data, ruimte_van(data)))
                    elif data.name in bekend and map_van(data):
                        naam, uitleg, ic = bekend[data.name]
                        rijen.append(Ruimtegebruik("appdata", naam, uitleg, ic, data, ruimte_van(data)))
                    else:
                        overig += ruimte_van(data)   # ook een bestand of snelkoppeling: niets volgen
        elif naam_ == ".cache":
            rijen.append(Ruimtegebruik("cache", t("Tijdelijke bestanden", "Temporary files"), _uitleg("cache"),
                                       "klok", pad, ruimte_van(pad)))
        elif naam_ == ".wine":
            rijen.append(Ruimtegebruik("wine", t("Windows-programma's (Wine)", "Windows programs (Wine)"),
                                       _uitleg("wine"), "apps", pad / "drive_c" if map_van(pad / "drive_c") else pad,
                                       ruimte_van(pad)))
        elif naam_.startswith("."):
            overig += ruimte_van(pad)
        else:
            sl, naam, ic = plek_van.get(pad, ("", naam_, "map"))
            rijen.append(Ruimtegebruik("map", naam, "", ic, pad, ruimte_van(pad)))
    rijen.append(Ruimtegebruik("losse", t("Losse bestanden in Thuis", "Loose files in Home"), "", "document", thuis_,
                               losse))
    rijen.append(Ruimtegebruik("overig", t("Instellingen en gegevens van apps", "Settings and data of apps"), "",
                               "schakelaar", None, overig))
    if not any(r.soort == "prullenbak" for r in rijen) and not _is_onder(bak, thuis_) \
            and _zelfde_koppeling(bak, thuis_, alle_koppels):
        # De prullenbak staat buiten je thuismap (XDG_DATA_HOME), maar wel op dezelfde schijf: die telt mee. Op een
        # andere schijf of netwerkmap niet: die ruimte gaat niet van deze schijf af.
        rijen.append(Ruimtegebruik("prullenbak", t("Prullenbak", "Trash"), _uitleg("prullenbak"), "prullenbak", bak,
                                   ruimte_van(bak / "files", _koppel_in(bak, alle_koppels))))
    # Voor de balk bovenaan: Afbeeldingen, Video's ... Staat zo'n map buiten je thuismap, dan alleen als hij op
    # dezelfde schijf staat (een map op de NAS of een tweede schijf neemt hier geen ruimte in, en tellen zou over
    # het netwerk gaan).
    ruimte: dict[str, int] = {}
    per_pad = {r.pad: r.grootte for r in rijen if r.soort == "map"}
    for sl, _naam, _ic, p in plekken():
        if sl not in dict(RUIMTE_SOORTEN):
            continue
        if p in per_pad:
            ruimte[sl] = per_pad[p]
        elif not _is_onder(p, thuis_) and _zelfde_koppeling(p, thuis_, alle_koppels):
            ruimte[sl] = ruimte_van(p, _koppel_in(p, alle_koppels))
        else:
            ruimte[sl] = 0
    ruimte["prullenbak"] = next((r.grootte for r in rijen if r.soort == "prullenbak"), 0)
    if gestopt():
        raise Afgebroken
    return rijen, ruimte


def grootste_mappen(thuis_: Path | None = None, min_grootte: int = MIN_GROOTTE) -> list[Ruimtegebruik]:
    """Wat in je thuismap de meeste ruimte inneemt, het grootste eerst (alleen wat minstens min_grootte is)."""
    rijen, _ruimte = tel_thuis(thuis_)
    return sorted((r for r in rijen if r.grootte >= min_grootte and r.grootte > 0), key=lambda r: -r.grootte)


def lees_maat(tekst: str) -> int:
    """'803.9 MB' (flatpak, LC_ALL=C) -> 803900000."""
    delen = tekst.replace(",", ".").split()
    if len(delen) != 2:
        return 0
    try:
        getal = float(delen[0])
    except ValueError:
        return 0
    keer = {"bytes": 1, "b": 1, "kb": 10**3, "mb": 10**6, "gb": 10**9, "tb": 10**12}.get(delen[1].lower())
    return int(getal * keer) if keer else 0


def systeem_apps(stop: threading.Event | None = None) -> list[tuple[str, int]]:
    """(app-id, grootte) van de apps die voor alle accounts zijn geïnstalleerd (Flatpak, systeem). Die staan niet in
    je thuismap, maar nemen wel ruimte in op dezelfde schijf (review 2). Dat vraagt flatpak zelf (we tellen nooit
    in /var/lib/flatpak of de BugOS-versies in /sysroot/ostree). Hoogstens 20 seconden; gaat 'stop' aan, dan
    meteen ophouden (flatpak wordt dan gestopt)."""
    try:
        proces = subprocess.Popen(["flatpak", "list", "--app", "--system", "--columns=application,size"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                  env={**os.environ, "LC_ALL": "C"})
    except OSError:
        return []
    eind = time.monotonic() + 20
    while True:
        try:
            uit, _ = proces.communicate(timeout=0.25)
            break
        except subprocess.TimeoutExpired:
            if (stop is not None and stop.is_set()) or time.monotonic() > eind:
                proces.kill()
                proces.communicate()
                return []
    apps = []
    for regel in uit.splitlines():
        delen = regel.split("\t")
        if len(delen) >= 2 and delen[0].strip():
            apps.append((delen[0].strip(), lees_maat(delen[1])))
    return apps


def ruimte_lijst(rijen: list[Ruimtegebruik], gebruikt: int, apps: list[tuple[str, int]],
                 min_grootte: int = MIN_GROOTTE) -> list[Ruimtegebruik]:
    """De regels om te tonen: wat in je thuismap groot is, grote apps voor iedereen, en de rest van wat er op de
    schijf in gebruik is ('BugOS en apps voor iedereen'), zodat het samen klopt met de balk bovenaan (review 2)."""
    lijst = [r for r in rijen if r.grootte >= min_grootte and r.grootte > 0]
    eigen = sum(r.grootte for r in rijen)
    for app_id, grootte in apps:
        if grootte >= min_grootte:
            info = app_info(app_id)
            lijst.append(Ruimtegebruik("systeemapp", info[0] if info else mooie_naam(app_id), _uitleg("systeemapp"),
                                       "apps", None, grootte, app_id))
    rest = gebruikt - eigen - sum(r.grootte for r in lijst if r.soort == "systeemapp")
    if rest >= min_grootte:
        lijst.append(Ruimtegebruik("systeem", t("BugOS en apps voor iedereen", "BugOS and apps for everyone"),
                                   _uitleg("systeem"), "computer", None, rest))
    return sorted(lijst, key=lambda r: -r.grootte)


def voorbeeld_grootste(nep: list[int]) -> tuple[list[Ruimtegebruik], dict[str, int], list[tuple[str, int]]]:
    """Voor foto's (BUGOS_RUIMTE): vaste regels in plaats van tellen."""
    gb = 10**9
    paden = {sl: (naam, ic, p) for sl, naam, ic, p in plekken()}
    rijen = [Ruimtegebruik("app", "Steam", _uitleg("app"), "apps", None, 182 * gb, "com.valvesoftware.Steam")]
    for sl, waarde in (("videos", nep[3]), ("afbeeldingen", nep[2]), ("downloads", nep[6]), ("muziek", nep[5]),
                       ("documenten", nep[4])):
        naam, ic, p = paden[sl]
        rijen.append(Ruimtegebruik("map", naam, "", ic, p, waarde))
    rijen += [
        Ruimtegebruik("cache", t("Tijdelijke bestanden", "Temporary files"), _uitleg("cache"), "klok", None,
                      int(4.1 * gb)),
        Ruimtegebruik("app", "Firefox", _uitleg("app"), "apps", None, int(2.3 * gb), "org.mozilla.firefox"),
        Ruimtegebruik("overig", t("Instellingen en gegevens van apps", "Settings and data of apps"), "", "schakelaar",
                      None, int(1.2 * gb)),
        Ruimtegebruik("prullenbak", t("Prullenbak", "Trash"), _uitleg("prullenbak"), "prullenbak", prullenbak(),
                      int(0.8 * gb)),
    ]
    ruimte = dict(zip([sl for sl, _k in RUIMTE_SOORTEN], nep[2:]))
    ruimte["prullenbak"] = int(0.8 * gb)
    return rijen, ruimte, [("org.libreoffice.LibreOffice", int(0.8 * gb))]


def in_winkel(app_id: str) -> bool:
    """Staat deze app in de BugOS Winkel? Een app die er niet in staat, opent bugos-store in Discover van KDE: dan
    openen we liever de Winkel zelf (daar staan ook je geïnstalleerde apps)."""
    try:
        apps = json.loads(WINKEL.read_text(encoding="utf-8"))["apps"]
        return any(str(a.get("id", "")).lower() == app_id.lower() for a in apps)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


class Grootsein(QObject):
    """Brengt de uitslag van een telling naar het venster (de hoofddraad): (teller, uitslag)."""
    klaar = Signal(object)


FOUT = "fout"   # de uitslag van een telling die misging (dan geen lijst, wel een zin)


class GrootsteTeller(threading.Thread):
    """Telt op de achtergrond wat de meeste ruimte inneemt (in een grote thuismap duurt dat even).

    Een eigen draad, niet de gedeelde QThreadPool: zo kan hij met een lagere voorrang draaien (de rest van de
    computer merkt er niets van), houdt hij de voorbeeldjes van Bestanden niet op, en hoeft niemand op hem te wachten
    als het venster dichtgaat (daemon). Elke telling heeft een eigen 'stop': de pagina verlaten stopt alleen deze.
    De uitslag is (rijen, ruimte, apps), None als hij gestopt is, of FOUT."""

    def __init__(self, sein: Grootsein, thuis_: Path | None = None):
        super().__init__(name="bugos-ruimte-tellen", daemon=True)
        self.sein, self.thuis = sein, thuis_
        self.stop = threading.Event()

    def run(self) -> None:
        try:
            # Alleen deze draad zachter (op Linux geldt een nice-waarde per draad).
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 10)
        except (AttributeError, OSError):
            pass
        try:
            rijen, ruimte = tel_thuis(self.thuis, stop=self.stop)
            apps = systeem_apps(stop=self.stop)
            if self.stop.is_set():
                raise Afgebroken
            uitslag = (rijen, ruimte, apps)
        except Afgebroken:
            uitslag = None
        except Exception:  # noqa: BLE001  tellen mag het venster nooit laten vallen
            uitslag = FOUT
        try:
            self.sein.klaar.emit((self, uitslag))
        except RuntimeError:  # het venster is al dicht
            pass


# ================================================================== legenda ===

class Legenda(QWidget):
    """De legenda onder de balk (Afbeeldingen 38 GB, Video's 52 GB, ...): drie naast elkaar, of twee of één als dat
    niet past (150 %, grote letters). Anders schoof de hele pagina opzij."""

    def __init__(self):
        super().__init__()
        self.rooster = QGridLayout(self)
        self.rooster.setContentsMargins(0, 0, 0, 0)
        self.rooster.setHorizontalSpacing(4)
        self.rooster.setVerticalSpacing(0)
        self.rooster.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)   # de breedte bepaalt dit vlak zelf
        self.items: list[QWidget] = []
        self.kolommen = 0

    def zet(self, items: list[QWidget]) -> None:
        for w in self.items:
            self.rooster.removeWidget(w)
            w.deleteLater()
        self.items = list(items)
        self.kolommen = 0
        self.deel_in()

    def hoogstens(self) -> int:
        return 3 if len(self.items) > 4 else max(len(self.items), 1)

    def nodig(self, n: int) -> int:
        breed = [w.sizeHint().width() for w in self.items]
        kolommen = [max(breed[k::n], default=0) for k in range(n)]
        return sum(kolommen) + (n - 1) * self.rooster.horizontalSpacing()

    def deel_in(self) -> None:
        breedte = self.width() if self.width() > 1 else 10**6
        n = next((k for k in range(self.hoogstens(), 0, -1) if self.nodig(k) <= breedte), 1)
        if n == self.kolommen:
            return
        for w in self.items:
            self.rooster.removeWidget(w)
        for i, w in enumerate(self.items):
            self.rooster.addWidget(w, i // n, i % n)
        self.kolommen = n
        self.updateGeometry()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.nodig(1), self.rooster.minimumSize().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.nodig(self.kolommen or 1), self.rooster.sizeHint().height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self.deel_in()


# ================================================================ één regel ===

class RuimteRij(QFrame):
    """Eén regel: icoontje, naam (met uitleg), een dun balkje en de grootte. Een map of app open je met een klik
    (of Enter); wat je hier niet kunt openen, reageert ook niet op de muis."""

    geklikt = Signal()

    def __init__(self, r: Ruimtegebruik, grootste: int, klikbaar: bool):
        super().__init__()
        self.gebruik = r
        self.setObjectName("schijfrij")     # dezelfde look als de schijven eronder (bugos_files_onderdelen.stijl)
        self.setMinimumHeight(56)
        if klikbaar:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setProperty("knop_voor_schermlezer", True)
        else:
            self.setProperty("leeg", "true")   # geen oplichten onder de muis: er valt niets te klikken
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(r.naam)
        self.setAccessibleDescription(r.uitleg)
        if r.uitleg:
            self.setToolTip(platte_tip(r.uitleg))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(lijn_icoon(r.icoon, "tekst2", 22, gekozen=None).pixmap(22, 22))
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop if r.uitleg else Qt.AlignmentFlag.AlignVCenter)
        blok = QVBoxLayout()
        blok.setSpacing(1)
        blok.addWidget(label(r.naam, "rij", wrap=False))
        if r.uitleg:
            blok.addWidget(label(r.uitleg, "klein"))
        lay.addLayout(blok, 1)
        balk = QProgressBar()
        balk.setObjectName("dun")
        balk.setTextVisible(False)
        balk.setRange(0, 1000)
        balk.setValue(int(1000 * r.grootte / grootste) if grootste else 0)
        balk.setProperty("vol", "false")
        balk.setFixedWidth(110)   # zoals bij de schijven eronder
        lay.addWidget(balk, 0, Qt.AlignmentFlag.AlignVCenter)
        maat = label(mooie_maat(r.grootte), "rij", wrap=False)
        maat.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        maat.setFixedWidth(px(84))
        lay.addWidget(maat)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.focusPolicy() != Qt.FocusPolicy.NoFocus \
                and self.rect().contains(e.position().toPoint()):
            self.geklikt.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and \
                self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            self.geklikt.emit()
            return
        super().keyPressEvent(e)


# ================================================================== de pagina ===

class Computer:
    """De pagina 'Deze computer': een stukje van het venster Bestanden."""

    # De pagina staat open of niet. Een eigenschap (geen gewone waarde): elke weg weg van deze pagina (een map
    # openen, de prullenbak, terug, het venster sluiten) zet in_computer op False, en dan stopt hier het tellen.
    # Zo telt er nooit iets door voor een pagina die niemand meer ziet.
    @property
    def in_computer(self) -> bool:
        return getattr(self, "_in_computer", False)

    @in_computer.setter
    def in_computer(self, aan: bool) -> None:
        was = getattr(self, "_in_computer", False)
        self._in_computer = bool(aan)
        if was and not aan:
            self.stop_tellen()

    def stop_tellen(self) -> None:
        """Stop de telling die nu loopt (pagina verlaten, venster dicht). Wat hij al had, wordt weggegooid: de
        vorige uitslag (als die er was) blijft staan, en de volgende keer op deze pagina telt hij opnieuw."""
        teller = getattr(self, "grootste_teller", None)
        if teller is not None:
            teller.stop.set()
        self.grootste_teller = None
        if getattr(self, "grootste_bezig", False):
            self.grootste_bezig = False
            self.tellen_bezig = False

    def open_computer(self, geschiedenis: bool = True) -> None:
        """De pagina 'Deze computer': al je schijven, en hoeveel ruimte er nog is (zoals 'Deze pc' in Windows)."""
        if geschiedenis and not self.in_computer:
            self.terug_lijst.append(self.plek_nu())
            self.vooruit_lijst.clear()
        if self.lijst.selectionModel() is not None:
            self.lijst.selectionModel().clear()
        self.in_computer, self.in_prullenbak = True, False
        self.vul_computer()
        self.bouw_pad()
        self.markeer_zijbalk()
        self.ververs_staat()

    def vul_computer(self) -> None:
        """Bovenaan: hoeveel ruimte je computer nog heeft. Dan wat de meeste ruimte inneemt. Daaronder: USB-sticks
        en andere schijven."""
        lay = self.computer_lay
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()

        # --- de computer zelf: groot getal, balk, en wat de ruimte inneemt
        totaal, vrij = eigen_ruimte()
        nep = voorbeeld_ruimte()
        if nep and getattr(self, "grootste", None) is None:
            rijen, ruimte, apps = voorbeeld_grootste(nep)
            self.grootste, self.grootste_tijd = (rijen, apps), time.monotonic()
            self.ruimte, self.ruimte_tijd = ruimte, time.monotonic()
        kaart = QFrame()
        kaart.setObjectName("kaart")
        binnen = QVBoxLayout(kaart)
        binnen.setContentsMargins(26, 22, 26, 20)
        binnen.setSpacing(0)
        regel = QHBoxLayout()
        regel.setSpacing(12)
        regel.addWidget(label(t(f"{mooie_maat(vrij)} vrij", f"{mooie_maat(vrij)} free"), "groot", wrap=False),
                        0, Qt.AlignmentFlag.AlignBottom)
        van = label(t(f"van de {mooie_maat(totaal)}", f"of {mooie_maat(totaal)}"), "sub", wrap=False)
        van.setContentsMargins(0, 0, 0, 9)
        regel.addWidget(van, 0, Qt.AlignmentFlag.AlignBottom)
        regel.addStretch(1)
        ruimte_knop = Knop(t("Ruimte maken", "Free up space"), "gewoon")
        ruimte_knop.setMinimumHeight(38)
        ruimte_knop.clicked.connect(lambda _c=False, k=ruimte_knop: self.ruimte_menu().exec(
            k.mapToGlobal(k.rect().bottomLeft())))
        regel.addWidget(ruimte_knop, 0, Qt.AlignmentFlag.AlignTop)
        binnen.addLayout(regel)
        binnen.addSpacing(14)
        self.ruimte_balk = RuimteBalk()
        binnen.addWidget(self.ruimte_balk)
        binnen.addSpacing(8)
        self.legenda = Legenda()
        binnen.addWidget(self.legenda)
        lay.addWidget(kaart)
        self.ruimte_totaal, self.ruimte_vrij = totaal, vrij
        self.toon_ruimte()

        # --- wat de meeste ruimte inneemt (één telling voor deze lijst én de balk hierboven)
        lay.addSpacing(10)
        apps_knop = Knop(t("Apps verwijderen die je niet gebruikt", "Remove apps you do not use"), "stil")
        apps_knop.setToolTip(t("Opent de Winkel, waar je apps verwijdert", "Opens the Store, where you remove apps"))
        apps_knop.clicked.connect(lambda _c=False: start("bugos-store"))
        self.grootste_kop = sectie_met_knop(t("Wat de meeste ruimte inneemt", "What takes up the most space"),
                                            apps_knop)
        lay.addWidget(self.grootste_kop)
        self.grootste_kaart = QFrame()
        self.grootste_kaart.setObjectName("kaart")
        self.grootste_lay = QVBoxLayout(self.grootste_kaart)
        self.grootste_lay.setContentsMargins(6, 6, 6, 6)
        self.grootste_lay.setSpacing(2)
        lay.addWidget(self.grootste_kaart)
        self.meer_knop = Knop("", "stil", "lijn:onder")
        self.meer_knop.clicked.connect(self.wissel_meer)
        self.meer_knop.hide()
        lay.addWidget(self.meer_knop, 0, Qt.AlignmentFlag.AlignLeft)
        link = "computer:/ruimte" in sys.argv[1:] and not getattr(self, "_ruimte_link", False)
        if link:
            self._ruimte_link = True   # alleen de eerste keer (vanuit Hulp): daarna is het gewoon Deze computer
        self.tel_grootste(opnieuw=link)
        self.vul_grootste()
        if link:
            QTimer.singleShot(0, self.naar_grootste)

        # --- USB-sticks en schijven: een gewone lijst
        lay.addSpacing(10)
        lay.addWidget(sectie(t("USB-sticks en schijven", "USB sticks and drives")))
        lijst_kaart = QFrame()
        lijst_kaart.setObjectName("kaart")
        rijen = QVBoxLayout(lijst_kaart)
        rijen.setContentsMargins(6, 6, 6, 6)
        rijen.setSpacing(2)
        for i, x in enumerate(self.lijst_schijven):
            if i:
                streep = lijn()
                streep.setContentsMargins(50, 0, 10, 0)
                rijen.addWidget(streep)
            rijen.addWidget(self.schijf_rij(x))
        if not self.lijst_schijven:
            tip = t("Steek een USB-stick in, dan staat hij hier.", "Plug in a USB stick and it shows up here.")
            leeg = SchijfRij("usb", t("Nog niets aangesloten", "Nothing plugged in yet"), tip, leeg=True)
            for uitleg in leeg.findChildren(QLabel):
                if uitleg.text() == tip:   # met grote letters liever twee regels dan een pagina die opzij schuift
                    uitleg.setWordWrap(True)
                    uitleg.setMinimumWidth(px(160))
                    uitleg.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rijen.addWidget(leeg)
        lay.addWidget(lijst_kaart)
        lay.addStretch(1)

    # ------------------------------------------------- wat de meeste ruimte inneemt
    def tel_grootste(self, opnieuw: bool = False) -> None:
        """Tellen op de achtergrond, als de laatste telling ouder is dan 10 minuten (of als je erom vraagt). Alleen
        zolang de pagina openstaat (zie in_computer)."""
        if getattr(self, "grootste_bezig", False) or not self.in_computer:
            return
        oud = time.monotonic() - getattr(self, "grootste_tijd", -1e9) > OPNIEUW_TELLEN
        if voorbeeld_ruimte() or not (opnieuw or oud or getattr(self, "grootste", None) is None):
            return
        if getattr(self, "grootsein", None) is None:
            self.grootsein = Grootsein(self)
            self.grootsein.klaar.connect(self._grootste_geteld)
        self.grootste_bezig = True
        self.tellen_bezig = True     # (de balk bovenaan komt uit dezelfde telling)
        self.grootste_fout = False
        self.grootste_teller = GrootsteTeller(self.grootsein)
        self.grootste_teller.start()

    def _grootste_geteld(self, bericht) -> None:
        """De uitslag van een telling (in de hoofddraad). Alleen die van de telling die nu loopt telt: een gestopte
        telling (je verliet de pagina) is al vergeten."""
        teller, uitslag = bericht
        if teller is not getattr(self, "grootste_teller", None):
            return
        self.grootste_teller = None
        self.grootste_bezig = False
        if uitslag is None or uitslag == FOUT:
            # Gestopt of misgegaan: niets onthouden (geen half of leeg lijstje dat tien minuten blijft staan).
            self.tellen_bezig = False
            self.grootste_fout = uitslag == FOUT
            if self.in_computer and getattr(self, "grootste_lay", None) is not None:
                try:
                    self.vul_grootste()
                except RuntimeError:
                    pass
            return
        rijen, ruimte, apps = uitslag
        self.grootste, self.grootste_tijd = (rijen, apps), time.monotonic()
        if ruimte:
            self._geteld(ruimte)
        else:
            self.tellen_bezig = False
        if self.in_computer and getattr(self, "grootste_lay", None) is not None:
            try:
                self.vul_grootste()
            except RuntimeError:   # de pagina werd intussen opnieuw opgebouwd
                pass

    def vul_grootste(self) -> None:
        lay = self.grootste_lay
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.ruimte_rijen: list[RuimteRij] = []
        gegevens = getattr(self, "grootste", None)
        if gegevens is None:
            if getattr(self, "grootste_fout", False) and not getattr(self, "grootste_bezig", False):
                tekst = t("Tellen lukte niet. Probeer het later nog eens: Ruimte maken > Zien wat ruimte inneemt.",
                          "Counting did not work. Try again later: Free up space > See what takes up space.")
            else:
                tekst = t("Bezig met tellen… Dit duurt soms een minuutje.", "Counting… This sometimes takes a minute.")
            bezig = label(tekst, "klein")
            bezig.setContentsMargins(14, 12, 14, 12)
            lay.addWidget(bezig)
            self.meer_knop.hide()
            return
        rijen, apps = gegevens
        gebruikt = max(self.ruimte_totaal - self.ruimte_vrij, 0)
        lijst = ruimte_lijst(rijen, gebruikt, apps)
        eigen_groot = [r for r in lijst if r.soort not in ("systeem", "systeemapp")]
        if not eigen_groot:
            # Niets groots in je eigen mappen: zeg waar de ruimte dan wel zit (geen doodlopende weg, review 2).
            niets = label(t("Er staat niets groots in je eigen mappen. De ruimte gaat naar BugOS en de apps zelf: "
                            "verwijder apps die je niet gebruikt in de Winkel.",
                            "There is nothing big in your own folders. The space goes to BugOS and the apps "
                            "themselves: remove apps you do not use in the Store."), "klein")
            niets.setContentsMargins(14, 12, 14, 12)
            lay.addWidget(niets)
        alles = getattr(self, "grootste_alles", False)
        toon = lijst[:HOOGSTENS if alles else ZICHTBAAR]
        grootste = max((r.grootte for r in lijst), default=0)
        for i, r in enumerate(toon):
            if i or not eigen_groot:
                streep = lijn()
                streep.setContentsMargins(50, 0, 10, 0)
                lay.addWidget(streep)
            klikbaar = r.soort in ("map", "losse", "prullenbak", "app", "wees", "apps", "wine", "systeemapp",
                                   "systeem")
            rij = RuimteRij(r, grootste, klikbaar)
            rij.geklikt.connect(lambda r=r: self.open_ruimte(r))
            lay.addWidget(rij)
            self.ruimte_rijen.append(rij)
        meer = min(len(lijst), HOOGSTENS) - ZICHTBAAR
        if meer > 0:
            self.meer_knop.setText(t("Minder tonen", "Show less") if alles
                                   else t("Meer tonen", "Show more") + f" ({meer})")
            pijl = lijn_pixmap("onder", "tekst2", 36)
            self.meer_knop.setIcon(QIcon(pijl.transformed(QTransform().rotate(180)) if alles else pijl))
            self.meer_knop.show()
        else:
            self.meer_knop.hide()

    def wissel_meer(self) -> None:
        self.grootste_alles = not getattr(self, "grootste_alles", False)
        self.vul_grootste()

    def naar_grootste(self) -> None:
        """Vanuit Hulp ('Laat zien wat ruimte inneemt'): meteen naar de lijst schuiven (op 1280x800 bij 150 %
        staat hij anders onder de rand, review 9)."""
        kop = getattr(self, "grootste_kop", None)
        if kop is not None:
            try:
                self.computer.ensureWidgetVisible(kop, 0, 40)
                self.computer.verticalScrollBar().setValue(max(kop.y() - 8, 0))
            except RuntimeError:
                pass

    def open_ruimte(self, r: Ruimtegebruik) -> None:
        """Waar je iets aan een regel doet: de map openen, de prullenbak, of de app in de Winkel."""
        if r.soort == "prullenbak":
            self.open_prullenbak()
        elif r.soort in ("app", "systeemapp", "apps", "systeem"):
            if r.app_id and in_winkel(r.app_id):
                start("bugos-store", f"appstream://{r.app_id}")
            else:
                start("bugos-store")   # nooit Discover van KDE
        elif r.pad is not None and r.pad.is_dir():
            self.ga_naar(r.pad)

    def ruimte_menu(self) -> QMenu:
        """Ruimte maken: de prullenbak leegmaken, of zien wat ruimte inneemt."""
        m = QMenu(self)
        zien = m.addAction(lijn_icoon("zoek", "tekst", 18, gekozen=None),
                           t("Zien wat ruimte inneemt", "See what takes up space"))
        zien.triggered.connect(lambda _c=False: (self.tel_grootste(opnieuw=True), self.naar_grootste()))
        m.addSeparator()
        bak = (self.ruimte or {}).get("prullenbak")
        tekst = t(f"Prullenbak leegmaken ({mooie_maat(bak)})", f"Empty the trash ({mooie_maat(bak)})") if bak else \
            t("Prullenbak leegmaken", "Empty the trash")
        a = m.addAction(lijn_icoon("prullenbak", "tekst", 18, gekozen=None), tekst)
        a.triggered.connect(lambda _c=False: self.leegmaken())
        a.setEnabled(bool(prullenbak_inhoud()))
        return m

    def toon_ruimte(self) -> None:
        """Kleur de balk: Afbeeldingen, Video's, ... en de rest (BugOS en apps). Wat over is, is vrij."""
        totaal, vrij = self.ruimte_totaal, self.ruimte_vrij
        if totaal <= 0:
            return
        gebruikt = max(totaal - vrij, 0)
        namen = {sl: (naam, pad) for sl, naam, _i, pad in plekken()}
        delen: list[tuple[float, QColor]] = []
        items: list[tuple[QColor, str, Path | None]] = []
        if self.ruimte:
            som = sum(v for k, v in self.ruimte.items() if k in dict(RUIMTE_SOORTEN))
            schaal = min(1.0, gebruikt / som) if som else 1.0
            for sl, kl in RUIMTE_SOORTEN:
                grootte = self.ruimte.get(sl, 0) * schaal
                if grootte < max(totaal * 0.002, 50 * 10**6):
                    continue  # te klein om te zien: telt mee bij de rest
                kleur_ = QColor(K["accent"] if kl == "accent" else kl)
                delen.append((grootte / totaal, kleur_))
                items.append((kleur_, f"{namen[sl][0]}  {mooie_maat(grootte)}", namen[sl][1]))
            rest = max(gebruikt - sum(d * totaal for d, _k in delen), 0)
            grijs = QColor(K["tekst3"])
            delen.append((rest / totaal, grijs))
            items.append((grijs, t(f"BugOS en apps  {mooie_maat(rest)}", f"BugOS and apps  {mooie_maat(rest)}"), None))
        else:
            grijs = QColor(K["tekst3"])
            delen.append((gebruikt / totaal, grijs))
            items.append((grijs, t(f"In gebruik  {mooie_maat(gebruikt)}  (bezig met tellen…)",
                                   f"In use  {mooie_maat(gebruikt)}  (counting…)"), None))
        self.ruimte_balk.zet(delen)
        knoppen = []
        for kleur_, tekst, pad in items:
            k = QPushButton(tekst.replace("&", "&&"))   # (U210)
            k.setObjectName("legenda")
            k.setIcon(stip_icoon(kleur_, hol=pad == "vrij"))
            k.setIconSize(QSize(12, 12))
            if isinstance(pad, Path):
                k.setCursor(Qt.CursorShape.PointingHandCursor)
                k.setToolTip(platte_tip(t(f"Open {pad.name}", f"Open {pad.name}")))
                k.clicked.connect(lambda _c=False, d=pad: self.ga_naar(d))
            else:
                k.setEnabled(False)
            knoppen.append(k)
        self.legenda.zet(knoppen)

    def _geteld(self, uitslag: dict) -> None:
        self.tellen_bezig = False
        self.ruimte, self.ruimte_tijd = uitslag, time.monotonic()
        if self.in_computer:
            try:
                self.toon_ruimte()
            except RuntimeError:   # de pagina werd intussen opnieuw opgebouwd
                pass
