#!/usr/bin/env python3
"""Test van BugOS Back-up (zonder venster): ruimte, back-up maken en terugzetten, met nep-mappen.
Er verandert niets aan je computer: thuis en de USB-schijf zijn tijdelijke mappen.

Gebruik:  python3 tools/test_backup.py   (rsync moet er zijn)
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
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

# 2. een paar bestanden kunnen niet mee (rsync 23): de andere mappen gaan gewoon door
NEP = TMP / "nep-bin"
NEP.mkdir()
(NEP / "rsync").write_text('#!/usr/bin/bash\ncase "$*" in *Documents*) exit 23;; esac\nexec /usr/bin/rsync "$@"\n')
(NEP / "rsync").chmod(0o755)
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"
schrijf(THUIS / "Pictures" / "vakantie.jpg", b"v" * 10)
code = bb.zonder_venster(SCHIJF)
klopt(code == 2 and (doel / "Pictures" / "vakantie.jpg").exists(),
      "deels: Documents lukt niet helemaal, Pictures (erna) wordt toch gekopieerd, met een melding")

lader = importlib.machinery.SourceFileLoader("bugos_overstap",
                                             str(ROOT / "system_files" / "usr" / "bin" / "bugos-switch"))
spec = importlib.util.spec_from_loader("bugos_overstap", lader)
bo = importlib.util.module_from_spec(spec)
lader.exec_module(bo)
bo.gebruikersmap = lambda xdg, standaard: THUIS / "nieuw" / standaard
(THUIS / "nieuw").mkdir()
WIN = TMP / "windows-stick" / "BugOS-Overstap"
schrijf(WIN / "Documents" / "cv.docx", b"c")
schrijf(WIN / "Pictures" / "kat.jpg", b"k")
code = bo.zonder_venster(WIN)
klopt(code == 2 and (THUIS / "nieuw" / "Pictures" / "kat.jpg").exists(),
      "overstap deels: Documents lukt niet helemaal, Pictures wordt toch teruggezet")
schrijf(WIN / "Bladwijzers" / "Edge.json", json.dumps({"roots": {"bar": {"name": "Balk", "children": [
    {"type": "url", "name": "Nieuws", "url": "https://example.org/"}]}}}).encode())
schrijf(WIN / "achtergrond.jpg", b"jpg")
bo.afronden(WIN)
html1 = THUIS / "nieuw" / "Documents" / "Bladwijzers-van-Windows.html"
html1.write_text("mijn eigen aanpassing")
bo.afronden(WIN)
klopt(html1.read_text() == "mijn eigen aanpassing"
      and (THUIS / "nieuw" / "Documents" / "Bladwijzers-van-Windows (2).html").exists()
      and (THUIS / "nieuw" / "Pictures" / "Windows-achtergrond (2).jpg").exists(),
      "overstap: nog een keer doen overschrijft niets (bladwijzers en achtergrond krijgen '(2)')")

# Een stick van de nieuwe Windows-overstap (BugOS-Switch) en een van de oude (BugOS-Overstap,
# van voor de hernoeming): bugos-switch moet ze allebei vinden en de info lezen (A033).
NIEUW_STICK, OUD_STICK = TMP / "stick-nieuw", TMP / "stick-oud"
schrijf(NIEUW_STICK / "BugOS-Switch" / "bugos-switch.json", json.dumps({"computer": "NIEUW"}).encode())
schrijf(OUD_STICK / "BugOS-Overstap" / "bugos-overstap.json", json.dumps({"computer": "OUD"}).encode())
os.environ["BUGOS_SCHIJVEN"] = f"{NIEUW_STICK}:{OUD_STICK}"
gevonden = bo.zoek_overstap()
klopt(sorted(bo.info(m).get("computer", "") for m in gevonden) == ["NIEUW", "OUD"],
      "overstap: vindt de map van de nieuwe (BugOS-Switch) en de oude Windows-versie (BugOS-Overstap)")
del os.environ["BUGOS_SCHIJVEN"]
os.environ["PATH"] = "/usr/bin:/bin"

# 3. terugzetten na opnieuw installeren: de computer heet anders, de oude back-up moet je toch zien
oud = SCHIJF / "BugOS-Backup" / "bugie@oude-laptop"
schrijf(oud / "Documents" / "oud.txt", b"o")
lijst = bb.backups_op(SCHIJF)
klopt(lijst[0] == doel and oud in lijst, "terugzetten: eigen back-up eerst, die van een andere computer staat er ook")
leeg = TMP / "lege-stick"
schrijf(leeg / "BugOS-Backup" / "bugie@oude-laptop" / "Music" / "lied.mp3", b"m")
klopt(bb.backups_op(leeg) == [leeg / "BugOS-Backup" / "bugie@oude-laptop"],
      "terugzetten: alleen een back-up van een andere computer, die wordt gevonden")
klopt(bb.backups_op(TMP / "bestaat-niet") == [], "terugzetten: schijf zonder back-up, geen fout")

# 4. links gaan mee, en elke map komt terug in de echte map (ook als die in een andere taal heet)
(THUIS / "Documents" / "snelkoppeling").symlink_to("brief.txt")
klopt(bb.zonder_venster(SCHIJF) == 0 and (doel / "Documents" / "snelkoppeling").is_symlink(),
      "back-up: een snelkoppeling (symlink) gaat mee")
klopt(json.loads((doel / bb.LIJSTJE).read_text()).get("PICTURES") == "Pictures",
      "back-up: lijstje met welke map welke soort is")
nl = TMP / "nl-stick" / "BugOS-Backup" / "bugie@oud"
schrijf(nl / "Afbeeldingen" / "kat.jpg", b"k")
schrijf(nl / "Eigen map" / "x.txt", b"x")
(nl / bb.LIJSTJE).write_text(json.dumps({"PICTURES": "Afbeeldingen"}))
naar = {Path(c[-2].rstrip("/")).name: c[-1].rstrip("/") for c in bb.terug_opdrachten(nl, THUIS)}
klopt(naar == {"Afbeeldingen": str(THUIS / "Pictures"), "Eigen map": str(THUIS / "Eigen map")},
      "terugzetten: 'Afbeeldingen' gaat naar de afbeeldingenmap van deze computer, een eigen map naar thuis")
oud_stijl = TMP / "oude-stick"
schrijf(oud_stijl / "Music" / "lied.mp3", b"m")
klopt([c[-1].rstrip("/") for c in bb.terug_opdrachten(oud_stijl, THUIS)] == [str(THUIS / "Music")],
      "terugzetten: een back-up zonder lijstje werkt ook (Engelse namen)")

# U078/U079: een stick die eruit is (rsync geeft dan ook 23) en een volle schijf zijn geen "een paar bestanden".
import subprocess  # noqa: E402

_weg = TMP / "stick-eruit" / "Documents"
_naar = TMP / "ergens"
_naar.mkdir()
_r = subprocess.run(["rsync", "-a", f"{_weg}/", f"{_naar}/"], capture_output=True, text=True)
for _mod, _naam in ((bb, "Back-up"), (bo, "Overstap")):
    klopt(_r.returncode == 23 and _mod.uitslag(_r.returncode, ["rsync", "-a", f"{_weg}/", f"{_naar}/"], _r.stderr) == "weg",
          f"U078: {_naam}: bronmap weg (stick eruit) geeft geen 'een paar bestanden konden niet mee'")
    _bron = THUIS
    klopt(_mod.uitslag(11, ["rsync", f"{_bron}/", f"{_naar}/"], "rsync: write failed: No space left on device (28)")
          == "vol" and _mod.uitslag(23, ["rsync", f"{_bron}/", f"{_naar}/"]) == "deels"
          and _mod.uitslag(24, ["rsync", f"{_bron}/", f"{_naar}/"]) == "goed"
          and _mod.uitslag(12, ["rsync", f"{_bron}/", f"{_naar}/"]) == "fout",
          f"U079: {_naam}: een volle schijf heet 'vol', 23 met de bron er nog is 'deels'")

# U409: een stick die alleen gelezen kan worden: rsync geeft 23, maar er ging niets mee (geen 'een paar bestanden').
klopt(bb.uitslag(23, ["rsync", f"{THUIS}/", f"{_naar}/"],
                 'rsync: [receiver] mkstemp "/run/media/x/BugOS-backup/Documents/.a.txt.Xy" failed: Read-only file system (30)')
      == "alleen-lezen" and "ALLEEN_LEZEN if soort" in (ROOT / "system_files/usr/bin/bugos-backup").read_text(),
      "U409: een schijf die alleen gelezen kan worden is geen 'deels', en krijgt een eigen melding")
# U410: de datum bewaren lukt niet (computer vol): geen fout naar boven (het venster bleef dan op 'Niet uittrekken').
_log_oud = bb.LOG
bb.LOG = TMP / "log-is-een-map"
bb.LOG.mkdir()
try:
    bb.onthoud(TMP)
    _u410 = True
except OSError:
    _u410 = False
bb.LOG = _log_oud
klopt(_u410, "U410: lukt het bewaren van de back-updatum niet, dan gaat de back-up toch netjes verder")

# U434: een back-up van een ander account (gedeelde familiestick): de vraag noemt hem en waarschuwt.
_ik = __import__("getpass").getuser()
_v434 = bb.terug_vraag(Path(f"/stick/BugOS-Backup/papa@bugos"))
_eigen434 = bb.terug_vraag(Path(f"/stick/BugOS-Backup/{_ik}@bugos"))
# D-12: de vraag noemt de back-up met een gewone naam ('Back-up van Papa ...'), de waarschuwing de accountnaam.
klopt("Papa" in _v434 and "'papa'" in _v434 and "\n\n" not in _eigen434 and "if lijst[0] != backup_doel(schijf):" in (ROOT / "system_files/usr/bin/bugos-backup").read_text(),
      "U434: terugzetten van andermans back-up: altijd kiezen, met naam en een waarschuwing")

# U442: een mapnaam als '<h1>x' op de stick wordt in de vraag geen opmaak, en de zinnen zijn te vertalen.
from PySide6.QtGui import QTextDocument as _QTD442
_d442 = _QTD442()
_d442.setHtml(bb.terug_vraag(Path("/stick/BugOS-Backup/<h1>papa@bugos")))
klopt("<h1>papa" in _d442.toPlainText() and 't("De bestanden uit \'{naam}\'' in
      (ROOT / "system_files/usr/bin/bugos-backup").read_text(),
      f"U442: de naam van de back-up wordt letterlijk getoond, en de vraag is te vertalen ({_d442.toPlainText()[:60]!r})")

# U444: 'laatste back-up' telt kalenderdagen (gisteren 23:59 is 'gisteren'), en een tijd in de toekomst is 'vandaag'.
import datetime as _dt444
_log444 = bb.LOG
bb.LOG = TMP / "backup444.json"
_gister = _dt444.datetime.combine(_dt444.date.today() - _dt444.timedelta(days=1), _dt444.time(23, 59))
bb.LOG.write_text(json.dumps({"schijf": "/x", "tijd": int(_gister.timestamp())}))
_a444 = bb.laatste_backup()
bb.LOG.write_text(json.dumps({"schijf": "/x", "tijd": int(__import__("time").time()) + 7200}))
_b444 = bb.laatste_backup()
bb.LOG = _log444
klopt(("gisteren" in _a444 or "yesterday" in _a444) and ("vandaag" in _b444 or "today" in _b444),
      f"U444: 'laatste back-up' in kalenderdagen, nooit negatief ({_a444!r}, {_b444!r})")

# U097: het lijstje op de stick bepaalt niet welke opdracht er draait: alleen de vaste soorten tellen.
_gevraagd: list = []
_echt_run = bb.subprocess.run
bb.subprocess.run = lambda cmd, *a, **k: (_gevraagd.append(cmd), _echt_run(["true"], *a, **k))[1] \
    if cmd and cmd[0] == "xdg-user-dir" else _echt_run(cmd, *a, **k)
_stick = TMP / "vreemde-stick"
(_stick / "Fotos").mkdir(parents=True)
(_stick / ".config").mkdir()
(_stick / bb.LIJSTJE).write_text(json.dumps({"ONBEKEND x": "Fotos", "PICTURES": "../weg"}))
_opdr = bb.terug_opdrachten(_stick, THUIS)
(_stick / bb.LIJSTJE).write_text("[1, 2]")
_lijst_ok = isinstance(bb.terug_opdrachten(_stick, THUIS), list)
bb.subprocess.run = _echt_run
klopt(all(c[1] in {x for x, _s in bb.MAPPEN} for c in _gevraagd) and _lijst_ok
      and not any(".config" in " ".join(o) for o in _opdr),
      f"U097: terugzetten vraagt xdg-user-dir alleen naar vaste soorten, slaat verborgen mappen over ({_gevraagd})")

# U211: de back-upmap kan niet gemaakt worden (stick eruit, alleen-lezen): een fout, niet eeuwig 'controleren'.
_bestand = TMP / "geen-map"
_bestand.write_text("x")
_oud_doel = bb.backup_doel
bb.backup_doel = lambda schijf: _bestand / "BugOS-Backup" / "x"
try:
    _code = bb.zonder_venster(TMP)
except OSError:
    _code = "uitzondering"
bb.backup_doel = _oud_doel
klopt(_code == 1, f"U211: de back-upmap kan niet gemaakt worden: een nette fout ({_code})")

# U226: een tweede schijf of de Windows-schijf ín de computer is geen back-upplek (en wordt niet vooraf gekozen).
import bugos_drives as _bd  # noqa: E402

_oud_sch = _bd.schijven
_bd.schijven = lambda *a: [_bd.Schijf(apparaat="/dev/sda2", naam="DATA", soort="intern", station="/dev/sda",
                                      wortel="/run/media/x/DATA"),
                           _bd.Schijf(apparaat="/dev/sdb1", naam="Stick", soort="stick", station="/dev/sdb",
                                      wortel="/run/media/x/Stick")]
_over = bb.zonder_interne([Path("/run/media/x/DATA"), Path("/run/media/x/Stick")], bb.interne_plekken())
_bd.schijven = _oud_sch
klopt(_over == [Path("/run/media/x/Stick")], f"U226: Back-up biedt alleen schijven aan die je eruit haalt ({_over})")
# U231: een oude back-up op een schijf in de computer kun je nog wel terugzetten (maar daar geen nieuwe maken).
_binnen = TMP / "binnen"
(_binnen / "BugOS-Backup" / "x@oud").mkdir(parents=True)
(_binnen / "BugOS-Backup" / "x@oud" / "Documents").mkdir()
_over2 = bb.zonder_interne([_binnen, Path("/run/media/x/Stick")], {str(_binnen)})
bb.LAATSTE_INTERNE.clear()
bb.LAATSTE_INTERNE.add(str(_binnen))
klopt(_over2 == [_binnen, Path("/run/media/x/Stick")] and bb.alleen_terugzetten(_binnen)
      and not bb.alleen_terugzetten(Path("/run/media/x/Stick")),
      f"U231: een oude back-up op een schijf in de computer kun je terugzetten, maar je maakt er geen nieuwe op ({_over2})")
bb.LAATSTE_INTERNE.clear()

# U228: de back-upmap heet naar de vaste computernaam, niet naar wat het netwerk de computer noemt.
import socket as _so  # noqa: E402

_oud_h, _oud_gh = bb.HOSTNAAM, _so.gethostname
_so.gethostname = lambda: "dhcp-10-1-2-3.school.lan"
bb.HOSTNAAM = TMP / "hostname"
bb.HOSTNAAM.write_text("thuis-pc\n")
_d1 = bb.backup_doel(SCHIJF).name
bb.HOSTNAAM = TMP / "geen-hostname"
_d2 = bb.backup_doel(SCHIJF).name
bb.HOSTNAAM, _so.gethostname = _oud_h, _oud_gh
klopt(_d1.endswith("@thuis-pc") and _d2.endswith("@bugos"),
      f"U228: de back-upmap wisselt niet van naam op een ander netwerk ({_d1}, {_d2})")

# U371: terugzetten: heeft de back-up een map met dezelfde naam als een (nieuwer) bestand op de computer, dan blijft dat
# bestand bewaard (met een naam erachter) in plaats van te verdwijnen.
import subprocess as _sp3  # noqa: E402

_bk, _th = TMP / "terug-bk", TMP / "terug-thuis"
(_bk / "Belasting").mkdir(parents=True)
(_bk / "Belasting" / "a.txt").write_text("oud")
_th.mkdir()
(_th / "Belasting").write_text("mijn nieuwe bestand")
_r = _sp3.run(bb.rsync_terug(_bk, _th), capture_output=True, text=True)
_bewaard = [str(p.relative_to(_th)) for p in _th.rglob("*")]
_kopie = [p for p in _th.rglob("Belasting") if p.is_file()]
klopt(_r.returncode == 0 and _kopie and _kopie[0].read_text() == "mijn nieuwe bestand",
      f"U371: terugzetten laat geen bestand van je computer verdwijnen (een map met dezelfde naam) ({_bewaard})")

import re as _re  # noqa: E402

klopt(any(_re.search(r"--backup-dir=.*\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}$", a) for a in bb.rsync_terug(_bk, _th)),
      "U381: de map voor vervangen bestanden heeft ook de tijd: twee keer terugzetten op één dag overschrijft niets")

# D-11: op Fedora is /media een koppeling naar run/media. Dezelfde schijf stond er dan twee keer in (als
# /run/media/test/USBSTICK, 'zit in de computer: alleen terugzetten', en als /media/test/USBSTICK, 'heeft al een
# back-up', waarop je dan wél een back-up kon maken). Na te bootsen met een tijdelijke map en een koppeling.
_ik = __import__("getpass").getuser()
_wortel = TMP / "d11"
(_wortel / "run" / "media" / _ik / "USBSTICK").mkdir(parents=True)
(_wortel / "media").symlink_to("run/media")
_gevonden = bb.schijven_in((_wortel / "run" / "media" / _ik, _wortel / "media" / _ik, _wortel / "media"),
                           is_koppel=lambda p: p.name == "USBSTICK")
klopt(_gevonden == [_wortel / "run" / "media" / _ik / "USBSTICK"],
      f"D-11: een schijf staat er één keer in, ook via de koppeling /media -> run/media ({_gevonden})")
_intern = str(_wortel / "run" / "media" / _ik / "USBSTICK")
_via_media = _wortel / "media" / _ik / "USBSTICK"
bb.LAATSTE_INTERNE.clear()
bb.LAATSTE_INTERNE.add(_intern)
klopt(bb.zonder_interne([_via_media], {_intern}) == [] and bb.alleen_terugzetten(_via_media),
      "D-11: dezelfde schijf in de computer via /media is ook 'in de computer' (geen back-up erop maken)")
bb.LAATSTE_INTERNE.clear()

# D-12: een gewone naam voor de back-up in plaats van 'test@bugos', met de dag en de tijd van de laatste back-up.
import time as _tijd12  # noqa: E402

_jaar = _tijd12.localtime().tm_year
_stip = _tijd12.mktime((_jaar, 11, 16, 13, 20, 0, 0, 0, -1))
_bk12 = TMP / "stick12" / "BugOS-Backup"
_eigen12 = _bk12 / f"{_ik}@{bb.computernaam()}"
_papa12 = _bk12 / "papa@oude-laptop"
for _b in (_eigen12, _papa12):
    (_b / "Documents" / "sub").mkdir(parents=True)
    (_b / bb.LIJSTJE).write_text(json.dumps({"DOCUMENTS": "Documents"}))
    os.utime(_b / bb.LIJSTJE, (_stip, _stip))
_n_eigen, _n_papa = bb.mooie_naam(_eigen12), bb.mooie_naam(_papa12)
_vraag12 = bb.terug_vraag(_eigen12)
klopt(_n_eigen.startswith(("Back-up van ", "Backup of ")) and _n_eigen.endswith(("16 november 13:20", "16 November 13:20"))
      and "@" not in _n_eigen and " op " not in _n_eigen and " on " not in _n_eigen,
      f"D-12: de back-up heet gewoon 'Back-up van <naam>, 16 november 13:20' ({_n_eigen!r})")
klopt(("Papa op oude-laptop" in _n_papa or "Papa on oude-laptop" in _n_papa) and "@" not in _n_papa,
      f"D-12: een back-up van een ander account of een andere computer zegt van wie en welke computer ({_n_papa!r})")
klopt(_n_eigen in _vraag12 and f"'{_eigen12.name}'" not in _vraag12,
      f"D-12: de vraag voor het terugzetten noemt de gewone naam, niet '{_eigen12.name}' ({_vraag12[:70]!r})")

# D-12: één bestand of map terugzetten, op dezelfde plek in je eigen map, nooit iets overschrijven ('naam (2)').
(_eigen12 / "Documents" / "sub" / "brief.txt").write_text("uit de back-up")
(_eigen12 / "Documents" / "los.txt").write_text("los")
schrijf(THUIS / "Documents" / "sub" / "brief.txt", b"mijn nieuwe versie")
_doel_b = bb.een_terug_doel(_eigen12, _eigen12 / "Documents" / "sub" / "brief.txt", THUIS)
_doel_m = bb.een_terug_doel(_eigen12, _eigen12 / "Documents" / "sub", THUIS)
_doel_l = bb.een_terug_doel(_eigen12, _eigen12 / "Documents" / "los.txt", THUIS)
klopt(_doel_b == THUIS / "Documents" / "sub" / "brief (2).txt" and _doel_m == THUIS / "Documents" / "sub (2)"
      and _doel_l == THUIS / "Documents" / "los.txt",
      f"D-12: één ding komt op dezelfde plek terug; staat daar al iets, dan als 'naam (2)' ({_doel_b}, {_doel_m})")
_r1 = _sp3.run(bb.een_terug_opdracht(_eigen12 / "Documents" / "sub" / "brief.txt", _doel_b), capture_output=True)
_r2 = _sp3.run(bb.een_terug_opdracht(_eigen12 / "Documents" / "sub", _doel_m), capture_output=True)
klopt(_r1.returncode == 0 and _r2.returncode == 0 and _doel_b.read_text() == "uit de back-up"
      and (THUIS / "Documents" / "sub" / "brief.txt").read_text() == "mijn nieuwe versie"
      and (_doel_m / "brief.txt").read_text() == "uit de back-up",
      "D-12: het bestand en de map staan terug, en je eigen nieuwere bestand is niet overschreven")
(_eigen12 / "Documents" / "naar-buiten").symlink_to(TMP)
klopt(bb.een_terug_doel(_eigen12, _eigen12, THUIS) is None
      and bb.een_terug_doel(_eigen12, _eigen12 / bb.LIJSTJE, THUIS) is None
      and bb.een_terug_doel(_eigen12, TMP / "thuis", THUIS) is None
      and bb.een_terug_doel(_eigen12, _eigen12 / "Documents" / "naar-buiten", THUIS) is None,
      "D-12: alleen wat echt in een map van de back-up staat (niet de back-up zelf, het lijstje of iets daarbuiten)")
(_eigen12 / "Documents" / "naar-buiten").unlink()

# D-12: het kiesvenster toont de back-up als boom (zonder het lijstje van BugOS) en geeft het gekozen ding terug.
from PySide6.QtCore import QTimer as _QT12  # noqa: E402
from PySide6.QtWidgets import QApplication as _QA12  # noqa: E402

_app12 = _QA12.instance() or _QA12([])
_zag12: dict = {}


def _kies_auto(poging: int = 0) -> None:
    """Wacht tot het venstertje er is en de map geladen is (QFileSystemModel leest op de achtergrond), en kies dan."""
    dlg = _QA12.activeModalWidget()
    if dlg is None or not hasattr(dlg, "boom"):
        if poging < 200:
            _QT12.singleShot(50, lambda: _kies_auto(poging + 1))
        return
    wortel = dlg.boom.rootIndex()
    namen = sorted(dlg.proxy.index(r, 0, wortel).data() for r in range(dlg.proxy.rowCount(wortel)))
    if namen != ["Documents"] and poging < 200:
        _QT12.singleShot(50, lambda: _kies_auto(poging + 1))
        return
    _zag12["namen"] = namen
    dlg.boom.setCurrentIndex(dlg.proxy.mapFromSource(dlg.model.index(str(_eigen12 / "Documents" / "los.txt"))))
    dlg.kies.click()


_QT12.singleShot(0, _kies_auto)
_QT12.singleShot(15000, lambda: _QA12.activeModalWidget() and _QA12.activeModalWidget().reject())
_gekozen12 = bb.kies_in_backup(None, _eigen12)
klopt(_zag12.get("namen") == ["Documents"] and _gekozen12 == _eigen12 / "Documents" / "los.txt",
      f"D-12: 'Eén bestand of map terugzetten' kiest in de back-up, zonder het lijstje van BugOS ({_zag12}, {_gekozen12})")
_bron = (ROOT / "system_files/usr/bin/bugos-backup").read_text(encoding="utf-8")
klopt('t("Eén bestand of map terugzetten"' in _bron and "self.een_terug.clicked.connect(self.zet_een_terug)" in _bron,
      "D-12: het venster heeft de knop 'Eén bestand of map terugzetten'")
_app12.processEvents()   # het venstertje echt opruimen (deleteLater) voor het einde

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
