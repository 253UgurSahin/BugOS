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


# ================================================================================ schermen: één scherm ===
# 19: resoluties en verversingen
_r = bi.resoluties(_s)
klopt(_r[0] == (2880, 1800, True) and len(_r) == len({(b, h) for b, h, _a in _r}) == 23
      and [b * h for b, h, _a in _r] == sorted((b * h for b, h, _a in _r), reverse=True)
      and sum(1 for *_x, a in _r if a) == 1, f"19: resoluties: uniek, de grootste eerst, 'aanbevolen' bij de voorkeur ({_r[:3]})")
klopt(bi.verversingen(_s, 1920, 1200) == [("12", 60), ("10", 75)], f"19: verversingen bij 1920x1200 ({bi.verversingen(_s, 1920, 1200)})")
_tv = [x for x in bi.lees_beeldschermen(ks(TWEE)) if x.naam == "HDMI-A-1"][0]
klopt(bi.verversingen(_tv, 3840, 2160) == [("11", 30), ("12", 60)], "19: 4K-tv: 30 en 60 Hz (59,94 heet 60)")
_veel = copy.deepcopy(_tv)
_veel.standen = [bi.Stand(i, 1920, 1080, hz) for i, hz in (("a", 60.0), ("b", 59.94), ("c", 50.0), ("d", 30.0),
                                                           ("e", 24.0), ("f", 120.0), ("g", 144.0))]
_veel.stand_id = "e"
_v = bi.verversingen(_veel, 1920, 1080)
klopt(_v == [("e", 24), ("c", 50), ("a", 60), ("f", 120), ("g", 144)],
      f"19: 59,94 en 60 zijn één knop (de hoogste telt); meer dan 4: de 4 hoogste en die van nu ({_v})")
klopt(bi.stand_voor(_s, 1920, 1080) == "13" and bi.stand_voor(_s, 1920, 1200, 75) == "10"
      and bi.stand_voor(_s, 2880, 1800) == "2" and bi.stand_voor(_s, 999, 1) == "",
      "19: stand_voor: de Hz van nu als het kan, anders de hoogste; een onbekende resolutie: niets")

# 22: terugzetten precies zoals in de VM getest (één opdracht, 144 ms, niets veranderd)
_h = bi.stappen_herstel(_vm)
klopt(_h == ["output.Virtual-1.enable", "output.Virtual-1.mode.12", "output.Virtual-1.rotation.none",
             "output.Virtual-1.scale.1.25", "output.Virtual-1.position.0,0", "output.Virtual-1.mirror.none",
             "output.Virtual-1.primary"] and all(bi.geldige_herstel(x) for x in _h), f"22: herstel-stappen voor de VM ({_h})")
_110 = copy.deepcopy(VM_KSCREEN)
_110["outputs"][0]["scale"] = 1.1
_h110 = bi.stappen_herstel(bi.lees_beeldschermen(ks(_110)))
klopt("output.Virtual-1.scale.1.1" in _h110 and all(bi.geldige_herstel(x) for x in _h110),
      "I2: een grootte van 110 % (uit KDE) kan terug")

# 25: het vangnet van systemd
_opd, _e = vang(bi.vangnet_aan, _h)
_c = _opd[0] if _opd else ()
klopt(_e and _e.startswith("bugos-scherm-terug-") and _c[:4] == ("systemd-run", "--user", "--quiet", f"--unit={_e}")
      and "--on-active=60" in _c and _c[_c.index("--") + 1].endswith("kscreen-doctor") and list(_c[_c.index("--") + 2:]) == _h,
      f"25: vangnet: systemd-run --user … --on-active=60 -- kscreen-doctor <herstel> ({_c[:6]})")
_opd, _e2 = vang(bi.vangnet_aan, _h)
klopt(_e2 != _e, "25: elk vangnet heeft een eigen naam (ook binnen dezelfde seconde)")
klopt(vang(bi.vangnet_aan, _h, antwoord=lambda c: (1, ""))[1] is None, "25: systemd-run lukt niet: geen vangnet (None)")
_opd, _ = vang(bi.vangnet_aan, _h + ["output.x.scale.0.1"])
klopt(_ == None and _opd == [], "I2c: het vangnet zet alleen geldige herstel-stappen")  # noqa: E711
_opd, _ok = vang(bi.vangnet_uit, "bugos-scherm-terug-1-2-3")
klopt(_ok and _opd == [("systemctl", "--user", "stop", "bugos-scherm-terug-1-2-3.timer")], "25: vangnet uit: systemctl --user stop ….timer")
klopt(vang(bi.vangnet_uit, None)[1] is True and vang(bi.vangnet_uit, "x; rm")[0] == [], "25: geen vangnet: niets; een rare naam: niets")
# I3: als de vraag opengaat een verse timer (eerst de nieuwe, dan de oude uit)
_opd, _n = vang(bi.vangnet_opnieuw, "bugos-scherm-terug-1-2-3", _h, 30)
klopt(_n and _n != "bugos-scherm-terug-1-2-3" and _opd[0][0] == "systemd-run" and "--on-active=30" in _opd[0]
      and _opd[1] == ("systemctl", "--user", "stop", "bugos-scherm-terug-1-2-3.timer"),
      "I3: de vraag gaat open: eerst een nieuwe timer (30 s), dan de oude uit")
