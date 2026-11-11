"""BugOS Instellingen: de pagina's Tijd en taal, en Inloggen en wachtwoord."""

from __future__ import annotations

import time
from datetime import datetime

import bugos_config as bi
from bugos_ui import TAAL, Knop, Rij, kde_instelling, label, leeg_groep, ronde_pixmap, t, vraag_ja, vraag_tekst
from bugos_settings_onderdelen import (
    Blad, Keuzes, KiesDialoog, WachtwoordDialoog, dichtstbij, meer_knop, op_achtergrond, schuifje,
)
from PySide6.QtCore import QDate, QLocale, Qt, QTime, QTimer
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QDateEdit, QDialog, QGridLayout, QHBoxLayout, QTimeEdit, QVBoxLayout, QWidget


# ============================================================ tijd en taal ===

DAGEN = (("maandag", "Monday"), ("dinsdag", "Tuesday"), ("woensdag", "Wednesday"), ("donderdag", "Thursday"),
         ("vrijdag", "Friday"), ("zaterdag", "Saturday"), ("zondag", "Sunday"))
MAANDEN = (("januari", "January"), ("februari", "February"), ("maart", "March"), ("april", "April"), ("mei", "May"),
           ("juni", "June"), ("juli", "July"), ("augustus", "August"), ("september", "September"),
           ("oktober", "October"), ("november", "November"), ("december", "December"))


def _klok(d: datetime) -> str:
    """De tijd zoals de klok op de taakbalk hem schrijft: 14:58, of 2:58 PM als je notatie Amerikaans is (LC_TIME)."""
    return QLocale.system().toString(QTime(d.hour, d.minute), QLocale.FormatType.ShortFormat)


def nu_tekst() -> str:
    d = datetime.now().astimezone()
    dag, maand = DAGEN[d.weekday()], MAANDEN[d.month - 1]
    return t(f"{dag[0].capitalize()} {d.day} {maand[0]} {d.year} · {_klok(d)}", _engels_nu(d))


def _engels_nu(d: datetime) -> str:
    """In het Engels zoals je regio het schrijft: 9 November 2026 (Ierland, VK) of November 9, 2026, en 14:05 of
    2:05 PM zoals de klok op de taakbalk (U445). Ook voor Duits, Frans, Turks…: die krijgen de Engelse tekst van
    BugOS, maar de datum zoals hun eigen taal hem schrijft (Montag, 9. November 2026) (U452).
    Alleen zonder regio (C/POSIX): de Amerikaanse volgorde, 24 uur."""
    loc = QLocale.system()
    if loc.language() in (QLocale.Language.C, QLocale.Language.Dutch):
        dag, maand = DAGEN[d.weekday()], MAANDEN[d.month - 1]
        klok = f"{d:%H:%M}" if loc.language() == QLocale.Language.C else _klok(d)
        return f"{dag[1]} {maand[1]} {d.day}, {d.year} · {klok}"
    datum = loc.toString(QDate(d.year, d.month, d.day), QLocale.FormatType.LongFormat)
    tijd = loc.toString(QTime(d.hour, d.minute), QLocale.FormatType.ShortFormat)
    return f"{datum} · {tijd}"


def _met_heel_jaar(formaat: str) -> str:
    """'M/d/yy' -> 'M/d/yyyy': in een datumveld liever het hele jaartal (26 kan ook 1926 zijn)."""
    return formaat if "yyyy" in formaat else formaat.replace("yy", "yyyy")


