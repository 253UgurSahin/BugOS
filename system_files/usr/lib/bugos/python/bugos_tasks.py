"""BugOS Taakbeheer: wat doet je computer? (zonder extra onderdelen; alles komt uit /proc en /sys)

Programma's worden per app gegroepeerd zoals KDE ze start: elk programma draait in zijn
eigen systemd-groep (bijvoorbeeld app-org.mozilla.firefox-1234.scope). Zo hoort alles van
Firefox bij elkaar, ook de losse tabbladen.

Voor tests en foto's kan een nep-/proc gebruikt worden: BUGOS_PROC=/pad/naar/proc.

Namen van apps en 'Opstarten' komen uit de .desktop-bestanden: dat staat in bugos_desktop.

De pagina Details (voor wie helpt) toont elk proces los: details() maakt de regels, beeindig() stopt er een. Een
proces van een ander (root, een ander account) kan niemand hier stoppen: dat weigert de kernel zelf al.
"""

from __future__ import annotations

import json
import os
import pwd
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
# Hulpjes die bij het inloggen vanzelf starten (…@autostart) en geen venster hebben: geen "programma dat je
# opende", dus bij de achtergrond (anders stonden Geoclue, KDE Connect en de Xwayland-brug bij je programma's).
AUTOSTART_HULPJES = {"geoclue-demo-agent", "org.kde.kdeconnect.daemon", "org.kde.xwaylandvideobridge",
                     "xembedsniproxy", "gmenudbusmenuproxy", "kaccess", "org.kde.kunifiedpush-distributor",
                     "polkit-kde-authentication-agent-1", "powerdevil", "baloo_file", "spice-vdagent",
                     "at-spi-dbus-bus", "pam_kwallet_init", "xdg-user-dirs", "orca-autostart", "vboxclient",
                     "vmware-user", "kxkb2locale1", "org.kde.plasma-fallback-session-restore",
                     "bugos-panel", "bugos-theme", "bugos-light-mode", "bugos-open-drives"}
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


def mijn_uid() -> int:
    """Wie ben jij (het nummer van je account)? Op één plek, zodat een test als 'gewone gebruiker' kan draaien,
    ook in een testcontainer die als root draait (review 5)."""
    return os.getuid()


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
    # De echte processorsensor eerst; acpitz (de moederbord-sensor) alleen als er niets anders is. De volgorde van
    # hwmon0, hwmon1 ... verschilt per opstart, dus niet de eerste nemen die we tegenkomen (U400).
    voorkeur = ("k10temp", "zenpower", "coretemp", "cpu_thermal", "acpitz")
    gevonden: dict[str, float] = {}
    for map_ in sorted((sys_map() / "class" / "hwmon").glob("hwmon*")):
        naam = lees(map_ / "name").strip()
        if naam in voorkeur and naam not in gevonden:
            waarde = lees(map_ / "temp1_input").strip()
            if waarde.lstrip("-").isdigit():
                gevonden[naam] = int(waarde) / 1000
    return next((gevonden[n] for n in voorkeur if n in gevonden), None)


