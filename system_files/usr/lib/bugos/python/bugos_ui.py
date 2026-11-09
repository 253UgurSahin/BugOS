"""Het BugOS-ontwerpsysteem: gedeelde bouwstenen voor alle BugOS-apps.

Jip-en-Janneke: hier staan de "legosteentjes" die elke BugOS-app gebruikt,
zodat alle apps er hetzelfde uitzien en hetzelfde praten.

  Taal        t("Nederlands", "English")
  Starten     start(...), draai(...), kde_instelling(...)
  Uiterlijk   maak_app(...)  -> kleuren (licht/donker), lettertypes, stijl
  Bouwstenen  Kop, Knop, Kaart, Tegel, IcoonChip, Schuif, SchakelRij,
              Zoekveld, Zijbalk, Banner, Chip, Voortgang, Sectie

Kleuren en maten komen uit één plek (KLEUREN hieronder), zodat alles klopt
met de huisstijl in docs/BRAND.md.

De code staat in een paar bestanden naast dit bestand, maar apps halen alles
gewoon uit bugos_ui: bugos_base (taal, starten), bugos_widgets (bouwstenen),
bugos_pages (grotere onderdelen) en bugos_shell (de schil van een app).
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bugos"


# =================================================================== taal ===
# Taal en programma's starten staan in bugos_base (zonder Qt).

from bugos_base import (  # noqa: E402, F401  (doorgeven: apps halen dit uit bugos_ui)
    _CATALOGUS, TAAL, VERTALINGEN, _catalogus, _taal, bestaat, draai, kde_instelling, start, t, zoeksleutel,
)


# ============================================================== huisstijl ===

ROOD = "#DE2F3E"

KLEUREN = {
    "licht": {
        # Kleine tekst haalt overal minstens 4,5:1 contrast (WCAG AA): tekst3, goed en let_op iets donkerder (U137).
        "achter": "#F6F5F5", "zijbalk": "#F6F5F5", "vlak": "#FFFFFF", "vlak_hover": "#FBF9F9",
        "rand": "#E6E2E2", "rand_sterk": "#D5D0D0", "tekst": "#16171C", "tekst2": "#5D6270",
        "tekst3": "#6B7080", "accent": "#DE2F3E", "accent_hover": "#C82434", "accent_tekst": "#FFFFFF",
        "accent_zacht": "#FDE9E9", "accent_lijn": "#F3B7BB", "goed": "#0E7A48", "goed_zacht": "#E3F5EC",
        "let_op": "#8F5600", "let_op_zacht": "#FFF3DC", "fout": "#D3263A", "fout_zacht": "#FDE8EA",
        "schaduw": "rgba(22,23,28,0.06)", "knop": "#F1EEEE", "knop_hover": "#E8E4E4", "schuif_uit": "#D9D4D4",
        "map_voor": "#EFC3C7", "map_achter": "#DDA2A8", "map_teken": "#8C3A43",
    },
    "donker": {
        "achter": "#111216", "zijbalk": "#111216", "vlak": "#1C1E24", "vlak_hover": "#22252C",
        "rand": "#2B2E36", "rand_sterk": "#3A3E48", "tekst": "#EDEEF1", "tekst2": "#A3A8B4",
        "tekst3": "#7C828E", "accent": "#EA3B4B", "accent_hover": "#F25262", "accent_tekst": "#FFFFFF",
        "accent_zacht": "#3A1C22", "accent_lijn": "#6A2A33", "goed": "#3FD17F", "goed_zacht": "#13291D",
        "let_op": "#F2B544", "let_op_zacht": "#2F2612", "fout": "#FF6B70", "fout_zacht": "#36181C",
        "schaduw": "rgba(0,0,0,0.35)", "knop": "#262930", "knop_hover": "#2F333B", "schuif_uit": "#3A3E48",
        "map_voor": "#67404A", "map_achter": "#7C4F59", "map_teken": "#F5DCE0",
    },
}

# Maten: één schaal voor het hele systeem (eigen apps, menu's, KDE-stijl, Plasma, vensterbalk).
# tools/design/tokens.py leest deze, dus de KDE- en Plasma-stijl gebruiken precies dezelfde getallen.
MATEN = {
    "knop": 12,          # hoeken van knoppen, invoervelden, lijstregels, menu's, tooltips
    "kaart": 16,         # hoeken van kaarten, tegels, groepen
    "groot": 22,         # hoeken van pop-ups, panelen en dialogen
    "stappen": (4, 8, 12, 16, 24, 32, 48),
    "lijn": 2,           # lijndikte van de pictogrammen op het 24-raster
    "schuif_spoor": 8,   # hoogte van het spoor van een schuif
    "schuif_knop": 22,   # doorsnede van het bolletje van een schuif
}

# Kleuren voor de pictogramtegeltjes (zoals bij een telefoon).
TINTEN = {
    "rood": "#E5383F", "oranje": "#F2711C", "geel": "#E8A317", "groen": "#1FA35B", "blauw": "#2F7BF5",
    "paars": "#8B5CF6", "roze": "#E2457A", "turkoois": "#0EA5A4", "grijs": "#6B7280",
}

DISPLAY = "Funnel Display"
K: dict[str, str] = dict(KLEUREN["licht"])  # actieve kleuren (wordt gezet door maak_app)
DONKER = False
# Hoeveel groter de letters zijn dan gewoon (KDE: 10 punten gewoon, 12 bij 'Grote letters'). maak_app zet hem,
# en alle letters van de BugOS-apps (die in pixels staan) groeien mee (U067).
SCHAAL = 1.0


def px(n: float) -> int:
    """Een lettergrootte in pixels, meegegroeid met 'Grote letters'."""
    return max(1, round(n * SCHAAL))


def letter_schaal(f: QFont) -> float:
    """De lettergrootte van KDE (10 punten is gewoon, 12 bij 'Grote letters') als factor, tussen 1 en 2."""
    punten = f.pointSizeF()
    # Tot 1,5 keer: de tegels en vaste vakjes groeien mee, maar daarboven past het ontwerp niet meer (U085).
    return min(1.5, max(1.0, punten / 10)) if punten > 0 else 1.0


def schaal_css(css: str) -> str:
    """Zet elke 'font-size: 14px' in een stijlblad om naar de grootte die bij SCHAAL hoort."""
    if SCHAAL == 1.0:
        return css
    return re.sub(r"font-size:\s*(\d+(?:\.\d+)?)px", lambda m: f"font-size: {px(float(m.group(1)))}px", css)


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
    return schaal_css(f"""
