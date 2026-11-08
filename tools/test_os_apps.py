#!/usr/bin/env python3
"""Test van de fixes in de BugOS-apps (Bestanden, Back-up, Overstap, Winkel, Welkom, schermlezers, vertalen).

Alles gebeurt in een tijdelijke map met een nep-thuismap; je echte bestanden worden niet aangeraakt.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_os_apps.py
"""

from __future__ import annotations

import errno
import importlib.machinery
import importlib.util
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-os-apps-test-"))
THUIS = TMP / "thuis"
os.environ["HOME"] = str(THUIS)
os.environ["XDG_DATA_HOME"] = str(THUIS / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(THUIS / ".config")
os.environ["BUGOS_LSBLK"] = ""  # geen echte schijven in de test
os.environ["LC_ALL"] = "nl_NL.UTF-8"  # de test kijkt naar de Nederlandse teksten
os.environ.pop("LANGUAGE", None)
(THUIS / ".config").mkdir(parents=True)


def laad(naam: str, programma: str):
    lader = importlib.machinery.SourceFileLoader(naam, str(ROOT / "system_files" / "usr" / "bin" / programma))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m  # nodig voor @dataclass
    lader.exec_module(m)
    return m


b = laad("bestanden", "bugos-files")
import bugos_files_acties as acties  # noqa: E402
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def stick_map(naam: str) -> Path:
    p = TMP / naam
    p.mkdir()
    return p


# ============================================ U003: een stick die niet alles kan bewaren ===
# Wat FAT/exFAT doen: een naam met ':' geeft EINVAL, en chmod naar rechten die hij niet kent geeft EPERM.
_echt_copyfile, _echt_chmod, _echt_rename = shutil.copyfile, os.chmod, os.rename
STICK = stick_map("stick")


def nep_stick(aan: bool) -> None:
    def copyfile(s, d, *a, **k):
        if str(d).startswith(str(STICK)) and ":" in os.path.basename(d):
            raise OSError(errno.EINVAL, "Invalid argument", str(d))
        return _echt_copyfile(s, d, *a, **k)

    def chmod(p, mode, *a, **k):
        if str(p).startswith(str(STICK)) and stat.S_IMODE(mode) & 0o044 != 0o044:
            raise PermissionError(errno.EPERM, "Operation not permitted", str(p))
        return _echt_chmod(p, mode, *a, **k)

    shutil.copyfile = copyfile if aan else _echt_copyfile
    os.chmod = chmod if aan else _echt_chmod


def eerste_rename_andere_schijf() -> None:
    """Het verplaatsen zelf zegt 'andere schijf' (EXDEV); daarna werkt rename gewoon."""
    keer = []

    def rename(a, c):
        if not keer:
            keer.append(1)
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return _echt_rename(a, c)

    os.rename = rename


vakantie = THUIS / "Vakantie"
vakantie.mkdir(parents=True)
for i in range(3):
    (vakantie / f"foto{i}.jpg").write_text(f"foto {i}")
(vakantie / "Meeting 10:30.docx").write_text("x")
nep_stick(True)
achter: list = []
try:
    kopie = b.kopieer_een(vakantie, STICK, verplaats=False, achter=achter)
    fout = ""
except Exception as e:  # noqa: BLE001
    kopie, fout = None, f"{type(e).__name__}: {e}"
klopt(kopie == STICK / "Vakantie" and sorted(p.name for p in kopie.iterdir()) == ["foto0.jpg", "foto1.jpg", "foto2.jpg"],
      f"U003: map met één naam die de stick niet kent: de rest komt er wel op {fout}")
klopt([naam for _p, naam, _r in achter] == ["Vakantie/Meeting 10:30.docx"],
      "U003: het bestand dat niet mee kon, staat in het lijstje (met de map ervoor)")
uitleg = acties.achter_uitleg(achter, False)
klopt("Meeting 10:30.docx" in uitleg and "De rest staat er wel" in uitleg and "Errno" not in uitleg
      and "[(" not in uitleg, f"U003: de melding is gewone taal: {uitleg!r}")
klopt(not any(p.name.endswith(".bugos-bezig") for p in STICK.iterdir()), "U003: geen tijdelijke map achtergebleven")

# rechten die een stick niet kan bewaren (een 0600-bestand, een 0700-map): de inhoud gaat gewoon mee
geheim = THUIS / "Geheim"
geheim.mkdir()
(geheim / "rekening.pdf").write_text("geld")
os.chmod(geheim / "rekening.pdf", 0o600)
os.chmod(geheim, 0o700)
try:
    los = b.kopieer_een(geheim / "rekening.pdf", STICK, verplaats=False)
    hele = b.kopieer_een(geheim, STICK, verplaats=False)
    fout = ""
except Exception as e:  # noqa: BLE001
    los = hele = None
    fout = f"{type(e).__name__}: {e}"
klopt(los is not None and los.read_text() == "geld" and hele is not None and (hele / "rekening.pdf").read_text() == "geld",
      f"U003: een 0600-bestand en een 0700-map gaan mee, ook al kan de stick de rechten niet bewaren {fout}")

# verplaatsen naar de stick: wat niet mee kon, blijft op de oude plek; de rest is verhuisd
verhuis = THUIS / "Verhuis"
(verhuis / "binnen").mkdir(parents=True)
(verhuis / "a.txt").write_text("a")
(verhuis / "binnen" / "b.txt").write_text("b")
(verhuis / "binnen" / "kwart?.txt").write_text("?")
(verhuis / "binnen" / "c:d.txt").write_text("c")
achter = []
eerste_rename_andere_schijf()
try:
    weg = b.kopieer_een(verhuis, STICK, verplaats=True, achter=achter)
except Exception as e:  # noqa: BLE001
    weg = None
    print("   ", type(e).__name__, e)
os.rename = _echt_rename
klopt(weg is not None and (weg / "a.txt").exists() and (weg / "binnen" / "b.txt").exists()
      and not (weg / "binnen" / "c:d.txt").exists(),
      "U003: verplaatsen met één naam die niet mag: de rest staat op de stick")
klopt((verhuis / "binnen" / "c:d.txt").read_text() == "c" and not (verhuis / "a.txt").exists()
      and not (verhuis / "binnen" / "b.txt").exists() and (verhuis / "binnen" / "kwart?.txt").exists() is False,
      "U003: verplaatsen: wat niet mee kon, staat nog op de oude plek; de rest is daar weg")
klopt("oude plek" in acties.achter_uitleg(achter, True),
      "U003: verplaatsen: de melding zegt dat het nog op de oude plek staat")
nep_stick(False)

# een echte fout (schijf vol) halverwege: nog steeds geen halve map (de belofte van A011)
vol = THUIS / "Vol"
vol.mkdir()
for i in range(3):
    (vol / f"f{i}.txt").write_text("x")


def schijf_vol(s, d, *a, **k):
    if os.path.basename(d) == "f1.txt":
        raise OSError(errno.ENOSPC, "No space left on device", str(d))
    return _echt_copyfile(s, d, *a, **k)


shutil.copyfile = schijf_vol
voor = sorted(p.name for p in STICK.iterdir())
try:
    b.kopieer_een(vol, STICK, verplaats=False)
    melding = None
except OSError as e:
    melding = e.strerror or str(e)
shutil.copyfile = _echt_copyfile
klopt(melding is not None and sorted(p.name for p in STICK.iterdir()) == voor,
      "U003: schijf vol halverwege: niets achtergebleven op de stick, en een fout")
klopt(melding is not None and "Errno" not in melding and "[(" not in melding and "vol" in melding,
      f"U003: schijf vol: de fout is gewone taal: {melding!r}")

# de klus op de achtergrond geeft het lijstje door aan het venster
nep_stick(True)
klus = b.Klus([vakantie], STICK, False)
uitslag: list = []
klus.klaar.connect(lambda g, f: uitslag.append((g, f)))
klus.run()  # gewoon hier, zonder draad: dan is het meteen klaar
nep_stick(False)
klopt(uitslag == [(1, "")] and [n for _p, n, _r in getattr(klus, "achter", [])] == ["Vakantie/Meeting 10:30.docx"],
      "U003: de klus telt de map als gelukt en onthoudt wat achterbleef")

# ============================= U004: verplaatsen naar een stick: eerst echt wegschrijven, dan pas weg ===
_echt_schrijf_weg = acties.schrijf_weg
gezien: list = []


def kijk_schrijf_weg(pad):
    gezien.append((Path(pad), (THUIS / "Naar stick" / "a.txt").exists()))
    return _echt_schrijf_weg(pad)


acties.schrijf_weg = kijk_schrijf_weg
(THUIS / "Naar stick").mkdir()
(THUIS / "Naar stick" / "a.txt").write_text("a")
klus = b.Klus([THUIS / "Naar stick"], STICK, True)
seinen: list = []
klus.wegschrijven.connect(lambda: seinen.append("wegschrijven"))
klus.klaar.connect(lambda g, f: seinen.append(("klaar", g, f)))
eerste_rename_andere_schijf()
klus.run()
os.rename = _echt_rename
acties.schrijf_weg = _echt_schrijf_weg
klopt(gezien == [(STICK / "Naar stick", True)] and not (THUIS / "Naar stick").exists()
      and (STICK / "Naar stick" / "a.txt").read_text() == "a",
      "U004: verplaatsen naar een andere schijf: eerst wegschrijven (origineel staat er dan nog), daarna pas weg")
klopt(seinen == ["wegschrijven", ("klaar", 1, "")], "U004: het venster hoort 'bezig met wegschrijven' vóór 'klaar'")
_echt_schrijf_weg(STICK)  # het echte wegschrijven werkt ook (syncfs)
klopt(True, "U004: echt wegschrijven naar een map geeft geen fout")


def stuk_schrijf_weg(pad):
    raise acties.KopieFout(errno.EIO, acties.leesbare_fout(errno.EIO, Path(pad).name))


acties.schrijf_weg = stuk_schrijf_weg
(THUIS / "Blijft").mkdir()
(THUIS / "Blijft" / "b.txt").write_text("b")
eerste_rename_andere_schijf()
try:
    b.kopieer_een(THUIS / "Blijft", STICK, verplaats=True)
    gemeld = False
except OSError:
    gemeld = True
os.rename = _echt_rename
acties.schrijf_weg = _echt_schrijf_weg
klopt(gemeld and (THUIS / "Blijft" / "b.txt").read_text() == "b",
      "U004: lukt het wegschrijven niet (stick eruit), dan blijft het origineel staan")

# ================================================= de vensters van Back-up en Overstap, met nep-programma's ===
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or b.maak_app("bugos-test", "bugos-test", ["test"])
bugos_ui.maak_app = lambda *a, **k: app  # elk venster deelt deze ene app
_gevangen: list = []
bugos_ui.uitvoeren = lambda _app, w: _gevangen.append(w) or 0  # niet wachten: geef het venster terug

NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "opdrachten.log"


def nep_programma(naam: str, inhoud: str) -> None:
    (NEP / naam).write_text("#!/usr/bin/bash\n" + inhoud)
    (NEP / naam).chmod(0o755)


nep_programma("sync", f'echo "sync $*" >> "{LOG}"\nexit 0\n')
nep_programma("xdg-user-dir", "exit 1\n")
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"


def wacht(voorwaarde, ms: int = 10000) -> bool:
    klok = QElapsedTimer()
    klok.start()
    while not voorwaarde() and klok.elapsed() < ms:
        app.processEvents()
    return voorwaarde()


def open_venster(module):
    _gevangen.clear()
    module.venster()
    w = _gevangen[-1]
    w.show()
    return w


bb = laad("bugos_backup", "bugos-backup")
SCHIJF = stick_map("backup-schijf")
os.environ["BUGOS_SCHIJVEN"] = str(SCHIJF)
(THUIS / "Documents").mkdir()
(THUIS / "Documents" / "brief.txt").write_text("hallo")

# ===================================================== U012: Back-up zegt pas 'eruit halen' na het wegschrijven ===
LOG.write_text("")
klopt(bb.zonder_venster(SCHIJF) == 0 and f"sync -f {bb.backup_doel(SCHIJF)}" in LOG.read_text(),
      "U012: back-up zonder venster schrijft alles echt weg (sync -f) voor hij klaar zegt")
LOG.write_text("")
w = open_venster(bb)
w.maak_backup()
wacht(lambda: "uithalen" in w.melding.tekst.text() or "lukte" in w.melding.tekst.text())
klopt("sync -f" in LOG.read_text() and "uithalen" in w.melding.tekst.text(),
      "U012: venster: eerst wegschrijven, dan pas 'Je mag hem er nu uithalen'")
klopt(bb.wegschrijven(SCHIJF) == ["sync", "-f", str(SCHIJF)],
      "U012: de laatste stap is sync -f op de schijf zelf (niet de hele computer)")
w.close()

# ======================================== U015: Back-up of Overstap sluiten terwijl hij bezig is ===
# Een nep-rsync die even wacht (zo zien we het venster 'bezig'), daarna doet hij het echt.
nep_programma("rsync", 'if [ -n "$BUGOS_TEST_VAST" ]; then exec /usr/bin/sleep 60; fi\n'
                       '/usr/bin/sleep "${BUGOS_TEST_SLAAP:-0}"\nexec /usr/bin/rsync "$@"\n')
bo = laad("bugos_overstap", "bugos-switch")
WIN = stick_map("windows-stick")
(WIN / "BugOS-Switch" / "Documents").mkdir(parents=True)
(WIN / "BugOS-Switch" / "bugos-switch.json").write_text('{"computer": "PC"}')
(WIN / "BugOS-Switch" / "Documents" / "cv.txt").write_text("cv")


def draait(w) -> bool:
    return w.proces.state() != w.proces.ProcessState.NotRunning


for naam, module, schijf, begin in (("Back-up", bb, SCHIJF, "maak_backup"), ("Overstap", bo, WIN, "begin")):
    os.environ["BUGOS_SCHIJVEN"] = str(schijf)
    # 1. 'Eerst afmaken': het venster blijft open en gaat vanzelf dicht als het klaar is
    os.environ["BUGOS_TEST_SLAAP"] = "1"
    w = open_venster(module)
    gevraagd: list = []
    w.vraag_stoppen = lambda g=gevraagd: g.append(1) or False
    getattr(w, begin)()
    wacht(lambda: draait(w), 5000)
    w.close()
    klopt(gevraagd == [1] and w.isVisible() and draait(w),
          f"U015: {naam}: sluiten tijdens het kopiëren vraagt het eerst, en stopt niet stilletjes")
    klopt(wacht(lambda: not w.isVisible(), 15000), f"U015: {naam}: 'Eerst afmaken': daarna gaat het venster vanzelf dicht")
    # 2. 'Nu stoppen': het proces stopt netjes en het venster gaat dicht
    os.environ["BUGOS_TEST_VAST"] = "1"
    w = open_venster(module)
    w.vraag_stoppen = lambda: True
    getattr(w, begin)()
    wacht(lambda: draait(w), 5000)
    w.close()
    klopt(wacht(lambda: not w.isVisible() and not draait(w), 8000),
          f"U015: {naam}: 'Nu stoppen': het kopiëren stopt en het venster gaat dicht")
    del os.environ["BUGOS_TEST_VAST"], os.environ["BUGOS_TEST_SLAAP"]
os.environ["BUGOS_SCHIJVEN"] = str(SCHIJF)

print()
shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
