"""BugOS Bestanden: USB-sticks en schijven openen, beheren en veilig verwijderen.

Jip-en-Janneke: één regel per schijf, het menu '…' (naam wijzigen, repareren,
leegmaken), een nieuwe schijf in gebruik nemen, en de opdrachten die dat op de
achtergrond doen zonder dat het venster vastloopt. Dit is een stukje van het
venster (Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from bugos_ui import lijn_icoon, t
from bugos_drives import (
    MAX_NAAM, Schijf, hernoem_stappen, klaarmaak_stappen, leegmaak_stappen, mooie_maat, openen_stappen,
    repareer_stappen, schijven, uitwerp_stappen,
)
from bugos_files_plekken import schijf_van, thuis, zit_in
from bugos_files_onderdelen import SchijfRij
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QMenu


class Schijven:
    """Schijven en USB-sticks: een stukje van het venster Bestanden."""

    # --------------------------------------------- schijven en USB-sticks
    def schijf_uitleg(self, x: Schijf) -> str:
        """Een zin over een schijf, voor de uitleg en de tooltip."""
        if x.nieuw:
            return t("Nog niet in gebruik. Klik op 'In gebruik nemen' om hem klaar te maken.",
                     "Not in use yet. Click 'Set up' to get it ready.")
        maat = f"{mooie_maat(x.grootte)} · " if x.grootte else ""
        if x.op_slot:
            return maat + t("Op slot. Klik erop, dan vraagt BugOS om het wachtwoord.",
                            "Locked. Click it and BugOS asks for the password.")
        if not x.wortel:
            return maat + t("Nog dicht. Klik om te openen.", "Closed. Click to open.")
        if x.vrij is not None and x.grootte:
            return t(f"{mooie_maat(x.vrij)} vrij van {mooie_maat(x.grootte)}",
                     f"{mooie_maat(x.vrij)} free of {mooie_maat(x.grootte)}")
        return t("Open", "Open")

    def schijf_rij(self, x: Schijf) -> SchijfRij:
        """Eén regel: open = hoeveel vrij + 'Veilig verwijderen'; dicht of op slot = 'Openen'."""
        if x.wortel:
            gebruikt = 1 - x.vrij / x.grootte if x.vrij is not None and x.grootte else None
            uitleg = self.schijf_uitleg(x)
            rij = SchijfRij(x.icoon, x.naam, uitleg, gebruikt, uitwerpen=x.los)
            if rij.knop is not None:
                rij.knop.clicked.connect(lambda _c=False, g=x: self.uitwerpen(g.station))
        elif x.nieuw:
            rij = SchijfRij(x.icoon, x.naam, t("Nog niet in gebruik", "Not in use yet"), None,
                            t("In gebruik nemen", "Set up"), soort_knop="hoofd")
            rij.knop.clicked.connect(lambda _c=False, g=x: self.neem_in_gebruik(g))
        else:
            uitleg = (t("Op slot · klik om te openen", "Locked · click to open") if x.op_slot
                      else t("Nog dicht · klik om te openen", "Closed · click to open"))
            if x.grootte:
                uitleg = f"{mooie_maat(x.grootte)} · " + uitleg
            rij = SchijfRij("slot" if x.op_slot else x.icoon, x.naam, uitleg, None)
        rij.setToolTip(self.schijf_uitleg(x))
        rij.geklikt.connect(lambda g=x: self.open_schijf(g))
        rij.meer.clicked.connect(lambda _c=False, g=x, k=rij.meer: self.schijf_menu(g).exec(
            k.mapToGlobal(k.rect().bottomLeft())))
        rij.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        rij.customContextMenuRequested.connect(lambda punt, g=x, r=rij: self.schijf_menu(g).exec(r.mapToGlobal(punt)))
        return rij

    def schijf_menu(self, x: Schijf) -> QMenu:
        """Alles wat je met een stick of schijf kunt doen, in één rustig menu."""
        m = QMenu(self)

        def actie(ic: str, tekst: str, doe, aan: bool = True, kleur_: str = "tekst") -> None:
            a = m.addAction(lijn_icoon(ic, kleur_, 18, gekozen=None), tekst)
            a.triggered.connect(lambda _c=False, f=doe: f())
            a.setEnabled(aan)

        vrij_spel = x.apparaat not in self.bezig and x.station not in self.bezig
        if x.nieuw:
            actie("vink", t("In gebruik nemen…", "Set up…"), lambda: self.neem_in_gebruik(x), vrij_spel)
            if x.los:
                m.addSeparator()
                actie("uitwerpen", t("Veilig verwijderen", "Safely remove"), lambda: self.uitwerpen(x.station),
                      vrij_spel)
            return m
        actie("openen", t("Openen", "Open"), lambda: self.open_schijf(x), vrij_spel)
        if x.soort != "cd":
            m.addSeparator()
            actie("potlood", t("Naam wijzigen…", "Rename…"), lambda: self.hernoem_schijf(x),
                  vrij_spel and not x.op_slot and x.fs in MAX_NAAM)
            actie("vink", t("Controleren en repareren", "Check and repair"), lambda: self.repareer_schijf(x),
                  vrij_spel and not x.op_slot)
            # Alleen voor schijven die je eruit kunt halen: nooit per ongeluk de Windows-schijf of een
            # andere interne schijf wissen (daarvoor is Schijfbeheer, voor gevorderden).
            if x.los:
                actie("prullenbak", t("Leegmaken (alles wissen)…", "Erase (delete everything)…"),
                      lambda: self.leegmaak_schijf(x), vrij_spel, "fout")
        if x.los:
            m.addSeparator()
            actie("uitwerpen", t("Veilig verwijderen", "Safely remove"), lambda: self.uitwerpen(x.station), vrij_spel)
        return m

    def beheer(self, x: Schijf, stappen: list[list[str]], bezig: str, gelukt: str, mislukt: str) -> None:
        """Voer een beheer-klus uit op de achtergrond, met een melding voor en na."""
        if x.apparaat in self.bezig:
            return
        if not shutil.which("gdbus") or not shutil.which("udisksctl"):
            self.melding.toon(t("Dat kan hier niet.", "That is not possible here."), "fout")
            return
        if not self.in_prullenbak and not self.in_computer and x.wortel and zit_in(self.huidig, Path(x.wortel)):
            self.ga_naar(thuis())  # zelf niet meer 'in' de schijf staan
        self.bezig.add(x.apparaat)
        self.melding.toon(bezig, seconden=0)

        def klaar(ok: bool, _uitvoer: str) -> None:
            self.bezig.discard(x.apparaat)
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            self.melding.toon(gelukt if ok else mislukt, "goed" if ok else "fout", seconden=10)

        self.draai(stappen, klaar)

    def hernoem_schijf(self, x: Schijf) -> None:
        maximum = MAX_NAAM.get(x.fs, 15)
        naam = self.vraag_tekst(t("Naam wijzigen", "Rename"),
                                t(f"Nieuwe naam voor '{x.naam}' (hoogstens {maximum} tekens):",
                                  f"New name for '{x.naam}' (at most {maximum} characters):"), x.naam)
        if not naam or naam == x.naam:
            return
        if len(naam) > maximum or "/" in naam:
            self.melding.toon(t(f"Die naam is te lang of heeft een /. Hoogstens {maximum} tekens.",
                                f"That name is too long or has a /. At most {maximum} characters."), "fout")
            return
        self.beheer(x, hernoem_stappen(x, naam), t(f"Naam wijzigen naar '{naam}'…", f"Renaming to '{naam}'…"),
                    t(f"De naam is nu '{naam}'.", f"The name is now '{naam}'."),
                    t("Naam wijzigen lukte niet. Probeer het nog eens.", "Renaming did not work. Try again."))

    def repareer_schijf(self, x: Schijf) -> None:
        self.beheer(x, repareer_stappen(x),
                    t(f"'{x.naam}' controleren en repareren… Haal hem er niet uit.",
                      f"Checking and repairing '{x.naam}'… Do not unplug it."),
                    t(f"Klaar: '{x.naam}' is gecontroleerd en zo nodig gerepareerd.",
                      f"Done: '{x.naam}' was checked and repaired where needed."),
                    t(f"Repareren lukte niet. Zet de bestanden van '{x.naam}' veilig en maak hem daarna leeg.",
                      f"Repair did not work. Save the files from '{x.naam}' and erase it afterwards."))

    def leegmaak_schijf(self, x: Schijf) -> None:
        if not self.vraag_ja(t("Alles wissen?", "Erase everything?"),
                             t(f"Alles op '{x.naam}' wordt gewist. Dit kan niet ongedaan worden.\n\n"
                               "Daarna is hij leeg en werkt hij op elke computer (ook Windows en Mac).",
                               f"Everything on '{x.naam}' will be erased. This cannot be undone.\n\n"
                               "Afterwards it is empty and works on any computer (Windows and Mac too)."),
                             t("Alles wissen", "Erase everything")):
            return
        # Zit precies dezelfde schijf er nog in? (Er kan intussen een andere stick in zitten.)
        nu = next((s for s in schijven() if s.apparaat == x.apparaat), None)
        if not x.los or nu is None or (nu.station, nu.grootte, nu.naam, nu.udisks_deel) != (
                x.station, x.grootte, x.naam, x.udisks_deel):
            self.melding.toon(t(f"'{x.naam}' zit er niet meer in. Er is niets gewist.",
                                f"'{x.naam}' is no longer there. Nothing was erased."), "fout")
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            return
        naam = x.naam if len(x.naam) <= 15 and "(" not in x.naam else t("USB-stick", "USB stick")
        self.beheer(x, leegmaak_stappen(x, naam),
                    t(f"'{x.naam}' leegmaken… Haal hem er niet uit.", f"Erasing '{x.naam}'… Do not unplug it."),
                    t(f"Klaar: '{naam}' is leeg.", f"Done: '{naam}' is empty."),
                    t("Leegmaken lukte niet. Haal de stick eruit, steek hem er opnieuw in en probeer het nog eens.",
                      "Erasing did not work. Unplug the stick, plug it in again and try again."))

    def neem_in_gebruik(self, x: Schijf) -> None:
        """Een nieuwe, lege schijf klaarmaken (zoals Schijfbeheer in Windows), met één vraag: de naam."""
        standaard = t("USB-stick", "USB stick") if x.soort == "stick" else t("Opslag", "Storage")
        maximum = 15 if x.los else 16
        naam = self.vraag_tekst(
            t("In gebruik nemen", "Set up"),
            t(f"BugOS maakt '{x.naam}' klaar, zodat je er bestanden op kunt zetten. Er staat nog niets op.\n\n"
              f"Hoe moet hij heten? (hoogstens {maximum} tekens)",
              f"BugOS gets '{x.naam}' ready so you can put files on it. There is nothing on it yet.\n\n"
              f"What should it be called? (at most {maximum} characters)"), standaard,
            ok=t("In gebruik nemen", "Set up"))
        if not naam:
            return
        if len(naam) > maximum or "/" in naam:
            self.melding.toon(t(f"Die naam is te lang of heeft een /. Hoogstens {maximum} tekens.",
                                f"That name is too long or has a /. At most {maximum} characters."), "fout")
            return
        self.beheer(x, klaarmaak_stappen(x, naam),
                    t(f"'{naam}' klaarmaken… Dit duurt even.", f"Getting '{naam}' ready… This takes a moment."),
                    t(f"Klaar: '{naam}' staat nu links bij Schijven en is er voortaan altijd.",
                      f"Done: '{naam}' is now listed under Drives and will always be there."),
                    t("Klaarmaken lukte niet. Probeer het nog eens, of vraag hulp.",
                      "Setting up did not work. Try again, or ask for help."))

    def draai(self, stappen: list[list[str]], klaar, laatste: list[str] | None = None) -> None:
        """Voer opdrachten na elkaar uit, zonder dat het venster vastloopt (ook niet als KDE om een wachtwoord vraagt)."""
        rij = [list(x) for x in stappen]
        uitvoer: list[str] = []

        def start(opdracht: list[str], verder) -> None:
            proces = QProcess(self)
            gedaan = []

            def af(code: int, status) -> None:
                if gedaan:
                    return
                gedaan.append(True)
                uitvoer.append(bytes(proces.readAllStandardOutput()).decode(errors="ignore")
                               + bytes(proces.readAllStandardError()).decode(errors="ignore"))
                proces.deleteLater()
                verder(code == 0 and status == QProcess.ExitStatus.NormalExit)

            def fout(soort) -> None:
                if soort == QProcess.ProcessError.FailedToStart and not gedaan:
                    gedaan.append(True)
                    proces.deleteLater()
                    verder(False)

            proces.finished.connect(af)
            proces.errorOccurred.connect(fout)
            proces.start(opdracht[0], opdracht[1:])

        def volgende(ok: bool = True) -> None:
            if not ok:
                klaar(False, "".join(uitvoer))
            elif rij:
                start(rij.pop(0), volgende)
            elif laatste:
                start(laatste, lambda _ok: klaar(True, "".join(uitvoer)))
            else:
                klaar(True, "".join(uitvoer))

        volgende()

    def open_schijf(self, x: Schijf) -> None:
        if x.nieuw:
            self.neem_in_gebruik(x)
            return
        if x.wortel:
            self.ga_naar(Path(x.wortel))
            return
        if x.apparaat in self.bezig:
            return
        opdracht = openen_stappen(x)
        if not shutil.which(opdracht[0]):
            self.melding.toon(t(f"'{x.naam}' kan hier niet open. Probeer Dolphin (voor gevorderden).",
                                f"'{x.naam}' cannot be opened here. Try Dolphin (advanced)."), "fout")
            return
        self.bezig.add(x.apparaat)
        self.melding.toon(t(f"'{x.naam}' openen…", f"Opening '{x.naam}'…"), seconden=0)

        def klaar(ok: bool, uitvoer: str) -> None:
            self.bezig.discard(x.apparaat)
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            nu = self.schijf(x.apparaat)
            if nu and nu.wortel:
                self.melding.hide()
                self.ga_naar(Path(nu.wortel))
            elif ok and " at " in uitvoer:
                self.melding.hide()
                self.ga_naar(Path(uitvoer.rsplit(" at ", 1)[1].strip().rstrip(".")))
            elif x.op_slot:
                self.melding.toon(t("Openen lukte niet. Klopte het wachtwoord?",
                                    "Opening did not work. Was the password right?"), "fout")
            else:
                self.melding.toon(t(f"'{x.naam}' kon niet open. Haal hem eruit en steek hem er opnieuw in.",
                                    f"'{x.naam}' could not be opened. Unplug it and plug it in again."), "fout")

        self.draai([opdracht], klaar)

    def uitwerpen_hier(self) -> None:
        hier = schijf_van(self.huidig, self.lijst_schijven)
        if hier and hier.los:
            self.uitwerpen(hier.station)

    def uitwerpen(self, station: str) -> None:
        """Veilig verwijderen: alle delen van de stick dicht, dan de stroom eraf."""
        if station in self.bezig:
            return
        delen = [x for x in self.lijst_schijven if x.station == station]
        naam = delen[0].naam if delen else t("De schijf", "The drive")
        stappen, laatste = uitwerp_stappen(self.lijst_schijven, station)
        if not shutil.which("udisksctl"):
            self.melding.toon(t("Veilig verwijderen kan hier niet.", "Safe removal is not available here."), "fout")
            return
        if not self.in_prullenbak and not self.in_computer and any(
                x.wortel and zit_in(self.huidig, Path(x.wortel)) for x in delen):
            self.ga_naar(thuis())  # zelf niet meer 'in' de stick staan
        self.bezig.add(station)
        self.melding.toon(t(f"'{naam}' veilig verwijderen…", f"Safely removing '{naam}'…"), seconden=0)

        def klaar(ok: bool, _uitvoer: str) -> None:
            self.bezig.discard(station)
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            if ok:
                self.melding.toon(t(f"Je kunt '{naam}' er nu veilig uithalen.", f"You can now safely remove '{naam}'."),
                                  "goed")
            else:
                self.melding.toon(t(f"'{naam}' is nog bezig. Sluit wat erop openstaat en probeer het opnieuw.",
                                    f"'{naam}' is still busy. Close what is open on it and try again."), "fout")

        self.draai(stappen, klaar, laatste)
