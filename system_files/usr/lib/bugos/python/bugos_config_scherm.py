"""BugOS Instellingen: geluid (pactl), scherm (kscreen-doctor, logind, KWin), energie
(powerprofilesctl, batterij, powerdevilrc: scherm uit, slapen) en uiterlijk.

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import bugos_config as _c
from bugos_base import t


# ================================================================== geluid ===

@dataclass
class Uitgang:
    naam: str           # technische naam (voor pactl)
    omschrijving: str   # wat je ziet, bv. "Ingebouwde luidsprekers"
    standaard: bool


def _aangesloten(s: dict, standaard: str) -> bool:
    """Hangt er iets aan? Een HDMI-uitgang zonder scherm eraan staat er bij bijna elke laptop; kies je hem, dan is
    alles stil. Zoals KDE: alleen tonen als er iets aan hangt (of als hij nu gekozen is) (U496). Ook voor microfoons
    (een koptelefoonaansluiting zonder headset)."""
    poorten = [p for p in s.get("ports") or [] if isinstance(p, dict)]
    return s.get("name") == standaard or not poorten or any(p.get("availability") != "not available" for p in poorten)


def lees_uitgangen(json_tekst: str, standaard: str) -> list[Uitgang]:
    """Uit: pactl -f json list sinks (en pactl get-default-sink)."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [Uitgang(s.get("name", ""), s.get("description") or s.get("name", ""), s.get("name") == standaard)
            for s in data if isinstance(s, dict) and s.get("name") and _aangesloten(s, standaard)]


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


# --------------------------------------------------------------- microfoon ---

@dataclass
class Ingang:
    naam: str           # technische naam (voor pactl), bv. alsa_input.pci-0000_00_1f.3.analog-stereo
    omschrijving: str   # wat je ziet, bv. "Ingebouwde microfoon"
    standaard: bool


@dataclass
class Headset:
    """Een bluetooth-headset die nu alleen muziek doet (A2DP): zijn microfoon werkt pas in de stand 'bellen' (I6)."""
    kaart: str          # bluez_card.AA_BB_CC_DD_EE_FF
    omschrijving: str
    profiel: str        # het profiel voor bellen, bv. headset-head-unit


@dataclass
class Microfoon:
    bereikbaar: bool    # reageert het geluid (PipeWire)?
    volume: int
    stil: bool
    ingangen: list[Ingang]
    headsets: list[Headset] = field(default_factory=list)


def geldige_bron(naam: str) -> bool:
    """Een naam van pactl (alsa_input.pci-0000_00_03.0.analog-stereo, bluez_input.AA_BB.0, @DEFAULT_SOURCE@)."""
    return isinstance(naam, str) and re.fullmatch(r"[A-Za-z0-9_.:@+-]+", naam) is not None and not naam.startswith("-")


def is_monitor(s: dict) -> bool:
    """De 'monitor' van een luidspreker (wat eruit komt) is geen microfoon."""
    eigen = s.get("properties") if isinstance(s.get("properties"), dict) else {}
    return bool(s.get("monitor_source")) or eigen.get("device.class") == "monitor" or \
        str(s.get("name", "")).endswith(".monitor")


def lees_ingangen(json_tekst: str, standaard: str) -> list[Ingang]:
    """Uit: pactl -f json list sources (en pactl get-default-source): de echte microfoons."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [Ingang(s["name"], s.get("description") or s["name"], s["name"] == standaard)
            for s in data if isinstance(s, dict) and s.get("name") and not is_monitor(s) and _aangesloten(s, standaard)]


def lees_headsets(json_tekst: str) -> list[Headset]:
    """Uit: pactl -f json list cards: bluetooth-headsets die nu op 'muziek' staan maar ook kunnen bellen."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return []
    uit = []
    for k in data if isinstance(data, list) else []:
        if not isinstance(k, dict) or not str(k.get("name", "")).startswith("bluez_card."):
            continue
        if not str(k.get("active_profile", "")).startswith("a2dp"):
            continue
        profielen = k.get("profiles") if isinstance(k.get("profiles"), dict) else {}
        bellen = [(p.get("priority", 0) if isinstance(p, dict) else 0, naam) for naam, p in profielen.items()
                  if str(naam).startswith("headset-head-unit") and isinstance(p, dict) and p.get("available", True)
                  and p.get("sources", 1)]
        if not bellen or not geldige_bron(k["name"]):
            continue
        profiel = max(bellen)[1]
        if not geldige_bron(profiel):
            continue
        eigen = k.get("properties") if isinstance(k.get("properties"), dict) else {}
        uit.append(Headset(k["name"], eigen.get("device.description") or eigen.get("device.alias") or k["name"], profiel))
    return uit


def _vb_ingangen() -> list[Ingang]:
    gekozen = _c._VB["ingang"]
    return [Ingang("builtin-mic", t("Ingebouwde microfoon", "Built-in microphone"), gekozen == "builtin-mic"),
            Ingang("webcam-mic", t("Microfoon van de webcam", "Webcam microphone"), gekozen == "webcam-mic"),
            Ingang("headset-mic", t("Headset van Bugie", "Bugie's headset"), gekozen == "headset-mic")]


_c._VB.setdefault("mic_volume", 80)
_c._VB.setdefault("mic_stil", False)
_c._VB.setdefault("ingang", "builtin-mic")


def microfoon() -> Microfoon:
    if _c.VOORBEELD:
        return Microfoon(True, _c._VB["mic_volume"], _c._VB["mic_stil"], _vb_ingangen())
    standaard = _c.draai("pactl", "get-default-source", timeout=5)[1].strip()
    code, uit = _c.draai("pactl", "-f", "json", "list", "sources", timeout=5)
    ingangen = lees_ingangen(uit, standaard) if code == 0 else []
    if any(i.standaard for i in ingangen):
        volume, stil = lees_volume(uit, standaard)
    else:   # de standaard is een 'monitor' of staat er niet bij: niets gekozen
        volume, stil = 0, False
    headsets = lees_headsets(_c.draai("pactl", "-f", "json", "list", "cards", timeout=5)[1]) if code == 0 else []
    return Microfoon(code == 0, min(volume, 100), stil, ingangen, headsets)


