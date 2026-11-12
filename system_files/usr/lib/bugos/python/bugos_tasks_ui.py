"""Onderdelen van BugOS Taakbeheer: het meten op de achtergrond, grafiekjes, de regels in de lijsten en de tabel
van de pagina Details (ProcesModel, ProcesFilter, ProcesTabel).

Hoort bij /usr/bin/bugos-task-manager (daar staat het venster zelf).
"""

from __future__ import annotations

import collections
import os
import threading
from pathlib import Path

import bugos_tasks as bt
from bugos_ui import TAAL, K, Kaart, Rij, Schuif, label, lijn_icoon, px, schaal_css, t

# De breedte van de kolommen Processor en Geheugen (kop en regels gelijk), bij gewone letters.
KOLOM_PROCESSOR, KOLOM_GEHEUGEN = 90, 96
# Details: de breedte van de kolommen Nummer, Van, Hoort bij, Processor en Geheugen (Naam krijgt de rest).
KOLOM_DETAILS = (None, 70, 96, 160, 84, 90)
from PySide6.QtCore import (  # noqa: E402
    QAbstractTableModel, QModelIndex, QRectF, QSize, QSortFilterProxyModel, Qt, QThread, Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLayout, QTreeView, QWidget,
)

GESCHIEDENIS = 60      # hoeveel metingen de grafiekjes laten zien (2 minuten)
TUSSENPOOS_MS = 2000   # elke 2 seconden meten


class Klusdraad(QThread):
    """Eén traag klusje op de achtergrond; 'klaar' komt terug in het venster (de hoofddraad)."""

    klaar = Signal(object)

    def __init__(self, werk):
        super().__init__()
        self.werk = werk

    def run(self) -> None:
        try:
            uitkomst = self.werk()
        except Exception as e:  # noqa: BLE001  (nooit het venster laten vastlopen)
            uitkomst = e
        self.klaar.emit(uitkomst)


# =============================================================== metingen ===

class Meetdraad(QThread):
    """Meet op de achtergrond, zodat het venster nooit hapert."""

    meting = Signal(object)

    def __init__(self):
        super().__init__()
        self.meter = bt.Meter()
        self.stoppen = False
        self.voorbeeld = bool(os.environ.get("BUGOS_TAKEN_VOORBEELD"))
        self.stap = 0
        self.zichtbaar = True
        self._wek = threading.Event()

    def stop(self) -> None:
        self.stoppen = True
        self._wek.set()

    def zet_zichtbaar(self, ja: bool) -> None:
        """Geminimaliseerd of verborgen: niet meten (dat kostte op een laptop steeds een paar procent van een kern).
        Weer in beeld: meteen een nieuwe meting (U311)."""
        self.zichtbaar = ja
        if ja:
            self._wek.set()

    def run(self) -> None:
        while not self.stoppen:
            if not self.zichtbaar:
                # Wachten tot het venster weer in beeld is (geen tikken van 10 keer per seconde meer) (U311).
                self._wek.wait()
                self._wek.clear()
                continue
            try:
                data = voorbeeld_meting(self.stap) if self.voorbeeld else self.meter.meet()
            except Exception:  # noqa: BLE001  een rare meting mag het venster nooit laten vallen
                data = None
            self.stap += 1
            if data is not None and not self.stoppen:
                self.meting.emit(data)
            self._wek.wait(TUSSENPOOS_MS / 1000)
            self._wek.clear()


