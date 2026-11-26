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
# Een programma met een eigen BugOS-naam, en een waarvan de uitleg de naam herhaalt.
(apps / "org.kde.okular.desktop").write_text("[Desktop Entry]\nType=Application\nName=Okular\n"
                                              "GenericName=Document Viewer\nCategories=Office;\nIcon=okular\n")
(apps / "dubbel.desktop").write_text("[Desktop Entry]\nType=Application\nName=Terminal\nGenericName=Terminal\n"
                                     "Categories=System;\n")
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
klopt(namen == ["Bestanden", "Documenten bekijken", "Firefox", "Sistem İzleyicisi", "Steam", "Terminal"],
      f"gegevens: apps op naam, verborgen niet ({namen})")
_ok = next((a for a in data["apps"] if a["id"] == "org.kde.okular.desktop"), {})
klopt(_ok.get("uitleg") == "PDF's en andere documenten lezen" and "okular" in _ok.get("zoek", ""),
      f"startmenu: Okular heet 'Documenten bekijken' met een eigen uitleg, en is als 'okular' te vinden ({_ok})")
_db = next((a for a in data["apps"] if a["id"] == "dubbel.desktop"), {})
klopt(_db.get("uitleg") == "", f"startmenu: een uitleg die alleen de naam herhaalt, valt weg ({_db.get('uitleg')!r})")
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

# 2026-11: het nieuwe snelmenu en de taakbalk: of je internet hebt (het icoontje rechtsonder), Nachtlampje, en welke
# knoppen je verborg (het potlood).
(NEP / "nmcli").write_text("#!/usr/bin/bash\ncase \"$*\" in *TYPE*device*) printf 'wifi:connected\\nethernet:unavailable\\n' ;; *) echo enabled ;; esac\n")
(NEP / "nmcli").chmod(0o755)
s = json.loads(draai("--snel"))
klopt(s["internet"] == "wifi" and s["wifi"] is True and s["nachtlicht"] is False and s["verborgen"] == [],
      f"snel: internet via wifi, nachtlampje uit, niets verborgen ({s['internet']}, {s['nachtlicht']}, {s['verborgen']})")
(NEP / "nmcli").write_text("#!/usr/bin/bash\ncase \"$*\" in *TYPE*device*) printf 'wifi:disconnected\\nethernet:connected (externally)\\n' ;; *) echo enabled ;; esac\n")
(NEP / "nmcli").chmod(0o755)
s = json.loads(draai("--zet", "verborgen", "spel,wifi,rm -rf,../x"))
klopt(s["internet"] == "kabel" and s["verborgen"] == ["wifi", "spel"],
      f"snel: internet via de kabel; verbergen bewaart alleen bekende knoppen, in vaste volgorde ({s['internet']}, {s['verborgen']})")
s = json.loads(draai("--zet", "verborgen", ""))
klopt(s["verborgen"] == [], "snel: alles weer tonen")
LOG.write_text("")
nep("kwriteconfig6")
draai("--zet", "nachtlicht", "aan")
klopt("kwriteconfig6 --file kwinrc --group NightColor --key Active --notify true" in LOG.read_text(),
      "snel: Nachtlampje aanzetten gaat via kwriteconfig6 (zoals Instellingen > Scherm)")

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
# U529: 'uit' terwijl de kaart er nog niet is (vliegtuigstand): blokkeren, zodat BlueZ hem straks niet vanzelf aanzet.
LOG.write_text("")
nep("bluetoothctl", "")
draai("--zet", "bluetooth", "uit", env_extra={"XDG_RUNTIME_DIR": str(_run517)})
klopt("rfkill block bluetooth" in logboek(), f"U529: bluetooth uit zonder kaart: blokkeren ({logboek().splitlines()})")
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

# Browser kiezen in Welkom (2026-11-24): de gekozen browser staat in het startmenu op de plek van Firefox.
_oud_home = sd.HOME
sd.HOME = TMP / "browser-thuis"
(sd.HOME / ".config" / "bugos").mkdir(parents=True)
try:
    _zonder = sd.favoriet_ids()
    (sd.HOME / ".config" / "bugos" / "browser").write_text("com.google.Chrome\n")
    _met = sd.favoriet_ids()
    (sd.HOME / ".config" / "bugos" / "browser").write_text("rm -rf ~\n")
    _kapot = sd.favoriet_ids()
finally:
    sd.HOME = _oud_home
