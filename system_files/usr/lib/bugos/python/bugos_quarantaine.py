"""BugOS Quarantaine: een app proberen zonder dat hij bij je spullen kan (de logica, zonder venster).

Wat de app in quarantaine ziet:
- een eigen, lege thuismap (een map op de schijf, niet jouw thuismap); alles wat hij schrijft, komt daar;
- het systeem (/usr, /etc) alleen om te lezen; /tmp, /var en /run zijn leeg;
- internet alleen als je dat aanzet (anders alleen 'localhost');
- het scherm (Wayland en X11), geluid (PipeWire) en de videokaart, anders kan hij niets laten zien;
- geen D-Bus: hij kan geen andere programma's aansturen, geen meldingen sturen en niet bij je wachtwoorden (KWallet).

Hoe: bubblewrap (bwrap), dat BugOS al heeft omdat Flatpak het gebruikt. Een Flatpak-app heeft al zijn eigen doos:
die starten we met 'flatpak run' zonder toegang tot je bestanden (--nofilesystem=host:reset) en met zijn gegevens
(~/.var/app/<id>) in de quarantainemap, door flatpak een andere HOME te geven (FLATPAK_USER_DIR wijst nog naar je
echte Flatpak-apps).

Eerlijk over de grens: dit is goed om te testen ('wat schrijft deze app, en waar?'), maar het is geen virtuele
machine. Dezelfde kernel, en via X11 kan een programma andere X11-vensters zien. Echt kwaadaardige software hoort in
een virtuele machine.

Alles hier is gewone Python zonder Qt, zodat tools/test_quarantaine.py het kan nagaan.
"""

from __future__ import annotations

import configparser
import os
import re
import shlex
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

# Een Flathub-id (org.voorbeeld.App), zoals APP_ID in bugos_apps.py.
FLATPAK_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}$")
# Veldcodes in Exec= van een .desktop-bestand (%f, %U ...): die vult de starter in; in quarantaine laten we ze weg.
VELDCODE = re.compile(r"^%[fFuUdDnNickvm]$")


def thuis() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def bewaar_map() -> Path:
    """Waar bewaarde quarantaines staan (je kunt er later mee verder)."""
    data = os.environ.get("XDG_DATA_HOME") or str(thuis() / ".local" / "share")
    return Path(data) / "bugos" / "quarantaine"


def tijdelijke_map() -> Path:
    """Waar een quarantaine draait die je na afloop weggooit. Op de schijf (niet in het geheugen): een installatie
    kan honderden MB schrijven."""
    cache = os.environ.get("XDG_CACHE_HOME") or str(thuis() / ".cache")
    return Path(cache) / "bugos" / "quarantaine"


def slug(naam: str) -> str:
    """Een veilige mapnaam: 'Google Chrome' -> 'google-chrome'."""
    s = re.sub(r"[^a-z0-9]+", "-", naam.lower()).strip("-")
    return s[:40] or "app"


@dataclass
class Doel:
    """Wat er in quarantaine start.
    soort: 'flatpak' (id), 'wine' (.exe/.msi), 'appimage', 'programma' (een opdracht met argumenten)."""
    soort: str
    naam: str
    opdracht: list[str] = field(default_factory=list)   # programma: de opdracht; anders leeg
    bestand: str = ""        # wine/appimage: het bestand zelf
    flatpak: str = ""        # flatpak: het id
    terminal: bool = False   # .desktop met Terminal=true


def _desktop_naam(cfg: configparser.RawConfigParser, taal: str) -> str:
    for sleutel in (f"Name[{taal}]", "Name"):
        if cfg.has_option("Desktop Entry", sleutel):
            return cfg.get("Desktop Entry", sleutel)
    return ""


def exec_argumenten(regel: str) -> list[str]:
    """Exec= uit een .desktop-bestand als lijst, zonder veldcodes (%u, %F ...). '%%' wordt '%'."""
    try:
        delen = shlex.split(regel)
    except ValueError:
        return []
    return [d.replace("%%", "%") for d in delen if not VELDCODE.match(d)]


