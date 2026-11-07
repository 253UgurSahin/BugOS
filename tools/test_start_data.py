#!/usr/bin/env python3
"""Test van bugos-start-data (de gegevens achter het startmenu en snelmenu), zonder Qt.

Nep-programma's (nmcli, wpctl, kreadconfig6, ...) staan vooraan op PATH en schrijven op wat ze
aangeroepen werden, zodat we kunnen controleren wat het script doet.

Gebruik:  python3 tools/test_start_data.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "system_files" / "usr" / "bin" / "bugos-start-data"
TMP = Path(tempfile.mkdtemp(prefix="bugos-start-data-test-"))
NEP = TMP / "nep"
LOG = TMP / "aanroepen.log"
NEP.mkdir()
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def nep(naam: str, uitvoer: str = "") -> None:
    """Een nep-programma dat zijn naam en argumenten in het logboek zet en vaste uitvoer geeft."""
    pad = NEP / naam
    pad.write_text("#!/usr/bin/bash\n"
                   f"printf '%s\\n' \"{naam} $*\" >> '{LOG}'\n"
                   f"cat <<'UIT'\n{uitvoer}\nUIT\n")
    pad.chmod(0o755)


def schoon_pad() -> str:
    """PATH zonder de echte BugOS-programma's (bugos-*): op BugOS zelf staan die in /usr/bin, en dan zou de
    test die vinden in plaats van zijn eigen nep-versies. Per map een schaduwmap met al het andere."""
    mappen = []
    for i, m in enumerate(p for p in os.environ.get("PATH", "").split(os.pathsep) if p):
        bron = Path(m)
        try:
            namen = [x.name for x in bron.iterdir()]
        except OSError:
            continue
        if not any(n.startswith("bugos-") for n in namen):
            mappen.append(m)
            continue
        schaduw = TMP / f"pad-{i}"
        schaduw.mkdir(exist_ok=True)
        for n in namen:
            if not n.startswith("bugos-") and not (schaduw / n).exists():
                (schaduw / n).symlink_to(bron / n)
        mappen.append(str(schaduw))
    return os.pathsep.join(mappen)


PAD = schoon_pad()


def draai(*args: str, env_extra: dict | None = None) -> str:
    env = dict(os.environ, PATH=f"{NEP}:{PAD}", HOME=str(TMP / "thuis"), LC_ALL="nl_NL.UTF-8",
               XDG_DATA_HOME=str(TMP / "data"), XDG_DATA_DIRS=str(TMP / "sys-share"),
               BUGOS_SYS=str(TMP / "sys"), XDG_CURRENT_DESKTOP="KDE")
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env,
                       check=False)
    return r.stdout


def logboek() -> str:
    try:
        return LOG.read_text()
    except OSError:
        return ""


# Een paar .desktop-bestanden
apps = TMP / "sys-share" / "applications"
apps.mkdir(parents=True)
(apps / "steam.desktop").write_text("[Desktop Entry]\nType=Application\nName=Steam\nCategories=Game;\nIcon=steam\n")
(apps / "firefox.desktop").write_text("[Desktop Entry]\nType=Application\nName=Firefox\nName[nl]=Firefox\n"
                                      "GenericName[nl]=Webbrowser\nCategories=Network;\nIcon=firefox\n")
(apps / "bugos-files.desktop").write_text("[Desktop Entry]\nType=Application\nName=Files\nName[nl]=Bestanden\n"
                                              "Categories=System;\nIcon=folder\n")
(apps / "geheim.desktop").write_text("[Desktop Entry]\nType=Application\nName=Geheim\nNoDisplay=true\n")
(TMP / "thuis").mkdir()
(TMP / "data").mkdir()

# 1. de gegevens voor het startmenu
data = json.loads(draai())
soorten = {a["soort"] for a in data["apps"]}
klopt(soorten == {"app", "instelling"}, "gegevens: elke app heeft een soort (app of instelling)")
wifi = next((a for a in data["apps"] if a["pad"] == "instelling:wifi"), None)
klopt(wifi is not None and wifi["naam"] == "Wifi en internet" and wifi["uitleg"] == "Instellingen"
      and "wlan" in wifi["zoek"], "gegevens: de pagina 'Wifi en internet' is te vinden met 'wlan'")
namen = [a["naam"] for a in data["apps"] if a["soort"] == "app"]
klopt(namen == ["Bestanden", "Firefox", "Steam"], f"gegevens: apps op naam, verborgen niet ({namen})")
fav = [a["id"] for a in data["favorieten"]]
klopt(fav == ["firefox.desktop", "bugos-files.desktop", "steam.desktop"],
      f"favorieten: Firefox en Steam ook onder hun rpm-naam, zonder dubbelen ({fav})")
klopt(all(a["soort"] == "app" for a in data["favorieten"]), "favorieten: geen instellingenpagina's")

# 2. snelmenu-status
nep("nmcli", "enabled")
nep("bluetoothctl", "Controller 00:11:22:33:44:55 BugOS [default]\n\tPowered: yes")
nep("wpctl", "Volume: 0.40 [MUTED]")
(NEP / "kreadconfig6").write_text("#!/usr/bin/bash\n"
                                  f"printf '%s\\n' \"kreadconfig6 $*\" >> '{LOG}'\n"
                                  "case \"$*\" in *ColorScheme*) echo BugOSDark ;; *Until*) echo '2999,12,31,0,0,0' ;; esac\n")
(NEP / "kreadconfig6").chmod(0o755)
s = json.loads(draai("--snel"))
klopt(s["wifi"] is True and s["bluetooth"] is True and s["volume"] == 40 and s["stil"] is True,
      "snel: wifi, bluetooth, volume 40% en stil uit nmcli, bluetoothctl en wpctl")
klopt(s["donker"] is True and s["niet_storen"] is True, "snel: donker (BugOSDark) en niet storen (tot 2999)")
klopt(s["spel"] is None, "snel: game-modus is 'onbekend' (knop uit) als bugos-game-mode ontbreekt")
(NEP / "kreadconfig6").write_text("#!/usr/bin/bash\n"
                                  "case \"$*\" in *ColorScheme*) echo BreezeDark ;; *Until*) echo '2001,1,1,0,0,0' ;; esac\n")
nep("bugos-game-mode", "aan")
s = json.loads(draai("--snel"))
klopt(s["donker"] is False and s["niet_storen"] is False and s["spel"] is True,
      "snel: BreezeDark telt niet als BugOS-donker, een verlopen 'tot' is niet meer niet storen, game-modus aan")

s = json.loads(draai("--snel", env_extra={"BUGOS_SNEL_VOORBEELD": "1"}))
klopt(s["wifi"] is True and s["volume"] == 60 and s["donker"] is False, "snel: voorbeeldstatus voor foto's")

# 3. tray-status
nep("nmcli", "wifi:connected\nethernet:unavailable\nloopback:unmanaged")
(TMP / "sys" / "class" / "power_supply" / "BAT0").mkdir(parents=True)
(TMP / "sys" / "class" / "power_supply" / "BAT0" / "capacity").write_text("64\n")
(TMP / "sys" / "class" / "power_supply" / "BAT0" / "status").write_text("Charging\n")
nep("wpctl", "Volume: 0.75")
tray = json.loads(draai("--tray"))
klopt(tray["internet"] == "wifi" and tray["volume"] == 75 and tray["stil"] is False and tray["batterij"] == 64
      and tray["laadt"] is True, f"tray: internet via wifi, volume 75%, batterij 64% aan het laden ({tray})")

# 4. knoppen omzetten
LOG.write_text("")
nep("kwriteconfig6")
nep("plasma-apply-colorscheme")
nep("plasma-apply-desktoptheme")
draai("--zet", "volume", "40")
klopt("wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.40" in logboek() and "set-mute" not in logboek(),
      "zet volume: alleen het volume, niet stil/aan")
LOG.write_text("")
draai("--zet", "niet_storen", "aan")
klopt("kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key Until --notify 2999,12,31,0,0,0" in logboek(),
      "zet niet storen: dezelfde waarde als Instellingen, met --notify")
LOG.write_text("")
nep("bugos-theme")
draai("--zet", "donker", "aan")
import time  # noqa: E402
for _ in range(50):  # bugos-theme start los (op de achtergrond): even wachten tot hij in het logboek staat
    if "bugos-theme donker" in logboek():
        break
    time.sleep(0.1)
klopt("bugos-theme donker" in logboek(),
      "zet donker: via bugos-theme (kleuren, KDE-programma's en Plasma-stijl in één keer, net als Instellingen)")

# 5. starten
LOG.write_text("")
nep("bugos-settings")
draai("--start", "instelling:wifi")
import time  # noqa: E402

time.sleep(0.5)
klopt("bugos-settings wifi" in logboek(), "start: 'instelling:wifi' opent BugOS Instellingen op de wifi-pagina")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
