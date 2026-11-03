"""Het BugOS-ontwerpsysteem: gedeelde bouwstenen voor alle BugOS-apps.

Jip-en-Janneke: hier staan de "legosteentjes" die elke BugOS-app gebruikt,
zodat alle apps er hetzelfde uitzien en hetzelfde praten.

  Taal        t("Nederlands", "English")
  Starten     start(...), draai(...), kde_instelling(...)
  Uiterlijk   maak_app(...)  -> kleuren (licht/donker), lettertypes, stijl
  Bouwstenen  Kop, Knop, Kaart, Tegel, IcoonChip, Schuif, SchakelRij,
              Zoekveld, Zijbalk, Banner, Chip, Voortgang, Sectie

Kleuren en maten komen uit één plek (KLEUREN hieronder), zodat alles klopt
met de huisstijl in docs/HUISSTIJL.md.
"""

from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import (
    Property, QByteArray, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bugos"


# =================================================================== taal ===

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


# ===================================================== programma's starten ===

def bestaat(programma: str) -> bool:
    return shutil.which(programma) is not None


def start(*cmd: str) -> bool:
    """Start een programma los op de achtergrond. Geeft False als het niet kon."""
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
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


# ============================================================== huisstijl ===

ROOD = "#DE2F3E"

KLEUREN = {
    "licht": {
        "achter": "#F6F5F5", "zijbalk": "#EFEDED", "vlak": "#FFFFFF", "vlak_hover": "#FBF9F9",
        "rand": "#E6E2E2", "rand_sterk": "#D5D0D0", "tekst": "#16171C", "tekst2": "#5D6270",
        "tekst3": "#8A8F9A", "accent": "#DE2F3E", "accent_hover": "#C82434", "accent_tekst": "#FFFFFF",
        "accent_zacht": "#FDE9E9", "accent_lijn": "#F3B7BB", "goed": "#14965A", "goed_zacht": "#E3F5EC",
        "let_op": "#B86E00", "let_op_zacht": "#FFF3DC", "fout": "#D3263A", "fout_zacht": "#FDE8EA",
        "schaduw": "rgba(22,23,28,0.06)", "knop": "#F1EEEE", "knop_hover": "#E8E4E4", "schuif_uit": "#D9D4D4",
    },
    "donker": {
        "achter": "#111216", "zijbalk": "#16171C", "vlak": "#1C1E24", "vlak_hover": "#22252C",
        "rand": "#2B2E36", "rand_sterk": "#3A3E48", "tekst": "#EDEEF1", "tekst2": "#A3A8B4",
        "tekst3": "#7C828E", "accent": "#EA3B4B", "accent_hover": "#F25262", "accent_tekst": "#FFFFFF",
        "accent_zacht": "#3A1C22", "accent_lijn": "#6A2A33", "goed": "#3FD17F", "goed_zacht": "#13291D",
        "let_op": "#F2B544", "let_op_zacht": "#2F2612", "fout": "#FF6B70", "fout_zacht": "#36181C",
        "schaduw": "rgba(0,0,0,0.35)", "knop": "#262930", "knop_hover": "#2F333B", "schuif_uit": "#3A3E48",
    },
}

# Kleuren voor de pictogramtegeltjes (zoals bij een telefoon).
TINTEN = {
    "rood": "#E5383F", "oranje": "#F2711C", "geel": "#E8A317", "groen": "#1FA35B", "blauw": "#2F7BF5",
    "paars": "#8B5CF6", "roze": "#E2457A", "turkoois": "#0EA5A4", "grijs": "#6B7280",
}

DISPLAY = "Funnel Display"
K: dict[str, str] = dict(KLEUREN["licht"])  # actieve kleuren (wordt gezet door maak_app)
DONKER = False


def _kies_thema(app: QApplication) -> bool:
    keuze = os.environ.get("BUGOS_THEMA")
    if keuze in ("licht", "donker"):
        return keuze == "donker"
    try:
        schema = app.styleHints().colorScheme()
        if schema == Qt.ColorScheme.Dark:
            return True
        if schema == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _laad_lettertypes() -> None:
    mappen = [Path("/usr/share/fonts/bugos"), Path("/usr/share/bugos/lettertypes")]
    extra = os.environ.get("BUGOS_LETTERS")
    if extra:
        mappen.append(Path(extra))
    for m in mappen:
        if m.is_dir():
            for f in sorted(m.glob("*.ttf")):
                QFontDatabase.addApplicationFont(str(f))


def _stijlblad(k: dict[str, str]) -> str:
    return f"""
* {{ outline: 0; }}
QWidget {{ color: {k['tekst']}; font-size: 14px; }}
QWidget#venster, QWidget#pagina, QScrollArea, QScrollArea > QWidget > QWidget#pagina {{ background: {k['achter']}; }}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
QLabel[rol="titel"] {{ font-family: "{DISPLAY}"; font-size: 30px; font-weight: 600; letter-spacing: -0.5px; }}
QLabel[rol="groot"] {{ font-family: "{DISPLAY}"; font-size: 40px; font-weight: 600; letter-spacing: -0.8px; }}
QLabel[rol="kop2"] {{ font-family: "{DISPLAY}"; font-size: 19px; font-weight: 600; }}
QLabel[rol="kop3"] {{ font-size: 15px; font-weight: 600; }}
QLabel[rol="sub"] {{ color: {k['tekst2']}; font-size: 15px; }}
QLabel[rol="klein"] {{ color: {k['tekst2']}; font-size: 13px; }}
QLabel[rol="sectie"] {{ color: {k['tekst3']}; font-size: 12px; font-weight: 600; letter-spacing: 0.6px; }}

QFrame[kaart="true"] {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 16px; }}
QFrame[kaart="accent"] {{ background: {k['accent_zacht']}; border: 1px solid {k['accent_lijn']}; border-radius: 16px; }}
QFrame#lijn {{ background: {k['rand']}; max-height: 1px; min-height: 1px; border: none; }}

QPushButton {{ background: {k['knop']}; color: {k['tekst']}; border: 1px solid transparent; border-radius: 12px;
  padding: 10px 18px; font-size: 14px; font-weight: 600; }}
QPushButton:hover {{ background: {k['knop_hover']}; }}
QPushButton:focus {{ border: 2px solid {k['accent']}; padding: 9px 17px; }}
QPushButton:disabled {{ color: {k['tekst3']}; }}
QPushButton[soort="hoofd"] {{ background: {k['accent']}; color: {k['accent_tekst']}; }}
QPushButton[soort="hoofd"]:hover {{ background: {k['accent_hover']}; }}
QPushButton[soort="hoofd"]:focus {{ border: 2px solid {k['tekst']}; }}
QPushButton[soort="hoofd"]:disabled {{ background: {k['knop']}; color: {k['tekst3']}; }}
QPushButton[soort="stil"] {{ background: transparent; color: {k['tekst2']}; }}
QPushButton[soort="stil"]:hover {{ background: {k['knop']}; color: {k['tekst']}; }}
QPushButton[soort="rand"] {{ background: transparent; border: 1px solid {k['rand_sterk']}; }}
QPushButton[soort="rand"]:hover {{ background: {k['knop']}; }}
QPushButton[groot="true"] {{ padding: 13px 24px; font-size: 15px; border-radius: 14px; }}
QPushButton[groot="true"]:focus {{ padding: 12px 23px; }}

QPushButton#tegel {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 16px; padding: 0; text-align: left; }}
QPushButton#tegel:hover {{ background: {k['vlak_hover']}; border: 1px solid {k['rand_sterk']}; }}
QPushButton#tegel:focus {{ border: 2px solid {k['accent']}; }}
QPushButton#keuze {{ background: {k['vlak']}; border: 2px solid {k['rand']}; border-radius: 18px; padding: 0; text-align: left; }}
QPushButton#keuze:hover {{ border: 2px solid {k['rand_sterk']}; }}
QPushButton#keuze:focus {{ border: 2px dashed {k['accent_lijn']}; }}
QPushButton#keuze:checked {{ border: 2px solid {k['accent']}; background: {k['vlak']}; }}

QLineEdit {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 14px; padding: 11px 14px;
  font-size: 15px; selection-background-color: {k['accent']}; }}
QLineEdit:focus {{ border: 2px solid {k['accent']}; padding: 10px 13px; }}

QComboBox {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px; padding: 10px 14px; font-size: 14px; }}
QComboBox:focus {{ border: 2px solid {k['accent']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 10px;
  selection-background-color: {k['accent_zacht']}; selection-color: {k['tekst']}; padding: 4px; }}

QListWidget#zijbalk {{ background: transparent; border: none; outline: 0; font-size: 14px; }}
QListWidget#zijbalk::item {{ padding: 10px 12px; border-radius: 10px; margin: 1px 0; color: {k['tekst']}; }}
QListWidget#zijbalk::item:hover {{ background: {k['knop']}; }}
QListWidget#zijbalk::item:selected {{ background: {k['accent_zacht']}; color: {k['accent']}; font-weight: 600; }}
QWidget#zijkant {{ background: {k['zijbalk']}; border-right: 1px solid {k['rand']}; }}

QProgressBar {{ background: {k['knop']}; border: none; border-radius: 6px; min-height: 12px; max-height: 12px;
  color: transparent; text-align: center; }}
QProgressBar::chunk {{ border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
  stop:0 #FF5C50, stop:1 {k['accent']}); }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {k['rand_sterk']}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {k['tekst3']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QScrollBar:horizontal {{ height: 0; }}

QMenu {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 9px 22px 9px 12px; border-radius: 8px; color: {k['tekst']}; }}
QMenu::item:selected {{ background: {k['knop']}; }}
QMenu::item:disabled {{ color: {k['tekst3']}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::separator {{ height: 1px; background: {k['rand']}; margin: 6px 8px; }}
QToolTip {{ background: {k['tekst']}; color: {k['achter']}; border: none; border-radius: 8px; padding: 6px 10px; }}
QCheckBox, QRadioButton {{ spacing: 10px; font-size: 15px; }}
"""


def _palet(k: dict[str, str]) -> QPalette:
    p = QPalette()
    rollen = {
        QPalette.ColorRole.Window: k["achter"], QPalette.ColorRole.WindowText: k["tekst"],
        QPalette.ColorRole.Base: k["vlak"], QPalette.ColorRole.AlternateBase: k["vlak_hover"],
        QPalette.ColorRole.Text: k["tekst"], QPalette.ColorRole.Button: k["knop"],
        QPalette.ColorRole.ButtonText: k["tekst"], QPalette.ColorRole.Highlight: k["accent"],
        QPalette.ColorRole.HighlightedText: k["accent_tekst"], QPalette.ColorRole.PlaceholderText: k["tekst3"],
        QPalette.ColorRole.ToolTipBase: k["tekst"], QPalette.ColorRole.ToolTipText: k["achter"],
        QPalette.ColorRole.Mid: k["rand"], QPalette.ColorRole.Midlight: k["rand"],
        QPalette.ColorRole.Link: k["accent"],
    }
    for rol, kleur in rollen.items():
        p.setColor(rol, QColor(kleur))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(k["tekst3"]))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(k["tekst3"]))
    return p


