"""BugOS Android-apps (Waydroid): de logica, zonder venster (tools/test_android.py kan het zo nagaan).

Waydroid draait een echt Android (LineageOS, zonder Google) in een container; elke app komt in een eigen venster en
in het startmenu (Waydroid maakt zelf ~/.local/share/applications/waydroid.<pakket>.desktop). BugOS zet het klaar met
één knop (bugos-android-root via pkexec), installeert een .apk met dubbelklik en zet F-Droid klaar als appwinkel.
Namen en uitvoer van waydroid nagekeken in de broncode van Waydroid (tools/helpers/arguments.py, actions/status.py,
actions/initializer.py, services/user_manager.py).

Eerlijk over de grens: Google Play zit er niet in (dat mag BugOS niet meeleveren), dus apps die Google nodig hebben
(sommige bank-apps) werken niet; en apps die alleen voor telefoonprocessors (ARM) gemaakt zijn, werken niet op een
gewone pc.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

WAYDROID = os.environ.get("BUGOS_WAYDROID", "/usr/bin/waydroid")
DATA = Path(os.environ.get("BUGOS_WAYDROID_DATA", "/var/lib/waydroid"))
ROOT_HULP = "/usr/libexec/bugos-android-root"
FDROID_URL = os.environ.get("BUGOS_FDROID_URL", "https://f-droid.org/F-Droid.apk")   # (anders: alleen voor de test)
FDROID_PAKKET = "org.fdroid.fdroid"
# Een Android-pakketnaam (com.voorbeeld.app): alleen zo'n naam gaat naar waydroid app launch/remove.
PAKKET = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")


def draai(*cmd: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def is_er() -> bool:
    return os.access(WAYDROID, os.X_OK)


def is_klaar() -> bool:
    """Zoals Waydroid zelf (initializer.is_initialized): de configuratie en het Android-systeem staan er."""
    return (DATA / "waydroid.cfg").is_file() and (DATA / "rootfs").is_dir()


def draait() -> bool:
    """waydroid status schrijft 'Session:\tRUNNING' of 'Session:\tSTOPPED'."""
    code, uit = draai(WAYDROID, "status", timeout=15)
    for regel in uit.splitlines():
        sleutel, _, waarde = regel.partition(":")
        if sleutel.strip() == "Session":
            return code == 0 and waarde.strip() == "RUNNING"
    return False


def status() -> str:
    """geen (Waydroid ontbreekt), niet-klaar, uit (klaar, Android draait niet) of aan."""
    if not is_er():
        return "geen"
    if not is_klaar():
        return "niet-klaar"
    return "aan" if draait() else "uit"


def start(wacht_s: float = 120, stap_s: float = 1.0) -> bool:
    """Android starten (waydroid session start, los) en wachten tot het draait."""
    if draait():
        return True
    try:
        subprocess.Popen([WAYDROID, "session", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        return False
    eind = time.monotonic() + wacht_s
    while time.monotonic() < eind:
        if draait():
            return True
        time.sleep(stap_s)
    return False


def stop() -> bool:
    return draai(WAYDROID, "session", "stop", timeout=30)[0] == 0


def apps() -> dict[str, str]:
    """{pakket: naam} van de geïnstalleerde Android-apps (waydroid app list: 'Name: ...' en 'packageName: ...')."""
    code, uit = draai(WAYDROID, "app", "list", timeout=30)
    lijst: dict[str, str] = {}
    naam = ""
    for regel in uit.splitlines():
        sleutel, _, waarde = regel.partition(":")
        sleutel, waarde = sleutel.strip(), waarde.strip()
        if sleutel == "Name":
            naam = waarde
        elif sleutel == "packageName" and PAKKET.match(waarde):
            lijst[waarde] = naam or waarde
            naam = ""
    return lijst


def is_apk(pad: str) -> bool:
    """Een echt .apk-bestand: de naam, en van binnen een zip (PK)."""
    p = Path(pad)
    if p.suffix.lower() != ".apk" or not p.is_file():
        return False
    try:
        with open(p, "rb") as f:
            return f.read(2) == b"PK"
    except OSError:
        return False


def installeer(pad: str) -> tuple[bool, str]:
    """(gelukt, naam van de nieuwe app of de reden). Start Android als het nog niet draait."""
    if not is_apk(pad):
        return False, "geen-apk"
    if not is_klaar():
        return False, "niet-klaar"
    if not start():
        return False, "start-niet"
    voor = apps()
    code, uit = draai(WAYDROID, "app", "install", str(Path(pad).resolve()), timeout=600)
    klein = uit.lower()
    if code != 0 or "error" in klein or "failed" in klein or "session is stopped" in klein:
        return False, "mislukt"
    # Even wachten: Android meldt een nieuwe app pas na het installeren.
    for _ in range(20):
        nieuw = {k: v for k, v in apps().items() if k not in voor}
        if nieuw:
            return True, next(iter(nieuw.values()))
        time.sleep(0.5)
    return True, Path(pad).stem   # bijgewerkt (stond er al), of Android meldt hem later


def fdroid_halen(map_: Path) -> Path | None:
    """F-Droid (de vrije Android-appwinkel) downloaden van f-droid.org. None als het niet lukte."""
    import urllib.request
    map_.mkdir(parents=True, exist_ok=True)
    doel = map_ / "F-Droid.apk"
    try:
        verzoek = urllib.request.Request(FDROID_URL, headers={"User-Agent": "BugOS"})
        with urllib.request.urlopen(verzoek, timeout=60) as r, open(doel, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError:
        return None
    return doel if is_apk(str(doel)) and doel.stat().st_size > 1_000_000 else None


def open_app(pakket: str) -> bool:
    if not PAKKET.match(pakket):
        return False
    try:
        subprocess.Popen([WAYDROID, "app", "launch", pakket], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except OSError:
        return False


def eigen_gegevens_weg(thuis: Path | None = None) -> None:
    """Na verwijderen: de Android-gegevens van jou en de starters van de Android-apps in je startmenu weg."""
    thuis = thuis or Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME") or thuis / ".local" / "share")
    shutil.rmtree(data / "waydroid", ignore_errors=True)
    for starter in (data / "applications").glob("waydroid.*.desktop"):
        starter.unlink(missing_ok=True)
    (data / "applications" / "Waydroid.desktop").unlink(missing_ok=True)