class KlokDialoog(QDialog):
    """De klok zelf zetten (geen internet): een datum en een tijd, zoals je regio ze schrijft (ook AM/PM)."""

    def __init__(self, ouder: QWidget):
        super().__init__(ouder)
        self.setWindowTitle(t("Klok zelf instellen", "Set the clock yourself"))
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(label(t("Klok zelf instellen", "Set the clock yourself"), "kop2"))
        lay.addWidget(label(t("Kies de datum en de tijd. Daarna vraagt BugOS je wachtwoord.",
                              "Choose the date and the time. BugOS then asks for your password."), "klein"))
        loc = QLocale.system()
        rooster = QGridLayout()
        rooster.setHorizontalSpacing(12)
        rooster.setVerticalSpacing(4)
        self.datum = QDateEdit(QDate.currentDate())
        self.datum.setCalendarPopup(True)
        self.datum.setDateRange(QDate(2020, 1, 1), QDate(2099, 12, 31))
        self.datum.setDisplayFormat(_met_heel_jaar(loc.dateFormat(QLocale.FormatType.ShortFormat)))
        self.datum.setAccessibleName(t("Datum", "Date"))
        nu = QTime.currentTime()
        self.tijd = QTimeEdit(QTime(nu.hour(), nu.minute()))
        self.tijd.setDisplayFormat(loc.timeFormat(QLocale.FormatType.ShortFormat))
        self.tijd.setAccessibleName(t("Tijd", "Time"))
        for veld in (self.datum, self.tijd):
            veld.setMinimumHeight(36)
        rooster.addWidget(label(t("Datum", "Date"), "klein"), 0, 0)
        rooster.addWidget(label(t("Tijd", "Time"), "klein"), 0, 1)
        rooster.addWidget(self.datum, 1, 0)
        rooster.addWidget(self.tijd, 1, 1)
        rooster.setColumnStretch(0, 3)
        rooster.setColumnStretch(1, 2)
        lay.addLayout(rooster)
        lay.addSpacing(4)
        knoppen = QHBoxLayout()
        knoppen.setSpacing(8)
        knoppen.addStretch(1)
        weg = Knop(t("Annuleren", "Cancel"), "stil")
        weg.clicked.connect(self.reject)
        ok = Knop(t("Klok zetten", "Set clock"), "hoofd")
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        knoppen.addWidget(weg)
        knoppen.addWidget(ok)
        lay.addLayout(knoppen)
        self.datum.setFocus()

    @property
    def wanneer(self) -> datetime:
        d, u = self.datum.date(), self.tijd.time()
        return datetime(d.year(), d.month(), d.day(), u.hour(), u.minute())


class TijdPagina(Blad):
    sleutel, icoon = "tijd", "klok"
    titel_nl, titel_en = "Tijd en taal", "Time and language"
    uitleg_nl = "De klok, je tijdzone en de taal van BugOS."
    uitleg_en = "The clock, your time zone and the language of BugOS."
    zoekwoorden = ("tijd klok datum tijdzone zomertijd wintertijd taal nederlands engels language land time clock "
                   "date time zone timezone daylight saving language english dutch region")
    kde = "kcm_regionandlang"

    def bouw(self) -> None:
        g = self.kaart()
        self.auto = schuifje(True, self.zet_auto)
        # De regel toont de klok; het schuifje zelf zet de tijd vanzelf goed (anders noemt een schermlezer de tijd).
        self.auto.setAccessibleName(t("Tijd vanzelf instellen", "Set the time automatically"))
        self.klok_rij = Rij("klok", nu_tekst(), "", self.auto)
        g.voeg(self.klok_rij)
        # Zelf de klok gelijkzetten: een eigen venster van BugOS (vroeger KDE's Datum en tijd) (U474).
        self.zelf_rij = Rij("klok", t("Klok zelf instellen…", "Set the clock yourself…"),
                            t("Datum en tijd met de hand", "Date and time by hand"), klikbaar=True)
        self.zelf_rij.geklikt.connect(self.klok_zetten)
        g.voeg(self.zelf_rij)
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
        if not tijd.auto:
            uitleg = t("Zet je zelf gelijk met 'Klok zelf instellen…'",
                       "You set it yourself with 'Set the clock yourself…'")
        elif tijd.gelijk:
            uitleg = t("Wordt vanzelf gelijkgezet via internet", "Set automatically over the internet")
        else:
            uitleg = t("Wacht op internet om de klok gelijk te zetten", "Waiting for the internet to set the clock")
        self.klok_rij.zet_uitleg(uitleg)
        self.zelf_rij.setVisible(not tijd.auto)
        self.zone_rij.zet_uitleg(bi.mooie_zone(tijd.zone, TAAL == "nl"))
        self.taal_rij.zet_uitleg(next((n for c, _l, n in bi.TALEN if c == code), code))

    def zet_auto(self, aan: bool) -> None:
        # Ook als het niet lukte (bijv. Annuleren bij het wachtwoord) opnieuw lezen: dan springt het schuifje terug.
        op_achtergrond(self, lambda: bi.zet_tijd_auto(aan), lambda ok: (self.ververs(), None if ok else self.melding.toon(
            t("Dat lukte niet.", "That did not work."), "fout")))

    def klok_zetten(self) -> None:
        d = KlokDialoog(self)
        if not d.exec():
            return
        wanneer = d.wanneer
        self.melding.toon(t("Klok wordt gezet… BugOS vraagt je wachtwoord.",
                            "Setting the clock… BugOS asks for your password."), seconden=120)

        def klaar(uitkomst) -> None:
            ok, reden = uitkomst if isinstance(uitkomst, tuple) else (False, "fout")
            if ok:
                self.melding.toon(t("De klok is gezet.", "The clock has been set."), "goed")
                self.klok_rij.titel.setText(nu_tekst())
            elif reden == "auto":
                self.melding.toon(t("Zet eerst 'Tijd vanzelf instellen' uit.",
                                    "Turn off 'Set the time automatically' first."), "fout")
            else:
                self.melding.toon(t("Dat lukte niet.", "That did not work."), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.zet_klok(wanneer), klaar)

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

