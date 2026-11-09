"""BugOS Instellingen: de pagina's Meldingen, Standaardprogramma's en Printers en scannen."""

from __future__ import annotations

import bugos_config as bi
from bugos_ui import TAAL, Chip, Knop, Rij, kde_instelling, leeg_groep, sectie, start, t
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
    kde = "kcm_notifications"

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
            t("Zo ziet een melding eruit. Klik erop, of veeg hem weg.", "This is what a notification looks like.")))
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
    zoekwoorden = ("standaard programma app browser internet e-mail mail foto's muziek video pdf openen met "
                   "bestandstype default programs apps applications browser web email mail photos music video pdf "
                   "open with file type")
    kde = "kcm_componentchooser"

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
               "gestopt": ("Gestopt · staat hij aan en zit de kabel erin?", "Stopped · is it on and plugged in?")}


class PrintersPagina(Blad):
    sleutel, icoon = "printers", "printer"
    titel_nl, titel_en = "Printers en scannen", "Printers and scanning"
    uitleg_nl = "Je printers, wat er nog geprint moet worden, en scannen."
    uitleg_en = "Your printers, what still has to be printed, and scanning."
    zoekwoorden = ("printer printen afdrukken scanner scannen wachtrij testpagina inkt papier printers printing "
                   "print scanner scanning scan queue test page ink paper")
    kde = "kcm_printer_manager"

    def bouw(self) -> None:
        kop = QHBoxLayout()
        kop.addWidget(sectie(t("Printers", "Printers")), 1)
        nieuw = Knop(t("Printer toevoegen", "Add a printer"), "stil", "lijn:map-plus")
        nieuw.clicked.connect(lambda _c=False: kde_instelling("kcm_printer_manager"))
        kop.addWidget(nieuw)
        self.lay.addLayout(kop)
        self.lijst = self.kaart()
        self.wacht_kaart = self.kaart(t("Wachtrij", "Queue"))
        self.leeg_knop = Knop(t("Wachtrij leegmaken", "Clear the queue"), "gewoon", "lijn:kruis")
        self.leeg_knop.clicked.connect(lambda _c=False: op_achtergrond(self, bi.wachtrij_leegmaken, lambda ok: (
            self.ververs(), None if ok else self.melding.toon(t("Leegmaken lukte niet.", "Clearing did not work."),
                                                              "fout"))))
        self.wacht_rij = Rij("document", "…", "", self.leeg_knop)
        self.wacht_kaart.voeg(self.wacht_rij)
        g = self.kaart(t("Scannen", "Scanning"))
        self.scan_rij = Rij("foto", t("Iets scannen", "Scan something"), "", klikbaar=True)
        self.scan_rij.geklikt.connect(self.scan)
        g.voeg(self.scan_rij)
        self.scanprogramma: str | None = None

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.printers(), bi.wachtrij(), bi.scanprogramma()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        printers, wacht, scan = uitkomst
        leeg_groep(self.lijst)
        for p in printers:
            rechts = QWidget()
            rl = QHBoxLayout(rechts)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)
            if p.standaard:
                rl.addWidget(Chip(t("Standaard", "Default"), "goed"))
            rl.addWidget(meer_knop(lambda x=p: self.menu(x)))
            self.lijst.voeg(Rij("printer", p.omschrijving, t(*STAAT_TEKST[p.staat]), rechts))
        if not printers:
            self.lijst.voeg(Rij("printer", t("Nog geen printer", "No printer yet"),
                                t("Zet de printer aan en kies 'Printer toevoegen'. De meeste worden vanzelf gevonden.",
                                  "Turn on the printer and choose 'Add a printer'. Most are found by themselves.")))
        self.wacht_rij.titel.setText(t("Niets staat te wachten", "Nothing is waiting") if not wacht else
                                     t("1 document staat te wachten", "1 document is waiting") if wacht == 1 else
                                     t(f"{wacht} documenten staan te wachten", f"{wacht} documents are waiting"))
        self.leeg_knop.setVisible(bool(wacht))
        self.scanprogramma = scan
        self.scan_rij.zet_uitleg(t("Opent het scanprogramma", "Opens the scanning program") if scan else
                                 t("Geen scanprogramma gevonden. Zoek 'Skanpage' in de BugOS Winkel.",
                                   "No scanning program found. Search 'Skanpage' in the BugOS Store."))

    def menu(self, p: bi.Printer) -> list:
        items = []
        if not p.standaard:
            items.append(("vink", t("Als standaard gebruiken", "Use as default"),
                          lambda: op_achtergrond(self, lambda: bi.zet_standaard_printer(p.naam),
                                                 lambda _u: self.ververs())))
        items.append(("document", t("Testpagina printen", "Print a test page"), lambda: op_achtergrond(
            self, lambda: bi.testpagina(p.naam), lambda ok: self.melding.toon(
                t("De testpagina is onderweg.", "The test page is on its way.") if ok else
                t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout"))))
        items.append(("code", t("Instellingen van deze printer (voor gevorderden)", "Printer settings (advanced)"),
                      lambda: kde_instelling("kcm_printer_manager")))
        return items

    def scan(self) -> None:
        if self.scanprogramma and not bi.VOORBEELD:
            if self.scanprogramma.startswith("flatpak:"):
                start("flatpak", "run", self.scanprogramma.split(":", 1)[1])
            else:
                start(self.scanprogramma)
        elif not self.scanprogramma:
            start("bugos-store")
