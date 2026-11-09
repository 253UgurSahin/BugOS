"""BugOS Bestanden: losse onderdelen van het venster.

Jip-en-Janneke: de stijl, het zoekveld, de gekleurde ruimtebalk, één regel per
USB-stick of schijf, en de gekleurde stipjes bij de ruimtebalk.
"""

from __future__ import annotations

from bugos_ui import K, Knop, Zoekveld, label, lijn_icoon, ronde_knop, schaal_css, t
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QWidget


def stijl() -> str:
    return schaal_css(f"""
QFrame#pad {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 12px; }}
QPushButton#kruimel {{ background: transparent; border: none; border-radius: 8px; padding: 6px 8px;
    font-size: 14px; color: {K['tekst2']}; }}
QPushButton#kruimel:hover {{ background: {K['knop']}; color: {K['tekst']}; }}
QPushButton#kruimel[laatste="true"] {{ color: {K['tekst']}; font-weight: 600; }}
QListView#tegels {{ background: transparent; border: none; outline: 0; }}
QWidget#computer_binnen {{ background: transparent; }}
QFrame#kaart {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; }}
QFrame#schijfrij {{ background: transparent; border-radius: 12px; }}
QFrame#schijfrij:hover {{ background: {K['knop']}; }}
QFrame#schijfrij:focus {{ border: 2px solid {K['accent']}; }}
QFrame#schijfrij[leeg="true"]:hover {{ background: transparent; }}
QPushButton#legenda {{ background: transparent; border: none; border-radius: 10px; padding: 5px 10px 5px 6px;
    text-align: left; font-size: 14px; font-weight: 400; color: {K['tekst']}; }}
QPushButton#legenda:hover {{ background: {K['knop']}; }}
QPushButton#legenda:disabled {{ color: {K['tekst2']}; }}
""")


class Zoekbalk(Zoekveld):
    """Het zoekveld bovenin: liefst 240 breed, maar het mag krimpen in een smal venster."""

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(240, super().sizeHint().height())


class RuimteBalk(QWidget):
    """Eén brede balk: elk stukje kleur is een soort bestanden; het lichte deel is nog vrij."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(16)
        self.delen: list[tuple[float, QColor]] = []

    def zet(self, delen: list[tuple[float, QColor]]) -> None:
        self.delen = delen
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        spoor = QPainterPath()
        spoor.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(spoor, QColor(K["knop"]))
        p.setClipPath(spoor)
        x = r.left()
        for deel, kleur_ in self.delen:
            breedte = r.width() * max(0.0, deel)
            if breedte < 0.5:
                continue
            p.fillRect(QRectF(x, r.top(), breedte, r.height()), kleur_)
            x += breedte
            p.fillRect(QRectF(x - 1, r.top(), 2, r.height()), QColor(K["vlak"]))  # een dun naadje
        p.end()


class SchijfRij(QFrame):
    """Eén regel in de lijst: icoontje, naam, hoeveel ruimte er vrij is, en één knop."""

    geklikt = Signal()

    def __init__(self, icoon_naam: str, naam: str, uitleg: str, gebruikt: float | None = None,
                 knop: str = "", uitwerpen: bool = False, leeg: bool = False, soort_knop: str = "gewoon"):
        super().__init__()
        self.setObjectName("schijfrij")
        if leeg:
            self.setProperty("leeg", "true")
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            # Ook met het toetsenbord: Tab erheen, Enter of spatie opent hem. Schermlezers lezen de naam voor.
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setAccessibleName(naam)
            self.setAccessibleDescription(uitleg)
        self.setMinimumHeight(60)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(lijn_icoon(icoon_naam, "tekst3" if leeg else "tekst2", 22, gekozen=None).pixmap(22, 22))
        lay.addWidget(ic)
        lay.addWidget(label(naam, "sub" if leeg else "rij", wrap=False), 1)
        lay.addWidget(label(uitleg, "klein", wrap=False))
        self.balk = None
        if gebruikt is not None:
            balk = QProgressBar()
            balk.setObjectName("dun")
            balk.setTextVisible(False)
            balk.setRange(0, 1000)
            balk.setValue(int(max(0.0, min(1.0, gebruikt)) * 1000))
            balk.setProperty("vol", "true" if gebruikt >= 0.9 else "false")
            balk.setFixedWidth(110)
            lay.addWidget(balk)
            self.balk = balk
        self.knop = None
        if knop:
            self.knop = Knop(knop, soort_knop)
            self.knop.setMinimumHeight(38)
            lay.addWidget(self.knop)
        elif uitwerpen:
            self.knop = ronde_knop("uitwerpen", t("Veilig verwijderen", "Safely remove"), klein=True)
            self.knop.setProperty("uitwerpen", True)
            lay.addWidget(self.knop)
        self.meer = None
        if not leeg:
            self.meer = ronde_knop("meer", t("Meer: naam wijzigen, repareren, leegmaken…", "More: rename, repair, erase…"),
                                   klein=True)
            lay.addWidget(self.meer)

    @property
    def uitwerp_knop(self):
        return self.knop if self.knop is not None and self.knop.property("uitwerpen") else None

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.geklikt.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            self.geklikt.emit()
            return
        super().keyPressEvent(e)


def stip_icoon(kleur_: QColor, hol: bool = False) -> QIcon:
    """Een rond gekleurd stipje voor de uitleg bij de ruimtebalk (hol = een rondje, voor 'Vrij')."""
    beeld = QPixmap(36, 36)
    beeld.fill(Qt.GlobalColor.transparent)
    p = QPainter(beeld)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if hol:
        p.setPen(QPen(QColor(K["tekst3"]), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(8, 8, 20, 20))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(kleur_)
        p.drawEllipse(QRectF(6, 6, 24, 24))
    p.end()
    beeld.setDevicePixelRatio(3)
    return QIcon(beeld)