klopt("org.mozilla.firefox.desktop" in _zonder and _met[0] == "com.google.Chrome.desktop"
      and "org.mozilla.firefox.desktop" not in _met and _kapot == _zonder,
      f"Browser: Chrome gekozen staat in het startmenu op de plek van Firefox ({_met[:2]})")
# A-07 (VM-test): op Kinoite is /home een koppeling naar /var/home. HOME zegt '/home/test', recently-used.xbel
# '/var/home/test/Documenten/...'. Het startmenu moet dan gewoon 'Documenten' tonen, niet het technische pad.
_echt = TMP / "a07" / "var" / "home" / "test"
(_echt / "Documenten" / "Werk").mkdir(parents=True)
(TMP / "a07" / "home").symlink_to(_echt.parent)   # zoals Kinoite: /home -> var/home
_oud_home = sd.HOME
sd.HOME = TMP / "a07" / "home" / "test"
try:
    _namen = {
        "via /var/home": sd.map_naam(_echt / "Documenten"),
        "via /home": sd.map_naam(sd.HOME / "Documenten"),
        "dieper": sd.map_naam(_echt / "Documenten" / "Werk"),
        "thuismap": sd.map_naam(_echt),
        "buiten": sd.map_naam(Path("/tmp")),
        "lijkt erop": sd.map_naam(_echt.parent / "testen"),   # '/var/home/testen' is niet de thuismap van 'test'
    }
finally:
    sd.HOME = _oud_home
klopt(_namen["via /var/home"] == "Documenten" and _namen["via /home"] == "Documenten"
      and _namen["dieper"] == "Documenten/Werk" and _namen["thuismap"] in ("Thuismap", "Home folder")
      and _namen["buiten"] == "/tmp" and _namen["lijkt erop"].endswith("/testen"),
      f"A-07: recente bestanden tonen 'Documenten', ook als het pad via /var/home loopt ({_namen})")

# A-11 (VM-test): 'Game mode' (twee woorden), 'gamemode' en 'gamen' vinden ook 'Game-modus aan/uit', niet alleen
# de pagina van Instellingen. Het startmenu zoekt elk woord los in 'zoek', dus elk woord moet erin staan.
_spel = sd.lees_desktop(ROOT / "system_files/usr/share/applications/bugos-game-mode.desktop")
_mist = [z for z in ("game mode", "gamemode", "gamen", "game-modus", "spelmodus")
         if not _spel or not all(w in _spel["zoek"] for w in sd.zoeksleutel(z).split())]
klopt(not _mist, f"A-11: zoeken op 'game mode', 'gamemode' en 'gamen' vindt 'Game-modus aan/uit' (mist: {_mist})")
# A-14: 'Teksteditor' in het startmenu is de eenvoudige KWrite; Kate (voor programmeurs) houdt zijn eigen naam.
# Is KWrite er niet, dan blijft Kate de Teksteditor (anders is er geen). sd.TAAL bepaalt de taal van t().
_a14 = TMP / "a14" / "applications"
_a14.mkdir(parents=True)
(_a14 / "org.kde.kate.desktop").write_text("[Desktop Entry]\nType=Application\nName=Kate\nExec=kate %U\n")
_kate_alleen = sd.lees_desktop(_a14 / "org.kde.kate.desktop") or {}
klopt(_kate_alleen.get("naam") in ("Teksteditor", "Text editor"),
      f"A-14: zonder KWrite blijft Kate de Teksteditor ({_kate_alleen.get('naam')!r})")
(_a14 / "org.kde.kwrite.desktop").write_text("[Desktop Entry]\nType=Application\nName=KWrite\nExec=kwrite %U\n")
_kwrite = sd.lees_desktop(_a14 / "org.kde.kwrite.desktop") or {}
_kate = sd.lees_desktop(_a14 / "org.kde.kate.desktop") or {}
klopt(_kwrite.get("naam") in ("Teksteditor", "Text editor") and _kate.get("naam", "").startswith("Kate (")
      and "kwrite" in _kwrite.get("zoek", "") and "kate" in _kate.get("zoek", ""),
      f"A-14: met KWrite is die de Teksteditor en heet Kate gewoon Kate ({_kwrite.get('naam')!r}, {_kate.get('naam')!r})")
