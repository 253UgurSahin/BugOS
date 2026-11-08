"""BugOS Instellingen: de echte knoppen achter de instellingen.

Elke instelling praat met het gewone gereedschap van Linux/KDE:
  wifi        -> nmcli (NetworkManager)
  bluetooth   -> bluetoothctl
  geluid      -> pactl (PipeWire)
  scherm      -> kscreen-doctor (grootte), logind (helderheid), KWin (nachtlicht)
  energie     -> powerprofilesctl, /sys/class/power_supply (batterij), powerdevilrc (scherm uit, slapen)
  uiterlijk   -> plasma-apply-colorscheme, plasma-apply-wallpaperimage
  zien        -> kdeglobals (grote letters), kcminputrc (grote aanwijzer), KWin (vergrootglas), kaccessrc
  muis        -> KWin via D-Bus (busctl), kdeglobals (dubbelklik)
  tijd        -> timedatectl, plasma-localerc (taal)
  inloggen    -> AccountsService (naam, wachtwoord), bugos-login (zonder wachtwoord), kscreenlockerrc
  meldingen   -> plasmanotifyrc
  programma's -> xdg-mime, xdg-settings
  printers    -> lpstat, lpoptions, lp (CUPS)
De 'lees'-functies zijn los te testen met voorbeelduitvoer. Met BUGOS_INSTELLINGEN_VOORBEELD=1
wordt er niets aan de computer veranderd en zie je voorbeeldgegevens (voor foto's en tests).

Hier staat wat alle onderdelen delen (draai, VOORBEELD, de voorbeeldgegevens, de KDE-hulpjes); de
onderdelen zelf staan in bugos_config_netwerk, _scherm, _zien, _account en _meldingen. Importeer
altijd bugos_config: alles staat hier ook.
"""

from __future__ import annotations

import os
import shutil
import subprocess

VOORBEELD = bool(os.environ.get("BUGOS_INSTELLINGEN_VOORBEELD"))


def omgeving(programma: str) -> dict[str, str]:
    """De omgeving voor een opdracht. We lezen de uitvoer, dus die moet in het Engels (C.UTF-8): anders zegt
    nmcli 'ingeschakeld' en lpstat 'Drucker'. Onze eigen bugos-hulpjes houden je taal (die laten meldingen zien)."""
    env = dict(os.environ)
    if not os.path.basename(programma).startswith("bugos-"):
        env["LC_ALL"] = "C.UTF-8"
        env.pop("LANGUAGE", None)
    return env


def draai(*cmd: str, invoer: str | None = None, timeout: int = 15) -> tuple[int, str]:
    """Voer een opdracht uit; geef (code, uitvoer). Bestaat het programma niet, dan (127, '')."""
    if not shutil.which(cmd[0]):
        return 127, ""
    try:
        r = subprocess.run(list(cmd), input=invoer, capture_output=True, text=True, timeout=timeout,
                           env=omgeving(cmd[0]))
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def heeft(programma: str) -> bool:
    return VOORBEELD or shutil.which(programma) is not None


_VB = {"wifi": True, "verbonden": "Home", "bt": True, "volume": 45, "stil": False, "uitgang": "speakers",
       "helderheid": 70, "nachtlicht": False, "schaal": 1.25, "profiel": "balanced", "donker": False,
       "bt_verbonden": {"AA:BB:CC:DD:EE:01"},
       "grote_tekst": False, "grote_aanwijzer": False, "schud": True, "plaktoetsen": False, "langzame_toetsen": False,
       "schermlezer": False, "dubbelklik": True, "aanwijzers": None, "tijd_auto": True, "zone": "Europe/Amsterdam",
       "taal": "en", "auto_inloggen": False, "slot_na": 15, "slot_na_slapen": True, "scherm_uit": 600,
       "slaap": 1800, "aanuit": 16, "deksel": 1, "niet_storen": False, "stil_bij_games": True, "geluidje": True,
       "apps": None, "printers": None, "volledige_naam": "Bugie"}


# ============================================================ kde-helpers ===

def kde_lees(bestand: str, groep: str, sleutel: str, standaard: str = "") -> str:
    if not shutil.which("kreadconfig6"):
        return standaard
    return draai("kreadconfig6", "--file", bestand, "--group", groep, "--key", sleutel, "--default", standaard,
                 timeout=5)[1].strip()


def kde_lees_groepen(bestand: str, groepen: list[str], sleutel: str, standaard: str = "") -> str:
    """Zoals kde_lees, maar voor een groep in een groep (bv. [AC][Display] in powerdevilrc)."""
    if not shutil.which("kreadconfig6"):
        return standaard
    cmd = ["kreadconfig6", "--file", bestand]
    for g in groepen:
        cmd += ["--group", g]
    cmd += ["--key", sleutel, "--default", standaard]
    return draai(*cmd, timeout=5)[1].strip()


def kde_schrijf(bestand: str, groepen: str | list[str], sleutel: str, waarde: str | None) -> bool:
    """Schrijf één KDE-instelling en zeg het tegen de programma's die open staan (--notify).
    waarde None haalt de instelling weg."""
    cmd = ["kwriteconfig6", "--file", bestand]
    for g in [groepen] if isinstance(groepen, str) else groepen:
        cmd += ["--group", g]
    cmd += ["--key", sleutel, "--notify"]
    cmd += ["--delete"] if waarde is None else [waarde]
    return draai(*cmd, timeout=5)[0] == 0


def kwin_herlees() -> None:
    draai("gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin", "--method",
          "org.kde.KWin.reconfigure", timeout=5)


def kwin_sneltoets(naam: str) -> bool:
    """Doe wat een sneltoets van KWin doet (bv. view_zoom_in), zonder dat je de toetsen hoeft te kennen."""
    if VOORBEELD:
        return True
    return draai("gdbus", "call", "--session", "--dest", "org.kde.kglobalaccel", "--object-path", "/component/kwin",
                 "--method", "org.kde.kglobalaccel.Component.invokeShortcut", naam, timeout=5)[0] == 0


# ============================================================ onderdelen ===
# Elke instelling staat in een eigen bestand (bugos_config_<onderdeel>.py). Die gebruiken draai, VOORBEELD
# en _VB via deze module, dus pas hier onderaan laden, als die al bestaan.
from bugos_config_netwerk import *  # noqa: E402,F401,F403  wifi, bluetooth
from bugos_config_scherm import *  # noqa: E402,F401,F403  geluid, scherm, energie, uiterlijk
from bugos_config_scherm import _energie_getal, _zet_energie  # noqa: E402,F401
from bugos_config_zien import *  # noqa: E402,F401,F403  makkelijker zien, muis en touchpad
from bugos_config_zien import _busctl  # noqa: E402,F401
from bugos_config_account import *  # noqa: E402,F401,F403  tijd en taal, inloggen
from bugos_config_account import _accounts, _accounts_dbus  # noqa: E402,F401
from bugos_config_meldingen import *  # noqa: E402,F401,F403  meldingen, programma's, printers
from bugos_config_meldingen import _VB_APPS  # noqa: E402,F401
