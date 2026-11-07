"""Het zijpaneel van BugOS Welkom: links de donkere achtergrond, het logo en de stappen.

Hoort bij /usr/bin/bugos-welcome.
"""

from __future__ import annotations

from bugos_ui import DISPLAY, K, achtergrond_pad, t
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


# ============================================================ zijpaneel ===

class Zijpaneel(QWidget):
    """Links: de BugOS-achtergrond, het logo en de stappen."""

    def __init__(self, stappen: list[str]):
        super().__init__()
        self.stappen = stappen
        self.huidig = 0
        self.beeld = QPixmap(achtergrond_pad(donker=True))
        # De zijbalk is altijd donker: het logo met de lichte kop.
        self.logo = QIcon("/usr/share/bugos/logo-dark.svg")
        self.setFixedWidth(330)

    def zet(self, i: int) -> None:
        self.huidig = i
        self.update()

    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        p.fillRect(r, QColor("#0E0F13"))
        if not self.beeld.isNull():
            bw, bh = self.beeld.width(), self.beeld.height()
            schaal = r.height() / bh * 1.15
            dw, dh = bw * schaal, bh * schaal
            p.drawPixmap(QRectF(r.right() - dw * 0.62, r.bottom() - dh, dw, dh), self.beeld, QRectF(0, 0, bw, bh))
            donker = QLinearGradient(0, 0, 0, r.height())
            donker.setColorAt(0, QColor(14, 15, 19, 235))
            donker.setColorAt(0.55, QColor(14, 15, 19, 150))
            donker.setColorAt(1, QColor(14, 15, 19, 40))
            p.fillRect(r, donker)

        # logo + woord
        self.logo.paint(p, 32, 34, 34, 34)
        f = p.font()
        f.setFamily(DISPLAY)
        f.setPixelSize(26)
        f.setWeight(f.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(76, 32, 220, 40), Qt.AlignmentFlag.AlignVCenter, "BugOS")

        # stappen
        y = 128
        for i, naam in enumerate(self.stappen):
            klaar, nu = i < self.huidig, i == self.huidig
            cx, cy = 44, y + 14
            if klaar:
                p.setBrush(QColor(K["accent"]))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - 11, cy - 11, 22, 22))
                vink = QPen(QColor("#FFFFFF"), 2.2)
                vink.setCapStyle(Qt.PenCapStyle.RoundCap)
                vink.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(vink)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPolyline([QPointF(cx - 5, cy + 0.5), QPointF(cx - 1.5, cy + 4), QPointF(cx + 5, cy - 3.5)])
            elif nu:
                p.setBrush(QColor("#FFFFFF"))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - 11, cy - 11, 22, 22))
                p.setBrush(QColor(K["accent"]))
                p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 90), 1.6))
                p.drawEllipse(QRectF(cx - 10, cy - 10, 20, 20))
            if i < len(self.stappen) - 1:
                p.setPen(QPen(QColor(255, 255, 255, 140 if klaar else 50), 1.6))
                p.drawLine(QPointF(cx, cy + 14), QPointF(cx, cy + 34))
            f = QFont(self.font())
            f.setPixelSize(15)
            f.setWeight(f.Weight.DemiBold if nu else f.Weight.Normal)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 255 if nu else (200 if klaar else 130)))
            p.drawText(QRectF(70, y, 240, 28), Qt.AlignmentFlag.AlignVCenter, naam)
            y += 48

        f = p.font()
        f.setPixelSize(13)
        f.setWeight(f.Weight.Normal)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 150))
        p.drawText(QRectF(32, r.bottom() - 52, 260, 24), Qt.AlignmentFlag.AlignVCenter,
                   t(f"Stap {self.huidig + 1} van {len(self.stappen)}", f"Step {self.huidig + 1} of {len(self.stappen)}"))
