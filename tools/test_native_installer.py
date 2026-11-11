#!/usr/bin/env python3
"""Test van de live-stick en het installatieprogramma (iso_live/src): wifi, woorden, tijdzone, voortgang, klaar.

Alles gebeurt in een tijdelijke map met nep-programma's vooraan op PATH (nmcli, systemctl, liveinst, bugos-live ...);
er wordt niets aan de computer veranderd. Dit draait in de CI-container (Python 3.12, PySide6, geen node, geen
image). Met --beeld draait het IN de live-image (localhost/bugos-live:lokaal) en kijkt het naar de echte bestanden
van het installatieprogramma (zie beeld() onderaan).

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_installer.py
          podman run --rm --privileged -v <repo>:/repo:ro --entrypoint /usr/bin/bash localhost/bugos-live:lokaal \\
              -c "python3 /repo/tools/test_native_installer.py --beeld"
"""

from __future__ import annotations

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
SRC = ROOT / "iso_live" / "src"
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
TMP = Path(tempfile.mkdtemp(prefix="bugos-installer-test-"))
NEP = TMP / "nep"
LOG = TMP / "aanroepen.log"
NEP.mkdir()
BEELD = "--beeld" in sys.argv[1:]
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def nep(naam: str, inhoud: str) -> None:
    """Een nep-programma (bash) vooraan op PATH; het schrijft zijn naam en argumenten in het logboek."""
    pad = NEP / naam
    pad.write_text("#!/usr/bin/bash\n" f"printf '%s\\n' \"{naam} $*\" >> '{LOG}'\n" + inhoud + "\n",
                   encoding="utf-8", newline="\n")
    pad.chmod(0o755)


def log() -> list[str]:
    try:
        return LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def schoon_pad() -> str:
    """PATH zonder de echte BugOS-programma's (bugos-*, liveinst): op een BugOS-computer staan die in /usr/bin, en dan
    zou de test die vinden in plaats van zijn eigen nep-versies. Per map een schaduwmap met al het andere."""
    mappen = []
    for i, m in enumerate(p for p in os.environ.get("PATH", "").split(os.pathsep) if p):
        bron = Path(m)
        try:
            namen = [x.name for x in bron.iterdir()]
        except OSError:
            continue
        if not any(n.startswith("bugos-") or n in ("liveinst", "kdialog") for n in namen):
            mappen.append(m)
            continue
        schaduw = TMP / f"pad-{i}"
        schaduw.mkdir(exist_ok=True)
        for n in namen:
            if not (n.startswith("bugos-") or n in ("liveinst", "kdialog")):
                try:
                    (schaduw / n).symlink_to(bron / n)
                except OSError:
                    pass
        mappen.append(str(schaduw))
    return os.pathsep.join(mappen)


def laad(naam: str, pad: Path):
    lader = importlib.machinery.SourceFileLoader(naam, str(pad))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


def wacht(app, voorwaarde, seconden: float = 5.0) -> bool:
    eind = time.monotonic() + seconden
    while time.monotonic() < eind:
        app.processEvents()
        if voorwaarde():
            return True
        time.sleep(0.01)
    app.processEvents()
    return voorwaarde()


def bron(naam: str) -> str:
    return (SRC / naam).read_text(encoding="utf-8")


