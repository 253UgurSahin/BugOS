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


_VB = {"wifi": True, "verbonden": "Home", "bt": True, "volume": 45, "stil": False, "uitgang": "speakers",
       "helderheid": 70, "nachtlicht": False, "schaal": 1.25, "profiel": "balanced", "donker": False,
       "bt_verbonden": {"AA:BB:CC:DD:EE:01"},
       "grote_tekst": False, "grote_aanwijzer": False, "schud": True, "plaktoetsen": False, "langzame_toetsen": False,
       "schermlezer": False, "dubbelklik": True, "aanwijzers": None, "tijd_auto": True, "zone": "Europe/Amsterdam",
       "taal": "en", "auto_inloggen": False, "slot_na": 15, "slot_na_slapen": True, "scherm_uit": 600,
       "slaap": 1800, "aanuit": 16, "deksel": 1, "niet_storen": False, "stil_bij_games": True, "geluidje": True,
       "apps": None, "printers": None, "volledige_naam": "Bugie"}


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
        lijst = [Apparaat("AA:BB:CC:DD:EE:01", "Bugie's headphones", "audio-headset", False, 80),
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
            Uitgang("speakers", "Built-in speakers", _VB["uitgang"] == "speakers"),
            Uitgang("hdmi", "TV (HDMI)", _VB["uitgang"] == "hdmi"),
            Uitgang("headset", "Bugie's headphones", _VB["uitgang"] == "headset")]
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
    return kde_lees("kdeglobals", "General", "ColorScheme", "BugOSLight") == "BugOSDark"


def zet_donker(aan: bool) -> None:
    if VOORBEELD:
        _VB["donker"] = aan
        return
    # Eén plek voor licht/donker: kleuren, KDE-programma's (Kvantum) en de Plasma-stijl.
    draai("bugos-theme", "donker" if aan else "licht", timeout=30)


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


# ============================================================ kde-helpers ===

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


# ======================================================== makkelijker zien ===

GEWONE_LETTERS = 10
GROTE_LETTERS = 12


def letter(familie: str, punten: int, dikte: int = 400) -> str:
    """Een lettertype zoals KDE het opschrijft in kdeglobals."""
    return f"{familie},{punten},-1,5,{dikte},0,0,0,0,0,0,0,0,0,0,1"


def lees_letter(tekst: str) -> tuple[str, int]:
    """'Inter,10,-1,5,400,...' -> ('Inter', 10)."""
    delen = tekst.split(",")
    try:
        return (delen[0].strip() or "Inter"), int(float(delen[1]))
    except (IndexError, ValueError):
        return "Inter", GEWONE_LETTERS


def grote_tekst() -> bool:
    if VOORBEELD:
        return _VB["grote_tekst"]
    return lees_letter(kde_lees("kdeglobals", "General", "font", ""))[1] >= GROTE_LETTERS


def zet_grote_tekst(aan: bool) -> None:
    """Grotere letters overal: menu's, knoppen, vensters. De lettersoort blijft wat hij was."""
    if VOORBEELD:
        _VB["grote_tekst"] = aan
        return
    familie, _p = lees_letter(kde_lees("kdeglobals", "General", "font", ""))
    punten = GROTE_LETTERS if aan else GEWONE_LETTERS
    for sleutel in ("font", "menuFont", "toolBarFont"):
        kde_schrijf("kdeglobals", "General", sleutel, letter(familie, punten))
    kde_schrijf("kdeglobals", "General", "smallestReadableFont", letter(familie, punten - 2))
    kde_schrijf("kdeglobals", "WM", "activeFont", letter(familie, punten, 600))
    draai("gdbus", "emit", "--session", "--object-path", "/KDEPlatformTheme", "--signal",
          "org.kde.KDEPlatformTheme.refreshFonts", timeout=5)
    kwin_herlees()


GEWONE_AANWIJZER = 24
GROTE_AANWIJZER = 48


def grote_aanwijzer() -> bool:
    if VOORBEELD:
        return _VB["grote_aanwijzer"]
    try:
        return int(kde_lees("kcminputrc", "Mouse", "cursorSize", str(GEWONE_AANWIJZER))) >= GROTE_AANWIJZER
    except ValueError:
        return False


