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
import warnings
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


# U040: een map MET submappen naar een stick die de rechten van mappen weigert: de rest komt er toch op.
nep_stick(True)
_bron = TMP / "thuis-u040" / "Fotos"
(_bron / "Vakantie").mkdir(parents=True)
(_bron / "a.jpg").write_text("a")
(_bron / "Vakantie" / "b.jpg").write_text("b")
os.chmod(_bron / "Vakantie", 0o700)   # rechten die de stick niet kan bewaren
_achter: list = []
try:
    _uit = acties.kopieer_een(_bron, STICK, False, _achter)
except OSError as e:
    _uit = f"mislukt: {e}"
nep_stick(False)
klopt(isinstance(_uit, Path) and (_uit / "Vakantie" / "b.jpg").read_text() == "b",
      f"U040: een map met submappen komt op een stick die mapsrechten weigert ({_uit})")


# U037: naar een stick zonder hoofdletters (FAT/exFAT): 'IMG_1.JPG' en 'img_1.jpg' overschrijven elkaar niet,
# de tweede blijft staan en wordt genoemd; bij verplaatsen blijft hij op de oude plek.
klopt(acties.kent_hoofdletters(TMP), "U037: een gewone Linux-map kent hoofdletters (dan verandert er niets)")
_echt_kent = acties.kent_hoofdletters
acties.kent_hoofdletters = lambda map_: False   # doe alsof STICK een FAT-stick is
for _verplaats in (False, True):
    _b = TMP / f"thuis-u037-{_verplaats}" / "Camera"
    (_b / "Sub").mkdir(parents=True)
    (_b / "IMG_1.JPG").write_text("groot")
    (_b / "img_1.jpg").write_text("klein")
    (_b / "Sub" / "a.txt").write_text("a")
    _achter: list = []
    if _verplaats:  # een stick is een andere schijf: rename lukt daar niet (EXDEV)
        _keer: list = []
        os.rename = lambda a, c, k=_keer: (k.append(1), (_ for _ in ()).throw(OSError(errno.EXDEV, "cross-device")))[1] \
            if not k else _echt_rename(a, c)
    _doel = acties.kopieer_een(_b, STICK, _verplaats, _achter)
    os.rename = _echt_rename
    _op_stick = sorted(p.name for p in _doel.iterdir())
    klopt(_op_stick == ["IMG_1.JPG", "Sub"] and (_doel / "IMG_1.JPG").read_text() == "groot"
          and [n for _p, n, _r in _achter] == ["Camera/img_1.jpg"] and "hoofdletters" in _achter[0][2].lower()
          + "capitals",
          f"U037: {'verplaatsen' if _verplaats else 'kopiëren'}: één van de twee mee, de andere genoemd ({_op_stick}, {_achter})")
    if _verplaats:
        klopt((_b / "img_1.jpg").read_text() == "klein" and not (_b / "IMG_1.JPG").exists(),
              "U037: verplaatsen: wat niet mee kon, staat nog op de oude plek; de rest is weg")
    shutil.rmtree(_doel)
acties.kent_hoofdletters = _echt_kent


# U048: een back-up naar een schijf zonder hoofdletters: 'img_1.jpg' naast 'IMG_1.JPG' wordt niet overschreven,
# maar overgeslagen en genoemd (geen "veilig" terwijl er één ontbreekt).
_bb48 = laad("bugos_backup_u048", "bugos-backup")
_thuis48 = TMP / "thuis-u048"
(_thuis48 / "Pictures" / "Vakantie").mkdir(parents=True)
(_thuis48 / "Pictures" / "IMG_1.JPG").write_text("groot")
(_thuis48 / "Pictures" / "img_1.jpg").write_text("klein")
(_thuis48 / "Pictures" / "Vakantie" / "a[1]*.jpg").write_text("a")
(_thuis48 / "Pictures" / "Vakantie" / "A[1]*.JPG").write_text("A")
klopt(_bb48.dubbel_op_schijf(TMP, [_thuis48 / "Pictures"]) == {}, "U048: een schijf die hoofdletters kent: niets overslaan")
_bb48.kent_hoofdletters = lambda p: False
_d48 = _bb48.dubbel_op_schijf(TMP, [_thuis48 / "Pictures"])
_doel48 = TMP / "stick-u048" / "BugOS-Backup" / "x"
_doel48.mkdir(parents=True)
_cmd = _bb48.rsync_maak(_thuis48 / "Pictures", _doel48, _d48[_thuis48 / "Pictures"])
import subprocess as _sp  # noqa: E402
_sp.run(_cmd, capture_output=True, check=False)
_op48 = sorted(str(p.relative_to(_doel48 / "Pictures")) for p in (_doel48 / "Pictures").rglob("*"))
klopt(sorted(_d48[_thuis48 / "Pictures"]) == ["Vakantie/a[1]*.jpg", "img_1.jpg"]
      and _op48 == ["IMG_1.JPG", "Vakantie", "Vakantie/A[1]*.JPG"],
      f"U048: de tweede van elk paar gaat niet mee (ook met * en [ in de naam): {_op48}")
