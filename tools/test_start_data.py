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
(apps / "tr.desktop").write_text("[Desktop Entry]\nType=Application\nName=Sistem İzleyicisi\nCategories=System;\n")
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
_mist = [w for w in ["night light", "night", "sleep", "screen reader", "sticky keys", "do not disturb", "version", "mute", "font", "scale", "game mode", "left-handed", "lid", "screen off", "about", "magnifier", "lock screen"]
         if not any(all(d in a["zoek"] for d in w.split()) for a in data["apps"] if a["soort"] == "instelling")]
_mist2 = [w for w in ("opslag", "fps", "dubbelklik", "lettergrootte", "taakbalk") if not any(w in a["zoek"] for a in data["apps"] if a["soort"] == "instelling")]
klopt(not _mist2, f"U358: het startmenu vindt ook 'opslag', 'fps', 'dubbelklik', 'lettergrootte' en 'taakbalk' (niet: {_mist2})")
klopt(not _mist and any(a["pad"] == "instelling:over" for a in data["apps"]),
      f"U069: startmenu vindt instellingen ook in het Engels, en 'Over deze computer' (niet: {_mist})")
_tr = next((a for a in data["apps"] if a["naam"] == "Sistem İzleyicisi"), None)
klopt(_tr is not None and "izleyici" in _tr["zoek"],
      f"U268: de zoektekst van 'Sistem İzleyicisi' bevat 'izleyici' (Turkse İ), zodat het startmenu hem vindt ({_tr and _tr['zoek']!r})")
namen = [a["naam"] for a in data["apps"] if a["soort"] == "app"]
klopt(namen == ["Bestanden", "Firefox", "Sistem İzleyicisi", "Steam"], f"gegevens: apps op naam, verborgen niet ({namen})")
fav = [a["id"] for a in data["favorieten"]]
klopt(fav == ["firefox.desktop", "bugos-files.desktop", "steam.desktop"],
      f"favorieten: Firefox en Steam ook onder hun rpm-naam, zonder dubbelen ({fav})")
klopt(all(a["soort"] == "app" for a in data["favorieten"]), "favorieten: geen instellingenpagina's")
# U414: een favorietenbestand dat geen lijst is (null), maakt het startmenu niet leeg.
(TMP / "thuis" / ".config" / "bugos").mkdir(parents=True, exist_ok=True)
(TMP / "thuis" / ".config" / "bugos" / "favorieten.json").write_text("null")
try:
    _d414 = json.loads(draai())
except ValueError:
    _d414 = {}
(TMP / "thuis" / ".config" / "bugos" / "favorieten.json").unlink()
klopt(bool(_d414.get("apps")) and bool(_d414.get("favorieten")), "U414: favorieten.json met 'null': het startmenu blijft gevuld")

# 2. snelmenu-status
# U061: zonder bluetooth-hardware vragen we bluetoothctl niets (die zou 5 s blijven wachten).
# Zonder wifi in de computer (een pc aan een kabel): geen wifi-tegel, ook al zegt nmcli 'enabled' (U111).
(NEP / "nmcli").write_text("#!/usr/bin/bash\ncase \"$*\" in *TYPE*device*) printf 'ethernet\\nloopback\\n' ;; *) echo enabled ;; esac\n")
(NEP / "nmcli").chmod(0o755)
nep("bluetoothctl", "Waiting to connect to bluetoothd...")
LOG.write_text("")
s = json.loads(draai("--snel"))
klopt(s["wifi"] is None, f"U111: snelmenu: geen wifi in de computer: geen wifi-tegel ({s['wifi']})")
(NEP / "nmcli").write_text("#!/usr/bin/bash\ncase \"$*\" in *TYPE*device*) exit 8 ;; *) echo enabled ;; esac\n")
(NEP / "nmcli").chmod(0o755)
s = json.loads(draai("--snel"))
klopt(s["wifi"] is True, f"U123: snelmenu: nmcli antwoordt (nog) niet: de wifi-tegel blijft, net als in Instellingen ({s['wifi']})")
(NEP / "nmcli").write_text("#!/usr/bin/bash\ncase \"$*\" in *TYPE*device*) printf 'wifi\\nethernet\\n' ;; *) echo enabled ;; esac\n")
(NEP / "nmcli").chmod(0o755)
s = json.loads(draai("--snel"))
klopt(s["bluetooth"] is None and "bluetoothctl" not in LOG.read_text(),
      "U061: geen bluetooth in de computer: geen tegel, en bluetoothctl wordt niet gevraagd")
