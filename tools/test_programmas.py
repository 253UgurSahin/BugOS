#!/usr/bin/env python3
"""Test van programma's van buiten de Winkel: AppImage (bugos-appimage), Windows-programma's (bugos-windows), Microsoft
365 als web-apps (bugos-webapp) en hun plek in Instellingen > Geïnstalleerde apps.

Wat we nagaan:
  - een AppImage herkennen (ELF met 'AI' en type 2 op plek 8), en een .run-installatiescript;
  - installeren: naam, pictogram en vensterklasse uit het programma zelf (met een echte kleine AppImage, als er een
    C-compiler is), een starter in het startmenu, verplaatst uit je home of gekopieerd van elders, een nieuwere versie
    vervangt de oude; zonder FUSE 2 start hij uitgepakt (APPIMAGE_EXTRACT_AND_RUN=1); verwijderen ruimt alles op;
  - het venster: Installeren, Alleen openen, een script in een terminal, een onbekend bestand;
  - Windows-programma's: de lijst (wine uninstaller --list), verwijderen met een veilige sleutel, onderdelen van
    Microsoft (winetricks -q, alleen de bekende namen), Microsoft 365 in/uit het startmenu, opnieuw beginnen;
  - bugos-webapp: de gekozen browser in een app-venster, anders een andere die het kan, anders gewoon openen;
  - Instellingen toont AppImages en Windows-programma's tussen de apps; Bestanden opent .AppImage, .run en .bat goed.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_programmas.py
"""

from __future__ import annotations

import configparser
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-programmas-"))
THUIS = TMP / "thuis"
(THUIS / "Downloads").mkdir(parents=True)
NEP = TMP / "nep"
NEP.mkdir()
LOG = TMP / "log"
os.environ.update({
    "HOME": str(THUIS), "XDG_DATA_HOME": str(THUIS / ".local" / "share"), "XDG_CACHE_HOME": str(THUIS / ".cache"),
    "WINEPREFIX": str(THUIS / ".local" / "share" / "bugos" / "windows"), "NEP_LOG": str(LOG),
    "PATH": f"{NEP}:{os.environ.get('PATH', '/usr/bin:/bin')}", "BUGOS_LIBFUSE2": str(TMP / "geen-libfuse.so.2"),
})
sys.path.insert(0, str(PY))
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def nep(naam: str, inhoud: str) -> None:
    p = NEP / naam
    p.write_text("#!/usr/bin/bash\n" + inhoud)
    p.chmod(0o755)


def log() -> str:
    return LOG.read_text() if LOG.exists() else ""


def laad(naam: str, pad: Path):
    """Een programma uit bin als module, met de modules uit deze map (zoals test_quarantaine.py)."""
    kopie = TMP / pad.name
    kopie.write_text(pad.read_text().replace("/usr/lib/bugos/python", str(PY)))
    kopie.chmod(0o755)
    lader = importlib.machinery.SourceFileLoader(naam, str(kopie))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    lader.exec_module(m)
    return m, kopie


# ============================================================================================= AppImage
import bugos_appimage as ai  # noqa: E402