# U051: stond 'img_1.jpg' al in de back-up en komt 'IMG_1.JPG' er later bij, dan blijft de oude in de back-up staan.
(_doel48.parent / "y" / "Pictures").mkdir(parents=True)
(_doel48.parent / "y" / "Pictures" / "img_1.jpg").write_text("klein")
_d51 = _bb48.dubbel_op_schijf(TMP, [_thuis48 / "Pictures"], _doel48.parent / "y")
klopt("IMG_1.JPG" in _d51[_thuis48 / "Pictures"] and "img_1.jpg" not in _d51[_thuis48 / "Pictures"],
      f"U051: wat al in de back-up staat, blijft; de nieuwe met andere hoofdletters gaat niet mee ({_d51})")
# U053: ook als de map eromheen een naamgenoot krijgt: wat in de back-up staat, blijft.
_t53 = TMP / "thuis-u053" / "Pictures"
(_t53 / "photos").mkdir(parents=True)
(_t53 / "photos" / "IMG_1.JPG").write_text("groot")
(_t53 / "photos" / "img_1.jpg").write_text("klein")
_b53 = TMP / "backup-u053"
(_b53 / "Pictures" / "photos").mkdir(parents=True)
(_b53 / "Pictures" / "photos" / "IMG_1.JPG").write_text("groot")   # zo staat het er na de eerste back-up
(_t53 / "Photos").mkdir()
(_t53 / "Photos" / "nieuw.jpg").write_text("n")
_d53 = _bb48.dubbel_op_schijf(TMP, [_t53], _b53)[_t53]
klopt("Photos" in _d53 and "photos/img_1.jpg" in _d53,
      f"U053: map 'photos' blijft (staat in de back-up), en daarbinnen gaat de naamgenoot nog steeds niet mee ({_d53})")
klopt("hoofdletters" in _bb48.DEELS_UITLEG or "capitals" in _bb48.DEELS_UITLEG,
      "U048: de melding 'konden niet mee' noemt ook namen die alleen in hoofdletters verschillen")


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
                       'if [ -n "$BUGOS_TEST_FOUT" ]; then /usr/bin/sleep 1; exit 11; fi\n'
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
    # 3. U038: 'Eerst afmaken', maar het mislukt (stick eruit): de foutmelding blijft staan, het venster blijft open
    os.environ["BUGOS_TEST_FOUT"] = "1"
    w = open_venster(module)
    w.vraag_stoppen = lambda: False
    getattr(w, begin)()
    wacht(lambda: draait(w), 5000)
    w.close()
    wacht(lambda: not draait(w), 15000)
    for _ in range(20):
        app.processEvents()
    klopt(w.isVisible() and "lukte niet" in w.melding.tekst.text(),
          f"U038: {naam}: mislukt het na 'Eerst afmaken', dan blijft het venster open met de foutmelding")
    w.close()
    del os.environ["BUGOS_TEST_FOUT"]
os.environ["BUGOS_SCHIJVEN"] = str(SCHIJF)

# ========================================== U014: ruimte tellen op de achtergrond (het venster loopt niet vast) ===
import threading  # noqa: E402
import time  # noqa: E402

_echt_ruimte = bb.ruimte_genoeg
telde_in: list = []


def traag_tellen(*a, **k):
    telde_in.append(threading.current_thread() is threading.main_thread())
    time.sleep(1.5)  # duizenden foto's
    return _echt_ruimte(*a, **k)


bb.ruimte_genoeg = traag_tellen
w = open_venster(bb)
klok = time.monotonic()
w.maak_backup()
duur = time.monotonic() - klok
klopt(duur < 0.5 and not w.maak.isEnabled() and "past" in w.melding.tekst.text(),
      f"U014: 'Maak back-up' komt meteen terug ({duur:.1f} s) en zegt 'Even kijken of alles past'")
