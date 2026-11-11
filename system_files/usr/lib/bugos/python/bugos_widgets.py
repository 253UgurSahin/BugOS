"""De kleine bouwstenen van bugos_ui: teksten, knoppen, kaarten, tegeltjes, schuifjes en tegels.

Apps halen ze uit bugos_ui (from bugos_ui import Knop, Kaart ...); dit bestand hoort daarbij.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Property, QEasingCurve, QEvent, QObject, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

import bugos_ui  # DONKER via de module lezen: maak_app zet hem pas als de app start
from bugos_ui import K, TINTEN, lijn_icoon, lijn_pixmap, zoeksleutel


# ============================================================= bouwstenen ===

KNOP_HOOGTE = 36      # een gewone knop (Windows 11: 32)
KNOP_GROOT = 44       # de grote hoofdknop van Welkom, Back-up en Overstap
SCHUIF_MAAT = (44, 24)  # het aan/uit-schuifje (Windows 11: 40 x 20)

def lettertype(punten: int, vet: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(punten)
    f.setBold(vet)
    return f


def label(tekst: str, rol: str = "", wrap: bool = True, kopieerbaar: bool = False, rijk: bool = False) -> QLabel:
    lab = QLabel(tekst)
    # Gewone tekst: een naam van buiten (een wifi-netwerk '<h1>GRATIS</h1>', een bestandsnaam) wordt geen opmaak
    # (U210). Alleen waar BugOS zelf opmaak gebruikt: rijk=True.
    lab.setTextFormat(Qt.TextFormat.RichText if rijk else Qt.TextFormat.PlainText)
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


class GeenDubbel:
    """Een dubbelklik is één klik: de tweede klik doet niets. Anders sloeg 'Volgende' in Welkom een pagina over, ging
    een schakelaar aan én uit, of startte 'Openen' een app twee keer (U530). (Zoals Rij, U332.)"""

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        e.accept()   # niet opnieuw indrukken: dan volgt er bij loslaten ook geen tweede 'clicked'


class Knop(GeenDubbel, QPushButton):
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
        # Rustig en compact zoals Windows 11, maar ruim boven de 24 px die je minstens moet kunnen raken. Met
        # 'Grote letters' groeit de knop mee (px), anders zat de grote letter klem.
        self.setMinimumHeight(bugos_ui.px(KNOP_GROOT if groot else KNOP_HOOGTE))


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
                achter.setAlphaF(0.22 if bugos_ui.DONKER else 0.13)
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
            "accent": (K["accent_gekozen"], K["accent_zacht"]), "goed": (K["goed"], K["goed_zacht"]),
            "let_op": (K["let_op"], K["let_op_zacht"]), "fout": (K["fout"], K["fout_zacht"]),
            "grijs": (K["tekst2"], K["knop"]),
        }.get(soort, (K["accent_gekozen"], K["accent_zacht"]))
        self.setStyleSheet(f"background:{achter};color:{voor};border-radius:10px;padding:3px 10px;"
                           f"font-size:{bugos_ui.px(12)}px;font-weight:600;")
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
            "bezig": (K["accent_gekozen"], K["accent_zacht"], "view-refresh"),   # 4,5:1 (U282)
        }.get(soort, (K["tekst"], K["knop"], "dialog-information"))
        self.setStyleSheet(f"QFrame{{background:{achter};border-radius:12px;}} QLabel{{color:{voor};font-size:{bugos_ui.px(14)}px;}}")
        self.teken.setPixmap(QIcon.fromTheme(icoon).pixmap(20, 20))
        self.tekst.setText(tekst)
        self.setVisible(bool(tekst))
        # De schermlezer zegt het ook ('VLC is verwijderd', 'lukte niet'): anders bleef Orca stil (U482).
        self.setAccessibleName(tekst)
        if tekst and soort != "bezig":
            try:
                from PySide6.QtGui import QAccessible, QAccessibleEvent
                QAccessible.updateAccessibility(QAccessibleEvent(self.tekst, QAccessible.Event.Alert))
            except (ImportError, AttributeError, RuntimeError):
                pass


class Schuif(GeenDubbel, QAbstractButton):
    """Een echte aan/uit-schuifschakelaar (met een vloeiende beweging)."""

    def __init__(self, aan: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(aan)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(*SCHUIF_MAAT)
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

    def showEvent(self, e) -> None:  # noqa: N802
        # Een schermlezer moet weten wát je aan- of uitzet. Heeft niemand een naam gegeven, neem dan
        # de eerste tekst die ernaast staat (de titel van de regel of het tegeltje).
        ouder = self.parentWidget()
        if not self.accessibleName() and ouder is not None:
            naast = ouder.findChildren(QLabel, "", Qt.FindChildOption.FindDirectChildrenOnly)
            tekst = next((x.text() for x in naast if x.text()), "")
            if tekst:
                self.setAccessibleName(tekst)
        super().showEvent(e)

    def zet_stil(self, aan: bool) -> None:
        """Zet de stand zonder signaal (bijv. bij het inlezen)."""
        self._anim.stop()   # een lopende schuif-animatie zou anders de oude stand tekenen (U184)
        self.blockSignals(True)
        self.setChecked(aan)
        self.blockSignals(False)
        self._set(1.0 if aan else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(*SCHUIF_MAAT)

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


class _LijnWacht(QObject):
    """Ziet een regel in een Groep verschijnen of verdwijnen, en zet dan de lijntjes goed."""

    def eventFilter(self, obj, e):  # noqa: N802
        if e.type() in (QEvent.Type.ShowToParent, QEvent.Type.HideToParent):
            groep = obj.parentWidget()
            if isinstance(groep, Groep):
                groep.lijnen_bijwerken()
        return False


_WACHT: _LijnWacht | None = None


class Groep(Kaart):
    """Een kaart met regels onder elkaar, gescheiden door dunne lijntjes. Een lijntje staat er alleen tussen twee
    regels die je ziet: een verborgen regel (bijv. 'Kabel' zonder kabel) laat geen lege strook met een streep achter."""

    def __init__(self):
        super().__init__(marge=0, ruimte=0)

    def voeg(self, w: QWidget) -> QWidget:
        global _WACHT
        if _WACHT is None:
            _WACHT = _LijnWacht()
        if self.lay.count():
            self.lay.addWidget(lijn())
        self.lay.addWidget(w)
        w.installEventFilter(_WACHT)
        self.lijnen_bijwerken()
        return w

    def lijnen_bijwerken(self) -> None:
        eerder = False          # staat er boven dit punt al een zichtbare regel?
        wachtend = None         # het laatste lijntje sinds die regel
        for i in range(self.lay.count()):
            w = self.lay.itemAt(i).widget()
            if w is None:
                continue
            if w.objectName() == "lijn":
                w.setVisible(False)
                wachtend = w
                continue
            if w.isHidden():
                continue
            if eerder and wachtend is not None:
                wachtend.setVisible(True)
            eerder, wachtend = True, None


class Tegel(GeenDubbel, QPushButton):
    """Een grote klikbare tegel: pictogram (op een gekleurd tegeltje), naam en uitleg."""

    def __init__(self, icoon: str, naam: str, tekst: str, actie: Callable[[], None],
                 zoekwoorden: str = "", tint: str = "rood"):
        super().__init__()
        self.setObjectName("tegel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Vaste hoogte: ruimte voor de naam en twee regels uitleg (niets wordt afgeknipt).
        self.setFixedHeight(bugos_ui.px(102))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.zoektekst = zoeksleutel(f"{naam} {tekst} {zoekwoorden}")
        self.setAccessibleName(naam)
        self.setAccessibleDescription(tekst)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)
        chip = IcoonChip(icoon, "neutraal", 44, vol=False)
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
        return all(woord in self.zoektekst for woord in zoeksleutel(zoek).split())


class KeuzeKaart(GeenDubbel, QPushButton):
    """Een grote kaart die je kunt aanklikken om iets te kiezen."""

    def __init__(self, inhoud: QWidget):
        super().__init__()
        self.setObjectName("keuze")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Kaarten naast elkaar worden even hoog (de hoogste wint).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        lay.addWidget(inhoud)
        inhoud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Een schermlezer ziet alleen de knop, niet de tekst erin: geef hem de eerste tekst als naam
        # (bijv. "Donker" of de naam van de USB-stick) en de rest als uitleg.
        teksten = [x.text() for x in inhoud.findChildren(QLabel) if x.text()]
        if teksten:
            self.setAccessibleName(teksten[0])
            self.setAccessibleDescription(" · ".join(teksten[1:]))

    def resizeEvent(self, e) -> None:  # noqa: N802
        """De hoogte volgt de breedte: een uitleg van twee of drie regels past er altijd in (ook bij 150 %).
        (Een QPushButton geeft de hoogte van een afgebroken tekst niet door aan zijn ouder.)"""
        super().resizeEvent(e)
        lay = self.layout()
        if lay is None or not lay.hasHeightForWidth():
            return
        if not hasattr(self, "_eigen_min"):
            self._eigen_min = self.minimumHeight()          # bijv. 112 uit keuze_kaart()
            lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
        nodig = max(self._eigen_min, lay.totalHeightForWidth(self.width()))
        if nodig != self.minimumHeight():
            self.setMinimumHeight(nodig)
