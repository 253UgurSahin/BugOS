"""BugOS: Linux-programma's van een website (AppImage) installeren, openen en verwijderen. De logica, zonder venster.

Een AppImage is één bestand met een heel programma erin (zoals een 'portable' .exe op Windows). Zonder BugOS moet je
het eerst 'uitvoerbaar' maken, en het komt nooit in je startmenu. Met BugOS: dubbelklik, 'Installeren', en het staat
in het startmenu met zijn eigen naam en pictogram, en je haalt het weer weg in Instellingen > Geïnstalleerde apps.

- Het programma komt in ~/.local/share/bugos/appimages/<id>.AppImage (uit je home verplaatst, van een USB-stick
  gekopieerd), het pictogram in .../icons/, de starter in ~/.local/share/applications/bugos-appimage-<id>.desktop
  met X-BugOS-AppImage=<pad>.
- Naam, pictogram en categorie komen uit het programma zelf ('--appimage-extract', de standaard van AppImage, zonder
  FUSE). Een nieuwere versie van hetzelfde programma vervangt de oude.
- FUSE 2 (libfuse.so.2) ontbreekt? Dan start BugOS het met APPIMAGE_EXTRACT_AND_RUN=1 (trager, maar het werkt).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

VOORVOEGSEL = "bugos-appimage-"
SLEUTEL = "X-BugOS-AppImage"
# Waar libfuse.so.2 kan staan (Fedora: fuse-libs). BUGOS_LIBFUSE2 alleen voor de test.
LIBFUSE2 = [os.environ["BUGOS_LIBFUSE2"]] if os.environ.get("BUGOS_LIBFUSE2") else [
    "/usr/lib64/libfuse.so.2", "/lib64/libfuse.so.2", "/usr/lib/libfuse.so.2", "/usr/lib/x86_64-linux-gnu/libfuse.so.2"]


def data_map() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def apps_map() -> Path:
    return data_map() / "bugos" / "appimages"


def starters_map() -> Path:
    return data_map() / "applications"


def soort(pad: str | Path) -> int:
    """2 of 1 voor een AppImage (type 2 of 1), 0 als het er geen is. Een AppImage is een ELF-programma met 'AI' en
    het type op plek 8 (de AppImage-specificatie)."""
    try:
        with open(pad, "rb") as f:
            kop = f.read(11)
    except OSError:
        return 0
    if kop[:4] != b"\x7fELF" or kop[8:10] != b"AI" or kop[10:11] not in (b"\x01", b"\x02"):
        return 0
    return kop[10]


def is_appimage(pad: str | Path) -> bool:
    return Path(pad).is_file() and soort(pad) > 0


def fuse2_er() -> bool:
    return any(os.path.exists(p) for p in LIBFUSE2)


def omgeving() -> dict[str, str]:
    """De omgeving om een AppImage te starten: zonder FUSE 2 uitpakken en dan starten."""
    env = dict(os.environ)
    if not fuse2_er():
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    return env


def maak_uitvoerbaar(pad: Path) -> bool:
    try:
        pad.chmod(pad.stat().st_mode | 0o755)
        return os.access(pad, os.X_OK)
    except OSError:
        return False


def slug(tekst: str) -> str:
    """Een veilige naam voor bestanden: kleine letters, cijfers en streepjes."""
    s = re.sub(r"[^a-z0-9]+", "-", tekst.lower()).strip("-")
    return s[:60] or "programma"


def _schoon(tekst: str, lengte: int = 200) -> str:
    """Tekst uit het programma zelf: geen nieuwe regels of stuurtekens (die zouden de starter kunnen veranderen)."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", tekst).strip()[:lengte]


def _lees_desktop(pad: Path) -> dict[str, str]:
    """De [Desktop Entry] van een .desktop-bestand, zonder configparser (die struikelt over %-tekens en dubbele
    sleutels). Een vertaalde naam in jouw taal gaat voor."""
    waarden: dict[str, str] = {}
    in_groep = False
    try:
        regels = pad.read_text(errors="replace").splitlines()
    except OSError:
        return waarden
    for regel in regels:
        regel = regel.strip()
        if regel.startswith("["):
            in_groep = regel == "[Desktop Entry]"
            continue
        if in_groep and "=" in regel and not regel.startswith("#"):
            k, _, v = regel.partition("=")
            waarden.setdefault(k.strip(), v.strip())
    return waarden