def videokaart() -> float | None:
    """Hoe druk de videokaart is (0-100), als we dat kunnen zien (AMD via /sys, Nvidia via nvidia-smi)."""
    # Alle kaarten bekijken en de drukste tonen: een laptop met AMD-processor en een Nvidia-kaart toonde anders altijd
    # de ingebouwde AMD, ook tijdens een game op de Nvidia (U406).
    waarden: list[float] = []
    nvidia_wakker = None   # None: geen Nvidia-kaart in /sys gezien
    for kaart in sorted((sys_map() / "class" / "drm").glob("card[0-9]*")):
        if "-" in kaart.name:
            continue   # card0-HDMI-A-1 enz.: een aansluiting, geen kaart
        waarde = lees(kaart / "device" / "gpu_busy_percent").strip()
        if waarde.isdigit():
            waarden.append(float(waarde))
        elif lees(kaart / "device" / "vendor").strip() == "0x10de":
            # Een slapende Nvidia-kaart niet wakker maken met nvidia-smi (kost accu); slaapt hij, dan doet hij niets.
            wakker = lees(kaart / "device" / "power" / "runtime_status").strip() != "suspended"
            nvidia_wakker = wakker or bool(nvidia_wakker)
    # Intel heeft geen gpu_busy_percent: dan ook geen nvidia-smi als de Nvidia-kaart slaapt (Optimus-laptop) (U421).
    if (nvidia_wakker or (nvidia_wakker is None and not waarden)) and os.environ.get("BUGOS_PROC") is None and Path("/usr/bin/nvidia-smi").exists():
        try:
            uit = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=3).stdout.split()
            waarden += [float(w) for w in uit if w.replace(".", "", 1).isdigit()]
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return max(waarden) if waarden else None


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
    uid: int = -1       # van welk account (de echte gebruiker uit 'Uid:'), -1 als onbekend
    start: int = 0      # wanneer hij begon (tikjes na het opstarten): zo herken je een hergebruikt nummer
    staat: str = ""     # R (bezig), S (wacht), Z (zombie: al gestopt) ...


def processen() -> list[Proces]:
    lijst = []
    mijn = mijn_uid()
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
        # Van wie is hij? De echte gebruiker (Uid: in status), niet de eigenaar van /proc/<pid>: die is root voor
        # programma's met extra rechten (gamescope) en voor ssh-agent, ook al zijn ze van jou (U451).
        uid = next((r.split()[1] for r in lees(map_ / "status").splitlines() if r.startswith("Uid:")), "")
        try:
            uid_ = int(uid) if uid.isdigit() else map_.stat().st_uid
        except OSError:
            continue
        eigen = uid_ == mijn
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
                            groep, uid_, int(rest[19]) if rest[19].isdigit() else 0, rest[0]))
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
                app_id = ontsnap_terug(m.group("id"))
                if "@autostart" in deel and app_id in AUTOSTART_HULPJES:
                    return "achtergrond", app_id, deel
                return "app", app_id, deel
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
        # De getallen van de laatste echte meting (voor een meting die te kort na de vorige komt).
        self.procent: dict[int, float] = {}
        self.snelheid = {"processor": 0.0, "schijf": 0.0, "schijf_bezig": 0.0, "binnen": 0.0, "buiten": 0.0}

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
        # Twee metingen vlak na elkaar (het venster komt net in beeld, en meet dan meteen opnieuw): dan zijn er te
        # weinig tikjes om eerlijk te delen, en kwam er bijvoorbeeld '300%' uit voor Taakbeheer zelf. Dan houden we
        # de getallen van de vorige meting, en meten we de volgende keer verder vanaf de oude (langere) basis.
        te_kort = self.vorige is not None and d_totaal < 10 * aantal_kernen()
        if te_kort:
            proc_procent = {p.pid: self.procent.get(p.pid, 0.0) for p in lijst}
            snel = dict(self.snelheid)
        else:
            # Nooit meer dan de hele computer (100%), en nooit minder dan niets.
            proc_procent = {p.pid: min(max(p.tijd - v["proc"].get(p.pid, p.tijd), 0) / d_totaal * 100, 100.0)
                            for p in lijst}
            snel = {
                "processor": min(max((bezig - v["bezig"]) / d_totaal * 100, 0.0), 100.0) if self.vorige else 0.0,
                "schijf": max(((lezen - v["lezen"]) + (schrijven - v["schrijven"])) / dt, 0.0),
                "schijf_bezig": min(max((schijf_ms - v["schijf_ms"]) / (dt * 1000) * 100, 0.0), 100.0)
                if self.vorige else 0.0,
                "binnen": max((binnen - v["binnen"]) / dt, 0.0), "buiten": max((buiten - v["buiten"]) / dt, 0.0),
            }
        mem_totaal, mem_vrij = geheugen()
        taken = groepeer(lijst, proc_procent)
        uitslag = {
            **snel,
            "geheugen_totaal": mem_totaal, "geheugen_gebruikt": max(mem_totaal - mem_vrij, 0),
            "temperatuur": temperatuur(), "videokaart": videokaart(),
            "taken": taken,
            "processen": details(lijst, proc_procent, taken),
        }
        if not te_kort:
            self.vorige = gezien
            self.procent, self.snelheid = proc_procent, snel
        return uitslag


