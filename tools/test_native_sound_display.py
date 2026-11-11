#!/usr/bin/env python3
"""Test van Geluid, Scherm, Energie en Uiterlijk in BugOS Instellingen, zonder KDE: de microfoon, de schermen
(resolutie, draaien, een tweede scherm, 'Beeld houden?' met een vangnet), de tijd op de batterij en de achtergrond.

Er verandert niets aan je computer: de opdrachten (pactl, kscreen-doctor, systemd-run, busctl,
plasma-apply-wallpaperimage) worden opgevangen (bi.draai vervangen); de pagina's draaien in de voorbeeldstand.
De voorbeelduitvoer is echte uitvoer uit de test-VM (zie de spec sound-display).

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_sound_display.py
"""

from __future__ import annotations

import copy
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-sound-display-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  XDG_CONFIG_HOME=str(TMP / ".config"), XDG_DATA_HOME=str(TMP / ".local" / "share"),
                  BUGOS_ACHTERGRONDEN=str(ROOT / "system_files" / "usr" / "share" / "wallpapers" / "bugos" / "contents"))
os.environ.pop("BUGOS_VB_SCHERMEN", None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402
import bugos_config_scherm as bcs  # noqa: E402

bcs.HERLEES_WACHT = 0   # niet echt wachten tussen twee keer kijken
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang(functie, *args, antwoord=lambda cmd: (0, "")):
    """Roep functie aan zonder voorbeeldstand, en geef de opdrachten die ze wilde draaien."""
    oud = (bi.VOORBEELD, bi.draai, shutil.which)
    opdrachten: list = []
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append(cmd), antwoord(cmd))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args)
    finally:
        bi.VOORBEELD, bi.draai, shutil.which = oud
    return opdrachten, uit


# ------------------------------------------------------------------ echte uitvoer uit de test-VM ---
# kscreen-doctor -j (KDE 6.8.2, QEMU 'Virtual-1'): 26 standen, id's als tekst en niet op volgorde; de voorkeur is '1'
# (2880x1800@75), nu staat '12' (1920x1200 @ 59,88); refreshRate is soms een geheel getal.
_VM_STANDEN = [("1", 2880, 1800, 75), ("2", 2880, 1800, 59.95899963378906), ("3", 2560, 1600, 59.987998962402344),
               ("4", 2560, 1440, 59.95100021362305), ("5", 2048, 1536, 60), ("6", 1920, 1440, 60),
               ("7", 1856, 1392, 60), ("8", 1792, 1344, 60), ("9", 2048, 1152, 60), ("10", 1920, 1200, 74.93000030517578),
               ("11", 1920, 1080, 74.9729995727539), ("12", 1920, 1200, 59.8849983215332),
               ("13", 1920, 1080, 60), ("14", 1600, 1200, 60), ("15", 1680, 1050, 59.95399856567383),
               ("16", 1400, 1050, 59.97800064086914), ("17", 1600, 900, 59.946998596191406), ("18", 1280, 1024, 60),
               ("19", 1440, 900, 59.887001037597656), ("20", 1280, 960, 60), ("21", 1280, 800, 59.81000137329102),
               ("22", 1280, 768, 59.869998931884766), ("23", 1280, 720, 60), ("24", 1024, 768, 60),
               ("25", 800, 600, 60.31700134277344), ("26", 640, 480, 59.94000244140625)]
_volgorde = [12, 1, 26, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 15, 14, 17, 16, 19, 18, 21, 20, 23, 22, 25, 24]
VM_KSCREEN = {
    "outputs": [{
        "brightness": 1, "clones": [], "connected": True, "currentModeId": "12", "enabled": True,
        "followPreferredMode": False, "iccProfilePath": "", "icon": "", "id": 1,
        "modes": [{"id": i, "name": f"{b}x{h}@{round(hz)}", "refreshRate": hz, "size": {"height": h, "width": b}}
                  for n in _volgorde for i, b, h, hz in [_VM_STANDEN[n - 1]]],
        "name": "Virtual-1", "pos": {"x": 0, "y": 0}, "preferredModes": ["1"], "priority": 1, "replicationSource": 0,
        "rotation": 1, "scale": 1.25, "size": {"height": 1200, "width": 1920}, "sizeMM": {"height": 457, "width": 731},
        "type": 0}],
    "screen": {"currentSize": {"height": 960, "width": 1536}, "id": 0, "maxActiveOutputsCount": 1,
               "maxSize": {"height": 64000, "width": 64000}, "minSize": {"height": 0, "width": 0}},
    "tabletModeAvailable": False, "tabletModeEngaged": False}
