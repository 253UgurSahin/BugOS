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


import builtins  # noqa: E402

_echt_open = builtins.open


def nep_stick(aan: bool) -> None:
    def copyfile(s, d, *a, **k):
        if str(d).startswith(str(STICK)) and ":" in os.path.basename(d):
            raise OSError(errno.EINVAL, "Invalid argument", str(d))
        return _echt_copyfile(s, d, *a, **k)

    def chmod(p, mode, *a, **k):
        if str(p).startswith(str(STICK)) and stat.S_IMODE(mode) & 0o044 != 0o044:
            raise PermissionError(errno.EPERM, "Operation not permitted", str(p))
        return _echt_chmod(p, mode, *a, **k)

    def open_(f, mode="r", *a, **k):   # ook het kopiëren in stukken (U115) schrijft met open()
        if "w" in str(mode) and str(f).startswith(str(STICK)) and ":" in os.path.basename(str(f)):
            raise OSError(errno.EINVAL, "Invalid argument", str(f))
        return _echt_open(f, mode, *a, **k)

    shutil.copyfile = copyfile if aan else _echt_copyfile
    os.chmod = chmod if aan else _echt_chmod
    builtins.open = open_ if aan else _echt_open


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

# ============ U140: terugzetten met niets om terug te zetten (stick eruit tijdens de vraag): niet 'Klaar!' ===
w = open_venster(bb)
_echt_vraag = bb.QMessageBox.question if hasattr(bb, "QMessageBox") else None
from PySide6.QtWidgets import QMessageBox as _QMB  # noqa: E402

_oud_q = _QMB.question
_doel = bb.backup_doel(SCHIJF)


def _ja_en_weg(*a, **k):
    for _m in list(_doel.iterdir()):   # de stick 'valt eruit' terwijl de vraag openstaat
        if _m.is_dir():
            shutil.rmtree(_m)
    return _QMB.StandardButton.Yes


_QMB.question = staticmethod(_ja_en_weg)
w.zet_terug()
wacht(lambda: "terug" in w.melding.tekst.text() or "niets" in w.melding.tekst.text() or "nothing" in w.melding.tekst.text(), 3000)
_QMB.question = _oud_q
klopt("Klaar" not in w.melding.tekst.text() and "Done" not in w.melding.tekst.text(),
      f"U140: niets om terug te zetten: geen 'Klaar! Je bestanden staan terug' ({w.melding.tekst.text()[:50]})")
w.close()
bb.zonder_venster(SCHIJF)   # de back-up weer maken voor de tests hierna

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

# U150/U152: Overstap noemt de mappen in je eigen taal; de balk van Back-up loopt één keer van 0 tot 100.
klopt(bo.mapnaam("Pictures") in ("Afbeeldingen", "Pictures") and bo.deels_uitleg(["Pictures"]).count("Pictures") == 0
      or bugos_ui.TAAL != "nl", f"U150: Overstap zegt 'Afbeeldingen', niet 'Pictures' ({bo.deels_uitleg(['Pictures'])})")
w = open_venster(bb)
w.stap_nr, w.stappen_totaal, w.uitvoer = 2, 3, ""
w.proces.readAllStandardOutput = lambda: b"50%"
w.lees()
klopt(w.balk.value() == 50, f"U152: Back-up: map 2 van 3 op 50% is 50% van het geheel ({w.balk.value()})")
w.close()


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
    # 2b. U241: 'Nu stoppen' en het venster meteen weer openen: dat wordt gezegd, en een nieuwe klus stopt niet meteen
    w = open_venster(module)
    w.vraag_stoppen = lambda: True
    getattr(w, begin)()
    wacht(lambda: draait(w), 5000)
    w.close()
    w.sluit_na = False   # weer geopend (dat doet luister())
    wacht(lambda: not draait(w), 8000)
    for _ in range(20):
        app.processEvents()
    klopt("Gestopt" in w.melding.tekst.text() and not w.gestopt and w.isVisible(),
          f"U241: {naam}: gestopt en weer geopend: 'Gestopt' (niet 'Bezig met stoppen…'), en de volgende klus gaat door "
          f"({w.melding.tekst.text()!r}, gestopt={w.gestopt})")
    w.close()
    wacht(lambda: not w.isVisible(), 3000)
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
klopt("5,0 GB" in w.melding.tekst.text() and "1,0 GB" in w.melding.tekst.text(),
      f"U237: Back-up schrijft in het Nederlands een komma: 5,0 GB ({w.melding.tekst.text()!r})")
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
# U081: na je eerste app staat 'Mijn apps' meteen in de zijbalk (niet pas na opnieuw openen).
_mijn = lambda: [i for i in range(ww.lijst.count()) if ww.lijst.item(i).data(winkel.Qt.ItemDataRole.UserRole) == "_mijn"]  # noqa: E731
for _i in reversed(_mijn()):
    ww.lijst.takeItem(_i)
ww.bezig_met = "org.videolan.VLC"
ww.klaar(0, None)
ww.bezig_met = "org.videolan.VLC"
ww.klaar(0, None)
klopt(len(_mijn()) == 1, "U081: na de eerste app staat 'Mijn apps' er meteen (één keer)")

# ================================== U016: een schermlezer hoort een naam bij schuifjes, regels en keuzekaarten ===
from PySide6.QtGui import QAccessible  # noqa: E402


def lezer(w) -> tuple[str, str, str]:
    i = QAccessible.queryAccessibleInterface(w)
    return (i.role().name, i.text(QAccessible.Text.Name), i.text(QAccessible.Text.Description)) if i else ("", "", "")


kiezer = bugos_ui.SchijfKiezer("Steek een USB-schijf in…")
kiezer.zet([("/run/media/u/STICK", "STICK", "29 GB vrij van 29 GB")])
klopt(lezer(next(iter(kiezer.kaarten.values())))[1:] == ("STICK", "29 GB vrij van 29 GB"),
      f"U016: de schijfkaart in Back-up/Overstap heeft de naam van de stick: {lezer(next(iter(kiezer.kaarten.values())))}")
_wijzig: list = []
kiezer.gewijzigd.connect(lambda: _wijzig.append(1))
kiezer.zet([("/run/media/u/STICK", "STICK", "29 GB vrij van 29 GB")])
_zelfde = len(_wijzig)
kiezer.zet([("/run/media/u/STICK", "STICK", "Heeft al een back-up · 20 GB vrij van 29 GB")])
klopt(_zelfde == 0 and lezer(next(iter(kiezer.kaarten.values())))[2] == "Heeft al een back-up · 20 GB vrij van 29 GB"
      and kiezer.gekozen() == "/run/media/u/STICK",
      f"U080: de schijfkaart toont de nieuwe tekst na een back-up (en blijft gekozen): {lezer(next(iter(kiezer.kaarten.values())))}")
_kaart = next(iter(kiezer.kaarten.values()))
kiezer.zet([("/run/media/u/STICK", "STICK", "21 GB vrij van 29 GB")])
klopt(next(iter(kiezer.kaarten.values())) is _kaart and lezer(_kaart)[2] == "21 GB vrij van 29 GB",
      "U102: alleen een andere tekst: dezelfde kaart (de focus blijft), met de nieuwe tekst")
