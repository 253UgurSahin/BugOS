"""BugOS Instellingen: de echte knoppen achter de instellingen.

Elke instelling praat met het gewone gereedschap van Linux/KDE:
  wifi        -> nmcli (NetworkManager)
  bluetooth   -> bluetoothctl
  geluid      -> pactl (PipeWire)
  scherm      -> kscreen-doctor (grootte), logind (helderheid), KWin (nachtlicht)
  energie     -> powerprofilesctl, /sys/class/power_supply (batterij)
  uiterlijk   -> plasma-apply-colorscheme, plasma-apply-wallpaperimage
De 'lees'-functies zijn los te testen met voorbeelduitvoer. Met BUGOS_INSTELLINGEN_VOORBEELD=1
wordt er niets aan de computer veranderd en zie je voorbeeldgegevens (voor foto's en tests).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VOORBEELD = bool(os.environ.get("BUGOS_INSTELLINGEN_VOORBEELD"))


def draai(*cmd: str, invoer: str | None = None, timeout: int = 15) -> tuple[int, str]:
    """Voer een opdracht uit; geef (code, uitvoer). Bestaat het programma niet, dan (127, '')."""
    if not shutil.which(cmd[0]):
        return 127, ""
    try:
        r = subprocess.run(list(cmd), input=invoer, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def heeft(programma: str) -> bool:
    return VOORBEELD or shutil.which(programma) is not None


# ==================================================================== wifi ===

@dataclass
class Netwerk:
    naam: str
    sterkte: int        # 0-100
    beveiligd: bool
    verbonden: bool


def splits_nmcli(regel: str) -> list[str]:
    """nmcli -t zet een ':' in een naam als '\\:' en een '\\' als '\\\\'."""
    delen, huidig, i = [], "", 0
    while i < len(regel):
        c = regel[i]
        if c == "\\" and i + 1 < len(regel):
            huidig += regel[i + 1]
            i += 2
            continue
        if c == ":":
            delen.append(huidig)
            huidig = ""
        else:
            huidig += c
        i += 1
    delen.append(huidig)
    return delen


def lees_netwerken(uitvoer: str) -> list[Netwerk]:
    """Uit: nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list. Dubbele namen: de sterkste telt."""
    beste: dict[str, Netwerk] = {}
    for regel in uitvoer.splitlines():
        d = splits_nmcli(regel)
        if len(d) < 4 or not d[1]:
            continue
        n = Netwerk(d[1], int(d[2]) if d[2].isdigit() else 0, d[3] not in ("", "--"), d[0].strip() == "*")
        oud = beste.get(n.naam)
        if oud is None or n.verbonden or (n.sterkte > oud.sterkte and not oud.verbonden):
            beste[n.naam] = n
    return sorted(beste.values(), key=lambda x: (not x.verbonden, -x.sterkte, x.naam.lower()))


_VB = {"wifi": True, "verbonden": "Thuis", "bt": True, "volume": 45, "stil": False, "uitgang": "speakers",
       "helderheid": 70, "nachtlicht": False, "schaal": 1.25, "profiel": "balanced", "donker": False,
       "bt_verbonden": {"AA:BB:CC:DD:EE:01"}}


def wifi_aan() -> bool:
    if VOORBEELD:
        return _VB["wifi"]
    return draai("nmcli", "-t", "-f", "WIFI", "radio")[1].strip() == "enabled"


def zet_wifi(aan: bool) -> bool:
    if VOORBEELD:
        _VB["wifi"] = aan
        return True
    return draai("nmcli", "radio", "wifi", "on" if aan else "off")[0] == 0


def netwerken(opnieuw_zoeken: bool = False) -> list[Netwerk]:
    if VOORBEELD:
        if not _VB["wifi"]:
            return []
        lijst = [Netwerk("Thuis", 86, True, False), Netwerk("Thuis-5G", 72, True, False),
                 Netwerk("Buren", 41, True, False), Netwerk("Bibliotheek gratis", 35, False, False),
                 Netwerk("Ziggo1234", 22, True, False)]
        for n in lijst:
            n.verbonden = n.naam == _VB["verbonden"]
        return sorted(lijst, key=lambda x: (not x.verbonden, -x.sterkte))
    _, uit = draai("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan",
                   "yes" if opnieuw_zoeken else "auto", timeout=25)
    return lees_netwerken(uit)


def verbind(naam: str, wachtwoord: str = "") -> tuple[bool, str]:
    """Verbind met een wifi-netwerk. Het wachtwoord gaat via de invoer, niet op de opdrachtregel."""
    if VOORBEELD:
        _VB["verbonden"] = naam
        return True, ""
    if wachtwoord:
        code, uit = draai("nmcli", "--ask", "device", "wifi", "connect", naam, invoer=wachtwoord + "\n", timeout=45)
    else:
        code, uit = draai("nmcli", "device", "wifi", "connect", naam, timeout=45)
    return code == 0, uit


def bekend_netwerk(naam: str) -> bool:
    """Zijn we hier al eens mee verbonden geweest (dan weet BugOS het wachtwoord nog)?"""
    if VOORBEELD:
        return naam in ("Thuis", "Thuis-5G")
    _, uit = draai("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show")
    return any(splits_nmcli(r)[:2] == [naam, "802-11-wireless"] for r in uit.splitlines())


def verbreek(naam: str) -> bool:
    if VOORBEELD:
        _VB["verbonden"] = ""
        return True
    return draai("nmcli", "connection", "down", "id", naam)[0] == 0


def kabel_verbonden() -> bool:
    if VOORBEELD:
        return False
    _, uit = draai("nmcli", "-t", "-f", "TYPE,STATE", "device")
    return any(splits_nmcli(r)[:2] == ["ethernet", "connected"] for r in uit.splitlines())


# =============================================================== bluetooth ===

@dataclass
class Apparaat:
    adres: str
    naam: str
    soort: str          # icoon-naam van bluez, bv. audio-headset, input-mouse, phone
    verbonden: bool
    batterij: int | None


def lees_bt_aan(uitvoer: str) -> bool:
    return any(r.strip() == "Powered: yes" for r in uitvoer.splitlines())


def lees_bt_apparaten(uitvoer: str) -> list[tuple[str, str]]:
    """Uit: bluetoothctl devices Paired -> [(adres, naam)]."""
    lijst = []
    for regel in uitvoer.splitlines():
        m = re.match(r"^Device ([0-9A-F:]{17}) (.+)$", regel.strip())
        if m:
            lijst.append((m.group(1), m.group(2)))
    return lijst


def lees_bt_info(adres: str, naam: str, uitvoer: str) -> Apparaat:
    soort, verbonden, batterij = "", False, None
    for regel in uitvoer.splitlines():
        regel = regel.strip()
        if regel.startswith("Icon:"):
            soort = regel.split(":", 1)[1].strip()
        elif regel.startswith("Connected:"):
            verbonden = regel.endswith("yes")
        elif regel.startswith("Battery Percentage:"):
            m = re.search(r"\((\d+)\)", regel)
            batterij = int(m.group(1)) if m else None
    return Apparaat(adres, naam, soort, verbonden, batterij)


def bt_aan() -> bool:
    if VOORBEELD:
        return _VB["bt"]
    return lees_bt_aan(draai("bluetoothctl", "show", timeout=5)[1])


def zet_bt(aan: bool) -> bool:
    if VOORBEELD:
        _VB["bt"] = aan
        return True
    if aan and shutil.which("rfkill"):
        draai("rfkill", "unblock", "bluetooth")
    return draai("bluetoothctl", "power", "on" if aan else "off", timeout=8)[0] == 0


def bt_apparaten() -> list[Apparaat]:
    if VOORBEELD:
        lijst = [Apparaat("AA:BB:CC:DD:EE:01", "Koptelefoon van oma", "audio-headset", False, 80),
                 Apparaat("AA:BB:CC:DD:EE:02", "Muis", "input-mouse", False, None),
                 Apparaat("AA:BB:CC:DD:EE:03", "Telefoon", "phone", False, None)]
        for a in lijst:
            a.verbonden = a.adres in _VB["bt_verbonden"]
        return lijst
    code, uit = draai("bluetoothctl", "devices", "Paired", timeout=5)
    paren = lees_bt_apparaten(uit)
    if code != 0 or not paren:
        paren = lees_bt_apparaten(draai("bluetoothctl", "paired-devices", timeout=5)[1])
    return [lees_bt_info(a, n, draai("bluetoothctl", "info", a, timeout=5)[1]) for a, n in paren]


def bt_verbind(adres: str, aan: bool) -> bool:
    if VOORBEELD:
        (_VB["bt_verbonden"].add if aan else _VB["bt_verbonden"].discard)(adres)
        return True
    return draai("bluetoothctl", "connect" if aan else "disconnect", adres, timeout=20)[0] == 0


def bt_vergeet(adres: str) -> bool:
    if VOORBEELD:
        return True
    return draai("bluetoothctl", "remove", adres, timeout=10)[0] == 0


# ================================================================== geluid ===

@dataclass
class Uitgang:
    naam: str           # technische naam (voor pactl)
    omschrijving: str   # wat je ziet, bv. "Ingebouwde luidsprekers"
    standaard: bool


def lees_uitgangen(json_tekst: str, standaard: str) -> list[Uitgang]:
    """Uit: pactl -f json list sinks (en pactl get-default-sink)."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return []
    return [Uitgang(s.get("name", ""), s.get("description") or s.get("name", ""), s.get("name") == standaard)
            for s in data if isinstance(s, dict) and s.get("name")]


