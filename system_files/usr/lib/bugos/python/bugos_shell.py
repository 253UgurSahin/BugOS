"""De schil van bugos_ui: het venster van een BugOS-app met zijbalk, pagina's, regels, meldingen en knoppenbalk.

Apps halen dit uit bugos_ui (from bugos_ui import Venster, Pagina, Rij ...); dit bestand hoort daarbij.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAccessible, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractSlider, QAccessibleWidget, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

import bugos_ui  # DONKER via de module lezen: maak_app zet hem pas als de app start
from bugos_pages import Zijbalk, Zoekveld, logo_icoon, sectie
from bugos_ui import LIJN, lijn_icoon, schermmaat, t
from bugos_widgets import Groep, Knop, label


# ================================================================== schil ===
# Eén schil voor alle BugOS-apps: links de naam van de app en de onderdelen,
# rechts pagina's met een vaste leesbreedte, overal dezelfde regels, meldingen
# en knoppenbalk. Zo zien Bestanden, Instellingen en Taakbeheer er hetzelfde uit.

LEESBREEDTE = 880      # breder wordt de inhoud van een pagina niet: dat leest rustiger
ZIJBALK_BREEDTE = 248


def app_kop(naam: str) -> QWidget:
    """De naam van de app bovenin de zijbalk, met het beestje er klein voor."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 0, 0, 6)
    lay.setSpacing(10)
    beeld = QLabel()
    beeld.setPixmap(logo_icoon().pixmap(QSize(22, 22)))
    beeld.setFixedSize(22, 22)
    lay.addWidget(beeld)
    lay.addWidget(label(naam, "appnaam", wrap=False), 1)
    return w


def ronde_knop(icoon_naam: str, tip: str, klein: bool = False) -> QPushButton:
    """Een rond knopje met alleen een icoontje (terug, vooruit, meer…)."""
    k = QPushButton()
    k.setObjectName("rond_klein" if klein else "rond")
    k.setIcon(lijn_icoon(icoon_naam, "tekst2" if klein else "tekst", 20, gekozen=None))
    k.setIconSize(QSize(20, 20))
    k.setToolTip(tip)
    k.setAccessibleName(tip)
    k.setCursor(Qt.CursorShape.PointingHandCursor)
    return k