_mime = (ROOT / "system_files/etc/xdg/kde-mimeapps.list").read_text(encoding="utf-8")
_pakk = (ROOT / "build_files/packages.txt").read_text(encoding="utf-8").split("\n")
_stijl = (ROOT / "build_files/style.sh").read_text(encoding="utf-8")
klopt("text/plain=org.kde.kwrite.desktop" in _mime and "kwrite" in _pakk
      and 'hernoem org.kde.kwrite.desktop "Teksteditor"' in _stijl and "org.kde.kwrite.desktop org.kde.khelpcenter" not in _stijl,
      "A-14: KWrite zit in het beeld, opent .txt-bestanden, heet Teksteditor en is niet meer verborgen")

# 6. Het menu van de rechtermuisknop op een app (StartMenu.qml, appMenu).
def wacht_op(tekst: str) -> bool:
    """Wacht tot een los gestart programma in het logboek staat (los_starten wacht er niet op)."""
    for _ in range(50):
        if tekst in logboek():
            return True
        time.sleep(0.1)
    return False


# Firefox als Flatpak, zoals Flatpak hem klaarzet: in de exports-map in je thuismap (een Flatpak voor alleen jou),
# met X-Flatpak, twee eigen acties en de Exec-regel van flatpak (met @@u %u @@). De Exec van de acties gebruikt
# hier een nep-flatpak (op PATH), zodat we zien wat er echt gestart wordt.
_fp = TMP / "thuis" / ".local" / "share" / "flatpak" / "exports" / "share" / "applications"
_fp.mkdir(parents=True)
(_fp / "org.mozilla.firefox.desktop").write_text(
    "[Desktop Entry]\nType=Application\nName=Firefox\nCategories=Network;\nIcon=org.mozilla.firefox\n"
    "Exec=flatpak run --branch=stable --arch=x86_64 --command=firefox --file-forwarding org.mozilla.firefox @@u %u @@\n"
    "Actions=new-window;new-private-window;kapot;zonder-exec;\nX-Flatpak=org.mozilla.firefox\n\n"
    "[Desktop Action new-window]\nName=Open a New Window\nName[nl]=Nieuw venster\n"
    "Exec=flatpak run --branch=stable --arch=x86_64 --command=firefox --file-forwarding org.mozilla.firefox --new-window @@u %u @@\n\n"
    "[Desktop Action new-private-window]\nName=Open a New Private Window\nName[nl]=Nieuw privévenster\n"
    "Exec=flatpak run --branch=stable --arch=x86_64 --command=firefox --file-forwarding org.mozilla.firefox --private-window @@u %u @@\n\n"
    "[Desktop Action zonder-exec]\nName=Zonder Exec\n\n"
    "[Desktop Action niet-genoemd]\nName=Staat niet in Actions\nExec=flatpak run iets\n",
    encoding="utf-8")
nep("flatpak")
_d6 = json.loads(draai())
_ff6 = next((a for a in _d6["apps"] if a["id"] == "org.mozilla.firefox.desktop"), {})
klopt([a["naam"] for a in _ff6.get("acties", [])] == ["Nieuw venster", "Nieuw privévenster"],
      f"app-menu: Firefox uit de Flatpak-map met zijn eigen acties in het Nederlands, zonder kapotte ({_ff6.get('acties')})")
klopt(_ff6.get("verwijder") == "org.mozilla.firefox", f"app-menu: een Flatpak kun je verwijderen ({_ff6.get('verwijder')!r})")
_st6 = next((a for a in _d6["apps"] if a["id"] == "steam.desktop"), {})
klopt(_st6.get("acties") == [] and _st6.get("verwijder") == "",
      f"app-menu: een gewone app zonder acties: geen acties en niet te verwijderen ({_st6.get('acties')}, {_st6.get('verwijder')!r})")
_en6 = json.loads(draai(env_extra={"LC_ALL": "en_US.UTF-8", "LANGUAGE": ""}))
_ffen = next((a for a in _en6["apps"] if a["id"] == "org.mozilla.firefox.desktop"), {})
klopt([a["naam"] for a in _ffen.get("acties", [])] == ["Open a New Window", "Open a New Private Window"],
      f"app-menu: in het Engels de gewone namen (Name) ({_ffen.get('acties')})")

# De opdracht van een actie: veldcodes weg (%u), @@u @@ van flatpak blijft (zo verwacht flatpak het zonder bestand).
klopt(sd.exec_argumenten("flatpak run --command=firefox --file-forwarding org.mozilla.firefox --private-window @@u %u @@")
      == ["flatpak", "run", "--command=firefox", "--file-forwarding", "org.mozilla.firefox", "--private-window", "@@u", "@@"],
      "app-menu: Exec van een Flatpak-actie: %u weg, de rest precies zoals het er staat")
