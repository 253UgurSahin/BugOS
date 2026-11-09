#!/usr/bin/env python3
"""Test van het BugOS-uitzetscherm (Logout.qml), buiten Plasma.

Laadt het scherm zoals de greeter van Plasma dat doet (sdtype, ShutdownType, maysd,
canLogout, spdMethods en screenGeometry als contextproperties) voor een paar gevallen,
kijkt welke knoppen je ziet, drukt op knoppen en toetsen en controleert dat de goede
signalen komen. Met een map als argument bewaart het ook een plaatje per geval.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_logout.py [map-voor-plaatjes]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import (
    QLocale,
    QObject,
    QPoint,
    QPointF,
    QRect,
    Qt,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent
QML = ROOT / "system_files/usr/share/bugos/logout/Logout.qml"
LOGO = ROOT / "system_files/usr/share/bugos/logo-dark.svg"
LETTERS = ROOT / "system_files/usr/share/fonts/bugos"

# Dezelfde waarden als KWorkSpace::ShutdownType in Plasma.
SHUTDOWN_TYPE = {"ShutdownTypeDefault": -1, "ShutdownTypeNone": 0, "ShutdownTypeReboot": 1, "ShutdownTypeHalt": 2}
SPD = {"StandbyState": False, "SuspendState": True, "HibernateState": False}
SCHERM = QRect(0, 0, 1600, 900)
KNOPPEN = ["knop_slaap", "knop_herstart", "knop_uit", "knop_afmelden", "knop_annuleren"]
SIGNALEN = ["logoutRequested", "haltRequested", "haltUpdateRequested", "rebootRequested", "rebootUpdateRequested",
            "cancelRequested", "lockScreenRequested", "cancelSoftwareUpdateRequested"]
SIGNALEN_MET_GETAL = ["suspendRequested", "rebootRequested2"]

fouten = 0
qt_meldingen: list[str] = []


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang_melding(_soort, _context, tekst: str) -> None:
    """Qt-waarschuwingen over ons QML (ReferenceError, bindinglus, ...) onthouden en laten zien."""
    if "Logout.qml" in tekst or "QML" in tekst:
        qt_meldingen.append(tekst)
        print("      Qt: " + tekst)


class Geval:
    """Eén keer het scherm laden, met de gegevens die de greeter meegeeft."""

    def __init__(self, naam: str, sdtype: str, *, maysd: bool = True, can_logout: bool = True,
                 scherm: QRect | None = SCHERM, update: bool | None = None) -> None:
        self.naam = naam
        self.gezien: list[str] = []
        self.view = v = QQuickView()
        ctx = v.rootContext()
        ctx.setContextProperty("sdtype", SHUTDOWN_TYPE[sdtype])
        ctx.setContextProperty("ShutdownType", SHUTDOWN_TYPE)
        ctx.setContextProperty("maysd", maysd)
        ctx.setContextProperty("canLogout", can_logout)
        ctx.setContextProperty("spdMethods", SPD)
        if scherm is not None:
            ctx.setContextProperty("screenGeometry", scherm)
        if update is not None:
            ctx.setContextProperty("softwareUpdatePending", update)
        v.setInitialProperties({"logo": QUrl.fromLocalFile(str(LOGO))})
        v.setSource(QUrl.fromLocalFile(str(QML)))
        self.root = v.rootObject()
        for e in v.errors():
            print("      " + e.toString())
        if self.root is None:
            return
        # De signalen van het QML-wortelobject rechtstreeks aan Python koppelen, zoals de greeter dat in C++ doet.
        for s in SIGNALEN:
            getattr(self.root, s).connect(lambda s=s: self.gezien.append(s))
        for s in SIGNALEN_MET_GETAL:
            getattr(self.root, s).connect(lambda n, s=s: self.gezien.append(f"{s}({n})"))
        v.show()
        v.requestActivate()
        QTest.qWaitForWindowActive(v)
        QTest.qWait(200)  # de iconen (SVG) komen via een data-url binnen, dat gaat niet in één keer

    def knop(self, naam: str) -> QQuickItem:
        return self.root.findChild(QQuickItem, naam)

    def zichtbaar(self) -> list[str]:
        return [n for n in KNOPPEN if self.knop(n).isVisible()]

    def midden(self, naam: str) -> QPoint:
        k = self.knop(naam)
        return k.mapToScene(QPointF(k.width() / 2, k.height() / 2)).toPoint()

    def klik(self, plek: str | QPoint) -> None:
        pos = self.midden(plek) if isinstance(plek, str) else plek
        QTest.mouseClick(self.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.qWait(50)

    def wijs_aan(self, naam: str) -> None:
        """Schuif de muis van de hoek naar de knop (echt bewegen, anders komt er geen hover)."""
        QTest.mouseMove(self.view, QPoint(10, 10))
        QTest.qWait(50)
        QTest.mouseMove(self.view, self.midden(naam))
        QTest.qWait(50)

    def toets(self, key: Qt.Key) -> None:
        QTest.keyClick(self.view, key)
        QTest.qWait(50)

    def focus(self) -> str:
        item = self.view.activeFocusItem()
        return item.objectName() if item is not None else ""

    def tekst(self, naam: str) -> str:
        return self.root.findChild(QObject, naam).property("text")

    def telt_af(self) -> bool:
        return bool(self.root.findChild(QObject, "aftellen").property("running"))

    def iconen_geladen(self) -> bool:
        iconen = self.root.findChildren(QQuickItem, "icoon")
        return len(iconen) == 4 and all(i.property("paintedWidth") > 0 for i in iconen)

    def pak(self) -> list[str]:
        """Geef de signalen tot nu toe terug en begin opnieuw met tellen."""
        gezien, self.gezien = list(self.gezien), []
        return gezien

    def plaatje(self, map_: Path) -> None:
        self.view.grabWindow().save(str(map_ / f"uitzetscherm-{self.naam}.png"))


def laad_letters() -> None:
    if LETTERS.is_dir():
        for p in sorted(LETTERS.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(p))
    families = set(QFontDatabase.families())
    klopt({"Funnel Display", "Inter"} <= families, "lettertypes Funnel Display en Inter geladen (voor een echt plaatje)")


def laad(naam: str, sdtype: str, uit: Path | None, **kw) -> Geval | None:
    eerder = len(qt_meldingen)
    g = Geval(naam, sdtype, **kw)
    klopt(g.root is not None, f"{naam}: Logout.qml laadt (sdtype {sdtype})")
    if g.root is None:
        return None
    klopt(len(qt_meldingen) == eerder, f"{naam}: geen QML-waarschuwingen bij het laden")
    if uit:
        g.plaatje(uit)  # meteen na het laden: zo ziet de gebruiker het scherm
    return g


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qInstallMessageHandler(vang_melding)
    QLocale.setDefault(QLocale("nl_NL"))
    app = QGuiApplication(sys.argv)
    uit = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if uit:
        uit.mkdir(parents=True, exist_ok=True)
    laad_letters()
    gevallen: list[Geval] = []

    # 1. Alles laten zien (Default): "Uitzetten..." zonder keuze, of Ctrl+Alt+Del.
    g = laad("kiezen", "ShutdownTypeDefault", uit)
    if g:
        gevallen.append(g)
        klopt(g.root.width() == 1600 and g.root.height() == 900, "kiezen: zo groot als screenGeometry")
        klopt(g.zichtbaar() == KNOPPEN, "kiezen: slaapstand, opnieuw opstarten, uitzetten, afmelden en 'Toch niet' zichtbaar")
        klopt(g.tekst("kop") == "Wat wil je doen?" and g.tekst("uitleg") == "Kies wat je wilt. Open programma's vragen of je je werk wilt bewaren.",
              "kiezen: kop en uitleg in gewone woorden")
        klopt(g.tekst("knop_uit") == "Uitzetten" and g.tekst("knop_annuleren") == "Toch niet", "kiezen: knoppen heten 'Uitzetten' en 'Toch niet'")
        klopt(not g.telt_af(), "kiezen: er wordt niet afgeteld")
        klopt(g.focus() == "knop_uit", "kiezen: de rode knop 'Uitzetten' heeft de focus")
        klopt(g.iconen_geladen(), "kiezen: de vier lijniconen (SVG in het bestand zelf) worden getekend")
        g.toets(Qt.Key.Key_Left)
        klopt(g.focus() == "knop_herstart", "kiezen: pijltje links gaat naar 'Opnieuw opstarten'")
        g.toets(Qt.Key.Key_Right)
        g.toets(Qt.Key.Key_Right)
        klopt(g.focus() == "knop_afmelden", "kiezen: twee keer rechts gaat naar 'Afmelden'")
        g.toets(Qt.Key.Key_Down)
        klopt(g.focus() == "knop_annuleren", "kiezen: pijltje omlaag gaat naar 'Toch niet'")
        g.toets(Qt.Key.Key_Right)
        klopt(g.focus() == "knop_slaap", "kiezen: na 'Toch niet' gaat rechts weer rond naar 'Slaapstand'")
        g.toets(Qt.Key.Key_Return)
        klopt(g.pak() == ["suspendRequested(2)"], "kiezen: Enter op 'Slaapstand' geeft suspendRequested(2)")
        g.klik("knop_uit")
        klopt(g.pak() == ["haltRequested"], "kiezen: klik op 'Uitzetten' geeft alleen haltRequested (geen cancel erbij)")
        g.klik("knop_herstart")
        klopt(g.pak() == ["rebootRequested"], "kiezen: klik op 'Opnieuw opstarten' geeft rebootRequested")
        g.klik("knop_afmelden")
        klopt(g.pak() == ["logoutRequested"], "kiezen: klik op 'Afmelden' geeft logoutRequested")
        g.klik("knop_annuleren")
        klopt(g.pak() == ["cancelRequested"], "kiezen: klik op 'Toch niet' geeft cancelRequested")
        g.klik(QPoint(40, 40))
        klopt(g.pak() == ["cancelRequested"], "kiezen: klik naast de knoppen geeft cancelRequested")
        g.toets(Qt.Key.Key_Escape)
        klopt(g.pak() == ["cancelRequested"], "kiezen: Escape geeft cancelRequested")

    # 2. Uitzetten gekozen in het startmenu (Halt): één rode knop, en er wordt afgeteld.
    g = laad("uitzetten", "ShutdownTypeHalt", uit)
    if g:
        gevallen.append(g)
        klopt(g.zichtbaar() == ["knop_uit", "knop_annuleren"], "uitzetten: alleen 'Uitzetten' en 'Toch niet' zichtbaar")
        klopt(g.focus() == "knop_uit", "uitzetten: 'Uitzetten' heeft de focus (Enter bevestigt)")
        klopt(g.tekst("kop") == "Computer uitzetten?", "uitzetten: kop 'Computer uitzetten?'")
        uitleg = g.tekst("uitleg")
        klopt(uitleg.startswith("Over ") and uitleg.endswith(" seconden gebeurt het vanzelf.") and g.root.property("resterend") >= 28,
              f"uitzetten: er wordt afgeteld in gewone woorden ({uitleg})")
        klopt(g.telt_af(), "uitzetten: de klok loopt")
        g.root.setProperty("nederlands", False)
        klopt(g.tekst("kop") == "Shut down the computer?" and g.tekst("knop_uit") == "Shut down", "uitzetten: ook in het Engels")
        g.root.setProperty("nederlands", True)
        g.root.setProperty("resterend", 1)
        QTest.qWait(1500)
        klopt(g.pak() == ["haltRequested"], "uitzetten: op nul geeft het scherm vanzelf haltRequested")
        klopt(not g.telt_af() and g.root.property("gestopt") is True, "uitzetten: daarna staat de klok stil")
        klopt(g.tekst("uitleg") == "Weet je het zeker? Druk dan op de knop.", "uitzetten: na het aftellen een gewone zin")
        g.toets(Qt.Key.Key_Return)
        klopt(g.pak() == ["haltRequested"], "uitzetten: Enter geeft haltRequested")
        g.klik("knop_uit")
        klopt(g.pak() == ["haltRequested"], "uitzetten: klik op 'Uitzetten' geeft haltRequested")

    # 3. Afmelden (None), zonder screenGeometry: dan is het scherm zo groot als Screen.
    g = laad("afmelden", "ShutdownTypeNone", uit, scherm=None)
    if g:
        gevallen.append(g)
        scherm = g.view.screen().size()
        klopt(g.root.width() == scherm.width() and g.root.height() == scherm.height(),
              f"afmelden: zonder screenGeometry zo groot als het scherm ({scherm.width()}x{scherm.height()})")
        klopt(g.zichtbaar() == ["knop_afmelden", "knop_annuleren"], "afmelden: alleen 'Afmelden' en 'Toch niet' zichtbaar")
        klopt(g.focus() == "knop_afmelden" and g.tekst("kop") == "Afmelden?", "afmelden: focus op 'Afmelden', kop 'Afmelden?'")
        klopt(g.telt_af(), "afmelden: de klok loopt")
        g.toets(Qt.Key.Key_Right)
        klopt(not g.telt_af() and g.focus() == "knop_annuleren", "afmelden: een toets stopt de klok (en gaat naar 'Toch niet')")
        g.toets(Qt.Key.Key_Left)
        g.toets(Qt.Key.Key_Return)
        klopt(g.pak() == ["logoutRequested"], "afmelden: terug en Enter geeft logoutRequested")
        g.toets(Qt.Key.Key_Escape)
        klopt(g.pak() == ["cancelRequested"], "afmelden: Escape geeft cancelRequested")

    # 4. Opnieuw opstarten met een update die klaarstaat (Reboot + softwareUpdatePending).
    g = laad("herstart-update", "ShutdownTypeReboot", uit, update=True)
    if g:
        gevallen.append(g)
        klopt(g.zichtbaar() == ["knop_herstart", "knop_annuleren"], "herstart-update: alleen 'Opnieuw opstarten' en 'Toch niet'")
        klopt(g.tekst("knop_herstart") == "Opnieuw opstarten voor de update" and g.tekst("kop") == "Opnieuw opstarten?",
              "herstart-update: de knop zegt dat de update meegaat")
        klopt(g.telt_af(), "herstart-update: de klok loopt")
        g.wijs_aan("knop_herstart")
        klopt(not g.telt_af(), "herstart-update: aanwijzen met de muis stopt de klok")
        g.klik("knop_herstart")
        klopt(g.pak() == ["rebootUpdateRequested"], "herstart-update: klik geeft rebootUpdateRequested")

    # 5. Uitzetten met update, en 6. alles laten zien zonder uitzetrechten (maysd uit).
    g = laad("uitzetten-update", "ShutdownTypeHalt", uit, update=True)
    if g:
        gevallen.append(g)
        klopt(g.tekst("knop_uit") == "Uitzetten na de update", "uitzetten-update: knop 'Uitzetten na de update'")
        g.klik("knop_uit")
        klopt(g.pak() == ["haltUpdateRequested"], "uitzetten-update: klik geeft haltUpdateRequested")
    g = laad("kiezen-zonder-uitzetten", "ShutdownTypeDefault", uit, maysd=False)
    if g:
        gevallen.append(g)
        klopt(g.zichtbaar() == ["knop_slaap", "knop_afmelden", "knop_annuleren"], "zonder uitzetrechten: geen 'Uitzetten' en 'Opnieuw opstarten'")
        klopt(g.focus() == "knop_afmelden", "zonder uitzetrechten: 'Afmelden' heeft de focus")

    # U088: twee beeldschermen (de greeter maakt per scherm een venster, met één gedeelde QML-motor): doe je iets op
    # het ene scherm, dan stopt het aftellen ook op het andere, en er wordt niets vanzelf uitgezet.
    from PySide6.QtQml import QQmlEngine
    motor = QQmlEngine()
    twee, signalen = [], []
    for i in range(2):
        v = QQuickView(motor, None)
        ctx = v.rootContext()
        for k, w in (("sdtype", SHUTDOWN_TYPE["ShutdownTypeHalt"]), ("ShutdownType", SHUTDOWN_TYPE), ("maysd", True),
                     ("canLogout", True), ("spdMethods", SPD), ("screenGeometry", SCHERM)):
            ctx.setContextProperty(k, w)
        v.setInitialProperties({"logo": QUrl.fromLocalFile(str(LOGO)), "wachttijd": 2})
        v.setSource(QUrl.fromLocalFile(str(QML)))
        v.rootObject().haltRequested.connect(lambda i=i: signalen.append(i))
        v.show()
        twee.append(v)
    twee[0].requestActivate()
    QTest.qWaitForWindowActive(twee[0])
    QTest.qWait(300)
    k = twee[0].rootObject().findChild(QQuickItem, "knop_uit")
    QTest.mouseMove(twee[0], QPoint(10, 10))   # eerst ernaast, dan erop: zoals de greeter-test hierboven
    QTest.qWait(50)
    QTest.mouseMove(twee[0], k.mapToScene(QPointF(k.width() / 2, k.height() / 2)).toPoint())
    QTest.qWait(3000)
    klopt(twee[1].rootObject().property("gestopt") and not signalen,
          f"U088: twee schermen: iets doen op het ene stopt het aftellen ook op het andere (vanzelf: {signalen})")
    for v in twee:
        v.close()
    motor2 = QQmlEngine()
    twee, signalen = [], []
    for i in range(2):
        v = QQuickView(motor2, None)
        ctx = v.rootContext()
        for k, w in (("sdtype", SHUTDOWN_TYPE["ShutdownTypeHalt"]), ("ShutdownType", SHUTDOWN_TYPE), ("maysd", True),
                     ("canLogout", True), ("spdMethods", SPD), ("screenGeometry", SCHERM)):
            ctx.setContextProperty(k, w)
        v.setInitialProperties({"logo": QUrl.fromLocalFile(str(LOGO)), "wachttijd": 1})
        v.setSource(QUrl.fromLocalFile(str(QML)))
        v.rootObject().haltRequested.connect(lambda i=i: signalen.append(i))
        twee.append(v)
    QTest.qWait(2500)
    klopt(len(signalen) == 1, f"U088: twee schermen, niemand doet iets: er wordt één keer uitgezet ({signalen})")
    for v in twee:
        v.close()

    klopt(not qt_meldingen, "geen QML-waarschuwingen tijdens de hele test")

    if uit:
        print(f"      plaatjes in {uit}")
    for g in gevallen:
        g.view.close()
    app.processEvents()
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