def _ander_account(groep: str) -> bool:
    """Hoort dit proces bij de sessie van een ander account (user-<nummer>.slice)? Niet: 'niet van jou volgens /proc':
    programma's met extra rechten (kwin_wayland) of ssh-agent zijn daar van root, maar wel van jou (U441)."""
    m = re.search(r"/user-(\d+)\.slice(?:/|$)", groep)
    return bool(m) and int(m.group(1)) != mijn_uid()


def groepeer(lijst: list[Proces], procent: dict[int, float]) -> list[Taak]:
    taken: dict[tuple[str, str], Taak] = {}
    eigen_pid = os.getpid()
    for p in lijst:
        soort, sleutel, eenheid = soort_van(p.groep)
        if soort != "systeem" and _ander_account(p.groep):
            # Van een ander account (snel wisselen): niet bij jouw Firefox optellen (dan kon je die niet sluiten),
            # maar samen onder 'Andere accounts', bij wat van de computer is (U433).
            soort, sleutel, eenheid = "systeem", "systeem:andere-accounts", "andere-accounts"
            naam, icoon = t("Andere accounts", "Other accounts"), ""
        elif soort == "app":
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
        # Een 'sudo' of 'pkexec' in je eigen Konsole of Instellingen (van root) maakt die niet onsluitbaar (U451).
        # Ook als de sudo eerder in de lijst staat dan Konsole: één proces van jou is genoeg (U463).
        if soort == "systeem":
            taak.eigen = taak.eigen and p.eigen
        elif taak.pids == [p.pid]:
            taak.eigen = p.eigen
        else:
            taak.eigen = taak.eigen or p.eigen
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


# ================================================================ details ===
# De pagina Details: elk proces los, zoals 'Details' in Taakbeheer van Windows. Voor wie helpt ("draait er iets dat
# Isolated Web Co heet?"). Dezelfde regels als hierboven: wat bij BugOS hoort of niet van jou is, kun je niet stoppen.

_NAMEN: dict[int, str] = {}   # uid -> loginnaam (verandert niet terwijl Taakbeheer open is)


def volle_naam(pid: int, comm: str) -> str:
    """De kernel kort een procesnaam in tot 15 tekens ('xdg-desktop-por'). Dan de naam van het programma zelf
    (/usr/libexec/xdg-desktop-portal-kde), als die met de korte naam begint. Een programma dat zijn titel
    herschrijft ('systemd-userwork: waiting...') houdt alleen het eerste woord (review 13). Anders de korte naam:
    firewalld draait als /usr/bin/python3, en Firefox noemt zijn tabbladen zelf 'Isolated Web Co'."""
    if len(comm) != 15:
        return comm
    eerste = lees(proc() / str(pid) / "cmdline").split("\0", 1)[0]
    naam = re.split(r"[\s:]", os.path.basename(eerste), maxsplit=1)[0] if eerste else ""
    return naam if naam.startswith(comm) else comm


def eigenaar_naam(uid: int) -> str:
    """Van wie: 'jij', 'systeem' (root) of de naam van het account (polkitd, een ander gezinslid)."""
    if uid < 0:
        return "?"
    if uid == mijn_uid():
        return t("jij", "you")
    if uid == 0:
        return t("systeem", "system")
    if uid not in _NAMEN:
        try:
            _NAMEN[uid] = pwd.getpwuid(uid).pw_name
        except (KeyError, OverflowError):
            _NAMEN[uid] = str(uid)
    return _NAMEN[uid]


