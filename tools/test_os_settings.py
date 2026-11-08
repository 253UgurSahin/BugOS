#!/usr/bin/env python3
"""Test van de OS-fouten in BugOS Instellingen (U001 en verder): schrijven we de juiste dingen weg,
en lezen we de uitvoer goed, ook als de computer een andere taal spreekt?

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai vervangen) of draaien
met nep-programma's in een tijdelijke map.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_os_settings.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-os-settings-test-"))
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


def kde_sleutels(opdrachten) -> dict:
    """{(groep/groep, sleutel): waarde} uit de kwriteconfig6-opdrachten."""
    uit = {}
    for c in opdrachten:
        if c[0] != "kwriteconfig6":
            continue
        groepen = [c[i + 1] for i, x in enumerate(c) if x == "--group"]
        sleutel = c[c.index("--key") + 1]
        uit[("/".join(groepen), sleutel)] = c[-1]
    return uit


# U001: scherm uit 'Nooit' moet ook echt nooit zijn (TurnOffDisplayWhenIdle=false), en niet meteen dimmen.
opdr, _ = vang(bi.zet_scherm_uit_na, 0)
s = kde_sleutels(opdr)
klopt(all(s.get((f"{p}/Display", "TurnOffDisplayWhenIdle")) == "false" for p in bi.PROFIELGROEPEN)
      and all(s.get((f"{p}/Display", "DimDisplayWhenIdle")) == "false" for p in bi.PROFIELGROEPEN),
      "U001: scherm uit 'nooit' zet uitzetten en dimmen echt uit")
opdr, _ = vang(bi.zet_scherm_uit_na, 600)
s = kde_sleutels(opdr)
klopt(s.get(("AC/Display", "TurnOffDisplayWhenIdle")) == "true" and s.get(("AC/Display", "DimDisplayWhenIdle")) == "true"
      and s.get(("AC/Display", "TurnOffDisplayIdleTimeoutSec")) == "600",
      "U001: scherm uit na 10 minuten zet het weer aan")
_, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "false" if "TurnOffDisplayWhenIdle" in c else "30"))
klopt(na == 0, "U001: staat uitzetten uit, dan leest Instellingen 'nooit'")
_, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "true" if "TurnOffDisplayWhenIdle" in c else "300"))
klopt(na == 300, "U001: staat uitzetten aan, dan de tijd")


shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
