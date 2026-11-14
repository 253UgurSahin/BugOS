"""BugOS Instellingen: wat alle pagina's delen. Werk op de achtergrond, de stijl, de kleine
onderdelen (keuzes, schuifbalken, menu's), Blad (een pagina) en de dialogen om iets te kiezen.
"""

from __future__ import annotations

from bugos_ui import (K, Knop, Pagina, Schuif, StreepKnop, Venster, Zoekveld, kde_instelling, label, lijn_icoon, ronde_knop,
                      px, schaal_css, schermmaat, t, zoeksleutel)
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QDialog, QFrame, QGridLayout, QHBoxLayout, QLayout, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QPushButton, QSlider, QVBoxLayout, QWidget,
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
    return schaal_css(f"""
QFrame#snel {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; }}
QPushButton#keus {{ background: transparent; border: none; border-radius: 9px; padding: 8px 14px; font-size: 14px;
    font-weight: 600; color: {K['tekst2']}; }}
QPushButton#keus:hover {{ color: {K['tekst']}; }}
QPushButton#keus:checked {{ background: {K['accent_zacht']}; color: {K['accent_gekozen']}; }}
QPushButton#keus:focus {{ border: 2px solid {K['accent']}; padding: 6px 12px; }}
QPushButton#keus:disabled {{ color: {K['tekst3']}; }}
QFrame#keuzes {{ background: {K['knop']}; border-radius: 12px; }}
QPushButton#plaatje {{ background: transparent; border: 2px solid transparent; border-radius: 16px; padding: 3px; }}
QPushButton#plaatje:hover {{ border: 2px solid {K['rand_sterk']}; }}
QPushButton#plaatje:checked {{ border: 2px solid {K['accent']}; }}
QPushButton#plaatje:focus {{ border: 2px dashed {K['accent']}; }}
QListWidget#keuzelijst {{ background: {K['vlak']}; border: 1px solid {K['rand']}; border-radius: 16px; padding: 6px;
    outline: 0; font-size: 14px; }}
QListWidget#keuzelijst::item {{ padding: 6px 12px; border-radius: 10px; color: {K['tekst']}; }}
QListWidget#keuzelijst::item:hover {{ background: {K['knop']}; }}
QListWidget#keuzelijst::item:selected {{ background: {K['accent_zacht']}; color: {K['accent_gekozen']}; font-weight: 600; }}
""")


def verborgen(w: QWidget) -> bool:
    """Is dit onderdeel echt verborgen (hide())? Niet: nog niet getoond omdat het venster nog niet open is.
    (Qt's isHidden() is ook True voor een onderdeel dat nog nooit getoond is; dan telde een Doorloop of Kolommen bij
    het bouwen niets mee, en bleef de eerste maat fout: de keuzes gingen dan niet onder de tekst, B-02.) Dezelfde
    regel als Qt zelf gebruikt om te kiezen of een kind mee verschijnt met zijn ouder."""
    return w.isHidden() and w.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide)


def leeg(item) -> bool:
    """Telt dit stukje van een indeling niet mee (een verborgen onderdeel)?"""
    w = item.widget()
    return verborgen(w) if w is not None else item.isEmpty()


