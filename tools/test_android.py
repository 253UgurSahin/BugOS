#!/usr/bin/env python3
"""Test van Android-apps (bugos-android, bugos_android.py en bugos-android-root), met een nagemaakte Waydroid.

De nep-waydroid doet wat de echte zegt te doen (nagekeken in de broncode van Waydroid): 'status' met 'Session:
RUNNING/STOPPED', 'session start/stop', 'app list' met 'Name:' en 'packageName:', 'app install', en 'init' (zet
waydroid.cfg en rootfs neer). pkexec, id, systemctl en firewall-cmd zijn ook nep. Wat we nagaan:
  - de stand: geen (Waydroid ontbreekt), niet-klaar, uit, aan;
  - klaarzetten (beheerdersdeel): init zonder Google (VANILLA), elke app een eigen venster (waydroid.cfg), de firewall
    laat het Android-netwerk door, de dienst aan; verwijderen: alleen de map van Waydroid, dienst uit;
  - een .apk: alleen een echt .apk-bestand; installeren start Android eerst en geeft de naam van de nieuwe app;
  - F-Droid halen (een te klein bestand telt niet), de pakketnaam-controle, je eigen Android-gegevens weg;
  - de terminal (status, installeer, fdroid, onbekend) en het venster (de standen en knoppen, klaarzetten en daarna
    meteen de .apk waarop je dubbelklikte, F-Droid installeren, verwijderen);
  - de starter (.desktop) en dat een .apk met dubbelklik in Android-apps opengaat.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_android.py
"""

from __future__ import annotations

import configparser
import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
ROOT_HULP = ROOT / "system_files" / "usr" / "libexec" / "bugos-android-root"
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-android-"))
THUIS = TMP / "thuis"
THUIS.mkdir()
NEP = TMP / "nep"
NEP.mkdir()
DATA = TMP / "var" / "waydroid"
STAAT = TMP / "staat"   # wat de nep-waydroid onthoudt
STAAT.mkdir()
LOG = TMP / "log"
os.environ.update({
    "HOME": str(THUIS), "XDG_CACHE_HOME": str(THUIS / ".cache"), "XDG_DATA_HOME": str(THUIS / ".local" / "share"),
    "BUGOS_WAYDROID": str(NEP / "waydroid"), "BUGOS_WAYDROID_DATA": str(DATA), "NEP_STAAT": str(STAAT),
    "NEP_LOG": str(LOG), "NEP_DATA": str(DATA), "NEP_ROOT_HULP": str(ROOT_HULP),
    "PATH": f"{NEP}:{os.environ.get('PATH', '/usr/bin:/bin')}",
})
os.environ.pop("BUGOS_FDROID_URL", None)

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


# De nep-waydroid. Een app installeren: de naam van het bestand (zonder .apk) wordt de app; 'kapot' in de naam lukt niet.
nep("waydroid", r'''echo "waydroid $*" >> "$NEP_LOG"
case "$1 ${2:-}" in
"status "*)
    if [ -f "$NEP_STAAT/aan" ]; then printf 'Session:\tRUNNING\nContainer:\tRUNNING\n'
    else printf 'Session:\tSTOPPED\nVendor type:\tMAINLINE\n'; fi ;;
"session start") [ -f "$NEP_STAAT/start-niet" ] || touch "$NEP_STAAT/aan" ;;
"session stop") rm -f "$NEP_STAAT/aan" ;;
"app list")
    for f in "$NEP_STAAT"/app.*; do
        [ -e "$f" ] || continue
        n="${f##*/app.}"
        printf 'Name: %s\npackageName: org.voorbeeld.%s\ncategories:\n\tandroid.intent.category.LAUNCHER\n' "$n" "$n"
    done ;;
"app install")
    [ -f "$NEP_STAAT/aan" ] || { echo "[11:00:00] WayDroid session is stopped"; exit 0; }
    n="$(basename "$3" .apk)"
    case "$n" in *kapot*) echo "Failure [INSTALL_FAILED_NO_MATCHING_ABIS]"; exit 0 ;; esac
    touch "$NEP_STAAT/app.$n" ;;
"init "*)
    echo "Downloading system image 42%"
    mkdir -p "$NEP_DATA/rootfs"
    printf '[waydroid]\narch = x86_64\nimages_path = /var/lib/waydroid/images\n\n[properties]\nro.hardware.gralloc = gbm\n' \
        > "$NEP_DATA/waydroid.cfg"
    echo "Android with user 0 is ready" ;;
esac
''')
nep("systemctl", 'echo "systemctl $*" >> "$NEP_LOG"\n')
nep("firewall-cmd", 'echo "firewall-cmd $*" >> "$NEP_LOG"\n')
nep("id", 'if [ "${1:-}" = -u ]; then echo 0; else /usr/bin/id "$@"; fi\n')
# pkexec: alleen het echte beheerdersdeel, en dan het exemplaar uit deze map.
nep("pkexec", '''echo "pkexec $*" >> "$NEP_LOG"
[ -f "$NEP_STAAT/geen-toestemming" ] && exit 126
[ "$1" = /usr/libexec/bugos-android-root ] || exit 127
shift
exec bash "$NEP_ROOT_HULP" "$@"
''')


