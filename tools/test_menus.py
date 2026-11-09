#!/usr/bin/env python3
"""Test van het snelmenu (QML): de schuiven voor volume en helderheid sturen de waarde die je kiest.

Klikken op de balk, snel slepen en de pijltjestoetsen moeten de nieuwe waarde doorgeven (U060). Zonder Plasma:
QuickMenu.qml laadt in een gewone QQuickView, met nep-status.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_menus.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent
QML = ROOT / "system_files" / "usr" / "share" / "plasma" / "plasmoids" / "org.bugos.quickmenu" / "contents" / "ui" / "QuickMenu.qml"
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def wacht(ms: int) -> None:
    lus = QEventLoop()
    QTimer.singleShot(ms, lus.quit)
    lus.exec()


app = QGuiApplication(sys.argv)
for stijl in ("Basic", "Fusion"):
    os.environ["QT_QUICK_CONTROLS_STYLE"] = stijl
    v = QQuickView()
    v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    v.setSource(QUrl.fromLocalFile(str(QML)))
    klopt(not v.errors(), f"[{stijl}] het snelmenu laadt zonder fouten {v.errors()[:1]}")
    v.resize(420, 600)
    v.show()
    root = v.rootObject()
    root.setProperty("status", {"wifi": True, "bluetooth": False, "spel": False, "donker": False, "volume": 40,
                                "stil": False, "niet_storen": False})
    gestuurd: list = []
    root.zet.connect(lambda wat, waarde, g=gestuurd: g.append((wat, waarde)))
    wacht(200)
    rij = root.findChild(QObject, "volume")
    schuif = next(c for c in rij.findChildren(QQuickItem) if "Slider" in c.metaObject().className())
    klopt(schuif.height() > 0, f"[{stijl}] de volumeschuif is te zien en aan te klikken (hoogte {schuif.height():.0f})")

    def punt(f: float):
        return schuif.mapToScene(QPointF(schuif.width() * f, schuif.height() / 2)).toPoint()

    # klikken op 80%
    QTest.mousePress(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(0.8))
    wacht(60)
    QTest.mouseRelease(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(0.8))
    wacht(400)
    klopt(gestuurd and gestuurd[-1][0] == "volume" and int(gestuurd[-1][1]) >= 70,
          f"[{stijl}] U060: klikken op de balk stuurt de nieuwe waarde ({gestuurd[-1:] })")
    # snel slepen naar 60%
    gestuurd.clear()
    QTest.mousePress(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(0.85))
    for f in (0.8, 0.75, 0.7, 0.65, 0.6):
        QTest.mouseMove(v, punt(f))
        wacht(20)
    QTest.mouseRelease(v, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(0.6))
    wacht(400)
    klopt(gestuurd and 50 <= int(gestuurd[-1][1]) <= 70, f"[{stijl}] U060: snel slepen stuurt waar je losliet ({gestuurd[-1:]})")
    # pijltje naar rechts
    gestuurd.clear()
    schuif.forceActiveFocus()
    voor = schuif.property("value")
    QTest.keyClick(v, Qt.Key.Key_Right)
    wacht(400)
    klopt(gestuurd and int(gestuurd[-1][1]) > voor, f"[{stijl}] U060: het pijltje stuurt de hogere waarde ({voor} -> {gestuurd[-1:]})")
    v.close()

# U064: in het startmenu lichten de recente bestanden ook op als je er met Tab op staat.
_start = (QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml").read_text(encoding="utf-8")
klopt("bregel.hovered || bregel.activeFocus" in _start, "U064: startmenu: een recent bestand met de toetsenbordfocus is te zien")

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
