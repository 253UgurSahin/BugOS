#!/usr/bin/env python3
"""Laad de BugOS-menu's (QML) buiten Plasma om tikfouten te vinden, en controleer het gedrag.

Gebruik: QT_QPA_PLATFORM=offscreen python3 tools/qml-test.py [map-voor-plaatjes]
Stopt met een fout als een menu niet laadt of iets niet klopt.
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

ROOT = Path(__file__).resolve().parent.parent / "system_files/usr/share/plasma/plasmoids"
STARTMENU = ROOT / "org.bugos.startmenu/contents/ui/StartMenu.qml"
SNELMENU = ROOT / "org.bugos.snelmenu/contents/ui/Snelmenu.qml"

APP = {"id": "a.desktop", "pad": "/a.desktop", "naam": "Firefox", "uitleg": "Webbrowser", "icoon": "firefox",
       "groep": "Internet", "zoek": "firefox webbrowser", "soort": "app"}
INSTELLING = {"id": "instelling-wifi", "pad": "instelling:wifi", "naam": "Wifi en internet", "uitleg": "Instellingen",
              "icoon": "network-wireless", "groep": "Instellingen", "zoek": "wifi en internet wlan netwerk",
              "soort": "instelling"}
GEGEVENS = {"apps": [APP, INSTELLING], "favorieten": [APP] * 6,
            "recent": [{"naam": f"brief {i}.odt", "pad": f"/tmp/brief{i}.odt", "map": "~/Documenten"} for i in range(8)],
            "gebruiker": {"naam": "Bugie", "foto": ""}}
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
        views.append((STARTMENU, start))

    snel = laad(SNELMENU)
    klopt(snel is not None, "Snelmenu.qml laadt")
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
    bron = (ROOT / "org.bugos.snelmenu/contents/ui/main.qml").read_text(encoding="utf-8")
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
              "snelmenu: --zet en bugos-instellingen gebruiken de aanhalingstekens")

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
