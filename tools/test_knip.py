#!/usr/bin/env python3
"""Test van het Knipprogramma (bugos-knip): knippen, tekenen, bewaren, klembord. Zonder Spectacle: een nep-foto.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_knip.py   (met BUGOS_KNIP_FOTO=<map>: ook foto's)
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="bugos-knip-test-"))
(TMP / "thuis" / ".config").mkdir(parents=True)
(TMP / "thuis" / "Afbeeldingen").mkdir()
(TMP / "thuis" / ".config" / "user-dirs.dirs").write_text('XDG_PICTURES_DIR="$HOME/Afbeeldingen"\n')
os.environ.update(HOME=str(TMP / "thuis"), XDG_CONFIG_HOME=str(TMP / "thuis" / ".config"), LC_ALL="nl_NL.UTF-8",
                  LANGUAGE="nl", XDG_RUNTIME_DIR=str(TMP), BUGOS_PYTHON=str(ROOT / "system_files/usr/lib/bugos/python"))
sys.path.insert(0, str(ROOT / "system_files/usr/lib/bugos/python"))
FOTO = os.environ.get("BUGOS_KNIP_FOTO", "")

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


import bugos_knip as kn  # noqa: E402

# ------------------------------------------------------------------------------------------------ de logica
klopt(kn.factor(2560, 1600, 1280, 800) == (2.0, 2.0) and kn.factor(10, 10, 0, 0) == (1.0, 1.0),
      "factor: bij 200 % gaan er twee beeldpunten in één")
klopt(kn.naar_beeld(10, 20, 100, 50, 0, 0, 2.0, 2.0, 2560, 1600) == (20, 40, 200, 100)
      and kn.naar_beeld(-50, -50, 100, 100, 0, 0, 1.0, 1.0, 800, 600) == (0, 0, 50, 50)
      and kn.naar_beeld(1300, 0, 100, 100, 1280, 0, 1.0, 1.0, 400, 400) == (20, 0, 100, 100),
      "naar_beeld: schaal, binnen de foto gehouden, en een tweede scherm rechts")
klopt(not kn.genoeg(2, 50) and kn.genoeg(10, 10), "een klik (een paar beeldpunten) is geen knipsel")
_m = kn.map_schermafbeeldingen()
klopt(_m == TMP / "thuis" / "Afbeeldingen" / "Schermafbeeldingen", f"de map: Afbeeldingen > Schermafbeeldingen ({_m})")
_m.mkdir(parents=True)
_nu = datetime(2026, 11, 27, 17, 5, 12)
_p1 = kn.nieuwe_naam(_m, _nu)
_p1.write_bytes(b"x")
_p2 = kn.nieuwe_naam(_m, _nu)
klopt(_p1.name == "Schermafbeelding 2026-11-27 170512.png" and _p2.name == "Schermafbeelding 2026-11-27 170512 (2).png",
      f"de naam: datum en tijd; bestaat hij al, dan (2) ({_p1.name}, {_p2.name})")
_p1.unlink()
os.environ["BUGOS_KNIP_BRON"] = str(TMP / "bestaat-niet.png")
klopt(not kn.vang_alles(TMP / "x.png"), "vang_alles: lukt het niet, dan False (en dan opent Spectacle zelf)")

# ------------------------------------------------------------------------------------------------ het programma
lader = importlib.machinery.SourceFileLoader("knip", str(ROOT / "system_files/usr/bin/bugos-knip"))
spec = importlib.util.spec_from_loader("knip", lader)
knip = importlib.util.module_from_spec(spec)
lader.exec_module(knip)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = knip.maak_app("bugos-knip", "bugos-knip", ["test"])
scherm = QGuiApplication.primaryScreen()
g = scherm.geometry()


def wacht(ms: int) -> None:
    QTest.qWait(ms)


def nep_foto(factor: float = 2.0) -> QImage:
    """Een 'bureaublad' op 200 %: een kleurverloop met een rood vlak op (100, 100)-(200, 150) (in schermpunten)."""
    b, h = int(g.width() * factor), int(g.height() * factor)
    img = QImage(b, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#F6F5F5"))
    p = QPainter(img)
    p.fillRect(int(100 * factor), int(100 * factor), int(100 * factor), int(50 * factor), QColor("#DE2F3E"))
    p.end()
    return img


uitkomst: list = []
kp = knip.Knipper(nep_foto(), lambda beeld: uitkomst.append(beeld))
kp.toon()
wacht(100)
laag = kp.lagen[0]
klopt(len(kp.lagen) == len(QGuiApplication.screens()) and laag.balk is not None and laag.isVisible(),
      "bevroren scherm: een laag per scherm, met de balk op het hoofdscherm")
klopt(laag.balk.knoppen["rechthoek"].isChecked() and "Sleep" in laag.balk.uitleg.text(),
      "de balk: 'Rechthoek' is gekozen, met uitleg eronder (sleep, Esc)")
if FOTO:
    Path(FOTO).mkdir(parents=True, exist_ok=True)
QTest.mousePress(laag, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 100))
for x, y in ((150, 120), (200, 150)):
    QTest.mouseMove(laag, QPoint(x, y))
    wacht(10)
if FOTO:
    laag.grab().save(f"{FOTO}/knip-slepen.png")
QTest.mouseRelease(laag, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(200, 150))
wacht(50)
klopt(len(uitkomst) == 1 and uitkomst[0] is not None and (uitkomst[0].width(), uitkomst[0].height()) == (200, 100)
      and QColor(uitkomst[0].pixel(100, 50)).name() == "#de2f3e",
      f"slepen van (100,100) naar (200,150) op 200 %: een knipsel van 200x100 beeldpunten, precies het rode vlak "
      f"({(uitkomst[0].width(), uitkomst[0].height()) if uitkomst and uitkomst[0] is not None else None})")
klopt(not kp.lagen, "na het knippen is het bevroren scherm weg")

uitkomst.clear()
kp = knip.Knipper(nep_foto(), lambda beeld: uitkomst.append(beeld))
kp.toon()
wacht(50)
QTest.mouseClick(kp.lagen[0], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(50, 50))
wacht(30)
klopt(not uitkomst and kp.lagen, "een klik zonder slepen knipt niets (het scherm blijft bevroren)")
kp.balk().knoppen["scherm"].click()
klopt(kp.modus == "scherm" and "Klik op een scherm" in kp.balk().uitleg.text(), "'Een scherm': de uitleg zegt 'klik op een scherm'")
QTest.mouseClick(kp.lagen[0], Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(300, 300))
wacht(30)
klopt(len(uitkomst) == 1 and (uitkomst[0].width(), uitkomst[0].height()) == (g.width() * 2, g.height() * 2),
      "'Een scherm': een klik geeft dat hele scherm")

uitkomst.clear()
kp = knip.Knipper(nep_foto(), lambda beeld: uitkomst.append(beeld))
kp.toon()
wacht(50)
QTest.keyClick(kp.lagen[0], Qt.Key.Key_Escape)
wacht(30)
klopt(uitkomst == [None] and not kp.lagen, "Esc stopt: geen knipsel, het bevroren scherm is weg")

# ------------------------------------------------------------------------------------------------ het tekenvel
bw = knip.Bewerker()
knipsel = nep_foto(1.0).copy(0, 0, 400, 300)
bw.zet_knipsel(knipsel, 1.0)
bw.resize(900, 640)
bw.show()
wacht(100)
_bewaard = sorted(_m.glob("Schermafbeelding *.png"))
klopt(len(_bewaard) == 1 and QImage(str(_bewaard[0])).size() == knipsel.size(),
      f"meteen bewaard in Afbeeldingen > Schermafbeeldingen ({[p.name for p in _bewaard]})")
klopt(QApplication.clipboard().image().size() == knipsel.size() and "Gekopieerd en bewaard" in bw.melding.text(),
      "meteen op het klembord, en dat staat eronder")
doek = bw.doek
v = doek.vak()
klopt(v.width() == 400 and v.height() == 300, f"een klein knipsel staat op ware grootte (niet uitgerekt) ({v.width():.0f}x{v.height():.0f})")


def punt(bx: float, by: float) -> QPoint:
    """Een plek in het knipsel (beeldpunten) als plek in het doek."""
    return QPoint(int(v.x() + bx * v.width() / knipsel.width()), int(v.y() + by * v.height() / knipsel.height()))


QTest.mousePress(doek, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(20, 250))
for x in range(30, 300, 15):
    QTest.mouseMove(doek, punt(x, 250))
QTest.mouseRelease(doek, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(300, 250))
wacht(600)
_na = QImage(str(_bewaard[0]))
klopt(len(doek.lijnen) == 1 and QColor(_na.pixel(150, 250)).name() == knip.PEN_KLEUREN[0].lower()
      and QColor(QApplication.clipboard().image().pixel(150, 250)).name() == knip.PEN_KLEUREN[0].lower(),
      "met de pen tekenen: het bewaarde bestand en het klembord zijn vanzelf bijgewerkt")
klopt(bw.knop_ongedaan.isEnabled() and not bw.knop_opnieuw.isEnabled(), "ongedaan maken kan, opnieuw nog niet")
QTest.keyClick(bw, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
wacht(50)
klopt(not doek.lijnen and bw.knop_opnieuw.isEnabled(), "Ctrl+Z haalt de lijn weg")
QTest.keyClick(bw, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
wacht(50)
klopt(len(doek.lijnen) == 1, "Ctrl+Y zet hem terug")
bw.kies_gereedschap("markeer")
klopt(bw.gereedschap["markeer"].isChecked() and any(k.isChecked() and k.property("kleur") == knip.PEN_KLEUREN[4]
                                                     for k in bw.kleur_knoppen),
      "markeerstift: geel, en die kleur is gekozen")
QTest.mousePress(doek, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(30, 60))
QTest.mouseMove(doek, punt(200, 60))
QTest.mouseRelease(doek, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(200, 60))
klopt(len(doek.lijnen) == 2 and doek.lijnen[1]["dikte"] >= doek.lijnen[0]["dikte"] * 4, "de markeerstift is breed")
if FOTO:
    bw.grab().save(f"{FOTO}/knip-bewerker.png")
bw.kies_gereedschap("gum")
QTest.mouseClick(doek, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punt(150, 250))
klopt(len(doek.lijnen) == 1 and doek.lijnen[0]["soort"] == "markeer", "de gum haalt de lijn weg waar je op klikt")
klopt(all(not k.isEnabled() for k in bw.kleur_knoppen), "met de gum zijn de kleuren uit")

# ------------------------------------------------------------------------------------------------ vastleggen
desk = (ROOT / "system_files/usr/share/applications/bugos-knip.desktop").read_text()
stijl = (ROOT / "build_files/style.sh").read_text()
klopt("X-KDE-Shortcuts=Print,Meta+Shift+S" in desk and "Exec=bugos-knip" in desk and "Name[nl]=Knipprogramma" in desk,
      "bugos-knip.desktop: Print Screen en Windows+Shift+S, 'Knipprogramma'")
klopt("bugos-task-manager bugos-files bugos-settings bugos-knip" in stijl
      and "X-KDE-Shortcuts=Print,Meta+Shift+S$//" in stijl and "verberg org.kde.spectacle.desktop" in stijl,
      "bij het bouwen: de sneltoets via kglobalaccel, Spectacle zonder Print en uit het startmenu")
klopt((ROOT / "system_files/usr/share/icons/BugOS/apps/scalable/bugos-knip.svg").is_file(), "het eigen pictogram")

bw.close()
import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
os._exit(1 if fouten else 0)
