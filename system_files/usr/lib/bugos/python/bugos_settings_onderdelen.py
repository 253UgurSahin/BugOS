"""BugOS Instellingen: wat alle pagina's delen. Werk op de achtergrond, de stijl, de kleine
onderdelen (keuzes, schuifbalken, menu's), Blad (een pagina) en de dialogen om iets te kiezen.
"""

from __future__ import annotations

from bugos_ui import K, Knop, Pagina, Schuif, Venster, Zoekveld, kde_instelling, label, lijn_icoon, ronde_knop, t
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QDialog, QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)


# ============================================================ achtergrond ===

class Sein(QObject):
    klaar = Signal(object)


class Klusje(QRunnable):
    def __init__(self, werk, sein: Sein):
        super().__init__()
        self.werk, self.sein = werk, sein

    def run(self) -> None:
        try:
            uitkomst = self.werk()
        except Exception:  # noqa: BLE001  een kapotte instelling mag het venster nooit laten vallen
            uitkomst = None
        try:
            self.sein.klaar.emit(uitkomst)
        except RuntimeError:  # het venster is al dicht
            pass


def op_achtergrond(ouder: QObject, werk, klaar) -> None:
    """Doe iets traags (wifi zoeken, bluetooth vragen) zonder dat het venster vastloopt."""
    sein = Sein(ouder)
    sein.klaar.connect(lambda uitkomst: (klaar(uitkomst), sein.deleteLater()))
    QThreadPool.globalInstance().start(Klusje(werk, sein))


# ============================================================ onderdelen ===

def stijl() -> str:
    return f"""
QFrame#snel {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; }}
QPushButton#keus {{ background: transparent; border: none; border-radius: 9px; padding: 8px 14px; font-size: 14px;
    font-weight: 600; color: {K['tekst2']}; }}
QPushButton#keus:hover {{ color: {K['tekst']}; }}
QPushButton#keus:checked {{ background: {K['vlak']}; color: {K['tekst']}; }}
QFrame#keuzes {{ background: {K['knop']}; border-radius: 12px; }}
QPushButton#plaatje {{ background: transparent; border: 2px solid transparent; border-radius: 16px; padding: 3px; }}
QPushButton#plaatje:hover {{ border: 2px solid {K['rand_sterk']}; }}
QPushButton#plaatje:checked {{ border: 2px solid {K['accent']}; }}
QListWidget#keuzelijst {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; padding: 6px;
    outline: 0; font-size: 14px; }}
QListWidget#keuzelijst::item {{ padding: 6px 12px; border-radius: 10px; color: {K['tekst']}; }}
QListWidget#keuzelijst::item:hover {{ background: {K['knop']}; }}
QListWidget#keuzelijst::item:selected {{ background: {K['accent_zacht']}; color: {K['accent']}; font-weight: 600; }}
"""


class Keuzes(QFrame):
    """Een paar knoppen naast elkaar waarvan er één gekozen is (zoals 100% · 125% · 150%)."""

    gekozen = Signal(object)

    def __init__(self, opties: list[tuple[object, str]]):
        super().__init__()
        self.setObjectName("keuzes")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.groep = QButtonGroup(self)
        self.knoppen: dict[object, QPushButton] = {}
        for waarde, tekst in opties:
            k = QPushButton(tekst)
            k.setObjectName("keus")
            k.setCheckable(True)
            k.setCursor(Qt.CursorShape.PointingHandCursor)
            k.clicked.connect(lambda _c=False, w=waarde: self.gekozen.emit(w))
            self.groep.addButton(k)
            self.knoppen[waarde] = k
            lay.addWidget(k)

    def zet(self, waarde: object) -> None:
        k = self.knoppen.get(waarde)
        if k is not None:
            k.setChecked(True)


class Regelaar(QWidget):
    """Een schuifbalk met het getal ernaast (volume, helderheid)."""

    veranderd = Signal(int)

    def __init__(self, waarde: int = 50):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.balk = QSlider(Qt.Orientation.Horizontal)
        self.balk.setRange(0, 100)
        self.balk.setValue(waarde)
        self.balk.setMinimumWidth(220)
        self.balk.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.balk, 1)
        self.getal = label(f"{waarde}%", "kop3", wrap=False)
        self.getal.setFixedWidth(48)
        self.getal.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.getal)
        self.wacht = QTimer(self)
        self.wacht.setSingleShot(True)
        self.wacht.setInterval(120)  # niet bij elke pixel iets aan de computer veranderen
        self.wacht.timeout.connect(lambda: self.veranderd.emit(self.balk.value()))
        self.balk.valueChanged.connect(lambda w: (self.getal.setText(f"{w}%"), self.wacht.start()))

    def zet(self, waarde: int) -> None:
        self.balk.blockSignals(True)
        self.balk.setValue(waarde)
        self.balk.blockSignals(False)
        self.getal.setText(f"{waarde}%")