def maak_app(naam: str, bureaublad_bestand: str, args: Sequence[str]) -> QApplication:
    """Maak de QApplication met de BugOS-stijl (licht of donker, vanzelf)."""
    global DONKER
    app = QApplication(list(args))
    app.setApplicationName(naam)
    app.setDesktopFileName(bureaublad_bestand)
    app.setWindowIcon(QIcon.fromTheme("bugos-logo", QIcon("/usr/share/bugos/logo.svg")))
    _laad_lettertypes()
    DONKER = _kies_thema(app)
    K.clear()
    K.update(KLEUREN["donker" if DONKER else "licht"])
    app.setStyle("Fusion")
    app.setPalette(_palet(K))
    # Inter is de BugOS-letter; gebruik hem als het systeem een algemene letter geeft.
    f = app.font()
    if f.family() in ("Sans Serif", "DejaVu Sans", "Noto Sans", "Cantarell", "") and \
            "Inter" in QFontDatabase.families():
        f.setFamily("Inter")
    f.setPixelSize(14)
    app.setFont(f)
    app.setStyleSheet(_stijlblad(K))
    return app


def uitvoeren(app: QApplication, venster: QWidget) -> int:
    """Toon het venster, wacht tot de gebruiker klaar is en ruim netjes op.

    Het venster moet weg zijn vóórdat de app verdwijnt, anders crasht Qt bij
    het afsluiten. Geef daarom het venster direct mee: uitvoeren(app, Venster())."""
    venster.show()
    code = app.exec()
    venster.hide()
    venster.deleteLater()
    del venster
    import gc
    gc.collect()
    return code