# ======================================================================================================== bugos-live ===
def test_live() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["LANG"] = os.environ["LC_ALL"] = "en_US.UTF-8"   # Engels: de standaardtaal van de stick
    os.environ.pop("LANGUAGE", None)
    os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD", None)
    sys.path.insert(0, str(PY))
    # nmcli: antwoord uit twee bestandjes, zodat elke test zijn eigen toestand kiest.
    (TMP / "conn").write_text("none\n", encoding="utf-8")
    (TMP / "types").write_text("ethernet\nloopback\n", encoding="utf-8")
    nep("nmcli", f'case "$*" in *CONNECTIVITY*) cat \'{TMP}/conn\' ;; *TYPE*) [ -f \'{TMP}/types-kapot\' ] && exit 8; '
                 f'cat \'{TMP}/types\' ;; esac')
    nep("bugos-settings", "exit 0")
    live = laad("bugos_live", SRC / "bugos-live")
    import bugos_ui

    app = bugos_ui.maak_app("bugos-live", "bugos-live", ["bugos-live"])

    # 21. 'Wifi kiezen' opent BugOS Instellingen op de wifi-pagina, niet KDE.
    w = live.Live()
    w.timer.stop()   # de test kiest zelf wanneer er gekeken wordt
    wacht(app, lambda: not w._bezig)
    gestart = []
    echt_popen = live.subprocess.Popen
    live.subprocess.Popen = lambda cmd, **kw: gestart.append((list(cmd), kw.get("start_new_session")))
    try:
        w.wifi.click()
    finally:
        live.subprocess.Popen = echt_popen
    klopt(gestart == [(["bugos-settings", "wifi"], True)],
          f"21: 'Choose Wi-Fi' opent bugos-settings wifi (in een eigen sessie) ({gestart})")
    for naam in ("bugos-live", "bugos-install", "build.sh"):
        tekst = bron(naam)
        klopt("systemsettings" not in tekst and "kcm_" not in tekst, f"21: {naam} opent geen KDE-instellingen")

    def stand(conn: str, types: str | None, kapot: bool = False) -> tuple[bool, str]:
        (TMP / "conn").write_text(conn + "\n", encoding="utf-8")
        if types is not None:
            (TMP / "types").write_text(types, encoding="utf-8")
        if kapot:
            (TMP / "types-kapot").write_text("", encoding="utf-8")
        else:
            (TMP / "types-kapot").unlink(missing_ok=True)
        w._wifi_gevraagd = float("-inf")   # opnieuw naar de wifi-kaart vragen
        w.kijk_internet()
        wacht(app, lambda: not w._bezig)
        return not w.wifi.isHidden(), w.chip.text()

    # 22. De knop staat er alleen zonder internet EN met een wifi-kaart.
    zicht, chip = stand("none", "ethernet\nloopback\n")
    klopt(not zicht and "No internet" in chip, f"22: geen internet, geen wifi-kaart (kabel-pc): geen wifi-knop ({chip})")
    zicht, _ = stand("none", "ethernet\nwifi\nloopback\n")
    klopt(zicht, "22: geen internet, wel een wifi-kaart: de knop 'Choose Wi-Fi' staat er")
    zicht, chip = stand("full", None)
    klopt(not zicht and "online" in chip, f"22: online: geen wifi-knop, de chip zegt 'You are online' ({chip})")
    zicht, _ = stand("none", "ethernet\n", kapot=True)
    klopt(zicht, "22: nmcli kan de apparaten niet noemen: de knop staat er (Instellingen legt het verder uit)")
    # I7: niet elke 3 s twee keer nmcli in de GUI-draad: de wifi-kaart wordt hooguit elke 30 s gevraagd.
    stand("none", "wifi\n")
    voor = sum(1 for r in log() if "TYPE" in r)
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    na = sum(1 for r in log() if "TYPE" in r)
    klopt(voor >= 1 and na == voor, f"22: de wifi-kaart wordt niet elke 3 s opnieuw gevraagd ({voor} -> {na})")
    nep("nmcli", "sleep 3; echo full")
    begin = time.monotonic()
    w._wifi_gevraagd = float("-inf")
    w.kijk_internet()
    duur = time.monotonic() - begin
    klopt(duur < 0.5, f"22: een trage nmcli laat het venster niet vastlopen ({duur:.2f} s)")
    wacht(app, lambda: not w._bezig, 8)
    w.close()


# ===================================================================================== woorden (bugos_webui.py) ===
PO_NL = ('cockpit.locale({\n "": {\n  "plural-forms": (n) => n != 1,\n  "language": "nl",\n  "language-direction": "ltr"\n'
         ' },\n "Use entire disk": [\n  null,\n  "Gebruik gehele schijf"\n ],\n "Passphrase": [\n  null,\n  "Wachtzin"\n ]\n});\n')


def po_woord(tekst: str, sleutel: str) -> str | None:
    """De vertaling die cockpit gebruikt: de LAATSTE keer dat de sleutel in het bestand staat."""
    import json
    i = tekst.rfind(json.dumps(sleutel, ensure_ascii=False) + ": [")
    if i < 0:
        return None
    rest = tekst[i + len(json.dumps(sleutel, ensure_ascii=False)) + 2:]
    lijst = json.JSONDecoder().raw_decode(rest)[0]
    return lijst[1]