def schuifje(aan: bool, omgezet) -> Schuif:
    s = Schuif(aan)
    s.toggled.connect(omgezet)
    return s


def menu_bij(knop: QWidget, items: list[tuple[str, str, object]]) -> None:
    """Een klein menu onder een knop: [(icoon, tekst, actie), ...]."""
    m = QMenu(knop)
    for ic, tekst, actie in items:
        a = m.addAction(lijn_icoon(ic, "tekst", 18, gekozen=None), tekst)
        a.triggered.connect(lambda _c=False, f=actie: f())
    m.exec(knop.mapToGlobal(knop.rect().bottomLeft()))


def meer_knop(items_maker) -> QPushButton:
    """Een '…'-knopje dat een menu opent (items_maker geeft de lijst voor menu_bij)."""
    k = ronde_knop("meer", t("Meer", "More"), klein=True)
    k.clicked.connect(lambda _c=False: menu_bij(k, items_maker()))
    return k


class Blad(Pagina):
    """Een pagina van Instellingen: titel, uitleg, kaarten, en onderaan de weg naar KDE voor gevorderden."""

    sleutel = ""
    icoon = ""
    titel_nl = titel_en = ""
    uitleg_nl = uitleg_en = ""
    zoekwoorden = ""
    kde = ""  # het KDE-onderdeel achter 'Meer instellingen (voor gevorderden)'

    def __init__(self, venster: Venster):
        super().__init__(self.naam(), t(self.uitleg_nl, self.uitleg_en) if self.uitleg_nl else "")
        self.venster = venster
        self.bouw()
        if self.kde:
            meer = Knop(t("Meer instellingen (voor gevorderden)", "More settings (advanced)"), "stil", "lijn:code")
            meer.clicked.connect(lambda _c=False: kde_instelling(self.kde))
            self.lay.addWidget(meer, 0, Qt.AlignmentFlag.AlignLeft)
        self.klaar()

    @classmethod
    def naam(cls) -> str:
        return t(cls.titel_nl, cls.titel_en)

    def bouw(self) -> None:
        pass


# ================================================================ kiezen ===

class KiesDialoog(QDialog):
    """Een lijst om één ding uit te kiezen (tijdzone, taal), met een zoekveld als de lijst lang is."""

    def __init__(self, ouder: QWidget, titel_tekst: str, items: list[tuple[object, str]], huidig: object = None,
                 zoek_hint: str = ""):
        super().__init__(ouder)
        self.setWindowTitle(titel_tekst)
        self.setMinimumWidth(460)
        self.gekozen = huidig
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(label(titel_tekst, "kop2"))
        self.zoekveld = None
        if zoek_hint:
            self.zoekveld = Zoekveld(zoek_hint)
            self.zoekveld.textChanged.connect(self.filter)
            lay.addWidget(self.zoekveld)
        self.lijst = QListWidget()
        self.lijst.setObjectName("keuzelijst")
        self.lijst.setMinimumHeight(min(400, 42 * len(items) + 12))
        for waarde, tekst in items:
            it = QListWidgetItem(tekst)
            it.setData(Qt.ItemDataRole.UserRole, waarde)
            it.setSizeHint(QSize(0, 40))
            self.lijst.addItem(it)
            if waarde == huidig:
                self.lijst.setCurrentItem(it)
        self.lijst.itemDoubleClicked.connect(lambda _it: self.accept())
        lay.addWidget(self.lijst, 1)
        knoppen = QHBoxLayout()
        knoppen.addStretch(1)
        weg = Knop(t("Annuleren", "Cancel"), "stil")
        weg.clicked.connect(self.reject)
        ok = Knop(t("Kiezen", "Choose"), "hoofd")
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        knoppen.addWidget(weg)
        knoppen.addWidget(ok)
        lay.addLayout(knoppen)
        if self.lijst.currentItem() is not None:
            self.lijst.scrollToItem(self.lijst.currentItem(), QAbstractItemView.ScrollHint.PositionAtCenter)

    def filter(self, tekst: str) -> None:
        woorden = tekst.lower().split()
        for i in range(self.lijst.count()):
            it = self.lijst.item(i)
            it.setHidden(not all(w in it.text().lower() for w in woorden))

    def accept(self) -> None:  # noqa: N802
        it = self.lijst.currentItem()
        if it is None or it.isHidden():
            it = next((self.lijst.item(i) for i in range(self.lijst.count()) if not self.lijst.item(i).isHidden()),
                      None)
        if it is None:
            return
        self.gekozen = it.data(Qt.ItemDataRole.UserRole)
        super().accept()


