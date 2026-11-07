#!/usr/bin/env python3
"""The photo studio: screenshots of the BugOS apps for the website and the README.

Runs INSIDE the BugOS image, without a screen (Qt 'offscreen'), at 2x sharpness.
Every photo is one app in a fixed state with example data (no real drives,
networks or printers from the computer it runs on). On your own computer, use:

    bash tools/screenshots/studio.sh [image]     # every photo -> website/assets/*.webp

or a single scene, inside the image:

    QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 LANG=en_US.UTF-8 BUGOS_THEMA=licht \\
        python3 tools/screenshots/studio.py welcome out.png

BUGOS_BRON points to the folder with the programs (default: the image itself, "/").
"""

from __future__ import annotations

import json
import os
import runpy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/usr/lib/bugos/python")

BRON = os.environ.get("BUGOS_BRON", "/")
WAIT = 2500  # ms: time for everything to load (lists, checks in the background)


def fake_drives() -> str:
    """Two fake USB drives, with the folder from BugOS Switch (Windows) on the first one."""
    base = Path(tempfile.mkdtemp(prefix="studio-"))
    stick, drive = base / "Bugie's USB stick", base / "Backup drive"
    for d in (stick, drive):
        d.mkdir()
    # New name first; the old Dutch name too, for older versions of the app.
    for folder, file in (("BugOS-Switch", "bugos-switch.json"), ("BugOS-Overstap", "bugos-overstap.json")):
        (stick / folder).mkdir()
        (stick / folder / file).write_text(
            json.dumps({"gebruiker": "Bugie", "computer": "LIVING-ROOM-PC"}), encoding="utf-8")
    return f"{stick}:{drive}"


def help_all_good(g: dict) -> None:
    """'Something is not working' with everything fine (the build computer has no Wi-Fi or printer)."""
    Result, OK = g["Uitslag"], g["OK"]
    good = [("controle_internet", "Internet", "You are connected to the internet."),
            ("controle_wifi", "Wi-Fi", "Wi-Fi is on."),
            ("controle_bluetooth", "Bluetooth", "Bluetooth is on."),
            ("controle_geluid", "Sound", "Sound works."),
            ("controle_printer", "Printer", "Printer is ready."),
            ("controle_opslag", "Storage", "Enough space: 212 GB free."),
            ("controle_updates", "Updates", "Everything is up to date.")]
    checks = []
    for name, title, text in good:
        def check(title=title, text=text):
            return Result(title, OK, text)
        check.__name__ = name  # the app picks the icon by this name
        checks.append(check)
    g["CONTROLES"][:] = checks


def program(*names: str) -> str:
    """The first program that exists (new English name first, then the old Dutch one in older images)."""
    for n in names:
        for base in (BRON, "/"):
            p = Path(base) / n.lstrip("/")
            if p.is_file():
                return str(p)
    raise SystemExit(f"ERROR: none of these programs exist: {', '.join(names)}")


WELCOME = ("usr/bin/bugos-welcome", "usr/bin/bugos-welkom")
HELP = ("usr/bin/bugos-help", "usr/bin/bugos-hulp")
SETTINGS = ("usr/bin/bugos-settings", "usr/bin/bugos-instellingen")
STORE = ("usr/bin/bugos-store", "usr/bin/bugos-winkel")
BACKUP = ("usr/bin/bugos-backup",)
SWITCH = ("usr/bin/bugos-switch", "usr/bin/bugos-overstap")
LIVE = ("../iso_live/src/bugos-live", "usr/bin/bugos-live")
FILES = ("usr/bin/bugos-files", "usr/bin/bugos-bestanden")
SAMPLE = {"BUGOS_INSTELLINGEN_VOORBEELD": "1"}

# name: (programs, arguments, extra environment, prepare(globals), state(window), crop (x, y, w, h) in real pixels)
SCENES = {
    "welcome": (WELCOME, [], {}, None, lambda w: (w.stapels.setCurrentIndex(2), w.ververs()), None),
    "help": (HELP, [], {}, help_all_good, None, None),
    "help-crop": (HELP, [], {}, help_all_good, None, (0, 0, 1760, 1120)),
    "settings": (SETTINGS, [], SAMPLE, None, None, None),
    "power-crop": (SETTINGS, ["updates"], SAMPLE, None, None, (480, 0, 1760, 1100)),
    "store": (STORE, [], {"BUGOS_GEINSTALLEERD": "org.mozilla.firefox,org.videolan.VLC"}, None, None, None),
    "backup": (BACKUP, [], {"BUGOS_SCHIJVEN": "fake"}, None, None, None),
    "switch": (SWITCH, [], {"BUGOS_SCHIJVEN": "fake"}, None, None, None),
    "live": (LIVE, [], {}, None, None, None),
    # Files needs a home folder with example files: studio.sh starts it through explorer.sh.
    "files": (FILES, [], {}, None, None, None),
}


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in SCENES:
        print(f"usage: studio.py <{'|'.join(SCENES)}> <out.png> [arguments for the app]", file=sys.stderr)
        return 2
    name, out, extra = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    programs, args, env, prepare, state, crop = SCENES[name]
    path = program(*programs)
    for k, v in env.items():
        os.environ[k] = fake_drives() if v == "fake" else v

    import bugos_ui
    from PySide6.QtCore import QRect, QTimer

    def run(app, window) -> int:
        window.show()
        if state:
            state(window)

        def snap():
            img = window.grab()
            if crop:
                img = img.copy(QRect(*crop))  # real pixels (so already 2x)
            out.parent.mkdir(parents=True, exist_ok=True)
            ok = img.save(str(out))
            print(f"{name}: {img.width()}x{img.height()} -> {out}" if ok else f"ERROR: {name} not saved")
            app.exit(0 if ok else 1)

        QTimer.singleShot(WAIT, snap)
        return app.exec()

    bugos_ui.uitvoeren = run  # the apps import this name, so replace it before they load
    sys.argv = [path, *args, *extra]
    g = runpy.run_path(path, run_name="studio")
    if prepare:
        prepare(g)
    return (g.get("main") or g["venster"])()  # some apps call it main(), others venster()


if __name__ == "__main__":
    sys.exit(main())