def voorbeeld_meting(stap: int) -> dict:
    """Voorbeeldgetallen voor foto's en demo's (BUGOS_TAKEN_VOORBEELD=1)."""
    import math
    import random

    def golf(basis: float, slag: float, snel: float = 0.35) -> float:
        """Een beetje grillig, zoals echte metingen: twee golfjes en wat ruis, af en toe een piekje."""
        r = random.Random(stap * 7919 + int(basis * 1000) + int(snel * 100))
        piek = slag * 1.6 if r.random() < 0.08 else 0.0
        waarde = basis + slag * (0.55 * math.sin(stap * snel) + 0.3 * math.sin(stap * snel * 2.7 + 1.3)
                                 + 0.35 * (r.random() - 0.5)) + piek
        return max(0.0, waarde)

    gb = 10**9
    taken = [
        bt.Taak("org.mozilla.firefox", "Firefox", "firefox", "app", "app-org.mozilla.firefox-1.scope",
                [101, 102, 103], golf(9, 4), int(2.1 * gb), True),
        bt.Taak("libreoffice-writer", "LibreOffice Writer", "libreoffice-writer", "app", "app-libreoffice-2.scope",
                [201], golf(1.2, 0.8), int(0.38 * gb), True),
        bt.Taak("com.spotify.Client", "Spotify", "com.spotify.Client", "app", "app-flatpak-com.spotify.Client-3.scope",
                [301, 302], golf(2.5, 1), int(0.46 * gb), True),
        bt.Taak("steam", "Steam", "steam", "app", "app-steam-4.scope", [401, 402], golf(1.5, 1, 0.5),
                int(0.61 * gb), True),
        bt.Taak("bugos-files", t("Bestanden", "Files"), "system-file-manager", "app", "app-bugos\\x2dbestanden-5.scope",
                [501], golf(0.3, 0.3), int(0.09 * gb), True),
        bt.Taak("achtergrond:plasma-plasmashell.service:plasmashell", t("Bureaublad (Plasma)", "Desktop (Plasma)"), "",
                "achtergrond", "plasma-plasmashell.service", [601], golf(1.0, 0.6), int(0.31 * gb), True, True),
        bt.Taak("achtergrond:plasma-kwin_wayland.service:kwin_wayland", t("Vensters (KWin)", "Windows (KWin)"), "",
                "achtergrond", "plasma-kwin_wayland.service", [602], golf(1.4, 0.8), int(0.18 * gb), True, True),
        bt.Taak("achtergrond:baloo.service:baloo_file", t("Zoeken in je bestanden", "Searching your files"), "",
                "achtergrond", "plasma-baloorunner.service", [603], golf(0.6, 0.4), int(0.12 * gb), True),
        bt.Taak("systeem:NetworkManager.service", t("Netwerk", "Network"), "", "systeem", "NetworkManager.service",
                [701], 0.1, int(0.02 * gb), False, True),
    ]
    return {
        "processor": sum(x.processor for x in taken) + golf(3, 2, 0.9), "geheugen_totaal": 16 * gb,
        "geheugen_gebruikt": int(golf(5.4, 0.15, 0.2) * gb), "schijf": golf(2.2e6, 2.0e6, 0.8),
        "schijf_bezig": golf(4, 3, 0.8), "binnen": golf(1.4e6, 1.2e6, 0.6), "buiten": golf(1.2e5, 0.8e5, 0.7),
        "temperatuur": golf(52, 3, 0.25), "videokaart": golf(8, 6, 0.4), "taken": taken,
        "processen": voorbeeld_processen(taken),
    }


def voorbeeld_processen(taken: list[bt.Taak]) -> list[bt.ProcesRegel]:
    """De pagina Details in de voorbeeldstand: de processen van de voorbeeldtaken, en een paar van de computer zelf.
    Van wie en of hij beschermd is, staat vast (niet afhankelijk van wie de foto maakt, ook niet als root)."""
    namen = {101: "firefox", 102: "Isolated Web Co", 103: "Isolated Web Co", 201: "soffice.bin", 301: "spotify",
             302: "spotify", 401: "steam", 402: "steamwebhelper", 501: "bugos-files", 601: "plasmashell",
             602: "kwin_wayland", 603: "baloo_file", 701: "NetworkManager"}
    jij, systeem = t("jij", "you"), t("systeem", "system")
    regels = []
    for taak in taken:
        for pid in taak.pids:
            n = len(taak.pids)
            eigen = taak.soort != "systeem"
            regels.append(bt.ProcesRegel(pid, namen.get(pid, taak.naam), 1000 if eigen else 0, jij if eigen else systeem,
                                         taak.naam, taak.processor / n, taak.geheugen // n, eigen,
                                         taak.beschermd or not eigen, 1000 + pid,
                                         taak.soort == "app" and pid == taak.pids[0]))
    mb = 10**6
    for pid, naam, uid, eigenaar, hoort_bij, procent, geheugen_ in (
            (1, "systemd", 0, systeem, "", 0.0, 17 * mb),
            (1530, "cupsd", 0, systeem, t("Printers", "Printers"), 0.0, int(9.8 * mb)),
            (1188, "polkitd", 999, "polkitd", "", 0.0, 12 * mb),
            (900, "bugos-task-manager", 1000, jij, t("Taakbeheer", "Task Manager"), 0.8, 64 * mb)):
        regels.append(bt.ProcesRegel(pid, naam, uid, eigenaar, hoort_bij, procent, geheugen_, uid == 1000, True,
                                     1000 + pid))
    return regels