class WachtwoordDialoog(QDialog):
    """Twee keer het nieuwe wachtwoord typen; pas als ze gelijk zijn, kan het.
    huidig=True: ook je huidige wachtwoord hier (voor wie geen beheerder is: dan vraagt KDE het niet)."""

    MINIMUM = 6

    def __init__(self, ouder: QWidget, huidig: bool = False):
        super().__init__(ouder)
        self.setWindowTitle(t("Nieuw wachtwoord", "New password"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        lay.addWidget(label(t("Kies een nieuw wachtwoord", "Choose a new password"), "kop2"))
        uitleg = (t(f"Eerst je huidige wachtwoord, dan het nieuwe (minstens {self.MINIMUM} tekens).",
                    f"First your current password, then the new one (at least {self.MINIMUM} characters).")
                  if huidig else
                  t(f"Minstens {self.MINIMUM} tekens. Daarna vraagt BugOS nog één keer je huidige wachtwoord.",
                    f"At least {self.MINIMUM} characters. BugOS then asks for your current password once more."))
        lay.addWidget(label(uitleg, "klein"))
        self.nu: QLineEdit | None = None
        if huidig:
            self.nu = QLineEdit()
            self.nu.setEchoMode(QLineEdit.EchoMode.Password)
            self.nu.setPlaceholderText(t("Huidig wachtwoord", "Current password"))
            lay.addWidget(self.nu)
        self.een = QLineEdit()
        self.een.setEchoMode(QLineEdit.EchoMode.Password)
        self.een.setPlaceholderText(t("Nieuw wachtwoord", "New password"))
        self.twee = QLineEdit()
        self.twee.setEchoMode(QLineEdit.EchoMode.Password)
        self.twee.setPlaceholderText(t("Nog een keer", "Once more"))
        lay.addWidget(self.een)
        lay.addWidget(self.twee)
        self.fout = label("", "klein")
        self.fout.setStyleSheet(f"color: {K['fout']};")
        lay.addWidget(self.fout)
        self.oog = Knop(t("Laten zien", "Show"), "stil", "lijn:oog")
        self.oog.setCheckable(True)
        self.oog.toggled.connect(self.laat_zien)
        lay.addWidget(self.oog, 0, Qt.AlignmentFlag.AlignLeft)
        knoppen = QHBoxLayout()
        knoppen.addStretch(1)
        weg = Knop(t("Annuleren", "Cancel"), "stil")
        weg.clicked.connect(self.reject)
        self.ok = Knop(t("Wachtwoord instellen", "Set password"), "hoofd")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.accept)
        knoppen.addWidget(weg)
        knoppen.addWidget(self.ok)
        lay.addLayout(knoppen)
        self.een.textChanged.connect(self.controleer)
        self.twee.textChanged.connect(self.controleer)
        if self.nu is not None:
            self.nu.textChanged.connect(self.controleer)

    def laat_zien(self, aan: bool) -> None:
        for veld in (self.een, self.twee, self.nu):
            if veld is not None:
                veld.setEchoMode(QLineEdit.EchoMode.Normal if aan else QLineEdit.EchoMode.Password)

    def controleer(self) -> None:
        a, b = self.een.text(), self.twee.text()
        self.ok.setEnabled(len(a) >= self.MINIMUM and a == b and (self.nu is None or bool(self.nu.text())))
        if a and len(a) < self.MINIMUM:
            self.fout.setText(t("Nog te kort.", "Still too short."))
        elif a and b and a != b:
            self.fout.setText(t("De twee wachtwoorden zijn niet hetzelfde.", "The two passwords are not the same."))
        else:
            self.fout.setText("")

    @property
    def wachtwoord(self) -> str:
        return self.een.text()

    @property
    def huidig_wachtwoord(self) -> str:
        return self.nu.text() if self.nu is not None else ""


def dichtstbij(keuzes: tuple, waarde: int) -> int:
    """De keuze die het dichtst bij de waarde ligt (0 betekent 'nooit' en blijft 0)."""
    if not waarde:
        return 0
    return min((k for k in keuzes if k), key=lambda k: abs(k - waarde))
