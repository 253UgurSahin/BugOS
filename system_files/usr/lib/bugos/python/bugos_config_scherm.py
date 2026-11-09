"""BugOS Instellingen: geluid (pactl), scherm (kscreen-doctor, logind, KWin), energie
(powerprofilesctl, batterij, powerdevilrc: scherm uit, slapen) en uiterlijk.

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import bugos_config as _c
from bugos_base import t


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
    if _c.VOORBEELD:
        return _c._VB["volume"], _c._VB["stil"], [
            Uitgang("speakers", "Built-in speakers", _c._VB["uitgang"] == "speakers"),
            Uitgang("hdmi", "TV (HDMI)", _c._VB["uitgang"] == "hdmi"),
            Uitgang("headset", "Bugie's headphones", _c._VB["uitgang"] == "headset")]
    standaard = _c.draai("pactl", "get-default-sink", timeout=5)[1].strip()
    uit = _c.draai("pactl", "-f", "json", "list", "sinks", timeout=5)[1]
    volume, stil = lees_volume(uit, standaard)
    return volume, stil, lees_uitgangen(uit, standaard)


def zet_volume(procent: int) -> None:
    if _c.VOORBEELD:
        _c._VB["volume"] = procent
        return
    _c.draai("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{max(0, min(procent, 100))}%", timeout=5)


def zet_stil(stil: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["stil"] = stil
        return
    _c.draai("pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if stil else "0", timeout=5)


def kies_uitgang(naam: str) -> None:
    if _c.VOORBEELD:
        _c._VB["uitgang"] = naam
        return
    _c.draai("pactl", "set-default-sink", naam, timeout=5)


# ================================================================== scherm ===

def backlight() -> Path | None:
    """De schermverlichting van een laptop (een losse monitor heeft dit meestal niet)."""
    basis = Path(os.environ.get("BUGOS_SYS", "/sys")) / "class" / "backlight"
    for pad in sorted(basis.glob("*")):
        if (pad / "max_brightness").exists():
            return pad
    return None


def helderheid() -> int | None:
    if _c.VOORBEELD:
        return _c._VB["helderheid"]
    pad = backlight()
    if pad is None:
        return None
    try:
        return round(int((pad / "brightness").read_text()) / max(int((pad / "max_brightness").read_text()), 1) * 100)
    except (OSError, ValueError):
        return None


def zet_helderheid(procent: int) -> None:
    """Via logind: dat mag zonder wachtwoord voor wie achter de computer zit."""
    if _c.VOORBEELD:
        _c._VB["helderheid"] = procent
        return
    pad = backlight()
    if pad is None:
        return
    try:
        maximum = int((pad / "max_brightness").read_text())
    except (OSError, ValueError):
        return
    waarde = max(1, round(maximum * max(5, min(procent, 100)) / 100))
    _c.draai("gdbus", "call", "--system", "--dest", "org.freedesktop.login1", "--object-path",
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
    if _c.VOORBEELD:
        return _c._VB["schaal"]
    schermen = lees_schalen(_c.draai("kscreen-doctor", "-j", timeout=8)[1])
    return schermen[0][1] if schermen else 1.0


def zet_schaal(waarde: float) -> bool:
    if _c.VOORBEELD:
        _c._VB["schaal"] = waarde
        return True
    schermen = lees_schalen(_c.draai("kscreen-doctor", "-j", timeout=8)[1])
    if not schermen:
        return False
    opdracht = ["kscreen-doctor"] + [f"output.{naam}.scale.{waarde:g}" for naam, _s in schermen]
    return _c.draai(*opdracht, timeout=15)[0] == 0


def nachtlicht() -> bool:
    if _c.VOORBEELD:
        return _c._VB["nachtlicht"]
    return _c.kde_lees("kwinrc", "NightColor", "Active", "false") == "true"


def zet_nachtlicht(aan: bool) -> None:
    """Warmer licht 's avonds (zoals 'Nachtlampje' in Windows); KWin regelt de tijden zelf."""
    if _c.VOORBEELD:
        _c._VB["nachtlicht"] = aan
        return
    # Met --notify (via kde_schrijf), anders ziet KWin het pas na opnieuw inloggen.
    _c.kde_schrijf("kwinrc", "NightColor", "Active", "true" if aan else "false")
    _c.draai("gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin", "--method",
          "org.kde.KWin.reconfigure", timeout=5)