kiezer.setEnabled(False)
kiezer.zet([("/run/media/u/STICK", "STICK", "19 GB vrij van 29 GB")])
klopt(not next(iter(kiezer.kaarten.values())).isEnabled(), "U080: tijdens een klus blijft een vernieuwde kaart op slot")
kiezer.setEnabled(True)

welkom = laad("bugos_welkom", "bugos-welcome")
for pagina in (welkom.Uiterlijk(), welkom.Updates()):
    kaarten = pagina.findChildren(bugos_ui.KeuzeKaart)
    namen = [lezer(k)[1] for k in kaarten]
    klopt(kaarten and all(namen), f"U016: Welkom ({type(pagina).__name__}): elke keuze heeft een naam: {namen}")

# U074: Welkom > 'Wat ga je doen?': Volgende, Terug, Volgende start niets twee keer, en uitzetten na het starten kan
# hier niet meer (het loopt al), dat zegt de pagina.
_gestart: list = []
_oud_start = welkom.start
welkom.start = lambda *a: _gestart.append(a)
_oud_steam = welkom.steam_opdracht
welkom.steam_opdracht = lambda: ("steam",)
jij = welkom.Jij()
jij.dev.schuif.setChecked(True)
jij.gamer.schuif.setChecked(True)
jij.bij_volgende()
jij.bij_volgende()
jij.oud.schuif.setChecked(True)
jij.bij_volgende()
welkom.start = _oud_start
klopt(_gestart == [("bugos-developer", "aan"), ("bugos-light-mode", "aan"), ("steam",)] or
      _gestart == [("bugos-developer", "aan"), ("steam",), ("bugos-light-mode", "aan")]
      and not jij.dev.schuif.isEnabled() and not jij.al_bezig.isHidden(),
      f"U074: Welkom start elke keuze maar één keer, en zegt dat het al loopt ({_gestart})")
# U130: geen Steam (ook niet als Flatpak): het schuifje gaat niet op slot met 'wordt klaargezet'.
welkom.steam_opdracht = lambda: ()
welkom.start = lambda *a: _gestart.append(a)
_gestart.clear()
jij2 = welkom.Jij()
jij2.gamer.schuif.setChecked(True)
jij2.bij_volgende()
welkom.start, welkom.steam_opdracht = _oud_start, _oud_steam
klopt(not _gestart and jij2.gamer.schuif.isEnabled(), "U130: zonder Steam: niets 'klaargezet' en het schuifje blijft vrij")
klopt(not jij2.steam_nog.isHidden(), "U181: zonder Steam (nog): de pagina zegt dat Steam nog komt")
# U179: de lichte stand stond al aan (vanzelf op een oudere pc): dan staat het schuifje ook aan.
_ls = TMP / "nep-ls-u179"
_ls.mkdir()
(_ls / "bugos-light-mode").write_text("#!/usr/bin/bash\n[ \"$1\" = status ] && echo aan\n")
(_ls / "bugos-light-mode").chmod(0o755)
_op = os.environ["PATH"]
os.environ["PATH"] = f"{_ls}:{_op}"
jij3 = welkom.Jij()
os.environ["PATH"] = _op
klopt(jij3.oud.schuif.isChecked() and "oud" in jij3.gestart and not jij3.oud.schuif.isEnabled(),
      "U179/U189: Welkom toont de lichte stand die al aan staat als aan (op slot: uitzetten doe je in Instellingen)")
# U129: de updatekeuze wordt pas onthouden als het lukte (Annuleren bij het wachtwoord: Volgende probeert opnieuw).
_upd = welkom.Updates()
_pk = TMP / "pk-nep"
_pk.mkdir()
(_pk / "pkexec").write_text("#!/usr/bin/bash\nexit 126\n")
(_pk / "pkexec").chmod(0o755)
_oud_path = os.environ["PATH"]
os.environ["PATH"] = f"{_pk}:{_oud_path}"
_begin = _upd.begin
_upd.hand.setChecked(True)
_upd.bij_volgende()
wacht(lambda: not getattr(_upd, "bezig", False), 5000)
os.environ["PATH"] = _oud_path
klopt(_upd.begin == _begin and _begin != "hand", f"U129: Annuleren bij het wachtwoord: de updatekeuze is niet als gedaan onthouden ({_upd.begin})")

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
# U062: schuifbalken (volume, helderheid) heten zoals hun regel; keuzeknoppen ("30 min") weten bij welke regel ze horen.
from PySide6.QtWidgets import QSlider  # noqa: E402
balken = [b_ for b_ in vi.findChildren(QSlider)]
klopt(balken and all(lezer(b_)[1] for b_ in balken), f"U062: elke schuifbalk in Instellingen heeft een naam ({[lezer(b_)[1] for b_ in balken]})")
from bugos_settings_onderdelen import Keuzes  # noqa: E402
keuzeknoppen = [k for kz in vi.findChildren(Keuzes) for k in kz.knoppen.values()]
klopt(keuzeknoppen and all(k.accessibleDescription() for k in keuzeknoppen),
      f"U062: keuzeknoppen ('30 min', 'Nooit') zeggen bij welke regel ze horen ({len(keuzeknoppen)} knoppen)")
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
# U108: echt weggooien op een stick gebeurt op de achtergrond (het venster loopt niet vast).
import bugos_files_bewerken as _bw  # noqa: E402

_grote = STICK / "Duizend fotos"
_grote.mkdir()
for _i in range(50):
    (_grote / f"{_i}.jpg").write_text("x")
_echt_zs, _echt_vraag, _echt_gekozen = _bw.zelfde_schijf, vb.vraag_ja, vb.gekozen
_bw.zelfde_schijf = lambda a, b_: False
vb.vraag_ja = lambda *a, **k: True
vb.gekozen = lambda: [_grote]
vb.weggooien()
_op_achtergrond = vb.klus is not None and isinstance(vb.klus, acties.Weggooien)
wacht(lambda: not _grote.exists() and not vb.klus.isRunning(), 5000)
for _ in range(10):
    app.processEvents()
_bw.zelfde_schijf, vb.vraag_ja, vb.gekozen = _echt_zs, _echt_vraag, _echt_gekozen
klopt(_op_achtergrond and not _grote.exists() and "weggegooid" in vb.melding.tekst.text(),
      f"U108: weggooien op een stick op de achtergrond, met een melding ({vb.melding.tekst.text()[:40]})")
# U119: weggooien op een stick terwijl er nog iets loopt: eerst zeggen, niet eerst vragen.
_gevraagd_ja: list = []


class _Bezig:
    def isRunning(self):
        return True