os.environ["BUGOS_VB_SCHERMEN"] = "2"
TWEE = bcs._voorbeeld_schermen()
del os.environ["BUGOS_VB_SCHERMEN"]
EEN_VB = copy.deepcopy(bi._VB["kscreen"])


def ks(data) -> str:
    return json.dumps(data)


def ks_fake(staat: dict, log: list | None = None, tekst: str = ""):
    """Een nep-kscreen-doctor: '-j' geeft 'staat'; een verandering doet hij echt op 'staat' (zoals KWin)."""
    def antwoord(cmd):
        if cmd[0] != "kscreen-doctor":
            return 0, ""
        if cmd[1:] == ("-j",):
            return 0, json.dumps(staat)
        if log is not None:
            log.append(cmd[1:])
        oud = bi._VB.get("kscreen")
        bi._VB["kscreen"] = staat
        bcs._voorbeeld_toepassen(list(cmd[1:]))
        bi._VB["kscreen"] = oud
        return 0, tekst
    return antwoord


# ====================================================================================== schermen: basis ===
# 17: de echte VM-uitvoer lezen
_vm = bi.lees_beeldschermen(ks(VM_KSCREEN))
_s = _vm[0] if _vm else None
klopt(len(_vm) == 1 and _s.naam == "Virtual-1" and _s.stand_id == "12" and len(_s.standen) == 26 and _s.schaal == 1.25
      and _s.hoofd and (_s.breed, _s.hoog) == (1920, 1200) and _s.soort == "anders" and _s.logisch == (1536, 960)
      and _s.voorkeur_id == "1", "17: kscreen-doctor -j uit de VM: één scherm, stand 12, 26 standen, 125 %, 1536x960 logisch")
klopt(bi.lees_beeldschermen("geen json") == [] and bi.lees_beeldschermen("{}") == [] and
      bi.lees_beeldschermen(ks({"outputs": [{"name": "X", "connected": False}]})) == [],
      "17: rare uitvoer, geen schermen of alleen losgekoppelde: geen schermen (geen fout)")
_opd, _uit = vang(bi.beeldschermen, antwoord=lambda c: (0, ks(VM_KSCREEN)))
klopt(_opd == [("kscreen-doctor", "-j")] and _uit and _uit[0].naam == "Virtual-1", "17: beeldschermen vraagt kscreen-doctor -j")
_opd, _uit = vang(bi.beeldschermen, antwoord=lambda c: (127, ""))
klopt(_uit is None, "17: zonder kscreen-doctor: None (dan alleen de grootte, zoals vroeger)")

# 20: de grootste grootte uit de echte beeldpunten (P2)
def _met_maat(b, h):
    s = copy.deepcopy(_s)
    s.breed, s.hoog = b, h
    return s


_gs = [bi.grootste_schaal(_met_maat(*m)) for m in ((1920, 1200), (1280, 800), (3840, 2160), (1200, 1920), (1366, 768))]
klopt(_gs == [1.5, 1.0, 2.0, 1.0, 1.0], f"20: grootste grootte: 1920x1200 150 %, 1280x800 100 %, 4K 200 %, gedraaid 100 % ({_gs})")

# 23: alleen stappen uit de lijst; met één stap die niet mag, draait er niets
for _stap in ("output.X.scale.0.1", "output.-X.enable", "output.a b.enable", "output.X.mode.1;rm", "output.X.rotation.sideways",
              "output.X.scale.1.1", "output.X.mirror.-d", "output.X.position.1,2;x", "output.X.Y.enable", "--help"):
    klopt(not bi.geldige_stap(_stap), f"23: geen geldige stap: {_stap!r}")
for _stap in ("output.HDMI-A-1.mode.12", "output.eDP-1.rotation.left", "output.eDP-1.scale.1.25", "output.eDP-1.scale.2",
              "output.DP-2.position.-1920,0", "output.HDMI-A-1.mirror.eDP-1", "output.HDMI-A-1.mirror.none",
              "output.eDP-1.primary", "output.eDP-1.disable"):
    klopt(bi.geldige_stap(_stap), f"23: geldige stap: {_stap!r}")
