#!/usr/bin/env python3
"""Test of BugOS Bestanden veilig met je bestanden omgaat.

Alles gebeurt in een tijdelijke map; je echte bestanden worden niet aangeraakt.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_bestanden.py
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

TMP = Path(tempfile.mkdtemp(prefix="bugos-bestanden-test-"))
os.environ["HOME"] = str(TMP / "thuis")
os.environ["XDG_DATA_HOME"] = str(TMP / "thuis" / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(TMP / "thuis" / ".config")
os.environ["BUGOS_LSBLK"] = ""  # geen echte schijven in de test
os.environ["LC_ALL"] = "nl_NL.UTF-8"  # de test kijkt naar de Nederlandse teksten
(TMP / "thuis" / ".config").mkdir(parents=True)

lader = importlib.machinery.SourceFileLoader("bestanden", str(ROOT / "system_files" / "usr" / "bin" / "bugos-bestanden"))
spec = importlib.util.spec_from_loader("bestanden", lader)
b = importlib.util.module_from_spec(spec)
sys.modules["bestanden"] = b  # nodig voor @dataclass
lader.exec_module(b)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


thuis = TMP / "thuis"
docs = thuis / "Documenten"
docs.mkdir()
(docs / "brief.txt").write_text("hallo oma")
(docs / "map").mkdir()
(docs / "map" / "binnen.txt").write_text("binnenin")

# 1. vrije namen: nooit overschrijven
klopt(b.vrije_naam(docs / "nieuw.txt") == docs / "nieuw.txt", "vrije naam: bestaat niet, blijft gelijk")
klopt(b.vrije_naam(docs / "brief.txt") == docs / "brief (2).txt", "vrije naam: bestaat al, wordt 'brief (2).txt'")
klopt(b.vrije_naam(docs / "map") == docs / "map (2)", "vrije naam: map bestaat al, wordt 'map (2)'")

# 2. naar de prullenbak en weer terug
bestand, info = b.naar_prullenbak(docs / "brief.txt")
klopt(not (docs / "brief.txt").exists(), "prullenbak: bestand is weg uit Documenten")
klopt(bestand.exists() and info.exists(), "prullenbak: bestand en info staan in de prullenbak")
klopt(b.lees_herkomst(info) == docs / "brief.txt", "prullenbak: weet waar het vandaan kwam")
inhoud = b.prullenbak_inhoud()
klopt(len(inhoud) == 1 and inhoud[0][0] == bestand, "prullenbak: inhoud toont het bestand")
terug = b.terugzetten(bestand, info)
klopt(terug == docs / "brief.txt" and terug.read_text() == "hallo oma", "terugzetten: weer op de oude plek, inhoud heel")
klopt(not info.exists(), "terugzetten: info-bestand opgeruimd")

# 3. twee keer hetzelfde weggooien: geen botsing
(docs / "kopie.txt").write_text("een")
b1, i1 = b.naar_prullenbak(docs / "kopie.txt")
(docs / "kopie.txt").write_text("twee")
b2, i2 = b.naar_prullenbak(docs / "kopie.txt")
klopt(b1 != b2 and b1.read_text() == "een" and b2.read_text() == "twee", "prullenbak: twee keer dezelfde naam, allebei bewaard")

# 4. terugzetten als er inmiddels iets anders staat: niets overschrijven
(docs / "kopie.txt").write_text("nieuw")
t1 = b.terugzetten(b1, i1)
klopt((docs / "kopie.txt").read_text() == "nieuw" and t1.read_text() == "een", "terugzetten: bestaand bestand blijft heel")

# 5. een oud bestand in de prullenbak zonder info wordt niet overschreven
wees = thuis / ".local" / "share" / "Trash" / "files" / "wees.txt"
wees.write_text("oud")
(docs / "wees.txt").write_text("nieuw")
b3, _i3 = b.naar_prullenbak(docs / "wees.txt")
klopt(wees.read_text() == "oud" and b3.read_text() == "nieuw", "prullenbak: los bestand zonder info blijft heel")

# 6. kopiëren en verplaatsen
doel = thuis / "Bureaublad"
doel.mkdir()
k = b.kopieer_een(docs / "map", doel, verplaats=False)
klopt(k == doel / "map" and (doel / "map" / "binnen.txt").read_text() == "binnenin", "kopiëren: map met inhoud gekopieerd")
k2 = b.kopieer_een(docs / "map", doel, verplaats=False)
klopt(k2 == doel / "map (2)", "kopiëren: tweede keer wordt 'map (2)'")
v = b.kopieer_een(docs / "kopie.txt", doel, verplaats=True)
klopt(v == doel / "kopie.txt" and not (docs / "kopie.txt").exists(), "verplaatsen: bestand verplaatst")
zelfde = b.kopieer_een(doel / "kopie.txt", doel, verplaats=True)
klopt(zelfde == doel / "kopie.txt" and zelfde.exists(), "verplaatsen naar dezelfde map: er gebeurt niets")
try:
    b.kopieer_een(docs / "map", docs / "map", verplaats=False)
    klopt(False, "map in zichzelf kopiëren wordt geweigerd")
except ValueError:
    klopt(True, "map in zichzelf kopiëren wordt geweigerd")

# 7. prullenbak legen
b.prullenbak_legen()
klopt(b.prullenbak_inhoud() == [], "prullenbak legen: leeg")
klopt((docs / "kopie.txt").exists() is False and (doel / "kopie.txt").exists(), "prullenbak legen: rest blijft heel")

# 8. namen tonen
klopt(b.toon_naam("Recept.odt", False) == "Recept", "naam: bekende extensie verborgen")
klopt(b.toon_naam("SpotifySetup.exe", False) == "SpotifySetup.exe", "naam: programma houdt zijn extensie")
klopt(b.toon_naam("foto.jpg", True) == "foto.jpg", "naam: map houdt zijn naam")

# 9. schijven herkennen (een nep-lijstje, zoals lsblk het geeft)
LINUX = "0fc63daf-8483-4772-8e79-3d69d8477de4"
NEP = [
    {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "size": 512110190592, "rm": False, "hotplug": False,
     "tran": "nvme", "mountpoints": [None], "children": [
         {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "type": "part", "size": 629145600, "fstype": "vfat",
          "parttype": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "mountpoints": ["/boot/efi"]},
         {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part", "size": 1073741824, "fstype": "ext4",
          "label": "boot", "parttype": LINUX, "mountpoints": ["/boot"]},
         {"name": "nvme0n1p3", "path": "/dev/nvme0n1p3", "type": "part", "size": 255000000000, "fstype": "btrfs",
          "label": "fedora", "parttype": LINUX, "mountpoints": ["/var/home", "/var", "/sysroot", "/etc"]},
         {"name": "nvme0n1p4", "path": "/dev/nvme0n1p4", "type": "part", "size": 16777216, "fstype": None,
          "parttype": "e3c9e316-0b5c-4db8-817d-f92df00215ae", "mountpoints": [None]},
         {"name": "nvme0n1p5", "path": "/dev/nvme0n1p5", "type": "part", "size": 254000000000, "fstype": "ntfs",
          "label": None, "parttype": "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7", "mountpoints": [None]},
         {"name": "nvme0n1p6", "path": "/dev/nvme0n1p6", "type": "part", "size": 700000000, "fstype": "ntfs",
          "parttype": "de94bba4-06d1-4d40-a16a-bfd50179d6ac", "mountpoints": [None]}]},
    {"name": "sda", "path": "/dev/sda", "type": "disk", "size": 1000204886016, "rm": False, "hotplug": False,
     "tran": "sata", "mountpoints": [None], "children": [
         {"name": "sda1", "path": "/dev/sda1", "type": "part", "size": 1000202788864, "fstype": "ntfs", "label": "Data",
          "fsavail": 612000000000, "fssize": 1000202788864, "mountpoints": ["/run/media/oma/Data"]}]},
    {"name": "sdb", "path": "/dev/sdb", "type": "disk", "size": 15931539456, "rm": True, "hotplug": True,
     "tran": "usb", "mountpoints": [None], "children": [
         {"name": "sdb1", "path": "/dev/sdb1", "type": "part", "size": 15930490880, "fstype": "vfat", "label": "OMA",
          "fsavail": 11800000000, "fssize": 15926000000, "mountpoints": ["/run/media/oma/OMA"]}]},
    {"name": "sdc", "path": "/dev/sdc", "type": "disk", "size": 2000398934016, "rm": False, "hotplug": True,
     "tran": "usb", "mountpoints": [None], "children": [
         {"name": "sdc1", "path": "/dev/sdc1", "type": "part", "size": 2000397795328, "fstype": "crypto_LUKS",
          "mountpoints": [None]}]},
    {"name": "sdd", "path": "/dev/sdd", "type": "disk", "size": 4026531840, "rm": True, "hotplug": True,
     "tran": "usb", "fstype": "vfat", "label": "NO NAME", "mountpoints": [None]},
    {"name": "sde", "path": "/dev/sde", "type": "disk", "size": 500107862016, "rm": False, "hotplug": True,
     "tran": "usb", "mountpoints": [None], "children": [
         {"name": "sde1", "path": "/dev/sde1", "type": "part", "size": 250000000000, "fstype": "crypto_LUKS",
          "mountpoints": [None], "children": [
              {"name": "luks-1234", "path": "/dev/mapper/luks-1234", "type": "crypt", "size": 249983000000,
               "fstype": "ext4", "label": "Back-up", "fsavail": 180000000000, "fssize": 245000000000,
               "mountpoints": ["/run/media/oma/Back-up"]}]},
         {"name": "sde2", "path": "/dev/sde2", "type": "part", "size": 250000000000, "fstype": "exfat",
          "label": "Films", "mountpoints": [None]}]},
    {"name": "sr0", "path": "/dev/sr0", "type": "rom", "size": 700000000, "rm": True, "fstype": "iso9660",
     "label": "Vakantie 2019", "mountpoints": [None]},
    {"name": "zram0", "path": "/dev/zram0", "type": "disk", "size": 8589934592, "fstype": "swap",
     "mountpoints": ["[SWAP]"]},
    {"name": "loop0", "path": "/dev/loop0", "type": "loop", "size": 100000, "fstype": "squashfs",
     "mountpoints": ["/var/lib/iets"]},
]
lijst = b.schijven(NEP)
per = {x.apparaat: x for x in lijst}
klopt(sorted(per) == ["/dev/nvme0n1p5", "/dev/sda1", "/dev/sdb1", "/dev/sdc1", "/dev/sdd", "/dev/sde1", "/dev/sde2",
                      "/dev/sr0"], "schijven: BugOS zelf, opstart- en herstelstukjes, swap en loop zie je niet")
w = per["/dev/nvme0n1p5"]
klopt(w.naam == "Windows-schijf" and w.soort == "intern" and not w.wortel and not w.los,
      "schijven: Windows naast BugOS heet 'Windows-schijf', dicht, niet uit te werpen")
klopt(per["/dev/sda1"].naam == "Data" and per["/dev/sda1"].soort == "intern" and per["/dev/sda1"].vrij == 612000000000,
      "schijven: tweede schijf in de computer, open, met vrije ruimte")
klopt(per["/dev/sdb1"].soort == "stick" and per["/dev/sdb1"].wortel == "/run/media/oma/OMA" and per["/dev/sdb1"].los,
      "schijven: USB-stick, open, uit te werpen")
c = per["/dev/sdc1"]
klopt(c.soort == "extern" and c.op_slot and c.naam == "Externe schijf",
      "schijven: externe schijf op slot heet 'Externe schijf'")
klopt(per["/dev/sdd"].naam == "USB-stick (4,0 GB)" and per["/dev/sdd"].station == "/dev/sdd",
      "schijven: stick zonder indeling en zonder naam heet 'USB-stick (4,0 GB)'")
e = per["/dev/sde1"]
klopt(e.naam == "Back-up" and e.versleuteld and not e.op_slot and e.fs_apparaat == "/dev/mapper/luks-1234",
      "schijven: geopende versleutelde schijf houdt zijn naam")
klopt(per["/dev/sr0"].soort == "cd" and per["/dev/sr0"].naam == "Vakantie 2019", "schijven: cd met naam")
stappen, laatste = b.uitwerp_stappen(lijst, "/dev/sde")
klopt(stappen == [["udisksctl", "unmount", "-b", "/dev/mapper/luks-1234"], ["udisksctl", "lock", "-b", "/dev/sde1"]]
      and laatste == ["udisksctl", "power-off", "-b", "/dev/sde"],
      "veilig verwijderen: eerst alle delen dicht (ook op slot), dan de stroom eraf")
klopt(b.openen_stappen(c)[:2] == ["solid-hardware6", "mount"] and c.apparaat.endswith("sdc1"),
      "openen: schijf op slot via KDE (die vraagt het wachtwoord)")
klopt(b.openen_stappen(per["/dev/sdd"]) == ["udisksctl", "mount", "-b", "/dev/sdd"], "openen: gewone stick via udisks")
klopt(b.schijf_van(Path("/run/media/oma/OMA/Foto's"), lijst) is per["/dev/sdb1"], "schijf_van: map op de stick")
klopt(b.systeem_plek("/var/home") and not b.systeem_plek("/var/mnt/data") and not b.systeem_plek("/run/media/oma/x"),
      "systeemplekken: /var/home wel, /var/mnt en /run/media niet")

# 10. het venster start en toont de mappen (zonder scherm)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or b.maak_app("bugos-bestanden", "bugos-bestanden", ["test"])
venster = b.Bestanden(docs)
for _ in range(50):
    app.processEvents()
klopt(venster.huidig == docs, "venster: opent in Documenten")
klopt(venster.grote_titel.text() in ("Documenten", "Documents", "Documenten".lower()) or venster.grote_titel.text() != "",
      "venster: toont een titel")
venster.ververs()
for _ in range(50):
    app.processEvents()
venster.selecteer(docs / "map")
klopt(venster.gekozen() == [docs / "map"], "kiezen: één map gekozen")
klopt(not venster.keuzebalk.isHidden() and venster.keuzebalk.knoppen["naam"].isVisibleTo(venster.keuzebalk),
      "kiezen: de knoppenbalk verschijnt, met Naam wijzigen")
klopt(venster.keuzebalk.knoppen["terugzetten"].isHidden(), "kiezen: geen Zet terug buiten de prullenbak")
venster.ga_naar(thuis)
klopt(venster.gekozen() == [] and venster.keuzebalk.isHidden(), "andere map: niets blijft gekozen, balk weg")

# kopiëren en plakken via het venster
klopt(venster.plak_knop.isHidden(), "plakken: geen knop zolang er niets gekopieerd is")
venster.ga_naar(docs)
for _ in range(50):
    app.processEvents()
venster.selecteer(docs / "map")
venster.kopieer()
app.processEvents()
klopt(not venster.plak_knop.isHidden(), "plakken: knop verschijnt na Kopiëren")
venster.ga_naar(doel)
venster.plak()
if venster.klus:
    venster.klus.wait(10000)
for _ in range(20):
    app.processEvents()
klopt((doel / "map (3)" / "binnen.txt").read_text() == "binnenin" and (docs / "map").exists(),
      "plakken: kopie als 'map (3)', het origineel blijft staan")
venster.terug()
venster.open_prullenbak()
klopt(venster.in_prullenbak and venster.lijst.model() is venster.bak_model, "venster: prullenbak opent")
venster.terug()
klopt(not venster.in_prullenbak and venster.huidig == docs, "venster: terug uit de prullenbak")

# 11. een USB-stick in het venster (nep-lijstje dat naar een echte map wijst)
import json  # noqa: E402

stick = TMP / "stick"
(stick / "Foto's").mkdir(parents=True)
nep_bestand = TMP / "lsblk.json"
nep_bestand.write_text(json.dumps({"blockdevices": [
    {"name": "sdx", "path": "/dev/sdx", "type": "disk", "size": 16000000000, "rm": True, "hotplug": True,
     "tran": "usb", "children": [
         {"name": "sdx1", "path": "/dev/sdx1", "type": "part", "size": 16000000000, "fstype": "exfat",
          "label": "Stick van oma", "fsavail": 12000000000, "fssize": 16000000000, "mountpoints": [str(stick)]}]}]}))
os.environ["BUGOS_LSBLK"] = str(nep_bestand)
venster.vul_zijbalk()
klopt([x.naam for x in venster.lijst_schijven] == ["Stick van oma"], "venster: de stick staat in de zijbalk")
venster.open_computer()
klopt(venster.in_computer and venster.stapel.currentWidget() is venster.computer
      and venster.grote_titel.text() == "Deze computer", "Deze computer: de pagina opent")
kaarten = venster.computer.widget().findChildren(b.SchijfKaart)
klopt(len(kaarten) == 2 and kaarten[1].uitwerp_knop is not None, "Deze computer: eigen bestanden en de stick (met uitwerpknop)")
kaarten[1].geklikt.emit()
klopt(venster.huidig == stick and not venster.in_computer and not venster.uitwerp_knop.isHidden()
      and venster.grote_titel.text() == "Stick van oma", "stick openen: naam bovenin en 'Veilig verwijderen'")
venster.terug()
klopt(venster.in_computer, "terug: weer op Deze computer")
venster.ga_naar(stick / "Foto's")
nep_bestand.write_text(json.dumps({"blockdevices": []}))
venster.vul_zijbalk()
klopt(venster.huidig == thuis and "eruit gehaald" in venster.melding.tekst.text(),
      "stick eruit getrokken: terug naar Thuis, met een melding")
os.environ["BUGOS_LSBLK"] = ""

# 12. opdrachten op de achtergrond (openen, veilig verwijderen): het venster loopt niet vast
from PySide6.QtCore import QElapsedTimer  # noqa: E402


def wacht_op(stappen, laatste=None):
    uitslag = []
    venster.draai(stappen, lambda ok, _uit: uitslag.append(ok), laatste)
    klok = QElapsedTimer()
    klok.start()
    while not uitslag and klok.elapsed() < 10000:
        app.processEvents()
    return uitslag[0] if uitslag else None


klopt(wacht_op([["true"], ["true"]], ["false"]) is True, "achtergrond: alles gelukt (de laatste stap mag mislukken)")
klopt(wacht_op([["true"], ["false"], ["true"]]) is False, "achtergrond: stopt bij een stap die mislukt")
klopt(wacht_op([["bestaat-niet-bugos"]]) is False, "achtergrond: een programma dat er niet is, geeft netjes 'mislukt'")

venster.close()
import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
