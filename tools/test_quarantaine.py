#!/usr/bin/env python3
"""Test van Quarantaine (bugos-quarantaine en bugos_quarantaine.py): een app proberen zonder dat hij bij je spullen kan.

Wat we nagaan:
  - wat er in quarantaine start: een app uit het startmenu (.desktop, ook een Flatpak), een .exe/.msi, een AppImage,
    een programma; de veldcodes (%u, %F) uit Exec= gaan eruit;
  - de doos (bwrap): een eigen thuismap, je echte thuismap niet, internet alleen als je dat aanzet, geen D-Bus, de
    .exe/AppImage alleen om te lezen; een Flatpak zonder toegang tot je bestanden en met zijn gegevens in quarantaine;
  - weggooien gooit alleen een quarantainemap weg, nooit iets anders;
  - met een echte bwrap (als die hier werkt): wat de app schrijft, komt in quarantaine; je echte bestanden ziet hij niet;
  - de terminal (--terminal, --bewaar, --lijst, --weg) en het venster (starten, klaar, bewaren, weggooien, dicht);
  - Bestanden en het startmenu: 'Openen in quarantaine' alleen bij programma's.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_quarantaine.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-quarantaine-"))
THUIS = TMP / "thuis"
(THUIS / "Documenten").mkdir(parents=True)
(THUIS / "Documenten" / "geheim.txt").write_text("van mij")
os.environ["HOME"] = str(THUIS)
os.environ["XDG_CACHE_HOME"] = str(THUIS / ".cache")
os.environ["XDG_DATA_HOME"] = str(THUIS / ".local" / "share")

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(naam: str, pad: Path):
    lader = importlib.machinery.SourceFileLoader(naam, str(pad))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


import bugos_quarantaine as q  # noqa: E402

# ------------------------------------------------------------------------------------------- wat start er
klopt(q.exec_argumenten("firefox --new-window %u") == ["firefox", "--new-window"], "Exec: veldcodes (%u) gaan eruit")
klopt(q.exec_argumenten('sh -c "echo 100%%"') == ["sh", "-c", "echo 100%"], "Exec: %% wordt %")
apps = TMP / "apps"
apps.mkdir()
(apps / "kladblok.desktop").write_text("[Desktop Entry]\nName=Notepad\nName[nl]=Kladblok\nExec=kwrite %U\nTerminal=false\n")
(apps / "org.voorbeeld.App.desktop").write_text(
    "[Desktop Entry]\nName=Voorbeeld\nExec=flatpak run --branch=stable org.voorbeeld.App @@u %u @@\nX-Flatpak=org.voorbeeld.App\n")
(apps / "kapot.desktop").write_text("geen desktop-bestand")
d = q.bepaal_doel(str(apps / "kladblok.desktop"), [], "nl")
klopt(d is not None and d.soort == "programma" and d.opdracht == ["kwrite"] and d.naam == "Kladblok",
      f".desktop: de opdracht en de naam in je eigen taal ({d})")
d = q.bepaal_doel(str(apps / "org.voorbeeld.App.desktop"), [], "nl")
klopt(d is not None and d.soort == "flatpak" and d.flatpak == "org.voorbeeld.App", f".desktop van een Flatpak: flatpak ({d})")
klopt(q.bepaal_doel(str(apps / "kapot.desktop"), []) is None, "een kapot .desktop-bestand: niets starten")
exe = TMP / "Setup.EXE"
exe.write_text("MZ")
d = q.bepaal_doel(str(exe), [])
klopt(d is not None and d.soort == "wine" and d.bestand == str(exe), "een .exe (ook met hoofdletters): Wine")
ai = TMP / "Tool-x86_64.AppImage"
ai.write_text("x")
ai.chmod(0o755)
klopt(q.bepaal_doel(str(ai), []).soort == "appimage", "een AppImage")
klopt(q.bepaal_doel("sh", ["-c", "true"]).opdracht == ["sh", "-c", "true"], "een programma op PATH, met argumenten")
klopt(q.bepaal_doel("bestaat-echt-niet-xyz", []) is None and q.bepaal_doel(str(TMP / "nee"), []) is None,
      "iets dat er niet is: None")

# ------------------------------------------------------------------------------------------- de doos
home = TMP / "q-home"
home.mkdir()
cmd = q.bwrap_opdracht(["sh"], home, internet=False)
binds = [(cmd[i + 1], cmd[i + 2]) for i, a in enumerate(cmd) if a == "--bind"]
echt = os.path.realpath(str(THUIS))
klopt(binds == [(str(home), echt)], f"doos: alleen de quarantaine-thuismap, op de plek van je thuismap ({binds})")
klopt("--unshare-net" in cmd and "--new-session" in cmd and "--die-with-parent" in cmd, "doos: geen internet, eigen sessie")
klopt(all(x in cmd for x in ("DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK")), "doos: geen D-Bus en geen SSH-sleutels")
klopt(not any(a == str(THUIS) or a == echt for i, a in enumerate(cmd) if cmd[i - 1] in ("--ro-bind", "--ro-bind-try")),
      "doos: je echte thuismap staat er nergens in")
klopt(cmd[cmd.index("--") + 1:] == ["sh"], "doos: de opdracht staat achter --")
cmd = q.bwrap_opdracht(["sh"], home, internet=True, terminal=True)
klopt("--unshare-net" not in cmd and "--new-session" not in cmd, "doos: met internet; in de terminal geen eigen sessie (Ctrl+C werkt)")
d = q.bepaal_doel(str(exe), [])
cmd, env = q.opdracht(d, home, internet=False)
ro = [(cmd[i + 1], cmd[i + 2]) for i, a in enumerate(cmd) if a == "--ro-bind" and cmd[i + 1] == str(exe)]
klopt(ro == [(str(exe), os.path.join(echt, "Quarantaine", "Setup.EXE"))] and "wine" in cmd and "start" in cmd,
      f"Wine: de .exe alleen om te lezen in ~/Quarantaine, gestart met wine start ({ro})")
klopt(cmd[cmd.index("WINEPREFIX") + 1] == os.path.join(echt, ".wine"), "Wine: een eigen Wine-map in quarantaine")
cmd, env = q.opdracht(q.Doel("flatpak", "Voorbeeld", flatpak="org.voorbeeld.App"), home, internet=False)
klopt(cmd[:2] == ["flatpak", "run"] and "--nofilesystem=host:reset" in cmd and "--unshare=network" in cmd
      and "--nosocket=session-bus" in cmd and cmd[-1] == "org.voorbeeld.App",
      f"Flatpak: geen toegang tot je bestanden, geen internet ({cmd})")
klopt(env["HOME"] == str(home) and env["FLATPAK_USER_DIR"] == str(THUIS / ".local/share/flatpak"),
      "Flatpak: zijn gegevens in quarantaine, je eigen Flatpak-apps blijven te vinden")
cmd, _env = q.opdracht(q.Doel("appimage", "Tool", bestand=str(ai)), home, internet=True)
klopt("APPIMAGE_EXTRACT_AND_RUN" in cmd and cmd[-1] == os.path.join(echt, "Quarantaine", ai.name),
      "AppImage: zonder FUSE (uitpakken en starten)")

# ------------------------------------------------------------------------------------------- mappen
m = q.nieuwe_map(q.Doel("programma", "Google Chrome", opdracht=["x"]))
klopt(m.parent == q.tijdelijke_map() and "google-chrome" in m.name and (m / "home").is_dir()
      and oct(m.stat().st_mode & 0o777) == "0o700", f"een tijdelijke map, alleen voor jou ({m.name})")
(m / "home" / "sub").mkdir()
(m / "home" / "sub" / "x").write_text("12345")
(m / "home" / "sub").chmod(0o500)   # zoals Wine soms doet: een map zonder schrijfrecht
klopt(q.omvang(m / "home") == (1, 5), "omvang: wat de app schreef")
q.weggooien(m)
klopt(not m.exists(), "weggooien: ook met een map zonder schrijfrecht erin")
for verkeerd in (THUIS, THUIS / "Documenten", q.tijdelijke_map(), Path("/")):
    try:
        q.weggooien(verkeerd)
        weg = True
    except ValueError:
        weg = False
    klopt(not weg and (THUIS / "Documenten" / "geheim.txt").exists(), f"weggooien weigert {verkeerd}")
m = q.nieuwe_map(q.Doel("programma", "Spel", opdracht=["x"]))
nieuw = q.bewaren(m, "Spel")
nieuw2 = q.bewaren(q.nieuwe_map(q.Doel("programma", "Spel", opdracht=["x"])), "Spel")
klopt(nieuw.name == "spel" and nieuw2.name == "spel-2" and [p.name for p in q.bewaarde("spel")] == ["spel-2", "spel"],
      f"bewaren: onder de naam van de app, en een tweede ernaast ({[p.name for p in q.bewaarde('spel')]})")
try:
    q.nieuwe_map(q.Doel("programma", "x"), "../ontsnapt")
    klopt(False, "een bewaarde naam met ../ wordt geweigerd")
except ValueError:
    klopt(True, "een bewaarde naam met ../ wordt geweigerd")


# ------------------------------------------------------------------------------------------- echt, met bwrap
def bwrap_werkt() -> bool:
    if not shutil.which("bwrap"):
        return False
    return subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-pid", "true"], capture_output=True).returncode == 0


if bwrap_werkt():
    d = q.bepaal_doel("sh", ["-c", "echo nieuw > ~/geschreven.txt; ls ~/Documenten 2>&1; cat /proc/1/cmdline | tr '\\0' ' '"])
    m = q.nieuwe_map(d)
    cmd, env = q.opdracht(d, m / "home", internet=False, terminal=True)
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **env}, timeout=30)
    klopt(r.returncode == 0 and (m / "home" / "geschreven.txt").read_text() == "nieuw\n"
          and not (THUIS / "geschreven.txt").exists(), f"echt: wat de app schrijft, komt in quarantaine ({r.stderr[-200:]})")
    klopt("geheim" not in r.stdout and "No such file" in r.stdout, f"echt: je eigen bestanden ziet hij niet ({r.stdout[:80]!r})")
    klopt("bwrap" in r.stdout or "sh" in r.stdout, "echt: een eigen procesruimte (proces 1 is de doos)")
    q.weggooien(m)
else:
    print("(geen werkende bwrap hier: de echte doos-test is overgeslagen)")

# ------------------------------------------------------------------------------------------- terminal
bq = TMP / "bugos-quarantaine"
bq.write_text((BIN / "bugos-quarantaine").read_text().replace("/usr/lib/bugos/python", str(PY)))
nep = TMP / "nep-bin"
nep.mkdir()
(nep / "bwrap").write_text('#!/usr/bin/bash\nwhile [ "$1" != -- ]; do shift; done; shift\necho ran:"$*"\n'
                           'touch "$HOME/.cache/nep-bwrap-was-hier"; exit 4\n')
(nep / "bwrap").chmod(0o755)
omg = dict(os.environ, PATH=f"{nep}:{os.environ['PATH']}")


def roep(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(bq), *args], capture_output=True, text=True, env=omg, timeout=60,
                          stdin=subprocess.DEVNULL)


r = roep("--terminal", "sh", "-c", "true")
klopt(r.returncode == 4 and "ran:sh -c true" in r.stdout and ("Weggegooid" in r.stderr or "Thrown away" in r.stderr)
      and not any(q.tijdelijke_map().iterdir()), f"terminal: de code van de app, en daarna weggegooid ({r.stderr[-120:]!r})")
r = roep("--terminal", "--bewaar", "Mijn Test", "sh")
klopt(("Bewaard" in r.stderr or "Kept" in r.stderr) and (q.bewaar_map() / "mijn-test" / "home").is_dir(), "terminal: --bewaar bewaart")
r = roep("--lijst")
klopt("mijn-test" in r.stdout, f"--lijst toont de bewaarde ({r.stdout.strip()[:60]})")
r = roep("--weg", "mijn-test")
klopt(r.returncode == 0 and not (q.bewaar_map() / "mijn-test").exists(), "--weg gooit hem weg")
klopt(roep("--weg", "../..").returncode == 1 and THUIS.exists(), "--weg met ../.. doet niets")
klopt(roep("--terminal", "bestaat-echt-niet-xyz").returncode == 2 and roep("--onzin", "sh").returncode == 2,
      "iets onbekends of een onbekende optie: code 2")

# ------------------------------------------------------------------------------------------- het venster
venster_mod = laad("bugos_quarantaine_app", bq)
import bugos_ui  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = bugos_ui.maak_app("bugos-quarantaine", "bugos-quarantaine", ["bugos-quarantaine"])
uitkomst: dict = {}


def wacht(voorwaarde, ms: int = 8000) -> None:
    import time
    eind = time.monotonic() + ms / 1000
    while not voorwaarde() and time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.02)


def doe(w) -> int:
    uitkomst["w"] = w
    w.show()
    app.processEvents()
    stap = uitkomst["stap"]
    stap(w)
    return 0


venster_mod.__dict__["uitvoeren"] = None
bugos_ui.uitvoeren = lambda _app, w: doe(w)
os.environ["PATH"] = omg["PATH"]


def stap_bewaren(w):
    klopt(w.stand == "kiezen" and not w.internet.schuif.isChecked(), "venster: begint met kiezen, internet uit")
    w.hoofd.click()
    wacht(lambda: w.stand == "klaar")
    uitkomst["map"] = w.map
    klopt(w.stand == "klaar" and "code 4" in w.uitleg.text() and (w.map / "uitvoer.log").exists(),
          f"venster: de app stopte; de code en uitvoer.log ({w.uitleg.text()[:70]!r})")
    klopt((w.hoofd.text(), w.tweede.text()) in (("Weggooien", "Bewaren"), ("Throw away", "Keep")),
          "venster: na afloop Weggooien of Bewaren")
    w.tweede.click()
    klopt(not uitkomst["map"].exists() and q.bewaarde("venster-app"), "venster: Bewaren zet hem bij de bewaarde")
    w.hoofd.click()


uitkomst["stap"] = stap_bewaren
venster_mod.venster_app({"internet": False, "bewaar": "", "modus": "venster"},
                        q.Doel("programma", "Venster app", opdracht=["sh"]))


def stap_weg(w):
    klopt(w.welke.isVisible() and w.welke.count() == 2, "venster: een bewaarde quarantaine van deze app is te kiezen")
    w.internet.schuif.setChecked(True)
    w.hoofd.click()
    wacht(lambda: w.stand == "klaar")
    m = w.map
    w.close()   # dicht zonder te kiezen: een tijdelijke quarantaine gaat weg
    klopt(not m.exists(), "venster: dicht na afloop zonder te kiezen: weggegooid")


uitkomst["stap"] = stap_weg
venster_mod.venster_app({"internet": False, "bewaar": "", "modus": "venster"},
                        q.Doel("programma", "Venster app", opdracht=["sh"]))

# ------------------------------------------------------------------------------------------- Bestanden, startmenu
import bugos_files_bewerken as fb  # noqa: E402

shutil.copy(bq, nep / "bugos-quarantaine")
(nep / "bugos-quarantaine").chmod(0o755)
doc = TMP / "brief.odt"
doc.write_text("tekst")
doc.chmod(0o755)   # zoals op een USB-stick (FAT): alles 'uitvoerbaar'
script = TMP / "maak.sh"
script.write_text("#!/bin/sh\necho hoi\n")
script.chmod(0o755)
elf = TMP / "programma"
elf.write_bytes(b"\x7fELF" + b"\0" * 20)
elf.chmod(0o755)
klopt(fb.in_quarantaine_kan(exe) and fb.in_quarantaine_kan(ai) and fb.in_quarantaine_kan(script)
      and fb.in_quarantaine_kan(elf), "Bestanden: 'Openen in quarantaine' bij een .exe, AppImage, script en programma")
klopt(not fb.in_quarantaine_kan(doc) and not fb.in_quarantaine_kan(TMP), "Bestanden: niet bij een document of map")
sd_bron = (BIN / "bugos-start-data").read_text()
klopt('los_starten("bugos-quarantaine", "--venster", args[1])' in sd_bron and 'args[1].endswith(".desktop")' in sd_bron,
      "startmenu: --quarantaine start alleen een .desktop-bestand, met het venster")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
