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


def leeft(pid: int) -> bool:
    """Draait dit proces nog? Een zombie telt als weg: die is gestopt, alleen nog niet opgeruimd door zijn ouder.
    (os.kill(pid, 0) zou een zombie nog als levend zien.)"""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # Na de naam tussen haakjes (die zelf spaties of haakjes kan hebben) komt de toestand: R, S, Z ...
    return stat.rsplit(")", 1)[-1].split()[:1] != ["Z"]


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
    nep("nmcli", f'[ -f \'{TMP}/traag\' ] && sleep 1; case "$*" in *CONNECTIVITY*) cat \'{TMP}/conn\' ;; *TYPE*) [ -f \'{TMP}/types-kapot\' ] && exit 8; '
                 f'cat \'{TMP}/types\' ;; esac')
    nep("bugos-settings", "exit 0")
    live = laad("bugos_live", SRC / "bugos-live")
    import bugos_ui

    app = bugos_ui.maak_app("bugos-live", "bugos-live", ["bugos-live"])

    # 22. Vóór het eerste antwoord van nmcli: geen 'geen internet' en geen wifi-knop (een online pc met een kabel zag
    # anders even het verkeerde), daarna wel de echte toestand (hier: offline, met een wifi-kaart).
    (TMP / "types").write_text("ethernet\nwifi\n", encoding="utf-8")
    (TMP / "traag").write_text("", encoding="utf-8")
    w0 = live.Live()   # een eigen naam: dit venster mag Python niet halverwege de test opruimen (dat liet Qt vallen)
    w0.timer.stop()
    w0.show()
    app.processEvents()
    klopt(w0.wifi.isHidden() and "Checking" in w0.chip.text() and "No internet" not in w0.chip.text(),
          f"22: vóór het eerste antwoord: geen wifi-knop, de chip zegt 'Checking the internet…' ({w0.chip.text()})")
    (TMP / "traag").unlink()
    wacht(app, lambda: not w0._bezig, 8)
    klopt(not w0.wifi.isHidden() and "No internet" in w0.chip.text(),
          f"22: na het eerste antwoord: offline met een wifi-kaart, de knop staat er ({w0.chip.text()})")
    w0.close()
    (TMP / "types").write_text("ethernet\nloopback\n", encoding="utf-8")

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
    # 21. Gaat Instellingen niet open, dan blijft de uitleg staan, ook na de volgende keer kijken (elke 3 s).
    def kapot(_cmd, **_kw):
        raise OSError(2, "No such file or directory")
    (TMP / "types").write_text("wifi\n", encoding="utf-8")
    w._wifi_gevraagd = float("-inf")
    live.subprocess.Popen = kapot
    try:
        w.wifi.click()
    finally:
        live.subprocess.Popen = echt_popen
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    klopt(not w.wifi_fout.isHidden() and "network icon" in w.wifi_fout.text() and "No internet" in w.chip.text(),
          f"21: Instellingen gaat niet open: de uitleg blijft staan na een nieuwe ronde ({w.wifi_fout.text()})")
    klopt("Errno" not in w.wifi_fout.text() and "No such file" not in w.wifi_fout.text(), "21: geen ruwe foutmelding")
    (TMP / "conn").write_text("full\n", encoding="utf-8")
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    klopt(w.wifi_fout.isHidden(), "21: online: de uitleg over wifi is weg")
    (TMP / "conn").write_text("none\n", encoding="utf-8")
    (TMP / "types").write_text("ethernet\nloopback\n", encoding="utf-8")
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
    test_klaar(app, live)
    test_start(app, live)


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
    # 11 (b). 'De schijf delen' (de standaard zodra er iets op de schijf staat), het venster om ruimte te maken en
    # 'Datum en tijd': die zinnen waren stijf Nederlands met 'u' en vakwoorden. Dat elke sleutel letterlijk in de
    # echte index.js staat, kijkt --beeld na (op een computer zonder image kan dat niet).
    schijf = ("Share disk with other operating systems", "Share disk with other operating systems: $0",
              "Keep current disk layout and use available space, to dual-boot with another OS.",
              "Not enough free space on the selected disks.",
              "To use this option, resize or remove existing partitions to free up at least $0.",
              "Reclaim space (required)", "Reclaim additional space", "Mount point assignment",
              "Assign partitions to mount points. Useful for pre-configured custom layouts.",
              "Apply mount point assignment and install", "Reclaim space",
              "Remove or resize existing filesystems to free up space for the installation.",
              "Available free space: $0. Installation requires: $1.", "Resize", "shrink", "shrink to $0",
              "Windows partitions with BitLocker encryption cannot be resized", "Not enough space on selected disks.",
              "The installation needs $0 of disk space; however, the capacity of the selected disks is only $1.",
              "Show AM/PM", "You must be connected to a network to enable automatic date and time.")
    klopt(all(k in W for k in schijf),
          f"11 (b): de zinnen van 'De schijf delen', 'Ruimte maken' en 'Datum en tijd' staan erin "
          f"({[k for k in schijf if k not in W]})")
    # Nederlands met 'je', nooit 'u' of 'uw' (Anaconda's eigen Nederlands zei 'verandert u de grootte ...').
    formeel = [nl for _en, nl in W.values() if re.search(r"\b(u|uw)\b", nl, re.IGNORECASE)]
    klopt(not formeel, f"11 (b): Nederlands met 'je', nergens 'u' of 'uw' ({formeel[:2]})")
    # Geen vakwoorden die Anaconda gebruikte (in beide talen): de regel hierboven vangt 'partition' en 'storage' al.
    vak = [x for v in W.values() for x in v
           if re.search(r"partitie|aankoppel|terugvorder|bestandssyste|mount point|filesystem|dual-boot|reclaim|\bOS\b",
                        x, re.IGNORECASE)]
    klopt(not vak, f"11 (b): geen aankoppelpunten, bestandssystemen, dual-booten of 'terugvorderen' ({vak[:2]})")
    # Elke $0/$1 uit de sleutel komt terug, in dezelfde volgorde (cockpit zet er de getallen of vette stukjes in).
    # Alleen bij de klaar-zin laten we $0 bewust weg (review I4: de naam van het systeem is daar niet nodig).
    weglaten = {"To begin using $0, reboot your system."}
    kwijt = [(k, x) for k, v in W.items() if k not in weglaten for x in v
             if re.findall(r"\$\d", x) != re.findall(r"\$\d", k)]
    klopt(not kwijt, f"11 (b): elke $0/$1 van de sleutel staat ook in de tekst, in dezelfde volgorde ({kwijt[:1]})")
    en_r, nl_r = W["Removing a filesystem will permanently delete all of the data it contains. Resizing a partition "
                   "can free up unused space, but is not risk-free. Be sure to have backups of anything important "
                   "before reclaiming space."]
    klopt("Install" in en_r and "Installeren" in nl_r and "USB" in en_r and "USB" in nl_r,
          "11 (b): 'Ruimte maken' zegt dat er pas iets verandert bij Installeren, en waar je eerst een kopie zet")
    # Die zin klopt alleen als de laatste knop bij 'De schijf delen' ook echt Installeren heet: dat is Anaconda's eigen
    # 'Install' (getButtonLabel), dus die mag niet in WOORDEN een andere naam krijgen.
    klopt("Install" not in W, "11 (b): de knop 'Install' houdt zijn naam (de uitleg in 'Ruimte maken' noemt hem)")

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
    # 'De schijf delen' staat alleen nog in WOORDEN (met Engels erbij), niet ook nog in de Nederlandse lijst van build.sh.
    klopt('"Share disk with other operating systems' not in bouw,
          "14: 'Share disk ...' heeft één bron (WOORDEN), niet ook nog een regel in build.sh")

    # 27. Engels vanaf de eerste pagina. slitherer (het venster van het installatieprogramma) stuurt geen
    # Accept-Language mee, dus cockpit gaf een lege po.js: onze Engelse woorden kwamen pas als je zelf een taal
    # aanklikte. index.html laadt nu eerst bugos-en.js (na index.js, vóór po.js).
    html = w.html_engels(INDEX_HTML)
    regels = [r.strip() for r in html.splitlines()]
    klopt(regels.index('<script type="text/javascript" src="index.js"></script>')
          < regels.index('<script type="text/javascript" src="bugos-en.js"></script>')
          < regels.index('<script type="text/javascript" src="po.js"></script>'),
          "27: index.html laadt bugos-en.js na index.js (daar zit cockpit in) en vóór po.js (een echt woordenboek wint)")
    klopt('\n    <script type="text/javascript" src="bugos-en.js"></script>\n' in html
          and html.replace('    <script type="text/javascript" src="bugos-en.js"></script>\n', "") == INDEX_HTML,
          "27: verder blijft index.html precies hetzelfde (zelfde inspringing)")
    for naam, kapot in (("twee keer", html), ("zonder po.js", INDEX_HTML.replace("po.js", "po-weg.js")),
                        ("po.js vóór index.js", INDEX_HTML.replace('src="index.js"', 'src="x.js"') + '<script src="index.js">')):
        try:
            w.html_engels(kapot)
            klopt(False, f"27: {naam}: het bouwen stopt (AssertionError)")
        except AssertionError:
            klopt(True, f"27: {naam}: het bouwen stopt (AssertionError)")
    # main() zoals build.sh hem aanroept (maar met --locales en --zone-tab: geen Anaconda op deze computer), op een
    # map met de echte vormen van de bestanden: alles in één keer, en bugos-en.js is hetzelfde als po.en_US.js.gz.
    m2 = TMP / "webui-main"
    m2.mkdir()
    with gzip.open(m2 / "index.js.gz", "wt", encoding="utf-8") as f:
        f.write(JS_KLOK + JS_ZET + JS_VAK)
    with gzip.open(m2 / "po.nl.js.gz", "wt", encoding="utf-8") as f:
        f.write(PO_NL)
    (m2 / "index.html").write_text(INDEX_HTML, encoding="utf-8", newline="\n")
    (TMP / "zone.tab").write_text(ZONE_TAB, encoding="utf-8", newline="\n")
    code = w.main([str(m2), "--locales", "en_US,en_GB", "--zone-tab", str(TMP / "zone.tab")])
    lees2 = {p.name: gzip.open(p, "rt", encoding="utf-8").read() for p in m2.glob("*.gz")}
    klopt(code == 0 and sorted(lees2) == ["bugos-en.js.gz", "index.js.gz", "po.en_GB.js.gz", "po.en_US.js.gz",
                                         "po.nl.js.gz"] and not list(m2.glob("*.nieuw")),
          f"27: main() maakt bugos-en.js.gz naast de po-bestanden, niets half achtergelaten ({sorted(lees2)})")
    klopt(lees2["bugos-en.js.gz"] == lees2["po.en_US.js.gz"] == w.po_engels("en_US")
          and "bugos-en.js" in (m2 / "index.html").read_text(encoding="utf-8"),
          "27: bugos-en.js heeft dezelfde Engelse woorden als po.en_US.js, en index.html laadt hem")
    klopt("bugosTzGok" in lees2["index.js.gz"] and JS_KLOK in lees2["index.js.gz"],
          "27: main() zet ook de tijdzonegok erin, en laat het klokvak (NTP) staan")