def test_woorden() -> None:
    import gzip
    import json
    import re

    w = laad("bugos_webui", SRC / "bugos_webui.py")
    W = w.WOORDEN
    # 11. Gewone woorden: elk paar is ingevuld, zonder vakjargon, en Nederlands is echt vertaald.
    klopt(all(isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, str) and x.strip() for x in v)
              for v in W.values()), "11: elke regel heeft een Engelse en een Nederlandse tekst")
    jargon = [(k, v) for k, v in W.items() for x in v
              if re.search(r"fedora|passphrase|partition|storage", x, re.IGNORECASE)]
    klopt(not jargon, f"11: geen 'Fedora', 'passphrase', 'partition' of 'storage' in de nieuwe woorden ({jargon[:2]})")
    gelijk = [k for k, (en, nl) in W.items() if en == nl]
    klopt(not gelijk, f"11: het Nederlands verschilt overal van het Engels ({gelijk})")
    # Een $0 in de tekst moet ook in de sleutel staan; weglaten mag (review I4: 'To begin using $0 ...').
    plek = [(k, x) for k, v in W.items() for x in v if not set(re.findall(r"\$\d", x)) <= set(re.findall(r"\$\d", k))]
    klopt(not plek, f"11: geen $0/$1 in een tekst die niet in de sleutel staat ({plek})")
    klopt("$0" not in "".join(W["To begin using $0, reboot your system."]) and
          all("$0" in x for x in W["Must be at least $0 characters"]),
          "11: '$0' weglaten mag (klaar-zin), meenemen ook (minstens $0 tekens)")
    nodig = ("Passphrase", "Use entire disk", "Erase data and install", "Review and install", "Storage configuration",
             "Exit to live desktop", "Remove all partitions on the selected devices, including existing operating systems.")
    klopt(all(k in W for k in nodig), "11: de woorden van de eigenaar staan erin (Passphrase, Use entire disk, ...)")
    en_k, nl_k = W["To begin using $0, reboot your system."]
    klopt("restart" in en_k and "USB" in en_k and "opnieuw" in nl_k and "USB" in nl_k,
          "11 (I5): het laatste scherm zegt zelf dat je opnieuw moet opstarten en de stick eruit haalt")
    en_w, nl_w = W["Remove all partitions on the selected devices, including existing operating systems."]
    klopt("if it is there" in en_w and "als dat erop staat" in nl_w,
          "11 (I12): de waarschuwing doet niet alsof er altijd Windows op staat")

    # 12. Een heel Engels woordenboek in cockpit-vorm.
    po = w.po_engels()
    klopt(po.startswith("cockpit.locale(") and po.endswith(");\n"), "12: po_engels() is cockpit.locale(...);")
    data = json.loads(po[len("cockpit.locale("):-len(");\n")])
    klopt(data[""]["language"] == "en_US" and data["Passphrase"] == [None, "Password"],
          "12: kop en_US, en 'Passphrase' wordt 'Password'")
    klopt(json.loads(w.po_engels("en_AU")[15:-3])[""]["language"] == "en_AU", "12: een kopie per Engelse taal (en_AU)")

    # 13. Achteraan erbij: de laatste sleutel telt.
    uit = w.achter_aan(PO_NL, 1)
    klopt(po_woord(uit, "Use entire disk") == "De hele schijf gebruiken" and po_woord(uit, "Passphrase") == "Wachtwoord",
          f"13: in po.nl wint ons woord ({po_woord(uit, 'Use entire disk')})")
    klopt(uit.startswith(PO_NL[:PO_NL.rfind("\n});")]) and uit.endswith("\n});\n"),
          "13: het bestaande woordenboek blijft heel, het einde ook")
    try:
        w.achter_aan("cockpit.locale({});", 1)
        klopt(False, "13: een po-bestand zonder '\\n});' stopt het bouwen")
    except AssertionError:
        klopt(True, "13: een po-bestand zonder '\\n});' stopt het bouwen")

    # 14. schrijf(): nieuwe Engelse bestanden, en achteraan bij de bestaande.
    m = TMP / "webui"
    m.mkdir()
    en_gb = PO_NL.replace('"nl"', '"en_GB"').replace("Gebruik gehele schijf", "Use entire disk")
    for naam, tekst in (("po.en_GB.js.gz", en_gb), ("po.nl.js.gz", PO_NL)):
        with gzip.open(m / naam, "wt", encoding="utf-8") as f:
            f.write(tekst)
    w.schrijf(str(m), ["en_US", "en_GB", "en_AU"])
    lees = {p.name: gzip.open(p, "rt", encoding="utf-8").read() for p in m.glob("*.gz")}
    klopt(sorted(lees) == ["po.en_AU.js.gz", "po.en_GB.js.gz", "po.en_US.js.gz", "po.nl.js.gz"] and not list(m.glob("*.nieuw")),
          f"14: po.en_US en po.en_AU erbij, en_GB en nl bijgewerkt, niets half achtergelaten ({sorted(lees)})")
    klopt('"language": "en_AU"' in lees["po.en_AU.js.gz"] and po_woord(lees["po.en_AU.js.gz"], "Exit to live desktop") == "Finish",
          "14: po.en_AU heeft zijn eigen taal en de Engelse woorden")
    klopt(po_woord(lees["po.en_GB.js.gz"], "Use entire disk") == "Use the whole disk" and '"en_GB"' in lees["po.en_GB.js.gz"],
          "14: po.en_GB (bestond al) krijgt onze woorden achteraan")
    klopt(po_woord(lees["po.nl.js.gz"], "Exit to live desktop") == "Afronden", "14: po.nl: 'Exit to live desktop' wordt 'Afronden'")
    try:
        w.schrijf(str(m), ["en_US;rm"])
        klopt(False, "14: een rare taalnaam wordt geweigerd")
    except AssertionError:
        klopt(True, "14: een rare taalnaam wordt geweigerd")
    # build.sh roept het aan NA de Nederlandse regels (zodat onze woorden het laatst komen) en geeft geen talen mee
    # zonder aanhalingstekens (shellcheck SC2086, review I3).
    bouw = bron("build.sh")
    roep = bouw.find('python3 "$SRC/bugos_webui.py"')
    klopt(roep > bouw.find("BugOS requires at least $0 of disk space.") > 0 and "$ENGELS" not in bouw,
          "14: build.sh zet de woorden na de bestaande Nederlandse regels")