_opd, _ok = vang(bi.pas_toe, ["output.Virtual-1.mode.12", "output.Virtual-1.scale.0.1"])
klopt(_ok is False and _opd == [], "23: pas_toe met één stap die niet mag: niets gedraaid")
# I2: terugzetten mag de grootte van nu (ook 110 % uit KDE), maar nog steeds niets geks
klopt(bi.geldige_herstel("output.eDP-1.scale.1.1") and bi.geldige_herstel("output.eDP-1.scale.2.25")
      and not bi.geldige_herstel("output.eDP-1.scale.0.1") and not bi.geldige_herstel("output.eDP-1.scale.9")
      and not bi.geldige_herstel("output.-x.enable") and not bi.geldige_herstel("output.x.mode.1;y"),
      "I2: herstel-stappen: 110 % en 225 % mogen, 10 %, 900 % en rare namen niet")

# 24: kscreen-doctor zegt altijd 'gelukt'; pas_toe kijkt zelf
_staat = copy.deepcopy(VM_KSCREEN)
_opd, _ok = vang(bi.pas_toe, ["output.Virtual-1.mode.21"],
                 antwoord=lambda c: (0, "Output mode 1x1@60 not found.\n") if c[1:] != ("-j",) else (0, ks(_staat)))
klopt(_ok is False, "24: 'Output mode … not found.' met code 0: niet gelukt")
_opd, _ok = vang(bi.pas_toe, ["output.Virtual-1.mode.21"],
                 antwoord=lambda c: (0, "") if c[1:] != ("-j",) else (0, ks(_staat)))
klopt(_ok is False and _opd.count(("kscreen-doctor", "-j")) == 2,
      f"24: na de stap staat het er niet (twee keer gekeken): niet gelukt ({len(_opd)} opdrachten)")
_staat = copy.deepcopy(VM_KSCREEN)
_opd, _ok = vang(bi.pas_toe, ["output.Virtual-1.mode.21"], antwoord=ks_fake(_staat))
klopt(_ok is True and ("kscreen-doctor", "output.Virtual-1.mode.21") in _opd, "24: de stap staat er echt: gelukt")
_staat = copy.deepcopy(VM_KSCREEN)
_opd, _ok = vang(bi.zet_schaal, 1.5, antwoord=lambda c: (0, "") if c[1:] != ("-j",) else (0, ks(_staat)))
klopt(_ok is False, "24/P1: zet_schaal(1.5) en kscreen-doctor deed niets (wel code 0): niet gelukt")
_opd, _ok = vang(bi.zet_schaal, 1.5, antwoord=ks_fake(_staat))
klopt(_ok is True and ("kscreen-doctor", "output.Virtual-1.scale.1.5") in _opd, "24: zet_schaal(1.5) lukt echt")
_opd, _ok = vang(bi.zet_schaal, 1.3, antwoord=ks_fake(_staat))
klopt(_ok is False and _opd == [], "24/P4: zet_schaal met een grootte die niet in de lijst staat: niets gedraaid")
_opd, _ok = vang(bi.pas_toe, ["output.Virtual-1.scale.1.1"], antwoord=ks_fake(copy.deepcopy(VM_KSCREEN)))
klopt(_ok is False and _opd == [], "I2: 110 % mag niet als keuze (alleen als herstel)")


