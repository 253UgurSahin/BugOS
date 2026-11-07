"""BugOS Instellingen: meldingen (plasmanotifyrc), standaardprogramma's (xdg-mime) en printers (CUPS).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import bugos_config as _c


# =============================================================== meldingen ===

def lees_tot(tekst: str) -> bool:
    """Is 'Until' uit plasmanotifyrc nog niet voorbij? KDE schrijft 'jaar,maand,dag,uur,min,sec' of een ISO-tijd."""
    from datetime import datetime
    tekst = tekst.strip()
    if not tekst:
        return False
    nu = datetime.now().astimezone()
    try:
        delen = [int(x) for x in tekst.split(",")]
        if len(delen) == 6:
            return datetime(*delen).astimezone() > nu
    except (ValueError, TypeError, OverflowError):
        pass
    try:
        tot = datetime.fromisoformat(tekst.replace("Z", "+00:00"))
        return (tot if tot.tzinfo else tot.astimezone()) > nu
    except ValueError:
        return False


def niet_storen() -> bool:
    if _c.VOORBEELD:
        return _c._VB["niet_storen"]
    return lees_tot(_c.kde_lees("plasmanotifyrc", "DoNotDisturb", "Until", ""))


def zet_niet_storen(aan: bool) -> None:
    """Aan: geen pop-ups tot je het weer uitzet (ze komen wel in de lijst)."""
    if _c.VOORBEELD:
        _c._VB["niet_storen"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "Until", "2999,12,31,0,0,0" if aan else None)


def stil_bij_games() -> bool:
    if _c.VOORBEELD:
        return _c._VB["stil_bij_games"]
    return _c.kde_lees("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true") == "true"


def zet_stil_bij_games(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["stil_bij_games"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true" if aan else "false")


def meldingsgeluid() -> bool:
    if _c.VOORBEELD:
        return _c._VB["geluidje"]
    return _c.kde_lees("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false") != "true"


def zet_meldingsgeluid(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["geluidje"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false" if aan else "true")


def proefmelding(titel: str, tekst: str) -> bool:
    if _c.VOORBEELD:
        return True
    return _c.draai("notify-send", "-a", "BugOS", "-i", "bugos-logo", titel, tekst, timeout=5)[0] == 0


# ====================================================== standaardprogramma's ===

# (sleutel, icoon, (naam nl, naam en), bestandstypes)
SOORTEN = [
    ("internet", "wereld", ("Internet", "Internet"), ["x-scheme-handler/http", "x-scheme-handler/https", "text/html"]),
    ("mail", "praten", ("E-mail", "Email"), ["x-scheme-handler/mailto"]),
    ("fotos", "foto", ("Foto's", "Photos"), ["image/jpeg", "image/png", "image/webp", "image/gif", "image/heif"]),
    ("muziek", "muziek", ("Muziek", "Music"), ["audio/mpeg", "audio/flac", "audio/x-wav", "audio/ogg", "audio/mp4"]),
    ("videos", "film", ("Video's", "Videos"), ["video/mp4", "video/x-matroska", "video/webm", "video/x-msvideo",
                                               "video/quicktime"]),
    ("pdf", "document", ("PDF-bestanden", "PDF files"), ["application/pdf"]),
    ("tekst", "potlood", ("Tekstbestanden", "Text files"), ["text/plain"]),
]

_VB_APPS = {"internet": ("firefox.desktop", [("firefox.desktop", "Firefox"), ("org.chromium.Chromium.desktop", "Chromium")]),
            "mail": ("org.mozilla.Thunderbird.desktop", [("org.mozilla.Thunderbird.desktop", "Thunderbird")]),
            "fotos": ("org.kde.gwenview.desktop", [("org.kde.gwenview.desktop", "Gwenview (foto's bekijken)"),
                                                   ("org.kde.krita.desktop", "Krita")]),
            "muziek": ("org.kde.elisa.desktop", [("org.kde.elisa.desktop", "Elisa (muziek)"),
                                                 ("vlc.desktop", "VLC")]),
            "videos": ("org.kde.haruna.desktop", [("org.kde.haruna.desktop", "Haruna (video)"), ("vlc.desktop", "VLC")]),
            "pdf": ("org.kde.okular.desktop", [("org.kde.okular.desktop", "Okular (documenten)"),
                                               ("firefox.desktop", "Firefox")]),
            "tekst": ("org.kde.kate.desktop", [("org.kde.kate.desktop", "Kate (tekst)"),
                                               ("org.kde.kwrite.desktop", "KWrite")])}


def app_mappen() -> list[Path]:
    thuis = Path.home()
    mappen = [thuis / ".local/share/applications", thuis / ".local/share/flatpak/exports/share/applications",
              Path("/var/lib/flatpak/exports/share/applications")]
    for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if d:
            mappen.append(Path(d) / "applications")
    return mappen


def lees_mimeinfo(tekst: str) -> dict[str, list[str]]:
    """Uit: mimeinfo.cache -> {bestandstype: [programma.desktop, ...]}."""
    uit: dict[str, list[str]] = {}
    for regel in tekst.splitlines():
        if "=" in regel and not regel.startswith("["):
            soort, apps = regel.split("=", 1)
            uit.setdefault(soort.strip(), []).extend(a for a in apps.split(";") if a.strip())
    return uit


def lees_desktop_naam(tekst: str, taalcode: str = "nl") -> str | None:
    """De naam uit een .desktop-bestand (in de taal van de gebruiker); None als het programma verborgen is."""
    namen: dict[str, str] = {}
    in_hoofd = False
    for regel in tekst.splitlines():
        regel = regel.strip()
        if regel.startswith("["):
            in_hoofd = regel == "[Desktop Entry]"
        elif in_hoofd and "=" in regel:
            sleutel, waarde = (x.strip() for x in regel.split("=", 1))
            if sleutel == "NoDisplay" and waarde.lower() == "true":
                return None
            if sleutel == "Name" or sleutel == f"Name[{taalcode}]":
                namen[sleutel] = waarde
    return namen.get(f"Name[{taalcode}]") or namen.get("Name")


def app_naam(desktop_id: str, taalcode: str = "nl", ook_verborgen: bool = False) -> str | None:
    for map_ in app_mappen():
        pad = map_ / desktop_id
        if pad.is_file():
            try:
                naam = lees_desktop_naam(pad.read_text(encoding="utf-8", errors="replace"), taalcode)
            except OSError:
                return None
            if naam is None and ook_verborgen:
                return desktop_id.removesuffix(".desktop")
            return naam
    return desktop_id.removesuffix(".desktop") if ook_verborgen else None


def apps_voor(sleutel: str, taalcode: str = "nl") -> list[tuple[str, str]]:
    """[(programma.desktop, naam)] die dit soort bestanden kunnen openen."""
    if _c.VOORBEELD:
        return _VB_APPS[sleutel][1]
    soorten = next(s for s in SOORTEN if s[0] == sleutel)[3]
    gezien: dict[str, str] = {}
    for map_ in app_mappen():
        try:
            cache = lees_mimeinfo((map_ / "mimeinfo.cache").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for soort in soorten:
            for app in cache.get(soort, []):
                if app not in gezien:
                    naam = app_naam(app, taalcode)
                    if naam:
                        gezien[app] = naam
    return sorted(gezien.items(), key=lambda x: x[1].lower())


def standaard_app(sleutel: str) -> str:
    """Welk programma.desktop opent dit nu?"""
    if _c.VOORBEELD:
        if _c._VB["apps"] is None:
            _c._VB["apps"] = {k: v[0] for k, v in _VB_APPS.items()}
        return _c._VB["apps"][sleutel]
    soort = next(s for s in SOORTEN if s[0] == sleutel)[3][0]
    return _c.draai("xdg-mime", "query", "default", soort, timeout=5)[1].strip()


def zet_standaard_app(sleutel: str, desktop_id: str) -> bool:
    if _c.VOORBEELD:
        standaard_app(sleutel)
        _c._VB["apps"][sleutel] = desktop_id
        return True
    soorten = next(s for s in SOORTEN if s[0] == sleutel)[3]
    goed = _c.draai("xdg-mime", "default", desktop_id, *soorten, timeout=10)[0] == 0
    if sleutel == "internet":
        _c.draai("xdg-settings", "set", "default-web-browser", desktop_id, timeout=10)
    return goed


# ================================================================ printers ===

@dataclass
class Printer:
    naam: str           # technische naam (voor lp)
    omschrijving: str   # wat je ziet
    staat: str          # klaar, bezig of gestopt
    standaard: bool


def lees_lpstat(printers_uit: str, standaard_uit: str) -> list[Printer]:
    """Uit: lpstat -l -p (printers) en lpstat -d (de standaard)."""
    m = re.search(r"destination:\s*(\S+)", standaard_uit)
    standaard = m.group(1) if m else ""
    lijst: list[Printer] = []
    for regel in printers_uit.splitlines():
        m = re.match(r"^printer (\S+) (is idle|now printing|disabled)", regel)
        if m:
            naam, staat = m.group(1), m.group(2)
            lijst.append(Printer(naam, naam.replace("_", " "),
                                 "klaar" if staat == "is idle" else "bezig" if staat == "now printing" else "gestopt",
                                 naam == standaard))
        elif lijst and regel.strip().startswith("Description:"):
            omschrijving = regel.split(":", 1)[1].strip()
            if omschrijving:
                lijst[-1].omschrijving = omschrijving
    return lijst


def printers() -> list[Printer]:
    if _c.VOORBEELD:
        if _c._VB["printers"] is None:
            _c._VB["printers"] = [Printer("HP_LaserJet", "Bugie's HP LaserJet", "klaar", True),
                               Printer("Canon_PIXMA", "Canon PIXMA (boven)", "gestopt", False)]
        return _c._VB["printers"]
    if not shutil.which("lpstat"):
        return []
    return lees_lpstat(_c.draai("lpstat", "-l", "-p", timeout=8)[1], _c.draai("lpstat", "-d", timeout=8)[1])


def wachtrij() -> int:
    """Hoeveel documenten staan te wachten om geprint te worden."""
    if _c.VOORBEELD:
        return 1
    return len([r for r in _c.draai("lpstat", "-o", timeout=8)[1].splitlines() if r.strip()])


def zet_standaard_printer(naam: str) -> bool:
    if _c.VOORBEELD:
        for p in printers():
            p.standaard = p.naam == naam
        return True
    return _c.draai("lpoptions", "-d", naam, timeout=8)[0] == 0


def testpagina(naam: str) -> bool:
    if _c.VOORBEELD:
        return True
    proef = "/usr/share/cups/data/testprint"
    if not os.path.exists(proef):
        return False
    return _c.draai("lp", "-d", naam, proef, timeout=15)[0] == 0


def wachtrij_leegmaken() -> bool:
    if _c.VOORBEELD:
        return True
    return _c.draai("cancel", "-a", timeout=8)[0] == 0


def scanprogramma() -> str | None:
    if _c.VOORBEELD:
        return "skanpage"
    return next((p for p in ("skanpage", "skanlite", "simple-scan") if shutil.which(p)), None)
