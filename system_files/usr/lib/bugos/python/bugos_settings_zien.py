"""BugOS Instellingen: de pagina's Makkelijker zien, en Muis en touchpad."""

from __future__ import annotations

import bugos_config as bi
from bugos_ui import Groep, Knop, Rij, sectie, t
from bugos_settings_onderdelen import Blad, Regelaar, op_achtergrond, schuifje
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


# ======================================================= makkelijker zien ===

class ZienPagina(Blad):
    sleutel, icoon = "zien", "oog"
    titel_nl, titel_en = "Makkelijker zien", "Easier to see"
    uitleg_nl = "Grotere letters, een grotere muisaanwijzer en een vergrootglas."
    uitleg_en = "Bigger letters, a bigger mouse pointer and a magnifier."
    zoekwoorden = ("lettergrootte tekstgrootte vergroten contrast zien ogen bril slecht groot grote letters tekst lettertype muisaanwijzer cursor vergrootglas "
                   "inzoomen zoom toegankelijkheid plaktoetsen langzame toetsen schermlezer voorlezen easier to see "
                   "accessibility eyes vision big large text letters font size mouse pointer cursor magnifier zoom "
                   "sticky keys slow keys screen reader read aloud orca")
    kde = "kcm_access"

    def bouw(self) -> None:
        g = self.kaart()
        self.tekst = schuifje(False, lambda aan: self.zet(bi.zet_grote_tekst, aan, t(
            "Klaar. Programma's die al open staan, krijgen de nieuwe letters als je ze opnieuw opent.",
            "Done. Programs that are already open get the new letters when you open them again.")))
        g.voeg(Rij("letter", t("Grote letters", "Big letters"),
                   t("In menu's, knoppen en vensters", "In menus, buttons and windows"), self.tekst))
        self.aanwijzer = schuifje(False, lambda aan: self.zet(bi.zet_grote_aanwijzer, aan))
        g.voeg(Rij("muis", t("Grote muisaanwijzer", "Big mouse pointer"), t("Twee keer zo groot", "Twice as big"),
                   self.aanwijzer))
        self.schud = schuifje(True, lambda aan: self.zet(bi.zet_schud_aanwijzer, aan))
        g.voeg(Rij("zoek", t("Muisaanwijzer kwijt? Schud de muis", "Lost the pointer? Shake the mouse"),
                   t("Dan wordt hij even groot, zodat je hem terugvindt", "It grows for a moment so you can find it"),
                   self.schud))
        g2 = self.kaart(t("Vergrootglas", "Magnifier"))
        knoppen = QWidget()
        kl = QHBoxLayout(knoppen)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(8)
        for tekst, stap in ((t("Dichterbij", "Closer"), 1), (t("Verder weg", "Further"), -1), (t("Gewoon", "Normal"), 0)):
            k = Knop(tekst, "gewoon")
            k.clicked.connect(lambda _c=False, s=stap: self.zoom(s))
            kl.addWidget(k)
        g2.voeg(Rij("oog", t("Het hele scherm dichterbij halen", "Bring the whole screen closer"),
                    t("Of houd de Windows-toets ingedrukt en druk op + of −",
                      "Or hold the Windows key and press + or −"), knoppen))
        g3 = self.kaart(t("Toetsenbord en voorlezen", "Keyboard and reading aloud"))
        self.plak = schuifje(False, lambda aan: self.zet(lambda a: bi.zet_toetshulp("plaktoetsen", a), aan))
        g3.voeg(Rij("toetsenbord", t("Plaktoetsen", "Sticky keys"),
                    t("Toetsen na elkaar in plaats van tegelijk: eerst Ctrl, dan C",
                      "Keys one after the other instead of together: first Ctrl, then C"), self.plak))
        self.langzaam = schuifje(False, lambda aan: self.zet(lambda a: bi.zet_toetshulp("langzame_toetsen", a), aan))
        g3.voeg(Rij("klok", t("Langzame toetsen", "Slow keys"),
                    t("Een toets telt pas als je hem even vasthoudt, tegen per ongeluk drukken",
                      "A key only counts when you hold it a moment, against accidental presses"), self.langzaam))
        self.lezer = schuifje(False, lambda aan: self.zet(lambda a: bi.zet_toetshulp("schermlezer", a), aan))
        self.lezer_rij = Rij("geluid", t("Schermlezer", "Screen reader"),
                             t("Leest voor wat op het scherm staat", "Reads aloud what is on the screen"), self.lezer)
        g3.voeg(self.lezer_rij)

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.grote_tekst(), bi.grote_aanwijzer(), bi.schud_aanwijzer(),
                                      bi.toetshulp("plaktoetsen"), bi.toetshulp("langzame_toetsen"),
                                      bi.toetshulp("schermlezer"), bi.kan_schermlezer()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        tekst, aanwijzer, schud, plak, langzaam, lezer, kan_lezer = uitkomst
        for schuif, aan in ((self.tekst, tekst), (self.aanwijzer, aanwijzer), (self.schud, schud), (self.plak, plak),
                            (self.langzaam, langzaam), (self.lezer, lezer)):
            schuif.zet_stil(bool(aan))
        self.lezer_rij.setVisible(bool(kan_lezer))

    def zet(self, werk, aan: bool, tekst: str = "") -> None:
        op_achtergrond(self, lambda: werk(aan), lambda _u: self.melding.toon(tekst, "goed") if tekst else None)

    def zoom(self, stap: int) -> None:
        op_achtergrond(self, lambda: bi.vergrootglas(stap), lambda ok: None if ok else self.melding.toon(
            t("Dat lukte niet.", "That did not work."), "fout"))