def lees_volume(json_tekst: str, naam: str) -> tuple[int, bool]:
    """(volume in procent, stil) van één uitgang, uit pactl -f json list sinks."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return 0, False
    for s in data:
        if isinstance(s, dict) and s.get("name") == naam:
            kanalen = [v.get("value_percent", "0%") for v in (s.get("volume") or {}).values() if isinstance(v, dict)]
            procent = [int(str(k).rstrip("%")) for k in kanalen if str(k).rstrip("%").isdigit()]
            return (round(sum(procent) / len(procent)) if procent else 0), bool(s.get("mute"))
    return 0, False


def geluid() -> tuple[int, bool, list[Uitgang]]:
    """(volume, stil, uitgangen)."""
    if VOORBEELD:
        return _VB["volume"], _VB["stil"], [
            Uitgang("speakers", "Ingebouwde luidsprekers", _VB["uitgang"] == "speakers"),
            Uitgang("hdmi", "Televisie (HDMI)", _VB["uitgang"] == "hdmi"),
            Uitgang("headset", "Koptelefoon van oma", _VB["uitgang"] == "headset")]
    standaard = draai("pactl", "get-default-sink", timeout=5)[1].strip()
    uit = draai("pactl", "-f", "json", "list", "sinks", timeout=5)[1]
    volume, stil = lees_volume(uit, standaard)
    return volume, stil, lees_uitgangen(uit, standaard)


def zet_volume(procent: int) -> None:
    if VOORBEELD:
        _VB["volume"] = procent
        return
    draai("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{max(0, min(procent, 100))}%", timeout=5)


def zet_stil(stil: bool) -> None:
    if VOORBEELD:
        _VB["stil"] = stil
        return
    draai("pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if stil else "0", timeout=5)


def kies_uitgang(naam: str) -> None:
    if VOORBEELD:
        _VB["uitgang"] = naam
        return
    draai("pactl", "set-default-sink", naam, timeout=5)


# ================================================================== scherm ===

def backlight() -> Path | None:
    """De schermverlichting van een laptop (een losse monitor heeft dit meestal niet)."""
    basis = Path(os.environ.get("BUGOS_SYS", "/sys")) / "class" / "backlight"
    for pad in sorted(basis.glob("*")):
        if (pad / "max_brightness").exists():
            return pad
    return None


def helderheid() -> int | None:
    if VOORBEELD:
        return _VB["helderheid"]
    pad = backlight()
    if pad is None:
        return None
    try:
        return round(int((pad / "brightness").read_text()) / max(int((pad / "max_brightness").read_text()), 1) * 100)
    except (OSError, ValueError):
        return None


def zet_helderheid(procent: int) -> None:
    """Via logind: dat mag zonder wachtwoord voor wie achter de computer zit."""
    if VOORBEELD:
        _VB["helderheid"] = procent
        return
    pad = backlight()
    if pad is None:
        return
    try:
        maximum = int((pad / "max_brightness").read_text())
    except (OSError, ValueError):
        return
    waarde = max(1, round(maximum * max(5, min(procent, 100)) / 100))
    draai("gdbus", "call", "--system", "--dest", "org.freedesktop.login1", "--object-path",
          "/org/freedesktop/login1/session/auto", "--method", "org.freedesktop.login1.Session.SetBrightness",
          "backlight", pad.name, str(waarde), timeout=5)


def lees_schalen(json_tekst: str) -> list[tuple[str, float]]:
    """Uit: kscreen-doctor -j -> [(naam, schaal)] van de schermen die aan staan."""
    try:
        data = json.loads(json_tekst or "{}")
    except ValueError:
        return []
    return [(o.get("name", ""), float(o.get("scale", 1.0))) for o in data.get("outputs", [])
            if isinstance(o, dict) and o.get("enabled") and o.get("connected", True)]


def schaal() -> float:
    if VOORBEELD:
        return _VB["schaal"]
    schermen = lees_schalen(draai("kscreen-doctor", "-j", timeout=8)[1])
    return schermen[0][1] if schermen else 1.0


def zet_schaal(waarde: float) -> bool:
    if VOORBEELD:
        _VB["schaal"] = waarde
        return True
    schermen = lees_schalen(draai("kscreen-doctor", "-j", timeout=8)[1])
    if not schermen:
        return False
    opdracht = ["kscreen-doctor"] + [f"output.{naam}.scale.{waarde:g}" for naam, _s in schermen]
    return draai(*opdracht, timeout=15)[0] == 0


def kde_lees(bestand: str, groep: str, sleutel: str, standaard: str = "") -> str:
    if not shutil.which("kreadconfig6"):
        return standaard
    return draai("kreadconfig6", "--file", bestand, "--group", groep, "--key", sleutel, "--default", standaard,
                 timeout=5)[1].strip()


def nachtlicht() -> bool:
    if VOORBEELD:
        return _VB["nachtlicht"]
    return kde_lees("kwinrc", "NightColor", "Active", "false") == "true"


def zet_nachtlicht(aan: bool) -> None:
    """Warmer licht 's avonds (zoals 'Nachtlampje' in Windows); KWin regelt de tijden zelf."""
    if VOORBEELD:
        _VB["nachtlicht"] = aan
        return
    draai("kwriteconfig6", "--file", "kwinrc", "--group", "NightColor", "--key", "Active", "true" if aan else "false")
    draai("gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin", "--method",
          "org.kde.KWin.reconfigure", timeout=5)