def kleur(naam: str) -> QColor:
    return QColor(K.get(naam, naam))


# ============================================================ lijn-iconen ===
# Eigen BugOS-pictogrammen: 24 x 24, lijn van 2, ronde uiteinden. Dezelfde
# stijl als op de website, zodat alles één familie is. Gebruik: "lijn:naam".

LIJN = {
    "ster": '<path d="M12 3.6l2.6 5.2 5.7.8-4.1 4 1 5.7L12 16.6l-5.2 2.7 1-5.7-4.1-4 5.7-.8z"/>',
    "wereld": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.3 2.5 3.5 5.3 3.5 8.5s-1.2 6-3.5 8.5c-2.3-2.5-3.5-5.3-3.5-8.5s1.2-6 3.5-8.5z"/>',
    "document": '<path d="M7 3.5h6.5l4.5 4.5v11.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z"/><path d="M13.5 3.5V8H18M9 12.5h6M9 16h4"/>',
    "foto": '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.5"/><path d="m4 17.5 5-4.5 3.5 3 3-2.5 4.5 4"/>',
    "muziek": '<path d="M9 17.5V6.5l10-2v11"/><circle cx="6.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="15.5" r="2.5"/>',
    "spel": '<path d="M7 8.5h10a4.5 4.5 0 0 1 4.5 4.5v1a2.5 2.5 0 0 1-4.4 1.6L15.5 14h-7l-1.6 1.6A2.5 2.5 0 0 1 2.5 14v-1A4.5 4.5 0 0 1 7 8.5z"/><path d="M7.5 10.5v3M6 12h3M15.5 11.5h.01M17.5 12.5h.01"/>',
    "praten": '<path d="M5.5 4.5h13a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H11l-4.5 3.5v-3.5h-1a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z"/>',
    "leren": '<path d="M2.5 9.5 12 5l9.5 4.5L12 14z"/><path d="M6.5 11.5v4c1.4 1.5 3.3 2.5 5.5 2.5s4.1-1 5.5-2.5v-4M21.5 9.5v4.5"/>',
    "handig": '<path d="M14.7 6.3a3.8 3.8 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.7-7.7a3.8 3.8 0 0 1-2-2z"/>',
    "code": '<path d="m8.5 8-4 4 4 4M15.5 8l4 4-4 4M13.5 5.5l-3 13"/>',
    "vink": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "huis": '<path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5h-5v5H5a1 1 0 0 1-1-1z"/>',
    "schakelaar": '<rect x="2.5" y="7" width="19" height="10" rx="5"/><circle cx="16.5" cy="12" r="2.5"/>',
    "computer": '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/>',
    "wifi": '<path d="M2.8 9.2a13.5 13.5 0 0 1 18.4 0M5.8 12.6a9 9 0 0 1 12.4 0M8.9 16a4.6 4.6 0 0 1 6.2 0M12 19.4h.01"/>',
    "bluetooth": '<path d="m7 7.5 10 9-5 4.5V3l5 4.5-10 9"/>',
    "geluid": '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.2 4.2 0 0 1 0 6M18.3 6.4a8 8 0 0 1 0 11.2"/>',
    "printer": '<path d="M7 8.5V3.5h10v5"/><rect x="3.5" y="8.5" width="17" height="8" rx="2"/><path d="M7 13.5h10v7H7z"/>',
    "opslag": '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="M3.5 13.5h17M7.5 16.3h.01M10.5 16.3h.01"/>',
    "verversen": '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4v4.5H15"/>',
    "schijf": '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M9.5 6.5h5M12 17.5h.01"/>',
    "klok": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "terug": '<path d="M9 7 4.5 11.5 9 16"/><path d="M5 11.5h9.5a5 5 0 0 1 0 10H12"/>',
    "film": '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="m10 9.5 4.5 2.5-4.5 2.5z"/>',
    "download": '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
    "map": '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "map-plus": '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M12 10.5v6M9 13.5h6"/>',
    "links": '<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>',
    "rechts": '<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
    "prullenbak": '<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 12a1.5 1.5 0 0 0 1.5 1.5h6a1.5 1.5 0 0 0 1.5-1.5l1-12M10 11v6M14 11v6"/>',
    "uitwerpen": '<path d="M12 4.5 4.5 13h15z"/><path d="M5 18.5h14"/>',
    "usb": '<path d="M8 10.5V4.5h8v6"/><rect x="6" y="10.5" width="12" height="10" rx="2.5"/><path d="M10.5 7h.01M13.5 7h.01"/>',
    "kopieer": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
    "plak": '<rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5V3.5h6v1M9 10h6M9 13.5h6M9 17h3"/>',
    "schaar": '<circle cx="6.5" cy="7" r="2.5"/><circle cx="6.5" cy="17" r="2.5"/><path d="M8.7 8.3 19.5 18M8.7 15.7 19.5 6"/>',
    "potlood": '<path d="M4.5 19.5 5.5 15 15.5 5a2.1 2.1 0 0 1 3 3l-10 10z"/><path d="m13.5 7 3 3"/>',
    "openen": '<path d="M13.5 4.5h6v6M19.5 4.5 11 13M17.5 13.5v5a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5V8A1.5 1.5 0 0 1 6 6.5h5"/>',
    "oog": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "kruis": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "laptop": '<rect x="4.5" y="5" width="15" height="10.5" rx="1.5"/><path d="M2.5 19h19"/>',
    "kaart": '<path d="M9 3.5h7.5A1.5 1.5 0 0 1 18 5v14a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V6.5z"/>'
             '<path d="M10 7V9.5M13 7V9.5M16 7V9.5"/>',
    "cd": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.5"/>',
    "slot": '<rect x="5.5" y="10.5" width="13" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
}