def zet_grote_aanwijzer(aan: bool) -> None:
    if VOORBEELD:
        _VB["grote_aanwijzer"] = aan
        return
    maat = str(GROTE_AANWIJZER if aan else GEWONE_AANWIJZER)
    thema = kde_lees("kcminputrc", "Mouse", "cursorTheme", "breeze_cursors") or "breeze_cursors"
    if shutil.which("plasma-apply-cursortheme") and \
            draai("plasma-apply-cursortheme", "--size", maat, thema, timeout=10)[0] == 0:
        return
    kde_schrijf("kcminputrc", "Mouse", "cursorSize", maat)
    kwin_herlees()


def schud_aanwijzer() -> bool:
    """Schud je de muis, dan wordt de aanwijzer even groot zodat je hem terugvindt."""
    if VOORBEELD:
        return _VB["schud"]
    return kde_lees("kwinrc", "Plugins", "shakecursorEnabled", "true") == "true"


def zet_schud_aanwijzer(aan: bool) -> None:
    if VOORBEELD:
        _VB["schud"] = aan
        return
    kde_schrijf("kwinrc", "Plugins", "shakecursorEnabled", "true" if aan else "false")
    kwin_herlees()


def vergrootglas(stap: int) -> bool:
    """stap +1 = inzoomen, -1 = uitzoomen, 0 = gewone grootte (het vergrootglas van KWin)."""
    if not VOORBEELD and kde_lees("kwinrc", "Plugins", "zoomEnabled", "true") != "true":
        kde_schrijf("kwinrc", "Plugins", "zoomEnabled", "true")
        kwin_herlees()
    return kwin_sneltoets("view_zoom_in" if stap > 0 else "view_zoom_out" if stap < 0 else "view_actual_size")


TOETSHULP = {"plaktoetsen": ("Keyboard", "StickyKeys"), "langzame_toetsen": ("Keyboard", "SlowKeys"),
             "schermlezer": ("ScreenReader", "Enabled")}


def toetshulp(naam: str) -> bool:
    if VOORBEELD:
        return _VB[naam]
    groep, sleutel = TOETSHULP[naam]
    return kde_lees("kaccessrc", groep, sleutel, "false") == "true"