def _uitpakken(appimage: Path, map_: Path, patroon: str) -> None:
    """Eén patroon uit de AppImage halen (in map_/squashfs-root). Draait de AppImage zelf, maar alleen het uitpakdeel
    (de standaard runtime van AppImage); zonder FUSE."""
    try:
        subprocess.run([str(appimage), "--appimage-extract", patroon], cwd=map_, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120, env={**os.environ, "APPIMAGE_EXTRACT_AND_RUN": ""})
    except (OSError, subprocess.SubprocessError):
        pass


def lees_info(appimage: Path) -> dict:
    """Naam, uitleg, categorie, vensterklasse en pictogram (tijdelijk bestand) uit de AppImage. Lukt het niet, dan
    de bestandsnaam: 'Krita-5.2.6-x86_64.AppImage' wordt 'Krita'."""
    naam_bestand = re.split(r"[-_ ]v?\d", appimage.stem, maxsplit=1)[0] or appimage.stem
    info = {"naam": _schoon(naam_bestand.replace("_", " ").replace("-", " ").strip(), 80) or "Programma",
            "uitleg": "", "categorie": "", "klasse": "", "icoon": None, "id": slug(naam_bestand), "tijdelijk": None}
    if not os.access(appimage, os.X_OK):
        return info
    tijdelijk = Path(tempfile.mkdtemp(prefix="bugos-appimage-"))
    info["tijdelijk"] = tijdelijk
    _uitpakken(appimage, tijdelijk, "*.desktop")
    wortel = tijdelijk / "squashfs-root"
    desktops = sorted(wortel.glob("*.desktop")) if wortel.is_dir() else []
    if desktops:
        d = _lees_desktop(desktops[0])
        taal = (os.environ.get("LANG") or "en")[:2]
        naam = d.get(f"Name[{taal}]") or d.get("Name")
        if naam:
            info["naam"] = _schoon(naam, 80)
        info["uitleg"] = _schoon(d.get(f"Comment[{taal}]") or d.get("Comment") or "")
        info["categorie"] = re.sub(r"[^A-Za-z0-9;-]", "", d.get("Categories", ""))[:200]
        info["klasse"] = re.sub(r"[^A-Za-z0-9._-]", "", d.get("StartupWMClass", ""))[:100]
        info["id"] = slug(desktops[0].stem)
    # Het pictogram: .DirIcon (vaak een verwijzing naar een .png of .svg in de wortel; die dan ook halen).
    _uitpakken(appimage, tijdelijk, ".DirIcon")
    icoon = wortel / ".DirIcon"
    if icoon.is_symlink():
        doel = os.readlink(icoon)
        if "/" not in doel and not doel.startswith("."):
            _uitpakken(appimage, tijdelijk, doel)
            icoon = wortel / doel
    if icoon.is_file() and not icoon.is_symlink() and icoon.stat().st_size < 5_000_000:
        info["icoon"] = icoon
    return info


def _exec_pad(pad: Path) -> str:
    """Een pad in Exec= van een .desktop-bestand (tussen aanhalingstekens, met \\ voor ", `, $ en \\)."""
    s = str(pad)
    for teken in ("\\", '"', "`", "$"):
        s = s.replace(teken, "\\" + teken)
    return f'"{s}"'


def _icoon_soort(pad: Path) -> str:
    with open(pad, "rb") as f:
        begin = f.read(512)
    if begin.startswith(b"\x89PNG"):
        return ".png"
    if b"<svg" in begin or begin.lstrip().startswith(b"<?xml"):
        return ".svg"
    return ""


