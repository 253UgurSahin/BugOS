#!/usr/bin/env python3
"""Test van het BugOS-inlogscherm (het SDDM-thema 'bugos', fase 3 van docs/STANDALONE.md).

SDDM controleert het wachtwoord zelf (PAM); hier staat er een nep-'sddm' voor in de plaats, met dezelfde namen als in de
broncode van SDDM (GreeterApp.cpp, GreeterProxy.h, UserModel, SessionModel). Wat we nagaan:
  - de laatste gebruiker staat klaar, met zijn naam; Enter geeft naam, wachtwoord en sessie aan sddm.login;
  - fout wachtwoord: een melding, het veld leeg; Caps Lock: dat zegt het scherm ook;
  - een andere gebruiker kiezen (pijltjes), een andere sessie (de proefsessie met de nieuwe schil);
  - geen gebruikerslijst: dan typ je je inlognaam;
  - de knoppen voor slaapstand, opnieuw opstarten en uitzetten alleen als het kan, en ze werken;
  - op een tweede scherm alleen de achtergrond;
  - het thema zelf (metadata: Qt 6, Main.qml), de SDDM-instelling en het vangnet.

Met BUGOS_SHELL_FOTO=<map> ook schermafbeeldingen.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_sddm_thema.py
"""

from __future__ import annotations

import configparser
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    Property, QAbstractListModel, QModelIndex, QObject, Qt, QUrl, Signal, Slot,
)
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THEMA = ROOT / "system_files" / "usr" / "share" / "sddm" / "themes" / "bugos"
FOTO = os.environ.get("BUGOS_SHELL_FOTO", "")
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


class Lijst(QAbstractListModel):
    def __init__(self, rollen: list[str], rijen: list[dict], laatste: int):
        super().__init__()
        self.rollen = {Qt.ItemDataRole.UserRole + 1 + i: r.encode() for i, r in enumerate(rollen)}
        self.rijen = rijen
        self._laatste = laatste

    def rowCount(self, _o=QModelIndex()):  # noqa: N802
        return len(self.rijen)

    def data(self, index, rol):
        naam = self.rollen.get(rol)
        return self.rijen[index.row()].get(naam.decode()) if naam else None

    def roleNames(self):  # noqa: N802
        return self.rollen

    lastIndex = Property(int, lambda self: self._laatste, constant=True)
    count = Property(int, lambda self: len(self.rijen), constant=True)


class NepSddm(QObject):
    loginFailed = Signal()
    loginSucceeded = Signal()
    informationMessage = Signal(str)
    veranderd = Signal()

    def __init__(self, kan=True):
        super().__init__()
        self.pogingen: list[tuple[str, str, int]] = []
        self.gedaan: list[str] = []
        self._kan = kan

    canPowerOff = Property(bool, lambda self: self._kan, notify=veranderd)
    canReboot = Property(bool, lambda self: self._kan, notify=veranderd)
    canSuspend = Property(bool, lambda self: self._kan, notify=veranderd)
    hostName = Property(str, lambda self: "bugos-laptop", constant=True)

    @Slot(str, str, int)
    def login(self, naam, wachtwoord, sessie):
        self.pogingen.append((naam, wachtwoord, sessie))

    @Slot()
    def powerOff(self):  # noqa: N802
        self.gedaan.append("uit")

    @Slot()
    def reboot(self):
        self.gedaan.append("herstart")

    @Slot()
    def suspend(self):
        self.gedaan.append("slaap")


class NepToetsenbord(QObject):
    veranderd = Signal()

    def __init__(self):
        super().__init__()
        self._caps = False

    capsLock = Property(bool, lambda self: self._caps, notify=veranderd)

    def zet(self, aan):
        self._caps = aan
        self.veranderd.emit()


class NepConfig(QObject):
    background = Property(str, lambda self: str(ROOT / "system_files/usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg"),
                          constant=True)


app = QGuiApplication(sys.argv)
GEBRUIKERS = [{"name": "bugie", "realName": "Bugie Lieveheer", "icon": "", "needsPassword": True, "homeDir": "/home/bugie"},
              {"name": "jan", "realName": "Jan", "icon": "", "needsPassword": True, "homeDir": "/home/jan"}]
SESSIES = [{"name": "Plasma (Wayland)", "file": "plasma.desktop", "comment": ""},
           {"name": "BugOS (nieuwe schil, proef)", "file": "bugos-schil.desktop", "comment": ""}]


def laad(gebruikers, sessies, primair=True, kan=True):
    view = QQuickView()
    sddm, toets, conf = NepSddm(kan), NepToetsenbord(), NepConfig()
    users = Lijst(["name", "realName", "homeDir", "icon", "needsPassword"], gebruikers, 1 if len(gebruikers) > 1 else 0)
    sess = Lijst(["file", "type", "name", "exec", "comment"], sessies, 0)
    ctx = view.rootContext()
    for naam, obj in (("sddm", sddm), ("userModel", users), ("sessionModel", sess), ("keyboard", toets),
                      ("config", conf), ("primaryScreen", primair)):
        ctx.setContextProperty(naam, obj)
    view._houd = (sddm, toets, users, sess, conf)   # niet opruimen
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.resize(1280, 800)
    view.setSource(QUrl.fromLocalFile(str(THEMA / "Main.qml")))
    view.show()
    return view, sddm, toets


def wacht(ms: int = 150) -> None:
    eind = time.monotonic() + ms / 1000
    while time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.01)


view, sddm, toets = laad(GEBRUIKERS, SESSIES)
klopt(view.status() == QQuickView.Status.Ready, f"Main.qml laadt ({[e.toString() for e in view.errors()][:2]})")
if view.status() != QQuickView.Status.Ready:
    sys.exit(1)