def zet_toetshulp(naam: str, aan: bool) -> None:
    """Plaktoetsen, langzame toetsen en de schermlezer: kaccess van KDE regelt het verder."""
    if VOORBEELD:
        _VB[naam] = aan
        return
    groep, sleutel = TOETSHULP[naam]
    kde_schrijf("kaccessrc", groep, sleutel, "true" if aan else "false")
    if shutil.which("kaccess"):
        try:
            subprocess.Popen(["kaccess"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass


def kan_schermlezer() -> bool:
    return VOORBEELD or shutil.which("orca") is not None


# ======================================================== muis en touchpad ===

@dataclass
class Aanwijzer:
    """Een muis of touchpad, zoals KWin hem kent."""
    sysnaam: str
    naam: str
    touchpad: bool
    aan: bool
    linkshandig: bool
    natuurlijk: bool    # scrollen 'zoals op een telefoon'
    snelheid: int       # 0-100
    tikken: bool        # tikken om te klikken (touchpad)
    kan: set[str]       # welke dingen dit apparaat kan: aan, linkshandig, natuurlijk, snelheid, tikken


def lees_busctl(uitvoer: str) -> list:
    """Uit: busctl ... --json=short (één JSON per regel) -> de waarden."""
    waarden = []
    for regel in uitvoer.splitlines():
        regel = regel.strip()
        if not regel.startswith("{"):
            continue
        try:
            d = json.loads(regel)
        except ValueError:
            continue
        waarden.append(d.get("data"))
    return waarden


def _busctl(*args: str) -> list:
    return lees_busctl(draai("busctl", "--user", *args, "--json=short", timeout=5)[1])


def lees_aanwijzer(sysnaam: str, eigenschappen: dict) -> Aanwijzer | None:
    """Uit: de eigenschappen (GetAll) van org.kde.KWin.InputDevice."""
    def w(naam: str, standaard=None):
        v = eigenschappen.get(naam)
        if isinstance(v, dict) and "data" in v:   # busctl schrijft een variant als {"type": "b", "data": true}
            v = v["data"]
        return standaard if v is None else v
    if not w("pointer", False):
        return None
    kan = {naam for naam, sleutel in (("aan", "supportsDisableEvents"), ("linkshandig", "supportsLeftHanded"),
                                      ("natuurlijk", "supportsNaturalScroll"), ("snelheid", "supportsPointerAcceleration"),
                                      ("tikken", "supportsTapToClick")) if w(sleutel, False)}
    versnelling = w("pointerAcceleration", 0.0) or 0.0
    return Aanwijzer(sysnaam, str(w("name", sysnaam)), bool(w("touchpad", False)), bool(w("enabled", True)),
                     bool(w("leftHanded", False)), bool(w("naturalScroll", False)),
                     max(0, min(100, round((float(versnelling) + 1) * 50))), bool(w("tapToClick", False)), kan)


def aanwijzers() -> list[Aanwijzer]:
    if VOORBEELD:
        if _VB["aanwijzers"] is None:
            _VB["aanwijzers"] = [
                Aanwijzer("event5", "Muis van Logitech", False, True, False, False, 50, False,
                          {"linkshandig", "natuurlijk", "snelheid"}),
                Aanwijzer("event7", "Touchpad", True, True, False, True, 55, True,
                          {"aan", "linkshandig", "natuurlijk", "snelheid", "tikken"})]
        return _VB["aanwijzers"]
    namen = _busctl("get-property", "org.kde.KWin", "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager",
                    "devicesSysNames")
    lijst = []
    for sysnaam in (namen[0] if namen and isinstance(namen[0], list) else []):
        alles = _busctl("call", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}", "org.freedesktop.DBus.Properties",
                        "GetAll", "s", "org.kde.KWin.InputDevice")
        if alles and isinstance(alles[0], list) and alles[0] and isinstance(alles[0][0], dict):
            a = lees_aanwijzer(sysnaam, alles[0][0])
            if a is not None:
                lijst.append(a)
    return sorted(lijst, key=lambda a: (a.touchpad, a.naam.lower()))


EIGENSCHAP = {"aan": ("enabled", "b"), "linkshandig": ("leftHanded", "b"), "natuurlijk": ("naturalScroll", "b"),
              "snelheid": ("pointerAcceleration", "d"), "tikken": ("tapToClick", "b")}


def zet_aanwijzer(sysnaam: str, wat: str, waarde: bool | int) -> bool:
    """Zet iets om op een muis of touchpad; KWin onthoudt het zelf (in kcminputrc)."""
    if VOORBEELD:
        for a in aanwijzers():
            if a.sysnaam == sysnaam:
                setattr(a, wat, waarde)
        return True
    sleutel, soort = EIGENSCHAP[wat]
    tekst = f"{(int(waarde) / 50) - 1:.2f}" if soort == "d" else ("true" if waarde else "false")
    return draai("busctl", "--user", "set-property", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}",
                 "org.kde.KWin.InputDevice", sleutel, soort, tekst, timeout=5)[0] == 0


def dubbelklik() -> bool:
    """Dubbelklikken om te openen (zoals in Windows); anders opent één klik."""
    if VOORBEELD:
        return _VB["dubbelklik"]
    return kde_lees("kdeglobals", "KDE", "SingleClick", "false") != "true"


def zet_dubbelklik(aan: bool) -> None:
    if VOORBEELD:
        _VB["dubbelklik"] = aan
        return
    kde_schrijf("kdeglobals", "KDE", "SingleClick", "false" if aan else "true")


# ============================================================ tijd en taal ===

@dataclass
class Tijd:
    zone: str           # bv. Europe/Amsterdam
    auto: bool          # klok vanzelf gelijkzetten via internet
    gelijk: bool        # en dat is ook gelukt


def lees_timedatectl(uitvoer: str) -> Tijd:
    """Uit: timedatectl show."""
    d = dict(r.split("=", 1) for r in uitvoer.splitlines() if "=" in r)
    return Tijd(d.get("Timezone", "") or "UTC", d.get("NTP", "no") == "yes", d.get("NTPSynchronized", "no") == "yes")


def tijd() -> Tijd:
    if VOORBEELD:
        return Tijd(_VB["zone"], _VB["tijd_auto"], _VB["tijd_auto"])
    return lees_timedatectl(draai("timedatectl", "show", timeout=5)[1])


