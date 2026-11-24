"""BugOS Instellingen: de pagina 'Geïnstalleerde apps' (onder Apps en gamen).

Zoals 'Geïnstalleerde apps' in Windows 11: een lijst met de apps op deze computer, en bij elke app 'Verwijderen'.
Het is dezelfde lijst als 'Mijn apps' in de BugOS Winkel, en het verwijderen gaat op precies dezelfde manier: de
lijst, de vraag, de opdracht voor flatpak en de melding daarna komen allemaal uit bugos_apps (niet een tweede
kopie hier). Installeren doe je in de Winkel; de knop 'Meer apps in de Winkel' brengt je daarheen.
"""

from __future__ import annotations

import bugos_apps
import bugos_config as bi
from bugos_ui import TAAL, Knop, Rij, leeg_groep, start, t
from bugos_settings_onderdelen import Blad, op_achtergrond
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

# Voor foto's en tests (BUGOS_INSTELLINGEN_VOORBEELD): een paar echte apps, zonder flatpak te vragen. Zo ziet de
# pagina er op de website en in de lay-outtest uit zoals op een gewone BugOS na de eerste start.
VOORBEELD_APPS = {
    "org.mozilla.firefox": {"naam": "Firefox", "bron": "flathub"},
    "org.libreoffice.LibreOffice": {"naam": "LibreOffice", "bron": "flathub"},
    "org.videolan.VLC": {"naam": "VLC", "bron": "flathub"},
    "com.spotify.Client": {"naam": "Spotify", "bron": "flathub"},
}


def lees_apps() -> list[dict]:
    """De apps voor deze pagina: [{'id', 'naam', 'uitleg'}], in de volgorde van 'Mijn apps' in de Winkel.

    Draait op de achtergrond (flatpak list duurt soms een seconde). De naam en uitleg komen uit de catalogus van de
    Winkel als de app daarin staat (dan heet hij net zo als in de Winkel, in jouw taal), anders de naam die flatpak
    geeft."""
    info = dict(VOORBEELD_APPS) if bi.VOORBEELD else bugos_apps.flatpak_lijst()
    try:
        catalogus = bugos_apps.lees_catalogus()["apps"]
    except (OSError, ValueError, KeyError):
        catalogus = []   # geen catalogus (een kapotte of ontbrekende store.json): dan alleen de namen van flatpak
    picks = {a["id"]: a for a in catalogus}
    ids = bugos_apps.mijn_apps_ids(catalogus, info, sleutel=lambda i: info[i]["naam"].lower())
    apps = []
    for app_id in ids:
        pick = picks.get(app_id)
        if pick is not None:
            naam = pick.get("naam_en", pick["naam"]) if TAAL != "nl" else pick["naam"]
            uitleg = pick.get("nl" if TAAL == "nl" else "en", pick.get("en", ""))
        else:
            naam = info[app_id]["naam"]
            # Waar komt hij vandaan? Meestal Flathub; een app van ergens anders zeggen we eerlijk.
            uitleg = t("Van Flathub", "From Flathub") if info[app_id].get("bron") == "flathub" else \
                t("Niet uit Flathub", "Not from Flathub")
        apps.append({"id": app_id, "naam": naam, "uitleg": uitleg})
    return apps


