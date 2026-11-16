"""BugOS: de apps op deze computer opnoemen en verwijderen, op één plek voor de Winkel en Instellingen > Apps.

Waarom een eigen module: 'Mijn apps' in de BugOS Winkel (bugos-store) en de pagina 'Geïnstalleerde apps' in
Instellingen laten dezelfde apps zien en verwijderen ze op dezelfde manier. Stond dat twee keer in de code, dan
zou de ene na een tijdje iets anders doen dan de andere (een app die je in de Winkel wel kunt verwijderen maar in
Instellingen niet, of een andere foutmelding). Hier staat dus:

  - welke apps er zijn (flatpak_lijst) en welke daarvan in 'Mijn apps' horen (mijn_apps_ids);
  - hoe je er een verwijdert (verwijder_opdracht) en wat je daarna zegt (verwijder_melding);
  - de vraag 'Verwijderen?' met het vinkje voor de bestanden van de app (vraag_verwijderen);
  - het pictogram van een app (app_icoon), ook zonder internet.

De afspraak (wens van de eigenaar, 2026-11-16): ALLES wat in 'Mijn apps' staat, kun je ook verwijderen. Daarom
staan daar alleen Flatpak-apps: die zijn los van BugOS zelf en kun je weghalen en later weer installeren. Wat in
BugOS zelf zit (Bestanden, Instellingen, Dolphin...) hoort bij het systeem en staat er niet tussen. Firefox en Steam
zaten vroeger als gewoon programma in BugOS; dat zijn nu ook Flatpaks (zie bugos-first-boot), dus die kun je nu
ook verwijderen.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from bugos_ui import bestaat, draai, t

# De catalogus van de Winkel: de apps die BugOS uitkoos, met een korte uitleg in het Nederlands en Engels.
CATALOGUS = Path("/usr/share/bugos/store.json")

# Een geldig app-id (org.voorbeeld.App): alleen zo'n id gaat ooit naar flatpak. Nooit met '-' vooraan, want dan zou
# flatpak het als optie lezen ('-rf' of '--delete-data' als app-naam mag nooit iets doen).
APP_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}$")

# Waar de pictogrammen van de apps staan. De eerste map die het pictogram heeft, wint.
ICOON_MAPPEN = [
    Path("/var/lib/flatpak/appstream/flathub/x86_64/active/icons/128x128"),
    Path("/var/lib/flatpak/appstream/flathub/x86_64/active/icons/64x64"),
    Path.home() / ".local/share/flatpak/appstream/flathub/x86_64/active/icons/128x128",
    # Meegeleverd met BugOS (build.sh): ook op een vers systeem en zonder internet een echt pictogram.
    Path("/usr/share/bugos/store-icons"),
]
# Voor screenshots en tests: een eigen map met pictogrammen vooraan.
if os.environ.get("BUGOS_APPICONEN"):
    ICOON_MAPPEN.insert(0, Path(os.environ["BUGOS_APPICONEN"]))
# Apps die (vroeger, of als iemand ze zelf als pakket erbij zette) als gewoon programma op de computer staan: hun
# pictogram heet in het thema anders dan hun Flathub-id.
THEMA_NAMEN = {"org.mozilla.firefox": "firefox", "com.valvesoftware.Steam": "steam"}


def lees_catalogus(pad: Path | None = None) -> dict:
    """De catalogus van de Winkel (store.json) als dict met 'categorieen' en 'apps'.

    Zonder pad: CATALOGUS, op het moment van lezen (niet van het laden van de module), zodat een test hem kan omzetten."""
    return json.loads((pad or CATALOGUS).read_text(encoding="utf-8"))


def flatpak_lijst() -> dict[str, dict]:
    """Elke geïnstalleerde Flatpak-app: id -> {'naam': naam, 'bron': waar hij vandaan kwam (meestal 'flathub')}.

    Zo kan 'Mijn apps' ook apps laten zien die niet uit de BugOS-selectie komen. Alleen apps (--app), geen
    onderdelen (runtimes): die verwijder je niet zelf, 'flatpak uninstall --unused' ruimt ze op."""
    if os.environ.get("BUGOS_GEINSTALLEERD") is not None:   # voor screenshots: de naam is het laatste stuk van het id
        return {i: {"naam": i.rsplit(".", 1)[-1], "bron": "flathub"}
                for i in filter(None, os.environ["BUGOS_GEINSTALLEERD"].split(","))}
    if not bestaat("flatpak"):
        return {}
    _, uit = draai("flatpak", "list", "--app", "--columns=application,name,origin", timeout=20)
    lijst = {}
    for regel in uit.splitlines():
        delen = [d.strip() for d in regel.split("\t")]
        # Alleen regels met een echt app-id: een foutmelding van flatpak wordt zo nooit een 'app'.
        if delen and APP_ID.match(delen[0]):
            lijst[delen[0]] = {"naam": delen[1] if len(delen) > 1 and delen[1] else delen[0].rsplit(".", 1)[-1],
                               "bron": delen[2] if len(delen) > 2 else ""}
    return lijst


def mijn_apps_ids(catalogus_apps: list[dict], flatpaks, sleutel=None) -> list[str]:
    """De apps voor 'Mijn apps' (Winkel) en 'Geïnstalleerde apps' (Instellingen), in de volgorde waarin ze staan.

    Eerst de apps uit de BugOS-selectie, in de volgorde van de catalogus (zo staan Firefox en LibreOffice bovenaan,
    zoals in de Winkel), daarna elke andere Flatpak-app op naam (sleutel: id -> waarop gesorteerd wordt; zonder
    sleutel op het id).

    Alleen Flatpak-apps, nooit een programma dat in BugOS zelf zit: zo heeft elke app in deze lijst een werkende
    knop 'Verwijderen' (de afspraak bovenaan deze module). Vroeger stonden Firefox en Steam er als programma van
    BugOS zelf tussen, zonder Verwijderen."""
    flatpaks = {f for f in flatpaks if APP_ID.match(f)}
    gekozen = [a["id"] for a in catalogus_apps if a["id"] in flatpaks]
    # Hoofdletters tellen niet bij het vergelijken (org.videolan.VLC en org.videolan.vlc zijn dezelfde app).
    gezien = {i.lower() for i in gekozen}
    anderen = [f for f in flatpaks if f.lower() not in gezien]
    anderen.sort(key=sleutel or (lambda i: i.lower()))
    return gekozen + anderen


def verwijder_opdracht(app_id: str, met_gegevens: bool) -> list[str]:
    """De argumenten voor flatpak om deze app te verwijderen (zonder 'flatpak' zelf), of [] bij een vreemd id.

    -y: flatpak vraagt dan niets meer in de terminal (er is geen terminal). Geen --noninteractive: dan mag KDE om
    het wachtwoord van een beheerder vragen (een app van het hele systeem verwijderen mag niet iedereen).
    --delete-data alleen als je dat aanvinkte: dan gaan ook je instellingen en bestanden van de app
    (~/.var/app/<id>) weg. Zonder vinkje blijven ze, zodat de app na opnieuw installeren weer is zoals hij was."""
    if not APP_ID.match(app_id or ""):
        return []
    return ["uninstall", "-y", app_id] + (["--delete-data"] if met_gegevens else [])


def verwijder_nu(opdracht: list[str], timeout: int = 900) -> tuple[int, str]:
    """Draai 'flatpak <opdracht>' (uit verwijder_opdracht) en wacht: (code, wat flatpak schreef).

    Voor Instellingen > Apps (op de achtergrond, zie op_achtergrond). De Winkel doet hetzelfde met een QProcess,
    omdat hij tijdens het installeren laat zien hoe ver het is. LC_ALL=C.UTF-8: flatpak schrijft dan Engels, en
    verwijder_melding herkent 'Not authorized' (een geweigerd wachtwoord), wat je taal ook is. timeout: ruim, want
    KDE vraagt misschien eerst het wachtwoord van een beheerder en dan wacht flatpak op jou."""
    if not opdracht:
        return 1, ""
    try:
        r = subprocess.run(["flatpak", *opdracht], capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LC_ALL": "C.UTF-8"})
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def verwijder_melding(code: int, uit: str, naam: str) -> tuple[str, str]:
    """Wat je ziet na het verwijderen: (tekst, soort melding: 'goed' of 'fout'), in gewone woorden.

    uit: wat flatpak schreef (in het Engels, LC_ALL=C.UTF-8), om een geweigerd wachtwoord te herkennen."""
    if code == 0:
        return t(f"{naam} is verwijderd.", f"{naam} has been removed."), "goed"
    if any(w in (uit or "").lower() for w in ("not authorized", "not allowed", "authentication", "authoriz")):
        return (t(f"{naam} verwijderen mag alleen met het wachtwoord van een beheerder.",
                  f"Removing {naam} needs an administrator's password."), "fout")
    return t(f"{naam} verwijderen lukte niet. Probeer het nog eens.",
             f"Removing {naam} did not work. Please try again."), "fout"


def vraag_verwijderen(ouder, naam: str) -> bool | None:
    """Eerst vragen (de BugOS-vraag; Enter doet niets, want weg is weg) (U464).

    Geeft None als je op Annuleren drukt, anders of je bestanden van de app (inloggen, instellingen) ook weg
    moeten (het vinkje, standaard uit)."""
    # Pas hier importeren: bugos_shell heeft een venster nodig, en deze module wordt ook zonder venster gebruikt.
    import bugos_shell
    from PySide6.QtWidgets import QCheckBox, QDialog

    vraag = bugos_shell.VraagDialoog(ouder, t("Verwijderen?", "Remove?"),
                                     t("{} van deze computer verwijderen?", "Remove {} from this computer?").format(naam),
                                     t("Verwijderen", "Remove"), enter_is_nee=True)
    vraag.vinkje = QCheckBox(t("Ook de instellingen en bestanden van deze app weggooien",
                               "Also delete this app's settings and files"))
    lay = vraag.layout()
    lay.insertWidget(lay.count() - 2, vraag.vinkje)   # onder de vraag, boven de knoppen
    if vraag.exec() != QDialog.DialogCode.Accepted:
        return None
    return vraag.vinkje.isChecked()


def app_icoon(app_id: str):
    """Het pictogram van een app: uit Flathub's lijst, uit BugOS zelf (store-icons) of uit het thema."""
    from PySide6.QtGui import QIcon, QPixmap

    for map_ in ICOON_MAPPEN:
        for ext in (".png", ".svg"):
            bestand = map_ / f"{app_id}{ext}"
            if bestand.is_file():
                return QIcon(str(bestand)) if ext == ".svg" else QIcon(QPixmap(str(bestand)))
    if QIcon.hasThemeIcon(app_id):
        return QIcon.fromTheme(app_id)
    return QIcon.fromTheme(THEMA_NAMEN.get(app_id, app_id), QIcon.fromTheme("application-x-executable"))
