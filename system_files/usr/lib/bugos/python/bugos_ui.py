"""Gedeelde bouwstenen voor alle BugOS-apps.

Jip-en-Janneke: hier staan de "legosteentjes" die elke BugOS-app gebruikt,
zodat alle apps er hetzelfde uitzien en hetzelfde praten:
  - t("Nederlands", "English")  -> tekst in de taal van de gebruiker
  - Tegel                       -> een grote knop met pictogram en uitleg
  - Schakelaar                  -> een aan/uit-knop met uitleg
  - draai(...) / start(...)     -> een ander programma laten werken
"""

from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bugos"


# ---------------------------------------------------------------- taal ----

VERTALINGEN = Path("/usr/share/bugos/vertalingen")


def _taal() -> str:
    """Twee-letter taalcode van de gebruiker, bijv. "nl", "en", "de", "tr"."""
    lang = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if not lang:
        lang = locale.getlocale()[0] or ""
    code = lang.split(".")[0].split("_")[0].lower()
    return code if code.isalpha() and len(code) in (2, 3) else "en"


def _catalogus(taal: str) -> dict[str, str]:
    """Vertalingen van de community: Engelse tekst -> tekst in deze taal."""
    if taal in ("nl", "en"):
        return {}
    try:
        data = json.loads((VERTALINGEN / f"{taal}.json").read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str) and v}
    except (OSError, ValueError):
        return {}


TAAL = _taal()
_CATALOGUS = _catalogus(TAAL)


def t(nl: str, en: str) -> str:
    """Geef de tekst in de taal van de gebruiker.

    Nederlands en Engels staan in de code zelf. Andere talen komen uit
    /usr/share/bugos/vertalingen/<taal>.json (zie docs/VERTALEN.md).
    Ontbreekt een vertaling, dan valt BugOS terug op Engels."""
    if TAAL == "nl":
        return nl
    return _CATALOGUS.get(en, en)


# ---------------------------------------------------- programma's starten ----

def bestaat(programma: str) -> bool:
    return shutil.which(programma) is not None


def start(*cmd: str) -> bool:
    """Start een programma los op de achtergrond. Geeft False als het niet kon."""
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except OSError:
        return False