class AppsPagina(Blad):
    sleutel, icoon = "mijnapps", "apps"
    titel_nl, titel_en = "Geïnstalleerde apps", "Installed apps"
    uitleg_nl = "De apps op deze computer. Verwijder wat je niet meer gebruikt; nieuwe apps haal je uit de Winkel."
    uitleg_en = "The apps on this computer. Remove what you no longer use; get new apps from the Store."
    zoekwoorden = ("apps app programma's programma geïnstalleerd geinstalleerd verwijderen weghalen deïnstalleren "
                   "installeren winkel mijn apps firefox steam installed apps programs remove uninstall delete "
                   "store my apps android apk waydroid fdroid")

    def bouw(self) -> None:
        self.bezig: str | None = None   # het id van de app die nu verwijderd wordt (dan kan er niet nog een bij)
        self.knoppen: dict[str, Knop] = {}
        self.lijst = self.kaart()
        # Onder de lijst: naar de Winkel, voor nieuwe apps en voor meer over een app.
        rij_w = QWidget()
        rij = QHBoxLayout(rij_w)
        rij.setContentsMargins(0, 0, 0, 0)
        rij.setSpacing(8)
        self.winkel = Knop(t("Meer apps in de Winkel", "More apps in the Store"), "rand", "lijn:download")
        self.winkel.clicked.connect(lambda _c=False: None if bi.VOORBEELD else start("bugos-store"))
        rij.addWidget(self.winkel)
        rij.addStretch(1)
        self.lay.addWidget(rij_w, 0, Qt.AlignmentFlag.AlignLeft)
        # Android-apps (Waydroid): klaarzetten, F-Droid en .apk-bestanden in een eigen venster (bugos-android). Onder
        # de Winkel-knop, niet ernaast: naast elkaar paste het niet op een half scherm (T-FIT).
        self.android = Knop(t("Android-apps", "Android apps"), "rand", "lijn:telefoon")
        self.android.clicked.connect(lambda _c=False: None if bi.VOORBEELD else start("bugos-android"))
        self.lay.addWidget(self.android, 0, Qt.AlignmentFlag.AlignLeft)

    def ververs(self) -> None:
        # Tijdens het verwijderen niet opnieuw lezen: dan zou de knop 'Bezig…' verdwijnen.
        if self.bezig is None:
            op_achtergrond(self, lees_apps, self.toon)

    def toon(self, apps) -> None:
        if apps is None:   # lezen mislukte helemaal: de oude lijst laten staan
            return
        leeg_groep(self.lijst)
        self.knoppen = {}
        if not apps:
            # Geen enkele app (de eerste start is nog bezig, of je haalde alles weg): zeg waar je ze vindt.
            self.lijst.voeg(Rij("apps", t("Nog geen apps", "No apps yet"),
                                t("Apps haal je uit de BugOS Winkel. Na de eerste start komen Firefox, LibreOffice "
                                  "en VLC vanzelf, zodra je internet hebt.",
                                  "Get apps from the BugOS Store. After the first start, Firefox, LibreOffice and "
                                  "VLC arrive by themselves once you are online.")))
            return
        for app in apps:
            weg = Knop(t("Verwijderen", "Remove"), "stil")
            weg.setAccessibleDescription(app["naam"])   # 'Verwijderen' van welke app? (zoals in de Winkel, U482)
            weg.clicked.connect(lambda _c=False, a=app: self.vraag(a))
            weg.setEnabled(self.bezig is None)
            self.knoppen[app["id"]] = weg
            self.lijst.voeg(Rij(bugos_apps.app_icoon(app["id"]), app["naam"], app["uitleg"], weg))

    def vraag(self, app: dict) -> None:
        """Verwijderen? Dezelfde vraag als in de Winkel (met het vinkje voor de bestanden van de app)."""
        if self.bezig is not None:
            return
        met_gegevens = bugos_apps.vraag_verwijderen(self, app["naam"])
        if met_gegevens is None:
            return
        opdracht = bugos_apps.verwijder_opdracht(app["id"], met_gegevens)
        if not opdracht:
            return
        self.bezig = app["id"]
        for knop in self.knoppen.values():   # één tegelijk: flatpak kan niet twee dingen tegelijk
            knop.setEnabled(False)
        self.knoppen[app["id"]].setText(t("Bezig…", "Working…"))
        self.melding.toon(t(f"{app['naam']} wordt verwijderd…", f"Removing {app['naam']}…"), "info", seconden=0)

        def werk() -> tuple[int, str]:
            if bi.VOORBEELD:   # foto's en tests: niets echt verwijderen, wel doen alsof het lukte
                VOORBEELD_APPS.pop(app["id"], None)
                return 0, ""
            # Wacht ook als KDE eerst het wachtwoord van een beheerder vraagt (zie verwijder_nu).
            return bugos_apps.verwijder_nu(opdracht)

        op_achtergrond(self, werk, lambda uitkomst: self.verwijderd(app, uitkomst))

    def verwijderd(self, app: dict, uitkomst) -> None:
        """Het verwijderen is klaar (gelukt of niet). Niet 'klaar': zo heet al de methode van Blad die de pagina afmaakt."""
        code, uit = uitkomst if uitkomst else (1, "")
        self.bezig = None
        tekst, soort = bugos_apps.verwijder_melding(code, uit, app["naam"])
        self.melding.toon(tekst, soort)
        self.ververs()   # de lijst opnieuw: zonder de app die weg is (of met, als het niet lukte)
