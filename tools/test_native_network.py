#!/usr/bin/env python3
"""Test van het pakket 'network': wifi van school of werk, opgeslagen netwerken, de kabel en bluetooth koppelen,
allemaal in BugOS zelf (geen KDE-venster).

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai / bi.draai_nm vervangen), draaien met
nep-programma's in een tijdelijke map, of de pagina's draaien in de voorbeeldstand. D-Bus wordt niet gebruikt.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_network.py
"""

from __future__ import annotations

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
TMP = Path(tempfile.mkdtemp(prefix="bugos-native-network-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang(functie, *args, antwoord=lambda cmd: (0, ""), antwoord_nm=None, **kwargs):
    """Roep functie aan zonder voorbeeldstand; geef [(opdracht, invoer)] en de uitkomst. Vangt bi.draai
    (antwoord -> (code, uitvoer)) en bi.draai_nm (antwoord_nm -> (code, uitvoer, fouten))."""
    oud = (bi.VOORBEELD, bi.draai, bi.draai_nm, shutil.which)
    opdrachten: list = []
    if antwoord_nm is None:
        def antwoord_nm(cmd, invoer):  # noqa: ARG001
            code, uit = antwoord(cmd)
            return code, uit, ""
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append((cmd, kw.get("invoer"))), antwoord(cmd))[1]
    bi.draai_nm = lambda *cmd, **kw: (opdrachten.append((cmd, kw.get("invoer"))), antwoord_nm(cmd, kw.get("invoer")))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args, **kwargs)
    finally:
        bi.VOORBEELD, bi.draai, bi.draai_nm, shutil.which = oud
    return opdrachten, uit


def nep_programma(map_: Path, naam: str, inhoud: str) -> None:
    map_.mkdir(parents=True, exist_ok=True)
    p = map_ / naam
    p.write_text("#!/usr/bin/bash\n" + inhoud, encoding="utf-8", newline="\n")
    p.chmod(0o755)


# =============================================================== de kabel ===
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:connected:enp0s1\nloopback:connected (externally):lo\n"))
klopt(k == ("verbonden", "enp0s1"), f"kabel: verbonden ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:unavailable:enp3s0\n"))
klopt(k == ("los", "enp3s0"), f"kabel: niet aangesloten ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:disconnected:enp3s0\n"))
klopt(k == ("uit", "enp3s0"), f"kabel: zit erin, niet verbonden ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "wifi:connected:wlan0\n"))
klopt(k == ("", ""), f"kabel: geen netwerkpoort ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:unavailable:enp3s0\nethernet:connecting (getting IP configuration):enp4s0\n"))
klopt(k == ("bezig", "enp4s0"), f"kabel: met twee poorten telt de beste ({k})")
o, ok = vang(bi.kabel_verbind, "enp3s0")
klopt(ok and o and o[0][0][:2] == ("nmcli", "--wait") and o[0][0][-3:] == ("device", "connect", "enp3s0"),
      f"kabel: verbinden met nmcli device connect ({o[:1]})")
o, ok = vang(bi.kabel_verbind, "--help")
klopt(not ok and not o, "kabel: een apparaatnaam die met '-' begint, gaat niet naar nmcli")

# =========================================================== draai_nm echt ===
_nep = TMP / "nep-bin"
nep_programma(_nep, "nepnm", 'echo out; echo err >&2; exit 4\n')
nep_programma(_nep, "nepslaap", 'sleep 3\n')
klopt(bi.draai_nm(str(_nep / "nepnm")) == (4, "out\n", "err\n"), "draai_nm: geeft code, uitvoer en fouten")
klopt(bi.draai_nm(str(_nep / "bestaat-niet")) == (127, "", ""), "draai_nm: een programma dat er niet is: 127")
_t0 = time.time()
klopt(bi.draai_nm(str(_nep / "nepslaap"), timeout=1)[0] == 124 and time.time() - _t0 < 2.5,
      "draai_nm: te traag: 124 (en niet blijven wachten)")