* {{ outline: 0; }}
QWidget {{ color: {k['tekst']}; font-size: 14px; }}
QWidget#venster, QWidget#pagina, QScrollArea, QScrollArea > QWidget > QWidget#pagina {{ background: {k['achter']}; }}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
QLabel[rol="titel"] {{ font-family: "{DISPLAY}"; font-size: 30px; font-weight: 600; letter-spacing: -0.5px; }}
QLabel[rol="groot"] {{ font-family: "{DISPLAY}"; font-size: 40px; font-weight: 600; letter-spacing: -0.8px; }}
QLabel[rol="kop2"] {{ font-family: "{DISPLAY}"; font-size: 19px; font-weight: 600; }}
QLabel[rol="kop3"] {{ font-size: 15px; font-weight: 600; }}
QLabel[rol="rij"] {{ font-size: 15px; font-weight: 500; }}
QLabel[rol="sub"] {{ color: {k['tekst2']}; font-size: 15px; }}
QLabel[rol="klein"] {{ color: {k['tekst2']}; font-size: 13px; }}
QLabel[rol="sectie"] {{ color: {k['tekst2']}; font-size: 13px; font-weight: 600; }}
QLabel[rol="appnaam"] {{ font-family: "{DISPLAY}"; font-size: 20px; font-weight: 600; letter-spacing: -0.3px; }}

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
QPushButton[soort="rand"]:focus {{ border: 2px solid {k['accent']}; padding: 9px 17px; }}
QPushButton[groot="true"] {{ padding: 13px 24px; font-size: 15px; border-radius: 12px; }}
QPushButton[groot="true"]:focus {{ padding: 12px 23px; }}