# ================================================================= energie ===

PROFIELEN = ("power-saver", "balanced", "performance")


# Fedora 44 heeft tuned-ppd: dezelfde dienst op D-Bus, maar zonder het programma powerprofilesctl.
STROOM = ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", "ActiveProfile")


def lees_busctl_tekst(uit: str) -> str:
    """'s "balanced"' (wat busctl get-property geeft) wordt 'balanced'."""
    uit = uit.strip()
    return uit[3:-1] if uit.startswith('s "') and uit.endswith('"') else ""


def energieprofiel() -> str | None:
    if _c.VOORBEELD:
        return _c._VB["profiel"]
    if shutil.which("powerprofilesctl"):
        code, uit = _c.draai("powerprofilesctl", "get", timeout=5)
        profiel = uit.strip()
    else:
        code, uit = _c.draai("busctl", "--system", "get-property", *STROOM, timeout=5)
        profiel = lees_busctl_tekst(uit)
    return profiel if code == 0 and profiel in PROFIELEN else None


def zet_energieprofiel(profiel: str) -> bool:
    if _c.VOORBEELD:
        _c._VB["profiel"] = profiel
        return True
    if shutil.which("powerprofilesctl"):
        return _c.draai("powerprofilesctl", "set", profiel, timeout=8)[0] == 0
    return _c.draai("busctl", "--system", "set-property", *STROOM, "s", profiel, timeout=8)[0] == 0


@dataclass
class Batterij:
    procent: int
    laadt: bool
    vol: bool
    aan_lader: bool = False   # aan de lader, maar laadt niet (bijv. een laadgrens van 80%) (U155)


def batterij() -> Batterij | None:
    """De batterij van deze computer. Een laptop met twee batterijen (veel ThinkPads) telt ze samen: anders zei BugOS
    'aan de lader, laadt niet' terwijl hij op de andere batterij liep (U399)."""
    if _c.VOORBEELD:
        return Batterij(76, False, False)
    basis = Path(os.environ.get("BUGOS_SYS", "/sys")) / "class" / "power_supply"
    gevonden = []
    # Een batterij herken je aan type=Battery (niet alleen 'BAT0': sommige laptops noemen hem anders), maar niet
    # die van een muis of toetsenbord (scope=Device) (U155).
    for pad in sorted(basis.glob("*")):
        try:
            soort = (pad / "type").read_text().strip() if (pad / "type").exists() else \
                ("Battery" if pad.name.startswith("BAT") else "")
            if soort != "Battery":
                continue
            if (pad / "scope").exists() and (pad / "scope").read_text().strip() == "Device":
                continue
            procent = int((pad / "capacity").read_text().strip())
            staat = (pad / "status").read_text().strip()
        except (OSError, ValueError):
            continue
        nu = vol = None
        for a, b_ in (("energy_now", "energy_full"), ("charge_now", "charge_full")):
            try:
                nu, vol = int((pad / a).read_text()), int((pad / b_).read_text())
                break
            except (OSError, ValueError):
                continue
        gevonden.append((procent, staat, nu, vol))
    if not gevonden:
        return None
    if len(gevonden) == 1:
        procent, staat, _n, _v = gevonden[0]
        return Batterij(procent, staat == "Charging", staat == "Full", staat == "Not charging" and _aan_stroom_kaal())
    staten = [g[1] for g in gevonden]
    if all(g[2] is not None and g[3] for g in gevonden):
        procent = round(100 * sum(g[2] for g in gevonden) / sum(g[3] for g in gevonden))
    else:
        procent = round(sum(g[0] for g in gevonden) / len(gevonden))
    laadt = "Charging" in staten
    leeg_loopt = "Discharging" in staten
    return Batterij(procent, laadt, all(st == "Full" for st in staten),
                    not laadt and not leeg_loopt and _aan_stroom_kaal())


