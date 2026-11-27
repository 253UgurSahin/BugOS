"""Alle apps op deze computer die geen Flatpak zijn: voor 'Mijn apps' in de Winkel.

Zoals 'Apps' in Windows: alles wat je hebt, op één plek. Wat je kunt verwijderen heeft een knop Verwijderen; wat bij
BugOS zelf hoort (Bestanden, Instellingen, de Terminal, ...) staat er ook, maar zonder die knop.

Soorten (app['soort']):
  appimage  een Linux-programma van een website, geïnstalleerd met bugos-appimage   -> verwijderbaar
  windows   een Windows-programma (Wine, bugos-windows)                            -> verwijderbaar (eigen verwijderprogramma)
  android   een Android-app (Waydroid, bugos-android)                               -> verwijderbaar
  m365      Word, Excel, ... van Microsoft 365 in je startmenu (web-apps)           -> verwijderbaar (uit het startmenu)
  systeem   hoort bij BugOS (in /usr/share/applications)                            -> niet verwijderbaar

Elke app: {'id', 'naam', 'soort', 'icoon', 'uitleg', 'verwijderbaar', 'pad' (de starter, of ''), 'sleutel'}.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from bugos_base import t
from bugos_desktop import lees_bureaublad, vertaald

PAKKET = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
M365_VOORVOEGSEL = "bugos-m365-"


def data_map() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def systeem_mappen() -> list[Path]:
    """De mappen met de starters van BugOS zelf (niet die van Flatpak: dat zijn de 'gewone' Mijn apps)."""
    mappen = [Path(p) / "applications" for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
              if p and "flatpak" not in p]
    gezien, uit = set(), []
    for m in mappen:
        if m not in gezien:
            gezien.add(m)
            uit.append(m)
    return uit


def _zichtbaar(pad: Path) -> tuple[str, str] | None:
    """(naam, pictogram) van een starter die in het startmenu staat; None voor een verborgen of kapotte."""
    c = lees_bureaublad(pad)
    if c is None:
        return None
    s = c["Desktop Entry"]
    if (s.get("Type", "Application") != "Application" or s.get("NoDisplay", "").lower() == "true"
            or s.get("Hidden", "").lower() == "true" or not s.get("Exec", "").strip()):
        return None
    if s.get("OnlyShowIn") and "KDE" not in s.get("OnlyShowIn", "").split(";"):
        return None
    if "KDE" in s.get("NotShowIn", "").split(";"):
        return None
    return vertaald(s, "Name") or pad.stem, s.get("Icon", "")


def systeem_apps() -> list[dict]:
    """De apps die bij BugOS horen (in het startmenu). Een starter die je zelf verborg (een eigen kopie met
    NoDisplay in ~/.local/share/applications), telt niet mee."""
    eigen = data_map() / "applications"
    uit: dict[str, dict] = {}
    for map_ in systeem_mappen():
        try:
            bestanden = sorted(map_.glob("*.desktop"))
        except OSError:
            continue
        for pad in bestanden:
            if pad.name in uit or pad.name.startswith((M365_VOORVOEGSEL, "waydroid.")):
                continue
            eigen_kopie = eigen / pad.name
            info = _zichtbaar(eigen_kopie if eigen_kopie.is_file() else pad)
            if info is None:
                uit[pad.name] = {}
                continue
            naam, icoon = info
            uit[pad.name] = {"id": f"systeem:{pad.stem}", "naam": naam, "soort": "systeem", "icoon": icoon,
                             "uitleg": t("Hoort bij BugOS", "Part of BugOS"), "verwijderbaar": False,
                             "pad": str(pad), "sleutel": pad.stem}
    return sorted((a for a in uit.values() if a), key=lambda a: a["naam"].lower())


def appimage_apps() -> list[dict]:
    try:
        import bugos_appimage
        return [{"id": f"appimage:{a['id']}", "naam": a["naam"], "soort": "appimage", "icoon": a["icoon"],
                 "uitleg": t("Linux-programma van een website (AppImage)", "Linux program from a website (AppImage)"),
                 "verwijderbaar": True, "pad": str(a["starter"]), "sleutel": a["id"]}
                for a in bugos_appimage.lijst()]
    except (ImportError, OSError):
        return []


def windows_apps() -> list[dict]:
    """De Windows-programma's (wine uninstaller --list). Kan een paar seconden duren: niet in het venster zelf."""
    try:
        import bugos_windows
        return [{"id": f"windows:{p['sleutel']}", "naam": p["naam"], "soort": "windows", "icoon": "bugos-exe",
                 "uitleg": t("Windows-programma", "Windows program"), "verwijderbaar": True, "pad": "",
                 "sleutel": p["sleutel"]}
                for p in bugos_windows.programmas()]
    except (ImportError, OSError):
        return []


