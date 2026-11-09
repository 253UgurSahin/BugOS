#!/usr/bin/env python3
"""Test van 'Er werkt iets niet' (bugos-help): nakijken en repareren laten het venster nooit vastlopen.
Met nep-controles: er verandert niets aan je computer.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_help.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))
import bugos_ui  # noqa: E402

lader = importlib.machinery.SourceFileLoader("bugos_help", str(ROOT / "system_files" / "usr" / "bin" / "bugos-help"))
spec = importlib.util.spec_from_loader("bugos_help", lader)
bh = importlib.util.module_from_spec(spec)
lader.exec_module(bh)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


gerepareerd: list = []


def trage_controle():
    time.sleep(1.5)
    return bh.Uitslag("Geluid", bh.PROBLEEM, "Het geluid staat uit.",
                      lambda: (time.sleep(1.5), gerepareerd.append(1)), "Zet aan")


# B003: zonder printer zegt lpstat -p "No destinations added." (exit 1); dat is geen printer.
_echt = (bh.draai, bh.bestaat)
bh.bestaat = lambda naam: True
antwoorden = {("-r",): (0, "scheduler is running\n"), ("-p",): (1, "lpstat: No destinations added.\n"),
              ("-e",): (0, "")}
bh.draai = lambda *cmd, **kw: antwoorden[cmd[1:]]
u = bh.controle_printer()
tekst = u.tekst.lower()
klopt(u.stand == bh.OK and u.repareer is not None and ("nog geen printer" in tekst or "no printer" in tekst),
      "printer: zonder printer 'nog geen printer toegevoegd', met de knop erbij")
antwoorden.update({("-p",): (0, "printer HP is idle.  enabled since Mon\n"), ("-e",): (0, "HP\n")})
u = bh.controle_printer()
klopt(u.stand == bh.OK and u.repareer is None, "printer: met een printer die klaarstaat 'Printer is klaar'")
# U090: "unknown" met een verbinding is geen "Geen verbinding".
antwoorden.update({("-t", "-f", "TYPE", "device"): (0, "wifi\nethernet\n"),
                   ("-t", "-f", "CONNECTIVITY", "general"): (0, "unknown\n"),
                   ("-t", "-f", "STATE", "general"): (0, "connected\n")})
u = bh.controle_internet()
klopt(u.stand == bh.OK, f"U090: internet 'unknown' maar wel verbonden: geen 'Geen verbinding' ({u.tekst})")
antwoorden[("-t", "-f", "STATE", "general")] = (0, "disconnected\n")
klopt(bh.controle_internet().stand == bh.PROBLEEM, "U090: internet 'unknown' en niet verbonden: wel 'Geen verbinding'")
# U174: een pc zonder wifi (aan een kabel): niet 'kies je wifi', wel 'zit de kabel erin?'.
antwoorden[("-t", "-f", "TYPE", "device")] = (0, "ethernet\nloopback\n")
u = bh.controle_internet()
klopt("kabel" in u.tekst or "cable" in u.tekst, f"U174: geen wifi in de computer: vraag naar de netwerkkabel ({u.tekst})")
antwoorden[("-t", "-f", "TYPE", "device")] = (0, "wifi\nethernet\n")
# U091: na 'Opnieuw verbinden' wachten tot er weer internet is, voor Hulp opnieuw kijkt.
_gedaan: list = []
bh.draai = lambda *cmd, **kw: (_gedaan.append(cmd), (0, ""))[1]
bh.herstart_netwerk()
klopt(_gedaan and _gedaan[-1][0] == "nm-online" and int(_gedaan[-1][-1]) <= 10, f"U091: na opnieuw verbinden wachten op het netwerk ({_gedaan[-1:]})")
# U092: Hulp kijkt niet online, dus zegt niet 'alles is bijgewerkt'.
import json as _json  # noqa: E402
for _modus in ("auto", "hand"):
    bh.draai = lambda *cmd, m=_modus, **kw: (0, _json.dumps({"deployments": [{"booted": True, "timestamp": 5}]})) \
        if cmd[0] == "rpm-ostree" else (0, m + "\n")
    u = bh.controle_updates()
    klopt(u.stand == bh.OK and "bijgewerkt" not in u.tekst and "up to date" not in u.tekst
          and ("herstart" in u.tekst or "restart" in u.tekst),
          f"U092: updates ({_modus}): zegt wat Hulp weet, niet 'alles is bijgewerkt' ({u.tekst})")
    if _modus == "hand":
        klopt("Winkel" not in u.tekst and "Store" not in u.tekst and u.repareer is not None,
              f"U100: zelf updaten: Hulp wijst naar 'Nu updaten' in Instellingen, niet naar de Winkel ({u.tekst})")
bh.draai, bh.bestaat = _echt

bh.CONTROLES = [trage_controle]
venster_ = {}
bugos_ui.uitvoeren = lambda app, w: venster_.setdefault("w", w) and 0  # niet blijven wachten: de test bestuurt het
bh.venster()
app = bugos_ui.QApplication.instance()
w = venster_["w"]


def wacht(tot, seconden: float = 10) -> bool:
    eind = time.monotonic() + seconden
    while time.monotonic() < eind:
        app.processEvents()
        if tot():
            return True
        time.sleep(0.02)
    return False


begin = time.monotonic()
wacht(lambda: w.bezig, 2)
klopt(w.bezig and time.monotonic() - begin < 1.0, "nakijken: gebeurt op de achtergrond, het venster blijft reageren")
klopt(wacht(lambda: not w.bezig and w.laatste), "nakijken: daarna staat de uitslag in het venster")
klopt(w.kop.text().startswith(("1 ding", "1 thing")), "nakijken: '1 ding om naar te kijken'")
knop = next(k for k in w.findChildren(bugos_ui.Knop) if k.text() == "Zet aan")
begin = time.monotonic()
knop.click()
klopt(time.monotonic() - begin < 0.5 and not knop.isEnabled(), "repareren: op de achtergrond, de knop zegt 'Bezig…'")
klopt(wacht(lambda: gerepareerd == [1] and not w.klusjes and not w.bezig, 15), "repareren: daarna opnieuw nagekeken")
w.close()

# U290: bluetooth uitgezet met de vliegtuigstand (geen Controller, wel een rfkill-schakelaar die uit staat):
# Hulp zegt 'staat uit' met een knop, niet 'geen bluetooth'.
import os  # noqa: E402
import tempfile as _tf  # noqa: E402

_sys = Path(_tf.mkdtemp())
(_sys / "class" / "rfkill" / "rfkill0").mkdir(parents=True)
(_sys / "class" / "rfkill" / "rfkill0" / "type").write_text("bluetooth\n")
(_sys / "class" / "rfkill" / "rfkill0" / "soft").write_text("1\n")
(_sys / "class" / "bluetooth").mkdir(parents=True)
_oud_sys = os.environ.get("BUGOS_SYS")
os.environ["BUGOS_SYS"] = str(_sys)
_echt2 = (bh.draai, bh.bestaat)
bh.draai = lambda *cmd, **kw: (1, "No default controller available")
bh.bestaat = lambda _p: True
_u = bh.controle_bluetooth()
bh.draai, bh.bestaat = _echt2
if _oud_sys is None:
    os.environ.pop("BUGOS_SYS", None)
else:
    os.environ["BUGOS_SYS"] = _oud_sys
klopt(_u.stand == bh.LET_OP and _u.repareer is not None,
      f"U290: bluetooth uit door de vliegtuigstand: 'staat uit' met een knop om hem aan te zetten ({_u.stand})")
klopt('start("bugos-files"' in (ROOT / "system_files/usr/bin/bugos-help").read_text(),
      "U291: 'Laat zien wat ruimte inneemt' opent BugOS Bestanden (niet Dolphin)")

# U237: 'schijf bijna vol' schrijft in het Nederlands een komma (1,5 GB), zoals de rest van BugOS.
from collections import namedtuple as _nt  # noqa: E402

_oud_du, _oud_t = bh.shutil.disk_usage, bh.t
bh.shutil.disk_usage = lambda p: _nt("du", "total used free")(500 * 1024**3, 0, int(1.5 * 1024**3))
bh.t = lambda nl, en: nl
_u = bh.controle_opslag()
bh.shutil.disk_usage, bh.t = _oud_du, _oud_t
klopt("1,5 GB" in _u.tekst if hasattr(_u, "tekst") else "1,5 GB" in str(_u),
      f"U237: 'schijf bijna vol' schrijft 1,5 GB met een komma ({_u})")

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
