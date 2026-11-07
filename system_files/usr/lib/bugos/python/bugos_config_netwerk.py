"""BugOS Instellingen: wifi (nmcli) en bluetooth (bluetoothctl).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

import bugos_config as _c


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
        lijst = [Netwerk("Thuis", 86, True, False), Netwerk("Thuis-5G", 72, True, False),
                 Netwerk("Buren", 41, True, False), Netwerk("Bibliotheek gratis", 35, False, False),
                 Netwerk("Ziggo1234", 22, True, False)]
        for n in lijst:
            n.verbonden = n.naam == _c._VB["verbonden"]
        return sorted(lijst, key=lambda x: (not x.verbonden, -x.sterkte))
    _, uit = _c.draai("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan",
                   "yes" if opnieuw_zoeken else "auto", timeout=25)
    return lees_netwerken(uit)


def verbind(naam: str, wachtwoord: str = "") -> tuple[bool, str]:
    """Verbind met een wifi-netwerk. Het wachtwoord gaat via de invoer, niet op de opdrachtregel."""
    if _c.VOORBEELD:
        _c._VB["verbonden"] = naam
        return True, ""
    if wachtwoord:
        code, uit = _c.draai("nmcli", "--ask", "device", "wifi", "connect", naam, invoer=wachtwoord + "\n", timeout=45)
    else:
        code, uit = _c.draai("nmcli", "device", "wifi", "connect", naam, timeout=45)
    return code == 0, uit


def bekend_netwerk(naam: str) -> bool:
    """Zijn we hier al eens mee verbonden geweest (dan weet BugOS het wachtwoord nog)?"""
    if _c.VOORBEELD:
        return naam in ("Thuis", "Thuis-5G")
    _, uit = _c.draai("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show")
    return any(splits_nmcli(r)[:2] == [naam, "802-11-wireless"] for r in uit.splitlines())


def verbreek(naam: str) -> bool:
    if _c.VOORBEELD:
        _c._VB["verbonden"] = ""
        return True
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


def bt_aan() -> bool:
    if _c.VOORBEELD:
        return _c._VB["bt"]
    return lees_bt_aan(_c.draai("bluetoothctl", "show", timeout=5)[1])


def zet_bt(aan: bool) -> bool:
    if _c.VOORBEELD:
        _c._VB["bt"] = aan
        return True
    if aan and shutil.which("rfkill"):
        _c.draai("rfkill", "unblock", "bluetooth")
    return _c.draai("bluetoothctl", "power", "on" if aan else "off", timeout=8)[0] == 0


def bt_apparaten() -> list[Apparaat]:
    if _c.VOORBEELD:
        lijst = [Apparaat("AA:BB:CC:DD:EE:01", "Bugie's headphones", "audio-headset", False, 80),
                 Apparaat("AA:BB:CC:DD:EE:02", "Muis", "input-mouse", False, None),
                 Apparaat("AA:BB:CC:DD:EE:03", "Telefoon", "phone", False, None)]
        for a in lijst:
            a.verbonden = a.adres in _c._VB["bt_verbonden"]
        return lijst
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