klopt(wacht(lambda: "uithalen" in w.melding.tekst.text(), 15000) and telde_in == [False],
      "U014: het tellen gebeurde op de achtergrond, daarna gaat de back-up gewoon door")
w.close()
# sluiten tijdens het tellen: geen crash, het venster gaat netjes dicht
w = open_venster(bb)
w.maak_backup()
w.close()
klopt(wacht(lambda: not w.isVisible() and not w.druk(), 8000), "U014: sluiten tijdens het tellen: stopt netjes")
bb.ruimte_genoeg = lambda *a, **k: (False, 5 * 1024**3, 1024**3)
w = open_venster(bb)
w.maak_backup()
klopt(wacht(lambda: "Te weinig ruimte" in w.melding.tekst.text()) and wacht(lambda: w.maak.isEnabled()),
      "U014: past het niet, dan zegt hij dat en kun je het opnieuw proberen")
w.close()
bb.ruimte_genoeg = _echt_ruimte

# ============================== U013: de Winkel ziet Firefox en Steam die al in BugOS zitten (geen Flatpak) ===
os.environ.pop("BUGOS_GEINSTALLEERD", None)
winkel = laad("bugos_winkel", "bugos-store")
APPS = TMP / "applications"
APPS.mkdir()
(APPS / "org.mozilla.firefox.desktop").write_text("[Desktop Entry]\nName=Firefox\nExec=firefox\n")
(APPS / "steam.desktop").write_text("[Desktop Entry]\nName=Steam\nExec=steam\n")
winkel.APP_MAPPEN = [APPS]
gestart: list = []
winkel.start = lambda *a: gestart.append(a)
cat = winkel.lees_catalogus(ROOT / "system_files" / "usr" / "share" / "bugos" / "store.json")
ww = winkel.Winkel(cat)
for zoek, app_id in (("Firefox", "org.mozilla.firefox"), ("Steam", "com.valvesoftware.Steam")):
    ww.zoek.setText(zoek)
    kaart = next((k for k in ww.kaarten if k.app["id"] == app_id), None)
    klopt(kaart is not None and kaart.knop.text() == "Openen" and not kaart.chip.isHidden(),
          f"U013: {zoek} (systeemprogramma) heet 'Geïnstalleerd' met 'Openen', niet 'Installeren'")
    gestart.clear()
    if kaart:
        kaart.klik()
    klopt(len(gestart) == 1 and gestart[0][0] in ("kioclient", "gio") and gestart[0][-1].endswith(".desktop"),
          f"U013: {zoek} openen start het eigen programma (niet 'flatpak run'): {gestart}")
ww.zoek.setText("VLC")
kaart = next((k for k in ww.kaarten if k.app["id"] == "org.videolan.VLC"), None)
klopt(kaart is not None and kaart.knop.text() == "Installeren", "U013: een app die er echt niet is: 'Installeren'")
# U052: de Winkel sluiten tijdens het installeren: niet afbreken, wachten en daarna vanzelf dicht;
# mislukt het, dan blijft de Winkel open met de melding.
nep_programma("flatpak", 'if [ "$1" = install ]; then echo "$*" >"$BUGOS_TEST_FLATPAK_ARGS"; /usr/bin/sleep 1; '
                          '[ "${BUGOS_TEST_FLATPAK:-0}" = 9 ] && echo "error: Not authorized" && exit 1; '
                          'exit "${BUGOS_TEST_FLATPAK:-0}"; fi\nexit 0\n')
os.environ["BUGOS_TEST_FLATPAK_ARGS"] = str(TMP / "flatpak-args")
vlc = next(a for a in cat["apps"] if a["id"] == "org.videolan.VLC")
for _code, _verwacht in (("0", "dicht"), ("1", "open")):
    os.environ["BUGOS_TEST_FLATPAK"] = _code
    ww.show()
    ww.installeer(vlc)
    wacht(lambda: ww.proces.state() != ww.proces.ProcessState.NotRunning, 3000)
    ww.close()
    _bleef = ww.isVisible() and ww.proces.state() != ww.proces.ProcessState.NotRunning
    wacht(lambda: ww.proces.state() == ww.proces.ProcessState.NotRunning, 8000)
    for _ in range(20):
        app.processEvents()
    if _verwacht == "dicht":
        klopt(_bleef and not ww.isVisible(), "U052: Winkel sluiten tijdens installeren: wacht tot het klaar is, dan dicht")
    else:
        klopt(_bleef and ww.isVisible() and "lukte niet" in ww.melding.tekst.text(),
              "U052: ... en mislukt het installeren, dan blijft de Winkel open met de melding")
