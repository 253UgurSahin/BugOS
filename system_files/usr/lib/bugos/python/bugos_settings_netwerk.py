"""BugOS Instellingen: de pagina's Wifi en internet, en Bluetooth."""

from __future__ import annotations

from pathlib import Path

import bugos_config as bi
from bugos_ui import (K, Banner, Groep, Knop, Rij, label, leeg_groep, lijn_icoon, schermmaat, schuifbaar,
                      sectie_met_knop, t, vraag_tekst)
from bugos_settings_onderdelen import Blad, Doorloop, Keuzes, meer_knop, op_achtergrond, schuifje
from PySide6.QtCore import ClassInfo, QEventLoop, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QStackedWidget,
                               QVBoxLayout, QWidget)

try:   # D-Bus (BlueZ): zit in PySide6 in de image; zonder zegt 'Apparaat toevoegen' dat bluetooth het niet doet
    from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusObjectPath, QDBusPendingCallWatcher
except ImportError:  # pragma: no cover
    QDBusConnection = QDBusMessage = QDBusObjectPath = QDBusPendingCallWatcher = None


def vrije_hoogte(w: QWidget | None = None) -> int:
    """Hoe hoog een venster hier mag zijn (het scherm zonder taakbalk en titelbalk)."""
    scherm = w.screen() if w is not None and w.screen() is not None else None
    return schermmaat((0, 99999), scherm=scherm)[0][1]


def knoppenrij(*knoppen: QWidget) -> QHBoxLayout:
    """Rechts onderin een dialoog: eerst de stille knop, dan de rode."""
    rij = QHBoxLayout()
    rij.setSpacing(8)
    rij.addStretch(1)
    for k in knoppen:
        rij.addWidget(k)
    return rij


# ================================================================== wifi ===

def sterkte_woord(n: int) -> str:
    return t("Sterk", "Strong") if n >= 70 else t("Goed", "Good") if n >= 45 else t("Zwak", "Weak")


def hoogte_zonder(lay: QVBoxLayout, breedte: int, behalve: QWidget) -> int:
    """Hoe hoog alles in een dialoog is, behalve één onderdeel (het schuifvlak): afgebroken tekst op de echte breedte."""
    m = lay.contentsMargins()
    totaal, zichtbaar = m.top() + m.bottom(), 0
    binnen = max(100, breedte - m.left() - m.right())
    for i in range(lay.count()):
        it = lay.itemAt(i)
        w = it.widget()
        if w is not None and w.isHidden():
            continue
        zichtbaar += 1   # ook het schuifvlak en een spacer: tussen elk paar staat 'spacing'
        if w is behalve:
            continue
        if it.spacerItem() is not None:
            totaal += it.sizeHint().height()
            continue
        totaal += it.heightForWidth(binnen) if it.hasHeightForWidth() else it.sizeHint().height()
    return totaal + lay.spacing() * max(0, zichtbaar - 1)


def fout_regel() -> tuple[QWidget, QLabel]:
    """Een korte regel met een teken en rode tekst (kleur alleen is niet genoeg: altijd met een symbool)."""
    w = QWidget()
    r = QHBoxLayout(w)
    r.setContentsMargins(0, 0, 0, 0)
    r.setSpacing(8)
    teken = QLabel()
    teken.setPixmap(lijn_icoon("uitroep", K["fout"], 16, gekozen=None).pixmap(16, 16))
    r.addWidget(teken, 0, Qt.AlignmentFlag.AlignTop)
    tekst = label("", "klein")
    tekst.setStyleSheet(f"color: {K['fout']};")
    r.addWidget(tekst, 1)
    w.hide()
    return w, tekst