# ===================================================== opgeslagen netwerken ===
def _antw_opg(cmd):
    if "NAME,UUID,TYPE,ACTIVE" in cmd:
        return 0, ("Home:u-1:802-11-wireless:yes\nWired connection 1:u-2:802-3-ethernet:yes\n"
                   "Cafe\\: De Hoek:u-3:802-11-wireless:no\nHome 1:u-4:802-11-wireless:no\n")
    if "802-11-wireless.ssid" in cmd:
        return 0, {"u-1": "Home\n", "u-3": "Cafe\\: De Hoek\n", "u-4": "Home\n"}[cmd[-1]]
    return 0, ""


_, _opg = vang(bi.opgeslagen_wifi, antwoord=_antw_opg)
klopt([(o.naam, o.uuids, o.actief) for o in _opg] == [("Home", ["u-1", "u-4"], True), ("Cafe: De Hoek", ["u-3"], False)],
      f"opgeslagen: alleen wifi, per netwerknaam samen ('Home' en 'Home 1'), verbonden eerst ({_opg})")
o, ok = vang(bi.vergeet_opgeslagen, _opg[0])
klopt(ok and [c for c, _i in o] == [("nmcli", "connection", "delete", "uuid", "u-1"),
                                    ("nmcli", "connection", "delete", "uuid", "u-4")],
      f"opgeslagen: vergeten gooit alle profielen van dat netwerk weg ({o})")
o, ok = vang(bi.vergeet_profiel, "-x")
klopt(not ok and not o, "opgeslagen: een uuid die met '-' begint, gaat niet naar nmcli")

# ================================================================ pagina's ===
# (alles hierboven raakt Qt niet; vanaf hier het venster van Instellingen in de voorbeeldstand)
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
venster = mod.Instellingen("start")
sn = sys.modules["bugos_settings_netwerk"]


def wacht(rondes: int = 5) -> None:
    for _ in range(rondes):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def wacht_ms(ms: int) -> None:
    eind = time.time() + ms / 1000
    while time.time() < eind:
        QThreadPool.globalInstance().waitForDone(20)
        app.processEvents()
        time.sleep(0.01)


venster.ga_naar("wifi")
wacht()
wifi = venster.paginas["wifi"]

# ---- de kabel op de pagina
bi.VB_NET["kabel"] = "los"
wifi.ververs()
wacht()
klopt(not wifi.kabel.isHidden() and "Niet aangesloten" in wifi.kabel.uitleg.text() and wifi.kabel_knop.isHidden(),
      f"kabel-regel: 'Niet aangesloten' als de kabel eruit is ({wifi.kabel.uitleg.text()!r})")
bi.VB_NET["kabel"] = "uit"
wifi.ververs()
wacht()
klopt(not wifi.kabel_knop.isHidden(), "kabel-regel: kabel erin maar niet verbonden: knop 'Verbinden'")
_kv = []
_oud_kv = bi.kabel_verbind
bi.kabel_verbind = lambda apparaat: (_kv.append(apparaat), True)[1]
wifi.kabel_knop.click()
wacht()
bi.kabel_verbind = _oud_kv
klopt(_kv == ["enp3s0"], f"kabel-regel: 'Verbinden' verbindt die poort ({_kv})")
bi.VB_NET["kabel"] = ""
wifi.ververs()
wacht()
klopt(wifi.kabel.isHidden(), "kabel-regel: zonder netwerkpoort geen regel")
wifi.toon((True, [], False, False))
klopt(wifi.kabel.isHidden() and wifi.lijst.isHidden(), "kabel-regel: de oude vorm (True/False) werkt nog (U111)")
wifi.toon((True, [], ("verbonden", "enp0s1"), False))
klopt(not wifi.kabel.isHidden() and "geen wifi" in wifi.hoofd.uitleg.text().lower(),
      "kabel-regel: zonder wifi in de computer staat de kabel er wel")
wifi.ververs()
wacht()