def draai(*cmd: str, timeout: int = 20) -> tuple[int, str]:
    """Draai een programma en wacht op het antwoord. Geeft (code, tekst)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def kde_instelling(module: str) -> None:
    """Open één onderdeel van de (grote) KDE-instellingen."""
    if bestaat("systemsettings"):
        start("systemsettings", module)
    else:
        start("kcmshell6", module)


# -------------------------------------------------------------- uiterlijk ----

ROOD = "#D93A3A"

STIJL = f"""
QPushButton#tegel {{
    text-align: left;
    padding: 14px 16px;
    border-radius: 14px;
    border: 1px solid palette(mid);
    background: palette(base);
}}
QPushButton#tegel:hover {{ border: 2px solid {ROOD}; }}
QPushButton#tegel:focus {{ border: 2px solid {ROOD}; }}
QPushButton#hoofdknop {{
    background: {ROOD}; color: white; border: none; border-radius: 12px;
    padding: 12px 22px; font-weight: bold;
}}
QPushButton#hoofdknop:disabled {{ background: palette(mid); }}
QFrame#kaart {{
    border: 1px solid palette(mid); border-radius: 14px; background: palette(base);
}}
"""


def lettertype(punten: int, vet: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(punten)
    f.setBold(vet)
    return f


def titel(tekst: str, punten: int = 22) -> QLabel:
    label = QLabel(tekst)
    label.setFont(lettertype(punten, True))
    label.setWordWrap(True)
    return label


def uitleg(tekst: str, punten: int = 12) -> QLabel:
    label = QLabel(tekst)
    label.setFont(lettertype(punten))
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def hoofdknop(tekst: str) -> QPushButton:
    knop = QPushButton(tekst)
    knop.setObjectName("hoofdknop")
    knop.setFont(lettertype(13, True))
    knop.setMinimumHeight(48)
    knop.setCursor(Qt.CursorShape.PointingHandCursor)
    return knop


def gewone_knop(tekst: str) -> QPushButton:
    knop = QPushButton(tekst)
    knop.setFont(lettertype(12))
    knop.setMinimumHeight(44)
    knop.setMinimumWidth(120)
    knop.setCursor(Qt.CursorShape.PointingHandCursor)
    return knop


class Tegel(QPushButton):
    """Een grote knop: pictogram, naam en een korte uitleg eronder."""

    def __init__(self, icoon: str, naam: str, tekst: str, actie: Callable[[], None],
                 zoekwoorden: str = ""):
        super().__init__()
        self.setObjectName("tegel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.zoektekst = f"{naam} {tekst} {zoekwoorden}".lower()
        self.setAccessibleName(naam)
        self.setAccessibleDescription(tekst)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(14)
        plaatje = QLabel()
        plaatje.setPixmap(QIcon.fromTheme(icoon, QIcon.fromTheme("preferences-system")).pixmap(QSize(40, 40)))
        plaatje.setFixedSize(44, 44)
        lay.addWidget(plaatje)
        tekstblok = QVBoxLayout()
        tekstblok.setSpacing(2)
        kop = QLabel(naam)
        kop.setFont(lettertype(13, True))
        sub = QLabel(tekst)
        sub.setFont(lettertype(10))
        sub.setWordWrap(True)
        sub.setStyleSheet("color: palette(placeholder-text);")
        tekstblok.addWidget(kop)
        tekstblok.addWidget(sub)
        lay.addLayout(tekstblok, 1)
        for w in (plaatje, kop, sub):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clicked.connect(actie)

    def past_bij(self, zoek: str) -> bool:
        return all(woord in self.zoektekst for woord in zoek.lower().split())


class Schakelaar(QFrame):
    """Een kaart met uitleg en een grote Aan/Uit-knop."""

    omgezet = Signal(bool)

    def __init__(self, naam: str, tekst: str, aan: bool):
        super().__init__()
        self.setObjectName("kaart")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(16)
        blok = QVBoxLayout()
        blok.addWidget(titel(naam, 14))
        blok.addWidget(uitleg(tekst, 11))
        lay.addLayout(blok, 1)
        self.knop = QPushButton()
        self.knop.setCheckable(True)
        self.knop.setMinimumSize(110, 44)
        self.knop.setFont(lettertype(12, True))
        self.knop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.knop.setAccessibleName(naam)
        self.zet(aan)
        self.knop.clicked.connect(self._klik)
        lay.addWidget(self.knop, 0, Qt.AlignmentFlag.AlignVCenter)

    def zet(self, aan: bool) -> None:
        self.knop.setChecked(aan)
        self.knop.setText(t("AAN", "ON") if aan else t("UIT", "OFF"))
        self.knop.setStyleSheet(
            f"background:{ROOD};color:white;border:none;border-radius:22px;" if aan
            else "border:2px solid palette(mid);border-radius:22px;")

    def _klik(self) -> None:
        aan = self.knop.isChecked()
        self.zet(aan)
        self.omgezet.emit(aan)


def maak_app(naam: str, bureaublad_bestand: str, args: Sequence[str]) -> QApplication:
    app = QApplication(list(args))
    app.setApplicationName(naam)
    app.setDesktopFileName(bureaublad_bestand)
    app.setWindowIcon(QIcon.fromTheme("bugos-logo"))
    app.setStyleSheet(STIJL)
    return app


def kader(*widgets: QWidget) -> QWidget:
    """Zet widgets onder elkaar met ruime marges."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 28, 32, 28)
    lay.setSpacing(16)
    for x in widgets:
        lay.addWidget(x)
    return w
