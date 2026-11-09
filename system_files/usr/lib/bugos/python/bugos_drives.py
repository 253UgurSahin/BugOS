"""BugOS: schijven herkennen en beheren (USB-sticks, externe en interne schijven).

Gedeeld door Bestanden en door bugos-open-drives (dat interne schijven bij het
opstarten opent, zoals D: in Windows altijd klaarstaat). Alles gaat via lsblk (kijken)
en udisks (doen); een wachtwoord vraagt KDE zelf als dat nodig is.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from bugos_ui import TAAL, t


def mooie_maat(n: int | float) -> str:
    for eenheid in ("bytes", "kB", "MB", "GB", "TB"):
        if n < 1000 or eenheid == "TB":
            if eenheid == "bytes":
                return f"{int(n)} bytes"
            tekst = f"{n:.1f} {eenheid}" if n < 10 else f"{n:.0f} {eenheid}"
            return tekst.replace(".", ",") if TAAL == "nl" else tekst  # 3,2 GB in het Nederlands, 3.2 GB in het Engels
        n /= 1000
    return ""


# ================================================================ schijven ===
# Alles wat je kunt insteken of wat er extra in de computer zit: USB-sticks, externe
# schijven, een tweede schijf, de oude Windows-schijf, een SD-kaartje of een cd.
# De schijf waar BugOS zelf op staat heet gewoon "Deze computer".

@dataclass
class Schijf:
    apparaat: str            # de partitie, bv. /dev/sdb1 (of /dev/sdb bij een stick zonder indeling)
    naam: str                # wat je ziet, bv. "USB-stick van Bugie" of "USB-stick (16 GB)"
    soort: str               # "stick", "extern", "intern", "kaart" of "cd"
    station: str             # het hele apparaat (bv. /dev/sdb): dat gaat eruit bij veilig verwijderen
    fs_apparaat: str = ""    # waar de bestanden echt op staan (bij een versleutelde schijf: het slot-apparaat)
    wortel: str = ""         # waar hij open staat; leeg = nog dicht
    grootte: int = 0         # in bytes
    vrij: int | None = None  # in bytes, als hij open staat
    op_slot: bool = False    # versleuteld en nog niet geopend
    versleuteld: bool = False
    fs: str = ""             # soort bestandssysteem, bv. ntfs, vfat, exfat
    udisks_deel: str = ""    # het stuk bij udisks (om leeg te maken)
    udisks_fs: str = ""      # het bestandssysteem bij udisks (naam wijzigen, repareren)
    nieuw: bool = False      # een nieuwe, lege schijf: eerst 'In gebruik nemen'

    @property
    def los(self) -> bool:
        """Kun je hem eruit halen (en dus veilig verwijderen)?"""
        return self.soort in ("stick", "extern", "kaart", "cd")

    @property
    def icoon(self) -> str:
        return {"stick": "usb", "kaart": "kaart", "cd": "cd"}.get(self.soort, "opslag")


VERBORGEN_TYPES = {  # partities die je nooit hoeft te zien
    "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",  # EFI (opstarten)
    "e3c9e316-0b5c-4db8-817d-f92df00215ae",  # Microsoft, gereserveerd
    "de94bba4-06d1-4d40-a16a-bfd50179d6ac",  # Windows-herstel
    "21686148-6449-6e6f-744e-656564454649",  # BIOS-opstart
    "0xef", "0x27",                          # EFI en Windows-herstel (oude indeling)
}
VERBORGEN_FS = {"swap", "LVM2_member", "linux_raid_member", "zfs_member", "squashfs", "erofs"}
SLOT_FS = {"crypto_LUKS", "BitLocker"}
LSBLK = ["lsblk", "-J", "-b", "-o",
         "NAME,KNAME,PATH,TYPE,SIZE,FSTYPE,FSAVAIL,FSSIZE,LABEL,MODEL,RM,HOTPLUG,TRAN,MOUNTPOINTS,PARTTYPE"]
UDISKS = "/org/freedesktop/UDisks2/block_devices/"


def udisks_pad(kname: str) -> str:
    """Het adres van een schijf bij udisks: 'sdb1' blijft 'sdb1', 'dm-0' wordt 'dm_2d0'."""
    return UDISKS + "".join(c if c.isalnum() else f"_{ord(c):02x}" for c in kname)


def systeem_plek(plek: str) -> bool:
    """Staat hier BugOS zelf? (/, /boot, /var, ... maar niet /var/mnt of /run/media)"""
    if plek in ("/", "[SWAP]"):
        return True
    if plek.startswith(("/var/mnt/", "/var/media/", "/run/media/", "/media/", "/mnt/")):
        return False
    return any(plek == p or plek.startswith(p + "/")
               for p in ("/sysroot", "/boot", "/efi", "/usr", "/etc", "/var", "/home", "/root", "/opt", "/srv"))


def lees_lsblk() -> list[dict]:
    nep = os.environ.get("BUGOS_LSBLK")  # voor tests en foto's: een vast lijstje in plaats van de echte schijven
    try:
        if nep is not None:
            return json.loads(Path(nep).read_text(encoding="utf-8")).get("blockdevices", []) if nep else []
        uit = subprocess.run(LSBLK, capture_output=True, text=True, timeout=4).stdout
        return json.loads(uit).get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def _plekken_van(a: dict) -> list[str]:
    return [m for m in (a.get("mountpoints") or [a.get("mountpoint")]) if m]


def _alle(a: dict):
    yield a
    for kind in a.get("children") or []:
        yield from _alle(kind)


def _getal(waarde) -> int | None:
    try:
        return int(waarde) if waarde is not None else None
    except (TypeError, ValueError):
        return None


def mmc_soort(naam: str) -> str:
    """'SD' voor een SD-kaart, 'MMC' voor ingebouwd eMMC-geheugen ('' als het niet te zien is)."""
    try:
        return (Path(os.environ.get("BUGOS_SYS", "/sys")) / "block" / naam / "device" / "type").read_text().strip()
    except OSError:
        return ""


def schijven(apparaten: list[dict] | None = None) -> list[Schijf]:
    """Alle schijven die je in Bestanden ziet (dus niet de schijf van BugOS zelf)."""
    apparaten = lees_lsblk() if apparaten is None else apparaten
    lijst: list[Schijf] = []
    for station in apparaten:
        if station.get("type") not in ("disk", "rom"):
            continue  # geen loop-apparaten en dergelijke
        naam = station.get("name") or ""
        if naam.startswith(("zram", "loop", "ram", "nbd")):
            continue
        if re.fullmatch(r"mmcblk\d+(boot\d+|rpmb)", naam):
            continue   # vaste stukjes van ingebouwd eMMC-geheugen, geen echte schijf (U142)
        systeem = any(systeem_plek(m) for a in _alle(station) for m in _plekken_van(a))
        grootte_station = _getal(station.get("size")) or 0
        if station.get("type") == "rom":
            soort = "cd"
        elif naam.startswith("mmcblk"):
            # SD-kaart of ingebouwd eMMC-geheugen (goedkope laptops)? Dat zegt de kernel (U142).
            soort = "intern" if mmc_soort(naam) == "MMC" else "kaart"
        elif station.get("rm") or station.get("hotplug") or station.get("tran") == "usb":
            soort = "stick" if station.get("rm") or grootte_station <= 128 * 10**9 else "extern"
        else:
            soort = "intern"
        if systeem:
            continue  # de schijf van BugOS zelf: daar staat alles al onder 'Thuis'
        if soort != "cd" and grootte_station > 0 and not station.get("fstype") and not station.get("children"):
            # Helemaal leeg (nieuw gekocht of gewist): eerst 'In gebruik nemen', zoals in Windows.
            maat = mooie_maat(grootte_station)
            lijst.append(Schijf(
                apparaat=station.get("path") or f"/dev/{naam}", soort=soort, station=station.get("path") or f"/dev/{naam}",
                naam={"stick": t(f"USB-stick ({maat})", f"USB stick ({maat})"),
                      "extern": t("Externe schijf", "External drive"),
                      "kaart": t(f"SD-kaart ({maat})", f"SD card ({maat})")}.get(
                          soort, t(f"Nieuwe schijf ({maat})", f"New drive ({maat})")),
                grootte=grootte_station, nieuw=True,
                udisks_deel=udisks_pad(station.get("kname") or naam)))
            continue
        kandidaten = [station] if station.get("fstype") and not station.get("children") else \
            [k for k in station.get("children") or [] if k.get("type") == "part"]
        for deel in kandidaten:
            fs = deel.get("fstype") or ""
            if not fs or fs in VERBORGEN_FS or (deel.get("parttype") or "").lower() in VERBORGEN_TYPES:
                continue
            grootte = _getal(deel.get("size")) or 0
            fs_deel, versleuteld, op_slot = deel, fs in SLOT_FS, False
            if versleuteld:
                open_slot = next((k for k in deel.get("children") or [] if k.get("type") == "crypt"), None)
                if open_slot is not None:
                    fs_deel = open_slot
                else:
                    op_slot = True
            plekken_ = _plekken_van(fs_deel)
            if any(systeem_plek(m) for m in plekken_):
                continue  # hier staat BugOS zelf op
            if soort == "intern" and not plekken_ and grootte < 10**9:
                continue  # kleine verborgen stukjes van de fabrikant
            label = (fs_deel.get("label") or deel.get("label") or "").strip()
            if label.upper() in ("NO NAME", "NO_NAME", "UNTITLED"):
                label = ""
            if not label:
                maat = mooie_maat(grootte or grootte_station)
                label = {
                    "stick": t(f"USB-stick ({maat})", f"USB stick ({maat})"),
                    "extern": t("Externe schijf", "External drive"),
                    "kaart": t(f"SD-kaart ({maat})", f"SD card ({maat})"),
                    "cd": t("Cd of dvd", "CD or DVD"),
                }.get(soort, t(f"Schijf ({maat})", f"Drive ({maat})"))
            wortel = plekken_[0] if plekken_ else ""
            lijst.append(Schijf(
                apparaat=deel.get("path") or f"/dev/{deel.get('name')}", naam=label, soort=soort,
                station=station.get("path") or f"/dev/{naam}",
                fs_apparaat=fs_deel.get("path") or f"/dev/{fs_deel.get('name')}", wortel=wortel,
                grootte=_getal(fs_deel.get("fssize")) or grootte, vrij=_getal(fs_deel.get("fsavail")) if wortel else None,
                op_slot=op_slot, versleuteld=versleuteld, fs=fs_deel.get("fstype") or fs,
                udisks_deel=udisks_pad(deel.get("kname") or deel.get("name") or ""),
                udisks_fs=udisks_pad(fs_deel.get("kname") or fs_deel.get("name") or "")))
    gezien: dict[str, int] = {}
    for s in lijst:  # twee keer dezelfde naam? Dan "USB-stick (16 GB) (2)"
        gezien[s.naam] = gezien.get(s.naam, 0) + 1
        if gezien[s.naam] > 1:
            s.naam = f"{s.naam} ({gezien[s.naam]})"
    return lijst


def openen_stappen(s: Schijf) -> list[str]:
    """Hoe zetten we deze schijf open? (Een wachtwoord vraagt KDE zelf, in een eigen venster.)"""
    if s.op_slot:
        return ["solid-hardware6", "mount", s.udisks_deel or udisks_pad(Path(s.apparaat).name)]
    return ["udisksctl", "mount", "-b", s.fs_apparaat or s.apparaat]


def gvariant_tekst(tekst: str) -> str:
    return "'" + tekst.replace("\\", "\\\\").replace("'", "\\'") + "'"


def udisks_opdracht(pad: str, methode: str, *args: str) -> list[str]:
    """Iets vragen aan udisks (de schijvendienst). Een wachtwoord vraagt KDE zelf, als dat nodig is."""
    return ["gdbus", "call", "--system", "--interactive", "--timeout", "3600", "--dest", "org.freedesktop.UDisks2",
            "--object-path", pad, "--method", f"org.freedesktop.UDisks2.{methode}", *args]


def dicht_stappen(s: Schijf) -> list[list[str]]:
    """Eerst dicht (als hij open is), en een versleutelde schijf ook weer op slot."""
    stappen = [["udisksctl", "unmount", "-b", s.fs_apparaat or s.apparaat]] if s.wortel else []
    if s.versleuteld and not s.op_slot:
        stappen.append(["udisksctl", "lock", "-b", s.apparaat])
    return stappen


# exFAT: 11 tekens (exfatprogs en udisks weigeren een langere naam, en dan mislukt wissen of instellen).
MAX_NAAM = {"vfat": 11, "exfat": 11, "ntfs": 32, "ext4": 16, "ext3": 16, "ext2": 16, "btrfs": 255, "xfs": 12}


def hernoem_stappen(s: Schijf, naam: str) -> list[list[str]]:
    """Een andere naam voor de stick (het etiket). Dicht, naam erop, weer open."""
    stappen = [["udisksctl", "unmount", "-b", s.fs_apparaat or s.apparaat]] if s.wortel else []
    stappen.append(udisks_opdracht(s.udisks_fs, "Filesystem.SetLabel", gvariant_tekst(naam), "{}"))
    stappen.append(["udisksctl", "mount", "-b", s.fs_apparaat or s.apparaat])
    return stappen


def repareer_stappen(s: Schijf) -> list[list[str]]:
    """Controleren en repareren (zoals 'Scannen en herstellen' in Windows). Dicht, repareren, weer open."""
    stappen = [["udisksctl", "unmount", "-b", s.fs_apparaat or s.apparaat]] if s.wortel else []
    stappen.append(udisks_opdracht(s.udisks_fs, "Filesystem.Repair", "{}"))
    stappen.append(["udisksctl", "mount", "-b", s.fs_apparaat or s.apparaat])
    return stappen


def leegmaak_stappen(s: Schijf, naam: str) -> list[list[str]]:
    """Alles wissen en opnieuw beginnen (formatteren), als exFAT: dat werkt ook op Windows, Mac en tv's."""
    stappen = dicht_stappen(s)
    opties = "{'label': <" + gvariant_tekst(naam) + ">, 'update-partition-type': <true>}"
    stappen.append(udisks_opdracht(s.udisks_deel, "Block.Format", gvariant_tekst("exfat"), opties))
    stappen.append(["udisksctl", "mount", "-b", s.apparaat])
    return stappen