# =================================================================================== tijdzone (bugos_webui.py) ===
# Echte stukjes uit index.js van anaconda-webui 68 (letterlijk overgenomen).
JS_ZET = 'LU=()=>o0("Timezone"),lx=({timezone:t})=>pb("SetTimezoneWithPriority",[t,90]);var ZU=()=>pb("GetAllValidTimezones");'
JS_VAK = ('var yg=Y.gettext,na="anaconda-screen-date-time",y3=({locale:t,setSectionValid:e,setTimezoneLabel:o})=>{'
          'let[r,l]=(0,oe.useState)(!0),[a,n]=(0,oe.useState)(!1),[i,c]=(0,oe.useState)(!1);return null};')
# Het vak 'Date and time' erboven (ook letterlijk, ingekort tot het begin): hier is r het vinkje voor de klok (NTP).
# Het begint met useState(!0), maar de pagina zet het meteen naar wat Anaconda zegt (await uB() = NTPEnabled, standaard
# True). Dat vinkje moet blijven zoals het is: tijdzone() mag dit stuk niet aanraken (zie bugos_webui.py bovenaan).
JS_KLOK = ('var Cf=Y.gettext,wf="anaconda-screen-date-time",oq=({locale:t,setSectionValid:e,timezone:o})=>{'
           'let[r,l]=(0,te.useState)(!0),[a,n]=(0,te.useState)(!0),[i,c]=(0,te.useState)(Se.utc()),'
           's=(0,te.useContext)(Bn).connected,[d,p]=(0,te.useState)(()=>L3(t)?"24":"ampm");'
           '(0,te.useEffect)(()=>{(async()=>{let W=await uB();l(!!W);let X=await xB();'
           'X&&c(Se.fromISO(X,{zone:"utc"}).setZone(o))})()},[o]);return null};'
           'var uB=()=>o0("NTPEnabled"),hB=({enabled:t})=>vB("NTPEnabled",Y.variant("b",t));')
# Het begin van de echte index.html van anaconda-webui 68 (met de titel die build.sh erin zet).
INDEX_HTML = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n    <title>Install BugOS</title>\n    <meta charset="utf-8">\n'
              '    <link rel="stylesheet" href="index.css">\n    <link rel="stylesheet" href="../../static/branding.css">\n\n'
              '    <script type="text/javascript" src="index.js"></script>\n'
              '    <script type="text/javascript" src="po.js"></script>\n</head>\n\n'
              '<body class="pf-m-redhat-font anaconda">\n    <div class="ct-page-fill" id="app"></div>\n</body>\n</html>\n')
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
    # 7 (a). Het vinkje 'De klok vanzelf gelijkzetten' (NTP) is een ander vinkje: dat staat aan omdat Anaconda het zo
    # zegt (NTPEnabled is standaard True), en dat laten we zo. tijdzone() raakt het vak 'Date and time' niet aan.
    met_klok = w.tijdzone(JS_KLOK + fixture, {"NL": "Europe/Amsterdam"})
    klopt(met_klok.startswith(JS_KLOK) and met_klok.count("useState)(!1),bugosTzKlaar") == 1
          and not w.R_VAK.search(JS_KLOK),
          "7 (a): het klokvak (NTP, leest NTPEnabled) blijft precies zoals het was; alleen het tijdzonevak verandert")
    # 7 (b). Terugdraaien (voor --beeld, waar index.js al aangepast is): ontdoe_tijdzone(tijdzone(x)) is weer x.
    klopt(w.ontdoe_tijdzone(uit) == fixture and w.ontdoe_tijdzone(met_klok) == JS_KLOK + fixture
          and w.ingebouwde_tabel(uit) == {"NL": "Europe/Amsterdam"},
          "7 (b): ontdoe_tijdzone draait tijdzone() precies terug, en ingebouwde_tabel leest de tabel terug")
    for naam, js in (("niet aangepast", fixture), ("half (zonder de haak)", uit.replace(",bugosTzKlaar=", ",x="))):
        try:
            w.ontdoe_tijdzone(js)
            klopt(False, f"7 (b): {naam}: ontdoe_tijdzone weigert (AssertionError)")
        except AssertionError:
            klopt(True, f"7 (b): {naam}: ontdoe_tijdzone weigert (AssertionError)")
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
    # B. Onze gok zet de zone met voorrang 30. Een 'timezone'- of 'timesource'-regel in de kickstart zet hem met
    # voorrang 70 (Timezone-module, process_kickstart), en dan wint de gok nooit meer: zonder melding, zonder fout.
    bouw_lf = bouw.replace("\r\n", "\n")
    kop = r"cat >>?\S*(?:interactive-defaults|bugos-updates)\.ks <<'?EOF'?\n"
    stukken = re.findall(kop + r"(.*?)\nEOF\n", bouw_lf, re.S)
    regels = [r for stuk in stukken for r in stuk.splitlines() if re.match(r"\s*(timezone|timesource)\b", r)]
    klopt(len(stukken) >= 3 and not regels,
          "B: geen 'timezone'/'timesource' in de kickstart (voorrang 70 zou de gok met voorrang 30 altijd overschrijven) "
          f"({len(stukken)} stukken, {regels})")