# ============================================================== onderdelen ===

def stijl() -> str:
    return schaal_css(f"""
QFrame#rij[gekozen="true"], QFrame#rij[gekozen="true"]:hover {{ background: {K['knop_hover']}; }}
QLabel#stip {{ border-radius: 6px; min-width: 12px; max-width: 12px; min-height: 12px; max-height: 12px; }}
QLabel#stip[soort="goed"] {{ background: {K['goed']}; }}
QLabel#stip[soort="let_op"] {{ background: {K['let_op']}; }}
QTreeView#processen {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; padding: 4px;
  font-size: 14px; selection-background-color: {K['knop_hover']}; selection-color: {K['tekst']}; outline: 0; }}
QTreeView#processen:focus {{ border: 1px solid {K['accent']}; }}
QTreeView#processen::item {{ height: 34px; padding: 0 8px; border: none; }}
QTreeView#processen::item:hover {{ background: {K['knop']}; }}
QTreeView#processen::item:selected {{ background: {K['knop_hover']}; color: {K['tekst']}; }}
QTreeView#processen QHeaderView {{ background: transparent; }}
QTreeView#processen QHeaderView::section {{ background: {K['vlak']}; color: {K['tekst2']}; border: none;
  border-bottom: 1px solid {K['rand']}; padding: 8px 8px; font-size: 13px; font-weight: 600; }}
QTreeView#processen QHeaderView::section:hover {{ color: {K['tekst']}; }}
QPushButton#balkknop:disabled {{ color: {K['tekst3']}; }}
""")


def app_icoon(naam: str, soort: str) -> QIcon:
    if naam and Path(naam).is_absolute():
        return QIcon(naam)
    ic = QIcon.fromTheme(naam) if naam else QIcon()
    if ic.isNull():
        ic = lijn_icoon("apps" if soort == "app" else "schakelaar", "tekst3", 22, gekozen=None)
    return ic


class Grafiek(QWidget):
    """Een rustig lijntje met een zachte tint eronder: hoe het de laatste twee minuten ging."""

    def __init__(self, maximum: float | None = 100.0):
        super().__init__()
        self.maximum = maximum  # None = past zich aan (voor schijf en internet)
        self.waarden: collections.deque[float] = collections.deque(maxlen=GESCHIEDENIS)
        self.setMinimumHeight(84)

    def voeg_toe(self, waarde: float) -> None:
        self.waarden.append(max(0.0, waarde))
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 4, -1, -2)
        p.setPen(QPen(QColor(K["rand"]), 1))
        for i in range(1, 4):  # drie dunne hulplijntjes
            y = r.top() + r.height() * i / 4
            p.drawLine(r.left(), y, r.right(), y)
        if len(self.waarden) < 2:
            return
        hoogste = self.maximum or max(max(self.waarden) * 1.25, 1.0)
        stap = r.width() / (GESCHIEDENIS - 1)
        start = r.right() - stap * (len(self.waarden) - 1)
        punten = [(start + i * stap, r.bottom() - min(w / hoogste, 1.0) * r.height())
                  for i, w in enumerate(self.waarden)]
        lijn_ = QPainterPath()
        lijn_.moveTo(*punten[0])
        for (x0, y0), (x1, y1) in zip(punten, punten[1:]):
            midden = (x0 + x1) / 2
            lijn_.cubicTo(midden, y0, midden, y1, x1, y1)
        vlak = QPainterPath(lijn_)
        vlak.lineTo(punten[-1][0], r.bottom())
        vlak.lineTo(punten[0][0], r.bottom())
        vlak.closeSubpath()
        kleur_ = QColor(K["tekst2"])
        verloop = QLinearGradient(0, r.top(), 0, r.bottom())
        boven = QColor(kleur_)
        boven.setAlphaF(0.16)
        onder = QColor(kleur_)
        onder.setAlphaF(0.0)
        verloop.setColorAt(0, boven)
        verloop.setColorAt(1, onder)
        p.fillPath(vlak, verloop)
        p.setPen(QPen(kleur_, 2.0))
        p.drawPath(lijn_)


