"""BugOS Instellingen: de pagina's Meldingen, Standaardprogramma's en Printers en scannen."""

from __future__ import annotations

import bugos_config as bi
from bugos_ui import TAAL, Chip, Knop, Rij, kde_instelling, leeg_groep, sectie, start, t, vraag_ja
from bugos_settings_onderdelen import Blad, meer_knop, op_achtergrond, schuifje
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget


# =============================================================== meldingen ===

class MeldingenPagina(Blad):
    sleutel, icoon = "meldingen", "bel"
    titel_nl, titel_en = "Meldingen", "Notifications"
    uitleg_nl = "De berichtjes rechtsonder in beeld, en wanneer ze stil moeten zijn."
    uitleg_en = "The little messages in the corner, and when they should keep quiet."
    zoekwoorden = ("meldingen notificaties berichtjes pop-up popup niet storen stil geluid games films "
                   "notifications notification popups do not disturb dnd quiet silent sounds games movies")

    def bouw(self) -> None:
        g = self.kaart()
        self.storen = schuifje(False, lambda aan: self.zet(bi.zet_niet_storen, aan))
        g.voeg(Rij("maan", t("Niet storen", "Do not disturb"),
                   t("Geen berichtjes in beeld tot je dit weer uitzet. Je vindt ze later terug in de lijst.",
                     "No messages on screen until you turn this off again. You find them in the list later."),
                   self.storen))
        self.games = schuifje(True, lambda aan: self.zet(bi.zet_stil_bij_games, aan))
        g.voeg(Rij("spel", t("Stil tijdens games en films", "Quiet during games and movies"),
                   t("Als iets het hele scherm vult", "When something fills the whole screen"), self.games))
        self.geluidje = schuifje(True, lambda aan: self.zet(bi.zet_meldingsgeluid, aan))
        g.voeg(Rij("geluid", t("Geluidje bij een melding", "Sound with a notification"), "", self.geluidje))
        g2 = self.kaart()
        proef = Knop(t("Proefmelding", "Test notification"), "gewoon", "lijn:bel")
        proef.clicked.connect(lambda _c=False: bi.proefmelding(
            t("Hallo van BugOS", "Hello from BugOS"),
            t("Zo ziet een melding eruit. Klik erop, of veeg hem weg.", "This is what a notification looks like. Click it, or swipe it away.")))
        g2.voeg(Rij("bel", t("Zo ziet een melding eruit", "See what a notification looks like"), "", proef))

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.niet_storen(), bi.stil_bij_games(), bi.meldingsgeluid()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        for schuif, aan in zip((self.storen, self.games, self.geluidje), uitkomst):
            schuif.zet_stil(bool(aan))

    def zet(self, werk, aan: bool) -> None:
        op_achtergrond(self, lambda: werk(aan), lambda _u: None)


# ===================================================== standaardprogramma's ===