# =================================================================================== tijdzone (bugos_webui.py) ===
# Echte stukjes uit index.js van anaconda-webui 68 (letterlijk overgenomen).
JS_ZET = 'LU=()=>o0("Timezone"),lx=({timezone:t})=>pb("SetTimezoneWithPriority",[t,90]);var ZU=()=>pb("GetAllValidTimezones");'
JS_VAK = ('var yg=Y.gettext,na="anaconda-screen-date-time",y3=({locale:t,setSectionValid:e,setTimezoneLabel:o})=>{'
          'let[r,l]=(0,oe.useState)(!0),[a,n]=(0,oe.useState)(!1),[i,c]=(0,oe.useState)(!1);return null};')
ZONE_TAB = ("# tzdb timezone descriptions\n#\n"
            "NL\t+5222+00454\tEurope/Amsterdam\n"
            "DE\t+5230+01322\tEurope/Berlin\tmost of Germany\n"
            "DE\t+4742+00841\tEurope/Busingen\tBusingen\n"
            "ES\t+4024-00341\tEurope/Madrid\tSpain (mainland)\n"
            "ES\t+2806-01524\tAtlantic/Canary\tCanary Islands\n"
            "kapotte regel zonder tabs\n"
            "XX\tgeen\n")
VERSCHUIVING = {"Europe/Amsterdam": (1, 2), "Europe/Berlin": (1, 2), "Europe/Busingen": (1, 2),
                "Europe/Madrid": (1, 2), "Atlantic/Canary": (0, 1)}


