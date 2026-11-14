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
    # U348: het scrollwieltje op de volumeschuif verandert het volume.
    gestuurd.clear()
    klopt(schuif.property("wheelEnabled") is True, f"[{stijl}] U348: het scrollwieltje werkt op de schuiven van het snelmenu")
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
# U268: Turkse İ en accenten: 'izleyici' vindt 'Sistem İzleyicisi', 'cafe' vindt 'Café'.
_apps = list(_sm.property("gegevens").toVariant()["apps"]) if hasattr(_sm.property("gegevens"), "toVariant") else list(_sm.property("gegevens")["apps"])
_apps += [_app("tr.desktop", "Sistem İzleyicisi", "sistem izleyicisi"), _app("cafe.desktop", "Café Bon", "cafe bon")]
_g = dict(_sm.property("gegevens").toVariant()) if hasattr(_sm.property("gegevens"), "toVariant") else dict(_sm.property("gegevens"))
_g["apps"] = _apps
_sm.setProperty("gegevens", _g)
_tr = {}
for _w in ("izleyici", "IZLEYICI", "İzleyici", "cafe", "café"):
    _veld.setProperty("text", _w)
    _open.clear()
    _sm.openEerste()
    _tr[_w] = _open[-1] if _open else None
klopt(_tr["izleyici"] == _tr["IZLEYICI"] == _tr["İzleyici"] == "tr.desktop" and _tr["cafe"] == _tr["café"] == "cafe.desktop",
      f"U268: zoeken in het startmenu vindt 'İzleyici' met 'izleyici' en 'Café' met 'cafe' ({_tr})")
# U280: de zoeksleutel van het startmenu (QML) is precies die van bugos-start-data (Python): ook ß, ς en kana.
import sys as _sys  # noqa: E402
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject  # noqa: E402

_sys.path.insert(0, str(QML.parents[6] / "lib" / "bugos" / "python"))
import bugos_base as _bb  # noqa: E402