class Doorloop(QLayout):
    """Onderdelen naast elkaar, links uitgelijnd; wat niet meer past, gaat naar de volgende regel (zoals tekst).

    Waarom: een gewone QHBoxLayout wordt nooit smaller dan alles naast elkaar. Bij 150 % of met grote letters is er
    op een laptop van 1280 x 800 te weinig ruimte, en dan schoof de hele pagina opzij (of viel een knop eraf). Een
    Doorloop zet wat niet meer past op een nieuwe regel. Gebruikt voor de tabjes boven een pagina (R07) en de
    plaatjes van de achtergrond op Uiterlijk (D05). Hij stond eerst in bugos-settings zelf; hier kunnen de pagina's
    hem ook gebruiken (bugos-settings haalt hem hier vandaan, dus 'Doorloop' bestaat daar nog steeds)."""

    def __init__(self, ruimte: int = 4, smal_links: int | None = None):
        super().__init__()
        self._items: list = []
        # Dezelfde ruimte tussen twee onderdelen naast elkaar én tussen twee regels.
        self.setSpacing(ruimte)
        # smal_links: past het breedste onderdeel niet meer met de gewone linkermarge (bijv. de knoppen onder Updates,
        # die 52 px inspringen zodat ze onder de tekst van de regel staan), dan deze kleinere marge. Anders werd de
        # pagina op een half scherm (640 px) breder dan het venster en schoof hij opzij (B-02).
        self.smal_links = smal_links

    # --- de gewone QLayout-functies: een eenvoudige lijst met onderdelen ---

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        # Wil zelf niet groeien: de onderdelen houden hun eigen maat, de rest van de regel blijft leeg.
        return Qt.Orientation(0)

    # --- de hoogte hangt af van de breedte (meer regels als het smaller wordt) ---

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, breed: int) -> int:  # noqa: N802
        # Alleen uitrekenen hoe hoog het wordt, niets verplaatsen.
        return self._leg(QRect(0, 0, breed, 0), alleen_meten=True)

    def setGeometry(self, r: QRect) -> None:  # noqa: N802
        super().setGeometry(r)
        self._leg(r)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Alles op één regel."""
        m = self.contentsMargins()
        zichtbaar = [i.sizeHint() for i in self._items if not leeg(i)]
        breed = sum(z.width() for z in zichtbaar) + self.spacing() * max(0, len(zichtbaar) - 1)
        hoog = max((z.height() for z in zichtbaar), default=0)
        return QSize(breed + m.left() + m.right(), hoog + m.top() + m.bottom())

    def minimumSize(self) -> QSize:  # noqa: N802
        """Zo smal als het breedste onderdeel: de rest kan eronder. (Dit maakt dat de pagina niet opzij schuift.)"""
        m = self.contentsMargins()
        z = QSize()
        for i in self._items:
            z = z.expandedTo(i.minimumSize())
        links = m.left() if self.smal_links is None else min(m.left(), self.smal_links)
        return QSize(z.width() + links + m.right(), z.height() + m.top() + m.bottom())

    def _leg(self, r: QRect, alleen_meten: bool = False) -> int:
        """Leg de onderdelen neer in r (of meet alleen) en geef de hoogte die daarvoor nodig is."""
        m = self.contentsMargins()
        links, rechts = r.x() + m.left(), r.right() - m.right()
        if self.smal_links is not None:
            # Het breedste onderdeel moet heel blijven: past het niet met de gewone marge, dan de kleine.
            breedst = max((i.sizeHint().width() for i in self._items if not leeg(i)), default=0)
            if rechts - links + 1 < breedst:
                links = r.x() + min(m.left(), self.smal_links)
        x, y, regel = links, r.y() + m.top(), 0
        for item in self._items:
            if leeg(item):     # verborgen onderdelen tellen niet mee
                continue
            z = item.sizeHint()
            if x > links and x + z.width() - 1 > rechts:   # past niet meer: volgende regel
                x, y, regel = links, y + regel + self.spacing(), 0
            if not alleen_meten:
                # Nooit breder dan de regel zelf (één onderdeel dat breder is dan alles, wordt smaller).
                item.setGeometry(QRect(QPoint(x, y), QSize(min(z.width(), rechts - links + 1), z.height())))
            x += z.width() + self.spacing()
            regel = max(regel, z.height())
        return y + regel + m.bottom() - r.y()


class Kolommen(QWidget):
    """Kaarten naast elkaar en even breed (Energie: zuinig, gebalanceerd, snel; Start: de vier snelle schuifjes).

    Past dat niet meer (Instellingen op de helft van het scherm, 150 %, grote letters), dan komen er minder op één
    regel: 4 -> 2 -> 1, of 3 -> 2 -> 1. Waarom: een QHBoxLayout wordt nooit smaller dan alles naast elkaar. Op een
    half scherm (640 px) werd de pagina daardoor breder dan het venster: een balk om opzij te schuiven en de kaart
    'Snel' half weg (B-02). Verborgen kaarten (geen wifi, geen bluetooth) tellen niet mee en laten geen gat achter."""

    def __init__(self, ruimte: int = 12):
        super().__init__()
        self._rooster = QGridLayout(self)
        self._rooster.setContentsMargins(0, 0, 0, 0)
        self._rooster.setSpacing(ruimte)
        # Het rooster mag de breedte van alles-naast-elkaar niet als minimum vastleggen: dat bepalen we zelf
        # (minimumSizeHint hieronder), anders wordt de kaart nooit smaller.
        self._rooster.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._items: list[QWidget] = []
        self.kolommen = 0      # hoeveel kaarten er nu naast elkaar staan (de test kijkt hiernaar)

    def voeg(self, w: QWidget) -> QWidget:
        self._items.append(w)
        # Wordt een kaart verborgen of weer getoond, dan opnieuw neerleggen (anders blijft er een gat).
        w.installEventFilter(self)
        self._leg(self._aantal(self.width()) if self.width() > 0 else len(self.zichtbaar()) or 1)
        return w

    def zichtbaar(self) -> list[QWidget]:
        return [w for w in self._items if not verborgen(w)]

    def _smalst(self) -> int:
        """De breedte die de breedste kaart minstens nodig heeft."""
        return max((max(w.minimumSizeHint().width(), w.minimumWidth()) for w in self.zichtbaar()), default=0)

    def _aantal(self, breed: int) -> int:
        """Hoeveel kaarten passen er naast elkaar in deze breedte? Bij vier nooit drie (dan staat er één alleen)."""
        n = len(self.zichtbaar())
        if n <= 1:
            return 1
        nodig, ruimte = self._smalst(), self._rooster.spacing()
        for k in range(n, 0, -1):
            if k > 1 and n > 3 and n % k:
                continue      # 4 kaarten: 4 of 2 naast elkaar, niet 3 + 1
            if k == 1 or k * nodig + (k - 1) * ruimte <= breed:
                return k
        return 1

    def _leg(self, k: int) -> None:
        """Leg de zichtbare kaarten neer in k kolommen, even breed."""
        while self._rooster.count():
            self._rooster.takeAt(0)        # (de kaarten zelf blijven bestaan; ze komen er zo weer in)
        for i in range(max(self._rooster.columnCount(), len(self._items))):
            self._rooster.setColumnStretch(i, 0)
        for i, w in enumerate(self.zichtbaar()):
            self._rooster.addWidget(w, i // k, i % k)
        for i in range(k):
            self._rooster.setColumnStretch(i, 1)
        self.kolommen = k
        self._rooster.invalidate()
        self.updateGeometry()

    def herschik(self) -> None:
        """Opnieuw tellen wat er past (na het verbergen of tonen van een kaart, of een andere breedte)."""
        self._leg(self._aantal(self.width()))

    def eventFilter(self, obj, e) -> bool:  # noqa: N802
        if e.type() in (QEvent.Type.ShowToParent, QEvent.Type.HideToParent) and obj in self._items:
            # Pas na deze gebeurtenis is isHidden() bijgewerkt: dan pas opnieuw neerleggen.
            QTimer.singleShot(0, self.herschik)
        return False

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Zo smal als de breedste kaart (dan staan ze onder elkaar); zo hoog als ze nu liggen."""
        return QSize(self._smalst(), self._rooster.minimumSize().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        z = self.zichtbaar()
        breed = sum(w.sizeHint().width() for w in z) + self._rooster.spacing() * max(0, len(z) - 1)
        return QSize(breed, self._rooster.sizeHint().height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        k = self._aantal(self.width())
        if k != self.kolommen:
            self._leg(k)


class Keuzes(QFrame):
    """Een paar knoppen naast elkaar waarvan er één gekozen is (zoals 100% · 125% · 150%)."""

    gekozen = Signal(object)

    def __init__(self, opties: list[tuple[object, str]]):
        super().__init__()
        self.setObjectName("keuzes")
        # Een Doorloop, geen QHBoxLayout: past een rij keuzes niet (Instellingen op een half scherm, 640 px), dan gaan
        # de laatste naar een tweede regel. Met een QHBoxLayout werd de pagina breder dan het venster en vielen
        # '200%', 'Omgekeerd' en 'Nooit' rechts weg (B-02).
        lay = Doorloop(2)
        self.setLayout(lay)
        lay.setContentsMargins(3, 3, 3, 3)
        self.groep = QButtonGroup(self)
        self.knoppen: dict[object, QPushButton] = {}
        for waarde, tekst in opties:
            # Gekozen: zacht rood met rode letters (zoals de zijbalk en de tabjes) en een korte rode streep eronder.
            k = StreepKnop(tekst, "keus")
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
        # Smaller mag tot 120 px (was 220): op een half scherm (640 px) hield de schuifbalk de pagina anders breder
        # dan het venster (B-02). Met ruimte genoeg wordt hij gewoon breder (rekfactor 1).
        self.balk.setMinimumWidth(px(120))
        self.balk.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.balk, 1)
        self.getal = label(f"{waarde}%", "kop3", wrap=False)
        self.getal.setFixedWidth(px(52))   # '100%' past, ook met grote letters (U085)
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


TOON_KDE_KNOP = False

PAGINA_MARGE, PAGINA_MARGE_SMAL = 40, 20   # links en rechts van een pagina; smal: onder SMAL_VANAF px breed
SMAL_VANAF = 480


def pagina_marge(breed: int) -> int:
    """De marge links en rechts van een pagina (en van de tabjes erboven) bij deze breedte (B-02)."""
    return PAGINA_MARGE_SMAL if breed < px(SMAL_VANAF) else PAGINA_MARGE


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
        # Geen 'Meer instellingen' meer onder elke pagina: dat bracht je steeds naar KDE. Alles van KDE staat nu op
        # één plek: Over deze computer > Geavanceerde instellingen. (self.kde blijft: wie het nodig heeft, weet welk
        # KDE-onderdeel bij de pagina hoort.)
        if self.kde and TOON_KDE_KNOP:
            meer = Knop(t("Meer instellingen (voor gevorderden)", "More settings (advanced)"), "stil", "lijn:code")
            meer.clicked.connect(lambda _c=False: kde_instelling(self.kde))
            self.lay.addWidget(meer, 0, Qt.AlignmentFlag.AlignLeft)
        self.klaar()

    @classmethod
    def naam(cls) -> str:
        return t(cls.titel_nl, cls.titel_en)

    def bouw(self) -> None:
        pass

    def resizeEvent(self, e) -> None:  # noqa: N802
        """Op een smalle pagina (Instellingen op de helft van het scherm) een kleinere marge links en rechts, zoals
        Windows 11: dan past een rij keuzes of knoppen nog naast elkaar in plaats van dat de pagina opzij schuift
        (B-02). Boven en onder blijven zoals ze zijn (onder de tabjes is de bovenmarge kleiner)."""
        super().resizeEvent(e)
        zijkant = pagina_marge(self.viewport().width())
        m = self.lay.contentsMargins()
        if m.left() != zijkant:
            self.lay.setContentsMargins(zijkant, m.top(), zijkant, m.bottom())


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
        # Niet hoger dan het scherm (1280x800 bij 150 %: 445 px vrij): de lijst schuift, de knoppen blijven te zien.
        ruimte = schermmaat((0, 9999))[0][1] - px(36) * (3 if zoek_hint else 2) - 110
        self.lijst.setMinimumHeight(max(120, min(400, 42 * len(items) + 12, ruimte)))
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
        woorden = zoeksleutel(tekst).split()   # (U268)
        for i in range(self.lijst.count()):
            it = self.lijst.item(i)
            it.setHidden(not all(w in zoeksleutel(it.text()) for w in woorden))

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
