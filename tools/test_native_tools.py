#!/usr/bin/env python3
"""Test van pakket 'tools': Taakbeheer, Hulp en Bestanden openen geen KDE-programma's meer.

- Hulp: 'Netwerk bekijken', 'Printer toevoegen' en 'Laat zien wat ruimte inneemt' gaan naar BugOS zelf.
- Bestanden: geen 'Openen in Dolphin' en geen 'Schijfbeheer'; wel 'Wat de meeste ruimte inneemt' (telt precies
  zoals 'du -s -x', op de achtergrond, en stopt als je de pagina verlaat), en een interne dataschijf wissen, met
  het bewijs dat dat nooit de schijf van BugOS, de live-stick, een schijf die het systeem gebruikt of een schijf
  met een besturingssysteem raakt, en altijd eerst vraagt.
- Taakbeheer: geen knop 'Systeemmonitor'; wel een eigen pagina Details (alles wat draait, beëindigen met een vraag,
  geforceerd pas na Beëindigen, nooit wat bij BugOS hoort of niet van jou is).
- R13: op een scherm van 1280x800 (100 % met grote letters, en 150 %) schuift niets opzij.

Alles met nep-programma's (ook udisksctl en gdbus), een nep-/proc, nep-/sys, nep-/etc en een nep-thuismap: er wordt
niets gestopt of gewist. De KDE-programma's (plasma-systemmonitor, dolphin, partitionmanager, filelight) staan als
nep-programma op PATH, zodat de test bewijst dat de sprongen weg zijn, ook als die programma's er wel zijn.
Nodig: GNU du (om mee te vergelijken). Draai als gewone gebruiker (zoals de CI): als root is een map met rechten 000
gewoon leesbaar, dan test dat stukje minder.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_tools.py
          (python3 tools/test_native_tools.py --r13 is alleen voor het eigen proces van de R13-ronde)
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
sys.path.insert(0, str(LIB))


def _r13_kind() -> None:
    """Het eigen proces van de R13-ronde (zie _r13_ronde verderop): de omgeving (scherm van 1280x800, schaal, taal,
    voorbeeldstand) komt van de ouder. Bouw Taakbeheer en Bestanden > Deze computer zoals bugos_ui.uitvoeren dat doet
    (passend op het scherm) en druk per pagina af hoeveel hij opzij schuift: 'PAGINA app pagina pixels'."""
    import importlib.machinery as _im
    import importlib.util as _iu

    import bugos_ui
    if os.environ.get("BUGOS_TEST_GROOT"):
        bugos_ui.letter_schaal = lambda _f: 1.5   # zoals KDE 'Grote letters' (net als tools/test_native_layout.py)
    from PySide6.QtCore import QEventLoop, QTimer as _QTimer

    bugos_ui.maak_app("bugos-test", "bugos-test", [sys.argv[0]])

    def wacht(ms: int) -> None:
        lus = QEventLoop()
        _QTimer.singleShot(ms, lus.quit)
        lus.exec()

    def laad_(naam: str, pad: Path):
        lader = _im.SourceFileLoader(naam, str(pad))
        module = _iu.module_from_spec(_iu.spec_from_loader(naam, lader))
        lader.exec_module(module)
        return module

    taken = laad_("tm_r13", ROOT / "system_files" / "usr" / "bin" / "bugos-task-manager").Taakbeheer()
    bugos_ui.pas_in_scherm(taken)
    taken.show()
    wacht(2600)   # één voorbeeldmeting afwachten (dan staan de getallen er, en zijn de kaarten zo breed als echt)
    for pg in ("programmas", "prestaties", "opstarten", "details"):
        taken.ga_naar(pg)
        wacht(150)
        print(f"PAGINA tasks {pg} {taken.paginas[pg].horizontalScrollBar().maximum()}", flush=True)
    taken.draad.stop()
    taken.draad.wait(3000)
    bestanden = laad_("bf_r13", ROOT / "system_files" / "usr" / "bin" / "bugos-files").Bestanden()
    bugos_ui.pas_in_scherm(bestanden)
    bestanden.show()
    bestanden.open_computer()
    wacht(300)
    print(f"PAGINA files computer {bestanden.computer.horizontalScrollBar().maximum()}", flush=True)
    bestanden.meer_knop.click()
    wacht(200)
    print(f"PAGINA files computer-alles {bestanden.computer.horizontalScrollBar().maximum()}", flush=True)
    sys.stdout.flush()
    os._exit(0)   # niet wachten op draadjes die nog lopen


if sys.argv[1:2] == ["--r13"]:
    _r13_kind()

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

# ============================================================= Bestanden ===
import bugos_ui  # noqa: E402

app = bugos_ui.maak_app("bugos-test", "bugos-test", [sys.argv[0]])
from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QDialog, QLabel, QMenu, QPushButton  # noqa: E402

import bugos_shell  # noqa: E402


def verwerk(ms: int = 0) -> None:
    eind = time.monotonic() + ms / 1000
    while True:
        app.processEvents()
        if time.monotonic() >= eind:
            break
        time.sleep(0.01)


def wacht_tot(voorwaarde, seconden: float = 10.0) -> bool:
    eind = time.monotonic() + seconden
    while time.monotonic() < eind:
        app.processEvents()
        if voorwaarde():
            return True
        time.sleep(0.02)
    return voorwaarde()


# Een kleine thuismap (de grote komt verderop bij 'Wat de meeste ruimte inneemt').
for _m in ("Documenten", "Videos", "Downloads"):
    (THUIS / _m).mkdir(parents=True, exist_ok=True)
schrijf(THUIS / ".config" / "user-dirs.dirs",
        'XDG_DOCUMENTS_DIR="$HOME/Documenten"\nXDG_VIDEOS_DIR="$HOME/Videos"\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
(THUIS / "Documenten" / "brief.txt").write_text("hallo")
bf = laad("bestanden", ROOT / "system_files" / "usr" / "bin" / "bugos-files")
sys.modules["bestanden"] = bf
import bugos_files_bewerken as _bew  # noqa: E402
import bugos_files_computer as bfc  # noqa: E402

for _bestand in ("bugos_files_bewerken.py", "bugos_files_computer.py", "bugos_files_schijven.py"):
    _tekst = (LIB / _bestand).read_text(encoding="utf-8")
    # Het enige programma dat deze stukjes zelf starten, is 'flatpak list' (de apps voor iedereen tellen): geen
    # Dolphin, geen Schijfbeheer, geen ander KDE-programma.
    _starts = [s.split("(", 1)[1][:12] for s in _tekst.split("subprocess.Popen")[1:]]
    klopt("dolphin" not in _tekst.lower() and "partitionmanager" not in _tekst
          and all(s.startswith('["flatpak"') for s in _starts),
          f"Bestanden: {_bestand} start geen Dolphin of Schijfbeheer (en noemt ze niet) ({_starts})")
klopt("Dolphin" not in (ROOT / "system_files" / "usr" / "bin" / "bugos-files").read_text(encoding="utf-8"),
      "Bestanden: de uitleg bovenin bugos-files noemt Dolphin niet meer")
_menus: list[list[str]] = []


class _StilMenu(QMenu):
    def exec(self, *_a, **_k):  # noqa: A003
        _menus.append([a.text() for a in self.actions() if a.text()])
        return None


_bew.QMenu = _StilMenu
venster = bf.Bestanden()
venster.show()
venster.ga_naar(THUIS / "Documenten")
klopt(wacht_tot(lambda: venster.sorteer.rowCount(venster.lijst.rootIndex()) == 1, 10),
      "Bestanden: Documenten met brief.txt is geladen")
venster.menu(QPoint(-50, -50))            # buiten elke tegel: lege plek
_idx = venster.sorteer.mapFromSource(venster.model.index(str(THUIS / "Documenten" / "brief.txt")))
venster.menu(venster.lijst.visualRect(_idx).center())   # op het bestand zelf (review 14)
klopt(len(_menus) == 2 and "Nieuwe map" in _menus[0] and "Naar de prullenbak" in _menus[1]
      and not any("Dolphin" in x for m in _menus for x in m) and not hasattr(venster, "in_dolphin"),
      f"F1: rechtermuisknop (lege plek en op een bestand): geen 'Openen in Dolphin' ({_menus})")
_bew.QMenu = QMenu
# De vragen zijn de gedeelde BugOS-vragen: geen QInputDialog of QMessageBox meer (layout-notitie).
_gezien: list = []
_echt_exec = bugos_shell.VraagDialoog.exec


def _nep_exec(self):
    _gezien.append(self)
    if self.veld is not None:
        self.veld.setText("Nieuwe brief")
    return QDialog.DialogCode.Accepted


bugos_shell.VraagDialoog.exec = _nep_exec
venster.lijst.setCurrentIndex(_idx)
venster.hernoem()
klopt((THUIS / "Documenten" / "Nieuwe brief.txt").exists() and _gezien and _gezien[-1].ja.text() == "Naam wijzigen"
      and _gezien[-1].veld.text() == "Nieuwe brief",
      "Bestanden: naam wijzigen gaat met de BugOS-vraag (knop 'Naam wijzigen'), de extensie blijft")
_gezien.clear()
klopt(venster.vraag_ja("Prullenbak leegmaken?", "Weg is weg.", "Leegmaken") is True and _gezien
      and _gezien[-1].standaard == "Annuleren", "Bestanden: bij wissen doet Enter uit gewoonte niets (Annuleren)")
bugos_shell.VraagDialoog.exec = _echt_exec
_bron = (LIB / "bugos_files_bewerken.py").read_text(encoding="utf-8")
klopt("QInputDialog" not in _bron and "QMessageBox" not in _bron, "Bestanden: geen QInputDialog of QMessageBox meer")
venster.open_computer()
verwerk(50)
_knoppen = [k.text() for k in venster.computer.widget().findChildren(QPushButton)]
klopt(not any("Schijfbeheer" in x or "Disk management" in x for x in _knoppen),
      f"F2: Deze computer: geen knop 'Schijfbeheer (voor gevorderden)' ({_knoppen})")

# Review 8: een tweede schijf in de computer (de oude D:) kun je in Bestanden zelf wissen; de Windows-schijf nooit.
# Wissen kan niet ongedaan worden, dus hier staat elke 'nee' apart: de schijf van BugOS, de live-stick (als stick én
# als schijf in een virtuele computer), een btrfs over twee schijven (lsblk noemt er maar één), /etc/fstab en
# /etc/crypttab, iets wat ergens anders open staat, een dichte schijf, de opstart-vlag en een ander Linux. Alles met
# een nep-lsblk, een nep-/proc/self/mountinfo, een nep-/sys en een nep-/etc: er wordt niets echt gewist.
import json as _json  # noqa: E402

import bugos_drives as bd  # noqa: E402

_lsblk = TMP / "lsblk.json"
_MEDIA = TMP / "media"   # speelt /run/media/<naam> na (waar udisks een schijf voor jou opent)
_echt_media = bd.MEDIA_WORTELS
bd.MEDIA_WORTELS = ("/run/media/", str(_MEDIA) + "/")
_d_schijf, _win, _ander = _MEDIA / "Data", _MEDIA / "Windows", _MEDIA / "Linux"
for _m in (_d_schijf, _MEDIA / "Boot", _MEDIA / "Wortel", _MEDIA / "Fstab", _MEDIA / "Kluis", _MEDIA / "Ruw",
           _MEDIA / "Kluis2"):
    _m.mkdir(parents=True, exist_ok=True)
(_win / "Windows" / "System32").mkdir(parents=True)
schrijf(_ander / "etc" / "os-release", 'NAME="Een ander Linux"\n')
_BASIS = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"   # 'gewone gegevens' (Microsoft basic data)
_EFI, _MSR = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "e3c9e316-0b5c-4db8-817d-f92df00215ae"
_LINUX = "0fc63daf-8483-4772-8e79-3d69d8477de4"   # 'Linux-bestanden' (gewone gegevens)


def _deel(naam: str, fs: str | None, plek=None, grootte: int = 250_000_000_000, soort: str = _BASIS,
          label: str | None = None, vlag: str | None = None, kinderen: list | None = None, uuid: str = "") -> dict:
    """Een stuk (partitie) zoals lsblk -J het geeft."""
    d = {"name": naam, "kname": naam, "path": f"/dev/{naam}", "type": "part", "size": grootte, "fstype": fs,
         "label": label, "parttype": soort, "uuid": uuid or f"uuid-{naam}", "partuuid": f"pu-{naam}",
         "partflags": vlag, "fsavail": 10**11 if plek else None, "fssize": grootte if plek else None,
         "mountpoints": [str(plek) if plek else None]}
    if kinderen:
        d["children"] = kinderen
    return d


def _schijf(naam: str, kinderen: list, grootte: int = 500_107_862_016, tran: str = "sata", los: bool = False,
            tabel: str = "gpt", fs: str | None = None) -> dict:
    """Een hele schijf zoals lsblk -J het geeft."""
    return {"name": naam, "kname": naam, "path": f"/dev/{naam}", "type": "disk", "size": grootte, "rm": los,
            "hotplug": los, "tran": tran, "pttype": tabel, "ptuuid": f"pt-{naam}", "fstype": fs, "children": kinderen}


def _luks(naam: str, dm: str, plek, label: str) -> dict:
    """Een versleuteld stuk dat open is (slot open, en wat erin staat ook)."""
    return _deel(naam, "crypto_LUKS", kinderen=[
        {"name": f"luks-{naam}", "kname": dm, "path": f"/dev/mapper/luks-{naam}", "type": "crypt", "fstype": "ext4",
         "label": label, "uuid": f"uuid-in-{naam}", "fsavail": 10**11, "fssize": 249 * 10**9,
         "mountpoints": [str(plek)]}])


def _schijven_lijst(d_open: bool = True, d_grootte: int = 500_107_862_016) -> list:
    return [
        # De oude D: (NTFS, open bij jou): die mag.
        _schijf("sdb", [_deel("sdb1", "ntfs", _d_schijf if d_open else None, 500_106_813_440, label="Data")],
                grootte=d_grootte),
        # De Windows-schijf: EFI, 'gereserveerd voor Microsoft', en Windows erop. Nooit.
        _schijf("nvme0n1", [_deel("nvme0n1p1", "vfat", None, 104_857_600, _EFI),
                            _deel("nvme0n1p2", None, None, 16_777_216, _MSR),
                            _deel("nvme0n1p3", "ntfs", _win, 255_000_000_000, label="Windows")],
                grootte=256_060_514_304, tran="nvme"),
        # BugOS zelf: staat niet eens in Bestanden.
        _schijf("nvme1n1", [_deel("nvme1n1p1", "vfat", "/boot/efi", 629_145_600, _EFI),
                            _deel("nvme1n1p2", "ext4", "/boot", 2_147_483_648, _LINUX),
                            _deel("nvme1n1p3", "btrfs", "/sysroot", 500_000_000_000, _LINUX)], tran="nvme"),
        # De live-stick waar BugOS van draait (USB), en dezelfde stick als schijf in een virtuele computer.
        _schijf("sdc", [_deel("sdc1", "iso9660", "/run/initramfs/live", 3_000_000_000, "0x0", label="BugOS-Live"),
                        _deel("sdc2", "vfat", None, 20_000_000, "0xef")], 32_000_000_000, "usb", True, "dos",
                "iso9660"),
        _schijf("sdh", [_deel("sdh1", "iso9660", "/run/initramfs/live", 3_000_000_000, "0x0", label="BugOS-Live"),
                        _deel("sdh2", "vfat", None, 20_000_000, "0xef")], 3_100_000_000, tabel="dos", fs="iso9660"),
        # Het systeem op btrfs over twee schijven: lsblk noemt alleen sdd1 als open, sde1 lijkt een dichte schijf.
        _schijf("sdd", [_deel("sdd1", "btrfs", "/sysroot", soort=_LINUX, uuid="raid-1")]),
        _schijf("sde", [_deel("sde1", "btrfs", None, soort=_LINUX, uuid="raid-1", label="fedora")]),
        # Een oude pc met Linux op de oude indeling: de opstart-vlag staat aan (open bij jou, zonder kenmerken).
        _schijf("sdi", [_deel("sdi1", "ext4", _MEDIA / "Boot", 1_073_741_824, "0x83", vlag="0x80"),
                        _deel("sdi2", "btrfs", _MEDIA / "Wortel", soort="0x83")], tabel="dos"),
        # Een dataschijf die het systeem zelf opent (/etc/fstab, op /mnt/backup).
        _schijf("sdj", [_deel("sdj1", "ext4", "/mnt/backup", soort=_LINUX, label="Backup")]),
        # Open bij jou, maar /etc/fstab noemt hem (UUID) of /etc/crypttab het slot (met hoofdletters).
        _schijf("sdk", [_deel("sdk1", "ext4", _MEDIA / "Fstab", soort=_LINUX, label="Fstab")]),
        _schijf("sdq", [_luks("sdq1", "dm-7", _MEDIA / "Kluis2", "Kluis2")]),
        # Dicht: BugOS kan niet zien wat erop staat.
        _schijf("sdl", [_deel("sdl1", "ext4", None, soort=_LINUX, label="Dicht")]),
        # Een ander Linux, open: herkenbaar aan etc/os-release.
        _schijf("sdm", [_deel("sdm1", "ext4", _ander, soort=_LINUX, label="Linux")]),
        # Versleuteld en open bij jou: die mag (dicht, op slot, dan wissen).
        _schijf("sdn", [_luks("sdn1", "dm-3", _MEDIA / "Kluis", "Kluis")]),
        # Een stuk zonder herkenbaar bestandssysteem naast een open stuk: niet te zien, dus niet.
        _schijf("sdo", [_deel("sdo1", "ext4", _MEDIA / "Ruw", soort=_LINUX, label="Ruw"),
                        _deel("sdo2", None, None, soort=_LINUX)]),
    ]


def _zet_lsblk(lijst: list) -> None:
    _lsblk.write_text(_json.dumps({"blockdevices": lijst}))


_zet_lsblk(_schijven_lijst())
os.environ["BUGOS_LSBLK"] = str(_lsblk)
# Wat het draaiende systeem gebruikt: een nep-/proc (mountinfo, swaps), nep-/sys en nep-/etc.
_PROC2, _SYS2, _ETC2 = TMP / "proc-schijven", TMP / "sys-schijven", TMP / "etc-schijven"
schrijf(_PROC2 / "self" / "mountinfo", "\n".join([
    "30 1 0:31 / / ro,relatime shared:1 - overlay composefs ro",
    "31 30 0:40 / /sysroot rw,relatime shared:2 - btrfs /dev/sdd1 rw,space_cache=v2",
    "32 30 8:33 / /run/initramfs/live ro,relatime shared:3 - iso9660 /dev/sdc1 ro",
    "33 30 8:145 / /mnt/backup rw,relatime shared:4 - ext4 /dev/sdj1 rw",
    f"34 30 8:17 / {_d_schijf} rw,nosuid,nodev shared:5 - ntfs3 /dev/sdb1 rw",
    f"35 30 8:209 / {_MEDIA}/Mijn\\040Schijf rw shared:6 - ext4 /dev/sdz1 rw",
]) + "\n")
schrijf(_PROC2 / "swaps", "Filename\t\tType\t\tSize\tUsed\tPriority\n/dev/sdg2  partition  8388604  0  -2\n"
                          "/dev/zram0  partition  8388604  0  100\n")


def _sys_deel(schijf: str, deel: str, nummer: str = "") -> None:
    """Een stuk in de nep-/sys: devices/.../block/<schijf>/<deel>/partition, class/block/<naam> en dev/block/M:m."""
    m = _SYS2 / "devices" / "pci0" / "block" / schijf / deel
    m.mkdir(parents=True, exist_ok=True)
    (m / "partition").write_text("1\n")
    (_SYS2 / "class" / "block").mkdir(parents=True, exist_ok=True)
    for naam, doel in ((deel, m), (schijf, m.parent)):
        if not (_SYS2 / "class" / "block" / naam).exists():
            (_SYS2 / "class" / "block" / naam).symlink_to(doel)
    if nummer:
        (_SYS2 / "dev" / "block").mkdir(parents=True, exist_ok=True)
        (_SYS2 / "dev" / "block" / nummer).symlink_to(m)


for _s, _p, _n in (("sdb", "sdb1", "8:17"), ("sdc", "sdc1", "8:33"), ("sdd", "sdd1", "8:49"), ("sde", "sde1", "8:65"),
                   ("sdj", "sdj1", "8:145"), ("sdg", "sdg2", "8:98"), ("sdn", "sdn1", "8:209")):
    _sys_deel(_s, _p, _n)
for _lid in ("sdd1", "sde1"):   # de twee leden van de btrfs van het systeem
    schrijf(_SYS2 / "fs" / "btrfs" / "1a2b3c" / "devices" / _lid, "")
schrijf(_ETC2 / "fstab", "UUID=uuid-sdk1  /data  ext4  defaults,nofail  0 2\n# UUID=uuid-sdb1 /oud ntfs 0 0\n")
schrijf(_ETC2 / "crypttab", "luks-kluis2  UUID=UUID-SDQ1  none  discard\n")
_echt_omgeving = {k: os.environ.get(k) for k in ("BUGOS_PROC", "BUGOS_SYS", "BUGOS_ETC")}
os.environ.update(BUGOS_PROC=str(_PROC2), BUGOS_SYS=str(_SYS2), BUGOS_ETC=str(_ETC2))
import bugos_files_schijven as bfs  # noqa: E402

_kp = {k.plek: k for k in bd.koppelingen()}
klopt(_kp.get("/sysroot") is not None and _kp["/sysroot"].soort == "btrfs" and _kp["/sysroot"].bron == "/dev/sdd1"
      and f"{_MEDIA}/Mijn Schijf" in _kp, f"wissen: /proc/self/mountinfo lezen (ook \\040 in een naam) ({sorted(_kp)})")
_in_gebruik = bd.stations_in_gebruik()
klopt(_in_gebruik == {"sdd", "sde", "sdc", "sdj", "sdg"},
      "wissen: het systeem gebruikt sdd (/sysroot), sde (tweede schijf van die btrfs), sdc (de live-stick), sdj "
      f"(/mnt/backup) en sdg (swap); niet wat bij jou open staat (sdb, sdn) ({sorted(_in_gebruik)})")
klopt(bd.fstab_sleutels() >= {"UUID=uuid-sdk1", "UUID=uuid-sdq1"} and "UUID=uuid-sdb1" not in bd.fstab_sleutels(),
      "wissen: /etc/fstab en /etc/crypttab lezen (zonder hoofdletters, zonder wat 'uit' staat met #)")
klopt(bd.fstab_noemt({"path": "/dev/sdk1", "uuid": "AbC-1"}, {"UUID=abc-1"})
      and bd.fstab_noemt({"kname": "dm-9", "path": "/dev/mapper/kluis"}, {"/dev/dm-9"})
      and not bd.fstab_noemt({"path": "/dev/sdk1", "uuid": "abc-2"}, {"UUID=abc-1", "/dev/sdk2"}),
      "wissen: fstab herkent een stuk aan UUID (ook met hoofdletters) en aan zijn apparaat (ook /dev/dm-N)")
# fstab schrijft een spatie als \040 (fstab(5)); mount leest 'LABEL=Mijn\040Data' als het label 'Mijn Data'. Ook met
# aanhalingstekens ('LABEL="Kwoot"'). Zo'n schijf is dus 'van het systeem', ook al staat hij nu open bij jou. Zonder
# die regel in fstab mag dezelfde schijf wel: het 'nee' komt echt van fstab.
_fstab_echt = (_ETC2 / "fstab").read_text(encoding="utf-8")
_spatie = _schijf("sds", [_deel("sds1", "ext4", _MEDIA / "Mijn Data", soort=_LINUX, label="Mijn Data")])
_kwoot = _schijf("sdt", [_deel("sdt1", "ext4", _MEDIA / "Kwoot", soort=_LINUX, label="Kwoot")])
schrijf(_ETC2 / "fstab", "LABEL=Mijn\\040Data  /data  ext4  defaults,nofail  0 2\n"
                         "LABEL='Kwoot'  /kwoot\\040map  ext4  defaults,nofail  0 2\n")
_sl_spatie = bd.fstab_sleutels()
_bez_spatie, _bez_kwoot = bfs._bezwaar(_spatie), bfs._bezwaar(_kwoot)
schrijf(_ETC2 / "fstab", _fstab_echt)
_bez_zonder = (bfs._bezwaar(_spatie), bfs._bezwaar(_kwoot))
klopt("LABEL=mijn data" in _sl_spatie and "LABEL=kwoot" in _sl_spatie and "fstab" in _bez_spatie
      and "fstab" in _bez_kwoot and _bez_zonder == ("", ""),
      f"wissen: fstab met \\040 (een spatie) en met aanhalingstekens herkent het label ('Mijn Data', 'Kwoot'); zonder "
      f"die regels mogen ze ({sorted(_sl_spatie)}, {_bez_spatie!r}, {_bez_kwoot!r}, zonder {_bez_zonder})")
venster.vul_zijbalk()
_stations = {x.station for x in venster.lijst_schijven}
klopt(not _stations & {"/dev/nvme1n1", "/dev/sdc", "/dev/sdh", "/dev/sdd"} and "/dev/sdb" in _stations,
      f"wissen: de schijf van BugOS, de live-stick (ook als schijf) en /sysroot staan niet eens in Bestanden "
      f"({sorted(_stations)})")
_per_station = {}
for _x in venster.lijst_schijven:
    _per_station.setdefault(_x.station, _x)
_d = next((x for x in venster.lijst_schijven if x.naam == "Data"), None)
_w = next((x for x in venster.lijst_schijven if x.naam == "Windows"), None)
klopt(_d is not None and _w is not None and bfs.wisbare_interne_schijf(_d) and not bfs.wisbare_interne_schijf(_w),
      "review 8: de dataschijf (D:) mag gewist worden, de schijf waar Windows van opstart niet")
_waarom = {s: bfs.wis_bezwaar(_per_station[f"/dev/{s}"]) for s in ("sdb", "sdn", "nvme0n1", "sde", "sdi", "sdj", "sdk",
                                                                     "sdq", "sdl", "sdm", "sdo")}
klopt(_waarom["sdb"] == "" and _waarom["sdn"] == "", f"wissen: de oude D: en een open versleutelde schijf mogen ({_waarom})")
klopt("opstart" in _waarom["nvme0n1"] and "gebruik door het systeem" in _waarom["sde"]
      and "opstart-vlag" in _waarom["sdi"] and "gebruik door het systeem" in _waarom["sdj"]
      and "fstab" in _waarom["sdk"] and "fstab" in _waarom["sdq"] and "dicht" in _waarom["sdl"]
      and "besturingssysteem" in _waarom["sdm"] and "dicht" in _waarom["sdo"],
      f"wissen: elke 'nee' om de goede reden (Windows, btrfs-lid, opstart-vlag, /mnt, fstab, crypttab, dicht, ander "
      f"Linux, onleesbaar stuk) ({_waarom})")
# Ook als iemand een schijf die niet in de lijst staat toch probeert (een oude regel, een andere weg): nee.
_geforceerd = {naam: bfs.wis_bezwaar(bd.Schijf(f"/dev/{deel}", naam, "intern", f"/dev/{schijf}", f"/dev/{deel}"))
               for naam, schijf, deel in (("BugOS", "nvme1n1", "nvme1n1p3"), ("live-stick", "sdc", "sdc1"),
                                          ("live-schijf", "sdh", "sdh1"), ("btrfs", "sdd", "sdd1"))}
klopt(all(_geforceerd.values()), f"wissen: de schijf van BugOS, de live-stick en de systeem-btrfs nooit ({_geforceerd})")
_stick = bd.Schijf("/dev/sdc1", "BugOS-Live", "stick", "/dev/sdc", "/dev/sdc1", wortel="/run/initramfs/live",
                   fs="iso9660")
klopt(bfs.los_in_gebruik(_stick)
      and "Leegmaken (alles wissen)…" not in [a.text() for a in venster.schijf_menu(_stick).actions()],
      "wissen: de stick waar BugOS van draait, kun je ook als stick niet leegmaken")
klopt("Leegmaken (alles wissen)…" in [a.text() for a in venster.schijf_menu(_d).actions()]
      and not any("Leegmaken (alles wissen)…" in [a.text() for a in venster.schijf_menu(_per_station[f"/dev/{s}"]).actions()]
                  for s in ("nvme0n1", "sde", "sdi", "sdj", "sdk", "sdl", "sdm", "sdo")),
      "review 8: alleen een schijf die mag, heeft 'Leegmaken (alles wissen)…' in zijn menu")
_gezien.clear()
_beheerd: list = []
_echt_beheer = venster.beheer
venster.beheer = lambda x, stappen, *a, **k: _beheerd.append((x.station, list(stappen)))
bugos_shell.VraagDialoog.exec = lambda self: (_gezien.append(self), QDialog.DialogCode.Rejected)[1]
venster.wis_interne_schijf(_d)
klopt(not _beheerd and _gezien and "500 GB" in _gezien[-1].uitleg.text() and "'Data'" in _gezien[-1].uitleg.text()
      and _gezien[-1].standaard == "Annuleren",
      "review 8: wissen vraagt eerst, met de naam en de grootte; Enter = Annuleren; Annuleren wist niets")
_gezien.clear()
bugos_shell.VraagDialoog.exec = lambda self: (_gezien.append(self), QDialog.DialogCode.Accepted)[1]
for _s in ("nvme0n1", "sde", "sdi", "sdj", "sdk", "sdl", "sdm", "sdo"):
    venster.wis_interne_schijf(_per_station[f"/dev/{_s}"])
klopt(not _beheerd and not _gezien, "wissen: een schijf die niet mag, krijgt niet eens de vraag (en er gebeurt niets)")
venster.wis_interne_schijf(_d)
venster.wis_interne_schijf(_per_station["/dev/sdn"])


def _tekst_van(stappen: list) -> list:
    return ["(controle)" if callable(st) else " ".join(st) for st in stappen]


_st = _tekst_van(_beheerd[0][1]) if _beheerd else []
klopt(len(_beheerd) == 2 and _beheerd[0][0] == "/dev/sdb" and _st[0] == "udisksctl unmount -b /dev/sdb1"
      and _st[1] == "(controle)" and "block_devices/sdb --method org.freedesktop.UDisks2.Block.Format 'gpt'" in _st[2]
      and "'ext4'" in _st[3] and _st[4] == "udisksctl mount -b /dev/sdb1" and not any("nvme" in x for x in _st),
      f"review 8: Alles wissen: eerst dicht, dan de laatste controle, dan nieuwe indeling en ext4 op sdb ({_st})")
_st_n = _tekst_van(_beheerd[1][1]) if len(_beheerd) > 1 else []
klopt(_st_n[:3] == ["udisksctl unmount -b /dev/mapper/luks-sdn1", "udisksctl lock -b /dev/sdn1", "(controle)"]
      and "block_devices/sdn " in _st_n[3], f"wissen: een versleutelde schijf eerst dicht en op slot ({_st_n})")
# De laatste controle (vlak vóór het wissen): zolang er iets open staat, of het een andere schijf is: nee.
_controle = _beheerd[0][1][1] if _beheerd else (lambda: True)
_nog_open = _controle()
_zet_lsblk(_schijven_lijst(d_open=False))
_dicht_ok = _controle()
_zet_lsblk(_schijven_lijst(d_open=False, d_grootte=2_000_398_934_016))   # een andere schijf kreeg de naam /dev/sdb
_andere = _controle()
_zet_lsblk(_schijven_lijst(d_open=False))
schrijf(_ETC2 / "fstab", "UUID=uuid-sdb1  /data  ntfs  defaults  0 0\n")
_fstab_nu = _controle()
schrijf(_ETC2 / "fstab", "UUID=uuid-sdk1  /data  ext4  defaults,nofail  0 2\n")
klopt(_nog_open is False and _dicht_ok is True and _andere is False and _fstab_nu is False,
      f"wissen: de laatste controle zegt alleen ja als alles dicht is en het dezelfde schijf is "
      f"(open {_nog_open}, dicht {_dicht_ok}, andere schijf {_andere}, nu in fstab {_fstab_nu})")
venster.beheer = _echt_beheer

# Van begin tot eind, met het echte draai() (QProcess) en nep-udisksctl en nep-gdbus die opschrijven wat ze moeten
# doen: (a) dichtzetten lukt echt (lsblk ziet hem daarna dicht): dan wissen; (b) udisksctl zegt 'ok' maar lsblk ziet
# hem nog open: dan stopt de laatste controle alles, er komt geen enkele opdracht om te wissen.
_LOG, _NA_DICHT = TMP / "udisks.log", TMP / "lsblk-na-dicht.json"
schrijf(BIN / "udisksctl", '#!/bin/sh\necho "udisksctl $*" >> "$NEP_LOG"\n'
                           'if [ "$1" = unmount ] && [ -n "$NEP_NA_DICHT" ]; then cp "$NEP_NA_DICHT" "$BUGOS_LSBLK"; fi\n'
                           'exit 0\n')
schrijf(BIN / "gdbus", '#!/bin/sh\necho "gdbus $*" >> "$NEP_LOG"\nexit 0\n')
for _p in ("udisksctl", "gdbus"):
    (BIN / _p).chmod(0o755)
_NA_DICHT.write_text(_json.dumps({"blockdevices": _schijven_lijst(d_open=False)}))
_uitkomst = {}
for _geval, _na in (("echt dicht", str(_NA_DICHT)), ("nog open", "")):
    _zet_lsblk(_schijven_lijst())
    venster.vul_zijbalk()
    _d = next((x for x in venster.lijst_schijven if x.naam == "Data"), None)
    _LOG.write_text("")
    os.environ.update(NEP_LOG=str(_LOG), NEP_NA_DICHT=_na)
    venster.wis_interne_schijf(_d)
    wacht_tot(lambda: not venster.bezig, 15)
    _uitkomst[_geval] = (_LOG.read_text().splitlines(), venster.melding.tekst.text())
bugos_shell.VraagDialoog.exec = _echt_exec
_echt_dicht, _nog_open_log = _uitkomst["echt dicht"][0], _uitkomst["nog open"][0]
klopt(len(_echt_dicht) == 4 and _echt_dicht[0] == "udisksctl unmount -b /dev/sdb1" and "Block.Format" in _echt_dicht[1]
      and "CreatePartitionAndFormat" in _echt_dicht[2] and _echt_dicht[3] == "udisksctl mount -b /dev/sdb1"
      and "is leeg" in _uitkomst["echt dicht"][1],
      f"wissen (echt draaien): dicht, controle, wissen, klaarmaken, openen ({_echt_dicht})")
klopt(_nog_open_log == ["udisksctl unmount -b /dev/sdb1"] and "lukte niet" in _uitkomst["nog open"][1],
      f"wissen (echt draaien): staat hij na 'dicht' nog open, dan wordt er niets gewist ({_nog_open_log})")
for _p in ("udisksctl", "gdbus"):
    (BIN / _p).unlink()
for _k, _v in _echt_omgeving.items():
    if _v is None:
        os.environ.pop(_k, None)
    else:
        os.environ[_k] = _v
bd.MEDIA_WORTELS = _echt_media
os.environ["BUGOS_LSBLK"] = ""
venster.vul_zijbalk()

# ===================================== Bestanden: 'Wat de meeste ruimte inneemt' ===
# Echte bytes (een 'sparse' bestand neemt geen ruimte in). Elke telling heeft een eigen stop: een venster sluiten
# stopt alleen zijn eigen telling (vroeger zette dat een gedeelde STOP aan en telde alles daarna 0, review 14).
klopt(wacht_tot(lambda: not getattr(venster, "grootste_bezig", False), 10), "ruimte: de eerste telling is klaar")
MB = 10**6


def vol(pad: Path, grootte: int) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    with open(pad, "wb") as f:
        f.write(b"\1" * grootte)


vol(THUIS / "Videos" / "a.bin", 3 * MB)
vol(THUIS / "Documenten" / "b.txt", 1 * MB)
vol(THUIS / ".var" / "app" / "com.valvesoftware.Steam" / "x", 5 * MB)
schrijf(TMP / "share" / "applications" / "com.valvesoftware.Steam.desktop",
        "[Desktop Entry]\nType=Application\nName=Steam\nIcon=steam\nExec=steam\n")
vol(THUIS / ".var" / "app" / "org.oud.Weggehaald" / "y", 1 * MB)          # app is weg, gegevens niet
vol(THUIS / ".local" / "share" / "Steam" / "y", 2 * MB)
vol(THUIS / ".local" / "share" / "containers" / "z", int(1.5 * MB))
vol(THUIS / ".local" / "share" / "raar-ding" / "q", 1 * MB)
vol(THUIS / ".local" / "share" / "Trash" / "files" / "z", 4 * MB)
vol(THUIS / ".local" / "share" / "flatpak" / "repo" / "a", 2 * MB)
os.link(THUIS / ".local" / "share" / "flatpak" / "repo" / "a", THUIS / ".local" / "share" / "flatpak" / "b")
vol(THUIS / ".cache" / "c", 1 * MB)
vol(THUIS / ".config" / "k", 512 * 1024)
vol(THUIS / "losse.iso", 2 * MB)
vol(THUIS / "NAS" / "film.mkv", 3 * MB)      # een netwerkmap in je thuismap
vol(THUIS / "Games" / "spel.bin", 3 * MB)    # een tweede schijf in je thuismap
os.symlink("/usr", THUIS / "link")
_echt_koppel, _echt_apparaat = bfc._koppelpunten, bfc._apparaat_van
bfc._koppelpunten = lambda: {str(THUIS / "NAS"), "/", "/proc"}
bfc._apparaat_van = lambda p: 999999 if Path(p).name == "Games" else _echt_apparaat(p)
_rijen = bfc.grootste_mappen(THUIS, min_grootte=0)
_per = {(r.soort, r.naam): r for r in _rijen}
_namen_rijen = [(r.soort, r.naam, r.grootte // 1000) for r in _rijen]
klopt(_rijen and _rijen[0].soort == "app" and _rijen[0].naam == "Steam" and 5 * MB <= _rijen[0].grootte < 6 * MB
      and _rijen[0].app_id == "com.valvesoftware.Steam",
      f"ruimte: de grootste eerst: Steam (gegevens van de app in ~/.var/app) ({_namen_rijen[:3]})")
_video = _per.get(("map", "Video's"))
klopt(_video is not None and _video.pad == THUIS / "Videos" and _video.grootte >= 3 * MB,
      "ruimte: Video's is een map-regel met zijn pad (klik = openen)")
klopt(("prullenbak", "Prullenbak") in _per and 4 * MB <= _per[("prullenbak", "Prullenbak")].grootte < 5 * MB
      and not any(r.naam == "Trash" for r in _rijen) and ("losse", "Losse bestanden in Thuis") in _per,
      "ruimte: de prullenbak is één regel (geen 'Trash'-app), losse bestanden in Thuis ook")
klopt(not any("NAS" in r.naam or "Games" in r.naam or r.naam == "link" for r in _rijen)
      and sum(r.grootte for r in _rijen) < 40 * MB,
      f"review 4: een netwerkmap of tweede schijf in je thuismap en een snelkoppeling naar /usr tellen niet mee "
      f"({sum(r.grootte for r in _rijen) // MB} MB)")
_flat = _per.get(("apps", "Apps die alleen voor jou zijn geïnstalleerd"))
klopt(_flat is not None and 2 * MB <= _flat.grootte < 3 * MB,
      f"review 10: een bestand met twee namen (hardlink, zoals in Flatpak) telt één keer ({_flat and _flat.grootte})")
_wees = next((r for r in _rijen if r.app_id == "org.oud.Weggehaald"), None)
klopt(_wees is not None and _wees.soort == "wees" and "niet meer geïnstalleerd" in _wees.uitleg
      and "Winkel" not in _wees.uitleg, "review 3: gegevens van een app die weg is: 'niet meer geïnstalleerd'")
_box = _per.get(("appdata", "Boxen (containers)"))
_overig = _per.get(("overig", "Instellingen en gegevens van apps"))
klopt(_box is not None and "Winkel" not in _box.uitleg and ("appdata", "Steam") in _per
      and not any(r.naam in ("containers", "raar-ding") for r in _rijen)
      and _overig is not None and _overig.grootte >= int(1.5 * MB),
      "review 3: 'containers' heet 'Boxen', Steam (zonder Flatpak) heet Steam; een onbekende map telt bij "
      "'Instellingen en gegevens van apps' (met .config)")
_cache = _per.get(("cache", "Tijdelijke bestanden"))
klopt(_cache is not None and _cache.grootte >= 1 * MB, "ruimte: ~/.cache heet 'Tijdelijke bestanden'")
_rijen2, _ruimte = bfc.tel_thuis(THUIS)
klopt(_ruimte.get("videos", 0) >= 3 * MB and _ruimte.get("documenten", 0) >= 1 * MB
      and 4 * MB <= _ruimte.get("prullenbak", 0) < 5 * MB,
      "review 17: één telling geeft ook de gekleurde balk (Video's, Documenten) en de prullenbak")
klopt(bfc.grootste_mappen(THUIS) == [], "ruimte: met de gewone grens (100 MB) is hier niets groot")
klopt(bfc._koppel_in(THUIS) >= {str(THUIS / "NAS")} and str(THUIS) not in bfc._koppel_in(THUIS),
      "review 4: koppelpunten in je thuismap worden herkend (niet je thuismap zelf)")
bfc._koppelpunten = _echt_koppel
klopt(all(isinstance(x, str) for x in bfc._koppelpunten()), "review 4: /proc/self/mountinfo lezen gaat (of geeft niets)")

# 'Zoals du': alle regels samen zijn precies wat 'du -s -x' over de thuismap zegt (zonder de thuismap zelf). Met alles
# wat het lastig maakt: hardlinks (ook tussen twee regels), snelkoppelingen (naar een bestand, een map, nergens heen,
# en een lange die zelf een blokje inneemt), een leeg 'sparse' bestand, een fifo, een map die je niet mag lezen, de
# prullenbak met zijn briefjes, Flatpak, ~/.var/app, ~/.wine en losse (verborgen) bestanden.
_DU = TMP / "du-thuis"
for _m in ("Documenten/diep/dieper", "Videos", "leeg", ".var/app/org.voorbeeld.App/data", ".local/share/Trash/files",
           ".local/share/Trash/info", ".local/share/flatpak/repo", ".local/state", ".cache/x", ".config",
           ".wine/drive_c", "geheim"):
    (_DU / _m).mkdir(parents=True, exist_ok=True)
vol(_DU / "Documenten" / "a.bin", 300_000)
vol(_DU / "Documenten" / "diep" / "dieper" / "b.bin", 70_001)
vol(_DU / "Videos" / "film.bin", 1 * MB)
os.link(_DU / "Videos" / "film.bin", _DU / "Documenten" / "zelfde-film.bin")   # één bestand in twee regels
vol(_DU / ".local" / "share" / "flatpak" / "repo" / "obj", 200_000)
os.link(_DU / ".local" / "share" / "flatpak" / "repo" / "obj", _DU / ".local" / "share" / "flatpak" / "app-obj")
with open(_DU / "Documenten" / "sparse.img", "wb") as _f:
    _f.truncate(50 * MB)   # 50 MB groot, maar (bijna) leeg: neemt bijna niets in
    _f.seek(10 * MB)
    _f.write(b"x")
os.symlink(_DU / "Documenten" / "a.bin", _DU / "Documenten" / "naar-a")
os.symlink("/usr", _DU / "Documenten" / "naar-usr")
os.symlink("/bestaat/niet", _DU / "Documenten" / "nergens")
os.symlink("/" + "lang/" * 40 + "doel", _DU / "Documenten" / "lang")
os.mkfifo(_DU / "Documenten" / "pijp")
vol(_DU / ".local" / "share" / "Trash" / "files" / "weg.bin", 123_456)
schrijf(_DU / ".local" / "share" / "Trash" / "info" / "weg.bin.trashinfo", "[Trash Info]\nPath=/x\n")
vol(_DU / ".cache" / "x" / "c.bin", 40_000)
vol(_DU / ".config" / "k.conf", 5_000)
vol(_DU / ".local" / "state" / "s", 9_000)
vol(_DU / ".var" / "app" / "org.voorbeeld.App" / "data" / "d.bin", 77_000)
vol(_DU / ".wine" / "drive_c" / "w.exe", 33_000)
vol(_DU / "geheim" / "niet-te-lezen.bin", 64_000)
vol(_DU / "los.txt", 1_234)
vol(_DU / ".verborgen", 2_345)
os.symlink(_DU / "Videos", _DU / "snelkoppeling-naar-videos")
(_DU / "geheim").chmod(0o000)
_xdg_data = os.environ.get("XDG_DATA_HOME", "")
os.environ["XDG_DATA_HOME"] = str(_DU / ".local" / "share")   # de prullenbak van deze thuismap
try:
    _du_rijen, _du_ruimte = bfc.tel_thuis(_DU)
    _du_kapot = ""
except Exception as _e:  # noqa: BLE001  (een map die je niet mag lezen, mag het tellen nooit laten vallen)
    _du_rijen, _du_ruimte, _du_kapot = [], {}, repr(_e)
os.environ["XDG_DATA_HOME"] = _xdg_data


def _du_s(pad: Path) -> int:
    """De echte du (GNU): -s samen, -x op dit apparaat blijven, -B1 in bytes. Zegt du 'Permission denied' (geheim/),
    dan is de uitkomst er toch."""
    uit = subprocess.run(["du", "-s", "-x", "-B1", str(pad)], capture_output=True, text=True)
    return int(uit.stdout.split()[0]) if uit.stdout.split() else -1


_du_totaal = _du_s(_DU) - os.lstat(_DU).st_blocks * 512
(_DU / "geheim").chmod(0o755)
_som = sum(r.grootte for r in _du_rijen)
_du_per = {r.soort: r.grootte for r in _du_rijen}
klopt(shutil.which("du") is not None and not _du_kapot and _som == _du_totaal,
      f"ruimte zoals du: alle regels samen zijn precies 'du -s -x' over de thuismap ({_som} = {_du_totaal}) {_du_kapot}")
klopt(_du_per.get("prullenbak") == _du_s(_DU / ".local" / "share" / "Trash" / "files")
      and _du_per.get("cache") == _du_s(_DU / ".cache"),
      f"ruimte zoals du: ook per regel (prullenbak {_du_per.get('prullenbak')}, tijdelijke bestanden {_du_per.get('cache')})")
klopt(not any(r.naam.startswith("snelkoppeling") for r in _du_rijen)
      and next((r.grootte for r in _du_rijen if r.naam == "Videos"), -1) < 1 * MB,
      "ruimte zoals du: een snelkoppeling naar een map telt als snelkoppeling; de film met twee namen telt één keer")

# Een map buiten je thuismap (Afbeeldingen op een NAS of een tweede schijf) neemt op deze schijf geen ruimte in: niet
# in de balk, en hij wordt niet eens geopend (een NAS die niet antwoordt, liet anders het tellen hangen). Staat hij
# wel op dezelfde schijf, dan telt hij mee.
_nas = TMP / "nas" / "Afbeeldingen"
vol(_nas / "foto.jpg", 1 * MB)
_echt_plekken, _echt_tel_map = bfc.plekken, bfc.tel_map
bfc.plekken = lambda: [(sl, n, ic, (_nas if sl == "afbeeldingen" else p)) for sl, n, ic, p in _echt_plekken()]
_geopend: list = []
bfc.tel_map = lambda p, *a, **k: (_geopend.append(str(p)), _echt_tel_map(p, *a, **k))[1]
bfc._koppelpunten = lambda: {str(TMP / "nas")}
_r_nas = bfc.tel_thuis(THUIS)[1].get("afbeeldingen")
_nas_geopend = [x for x in _geopend if x.startswith(str(TMP / "nas"))]
bfc._koppelpunten = lambda: set()
_r_zelfde = bfc.tel_thuis(THUIS)[1].get("afbeeldingen", 0)
bfc._koppelpunten, bfc.tel_map, bfc.plekken = _echt_koppel, _echt_tel_map, _echt_plekken
klopt(_r_nas == 0 and not _nas_geopend and _r_zelfde >= 1 * MB,
      f"ruimte: Afbeeldingen op een andere schijf of NAS telt niet mee en wordt niet geopend; op dezelfde schijf wel "
      f"({_r_nas}, {_nas_geopend}, {_r_zelfde})")

# Op de achtergrond, en te stoppen. Met een trage telling (elke map 0,4 s): de pagina staat er meteen, het venster
# blijft reageren, en weggaan van de pagina stopt de telling meteen, zonder half lijstje. Terug: opnieuw tellen.
def _traag(p, *a, **k):
    time.sleep(0.4)
    return _echt_tel_map(p, *a, **k)


bfc.tel_map = _traag
v4 = bf.Bestanden()
v4.show()
_t0 = time.monotonic()
v4.open_computer()
_open_duur = time.monotonic() - _t0
_teller = v4.grootste_teller
_tikken: list = []
_tik = QTimer()
_tik.timeout.connect(lambda: _tikken.append(time.monotonic()))
_tik.start(20)
verwerk(400)
_tik.stop()
_bezig_tijdens = bool(v4.grootste_bezig and _teller is not None and _teller.is_alive())
_t1 = time.monotonic()
v4.ga_naar(THUIS)   # de pagina verlaten
_gestopt = _teller is not None and wacht_tot(lambda: not _teller.is_alive(), 3)
_stop_duur = time.monotonic() - _t1
verwerk(50)
klopt(_open_duur < 0.5 and _bezig_tijdens and len(_tikken) >= 8,
      f"ruimte: tellen gaat op de achtergrond: de pagina staat er meteen ({_open_duur:.2f} s), het venster reageert "
      f"({len(_tikken)} tikken in 0,4 s)")
klopt(_gestopt and _stop_duur < 1.5 and _teller.stop.is_set() and v4.grootste is None and not v4.grootste_bezig
      and not v4.tellen_bezig,
      f"ruimte: de pagina verlaten stopt het tellen meteen ({_stop_duur:.2f} s), en er blijft geen half lijstje staan")
bfc.tel_map = _echt_tel_map
v4.open_computer()
_teller2 = v4.grootste_teller
klopt(_teller2 is not None and _teller2 is not _teller and wacht_tot(lambda: v4.grootste is not None, 15)
      and sum(r.grootte for r in v4.grootste[0]) > 10 * MB,
      "ruimte: terug op de pagina telt hij opnieuw, en dan staat de lijst er wel")
# Een venster sluiten stopt zijn eigen telling, en alleen die: daarna telt alles gewoon (geen gedeelde STOP meer).
bfc.tel_map = _traag
v5 = bf.Bestanden()
v5.show()
v5.open_computer()
_teller5 = v5.grootste_teller
v5.close()
_gestopt5 = _teller5 is not None and wacht_tot(lambda: not _teller5.is_alive(), 3)
bfc.tel_map = _echt_tel_map
_na_sluiten = sum(r.grootte for r in bfc.tel_thuis(THUIS)[0])
klopt(_gestopt5 and _teller5.stop.is_set() and _na_sluiten > 10 * MB,
      f"ruimte: een venster sluiten stopt zijn telling; daarna telt een ander gewoon door ({_na_sluiten // MB} MB)")
v4.hide()

# Apps voor iedereen (Flatpak, systeem) en de rest: samen precies wat er in gebruik is (review 2).
klopt(bfc.lees_maat("803.9 MB") == 803_900_000 and bfc.lees_maat("1,2 GB") == 1_200_000_000
      and bfc.lees_maat("12 bytes") == 12 and bfc.lees_maat("onzin") == 0, "review 2: maten van flatpak lezen")
schrijf(BIN / "flatpak", "#!/bin/sh\nprintf 'org.libreoffice.LibreOffice\\t803.9 MB\\norg.kde.Klein\\t12.0 kB\\n'\n")
(BIN / "flatpak").chmod(0o755)
klopt(bfc.systeem_apps() == [("org.libreoffice.LibreOffice", 803_900_000), ("org.kde.Klein", 12_000)],
      f"review 2: de apps voor iedereen en hun grootte ({bfc.systeem_apps()})")
GB = 10**9
_lijst = bfc.ruimte_lijst([bfc.Ruimtegebruik("map", "Video's", "", "film", None, 30 * GB),
                           bfc.Ruimtegebruik("cache", "Tijdelijke bestanden", "", "klok", None, 50 * MB)],
                          100 * GB, [("org.libreoffice.LibreOffice", 20 * GB), ("org.kde.Klein", 12_000)])
_soorten = [(r.soort, r.grootte // GB) for r in _lijst]
klopt(_soorten == [("systeem", 49), ("map", 30), ("systeemapp", 20)]
      and sum(r.grootte for r in _lijst) + 50 * MB == 100 * GB and _lijst[0].naam == "BugOS en apps voor iedereen",
      f"review 2: met 'BugOS en apps voor iedereen' klopt het totaal met wat er in gebruik is ({_soorten})")

# Deze computer zonder iets groots: geen doodlopende weg (review 2).
_gestart_b: list = []
_echt_start_b = bfc.start
bfc.start = lambda *a: (_gestart_b.append(a), True)[1]
venster.grootste, venster.grootste_tijd = None, -1e9
venster.open_computer()
klopt(wacht_tot(lambda: not venster.grootste_bezig and venster.grootste is not None, 10),
      "ruimte: Deze computer telt op de achtergrond")
verwerk(30)
_teksten = [x.text() for x in venster.grootste_kaart.findChildren(QLabel)]
_knop_apps = [k for k in venster.grootste_kop.findChildren(QPushButton) if "Apps verwijderen" in k.text()]
klopt(any(x.startswith("Er staat niets groots in je eigen mappen") for x in _teksten) and _knop_apps,
      f"review 2: niets groots in je eigen mappen: dat staat er, met 'Apps verwijderen die je niet gebruikt' ({_teksten[:2]})")
if _knop_apps:
    _knop_apps[0].click()
klopt(_gestart_b[-1:] == [("bugos-store",)], f"review 2: die knop opent de Winkel ({_gestart_b[-1:]})")
_eerste_actie = [a.text() for a in venster.ruimte_menu().actions() if a.text()]
klopt(_eerste_actie[:1] == ["Zien wat ruimte inneemt"],
      f"ruimte: 'Ruimte maken' begint met 'Zien wat ruimte inneemt' ({_eerste_actie})")

# Voorbeeldstand (voor foto's): vaste regels, 5 eerst, 'Meer tonen' (spec 26, 27).
os.environ["BUGOS_RUIMTE"] = "512000000000,61000000000,38000000000,52000000000,9000000000,14000000000,21000000000"
v2 = bf.Bestanden()
v2.resize(1080, 720)
v2.show()
v2.open_computer()
verwerk(30)
_schijfrijen = len(v2.computer.widget().findChildren(bfc.SchijfRij))
_zichtbaar = [r for r in v2.ruimte_rijen if r.isVisibleTo(v2)]
klopt(len(_zichtbaar) == 5 and _zichtbaar[0].gebruik.naam == "Steam" and v2.meer_knop.isVisibleTo(v2)
      and v2.meer_knop.text() == "Meer tonen (7)",
      f"ruimte: eerst 5 regels, Steam bovenaan, en 'Meer tonen (7)' ({len(_zichtbaar)}, {v2.meer_knop.text()!r})")
v2.meer_knop.click()
verwerk(30)
_alle_rijen = [r.gebruik for r in v2.ruimte_rijen if r.isVisibleTo(v2)]
klopt(len(_alle_rijen) == 12 and v2.meer_knop.text() == "Minder tonen"
      and _alle_rijen[-1].soort in ("systeemapp", "prullenbak") and any(r.soort == "systeem" for r in _alle_rijen),
      f"ruimte: 'Meer tonen' laat alles zien (12), met 'BugOS en apps voor iedereen' ({len(_alle_rijen)})")
klopt(_schijfrijen == 1, f"ruimte: de nieuwe regels zijn geen schijf-regels (test_files telt die) ({_schijfrijen})")
_bron_rij = {r.gebruik.soort: r for r in v2.ruimte_rijen}
klopt(_bron_rij["cache"].focusPolicy() == Qt.FocusPolicy.NoFocus
      and _bron_rij["map"].focusPolicy() == Qt.FocusPolicy.StrongFocus
      and _bron_rij["map"].accessibleName() == _bron_rij["map"].gebruik.naam,
      "ruimte: wat je niet kunt openen, krijgt geen focus; een map wel, met zijn naam voor de schermlezer")
bfc.WINKEL = ROOT / "system_files" / "usr" / "share" / "bugos" / "store.json"
_gestart_b.clear()
next(r for r in v2.ruimte_rijen if r.gebruik.naam == "Steam").geklikt.emit()
v2.open_ruimte(bfc.Ruimtegebruik("systeemapp", "Iets", "", "apps", None, GB, "org.kde.NietInDeWinkel"))
v2.open_ruimte(next(r.gebruik for r in v2.ruimte_rijen if r.gebruik.soort == "systeem"))
klopt(_gestart_b == [("bugos-store", "appstream://com.valvesoftware.Steam"), ("bugos-store",), ("bugos-store",)],
      f"review 2: een app opent in de Winkel; staat hij er niet in, dan de Winkel zelf (nooit Discover) ({_gestart_b})")
_video_rij = next(r for r in v2.ruimte_rijen if r.gebruik.soort == "map" and r.gebruik.naam == "Video's")
_video_rij.geklikt.emit()
verwerk(30)
klopt(v2.huidig == THUIS / "Videos" and not v2.in_computer, "ruimte: klik op Video's opent die map")
bfc.start = _echt_start_b
# Vanuit Hulp (computer:/ruimte): meteen naar de lijst schuiven, ook op een klein scherm (review 9).
sys.argv.append("computer:/ruimte")
v3 = bf.Bestanden()
v3.resize(853, 533)
v3.show()
v3.open_computer()
verwerk(100)
_stand = v3.computer.verticalScrollBar().value()
sys.argv.remove("computer:/ruimte")
klopt(_stand > 0 and v3.computer.verticalScrollBar().maximum() > 0,
      f"review 9: vanuit Hulp schuift Deze computer naar 'Wat de meeste ruimte inneemt' ({_stand})")
v3.resize(1280, 720)
verwerk(80)
_lg = v3.legenda
_drie = (_lg.kolommen, _lg.nodig(3))
_lg.resize(_lg.nodig(3) - 10, _lg.height())
_twee = _lg.kolommen
klopt(_drie[0] == 3 and _twee < 3 and _lg.minimumSizeHint().width() < _drie[1],
      f"Deze computer: past de legenda niet in drie kolommen (150 %, grote letters), dan in minder; de pagina hoeft "
      f"niet opzij te schuiven ({_drie} -> {_twee})")
for _v in (v2, v3):
    _v.hide()
os.environ.pop("BUGOS_RUIMTE", None)
bfc._apparaat_van = _echt_apparaat


# ======================================================= Taakbeheer: gegevens ===
import bugos_tasks as bt  # noqa: E402

MIJN = 4000   # een gewone gebruiker, ook als deze test als root draait (de CI-container) (review 5)
bt.mijn_uid = lambda: MIJN
EIGEN = f"/user.slice/user-{MIJN}.slice/user@{MIJN}.service"


def proces(pid: int, naam: str, groep: str, tijd: int = 10, rss: int = 1000, pss_kb: int = 0, uid: int | None = None,
           start: int = 100, cmdline: list[str] | None = None, kernel: bool = False, staat: str = "S",
           ppid: int = 1) -> None:
    vlaggen = 0x00200000 if kernel else 0x00400100
    velden = [staat, str(ppid), "0", "0", "0", "-1", str(vlaggen), "0", "0", "0", "0", str(tijd), "0", "0", "0",
              "20", "0", "1", "0", str(start), "1000000", str(rss)] + ["0"] * 10
    schrijf(PROC / str(pid) / "stat", f"{pid} ({naam}) " + " ".join(velden) + "\n")
    u = MIJN if uid is None else uid
    schrijf(PROC / str(pid) / "status", f"Name:\t{naam}\nUid:\t{u}\t{u}\t{u}\t{u}\n")
    schrijf(PROC / str(pid) / "cgroup", f"0::{groep}\n")
    if pss_kb:
        schrijf(PROC / str(pid) / "smaps_rollup", f"Pss: {pss_kb} kB\n")
    if cmdline is not None:
        (PROC / str(pid) / "cmdline").write_bytes("\0".join(cmdline).encode() + b"\0")


def processor(bezig: int, rust: int) -> None:
    schrijf(PROC / "stat", f"cpu  {bezig} 0 0 {rust} 0 0 0 0 0 0\ncpu0 1 0 0 1 0 0 0 0 0 0\ncpu1 1 0 0 1 0 0 0 0 0 0\n")


schrijf(PROC / "meminfo", "MemTotal:       16000000 kB\nMemAvailable:    8000000 kB\n")
schrijf(PROC / "diskstats", "")
schrijf(PROC / "net" / "dev", "Inter-|\n face |\n")
schrijf(TMP / "share" / "applications" / "org.mozilla.firefox.desktop",
        "[Desktop Entry]\nType=Application\nName=Firefox\nIcon=firefox\nExec=firefox\n")
FF = f"{EIGEN}/app.slice/app-flatpak-org.mozilla.firefox-1234.scope"
proces(100, "firefox", FF, tijd=100, pss_kb=300000)
proces(101, "Isolated Web Co", FF, tijd=50, pss_kb=200000, cmdline=["/usr/lib64/firefox/firefox", "-contentproc"],
       ppid=100)
proces(200, "plasmashell", f"{EIGEN}/session.slice/plasma-plasmashell.service", pss_kb=150000)
proces(210, "xdg-desktop-por", f"{EIGEN}/session.slice/xdg-desktop-portal-kde.service",
       cmdline=["/usr/libexec/xdg-desktop-portal-kde"])
proces(300, "NetworkManager", "/system.slice/NetworkManager.service", uid=0, rss=5000)
proces(310, "firewalld", "/system.slice/firewalld.service", uid=0,
       cmdline=["/usr/bin/python3", "-sP", "/usr/bin/firewalld"], start=1509)
proces(400, "spotify", f"/user.slice/user-{MIJN + 1}.slice/user@{MIJN + 1}.service/app.slice/app-spotify-9.scope",
       uid=MIJN + 1)
proces(2, "kthreadd", "", kernel=True)
processor(1000, 1000)
_lijst = {p.pid: p for p in bt.processen()}
klopt(_lijst[300].uid == 0 and _lijst[100].uid == MIJN and _lijst[100].start == 100 and _lijst[310].start == 1509
      and _lijst[100].eigen and not _lijst[300].eigen and 2 not in _lijst,
      "Details: processen() leest van wie (Uid:) en de starttijd (veld 22); geen kernel-draadjes")
klopt(bt.volle_naam(210, "xdg-desktop-por") == "xdg-desktop-portal-kde" and bt.volle_naam(310, "firewalld") == "firewalld"
      and bt.volle_naam(101, "Isolated Web Co") == "Isolated Web Co"
      and bt.volle_naam(999, "nergens-te-vind") == "nergens-te-vind",
      "Details: een tot 15 tekens ingekorte naam wordt de volle naam; de rest blijft")
proces(220, "systemd-userwor", f"{EIGEN}/init.scope", cmdline=["systemd-userwork: waiting..."])
_n220 = bt.volle_naam(220, "systemd-userwor")
klopt(_n220 == "systemd-userwork", f"review 13: een herschreven titel geeft alleen de naam ({_n220})")
import shutil as _sh  # noqa: E402

_sh.rmtree(PROC / "220")
klopt(bt.eigenaar_naam(MIJN) == "jij" and bt.eigenaar_naam(0) == "systeem" and bt.eigenaar_naam(4123456) == "4123456"
      and bt.eigenaar_naam(-1) == "?", "Details: van wie: 'jij', 'systeem', of het nummer als er geen naam is")
klopt(not bt.proces_beschermd(_lijst[100]) and bt.proces_beschermd(_lijst[200]) and bt.proces_beschermd(_lijst[300])
      and bt.proces_beschermd(_lijst[400]) and bt.proces_beschermd(_lijst[210]),
      "Details: beschermd: plasmashell, NetworkManager (systeem), een ander account en de portalen; Firefox niet")
meter = bt.Meter()
meter.meet()
proces(100, "firefox", FF, tijd=400, pss_kb=300000)
processor(3000, 3000)
_m = meter.meet()
_regels = {r.pid: r for r in _m["processen"]}
_ff = next(x for x in _m["taken"] if x.soort == "app" and 100 in x.pids)
klopt(set(_regels) == {100, 101, 200, 210, 300, 310, 400} and _regels[101].hoort_bij == _ff.naam == "Firefox"
      and all(0 <= r.processor <= 100 for r in _regels.values()) and _regels[100].processor > 0 and _regels[100].app
      and not _regels[101].app and not _regels[300].app,
      f"Details: de meting geeft elk proces met de taak waar het bij hoort ({sorted(_regels)})")
klopt(_regels[310].hoort_bij == "" and _regels[300].hoort_bij == "Netwerk" and _regels[400].eigenaar == str(MIJN + 1),
      f"review 12: 'Hoort bij' herhaalt de naam niet ({_regels[310].hoort_bij!r}); NetworkManager hoort bij Netwerk")
klopt(bt.zelfde_proces(100, 100), "Details: zelfde_proces: hetzelfde nummer en dezelfde starttijd")
proces(100, "firefox", FF, tijd=400, start=555)
klopt(not bt.zelfde_proces(100, 100) and not bt.zelfde_proces(12345, 100),
      "Details: zelfde_proces: een hergebruikt nummer (andere starttijd) of een verdwenen proces is niet hetzelfde")
proces(100, "firefox", FF, tijd=400, staat="Z")
klopt(not bt.zelfde_proces(100, 100), "review 15: een zombie (Z) is al gestopt")
proces(100, "firefox", FF, tijd=400, pss_kb=300000)
_gestuurd: list = []
_echt_kill = bt.os.kill


def _nep_kill(pid, sig):
    _gestuurd.append((pid, sig))


bt.os.kill = _nep_kill
_r = _regels[100]
klopt(bt.beeindig(_r) == "klaar" and _gestuurd[-1:] == [(100, signal.SIGTERM)], "Details: Beëindigen stuurt TERM")
klopt(bt.beeindig(_r, hard=True) == "klaar" and _gestuurd[-1:] == [(100, signal.SIGKILL)],
      "Details: Geforceerd beëindigen stuurt KILL")
_voor = len(_gestuurd)
klopt(bt.beeindig(_regels[200]) == "beschermd" and len(_gestuurd) == _voor,
      "Details: een beschermd proces: niets gestuurd")
proces(100, "firefox", FF, tijd=400, start=555)
klopt(bt.beeindig(_r) == "weg" and len(_gestuurd) == _voor, "Details: een hergebruikt nummer: 'weg', niets gestuurd")
proces(100, "firefox", FF, tijd=400, pss_kb=300000)


def _nee(pid, sig):
    raise PermissionError(1, "Operation not permitted")


bt.os.kill = _nee
klopt(bt.beeindig(_r) == "mag_niet", "Details: niet toegestaan (EPERM) -> 'mag_niet'")


def _weg(pid, sig):
    raise ProcessLookupError(3, "No such process")


bt.os.kill = _weg
klopt(bt.beeindig(_r) == "weg", "Details: net verdwenen (ESRCH) -> 'weg'")
bt.os.kill = _nep_kill   # vanaf hier stuurt niets in deze test een echt signaal (ook niet als root) (review 5)


# ======================================================= Taakbeheer: venster ===
proces(100, "firefox", FF, tijd=400, pss_kb=300000)
tm = laad("bugos_task_manager", ROOT / "system_files" / "usr" / "bin" / "bugos-task-manager")
import bugos_tasks_ui as tbu  # noqa: E402

klopt("plasma-systemmonitor" not in (ROOT / "system_files" / "usr" / "bin" / "bugos-task-manager").read_text(
    encoding="utf-8"), "T1: bugos-task-manager noemt plasma-systemmonitor niet meer")
_echt_meetdraad_start = tbu.Meetdraad.start
tbu.Meetdraad.start = lambda self: None   # niet zelf meten: de test geeft de metingen
tv = tm.Taakbeheer()
_venster_vensters: list = []
tv.sluit_vensters = lambda pids: (_venster_vensters.append(list(pids)), True)[1]   # nooit echt KWin vragen
tv.resize(1080, 720)
tv.show()
verwerk(50)
klopt(not any("Systeemmonitor" in k.text() or "System Monitor" in k.text() for k in tv.findChildren(QPushButton))
      and "details" in tv.paginas,
      "T1: geen knop 'Systeemmonitor' (ook al bestaat plasma-systemmonitor), wel een pagina Details")
_meter = bt.Meter()
_meter.meet()
processor(5000, 5000)
_m1 = _meter.meet()
tv.nieuwe_meting(_m1)
tv.tweede_start(["--details"])
verwerk(50)
klopt(tv.huidige() == "details" and tv.proces_model.rowCount() == 7 and tv.details_aantal.text() == "7 processen",
      f"Details: --details opent de pagina; 7 processen ({tv.proces_model.rowCount()}, {tv.details_aantal.text()!r})")


def zichtbare_pids() -> list[int]:
    f = tv.proces_filter
    return [f.index(i, 0).data(tbu.REGEL_ROL).pid for i in range(f.rowCount())]


tv.details_zoek.setText("isol")
_isol = zichtbare_pids()
tv.details_zoek.setText("3")
_drie = sorted(zichtbare_pids())
tv.details_zoek.setText("firefox")
_ff_pids = sorted(zichtbare_pids())
tv.details_zoek.setText("nergens")
_niets = (zichtbare_pids(), tv.details_leeg.isVisible(), tv.details_leeg.text())
tv.details_zoek.setText("")
klopt(_isol == [101] and _drie == [300, 310] and _ff_pids == [100, 101] and len(zichtbare_pids()) == 7,
      f"Details: zoeken op naam, op het begin van het nummer en op 'hoort bij' ({_isol}, {_drie}, {_ff_pids})")
klopt(_niets[0] == [] and _niets[1] and _niets[2].startswith("Niets gevonden"),
      f"Details: niets gevonden: dat staat er, met een tip ({_niets[2]!r})")
klopt(tv.details_zoek.placeholderText() == "Zoeken" and "nummer" in tv.details_zoek.toolTip()
      and tv.alleen_eigen.accessibleName() == "Alleen van jou",
      "review 18: kort 'Zoeken' in het vak (de hele uitleg als tip), en het schuifje heeft een naam")
tv.alleen_eigen.setChecked(True)
_eigen = sorted(zichtbare_pids())
_eigen_tekst = tv.details_aantal.text()
tv.alleen_eigen.setChecked(False)
klopt(_eigen == [100, 101, 200, 210] and _eigen_tekst == "4 van 7",
      f"Details: 'Alleen van jou' laat alleen je eigen processen zien ({_eigen}, {_eigen_tekst!r})")
tv.tabel.sortByColumn(5, Qt.SortOrder.DescendingOrder)
_eerste = tv.proces_filter.index(0, 0).data(tbu.REGEL_ROL)
klopt(_eerste.geheugen == max(r.geheugen for r in tv.proces_model.regels),
      f"Details: sorteren op Geheugen: de grootste bovenaan ({_eerste.naam})")
tv.tabel.sortByColumn(0, Qt.SortOrder.AscendingOrder)
_namen = [tv.proces_filter.index(i, 0).data() for i in range(tv.proces_filter.rowCount())]
klopt(_namen == sorted(_namen, key=str.lower), f"Details: op naam, zonder op hoofdletters te letten ({_namen[:3]})")


def kies_pid(pid: int) -> None:
    f = tv.proces_filter
    for i in range(f.rowCount()):
        if f.index(i, 0).data(tbu.REGEL_ROL).pid == pid:
            tv.tabel.setCurrentIndex(f.index(i, 0))
            break
    verwerk(20)


kies_pid(200)
_knoppen = tv.details_balk.knoppen
klopt(tv.details_balk.isVisible() and not _knoppen["beeindigen"].isEnabled() and not _knoppen["forceren"].isEnabled()
      and "hoort bij BugOS" in _knoppen["beeindigen"].toolTip(),
      "Details: plasmashell gekozen: de balk, maar beide knoppen grijs met de reden als tip")
kies_pid(400)
klopt(not _knoppen["beeindigen"].isEnabled() and "niet van jou" in _knoppen["forceren"].toolTip(),
      "Details: een proces van een ander account: grijs, 'Dit is niet van jou'")
kies_pid(100)
klopt(_knoppen["beeindigen"].isEnabled() and not _knoppen["forceren"].isEnabled()
      and "eerst Beëindigen" in _knoppen["forceren"].toolTip() and tv.gekozen_regel().pid == 100
      and tv.details_balk.aantal.text() == "firefox",
      "Details: Firefox gekozen: Beëindigen werkt; Geforceerd beëindigen pas na Beëindigen (grijs, met de reden als tip)")
# Geforceerd zonder eerst Beëindigen (een andere weg dan de knop): geen vraag, en er wordt niets gestuurd.
_vooraf: list = []
bugos_shell.VraagDialoog.exec = lambda self: (_vooraf.append(self), QDialog.DialogCode.Accepted)[1]
_echt_beeindig_vooraf = tm.bt.beeindig
tm.bt.beeindig = lambda regel, hard=False: (_vooraf.append((regel.pid, hard)), "klaar")[1]
tv.beeindig_gekozen(hard=True)
tv.beeindig_regel(tv.gekozen_regel(), hard=True)
verwerk(50)
tm.bt.beeindig = _echt_beeindig_vooraf
bugos_shell.VraagDialoog.exec = _echt_exec
klopt(not _vooraf, f"Details: Geforceerd beëindigen kan niet vóór Beëindigen, ook niet via een andere weg ({_vooraf})")
# In-place bijwerken: 101 gekozen, dan is 100 weg en 120 nieuw: 101 blijft gekozen, geen modelReset (review/spec 14).
kies_pid(101)
_resets: list = []
tv.proces_model.modelReset.connect(lambda: _resets.append(1))
_sh.rmtree(PROC / "100")
proces(120, "firefox", FF, tijd=10, pss_kb=1000)
processor(7000, 7000)
tv.nieuwe_meting(_meter.meet())
verwerk(30)
_pids = {r.pid for r in tv.proces_model.regels}
klopt(tv.gekozen_regel() is not None and tv.gekozen_regel().pid == 101 and 120 in _pids and 100 not in _pids
      and not _resets, f"Details: bijwerken op zijn plek: je keuze blijft staan ({sorted(_pids)}, resets {_resets})")
# Het gekozen proces verdwijnt: de balk gaat weg.
kies_pid(120)
_sh.rmtree(PROC / "120")
processor(8000, 8000)
tv.nieuwe_meting(_meter.meet())
verwerk(30)
klopt(tv.gekozen_regel() is None and tv.details_balk.isHidden(), "Details: het gekozen proces is weg: de balk ook")
proces(100, "firefox", FF, tijd=400, pss_kb=300000)
processor(9000, 9000)
tv.nieuwe_meting(_meter.meet())
verwerk(20)

# Beëindigen vraagt eerst (review 1). Annuleren: niets; Delete op de tabel: dezelfde vraag.
_vragen: list = []
_antwoord = [QDialog.DialogCode.Rejected]


def _vraag_exec(self):
    _vragen.append(self)
    return _antwoord[0]


bugos_shell.VraagDialoog.exec = _vraag_exec
_beeindigd: list = []
_echt_beeindig = tm.bt.beeindig
tm.bt.beeindig = lambda regel, hard=False: (_beeindigd.append((regel.pid, hard)), "klaar")[1]
kies_pid(101)
tv.beeindig_gekozen()
klopt(len(_vragen) == 1 and _vragen[0].kop.text() == "Isolated Web Co beëindigen?" and _vragen[0].standaard == "Annuleren"
      and "opgeslagen" in _vragen[0].uitleg.text() and not _beeindigd,
      "review 1: Beëindigen vraagt eerst (werk kan verloren gaan; Enter = Annuleren); Annuleren doet niets")
from PySide6.QtGui import QKeySequence, QShortcut  # noqa: E402

# (Offscreen is geen venster 'actief', dus de toets zelf komt niet aan: kijk naar de sneltoets en druk hem in.)
_del = [sc for sc in tv.tabel.findChildren(QShortcut) if sc.key() == QKeySequence(QKeySequence.StandardKey.Delete)]
if _del:
    _del[0].activated.emit()
verwerk(20)
klopt(len(_del) == 1 and _del[0].context() == Qt.ShortcutContext.WidgetShortcut and len(_vragen) == 2
      and not _beeindigd, f"review 1: Delete op de tabel vraagt ook eerst ({len(_vragen)} vragen)")
_antwoord[0] = QDialog.DialogCode.Accepted
_venster_vensters.clear()
tv.beeindig_gekozen()
klopt(wacht_tot(lambda: _beeindigd == [(101, False)], 5) and "wordt beëindigd" in tv.details.melding.tekst.text()
      and not _venster_vensters,
      f"Details: Beëindigen na 'ja': een stopverzoek voor 101 (geen venster) ({_beeindigd}, {_venster_vensters})")
_beeindigd.clear()
kies_pid(100)
tv.beeindig_gekozen()
klopt(wacht_tot(lambda: _venster_vensters == [[100]], 5) and not _beeindigd,
      f"review 1: Firefox zelf (heeft vensters) eerst netjes sluiten, zoals op het kruisje ({_venster_vensters}, {_beeindigd})")
kies_pid(100)
klopt(_knoppen["forceren"].isEnabled() and _knoppen["beeindigen"].isEnabled(),
      "Details: na Beëindigen mag Geforceerd beëindigen (voor precies dit proces)")
tv.beeindig_gekozen(hard=True)
klopt(wacht_tot(lambda: _beeindigd == [(100, True)], 5) and "geforceerd" in _vragen[-1].kop.text(),
      f"Details: Geforceerd beëindigen vraagt ook, en stuurt dan meteen KILL ({_beeindigd})")
klopt(wacht_tot(lambda: "geforceerd beëindigd" in tv.details.melding.tekst.text(), 5),
      f"Details: daarna 'is geforceerd beëindigd' ({tv.details.melding.tekst.text()!r})")
# Na 3 s draait het nog: de melding met 'Geforceerd beëindigen'.
_r101 = next(r for r in tv.proces_model.regels if r.pid == 101)
tv.nog_bezig(_r101, False)
klopt(tv.details.melding.knop.isVisible() and tv.details.melding.knop.text() == "Geforceerd beëindigen"
      and "draait nog" in tv.details.melding.tekst.text(), "Details: draait het na 3 s nog, dan 'Geforceerd beëindigen'")
_beeindigd.clear()
tv.details.melding.knop.click()   # 101 kreeg al Beëindigen: dan mag geforceerd, meteen (KILL)
klopt(wacht_tot(lambda: _beeindigd == [(101, True)], 5),
      f"Details: de knop in die melding beëindigt geforceerd (Beëindigen was al geprobeerd) ({_beeindigd})")
_sh.rmtree(PROC / "101")
tv.nog_bezig(_r101, False)
klopt("is beëindigd" in tv.details.melding.tekst.text(), "Details: is het weg, dan 'is beëindigd'")
# Wat bij BugOS hoort of niet van jou is, beëindigt beeindig_regel nooit (ook niet als iets anders hem aanroept): er
# gaat niets naar bt.beeindig en niets naar KWin.
_beeindigd.clear()
_venster_vensters.clear()
kies_pid(210)
_portaal = tv.gekozen_regel()
tv.beeindig_regel(_portaal, hard=False)
tv.beeindig_regel(_portaal, hard=True)
verwerk(50)
klopt(_portaal is not None and _portaal.beschermd and not _beeindigd and not _venster_vensters
      and "niet beëindigen" in tv.details.melding.tekst.text(),
      f"Details: een beschermd proces (portaal) wordt nooit beëindigd, ook niet via een andere weg ({_beeindigd})")
tm.bt.beeindig = _echt_beeindig
# Hoe het afliep, in gewone woorden. Met een eigen, gewoon proces (niet beschermd, geen venster).
_kate = bt.ProcesRegel(4242, "kate", MIJN, "jij", "", 0.0, 0, True, False, 4242)
for _uitkomst, _woord in (("weg", "draait al niet meer"), ("mag_niet", "niet van jou"), ("fout", "lukte niet")):
    tm.bt.beeindig = lambda regel, hard=False, u=_uitkomst: u
    tv.beeindig_regel(_kate, hard=False)
    klopt(wacht_tot(lambda w=_woord: w in tv.details.melding.tekst.text(), 5),
          f"Details: uitkomst '{_uitkomst}': '{_woord}' in gewone woorden ({tv.details.melding.tekst.text()!r})")
tm.bt.beeindig = _echt_beeindig
bugos_shell.VraagDialoog.exec = _echt_exec
# Escape: eerst de keuze weg, het venster blijft open.
kies_pid(200)
tv.escape()
klopt(tv.gekozen_regel() is None and tv.isVisible(), "Details: Escape haalt eerst je keuze weg (het venster blijft open)")
# Een andere pagina: de balk weg.
kies_pid(210)
tv.ga_naar("programmas")
verwerk(20)
klopt(tv.details_balk.isHidden() and tv.gekozen_regel() is None, "Details: naar een andere pagina: de balk is weg")
tv.ga_naar("details")
verwerk(20)
# Smal venster: 'Hoort bij' gaat weg, breed weer terug (review 14: het venster is echt in beeld).
tv.resize(900, 600)
verwerk(60)
_smal = tv.tabel.isColumnHidden(3)
tv.resize(1400, 800)
verwerk(60)
klopt(_smal and not tv.tabel.isColumnHidden(3) and not tv.tabel.isColumnHidden(2),
      f"Details: smal venster: 'Hoort bij' verborgen; breed: alles te zien (viewport {tv.tabel.viewport().width()})")
# R13: past het niet (150 %, grote letters), dan gaan de kaarten en getallen naar een volgende rij in plaats van dat de
# pagina opzij schuift. Eerst de plooi zelf, met een breedte die net niet past; daarna echt op 1280x800 (hieronder).
tv.ga_naar("programmas")
verwerk(80)
_sp, _mp = tv.samen_plooi, tv.meet_plooi


def _getallen() -> tuple[int, list[bool]]:
    return _sp.kolommen, [b.streep.isVisible() for b in _sp.delen]


_hoog = _sp.height()
_breed = _getallen()
_sp.resize(_sp.nodig(4) - 10, _hoog)
_twee = _getallen()
_sp.resize(_sp.nodig(2) - 10, _hoog)
_een = _getallen()
_sp.resize(_sp.nodig(4) + 40, _hoog)
_weer = _getallen()
klopt(_breed == (4, [False, True, True, True]) and _twee == (2, [False, True, False, True])
      and _een == (1, [False, False, False, False]) and _weer == _breed,
      f"R13: vier getallen op een rij, anders twee rijen van twee (nooit 3 + 1), anders één per rij; een streep alleen "
      f"tussen twee getallen op één rij, ook meteen na het openen ({_breed} -> {_twee} -> {_een} -> {_weer})")
tv.ga_naar("prestaties")
verwerk(80)
_mhoog = _mp.height()
_m = [_mp.kolommen]
for _b in (_mp.nodig(3) - 10, _mp.nodig(2) - 10, _mp.nodig(3) + 40):
    _mp.resize(_b, _mhoog)
    _m.append(_mp.kolommen)
klopt(_m == [3, 2, 1, 3], f"R13: drie kaarten op een rij, anders twee, anders één ({_m})")
tv.resize(1400, 800)
verwerk(60)


def _r13_ronde(schaal: str, groot: bool) -> dict[str, int]:
    """Taakbeheer en Bestanden > Deze computer op een scherm van 1280x800, in een eigen proces (QT_SCALE_FACTOR en
    de lettergrootte kunnen maar één keer per proces): hoeveel schuift elke pagina opzij?"""
    conf = TMP / f"scherm-{schaal}-{int(groot)}.json"
    conf.write_text(_json.dumps({"screens": [{"name": "s", "x": 0, "y": 0, "width": 1280, "height": 800,
                                              "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}))
    thuis_ = TMP / f"r13-thuis-{schaal}-{int(groot)}"
    for m in (".config", "Desktop", "Documents", "Pictures", "Music", "Videos", "Downloads"):
        (thuis_ / m).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(thuis_), XDG_CONFIG_HOME=str(thuis_ / ".config"),
               XDG_DATA_HOME=str(thuis_ / ".local" / "share"), BUGOS_TAKEN_VOORBEELD="1", BUGOS_MEERDERE="1",
               BUGOS_RUIMTE="512000000000,61000000000,38000000000,52000000000,9000000000,14000000000,21000000000",
               BUGOS_LSBLK="", BUGOS_THEMA="licht", BUGOS_LETTERS=str(ROOT / "system_files/usr/share/fonts/bugos"),
               LC_ALL="en_US.UTF-8", LANG="en_US.UTF-8", QT_QPA_PLATFORM=f"offscreen:configfile={conf}",
               QT_SCALE_FACTOR=schaal, BUGOS_TEST_GROOT="1" if groot else "")
    env.pop("LANGUAGE", None)
    uit = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--r13"], env=env, capture_output=True,
                         text=True, timeout=240, cwd=str(TMP))
    pagina = {}
    for regel in uit.stdout.splitlines():
        if regel.startswith("PAGINA "):
            _, app_, pg, schuift = regel.split()
            pagina[f"{app_}/{pg}"] = int(schuift)
    if uit.returncode or len(pagina) != 6:
        pagina["kapot"] = uit.returncode or -1
        print(uit.stderr[-800:])
    return pagina


for _schaal, _groot, _naam in (("1", True, "100 % met grote letters"), ("1.5", False, "150 %")):
    _ronde = _r13_ronde(_schaal, _groot)
    klopt(len(_ronde) == 6 and not any(v > 1 for v in _ronde.values()),
          f"R13: 1280x800 bij {_naam}: Taakbeheer (alle vier pagina's) en Deze computer (met 'Wat de meeste ruimte "
          f"inneemt', ook na 'Meer tonen') schuiven niet opzij ({_ronde})")
tv.ga_naar("details")
verwerk(20)
tv.stop_meten()
tv.close()
verwerk(20)

# Voorbeeldstand (BUGOS_TAKEN_VOORBEELD=1): nooit een echt signaal, ook KWin niets vragen (X1, review 11).
os.environ["BUGOS_TAKEN_VOORBEELD"] = "1"
_signalen: list = []
bt.os.kill = lambda pid, sig: _signalen.append((pid, sig))
_echt_stop = tm.bt.stop
tm.bt.stop = lambda pids, hard=False: (_signalen.append(("stop", tuple(pids))), 0)[1]
_echt_beeindig = tm.bt.beeindig
tm.bt.beeindig = lambda regel, hard=False: (_signalen.append(("beeindig", regel.pid)), "klaar")[1]
tv2 = tm.Taakbeheer()
_kwin: list = []
tv2.sluit_vensters = lambda pids: (_kwin.append(list(pids)), True)[1]
tv2.show()
_vm = tbu.voorbeeld_meting(0)
_vr = _vm["processen"]
tv2.nieuwe_meting(_vm)
tv2.ga_naar("details")
verwerk(30)
klopt(len(_vr) == 17 and len({r.pid for r in _vr}) == 17 and any(r.beschermd and r.uid == 0 for r in _vr)
      and next(r for r in _vr if r.pid == 1).eigenaar == "systeem" and next(r for r in _vr if r.pid == 101).eigen,
      f"Details: de voorbeeldstand heeft 17 processen, met vaste eigenaren (ook als root) ({len(_vr)})")
klopt(next(r for r in _vr if r.pid == 501).hoort_bij == "Bestanden" and next(r for r in _vr if r.pid == 1).hoort_bij == ""
      and next(r for r in _vr if r.pid == 1530).hoort_bij == "Printers",
      "review 7/12: de voorbeeldnamen zijn vertaalbaar (Bestanden/Files), systemd herhaalt zijn naam niet")
_r = next(r for r in _vr if r.pid == 101)
tv2.beeindig_regel(_r, hard=True)
tv2.beeindig_regel(_r, hard=False)
_ff_taak = next(x for x in _vm["taken"] if x.naam == "Firefox")
tv2.sluiten(_ff_taak)
tv2.forceren(_ff_taak)
verwerk(100)
klopt(not _signalen and not _kwin and "geforceerd gesloten" in tv2.programmas.melding.tekst.text(),
      f"X1: voorbeeldstand: Beëindigen, Sluiten en Geforceerd sluiten sturen niets en vragen KWin niets ({_signalen}, {_kwin})")
tv2.stop_meten()
tv2.close()
verwerk(20)
os.environ.pop("BUGOS_TAKEN_VOORBEELD", None)
tm.bt.stop, tm.bt.beeindig = _echt_stop, _echt_beeindig
bt.os.kill = _nep_kill
tbu.Meetdraad.start = _echt_meetdraad_start

# ================================================================= einde ===
print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
