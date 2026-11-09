#!/usr/bin/env python3
"""Test van BugOS Instellingen: lezen we de uitvoer van nmcli, bluetoothctl, pactl, kscreen-doctor, busctl,
timedatectl, lpstat en de KDE-bestanden goed? En opent het venster met elke pagina (met voorbeeldgegevens,
er verandert niets aan je computer)?

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_settings.py
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
TMP = Path(tempfile.mkdtemp(prefix="bugos-settings-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  BUGOS_ACHTERGRONDEN=str(ROOT / "system_files" / "usr" / "share" / "wallpapers" / "bugos" / "contents"))

import bugos_config as bi  # noqa: E402

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
klopt(bi.lees_bt_apparaten("Device AA:BB:CC:DD:EE:01 Koptelefoon van Bugie\nDevice 11:22:33:44:55:66 Muis\n")
      == [("AA:BB:CC:DD:EE:01", "Koptelefoon van Bugie"), ("11:22:33:44:55:66", "Muis")], "bluetooth: apparaten")
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
klopt(len(bi.bugos_achtergronden()) == 3 and Path(bi.bugos_achtergronden()[0][1]).is_dir(),
      "uiterlijk: de achtergronden van BugOS (eerst het pakket dat licht/donker volgt, U131)")

# 6. voorbeeldstand: aanzetten en uitzetten werkt zonder iets aan de computer te doen
bi.zet_wifi(False)
klopt(not bi.wifi_aan() and bi.netwerken() == [], "voorbeeld: wifi uit, dan geen netwerken")
bi.zet_wifi(True)
klopt(bi.verbind("Buren", "geheim")[0] and next(n for n in bi.netwerken() if n.verbonden).naam == "Buren",
      "voorbeeld: verbinden met een ander netwerk")

# 6b. de nieuwe onderdelen: lezen wat de computer zegt
klopt(bi.lees_letter("Inter,12,-1,5,400,0,0,0,0,0,0,0,0,0,0,1") == ("Inter", 12) and bi.lees_letter("") == ("Inter", 10),
      "zien: lettergrootte uit kdeglobals lezen")
klopt(bi.letter("Inter", 12, 600).startswith("Inter,12,-1,5,600,"), "zien: lettertype opschrijven zoals KDE dat doet")
busctl = ('{"type":"as","data":["event5","event7"]}\n'
          '{"type":"a{sv}","data":[{"name":{"type":"s","data":"Logitech Muis"},"pointer":{"type":"b","data":true},'
          '"touchpad":{"type":"b","data":false},"enabled":{"type":"b","data":true},"leftHanded":{"type":"b","data":true},'
          '"naturalScroll":{"type":"b","data":false},"pointerAcceleration":{"type":"d","data":0.5},'
          '"supportsLeftHanded":{"type":"b","data":true},"supportsPointerAcceleration":{"type":"b","data":true},'
          '"supportsNaturalScroll":{"type":"b","data":true},"supportsTapToClick":{"type":"b","data":false}}]}\n')
waarden = bi.lees_busctl(busctl)
klopt(waarden[0] == ["event5", "event7"], "muis: de lijst met apparaten uit busctl")
muis = bi.lees_aanwijzer("event5", waarden[1][0])
klopt(muis is not None and muis.naam == "Logitech Muis" and muis.linkshandig and muis.snelheid == 75
      and muis.kan == {"linkshandig", "natuurlijk", "snelheid"}, "muis: naam, linkshandig, snelheid 75%, wat hij kan")
klopt(bi.lees_aanwijzer("event1", {"pointer": {"type": "b", "data": False}, "keyboard": {"type": "b", "data": True}})
      is None, "muis: een toetsenbord is geen muis")
# Met de echte namen van KWin: tikken kan als tapFingerCount > 0 (er bestaat geen supportsTapToClick) (U153).
pad = bi.lees_aanwijzer("event7", {"name": "Touchpad", "pointer": True, "touchpad": True, "tapToClick": True,
                                   "tapFingerCount": {"type": "i", "data": 3}, "supportsDisableEvents": True,
                                   "enabled": False})
klopt(pad is not None and pad.touchpad and pad.tikken and not pad.aan and pad.kan == {"tikken", "aan"},
      "muis: ook als busctl de waarden zonder 'type' en 'data' geeft")
tijd = bi.lees_timedatectl("Timezone=Europe/Amsterdam\nLocalRTC=no\nCanNTP=yes\nNTP=yes\nNTPSynchronized=yes\n")
klopt(tijd.zone == "Europe/Amsterdam" and tijd.auto and tijd.gelijk, "tijd: tijdzone en 'vanzelf gelijkzetten'")
klopt(bi.mooie_zone("Europe/Amsterdam") == "Amsterdam (Europa)"
      and bi.mooie_zone("America/New_York") == "New York (Amerika)"
      and bi.mooie_zone("America/Argentina/Buenos_Aires") == "Argentina / Buenos Aires (Amerika)"
      and bi.mooie_zone("UTC") == "UTC", "tijd: tijdzones in gewone woorden")
klopt(bi.lees_autologin(["[General]\nx=1\n", "[Autologin]\nUser=bugie\nSession=plasma\n"], "bugie")
      and not bi.lees_autologin(["[Autologin]\nUser=sanne\n"], "bugie"), "inloggen: 'zonder wachtwoord' uit sddm lezen")
hash_ = bi.versleutel("geheim123")
klopt(hash_.startswith("$6$") and len(hash_) > 90, "inloggen: wachtwoord versleutelen zoals /etc/shadow")
# De hash mag nooit op een opdrachtregel staan (dan leest elke gebruiker hem in 'ps').
_oud = (bi.VOORBEELD, bi.draai, bi._accounts_dbus)
_opdrachten: list = []
_dbus: list = []
bi.VOORBEELD = False
bi.draai = lambda *cmd, **kw: (_opdrachten.append(cmd), (0, ""))[1]
bi._accounts_dbus = lambda methode, *args, **kw: (_dbus.append((methode, args)), (True, ""))[1]
_goed, _ = bi.zet_wachtwoord("geheim123")
bi.VOORBEELD, bi.draai, bi._accounts_dbus = _oud
klopt(_goed and not _opdrachten and _dbus and _dbus[0][0] == "SetPassword" and _dbus[0][1][0].startswith("$6$"),
      "inloggen: nieuw wachtwoord via D-Bus in het programma, niet via een opdracht")
# B001: Fedora 44 heeft geen powerprofilesctl (tuned-ppd); dan via busctl.
klopt(bi.lees_busctl_tekst('s "performance"\n') == "performance" and bi.lees_busctl_tekst("onzin") == "",
      "energie: het antwoord van busctl lezen")
_oud = (bi.VOORBEELD, bi.draai, bi.shutil.which)
_opdrachten = []
bi.VOORBEELD = False
bi.shutil.which = lambda naam: None if naam == "powerprofilesctl" else "/usr/bin/" + naam
bi.draai = lambda *cmd, **kw: (_opdrachten.append(cmd), (0, 's "balanced"'))[1]
_profiel = bi.energieprofiel()
_gezet = bi.zet_energieprofiel("performance")
bi.VOORBEELD, bi.draai, bi.shutil.which = _oud
klopt(_profiel == "balanced" and _gezet and _opdrachten[-1][:3] == ("busctl", "--system", "set-property")
      and _opdrachten[-1][-2:] == ("s", "performance"),
      "energie: zonder powerprofilesctl lezen en zetten via D-Bus (busctl)")
klopt(bi.lees_tot("2999,12,31,0,0,0") and not bi.lees_tot("2001,1,1,0,0,0") and not bi.lees_tot("")
      and bi.lees_tot("2999-01-01T00:00:00") and not bi.lees_tot("onzin"),
      "meldingen: 'niet storen tot' lezen (lijstje van KDE of ISO-tijd)")
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402
_straks, _net = _dt.now() + _td(hours=2), _dt.now() - _td(minutes=10)
_kde = lambda d, sec="7.913": f"{d.year},{d.month},{d.day},{d.hour},{d.minute},{sec}"  # noqa: E731
_utc = _dt.now(_tz.utc) + _td(hours=2)
klopt(bi.lees_tot(_kde(_straks)) and not bi.lees_tot(_kde(_net)) and bi.lees_tot(_kde(_utc, "12.345") + ",UTC")
      and not bi.lees_tot(_kde(_dt.now(_tz.utc) - _td(hours=2)) + ",UTC"),
      "U072: 'niet storen tot' zoals KDE het echt schrijft (seconden met komma-deel, tijdzone erachter)")
cache = "[MIME Cache]\napplication/pdf=org.kde.okular.desktop;firefox.desktop;\nimage/png=org.kde.gwenview.desktop;\n"
klopt(bi.lees_mimeinfo(cache)["application/pdf"] == ["org.kde.okular.desktop", "firefox.desktop"],
      "programma's: mimeinfo.cache lezen")
klopt(bi.lees_desktop_naam("[Desktop Entry]\nName=Okular\nName[nl]=Okular (documenten)\n[Desktop Action x]\nName=Anders\n")
      == "Okular (documenten)" and bi.lees_desktop_naam("[Desktop Entry]\nName=Geheim\nNoDisplay=true\n") is None,
      "programma's: naam uit een .desktop-bestand; verborgen programma's niet")
lp = ("printer HP_LaserJet is idle.  enabled since Mon 03 Nov 2026\n\tDescription: HP LaserJet van Bugie\n\tLocation: kamer\n"
      "printer Canon_PIXMA disabled since Sun 02 Nov 2026 -\n\tPaused\n\tDescription: Canon PIXMA\n"
      "printer Brother now printing Brother-12.  enabled since Mon\n")
prs = bi.lees_lpstat(lp, "system default destination: HP_LaserJet\n")
klopt([(p.omschrijving, p.staat, p.standaard) for p in prs]
      == [("HP LaserJet van Bugie", "klaar", True), ("Canon PIXMA", "gestopt", False), ("Brother", "bezig", False)],
      "printers: naam, of hij klaar is, en welke de standaard is")
klopt(bi.lees_lpstat("", "no system default destination\n") == [], "printers: geen printers")
bi.zet_grote_tekst(True)
klopt(bi.grote_tekst(), "voorbeeld: grote letters aan")
bi.zet_aanwijzer("event7", "tikken", False)
klopt(not next(a for a in bi.aanwijzers() if a.touchpad).tikken, "voorbeeld: tikken om te klikken uit")
bi.zet_slot_na(0)
klopt(bi.slot_na() == 0, "voorbeeld: scherm nooit op slot")
bi.zet_standaard_app("pdf", "firefox.desktop")
klopt(bi.standaard_app("pdf") == "firefox.desktop", "voorbeeld: een ander programma voor PDF")
bi.zet_standaard_printer("Canon_PIXMA")
klopt([p.standaard for p in bi.printers()] == [False, True], "voorbeeld: een andere standaardprinter")

# 7. het venster, met elke pagina
lader = importlib.machinery.SourceFileLoader("instellingen", str(ROOT / "system_files" / "usr" / "bin" /
                                                                 "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
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
muis_p = venster.paginas["muis"]
klopt(len(muis_p.vak.findChildren(mod.Groep)) == 2 and len(muis_p.vak.findChildren(mod.Regelaar)) == 2,
      "muis-pagina: een kaart voor de muis en een voor het touchpad, elk met een snelheidsschuif")
klopt(venster.paginas["inloggen"].ik.titel.text() == "Bugie" and "bugie" in venster.paginas["inloggen"].ik.uitleg.text(),
      "inloggen-pagina: naam en inlognaam")
klopt(venster.paginas["programmas"].rijen["pdf"].uitleg.text() == "Firefox", "programma's-pagina: PDF opent nu met Firefox")
printers_p = venster.paginas["printers"]
klopt(len(printers_p.lijst.findChildren(mod.Rij)) == 2 and "wacht" in printers_p.wacht_rij.titel.text(),
      "printers-pagina: twee printers en de wachtrij")
klopt(venster.paginas["tijd"].zone_rij.uitleg.text() == "Amsterdam (Europa)", "tijd-pagina: de tijdzone in gewone woorden")
energie_p = venster.paginas["energie"]
klopt(energie_p.scherm_uit.knoppen[600].isChecked() and energie_p.slaap.knoppen[1800].isChecked()
      and energie_p.deksel_rij.isVisibleTo(energie_p), "energie-pagina: scherm uit na 10 min, slapen na 30 min, dichtklappen")
d = mod.KiesDialoog(venster, "Test", [(z, bi.mooie_zone(z)) for z in bi.tijdzones()], "Europe/Amsterdam", "zoek")
d.filter("tok")
zichtbaar = [d.lijst.item(i).text() for i in range(d.lijst.count()) if not d.lijst.item(i).isHidden()]
klopt(zichtbaar == ["Tokyo (Azië)"], "kiezen: zoeken in de lijst met tijdzones")
d.accept()
klopt(d.gekozen == "Asia/Tokyo", "kiezen: Enter kiest wat je gevonden hebt")
w = mod.WachtwoordDialoog(venster)
w.een.setText("geheim1")
w.twee.setText("geheim2")
klopt(not w.ok.isEnabled() and w.fout.text(), "wachtwoord: niet hetzelfde, dan kan het niet")
w.twee.setText("geheim1")
klopt(w.ok.isEnabled() and w.wachtwoord == "geheim1", "wachtwoord: twee keer hetzelfde, dan kan het")
venster.zoekveld.setText("wachtwoord")
app.processEvents()
gevonden = [r.titel.text() for r in venster.paginas["start"].zoek_kaart.findChildren(mod.Rij)]
klopt("Inloggen en wachtwoord" in gevonden and "Wifi en internet" in gevonden, "zoeken: 'wachtwoord' vindt Inloggen en Wifi")
QThreadPool.globalInstance().waitForDone(5000)
venster.close()

shutil.rmtree(TMP, ignore_errors=True)
# U229: Engels kiezen in Europa geeft geen Amerikaanse datum en Letter-papier.
import bugos_config_account as _ca  # noqa: E402

_lees, _schrijf, _vb = _ca._c.kde_lees, _ca._c.kde_schrijf, _ca._c.VOORBEELD
_geschreven = {}
_ca._c.VOORBEELD = False
_ca._c.kde_schrijf = lambda bestand, groep, sleutel, waarde: _geschreven.__setitem__(sleutel, waarde) or True
_uit = {}
for _nu, _verwacht in (("nl_NL.UTF-8", "en_IE.UTF-8"), ("en_GB.UTF-8", "en_GB.UTF-8"), ("", "en_US.UTF-8")):
    _ca._c.kde_lees = lambda bestand, groep, sleutel, standaard="", _w=_nu: _w if sleutel == "LANG" else standaard
    _oud_env = os.environ.pop("LANG", None)
    _ca.zet_taal("en")
    if _oud_env is not None:
        os.environ["LANG"] = _oud_env
    _uit[_nu] = _geschreven.get("LANG") == _verwacht
_ca.zet_taal("nl")
_nl = _geschreven.get("LANG")
_ca._c.kde_lees, _ca._c.kde_schrijf, _ca._c.VOORBEELD = _lees, _schrijf, _vb
klopt(all(_uit.values()) and _nl == "nl_NL.UTF-8",
      f"U229: Engels in Europa geeft dag/maand en A4 (en_IE); een Engelse streek blijft; Nederlands blijft nl_NL ({_uit}, {_nl})")

print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