_bw.zelfde_schijf = lambda a, b_: False
vb.vraag_ja = lambda *a, **k: (_gevraagd_ja.append(1), True)[1]
(STICK / "nog een").mkdir()
vb.gekozen = lambda: [STICK / "nog een"]
_echte_klus, vb.klus = vb.klus, _Bezig()
vb.weggooien()
klopt(not _gevraagd_ja and (STICK / "nog een").exists() and "Even wachten" in vb.melding.tekst.text(),
      "U119: weggooien terwijl er nog iets loopt: eerst zeggen, niet eerst 'Echt weggooien?' vragen")
vb.klus = _echte_klus
# U119: een gemengde keuze (thuis en stick): de melding telt allebei, en Ongedaan maken blijft.
(THUIS / "naar-bak.txt").write_text("x")
_bw.zelfde_schijf = lambda a, b_: not str(a).startswith(str(STICK))
vb.gekozen = lambda: [THUIS / "naar-bak.txt", STICK / "nog een"]
vb.weggooien()
wacht(lambda: not (STICK / "nog een").exists() and not vb.klus.isRunning(), 5000)
for _ in range(10):
    app.processEvents()
klopt("prullenbak" in vb.melding.tekst.text() and not vb.melding.knop.isHidden(),
      f"U119: gemengd weggooien: telt allebei en houdt 'Ongedaan maken' ({vb.melding.tekst.text()})")
_bw.zelfde_schijf, vb.vraag_ja, vb.gekozen = _echt_zs, _echt_vraag, _echt_gekozen
# U120: na knippen en plakken in een ander venster staat 'Plakken' niet meer aan (de bestanden zijn weg).
from PySide6.QtCore import QMimeData, QUrl  # noqa: E402

_md = QMimeData()
_md.setUrls([QUrl.fromLocalFile(str(TMP / "bestaat-niet-meer.txt"))])
app.clipboard().setMimeData(_md)
klopt(not vb.klembord_heeft_bestanden(), "U120: het klembord wijst naar bestanden die weg zijn: geen 'Plakken'")
app.clipboard().setText("")
# U116: Stoppen laat 'Haal de stick er nog niet uit' zien, en een late voortgang haalt de knop niet terug.
_slome = TMP / "slome-bron"
_slome.mkdir()
(_slome / "a.bin").write_bytes(b"y" * (40 * 1024 * 1024))
vb.gekozen = _echt_gekozen
(TMP / "stop-doel").mkdir()
vb._start_klus([_slome], TMP / "stop-doel", False, klembord=False)
wacht(lambda: "kopiëren" in vb.melding.tekst.text() and not vb.melding.knop.isHidden(), 3000)
vb.melding.knop.click()
_na_stop = vb.melding.tekst.text()
vb.klus.voortgang.emit(0, 1)
_late = vb.melding.tekst.text()
wacht(lambda: not vb.klus.isRunning(), 10000)
for _ in range(10):
    app.processEvents()
klopt(("Stoppen" in _na_stop or "Stopping" in _na_stop or "Gestopt" in _na_stop) and _late == _na_stop,
      f"U116: na Stoppen: 'haal de stick er nog niet uit', en de knop komt niet terug ({_na_stop} / {_late})")

# U106/U107: de melding noemt de (2)-namen, en knippen-plakken wist niet wat je intussen anders kopieerde.
vb.sluit_na_klus = False


class _NepKlus:
    gestopt, hernoemd, achter = False, 3, []


app.clipboard().setText("https://voorbeeld.nl")
vb._klus_klaar(5, "", True, [], True, _NepKlus())
klopt("(2)" in vb.melding.tekst.text() and app.clipboard().text() == "https://voorbeeld.nl",
      f"U106/U107: melding over (2)-namen ({vb.melding.tekst.text()[:60]}), het klembord van een ander blijft staan")


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

# ========================== U076: een bestand met een heel lange naam kan ook naar de prullenbak ===
_lang_map = TMP / "lang"
_lang_map.mkdir()
_mislukt = []
for _naam in ("a" * 248 + ".jpg", "é" * 125 + ".txt", "b" * 255):
    _bron = _lang_map / _naam
    _bron.write_text("x")
    try:
        _in_bak, _info = acties.naar_prullenbak(_bron)
        _terug = acties.terugzetten(_in_bak, _info)
        if _terug != _bron or not _bron.exists() or _info.exists() or len(_info.name.encode()) > 255 \
                or _in_bak.suffix != _bron.suffix:
            _mislukt.append((len(_naam.encode()), "terug", _terug.name[:20]))
    except OSError as e:
        _mislukt.append((len(_naam.encode()), str(e)))
klopt(not _mislukt, f"U076: namen tot 255 bytes kunnen naar de prullenbak en weer terug, de extensie blijft ({_mislukt})")
_bron = _lang_map / ("c" * 250 + ".png")
_bron.write_text("1")
_a, _ = acties.naar_prullenbak(_bron)
_bron.write_text("2")
_b2, _ = acties.naar_prullenbak(_bron)
klopt(_a != _b2 and _a.read_text() == "1" and _b2.read_text() == "2" and _b2.suffix == ".png",
      "U076: twee keer dezelfde lange naam: allebei in de prullenbak, niets overschreven")

# U086: de prullenbak in Bestanden toont de echte naam, niet de ingekorte naam in de prullenbak.
_bron = _lang_map / ("d" * 250 + ".txt")
_bron.write_text("x")
acties.naar_prullenbak(_bron)
_bv = b.Bestanden(THUIS) if hasattr(b, "Bestanden") else None
if _bv is not None:
    _bv.open_prullenbak()
    _namen = [_bv.bak_model.item(i).text() for i in range(_bv.bak_model.rowCount())]
    klopt(_bron.name in _namen, "U086: de prullenbak toont de echte (lange) naam")
    _bv.close()
else:
    klopt(False, "U086: venster Bestanden niet gevonden")

# U094-U096: het Windows-deel van Overstap (statisch: hier is geen PowerShell; de CI op Windows leest het script ook).
_ps = (ROOT / "windows-switch" / "BugOS-Switch.ps1").read_text(encoding="utf-8-sig")
klopt("$LASTEXITCODE -ge 16) { throw" in _ps and "$LASTEXITCODE -ge 8) { $script:Deels += $m.Naam }" in _ps
      and "deels      = @($script:Deels)" in _ps,
      "U094: robocopy 8 (een paar bestanden niet) stopt het meenemen niet; bugos-switch.json wordt toch geschreven")
_maak = _ps[_ps.index("$maak.Add_Click"):]
klopt("Test-SwitchBestanden $stick.Number" in _maak and _maak.index("Test-SwitchBestanden") < _maak.index("Vraag ("),
      "U095: stap 4 wist geen stick waar je bestanden uit stap 2 op staan (eerst kijken, dan pas vragen)")
klopt("/XF desktop.ini Thumbs.db" in _ps, "U096: desktop.ini en Thumbs.db gaan niet mee naar BugOS")

# ========================== U103-U107: kopiëren in Bestanden: vol, stoppen, de stick-melding, (2)-namen, klembord ===
import errno as _errno  # noqa: E402

_src = TMP / "camera"
_src.mkdir()
for _i in range(5):
    (_src / f"IMG_{_i}.JPG").write_text("x")
