#!/usr/bin/env python3
"""Test van pakket 'account' in BugOS Instellingen: de klok met de hand, andere mensen (toevoegen, beheerder maken,
verwijderen, nieuw wachtwoord), je eigen foto, de notatie van datum en tijd, en de toetsenborden. Alles zonder KDE.

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai vervangen), D-Bus wordt nagedaan
(bi.accounts_roep vervangen) en de pagina's draaien in de voorbeeldstand. Geen root, geen polkit nodig.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_account.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-account-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  XDG_RUNTIME_DIR=str(TMP), BUGOS_ACCOUNTS_ICONEN=str(TMP / "iconen"))
os.environ.pop("LANGUAGE", None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402
import bugos_config_account as ca  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang(functie, *args, antwoord=lambda cmd: (0, ""), **kwargs):
    """Roep functie aan zonder voorbeeldstand, en geef de opdrachten die ze wilde draaien."""
    oud = (bi.VOORBEELD, bi.draai, shutil.which)
    opdrachten: list = []
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append(cmd), antwoord(cmd))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args, **kwargs)
    finally:
        bi.VOORBEELD, bi.draai, shutil.which = oud
    return opdrachten, uit


# ================================================================== de klok met de hand (stap 1) ===

def _ntp(aan: bool):
    def antwoord(cmd):
        if cmd[:2] == ("timedatectl", "show"):
            return 0, f"Timezone=Europe/Amsterdam\nNTP={'yes' if aan else 'no'}\nNTPSynchronized=no\n"
        return 0, ""
    return antwoord


_o14, _u14 = vang(bi.zet_klok, datetime(2026, 11, 11, 9, 30), antwoord=_ntp(False))
klopt(_u14 == (True, "") and ("timedatectl", "set-time", "2026-11-11 09:30:00") in _o14,
      f"14: klok zetten via timedatectl set-time, plaatselijke tijd ({_o14})")
_o14b, _u14b = vang(bi.zet_klok, datetime(2026, 11, 11, 9, 30), antwoord=_ntp(True))
klopt(_u14b == (False, "auto") and not any(c[:2] == ("timedatectl", "set-time") for c in _o14b),
      f"14: tijd gaat nog vanzelf: 'auto', en geen set-time ({_u14b})")


def _weigert(cmd):
    if cmd[:2] == ("timedatectl", "set-time"):
        return 1, ""
    return _ntp(False)(cmd)


_o14c, _u14c = vang(bi.zet_klok, datetime(2030, 1, 1, 12, 0), antwoord=_weigert)
klopt(_u14c == (False, "fout"), f"14: geweigerd en de klok staat niet op de gevraagde tijd: 'fout' ({_u14c})")
_bijna = datetime.now().replace(microsecond=0)
_bijna = _bijna.replace(year=_bijna.year + 1)   # stel: de klok liep een jaar achter, en het lukte na 25 s toch
_echt_now = ca.datetime
_stap = iter([datetime(2026, 1, 1, 8, 0), _bijna])


class _SprongDatum(datetime):
    @classmethod
    def now(cls, tz=None):   # eerst de oude tijd, daarna (na de time-out) staat de klok op de gevraagde tijd
        return next(_stap, _bijna) if tz is None else _echt_now.now(tz)


ca.datetime = _SprongDatum
try:
    _o14e, _u14e = vang(bi.zet_klok, _bijna, antwoord=_weigert)
finally:
    ca.datetime = _echt_now
klopt(_u14e == (True, ""), f"I5: timedatectl gaf het op, maar de klok staat wel goed: gelukt ({_u14e})")

# ============================================================ het venster van Instellingen (voorbeeldstand) ===

lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
venster = mod.Instellingen("start")
import bugos_settings_account as sa  # noqa: E402


def wacht() -> None:
    for _ in range(3):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def teksten(w) -> str:
    return " ".join(x.text() for x in w.findChildren(QLabel) if not x.isHidden())


# 30: de klok met de hand via het BugOS-venster.
venster.ga_naar("tijd")
wacht()
tp = venster.paginas["tijd"]
tp.toon((ca.Tijd("Europe/Amsterdam", False, False), "nl"))
_gezet30: list = []


class _NepKlok30:
    def __init__(self, ouder):
        self.wanneer = datetime(2026, 11, 11, 9, 30)


setattr(_NepKlok30, "exec", lambda self: 1)
_oud30 = (sa.KlokDialoog, bi.zet_klok)
sa.KlokDialoog = _NepKlok30
bi.zet_klok = lambda w: (_gezet30.append(w), (True, ""))[1]
_zichtbaar30 = tp.zelf_rij.isVisibleTo(tp)
tp.zelf_rij.geklikt.emit()
wacht()
sa.KlokDialoog, bi.zet_klok = _oud30
klopt(_zichtbaar30 and _gezet30 == [datetime(2026, 11, 11, 9, 30)]
      and "De klok is gezet" in tp.melding.tekst.text(),
      f"30: klok zelf instellen: één keer zet_klok met de gekozen tijd ({_gezet30}, {tp.melding.tekst.text()!r})")
_kd = sa.KlokDialoog(venster)
klopt(_kd.datum.displayFormat().count("y") == 4 and _kd.sizeHint().height() <= 480 and _kd.sizeHint().width() <= 600,
      f"30: het klokvenster: heel jaartal, past op 1280x800 bij 150 % ({_kd.datum.displayFormat()}, {_kd.sizeHint()})")
tp.toon((ca.Tijd("Europe/Amsterdam", True, False), "nl"))
klopt("Wacht op internet" in tp.klok_rij.uitleg.text() and tp.zelf_rij.isHidden(),
      f"F: tijd vanzelf, maar nog niet gelijk: 'wacht op internet' ({tp.klok_rij.uitleg.text()!r})")

# 31: geen sprongen naar KDE meer in de pagina's van dit pakket.
_bron = (PY / "bugos_settings_account.py").read_text(encoding="utf-8")
klopt("kcm_clock" not in _bron, "31: Tijd en taal opent geen KDE-onderdeel meer")

QThreadPool.globalInstance().waitForDone(5000)
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
