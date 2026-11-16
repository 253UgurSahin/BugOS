#!/usr/bin/env python3
"""Test van 'Haal alles van je oude pc' (bugos-switch, BugOS Switch versie 2).

Wat we testen, allemaal met nep-programma's (nmcli, lpadmin, kwriteconfig6, timedatectl, busctl, kscreen-doctor,
firefox ...) en een nep-thuismap in een tijdelijke map; aan je eigen computer verandert niets:
  - de tabellen: Windows-tijdzone -> IANA, Windows-toetsenbord (KLID) -> xkb, Windows-programma -> Winkel-app;
  - instellingen overzetten met dezelfde functies als Instellingen (taal, notatie, tijdzone, toetsenbord, donker,
    muis, en de grootte alleen als die op het scherm past);
  - wifi alleen op naam (nooit een wachtwoord), een bestaand netwerk nooit overschrijven, school/werk: zelf inloggen;
  - printers op adres (IPP Everywhere); wat mislukt, staat in de lijst en houdt de rest niet tegen;
  - bladwijzers vanzelf in Firefox (en wat er al in Firefox stond, blijft), een eigen LZ4-lezer voor .jsonlz4;
  - het Firefox-profiel van Windows overnemen, zonder wachtwoorden en cookies, het oude blijft als reserve;
  - het venster: overzicht met schuifjes (alles aan), Overzetten, samenvatting; een stick van versie 1 werkt nog;
  - Welkom: de tegel heet 'Haal alles van je oude pc' en noemt de stick als die erin zit.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_switch_config.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-switch-test-"))
THUIS = TMP / "thuis"
(THUIS / ".config").mkdir(parents=True)
os.environ.update(HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), XDG_DATA_HOME=str(THUIS / ".local/share"),
                  LC_ALL="nl_NL.UTF-8", LANG="en_US.UTF-8", BUGOS_LSBLK="")
os.environ.pop("LANGUAGE", None)
os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD", None)
os.environ.pop("XDG_RUNTIME_DIR", None)   # geen systemd-run voor 'start': het nep-programma direct

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


# ======================================================================= nep-programma's ===
NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "opdrachten.log"
LOG.write_text("")
SCHERM = TMP / "kscreen.json"


def nep(naam: str, inhoud: str, taal: str = "bash") -> None:
    kop = "#!/usr/bin/bash\n" if taal == "bash" else "#!/usr/bin/python3\n"
    (NEP / naam).write_text(kop + inhoud)
    (NEP / naam).chmod(0o755)


def log() -> str:
    return LOG.read_text()


# Elke opdracht schrijft een regel in het logboek: zo zien we wat er (niet) gebeurde.
for naam in ("kwriteconfig6", "bugos-theme", "lpoptions", "plasma-apply-wallpaperimage", "bugos-store"):
    nep(naam, f'echo "{naam} $*" >> "{LOG}"\nexit 0\n')
# kreadconfig6: altijd de standaard (er is nog niets gezet).
nep("kreadconfig6", 'while [ $# -gt 0 ]; do [ "$1" = --default ] && { echo "$2"; exit 0; }; shift; done\n')
nep("timedatectl", f'echo "timedatectl $*" >> "{LOG}"\n[ "$1" = show ] && printf "Timezone=UTC\\nNTP=yes\\n"\nexit 0\n')
nep("localectl", 'printf "   X11 Layout: us\\n    X11 Model: pc105\\n"\n')
nep("xdg-user-dir", "exit 1\n")
# nmcli: er is al een netwerk 'Thuis' (dat mag nooit veranderen). 'Kapot' kan niet worden opgeslagen.
nep("nmcli", f'''echo "nmcli $*" >> "{LOG}"
case "$*" in
    *"-t -f NAME connection show"*) printf 'Thuis\\nWired connection 1\\n' ;;
    *"-t -f NAME,UUID,TYPE,ACTIVE connection show"*) printf 'Thuis:1111-aaaa:802-11-wireless:no\\n' ;;
    *"-g 802-11-wireless.ssid connection show uuid"*) echo "Thuis" ;;
    *"connection add"*Kapot*) echo "Error: kapot" >&2; exit 1 ;;
    *"connection add"*) echo "Connection 'x' (01234567-89ab-cdef-0123-456789abcdef) successfully added." ;;
esac
exit 0
''')
# busctl: één muis (event5) die links/rechts en snelheid kan.
nep("busctl", f'''echo "busctl $*" >> "{LOG}"
case "$*" in
    *devicesSysNames*) echo '{{"type":"as","data":["event5"]}}' ;;
    *GetAll*) echo '{{"type":"a{{sv}}","data":[{{"name":{{"type":"s","data":"Muis"}},"pointer":{{"type":"b","data":true}},"touchpad":{{"type":"b","data":false}},"supportsLeftHanded":{{"type":"b","data":true}},"supportsPointerAcceleration":{{"type":"b","data":true}},"leftHanded":{{"type":"b","data":false}},"pointerAcceleration":{{"type":"d","data":0.0}}}}]}}' ;;
esac
exit 0
''')
# kscreen-doctor: leest en schrijft een scherm in kscreen.json (zodat 'kijk of het echt zo staat' klopt).
nep("kscreen-doctor", f'''import json, re, sys
pad = {str(SCHERM)!r}
d = json.load(open(pad))
if sys.argv[1:] == ["-j"]:
    print(json.dumps(d)); sys.exit(0)
open({str(LOG)!r}, "a").write("kscreen-doctor " + " ".join(sys.argv[1:]) + "\\n")
for stap in sys.argv[1:]:
    m = re.fullmatch(r"output\\.([^.]+)\\.scale\\.([\\d.]+)", stap)
    for o in d["outputs"]:
        if m and o["name"] == m.group(1):
            o["scale"] = float(m.group(2))
json.dump(d, open(pad, "w"))
''', taal="python")
# Printers: er is er al een op 192.168.1.50; 10.0.0.99 antwoordt niet.
nep("lpstat", f'''echo "lpstat $*" >> "{LOG}"
case "$*" in
    "-v") echo "device for Oud: ipp://192.168.1.50/ipp/print" ;;
    "-d") echo "no system default destination" ;;
esac
exit 0
''')
nep("lpadmin", f'''echo "lpadmin $*" >> "{LOG}"
case "$*" in *10.0.0.99*) echo "lpadmin: Unable to connect to printer" >&2; exit 1 ;; esac
exit 0
''')
# firefox --headless: maakt het profiel, zoals de echte Firefox bij de eerste start.
nep("firefox", f'''echo "firefox $*" >> "{LOG}"
m="$HOME/.mozilla/firefox"; mkdir -p "$m/abcd.default-release"
printf '[Install4F96D1932A9F858E]\\nDefault=abcd.default-release\\nLocked=1\\n\\n[Profile0]\\nName=default-release\\nIsRelative=1\\nPath=abcd.default-release\\n\\n[General]\\nStartWithLastProfile=1\\nVersion=2\\n' > "$m/profiles.ini"
printf '[4F96D1932A9F858E]\\nDefault=abcd.default-release\\nLocked=1\\n' > "$m/installs.ini"
echo 'user_pref("browser.startup.homepage", "about:home");' > "$m/abcd.default-release/prefs.js"
''')
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"


def zet_scherm(breed: int, hoog: int, schaal: float = 1.0) -> None:
    """Het nep-scherm: één ingebouwd scherm van breed x hoog."""
    import bugos_config  # noqa: F401  eerst: bugos_config laadt de onderdelen zelf (anders een kring)
    import bugos_config_scherm as bs
    d = bs._voorbeeld_schermen()
    o = d["outputs"][0]
    o.update(scale=schaal, size={"width": breed, "height": hoog}, currentModeId="1", preferredModes=["1"])
    o["modes"] = [{"id": "1", "name": f"{breed}x{hoog}@60", "refreshRate": 60.0, "size": {"width": breed, "height": hoog}}]
    SCHERM.write_text(json.dumps(d))


zet_scherm(1280, 800)

import bugos_config as bi  # noqa: E402
import bugos_config_scherm as bs  # noqa: E402
import bugos_overstap_firefox as ff  # noqa: E402
import bugos_overstap_toepassen as ot  # noqa: E402

bs.HERLEES_WACHT = 0
bi.ben_beheerder = lambda: True   # dan lpadmin direct (zonder pkexec), zoals bij de eerste gebruiker van BugOS

# ============================================================================= de tabellen ===
klopt(ot.iana_zone("W. Europe Standard Time", "NL") == "Europe/Amsterdam"
      and ot.iana_zone("W. Europe Standard Time") == "Europe/Berlin"
      and ot.iana_zone("Romance Standard Time", "BE") == "Europe/Brussels",
      "tijdzone: Windows 'W. Europe Standard Time' + NL -> Europe/Amsterdam (zonder land: Berlin, CLDR '001')")
klopt(ot.iana_zone("India Standard Time") == "Asia/Kolkata" and ot.iana_zone("FLE Standard Time", "UA") == "Europe/Kyiv",
      "tijdzone: de oude CLDR-namen worden de nieuwe (Calcutta -> Kolkata, Kiev -> Kyiv)")
klopt(ot.iana_zone("Mars Standard Time") == "" and len(ot._tz()) > 130, "tijdzone: een onbekende geeft '' (niet raden)")
# VM-test 2026-11-16: notatie 'en-US' en taal 'en-NL' in 'W. Europe' gaf Berlijn (US hoort niet bij die zone).
# Het eerste land dat wél bij de Windows-zone hoort, telt.
klopt(ot.iana_zone("W. Europe Standard Time", ("US", "NL")) == "Europe/Amsterdam"
      and ot.iana_zone("W. Europe Standard Time", ("NL", "DE")) == "Europe/Amsterdam"
      and ot.iana_zone("W. Europe Standard Time", ("US", "")) == "Europe/Berlin",
      "tijdzone: notatie en-US + taal en-NL in W. Europe -> Amsterdam (het land dat bij de zone hoort)")
# (Niet de stap zelf draaien: die roept pkexec aan. Wel nakijken dat hij notatie én taal doorgeeft.)
_ot_bron = (ROOT / "system_files/usr/lib/bugos/python/bugos_overstap_toepassen.py").read_text(encoding="utf-8")
klopt(_ot_bron.count('(land_van(_tekst(ins.get("notatie"))), land_van(_tekst(ins.get("taal"))))') == 2,
      "tijdzone: overzicht en toepassen geven notatie en taal allebei door")
# Firefox' nieuwere wachtwoordopslag (logins.db) gaat nooit mee, net als logins.json en key4.db.
klopt({"logins.db", "logins.db-wal", "logins.db-shm", "logins.json", "key4.db"} <= ff.NOOIT_MEE,
      "Firefox: logins.db (nieuwe wachtwoordopslag) gaat nooit mee")
_ps = (ROOT / "windows-switch" / "BugOS-Switch.ps1").read_text(encoding="utf-8")
klopt("'logins.db'" in _ps and "'key4.db'" in _ps, "Windows-kant: logins.db wordt ook niet op de stick gezet")
# Dezelfde stick via /media én /run/media (op Fedora is /media een koppeling): één keer in de lijst.
_echt = TMP / "run-media" / "STICK"
(_echt / "BugOS-Switch").mkdir(parents=True, exist_ok=True)
(_echt / "BugOS-Switch" / "bugos-switch.json").write_text('{"versie": 2}', encoding="utf-8")
_link = TMP / "media-link"
_link.symlink_to(TMP / "run-media", target_is_directory=True)
_oud_schijven = os.environ.get("BUGOS_SCHIJVEN")
os.environ.pop("BUGOS_SCHIJVEN", None)
_gevonden = []
for _basis in (TMP / "run-media", _link):
    for _s in _basis.iterdir():
        _gevonden.extend(ot._op_schijf(_s))
klopt(len({p.resolve() for p in _gevonden}) == 1 and len(_gevonden) == 2,
      "stick: via /media en /run/media dezelfde map (voorwaarde voor de volgende controle)")
klopt("echt = map_.resolve()" in (ROOT / "system_files/usr/lib/bugos/python/bugos_overstap_toepassen.py").read_text(encoding="utf-8"),
      "stick: zoek_overstap telt het echte pad één keer (niet twee keer dezelfde stick)")
if _oud_schijven is not None:
    os.environ["BUGOS_SCHIJVEN"] = _oud_schijven
klopt(ot.land_van("nl-NL") == "NL" and ot.land_van("nl") == "" and ot.regio_code("nl-BE") == "nl_BE"
      and ot.taal_code("de-AT") == "de", "taal en notatie: nl-NL -> nl en nl_NL, land NL")
klopt(ot.xkb_voor("00020409") == bi.Indeling("us", "intl") and ot.xkb_voor("0413:00000413") == bi.Indeling("nl")
      and ot.xkb_voor("813") == bi.Indeling("be"),
      "toetsenbord: KLID 00020409 -> us/intl, ook '0413:00000413' en zonder voorloopnullen")
klopt(ot.xkb_voor("0000FFFF") is None and ot.xkb_voor("{GUID-IME}") is None and ot.xkb_voor(None) is None,
      "toetsenbord: een onbekende of een invoermethode (IME) wordt niet geraden")
klopt(all(bi.goede_indeling(bi.Indeling(*v)) for v in ot.KLID.values()),
      "toetsenbord: elke xkb-naam in de tabel is geldig voor zet_toetsenborden")
klopt(ot.schaal_waarde(125) == 1.25 and ot.schaal_waarde(100) == 1.0 and ot.schaal_waarde(175) == 1.75
      and ot.schaal_waarde(110) == 1.0 and ot.schaal_waarde(300) is None and ot.schaal_waarde("125") is None,
      "grootte: 125 % -> 1.25 uit de vaste lijst van Instellingen; onzin -> niets")
klopt(ot.snelheid_van_windows(10) == 50 and ot.snelheid_van_windows(1) == 0 and ot.snelheid_van_windows(20) == 100
      and ot.snelheid_van_windows(0) is None, "muis: Windows-snelheid 10 (gewoon) -> 50 in Instellingen, 1 -> 0, 20 -> 100")
klopt([ot.wifi_soort(b) for b in ("WPA2-Personal", "WPA3-Personal", "WPA2-Enterprise", "Open", "WEP", "", "WPA2/WPA3-Personal")]
      == ["psk", "sae", "zakelijk", "open", "wep", "", "psk"],
      "wifi: soort uit netsh (Personal, WPA3, Enterprise, Open, WEP; leeg is onbekend, niet open)")
klopt(ot.printer_adres("IP_192.168.1.40") == "192.168.1.40" and ot.printer_adres("192.168.1.40_1") == "192.168.1.40"
      and ot.printer_adres("http://printer.local:631/ipp/print") == "printer.local",
      "printers: Windows-poortnamen (IP_..., ..._1) en http-adressen -> een adres voor 'Op adres'")

# De programma's: elke regel deugt, en de gewone programma's komen goed uit.
_data = json.loads((ROOT / "system_files/usr/share/bugos/overstap-apps.json").read_text(encoding="utf-8"))
_regels = ot.app_regels()
klopt(len(_regels) == len(_data["apps"]) and len(_regels) > 50,
      f"programma's: elke regel in overstap-apps.json is bruikbaar (regex, soort, id) ({len(_regels)})")
klopt(all((r["soort"] == "negeer" or (r.get("nl") and r.get("en") and r["nl"] != r["en"]))
          and (r["soort"] != "winkel" or r.get("id")) for r in _data["apps"]),
      "programma's: elke regel heeft een Nederlandse en Engelse uitleg; elke Winkel-regel een id")
_s, _rest = ot.suggesties([{"naam": n} for n in (
    "Spotify", "Google Chrome", "Microsoft Edge", "Microsoft Edge WebView2 Runtime", "7-Zip 23.01 (x64)",
    "Microsoft 365 - nl-nl", "Microsoft Word 2016", "Adobe Photoshop 2024", "Adobe Acrobat Reader DC", "Notepad++ (64-bit)",
    "paint.net", "Discord", "Steam", "Minecraft Launcher", "Epic Games Launcher", "Battle.net", "OneDrive",
    "Microsoft Visual C++ 2015-2022 Redistributable (x64)", "WhatsApp", "Iets Heel Eigens 3.0", "Reset Tool")])
_per = {w: s for s in _s for w in s.windows}
klopt(_per["Spotify"].id == "com.spotify.Client" and _per["Spotify"].soort == "winkel"
      and _per["Google Chrome"].id == "com.google.Chrome" and _per["Microsoft Edge"].id == "com.microsoft.Edge",
      "programma's: Spotify, Chrome en Edge -> hun app in de Winkel")
klopt("Microsoft Edge WebView2 Runtime" not in _per and "Microsoft Visual C++ 2015-2022 Redistributable (x64)" not in _per
      and "Microsoft Visual C++ 2015-2022 Redistributable (x64)" not in _rest,
      "programma's: hulpstukken van Windows (WebView2, Visual C++) laten we niet zien")
klopt(_per["7-Zip 23.01 (x64)"].soort == "ingebouwd" and _per["Notepad++ (64-bit)"].soort == "ingebouwd",
      "programma's: 7-Zip en Notepad++ zitten al in BugOS (Ark, KWrite)")
klopt(_per["Microsoft 365 - nl-nl"] is _per["Microsoft Word 2016"] and _per["Microsoft Word 2016"].naam == "LibreOffice"
      and "anders" in _per["Microsoft Word 2016"].tekst.lower() + _per["Microsoft Word 2016"].tekst.lower(),
      "programma's: Office en Word samen bij LibreOffice, met een eerlijke regel (opmaak soms anders)")
klopt(_per["Adobe Photoshop 2024"].soort == "niet" and _per["OneDrive"].soort == "niet"
      and _per["Adobe Acrobat Reader DC"].id == "org.kde.okular" and _per["paint.net"].id == "com.github.PintaProject.Pinta",
      "programma's: Photoshop en OneDrive 'niet op BugOS'; Acrobat -> Okular, Paint.NET -> Pinta")
klopt(_per["Minecraft Launcher"].id == "org.prismlauncher.PrismLauncher" and _per["Epic Games Launcher"].id
      == "com.heroicgameslauncher.hgl" and _per["Battle.net"].soort == "niet",
      "programma's: Minecraft -> Prism Launcher, Epic -> Heroic, Battle.net: niet (via Lutris)")
klopt(_rest == ["Iets Heel Eigens 3.0", "Reset Tool"], f"programma's: wat we niet kennen, staat apart ({_rest})")
klopt(ot.winkel_opdracht("com.spotify.Client") == ["bugos-store", "appstream://com.spotify.Client"]
      and ot.winkel_opdracht("-rf /") == [], "programma's: de knop opent de Winkel op de pagina van de app, niets anders")

# ============================================================================= instellingen ===
LOG.write_text("")
ins = {"taal": "nl-NL", "notatie": "nl-NL", "tijdzone": "W. Europe Standard Time",
       "toetsenborden": ["00020409", "00000413", "0000FFFF"], "donker": True,
       "muis": {"linkshandig": True, "snelheid": 15, "scrollregels": 6}, "schaal": 125}
uit = ot.zet_instellingen(ins)
L = log()
klopt("plasma-localerc --group Translations --key LANGUAGE --notify nl:en_US" in L
      and "--group Formats --key LC_TIME --notify nl_NL.UTF-8" in L,
      "instellingen: taal Nederlands en de notatie nl_NL, via zet_taal en zet_regio (plasma-localerc)")
klopt("timedatectl set-timezone Europe/Amsterdam" in L, "instellingen: tijdzone Europe/Amsterdam via zet_tijdzone")
klopt("kxkbrc --group Layout --key LayoutList us,nl" in L and "--key VariantList intl," in L and
      "--key Use --notify true" in L, "instellingen: toetsenborden us/intl en nl in kxkbrc (zet_toetsenborden)")
klopt(any(u.soort == ot.ZELF and "0000FFFF" in u.tekst for u in uit),
      "instellingen: het onbekende toetsenbord staat in de lijst: 'kies het zelf'")
klopt("bugos-theme donker" in L, "instellingen: donker via bugos-theme")
klopt("InputDevice/event5 org.kde.KWin.InputDevice leftHanded b true" in L
      and "pointerAcceleration d 0.50" in L and "scrollFactor d 2.00" in L
      and "kdeglobals --group KDE --key WheelScrollLines --notify 6" in L,
      "instellingen: muis linkshandig, sneller (15 -> 75), 6 regels per tikje (KWin en kdeglobals)")
klopt("kscreen-doctor output" not in L and any(u.soort == ot.NIET and "125 %" in u.tekst and "past niet" in u.tekst
                                                 for u in uit),
      "instellingen: 125 % past niet op 1280x800 (dezelfde regel als Instellingen): niet gezet, wel gezegd")
zet_scherm(1920, 1080)
LOG.write_text("")
uit = ot.zet_instellingen({"schaal": 125})
klopt("kscreen-doctor output.eDP-1.scale.1.25" in log() and uit and uit[0].soort == ot.GOED,
      f"instellingen: op 1920x1080 past 125 % wel en wordt gezet ({[u.tekst for u in uit]})")
klopt(ot.zet_instellingen({"schaal": 125})[0].tekst.endswith("(stond al zo)."),
      "instellingen: stond het al zo, dan niets opnieuw zetten")
zet_scherm(1280, 800)
klopt(ot.zet_instellingen({}) == [] and ot.zet_instellingen("kapot") == [],
      "instellingen: niets (of iets geks) op de stick: niets doen")
_vreemd = ot.zet_instellingen({"taal": "xx-YY", "tijdzone": "Mars Standard Time"})
klopt([u.soort for u in _vreemd] == [ot.NIET, ot.NIET], "instellingen: onbekende taal en tijdzone: 'kan niet', geen gok")
# D-10: de VM-test. BugOS is hier Engels (LANG=en_US); de stick heeft taal nl-NL en notatie en-US. Taal aan, notatie
# uit: de taal wordt Nederlands, maar de datum en tijd blijven Amerikaans (zet_taal haalt LC_TIME weg; dat zetten we
# terug naar wat het was). Andersom: notatie aan, taal uit: alleen LC_TIME, de taal blijft.
LOG.write_text("")
_d10 = {"taal": "nl-NL", "notatie": "nl-NL", "tijdzone": "W. Europe Standard Time"}
uit = ot.zet_instellingen(_d10, met_taal=True, met_notatie=False, met_rest=False)
L = log()
klopt("--group Translations --key LANGUAGE --notify nl:en_US" in L and L.rstrip().endswith(
    "--group Formats --key LC_TIME --notify en_US.UTF-8") and "timedatectl" not in L
      and any(u.deel == "notatie" and "Blijft zoals in Verenigde Staten" in u.tekst for u in uit),
      "D-10: taal aan en notatie uit: Nederlands, maar de datum en tijd blijven zoals ze waren (en niets anders)")
LOG.write_text("")
uit = ot.zet_instellingen(_d10, met_taal=False, met_notatie=True, met_rest=False)
L = log()
klopt("Translations" not in L and "--key LC_TIME --notify nl_NL.UTF-8" in L
      and any(u.deel == "taal" and u.tekst.startswith("Blijft English (Windows had Nederlands)") for u in uit),
      "D-10: notatie aan en taal uit: alleen de datum en tijd, de taal blijft English")
LOG.write_text("")
klopt(ot.zet_instellingen({"taal": "en-NL", "notatie": "en-US"}, met_taal=False, met_notatie=False) == [] and log() == "",
      "D-10: Windows had dezelfde taal en notatie als BugOS: niets te doen, en ook geen 'blijft'-regels")
klopt(ot.taal_wissel({"taal": "nl-NL"}) == ("en", "nl") and ot.taal_wissel({"taal": "en-NL"}) == ("en", "")
      and ot.taal_wissel({"taal": "xx-YY"}) == ("en", "") and ot.notatie_wissel({"notatie": "en-US"}) == ("en_US", ""),
      "D-10: taal_wissel/notatie_wissel: alleen een wissel als het echt anders is en BugOS het kent")
klopt(ot.regio_voorbeeld("en_US") == "2:58 PM, 11/16/26" and ot.regio_voorbeeld("nl_NL") == "14:58, 16-11-2026"
      and ot.regio_voorbeeld("de_DE") == "14:58, 16.11.2026",
      "D-10: bij de notatie een voorbeeld van de klok en de datum (12 uur en maand/dag zie je meteen)")

# ===================================================================================== wifi ===
LOG.write_text("")
uit = ot.zet_wifi([{"naam": "Thuis", "beveiliging": "WPA2-Personal"},
                   {"naam": "Thuis-5G", "beveiliging": "WPA2-Personal"},
                   {"naam": "Zolder", "beveiliging": "WPA3-Personal", "verborgen": True},
                   {"naam": "eduroam", "beveiliging": "WPA2-Enterprise"},
                   {"naam": "Kapot", "beveiliging": "WPA2-Personal"},
                   {"naam": "-x", "beveiliging": "WPA2-Personal"}])
L = log()
_add = [r for r in L.splitlines() if "connection add" in r]
klopt(not any(" Thuis " in r + " " for r in _add) and "modify" not in L and "delete" not in L,
      "wifi: het bestaande netwerk 'Thuis' wordt niet overschreven (geen add, modify of delete)")
klopt(any("con-name Thuis-5G ssid Thuis-5G" in r and "wifi-sec.key-mgmt wpa-psk wifi-sec.psk-flags 1" in r
          and "connection.permissions user:" in r for r in _add),
      "wifi: Thuis-5G opgeslagen zonder wachtwoord (psk-flags 1: BugOS vraagt het één keer), alleen voor jou")
klopt(not any(x in r for r in _add for x in ("wifi-sec.psk ", "802-11-wireless-security.psk ", "--ask", "password"))
      and "wachtwoord" not in L.lower(),
      "wifi: nooit een wachtwoord op de opdrachtregel")
klopt(any("Zolder" in r and "key-mgmt sae" in r and "802-11-wireless.hidden yes" in r for r in _add),
      "wifi: WPA3 (sae) en een verborgen netwerk")
klopt(not any("eduroam" in r for r in _add) and any(u.soort == ot.ZELF and "eduroam" in u.tekst and "Instellingen" in u.tekst
                                                    for u in uit),
      "wifi: school/werk (eduroam): geen profiel, wel 'log één keer in via Instellingen > Wifi'")
klopt(any(u.soort == ot.ZELF and "Kapot" in u.tekst for u in uit) and not any("-x" in r for r in _add),
      "wifi: wat niet opgeslagen kon worden staat erbij; een naam die met '-' begint gaat nooit naar nmcli")

# ================================================================================= printers ===
LOG.write_text("")
uit = ot.zet_printers([{"naam": "HP LaserJet", "adres": "IP_192.168.1.40", "standaard": True},
                       {"naam": "Oude Canon", "adres": "192.168.1.50"},
                       {"naam": "Kelder", "adres": "10.0.0.99"},
                       {"naam": "USB-ding", "adres": "USB001"}])
L = log()
klopt("lpadmin -p HP_LaserJet -E -v ipp://192.168.1.40/ipp/print -m everywhere -D HP LaserJet" in L
      and "lpoptions -d HP_LaserJet" in L,
      "printers: HP LaserJet op 192.168.1.40 met IPP Everywhere, en je standaardprinter (zoals Windows)")
klopt("192.168.1.50" not in L.replace("lpstat -v", "") and any("Oude Canon" in u.tekst and u.soort == ot.GOED for u in uit),
      "printers: een printer die er al is (zelfde adres), wordt niet nog eens toegevoegd")
klopt(any(u.soort == ot.ZELF and "Kelder" in u.tekst for u in uit) and any("USB-ding" in u.tekst for u in uit)
      and uit[0].soort == ot.GOED, "printers: wat niet lukt staat in de lijst; de rest gaat gewoon door")

# ==================================================================================== Firefox ===
# Een eigen LZ4-lezer: een blok met alleen letterlijke bytes, en een met een herhaling die zichzelf overlapt.
_tekst = b'{"a":1}'
klopt(ff.lz4_blok(bytes([len(_tekst) << 4]) + _tekst, 100) == _tekst, "lz4: een blok met alleen letterlijke bytes")
klopt(ff.lz4_blok(bytes([0x1F, ord("a"), 1, 0, 6]) + bytes([0x10, ord("b")]), 100) == b"a" * 26 + b"b",
      "lz4: een overlappende herhaling ('aaaa…') en lange lengtes")
try:
    ff.lz4_blok(bytes([0x1F, ord("a"), 9, 0, 6]), 100)
    klopt(False, "lz4: een verwijzing naar vóór het begin is kapot")
except ValueError:
    klopt(True, "lz4: een verwijzing naar vóór het begin is kapot (ValueError, geen crash)")


def mozlz4(data: dict) -> bytes:
    """Een .jsonlz4 zoals Firefox hem maakt (hier met één blok letterlijke bytes)."""
    ruw = json.dumps(data).encode()
    lengte = len(ruw) - 15
    token = bytes([0xF0]) + bytes([255] * (lengte // 255)) + bytes([lengte % 255])
    return b"mozLz40\0" + struct.pack("<I", len(ruw)) + token + ruw


def stick(naam: str, data: dict | None, mappen: tuple = ("Documents",)) -> Path:
    """Een nep-stick met de map BugOS-Switch."""
    s = TMP / naam / "BugOS-Switch"
    s.mkdir(parents=True)
    for m in mappen:
        (s / m).mkdir()
        (s / m / f"van-{naam}.txt").write_text(naam)
    if data is not None:
        (s / "bugos-switch.json").write_text(json.dumps(data), encoding="utf-8")
    return s


CHROME = {"roots": {"bookmark_bar": {"children": [{"type": "url", "name": "Nieuws", "url": "https://nos.nl/",
                                                   "date_added": "13300000000000000"},
                                                  {"type": "url", "name": "Instellingen", "url": "chrome://settings"},
                                                  {"type": "folder", "name": "Werk & <b>zo</b>", "children": [
                                                      {"type": "url", "name": "Mail", "url": "https://mail.example/"}]}]},
                    "other": {"children": [{"type": "url", "name": "Recept", "url": "https://recept.example/"}]}}}
FIREFOX = {"guid": "root________", "children": [
    {"guid": "toolbar_____", "typeCode": 2, "children": [{"typeCode": 1, "title": "Wiki", "uri": "https://wiki.example/",
                                                          "tags": "leren", "keyword": "w"}]},
    {"guid": "menu________", "typeCode": 2, "children": [{"typeCode": 3}, {"typeCode": 1, "title": "Menu-ding",
                                                                           "uri": "https://menu.example/"}]}]}

V2 = stick("v2", {
    "versie": 2, "gebruiker": "Bugie", "computer": "WOONKAMER", "taal": "nl",
    "instellingen": {"taal": "nl-NL", "notatie": "nl-NL", "tijdzone": "W. Europe Standard Time",
                     "toetsenborden": ["00020409"], "donker": True,
                     "muis": {"linkshandig": False, "snelheid": 10, "scrollregels": 3}, "schaal": 100},
    "wifi": [{"naam": "Thuis", "beveiliging": "WPA2-Personal"}, {"naam": "Thuis-5G", "beveiliging": "WPA2-Personal"},
             {"naam": "eduroam", "beveiliging": "WPA2-Enterprise"}],
    "printers": [{"naam": "HP LaserJet", "adres": "192.168.1.40", "standaard": True}],
    "programmas": [{"naam": "Spotify", "uitgever": "Spotify AB"}, {"naam": "Adobe Photoshop 2024"},
                   {"naam": "Iets Eigens"}],
    "browsers": [{"browser": "Chrome", "profiel": "Default", "naam": "Persoon 1", "bladwijzers": "Bladwijzers/Chrome-Default.json"},
                 {"browser": "Chrome", "profiel": "Profile 1", "naam": "Werk", "bladwijzers": "Bladwijzers/Chrome-Profile 1.json"},
                 {"browser": "Firefox", "profiel": "abc", "bladwijzers": "Bladwijzers/Firefox-abc.jsonlz4"},
                 {"browser": "Kwaad", "bladwijzers": "../../../etc/passwd"}],
    "firefox_profiel": "Firefox/abc123.default-release",
}, mappen=("Documents", "Pictures"))
(V2 / "Bladwijzers").mkdir()
(V2 / "Bladwijzers" / "Chrome-Default.json").write_text(json.dumps(CHROME))
(V2 / "Bladwijzers" / "Chrome-Profile 1.json").write_text(json.dumps({"roots": {"bookmark_bar": {"children": [
    {"type": "url", "name": "Intranet", "url": "https://intranet.example/"}]}}}))
(V2 / "Bladwijzers" / "Firefox-abc.jsonlz4").write_bytes(mozlz4(FIREFOX))
(V2 / "achtergrond.jpg").write_bytes(b"jpg")
FXW = V2 / "Firefox" / "abc123.default-release"
FXW.mkdir(parents=True)
for n in ("logins.json", "key4.db", "cookies.sqlite", "compatibility.ini", "extensions.json", "sessionstore.jsonlz4"):
    (FXW / n).write_text("geheim" if n in ("logins.json", "key4.db", "cookies.sqlite") else "windows")
(FXW / "prefs.js").write_text('user_pref("browser.download.dir", "C:\\\\Users\\\\Bugie\\\\Downloads");\n'
                              'user_pref("browser.startup.page", 3);\n')
(FXW / "extensions").mkdir()
(FXW / "extensions" / "ublock@example.xpi").write_bytes(b"xpi")

i2 = ot.info(V2)
bronnen = ff.bladwijzer_bronnen(V2, i2)
klopt([b.naam for b in bronnen] == ["Chrome (Persoon 1)", "Chrome (Werk)", "Firefox"],
      f"bladwijzers: elk profiel apart, met zijn naam; een pad buiten de stick telt niet ({[b.naam for b in bronnen]})")
klopt(ff.lees_bron(bronnen[2])[0]["kinderen"][0]["sleutel"] == "w" and ff.lees_bron(bronnen[2])[1]["kinderen"][0] == {"scheiding": True},
      "bladwijzers: Firefox.jsonlz4 van Windows wordt gelezen (met sleutelwoord en scheidingslijn)")
_chr = ff.lees_bron(bronnen[0])
klopt(_chr[0]["url"] == "https://nos.nl/" and _chr[0]["datum"] > 1_600_000_000 and all(k.get("url") != "chrome://settings" for k in _chr),
      "bladwijzers: Chrome-datum naar Firefox-tijd; chrome://-pagina's (werken niet in Firefox) gaan niet mee")

# Firefox nog nooit gestart: BugOS laat Firefox zelf het profiel maken (headless), en zet de bladwijzers erin.
LOG.write_text("")
u = ff.bladwijzers_naar_firefox(bronnen, "WOONKAMER")
PROFIEL = THUIS / ".mozilla/firefox/abcd.default-release"
prefs = (PROFIEL / "prefs.js").read_text()
html = (PROFIEL / ff.EIGEN_BESTAND).read_text()
klopt("firefox --headless --screenshot" in log() and u.soort == ot.GOED,
      f"bladwijzers: zonder Firefox-profiel maakt Firefox er zelf een (headless) ({u.tekst[:60]})")
klopt('user_pref("browser.places.importBookmarksHTML", true);' in prefs
      and f'user_pref("browser.bookmarks.file", "{PROFIEL / ff.EIGEN_BESTAND}");' in prefs
      and 'browser.startup.homepage' in prefs and not (PROFIEL / "user.js").exists(),
      "bladwijzers: Firefox leest ze bij de volgende start (prefs.js, niet user.js: dan maar één keer)")
klopt('PERSONAL_TOOLBAR_FOLDER="true">Bookmarks Toolbar' in html and ">Van Windows (WOONKAMER)</H3>" in html
      and ">Chrome (Persoon 1)</H3>" in html and "Werk &amp; &lt;b&gt;zo&lt;/b&gt;" in html
      and 'SHORTCUTURL="w"' in html and 'TAGS="leren"' in html,
      "bladwijzers: in één map 'Van Windows' op de balk, per profiel een map, veilig geschreven")

# Er staan al bladwijzers in Firefox (met een tag en een sleutelwoord): die blijven, want Firefox vervangt alles.
db = sqlite3.connect(str(PROFIEL / "places.sqlite"))
db.executescript("""
CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);
CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER, parent INTEGER, position INTEGER,
                            title TEXT, guid TEXT, dateAdded INTEGER);