# =============================================================================== voortgang (bugos_voortgang.py) ===
INSTALLATIE = '''class DeployOSTreeTask(Task):
    def run(self):
        ref = _get_ref(self._data)
        if self._data.is_container():
            args = ["container", "image", "deploy", "--sysroot=" + self._physroot, "--image=" + ref]
            safe_exec_program(
                "ostree",
                args,
                env_add={"LC_ALL": "C.UTF-8"},
            )
        else:
            pass
'''


def maak_oci(map_: Path, lagen: dict[str, int]) -> None:
    import json
    (map_ / "blobs" / "sha256").mkdir(parents=True)
    (map_ / "index.json").write_text(json.dumps({"manifests": [{"digest": "sha256:m1"}]}), encoding="utf-8")
    (map_ / "blobs" / "sha256" / "m1").write_text(json.dumps(
        {"layers": [{"digest": f"sha256:{h}", "size": g} for h, g in lagen.items()]}), encoding="utf-8")


def test_voortgang() -> None:
    import re
    import threading

    v = laad("bugos_voortgang", SRC / "bugos_voortgang.py")
    oci = TMP / "oci"
    maak_oci(oci, {"a": 100, "b": 300, "c": 600})
    # 1. De lagen en hun grootte uit de OCI-map op de stick.
    klopt(v.lagen(str(oci)) == {"a": 100, "b": 300, "c": 600}, f"1: lagen() leest de OCI-map ({v.lagen(str(oci))})")
    klopt(v.lagen(str(oci) + ":latest") == {"a": 100, "b": 300, "c": 600}, "1: ook met ':naam' erachter (oci-transport)")
    # 2. Wat er al binnen is, en hoeveel procent dat is (naar grootte, niet naar aantal).
    phys = TMP / "sysimage"
    klopt(v.binnen(str(phys)) == set(), "2: binnen() zolang de map er nog niet is: niets")
    blob = phys / v.BLOB_MAP
    blob.mkdir(parents=True)
    for n in ("sha256_3A_b", "sha256_3A_c", "ostree"):
        (blob / n).write_text("", encoding="utf-8")
    alle = v.lagen(str(oci))
    klopt(v.binnen(str(phys)) == {"b", "c"} and v.procent(alle, v.binnen(str(phys))) == 90,
          f"2: twee van de drie lagen (900 van 1000 bytes) = 90% ({v.procent(alle, v.binnen(str(phys)))})")
    klopt(v.procent(alle, {"a", "b", "c"}) == 100 and v.procent({}, set()) == 0 and v.procent(alle, set()) == 0,
          "2: alles binnen = 100; niets = 0; geen lagen = 0 (geen deling door nul)")
    # 3. De zinnen.
    b = v.bericht
    klopt(b(37, 12, True) == "BugOS wordt gekopieerd: 37% klaar (12 minuten bezig)", f"3: NL ({b(37, 12, True)})")
    klopt(b(37, 1, False) == "Copying BugOS: 37% done (1 minute so far)" and b(3, 0, False) == "Copying BugOS: 3% done",
          f"3: EN, 1 minute / geen minuten ({b(37, 1, False)} | {b(3, 0, False)})")
    klopt(b(100, 25, False).startswith("Almost done") and b(100, 1, True).startswith("Bijna klaar")
          and "(1 minuut bezig)" in b(100, 1, True), "3: 100%: 'Almost done: putting BugOS in place'")
    klopt(b(None, 2, True) == "BugOS wordt gekopieerd (2 minuten bezig)" and "%" not in b(None, 3, False),
          "3: percentage onbekend: alleen de minuten")
    klopt(not re.search(r"few minutes|paar minuten", " ".join(b(p, m, n) for p in (None, 5, 100) for m in (0, 1, 7)
                                                         for n in (True, False))),
          "3 (I11): nergens 'a few minutes': we beloven geen tijd die we niet gemeten hebben")

    # 4. Het meldt op de achtergrond, in het Nederlands, en het percentage loopt nooit terug.
    for n in ("sha256_3A_b", "sha256_3A_c"):
        (blob / n).unlink()
    tik = iter(range(0, 10 ** 6, 30))
    berichten: list[str] = []
    with v.met_voortgang(berichten.append, str(phys), str(oci), interval=0.02, klok=lambda: next(tik), taal="nl_NL.UTF-8"):
        for n in ("sha256_3A_a", "sha256_3A_b", "sha256_3A_c"):
            time.sleep(0.07)
            (blob / n).write_text("", encoding="utf-8")
        time.sleep(0.07)
    time.sleep(0.05)
    klopt(not any(d.name == "bugos-voortgang" for d in threading.enumerate()), "4: na het blok is de draad weg")
    pct = [int(x) for m in berichten for x in re.findall(r"(\d+)% klaar", m)]
    klopt(len(berichten) >= 4 and all(m.startswith(("BugOS wordt gekopieerd", "Bijna klaar")) for m in berichten),
          f"4: berichten in het Nederlands ({len(berichten)}: {berichten[:1]} ... {berichten[-1:]})")
    klopt(pct == sorted(pct) and pct and pct[0] < 100 and berichten[-1].startswith("Bijna klaar"),
          f"4: het percentage loopt alleen op, en eindigt met 'Bijna klaar' ({sorted(set(pct))})")
    klopt("minuten bezig" in berichten[-1], f"4: de minuten tellen mee ({berichten[-1]})")
    # 5. Geen OCI-map, of een meld() die misgaat: het installeren merkt er niets van.
    berichten = []
    gewoon = TMP / "geen-oci"
    gewoon.mkdir()
    with v.met_voortgang(berichten.append, str(phys), str(gewoon), interval=0.02, taal="en_US.UTF-8"):
        time.sleep(0.1)
    klopt(berichten and all("%" not in m and m.startswith("Copying BugOS") for m in berichten),
          f"5: geen OCI-map: alleen 'Copying BugOS' zonder percentage ({berichten[:1]})")

    def kapot(_m):
        raise RuntimeError("D-Bus weg")
    try:
        with v.met_voortgang(kapot, str(phys), str(oci), interval=0.02):
            time.sleep(0.08)
        klopt(True, "5: een meld() die misgaat breekt het installeren niet")
    except Exception as e:  # noqa: BLE001
        klopt(False, f"5: een meld() die misgaat breekt het installeren niet ({e!r})")
    try:
        with v.met_voortgang(berichten.append, str(phys), str(oci), interval=0.02):
            raise OSError("ostree mislukt")
    except OSError:
        klopt(not any(d.name == "bugos-voortgang" for d in threading.enumerate()),
              "5: mislukt ostree, dan gaat de fout gewoon door naar Anaconda en stopt de draad")

    # 6. De aanroep in Anaconda zetten: precies één keer, en het blijft geldige Python.
    nieuw = v.patch_installatie(INSTALLATIE)
    klopt("met_voortgang(self.report_progress, self._physroot, ref)" in nieuw and 'env_add={"LC_ALL": "C.UTF-8"}' in nieuw,
          "6: patch_installatie zet met_voortgang om het kopiëren, ostree krijgt nog steeds LC_ALL=C.UTF-8")
    try:
        compile(nieuw, "installation.py", "exec")
        klopt(True, "6: de aangepaste installation.py is geldige Python")
    except SyntaxError as e:
        klopt(False, f"6: de aangepaste installation.py is geldige Python ({e})")
    for naam, tekst in (("zonder het stuk", INSTALLATIE.replace("args,\n", "argumenten,\n")),
                        ("met het stuk twee keer", INSTALLATIE + INSTALLATIE), ("al aangepast", nieuw)):
        try:
            v.patch_installatie(tekst)
            klopt(False, f"6: {naam}: het bouwen stopt")
        except AssertionError:
            klopt(True, f"6: {naam}: het bouwen stopt")
    bouw = bron("build.sh")
    klopt(bouw.find('bugos_voortgang.py" patch') > bouw.find("anaconda-webui") > 0
          and 'install -Dm0644 "$SRC/bugos_voortgang.py"' in bouw and "py_compile" in bouw,
          "6: build.sh zet bugos_voortgang.py naast Anaconda en past installation.py aan (na het installeren van Anaconda)")