def zet_microfoon_volume(procent: int) -> None:
    if _c.VOORBEELD:
        _c._VB["mic_volume"] = procent
        return
    _c.draai("pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{max(0, min(procent, 100))}%", timeout=5)


def zet_microfoon_stil(stil: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["mic_stil"] = stil
        return
    _c.draai("pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if stil else "0", timeout=5)


def kies_ingang(naam: str) -> bool:
    if not geldige_bron(naam) or naam.startswith("@"):
        return False
    if _c.VOORBEELD:
        _c._VB["ingang"] = naam
        return True
    return _c.draai("pactl", "set-default-source", naam, timeout=5)[0] == 0


def headset_bellen(kaart: str, profiel: str) -> bool:
    """Zet een bluetooth-headset op 'bellen' (dan werkt zijn microfoon). Alleen een profiel dat de kaart zelf noemt."""
    if not geldige_bron(kaart) or not geldige_bron(profiel):
        return False
    if _c.VOORBEELD:
        return True
    bekend = lees_headsets(_c.draai("pactl", "-f", "json", "list", "cards", timeout=5)[1])
    if not any(h.kaart == kaart and h.profiel == profiel for h in bekend):
        return False
    return _c.draai("pactl", "set-card-profile", kaart, profiel, timeout=8)[0] == 0


def microfoon_klaar() -> str:
    """Vlak voor de test: 'ok', 'stil' (de microfoon staat uit) of 'weg' (de gekozen microfoon is er niet meer:
    parec neemt dan stilletjes een andere op, I9)."""
    m = microfoon()
    if not m.bereikbaar or not any(i.standaard for i in m.ingangen):
        return "weg"
    return "stil" if m.stil else "ok"


def microfoon_test_opdracht(naam: str = "@DEFAULT_SOURCE@") -> list[str]:
    """parec: 8000 keer per seconde, mono, 16 bits. Plasma toont dan 'BugOS Settings gebruikt de microfoon'.
    Er wordt niets opgeslagen: alleen de hoogste waarde van elk stukje telt."""
    if not geldige_bron(naam) or shutil.which("parec") is None:
        return []
    return ["parec", "-d", naam, "-n", "BugOS Settings", "--stream-name=Microphone test", "--raw", "--format=s16le",
            "--channels=1", "--rate=8000", "--latency-msec=50"]


def niveau(data: bytes) -> int:
    """Hoe hard (0..100) een stukje geluid is: de hoogste uitslag, in decibel, van -60 dB (0) tot 0 dB (100)."""
    import array
    import math
    import sys
    if len(data) < 2:
        return 0
    getallen = array.array("h")
    getallen.frombytes(bytes(data[:len(data) - len(data) % 2]))
    if sys.byteorder == "big":
        getallen.byteswap()
    piek = max(abs(x) for x in getallen)
    if piek <= 0:
        return 0
    db = 20 * math.log10(min(piek, 32767) / 32767)
    return round(min(max((db + 60) / 60, 0), 1) * 100)


# ---------------------------------------------------- apps die geluid maken ---

def lees_apps(json_tekst: str) -> list[tuple[int, str, int]]:
    """Uit: pactl -f json list sink-inputs -> [(nummer, naam, volume)]. Niet: gepauzeerd of meldingsgeluidjes."""
    try:
        data = json.loads(json_tekst or "[]")
    except ValueError:
        return []
    uit = []
    for s in data if isinstance(data, list) else []:
        if not isinstance(s, dict) or s.get("corked") or not str(s.get("index", "")).isdigit():
            continue
        eigen = s.get("properties") if isinstance(s.get("properties"), dict) else {}
        if eigen.get("media.role") == "event":
            continue
        kanalen = [str(v.get("value_percent", "0%")).rstrip("%") for v in (s.get("volume") or {}).values()
                   if isinstance(v, dict)]
        procent = [int(k) for k in kanalen if k.isdigit()]
        naam = eigen.get("application.name") or eigen.get("application.process.binary") or t("Onbekende app", "Unknown app")
        uit.append((int(s["index"]), str(naam), min(100, round(sum(procent) / len(procent))) if procent else 0))
    return uit


_c._VB.setdefault("apps_geluid", None)


def apps_geluid() -> list[tuple[int, str, int]]:
    if _c.VOORBEELD:
        if _c._VB["apps_geluid"] is None:
            _c._VB["apps_geluid"] = [(1, "Firefox", 80), (2, t("Muziek", "Music"), 45)]
        return list(_c._VB["apps_geluid"])
    code, uit = _c.draai("pactl", "-f", "json", "list", "sink-inputs", timeout=5)
    return lees_apps(uit) if code == 0 else []


def zet_app_volume(nummer: int, procent: int) -> bool:
    if _c.VOORBEELD:
        _c._VB["apps_geluid"] = [(n, a, procent if n == nummer else v) for n, a, v in apps_geluid()]
        return True
    return _c.draai("pactl", "set-sink-input-volume", str(int(nummer)), f"{max(0, min(int(procent), 100))}%",
                    timeout=5)[0] == 0


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


def zet_schaal(waarde: float, naam: str | None = None) -> bool:
    """Alles groter of kleiner: voor één scherm (naam), of voor elk scherm dat aan staat. kscreen-doctor zegt altijd
    'gelukt' (ook als het niet lukte), dus pas_toe kijkt daarna of het echt zo staat (P1)."""
    if waarde not in SCHALEN:
        return False
    if _c.VOORBEELD:
        _c._VB["schaal"] = waarde
    lijst = beeldschermen()
    if not lijst:
        return False
    namen = [s.naam for s in lijst if s.aan and (naam is None or s.naam == naam)]
    if not namen:
        return False
    stappen = [x for n in namen for x in stappen_schaal(n, waarde)]
    return pas_toe(stappen + plekken_na(lijst, stappen))


# ------------------------------------------------------------ beeldschermen ---
# kscreen-doctor -j: alles over de schermen. Let op: kscreen-doctor geeft ALTIJD code 0, ook als het niet lukte, en
# neemt ook onzin aan (scale.0.1). Daarom sturen we alleen waarden uit vaste lijsten en lezen we daarna opnieuw.

SCHALEN = (1.0, 1.25, 1.5, 1.75, 2.0)
# Bij een grootte moet er minstens zoveel (logische) ruimte overblijven, anders past niets meer, ook de knop terug
# niet (U397). Eén getal: wil je 125 % op een laptop van 1280x800, zet MIN_HOOGTE dan op 600.
MIN_BREEDTE, MIN_HOOGTE = 1024, 700
DRAAI_NAAM = {1: "none", 2: "left", 4: "inverted", 8: "right", 16: "flipped", 32: "flipped90", 64: "flipped180",
              128: "flipped270"}
NAAM_DRAAI = {v: k for k, v in DRAAI_NAAM.items()}
GEKANTELD = (2, 8, 32, 128)   # op zijn kant: breedte en hoogte wisselen
RISICO = (".mode.", ".rotation.", ".enable", ".disable", ".mirror.")   # hiermee kan het scherm zwart worden
HERLEES_WACHT = 0.7   # seconden tussen twee keer kijken of een verandering er echt is (tests: 0)


@dataclass
class Stand:
    """Een stand van een scherm: resolutie en verversing (kscreen 'mode')."""
    id: str
    breed: int
    hoog: int
    hz: float


@dataclass
class Beeldscherm:
    id: int
    naam: str                  # de aansluiting, bv. eDP-1 of HDMI-A-1
    soort: str                 # "ingebouwd" | "hdmi" | "anders"
    aan: bool
    hoofd: bool                # het hoofdscherm (taakbalk, nieuwe vensters)
    stand_id: str
    standen: list[Stand]
    voorkeur_id: str
    draai: int                 # 1 gewoon, 2 links, 4 omgekeerd, 8 rechts (16..128 gespiegeld)
    schaal: float
    x: int
    y: int
    breed: int                 # echte beeldpunten, na het draaien
    hoog: int
    kopie_van: int = 0         # id van het scherm dat dit scherm nadoet (0: niets)
    model: str = ""

    @property
    def logisch(self) -> tuple[int, int]:
        s = self.schaal or 1.0
        return round(self.breed / s), round(self.hoog / s)

    def stand(self, stand_id: str | None = None) -> Stand | None:
        sid = self.stand_id if stand_id is None else stand_id
        return next((m for m in self.standen if m.id == sid), None)


def _getal(waarde, standaard: int = 0) -> int:
    try:
        return int(waarde)
    except (TypeError, ValueError):
        return standaard


def lees_beeldschermen(json_tekst: str) -> list[Beeldscherm]:
    """Uit: kscreen-doctor -j -> de aangesloten schermen: eerst die aan staan (van links naar rechts), dan de rest."""
    try:
        data = json.loads(json_tekst or "{}")
    except ValueError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("outputs"), list):
        return []
    lijst: list[Beeldscherm] = []
    for o in data["outputs"]:
        if not isinstance(o, dict) or not o.get("name") or not o.get("connected", True):
            continue
        standen = []
        for m in o.get("modes") or []:
            if not isinstance(m, dict) or not str(m.get("id", "")).isdigit():
                continue
            maat = m.get("size") or {}
            b, h = _getal(maat.get("width")), _getal(maat.get("height"))
            try:
                hz = float(m.get("refreshRate") or 0)
            except (TypeError, ValueError):
                hz = 0.0
            if b > 0 and h > 0:
                standen.append(Stand(str(m["id"]), b, h, hz))
        stand_id = str(o.get("currentModeId") or "")
        voorkeur = [str(p) for p in o.get("preferredModes") or [] if str(p).isdigit()]
        naam = str(o["name"])
        soort = o.get("type")
        if soort == 7 or naam.startswith(("eDP", "LVDS", "DSI")):
            soort_naam = "ingebouwd"
        elif soort == 6 or naam.startswith("HDMI"):
            soort_naam = "hdmi"
        else:
            soort_naam = "anders"
        maat = o.get("size") or {}
        pos = o.get("pos") or {}
        try:
            schaal_ = round(float(o.get("scale") or 1.0), 4)
        except (TypeError, ValueError):
            schaal_ = 1.0
        lijst.append(Beeldscherm(
            id=_getal(o.get("id")), naam=naam, soort=soort_naam, aan=bool(o.get("enabled")),
            hoofd=bool(o.get("enabled")) and o.get("priority") == 1, stand_id=stand_id, standen=standen,
            voorkeur_id=voorkeur[0] if voorkeur else stand_id, draai=_getal(o.get("rotation"), 1) or 1,
            schaal=schaal_ if schaal_ > 0 else 1.0, x=_getal(pos.get("x")), y=_getal(pos.get("y")),
            breed=_getal(maat.get("width")), hoog=_getal(maat.get("height")),
            kopie_van=_getal(o.get("replicationSource"))))
    aan = sorted((s for s in lijst if s.aan), key=lambda s: (s.x, s.y))
    uit = sorted((s for s in lijst if not s.aan), key=lambda s: s.naam)
    if aan and not any(s.hoofd for s in aan):
        aan[0].hoofd = True
    return aan + uit


def _voorbeeld_schermen() -> dict:
    """Voorbeeld in de vorm van kscreen-doctor -j (zodat dezelfde lezer draait). BUGOS_VB_SCHERMEN=2: met een tv."""
    ingebouwd = {"id": 1, "name": "eDP-1", "type": 7, "connected": True, "enabled": True, "priority": 1,
                 "pos": {"x": 0, "y": 0}, "scale": 1.25, "rotation": 1, "currentModeId": "1", "preferredModes": ["1"],
                 "replicationSource": 0, "size": {"width": 1920, "height": 1200},
                 "modes": [{"id": "1", "name": "1920x1200@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1200}},
                           {"id": "2", "name": "1920x1200@48", "refreshRate": 48.0, "size": {"width": 1920, "height": 1200}},
                           {"id": "3", "name": "1680x1050@60", "refreshRate": 59.95, "size": {"width": 1680, "height": 1050}},
                           {"id": "4", "name": "1280x800@60", "refreshRate": 59.81, "size": {"width": 1280, "height": 800}}]}
    tv = {"id": 2, "name": "HDMI-A-1", "type": 6, "connected": True, "enabled": True, "priority": 2,
          "pos": {"x": 1536, "y": 0}, "scale": 1.0, "rotation": 1, "currentModeId": "13", "preferredModes": ["12"],
          "replicationSource": 0, "size": {"width": 1920, "height": 1080},
          "modes": [{"id": "11", "name": "3840x2160@30", "refreshRate": 30.0, "size": {"width": 3840, "height": 2160}},
                    {"id": "12", "name": "3840x2160@60", "refreshRate": 59.94, "size": {"width": 3840, "height": 2160}},
                    {"id": "13", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                    {"id": "14", "name": "1920x1080@50", "refreshRate": 50.0, "size": {"width": 1920, "height": 1080}},
                    {"id": "15", "name": "1280x720@60", "refreshRate": 60.0, "size": {"width": 1280, "height": 720}}]}
    return {"outputs": [ingebouwd, tv] if os.environ.get("BUGOS_VB_SCHERMEN") == "2" else [ingebouwd]}


_c._VB.setdefault("kscreen", _voorbeeld_schermen())


def beeldschermen() -> list[Beeldscherm] | None:
    """De schermen; None als kscreen-doctor er niet is, niet werkt of geen scherm kent (dan toont de pagina alleen
    de grootte, zoals vroeger)."""
    if _c.VOORBEELD:
        return lees_beeldschermen(json.dumps(_c._VB["kscreen"])) or None
    code, uit = _c.draai("kscreen-doctor", "-j", timeout=8)
    if code != 0:
        return None
    return lees_beeldschermen(uit) or None


def grootste_schaal(s: Beeldscherm) -> float:
    """De grootste grootte waarbij dit scherm nog minstens 1024x700 logische beeldpunten heeft (U397), uit de echte
    beeldpunten van kscreen-doctor. (Qt zegt onder Wayland bij 125 % dat het scherm 2x zo groot is: P2.)"""
    b, h = s.breed, s.hoog
    if b <= 0 or h <= 0:
        st = s.stand() or s.stand(s.voorkeur_id)
        if st is None:
            return 1.0
        b, h = (st.hoog, st.breed) if s.draai in GEKANTELD else (st.breed, st.hoog)
    beste = 1.0
    for w in SCHALEN:
        if b / w >= MIN_BREEDTE and h / w >= MIN_HOOGTE:
            beste = w
    return beste


# Een stap voor kscreen-doctor die BugOS zelf maakt uit wat je kiest: alleen deze waarden.
_NAAM = r"(?!-)[A-Za-z0-9_-]+"   # kscreen-doctor splitst op '.', dus een punt kan niet in de naam
_STAP = re.compile(r"output\.(" + _NAAM + r")\.(enable|disable|primary|mode\.\d{1,4}|rotation\.(?:none|left|right|"
                   r"inverted|flipped|flipped90|flipped180|flipped270)|scale\.(?:1|1\.25|1\.5|1\.75|2)|"
                   r"position\.-?\d{1,5},-?\d{1,5}|mirror\.(?:" + _NAAM + r"))")
# Een stap om terug te zetten wat er stond: die waarden komen uit kscreen-doctor -j zelf (een grootte van 110 % uit
# KDE kan dus ook), maar nog steeds niets geks (I2).
_HERSTEL = re.compile(r"output\.(" + _NAAM + r")\.(enable|disable|primary|mode\.\d{1,5}|rotation\.(?:none|left|right|"
                      r"inverted|flipped|flipped90|flipped180|flipped270)|scale\.(\d(?:\.\d{1,4})?)|"
                      r"position\.-?\d{1,5},-?\d{1,5}|mirror\.(?:" + _NAAM + r"))")


def geldige_stap(stap: str) -> bool:
    return isinstance(stap, str) and _STAP.fullmatch(stap) is not None


def geldige_herstel(stap: str) -> bool:
    if not isinstance(stap, str):
        return False
    m = _HERSTEL.fullmatch(stap)
    if m is None:
        return False
    return m.group(3) is None or 0.5 <= float(m.group(3)) <= 4.0


def _ontleed(stap: str) -> tuple[str, str, str]:
    """'output.HDMI-A-1.mode.12' -> ('HDMI-A-1', 'mode', '12'); 'output.X.enable' -> ('X', 'aan', 'ja')."""
    _o, naam, rest = stap.split(".", 2)
    if rest in ("enable", "disable"):
        return naam, "aan", "ja" if rest == "enable" else "nee"
    if rest == "primary":
        return naam, "hoofd", "ja"
    soort, _p, waarde = rest.partition(".")
    return naam, soort, waarde


def _verwacht(stappen: list[str]) -> dict[tuple[str, str], str]:
    """Per scherm en eigenschap: wat de laatste stap ervan zegt."""
    uit: dict[tuple[str, str], str] = {}
    for stap in stappen:
        naam, soort, waarde = _ontleed(stap)
        uit[(naam, soort)] = waarde
    return uit


def klopt_na(stappen: list[str], lijst: list[Beeldscherm]) -> bool:
    """Staat alles nu zoals de stappen zeiden? (kscreen-doctor zegt het zelf niet eerlijk.)"""
    per_naam = {s.naam: s for s in lijst}
    id_van = {s.naam: s.id for s in lijst}
    verwacht = _verwacht(stappen)
    for (naam, soort), waarde in verwacht.items():
        s = per_naam.get(naam)
        if s is None:
            return False
        if soort == "aan":
            if s.aan != (waarde == "ja"):
                return False
            continue
        if not s.aan:
            if verwacht.get((naam, "aan")) == "nee":
                continue   # het staat uit: de rest doet er niet toe
            return False
        if soort == "hoofd" and not s.hoofd:
            return False
        if soort == "mode" and s.stand_id != waarde:
            return False
        if soort == "rotation" and s.draai != NAAM_DRAAI.get(waarde):
            return False
        if soort == "scale" and abs(s.schaal - float(waarde)) >= 0.01:
            return False
        if soort == "position" and (s.x, s.y) != tuple(int(v) for v in waarde.split(",")):
            return False
        if soort == "mirror" and s.kopie_van != (0 if waarde == "none" else id_van.get(waarde, -1)):
            return False
    return True


def _voorbeeld_toepassen(stappen: list[str]) -> None:
    """Voorbeeldstand: doe de stappen op het voorbeeld (_VB['kscreen']), zoals KWin het zou doen."""
    outputs = {o["name"]: o for o in _c._VB["kscreen"]["outputs"]}
    for stap in stappen:
        naam, soort, waarde = _ontleed(stap)
        o = outputs.get(naam)
        if o is None:
            continue
        if soort == "aan":
            o["enabled"] = waarde == "ja"
        elif soort == "hoofd":
            o["priority"] = 1
            for i, ander in enumerate(x for x in outputs.values() if x is not o):
                ander["priority"] = i + 2
        elif soort == "mode":
            m = next((m for m in o["modes"] if m["id"] == waarde), None)
            if m is not None:
                o["currentModeId"] = waarde
                b, h = m["size"]["width"], m["size"]["height"]
                o["size"] = {"width": h, "height": b} if o["rotation"] in GEKANTELD else {"width": b, "height": h}
        elif soort == "rotation":
            oud, nieuw = o["rotation"], NAAM_DRAAI[waarde]
            if (oud in GEKANTELD) != (nieuw in GEKANTELD):
                o["size"] = {"width": o["size"]["height"], "height": o["size"]["width"]}
            o["rotation"] = nieuw
        elif soort == "scale":
            o["scale"] = float(waarde)
        elif soort == "position":
            x, y = (int(v) for v in waarde.split(","))
            o["pos"] = {"x": x, "y": y}
        elif soort == "mirror":
            o["replicationSource"] = 0 if waarde == "none" else outputs.get(waarde, {}).get("id", 0)


def pas_toe(stappen: list[str], herstel: bool = False) -> bool:
    """Geef de stappen aan kscreen-doctor en kijk daarna of het echt zo staat. Eén stap die niet mag: niets doen.
    herstel=True: stappen die terugzetten wat er stond (uit kscreen-doctor -j zelf, zie geldige_herstel)."""
    if not stappen:
        return True
    toets = geldige_herstel if herstel else geldige_stap
    if not all(toets(s) for s in stappen):
        return False
    if _c.VOORBEELD:
        _voorbeeld_toepassen(stappen)
        return True
    code, uit = _c.draai("kscreen-doctor", *stappen, timeout=15)
    if code != 0 or "not found" in uit.lower() or "failed" in uit.lower():
        # 'Output mode 9999x9999@60 not found.', 'applying config failed! ...' (met code 0)
        return False
    for poging in range(2):
        if poging:
            time.sleep(HERLEES_WACHT)   # KWin kan net even later klaar zijn
        code, uit = _c.draai("kscreen-doctor", "-j", timeout=8)
        if code == 0 and klopt_na(stappen, lees_beeldschermen(uit)):
            return True
    return False


# ------------------------------------------------------------- de stappen ---

def resoluties(s: Beeldscherm) -> list[tuple[int, int, bool]]:
    """[(breed, hoog, aanbevolen)], de grootste eerst."""
    voorkeur = s.stand(s.voorkeur_id)
    maten = sorted({(m.breed, m.hoog) for m in s.standen}, key=lambda bh: (bh[0] * bh[1], bh[0]), reverse=True)
    return [(b, h, voorkeur is not None and (b, h) == (voorkeur.breed, voorkeur.hoog)) for b, h in maten]


def huidige_resolutie(s: Beeldscherm) -> tuple[int, int]:
    """De resolutie van nu (zoals het scherm hem kent, niet gedraaid)."""
    st = s.stand()
    if st is not None:
        return st.breed, st.hoog
    return (s.hoog, s.breed) if s.draai in GEKANTELD else (s.breed, s.hoog)


def verversingen(s: Beeldscherm, breed: int, hoog: int) -> list[tuple[str, int]]:
    """[(stand_id, Hz afgerond)] bij deze resolutie, oplopend. 59,94 en 60 zijn allebei '60 Hz' (de hoogste telt).
    Meer dan 4: de 4 hoogste en die van nu (nooit meer dan 5 knoppen)."""
    emmers: dict[int, Stand] = {}
    for m in s.standen:
        if (m.breed, m.hoog) == (breed, hoog) and m.hz > 0:
            k = round(m.hz)
            if k not in emmers or m.hz > emmers[k].hz:
                emmers[k] = m
    hz = sorted(emmers)
    if len(hz) > 4:
        nu = s.stand()
        houden = set(hz[-4:])
        if nu is not None and (nu.breed, nu.hoog) == (breed, hoog) and round(nu.hz) in emmers:
            houden.add(round(nu.hz))
        hz = sorted(houden)
    return [(emmers[k].id, k) for k in hz]


def stand_voor(s: Beeldscherm, breed: int, hoog: int, hz: int | None = None) -> str:
    """De stand voor deze resolutie: met deze Hz; anders de Hz van nu als die er is; anders de hoogste."""
    passend = [m for m in s.standen if (m.breed, m.hoog) == (breed, hoog)]
    if not passend:
        return ""
    if hz is None:
        nu = s.stand()
        if nu is not None and any(round(m.hz) == round(nu.hz) for m in passend):
            hz = round(nu.hz)
    if hz is not None:
        zelfde = [m for m in passend if round(m.hz) == hz]
        if zelfde:
            return max(zelfde, key=lambda m: m.hz).id
    return max(passend, key=lambda m: m.hz).id


def schermstand(lijst: list[Beeldscherm]) -> str:
    """'uitbreiden', 'kopie' (hetzelfde beeld) of 'alleen:<naam>'."""
    aan = [s for s in lijst if s.aan]
    if len(aan) == 1 and len(lijst) > 1:
        return "alleen:" + aan[0].naam
    if any(s.kopie_van for s in aan):
        return "kopie"
    return "uitbreiden"


def schermnummers(lijst: list[Beeldscherm]) -> dict[str, int]:
    """Het nummer dat je ziet ('Scherm 1', 'Alleen 2'): vast per scherm, het ingebouwde eerst, dan op aansluiting.
    Niet op plek: anders werd de tv na 'Alleen 2' of na 'Links' ineens scherm 1, en wisselde 'Alleen 1' van scherm."""
    volgorde = sorted(lijst, key=lambda s: (s.soort != "ingebouwd", s.naam))
    return {s.naam: i + 1 for i, s in enumerate(volgorde)}


def _hoofd(lijst: list[Beeldscherm]) -> Beeldscherm | None:
    return next((s for s in lijst if s.hoofd and s.aan), next((s for s in lijst if s.aan), lijst[0] if lijst else None))


def _aanzet_stand(s: Beeldscherm) -> str:
    """De stand voor een scherm dat aan gaat: die van nu als die bestaat, anders de aanbevolen, anders de grootste.
    (Of KWin bij een scherm dat uit staat nog een stand en maat geeft, weet niemand zeker: I5.)"""
    for sid in (s.stand_id, s.voorkeur_id):
        if s.stand(sid) is not None:
            return sid
    if s.standen:
        return max(s.standen, key=lambda m: (m.breed * m.hoog, m.hz)).id
    return ""


def _logische_maat(s: Beeldscherm, stand_id: str | None = None) -> tuple[int, int] | None:
    """Hoe groot het scherm is in logische punten. Een scherm dat uit staat: uit zijn stand berekend. None: onbekend."""
    if stand_id is None and s.aan and s.breed > 0 and s.hoog > 0:
        return s.logisch
    st = s.stand(stand_id if stand_id is not None else _aanzet_stand(s))
    if st is None:
        return None
    b, h = (st.hoog, st.breed) if s.draai in GEKANTELD else (st.breed, st.hoog)
    sc = s.schaal or 1.0
    return round(b / sc), round(h / sc)


def _overlappen(rechthoeken: list[tuple[int, int, int, int]]) -> bool:
    for i, (x1, y1, b1, h1) in enumerate(rechthoeken):
        for x2, y2, b2, h2 in rechthoeken[i + 1:]:
            if x1 < x2 + b2 and x2 < x1 + b1 and y1 < y2 + h2 and y2 < y1 + h1:
                return True
    return False


def stappen_uitbreiden(lijst: list[Beeldscherm]) -> list[str]:
    """Elk scherm aan, niets nadoen. Lagen ze over elkaar (of stond er een uit of deed er een na), dan naast elkaar:
    het hoofdscherm links, de rest rechts ervan."""
    stappen: list[str] = []
    maten: dict[str, tuple[int, int] | None] = {}
    opnieuw = False
    for s in lijst:
        stappen += [f"output.{s.naam}.enable", f"output.{s.naam}.mirror.none"]
        if not s.aan:
            opnieuw = True
            sid = _aanzet_stand(s)
            if sid:
                stappen.append(f"output.{s.naam}.mode.{sid}")
            maten[s.naam] = _logische_maat(s, sid) if sid else None
        else:
            maten[s.naam] = _logische_maat(s)
            opnieuw = opnieuw or bool(s.kopie_van)
    if not opnieuw:
        rechthoeken = [(s.x, s.y, *maten[s.naam]) for s in lijst if maten[s.naam]]
        opnieuw = _overlappen(rechthoeken)
    if opnieuw:
        hoofd = _hoofd(lijst)
        x = 0
        for s in [hoofd] + [s for s in lijst if s is not hoofd]:
            if maten.get(s.naam) is None:
                continue   # geen stand bekend: aanzetten zonder plek (klopt_na kijkt er dan ook niet naar)
            stappen.append(f"output.{s.naam}.position.{x},0")
            x += maten[s.naam][0]
    return stappen


def stappen_kopie(lijst: list[Beeldscherm]) -> list[str]:
    """Overal hetzelfde beeld: elk scherm doet het hoofdscherm na."""
    hoofd = _hoofd(lijst)
    stappen: list[str] = []
    for s in lijst:
        stappen.append(f"output.{s.naam}.enable")
        if not s.aan and _aanzet_stand(s):
            stappen.append(f"output.{s.naam}.mode.{_aanzet_stand(s)}")
        stappen.append(f"output.{s.naam}.mirror." + ("none" if s is hoofd else hoofd.naam))
    return stappen


def stappen_alleen(lijst: list[Beeldscherm], naam: str) -> list[str]:
    """Alleen dit scherm aan (de rest uit), en het wordt het hoofdscherm."""
    s = next((x for x in lijst if x.naam == naam), None)
    if s is None:
        return []
    stappen = [f"output.{naam}.enable"]
    if not s.aan and _aanzet_stand(s):
        stappen.append(f"output.{naam}.mode.{_aanzet_stand(s)}")
    stappen += [f"output.{naam}.mirror.none", f"output.{naam}.position.0,0"]
    stappen += [f"output.{x.naam}.disable" for x in lijst if x.naam != naam]
    return stappen + [f"output.{naam}.primary"]


def stappen_hoofd(naam: str) -> list[str]:
    return [f"output.{naam}.primary"]


def stappen_stand(naam: str, stand_id: str) -> list[str]:
    return [f"output.{naam}.mode.{stand_id}"] if stand_id else []


def stappen_draai(naam: str, code: int) -> list[str]:
    return [f"output.{naam}.rotation.{DRAAI_NAAM[code]}"] if code in DRAAI_NAAM else []


def stappen_schaal(naam: str, waarde: float) -> list[str]:
    return [f"output.{naam}.scale.{waarde:g}"]


def huidige_kant(lijst: list[Beeldscherm], naam: str) -> str | None:
    """Aan welke kant van het hoofdscherm staat dit scherm? None voor het hoofdscherm zelf."""
    hoofd = _hoofd(lijst)
    s = next((x for x in lijst if x.naam == naam), None)
    if s is None or hoofd is None or s is hoofd or not s.aan:
        return None
    hb, hh = hoofd.logisch
    sb, sh = s.logisch
    dx = (s.x + sb / 2) - (hoofd.x + hb / 2)
    dy = (s.y + sh / 2) - (hoofd.y + hh / 2)
    if abs(dx) >= abs(dy):
        return "rechts" if dx >= 0 else "links"
    return "onder" if dy >= 0 else "boven"


def _indeling(lijst: list[Beeldscherm], kanten: dict[str, str]) -> dict[str, tuple[int, int]]:
    """Plekken voor elk scherm dat aan staat (en niets nadoet): het hoofdscherm blijft, elk ander scherm komt aan zijn
    kant voorbij alles wat er al staat (dus nooit over elkaar, en zonder gat). Daarna begint alles bij 0,0."""
    hoofd = _hoofd(lijst)
    if hoofd is None:
        return {}
    hb, hh = hoofd.logisch
    plek: dict[str, tuple[int, int, int, int]] = {hoofd.naam: (hoofd.x, hoofd.y, hb, hh)}
    for s in lijst:
        if s is hoofd or not s.aan or s.kopie_van:
            continue
        b, h = s.logisch
        links = min(r[0] for r in plek.values())
        rechts = max(r[0] + r[2] for r in plek.values())
        boven = min(r[1] for r in plek.values())
        onder = max(r[1] + r[3] for r in plek.values())
        kant = kanten.get(s.naam) or "rechts"
        x, y = {"rechts": (rechts, hoofd.y), "links": (links - b, hoofd.y), "boven": (hoofd.x, boven - h),
                "onder": (hoofd.x, onder)}[kant]
        plek[s.naam] = (x, y, b, h)
    dx = -min(r[0] for r in plek.values())
    dy = -min(r[1] for r in plek.values())
    return {n: (r[0] + dx, r[1] + dy) for n, r in plek.items()}


def stappen_plek(lijst: list[Beeldscherm], naam: str, kant: str) -> list[str]:
    """Zet dit scherm links, rechts, boven of onder het hoofdscherm, zodat de muis de goede kant op gaat."""
    if kant not in ("links", "rechts", "boven", "onder") or huidige_kant(lijst, naam) is None:
        return []
    kanten = {s.naam: huidige_kant(lijst, s.naam) for s in lijst}
    kanten[naam] = kant
    # Het scherm dat verplaatst wordt als laatste, zodat het voorbij de andere komt.
    volgorde = [s for s in lijst if s.naam != naam] + [s for s in lijst if s.naam == naam]
    plek = _indeling(volgorde, kanten)
    return [f"output.{s.naam}.position.{plek[s.naam][0]},{plek[s.naam][1]}" for s in lijst if s.naam in plek]


def _na(lijst: list[Beeldscherm], stappen: list[str]) -> list[Beeldscherm]:
    """Hoe de schermen eruitzien na deze stappen (voor de plekken)."""
    nieuw = copy.deepcopy(lijst)
    per_naam = {s.naam: s for s in nieuw}
    for stap in stappen:
        naam, soort, waarde = _ontleed(stap)
        s = per_naam.get(naam)
        if s is None:
            continue
        if soort == "mode" and s.stand(waarde) is not None:
            st = s.stand(waarde)
            s.stand_id = waarde
            s.breed, s.hoog = (st.hoog, st.breed) if s.draai in GEKANTELD else (st.breed, st.hoog)
        elif soort == "rotation" and waarde in NAAM_DRAAI:
            nieuw_ = NAAM_DRAAI[waarde]
            if (s.draai in GEKANTELD) != (nieuw_ in GEKANTELD):
                s.breed, s.hoog = s.hoog, s.breed
            s.draai = nieuw_
        elif soort == "scale":
            s.schaal = float(waarde)
    return nieuw


def plekken_na(lijst: list[Beeldscherm], stappen: list[str]) -> list[str]:
    """Wordt een scherm groter of kleiner (resolutie, draaien, grootte) terwijl er meer schermen naast elkaar staan,
    dan schuiven de andere mee: anders ontstaat er een gat (de muis kan niet over) of liggen ze over elkaar (I4).
    Alleen de plekken die veranderen."""
    if not stappen or len([s for s in lijst if s.aan]) < 2 or schermstand(lijst) != "uitbreiden":
        return []
    if not any(_ontleed(s)[1] in ("mode", "rotation", "scale") for s in stappen):
        return []
    kanten = {s.naam: huidige_kant(lijst, s.naam) for s in lijst}
    na = _na(lijst, stappen)
    plek = _indeling(na, kanten)
    return [f"output.{s.naam}.position.{plek[s.naam][0]},{plek[s.naam][1]}" for s in na
            if s.naam in plek and plek[s.naam] != (s.x, s.y)]


def stappen_herstel(lijst: list[Beeldscherm]) -> list[str]:
    """Alles weer zoals het nu staat (voor 'Terugzetten' en het vangnet)."""
    stappen: list[str] = []
    id_naar_naam = {s.id: s.naam for s in lijst}
    for s in lijst:
        if not s.aan:
            continue
        stappen.append(f"output.{s.naam}.enable")
        if s.stand() is not None:
            stappen.append(f"output.{s.naam}.mode.{s.stand_id}")
        if s.draai in DRAAI_NAAM:
            stappen.append(f"output.{s.naam}.rotation.{DRAAI_NAAM[s.draai]}")
        stappen.append(f"output.{s.naam}.scale.{s.schaal:g}")
        stappen.append(f"output.{s.naam}.position.{s.x},{s.y}")
        stappen.append(f"output.{s.naam}.mirror.{id_naar_naam.get(s.kopie_van, 'none') if s.kopie_van else 'none'}")
    stappen += [f"output.{s.naam}.disable" for s in lijst if not s.aan]
    hoofd = _hoofd(lijst)
    if hoofd is not None:
        stappen.append(f"output.{hoofd.naam}.primary")
    return stappen


# ---------------------------------------------------------------- vangnet ---
# Wordt het scherm zwart (de tv op de verkeerde ingang), dan zet BugOS het na 15 s vanzelf terug. En als Instellingen
# in die tijd vastloopt of dichtgaat, doet een timer van systemd het: die loopt los van Instellingen.

EERSTE_VANGNET = 60   # s: ruim meer dan toepassen (15 s) + twee keer kijken (2 x 8 s) + de vraag (15 s)
_teller = 0


def vangnet_aan(herstel: list[str], seconden: int = EERSTE_VANGNET) -> str | None:
    """Zet een timer die over 'seconden' alles terugzet. Geeft de naam van de timer, of None (dan beschermt alleen
    de vraag in Instellingen)."""
    global _teller
    if not herstel or not all(geldige_herstel(s) for s in herstel):
        return None
    if _c.VOORBEELD:
        return "voorbeeld"
    _teller += 1
    eenheid = f"bugos-scherm-terug-{os.getpid()}-{int(time.time())}-{_teller}"
    extra = []
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    if re.fullmatch(r"[A-Za-z0-9._/-]+", wayland):
        extra = [f"--setenv=WAYLAND_DISPLAY={wayland}"]
    code, _u = _c.draai("systemd-run", "--user", "--quiet", f"--unit={eenheid}", f"--on-active={int(seconden)}",
                        *extra, "--", shutil.which("kscreen-doctor") or "kscreen-doctor", *herstel, timeout=10)
    return eenheid if code == 0 else None


def vangnet_uit(eenheid: str | None) -> bool:
    """Zet de timer uit (het nieuwe beeld blijft). True als er geen timer meer loopt."""
    if eenheid is None or eenheid == "voorbeeld":
        return True
    if not re.fullmatch(r"bugos-scherm-terug-[0-9-]+", eenheid):
        return False
    return _c.draai("systemctl", "--user", "stop", f"{eenheid}.timer", timeout=5)[0] == 0


def vangnet_opnieuw(eenheid: str | None, herstel: list[str], seconden: int) -> str | None:
    """De vraag 'Beeld houden?' gaat open: een nieuwe timer die pas ná de vraag afgaat (I3). Eerst de nieuwe, dan de
    oude uit: er is nooit een moment zonder vangnet. Lukt de nieuwe niet, dan blijft de oude."""
    nieuw = vangnet_aan(herstel, seconden)
    if nieuw is None:
        return eenheid
    vangnet_uit(eenheid)
    return nieuw


@dataclass
class Wijziging:
    gelukt: bool
    herstel: list[str] = field(default_factory=list)
    vangnet: str | None = None
    risico: bool = False
    terug: bool = True   # mislukt: staat alles weer zoals het was?


def scherm_wijzigen(stappen: list[str]) -> Wijziging:
    """Verander iets aan de schermen. Met risico (resolutie, draaien, aan/uit, hetzelfde beeld) eerst een vangnet."""
    risico = any(r in s for s in stappen for r in RISICO)
    oud = beeldschermen()
    if oud is None or not stappen:
        return Wijziging(False, [], None, risico)
    stappen = list(stappen) + plekken_na(oud, stappen)
    herstel = stappen_herstel(oud)
    vangnet = vangnet_aan(herstel) if risico else None
    if pas_toe(stappen):
        return Wijziging(True, herstel, vangnet, risico)
    # Half gelukt? Terugzetten. Alleen als dat lukte, de timer uit: anders is die de tweede kans (I2).
    terug = pas_toe(herstel, herstel=True)
    if terug:
        vangnet_uit(vangnet)
        vangnet = None
    return Wijziging(False, herstel, vangnet, risico, terug)


def scherm_terug(herstel: list[str], vangnet: str | None) -> bool:
    """'Terugzetten' (of de 15 s zijn om). Lukt het niet, dan blijft de timer als tweede kans."""
    ok = pas_toe(herstel, herstel=True)
    if ok:
        vangnet_uit(vangnet)
    return ok


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


UPOWER = ("org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device")
_c._VB.setdefault("accu_tijd", (12000, 0))


def lees_busctl_getallen(uit: str) -> list[int]:
    """'x 12000\\nx 0' (busctl get-property met twee eigenschappen) wordt [12000, 0]."""
    getallen = []
    for regel in (uit or "").splitlines():
        delen = regel.split()
        if len(delen) == 2 and delen[0] == "x" and delen[1].lstrip("-").isdigit():
            getallen.append(int(delen[1]))
    return getallen


def batterij_tijd() -> tuple[int, int]:
    """(seconden tot leeg, seconden tot vol) volgens UPower; (0, 0) als het niet bekend is."""
    if _c.VOORBEELD:
        return tuple(_c._VB["accu_tijd"])
    code, uit = _c.draai("busctl", "--system", "get-property", *UPOWER, "TimeToEmpty", "TimeToFull", timeout=5)
    getallen = lees_busctl_getallen(uit) if code == 0 else []
    if len(getallen) != 2:
        return 0, 0
    return max(getallen[0], 0), max(getallen[1], 0)


def duur_tekst(seconden: int) -> str:
    """'3 u 20 min', '45 min', '2 u': op 5 minuten afgerond (eerst alles samen, dus nooit '60 min': review I8)."""
    vijf = max(1, round(seconden / 300))
    uren, minuten = divmod(vijf * 5, 60)
    if not uren:
        return t("{m} min", "{m} min").format(m=minuten)
    if not minuten:
        return t("{u} u", "{u} h").format(u=uren)
    return t("{u} u {m} min", "{u} h {m} min").format(u=uren, m=minuten)


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
