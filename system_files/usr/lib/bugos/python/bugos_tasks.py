"""BugOS Taakbeheer: wat doet je computer? (zonder extra onderdelen; alles komt uit /proc en /sys)

Programma's worden per app gegroepeerd zoals KDE ze start: elk programma draait in zijn
eigen systemd-groep (bijvoorbeeld app-org.mozilla.firefox-1234.scope). Zo hoort alles van
Firefox bij elkaar, ook de losse tabbladen.

Voor tests en foto's kan een nep-/proc gebruikt worden: BUGOS_PROC=/pad/naar/proc.

Namen van apps en 'Opstarten' komen uit de .desktop-bestanden: dat staat in bugos_desktop.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from bugos_desktop import (  # noqa: F401  (doorgeven: Taakbeheer haalt dit uit bugos_tasks)
    _APPS, ALLEEN_UIT, Opstart, app_info, app_mappen, config_thuis, lees_bureaublad, met_hidden, mooie_naam,
    opstart_lijst, schrijf_veilig, systeem_autostart, vertaald, zet_opstart,
)
from bugos_drives import mooie_maat as maat
from bugos_ui import t

PF_KTHREAD = 0x00200000  # een stukje van de kernel zelf, geen programma
PAGINA = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
SCHIJF_NAAM = re.compile(r"^(sd[a-z]+|vd[a-z]+|xvd[a-z]+|hd[a-z]+|nvme\d+n\d+|mmcblk\d+)$")
NIET_NETWERK = ("lo", "veth", "docker", "br-", "virbr", "podman", "tun", "tap", "wg", "vnet")
APP_EENHEID = re.compile(r"^app-(?:(?:flatpak|gnome|kde|snap|dbus)-)?(?P<id>.+?)(?:@[^.]*)?(?:-[0-9a-fA-F]+)?"
                         r"\.(?:scope|service)$")
# Onderdelen van BugOS zelf: die kun je niet per ongeluk beëindigen.
BESCHERMD = {"kwin_wayland", "kwin_x11", "plasmashell", "ksmserver", "kded6", "kded5", "plasma_session",
             "Xwayland", "systemd", "dbus-broker", "dbus-daemon", "startplasma-wayland", "startplasma-x11",
             "polkit-kde-authentication-agent-1", "xdg-desktop-portal", "xdg-desktop-portal-kde", "pipewire",
             "wireplumber", "pipewire-pulse", "bugos-task-manager", "sddm", "sddm-helper", "kwin_wayland_wrapper"}
# De kernel bewaart een procesnaam (comm) in maximaal 15 tekens: "xdg-desktop-portal-kde" heet daar
# "xdg-desktop-por". Vergelijk dus op die ingekorte naam, anders herkennen we lange namen nooit.
BESCHERMD_KORT = {naam[:15] for naam in BESCHERMD}
# Ook alles wat in een eenheid van het bureaublad zelf draait (plasma-*.service) of in de inlogsessie
# (session-*.scope, daar draait startplasma) hoort bij BugOS: stoppen sluit alle vensters.
# En wat de sessie onder water nodig heeft: de berichtenbus (dbus/dbus-broker, en wat die zelf start:
# dbus-:<id>-<naam>.service), het gebruikersbeheer (init.scope: systemd --user en (sd-pam)),
# toegankelijkheid voor schermlezers (at-spi), instellingen (dconf) en de Flatpak-portalen (xdg-*).
BESCHERMDE_EENHEID = re.compile(r"^(plasma-.+\.service|session-[^/]+\.scope|init\.scope|dbus(-broker)?\.service"
                                r"|dbus-:.+\.service|at-spi-dbus-bus\.service|dconf\.service|xdg-.+\.service)$")
BEKENDE_NAMEN = {  # achtergrond: gewone woorden in plaats van programmanamen
    "plasmashell": ("Bureaublad (Plasma)", "Desktop (Plasma)"),
    "kwin_wayland": ("Vensters (KWin)", "Windows (KWin)"),
    "pipewire": ("Geluid (PipeWire)", "Sound (PipeWire)"),
    "pipewire-pulse": ("Geluid (PipeWire)", "Sound (PipeWire)"),
    "wireplumber": ("Geluid (WirePlumber)", "Sound (WirePlumber)"),
    "baloo_file": ("Zoeken in je bestanden", "Searching your files"),
    "baloo_file_extractor": ("Zoeken in je bestanden", "Searching your files"),
    "kded6": ("KDE-diensten", "KDE services"),
    "xdg-desktop-portal": ("Portalen", "Portals"),
    "NetworkManager": ("Netwerk", "Network"),
    "bluetoothd": ("Bluetooth", "Bluetooth"),
    "cupsd": ("Printers", "Printers"),
    "flatpak-system-helper": ("Apps bijwerken (Flatpak)", "Updating apps (Flatpak)"),
    "rpm-ostree": ("BugOS bijwerken", "Updating BugOS"),
}


def proc() -> Path:
    return Path(os.environ.get("BUGOS_PROC", "/proc"))


def sys_map() -> Path:
    return Path(os.environ.get("BUGOS_SYS", "/sys"))


def lees(pad: Path) -> str:
    try:
        return pad.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ================================================================ systeem ===

def cpu_tijden() -> tuple[int, int]:
    """(bezig, totaal) in tikjes, voor alle kernen samen (uit /proc/stat)."""
    for regel in lees(proc() / "stat").splitlines():
        if regel.startswith("cpu "):
            getallen = [int(x) for x in regel.split()[1:9]]
            totaal = sum(getallen)
            rust = getallen[3] + (getallen[4] if len(getallen) > 4 else 0)
            return totaal - rust, totaal
    return 0, 0


def aantal_kernen() -> int:
    return sum(1 for r in lees(proc() / "stat").splitlines() if re.match(r"cpu\d+ ", r)) or (os.cpu_count() or 1)


def geheugen() -> tuple[int, int]:
    """(totaal, beschikbaar) in bytes (uit /proc/meminfo)."""
    waarden = {}
    for regel in lees(proc() / "meminfo").splitlines():
        delen = regel.split()
        if len(delen) >= 2 and delen[0] in ("MemTotal:", "MemAvailable:"):
            waarden[delen[0]] = int(delen[1]) * 1024
    return waarden.get("MemTotal:", 0), waarden.get("MemAvailable:", 0)


def schijf_tellers() -> tuple[int, int, int]:
    """(gelezen bytes, geschreven bytes, ms bezig van de drukste schijf) voor hele schijven."""
    lezen = schrijven = bezig = 0
    for regel in lees(proc() / "diskstats").splitlines():
        d = regel.split()
        if len(d) >= 13 and SCHIJF_NAAM.match(d[2]):
            lezen += int(d[5]) * 512
            schrijven += int(d[9]) * 512
            bezig = max(bezig, int(d[12]))
    return lezen, schrijven, bezig


def netwerk_tellers() -> tuple[int, int]:
    """(ontvangen, verstuurd) in bytes, zonder de interne netwerkjes (lo, docker, vpn ...)."""
    binnen = buiten = 0
    for regel in lees(proc() / "net" / "dev").splitlines()[2:]:
        if ":" not in regel:
            continue
        naam, rest = regel.split(":", 1)
        naam = naam.strip()
        if naam.startswith(NIET_NETWERK):
            continue
        d = rest.split()
        if len(d) >= 9:
            binnen += int(d[0])
            buiten += int(d[8])
    return binnen, buiten


def temperatuur() -> float | None:
    """De temperatuur van de processor in graden, als de computer die doorgeeft."""
    for map_ in sorted((sys_map() / "class" / "hwmon").glob("hwmon*")):
        if lees(map_ / "name").strip() in ("k10temp", "coretemp", "zenpower", "cpu_thermal", "acpitz"):
            waarde = lees(map_ / "temp1_input").strip()
            if waarde.lstrip("-").isdigit():
                return int(waarde) / 1000
    return None


def videokaart() -> float | None:
    """Hoe druk de videokaart is (0-100), als we dat kunnen zien (AMD via /sys, Nvidia via nvidia-smi)."""
    for kaart in sorted((sys_map() / "class" / "drm").glob("card[0-9]*")):
        waarde = lees(kaart / "device" / "gpu_busy_percent").strip()
        if waarde.isdigit():
            return float(waarde)
    if os.environ.get("BUGOS_PROC") is None and Path("/usr/bin/nvidia-smi").exists():
        try:
            uit = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=3).stdout.split()
            return float(uit[0]) if uit else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    return None


# ============================================================= processen ===

@dataclass
class Proces:
    pid: int
    naam: str           # korte naam (comm)
    ppid: int
    tijd: int           # gebruikte processortijd in tikjes (utime + stime)
    geheugen: int       # bytes (Pss als dat kan, anders RSS)
    eigen: bool         # van jou (dan mag je hem stoppen)
    groep: str          # het cgroup-pad


def processen() -> list[Proces]:
    lijst = []
    mijn = os.getuid()
    for map_ in proc().iterdir():
        if not map_.name.isdigit():
            continue
        stat = lees(map_ / "stat")
        if not stat or ")" not in stat:
            continue
        naam = stat[stat.find("(") + 1:stat.rfind(")")]
        rest = stat[stat.rfind(")") + 2:].split()
        if len(rest) < 22 or int(rest[6]) & PF_KTHREAD:
            continue
        try:
            eigen = map_.stat().st_uid == mijn
        except OSError:
            continue
        geheugen_ = 0
        if eigen:
            for regel in lees(map_ / "smaps_rollup").splitlines():
                if regel.startswith("Pss:"):
                    geheugen_ = int(regel.split()[1]) * 1024
                    break
        if not geheugen_:
            geheugen_ = int(rest[21]) * PAGINA
        groep = ""
        for regel in lees(map_ / "cgroup").splitlines():
            if regel.startswith("0::"):
                groep = regel[3:].strip()
        lijst.append(Proces(int(map_.name), naam, int(rest[1]), int(rest[11]) + int(rest[12]), geheugen_, eigen,
                            groep))
    return lijst


def ontsnap_terug(tekst: str) -> str:
    """systemd schrijft een '-' in een naam als \\x2d: maak daar weer gewone tekens van."""
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), tekst)


def soort_van(groep: str) -> tuple[str, str, str]:
    """(soort, sleutel, eenheid) bij een cgroup-pad.

    soort: "app" (een programma dat je zelf opende), "achtergrond" (van jou, maar geen venster)
    of "systeem" (van de computer zelf)."""
    delen = [d for d in groep.split("/") if d]
    if not delen or delen[0] in ("system.slice", "init.scope", "machine.slice") or not delen[0].startswith("user"):
        eenheid = delen[1] if len(delen) > 1 else (delen[0] if delen else "kernel")
        return "systeem", eenheid, eenheid
    for deel in delen:
        if deel.startswith("app-"):
            m = APP_EENHEID.match(deel)
            if m:
                return "app", ontsnap_terug(m.group("id")), deel
    eenheid = next((d for d in reversed(delen) if d.endswith((".service", ".scope"))), delen[-1])
    return "achtergrond", eenheid, eenheid


# ============================================================= groeperen ===

@dataclass
class Taak:
    sleutel: str
    naam: str
    icoon: str
    soort: str                     # app, achtergrond of systeem
    eenheid: str                   # de systemd-eenheid (om alles in één keer te stoppen)
    pids: list[int] = field(default_factory=list)
    processor: float = 0.0         # procent van de hele computer
    geheugen: int = 0              # bytes
    eigen: bool = False
    beschermd: bool = False        # hoort bij BugOS zelf: niet stoppen


class Meter:
    """Houdt de vorige meting bij, zodat we 'hoeveel per seconde' kunnen uitrekenen."""

    def __init__(self):
        self.vorige: dict | None = None

    def meet(self) -> dict:
        nu = time.monotonic()
        bezig, totaal = cpu_tijden()
        lezen, schrijven, schijf_ms = schijf_tellers()
        binnen, buiten = netwerk_tellers()
        lijst = processen()
        gezien = {"tijd": nu, "bezig": bezig, "totaal": totaal, "lezen": lezen, "schrijven": schrijven,
                  "schijf_ms": schijf_ms, "binnen": binnen, "buiten": buiten,
                  "proc": {p.pid: p.tijd for p in lijst}}
        v = self.vorige or gezien
        dt = max(nu - v["tijd"], 1e-6)
        d_totaal = max(totaal - v["totaal"], 1)
        proc_procent = {p.pid: max(p.tijd - v["proc"].get(p.pid, p.tijd), 0) / d_totaal * 100 for p in lijst}
        mem_totaal, mem_vrij = geheugen()
        uitslag = {
            "processor": (bezig - v["bezig"]) / d_totaal * 100 if self.vorige else 0.0,
            "geheugen_totaal": mem_totaal, "geheugen_gebruikt": max(mem_totaal - mem_vrij, 0),
            "schijf": ((lezen - v["lezen"]) + (schrijven - v["schrijven"])) / dt,
            "schijf_bezig": min((schijf_ms - v["schijf_ms"]) / (dt * 1000) * 100, 100) if self.vorige else 0.0,
            "binnen": (binnen - v["binnen"]) / dt, "buiten": (buiten - v["buiten"]) / dt,
            "temperatuur": temperatuur(), "videokaart": videokaart(),
            "taken": groepeer(lijst, proc_procent),
        }
        self.vorige = gezien
        return uitslag


def groepeer(lijst: list[Proces], procent: dict[int, float]) -> list[Taak]:
    taken: dict[tuple[str, str], Taak] = {}
    eigen_pid = os.getpid()
    for p in lijst:
        soort, sleutel, eenheid = soort_van(p.groep)
        if soort == "app":
            info = app_info(sleutel)
            naam, icoon = info if info else (mooie_naam(sleutel), "")
        else:
            sleutel = f"{soort}:{eenheid}:{p.naam}" if soort == "achtergrond" else f"{soort}:{eenheid}"
            bekend = BEKENDE_NAMEN.get(p.naam)
            naam, icoon = (t(*bekend) if bekend else p.naam), ""
        taak = taken.get((soort, sleutel))
        if taak is None:
            taak = taken[(soort, sleutel)] = Taak(sleutel, naam, icoon, soort, eenheid, eigen=p.eigen)
        taak.pids.append(p.pid)
        taak.processor += procent.get(p.pid, 0.0)
        taak.geheugen += p.geheugen
        taak.eigen = taak.eigen and p.eigen
        if (p.naam[:15] in BESCHERMD_KORT or p.pid == eigen_pid or soort == "systeem"
                or BESCHERMDE_EENHEID.match(eenheid)):
            taak.beschermd = True
    return sorted(taken.values(), key=lambda x: (x.soort != "app", x.naam.lower()))


def advies(processor: list[float], gebruikt: int, totaal: int, taken: list[Taak]) -> tuple[str, str]:
    """('goed' of 'let_op', een zin in gewone woorden over hoe het gaat)."""
    apps = [x for x in taken if x.soort == "app"] or taken
    if totaal and gebruikt / totaal > 0.9:
        zwaarste = max(apps, key=lambda x: x.geheugen, default=None)
        wie = t(f" {zwaarste.naam} gebruikt het meeste.", f" {zwaarste.naam} uses the most.") if zwaarste else ""
        return "let_op", t("Het geheugen is bijna vol. Sluit een paar programma's die je niet gebruikt." + wie,
                           "Memory is almost full. Close a few programs you are not using." + wie)
    laatste = processor[-3:]
    if len(laatste) == 3 and min(laatste) > 85:
        zwaarste = max(apps, key=lambda x: x.processor, default=None)
        wie = t(f" {zwaarste.naam} gebruikt de meeste kracht.", f" {zwaarste.naam} uses the most power.") \
            if zwaarste else ""
        return "let_op", t("Je computer heeft het druk." + wie, "Your computer is busy." + wie)
    return "goed", t("Alles loopt soepel.", "Everything is running smoothly.")


def stop(pids: list[int], hard: bool = False) -> int:
    """Stuur een stopsignaal (netjes: TERM, of hard: KILL). Geeft terug hoeveel dat lukte."""
    gelukt = 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL if hard else signal.SIGTERM)
            gelukt += 1
        except OSError:
            pass
    return gelukt


def leeft(pids: list[int]) -> list[int]:
    return [pid for pid in pids if (proc() / str(pid)).exists()]


def sluit_script(pids: list[int]) -> str:
    """Een KWin-scriptje dat de vensters van deze programma's sluit, net als op het kruisje klikken."""
    return ("const pids = new Set(%s);\n"
            "for (const w of workspace.windowList()) {\n"
            "    if (pids.has(w.pid)) { w.closeWindow(); }\n"
            "}\n") % json.dumps(sorted(pids))


# ================================================================ maten ===

def snelheid(n: float) -> str:
    """Hoeveel per seconde, in gewone woorden ('rustig' als er bijna niets gebeurt)."""
    return maat(n) + "/s" if n >= 1000 else t("rustig", "idle")
