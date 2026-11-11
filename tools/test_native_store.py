#!/usr/bin/env python3
"""Test van de BugOS Winkel zonder KDE Discover (pakket 'store'): alle apps van Flathub in de Winkel zelf.

De lijst van Flathub (appstream), flatpak, busctl en de rest zijn nep: alles gebeurt in een tijdelijke map, zonder
internet en zonder je echte apps aan te raken.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_store.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BRON = ROOT / "system_files" / "usr" / "bin" / "bugos-store"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-store-test-"))
THUIS = TMP / "thuis"
(THUIS / ".config").mkdir(parents=True)
os.environ["HOME"] = str(THUIS)
os.environ["XDG_DATA_HOME"] = str(THUIS / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(THUIS / ".config")
os.environ["XDG_CACHE_HOME"] = str(TMP / "cache")
os.environ["BUGOS_APPSTREAM"] = str(TMP / "appstream")
os.environ["LC_ALL"] = "nl_NL.UTF-8"   # de test kijkt naar de Nederlandse teksten
os.environ["BUGOS_MEERDERE"] = "1"
for _weg in ("LANGUAGE", "BUGOS_GEINSTALLEERD", "BUGOS_INSTELLINGEN_VOORBEELD", "BUGOS_WINKEL_VOORBEELD",
             "BUGOS_WINKEL_GEEN_VERVERS"):
    os.environ.pop(_weg, None)

NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "flatpak.log"
LOG.write_text("")


def nep_programma(naam: str, inhoud: str) -> None:
    (NEP / naam).write_text("#!/usr/bin/bash\n" + inhoud)
    (NEP / naam).chmod(0o755)


# Een nep-flatpak: schrijft elke opdracht in flatpak.log en antwoordt zoals de echte (TAB tussen de kolommen).
nep_programma("flatpak", f'''echo "$*" >> "{LOG}"
case "$1 $2 $3" in
  "list --app --columns=application") printf 'org.voorbeeld.Oud\\n'; exit 0 ;;
  "list --app --columns=application,name,origin") printf 'org.voorbeeld.Oud\\tOud\\tflathub\\n'; exit 0 ;;
  "list --runtime --columns=ref") printf 'org.gnome.Platform/x86_64/49\\n'; exit 0 ;;
esac
if [ "$1" = remote-ls ]; then
  printf 'app/org.voorbeeld.Radio/x86_64/stable\\t5.5\\302\\240MB\\t12.3\\302\\240MB\\torg.gnome.Platform/x86_64/49\\n'
  printf 'app/org.voorbeeld.Oud/x86_64/stable\\t309.7\\302\\240MB\\t15.9\\302\\240MB\\torg.freedesktop.Platform/x86_64/25.08\\n'
  printf 'runtime/org.freedesktop.Platform/x86_64/25.08\\t260.1\\302\\240MB\\t670.7\\302\\240MB\\t\\n'
  printf 'runtime/org.gnome.Platform/x86_64/49\\t418.8\\302\\240MB\\t1.1\\302\\240GB\\t\\n'
  exit 0
fi
if [ "$1" = install ]; then
  /usr/bin/sleep 0.3
  [ "${{BUGOS_TEST_FLATPAK:-0}}" = 9 ] && echo "error: Not authorized" && exit 1
  [ "${{BUGOS_TEST_FLATPAK:-0}}" = 8 ] && echo "error: No space left on device" && exit 1
  [ "${{BUGOS_TEST_FLATPAK:-0}}" = 7 ] && echo "error: Nothing matches $4 in remote flathub" && exit 1
  exit "${{BUGOS_TEST_FLATPAK:-0}}"
fi
if [ "$1" = update ]; then
  [ -n "$BUGOS_TEST_VERVERS_SLAAP" ] && /usr/bin/sleep "$BUGOS_TEST_VERVERS_SLAAP"
  exit "${{BUGOS_TEST_VERVERS:-0}}"
fi
exit 0
''')
nep_programma("plasma-discover", f'touch "{TMP}/discover-gestart"\n')
nep_programma("busctl", '''case "$*" in
  *NetworkManager*Metered*) echo "u ${BUGOS_TEST_METERED:-4}" ;;
  *login1*Active*) echo "b ${BUGOS_TEST_ACTIEF:-true}" ;;
  *) exit 1 ;;
esac
''')
nep_programma("kioclient", f'echo "kioclient $*" >> "{LOG}"\n')
nep_programma("xdg-open", f'echo "xdg-open $*" >> "{LOG}"\n')
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(naam: str):
    lader = importlib.machinery.SourceFileLoader(naam, str(BRON))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


BRONTEKST = BRON.read_text(encoding="utf-8")

# ============================================================== 11. geen KDE Discover meer in de Winkel ===
klopt("plasma-discover" not in BRONTEKST and "Discover" not in BRONTEKST,
      "11: de Winkel start nergens KDE Discover (en noemt het niet)")

winkel = laad("bugos_winkel_test")
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or bugos_ui.maak_app("bugos-test", "bugos-test", ["test"])
gestart: list = []
winkel.start = lambda *a: gestart.append(a) or True
APPS = TMP / "applications"
APPS.mkdir()
winkel.APP_MAPPEN = [APPS]
CAT = winkel.lees_catalogus(ROOT / "system_files" / "usr" / "share" / "bugos" / "store.json")


def wacht(voorwaarde, ms: int = 8000) -> bool:
    klok = QElapsedTimer()
    klok.start()
    while not voorwaarde() and klok.elapsed() < ms:
        app.processEvents()
    return bool(voorwaarde())


def even(ms: int) -> None:
    wacht(lambda: False, ms)


# ============================================================== 1. geen sprong meer, alles in de Winkel ===
w = winkel.Winkel(CAT)
w.resize(1180, 760)
w.show()
w.activateWindow()
from PySide6.QtTest import QTest  # noqa: E402

QTest.qWaitForWindowActive(w, 2000)
w.tweede_start(["appstream://org.mozilla.firefox"])
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "Firefox",
      f"1: een app uit de BugOS-selectie: de lijst met die app ({w.zoek.text()!r})")
w.tweede_start(["appstream://org.example.NietBijOns"])
klopt(w.stapel.currentIndex() == 1 and w.pagina_id == "org.example.NietBijOns" and gestart == [],
      f"1: een onbekende app: een eigen pagina in de Winkel, geen ander programma ({w.pagina_id}, {gestart})")
w.tweede_start(["appstream:org.videolan.vlc"])
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "VLC",
      "1: daarna een app uit de selectie (kleine letters, zonder //): terug naar de lijst met VLC (U330)")
w.tweede_start(["appstream://-rf.x.y"])
klopt(w.stapel.currentIndex() == 0 and gestart == [], "1: een id met '-' vooraan wordt nooit iets (geen optie)")
w.zoek.setText("radio")
w.toon_app("org.example.NietBijOns")
w.terug()
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "radio" and w.pagina_id is None,
      "1: Terug: de lijst weer, met dezelfde zoektekst")
w.toon_app("org.example.NietBijOns")
w.pagina.terug.setFocus()
QTest.keyClick(w.pagina.terug, Qt.Key.Key_Escape)
klopt(w.stapel.currentIndex() == 0, "1: Esc op de app-pagina = terug naar de lijst")
w.toon_app("org.example.NietBijOns")
w.lijst.setCurrentRow(1)
klopt(w.stapel.currentIndex() == 0, "1: een onderwerp in de zijbalk kiezen terwijl een app-pagina open is: de lijst")
w.zoek.setText("")
w.meer_apps()
klopt(gestart == [] and w.focusWidget() is w.zoek and "Typ hierboven" in w.opdracht_melding.tekst.text(),
      f"1: 'Alle apps doorzoeken' start niets, maar zet je in het zoekveld ({w.opdracht_melding.tekst.text()!r})")
w.zoek.setText("qqqzzz")
klopt("Niets gevonden voor \"qqqzzz\"" in w.melding.tekst.text(),
      "1: niets gevonden: een gewone zin met een voorbeeld, geen verwijzing naar een ander programma")
w.close()
klopt(not (TMP / "discover-gestart").exists(), "1: KDE Discover is nooit gestart")

print()
print("Fouten:", fouten)
sys.exit(1 if fouten else 0)
