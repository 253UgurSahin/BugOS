"""BugOS Bestanden: het venster zelf.

Jip-en-Janneke: hier wordt het venster opgebouwd (zijbalk, balk bovenin, tegels,
de knoppenbalk onderin en de sneltoetsen) en bijgehouden wat er te zien is.
Wat je in het venster kunt doen, staat in de andere bugos_files_*-stukjes:
navigeren, bewerken, Deze computer en schijven.
"""

from __future__ import annotations

from pathlib import Path

from bugos_ui import ActieBalk, Knop, Melding, Venster, Zijbalk, label, lijn_icoon, px, ronde_knop, t
from bugos_drives import Schijf, mooie_maat
from bugos_files_plekken import PAD_ROL, STOP, Telsein, bijzondere_mappen, schijf_van, thuis, vrije_ruimte
from bugos_files_acties import Klus
from bugos_files_tegels import Sorteerder, TegelTekenaar, Voorbeelden
from bugos_files_onderdelen import Zoekbalk, stijl
from bugos_files_navigeren import Navigeren
from bugos_files_bewerken import Bewerken, laat_klembord_los
from bugos_files_computer import Computer
from bugos_files_schijven import Schijven
from PySide6.QtCore import QDir, QEvent, QPoint, QRect, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileSystemModel, QFrame, QHBoxLayout, QLabel, QListView, QScrollArea, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)


# ================================================================ venster ===