def lijn_pixmap(naam: str, kleur_: str | QColor, px: int, dikte: float = 2.0) -> QPixmap:
    """Teken een BugOS-lijnicoon op px x px beeldpunten (doorzichtige achtergrond)."""
    from PySide6.QtSvg import QSvgRenderer
    k = QColor(K.get(kleur_, kleur_) if isinstance(kleur_, str) else kleur_).name()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{k}" '
           f'stroke-width="{dikte}" stroke-linecap="round" stroke-linejoin="round">{LIJN.get(naam, "")}</svg>')
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return pm


def lijn_icoon(naam: str, kleur_: str | QColor = "tekst2", maat: int = 20,
               gekozen: str | QColor | None = "accent") -> QIcon:
    """Een QIcon van een lijnicoon; de gekozen stand (in een lijst) is rood."""
    ic = QIcon()
    for schaal in (1, 2, 3):
        ic.addPixmap(lijn_pixmap(naam, kleur_, maat * schaal), QIcon.Mode.Normal)
        if gekozen is not None:
            ic.addPixmap(lijn_pixmap(naam, gekozen, maat * schaal), QIcon.Mode.Selected)
    return ic


def icoon(naam: str) -> QIcon:
    """'lijn:naam' -> eigen lijnicoon, anders het pictogram uit het thema."""
    if naam.startswith("lijn:"):
        return lijn_icoon(naam[5:])
    return QIcon.fromTheme(naam)


# ============================================================= bouwstenen ===

def lettertype(punten: int, vet: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(punten)
    f.setBold(vet)
    return f


def label(tekst: str, rol: str = "", wrap: bool = True, kopieerbaar: bool = False) -> QLabel:
    lab = QLabel(tekst)
    if rol:
        lab.setProperty("rol", rol)
    lab.setWordWrap(wrap)
    if kopieerbaar:
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


def titel(tekst: str, punten: int = 0) -> QLabel:
    """Grote kop (in de BugOS-letter). 'punten' blijft voor oude code."""
    rol = "titel" if punten == 0 or punten >= 20 else ("kop2" if punten >= 14 else "kop3")
    return label(tekst, rol)


def uitleg(tekst: str, punten: int = 12) -> QLabel:
    return label(tekst, "sub" if punten >= 12 else "klein", kopieerbaar=True)


def wit_icoon(ic: QIcon, maat: int) -> QIcon:
    """Maak een (eenkleurig) pictogram wit, voor op een rode knop."""
    uit = QIcon()
    for schaal in (1, 2):
        bron = ic.pixmap(QSize(maat, maat), schaal)
        if bron.isNull():
            continue
        wit = QPixmap(bron.size())
        wit.setDevicePixelRatio(bron.devicePixelRatio())
        wit.fill(Qt.GlobalColor.transparent)
        q = QPainter(wit)
        q.drawPixmap(0, 0, bron)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        q.fillRect(wit.rect(), QColor("#FFFFFF"))
        q.end()
        uit.addPixmap(wit)
    return uit if not uit.isNull() else ic


class Knop(QPushButton):
    """Knop in de BugOS-stijl. soort: "hoofd" (rood), "gewoon", "stil" of "rand"."""

    def __init__(self, tekst: str, soort: str = "gewoon", icoon: str | None = None, groot: bool = False):
        super().__init__(tekst)
        self.setProperty("soort", soort)
        if groot:
            self.setProperty("groot", "true")
        if icoon and icoon.startswith("lijn:"):
            self.setIcon(lijn_icoon(icoon[5:], "#FFFFFF" if soort == "hoofd" else "tekst", 18, gekozen=None))
            self.setIconSize(QSize(18, 18))
        elif icoon:
            ic = QIcon.fromTheme(icoon)
            self.setIcon(wit_icoon(ic, 18) if soort == "hoofd" else ic)
            self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48 if groot else 42)