# =============================================================== uiterlijk ===

def donker() -> bool:
    if _c.VOORBEELD:
        return _c._VB["donker"]
    schema = _c.kde_lees("kdeglobals", "General", "ColorScheme", "BugOSLight")
    if schema in ("BugOSDark", "BugOSLight", ""):
        return schema == "BugOSDark"
    # Een ander kleurenschema (Breeze Dark in de KDE-instellingen): donker als de vensters donker zijn (U325).
    try:
        r, g, b = (int(x) for x in _c.kde_lees("kdeglobals", "Colors:Window", "BackgroundNormal", "").split(",")[:3])
    except ValueError:
        return False
    return r * 299 + g * 587 + b * 114 < 128000


def zet_donker(aan: bool) -> bool:
    if _c.VOORBEELD:
        _c._VB["donker"] = aan
        return True
    # Eén plek voor licht/donker: kleuren, KDE-programma's (Kvantum) en de Plasma-stijl. Zeg of het lukte (U336).
    return _c.draai("bugos-theme", "donker" if aan else "licht", timeout=30)[0] == 0


def bugos_achtergronden() -> list[tuple[str, str]]:
    """[(naam, pad)] van de achtergronden van BugOS zelf."""
    basis = Path(os.environ.get("BUGOS_ACHTERGRONDEN", "/usr/share/wallpapers/bugos/contents"))
    lijst = []
    # Eerst die van het begin: het hele pakket, dat zelf meewisselt met licht en donker (U131).
    if (basis / "images").is_dir() and (basis / "images_dark").is_dir():
        lijst.append((t("Stip (licht en donker)", "Dot (light and dark)"), str(basis.parent)))
    for naam, map_ in ((t("Stip (licht)", "Dot (light)"), "images"), (t("Stip (donker)", "Dot (dark)"), "images_dark")):
        beelden = sorted((basis / map_).glob("*.jpg"))
        if beelden:
            lijst.append((naam, str(beelden[0])))
    return lijst


def eigen_achtergrond_map() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "wallpapers" / "bugos-eigen"


def zet_achtergrond(pad: str) -> bool:
    if _c.VOORBEELD:
        return True
    # Een eigen foto eerst kopiëren: van een USB-stick of uit Downloads verdween hij anders zodra de stick eruit
    # ging of je de foto weggooide (U335). BugOS' eigen achtergronden staan in /usr en blijven.
    if not pad.startswith("/usr/"):
        try:
            eigen = eigen_achtergrond_map()
            eigen.mkdir(parents=True, exist_ok=True)
            if Path(pad).resolve().parent != eigen.resolve():
                # Elke keer een nieuwe naam: anders ziet Plasma bij een andere foto met dezelfde naam (IMG_0001.jpg)
                # geen verandering en blijft de oude staan (U343).
                import time
                bron = Path(pad)
                doel = eigen / f"{bron.stem}-{int(time.time())}{bron.suffix}"
                shutil.copy2(bron, doel)
                pad = str(doel)
        except OSError:
            pass   # kopiëren lukt niet (vol?): dan het origineel gebruiken
    gelukt = _c.draai("plasma-apply-wallpaperimage", pad, timeout=15)[0] == 0
    if gelukt:
        # Pas na het instellen de oude eigen foto's weg (lukte het niet, dan blijft de vorige gewoon staan) (U343).
        try:
            for oud in eigen_achtergrond_map().iterdir():
                if oud.is_file() and oud.resolve() != Path(pad).resolve():   # ook via /home -> /var/home (U356)
                    oud.unlink(missing_ok=True)
        except OSError:
            pass
    return gelukt