def test_tijdzone() -> None:
    import json
    import re

    w = sys.modules.get("bugos_webui") or laad("bugos_webui", SRC / "bugos_webui.py")
    fixture = JS_ZET + JS_VAK
    # 7. Het vinkje start uit, er komt één gok bij elke taal, de rest blijft heel.
    uit = w.tijdzone(fixture, {"NL": "Europe/Amsterdam"})
    klopt("useState)(!1),bugosTzKlaar=(0,oe.useEffect)(()=>{bugosTzGok(t)},[t]),[a,n]" in uit,
          "7: het vinkje 'automatisch' start uit, en de gok draait bij elke taal (zelfde hook-volgorde)")
    klopt('pb("SetTimezoneWithPriority",[z,30])' in uit and uit.count("[t,90]") == 1,
          "7: de gok gebruikt de D-Bus-aanroep van de pagina met prioriteit 30; jouw eigen keuze (90) blijft")
    klopt('{"NL":"Europe/Amsterdam"}' in uit and 'o0("Timezone")' in uit and "useState)(!0),[a,n]" not in uit,
          "7: de tabel staat erin, de D-Bus-naam 'Timezone' is niet aangeraakt, niets meer op (!0)")
    # 8. Twee keer, of een andere versie van het installatieprogramma: het bouwen stopt.
    for naam, js in (("twee keer", uit), ("zonder SetTimezone", JS_VAK), ("zonder het vak", JS_ZET),
                     ("SetTimezone twee keer", JS_ZET + JS_ZET + JS_VAK)):
        try:
            w.tijdzone(js, {"NL": "Europe/Amsterdam"})
            klopt(False, f"8: {naam}: het bouwen stopt (AssertionError)")
        except AssertionError:
            klopt(True, f"8: {naam}: het bouwen stopt (AssertionError)")
    # 9. Alleen landen waar elke zone dezelfde tijd heeft.
    landen = w.landen_met_een_zone(ZONE_TAB, verschuiving=lambda z: VERSCHUIVING[z])
    klopt(landen == {"DE": "Europe/Berlin", "NL": "Europe/Amsterdam"},
          f"9: NL en DE (Berlin en Busingen lopen gelijk) wel, ES (Canarische eilanden) niet ({landen})")
    tabel = w.tijdzone_tabel(ZONE_TAB, geldig={"Europe/Amsterdam", "Europe/Madrid"}, verschuiving=lambda z: VERSCHUIVING[z])
    klopt(tabel == {"ES": "Europe/Madrid", "NL": "Europe/Amsterdam"},
          f"9 (I9): Spanje krijgt het vasteland; wat Anaconda niet kent valt eruit ({tabel})")
    klopt(set(w.VOORKEUR) == {"ES", "PT", "NZ", "UA", "CN", "CL", "EC"} and not {"US", "CA", "AU", "BR", "RU", "MX", "ID"} & set(w.VOORKEUR),
          "9 (I9): geen gok voor landen zonder een zone die voor bijna iedereen klopt (VS, Canada, ...)")
    # 10. Niets uit de tabel kan uit de JavaScript-string breken.
    try:
        w.tijdzone(fixture, {"NL": 'Europe/A"});alert(1);//'})
        klopt(False, "10: een rare zone in de tabel wordt geweigerd")
    except AssertionError:
        klopt(True, "10: een rare zone in de tabel wordt geweigerd")
    stuk = uit[uit.index("bugosTzLanden=") + len("bugosTzLanden="):uit.index(";function bugosTzGok")]
    klopt(json.loads(stuk) == {"NL": "Europe/Amsterdam"} and "</" not in uit, "10: de tabel is gewone JSON")
    gok = re.search(r"/\^\[a-z\]\{2,3\}-\(\[a-z\]\{2\}\)\(\?!\[a-z0-9\]\)/", uit)
    klopt(gok is not None, "10: alleen het land na de taal telt ('nl-nl' -> NL; 'en' of 'de' -> geen gok)")
    # De taal -> land-regel, nagedaan in Python (dezelfde reguliere expressie als in de JavaScript).
    regel = re.compile(r"^[a-z]{2,3}-([a-z]{2})(?![a-z0-9])")
    land = {x: (regel.match(x).group(1).upper() if regel.match(x) else None)
            for x in ("nl-nl", "en-us", "en", "de", "sr-rs@latin", "zh-cn", "ast-es", "nl-nlx")}
    klopt(land == {"nl-nl": "NL", "en-us": "US", "en": None, "de": None, "sr-rs@latin": "RS", "zh-cn": "CN",
                   "ast-es": "ES", "nl-nlx": None}, f"10: taal -> land ({land})")

    # CSS in build.sh: het vinkje en 'NTP' weg, de lijsten niet meer ingesprongen, en een zin om het na te kijken.
    bouw = bron("build.sh")
    css = bouw[bouw.index('cat >"$BRANDING/branding.css"'):]
    css = css[:css.index("\nEOF")]
    klopt("#anaconda-screen-date-time-auto-timezone" in css and "#anaconda-screen-date-time-configure-ntp" in css,
          "A: CSS verbergt het vinkje 'tijdzone automatisch' en 'Configure NTP servers'")
    klopt(re.search(r"__indent:has\(#anaconda-screen-date-time-region-toggle\) \{\s*margin-inline-start: 0;", css) is not None,
          "A (I8): de keuzelijsten springen niet meer in onder een verborgen vinkje")
    klopt("Is this where you live?" in css and "Woon je hier?" in css and "html:lang(nl)" in css,
          "A (I2): onder de keuzelijsten staat in het Engels en Nederlands dat je het moet nakijken")
    klopt("use_geolocation = False" in bouw and "geolocation_provider =\n" in bouw.replace("\r\n", "\n"),
          "A: plaatsbepaling blijft uit (niets wordt op internet gevraagd)")
    klopt(css.count("{") == css.count("}"), "A: de CSS is heel (evenveel { als })")


