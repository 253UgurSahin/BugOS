#!/usr/bin/env python3
"""Test van 'Haal alles van je oude pc': bestanden slimmer (E) en alles terugdraaien (F).

Wat we testen, met een nep-thuismap in een tijdelijke map en nep-programma's (aan je eigen computer verandert niets):
  - het overzicht noemt de nieuwe onderdelen: andere mappen, lettertypen, e-mail (Thunderbird en Outlook);
  - extra mappen komen in je Thuismap (en een rare naam van de stick, zoals '.config' of '../x', telt niet);
  - lettertypen in ~/.local/share/fonts/Van Windows, zonder iets te overschrijven;
  - Thunderbird: het profiel zonder wachtwoorden, cookies en ImapMail; Windows-paden uit prefs.js; een nieuw
    profiles.ini met dat profiel als standaard (Thunderbird nog niet geïnstalleerd: 'installeer hem in de Winkel');
  - Outlook-bestanden in Documenten, met eerlijke uitleg; OneDrive-bestanden die niet meekwamen: zeggen welke;
  - Firefox als Flatpak: BugOS vindt het profiel ook in ~/.var/app/org.mozilla.firefox;
  - het logboek: rsync-regels lezen (nooit iets buiten de doelmap), een oude waarde telt maar één keer;
  - terugdraaien: bestanden naar de prullenbak, een bestand dat je zelf veranderde blijft staan, lege mappen weg,
    instellingen terug (taal vóór de notatie), wifi en printers eruit, het Thunderbird-profiel naar de prullenbak en
    profiles.ini zoals het was;
  - het venster: 'Alles terugdraaien' staat er zodra er een logboek is, en werkt.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_switch_slimmer.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-switch-slimmer-"))
THUIS = TMP / "thuis"
(THUIS / ".config").mkdir(parents=True)
os.environ.update(HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), XDG_DATA_HOME=str(THUIS / ".local/share"),
                  XDG_CACHE_HOME=str(THUIS / ".cache"), LC_ALL="nl_NL.UTF-8", LANG="nl_NL.UTF-8", BUGOS_LSBLK="")
os.environ.pop("LANGUAGE", None)
os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD", None)
os.environ.pop("XDG_RUNTIME_DIR", None)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


# ======================================================================= nep-programma's ===
# Alleen wat hier nodig is. Geen flatpak en geen thunderbird in het PATH: Thunderbird is 'nog niet geïnstalleerd'.
NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "opdrachten.log"
LOG.write_text("")


def nep(naam: str, inhoud: str) -> None:
    (NEP / naam).write_text("#!/usr/bin/bash\n" + inhoud)
    (NEP / naam).chmod(0o755)


for naam in ("kwriteconfig6", "plasma-apply-wallpaperimage", "fc-cache", "bugos-theme"):
    nep(naam, f'echo "{naam} $*" >> "{LOG}"\nexit 0\n')
nep("kreadconfig6", 'while [ $# -gt 0 ]; do [ "$1" = --default ] && { echo "$2"; exit 0; }; shift; done\n')
nep("xdg-user-dir", "exit 1\n")
nep("nmcli", f'echo "nmcli $*" >> "{LOG}"\nexit 0\n')
nep("lpadmin", f'echo "lpadmin $*" >> "{LOG}"\nexit 0\n')
nep("lpoptions", f'echo "lpoptions $*" >> "{LOG}"\nexit 0\n')
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"


def log() -> str:
    return LOG.read_text()


import bugos_config as bi  # noqa: E402
import bugos_overstap_bestanden as ob  # noqa: E402
import bugos_overstap_firefox as ff  # noqa: E402
import bugos_overstap_logboek as lb  # noqa: E402
import bugos_overstap_toepassen as ot  # noqa: E402

bi.ben_beheerder = lambda: True   # lpadmin direct, zonder pkexec


def stick(naam: str, data: dict) -> Path:
    """Een nep-stick zoals BugOS Switch (Windows) hem sinds 'bestanden slimmer' maakt."""
    s = TMP / naam / "BugOS-Switch"
    (s / "Documents").mkdir(parents=True)
    (s / "Documents" / "brief.txt").write_text("brief")
    (s / "Extra" / "Foto's 2019" / "Vakantie").mkdir(parents=True)
    (s / "Extra" / "Foto's 2019" / "Vakantie" / "strand.txt").write_text("strand")
    (s / "Extra" / "geheim").mkdir(parents=True)
    (s / "Lettertypen").mkdir()
    (s / "Lettertypen" / "MijnLetter.ttf").write_bytes(b"ttf" * 10)
    (s / "Lettertypen" / "leesmij.txt").write_text("geen lettertype")
    p = s / "Thunderbird" / "abcd.default-release"
    (p / "Mail" / "Local Folders").mkdir(parents=True)
    (p / "ImapMail" / "imap.example.com").mkdir(parents=True)
    (p / "Mail" / "Local Folders" / "Inbox").write_text("From x")
    (p / "ImapMail" / "imap.example.com" / "INBOX").write_text("kopie van de server")
    (p / "prefs.js").write_text('user_pref("mail.server.server1.directory", "C:\\\\Users\\\\x\\\\Mail");\n'
                                'user_pref("mail.server.server1.directory-rel", "[ProfD]Mail/Local Folders");\n')
    for geheim in ("logins.json", "key4.db", "cookies.sqlite"):
        (p / geheim).write_text("GEHEIM")
    (s / "Outlook").mkdir()
    (s / "Outlook" / "thuis.pst").write_bytes(b"pst")
    (s / "bugos-switch.json").write_text(json.dumps(data), encoding="utf-8")
    return s


DATA = {
    "versie": 2, "computer": "LAPTOP-PIET", "gebruiker": "piet", "mappen": ["Documents"],
    "extra": [{"naam": "Foto's 2019", "map": "Extra/Foto's 2019", "van": "D:\\Foto's 2019"},
              {"naam": ".config", "map": "Extra/geheim"},          # verborgen map in je Thuismap: nooit
              {"naam": "Weg", "map": "../../buiten"}],             # buiten de stick: nooit
    "lettertypen": {"map": "Lettertypen", "aantal": 1},
    "thunderbird_profiel": "Thunderbird/abcd.default-release",
    "outlook": {"pst": ["Outlook/thuis.pst", "Documents/bestaat-niet.pst"]},
    "cloud": {"aantal": 3, "bytes": 1000, "voorbeelden": ["foto.jpg", "lijst.xlsx"], "meegenomen": False},
}
S = stick("stick", DATA)
I = ot.info(S)

# ============================================================================== het overzicht ===
delen = [o.sleutel for o in ot.onderdelen(S)]
klopt({"bestanden", "extra", "lettertypen", "mail"} <= set(delen),
      f"overzicht: andere mappen, lettertypen en e-mail staan erin ({delen})")
klopt([n for n, _p in ob.extra_mappen(S, I)] == ["Foto's 2019"],
      "extra mappen: een verborgen naam (.config) en een pad buiten de stick tellen niet")
uitleg = {o.sleutel: o.uitleg for o in ot.onderdelen(S)}
klopt("Thunderbird" in uitleg["mail"] and "Outlook" in uitleg["mail"] and "wachtwoord" in uitleg["mail"],
      "overzicht: e-mail noemt Thunderbird (zonder wachtwoorden) en Outlook")
klopt([p.name for p in ob.lettertypen_op_stick(S, I)] == ["MijnLetter.ttf"], "lettertypen: alleen echte lettertypen")
# VM-test 2026-11-16: 'lijn:tekst' en 'lijn:mail' bestonden niet: lege tegeltjes. Elk icoon moet echt bestaan.
import re as _re  # noqa: E402
_ui = (PY / "bugos_ui.py").read_text(encoding="utf-8")
_lijn = set(_re.findall(r"^    \"([a-z_]+)\": '<", _ui[_ui.index("LIJN = {"):], _re.M))
_iconen = {o.icoon[5:] for o in ot.onderdelen(S) if o.icoon.startswith("lijn:")}
klopt(_iconen and _iconen <= _lijn, f"overzicht: elk icoon bestaat echt (mist: {sorted(_iconen - _lijn)})")
klopt(next(o.uitleg for o in ot.onderdelen(S) if o.sleutel == "lettertypen").startswith("1 lettertype dat"),
      "overzicht: '1 lettertype' (niet '1 lettertypen')")

# ================================================================================ het logboek ===
lb.ACTIEF = lb.Logboek()
lb.ACTIEF.begin("LAPTOP-PIET", "piet")

# rsync-logboek lezen: nieuw bestand en nieuwe map; '../' en een absoluut pad nooit.
RLOG = TMP / "rsync.log"
RLOG.write_text("2026/11/16 19:30:01 [123] building file list\n"
                "2026/11/16 19:30:01 [123] cd+++++++++ Vakantie/\n"
                "2026/11/16 19:30:01 [123] >f+++++++++ Vakantie/strand.txt\n"
                "2026/11/16 19:30:01 [123] >f+++++++++ ../buiten.txt\n"
                "2026/11/16 19:30:01 [123] >f+++++++++ /etc/passwd\n"
                "2026/11/16 19:30:01 [123] >f..t...... al-er.txt\n")
_b, _m = lb.lees_rsync_log(RLOG, THUIS / "Foto's 2019")
klopt([str(p) for p in _b] == [str(THUIS / "Foto's 2019" / "Vakantie" / "strand.txt")]
      and [str(p) for p in _m] == [str(THUIS / "Foto's 2019" / "Vakantie")],
      "rsync-logboek: alleen nieuwe bestanden en mappen, nooit iets buiten de doelmap")

# Een oude waarde telt maar één keer (twee keer overzetten: terug naar hoe het vóór de eerste keer was).
lb.onthoud("instelling", naam="donker", oud=False)
lb.onthoud("instelling", naam="donker", oud=True)
klopt([a["oud"] for a in lb.ACTIEF.data["acties"] if a.get("naam") == "donker"] == [False],
      "logboek: van een instelling telt alleen de eerste oude waarde")
lb.ACTIEF.data["acties"].clear()

# ======================================================================= de stappen zelf ===
bo_stappen = None


def laad(naam: str, programma: str):
    lader = importlib.machinery.SourceFileLoader(naam, str(BIN / programma))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


bo = laad("bugos_overstap_slimmer", "bugos-switch")
bo.gebruikersmap = lambda xdg, standaard: THUIS / standaard
(THUIS / "Documents").mkdir(exist_ok=True)
(THUIS / "Documents" / "brief.txt").write_text("mijn eigen brief")   # bestaat al: nooit overschrijven

stappen_ = bo.stappen(S, True, True)
klopt(any(str(THUIS / "Foto's 2019") + "/" == c[-1] for _t, c in stappen_)
      and all(any(x.startswith("--log-file=") for x in c) for _t, c in stappen_),
      "stappen: de extra map gaat naar de Thuismap, en elke rsync schrijft een logboek")
for _t, cmd in stappen_:
    import subprocess
    subprocess.run(cmd, capture_output=True)
    bo.na_rsync(cmd)
klopt((THUIS / "Foto's 2019" / "Vakantie" / "strand.txt").read_text() == "strand"
      and (THUIS / "Documents" / "brief.txt").read_text() == "mijn eigen brief",
      "extra map staat in de Thuismap; je eigen brief is niet overschreven")
_nieuw = [a["pad"] for a in lb.ACTIEF.data["acties"] if a["soort"] == "bestand"]
klopt(str(THUIS / "Foto's 2019" / "Vakantie" / "strand.txt") in _nieuw
      and str(THUIS / "Documents" / "brief.txt") not in _nieuw,
      "logboek: het nieuwe bestand staat erin, je eigen brief (al op BugOS) niet")

u = ob.zet_lettertypen(S, I)
klopt((ob.lettertypen_map() / "MijnLetter.ttf").is_file() and u[0].soort == ot.GOED and "fc-cache" in log(),
      "lettertypen: in ~/.local/share/fonts/Van Windows, en fc-cache kent ze meteen")
klopt(ob.zet_lettertypen(S, I)[0].tekst.startswith("Ze stonden er al"), "lettertypen: een tweede keer: 'stonden er al'")

u = ob.zet_thunderbird(S, I)
TBMAP = THUIS / ".var" / "app" / "org.mozilla.Thunderbird" / ".thunderbird"
_profiel = next(TBMAP.glob("*.van-windows"), None)
klopt(_profiel is not None and (_profiel / "Mail" / "Local Folders" / "Inbox").is_file(),
      "Thunderbird: het profiel staat klaar in de map van de Flatpak (ook al is hij nog niet geïnstalleerd)")
klopt(_profiel is not None and not any((_profiel / n).exists() for n in ("logins.json", "key4.db", "cookies.sqlite",
                                                                          "ImapMail")),
      "Thunderbird: geen wachtwoorden, geen cookies en geen ImapMail")
klopt(_profiel is not None and "C:\\\\" not in (_profiel / "prefs.js").read_text()
      and "directory-rel" in (_profiel / "prefs.js").read_text(),
      "Thunderbird: Windows-paden uit prefs.js weg, de '-rel'-variant blijft")
_ini = ff._ini(TBMAP / "profiles.ini")
klopt(any(_ini[s].get("Default") == "1" and _ini[s].get("Path") == getattr(_profiel, "name", "?")
          for s in _ini.sections()), "Thunderbird: een nieuw profiles.ini met dit profiel als standaard")
klopt(u and u[0].soort == ot.ZELF and "Winkel" in u[0].tekst,
      f"Thunderbird nog niet geïnstalleerd: 'installeer hem in de Winkel' ({u[0].tekst[:60] if u else ''})")

u = ob.zet_outlook(S, I, THUIS / "Documents")
klopt((THUIS / "Documents" / "Outlook-bestanden" / "thuis.pst").is_file() and u[0].soort == ot.ZELF
      and "Thunderbird" in u[0].tekst, "Outlook: .pst in Documenten/Outlook-bestanden, met eerlijke uitleg")
u = ob.cloud_uitslag(I)
klopt(u and "3 bestanden" in u[0].tekst and "foto.jpg" in u[0].tekst and "onedrive.live.com" in u[0].tekst,
      "OneDrive: zegt hoeveel er niet meekwamen, welke, en waar ze zijn")
klopt(ob.cloud_uitslag({"cloud": {"aantal": 3, "meegenomen": True}}) == [], "OneDrive: meegenomen = niets te zeggen")

# Firefox als Flatpak: het profiel staat in ~/.var/app/org.mozilla.firefox/.mozilla/firefox.
FXF = THUIS / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox"
(FXF / "xyz.default-release").mkdir(parents=True)
(FXF / "profiles.ini").write_text("[Profile0]\nName=default-release\nIsRelative=1\nPath=xyz.default-release\nDefault=1\n")
klopt(ff.standaard_profiel() == FXF / "xyz.default-release",
      "Firefox als Flatpak: BugOS vindt het profiel in ~/.var/app/org.mozilla.firefox")

# Instellingen, wifi en printers: wat erbij kwam, in het logboek (met de oude waarde).
lb.onthoud("instelling", naam="regio", oud="nl_NL")
lb.onthoud("instelling", naam="taal", oud="nl")
lb.onthoud("wifi", naam="Thuis-5G", uuid="01234567-89ab-cdef-0123-456789abcdef")
lb.onthoud("printer", wachtrij="HP_LaserJet", naam="HP LaserJet")
lb.ACTIEF.uitslagen([ot.Uitslag("bestanden", ot.GOED, "Je bestanden staan op hun plek.")])
klopt("LAPTOP-PIET" in lb.Logboek().samenvatting() and "wifi" in lb.Logboek().samenvatting(),
      f"logboek: de samenvatting noemt de computer en wat er kwam ({lb.Logboek().samenvatting()})")
lb.ACTIEF = None

# ============================================================================== terugdraaien ===
# Een bestand dat je na het overzetten zelf veranderde, blijft staan.
time.sleep(0.05)
_veranderd = THUIS / "Foto's 2019" / "Vakantie" / "strand.txt"
_veranderd.write_text("strand, met mijn eigen aantekening")
os.utime(_veranderd, (time.time() + 10, time.time() + 10))
_zet = []
bi.zet_taal = lambda c: _zet.append(("taal", c)) or True
bi.zet_regio = lambda c: _zet.append(("regio", c)) or True
LOG.write_text("")
uit = lb.terugdraaien()
_teksten = " | ".join(f"{x.deel}:{x.soort}:{x.tekst}" for x in uit)
PRUL = THUIS / ".local" / "share" / "Trash" / "files"
klopt(not (ob.lettertypen_map() / "MijnLetter.ttf").exists() and (PRUL / "MijnLetter.ttf").exists(),
      "terugdraaien: het lettertype staat in de prullenbak (niet echt weg)")
klopt(_veranderd.exists() and "strand.txt" in _teksten,
      "terugdraaien: een bestand dat je zelf veranderde, blijft staan (en dat staat erbij)")
klopt((THUIS / "Documents" / "brief.txt").read_text() == "mijn eigen brief",
      "terugdraaien: je eigen brief (stond er al) blijft precies zo")
klopt(not (THUIS / "Documents" / "Outlook-bestanden").exists(), "terugdraaien: de lege map Outlook-bestanden is weg")
klopt(_zet == [("taal", "nl"), ("regio", "nl_NL")], f"terugdraaien: eerst de taal, dan de notatie ({_zet})")
klopt("nmcli connection delete uuid 01234567-89ab-cdef-0123-456789abcdef" in log(),
      "terugdraaien: het wifi-netwerk van de stick gaat eruit (precies dat profiel, op uuid)")
klopt("lpadmin -x HP_LaserJet" in log(), "terugdraaien: de printer van je oude pc gaat eruit")
klopt(_profiel is not None and not _profiel.exists() and not (TBMAP / "profiles.ini").exists(),
      "terugdraaien: het Thunderbird-profiel naar de prullenbak, profiles.ini zoals het was (er was er geen)")
klopt(not lb.pad().exists() and any(lb.map_().glob("logboek-teruggedraaid-*.json")),
      "terugdraaien: het logboek heeft een andere naam (de volgende overstap begint schoon)")
klopt(lb.terugdraaien()[0].soort == ot.NIET, "terugdraaien zonder logboek: 'er is niets om terug te draaien'")

# ================================================================================= het venster ===
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or bugos_ui.maak_app("bugos-test", "bugos-test", ["test"])
bugos_ui.maak_app = lambda *a, **k: app
_gevangen: list = []
bugos_ui.uitvoeren = lambda _app, w: _gevangen.append(w) or 0


def wacht(voorwaarde, ms: int = 15000) -> bool:
    klok = QElapsedTimer()
    klok.start()
    while not voorwaarde() and klok.elapsed() < ms:
        app.processEvents()
    return voorwaarde()


os.environ["BUGOS_SCHIJVEN"] = str(TMP / "geen-schijven")
bo.venster()
w = _gevangen[-1]
w.show()
app.processEvents()
klopt(not w.terug.isVisibleTo(w), "venster: zonder logboek geen 'Alles terugdraaien'")
w.close()

# Een logboek met één bestand: dan staat het blok er, en de knop werkt.
_los = THUIS / "Documents" / "van-windows.txt"
_los.write_text("x")
boek = lb.Logboek()
boek.begin("WOONKAMER", "an")
boek.bestand_erbij(_los)
bo.venster()
w = _gevangen[-1]
w.show()
app.processEvents()
klopt(w.terug.isVisibleTo(w) and "WOONKAMER" in w.terug_tekst.text() and w.terug_knop.isEnabled(),
      f"venster: met een logboek staat 'Alles terugdraaien' er, met wat erin staat ({w.terug_tekst.text()[:70]})")
w.start_terugdraaien()
klopt(wacht(lambda: not w.bezig() and w.samenvatting.isVisibleTo(w)) and not _los.exists()
      and "Teruggedraaid" in w.melding.tekst.text() and not w.terug.isVisibleTo(w),
      "venster: terugdraaien zet het bestand in de prullenbak, zegt 'Teruggedraaid', en het blok verdwijnt")
w.close()

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{fouten} fout(en)")
sys.exit(1 if fouten else 0)
