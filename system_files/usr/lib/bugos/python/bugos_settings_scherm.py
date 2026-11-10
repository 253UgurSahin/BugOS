"""BugOS Instellingen: de pagina's Geluid, Scherm, Energie en Uiterlijk."""

from __future__ import annotations

from pathlib import Path

import bugos_config as bi
from bugos_ui import Chip, KeuzeKaart, Knop, Rij, label, leeg_groep, lijn_icoon, sectie, t
from bugos_settings_onderdelen import Blad, Keuzes, Regelaar, dichtstbij, op_achtergrond, schuifje
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


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
        # De microfoon kies je (nog) bij KDE: zeg waar, zodat zoeken op 'microfoon' ergens heen leidt (U166).
        self.lay.addWidget(label(t("De microfoon kies en zet je bij 'Meer instellingen (voor gevorderden)' hieronder.",
                                   "You choose and set the microphone under 'More settings (advanced)' below."),
                                 "klein"))

    def ververs(self) -> None:
        op_achtergrond(self, bi.geluid, self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        volume, stil, uitgangen = uitkomst
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


# ================================================================ scherm ===

class SchermPagina(Blad):
    sleutel, icoon = "scherm", "computer"
    titel_nl, titel_en = "Scherm", "Display"
    uitleg_nl = "Helderheid, warm licht voor de avond, en hoe groot alles is."
    uitleg_en = "Brightness, warm light for the evening, and how big everything is."
    zoekwoorden = ("scherm beeldscherm monitor helderheid nachtlicht nachtlampje groot groter klein schaal tekst "
                   "display screen monitor brightness night light night color blue light size bigger smaller scale "
                   "scaling text")
    kde = "kcm_kscreen"

    def bouw(self) -> None:
        g = self.kaart()
        self.helder = Regelaar(70)
        self.helder.veranderd.connect(lambda w: op_achtergrond(self, lambda: bi.zet_helderheid(w), lambda _u: None))
        self.helder_rij = Rij("zon", t("Helderheid", "Brightness"), "", self.helder)
        g.voeg(self.helder_rij)
        self.nacht = schuifje(False, lambda aan: op_achtergrond(self, lambda: bi.zet_nachtlicht(aan), lambda _u: None))
        g.voeg(Rij("maan", t("Nachtlicht", "Night light"),
                   t("'s Avonds warmer licht, prettiger voor je ogen", "Warmer light in the evening, easier on your eyes"),
                   self.nacht))
        g2 = self.kaart(t("Grootte", "Size"))
        self.grootte = Keuzes([(1.0, "100%"), (1.25, "125%"), (1.5, "150%"), (1.75, "175%"), (2.0, "200%")])
        self.grootte.gekozen.connect(self.zet_grootte)
        g2.voeg(Rij("computer", t("Alles groter of kleiner", "Make everything bigger or smaller"),
                    t("Tekst, knoppen en vensters", "Text, buttons and windows"), self.grootte))

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.helderheid(), bi.nachtlicht(), bi.schaal()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        helder, nacht, schaal = uitkomst
        self._schaal = schaal   # onthouden: bij een klik niet opnieuw kscreen-doctor vragen (dat houdt het venster op) (U407)
        self.helder_rij.setVisible(helder is not None)
        if helder is not None:
            self.helder.zet(helder)
        self.nacht.zet_stil(nacht)
        self.grootte.zet(min((1.0, 1.25, 1.5, 1.75, 2.0), key=lambda w: abs(w - schaal)))
        # Op een klein scherm (1366×768) is 200% maar 683×384: dan past niets meer, ook de knop terug niet. Alleen
        # groottes aanbieden waarbij minstens 1024×700 overblijft (de huidige blijft altijd te kiezen) (U397).
        for waarde, knop in self.grootte.knoppen.items():
            knop.setEnabled(waarde <= max(groot_genoeg(), schaal + 0.01))

    def zet_grootte(self, waarde: float) -> None:
        if waarde > max(groot_genoeg(), getattr(self, "_schaal", 1.0) + 0.01):   # (U397, U407)
            self.melding.toon(t("Dat is te groot voor dit scherm: dan past niets meer.",
                                "That is too big for this screen: nothing would fit any more."), "let_op")
            self.ververs()
            return
        self.melding.toon(t(f"Grootte {waarde:.0%} wordt ingesteld…", f"Setting size to {waarde:.0%}…"))
        op_achtergrond(self, lambda: bi.zet_schaal(waarde), lambda ok: (setattr(self, "_schaal", waarde) if ok else self.ververs(), self.melding.toon(
            t("Klaar. Sommige programma's worden pas groter als je ze opnieuw opent.",
              "Done. Some programs only change after you open them again.") if ok else
            t("Dat lukte niet. Probeer het bij 'Meer instellingen'.", "That did not work. Try 'More settings'."),
            "goed" if ok else "fout")))   # mislukt: opnieuw lezen, dan staat de echte grootte weer gekozen


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

class UiterlijkPagina(Blad):
    sleutel, icoon = "uiterlijk", "palet"
    titel_nl, titel_en = "Uiterlijk", "Appearance"
    uitleg_nl = "Licht of donker, en de achtergrond van je bureaublad."
    uitleg_en = "Light or dark, and your desktop background."
    zoekwoorden = ("uiterlijk licht donker thema kleur achtergrond bureaublad foto wallpaper appearance light dark "
                   "theme dark mode color colour background desktop wallpaper picture")
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

    def ververs(self) -> None:
        op_achtergrond(self, bi.donker, lambda d: self.thema[bool(d)].setChecked(True))

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