_opd, _n = vang(bi.vangnet_opnieuw, "bugos-scherm-terug-1-2-3", _h, 30, antwoord=lambda c: (1, ""))
klopt(_n == "bugos-scherm-terug-1-2-3" and not any(c[0] == "systemctl" for c in _opd), "I3: lukt de nieuwe niet, dan blijft de oude")

# 26: een verandering die niet lukt
_staat = copy.deepcopy(VM_KSCREEN)


def _mislukt_dan_herstel(cmd):
    if cmd[0] == "kscreen-doctor" and cmd[1:] == ("-j",):
        return 0, ks(_staat)
    if cmd[0] == "kscreen-doctor" and "output.Virtual-1.mode.21" in cmd:
        return 0, "applying config failed!\n"
    return 0, ""


_opd, _w = vang(bi.scherm_wijzigen, ["output.Virtual-1.mode.21"], antwoord=_mislukt_dan_herstel)
_na = [c for c in _opd if c[1:] != ("-j",)]
klopt(_w.gelukt is False and _w.terug and _w.vangnet is None and _na[0][0] == "systemd-run"
      and _na[1] == ("kscreen-doctor", "output.Virtual-1.mode.21") and _na[2] == ("kscreen-doctor", *_h)
      and _na[3][:3] == ("systemctl", "--user", "stop"),
      f"26: mislukt: vangnet aan, de stap, terugzetten, en dan pas het vangnet uit ({[c[:2] for c in _na]})")
_opd, _w = vang(bi.scherm_wijzigen, ["output.Virtual-1.mode.21"],
                antwoord=lambda c: (0, ks(_staat)) if c[1:] == ("-j",) else (0, "failed\n") if c[0] == "kscreen-doctor" else (0, ""))
klopt(_w.gelukt is False and not _w.terug and _w.vangnet and not any(c[0] == "systemctl" for c in _opd),
      "I2: mislukt en terugzetten lukt ook niet: het vangnet blijft staan (geen systemctl stop)")
_opd, _w = vang(bi.scherm_wijzigen, ["output.Virtual-1.primary"], antwoord=ks_fake(copy.deepcopy(VM_KSCREEN)))
klopt(_w.gelukt and not _w.risico and not any(c[0] == "systemd-run" for c in _opd), "26: hoofdscherm kiezen is geen risico: geen vangnet")
_staat = copy.deepcopy(VM_KSCREEN)
_opd, _w = vang(bi.scherm_wijzigen, ["output.Virtual-1.rotation.left"], antwoord=ks_fake(_staat))
klopt(_w.gelukt and _w.risico and _w.vangnet and _staat["outputs"][0]["rotation"] == 2
      and _staat["outputs"][0]["size"] == {"width": 1200, "height": 1920}, "26: draaien lukt (met vangnet); breedte en hoogte wisselen")
_opd, _ok = vang(bi.scherm_terug, _w.herstel, _w.vangnet, antwoord=ks_fake(_staat))
klopt(_ok and _staat["outputs"][0]["rotation"] == 1 and _opd[-1][:3] == ("systemctl", "--user", "stop"),
      "26: 'Terugzetten': weer gewoon, en het vangnet uit")


# ============================================================================== schermen: meer schermen ===
def twee(**anders) -> dict:
    """Het voorbeeld met een tv; anders={'HDMI-A-1': {...}} verandert velden van een scherm."""
    d = copy.deepcopy(TWEE)
    for o in d["outputs"]:
        o.update(anders.get(o["name"], {}))
    return d


# 18: twee schermen lezen: volgorde, soort, hoofdscherm, en hoe ze samen staan
_l2 = bi.lees_beeldschermen(ks(TWEE))
klopt([s.naam for s in _l2] == ["eDP-1", "HDMI-A-1"] and [s.soort for s in _l2] == ["ingebouwd", "hdmi"]
      and _l2[0].hoofd and not _l2[1].hoofd and bi.schermstand(_l2) == "uitbreiden" and _l2[0].logisch == (1536, 960),
      "18: twee schermen: eerst de laptop, dan de tv; de laptop is het hoofdscherm; uitgebreid")
