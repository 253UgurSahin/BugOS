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
antwoorden.update({("-t", "-f", "CONNECTIVITY", "general"): (0, "unknown\n"),
                   ("-t", "-f", "STATE", "general"): (0, "connected\n")})
u = bh.controle_internet()
klopt(u.stand == bh.OK, f"U090: internet 'unknown' maar wel verbonden: geen 'Geen verbinding' ({u.tekst})")
antwoorden[("-t", "-f", "STATE", "general")] = (0, "disconnected\n")
klopt(bh.controle_internet().stand == bh.PROBLEEM, "U090: internet 'unknown' en niet verbonden: wel 'Geen verbinding'")
# U091: na 'Opnieuw verbinden' wachten tot er weer internet is, voor Hulp opnieuw kijkt.
_gedaan: list = []
bh.draai = lambda *cmd, **kw: (_gedaan.append(cmd), (0, ""))[1]
bh.herstart_netwerk()
klopt(_gedaan and _gedaan[-1][0] == "nm-online", f"U091: na opnieuw verbinden wachten op het netwerk ({_gedaan[-1:]})")
# U092: Hulp kijkt niet online, dus zegt niet 'alles is bijgewerkt'.
import json as _json  # noqa: E402
for _modus in ("auto", "hand"):
    bh.draai = lambda *cmd, m=_modus, **kw: (0, _json.dumps({"deployments": [{"booted": True, "timestamp": 5}]})) \
        if cmd[0] == "rpm-ostree" else (0, m + "\n")
    u = bh.controle_updates()
    klopt(u.stand == bh.OK and "bijgewerkt" not in u.tekst and "up to date" not in u.tekst
          and ("herstart" in u.tekst or "restart" in u.tekst),
          f"U092: updates ({_modus}): zegt wat Hulp weet, niet 'alles is bijgewerkt' ({u.tekst})")
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

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
