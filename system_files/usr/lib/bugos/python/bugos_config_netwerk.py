"""BugOS Instellingen: wifi (nmcli) en bluetooth (bluetoothctl).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import bugos_config as _c
from bugos_base import t


# Nieuwe voorbeeldstand van dit onderdeel (de gedeelde _c._VB blijft voor wifi, verbonden, bt en bt_verbonden).
# Tests en foto's zetten hier iets in; het moet een publieke naam zijn (bugos_config doet 'import *').
VB_NET = {
    "kabel": "",                 # "" (geen netwerkpoort), "verbonden", "bezig", "los", "uit"
    "opgeslagen": ["Home", "Home-5G", "eduroam", "Hotel Zonneveld"],
    "zakelijk": {},              # ssid -> ZakelijkProfiel, opgeslagen in de voorbeeldstand
    "bt_gekoppeld": set(),       # adressen die in de voorbeeldstand gekoppeld zijn
}


def draai_nm(*cmd: str, invoer: str | None = None, timeout: int = 15) -> tuple[int, str, str]:
    """Zoals draai, maar met de foutuitvoer erbij: (code, uitvoer, fouten). nmcli zet elke 'Error: ...' op stderr,
    en daar hangt van af wat we tegen je zeggen. Nooit via een shell; het wachtwoord gaat alleen via de invoer."""
    if not shutil.which(cmd[0]):
        return 127, "", ""
    try:
        r = subprocess.run(list(cmd), input=invoer, capture_output=True, text=True, timeout=timeout,
                           env=_c.omgeving(cmd[0]))
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Timeout"
    except (OSError, subprocess.SubprocessError):
        return 1, "", ""


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
                 Netwerk("eduroam", 64, True, False, True),   # school of werk: een eigen venster (gebruikersnaam)
                 Netwerk(t("Buren", "Neighbours"), 41, True, False),
                 Netwerk(t("Bibliotheek gratis", "Library free Wi-Fi"), 35, False, False),
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
        return naam in ("Home", "Home-5G") or naam in VB_NET["zakelijk"]
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


@dataclass
class Opgeslagen:
    """Een opgeslagen wifi-netwerk: alle profielen met dezelfde netwerknaam (SSID) samen, want 'Thuis' en een ouder
    'Thuis 1' zijn voor jou hetzelfde netwerk (U357)."""
    naam: str
    uuids: list[str] = field(default_factory=list)
    actief: bool = False


def opgeslagen_wifi() -> list[Opgeslagen]:
    """Alle wifi-netwerken die BugOS onthoudt, het verbonden netwerk eerst."""
    if _c.VOORBEELD:
        return sorted((Opgeslagen(n, ["voorbeeld-" + n], n == _c._VB["verbonden"]) for n in VB_NET["opgeslagen"]),
                      key=lambda o: (not o.actief, o.naam.lower()))
    code, uit = _c.draai("nmcli", "-t", "-f", "NAME,UUID,TYPE,ACTIVE", "connection", "show")
    if code != 0:
        return []
    per_ssid: dict[str, Opgeslagen] = {}
    for regel in uit.splitlines():
        d = splits_nmcli(regel)
        if len(d) < 4 or d[2] != "802-11-wireless" or not d[1]:
            continue
        ruw = _c.draai("nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "uuid", d[1])[1]
        ssid = (splits_nmcli(ruw.rstrip("\n")) or [""])[0] or d[0]
        o = per_ssid.setdefault(ssid, Opgeslagen(ssid))
        o.uuids.append(d[1])
        o.actief = o.actief or d[3].strip() == "yes"
    return sorted(per_ssid.values(), key=lambda o: (not o.actief, o.naam.lower()))


def vergeet_profiel(uuid: str) -> bool:
    """Gooi één opgeslagen profiel weg (op zijn UUID)."""
    if _c.VOORBEELD:
        naam = uuid.removeprefix("voorbeeld-")
        if naam in VB_NET["opgeslagen"]:
            VB_NET["opgeslagen"].remove(naam)
        VB_NET["zakelijk"].pop(naam, None)
        if _c._VB["verbonden"] == naam:
            _c._VB["verbonden"] = ""
        return True
    if not uuid or uuid.startswith("-"):
        return False
    return _c.draai("nmcli", "connection", "delete", "uuid", uuid)[0] == 0


def vergeet_opgeslagen(o: Opgeslagen) -> bool:
    """Vergeet een opgeslagen netwerk: al zijn profielen (anders verbindt NetworkManager met het oudere) (U357)."""
    return all([_c.vergeet_profiel(u) for u in o.uuids]) if o.uuids else False


def stop_profiel(uuid: str) -> bool:
    if _c.VOORBEELD:
        return True
    if not uuid or uuid.startswith("-"):
        return False
    return _c.draai("nmcli", "connection", "down", "uuid", uuid, timeout=20)[0] == 0


_KABEL_RANG = {"verbonden": 4, "bezig": 3, "uit": 2, "los": 1}


def kabel() -> tuple[str, str]:
    """Hoe staat de netwerkkabel: (stand, apparaat). stand: 'verbonden', 'bezig', 'uit' (de kabel zit erin, maar niet
    verbonden), 'los' (niet aangesloten) of '' (geen netwerkpoort). Bij meer poorten telt de beste."""
    if _c.VOORBEELD:
        return VB_NET["kabel"], "enp3s0" if VB_NET["kabel"] else ""
    code, uit = _c.draai("nmcli", "-t", "-f", "TYPE,STATE,DEVICE", "device")
    beste = ("", "")
    if code != 0:
        return beste
    for regel in uit.splitlines():
        d = splits_nmcli(regel)
        if len(d) < 3 or d[0] != "ethernet":
            continue
        staat = d[1].strip()
        stand = ("verbonden" if staat == "connected" else "bezig" if staat.startswith("connecting") else
                 "los" if staat == "unavailable" else "uit" if staat == "disconnected" else "")
        if stand and _KABEL_RANG[stand] > _KABEL_RANG.get(beste[0], 0):
            beste = (stand, d[2])
    return beste


def kabel_verbind(apparaat: str) -> bool:
    """Verbind via de kabel (de kabel zit erin, maar NetworkManager deed niets)."""
    if _c.VOORBEELD:
        VB_NET["kabel"] = "verbonden"
        return True
    if not apparaat or apparaat.startswith("-"):
        return False
    return _c.draai("nmcli", "--wait", "20", "device", "connect", apparaat, timeout=25)[0] == 0


# ===================================================== wifi van school of werk ===
# WPA2/WPA3-Enterprise (802.1X, eduroam) met je eigen gebruikersnaam en wachtwoord: PEAP of TTLS.
# Het profiel maakt nmcli (zonder geheim op de opdrachtregel); het wachtwoord geeft ons eigen hulpje bugos_wifi_agent
# via stdin aan NetworkManager, één keer, en zonder dat KDE erom vraagt.

AGENT = str(Path(__file__).with_name("bugos_wifi_agent.py"))


@dataclass
class ZakelijkProfiel:
    naam: str                 # SSID (ook de naam van het profiel)
    gebruiker: str = ""       # 802-1x.identity
    methode: str = "peap"     # "peap" -> fase 2 mschapv2 | "ttls" -> fase 2 pap
    anoniem: str = ""         # 802-1x.anonymous-identity ("" = niet gezet: dan is het je gebruikersnaam, zoals Windows)
    controleer: bool = True   # het certificaat van de server controleren
    domein: str = ""          # 802-1x.domain-suffix-match
    ca_bestand: str = ""      # 802-1x.ca-cert (een vol pad); "" = de certificaten van het systeem
    verborgen: bool = False   # 802-11-wireless.hidden
    uuid: str = ""            # het opgeslagen profiel; "" = nieuw
    prive: bool = True        # alleen voor deze gebruiker (connection.permissions user:<naam>)


@dataclass
class EapUitslag:
    soort: str = ""
    reden: str = ""
    server: str = ""


_DOMEIN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")
_HOSTNAAM = re.compile(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
_TUSSEN = {"ac", "co", "com", "edu", "gov", "net", "org", "sch", "nhs", "govt", "school"}


def geldig_domein(domein: str) -> bool:
    """Minstens twee delen (school.nl): alleen 'nl' zou elk certificaat voor elke .nl-naam goedkeuren."""
    return bool(_DOMEIN.fullmatch(domein.strip().lower())) and len(domein.strip()) <= 253


def veilige_server(naam: str) -> str:
    """De servernaam uit een certificaat, alleen als het echt een hostnaam is: die naam kiest wie het netwerk maakt
    (ook een nepnetwerk), dus geen zinnen als 'IT: zet de controle uit'."""
    naam = naam.strip()
    return naam if len(naam) <= 64 and _HOSTNAAM.fullmatch(naam) else ""


def standaard_domein(gebruiker: str) -> str:
    """Het domein van de server, afgeleid uit je gebruikersnaam (student@student.tudelft.nl -> tudelft.nl)."""
    if "@" not in gebruiker:
        return ""
    d = gebruiker.rsplit("@", 1)[1].strip().strip(".").lower()
    if not _DOMEIN.fullmatch(d):
        return ""
    delen = d.split(".")
    if len(delen) >= 3 and delen[-2] in _TUSSEN and len(delen[-1]) == 2:
        return ".".join(delen[-3:])
    return ".".join(delen[-2:])


def ontsnap(regel: str) -> str:
    """nmcli -g zet '\\' voor ':' en '\\'. Haal dat weg (zonder op ':' te splitsen)."""
    uit, i = "", 0
    while i < len(regel):
        if regel[i] == "\\" and i + 1 < len(regel):
            uit += regel[i + 1]
            i += 2
            continue
        uit += regel[i]
        i += 1
    return uit


def login_naam() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        return os.environ.get("USER", "")


_VELDEN = ("802-11-wireless-security.key-mgmt,802-1x.eap,802-1x.phase2-auth,802-1x.identity,802-1x.anonymous-identity,"
           "802-1x.system-ca-certs,802-1x.domain-suffix-match,802-1x.ca-cert,802-11-wireless.hidden,"
           "connection.permissions")


def zakelijk_profiel(naam: str) -> ZakelijkProfiel | None:
    """Het opgeslagen profiel van school of werk voor dit netwerk (het eigen profiel van deze gebruiker eerst)."""
    if _c.VOORBEELD:
        return VB_NET["zakelijk"].get(naam)
    uuids = _c.wifi_uuids(naam)
    if not uuids:
        return None
    gevonden = []
    for u in sorted(uuids):
        # Eerst alleen key-mgmt: voor instellingen die een profiel niet heeft, drukt nmcli -g NIETS af (ook geen lege
        # regel), dan zou de rest verschuiven.
        if _c.draai("nmcli", "-g", "802-11-wireless-security.key-mgmt", "connection", "show", "uuid", u)[1].strip() \
                != "wpa-eap":
            continue
        code, uit = _c.draai("nmcli", "-g", _VELDEN, "connection", "show", "uuid", u)
        regels = uit.split("\n")
        if regels and regels[-1] == "":
            regels = regels[:-1]
        if code != 0 or len(regels) != 10:
            continue
        km, eap, _fase2, ident, anon, sysca, domein, ca, verborgen, rechten = (ontsnap(r) for r in regels)
        ca = ca.removeprefix("file://")
        p = ZakelijkProfiel(naam, ident, "ttls" if eap.strip().startswith("ttls") else "peap", anon,
                            sysca.strip() == "yes" or bool(ca) or bool(domein), domein, ca, verborgen.strip() == "yes",
                            u, ("user:" + login_naam()) in rechten.split(","))
        gevonden.append(p)
    if not gevonden:
        return None
    return next((p for p in gevonden if p.prive), gevonden[0])


def zakelijk_instellingen(p: ZakelijkProfiel) -> list[str]:
    eap, fase2 = ("ttls", "pap") if p.methode == "ttls" else ("peap", "mschapv2")
    return ["802-1x.eap", eap, "802-1x.phase2-auth", fase2, "802-1x.identity", p.gebruiker.strip(),
            "802-1x.anonymous-identity", p.anoniem.strip(), "802-1x.password-flags", "0",
            "802-1x.system-ca-certs", "yes" if p.controleer and not p.ca_bestand else "no",
            "802-1x.domain-suffix-match", p.domein.strip().lower() if p.controleer else "",
            "802-1x.ca-cert", p.ca_bestand if p.controleer else "",
            "802-11-wireless.hidden", "yes" if p.verborgen else "no"]


def opslaan_fout(tekst: str) -> str:
    t_ = tekst.lower()
    if "not authorized" in t_ or "insufficient privileges" in t_ or "permission denied" in t_:
        return "rechten"
    if "failed to recognize certificate" in t_ or "failed to open file" in t_ or "ca-cert" in t_:
        return "ca_bestand"
    return "opslaan"


def bewaar_zakelijk(p: ZakelijkProfiel) -> tuple[str, str]:
    """Maak of verander het profiel (zonder wachtwoord: dat geeft verbind_zakelijk). Geeft (uuid, fout)."""
    if _c.VOORBEELD:
        p.uuid = "voorbeeld-" + p.naam
        VB_NET["zakelijk"][p.naam] = p
        if p.naam not in VB_NET["opgeslagen"]:
            VB_NET["opgeslagen"].append(p.naam)
        return p.uuid, ""
    if not p.gebruiker.strip() or not p.naam or (p.controleer and p.domein.strip() and not geldig_domein(p.domein)):
        return "", "opslaan"
    login = login_naam()
    instellingen = zakelijk_instellingen(p)
    if p.uuid:
        # Ook een ouder profiel voor iedereen wordt nu van jou alleen: anders verbond je broertje met jouw account.
        code, uit, fout = _c.draai_nm("nmcli", "connection", "modify", "uuid", p.uuid, "connection.permissions",
                                      "user:" + login, *instellingen, timeout=20)
        return (p.uuid, "") if code == 0 else ("", opslaan_fout(fout + uit))
    zonder_leeg = []
    for i in range(0, len(instellingen), 2):
        if instellingen[i + 1] != "":
            zonder_leeg += instellingen[i:i + 2]
    # Eerst niet vanzelf verbinden: anders begint NetworkManager er misschien al aan zonder wachtwoord (en vraagt KDE
    # het). Pas na de eerste keer dat het lukt, gaat dat aan (zet_vanzelf).
    code, uit, fout = _c.draai_nm("nmcli", "connection", "add", "type", "wifi", "con-name", p.naam, "ssid", p.naam,
                                  "wifi-sec.key-mgmt", "wpa-eap", "connection.permissions", "user:" + login,
                                  "connection.autoconnect", "no", *zonder_leeg, timeout=20)
    m = re.search(r"\(([0-9a-fA-F-]{36})\) successfully added", uit + fout)
    if code != 0 or not m:
        return "", opslaan_fout(fout + uit)
    p.uuid = m.group(1)
    return p.uuid, ""


def zet_vanzelf(uuid: str) -> bool:
    """Na de eerste keer dat het lukte: voortaan vanzelf verbinden als het netwerk in de buurt is."""
    if _c.VOORBEELD:
        return True
    if not uuid or uuid.startswith("-"):
        return False
    return _c.draai("nmcli", "connection", "modify", "uuid", uuid, "connection.autoconnect", "yes")[0] == 0


def zakelijk_fout(code: int, tekst: str) -> str:
    """Wat ging er mis, uit de tekst van nmcli of NetworkManager (Engels: LC_ALL=C.UTF-8)."""
    t_ = tekst.lower()
    if code in (3, 124) or "timeout expired" in t_:
        return "traag"
    if "no network with ssid" in t_ or "could not be found" in t_ or "ssid not found" in t_:
        return "bereik"
    if code == 1 and "password (802-1x.password)" in t_:
        return "inloggen"
    if "secrets were required" in t_ or "802.1x supplicant" in t_ or "supplicant" in t_ or "no-secrets" in t_:
        return "inloggen"
    if "no suitable device" in t_ or "no wi-fi device" in t_ or "not available because" in t_:
        return "apparaat"
    if "not authorized" in t_ or "insufficient privileges" in t_ or "permission denied" in t_:
        return "rechten"
    if code == 10 or "unknown connection" in t_:
        return "opslaan"
    return "anders"


# NMDeviceStateReason en NMActiveConnectionStateReason (libnm, NetworkManager 1.56).
_APPARAAT_INLOGGEN = {7, 8, 10, 11}        # NO_SECRETS, SUPPLICANT_DISCONNECT, _FAILED, _TIMEOUT
_APPARAAT_WEG = {36, 37, 78}               # REMOVED, SLEEPING, NETWORKING_OFF
_APPARAAT_BEREIK = {53}                    # SSID_NOT_FOUND


def agent_soort(u: dict) -> str:
    """Wat ging er mis, uit de uitslag van bugos_wifi_agent ('' = gelukt)."""
    if not u:
        return "anders"
    if u.get("gelukt"):
        return ""
    fout, melding = str(u.get("fout", "")), str(u.get("melding", ""))
    if fout:
        if fout == "geen_dbus":
            return "anders"
        if "UnknownConnection" in fout or "InvalidConnection" in fout:
            return "opslaan"
        if "PermissionDenied" in fout or "NotAuthorized" in fout or "AccessDenied" in fout:
            return "rechten"
        return zakelijk_fout(1, melding)
    if u.get("opnieuw"):
        return "inloggen"
    if u.get("zonder"):
        return "nodig"
    reden, apparaat = int(u.get("reden", 0)), int(u.get("apparaat_reden", 0))
    if apparaat in _APPARAAT_BEREIK:
        return "bereik"
    if u.get("te_laat") or reden == 6:
        return "traag"
    if apparaat in _APPARAAT_INLOGGEN or reden in (9, 10):
        return "inloggen"
    if apparaat in _APPARAAT_WEG or reden == 14:
        return "apparaat"
    return "anders"


def lees_agent_uitslag(uit: str) -> dict:
    for regel in reversed(uit.strip().splitlines()):
        try:
            u = json.loads(regel)
        except ValueError:
            continue
        if isinstance(u, dict):
            return u
    return {}


def lees_eap_log(tekst: str) -> EapUitslag:
    """De regels van wpa_supplicant (journal) na een mislukte poging: wat was het echt?"""
    server, cert, nak, gekozen, mislukt = "", "", False, False, False
    for regel in tekst.splitlines():
        if "CTRL-EVENT-EAP-PEER-CERT" in regel and "depth=0" in regel:
            m = re.search(r"subject='([^']*)'", regel)
            cn = re.search(r"CN=([^/,']+)", m.group(1)) if m else None
            if cn:
                server = cn.group(1)
        elif "CTRL-EVENT-EAP-TLS-CERT-ERROR" in regel:
            m = re.search(r"reason=(\d+)", regel)
            r = int(m.group(1)) if m else -1
            cert = "domein" if r in (5, 6, 9, 10) else "tijd" if r in (3, 4) else "onbekend"
            if "depth=0" in regel:
                m = re.search(r"subject='([^']*)'", regel)
                cn = re.search(r"CN=([^/,']+)", m.group(1)) if m else None
                if cn:
                    server = cn.group(1)
        elif "CTRL-EVENT-EAP-PROPOSED-METHOD" in regel and "NAK" in regel:
            nak = True
        elif "CTRL-EVENT-EAP-METHOD" in regel and "selected" in regel:
            gekozen = True
        elif "CTRL-EVENT-EAP-FAILURE" in regel:
            mislukt = True
    if cert:
        return EapUitslag("certificaat", cert, veilige_server(server))
    if nak and not gekozen:
        return EapUitslag("methode")
    if mislukt:
        return EapUitslag("wachtwoord")
    return EapUitslag()


def verbind_zakelijk(uuid: str, wachtwoord: str = "") -> tuple[bool, str, str, str]:
    """Verbind met een opgeslagen profiel van school of werk. Geeft (gelukt, soort, reden, server).
    wachtwoord '' = het bekende wachtwoord gebruiken; vraagt NetworkManager toch iets, dan is soort 'nodig'."""
    if _c.VOORBEELD:
        naam = uuid.removeprefix("voorbeeld-")
        p = VB_NET["zakelijk"].get(naam)
        if wachtwoord == "fout":
            return False, "wachtwoord", "", ""
        if p is not None and p.controleer and p.domein == "fout.nl":
            return False, "certificaat", "domein", "radius.voorbeeld.nl"
        _c._VB["verbonden"] = naam
        return True, "", "", ""
    if not uuid or uuid.startswith("-") or "\n" in wachtwoord or "\r" in wachtwoord:
        return False, "anders", "", ""
    t0 = int(time.time()) - 2
    code, uit, fout = _c.draai_nm("python3", "-I", AGENT, uuid, "45", invoer=wachtwoord, timeout=60)
    if code == 124:
        return False, "traag", "", ""
    if code == 127:
        return False, "anders", "", ""
    u = lees_agent_uitslag(uit)
    soort = agent_soort(u)
    if not soort:
        return True, "", "", ""
    if soort == "inloggen":
        # Waarom precies? wpa_supplicant schrijft het in het journal (dat mag een beheerder lezen).
        log = _c.draai("journalctl", "-b", "-q", "--no-pager", "-o", "cat", "-t", "wpa_supplicant", "--since",
                       "@" + str(t0), timeout=5)[1]
        e = lees_eap_log(log)
        if e.soort:
            return False, e.soort, e.reden, e.server
    return False, soort, "", ""


def ca_veilige_naam(ssid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", ssid) or "netwerk"


def kopieer_ca(bron: str, ssid: str) -> tuple[str, str]:
    """Zet het certificaatbestand van de ICT-afdeling op een vaste plek (~/.cert/bugos-wifi/), zodat het niet weg is
    als je je Downloads opruimt. Geeft (pad, fout); fout 'ca_bestand' als het geen certificaat lijkt."""
    try:
        data = Path(bron).read_bytes()
    except OSError:
        return "", "ca_bestand"
    pem = b"-----BEGIN CERTIFICATE-----" in data
    der = not pem and data[:1] == b"\x30" and 100 < len(data) < 64 * 1024
    if not (pem or der) or len(data) > 1024 * 1024:
        return "", "ca_bestand"
    if _c.VOORBEELD:
        return bron, ""
    doel_map = Path.home() / ".cert" / "bugos-wifi"
    try:
        doel_map.mkdir(parents=True, exist_ok=True)
        doel_map.chmod(0o700)
        doel = doel_map / (ca_veilige_naam(ssid) + (".pem" if pem else ".der"))
        doel.write_bytes(data)
        doel.chmod(0o644)
    except OSError:
        return "", "ca_bestand"
    return str(doel), ""


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
                 Apparaat("AA:BB:CC:DD:EE:02", t("Muis", "Mouse"), "input-mouse", False, None),
                 Apparaat("AA:BB:CC:DD:EE:03", t("Telefoon", "Phone"), "phone", False, None)]
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