klopt(bi.schermstand(bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"replicationSource": 1}})))) == "kopie"
      and bi.schermstand(bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"enabled": False}})))) == "alleen:eDP-1",
      "18: de tv doet de laptop na: 'kopie'; de tv uit: 'alleen:eDP-1'")
_l2r = bi.lees_beeldschermen(ks(twee(**{"eDP-1": {"pos": {"x": 1920, "y": 0}}, "HDMI-A-1": {"pos": {"x": 0, "y": 0}}})))
klopt([s.naam for s in _l2r] == ["HDMI-A-1", "eDP-1"] and bi.schermnummers(_l2r) == {"eDP-1": 1, "HDMI-A-1": 2}
      and bi.schermnummers(bi.lees_beeldschermen(ks(twee(**{"eDP-1": {"enabled": False}})))) == {"eDP-1": 1, "HDMI-A-1": 2},
      "18: de nummers blijven vast (de laptop 1, de tv 2), ook als de tv links staat of de laptop uit is")
_lu = bi.lees_beeldschermen(ks(twee(**{"eDP-1": {"enabled": False}})))
klopt([s.naam for s in _lu] == ["HDMI-A-1", "eDP-1"] and _lu[0].hoofd and not _lu[1].hoofd
      and bi.lees_beeldschermen(ks(twee(**{"eDP-1": {"enabled": False, "priority": 1}, "HDMI-A-1": {"priority": 2}})))[0].hoofd,
      "18: staat het hoofdscherm uit, dan is het eerste scherm dat aan staat het hoofdscherm")

# 21: de stappen, precies
klopt(bi.stappen_alleen(_l2, "HDMI-A-1") == ["output.HDMI-A-1.enable", "output.HDMI-A-1.mirror.none",
                                              "output.HDMI-A-1.position.0,0", "output.eDP-1.disable",
                                              "output.HDMI-A-1.primary"],
      f"21: alleen de tv ({bi.stappen_alleen(_l2, 'HDMI-A-1')})")
klopt(bi.stappen_kopie(_l2) == ["output.eDP-1.enable", "output.eDP-1.mirror.none", "output.HDMI-A-1.enable",
                                "output.HDMI-A-1.mirror.eDP-1"], f"21: hetzelfde beeld ({bi.stappen_kopie(_l2)})")
klopt(bi.stappen_uitbreiden(_l2) == ["output.eDP-1.enable", "output.eDP-1.mirror.none", "output.HDMI-A-1.enable",
                                     "output.HDMI-A-1.mirror.none"],
      "21: uitbreiden terwijl ze al netjes naast elkaar staan: geen nieuwe plekken")
_over = bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"pos": {"x": 0, "y": 0}, "replicationSource": 1}})))
klopt(bi.stappen_uitbreiden(_over)[-2:] == ["output.eDP-1.position.0,0", "output.HDMI-A-1.position.1536,0"],
      f"21: uitbreiden na 'hetzelfde beeld': de tv rechts naast de laptop ({bi.stappen_uitbreiden(_over)[-2:]})")
_plek = {k: bi.stappen_plek(_l2, "HDMI-A-1", k) for k in ("rechts", "links", "boven", "onder")}
klopt(_plek["links"] == ["output.eDP-1.position.1920,0", "output.HDMI-A-1.position.0,0"]
      and _plek["rechts"] == ["output.eDP-1.position.0,0", "output.HDMI-A-1.position.1536,0"]
      and _plek["boven"] == ["output.eDP-1.position.0,1080", "output.HDMI-A-1.position.0,0"]
      and _plek["onder"] == ["output.eDP-1.position.0,0", "output.HDMI-A-1.position.0,960"]
      and bi.stappen_plek(_l2, "eDP-1", "links") == [] and bi.stappen_plek(_l2, "HDMI-A-1", "schuin") == [],
      f"21: waar staat de tv: links, rechts, boven, onder (alles begint bij 0,0); het hoofdscherm zelf: niets ({_plek})")
klopt(bi.huidige_kant(_l2, "HDMI-A-1") == "rechts" and bi.huidige_kant(_l2, "eDP-1") is None
      and bi.huidige_kant(_l2r, "HDMI-A-1") == "links", "21: huidige_kant: de tv staat rechts (of links)")
_drie = twee()
_drie["outputs"].append(dict(copy.deepcopy(TWEE["outputs"][1]), id=3, name="DP-2", type=0, pos={"x": 3456, "y": 0}))
_l3 = bi.lees_beeldschermen(ks(_drie))
_p3 = bi.stappen_plek(_l3, "DP-2", "links")
klopt(_p3 == ["output.eDP-1.position.1920,0", "output.HDMI-A-1.position.3456,0", "output.DP-2.position.0,0"],
      f"C4: drie schermen, de derde naar links: voorbij alles wat er al staat, niets over elkaar ({_p3})")