# ============================================================================ bugos-install en het merkteken ===
def post_merkteken(map_: Path) -> Path:
    """Het %post-stukje uit build.sh, zoals Anaconda het krijgt (de heredoc uitgevouwen door bash), met /run/bugos-install
    vervangen door een map van de test. Geeft het pad van het script."""
    bouw = bron("build.sh").replace("\r\n", "\n")
    begin = bouw.index("%post --nochroot\ninstall -d -m 0755 /run/bugos-install")
    stuk = bouw[begin:bouw.index("%end", begin)].split("\n", 1)[1]
    # bash vouwt de heredoc uit (\$ wordt $), precies zoals bij het bouwen.
    uit = subprocess.run(["bash", "-c", "cat <<EOF\n" + stuk + "EOF\n"], capture_output=True, text=True, check=True).stdout
    script = map_ / "post.sh"
    script.write_text(uit.replace("/run/bugos-install", str(map_ / "run")), encoding="utf-8", newline="\n")
    return script


def test_install() -> None:
    bin_ = TMP / "bugos-install"
    bin_.write_text(bron("bugos-install").replace("\r\n", "\n").replace("/usr/share/bugos", str(ROOT / "system_files/usr/share/bugos")),
                    encoding="utf-8", newline="\n")
    bin_.chmod(0o755)
    m = TMP / "merk"
    m.mkdir()
    merk = m / "run" / "gelukt"
    post = post_merkteken(m)
    sysroot = m / "sysroot"
    (sysroot / "etc").mkdir(parents=True)
    nep("lsblk", f'cat \'{TMP}/lsblk\' 2>/dev/null || echo ext4')
    nep("kdialog", "exit 0")
    # bugos-live: 'start' (de melding) blijft staan tot iemand hem stopt, zoals het echte venster; het schrijft zijn
    # nummer op, zodat de test kan zien dat hij er was en daarna weg is. Wachten gebeurt in bash zelf (read op een
    # fifo, geen sleep): dan blijft het één proces dat bugos-live heet, en houdt niets de uitvoer van de test open.
    nep("bugos-live", f'if [ "$1" = start ]; then echo "$$" > \'{TMP}/start-pid\'; exec >/dev/null 2>&1; '
                      f'rm -f \'{TMP}/start-fifo\'; mkfifo \'{TMP}/start-fifo\'; read -r -t 20 _ <> \'{TMP}/start-fifo\'; '
                      f'exit 0; fi\n'
                      f'echo "LANGUAGE=${{LANGUAGE-<leeg>}}" >> \'{LOG}\'; exit "$(cat \'{TMP}/live-code\' 2>/dev/null || echo 0)"')
    # liveinst: wacht tot de melding er is (het echte liveinst doet er veel langer over dan het starten van de melding),
    # en doet dan wat er in $TMP/liveinst-doe staat (het %post-script draaien, of iets anders).
    nep("liveinst", f'for _ in $(seq 60); do [ -s \'{TMP}/start-pid\' ] && break; sleep 0.05; done\n'
                    f'[ -f \'{TMP}/liveinst-doe\' ] && bash \'{TMP}/liveinst-doe\'; exit 3')
    # Per ronde: (was de melding er, en is hij na afloop weg?)
    meldingen: list[tuple[bool, bool]] = []

    def ronde(doe: str | None, locale: str | None = None, post_lang: str = "", oud: str | None = None) -> list[str]:
        LOG.write_text("", encoding="utf-8")
        (TMP / "start-pid").unlink(missing_ok=True)
        shutil.rmtree(m / "run", ignore_errors=True)
        if oud is not None:   # een merkteken van een eerdere poging
            (m / "run").mkdir()
            merk.write_text(oud, encoding="utf-8")
        lc = sysroot / "etc" / "locale.conf"
        if locale is None:
            lc.unlink(missing_ok=True)
        else:
            lc.write_text(locale + "\n", encoding="utf-8")
        doe_pad = TMP / "liveinst-doe"
        if doe is None:
            doe_pad.unlink(missing_ok=True)
        else:
            doe_pad.write_text(doe, encoding="utf-8")
        env = dict(os.environ, BUGOS_INSTALL_MERKTEKEN=str(merk), ANA_INSTALL_PATH=str(sysroot), LANG=post_lang or "en_US.UTF-8")
        env.pop("LANGUAGE", None)
        env.pop("LC_ALL", None)
        subprocess.run([str(bin_)], env=env, capture_output=True, text=True, timeout=30)
        pid_tekst = (TMP / "start-pid").read_text(encoding="utf-8").strip() if (TMP / "start-pid").exists() else ""
        weg = True
        if pid_tekst.isdigit():
            # bugos-install stuurde hem weg (SIGTERM); geef hem heel even om echt te stoppen.
            eind = time.monotonic() + 3
            while leeft(int(pid_tekst)) and time.monotonic() < eind:
                time.sleep(0.02)
            weg = not leeft(int(pid_tekst))
        meldingen.append((pid_tekst.isdigit(), weg))
        # 'bugos-live start' draait tegelijk met liveinst: in welke volgorde ze in het logboek komen, ligt niet vast.
        # Die regel hier dus weglaten; meldingen houdt bij of hij er was.
        return [r for r in log() if r.startswith(("bugos-live", "LANGUAGE=", "liveinst")) and r != "bugos-live start"]

    draai_post = f"bash '{post}'\n"
    # 15. Gelukt, Nederlands gekozen. Anaconda schrijft LANG="nl_NL.UTF-8" (met aanhalingstekens, review I1).
    r = ronde(draai_post, 'LANG="nl_NL.UTF-8"')
    klopt(r == ["liveinst ", "bugos-live klaar", "LANGUAGE=nl"],
          f"15: gelukt, Nederlands (LANG=\"nl_NL.UTF-8\" zoals Anaconda het schrijft): het venster in het Nederlands ({r})")
    klopt(oct(merk.stat().st_mode & 0o777) == "0o644" and oct(merk.parent.stat().st_mode & 0o777) == "0o755",
          f"15 (I6): het merkteken is leesbaar voor de live-gebruiker ({oct(merk.stat().st_mode & 0o777)})")
    r = ronde(draai_post, "LANG=nl_NL.UTF-8")
    klopt(r[-1:] == ["LANGUAGE=nl"], f"15: ook zonder aanhalingstekens ({r})")
    # 16. Engels.
    r = ronde(draai_post, 'LANG="en_US.UTF-8"')
    klopt(r == ["liveinst ", "bugos-live klaar", "LANGUAGE=en"], f"16: gelukt, Engels ({r})")
    # I6: locale.conf niet te lezen: dan de taal van Anaconda zelf (LANG van het %post-script).
    r = ronde(draai_post, None, post_lang="fy_NL.UTF-8")
    klopt(r[-1:] == ["LANGUAGE=fy"], f"16 (I6): geen locale.conf: de taal van het installatieprogramma ({r})")
    # 17. Gestopt (niets geschreven), met een merkteken van een eerdere poging: geen venster.
    r = ronde(None, oud="0\nnl_NL.UTF-8\n")
    klopt(r == ["liveinst "], f"17: gestopt, oud merkteken '0': geen venster ({r})")
    oud = int(Path("/proc/uptime").read_text().split(".")[0]) - 100
    r = ronde(None, oud=f"{oud}\nnl_NL.UTF-8\n")
    klopt(r == ["liveinst "], f"17: merkteken van een eerdere poging (voor deze start): geen venster ({r})")
    r = ronde(None)
    klopt(r == ["liveinst "], f"17: geen merkteken (mislukt of gestopt): geen venster ({r})")
    # 18. Rommel in het merkteken.
    r = ronde("printf 'abc\\nnl\\n' > '" + str(merk) + "'", oud="")
    klopt(r == ["liveinst "], f"18: rommel op regel 1: geen venster ({r})")
    nu = "$(cut -d. -f1 /proc/uptime)"
    r = ronde(f"printf '%s\\n%s\\n' \"{nu}\" 'x;rm -rf /' > '{merk}'", oud="")
    klopt(r == ["liveinst ", "bugos-live klaar", "LANGUAGE=<leeg>"],
          f"18: een rare taal gaat niet naar LANGUAGE, het venster komt in de taal van de stick ({r})")
    r = ronde(f"printf '%s\\n' \"{nu}\" > '{merk}'", oud="")
    klopt(r == ["liveinst ", "bugos-live klaar", "LANGUAGE=<leeg>"], f"18 (I6): alleen regel 1: venster, taal van de stick ({r})")
    r = ronde(f"printf '%s\\n%s\\n' \"{nu}\" 'C.UTF-8' > '{merk}'", oud="")
    klopt(r[-1:] == ["LANGUAGE=<leeg>"], f"18: taal C: geen LANGUAGE ({r})")
    # 28 (c). Elke ronde hierboven startte liveinst: de melding 'Het installatieprogramma start' kwam er vóór liveinst
    # (liveinst wachtte erop), en was weg toen bugos-install klaar was: ook als liveinst mislukte of stopte (17, 18),
    # en vóór het venster 'Nu opnieuw opstarten' (15, 16).
    klopt(len(meldingen) == 11 and all(er for er, _weg in meldingen),
          f"28 (c): bij elke start van liveinst komt eerst de melding (bugos-live start) ({meldingen})")
    klopt(all(weg for _er, weg in meldingen),
          f"28 (c): na liveinst is de melding altijd weg, gelukt of niet ({meldingen})")

    # 19. BitLocker: de BugOS-vraag (bugos-live bitlocker). 0 = doorgaan, 10 = stoppen, iets anders = kon niet vragen.
    (TMP / "lsblk").write_text("\nntfs\nBitLocker\next4\n", encoding="utf-8")
    nep("zenity", f"exit \"$(cat '{TMP}/zen-code' 2>/dev/null || echo 0)\"")

    def bitlocker(live_code: int, zen_code: int = 0) -> list[str]:
        (TMP / "live-code").write_text(str(live_code), encoding="utf-8")
        (TMP / "zen-code").write_text(str(zen_code), encoding="utf-8")
        r = ronde(None)
        # 'bugos-live start' (de melding) staat hier niet in: die loopt tegelijk met liveinst (zie meldingen).
        return [x.split()[0] + (" " + x.split()[1] if x.startswith("bugos-live") and len(x.split()) > 1 else "")
                for x in log() if x.startswith(("bugos-live", "liveinst", "zenity", "kdialog")) and x != "bugos-live start"]

    r = bitlocker(10)
    klopt(r == ["bugos-live bitlocker"], f"19: BitLocker, 'Stop' (of het venster dicht): het installatieprogramma start niet ({r})")
    klopt(meldingen[-1] == (False, True), f"28 (c): na 'Stop' ook geen melding 'Het installatieprogramma start' ({meldingen[-1]})")
    r = bitlocker(0)
    klopt(r == ["bugos-live bitlocker", "liveinst"], f"19: BitLocker, 'Yes, continue': het installatieprogramma start ({r})")
    klopt(meldingen[-1] == (True, True),
          f"28 (c): na 'Yes, continue' komt de melding pas (ná de BitLocker-vraag), en is daarna weg ({meldingen[-1]})")
    r = bitlocker(1, zen_code=1)
    klopt(r == ["bugos-live bitlocker", "zenity", "liveinst"][:2],
          f"19 (I10): het BugOS-venster valt om: de vraag komt via zenity; 'Stop' daar stopt ({r})")
    r = bitlocker(1, zen_code=0)
    klopt(r == ["bugos-live bitlocker", "zenity", "liveinst"], f"19 (I10): ... en 'Yes, continue' daar gaat door ({r})")
    r = bitlocker(139, zen_code=127)
    klopt(r == ["bugos-live bitlocker", "zenity", "liveinst"],
          f"19 (I10): kan ook zenity niet: het installeren gaat door, 'BugOS installeren' doet nooit niets ({r})")
    (TMP / "lsblk").unlink()
    (TMP / "live-code").unlink()
    r = bitlocker(0)
    klopt(r == ["liveinst"], f"19: geen BitLocker: geen vraag, meteen het installatieprogramma ({r})")

    # 20. Statisch: niet meer exec liveinst; het merkteken is de laatste stap in de kickstart; geen nieuw yad-venster.
    tekst = bron("bugos-install")
    klopt("exec liveinst" not in tekst, "20: bugos-install neemt liveinst niet meer over (exec), zodat het daarna kan kijken")
    klopt("kdialog" not in tekst and "bugos-live bitlocker" in tekst, "20: de BitLocker-vraag is een BugOS-venster, geen kdialog (KDE)")
    # 28 (c). De volgorde in bugos-install: eerst de BitLocker-vraag, dan de melding (op de achtergrond), dan liveinst,
    # dan de melding weg (alleen als het nog ons kind is), en pas daarna het venster 'Nu opnieuw opstarten'.
    volgorde = [tekst.find(x) for x in ("bugos-live bitlocker", "bugos-live start &", "melding=$!", 'liveinst "$@"',
                                        'ps -o ppid= -p "$melding"', 'kill "$melding"', "exec bugos-live klaar")]
    klopt(-1 not in volgorde and volgorde == sorted(volgorde),
          f"28 (c): bugos-install: BitLocker-vraag, melding, liveinst, melding weg, dan pas 'klaar' ({volgorde})")
    bouw = bron("build.sh").replace("\r\n", "\n")
    ks = bouw[bouw.index("interactive-defaults.ks <<EOF"):]
    ks = ks[:ks.index("\nEOF\n")]
    klopt(ks.index("%post --nochroot\ninstall -d -m 0755 /run/bugos-install") > ks.index("%include /usr/share/anaconda/post-scripts/bugos-updates.ks"),
          "20: het merkteken komt na de bootc-switch en de Nvidia-stap (%include)")
    na = bouw[bouw.index('install -Dm0755 "$SRC/bugos-live" /usr/bin/bugos-live'):]
    klopt(na.index('SourceFileLoader("bugos_live", "/usr/bin/bugos-live")') < na.index("\nPY\n") < 1500
          and "except ImportError" in na[:1500],
          "20: build.sh laadt bugos-live na het kopiëren: past het niet bij BASE_IMAGE (te oud), dan stopt het bouwen")
    if shutil.which("shellcheck"):
        r = subprocess.run(["shellcheck", "-x", "iso_live/src/bugos-install", "iso_live/src/build.sh"], cwd=ROOT,
                           capture_output=True, text=True)
        klopt(r.returncode == 0, f"20: shellcheck -x bugos-install en build.sh ({r.stdout.strip()[-300:]})")
        r = subprocess.run(["shellcheck", "-s", "bash", str(post)], capture_output=True, text=True)
        klopt(r.returncode == 0, f"20: shellcheck op het %post-script zoals Anaconda het krijgt ({r.stdout.strip()[-300:]})")
    else:
        klopt(True, "20: shellcheck OK (overgeslagen: niet op deze computer)")