# Een echte kleine AppImage: een C-programma dat '--appimage-extract' doet zoals de runtime van AppImage, en anders
# opschrijft hoe hij gestart werd. Met 'AI' en type 2 op plek 8 (de kernel kijkt daar niet naar).
C_BRON = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc >= 3 && strcmp(argv[1], "--appimage-extract") == 0) {
        mkdir("squashfs-root", 0755);
        if (strcmp(argv[2], "*.desktop") == 0) {
            FILE *f = fopen("squashfs-root/org.voorbeeld.Tekenen.desktop", "w");
            fputs("[Desktop Entry]\nType=Application\nName=Tekenen Pro\nName[nl]=Tekenen Pro NL\n"
                  "Comment=Teken iets\nExec=AppRun %F\nIcon=tekenen\nCategories=Graphics;$(rm -rf);\n"
                  "StartupWMClass=tekenen-pro\n", f);
            fclose(f);
        } else if (strcmp(argv[2], ".DirIcon") == 0) {
            symlink("tekenen.png", "squashfs-root/.DirIcon");
        } else if (strcmp(argv[2], "tekenen.png") == 0) {
            FILE *f = fopen("squashfs-root/tekenen.png", "wb");
            fwrite("\x89PNG\r\n\x1a\n0000", 1, 12, f);
            fclose(f);
        }
        return 0;
    }
    const char *l = getenv("NEP_LOG");
    FILE *f = l ? fopen(l, "a") : NULL;
    if (f) {
        const char *e = getenv("APPIMAGE_EXTRACT_AND_RUN");
        fprintf(f, "appimage gestart extract=%s args=", e ? e : "");
        for (int i = 1; i < argc; i++) fprintf(f, "%s ", argv[i]);
        fputs("\n", f);
        fclose(f);
    }
    return 0;
}
'''


def maak_appimage(pad: Path) -> bool:
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        return False
    (TMP / "ai.c").write_text(C_BRON)
    if subprocess.run([cc, "-O0", "-o", str(pad), str(TMP / "ai.c")], capture_output=True).returncode != 0:
        return False
    data = bytearray(pad.read_bytes())
    data[8:11] = b"AI\x02"
    pad.write_bytes(bytes(data))
    pad.chmod(0o755)
    return True


bron = TMP / "bron.AppImage"
echt = maak_appimage(bron)
nep_ai = TMP / "nep.AppImage"
nep_ai.write_bytes(b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\x00" * 64)
elf = TMP / "gewoon-programma"
elf.write_bytes(b"\x7fELF\x02\x01\x01\x00\x00\x00\x00" + b"\x00" * 64)
klopt(ai.soort(nep_ai) == 2 and not ai.is_appimage(elf) and not ai.is_appimage(TMP / "weg.AppImage"),
      "een AppImage herkennen (ELF met 'AI' en type 2); een gewoon programma niet")
script = TMP / "installeer.run"
script.write_text("#!/bin/sh\necho hallo\n")
klopt(ai.is_installatiescript(script) and not ai.is_installatiescript(nep_ai)
      and ai.script_opdracht(script)[-2:] == ["bash", str(script.resolve())],
      "een .run-installatiescript: in een terminal met bash (hoeft niet uitvoerbaar te zijn)")
klopt(ai._exec_pad(Path('/a b/c"d$e`f\\g')) == '"/a b/c\\"d\\$e\\`f\\\\g"', "een pad in Exec= staat goed tussen aanhalingstekens")
klopt(ai.slug("Org.KDE Krita!") == "org-kde-krita" and ai.slug("../..") == "programma", "veilige namen voor bestanden")
klopt(ai.lees_info(nep_ai)["naam"] == "nep" and ai.lees_info(TMP / "Krita-5.2.6-x86_64.AppImage")["naam"] == "Krita",
      "zonder iets uit het programma: de naam uit de bestandsnaam (Krita-5.2.6-x86_64 wordt Krita)")

if echt:
    download = THUIS / "Downloads" / "Tekenen-2.1-x86_64.AppImage"
    shutil.copy2(bron, download)
    os.environ["LANG"] = "nl_NL.UTF-8"
    gelukt, info = ai.installeer(download)
    klopt(gelukt and info["naam"] == "Tekenen Pro NL" and info["id"] == "org-voorbeeld-tekenen" and info["verplaatst"]
          and not download.exists() and info["pad"].is_file() and os.access(info["pad"], os.X_OK),
          f"installeren: naam uit het programma (in jouw taal), verplaatst uit Downloads, uitvoerbaar ({info})")
    starter = configparser.ConfigParser(interpolation=None)
    starter.optionxform = str
    starter.read(info["starter"])
    e = starter["Desktop Entry"]
    klopt(e["Exec"] == f'bugos-appimage start "{info["pad"]}" %U' and e["StartupWMClass"] == "tekenen-pro"
          and e["Categories"] == "Graphics;rm-rf;" and e["Icon"].endswith("icons/org-voorbeeld-tekenen.png")
          and Path(e["Icon"]).is_file() and e[ai.SLEUTEL] == str(info["pad"]),
          "de starter: Exec via bugos-appimage, eigen pictogram, vensterklasse; rare tekens uit de categorie weg")
    klopt([a["id"] for a in ai.lijst()] == ["org-voorbeeld-tekenen"], "lijst: de geïnstalleerde AppImage")
    stick = TMP / "stick"
    stick.mkdir()
    shutil.copy2(bron, stick / "Tekenen-2.2.AppImage")
    gelukt, info2 = ai.installeer(stick / "Tekenen-2.2.AppImage")
    klopt(gelukt and not info2["verplaatst"] and (stick / "Tekenen-2.2.AppImage").exists() and len(ai.lijst()) == 1
          and len(list(ai.apps_map().glob("*.AppImage"))) == 1,
          "van een USB-stick: gekopieerd (de stick blijft heel); een nieuwere versie vervangt de oude")
    LOG.unlink(missing_ok=True)
    klopt(ai.start(info["pad"], ["bestand.png"]), "starten")
    for _ in range(100):
        if "appimage gestart" in log():
            break
        time.sleep(0.05)
    klopt("extract=1 args=bestand.png" in log(), f"zonder FUSE 2: uitgepakt starten (APPIMAGE_EXTRACT_AND_RUN=1) ({log()!r})")
    os.environ["BUGOS_LIBFUSE2"] = str(bron)   # een bestand dat bestaat: dan 'is' FUSE 2 er
    ai.LIBFUSE2 = [str(bron)]
    klopt("APPIMAGE_EXTRACT_AND_RUN" not in ai.omgeving(), "met FUSE 2: gewoon starten")
else:
    print("(geen C-compiler: de test met een echte AppImage is overgeslagen)")

klopt(ai.installeer(elf) == (False, "geen-appimage"), "installeren van iets dat geen AppImage is: nee")
klopt(not ai.verwijder("../../etc") and not ai.verwijder("bestaat-niet"), "verwijderen: alleen een veilige, bekende naam")

# ------------------------------------------------------------------------------------------- het venster
import bugos_ui  # noqa: E402

app = bugos_ui.maak_app("bugos-programmas-test", "bugos-programmas-test", ["test"])
stap = {}


def doe(w) -> int:
    w.show()
    app.processEvents()
    stap["f"](w)
    w.close()
    return 0


bugos_ui.uitvoeren = lambda _a, w: doe(w)
bugos_ui.vraag_ja = lambda *_a, **_k: True
nep("konsole", 'echo "konsole $*" >>"$NEP_LOG"\n')
nep("bugos-store", 'echo "store $*" >>"$NEP_LOG"\n')
nep("bugos-quarantaine", 'echo "quarantaine $*" >>"$NEP_LOG"\n')
venster_ai, kopie_ai = laad("bugos_appimage_app", BIN / "bugos-appimage")

if echt:
    tweede = THUIS / "Downloads" / "Tekenen-3.0.AppImage"
    shutil.copy2(bron, tweede)
    tweede.chmod(0o644)   # zoals na een download: nog niet uitvoerbaar

    def stap_appimage(w):
        klopt(w.soort == "appimage" and "Tekenen Pro NL" in w.titel.text() and w.derde.isVisible(),
              f"venster: AppImage herkend, de naam uit het programma ({w.titel.text()!r})")
        w.hoofd.click()
        klopt(w.geinstalleerd is not None and w.melding.soort == "goed" and "startmenu" in w.melding.tekst.text()
              and w.hoofd.text() == "Openen", f"venster: Installeren, en dan 'staat in je startmenu' ({w.melding.tekst.text()!r})")

    stap["f"] = stap_appimage
    venster_ai.venster(tweede)

LOG.unlink(missing_ok=True)


def stap_script(w):
    klopt(w.soort == "script" and not w.derde.isVisible(), "venster: een .run-installatiescript herkend")
    w.hoofd.click()
    eind = time.monotonic() + 5
    while "konsole" not in log() and time.monotonic() < eind:
        time.sleep(0.05)
    klopt(f"konsole --hold -e bash {script.resolve()}" in log(), "venster: het script opent in een terminal")


stap["f"] = stap_script
venster_ai.venster(script)


def stap_onbekend(w):
    klopt(w.soort == "onbekend" and not w.tweede.isVisible() and w.hoofd.text() in ("Kijk in de Winkel", "Look in the Store"),
          "venster: een onbekend bestand: uitleg en de Winkel, niets uitvoeren")


stap["f"] = stap_onbekend
venster_ai.venster(elf)
r = subprocess.run([sys.executable, str(kopie_ai), "lijst"], capture_output=True, text=True)
klopt(r.returncode == 0 and (not echt or "org-voorbeeld-tekenen\tTekenen Pro NL" in r.stdout), f"terminal: lijst ({r.stdout!r})")
r = subprocess.run([sys.executable, str(kopie_ai), "onzin"], capture_output=True, text=True)
klopt(r.returncode == 2, "terminal: iets onbekends: de uitleg (code 2)")

# ============================================================================================= Windows
import bugos_windows as w  # noqa: E402

nep("wine", r'''echo "wine WINEPREFIX=$WINEPREFIX $*" >>"$NEP_LOG"
if [ "$1 $2" = "uninstaller --list" ]; then
    printf '{90160000-008C-0000-1000-0000000FF1CE}|||Notepad++ (64-bit)\n-rf|||Kwaadaardig\nZoom|||Zoom\nkapotte regel\n'
