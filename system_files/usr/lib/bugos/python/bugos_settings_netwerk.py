"""BugOS Instellingen: de pagina's Wifi en internet, en Bluetooth."""

from __future__ import annotations

import bugos_config as bi
from bugos_ui import Knop, Rij, bestaat, kde_instelling, leeg_groep, sectie, start, t
from bugos_settings_onderdelen import Blad, meer_knop, op_achtergrond, schuifje
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLineEdit


# ================================================================== wifi ===

def sterkte_woord(n: int) -> str:
    return t("Sterk", "Strong") if n >= 70 else t("Goed", "Good") if n >= 45 else t("Zwak", "Weak")


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
        g.voeg(self.kabel)
        kop = QHBoxLayout()
        kop.addWidget(sectie(t("Netwerken in de buurt", "Networks nearby")), 1)
        self.zoek_knop = Knop(t("Opnieuw zoeken", "Search again"), "stil", "lijn:verversen")
        self.zoek_knop.clicked.connect(lambda _c=False: self.ververs(True))
        kop.addWidget(self.zoek_knop)
        self.lay.addLayout(kop)
        self.lijst = self.kaart()
        # Een netwerk dat zijn naam niet laat zien (een 'verborgen' netwerk) (U109).
        self.ander = Knop(t("Ander netwerk…", "Other network…"), "stil", "lijn:plus")
        self.ander.clicked.connect(lambda _c=False: self.verbind_verborgen())
        self.lay.addWidget(self.ander, 0, Qt.AlignmentFlag.AlignLeft)

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
        for w in (self.schakel, self.zoek_knop, self.lijst, self.ander):
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
        """Vraag het wachtwoord van een netwerk ('' = niet ingevuld of geannuleerd)."""
        d = QInputDialog(self)
        d.setWindowTitle(t("Wachtwoord", "Password"))
        if veranderd:
            d.setLabelText(t(f"Verbinden met '{n.naam}' lukte niet. Misschien is het wachtwoord veranderd.\n"
                             "Wat is het wachtwoord nu?",
                             f"Connecting to '{n.naam}' did not work. Maybe the password changed.\n"
                             "What is the password now?"))
        else:
            d.setLabelText(t(f"Wat is het wachtwoord van '{n.naam}'?\n(Het staat vaak op de onderkant van het modem.)",
                             f"What is the password of '{n.naam}'?\n(It is often on the bottom of the router.)"))
        d.setTextEchoMode(QLineEdit.EchoMode.Password)
        d.setOkButtonText(t("Verbinden", "Connect"))
        d.setCancelButtonText(t("Annuleren", "Cancel"))
        if not d.exec():
            return ""
        return d.textValue()

    def verbind_met(self, n: bi.Netwerk, bekend: bool, wachtwoord: str = "") -> None:
        if getattr(n, "zakelijk", False) and not bekend:
            # School- of werkwifi (eduroam): daar hoort ook een gebruikersnaam bij, en dat kan alleen KDE's eigen
            # netwerkscherm (U495).
            self.melding.toon(t(f"'{n.naam}' is een netwerk van school of werk: daar hoort ook een gebruikersnaam bij. "
                                "Dat stel je in het netwerkscherm in; we openen het voor je.",
                                f"'{n.naam}' is a school or work network: it also needs a user name. You set that up "
                                "in the network screen; we open it for you."), "let_op", seconden=0)
            kde_instelling("kcm_networkmanagement")
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

def apparaat_icoon(soort: str) -> str:
    if soort.startswith("audio"):
        return "geluid"
    if soort.startswith("input-gaming"):
        return "spel"
    if soort == "phone":
        return "praten"
    return "bluetooth"


class BluetoothPagina(Blad):
    sleutel, icoon = "bluetooth", "bluetooth"
    titel_nl, titel_en = "Bluetooth", "Bluetooth"
    uitleg_nl = "Koptelefoons, muizen, toetsenborden en telefoons zonder draad. Klik op een apparaat om te verbinden."
    uitleg_en = "Headphones, mice, keyboards and phones without a cable. Click a device to connect."
    zoekwoorden = ("bluetooth koptelefoon oortjes muis toetsenbord telefoon koppelen draadloos bluetooth headphones "
                   "earbuds mouse keyboard phone pair pairing wireless")

    def bouw(self) -> None:
        g = self.kaart()
        self.schakel = schuifje(True, self.zet_bt)
        self.hoofd = Rij("bluetooth", "Bluetooth", "", self.schakel)
        g.voeg(self.hoofd)
        kop = QHBoxLayout()
        kop.addWidget(sectie(t("Jouw apparaten", "Your devices")), 1)
        nieuw = self.nieuw = Knop(t("Nieuw apparaat koppelen", "Pair a new device"), "stil", "lijn:map-plus")
        nieuw.clicked.connect(lambda _c=False: start("bluedevil-wizard") if bestaat("bluedevil-wizard")
                              else kde_instelling("kcm_bluetooth"))
        kop.addWidget(nieuw)
        self.lay.addLayout(kop)
        self.lijst = self.kaart()

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.bt_aan(), bi.bt_apparaten(), bi.VOORBEELD or bi.bt_hardware()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        aan, apparaten, *rest = uitkomst
        heeft = rest[0] if rest else True
        # Geen bluetooth in de computer: dat zeggen, geen schakelaar en knop die niets doen (U157).
        for w in (self.schakel, self.nieuw, self.lijst):
            w.setVisible(heeft)
        if not heeft:
            self.hoofd.zet_uitleg(t("Deze computer heeft geen bluetooth", "This computer has no Bluetooth"))
            return
        self.schakel.zet_stil(aan)
        verbonden = sum(1 for a in apparaten if a.verbonden)
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
        op_achtergrond(self, lambda: bi.zet_bt(aan), lambda _u: QTimer.singleShot(800, self.ververs))

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