# ====================================================================================== het venster 'klaar' ===
MAAT = r'''
import importlib.machinery, importlib.util, json, os, sys
sys.path.insert(0, sys.argv[2])
lader = importlib.machinery.SourceFileLoader("bugos_live", sys.argv[1])
spec = importlib.util.spec_from_loader("bugos_live", lader)
live = importlib.util.module_from_spec(spec); lader.exec_module(live)
app = live.maak_app("bugos-live", "bugos-live", ["bugos-live"])
from PySide6.QtWidgets import QLabel, QPushButton
k = live.venster(["klaar"])
uit = {"klasse": type(k).__name__, "kop": k.kop.text(), "nu": k.nu.text(), "fouten": []}
k.resize(720, 440)
k.show()
for stand in ("begin", "bezig", "mislukt"):
    k.toon(stand)
    for _ in range(5):
        app.processEvents()
    # Op het scherm: elk zichtbaar stuk binnen het venster, geen tekst afgeknipt, de knoppen onder de tekst.
    for w in k.findChildren(QLabel) + k.findChildren(QPushButton):
        if not w.isVisible():
            continue
        g = w.geometry()
        if g.left() < 0 or g.top() < 0 or g.right() > k.width() or g.bottom() > k.height():
            uit["fouten"].append(f"{stand}: {w.text()[:20]!r} valt buiten het venster {g.getRect()}")
        if isinstance(w, QLabel) and w.wordWrap() and w.text() and w.heightForWidth(w.width()) > w.height():
            uit["fouten"].append(f"{stand}: {w.text()[:20]!r} afgeknipt ({w.heightForWidth(w.width())} > {w.height()})")
        if isinstance(w, QPushButton) and w.width() < w.sizeHint().width():
            uit["fouten"].append(f"{stand}: knop {w.text()!r} te smal")
    tekst_onder = max(x.geometry().bottom() for x in (k.kop, k.tekst, k.fout) if x.isVisible())
    if k.nu.geometry().top() <= tekst_onder:
        uit["fouten"].append(f"{stand}: de knoppen staan over de tekst")
    uit[stand] = k.layout().minimumSize().height()
print(json.dumps(uit))
'''