# ================================================================= energie ===

PROFIELEN = ("power-saver", "balanced", "performance")


def energieprofiel() -> str | None:
    if VOORBEELD:
        return _VB["profiel"]
    code, uit = draai("powerprofilesctl", "get", timeout=5)
    return uit.strip() if code == 0 and uit.strip() in PROFIELEN else None


def zet_energieprofiel(profiel: str) -> bool:
    if VOORBEELD:
        _VB["profiel"] = profiel
        return True
    return draai("powerprofilesctl", "set", profiel, timeout=8)[0] == 0


@dataclass
class Batterij:
    procent: int
    laadt: bool
    vol: bool


def batterij() -> Batterij | None:
    if VOORBEELD:
        return Batterij(76, False, False)
    basis = Path(os.environ.get("BUGOS_SYS", "/sys")) / "class" / "power_supply"
    for pad in sorted(basis.glob("BAT*")):
        try:
            procent = int((pad / "capacity").read_text().strip())
            staat = (pad / "status").read_text().strip()
        except (OSError, ValueError):
            continue
        return Batterij(procent, staat == "Charging", staat == "Full")
    return None


# =============================================================== uiterlijk ===

def donker() -> bool:
    if VOORBEELD:
        return _VB["donker"]
    return kde_lees("kdeglobals", "General", "ColorScheme", "BugOSLicht") == "BugOSDonker"


def zet_donker(aan: bool) -> None:
    if VOORBEELD:
        _VB["donker"] = aan
        return
    draai("plasma-apply-colorscheme", "BugOSDonker" if aan else "BugOSLicht")
    draai("plasma-apply-desktoptheme", "breeze-dark" if aan else "default")


def bugos_achtergronden() -> list[tuple[str, str]]:
    """[(naam, pad)] van de achtergronden van BugOS zelf."""
    basis = Path(os.environ.get("BUGOS_ACHTERGRONDEN", "/usr/share/wallpapers/bugos/contents"))
    lijst = []
    for naam, map_ in (("Stip (licht)", "images"), ("Stip (donker)", "images_dark")):
        beelden = sorted((basis / map_).glob("*.jpg"))
        if beelden:
            lijst.append((naam, str(beelden[0])))
    return lijst


def zet_achtergrond(pad: str) -> bool:
    if VOORBEELD:
        return True
    return draai("plasma-apply-wallpaperimage", pad, timeout=15)[0] == 0