QPushButton#tegel {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 16px; padding: 0; text-align: left; }}
QPushButton#tegel:hover {{ background: {k['vlak_hover']}; border: 1px solid {k['rand_sterk']}; }}
QPushButton#tegel:focus {{ border: 2px solid {k['accent']}; }}
QPushButton#keuze {{ background: {k['vlak']}; border: 2px solid {k['rand']}; border-radius: 16px; padding: 0; text-align: left; }}
QPushButton#keuze:hover {{ border: 2px solid {k['rand_sterk']}; }}
QPushButton#keuze:focus {{ border: 2px dashed {k['accent']}; }}
QPushButton#keuze:checked {{ border: 2px solid {k['accent']}; background: {k['vlak']}; }}

QLineEdit {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px; padding: 11px 14px;
  font-size: 15px; selection-background-color: {k['accent']}; }}
QLineEdit:focus {{ border: 2px solid {k['accent']}; padding: 10px 13px; }}

QComboBox {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px; padding: 10px 14px; font-size: 14px; }}
QComboBox:focus {{ border: 2px solid {k['accent']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px;
  selection-background-color: {k['accent_zacht']}; selection-color: {k['tekst']}; padding: 4px; }}

QListWidget#zijbalk {{ background: transparent; border: none; outline: 0; font-size: 14px; }}
QListWidget#zijbalk::item {{ padding: 10px 12px; border-radius: 12px; margin: 1px 0; color: {k['tekst']}; }}
QListWidget#zijbalk::item:hover {{ background: {k['knop']}; }}
QListWidget#zijbalk::item:selected {{ background: {k['accent_zacht']}; color: {k['accent']}; font-weight: 600; }}
QWidget#zijkant {{ background: {k['zijbalk']}; border: none; }}

QProgressBar {{ background: {k['knop']}; border: none; border-radius: 6px; min-height: 12px; max-height: 12px;
  color: transparent; text-align: center; }}
QProgressBar::chunk {{ border-radius: 6px; background: {k['accent']}; }}
QProgressBar#dun {{ border-radius: 3px; min-height: 6px; max-height: 6px; }}
QProgressBar#dun::chunk {{ background: {k['tekst3']}; border-radius: 3px; }}
QProgressBar#dun[vol="true"]::chunk {{ background: {k['let_op']}; }}

QFrame#rij {{ background: transparent; border-radius: 12px; }}
QFrame#rij[klikbaar="true"]:hover {{ background: {k['knop']}; }}
QFrame#rij[klikbaar="true"]:focus {{ background: {k['knop']}; border: 2px solid {k['accent']}; }}
QPushButton#rond {{ min-width: 42px; max-width: 42px; min-height: 42px; max-height: 42px; border-radius: 21px;
  background: {k['knop']}; border: none; padding: 0; }}
QPushButton#rond:hover {{ background: {k['knop_hover']}; }}
QPushButton#rond:focus {{ border: 2px solid {k['accent']}; }}
QPushButton#rond:disabled {{ background: transparent; }}
QPushButton#rond_klein {{ min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; border-radius: 18px;
  background: transparent; border: none; padding: 0; }}
QPushButton#rond_klein:hover {{ background: {k['knop_hover']}; }}
QPushButton#rond_klein:focus {{ border: 2px solid {k['accent']}; }}
QFrame#melding {{ background: {k['knop']}; border-radius: 12px; }}
QFrame#melding[soort="goed"] {{ background: {k['goed_zacht']}; }}
QFrame#melding[soort="fout"] {{ background: {k['fout_zacht']}; }}
QFrame#melding[soort="let_op"] {{ background: {k['let_op_zacht']}; }}
QFrame#actiebalk {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 22px; }}
QPushButton#balkknop {{ background: transparent; border: none; border-radius: 12px; padding: 9px 14px;
  font-size: 14px; font-weight: 600; color: {k['tekst']}; }}