def test_klaar(app, live) -> None:
    import json

    os.environ["BUGOS_INSTELLINGEN_VOORBEELD"] = "1"
    # 23. Voorbeeldstand: 'Nu opnieuw opstarten' laat zien wat er gebeurt, maar start niets.
    LOG.write_text("", encoding="utf-8")
    nep("systemctl", f"exit \"$(cat '{TMP}/sc-code' 2>/dev/null || echo 0)\"")
    k = live.Klaar()
    k.show()
    klopt(k.kop.text() == "BugOS is on your computer" and k.nu.isDefault() and not k.fout.isVisible(),
          f"23: begin: 'BugOS is on your computer', 'Restart now' is de standaardknop ({k.kop.text()})")
    k.nu.click()
    klopt(k.kop.text() == "Restarting…" and not k.nu.isEnabled() and not k.later.isEnabled()
          and "screen goes black" in k.tekst.text(), f"23: bezig: 'Restarting…', beide knoppen uit ({k.kop.text()})")
    wacht(app, lambda: False, 0.2)
    klopt(not [r for r in log() if r.startswith("systemctl")], "23: in de voorbeeldstand wordt systemctl niet gestart")
    k.close()
    os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD")

    # 24. Echt: systemctl weigert -> uitleg met het startmenu; lukt het -> blijft 'bezig' (de computer gaat uit).
    def klik(code: str | None) -> live.Klaar:
        LOG.write_text("", encoding="utf-8")
        oud_pad = os.environ["PATH"]
        if code is None:   # systemctl bestaat niet
            leeg = TMP / "leeg-pad"
            leeg.mkdir(exist_ok=True)
            os.environ["PATH"] = str(leeg)
        else:
            (TMP / "sc-code").write_text(code, encoding="utf-8")
        k = live.Klaar()
        k.show()
        try:
            k.nu.click()
            if k.proces is not None:
                k.proces.waitForFinished(5000)
            wacht(app, lambda: k.fout.isVisible(), 1.0)
        finally:
            os.environ["PATH"] = oud_pad
        return k

    k = klik("1")
    klopt(k.fout.isVisible() and k.nu.isEnabled() and k.later.isEnabled() and k.kop.text() == "BugOS is on your computer"
          and "Start menu" in k.fout.text(), f"24: systemctl weigert: uitleg 'Use Restart in the Start menu', knoppen weer aan ({k.fout.text()})")
    klopt("systemctl reboot" in log(), f"24: 'Restart now' vraagt systemctl reboot ({log()})")
    k.close()
    k = klik("0")
    klopt(not k.fout.isVisible() and not k.nu.isEnabled() and k.kop.text() == "Restarting…",
          "24: systemctl lukt: het venster blijft op 'Restarting…' (de computer gaat uit)")
    k.close()
    k = klik(None)
    klopt(k.fout.isVisible() and k.nu.isEnabled(), "24: systemctl ontbreekt: ook de uitleg, geen dood spoor")
    k.close()

    # 25. 'Later' sluit; main() kiest het venster; in het Nederlands als het installatieprogramma Nederlands was.
    k = live.Klaar()
    k.show()
    k.later.click()
    klopt(not k.isVisible(), "25: 'Later' sluit het venster (verder gebeurt er niets)")
    klopt(isinstance(live.venster(["klaar"]), live.Klaar) and isinstance(live.venster([]), live.Live)
          and type(live.venster(["iets"])) is live.Live, "25: bugos-live klaar -> Klaar, bugos-live -> het welkomstscherm")
    metingen = {}
    for taal in ("en", "nl"):
        env = dict(os.environ, LANGUAGE=taal, LANG="en_US.UTF-8", QT_QPA_PLATFORM="offscreen")
        env.pop("LC_ALL", None)
        r = subprocess.run([sys.executable, "-c", MAAT, str(SRC / "bugos-live"), str(PY)], env=env,
                           capture_output=True, text=True, timeout=60)
        try:
            metingen[taal] = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            metingen[taal] = {"fout": r.stderr[-300:]}
    nl = metingen["nl"]
    klopt(nl.get("klasse") == "Klaar" and nl.get("kop") == "BugOS staat op je computer" and nl.get("nu") == "Nu opnieuw opstarten",
          f"25: met LANGUAGE=nl (zo start bugos-install het) is het venster Nederlands ({nl.get('kop')})")
    # 26. Past op een laptop van 1280x800 bij 150 %: 720x440 (x1.5 = 1080x660) plus titelbalk, boven de taakbalk.
    for taal, mt in metingen.items():
        klopt("fouten" in mt and not mt["fouten"],
              f"26: {taal}: in 720x440 past alles, in alle drie de standen (niets afgeknipt of eronder) ({mt.get('fouten')})")
    klopt(720 * 1.5 <= 1280 and (440 + 40) * 1.5 <= 800 - 72,
          "26: 720x440 met titelbalk bij 150 % past op 1280x800 boven een taakbalk van 72 px")

    # F. De BitLocker-vraag: de gedeelde BugOS-vraag (vraag_ja), Enter = Stop; de exitcode die bugos-install verwacht.
    import bugos_shell
    from PySide6.QtWidgets import QDialog
    gezien = []
    echt = bugos_shell.VraagDialoog.exec
    for antwoord in (QDialog.DialogCode.Rejected, QDialog.DialogCode.Accepted):
        bugos_shell.VraagDialoog.exec = lambda self, a=antwoord: (gezien.append(self), a)[1]
        try:
            ja = live.vraag_bitlocker()
        finally:
            bugos_shell.VraagDialoog.exec = echt
        klopt(ja == (antwoord == QDialog.DialogCode.Accepted), f"F: BitLocker-vraag: {antwoord.name} -> {ja}")
    d = gezien[0]
    klopt(d.standaard == "Stop" and d.nee.text() == "Stop" and d.ja.text() == "Yes, continue",
          f"F: knoppen 'Stop' en 'Yes, continue'; Enter doet het veilige: Stop ({d.standaard})")
    klopt("recovery key" in d.uitleg.text() and "account.microsoft.com/devices/recoverykey" in d.uitleg.text()
          and "BitLocker" in d.kop.text(), "F: de vraag zegt waarom: eerst de herstelsleutel opschrijven")
    code = ("import importlib.machinery, importlib.util, sys\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "lader = importlib.machinery.SourceFileLoader('bugos_live', sys.argv[1])\n"
            "live = importlib.util.module_from_spec(importlib.util.spec_from_loader('bugos_live', lader)); lader.exec_module(live)\n"
            "import bugos_shell\n"
            "keus = int(sys.argv[3])\n"
            "bugos_shell.VraagDialoog.exec = lambda self: keus\n"
            "sys.argv = ['bugos-live', 'bitlocker']\n"
            "sys.exit(live.main())\n")
    codes = []
    for keus in ("0", "1"):
        r = subprocess.run([sys.executable, "-c", code, str(SRC / "bugos-live"), str(PY), keus],
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True, text=True, timeout=60)
        codes.append(r.returncode)
        if r.returncode not in (0, 10):
            print(r.stderr[-600:])
    klopt(codes == [10, 0], f"F (I10): bugos-live bitlocker: Stop = 10, doorgaan = 0 (anders = 'kon niet vragen') ({codes})")