def hoofdknop(tekst: str) -> Knop:
    return Knop(tekst, "hoofd", groot=True)


def gewone_knop(tekst: str) -> Knop:
    return Knop(tekst, "gewoon")


def lijn() -> QFrame:
    f = QFrame()
    f.setObjectName("lijn")
    return f


class Kaart(QFrame):
    """Een wit (of donker) vlak met afgeronde hoeken."""

    def __init__(self, soort: str = "true", marge: int = 20, ruimte: int = 12, richting: str = "v"):
        super().__init__()
        self.setProperty("kaart", soort)
        self.lay = QVBoxLayout(self) if richting == "v" else QHBoxLayout(self)
        self.lay.setContentsMargins(marge, marge, marge, marge)
        self.lay.setSpacing(ruimte)


class IcoonChip(QWidget):
    """Pictogram op een afgerond, gekleurd tegeltje (zoals op een telefoon).

    vol=True  -> stevige kleur met een wit symbool (standaard)
    vol=False -> zachte tint met het pictogram in eigen kleuren
    """

    TEKENS = ("vink", "uitroep", "kruis")

    def __init__(self, icoon: str, tint: str = "rood", maat: int = 44, icoon_maat: int | None = None,
                 vol: bool = True):
        super().__init__()
        self.teken = icoon if icoon in self.TEKENS else ""
        self.lijn = icoon[5:] if icoon.startswith("lijn:") else ""
        self.icoon = QIcon() if (self.teken or self.lijn) else QIcon.fromTheme(icoon, QIcon.fromTheme("application-x-executable"))
        self.neutraal = tint == "neutraal"
        self.tint = QColor(K["tekst2"]) if self.neutraal else QColor(TINTEN.get(tint, tint))
        self.vol = vol
        self.icoon_maat = icoon_maat or int(maat * (0.5 if vol else 0.62))
        self.setFixedSize(maat, maat)

    def _wit(self, m: int) -> QPixmap:
        dpr = self.devicePixelRatioF()
        bron = self.icoon.pixmap(QSize(m, m), dpr)
        if bron.isNull() or bron.width() == 0:
            return bron
        wit = QPixmap(bron.size())
        wit.setDevicePixelRatio(bron.devicePixelRatio())
        wit.fill(Qt.GlobalColor.transparent)
        q = QPainter(wit)
        q.drawPixmap(0, 0, bron)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        q.fillRect(wit.rect(), QColor("#FFFFFF"))
        q.end()
        return wit

    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        pad = QPainterPath()
        pad.addRoundedRect(r, r.width() * 0.3, r.width() * 0.3)
        m = self.icoon_maat
        x = (self.width() - m) / 2
        dpr = self.devicePixelRatioF()
        if self.vol and not self.neutraal:
            verloop = QLinearGradient(0, 0, 0, r.height())
            verloop.setColorAt(0, self.tint.lighter(118))
            verloop.setColorAt(1, self.tint)
            p.fillPath(pad, verloop)
            if self.teken:
                self._teken(p, r)
                return
            if self.lijn:
                p.drawPixmap(QRectF(x, x, m, m), lijn_pixmap(self.lijn, "#FFFFFF", int(m * dpr), 2.2), QRectF())
                return
            wit = self._wit(m)
            if not wit.isNull():
                p.drawPixmap(QRectF(x, x, m, m), wit, QRectF())
        else:
            if self.neutraal:
                p.fillPath(pad, QColor(K["knop"]))
            else:
                achter = QColor(self.tint)
                achter.setAlphaF(0.22 if DONKER else 0.13)
                p.fillPath(pad, achter)
            if self.lijn:
                glyph = QColor(K["tekst2"]) if self.neutraal else self.tint
                p.drawPixmap(QRectF(x, x, m, m), lijn_pixmap(self.lijn, glyph, int(m * dpr), 2.0), QRectF())
            else:
                self.icoon.paint(p, int(x), int(x), m, m)


    def _teken(self, p: QPainter, r: QRectF) -> None:
        """Strakke eigen tekens: vinkje, uitroepteken of kruis (wit)."""
        w = r.width()
        pen = QPen(QColor("#FFFFFF"), max(2.0, w * 0.085))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = r.center().x(), r.center().y()
        if self.teken == "vink":
            p.drawPolyline([QPointF(cx - w * 0.2, cy + w * 0.01), QPointF(cx - w * 0.05, cy + w * 0.16),
                            QPointF(cx + w * 0.22, cy - w * 0.14)])
        elif self.teken == "kruis":
            d = w * 0.16
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx + d, cy - d), QPointF(cx - d, cy + d))
        else:
            p.drawLine(QPointF(cx, cy - w * 0.2), QPointF(cx, cy + w * 0.04))
            p.setBrush(QColor("#FFFFFF"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy + w * 0.19), w * 0.055, w * 0.055)