QPushButton#balkknop:hover {{ background: {k['knop']}; }}
QPushButton#balkknop:focus {{ background: {k['knop']}; border: 2px solid {k['accent']}; padding: 7px 12px; }}
QFrame#streep {{ background: {k['rand']}; min-width: 1px; max-width: 1px; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {k['rand_sterk']}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {k['tekst3']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; width: 0; background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {k['rand_sterk']}; border-radius: 3px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: {k['tekst3']}; }}

QMenu {{ background: {k['vlak']}; border: 1px solid {k['rand']}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 9px 22px 9px 12px; border-radius: 8px; color: {k['tekst']}; }}
QMenu::item:selected {{ background: {k['knop']}; }}
QMenu::item:disabled {{ color: {k['tekst3']}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::separator {{ height: 1px; background: {k['rand']}; margin: 6px 8px; }}
QToolTip {{ background: {k['tekst']}; color: {k['achter']}; border: none; border-radius: 8px; padding: 6px 10px; }}
QCheckBox, QRadioButton {{ spacing: 10px; font-size: 15px; }}
QSlider {{ min-height: 28px; }}
QSlider::groove:horizontal {{ height: 8px; border-radius: 4px; background: {k['schuif_uit']}; }}
QSlider::sub-page:horizontal {{ height: 8px; border-radius: 4px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF5C50, stop:1 {k['accent']}); }}
QSlider::handle:horizontal {{ width: 22px; height: 22px; margin: -7px 0; border-radius: 11px; background: #FFFFFF;
  border: 1px solid {k['rand_sterk']}; }}
QSlider::groove:horizontal:disabled, QSlider::sub-page:horizontal:disabled {{ background: {k['knop']}; }}
QSlider::handle:horizontal:focus {{ border: 3px solid {k['accent']}; }}
""")


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


def _een_naam(naam: str) -> str:
    """Het adres waarop een open programma luistert. In de eigen runtime-map (/run/user/<uid>, alleen voor jou):
    een naam in de gedeelde /tmp kan een ander account op deze computer bezetten (U219)."""
    map_ = os.environ.get("XDG_RUNTIME_DIR", "")
    if map_ and os.path.isdir(map_) and os.stat(map_).st_uid == os.getuid():
        return os.path.join(map_, f"bugos-{naam}")
    return f"bugos-{naam}-{os.getuid()}"


def al_open(naam: str, args: Sequence[str]) -> bool:
    """Is dit programma al open (voor deze gebruiker)? Dan krijgt dat venster de opdracht (bijv. de pagina) en
    komt het naar voren; geef True terug, dan stopt deze tweede start (U208).
    Alleen als het open venster 'ok' terugzegt: hangt het, of is het net aan het afsluiten, dan gewoon een
    nieuw venster (U220)."""
    if os.environ.get("BUGOS_MEERDERE"):   # voor tests: elke start een eigen venster
        return False
    from PySide6.QtNetwork import QLocalSocket
    sok = QLocalSocket()
    sok.connectToServer(_een_naam(naam))
    if not sok.waitForConnected(300):
        return False
    import json as _json
    # Het startbewijs van Plasma meegeven: zonder dat mag een Wayland-venster niet naar voren komen (U218).
    bericht = {"args": list(args), "token": os.environ.get("XDG_ACTIVATION_TOKEN", "")}
    sok.write(_json.dumps(bericht).encode() + b"\n")
    sok.flush()
    sok.waitForBytesWritten(500)
    antwoord = b""
    while b"ok" not in antwoord and sok.waitForReadyRead(2000):
        antwoord += bytes(sok.readAll())
    sok.disconnectFromServer()
    return b"ok" in antwoord


def _naar_voren(venster: QWidget, token: str) -> None:
    """Een open venster weer laten zien zoals het was: gemaximaliseerd blijft gemaximaliseerd, alleen
    geminimaliseerd gaat eraf (U217)."""
    if token:
        os.environ["XDG_ACTIVATION_TOKEN"] = token   # Qt gebruikt dit bij activateWindow (Wayland) (U218)
    venster.setWindowState(venster.windowState() & ~Qt.WindowState.WindowMinimized)
    venster.show()
    venster.raise_()
    venster.activateWindow()


def luister(naam: str, venster: QWidget) -> None:
    """Een tweede start van dit programma brengt dit venster naar voren (en geeft de opdracht door aan
    venster.tweede_start(args), als het venster dat kent) (U208)."""
    if os.environ.get("BUGOS_MEERDERE"):
        return
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(venster)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(_een_naam(naam))   # een oude, achtergebleven naam (na een crash)
    if not server.listen(_een_naam(naam)):
        return

    def nieuw() -> None:
        sok = server.nextPendingConnection()
        if sok is None:
            return
        buffer = bytearray()

        def lees() -> None:
            import json as _json
            buffer.extend(bytes(sok.readAll()))
            if b"\n" not in buffer:
                return   # nog niet alles binnen
            try:
                bericht = _json.loads(bytes(buffer).split(b"\n", 1)[0].decode() or "{}")
            except ValueError:
                bericht = {}
            if isinstance(bericht, list):   # het oude formaat
                bericht = {"args": bericht}
            if not isinstance(bericht, dict):
                bericht = {}
            args = [str(a) for a in bericht.get("args") or []]
            if hasattr(venster, "tweede_start"):
                try:
                    venster.tweede_start(args)
                except Exception:  # noqa: BLE001  een rare opdracht mag het open venster niet laten vallen
                    pass
            # Je opent het opnieuw: dan niet meer vanzelf dichtgaan als een klus klaar is (U221).
            for vlag in ("sluit_na", "sluit_na_update"):
                if getattr(venster, vlag, False):
                    setattr(venster, vlag, False)
            _naar_voren(venster, str(bericht.get("token") or ""))
            sok.write(b"ok")
            sok.flush()

        sok.readyRead.connect(lees)
        sok.disconnected.connect(sok.deleteLater)

    server.newConnection.connect(nieuw)
    venster._een_server = server


def maak_app(naam: str, bureaublad_bestand: str, args: Sequence[str], een_keer: bool = False) -> QApplication:
    """Maak de QApplication met de BugOS-stijl (licht of donker, vanzelf).
    een_keer: is het programma al open, dan komt dat venster naar voren en stopt deze start (U208)."""
    global DONKER, SCHAAL
    app = QApplication(list(args))
    if een_keer:
        app.setProperty("bugos_een_keer", naam)
        if al_open(naam, list(args)[1:]):
            raise SystemExit(0)
    app.setApplicationName(naam)
    app.setDesktopFileName(bureaublad_bestand)
    # Het eigen pictogram van de app (zelfde naam als het .desktop-bestand), zodat Alt+Tab en de taakbalk
    # hetzelfde tegeltje tonen als het startmenu.
    app.setWindowIcon(QIcon.fromTheme(bureaublad_bestand.removesuffix(".desktop"),
                                      QIcon.fromTheme("bugos-logo", QIcon("/usr/share/bugos/logo.svg"))))
    _laad_lettertypes()
    DONKER = _kies_thema(app)
    K.clear()
    K.update(KLEUREN["donker" if DONKER else "licht"])
    app.setStyle("Fusion")
    app.setPalette(_palet(K))
    # Inter is de BugOS-letter; gebruik hem als het systeem een algemene letter geeft.
    f = app.font()
    SCHAAL = letter_schaal(f)
    if f.family() in ("Sans Serif", "DejaVu Sans", "Noto Sans", "Cantarell", "") and \
            "Inter" in QFontDatabase.families():
        f.setFamily("Inter")
    f.setPixelSize(px(14))
    app.setFont(f)
    app.setStyleSheet(_stijlblad(K))
    return app


def uitvoeren(app: QApplication, venster: QWidget) -> int:
    """Toon het venster, wacht tot de gebruiker klaar is en ruim netjes op.

    Het venster moet weg zijn vóórdat de app verdwijnt, anders crasht Qt bij
    het afsluiten. Geef daarom het venster direct mee: uitvoeren(app, Venster())."""
    if app.property("bugos_een_keer"):
        luister(str(app.property("bugos_een_keer")), venster)
    venster.show()
    code = app.exec()
    server = getattr(venster, "_een_server", None)
    if server is not None:
        server.close()   # wie nu start, krijgt een eigen venster in plaats van niets (U220)
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
    "uitroep": '<path d="M12 3.8 2.8 19.5h18.4z"/><path d="M12 9.5v4.5M12 16.8v.3"/>',
    "zoek": '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    "laptop": '<rect x="4.5" y="5" width="15" height="10.5" rx="1.5"/><path d="M2.5 19h19"/>',
    "kaart": '<path d="M9 3.5h7.5A1.5 1.5 0 0 1 18 5v14a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V6.5z"/>'
             '<path d="M10 7V9.5M13 7V9.5M16 7V9.5"/>',
    "cd": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.5"/>',
    "slot": '<rect x="5.5" y="10.5" width="13" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
    "meer": '<circle cx="5.5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18.5" cy="12" r="1.2"/>',
    "apps": '<rect x="4" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8"/>'
            '<rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.8"/>',
    "grafiek": '<path d="M3 12.5h3.5l2.5-6 4 11.5 2.8-7.5 1.7 2H21"/>',
    "aan": '<path d="M12 3.5v8"/><path d="M6.6 6.8a7.5 7.5 0 1 0 10.8 0"/>',
    "onder": '<path d="m6.5 9.5 5.5 5.5 5.5-5.5"/>',
    "batterij": '<rect x="3" y="7" width="16" height="10" rx="2.2"/><path d="M21.5 10.5v3M6.5 10.5v3"/>',
    "palet": '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.5 0 1.9-1 1.3-2.1-.6-1.1.2-2.4 1.6-2.4H17a3.5 3.5 0 0 0 3.5-3.5'
             'C20.5 7.3 16.7 3.5 12 3.5z"/><circle cx="7.8" cy="11" r="1"/><circle cx="11.5" cy="7.6" r="1"/>'
             '<circle cx="15.8" cy="9.4" r="1"/>',
    "zon": '<circle cx="12" cy="12" r="3.8"/><path d="M12 2.8v2.2M12 19v2.2M2.8 12H5M19 12h2.2M5.5 5.5l1.6 1.6'
           'M16.9 16.9l1.6 1.6M5.5 18.5l1.6-1.6M16.9 7.1l1.6-1.6"/>',
    "maan": '<path d="M19.5 14.6A8 8 0 1 1 9.4 4.5a6.4 6.4 0 0 0 10.1 10.1z"/>',
    "muis": '<rect x="7" y="3.5" width="10" height="17" rx="5"/><path d="M12 3.5v5M7 10.5h10"/>',
    "bel": '<path d="M6.5 16.5v-5.5a5.5 5.5 0 0 1 11 0v5.5l1.5 2h-14z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "persoon": '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
    "toetsenbord": '<rect x="2.5" y="6.5" width="19" height="11" rx="2"/><path d="M6 10h.01M9.5 10h.01M13 10h.01'
                   'M16.5 10h.01M6 13.5h.01M9.5 13.5h3.5M16.5 13.5h.01"/>',
    "letter": '<path d="M5 19 12 4.5 19 19M7.6 13.5h8.8"/>',
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


# ===================================================== de rest van bugos_ui ===
# Pas hier, onderaan: deze bestanden gebruiken zelf de kleuren en iconen hierboven.

from bugos_widgets import (  # noqa: E402, F401  (doorgeven: apps halen dit uit bugos_ui)
    Banner, Chip, Groep, IcoonChip, Kaart, KeuzeKaart, Knop, SchakelRij, Schakelaar, Schuif, Tegel, gewone_knop,
    hoofdknop, label, lettertype, lijn, titel, uitleg, wit_icoon,
)
from bugos_pages import (  # noqa: E402, F401
    Held, SchijfKiezer, Voortgang, Zijbalk, Zoekveld, achtergrond_pad, kader, kop, kop_met_icoon, logo_icoon,
    merk_label, pagina, raster, ronde_pixmap, schijf_info, sectie,
)
from bugos_shell import (  # noqa: E402, F401
    LEESBREEDTE, ZIJBALK_BREEDTE, ActieBalk, Melding, Pagina, Rij, Venster, app_kop, leeg_groep, ronde_knop,
)