class ProgrammasPagina(Blad):
    sleutel, icoon = "programmas", "apps"
    titel_nl, titel_en = "Standaardprogramma's", "Default programs"
    uitleg_nl = "Welk programma opent wat: internet, e-mail, foto's, muziek, video's en documenten."
    uitleg_en = "Which program opens what: internet, email, photos, music, videos and documents."
    zoekwoorden = ("standaardapps standaardprogramma standaard programma app browser internet e-mail mail foto's muziek video pdf openen met "
                   "bestandstype default programs apps applications browser web email mail photos music video pdf "
                   "open with file type")

    def bouw(self) -> None:
        self.lijst = self.kaart(t("Klik op … om een ander programma te kiezen", "Click … to choose another program"))
        self.rijen: dict[str, Rij] = {}
        for sleutel, ic, (nl, en), _soorten in bi.SOORTEN:
            rij = Rij(ic, t(nl, en), "…", meer_knop(lambda s=sleutel: self.keuzes(s)))
            self.lijst.voeg(rij)
            self.rijen[sleutel] = rij
        alle = Knop(t("Alle bestandstypes (voor gevorderden)", "All file types (advanced)"), "stil", "lijn:code")
        alle.clicked.connect(lambda _c=False: kde_instelling("kcm_filetypes"))
        self.lay.addWidget(alle, 0, Qt.AlignmentFlag.AlignLeft)

    def ververs(self) -> None:
        def lees() -> dict[str, str]:
            uit = {}
            for sleutel, _ic, _namen, _soorten in bi.SOORTEN:
                app = bi.standaard_app(sleutel)
                naam = next((n for i, n in bi.apps_voor(sleutel, TAAL) if i == app), None) if app else None
                uit[sleutel] = naam or (bi.app_naam(app, TAAL, ook_verborgen=True) if app and not bi.VOORBEELD else "")
            return uit
        op_achtergrond(self, lees, self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        for sleutel, naam in uitkomst.items():
            self.rijen[sleutel].zet_uitleg(naam or t("Nog niets gekozen", "Nothing chosen yet"))

    def keuzes(self, sleutel: str) -> list:
        huidig = bi.standaard_app(sleutel)
        items = [("vink" if app == huidig else "apps", naam, (lambda a=app: self.kies(sleutel, a)))
                 for app, naam in bi.apps_voor(sleutel, TAAL)]
        return items or [("kruis", t("Geen programma gevonden. Kijk in de BugOS Winkel.",
                                     "No program found. Have a look in the BugOS Store."), lambda: start("bugos-store"))]

    def kies(self, sleutel: str, app: str) -> None:
        op_achtergrond(self, lambda: bi.zet_standaard_app(sleutel, app), lambda ok: (
            self.melding.toon(t("Klaar.", "Done.") if ok else t("Dat lukte niet.", "That did not work."),
                              "goed" if ok else "fout"), self.ververs()))


# ================================================================ printers ===

STAAT_TEKST = {"klaar": ("Klaar om te printen", "Ready to print"), "bezig": ("Aan het printen", "Printing"),
               "gestopt": ("Gestopt · staat hij aan en zit de kabel erin? Kies dan Verder printen in het menu.",
                           "Stopped · is it on and plugged in? Then choose Resume printing in the menu."),
               "gepauzeerd": ("Gepauzeerd", "Paused"),
               "wacht": ("Wacht op de printer · staat hij aan en zit hij op dezelfde wifi?",
                         "Waiting for the printer · is it on and on the same Wi-Fi?")}

# Wat er misging, in gewone woorden (nooit de foutmelding van CUPS zelf).
FOUT_TEKST = {
    "geweigerd": ("Niets gedaan: er was geen toestemming.", "Nothing done: permission was not given."),
    "verboden": ("Dat mag alleen een beheerder van deze computer.", "Only an administrator of this computer can do that."),
    "onbereikbaar": ("BugOS kan de printer niet bereiken. Staat hij aan en zit hij op dezelfde wifi als deze computer?",
                     "BugOS cannot reach the printer. Is it on, and on the same Wi-Fi as this computer?"),
    "bestaat_niet": ("Die printer bestaat niet meer. De lijst wordt bijgewerkt.",
                     "That printer no longer exists. The list is updated."),
    "anders": ("Dat lukte niet. Probeer het nog eens.", "That did not work. Try again."),
}


def fout_tekst(soort: str) -> str:
    return t(*FOUT_TEKST.get(soort, FOUT_TEKST["anders"]))


def printer_staat(p: bi.Printer) -> str:
    """De regel onder een printer: klaar, aan het printen, gestopt, gepauzeerd of wacht op de printer."""
    if p.gepauzeerd:
        sleutel = "gepauzeerd"
    elif p.staat == "gestopt":
        sleutel = "gestopt"
    elif p.onbereikbaar:
        sleutel = "wacht"
    else:
        sleutel = p.staat
    tekst = t(*STAAT_TEKST.get(sleutel, STAAT_TEKST["klaar"]))
    return f"{tekst} · {p.locatie}" if p.locatie else tekst


class PrintersPagina(Blad):
    sleutel, icoon = "printers", "printer"
    titel_nl, titel_en = "Printers en scannen", "Printers and scanning"
    uitleg_nl = "Je printers, wat er nog geprint moet worden, en scannen."
    uitleg_en = "Your printers, what still has to be printed, and scanning."
    zoekwoorden = ("printer printen afdrukken scanner scannen wachtrij testpagina inkt papier printers printing "
                   "print scanner scanning scan queue test page ink paper")
    MAX_TAKEN = 5

    def bouw(self) -> None:
        kop = QHBoxLayout()
        kop.addWidget(sectie(t("Printers", "Printers")), 1)
        nieuw = Knop(t("Printer toevoegen", "Add a printer"), "stil", "lijn:map-plus")
        nieuw.clicked.connect(lambda _c=False: kde_instelling("kcm_printer_manager"))
        kop.addWidget(nieuw)
        self.lay.addLayout(kop)
        self.lijst = self.kaart()
        self.wacht_kaart = self.kaart(t("Wachtrij", "Queue"))
        self.wacht_rij: Rij | None = None
        self.leeg_knop: Knop | None = None
        self.taak_rijen: list[Rij] = []
        self.wachtrij_rijen(0, [])
        g = self.kaart(t("Scannen", "Scanning"))
        self.scan_rij = Rij("foto", t("Iets scannen", "Scan something"), "", klikbaar=True)
        self.scan_rij.geklikt.connect(self.scan)
        g.voeg(self.scan_rij)
        self.scanprogramma: str | None = None
        self.beheerder = True

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.printers(), bi.wachtrij(), bi.scanprogramma(), bi.taken(),
                                      bi.ben_beheerder()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        printers, wacht, scan, taken, self.beheerder = uitkomst
        leeg_groep(self.lijst)
        for p in printers:
            rechts = QWidget()
            rl = QHBoxLayout(rechts)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)
            if p.standaard:
                rl.addWidget(Chip(t("Standaard", "Default"), "goed"))
            rl.addWidget(meer_knop(lambda x=p: self.menu(x)))
            self.lijst.voeg(Rij("printer", p.omschrijving, printer_staat(p), rechts))
        if not printers:
            self.lijst.voeg(Rij("printer", t("Nog geen printer", "No printer yet"),
                                t("Zet de printer aan en kies 'Printer toevoegen'. De meeste worden vanzelf gevonden.",
                                  "Turn on the printer and choose 'Add a printer'. Most are found by themselves.")))
        namen = {p.naam: p.omschrijving for p in printers}
        self.wachtrij_rijen(wacht, taken, namen)
        self.scanprogramma = scan
        self.scan_rij.zet_uitleg(t("Opent het scanprogramma", "Opens the scanning program") if scan else
                                 t("Geen scanprogramma gevonden. Zoek 'Skanpage' in de BugOS Winkel.",
                                   "No scanning program found. Search 'Skanpage' in the BugOS Store."))

    def wachtrij_rijen(self, wacht: int, taken: list, namen: dict | None = None) -> None:
        """De wachtrij: hoeveel er wacht ('Alles annuleren'), en daaronder je eigen documenten, elk met 'Annuleren'."""
        leeg_groep(self.wacht_kaart)
        self.leeg_knop = Knop(t("Alles annuleren", "Cancel all"), "gewoon", "lijn:kruis")
        self.leeg_knop.clicked.connect(lambda _c=False: op_achtergrond(self, bi.wachtrij_leegmaken, lambda ok: (
            self.ververs(), None if ok else self.melding.toon(t("Annuleren lukte niet.", "Cancelling did not work."),
                                                              "fout"))))
        titel = (t("Niets staat te wachten", "Nothing is waiting") if not wacht else
                 t("1 document staat te wachten", "1 document is waiting") if wacht == 1 else
                 t("{n} documenten staan te wachten", "{n} documents are waiting").format(n=wacht))
        self.wacht_rij = Rij("document", titel, "", self.leeg_knop)
        self.leeg_knop.setVisible(bool(wacht))
        self.wacht_kaart.voeg(self.wacht_rij)
        self.taak_rijen = []
        for taak in taken[:self.MAX_TAKEN]:
            weg = Knop(t("Annuleren", "Cancel"), "gewoon")
            weg.clicked.connect(lambda _c=False, x=taak: self.annuleer(x))
            plek = (namen or {}).get(taak.printer, taak.printer.replace("_", " "))
            uitleg = f"{plek} · " + (t("wordt nu geprint", "printing now") if taak.actief else t("wacht", "waiting"))
            rij = Rij("document", taak.titel or t("Document", "Document"), uitleg, weg)
            weg.setAccessibleName(t("{titel} annuleren", "Cancel {titel}").format(titel=rij.titel.text()))
            self.wacht_kaart.voeg(rij)
            self.taak_rijen.append(rij)
        if len(taken) > self.MAX_TAKEN:
            rij = Rij("document", t("en nog {n} meer", "and {n} more").format(n=len(taken) - self.MAX_TAKEN), "")
            self.wacht_kaart.voeg(rij)
            self.taak_rijen.append(rij)

    def annuleer(self, taak) -> None:
        op_achtergrond(self, lambda: bi.annuleer_taak(taak.printer, taak.id), lambda ok: (
            self.ververs(), None if ok else self.melding.toon(fout_tekst("anders"), "fout")))

    def menu(self, p: bi.Printer) -> list:
        items = []
        if not p.standaard:
            items.append(("vink", t("Als standaard gebruiken", "Use as default"),
                          lambda: op_achtergrond(self, lambda: bi.zet_standaard_printer(p.naam),
                                                 lambda _u: self.ververs())))
        items.append(("document", t("Testpagina printen", "Print a test page"), lambda: self.testpagina(p.naam)))
        if not bi.NAAM_RE.match(p.naam):   # een naam die BugOS niet zelf maakte en niet vertrouwt: alleen de testpagina
            return items
        items.append(("code", t("Instellingen van deze printer (voor gevorderden)", "Printer settings (advanced)"),
                      lambda: kde_instelling("kcm_printer_manager")))
        if p.staat == "gestopt":
            items.append(("aan", t("Verder printen", "Resume printing"), lambda: self.doe(
                lambda: bi.hervat_printer(p.naam), t("Even geduld...", "One moment..."),
                t("De printer print weer.", "The printer is printing again."))))
        elif self.beheerder:
            items.append(("maan", t("Printen pauzeren", "Pause printing"), lambda: self.doe(
                lambda: bi.pauzeer_printer(p.naam), t("Even geduld...", "One moment..."), t("Gepauzeerd.", "Paused."))))
        items.append(("prullenbak", t("Printer verwijderen", "Remove printer"), lambda: self.verwijder(p)))
        return items

    def testpagina(self, naam: str) -> None:
        op_achtergrond(self, lambda: bi.testpagina(naam), lambda ok: self.melding.toon(
            t("De testpagina is onderweg.", "The test page is on its way.") if ok else
            t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout"))

    def verwijder(self, p: bi.Printer) -> None:
        if not vraag_ja(self, t("Printer verwijderen?", "Remove printer?"),
                        t("{naam} verwijderen? Je kunt hem later weer toevoegen.",
                          "Remove {naam}? You can add it again later.").format(naam=p.omschrijving),
                        t("Verwijderen", "Remove"), enter_is_nee=True):
            return
        self.doe(lambda: bi.verwijder_printer(p.naam), t("Printer verwijderen...", "Removing the printer..."),
                 t("Printer verwijderd.", "Printer removed."))

    def doe(self, werk, bezig: str, klaar: str) -> None:
        """Iets met een printer (verder, pauze, weg): eerst 'even geduld', dan 'gelukt' of wat er misging."""
        if not self.beheerder:
            bezig = t("{bezig} BugOS vraagt het wachtwoord van een beheerder.",
                      "{bezig} BugOS asks for an administrator's password.").format(bezig=bezig)
        self.melding.toon(bezig, "info", seconden=20)

        def af(soort) -> None:
            if soort == "ok":
                self.melding.toon(klaar, "goed")
            else:
                self.melding.toon(fout_tekst(soort or "anders"), "info" if soort == "geweigerd" else "fout")
            self.ververs()
        op_achtergrond(self, werk, af)

    def scan(self) -> None:
        if self.scanprogramma and not bi.VOORBEELD:
            if self.scanprogramma.startswith("flatpak:"):
                start("flatpak", "run", self.scanprogramma.split(":", 1)[1])
            else:
                start(self.scanprogramma)
        elif not self.scanprogramma:
            start("bugos-store")