# ======================================================= scherm uit, slapen ===

PROFIELGROEPEN = ("AC", "Battery", "LowBattery")
SCHERM_UIT_KEUZES = (300, 600, 1800, 0)     # seconden; 0 = nooit
SLAAP_KEUZES = (600, 900, 1800, 3600, 0)   # 10 min: KDE's eigen tijd op de accu (U243)
KNOP_VRAGEN, KNOP_SLAPEN, KNOP_UIT, KNOP_NIETS, KNOP_SCHERM_UIT = 16, 1, 8, 0, 64


def energie_herlees() -> None:
    _c.draai("gdbus", "call", "--session", "--dest", "org.kde.Solid.PowerManagement", "--object-path",
          "/org/kde/Solid/PowerManagement", "--method", "org.kde.Solid.PowerManagement.refreshStatus", timeout=5)


# KDE's eigen tijden als je niets koos: op de accu korter dan aan het stopcontact.
_KDE_STANDAARD = {("AC", "TurnOffDisplayIdleTimeoutSec"): 600, ("AC", "AutoSuspendIdleTimeoutSec"): 900,
                  ("Battery", "TurnOffDisplayIdleTimeoutSec"): 300, ("Battery", "AutoSuspendIdleTimeoutSec"): 600}


def tijden_profiel() -> str:
    """Welke tijden de pagina nu toont en verandert: 'AC' of 'Battery' (U462)."""
    return _profiel()


def _profiel() -> str:
    """Welke tijden gelden nu: een laptop die op de accu loopt, gebruikt die van 'Battery' (U235)."""
    accu = batterij()
    if accu is None or accu.laadt or accu.vol or accu.aan_lader or _aan_stroom():
        return "AC"
    return "Battery"


def _laders() -> list[bool]:
    """Elke lader die de computer kent (stekker 'Mains', of USB-C 'USB'), met: zit hij erin? (U405)"""
    basis = Path(os.environ.get("BUGOS_SYS", "/sys")) / "class" / "power_supply"
    uit: list[bool] = []
    for pad in basis.glob("*"):
        try:
            if (pad / "type").read_text().strip() not in ("Mains", "USB"):
                continue
            if (pad / "scope").exists() and (pad / "scope").read_text().strip() == "Device":
                continue
            uit.append((pad / "online").read_text().strip() == "1")
        except OSError:
            continue
    return uit


def _aan_stroom_kaal() -> bool:
    """Zit de lader erin? Zonder melding van een lader (sommige laptops): ja, zoals vroeger."""
    laders = _laders()
    return not laders or any(laders)


def _aan_stroom() -> bool:
    """Zit de lader erin? Sommige laptops met een laadgrens zeggen bij de accu 'Unknown' (U243)."""
    return any(_laders())


def _energie_getal(groep: str, sleutel: str, standaard: int) -> int:
    profiel = _profiel()
    standaard = _KDE_STANDAARD.get((profiel, sleutel), standaard)
    try:
        return int(_c.kde_lees_groepen("powerdevilrc", [profiel, groep], sleutel, str(standaard)))
    except ValueError:
        return standaard


def _zet_energie(groep: str, sleutel: str, waarde: int, alle: bool = False) -> None:
    """Alleen voor de stand die nu geldt (aan de lader of op de accu), zoals de pagina hem toont. Eerst schreven we alle
    drie, en dan waren KDE's kortere accutijden voor altijd weg, en sliep een bijna lege laptop niet meer (U454).
    Is de keuze KDE's eigen tijd, dan de sleutel weghalen: dan geldt KDE's standaard weer.
    alle: voor de deksel en de aan/uit-knop, die geen 'tijden van nu' zijn: overal hetzelfde (U461)."""
    for profiel in (PROFIELGROEPEN if alle else (_profiel(),)):
        if _KDE_STANDAARD.get((profiel, sleutel)) == waarde:
            _c.kde_schrijf("powerdevilrc", [profiel, groep], sleutel, None)
        else:
            _c.kde_schrijf("powerdevilrc", [profiel, groep], sleutel, str(waarde))


