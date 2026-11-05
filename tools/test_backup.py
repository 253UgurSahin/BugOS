#!/usr/bin/env python3
"""Test van BugOS Back-up (zonder venster): ruimte, back-up maken en terugzetten, met nep-mappen.
Er verandert niets aan je computer: thuis en de USB-schijf zijn tijdelijke mappen.

Gebruik:  python3 tools/test_backup.py   (rsync moet er zijn)
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))
TMP = Path(tempfile.mkdtemp(prefix="bugos-backup-test-"))
THUIS, SCHIJF = TMP / "thuis", TMP / "stick"
THUIS.mkdir()
SCHIJF.mkdir()
os.environ.update(HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), LC_ALL="nl_NL.UTF-8",
                  PATH="/usr/bin:/bin")  # geen xdg-user-dir nodig: dan de standaardnamen

lader = importlib.machinery.SourceFileLoader("bugos_backup", str(ROOT / "system_files" / "usr" / "bin" / "bugos-backup"))
spec = importlib.util.spec_from_loader("bugos_backup", lader)
bb = importlib.util.module_from_spec(spec)
lader.exec_module(bb)
bb.gebruikersmap = lambda xdg, standaard: THUIS / standaard  # vaste plek, wat de computer ook zegt

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def schrijf(pad: Path, inhoud: bytes) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_bytes(inhoud)


# 1. ruimte: alleen wat nieuw of veranderd is, telt
schrijf(THUIS / "Documents" / "brief.txt", b"x" * 1000)
schrijf(THUIS / "Pictures" / "foto.jpg", b"y" * 5000)
mappen = bb.bron_mappen()
doel = bb.backup_doel(SCHIJF)
_, nodig, _ = bb.ruimte_genoeg(SCHIJF, mappen, doel)
klopt(nodig == 6000, "ruimte: eerste keer telt alles (6000 bytes)")
klopt(bb.zonder_venster(SCHIJF) == 0 and (doel / "Pictures" / "foto.jpg").read_bytes() == b"y" * 5000,
      "back-up: de foto staat op de schijf")
schrijf(THUIS / "Documents" / "nieuw.txt", b"z" * 300)
_, nodig, _ = bb.ruimte_genoeg(SCHIJF, mappen, doel)
klopt(nodig == 300, "ruimte: daarna alleen wat nieuw is (300 bytes), niet alles opnieuw")

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