def uitwerp_stappen(lijst: list[Schijf], station: str) -> tuple[list[list[str]], list[str]]:
    """Wat moet er gebeuren voor 'Veilig verwijderen'? Alle delen dicht, dan de stroom eraf.

    Geeft (stappen die moeten lukken, laatste stap die mag mislukken)."""
    stappen: list[list[str]] = []
    for s in lijst:
        if s.station != station:
            continue
        if s.wortel:
            stappen.append(["udisksctl", "unmount", "-b", s.fs_apparaat or s.apparaat])
        if s.versleuteld and not s.op_slot:
            stappen.append(["udisksctl", "lock", "-b", s.apparaat])
    if station.startswith("/dev/sr"):
        return stappen, ["eject", station]
    return stappen, ["udisksctl", "power-off", "-b", station]


def eerste_deel(station: str) -> str:
    """Het eerste stuk van een schijf: /dev/sdb -> /dev/sdb1, /dev/nvme1n1 -> /dev/nvme1n1p1."""
    return f"{station}p1" if station[-1:].isdigit() else f"{station}1"


def klaarmaak_stappen(s: Schijf, naam: str) -> list[list[str]]:
    """Een nieuwe, lege schijf klaarmaken, zoals Schijfbeheer in Windows: indelen, één stuk, formatteren.

    In de computer: ext4 (snel en betrouwbaar) en van jou. Los (stick, externe schijf): exFAT, werkt overal."""
    station = udisks_pad(Path(s.station).name)
    if s.los:
        tabel, soort_deel, fs, extra = "dos", "0x07", "exfat", ""
    else:
        tabel, soort_deel, fs, extra = "gpt", "", "ext4", ", 'take-ownership': <true>"
    opties = "{'label': <" + gvariant_tekst(naam) + ">" + extra + "}"
    return [
        udisks_opdracht(station, "Block.Format", gvariant_tekst(tabel), "{}"),
        udisks_opdracht(station, "PartitionTable.CreatePartitionAndFormat", "1048576", "0", gvariant_tekst(soort_deel),
                        gvariant_tekst(""), "{}", gvariant_tekst(fs), opties),
        ["udisksctl", "mount", "-b", eerste_deel(s.station)],
    ]