# ========================================================================================= microfoon ===
# pactl -f json list sources uit de VM (PipeWire 1.6.11): de 'monitor' van de luidspreker en de echte ingang.
VM_BRONNEN = [
    {"index": 51, "name": "alsa_output.pci-0000_00_03.0.analog-stereo.monitor",
     "description": "Monitor of Built-in Audio Analog Stereo", "mute": False,
     "volume": {"front-left": {"value": 65536, "value_percent": "100%", "db": "0.00 dB"},
                "front-right": {"value": 65536, "value_percent": "100%", "db": "0.00 dB"}},
     "monitor_source": "alsa_output.pci-0000_00_03.0.analog-stereo", "active_port": "analog-output-lineout",
     "ports": [{"name": "analog-output-lineout", "description": "Line Out", "type": "Line", "priority": 9000,
                "availability_group": "Legacy 2", "availability": "availability unknown"}],
     "state": "SUSPENDED", "properties": {"device.class": "monitor", "media.class": "Audio/Sink",
                                          "device.form_factor": "internal"}},
    {"index": 52, "name": "alsa_input.pci-0000_00_03.0.analog-stereo", "description": "Built-in Audio Analog Stereo",
     "mute": False, "volume": {"front-left": {"value": 65536, "value_percent": "100%", "db": "0.00 dB"},
                               "front-right": {"value": 45875, "value_percent": "70%", "db": "-9.29 dB"}},
     "monitor_source": "", "active_port": "analog-input-linein",
     "ports": [{"name": "analog-input-linein", "description": "Line In", "type": "Line", "priority": 8100,
                "availability_group": "Legacy 1", "availability": "availability unknown"}],
     "state": "SUSPENDED", "properties": {"device.class": "sound", "media.class": "Audio/Source",
                                          "device.form_factor": "internal"}}]
VM_STANDAARD = "alsa_input.pci-0000_00_03.0.analog-stereo"
_i = bi.lees_ingangen(json.dumps(VM_BRONNEN), VM_STANDAARD)
klopt(len(_i) == 1 and _i[0].naam == VM_STANDAARD and _i[0].standaard and _i[0].omschrijving == "Built-in Audio Analog Stereo",
      f"1: de echte VM-bronnen: één microfoon (de 'monitor' van de luidspreker telt niet), in gebruik ({_i})")
for _wat, _bron in (("monitor_source", {"name": "a", "monitor_source": "x"}),
                    ("device.class monitor", {"name": "b", "properties": {"device.class": "monitor"}}),
                    ("naam .monitor", {"name": "c.monitor"})):
    klopt(bi.lees_ingangen(json.dumps([_bron, {"name": "echt"}]), "") == [bi.Ingang("echt", "echt", False)],
          f"2: een monitor valt weg ({_wat})")
_weg = {"name": "jack", "description": "Headset-aansluiting", "ports": [{"availability": "not available"}]}
klopt([i.naam for i in bi.lees_ingangen(json.dumps([_weg, {"name": "ingebouwd"}]), "ingebouwd")] == ["ingebouwd"]
      and [i.naam for i in bi.lees_ingangen(json.dumps([_weg]), "jack")] == ["jack"],
      "3: een aansluiting zonder headset erin valt weg, behalve als hij gekozen is (zoals U496)")
klopt(bi.lees_ingangen("kapot", "") == [] and bi.lees_ingangen("", "") == [] and bi.lees_ingangen("{}", "") == [],
      "4: rare uitvoer: geen microfoons (geen fout)")


def _pactl(lijst_code=0, kaarten="[]", standaard=VM_STANDAARD):
    def antwoord(cmd):
        if cmd[:2] == ("pactl", "get-default-source"):
            return 0, standaard + "\n"
        if cmd[:5] == ("pactl", "-f", "json", "list", "sources"):
            return lijst_code, json.dumps(VM_BRONNEN) if lijst_code == 0 else ""
        if cmd[:5] == ("pactl", "-f", "json", "list", "cards"):
            return 0, kaarten
        return 0, ""
    return antwoord


_opd, _m = vang(bi.microfoon, antwoord=_pactl())
klopt(("pactl", "get-default-source") in _opd and ("pactl", "-f", "json", "list", "sources") in _opd
      and _m.bereikbaar and _m.volume == 85 and not _m.stil and len(_m.ingangen) == 1,
      f"5: microfoon: pactl get-default-source en list sources; volume is het gemiddelde ({_m.volume})")
_opd, _m = vang(bi.microfoon, antwoord=_pactl(lijst_code=1))
klopt(_m.bereikbaar is False and _m.ingangen == [], "5: pactl list sources mislukt: het geluid reageert niet")
_opd, _m = vang(bi.microfoon, antwoord=_pactl(standaard="alsa_output.pci-0000_00_03.0.analog-stereo.monitor"))
klopt(_m.bereikbaar and not any(i.standaard for i in _m.ingangen) and _m.volume == 0,
      "5: de standaard is een 'monitor': geen microfoon gekozen")
