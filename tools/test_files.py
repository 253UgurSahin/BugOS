#!/usr/bin/env python3
"""Test of BugOS Bestanden veilig met je bestanden omgaat.

Alles gebeurt in een tijdelijke map; je echte bestanden worden niet aangeraakt.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_files.py
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

TMP = Path(tempfile.mkdtemp(prefix="bugos-files-test-"))
os.environ["HOME"] = str(TMP / "thuis")
os.environ["XDG_DATA_HOME"] = str(TMP / "thuis" / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(TMP / "thuis" / ".config")
os.environ["BUGOS_LSBLK"] = ""  # geen echte schijven in de test
os.environ["LC_ALL"] = "nl_NL.UTF-8"  # de test kijkt naar de Nederlandse teksten
(TMP / "thuis" / ".config").mkdir(parents=True)

lader = importlib.machinery.SourceFileLoader("bestanden", str(ROOT / "system_files" / "usr" / "bin" / "bugos-files"))
spec = importlib.util.spec_from_loader("bestanden", lader)
b = importlib.util.module_from_spec(spec)
sys.modules["bestanden"] = b  # nodig voor @dataclass
lader.exec_module(b)
import bugos_drives as sch  # noqa: E402  (schijven herkennen en beheren)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


thuis = TMP / "thuis"
docs = thuis / "Documenten"
docs.mkdir()
(docs / "brief.txt").write_text("hallo bugie")
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
klopt(terug == docs / "brief.txt" and terug.read_text() == "hallo bugie", "terugzetten: weer op de oude plek, inhoud heel")
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
# 6b. gaat het halverwege mis (schijf vol, stick eruit), dan blijft er geen halve kopie achter
import shutil as _sh  # noqa: E402
_echt_copy2 = _sh.copy2


def _halverwege(bron, doel_, **kw):
    _echt_copy2(bron, doel_, **kw)
    if Path(bron).name == "binnen.txt":
        raise OSError(28, "No space left on device")


_echt_copytree = _sh.copytree
_sh.copytree = lambda s, d, **kw: _echt_copytree(s, d, copy_function=_halverwege, **kw)
voor = sorted(p.name for p in doel.iterdir())
try:
    b.kopieer_een(docs / "map", doel, verplaats=False)
    klopt(False, "kopie mislukt halverwege: fout gemeld")
except (OSError, _sh.Error):
    klopt(sorted(p.name for p in doel.iterdir()) == voor, "kopie mislukt halverwege: geen halve map achtergebleven")
_sh.copytree = _echt_copytree
# 6c. verplaatsen naar een andere schijf: eerst helemaal kopiëren, dan pas het origineel weg
_echt_rename = os.rename
_keer = []


def _andere_schijf(a, c):
    if not _keer:  # alleen de eerste poging (het verplaatsen zelf) zegt: andere schijf
        _keer.append(1)
        raise OSError(18, "Invalid cross-device link")
    return _echt_rename(a, c)


os.rename = _andere_schijf
(docs / "verhuis").mkdir()
(docs / "verhuis" / "a.txt").write_text("a")
v2 = b.kopieer_een(docs / "verhuis", doel, verplaats=True)
os.rename = _echt_rename
klopt(v2 == doel / "verhuis" and (v2 / "a.txt").read_text() == "a" and not (docs / "verhuis").exists()
      and not any(p.name.endswith(".bugos-bezig") for p in doel.iterdir()),
      "verplaatsen naar een andere schijf: alles over, origineel weg, geen tijdelijke map over")

# 7. prullenbak legen
b.prullenbak_legen()
klopt(b.prullenbak_inhoud() == [], "prullenbak legen: leeg")
klopt((docs / "kopie.txt").exists() is False and (doel / "kopie.txt").exists(), "prullenbak legen: rest blijft heel")
# 7b. kan iets niet weg, dan blijft het zichtbaar in de prullenbak (geen verborgen restjes)
(docs / "vast").mkdir()
(docs / "vast" / "x.txt").write_text("x")
(docs / "los.txt").write_text("l")
b.naar_prullenbak(docs / "vast")
b.naar_prullenbak(docs / "los.txt")
_echt_rmtree = _sh.rmtree


def _weigert(p, *a, **kw):
    if Path(p).name == "vast":
        raise PermissionError(13, "Permission denied")
    return _echt_rmtree(p, *a, **kw)


_sh.rmtree = _weigert
mislukt = b.prullenbak_legen()
_sh.rmtree = _echt_rmtree
klopt(mislukt == 1 and [x[0].name for x in b.prullenbak_inhoud()] == ["vast"],
      "prullenbak legen: wat niet weg kan, telt als mislukt en blijft zichtbaar; de rest is weg")
b.prullenbak_legen()

# 7c. snelkoppelingen: telt waar de koppeling zelf staat (kapot of naar een andere schijf)
(docs / "kapot").symlink_to(TMP / "bestaat-niet")
klopt(b.zelfde_schijf(docs / "kapot", thuis), "snelkoppeling: een kapotte koppeling in Documenten mag naar de prullenbak")

# 8. namen tonen
klopt(b.toon_naam("Recept.odt", False) == "Recept", "naam: bekende extensie verborgen")
klopt(b.toon_naam("SpotifySetup.exe", False) == "SpotifySetup.exe", "naam: programma houdt zijn extensie")
klopt(b.toon_naam("foto.jpg", True) == "foto.jpg", "naam: map houdt zijn naam")

# 9. schijven herkennen (een nep-lijstje, zoals lsblk het geeft)
# U139: een stick die er net in zit, wordt opengezet (KDE doet dat niet vanzelf), zodat Back-up en Overstap hem zien.
# U142: de vaste stukjes van eMMC-geheugen (mmcblk0boot0) zijn geen 'SD-kaart', en ingebouwd eMMC is 'intern'.
_ub = TMP / "nep-udisks"
_ub.mkdir()
(_ub / "udisksctl").write_text(f"#!/usr/bin/bash\necho \"$*\" >>{_ub}/log\n")
(_ub / "udisksctl").chmod(0o755)
_oud_pad = os.environ["PATH"]
os.environ["PATH"] = f"{_ub}:{_oud_pad}"
_n = sch.losse_openen([sch.Schijf(apparaat="/dev/sdb1", naam="Stick", soort="stick", station="/dev/sdb", fs="vfat"),
                        sch.Schijf(apparaat="/dev/sdc1", naam="Al open", soort="stick", station="/dev/sdc", fs="vfat",
                                   wortel="/run/media/x/A"),
                        sch.Schijf(apparaat="/dev/sda2", naam="D", soort="intern", station="/dev/sda", fs="ntfs")])
_n2 = sch.losse_openen([sch.Schijf(apparaat="/dev/sdb1", naam="Stick", soort="stick", station="/dev/sdb", fs="vfat")])
os.environ["PATH"] = _oud_pad
klopt(_n == 1 and (_ub / "log").read_text().split() == ["mount", "-b", "/dev/sdb1", "--no-user-interaction"],
      "U139: een dichte USB-stick gaat vanzelf open (zonder te vragen); open en interne schijven niet")
klopt(_n2 == 0 and (_ub / "log").read_text().count("mount") == 1,
      "U164: weer dicht ('Veilig verwijderen') of lukte openen niet: niet elke 3 seconden opnieuw openzetten")
_sys = TMP / "sys-mmc"
for _d, _t in (("mmcblk0", "MMC"), ("mmcblk1", "SD")):
    (_sys / "block" / _d / "device").mkdir(parents=True)
    (_sys / "block" / _d / "device" / "type").write_text(_t + "\n")
os.environ["BUGOS_SYS"] = str(_sys)
_emmc = [{"name": "mmcblk0boot0", "path": "/dev/mmcblk0boot0", "type": "disk", "size": 4194304, "rm": False},
         {"name": "mmcblk0", "path": "/dev/mmcblk0", "type": "disk", "size": 64000000000, "rm": False, "children": [
             {"name": "mmcblk0p1", "path": "/dev/mmcblk0p1", "type": "part", "size": 64000000000, "fstype": "ntfs",
              "label": "Data", "mountpoints": [None]}]},
         {"name": "mmcblk1", "path": "/dev/mmcblk1", "type": "disk", "size": 32000000000, "rm": True, "children": [
             {"name": "mmcblk1p1", "path": "/dev/mmcblk1p1", "type": "part", "size": 32000000000, "fstype": "exfat",
              "mountpoints": [None]}]}]
_lijst = sch.schijven(_emmc)
del os.environ["BUGOS_SYS"]
klopt(not any("boot0" in x.apparaat for x in _lijst) and [x.soort for x in _lijst] == ["intern", "kaart"],
      f"U142: eMMC: geen nep-'SD-kaart (4,2 MB)', ingebouwd geheugen is intern, een echte SD-kaart is een kaart ({[(x.apparaat, x.soort) for x in _lijst]})")
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
          "fsavail": 612000000000, "fssize": 1000202788864, "mountpoints": ["/run/media/bugie/Data"]}]},
    {"name": "sdb", "path": "/dev/sdb", "type": "disk", "size": 15931539456, "rm": True, "hotplug": True,
     "tran": "usb", "mountpoints": [None], "children": [
         {"name": "sdb1", "path": "/dev/sdb1", "type": "part", "size": 15930490880, "fstype": "vfat", "label": "BUGIE",
          "fsavail": 11800000000, "fssize": 15926000000, "mountpoints": ["/run/media/bugie/BUGIE"]}]},
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
              {"name": "luks-1234", "kname": "dm-0", "path": "/dev/mapper/luks-1234", "type": "crypt",
               "size": 249983000000,
               "fstype": "ext4", "label": "Back-up", "fsavail": 180000000000, "fssize": 245000000000,
               "mountpoints": ["/run/media/bugie/Back-up"]}]},
         {"name": "sde2", "path": "/dev/sde2", "type": "part", "size": 250000000000, "fstype": "exfat",
          "label": "Films", "mountpoints": [None]}]},
    {"name": "sdf", "path": "/dev/sdf", "type": "disk", "size": 1000204886016, "rm": False, "hotplug": False,
     "tran": "sata", "mountpoints": [None]},
    {"name": "sdg", "path": "/dev/sdg", "type": "disk", "size": 2000398934016, "rm": False, "hotplug": False,
     "tran": "sata", "mountpoints": [None], "children": [
         {"name": "sdg1", "path": "/dev/sdg1", "type": "part", "size": 2000397795328, "fstype": "LVM2_member",
          "mountpoints": [None]}]},
    {"name": "sr0", "path": "/dev/sr0", "type": "rom", "size": 700000000, "rm": True, "fstype": "iso9660",
     "label": "Vakantie 2019", "mountpoints": [None]},
    {"name": "zram0", "path": "/dev/zram0", "type": "disk", "size": 8589934592, "fstype": "swap",
     "mountpoints": ["[SWAP]"]},
    {"name": "loop0", "path": "/dev/loop0", "type": "loop", "size": 100000, "fstype": "squashfs",
     "mountpoints": ["/var/lib/iets"]},
]
lijst = sch.schijven(NEP)
per = {x.apparaat: x for x in lijst}
klopt(sorted(per) == ["/dev/sda1", "/dev/sdb1", "/dev/sdc1", "/dev/sdd", "/dev/sde1", "/dev/sde2", "/dev/sdf",
                      "/dev/sr0"],
      "schijven: de schijf van BugOS zelf (met alles erop), LVM, swap en loop zie je niet")
f = per["/dev/sdf"]
klopt(f.nieuw and f.soort == "intern" and f.naam == "Nieuwe schijf (1,0 TB)" and not f.los,
      "nieuwe schijf in de computer: 'Nieuwe schijf (1,0 TB)', nog niet in gebruik")
st = sch.klaarmaak_stappen(f, "Opslag")
klopt(st[0][st[0].index("--object-path") + 1].endswith("/sdf") and st[0][-3].endswith("Block.Format")
      and st[0][-2] == "'gpt'",
      "in gebruik nemen (in de computer): eerst een nieuwe indeling (GPT)")
klopt(st[1][-8].endswith("CreatePartitionAndFormat") and st[1][-7:-5] == ["1048576", "0"] and st[1][-2] == "'ext4'"
      and "take-ownership" in st[1][-1] and "'Opslag'" in st[1][-1],
      "in gebruik nemen: één stuk over de hele schijf, ext4, en van jou")
klopt(st[2] == ["udisksctl", "mount", "-b", "/dev/sdf1"], "in gebruik nemen: daarna meteen open")
nieuwe_stick = sch.Schijf(apparaat="/dev/sdh", naam="USB-stick (16 GB)", soort="stick", station="/dev/sdh", nieuw=True)
st = sch.klaarmaak_stappen(nieuwe_stick, "USB-stick")
klopt(st[0][-2] == "'dos'" and st[1][-5] == "'0x07'" and st[1][-2] == "'exfat'",
      "in gebruik nemen (stick): exFAT, zodat hij ook op Windows, Mac en tv's werkt")
klopt(sch.eerste_deel("/dev/nvme1n1") == "/dev/nvme1n1p1" and sch.eerste_deel("/dev/sdb") == "/dev/sdb1",
      "eerste stuk: sdb1, maar nvme1n1p1")
proef = [sch.Schijf("/dev/sdx1", "Data", "intern", "/dev/sdx", "/dev/sdx1", fs="ntfs"),
         sch.Schijf("/dev/sdy1", "Open", "intern", "/dev/sdy", "/dev/sdy1", wortel="/run/media/bugie/Open", fs="ext4"),
         sch.Schijf("/dev/sdz1", "Stick", "stick", "/dev/sdz", "/dev/sdz1", fs="vfat"),
         sch.Schijf("/dev/sdw1", "Slot", "intern", "/dev/sdw", "/dev/sdw1", op_slot=True, fs="crypto_LUKS"),
         sch.Schijf("/dev/sdv", "Nieuw", "intern", "/dev/sdv", nieuw=True)]
klopt(sch.auto_open_stappen(proef) == [["udisksctl", "mount", "-b", "/dev/sdx1", "--no-user-interaction"]],
      "bij het opstarten: alleen dichte schijven in de computer gaan vanzelf open (geen sticks, slot of nieuw)")
klopt(per["/dev/sda1"].naam == "Data" and per["/dev/sda1"].soort == "intern" and per["/dev/sda1"].vrij == 612000000000,
      "schijven: tweede schijf in de computer, open, met vrije ruimte")
klopt(per["/dev/sdb1"].soort == "stick" and per["/dev/sdb1"].wortel == "/run/media/bugie/BUGIE" and per["/dev/sdb1"].los,
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
stappen, laatste = sch.uitwerp_stappen(lijst, "/dev/sde")
klopt(stappen == [["udisksctl", "unmount", "-b", "/dev/mapper/luks-1234"], ["udisksctl", "lock", "-b", "/dev/sde1"]]
      and laatste == ["udisksctl", "power-off", "-b", "/dev/sde"],
      "veilig verwijderen: eerst alle delen dicht (ook op slot), dan de stroom eraf")
klopt(sch.openen_stappen(c)[:2] == ["solid-hardware6", "mount"] and c.apparaat.endswith("sdc1"),
      "openen: schijf op slot via KDE (die vraagt het wachtwoord)")
klopt(sch.openen_stappen(per["/dev/sdd"]) == ["udisksctl", "mount", "-b", "/dev/sdd"], "openen: gewone stick via udisks")
klopt(b.schijf_van(Path("/run/media/bugie/BUGIE/Foto's"), lijst) is per["/dev/sdb1"], "schijf_van: map op de stick")
klopt(sch.systeem_plek("/var/home") and not sch.systeem_plek("/var/mnt/data") and not sch.systeem_plek("/run/media/bugie/x"),
      "systeemplekken: /var/home wel, /var/mnt en /run/media niet")
klopt(e.udisks_fs.endswith("/block_devices/dm_2d0") and e.udisks_deel.endswith("/block_devices/sde1"),
      "udisks: 'dm-0' wordt 'dm_2d0' (zo heet hij daar)")
klopt(sch.gvariant_tekst("Bugie's stick") == "'Bugie\\'s stick'", "naam wijzigen: een ' in de naam gaat goed mee")
bugie = per["/dev/sdb1"]
st = sch.hernoem_stappen(bugie, "Foto's")
klopt(st[0] == ["udisksctl", "unmount", "-b", "/dev/sdb1"] and "Filesystem.SetLabel" in st[1][-3]
      and st[1][-2] == "'Foto\\'s'" and st[2] == ["udisksctl", "mount", "-b", "/dev/sdb1"],
      "naam wijzigen: dicht, naam erop, weer open")
st = sch.leegmaak_stappen(e, "Back-up")
klopt(st[0] == ["udisksctl", "unmount", "-b", "/dev/mapper/luks-1234"] and st[1] == ["udisksctl", "lock", "-b", "/dev/sde1"]
      and st[2][st[2].index("--object-path") + 1].endswith("/sde1") and "'exfat'" in st[2]
      and st[3] == ["udisksctl", "mount", "-b", "/dev/sde1"],
      "leegmaken: dicht, op slot, het hele stuk opnieuw (exFAT), weer open")
klopt(sch.repareer_stappen(per["/dev/sdd"])[0][-2].endswith("Filesystem.Repair"),
      "repareren: een dichte stick hoeft niet eerst dicht")

(TMP / "tel" / "binnen").mkdir(parents=True)
(TMP / "tel" / "a.bin").write_bytes(b"x" * 100_000)
(TMP / "tel" / "binnen" / "b.bin").write_bytes(b"x" * 50_000)
klopt(b.mapgrootte(TMP / "tel") >= 150_000, "ruimte tellen: ook wat in submappen staat telt mee")

# 10. het venster start en toont de mappen (zonder scherm)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or b.maak_app("bugos-files", "bugos-files", ["test"])
venster = b.Bestanden(docs)
for _ in range(50):
    app.processEvents()
klopt(venster.huidig == docs, "venster: opent in Documenten")
klopt(venster.plek_naam() == docs.name, "venster: het pad bovenin eindigt bij Documenten")
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


class _BezigeKlus:
    def isRunning(self):  # noqa: N802
        return True


venster.show()
venster.klus = _BezigeKlus()
venster.close()
klopt(venster.isVisible() and venster.sluit_na_klus, "sluiten tijdens kopiëren: venster wacht tot het klaar is")
venster.klus = None
venster._klus_klaar(1, "", False)
for _ in range(20):
    app.processEvents()
klopt(not venster.isVisible(), "sluiten tijdens kopiëren: na het kopiëren gaat het venster vanzelf dicht")
venster.sluit_na_klus = False
venster.show()
# ongedaan maken dat niet lukt (het ding is intussen weg uit de prullenbak): geen 'Teruggezet.'
venster.laatst_weg = [(thuis / ".local" / "share" / "Trash" / "files" / "bestaat-niet.txt",
                       thuis / ".local" / "share" / "Trash" / "info" / "bestaat-niet.txt.trashinfo")]
venster.ongedaan()
klopt("niet terug" in venster.melding.tekst.text(), "ongedaan maken dat mislukt: zegt dat het niet lukte")

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
          "label": "Stick van Bugie", "fsavail": 12000000000, "fssize": 16000000000, "mountpoints": [str(stick)]}]}]}))
os.environ["BUGOS_LSBLK"] = str(nep_bestand)
venster.vul_zijbalk()
klopt([x.naam for x in venster.lijst_schijven] == ["Stick van Bugie"], "venster: de stick staat in de zijbalk")
venster.open_computer()
klopt(venster.in_computer and venster.stapel.currentWidget() is venster.computer
      and venster.plek_naam() == "Deze computer", "Deze computer: de pagina opent")
tegels = venster.computer.widget().findChildren(b.SchijfRij)
klopt(len(tegels) == 1 and tegels[0].uitwerp_knop is not None and tegels[0].meer is not None,
      "Deze computer: de stick, met 'Veilig verwijderen' en een knop voor meer")
menu = venster.schijf_menu(venster.lijst_schijven[0])
klopt([a.text() for a in menu.actions() if a.text()] == ["Openen", "Naam wijzigen…", "Controleren en repareren",
                                                          "Leegmaken (alles wissen)…", "Veilig verwijderen"],
      "beheer: openen, naam wijzigen, repareren, leegmaken, veilig verwijderen")
windows = sch.Schijf("/dev/nvme0n1p3", "Windows", "intern", "/dev/nvme0n1", "/dev/nvme0n1p3", fs="ntfs")
klopt("Leegmaken (alles wissen)…" not in [a.text() for a in venster.schijf_menu(windows).actions()],
      "beheer: een interne schijf (Windows) kun je hier niet wissen")
_gewist: list = []
_oud_vraag, _oud_beheer = venster.vraag_ja, venster.beheer
venster.vraag_ja = lambda *a, **kw: True
_stappen: list = []
venster.beheer = lambda x, *a, **kw: (_gewist.append(x.apparaat), _stappen.append(str(a[0]) if a else ""))
andere = sch.Schijf("/dev/sdq1", "Andere stick", "stick", "/dev/sdq", "/dev/sdq1", fs="vfat")
venster.leegmaak_schijf(andere)                     # zit er niet (meer) in
venster.leegmaak_schijf(windows)                    # intern: nooit
venster.leegmaak_schijf(venster.lijst_schijven[0])  # de stick die er echt in zit
venster.vraag_ja, venster.beheer = _oud_vraag, _oud_beheer
klopt(_gewist == ["/dev/sdx1"], "leegmaken: alleen de stick die er nu echt in zit (geen andere, geen interne)")
# U058: exFAT kent hoogstens 11 tekens; "Stick van Bugie" (15) zou het wissen laten mislukken, dus een kortere naam.
klopt(_stappen and "Stick van Bugie" not in _stappen[0] and "USB-stick" in _stappen[0],
      "U058: leegmaken van een stick met een lange naam (15 tekens) gebruikt een naam die exFAT kent")
klopt(venster.ruimte_balk is not None and venster.status.text() == "1 aangesloten", "Deze computer: ruimte bovenaan, en 1 aangesloten")
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402

klopt(tegels[0].focusPolicy() == Qt.FocusPolicy.StrongFocus and tegels[0].accessibleName() == "Stick van Bugie",
      "toetsenbord: de stick-rij is met Tab te bereiken en heeft een naam voor schermlezers")
_geopend = []
tegels[0].geklikt.connect(lambda: _geopend.append(1))
tegels[0].keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
klopt(_geopend == [1] and venster.huidig == stick, "toetsenbord: Enter op de stick-rij opent hem")
venster.open_computer()
tegels = venster.computer.widget().findChildren(b.SchijfRij)
tegels[0].geklikt.emit()
klopt(venster.huidig == stick and not venster.in_computer and not venster.uitwerp_knop.isHidden()
      and venster.plek_naam() == "Stick van Bugie", "stick openen: naam bovenin en 'Veilig verwijderen'")
venster.terug()
klopt(venster.in_computer, "terug: weer op Deze computer")
venster.ga_naar(stick / "Foto's")
nep_bestand.write_text(json.dumps({"blockdevices": []}))
venster.vul_zijbalk()
klopt(venster.huidig == thuis and "eruit gehaald" in venster.melding.tekst.text(),
      "stick eruit getrokken: terug naar Thuis, met een melding")
os.environ["BUGOS_LSBLK"] = ""
venster.vul_zijbalk()
venster.open_computer()
for _ in range(20):
    app.processEvents()
leeg = [x for x in venster.computer.widget().findChildren(b.SchijfRij) if x.property("leeg") == "true"]
klopt(len(leeg) == 1, "Deze computer zonder stick: 'Steek een USB-stick in' (en verder niets)")
# U077: 'Ruimte maken > Prullenbak leegmaken' op Deze computer: je blijft op Deze computer, en Terug klopt.
(thuis / "weg-ermee.txt").write_text("x")
b.naar_prullenbak(thuis / "weg-ermee.txt")
_terug_voor = list(venster.terug_lijst)
venster.vraag_ja = lambda *a, **kw: True
venster.leegmaken()
klopt(venster.in_computer and not venster.in_prullenbak and venster.terug_lijst == _terug_voor
      and not b.prullenbak_inhoud(), "U077: prullenbak leegmaken vanaf Deze computer: je blijft daar, Terug klopt")

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
# U141: naam wijzigen of repareren mislukt: de schijf gaat toch weer open (de laatste stap draait altijd).
_teken = TMP / "weer-open"
_uit: list = []
venster.draai([["false"]], lambda ok, _u: _uit.append(ok), altijd=["touch", str(_teken)])
_k = QElapsedTimer()
_k.start()
while not _uit and _k.elapsed() < 10000:
    app.processEvents()
klopt(_uit == [False] and _teken.exists(), "U141: mislukt het hernoemen of repareren, dan gaat de schijf toch weer open")

venster.close()
import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