(TMP / "sys" / "class" / "bluetooth" / "hci0").mkdir(parents=True, exist_ok=True)
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

# U346: een batterij die niet BAT0 heet (CMB0) staat toch in het snelmenu; die van een muis (scope=Device) niet.
import shutil as _sh  # noqa: E402

_sh.rmtree(TMP / "sys" / "class" / "power_supply" / "BAT0")
for _n, _w in (("CMB0", {"type": "Battery", "capacity": "55", "status": "Discharging"}),
               ("hidpp_battery_0", {"type": "Battery", "scope": "Device", "capacity": "10", "status": "Discharging"})):
    (TMP / "sys" / "class" / "power_supply" / _n).mkdir(parents=True)
    for _k, _v in _w.items():
        (TMP / "sys" / "class" / "power_supply" / _n / _k).write_text(_v + "\n")
# U347: zonder geluid (geen standaard-luidspreker) is ook 'Geluid uit' grijs.
nep("wpctl", "")
_s = json.loads(draai("--snel"))
klopt(_s["batterij"] == 55 and _s["volume"] is None and _s["stil"] is None,
      f"U346/U347: batterij CMB0 telt (muisbatterij niet); zonder geluid is ook 'Geluid uit' grijs ({_s['batterij']}, {_s['stil']})")
# U352: in recente bestanden wordt alleen het begin van het pad '~' (niet een map die ook zo heet).
klopt('.replace(str(HOME), "~")' not in SCRIPT.read_text(), "U352: in recente bestanden wordt alleen het begin van het pad '~'")

# 4. knoppen omzetten
LOG.write_text("")
nep("kwriteconfig6")
nep("plasma-apply-colorscheme")
nep("plasma-apply-desktoptheme")
draai("--zet", "volume", "40")
klopt("wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.40" in logboek() and "set-mute" not in logboek(),
      "zet volume: alleen het volume, niet stil/aan")
LOG.write_text("")
_donker = json.loads(draai("--zet", "donker", "aan"))
klopt(_donker["donker"] is True, "U128: Donker aantikken in het snelmenu toont meteen 'aan' (bugos-theme loopt nog)")
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

# U504: bluetooth aan in het snelmenu na de vliegtuigstand: eerst wachten tot de kaart er is, dan 'power on'.
LOG.write_text("")
(NEP / "bluetoothctl").write_text(f'#!/usr/bin/bash\necho "bluetoothctl $*" >>"{LOG}"\n'
                                  f'[ "$1" = show ] && [ "$(grep -c "bluetoothctl show" "{LOG}")" -ge 2 ] && echo "Controller AA"\nexit 0\n')
(NEP / "bluetoothctl").chmod(0o755)
nep("rfkill")
draai("--zet", "bluetooth", "aan")
_volg504 = [r.split()[0] + " " + r.split()[1] for r in logboek().splitlines() if r.startswith(("rfkill", "bluetoothctl"))]
klopt(_volg504[:1] == ["rfkill unblock"] and "bluetoothctl power" in _volg504
      and _volg504[:_volg504.index("bluetoothctl power")].count("bluetoothctl show") >= 2,
      f"U504: bluetooth aan in het snelmenu wacht op de kaart ({_volg504})")
# U517: tijdens het wachten klik je 'uit': dan niet daarna alsnog 'aan'.
_run517 = TMP / "run517"
_run517.mkdir()
LOG.write_text("")
(NEP / "bluetoothctl").write_text(f'#!/usr/bin/bash\necho "bluetoothctl $*" >>"{LOG}"\n'
                                  f'[ "$1" = show ] && echo nieuwer >"{_run517}/bugos-bt-wens-$(id -u)"\nexit 0\n')
(NEP / "bluetoothctl").chmod(0o755)
draai("--zet", "bluetooth", "aan", env_extra={"XDG_RUNTIME_DIR": str(_run517)})
klopt("bluetoothctl power on" not in logboek(), "U517: bluetooth: de laatste klik telt (geen 'aan' na een nieuwere klik)")
nep("bluetoothctl", "Controller 00:11:22:33:44:55 BugOS [default]\n\tPowered: yes")
# U260: game-modus vanuit het snelmenu wordt niet na 5 s afgebroken (dan bleef 'volle kracht' half aan staan).
LOG.write_text("")
(NEP / "bugos-game-mode").write_text(f'#!/usr/bin/bash\n[ "$1" = aan ] && sleep 6\necho "bugos-game-mode $*" >>"{LOG}"\necho uit\n')
(NEP / "bugos-game-mode").chmod(0o755)
_t0 = time.time()
_spel = json.loads(draai("--zet", "spel", "aan"))
_duur = time.time() - _t0
for _ in range(100):
    if "bugos-game-mode aan" in logboek():
        break
    time.sleep(0.1)
