"""BugOS Bestanden: USB-sticks en schijven openen, beheren en veilig verwijderen.

Jip-en-Janneke: één regel per schijf, het menu '…' (naam wijzigen, repareren,
leegmaken), een nieuwe schijf in gebruik nemen, en de opdrachten die dat op de
achtergrond doen zonder dat het venster vastloopt. Dit is een stukje van het
venster (Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from bugos_ui import lijn_icoon, platte_tip, t
from bugos_drives import (
    MAX_NAAM, VERBORGEN_FS, VERBORGEN_TYPES, Schijf, _alle, _plekken_van, dicht_stappen, fstab_noemt, fstab_sleutels,
    hernoem_stappen, klaarmaak_stappen, leegmaak_stappen, lees_lsblk, mooie_maat, op_media_plek, openen_stappen,
    repareer_stappen, schijven, stations_in_gebruik, systeem_plek, uitwerp_stappen,
)
from bugos_files_plekken import schijf_van, thuis, zit_in
from bugos_files_onderdelen import SchijfRij
from PySide6.QtCore import QProcess, Qt, QTimer
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
        rij.setToolTip(platte_tip(self.schijf_uitleg(x)))
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
            # Een stick of externe schijf: leegmaken (exFAT, werkt overal), behalve als het systeem hem zelf gebruikt
            # (BugOS draait ervan). Een tweede schijf in de computer alleen als hij nergens van opstart (geen
            # Windows, geen BugOS, geen ander systeem): dan helemaal wissen en opnieuw in gebruik nemen, zoals
            # 'Schijven en volumes' in Windows 11 (zie wis_bezwaar). Nooit de schijf van Windows.
            if x.los:
                if not los_in_gebruik(x):
                    actie("prullenbak", t("Leegmaken (alles wissen)…", "Erase (delete everything)…"),
                          lambda: self.leegmaak_schijf(x), vrij_spel, "fout")
            elif wisbare_interne_schijf(x):
                actie("prullenbak", t("Leegmaken (alles wissen)…", "Erase (delete everything)…"),
                      lambda: self.wis_interne_schijf(x), vrij_spel, "fout")
        if x.los:
            m.addSeparator()
            actie("uitwerpen", t("Veilig verwijderen", "Safely remove"), lambda: self.uitwerpen(x.station), vrij_spel)
        return m

    def _na_schijfklus(self, ok: bool) -> None:
        """Wilde je het venster al sluiten tijdens een schijfklus? Dan nu (als alles klaar is en lukte) (U207)."""
        if getattr(self, "sluit_na_klus", False) and not self.bezig and not (self.klus and self.klus.isRunning()):
            if ok:
                self.close()
            else:
                self.sluit_na_klus = False   # mislukt: open laten, zodat je de melding ziet

    def beheer(self, x: Schijf, stappen: list, bezig: str, gelukt: str, mislukt: str,
               weer_open: bool = False) -> None:
        """Voer een beheer-klus uit op de achtergrond, met een melding voor en na. Een stap is een opdracht
        (['udisksctl', ...]) of een controle (een functie die True of False geeft, zie draai)."""
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
            QTimer.singleShot(0, lambda ok=ok: self._na_schijfklus(ok))
            self.vul_zijbalk()
            self.melding.toon(gelukt if ok else mislukt, "goed" if ok else "fout", seconden=10)

        # Naam wijzigen en repareren: de laatste stap zet hem weer open. Ook als het mislukte, anders blijft de
        # stick 'dicht' staan (U141).
        if weer_open and stappen and isinstance(stappen[-1], list) and stappen[-1][:2] == ["udisksctl", "mount"]:
            self.draai(stappen[:-1], klaar, altijd=stappen[-1])
        else:
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
                    t("Naam wijzigen lukte niet. Probeer het nog eens.", "Renaming did not work. Try again."),
                    weer_open=True)

    def repareer_schijf(self, x: Schijf) -> None:
        self.beheer(x, repareer_stappen(x),
                    t(f"'{x.naam}' controleren en repareren… Haal hem er niet uit.",
                      f"Checking and repairing '{x.naam}'… Do not unplug it."),
                    t(f"Klaar: '{x.naam}' is gecontroleerd en zo nodig gerepareerd.",
                      f"Done: '{x.naam}' was checked and repaired where needed."),
                    # Niet meteen 'maak hem leeg' zeggen: vaak kon het controleren hier alleen niet (U141).
                    t(f"'{x.naam}' kon hier niet gecontroleerd worden. Je bestanden staan er nog. Doet hij raar? "
                      "Zet je bestanden dan eerst veilig.",
                      f"'{x.naam}' could not be checked here. Your files are still on it. Does it act strangely? "
                      "Then save your files first."),
                    weer_open=True)

    def leegmaak_schijf(self, x: Schijf) -> None:
        if not self.vraag_ja(t("Alles wissen?", "Erase everything?"),
                             t(f"Alles op '{x.naam}' wordt gewist. Dit kan niet ongedaan worden.\n\n"
                               "Daarna is hij leeg en werkt hij op elke computer (ook Windows en Mac).",
                               f"Everything on '{x.naam}' will be erased. This cannot be undone.\n\n"
                               "Afterwards it is empty and works on any computer (Windows and Mac too)."),
                             t("Alles wissen", "Erase everything")):
            return
        # Zit precies dezelfde schijf er nog in? (Er kan intussen een andere stick in zitten.) En gebruikt het
        # systeem hem niet zelf (BugOS draait ervan)?
        nu = next((s for s in schijven() if s.apparaat == x.apparaat), None)
        if not x.los or nu is None or los_in_gebruik(x) or (nu.station, nu.grootte, nu.naam, nu.udisks_deel) != (
                x.station, x.grootte, x.naam, x.udisks_deel):
            self.melding.toon(t(f"'{x.naam}' zit er niet meer in. Er is niets gewist.",
                                f"'{x.naam}' is no longer there. Nothing was erased."), "fout")
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            return
        naam = x.naam if len(x.naam) <= MAX_NAAM["exfat"] and "(" not in x.naam else \
            (t("SD-kaart", "SD card") if x.soort == "kaart" else t("USB-stick", "USB stick"))   # (U151)
        self.beheer(x, leegmaak_stappen(x, naam),
                    t(f"'{x.naam}' leegmaken… Haal hem er niet uit.", f"Erasing '{x.naam}'… Do not unplug it."),
                    t(f"Klaar: '{naam}' is leeg.", f"Done: '{naam}' is empty."),
                    t("Leegmaken lukte niet. Haal de stick eruit, steek hem er opnieuw in en probeer het nog eens.",
                      "Erasing did not work. Unplug the stick, plug it in again and try again."))

    def wis_interne_schijf(self, x: Schijf) -> None:
        """Een tweede schijf in de computer (bijvoorbeeld de oude D: van Windows) helemaal wissen en opnieuw in
        gebruik nemen. Eerst een duidelijke vraag met de naam en de grootte; Enter uit gewoonte doet niets.

        Vier sloten, elk apart genoeg om niets te wissen: (1) wis_bezwaar vóór de vraag (zie de regels daar),
        (2) na de vraag opnieuw, en het moet nog precies dezelfde schijf zijn, (3) na het dichtzetten, vlak vóór het
        wissen, wis_controle (alles echt dicht, nog steeds dezelfde schijf), en (4) udisks vraagt zelf het
        beheerderswachtwoord voor een schijf in de computer."""
        st = _station_lsblk(x.station) if x.station else None
        if st is None or wis_bezwaar(x):
            self.melding.toon(t("Deze schijf kun je hier niet wissen.", "You cannot erase this drive here."), "fout")
            return
        voor = _identiteit(st)
        delen = [s for s in self.lijst_schijven if s.station == x.station]
        namen = ", ".join(f"'{s.naam}'" for s in delen) or f"'{x.naam}'"
        maat = mooie_maat(int(st.get("size") or 0) or x.grootte)
        if not self.vraag_ja(t("Deze schijf helemaal wissen?", "Erase this whole drive?"),
                             t("Alles op deze schijf in je computer ({maat}) wordt gewist: {namen}, met alle bestanden "
                               "erop. Dit kan niet ongedaan worden.\n\nZet eerst over wat je wilt houden. Daarna is "
                               "de schijf leeg en klaar voor gebruik in deze computer. BugOS vraagt het "
                               "beheerderswachtwoord.",
                               "Everything on this drive in your computer ({maat}) will be erased: {namen}, with all "
                               "the files on it. This cannot be undone.\n\nCopy what you want to keep first. "
                               "Afterwards the drive is empty and ready to use in this computer. BugOS asks for the "
                               "administrator password.").replace("{maat}", maat).replace("{namen}", namen),
                             t("Alles wissen", "Erase everything")):
            return
        # Zit precies dezelfde schijf er nog (zelfde grootte, zelfde indeling, zelfde stukken), en mag het nog steeds?
        # (Terwijl de vraag openstond, kan er van alles veranderd zijn.) Anders niets doen.
        nu = _station_lsblk(x.station)
        if nu is None or _identiteit(nu) != voor or wis_bezwaar(x):
            self.melding.toon(t("De schijf is veranderd. Er is niets gewist.",
                                "The drive has changed. Nothing was erased."), "fout")
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            return
        naam = x.naam if len(x.naam) <= MAX_NAAM["ext4"] and "(" not in x.naam else t("Opslag", "Storage")
        # Alles op deze schijf dicht (en een geopend slot weer op slot), uit wat lsblk nú zegt: niet uit de lijst in
        # de zijbalk, die kan een paar seconden oud zijn.
        dicht = [s for s in schijven([nu]) if s.station == x.station]
        stappen: list = [stap for s in dicht for stap in dicht_stappen(s)]
        # Vlak vóór het wissen nog één keer kijken: staat er echt niets meer open? Nee: dan stopt de rij hier en
        # wordt er niets gewist (draai behandelt dit als een opdracht die mislukt).
        stappen.append(lambda: wis_controle(x.station, voor))
        stappen += klaarmaak_stappen(Schijf(apparaat=x.station, naam=naam, soort="intern", station=x.station), naam)
        self.beheer(x, stappen,
                    t("De schijf wissen en klaarmaken… Dit duurt even.",
                      "Erasing and setting up the drive… This takes a moment."),
                    t("Klaar: '{naam}' is leeg en staat links bij Schijven.",
                      "Done: '{naam}' is empty and listed under Drives.").replace("{naam}", naam),
                    t("Wissen lukte niet. Er kan nog iets open zijn op de schijf: sluit dat en probeer het opnieuw.",
                      "Erasing did not work. Something may still be open on the drive: close it and try again."))

    def neem_in_gebruik(self, x: Schijf) -> None:
        """Een nieuwe, lege schijf klaarmaken (zoals Schijfbeheer in Windows), met één vraag: de naam."""
        standaard = t("USB-stick", "USB stick") if x.soort == "stick" else t("Opslag", "Storage")
        maximum = MAX_NAAM["exfat"] if x.los else 16   # een losse schijf wordt exFAT
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
        # Zit precies dezelfde lege schijf er nog in? Terwijl je een naam koos, kan er een andere stick op dezelfde
        # plek zijn gekomen: die mag niet gewist worden (zoals bij 'Leegmaken') (U369).
        nu = next((s for s in schijven() if s.station == x.station), None)
        if nu is None or not nu.nieuw or (nu.grootte, nu.udisks_deel) != (x.grootte, x.udisks_deel):
            self.melding.toon(t(f"'{x.naam}' zit er niet meer in. Er is niets veranderd.",
                                f"'{x.naam}' is no longer there. Nothing was changed."), "fout")
            self._zijbalk_sleutels = None
            self.vul_zijbalk()
            return
        self.beheer(x, klaarmaak_stappen(x, naam),
                    t(f"'{naam}' klaarmaken… Dit duurt even.", f"Getting '{naam}' ready… This takes a moment."),
                    t(f"Klaar: '{naam}' staat nu links bij Schijven en is er voortaan altijd.",
                      f"Done: '{naam}' is now listed under Drives and will always be there."),
                    t("Klaarmaken lukte niet. Probeer het nog eens, of vraag hulp.",
                      "Setting up did not work. Try again, or ask for help."))

    def draai(self, stappen: list, klaar, laatste: list[str] | None = None,
              altijd: list[str] | None = None) -> None:
        """Voer opdrachten na elkaar uit, zonder dat het venster vastloopt (ook niet als KDE om een wachtwoord vraagt).

        Een stap kan ook een controle zijn: een functie zonder argumenten. Geeft die False (of gaat hij mis), dan
        stopt de rij daar, net als bij een opdracht die mislukt. Zo kijkt 'wissen' vlak vóór het formatteren nog
        of alles echt dicht is."""
        rij = [x if callable(x) else list(x) for x in stappen]
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
                if altijd:   # ook na een fout (bijv. de schijf weer openzetten)
                    start(altijd, lambda _ok: klaar(False, "".join(uitvoer)))
                else:
                    klaar(False, "".join(uitvoer))
            elif rij:
                stap = rij.pop(0)
                if callable(stap):
                    try:
                        goed = bool(stap())
                    except Exception:  # noqa: BLE001  een controle die misgaat, is een 'nee'
                        goed = False
                    volgende(goed)
                else:
                    start(stap, volgende)
            elif altijd:
                start(altijd, lambda ok2: klaar(ok2, "".join(uitvoer)))
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
            self.melding.toon(t("'{naam}' kan hier niet open. Haal hem eruit en steek hem er opnieuw in.",
                                "'{naam}' cannot be opened here. Unplug it and plug it in again.").replace(
                                    "{naam}", x.naam), "fout")
            return
        self.bezig.add(x.apparaat)
        self.melding.toon(t(f"'{x.naam}' openen…", f"Opening '{x.naam}'…"), seconden=0)

        def klaar(ok: bool, uitvoer: str) -> None:
            self.bezig.discard(x.apparaat)
            self._zijbalk_sleutels = None
            QTimer.singleShot(0, lambda ok=ok: self._na_schijfklus(ok))
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
        # Loopt er in dit venster nog een kopie (naar of van deze schijf)? Dan niet: tussen twee bestanden is de stick
        # even 'vrij', en dan zei BugOS 'je mag hem eruit halen' terwijl het kopiëren nog bezig was (U386).
        if self.klus is not None and self.klus.isRunning():
            self.melding.toon(t("Even wachten: er loopt nog iets (kopiëren of weggooien).",
                                "One moment: something is still busy (copying or deleting)."), "let_op")
            return
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
            QTimer.singleShot(0, lambda ok=ok: self._na_schijfklus(ok))
            self.vul_zijbalk()
            if ok:
                self.melding.toon(t(f"Je kunt '{naam}' er nu veilig uithalen.", f"You can now safely remove '{naam}'."),
                                  "goed")
            else:
                self.melding.toon(t(f"'{naam}' is nog bezig. Sluit wat erop openstaat en probeer het opnieuw.",
                                    f"'{naam}' is still busy. Close what is open on it and try again."), "fout")

        self.draai(stappen, klaar, laatste)


# ===================================================== een interne schijf wissen ===
# Wissen kan niet ongedaan worden. Daarom is elke regel hieronder een 'nee' die altijd wint: BugOS wist alleen een
# losse dataschijf in de computer (de oude D: van Windows), en alleen als het álles op die schijf heeft kunnen
# bekijken. Nooit de schijf van BugOS zelf, nooit de schijf waar BugOS van draait (ook niet de live-stick), nooit
# een schijf die het systeem gebruikt (iets wat ergens anders open staat dan bij jou, /etc/fstab, swap, een btrfs
# of RAID over meer schijven), en nooit een schijf waar een besturingssysteem op staat of van opstart.
# Liever een keer 'dat kan hier niet' te veel dan één keer de verkeerde schijf leeg.

# Stukken die iets opstarten of bij een systeem horen: EFI, 'gereserveerd voor Microsoft', Windows-herstel en
# BIOS-opstart (VERBORGEN_TYPES), en de vaste soorten van Linux (systemd 'Discoverable Partitions') en macOS.
OPSTART_TYPES = VERBORGEN_TYPES | {
    "4f68bce3-e8cd-4db1-96e7-fbcaf984b709",  # Linux: het systeem zelf (x86-64)
    "b921b045-1df0-41c3-af44-4c6f280d3fae",  # Linux: het systeem zelf (ARM 64)
    "8484680c-9521-48c6-9c11-b0720656f69e",  # Linux: /usr (x86-64)
    "bc13c2ff-59e6-4262-a352-b275fd6f7172",  # Linux: /boot (XBOOTLDR)
    "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f",  # Linux: swap
    "4d21b016-b534-45c2-a9fb-5c16e091fd2d",  # Linux: /var
    "e6d6d379-f507-44c2-a23c-238f2a3df928",  # Linux: LVM
    "a19d880f-05fc-4d3b-a006-743f0f84911e",  # Linux: RAID
    "48465300-0000-11aa-aa11-00306543ecac",  # macOS: HFS+
    "7c3457ef-0000-11aa-aa11-00306543ecac",  # macOS: APFS
    "426f6f74-0000-11aa-aa11-00306543ecac",  # macOS: opstarten
    "0x82", "0x8e", "0xfd", "0xa5", "0xa6", "0xa9", "0xaf",   # oude indeling: swap, LVM, RAID, BSD, macOS
}
# Een opstartmedium dat als schijf in de computer zit (de live-stick als schijf in een virtuele computer).
OPSTART_FS = {"iso9660", "udf"}
# Waaraan BugOS een besturingssysteem herkent op een stuk dat open staat (bovenin dat stuk).
OS_TEKENS = ("Windows/System32", "bootmgr", "EFI", "etc/os-release", "usr/lib/os-release", "ostree", "boot/loader",
             "loader/entries", "grub", "grub2", "boot/grub", "boot/grub2", "root/ostree", "root/etc/os-release",
             "root/usr/lib/os-release", "@/etc/os-release", "@/usr/lib/os-release")


def _station_lsblk(station: str) -> dict | None:
    """Wat lsblk nu over dit hele apparaat zegt (de ruwe regel, met alle stukken eronder); None als het er niet
    (meer) is."""
    for st in lees_lsblk():
        if (st.get("path") or f"/dev/{st.get('name')}") == station and st.get("type") == "disk":
            return st
    return None


def _identiteit(st: dict) -> tuple:
    """Waaraan je deze schijf herkent, los van wat er open staat: grootte, indeling (met haar eigen nummer) en per
    stuk het pad, de soort, het bestandssysteem, de UUID en de grootte. Zo wordt nooit een andere schijf gewist die
    intussen dezelfde naam (/dev/sdb) kreeg."""
    stukken = tuple((a.get("path") or a.get("name") or "", str(a.get("parttype") or "").lower(), a.get("fstype") or "",
                     str(a.get("uuid") or "").lower(), str(a.get("size") or ""))
                    for a in st.get("children") or [] if a.get("type") == "part")
    return (str(st.get("size") or ""), str(st.get("ptuuid") or "").lower(), str(st.get("pttype") or "").lower(),
            st.get("fstype") or "", stukken)


def _opstart_vlag(a: dict, tabel: str) -> bool:
    """Staat de opstart-vlag aan? Oude indeling (MBR): 'actief' (0x80), zo start de BIOS ervan op (Windows, en
    Linux zoals Anaconda het op een oude pc installeert). GPT: 'nodig voor het platform' (bit 0) of 'legacy BIOS
    bootable' (bit 2)."""
    try:
        vlag = int(str(a.get("partflags") or ""), 16)
    except ValueError:
        return False
    return bool(vlag & 0x80) if tabel == "dos" else bool(vlag & 0x5)