def log() -> str:
    return LOG.read_text() if LOG.exists() else ""


def apk(naam: str, groot: int = 2048, echt: bool = True) -> Path:
    p = TMP / naam
    p.write_bytes((b"PK\x03\x04" if echt else b"MZ\x00\x00") + b"\x00" * groot)
    return p


sys.path.insert(0, str(PY))
import bugos_android as a  # noqa: E402

# ------------------------------------------------------------------------------------------- de stand
os.environ["BUGOS_WAYDROID"] = str(TMP / "bestaat-niet")
a.WAYDROID = os.environ["BUGOS_WAYDROID"]
klopt(a.status() == "geen", "zonder Waydroid: 'geen'")
os.environ["BUGOS_WAYDROID"] = str(NEP / "waydroid")
a.WAYDROID = os.environ["BUGOS_WAYDROID"]
klopt(a.status() == "niet-klaar", "met Waydroid, nog niet klaargezet: 'niet-klaar'")
klopt(a.installeer(str(apk("vroeg.apk")))[1] == "niet-klaar", "installeren vóór het klaarzetten: 'niet-klaar'")

# ------------------------------------------------------------------------------------------- beheerdersdeel
r = subprocess.run(["bash", str(ROOT_HULP), "klaarzetten"], capture_output=True, text=True)
klopt(r.returncode == 0 and r.stdout.strip().endswith("KLAAR"), f"klaarzetten lukt ({r.stdout[-60:]!r} {r.stderr[-80:]!r})")
klopt("waydroid init -s VANILLA" in log(), "klaarzetten: Android zonder Google (init -s VANILLA)")
cfg = configparser.ConfigParser()
cfg.optionxform = str
cfg.read(DATA / "waydroid.cfg")
klopt(cfg.get("properties", "persist.waydroid.multi_windows", fallback="") == "true"
      and cfg.get("properties", "ro.hardware.gralloc", fallback="") == "gbm" and cfg.get("waydroid", "arch") == "x86_64",
      "klaarzetten: elke app een eigen venster; de rest van waydroid.cfg blijft")
klopt("firewall-cmd --permanent --zone=trusted --add-interface=waydroid0" in log(),
      "klaarzetten: de firewall laat het netwerk van Android door (alleen waydroid0)")
klopt("systemctl enable --now waydroid-container.service" in log(), "klaarzetten: de Android-dienst aan")
klopt(a.status() == "uit", "na het klaarzetten: 'uit' (klaar, Android draait nog niet)")
nep_id = NEP / "id"
nep_id.rename(NEP / "id.uit")
r = subprocess.run(["bash", str(ROOT_HULP), "klaarzetten"], capture_output=True, text=True)
(NEP / "id.uit").rename(nep_id)
klopt(os.geteuid() == 0 or r.returncode == 1, "het beheerdersdeel weigert zonder beheerder")
r = subprocess.run(["bash", str(ROOT_HULP), "iets"], capture_output=True, text=True)
klopt(r.returncode == 2, "beheerdersdeel: een onbekende opdracht doet niets (code 2)")
r = subprocess.run(["bash", str(ROOT_HULP), "verwijderen"], capture_output=True, text=True,
                   env={**os.environ, "BUGOS_WAYDROID_DATA": str(THUIS)})