# I4: een scherm wordt groter of kleiner: de andere schuiven mee (geen gat, niet over elkaar)
klopt(bi.plekken_na(_l2, ["output.HDMI-A-1.scale.2"]) == [],
      "I4: de tv naar 200 %: de tv blijft op x=1536 (hij staat rechts; links verandert niets)")
klopt(bi.plekken_na(_l2, ["output.eDP-1.mode.4", "output.eDP-1.scale.1"]) == ["output.HDMI-A-1.position.1280,0"],
      f"I4: de laptop naar 1280x800 op 100 %: de tv schuift naar x=1280 ({bi.plekken_na(_l2, ['output.eDP-1.mode.4', 'output.eDP-1.scale.1'])})")
klopt(bi.plekken_na(_l2r, ["output.HDMI-A-1.scale.2"]) == ["output.eDP-1.position.960,0"],
      "I4: de tv links naar 200 % (960 breed): de laptop schuift mee naar x=960")
klopt(bi.plekken_na(_l2, ["output.eDP-1.rotation.left"]) == ["output.HDMI-A-1.position.960,0"],
      "I4: de laptop op zijn kant (960 breed): de tv schuift naar x=960")
klopt(bi.plekken_na(bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"replicationSource": 1}}))),
                    ["output.eDP-1.scale.1"]) == [] and bi.plekken_na(_vm, ["output.Virtual-1.scale.1"]) == [],
      "I4: hetzelfde beeld of maar één scherm: geen plekken")
_staat = twee()
_opd, _ok = vang(bi.zet_schaal, 1.0, "eDP-1", antwoord=ks_fake(_staat))
klopt(_ok and ("kscreen-doctor", "output.eDP-1.scale.1", "output.HDMI-A-1.position.1920,0") in _opd
      and _staat["outputs"][1]["pos"] == {"x": 1920, "y": 0} and _staat["outputs"][1]["scale"] == 1.0,
      "I4: de laptop naar 100 % (1920 breed): in dezelfde opdracht schuift de tv naar x=1920")
_staat = twee()
_opd, _w = vang(bi.scherm_wijzigen, ["output.eDP-1.mode.4"], antwoord=ks_fake(_staat))
klopt(_w.gelukt and _staat["outputs"][1]["pos"]["x"] == 1024, "I4: andere resolutie op de laptop: de tv schuift mee (x=1024)")

# I5: 'Uitbreiden' na 'Alleen 1': de tv staat uit; zonder bruikbare stand de aanbevolen stand
_uit = bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"enabled": False, "currentModeId": "", "size": {"width": 0, "height": 0}}})))
_u = bi.stappen_uitbreiden(_uit)
klopt(_u == ["output.eDP-1.enable", "output.eDP-1.mirror.none", "output.HDMI-A-1.enable", "output.HDMI-A-1.mirror.none",
             "output.HDMI-A-1.mode.12", "output.eDP-1.position.0,0", "output.HDMI-A-1.position.1536,0"],
      f"I5: de tv weer aan met zijn aanbevolen stand (4K), rechts van de laptop ({_u})")
_geen = bi.lees_beeldschermen(ks(twee(**{"HDMI-A-1": {"enabled": False, "currentModeId": "", "modes": [],
                                                       "preferredModes": [], "size": {"width": 0, "height": 0}}})))
_g = bi.stappen_uitbreiden(_geen)
klopt("output.HDMI-A-1.enable" in _g and not any(s.startswith("output.HDMI-A-1.position") for s in _g)
      and not any(".mode." in s for s in _g), f"I5: zonder enige stand: aanzetten zonder plek ({_g})")
_staat = twee(**{"HDMI-A-1": {"enabled": False}})
_opd, _w = vang(bi.scherm_wijzigen, bi.stappen_uitbreiden(bi.lees_beeldschermen(ks(_staat))), antwoord=ks_fake(_staat))
klopt(_w.gelukt and _w.risico and _staat["outputs"][1]["enabled"], "I5: 'Uitbreiden' na 'Alleen 1' lukt (met vangnet)")
_h2 = bi.stappen_herstel(_uit)
klopt(_h2[-2:] == ["output.HDMI-A-1.disable", "output.eDP-1.primary"] and all(bi.geldige_herstel(x) for x in _h2),
      f"22: terugzetten met een scherm dat uit staat: dat gaat weer uit, en het hoofdscherm blijft ({_h2[-2:]})")


# =========================================================================================== energie ===
# 31: hoe lang de batterij nog gaat (UPower; in de VM zonder batterij 'x 0' en 'x 0')
klopt(bi.lees_busctl_getallen("x 12000\nx 0\n") == [12000, 0] and bi.lees_busctl_getallen("rommel\nx\nx 5 6\n") == [],
      "31: busctl-getallen lezen ('x 12000'); rommel telt niet")
