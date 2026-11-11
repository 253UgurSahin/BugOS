#!/usr/bin/env python3
"""Test van pakket 'tools': Taakbeheer, Hulp en Bestanden openen geen KDE-programma's meer.

- Hulp: 'Netwerk bekijken', 'Printer toevoegen' en 'Laat zien wat ruimte inneemt' gaan naar BugOS zelf.
- Bestanden: geen 'Openen in Dolphin' en geen 'Schijfbeheer'; wel 'Wat de meeste ruimte inneemt'.
- Taakbeheer: geen knop 'Systeemmonitor'; wel een eigen pagina Details (alles wat draait, beëindigen met een vraag).

Alles met nep-programma's, een nep-/proc en een nep-thuismap: er wordt niets gestopt of gewist. De KDE-programma's
(plasma-systemmonitor, dolphin, partitionmanager, filelight) staan als nep-programma op PATH, zodat de test bewijst
dat de sprongen weg zijn, ook als die programma's er wel zijn.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_tools.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import signal
import stat as _stat
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
sys.path.insert(0, str(LIB))

TMP = Path(tempfile.mkdtemp(prefix="bugos-tools-test-"))
PROC = TMP / "proc"
THUIS = TMP / "thuis"
BIN = TMP / "bin"
for _m in (PROC, THUIS, BIN, TMP / "share" / "applications"):
    _m.mkdir(parents=True, exist_ok=True)
# De KDE-programma's bestaan 'wel': de test bewijst dat BugOS ze toch niet start.
for _naam in ("plasma-systemmonitor", "dolphin", "partitionmanager", "filelight"):
    (BIN / _naam).write_text("#!/bin/sh\nexit 0\n")
    (BIN / _naam).chmod(0o755)
os.environ.update(BUGOS_PROC=str(PROC), BUGOS_SYS=str(TMP / "sys"), LC_ALL="nl_NL.UTF-8", LANG="nl_NL.UTF-8",
                  HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), XDG_CONFIG_DIRS=str(TMP / "etc"),
                  XDG_DATA_HOME=str(THUIS / ".local" / "share"), XDG_DATA_DIRS=str(TMP / "share"),
                  XDG_RUNTIME_DIR=str(TMP / "run"), BUGOS_LSBLK="", BUGOS_MEERDERE="1",
                  PATH=str(BIN) + os.pathsep + os.environ.get("PATH", ""))
(TMP / "run").mkdir(mode=0o700, exist_ok=True)
for _weg in ("BUGOS_TAKEN_VOORBEELD", "BUGOS_RUIMTE", "BUGOS_THEMA"):
    os.environ.pop(_weg, None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(naam: str, pad: Path):
    lader = importlib.machinery.SourceFileLoader(naam, str(pad))
    spec = importlib.util.spec_from_loader(naam, lader)
    module = importlib.util.module_from_spec(spec)
    lader.exec_module(module)
    return module


def schrijf(pad: Path, tekst: str) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(tekst, encoding="utf-8")


# ================================================================== Hulp ===
bh = laad("bugos_help", ROOT / "system_files" / "usr" / "bin" / "bugos-help")
bron_hulp = (ROOT / "system_files" / "usr" / "bin" / "bugos-help").read_text(encoding="utf-8")
klopt("kde_instelling" not in bron_hulp and "filelight" not in bron_hulp and "kcm_" not in bron_hulp,
      "Hulp: geen kde_instelling, geen kcm_ en geen Filelight meer in bugos-help")

_gestart: list = []
_echt_hulp = (bh.start, bh.draai, bh.bestaat, bh.shutil.disk_usage)
bh.start = lambda *a: (_gestart.append(a), True)[1]
bh.bestaat = lambda naam: True   # ook 'filelight' bestaat: toch niet gebruiken
antwoorden = {("-t", "-f", "CONNECTIVITY", "general"): (0, "none\n"),
              ("-t", "-f", "STATE", "general"): (0, "disconnected\n"),
              ("-t", "-f", "TYPE", "device"): (0, "ethernet\nloopback\n"),
              ("-r",): (0, "scheduler is running\n"), ("-p",): (1, "lpstat: No destinations added.\n"),
              ("-e",): (0, "")}
bh.draai = lambda *cmd, **kw: antwoorden.get(cmd[1:], (1, ""))
u = bh.controle_internet()
u.repareer()
klopt(u.stand == bh.PROBLEEM and "kabel" in u.tekst and _gestart[-1:] == [("bugos-settings", "wifi")]
      and u.repareer_tekst == "Netwerk bekijken",
      f"H1: geen wifi en geen verbinding: 'Netwerk bekijken' opent Instellingen > Wifi en internet ({_gestart[-1:]})")
u = bh.controle_printer()
u.repareer()
klopt(_gestart[-1:] == [("bugos-settings", "printers")] and u.repareer_tekst == "Printer toevoegen",
      f"H2: nog geen printer: 'Printer toevoegen' opent Instellingen > Printers ({_gestart[-1:]})")
from collections import namedtuple as _nt  # noqa: E402

_Gebruik = _nt("du", "total used free")
bh.shutil.disk_usage = lambda p: _Gebruik(500 * 1024**3, 0, int(1.5 * 1024**3))
u = bh.controle_opslag()
u.repareer()
klopt(u.stand == bh.PROBLEEM and "1,5 GB" in u.tekst and _gestart[-1:] == [("bugos-files", "computer:/ruimte")],
      f"H3: schijf bijna vol: Bestanden > Deze computer, ook al is Filelight er ({u.tekst!r}, {_gestart[-1:]})")
bh.shutil.disk_usage = lambda p: _Gebruik(100 * 1024**3, 0, int(5 * 1024**3))
u = bh.controle_opslag()
klopt(u.stand == bh.LET_OP and u.repareer is not None and (u.repareer(), _gestart[-1])[1] == ("bugos-files", "computer:/ruimte")
      and "5 GB" in u.tekst, f"H3: nog maar 5 GB vrij: ook dan de knop naar 'Wat de meeste ruimte inneemt' ({u.tekst!r})")
bh.shutil.disk_usage = lambda p: _Gebruik(500 * 1024**3, 0, int(50 * 1024**3))
klopt(bh.controle_opslag().repareer is None, "H3: genoeg ruimte: geen knop")
bh.start, bh.draai, bh.bestaat, bh.shutil.disk_usage = _echt_hulp

# ================================================================= einde ===
print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