_ex = sd.exec_argumenten('prog %F --naam=%c %c %i "met spatie" --bestand=%f 100%% %k "a\\sb" c\\sd', "Mijn App", "mijn-icoon", "/pad/x.desktop")
# \s is een spatie: tussen aanhalingstekens hoort hij bij het argument ("a b"), zonder splitst hij (c en d).
klopt(_ex == ["prog", "--naam=", "Mijn App", "--icon", "mijn-icoon", "met spatie", "--bestand=", "100%", "/pad/x.desktop",
              "a b", "c", "d"],
      f"app-menu: veldcodes zoals de specificatie: %F/%f weg, %c naam, %i --icon, %% wordt %, %k het pad, \\s spatie ({_ex})")
klopt(sd.exec_argumenten('prog "kapot') == [] and sd.exec_argumenten("prog; rm -rf ~") == ["prog;", "rm", "-rf", "~"],
      "app-menu: een kapotte Exec start niets, en een ; is gewoon tekst (er komt geen shell aan te pas)")
klopt(sd.actie_opdracht(_fp / "org.mozilla.firefox.desktop", "niet-genoemd") == []
      and sd.actie_opdracht(_fp / "org.mozilla.firefox.desktop", "bestaat-niet") == []
      and sd.actie_opdracht(TMP / "geen.desktop", "new-window") == [],
      "app-menu: alleen acties die in Actions= staan kunnen starten (en geen bestand: niets)")
LOG.write_text("")
draai("--actie", str(_fp / "org.mozilla.firefox.desktop"), "new-private-window")
klopt(wacht_op("flatpak run --branch=stable --arch=x86_64 --command=firefox --file-forwarding org.mozilla.firefox --private-window @@u @@"),
      f"app-menu: 'Nieuw privévenster' start flatpak met --private-window ({logboek().splitlines()})")
LOG.write_text("")
draai("--actie", str(_fp / "org.mozilla.firefox.desktop"), "zonder-exec")
time.sleep(0.3)
klopt("flatpak" not in logboek(), "app-menu: een actie zonder Exec start niets")

# Vastmaken aan Start en losmaken. Nu is er ook de Flatpak van Firefox: die telt voor 'org.mozilla.firefox.desktop'.
_favb = TMP / "thuis" / ".config" / "bugos" / "favorieten.json"
_v = json.loads(draai("--vastzetten", "tr.desktop"))
_ids = [a["id"] for a in _v["favorieten"]]
klopt(_ids[-1:] == ["tr.desktop"] and json.loads(_favb.read_text())[-1] == "tr.desktop"
      and next(a for a in _v["apps"] if a["id"] == "tr.desktop")["vastgezet"] is True,
      f"vastmaken aan Start: achteraan, in favorieten.json, en de app weet dat hij vastgezet is ({_ids})")
klopt("org.mozilla.firefox.desktop" in json.loads(_favb.read_text()) and "bugos-store.desktop" in json.loads(_favb.read_text()),
      "vastmaken aan Start: de standaardlijst blijft erin staan (ook apps die er nu niet zijn)")
_v = json.loads(draai("--vastzetten", "tr.desktop"))
klopt([a["id"] for a in _v["favorieten"]].count("tr.desktop") == 1, "vastmaken aan Start: twee keer vastmaken geeft geen dubbele tegel")
_v = json.loads(draai("--losmaken", "firefox.desktop"))
_ids = [a["id"] for a in _v["favorieten"]]
_opgeslagen = json.loads(_favb.read_text())
klopt("org.mozilla.firefox.desktop" not in _opgeslagen and "firefox.desktop" not in _ids and "org.mozilla.firefox.desktop" not in _ids
      and all(not a.get("vastgezet") for a in _v["apps"] if "firefox" in a["id"]),
      f"losmaken van Start: onder elke naam weg (rpm en Flatpak) ({_ids})")
_voor = _favb.read_text()
draai("--vastzetten", "../../etc/passwd")
draai("--losmaken", "tr desktop")
klopt(_favb.read_text() == _voor, "vastmaken aan Start: een vreemde naam (met / of een spatie) verandert niets")
_v = json.loads(draai("--losmaken", "tr.desktop"))
klopt("tr.desktop" not in [a["id"] for a in _v["favorieten"]], "losmaken van Start: de tegel is weg")