_opd, _bt = vang(bi.batterij_tijd, antwoord=lambda c: (0, "x 12000\nx 0\n"))
klopt(_opd == [("busctl", "--system", "get-property", "org.freedesktop.UPower",
                "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device", "TimeToEmpty",
                "TimeToFull")] and _bt == (12000, 0), "31: batterij_tijd vraagt UPower TimeToEmpty en TimeToFull")
klopt(vang(bi.batterij_tijd, antwoord=lambda c: (0, "x 5\n"))[1] == (0, 0)
      and vang(bi.batterij_tijd, antwoord=lambda c: (1, "x 5\nx 6\n"))[1] == (0, 0),
      "31: één getal, of busctl mislukt: (0, 0), dan zeggen we niets over de tijd")
# 32 en I8: afronden op 5 minuten, eerst alles samen (nooit '60 min' of '1 u 60 min')
_d = {s: bi.duur_tekst(s) for s in (12000, 2700, 7200, 3500, 7100, 3300, 61, 100)}
klopt(_d == {12000: "3 u 20 min", 2700: "45 min", 7200: "2 u", 3500: "1 u", 7100: "2 u", 3300: "55 min", 61: "5 min",
             100: "5 min"}, f"32/I8: duur_tekst ({_d})")


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


# 9: hoe hard een stukje geluid is (16 bits, little-endian; -60 dB is 0, 0 dB is 100)
import struct  # noqa: E402

_n = [bi.niveau(b""), bi.niveau(b"\x01\x00" * 400), bi.niveau(struct.pack("<h", 32767) * 4),
      bi.niveau(struct.pack("<h", -12702) * 9), bi.niveau(struct.pack("<h", 328) * 3), bi.niveau(b"\x00\x40\x01")]
klopt(_n[:5] == [0, 0, 100, 86, 33] and 0 <= _n[5] <= 100,
      f"9: niveau: stil 0, piek 1 is 0, de hoogste 100, 12702 is 86, 328 is 33; een oneven lengte geeft geen fout ({_n})")
# 10 (en I9): de test neemt op van de microfoon die gesprekken gebruiken
_opd, _cmd = vang(bi.microfoon_test_opdracht)
klopt(_cmd == ["parec", "-d", "@DEFAULT_SOURCE@", "-n", "BugOS Settings", "--stream-name=Microphone test", "--raw",
               "--format=s16le", "--channels=1", "--rate=8000", "--latency-msec=50"],
      "10/I9: de testopdracht: parec van @DEFAULT_SOURCE@, 8000 Hz mono, met de naam 'BugOS Settings'")
klopt(vang(bi.microfoon_test_opdracht, "-x")[1] == [], "10: een rare naam: geen opdracht")
_w = shutil.which
shutil.which = lambda n, *a, **k: None
klopt(bi.microfoon_test_opdracht() == [], "10: zonder parec: geen opdracht")
shutil.which = _w
klopt(vang(bi.microfoon_klaar, antwoord=_pactl())[1] == "ok"
      and vang(bi.microfoon_klaar, antwoord=_pactl(standaard="weg.mic"))[1] == "weg"
      and vang(bi.microfoon_klaar, antwoord=_pactl(lijst_code=1))[1] == "weg",
      "I9: vlak voor de test: is de gekozen microfoon er nog (anders neemt parec stilletjes een andere)")


# ======================================================================================== het venster ===
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QPoint, QThreadPool, QTimer  # noqa: E402
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
# 13, 14, 16: de microfoon testen (voorbeeldstand: een balk die beweegt, zonder echte microfoon)
ss.TEST_SECONDEN = 1.5
bi._VB["mic_stil"] = False
gp.ververs()
wacht()
gp.test_knop.click()
wacht()
wacht_ms(500)
klopt(gp.test_bezig and gp.meter.isVisibleTo(gp) and gp.meter.value() > 0 and gp.test_knop.text() == "Stoppen",
      f"13: Testen: de balk staat er en beweegt ({gp.meter.value()}), de knop heet 'Stoppen'")
wacht_ms(1400)
klopt(not gp.test_bezig and not gp.meter.isVisibleTo(gp) and "werkt" in gp.melding.tekst.text(),
      f"13: na de test: 'Je microfoon werkt.' ({gp.melding.tekst.text()!r})")
