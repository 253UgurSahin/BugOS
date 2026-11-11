"""BugOS Instellingen: de pagina's Geluid, Scherm, Energie en Uiterlijk."""

from __future__ import annotations

import time
from pathlib import Path

import bugos_config as bi
import bugos_ui
from bugos_ui import (Chip, Groep, KeuzeKaart, Knop, Rij, Voortgang, label, leeg_groep, lijn_icoon, schermmaat, sectie,
                      t)
from bugos_settings_onderdelen import Blad, Keuzes, KiesDialoog, Regelaar, dichtstbij, op_achtergrond, schuifje
from bugos_settings_systeem import Schakelaars
from PySide6.QtCore import QProcess, QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

MIC = "microfoon" if "microfoon" in bugos_ui.LIJN else "geluid"
TEST_SECONDEN = 20              # de microfoontest stopt vanzelf
BASIS_MONSTERS = 4000           # het eerste halve seconde (8000 per seconde): hoe stil de kamer is
HOORDE_BOVEN, HOORDE_MIN = 20, 40   # 'gehoord': zoveel boven de stilte, en minstens zo hard (0..100, review I10)
VB_NIVEAUS = (4, 6, 5, 3, 6, 4, 12, 35, 62, 48, 70, 30, 8, 55)   # voorbeeldstand: eerst stil, dan praten


def kaart_zonder_kop(lay: QVBoxLayout) -> Groep:
    """Een kaart met regels, zoals Pagina.kaart(), maar het kopje staat er los boven (dan kan het apart weg)."""
    g = Groep()
    g.lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(g)
    return g


# ================================================================ geluid ===