# Vastmaken aan de taakbalk: de lijst van KDE's takenlijst uit het bestand van Plasma; veranderen via bugos-panel.
_cfg = TMP / "cfg"
_cfg.mkdir()
_rc = _cfg / "plasma-org.kde.plasma.desktop-appletsrc"
_rc.write_text("[Containments][2]\nplugin=org.kde.panel\n\n[Containments][2][Applets][5]\nplugin=org.kde.plasma.icontasks\n\n"
               "[Containments][2][Applets][5][Configuration][General]\n"
               "launchers=applications:bugos-files.desktop,file:///usr/share/applications/steam.desktop,preferred://browser\n"
               "[Containments][2][Applets][6]\nplugin=org.bugos.taskbar\n")
_tb = {"XDG_CONFIG_HOME": str(_cfg), "XDG_CACHE_HOME": str(TMP / "cache")}
_g = json.loads(draai(env_extra=_tb))
klopt(_g.get("taakbalk_kan") is False, "taakbalk: zonder bugos-panel geen 'Vastmaken aan taakbalk'")
nep("bugos-panel", "ok:bugos-files.desktop,steam.desktop,tr.desktop")
_g = json.loads(draai(env_extra=_tb))
_op = {a["id"]: a.get("op_taakbalk") for a in _g["apps"] if a["soort"] == "app"}
klopt(_g.get("taakbalk_kan") is True and _op.get("bugos-files.desktop") is True and _op.get("steam.desktop") is True
      and _op.get("tr.desktop") is False,
      f"taakbalk: leest de vastgezette apps van de takenlijst (ook als file://) ({_op})")
LOG.write_text("")
_g = json.loads(draai("--taakbalk", "vastmaken", "tr.desktop", env_extra=_tb))
klopt("bugos-panel taakbalk vastmaken tr.desktop" in logboek()
      and next(a for a in _g["apps"] if a["id"] == "tr.desktop")["op_taakbalk"] is True,
      "taakbalk: vastmaken gaat via bugos-panel, en het menu ziet het meteen (ook voor Plasma zijn bestand bijwerkt)")
_g = json.loads(draai(env_extra=_tb))
klopt(next(a for a in _g["apps"] if a["id"] == "tr.desktop")["op_taakbalk"] is True,
      "taakbalk: ook bij de volgende keer openen (Plasma schrijft zijn bestand pas later)")
os.utime(_rc, (time.time() + 5, time.time() + 5))   # nu heeft Plasma zijn bestand bijgewerkt (zonder tr.desktop)
_g = json.loads(draai(env_extra=_tb))
klopt(next(a for a in _g["apps"] if a["id"] == "tr.desktop")["op_taakbalk"] is False,
      "taakbalk: is het bestand van Plasma nieuwer, dan telt dat weer")
LOG.write_text("")
draai("--taakbalk", "losmaken", "org.mozilla.firefox.desktop", env_extra=_tb)
klopt("bugos-panel taakbalk losmaken org.mozilla.firefox.desktop" in logboek()
      and "bugos-panel taakbalk losmaken firefox.desktop" in logboek(),
      "taakbalk: losmaken onder elke naam van de app (rpm en Flatpak)")
LOG.write_text("")
draai("--taakbalk", "vastmaken", "x';y.desktop", env_extra=_tb)
klopt("bugos-panel" not in logboek(), "taakbalk: een vreemde naam gaat niet naar bugos-panel")
_rc.write_text("[Containments][2]\nplugin=org.kde.panel\n")
klopt(json.loads(draai(env_extra=_tb)).get("taakbalk_kan") is False,
      "taakbalk: geen takenlijst op de taakbalk: geen 'Vastmaken aan taakbalk'")

# Verwijderen: opent de Winkel op die app (met zijn eigen 'Weet je het zeker?'), verwijdert zelf niets.
LOG.write_text("")
nep("bugos-store")
draai("--verwijder", "org.mozilla.firefox")
klopt(wacht_op("bugos-store appstream://org.mozilla.firefox") and "flatpak" not in logboek(),
      "verwijderen: opent de Winkel op die app (en roept zelf geen flatpak uninstall aan)")
LOG.write_text("")
draai("--verwijder", "org.mozilla.firefox; rm -rf ~")
time.sleep(0.3)
klopt("bugos-store" not in logboek(), "verwijderen: een vreemde naam opent niets")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