def _os_teken(plek: str) -> bool:
    """Staat er bovenin dit open stuk iets van een besturingssysteem (Windows, Linux, een opstartmap)?"""
    return any(os.path.lexists(os.path.join(plek, teken)) for teken in OS_TEKENS)


def _te_bekijken(a: dict) -> bool:
    """Kon BugOS zien wat er op dit stuk staat? Alleen als het open staat (op een plek van udisks voor jou), of een
    geopend slot is met daarin iets dat open staat. Dicht, op slot of zonder herkenbaar bestandssysteem: niet te
    zien, en wat je niet kunt zien, wist BugOS niet."""
    if _plekken_van(a):
        return True
    kinderen = a.get("children") or []
    return (a.get("fstype") or "") == "crypto_LUKS" and bool(kinderen) and all(_te_bekijken(k) for k in kinderen)


def _bezwaar(st: dict, na_dicht: bool = False) -> str:
    """Waarom deze hele schijf (een lsblk-regel) niet gewist mag worden, in een paar woorden; '' als het mag.

    na_dicht: de laatste controle vlak vóór het wissen, nadat BugOS alles heeft dichtgezet. Dan mag er niets meer
    open staan en niets meer 'boven' een stuk hangen (een geopend slot, LVM)."""
    if st.get("type") != "disk":
        return "geen hele schijf"
    if st.get("rm") or st.get("hotplug") or st.get("tran") == "usb":
        return "een losse schijf"   # sticks en externe schijven: daarvoor is 'Leegmaken' (exFAT)
    if (st.get("kname") or st.get("name") or "") in stations_in_gebruik():
        return "in gebruik door het systeem"
    tabel = str(st.get("pttype") or "").lower()
    if not tabel and any(str(k.get("parttype") or "").startswith("0x") for k in st.get("children") or []):
        tabel = "dos"   # lsblk zonder PTTYPE: een soort als '0x07' bestaat alleen op de oude indeling (MBR)
    sleutels = fstab_sleutels()
    stukken = [k for k in st.get("children") or [] if k.get("type") == "part"] or ([st] if st.get("fstype") else [])
    if not stukken:
        return "er staat niets op"   # een lege schijf neem je in gebruik, die hoeft niet gewist
    for a in _alle(st):
        soort, fs = str(a.get("parttype") or "").lower(), a.get("fstype") or ""
        if soort in OPSTART_TYPES:
            return "een opstart- of systeemdeel"
        if _opstart_vlag(a, tabel):
            return "de opstart-vlag staat aan"
        if fs in VERBORGEN_FS or fs in OPSTART_FS or fs == "BitLocker":
            return "een systeemdeel (swap, LVM, RAID, BitLocker of een opstartmedium)"
        if fstab_noemt(a, sleutels):
            return "staat in /etc/fstab of /etc/crypttab"
        if tabel == "dos" and fs == "ntfs":
            return "Windows op de oude indeling"   # niet te zien of Windows ervan opstart
        for m in _plekken_van(a):
            if systeem_plek(m) or not op_media_plek(m):
                return "in gebruik door het systeem"
            if na_dicht:
                return "staat nog open"
            if _os_teken(m):
                return "er staat een besturingssysteem op"
        if na_dicht and a is not st and a.get("type") != "part":
            return "nog in gebruik (een geopend slot of LVM)"
    if not na_dicht and not all(_te_bekijken(a) for a in stukken):
        return "nog dicht: BugOS kan niet zien wat erop staat"
    return ""