_naar = TMP / "foto-doel"
_naar.mkdir()
_echt_een = acties._kopieer_bestand
_pogingen: list = []


def _vol_na_twee(bron, doel, stop=None):
    _pogingen.append(bron)
    if len(_pogingen) > 2:
        raise OSError(_errno.ENOSPC, "No space left on device")
    return _echt_een(bron, doel, stop)


acties._kopieer_bestand = _vol_na_twee
_k = b.Klus(sorted(_src.iterdir()), _naar, False)
_u: list = []
_k.klaar.connect(lambda g, f: _u.append((g, f)))
_k.run()
acties._kopieer_bestand = _echt_een
klopt(_u and _u[0][0] == 2 and "2 van 5" in _u[0][1] and len(_pogingen) == 3,
      f"U103: schijf vol: zegt hoeveel er wel en niet mee zijn, en probeert de rest niet meer ({_u}, {len(_pogingen)} pogingen)")
# U104: stoppen midden in een map: niets half achtergebleven; en oude halve kopieën worden na een dag opgeruimd.
_map = TMP / "grote-map"
_map.mkdir()
for _i in range(5):
    (_map / f"f{_i}.txt").write_text("x")
_teller = []
try:
    acties.kopieer_een(_map, _naar, False, [], stop=lambda: (_teller.append(1), len(_teller) > 2)[1])
    _gestopt = False
except acties.Gestopt:
    _gestopt = True
klopt(_gestopt and not list(_naar.glob(".*bugos-bezig")) and not (_naar / "grote-map").exists(),
      "U104: stoppen tijdens het kopiëren: niets half achtergebleven")
_oud = _naar / ".oud.bugos-bezig"
_oud.mkdir()
_nieuw = _naar / ".nieuw.bugos-bezig"
_nieuw.mkdir()
os.utime(_oud, (1, 1))
acties.ruim_oude_halve_op(_naar)
klopt(not _oud.exists() and _nieuw.exists(), "U104: een oude halve kopie (stroom eraf) wordt opgeruimd, een lopende niet")
_nieuw.rmdir()
# U115: Stoppen tijdens één groot bestand dat je verplaatst: het origineel blijft, er staat niets half.
_film = TMP / "film.mkv"
_film.write_bytes(b"x" * (9 * 1024 * 1024))
_echt_rename = os.rename
_eerste_rename = []


def _ander_schijf_rename(a, b_):
    if not _eerste_rename:   # de eerste os.rename (verplaatsen) doet alsof het naar een andere schijf gaat
        _eerste_rename.append(1)
        raise OSError(_errno.EXDEV, "cross-device")
    return _echt_rename(a, b_)


acties.os.rename = _ander_schijf_rename
try:
    acties.kopieer_een(_film, _naar, True, [], stop=lambda: True)
    _uitkomst = "klaar"
except acties.Gestopt:
    _uitkomst = "gestopt"
acties.os.rename = _echt_rename
klopt(_uitkomst == "gestopt" and _film.exists() and not (_naar / "film.mkv").exists()
      and not list(_naar.glob(".*bugos-bezig")),
      f"U115: stoppen tijdens één groot bestand (verplaatsen): het origineel blijft, niets half ({_uitkomst})")
# U144: een 'pijp' (FIFO) kopiëren blijft niet eeuwig hangen; Stoppen werkt ook midden in een groot bestand in een map.
import threading as _thr  # noqa: E402

_pijp = TMP / "steam.pipe"
os.mkfifo(_pijp)
_klaar_pijp: list = []
_t = _thr.Thread(target=lambda: _klaar_pijp.append(
    (lambda: (acties.kopieer_een(_pijp, _naar, False, [], stop=lambda: False), "klaar"))() if False else None), daemon=True)


def _probeer_pijp():
    try:
        acties.kopieer_een(_pijp, _naar, False, [], stop=lambda: False)
        _klaar_pijp.append("klaar")
    except (OSError, shutil.Error) as e:
        _klaar_pijp.append(type(e).__name__)


_t = _thr.Thread(target=_probeer_pijp, daemon=True)
_t.start()
_t.join(3)
klopt(bool(_klaar_pijp), f"U144: een pijp (FIFO) kopiëren hangt niet, maar geeft meteen een fout ({_klaar_pijp})")
_filmmap = TMP / "filmmap"
_filmmap.mkdir()
(_filmmap / "film.mkv").write_bytes(b"z" * (17 * 1024 * 1024))
_tel = []
try:
    acties.kopieer_een(_filmmap, _naar, False, [], stop=lambda: (_tel.append(1), len(_tel) > 2)[1])
    _st = "klaar"
except acties.Gestopt:
    _st = "gestopt"
klopt(_st == "gestopt" and not (_naar / "filmmap").exists() and not list(_naar.glob(".*bugos-bezig")),
      f"U144: Stoppen midden in één groot bestand in een map: meteen gestopt, niets half ({_st}, {len(_tel)} keer gekeken)")

# U122: Stoppen als het al klaar is, telt niet als 'gestopt'.
_k = b.Klus([], _naar, False)
_k.stop()
klopt(not _k.gestopt, "U122: Stoppen nadat het kopiëren al klaar was: niet 'Gestopt' melden")

# U105: van een stick naar de computer kopiëren zegt niet 'Haal de stick er nog niet uit'.
_ws: list = []
_k = b.Klus([_src / "IMG_0.JPG"], TMP / "thuis-doel", False)
(TMP / "thuis-doel").mkdir()
_k.wegschrijven.connect(lambda: _ws.append(1))
_echt_zelfde = acties.zelfde_schijf
acties.zelfde_schijf = lambda a, b_: False   # doe alsof de stick een andere schijf is dan de computer
_k.run()
acties.zelfde_schijf = _echt_zelfde
klopt(not _ws, "U105: kopiëren naar de computer (niet naar een stick): geen 'Haal de stick er nog niet uit'")
os.environ["BUGOS_LOSSE_SCHIJF"] = str(TMP / "thuis-doel")   # nu is dit wel een stick
acties.zelfde_schijf = lambda a, b_: False
_k = b.Klus([_src / "IMG_1.JPG"], TMP / "thuis-doel", False)
_k.wegschrijven.connect(lambda: _ws.append(1))
_k.run()
acties.zelfde_schijf = _echt_zelfde
del os.environ["BUGOS_LOSSE_SCHIJF"]
klopt(_ws == [1], "U105: kopiëren naar een stick: wel eerst wegschrijven ('Haal de stick er nog niet uit')")
# U106: dezelfde foto's nog een keer: zeggen dat ze (2) achter de naam kregen.
(TMP / "tweede-keer").mkdir()
_k = b.Klus([_src / "IMG_0.JPG", _src / "IMG_1.JPG"], TMP / "tweede-keer", False)
_k.run()
_k2 = b.Klus([_src / "IMG_0.JPG", _src / "IMG_1.JPG"], TMP / "tweede-keer", False)
_k2.run()
klopt(_k.hernoemd == 0 and _k2.hernoemd == 2, f"U106: de tweede keer kregen 2 bestanden (2) achter de naam ({_k2.hernoemd})")

