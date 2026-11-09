"""BugOS Instellingen: de pagina's Tijd en taal, en Inloggen en wachtwoord."""

from __future__ import annotations

import time
from datetime import datetime

import bugos_config as bi
from bugos_ui import TAAL, Knop, Rij, kde_instelling, label, t
from bugos_settings_onderdelen import (
    Blad, Keuzes, KiesDialoog, WachtwoordDialoog, dichtstbij, meer_knop, op_achtergrond, schuifje,
)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QWidget


# ============================================================ tijd en taal ===

DAGEN = (("maandag", "Monday"), ("dinsdag", "Tuesday"), ("woensdag", "Wednesday"), ("donderdag", "Thursday"),
         ("vrijdag", "Friday"), ("zaterdag", "Saturday"), ("zondag", "Sunday"))
MAANDEN = (("januari", "January"), ("februari", "February"), ("maart", "March"), ("april", "April"), ("mei", "May"),
           ("juni", "June"), ("juli", "July"), ("augustus", "August"), ("september", "September"),
           ("oktober", "October"), ("november", "November"), ("december", "December"))


def nu_tekst() -> str:
    d = datetime.now().astimezone()
    dag, maand = DAGEN[d.weekday()], MAANDEN[d.month - 1]
    return t(f"{dag[0].capitalize()} {d.day} {maand[0]} {d.year} · {d:%H:%M}",
             f"{dag[1]} {maand[1]} {d.day}, {d.year} · {d:%H:%M}")


class TijdPagina(Blad):
    sleutel, icoon = "tijd", "klok"
    titel_nl, titel_en = "Tijd en taal", "Time and language"
    uitleg_nl = "De klok, je tijdzone en de taal van BugOS."
    uitleg_en = "The clock, your time zone and the language of BugOS."
    zoekwoorden = "tijd klok datum tijdzone zomertijd wintertijd taal nederlands engels language land"
    kde = "kcm_regionandlang"

    def bouw(self) -> None:
        g = self.kaart()
        self.auto = schuifje(True, self.zet_auto)
        # De regel toont de klok; het schuifje zelf zet de tijd vanzelf goed (anders noemt een schermlezer de tijd).
        self.auto.setAccessibleName(t("Tijd vanzelf instellen", "Set the time automatically"))
        self.klok_rij = Rij("klok", nu_tekst(), "", self.auto)
        g.voeg(self.klok_rij)
        self.tik = QTimer(self)
        self.tik.setInterval(20000)
        self.tik.timeout.connect(lambda: self.klok_rij.titel.setText(nu_tekst()))
        self.tik.start()
        zone_knop = Knop(t("Andere tijdzone…", "Other time zone…"), "gewoon")
        zone_knop.clicked.connect(self.kies_zone)
        self.zone_rij = Rij("wereld", t("Tijdzone", "Time zone"), "", zone_knop)
        g.voeg(self.zone_rij)
        g2 = self.kaart(t("Taal", "Language"))
        taal_knop = Knop(t("Andere taal…", "Other language…"), "gewoon")
        taal_knop.clicked.connect(self.kies_taal)
        self.taal_rij = Rij("praten", t("Taal van BugOS", "Language of BugOS"), "", taal_knop)
        g2.voeg(self.taal_rij)
        self.lay.addWidget(label(t("Nederlands en Engels zijn compleet. In andere talen zijn KDE en de meeste "
                                   "programma's vertaald; de BugOS-programma's zelf zijn dan in het Engels.",
                                   "Dutch and English are complete. In other languages KDE and most programs are "
                                   "translated; the BugOS programs themselves are then in English."), "klein"))

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.tijd(), bi.taal()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        tijd, code = uitkomst
        self.auto.zet_stil(tijd.auto)
        self.klok_rij.titel.setText(nu_tekst())
        self.klok_rij.zet_uitleg(t("Wordt vanzelf gelijkgezet via internet", "Set automatically over the internet")
                                 if tijd.auto else t("Zet je zelf gelijk (bij 'Meer instellingen')",
                                                     "You set it yourself (under 'More settings')"))
        self.zone_rij.zet_uitleg(bi.mooie_zone(tijd.zone, TAAL == "nl"))
        self.taal_rij.zet_uitleg(next((n for c, _l, n in bi.TALEN if c == code), code))

    def zet_auto(self, aan: bool) -> None:
        # Ook als het niet lukte (bijv. Annuleren bij het wachtwoord) opnieuw lezen: dan springt het schuifje terug.
        op_achtergrond(self, lambda: bi.zet_tijd_auto(aan), lambda ok: (self.ververs(), None if ok else self.melding.toon(
            t("Dat lukte niet.", "That did not work."), "fout")))

    def kies_zone(self) -> None:
        # timedatectl kan even duren: eerst op de achtergrond ophalen, dan pas de keuzelijst.
        op_achtergrond(self, lambda: (bi.tijd().zone, bi.tijdzones()), self.kies_zone_uit)

    def kies_zone_uit(self, uitkomst) -> None:
        if not isinstance(uitkomst, tuple):
            self.melding.toon(t("De tijdzones konden niet geladen worden.", "Could not load the time zones."), "fout")
            return
        nl = TAAL == "nl"
        huidig, zones = uitkomst
        d = KiesDialoog(self, t("Waar ben je?", "Where are you?"),
                        [(z, bi.mooie_zone(z, nl)) for z in zones], huidig,
                        t("Zoek een stad, bijvoorbeeld Amsterdam", "Search a city, for example London"))
        if not d.exec() or d.gekozen == huidig:
            return
        zone = d.gekozen
        self.melding.toon(t("Tijdzone wordt gezet… BugOS vraagt misschien je wachtwoord.",
                            "Setting the time zone… BugOS may ask for your password."), seconden=60)

        def klaar(ok) -> None:
            if ok:
                time.tzset()   # anders blijft dit programma de oude tijdzone gebruiken (en de klok bovenaan de oude tijd)
            self.melding.toon(t(f"De klok staat nu op {bi.mooie_zone(zone, nl)}.",
                                f"The clock is now set to {bi.mooie_zone(zone, nl)}.") if ok else
                              t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.zet_tijdzone(zone), klaar)

    def kies_taal(self) -> None:
        huidig = bi.taal()
        d = KiesDialoog(self, t("Welke taal?", "Which language?"), [(c, n) for c, _l, n in bi.TALEN], huidig)
        if not d.exec() or d.gekozen == huidig:
            return
        code = d.gekozen

        def klaar(ok) -> None:
            if ok:
                self.melding.toon(t("Klaar. Meld je af en weer aan, dan is alles in die taal.",
                                    "Done. Log out and back in, and everything is in that language."), "goed",
                                  t("Nu afmelden", "Log out now"), bi.afmelden, seconden=0)
            else:
                self.melding.toon(t("Dat lukte niet.", "That did not work."), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.zet_taal(code), klaar)


