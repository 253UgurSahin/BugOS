"""BugOS Bestanden: wat je met je bestanden doet.

Jip-en-Janneke: het menu onder de rechtermuisknop, kopiëren en plakken (ook met
het klembord van KDE), naam wijzigen, een nieuwe map, weggooien met Ongedaan maken,
en de prullenbak (terugzetten, leegmaken). Dit is een stukje van het venster
(Bestanden in bugos_files_venster.py erft het).
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

from bugos_ui import lijn_icoon, start, t
from bugos_ui import vraag_ja as _vraag_ja, vraag_tekst as _vraag_tekst
from bugos_shell import VraagDialoog
from bugos_desktop import app_mappen, lees_bureaublad, vertaald
from bugos_drives import mooie_maat
from bugos_files_plekken import INFO_ROL, PAD_ROL, VERBERG_EXT, thuis, toon_naam
from bugos_files_acties import (  # noqa: I001
    NAAM_FOUTEN, RECHTEN_FOUTEN, Klus, Weggooien, achter_uitleg, naar_prullenbak, op_losse_schijf, prullenbak_legen, terugzetten, vrije_naam,
    zelfde_schijf,
)
from PySide6.QtCore import QEvent, QMimeData, QMimeDatabase, QModelIndex, QPoint, Qt, QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMenu


# Bestanden die BugOS zelf opent, met een eigen helper (D-01). De standaardweg (QDesktopServices -> kde-open -> KIO)
# weigert elk "uitvoerbaar" bestand: "Vanwege veiligheidsredenen is het starten van uitvoerbare bestanden niet
# toegestaan in deze context", ook al is bugos-exe.desktop de standaard-app voor .exe. bugos-exe en bugos-package
# voeren zelf niets blind uit: ze vragen eerst (Winkel-versie, doosje, Wine) en leggen uit als het niet lukt.
# Op de extensie (hoofdletters tellen niet), want zo herkent ook de gebruiker een installatiebestand.
# Wat je met de rechtermuisknop 'Openen in quarantaine' kunt (bugos-quarantaine).
QUARANTAINE_SOORTEN = (".exe", ".msi", ".appimage", ".desktop")


def in_quarantaine_kan(pad: Path) -> bool:
    """Een programma dat je in quarantaine kunt proberen: een Windows-programma, een AppImage, een starter (.desktop)
    of een uitvoerbaar bestand. Geen mappen en geen gewone documenten."""
    import os
    import shutil
    if not shutil.which("bugos-quarantaine") or not pad.is_file():
        return False
    if pad.suffix.lower() in QUARANTAINE_SOORTEN:
        return True
    # Uitvoerbaar is niet genoeg: op een USB-stick (FAT, exFAT) is elk bestand 'uitvoerbaar'. Alleen een echt
    # programma (ELF) of een script (#!).
    if not os.access(pad, os.X_OK):
        return False
    try:
        with open(pad, "rb") as f:
            begin = f.read(4)
    except OSError:
        return False
    return begin == b"\x7fELF" or begin[:2] == b"#!"


EIGEN_OPENER = {".exe": "bugos-exe", ".msi": "bugos-exe", ".deb": "bugos-package", ".rpm": "bugos-package"}
# Hun .desktop-bestanden zijn NoDisplay (niet in het startmenu), maar horen wel in 'Openen met' (D-01).
EIGEN_APPS = {"bugos-exe.desktop", "bugos-package.desktop"}


def eigen_opener(pad: Path) -> str | None:
    """Het BugOS-programma dat dit bestand zelf opent (bugos-exe of bugos-package), of None: dan de gewone weg."""
    return EIGEN_OPENER.get(pad.suffix.lower())


def openen_met_apps(pad: Path, hoogstens: int = 12) -> list[tuple[str, str]]:
    """(naam, pad van het .desktop-bestand) van de apps die dit soort bestand kunnen openen, voor 'Openen met'.

    Uit de mimeinfo.cache van elke map met apps (die KDE en Flatpak bijhouden): per soort bestand (text/plain,
    image/png ...) welke apps het kunnen. Ook de 'ouders' van de soort tellen (een .py is ook text/plain), zoals
    de bestandsbeheerder van KDE. Verborgen apps (NoDisplay) niet. Elke app één keer, op naam."""
    soort = QMimeDatabase().mimeTypeForFile(str(pad))
    soorten = [soort.name()] + list(soort.allAncestors())
    mappen = app_mappen()
    gevonden: dict[str, None] = {}   # desktop-id's in volgorde (een dict onthoudt de volgorde, zonder dubbele)
    for map_ in mappen:
        try:
            regels = (map_ / "mimeinfo.cache").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        cache: dict[str, list[str]] = {}
        for regel in regels:
            if "=" in regel and not regel.startswith("["):
                sleutel, waarde = regel.split("=", 1)
                cache[sleutel.strip()] = [x for x in waarde.split(";") if x]
        for s in soorten:
            for desktop_id in cache.get(s, []):
                gevonden.setdefault(desktop_id, None)
    uit: dict[str, tuple[str, str]] = {}
    for desktop_id in gevonden:
        bestand = next((m / desktop_id for m in mappen if (m / desktop_id).is_file()), None)
        c = lees_bureaublad(bestand) if bestand is not None else None
        if c is None:
            continue
        s = c["Desktop Entry"]
        # Verborgen apps niet, behalve die van BugOS zelf voor .exe/.msi/.deb/.rpm (die zijn alleen in het startmenu
        # verborgen) (D-01).
        verborgen = s.get("NoDisplay", "false").lower() == "true" and desktop_id not in EIGEN_APPS
        if verborgen or s.get("Hidden", "false").lower() == "true":
            continue
        naam = vertaald(s, "Name") or desktop_id.removesuffix(".desktop")
        uit.setdefault(naam.lower(), (naam, str(bestand)))
    return sorted(uit.values(), key=lambda x: x[0].lower())[:hoogstens]


class Bewerken:
    """Menu, kopiëren en plakken, weggooien en de prullenbak: een stukje van het venster Bestanden."""

    # ----------------------------------------------------------- menu
    def _rechts_geklikt(self, waar, punt) -> None:
        """De rechtermuisknop is losgelaten (RechtsKlik): het menu van de tegel eronder, of van de map zelf."""
        if self.in_computer:
            return   # Deze computer heeft eigen knoppen en menu's per schijf
        if waar is self.leeg:
            # Een lege map (of 'niks gevonden'): er staan geen tegels, dus het menu van de map zelf.
            self.menu(None, globaal=self.leeg.mapToGlobal(punt))
        else:
            self.menu(punt)

    def maak_menu(self, punt, toetsenbord: bool = False) -> QMenu:
        """Het menu onder de rechtermuisknop, zoals in de Verkenner van Windows (C-01). Dezelfde acties als de
        knoppenbalk onderin en de knoppen bovenin: niets dat alleen hier kan.

          op een tegel:  Openen, Openen met ▸, Knippen, Kopiëren, Naam wijzigen, Weggooien, Eigenschappen
          op leeg vlak:  Nieuwe map, Nieuw tekstbestand, Plakken (als er iets gekopieerd is), Sorteren op ▸
          prullenbak:    Zet terug, Prullenbak leegmaken

        punt: in de coördinaten van de tegels (viewport), of None (een lege map). toetsenbord: geopend met de
        Menu-toets: dan geldt wat er gekozen is, ook als het punt niet op een tegel valt."""
        m = QMenu(self)

        def actie(ic: str, tekst: str, doe, aan: bool = True):
            a = m.addAction(lijn_icoon(ic, "tekst", 18, gekozen=None), tekst)
            a.triggered.connect(lambda _c=False, f=doe: f())
            a.setEnabled(aan)
            return a

        index = self.lijst.indexAt(punt) if punt is not None and self.stapel.currentWidget() is self.lijst \
            else QModelIndex()
        sel = self.lijst.selectionModel()
        if index.isValid() and sel is not None and not sel.isSelected(index):
            # Rechts op een tegel die niet gekozen was: alleen die (zoals Windows), niet ook de vorige keuze.
            self.lijst.setCurrentIndex(index)
        if index.isValid() or (toetsenbord and punt is not None):
            gekozen = self.gekozen()
        else:
            gekozen = []
            if sel is not None:
                sel.clearSelection()   # rechts op het lege vlak: het menu gaat over de map, niet over de keuze
        if self.in_prullenbak:
            actie("terug", t("Zet terug", "Restore"), self.zet_terug, bool(gekozen))
            m.addSeparator()
            actie("prullenbak", t("Prullenbak leegmaken", "Empty trash"), self.leegmaken,
                  self.bak_model.rowCount() > 0)
        elif gekozen:
            actie("openen", t("Openen", "Open"), self.openen)
            if len(gekozen) == 1 and gekozen[0].is_file():
                # Openen met: de apps die dit soort bestand kunnen openen (uit hun .desktop-bestand).
                apps = openen_met_apps(gekozen[0])
                sub = m.addMenu(lijn_icoon("apps", "tekst", 18, gekozen=None), t("Openen met", "Open with"))
                for naam, bestand in apps:
                    a = sub.addAction(naam)
                    a.triggered.connect(lambda _c=False, b=bestand, p=gekozen[0]: self.open_met(b, p))
                if not apps:
                    geen = sub.addAction(t("Geen andere app gevonden", "No other app found"))
                    geen.setEnabled(False)
                # Een programma (Windows-programma, AppImage, starter of uitvoerbaar bestand) eerst veilig proberen:
                # in quarantaine kan het niet bij je bestanden (bugos-quarantaine).
                if in_quarantaine_kan(gekozen[0]):
                    actie("slot", t("Openen in quarantaine", "Open in quarantine"),
                          lambda p=gekozen[0]: start("bugos-quarantaine", "--venster", str(p)))
            m.addSeparator()
            actie("schaar", t("Knippen", "Cut"), self.knip)
            actie("kopieer", t("Kopiëren", "Copy"), self.kopieer)
            actie("potlood", t("Naam wijzigen", "Rename"), self.hernoem, len(gekozen) == 1)
            m.addSeparator()
            # Hetzelfde woord als de knop in de balk onderin (D-15). 'Weggooien' klopt ook op een USB-stick, waar
            # het niet naar de prullenbak gaat (dan vraagt BugOS het eerst).
            actie("prullenbak", t("Weggooien", "Delete"), self.weggooien)
            m.addSeparator()
            actie("meer", t("Eigenschappen", "Properties"), self.eigenschappen, len(gekozen) == 1)
        else:
            actie("map-plus", t("Nieuwe map", "New folder"), self.nieuwe_map)
            actie("document", t("Nieuw tekstbestand", "New text file"), self.nieuw_tekstbestand)
            if self.klembord_heeft_bestanden():   # alleen als er iets te plakken is (zoals de knop bovenin)
                m.addSeparator()
                actie("plak", t("Plakken", "Paste"), self.plak)
            m.addSeparator()
            sub = m.addMenu(lijn_icoon("onder", "tekst", 18, gekozen=None), t("Sorteren op", "Sort by"))
            for sleutel, tekst_ in (("naam", t("Naam", "Name")), ("datum", t("Gewijzigd", "Date modified")),
                                    ("grootte", t("Grootte", "Size")), ("soort", t("Soort", "Type"))):
                a = sub.addAction(tekst_)
                a.setCheckable(True)
                a.setChecked(self.sorteer.sleutel == sleutel)
                a.triggered.connect(lambda _c=False, s=sleutel: self.sorteer_op(s))
        return m

    def menu(self, punt, toetsenbord: bool = False, globaal: QPoint | None = None) -> None:
        if self.in_computer:
            return
        m = self.maak_menu(punt, toetsenbord)
        if globaal is None:
            globaal = self.lijst.viewport().mapToGlobal(punt if punt is not None else QPoint(0, 0))
        m.exec(globaal)
        self.focus_terug()

    def sorteer_op(self, sleutel: str) -> None:
        """Sorteren op naam, datum, grootte of soort (mappen blijven altijd vooraan, zoals in Windows)."""
        self.sorteer.zet_sleutel(sleutel)

    def open_met(self, bureaublad: str, pad: Path) -> None:
        """Open dit bestand met een andere app (uit 'Openen met'). gio start het .desktop-bestand met het bestand
        erbij, net zoals de Winkel apps start; zonder gio doet kioclient het."""
        import shutil
        # Via de gedeelde start() van BugOS (los op de achtergrond), zoals de rest van Bestanden.
        if shutil.which("gio"):
            gelukt = start("gio", "launch", bureaublad, str(pad))
        elif shutil.which("kioclient"):
            gelukt = start("kioclient", "exec", bureaublad, str(pad))
        else:
            gelukt = False
        if not gelukt:
            self.melding.toon(t("Openen met een andere app lukte niet.", "Could not open with another app."), "fout")

    def eigenschappen(self) -> None:
        """Eigenschappen van één bestand of map: soort, grootte, plek en wanneer het veranderd is, in gewone woorden.
        Een map tellen we niet helemaal (dat kan lang duren): dan hoeveel dingen erin staan."""
        paden = self.gekozen()
        if len(paden) != 1:
            return
        pad = paden[0]
        regels = [t(f"Plek: {pad.parent}", f"Location: {pad.parent}")]
        try:
            st = pad.stat()
        except OSError:
            st = None
        if pad.is_dir():
            try:
                n = sum(1 for _ in os.scandir(pad))
                regels.insert(0, t(f"Map met {n} {'ding' if n == 1 else 'dingen'}",
                                   f"Folder with {n} {'item' if n == 1 else 'items'}"))
            except OSError:
                regels.insert(0, t("Map", "Folder"))
        else:
            from PySide6.QtCore import QMimeDatabase
            soort = QMimeDatabase().mimeTypeForFile(str(pad)).comment() or pad.suffix.lstrip(".").upper()
            regels.insert(0, t(f"Soort: {soort}", f"Type: {soort}"))
            if st is not None:
                regels.insert(1, t(f"Grootte: {mooie_maat(st.st_size)}", f"Size: {mooie_maat(st.st_size)}"))
        if st is not None:
            from datetime import datetime
            wanneer = datetime.fromtimestamp(st.st_mtime).strftime("%d-%m-%Y %H:%M")
            regels.append(t(f"Gewijzigd: {wanneer}", f"Modified: {wanneer}"))
        d = VraagDialoog(self, pad.name, "\n".join(regels), t("Sluiten", "Close"))
        d.nee.hide()   # alleen kijken: één knop
        d.exec()
        self.focus_terug()

    def focus_terug(self) -> None:
        """Na een vraag of menu: de focus terug op de tegels (C-08). Anders zette Qt hem op het eerste wat het
        vond, de knop 'Thuis' in het pad, met een rode rand eromheen."""
        if self.in_computer:
            return
        doel = self.stapel.currentWidget()
        if doel is self.lijst or doel is self.leeg:
            # Een lege map heeft geen tegels: dan het lege vlak zelf (dat kan de focus hebben, zie venster).
            doel.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------- kopiëren en plakken
    def _naar_klembord(self, knip: bool) -> None:
        paden = self.gekozen()
        if not paden or self.in_prullenbak:
            return
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in paden])
        data.setData("application/x-kde-cutselection", b"1" if knip else b"0")
        regels = ["cut" if knip else "copy"] + [QUrl.fromLocalFile(str(p)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
                                              for p in paden]   # GTK leest spaties alleen als %20
        data.setData("x-special/gnome-copied-files", "\n".join(regels).encode())
        zet_op_klembord(data)
        n = len(paden)
        self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} {'geknipt' if knip else 'gekopieerd'}. Ga naar een map en kies Plakken.",
                            f"{n} {'item' if n == 1 else 'items'} {'cut' if knip else 'copied'}. Go to a folder and choose Paste."))

    def kopieer(self) -> None:
        self._naar_klembord(False)

    def knip(self) -> None:
        self._naar_klembord(True)

    def klembord_heeft_bestanden(self) -> bool:
        data = QApplication.clipboard().mimeData()
        # Alleen als er nog iets van bestaat: na knippen en plakken in een ander venster zijn de bestanden weg,
        # dan geen 'Plakken' meer dat niets doet (U120).
        return bool(data and data.hasUrls() and any(u.isLocalFile() and (Path(u.toLocalFile()).exists() or
                                                                          Path(u.toLocalFile()).is_symlink())
                                                    for u in data.urls()))

    def plak(self) -> None:
        if self.in_prullenbak or self.in_computer or not self.klembord_heeft_bestanden():
            return
        if self.klus and self.klus.isRunning():
            # Niet stil niets doen (U521).
            self.melding.toon(t("Even wachten: er loopt nog iets (kopiëren of weggooien).",
                                "One moment: something is still busy (copying or deleting)."), "let_op")
            return
        data = QApplication.clipboard().mimeData()
        bronnen = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile() and Path(u.toLocalFile()).exists()]
        knip = bytes(data.data("application/x-kde-cutselection")).strip() == b"1" or \
            bytes(data.data("x-special/gnome-copied-files")).startswith(b"cut")
        if not bronnen:
            return
        self._start_klus(bronnen, self.huidig, knip)

    def _start_klus(self, bronnen: list[Path], doelmap: Path, knip: bool, klembord: bool = True) -> None:
        """Kopiëren of verplaatsen op de achtergrond, met een melding per stap (klembord: het kwam van Plakken)."""
        self.klus = Klus(bronnen, doelmap, knip)
        klus = self.klus
        # Met een knop 'Stoppen': wat al klaar is blijft, wat half was wordt weggehaald (U104).
        # Alleen over 'de stick' praten als er een stick bij is (U121): tussen twee interne schijven gewoon 'opslaan'.
        met_stick = op_losse_schijf(doelmap) or any(op_losse_schijf(b) for b in bronnen)
        def stoppen() -> None:
            # Het bestand dat bezig is, moet nog even worden afgemaakt of weggehaald: zeg dat, anders trek je de stick eruit (U116).
            klus.stop()
            if klus.gestopt:
                self.melding.toon(t("Stoppen… Haal de stick er nog niet uit.", "Stopping… Do not unplug the stick yet.")
                                  if met_stick else t("Stoppen…", "Stopping…"), seconden=0)   # (U145)

        self.klus.voortgang.connect(lambda i, n: None if klus.gestopt else self.melding.toon(
            t(f"Bezig met {'verplaatsen' if knip else 'kopiëren'}: {i + 1} van {n}…", f"{'Moving' if knip else 'Copying'}: {i + 1} of {n}…"),
            knop=t("Stoppen", "Stop"), actie=stoppen, seconden=0))
        self.klus.wegschrijven.connect(lambda: self.melding.toon(
            t("Bezig met wegschrijven… Haal de stick er nog niet uit.", "Writing to the stick… Do not unplug it yet.")
            if met_stick else t("Bezig met opslaan…", "Saving…"), seconden=0))
        self.klus.klaar.connect(lambda gelukt, fout: self._klus_klaar(gelukt, fout, knip, klus.achter, klembord, klus))
        self.klus.start()

    # ---------------------------------------------- slepen en loslaten
    def slepen(self, e, waar) -> bool:
        """Iets uit een ander venster (of uit deze map) hierheen gesleept: kopiëren, met Shift verplaatsen.
        Laat je het op een map los, dan gaat het in die map. Geeft True als wij het afhandelen.
        Bij binnenkomen altijd aannemen (ook boven het bestand dat je sleept): Qt stuurt anders de rest van het slepen
        niet meer, en kon je een bestand nooit op een map in hetzelfde venster loslaten. Per beweging zeggen of het
        hier kan (U519)."""
        data = e.mimeData()
        if not data or not data.hasUrls() or self.in_prullenbak or self.in_computer:
            return False
        bronnen = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()]
        bronnen = [b for b in bronnen if b.exists() or b.is_symlink()]
        van_internet = not bronnen and any(not u.isLocalFile() for u in data.urls())
        if not bronnen and not van_internet:
            return False
        if e.type() == QEvent.Type.DragEnter:
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
            return True
        bezig = bool(self.klus and self.klus.isRunning())
        doelmap = self.huidig
        if waar is self.lijst.viewport():
            index = self.lijst.indexAt(e.position().toPoint())
            pad = Path(index.data(PAD_ROL)) if index.isValid() and index.data(PAD_ROL) else None
            if pad and pad.is_dir() and pad not in bronnen:
                doelmap = pad
        kan = not van_internet and not bezig and not all(b.parent == doelmap for b in bronnen)
        if e.type() == QEvent.Type.DragMove:
            if kan or van_internet or bezig:   # internet en 'bezig': loslaten mag, dan zeggen we waarom het niet kan
                e.setDropAction(Qt.DropAction.CopyAction)
                e.accept()
            else:
                e.ignore()   # staat er al: niets te doen
            return True
        # Loslaten
        if van_internet:
            # Een plaatje uit Firefox of een bijlage uit Thunderbird is (nog) geen bestand (U522).
            self.melding.toon(t("Dit komt van internet of uit een mail. Bewaar het eerst daar (rechtermuisknop > "
                                "Opslaan als), dan staat het in Downloads.",
                                "This comes from the internet or an e-mail. Save it there first (right-click > Save "
                                "as), then it is in Downloads."), "let_op")
            e.ignore()
            return True
        if bezig:
            self.melding.toon(t("Even wachten: er loopt nog iets (kopiëren of weggooien).",
                                "One moment: something is still busy (copying or deleting)."), "let_op")   # (U521)
            e.ignore()
            return True
        if not kan:
            e.ignore()
            return True
        knip = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._start_klus(bronnen, doelmap, knip, klembord=False)
        # Altijd 'kopiëren' terugzeggen: verplaatsen doen we zelf, het andere programma hoeft niets weg te gooien.
        e.setDropAction(Qt.DropAction.CopyAction)
        e.accept()
        return True

    def _klus_klaar(self, gelukt: int, fout: str, knip: bool, achter: list | None = None,
                    klembord: bool = True, klus=None) -> None:
        gestopt = bool(klus and klus.gestopt)
        hernoemd = klus.hernoemd if klus else 0
        if gestopt:
            self.melding.toon(t(f"Gestopt. {gelukt} {'ding' if gelukt == 1 else 'dingen'} {'verplaatst' if knip else 'gekopieerd'}; "
                                "wat half was, is weggehaald.",
                                f"Stopped. {gelukt} {'item' if gelukt == 1 else 'items'} {'moved' if knip else 'copied'}; "
                                "what was half done has been removed.") + (f" {fout}" if fout else ""), "let_op", seconden=0)
        elif fout:
            # Wilde je al sluiten (en liep je weg), dan blijft de fout staan tot je hem ziet.
            self.melding.toon(t(f"Niet alles lukte: {fout}", f"Not everything worked: {fout}"), "fout",
                              seconden=0 if self.sluit_na_klus else 12)
        elif achter:  # bijv. een naam met ':' op een USB-stick: de rest staat er wel
            self.melding.toon(achter_uitleg(achter, knip), "let_op", seconden=0)
        else:
            extra = t(f" {hernoemd} {'bestond' if hernoemd == 1 else 'bestonden'} hier al en {'kreeg' if hernoemd == 1 else 'kregen'} "
                      "(2) achter de naam.",
                      f" {hernoemd} already existed here and got (2) after the name.") if hernoemd else ""   # U106
            self.melding.toon(t(f"Klaar: {gelukt} {'ding' if gelukt == 1 else 'dingen'} {'verplaatst' if knip else 'gekopieerd'}.",
                                f"Done: {gelukt} {'item' if gelukt == 1 else 'items'} {'moved' if knip else 'copied'}.") + extra,
                              "let_op" if hernoemd else "goed", seconden=12 if hernoemd else 4)
        if knip and klembord and not gestopt:
            # Alleen ons eigen knippen wissen: kopieerde je intussen iets anders, dan blijft dat staan (U107).
            kb = QApplication.clipboard()
            if kb is not None and _ONS_KLEMBORD and (kb.ownsClipboard() or kb.mimeData() is _ONS_KLEMBORD[0]):
                kb.clear()
        if hasattr(self, "ververs_plak"):
            self.ververs_plak()   # na knippen en plakken: geen dode 'Plakken'-knop
        if self.sluit_na_klus:
            if fout or achter or gestopt:
                self.sluit_na_klus = False  # niet alles lukte: dat moet je kunnen lezen, dus het venster blijft open
            else:
                QTimer.singleShot(0, self.close)

    # ------------------------------------------------------------ vragen
    def vraag_tekst(self, titel: str, vraag: str, tekst: str, ok: str = "", kies_tot: int | None = None) -> str | None:
        """De gedeelde BugOS-vraag (bugos_ui.vraag_tekst). kies_tot: alleen het begin kiezen (de naam zonder .odt),
        zoals in Windows (U507). None als je annuleert."""
        antwoord = _vraag_tekst(self, titel, vraag, tekst, ok=ok or t("OK", "OK"), kies_tot=kies_tot)
        self.focus_terug()   # (C-08)
        return antwoord.strip() if antwoord is not None else None

    def naam_fout(self, e: OSError) -> str:
        """Waarom een naam niet kon, in gewone woorden (niet 'Invalid argument') (U508)."""
        if e.errno in NAAM_FOUTEN:
            if e.errno == errno.ENAMETOOLONG:
                return t("de naam is te lang", "the name is too long")
            return t("de naam heeft een teken dat deze schijf niet kent (zoals : ? * of \")",
                     "the name has a character this drive does not allow (like : ? * or \")")
        if e.errno in RECHTEN_FOUTEN:
            return t("je mag hier niets veranderen", "you may not change anything here")
        if e.errno == errno.ENOSPC:
            return t("de schijf is vol", "the drive is full")
        return e.strerror or t("er ging iets mis", "something went wrong")

    def vraag_ja(self, titel: str, tekst: str, ja: str) -> bool:
        """Iets dat je niet ongedaan maakt (wissen, de prullenbak legen): Enter uit gewoonte doet dan niets."""
        ja_ = _vraag_ja(self, titel, tekst, ja, enter_is_nee=True)
        self.focus_terug()   # (C-08)
        return ja_

    # ------------------------------------------- naam, map, weggooien
    def hernoem(self) -> None:
        paden = self.gekozen()
        if len(paden) != 1 or self.in_prullenbak:
            return
        oud = paden[0]
        verborgen_ext = not oud.is_dir() and toon_naam(oud.name, False) != oud.name
        nieuw = self.vraag_tekst(t("Naam wijzigen", "Rename"), t("Nieuwe naam:", "New name:"), oud.name,
                                 ok=t("Naam wijzigen", "Rename"), kies_tot=len(oud.stem) if oud.suffix and not oud.is_dir() else None)
        if not nieuw or nieuw == oud.name:
            return
        # De tegel laat 'Recept' zien zonder '.odt': typ je 'Taart', dan wordt het 'Taart.odt', niet een bestand
        # zonder soort (U507).
        # Eerst controleren, dan pas de extensie erbij: anders werd '..' het verborgen '...odt' (U515).
        if "/" in nieuw or nieuw.strip(".") == "":
            self.melding.toon(t("Een naam mag geen / bevatten en niet alleen uit punten bestaan.",
                                "A name cannot contain / or be only dots."), "fout")
            return
        # 'Taart v1.2' of 'Brief Dr. Jansen' hebben ook een punt, maar geen echte extensie: dan ook .odt erbij (U515).
        # Maar een echte andere extensie die je zelf typt (.html, .sh, .json) laten we staan (U527).
        nieuwe_ext = Path(nieuw).suffix
        echte_ext = bool(nieuwe_ext) and nieuwe_ext.lower() in VERBERG_EXT or \
            (1 < len(nieuwe_ext) <= 6 and nieuwe_ext[1:].isalnum() and not nieuwe_ext[1:].isdigit())
        if verborgen_ext and not echte_ext:
            nieuw += oud.suffix
            if nieuw == oud.name:
                return
        doel = oud.with_name(nieuw)
        # Op een USB-stick (FAT/exFAT) zijn Foto.JPG en Foto.jpg hetzelfde bestand: dan is het
        # alleen andere hoofdletters, en dat mag gewoon.
        try:
            alleen_hoofdletters = nieuw.lower() == oud.name.lower() and doel.exists() and oud.samefile(doel)
        except OSError:
            alleen_hoofdletters = False
        if (doel.exists() or doel.is_symlink()) and not alleen_hoofdletters:  # ook een kapotte snelkoppeling niet overschrijven
            self.melding.toon(t(f"Er staat al iets met de naam '{nieuw}'.", f"Something named '{nieuw}' already exists."), "fout")
            return
        try:
            oud.rename(doel)
        except OSError as e:
            reden = self.naam_fout(e)
            self.melding.toon(t(f"Naam wijzigen lukte niet: {reden}.", f"Rename failed: {reden}."), "fout")

    def nieuwe_map(self) -> None:
        if self.in_prullenbak or self.in_computer:
            return
        naam = self.vraag_tekst(t("Nieuwe map", "New folder"), t("Naam van de map:", "Folder name:"),
                                t("Nieuwe map", "New folder"), ok=t("Maken", "Make"))
        if not naam:
            return
        if "/" in naam or naam in (".", ".."):   # '.' maakte een map naast deze, '..' een verborgen map (U509)
            self.melding.toon(t("Een naam mag geen / bevatten en niet alleen uit punten bestaan.",
                                "A name cannot contain / or be only dots."), "fout")
            return
        doel = vrije_naam(self.huidig / naam)
        try:
            doel.mkdir()
            QTimer.singleShot(300, lambda: self.selecteer(doel))
        except OSError as e:
            reden = self.naam_fout(e)
            self.melding.toon(t(f"De map maken lukte niet: {reden}.", f"Could not make the folder: {reden}."), "fout")

    def nieuw_tekstbestand(self) -> None:
        """Een leeg tekstbestand, zoals Nieuw > Tekstdocument in Windows (C-02). Eerst de naam, met 'Nieuw
        tekstbestand' al gekozen (zonder .txt), zodat je meteen een eigen naam typt; Annuleren maakt niets. Typ je
        geen soort, dan komt er .txt achter (de tegel laat .txt niet zien). Bestaat de naam al, dan '(2)' erachter:
        nooit een bestaand bestand leegmaken."""
        if self.in_prullenbak or self.in_computer:
            return
        standaard = t("Nieuw tekstbestand", "New text file")
        naam = self.vraag_tekst(t("Nieuw tekstbestand", "New text file"), t("Naam van het bestand:", "File name:"),
                                f"{standaard}.txt", ok=t("Maken", "Make"), kies_tot=len(standaard))
        if not naam:
            return
        if "/" in naam or naam.strip(".") == "":
            self.melding.toon(t("Een naam mag geen / bevatten en niet alleen uit punten bestaan.",
                                "A name cannot contain / or be only dots."), "fout")
            return
        if not Path(naam).suffix:
            naam += ".txt"
        doel = vrije_naam(self.huidig / naam)
        try:
            # 'x': alleen maken als hij er nog niet is (ook als er intussen iets met die naam kwam).
            with open(doel, "x", encoding="utf-8"):
                pass
            QTimer.singleShot(300, lambda: self.selecteer(doel))
        except OSError as e:
            reden = self.naam_fout(e)
            self.melding.toon(t(f"Het bestand maken lukte niet: {reden}.", f"Could not make the file: {reden}."),
                              "fout")

    def weggooien(self) -> None:
        if self.in_prullenbak:
            return
        # Wat al weg is (twee keer snel op Delete), niet nog eens: anders leek het 'op een andere schijf' (U337).
        paden = [p for p in self.gekozen() if os.path.lexists(p)]
        if not paden:
            return
        ver = [p for p in paden if not zelfde_schijf(p, thuis())]
        if ver and self.klus and self.klus.isRunning():
            # Eerst kijken, dan pas vragen: anders zeg je 'Ja' en gebeurt er niets (U119).
            self.melding.toon(t("Even wachten: er loopt nog iets (kopiëren of weggooien).",
                                "One moment: something is still busy (copying or deleting)."), "let_op")
            return
        if ver:
            if not self.vraag_ja(t("Echt weggooien?", "Really delete?"),
                                 t("Dit staat op een USB-stick of een andere schijf. Weggooien kan daar niet ongedaan "
                                   "worden. Echt weggooien?",
                                   "This is on a USB stick or another drive. Deleting there cannot be undone. "
                                   "Really delete?"),
                                 t("Weggooien", "Delete")):
                return
        weg, fout = [], ""
        for p in paden:
            if p in ver:
                continue   # die gaan hieronder op de achtergrond
            try:
                weg.append(naar_prullenbak(p))
            except OSError as e:
                fout = e.strerror or str(e)
        self.laatst_weg = weg
        if ver:
            self.klus = Weggooien(ver)
            self.melding.toon(t("Bezig met weggooien…", "Deleting…"), seconden=0)
            self.klus.klaar.connect(lambda n, f, eerder=fout, bak=len(weg): self._weg_klaar(n, f or eerder, bak))
            self.klus.start()
            return
        if fout:
            self.melding.toon(t(f"Niet alles kon weg: {fout}", f"Not everything could be deleted: {fout}"), "fout")
        elif weg:
            n = len(weg)
            self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} naar de prullenbak.", f"{n} {'item' if n == 1 else 'items'} moved to the trash."),
                              knop=t("Ongedaan maken", "Undo"), actie=self.ongedaan, seconden=10)

    def _weg_klaar(self, n: int, fout: str, in_bak: int = 0) -> None:
        # Alleen verversen als je nog in dezelfde map bent (niet in Deze computer of de prullenbak), en dan zonder
        # je keuze, zoekterm en plek kwijt te raken: de lijst houdt de map zelf al in de gaten (U118).
        if fout:
            self.melding.toon(t(f"Niet alles kon weg: {fout}", f"Not everything could be deleted: {fout}"), "fout",
                              seconden=0 if self.sluit_na_klus else 12)
            self.sluit_na_klus = False
        elif in_bak:   # een deel ging naar de prullenbak: dat kan nog terug (U119)
            self.melding.toon(t(f"{n} weggegooid, {in_bak} naar de prullenbak.", f"{n} deleted, {in_bak} moved to the trash."),
                              knop=t("Ongedaan maken", "Undo"), actie=self.ongedaan, seconden=10)
        else:
            self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} weggegooid.", f"{n} {'item' if n == 1 else 'items'} deleted."), "goed")
        if not fout:
            if self.sluit_na_klus:
                QTimer.singleShot(0, self.close)

    def ongedaan(self) -> None:
        mislukt = 0
        for bestand, info in self.laatst_weg:
            try:
                terugzetten(bestand, info)
            except OSError:
                mislukt += 1
        self.laatst_weg = []
        if mislukt:
            self.melding.toon(t(f"{mislukt} {'ding kon' if mislukt == 1 else 'dingen konden'} niet terug. "
                                "Kijk in de prullenbak.",
                                f"{mislukt} {'item' if mislukt == 1 else 'items'} could not be restored. "
                                "Look in the trash."), "fout")
        else:
            self.melding.toon(t("Teruggezet.", "Restored."), "goed")

    # ------------------------------------------------------ prullenbak
    def zet_terug(self) -> None:
        if not self.in_prullenbak:
            return
        sel = [i for i in self.lijst.selectionModel().selectedIndexes() if i.column() == 0]   # (U506)
        n = mislukt = 0
        for i in sel:
            try:
                terugzetten(Path(i.data(PAD_ROL)), Path(i.data(INFO_ROL)))
                n += 1
            except OSError:
                mislukt += 1
        self.open_prullenbak(geschiedenis=False)
        if mislukt:
            self.melding.toon(t(f"{n} teruggezet, {mislukt} {'lukte' if mislukt == 1 else 'lukten'} niet "
                                "(is de plek waar het stond er nog, en mag je daar schrijven?).",
                                f"{n} restored, {mislukt} could not be restored "
                                "(does the original place still exist, and may you write there?)."), "fout")
        elif n:
            self.melding.toon(t(f"{n} {'ding' if n == 1 else 'dingen'} teruggezet.", f"{n} {'item' if n == 1 else 'items'} restored."), "goed")

    def leegmaken(self) -> None:
        if self.vraag_ja(t("Prullenbak leegmaken?", "Empty the trash?"),
                         t("Alles in de prullenbak wordt echt weggegooid. Dit kan niet ongedaan worden.",
                           "Everything in the trash will be deleted for good. This cannot be undone."),
                         t("Leegmaken", "Empty")):
            mislukt = prullenbak_legen()
            # Blijf waar je was (U077): ook vanaf 'Deze computer' > Ruimte maken, waar Terug anders verkeerd ging.
            if self.in_prullenbak:
                self.open_prullenbak(geschiedenis=False)
            elif self.in_computer:
                self.grootste_tijd = -1e9   # de prullenbak in 'Wat de meeste ruimte inneemt' opnieuw tellen
                self.vul_computer()
            if mislukt:
                self.melding.toon(t(f"{mislukt} {'ding kon' if mislukt == 1 else 'dingen konden'} niet weg. "
                                    "Ze staan nog in de prullenbak.",
                                    f"{mislukt} {'item' if mislukt == 1 else 'items'} could not be deleted. "
                                    "They are still in the trash."), "fout")
            else:
                self.melding.toon(t("De prullenbak is leeg.", "The trash is empty."), "goed")


_ONS_KLEMBORD: list[QMimeData] = []  # wat wij zelf op het klembord hebben gezet


def zet_op_klembord(data: QMimeData) -> None:
    _ONS_KLEMBORD[:] = [data]
    QApplication.clipboard().setMimeData(data)


def laat_klembord_los() -> None:
    """Wat wij op het klembord zetten, ruimen we zelf op voordat het programma stopt.

    Anders ruimt Qt het pas op als Python al weg is, en dan crasht het programma bij het
    afsluiten. De klembordbeheerder van KDE heeft het al bewaard, dus plakken kan daarna nog.
    """
    klembord = QApplication.clipboard()
    if klembord is None or not _ONS_KLEMBORD:
        return
    try:
        nog_van_ons = klembord.ownsClipboard() or klembord.mimeData() is _ONS_KLEMBORD[0]
    except RuntimeError:
        nog_van_ons = False
    _ONS_KLEMBORD.clear()
    if nog_van_ons:
        klembord.clear()