# ========================== U134: elke knop, schuif en regel laat zien dat hij de toetsenbordfocus heeft ===
from PySide6.QtWidgets import QSlider, QVBoxLayout, QWidget  # noqa: E402

_houder = QWidget()
_lay = QVBoxLayout(_houder)
_rond = bugos_ui.ronde_knop("terug", "Terug")
_rand = bugos_ui.Knop("Opnieuw kijken", "rand")
_schuif = QSlider(Qt.Orientation.Horizontal)
_schuif.setFixedWidth(200)
for _w in (_rond, _rand, _schuif):
    _lay.addWidget(_w)
_houder.show()
_houder.activateWindow()
wacht(lambda: _houder.isActiveWindow(), 2000)
_zonder_focus = {}
_anders = []
for _naam, _w in (("ronde knop", _rond), ("rand-knop", _rand), ("schuif", _schuif)):
    _houder.setFocus()
    app.processEvents()
    _voor = _w.grab().toImage()
    _w.setFocus()
    for _ in range(5):
        app.processEvents()
    _na = _w.grab().toImage()
    if _voor == _na:
        _anders.append(_naam)
_houder.close()
klopt(not _anders, f"U134: de toetsenbordfocus is te zien op elke knop en schuif (niet bij: {_anders})")

# ========================== U137: kleine tekst haalt 4,5:1 contrast (WCAG AA) in het lichte thema ===
def _lum(h):
    c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b_):
    x, y = sorted((_lum(a), _lum(b_)), reverse=True)
    return (x + 0.05) / (y + 0.05)


_L = bugos_ui.KLEUREN["licht"]
_laag = [(v, a, round(_contrast(_L[v], _L[a]), 2)) for v in ("tekst2", "tekst3", "goed", "let_op", "fout")
         for a in ("achter", "vlak") if _contrast(_L[v], _L[a]) < 4.5]
klopt(not _laag, f"U137: kleine tekst in het lichte thema haalt 4,5:1 ({_laag})")
# U273: ook in het donker, op de hoofdknoppen en bij wat je koos (zijbalk); het schuifje 'uit' haalt 3:1.
_laag = []
for _th, _k in bugos_ui.KLEUREN.items():
    _paren = [("accent_tekst", "knop_hoofd", 4.5), ("accent_tekst", "knop_hoofd_hover", 4.5),
              ("accent_gekozen", "accent_zacht", 4.5), ("tekst3", "vlak", 4.5), ("tekst2", "vlak", 4.5),
              ("schuif_uit", "vlak", 3.0), ("fout", "fout_zacht", 4.5)]   # (U299)
    _laag += [(_th, v, a, round(_contrast(_k[v], _k[a]), 2)) for v, a, m in _paren if _contrast(_k[v], _k[a]) < m]
klopt(not _laag, f"U273: hoofdknoppen, gekozen items en het schuifje halen genoeg contrast, licht en donker ({_laag})")

# ========================== U138: taalrestjes: de Hulp-uitslag, 'rustig verstuurd', dezelfde woorden voor afmelden ===
_help = (ROOT / "system_files/usr/bin/bugos-help").read_text()
_tm = (ROOT / "system_files/usr/bin/bugos-task-manager").read_text()
_sm = (ROOT / "system_files/usr/share/plasma/plasmoids/org.bugos.startmenu/contents/ui/StartMenu.qml").read_text()
klopt('t("BugOS hulp-uitslag", "BugOS help report")' in _help and "niets verstuurd" in _tm
      and 'menu.tr("Afmelden", "Log out")' in _sm and 'menu.tr("Opnieuw opstarten", "Restart")' in _sm,
      "U138: Hulp-uitslag ook in het Engels, geen 'rustig verstuurd', startmenu zegt Afmelden/Opnieuw opstarten zoals het uitzetscherm")

# ========================== U170-U172: voorbeeldjes in Bestanden: klein genoeg, een vaste grens, en PDF's ===
import bugos_files_tegels as _tg  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402

_groot = QImage(4000, 3000, QImage.Format.Format_RGB32)
_groot.fill(QColor("#336699"))
_fp = TMP / "grote-foto.jpg"
_groot.save(str(_fp), "JPG")
_vb = _tg.maak_voorbeeld(str(_fp))
klopt(max(_vb.width(), _vb.height()) <= 256, f"U170: een grote foto krijgt een voorbeeldje van hoogstens 256 px ({_vb.width()}x{_vb.height()})")
_v = _tg.Voorbeelden()
for _i in range(_tg.CACHE_MAX + 50):
    _v._klaar(f"/x/{_i}.jpg", _vb, _v.generatie)
klopt(len(_v.cache) == _tg.CACHE_MAX, f"U170: de voorbeeldjes-cache heeft een grens ({len(_v.cache)})")
_oud = _v.generatie
_v.vergeet()
_v._klaar("/oude-map/a.jpg", _vb, _oud)
klopt("/oude-map/a.jpg" not in _v.cache and _v.generatie == _oud + 1,
      "U171: na een andere map tellen de nog lopende voorbeeldjes van de oude map niet meer")
if shutil.which("pdftoppm"):
    _pdf = TMP / "brief.pdf"
    from PySide6.QtGui import QPageSize, QPdfWriter, QPainter as _QP  # noqa: E402
    _w = QPdfWriter(str(_pdf))
    _w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    _pt = _QP(_w)
    _pt.drawText(100, 100, "Hallo")
    _pt.end()
    _pv = _tg.maak_voorbeeld(str(_pdf))
    klopt(not _pv.isNull() and max(_pv.width(), _pv.height()) <= 256, f"U172: een PDF krijgt een eigen voorbeeldje ({_pv.width()}x{_pv.height()})")
    _uri, _naam, _cache = _tg._thumb_plek(str(_pdf))
    klopt((_cache / "large" / _naam).exists(), "U197: het voorbeeldje van een PDF wordt bewaard (de volgende keer niet opnieuw maken)")
    klopt(stat.S_IMODE(os.stat(_cache / "large" / _naam).st_mode) == 0o600 and stat.S_IMODE(os.stat(_cache / "large").st_mode) == 0o700,
          "U201: bewaarde voorbeeldjes zijn alleen voor jou (map 0700, bestand 0600)")
_help_tekst = (ROOT / "system_files/usr/bin/bugos-help").read_text()
klopt("else QApplication.quit())" in _help_tekst, "U199: Hulp sluiten tijdens een controle: het programma stopt echt (niet onzichtbaar door)")
klopt("timeout 180 skopeo inspect" in (ROOT / "system_files/usr/bin/bugos-updatecheck").read_text(),
      "U202: de updatecheck kan niet eeuwig op skopeo blijven hangen")

# ========================== U173, U175-U177: Winkel en Windows-installaties ===
_alt = (ROOT / "system_files/usr/share/bugos/alternatives.txt").read_text()
_store = json.loads((ROOT / "system_files/usr/share/bugos/store.json").read_text())
klopt("eneshecan" not in _alt and "com.rtosta.zapzap" in _alt and any(a["id"] == "com.rtosta.zapzap" for a in _store["apps"]),
      "U173: WhatsApp verwijst naar ZapZap (de oude app is van Flathub gehaald), en ZapZap staat in de Winkel")