klopt(_spel["spel"] is True and _duur < 5 and "bugos-game-mode aan" in logboek(),
      f"U260: game-modus aan vanuit het snelmenu loopt helemaal door (los gestart) en toont meteen 'aan' ({_duur:.1f} s)")

# 5. starten
LOG.write_text("")
nep("bugos-settings")
draai("--start", "instelling:wifi")
import time  # noqa: E402

time.sleep(0.5)
klopt("bugos-settings wifi" in logboek(), "start: 'instelling:wifi' opent BugOS Instellingen op de wifi-pagina")

# U112: de foto van de gebruiker met zijn tijd (dan laadt het startmenu een nieuwe foto opnieuw).
# U113: ook recente bestanden van apps uit de Winkel (Flatpak, met een eigen lijst in ~/.var/app).
import getpass  # noqa: E402

_iconen = TMP / "accounts-iconen"
_iconen.mkdir()
(_iconen / getpass.getuser()).write_bytes(b"png")
_doc = TMP / "thuis" / "brief.odt"
_doc.parent.mkdir(parents=True, exist_ok=True)
_doc.write_text("x")
_flatpak = TMP / "thuis" / ".var" / "app" / "org.libreoffice.LibreOffice" / "data"
_flatpak.mkdir(parents=True)
(_flatpak / "recently-used.xbel").write_text(
    '<?xml version="1.0"?><xbel version="1.0"><bookmark href="file://' + str(_doc) +
    '" added="2026-11-09T10:00:00Z" modified="2026-11-09T10:00:00Z" visited="2026-11-09T10:00:00Z"/></xbel>')
_d = json.loads(draai(env_extra={"BUGOS_ACCOUNTS_ICONEN": str(_iconen)}))
klopt(_d["gebruiker"]["foto"] == str(_iconen / getpass.getuser()) and _d["gebruiker"].get("foto_tijd", 0) > 0,
      f"U112: de foto van de gebruiker, met de tijd erbij ({_d['gebruiker']})")
klopt(any(r["pad"] == str(_doc) for r in _d["recent"]), f"U113: recente bestanden van een Winkel-app staan erbij ({_d['recent'][:2]})")
_sm = (ROOT / "system_files/usr/share/plasma/plasmoids/org.bugos.startmenu/contents/ui/StartMenu.qml").read_text()
klopt("foto_tijd" in _sm and "cache: false" in _sm, "U112: het startmenu laadt een nieuwe foto opnieuw")

# U072: 'niet storen tot' zoals KDE het echt schrijft (seconden met komma-deel, soms een tijdzone erachter).
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
_lader = importlib.machinery.SourceFileLoader("bugos_start_data_mod", str(SCRIPT))
sd = importlib.util.module_from_spec(importlib.util.spec_from_loader(_lader.name, _lader))
_lader.exec_module(sd)
sys.path.insert(0, str(SCRIPT.parent.parent / "lib" / "bugos" / "python"))
import bugos_base as _bb  # noqa: E402

klopt(all(sd.zoeksleutel(w) == _bb.zoeksleutel(w) for w in ("größe", "οδηγός", "İstanbul", "がぞう", "Café")),
      "U280: bugos-start-data en de apps maken dezelfde zoeksleutel")
_kde = lambda d, sec="7.913": f"{d.year},{d.month},{d.day},{d.hour},{d.minute},{sec}"  # noqa: E731
_u = datetime.now(timezone.utc)
klopt(sd.niet_storen_tot_in_toekomst(_kde(datetime.now() + timedelta(hours=1)))
      and not sd.niet_storen_tot_in_toekomst(_kde(datetime.now() - timedelta(minutes=10)))
      and sd.niet_storen_tot_in_toekomst(_kde(_u + timedelta(hours=2), "12.345") + ",UTC")
      and not sd.niet_storen_tot_in_toekomst(_kde(_u - timedelta(hours=2)) + ",UTC"),
      "U072: snelmenu leest 'niet storen tot' met komma-seconden en tijdzone goed")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