# =================================================================== --beeld: in de echte live-image (geen ISO nodig) ===
WEBUI = Path("/usr/share/cockpit/anaconda-webui")


def beeld_woorden(w) -> None:
    import gzip
    import json
    from cockpit import packages

    js = gzip.open(WEBUI / "index.js.gz", "rt", encoding="utf-8").read()
    weg = [k for k in w.WOORDEN if json.dumps(k) not in js]
    klopt(not weg, f"beeld: elke sleutel van WOORDEN staat in de echte index.js ({weg})")
    kopie = Path("/tmp/installer-woorden")
    shutil.rmtree(kopie, ignore_errors=True)
    shutil.copytree(WEBUI, kopie / "anaconda-webui")
    d = kopie / "anaconda-webui"
    klopt(w.main([str(d)]) == 0, "beeld: bugos_webui.py draait zoals build.sh het aanroept (talen van Anaconda zelf)")
    pakket = packages.Package(packages.Manifest(d, json.loads((d / "manifest.json").read_text())))
    for al, sleutel, verwacht in (("en-us", "Passphrase", "Password"), ("en-US,en;q=0.5", "Exit to live desktop", "Finish"),
                                  ("en-au", "Passphrase", "Password"), ("en-gb", "Use entire disk", "Use the whole disk"),
                                  ("nl-nl", "Passphrase", "Wachtwoord"), ("nl-nl", "Exit to live desktop", "Afronden")):
        doc = pakket.load_path("po.js", {"Accept-Language": al})
        ruw = doc.data.read()
        tekst = gzip.decompress(ruw).decode() if ruw[:2] == b"\x1f\x8b" else ruw.decode()
        klopt(po_woord(tekst, sleutel) == verwacht, f"beeld: cockpit geeft bij {al!r} voor {sleutel!r}: {po_woord(tekst, sleutel)!r}")
    de = gzip.decompress(pakket.load_path("po.js", {"Accept-Language": "de-de"}).data.read()).decode()
    klopt(po_woord(de, "Passphrase") not in (None, "Password"), "beeld: Duits houdt zijn eigen vertaling")
    shutil.rmtree(kopie, ignore_errors=True)


def eerste_pixel(png: Path) -> tuple[int, int, int] | None:
    """De kleur van het eerste pixel van een PNG, in gewone Python (geen Pillow in de image). Voor elk PNG-filter is
    het eerste pixel van de eerste rij gewoon de echte kleur (links en boven is nul)."""
    import struct
    import zlib
    try:
        data = png.read_bytes()
    except OSError:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i, idat, kleur_type = 8, b"", None
    while i < len(data):
        lengte, soort = struct.unpack(">I4s", data[i:i + 8])
        stuk = data[i + 8:i + 8 + lengte]
        if soort == b"IHDR":
            kleur_type = stuk[9]
        elif soort == b"IDAT":
            idat += stuk
        i += 12 + lengte
    ruw = zlib.decompressobj().decompress(idat, 8)
    if kleur_type not in (2, 6) or len(ruw) < 4:
        return None
    return ruw[1], ruw[2], ruw[3]


