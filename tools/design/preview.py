#!/usr/bin/env python3
"""Proefkaarten van de BugOS-ontwerptaal buiten de eigen apps, in een container.

Draait in de testbank (BugOS + Kvantum + rsvg-convert):
    podman run --rm -v <repo>:/repo:ro -v <uitmap>:/uit localhost/bugos-testbank \\
        python3 /repo/tools/design/preview.py <wat> [licht|donker|beide] [namen...]

    wat:  iconen   contactvellen van het pictogramthema (naast Breeze ter vergelijking)
          kvantum  een venster vol KDE-knoppen (QtWidgets) en hetzelfde in de stijl van
                   KDE Instellingen (Kirigami), met de BugOS Kvantum-stijl
          plasma   taakbalk, pop-up, tooltip en Plasma-knoppen met de BugOS Plasma-stijl
          alles    alle drie

De testbank (Windows):  zie tools/design/README.md
"""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("BUGOS_REPO", "/repo"))
UIT = Path(os.environ.get("BUGOS_UIT", "/uit"))
HIER = Path(__file__).resolve().parent
TEKST = {".svg", ".colors", ".kvconfig", ".theme", ".json", ".qml", ".js", ".desktop", ".conf", ".txt", ""}

# Wat uit de repo in het systeem van de container moet (net als build.sh doet).
NEERZETTEN = ["usr/share/icons/BugOS", "usr/share/Kvantum", "usr/share/plasma/desktoptheme/bugos",
              "usr/share/color-schemes", "usr/share/fonts/bugos"]


def zet_neer() -> None:
    for rel in NEERZETTEN:
        bron = REPO / "system_files" / rel
        doel = Path("/") / rel
        if not bron.exists():
            continue
        for pad in bron.rglob("*"):
            if pad.is_dir():
                continue
            d = doel / pad.relative_to(bron)
            d.parent.mkdir(parents=True, exist_ok=True)
            if pad.suffix.lower() in TEKST:
                # Op Windows staan tekstbestanden soms met CRLF in de werkmap.
                d.write_bytes(pad.read_bytes().replace(b"\r\n", b"\n"))
            else:
                shutil.copyfile(pad, d)
    subprocess.run(["fc-cache", "-f"], capture_output=True)


def _ini(pad: Path) -> configparser.RawConfigParser:
    c = configparser.RawConfigParser(strict=False, interpolation=None)
    c.optionxform = str
    if pad.exists():
        c.read_string(pad.read_text(encoding="utf-8").replace("\r\n", "\n"))
    return c


def heeft_kvantum(naam: str) -> bool:
    return (Path("/usr/share/Kvantum") / naam / f"{naam}.kvconfig").exists()


def heeft_plasmastijl() -> bool:
    return Path("/usr/share/plasma/desktoptheme/bugos/metadata.json").exists()


def heeft_iconen() -> bool:
    return Path("/usr/share/icons/BugOS/index.theme").exists()


def maak_thuis(thema: str) -> dict:
    """Een gebruiker met de BugOS-instellingen voor licht of donker; geeft de omgeving terug."""
    thuis = Path(f"/tmp/proef-{thema}")
    if thuis.exists():
        shutil.rmtree(thuis)
    cfg = thuis / ".config"
    cfg.mkdir(parents=True)
    schema = "BugOSDark" if thema == "donker" else "BugOSLight"
    kvnaam = "BugOSDark" if thema == "donker" else "BugOS"

    glob = _ini(Path("/usr/share/color-schemes") / f"{schema}.colors")
    for groep in ("General", "KDE", "Icons"):
        if not glob.has_section(groep):
            glob.add_section(groep)
    glob.set("General", "ColorScheme", schema)
    glob.set("General", "font", "Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1")
    glob.set("General", "AccentColor", "222,47,62")
    glob.set("Icons", "Theme", "BugOS" if heeft_iconen() else "breeze")
    glob.set("KDE", "widgetStyle", "kvantum" if heeft_kvantum(kvnaam) else "Breeze")
    with open(cfg / "kdeglobals", "w", encoding="utf-8") as f:
        glob.write(f, space_around_delimiters=False)

    (cfg / "plasmarc").write_text(f"[Theme]\nname={'bugos' if heeft_plasmastijl() else 'default'}\n", encoding="utf-8")
    (cfg / "Kvantum").mkdir()
    (cfg / "Kvantum" / "kvantum.kvconfig").write_text(f"[General]\ntheme={kvnaam}\n", encoding="utf-8")

    run = Path(f"/tmp/run-{thema}")
    run.mkdir(mode=0o700, exist_ok=True)
    env = dict(os.environ)
    env.update(HOME=str(thuis), XDG_CONFIG_HOME=str(cfg), XDG_RUNTIME_DIR=str(run),
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="kde",
               QT_QUICK_CONTROLS_STYLE="org.kde.desktop", QT_QUICK_BACKEND="software", BUGOS_THEMA=thema,
               BUGOS_UIT=str(UIT), PYTHONDONTWRITEBYTECODE="1")
    if heeft_kvantum(kvnaam):
        env["QT_STYLE_OVERRIDE"] = "kvantum"
    return env


def draai(script: str, thema: str, extra: list[str]) -> int:
    env = maak_thuis(thema)
    print(f"== {script} ({thema})", flush=True)
    r = subprocess.run([sys.executable, str(HIER / script), *extra], env=env)
    return r.returncode


def main(args: list[str]) -> int:
    wat = args[0] if args else "alles"
    themas = {"licht": ["licht"], "donker": ["donker"]}.get(args[1] if len(args) > 1 else "beide", ["licht", "donker"])
    extra = args[2:]
    UIT.mkdir(parents=True, exist_ok=True)
    zet_neer()
    print("BugOS-iconen:", heeft_iconen(), "| Kvantum BugOS:", heeft_kvantum("BugOS"), heeft_kvantum("BugOSDark"),
          "| Plasma-stijl bugos:", heeft_plasmastijl())
    scripts = {"iconen": "preview_icons.py", "kvantum": "preview_kvantum.py", "plasma": "preview_plasma.py"}
    kies = list(scripts) if wat == "alles" else [wat]
    fout = 0
    for k in kies:
        for t in themas:
            fout |= draai(scripts[k], t, extra)
    print("klaar; plaatjes in", UIT)
    return fout


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