klopt(all(w in _alt for w in ("^tsetup|", "epicinstaller|", "gog_galaxy|")),
      "U176: de echte bestandsnamen van Telegram, Epic en GOG Galaxy worden herkend")
klopt(next(a for a in _store["apps"] if a["id"] == "org.kde.kcalc").get("naam_en") == "Calculator",
      "U175: de rekenmachine heet in het Engels 'Calculator'")
klopt('draai("pkexec", "/usr/bin/systemctl", "restart", "cups", timeout=120)' in (ROOT / "system_files/usr/bin/bugos-help").read_text(),
      "U177: Hulp wacht op het wachtwoord voor de printerdienst voor hij opnieuw kijkt")
# U246: met het beheerderswachtwoord draait altijd het echte programma, niet een gelijknamig bestand op je PATH.
_pk_fout = []
for _bin in sorted((ROOT / "system_files/usr/bin").iterdir()):
    if _bin.is_file():
        for _r in _bin.read_text(errors="ignore").splitlines():
            if "pkexec" in _r and not _r.lstrip().startswith("#") and ("pkexec \"$0\"" in _r or 'pkexec", "systemctl"' in _r):
                _pk_fout.append(f"{_bin.name}: {_r.strip()}")
klopt(not _pk_fout, f"U246: pkexec start alleen programma's met een vast pad ({_pk_fout})")

# ========================== U184-U186: schuifje, vrije ruimte, Opstarten ===
from bugos_widgets import Schuif as _Schuif  # noqa: E402

_s = _Schuif(False)
_s.show()
_s.click()
_s.zet_stil(False)
wacht(lambda: False, 400)
klopt(not _s.isChecked() and _s.property("stand") == 0.0,
      f"U184: een schuifje dat meteen wordt teruggezet, staat ook getekend op 'uit' ({_s.property('stand')})")
_s.close()
import bugos_pages as _bpg  # noqa: E402

_echt_du = _bpg.shutil.disk_usage
_bpg.shutil.disk_usage = lambda p_: type("G", (), {"free": 450 * 10**6, "total": 2 * 10**9})()
_tekst = _bpg.schijf_info(TMP)
_bpg.shutil.disk_usage = _echt_du
klopt("0 GB vrij" not in _tekst and "0 GB free" not in _tekst and "450" in _tekst, f"U185: een kleine stick met 450 MB vrij: niet '0 GB vrij' ({_tekst})")
import bugos_tasks_ui as _btu  # noqa: E402
import bugos_tasks as _bts  # noqa: E402

_it = _bts.Opstart("x.desktop", "X", "", True, False)
_r = _btu.OpstartRij(_it, lambda item, aan: False)
_r.schuif.setChecked(False)
klopt(_r.schuif.isChecked() and "Start mee" in _r.stand.text() or "Starts" in _r.stand.text(),
      "U186: Opstarten: lukt het omzetten niet, dan springt het schuifje terug")

# ========================== U209-U213 ===
from bugos_widgets import label as _label  # noqa: E402

_w = _label("<h1>GRATIS WIFI</h1>")
klopt(_w.textFormat() == Qt.TextFormat.PlainText, "U210: een naam van buiten (wifi, bestand) wordt geen opmaak")
_nav = (ROOT / "system_files/usr/lib/bugos/python/bugos_files_navigeren.py").read_text()
klopt('QPushButton(zichtbaar.replace("&", "&&"))' in _nav, "U210: een & in een mapnaam (R&D) wordt geen sneltoets")
klopt(winkel.app_naam({"naam": "Rekenmachine", "naam_en": "Calculator"}) in ("Rekenmachine", "Calculator")
      and "app_naam(app)" in (ROOT / "system_files/usr/bin/bugos-store").read_text().split("def installeer")[1][:400],
      "U209: de Winkel gebruikt overal de naam in jouw taal (ook bij installeren)")
klopt('t("Nederlands", "English")' in (ROOT / "system_files/usr/bin/bugos-welcome").read_text(),
      "U213: Welkom met LANG=C noemt de taal 'English', niet 'Nederlands'")
# U212: Welkom sluiten terwijl de wachtwoordvraag openstaat: het venster blijft tot het klaar is.
_wk = welkom.Welkom()
_wk.show()
_wk.paginas[0].bezig = True
_wk.close()
_open = _wk.isVisible()
_wk.paginas[0].bezig = False
wacht(lambda: not _wk.isVisible(), 3000)
klopt(_open and not _wk.isVisible(), "U212: Welkom sluiten tijdens de wachtwoordvraag: eerst afwachten, dan dicht")

# ========================== U208: een tweede start brengt het open venster naar voren (geen tweede venster) ===
_meer = os.environ.pop("BUGOS_MEERDERE", None)
from PySide6.QtWidgets import QWidget as _QW  # noqa: E402


class _Vak(_QW):
    def __init__(self):
        super().__init__()
        self.gekregen = []

    def tweede_start(self, args):
        self.gekregen.append(args)


_rt = TMP / "run-user"
_rt.mkdir(mode=0o700)
os.environ["XDG_RUNTIME_DIR"] = str(_rt)


def _tweede(naam, args, token=""):
    """Een echte tweede start (eigen proces): die wacht op 'ok' van het open venster."""
    import json as _js
    code = ("import sys, os, json; sys.path.insert(0, sys.argv[1]); os.environ['QT_QPA_PLATFORM']='offscreen'\n"
            "from PySide6.QtCore import QCoreApplication; a = QCoreApplication([])\n"
            "import bugos_ui; print(bugos_ui.al_open(sys.argv[2], json.loads(sys.argv[3])))")
    omg = dict(os.environ, XDG_ACTIVATION_TOKEN=token)
    p = _sp.Popen([sys.executable, "-c", code, str(ROOT / "system_files/usr/lib/bugos/python"), naam, _js.dumps(args)],
                  stdout=_sp.PIPE, text=True, env=omg)
    wacht(lambda: p.poll() is not None, 15000)
    return p.communicate()[0].strip() == "True"


_vak = _Vak()
bugos_ui.luister("test-u208", _vak)
_vak.show()
_vak.showMaximized()
wacht(lambda: False, 100)
_al = _tweede("test-u208", ["wifi"], token="tok-123")
_niet = _tweede("test-u208-niet-open", ["x"])
klopt(_al and _vak.gekregen == [["wifi"]] and not _niet,
      f"U208: een tweede start geeft de opdracht aan het open venster en stopt zelf ({_vak.gekregen})")
klopt(bool(_vak.windowState() & Qt.WindowState.WindowMaximized),
      f"U217: een tweede start laat een gemaximaliseerd venster gemaximaliseerd ({_vak.windowState()})")
klopt(os.environ.get("XDG_ACTIVATION_TOKEN") == "tok-123",
      "U218: het startbewijs van Plasma gaat mee, zodat het venster op Wayland echt naar voren komt")
