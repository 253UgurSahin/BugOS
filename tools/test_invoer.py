#!/usr/bin/env python3
"""Test van bugos-invoer: een nieuw touchpad scrollt zoals in Windows, maar één keer per touchpad (daarna is het de
keuze van de gebruiker), en een muis laat het met rust. Met de voorbeeld-aanwijzers van bugos_config_zien
(BUGOS_INSTELLINGEN_VOORBEELD=1): een Logitech-muis en een touchpad met natuurlijk scrollen aan.

Gebruik:  python3 tools/test_invoer.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files/usr/lib/bugos/python"
os.environ["BUGOS_INSTELLINGEN_VOORBEELD"] = "1"
os.environ["BUGOS_PYTHON"] = str(PY)
sys.path.insert(0, str(PY))
fouten = 0


def klopt(ok: bool, wat: str) -> None:
    global fouten
    print(("OK    " if ok else "FOUT  ") + wat)
    if not ok:
        fouten += 1


loader = importlib.machinery.SourceFileLoader("bugos_invoer", str(ROOT / "system_files/usr/bin/bugos-invoer"))
spec = importlib.util.spec_from_loader("bugos_invoer", loader)
invoer = importlib.util.module_from_spec(spec)
loader.exec_module(invoer)
import bugos_config  # noqa: E402,F401
import bugos_config_zien as zien  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    os.environ["XDG_CONFIG_HOME"] = tmp
    tp = next(a for a in zien.aanwijzers() if a.touchpad)
    muis = next(a for a in zien.aanwijzers() if not a.touchpad)
    klopt(tp.natuurlijk, "begin: het touchpad scrollt zoals een Mac (de standaard van KDE)")
    klopt(invoer.main(["standaard"]) == 0, "bugos-invoer standaard: gelukt")
    klopt(not tp.natuurlijk, "daarna: het touchpad scrollt zoals in Windows")
    klopt(not muis.natuurlijk, "de muis blijft zoals hij was")
    gezien = (Path(tmp) / "bugos" / "invoer-gezien").read_text(encoding="utf-8").splitlines()
    klopt(gezien == [tp.naam], f"het touchpad staat in invoer-gezien ({gezien})")
    # De gebruiker kiest daarna de Mac-manier: bij het volgende inloggen blijft dat zo.
    zien.zet_aanwijzer(tp.sysnaam, "natuurlijk", True)
    invoer.main(["standaard"])
    klopt(tp.natuurlijk, "eigen keuze (Mac-manier) blijft na opnieuw inloggen")
    klopt(invoer.main(["onzin"]) == 2, "onbekende opdracht: uitleg en code 2")

bureau = (ROOT / "system_files/etc/xdg/autostart/bugos-invoer.desktop").read_text(encoding="utf-8")
klopt("Exec=bugos-invoer standaard" in bureau, "start bij elk inloggen (autostart)")
zien_tekst = (PY / "bugos_settings_zien.py").read_text(encoding="utf-8")
klopt("Scrollen zoals op een Mac" in zien_tekst, "Instellingen: de schakelaar heet 'Scrollen zoals op een Mac'")

print(f"\n{fouten} fout(en)")
sys.exit(1 if fouten else 0)