# ======================================================== de melding 'Het installatieprogramma start' (c) ===
# Zelfde soort meting als MAAT, voor het venster 'start' in beide standen (gewoon, en 'het duurt langer').
MAAT_START = r'''
import importlib.machinery, importlib.util, json, os, sys
sys.path.insert(0, sys.argv[2])
lader = importlib.machinery.SourceFileLoader("bugos_live", sys.argv[1])
spec = importlib.util.spec_from_loader("bugos_live", lader)
live = importlib.util.module_from_spec(spec); lader.exec_module(live)
app = live.maak_app("bugos-live", "bugos-live", ["bugos-live"])
from PySide6.QtWidgets import QLabel, QProgressBar
s = live.venster(["start"])
s.timer.stop()
uit = {"klasse": type(s).__name__, "kop": s.kop.text(), "tekst": s.tekst.text(), "fouten": [],
       "maat": [s.width(), s.height()]}
s.show()
for lang in (False, True):
    s.toon(lang=lang)
    for _ in range(5):
        app.processEvents()
    for w in s.findChildren(QLabel) + s.findChildren(QProgressBar):
        if not w.isVisible():
            continue
        g = w.geometry()
        if g.left() < 0 or g.top() < 0 or g.right() > s.width() or g.bottom() > s.height():
            uit["fouten"].append(f"{lang}: {type(w).__name__} valt buiten het venster {g.getRect()}")
        if isinstance(w, QLabel) and w.wordWrap() and w.text() and w.heightForWidth(w.width()) > w.height():
            uit["fouten"].append(f"{lang}: {w.text()[:20]!r} afgeknipt ({w.heightForWidth(w.width())} > {w.height()})")
    if s.balk.geometry().top() <= s.tekst.geometry().bottom():
        uit["fouten"].append(f"{lang}: het balkje staat over de tekst")
    uit["lang" if lang else "kort"] = s.tekst.text()
print(json.dumps(uit))
'''


