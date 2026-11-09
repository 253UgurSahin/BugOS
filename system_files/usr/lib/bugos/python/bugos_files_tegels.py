"""BugOS Bestanden: de tegels rechts in het venster.

Jip-en-Janneke: voorbeeldjes van foto's en documenten (op de achtergrond geladen),
het tekenen van mappen en papiertjes, en de volgorde (mappen eerst, 'Foto 2' voor 'Foto 10').
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

from bugos_ui import K, lijn_pixmap, px
from bugos_files_plekken import AFBEELDING, ODF, PAD_ROL, SOORTEN, thuis, toon_naam
from PySide6.QtCore import (
    QCollator, QModelIndex, QObject, QRectF, QRunnable, QSize, QSortFilterProxyModel, Qt, QThreadPool, QTimer, QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QImageReader, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import QStyle, QStyledItemDelegate


# ============================================================ voorbeelden ===

def freedesktop_voorbeeld(pad: str) -> QImage:
    """Heeft KDE of een ander programma al een voorbeeldje gemaakt? Gebruik dat."""
    uri = QUrl.fromLocalFile(pad).toString(QUrl.ComponentFormattingOption.FullyEncoded)
    naam = hashlib.md5(uri.encode()).hexdigest() + ".png"
    cache = Path(os.environ.get("XDG_CACHE_HOME", thuis() / ".cache")) / "thumbnails"
    for maat in ("xx-large", "x-large", "large", "normal"):
        p = cache / maat / naam
        if p.exists():
            return QImage(str(p))
    return QImage()


def maak_voorbeeld(pad: str) -> QImage:
    ext = Path(pad).suffix.lower()
    if ext in AFBEELDING:
        lezer = QImageReader(pad)
        lezer.setAutoTransform(True)
        maat = lezer.size()
        if maat.isValid() and (maat.width() > 512 or maat.height() > 512):
            lezer.setScaledSize(maat.scaled(QSize(512, 512), Qt.AspectRatioMode.KeepAspectRatio))
        beeld = lezer.read()
        if not beeld.isNull():
            return beeld
    if ext in ODF:
        try:
            with zipfile.ZipFile(pad) as z:
                return QImage.fromData(z.read("Thumbnails/thumbnail.png"))
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    return freedesktop_voorbeeld(pad)


class Seinen(QObject):
    klaar = Signal(str, QImage)


class VoorbeeldTaak(QRunnable):
    def __init__(self, pad: str, seinen: Seinen):
        super().__init__()
        self.pad, self.seinen = pad, seinen

    def run(self) -> None:
        try:
            beeld = maak_voorbeeld(self.pad)
        except Exception:  # een kapot bestand mag nooit de app laten vallen
            beeld = QImage()
        try:
            self.seinen.klaar.emit(self.pad, beeld)
        except RuntimeError:  # het venster is al dicht
            pass


class Voorbeelden(QObject):
    """Voorbeeldjes laden op de achtergrond en onthouden."""

    bijgewerkt = Signal()

    def __init__(self):
        super().__init__()
        self.cache: dict[str, QPixmap | None] = {}
        self.bezig: set[str] = set()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(2)
        self.seinen = Seinen()
        self.seinen.klaar.connect(self._klaar)
        self.tik = QTimer(self)
        self.tik.setSingleShot(True)
        self.tik.setInterval(60)
        self.tik.timeout.connect(self.bijgewerkt.emit)

    def heeft_voorbeeld(self, pad: str) -> bool:
        ext = Path(pad).suffix.lower()
        return ext in AFBEELDING or ext in ODF or ext in (".pdf", ".mp4", ".mkv", ".webm", ".mov", ".avi")

    def pixmap(self, pad: str) -> QPixmap | None:
        if pad in self.cache:
            return self.cache[pad]
        if pad not in self.bezig and self.heeft_voorbeeld(pad):
            self.bezig.add(pad)
            self.pool.start(VoorbeeldTaak(pad, self.seinen))
        return None

    def _klaar(self, pad: str, beeld: QImage) -> None:
        self.bezig.discard(pad)
        self.cache[pad] = QPixmap.fromImage(beeld) if not beeld.isNull() else None
        self.tik.start()

    def vergeet(self) -> None:
        self.cache.clear()

    def stop(self) -> None:
        self.pool.clear()
        self.pool.waitForDone(1500)


# ================================================================ tekenen ===

def teken_map(p: QPainter, r: QRectF, teken: str = "") -> None:
    """Een zachte BugOS-map in een rustige tint (met eventueel een tekentje erop, zoals bij Documenten)."""
    midden, donker, tekenkleur = QColor(K["map_voor"]), QColor(K["map_achter"]), QColor(K["map_teken"])
    licht = midden.lighter(104)
    w, h = r.width(), r.height()
    straal = w * 0.085
    tab = QPainterPath()
    tab.addRoundedRect(QRectF(r.left(), r.top(), w * 0.44, h * 0.32), straal, straal)
    p.fillPath(tab, donker)
    achter = QPainterPath()
    achter.addRoundedRect(QRectF(r.left(), r.top() + h * 0.1, w, h * 0.9), straal, straal)
    p.fillPath(achter, donker)
    voor = QPainterPath()
    voor_r = QRectF(r.left(), r.top() + h * 0.24, w, h * 0.76)
    voor.addRoundedRect(voor_r, straal, straal)
    verloop = QLinearGradient(0, voor_r.top(), 0, voor_r.bottom())
    verloop.setColorAt(0, licht)
    verloop.setColorAt(1, midden)
    p.fillPath(voor, verloop)
    p.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
    p.drawLine(int(voor_r.left() + straal), int(voor_r.top() + 1), int(voor_r.right() - straal), int(voor_r.top() + 1))
    if teken:
        m = h * 0.38
        dpr = p.device().devicePixelRatioF() if p.device() else 1.0
        pm = lijn_pixmap(teken, tekenkleur, int(m * dpr), 2.2)
        p.drawPixmap(QRectF(voor_r.center().x() - m / 2, voor_r.center().y() - m / 2 + h * 0.02, m, m), pm, QRectF())


def teken_papier(p: QPainter, r: QRectF, ext: str) -> None:
    """Een papiertje met een gekleurd labeltje (PDF, DOCX, ...)."""
    kleur, soort = SOORTEN.get(ext, ("#8A8F9A", "tekst"))
    w, h = r.width(), r.height()
    hoek = w * 0.26
    pad = QPainterPath()
    pad.moveTo(r.left() + 6, r.top())
    pad.lineTo(r.right() - hoek, r.top())
    pad.lineTo(r.right(), r.top() + hoek)
    pad.lineTo(r.right(), r.bottom() - 6)
    pad.quadTo(r.right(), r.bottom(), r.right() - 6, r.bottom())
    pad.lineTo(r.left() + 6, r.bottom())
    pad.quadTo(r.left(), r.bottom(), r.left(), r.bottom() - 6)
    pad.lineTo(r.left(), r.top() + 6)
    pad.quadTo(r.left(), r.top(), r.left() + 6, r.top())
    p.fillPath(pad, QColor(K["vlak"]))
    p.setPen(QPen(QColor(K["rand_sterk"]), 1))
    p.drawPath(pad)
    vouw = QPainterPath()
    vouw.moveTo(r.right() - hoek, r.top())
    vouw.lineTo(r.right() - hoek, r.top() + hoek - 4)
    vouw.quadTo(r.right() - hoek, r.top() + hoek, r.right() - hoek + 4, r.top() + hoek)
    vouw.lineTo(r.right(), r.top() + hoek)
    p.fillPath(vouw, QColor(K["knop"]))
    p.drawPath(vouw)
    dpr = p.device().devicePixelRatioF() if p.device() else 1.0
    if soort in ("muziek", "film", "doos"):
        icoon = {"muziek": "muziek", "film": "film", "doos": "map"}[soort]
        m = w * 0.46
        pm = lijn_pixmap(icoon, QColor(kleur), int(m * dpr), 2.0)
        p.drawPixmap(QRectF(r.center().x() - m / 2, r.top() + h * 0.22, m, m), pm, QRectF())
    else:
        p.setPen(QPen(QColor(K["rand_sterk"]), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(4 if soort == "tekst" else 3):
            y = r.top() + h * (0.26 + i * 0.11)
            breed = 0.62 if i % 2 == 0 else 0.48
            if soort == "tabel":
                p.drawLine(int(r.left() + w * 0.18), int(y), int(r.left() + w * 0.82), int(y))
            else:
                p.drawLine(int(r.left() + w * 0.18), int(y), int(r.left() + w * (0.18 + breed)), int(y))
    if ext:
        f = QFont(p.font())
        f.setPixelSize(max(9, int(w * 0.17)))
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        tekst = ext.upper()[:4]
        fm = QFontMetrics(f)
        bw = fm.horizontalAdvance(tekst) + 10
        label_r = QRectF(r.left() + w * 0.12, r.bottom() - h * 0.3, bw, h * 0.18)
        lab = QPainterPath()
        lab.addRoundedRect(label_r, 4, 4)
        p.fillPath(lab, QColor(kleur))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(label_r, Qt.AlignmentFlag.AlignCenter, tekst)


def twee_regels(fm: QFontMetrics, tekst: str, breedte: int) -> list[str]:
    """Naam over hoogstens twee regels, met ... als het niet past."""
    if fm.horizontalAdvance(tekst) <= breedte:
        return [tekst]
    woorden, eerste = tekst.split(" "), ""
    for i in range(len(woorden), 0, -1):
        poging = " ".join(woorden[:i])
        if fm.horizontalAdvance(poging) <= breedte:
            eerste = poging
            rest = " ".join(woorden[i:])
            break
    if not eerste:  # één lang woord: hard afbreken
        n = len(tekst)
        while n > 1 and fm.horizontalAdvance(tekst[:n]) > breedte:
            n -= 1
        eerste, rest = tekst[:n], tekst[n:]
    return [eerste, fm.elidedText(rest, Qt.TextElideMode.ElideMiddle, breedte)] if rest else [eerste]


class TegelTekenaar(QStyledItemDelegate):
    """Tekent elk bestand als een tegel: voorbeeldje boven, naam eronder."""

    @staticmethod
    def maat() -> QSize:
        """De tegel groeit mee met 'Grote letters' (de naam eronder past dan nog) (U085)."""
        return QSize(px(148), px(164))

    def __init__(self, voorbeelden: Voorbeelden, bijzonder: dict[str, str]):
        super().__init__()
        self.voorbeelden = voorbeelden
        self.bijzonder = bijzonder

    def sizeHint(self, _optie, _index) -> QSize:  # noqa: N802
        return self.maat()

    def paint(self, p: QPainter, optie, index) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(optie.rect).adjusted(5, 5, -5, -5)
        gekozen = bool(optie.state & QStyle.StateFlag.State_Selected)
        boven = bool(optie.state & QStyle.StateFlag.State_MouseOver)
        if gekozen or boven:
            vak = QPainterPath()
            vak.addRoundedRect(r, 14, 14)
            p.fillPath(vak, QColor(K["knop_hover"] if gekozen else K["knop"]))
            if gekozen:
                p.setPen(QPen(QColor(K["rand_sterk"]), 1.2))
                p.drawPath(vak)
        pad = index.data(PAD_ROL) or ""
        is_map = os.path.isdir(pad)
        plek = QRectF(r.left() + 14, r.top() + 10, r.width() - 28, 92)
        if is_map:
            m = QRectF(0, 0, 84, 66)
            m.moveCenter(plek.center())
            teken_map(p, m, self.bijzonder.get(pad, ""))
        else:
            voorbeeld = self.voorbeelden.pixmap(pad)
            if voorbeeld is not None and not voorbeeld.isNull():
                maat = voorbeeld.size().scaled(plek.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
                doel = QRectF(0, 0, maat.width(), maat.height())
                doel.moveCenter(plek.center())
                schaduw = QPainterPath()
                schaduw.addRoundedRect(doel.translated(0, 2), 7, 7)
                p.fillPath(schaduw, QColor(0, 0, 0, 40))
                rond = QPainterPath()
                rond.addRoundedRect(doel, 7, 7)
                p.setClipPath(rond)
                p.drawPixmap(doel, voorbeeld, QRectF(voorbeeld.rect()))
                p.setClipping(False)
                p.setPen(QPen(QColor(0, 0, 0, 30), 1))
                p.drawPath(rond)
            elif Path(pad).suffix.lower() in AFBEELDING and pad in self.voorbeelden.bezig:
                wacht = QPainterPath()
                wacht.addRoundedRect(QRectF(plek.center().x() - 50, plek.center().y() - 36, 100, 72), 7, 7)
                p.fillPath(wacht, QColor(K["knop"]))
            else:
                papier = QRectF(0, 0, 62, 80)
                papier.moveCenter(plek.center())
                teken_papier(p, papier, Path(pad).suffix.lower().lstrip("."))
        naam = toon_naam(index.data(Qt.ItemDataRole.DisplayRole) or Path(pad).name, is_map)
        f = QFont(optie.font)
        f.setPixelSize(px(13))
        if gekozen:
            f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        fm = QFontMetrics(f)
        regels = twee_regels(fm, naam, int(r.width() - 16))
        p.setPen(QColor(K["tekst"]))
        y = plek.bottom() + 10
        for regel in regels:
            p.drawText(QRectF(r.left() + 8, y, r.width() - 16, fm.height()), Qt.AlignmentFlag.AlignHCenter, regel)
            y += fm.height()
        p.restore()


# ================================================================== model ===

class Sorteerder(QSortFilterProxyModel):
    """Mappen eerst, dan bestanden; 'Foto 2' voor 'Foto 10'. Zoeken binnen de open map."""

    def __init__(self):
        super().__init__()
        self.zoek = ""
        self.wortel = ""
        self.collator = QCollator()
        self.collator.setNumericMode(True)
        self.collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def zet_zoek(self, tekst: str) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt 6.10 en nieuwer
            self.beginFilterChange()
            self.zoek = tekst.strip().lower()
            self.endFilterChange()
        else:
            self.zoek = tekst.strip().lower()
            self.invalidateFilter()

    def filterAcceptsRow(self, rij: int, ouder: QModelIndex) -> bool:  # noqa: N802
        if not self.zoek:
            return True
        bron = self.sourceModel()
        if bron.filePath(ouder) != self.wortel:
            return True
        return self.zoek in bron.fileName(bron.index(rij, 0, ouder)).lower()

    def lessThan(self, a: QModelIndex, b: QModelIndex) -> bool:  # noqa: N802
        bron = self.sourceModel()
        map_a, map_b = bron.isDir(a), bron.isDir(b)
        if map_a != map_b:
            return map_a
        return self.collator.compare(bron.fileName(a), bron.fileName(b)) < 0