WERELDDEEL = {"Europe": ("Europa", "Europe"), "America": ("Amerika", "America"), "Asia": ("Azië", "Asia"),
              "Africa": ("Afrika", "Africa"), "Australia": ("Australië", "Australia"),
              "Pacific": ("Stille Oceaan", "Pacific"), "Atlantic": ("Atlantische Oceaan", "Atlantic"),
              "Indian": ("Indische Oceaan", "Indian Ocean"), "Antarctica": ("Antarctica", "Antarctica"),
              "Arctic": ("Noordpool", "Arctic")}


def mooie_zone(zone: str, nl: bool = True) -> str:
    """'Europe/Amsterdam' -> 'Amsterdam (Europa)'."""
    if "/" not in zone:
        return zone
    deel, stad = zone.split("/", 1)
    stad = stad.replace("_", " ").replace("/", " / ")
    naam = WERELDDEEL.get(deel)
    return f"{stad} ({naam[0] if nl else naam[1]})" if naam else f"{stad} ({deel})"


def tijdzones() -> list[str]:
    if VOORBEELD:
        return ["Europe/Amsterdam", "Europe/Brussels", "Europe/Berlin", "Europe/London", "Europe/Istanbul",
                "America/New_York", "America/Curacao", "Asia/Tokyo", "Australia/Sydney"]
    zones = [z.strip() for z in draai("timedatectl", "list-timezones", timeout=5)[1].splitlines()]
    return [z for z in zones if "/" in z and not z.startswith("Etc/")]


def zet_tijdzone(zone: str) -> bool:
    """Via timedatectl; KDE vraagt het wachtwoord, net als Windows."""
    if VOORBEELD:
        _VB["zone"] = zone
        return True
    return draai("timedatectl", "set-timezone", zone, timeout=60)[0] == 0


def zet_tijd_auto(aan: bool) -> bool:
    if VOORBEELD:
        _VB["tijd_auto"] = aan
        return True
    return draai("timedatectl", "set-ntp", "true" if aan else "false", timeout=60)[0] == 0


# (code, landcode voor de klok en getallen, naam in die taal zelf)
TALEN = [("en", "en_US", "English"), ("nl", "nl_NL", "Nederlands"), ("de", "de_DE", "Deutsch"),
         ("fr", "fr_FR", "Français"), ("es", "es_ES", "Español"), ("it", "it_IT", "Italiano"),
         ("pt", "pt_PT", "Português"), ("pl", "pl_PL", "Polski"), ("tr", "tr_TR", "Türkçe"),
         ("uk", "uk_UA", "Українська"), ("ar", "ar_EG", "العربية")]


def taal() -> str:
    if VOORBEELD:
        return _VB["taal"]
    tekst = kde_lees("plasma-localerc", "Translations", "LANGUAGE", "")
    if not tekst:
        tekst = kde_lees("plasma-localerc", "Formats", "LANG", "") or os.environ.get("LANG", "")
    code = tekst.split(":")[0].split(".")[0].split("_")[0].lower()
    return code if any(code == c for c, _l, _n in TALEN) else "en"


def zet_taal(code: str) -> bool:
    """De taal van KDE en de BugOS-programma's; geldt na opnieuw inloggen (zo doet KDE dat ook)."""
    if VOORBEELD:
        _VB["taal"] = code
        return True
    land = next((land for c, land, _n in TALEN if c == code), None)
    if land is None:
        return False
    goed = kde_schrijf("plasma-localerc", "Translations", "LANGUAGE", code if code == "en" else f"{code}:en_US")
    goed = kde_schrijf("plasma-localerc", "Formats", "LANG", f"{land}.UTF-8") and goed
    return goed


def afmelden() -> None:
    """Vraag netjes of je wilt afmelden (het scherm van KDE)."""
    if VOORBEELD:
        return
    draai("gdbus", "call", "--session", "--dest", "org.kde.LogoutPrompt", "--object-path", "/LogoutPrompt",
          "--method", "org.kde.LogoutPrompt.promptLogout", timeout=5)


# ================================================== inloggen en wachtwoord ===

@dataclass
class Gebruiker:
    naam: str               # inlognaam, bv. bugie
    volledige_naam: str     # bv. Bugie
    beheerder: bool
    auto_inloggen: bool


