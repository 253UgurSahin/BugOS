#!/usr/bin/env python3
"""Laad de BugOS-menu's (QML) buiten Plasma om tikfouten te vinden.

Gebruik: QT_QPA_PLATFORM=offscreen python3 tools/qml-test.py [map-voor-plaatjes]
Stopt met een fout als een menu niet laadt.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

ROOT = Path(__file__).resolve().parent.parent / "system_files/usr/share/plasma/plasmoids"
TESTS = [
    (ROOT / "org.bugos.startmenu/contents/ui/StartMenu.qml", "gegevens", {
        "apps": [{"id": "a.desktop", "pad": "/a.desktop", "naam": "Firefox", "uitleg": "Webbrowser",
                  "icoon": "firefox", "groep": "Internet", "zoek": "firefox webbrowser"}],
        "favorieten": [], "recent": [{"naam": "brief.odt", "pad": "/tmp/brief.odt", "map": "~"}],
        "gebruiker": {"naam": "Oma"}}),
    (ROOT / "org.bugos.snelmenu/contents/ui/Snelmenu.qml", "status", {
        "wifi": True, "bluetooth": False, "spel": False, "donker": False, "volume": 40, "stil": False,
        "niet_storen": False}),
]


def main() -> int:
    app = QGuiApplication(sys.argv)
    uit = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    fouten = 0
    views = []
    for pad, eigenschap, waarde in TESTS:
        v = QQuickView()
        v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        v.setSource(QUrl.fromLocalFile(str(pad)))
        if v.errors() or v.rootObject() is None:
            for e in v.errors():
                print(f"FOUT {pad.name}: {e.toString()}")
            fouten += 1
            continue
        v.rootObject().setProperty(eigenschap, waarde)
        v.resize(640, 620)
        v.show()
        views.append((pad, v))
        print(f"OK   {pad.name}")

    def klaar():
        if uit:
            uit.mkdir(parents=True, exist_ok=True)
            for pad, v in views:
                v.grabWindow().save(str(uit / f"{pad.stem}.png"))
        app.exit(1 if fouten else 0)

    QTimer.singleShot(500, klaar)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
