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
    # U084: de lettergrootte volgt 'schaal' meteen (main.qml koppelt hem aan Kirigami.Theme, dat meteen meeverandert).
    _kop = next((c for c in root.findChildren(QQuickItem) if c.property("text") in ("Snelmenu", "Quick menu")), None)
    _voor = _kop.property("font").pixelSize() if _kop else 0
    root.setProperty("schaal", 1.5)
    wacht(50)
    _na = _kop.property("font").pixelSize() if _kop else 0
    root.setProperty("schaal", 1.0)
    klopt(_kop is not None and _na == round(_voor * 1.5), f"[{stijl}] U084: de letters groeien meteen mee met schaal ({_voor} -> {_na})")
    v.close()

# U064: in het startmenu lichten de recente bestanden ook op als je er met Tab op staat.
_start = (QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml").read_text(encoding="utf-8")
klopt("bregel.hovered || bregel.activeFocus" in _start, "U064: startmenu: een recent bestand met de toetsenbordfocus is te zien")

# U098: Enter in het startmenu opent de beste treffer, niet de eerste op het alfabet.
_sv = QQuickView()
_sv.setSource(QUrl.fromLocalFile(str(QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml")))
_sm = _sv.rootObject()
_app = lambda i, n, z: {"id": i, "pad": i, "naam": n, "soort": "app", "groep": "x", "uitleg": "", "icoon": "",  # noqa: E731
                        "zoek": f"{n} {z}".lower()}
_sm.setProperty("gegevens", {"apps": [
    _app("systemsettings.desktop", "All settings", "settings system kde"),
    _app("bugos-backup.desktop", "Backup", "files backup usb"),
    _app("org.kde.dolphin.desktop", "Dolphin (advanced)", "files explorer"),
    _app("bugos-files.desktop", "Files", "files explorer folders"),
    _app("bugos-settings.desktop", "Settings", "settings wifi bluetooth"),
    {"id": "instelling-wifi", "pad": "instelling:wifi", "naam": "Wi-Fi and internet", "soort": "instelling",
     "groep": "Settings", "uitleg": "", "icoon": "", "zoek": "wi-fi and internet wifi wlan"}], "favorieten": [], "recent": [], "gebruiker": {"naam": ""}})
_open: list = []
_sm.start.connect(lambda pad: _open.append(pad))
_veld = _sm.findChild(QObject, "zoekveld")
_uit = {}
for _w in ("settings", "files", "explorer", "wifi"):
    _veld.setProperty("text", _w)
    _sm.openEerste()
    _uit[_w] = _open[-1] if _open else None
klopt(_uit == {"settings": "bugos-settings.desktop", "files": "bugos-files.desktop", "explorer": "bugos-files.desktop",
               "wifi": "instelling:wifi"}, f"U098: Enter opent de beste treffer ({_uit})")
_sv.close()

# U099: elk QML-type dat een plasmoid gebruikt, bestaat (een Qt-type, of een .qml-bestand ernaast). Na een hernoeming
# verwees main.qml naar "Snelmenu" (bestaat niet): dan laadt Plasma het hele snelmenu niet, en de tests hierboven
# (die QuickMenu.qml los laden) zagen dat niet.
import re  # noqa: E402

import PySide6  # noqa: E402

_qt_types = set()
for _f in (Path(PySide6.__file__).parent / "Qt" / "qml").rglob("*.qmltypes"):
    _qt_types.update(re.findall(r'exports: \[[^\]]*?"[\w./]+/(\w+) ', _f.read_text(errors="replace")))
    _qt_types.update(re.findall(r'"[\w./]+/(\w+) \d', _f.read_text(errors="replace")))
_plasma = {"PlasmoidItem"}   # van org.kde.plasma.plasmoid (niet in Qt zelf)
_mist = []
for _qmlbestand in sorted((QML.parent.parent.parent.parent).glob("org.bugos.*/contents/ui/*.qml")):
    _tekst = re.sub(r"//[^\n]*", "", _qmlbestand.read_text(encoding="utf-8"))
    _eigen = {q.stem for q in _qmlbestand.parent.glob("*.qml")} | set(re.findall(r"\bcomponent\s+(\w+)\s*:", _tekst))
    for _type in set(re.findall(r"(?<![\w.])([A-Z]\w*)\s*\{", _tekst)):
        if _type not in _qt_types and _type not in _eigen and _type not in _plasma:
            _mist.append(f"{_qmlbestand.parent.parent.parent.name}/{_qmlbestand.name}: {_type}")
klopt(len(_qt_types) > 100 and not _mist, f"U099: alle QML-types in de plasmoids bestaan ({_mist})")

# U135: in het start- en snelmenu is de toetsenbordfocus goed te zien (een rode rand), en Enter werkt op het tandwiel.
_sm_tekst = (QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml").read_text()
_qm_tekst = QML.read_text()
klopt(_sm_tekst.count("activeFocus ? 2 : 0") >= 4 and "pijl.activeFocus ? 2 : 0" in _qm_tekst
      and "tandwiel.activeFocus ? 2 : 0" in _qm_tekst and _qm_tekst.count("Keys.onReturnPressed") >= 3,
      "U135: startmenu-tegels, -regels, -knoppen en de pijltjes en het tandwiel van het snelmenu tonen de focus")

_ui = QML.parent.parent.parent.parent
for _m in ("org.bugos.startmenu", "org.bugos.quickmenu"):
    _main = (_ui / _m / "contents" / "ui" / "main.qml").read_text(encoding="utf-8")
    klopt("schaal: Kirigami.Theme.defaultFont.pointSize" in _main, f"U084: {_m}: main.qml koppelt de letters aan Kirigami.Theme")
print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