def wis_bezwaar(x: Schijf) -> str:
    """Waarom de schijf onder dit stuk niet gewist mag worden; '' als het mag (een interne dataschijf)."""
    if x.soort != "intern" or x.nieuw or not x.station:
        return "geen interne dataschijf"
    st = _station_lsblk(x.station)
    return "niet (meer) gevonden" if st is None else _bezwaar(st)


def wisbare_interne_schijf(x: Schijf) -> bool:
    """Mag de interne schijf onder dit stuk helemaal gewist worden? (zie wis_bezwaar)"""
    return not wis_bezwaar(x)


def wis_controle(station: str, voor: tuple) -> bool:
    """De laatste controle, vlak vóór het wissen (nadat alles is dichtgezet): is het nog precies dezelfde schijf,
    staat er niets meer open, en zegt elke regel nog steeds dat het mag? Nee: dan wordt er niets gewist."""
    nu = _station_lsblk(station)
    return nu is not None and _identiteit(nu) == voor and not _bezwaar(nu, na_dicht=True)


def los_in_gebruik(x: Schijf) -> bool:
    """Gebruikt het systeem deze stick of externe schijf zelf (BugOS draait ervan, of hij hangt ergens via
    /etc/fstab)? Dan geen 'Leegmaken'. Dezelfde blik in /proc en /sys als bij een interne schijf."""
    return bool(x.station) and os.path.basename(x.station) in stations_in_gebruik()