SDDM_BESTANDEN = ("/etc/sddm.conf", "/etc/sddm.conf.d")


def lees_autologin(teksten: list[str], naam: str) -> bool:
    """Staat in een sddm-bestand [Autologin] User=<naam>?"""
    for tekst in teksten:
        groep = ""
        for regel in tekst.splitlines():
            regel = regel.strip()
            if regel.startswith("[") and regel.endswith("]"):
                groep = regel[1:-1]
            elif groep == "Autologin" and "=" in regel:
                sleutel, waarde = (x.strip() for x in regel.split("=", 1))
                if sleutel == "User" and waarde == naam:
                    return True
    return False


def gebruiker() -> Gebruiker:
    if VOORBEELD:
        return Gebruiker("bugie", _VB["volledige_naam"], True, _VB["auto_inloggen"])
    import grp
    import pwd
    try:
        pw = pwd.getpwuid(os.getuid())
        naam, vol = pw.pw_name, pw.pw_gecos.split(",")[0].strip()
    except KeyError:
        naam, vol = os.environ.get("USER", "?"), ""
    try:
        beheerder = naam in grp.getgrnam("wheel").gr_mem
    except KeyError:
        beheerder = False
    teksten = []
    for pad in SDDM_BESTANDEN:
        p = Path(pad)
        bestanden = sorted(p.glob("*.conf")) if p.is_dir() else [p]
        for b in bestanden:
            try:
                teksten.append(b.read_text(encoding="utf-8"))
            except OSError:
                pass
    return Gebruiker(naam, vol or naam.capitalize(), beheerder, lees_autologin(teksten, naam))


def _accounts(methode: str, *args: str, timeout: int = 60) -> tuple[int, str]:
    return draai("gdbus", "call", "--system", "--interactive", "--dest", "org.freedesktop.Accounts", "--object-path",
                 f"/org/freedesktop/Accounts/User{os.getuid()}", "--method",
                 f"org.freedesktop.Accounts.User.{methode}", *args, timeout=timeout)


def zet_volledige_naam(naam: str) -> bool:
    if VOORBEELD:
        _VB["volledige_naam"] = naam
        return True
    return _accounts("SetRealName", naam)[0] == 0


def versleutel(wachtwoord: str) -> str:
    """Zoals /etc/shadow het bewaart (SHA-512 met zout), via de libcrypt van het systeem."""
    import ctypes
    import secrets
    tekens = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    zout = "$6$" + "".join(secrets.choice(tekens) for _ in range(16))
    lib = ctypes.CDLL("libcrypt.so.1")
    lib.crypt.restype = ctypes.c_char_p
    lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    uit = lib.crypt(wachtwoord.encode("utf-8"), zout.encode("ascii"))
    return uit.decode("ascii") if uit else ""


def zet_wachtwoord(nieuw: str) -> tuple[bool, str]:
    """Nieuw wachtwoord via AccountsService; KDE vraagt eerst je huidige wachtwoord."""
    if VOORBEELD:
        return True, ""
    try:
        hash_ = versleutel(nieuw)
    except OSError:
        hash_ = ""
    if not hash_:
        return False, "crypt"
    code, uit = _accounts("SetPassword", hash_, "")
    return code == 0, uit


def zet_auto_inloggen(aan: bool, naam: str) -> bool:
    """Inloggen zonder wachtwoord: een klein hulpje als beheerder (pkexec vraagt het wachtwoord één keer)."""
    if VOORBEELD:
        _VB["auto_inloggen"] = aan
        return True
    return draai("pkexec", "/usr/bin/bugos-login", "aan" if aan else "uit", naam, timeout=120)[0] == 0


SLOT_KEUZES = (5, 15, 30, 0)   # minuten; 0 = nooit


def slot_na() -> int:
    """Na hoeveel minuten niets doen gaat het scherm op slot (0 = nooit)."""
    if VOORBEELD:
        return _VB["slot_na"]
    if kde_lees("kscreenlockerrc", "Daemon", "Autolock", "true") != "true":
        return 0
    try:
        return int(kde_lees("kscreenlockerrc", "Daemon", "Timeout", "5"))
    except ValueError:
        return 5


