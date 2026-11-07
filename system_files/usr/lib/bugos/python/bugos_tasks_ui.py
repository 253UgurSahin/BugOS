"""Onderdelen van BugOS Taakbeheer: het meten op de achtergrond, grafiekjes en de regels in de lijsten.

Hoort bij /usr/bin/bugos-task-manager (daar staat het venster zelf).
"""

from __future__ import annotations

import collections
import os
from pathlib import Path

import bugos_tasks as bt
from bugos_ui import K, Kaart, Rij, Schuif, label, lijn_icoon, t
from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

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

    def run(self) -> None:
        while not self.stoppen:
            try:
                data = voorbeeld_meting(self.stap) if self.voorbeeld else self.meter.meet()
            except Exception:  # noqa: BLE001  een rare meting mag het venster nooit laten vallen
                data = None
            self.stap += 1
            if data is not None and not self.stoppen:
                self.meting.emit(data)
            for _ in range(TUSSENPOOS_MS // 100):
                if self.stoppen:
                    return
                self.msleep(100)


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
        bt.Taak("bugos-files", "Bestanden", "system-file-manager", "app", "app-bugos\\x2dbestanden-5.scope",
                [501], golf(0.3, 0.3), int(0.09 * gb), True),
        bt.Taak("achtergrond:plasma-plasmashell.service:plasmashell", "Bureaublad (Plasma)", "", "achtergrond",
                "plasma-plasmashell.service", [601], golf(1.0, 0.6), int(0.31 * gb), True, True),
        bt.Taak("achtergrond:plasma-kwin_wayland.service:kwin_wayland", "Vensters (KWin)", "", "achtergrond",
                "plasma-kwin_wayland.service", [602], golf(1.4, 0.8), int(0.18 * gb), True, True),
        bt.Taak("achtergrond:baloo.service:baloo_file", "Zoeken in je bestanden", "", "achtergrond",
                "plasma-baloorunner.service", [603], golf(0.6, 0.4), int(0.12 * gb), True),
        bt.Taak("systeem:NetworkManager.service", "Netwerk", "", "systeem", "NetworkManager.service", [701],
                0.1, int(0.02 * gb), False, True),
    ]
    return {
        "processor": sum(x.processor for x in taken) + golf(3, 2, 0.9), "geheugen_totaal": 16 * gb,
        "geheugen_gebruikt": int(golf(5.4, 0.15, 0.2) * gb), "schijf": golf(2.2e6, 2.0e6, 0.8),
        "schijf_bezig": golf(4, 3, 0.8), "binnen": golf(1.4e6, 1.2e6, 0.6), "buiten": golf(1.2e5, 0.8e5, 0.7),
        "temperatuur": golf(52, 3, 0.25), "videokaart": golf(8, 6, 0.4), "taken": taken,
    }


# ============================================================== onderdelen ===

def stijl() -> str:
    return f"""
QFrame#rij[gekozen="true"], QFrame#rij[gekozen="true"]:hover {{ background: {K['knop_hover']}; }}
QLabel#stip {{ border-radius: 6px; min-width: 12px; max-width: 12px; min-height: 12px; max-height: 12px; }}
QLabel#stip[soort="goed"] {{ background: {K['goed']}; }}
QLabel#stip[soort="let_op"] {{ background: {K['let_op']}; }}
"""


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


class Getallen(QWidget):
    """Rechts in een regel: kracht en geheugen, netjes onder hun kopje."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self.processor = label("", "klein", wrap=False)
        self.processor.setFixedWidth(84)
        self.processor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.geheugen = label("", "klein", wrap=False)
        self.geheugen.setFixedWidth(92)
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
        self.schuif.toggled.connect(lambda aan: (omzetten(item, aan), self._tekst(aan)))
        self._tekst(item.aan)

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