_opd, _ = vang(bi.zet_microfoon_volume, 150)
_opd2, _ = vang(bi.zet_microfoon_volume, -5)
klopt(_opd == [("pactl", "set-source-volume", "@DEFAULT_SOURCE@", "100%")] and _opd2[0][-1] == "0%",
      "6: microfoonvolume 150 wordt 100 %, -5 wordt 0 %")
_opd, _ = vang(bi.zet_microfoon_stil, True)
klopt(_opd == [("pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1")], "7: microfoon uit: pactl set-source-mute … 1")
for _naam in ("-d", "a b", "x;y", "@DEFAULT_SOURCE@", ""):
    _opd, _ok = vang(bi.kies_ingang, _naam)
    klopt(_ok is False and _opd == [], f"8: kies_ingang({_naam!r}) draait niets")
_opd, _ok = vang(bi.kies_ingang, "bluez_input.AA_BB_CC_DD_EE_FF.0")
klopt(_ok and _opd == [("pactl", "set-default-source", "bluez_input.AA_BB_CC_DD_EE_FF.0")], "8: een echte naam: pactl set-default-source")
_opd, _ok = vang(bi.kies_ingang, VM_STANDAARD, antwoord=lambda c: (1, ""))
klopt(_ok is False, "8: pactl zegt 'No such entity' (code 1): niet gelukt")

# I6: een bluetooth-headset op 'muziek' (A2DP): niet 'geen microfoon', maar 'Gebruik voor bellen'
KAARTEN = json.dumps([
    {"index": 40, "name": "alsa_card.pci-0000_00_03.0", "active_profile": "output:analog-stereo+input:analog-stereo",
     "profiles": {"off": {"available": True}}, "properties": {"device.description": "Built-in Audio"}},
    {"index": 77, "name": "bluez_card.AA_BB_CC_DD_EE_FF", "active_profile": "a2dp-sink",
     "properties": {"device.description": "Bugie's koptelefoon"},
     "profiles": {"off": {"sinks": 0, "sources": 0, "priority": 0, "available": True},
                  "a2dp-sink": {"sinks": 1, "sources": 0, "priority": 18, "available": True},
                  "headset-head-unit-cvsd": {"sinks": 1, "sources": 1, "priority": 1, "available": True},
                  "headset-head-unit": {"sinks": 1, "sources": 1, "priority": 30, "available": True}}},
    {"index": 78, "name": "bluez_card.11_22_33_44_55_66", "active_profile": "headset-head-unit",
     "profiles": {"headset-head-unit": {"sources": 1, "available": True}}}])
_h = bi.lees_headsets(KAARTEN)
klopt(_h == [bi.Headset("bluez_card.AA_BB_CC_DD_EE_FF", "Bugie's koptelefoon", "headset-head-unit")],
      f"I6: een headset op muziek wordt gevonden, met het beste profiel om te bellen ({_h})")
_opd, _ok = vang(bi.headset_bellen, "bluez_card.AA_BB_CC_DD_EE_FF", "headset-head-unit", antwoord=_pactl(kaarten=KAARTEN))
klopt(_ok and _opd[-1] == ("pactl", "set-card-profile", "bluez_card.AA_BB_CC_DD_EE_FF", "headset-head-unit"),
      "I6: 'Gebruik voor bellen': pactl set-card-profile met het profiel uit de lijst")
_opd, _ok = vang(bi.headset_bellen, "bluez_card.AA_BB_CC_DD_EE_FF", "off", antwoord=_pactl(kaarten=KAARTEN))
klopt(not _ok and not any(c[1] == "set-card-profile" for c in _opd), "I6: een profiel dat de kaart niet noemt: niets")
_opd, _ok = vang(bi.headset_bellen, "-x", "headset-head-unit", antwoord=_pactl(kaarten=KAARTEN))
klopt(not _ok and _opd == [], "I6: een rare kaartnaam: niets")
klopt(bi.lees_headsets("kapot") == [] and bi.lees_headsets("{}") == [], "I6: rare uitvoer van cards: geen headsets")
klopt("kde_instelling(" not in (PY / "bugos_settings_scherm.py").read_text(encoding="utf-8"),
      "11: Geluid, Scherm, Energie en Uiterlijk openen geen KDE-scherm meer")


# ======================================================================================== het venster ===
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
import bugos_settings_scherm as ss  # noqa: E402

venster = mod.Instellingen("start")
venster.resize(1120, 760)
venster.show()