os.environ.pop("XDG_ACTIVATION_TOKEN", None)
_vak.showMinimized()
wacht(lambda: False, 100)
_tweede("test-u208", [])
klopt(not (_vak.windowState() & Qt.WindowState.WindowMinimized) and _vak.isVisible(),
      "U217: een geminimaliseerd venster komt bij een tweede start weer tevoorschijn")
klopt(bugos_ui._een_naam("x").startswith(str(_rt) + "/"),
      f"U219: het adres staat in je eigen runtime-map, niet in de gedeelde /tmp ({bugos_ui._een_naam('x')})")
# U220: luistert er iets dat geen 'ok' zegt (vastgelopen, of net aan het afsluiten)? Dan gewoon zelf starten.
from PySide6.QtNetwork import QLocalServer as _QLS  # noqa: E402

_stom = _QLS()
_stom.listen(bugos_ui._een_naam("test-u220"))
klopt(not _tweede("test-u220", ["x"]), "U220: een open venster dat niet antwoordt, slikt een nieuwe start niet in")
_stom.close()
klopt("server.close()" in (ROOT / "system_files/usr/lib/bugos/python/bugos_ui.py").read_text().split("def uitvoeren")[1],
      "U220: na het sluiten luistert het programma niet meer (een start dan geeft een nieuw venster)")
# U221: weer openen terwijl het venster wacht om na een klus dicht te gaan: dan blijft het open.
_vak.sluit_na = True
_vak.sluit_na_update = True
_tweede("test-u208", [])
klopt(not _vak.sluit_na and not _vak.sluit_na_update,
      "U221: je opent het venster weer: het gaat na de klus niet meer vanzelf dicht")
klopt("self.isVisible()" in (ROOT / "system_files/usr/bin/bugos-help").read_text().split("def closeEvent")[1][:900],
      "U221: Hulp weer geopend tijdens een reparatie: het venster blijft open als de reparatie klaar is")
if _meer is not None:
    os.environ["BUGOS_MEERDERE"] = _meer
_vak.deleteLater()
# U222: de Winkel was al open; 'Uit de Winkel halen?' na een .exe gaat naar die app, en Taakbeheer naar de pagina.
_ww2 = winkel.Winkel(cat)
_ww2.tweede_start(["appstream://org.mozilla.firefox"])
_z1 = _ww2.zoek.text()
_ww2.tweede_start(["--zoek", "foto", "bewerken"])
_z2 = _ww2.zoek.text()
gestart.clear()
_ww2.tweede_start(["appstream://org.example.NietBijOns"])
# U330: 'appstream:id' zonder // en een id in kleine letters (zo geeft KDE het soms door) vinden toch de app.
_ww2.tweede_start(["appstream:org.videolan.vlc"])
klopt(_ww2.zoek.text() == "VLC" and winkel.begin_uit(["appstream:org.videolan.VLC"]) == ("", "org.videolan.VLC"),
      f"U330: een Flathub-link zonder // of in kleine letters vindt toch de app in de Winkel ({_ww2.zoek.text()!r})")
klopt(_z1 == "Firefox" and _z2 == "foto bewerken" and gestart == [("plasma-discover", "appstream://org.example.NietBijOns")],
      f"U222: een tweede start van de Winkel gaat naar de gevraagde app of zoekt ({_z1!r}, {_z2!r}, {gestart})")
_ww2.deleteLater()
_tb_tekst = (ROOT / "system_files/usr/bin/bugos-task-manager").read_text()
klopt("def tweede_start" in _tb_tekst and "venster.tweede_start(sys.argv[1:])" in _tb_tekst,
      "U222: Taakbeheer --prestaties gaat ook naar Prestaties als Taakbeheer al open was")
# U234: Back-up gesloten tijdens het tellen en weer geopend: geen valse 'te weinig ruimte'.
import threading as _thr  # noqa: E402


class _NepTeller:
    def __init__(self):
        self.stop = _thr.Event()
        self.stop.set()

    def wait(self):
        return True

    def isRunning(self):  # noqa: N802
        return False


_bw = open_venster(bb)
_bw.teller = _NepTeller()
_bw.sluit_na = False   # weer geopend: luister() zette dit terug
_bw.geteld(SCHIJF, [], False, 5 * 1024**3, 0)
_tk = _bw.melding.tekst.text()
klopt("ruimte" not in _tk and "Gestopt" in _tk and _bw.isVisible(),
      f"U234: tellen gestopt en Back-up weer geopend: geen valse 'te weinig ruimte' ({_tk!r})")
_bw.teller = None
_bw.close()
# U233: weer geopend tijdens het kopiëren: de melding belooft niet meer dat het venster vanzelf dichtgaat.
_teksten = {n: (ROOT / "system_files/usr/bin" / n).read_text() for n in ("bugos-backup", "bugos-switch", "bugos-store")}
klopt(all("def tweede_start" in x and "(U233)" in x for x in _teksten.values()),
      "U233: Back-up, Overstap en Winkel vervangen 'gaat vanzelf dicht' als je ze weer opent")
# U268: zoeken met Turkse İ en accenten (ook van een Mac: é als twee tekens) in de Winkel, Instellingen en Bestanden.
import unicodedata as _ud  # noqa: E402

_mac = _ud.normalize("NFD", "café")
klopt(bugos_ui.zoeksleutel("İstanbul tatil.jpg").startswith("istanbul") and bugos_ui.zoeksleutel(_mac) == "cafe"
      and winkel.past({"naam": "Sistem İzleyicisi", "id": "x"}, "izleyici"),
      "U268: 'istanbul' vindt 'İstanbul', 'cafe' vindt 'café' (ook van een Mac), ook in de Winkel")
# U271: zichtbare toetsenbordfocus ook op de keuzeknoppen, achtergronden, het pad in Bestanden en de legenda.
import bugos_files_onderdelen as _fo  # noqa: E402
import bugos_settings_onderdelen as _so  # noqa: E402

_css = _fo.stijl() + _so.stijl()
_zonder = [n for n in ("keus", "plaatje", "kruimel", "legenda") if f"QPushButton#{n}:focus" not in _css]
klopt(not _zonder, f"U271: elke eigen knop laat zien dat hij de toetsenbordfocus heeft (niet: {_zonder})")
# U272: een diep pad past in de balk: lange namen ingekort (de hele naam als tip), de laatste zo heel mogelijk.
from PySide6.QtWidgets import QPushButton as _QPB  # noqa: E402

_diep = THUIS / "Documents" / "Schoolwerk 2024" / "Geschiedenis werkstuk" / "Bronnen en afbeeldingen"
_diep.mkdir(parents=True, exist_ok=True)
_pv = b.Bestanden(_diep)
_pv.resize(1120, 740)
_pv.show()
for _ in range(6):
    wacht(lambda: False, 60)