def proces_beschermd(p: Proces) -> bool:
    """Mag dit ene proces niet gestopt worden? Dezelfde regels als groepeer() per taak."""
    soort, _sleutel, eenheid = soort_van(p.groep)
    return (not p.eigen or _ander_account(p.groep) or p.naam[:15] in BESCHERMD_KORT or p.pid == os.getpid()
            or soort == "systeem" or bool(BESCHERMDE_EENHEID.match(eenheid)))


@dataclass
class ProcesRegel:
    """Eén regel op de pagina Details."""
    pid: int
    naam: str
    uid: int
    eigenaar: str        # 'jij', 'systeem' of een loginnaam
    hoort_bij: str       # de naam van de taak (Firefox, Netwerk ...), leeg als die gelijk is aan de naam
    processor: float     # procent van de hele computer
    geheugen: int        # bytes
    eigen: bool          # van jou
    beschermd: bool      # kan hier niet gestopt worden
    start: int           # om een hergebruikt procesnummer te herkennen
    app: bool = False    # hoort bij een programma met een venster (dan eerst netjes sluiten)


def details(lijst: list[Proces], procent: dict[int, float], taken: list[Taak]) -> list[ProcesRegel]:
    """Een regel per proces, met de taak waar hij bij hoort (zoals op de pagina Programma's)."""
    taak_van = {pid: taak for taak in taken for pid in taak.pids}
    comm = {p.pid: p.naam for p in lijst}
    regels = []
    for p in lijst:
        naam = volle_naam(p.pid, p.naam)
        taak = taak_van.get(p.pid)
        hoort_bij = ""
        if taak is not None:
            hoort_bij = taak.naam
            eerste = taak.pids[0] if taak.pids else p.pid
            if hoort_bij == comm.get(eerste):   # een systeemtaak zonder eigen woord: de volle naam (review 12)
                hoort_bij = volle_naam(eerste, hoort_bij)
            if hoort_bij == naam:
                hoort_bij = ""                 # alleen de naam nog eens: dan liever niets
        regels.append(ProcesRegel(p.pid, naam, p.uid, eigenaar_naam(p.uid), hoort_bij, procent.get(p.pid, 0.0),
                                  p.geheugen, p.eigen, proces_beschermd(p), p.start,
                                  bool(taak and taak.soort == "app")))
    return regels


def zelfde_proces(pid: int, start: int) -> bool:
    """Draait dit nummer nog, en is het nog hetzelfde proces (zelfde starttijd)? Een zombie (Z) is al gestopt."""
    stat = lees(proc() / str(pid) / "stat")
    if ")" not in stat:
        return False
    rest = stat[stat.rfind(")") + 2:].split()
    if len(rest) < 20 or rest[0] == "Z" or not rest[19].isdigit():
        return False
    return int(rest[19]) == start


def _signaal(pid: int, start: int, sig: int) -> None:
    """Stuur het signaal. Op de echte computer via een pidfd: dan kan het nummer tussen kijken en stoppen niet
    ineens van een ander proces zijn (review 15)."""
    if str(proc()) == "/proc" and hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        fd = os.pidfd_open(pid)
        try:
            if not zelfde_proces(pid, start):
                raise ProcessLookupError(pid)
            signal.pidfd_send_signal(fd, sig)
        finally:
            os.close(fd)
        return
    os.kill(pid, sig)


def beeindig(regel: ProcesRegel, hard: bool = False) -> str:
    """Eén proces stoppen: netjes (TERM) of hard (KILL). Geeft 'klaar', 'weg' (draait niet meer, of het nummer is
    nu van een ander proces), 'beschermd', 'mag_niet' (niet van jou) of 'fout'."""
    if regel.beschermd:
        return "beschermd"
    if not zelfde_proces(regel.pid, regel.start):
        return "weg"
    try:
        _signaal(regel.pid, regel.start, signal.SIGKILL if hard else signal.SIGTERM)
    except ProcessLookupError:
        return "weg"
    except PermissionError:
        return "mag_niet"
    except OSError:
        return "fout"
    return "klaar"


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
