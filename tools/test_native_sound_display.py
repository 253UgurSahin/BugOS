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

print(f"\n{fouten} fout(en).")
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fouten else 0)