def wacht(keer: int = 5) -> None:
    for _ in range(keer):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def rijen_in(g) -> list:
    """De regels die nu in een kaart staan (leeg_groep haalt ze eruit; weg zijn ze pas later, deleteLater)."""
    return [g.lay.itemAt(i).widget() for i in range(g.lay.count()) if isinstance(g.lay.itemAt(i).widget(), mod.Rij)]


def wacht_ms(ms: int) -> None:
    eind = time.monotonic() + ms / 1000
    while time.monotonic() < eind:
        QThreadPool.globalInstance().waitForDone(20)
        app.processEvents()
        time.sleep(0.01)


# 30: de oude vorm (3 waarden) werkt nog, en dan geldt de grens van Qt (offscreen 800x600: geen 150/200 %)
venster.ga_naar("scherm")
wacht()
sp = venster.paginas["scherm"]
klopt(sp._schermen is not None and sp.grens() == 1.5, f"P2: met de schermen van kscreen: grens uit de echte beeldpunten ({sp.grens()})")
sp.toon((None, False, 1.0))
_aan = {w: k.isEnabled() for w, k in sp.grootte.knoppen.items()}
klopt(sp._schermen is None and _aan[1.0] and not _aan[1.5] and not _aan[2.0],
      f"30/U397: oude vorm: de schermen zijn vergeten en de grens is die van Qt ({_aan})")
klopt(callable(ss.groot_genoeg) and ss.groot_genoeg() == 1.0, "30: groot_genoeg() bestaat nog en werkt zonder argumenten")
sp.ververs()
wacht()


# 12, 15, I6: de pagina Geluid (voorbeeld)
venster.ga_naar("geluid")
wacht()
gp = venster.paginas["geluid"]
_rijen = rijen_in(gp.mic_lijst)
_chips = [r for r in _rijen if isinstance(r.rechts, ss.Chip)]
_teksten = " ".join(w.text() for w in gp.findChildren(ss.QLabel)).lower()
klopt(len(_rijen) == 3 and len(_chips) == 1 and gp.mic_kaart.isVisibleTo(gp),
      f"12: Geluid: drie microfoons, één 'In gebruik', en de microfoonkaart ({len(_rijen)}, {len(_chips)})")
klopt("geluidscherm" not in _teksten and "sound screen" not in _teksten, "12: geen regel meer naar het geluidscherm van KDE")
_klik = [r for r in _rijen if r.property("klikbaar") == "true"]
_klik[0].geklikt.emit()
wacht()
klopt(bi._VB["ingang"] == "webcam-mic" and "gekozen" in gp.melding.tekst.text().lower(),
      f"12: een andere microfoon kiezen ({bi._VB['ingang']}, {gp.melding.tekst.text()!r})")
gp.toon_microfoon(bi.Microfoon(True, 0, False, []))
_r = rijen_in(gp.mic_lijst)
klopt(len(_r) == 1 and "Geen microfoon gevonden" in _r[0].titel.text() and not gp.mic_kaart.isVisibleTo(gp)
      and not gp.mic_lijst_kop.isVisibleTo(gp), "15: geen microfoon: 'Geen microfoon gevonden', geen microfoonkaart")
gp.toon_microfoon(bi.Microfoon(False, 0, False, []))
_r = rijen_in(gp.mic_lijst)
klopt(len(_r) == 1 and "reageert nu niet" in _r[0].titel.text() and not gp.mic_kaart.isVisibleTo(gp),
      "15: het geluid reageert niet: dat zeggen we, geen microfoonkaart")
gp.toon_microfoon(None)
klopt("reageert nu niet" in rijen_in(gp.mic_lijst)[0].titel.text(), "15: lezen mislukt (None): ook 'reageert nu niet'")
gp.toon_microfoon(bi.Microfoon(True, 0, False, [], bi.lees_headsets(KAARTEN)))
_r = rijen_in(gp.mic_lijst)
klopt(len(_r) == 1 and "Geen microfoon" not in _r[0].titel.text() and isinstance(_r[0].rechts, ss.Knop),
      "I6: alleen een headset op muziek: een knop 'Gebruik voor bellen', niet 'Sluit een headset aan'")
gp.ververs()
wacht()
print(f"\n{fouten} fout(en).")
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fouten else 0)
