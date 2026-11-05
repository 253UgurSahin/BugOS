#!/usr/bin/env python3
"""Test van 'Er werkt iets niet' (bugos-hulp): nakijken en repareren laten het venster nooit vastlopen.
Met nep-controles: er verandert niets aan je computer.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_hulp.py
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

lader = importlib.machinery.SourceFileLoader("bugos_hulp", str(ROOT / "system_files" / "usr" / "bin" / "bugos-hulp"))
spec = importlib.util.spec_from_loader("bugos_hulp", lader)
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