class GeluidPagina(Blad):
    sleutel, icoon = "geluid", "geluid"
    titel_nl, titel_en = "Geluid", "Sound"
    uitleg_nl = "Hoe hard, en waar het geluid uit komt."
    uitleg_en = "How loud, and where the sound comes from."
    zoekwoorden = ("geluid volume luidspreker speaker koptelefoon hdmi tv stil dempen microfoon sound audio volume "
                   "speaker speakers headphones hdmi tv mute silent microphone mic")
    kde = "kcm_pulseaudio"

    def bouw(self) -> None:
        g = self.kaart()
        self.regelaar = Regelaar(50)
        self.regelaar.veranderd.connect(lambda w: op_achtergrond(self, lambda: bi.zet_volume(w), lambda _u: None))
        g.voeg(Rij("geluid", t("Volume", "Volume"), "", self.regelaar))
        self.stil = schuifje(False, lambda aan: op_achtergrond(self, lambda: bi.zet_stil(aan), lambda _u: None))
        g.voeg(Rij("kruis", t("Geluid uit", "Mute"), t("Alles even stil", "Everything quiet for a moment"),
                   self.stil))
        self.lijst = self.kaart(t("Waar komt het geluid uit? Klik om te kiezen.",
                                  "Where does the sound come from? Click to choose."))
        # De microfoon, helemaal in BugOS (niet meer het geluidscherm van KDE). Een eigen kopje 'Microfoon', zodat
        # 'Volume' kort blijft en de regel ook op 150 % past (review I7); zoeken op 'microfoon' komt hier (U166).
        self.lay.addWidget(sectie(t("Microfoon", "Microphone")))
        self.mic_kaart = kaart_zonder_kop(self.lay)
        self.mic_regelaar = Regelaar(80)
        self.mic_regelaar.veranderd.connect(
            lambda w: op_achtergrond(self, lambda: bi.zet_microfoon_volume(w), lambda _u: None))
        self.mic_kaart.voeg(Rij(MIC, t("Volume", "Volume"), "", self.mic_regelaar))
        self.mic_uit = schuifje(False, self.zet_mic_uit)
        self.mic_kaart.voeg(Rij("kruis", t("Microfoon uit", "Microphone off"),
                                t("Niemand hoort je, ook niet in een gesprek", "Nobody hears you, not even in a call"),
                                self.mic_uit))
        test = QWidget()
        tl = QHBoxLayout(test)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(12)
        self.meter = Voortgang()
        self.meter.setObjectName("dun")   # dun en grijs: meters zijn grijs (BRAND.md)
        self.meter.setFixedWidth(bugos_ui.px(160))
        self.meter.setAccessibleName(t("Hoe hard de microfoon je hoort", "How loud the microphone hears you"))
        self.meter.hide()
        tl.addWidget(self.meter, 0, Qt.AlignmentFlag.AlignVCenter)
        self.test_knop = Knop(t("Testen", "Test"), "gewoon")
        self.test_knop.clicked.connect(self.test_knop_geklikt)
        tl.addWidget(self.test_knop)
        self.test_rij = Rij(MIC, t("Test je microfoon", "Test your microphone"),
                            t("Druk op Testen en zeg iets. De balk beweegt als de microfoon je hoort.",
                              "Press Test and say something. The bar moves when the microphone hears you."), test)
        self.mic_kaart.voeg(self.test_rij)
        self._proces = None
        self._test_klok = QTimer(self)        # stopt de test vanzelf
        self._test_klok.setSingleShot(True)
        self._test_klok.timeout.connect(lambda: self.eind_test(True))
        self._vb_klok = QTimer(self)          # voorbeeldstand: een balk die beweegt, zonder microfoon
        self._vb_klok.setInterval(80)
        self._vb_klok.timeout.connect(self._vb_stukje)
        self.mic_lijst_kop = sectie(t("Waar praat je in? Klik om te kiezen.", "What do you talk into? Click to choose."))
        self.lay.addWidget(self.mic_lijst_kop)
        self.mic_lijst = kaart_zonder_kop(self.lay)

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (*bi.geluid(), bi.microfoon()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        volume, stil, uitgangen, *rest = uitkomst
        self.regelaar.zet(volume)
        self.stil.zet_stil(stil)
        leeg_groep(self.lijst)
        for u in uitgangen:
            if u.standaard:
                self.lijst.voeg(Rij("vink", u.omschrijving, "", Chip(t("In gebruik", "In use"), "goed")))
            else:
                rij = Rij("geluid", u.omschrijving, "", klikbaar=True, pijl=False)
                rij.geklikt.connect(lambda x=u: op_achtergrond(self, lambda: bi.kies_uitgang(x.naam),
                                                               lambda _u: self.ververs()))
                self.lijst.voeg(rij)
        if not uitgangen:
            self.lijst.voeg(Rij("geluid", t("Geen luidsprekers gevonden", "No speakers found"),
                                t("Sluit een koptelefoon of luidspreker aan.", "Connect headphones or a speaker.")))
        if rest:
            self.toon_microfoon(rest[0])

    def toon_microfoon(self, m) -> None:
        if m is None:   # het lezen ging mis (Klusje gaf None): zoals 'reageert niet'
            m = bi.Microfoon(False, 0, False, [])
        self.mic = m
        leeg_groep(self.mic_lijst)
        gekozen = any(i.standaard for i in m.ingangen)
        if not m.bereikbaar:
            self.mic_lijst.voeg(Rij(MIC, t("Het geluid reageert nu niet", "Sound is not responding right now"),
                                    t("Log uit en weer in. Helpt dat niet, start de computer dan opnieuw.",
                                      "Sign out and back in. If that does not help, restart the computer.")))
        else:
            for i in m.ingangen:
                if i.standaard:
                    self.mic_lijst.voeg(Rij("vink", i.omschrijving, "", Chip(t("In gebruik", "In use"), "goed")))
                else:
                    rij = Rij(MIC, i.omschrijving, "", klikbaar=True, pijl=False)
                    rij.geklikt.connect(lambda x=i: self.kies_microfoon(x))
                    self.mic_lijst.voeg(rij)
            # Een bluetooth-headset op 'muziek' heeft geen microfoon: niet 'Sluit een headset aan' zeggen (die zit er
            # al), maar één knop om hem op 'bellen' te zetten (review I6).
            for h in m.headsets:
                knop = Knop(t("Gebruik voor bellen", "Use for calls"), "gewoon")
                knop.clicked.connect(lambda _c=False, x=h: self.headset_bellen(x))
                self.mic_lijst.voeg(Rij(MIC, h.omschrijving, t("Nu alleen voor muziek. Zet hem op bellen om ermee te "
                                                                "praten.", "Now only for music. Switch it to calls to "
                                                                "talk through it."), knop))
            if not m.ingangen and not m.headsets:
                self.mic_lijst.voeg(Rij(MIC, t("Geen microfoon gevonden", "No microphone found"),
                                        t("Sluit een headset of microfoon aan. Een webcam heeft er vaak ook een.",
                                          "Connect a headset or microphone. A webcam often has one too.")))
        self.mic_kaart.setVisible(m.bereikbaar and gekozen)
        self.mic_lijst_kop.setVisible(m.bereikbaar and bool(m.ingangen or m.headsets))
        self.mic_regelaar.zet(m.volume)
        self.mic_uit.zet_stil(m.stil)

    def kies_microfoon(self, ingang) -> None:
        self.stop_test()
        def klaar(ok) -> None:
            if ok:
                self.melding.toon(t("Microfoon gekozen.", "Microphone chosen."), "goed")
            else:
                self.melding.toon(t("Dat lukte niet. Is de microfoon nog aangesloten?",
                                    "That did not work. Is the microphone still connected?"), "fout")
            self.ververs()
        op_achtergrond(self, lambda: bi.kies_ingang(ingang.naam), klaar)

    def headset_bellen(self, h) -> None:
        def klaar(ok) -> None:
            if ok:
                self.melding.toon(t("Je headset staat nu op bellen. Je kunt ermee praten.",
                                    "Your headset is now set for calls. You can talk through it."), "goed")
            else:
                self.melding.toon(t("Dat lukte niet. Zet de headset uit en weer aan, en probeer het nog eens.",
                                    "That did not work. Turn the headset off and on, and try again."), "fout")
            self.ververs()
        op_achtergrond(self, lambda: bi.headset_bellen(h.kaart, h.profiel), klaar)

    def zet_mic_uit(self, aan: bool) -> None:
        if aan:
            self.stop_test()
        op_achtergrond(self, lambda: bi.zet_microfoon_stil(aan), lambda _u: None)

    # ------------------------------------------------------ de microfoon testen ---
    # parec neemt op van de microfoon die gesprekken ook gebruiken (@DEFAULT_SOURCE@); er wordt niets bewaard, alleen
    # hoe hard elk stukje is. Weg van de pagina (ander tabje, venster dicht): de test stopt, BugOS luistert nooit stiekem.

    @property
    def test_bezig(self) -> bool:
        return self._proces is not None or self._vb_klok.isActive()

    def test_knop_geklikt(self) -> None:
        if self.test_bezig:
            self.eind_test(True)
            return
        if self.mic_uit.isChecked():
            self.melding.toon(t("Je microfoon staat uit. Zet hem eerst aan.", "Your microphone is off. Turn it on first."),
                              "let_op")
            return
        self.test_knop.setEnabled(False)

        def klaar(staat) -> None:
            self.test_knop.setEnabled(True)
            if not self.isVisible():
                return
            if staat == "stil":
                self.melding.toon(t("Je microfoon staat uit. Zet hem eerst aan.",
                                    "Your microphone is off. Turn it on first."), "let_op")
                self.ververs()
            elif staat != "ok":   # de gekozen microfoon is er niet meer (dan neemt parec stilletjes een andere: I9)
                self.melding.toon(t("Dat lukte niet. Is de microfoon nog aangesloten?",
                                    "That did not work. Is the microphone still connected?"), "fout")
                self.ververs()
            else:
                self.begin_test()
        op_achtergrond(self, bi.microfoon_klaar, klaar)

    def begin_test(self) -> None:
        self._hoogste = self._basis = self._toon_niveau = self._monsters = 0
        self._rest = b""
        self._begon = time.monotonic()
        if bi.VOORBEELD:
            self._vb_i = 0
            self._vb_klok.start()
        else:
            opdracht = bi.microfoon_test_opdracht()
            if not opdracht:
                self.test_mislukt()
                return
            p = QProcess(self)
            p.setProgram(opdracht[0])
            p.setArguments(opdracht[1:])
            p.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            p.readyReadStandardOutput.connect(self._stukje)
            p.errorOccurred.connect(lambda _f, p=p: self._proces_weg(p))
            p.finished.connect(lambda *_a, p=p: self._proces_weg(p))
            self._proces = p
            p.start()
        self.meter.setValue(0)
        self.meter.show()
        self.test_knop.setText(t("Stoppen", "Stop"))
        self._test_klok.start(int(TEST_SECONDEN * 1000))

    def _verwerk(self, n: int, monsters: int) -> None:
        # Het eerste halve seconde is de stilte van de kamer: 'gehoord' telt pas ruim daarboven (review I10).
        if self._monsters < BASIS_MONSTERS:
            self._basis = max(self._basis, n)
        else:
            self._hoogste = max(self._hoogste, n)
        self._monsters += monsters
        self._toon_niveau = max(n, round(self._toon_niveau * 0.7))
        self.meter.setValue(self._toon_niveau)

    def _stukje(self) -> None:
        if self._proces is None:
            return
        data = self._rest + bytes(self._proces.readAllStandardOutput())
        heel = len(data) - len(data) % 2
        self._rest = data[heel:]
        if heel:
            self._verwerk(bi.niveau(data[:heel]), heel // 2)

    def _vb_stukje(self) -> None:
        self._verwerk(VB_NIVEAUS[self._vb_i % len(VB_NIVEAUS)], 640)   # 80 ms bij 8000 Hz
        self._vb_i += 1

    def _proces_weg(self, p) -> None:
        if p is not self._proces:
            return   # al gestopt door ons
        if self._monsters == 0 and time.monotonic() - self._begon < 1.5:
            self.test_mislukt()   # parec startte niet, of stopte meteen zonder geluid
        else:
            self.eind_test(True)

    def test_mislukt(self) -> None:
        self.stop_test()
        self.melding.toon(t("De test lukte niet. Probeer het nog eens.", "The test did not work. Try again."), "fout")

    def eind_test(self, met_uitslag: bool) -> None:
        if not self.test_bezig:
            return
        gehoord = self._hoogste >= max(self._basis + HOORDE_BOVEN, HOORDE_MIN)
        self.stop_test()
        if not met_uitslag:
            return
        if gehoord:
            self.melding.toon(t("Je microfoon werkt.", "Your microphone works."), "goed")
        else:
            self.melding.toon(t("We hoorden niets. Staat het volume van de microfoon laag, of is het de verkeerde "
                                "microfoon?", "We heard nothing. Is the microphone volume low, or is it the wrong "
                                "microphone?"), "let_op")
        self.ververs()

    def stop_test(self) -> None:
        """Stil stoppen (geen melding)."""
        self._test_klok.stop()
        self._vb_klok.stop()
        p, self._proces = self._proces, None
        if p is not None:
            for sein in (p.readyReadStandardOutput, p.errorOccurred, p.finished):
                try:
                    sein.disconnect()
                except (RuntimeError, TypeError):
                    pass
            p.terminate()
            if not p.waitForFinished(500):
                p.kill()
                p.waitForFinished(500)
            p.deleteLater()
        self.meter.hide()
        self.test_knop.setText(t("Testen", "Test"))

    def hideEvent(self, e) -> None:  # noqa: N802
        self.stop_test()
        super().hideEvent(e)


# ================================================================ scherm ===

TERUG_NA = 15   # s: zo lang wacht 'Beeld houden?' op een klik, dan gaat het vanzelf terug (tests: 1)


class Wissel(QWidget):
    """Een plekje voor één onderdeel dat per scherm anders is (bv. de keuzes voor de verversing)."""

    def __init__(self, inhoud: QWidget):
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self.inhoud = inhoud
        self._lay.addWidget(inhoud)

    def zet(self, inhoud: QWidget) -> None:
        oud, self.inhoud = self.inhoud, inhoud
        self._lay.removeWidget(oud)
        oud.hide()
        oud.deleteLater()
        self._lay.addWidget(inhoud)
        self.updateGeometry()


def keuzes_voor(opties: list, titel: str, gekozen) -> Keuzes:
    """Keuzes met de titel van de regel erbij voor de schermlezer (zoals Rij dat bij het bouwen doet)."""
    k = Keuzes(opties)
    for knop in k.knoppen.values():
        knop.setAccessibleDescription(titel)
    k.gekozen.connect(gekozen)
    return k


def niets_gekozen(k: Keuzes) -> None:
    k.groep.setExclusive(False)
    for knop in k.knoppen.values():
        knop.setChecked(False)
    k.groep.setExclusive(True)


class HoudenDialoog(QDialog):
    """'Beeld houden?': na een verandering die het scherm zwart kan maken. Klik je niet, dan gaat het vanzelf terug.
    Enter, Esc en het kruisje zijn allemaal 'Terugzetten' (de veilige kant)."""

    def __init__(self, ouder: QWidget):
        super().__init__(ouder)
        self.setWindowTitle(t("Beeld houden?", "Keep this display?"))
        self.setModal(True)
        breed = schermmaat((bugos_ui.px(460), 0))[0][0]
        self.setMinimumWidth(breed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(label(t("Is alles goed te zien?", "Can you see everything?"), "kop2"))
        lay.addWidget(label(t("Klik op Houden als het beeld goed is. Anders gaat het vanzelf terug.",
                              "Click Keep if the picture looks right. Otherwise it goes back by itself."), "klein"))
        self.rest = TERUG_NA
        self.teller = label("", "sub")
        lay.addWidget(self.teller)
        lay.addSpacing(4)
        knoppen = QHBoxLayout()
        knoppen.setSpacing(8)
        knoppen.addStretch(1)
        self.terug = Knop(t("Terugzetten", "Go back"), "stil")
        self.terug.clicked.connect(self.reject)
        self.houden = Knop(t("Houden", "Keep"), "hoofd")
        self.houden.clicked.connect(self.accept)
        knoppen.addWidget(self.terug)
        knoppen.addWidget(self.houden)
        lay.addLayout(knoppen)
        self.terug.setDefault(True)   # een Enter uit gewoonte gaat terug
        self.terug.setFocus()
        self.klok = QTimer(self)
        self.klok.setInterval(1000)
        self.klok.timeout.connect(self.tik)
        self.zet_teller()
        self.klok.start()

    def zet_teller(self) -> None:
        self.teller.setText(t("Terug over {n} seconden", "Going back in {n} seconds").format(n=self.rest))

    def tik(self) -> None:
        self.rest -= 1
        if self.rest <= 0:
            self.klok.stop()
            self.reject()
            return
        self.zet_teller()

    def done(self, r: int) -> None:
        self.klok.stop()
        super().done(r)

    def closeEvent(self, e) -> None:  # noqa: N802
        e.ignore()
        self.reject()


def scherm_model(naam: str) -> str:
    """Het merk en type dat het scherm zelf zegt (Qt), bv. 'Samsung TV'. Niet als het alleen de aansluiting herhaalt
    (de VM zegt 'Virtual-1-QEMU Monitor')."""
    from PySide6.QtGui import QGuiApplication
    for sc in QGuiApplication.screens():
        if sc.name() == naam:
            model = (sc.model() or "").strip()
            if model and naam not in model:
                return model
    return ""


def scherm_naam(s, lijst) -> str:
    """De naam die je ziet: 'Ingebouwd scherm', 'Scherm of tv (HDMI)', of het merk van het scherm."""
    model = scherm_model(s.naam)
    if model:
        return f"{model} (HDMI)" if s.soort == "hdmi" else model
    if s.soort == "ingebouwd":
        return t("Ingebouwd scherm", "Built-in screen")
    if s.soort == "hdmi":
        return t("Scherm of tv (HDMI)", "Screen or TV (HDMI)")
    return t("Scherm", "Screen") if len(lijst) == 1 else t("Extra scherm", "Extra screen")


class SchermPagina(Blad):
    sleutel, icoon = "scherm", "computer"
    titel_nl, titel_en = "Scherm", "Display"
    uitleg_nl = "Helderheid, warm licht voor de avond, en hoe groot alles is."
    uitleg_en = "Brightness, warm light for the evening, and how big everything is."
    zoekwoorden = ("scherm beeldscherm monitor helderheid nachtlicht nachtlampje groot groter klein schaal tekst "
                   "resolutie verversing hz draaien kantelen staand tweede scherm tv beamer projector uitbreiden "
                   "dupliceren hoofdscherm "
                   "display screen monitor brightness night light night color blue light size bigger smaller scale "
                   "scaling text resolution refresh rate rotate rotation portrait second screen tv projector extend "
                   "duplicate mirror main screen")
    kde = "kcm_kscreen"

    def bouw(self) -> None:
        self.bezig = False
        self._schermen = None
        self._gekozen = None         # het scherm onder 'Instellen voor' (naam van de aansluiting)
        self._stand_opties = self._kies_opties = None
        g = self.kaart()
        self.helder = Regelaar(70)
        self.helder.veranderd.connect(lambda w: op_achtergrond(self, lambda: bi.zet_helderheid(w), lambda _u: None))
        self.helder_rij = Rij("zon", t("Helderheid", "Brightness"), "", self.helder)
        g.voeg(self.helder_rij)
        self.nacht = schuifje(False, lambda aan: op_achtergrond(self, lambda: bi.zet_nachtlicht(aan), lambda _u: None))
        g.voeg(Rij("maan", t("Nachtlicht", "Night light"),
                   t("'s Avonds warmer licht, prettiger voor je ogen", "Warmer light in the evening, easier on your eyes"),
                   self.nacht))
        # Je schermen: alleen met twee of meer (een laptop met een tv, twee monitoren).
        self.schermen_kop = sectie(t("Je schermen", "Your screens"))
        self.lay.addWidget(self.schermen_kop)
        self.schermen_kaart = kaart_zonder_kop(self.lay)
        titel_stand = t("Meer dan één scherm", "More than one screen")
        self.stand = Wissel(keuzes_voor([], titel_stand, self.zet_stand))
        self.stand_rij = Rij("computer", titel_stand, t("Uitbreiden geeft meer ruimte. Hetzelfde beeld is handig "
                                                        "voor de tv.", "Extend gives more room. Duplicate is handy "
                                                        "for the TV."), self.stand)
        self.schermen_kaart.voeg(self.stand_rij)
        titel_kies = t("Instellen voor", "Settings for")
        self.kies = Wissel(keuzes_voor([], titel_kies, self.kies_scherm))
        self.kies_rij = Rij("computer", titel_kies, "", self.kies)
        self.schermen_kaart.voeg(self.kies_rij)
        self.schermen_kop.hide()
        self.schermen_kaart.hide()
        # Het beeld van (het gekozen) scherm. Zonder gegevens van kscreen-doctor alleen de grootte, zoals vroeger.
        self.beeld_kop = sectie(t("Grootte", "Size"))
        self.lay.addWidget(self.beeld_kop)
        self.beeld_kaart = kaart_zonder_kop(self.lay)
        hoofd = QWidget()
        hl = QHBoxLayout(hoofd)
        hl.setContentsMargins(0, 0, 0, 0)
        self.hoofd_chip = Chip(t("Dit is je hoofdscherm", "This is your main screen"), "goed")
        self.hoofd_knop = Knop(t("Maak hoofdscherm", "Make main screen"), "gewoon")
        self.hoofd_knop.clicked.connect(self.maak_hoofd)
        hl.addWidget(self.hoofd_chip)
        hl.addWidget(self.hoofd_knop)
        self.hoofd_rij = Rij("ster", t("Hoofdscherm", "Main screen"),
                             t("Hier komen de taakbalk en nieuwe vensters", "The taskbar and new windows go here"), hoofd)
        self.beeld_kaart.voeg(self.hoofd_rij)
        titel_plek = t("Waar staat dit scherm?", "Where is this screen?")
        self.plek = keuzes_voor([("links", t("Links", "Left")), ("rechts", t("Rechts", "Right")),
                                 ("boven", t("Boven", "Above")), ("onder", t("Onder", "Below"))], titel_plek,
                                self.zet_plek)
        self.plek_rij = Rij("kaart", titel_plek, t("Naast je hoofdscherm, zodat de muis de goede kant op gaat",
                                                   "Next to your main screen, so the mouse goes the right way"),
                            self.plek)
        self.beeld_kaart.voeg(self.plek_rij)
        self.resolutie_rij = Rij("computer", t("Resolutie", "Resolution"), "", klikbaar=True)
        self.resolutie_rij.geklikt.connect(self.kies_resolutie)
        self.beeld_kaart.voeg(self.resolutie_rij)
        titel_hz = t("Verversing", "Refresh rate")
        self.hz = Wissel(keuzes_voor([(60, "60 Hz")], titel_hz, self.zet_hz))
        self.hz_rij = Rij("klok", titel_hz, t("Hoe vaak per seconde het beeld ververst. Hoger is vloeiender.",
                                              "How often per second the picture refreshes. Higher is smoother."), self.hz)
        self.beeld_kaart.voeg(self.hz_rij)
        titel_draai = t("Draaien", "Rotation")
        self.draai = keuzes_voor([(1, t("Gewoon", "Normal")), (2, t("Links", "Left")), (8, t("Rechts", "Right")),
                                  (4, t("Omgekeerd", "Upside down"))], titel_draai, self.zet_draai)
        self.draai_rij = Rij("verversen", titel_draai, t("Voor een scherm dat op zijn kant staat",
                                                         "For a screen that stands on its side"), self.draai)
        self.beeld_kaart.voeg(self.draai_rij)
        self.grootte = Keuzes([(w, f"{w:.0%}") for w in bi.SCHALEN])
        self.grootte.gekozen.connect(self.zet_grootte)
        self.grootte_rij = Rij("computer", t("Alles groter of kleiner", "Make everything bigger or smaller"),
                               t("Tekst, knoppen en vensters", "Text, buttons and windows"), self.grootte)
        self.beeld_kaart.voeg(self.grootte_rij)
        aanzetten = Knop(t("Aanzetten", "Turn on"), "gewoon")
        aanzetten.clicked.connect(self.zet_aan)
        self.uit_rij = Rij("computer", t("Dit scherm staat uit", "This screen is off"),
                           t("Je gebruikt nu alleen het andere scherm", "You only use the other screen now"), aanzetten)
        self.beeld_kaart.voeg(self.uit_rij)
        for r in (self.hoofd_rij, self.plek_rij, self.resolutie_rij, self.hz_rij, self.draai_rij, self.uit_rij):
            r.hide()
        # Een tv in- of uitpluggen terwijl de pagina open is: meteen bijwerken.
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self.schermen_anders)
            app.screenRemoved.connect(self.schermen_anders)

    def schermen_anders(self, *_a) -> None:
        if self.isVisible():
            self.ververs()

    def ververs(self) -> None:
        def lees():
            schermen = bi.beeldschermen()   # één keer kscreen-doctor (de grootte staat erin)
            hoofd = next((s for s in schermen or [] if s.hoofd), None)
            return bi.helderheid(), bi.nachtlicht(), hoofd.schaal if hoofd else bi.schaal(), schermen
        op_achtergrond(self, lees, self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        helder, nacht, schaal, *rest = uitkomst
        # Zonder schermen (oude vorm, of kscreen-doctor werkt niet): de grens van Qt, zoals vroeger (U397, I13).
        self._schermen = rest[0] if rest else None
        self.helder_rij.setVisible(helder is not None)
        if helder is not None:
            self.helder.zet(helder)
        self.nacht.zet_stil(nacht)
        self.toon_schermen()
        s = self.gekozen_scherm()
        self.toon_beeld(s, s.schaal if s is not None else schaal)

    def meer_schermen(self) -> bool:
        return len(self._schermen or []) >= 2

    def toon_schermen(self) -> None:
        """De kaart 'Je schermen': uitbreiden, hetzelfde beeld, of maar één aan; en welk scherm je instelt."""
        lijst = self._schermen or []
        meer = self.meer_schermen()
        self.schermen_kop.setVisible(meer)
        self.schermen_kaart.setVisible(meer)
        if not meer:
            self._gekozen = None
            return
        nummers = bi.schermnummers(lijst)
        if self._gekozen not in nummers:
            hoofd = next((s for s in lijst if s.hoofd), lijst[0])
            self._gekozen = hoofd.naam
        op_nummer = sorted(lijst, key=lambda s: nummers[s.naam])
        opties = [("uitbreiden", t("Uitbreiden", "Extend")), ("kopie", t("Hetzelfde beeld", "Duplicate"))]
        if len(lijst) == 2:
            opties += [("alleen:" + s.naam, t("Alleen {n}", "Only {n}").format(n=nummers[s.naam])) for s in op_nummer]
        if opties != self._stand_opties:
            self._stand_opties = opties
            self.stand.zet(keuzes_voor(opties, self.stand_rij.titel.text(), self.zet_stand))
        stand = bi.schermstand(lijst)
        if stand in self.stand.inhoud.knoppen:
            self.stand.inhoud.zet(stand)
        else:
            niets_gekozen(self.stand.inhoud)   # (3 schermen, maar één aan)
        kies = [(s.naam, t("Scherm {n}", "Screen {n}").format(n=nummers[s.naam])) for s in op_nummer]
        if kies != self._kies_opties:
            self._kies_opties = kies
            self.kies.zet(keuzes_voor(kies, self.kies_rij.titel.text(), self.kies_scherm))
        self.kies.inhoud.zet(self._gekozen)
        s = self.gekozen_scherm()
        self.kies_rij.zet_uitleg(scherm_naam(s, lijst) if s is not None else "")

    def toon_beeld(self, s, schaal: float) -> None:
        """Hoofdscherm, plek, resolutie, verversing, draaien en grootte van het gekozen scherm."""
        lijst = self._schermen or []
        self._schaal = schaal   # onthouden: bij een klik niet opnieuw kscreen-doctor vragen (dat houdt het venster op) (U407)
        if s is None:
            self.beeld_kop.setText(t("Grootte", "Size"))
            for r in (self.hoofd_rij, self.plek_rij, self.resolutie_rij, self.hz_rij, self.draai_rij, self.uit_rij):
                r.hide()
            self.grootte_rij.show()
            self.toon_grootte(schaal)
            return
        if self.meer_schermen():
            self.beeld_kop.setText(t("Scherm {n} · {naam}", "Screen {n} · {naam}").format(
                n=bi.schermnummers(lijst)[s.naam], naam=scherm_naam(s, lijst)))
        else:
            self.beeld_kop.setText(t("Beeld", "Picture"))
        if not s.aan:   # 'Alleen' het andere scherm: dit scherm staat uit
            for r in (self.hoofd_rij, self.plek_rij, self.resolutie_rij, self.hz_rij, self.draai_rij, self.grootte_rij):
                r.hide()
            self.uit_rij.show()
            return
        self.uit_rij.hide()
        stand = bi.schermstand(lijst)
        aan = [x for x in lijst if x.aan]
        self.hoofd_rij.setVisible(len(aan) >= 2 and stand != "kopie")
        self.hoofd_chip.setVisible(s.hoofd)
        self.hoofd_knop.setVisible(not s.hoofd)
        kant = bi.huidige_kant(lijst, s.naam)
        self.plek_rij.setVisible(stand == "uitbreiden" and kant is not None)
        if kant is not None:
            self.plek.zet(kant)
        b, h = bi.huidige_resolutie(s)
        self.resolutie_rij.zet_uitleg(t("Hoe scherp het beeld is: nu {b} × {h}",
                                        "How sharp the picture is: now {b} × {h}").format(b=b, h=h))
        self.resolutie_rij.setVisible(bool(s.standen))
        opties = bi.verversingen(s, b, h)
        if [hz for _i, hz in opties] != list(self.hz.inhoud.knoppen):
            self.hz.zet(keuzes_voor([(hz, f"{hz} Hz") for _i, hz in opties] or [(0, "")],
                                    self.hz_rij.titel.text(), self.zet_hz))
        nu = s.stand()
        if nu is not None and round(nu.hz) in self.hz.inhoud.knoppen:
            self.hz.inhoud.zet(round(nu.hz))
        else:
            niets_gekozen(self.hz.inhoud)
        self.hz_rij.setVisible(len(opties) > 1)
        if s.draai in self.draai.knoppen:
            self.draai.zet(s.draai)
        else:
            niets_gekozen(self.draai)   # gespiegeld (uit KDE): geen van de vier
        self.draai_rij.show()
        self.grootte_rij.show()
        self.toon_grootte(schaal)

    def toon_grootte(self, schaal: float) -> None:
        self.grootte.zet(min(bi.SCHALEN, key=lambda w: abs(w - schaal)))
        # Op een klein scherm (1366×768) is 200% maar 683×384: dan past niets meer, ook de knop terug niet. Alleen
        # groottes aanbieden waarbij minstens 1024×700 overblijft (de huidige blijft altijd te kiezen) (U397).
        grens = self.grens()
        for waarde, knop in self.grootte.knoppen.items():
            knop.setEnabled(waarde <= max(grens, schaal + 0.01))

    def gekozen_scherm(self):
        schermen = getattr(self, "_schermen", None)
        if not schermen:
            return None
        return next((s for s in schermen if s.naam == self._gekozen), None) or \
            next((s for s in schermen if s.hoofd), schermen[0])

    def grens(self) -> float:
        """De grootste grootte voor het gekozen scherm: uit de echte beeldpunten als we die weten (P2)."""
        s = self.gekozen_scherm()
        return bi.grootste_schaal(s) if s is not None else groot_genoeg()

    # ------------------------------------------------------------ veranderen ---

    def kies_scherm(self, naam: str) -> None:
        self._gekozen = naam
        self.toon_schermen()
        s = self.gekozen_scherm()
        if s is not None:
            self.toon_beeld(s, s.schaal)

    def zet_stand(self, stand: str) -> None:
        lijst = self._schermen or []
        if not lijst or stand == bi.schermstand(lijst):
            return
        if stand == "uitbreiden":
            stappen = bi.stappen_uitbreiden(lijst)
        elif stand == "kopie":
            stappen = bi.stappen_kopie(lijst)
        else:
            stappen = bi.stappen_alleen(lijst, stand.partition(":")[2])
        self.verander(stappen)

    def maak_hoofd(self) -> None:
        s = self.gekozen_scherm()
        if s is not None and not s.hoofd:
            self.verander(bi.stappen_hoofd(s.naam))

    def zet_plek(self, kant: str) -> None:
        s = self.gekozen_scherm()
        lijst = self._schermen or []
        if s is None or kant == bi.huidige_kant(lijst, s.naam):
            return
        self.verander(bi.stappen_plek(lijst, s.naam, kant))

    def zet_aan(self) -> None:
        if self._schermen:
            self.verander(bi.stappen_uitbreiden(self._schermen))

    def kies_resolutie(self) -> None:
        s = self.gekozen_scherm()
        if s is None or self.bezig:
            return
        nu = bi.huidige_resolutie(s)
        items = [((b, h), t("{b} × {h} (aanbevolen)", "{b} × {h} (recommended)").format(b=b, h=h) if beste
                  else f"{b} × {h}") for b, h, beste in bi.resoluties(s)]
        d = KiesDialoog(self, t("Kies een resolutie", "Choose a resolution"), items, huidig=nu)
        if d.exec() and d.gekozen and tuple(d.gekozen) != nu:
            b, h = d.gekozen
            self.verander(bi.stappen_stand(s.naam, bi.stand_voor(s, b, h)))

    def zet_hz(self, hz: int) -> None:
        s = self.gekozen_scherm()
        nu = s.stand() if s is not None else None
        if s is None or (nu is not None and round(nu.hz) == hz):
            return
        b, h = bi.huidige_resolutie(s)
        self.verander(bi.stappen_stand(s.naam, bi.stand_voor(s, b, h, hz)))

    def zet_draai(self, code: int) -> None:
        s = self.gekozen_scherm()
        if s is None or s.draai == code:
            return
        self.verander(bi.stappen_draai(s.naam, code))

    def zet_grootte(self, waarde: float) -> None:
        if waarde > max(self.grens(), getattr(self, "_schaal", 1.0) + 0.01):   # (U397, U407)
            self.melding.toon(t("Dat is te groot voor dit scherm: dan past niets meer.",
                                "That is too big for this screen: nothing would fit any more."), "let_op")
            self.ververs()
            return
        s = self.gekozen_scherm()
        per_scherm = s is not None and sum(1 for x in self._schermen or [] if x.aan) >= 2
        self.melding.toon(t("Grootte {p} wordt ingesteld…", "Setting size to {p}…").format(p=f"{waarde:.0%}"))

        def klaar(ok) -> None:
            if ok:
                self._schaal = waarde
                self.melding.toon(t("Klaar. Sommige programma's worden pas groter als je ze opnieuw opent.",
                                    "Done. Some programs only change after you open them again."), "goed")
                if per_scherm:
                    self.ververs()   # de andere schermen schoven mee (I4)
            else:   # mislukt: opnieuw lezen, dan staat de echte grootte weer gekozen
                self.melding.toon(t("Dat lukte niet. Probeer een andere grootte.",
                                    "That did not work. Try another size."), "fout")
                self.ververs()
        # Eén scherm: precies zoals vroeger (alle schermen). Meer: alleen het gekozen scherm.
        op_achtergrond(self, (lambda: bi.zet_schaal(waarde, s.naam)) if per_scherm else (lambda: bi.zet_schaal(waarde)),
                       klaar)

    def zet_slot(self, dicht: bool) -> None:
        self.bezig = dicht
        self.schermen_kaart.setEnabled(not dicht)
        self.beeld_kaart.setEnabled(not dicht)

    def verander(self, stappen: list[str]) -> None:
        """Iets aan de schermen veranderen. Kan het beeld zwart worden, dan daarna 'Beeld houden?' (C3)."""
        if self.bezig or not stappen:
            self.ververs()   # de knoppen weer zoals het echt staat
            return
        self.zet_slot(True)
        self.melding.toon(t("Even geduld…", "One moment…"), seconden=0)
        op_achtergrond(self, lambda: bi.scherm_wijzigen(stappen), self.na_wijzigen)

    def klaar_met_wijzigen(self) -> None:
        self.zet_slot(False)
        self.ververs()

    def na_wijzigen(self, w) -> None:
        if w is None or not w.gelukt:
            if w is not None and not w.terug:
                self.melding.toon(t("Dat lukte niet. BugOS zet je scherm zo vanzelf terug zoals het was.",
                                    "That did not work. BugOS puts your screen back as it was in a moment."), "fout")
            else:
                self.melding.toon(t("Dat lukte niet. Je scherm staat weer zoals het was.",
                                    "That did not work. Your screen is back as it was."), "fout")
            self.klaar_met_wijzigen()
            return
        if not w.risico:
            self.melding.toon(t("Klaar.", "Done."), "goed")
            self.klaar_met_wijzigen()
            return
        # De vraag gaat open: een verse timer die pas na de vraag afgaat (review I3).
        op_achtergrond(self, lambda: bi.vangnet_opnieuw(w.vangnet, w.herstel, TERUG_NA + 15),
                       lambda nieuw: self.vraag_houden(w, nieuw if nieuw is not None else w.vangnet))

    def vraag_houden(self, w, vangnet) -> None:
        self.melding.hide()
        houden = HoudenDialoog(self).exec() == QDialog.DialogCode.Accepted
        if houden:
            def gehouden(ok) -> None:
                if ok:
                    self.melding.toon(t("Klaar. Het nieuwe beeld blijft.", "Done. The new display stays."), "goed")
                else:   # de timer liep nog: misschien springt het toch terug (review I3)
                    self.melding.toon(t("Het nieuwe beeld blijft misschien niet. Springt het terug, kies het dan nog "
                                        "een keer.", "The new display may not stay. If it switches back, choose it "
                                        "again."), "let_op")
                self.klaar_met_wijzigen()
            op_achtergrond(self, lambda: bi.vangnet_uit(vangnet), gehouden)
        else:
            def terug(ok) -> None:
                if ok:
                    self.melding.toon(t("Het beeld staat weer zoals het was.", "The display is back as it was."), "info")
                else:
                    self.melding.toon(t("Terugzetten lukte niet. BugOS probeert het zo nog een keer.",
                                        "Going back did not work. BugOS tries again in a moment."), "fout")
                self.klaar_met_wijzigen()
            op_achtergrond(self, lambda: bi.scherm_terug(w.herstel, vangnet), terug)


def groot_genoeg() -> float:
    """De grootste schaal waarbij het scherm nog minstens 1024×700 (logische) beeldpunten heeft (U397)."""
    from PySide6.QtGui import QGuiApplication
    scherm = QGuiApplication.primaryScreen()
    if scherm is None:
        return 2.0
    echt_b = scherm.size().width() * scherm.devicePixelRatio()
    echt_h = scherm.size().height() * scherm.devicePixelRatio()
    beste = 1.0
    for w in (1.0, 1.25, 1.5, 1.75, 2.0):
        if echt_b / w >= 1024 and echt_h / w >= 700:
            beste = w
    return beste


# =============================================================== energie ===

PROFIEL_TEKST = {
    "power-saver": (("Zuinig", "Saver"), ("Batterij gaat langer mee", "Battery lasts longer"), "batterij"),
    "balanced": (("Gebalanceerd", "Balanced"), ("Aanbevolen", "Recommended"), "vink"),
    "performance": (("Snel", "Fast"), ("Volle kracht, voor games", "Full power, for games"), "spel"),
}


def keuze_kaart(icoon_naam: str, naam: str, uitleg_tekst: str) -> KeuzeKaart:
    inhoud = QWidget()
    il = QVBoxLayout(inhoud)
    il.setContentsMargins(4, 4, 4, 4)
    il.setSpacing(6)
    plaatje = QLabel()
    plaatje.setPixmap(lijn_icoon(icoon_naam, "tekst", 24, gekozen=None).pixmap(24, 24))
    il.addWidget(plaatje)
    il.addWidget(label(naam, "kop3", wrap=False))
    il.addWidget(label(uitleg_tekst, "klein"))
    kaart = KeuzeKaart(inhoud)
    kaart.setMinimumHeight(112)
    return kaart


class EnergiePagina(Blad):
    sleutel, icoon = "energie", "batterij"
    titel_nl, titel_en = "Energie", "Power"
    uitleg_nl = "Zuinig of snel, en hoe het met de batterij gaat."
    uitleg_en = "Saving or fast, and how the battery is doing."
    zoekwoorden = ("energie batterij accu stroom zuinig snel prestaties slaapstand opladen power battery energy "
                   "saver performance sleep suspend charging lid screen off")
    kde = "kcm_powerdevilprofilesconfig"

    def bouw(self) -> None:
        self.batterij_kaart = self.kaart()
        self.batterij = Rij("batterij", t("Batterij", "Battery"), "")
        self.batterij_kaart.voeg(self.batterij)
        self.lay.addWidget(sectie(t("Hoe moet je computer werken?", "How should your computer work?")))
        rij = QHBoxLayout()
        rij.setSpacing(12)
        self.profielen: dict[str, KeuzeKaart] = {}
        groep = QButtonGroup(self)
        for profiel in bi.PROFIELEN:
            (nl, en), (unl, uen), ic = PROFIEL_TEKST[profiel]
            kaart = keuze_kaart(ic, t(nl, en), t(unl, uen))
            kaart.clicked.connect(lambda _c=False, p=profiel: self.zet_profiel(p))
            groep.addButton(kaart)
            self.profielen[profiel] = kaart
            rij.addWidget(kaart, 1)
        self.profiel_rij = QWidget()
        self.profiel_rij.setLayout(rij)
        self.lay.addWidget(self.profiel_rij)
        self.geen_profiel = label(t("Deze computer kan niet wisselen tussen zuinig en snel.",
                                    "This computer cannot switch between saving and fast."), "sub")
        self.geen_profiel.hide()
        self.lay.addWidget(self.geen_profiel)
        g = self.kaart(t("Scherm uit en slapen", "Screen off and sleep"))
        self.scherm_uit = Keuzes([(300, t("5 min", "5 min")), (600, t("10 min", "10 min")), (1800, t("30 min", "30 min")),
                                  (0, t("Nooit", "Never"))])
        self.scherm_uit.gekozen.connect(lambda s: op_achtergrond(self, lambda: bi.zet_scherm_uit_na(s), lambda _u: None))
        self.scherm_rij = Rij("computer", t("Scherm uit als je niets doet", "Screen off when you do nothing"),
                              t("Even met de muis bewegen en het is terug", "Move the mouse and it is back"), self.scherm_uit)
        g.voeg(self.scherm_rij)
        self.slaap = Keuzes([(600, t("10 min", "10 min")), (900, t("15 min", "15 min")), (1800, t("30 min", "30 min")), (3600, t("1 uur", "1 hour")),
                             (0, t("Nooit", "Never"))])
        self.slaap.gekozen.connect(lambda s: op_achtergrond(self, lambda: bi.zet_slaap_na(s), lambda _u: None))
        self.slaap_rij = Rij("maan", t("Slaapstand als je niets doet", "Sleep when you do nothing"),
                             t("Zuinig; alles staat er weer zodra je een toets indrukt",
                               "Saves power; everything is back as soon as you press a key"), self.slaap)
        g.voeg(self.slaap_rij)
        self.aanuit = Keuzes([(bi.KNOP_VRAGEN, t("Vragen", "Ask")), (bi.KNOP_SLAPEN, t("Slapen", "Sleep")),
                              (bi.KNOP_UIT, t("Uitzetten", "Shut down"))])
        self.aanuit.gekozen.connect(lambda w: op_achtergrond(self, lambda: bi.zet_aanuit_knop(w), lambda _u: None))
        g.voeg(Rij("aan", t("Als je op de aan/uit-knop drukt", "When you press the power button"), "", self.aanuit))
        self.deksel = Keuzes([(bi.KNOP_SLAPEN, t("Slapen", "Sleep")), (bi.KNOP_SCHERM_UIT, t("Scherm uit", "Screen off")),
                              (bi.KNOP_NIETS, t("Niets", "Nothing"))])
        self.deksel.gekozen.connect(lambda w: op_achtergrond(self, lambda: bi.zet_deksel(w), lambda _u: None))
        self.deksel_rij = Rij("laptop", t("Als je de laptop dichtklapt", "When you close the laptop"), "", self.deksel)
        g.voeg(self.deksel_rij)

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.batterij(), bi.energieprofiel(), bi.scherm_uit_na(), bi.slaap_na(),
                                      bi.aanuit_knop(), bi.deksel(), bi.tijden_profiel()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        bat, profiel, scherm_uit, slaap, aanuit, deksel, *rest = uitkomst
        stand = rest[0] if rest else "AC"
        self.scherm_uit.zet(dichtstbij(bi.SCHERM_UIT_KEUZES, scherm_uit))
        self.slaap.zet(dichtstbij(bi.SLAAP_KEUZES, slaap))
        self.aanuit.zet(aanuit if aanuit in (bi.KNOP_VRAGEN, bi.KNOP_SLAPEN, bi.KNOP_UIT) else bi.KNOP_VRAGEN)
        self.deksel.zet(deksel if deksel in (bi.KNOP_SLAPEN, bi.KNOP_SCHERM_UIT, bi.KNOP_NIETS) else bi.KNOP_SLAPEN)
        self.deksel_rij.setVisible(bat is not None)
        # Een laptop heeft aparte tijden aan de lader en op de accu; we veranderen alleen die van nu (U454).
        uitleg = t("Even met de muis bewegen en het is terug", "Move the mouse and it is back")
        if bat is not None:
            op_accu = stand == "Battery"   # zoals de tijden echt geschreven worden (U462)
            uitleg += " · " + (t("deze tijden gelden nu op de accu", "these times apply on battery now") if op_accu else
                               t("deze tijden gelden nu aan de lader", "these times apply on the charger now"))
        self.scherm_rij.zet_uitleg(uitleg)
        # Ook slapen verschilt per stand: daar dezelfde zin (U483).
        slaap = t("Zuinig; alles staat er weer zodra je een toets indrukt",
                  "Saves power; everything is back as soon as you press a key")
        self.slaap_rij.zet_uitleg(slaap + uitleg[len(t("Even met de muis bewegen en het is terug",
                                                       "Move the mouse and it is back")):])
        self.batterij_kaart.setVisible(bat is not None)
        if bat is not None:
            staat = t("vol", "full") if bat.vol else t("wordt opgeladen", "charging") if bat.laadt else \
                t("aan de lader, laadt niet", "plugged in, not charging") if bat.aan_lader else t("op batterij", "on battery")
            self.batterij.zet_uitleg(f"{bat.procent}% · {staat}")
        self.profiel_rij.setVisible(profiel is not None)
        self.geen_profiel.setVisible(profiel is None)
        if profiel in self.profielen:
            self.profielen[profiel].setChecked(True)

    def zet_profiel(self, profiel: str) -> None:
        # Daarna opnieuw lezen: lukte het niet, dan staat de keuze weer op wat echt aan staat (U156).
        op_achtergrond(self, lambda: bi.zet_energieprofiel(profiel), lambda ok: (self.ververs(), self.melding.toon(
            t(f"Je computer werkt nu: {PROFIEL_TEKST[profiel][0][0].lower()}.",
              f"Your computer now works: {PROFIEL_TEKST[profiel][0][1].lower()}.") if ok else
            t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout")))


# ============================================================= uiterlijk ===

class UiterlijkPagina(Schakelaars, Blad):
    sleutel, icoon = "uiterlijk", "palet"
    titel_nl, titel_en = "Uiterlijk", "Appearance"
    uitleg_nl = "Licht of donker, de achtergrond van je bureaublad, en de taakbalk."
    uitleg_en = "Light or dark, your desktop background, and the taskbar."
    zoekwoorden = ("uiterlijk licht donker thema kleur achtergrond bureaublad foto wallpaper taakbalk startmenu snelmenu "
                   "appearance light dark theme dark mode color colour background desktop wallpaper picture taskbar "
                   "start menu quick menu")
    kde = "kcm_colors"

    def bouw(self) -> None:
        self.lay.addWidget(sectie(t("Licht of donker", "Light or dark")))
        rij = QHBoxLayout()
        rij.setSpacing(12)
        groep = QButtonGroup(self)
        self.thema: dict[bool, KeuzeKaart] = {}
        for donker, (nl, en), (unl, uen) in ((False, ("Licht", "Light"), ("Fris en helder", "Fresh and bright")),
                                             (True, ("Donker", "Dark"), ("Rustig voor je ogen", "Calm for your eyes"))):
            kaart = keuze_kaart("maan" if donker else "zon", t(nl, en), t(unl, uen))
            kaart.setMinimumWidth(220)
            kaart.clicked.connect(lambda _c=False, d=donker: self.zet_thema(d))
            groep.addButton(kaart)
            self.thema[donker] = kaart
            rij.addWidget(kaart, 1)
        rij.addStretch(1)
        self.lay.addLayout(rij)
        self.lay.addWidget(sectie(t("Achtergrond", "Background")))
        plaatjes = QHBoxLayout()
        plaatjes.setSpacing(12)
        groep2 = QButtonGroup(self)
        for naam, pad in bi.bugos_achtergronden():
            k = QPushButton()
            k.setObjectName("plaatje")
            k.setCheckable(True)
            k.setCursor(Qt.CursorShape.PointingHandCursor)
            k.setToolTip(naam)
            k.setAccessibleName(naam)   # een schermlezer hoort welke achtergrond het is
            # Het pakket (licht en donker): laat zijn eigen voorbeeldplaatje zien.
            beeld = QPixmap(str(Path(pad) / "contents" / "screenshot.jpg") if Path(pad).is_dir() else pad)
            if not beeld.isNull():
                k.setIcon(beeld.scaled(QSize(320, 180), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                       Qt.TransformationMode.SmoothTransformation))
                k.setIconSize(QSize(176, 99))
            k.clicked.connect(lambda _c=False, p=pad: self.zet_achtergrond(p))
            groep2.addButton(k)
            plaatjes.addWidget(k)
        eigen = Knop(t("Eigen foto kiezen…", "Choose your own photo…"), "gewoon", "lijn:foto")
        eigen.clicked.connect(self.kies_foto)
        plaatjes.addWidget(eigen, 0, Qt.AlignmentFlag.AlignVCenter)
        plaatjes.addStretch(1)
        self.lay.addLayout(plaatjes)
        g = self.kaart(t("Taakbalk", "Taskbar"))
        for onderdeel, ic, (nl, en), (unl, uen) in (
                ("startmenu", "apps", ("BugOS-startmenu", "BugOS start menu"),
                 ("De Windows-toets of Alt+F1 opent het. Uit: het eenvoudige menu van KDE.",
                  "The Windows key or Alt+F1 opens it. Off: KDE's plain menu.")),
                ("snelmenu", "schakelaar", ("Snelmenu op de taakbalk", "Quick menu on the taskbar"),
                 ("Grote knoppen voor wifi, bluetooth, game-modus, donker, niet storen en geluid.",
                  "Big buttons for Wi-Fi, Bluetooth, game mode, dark, do not disturb and sound."))):   # (U476)
            g.voeg(Rij(ic, t(nl, en), t(unl, uen), self.schakel("bugos-panel", onderdeel)))

    def ververs(self) -> None:
        op_achtergrond(self, bi.donker, lambda d: self.thema[bool(d)].setChecked(True))
        self.ververs_schakels()

    def zet_thema(self, donker: bool) -> None:
        def klaar(ok) -> None:
            if ok:
                self.melding.toon(t("Klaar. Open programma's krijgen de nieuwe kleuren als je ze opnieuw opent.",
                                    "Done. Open programs get the new colors when you open them again."), "goed")
            else:   # niet 'Klaar' zeggen als het niet lukte; de knoppen weer zoals het echt is (U336)
                self.melding.toon(t("Dat lukte niet. Probeer het nog eens.", "That did not work. Try again."), "fout")
                self.ververs()
        op_achtergrond(self, lambda: bi.zet_donker(donker), klaar)

    def zet_achtergrond(self, pad: str) -> None:
        op_achtergrond(self, lambda: bi.zet_achtergrond(pad), lambda ok: self.melding.toon(
            t("Je achtergrond is veranderd.", "Your background has changed.") if ok else
            t("Dat lukte niet.", "That did not work."), "goed" if ok else "fout"))

    def kies_foto(self) -> None:
        # De echte map Afbeeldingen (ook als je later een andere taal koos) (U114).
        from bugos_files_plekken import xdg_map
        map_ = xdg_map("PICTURES", "Pictures")
        pad, _ = QFileDialog.getOpenFileName(self, t("Kies een foto", "Choose a photo"),
                                             str(map_ if map_.exists() else Path.home()),
                                             t("Foto's (*.jpg *.jpeg *.png *.webp)", "Photos (*.jpg *.jpeg *.png *.webp)"))
        if pad:
            self.zet_achtergrond(pad)
