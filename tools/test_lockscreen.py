#!/usr/bin/env python3
"""Test van het BugOS-vergrendelscherm (shell-pakket org.bugos.schil, fase 3 van docs/STANDALONE.md).

Het scherm draait echt in kscreenlocker_greet van KDE; die controleert het wachtwoord (PAM). Hier staat er een
nep-'authenticator' voor in de plaats, met dezelfde namen als in kscreenlocker Plasma/6.5 (pamauthenticators.h):
startAuthenticating(), respond(), succeeded(), failed(soort), hadPrompt, infoMessage, errorMessage, prompt.
Wat we nagaan:
  - eerst alleen de klok; een toets toont het wachtwoordveld (en die eerste letter telt mee);
  - Enter geeft het wachtwoord aan de authenticator; fout: een melding, het veld leeg, even wachten, opnieuw;
  - goed: Qt.quit() (zo ontgrendelt kscreenlocker); zonder wachtwoord (vingerafdruk): eerst een knop;
  - Escape verbergt het veld weer en wist wat je typte;
  - de namen die kscreenlocker op het scherm zoekt (locked, viewVisible, suspendToRam ...) bestaan;
  - slaapstand alleen als het kan; het pakket zelf (metadata) klopt.

Met BUGOS_SHELL_FOTO=<map> ook schermafbeeldingen.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_lockscreen.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Property, QByteArray, QObject, Qt, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAKKET = ROOT / "system_files" / "usr" / "share" / "plasma" / "shells" / "org.bugos.schil"
FOTO = os.environ.get("BUGOS_SHELL_FOTO", "")
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


class NepAuthenticator(QObject):
    succeeded = Signal()
    failed = Signal(int, QObject)
    infoMessageChanged = Signal()
    errorMessageChanged = Signal()
    promptChanged = Signal()
    promptForSecretChanged = Signal()
    hadPromptChanged = Signal()

    def __init__(self):
        super().__init__()
        self.gestart = 0
        self.antwoorden: list[str] = []
        self._had_prompt = True
        self._info = ""

    @Slot()
    def startAuthenticating(self):  # noqa: N802
        self.gestart += 1

    @Slot(QByteArray)
    def respond(self, antwoord):
        tekst = bytes(antwoord).decode()
        self.antwoorden.append(tekst)
        if tekst == "goed":
            self.succeeded.emit()
        else:
            self.failed.emit(0, None)

    def _hp(self):
        return self._had_prompt

    hadPrompt = Property(bool, _hp, notify=hadPromptChanged)

    def _im(self):
        return self._info

    infoMessage = Property(str, _im, notify=infoMessageChanged)
    errorMessage = Property(str, lambda self: "", notify=errorMessageChanged)
    prompt = Property(str, lambda self: "", notify=promptChanged)
    busy = Property(bool, lambda self: False, constant=True)


app = QGuiApplication(sys.argv)
gestopt: list[bool] = []
auth = NepAuthenticator()
view = QQuickView()
view.engine().quit.connect(lambda: gestopt.append(True))
ctx = view.rootContext()
ctx.setContextProperty("authenticator", auth)
ctx.setContextProperty("kscreenlocker_userName", "bugie")
ctx.setContextProperty("kscreenlocker_userImage", "")
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.resize(1280, 800)
fouten_qml: list[str] = []
view.engine().warnings.connect(lambda ws: fouten_qml.extend(w.toString() for w in ws))
view.setSource(QUrl.fromLocalFile(str(PAKKET / "contents" / "lockscreen" / "LockScreen.qml")))
klopt(view.status() == QQuickView.Status.Ready, f"LockScreen.qml laadt ({[e.toString() for e in view.errors()][:2]})")
if view.status() != QQuickView.Status.Ready:
    sys.exit(1)
view.show()
root = view.rootObject()


def wacht(ms: int = 100) -> None:
    eind = time.monotonic() + ms / 1000
    while time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.01)


def kind(naam: str):
    return root.findChild(QObject, naam)


wacht(400)
ernstig = [f for f in fouten_qml if "3840x2160.jpg" not in f]
klopt(not ernstig, f"geen QML-fouten ({ernstig[:2]})")
mo = root.metaObject()
namen = [mo.property(i).name() for i in range(mo.propertyCount())]
seinen = [bytes(mo.method(i).methodSignature()).decode() for i in range(mo.methodCount())]
klopt(all(n in namen for n in ("locked", "viewVisible", "suspendToRamSupported", "suspendToDiskSupported"))
      and "suspendToRam()" in seinen and "suspendToDisk()" in seinen,
      "de namen die kscreenlocker op het scherm zoekt, bestaan (locked, viewVisible, suspendToRam ...)")
klopt(auth.gestart == 1, "bij het openen: de authenticator begint (ook voor een vingerafdruk)")
klopt(kind("grooteKlok").property("visible") and not kind("invoerBlok").property("visible"),
      "eerst alleen de klok, zoals Windows")
if FOTO:
    Path(FOTO).mkdir(parents=True, exist_ok=True)
    view.grabWindow().scaled(960, 600).save(f"{FOTO}/vergrendeld-klok.png")

# Een toets: het veld komt, en die eerste letter telt mee.
QTest.keyClick(view, Qt.Key.Key_F, Qt.KeyboardModifier.NoModifier)
wacht(400)
veld = kind("wachtwoord")
klopt(kind("invoerBlok").property("visible") and veld.property("text") == "f",
      f"een toets toont het wachtwoordveld; de eerste letter gaat niet verloren ({veld.property('text')!r})")
klopt(veld.property("displayText") == "●", f"het wachtwoord staat er als bolletjes ({veld.property('displayText')!r})")
if FOTO:
    view.grabWindow().scaled(960, 600).save(f"{FOTO}/vergrendeld-invoer.png")

# Fout wachtwoord
for t in "out":
    QTest.keyClick(view, t)
QTest.keyClick(view, Qt.Key.Key_Return)
wacht(300)
melding = kind("melding").property("text")
klopt(auth.antwoorden == ["fout"] and veld.property("text") == "" and ("klopt niet" in melding or "not right" in melding),
      f"fout wachtwoord: naar de authenticator, het veld leeg, en een melding ({auth.antwoorden}, {melding!r})")
klopt(not veld.property("enabled"), "na een fout wachtwoord even wachten (zoals KDE)")
if FOTO:
    view.grabWindow().scaled(960, 600).save(f"{FOTO}/vergrendeld-fout.png")
gestart_voor = auth.gestart
wacht(3300)
klopt(veld.property("enabled") and auth.gestart == gestart_voor + 1, "na het wachten: opnieuw beginnen")

# Escape verbergt en wist
veld.setProperty("text", "half")
QTest.keyClick(view, Qt.Key.Key_Escape)
wacht(300)
klopt(not kind("invoerBlok").property("visible") and veld.property("text") == "", "Escape: terug naar de klok, getypte tekst weg")

# Goed wachtwoord: Qt.quit (zo ontgrendelt kscreenlocker)
QTest.keyClick(view, Qt.Key.Key_G)
wacht(300)
for t in "oed":
    QTest.keyClick(view, t)
QTest.keyClick(view, Qt.Key.Key_Enter)
wacht(200)
klopt(auth.antwoorden[-1] == "goed" and gestopt == [True], f"goed wachtwoord: ontgrendelen (Qt.quit) ({auth.antwoorden})")

# Zonder wachtwoord (vingerafdruk): eerst een knop
gestopt.clear()
auth._had_prompt = False
auth.succeeded.emit()
wacht(300)
knop = kind("zonderWachtwoordKnop")
klopt(knop.property("visible") and not gestopt, "ontgrendeld zonder wachtwoord: eerst de knop 'Ontgrendelen'")

# Slaapstand alleen als het kan
klopt(not kind("slaapKnop").property("visible"), "geen slaapstand-knop als de computer dat niet kan")
root.setProperty("suspendToRamSupported", True)
wacht(100)
klopt(kind("slaapKnop").property("visible"), "wel een slaapstand-knop als het kan")

# Het pakket
meta = json.loads((PAKKET / "metadata.json").read_text())
klopt(meta.get("KPackageStructure") == "Plasma/Shell" and meta.get("X-Plasma-APIVersion") == "2"
      and meta["KPlugin"]["Id"] == "org.bugos.schil",
      "het pakket: Plasma/Shell, API-versie 2 (anders valt kscreenlocker terug op KDE), id org.bugos.schil")
sessie = (ROOT / "system_files/usr/bin/bugos-sessie").read_text()
env = (ROOT / "system_files/etc/xdg/plasma-workspace/env/bugos-schil.sh").read_text()
klopt("PLASMA_DEFAULT_SHELL=org.bugos.schil" in sessie and "unset-environment" in env and "PLASMA_DEFAULT_SHELL" in env,
      "alleen in de proefsessie: bugos-sessie kiest het pakket, de gewone sessie haalt het weg")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
os._exit(1 if fouten else 0)