class Chip(QLabel):
    """Klein label met een kleurtje, bijv. 'Aanbevolen' of 'Werkt'."""

    def __init__(self, tekst: str, soort: str = "accent"):
        super().__init__(tekst)
        voor, achter = {
            "accent": (K["accent"], K["accent_zacht"]), "goed": (K["goed"], K["goed_zacht"]),
            "let_op": (K["let_op"], K["let_op_zacht"]), "fout": (K["fout"], K["fout_zacht"]),
            "grijs": (K["tekst2"], K["knop"]),
        }.get(soort, (K["accent"], K["accent_zacht"]))
        self.setStyleSheet(f"background:{achter};color:{voor};border-radius:10px;padding:3px 10px;"
                           f"font-size:12px;font-weight:600;")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class Banner(QFrame):
    """Een meldingsbalk: info, goed, let_op of fout."""

    def __init__(self, tekst: str = "", soort: str = "info"):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        self.teken = QLabel()
        self.tekst = label(tekst)
        lay.addWidget(self.teken, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.tekst, 1)
        self.zet(tekst, soort)

    def zet(self, tekst: str, soort: str = "info") -> None:
        voor, achter, icoon = {
            "info": (K["tekst"], K["knop"], "dialog-information"),
            "goed": (K["goed"], K["goed_zacht"], "emblem-success"),
            "let_op": (K["let_op"], K["let_op_zacht"], "dialog-warning"),
            "fout": (K["fout"], K["fout_zacht"], "dialog-error"),
            "bezig": (K["accent"], K["accent_zacht"], "view-refresh"),
        }.get(soort, (K["tekst"], K["knop"], "dialog-information"))
        self.setStyleSheet(f"QFrame{{background:{achter};border-radius:14px;}} QLabel{{color:{voor};font-size:14px;}}")
        self.teken.setPixmap(QIcon.fromTheme(icoon).pixmap(20, 20))
        self.tekst.setText(tekst)
        self.setVisible(bool(tekst))


class Schuif(QAbstractButton):
    """Een echte aan/uit-schuifschakelaar (met een vloeiende beweging)."""

    def __init__(self, aan: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(aan)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 30)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._stand = 1.0 if aan else 0.0
        self._anim = QPropertyAnimation(self, b"stand", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._beweeg)

    def _beweeg(self, aan: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._stand)
        self._anim.setEndValue(1.0 if aan else 0.0)
        self._anim.start()

    def _get(self) -> float:
        return self._stand

    def _set(self, w: float) -> None:
        self._stand = w
        self.update()

    stand = Property(float, _get, _set)

    def zet_stil(self, aan: bool) -> None:
        """Zet de stand zonder signaal (bijv. bij het inlezen)."""
        self.blockSignals(True)
        self.setChecked(aan)
        self.blockSignals(False)
        self._set(1.0 if aan else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(52, 30)

    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        uit, aan = QColor(K["schuif_uit"]), QColor(K["accent"])
        s = self._stand
        baan = QColor(int(uit.red() + (aan.red() - uit.red()) * s), int(uit.green() + (aan.green() - uit.green()) * s),
                      int(uit.blue() + (aan.blue() - uit.blue()) * s))
        if not self.isEnabled():
            baan.setAlphaF(0.45)
        r = QRectF(1, 1, w - 2, h - 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(baan)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if self.hasFocus():
            p.setPen(QPen(QColor(K["accent"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), h / 2, h / 2)
            p.setPen(Qt.PenStyle.NoPen)
        d = h - 8
        x = 4 + (w - 8 - d) * s
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, 5, d, d))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 4, d, d))


class SchakelRij(QFrame):
    """Een regel met titel, uitleg en rechts een schuifschakelaar."""

    omgezet = Signal(bool)

    def __init__(self, naam: str, tekst: str, aan: bool, icoon: str | None = None, tint: str = "rood"):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)
        if icoon:
            lay.addWidget(IcoonChip(icoon, tint, 40), 0, Qt.AlignmentFlag.AlignTop)
        blok = QVBoxLayout()
        blok.setSpacing(3)
        blok.addWidget(label(naam, "kop3"))
        blok.addWidget(label(tekst, "klein"))
        lay.addLayout(blok, 1)
        self.schuif = Schuif(aan)
        self.schuif.setAccessibleName(naam)
        self.schuif.toggled.connect(self.omgezet.emit)
        lay.addWidget(self.schuif, 0, Qt.AlignmentFlag.AlignVCenter)


class Schakelaar(SchakelRij):
    """Oude naam (voor bestaande code): een kaart met uitleg en een schuif."""

    def __init__(self, naam: str, tekst: str, aan: bool):
        super().__init__(naam, tekst, aan)
        self.setProperty("kaart", "true")

    def zet(self, aan: bool) -> None:
        self.schuif.zet_stil(aan)


class Groep(Kaart):
    """Een kaart met regels onder elkaar, gescheiden door dunne lijntjes."""

    def __init__(self):
        super().__init__(marge=0, ruimte=0)

    def voeg(self, w: QWidget) -> QWidget:
        if self.lay.count():
            self.lay.addWidget(lijn())
        self.lay.addWidget(w)
        return w


class Tegel(QPushButton):
    """Een grote klikbare tegel: pictogram (op een gekleurd tegeltje), naam en uitleg."""

    def __init__(self, icoon: str, naam: str, tekst: str, actie: Callable[[], None],
                 zoekwoorden: str = "", tint: str = "rood"):
        super().__init__()
        self.setObjectName("tegel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Vaste hoogte: ruimte voor de naam en twee regels uitleg (niets wordt afgeknipt).
        self.setFixedHeight(102)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.zoektekst = f"{naam} {tekst} {zoekwoorden}".lower()
        self.setAccessibleName(naam)
        self.setAccessibleDescription(tekst)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)
        chip = IcoonChip(icoon, tint, 44)
        lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
        blok = QVBoxLayout()
        blok.setSpacing(2)
        kop = label(naam, "kop3", wrap=False)
        sub = label(tekst, "klein")
        blok.addWidget(kop)
        blok.addWidget(sub)
        blok.addStretch(1)
        lay.addLayout(blok, 1)
        for w in (chip, kop, sub):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clicked.connect(actie)

    def past_bij(self, zoek: str) -> bool:
        return all(woord in self.zoektekst for woord in zoek.lower().split())