def slot_herlees() -> None:
    draai("gdbus", "call", "--session", "--dest", "org.freedesktop.ScreenSaver", "--object-path", "/ScreenSaver",
          "--method", "org.kde.screensaver.configure", timeout=5)


def zet_slot_na(minuten: int) -> None:
    if VOORBEELD:
        _VB["slot_na"] = minuten
        return
    kde_schrijf("kscreenlockerrc", "Daemon", "Autolock", "true" if minuten else "false")
    if minuten:
        kde_schrijf("kscreenlockerrc", "Daemon", "Timeout", str(minuten))
    slot_herlees()


def slot_na_slapen() -> bool:
    if VOORBEELD:
        return _VB["slot_na_slapen"]
    return kde_lees("kscreenlockerrc", "Daemon", "LockOnResume", "true") == "true"


def zet_slot_na_slapen(aan: bool) -> None:
    if VOORBEELD:
        _VB["slot_na_slapen"] = aan
        return
    kde_schrijf("kscreenlockerrc", "Daemon", "LockOnResume", "true" if aan else "false")
    slot_herlees()


def vergrendel() -> None:
    if not VOORBEELD:
        draai("loginctl", "lock-session", timeout=5)


# ======================================================= scherm uit, slapen ===

PROFIELGROEPEN = ("AC", "Battery", "LowBattery")
SCHERM_UIT_KEUZES = (300, 600, 1800, 0)     # seconden; 0 = nooit
SLAAP_KEUZES = (900, 1800, 3600, 0)
KNOP_VRAGEN, KNOP_SLAPEN, KNOP_UIT, KNOP_NIETS, KNOP_SCHERM_UIT = 16, 1, 8, 0, 64


def energie_herlees() -> None:
    draai("gdbus", "call", "--session", "--dest", "org.kde.Solid.PowerManagement", "--object-path",
          "/org/kde/Solid/PowerManagement", "--method", "org.kde.Solid.PowerManagement.refreshStatus", timeout=5)


def _energie_getal(groep: str, sleutel: str, standaard: int) -> int:
    try:
        return int(kde_lees_groepen("powerdevilrc", ["AC", groep], sleutel, str(standaard)))
    except ValueError:
        return standaard


def _zet_energie(groep: str, sleutel: str, waarde: int) -> None:
    for profiel in PROFIELGROEPEN:
        kde_schrijf("powerdevilrc", [profiel, groep], sleutel, str(waarde))


def scherm_uit_na() -> int:
    if VOORBEELD:
        return _VB["scherm_uit"]
    return _energie_getal("Display", "TurnOffDisplayIdleTimeoutSec", 600)


def zet_scherm_uit_na(seconden: int) -> None:
    if VOORBEELD:
        _VB["scherm_uit"] = seconden
        return
    _zet_energie("Display", "TurnOffDisplayIdleTimeoutSec", seconden)
    _zet_energie("Display", "DimDisplayIdleTimeoutSec", max(60, seconden - 60) if seconden else 0)
    energie_herlees()


def slaap_na() -> int:
    if VOORBEELD:
        return _VB["slaap"]
    if _energie_getal("SuspendAndShutdown", "AutoSuspendAction", KNOP_SLAPEN) == KNOP_NIETS:
        return 0
    return _energie_getal("SuspendAndShutdown", "AutoSuspendIdleTimeoutSec", 900)


def zet_slaap_na(seconden: int) -> None:
    if VOORBEELD:
        _VB["slaap"] = seconden
        return
    _zet_energie("SuspendAndShutdown", "AutoSuspendAction", KNOP_SLAPEN if seconden else KNOP_NIETS)
    if seconden:
        _zet_energie("SuspendAndShutdown", "AutoSuspendIdleTimeoutSec", seconden)
    energie_herlees()


def aanuit_knop() -> int:
    if VOORBEELD:
        return _VB["aanuit"]
    return _energie_getal("SuspendAndShutdown", "PowerButtonAction", KNOP_VRAGEN)


def zet_aanuit_knop(waarde: int) -> None:
    if VOORBEELD:
        _VB["aanuit"] = waarde
        return
    _zet_energie("SuspendAndShutdown", "PowerButtonAction", waarde)
    energie_herlees()


