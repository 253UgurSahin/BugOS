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
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMenu, QPushButton  # noqa: E402

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

# ===================================== Bestanden: 'Wat de meeste ruimte inneemt' ===
# Echte bytes (een 'sparse' bestand neemt geen ruimte in). Sluit hier nooit een Bestanden-venster: dan gaat STOP
# aan en telt alles daarna 0 (review 14).
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
klopt(_knoppen["beeindigen"].isEnabled() and _knoppen["forceren"].isEnabled() and tv.gekozen_regel().pid == 100
      and tv.details_balk.aantal.text() == "firefox", "Details: Firefox gekozen: beide knoppen werken")
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
_sh.rmtree(PROC / "101")
tv.nog_bezig(_r101, False)
klopt("is beëindigd" in tv.details.melding.tekst.text(), "Details: is het weg, dan 'is beëindigd'")
tm.bt.beeindig = _echt_beeindig
for _uitkomst, _woord in (("weg", "draait al niet meer"), ("mag_niet", "niet van jou"), ("fout", "lukte niet")):
    tm.bt.beeindig = lambda regel, hard=False, u=_uitkomst: u
    kies_pid(310 if _uitkomst == "mag_niet" else 210)
    _rg = tv.gekozen_regel()
    tv.beeindig_regel(_rg, hard=True)
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