# U059: zonder --noninteractive (dan kan KDE om een beheerderswachtwoord vragen), en "geen toestemming" zegt dat.
klopt("--noninteractive" not in (TMP / "flatpak-args").read_text() and "install" in (TMP / "flatpak-args").read_text(),
      "U059: de Winkel installeert zonder --noninteractive, zodat om een wachtwoord gevraagd kan worden")
os.environ["BUGOS_TEST_FLATPAK"] = "9"
ww.show()
ww.installeer(vlc)
wacht(lambda: ww.proces.state() == ww.proces.ProcessState.NotRunning and ww.bezig_met is None, 8000)
klopt("beheerder" in ww.melding.tekst.text(), f"U059: geen toestemming: de Winkel zegt dat een beheerder nodig is ({ww.melding.tekst.text()[:60]})")
del os.environ["BUGOS_TEST_FLATPAK"]
ww.close()

# ================================== U016: een schermlezer hoort een naam bij schuifjes, regels en keuzekaarten ===
from PySide6.QtGui import QAccessible  # noqa: E402


def lezer(w) -> tuple[str, str, str]:
    i = QAccessible.queryAccessibleInterface(w)
    return (i.role().name, i.text(QAccessible.Text.Name), i.text(QAccessible.Text.Description)) if i else ("", "", "")


kiezer = bugos_ui.SchijfKiezer("Steek een USB-schijf in…")
kiezer.zet([("/run/media/u/STICK", "STICK", "29 GB vrij van 29 GB")])
klopt(lezer(next(iter(kiezer.kaarten.values())))[1:] == ("STICK", "29 GB vrij van 29 GB"),
      f"U016: de schijfkaart in Back-up/Overstap heeft de naam van de stick: {lezer(next(iter(kiezer.kaarten.values())))}")

welkom = laad("bugos_welkom", "bugos-welcome")
for pagina in (welkom.Uiterlijk(), welkom.Updates()):
    kaarten = pagina.findChildren(bugos_ui.KeuzeKaart)
    namen = [lezer(k)[1] for k in kaarten]
    klopt(kaarten and all(namen), f"U016: Welkom ({type(pagina).__name__}): elke keuze heeft een naam: {namen}")

os.environ["BUGOS_INSTELLINGEN_VOORBEELD"] = "1"
inst = laad("bugos_instellingen", "bugos-settings")
from bugos_shell import Rij  # noqa: E402
from bugos_widgets import Schuif  # noqa: E402

vi = inst.Instellingen("wifi")
vi.show()
for sleutel in list(vi.paginas):  # elke pagina een keer laten zien (zoals iemand die rondklikt)
    vi.ga_naar(sleutel)
    for _ in range(10):
        app.processEvents()
schuiven = vi.findChildren(Schuif)
zonder = [s for s in schuiven if not lezer(s)[1]]
klopt(schuiven and not zonder, f"U016: Instellingen: elk schuifje heeft een naam ({len(zonder)} van {len(schuiven)} zonder)")
rijen = [r for r in vi.findChildren(Rij) if r.property("klikbaar") == "true"]
slecht = [r.titel.text() for r in rijen if lezer(r)[0] != "Button" or lezer(r)[1] != r.titel.text()]
klopt(rijen and not slecht, f"U016: Instellingen: elke klikbare regel is een knop met de titel als naam (mis: {slecht[:3]})")
r = rijen[0]
r.titel.setText("Nieuwe titel")
klopt(lezer(r)[1] == "Nieuwe titel", "U016: verandert de titel van een regel, dan hoort de schermlezer de nieuwe")
# U039: een knop met tekst in een regel ("Nu vergrendelen") houdt zijn eigen tekst als naam, niet de titel van de regel.
from PySide6.QtWidgets import QAbstractButton  # noqa: E402
knoppen = [k for k in vi.findChildren(QAbstractButton) if not isinstance(k, Schuif) and k.text().strip()
           and isinstance(k.parent(), Rij)]
