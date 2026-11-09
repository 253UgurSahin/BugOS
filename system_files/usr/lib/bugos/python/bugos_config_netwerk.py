"""BugOS Instellingen: wifi (nmcli) en bluetooth (bluetoothctl).

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


# ==================================================================== wifi ===

@dataclass
class Netwerk:
    naam: str
    sterkte: int        # 0-100
    beveiligd: bool
    verbonden: bool
    zakelijk: bool = False   # school/werk (WPA2-Enterprise, 802.1X): ook een gebruikersnaam nodig (U495)


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
        # 'OWE' (Enhanced Open) is een open netwerk: geen wachtwoord vragen (U495).
        beveiliging = [w for w in d[3].split() if w not in ("--", "OWE", "OWE-TM")]
        n = Netwerk(d[1], int(d[2]) if d[2].isdigit() else 0, bool(beveiliging), d[0].strip() == "*",
                    "802.1X" in d[3])
        oud = beste.get(n.naam)
        if oud is None or n.verbonden or (n.sterkte > oud.sterkte and not oud.verbonden):
            beste[n.naam] = n
    return sorted(beste.values(), key=lambda x: (not x.verbonden, -x.sterkte, x.naam.lower()))


def heeft_wifi() -> bool:
    """Heeft deze computer wifi? (nmcli zegt 'enabled' ook als er geen wifi-kaart is) (U111)."""
    if _c.VOORBEELD:
        return True
    code, uit = _c.draai("nmcli", "-t", "-f", "TYPE", "device")
    return code != 0 or any(r.strip() == "wifi" for r in uit.splitlines())


def wifi_aan() -> bool:
    if _c.VOORBEELD:
        return _c._VB["wifi"]
    return _c.draai("nmcli", "-t", "-f", "WIFI", "radio")[1].strip() == "enabled"


def zet_wifi(aan: bool) -> bool:
    if _c.VOORBEELD:
        _c._VB["wifi"] = aan
        return True
    return _c.draai("nmcli", "radio", "wifi", "on" if aan else "off")[0] == 0


def netwerken(opnieuw_zoeken: bool = False) -> list[Netwerk]:
    if _c.VOORBEELD:
        if not _c._VB["wifi"]:
            return []
        lijst = [Netwerk("Home", 86, True, False), Netwerk("Home-5G", 72, True, False),
                 Netwerk("Buren", 41, True, False), Netwerk("Bibliotheek gratis", 35, False, False),
                 Netwerk("Ziggo1234", 22, True, False)]
        for n in lijst:
            n.verbonden = n.naam == _c._VB["verbonden"]
        return sorted(lijst, key=lambda x: (not x.verbonden, -x.sterkte))
    _, uit = _c.draai("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan",
                   "yes" if opnieuw_zoeken else "auto", timeout=25)
    return lees_netwerken(uit)


def verbind(naam: str, wachtwoord: str = "", bekend: bool = False, verborgen: bool = False) -> tuple[bool, str]:
    """Verbind met een wifi-netwerk. Het wachtwoord gaat via de invoer, niet op de opdrachtregel.
    bekend: het netwerk is al opgeslagen, maar het wachtwoord is veranderd. Dan het opgeslagen netwerk
    starten met --ask: werkt het oude wachtwoord niet, dan vraagt nmcli het nieuwe (en dat lezen we uit de invoer)."""
    if _c.VOORBEELD:
        _c._VB["verbonden"] = naam
        return True, ""
    if verborgen:   # een netwerk dat zijn naam niet uitzendt: zelf de naam opgeven (U109)
        if wachtwoord:
            code, uit = _c.draai("nmcli", "--wait", "40", "--ask", "device", "wifi", "connect", naam, "hidden", "yes",
                                 invoer=wachtwoord + "\n", timeout=45)   # --wait: (U503, U518)
        else:
            code, uit = _c.draai("nmcli", "--wait", "40", "device", "wifi", "connect", naam, "hidden", "yes", timeout=45)
        return code == 0, uit
    if wachtwoord and bekend:
        code, uit = _c.draai("nmcli", "--wait", "55", "--ask", "connection", "up", "id", naam, invoer=wachtwoord + "\n",
                             timeout=60)
    elif wachtwoord:
        # --wait: nmcli stopt zelf voordat wij hem afbreken (dan weten we waarom het mislukte) (U503).
        code, uit = _c.draai("nmcli", "--wait", "40", "--ask", "device", "wifi", "connect", naam, invoer=wachtwoord + "\n",
                             timeout=45)
    else:
        code, uit = _c.draai("nmcli", "--wait", "40", "device", "wifi", "connect", naam, timeout=45)
    return code == 0, uit


def bekend_netwerk(naam: str) -> bool:
    """Zijn we hier al eens mee verbonden geweest (dan weet BugOS het wachtwoord nog)?"""
    if _c.VOORBEELD:
        return naam in ("Home", "Home-5G")
    _, uit = _c.draai("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show")
    return any(splits_nmcli(r)[:2] == [naam, "802-11-wireless"] for r in uit.splitlines())


def wifi_uuids(naam: str) -> set[str] | None:
    """De UUID's van alle opgeslagen profielen voor dit netwerk (SSID), welke naam het profiel ook heeft."""
    if _c.VOORBEELD:
        return set()
    code, uit = _c.draai("nmcli", "-t", "-f", "UUID,TYPE", "connection", "show")
    if code != 0:
        return None   # niet te zien: dan ook niets als 'nieuw' weggooien (U518)
    uuids = set()
    for regel in uit.splitlines():
        delen = splits_nmcli(regel)
        if len(delen) >= 2 and delen[1] == "802-11-wireless":
            # -g ontsnapt ':' en '\' (zoals -t): terug naar de echte naam, en spaties aan de rand horen erbij (U366).
            ruw = _c.draai("nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "uuid", delen[0])[1]
            if (splits_nmcli(ruw.rstrip("\n")) or [""])[0] == naam:
                uuids.add(delen[0])
    return uuids


def vergeet_uuids(uuids) -> None:
    for u in uuids:
        _c.draai("nmcli", "connection", "delete", "uuid", u)


def wachtwoord_fout(uitvoer: str) -> bool:
    """Zei nmcli dat het wachtwoord (de 'secrets') niet klopte? Niet: buiten bereik of te traag (U503)."""
    u = uitvoer.lower()
    return "secrets were required" in u or "802-1x" in u or "psk" in u or "wrong password" in u


def vergeet_netwerk(naam: str) -> bool:
    """Het opgeslagen wifi-netwerk (en zijn wachtwoord) weggooien: dan verbindt BugOS er niet meer vanzelf mee (U338)."""
    if _c.VOORBEELD:
        _c._VB["verbonden"] = ""
        return True
    # Het profiel dat nu echt verbonden is (op naam kan het 'Thuis 1' heten, en 'Thuis' een ouder profiel zijn): op
    # zijn UUID weggooien (U345).
    # Alle opgeslagen profielen voor dit netwerk (SSID), ook een ouder 'Thuis' naast 'Thuis 1': anders verbond
    # NetworkManager er meteen weer mee (U357).
    weg = sorted(wifi_uuids(naam) or ())
    if not weg:
        return _c.draai("nmcli", "connection", "delete", "id", naam)[0] == 0
    return all(_c.draai("nmcli", "connection", "delete", "uuid", u)[0] == 0 for u in weg)


def verbreek(naam: str) -> bool:
    if _c.VOORBEELD:
        _c._VB["verbonden"] = ""
        return True
    # Het profiel dat nu verbonden is, op zijn UUID: het kan 'Thuis 1' heten terwijl het netwerk 'Thuis' heet (U497).
    _, uit = _c.draai("nmcli", "-t", "-f", "UUID,TYPE", "connection", "show", "--active")
    for regel in uit.splitlines():
        delen = splits_nmcli(regel)
        if len(delen) >= 2 and delen[1] == "802-11-wireless":
            ruw = _c.draai("nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "uuid", delen[0])[1]
            if (splits_nmcli(ruw.rstrip("\n")) or [""])[0] == naam:
                return _c.draai("nmcli", "connection", "down", "uuid", delen[0])[0] == 0
    return _c.draai("nmcli", "connection", "down", "id", naam)[0] == 0


def kabel_verbonden() -> bool:
    if _c.VOORBEELD:
        return False
    _, uit = _c.draai("nmcli", "-t", "-f", "TYPE,STATE", "device")
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


def bt_hardware() -> bool:
    """Heeft deze computer bluetooth? Zonder (veel pc's) start bluetoothd niet, en wacht 'bluetoothctl'
    tot zijn tijd op is: dan vragen we het niet eens."""
    sys_ = Path(os.environ.get("BUGOS_SYS", "/sys"))
    try:
        if any((sys_ / "class" / "bluetooth").iterdir()):
            return True
    except OSError:
        pass
    # Uitgezet met de vliegtuigstand of een Fn-toets: dan verdwijnt hci0, maar de bluetooth-schakelaar (rfkill)
    # is er nog. Dan heeft de computer wel bluetooth, en moet je hem weer aan kunnen zetten (U165).
    try:
        # Alleen een schakelaar die echt uit staat (soft of hard = 1): sommige laptops melden er ook een zonder
        # bluetooth-kaart, en die staat niet 'uit' (U188).
        def uit(r: Path) -> bool:
            return any((r / k).exists() and (r / k).read_text().strip() == "1" for k in ("soft", "hard"))
        return any((r / "type").read_text().strip() == "bluetooth" and uit(r) for r in (sys_ / "class" / "rfkill").iterdir())
    except OSError:
        return False


def bt_aan() -> bool:
    if _c.VOORBEELD:
        return _c._VB["bt"]
    if not bt_hardware():
        return False
    return lees_bt_aan(_c.draai("bluetoothctl", "show", timeout=5)[1])


def zet_bt(aan: bool) -> bool:
    if _c.VOORBEELD:
        _c._VB["bt"] = aan
        return True
    if not bt_hardware():
        return False   # geen bluetooth in deze computer: niet 8 seconden op bluetoothctl wachten (U157)
    if aan and shutil.which("rfkill"):
        _c.draai("rfkill", "unblock", "bluetooth")
        # Na de vliegtuigstand komt de bluetooth-kaart pas even later terug: wachten tot hij er is (zoals Help, U290)
        # (U499).
        import time as _tijd
        for _ in range(10):
            if "Controller" in _c.draai("bluetoothctl", "show", timeout=3)[1]:
                break
            _tijd.sleep(0.5)
    return _c.draai("bluetoothctl", "power", "on" if aan else "off", timeout=8)[0] == 0


def bt_apparaten() -> list[Apparaat]:
    if _c.VOORBEELD:
        lijst = [Apparaat("AA:BB:CC:DD:EE:01", "Bugie's headphones", "audio-headset", False, 80),
                 Apparaat("AA:BB:CC:DD:EE:02", "Muis", "input-mouse", False, None),
                 Apparaat("AA:BB:CC:DD:EE:03", "Telefoon", "phone", False, None)]
        for a in lijst:
            a.verbonden = a.adres in _c._VB["bt_verbonden"]
        return lijst
    if not bt_hardware():
        return []
    code, uit = _c.draai("bluetoothctl", "devices", "Paired", timeout=5)
    paren = lees_bt_apparaten(uit)
    if code != 0 or not paren:
        paren = lees_bt_apparaten(_c.draai("bluetoothctl", "paired-devices", timeout=5)[1])
    return [lees_bt_info(a, n, _c.draai("bluetoothctl", "info", a, timeout=5)[1]) for a, n in paren]


def bt_verbind(adres: str, aan: bool) -> bool:
    if _c.VOORBEELD:
        (_c._VB["bt_verbonden"].add if aan else _c._VB["bt_verbonden"].discard)(adres)
        return True
    return _c.draai("bluetoothctl", "connect" if aan else "disconnect", adres, timeout=20)[0] == 0


def bt_vergeet(adres: str) -> bool:
    if _c.VOORBEELD:
        return True
    return _c.draai("bluetoothctl", "remove", adres, timeout=10)[0] == 0
