#!/usr/bin/env python3
"""Test van BugOS Instellingen: lezen we de uitvoer van nmcli, bluetoothctl, pactl en kscreen-doctor goed?
En opent het venster met elke pagina (met voorbeeldgegevens, er verandert niets aan je computer)?

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_instellingen.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))
TMP = Path(tempfile.mkdtemp(prefix="bugos-instellingen-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  BUGOS_ACHTERGRONDEN=str(ROOT / "system_files" / "usr" / "share" / "wallpapers" / "bugos" / "contents"))

import bugos_instellen as bi  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


# 1. wifi (nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list)
uit = ("*:Thuis:86:WPA2\n"
       " :Buren:41:WPA1 WPA2\n"
       " :Bibliotheek gratis:35:\n"
       " :Naam\\:met dubbele punt:50:WPA2\n"
       " :Thuis:40:WPA2\n"
       " ::60:WPA2\n")
netten = bi.lees_netwerken(uit)
klopt([n.naam for n in netten] == ["Thuis", "Naam:met dubbele punt", "Buren", "Bibliotheek gratis"],
      "wifi: verbonden netwerk eerst, dan op sterkte; verborgen netwerk (zonder naam) niet")
klopt(netten[0].verbonden and netten[0].sterkte == 86, "wifi: een naam die twee keer voorkomt telt één keer")
klopt(not next(n for n in netten if n.naam == "Bibliotheek gratis").beveiligd, "wifi: open netwerk zonder wachtwoord")
klopt(bi.splits_nmcli("a\\\\b:c") == ["a\\b", "c"], "wifi: een \\ in een naam gaat goed")

# 2. bluetooth
klopt(bi.lees_bt_aan("Controller 00:11 BugOS [default]\n\tPowered: yes\n\tDiscoverable: no\n"), "bluetooth: aan")
klopt(not bi.lees_bt_aan("Controller 00:11 BugOS\n\tPowered: no\n"), "bluetooth: uit")
klopt(bi.lees_bt_apparaten("Device AA:BB:CC:DD:EE:01 Koptelefoon van oma\nDevice 11:22:33:44:55:66 Muis\n")
      == [("AA:BB:CC:DD:EE:01", "Koptelefoon van oma"), ("11:22:33:44:55:66", "Muis")], "bluetooth: apparaten")
info = bi.lees_bt_info("AA:BB:CC:DD:EE:01", "Koptelefoon", "\tName: Koptelefoon\n\tIcon: audio-headset\n"
                       "\tConnected: yes\n\tBattery Percentage: 0x50 (80)\n")
klopt(info.verbonden and info.soort == "audio-headset" and info.batterij == 80, "bluetooth: verbonden, soort, batterij")

# 3. geluid (pactl -f json list sinks)
sinks = json.dumps([
    {"index": 1, "name": "alsa_output.pci.analog-stereo", "description": "Ingebouwde luidsprekers", "mute": False,
     "volume": {"front-left": {"value_percent": "45%"}, "front-right": {"value_percent": "47%"}}},
    {"index": 2, "name": "alsa_output.hdmi", "description": "Televisie (HDMI)", "mute": True,
     "volume": {"front-left": {"value_percent": "100%"}}}])
klopt(bi.lees_volume(sinks, "alsa_output.pci.analog-stereo") == (46, False), "geluid: volume (gemiddeld) en niet stil")
klopt(bi.lees_volume(sinks, "alsa_output.hdmi") == (100, True), "geluid: tv staat stil")
uitgangen = bi.lees_uitgangen(sinks, "alsa_output.hdmi")
klopt([u.omschrijving for u in uitgangen] == ["Ingebouwde luidsprekers", "Televisie (HDMI)"] and uitgangen[1].standaard,
      "geluid: uitgangen met gewone namen, en welke in gebruik is")
klopt(bi.lees_volume("geen json", "x") == (0, False) and bi.lees_uitgangen("", "x") == [],
      "geluid: rare uitvoer geeft geen fout")

# 4. scherm (kscreen-doctor -j)
schermen = json.dumps({"outputs": [{"name": "eDP-1", "enabled": True, "connected": True, "scale": 1.25},
                                   {"name": "HDMI-A-1", "enabled": False, "connected": True, "scale": 1}]})
klopt(bi.lees_schalen(schermen) == [("eDP-1", 1.25)], "scherm: alleen schermen die aan staan, met hun grootte")
(TMP / "sys" / "class" / "backlight" / "intel_backlight").mkdir(parents=True)
(TMP / "sys" / "class" / "backlight" / "intel_backlight" / "max_brightness").write_text("1000\n")
klopt(bi.backlight() is not None and bi.backlight().name == "intel_backlight", "scherm: schermverlichting gevonden")

# 5. energie
(TMP / "sys" / "class" / "power_supply" / "BAT0").mkdir(parents=True)
(TMP / "sys" / "class" / "power_supply" / "BAT0" / "capacity").write_text("64\n")
(TMP / "sys" / "class" / "power_supply" / "BAT0" / "status").write_text("Charging\n")
os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD")
bi.VOORBEELD = False
bat = bi.batterij()
klopt(bat is not None and bat.procent == 64 and bat.laadt, "energie: batterij 64%, wordt opgeladen")
bi.VOORBEELD = True
klopt(len(bi.bugos_achtergronden()) == 2, "uiterlijk: de twee achtergronden van BugOS")

# 6. voorbeeldstand: aanzetten en uitzetten werkt zonder iets aan de computer te doen
bi.zet_wifi(False)
klopt(not bi.wifi_aan() and bi.netwerken() == [], "voorbeeld: wifi uit, dan geen netwerken")
bi.zet_wifi(True)
klopt(bi.verbind("Buren", "geheim")[0] and next(n for n in bi.netwerken() if n.verbonden).naam == "Buren",
      "voorbeeld: verbinden met een ander netwerk")

# 7. het venster, met elke pagina
lader = importlib.machinery.SourceFileLoader("instellingen", str(ROOT / "system_files" / "usr" / "bin" /
                                                                 "bugos-instellingen"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402

app = mod.maak_app("bugos-instellingen", "bugos-instellingen", ["test"])
venster = mod.Instellingen("start")
for klasse in mod.PAGINAS:
    venster.ga_naar(klasse.sleutel)
    QThreadPool.globalInstance().waitForDone(5000)
    app.processEvents()
    klopt(venster.stapel.currentWidget() is venster.paginas[klasse.sleutel], f"venster: pagina '{klasse.naam()}' opent")
wifi = venster.paginas["wifi"]
klopt(wifi.hoofd.uitleg.text() == "Verbonden met Buren" and wifi.lijst.lay.count() > 3,
      "wifi-pagina: verbonden netwerk en de lijst met netwerken")
venster.zoekveld.setText("koptelefoon")
app.processEvents()
gevonden = [r.titel.text() for r in venster.paginas["start"].zoek_kaart.findChildren(mod.Rij)]
klopt(venster.stapel.currentWidget() is venster.paginas["start"] and "Bluetooth" in gevonden and "Geluid" in gevonden,
      "zoeken: 'koptelefoon' vindt Bluetooth en Geluid")
klopt(mod.Instellingen("schakelaars").stapel.currentWidget().sleutel == "updates", "oude naam 'schakelaars' werkt nog")
klopt(mod.begin_pagina(["-qwindowgeometry", "1180x740+0+0", "wifi"]) == "wifi" and mod.begin_pagina([]) == "start",
      "startpagina: het woord 'wifi' wordt gevonden, ook na Qt-opties")
QThreadPool.globalInstance().waitForDone(5000)
venster.close()

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