def lees_desktop(pad: str, taal: str = "") -> Doel | None:
    """Een .desktop-bestand (uit het startmenu) als Doel. Een Flatpak-app (X-Flatpak=) wordt 'flatpak'."""
    cfg = configparser.RawConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str   # 'Name[nl]' en 'Exec' met hoofdletters zoals in het bestand
    try:
        cfg.read(pad, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    if not cfg.has_section("Desktop Entry"):
        return None
    naam = _desktop_naam(cfg, taal) or Path(pad).stem
    flatpak = cfg.get("Desktop Entry", "X-Flatpak", fallback="").strip()
    if flatpak and FLATPAK_ID.match(flatpak):
        return Doel("flatpak", naam, flatpak=flatpak)
    opdracht = exec_argumenten(cfg.get("Desktop Entry", "Exec", fallback=""))
    if not opdracht:
        return None
    terminal = cfg.get("Desktop Entry", "Terminal", fallback="false").strip().lower() == "true"
    return Doel("programma", naam, opdracht=opdracht, terminal=terminal)


def is_flatpak(app_id: str) -> bool:
    if not FLATPAK_ID.match(app_id) or not shutil.which("flatpak"):
        return False
    import subprocess
    try:
        return subprocess.run(["flatpak", "info", app_id], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def bepaal_doel(wat: str, args: list[str], taal: str = "") -> Doel | None:
    """Wat moet er in quarantaine? Een .desktop-bestand, een .exe/.msi, een .AppImage, een Flatpak-id, of een
    programma (naam op PATH of een pad). None: dat kunnen we niet starten."""
    klein = wat.lower()
    if klein.endswith(".desktop") and os.path.isfile(wat):
        doel = lees_desktop(wat, taal)
        if doel is not None and doel.soort == "programma":
            doel.opdracht += args
        return doel
    if klein.endswith((".exe", ".msi")) and os.path.isfile(wat):
        return Doel("wine", Path(wat).name, bestand=os.path.abspath(wat))
    if klein.endswith(".appimage") and os.path.isfile(wat):
        return Doel("appimage", Path(wat).name, bestand=os.path.abspath(wat))
    if "/" not in wat and is_flatpak(wat):
        return Doel("flatpak", wat.rsplit(".", 1)[-1], flatpak=wat)
    if "/" in wat:
        if os.path.isfile(wat) and os.access(wat, os.X_OK):
            return Doel("programma", Path(wat).name, opdracht=[os.path.abspath(wat)] + args)
        return None
    if shutil.which(wat):
        return Doel("programma", wat, opdracht=[wat] + args)
    return None


def apps_om_te_proberen() -> list[tuple[str, str, str]]:
    """De apps uit het startmenu die je in quarantaine kunt proberen: [(naam, pictogram, pad naar .desktop)], op naam.
    Niet: verborgen starters (NoDisplay, Hidden), geen Type=Application, en de onderdelen van BugOS zelf. Een app die
    in meer mappen staat (eigen map gaat voor), telt één keer."""
    from bugos_desktop import app_mappen, lees_bureaublad, vertaald
    gezien: dict[str, tuple[str, str, str]] = {}
    for map_ in app_mappen():
        try:
            bestanden = sorted(map_.glob("*.desktop"))
        except OSError:
            continue
        for pad in bestanden:
            if pad.name in gezien or pad.name.startswith("bugos-"):
                continue
            c = lees_bureaublad(pad)
            if c is None:
                gezien[pad.name] = ("", "", "")
                continue
            sec = c["Desktop Entry"]
            if (sec.get("Type", "Application") != "Application" or sec.get("NoDisplay", "").lower() == "true"
                    or sec.get("Hidden", "").lower() == "true" or not sec.get("Exec", "").strip()):
                gezien[pad.name] = ("", "", "")
                continue
            gezien[pad.name] = (vertaald(sec, "Name") or pad.stem, sec.get("Icon", ""), str(pad))
    return sorted((a for a in gezien.values() if a[2]), key=lambda a: a[0].lower())


def nieuwe_map(doel: Doel, bewaard: str = "") -> Path:
    """De quarantainemap (met home/ erin). bewaard: de naam van een bewaarde quarantaine om mee verder te gaan."""
    if bewaard:
        if "/" in bewaard or bewaard.startswith("."):
            raise ValueError("ongeldige naam")
        map_ = bewaar_map() / bewaard
    else:
        map_ = tijdelijke_map() / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug(doel.naam)}-{os.getpid()}"
    (map_ / "home").mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(map_, 0o700)
    except OSError:
        pass
    return map_


def _runtime() -> str:
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def bwrap_opdracht(binnen: list[str], home: Path, internet: bool, extra_ro: list[str] | None = None,
                   terminal: bool = False, extra_env: dict[str, str] | None = None) -> list[str]:
    """De opdracht voor bubblewrap. binnen: wat er in de doos start. home: de quarantaine-thuismap.
    extra_ro: bestanden die de app mag lezen (bijv. de .exe zelf); die komen in ~/Quarantaine/ in de doos."""
    echt_thuis = os.environ.get("HOME") or str(Path.home())
    thuis_doel = os.path.realpath(echt_thuis)
    rt = _runtime()
    a = ["bwrap", "--die-with-parent",
         "--unshare-user-try", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try",
         "--hostname", "quarantaine"]
    if not internet:
        a.append("--unshare-net")
    if not terminal:
        # Geen gedeelde terminal: een programma kan dan geen toetsen in jouw terminal 'typen' (TIOCSTI).
        a.append("--new-session")
    a += ["--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc"]
    for naam in ("bin", "sbin", "lib", "lib64"):
        if os.path.islink(f"/{naam}"):
            a += ["--symlink", os.readlink(f"/{naam}"), f"/{naam}"]
        elif os.path.isdir(f"/{naam}"):
            a += ["--ro-bind", f"/{naam}", f"/{naam}"]
    a += ["--ro-bind-try", "/opt", "/opt",
          "--proc", "/proc", "--dev", "/dev", "--dev-bind-try", "/dev/dri", "/dev/dri",
          "--tmpfs", "/tmp", "--tmpfs", "/var", "--tmpfs", "/run",
          # De naamserver (resolv.conf wijst daarheen op Fedora), anders werkt internet zonder namen.
          "--ro-bind-try", "/run/systemd/resolve", "/run/systemd/resolve",
          "--ro-bind-try", "/run/NetworkManager/resolv.conf", "/run/NetworkManager/resolv.conf"]
    # Op Fedora Atomic is /home een verwijzing naar var/home: dezelfde verwijzing in de doos.
    if os.path.islink("/home"):
        a += ["--symlink", os.readlink("/home"), "/home"]
    a += ["--bind", str(home), thuis_doel]
    # Het scherm en het geluid: alleen de sockets, in een eigen, lege runtime-map.
    a += ["--perms", "0700", "--dir", rt]
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    if wayland:
        pad = wayland if wayland.startswith("/") else os.path.join(rt, wayland)
        a += ["--ro-bind-try", pad, pad]
    for sok in ("pipewire-0", "pulse/native"):
        a += ["--ro-bind-try", os.path.join(rt, sok), os.path.join(rt, sok)]
    if os.environ.get("DISPLAY"):
        a += ["--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix"]
        xauth = os.environ.get("XAUTHORITY", "")
        if xauth:
            a += ["--ro-bind-try", xauth, xauth]
    for bestand in extra_ro or []:
        a += ["--ro-bind", bestand, os.path.join(thuis_doel, "Quarantaine", Path(bestand).name)]
    a += ["--chdir", thuis_doel,
          "--unsetenv", "DBUS_SESSION_BUS_ADDRESS", "--unsetenv", "SSH_AUTH_SOCK",
          "--setenv", "BUGOS_QUARANTAINE", "1"]
    for k, v in (extra_env or {}).items():
        a += ["--setenv", k, v]
    return a + ["--"] + binnen


def binnen_pad(bestand: str) -> str:
    """Waar een extra bestand (de .exe, de AppImage) in de doos staat."""
    echt_thuis = os.path.realpath(os.environ.get("HOME") or str(Path.home()))
    return os.path.join(echt_thuis, "Quarantaine", Path(bestand).name)


def opdracht(doel: Doel, home: Path, internet: bool, terminal: bool = False) -> tuple[list[str], dict[str, str]]:
    """(opdracht, extra omgeving voor de opdracht zelf) om doel in quarantaine te starten."""
    if doel.soort == "flatpak":
        echt = thuis()
        omgeving = {
            "HOME": str(home),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            # Je echte Flatpak-apps (die van jou alleen); die van de computer vindt flatpak altijd.
            "FLATPAK_USER_DIR": os.environ.get("FLATPAK_USER_DIR") or str(echt / ".local" / "share" / "flatpak"),
        }
        cmd = ["flatpak", "run", "--nofilesystem=host:reset", "--nosocket=session-bus", "--nosocket=system-bus",
               "--nosocket=ssh-auth", "--env=BUGOS_QUARANTAINE=1"]
        if not internet:
            cmd.append("--unshare=network")
        return cmd + [doel.flatpak], omgeving
    if doel.soort == "wine":
        exe = binnen_pad(doel.bestand)
        wijn = ["wine", "msiexec", "/i", exe] if doel.bestand.lower().endswith(".msi") \
            else ["wine", "start", "/wait", "/unix", exe]
        env = {"WINEPREFIX": os.path.join(os.path.realpath(str(thuis())), ".wine"), "WINEDEBUG": "-all"}
        return bwrap_opdracht(wijn, home, internet, [doel.bestand], terminal, env), {}
    if doel.soort == "appimage":
        # Zonder FUSE (dat werkt niet in de doos): de AppImage pakt zich uit in /tmp en start dan.
        env = {"APPIMAGE_EXTRACT_AND_RUN": "1"}
        return bwrap_opdracht([binnen_pad(doel.bestand)], home, internet, [doel.bestand], terminal, env), {}
    return bwrap_opdracht(list(doel.opdracht), home, internet, None, terminal), {}


def omvang(map_: Path) -> tuple[int, int]:
    """(aantal bestanden, bytes) in map_: wat de app schreef. Verwijzingen volgen we niet."""
    n = grootte = 0
    for wortel, _mappen, bestanden in os.walk(map_, followlinks=False):
        for b in bestanden:
            try:
                grootte += os.lstat(os.path.join(wortel, b)).st_size
                n += 1
            except OSError:
                pass
    return n, grootte


def maat_tekst(b: int) -> str:
    for eenheid in ("B", "KB", "MB", "GB"):
        if b < 1000 or eenheid == "GB":
            return f"{b:.0f} {eenheid}" if eenheid == "B" else f"{b:.1f} {eenheid}"
        b /= 1000
    return f"{b:.1f} GB"


def weggooien(map_: Path) -> None:
    """De quarantainemap weg. Alleen binnen onze eigen mappen, nooit iets anders."""
    map_ = Path(map_)
    for basis in (tijdelijke_map(), bewaar_map()):
        try:
            map_.resolve().relative_to(basis.resolve())
        except ValueError:
            continue
        if map_.resolve() != basis.resolve():
            # Mappen zonder schrijfrecht (Wine en sommige installers maken die) eerst weer van jou maken.
            for wortel, mappen, _b in os.walk(map_, followlinks=False):
                for m in mappen:
                    pad = os.path.join(wortel, m)
                    if not os.path.islink(pad):
                        try:
                            os.chmod(pad, 0o700)
                        except OSError:
                            pass
            shutil.rmtree(map_, ignore_errors=True)
            return
    raise ValueError(f"niet een quarantainemap: {map_}")


def bewaren(map_: Path, naam: str) -> Path:
    """Een tijdelijke quarantaine bewaren onder naam (in bewaar_map); geeft de nieuwe plek."""
    doel = bewaar_map() / slug(naam)
    basis, i = doel, 2
    while doel.exists():
        doel = Path(f"{basis}-{i}")
        i += 1
    doel.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(map_), str(doel))
    return doel


def bewaarde(naam_begin: str = "") -> list[Path]:
    """De bewaarde quarantaines (nieuwste eerst), eventueel alleen die van één app (naam_begin = slug)."""
    try:
        mappen = [p for p in bewaar_map().iterdir() if p.is_dir() and (p / "home").is_dir()]
    except OSError:
        return []
    if naam_begin:
        mappen = [p for p in mappen if p.name == naam_begin or p.name.startswith(naam_begin + "-")]
    return sorted(mappen, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
