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

# ============================================================= Bestanden ===
import bugos_ui  # noqa: E402

app = bugos_ui.maak_app("bugos-test", "bugos-test", [sys.argv[0]])
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QPushButton  # noqa: E402

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
    klopt("dolphin" not in _tekst.lower() and "partitionmanager" not in _tekst and "subprocess.Popen" not in _tekst,
          f"Bestanden: {_bestand} start geen Dolphin of Schijfbeheer (en noemt ze niet)")
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
import json as _json  # noqa: E402

_lsblk = TMP / "lsblk.json"
_d_schijf = TMP / "oude-d"
_d_schijf.mkdir()
_win = TMP / "windows-c"
(_win / "Windows" / "System32").mkdir(parents=True)
_BASIS = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"   # 'gewone gegevens' (Microsoft basic data)
_lsblk.write_text(_json.dumps({"blockdevices": [
    {"name": "sdb", "kname": "sdb", "path": "/dev/sdb", "type": "disk", "size": 500107862016, "rm": False,
     "hotplug": False, "tran": "sata", "children": [
         {"name": "sdb1", "kname": "sdb1", "path": "/dev/sdb1", "type": "part", "size": 500106813440, "fstype": "ntfs",
          "label": "Data", "parttype": _BASIS, "fsavail": 400000000000, "fssize": 500106813440,
          "mountpoints": [str(_d_schijf)]}]},
    {"name": "nvme0n1", "kname": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "size": 256060514304, "rm": False,
     "hotplug": False, "tran": "nvme", "children": [
         {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "type": "part", "size": 104857600, "fstype": "vfat",
          "parttype": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "mountpoints": [None]},
         {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part", "size": 16777216, "fstype": None,
          "parttype": "e3c9e316-0b5c-4db8-817d-f92df00215ae", "mountpoints": [None]},
         {"name": "nvme0n1p3", "kname": "nvme0n1p3", "path": "/dev/nvme0n1p3", "type": "part", "size": 255000000000,
          "fstype": "ntfs", "label": "Windows", "parttype": _BASIS, "fsavail": 100000000000, "fssize": 255000000000,
          "mountpoints": [str(_win)]}]}]}))
os.environ["BUGOS_LSBLK"] = str(_lsblk)
import bugos_files_schijven as bfs  # noqa: E402

venster.vul_zijbalk()
_d = next((x for x in venster.lijst_schijven if x.naam == "Data"), None)
_w = next((x for x in venster.lijst_schijven if x.naam == "Windows"), None)
klopt(_d is not None and _w is not None and bfs.wisbare_interne_schijf(_d) and not bfs.wisbare_interne_schijf(_w),
      "review 8: de dataschijf (D:) mag gewist worden, de schijf waar Windows van opstart niet")
klopt("Leegmaken (alles wissen)…" in [a.text() for a in venster.schijf_menu(_d).actions()]
      and "Leegmaken (alles wissen)…" not in [a.text() for a in venster.schijf_menu(_w).actions()],
      "review 8: alleen de dataschijf heeft 'Leegmaken (alles wissen)…' in zijn menu")
_gezien.clear()
_beheerd: list = []
_echt_beheer = venster.beheer
venster.beheer = lambda x, stappen, *a, **k: _beheerd.append((x.station, [" ".join(st) for st in stappen]))
bugos_shell.VraagDialoog.exec = lambda self: (_gezien.append(self), QDialog.DialogCode.Rejected)[1]
venster.wis_interne_schijf(_d)
klopt(not _beheerd and _gezien and "500 GB" in _gezien[-1].uitleg.text() and "'Data'" in _gezien[-1].uitleg.text()
      and _gezien[-1].standaard == "Annuleren",
      "review 8: wissen vraagt eerst, met de naam en de grootte; Enter = Annuleren; Annuleren wist niets")
bugos_shell.VraagDialoog.exec = lambda self: QDialog.DialogCode.Accepted
venster.wis_interne_schijf(_w)
venster.wis_interne_schijf(_d)
bugos_shell.VraagDialoog.exec = _echt_exec
venster.beheer = _echt_beheer
_st = _beheerd[0][1] if _beheerd else []
klopt(len(_beheerd) == 1 and _beheerd[0][0] == "/dev/sdb" and _st[0].startswith("udisksctl unmount -b /dev/sdb1")
      and "block_devices/sdb --method org.freedesktop.UDisks2.Block.Format 'gpt'" in _st[1]
      and "'ext4'" in _st[2] and _st[3] == "udisksctl mount -b /dev/sdb1" and not any("nvme" in x for x in _st),
      f"review 8: Alles wissen: eerst dicht, dan nieuwe indeling en ext4 op sdb, nooit op de Windows-schijf ({_st})")
os.environ["BUGOS_LSBLK"] = ""
venster.vul_zijbalk()


# ======================================================= Taakbeheer: gegevens ===
import bugos_tasks as bt  # noqa: E402

MIJN = 4000   # een gewone gebruiker, ook als deze test als root draait (de CI-container) (review 5)
bt.mijn_uid = lambda: MIJN
EIGEN = f"/user.slice/user-{MIJN}.slice/user@{MIJN}.service"


def proces(pid: int, naam: str, groep: str, tijd: int = 10, rss: int = 1000, pss_kb: int = 0, uid: int | None = None,
           start: int = 100, cmdline: list[str] | None = None, kernel: bool = False, staat: str = "S") -> None:
    vlaggen = 0x00200000 if kernel else 0x00400100
    velden = [staat, "1", "0", "0", "0", "-1", str(vlaggen), "0", "0", "0", "0", str(tijd), "0", "0", "0",
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
proces(101, "Isolated Web Co", FF, tijd=50, pss_kb=200000, cmdline=["/usr/lib64/firefox/firefox", "-contentproc"])
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
      and not _regels[300].app,
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

# ================================================================= einde ===
print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