class KeuzeKaart(QPushButton):
    """Een grote kaart die je kunt aanklikken om iets te kiezen."""

    def __init__(self, inhoud: QWidget):
        super().__init__()
        self.setObjectName("keuze")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        lay.addWidget(inhoud)
        inhoud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class SchijfKiezer(QWidget):
    """Laat aangesloten schijven zien als kaarten om aan te klikken."""

    gewijzigd = Signal()

    def __init__(self, leeg_tekst: str):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        self.leeg_tekst = leeg_tekst
        self.kaarten: dict[str, KeuzeKaart] = {}
        from PySide6.QtWidgets import QButtonGroup
        self.groep = QButtonGroup(self)
        self.groep.buttonClicked.connect(lambda _: self.gewijzigd.emit())
        self.leeg = Kaart(marge=22, ruimte=16, richting="h")
        self.leeg.lay.addWidget(IcoonChip("drive-removable-media-usb", "grijs", 48))
        blok = QVBoxLayout()
        blok.setSpacing(2)
        blok.addWidget(label(leeg_tekst, "kop3"))
        blok.addWidget(label(t("BugOS ziet hem vanzelf verschijnen.", "BugOS will notice it automatically."), "klein"))
        self.leeg.lay.addLayout(blok, 1)
        self.lay.addWidget(self.leeg)

    def zet(self, items: list[tuple[str, str, str]]) -> None:
        """items: (sleutel, naam, extra uitleg)"""
        huidig = self.gekozen()
        sleutels = [i[0] for i in items]
        if sleutels == list(self.kaarten):
            return
        for k in self.kaarten.values():
            self.groep.removeButton(k)
            self.lay.removeWidget(k)
            k.deleteLater()
        self.kaarten = {}
        for sleutel, naam, extra in items:
            binnen = QWidget()
            r = QHBoxLayout(binnen)
            r.setContentsMargins(4, 2, 4, 2)
            r.setSpacing(14)
            r.addWidget(IcoonChip("drive-removable-media-usb", "turkoois", 44))
            b = QVBoxLayout()
            b.setSpacing(2)
            b.addWidget(label(naam, "kop3"))
            b.addWidget(label(extra, "klein"))
            r.addLayout(b, 1)
            k = KeuzeKaart(binnen)
            self.groep.addButton(k)
            self.lay.addWidget(k)
            self.kaarten[sleutel] = k
        self.leeg.setVisible(not items)
        if items:
            (self.kaarten.get(huidig) or next(iter(self.kaarten.values()))).setChecked(True)
        self.gewijzigd.emit()

    def gekozen(self) -> str | None:
        for sleutel, k in self.kaarten.items():
            if k.isChecked():
                return sleutel
        return None

    def setEnabled(self, aan: bool) -> None:  # noqa: N802
        for k in self.kaarten.values():
            k.setEnabled(aan)


def schijf_info(pad: Path) -> str:
    """'32 GB vrij van 64 GB' voor een schijf."""
    try:
        g = shutil.disk_usage(str(pad))
        return t(f"{g.free / 1024**3:.0f} GB vrij van {g.total / 1024**3:.0f} GB",
                 f"{g.free / 1024**3:.0f} GB free of {g.total / 1024**3:.0f} GB")
    except OSError:
        return ""


def kop_met_icoon(icoon: str, tint: str, titel_tekst: str, sub: str) -> QWidget:
    """Paginakop met een groot icoontegeltje ervoor."""
    w = QWidget()
    r = QHBoxLayout(w)
    r.setContentsMargins(0, 0, 0, 0)
    r.setSpacing(20)
    r.addWidget(IcoonChip(icoon, tint, 72), 0, Qt.AlignmentFlag.AlignTop)
    b = QVBoxLayout()
    b.setSpacing(6)
    b.addWidget(label(titel_tekst, "titel"))
    b.addWidget(label(sub, "sub"))
    r.addLayout(b, 1)
    return w


class Zoekveld(QLineEdit):
    def __init__(self, hint: str):
        super().__init__()
        self.setPlaceholderText(hint)
        self.setClearButtonEnabled(True)
        self.addAction(QIcon.fromTheme("edit-find"), QLineEdit.ActionPosition.LeadingPosition)
        self.setMinimumHeight(48)