_oud_niv = ss.VB_NIVEAUS
ss.VB_NIVEAUS = (30, 32, 31, 30, 33, 30, 34, 36, 35, 33)   # alleen het geruis van de kamer (I10)
gp.test_knop.click()
wacht()
wacht_ms(1700)
ss.VB_NIVEAUS = _oud_niv
klopt("hoorden niets" in gp.melding.tekst.text(), f"I10: alleen geruis van de kamer telt niet als 'gehoord' ({gp.melding.tekst.text()!r})")
bi._VB["mic_stil"] = True
gp.ververs()
wacht()
gp.test_knop.click()
wacht()
klopt(not gp.test_bezig and not gp.meter.isVisibleTo(gp) and "staat uit" in gp.melding.tekst.text(),
      "14: de microfoon staat uit: de test begint niet, 'Zet hem eerst aan'")
bi._VB["mic_stil"] = False
gp.ververs()
wacht()
ss.TEST_SECONDEN = 20
gp.test_knop.click()
wacht()
wacht_ms(200)
_was = gp.test_bezig
venster.ga_naar("meldingen")   # een ander tabje: de pagina gaat weg
wacht()
klopt(_was and not gp.test_bezig and gp._proces is None and not gp._test_klok.isActive(),
      "16: weg van de pagina tijdens de test: de test stopt (BugOS luistert niet stiekem door)")
venster.ga_naar("geluid")
wacht()
gp.test_knop.click()
wacht()
wacht_ms(200)
gp.mic_uit.setChecked(True)
klopt(not gp.test_bezig, "A: 'Microfoon uit' tijdens de test: de test stopt")
gp.mic_uit.setChecked(False)
wacht()

# 33: de pagina Energie (voorbeeld: 76 %, op de batterij, 12000 s)
venster.ga_naar("energie")
wacht()
ep = venster.paginas["energie"]
klopt(ep.batterij.uitleg.text() == "76% · op batterij · nog ongeveer 3 u 20 min",
      f"33: Energie: 'nog ongeveer 3 u 20 min' ({ep.batterij.uitleg.text()!r})")
ep.toon((bi.Batterij(50, True, False), None, 300, 600, bi.KNOP_VRAGEN, bi.KNOP_SLAPEN, "AC", (0, 2700)))
klopt(ep.batterij.uitleg.text() == "50% · wordt opgeladen · vol over ongeveer 45 min",
      f"33: aan de lader: 'vol over ongeveer 45 min' ({ep.batterij.uitleg.text()!r})")
ep.toon((bi.Batterij(50, False, False), None, 300, 600, bi.KNOP_VRAGEN, bi.KNOP_SLAPEN, "Battery", (30, 0)))
_u1 = ep.batterij.uitleg.text()
ep.toon((bi.Batterij(50, False, False), None, 300, 600, bi.KNOP_VRAGEN, bi.KNOP_SLAPEN, "Battery", (60 * 3600, 0)))
_u2 = ep.batterij.uitleg.text()
ep.toon((bi.Batterij(50, False, False), None, 300, 600, bi.KNOP_VRAGEN, bi.KNOP_SLAPEN, "Battery"))
klopt(_u1 == _u2 == ep.batterij.uitleg.text() == "50% · op batterij",
      "33: een tijd die niet kan (30 s, 60 uur) of de oude vorm zonder tijd: geen tijd erbij")
_titel_x = ep.titel.mapTo(ep.widget(), QPoint(0, 0)).x()
_kaart_x = ep.profielen["balanced"].parentWidget().mapTo(ep.widget(), QPoint(0, 0)).x() + \
    min(k.x() for k in ep.profielen.values())
klopt(_kaart_x == _titel_x, f"D06: de drie profielkaarten beginnen op de lijn van de titel ({_kaart_x} en {_titel_x})")
ep.ververs()
wacht()

# 27, 28 (één scherm), 29: de pagina Scherm
venster.ga_naar("scherm")
wacht()
sp = venster.paginas["scherm"]
klopt("1920 × 1200" in sp.resolutie_rij.uitleg.text() and sp.hz_rij.isVisibleTo(sp)
      and sorted(sp.hz.inhoud.knoppen) == [48, 60] and sp.hz.inhoud.knoppen[60].isChecked()
      and len(sp.draai.knoppen) == 4 and sp.draai.knoppen[1].isChecked() and sp.beeld_kop.text() == "Beeld",
      f"27: één scherm: resolutie 'nu 1920 × 1200', 48 en 60 Hz, vier knoppen om te draaien ({sp.resolutie_rij.uitleg.text()!r})")


def houden_klikken(knop: str, na_ms: int = 300) -> None:
    """Klik straks op een knop van 'Beeld houden?' (die opent in een eigen lus, binnen een terugroep)."""
    def doe():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, ss.HoudenDialoog) and w.isVisible():
                getattr(w, knop).click()
                return
        QTimer.singleShot(100, doe)   # nog niet open
    QTimer.singleShot(na_ms, doe)


def kscreen_vb() -> dict:
    return {o["name"]: o for o in bi._VB["kscreen"]["outputs"]}