def test_start(app, live) -> None:
    """28 (c): bugos-live start. Sluit zichzelf zodra het installatieprogramma klaar is: de vlag backend_ready van
    Anaconda én het venster met de pagina. Daarvoor een eigen /proc en een eigen vlag (de module-variabelen)."""
    import json

    proc = TMP / "proc"
    (proc / "self").mkdir(parents=True)                 # geen getal: overslaan
    (proc / "7").mkdir()                                # webui-desktop zelf: heeft de pagina NIET op zijn regel
    (proc / "7" / "cmdline").write_bytes(b"/usr/bin/bash\0/usr/libexec/anaconda/webui-desktop\0-t\0live\0")
    (proc / "8").mkdir()                                # zonder cmdline (net weg, of niet te lezen): overslaan
    vlag = TMP / "backend_ready"
    live.PROC, live.ANACONDA_KLAAR = str(proc), str(vlag)
    url = b"http://127.0.0.1/cockpit/@localhost/anaconda-webui/index.html"

    def browser(aan: bool) -> None:
        if aan:
            (proc / "42").mkdir(exist_ok=True)
            (proc / "42" / "cmdline").write_bytes(b"slitherer\0" + url + b"\0")
        else:
            shutil.rmtree(proc / "42", ignore_errors=True)

    klopt(not live.installatie_venster() and not live.installatie_venster(str(TMP / "bestaat-niet")),
          "28 (c): geen venster van het installatieprogramma (webui-desktop zelf telt niet; geen /proc: geen fout)")
    browser(True)
    klopt(live.installatie_venster() and not live.installatie_klaar(),
          "28 (c): het venster draait, maar Anaconda is nog niet klaar (geen backend_ready): nog niet klaar")
    browser(False)
    vlag.write_text("", encoding="utf-8")
    klopt(not live.installatie_klaar(), "28 (c): backend_ready, maar (nog) geen venster: nog niet klaar")
    vlag.unlink()

    s = live.venster(["start"])
    s.timer.stop()   # de test kiest zelf wanneer er gekeken wordt
    s.NA_KLAAR_MS = 50
    s.show()
    app.processEvents()
    klopt(isinstance(s, live.Start) and s.kop.text() == "The installer is starting" and "a minute or two" in s.tekst.text()
          and "no need to click again" in s.tekst.text() and s.balk.maximum() == 0 and s.isVisible(),
          f"28 (c): 'The installer is starting', hoe lang het ongeveer duurt, en een balkje dat loopt ({s.tekst.text()})")
    browser(True)
    s.kijk()
    klopt(s.isVisible() and not s.klaar_gezien, "28 (c): venster er, Anaconda nog niet klaar: de melding blijft")
    s.begin = time.monotonic() - s.LANG_S - 1
    s.kijk()
    klopt(s.isVisible() and "longer than usual" in s.tekst.text(),
          f"28 (c): na 4 minuten zegt de melding eerlijk dat het langer duurt ({s.tekst.text()})")
    vlag.write_text("", encoding="utf-8")
    s.kijk()
    klopt(s.klaar_gezien and wacht(app, lambda: not s.isVisible(), 3),
          "28 (c): backend_ready en het venster: de melding gaat vanzelf weg")
    browser(False)
    vlag.unlink()
    live.PROC, live.ANACONDA_KLAAR = "/proc", "/run/anaconda/backend_ready"

    # Op het scherm, in het Engels en het Nederlands (zo start bugos-install hem: de taal van de stick, of LANGUAGE).
    metingen = {}
    for taal in ("en", "nl"):
        env = dict(os.environ, LANGUAGE=taal, LANG="en_US.UTF-8", QT_QPA_PLATFORM="offscreen")
        env.pop("LC_ALL", None)
        r = subprocess.run([sys.executable, "-c", MAAT_START, str(SRC / "bugos-live"), str(PY)], env=env,
                           capture_output=True, text=True, timeout=60)
        try:
            metingen[taal] = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            metingen[taal] = {"fout": r.stderr[-300:]}
    nl = metingen["nl"]
    klopt(nl.get("klasse") == "Start" and nl.get("kop") == "Het installatieprogramma start"
          and "minuut of twee" in nl.get("kort", "") and "langer dan normaal" in nl.get("lang", ""),
          f"28 (c): in het Nederlands: 'Het installatieprogramma start' ({nl.get('kop')} | {nl.get('kort')})")
    for taal, mt in metingen.items():
        klopt("fouten" in mt and not mt["fouten"],
              f"28 (c): {taal}: in {mt.get('maat')} past alles, in beide standen (niets afgeknipt of eronder) "
              f"({mt.get('fouten')})")
    # Past op een laptop van 1280x800 bij 150 %, met titelbalk, boven de taakbalk (zelfde regel als 26).
    b, h = metingen["en"].get("maat", [9999, 9999])
    klopt(b * 1.5 <= 1280 and (h + 40) * 1.5 <= 800 - 72,
          f"28 (c): {b}x{h} met titelbalk bij 150 % past op 1280x800 boven een taakbalk van 72 px")


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


def beeld_voortgang() -> None:
    """patch_installatie op een kopie van de echte pyanaconda; daarna moet DeployOSTreeTask.run met_voortgang gebruiken."""
    import pyanaconda
    ana = Path(pyanaconda.__file__).parent
    kopie = Path("/tmp/installer-ana")
    shutil.rmtree(kopie, ignore_errors=True)
    shutil.copytree(ana, kopie / "pyanaconda", ignore=shutil.ignore_patterns("__pycache__"))
    doel = kopie / "pyanaconda" / "modules" / "payloads" / "payload" / "rpm_ostree"
    shutil.copy(SRC / "bugos_voortgang.py", doel / "bugos_voortgang.py")
    r = subprocess.run([sys.executable, str(SRC / "bugos_voortgang.py"), "patch", str(doel / "installation.py")],
                       capture_output=True, text=True)
    klopt(r.returncode == 0, f"beeld: de echte installation.py van Anaconda laat zich aanpassen ({r.stderr.strip()[-200:]})")
    code = ("from pyanaconda.modules.payloads.payload.rpm_ostree.installation import DeployOSTreeTask as D;"
            "import pyanaconda;print(pyanaconda.__file__);print('met_voortgang' in D.run.__code__.co_names)")
    for vlag in ([], ["-O"]):
        r = subprocess.run([sys.executable, *vlag, "-c", code], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(kopie)))
        regels = r.stdout.split()
        klopt(r.returncode == 0 and regels[-1:] == ["True"] and str(kopie) in regels[0],
              f"beeld: DeployOSTreeTask.run gebruikt met_voortgang {' '.join(vlag)} ({r.stdout.strip()} {r.stderr.strip()[-200:]})")
    shutil.rmtree(kopie, ignore_errors=True)


def beeld_echt_kopieren(seconden: int = 70) -> None:
    """(--echt, ~75 s, podman run --privileged) Echt kopiëren zoals Anaconda het doet, met de voortgang erbij."""
    import re
    v = laad("bugos_voortgang", SRC / "bugos_voortgang.py")
    oci = "/var/lib/bugos-stick/bugos"
    sr = Path("/var/tmp/installer-sr")
    shutil.rmtree(sr, ignore_errors=True)
    sr.mkdir(parents=True)
    subprocess.run(["ostree", "admin", "init-fs", "--modern", str(sr)], capture_output=True, check=False)
    subprocess.run(["ostree", "admin", f"--sysroot={sr}", "os-init", "bugos"], capture_output=True, check=False)
    berichten: list[str] = []
    begin = time.monotonic()

    def meld(m: str) -> None:
        berichten.append(m)
        print(f"      {time.monotonic() - begin:4.0f}s  {m}")
    proc = subprocess.Popen(["ostree", "container", "image", "deploy", f"--sysroot={sr}", f"--image={oci}",
                             "--transport=oci", "--stateroot=bugos", "--no-signature-verification"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, LC_ALL="C.UTF-8"))
    # De klok 30 keer zo snel, zodat je in 70 s ook de minuten ziet lopen.
    with v.met_voortgang(meld, str(sr), oci, interval=8, klok=lambda: (time.monotonic() - begin) * 30, taal="en_US.UTF-8"):
        try:
            proc.wait(timeout=seconden)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    pct = [int(x) for m in berichten for x in re.findall(r"(\d+)% done", m)]
    klopt(len(berichten) >= 2 and pct == sorted(pct) and pct and pct[-1] > pct[0],
          f"beeld (echt): tijdens het echte kopiëren loopt het percentage op ({pct})")
    shutil.rmtree(sr, ignore_errors=True)


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
    beeld_voortgang()
    if "--echt" in sys.argv[1:]:
        beeld_echt_kopieren()
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


def main() -> int:
    if BEELD:
        return beeld()
    os.environ["PATH"] = str(NEP) + os.pathsep + schoon_pad()
    test_woorden()
    test_tijdzone()
    test_voortgang()
    test_install()
    test_live()
    shutil.rmtree(TMP, ignore_errors=True)
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