class Rij(QFrame):
    """Eén regel in een kaart: icoontje, naam, een regel uitleg, en rechts een schuifje, knop of pijltje.

    klikbaar=True: de hele regel is een knop (muis, Enter of spatie) en geeft 'geklikt'.
    Is de regel te smal (klein venster, 150 %, grote letters), dan gaan de knoppen of keuzes rechts onder de tekst,
    zoals een instellingenkaart in Windows 11. Getallen (Taakbeheer) blijven altijd rechts staan, onder hun kopjes."""

    geklikt = Signal()
    STAPELBAAR = True   # False: wat rechts staat, gaat nooit onder de tekst

    def __init__(self, icoon_naam: str | QIcon, titel_tekst: str, uitleg_tekst: str = "",
                 rechts: QWidget | None = None, klikbaar: bool = False, pijl: bool | None = None, hoogte: int = 60):
        super().__init__()
        self.setObjectName("rij")
        self.setProperty("klikbaar", "true" if klikbaar else "false")
        if klikbaar:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(hoogte)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 12, 8)
        lay.setSpacing(14)
        self.icoon = QLabel()
        self.icoon.setFixedSize(24, 24)
        self.icoon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zet_icoon(icoon_naam)
        lay.addWidget(self.icoon, 0, Qt.AlignmentFlag.AlignVCenter)
        blok = QVBoxLayout()
        blok.setSpacing(1)
        self.titel = label(titel_tekst, "rij", wrap=False)
        self.uitleg = label(uitleg_tekst, "klein")
        self.uitleg.setVisible(bool(uitleg_tekst))
        blok.addWidget(self.titel)
        blok.addWidget(self.uitleg)
        lay.addLayout(blok, 1)
        self.rechts = rechts
        if rechts is not None:
            lay.addWidget(rechts, 0, Qt.AlignmentFlag.AlignVCenter)
            # Een schuifje heet zoals de regel; een knop met tekst ("Nu vergrendelen") houdt zijn eigen tekst.
            if isinstance(rechts, QAbstractButton) and not rechts.accessibleName() and not rechts.text().strip():
                rechts.setAccessibleName(titel_tekst)
            # Een schuifbalk (volume, helderheid) heet zoals de regel; keuzeknoppen ("30 min", "Nooit")
            # krijgen de regel als uitleg, zodat je hoort bij welke regel ze horen.
            balk = getattr(rechts, "balk", None)
            if balk is not None and not balk.accessibleName():
                balk.setAccessibleName(titel_tekst)
            for knop in getattr(rechts, "knoppen", {}).values():
                if not knop.accessibleDescription():
                    knop.setAccessibleDescription(titel_tekst)
                rechts.setAccessibleDescription(uitleg_tekst)
        self.rechts = rechts
        self.pijl = None
        if pijl is None:
            pijl = klikbaar and rechts is None
        if pijl:
            self.pijl = QLabel()
            self.pijl.setPixmap(lijn_icoon("rechts", "tekst3", 16, gekozen=None).pixmap(16, 16))
            lay.addWidget(self.pijl, 0, Qt.AlignmentFlag.AlignVCenter)
        self._gestapeld = False
        if self._kan_stapelen():
            # Anders legt de layout de breedte van één regel vast als minimum, en wordt de regel nooit smaller.
            lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

    def _kan_stapelen(self) -> bool:
        """Alleen iets om te bedienen (keuzes, knoppen, een schuifbalk) mag onder de tekst; getallen niet."""
        r = getattr(self, "rechts", None)
        if r is None or not self.STAPELBAAR:
            return False
        bediening = (QAbstractButton, QAbstractSlider)
        return isinstance(r, bediening) or any(r.findChildren(b) for b in bediening)

    def _titel_breedte(self) -> int:
        """Hoe breed de titel op één regel is. Gemeten met de letter zelf, dus hetzelfde of hij nu afbreekt of niet
        (anders springt de regel heen en weer)."""
        self.titel.ensurePolished()
        return self.titel.fontMetrics().horizontalAdvance(self.titel.text()) + 2

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Zo smal kan de regel: het schuifje, de knoppen of de keuzes kunnen onder de tekst, en een lange titel
        breekt af (zie resizeEvent)."""
        if not self._kan_stapelen():
            return super().minimumSizeHint()
        m = self.layout().contentsMargins()
        tekst = min(self._titel_breedte(), bugos_ui.px(200))
        breed = m.left() + m.right() + 24 + 14 + max(tekst, self.rechts.minimumSizeHint().width())
        return QSize(breed, super().minimumSizeHint().height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        """Te smal? Dan gaat wat rechts staat onder de tekst, zoals in Windows 11. Weer breed genoeg: terug naar
        rechts. Het blijft hetzelfde onderdeel van de regel, dus de Tab-volgorde en de schermlezer veranderen niet.
        Is zelfs de titel te lang voor de regel, dan breekt hij af (nooit afgeknipt)."""
        super().resizeEvent(e)
        if not hasattr(self, "_gestapeld") or not self._kan_stapelen():
            return
        lay = self.layout()
        m = lay.contentsMargins()
        titel = self._titel_breedte()
        vast = m.left() + m.right() + 24 + 14
        rechts = 14 + self.rechts.sizeHint().width() + (30 if self.pijl else 0)
        stapel = self.width() < vast + min(titel, bugos_ui.px(240)) + rechts
        # De titel breekt af als hij niet op één regel past: naast wat rechts staat, of (gestapeld) over de hele regel.
        afbreken = self.width() < vast + titel + (0 if stapel else rechts)
        if afbreken != self.titel.wordWrap():
            self.titel.setWordWrap(afbreken)
        if stapel == self._gestapeld:
            return
        self._gestapeld = stapel
        blok = lay.itemAt(1).layout()       # titel + uitleg
        if stapel:
            lay.removeWidget(self.rechts)
            blok.addSpacing(6)
            blok.addWidget(self.rechts, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            blok.removeWidget(self.rechts)
            laatste = blok.itemAt(blok.count() - 1)
            if laatste is not None and laatste.spacerItem() is not None:
                blok.removeItem(laatste)
            lay.insertWidget(2, self.rechts, 0, Qt.AlignmentFlag.AlignVCenter)
        self.updateGeometry()

    def zet_icoon(self, naam: str | QIcon) -> None:
        if isinstance(naam, QIcon):
            ic = naam
        else:
            naam = naam[5:] if naam.startswith("lijn:") else naam
            ic = lijn_icoon(naam, "tekst2", 22, gekozen=None) if naam in LIJN else QIcon.fromTheme(naam)
        self.icoon.setPixmap(ic.pixmap(QSize(22, 22)))

    def zet_uitleg(self, tekst: str) -> None:
        self.uitleg.setText(tekst)
        self.uitleg.setVisible(bool(tekst))
        # Ook voor de schermlezer: de keuzeknoppen ('5 min', 'Nooit') horen de nieuwe uitleg (U483).
        rechts = getattr(self, "rechts", None)
        if rechts is not None and getattr(rechts, "knoppen", None):
            rechts.setAccessibleDescription(tekst)
            titel = self.titel.text()
            for knop in rechts.knoppen.values():
                knop.setAccessibleDescription(f"{titel}. {tekst}" if tekst else titel)

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        # Een dubbelklik is één klik: de tweede keer loslaten doet niets (anders twee keer verbinden,
        # twee wachtwoordvragen) (U332).
        self._dubbel = True
        super().mouseDoubleClickEvent(e)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if getattr(self, "_dubbel", False):
            self._dubbel = False
        elif self.property("klikbaar") == "true" and e.button() == Qt.MouseButton.LeftButton \
                and self.rect().contains(e.position().toPoint()):
            self.geklikt.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.property("klikbaar") == "true" and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not e.isAutoRepeat():   # Enter vasthouden is één keer (geen stapel wachtwoordvragen) (U531)
                self.geklikt.emit()
            e.accept()
            return
        super().keyPressEvent(e)


class _RijVoorSchermlezer(QAccessibleWidget):
    """Wat een schermlezer hoort bij een regel waar je op kunt klikken: 'knop', met de titel als naam
    en de uitleg erbij. Hij leest ze elke keer opnieuw, dus ook als de titel later verandert."""

    def __init__(self, rij: Rij):
        super().__init__(rij, QAccessible.Role.Button)
        self.rij = rij

    def text(self, soort):
        if soort == QAccessible.Text.Name:
            return self.rij.accessibleName() or self.rij.titel.text()
        if soort == QAccessible.Text.Description:
            return self.rij.accessibleDescription() or self.rij.uitleg.text()
        return super().text(soort)


class _KnopVoorSchermlezer(QAccessibleWidget):
    """Een eigen vlak dat je kunt aanklikken (bijv. een schijf in Bestanden): voor een schermlezer een knop,
    niet 'paneel' (U274). De naam en uitleg komen uit accessibleName/-Description."""

    def __init__(self, ding):
        super().__init__(ding, QAccessible.Role.Button)


def _schermlezer(_soort: str, ding):
    if isinstance(ding, Rij) and ding.property("klikbaar") == "true":
        return _RijVoorSchermlezer(ding)
    if isinstance(ding, QWidget) and ding.property("knop_voor_schermlezer") is True:
        return _KnopVoorSchermlezer(ding)
    return None


QAccessible.installFactory(_schermlezer)


class Melding(QFrame):
    """Een korte melding bovenin een pagina, eventueel met een knop ('Ongedaan maken'). Verdwijnt vanzelf."""

    def __init__(self):
        super().__init__()
        self.setObjectName("melding")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 9, 8, 9)
        lay.setSpacing(12)
        self.tekst = label("", wrap=True)
        self.knop = Knop("", "stil")
        self.knop.setMinimumHeight(bugos_ui.px(32))
        lay.addWidget(self.tekst, 1)
        lay.addWidget(self.knop)
        self.actie = None
        self.knop.clicked.connect(self._klik)
        self.klok = QTimer(self)
        self.klok.setSingleShot(True)
        self.klok.timeout.connect(self.hide)
        self.hide()

    def toon(self, tekst: str, soort: str = "info", knop: str = "", actie=None, seconden: int = 7) -> None:
        self.setProperty("soort", soort)
        self.style().unpolish(self)
        self.style().polish(self)
        self.tekst.setText(tekst)
        self.knop.setText(knop)
        self.knop.setVisible(bool(knop))
        self.actie = actie
        self.show()
        if seconden:
            self.klok.start(seconden * 1000)
        else:
            self.klok.stop()

    def _klik(self) -> None:
        actie, self.actie = self.actie, None
        self.hide()
        if actie:
            actie()


class ActieBalk(QFrame):
    """Zweeft onderin zodra je iets kiest: '2 gekozen · Openen · Kopiëren · …' met een kruisje."""

    gesloten = Signal()

    def __init__(self, ouder: QWidget):
        super().__init__(ouder)
        self.setObjectName("actiebalk")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(20, 7, 7, 7)
        self.lay.setSpacing(2)
        self.aantal = label("", "kop3", wrap=False)
        self.lay.addWidget(self.aantal)
        self.lay.addSpacing(10)
        streep = QFrame()
        streep.setObjectName("streep")
        streep.setFixedHeight(26)
        self.lay.addWidget(streep)
        self.lay.addSpacing(6)
        self.knoppen: dict[str, QPushButton] = {}
        self.sluit = ronde_knop("kruis", t("Niets meer kiezen", "Clear selection"))
        self.sluit.clicked.connect(self.gesloten.emit)
        schaduw = QGraphicsDropShadowEffect(self)
        schaduw.setBlurRadius(36)
        schaduw.setOffset(0, 10)
        schaduw.setColor(QColor(0, 0, 0, 150 if bugos_ui.DONKER else 46))
        self.setGraphicsEffect(schaduw)
        self.hide()

    def knop(self, sleutel: str, icoon_naam: str, tekst: str, actie) -> QPushButton:
        k = QPushButton(tekst)
        k.setObjectName("balkknop")
        k.setIcon(lijn_icoon(icoon_naam, "tekst", 18, gekozen=None))
        k.setIconSize(QSize(18, 18))
        k.setCursor(Qt.CursorShape.PointingHandCursor)
        k.clicked.connect(lambda _c=False, f=actie: f())
        self.lay.addWidget(k)
        self.knoppen[sleutel] = k
        return k

    def klaar(self) -> None:
        """Na de laatste knop: ruimte en het kruisje."""
        self.lay.addSpacing(6)
        self.lay.addWidget(self.sluit)

    def toon(self, n: int, zichtbaar: set[str] | None = None, woord: tuple[str, str] = ("gekozen", "selected")) -> None:
        if not n:
            self.hide()
            return
        self.aantal.setText(f"{n} {t(*woord)}")
        for sleutel, k in self.knoppen.items():
            k.setVisible(zichtbaar is None or sleutel in zichtbaar)
        self.adjustSize()
        self.show()
        self.raise_()

    def plaats(self, gebied: QRect) -> None:
        """Midden onderin 'gebied' (in de coördinaten van het venster). Passen de woorden niet (smal venster, 150 %),
        dan alleen de icoontjes, met de naam als tip en voor de schermlezer, zoals de knoppenbalk van Verkenner."""
        if self.isHidden():
            return
        self.setMaximumWidth(max(200, gebied.width() - 24))
        for k in self.knoppen.values():                 # eerst met woorden proberen
            volle = k.property("volle_tekst")
            if volle and not k.text():                  # een nieuwe tekst van de app gaat voor
                k.setText(volle)
        self.adjustSize()
        alleen_icoon = self.sizeHint().width() > self.maximumWidth()
        for k in self.knoppen.values():
            if alleen_icoon:
                # Het woord als tip en voor de schermlezer. Steeds opnieuw: de app kan het woord veranderen
                # (Taakbeheer: 'Sluiten' of 'Stoppen').
                naam = k.text() or k.property("volle_tekst") or ""
                k.setProperty("volle_tekst", naam)
                k.setToolTip(naam)
                k.setAccessibleName(naam)
                k.setText("")
            else:
                # Met woorden: geen vaste naam, dan leest de schermlezer altijd het woord dat er nu staat.
                k.setToolTip("")
                k.setAccessibleName("")
        if alleen_icoon:
            self.adjustSize()
        self.move(gebied.center().x() - self.width() // 2, gebied.bottom() - self.height() - 14)
        self.raise_()


class Pagina(QScrollArea):
    """Een pagina in een BugOS-app: grote titel, een regel uitleg, en kaarten met een vaste leesbreedte."""

    def __init__(self, titel_tekst: str = "", uitleg_tekst: str = "", breedte: int = LEESBREEDTE):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        # Past een rij niet (smal venster, grote letters), dan kun je opzij schuiven: niets valt buiten bereik (U133).
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewport().setAutoFillBackground(False)
        buiten = QWidget()
        buiten.setObjectName("pagina")
        rij = QHBoxLayout(buiten)
        rij.setContentsMargins(0, 0, 0, 0)
        rij.setSpacing(0)
        inhoud = QWidget()
        inhoud.setObjectName("pagina")
        inhoud.setMaximumWidth(breedte)
        self.lay = QVBoxLayout(inhoud)
        self.lay.setContentsMargins(40, 32, 40, 28)
        self.lay.setSpacing(14)
        rij.addWidget(inhoud, 1)
        rij.addStretch(0)
        self.titel = self.sub = None
        if titel_tekst:
            self.titel = label(titel_tekst, "titel")
            self.lay.addWidget(self.titel)
        if uitleg_tekst:
            self.sub = label(uitleg_tekst, "sub")
            self.lay.addWidget(self.sub)
        self.melding = Melding()
        self.lay.addWidget(self.melding)
        self.setWidget(buiten)

    def kaart(self, kopje: str = "") -> Groep:
        """Een kaart met regels, eventueel met een kopje erboven."""
        if kopje:
            self.lay.addWidget(sectie(kopje))
        g = Groep()
        g.lay.setContentsMargins(4, 4, 4, 4)
        self.lay.addWidget(g)
        return g

    def klaar(self) -> None:
        """Na de laatste kaart: de rest van de ruimte leeg laten."""
        self.lay.addStretch(1)

    def ververs(self) -> None:
        """Wordt aangeroepen als de pagina opent (voor apps die iets willen bijwerken)."""


def leeg_groep(g: Groep) -> None:
    """Haal alle regels uit een kaart (om hem opnieuw te vullen)."""
    while g.lay.count():
        item = g.lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class Venster(QWidget):
    """Het venster van een BugOS-app: links de naam van de app en de onderdelen, rechts de pagina's.

    inhoud=None: rechts komt een stapel pagina's (voeg_pagina). Anders komt die widget rechts."""

    pagina_gekozen = Signal(str)

    def __init__(self, naam: str, titel_tekst: str = "", zoeken: str = "", inhoud: QWidget | None = None,
                 maat: tuple[int, int] = (1120, 760), minimum: tuple[int, int] = (920, 600)):
        super().__init__()
        self.setObjectName("venster")
        self.setWindowTitle(titel_tekst or naam)
        # Nooit groter dan het scherm (bijv. 1920x1080 op 200 %, of 1280x800 op 150 %), met de taakbalk en de
        # titelbalk erbij: anders valt de onderkant eraf (U133). Dezelfde maat als bugos_ui.uitvoeren gebruikt.
        maat, minimum = schermmaat(maat, minimum)
        self.resize(*maat)
        self.setMinimumSize(*minimum)
        hoofd = QHBoxLayout(self)
        hoofd.setContentsMargins(0, 0, 0, 0)
        hoofd.setSpacing(0)
        self.zij = QWidget()
        self.zij.setObjectName("zijkant")
        self.zij.setFixedWidth(bugos_ui.px(ZIJBALK_BREEDTE))   # groeit mee met grote letters (U136)
        self.zij_lay = QVBoxLayout(self.zij)
        self.zij_lay.setContentsMargins(14, 22, 14, 14)
        self.zij_lay.setSpacing(10)
        self.zij_lay.addWidget(app_kop(naam))
        self.zoekveld = None
        if zoeken:
            self.zoekveld = Zoekveld(zoeken)   # 36 px, zoals elk invoerveld (groeit mee met grote letters)
            self.zij_lay.addWidget(self.zoekveld)
        self.nav = Zijbalk()
        self.zij_lay.addWidget(self.nav, 1)
        self.onder = QVBoxLayout()
        self.onder.setSpacing(4)
        self.zij_lay.addLayout(self.onder)
        hoofd.addWidget(self.zij)
        self.stapel = QStackedWidget() if inhoud is None else None
        self.inhoud = self.stapel if inhoud is None else inhoud
        hoofd.addWidget(self.inhoud, 1)
        self.paginas: dict[str, QWidget] = {}
        self.nav.currentRowChanged.connect(self._kies)

    def voeg_pagina(self, sleutel: str, icoon_naam: str, naam: str, pagina: QWidget) -> QWidget:
        self.nav.voeg_toe(icoon_naam if icoon_naam.startswith("lijn:") or ":" in icoon_naam else f"lijn:{icoon_naam}",
                          naam, sleutel)
        if self.stapel is not None:
            self.stapel.addWidget(pagina)
        self.paginas[sleutel] = pagina
        return pagina

    def onder_knop(self, tekst: str, icoon_naam: str, actie, tip: str = "") -> Knop:
        """Een stille knop onderin de zijbalk, bijvoorbeeld 'Meer instellingen (voor gevorderden)'."""
        k = Knop(tekst, "stil", f"lijn:{icoon_naam}" if icoon_naam else None)
        if tip:
            k.setToolTip(tip)
        k.clicked.connect(lambda _c=False: actie())
        self.onder.addWidget(k)
        return k

    def huidige(self) -> str:
        return self.nav.sleutel(self.nav.currentRow())

    def ga_naar(self, sleutel: str) -> None:
        if self.huidige() == sleutel:
            self._kies(self.nav.currentRow())
        else:
            self.nav.kies(sleutel)

    def _kies(self, rij: int) -> None:
        sleutel = self.nav.sleutel(rij)
        pagina = self.paginas.get(sleutel)
        if pagina is None:
            return
        if self.stapel is not None:
            self.stapel.setCurrentWidget(pagina)
        ververs = getattr(pagina, "ververs", None)
        if callable(ververs):
            ververs()
        self.pagina_gekozen.emit(sleutel)