houden_klikken("houden")
sp.draai.knoppen[2].click()
wacht()
wacht()
klopt(kscreen_vb()["eDP-1"]["rotation"] == 2 and "blijft" in sp.melding.tekst.text() and not sp.bezig,
      f"28: draaien naar links en 'Houden': het blijft ({sp.melding.tekst.text()!r})")
ss.TERUG_NA = 1
sp.draai.knoppen[8].click()
wacht()
wacht_ms(1600)
wacht()
klopt(kscreen_vb()["eDP-1"]["rotation"] == 2 and "zoals het was" in sp.melding.tekst.text(),
      f"28: draaien naar rechts en niets doen: na de tijd weer zoals het was ({sp.melding.tekst.text()!r})")
_oud_uit = bi.vangnet_uit
bi.vangnet_uit = lambda e: False
houden_klikken("houden")
sp.draai.knoppen[1].click()
wacht()
wacht()
bi.vangnet_uit = _oud_uit
klopt(kscreen_vb()["eDP-1"]["rotation"] == 1 and "misschien" in sp.melding.tekst.text(),
      f"I3: 'Houden', maar de timer stopt niet: 'blijft misschien niet' ({sp.melding.tekst.text()!r})")
ss.TERUG_NA = 15


class NepKies:
    gekozen = (1280, 800)

    def __init__(self, ouder, titel, items, huidig=None, zoek_hint=""):
        NepKies.items, NepKies.huidig = items, huidig

    def exec(self):
        return 1


_oud_kies = ss.KiesDialoog
ss.KiesDialoog = NepKies
houden_klikken("terug")
sp.kies_resolutie()
wacht()
wacht()
ss.KiesDialoog = _oud_kies
klopt(NepKies.huidig == (1920, 1200) and NepKies.items[0] == ((1920, 1200), "1920 × 1200 (aanbevolen)")
      and kscreen_vb()["eDP-1"]["currentModeId"] == "1" and "zoals het was" in sp.melding.tekst.text(),
      f"28: resolutie kiezen (1280 × 800) en 'Terugzetten': weer 1920 × 1200 ({NepKies.items[:1]})")
# 29: de vraag zelf: Esc gaat terug, Enter ook (Terugzetten is de standaardknop)
from PySide6.QtCore import Qt as _Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

_d = ss.HoudenDialoog(sp)
_d.show()
QTest.keyClick(_d, _Qt.Key.Key_Escape)
klopt(_d.result() == ss.QDialog.DialogCode.Rejected and not _d.isVisible(), "29: Esc: terugzetten")
_d = ss.HoudenDialoog(sp)
klopt(_d.terug.isDefault() and not _d.houden.isDefault() and _d.terug.text() == "Terugzetten"
      and "15 seconden" in _d.teller.text(), "29: 'Terugzetten' is de standaardknop (Enter); 'Terug over 15 seconden'")
_d.close()
klopt(_d.result() == ss.QDialog.DialogCode.Rejected, "29: het kruisje: terugzetten")
sp.verander([])   # niets te doen: geen fout
wacht()

# 28: twee schermen (de laptop en een tv)
bi._VB["kscreen"] = twee()
sp.ververs()
wacht()
klopt(sp.schermen_kaart.isVisibleTo(sp) and sp.schermen_kop.isVisibleTo(sp)
      and list(sp.stand.inhoud.knoppen) == ["uitbreiden", "kopie", "alleen:eDP-1", "alleen:HDMI-A-1"]
      and [k.text() for k in sp.stand.inhoud.knoppen.values()] == ["Uitbreiden", "Hetzelfde beeld", "Alleen 1", "Alleen 2"]
      and sp.stand.inhoud.knoppen["uitbreiden"].isChecked() and sp.kies.inhoud.knoppen["eDP-1"].isChecked()
      and sp.kies_rij.uitleg.text() == "Ingebouwd scherm",
      "28: twee schermen: 'Je schermen' met vier keuzes (uitgebreid gekozen), instellen voor scherm 1 (de laptop)")
klopt(sp.beeld_kop.text() == "Scherm 1 · Ingebouwd scherm" and sp.hoofd_rij.isVisibleTo(sp)
      and sp.hoofd_chip.isVisibleTo(sp) and not sp.hoofd_knop.isVisibleTo(sp) and not sp.plek_rij.isVisibleTo(sp),
      f"28: de laptop is het hoofdscherm; geen 'Waar staat dit scherm?' voor het hoofdscherm ({sp.beeld_kop.text()!r})")