class ZakelijkDialoog(QDialog):
    """Wifi van school of werk (eduroam): je eigen gebruikersnaam en wachtwoord, zoals op je telefoon. Onder 'Meer
    opties' de manier van inloggen en de controle van het certificaat. Opent met open() en zegt het met klaar(bool)."""

    klaar = Signal(bool)

    def __init__(self, ouder: QWidget, naam: str = "", profiel: bi.ZakelijkProfiel | None = None,
                 fout: tuple[str, str, str] | None = None, verborgen: bool = False):
        super().__init__(ouder)
        self.naam = naam
        self.bewerkbaar = not naam
        p = profiel or bi.ZakelijkProfiel(naam, verborgen=verborgen)
        self.verborgen = verborgen or p.verborgen
        self.uuid = p.uuid
        self.nieuw_uuid = ""
        self.bezig = False
        self.gestopt = False
        self.gelukt = False
        self.domein_zelf = bool(p.domein)
        # Pas iets zeggen over het domein als je klaar bent met je gebruikersnaam (niet al bij de eerste letter).
        self.gebruiker_af = bool(p.gebruiker)
        self.ca_pad = p.ca_bestand
        kop = (t("Verbinden met {naam}", "Connect to {naam}").format(naam=naam) if naam else
               t("Netwerk van school of werk", "School or work network"))
        self.setWindowTitle(kop)
        self.setMinimumWidth(min(520, max(360, schermmaat((99999, 0), scherm=ouder.screen())[0][0] - 40)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        self.kop = label(kop, "kop2")
        lay.addWidget(self.kop)
        lay.addWidget(label(t("Dit netwerk van school of werk vraagt je eigen gebruikersnaam en wachtwoord. Je vindt ze "
                              "op de ICT-pagina van je school of werk.",
                              "This school or work network asks for your own user name and password. Your school's "
                              "or work's IT page has them."), "klein"))
        self.banner = Banner()
        lay.addWidget(self.banner)

        binnen = self.binnen = QWidget()
        bl = QVBoxLayout(binnen)
        bl.setContentsMargins(0, 0, 8, 0)
        bl.setSpacing(6)

        def veld(kopje: str, lay_, hint: str = "", tekst: str = "") -> QLineEdit:
            lay_.addWidget(label(kopje, "rij"))
            e = QLineEdit(tekst)
            e.setPlaceholderText(hint)
            e.setAccessibleName(kopje)
            e.setMinimumHeight(36)
            lay_.addWidget(e)
            lay_.addSpacing(4)
            return e

        self.netnaam = veld(t("Naam van het netwerk", "Network name"), bl) if self.bewerkbaar else None
        self.gebruiker = veld(t("Gebruikersnaam", "User name"), bl, t("bijvoorbeeld naam@school.nl",
                                                                      "for example name@school.edu"), p.gebruiker)
        self.wachtwoord = veld(t("Wachtwoord", "Password"), bl)
        self.wachtwoord.setEchoMode(QLineEdit.EchoMode.Password)
        self.oog = self.wachtwoord.addAction(lijn_icoon("oog", "tekst2", 18, gekozen=None),
                                             QLineEdit.ActionPosition.TrailingPosition)
        self.oog.setCheckable(True)
        self.oog.setToolTip(t("Wachtwoord laten zien", "Show password"))
        self.oog.toggled.connect(lambda aan: self.wachtwoord.setEchoMode(
            QLineEdit.EchoMode.Normal if aan else QLineEdit.EchoMode.Password))

        self.meer = Knop(t("Meer opties", "More options"), "stil", "lijn:rechts")
        self.meer.setCheckable(True)
        self.meer.setAutoDefault(False)
        self.meer.toggled.connect(self.toon_meer)
        bl.addWidget(self.meer, 0, Qt.AlignmentFlag.AlignLeft)

        opties = self.opties = QWidget()
        ol = QVBoxLayout(opties)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(6)
        ol.addWidget(label(t("Manier van inloggen", "Sign-in method"), "rij"))
        self.methode = Keuzes([("peap", "PEAP"), ("ttls", "TTLS")])
        self.methode_keus = p.methode if p.methode in ("peap", "ttls") else "peap"
        self.methode.zet(self.methode_keus)
        self.methode.gekozen.connect(self.kies_methode)
        ol.addWidget(self.methode, 0, Qt.AlignmentFlag.AlignLeft)
        ol.addWidget(label(t("Weet je het niet? Laat PEAP staan: dat gebruiken de meeste scholen en bedrijven.",
                             "Not sure? Keep PEAP: most schools and companies use it."), "klein"))
        ol.addSpacing(4)
        self.anoniem = veld(t("Anonieme naam (niet verplicht)", "Anonymous name (optional)"), ol,
                            t("bijvoorbeeld anonymous@school.nl", "for example anonymous@school.edu"), p.anoniem)
        self.controle = schuifje(p.controleer, lambda _aan: self.werk_bij())
        self.controle_rij = Rij("slot", t("Controleer dat dit echt jouw netwerk is",
                                          "Check that this is really your network"),
                                t("Aangeraden. Dan kan een nepnetwerk met dezelfde naam je wachtwoord niet stelen.",
                                  "Recommended. A fake network with the same name then cannot steal your password."),
                                self.controle)
        self.controle_rij.layout().setContentsMargins(0, 4, 0, 4)
        ol.addWidget(self.controle_rij)
        self.domein = veld(t("Domein van de server", "Server domain"), ol, t("school.nl", "school.edu"), p.domein)
        ol.addWidget(label(t("Staat op de ICT-pagina van je school of werk, bijvoorbeeld school.nl.",
                             "On your school's or work's IT page, for example school.edu."), "klein"))
        ol.addSpacing(4)
        ca_rij = QHBoxLayout()
        ca_rij.setSpacing(8)
        self.ca_knop = Knop(t("Certificaatbestand kiezen…", "Choose certificate file…"), "stil", "lijn:document")
        self.ca_knop.setAutoDefault(False)
        self.ca_knop.clicked.connect(lambda _c=False: self.kies_ca())
        ca_rij.addWidget(self.ca_knop)
        self.ca_naam = label("", "klein", wrap=False)
        ca_rij.addWidget(self.ca_naam)
        self.ca_weg = Knop("", "stil", "lijn:kruis")
        self.ca_weg.setAccessibleName(t("Certificaatbestand weghalen", "Remove certificate file"))
        self.ca_weg.setToolTip(self.ca_weg.accessibleName())
        self.ca_weg.setAutoDefault(False)
        self.ca_weg.clicked.connect(lambda _c=False: self.zet_ca(""))
        ca_rij.addWidget(self.ca_weg)
        ca_rij.addStretch(1)
        ol.addLayout(ca_rij)
        ol.addWidget(label(t("Bestand van de ICT-afdeling (niet verplicht)", "File from your IT department (optional)"),
                           "klein"))
        self.waarschuwing = Banner()
        ol.addWidget(self.waarschuwing)
        opties.hide()
        bl.addWidget(opties)
        bl.addStretch(1)
        self.vlak = schuifbaar(binnen)
        lay.addWidget(self.vlak, 1)

        # Waarom 'Verbinden' nog niet kan, boven de knoppen (ook als 'Meer opties' dicht of weggeschoven is) (N9).
        self.hint, self.hint_tekst = fout_regel()
        lay.addWidget(self.hint)
        lay.addSpacing(4)
        self.weg = Knop(t("Annuleren", "Cancel"), "stil")
        self.weg.clicked.connect(self.reject)
        self.ok = Knop(t("Verbinden", "Connect"), "hoofd")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.verbind)
        lay.addLayout(knoppenrij(self.weg, self.ok))

        for e in (self.netnaam, self.gebruiker, self.wachtwoord, self.anoniem):
            if e is not None:
                e.textChanged.connect(lambda _t: self.werk_bij())
        self.gebruiker.textEdited.connect(self.gebruiker_getypt)
        self.gebruiker.editingFinished.connect(self.gebruiker_klaar)
        self.wachtwoord.textEdited.connect(lambda _t: self.gebruiker_klaar())
        self.domein.textEdited.connect(lambda _t: (setattr(self, "domein_zelf", True), self.werk_bij()))
        self.domein.textChanged.connect(lambda _t: self.werk_bij())
        self.zet_ca(self.ca_pad)
        if p.gebruiker and not self.domein_zelf:
            self.gebruiker_getypt(p.gebruiker)
        self.werk_bij()
        (self.netnaam or (self.wachtwoord if p.gebruiker else self.gebruiker)).setFocus()
        if fout:
            self.toon_fout(*fout)
        self.pas_hoogte()

    # ---------------------------------------------------------------- velden
    def gebruiker_getypt(self, tekst: str) -> None:
        if not self.domein_zelf:
            self.domein.setText(bi.standaard_domein(tekst))

    def gebruiker_klaar(self) -> None:
        if self.gebruiker.text().strip() and not self.gebruiker_af:
            self.gebruiker_af = True
            self.werk_bij()

    def kies_methode(self, waarde) -> None:
        self.methode_keus = waarde
        self.werk_bij()

    def toon_meer(self, open_: bool) -> None:
        self.opties.setVisible(open_)
        self.meer.setIcon(lijn_icoon("onder" if open_ else "rechts"))
        self.pas_hoogte()

    def open_meer(self, focus: QWidget | None = None, zien: QWidget | None = None) -> None:
        if not self.meer.isChecked():
            self.meer.setChecked(True)
        if focus is not None:
            QTimer.singleShot(0, lambda: (self.vlak.ensureWidgetVisible(focus), focus.setFocus()))
        elif zien is not None:
            QTimer.singleShot(0, lambda: self.vlak.ensureWidgetVisible(zien))

    def kies_ca(self) -> None:
        pad, _ = QFileDialog.getOpenFileName(self, t("Certificaatbestand kiezen", "Choose certificate file"),
                                             str(Path.home() / "Downloads"),
                                             t("Certificaten", "Certificates") + " (*.pem *.crt *.cer *.der);;"
                                             + t("Alle bestanden", "All files") + " (*)")
        if pad:
            self.zet_ca(pad)

    def zet_ca(self, pad: str) -> None:
        self.ca_pad = pad
        self.ca_naam.setText(Path(pad).name if pad else "")
        self.ca_naam.setVisible(bool(pad))
        self.ca_weg.setVisible(bool(pad))
        self.werk_bij()

    def waarom_niet(self) -> str:
        """Waarom 'Verbinden' nog niet kan ('' = het kan). Alleen over het domein; lege velden spreken voor zich."""
        if not self.controle.isChecked() or self.ca_pad:
            return ""
        d = self.domein.text().strip()
        if not d:
            return (t("Vul bij Meer opties het domein van de server in (bijvoorbeeld school.nl), of zet de controle uit.",
                      "Under More options, fill in the server domain (for example school.edu), or turn the check off.")
                    if self.gebruiker.text().strip() else "")
        if not bi.geldig_domein(d):
            return t("'{d}' is geen domein. Vul iets in als school.nl.",
                     "'{d}' is not a domain. Fill in something like school.edu.").format(d=d)
        return ""

    def werk_bij(self) -> None:
        if not hasattr(self, "ok"):
            return
        reden = self.waarom_niet()
        waarom = reden if self.gebruiker_af else ""
        if waarom and self.hint.isHidden() and not self.meer.isChecked():
            # Het domein staat bij Meer opties: dan meteen openklappen (geen grijze knop zonder reden) (N9).
            # Alleen in beeld, niet de focus: wie met Tab naar het wachtwoord gaat, typt het anders in het domeinveld.
            self.open_meer(zien=self.domein)
        self.hint_tekst.setText(waarom)
        zichtbaar = bool(waarom)
        if zichtbaar == self.hint.isHidden():
            self.hint.setVisible(zichtbaar)
            self.pas_hoogte()
        klaar = (bool(self.gebruiker.text().strip()) and bool(self.wachtwoord.text())
                 and (self.netnaam is None or bool(self.netnaam.text().strip())) and not reden)
        self.ok.setEnabled(klaar and not self.bezig)
        if not self.controle.isChecked():
            self.waarschuwing.zet(
                t("Niet controleren is met TTLS extra onveilig: een nepnetwerk kan je wachtwoord dan gewoon lezen. Doe "
                  "dit alleen als je school of werk dat zegt.",
                  "Not checking is extra unsafe with TTLS: a fake network could simply read your password. Only do "
                  "this if your school or work says so.") if self.methode_keus == "ttls" else
                t("Niet controleren is minder veilig: een nepnetwerk met dezelfde naam kan dan je wachtwoord "
                  "onderscheppen. Doe dit alleen als je school of werk dat zegt.",
                  "Not checking is less safe: a fake network with the same name could then catch your password. "
                  "Only do this if your school or work says so."), "let_op")
        elif not self.waarschuwing.isHidden():
            self.waarschuwing.zet("")
        self.domein.setEnabled(self.controle.isChecked() and not self.bezig)

    def pas_hoogte(self) -> None:
        """Zo hoog als de inhoud, maar nooit hoger dan het scherm: dan schuift het middenstuk, de knoppen blijven."""
        lay = self.layout()
        breed = max(self.width(), self.minimumWidth())
        rest = hoogte_zonder(lay, breed, self.vlak)
        binnen_breed = max(100, breed - 48 - 12)
        bl = self.binnen.layout()
        binnen = bl.totalHeightForWidth(binnen_breed) if bl.hasHeightForWidth() else bl.totalSizeHint().height()
        maxh = max(140, vrije_hoogte(self) - rest)
        self.vlak.setMinimumHeight(min(binnen, maxh))
        self.vlak.setMaximumHeight(maxh)
        self.resize(breed, rest + min(binnen, maxh))

    # ---------------------------------------------------------------- verbinden
    def profiel(self) -> bi.ZakelijkProfiel:
        naam = self.netnaam.text().strip() if self.netnaam is not None else self.naam
        controleer = self.controle.isChecked()
        return bi.ZakelijkProfiel(naam, self.gebruiker.text().strip(), self.methode_keus, self.anoniem.text().strip(),
                                  controleer, self.domein.text().strip().lower() if controleer else "",
                                  self.ca_pad if controleer else "", self.verborgen, self.uuid)

    def zet_bezig(self, bezig: bool) -> None:
        self.bezig = bezig
        for w in (self.netnaam, self.gebruiker, self.wachtwoord, self.meer, self.opties):
            if w is not None:
                w.setEnabled(not bezig)
        self.ok.setText(t("Verbinden…", "Connecting…") if bezig else t("Verbinden", "Connect"))
        self.werk_bij()

    def verbind(self) -> None:
        if self.bezig or not self.ok.isEnabled():
            return
        p = self.profiel()
        ww = self.wachtwoord.text()
        nieuw_ca = bool(p.ca_bestand) and not p.ca_bestand.startswith(str(Path.home() / ".cert" / "bugos-wifi"))
        self.naam = p.naam
        self.zet_bezig(True)
        self.banner.zet(t("Verbinden met {naam}… Dit kan tot een minuut duren.",
                          "Connecting to {naam}… This can take up to a minute.").format(naam=p.naam), "bezig")
        self.pas_hoogte()
        # Eerst opslaan (snel), dan verbinden (tot een minuut): zo weet Annuleren tijdens het verbinden welk profiel
        # het moet stoppen en weggooien.
        nieuw = not p.uuid or p.uuid == self.nieuw_uuid   # door dit venster gemaakt en nog nooit verbonden

        def opslaan():
            if nieuw_ca:
                pad, f = bi.kopieer_ca(p.ca_bestand, p.naam)
                if f:
                    return p.uuid, f
                p.ca_bestand = pad
            return bi.bewaar_zakelijk(p)

        op_achtergrond(self, opslaan, lambda u: self.opgeslagen(u, p, ww, nieuw))

    def opgeslagen(self, uitkomst, p: bi.ZakelijkProfiel, ww: str, nieuw: bool) -> None:
        uuid, f = uitkomst or ("", "opslaan")
        if uuid:
            self.uuid = uuid
            if nieuw:
                self.nieuw_uuid = uuid
        if self.gestopt:
            # Geannuleerd terwijl het opsloeg: een nieuw profiel blijft niet staan.
            if nieuw and uuid:
                op_achtergrond(self.parent() or self, lambda: bi.vergeet_profiel(uuid), lambda _u: None)
            return
        if p.ca_bestand and p.ca_bestand != self.ca_pad:
            self.zet_ca(p.ca_bestand)   # voortaan de kopie in ~/.cert
        if f or not uuid:
            self.zet_bezig(False)
            self.toon_fout(f or "opslaan")
            return

        def werk():
            ok, soort, reden, server = bi.verbind_zakelijk(uuid, ww)
            if ok and nieuw:
                bi.zet_vanzelf(uuid)   # pas nu het werkt: voortaan vanzelf verbinden (N4)
            return ok, soort, reden, server

        op_achtergrond(self, werk, self.verbonden)

    def verbonden(self, uitkomst) -> None:
        if self.gestopt:
            return   # Annuleren heeft het al gestopt (en een nieuw profiel weggegooid)
        ok, soort, reden, server = uitkomst or (False, "anders", "", "")
        self.zet_bezig(False)
        if ok:
            self.gelukt = True
            self.nieuw_uuid = ""
            self.wachtwoord.clear()
            self.banner.zet("")
            self.klaar.emit(True)
            super().accept()
            return
        self.toon_fout(soort, reden, server)

    def toon_fout(self, soort: str, reden: str = "", server: str = "") -> None:
        naam = self.naam or (self.netnaam.text().strip() if self.netnaam is not None else "")
        domein = self.domein.text().strip()
        server = bi.veilige_server(server)
        focus: QWidget | None = self.wachtwoord
        meer = False
        if soort == "wachtwoord":
            tekst = t("Inloggen lukte niet. Kloppen je gebruikersnaam en wachtwoord? Let op hoofdletters.",
                      "Signing in did not work. Are your user name and password right? Mind capitals.")
            self.wachtwoord.selectAll()
        elif soort == "inloggen":
            tekst = t("Inloggen lukte niet. Kijk of je gebruikersnaam en wachtwoord kloppen. Kloppen die, kijk dan bij "
                      "Meer opties of de manier van inloggen en het domein passen bij wat je school of werk zegt.",
                      "Signing in did not work. Check your user name and password. If they are right, check under "
                      "More options that the sign-in method and the domain match what your school or work says.")
        elif soort == "nodig":
            self.banner.zet(t("Typ je wachtwoord om te verbinden.", "Type your password to connect."), "info")
            self.pas_hoogte()
            self.wachtwoord.setFocus()
            return
        elif soort == "methode":
            tekst = t("Dit netwerk gebruikt een andere manier van inloggen. Kies bij Meer opties de andere manier "
                      "(PEAP of TTLS) en probeer het opnieuw.",
                      "This network uses a different way of signing in. Under More options, choose the other method "
                      "(PEAP or TTLS) and try again.")
            meer, focus = True, self.methode.knoppen.get(self.methode_keus)
        elif soort == "certificaat" and reden == "domein":
            tekst = (t("Het certificaat van het netwerk hoort bij '{server}', niet bij '{domein}'. Kijk op de "
                       "ICT-pagina van je school of werk welk domein je invult.",
                       "The network's certificate belongs to '{server}', not to '{domein}'. Check your school's or "
                       "work's IT page for the domain to fill in.") if server else
                     t("Het certificaat van het netwerk past niet bij het domein '{domein}'. Kijk op de ICT-pagina "
                       "van je school of werk welk domein je invult.",
                       "The network's certificate does not match the domain '{domein}'. Check your school's or "
                       "work's IT page for the domain to fill in.")).format(server=server, domein=domein)
            meer, focus = True, self.domein
        elif soort == "certificaat" and reden == "tijd":
            tekst = t("Het certificaat van dit netwerk is verlopen of nog niet geldig. Klopt de klok van deze computer? "
                      "Anders: meld het bij de ICT-afdeling.",
                      "This network's certificate has expired or is not valid yet. Is this computer's clock right? "
                      "Otherwise: tell your IT department.")
            focus = None
        elif soort == "certificaat":
            # Zonder 'of zet de controle uit': juist bij een nepnetwerk zie je deze melding (N12).
            tekst = t("BugOS kent de uitgever van het certificaat van dit netwerk niet. Vraag de ICT-afdeling om het "
                      "certificaatbestand en kies het bij Meer opties.",
                      "BugOS does not know who issued this network's certificate. Ask your IT department for the "
                      "certificate file and choose it under More options.")
            meer, focus = True, self.ca_knop
        elif soort == "ca_bestand":
            tekst = t("Dit bestand is geen certificaat. Vraag de ICT-afdeling om het juiste bestand.",
                      "This file is not a certificate. Ask your IT department for the right file.")
            meer, focus = True, self.ca_knop
        elif soort == "bereik":
            tekst = t("{naam} is nu niet te vinden. Ben je dichtbij genoeg?",
                      "{naam} cannot be found right now. Are you close enough?").format(naam=naam)
            focus = None
        elif soort == "traag":
            tekst = t("Het duurde te lang. Probeer het nog eens; lukt het weer niet, kijk dan bij Meer opties.",
                      "It took too long. Try again; if it fails again, check More options.")
            focus = None
        elif soort == "apparaat":
            tekst = t("De wifi van deze computer is niet klaar. Zet wifi uit en weer aan en probeer het opnieuw.",
                      "This computer's Wi-Fi is not ready. Turn Wi-Fi off and on and try again.")
            focus = None
        elif soort == "rechten":
            tekst = t("BugOS mocht dit netwerk niet opslaan. Vraag iemand met een beheerdersaccount om hulp.",
                      "BugOS was not allowed to save this network. Ask someone with an administrator account for "
                      "help.")
            focus = None
        elif soort == "opslaan":
            tekst = t("Het netwerk opslaan lukte niet. Probeer het nog eens.",
                      "Saving the network did not work. Try again.")
            focus = None
        else:
            tekst = t("Verbinden lukte niet. Probeer het nog eens.", "Connecting did not work. Try again.")
            focus = None
        self.banner.zet(tekst, "fout")
        if meer:
            self.open_meer(focus)
        self.pas_hoogte()
        if focus is not None and not meer:
            focus.setFocus()

    def reject(self) -> None:  # noqa: D102
        # Een nieuw profiel dat nooit verbond, blijft niet staan; was het nog bezig, dan ook stoppen.
        uuid, bezig, stop = self.nieuw_uuid, self.bezig, self.uuid
        self.gestopt = True
        ouder = self.parent() or self
        if bezig and stop:
            op_achtergrond(ouder, lambda: (bi.stop_profiel(stop), bool(uuid) and bi.vergeet_profiel(uuid)),
                           lambda _u: None)
        elif uuid:
            op_achtergrond(ouder, lambda: bi.vergeet_profiel(uuid), lambda _u: None)
        self.nieuw_uuid = ""
        self.wachtwoord.clear()
        self.klaar.emit(False)
        super().reject()


class OpgeslagenDialoog(QDialog):
    """Opgeslagen netwerken: wat BugOS onthoudt, en per netwerk 'Vergeten' (ook een oud netwerk dat nu niet in de buurt
    is, met een oud wachtwoord)."""

    def __init__(self, ouder: QWidget):
        super().__init__(ouder)
        self.setWindowTitle(t("Opgeslagen netwerken", "Saved networks"))
        self.setMinimumWidth(480)
        self.veranderd = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(label(t("Opgeslagen netwerken", "Saved networks"), "kop2"))
        lay.addWidget(label(t("Vergeet je een netwerk, dan verbindt BugOS er niet meer vanzelf mee. De volgende keer "
                              "vraagt BugOS het wachtwoord opnieuw.",
                              "If you forget a network, BugOS no longer connects to it by itself. Next time BugOS "
                              "asks for the password again."), "klein"))
        self.banner = Banner()
        lay.addWidget(self.banner)
        binnen = QWidget()
        bl = QVBoxLayout(binnen)
        bl.setContentsMargins(0, 0, 0, 0)
        self.groep = Groep()
        self.groep.lay.setContentsMargins(4, 4, 4, 4)
        bl.addWidget(self.groep)
        bl.addStretch(1)
        self.vlak = schuifbaar(binnen)
        self.binnen = binnen
        lay.addWidget(self.vlak, 1)
        lay.addSpacing(4)
        sluit = Knop(t("Sluiten", "Close"), "hoofd")
        sluit.clicked.connect(self.accept)
        sluit.setDefault(True)
        lay.addLayout(knoppenrij(sluit))
        self.rijen: dict[str, Rij] = {}
        self.vul([])
        op_achtergrond(self, bi.opgeslagen_wifi, self.vul)

    def vul(self, lijst) -> None:
        leeg_groep(self.groep)
        self.rijen = {}
        for o in lijst or []:
            knop = Knop(t("Vergeten", "Forget"), "stil")
            knop.setAccessibleName(t("{naam} vergeten", "Forget {naam}").format(naam=o.naam))
            knop.clicked.connect(lambda _c=False, x=o: self.vergeet(x))
            rij = Rij("wifi", o.naam, t("Nu verbonden", "Connected now") if o.actief else "", knop)
            self.rijen[o.naam] = rij
            self.groep.voeg(rij)
        if not self.rijen:
            self.groep.voeg(Rij("wifi", t("Nog geen netwerken opgeslagen", "No saved networks yet") if lijst is not None
                                else t("Even kijken…", "Looking…")))
        self.pas_hoogte()

    def pas_hoogte(self) -> None:
        maxh = max(160, vrije_hoogte(self) - 220)
        self.vlak.setMinimumHeight(min(self.binnen.sizeHint().height(), maxh))
        self.vlak.setMaximumHeight(maxh)
        self.adjustSize()

    def vergeet(self, o) -> None:
        rij = self.rijen.get(o.naam)
        if rij is not None and rij.rechts is not None:
            rij.rechts.setEnabled(False)

        def klaar(ok) -> None:
            if ok:
                self.veranderd = True
                self.banner.zet(t("{naam} is vergeten.", "{naam} is forgotten.").format(naam=o.naam), "goed")
                op_achtergrond(self, bi.opgeslagen_wifi, self.vul)
            else:
                if rij is not None and rij.rechts is not None:
                    rij.rechts.setEnabled(True)
                self.banner.zet(t("Vergeten lukte niet.", "Forgetting did not work."), "fout")

        op_achtergrond(self, lambda: bi.vergeet_opgeslagen(o), klaar)


class WifiPagina(Blad):
    sleutel, icoon = "wifi", "wifi"
    titel_nl, titel_en = "Wifi en internet", "Wi-Fi and internet"
    uitleg_nl = "Klik op een netwerk om te verbinden. BugOS onthoudt het wachtwoord."
    uitleg_en = "Click a network to connect. BugOS remembers the password."
    zoekwoorden = ("wifi wlan internet netwerk draadloos wachtwoord kabel ethernet verbinding wifi wi-fi wlan "
                   "internet network wireless password cable ethernet connection")

    def bouw(self) -> None:
        g = self.kaart()
        self.schakel = schuifje(True, self.zet_wifi)
        self.hoofd = Rij("wifi", t("Wifi", "Wi-Fi"), "", self.schakel)
        g.voeg(self.hoofd)
        # De netwerkkabel: altijd te zien als de computer een netwerkpoort heeft (Help stuurt je hierheen als er geen
        # wifi is). 'Verbinden' alleen als de kabel erin zit maar niet verbonden is.
        self.kabel_knop = Knop(t("Verbinden", "Connect"), "stil")
        self.kabel_knop.clicked.connect(lambda _c=False: self.verbind_kabel())
        self.kabel_knop.hide()
        self.kabel = Rij("computer", t("Kabel", "Cable"), t("Verbonden met een netwerkkabel", "Connected by cable"),
                         self.kabel_knop)
        self.kabel.hide()
        self.kabel_apparaat = ""
        # Opgeslagen netwerken, vlak onder de schakelaar (zoals 'Bekende netwerken beheren' in Windows): daar vergeet je
        # ook een oud netwerk dat nu niet in de buurt is.
        self.opgeslagen = Rij("slot", t("Opgeslagen netwerken", "Saved networks"),
                              t("Netwerken die BugOS onthoudt. Hier kun je ze vergeten.",
                                "Networks BugOS remembers. You can forget them here."), klikbaar=True)
        self.opgeslagen.geklikt.connect(self.open_opgeslagen)
        g.voeg(self.opgeslagen)
        g.voeg(self.kabel)
        self.zoek_knop = Knop(t("Opnieuw zoeken", "Search again"), "stil", "lijn:verversen")
        self.zoek_knop.clicked.connect(lambda _c=False: self.ververs(True))
        self.lay.addWidget(sectie_met_knop(t("Netwerken in de buurt", "Networks nearby"), self.zoek_knop))
        self.lijst = self.kaart()
        # Een netwerk dat zijn naam niet laat zien (een 'verborgen' netwerk) (U109).
        self.ander = Knop(t("Ander netwerk…", "Other network…"), "stil", "lijn:plus")
        self.ander.clicked.connect(lambda _c=False: self.verbind_verborgen())
        # Een verborgen netwerk van school of werk (met gebruikersnaam): hetzelfde venster als eduroam, met een naamveld.
        self.school = Knop(t("Netwerk van school of werk…", "School or work network…"), "stil", "lijn:leren")
        self.school.clicked.connect(lambda _c=False: self.open_zakelijk("", verborgen=True))
        # Een Doorloop: op een half scherm (640 px) komt de tweede knop onder de eerste, in plaats van dat de pagina
        # opzij schuift (B-02).
        onder = Doorloop(8)
        onder.addWidget(self.ander)
        onder.addWidget(self.school)
        self.lay.addLayout(onder)

    def ververs(self, opnieuw: bool = False) -> None:
        self.hoofd.zet_uitleg(t("Even zoeken…", "Searching…"))
        op_achtergrond(self, lambda: (bi.wifi_aan(), bi.netwerken(opnieuw), bi.kabel(), bi.heeft_wifi()), self.toon)

    def toon_kabel(self, kabel) -> None:
        """kabel: (stand, apparaat) uit bi.kabel(), of (oud) True = verbonden, False = niet te zien."""
        if isinstance(kabel, tuple):
            stand, self.kabel_apparaat = kabel
        else:
            stand, self.kabel_apparaat = ("verbonden" if kabel else ""), ""
        teksten = {
            "verbonden": t("Verbonden met een netwerkkabel", "Connected by cable"),
            "bezig": t("Bezig met verbinden…", "Connecting…"),
            "los": t("Niet aangesloten · steek de netwerkkabel in de computer",
                     "Not plugged in · plug the network cable into the computer"),
            "uit": t("De kabel zit erin, maar is niet verbonden", "Cable plugged in, but not connected"),
        }
        self.kabel.setVisible(stand in teksten)
        self.kabel.zet_uitleg(teksten.get(stand, ""))
        self.kabel_knop.setVisible(stand == "uit" and bool(self.kabel_apparaat))

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        aan, netwerken, kabel, wifi = uitkomst
        self.schakel.zet_stil(aan)
        self.toon_kabel(kabel)
        # Zonder wifi in de computer: dat zeggen, en geen schakelaar of lijst die niets doen (U111).
        for w in (self.schakel, self.zoek_knop, self.lijst, self.ander, self.school, self.opgeslagen):
            w.setVisible(wifi)
        if not wifi:
            self.hoofd.zet_uitleg(t("Deze computer heeft geen wifi", "This computer has no Wi-Fi"))
            return
        nu = next((n for n in netwerken if n.verbonden), None)
        self.hoofd.zet_uitleg(t(f"Verbonden met {nu.naam}", f"Connected to {nu.naam}") if nu else
                              (t("Niet verbonden", "Not connected") if aan else t("Uit", "Off")))
        leeg_groep(self.lijst)
        for n in netwerken:
            slot = t(" · met wachtwoord", " · with password") if n.beveiligd else t(" · open netwerk", " · open network")
            if n.verbonden:
                meer = meer_knop(lambda x=n: [("kruis", t("Verbreken", "Disconnect"), lambda: self.verbreek(x)),
                                              ("prullenbak", t("Vergeten", "Forget"), lambda: self.vergeet_wifi(x))])
                self.lijst.voeg(Rij("vink", n.naam, t("Verbonden · ", "Connected · ") + sterkte_woord(n.sterkte) + slot,
                                    meer))
            else:
                rij = Rij("slot" if n.beveiligd else "wifi", n.naam, sterkte_woord(n.sterkte) + slot, klikbaar=True,
                          pijl=False)
                rij.geklikt.connect(lambda x=n: self.verbind(x))
                self.lijst.voeg(rij)
        if not netwerken:
            self.lijst.voeg(Rij("wifi", t("Geen netwerken gevonden", "No networks found") if aan else
                                t("Wifi staat uit", "Wi-Fi is off"),
                                t("Zet wifi aan of zoek opnieuw.", "Turn on Wi-Fi or search again.")))

    def open_opgeslagen(self) -> None:
        d = self.opgeslagen_dialoog = OpgeslagenDialoog(self)
        d.finished.connect(lambda _r: d.veranderd and self.ververs())
        d.open()

    def verbind_kabel(self) -> None:
        apparaat = self.kabel_apparaat
        self.kabel_knop.setEnabled(False)
        self.melding.toon(t("Verbinden via de kabel…", "Connecting by cable…"), seconden=25)

        def klaar(ok) -> None:
            self.kabel_knop.setEnabled(True)
            if ok:
                self.melding.hide()
            else:
                self.melding.toon(t("Verbinden via de kabel lukte niet.", "Connecting by cable did not work."), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.kabel_verbind(apparaat), klaar)

    def zet_wifi(self, aan: bool) -> None:
        op_achtergrond(self, lambda: bi.zet_wifi(aan), lambda _u: QTimer.singleShot(1500, self.ververs))

    def verbind(self, n: bi.Netwerk) -> None:
        if not n.beveiligd:
            self.verbind_met(n, bekend=True)
            return
        # Kennen we dit netwerk al? (nmcli kan even duren: op de achtergrond, het venster blijft reageren.)
        self.melding.toon(t(f"Even kijken bij {n.naam}…", f"Checking {n.naam}…"), seconden=15)
        op_achtergrond(self, lambda: bi.bekend_netwerk(n.naam), lambda bekend: self.verbind_met(n, bekend is True))

    def vraag_wachtwoord(self, n: bi.Netwerk, veranderd: bool = False) -> str:
        """Vraag het wachtwoord van een netwerk ('' = niet ingevuld of geannuleerd). Het gaat daarna via stdin naar
        nmcli, nooit op de opdrachtregel."""
        if veranderd:
            vraag = t("Verbinden met '{naam}' lukte niet. Misschien is het wachtwoord veranderd. Wat is het wachtwoord "
                      "nu?", "Connecting to '{naam}' did not work. Maybe the password changed. What is the password "
                      "now?").format(naam=n.naam)
        else:
            vraag = t("Wat is het wachtwoord van '{naam}'? Het staat vaak op de onderkant van het modem.",
                      "What is the password of '{naam}'? It is often on the bottom of the router.").format(naam=n.naam)
        return vraag_tekst(self, t("Wachtwoord", "Password"), vraag, ok=t("Verbinden", "Connect"), wachtwoord=True) or ""

    def verbind_met(self, n: bi.Netwerk, bekend: bool, wachtwoord: str = "") -> None:
        if getattr(n, "zakelijk", False):
            # School- of werkwifi (eduroam): daar hoort ook een gebruikersnaam bij. BugOS' eigen venster (U495).
            self.verbind_zakelijk(n, bekend)
            return
        if n.beveiligd and not bekend:
            wachtwoord = self.vraag_wachtwoord(n)
            if not wachtwoord:
                return
        # Zo lang als nmcli mag wachten (45-60 s), niet 30 s (U499).
        self.melding.toon(t(f"Verbinden met {n.naam}…", f"Connecting to {n.naam}…"), seconden=65)

        def klaar(uitkomst) -> None:
            gelukt = bool(uitkomst and uitkomst[0])
            if not gelukt and bekend and n.beveiligd and not wachtwoord:
                # Een bekend netwerk dat niet meer wil: vaak is het wachtwoord veranderd. Vraag het nieuwe.
                self.melding.hide()
                nieuw = self.vraag_wachtwoord(n, veranderd=True)
                if nieuw:
                    self.verbind_met(n, True, nieuw)
                    return
            # Een open netwerk heeft geen wachtwoord: dan niet daarnaar vragen (U110).
            mislukt = t("Verbinden lukte niet. Klopt het wachtwoord? Probeer het nog eens.",
                        "Connecting did not work. Is the password right? Try again.") if n.beveiligd else \
                t("Verbinden lukte niet. Ben je dichtbij genoeg? Probeer het nog eens.",
                  "Connecting did not work. Are you close enough? Try again.")
            self.melding.toon(t(f"Verbonden met {n.naam}.", f"Connected to {n.naam}.") if gelukt else mislukt,
                              "goed" if gelukt else "fout")
            self.ververs()

        def probeer():
            voor = bi.wifi_uuids(n.naam) if not bekend else set()
            uitkomst = bi.verbind(n.naam, wachtwoord, bekend)
            if not uitkomst[0] and not bekend and voor is not None and bi.wachtwoord_fout(uitkomst[1] or ""):
                # nmcli laat het nieuwe profiel staan (met het verkeerde wachtwoord): weg ermee, anders vroeg de
                # volgende klik niets en zei hij 'misschien is het wachtwoord veranderd' (U498). Alleen het profiel dat
                # nu nieuw is, en alleen bij een fout wachtwoord (niet buiten bereik of te traag) (U503).
                bi.vergeet_uuids((bi.wifi_uuids(n.naam) or set()) - voor)
            return uitkomst

        op_achtergrond(self, probeer, klaar)

    def verbind_zakelijk(self, n: bi.Netwerk, bekend: bool) -> None:
        """Een netwerk van school of werk: nieuw -> het venster; bekend -> meteen verbinden, en lukt dat niet, dan het
        venster met wat er al bekend is en wat er misging."""
        if not bekend:
            self.open_zakelijk(n.naam)
            return
        self.melding.toon(t("Verbinden met {naam}…", "Connecting to {naam}…").format(naam=n.naam), seconden=65)

        def werk():
            p = bi.zakelijk_profiel(n.naam)
            return (p, bi.verbind_zakelijk(p.uuid, "")) if p is not None else None

        def klaar(uitkomst) -> None:
            if not uitkomst:
                self.melding.hide()
                self.open_zakelijk(n.naam)
                return
            p, (gelukt, soort, reden, server) = uitkomst
            if gelukt:
                self.melding.toon(t("Verbonden met {naam}.", "Connected to {naam}.").format(naam=n.naam), "goed")
                self.ververs()
                return
            self.melding.hide()
            self.open_zakelijk(n.naam, profiel=p, fout=(soort, reden, server))

        op_achtergrond(self, werk, klaar)

    def open_zakelijk(self, naam: str, profiel=None, fout=None, verborgen: bool = False) -> None:
        oud = getattr(self, "zakelijk_dialoog", None)
        if oud is not None and not oud.isVisible():
            oud.deleteLater()
        d = self.zakelijk_dialoog = ZakelijkDialoog(self, naam, profiel, fout, verborgen)

        def klaar(ok: bool) -> None:
            if ok:
                self.melding.toon(t("Verbonden met {naam}.", "Connected to {naam}.").format(naam=d.naam), "goed")
                self.ververs()

        d.klaar.connect(klaar)
        d.open()

    def verbind_verborgen(self) -> None:
        d = QInputDialog(self)
        d.setWindowTitle(t("Ander netwerk", "Other network"))
        d.setLabelText(t("Wat is de naam van het netwerk?", "What is the name of the network?"))
        d.setOkButtonText(t("Verder", "Next"))
        d.setCancelButtonText(t("Annuleren", "Cancel"))
        if not d.exec() or not d.textValue().strip():
            return
        naam = d.textValue().strip()
        w = QInputDialog(self)
        w.setWindowTitle(t("Wachtwoord", "Password"))
        w.setLabelText(t(f"Wat is het wachtwoord van '{naam}'?\n(Geen wachtwoord? Laat het leeg.)",
                         f"What is the password of '{naam}'?\n(No password? Leave it empty.)"))
        w.setTextEchoMode(QLineEdit.EchoMode.Password)
        w.setOkButtonText(t("Verbinden", "Connect"))
        w.setCancelButtonText(t("Annuleren", "Cancel"))
        if not w.exec():
            return
        wachtwoord = w.textValue()
        self.melding.toon(t(f"Verbinden met {naam}…", f"Connecting to {naam}…"), seconden=50)   # (U518)

        def klaar(uitkomst) -> None:
            gelukt = bool(uitkomst and uitkomst[0])
            self.melding.toon(t(f"Verbonden met {naam}.", f"Connected to {naam}.") if gelukt else
                              t("Verbinden lukte niet. Klopt de naam (let op hoofdletters) en het wachtwoord?",
                                "Connecting did not work. Are the name (mind capitals) and password right?"),
                              "goed" if gelukt else "fout")
            self.ververs()

        def probeer():
            # Net als bij een zichtbaar netwerk: een verkeerd wachtwoord blijft niet bewaard (U498, U503, U518).
            voor = bi.wifi_uuids(naam)
            uitkomst = bi.verbind(naam, wachtwoord, verborgen=True)
            if not uitkomst[0] and voor is not None and bi.wachtwoord_fout(uitkomst[1] or ""):
                bi.vergeet_uuids((bi.wifi_uuids(naam) or set()) - voor)
            return uitkomst

        op_achtergrond(self, probeer, klaar)

    def verbreek(self, n: bi.Netwerk) -> None:
        def klaar(ok) -> None:
            if not ok:   # niet stil laten mislukken (U497)
                self.melding.toon(t("Verbreken lukte niet.", "Disconnecting did not work."), "fout")
            self.ververs()
        op_achtergrond(self, lambda: bi.verbreek(n.naam), klaar)

    def vergeet_wifi(self, n: bi.Netwerk) -> None:
        """Vergeten: verbreken en het wachtwoord weggooien (U338)."""
        def klaar(ok) -> None:
            if not ok:   # niet stil laten mislukken (bijv. geen beheerder) (U345)
                self.melding.toon(t("Vergeten lukte niet.", "Forgetting did not work."), "fout")
            self.ververs()
        op_achtergrond(self, lambda: bi.vergeet_netwerk(n.naam), klaar)




# ============================================================= bluetooth ===

# Wat voor apparaat (bi.bt_soort) -> het lijn-icoon en de woorden eronder.
BT_ICOON = {"geluid": "geluid", "muis": "muis", "toetsenbord": "toetsenbord", "spel": "spel", "tablet": "potlood",
            "telefoon": "telefoon", "computer": "computer", "printer": "printer", "camera": "foto",
            "apparaat": "bluetooth"}


def bt_woord(soort: str) -> str:
    return {
        "geluid": t("Koptelefoon of speaker", "Headphones or speaker"), "muis": t("Muis", "Mouse"),
        "toetsenbord": t("Toetsenbord", "Keyboard"), "telefoon": t("Telefoon", "Phone"),
        "spel": t("Spelcontroller", "Game controller"), "computer": t("Computer", "Computer"),
        "tablet": t("Tablet of pen", "Tablet or pen"), "printer": t("Printer", "Printer"),
        "camera": t("Camera", "Camera"),
    }.get(soort, t("Apparaat", "Device"))


def apparaat_icoon(soort: str) -> str:
    """Het icoon voor een apparaat (soort = het icoon van BlueZ): een muis is een muis, niet het bluetooth-teken."""
    return BT_ICOON.get(bi.bt_soort(soort), "bluetooth")


AGENT_PAD = "/org/bugos/BluetoothAgent"
_AGENT = None

if QDBusConnection is not None:
    @ClassInfo({"D-Bus Interface": "org.bluez.Agent1"})
    class BluetoothAgent(QObject):
        """Ons eigen BlueZ-'agent': BlueZ vraagt hem de codes bij het koppelen dat WIJ starten (Device1.Pair vanaf
        dezelfde D-Bus-verbinding). Alleen root (bluetoothd) mag hem aanroepen. We nemen niet de standaard-agent van
        KDE over: koppelen dat een telefoon zelf start, blijft via KDE gaan (zie de spec, deel 6).

        Zonder waarde antwoorden (bevestigen, toestaan): later, met msg.setDelayedReply + createReply.
        Met een waarde (pincode, code): synchroon, met een eigen wachtlus tot de gebruiker antwoordt. Nooit
        QDBusContext gebruiken (dat liet het proces vallen in de VM) en nooit createReply([waarde]) (verkeerd type)."""

        def __init__(self):
            super().__init__()
            self.koppelaar = None    # de koppelaar van het open venster (met .pad en het signaal .vraag)
            self.stuur = None        # in tests: een lijst.append; anders de systeembus
            self.wacht = None        # een vraag (QDBusMessage) die op ja/nee wacht
            self.lus: QEventLoop | None = None
            self.waarde = None

        def verstuur(self, m) -> None:
            (self.stuur or QDBusConnection.systemBus().send)(m)

        def van_ons(self, dev) -> bool:
            k = self.koppelaar
            return k is not None and bool(getattr(k, "pad", "")) and dev.path() == k.pad

        def later(self, msg, ja: bool) -> None:
            msg.setDelayedReply(True)
            self.verstuur(msg.createReply() if ja else msg.createErrorReply("org.bluez.Error.Rejected", "Rejected"))

        @Slot(QDBusObjectPath, "uint", QDBusMessage)
        def RequestConfirmation(self, dev, passkey, msg):  # noqa: N802
            if not self.van_ons(dev):
                self.later(msg, False)
                return
            self.annuleer()
            msg.setDelayedReply(True)
            self.wacht = msg
            self.koppelaar.vraag.emit("vergelijk", dev.path(), int(passkey))

        @Slot(QDBusObjectPath, QDBusMessage)
        def RequestAuthorization(self, dev, msg):  # noqa: N802
            self.later(msg, self.van_ons(dev))

        @Slot(QDBusObjectPath, str, QDBusMessage)
        def AuthorizeService(self, dev, uuid, msg):  # noqa: N802, ARG002
            self.later(msg, self.van_ons(dev))

        @Slot(QDBusObjectPath, result=str)
        def RequestPinCode(self, dev):  # noqa: N802
            if not self.van_ons(dev):
                return ""
            self.koppelaar.vraag.emit("pin", dev.path(), None)
            w = self.wacht_op_antwoord()
            return str(w) if w is not None else ""

        @Slot(QDBusObjectPath, result="uint")
        def RequestPasskey(self, dev):  # noqa: N802
            if not self.van_ons(dev):
                return 0
            self.koppelaar.vraag.emit("passkey", dev.path(), None)
            w = self.wacht_op_antwoord()
            try:
                return max(0, min(999999, int(w))) if w is not None else 0
            except (TypeError, ValueError):
                return 0

        @Slot(QDBusObjectPath, "uint", "ushort")
        def DisplayPasskey(self, dev, passkey, getypt):  # noqa: N802
            if self.van_ons(dev):
                self.koppelaar.vraag.emit("typ", dev.path(), (int(passkey), int(getypt)))

        @Slot(QDBusObjectPath, str)
        def DisplayPinCode(self, dev, pin):  # noqa: N802
            if self.van_ons(dev):
                self.koppelaar.vraag.emit("typ", dev.path(), (str(pin), -1))

        @Slot()
        def Cancel(self):  # noqa: N802
            """BlueZ geeft het op (te laat, of het apparaat stopte): de vraag in het venster weg."""
            had = self.wacht is not None or self.lus is not None
            self.wacht = None   # BlueZ wacht er niet meer op
            self.stop_lus()
            if had and self.koppelaar is not None:
                self.koppelaar.vraag.emit("stop", getattr(self.koppelaar, "pad", ""), None)

        @Slot()
        def Release(self):  # noqa: N802
            self.annuleer()

        # ---- de kant van BugOS
        def antwoord(self, ja: bool, waarde=None) -> None:
            if self.wacht is not None:
                msg, self.wacht = self.wacht, None
                self.verstuur(msg.createReply() if ja else msg.createErrorReply("org.bluez.Error.Rejected", "No"))
            if self.lus is not None:
                self.waarde = waarde if ja else None
                self.lus.quit()

        def geef(self, waarde) -> None:
            self.antwoord(True, waarde)

        def annuleer(self) -> None:
            if self.wacht is not None:
                msg, self.wacht = self.wacht, None
                self.verstuur(msg.createErrorReply("org.bluez.Error.Canceled", "Canceled"))
            self.stop_lus()

        def stop_lus(self) -> None:
            if self.lus is not None:
                self.waarde = None
                self.lus.quit()

        def wacht_op_antwoord(self, ms: int = 55000):
            self.stop_lus()
            lus = self.lus = QEventLoop()
            self.waarde = None
            QTimer.singleShot(ms, lus.quit)
            lus.exec()
            if self.lus is lus:
                self.lus = None
            return self.waarde
else:  # pragma: no cover
    BluetoothAgent = None


def bluetooth_agent():
    """Eén agent per programma (een tweede registerObject op hetzelfde pad lukt niet)."""
    global _AGENT
    if _AGENT is None and BluetoothAgent is not None:
        bus = QDBusConnection.systemBus()
        if not bus.isConnected():
            return None
        a = BluetoothAgent()
        if not bus.registerObject(AGENT_PAD, a, QDBusConnection.RegisterOption.ExportAllSlots):
            return None
        _AGENT = a
    return _AGENT


class BluezKoppelaar(QObject):
    """Zoeken en koppelen met BlueZ (D-Bus). Dezelfde vorm als NepKoppelaar, zodat het venster niet weet welke het is."""

    gevonden = Signal(object)          # bi.BtStand (elke 2 s)
    vraag = Signal(str, str, object)   # (soort: vergelijk | typ | pin | passkey | stop, pad, waarde)
    gekoppeld = Signal(str, str)       # (pad, D-Bus-foutnaam); "" = gelukt
    probleem = Signal(str)             # een D-Bus-fout bij het zoeken (bluetooth uit, weg)

    def __init__(self, ouder: QObject | None = None):
        super().__init__(ouder)
        self.pad = ""
        self.adapter = ""
        self.wil_zoeken = False
        self.zoekt = False
        self.peilt = False
        self.gesloten = False
        self.agent = None
        self.wachters: list = []
        self.klok = QTimer(self)
        self.klok.setInterval(2000)
        self.klok.timeout.connect(self.peil)

    def roep(self, pad: str, iface: str, methode: str, args=(), ms: int = 5000, klaar=None) -> None:
        """Een D-Bus-aanroep naar BlueZ zonder te wachten; klaar(foutnaam) ('' = gelukt)."""
        if QDBusConnection is None:
            if klaar is not None:
                klaar("org.freedesktop.DBus.Error.ServiceUnknown")
            return
        msg = QDBusMessage.createMethodCall("org.bluez", pad, iface, methode)
        if args:
            msg.setArguments(list(args))
        w = QDBusPendingCallWatcher(QDBusConnection.systemBus().asyncCall(msg, ms), self)
        self.wachters.append(w)

        def af(w_) -> None:
            fout = w_.error().name() if w_.isError() else ""
            if w_ in self.wachters:
                self.wachters.remove(w_)
            w_.deleteLater()
            if klaar is not None and not self.gesloten:
                klaar(fout)

        w.finished.connect(af)

    def start(self) -> None:
        self.agent = bluetooth_agent()
        if self.agent is None:
            self.probleem.emit("org.freedesktop.DBus.Error.ServiceUnknown")
            return
        self.agent.koppelaar = self
        # Alleen voor ons eigen koppelen; niet RequestDefaultAgent (KDE blijft de standaard voor een telefoon die zelf
        # begint). 'AlreadyExists' = al geregistreerd: goed.
        self.roep("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent",
                  [QDBusObjectPath(AGENT_PAD), "KeyboardDisplay"],
                  klaar=lambda f: f and f != "org.bluez.Error.AlreadyExists" and self.probleem.emit(f))
        self.wil_zoeken = True
        self.peil()
        self.klok.start()

    def peil(self) -> None:
        if self.peilt or self.gesloten:
            return
        self.peilt = True
        op_achtergrond(self, bi.bt_objecten, self.gepeild)

    def gepeild(self, stand) -> None:
        self.peilt = False
        if self.gesloten or stand is None:
            return
        if stand.adapter != self.adapter or not stand.aan:
            self.adapter, self.zoekt = stand.adapter, False   # een andere (of geen) kaart, of uitgezet
        if self.adapter and stand.aan and self.wil_zoeken and not self.zoekt:
            self.zoek_aan()
        self.gevonden.emit(stand)

    def zoek_aan(self) -> None:
        self.zoekt = True

        def klaar(fout: str) -> None:
            if fout in ("", "org.bluez.Error.InProgress"):   # InProgress: iemand anders zoekt al, ook goed
                return
            self.zoekt = False
            self.probleem.emit(fout)

        self.roep(self.adapter, "org.bluez.Adapter1", "StartDiscovery", klaar=klaar)

    def zoek(self, aan: bool) -> None:
        """Zoeken zolang de lijst open is (zoals Windows): BlueZ ruimt anders apparaten op die je nog wilt kiezen."""
        self.wil_zoeken = aan
        if aan and self.adapter and not self.zoekt:
            self.zoek_aan()
        elif not aan and self.zoekt and self.adapter:
            self.zoekt = False
            self.roep(self.adapter, "org.bluez.Adapter1", "StopDiscovery")

    def koppel(self, pad: str) -> None:
        self.pad = pad
        self.zoek(False)   # niet zoeken tijdens het koppelen (dat maakt koppelen onbetrouwbaar)

        def vertrouwd(_ok) -> None:
            if self.gesloten or self.pad != pad:
                return
            self.roep(pad, "org.bluez.Device1", "Pair", ms=90000, klaar=lambda f: self.na_koppelen(pad, f))

        # Eerst vertrouwen: een koptelefoon zet meteen na het koppelen zijn geluid aan, en dan vroeg BlueZ anders KDE's
        # agent om toestemming (een KDE-melding midden in ons koppelen) (N8).
        op_achtergrond(self, lambda: bi.bt_vertrouw(pad, True), vertrouwd)

    def na_koppelen(self, pad: str, fout: str) -> None:
        if fout and fout != "org.bluez.Error.AlreadyExists":
            op_achtergrond(self, lambda: bi.bt_vertrouw(pad, False), lambda _u: None)   # weer niet vertrouwd
        self.gekoppeld.emit(pad, fout)

    def antwoord(self, ja: bool, waarde=None) -> None:
        if self.agent is not None:
            self.agent.antwoord(ja, waarde)

    def stop_koppelen(self) -> None:
        if self.pad:
            self.roep(self.pad, "org.bluez.Device1", "CancelPairing")
        if self.agent is not None:
            self.agent.annuleer()

    def sluit(self) -> None:
        if self.gesloten:
            return
        self.klok.stop()
        if self.agent is not None:
            self.agent.annuleer()
            if self.agent.koppelaar is self:
                self.agent.koppelaar = None
        if self.zoekt and self.adapter:
            self.roep(self.adapter, "org.bluez.Adapter1", "StopDiscovery")
        if self.agent is not None:
            self.roep("/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent", [QDBusObjectPath(AGENT_PAD)])
        self.gesloten = True
        self.zoekt = False


class NepKoppelaar(QObject):
    """De voorbeeldstand (foto's en tests): vindt na een tijdje vier apparaten; een telefoon vraagt of de code klopt,
    een toetsenbord laat een code typen, oortjes en een controller koppelen zo."""

    gevonden = Signal(object)
    vraag = Signal(str, str, object)
    gekoppeld = Signal(str, str)
    probleem = Signal(str)

    def __init__(self, ouder: QObject | None = None):
        super().__init__(ouder)
        self.pad = ""
        self.wacht_soort = ""
        self.pin_voor = ""        # foto's/tests: dit apparaat vraagt een pincode
        self.gesloten = False
        self.klokken: list[QTimer] = []
        self.getoond = 0

    def na(self, ms: int, f) -> None:
        k = QTimer(self)
        k.setSingleShot(True)
        k.timeout.connect(f)
        k.start(ms)
        self.klokken.append(k)

    def stop_klokken(self) -> None:
        for k in self.klokken:
            k.stop()
        self.klokken = []

    def toon(self, n: int) -> None:
        if self.gesloten:
            return
        self.getoond = max(self.getoond, n)
        stand = bi.bt_objecten()
        zichtbaar = {g.adres for g in bi.VB_BT_GEVONDEN[:self.getoond]} | {bi.VB_BT_GEVONDEN[-1].adres}
        stand.apparaten = [g for g in stand.apparaten if g.adres in zichtbaar]
        self.gevonden.emit(stand)

    def start(self) -> None:
        for ms, n in ((300, 1), (900, 3), (1500, 4)):
            self.na(ms, lambda n=n: self.toon(n))

    def zoek(self, aan: bool) -> None:
        if aan and self.getoond:
            self.na(50, lambda: self.toon(self.getoond))

    def koppel(self, pad: str) -> None:
        self.pad = pad
        g = next((x for x in bi.VB_BT_GEVONDEN if x.pad == pad), None)
        soort = bi.bt_soort(g.soort) if g is not None else ""
        if g is not None and g.naam == self.pin_voor:
            self.wacht_soort = "pin"
            self.na(400, lambda: self.vraag.emit("pin", pad, None))
        elif soort == "telefoon":
            self.wacht_soort = "vergelijk"
            self.na(400, lambda: self.vraag.emit("vergelijk", pad, 284913))
        elif soort == "toetsenbord":
            self.wacht_soort = ""
            self.na(300, lambda: self.vraag.emit("typ", pad, (503172, 0)))
            for i, n in enumerate((2, 4, 6)):
                self.na(700 + 400 * i, lambda n=n: self.vraag.emit("typ", pad, (503172, n)))
            self.na(2100, lambda: self.gekoppeld.emit(pad, ""))
        else:
            self.na(800, lambda: self.gekoppeld.emit(pad, ""))

    def antwoord(self, ja: bool, waarde=None) -> None:  # noqa: ARG002
        if not self.wacht_soort:
            return
        self.wacht_soort = ""
        pad = self.pad
        self.na(300, lambda: self.gekoppeld.emit(pad, "" if ja else "org.bluez.Error.AuthenticationFailed"))

    def stop_koppelen(self) -> None:
        pad, self.wacht_soort = self.pad, ""
        self.stop_klokken()
        self.na(100, lambda: self.gekoppeld.emit(pad, "org.bluez.Error.AuthenticationCanceled"))

    def sluit(self) -> None:
        self.gesloten = True
        self.stop_klokken()


class KoppelDialoog(QDialog):
    """Apparaat toevoegen: zoeken, kiezen, koppelen (met de code als het apparaat dat vraagt), vertrouwen en verbinden.
    Opent met open(); zegt het met klaar(tekst, soort) voor de melding op de pagina."""

    klaar = Signal(str, str)

    def __init__(self, ouder: QWidget, koppelaar):
        super().__init__(ouder)
        self.koppelaar = koppelaar
        koppelaar.setParent(self)
        self.staat = "lijst"
        self.pad = self.naam = self.adres = self.soort = ""
        self.door_mij_gestopt = False
        self.nee_gezegd = False
        self.gekozen = None
        self.fout_soort = ""
        self.rijen: dict[str, Rij] = {}
        self.inhoud_sleutel: tuple = ()
        self.gesloten = False
        self.setWindowTitle(t("Apparaat toevoegen", "Add a device"))
        breed = min(520, max(360, schermmaat((99999, 0), scherm=ouder.screen())[0][0] - 40))
        self.setMinimumWidth(breed)
        # Een venster mag de vrije hoogte gebruiken: anders zag je bij 150 % maar anderhalf apparaat (N10).
        self.resize(breed, max(300, min(500, vrije_hoogte(ouder))))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        self.kop = label(t("Apparaat toevoegen", "Add a device"), "kop2")
        lay.addWidget(self.kop)
        self.stapel = QStackedWidget()
        lay.addWidget(self.stapel, 1)

        # ---- de lijst
        lijst = QWidget()
        ll = QVBoxLayout(lijst)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(10)
        ll.addWidget(label(t("Zet je apparaat in koppelstand.", "Put your device in pairing mode."), "klein"))
        self.zoek_banner = Banner(t("Apparaten zoeken…", "Looking for devices…"), "bezig")
        ll.addWidget(self.zoek_banner)
        binnen = QWidget()
        bl = QVBoxLayout(binnen)
        bl.setContentsMargins(0, 0, 0, 0)
        self.groep = Groep()
        self.groep.lay.setContentsMargins(4, 4, 4, 4)
        self.groep.hide()
        bl.addWidget(self.groep)
        bl.addStretch(1)
        ll.addWidget(schuifbaar(binnen), 1)
        self.stapel.addWidget(lijst)

        # ---- koppelen
        kp = QWidget()
        kl = QVBoxLayout(kp)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(10)
        kl.addStretch(1)   # alles in het midden, niet bovenin met een leeg vlak eronder
        self.banner = Banner()
        kl.addWidget(self.banner)
        self.vraag_label = label("", "sub")
        kl.addWidget(self.vraag_label)
        self.code = label("", "titel", wrap=False)
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        kl.addWidget(self.code)
        self.code_onder = label("", "klein")
        self.code_onder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kl.addWidget(self.code_onder)
        self.invoer = QLineEdit()
        self.invoer.setMinimumHeight(36)
        self.invoer.textChanged.connect(lambda _t: self.werk_knoppen_bij())
        kl.addWidget(self.invoer)
        self.invoer_uitleg = label("", "klein")
        kl.addWidget(self.invoer_uitleg)
        kl.addStretch(1)
        self.stapel.addWidget(kp)

        # ---- knoppen (welke je ziet, hangt van de stand af)
        lay.addSpacing(4)
        self.weg_knop = Knop(t("Annuleren", "Cancel"), "stil")
        self.weg_knop.clicked.connect(self.annuleer)
        self.nee_knop = Knop("", "stil")
        self.nee_knop.clicked.connect(self.nee)
        self.ja_knop = Knop("", "hoofd")
        self.ja_knop.clicked.connect(self.ja)
        lay.addLayout(knoppenrij(self.weg_knop, self.nee_knop, self.ja_knop))

        koppelaar.gevonden.connect(self.bij_gevonden)
        koppelaar.vraag.connect(self.bij_vraag)
        koppelaar.gekoppeld.connect(self.bij_gekoppeld)
        koppelaar.probleem.connect(self.bij_probleem)
        self.niets = QTimer(self)
        self.niets.setSingleShot(True)
        self.niets.timeout.connect(self.toon_lijst_inhoud)
        self.laatste = None
        self.toon_lijst(zoeken=False)
        koppelaar.start()

    # ---------------------------------------------------------------- standen
    def knoppen(self, weg: bool = False, nee: str = "", ja: str = "") -> None:
        self.weg_knop.setVisible(weg)
        self.nee_knop.setText(nee)
        self.nee_knop.setVisible(bool(nee))
        self.ja_knop.setText(ja)
        self.ja_knop.setVisible(bool(ja))
        self.ja_knop.setDefault(bool(ja) and self.staat in ("pin", "passkey"))
        self.werk_knoppen_bij()

    def werk_knoppen_bij(self) -> None:
        if self.staat in ("pin", "passkey"):
            self.ja_knop.setEnabled(bool(self.invoer.text().strip()))
        else:
            self.ja_knop.setEnabled(True)

    def toon_lijst(self, zoeken: bool = True) -> None:
        self.staat = "lijst"
        self.pad = ""
        self.kop.setText(t("Apparaat toevoegen", "Add a device"))
        self.setWindowTitle(self.kop.text())
        self.stapel.setCurrentIndex(0)
        self.knoppen(weg=True)
        if zoeken:
            self.koppelaar.zoek(True)
        self.niets.start(15000)
        self.toon_lijst_inhoud()

    def koppel_blad(self, kop: str) -> None:
        self.stapel.setCurrentIndex(1)
        self.kop.setText(kop)
        self.setWindowTitle(kop)
        for w in (self.vraag_label, self.code, self.code_onder, self.invoer, self.invoer_uitleg):
            w.hide()

    def toon_bezig(self, tekst: str = "") -> None:
        self.staat = "bezig"
        self.koppel_blad(t("Koppelen met {naam}", "Pairing with {naam}").format(naam=self.naam))
        self.banner.zet(tekst or t("Even geduld… Kies op het apparaat 'Koppelen' als het dat vraagt.",
                                   "One moment… Choose 'Pair' on the device if it asks."), "bezig")
        self.knoppen(weg=True)

    # ---------------------------------------------------------------- de lijst
    def bij_gevonden(self, stand) -> None:
        if self.gesloten:
            return
        self.laatste = stand
        if self.staat == "lijst":
            self.toon_lijst_inhoud()

    def toon_lijst_inhoud(self) -> None:
        if self.staat != "lijst":
            return
        stand = self.laatste
        if stand is not None and not stand.adapter:
            self.zoek_banner.zet(t("Bluetooth doet het nu niet. Zet Bluetooth uit en weer aan.",
                                   "Bluetooth is not working right now. Turn Bluetooth off and on."), "fout")
        elif stand is not None and not stand.aan:
            self.zoek_banner.zet(t("Bluetooth staat uit. Zet Bluetooth aan en probeer het opnieuw.",
                                   "Bluetooth is off. Turn Bluetooth on and try again."), "fout")
        elif self.zoek_banner.tekst.text() != t("Apparaten zoeken…", "Looking for devices…"):
            self.zoek_banner.zet(t("Apparaten zoeken…", "Looking for devices…"), "bezig")
        nieuw = bi.bt_nieuw(stand) if stand is not None and stand.aan else []
        lang_genoeg = not self.niets.isActive()
        sleutel = tuple((g.pad, g.naam, g.soort) for g in nieuw) + ((("niets",),) if lang_genoeg and not nieuw else ())
        if sleutel == self.inhoud_sleutel:
            return
        self.inhoud_sleutel = sleutel
        leeg_groep(self.groep)
        self.rijen = {}
        for g in nieuw:
            soort = bi.bt_soort(g.soort)
            rij = Rij(BT_ICOON.get(soort, "bluetooth"), g.naam, bt_woord(soort), klikbaar=True, pijl=False)
            rij.geklikt.connect(lambda x=g: self.koppel(x))
            self.rijen[g.naam] = rij
            self.groep.voeg(rij)
        if not nieuw and lang_genoeg:
            self.groep.voeg(Rij("bluetooth", t("Nog niets gevonden", "Nothing found yet"),
                                t("Staat het apparaat aan, dichtbij en in koppelstand? Vaak houd je de aan-knop of de "
                                  "bluetooth-knop een paar seconden ingedrukt. Op een telefoon open je de "
                                  "bluetooth-instellingen.",
                                  "Is the device on, nearby and in pairing mode? Often you hold its power or Bluetooth "
                                  "button for a few seconds. On a phone, open its Bluetooth settings.")))
        self.groep.setVisible(bool(nieuw) or lang_genoeg)

    def bij_probleem(self, fout: str) -> None:
        if self.gesloten:
            return
        soort = bi.bt_koppel_fout(fout)
        if self.staat == "lijst" and soort in ("uit", "geen"):
            self.zoek_banner.zet(t("Bluetooth staat uit. Zet Bluetooth aan en probeer het opnieuw.",
                                   "Bluetooth is off. Turn Bluetooth on and try again.") if soort == "uit" else
                                 t("Bluetooth doet het nu niet. Zet Bluetooth uit en weer aan.",
                                   "Bluetooth is not working right now. Turn Bluetooth off and on."), "fout")

    # ---------------------------------------------------------------- koppelen
    def koppel(self, g) -> None:
        if self.staat not in ("lijst", "fout"):
            return
        self.gekozen = g
        self.pad, self.naam, self.adres, self.soort = g.pad, g.naam, g.adres, bi.bt_soort(g.soort)
        self.door_mij_gestopt = self.nee_gezegd = False
        self.niets.stop()
        self.toon_bezig()
        self.koppelaar.koppel(g.pad)

    def bij_vraag(self, soort: str, pad: str, waarde) -> None:
        if self.gesloten or pad != self.pad or self.staat in ("lijst", "fout", "klaar"):
            return
        if soort == "stop":
            self.toon_bezig()
            return
        self.koppel_blad(t("Koppelen met {naam}", "Pairing with {naam}").format(naam=self.naam))
        self.banner.zet("")
        if soort == "vergelijk":
            self.staat = "vergelijk"
            self.vraag_label.setText(t("Zie je deze code ook op {naam}?", "Do you see this code on {naam} too?")
                                     .format(naam=self.naam))
            self.zet_code(int(waarde))
            self.code_onder.setText(t("Kies dan op beide apparaten 'Koppelen'.", "Then choose 'Pair' on both devices."))
            self.code_onder.show()
            self.knoppen(nee=t("Nee, ze zijn anders", "No, they're different"), ja=t("Ja, koppelen", "Yes, pair"))
        elif soort == "typ":
            self.staat = "typ"
            code, getypt = waarde if isinstance(waarde, tuple) else (waarde, 0)
            self.vraag_label.setText(t("Typ deze code op {naam} en druk op Enter:",
                                       "Type this code on {naam} and press Enter:").format(naam=self.naam))
            self.zet_code(code)
            if isinstance(code, int) and getypt > 0:
                self.code_onder.setText(t("{n} van de 6 cijfers getypt", "{n} of 6 digits typed").format(n=getypt))
                self.code_onder.show()
            self.knoppen(weg=True)
        elif soort in ("pin", "passkey"):
            self.staat = soort
            self.vraag_label.setText((t("Typ de pincode van {naam}", "Type the PIN of {naam}") if soort == "pin" else
                                      t("Typ de code die {naam} laat zien", "Type the code {naam} shows"))
                                     .format(naam=self.naam))
            self.vraag_label.show()
            self.invoer.setValidator(None if soort == "pin" else QIntValidator(0, 999999, self.invoer))
            self.invoer.setMaxLength(16 if soort == "pin" else 6)
            self.invoer.setText("0000" if soort == "pin" else "")
            self.invoer.setAccessibleName(self.vraag_label.text())
            self.invoer.show()
            self.invoer.selectAll()
            self.invoer.setFocus()
            if soort == "pin":
                self.invoer_uitleg.setText(t("Staat vaak in de handleiding. Meestal is het 0000 of 1234.",
                                             "Often in the manual. Usually it is 0000 or 1234."))
                self.invoer_uitleg.show()
            self.knoppen(weg=True, ja=t("Koppelen", "Pair"))

    def zet_code(self, code) -> None:
        tekst = bi.code_tekst(code)
        self.code.setText(tekst)
        # De schermlezer leest de cijfers één voor één.
        self.code.setAccessibleName(" ".join(c for c in tekst if not c.isspace()))
        self.vraag_label.show()
        self.code.show()

    def ja(self) -> None:
        if self.staat == "vergelijk":
            self.koppelaar.antwoord(True)
            self.toon_bezig()
        elif self.staat in ("pin", "passkey"):
            w = self.invoer.text().strip()
            if not w:
                return
            self.koppelaar.antwoord(True, w if self.staat == "pin" else int(w))
            self.toon_bezig()
        elif self.staat == "fout" and self.fout_soort == "weg":
            self.toon_lijst()
        elif self.staat == "fout" and self.gekozen is not None:
            self.koppel(self.gekozen)   # opnieuw proberen

    def nee(self) -> None:
        if self.staat == "vergelijk":
            self.nee_gezegd = True
            self.koppelaar.antwoord(False)
            self.toon_bezig()
        elif self.staat == "fout":
            self.toon_lijst()

    def annuleer(self) -> None:
        if self.staat == "lijst":
            self.reject()
            return
        # Tijdens het koppelen: stoppen en terug naar de lijst (de uitslag van BlueZ telt dan niet meer).
        self.door_mij_gestopt = True
        if self.staat in ("pin", "passkey"):
            self.koppelaar.antwoord(False)
        self.koppelaar.stop_koppelen()
        self.toon_lijst()

    def bij_gekoppeld(self, pad: str, fout: str) -> None:
        if self.gesloten or pad != self.pad or self.staat in ("lijst", "klaar"):
            return
        soort = bi.bt_koppel_fout(fout, apparaat=True) if fout else ""
        if soort in ("", "al"):
            self.staat = "klaar"
            self.toon_bezig(t("Verbinden met {naam}…", "Connecting to {naam}…").format(naam=self.naam))
            self.staat = "klaar"
            self.knoppen()
            pad_, adres = self.pad, self.adres
            op_achtergrond(self, lambda: bi.bt_vertrouw_en_verbind(pad_, adres), self.verbonden)
            return
        if self.nee_gezegd and soort in ("geweigerd", "gestopt", "anders"):
            soort = "codes"   # 'Nee, ze zijn anders' eindigt bij BlueZ als geweigerd
        self.toon_fout(soort)

    def verbonden(self, uitkomst) -> None:
        if self.gesloten:
            return
        _vertrouwd, verbonden = uitkomst or (False, False)
        if verbonden:
            tekst, soort = t("{naam} is gekoppeld en verbonden.", "{naam} is paired and connected."), "goed"
        elif self.soort in ("telefoon", "computer", "tablet"):
            # Een telefoon of computer heeft meestal niets om mee te 'verbinden': gekoppeld is dan klaar (N14).
            tekst, soort = t("{naam} is gekoppeld.", "{naam} is paired."), "goed"
        else:
            tekst, soort = t("{naam} is gekoppeld. Verbinden lukte nog niet: klik erop in de lijst.",
                             "{naam} is paired. Connecting did not work yet: click it in the list."), "let_op"
        self.klaar.emit(tekst.format(naam=self.naam), soort)
        self.accept()

    def toon_fout(self, soort: str) -> None:
        self.staat = "fout"
        self.fout_soort = soort
        self.koppel_blad(t("Koppelen met {naam}", "Pairing with {naam}").format(naam=self.naam))
        teksten = {
            "codes": t("De codes kwamen niet overeen, of {naam} weigerde. Probeer het nog eens.",
                       "The codes did not match, or {naam} refused. Try again."),
            "gestopt": t("Het koppelen is gestopt.", "Pairing was stopped."),
            "geweigerd": t("{naam} wilde niet koppelen. Kies op het apparaat 'Koppelen' of 'Toestaan'.",
                           "{naam} did not want to pair. Choose 'Pair' or 'Allow' on the device."),
            "traag": t("Het duurde te lang. Zet {naam} opnieuw in koppelstand en probeer het nog eens.",
                       "It took too long. Put {naam} in pairing mode again and try again."),
            "bereik": t("{naam} antwoordt niet. Staat het aan, dichtbij en in koppelstand?",
                        "{naam} does not answer. Is it on, nearby and in pairing mode?"),
            "bezig": t("BugOS is al met {naam} bezig. Wacht even en probeer het opnieuw.",
                       "BugOS is already busy with {naam}. Wait a moment and try again."),
            "uit": t("Bluetooth staat uit. Zet Bluetooth aan en probeer het opnieuw.",
                     "Bluetooth is off. Turn Bluetooth on and try again."),
            "geen": t("Bluetooth doet het nu niet. Zet Bluetooth uit en weer aan.",
                      "Bluetooth is not working right now. Turn Bluetooth off and on."),
            "weg": t("{naam} is niet meer te vinden. Ga terug naar de lijst; zet het apparaat zo nodig opnieuw in "
                     "koppelstand.",
                     "{naam} cannot be found any more. Go back to the list; put the device in pairing mode again if "
                     "needed."),
        }
        self.banner.zet(teksten.get(soort, t("Koppelen lukte niet. Probeer het nog eens.", "Pairing did not work. "
                                             "Try again.")).format(naam=self.naam), "fout")
        if soort == "weg":   # dat apparaat is er niet meer: alleen terug naar de lijst
            self.knoppen(ja=t("Terug naar de lijst", "Back to the list"))
        else:
            self.knoppen(nee=t("Terug naar de lijst", "Back to the list"), ja=t("Opnieuw proberen", "Try again"))

    # ---------------------------------------------------------------- sluiten
    def done(self, r: int) -> None:  # noqa: D102
        if not self.gesloten:
            self.gesloten = True
            self.niets.stop()
            if self.staat in ("bezig", "vergelijk", "typ", "pin", "passkey"):
                self.koppelaar.stop_koppelen()
            self.koppelaar.sluit()
        super().done(r)


class BluetoothPagina(Blad):
    sleutel, icoon = "bluetooth", "bluetooth"
    titel_nl, titel_en = "Bluetooth", "Bluetooth"
    uitleg_nl = "Koptelefoons, muizen, toetsenborden en telefoons zonder draad. Klik op een apparaat om te verbinden."
    uitleg_en = "Headphones, mice, keyboards and phones without a cable. Click a device to connect."
    zoekwoorden = ("bluetooth koptelefoon oortjes muis toetsenbord telefoon koppelen draadloos bluetooth headphones "
                   "earbuds mouse keyboard phone pair pairing wireless")

    HARD_UIT = ("Bluetooth staat uit met een knop of schakelaar op de computer (vliegtuigstand). Zet die eerst om.",
                "Bluetooth is turned off with a switch or key on the computer (airplane mode). Switch it back first.")

    def bouw(self) -> None:
        g = self.kaart()
        self.schakel = schuifje(True, self.zet_bt)
        self.hoofd = Rij("bluetooth", "Bluetooth", "", self.schakel)
        g.voeg(self.hoofd)
        nieuw = self.nieuw = Knop(t("Nieuw apparaat koppelen", "Pair a new device"), "stil", "lijn:map-plus")
        nieuw.clicked.connect(lambda _c=False: self.koppel_nieuw())
        self.lay.addWidget(sectie_met_knop(t("Jouw apparaten", "Your devices"), nieuw))
        self.lijst = self.kaart()

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.bt_aan(), bi.bt_apparaten(), bi.VOORBEELD or bi.bt_hardware(),
                                      bi.bt_hard_uit()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        aan, apparaten, *rest = uitkomst
        heeft = rest[0] if rest else True
        hard = bool(rest[1]) if len(rest) > 1 else False
        # Geen bluetooth in de computer: dat zeggen, geen schakelaar en knop die niets doen (U157).
        for w in (self.schakel, self.nieuw, self.lijst):
            w.setVisible(heeft)
        if not heeft:
            self.hoofd.zet_uitleg(t("Deze computer heeft geen bluetooth", "This computer has no Bluetooth"))
            return
        self.schakel.zet_stil(aan)
        verbonden = sum(1 for a in apparaten if a.verbonden)
        if not aan and hard:
            # Met een knop op de computer uitgezet: dan helpt het schuifje niet, en dat zeggen we (N15).
            self.hoofd.zet_uitleg(t("Uit met een knop of schakelaar op de computer (vliegtuigstand)",
                                    "Off with a switch or key on the computer (airplane mode)"))
        else:
            self.hoofd.zet_uitleg((t(f"Aan · {verbonden} verbonden", f"On · {verbonden} connected") if verbonden
                                   else t("Aan", "On")) if aan else t("Uit", "Off"))
        leeg_groep(self.lijst)
        for a in apparaten:
            batterij = t(f" · batterij {a.batterij}%", f" · battery {a.batterij}%") if a.batterij is not None else ""
            if a.verbonden:
                meer = meer_knop(lambda x=a: [("kruis", t("Verbreken", "Disconnect"), lambda: self.verbind(x)),
                                              ("prullenbak", t("Vergeten", "Forget"), lambda: self.vergeet(x))])
                self.lijst.voeg(Rij("vink", a.naam, t("Verbonden", "Connected") + batterij, meer))
            else:
                # Ook een apparaat dat niet verbonden is, kun je vergeten (bv. een oude koptelefoon).
                meer = meer_knop(lambda x=a: [("prullenbak", t("Vergeten", "Forget"), lambda: self.vergeet(x))])
                rij = Rij(apparaat_icoon(a.soort), a.naam, t("Niet verbonden", "Not connected") + batterij, meer,
                          klikbaar=aan, pijl=False)
                rij.geklikt.connect(lambda x=a: self.verbind(x))
                self.lijst.voeg(rij)
        if not apparaten:
            self.lijst.voeg(Rij("bluetooth", t("Nog niets gekoppeld", "Nothing paired yet"),
                                t("Kies 'Nieuw apparaat koppelen' en zet je apparaat in koppelstand.",
                                  "Choose 'Pair a new device' and put your device in pairing mode.")))

    def zet_bt(self, aan: bool) -> None:
        def klaar(uitkomst) -> None:
            ok, hard = uitkomst or (False, False)
            if aan and not ok:   # niet stil laten mislukken (N15)
                self.melding.toon(t(*self.HARD_UIT) if hard else
                                  t("Bluetooth aanzetten lukte niet.", "Turning on Bluetooth did not work."),
                                  "let_op" if hard else "fout", seconden=0 if hard else 8)
            QTimer.singleShot(800, self.ververs)

        op_achtergrond(self, lambda: (bi.zet_bt(aan), bi.bt_hard_uit()), klaar)

    # ---------------------------------------------------------------- koppelen
    def koppel_nieuw(self) -> None:
        """Nieuw apparaat koppelen, in BugOS zelf (niet met de wizard van KDE). Staat bluetooth uit, dan eerst aan."""
        self.nieuw.setEnabled(False)

        def klaar(uitkomst) -> None:
            self.nieuw.setEnabled(True)
            hard, aan = uitkomst or (False, False)
            if hard:
                self.melding.toon(t(*self.HARD_UIT), "let_op", seconden=0)
                return
            if aan:
                self.open_koppelen()
                return
            self.melding.toon(t("Bluetooth aanzetten…", "Turning on Bluetooth…"), seconden=15)
            op_achtergrond(self, lambda: bi.zet_bt(True), self.aangezet)

        op_achtergrond(self, lambda: (bi.bt_hard_uit(), bi.bt_aan()), klaar)

    def aangezet(self, ok) -> None:
        if not ok:
            self.melding.toon(t("Bluetooth aanzetten lukte niet.", "Turning on Bluetooth did not work."), "fout")
            return
        self.melding.hide()
        self.ververs()
        self.open_koppelen()

    def open_koppelen(self) -> None:
        oud = getattr(self, "koppel_dialoog", None)
        if oud is not None and not oud.isVisible():
            oud.deleteLater()
        koppelaar = NepKoppelaar() if bi.VOORBEELD else BluezKoppelaar()
        d = self.koppel_dialoog = KoppelDialoog(self, koppelaar)
        d.klaar.connect(lambda tekst, soort: self.melding.toon(tekst, soort))
        d.finished.connect(lambda _r: self.ververs())
        d.open()

    def verbind(self, a: bi.Apparaat) -> None:
        self.melding.toon(t(f"{a.naam}: even geduld…", f"{a.naam}: one moment…"), seconden=20)

        def klaar(gelukt) -> None:
            if gelukt:
                self.melding.toon(t(f"{a.naam} is verbroken.", f"{a.naam} is disconnected.") if a.verbonden else
                                  t(f"{a.naam} is verbonden.", f"{a.naam} is connected."), "goed")
            else:
                self.melding.toon(t(f"Dat lukte niet. Staat {a.naam} aan en dichtbij?",
                                    f"That did not work. Is {a.naam} on and nearby?"), "fout")
            self.ververs()

        op_achtergrond(self, lambda: bi.bt_verbind(a.adres, not a.verbonden), klaar)

    def vergeet(self, a: bi.Apparaat) -> None:
        op_achtergrond(self, lambda: bi.bt_vergeet(a.adres), lambda _u: self.ververs())
