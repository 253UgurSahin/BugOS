#!/usr/bin/env python3
"""Test van de eigen BugOS-schil (bugos-shell, docs/STANDALONE.md fase 1): de QML met nep-onderdelen.

bugos-shell (C++) geeft de QML drie dingen: opdracht (programma's uitvoeren), schil (layer-shell en de Meta-toets) en
meldingen (de meldingendienst). Hier staan daar Python-nepversies voor in de plaats, zodat de QML zonder KWin en
zonder D-Bus te testen is. Wat we nagaan:
  - de taakbalk staat er meteen, de menu's pas als je erom vraagt;
  - Start (en de Meta-toets) opent het startmenu en haalt de gegevens op; nog een keer sluit het;
  - wat het startmenu en het snelmenu vragen, gaat als losse argumenten naar bugos-start-data (nooit via een shell);
  - meldingen: een kaartje verschijnt, het kruisje en de knoppen gaan naar de meldingendienst;
  - de klok, de kalender, en een klik naast een menu sluit het;
  - het startmenu biedt in de schil geen 'Vastmaken aan taakbalk' (komt in fase 2);
  - de bestanden voor de sessie (bugos-shell.desktop, de proefsessie, de keuze tussen schil en Plasma).

Met BUGOS_SHELL_FOTO=<map> bewaart de test ook schermafbeeldingen van de taakbalk en de menu's.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_shell.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"

from PySide6.QtCore import (  # noqa: E402
    Q_ARG, Property, QAbstractListModel, QMetaObject, QModelIndex, QObject, Qt, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QColor, QGuiApplication, QPixmap  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickImageProvider  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "system_files" / "usr" / "share" / "bugos" / "shell"
TMP = Path(tempfile.mkdtemp(prefix="bugos-shell-"))
(TMP / "config" / "bugos").mkdir(parents=True)
(TMP / "config" / "bugos" / "browser").write_text("com.google.Chrome\n")
BUREAUBLAD = TMP / "Bureaublad"
BUREAUBLAD.mkdir()
(BUREAUBLAD / "Boodschappen.txt").write_text("melk")
(BUREAUBLAD / "Setup.exe").write_text("MZ")
(BUREAUBLAD / "Foto's").mkdir()
os.environ["XDG_CONFIG_HOME"] = str(TMP / "config")
FOTO = os.environ.get("BUGOS_SHELL_FOTO", "")

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


GEGEVENS = {
    "apps": [{"id": "org.mozilla.firefox.desktop", "pad": "/usr/share/applications/org.mozilla.firefox.desktop",
              "naam": "Firefox", "uitleg": "Browser", "icoon": "firefox", "groep": "Internet", "zoek": "firefox",
              "soort": "app", "acties": [], "verwijder": "org.mozilla.firefox", "quarantaine": True}],
    "favorieten": [{"id": "org.mozilla.firefox.desktop", "pad": "/usr/share/applications/org.mozilla.firefox.desktop",
                    "naam": "Firefox", "uitleg": "Browser", "icoon": "firefox", "groep": "Internet", "zoek": "firefox",
                    "soort": "app", "acties": [], "verwijder": "org.mozilla.firefox", "quarantaine": True,
                    "vastgezet": True}],
    "recent": [], "gebruiker": {"naam": "Bugie"}, "taakbalk_kan": True,
}
SNEL = {"wifi": True, "wifi_naam": "Thuis", "bluetooth": False, "volume": 40, "stil": False, "niet_storen": False}


class NepOpdracht(QObject):
    klaar = Signal(str, int, str)

    def __init__(self):
        super().__init__()
        self.uitgevoerd: list[tuple[list, str]] = []
        self.gestart: list[list] = []

    @Slot("QVariantList", str)
    def voerUit(self, argv, sleutel):  # noqa: N802
        argv = [str(a) for a in argv]
        self.uitgevoerd.append((argv, sleutel))
        if sleutel == "gegevens":
            QTimer.singleShot(0, lambda: self.klaar.emit(sleutel, 0, json.dumps(GEGEVENS)))
        elif sleutel == "snel":
            QTimer.singleShot(0, lambda: self.klaar.emit(sleutel, 0, json.dumps(SNEL)))

    @Slot("QVariantList", result=bool)
    def start(self, argv):
        self.gestart.append([str(a) for a in argv])
        return True


class NepSchil(QObject):
    startmenu = Signal()
    bureaublad = Signal(bool)

    def __init__(self):
        super().__init__()
        self.lagen: list[tuple[str, int]] = []
        self.plekken: list[tuple[int, int]] = []
        self.bureaublad_getoond: list[bool] = []

    @Slot(QObject, str, int, result=bool)
    def laag(self, _venster, soort, marge):
        self.lagen.append((soort, marge))
        return False

    @Slot(result=bool)
    def heeftLagen(self):  # noqa: N802
        return False

    @Slot(QObject, int, int, result=bool)
    def plaats(self, _venster, x, y):
        self.plekken.append((int(x), int(y)))
        return False

    @Slot(bool)
    def bureaubladTonen(self, tonen):  # noqa: N802
        self.bureaublad_getoond.append(bool(tonen))


class NepMeldingen(QObject):
    lijstVeranderd = Signal()

    def __init__(self):
        super().__init__()
        self._lijst: list = []
        self.gesloten: list[int] = []
        self.acties: list[tuple[int, str]] = []

    def _lees(self):
        return self._lijst

    lijst = Property("QVariantList", _lees, notify=lijstVeranderd)

    def zet(self, lijst):
        self._lijst = lijst
        self.lijstVeranderd.emit()

    geschiedenisVeranderd = Signal()
    _geschiedenis: list = []
    _ongelezen = 0
    geschiedenis = Property("QVariantList", lambda self: self._geschiedenis, notify=geschiedenisVeranderd)
    ongelezen = Property(int, lambda self: self._ongelezen, notify=geschiedenisVeranderd)

    def zet_geschiedenis(self, lijst, ongelezen):
        self._geschiedenis, self._ongelezen = lijst, ongelezen
        self.geschiedenisVeranderd.emit()

    @Slot()
    def allesGelezen(self):  # noqa: N802
        self.zet_geschiedenis(self._geschiedenis, 0)

    @Slot()
    def wisGeschiedenis(self):  # noqa: N802
        self.zet_geschiedenis([], 0)

    @Slot(int)
    def uitGeschiedenis(self, id_):  # noqa: N802
        self.zet_geschiedenis([m for m in self._geschiedenis if m["id"] != id_], self._ongelezen)

    @Slot(int, str)
    def actieUitGeschiedenis(self, id_, sleutel):  # noqa: N802
        self.acties.append((int(id_), sleutel))
        self.uitGeschiedenis(id_)

    @Slot(int)
    def sluit(self, id_):
        self.gesloten.append(int(id_))
        self.zet([m for m in self._lijst if m["id"] != id_])

    @Slot(int, str)
    def actie(self, id_, sleutel):
        self.acties.append((int(id_), sleutel))
        self.zet([m for m in self._lijst if m["id"] != id_])


class NepInstellingen(QObject):
    veranderd = Signal(str)

    def __init__(self, map_: Path, bureaublad: Path):
        super().__init__()
        self.map = map_
        self._bureaublad = str(bureaublad)

    def _bb(self):
        return self._bureaublad

    bureaubladMap = Property(str, _bb, constant=True)

    @Slot(str, result=str)
    def lees(self, naam):
        try:
            return (self.map / naam).read_text()
        except OSError:
            return ""

    @Slot(str, str, result=bool)
    def bewaar(self, naam, tekst):
        (self.map / naam).write_text(tekst)
        return True

    @Slot(bool, result=str)
    def achtergrondBeeld(self, donker):  # noqa: N802
        gekozen = self.lees("achtergrond").strip()
        if gekozen and Path(gekozen).is_file():
            return gekozen
        pakket = ROOT / "system_files/usr/share/wallpapers/bugos/contents"
        return str(pakket / ("images_dark" if donker else "images") / "3840x2160.jpg")


class NepSysteemvak(QAbstractListModel):
    ROLLEN = {Qt.ItemDataRole.UserRole + 1: b"titel", Qt.ItemDataRole.UserRole + 2: b"icoon",
              Qt.ItemDataRole.UserRole + 3: b"status", Qt.ItemDataRole.UserRole + 4: b"uitleg",
              Qt.ItemDataRole.UserRole + 5: b"heeftMenu", Qt.ItemDataRole.UserRole + 6: b"alleenMenu",
              Qt.ItemDataRole.UserRole + 7: b"sleutel"}

    def __init__(self):
        super().__init__()
        self.items = [{"titel": "Steam", "icoon": "image://icon/steam", "status": "Active", "uitleg": "Steam",
                       "heeftMenu": True, "alleenMenu": False, "sleutel": "a"},
                      {"titel": "Stil", "icoon": "image://icon/x", "status": "Passive", "uitleg": "",
                       "heeftMenu": False, "alleenMenu": False, "sleutel": "b"}]
        self.geactiveerd: list[int] = []
        self.geklikt: list[tuple[int, int]] = []

    def rowCount(self, _ouder=QModelIndex()):  # noqa: N802
        return len(self.items)

    def data(self, index, rol):
        naam = self.ROLLEN.get(rol)
        return self.items[index.row()].get(naam.decode()) if naam else None

    def roleNames(self):  # noqa: N802
        return self.ROLLEN

    @Slot(int, int, int, result=bool)
    def activeer(self, rij, _x, _y):
        self.geactiveerd.append(rij)
        return True

    @Slot(int, int, int)
    def secundair(self, *_a):
        pass

    @Slot(int, int)
    def scroll(self, *_a):
        pass

    @Slot(int, result="QVariantList")
    def menu(self, rij):
        if rij != 0:
            return []
        return [{"id": 1, "tekst": "Openen", "aan": True, "scheiding": False, "kinderen": []},
                {"id": 0, "tekst": "", "aan": True, "scheiding": True, "kinderen": []},
                {"id": 9, "tekst": "Stoppen", "aan": True, "scheiding": False, "kinderen": []}]

    @Slot(int, int, int)
    def contextMenu(self, *_a):  # noqa: N802
        pass

    @Slot(int, int)
    def menuKlik(self, rij, id_):  # noqa: N802
        self.geklikt.append((rij, id_))


class NepOsd(QObject):
    getoond = Signal()

    def __init__(self):
        super().__init__()
        self._icoon, self._tekst, self._waarde, self._maximum = "", "", -1, 100

    icoon = Property(str, lambda self: self._icoon, notify=getoond)
    tekst = Property(str, lambda self: self._tekst, notify=getoond)
    waarde = Property(int, lambda self: self._waarde, notify=getoond)
    maximum = Property(int, lambda self: self._maximum, notify=getoond)

    def toon(self, icoon, tekst, waarde):
        self._icoon, self._tekst, self._waarde = icoon, tekst, waarde
        self.getoond.emit()


class NepPictogram(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, _id, maat, gevraagd):  # noqa: N802
        pm = QPixmap(max(16, gevraagd.width()), max(16, gevraagd.height()))
        pm.fill(QColor("#DE2F3E"))
        return pm


app = QGuiApplication(sys.argv)
opdracht, schil, meldingen = NepOpdracht(), NepSchil(), NepMeldingen()
instellingen, systeemvak = NepInstellingen(TMP / "config" / "bugos", BUREAUBLAD), NepSysteemvak()
osd = NepOsd()
engine = QQmlApplicationEngine()
engine.addImageProvider("icon", NepPictogram())
ctx = engine.rootContext()
ctx.setContextProperty("opdracht", opdracht)
ctx.setContextProperty("schil", schil)
ctx.setContextProperty("meldingen", meldingen)
ctx.setContextProperty("instellingen", instellingen)
ctx.setContextProperty("systeemvak", systeemvak)
ctx.setContextProperty("osd", osd)
fout_meldingen: list[str] = []
engine.warnings.connect(lambda ws: fout_meldingen.extend(w.toString() for w in ws))
engine.load(QUrl.fromLocalFile(str(SHELL / "Shell.qml")))
klopt(bool(engine.rootObjects()), f"Shell.qml laadt ({fout_meldingen[:3]})")
if not engine.rootObjects():
    sys.exit(1)
root = engine.rootObjects()[0]


def wacht(ms: int = 100) -> None:
    import time
    eind = time.monotonic() + ms / 1000
    while time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.01)


def waarde(naam: str):
    """Een eigenschap van de QML als gewone Python-waarde (een lijst of object komt als QJSValue)."""
    w = root.property(naam)
    return w.toVariant() if hasattr(w, "toVariant") else w


def kind(naam: str):
    return root.findChild(QObject, naam)


wacht(300)
ernstig = [w for w in fout_meldingen if "Takenlijst.qml" not in w and "image://" not in w]
klopt(not ernstig, f"geen QML-fouten (behalve de takenlijst zonder KDE hier) ({ernstig[:3]})")
def venster(naam: str):
    """Een venster van de schil op naam (objectName), ook die van een Instantiator (per scherm)."""
    for w in app.topLevelWindows():
        if w.objectName() == naam:
            return w
    return kind(naam)


paneel = venster("paneel")
start_v, snel_v, kal_v, meld_v = (venster(n) for n in ("startVenster", "snelVenster", "kalenderVenster",
                                                         "meldingVenster"))
klopt(paneel is not None and paneel.isVisible() and not start_v.isVisible() and not snel_v.isVisible()
      and not meld_v.isVisible(), "de taakbalk staat er meteen; de menu's en meldingen nog niet "
      f"({[w.isVisible() for w in (paneel, start_v, snel_v, kal_v, meld_v)]})")
klopt(("paneel", 0) in schil.lagen and ("links", 8) in schil.lagen and ("melding", 12) in schil.lagen
      and ("achtergrond", 0) in schil.lagen and ("vangnet", 0) in schil.lagen,
      f"elk venster vraagt zijn plek met layer-shell ({sorted(set(s for s, _ in schil.lagen))})")
klopt(paneel.height() == 48, f"de taakbalk is 48 px hoog, zoals Windows 11 ({paneel.height()})")
klopt(waarde("launchers")[1] == "applications:com.google.Chrome.desktop",
      f"de takenlijst heeft de browser die je in Welkom koos ({waarde('launchers')})")
klopt(opdracht.uitgevoerd and opdracht.uitgevoerd[0] == (["bugos-start-data"], "gegevens"),
      "bij het starten: de gegevens van het startmenu ophalen")

# Start: de Meta-toets (KWin -> org.kde.plasmashell activateLauncherMenu -> schil.startmenu)
opdracht.uitgevoerd.clear()
schil.startmenu.emit()
wacht()
klopt(start_v.isVisible() and paneel.findChild(QObject, "startKnop") is not None, "de Meta-toets opent het startmenu")
klopt((["bugos-start-data"], "gegevens") in opdracht.uitgevoerd, "het startmenu haalt bij het openen de gegevens opnieuw op")
gegevens = waarde("gegevens")
klopt(gegevens.get("gebruiker", {}).get("naam") == "Bugie" and gegevens.get("taakbalk_kan") is True
      and gegevens["apps"][0].get("op_taakbalk") is False,
      "de gegevens komen aan; 'Vastmaken aan taakbalk' kan (de schil weet zelf wat er vastzit)")
if FOTO:
    Path(FOTO).mkdir(parents=True, exist_ok=True)
    start_v.grabWindow().save(f"{FOTO}/startmenu.png")
schil.startmenu.emit()
wacht()
klopt(not start_v.isVisible(), "nog een keer de Meta-toets: het startmenu gaat dicht")

# Wat het startmenu vraagt, als losse argumenten (een naam met ' of ; wordt nooit een opdracht)
root.setProperty("open", "start")
wacht()
startmenu = None
for o in start_v.contentItem().childItems():
    if o.property("gegevens") is not None:
        startmenu = o
klopt(startmenu is not None, "het startmenu (StartMenu.qml) staat in zijn venster")
opdracht.uitgevoerd.clear()
lastig = "/tmp/a'; rm -rf ~; echo '.desktop"
startmenu.start.emit(lastig)
wacht()
klopt((["bugos-start-data", "--start", lastig], "") in opdracht.uitgevoerd and not start_v.isVisible(),
      f"een app starten: het pad als één argument, en het menu gaat dicht ({opdracht.uitgevoerd})")
root.setProperty("open", "start")
wacht()
opdracht.uitgevoerd.clear()
startmenu.quarantaine.emit("/usr/share/applications/x.desktop")
startmenu.aanUit.emit("herstarten")
wacht()
klopt((["bugos-start-data", "--quarantaine", "/usr/share/applications/x.desktop"], "") in opdracht.uitgevoerd
      and (["bugos-start-data", "--aan-uit", "herstarten"], "") in opdracht.uitgevoerd,
      "quarantaine en aan/uit gaan naar bugos-start-data")

# Snelmenu
root.setProperty("open", "")
QMetaObject.invokeMethod(root, "toon", Q_ARG("QVariant", "snel"), Q_ARG("QVariant", None))
wacht()
klopt(snel_v.isVisible() and not start_v.isVisible(), "het snelmenu gaat open (en het startmenu niet)")
klopt(waarde("snelStatus").get("wifi_naam") == "Thuis", "het snelmenu krijgt de status")
snel = snel_v.contentItem().childItems()[0]
opdracht.uitgevoerd.clear()
snel.zet.emit("donker", "aan")
snel.open.emit("instellingen")
wacht()
klopt((["bugos-start-data", "--zet", "donker", "aan"], "snel") in opdracht.uitgevoerd
      and (["bugos-start-data", "--start", "instelling:start"], "") in opdracht.uitgevoerd,
      f"snelmenu: zetten en Instellingen openen ({opdracht.uitgevoerd})")
klopt(not snel_v.isVisible(), "na 'Instellingen openen' gaat het snelmenu dicht")

# Kalender, en een klik naast het menu sluit het
QMetaObject.invokeMethod(root, "toon", Q_ARG("QVariant", "kalender"), Q_ARG("QVariant", None))
wacht()
vangnet = venster("vangnet")
klopt(kal_v.isVisible() and vangnet is not None, "de klok opent de kalender, met het vangnet eronder")
if FOTO:
    kal_v.grabWindow().save(f"{FOTO}/kalender.png")
QMetaObject.invokeMethod(root, "sluitAlles")
wacht()
klopt(not kal_v.isVisible() and not vangnet.isVisible(), "sluiten: de kalender en het vangnet zijn weg")

# Meldingen
meldingen.zet([{"id": 7, "app": "BugOS", "icoon": "bugos-logo", "kop": "Firefox is klaar",
                "tekst": "Je vindt hem in het <b>startmenu</b>.", "knoppen": [{"sleutel": "open", "tekst": "Openen"}],
                "standaard": True, "dringend": False}])
wacht(200)
klopt(meld_v.isVisible() and meld_v.height() > 60, f"een melding: het kaartje verschijnt ({meld_v.height()} px)")
if FOTO:
    paneel.grabWindow().save(f"{FOTO}/taakbalk.png")
    meld_v.grabWindow().save(f"{FOTO}/melding.png")
kaart = meld_v.contentItem().childItems()[0].childItems()[0]
kaart.actie.emit("open")
wacht()
klopt(meldingen.acties == [(7, "open")] and not meld_v.isVisible(), "een knop op de melding gaat naar de app; het kaartje is weg")
meldingen.zet([{"id": 8, "app": "", "icoon": "", "kop": "Hallo", "tekst": "", "knoppen": [], "standaard": False,
                "dringend": False}])
wacht(100)
meld_v.contentItem().childItems()[0].childItems()[0].dicht.emit()
wacht()
klopt(meldingen.gesloten == [8], "het kruisje sluit de melding")

# ===================================================================================================== fase 2 ===
def roep(obj, naam, *args):
    return QMetaObject.invokeMethod(obj, naam, *[Q_ARG("QVariant", a) for a in args])


klopt(root.property("aantalPanelen") == len(app.screens()) and root.property("aantalBureaubladen") == len(app.screens()),
      f"per scherm een taakbalk en een bureaublad ({len(app.screens())} scherm(en))")

# Vastmaken aan de taakbalk vanuit het startmenu: de schil bewaart het zelf (~/.config/bugos/taakbalk).
root.setProperty("open", "start")
wacht()
startmenu.taakbalk.emit("org.mozilla.firefox.desktop", True)
wacht()
bewaard = json.loads((TMP / "config" / "bugos" / "taakbalk").read_text())
klopt(bewaard[-1] == "applications:org.mozilla.firefox.desktop" and waarde("launchers") == bewaard
      and waarde("gegevens")["apps"][0]["op_taakbalk"] is True,
      f"vastmaken aan de taakbalk: bewaard, in de takenlijst, en het startmenu weet het ({bewaard})")
startmenu.taakbalk.emit("org.mozilla.firefox.desktop", False)
wacht()
klopt("applications:org.mozilla.firefox.desktop" not in json.loads((TMP / "config" / "bugos" / "taakbalk").read_text()),
      "losmaken van de taakbalk")
# Een ander programma verandert de lijst (of iemand met de hand): alleen echte starters tellen.
(TMP / "config" / "bugos" / "taakbalk").write_text(json.dumps(
    ["applications:bugos-files.desktop", "applications:../../etc/passwd", "rm -rf ~", 7]))
instellingen.veranderd.emit("taakbalk")
wacht()
klopt(waarde("launchers") == ["applications:bugos-files.desktop"], f"een vreemde regel in de lijst telt niet ({waarde('launchers')})")
(TMP / "config" / "bugos" / "taakbalk").write_text("geen json")
instellingen.veranderd.emit("taakbalk")
wacht()
klopt(len(waarde("launchers")) == 4, "een kapot bestand: de standaardlijst (Bestanden, browser, Winkel, Instellingen)")

# Je eigen achtergrond (Instellingen > Uiterlijk schrijft ~/.config/bugos/achtergrond)
foto = TMP / "vakantie.jpg"
foto.write_bytes((ROOT / "system_files/usr/share/wallpapers/bugos/contents/images/3840x2160.jpg").read_bytes())
(TMP / "config" / "bugos" / "achtergrond").write_text(str(foto) + "\n")
instellingen.veranderd.emit("achtergrond")
wacht()
klopt(root.property("achtergrondBeeld") == str(foto), "je eigen achtergrond: de schil wisselt meteen mee")

# Het systeemvak
klopt(roep(root, "vakMenu", None, 900, 0), "het systeemvak: menu opvragen")
wacht()
los = venster("losMenu")
regels = los.property("platteRegels").toVariant()
klopt(los.isVisible() and [r["tekst"] for r in regels] == ["Openen", "", "Stoppen"],
      f"rechtermuisknop op een app in het systeemvak: zijn eigen menu ({[r['tekst'] for r in regels]})")
klopt(schil.plekken and schil.plekken[-1][1] + los.height() <= (app.screens()[0].size().height() - 48),
      f"het menu staat boven de taakbalk ({schil.plekken[-1:]}, {los.height()} px hoog)")
if FOTO:
    los.grabWindow().save(f"{FOTO}/vakmenu.png")
roep(los, "kies", 2)
wacht()
klopt(systeemvak.geklikt == [(0, 9)] and not los.isVisible(), "een keuze in het menu gaat naar de app; het menu gaat dicht")

# Rechtermuisknop op Start: de snelle lijst (Win+X)
roep(root, "startKnopMenu", None, 8)
wacht()
teksten = [r.get("tekst", "") for r in los.property("platteRegels").toVariant()]
klopt(los.isVisible() and teksten[0] in ("Taakbeheer", "Task Manager") and len(teksten) == 10,
      f"rechtermuisknop op Start: Taakbeheer, ... en aan/uit ({teksten})")
opdracht.uitgevoerd.clear()
roep(los, "kies", 8)
wacht()
klopt((["bugos-start-data", "--aan-uit", "herstarten"], "") in opdracht.uitgevoerd, "Win+X: Opnieuw opstarten")

# Het bureaublad: je bestanden als pictogrammen, met een menu
bb = venster("bureaublad")
pictogrammen = bb.findChild(QObject, "bureaubladPictogrammen") if bb is not None else None
import time as _t  # noqa: E402
_eind = _t.monotonic() + 3
while pictogrammen is not None and pictogrammen.property("count") < 3 and _t.monotonic() < _eind:
    wacht(50)
klopt(pictogrammen is not None and pictogrammen.property("count") == 3,
      f"het bureaublad toont de bestanden uit je bureaubladmap ({pictogrammen.property('count') if pictogrammen else None})")
if FOTO and bb is not None:
    bb.grabWindow().scaled(960, 600).save(f"{FOTO}/bureaublad.png")
exe = str(BUREAUBLAD / "Setup.exe")
roep(root, "bureaubladMenu", None, 300, 200, exe)
wacht()
teksten = [r.get("tekst", "") for r in los.property("platteRegels").toVariant()]
klopt(any(t in ("Openen in quarantaine", "Open in quarantine") for t in teksten),
      f"rechtermuisknop op een programma op het bureaublad: 'Openen in quarantaine' ({teksten})")
opdracht.gestart.clear()
roep(los, "kies", 1)
wacht()
klopt(opdracht.gestart == [["bugos-quarantaine", "--venster", exe]], f"quarantaine vanaf het bureaublad ({opdracht.gestart})")
roep(root, "bureaubladMenu", None, 300, 200, str(BUREAUBLAD / "Boodschappen.txt"))
wacht()
teksten = [r.get("tekst", "") for r in los.property("platteRegels").toVariant()]
klopt(not any("quarantaine" in t or "quarantine" in t for t in teksten), "bij een document geen quarantaine")
roep(los, "sluit")
opdracht.uitgevoerd.clear()
roep(root, "openBestand", "/home/x/Bureaublad/Steam.desktop")
roep(root, "openBestand", "/home/x/Bureaublad/brief.odt")
wacht()
klopt((["bugos-start-data", "--start", "/home/x/Bureaublad/Steam.desktop"], "") in opdracht.uitgevoerd
      and (["bugos-start-data", "--open", "/home/x/Bureaublad/brief.odt"], "") in opdracht.uitgevoerd,
      "dubbelklik: een starter start de app, een bestand opent")
roep(root, "bureaubladWissel")
klopt(schil.bureaublad_getoond == [True], "Bureaublad tonen (het strookje rechts)")
klopt(paneel is not None and paneel.findChild(QObject, "systeemvak") is not None, "de taakbalk van het hoofdscherm heeft het systeemvak")

# ===================================================================================================== fase 3 ===
# De bel en het meldingencentrum
bel = paneel.findChild(QObject, "belKnop")
meldingen.zet_geschiedenis([
    {"id": 21, "app": "Steam", "icoon": "steam", "kop": "Update klaar", "tekst": "", "knoppen": [{"sleutel": "open", "tekst": "Openen"}],
     "standaard": False, "dringend": False, "tijd": "09:12"},
    {"id": 20, "app": "BugOS", "icoon": "bugos-logo", "kop": "Firefox is klaar", "tekst": "", "knoppen": [],
     "standaard": False, "dringend": False, "tijd": "09:10"}], 2)
wacht()
klopt(bel is not None and bel.property("visible") and "2" in bel.property("naam"),
      f"de bel op de taakbalk telt de nieuwe meldingen ({bel.property('naam') if bel else None})")
centrum = venster("meldingenCentrum")
QMetaObject.invokeMethod(root, "toon", Q_ARG("QVariant", "meldingen"), Q_ARG("QVariant", None))
wacht(200)
klopt(centrum.isVisible() and meldingen.property("ongelezen") == 0, "de bel opent het meldingencentrum; alles is gezien")
lijst = centrum.findChild(QObject, "centrumLijst")
klopt(lijst is not None and lijst.property("count") == 2, f"het meldingencentrum toont de bewaarde meldingen ({lijst.property('count') if lijst else None})")
if FOTO:
    centrum.grabWindow().save(f"{FOTO}/meldingencentrum.png")
meldingen.acties.clear()
eerste = lijst.property("contentItem").childItems()[0]
eerste.actie.emit("open")
wacht()
klopt(meldingen.acties == [(21, "open")] and len(meldingen.property("geschiedenis")) == 1,
      "een knop op een oude melding gaat naar de app, en de melding gaat uit het centrum")
opdracht.uitgevoerd.clear()
centrum.findChild(QObject, "nietStorenKnop").geklikt.emit()
wacht()
klopt((["bugos-start-data", "--zet", "niet_storen", "aan"], "snel") in opdracht.uitgevoerd, "niet storen aanzetten vanuit het centrum")
centrum.findChild(QObject, "allesWissen").geklikt.emit()
wacht()
klopt(len(meldingen.property("geschiedenis")) == 0, "Alles wissen")
QMetaObject.invokeMethod(root, "sluitAlles")

# De schermmelding bij de volumetoetsen (OSD)
osd_v = venster("osdVenster")
klopt(not osd_v.isVisible(), "de schermmelding is er niet vanzelf")
osd.toon("audio-volume-medium", "", 40)
wacht(100)
balk = osd_v.findChild(QObject, "osdBalk")
klopt(osd_v.isVisible() and balk.property("visible"), "volumetoets: de schermmelding met een balk")
if FOTO:
    osd_v.grabWindow().save(f"{FOTO}/osd.png")
osd.toon("audio-volume-muted", "Geluid uit", -1)
wacht(100)
klopt(osd_v.isVisible() and not balk.property("visible"), "geluid uit: alleen tekst")
wacht(2000)
klopt(not osd_v.isVisible(), "na een paar tellen gaat de schermmelding weg")
klopt(("osd", 96) in schil.lagen, f"de schermmelding staat onderaan, boven de taakbalk ({[l for l in schil.lagen if l[0] == 'osd']})")

# De bestanden voor de sessie
bureaublad = (ROOT / "system_files/usr/share/applications/bugos-shell.desktop").read_text()
klopt("Exec=/usr/bin/bugos-shell" in bureaublad and "org_kde_plasma_window_management" in bureaublad
      and "NoDisplay=true" in bureaublad, "bugos-shell.desktop: KWin geeft de schil de vensterlijst")
sessie = (ROOT / "system_files/usr/share/wayland-sessions/bugos-klassiek.desktop").read_text()
klopt("Exec=/usr/bin/bugos-sessie klassiek" in sessie, "fase 4: 'BugOS klassiek (Plasma)' staat op het inlogscherm als terugweg")
keuze = (ROOT / "system_files/usr/libexec/bugos-schil-of-plasma").read_text()
klopt("BUGOS_SCHIL" in keuze and 'exec "$SHELL_BIN"' in keuze and 'exec "$PLASMA_BIN"' in keuze,
      "de dienst van de schil kiest: bugos-shell (standaard), anders het klassieke Plasma")
dropin = (ROOT / "system_files/usr/lib/systemd/user/plasma-plasmashell.service.d/50-bugos-schil.conf").read_text()
klopt("ExecStart=\n" in dropin and "ExecStart=/usr/libexec/bugos-schil-of-plasma" in dropin,
      "plasma-plasmashell.service start de keuze in plaats van plasmashell")
# 2026-11 (gebruiker: "taakbalk cleaner, professioneler, instelbaar"): rechts één knop met de icoontjes van internet,
# geluid en batterij (het snelmenu); de grootte en de plek van Start en je apps zijn in te stellen.
klopt(any(a[:2] == ["bugos-start-data", "--tray"] and k == "tray" for a, k in opdracht.uitgevoerd),
      "de taakbalk vraagt bij het begin de status voor de icoontjes rechts (bugos-start-data --tray)")
root.setProperty("trayStatus", {"internet": "wifi", "wifi": True, "volume": 60, "stil": False, "batterij": 76, "laadt": True})
wacht(100)
snelk = paneel.findChild(QObject, "snelKnop")
klopt(snelk.property("internetIcoon") == "network-wireless" and snelk.property("geluidIcoon") == "audio-volume-medium"
      and snelk.property("batterijIcoon") == "battery-080-charging"
      and any(w in snelk.property("naam") for w in ("internet via wifi", "internet over Wi-Fi"))
      and any(w in snelk.property("naam") for w in ("batterij 76%", "battery 76%")),
      f"snelmenu-knop: wifi, geluid en batterij als icoontjes, en voor een schermlezer in woorden ({snelk.property('naam')})")
root.setProperty("trayStatus", {"internet": "geen", "wifi": False, "volume": 30, "stil": True, "batterij": None})
wacht(50)
klopt(snelk.property("internetIcoon") == "network-offline" and snelk.property("geluidIcoon") == "audio-volume-muted"
      and snelk.property("batterijIcoon") == "", "snelmenu-knop: geen internet, geluid uit, geen batterij (een pc)")
stijl = TMP / "config" / "bugos" / "taakbalkstijl"
stijl.write_text(json.dumps({"grootte": "klein", "uitlijning": "midden"}))
instellingen.veranderd.emit("taakbalkstijl")
wacht(400)
links = paneel.findChild(QObject, "links")
midden_x = (paneel.width() - links.property("width")) / 2
klopt(paneel.height() == 40 and abs(links.property("x") - midden_x) <= 1,
      f"taakbalk: klein (40 px) en Start met je apps in het midden ({paneel.height()}, x {links.property('x')} ~ {midden_x:.0f})")
stijl.write_text(json.dumps({"grootte": "groot", "uitlijning": "links"}))
instellingen.veranderd.emit("taakbalkstijl")
wacht(400)
klopt(paneel.height() == 56 and links.property("x") == 8, f"taakbalk: groot (56 px) en weer links ({paneel.height()})")
stijl.write_text("kapot{")
instellingen.veranderd.emit("taakbalkstijl")
wacht(400)
klopt(paneel.height() == 48 and links.property("x") == 8, "taakbalk: een kapotte instelling = gewoon (48 px, links)")
klopt("setExclusiveZone(h)" in (ROOT / "shell/src/schil.cpp").read_text(),
      "taakbalk: een andere grootte laat vensters ook meteen zoveel ruimte vrij (layer-shell)")

# Drie taakbalken op elkaar en een Windows-toets die niets deed (2026-11): één schil tegelijk, een taakbalk per
# (ongespiegeld) scherm en vast aan dat scherm, geen Plasma ernaast, en de naam org.kde.plasmashell opnieuw proberen.
hoofd_cpp = (ROOT / "shell/src/main.cpp").read_text()
schil_cpp = (ROOT / "shell/src/schil.cpp").read_text()
shell_qml = (ROOT / "system_files/usr/share/bugos/shell/Shell.qml").read_text()
klopt("QLockFile" in hoofd_cpp and "setStaleLockTime(0)" in hoofd_cpp and "tryLock(0)" in hoofd_cpp,
      "één schil tegelijk (een slot in XDG_RUNTIME_DIR; een tweede start stopt meteen)")
klopt(shell_qml.count("model: root.schermen") == 2 and "u.virtualX === s.virtualX" in shell_qml,
      "een taakbalk en bureaublad per scherm; gespiegelde schermen (zelfde plek) maar één keer")
klopt("l->setScreen(venster->screen())" in schil_cpp and "BUGOS_LAYERSHELL_SCHERM" in schil_cpp,
      "de taakbalk zit vast aan zijn eigen scherm (layer-shell 6.6+)")
klopt("pkill -u" in keuze and "plasmashell" in keuze, "in de nieuwe schil draait er geen Plasma ernaast")
klopt("registerService" in schil_cpp and "QTimer" in schil_cpp and "activateLauncherMenu" in schil_cpp,
      "Windows-toets: de naam org.kde.plasmashell wordt opnieuw geprobeerd als hij nog bezet is")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
# Meteen stoppen: anders ruimt Python de nep-onderdelen op terwijl de QML er nog naar kijkt (alleen ruis in het log).
os._exit(1 if fouten else 0)
