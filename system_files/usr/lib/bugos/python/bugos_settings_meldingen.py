"""BugOS Instellingen: de pagina's Meldingen, Standaardprogramma's en Printers en scannen."""

from __future__ import annotations

from pathlib import Path

import bugos_config as bi
from bugos_ui import (TAAL, Banner, Chip, Groep, Knop, Rij, label, leeg_groep, px, schermmaat, sectie, sectie_met_knop,
                      start, t, vraag_ja, vraag_tekst)
from bugos_settings_onderdelen import Blad, KiesDialoog, Keuzes, meer_knop, menu_bij, op_achtergrond, schuifje
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QFrame, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget


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
        # Per app aan of uit (zoals Windows op dezelfde pagina); alleen apps die al eens een melding gaven.
        self.apps_kop = sectie(t("Meldingen van apps", "Notifications from apps"))
        self.lay.addWidget(self.apps_kop)
        self.apps_uitleg = label(t("Zet een app uit als je zijn berichtjes niet meer wilt zien.",
                                   "Turn an app off if you no longer want to see its messages."), "klein")
        self.lay.addWidget(self.apps_uitleg)
        self.apps = self.kaart()
        self.app_schuifjes: dict[str, object] = {}
        for w in (self.apps_kop, self.apps_uitleg, self.apps):
            w.hide()

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.niet_storen(), bi.stil_bij_games(), bi.meldingsgeluid(),
                                      bi.app_meldingen(TAAL)), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        for schuif, aan in zip((self.storen, self.games, self.geluidje), uitkomst[:3]):
            schuif.zet_stil(bool(aan))
        apps = uitkomst[3] or []
        leeg_groep(self.apps)
        self.app_schuifjes = {}
        for app, naam, aan in apps:
            s = schuifje(aan, lambda nu, a=app: self.zet_app(a, nu))
            rij = Rij("bel", naam, self.app_uitleg(aan), s)
            s.toggled.connect(lambda nu, r=rij: r.zet_uitleg(self.app_uitleg(nu)))
            self.apps.voeg(rij)
            self.app_schuifjes[app] = s
        for w in (self.apps_kop, self.apps_uitleg, self.apps):
            w.setVisible(bool(apps))

    @staticmethod
    def app_uitleg(aan: bool) -> str:
        return "" if aan else t("Uit · je vindt ze nog wel in de lijst", "Off · you still find them in the list")

    def zet_app(self, app: str, aan: bool) -> None:
        op_achtergrond(self, lambda: bi.zet_app_meldingen(app, aan), lambda _u: None)

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
        self.ander = Knop(t("Een ander soort bestand...", "Another kind of file..."), "stil", "lijn:map")
        self.ander.clicked.connect(lambda _c=False: self.kies_bestand())
        self.lay.addWidget(self.ander, 0, Qt.AlignmentFlag.AlignLeft)

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

    # ----------------------------------------------------- een ander soort bestand ---
    def kies_bestand(self) -> None:
        """Kies een bestand van die soort; BugOS zegt wat het is en laat je het programma kiezen (geen KDE)."""
        pad, _filter = QFileDialog.getOpenFileName(self, t("Kies een bestand van die soort", "Choose a file of that kind"),
                                                   str(Path.home()))
        if pad:
            op_achtergrond(self, lambda: bi.bestandssoort(pad), lambda mime: self.kies_soort(mime or ""))

    def kies_soort(self, mime: str) -> None:
        if not mime or mime == "application/octet-stream":
            self.melding.toon(t("BugOS weet niet wat voor bestand dit is.", "BugOS does not know what kind of file this is."))
            return
        if not bi.mag_soort_zetten(mime):
            self.melding.toon(t("Dit soort bestand regelt BugOS zelf.", "BugOS takes care of this kind of file itself."))
            return
        op_achtergrond(self, lambda: (bi.soort_naam(mime, TAAL), bi.apps_voor_soort(mime, TAAL),
                                      bi.standaard_voor_soort(mime)),
                       lambda uitkomst: self.kies_programma(mime, *(uitkomst or (mime, [], ""))))

    def kies_programma(self, mime: str, naam: str, apps: list, huidig: str) -> None:
        items = list(apps) + [("__alle__", t("Een ander programma...", "Another program..."))]
        d = KiesDialoog(self, t("Waarmee open je {naam}?", "What opens {naam}?").format(naam=naam), items,
                        huidig if any(a == huidig for a, _n in apps) else None)
        if d.exec() != QDialog.DialogCode.Accepted or not d.gekozen:
            return
        app = d.gekozen
        if app == "__alle__":
            alle = bi.alle_apps(TAAL)
            d = KiesDialoog(self, t("Waarmee open je {naam}?", "What opens {naam}?").format(naam=naam), alle,
                            huidig, t("Zoek een programma", "Search for a program"))
            if d.exec() != QDialog.DialogCode.Accepted or not d.gekozen:
                return
            app, apps = d.gekozen, alle
        app_tekst = dict(apps).get(app, app)
        op_achtergrond(self, lambda: bi.zet_standaard_voor_soort(mime, app), lambda ok: self.melding.toon(
            t("{naam} opent voortaan met {app}.", "{naam} now opens with {app}.").format(naam=naam, app=app_tekst)
            if ok else t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout"))


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


def dialoog_opzet(d: QDialog, titel_tekst: str, breed: int = 560) -> QVBoxLayout:
    """Zoals KiesDialoog en de vragen: een kop, ruime marges. Nooit breder dan het scherm (150 % op 1280x800)."""
    d.setWindowTitle(titel_tekst)
    d.setMinimumWidth(schermmaat((px(breed), 0))[0][0])
    lay = QVBoxLayout(d)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(12)
    return lay


class PrinterInstellingen(QDialog):
    """Papier, één of twee kanten, kleur of zwart-wit, en (voor een beheerder) de naam. uitkomst na afloop:
    'ok' (bewaard), 'verwijder' (de knop Printer verwijderen), een foutsoort, of '' (Annuleren)."""

    def __init__(self, ouder: QWidget, p: bi.Printer, beheerder: bool):
        super().__init__(ouder)
        self.p, self.beheerder = p, beheerder
        self.uitkomst = ""
        self.laden, self.bezig = True, False   # bezig: aan het bewaren
        self.opties: bi.Opties | None = None
        self.gekozen: dict[str, str | None] = {}
        lay = dialoog_opzet(self, t("Printerinstellingen", "Printer settings"))
        lay.addWidget(label(p.omschrijving, "kop2"))
        # De uitleg en de melding staan op dezelfde plek: nooit allebei, dan blijft het venster laag (review R4).
        self.uitleg = label(t("Deze keuzes gelden elke keer dat iemand op deze computer print. In het printvenster kun je "
                              "ze per keer nog veranderen.",
                              "These choices are used every time anyone on this computer prints. You can still change "
                              "them in the print window.") if beheerder else
                            t("Deze keuzes gelden alleen voor jou, in de meeste programma's. In het printvenster kun je "
                              "ze per keer nog veranderen.",
                              "These choices are only for you, in most programs. You can still change them in the "
                              "print window."), "klein")
        lay.addWidget(self.uitleg)
        self.banner = Banner("", "bezig")
        lay.addWidget(self.banner)
        self.groep = Groep()
        self.papier_knop = Knop("…", "gewoon", "lijn:onder")
        self.papier_knop.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # het pijltje rechts, zoals een keuzelijst
        self.papier_knop.clicked.connect(self.kies_papier)
        self.papier_rij = Rij("document", t("Papierformaat", "Paper size"), "", self.papier_knop)
        self.zijden = Keuzes([("een", t("Eén kant", "One side")), ("twee", t("Beide kanten", "Both sides"))])
        self.zijden.gekozen.connect(lambda w: self.gekozen.__setitem__("zijden", w))
        self.zijden_rij = Rij("kopieer", t("Printen op", "Print on"), "", self.zijden)
        self.kleur = Keuzes([("kleur", t("Kleur", "Colour")), ("zw", t("Zwart-wit", "Black and white"))])
        self.kleur.gekozen.connect(lambda w: self.gekozen.__setitem__("kleur", w))
        self.kleur_rij = Rij("palet", t("Kleuren", "Colours"), "", self.kleur)
        for r in (self.papier_rij, self.zijden_rij, self.kleur_rij):
            r.hide()
            self.groep.voeg(r)
        self.naam_veld: QLineEdit | None = None
        if beheerder:
            self.naam_veld = QLineEdit(p.omschrijving)
            self.naam_veld.setMaxLength(127)
            self.naam_veld.setMinimumWidth(220)
            self.naam_veld.setAccessibleName(t("Naam", "Name"))
            self.naam_veld.textChanged.connect(lambda _x: self.knoppen_bijwerken())
            self.groep.voeg(Rij("potlood", t("Naam", "Name"), "", self.naam_veld))
        lay.addWidget(self.groep)
        knoppen = QHBoxLayout()
        knoppen.setSpacing(8)
        self.weg: Knop | None = None
        if beheerder:
            self.weg = Knop(t("Printer verwijderen", "Remove printer"), "stil", "lijn:prullenbak")
            self.weg.setAutoDefault(False)
            self.weg.clicked.connect(lambda _c=False: self.klaar("verwijder"))
            knoppen.addWidget(self.weg)
        knoppen.addStretch(1)
        self.annuleer = Knop(t("Annuleren", "Cancel"), "stil")
        self.annuleer.clicked.connect(self.reject)
        self.bewaar = Knop(t("Bewaren", "Save"), "hoofd")
        self.bewaar.setDefault(True)
        self.bewaar.clicked.connect(self.bewaren)
        knoppen.addWidget(self.annuleer)
        knoppen.addWidget(self.bewaar)
        lay.addLayout(knoppen)
        self.toon_banner(t("Instellingen ophalen...", "Getting the settings..."), "bezig")
        self.knoppen_bijwerken()
        op_achtergrond(self, lambda: bi.printer_opties(p.naam), self.toon)

    def toon_banner(self, tekst: str, soort: str = "info") -> None:
        self.banner.zet(tekst, soort)
        self.uitleg.setVisible(not tekst)

    def knoppen_bijwerken(self) -> None:
        rustig = not self.laden and not self.bezig
        self.bewaar.setEnabled(rustig and (self.opties is not None or self.naam_veld is not None)
                               and (self.naam_veld is None or bool(self.naam_veld.text().strip())))
        if self.weg is not None:
            self.weg.setEnabled(rustig)
        self.annuleer.setEnabled(not self.bezig)
        self.groep.setEnabled(rustig)

    def toon(self, opties) -> None:
        self.laden = False
        self.opties = opties
        if opties is None:
            self.toon_banner(t("BugOS kan de instellingen van deze printer niet lezen. Kies ze dan in het printvenster "
                               "van je programma.", "BugOS cannot read this printer's settings. Choose them in your "
                               "program's print window instead."), "let_op")
        else:
            self.toon_banner("")
            self.gekozen = {"papier": opties.papier, "zijden": opties.zijden, "kleur": opties.kleur}
            if opties.papieren:
                self.papier_knop.setText(dict(opties.papieren).get(opties.papier or "", opties.papier or "…"))
                self.papier_rij.show()
            if opties.zijden:
                self.zijden.zet(opties.zijden)
                self.zijden_rij.show()
            if opties.kleur:
                self.kleur.zet(opties.kleur)
                self.kleur_rij.show()
        self.knoppen_bijwerken()
        (self.bewaar if self.bewaar.isEnabled() else self.annuleer).setFocus()   # geen rode rand om 'A4' bij het openen
        self.adjustSize()

    def kies_papier(self) -> None:
        if self.opties is None:
            return
        menu_bij(self.papier_knop, [("vink" if k == self.gekozen.get("papier") else "document", tekst,
                                     (lambda k=k, tekst=tekst: (self.gekozen.__setitem__("papier", k),
                                                                self.papier_knop.setText(tekst))))
                                    for k, tekst in self.opties.papieren])

    def wijzigingen(self) -> dict[str, str]:
        """Alleen wat je veranderd hebt (zo blijft een keuze die BugOS niet kent, zoals DuplexTumble, staan)."""
        o, g, uit = self.opties, self.gekozen, {}
        if o is None:
            return uit
        if o.papier is not None and g.get("papier") and g["papier"] != o.papier:
            uit["PageSize"] = g["papier"]
        if o.zijden and g.get("zijden") in o.zijden_waarde and g["zijden"] != o.zijden:
            uit["Duplex"] = o.zijden_waarde[g["zijden"]]
        if o.kleur and g.get("kleur") in o.kleur_waarde and g["kleur"] != o.kleur:
            uit["ColorModel"] = o.kleur_waarde[g["kleur"]]
        return uit

    def bewaren(self) -> None:
        if self.bezig or self.laden:
            return
        naam = self.naam_veld.text().strip() if self.naam_veld is not None else ""
        beschrijving = naam if naam and naam != self.p.omschrijving else None
        wijzigingen = self.wijzigingen()
        self.bezig = True
        self.knoppen_bijwerken()
        self.toon_banner(t("Bewaren...", "Saving..."), "bezig")

        def af(soort) -> None:
            self.bezig = False
            soort = soort or "anders"
            if soort in ("ok", "bestaat_niet"):
                self.klaar(soort)
                return
            self.toon_banner(fout_tekst(soort), "info" if soort == "geweigerd" else "fout")
            self.knoppen_bijwerken()
        op_achtergrond(self, lambda: bi.zet_printer_opties(self.p.naam, wijzigingen, beschrijving), af)

    def klaar(self, uitkomst: str) -> None:
        self.uitkomst = uitkomst
        self.bezig = False
        super().accept()

    def reject(self) -> None:  # noqa: D102
        if self.bezig:   # tijdens het bewaren niet weg (het gebeurt toch)
            return
        super().reject()


GEEN_SOFTWARE = ("BugOS heeft geen software voor deze printer. Printers van na ongeveer 2015 werken meestal zonder; "
                 "deze heeft software van de maker nodig, en die kan BugOS nog niet installeren. Kijk op de website "
                 "van de maker of de printer met Linux werkt, of vraag hulp op het BugOS-forum.",
                 "BugOS has no software for this printer. Printers made after about 2015 usually work without it; this "
                 "one needs software from its maker, and BugOS cannot install that yet. Look on the maker's website "
                 "whether the printer works with Linux, or ask for help on the BugOS forum.")


def plek_tekst(g: bi.Gevonden) -> str:
    """De regel onder een gevonden printer: waar hij is, of hij software nodig heeft, en of hij er al is."""
    if g.soort == "netwerk":
        tekst = t("Op je netwerk", "On your network")
    else:
        tekst = t("Met een kabel aangesloten", "Plugged in with a cable")
    if not g.driverless:
        tekst += t(" · heeft software van de maker nodig", " · needs software from its maker")
    if g.locatie:
        tekst += " · " + g.locatie
    if g.al_toegevoegd:
        tekst += t(" · al toegevoegd", " · already added")
    return tekst


class PrinterToevoegen(QDialog):
    """Printer toevoegen: BugOS zoekt printers op je wifi en met een kabel; 'Toevoegen' en hij is er. Kan hij niet
    zonder software van de maker, dan kies je merk en model. Staat hij er niet bij: het adres typen.
    Na afloop: self.toegevoegd = (wachtrij, naam) of None."""

    RIJ = 62

    def __init__(self, ouder: QWidget, beheerder: bool):
        super().__init__(ouder)
        self.beheerder = beheerder
        self.bezig = False
        self.toegevoegd: tuple[str, str] | None = None
        self.adres = ""
        lay = dialoog_opzet(self, t("Printer toevoegen", "Add a printer"))
        lay.addWidget(label(t("Printer toevoegen", "Add a printer"), "kop2"))
        uitleg = t("Zet de printer aan. Printers op je wifi, of met een kabel aan deze computer, verschijnen hier.",
                   "Turn the printer on. Printers on your Wi-Fi, or plugged into this computer with a cable, show up here.")
        if not beheerder:
            uitleg += " " + t("Om een printer toe te voegen vraagt BugOS het wachtwoord van een beheerder.",
                              "To add a printer, BugOS asks for an administrator's password.")
        # De uitleg en een melding staan op dezelfde plek, nooit allebei: zo past het venster op 1280x800 bij 150 % (R4).
        self.uitleg = label(uitleg, "klein")
        lay.addWidget(self.uitleg)
        self.status = Banner("", "bezig")
        lay.addWidget(self.status)
        self.lijst = Groep()
        self.lijst.lay.setContentsMargins(4, 4, 4, 4)
        self.vlak = QScrollArea()
        self.vlak.setFrameShape(QFrame.Shape.NoFrame)
        self.vlak.setWidgetResizable(True)
        self.vlak.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vlak.setWidget(self.lijst)
        lay.addWidget(self.vlak)
        anders = QHBoxLayout()
        anders.setSpacing(8)
        self.ander = Knop(t("Mijn printer staat er niet bij", "My printer is not in the list"), "stil", "lijn:zoek")
        self.ander.setAutoDefault(False)
        self.ander.clicked.connect(self.vraag_adres)
        anders.addWidget(self.ander)
        self.kabel: Knop | None = None
        if not beheerder:   # oude printers met een kabel ziet alleen een beheerder (lpinfo, review R7)
            self.kabel = Knop(t("Printer met een kabel?", "Printer with a cable?"), "stil", "lijn:printer")
            self.kabel.setToolTip(t("Zoek met het wachtwoord van een beheerder", "Look with an administrator's password"))
            self.kabel.setAutoDefault(False)
            self.kabel.clicked.connect(lambda _c=False: self.zoek(met_kabel=True))
            anders.addWidget(self.kabel)
        anders.addStretch(1)
        lay.addLayout(anders)
        knoppen = QHBoxLayout()
        knoppen.setSpacing(8)
        self.opnieuw = Knop(t("Opnieuw zoeken", "Search again"), "stil", "lijn:verversen")
        self.opnieuw.setAutoDefault(False)
        self.opnieuw.clicked.connect(lambda _c=False: self.zoek())
        knoppen.addWidget(self.opnieuw)
        knoppen.addStretch(1)
        self.sluit = Knop(t("Sluiten", "Close"), "gewoon")
        self.sluit.clicked.connect(self.reject)
        knoppen.addWidget(self.sluit)
        lay.addLayout(knoppen)
        self.zoek()

    # ---------------------------------------------------------------- staat ---
    def toon_status(self, tekst: str, soort: str = "bezig") -> None:
        self.status.zet(tekst, soort)
        self.uitleg.setVisible(not tekst)
        self.pas_hoogte()
        # Nieuwe regels in een zichtbaar venster laat Qt pas in de volgende ronde zien (en meet ze dan pas mee).
        QTimer.singleShot(0, self.pas_hoogte)

    def pas_hoogte(self) -> None:
        """Hooguit drie printers in beeld (de rest schuift), en nooit hoger dan het scherm (review R4)."""
        lay = self.layout()
        m = lay.contentsMargins()
        breed = max(self.width(), self.minimumWidth()) - m.left() - m.right()
        rest, n = m.top() + m.bottom(), 0
        for i in range(lay.count()):
            it = lay.itemAt(i)
            w = it.widget()
            if w is self.vlak:
                n += 1
                continue
            if w is not None and w.isHidden():
                continue
            n += 1
            rest += it.heightForWidth(breed) if it.hasHeightForWidth() else it.sizeHint().height()
        rest += lay.spacing() * max(0, n - 1)
        vrij = schermmaat((0, 9999))[0][1]
        inhoud = self.lijst.sizeHint().height()
        # Uit de layout, niet findChildren: oude regels (leeg_groep) bestaan nog tot de volgende ronde van Qt.
        rijen = [w for w in (self.lijst.lay.itemAt(i).widget() for i in range(self.lijst.lay.count()))
                 if isinstance(w, Rij)]
        lm = self.lijst.lay.contentsMargins()
        per = (inhoud - lm.top() - lm.bottom()) / max(1, len(rijen))
        drie = inhoud if len(rijen) <= 3 else int(lm.top() + 3.5 * per)   # de 4e half: dan zie je dat er meer is
        self.vlak.setFixedHeight(max(px(self.RIJ), min(inhoud, drie, vrij - rest)))
        self.adjustSize()

    def zet_bezig(self, bezig: bool) -> None:
        self.bezig = bezig
        for k in (self.ander, self.kabel, self.opnieuw, self.sluit, *self.lijst.findChildren(Knop)):
            if k is not None:
                k.setEnabled(not bezig)

    def reject(self) -> None:  # noqa: D102
        if self.bezig:   # tijdens het toevoegen niet weg: het gebeurt toch
            return
        super().reject()

    # ---------------------------------------------------------------- zoeken ---
    def zoek(self, met_kabel: bool | None = None) -> None:
        self.toon_status(t("Printers zoeken... dit duurt een paar tellen.", "Looking for printers... this takes a few seconds."))
        self.vlak.hide()
        self.opnieuw.setEnabled(False)
        if self.kabel is not None:
            self.kabel.setEnabled(False)
        op_achtergrond(self, lambda: bi.gevonden_printers(met_kabel), self.toon_gevonden)

    def toon_gevonden(self, gevonden) -> None:
        leeg_groep(self.lijst)
        for g in gevonden or []:
            if g.al_toegevoegd:
                rechts = Chip(t("Toegevoegd", "Added"), "goed")
            else:
                rechts = Knop(t("Toevoegen", "Add"), "gewoon")
                rechts.clicked.connect(lambda _c=False, x=g: self.voeg_toe(x))
            self.lijst.voeg(Rij("printer", g.naam, plek_tekst(g), rechts))
        if not gevonden:
            self.lijst.voeg(Rij("printer", t("Geen printer gevonden", "No printer found"),
                                t("Staat de printer aan en zit hij op dezelfde wifi? Of zit de kabel erin? Zoek dan "
                                  "opnieuw, of kies 'Mijn printer staat er niet bij'.",
                                  "Is the printer on and on the same Wi-Fi? Or is the cable plugged in? Then search "
                                  "again, or choose 'My printer is not in the list'.")))
        self.opnieuw.setEnabled(True)
        if self.kabel is not None:
            self.kabel.setEnabled(True)
        self.vlak.show()
        self.toon_status("")

    # ------------------------------------------------------------- toevoegen ---
    def voeg_toe(self, g: bi.Gevonden) -> None:
        if not g.driverless:   # een oude printer met een kabel, of een die geen IPP Everywhere kan
            self.kies_model(g.uri, g.dienst or g.naam, g.naam, g.model_hint)
            return
        # Geen IPP Everywhere (Unable to create PPD): dezelfde ipp://-link werkt met software van de maker.
        self.doe(lambda: bi.printer_toevoegen(g), g.naam,
                 t("{naam} toevoegen... dit kan een halve minuut duren.",
                   "Adding {naam}... this can take half a minute.").format(naam=g.naam),
                 lambda _soort: self.kies_model(g.reserve_uri or g.uri, g.dienst or g.naam, g.naam, g.model_hint))

    def doe(self, werk, naam: str, bezig_tekst: str, zonder=None) -> None:
        """Toevoegen op de achtergrond. zonder(soort): wat er gebeurt als de printer software van de maker nodig heeft."""
        self.zet_bezig(True)
        self.toon_status(bezig_tekst)

        def af(uitkomst) -> None:
            self.zet_bezig(False)
            soort, wachtrij = uitkomst if uitkomst else ("anders", "")
            if soort == "ok":
                self.toegevoegd = (wachtrij, naam)
                self.accept()
            elif soort in ("geen_driverless", "geen_antwoord") and zonder is not None:
                zonder(soort)
            else:
                self.toon_status(fout_tekst(soort), "info" if soort == "geweigerd" else "fout")
        op_achtergrond(self, werk, af)

    def vraag_adres(self) -> None:
        uitleg = t("Het adres staat op het schermpje van de printer, of op een pagina met zijn instellingen die hij kan "
                   "printen (bijvoorbeeld 192.168.1.20).", "You find the address on the printer's screen, or on a page "
                   "with its settings that it can print (for example 192.168.1.20).")
        vraag = uitleg
        while True:
            tekst = vraag_tekst(self, t("Adres van de printer", "Printer address"), vraag, self.adres,
                                t("Printer toevoegen", "Add printer"))
            if tekst is None:
                return
            self.adres = tekst.strip()
            if bi.adres_kandidaten(self.adres):
                break
            vraag = t("Dat lijkt geen printeradres. Het ziet eruit als 192.168.1.20 of printer.local.",
                      "That does not look like a printer address. It looks like 192.168.1.20 or printer.local.")
        adres = self.adres
        basis, ipp_uri, socket_uri = bi.adres_vervolg(adres)

        def zonder(soort: str) -> None:
            if soort == "geen_antwoord":   # geen IPP: klassieke netwerkprinters luisteren op poort 9100
                self.kies_model(socket_uri, basis, adres, "",
                                t("De printer antwoordt niet op de gewone manier. Kies het merk en model.",
                                  "The printer does not answer in the usual way. Choose its brand and model."))
            else:
                self.kies_model(ipp_uri, basis, adres, "")
        self.doe(lambda: bi.printer_toevoegen_adres(adres), adres,
                 t("Contact zoeken met de printer... dit kan een halve minuut duren.",
                   "Contacting the printer... this can take half a minute."), zonder)

    # ------------------------------------------------- software van de maker ---
    def kies_model(self, uri: str, basis: str, naam: str, hint: str, eerst: str = "", alles: bool = False) -> None:
        """Merk en model kiezen (hplip, gutenprint, brlaser ...). Eerst wat bij de printer past (een paar tellen), en
        pas als je dat vraagt, of als niets past, de hele lijst (soms een minuut, review R2)."""
        woorden = [] if alles else bi.model_woorden(hint)
        alles = alles or not woorden
        self.toon_status(eerst or (t("Alle printers opzoeken... dat duurt soms een minuut.",
                                     "Looking up all printers... this sometimes takes a minute.") if alles else
                                   t("Software voor deze printer opzoeken... dat duurt een paar tellen.",
                                     "Looking up software for this printer... this takes a few seconds.")))
        self.zet_bezig(True)

        def gevonden(lijst) -> None:
            self.zet_bezig(False)
            if lijst is None:
                self.toon_status(t("De lijst met printers kon niet geladen worden. Probeer het nog eens.",
                                   "The list of printers could not be loaded. Try again."), "fout")
                return
            if not lijst and not alles:   # niets past bij merk en model: dan de hele lijst, al gefilterd
                self.kies_model(uri, basis, naam, hint, alles=True)
                return
            if not lijst:
                self.toon_status(t(*GEEN_SOFTWARE), "info")
                return
            items = list(lijst) if alles else \
                list(lijst) + [("__alle__", t("Een ander merk of model...", "Another brand or model..."))]
            d = KiesDialoog(self, t("Welk merk en model?", "Which brand and model?"), items, lijst[0][0],
                            t("Typ merk en model, bijvoorbeeld LaserJet 1020", "Type brand and model, for example LaserJet 1020"))
            if alles and hint and d.zoekveld is not None:
                d.zoekveld.setText(" ".join(bi.model_woorden(hint)[:2]))
            if d.exec() != QDialog.DialogCode.Accepted or not d.gekozen:
                self.toon_status(t(*GEEN_SOFTWARE), "info")
                return
            if d.gekozen == "__alle__":
                self.kies_model(uri, basis, naam, hint, alles=True)
                return
            model = d.gekozen
            self.doe(lambda: bi.printer_toevoegen_model(uri, basis, naam, model), naam,
                     t("{naam} toevoegen... dit kan een halve minuut duren.",
                       "Adding {naam}... this can take half a minute.").format(naam=naam))
        op_achtergrond(self, lambda: bi.modellen(" ".join(woorden)), gevonden)

    def accept(self) -> None:  # noqa: D102
        self.bezig = False
        super().accept()


class PrintersPagina(Blad):
    sleutel, icoon = "printers", "printer"
    titel_nl, titel_en = "Printers en scannen", "Printers and scanning"
    uitleg_nl = "Je printers, wat er nog geprint moet worden, en scannen."
    uitleg_en = "Your printers, what still has to be printed, and scanning."
    zoekwoorden = ("printer printen afdrukken scanner scannen wachtrij testpagina inkt papier printers printing "
                   "print scanner scanning scan queue test page ink paper")
    MAX_TAKEN = 5

    def bouw(self) -> None:
        self.nieuw = Knop(t("Printer toevoegen", "Add a printer"), "stil", "lijn:printer")
        self.nieuw.clicked.connect(lambda _c=False: self.toevoegen())
        self.lay.addWidget(sectie_met_knop(t("Printers", "Printers"), self.nieuw))
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
                                 t("Geen scanprogramma gevonden. Klik om Skanpage in de BugOS Winkel te zoeken.",
                                   "No scanning program found. Click to find Skanpage in the BugOS Store."))

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
            # De knop heet zoals zijn tekst (U039); welk document het is, hoort de schermlezer als beschrijving.
            weg.setAccessibleDescription(rij.titel.text())
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
        items.append(("palet", t("Instellingen van deze printer", "Printer settings"), lambda: self.instellingen(p)))
        if p.staat == "gestopt":
            items.append(("aan", t("Verder printen", "Resume printing"), lambda: self.doe(
                lambda: bi.hervat_printer(p.naam), t("Even geduld...", "One moment..."),
                t("De printer print weer.", "The printer is printing again."))))
        elif self.beheerder:
            items.append(("maan", t("Printen pauzeren", "Pause printing"), lambda: self.doe(
                lambda: bi.pauzeer_printer(p.naam), t("Even geduld...", "One moment..."), t("Gepauzeerd.", "Paused."))))
        items.append(("prullenbak", t("Printer verwijderen", "Remove printer"), lambda: self.verwijder(p)))
        return items

    def toevoegen(self) -> None:
        d = PrinterToevoegen(self, self.beheerder)
        d.exec()
        if d.toegevoegd:
            wachtrij, naam = d.toegevoegd
            self.melding.toon(t("{naam} is toegevoegd.", "{naam} has been added.").format(naam=naam), "goed",
                              knop=t("Testpagina printen", "Print a test page"),
                              actie=lambda: self.testpagina(wachtrij), seconden=12)
        self.ververs()

    def instellingen(self, p: bi.Printer) -> None:
        d = PrinterInstellingen(self, p, self.beheerder)
        d.exec()
        if d.uitkomst == "verwijder":
            self.verwijder(p)
        elif d.uitkomst == "ok":
            self.melding.toon(t("Bewaard.", "Saved."), "goed")
            self.ververs()
        elif d.uitkomst:
            self.melding.toon(fout_tekst(d.uitkomst), "fout")
            self.ververs()

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
            start("bugos-store", "--zoek", "Skanpage")   # de Winkel zoekt meteen (niet de voorpagina)