fi
''')
nep("winetricks", r'''echo "winetricks WINEPREFIX=$WINEPREFIX $*" >>"$NEP_LOG"
[ "$2" = dotnet48 ] && exit 1
echo "$2" >>"$WINEPREFIX/winetricks.log"
''')
klopt(w.programmas() == [], "nog geen Windows-map: geen programma's (en Wine niet gestart)")
(w.prefix() / "drive_c").mkdir(parents=True)
(w.prefix() / "system.reg").write_text("")
lijst = w.programmas()
klopt([p["naam"] for p in lijst] == ["Notepad++ (64-bit)", "Zoom"], f"de lijst uit wine uninstaller ({lijst})")
klopt(w.verwijder_opdracht("{90160000-008C-0000-1000-0000000FF1CE}")[-2:] == ["--remove", "{90160000-008C-0000-1000-0000000FF1CE}"]
      and w.verwijder_opdracht("-rf") is None and w.verwijder_opdracht("a;b") is None,
      "verwijderen: alleen een veilige sleutel (nooit iets dat met - begint)")
klopt(w.onderdeel_opdracht("rm") is None and w.onderdeel_opdracht("vcrun2022") == [w.WINETRICKS, "-q", "vcrun2022"],
      "onderdelen: alleen de bekende namen gaan naar winetricks, zonder vragen (-q)")
klopt(w.installeer_onderdeel("vcrun2022") == (True, "") and w.onderdelen_erop() == {"vcrun2022"}
      and f"WINEPREFIX={w.prefix()} -q vcrun2022" in log(),
      "een onderdeel toevoegen: in de Windows-map van BugOS; daarna staat het erop")
klopt(w.installeer_onderdeel("dotnet48") == (False, "mislukt"), "een onderdeel dat niet lukt: 'mislukt'")
klopt(not w.office_staat() and len(w.office_aan()) == 5 and w.office_staat(), "Microsoft 365 in het startmenu")
word = configparser.ConfigParser(interpolation=None)
word.optionxform = str
word.read(THUIS / ".local/share/applications/bugos-m365-word.desktop")
klopt(word["Desktop Entry"]["Exec"] == "bugos-webapp https://www.office.com/launch/word"
      and word["Desktop Entry"]["Categories"] == "Office;", "Word: een web-app via bugos-webapp, bij Kantoor")
klopt(word["Desktop Entry"]["Icon"] == "bugos-m365-word"
      and all((ROOT / f"system_files/usr/share/icons/BugOS/apps/scalable/bugos-m365-{k}.svg").is_file()
              for k, *_ in w.OFFICE), "Microsoft 365: eigen, duidelijke pictogrammen (in het BugOS-thema)")
# Een oude starter (met het oude pictogram) wordt bij het inloggen bijgewerkt; zonder Microsoft 365 gebeurt er niets.
_oud = THUIS / ".local/share/applications/bugos-m365-word.desktop"
_oud.write_text(_oud.read_text().replace("Icon=bugos-m365-word", "Icon=x-office-document"))
klopt(w.office_bijwerken() and "Icon=bugos-m365-word" in _oud.read_text() and not w.office_bijwerken(),
      "Microsoft 365: oude starters krijgen bij het inloggen de nieuwe pictogrammen (één keer)")
w.office_uit()
klopt(not w.office_staat() and not list((THUIS / ".local/share/applications").glob("bugos-m365-*")),
      "Microsoft 365 uit het startmenu")
klopt(not w.office_bijwerken() and not list((THUIS / ".local/share/applications").glob("bugos-m365-*")),
      "bijwerken zet Microsoft 365 niet aan als het uit staat")
klopt(w.is_office_installatie("OfficeSetup.exe") and w.is_office_installatie("Setup.X64.nl-nl_O365ProPlusRetail.exe")
      and not w.is_office_installatie("LibreOffice_25.2.0_Win_x86-64.msi") and not w.is_office_installatie("spel.exe"),
      "het installatieprogramma van Office herkennen (niet LibreOffice)")

# Het venster
nep("bugos-exe", 'echo "exe $*" >>"$NEP_LOG"\n')
venster_w, kopie_w = laad("bugos_windows_app", BIN / "bugos-windows")


def stap_windows(v):
    rijen = v.programmas.findChildren(bugos_ui.Rij)
    namen = [r.findChildren(bugos_ui.QLabel)[1].text() for r in rijen] if rijen else []
    klopt(any("Notepad++" in n for n in namen) and any("Zoom" in n for n in namen),
          f"venster: je Windows-programma's ({namen})")
    knoppen = [k for k in v.onderdelen.findChildren(bugos_ui.Knop) if k.text() in ("Toevoegen", "Add")]
    chips = v.onderdelen.findChildren(bugos_ui.Chip)
    klopt(len(chips) == 1 and len(knoppen) == len(w.ONDERDELEN) - 1,
          f"venster: Visual C++ staat erop, de rest kun je toevoegen ({len(chips)}, {len(knoppen)})")
    v.onderdeel("corefonts", "Microsoft-lettertypen")
    eind = time.monotonic() + 20
    while v.proces is not None and time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.02)
    klopt(v.melding.soort == "goed" and "corefonts" in w.onderdelen_erop(),
          f"venster: een onderdeel toevoegen lukt ({v.melding.tekst.text()!r})")
    v.office.schuif.setChecked(True)
    app.processEvents()
    klopt(w.office_staat(), "venster: de schakelaar zet Microsoft 365 in het startmenu")
    v.office.schuif.setChecked(False)
    app.processEvents()
    klopt(not w.office_staat(), "venster: en weer eruit")


stap["f"] = stap_windows
venster_w.venster()
oud = w.opnieuw_beginnen()
klopt(oud is not None and oud.exists() and (oud / "system.reg").exists() and not w.prefix().exists(),
      "opnieuw beginnen: de oude Windows-map blijft bewaard, er komt een nieuwe")
r = subprocess.run([sys.executable, str(kopie_w), "office", "aan"], capture_output=True, text=True)
klopt(r.returncode == 0 and w.office_staat(), "terminal: bugos-windows office aan")
w.office_uit()

# ============================================================================================= bugos-webapp
WEBAPP = BIN / "bugos-webapp"


def webapp(gekozen: str, geinstalleerd: list[str], adres: str = "https://www.office.com/launch/word") -> str:
    LOG.unlink(missing_ok=True)
    nep("bugos-browser", f'[ "$1" = status ] && echo "{gekozen}"\n')
    nep("flatpak", f'''if [ "$1" = info ]; then case " {' '.join(geinstalleerd)} " in *" $2 "*) exit 0 ;; esac; exit 1; fi