root = view.rootObject()


def zoek(wortel, naam: str):
    """Op naam zoeken, ook tussen de onderdelen van een Repeater (die hangen alleen in de boom van zichtbare
    onderdelen, niet in die van findChild)."""
    gevonden = wortel.findChild(QObject, naam)
    if gevonden is not None:
        return gevonden
    te_doen = [wortel]
    while te_doen:
        item = te_doen.pop()
        if item.objectName() == naam:
            return item
        te_doen.extend(item.childItems())
    return None


def kind(naam: str):
    return zoek(root, naam)


wacht(300)
klopt(kind("naam").property("text") == "Jan", f"de laatste gebruiker staat klaar ({kind('naam').property('text')!r})")
if FOTO:
    Path(FOTO).mkdir(parents=True, exist_ok=True)
    view.grabWindow().scaled(960, 600).save(f"{FOTO}/inlogscherm.png")
for t in "geheim":
    QTest.keyClick(view, t)
QTest.keyClick(view, Qt.Key.Key_Return)
wacht()
klopt(sddm.pogingen == [("jan", "geheim", 0)], f"Enter: naam, wachtwoord en sessie naar sddm.login ({sddm.pogingen})")
sddm.loginFailed.emit()
wacht()
melding = kind("melding").property("text")
klopt(("klopt niet" in melding or "not right" in melding) and kind("wachtwoord").property("text") == "",
      f"fout wachtwoord: een melding en het veld leeg ({melding!r})")
toets.zet(True)
wacht()
klopt("Caps Lock" in kind("melding").property("text"), "Caps Lock aan: dat zegt het scherm ook")
toets.zet(False)

# Een andere gebruiker en een andere sessie
QTest.keyClick(view, Qt.Key.Key_Up)
wacht()
klopt(kind("naam").property("text") == "Bugie Lieveheer", "pijltje: een andere gebruiker")
klopt(kind("sessieKnop").property("visible"), "een keus van sessies: de knop staat er")
root.setProperty("sessie", 1)
wacht()
sddm.pogingen.clear()
for t in "x":
    QTest.keyClick(view, t)
QTest.keyClick(view, Qt.Key.Key_Enter)
wacht()
klopt(sddm.pogingen == [("bugie", "x", 1)], f"inloggen in de gekozen sessie (de proefsessie) ({sddm.pogingen})")

# Aan/uit
for naam in ("knop-slaap", "knop-herstart", "knop-uit"):
    klopt(kind(naam) is not None and kind(naam).property("visible"), f"{naam}: zichtbaar als het kan")
# Klikken op Opnieuw opstarten: naar sddm.reboot
knop = kind("knop-herstart")
QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                 knop.mapToScene(knop.boundingRect().center()).toPoint())
wacht()
klopt(sddm.gedaan == ["herstart"], f"Opnieuw opstarten werkt ({sddm.gedaan})")
view.close()
view2, sddm2, _ = laad(GEBRUIKERS[:1], SESSIES[:1], kan=False)
wacht(200)
r2 = view2.rootObject()
klopt(not zoek(r2, "knop-uit").property("visible") and not zoek(r2, "sessieKnop").property("visible")
      and not zoek(r2, "vorigeGebruiker").property("visible"),
      "kan niet uitzetten, één sessie, één gebruiker: die knoppen staan er niet")
view2.close()

# Geen gebruikerslijst: inlognaam typen
view3, sddm3, _ = laad([], SESSIES)
wacht(200)
r3 = view3.rootObject()
klopt(r3.findChild(QObject, "naamVeld").property("activeFocus"), "geen gebruikerslijst: eerst je inlognaam typen")
for t in "piet":
    QTest.keyClick(view3, t)
QTest.keyClick(view3, Qt.Key.Key_Return)
for t in "pw":
    QTest.keyClick(view3, t)
QTest.keyClick(view3, Qt.Key.Key_Return)
wacht()
klopt(sddm3.pogingen == [("piet", "pw", 0)], f"met een getypte naam inloggen ({sddm3.pogingen})")
view3.close()

# Tweede scherm: alleen de achtergrond
view4, _, _ = laad(GEBRUIKERS, SESSIES, primair=False)
wacht(200)
klopt(not view4.rootObject().findChild(QObject, "inlogBlok").property("visible"), "op een tweede scherm alleen de achtergrond")
view4.close()

# Het thema, de instelling en het vangnet
meta = configparser.ConfigParser()
meta.read(THEMA / "metadata.desktop")
klopt(meta["SddmGreeterTheme"].get("QtVersion") == "6" and meta["SddmGreeterTheme"].get("MainScript") == "Main.qml",
      "metadata: Qt 6 (anders start SDDM de Qt 5-versie) en Main.qml")
conf = (ROOT / "system_files/usr/lib/sddm/sddm.conf.d/50-bugos.conf").read_text()
klopt("Current=bugos" in conf and "DisplayServer=wayland" in conf, "SDDM gebruikt het thema 'bugos', op Wayland")
vangnet = (ROOT / "system_files/usr/lib/systemd/system/sddm.service.d/50-bugos-vangnet.conf").read_text()
terug = (ROOT / "system_files/usr/lib/systemd/system/bugos-inlogscherm-terug.service").read_text()
klopt("OnFailure=bugos-inlogscherm-terug.service" in vangnet and "bugos-inlogscherm plasma --nu" in terug,
      "het vangnet: start SDDM niet, dan vanzelf terug naar Plasma Login")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
os._exit(1 if fouten else 0)