verkeerd = [(k.text(), lezer(k)[1]) for k in knoppen if lezer(k)[1] not in ("", k.text())]
klopt(knoppen and not verkeerd, f"U039: knoppen met tekst in een regel heten zoals hun tekst ({len(knoppen)} knoppen, mis: {verkeerd[:3]})")
vi.close()
del os.environ["BUGOS_INSTELLINGEN_VOORBEELD"]

# ===================================== U029: Foto.JPG -> Foto.jpg op een stick (FAT/exFAT kent geen hoofdletters) ===
from bugos_files_bewerken import Bewerken  # noqa: E402


class NepMelding:
    def __init__(self):
        self.teksten: list[str] = []

    def toon(self, tekst, *a, **k):
        self.teksten.append(tekst)


class NepVenster(Bewerken):
    """Alleen wat 'Naam wijzigen' nodig heeft."""

    def __init__(self, gekozen: Path, nieuw: str):
        self.in_prullenbak, self._gekozen, self._nieuw, self.melding = False, gekozen, nieuw, NepMelding()

    def gekozen(self):
        return [self._gekozen]

    def vraag_tekst(self, *a, **k):
        return self._nieuw


FAT = stick_map("fat-stick")
(FAT / "Foto.JPG").write_text("foto")
os.link(FAT / "Foto.JPG", FAT / "Foto.jpg")  # zo ziet een FAT-stick het: twee namen, één bestand
hernoemd: list = []
_echt_path_rename = Path.rename
Path.rename = lambda self, doel: hernoemd.append((self.name, Path(doel).name)) or Path(doel)
nv = NepVenster(FAT / "Foto.JPG", "Foto.jpg")
nv.hernoem()
klopt(hernoemd == [("Foto.JPG", "Foto.jpg")] and not any("al iets" in x for x in nv.melding.teksten),
      f"U029: alleen hoofdletters anders op een stick: de naam wordt gewoon gewijzigd {nv.melding.teksten}")
(FAT / "Brief.txt").write_text("een")
(FAT / "brief.txt").write_text("twee")  # echt twee bestanden (op een gewone schijf kan dat)
hernoemd.clear()
nv = NepVenster(FAT / "Brief.txt", "brief.txt")
nv.hernoem()
Path.rename = _echt_path_rename
klopt(hernoemd == [] and any("al iets" in x for x in nv.melding.teksten),
      "U029: bestaat er echt een ander bestand met die naam, dan blijft het geweigerd")

# ============================================= U031: 'bugos-files Documents' vanuit een terminal: zoeken werkt ===
docs = THUIS / "Documenten"
docs.mkdir()
for n in ("recept.txt", "brief.txt", "foto.jpg"):
    (docs / n).write_text("x")
oude_map = os.getcwd()
os.chdir(THUIS)
start, kies = b.start_pad(["Documenten"])
klopt(start == docs and start.is_absolute(), f"U031: een map zonder volledig pad wordt een volledig pad: {start}")
vb = b.Bestanden(start, kies)
wacht(lambda: vb.lijst.model().rowCount(vb.lijst.rootIndex()) == 3, 5000)
vb.zoek.setText("recept")
wacht(lambda: vb.lijst.model().rowCount(vb.lijst.rootIndex()) == 1, 3000)
klopt(vb.lijst.model().rowCount(vb.lijst.rootIndex()) == 1, "U031: zoeken in die map vindt alleen 'recept'")
vb.close()
os.chdir(oude_map)

# ============================================================ U030: 3,2 GB in het Nederlands, 3.2 GB in het Engels ===
import bugos_drives  # noqa: E402

klopt(bugos_drives.mooie_maat(3_200_000_000) == "3,2 GB", "U030: Nederlands: 3,2 GB (met een komma)")
bugos_drives.TAAL = "en"
klopt(bugos_drives.mooie_maat(3_200_000_000) == "3.2 GB" and bugos_drives.mooie_maat(64_000_000_000) == "64 GB",
      f"U030: Engels: 3.2 GB (met een punt): {bugos_drives.mooie_maat(3_200_000_000)}")
bugos_drives.TAAL = "nl"

# ============================================== U028: "Sleep er iets naartoe": loslaten kopieert het echt ===
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402