def firefox(html: str, naam: str) -> tuple[tuple[int, int, int] | None, Path]:
    """Open een pagina in Firefox zonder scherm en maak een foto (de manier die in de live-image werkt)."""
    m = Path("/tmp/installer-t")
    (m / "home").mkdir(parents=True, exist_ok=True)
    (m / f"{naam}.html").write_text(html, encoding="utf-8")
    png = m / f"{naam}.png"
    png.unlink(missing_ok=True)
    env = dict(os.environ, MOZ_HEADLESS="1", HOME=str(m / "home"))
    subprocess.run(["timeout", "90", "firefox", "--headless", "--window-size=1100,560", "--screenshot", str(png),
                    f"file://{m / naam}.html"], env=env, capture_output=True, check=False)
    return eerste_pixel(png), png


GROEN, ROOD = (0, 255, 0), (255, 0, 0)


def syntax_pagina(js: str) -> str:
    import json
    s = json.dumps(js).replace("</", "<\\/")
    return ('<!doctype html><body style="margin:0"><script>var s=' + s + ';try{new Function(s);'
            'document.body.style.background="#00ff00"}catch(e){document.body.style.background="#ff0000"}</script>')


def beeld_tijdzone(w) -> None:
    import gzip
    import json

    js = gzip.open(WEBUI / "index.js.gz", "rt", encoding="utf-8").read()
    klopt(len(w.R_ZET.findall(js)) == 1 and len(w.R_VAK.findall(js)) == 1, "beeld: beide ankers staan precies één keer in index.js")
    zone_tab = Path("/usr/share/zoneinfo/zone.tab").read_text(encoding="utf-8")
    geldig = w.geldige_zones()
    tabel = w.tijdzone_tabel(zone_tab, geldig)
    klopt(len(tabel) >= 200 and tabel.get("NL") == "Europe/Amsterdam" and tabel.get("BE") == "Europe/Brussels"
          and tabel.get("DE") == "Europe/Berlin" and tabel.get("ES") == "Europe/Madrid" and "US" not in tabel,
          f"beeld: echte zone.tab: {len(tabel)} landen, NL Amsterdam, BE Brussel, DE Berlijn, ES Madrid, VS niet")
    klopt(all(z in geldig for z in tabel.values()) and all(z in geldig for z in w.VOORKEUR.values()),
          "beeld: elke zone uit de tabel staat in de keuzelijsten van Anaconda (ook Europe/Kyiv)")
    uit = w.tijdzone(js, tabel)
    print(f"      (index.js +{len(uit) - len(js)} tekens)")
    kleur, _ = firefox(syntax_pagina(uit), "syntax")
    klopt(kleur == GROEN, f"beeld: Firefox leest de aangepaste index.js zonder fout ({kleur})")
    kleur, _ = firefox(syntax_pagina(uit + "let let;"), "syntax-kapot")
    klopt(kleur == ROOD, f"beeld: tegenproef: een kapotte index.js geeft rood ({kleur})")

    # Draait de gok echt? De aangepaste stukjes met een nep-D-Bus (pb) en een nep-React (oe), in Firefox.
    proef = w.tijdzone("var Y={gettext:0};var roep=[];var pb=(m,a)=>{roep.push(a);return Promise.reject(1)};"
                       + JS_ZET + JS_VAK.replace("return null", "return r"), tabel)
    test = ("var oe={useState:(v)=>[v,()=>0],useEffect:(f,d)=>{f();return void 0}};var uit=[];"
            "for(const t of ['nl-nl','en-us','en','de-de','sr-rs@latin']){roep=[];var vink=y3({locale:t});"
            "uit.push(t+'='+(roep.length?roep[0][0]+'@'+roep[0][1]:'-')+(vink?'+vink':''));}"
            "var goed=uit.join(' ')==" + json.dumps("nl-nl=Europe/Amsterdam@30 en-us=- en=- de-de=Europe/Berlin@30 "
                                                     "sr-rs@latin=Europe/Belgrade@30") + ";")
    html = ('<!doctype html><body style="margin:0"><script>try{' + proof_js(proef, test) + '}catch(e){'
            'document.body.style.background="#ff0000";document.body.textContent=String(e)}</script>')
    kleur, _ = firefox(html, "gok")
    klopt(kleur == GROEN, f"beeld: in Firefox: nl-nl -> Amsterdam (30), de-de -> Berlijn, en-us -> niets, vinkje uit ({kleur})")

    # De CSS: het echte index.css van het installatieprogramma + onze branding.css, op dezelfde opbouw als de pagina.
    bouw = bron("build.sh").replace("\r\n", "\n")
    css = bouw[bouw.index("<<'EOF'\n", bouw.index('cat >"$BRANDING/branding.css"')) + 8:]
    css = css[:css.index("\nEOF\n")]
    m = Path("/tmp/installer-t")
    (m / "index.css").write_text(gzip.open(WEBUI / "index.css.gz", "rt", encoding="utf-8").read(), encoding="utf-8")
    (m / "branding.css").write_text(css, encoding="utf-8")
    html = CSS_PAGINA.replace("@VERWACHT@", json.dumps({
        "en": ["none", "0px", "Is this where you live? If not, choose your region and city.", "none"],
        "nl": ["none", "0px", "Woon je hier? Zo niet, kies dan je regio en je stad.", "none"],
        "de": ["none", "0px", "", "none"]}))
    kleur, png = firefox(html, "css")
    klopt(kleur == GROEN, f"beeld: CSS: vinkje en NTP weg, lijsten niet ingesprongen, de zin in en/nl, niet in de ({kleur}, {png})")