klopt(THUIS.exists(), "verwijderen gooit alleen een map die 'waydroid' heet weg, nooit iets anders")

# ------------------------------------------------------------------------------------------- apk en installeren
klopt(a.is_apk(str(apk("goed.apk"))) and not a.is_apk(str(apk("nep.apk", echt=False)))
      and not a.is_apk(str(apk("goed.zip"))) and not a.is_apk(str(TMP / "weg.apk")),
      "alleen een echt .apk-bestand telt (de naam, en van binnen een zip)")
klopt(a.installeer(str(apk("nep2.apk", echt=False))) == (False, "geen-apk"), "geen echte .apk: niet installeren")
(STAAT / "start-niet").touch()
klopt(a.start(wacht_s=0.3, stap_s=0.05) is False, "start Android niet: niet eindeloos wachten")
(STAAT / "start-niet").unlink()
gelukt, naam = a.installeer(str(apk("Rekenmachine.apk")))
klopt(gelukt and naam == "Rekenmachine" and a.status() == "aan",
      f"installeren start Android eerst en geeft de naam van de nieuwe app ({gelukt}, {naam!r})")
klopt(a.apps() == {"org.voorbeeld.Rekenmachine": "Rekenmachine"}, f"app list wordt gelezen ({a.apps()})")
klopt(a.installeer(str(apk("kapot.apk"))) == (False, "mislukt"), "een app die niet kan (bijv. alleen ARM): 'mislukt'")
klopt(a.stop() and a.status() == "uit", "Android stoppen")
klopt(a.open_app("org.voorbeeld.Rekenmachine") and not a.open_app("--help") and not a.open_app("a;rm -rf /"),
      "een app openen: alleen een echte pakketnaam gaat naar waydroid")

# ------------------------------------------------------------------------------------------- F-Droid
klein = apk("klein.apk", groot=100)
a.FDROID_URL = klein.as_uri()
klopt(a.fdroid_halen(TMP / "dl1") is None, "F-Droid: een te klein bestand telt niet (afgebroken download)")
groot = apk("fdroid-bron.apk", groot=1_200_000)
a.FDROID_URL = groot.as_uri()
klopt(a.fdroid_halen(TMP / "dl2") == TMP / "dl2" / "F-Droid.apk", "F-Droid downloaden")
a.FDROID_URL = (TMP / "bestaat-niet.apk").as_uri()
klopt(a.fdroid_halen(TMP / "dl3") is None, "F-Droid: download mislukt → None")

# ------------------------------------------------------------------------------------------- eigen gegevens
apps_map = THUIS / ".local" / "share" / "applications"
apps_map.mkdir(parents=True)
(apps_map / "waydroid.org.voorbeeld.Rekenmachine.desktop").write_text("[Desktop Entry]\n")
(apps_map / "firefox.desktop").write_text("[Desktop Entry]\n")
(THUIS / ".local" / "share" / "waydroid").mkdir()
a.eigen_gegevens_weg()
klopt(not (THUIS / ".local" / "share" / "waydroid").exists() and (apps_map / "firefox.desktop").exists()
      and not list(apps_map.glob("waydroid.*")), "je eigen Android-gegevens en Android-starters weg; de rest blijft")

# ------------------------------------------------------------------------------------------- terminal
# Een kopie die de modules uit deze map haalt (zoals in test_quarantaine.py); het venster start ook deze kopie.
BA = TMP / "bugos-android"
BA.write_text((BIN / "bugos-android").read_text().replace("/usr/lib/bugos/python", str(PY)))
BA.chmod(0o755)


def roep(*args: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BA), *args], capture_output=True, text=True,
                          env={**os.environ, **env}, timeout=60)