leeg_map = THUIS / "Leeg"
leeg_map.mkdir()
(THUIS / "Ergens").mkdir()
(THUIS / "Ergens" / "lied.mp3").write_text("la")
(THUIS / "Ergens" / "verhuis.txt").write_text("weg")
vb = b.Bestanden(leeg_map)
vb.show()
wacht(lambda: vb.stapel.currentWidget() is vb.leeg, 3000)
klopt(vb.stapel.currentWidget() is vb.leeg and "Sleep" in vb.leeg_sub.text(), "U028: een lege map zegt 'Sleep er iets naartoe'")
# U038 (Bestanden): sluiten tijdens het kopiëren wacht; mislukt het daarna, dan blijft het venster open met de melding.
vb.sluit_na_klus = True
vb._klus_klaar(0, "de stick is eruit getrokken", False)
app.processEvents()
klopt(vb.isVisible() and not vb.sluit_na_klus and "stick" in vb.melding.tekst.text(),
      "U038: Bestanden: mislukt het kopiëren nadat je het venster sloot, dan blijft het open met de foutmelding")
klopt(not vb.melding.klok.isActive(), "U047: Bestanden: die foutmelding blijft staan (verdwijnt niet na 12 seconden)")


def laat_los(waar, pad: Path, shift: bool = False) -> bool:
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(pad))])
    mods = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    acties_ = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    with warnings.catch_warnings():  # Qt 6 heeft voor DragEnter alleen nog de oude maker met een QPoint
        warnings.simplefilter("ignore", DeprecationWarning)
        binnen = QDragEnterEvent(QPointF(20, 20).toPoint(), acties_, data, Qt.MouseButton.LeftButton, mods)
    QApplication.sendEvent(waar, binnen)
    if not binnen.isAccepted():
        return False
    los = QDropEvent(QPointF(20, 20), acties_, data, Qt.MouseButton.LeftButton, mods)
    QApplication.sendEvent(waar, los)
    return los.isAccepted()


klopt(laat_los(vb.leeg, THUIS / "Ergens" / "lied.mp3"), "U028: de lege map neemt iets aan dat je erop loslaat")
klopt(wacht(lambda: (leeg_map / "lied.mp3").exists() and not (vb.klus and vb.klus.isRunning()), 5000)
      and (THUIS / "Ergens" / "lied.mp3").exists(), "U028: loslaten kopieert het (het origineel blijft staan)")
wacht(lambda: vb.stapel.currentWidget() is vb.lijst, 3000)
klopt(laat_los(vb.lijst.viewport(), THUIS / "Ergens" / "verhuis.txt", shift=True)
      and wacht(lambda: (leeg_map / "verhuis.txt").exists() and not (THUIS / "Ergens" / "verhuis.txt").exists(), 5000),
      "U028: met Shift loslaten op de tegels verplaatst het")
wacht(lambda: not (vb.klus and vb.klus.isRunning()), 5000)
klopt(not laat_los(vb.lijst.viewport(), leeg_map / "lied.mp3"), "U028: iets uit deze map hier loslaten doet niets")
vb.close()

# ================================================= U019: het vertaal-sjabloon komt waar de apps kijken ===
import json  # noqa: E402

import bugos_base  # noqa: E402

lader = importlib.machinery.SourceFileLoader("verzamel", str(ROOT / "tools" / "collect-translations.py"))
spec = importlib.util.spec_from_loader("verzamel", lader)
verzamel = importlib.util.module_from_spec(spec)
lader.exec_module(verzamel)
klopt(verzamel.DOEL.relative_to(verzamel.BRONNEN).as_posix() == bugos_base.VERTALINGEN.relative_to("/usr").as_posix(),
      f"U019: het script schrijft naar de map die de apps lezen ({verzamel.DOEL.relative_to(ROOT)})")
verzamel.DOEL, verzamel.ROOT = TMP / "vertalingen", TMP  # niet in BugOS zelf schrijven
oud_argv = sys.argv
sys.argv = ["collect-translations.py"]
verzamel.main()
sys.argv = oud_argv
sjabloon = verzamel.DOEL / "template.json"
klopt(sjabloon.is_file() and len(json.loads(sjabloon.read_text())) > 400,
      "U019: zonder taalcode maakt het script template.json, met alle teksten")
echt = json.loads((ROOT / "system_files" / "usr" / "share" / "bugos" / "translations" / "template.json").read_text())
klopt("Writing to the stick… Do not unplug it yet." in echt and len(echt) > 400,
      f"U019: het sjabloon in BugOS is bijgewerkt ({len(echt)} teksten)")

print()
shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