class MeetKaart(Kaart):
    """Een kaart op 'Prestaties': naam, groot getal, uitleg en een grafiekje."""

    def __init__(self, naam: str, maximum: float | None = 100.0):
        super().__init__(marge=22, ruimte=4)
        self.lay.addWidget(label(naam, "kop3", wrap=False))
        self.waarde = label("–", "kop2", wrap=False)
        self.uitleg = label("", "klein", wrap=False)
        self.lay.addWidget(self.waarde)
        self.lay.addWidget(self.uitleg)
        self.lay.addSpacing(8)
        self.grafiek = Grafiek(maximum)
        self.lay.addWidget(self.grafiek)

    def zet(self, waarde: str, uitleg: str, punt: float) -> None:
        self.waarde.setText(waarde)
        self.uitleg.setText(uitleg)
        self.grafiek.voeg_toe(punt)


class Plooi(QWidget):
    """Kaarten of blokjes naast elkaar, net zoveel als er passen (hoogstens 'hoogstens' per rij). Bij 150 % of met
    'Grote letters' gaan ze naar een volgende rij in plaats van dat de pagina opzij schuift (R13).
    bij_kolom(deel, kolom) hoort na elke nieuwe indeling (bijv. om een scheidingsstreep links te verbergen).
    keuzes: welke aantallen per rij mogen (bijv. (4, 2, 1): vier getallen worden twee rijen van twee, nooit 3 + 1)."""

    def __init__(self, delen: list[QWidget], hoogstens: int, ruimte: int = 14, bij_kolom=None,
                 keuzes: tuple[int, ...] | None = None):
        super().__init__()
        self.delen, self.hoogstens, self.ruimte, self.bij_kolom = list(delen), hoogstens, ruimte, bij_kolom
        self.keuzes = tuple(sorted(set(keuzes or range(1, hoogstens + 1)) | {1}, reverse=True))
        self.rooster = QGridLayout(self)
        self.rooster.setContentsMargins(0, 0, 0, 0)
        self.rooster.setSpacing(ruimte)
        # De breedte bepaalt dit vlak zelf (minimumSizeHint): anders hield de indeling van nu de pagina breed.
        self.rooster.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.kolommen = 0
        self.deel_in(self.keuzes[0])

    @staticmethod
    def verstopt(d: QWidget) -> bool:
        """Is dit deel echt verborgen (iemand riep hide(), zoals bij de videokaart)? Niet: 'nog nergens geplaatst'.
        Een widget zonder ouder zegt isHidden() tot een layout hem opneemt; dan kreeg het eerste blokje bij het
        bouwen nooit zijn indeling (de streep links bleef staan)."""
        return d.isHidden() and d.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide)

    def nodig(self, n: int) -> int:
        """Hoe breed het minstens is met n naast elkaar: per kolom het breedste deel, plus de ruimte ertussen."""
        breed = [max(d.minimumSizeHint().width(), d.minimumWidth()) for d in self.delen if not self.verstopt(d)]
        return sum(max(breed[k::n], default=0) for k in range(n)) + (n - 1) * self.ruimte

    def past(self) -> int:
        """Hoeveel er naast elkaar passen. Naar méér per rij pas met wat speling: de getallen veranderen elke twee
        seconden een beetje van breedte, en dan moet de indeling niet heen en weer springen."""
        return next((k for k in self.keuzes
                     if self.nodig(k) + (12 if k > self.kolommen else 0) <= self.width()), 1)

    def deel_in(self, n: int, opnieuw: bool = False) -> None:
        if n == self.kolommen and not opnieuw:
            return
        while self.rooster.count():
            self.rooster.takeAt(0)
        zichtbaar = [d for d in self.delen if not self.verstopt(d)]
        for i, d in enumerate(zichtbaar + [d for d in self.delen if self.verstopt(d)]):   # verborgen achteraan
            self.rooster.addWidget(d, i // n, i % n)
            if self.bij_kolom and i < len(zichtbaar):
                self.bij_kolom(d, i % n)
        for k in range(self.hoogstens):
            self.rooster.setColumnStretch(k, 1 if k < n else 0)
        self.kolommen = n
        self.updateGeometry()

    def herschik(self) -> None:
        """Opnieuw indelen, na het tonen of verbergen van een deel."""
        self.deel_in(self.past() if self.width() > 1 else self.keuzes[0], opnieuw=True)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.nodig(1), self.rooster.minimumSize().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.nodig(self.kolommen or 1), self.rooster.sizeHint().height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self.deel_in(self.past())

    def bijwerken(self) -> None:
        """Na nieuwe getallen (ze kunnen breder zijn geworden)."""
        if self.width() > 1:
            self.deel_in(self.past())


class Getallen(QWidget):
    """Rechts in een regel: kracht en geheugen, netjes onder hun kopje."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self.processor = label("", "klein", wrap=False)
        self.processor.setFixedWidth(px(KOLOM_PROCESSOR))
        self.processor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.geheugen = label("", "klein", wrap=False)
        self.geheugen.setFixedWidth(px(KOLOM_GEHEUGEN))
        self.geheugen.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.processor)
        lay.addWidget(self.geheugen)


class TaakRij(Rij):
    """Eén programma (of achtergrondtaak): icoon, naam, kracht en geheugen. Klik om te kiezen."""

    def __init__(self, taak: bt.Taak):
        self.getallen = Getallen()
        kiesbaar = not taak.beschermd and taak.eigen
        super().__init__(app_icoon(taak.icoon, taak.soort), taak.naam,
                         "" if kiesbaar else t("Hoort bij BugOS", "Part of BugOS"), self.getallen,
                         klikbaar=kiesbaar, pijl=False, hoogte=52)
        self.sleutel = taak.sleutel
        self.zet(taak)

    def zet(self, taak: bt.Taak) -> None:
        self.taak = taak
        self.titel.setText(taak.naam)
        procent = taak.processor
        self.getallen.processor.setText(f"{procent:.0f}%" if procent >= 0.5 else "0%")
        kleur_ = K["let_op"] if procent >= 20 else K["tekst2"]
        self.getallen.processor.setStyleSheet(f"color: {kleur_};" + (" font-weight: 600;" if procent >= 20 else ""))
        self.getallen.geheugen.setText(bt.maat(taak.geheugen))

    def kies(self, aan: bool) -> None:
        self.setProperty("gekozen", "true" if aan else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class OpstartRij(Rij):
    """Een programma dat vanzelf meestart, met een schuifje."""

    def __init__(self, item: bt.Opstart, omzetten):
        rechts = QWidget()
        rl = QHBoxLayout(rechts)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self.stand = label("", "klein", wrap=False)
        self.schuif = Schuif(item.aan)
        self.schuif.setAccessibleName(item.naam)
        rl.addWidget(self.stand)
        rl.addWidget(self.schuif)
        super().__init__(app_icoon(item.icoon, "app"), item.naam, "", rechts)
        self.schuif.toggled.connect(lambda aan: self._omgezet(aan, omzetten(item, aan)))
        self._tekst(item.aan)

    def _omgezet(self, aan: bool, gelukt) -> None:
        """Lukte het niet (False), dan springt het schuifje terug (U186)."""
        if gelukt is False:
            self.schuif.zet_stil(not aan)
            aan = not aan
        self._tekst(aan)

    def _tekst(self, aan: bool) -> None:
        self.stand.setText(t("Start mee", "Starts") if aan else t("Start niet mee", "Does not start"))


class Status(QWidget):
    """Het stipje met de zin 'Alles loopt soepel.' bovenaan een pagina."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 0, 0)
        lay.setSpacing(10)
        self.stip = QLabel()
        self.stip.setObjectName("stip")
        self.stip.setProperty("soort", "goed")
        lay.addWidget(self.stip, 0, Qt.AlignmentFlag.AlignVCenter)
        self.tekst = label(t("Even kijken…", "Taking a look…"), "sub", wrap=False)
        lay.addWidget(self.tekst, 1)

    def zet(self, soort: str, zin: str) -> None:
        self.tekst.setText(zin)
        if self.stip.property("soort") != soort:
            self.stip.setProperty("soort", soort)
            self.stip.style().unpolish(self.stip)
            self.stip.style().polish(self.stip)


# ================================================================ details ===
# De pagina Details: één tabel met elk proces. Het model wordt elke twee seconden bijgewerkt OP ZIJN PLEK (op pid en
# starttijd), nooit opnieuw opgebouwd: anders sprong je keuze elke twee seconden weg.

REGEL_ROL = int(Qt.ItemDataRole.UserRole) + 1     # de bt.ProcesRegel zelf
SORTEER_ROL = int(Qt.ItemDataRole.UserRole) + 2   # waarop een kolom sorteert


def procent_tekst(p: float) -> str:
    """0,7% in het Nederlands, 0.7% in het Engels (zoals de maten: 9,8 MB)."""
    if p < 0.05:
        return "0%"
    tekst = f"{p:.1f}%" if p < 10 else f"{p:.0f}%"
    return tekst.replace(".", ",") if TAAL == "nl" else tekst


class ProcesModel(QAbstractTableModel):
    """Alle processen (bt.ProcesRegel), zes kolommen."""

    @staticmethod
    def koppen() -> tuple[str, ...]:
        """De kolomkoppen. Elk als eigen t("..", "..") met twee vaste teksten: alleen zo vindt
        tools/collect-translations.py ze voor de vertalingen (t(*een_lijst) ziet hij niet)."""
        return (t("Naam", "Name"), t("Nummer", "Number"), t("Van", "Owner"), t("Hoort bij", "Part of"),
                t("Processor", "Processor"), t("Geheugen", "Memory"))

    def __init__(self):
        super().__init__()
        self.regels: list[bt.ProcesRegel] = []

    def rowCount(self, ouder=QModelIndex()) -> int:  # noqa: N802
        return 0 if ouder.isValid() else len(self.regels)

    def columnCount(self, ouder=QModelIndex()) -> int:  # noqa: N802
        return 0 if ouder.isValid() else 6

    def headerData(self, kolom, richting, rol=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if richting != Qt.Orientation.Horizontal or not 0 <= kolom < 6:
            return None
        if rol == Qt.ItemDataRole.DisplayRole:
            return self.koppen()[kolom]
        if rol == Qt.ItemDataRole.TextAlignmentRole:
            rechts = kolom in (1, 4, 5)
            return int((Qt.AlignmentFlag.AlignRight if rechts else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        if rol == Qt.ItemDataRole.ToolTipRole:
            if kolom == 1:
                return t("Procesnummer (PID)", "Process number (PID)")
            if kolom == 5:
                return t("Bij je eigen processen: wat ze echt gebruiken. Bij andere: inclusief gedeeld geheugen.",
                         "For your own processes: what they really use. For others: including shared memory.")
        return None

    def data(self, index, rol=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.regels):
            return None
        r, kolom = self.regels[index.row()], index.column()
        if rol == Qt.ItemDataRole.DisplayRole:
            return (r.naam, str(r.pid), r.eigenaar, r.hoort_bij, procent_tekst(r.processor), bt.maat(r.geheugen))[kolom]
        if rol == SORTEER_ROL:
            return (r.naam.lower(), r.pid, r.eigenaar.lower(), r.hoort_bij.lower(), r.processor, r.geheugen)[kolom]
        if rol == REGEL_ROL:
            return r
        if rol == Qt.ItemDataRole.TextAlignmentRole and kolom in (1, 4, 5):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if rol == Qt.ItemDataRole.ForegroundRole:
            if kolom == 4 and r.processor >= 20:
                return QColor(K["let_op"])
            if r.beschermd:
                return QColor(K["tekst2"])
        if rol == Qt.ItemDataRole.FontRole and kolom == 4 and r.processor >= 20:
            f = QFont()
            f.setWeight(QFont.Weight.DemiBold)
            return f
        if rol == Qt.ItemDataRole.ToolTipRole and kolom == 0:
            extra = ""
            if r.beschermd:
                extra = t(" · hoort bij BugOS", " · part of BugOS") if r.eigen else t(" · niet van jou", " · not yours")
            return f"{r.naam} · {r.pid}{extra}"
        return None

    def zet(self, regels: list[bt.ProcesRegel]) -> None:
        """Bijwerken op hun plek: weg wat weg is, de rest nieuwe getallen, nieuw achteraan. Een nummer met een
        andere starttijd is een ander proces (dan springt je keuze niet naar een ander programma)."""
        nieuw = {(r.pid, r.start): r for r in regels}
        i = len(self.regels) - 1
        while i >= 0:                                   # van achteren, in stukjes die aan elkaar zitten
            if (self.regels[i].pid, self.regels[i].start) in nieuw:
                i -= 1
                continue
            eind = i
            while i >= 0 and (self.regels[i].pid, self.regels[i].start) not in nieuw:
                i -= 1
            self.beginRemoveRows(QModelIndex(), i + 1, eind)
            del self.regels[i + 1:eind + 1]
            self.endRemoveRows()
        gezien = set()
        for j, r in enumerate(self.regels):
            sleutel = (r.pid, r.start)
            self.regels[j] = nieuw[sleutel]
            gezien.add(sleutel)
        if self.regels:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.regels) - 1, 5))
        erbij = [r for sleutel, r in nieuw.items() if sleutel not in gezien]
        if erbij:
            self.beginInsertRows(QModelIndex(), len(self.regels), len(self.regels) + len(erbij) - 1)
            self.regels.extend(erbij)
            self.endInsertRows()


class ProcesFilter(QSortFilterProxyModel):
    """Zoeken (op naam, 'hoort bij' of het begin van het nummer) en 'Alleen van jou'."""

    def __init__(self):
        super().__init__()
        self.zoek = ""
        self.alleen_eigen = False
        self.setSortRole(SORTEER_ROL)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def zet_zoek(self, tekst: str) -> None:
        self.zoek = tekst.strip().lower()
        self.invalidateFilter()

    def zet_eigen(self, aan: bool) -> None:
        self.alleen_eigen = aan
        self.invalidateFilter()

    def filterAcceptsRow(self, rij: int, ouder) -> bool:  # noqa: N802
        bron = self.sourceModel()
        if not isinstance(bron, ProcesModel) or not 0 <= rij < len(bron.regels):
            return False
        r = bron.regels[rij]
        if self.alleen_eigen and not r.eigen:
            return False
        z = self.zoek
        return not z or z in r.naam.lower() or z in r.hoort_bij.lower() or str(r.pid).startswith(z)


class ProcesTabel(QTreeView):
    """De tabel van Details. Smal venster (of 150 %): eerst 'Hoort bij' weg, dan ook 'Van', zodat Processor en
    Geheugen altijd te zien zijn."""

    def __init__(self, model: QSortFilterProxyModel):
        super().__init__()
        self.setObjectName("processen")
        self.setModel(model)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAccessibleName(t("Alles wat draait", "Everything that is running"))
        kop = self.header()
        kop.setStretchLastSection(False)
        kop.setSectionsMovable(False)
        kop.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for kolom, breedte in enumerate(KOLOM_DETAILS):
            if breedte:
                kop.setSectionResizeMode(kolom, QHeaderView.ResizeMode.Fixed)
                kop.resizeSection(kolom, px(breedte))
        self.setMinimumHeight(px(150))   # 1280x800 bij 150 %: dan past de pagina nog zonder te schuiven

    def verberg_kolommen(self) -> None:
        breed = self.viewport().width()
        self.setColumnHidden(3, breed < px(650))
        self.setColumnHidden(2, breed < px(490))

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self.verberg_kolommen()

    def sizeHint(self) -> QSize:  # noqa: N802
        """Niet hoger willen dan het minimum: de pagina geeft de tabel zelf alle ruimte die over is. (Een grotere
        wens liet de pagina op een klein scherm net een paar pixels schuiven.)"""
        return QSize(super().sizeHint().width(), self.minimumHeight())