def android_apps() -> list[dict]:
    """De Android-apps: Waydroid zet voor elke app een starter waydroid.<pakket>.desktop in je startmenu. Zo hoeft
    Android niet te draaien om te zien wat je hebt."""
    uit = []
    map_ = data_map() / "applications"
    for pad in sorted(map_.glob("waydroid.*.desktop")) if map_.is_dir() else []:
        pakket = pad.name[len("waydroid."):-len(".desktop")]
        if not PAKKET.match(pakket):
            continue
        c = lees_bureaublad(pad)
        if c is None:
            continue
        s = c["Desktop Entry"]
        uit.append({"id": f"android:{pakket}", "naam": vertaald(s, "Name") or pakket, "soort": "android",
                    "icoon": s.get("Icon", ""), "uitleg": t("Android-app", "Android app"), "verwijderbaar": True,
                    "pad": str(pad), "sleutel": pakket})
    return sorted(uit, key=lambda a: a["naam"].lower())


def m365_apps() -> list[dict]:
    map_ = data_map() / "applications"
    uit = []
    for pad in sorted(map_.glob(f"{M365_VOORVOEGSEL}*.desktop")) if map_.is_dir() else []:
        info = _zichtbaar(pad)
        if info is None:
            continue
        uit.append({"id": f"m365:{pad.stem}", "naam": info[0], "soort": "m365", "icoon": info[1],
                    "uitleg": t("Microsoft 365 (in je browser)", "Microsoft 365 (in your browser)"),
                    "verwijderbaar": True, "pad": str(pad), "sleutel": pad.stem})
    return uit


def lokale_apps(met_windows: bool = True) -> list[dict]:
    """Alles behalve de Flatpaks: eerst wat je zelf installeerde (op soort), dan wat bij BugOS hoort."""
    eigen = m365_apps() + appimage_apps() + (windows_apps() if met_windows else []) + android_apps()
    return eigen + systeem_apps()


def open_app(app: dict) -> bool:
    """Openen zoals vanuit het startmenu."""
    from bugos_base import start
    if app["soort"] == "android":
        import bugos_android
        return bugos_android.open_app(app["sleutel"])
    if app["soort"] == "windows":
        return start("bugos-windows")   # het venster met je Windows-programma's (een programma heeft geen vaste starter)
    if app.get("pad"):
        if shutil.which("kioclient"):
            return start("kioclient", "exec", app["pad"])
        return start("gio", "launch", app["pad"])
    return False


def verwijder(app: dict) -> bool:
    """Verwijderen (blokkeert: op de achtergrond aanroepen). Een Windows-programma: zijn eigen verwijderprogramma,
    dat zelf vragen stelt. Een app van BugOS zelf: nooit."""
    if not app.get("verwijderbaar"):
        return False
    soort, sleutel = app["soort"], app.get("sleutel", "")
    if soort == "appimage":
        import bugos_appimage
        return bugos_appimage.verwijder(sleutel)
    if soort == "m365":
        if not sleutel.startswith(M365_VOORVOEGSEL) or "/" in sleutel:
            return False
        (data_map() / "applications" / f"{sleutel}.desktop").unlink(missing_ok=True)
        return True
    if soort == "windows":
        import bugos_windows
        opdracht = bugos_windows.verwijder_opdracht(sleutel)
        if not opdracht:
            return False
        try:
            return subprocess.run(opdracht, env=bugos_windows.omgeving(), capture_output=True,
                                  timeout=3600).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    if soort == "android":
        if not PAKKET.match(sleutel):
            return False
        import bugos_android
        if not bugos_android.draait() and not bugos_android.start():
            return False
        code, _ = bugos_android.draai(bugos_android.WAYDROID, "app", "remove", sleutel, timeout=120)
        if code == 0:
            (data_map() / "applications" / f"waydroid.{sleutel}.desktop").unlink(missing_ok=True)
        return code == 0
    return False