def deksel() -> int:
    """Wat gebeurt er als je de laptop dichtklapt."""
    if VOORBEELD:
        return _VB["deksel"]
    return _energie_getal("SuspendAndShutdown", "LidAction", KNOP_SLAPEN)


def zet_deksel(waarde: int) -> None:
    if VOORBEELD:
        _VB["deksel"] = waarde
        return
    _zet_energie("SuspendAndShutdown", "LidAction", waarde)
    energie_herlees()


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
    if VOORBEELD:
        return _VB["niet_storen"]
    return lees_tot(kde_lees("plasmanotifyrc", "DoNotDisturb", "Until", ""))


def zet_niet_storen(aan: bool) -> None:
    """Aan: geen pop-ups tot je het weer uitzet (ze komen wel in de lijst)."""
    if VOORBEELD:
        _VB["niet_storen"] = aan
        return
    kde_schrijf("plasmanotifyrc", "DoNotDisturb", "Until", "2999,12,31,0,0,0" if aan else None)


def stil_bij_games() -> bool:
    if VOORBEELD:
        return _VB["stil_bij_games"]
    return kde_lees("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true") == "true"


def zet_stil_bij_games(aan: bool) -> None:
    if VOORBEELD:
        _VB["stil_bij_games"] = aan
        return
    kde_schrijf("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true" if aan else "false")


def meldingsgeluid() -> bool:
    if VOORBEELD:
        return _VB["geluidje"]
    return kde_lees("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false") != "true"


def zet_meldingsgeluid(aan: bool) -> None:
    if VOORBEELD:
        _VB["geluidje"] = aan
        return
    kde_schrijf("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false" if aan else "true")


def proefmelding(titel: str, tekst: str) -> bool:
    if VOORBEELD:
        return True
    return draai("notify-send", "-a", "BugOS", "-i", "bugos-logo", titel, tekst, timeout=5)[0] == 0


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
    if VOORBEELD:
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
    if VOORBEELD:
        if _VB["apps"] is None:
            _VB["apps"] = {k: v[0] for k, v in _VB_APPS.items()}
        return _VB["apps"][sleutel]
    soort = next(s for s in SOORTEN if s[0] == sleutel)[3][0]
    return draai("xdg-mime", "query", "default", soort, timeout=5)[1].strip()


def zet_standaard_app(sleutel: str, desktop_id: str) -> bool:
    if VOORBEELD:
        standaard_app(sleutel)
        _VB["apps"][sleutel] = desktop_id
        return True
    soorten = next(s for s in SOORTEN if s[0] == sleutel)[3]
    goed = draai("xdg-mime", "default", desktop_id, *soorten, timeout=10)[0] == 0
    if sleutel == "internet":
        draai("xdg-settings", "set", "default-web-browser", desktop_id, timeout=10)
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
    if VOORBEELD:
        if _VB["printers"] is None:
            _VB["printers"] = [Printer("HP_LaserJet", "Bugie's HP LaserJet", "klaar", True),
                               Printer("Canon_PIXMA", "Canon PIXMA (boven)", "gestopt", False)]
        return _VB["printers"]
    if not shutil.which("lpstat"):
        return []
    return lees_lpstat(draai("lpstat", "-l", "-p", timeout=8)[1], draai("lpstat", "-d", timeout=8)[1])


def wachtrij() -> int:
    """Hoeveel documenten staan te wachten om geprint te worden."""
    if VOORBEELD:
        return 1
    return len([r for r in draai("lpstat", "-o", timeout=8)[1].splitlines() if r.strip()])


def zet_standaard_printer(naam: str) -> bool:
    if VOORBEELD:
        for p in printers():
            p.standaard = p.naam == naam
        return True
    return draai("lpoptions", "-d", naam, timeout=8)[0] == 0


def testpagina(naam: str) -> bool:
    if VOORBEELD:
        return True
    proef = "/usr/share/cups/data/testprint"
    if not os.path.exists(proef):
        return False
    return draai("lp", "-d", naam, proef, timeout=15)[0] == 0


def wachtrij_leegmaken() -> bool:
    if VOORBEELD:
        return True
    return draai("cancel", "-a", timeout=8)[0] == 0


def scanprogramma() -> str | None:
    if VOORBEELD:
        return "skanpage"
    return next((p for p in ("skanpage", "skanlite", "simple-scan") if shutil.which(p)), None)