CREATE TABLE moz_keywords (id INTEGER PRIMARY KEY, keyword TEXT, place_id INTEGER);
INSERT INTO moz_places VALUES (1, 'https://eigen.example/'), (2, 'https://balk.example/');
INSERT INTO moz_bookmarks VALUES (1, 2, NULL, 0, 0, '', 'root________', 0), (2, 2, NULL, 1, 0, 'menu', 'menu________', 0),
    (3, 2, NULL, 1, 1, 'toolbar', 'toolbar_____', 0), (4, 2, NULL, 1, 2, 'tags', 'tags________', 0),
    (5, 2, NULL, 1, 3, 'unfiled', 'unfiled_____', 0), (6, 1, 1, 2, 0, 'Eigen', 'aaaaaaaaaaaa', 1600000000000000),
    (7, 1, 2, 3, 0, 'Op de balk', 'bbbbbbbbbbbb', 0), (8, 2, NULL, 4, 0, 'kook', 'cccccccccccc', 0),
    (9, 1, 1, 8, 0, NULL, 'dddddddddddd', 0), (10, 3, NULL, 2, 1, NULL, 'eeeeeeeeeeee', 0);
INSERT INTO moz_keywords VALUES (1, 'eg', 1);
""")
db.commit()
db.close()
u = ff.bladwijzers_naar_firefox(bronnen[:1], "WOONKAMER")
html = (PROFIEL / ff.EIGEN_BESTAND).read_text()
klopt('HREF="https://eigen.example/" ADD_DATE="1600000000" TAGS="kook" SHORTCUTURL="eg">Eigen</A>' in html
      and ">Op de balk</A>" in html and "<HR>" in html and html.index("Op de balk") < html.index("Van Windows"),
      "bladwijzers: wat al in Firefox stond (met tag, sleutelwoord, datum en scheiding) blijft, de nieuwe map erachter")
klopt(">Nieuws</A>" in html and ">Chrome (Persoon 1)</H3>" not in html,
      "bladwijzers: één profiel op de stick: alles direct in de map 'Van Windows'")
# Staat de map al in Firefox (Firefox heeft ze ingelezen), dan niet nog een keer.
db = sqlite3.connect(str(PROFIEL / "places.sqlite"))
db.execute("INSERT INTO moz_bookmarks VALUES (11, 2, NULL, 3, 1, 'Van Windows (WOONKAMER)', 'ffffffffffff', 0)")
db.commit()
db.close()
(PROFIEL / ff.EIGEN_BESTAND).unlink()
u = ff.bladwijzers_naar_firefox(bronnen, "WOONKAMER")
klopt(u.soort == ot.GOED and not (PROFIEL / ff.EIGEN_BESTAND).exists(), "bladwijzers: nog eens doen zet ze er niet dubbel in")
# Firefox staat open: niets aanraken (Firefox schrijft prefs.js bij het sluiten weer over).
(PROFIEL / "lock").symlink_to(f"127.0.0.1:+{os.getpid()}")
u = ff.bladwijzers_naar_firefox(bronnen, "ANDERE-PC")
klopt(u.soort == ot.ZELF and "Sluit Firefox" in u.tekst and not (PROFIEL / ff.EIGEN_BESTAND).exists(),
      "bladwijzers: Firefox staat open: niets veranderd, 'sluit Firefox en druk nog eens op Overzetten'")
(PROFIEL / "lock").unlink()
# Een kapot places.sqlite: niets doen (inlezen zou alles vervangen), en zeggen hoe het met de hand gaat.
(PROFIEL / "places.sqlite").rename(PROFIEL / "places.goed")
(PROFIEL / "places.sqlite").write_bytes(b"dit is geen database")
u = ff.bladwijzers_naar_firefox(bronnen, "ANDERE-PC")
klopt(u.soort == ot.ZELF and not (PROFIEL / ff.EIGEN_BESTAND).exists() and "Importeren" in u.tekst,
      "bladwijzers: huidige bladwijzers niet te lezen: niets veranderd (anders zou je ze kwijtraken)")
(PROFIEL / "places.sqlite").unlink()
(PROFIEL / "places.goed").rename(PROFIEL / "places.sqlite")

# Het Firefox-profiel van Windows overnemen.
u = ff.profiel_overnemen(FXW, "WOONKAMER")
ini = ff._ini(THUIS / ".mozilla/firefox/profiles.ini")
nieuw = next(s for s in ini.sections() if ini[s].get("Name") == "Van Windows (WOONKAMER)")
NIEUW = THUIS / ".mozilla/firefox" / ini[nieuw]["Path"]
klopt(u.soort == ot.GOED and NIEUW.is_dir() and (NIEUW / "extensions" / "ublock@example.xpi").exists(),
      f"firefox: het profiel van Windows staat als nieuw profiel in ~/.mozilla/firefox ({u.tekst[:50]})")
klopt(not any((NIEUW / n).exists() for n in ("logins.json", "key4.db", "cookies.sqlite", "sessionstore.jsonlz4")),
      "firefox: nooit wachtwoorden of cookies, ook niet als ze op de stick stonden")
klopt(not (NIEUW / "compatibility.ini").exists() and not (NIEUW / "extensions.json").exists()
      and "C:\\\\" not in (NIEUW / "prefs.js").read_text() and "browser.startup.page" in (NIEUW / "prefs.js").read_text(),
      "firefox: wat Windows-paden heeft (compatibility.ini, extensions.json, de downloadmap op C:) laat Firefox zelf opnieuw maken")
klopt(ini["Install4F96D1932A9F858E"]["Default"] == NIEUW.name and PROFIEL.is_dir()
      and any(ini[s].get("Path") == "abcd.default-release" for s in ini.sections())
      and ff._ini(THUIS / ".mozilla/firefox/installs.ini")["4F96D1932A9F858E"]["Default"] == NIEUW.name
      and ff.standaard_profiel() == NIEUW,
      "firefox: het nieuwe profiel is nu het standaardprofiel; het oude blijft (reserve)")
klopt(ff.profiel_overnemen(FXW, "WOONKAMER").soort == ot.GOED
      and sum(1 for s in ff._ini(THUIS / ".mozilla/firefox/profiles.ini").sections() if s.startswith("Profile")) == 2,
      "firefox: nog eens doen maakt geen tweede kopie")
klopt("=" in (THUIS / ".mozilla/firefox/profiles.ini").read_text() and " = " not in (THUIS / ".mozilla/firefox/profiles.ini").read_text(),
      "firefox: profiles.ini zoals Firefox hem schrijft (Sleutel=waarde)")

# ============================================================== het venster (versie 2 en versie 1) ===
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

app = QApplication.instance() or bugos_ui.maak_app("bugos-test", "bugos-test", ["test"])
bugos_ui.maak_app = lambda *a, **k: app
_gevangen: list = []
bugos_ui.uitvoeren = lambda _app, w: _gevangen.append(w) or 0


def laad(naam: str, programma: str):
    lader = importlib.machinery.SourceFileLoader(naam, str(BIN / programma))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


def wacht(voorwaarde, ms: int = 15000) -> bool:
    klok = QElapsedTimer()
    klok.start()
    while not voorwaarde() and klok.elapsed() < ms:
        app.processEvents()
    return voorwaarde()


def teksten(w) -> str:
    return " | ".join(x.text() for x in w.findChildren(QLabel) if x.isVisibleTo(w) and x.text())


bo = laad("bugos_overstap", "bugos-switch")
bo.gebruikersmap = lambda xdg, standaard: THUIS / standaard
for m in ("Documents", "Pictures"):
    (THUIS / m).mkdir(exist_ok=True)

# Een nieuwe thuismap voor Firefox (zonder profiel), zodat het venster alles van voren af aan doet.
import shutil  # noqa: E402
shutil.rmtree(THUIS / ".mozilla")
os.environ["BUGOS_SCHIJVEN"] = str(V2.parent)
zet_scherm(1280, 800)
LOG.write_text("")
bo.venster()
w = _gevangen[-1]
w.show()
app.processEvents()
klopt(set(w.schakelaars) == {"bestanden", "bladwijzers", "firefox", "achtergrond", "instellingen", "taal", "notatie",
                              "wifi", "printers"}
      and all(s.isChecked() for k, s in w.schakelaars.items() if k not in ("taal", "notatie"))
      and w.overzicht.isVisibleTo(w) and not w.wat.isVisibleTo(w),
      f"venster: het overzicht van een stick van versie 2: elk onderdeel met een schuifje, alles aan ({sorted(w.schakelaars)})")
# D-10: deze BugOS is Engels met de Amerikaanse notatie (LANG=en_US in de test), de stick Nederlands. Taal en notatie
# hebben een eigen schuifje met 'nu -> straks', en dat staat UIT: BugOS verandert je taal niet zonder dat je het aanzet.
_t = teksten(w)
klopt(not w.schakelaars["taal"].isChecked() and not w.schakelaars["notatie"].isChecked()
      and "English -> Nederlands" in _t and "Verenigde Staten -> Nederland (14:58, 16-11-2026)" in _t,
      "D-10: taal en notatie staan als 'nu -> straks' in het overzicht, elk met een eigen schuifje dat uit staat")
klopt("Nederlands" not in next((o.uitleg for o in ot.onderdelen(V2) if o.sleutel == "instellingen"), ""),
      "D-10: het schuifje 'Instellingen' noemt de andere taal niet meer (alleen het woord 'English' was te weinig)")
klopt("Thuis-5G" in _t and "HP LaserJet" in _t and "Spotify" in _t and "Niet op BugOS" in _t and "Iets Eigens" in _t,
      "venster: het overzicht noemt de wifi, de printer en de programma's (met 'niet op BugOS' en de rest)")
_winkel = [k for k in w.programmas.findChildren(QPushButton) if k.text() == "In de Winkel"]
klopt(len(_winkel) == 1 and not any("nstalle" in k.text() for k in w.findChildren(QPushButton)),
      "venster: per Winkel-app een knop 'In de Winkel', nergens een knop die zelf installeert")
_winkel[0].click()
klopt(wacht(lambda: "bugos-store appstream://com.spotify.Client" in log(), 5000),
      "venster: 'In de Winkel' opent de Winkel op de pagina van Spotify (bugos-store appstream://…)")
w.schakelaars["wifi"].setChecked(False)   # wifi niet: dan ook niets met nmcli
LOG.write_text("")
w.begin()
klopt(wacht(lambda: not w.bezig() and w.samenvatting.isVisibleTo(w), 30000),
      "venster: Overzetten loopt door tot de samenvatting (de bestanden, dan de rest op de achtergrond)")
L = log()
_t = teksten(w)
klopt((THUIS / "Documents" / "van-v2.txt").exists() and (THUIS / "Pictures" / "van-v2.txt").exists(),
      "venster: de bestanden staan op hun plek")
_samen = teksten(w.samenvatting)
klopt("connection add" not in L and "Wifi" not in _samen,
      "venster: wifi stond uit: niets met wifi gedaan, en het staat ook niet in de samenvatting")
klopt("timedatectl set-timezone Europe/Amsterdam" in L and "bugos-theme donker" in L and "lpadmin -p HP_LaserJet" in L,
      "venster: instellingen en printer zijn overgezet")
klopt("--group Translations" not in L and "--key LC_TIME" not in L and "--key LANG " not in L
      and "Blijft English (Windows had Nederlands)" in _samen and "Blijft zoals in Verenigde Staten" in _samen,
      "D-10: taal en notatie stonden uit: BugOS blijft Engels met dezelfde datum en tijd, en zegt dat in de samenvatting")
klopt(all(x in _samen for x in ("Je bestanden", "Instellingen", "Tijdzone: Amsterdam", "Printers", "Bladwijzers",
                                 "Je Firefox van Windows", "Je achtergrond")),
      f"venster: de samenvatting noemt per onderdeel wat er gebeurde ({_samen[:120]})")
_ff_ini = ff._ini(THUIS / ".mozilla/firefox/profiles.ini")
_nieuw = next((s for s in _ff_ini.sections() if _ff_ini[s].get("Name", "").startswith("Van Windows")), "")
_nieuw_pad = THUIS / ".mozilla/firefox" / _ff_ini[_nieuw]["Path"] if _nieuw else THUIS
_html = (_nieuw_pad / ff.EIGEN_BESTAND).read_text() if (_nieuw_pad / ff.EIGEN_BESTAND).exists() else ""
klopt(bool(_nieuw) and ">Chrome (Werk)</H3>" in _html and "Wiki" not in _html,
      "venster: eerst het Firefox-profiel van Windows, dan de Chrome-bladwijzers erin (die van Firefox zaten er al)")
klopt(any(p.name.startswith("Bladwijzers-van-Windows") for p in (THUIS / "Documents").iterdir()),
      "venster: een kopie van de bladwijzers staat in Documenten (zoals in versie 1)")
klopt("Klaar" in w.melding.tekst.text() and w.knop.isEnabled(), f"venster: klaar ({w.melding.tekst.text()[:60]})")
w.close()
# D-10: de melding tijdens het overzetten noemt alleen wat aan staat ('wifi en printers' stond er ook als die uit waren).
_b1 = bo.bezig_tekst({"instellingen"})
_b2 = bo.bezig_tekst({"taal", "bladwijzers"})
_b3 = bo.bezig_tekst({"instellingen", "wifi", "printers"})
klopt("wifi" not in _b1 and "printer" not in _b1 and "je instellingen" in _b1 and "de tijdzone" in _b1
      and "wachtwoord" not in _b2 and "je instellingen en je bladwijzers" in _b2
      and "je wifi-netwerken en je printers" in _b3 and "de tijdzone en de printers" in _b3
      and bo.bezig_tekst(set()) == "",
      f"D-10: de melding noemt alleen wat aan staat, en het wachtwoord alleen als dat nodig is ({_b1!r} | {_b2!r})")

# Een stick van versie 1: alleen bestanden, bladwijzers en achtergrond. Werkt zoals altijd.
V1 = stick("v1", {"gebruiker": "Oma", "computer": "OUDE-PC"})
(V1 / "Bladwijzers").mkdir()
(V1 / "Bladwijzers" / "Edge.json").write_text(json.dumps(CHROME))
os.environ["BUGOS_SCHIJVEN"] = str(V1.parent)
bo.venster()
w = _gevangen[-1]
w.show()
app.processEvents()
klopt(set(w.schakelaars) == {"bestanden", "bladwijzers"} and not w.programmas.isVisibleTo(w),
      f"venster: een stick van versie 1: alleen bestanden en bladwijzers (geen instellingen of programma's) ({sorted(w.schakelaars)})")
LOG.write_text("")
w.begin()
klopt(wacht(lambda: not w.bezig() and w.samenvatting.isVisibleTo(w), 30000) and (THUIS / "Documents" / "van-v1.txt").exists(),
      "venster: versie 1 zet de bestanden en bladwijzers over")
klopt("nmcli" not in log() and "lpadmin" not in log() and "kwriteconfig6" not in log(),
      "venster: versie 1 verandert geen instellingen, wifi of printers")
w.close()
klopt(bo.zonder_venster(V1) == 0, "zonder venster (--zet) werkt nog voor versie 1")
klopt([o.sleutel for o in ot.onderdelen(stick("kapot", None))] == ["bestanden"],
      "een stick zonder (leesbaar) bugos-switch.json: alleen de mappen, geen crash")

# ============================================================ voorbeeldstand (schermfoto's, schermtest) ===
# Met BUGOS_INSTELLINGEN_VOORBEELD=1 verandert er niets aan de computer: geen enkele opdracht.
bi.VOORBEELD = True
LOG.write_text("")
_vb = (ot.zet_instellingen(ins) + ot.zet_wifi(i2["wifi"]) + ot.zet_printers(i2["printers"])
       + [ff.bladwijzers_naar_firefox(bronnen, "X"), ff.profiel_overnemen(FXW, "X")])
klopt(log() == "" and len(_vb) > 5 and ot.voorbeeld_uitslagen(),
      f"voorbeeldstand: alles overzetten draait zonder één opdracht uit te voeren ({log()[:80]!r})")
bi.VOORBEELD = False

# ================================================================================== Welkom ===
os.environ["BUGOS_SCHIJVEN"] = str(V2.parent)
welkom = laad("bugos_welkom", "bugos-welcome")
klaar = welkom.Klaar()
klaar.show()
app.processEvents()
_t = teksten(klaar)
klopt("Haal alles van je oude pc" in _t, "Welkom: de tegel heet 'Haal alles van je oude pc'")
klopt(klaar.stick.isVisibleTo(klaar) and "WOONKAMER" in klaar.stick.tekst.text(),
      "Welkom: zit de BugOS Switch-schijf erin, dan staat dat op de laatste pagina (van wie, welke computer)")
klaar.hide()
os.environ["BUGOS_SCHIJVEN"] = str(TMP / "leeg")
klaar.show()
app.processEvents()
klopt(not klaar.stick.isVisibleTo(klaar), "Welkom: zonder die schijf geen melding")

print(f"\n{fouten} fout(en)")
sys.exit(1 if fouten else 0)