class Zijbalk(QListWidget):
    """Navigatie aan de linkerkant (zoals bij Instellingen in Windows)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("zijbalk")
        self.setIconSize(QSize(20, 20))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def voeg_toe(self, icoon_naam: str, tekst: str, sleutel: str) -> QListWidgetItem:
        it = QListWidgetItem(icoon(icoon_naam), tekst)
        it.setData(Qt.ItemDataRole.UserRole, sleutel)
        it.setSizeHint(QSize(0, 44))
        self.addItem(it)
        return it

    def voeg_kop(self, tekst: str) -> QListWidgetItem:
        """Een klein kopje (niet aan te klikken), bijvoorbeeld 'USB-STICKS'."""
        it = QListWidgetItem(tekst.upper())
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        f = it.font()
        f.setPointSizeF(max(7.5, f.pointSizeF() * 0.78))
        f.setWeight(QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        it.setFont(f)
        it.setForeground(QColor(K["tekst3"]))
        it.setSizeHint(QSize(0, 34))
        self.addItem(it)
        return it

    def sleutel(self, rij: int) -> str:
        it = self.item(rij)
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def kies(self, sleutel: str) -> None:
        for rij in range(self.count()):
            if self.sleutel(rij) == sleutel:
                self.setCurrentRow(rij)
                return


def logo_icoon() -> QIcon:
    """Het beestje voor het huidige thema: in donker met een licht kopje (anders verdwijnt het kopje)."""
    pad = Path("/usr/share/bugos/logo-donker.svg" if DONKER else "/usr/share/bugos/logo.svg")
    return QIcon(str(pad)) if pad.exists() else QIcon.fromTheme("bugos-logo")


def merk_label(maat: int = 28, met_tekst: bool = True) -> QWidget:
    """Het BugOS-logo (lieveheersbeestje) met eventueel het woord 'BugOS'."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    logo = QLabel()
    logo.setPixmap(logo_icoon().pixmap(maat, maat))
    lay.addWidget(logo)
    if met_tekst:
        tekst = QLabel("BugOS")
        tekst.setStyleSheet(f'font-family:"{DISPLAY}";font-size:{int(maat * 0.78)}px;font-weight:600;letter-spacing:-0.4px;')
        lay.addWidget(tekst)
    lay.addStretch(1)
    return w


def achtergrond_pad(donker: bool | None = None) -> str:
    """Pad naar de BugOS-achtergrond 'Stip' (licht of donker)."""
    d = DONKER if donker is None else donker
    eigen = os.environ.get("BUGOS_ACHTERGROND")
    if eigen:
        return eigen.replace("{thema}", "images_dark" if d else "images")
    return f"/usr/share/wallpapers/bugos/contents/{'images_dark' if d else 'images'}/3840x2160.jpg"


class Held(QFrame):
    """Een brede kaart met een stukje van de BugOS-achtergrond erachter."""

    def __init__(self, hoogte: int = 150, marge: int = 28):
        super().__init__()
        self.setMinimumHeight(hoogte)
        self.beeld = QPixmap(achtergrond_pad())
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(marge, marge, marge, marge)
        self.lay.setSpacing(18)

    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        pad = QPainterPath()
        pad.addRoundedRect(r, 18, 18)
        p.setClipPath(pad)
        p.fillRect(r, QColor(K["vlak"]))
        if not self.beeld.isNull():
            # 'cover': vul de kaart, rechtsonder uitgelijnd (daar zit de stip)
            bw, bh = self.beeld.width(), self.beeld.height()
            schaal = max(r.width() / bw, r.height() / bh) * 1.25
            dw, dh = bw * schaal, bh * schaal
            p.drawPixmap(QRectF(r.right() - dw, r.bottom() - dh * 0.82, dw, dh), self.beeld, QRectF(0, 0, bw, bh))
            overgang = QLinearGradient(r.left(), 0, r.right(), 0)
            basis = QColor(K["vlak"])
            for pos, alfa in ((0.0, 0.97), (0.40, 0.9), (0.62, 0.15), (0.8, 0.0)):
                c = QColor(basis)
                c.setAlphaF(alfa)
                overgang.setColorAt(pos, c)
            p.fillRect(r, overgang)
        p.setClipping(False)
        p.setPen(QPen(QColor(K["rand"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(pad)


class Voortgang(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setRange(0, 100)
        self.setTextVisible(False)


def sectie(tekst: str) -> QLabel:
    return label(tekst.upper(), "sectie", wrap=False)


def kop(titel_tekst: str, sub: str = "") -> QWidget:
    """Paginakop: grote titel met een regel uitleg eronder."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(label(titel_tekst, "titel"))
    if sub:
        lay.addWidget(label(sub, "sub"))
    return w


def pagina(marge: tuple[int, int, int, int] = (40, 34, 40, 30), ruimte: int = 18) -> tuple[QWidget, QVBoxLayout]:
    """Een lege pagina met de juiste achtergrond en marges."""
    w = QWidget()
    w.setObjectName("pagina")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*marge)
    lay.setSpacing(ruimte)
    return w, lay


def raster(kolommen: int = 3, ruimte: int = 12) -> tuple[QWidget, QGridLayout]:
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(ruimte)
    g.setVerticalSpacing(ruimte)
    return w, g


def kader(*widgets: QWidget) -> QWidget:
    """Zet widgets onder elkaar met ruime marges (oude hulp)."""
    w, lay = pagina()
    for x in widgets:
        lay.addWidget(x)
    return w


def ronde_pixmap(pix: QPixmap, straal: int) -> QPixmap:
    """Maak de hoeken van een plaatje rond (scherp op elk scherm)."""
    dpr = pix.devicePixelRatio()
    uit = QPixmap(pix.size())
    uit.setDevicePixelRatio(dpr)
    uit.fill(Qt.GlobalColor.transparent)
    p = QPainter(uit)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    b, h = pix.width() / dpr, pix.height() / dpr
    pad = QPainterPath()
    pad.addRoundedRect(QRectF(0, 0, b, h), straal, straal)
    p.setClipPath(pad)
    p.drawPixmap(QRectF(0, 0, b, h), pix, QRectF(pix.rect()))
    p.end()
    return uit
