"""BugOS: Windows-programma's (Wine) beheren. De logica, zonder venster (tools/test_programmas.py gaat het na).

Wat bugos-exe niet doet (dat opent één .exe), doet dit, zoals 'Programma's en onderdelen' in Windows:
  - de Windows-programma's die je installeerde, en ze weer verwijderen (wine uninstaller --list / --remove);
  - onderdelen van Microsoft die veel programma's nodig hebben: Visual C++, .NET, de Microsoft-lettertypen, DirectX
    (winetricks; die haalt ze bij Microsoft zelf vandaan);
  - Microsoft 365 (Word, Excel, PowerPoint, Outlook, OneDrive) in je startmenu, als web-apps in je browser. Microsoft
    365 en Office 2019 en nieuwer werken niet goed met Wine (installeren, activeren en inloggen lopen vast); in de
    browser is het de echte Office, gratis met een Microsoft-account;
  - de C:-schijf openen, en opnieuw beginnen met een lege Windows-map (de oude wordt bewaard).

Dezelfde Windows-map als bugos-exe: ~/.local/share/bugos/windows (WINEPREFIX).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

WINE = os.environ.get("BUGOS_WINE", "wine")
WINETRICKS = os.environ.get("BUGOS_WINETRICKS", "winetricks")

# (winetricks-naam, naam nl, naam en, uitleg nl, uitleg en). Alleen deze namen gaan naar winetricks.
ONDERDELEN = [
    ("vcrun2022", "Microsoft Visual C++ 2015-2022", "Microsoft Visual C++ 2015-2022",
     "Veel programma's en spellen hebben dit nodig ('MSVCP140.dll ontbreekt').",
     "Many programs and games need this ('MSVCP140.dll is missing')."),
    ("dotnet48", ".NET Framework 4.8", ".NET Framework 4.8",
     "Voor programma's die met .NET gemaakt zijn. Downloaden en installeren duurt een kwartier.",
     "For programs made with .NET. Downloading and installing takes 15 minutes."),
    ("dotnetdesktop8", ".NET Desktop Runtime 8", ".NET Desktop Runtime 8",
     "Voor nieuwere .NET-programma's ('.NET 8 is vereist').",
     "For newer .NET programs ('.NET 8 is required')."),
    ("corefonts", "Microsoft-lettertypen", "Microsoft fonts",
     "Arial, Times New Roman, Verdana en meer: documenten en programma's zien er dan uit zoals op Windows.",
     "Arial, Times New Roman, Verdana and more: documents and programs then look like on Windows."),
    ("d3dx9", "DirectX 9", "DirectX 9",
     "Voor oudere spellen ('d3dx9_43.dll ontbreekt').",
     "For older games ('d3dx9_43.dll is missing')."),
    ("vb6run", "Visual Basic 6", "Visual Basic 6",
     "Voor oude programma's ('MSVBVM60.DLL ontbreekt').",
     "For old programs ('MSVBVM60.DLL is missing')."),
]
ONDERDEEL_NAMEN = {o[0] for o in ONDERDELEN}

# Microsoft 365 als web-apps: (sleutel, naam, adres, pictogram). Alleen deze adressen gaan naar bugos-webapp.
OFFICE = [
    # Eigen, duidelijke tegels (bugos-m365-*.svg in het BugOS-pictogramthema); de algemene pictogrammen van KDE
    # (een documentje, een map) waren slecht te zien en niet te herkennen (2026-11).
    ("word", "Word", "https://www.office.com/launch/word", "bugos-m365-word"),
    ("excel", "Excel", "https://www.office.com/launch/excel", "bugos-m365-excel"),
    ("powerpoint", "PowerPoint", "https://www.office.com/launch/powerpoint", "bugos-m365-powerpoint"),
    ("outlook", "Outlook", "https://outlook.office.com/mail/", "bugos-m365-outlook"),
    ("onedrive", "OneDrive", "https://onedrive.live.com/", "bugos-m365-onedrive"),
]
OFFICE_VOORVOEGSEL = "bugos-m365-"
# Een sleutel uit 'wine uninstaller --list': meestal {GUID}, soms een naam ('Notepad++'). Nooit met - beginnen.
SLEUTEL = re.compile(r"^[A-Za-z0-9{][A-Za-z0-9{}._+ -]{0,127}$")


def prefix() -> Path:
    return Path(os.environ.get("WINEPREFIX") or Path.home() / ".local" / "share" / "bugos" / "windows")


def data_map() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def is_er() -> bool:
    return shutil.which(WINE) is not None


def is_klaar() -> bool:
    """Is de Windows-map er (de eerste keer een .exe openen maakt hem)?"""
    return (prefix() / "system.reg").is_file()


def omgeving() -> dict[str, str]:
    return {**os.environ, "WINEPREFIX": str(prefix()), "WINEDEBUG": "-all"}


def draai(*cmd: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=omgeving())
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


# ------------------------------------------------------------------------------------------- programma's

def programmas() -> list[dict]:
    """De geïnstalleerde Windows-programma's: [{'sleutel', 'naam'}], op naam (wine uninstaller --list schrijft
    '{GUID}|||Naam' per regel)."""
    if not is_klaar():
        return []
    code, uit = draai(WINE, "uninstaller", "--list", timeout=60)
    lijst = []
    for regel in uit.splitlines():
        sleutel, scheiding, naam = regel.partition("|||")
        sleutel, naam = sleutel.strip(), naam.strip()
        if scheiding and naam and SLEUTEL.match(sleutel):
            lijst.append({"sleutel": sleutel, "naam": naam})
    return sorted(lijst, key=lambda p: p["naam"].lower())


def verwijder_opdracht(sleutel: str) -> list[str] | None:
    """De opdracht die het verwijderprogramma van dat Windows-programma start (je ziet zijn eigen vensters)."""
    if not SLEUTEL.match(sleutel):
        return None
    return [WINE, "uninstaller", "--remove", sleutel]


def starters() -> list[Path]:
    """De starters die Wine in je startmenu zette (~/.local/share/applications/wine/...)."""
    map_ = data_map() / "applications" / "wine"
    return sorted(map_.rglob("*.desktop")) if map_.is_dir() else []


# ------------------------------------------------------------------------------------------- onderdelen

def onderdelen_erop() -> set[str]:
    """Welke onderdelen er al op staan: winetricks schrijft elk geïnstalleerd onderdeel in winetricks.log."""
    try:
        regels = (prefix() / "winetricks.log").read_text(errors="replace").split()
    except OSError:
        return set()
    return {r for r in regels if r in ONDERDEEL_NAMEN}


def onderdeel_opdracht(naam: str) -> list[str] | None:
    """winetricks -q <naam>: zonder vragen (-q), in de Windows-map van BugOS (WINEPREFIX in de omgeving)."""
    if naam not in ONDERDEEL_NAMEN or shutil.which(WINETRICKS) is None:
        return None
    return [WINETRICKS, "-q", naam]


def installeer_onderdeel(naam: str) -> tuple[bool, str]:
    """(gelukt, reden): geen-winetricks, onbekend, niet-klaar, mislukt."""
    opdracht = onderdeel_opdracht(naam)
    if naam not in ONDERDEEL_NAMEN:
        return False, "onbekend"
    if opdracht is None:
        return False, "geen-winetricks"
    if not is_klaar():
        return False, "niet-klaar"
    code, _uit = draai(*opdracht, timeout=3600)
    return (code == 0 and naam in onderdelen_erop()), ("" if code == 0 else "mislukt")


# ------------------------------------------------------------------------------------------- Microsoft 365

def office_staat() -> bool:
    return all((data_map() / "applications" / f"{OFFICE_VOORVOEGSEL}{k}.desktop").is_file() for k, *_ in OFFICE)


def office_aan() -> list[Path]:
    """Word, Excel, PowerPoint, Outlook en OneDrive in het startmenu (web-apps via bugos-webapp)."""
    map_ = data_map() / "applications"
    map_.mkdir(parents=True, exist_ok=True)
    gemaakt = []
    for sleutel, naam, adres, icoon in OFFICE:
        p = map_ / f"{OFFICE_VOORVOEGSEL}{sleutel}.desktop"
        p.write_text("[Desktop Entry]\nType=Application\n"
                     f"Name={naam}\nGenericName=Microsoft 365\n"
                     f"Comment=Microsoft 365 {naam} (web)\nComment[nl]=Microsoft 365 {naam} (in je browser)\n"
                     f"Exec=bugos-webapp {adres}\nIcon={icoon}\nCategories=Office;\nTerminal=false\n"
                     f"Keywords=microsoft;office;365;{sleutel};\n")
        gemaakt.append(p)
    return gemaakt


def office_bijwerken() -> bool:
    """Staat (een deel van) Microsoft 365 in het startmenu, en wijkt een starter af van wat office_aan nu schrijft
    (bijv. de oude pictogrammen), dan alles opnieuw schrijven. Geeft True als er iets veranderde."""
    map_ = data_map() / "applications"
    bestaand = [map_ / f"{OFFICE_VOORVOEGSEL}{k}.desktop" for k, *_ in OFFICE]
    if not any(p.is_file() for p in bestaand):
        return False
    voor = [p.read_text(encoding="utf-8", errors="replace") if p.is_file() else "" for p in bestaand]
    office_aan()
    return voor != [p.read_text(encoding="utf-8", errors="replace") for p in bestaand]


def office_uit() -> None:
    for sleutel, *_ in OFFICE:
        (data_map() / "applications" / f"{OFFICE_VOORVOEGSEL}{sleutel}.desktop").unlink(missing_ok=True)


def is_office_installatie(naam: str) -> bool:
    """Lijkt dit bestand op het installatieprogramma van Microsoft Office of 365 (OfficeSetup.exe, Setup.X64.nl-nl_O365...)?"""
    klein = naam.lower()
    return bool(re.search(r"officesetup|o365|microsoft ?365|office ?(19|20|21|24)|setup\.x(64|86)\.", klein))


# ------------------------------------------------------------------------------------------- de Windows-map

def opnieuw_beginnen() -> Path | None:
    """De Windows-map opzij zetten (niet weggooien: er kunnen bestanden in staan); de volgende .exe maakt een nieuwe.
    Geeft de plek van de oude map, of None als er geen was."""
    p = prefix()
    if not p.exists():
        return None
    if shutil.which("wineserver"):   # eerst alles van Windows stoppen
        subprocess.run(["wineserver", "-k"], env=omgeving(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    oud = p.with_name(f"{p.name}-oud-{time.strftime('%Y%m%d-%H%M%S')}")
    p.rename(oud)
    for starter in starters():   # hun programma's zijn er niet meer
        starter.unlink(missing_ok=True)
    return oud