# ---- opgeslagen netwerken (in de eerste kaart, onder de schakelaar)
klopt(not wifi.opgeslagen.isHidden() and wifi.opgeslagen.parent() is wifi.hoofd.parent(),
      "opgeslagen: de regel 'Opgeslagen netwerken' staat in de eerste kaart, onder de wifi-schakelaar")
wifi.opgeslagen.geklikt.emit()
wacht()
_od = wifi.opgeslagen_dialoog
_namen = list(_od.rijen)
klopt(_od.isVisible() and _namen[:1] == ["Home"] and set(_namen) == {"Home", "Home-5G", "eduroam", "Hotel Zonneveld"}
      and _od.rijen["Home"].uitleg.text() == "Nu verbonden",
      f"opgeslagen: het venster toont de 4 voorbeeldnetwerken, 'Home' (verbonden) eerst ({_namen})")
_od.rijen["Hotel Zonneveld"].rechts.click()
wacht()
klopt("Hotel Zonneveld" not in _od.rijen and not _od.banner.isHidden() and "vergeten" in _od.banner.tekst.text(),
      f"opgeslagen: 'Vergeten' haalt de regel weg en zegt het ({_od.banner.tekst.text()!r})")
_oud_vo = bi.vergeet_opgeslagen
bi.vergeet_opgeslagen = lambda o: False
_od.rijen["Home-5G"].rechts.click()
wacht()
bi.vergeet_opgeslagen = _oud_vo
klopt("Home-5G" in _od.rijen and "lukte niet" in _od.banner.tekst.text() and _od.rijen["Home-5G"].rechts.isEnabled(),
      "opgeslagen: lukt vergeten niet, dan zegt het venster dat (en de knop doet het weer)")
_od.accept()
wacht()
wifi.toon((True, [], False, False))
klopt(wifi.opgeslagen.isHidden(), "opgeslagen: zonder wifi in de computer geen regel 'Opgeslagen netwerken'")
wifi.ververs()
wacht()

# ---- de lay-out-notities: kopjes met een knop, de wachtwoordvraag in BugOS-stijl, Engelse voorbeeldnamen
klopt(wifi.zoek_knop.parent().objectName() == "sectie_met_knop",
      "wifi: 'Opnieuw zoeken' staat in het kopje 'Netwerken in de buurt' (sectie_met_knop)")
import bugos_shell  # noqa: E402

_vd = {}


def _nep_exec(self):
    _vd["echo"] = self.veld.echoMode() if self.veld is not None else None
    _vd["uitleg"] = self.uitleg.text()
    self.veld.setText("ge heim")
    return 1


_oud_exec = bugos_shell.VraagDialoog.exec
bugos_shell.VraagDialoog.exec = _nep_exec
_ww = wifi.vraag_wachtwoord(bi.Netwerk("Thuis", 80, True, False))
bugos_shell.VraagDialoog.exec = lambda self: 0
_ww_weg = wifi.vraag_wachtwoord(bi.Netwerk("Thuis", 80, True, False), veranderd=True)
bugos_shell.VraagDialoog.exec = _oud_exec
from PySide6.QtWidgets import QLineEdit  # noqa: E402

klopt(_ww == "ge heim" and _ww_weg == "" and _vd.get("echo") == QLineEdit.EchoMode.Password and "Thuis" in _vd["uitleg"],
      f"wifi: het wachtwoord vragen gaat met BugOS' eigen vraag (bolletjes), Annuleren geeft '' ({_vd})")
_bron_cfg = (PY / "bugos_config_netwerk.py").read_text(encoding="utf-8")
klopt('t("Buren", "Neighbours")' in _bron_cfg and 't("Telefoon", "Phone")' in _bron_cfg and 't("Muis", "Mouse")' in _bron_cfg,
      "voorbeeldstand: de namen van buren, muis en telefoon zijn er ook in het Engels")
klopt(sn.apparaat_icoon("phone") == "telefoon", "bluetooth: een telefoon heeft het telefoon-icoon (geen tekstballon)")

# ==================================================================== eind ===
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