def proof_js(proef: str, test: str) -> str:
    return (proef + test + 'document.body.style.background=goed?"#00ff00":"#ff0000";'
            'document.body.textContent=uit.join(" ");')


# Dezelfde opbouw als de pagina 'Datum en tijd' (Timezone.jsx + PatternFly: StackItem > Flex > FlexItem > Checkbox).
CSS_PAGINA = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<link rel="stylesheet" href="index.css"><link rel="stylesheet" href="branding.css"></head>
<body style="margin:0"><div id="kleur" style="height:24px"></div><div class="anaconda" style="padding:24px">
<h2>Time zone</h2>
<div class="pf-v6-l-stack pf-m-gutter">
 <div class="pf-v6-l-stack__item" id="vinkrij"><div class="pf-v6-l-flex pf-m-align-items-center"><div>
  <div class="pf-v6-c-check"><input class="pf-v6-c-check__input" type="checkbox" id="anaconda-screen-date-time-auto-timezone">
  <label class="pf-v6-c-check__label">Automatically set timezone</label></div></div></div></div>
 <div class="pf-v6-l-stack__item"><div class="pf-v6-l-flex pf-m-align-items-center anaconda-screen-date-time__indent" id="rij">
  <div><button class="pf-v6-c-menu-toggle" id="anaconda-screen-date-time-region-toggle">Europe</button></div>
  <div><button class="pf-v6-c-menu-toggle" id="anaconda-screen-date-time-city-toggle">Amsterdam</button></div>
  <div><span class="anaconda-screen-date-time__timezone-label">CET, UTC+1</span></div></div></div>
</div>
<div class="pf-v6-l-flex"><div><button class="pf-v6-c-button pf-m-link" id="anaconda-screen-date-time-configure-ntp">Configure NTP servers</button></div></div>
<p id="uitslag"></p></div>
<script>
var verwacht=@VERWACHT@, uit=[], goed=true;
for (const taal of ["en","nl","de"]) {
  document.documentElement.lang = taal;
  const na = getComputedStyle(document.getElementById("rij"), "::after").content;
  const tekst = (na === "none" || na === "normal") ? "" : JSON.parse(na);
  const r = [getComputedStyle(document.getElementById("vinkrij")).display,
             getComputedStyle(document.getElementById("rij")).marginInlineStart, tekst,
             getComputedStyle(document.getElementById("anaconda-screen-date-time-configure-ntp")).display];
  uit.push(taal + ": " + JSON.stringify(r));
  if (JSON.stringify(r) !== JSON.stringify(verwacht[taal])) goed = false;
}
document.documentElement.lang = "en";
document.getElementById("kleur").style.background = goed ? "#00ff00" : "#ff0000";
document.getElementById("uitslag").textContent = uit.join(" | ");
</script></body></html>"""


def beeld() -> int:
    if not WEBUI.is_dir():
        print("--beeld draait alleen in de live-image (localhost/bugos-live:lokaal)")
        return 2
    w = laad("bugos_webui", SRC / "bugos_webui.py")
    beeld_woorden(w)
    beeld_tijdzone(w)
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


def main() -> int:
    if BEELD:
        return beeld()
    os.environ["PATH"] = str(NEP) + os.pathsep + schoon_pad()
    test_woorden()
    test_tijdzone()
    test_live()
    shutil.rmtree(TMP, ignore_errors=True)
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
