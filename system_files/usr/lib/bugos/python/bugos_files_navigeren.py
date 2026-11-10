"""BugOS Bestanden: de zijbalk en het rondlopen door je mappen.

Jip-en-Janneke: links de vaste plekken en schijven, bovenin het pad (kruimels),
en de knoppen Terug, Vooruit en Omhoog. Dit is een stukje van het venster
(Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import getpass

import os
from pathlib import Path

from bugos_ui import lijn_icoon, platte_tip, px, t
from bugos_drives import Schijf, schijven
from bugos_files_plekken import HERKOMST_ROL, INFO_ROL, PAD_ROL, plekken, schijf_van, thuis, zit_in
from bugos_files_acties import prullenbak_inhoud
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFontMetrics, QStandardItem
from PySide6.QtWidgets import QLabel, QPushButton


class Navigeren:
    """Zijbalk en navigeren: een stukje van het venster Bestanden."""

    # ------------------------------------------------------------ zijbalk
    def vul_zijbalk(self) -> None:
        """Vaste plekken, en daaronder 'Schijven': Deze computer, USB-sticks en andere schijven."""
        oud, lijst = self.lijst_schijven, schijven()
        self.lijst_schijven = lijst
        sleutels = ([f"plek:{p[0]}:{p[1]}" for p in plekken()]
                    + [f"{x.apparaat}|{x.naam}|{x.wortel}|{x.op_slot}" for x in lijst])
        if getattr(self, "_zijbalk_sleutels", None) == sleutels:
            return
        self._zijbalk_sleutels = sleutels
        # Stond je in een schijf die nu dicht is of eruit is gehaald? Dan terug naar Thuis.
        weg = None if self.in_prullenbak or self.in_computer else schijf_van(self.huidig, oud)
        if weg and not any(x.wortel == weg.wortel for x in lijst):
            nog_er = any(x.apparaat == weg.apparaat for x in lijst)
            self.ga_naar(thuis(), geschiedenis=False)
            self.melding.toon(t(f"'{weg.naam}' is dichtgegaan.", f"'{weg.naam}' was closed.") if nog_er else
                              t(f"'{weg.naam}' is eruit gehaald.", f"'{weg.naam}' was removed."))
        self.zijbalk.clear()
        for sleutel, naam, ic, _pad in plekken():
            self.zijbalk.voeg_toe(f"lijn:{ic}", naam, f"plek:{sleutel}")
        self.zijbalk.voeg_kop(t("Schijven", "Drives"))
        self.zijbalk.voeg_toe("lijn:laptop", t("Deze computer", "This computer"), "computer")
        for x in lijst:
            item = self.zijbalk.voeg_toe(f"lijn:{'slot' if x.op_slot else x.icoon}", x.naam, f"schijf:{x.apparaat}")
            item.setToolTip(platte_tip(self.schijf_uitleg(x)))
        self.markeer_zijbalk()
        if self.in_computer:
            self.vul_computer()
        elif not self.in_prullenbak:
            self.bouw_pad()

    def markeer_zijbalk(self) -> None:
        self.zijbalk.clearSelection()
        self.bak_lijst.clearSelection()
        if self.in_prullenbak:
            self.bak_lijst.setCurrentRow(0)
            return
        if self.in_computer:
            self.zijbalk.kies("computer")
            return
        beste, lengte = "", -1
        for sleutel, _n, _i, pad in plekken():
            if (self.huidig == pad or zit_in(self.huidig, pad)) and len(str(pad)) > lengte:
                beste, lengte = f"plek:{sleutel}", len(str(pad))
        hier = schijf_van(self.huidig, self.lijst_schijven)
        if hier and len(hier.wortel) > lengte:
            beste = f"schijf:{hier.apparaat}"
        if beste:
            self.zijbalk.kies(beste)

    def schijf(self, apparaat: str) -> Schijf | None:
        return next((x for x in self.lijst_schijven if x.apparaat == apparaat), None)

    def zijbalk_klik(self, item) -> None:
        sleutel = item.data(Qt.ItemDataRole.UserRole) or ""
        if sleutel.startswith("plek:"):
            for s, _n, _i, pad in plekken():
                if f"plek:{s}" == sleutel:
                    pad.mkdir(parents=True, exist_ok=True)
                    self.ga_naar(pad)
        elif sleutel == "computer":
            self.open_computer()
        elif sleutel.startswith("schijf:"):
            gevonden = self.schijf(sleutel[7:])
            if gevonden:
                self.open_schijf(gevonden)

    def zijbalk_menu(self, punt) -> None:
        item = self.zijbalk.itemAt(punt)
        sleutel = (item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        gevonden = self.schijf(sleutel[7:]) if sleutel.startswith("schijf:") else None
        if gevonden is None:
            return
        self.schijf_menu(gevonden).exec(self.zijbalk.mapToGlobal(punt))

    # -------------------------------------------------------- navigeren
    def ga_naar(self, pad: Path, geschiedenis: bool = True) -> None:
        pad = Path(pad)
        try:
            is_map = pad.is_dir()
        except PermissionError:
            is_map = False
        if not is_map:
            # Open voor een ander account (snel wisselen: de schijf hangt onder /run/media/<die naam>) (U387).
            delen = pad.parts
            if len(delen) > 3 and delen[1:3] in (("run", "media"),) and delen[3] != getpass.getuser():
                self.melding.toon(t(f"'{pad.name}' is geopend door {delen[3]}. Vraag die om hem veilig te verwijderen, "
                                    "en steek hem er dan opnieuw in.",
                                    f"'{pad.name}' was opened by {delen[3]}. Ask them to remove it safely, then plug it "
                                    "in again."), "let_op")
                return
            self.melding.toon(t(f"De map '{pad.name}' bestaat niet (meer).", f"The folder '{pad.name}' does not exist."), "fout")
            return
        if not os.access(pad, os.R_OK | os.X_OK):
            # Bijv. de thuismap van een ander account: niet 'deze map is leeg' laten zien (U510).
            self.melding.toon(t(f"In '{pad.name or pad}' mag je niet kijken.", f"You may not look in '{pad.name or pad}'."),
                              "let_op")
            return
        if geschiedenis and (self.in_prullenbak or self.in_computer or pad != self.huidig):
            self.terug_lijst.append(self.plek_nu())
            self.vooruit_lijst.clear()
        self.in_prullenbak = self.in_computer = False
        self.huidig = pad
        self.zoek.blockSignals(True)
        self.zoek.clear()
        self.zoek.blockSignals(False)
        self.sorteer.zet_zoek("")
        self.sorteer.wortel = str(pad)
        if self.lijst.model() is not self.sorteer:
            self.lijst.setModel(self.sorteer)
            self.lijst.selectionModel().selectionChanged.connect(lambda *_: self.ververs_staat())
        else:
            self.lijst.selectionModel().clear()  # niets uit de vorige map blijft gekozen
        bron = self.model.setRootPath(str(pad))
        self.lijst.setRootIndex(self.sorteer.mapFromSource(bron))
        self.lijst.scrollToTop()
        self.voorbeelden.vergeet()
        self.bouw_pad()
        self.markeer_zijbalk()
        self.ververs_staat()

    def plek_nu(self) -> Path:
        """Waar zijn we? (voor de terug- en vooruitknop)"""
        if self.in_prullenbak:
            return Path("::prullenbak")
        return Path("::computer") if self.in_computer else self.huidig

    def open_prullenbak(self, geschiedenis: bool = True) -> None:
        if geschiedenis and not self.in_prullenbak:
            self.terug_lijst.append(self.plek_nu())
            self.vooruit_lijst.clear()
        self.in_prullenbak, self.in_computer = True, False
        self.bak_model.clear()
        for bestand, info, herkomst in prullenbak_inhoud():
            # De echte naam (zoals Dolphin), niet die in de prullenbak ('Foto (2).jpg', of ingekort) (U086).
            it = QStandardItem(herkomst.name if herkomst and herkomst.name else bestand.name)
            it.setData(str(bestand), PAD_ROL)
            it.setData(str(info), INFO_ROL)
            it.setData(str(herkomst or ""), HERKOMST_ROL)
            it.setToolTip(platte_tip(t(f"Kwam uit: {herkomst.parent if herkomst else '?'}",
                                       f"Came from: {herkomst.parent if herkomst else '?'}")))
            it.setEditable(False)
            self.bak_model.appendRow(it)
        self.lijst.setModel(self.bak_model)
        self.lijst.setRootIndex(QModelIndex())
        self.lijst.selectionModel().selectionChanged.connect(lambda *_: self.ververs_staat())
        self.bouw_pad()
        self.markeer_zijbalk()
        self.ververs_staat()

    def terug(self) -> None:
        if not self.terug_lijst:
            return
        vorige = self.terug_lijst.pop()
        self.vooruit_lijst.append(self.plek_nu())
        self._spring(vorige)

    def vooruit(self) -> None:
        if not self.vooruit_lijst:
            return
        volgende = self.vooruit_lijst.pop()
        self.terug_lijst.append(self.plek_nu())
        self._spring(volgende)

    def _spring(self, doel: Path) -> None:
        if str(doel) == "::prullenbak":
            self.open_prullenbak(geschiedenis=False)
        elif str(doel) == "::computer":
            self.open_computer(geschiedenis=False)
        else:
            self.ga_naar(doel, geschiedenis=False)

    def omhoog(self) -> None:
        if not self.in_prullenbak and not self.in_computer and self.huidig.parent != self.huidig:
            self.ga_naar(self.huidig.parent)

    def plek_naam(self) -> str:
        """De naam die bovenin staat: het laatste stukje van het pad, of (zonder pad) de naam in de balk.

        Er is geen aparte grote titel meer; dit is dus wat de gebruiker ziet als 'waar ben ik'."""
        if not self.pad_vak.isHidden():
            # Uit de layout lezen (niet findChildren): oude kruimels staan dan al niet meer
            # in de layout, ook al heeft Qt ze nog niet echt opgeruimd (deleteLater).
            for i in range(self.pad_lay.count() - 1, -1, -1):
                w = self.pad_lay.itemAt(i).widget()
                if isinstance(w, QPushButton):
                    return w.accessibleName() or w.text()   # de hele naam, ook als hij ingekort is (U281)
            return ""
        return self.titel.text()

    def pad_passend(self) -> None:
        """Na een andere breedte: het pad opnieuw passend maken (U272)."""
        if self.pad_vak.isVisible() and self.pad_vak.width() != getattr(self, "_pad_breedte", -1):
            self.bouw_pad()

    def bouw_pad(self) -> None:
        while self.pad_lay.count():
            w = self.pad_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        in_map = not self.in_prullenbak and not self.in_computer
        self.pad_vak.setVisible(in_map)
        self.titel.setVisible(not in_map)
        self.zoek.setVisible(in_map)
        self.nieuw_knop.setVisible(in_map)
        self.ververs_plak()
        self.leeg_knop.setVisible(self.in_prullenbak)
        hier = schijf_van(self.huidig, self.lijst_schijven) if in_map else None
        self.uitwerp_knop.setVisible(bool(hier and hier.los))
        self.terug_knop.setEnabled(bool(self.terug_lijst))
        self.vooruit_knop.setEnabled(bool(self.vooruit_lijst))
        if not in_map:
            # Geen pad hier (Prullenbak, Deze computer): de naam staat dan in de balk zelf,
            # op de plek van het pad, zodat je altijd bovenin ziet waar je bent.
            titel = t("Prullenbak", "Trash") if self.in_prullenbak else t("Deze computer", "This computer")
            self.titel.setText(titel)
            self.setWindowTitle(titel)
            return
        self.setWindowTitle(f"{self.huidig.name or '/'} - {t('Bestanden', 'Files')}")
        # Van waar tellen we? Thuis, een schijf, of de hele computer.
        delen: list[tuple[str, Path]] = []
        wortel_naam, wortel = t("Computer", "Computer"), Path("/")
        if hier:
            wortel_naam, wortel = hier.naam, Path(hier.wortel)
        if wortel == Path("/") and (self.huidig == thuis() or zit_in(self.huidig, thuis())):
            wortel_naam, wortel = t("Thuis", "Home"), thuis()
        delen.append((wortel_naam, wortel))
        try:
            rest = self.huidig.resolve().relative_to(wortel.resolve()).parts
        except ValueError:
            rest = self.huidig.parts[1:]
        p = wortel
        for deel in rest:
            p = p / deel
            delen.append((deel, p))
        if len(delen) > 5:
            delen = delen[:1] + [("…", delen[-4][1])] + delen[-3:]
        # Past het niet in de balk? Lange namen in het midden inkorten ('Geschie…stuk', de hele naam als tip), en
        # zo nodig meer mappen achter '…' zetten. De laatste (waar je nu bent) blijft zo lang mogelijk heel (U272).
        # Meten met een echte knop in de stijl van het pad: de letter en wat een knop om zijn tekst heen nodig heeft.
        proef = QPushButton("x", self.pad_vak)
        proef.setObjectName("kruimel")
        proef.setProperty("laatste", "true")   # vet: reken ruim
        proef.ensurePolished()
        fm = QFontMetrics(proef.font())
        rand = proef.sizeHint().width() - fm.horizontalAdvance("x") + 16   # plus het pijltje ervoor
        proef.deleteLater()
        self._pad_breedte = self.pad_vak.width()
        ruimte = max(self.pad_vak.width() - 20, px(200))
        kort, lang = px(110), max(ruimte // 2, px(140))

        def breedte(lijst) -> int:
            return sum(min(fm.horizontalAdvance(n), lang if j == len(lijst) - 1 else kort) + rand
                       for j, (n, _d) in enumerate(lijst))

        while breedte(delen) > ruimte and len(delen) > 2:
            if delen[1][0] == "…":
                if len(delen) <= 3:
                    break
                delen = delen[:2] + delen[3:]
                delen[1] = ("…", delen[2][1].parent)
            else:
                delen = delen[:1] + [("…", delen[1][1])] + delen[2:]
        for i, (naam, doel) in enumerate(delen):
            if i:
                pijl = QLabel()
                pijl.setPixmap(lijn_icoon("rechts", "tekst3", 14, gekozen=None).pixmap(14, 14))
                self.pad_lay.addWidget(pijl)
            if i == len(delen) - 1:   # de laatste krijgt wat er over is
                maxw = max(ruimte - sum(min(fm.horizontalAdvance(n), kort) + rand for n, _d in delen[:-1]) - rand,
                           px(60))
            else:
                maxw = kort
            zichtbaar = fm.elidedText(naam, Qt.TextElideMode.ElideMiddle, maxw)
            k = QPushButton(zichtbaar.replace("&", "&&"))   # een & in een mapnaam is geen sneltoets (U210)
            if zichtbaar != naam:
                k.setToolTip(platte_tip(naam))
            # Een schermlezer hoort de hele naam, ook als hij ingekort is; '…' zegt welke map hij opent (U281).
            k.setAccessibleName(doel.name if naam == "…" else naam)
            if naam == "…":
                k.setToolTip(platte_tip(str(doel)))
            k.setObjectName("kruimel")
            k.setProperty("laatste", "true" if i == len(delen) - 1 else "false")
            k.setCursor(Qt.CursorShape.PointingHandCursor)
            k.clicked.connect(lambda _=False, d=doel: self.ga_naar(d))
            self.pad_lay.addWidget(k)
        self.pad_lay.addStretch(1)