def scherm_uit_na() -> int:
    if _c.VOORBEELD:
        return _c._VB["scherm_uit"]
    # Staat 'scherm uitzetten' helemaal uit, dan is het 'nooit' (welke tijd er ook staat).
    if _c.kde_lees_groepen("powerdevilrc", [_profiel(), "Display"], "TurnOffDisplayWhenIdle", "true") == "false":
        return 0
    seconden = _energie_getal("Display", "TurnOffDisplayIdleTimeoutSec", 600)
    if seconden <= 0:
        # Zo schreef een oudere BugOS 'nooit' weg, maar KDE zet het scherm dan toch na 30 s uit.
        # Je koos 'nooit': dat zetten we nu goed, zodat het ook echt nooit is.
        zet_scherm_uit_na(0)
        return 0
    return seconden


def zet_scherm_uit_na(seconden: int) -> None:
    if _c.VOORBEELD:
        _c._VB["scherm_uit"] = seconden
        return
    # Een tijd van 0 is voor KDE niet 'nooit': dan zet hij het scherm toch uit (na 30 s) en dimt hij meteen.
    # Daarom voor 'nooit' het uitzetten en dimmen zelf uitzetten, en anders weer aan.
    aan = "true" if seconden else "false"
    profiel = _profiel()   # alleen de stand die nu geldt (U454)
    _c.kde_schrijf("powerdevilrc", [profiel, "Display"], "TurnOffDisplayWhenIdle", aan)
    _c.kde_schrijf("powerdevilrc", [profiel, "Display"], "DimDisplayWhenIdle", aan)
    if seconden:
        _zet_energie("Display", "TurnOffDisplayIdleTimeoutSec", seconden)
        _zet_energie("Display", "DimDisplayIdleTimeoutSec", max(60, seconden - 60))
    energie_herlees()


def slaap_na() -> int:
    if _c.VOORBEELD:
        return _c._VB["slaap"]
    if _energie_getal("SuspendAndShutdown", "AutoSuspendAction", KNOP_SLAPEN) == KNOP_NIETS:
        return 0
    return _energie_getal("SuspendAndShutdown", "AutoSuspendIdleTimeoutSec", 900)


def zet_slaap_na(seconden: int) -> None:
    if _c.VOORBEELD:
        _c._VB["slaap"] = seconden
        return
    _zet_energie("SuspendAndShutdown", "AutoSuspendAction", KNOP_SLAPEN if seconden else KNOP_NIETS)
    if seconden:
        _zet_energie("SuspendAndShutdown", "AutoSuspendIdleTimeoutSec", seconden)
    energie_herlees()


def aanuit_knop() -> int:
    if _c.VOORBEELD:
        return _c._VB["aanuit"]
    return _energie_getal("SuspendAndShutdown", "PowerButtonAction", KNOP_VRAGEN)


def zet_aanuit_knop(waarde: int) -> None:
    if _c.VOORBEELD:
        _c._VB["aanuit"] = waarde
        return
    _zet_energie("SuspendAndShutdown", "PowerButtonAction", waarde, alle=True)
    energie_herlees()


def deksel() -> int:
    """Wat gebeurt er als je de laptop dichtklapt."""
    if _c.VOORBEELD:
        return _c._VB["deksel"]
    return _energie_getal("SuspendAndShutdown", "LidAction", KNOP_SLAPEN)


def zet_deksel(waarde: int) -> None:
    if _c.VOORBEELD:
        _c._VB["deksel"] = waarde
        return
    _zet_energie("SuspendAndShutdown", "LidAction", waarde, alle=True)
    energie_herlees()