# ================================================== inloggen en wachtwoord ===

class InloggenPagina(Blad):
    sleutel, icoon = "inloggen", "persoon"
    titel_nl, titel_en = "Inloggen en wachtwoord", "Login and password"
    uitleg_nl = "Jouw naam en wachtwoord, en wanneer het scherm op slot gaat."
    uitleg_en = "Your name and password, and when the screen locks."
    zoekwoorden = ("inloggen aanmelden wachtwoord account gebruiker naam beheerder op slot vergrendelen "
                   "automatisch inloggen zonder wachtwoord")
    kde = "kcm_users"

    def bouw(self) -> None:
        self.gebruiker: bi.Gebruiker | None = None
        g = self.kaart()
        rechts = QWidget()
        rl = QHBoxLayout(rechts)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        ww = Knop(t("Wachtwoord wijzigen…", "Change password…"), "gewoon", "lijn:slot")
        ww.clicked.connect(self.wijzig_wachtwoord)
        rl.addWidget(ww)
        rl.addWidget(meer_knop(lambda: [("potlood", t("Naam wijzigen…", "Change name…"), self.wijzig_naam)]))
        self.ik = Rij("persoon", "…", "", rechts)
        g.voeg(self.ik)
        self.auto = schuifje(False, self.zet_auto)
        g.voeg(Rij("aan", t("Inloggen zonder wachtwoord", "Log in without a password"),
                   t("Handig thuis. Let op: iedereen die de computer aanzet, kan dan bij je bestanden.",
                     "Handy at home. Note: anyone who turns on the computer can then reach your files."), self.auto))
        g2 = self.kaart(t("Scherm op slot", "Screen lock"))
        self.slot = Keuzes([(5, t("5 min", "5 min")), (15, t("15 min", "15 min")), (30, t("30 min", "30 min")),
                            (0, t("Nooit", "Never"))])
        self.slot.gekozen.connect(lambda m: op_achtergrond(self, lambda: bi.zet_slot_na(m), lambda _u: None))
        g2.voeg(Rij("slot", t("Vanzelf op slot als je even weg bent", "Lock by itself when you step away"),
                    t("Daarna is je wachtwoord nodig", "Your password is needed after that"), self.slot))
        self.slot_slaap = schuifje(True, lambda aan: op_achtergrond(self, lambda: bi.zet_slot_na_slapen(aan),
                                                                     lambda _u: None))
        g2.voeg(Rij("maan", t("Wachtwoord vragen na de slaapstand", "Ask for the password after sleep"), "",
                    self.slot_slaap))
        nu = Knop(t("Nu op slot", "Lock now"), "gewoon", "lijn:slot")
        nu.clicked.connect(lambda _c=False: bi.vergrendel())
        g2.voeg(Rij("computer", t("Even weg?", "Stepping away?"), t("Zoals Windows-toets + L", "Like Windows key + L"),
                    nu))
        g3 = self.kaart(t("Andere mensen", "Other people"))
        rij = Rij("persoon", t("Iemand toevoegen", "Add someone"),
                  t("Een eigen account voor iemand anders, met eigen bestanden en instellingen",
                    "A separate account for someone else, with their own files and settings"), klikbaar=True)
        rij.geklikt.connect(lambda: kde_instelling("kcm_users"))
        g3.voeg(rij)

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.gebruiker(), bi.slot_na(), bi.slot_na_slapen()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        g, slot, slaap = uitkomst
        self.gebruiker = g
        self.ik.titel.setText(g.volledige_naam)
        self.ik.zet_uitleg(t(f"Inlognaam: {g.naam}", f"Login name: {g.naam}") +
                           (t(" · beheerder", " · administrator") if g.beheerder else ""))
        self.auto.zet_stil(g.auto_inloggen)
        self.slot.zet(dichtstbij(bi.SLOT_KEUZES, slot))
        self.slot_slaap.zet_stil(bool(slaap))

    def wijzig_naam(self) -> None:
        nieuw, ok = QInputDialog.getText(self, t("Je naam", "Your name"),
                                         t("Hoe heet je? Dit zie je op het inlogscherm.",
                                           "What is your name? You see this on the login screen."),
                                         text=self.gebruiker.volledige_naam if self.gebruiker else "")
        nieuw = nieuw.strip()
        if ok and nieuw:
            op_achtergrond(self, lambda: bi.zet_volledige_naam(nieuw), lambda goed: (
                self.melding.toon(t(f"Je heet nu {nieuw}.", f"You are now called {nieuw}.") if goed else
                                  t("Dat lukte niet.", "That did not work."), "goed" if goed else "fout"),
                self.ververs()))

    def wijzig_wachtwoord(self) -> None:
        # Een beheerder mag het via AccountsService (KDE vraagt dan je wachtwoord). Wie geen beheerder is, zou
        # daar het wachtwoord van een beheerder moeten typen; dan gaat het zoals in een terminal (passwd).
        eigen = self.gebruiker is not None and not self.gebruiker.beheerder
        d = WachtwoordDialoog(self, huidig=eigen)
        if not d.exec():
            return
        nieuw, huidig = d.wachtwoord, d.huidig_wachtwoord
        if eigen:
            self.melding.toon(t("Even geduld…", "One moment…"), seconden=90)
        else:
            self.melding.toon(t("Even geduld… BugOS vraagt eerst je huidige wachtwoord.",
                                "One moment… BugOS first asks for your current password."), seconden=90)

        def klaar(uitkomst) -> None:
            goed = bool(uitkomst and uitkomst[0])
            if goed:
                self.melding.toon(t("Je wachtwoord is veranderd.", "Your password has been changed."), "goed")
            elif uitkomst and uitkomst[1] == "simpel":
                self.melding.toon(t("Dat wachtwoord is te makkelijk te raden. Kies een langer wachtwoord, "
                                    "met verschillende soorten tekens.",
                                    "That password is too easy to guess. Choose a longer one, "
                                    "with different kinds of characters."), "fout", seconden=12)
            else:
                self.melding.toon(t("Dat lukte niet. Klopte je huidige wachtwoord?",
                                    "That did not work. Was your current password right?"), "fout")

        if eigen:
            op_achtergrond(self, lambda: bi.zet_eigen_wachtwoord(huidig, nieuw), klaar)
        else:
            op_achtergrond(self, lambda: bi.zet_wachtwoord(nieuw), klaar)

    def zet_auto(self, aan: bool) -> None:
        naam = self.gebruiker.naam if self.gebruiker else ""
        self.melding.toon(t("BugOS vraagt je wachtwoord…", "BugOS asks for your password…"), seconden=90)

        def klaar(ok) -> None:
            if ok:
                self.melding.toon(t("Voortaan log je vanzelf in.", "From now on you log in automatically.") if aan else
                                  t("Voortaan vraagt BugOS weer je wachtwoord.",
                                    "From now on BugOS asks for your password again."), "goed")
            else:
                self.melding.toon(t("Dat lukte niet.", "That did not work."), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.zet_auto_inloggen(aan, naam), klaar)