def installeer(bron: str | Path) -> tuple[bool, dict | str]:
    """De AppImage bij je apps zetten, met een starter in het startmenu. (True, info) of (False, reden):
    geen-appimage, geen-ruimte, mislukt. Uit je home wordt hij verplaatst, van ergens anders (een USB-stick) gekopieerd."""
    bron = Path(bron).resolve()
    if not is_appimage(bron):
        return False, "geen-appimage"
    doelmap = apps_map()
    try:
        doelmap.mkdir(parents=True, exist_ok=True)
        tijdelijk_doel = doelmap / f".nieuw-{os.getpid()}.AppImage"
        if Path.home() in bron.parents and bron.parent != doelmap:
            shutil.move(str(bron), tijdelijk_doel)
            verplaatst = True
        else:
            shutil.copy2(bron, tijdelijk_doel)
            verplaatst = False
    except OSError as e:
        return False, "geen-ruimte" if getattr(e, "errno", 0) == 28 else "mislukt"
    if not maak_uitvoerbaar(tijdelijk_doel):
        tijdelijk_doel.unlink(missing_ok=True)
        return False, "mislukt"
    info = lees_info(tijdelijk_doel)
    app_id = info["id"]
    doel = doelmap / f"{app_id}.AppImage"
    os.replace(tijdelijk_doel, doel)   # een oudere versie van hetzelfde programma wordt vervangen
    icoon_regel = "application-x-executable"
    if info["icoon"] is not None and (ext := _icoon_soort(info["icoon"])):
        (doelmap / "icons").mkdir(exist_ok=True)
        for oud in (doelmap / "icons").glob(f"{app_id}.*"):
            oud.unlink(missing_ok=True)
        icoon_doel = doelmap / "icons" / f"{app_id}{ext}"
        shutil.copyfile(info["icoon"], icoon_doel)
        icoon_regel = str(icoon_doel)
    if info["tijdelijk"]:
        shutil.rmtree(info["tijdelijk"], ignore_errors=True)
    regels = ["[Desktop Entry]", "Type=Application", f"Name={info['naam']}"]
    if info["uitleg"]:
        regels.append(f"Comment={info['uitleg']}")
    regels += [f"Exec=bugos-appimage start {_exec_pad(doel)} %U", f"Icon={icoon_regel}",
               f"Categories={info['categorie'] or 'Utility;'}", "Terminal=false", f"{SLEUTEL}={doel}"]
    if info["klasse"]:
        regels.append(f"StartupWMClass={info['klasse']}")
    starters_map().mkdir(parents=True, exist_ok=True)
    starter = starters_map() / f"{VOORVOEGSEL}{app_id}.desktop"
    nieuw = starter.with_suffix(".nieuw")
    nieuw.write_text("\n".join(regels) + "\n")
    os.replace(nieuw, starter)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(starters_map())], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    return True, {"id": app_id, "naam": info["naam"], "pad": doel, "starter": starter, "verplaatst": verplaatst}


def lijst() -> list[dict]:
    """De AppImages die BugOS heeft geïnstalleerd: [{'id', 'naam', 'pad', 'starter', 'icoon'}], op naam."""
    uit = []
    for starter in sorted(starters_map().glob(f"{VOORVOEGSEL}*.desktop")):
        d = _lees_desktop(starter)
        if SLEUTEL not in d:
            continue
        uit.append({"id": starter.stem[len(VOORVOEGSEL):], "naam": d.get("Name", starter.stem),
                    "pad": Path(d[SLEUTEL]), "starter": starter, "icoon": d.get("Icon", "")})
    return sorted(uit, key=lambda a: a["naam"].lower())


def verwijder(app_id: str) -> bool:
    """Het programma, zijn pictogram en zijn starter weg. Alleen wat in de map van BugOS staat."""
    if slug(app_id) != app_id:
        return False
    gevonden = False
    for a in lijst():
        if a["id"] != app_id:
            continue
        gevonden = True
        if a["pad"].parent == apps_map():
            a["pad"].unlink(missing_ok=True)
        for icoon in (apps_map() / "icons").glob(f"{app_id}.*"):
            icoon.unlink(missing_ok=True)
        a["starter"].unlink(missing_ok=True)
    return gevonden


def start(pad: str | Path, args: list[str] | None = None) -> bool:
    """Een AppImage starten (los van dit programma). Zonder FUSE 2: uitpakken en dan starten."""
    pad = Path(pad)
    if not is_appimage(pad):
        return False
    if not os.access(pad, os.X_OK) and not maak_uitvoerbaar(pad):
        # Niet uitvoerbaar te maken (een USB-stick met FAT): een kopie in de tijdelijke map.
        kopie = Path(tempfile.mkdtemp(prefix="bugos-appimage-run-")) / pad.name
        shutil.copy2(pad, kopie)
        maak_uitvoerbaar(kopie)
        pad = kopie
    try:
        subprocess.Popen([str(pad), *(args or [])], env=omgeving(), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ------------------------------------------------------------------------- installatiescripts (.run, makeself)

def is_installatiescript(pad: str | Path) -> bool:
    """Een Linux-installatiescript van een website (.run of .sh, vaak van makeself): begint met #!."""
    p = Path(pad)
    if p.suffix.lower() not in (".run", ".sh") or not p.is_file():
        return False
    try:
        with open(p, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def script_opdracht(pad: str | Path) -> list[str]:
    """Het installatiescript in een terminal (je ziet wat het doet en kunt antwoorden), en de terminal blijft open
    tot je hem sluit. Met bash, zodat het niet eerst uitvoerbaar hoeft te zijn."""
    p = str(Path(pad).resolve())
    if shutil.which("konsole"):
        return ["konsole", "--hold", "-e", "bash", p]
    return ["xterm", "-hold", "-e", "bash", p]