_anders = []
for _w in ("größe", "Straße", "οδηγός", "İstanbul", "がぞう", "Café", "ﬁle", "Ǆ"):
    _qml = QMetaObject.invokeMethod(_sm, "zoeksleutel", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", _w))
    if _qml != _bb.zoeksleutel(_w):
        _anders.append((_w, _qml, _bb.zoeksleutel(_w)))
klopt(not _anders, f"U280: het startmenu en bugos-start-data maken dezelfde zoeksleutel (ß, ς, kana) ({_anders})")
klopt(_uit == {"settings": "bugos-settings.desktop", "files": "bugos-files.desktop", "explorer": "bugos-files.desktop",
               "wifi": "instelling:wifi"}, f"U098: Enter opent de beste treffer ({_uit})")
# U205: typen zoekt ook als de focus niet in het zoekveld staat; U204: na 'Alle apps' staat de focus op de lijst.
_sv.show()
_sm.findChild(QObject, "zoekveld").setProperty("text", "")
_sm.setProperty("focus", True)
_sm.forceActiveFocus()
wacht(50)
QTest.keyClick(_sv, Qt.Key.Key_F)
QTest.keyClick(_sv, Qt.Key.Key_I)
wacht(50)
klopt(_sm.findChild(QObject, "zoekveld").property("text") == "fi",
      f"U205: typen in het startmenu zoekt, ook zonder focus in het zoekveld ({_sm.findChild(QObject, 'zoekveld').property('text')!r})")
# U223: een sneltoets (Ctrl+A) met de focus op een tegel is geen zoektekst.
_sm.findChild(QObject, "zoekveld").setProperty("text", "")
_sm.forceActiveFocus()
wacht(50)
QTest.keyClick(_sv, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
wacht(50)
klopt(_sm.findChild(QObject, "zoekveld").property("text") == "",
      f"U223: Ctrl+A in het startmenu typt niets in het zoekveld ({_sm.findChild(QObject, 'zoekveld').property('text')!r})")
# U349: met de pijltjes naar rij 3, dan terug in het zoekveld klikken: Enter opent wat gemarkeerd is (de eerste).
_veld2 = _sm.findChild(QObject, "zoekveld")
_veld2.setProperty("text", "s")
wacht(50)
_zl = _sm.findChild(QObject, "zoekLijst")
if _zl is not None:
    _zl.setProperty("currentIndex", 2)
    _zl.forceActiveFocus()
    wacht(20)
    _veld2.forceActiveFocus()
    wacht(20)
    klopt(_zl.property("currentIndex") == 0, f"U349: terug in het zoekveld staat de markering weer op wat Enter opent ({_zl.property('currentIndex')})")
else:
    klopt('onActiveFocusChanged: if (activeFocus && zoekLijst.count > 0) zoekLijst.currentIndex = 0' in _start,
          "U349: terug in het zoekveld staat de markering weer op wat Enter opent")
_sv.close()
_smtekst = (QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml").read_text()
klopt("alleLijst.forceActiveFocus()" in _smtekst and "stapel.currentIndex = 0; zoekveld.forceActiveFocus()" in _smtekst,
      "U204: na 'Alle apps' en 'Terug' staat de toetsenbordfocus op iets wat je ziet")
for _m in ("org.bugos.startmenu", "org.bugos.quickmenu"):
    _mt = (QML.parent.parent.parent.parent / _m / "contents" / "ui" / "main.qml").read_text()
    klopt("onPressed: wasOpen = root.expanded" in _mt and "onClicked: root.expanded = !wasOpen" in _mt,
          f"U203: {_m}: nog eens op de knop klikken sluit het menu (gaat niet meteen weer open)")
klopt('snel.tr("Wifi", "Wi-Fi")' in QML.read_text(), "U206: de wifi-tegel heet in het Engels 'Wi-Fi'")

# U099: elk QML-type dat een plasmoid gebruikt, bestaat (een Qt-type, of een .qml-bestand ernaast). Na een hernoeming
# verwees main.qml naar "Snelmenu" (bestaat niet): dan laadt Plasma het hele snelmenu niet, en de tests hierboven
# (die QuickMenu.qml los laden) zagen dat niet.
import re  # noqa: E402

import PySide6  # noqa: E402

from PySide6.QtCore import QLibraryInfo  # noqa: E402

# Waar de QML-modules van Qt staan: in de pip-versie van PySide6 zitten ze in het pakket zelf (PySide6/Qt/qml), in
# BugOS (Fedora) bij de Qt van het systeem (/usr/lib64/qt6/qml). Vraag het Qt zelf, anders vond de test in het
# gebouwde beeld niets en meldde hij elk type (Timer, Rectangle...) als 'bestaat niet'.
_qml_mappen = {Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath)), Path(PySide6.__file__).parent / "Qt" / "qml"}
_qt_types = set()
for _f in (f for _m in _qml_mappen if _m.is_dir() for f in _m.rglob("*.qmltypes")):
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
klopt("regel.activeFocus ? 2 : 0" in _sm_tekst and "ListView.view.currentIndex = i" in _sm_tekst,
      "U149: startmenu: de regel met de toetsenbordfocus licht op en is ook de gekozen regel (Enter opent die)")
klopt(_sm_tekst.count("activeFocus ? 2 : 0") >= 4 and "pijl.activeFocus ? 2 : 0" in _qm_tekst
      and "tandwiel.activeFocus ? 2 : 0" in _qm_tekst and _qm_tekst.count("Keys.onReturnPressed") >= 3,
      "U135: startmenu-tegels, -regels, -knoppen en de pijltjes en het tandwiel van het snelmenu tonen de focus")

_ui = QML.parent.parent.parent.parent
for _m in ("org.bugos.startmenu", "org.bugos.quickmenu"):
    _main = (_ui / _m / "contents" / "ui" / "main.qml").read_text(encoding="utf-8")
    klopt("schaal: Kirigami.Theme.defaultFont.pointSize" in _main, f"U084: {_m}: main.qml koppelt de letters aan Kirigami.Theme")

# ---------------------------------------------------------------- VM-test (A-02, A-05, A-06, A-17, B-23) ---
def klik(view: QQuickView, item: QQuickItem) -> None:
    """Echt klikken (muis) midden op een onderdeel, zoals de tester deed: dan telt wat er bovenop ligt."""
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    wacht(80)


for stijl in ("Basic", "Fusion"):
    os.environ["QT_QUICK_CONTROLS_STYLE"] = stijl
    _qv = QQuickView()
    _qv.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    _qv.setSource(QUrl.fromLocalFile(str(QML)))
    _qv.resize(420, 640)
    _qv.show()
    _q = _qv.rootObject()
    # Een pc zoals in de VM: geen wifi-kaart en geen bluetooth (null), niet storen uit.
    _q.setProperty("status", {"wifi": None, "bluetooth": None, "spel": False, "donker": False, "volume": 40,
                              "stil": False, "niet_storen": False})
    _zet: list = []
    _geopend: list = []
    _q.zet.connect(lambda wat, waarde, g=_zet: g.append((wat, waarde)))
    _q.open.connect(lambda wat, g=_geopend: g.append(wat))
    wacht(200)
    # A-02: het pijltje van 'Niet storen' opent Instellingen > Meldingen en zet niet storen NIET aan.
    klik(_qv, _q.findChild(QQuickItem, "pijl-niet_storen"))
    klopt(_geopend == ["meldingen"] and not _zet,
          f"[{stijl}] A-02: het pijltje van 'Niet storen' opent Meldingen (open {_geopend}, zet {_zet})")
    # A-02: de pijltjes van een grijze wifi- en bluetooth-tegel werken toch.
    _geopend.clear()
    klik(_qv, _q.findChild(QQuickItem, "pijl-wifi"))
    klik(_qv, _q.findChild(QQuickItem, "pijl-bluetooth"))
    klopt(_geopend == ["wifi", "bluetooth"] and not _zet,
          f"[{stijl}] A-02: de pijltjes van grijze wifi- en bluetooth-tegels openen hun pagina ({_geopend})")
    # A-02: een grijze tegel zegt waarom; een gewone tegel niet.
    _w = _q.findChild(QQuickItem, "waarom-wifi")
    _b = _q.findChild(QQuickItem, "waarom-bluetooth")
    _d = _q.findChild(QQuickItem, "waarom-donker")
    klopt(_w is not None and _w.isVisible() and _w.property("text") == "Geen wifi" and _b.isVisible()
          and not _d.isVisible() and "geen wifi" in _q.findChild(QQuickItem, "tegel-wifi").property("waarom"),
          f"[{stijl}] A-02: grijze tegels zeggen waarom ('Geen wifi', 'Deze computer heeft geen wifi')")
    # De tegel zelf werkt nog gewoon (klikken = aan/uit), naast het pijltje.
    _zet.clear()
    klik(_qv, _q.findChild(QQuickItem, "knop-niet_storen"))
    klopt(_zet == [("niet_storen", "aan")], f"[{stijl}] A-02: op de tegel zelf klikken zet niet storen aan ({_zet})")
    _qv.close()

_smpad = QML.parent.parent.parent.parent / "org.bugos.startmenu" / "contents" / "ui" / "StartMenu.qml"
_v2 = QQuickView()
_v2.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
_v2.setSource(QUrl.fromLocalFile(str(_smpad)))
_s2 = _v2.rootObject()
_fav = [_app(f"app{i}.desktop", f"App {i}", "") for i in range(12)]
_s2.setProperty("gegevens", {"apps": [dict(a, groep=f"Groep {i % 5}") for i, a in enumerate(_fav * 3)],
                             "favorieten": _fav, "gebruiker": {"naam": "Test"},
                             "recent": [{"naam": "boodschappen.txt", "pad": "/tmp/b.txt", "map": "Documenten"}]})
# Zoals in Plasma (main.qml): het menu krijgt zijn eigen hoogte, op een scherm van 1280x800 hooguit 680.
_s2.setProperty("maxHoogte", 680)
wacht(100)
_hoog = _s2.property("implicitHeight")
_v2.resize(660, int(_hoog))
_v2.show()
wacht(200)
# A-05: 12 vastgezette apps en 'Recent geopend' passen zonder scrollen in een menu van 1280x800.
_beg = next(c for c in _s2.findChildren(QQuickItem) if c.metaObject().className().startswith("QQuickFlickable")
            and c.property("contentHeight") > 0)
klopt(560 <= _hoog <= 680 and _beg.property("contentHeight") <= _beg.height() + 1,
      f"A-05: het startmenu is ruim (maar past op 1280x800) en 'Recent geopend' staat in beeld zonder scrollen "
      f"(menu {_hoog}, inhoud {_beg.property('contentHeight'):.0f} in {_beg.height():.0f})")
# A-05: een keer gescrold? Bij het openen weer bovenaan.
_beg.setProperty("contentY", 80)
QMetaObject.invokeMethod(_s2, "terugNaarBegin")
klopt(_beg.property("contentY") == 0, "A-05: bij het openen staat de beginpagina weer bovenaan (geen afgeknipte rij)")
# A-06: 'Alle apps' laat veel regels tegelijk zien (Windows: 8-10; de VM: ~3).
_s2.findChild(QObject, "stapel").setProperty("currentIndex", 1)
wacht(150)
_al = _s2.findChild(QQuickItem, "alleLijst")
# Een regel van de lijst herkennen we aan zijn type (AppRegel, een inline component van StartMenu.qml).
_regels = [c for c in _al.findChildren(QQuickItem) if "AppRegel" in c.metaObject().className()]
_rh = _regels[0].height() if _regels else 0
klopt(_al.property("count") > 10 and _rh > 0 and _al.height() / _rh >= 6,
      f"A-06: 'Alle apps' toont minstens 6 regels tegelijk ({_al.height():.0f} / {_rh:.0f}, {len(_regels)} regels gemaakt)")
_s2.findChild(QObject, "stapel").setProperty("currentIndex", 0)
# A-17: het gebruikerstegeltje opent Instellingen > Account (de pagina 'inloggen') en sluit het menu.
_gestart: list = []
_dicht: list = []
_s2.start.connect(lambda pad, g=_gestart: g.append(pad))
_s2.sluiten.connect(lambda g=_dicht: g.append(True))
wacht(50)
klik(_v2, _s2.findChild(QQuickItem, "ikKnop"))
klopt(_gestart == ["instelling:inloggen"] and _dicht, f"A-17: klikken op jezelf in het startmenu opent Account ({_gestart})")
_v2.close()
# B-23: het tandwiel en 'Instellingen openen' van het snelmenu sturen 'start' mee (dan gaat een open Instellingen
# naar de startpagina; zonder pagina bleef het staan waar het was).
_qmain = (QML.parent / "main.qml").read_text(encoding="utf-8")
klopt('wat === "instellingen" ? "start" : wat' in _qmain and "instelling:start" in _qmain
      and '"bugos-start-data --start instelling:")' not in _qmain,
      "B-23: het snelmenu opent Instellingen op de startpagina ('instelling:start')")

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
