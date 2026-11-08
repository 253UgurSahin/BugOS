"""BugOS Bestanden: wat je met je bestanden doet.

Jip-en-Janneke: het menu onder de rechtermuisknop, kopiëren en plakken (ook met
het klembord van KDE), naam wijzigen, een nieuwe map, weggooien met Ongedaan maken,
en de prullenbak (terugzetten, leegmaken). Dit is een stukje van het venster
(Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from bugos_ui import lijn_icoon, t
from bugos_files_plekken import INFO_ROL, PAD_ROL, thuis
from bugos_files_acties import Klus, achter_uitleg, naar_prullenbak, prullenbak_legen, terugzetten, vrije_naam, zelfde_schijf
from PySide6.QtCore import QEvent, QMimeData, Qt, QTimer, QUrl
from PySide6.QtWidgets import QApplication, QInputDialog, QLabel, QMenu, QMessageBox


class Bewerken:
    """Menu, kopiëren en plakken, weggooien en de prullenbak: een stukje van het venster Bestanden."""

    # ----------------------------------------------------------- menu
    def menu(self, punt) -> None:
        m = QMenu(self)

        def actie(ic: str, tekst: str, doe, aan: bool = True) -> None:
            a = m.addAction(lijn_icoon(ic, "tekst", 18, gekozen=None), tekst)
            a.triggered.connect(lambda _c=False, f=doe: f())
            a.setEnabled(aan)

        index = self.lijst.indexAt(punt)
        if index.isValid() and not self.lijst.selectionModel().isSelected(index):
            self.lijst.setCurrentIndex(index)
        gekozen = self.gekozen() if index.isValid() else []
        if self.in_prullenbak:
            actie("terug", t("Zet terug", "Restore"), self.zet_terug, bool(gekozen))
            m.addSeparator()
            actie("prullenbak", t("Prullenbak leegmaken", "Empty trash"), self.leegmaken,
                  self.bak_model.rowCount() > 0)
        elif gekozen:
            actie("openen", t("Openen", "Open"), self.openen)
            m.addSeparator()
            actie("kopieer", t("Kopiëren", "Copy"), self.kopieer)
            actie("schaar", t("Knippen", "Cut"), self.knip)
            actie("potlood", t("Naam wijzigen", "Rename"), self.hernoem, len(gekozen) == 1)
            m.addSeparator()
            actie("prullenbak", t("Naar de prullenbak", "Move to trash"), self.weggooien)
            if shutil.which("dolphin"):
                m.addSeparator()
                actie("oog", t("Openen in Dolphin (voor gevorderden)", "Open in Dolphin (advanced)"), self.in_dolphin)
        else:
            actie("plak", t("Plakken", "Paste"), self.plak, self.klembord_heeft_bestanden())
            actie("map-plus", t("Nieuwe map", "New folder"), self.nieuwe_map)
            if shutil.which("dolphin"):
                m.addSeparator()
                actie("oog", t("Openen in Dolphin (voor gevorderden)", "Open in Dolphin (advanced)"), self.in_dolphin)
        m.exec(self.lijst.viewport().mapToGlobal(punt))

    def in_dolphin(self) -> None:
        subprocess.Popen(["dolphin", str(self.huidig)], start_new_session=True)

    # ------------------------------------------- kopiëren en plakken
    def _naar_klembord(self, knip: bool) -> None:
        paden = self.gekozen()
        if not paden or self.in_prullenbak:
            return
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in paden])
        data.setData("application/x-kde-cutselection", b"1" if knip else b"0")
        regels = ["cut" if knip else "copy"] + [QUrl.fromLocalFile(str(p)).toString() for p in paden]
        data.setData("x-special/gnome-copied-files", "\n".join(regels).encode())
        zet_op_klembord(data)
        n = len(paden)
        self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} {'geknipt' if knip else 'gekopieerd'}. Ga naar een map en kies Plakken.",
                            f"{n} {'item' if n == 1 else 'items'} {'cut' if knip else 'copied'}. Go to a folder and choose Paste."))

    def kopieer(self) -> None:
        self._naar_klembord(False)

    def knip(self) -> None:
        self._naar_klembord(True)

    def klembord_heeft_bestanden(self) -> bool:
        data = QApplication.clipboard().mimeData()
        return bool(data and data.hasUrls() and any(u.isLocalFile() for u in data.urls()))

    def plak(self) -> None:
        if self.in_prullenbak or self.in_computer or not self.klembord_heeft_bestanden() or \
                (self.klus and self.klus.isRunning()):
            return
        data = QApplication.clipboard().mimeData()
        bronnen = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile() and Path(u.toLocalFile()).exists()]
        knip = bytes(data.data("application/x-kde-cutselection")).strip() == b"1" or \
            bytes(data.data("x-special/gnome-copied-files")).startswith(b"cut")
        if not bronnen:
            return
        self._start_klus(bronnen, self.huidig, knip)

    def _start_klus(self, bronnen: list[Path], doelmap: Path, knip: bool, klembord: bool = True) -> None:
        """Kopiëren of verplaatsen op de achtergrond, met een melding per stap (klembord: het kwam van Plakken)."""
        self.klus = Klus(bronnen, doelmap, knip)
        self.klus.voortgang.connect(lambda i, n: self.melding.toon(
            t(f"Bezig met {'verplaatsen' if knip else 'kopiëren'}: {i + 1} van {n}…", f"{'Moving' if knip else 'Copying'}: {i + 1} of {n}…"),
            seconden=0))
        self.klus.wegschrijven.connect(lambda: self.melding.toon(
            t("Bezig met wegschrijven… Haal de stick er nog niet uit.", "Writing to the stick… Do not unplug it yet."),
            seconden=0))
        klus = self.klus
        self.klus.klaar.connect(lambda gelukt, fout: self._klus_klaar(gelukt, fout, knip, klus.achter, klembord))
        self.klus.start()

    # ---------------------------------------------- slepen en loslaten
    def slepen(self, e, waar) -> bool:
        """Iets uit een ander venster (of uit deze map) hierheen gesleept: kopiëren, met Shift verplaatsen.
        Laat je het op een map los, dan gaat het in die map. Geeft True als wij het afhandelen."""
        data = e.mimeData()
        bronnen = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()] if data and data.hasUrls() else []
        bronnen = [b for b in bronnen if b.exists() or b.is_symlink()]
        if not bronnen or self.in_prullenbak or self.in_computer or (self.klus and self.klus.isRunning()):
            return False
        doelmap = self.huidig
        if waar is self.lijst.viewport():
            index = self.lijst.indexAt(e.position().toPoint())
            pad = Path(index.data(PAD_ROL)) if index.isValid() and index.data(PAD_ROL) else None
            if pad and pad.is_dir() and pad not in bronnen:
                doelmap = pad
        if all(b.parent == doelmap for b in bronnen):
            return False  # staat er al: niets te doen
        if e.type() == QEvent.Type.Drop:
            knip = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._start_klus(bronnen, doelmap, knip, klembord=False)
        # Altijd 'kopiëren' terugzeggen: verplaatsen doen we zelf, het andere programma hoeft niets weg te gooien.
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()
        return True

    def _klus_klaar(self, gelukt: int, fout: str, knip: bool, achter: list | None = None,
                    klembord: bool = True) -> None:
        if fout:
            self.melding.toon(t(f"Niet alles lukte: {fout}", f"Not everything worked: {fout}"), "fout", seconden=12)
        elif achter:  # bijv. een naam met ':' op een USB-stick: de rest staat er wel
            self.melding.toon(achter_uitleg(achter, knip), "let_op", seconden=0)
        else:
            self.melding.toon(t(f"Klaar: {gelukt} {'ding' if gelukt == 1 else 'dingen'} {'verplaatst' if knip else 'gekopieerd'}.",
                                f"Done: {gelukt} {'item' if gelukt == 1 else 'items'} {'moved' if knip else 'copied'}."), "goed")
        if knip and klembord:
            QApplication.clipboard().clear()
        if self.sluit_na_klus:
            QTimer.singleShot(0, self.close)

    # ------------------------------------------------------------ vragen
    def vraag_tekst(self, titel: str, vraag: str, tekst: str, ok: str = "") -> str | None:
        d = QInputDialog(self)
        d.setWindowTitle(titel)
        d.setLabelText(vraag)
        d.setTextValue(tekst)
        d.setOkButtonText(ok or t("Klaar", "OK"))
        d.setCancelButtonText(t("Annuleren", "Cancel"))
        for uitleg in d.findChildren(QLabel):
            uitleg.setWordWrap(True)  # lange uitleg netjes over een paar regels
        d.resize(460, d.sizeHint().height())
        return d.textValue().strip() if d.exec() else None

    def vraag_ja(self, titel: str, tekst: str, ja: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(titel)
        box.setText(tekst)
        box.setIcon(QMessageBox.Icon.Warning)
        ja_knop = box.addButton(ja, QMessageBox.ButtonRole.DestructiveRole)
        nee = box.addButton(t("Annuleren", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(nee)
        box.exec()
        return box.clickedButton() is ja_knop

    # ------------------------------------------- naam, map, weggooien
    def hernoem(self) -> None:
        paden = self.gekozen()
        if len(paden) != 1 or self.in_prullenbak:
            return
        oud = paden[0]
        nieuw = self.vraag_tekst(t("Naam wijzigen", "Rename"), t("Nieuwe naam:", "New name:"), oud.name)
        if not nieuw or nieuw == oud.name:
            return
        if "/" in nieuw or nieuw in (".", ".."):
            self.melding.toon(t("Een naam mag geen / bevatten.", "A name cannot contain /."), "fout")
            return
        doel = oud.with_name(nieuw)
        # Op een USB-stick (FAT/exFAT) zijn Foto.JPG en Foto.jpg hetzelfde bestand: dan is het
        # alleen andere hoofdletters, en dat mag gewoon.
        try:
            alleen_hoofdletters = nieuw.lower() == oud.name.lower() and doel.exists() and oud.samefile(doel)
        except OSError:
            alleen_hoofdletters = False
        if (doel.exists() or doel.is_symlink()) and not alleen_hoofdletters:  # ook een kapotte snelkoppeling niet overschrijven
            self.melding.toon(t(f"Er staat al iets met de naam '{nieuw}'.", f"Something named '{nieuw}' already exists."), "fout")
            return
        try:
            oud.rename(doel)
        except OSError as e:
            self.melding.toon(t(f"Naam wijzigen lukte niet: {e.strerror}", f"Rename failed: {e.strerror}"), "fout")

    def nieuwe_map(self) -> None:
        if self.in_prullenbak or self.in_computer:
            return
        naam = self.vraag_tekst(t("Nieuwe map", "New folder"), t("Naam van de map:", "Folder name:"),
                                t("Nieuwe map", "New folder"))
        if not naam:
            return
        if "/" in naam:
            self.melding.toon(t("Een naam mag geen / bevatten.", "A name cannot contain /."), "fout")
            return
        doel = vrije_naam(self.huidig / naam)
        try:
            doel.mkdir()
            QTimer.singleShot(300, lambda: self.selecteer(doel))
        except OSError as e:
            self.melding.toon(t(f"De map maken lukte niet: {e.strerror}", f"Could not make the folder: {e.strerror}"), "fout")

    def weggooien(self) -> None:
        if self.in_prullenbak:
            return
        paden = self.gekozen()
        if not paden:
            return
        ver = [p for p in paden if not zelfde_schijf(p, thuis())]
        if ver:
            if not self.vraag_ja(t("Echt weggooien?", "Really delete?"),
                                 t("Dit staat op een USB-stick of een andere schijf. Weggooien kan daar niet ongedaan "
                                   "worden. Echt weggooien?",
                                   "This is on a USB stick or another drive. Deleting there cannot be undone. "
                                   "Really delete?"),
                                 t("Weggooien", "Delete")):
                return
        weg, fout = [], ""
        for p in paden:
            try:
                if p in ver:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                else:
                    weg.append(naar_prullenbak(p))
            except OSError as e:
                fout = e.strerror or str(e)
        self.laatst_weg = weg
        if fout:
            self.melding.toon(t(f"Niet alles kon weg: {fout}", f"Not everything could be deleted: {fout}"), "fout")
        elif weg:
            n = len(weg)
            self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} naar de prullenbak.", f"{n} {'item' if n == 1 else 'items'} moved to the trash."),
                              knop=t("Ongedaan maken", "Undo"), actie=self.ongedaan, seconden=10)

    def ongedaan(self) -> None:
        mislukt = 0
        for bestand, info in self.laatst_weg:
            try:
                terugzetten(bestand, info)
            except OSError:
                mislukt += 1
        self.laatst_weg = []
        if mislukt:
            self.melding.toon(t(f"{mislukt} {'ding kon' if mislukt == 1 else 'dingen konden'} niet terug. "
                                "Kijk in de prullenbak.",
                                f"{mislukt} {'item' if mislukt == 1 else 'items'} could not be restored. "
                                "Look in the trash."), "fout")
        else:
            self.melding.toon(t("Teruggezet.", "Restored."), "goed")

    # ------------------------------------------------------ prullenbak
    def zet_terug(self) -> None:
        if not self.in_prullenbak:
            return
        sel = self.lijst.selectionModel().selectedIndexes()
        n = mislukt = 0
        for i in sel:
            try:
                terugzetten(Path(i.data(PAD_ROL)), Path(i.data(INFO_ROL)))
                n += 1
            except OSError:
                mislukt += 1
        self.open_prullenbak(geschiedenis=False)
        if mislukt:
            self.melding.toon(t(f"{n} teruggezet, {mislukt} {'lukte' if mislukt == 1 else 'lukten'} niet "
                                "(is de plek waar het stond er nog, en mag je daar schrijven?).",
                                f"{n} restored, {mislukt} could not be restored "
                                "(does the original place still exist, and may you write there?)."), "fout")
        elif n:
            self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} teruggezet.", f"{n} {'item' if n == 1 else 'items'} restored."), "goed")

    def leegmaken(self) -> None:
        if self.vraag_ja(t("Prullenbak leegmaken?", "Empty the trash?"),
                         t("Alles in de prullenbak wordt echt weggegooid. Dit kan niet ongedaan worden.",
                           "Everything in the trash will be deleted for good. This cannot be undone."),
                         t("Leegmaken", "Empty")):
            mislukt = prullenbak_legen()
            self.open_prullenbak(geschiedenis=False)
            if mislukt:
                self.melding.toon(t(f"{mislukt} {'ding kon' if mislukt == 1 else 'dingen konden'} niet weg. "
                                    "Ze staan nog in de prullenbak.",
                                    f"{mislukt} {'item' if mislukt == 1 else 'items'} could not be deleted. "
                                    "They are still in the trash."), "fout")
            else:
                self.melding.toon(t("De prullenbak is leeg.", "The trash is empty."), "goed")


_ONS_KLEMBORD: list[QMimeData] = []  # wat wij zelf op het klembord hebben gezet


def zet_op_klembord(data: QMimeData) -> None:
    _ONS_KLEMBORD[:] = [data]
    QApplication.clipboard().setMimeData(data)


def laat_klembord_los() -> None:
    """Wat wij op het klembord zetten, ruimen we zelf op voordat het programma stopt.

    Anders ruimt Qt het pas op als Python al weg is, en dan crasht het programma bij het
    afsluiten. De klembordbeheerder van KDE heeft het al bewaard, dus plakken kan daarna nog.
    """
    klembord = QApplication.clipboard()
    if klembord is None or not _ONS_KLEMBORD:
        return
    try:
        nog_van_ons = klembord.ownsClipboard() or klembord.mimeData() is _ONS_KLEMBORD[0]
    except RuntimeError:
        nog_van_ons = False
    _ONS_KLEMBORD.clear()
    if nog_van_ons:
        klembord.clear()