sp.kies.inhoud.knoppen["HDMI-A-1"].click()
klopt(sp.beeld_kop.text() == "Scherm 2 · Scherm of tv (HDMI)" and sp.hoofd_knop.isVisibleTo(sp)
      and sp.plek_rij.isVisibleTo(sp) and sp.plek.knoppen["rechts"].isChecked()
      and "1920 × 1080" in sp.resolutie_rij.uitleg.text() and sorted(sp.hz.inhoud.knoppen) == [50, 60]
      and sp.grootte.knoppen[1.5].isEnabled() and not sp.grootte.knoppen[1.75].isEnabled()
      and sp.grootte.knoppen[1.0].isChecked(),
      "28: de tv kiezen: zijn eigen resolutie (1920 × 1080), 50/60 Hz, 100 %, rechts van de laptop; tot 150 %")
sp.zet_grootte(1.5)
wacht()
wacht()
klopt(kscreen_vb()["HDMI-A-1"]["scale"] == 1.5 and kscreen_vb()["eDP-1"]["scale"] == 1.25
      and sp.kies.inhoud.knoppen["HDMI-A-1"].isChecked() and sp.grootte.knoppen[1.5].isChecked(),
      "28: de grootte geldt alleen voor het gekozen scherm (de tv 150 %, de laptop blijft 125 %)")
sp.plek.knoppen["links"].click()
wacht()
wacht()
klopt(kscreen_vb()["HDMI-A-1"]["pos"] == {"x": 0, "y": 0} and kscreen_vb()["eDP-1"]["pos"] == {"x": 1280, "y": 0}
      and sp.plek.knoppen["links"].isChecked() and sp.beeld_kop.text().startswith("Scherm 2")
      and "Klaar" in sp.melding.tekst.text(),
      f"28: de tv links: de tv op 0,0, de laptop ernaast; hij blijft 'Scherm 2' ({kscreen_vb()['eDP-1']['pos']})")
sp.hoofd_knop.click()
wacht()
wacht()
klopt(kscreen_vb()["HDMI-A-1"]["priority"] == 1 and kscreen_vb()["eDP-1"]["priority"] == 2
      and sp.hoofd_chip.isVisibleTo(sp) and not sp.plek_rij.isVisibleTo(sp),
      "28: 'Maak hoofdscherm': de tv is nu het hoofdscherm (zonder 'Beeld houden?': dat is geen risico)")
ss.TERUG_NA = 1
houden_klikken("houden")
sp.stand.inhoud.knoppen["alleen:HDMI-A-1"].click()
wacht()
wacht()
klopt(kscreen_vb()["eDP-1"]["enabled"] is False and kscreen_vb()["HDMI-A-1"]["enabled"]
      and sp.stand.inhoud.knoppen["alleen:HDMI-A-1"].isChecked() and "blijft" in sp.melding.tekst.text()
      and not sp.bezig and sp.schermen_kaart.isEnabled(),
      f"28: 'Alleen 2' en 'Houden': de laptop staat uit ({sp.melding.tekst.text()!r})")
sp.kies.inhoud.knoppen["eDP-1"].click()
klopt(sp.uit_rij.isVisibleTo(sp) and not sp.resolutie_rij.isVisibleTo(sp) and not sp.grootte_rij.isVisibleTo(sp)
      and sp.beeld_kop.text() == "Scherm 1 · Ingebouwd scherm",
      "28: de laptop kiezen terwijl hij uit staat: 'Dit scherm staat uit' met 'Aanzetten'")
houden_klikken("houden")
sp.uit_rij.rechts.click()
wacht()
wacht()
klopt(kscreen_vb()["eDP-1"]["enabled"] and sp.stand.inhoud.knoppen["uitbreiden"].isChecked()
      and not sp.uit_rij.isVisibleTo(sp),
      f"28/I5: 'Aanzetten': weer uitgebreid, de laptop staat weer aan ({kscreen_vb()['eDP-1'].get('pos')})")
sp.kies.inhoud.knoppen["HDMI-A-1"].click()
sp.draai.knoppen[2].click()
wacht()
wacht_ms(1600)
wacht()
klopt(kscreen_vb()["HDMI-A-1"]["rotation"] == 1 and "zoals het was" in sp.melding.tekst.text(),
      f"28: de tv draaien en niets doen: na de tijd weer gewoon ({sp.melding.tekst.text()!r})")
ss.TERUG_NA = 15
sp.hide()
sp.schermen_anders()   # een scherm erbij terwijl de pagina weg is: niets
klopt(True, "28: een scherm in- of uitpluggen terwijl de pagina dicht is: geen fout")
bi._VB["kscreen"] = copy.deepcopy(EEN_VB)
venster.ga_naar("geluid")
venster.ga_naar("scherm")
wacht()
klopt(not sp.schermen_kaart.isVisibleTo(sp) and sp.beeld_kop.text() == "Beeld",
      "28: weer één scherm: geen 'Je schermen', het kopje is 'Beeld'")
print(f"\n{fouten} fout(en).")
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fouten else 0)