klopt(roep("status").stdout.strip() == "uit", "terminal: status")
r = roep("installeer", str(apk("Notities.apk")))
klopt(r.returncode == 0 and r.stdout.strip() == "Notities", f"terminal: installeer ({r.stdout!r})")
r = roep("installeer", str(apk("kapot2.apk")))
klopt(r.returncode == 1 and r.stdout.strip() == "mislukt", "terminal: installeer die mislukt: code 1")
r = roep("fdroid", BUGOS_FDROID_URL=(TMP / "weg.apk").as_uri())
klopt(r.returncode == 1 and r.stdout.strip() == "download-mislukt", "terminal: fdroid zonder internet")
r = roep("onzin", "x")
klopt(r.returncode == 2 and "bugos-android" in r.stderr, "terminal: iets onbekends geeft de uitleg (code 2), geen venster")

# ------------------------------------------------------------------------------------------- venster
lader = importlib.machinery.SourceFileLoader("bugos_android_app", str(BA))
spec = importlib.util.spec_from_loader("bugos_android_app", lader)
mod = importlib.util.module_from_spec(spec)
lader.exec_module(mod)
import bugos_ui  # noqa: E402

app = bugos_ui.maak_app("bugos-android", "bugos-android", ["bugos-android"])
vragen: list[str] = []
bugos_ui.vraag_ja = lambda _o, titel, *_a, **_k: vragen.append(titel) or True
stappen = {}


def wacht(voorwaarde, s: float = 20) -> bool:
    eind = time.monotonic() + s
    while not voorwaarde() and time.monotonic() < eind:
        app.processEvents()
        time.sleep(0.02)
    return voorwaarde()


def doe(w) -> int:
    w.show()
    app.processEvents()
    stappen["stap"](w)
    w.close()
    return 0


bugos_ui.uitvoeren = lambda _app, w: doe(w)


def zichtbaar(w) -> set[str]:
    return {n for n in ("klaarzetten", "fdroid", "apk_knop", "aanuit", "weg") if getattr(w, n).isVisible()}


def stap_uit(w):
    if os.environ.get("BUGOS_ANDROID_FOTO"):
        app.processEvents()
        w.grab().save(os.environ["BUGOS_ANDROID_FOTO"] + "/android-klaar.png")
    klopt(w.stand == "uit" and zichtbaar(w) == {"fdroid", "apk_knop", "aanuit", "weg"},
          f"venster, klaar: F-Droid, een .apk, starten en verwijderen ({zichtbaar(w)})")
    klopt(w.aanuit.text() in ("Android starten", "Start Android"), "venster: de knop zegt 'Android starten'")
    os.environ["BUGOS_FDROID_URL"] = groot.as_uri()
    w.fdroid.click()
    klopt(not w.fdroid.isEnabled() and w.balk.isVisible(), "venster: tijdens het werk staan de knoppen stil")
    klopt(wacht(lambda: w.proces is None), "venster: F-Droid is klaar")
    klopt("F-Droid" in w.melding.tekst.text() and w.melding.soort == "goed" and w.stand == "aan",
          f"venster: 'F-Droid is geïnstalleerd', en Android draait ({w.melding.tekst.text()!r})")
    klopt(w.aanuit.text() in ("Android stoppen", "Stop Android"), "venster: nu 'Android stoppen'")
    w.aanuit.click()
    klopt(wacht(lambda: w.proces is None) and w.stand == "uit", "venster: Android stoppen")
    w.verwijderen()
    klopt(wacht(lambda: w.proces is None), "venster: verwijderen is klaar")
    klopt(vragen[-1] in ("Android verwijderen?", "Remove Android?") and w.stand == "niet-klaar"
          and not DATA.exists() and "systemctl disable --now waydroid-container.service" in log()
          and "--remove-interface=waydroid0" in log(),
          "venster: verwijderen vraagt eerst, en dan zijn Android, de dienst en de firewall-regel weg")


a.stop()   # de terminal-test liet Android aan
stappen["stap"] = stap_uit
mod.venster("")