class Bestanden(Navigeren, Bewerken, Computer, Schijven, Venster):
    def __init__(self, start: Path | None = None, kies: Path | None = None):
        rechts_w = QWidget()
        super().__init__(t("Bestanden", "Files"), inhoud=rechts_w, maat=(1120, 740), minimum=(940, 560))
        self.setStyleSheet(stijl())
        self.terug_lijst: list[Path] = []
        self.vooruit_lijst: list[Path] = []
        self.huidig = thuis()
        self.in_prullenbak = False
        self.klus: Klus | None = None
        self.sluit_na_klus = False
        self.laatst_weg: list[tuple[Path, Path]] = []
        self.in_computer = False                 # de pagina 'Deze computer' staat open
        self.lijst_schijven: list[Schijf] = []   # USB-sticks en andere schijven
        self.bezig: set[str] = set()             # schijven die nu open of dicht gaan
        self.ruimte: dict[str, int] | None = None  # hoe groot Afbeeldingen, Video's, ... zijn (geteld)
        self.ruimte_tijd = 0.0
        self.telsein = Telsein(self)
        self.telsein.klaar.connect(self._geteld)
        self.tellen_bezig = False

        # --- links: plekken, USB-sticks en de prullenbak (de zijbalk komt van de schil)
        self.zijbalk = self.nav
        self.zijbalk.itemClicked.connect(self.zijbalk_klik)
        self.zijbalk.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.zijbalk.customContextMenuRequested.connect(self.zijbalk_menu)
        self.bak_lijst = Zijbalk()
        self.bak_lijst.voeg_toe("lijn:prullenbak", t("Prullenbak", "Trash"), "prullenbak")
        self.bak_lijst.setFixedHeight(48)
        self.bak_lijst.itemClicked.connect(lambda _it: self.open_prullenbak())
        self.onder.addWidget(self.bak_lijst)

        # --- rechts: één compacte balk bovenin, een korte regel info, de tegels.
        # Zoals de Verkenner van Windows 11: waar je bent staat in het pad (kruimels),
        # niet nog een keer als grote titel eronder. Dat scheelt ruim 60 px hoogte.
        HOOGTE = 40   # knophoogte uit het ontwerp (MATEN in tools/design: knopHoogte = 40)
        rechts = QVBoxLayout(rechts_w)
        rechts.setContentsMargins(22, 14, 22, 12)
        rechts.setSpacing(8)
        balk = QHBoxLayout()
        balk.setSpacing(8)
        # Kleine ronde knopjes (36 px, zonder vlak tot je erover gaat): rustiger naast het pad.
        self.terug_knop = ronde_knop("links", t("Terug", "Back"), klein=True)
        self.vooruit_knop = ronde_knop("rechts", t("Vooruit", "Forward"), klein=True)
        self.terug_knop.clicked.connect(self.terug)
        self.vooruit_knop.clicked.connect(self.vooruit)
        balk.addWidget(self.terug_knop)
        balk.addWidget(self.vooruit_knop)
        self.pad_vak = QFrame()
        self.pad_vak.setObjectName("pad")
        self.pad_vak.setFixedHeight(HOOGTE)
        # De balk krijgt de ruimte die over is (niet wat het pad zou willen): bouw_pad maakt het pad passend (U272).
        self.pad_vak.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.pad_vak.setMinimumWidth(px(220))   # genoeg voor 'Thuis › … › map'
        self.pad_vak.installEventFilter(self)   # andere breedte: het pad opnieuw passend maken (U272)
        self.pad_lay = QHBoxLayout(self.pad_vak)
        self.pad_lay.setContentsMargins(8, 0, 8, 0)
        self.pad_lay.setSpacing(0)
        self.titel = label("", "kop3", wrap=False)
        balk.addWidget(self.pad_vak, 1)
        balk.addWidget(self.titel, 1)
        self.zoek = Zoekbalk(t("Zoek in deze map", "Search this folder"))
        self.zoek.setMinimumWidth(px(120))
        self.zoek.setMaximumWidth(240)
        self.zoek.setMinimumHeight(HOOGTE)
        self.zoek.setMaximumHeight(HOOGTE)
        self.zoek.textChanged.connect(self.zoeken)
        balk.addWidget(self.zoek)
        self.plak_knop = Knop(t("Plakken", "Paste"), "gewoon", "lijn:plak")
        self.plak_knop.setToolTip(t("Zet hier neer wat je hebt gekopieerd of geknipt", "Put what you copied or cut here"))
        self.plak_knop.clicked.connect(self.plak)
        self.nieuw_knop = Knop(t("Nieuwe map", "New folder"), "gewoon", "lijn:map-plus")
        self.nieuw_knop.clicked.connect(self.nieuwe_map)
        self.uitwerp_knop = Knop(t("Veilig verwijderen", "Safely remove"), "gewoon", "lijn:uitwerpen")
        self.uitwerp_knop.clicked.connect(self.uitwerpen_hier)
        self.leeg_knop = Knop(t("Prullenbak leegmaken", "Empty trash"), "gewoon", "lijn:prullenbak")
        self.leeg_knop.clicked.connect(self.leegmaken)
        for k in (self.plak_knop, self.nieuw_knop, self.uitwerp_knop, self.leeg_knop):
            k.setMinimumHeight(HOOGTE)
            k.setMaximumHeight(HOOGTE)
            k.setProperty("volle_tekst", k.text())
            k.setAccessibleName(k.text())   # ook zonder tekst (smal venster) een naam voor de schermlezer
            k.setToolTip(k.toolTip() or k.text())
            balk.addWidget(k)
        self.plak_knop.hide()
        rechts.addLayout(balk)

        # Eén korte regel onder de balk: "8 items · 1 gekozen · 11 GB vrij".
        # Vroeger stond hier eerst nog de naam van de map als grote titel; die stond
        # al in het pad (of, bij Prullenbak en Deze computer, in self.titel in de balk).
        self.status = label("", "sub", wrap=False)
        self.status.setContentsMargins(6, 0, 0, 0)
        rechts.addWidget(self.status)

        self.melding = Melding()
        rechts.addWidget(self.melding)

        # het model: de echte bestanden op de schijf
        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.verborgen = False
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.sorteer = Sorteerder()
        self.sorteer.setSourceModel(self.model)
        self.sorteer.setDynamicSortFilter(True)
        self.sorteer.sort(0)
        self.bak_model = QStandardItemModel(self)

        self.voorbeelden = Voorbeelden()
        self.lijst = QListView()
        self.lijst.setObjectName("tegels")
        self.lijst.setViewMode(QListView.ViewMode.IconMode)
        self.lijst.setResizeMode(QListView.ResizeMode.Adjust)
        self.lijst.setMovement(QListView.Movement.Static)
        self.lijst.setUniformItemSizes(True)
        self.lijst.setGridSize(TegelTekenaar.maat())
        self.lijst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lijst.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lijst.setDragEnabled(True)
        self.lijst.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.lijst.viewport().setAcceptDrops(True)  # loslaten vangen we zelf op (zie eventFilter)
        self.lijst.viewport().installEventFilter(self)
        self.lijst.setMouseTracking(True)
        self.lijst.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lijst.setItemDelegate(TegelTekenaar(self.voorbeelden, bijzondere_mappen()))
        self.lijst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lijst.customContextMenuRequested.connect(self.menu)
        self.lijst.activated.connect(self.openen)
        self.voorbeelden.bijgewerkt.connect(self.lijst.viewport().update)
        self.model.directoryLoaded.connect(lambda _p: self.ververs_staat())
        self.sorteer.rowsInserted.connect(lambda *_: self.ververs_staat())
        self.sorteer.rowsRemoved.connect(lambda *_: self.ververs_staat())
        self.sorteer.layoutChanged.connect(lambda *_: self.ververs_staat())

        self.leeg = QWidget()
        ll = QVBoxLayout(self.leeg)
        ll.addStretch(1)
        self.leeg_beeld = QLabel()
        self.leeg_beeld.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.leeg_kop = label("", "kop2")
        self.leeg_kop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.leeg_sub = label("", "sub")
        self.leeg_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self.leeg_beeld, self.leeg_kop, self.leeg_sub):
            ll.addWidget(w)
        self.leeg.setAcceptDrops(True)  # "Sleep er iets naartoe": dat moet dan ook werken
        self.leeg.installEventFilter(self)
        ll.addStretch(2)
        self.computer = QScrollArea()
        self.computer.setFrameShape(QFrame.Shape.NoFrame)
        self.computer.setWidgetResizable(True)
        self.computer.viewport().setAutoFillBackground(False)
        binnen = QWidget()
        binnen.setObjectName("computer_binnen")
        self.computer_lay = QVBoxLayout(binnen)
        self.computer_lay.setContentsMargins(4, 4, 4, 4)
        self.computer_lay.setSpacing(14)
        self.computer.setWidget(binnen)
        self.stapel = QStackedWidget()
        self.stapel.addWidget(self.lijst)
        self.stapel.addWidget(self.leeg)
        self.stapel.addWidget(self.computer)
        rechts.addWidget(self.stapel, 1)

        # zweeft onderin zodra je iets kiest
        self.keuzebalk = ActieBalk(self)
        self.keuzebalk.knop("openen", "openen", t("Openen", "Open"), self.openen)
        self.keuzebalk.knop("kopieer", "kopieer", t("Kopiëren", "Copy"), self.kopieer)
        self.keuzebalk.knop("knip", "schaar", t("Knippen", "Cut"), self.knip)
        self.keuzebalk.knop("naam", "potlood", t("Naam wijzigen", "Rename"), self.hernoem)
        self.keuzebalk.knop("weg", "prullenbak", t("Weggooien", "Delete"), self.weggooien)
        self.keuzebalk.knop("terugzetten", "terug", t("Zet terug", "Restore"), self.zet_terug)
        self.keuzebalk.klaar()
        self.keuzebalk.gesloten.connect(self.lijst.clearSelection)
        QApplication.clipboard().dataChanged.connect(self.ververs_plak)

        # sneltoetsen, net als in Windows
        for toets, actie in (
            (QKeySequence.StandardKey.Copy, self.kopieer), (QKeySequence.StandardKey.Cut, self.knip),
            (QKeySequence.StandardKey.Paste, self.plak), (QKeySequence.StandardKey.Delete, self.weggooien),
            (QKeySequence.StandardKey.Find, self.zoek.setFocus), (QKeySequence.StandardKey.Refresh, self.ververs),
            (QKeySequence("F2"), self.hernoem), (QKeySequence("Backspace"), self.terug),
            (QKeySequence("Alt+Left"), self.terug), (QKeySequence("Alt+Right"), self.vooruit),
            (QKeySequence("Alt+Up"), self.omhoog), (QKeySequence("Ctrl+Shift+N"), self.nieuwe_map),
            (QKeySequence("Ctrl+H"), self.wissel_verborgen),
        ):
            sc = QShortcut(QKeySequence(toets), self)
            sc.activated.connect(lambda f=actie: f())
        wis = QShortcut(QKeySequence("Escape"), self)
        wis.activated.connect(self.escape)

        self.vul_zijbalk()
        self.apparaten = QTimer(self)
        self.apparaten.timeout.connect(self.vul_zijbalk)
        self.apparaten.start(3000)
        self.ga_naar(start or thuis(), geschiedenis=False)
        if kies:
            QTimer.singleShot(400, lambda: self.selecteer(kies))

    # ----------------------------------------------------------- inhoud
    def ververs_staat(self) -> None:
        if self.in_computer:
            n = len(self.lijst_schijven)
            self.status.setText(t(f"{n} aangesloten", f"{n} connected") if n else
                                t("Niets aangesloten", "Nothing connected"))
            self.stapel.setCurrentWidget(self.computer)
            self.keuzebalk.toon(0)
            self.plaats_keuzebalk()
            return
        model = self.lijst.model()
        if model is None:
            return
        aantal = model.rowCount(self.lijst.rootIndex())
        gekozen = len(self.gekozen())
        if aantal == 0:
            if self.in_prullenbak:
                ic, kop, sub = "prullenbak", t("De prullenbak is leeg", "The trash is empty"), \
                    t("Wat je weggooit, komt eerst hier. Je kunt het terugzetten.", "What you delete comes here first. You can restore it.")
            elif self.sorteer.zoek:
                ic, kop, sub = "map", t("Niks gevonden", "Nothing found"), \
                    t(f"Er staat niks met '{self.zoek.text()}' in deze map.", f"Nothing with '{self.zoek.text()}' in this folder.")
            else:
                ic, kop, sub = "map", t("Deze map is leeg", "This folder is empty"), \
                    t("Sleep er iets naartoe, of maak een nieuwe map.", "Drag something here, or make a new folder.")
            self.leeg_beeld.setPixmap(lijn_icoon(ic, "tekst3", 56, gekozen=None).pixmap(56, 56))
            self.leeg_kop.setText(kop)
            self.leeg_sub.setText(sub)
            self.stapel.setCurrentWidget(self.leeg)
        else:
            self.stapel.setCurrentWidget(self.lijst)
        woord = t("ding" if aantal == 1 else "dingen", "item" if aantal == 1 else "items")
        delen = [f"{aantal} {woord}"]
        if gekozen:
            delen.append(t(f"{gekozen} gekozen", f"{gekozen} selected"))
        if not self.in_prullenbak:
            hier = schijf_van(self.huidig, self.lijst_schijven)
            vrij = mooie_maat(hier.vrij) if hier and hier.vrij is not None else vrije_ruimte(self.huidig)
            if vrij:
                delen.append(t(f"{vrij} vrij", f"{vrij} free"))
        self.status.setText("  ·  ".join(delen))
        self.leeg_knop.setEnabled(aantal > 0)
        if self.in_prullenbak:
            knoppen = {"terugzetten"}
        else:
            knoppen = {"openen", "kopieer", "knip", "weg"} | ({"naam"} if gekozen == 1 else set())
        self.keuzebalk.toon(gekozen, knoppen)
        self.plaats_keuzebalk()

    def plaats_keuzebalk(self) -> None:
        """Midden onderin over de tegels; de tegels schuiven op zodat er niets onder verdwijnt."""
        balk = self.keuzebalk
        onder = balk.sizeHint().height() + 28 if not balk.isHidden() else 0
        if self.lijst.viewportMargins().bottom() != onder:
            self.lijst.setViewportMargins(0, 0, 0, onder)
        balk.plaats(QRect(self.stapel.mapTo(self, QPoint(0, 0)), self.stapel.size()))

    def closeEvent(self, e) -> None:  # noqa: N802
        if self.bezig:
            # Een schijf wordt klaargemaakt, gewist, hernoemd of gerepareerd: niet halverwege afbreken (U207).
            self.sluit_na_klus = True
            self.melding.toon(t("Even wachten: de schijf is nog bezig. Haal hem er niet uit; daarna gaat het venster "
                                "vanzelf dicht.", "One moment: the drive is still busy. Do not unplug it; the window "
                                "closes by itself afterwards."), seconden=0)
            e.ignore()
            return
        if self.klus and self.klus.isRunning():
            # Nooit midden in het kopiëren stoppen: wacht tot het klaar is en sluit dan vanzelf.
            self.sluit_na_klus = True
            self.melding.toon(t("Even wachten: er loopt nog iets (kopiëren of weggooien). Daarna gaat het venster vanzelf dicht.",
                                "One moment: something is still busy (copying or deleting). The window closes by itself afterwards."),
                              seconden=0)
            e.ignore()
            return
        self.apparaten.stop()
        self.voorbeelden.stop()
        STOP.set()
        QThreadPool.globalInstance().waitForDone(2000)
        laat_klembord_los()
        super().closeEvent(e)

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        # Smal venster (of grote letters): de knoppen bovenin alleen met hun pictogram (de naam als tip), anders
        # schoof de zoekbalk over het pad en viel 'Veilig verwijderen' half weg (U398).
        if hasattr(self, "leeg_knop"):
            smal = self.width() < px(1260)
            for k in (self.plak_knop, self.nieuw_knop, self.uitwerp_knop, self.leeg_knop):
                k.setText("" if smal else k.property("volle_tekst"))
        if hasattr(self, "keuzebalk"):
            self.plaats_keuzebalk()

    def event(self, e) -> bool:
        if e.type() == QEvent.Type.WindowActivate:
            self.ververs_plak()  # er kan in een ander programma iets gekopieerd zijn
        return super().event(e)

    def eventFilter(self, ding, e) -> bool:  # noqa: N802
        if ding is getattr(self, "pad_vak", None) and e.type() == QEvent.Type.Resize and hasattr(self, "huidig"):
            QTimer.singleShot(0, self.pad_passend)
            return False
        if e.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop) and \
                ding in (self.lijst.viewport(), self.leeg):
            if self.slepen(e, ding):
                return True
            if e.type() != QEvent.Type.DragMove:
                e.ignore()
                return True
        return super().eventFilter(ding, e)

    def ververs_plak(self) -> None:
        self.plak_knop.setVisible(not self.in_prullenbak and not self.in_computer and self.klembord_heeft_bestanden())

    def escape(self) -> None:
        if self.zoek.text():
            self.zoek.clear()
        else:
            self.lijst.clearSelection()

    def zoeken(self, tekst: str) -> None:
        self.sorteer.zet_zoek(tekst)
        self.ververs_staat()

    def ververs(self) -> None:
        if self.in_prullenbak:
            self.open_prullenbak(geschiedenis=False)
            return
        self.voorbeelden.vergeet()
        self.ga_naar(self.huidig, geschiedenis=False)

    def wissel_verborgen(self) -> None:
        self.verborgen = not self.verborgen
        filter_ = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
        if self.verborgen:
            filter_ |= QDir.Filter.Hidden
        self.model.setFilter(filter_)

    def gekozen(self) -> list[Path]:
        sel = self.lijst.selectionModel()
        if sel is None or self.in_computer:
            return []
        return [Path(i.data(PAD_ROL)) for i in sel.selectedIndexes() if i.data(PAD_ROL)]

    def selecteer(self, pad: Path) -> None:
        if self.in_prullenbak or self.in_computer:
            return
        idx = self.sorteer.mapFromSource(self.model.index(str(pad)))
        if idx.isValid():
            self.lijst.setCurrentIndex(idx)
            self.lijst.scrollTo(idx)

    def openen(self, index=None) -> None:
        paden = [Path(index.data(PAD_ROL))] if index is not None and index.data(PAD_ROL) else self.gekozen()
        if self.in_prullenbak:
            self.melding.toon(t("Zet het eerst terug om het te openen.", "Restore it first to open it."))
            return
        for pad in paden[:10]:
            if pad.is_dir():
                self.ga_naar(pad)
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pad)))