echo "flatpak $*" >>"$NEP_LOG"\n''')
    nep("xdg-open", 'echo "xdg-open $*" >>"$NEP_LOG"\n')
    r = subprocess.run(["bash", str(WEBAPP), adres], capture_output=True, text=True)
    return (log().strip() or r.stderr.strip())


klopt(webapp("com.microsoft.Edge", ["com.microsoft.Edge"]) == "flatpak run com.microsoft.Edge --app=https://www.office.com/launch/word",
      "web-app: de gekozen browser (Edge) in een app-venster")
klopt(webapp("org.mozilla.firefox", ["org.mozilla.firefox", "com.google.Chrome"]).startswith("flatpak run com.google.Chrome --app="),
      "web-app: Firefox gekozen maar Chrome is er ook: Chrome voor het app-venster")
klopt(webapp("org.mozilla.firefox", ["org.mozilla.firefox"]) == "flatpak run org.mozilla.firefox --new-window https://www.office.com/launch/word",
      "web-app: alleen Firefox: een nieuw venster")
klopt(webapp("", []) == "xdg-open https://www.office.com/launch/word", "web-app: geen browser bekend: gewoon openen")
klopt(webapp("", [], "https://x.nl/$(id)").startswith("Gebruik") and webapp("", [], "file:///etc/passwd").startswith("Gebruik"),
      "web-app: alleen een gewoon https-adres")

# ============================================================================================= Instellingen en Bestanden
import bugos_settings_apps as sa  # noqa: E402

(w.prefix()).mkdir(parents=True, exist_ok=True)
(w.prefix() / "system.reg").write_text("")
andere = sa.andere_apps()
soorten = sorted({a["soort"] for a in andere})
klopt(soorten == (["appimage", "windows"] if echt else ["windows"]) and any(a["naam"] == "Zoom" for a in andere),
      f"Instellingen > Geïnstalleerde apps: ook AppImages en Windows-programma's ({[a['naam'] for a in andere]})")
import bugos_files_bewerken as fb  # noqa: E402

klopt(fb.eigen_opener(Path("x.AppImage")) == "bugos-appimage" and fb.eigen_opener(Path("y.run")) == "bugos-appimage"
      and fb.eigen_opener(Path("z.BAT")) == "bugos-exe" and fb.eigen_opener(Path("s.lnk")) == "bugos-exe"
      and fb.eigen_opener(Path("doc.txt")) is None, "Bestanden: .AppImage en .run naar bugos-appimage, .bat en .lnk naar bugos-exe")
mime = (ROOT / "system_files/etc/xdg/kde-mimeapps.list").read_text()
klopt("application/vnd.appimage=bugos-appimage.desktop" in mime and "application/x-makeself=bugos-appimage.desktop" in mime,
      "dubbelklik op een AppImage of .run: bugos-appimage")
klopt("fuse-libs" in (ROOT / "build_files/packages.txt").read_text().split(), "FUSE 2 zit in het image (fuse-libs)")
for naam in ("bugos-appimage", "bugos-windows", "bugos-webapp"):
    klopt(os.access(BIN / naam, os.X_OK), f"{naam} is uitvoerbaar")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
os._exit(1 if fouten else 0)