# ======================================================== muis en touchpad ===

class MuisPagina(Blad):
    sleutel, icoon = "muis", "muis"
    titel_nl, titel_en = "Muis en touchpad", "Mouse and touchpad"
    uitleg_nl = "Hoe snel de aanwijzer beweegt, en wat klikken en scrollen doen."
    uitleg_en = "How fast the pointer moves, and what clicking and scrolling do."
    zoekwoorden = ("dubbelklikken dubbelklik muis touchpad aanwijzer cursor snelheid linkshandig scrollen scrollrichting tikken klikken "
                   "dubbelklik mouse touchpad trackpad pointer cursor speed left-handed left handed scrolling "
                   "scroll direction natural scrolling tap click double click")
    kde = "kcm_mouse"

    def bouw(self) -> None:
        self.vak = QWidget()
        self.vak_lay = QVBoxLayout(self.vak)
        self.vak_lay.setContentsMargins(0, 0, 0, 0)
        self.vak_lay.setSpacing(14)
        self.lay.addWidget(self.vak)
        g = self.kaart(t("Klikken", "Clicking"))
        self.dubbel = schuifje(True, lambda aan: op_achtergrond(self, lambda: bi.zet_dubbelklik(aan), lambda _u: None))
        g.voeg(Rij("vink", t("Dubbelklikken om te openen", "Double-click to open"),
                   t("Zoals in Windows. Uit: één klik opent een bestand of map.",
                     "Like in Windows. Off: one click opens a file or folder."), self.dubbel))

    def ververs(self) -> None:
        op_achtergrond(self, lambda: (bi.aanwijzers(), bi.dubbelklik()), self.toon)

    def toon(self, uitkomst) -> None:
        if not uitkomst:
            return
        apparaten, dubbel = uitkomst
        self.dubbel.zet_stil(bool(dubbel))
        while self.vak_lay.count():
            item = self.vak_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for a in apparaten:
            self.vak_lay.addWidget(sectie(a.naam))
            g = Groep()
            g.lay.setContentsMargins(4, 4, 4, 4)
            self.vak_lay.addWidget(g)
            if a.touchpad and "aan" in a.kan:
                g.voeg(Rij("schakelaar", t("Touchpad aan", "Touchpad on"), "",
                           schuifje(a.aan, lambda aan, x=a: self.zet(x, "aan", aan))))
            if "snelheid" in a.kan:
                r = Regelaar(a.snelheid)
                r.veranderd.connect(lambda w, x=a: self.zet(x, "snelheid", w))
                g.voeg(Rij("muis", t("Snelheid van de aanwijzer", "Pointer speed"), "", r))
            if a.touchpad and "tikken" in a.kan:
                g.voeg(Rij("vink", t("Tikken om te klikken", "Tap to click"),
                           t("Een tikje op het touchpad is een klik", "A tap on the touchpad is a click"),
                           schuifje(a.tikken, lambda aan, x=a: self.zet(x, "tikken", aan))))
            if "natuurlijk" in a.kan:
                g.voeg(Rij("onder", t("Scrollen zoals op een telefoon", "Scroll like on a phone"),
                           # Zoals op een telefoon: omhoog vegen schuift de pagina omhoog, je gaat verder naar beneden (U160).
                           t("Veeg omhoog om verder naar beneden te gaan", "Swipe up to go further down") if a.touchpad else
                           t("Wieltje naar je toe gaat omhoog", "Wheel towards you goes up"),
                           schuifje(a.natuurlijk, lambda aan, x=a: self.zet(x, "natuurlijk", aan))))
            if "linkshandig" in a.kan:
                g.voeg(Rij("links", t("Linkshandig", "Left-handed"),
                           t("Linker- en rechterknop omgewisseld", "Left and right buttons swapped"),
                           schuifje(a.linkshandig, lambda aan, x=a: self.zet(x, "linkshandig", aan))))
        if not apparaten:
            g = Groep()
            g.lay.setContentsMargins(4, 4, 4, 4)
            g.voeg(Rij("muis", t("Geen muis of touchpad gevonden", "No mouse or touchpad found"),
                       t("Sluit een muis aan; BugOS ziet hem vanzelf.", "Connect a mouse; BugOS sees it by itself.")))
            self.vak_lay.addWidget(g)

    def zet(self, a: bi.Aanwijzer, wat: str, waarde) -> None:
        def klaar(ok) -> None:
            if not ok:   # de schakelaar terug zoals het echt is (U350)
                self.melding.toon(t("Dat lukte niet.", "That did not work."), "fout")
                self.ververs()
        op_achtergrond(self, lambda: bi.zet_aanwijzer(a.sysnaam, wat, waarde), klaar)