_kr = [_pv.pad_lay.itemAt(i).widget() for i in range(_pv.pad_lay.count())]
_kr = [k for k in _kr if isinstance(k, _QPB)]
_som = sum(k.sizeHint().width() for k in _kr) + 16 * (len(_kr) - 1)
klopt(_kr and _som <= _pv.pad_vak.width() and "Bronnen" in _kr[-1].text(),
      f"U272: een diep pad past in de balk in Bestanden ({[k.text() for k in _kr]}, {_som} van {_pv.pad_vak.width()} px)")
# U281: een ingekorte map heet voor een schermlezer toch voluit, en '…' zegt welke map hij opent.
_kort = [k for k in _kr if k.text() != k.accessibleName()]
klopt(all(k.accessibleName() and "…" not in k.accessibleName() for k in _kr) and _pv.plek_naam() == "Bronnen en afbeeldingen",
      f"U281: elk stukje van het pad heeft voor een schermlezer de hele naam ({[k.accessibleName() for k in _kr]})")
# U282/U283: 'bezig'-meldingen halen 4,5:1, en de Plasma-schakelaar 'uit' 3:1 (staat in het gemaakte switch.svg).
_bk = bugos_ui.KLEUREN
klopt(all(_contrast(_bk[t]["accent_gekozen"], _bk[t]["accent_zacht"]) >= 4.5 for t in _bk)
      and 'K["accent_gekozen"], K["accent_zacht"], "view-refresh"' in (ROOT / "system_files/usr/lib/bugos/python/bugos_widgets.py").read_text()
      and "A_SCHAKELAAR = 0.45" in (ROOT / "tools/plasma/buttons_draw.py").read_text(),
      "U282/U283: de 'bezig'-melding en de schakelaar 'uit' van Plasma halen genoeg contrast")
_pv.close()
# U274: een schijf in Bestanden > Deze computer is voor een schermlezer een knop (niet 'paneel').
from PySide6.QtGui import QAccessible as _QA  # noqa: E402

_sr = _fo.SchijfRij("usb", "USB-stick", "12 GB vrij")
_sr.show()
_ai = _QA.queryAccessibleInterface(_sr)
klopt(_ai is not None and _ai.role() == _QA.Role.Button and _ai.text(_QA.Text.Name) == "USB-stick",
      f"U274: een schijf in Bestanden is voor een schermlezer een knop met zijn naam ({_ai and _ai.role()})")
_sr.close()
# U275: een Arabische Qt-vertaling draait de BugOS-vensters (Engelse tekst) niet om naar rechts-naar-links.
from PySide6.QtCore import QLibraryInfo as _QLI, QTranslator as _QTr  # noqa: E402

_ar = _QTr()
if _ar.load("qtbase_ar", _QLI.path(_QLI.LibraryPath.TranslationsPath)):
    app.installTranslator(_ar)
    for _ in range(5):
        app.processEvents()
    _richting = app.layoutDirection()
    app.removeTranslator(_ar)
    klopt(_richting == Qt.LayoutDirection.LeftToRight,
          f"U275: met een Arabische Qt-vertaling blijven de BugOS-vensters van links naar rechts ({_richting})")
_stukken = [(n, (ROOT / "system_files/usr/bin" / n).read_text()) for n in
            ("bugos-settings", "bugos-task-manager", "bugos-store", "bugos-welcome", "bugos-backup", "bugos-switch", "bugos-help")]
klopt(all("een_keer=True" in tekst for _n, tekst in _stukken), "U208: Instellingen, Taakbeheer, Winkel, Welkom, Back-up, Overstap en Hulp openen maar één keer")

# ========================== U067: 'Grote letters' maakt ook de letters van de BugOS-apps groter ===
from PySide6.QtGui import QFont  # noqa: E402

_gewoon, _groot = QFont("Inter"), QFont("Inter")
_gewoon.setPointSizeF(10)
_groot.setPointSizeF(12)
klopt(bugos_ui.letter_schaal(_gewoon) == 1.0 and abs(bugos_ui.letter_schaal(_groot) - 1.2) < 1e-9,
      "U067: KDE-letter 10 punt is gewoon, 12 punt (Grote letters) is 1,2 keer zo groot")
_oud_schaal = bugos_ui.SCHAAL
bugos_ui.SCHAAL = 1.2
_blad = bugos_ui._stijlblad(bugos_ui.K)
import bugos_files_onderdelen as _fo  # noqa: E402
import bugos_settings_onderdelen as _so  # noqa: E402
import bugos_tasks_ui as _tu  # noqa: E402

klopt('QLabel[rol="rij"] { font-size: 18px;' in _blad and "font-size: 14px" not in _blad
      and all("font-size: 14px" not in m.stijl() for m in (_fo, _so, _tu)) and bugos_ui.px(13) == 16,
      "U067: met grote letters worden de pixelmaten in de stijlbladen 1,2 keer zo groot")
# U085: vaste vakjes groeien mee: '100%' naast een schuif, de kolom Processor, de bestandstegel.
from PySide6.QtGui import QFontMetrics  # noqa: E402
import bugos_files_tegels as _ft  # noqa: E402

_f = QFont("Inter")
_f.setPixelSize(bugos_ui.px(15))
_f.setWeight(QFont.Weight.DemiBold)
_schuif = _so.Regelaar(50) if hasattr(_so, "Regelaar") else None
_breed = _schuif.getal.width() if _schuif else 0
_kop = QFont("Inter")
_kop.setPixelSize(bugos_ui.px(13))
_kop.setWeight(QFont.Weight.DemiBold)
klopt(_schuif is not None and QFontMetrics(_f).horizontalAdvance("100%") <= _breed
      and QFontMetrics(_kop).horizontalAdvance("Processor") <= bugos_ui.px(_tu.KOLOM_PROCESSOR)
      and _ft.TegelTekenaar.maat().height() == bugos_ui.px(164),
      f"U085: met grote letters past '100%' ({QFontMetrics(_f).horizontalAdvance('100%')} <= {_breed}), 'Processor' en de tegel")
_groot2 = QFont("Inter")
_groot2.setPointSizeF(20)
klopt(bugos_ui.letter_schaal(_groot2) == 1.5, "U085: heel grote KDE-letters: BugOS groeit tot 1,5 keer (daarboven past het niet)")
bugos_ui.SCHAAL = _oud_schaal
klopt('QLabel[rol="rij"] { font-size: 15px;' in bugos_ui._stijlblad(bugos_ui.K), "U067: gewone letters: niets verandert")
_qml = [ROOT / "system_files/usr/share/plasma/plasmoids/org.bugos.startmenu/contents/ui/StartMenu.qml",
        ROOT / "system_files/usr/share/plasma/plasmoids/org.bugos.quickmenu/contents/ui/QuickMenu.qml",
        ROOT / "system_files/usr/share/bugos/logout/Logout.qml"]
_vast = [f"{q.name}:{n}" for q in _qml for n, r in enumerate(q.read_text().splitlines(), 1)
         if "font.pixelSize:" in r and ".schaal" not in r]
klopt(not _vast, f"U067: startmenu, snelmenu en uitzetscherm groeien mee met de letters van KDE ({_vast[:3]})")

print()
shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