def _foto_icoon(pad: str, maat: int = 22) -> QIcon | None:
    """Een foto als rond icoontje (scherp op elk scherm), of None als het plaatje niet te openen is."""
    if not pad:
        return None
    beeld = QImage(pad)
    if beeld.isNull():
        return None
    zijde = min(beeld.width(), beeld.height())
    beeld = beeld.copy((beeld.width() - zijde) // 2, (beeld.height() - zijde) // 2, zijde, zijde)
    pix = QPixmap.fromImage(beeld.scaled(maat * 3, maat * 3, Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
    pix.setDevicePixelRatio(3)
    return QIcon(ronde_pixmap(pix, maat / 2))


class WachtwoordVoorDialoog(WachtwoordDialoog):
    """Een nieuw wachtwoord voor iemand anders: het venster zegt van wie, en welk wachtwoord BugOS daarna vraagt."""

    def __init__(self, ouder: QWidget, naam: str, beheerder: bool = True):
        super().__init__(ouder, huidig=False)
        titel = t("Nieuw wachtwoord voor {naam}", "New password for {naam}").format(naam=naam)
        self.setWindowTitle(titel)
        lay = self.layout()
        lay.itemAt(0).widget().setText(titel)
        uitleg = t("Minstens {n} tekens. Daarna logt {naam} in met dit wachtwoord.",
                   "At least {n} characters. {naam} then logs in with this password.").format(n=self.MINIMUM, naam=naam)
        uitleg += " " + (t("BugOS vraagt eerst nog één keer jouw eigen wachtwoord.",
                           "BugOS first asks for your own password once more.") if beheerder else
                         t("BugOS vraagt eerst het wachtwoord van een beheerder.",
                           "BugOS first asks for the password of an administrator."))
        lay.itemAt(1).widget().setText(uitleg)


BEZIG = ("Even geduld… BugOS vraagt je wachtwoord.", "One moment… BugOS asks for your password.")


def reden_tekst(reden: str, naam: str = "") -> str:
    """Waarom iets met een account niet lukte, in gewone woorden (nooit de foutmelding van het systeem)."""
    if reden == "geweigerd":
        return t("Er is niets veranderd: daarvoor is het wachtwoord van een beheerder nodig.",
                 "Nothing changed: this needs the password of an administrator.")
    if reden == "later":
        return t("Dat lukt pas na een herstart van de computer.", "This only works after restarting the computer.")
    if reden == "laatste":
        return t("Er moet altijd minstens één beheerder zijn.", "There must always be at least one administrator.")
    if reden == "ingelogd":
        return t("{naam} is nog ingelogd. Laat {naam} eerst afmelden, of start de computer opnieuw.",
                 "{naam} is still logged in. Ask {naam} to log out first, or restart the computer.").format(naam=naam)
    return t("Dat lukte niet.", "That did not work.")


class InloggenPagina(Blad):
    sleutel, icoon = "inloggen", "persoon"
    titel_nl, titel_en = "Inloggen en wachtwoord", "Login and password"
    uitleg_nl = "Jouw naam, foto en wachtwoord, andere mensen, en wanneer het scherm op slot gaat."
    uitleg_en = "Your name, picture and password, other people, and when the screen locks."
    zoekwoorden = ("inloggen aanmelden wachtwoord account gebruiker naam beheerder op slot vergrendelen automatisch "
                   "inloggen zonder wachtwoord login log in sign in password account user name administrator admin "
                   "lock screen lock automatic login "
                   "mensen persoon toevoegen verwijderen kind kinderen gezin gast foto profielfoto plaatje "
                   "people person add remove family guest picture photo avatar account type standard")
    kde = "kcm_users"

    def bouw(self) -> None:
        self.gebruiker: bi.Gebruiker | None = None
        self.mensen: list[bi.Persoon] = []
        self.mensen_rijen: list[Rij] = []
        g = self.kaart()
        rechts = QWidget()
        rl = QHBoxLayout(rechts)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        ww = Knop(t("Wachtwoord wijzigen…", "Change password…"), "gewoon", "lijn:slot")
        ww.clicked.connect(self.wijzig_wachtwoord)
        rl.addWidget(ww)
        rl.addWidget(meer_knop(self.menu_ik))
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
        self.g3 = self.kaart(t("Andere mensen", "Other people"))
        self.vul_mensen([])
        # Wie geen beheerder is, mag het ook proberen: dan vraagt BugOS het wachtwoord van een beheerder (zoals Windows).
        self.alleen_beheerder = label(t("Iemand toevoegen of weghalen kan alleen met het wachtwoord van een beheerder.",
                                        "Adding or removing someone needs the password of an administrator."), "klein")
        self.alleen_beheerder.hide()
        self.lay.addWidget(self.alleen_beheerder)

    def vul_mensen(self, lijst: list[bi.Persoon]) -> None:
        """De kaart Andere mensen opnieuw vullen: iedereen behalve jij, op naam, en onderaan 'Iemand toevoegen'."""
        self.mensen = list(lijst)
        leeg_groep(self.g3)
        self.mensen_rijen = []
        for p in sorted((p for p in lijst if not p.ik), key=lambda p: (p.volledige_naam.casefold(), p.naam)):
            uitleg = (t("Beheerder", "Administrator") if p.beheerder else t("Standaard", "Standard"))
            uitleg += t(" · inlognaam {naam}", " · login name {naam}").format(naam=p.naam)
            if p.ingelogd:
                uitleg += t(" · nu ingelogd", " · logged in now")
            rij = Rij(_foto_icoon(p.foto) or "persoon", p.volledige_naam, uitleg,
                      meer_knop(lambda p=p: self.menu_voor(p)))
            rij.persoon = p
            self.g3.voeg(rij)
            self.mensen_rijen.append(rij)
        self.voeg_rij = Rij("persoon", t("Iemand toevoegen", "Add someone"),
                            t("Een eigen account voor iemand anders, met eigen bestanden en instellingen",
                              "A separate account for someone else, with their own files and settings"), klikbaar=True)
        self.voeg_rij.geklikt.connect(lambda: kde_instelling("kcm_users"))
        self.g3.voeg(self.voeg_rij)

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.gebruiker(), bi.slot_na(), bi.slot_na_slapen(), bi.mensen()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        g, slot, slaap = uitkomst[:3]
        self.gebruiker = g
        self.ik.titel.setText(g.volledige_naam)
        self.ik.zet_uitleg(t(f"Inlognaam: {g.naam}", f"Login name: {g.naam}") +
                           (t(" · beheerder", " · administrator") if g.beheerder else ""))
        self.ik.zet_icoon(_foto_icoon(getattr(g, "foto", "")) or "persoon")
        self.auto.zet_stil(g.auto_inloggen)
        self.slot.zet(dichtstbij(bi.SLOT_KEUZES, slot))
        self.slot_slaap.zet_stil(bool(slaap))
        self.alleen_beheerder.setVisible(not g.beheerder)
        if len(uitkomst) > 3 and uitkomst[3] is not None:   # (een oude aanroeper geeft er drie: mensen dan laten)
            self.vul_mensen(uitkomst[3])

    # ------------------------------------------------------------------ jij ---

    def menu_ik(self) -> list:
        return [("potlood", t("Naam wijzigen…", "Change name…"), self.wijzig_naam)]

    def wijzig_naam(self) -> None:
        nieuw = vraag_tekst(self, t("Je naam", "Your name"),
                            t("Hoe heet je? Dit zie je op het inlogscherm.",
                              "What is your name? You see this on the login screen."),
                            self.gebruiker.volledige_naam if self.gebruiker else "", t("Opslaan", "Save"))
        nieuw = (nieuw or "").strip()
        if nieuw:
            op_achtergrond(self, lambda: bi.zet_volledige_naam(nieuw), lambda goed: (
                self.melding.toon(t("Je heet nu {naam}.", "You are now called {naam}.").format(naam=nieuw) if goed else
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

    # -------------------------------------------------------- andere mensen ---

    def menu_voor(self, p: bi.Persoon) -> list:
        items = [("slot", t("Nieuw wachtwoord…", "Set a new password…"), lambda: self.nieuw_wachtwoord_voor(p))]
        if p.beheerder:
            items.append(("persoon", t("Gewone gebruiker maken", "Make standard user"), lambda: self.zet_soort(p, False)))
        else:
            items.append(("persoon", t("Beheerder maken", "Make administrator"), lambda: self.zet_soort(p, True)))
        if not bi.laatste_beheerder(p, self.mensen):
            items.append(("prullenbak", t("Verwijderen…", "Remove…"), lambda: self.verwijder(p)))
        return items

    def _bezig(self) -> None:
        self.melding.toon(t(*BEZIG), seconden=120)

    def zet_soort(self, p: bi.Persoon, beheerder: bool) -> None:
        naam = p.volledige_naam
        if beheerder and not vraag_ja(
                self, t("Beheerder maken?", "Make administrator?"),
                t("{naam} kan dan apps installeren, andere mensen toevoegen en alles op deze computer veranderen.",
                  "{naam} can then install apps, add other people and change everything on this computer."
                  ).format(naam=naam),
                t("Beheerder maken", "Make administrator")):
            return
        self._bezig()
        alle = list(self.mensen)

        def klaar(uitkomst) -> None:
            ok, reden = uitkomst if isinstance(uitkomst, tuple) else (False, "fout")
            if ok:
                tekst = (t("{naam} is nu beheerder.", "{naam} is now an administrator.") if beheerder else
                         t("{naam} is nu een gewone gebruiker.", "{naam} is now a standard user.")).format(naam=naam)
                if p.ingelogd:
                    tekst += t(" Dat geldt vanaf de volgende keer dat die inlogt.",
                               " It counts from the next time they log in.")
                self.melding.toon(tekst, "goed")
            else:
                self.melding.toon(reden_tekst(reden, naam), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.zet_soort(p, beheerder, alle), klaar)

    def verwijder(self, p: bi.Persoon) -> None:
        naam = p.volledige_naam
        if p.ingelogd:   # meteen zeggen, niet eerst een wachtwoord vragen
            self.melding.toon(reden_tekst("ingelogd", naam), "fout", seconden=12)
            return
        if not vraag_ja(self, t("{naam} verwijderen?", "Remove {naam}?").format(naam=naam),
                        t("Het account en alle bestanden van {naam} (documenten, foto's, downloads) gaan van deze "
                          "computer af. Dat kan niet ongedaan worden. Wil je iets bewaren? Log dan eerst in als {naam} "
                          "en zet het op een USB-stick.",
                          "The account and all files of {naam} (documents, photos, downloads) are removed from this "
                          "computer. This cannot be undone. Want to keep something? Log in as {naam} first and copy "
                          "it to a USB stick.").format(naam=naam),
                        t("Verwijderen", "Remove"), enter_is_nee=True):
            return
        self._bezig()
        alle = list(self.mensen)

        def klaar(uitkomst) -> None:
            ok, reden = uitkomst if isinstance(uitkomst, tuple) else (False, "fout")
            if ok:
                self.melding.toon(t("{naam} is verwijderd.", "{naam} has been removed.").format(naam=naam), "goed")
            else:
                self.melding.toon(reden_tekst(reden, naam), "fout", seconden=12 if reden == "ingelogd" else 7)
            self.ververs()

        op_achtergrond(self, lambda: bi.verwijder_persoon(p, alle), klaar)

    def nieuw_wachtwoord_voor(self, p: bi.Persoon) -> None:
        naam = p.volledige_naam
        d = WachtwoordVoorDialoog(self, naam, self.gebruiker is None or self.gebruiker.beheerder)
        if not d.exec():
            return
        nieuw = d.wachtwoord
        d.een.setText("")
        d.twee.setText("")
        self._bezig()

        def klaar(uitkomst) -> None:
            ok, reden = uitkomst if isinstance(uitkomst, tuple) else (False, "fout")
            self.melding.toon(t("Het wachtwoord van {naam} is veranderd.", "{naam}'s password has been changed."
                                ).format(naam=naam) if ok else reden_tekst(reden, naam), "goed" if ok else "fout")

        op_achtergrond(self, lambda: bi.zet_wachtwoord_van(p.uid, nieuw), klaar)