def losse_openen(lijst: list[Schijf] | None = None) -> int:
    """Zet USB-sticks, externe schijven en SD-kaarten die er net in zitten open (zonder te vragen), zodat Back-up
    en Overstap ze zien. KDE doet dat standaard niet (automount staat uit) (U139). Geeft hoeveel er opengingen."""
    lijst = schijven() if lijst is None else lijst
    gedaan = 0
    for s in lijst:
        if s.soort in ("stick", "extern", "kaart") and not s.wortel and not s.op_slot and not s.nieuw and s.fs:
            try:
                if subprocess.run(["udisksctl", "mount", "-b", s.fs_apparaat or s.apparaat, "--no-user-interaction"],
                                  capture_output=True, timeout=20).returncode == 0:
                    gedaan += 1
            except (OSError, subprocess.SubprocessError):
                pass
    return gedaan


_openen_bezig = []


def losse_openen_op_achtergrond() -> None:
    """losse_openen() in een eigen draad (udisks kan even duren): het venster loopt niet vast. De volgende keer
    kijken ziet de stick dan open."""
    if _openen_bezig:
        return
    import threading

    def werk() -> None:
        try:
            losse_openen()
        except Exception:  # noqa: BLE001  zonder lsblk/udisks: dan niet
            pass
        finally:
            _openen_bezig.clear()

    _openen_bezig.append(1)
    threading.Thread(target=werk, daemon=True).start()


def auto_open_stappen(lijst: list[Schijf]) -> list[list[str]]:
    """Welke schijven gaan vanzelf open na het inloggen? Alle schijven die in de computer zitten
    (zoals D: in Windows), behalve schijven op slot of nieuwe, lege schijven."""
    return [["udisksctl", "mount", "-b", s.fs_apparaat or s.apparaat, "--no-user-interaction"]
            for s in lijst if s.soort == "intern" and not s.wortel and not s.op_slot and not s.nieuw and s.fs]
