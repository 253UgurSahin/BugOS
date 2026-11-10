"""Grotere onderdelen van bugos_ui: schijfkiezer, zoekveld, zijbalk, logo, held en hulpjes voor een pagina.

Apps halen ze uit bugos_ui (from bugos_ui import Zijbalk, pagina ...); dit bestand hoort daarbij.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QScrollArea,
    QVBoxLayout, QWidget,
)

import bugos_ui  # DONKER via de module lezen: maak_app zet hem pas als de app start
from bugos_ui import DISPLAY, K, icoon, lijn_icoon, t
from bugos_widgets import IcoonChip, Kaart, KeuzeKaart, label


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
        self.groep.buttonClicked.connect(lambda _: (setattr(self, "_kwijt", False), self.gewijzigd.emit()))
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
        # Niet alleen de sleutels vergelijken: ook de tekst (bijv. 'heeft al een back-up', de vrije ruimte) (U080).
        if [tuple(i) for i in items] == getattr(self, "_items", None):
            return
        # Zelfde schijven, alleen een andere tekst (bijv. de vrije ruimte): de tekst bijwerken, niet alles opnieuw
        # bouwen, anders raakt wie met het toetsenbord of een schermlezer op een kaart staat de focus kwijt (U102).
        if [i[0] for i in items] == list(self.kaarten) and all(hasattr(k, "_teksten") for k in self.kaarten.values()):
            for sleutel, naam, extra in items:
                k = self.kaarten[sleutel]
                k._teksten[0].setText(naam)
                k._teksten[1].setText(extra)
                k.setAccessibleName(naam)
                k.setAccessibleDescription(extra)
            self._items = [tuple(i) for i in items]
            return
        self._items = [tuple(i) for i in items]
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
            naam_l, extra_l = label(naam, "kop3"), label(extra, "klein")
            b.addWidget(naam_l)
            b.addWidget(extra_l)
            r.addLayout(b, 1)
            k = KeuzeKaart(binnen)
            k._teksten = (naam_l, extra_l)
            k.setEnabled(getattr(self, "_aan", True))   # tijdens een klus blijven nieuwe kaarten ook op slot
            self.groep.addButton(k)
            self.lay.addWidget(k)
            self.kaarten[sleutel] = k
        self.leeg.setVisible(not items)
        if items:
            if huidig in self.kaarten:
                self.kaarten[huidig].setChecked(True)
            elif huidig is None and not getattr(self, "_kwijt", False):   # ook niet als er nog maar één over is (U534)
                next(iter(self.kaarten.values())).setChecked(True)
            else:
                self._kwijt = True   # ook bij de volgende verversing niet vanzelf een andere kiezen
            # De gekozen schijf is eruit en er zijn er nog meer: niet stil een andere kiezen (dan ging de back-up naar
            # een schijf die je niet koos); je kiest zelf opnieuw (U533).
        self.gewijzigd.emit()

    def gekozen(self) -> str | None:
        for sleutel, k in self.kaarten.items():
            if k.isChecked():
                return sleutel
        return None

    def setEnabled(self, aan: bool) -> None:  # noqa: N802
        self._aan = aan
        for k in self.kaarten.values():
            k.setEnabled(aan)


def schijf_info(pad: Path) -> str:
    """'32 GB vrij van 64 GB' voor een schijf."""
    try:
        g = shutil.disk_usage(str(pad))
        # Zoals Bestanden (1000, met een komma): niet '0 GB vrij' op een kleine stick met 450 MB vrij (U185).
        from bugos_drives import mooie_maat
        return t(f"{mooie_maat(g.free)} vrij van {mooie_maat(g.total)}", f"{mooie_maat(g.free)} free of {mooie_maat(g.total)}")
    except OSError:
        return ""


def kop_met_icoon(icoon: str, tint: str, titel_tekst: str, sub: str) -> QWidget:
    """Paginakop met een rustig icoontegeltje ervoor (de tint doet niet meer mee: overal dezelfde stijl)."""
    del tint
    w = QWidget()
    r = QHBoxLayout(w)
    r.setContentsMargins(0, 0, 0, 0)
    r.setSpacing(20)
    r.addWidget(IcoonChip(icoon, "neutraal", 64, vol=False), 0, Qt.AlignmentFlag.AlignTop)
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
        self.addAction(lijn_icoon("zoek", "tekst3", 18, gekozen=None), QLineEdit.ActionPosition.LeadingPosition)
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
        it = QListWidgetItem(tekst)
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        f = it.font()
        f.setPointSizeF(max(8.0, f.pointSizeF() * 0.9))
        f.setWeight(QFont.Weight.DemiBold)
        it.setFont(f)
        it.setForeground(QColor(K["tekst3"]))
        it.setSizeHint(QSize(0, 36))
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
    pad = Path("/usr/share/bugos/logo-dark.svg" if bugos_ui.DONKER else "/usr/share/bugos/logo.svg")
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
    d = bugos_ui.DONKER if donker is None else donker
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
    """Een klein kopje boven een kaart, in een gewone zin (geen hoofdletters)."""
    lab = label(tekst, "sectie", wrap=False)
    lab.setContentsMargins(4, 6, 0, 0)
    return lab


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


def schuifbaar(w: QWidget) -> QScrollArea:
    """Zet een pagina in een schuifvlak: op een klein scherm (of met grote letters) kun je naar de knoppen onderaan
    schuiven, in plaats van dat ze buiten het venster vallen (U401)."""
    vlak = QScrollArea()
    vlak.setFrameShape(QFrame.Shape.NoFrame)
    vlak.setWidgetResizable(True)
    vlak.viewport().setAutoFillBackground(False)
    # Geen eigen Tab-stop (een naamloos 'schuifvlak' voor de schermlezer); naar een knop onderaan tabben schuift
    # hem toch in beeld (U481).
    vlak.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    vlak.setWidget(w)
    return vlak


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