def stap_dubbelklik(w):
    if os.environ.get("BUGOS_ANDROID_FOTO"):
        app.processEvents()
        w.grab().save(os.environ["BUGOS_ANDROID_FOTO"] + "/android-niet-klaar.png")
    klopt(w.stand == "niet-klaar" and zichtbaar(w) == {"klaarzetten"} and "1 GB" in w.uitleg.text(),
          f"venster, nog niet klaar: alleen 'Android klaarzetten', met de uitleg (1 GB) ({zichtbaar(w)})")
    klopt(wacht(lambda: w.melding.isVisible(), 3) and "Spelletje.apk" in w.melding.tekst.text() and w.apk,
          "dubbelklik op een .apk vóór het klaarzetten: eerst klaarzetten, de app wordt onthouden")
    (STAAT / "geen-toestemming").touch()
    w.klaarzetten.click()
    klopt(wacht(lambda: w.proces is None) and w.melding.soort == "let_op" and w.stand == "niet-klaar",
          f"venster: geen wachtwoord gegeven: een rustige melding ({w.melding.tekst.text()!r})")
    (STAAT / "geen-toestemming").unlink()
    w.klaarzetten.click()
    klopt(wacht(lambda: w.proces is not None and w.klus == "installeer", 40),
          "venster: na het klaarzetten meteen de .apk waarop je dubbelklikte")
    klopt(wacht(lambda: w.proces is None, 40) and "Spelletje" in w.melding.tekst.text() and w.melding.soort == "goed",
          f"venster: de app is geïnstalleerd ({w.melding.tekst.text()!r})")
    klopt(vragen[-1] in ("Deze Android-app installeren?", "Install this Android app?"), "venster: eerst gevraagd")


stappen["stap"] = stap_dubbelklik
vragen.clear()
mod.venster(str(apk("Spelletje.apk")))


def stap_geen_apk(w):
    klopt(wacht(lambda: w.melding.isVisible(), 3) and w.melding.soort == "fout" and w.proces is None,
          "venster: een bestand dat geen .apk is: een melding, niets geïnstalleerd")


stappen["stap"] = stap_geen_apk
mod.venster(str(apk("geen.apk", echt=False)))

os.environ["BUGOS_WAYDROID"] = str(TMP / "bestaat-niet")
mod.a.WAYDROID = os.environ["BUGOS_WAYDROID"]


def stap_geen(w):
    klopt(w.stand == "geen" and not zichtbaar(w), "venster zonder Waydroid: uitleg, geen knoppen")


stappen["stap"] = stap_geen
mod.venster("")

# ------------------------------------------------------------------------------------------- starter en dubbelklik
st = configparser.ConfigParser(interpolation=None)
st.optionxform = str
st.read(ROOT / "system_files" / "usr" / "share" / "applications" / "bugos-android.desktop")
e = st["Desktop Entry"]
klopt(e["Exec"] == "bugos-android %f" and "application/vnd.android.package-archive" in e["MimeType"]
      and e.get("Name[nl]") == "Android-apps", "de starter: 'Android-apps', opent een .apk")
mime = (ROOT / "system_files" / "etc" / "xdg" / "kde-mimeapps.list").read_text()
klopt("application/vnd.android.package-archive=bugos-android.desktop" in mime, "dubbelklik op een .apk: Android-apps")
pakketten = (ROOT / "build_files" / "packages.txt").read_text().split()
klopt("waydroid" in pakketten, "Waydroid zit in het image (packages.txt)")
beleid = (ROOT / "system_files" / "usr" / "share" / "polkit-1" / "actions" / "org.bugos.android.policy").read_text()
klopt("/usr/libexec/bugos-android-root" in beleid and "auth_admin_keep" in beleid,
      "polkit: alleen het beheerdersdeel, met je wachtwoord")
klopt(a.ROOT_HULP == "/usr/libexec/bugos-android-root" and os.access(ROOT_HULP, os.X_OK)
      and os.access(BIN / "bugos-android", os.X_OK), "de programma's zijn uitvoerbaar en de paden kloppen")
# build.sh zet alles eerst op 0644 en daarna alleen bepaalde programma's weer op 0755. Het beheerdersdeel moet daar
# bij zitten: anders vraagt pkexec wel je wachtwoord, maar start het hulpje daarna niet ('wachtwoord niet goed').
bouw = (ROOT / "build_files" / "build.sh").read_text()
klopt(re.search(r"^chmod 0755 .*/usr/libexec/bugos-(\*|android-root)", bouw, re.M) is not None,
      "build.sh maakt het beheerdersdeel uitvoerbaar (anders 'wachtwoord niet goed' bij klaarzetten)")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.stdout.flush()
os._exit(1 if fouten else 0)
