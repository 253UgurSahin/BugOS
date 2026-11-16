#!/usr/bin/env python3
"""Laad de BugOS-menu's (QML) buiten Plasma om tikfouten te vinden, en controleer het gedrag.

Gebruik: QT_QPA_PLATFORM=offscreen python3 tools/qml-test.py [map-voor-plaatjes]
Stopt met een fout als een menu niet laadt of iets niet klopt.
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

ROOT = Path(__file__).resolve().parent.parent / "system_files/usr/share/plasma/plasmoids"
STARTMENU = ROOT / "org.bugos.startmenu/contents/ui/StartMenu.qml"
SNELMENU = ROOT / "org.bugos.quickmenu/contents/ui/QuickMenu.qml"

APP = {"id": "a.desktop", "pad": "/a.desktop", "naam": "Firefox", "uitleg": "Webbrowser", "icoon": "firefox",
       "groep": "Internet", "zoek": "firefox webbrowser", "soort": "app",
       # Voor het menu van de rechtermuisknop: twee eigen acties, een Flatpak (dus te verwijderen), niet vastgezet
       # op Start, wel op de taakbalk.
       "acties": [{"id": "new-window", "naam": "Nieuw venster", "icoon": ""},
                  {"id": "new-private-window", "naam": "Nieuw privévenster", "icoon": ""}],
       "verwijder": "org.mozilla.firefox", "vastgezet": False, "op_taakbalk": True}
INSTELLING = {"id": "instelling-wifi", "pad": "instelling:wifi", "naam": "Wifi en internet", "uitleg": "Instellingen",
              "icoon": "network-wireless", "groep": "Instellingen", "zoek": "wifi en internet wlan netwerk",
              "soort": "instelling"}
GEGEVENS = {"apps": [APP, INSTELLING], "favorieten": [APP] * 6,
            "recent": [{"naam": f"brief {i}.odt", "pad": f"/tmp/brief{i}.odt", "map": "~/Documenten"} for i in range(8)],
            "gebruiker": {"naam": "Bugie", "foto": ""}, "taakbalk_kan": True}
STATUS = {"wifi": True, "bluetooth": False, "spel": False, "donker": False, "volume": 40, "stil": False,
          "niet_storen": False}
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(pad: Path) -> QQuickView | None:
    v = QQuickView()
    v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    v.setSource(QUrl.fromLocalFile(str(pad)))
    if v.errors() or v.rootObject() is None:
        for e in v.errors():
            print(f"FOUT  {pad.name}: {e.toString()}")
        return None
    v.resize(660, 640)
    v.show()
    return v


def kind(v: QQuickView, naam: str) -> QObject | None:
    return v.rootObject().findChild(QObject, naam)


def item_met_naam(item, naam: str):
    """Een item op objectName zoeken langs de zichtbare boom (childItems). findChild vindt items uit een Repeater
    niet: die hebben wel een ouder om in te staan, maar geen QObject-ouder."""
    if item.objectName() == naam:
        return item
    for k in item.childItems():
        gevonden = item_met_naam(k, naam)
        if gevonden is not None:
            return gevonden
    return None


def roep(obj: QObject, functie: str, *args):
    """Een JavaScript-functie van het QML-bestand aanroepen (met QVariant-argumenten) en het antwoord teruggeven."""
    uit = QMetaObject.invokeMethod(obj, functie, Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args])
    return uit.toVariant() if hasattr(uit, "toVariant") else uit


def als_lijst(waarde):
    """Een 'var'-eigenschap van QML komt soms als QJSValue terug: dan eerst omzetten naar gewone Python."""
    return waarde.toVariant() if hasattr(waarde, "toVariant") else waarde


def teksten(regels) -> list[str]:
    return [r["tekst"] for r in (als_lijst(regels) or [])]


def test_app_menu(app: QGuiApplication, start: QQuickView) -> None:
    """Het menu van de rechtermuisknop op een app (StartMenu.qml, appMenu): wat erin staat, dat de rechtermuisknop
    het opent zonder de app te starten, dat het binnen het startmenu blijft, en wat elke keuze doorgeeft."""
    from PySide6.QtTest import QTest
    wortel = start.rootObject()
    # Wat er in het menu staat, per soort app.
    _ff = teksten(roep(wortel, "appMenuVoor", APP))
    klopt(_ff == ["Openen", "Nieuw venster", "Nieuw privévenster", "Vastmaken aan Start", "Losmaken van taakbalk",
                  "Verwijderen"],
          f"app-menu: Firefox (Flatpak): Openen, zijn eigen acties, vastmaken, verwijderen ({_ff})")
    eigen = dict(APP, acties=[], verwijder="", vastgezet=True, op_taakbalk=False)
    _eigen = teksten(roep(wortel, "appMenuVoor", eigen))
    klopt(_eigen == ["Openen", "Losmaken van Start", "Vastmaken aan taakbalk"],
          f"app-menu: een app van BugOS zelf: geen 'Verwijderen'; vastgezet: 'Losmaken van Start' ({_eigen})")
    klopt(teksten(roep(wortel, "appMenuVoor", INSTELLING)) == ["Openen"],
          "app-menu: een pagina van Instellingen (zoeken): alleen 'Openen'")
    wortel.setProperty("gegevens", dict(GEGEVENS, taakbalk_kan=False))
    app.processEvents()
    klopt(not any("taakbalk" in x for x in teksten(roep(wortel, "appMenuVoor", APP))),
          "app-menu: zonder takenlijst op de taakbalk geen regel voor de taakbalk")
    wortel.setProperty("gegevens", GEGEVENS)
    app.processEvents()

    # Rechtermuisknop op de eerste vastgezette tegel: het menu van die app gaat open, de app start NIET.
    gestart, acties, vast, dicht = [], [], [], []
    wortel.start.connect(lambda p: gestart.append(p))
    wortel.appActie.connect(lambda p, a: acties.append((p, a)))
    wortel.vastzetten.connect(lambda i, aan: vast.append((i, aan)))
    wortel.sluiten.connect(lambda: dicht.append(1))
    tegel = item_met_naam(wortel, "tegel0")
    popup = kind(start, "appMenu")
    klopt(tegel is not None and popup is not None, "app-menu: tegel en menu zijn er")
    if tegel is None or popup is None:
        return
    midden = tegel.mapToScene(QPointF(tegel.property("width") / 2, tegel.property("height") / 2)).toPoint()
    QTest.mouseClick(start, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, midden)
    app.processEvents()
    klopt(popup.property("visible") is True and not gestart,
          f"app-menu: rechtermuisknop op een tegel opent zijn menu en start de app niet "
          f"(open: {popup.property('visible')}, gestart: {gestart})")
    klopt(teksten(wortel.property("appMenuRegels"))[:3] == ["Openen", "Nieuw venster", "Nieuw privévenster"],
          "app-menu: het menu hoort bij de tegel waarop je klikte")
    # Het menu valt helemaal binnen het startmenu (de pop-up van Plasma knipt de rest weg).
    x, y = popup.property("x"), popup.property("y")
    klopt(x >= 0 and y >= 0 and x + popup.property("width") <= wortel.property("width")
          and y + popup.property("height") <= wortel.property("height"),
          f"app-menu: valt binnen het startmenu ({x}, {y}, {popup.property('width')} x {popup.property('height')})")
    # Een klik naast het menu sluit alleen het menu: er start geen andere app.
    # (Een punt naast het menu: het menu opent bij de muis, dus 'midden' ligt er nu in.)
    naast = QPointF(x - 15 if x > 30 else x + popup.property("width") + 15, y + 10).toPoint()
    QTest.mouseClick(start, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, naast)
    app.processEvents()
    klopt(popup.property("visible") is False and not gestart,
          f"app-menu: een klik ernaast sluit alleen het menu ({popup.property('visible')}, {gestart})")
    # 'Nieuw privévenster' kiezen: de eigen actie van de app, en het startmenu gaat dicht.
    roep(wortel, "toonAppMenu", APP, None, 0, 0, False)
    app.processEvents()
    QMetaObject.invokeMethod(wortel, "kiesAppMenu", Q_ARG("QVariant", 2))
    app.processEvents()
    klopt(acties == [("/a.desktop", "new-private-window")] and dicht and popup.property("visible") is False,
          f"app-menu: 'Nieuw privévenster' start die actie van de app ({acties})")
    # Vastmaken aan Start: het startmenu blijft open.
    dicht.clear()
    roep(wortel, "toonAppMenu", APP, None, 0, 0, True)
    app.processEvents()
    QMetaObject.invokeMethod(wortel, "kiesAppMenu", Q_ARG("QVariant", 3))
    app.processEvents()
    klopt(vast == [("a.desktop", True)] and not dicht,
          f"app-menu: 'Vastmaken aan Start' zet de app vast en het startmenu blijft open ({vast})")
    # Met het toetsenbord: Menu-toets op de gemarkeerde app in 'Alle apps', dan Esc.
    QMetaObject.invokeMethod(wortel, "terugNaarBegin")
    kind(start, "stapel").setProperty("currentIndex", 1)
    lijst = kind(start, "alleLijst")
    lijst.setProperty("currentIndex", 0)
    lijst.forceActiveFocus()
    app.processEvents()
    QTest.keyClick(start, Qt.Key.Key_Menu)
    app.processEvents()
    klopt(popup.property("visible") is True and kind(start, "appMenuLijst").property("currentIndex") == 0,
          "app-menu: de Menu-toets opent het menu van de gemarkeerde app, met 'Openen' gemarkeerd")
    QTest.keyClick(start, Qt.Key.Key_Escape)
    app.processEvents()
    klopt(popup.property("visible") is False and not gestart, "app-menu: Esc sluit het menu (en start niets)")
    QMetaObject.invokeMethod(wortel, "terugNaarBegin")
    app.processEvents()


def main() -> int:
    app = QGuiApplication(sys.argv)
    uit = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    views = []

    start = laad(STARTMENU)
    klopt(start is not None, "StartMenu.qml laadt")
    if start:
        wortel = start.rootObject()
        wortel.setProperty("gegevens", GEGEVENS)
        app.processEvents()
        klopt(kind(start, "alleLijst").property("count") == 1, "startmenu: 'Alle apps' laat alleen echte apps zien (geen instellingen)")
        kind(start, "zoekveld").setProperty("text", "wifi")
        app.processEvents()
        klopt(kind(start, "zoekLijst").property("count") == 1, "startmenu: zoeken op 'wifi' vindt de pagina 'Wifi en internet'")
        kind(start, "zoekveld").setProperty("text", "fire")
        app.processEvents()
        klopt(kind(start, "zoekLijst").property("count") == 1, "startmenu: zoeken op 'fire' vindt Firefox")
        kind(start, "zoekveld").setProperty("text", "")
        app.processEvents()
        klopt(bool(wortel.property("datumTekst")), "startmenu: de datum staat erbij")
        test_app_menu(app, start)
        views.append((STARTMENU, start))

    snel = laad(SNELMENU)
    klopt(snel is not None, "QuickMenu.qml laadt")
    if snel:
        app.processEvents()
        klopt(kind(snel, "evenKijken").property("visible") is True, "snelmenu: zonder status staat er 'Even kijken…'")
        snel.rootObject().setProperty("status", STATUS)
        app.processEvents()
        klopt(kind(snel, "evenKijken").property("visible") is False, "snelmenu: met status verdwijnt 'Even kijken…'")
        klopt(kind(snel, "volume").property("visible") is True and kind(snel, "helderheid").property("visible") is False
              and kind(snel, "batterij").property("visible") is False,
              "snelmenu: pc zonder schermverlichting en batterij: alleen de volumeschuif")
        snel.rootObject().setProperty("status", dict(STATUS, helderheid=70, batterij=76, laadt=True))
        app.processEvents()
        klopt(kind(snel, "helderheid").property("visible") is True and kind(snel, "batterij").property("visible") is True,
              "snelmenu: laptop: ook helderheid en batterij")
        views.append((SNELMENU, snel))

    # De opdrachten van het snelmenu gaan via een shell: elke waarde moet heel aankomen, wat er ook in staat.
    import re
    import shutil
    import subprocess
    from PySide6.QtQml import QJSEngine
    bron = (ROOT / "org.bugos.quickmenu/contents/ui/main.qml").read_text(encoding="utf-8")
    m = re.search(r"function aanhalen\(tekst\) \{.*?\}\s*$", bron, re.M)
    klopt(m is not None, "snelmenu: main.qml heeft een functie om waarden aan te halen")
    if m and shutil.which("bash"):
        js = QJSEngine()
        js.evaluate(m.group(0))
        lastig = "wifi'; touch /tmp/gehackt; echo '$(x) `y` \"z\""
        aangehaald = js.evaluate(f"aanhalen({json.dumps(lastig)})").toString()
        terug = subprocess.run(["bash", "-c", "printf %s " + aangehaald], capture_output=True, text=True).stdout
        klopt(terug == lastig, "snelmenu: een waarde met ' ; $( ) ` komt precies zo aan (er wordt niets uitgevoerd)")
        klopt("root.aanhalen(wat)" in bron and "root.aanhalen(waarde)" in bron,
              "snelmenu: --zet en bugos-settings gebruiken de aanhalingstekens")

    # main.qml van het startmenu: de nieuwe opdrachten met aanhalingstekens, en welke antwoorden nieuwe gegevens zijn.
    smain = (ROOT / "org.bugos.startmenu/contents/ui/main.qml").read_text(encoding="utf-8")
    klopt(all(x in smain for x in ('--actie " + root.aanhalen(pad) + " " + root.aanhalen(actie)',
                                   "root.aanhalen(id)", '--verwijder " + root.aanhalen(flatpak)')),
          "app-menu: main.qml geeft pad, actie, id en Flatpak-id tussen aanhalingstekens door")
    m = re.search(r"function geeftGegevens\(bron\) \{.*?\n    \}", smain, re.S)
    klopt(m is not None, "app-menu: main.qml weet welke antwoorden nieuwe gegevens zijn")
    if m:
        js = QJSEngine()
        js.evaluate(m.group(0))
        ja = [js.evaluate(f"geeftGegevens({json.dumps(b)})").toBool() for b in (
            "bugos-start-data", "bugos-start-data --vastzetten 'a.desktop'", "bugos-start-data --losmaken 'a.desktop'",
            "bugos-start-data --taakbalk vastmaken 'a.desktop'")]
        nee = [js.evaluate(f"geeftGegevens({json.dumps(b)})").toBool() for b in (
            "bugos-start-data --start '/a.desktop'", "bugos-start-data --actie '/a.desktop' 'x'")]
        klopt(all(ja) and not any(nee), f"app-menu: vastmaken/losmaken geven nieuwe gegevens, starten niet ({ja}, {nee})")

    def klaar():
        if uit:
            uit.mkdir(parents=True, exist_ok=True)
            for pad, v in views:
                v.grabWindow().save(str(uit / f"{pad.stem}.png"))
        print()
        print("Alles goed." if not fouten else f"{fouten} fout(en).")
        app.exit(1 if fouten else 0)

    QTimer.singleShot(600, klaar)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
