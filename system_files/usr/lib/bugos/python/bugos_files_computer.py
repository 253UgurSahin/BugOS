"""BugOS Bestanden: de pagina 'Deze computer'.

Jip-en-Janneke: hoeveel ruimte je computer nog heeft, wat die ruimte inneemt
(Afbeeldingen, Video's, ...) en een knop 'Ruimte maken'. Dit is een stukje van het
venster (Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from bugos_ui import K, Knop, label, lijn, lijn_icoon, sectie, t
from bugos_drives import mooie_maat
from bugos_files_plekken import RUIMTE_SOORTEN, Teller, eigen_ruimte, plekken, voorbeeld_ruimte
from bugos_files_acties import prullenbak, prullenbak_inhoud
from bugos_files_onderdelen import RuimteBalk, SchijfRij, stip_icoon
from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QMenu, QPushButton, QVBoxLayout


class Computer:
    """De pagina 'Deze computer': een stukje van het venster Bestanden."""

    def open_computer(self, geschiedenis: bool = True) -> None:
        """De pagina 'Deze computer': al je schijven, en hoeveel ruimte er nog is (zoals 'Deze pc' in Windows)."""
        if geschiedenis and not self.in_computer:
            self.terug_lijst.append(self.plek_nu())
            self.vooruit_lijst.clear()
        if self.lijst.selectionModel() is not None:
            self.lijst.selectionModel().clear()
        self.in_computer, self.in_prullenbak = True, False
        self.vul_computer()
        self.bouw_pad()
        self.markeer_zijbalk()
        self.ververs_staat()

    def vul_computer(self) -> None:
        """Bovenaan: hoeveel ruimte je computer nog heeft. Daaronder: USB-sticks en andere schijven."""
        lay = self.computer_lay
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()

        # --- de computer zelf: groot getal, balk, en wat de ruimte inneemt
        totaal, vrij = eigen_ruimte()
        nep = voorbeeld_ruimte()
        if nep and self.ruimte is None:
            self.ruimte = dict(zip([sl for sl, _k in RUIMTE_SOORTEN], nep[2:]))
            self.ruimte_tijd = time.monotonic()
        kaart = QFrame()
        kaart.setObjectName("kaart")
        binnen = QVBoxLayout(kaart)
        binnen.setContentsMargins(26, 22, 26, 20)
        binnen.setSpacing(0)
        regel = QHBoxLayout()
        regel.setSpacing(12)
        regel.addWidget(label(t(f"{mooie_maat(vrij)} vrij", f"{mooie_maat(vrij)} free"), "groot", wrap=False),
                        0, Qt.AlignmentFlag.AlignBottom)
        van = label(t(f"van de {mooie_maat(totaal)}", f"of {mooie_maat(totaal)}"), "sub", wrap=False)
        van.setContentsMargins(0, 0, 0, 9)
        regel.addWidget(van, 0, Qt.AlignmentFlag.AlignBottom)
        regel.addStretch(1)
        ruimte_knop = Knop(t("Ruimte maken", "Free up space"), "gewoon")
        ruimte_knop.setMinimumHeight(38)
        ruimte_knop.clicked.connect(lambda _c=False, k=ruimte_knop: self.ruimte_menu().exec(
            k.mapToGlobal(k.rect().bottomLeft())))
        regel.addWidget(ruimte_knop, 0, Qt.AlignmentFlag.AlignTop)
        binnen.addLayout(regel)
        binnen.addSpacing(14)
        self.ruimte_balk = RuimteBalk()
        binnen.addWidget(self.ruimte_balk)
        binnen.addSpacing(8)
        self.legenda = QGridLayout()
        self.legenda.setHorizontalSpacing(4)
        self.legenda.setVerticalSpacing(0)
        binnen.addLayout(self.legenda)
        lay.addWidget(kaart)
        self.ruimte_totaal, self.ruimte_vrij = totaal, vrij
        self.toon_ruimte()
        if not self.tellen_bezig and (self.ruimte is None or time.monotonic() - self.ruimte_tijd > 120):
            self.tellen_bezig = True
            mappen = [(sl, pad) for sl, _n, _i, pad in plekken() if sl in dict(RUIMTE_SOORTEN)]
            mappen.append(("prullenbak", prullenbak() / "files"))
            QThreadPool.globalInstance().start(Teller(mappen, self.telsein))

        # --- USB-sticks en schijven: een gewone lijst
        lay.addSpacing(10)
        lay.addWidget(sectie(t("USB-sticks en schijven", "USB sticks and drives")))
        lijst_kaart = QFrame()
        lijst_kaart.setObjectName("kaart")
        rijen = QVBoxLayout(lijst_kaart)
        rijen.setContentsMargins(6, 6, 6, 6)
        rijen.setSpacing(2)
        for i, x in enumerate(self.lijst_schijven):
            if i:
                streep = lijn()
                streep.setContentsMargins(50, 0, 10, 0)
                rijen.addWidget(streep)
            rijen.addWidget(self.schijf_rij(x))
        if not self.lijst_schijven:
            rijen.addWidget(SchijfRij("usb", t("Nog niets aangesloten", "Nothing plugged in yet"),
                                      t("Steek een USB-stick in, dan staat hij hier.",
                                        "Plug in a USB stick and it shows up here."), leeg=True))
        lay.addWidget(lijst_kaart)
        if shutil.which("partitionmanager"):
            beheer = Knop(t("Schijfbeheer (voor gevorderden)", "Disk management (advanced)"), "stil", "lijn:opslag")
            beheer.setToolTip(t("Schijven indelen en formatteren, zoals Schijfbeheer in Windows",
                                "Partition and format drives, like Disk Management in Windows"))
            beheer.clicked.connect(lambda _c=False: subprocess.Popen(["partitionmanager"], start_new_session=True))
            lay.addWidget(beheer, 0, Qt.AlignmentFlag.AlignRight)
        lay.addStretch(1)

    def ruimte_menu(self) -> QMenu:
        """Ruimte maken: de prullenbak leegmaken, of (voor gevorderden) Schijfbeheer."""
        m = QMenu(self)
        bak = (self.ruimte or {}).get("prullenbak")
        tekst = t(f"Prullenbak leegmaken ({mooie_maat(bak)})", f"Empty the trash ({mooie_maat(bak)})") if bak else \
            t("Prullenbak leegmaken", "Empty the trash")
        a = m.addAction(lijn_icoon("prullenbak", "tekst", 18, gekozen=None), tekst)
        a.triggered.connect(lambda _c=False: self.leegmaken())
        a.setEnabled(bool(prullenbak_inhoud()))
        return m

    def toon_ruimte(self) -> None:
        """Kleur de balk: Afbeeldingen, Video's, ... en de rest (BugOS en apps). Wat over is, is vrij."""
        totaal, vrij = self.ruimte_totaal, self.ruimte_vrij
        if totaal <= 0:
            return
        gebruikt = max(totaal - vrij, 0)
        while self.legenda.count():
            w = self.legenda.takeAt(0).widget()
            if w:
                w.deleteLater()
        namen = {sl: (naam, pad) for sl, naam, _i, pad in plekken()}
        delen: list[tuple[float, QColor]] = []
        items: list[tuple[QColor, str, Path | None]] = []
        if self.ruimte:
            som = sum(v for k, v in self.ruimte.items() if k in dict(RUIMTE_SOORTEN))
            schaal = min(1.0, gebruikt / som) if som else 1.0
            for sl, kl in RUIMTE_SOORTEN:
                grootte = self.ruimte.get(sl, 0) * schaal
                if grootte < max(totaal * 0.002, 50 * 10**6):
                    continue  # te klein om te zien: telt mee bij de rest
                kleur_ = QColor(K["accent"] if kl == "accent" else kl)
                delen.append((grootte / totaal, kleur_))
                items.append((kleur_, f"{namen[sl][0]}  {mooie_maat(grootte)}", namen[sl][1]))
            rest = max(gebruikt - sum(d * totaal for d, _k in delen), 0)
            grijs = QColor(K["tekst3"])
            delen.append((rest / totaal, grijs))
            items.append((grijs, t(f"BugOS en apps  {mooie_maat(rest)}", f"BugOS and apps  {mooie_maat(rest)}"), None))
        else:
            grijs = QColor(K["tekst3"])
            delen.append((gebruikt / totaal, grijs))
            items.append((grijs, t(f"In gebruik  {mooie_maat(gebruikt)}  (bezig met tellen…)",
                                   f"In use  {mooie_maat(gebruikt)}  (counting…)"), None))
        self.ruimte_balk.zet(delen)
        kolommen = 3 if len(items) > 4 else max(len(items), 1)
        for i, (kleur_, tekst, pad) in enumerate(items):
            k = QPushButton(tekst)
            k.setObjectName("legenda")
            k.setIcon(stip_icoon(kleur_, hol=pad == "vrij"))
            k.setIconSize(QSize(12, 12))
            if isinstance(pad, Path):
                k.setCursor(Qt.CursorShape.PointingHandCursor)
                k.setToolTip(t(f"Open {pad.name}", f"Open {pad.name}"))
                k.clicked.connect(lambda _c=False, d=pad: self.ga_naar(d))
            else:
                k.setEnabled(False)
            self.legenda.addWidget(k, i // kolommen, i % kolommen)

    def _geteld(self, uitslag: dict) -> None:
        self.tellen_bezig = False
        self.ruimte, self.ruimte_tijd = uitslag, time.monotonic()
        if self.in_computer:
            self.toon_ruimte()