# =============================================================== vragen ===
# Eén look voor elke vraag, zoals KiesDialoog: een kop, ruime marges, rechts 'Annuleren' (stil) en de rode knop.
# Niet QMessageBox (met Qt's blauwe '?') of QInputDialog (geen kop, de knoppen verkeerd om).

class VraagDialoog(QDialog):
    """Een vraag met een kop, een uitleg, eventueel een invoerveld, en twee knoppen: stil 'nee', rood 'ja'."""

    def __init__(self, ouder: QWidget | None, titel_tekst: str, tekst: str, ja: str, nee: str = "",
                 veld: bool = False, waarde: str = "", wachtwoord: bool = False, enter_is_nee: bool = False):
        super().__init__(ouder)
        self.setWindowTitle(titel_tekst)
        breed = schermmaat((bugos_ui.px(440), 0))[0][0]   # op een smal scherm (150 %) niet breder dan het scherm
        self.setMinimumWidth(breed)
        self.setMaximumWidth(max(breed, bugos_ui.px(560)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        self.kop = label(titel_tekst, "kop2")
        lay.addWidget(self.kop)
        self.uitleg = label(tekst, "klein" if veld else "sub", kopieerbaar=True)
        self.uitleg.setVisible(bool(tekst))
        lay.addWidget(self.uitleg)
        self.veld: QLineEdit | None = None
        self.oog: Knop | None = None
        if veld:
            self.veld = QLineEdit(waarde)
            self.veld.setMinimumHeight(bugos_ui.px(36))
            self.veld.setAccessibleName(titel_tekst)
            lay.addWidget(self.veld)
            if wachtwoord:
                # Bolletjes; 'Laten zien' zoals bij WachtwoordDialoog. De tekst staat nergens anders (geen tip, geen log).
                self.veld.setEchoMode(QLineEdit.EchoMode.Password)
                self.oog = Knop(t("Laten zien", "Show"), "stil", "lijn:oog")
                self.oog.setCheckable(True)
                # Een aan/uit-knopje zoals een vinkje: spatie zet het om, Enter verstuurt nog steeds de vraag.
                self.oog.setAutoDefault(False)
                self.oog.toggled.connect(lambda aan: self.veld.setEchoMode(
                    QLineEdit.EchoMode.Normal if aan else QLineEdit.EchoMode.Password))
                lay.addWidget(self.oog, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(4)
        knoppen = QHBoxLayout()
        knoppen.setSpacing(8)
        knoppen.addStretch(1)
        self.nee = Knop(nee or t("Annuleren", "Cancel"), "stil")
        self.nee.clicked.connect(self.reject)
        self.ja = Knop(ja, "hoofd")
        self.ja.clicked.connect(self.accept)
        knoppen.addWidget(self.nee)
        knoppen.addWidget(self.ja)
        lay.addLayout(knoppen)
        # Enter uit gewoonte: bij iets dat je niet ongedaan maakt (teruggaan, weggooien) doet dat niets (U380).
        # Sta je met Tab op een knop, dan doet Enter (net als spatie) die knop, zoals overal in Windows en KDE: beide
        # knoppen blijven 'autoDefault'. De standaardknop telt alleen als er geen knop gekozen is (in het tekstveld).
        standaard = self.nee if enter_is_nee else self.ja
        standaard.setDefault(True)
        if self.veld is not None:
            if not wachtwoord:   # een lege naam kan niet; een leeg wachtwoord (open netwerk) mag de pagina zelf weigeren
                self.veld.textChanged.connect(lambda tekst_: self.ja.setEnabled(bool(tekst_.strip())))
                self.ja.setEnabled(bool(waarde.strip()))
            self.veld.setFocus()
        else:
            standaard.setFocus()

    def sizeHint(self) -> QSize:  # noqa: N802
        """Precies zo hoog als de inhoud bij de echte breedte: geen lege strook boven de knoppen. (Qt rekende de hoogte
        van een afgebroken uitleg uit bij een smallere breedte dan de minimale 440 px, en hield die ruimte dan over.)"""
        lay = self.layout()
        if lay is None:
            return super().sizeHint()
        breed = max(self.minimumWidth(), min(self.maximumWidth(), lay.totalSizeHint().width()))
        hoog = lay.totalHeightForWidth(breed) if lay.hasHeightForWidth() else lay.totalSizeHint().height()
        return QSize(breed, hoog)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        maat = self.sizeHint()
        self.setMinimumHeight(min(self.minimumHeight(), maat.height()))
        self.resize(maat)

    @property
    def standaard(self) -> str:
        """De tekst van de knop die Enter kiest (voor de tests)."""
        return self.nee.text() if self.nee.isDefault() else self.ja.text()


def vraag_ja(ouder: QWidget | None, titel_tekst: str, tekst: str, ja: str, nee: str = "",
             enter_is_nee: bool = False) -> bool:
    """Vraag iets met ja of nee, in de BugOS-stijl. True als je op 'ja' klikt.

        if vraag_ja(self, t("Printer verwijderen?", "Remove printer?"), t("...", "..."), t("Verwijderen", "Remove"),
                    enter_is_nee=True): ...

    nee: standaard 'Annuleren'. enter_is_nee=True: Enter doet het veilige (niets), voor iets dat je niet ongedaan
    kunt maken."""
    d = VraagDialoog(ouder, titel_tekst, tekst, ja, nee, enter_is_nee=enter_is_nee)
    return d.exec() == QDialog.DialogCode.Accepted


def vraag_tekst(ouder: QWidget | None, titel_tekst: str, vraag: str, tekst: str = "", ok: str = "",
                wachtwoord: bool = False, kies_tot: int | None = None) -> str | None:
    """Vraag een tekst (een naam, een wifi-wachtwoord). None bij Annuleren.

    wachtwoord=True: je ziet bolletjes, met 'Laten zien' eronder. Geef het antwoord nooit door op een opdrachtregel
    (gebruik stdin) en zet het nergens in een log. kies_tot: alleen dat stuk is gekozen (een bestandsnaam zonder
    '.odt'), zodat je meteen een nieuwe naam typt."""
    d = VraagDialoog(ouder, titel_tekst, vraag, ok or t("OK", "OK"), veld=True, waarde=tekst, wachtwoord=wachtwoord)
    if d.veld is not None and tekst:
        if kies_tot is not None and 0 < kies_tot <= len(tekst):
            d.veld.setSelection(0, kies_tot)
        else:
            d.veld.selectAll()
    if d.exec() != QDialog.DialogCode.Accepted or d.veld is None:
        return None
    return d.veld.text()
