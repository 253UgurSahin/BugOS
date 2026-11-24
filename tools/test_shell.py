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

from PySide6.QtCore import Q_ARG, Property, QMetaObject, QObject, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QPixmap  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickImageProvider  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "system_files" / "usr" / "share" / "bugos" / "shell"
TMP = Path(tempfile.mkdtemp(prefix="bugos-shell-"))
(TMP / "config" / "bugos").mkdir(parents=True)
(TMP / "config" / "bugos" / "browser").write_text("com.google.Chrome\n")
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

    @Slot(QObject, str, int, result=bool)
    def laag(self, _venster, soort, marge):
        self.lagen.append((soort, marge))
        return False

    @Slot(result=bool)
    def heeftLagen(self):  # noqa: N802
        return False


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

    @Slot(int)
    def sluit(self, id_):
        self.gesloten.append(int(id_))
        self.zet([m for m in self._lijst if m["id"] != id_])

    @Slot(int, str)
    def actie(self, id_, sleutel):
        self.acties.append((int(id_), sleutel))
        self.zet([m for m in self._lijst if m["id"] != id_])


class NepPictogram(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, _id, maat, gevraagd):  # noqa: N802
        pm = QPixmap(max(16, gevraagd.width()), max(16, gevraagd.height()))
        pm.fill(QColor("#DE2F3E"))
        return pm


app = QGuiApplication(sys.argv)
opdracht, schil, meldingen = NepOpdracht(), NepSchil(), NepMeldingen()
engine = QQmlApplicationEngine()
engine.addImageProvider("icon", NepPictogram())
ctx = engine.rootContext()
ctx.setContextProperty("opdracht", opdracht)
ctx.setContextProperty("schil", schil)
ctx.setContextProperty("meldingen", meldingen)
ctx.setContextProperty("achtergrondMap", str(ROOT / "system_files/usr/share/wallpapers/bugos/contents"))
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
paneel, start_v, snel_v, kal_v, meld_v = (kind(n) for n in ("paneel", "startVenster", "snelVenster", "kalenderVenster",
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
klopt(start_v.isVisible() and kind("startKnop") is not None, "de Meta-toets opent het startmenu")
klopt((["bugos-start-data"], "gegevens") in opdracht.uitgevoerd, "het startmenu haalt bij het openen de gegevens opnieuw op")
gegevens = waarde("gegevens")
klopt(gegevens.get("gebruiker", {}).get("naam") == "Bugie" and gegevens.get("taakbalk_kan") is False,
      "de gegevens komen aan; 'Vastmaken aan taakbalk' staat in de schil (nog) uit")
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
QMetaObject.invokeMethod(root, "toon", Q_ARG("QVariant", "snel"))
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
QMetaObject.invokeMethod(root, "toon", Q_ARG("QVariant", "kalender"))
wacht()
vangnet = None
for w in app.topLevelWindows():
    if w.isVisible() and w is not paneel and w is not kal_v and w.width() == paneel.width() and w.height() > 200 \
            and w.color().alpha() < 10:
        vangnet = w
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

# De bestanden voor de sessie
bureaublad = (ROOT / "system_files/usr/share/applications/bugos-shell.desktop").read_text()
klopt("Exec=/usr/bin/bugos-shell" in bureaublad and "org_kde_plasma_window_management" in bureaublad
      and "NoDisplay=true" in bureaublad, "bugos-shell.desktop: KWin geeft de schil de vensterlijst")
sessie = (ROOT / "system_files/usr/share/wayland-sessions/bugos-schil.desktop").read_text()
klopt("Exec=/usr/bin/bugos-sessie" in sessie, "de proefsessie 'BugOS (nieuwe schil, proef)' staat op het inlogscherm")
keuze = (ROOT / "system_files/usr/libexec/bugos-schil-of-plasma").read_text()
klopt("BUGOS_SCHIL" in keuze and "exec /usr/bin/bugos-shell" in keuze and "exec /usr/bin/plasmashell" in keuze,
      "de dienst van de schil kiest: bugos-shell in de proefsessie, anders gewoon Plasma")
dropin = (ROOT / "system_files/usr/lib/systemd/user/plasma-plasmashell.service.d/50-bugos-schil.conf").read_text()
klopt("ExecStart=\n" in dropin and "ExecStart=/usr/libexec/bugos-schil-of-plasma" in dropin,
      "plasma-plasmashell.service start de keuze in plaats van plasmashell")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
# Meteen stoppen: anders ruimt Python de nep-onderdelen op terwijl de QML er nog naar kijkt (alleen ruis in het log).
os._exit(1 if fouten else 0)
