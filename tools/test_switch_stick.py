#!/usr/bin/env python3
"""Test van 'Haal alles van je oude pc': de USB-schijf van BugOS Switch vinden en openzetten.

Een echte melding (2026-11-24): stick van het Windows-programma erin, en het venster bleef 'Steek de USB-schijf met
je Windows-spullen in…' zeggen. KDE zet een stick niet vanzelf open; BugOS deed dat één keer per schijf, en lukte
die ene keer niet (net ingestoken, udisks kent hem nog niet; een NTFS die Windows niet netjes afsloot), dan nooit
meer. Wat we hier testen, met een nep-lsblk (BUGOS_LSBLK), een nep-/proc/self/mountinfo (BUGOS_PROC) en een
nep-udisksctl die de 'stick' echt openzet (een map in een tijdelijke map); aan je eigen computer verandert niets:
  - een stick die er net in zit, gaat open zonder wachtwoordvraag (--no-user-interaction) en staat er binnen een
    paar seconden, ook als de eerste keer openen mislukt;
  - een NTFS-schijf die alleen alleen-lezen open wil, gaat alleen-lezen open (Overstap leest alleen);
  - 'mag niet' van udisks: niet steeds opnieuw; een kapotte stick: na een paar keer niet meer; dichtgezet door jou:
    niet zelf weer open; eruit en weer erin: weer open; lsblk even leeg: niets vergeten;
  - een stick op slot (BitLocker) of zonder map BugOS-Switch: het venster zegt dat, in plaats van 'steek hem in';
  - bugos-switch.json in elke codering die PowerShell schrijft (UTF-8 met/zonder BOM, UTF-16, cp1252), andere
    hoofdletters, en een stick waar het infobestand ontbreekt (eruit getrokken voordat Windows klaar was);
  - het venster: stick erin terwijl het open is -> binnen een paar seconden de kaart en het overzicht.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_switch_stick.py
"""

from __future__ import annotations

import codecs
import importlib.machinery
import importlib.util
import json
import os
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

TMP = Path(tempfile.mkdtemp(prefix="bugos-switch-stick-"))
THUIS = TMP / "thuis"
(THUIS / ".config").mkdir(parents=True)
LSBLK = TMP / "lsblk.json"
PROC = TMP / "proc"
(PROC / "self").mkdir(parents=True)
MOUNTINFO = PROC / "self" / "mountinfo"
NEP = TMP / "nep-bin"
NEP.mkdir()
PLAN = TMP / "plan.json"
LOG = TMP / "udisksctl.log"
MEDIA = TMP / "media"          # hier 'staan' de sticks; zichtbaar pas als ze in de nep-mountinfo staan
MEDIA.mkdir()
os.environ.update(HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), XDG_DATA_HOME=str(THUIS / ".local/share"),
                  XDG_CACHE_HOME=str(THUIS / ".cache"), LC_ALL="nl_NL.UTF-8", LANG="nl_NL.UTF-8",
                  BUGOS_LSBLK=str(LSBLK), BUGOS_PROC=str(PROC), NEP_PLAN=str(PLAN), NEP_LOG=str(LOG),
                  NEP_MEDIA=str(MEDIA), PATH=f"{NEP}:{os.environ['PATH']}")
for weg in ("LANGUAGE", "BUGOS_SCHIJVEN", "BUGOS_INSTELLINGEN_VOORBEELD", "XDG_RUNTIME_DIR"):
    os.environ.pop(weg, None)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


# ======================================================================= nep-programma's ===
# udisksctl: elke aanroep in het logboek; het antwoord uit het plan (een lijst, de eerste gaat eraf). Een antwoord met
# "open": de stick gaat open: in lsblk en in mountinfo staat hij dan op NEP_MEDIA/<label>. Leeg plan: gewoon open.
(NEP / "udisksctl").write_text(r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ["NEP_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
plan = Path(os.environ["NEP_PLAN"])
stappen = json.loads(plan.read_text()) if plan.exists() else []
stap = stappen.pop(0) if stappen else {"code": 0, "uit": "", "open": True}
plan.write_text(json.dumps(stappen))
if sys.argv[1:2] == ["mount"] and stap.get("open"):
    apparaat = sys.argv[sys.argv.index("-b") + 1]
    lsblk = Path(os.environ["BUGOS_LSBLK"])
    data = json.loads(lsblk.read_text())
    for station in data["blockdevices"]:
        for deel in [station] + station.get("children", []):
            if deel.get("path") == apparaat:
                plek = os.path.join(os.environ["NEP_MEDIA"], deel.get("label") or "schijf")
                deel["mountpoints"] = [plek]
                deel["fsavail"], deel["fssize"] = 10**9, 16 * 10**9
                soort = deel.get("fstype")
    lsblk.write_text(json.dumps(data))
    mi = Path(os.environ["BUGOS_PROC"]) / "self" / "mountinfo"
    opties = "ro" if "ro" in sys.argv else "rw"
    with open(mi, "a") as f:
        f.write(f"90 1 8:17 / {plek} {opties},nosuid,nodev - {soort} {apparaat} {opties}\n")
    print(f"Mounted {apparaat} at {plek}")
sys.stderr.write(stap.get("uit", ""))
sys.exit(stap.get("code", 0))
''')
(NEP / "udisksctl").chmod(0o755)

SYSTEEM_MI = "22 1 252:1 / / rw,relatime - ext4 /dev/vda1 rw\n23 22 252:1 /var/home /var/home rw - ext4 /dev/vda1 rw\n"


def zet_schijven(stick: dict | None = None) -> None:
    """De nep-lsblk: de schijf van BugOS zelf, en (als 'stick') een USB-stick met één partitie."""
    apparaten = [{"name": "vda", "kname": "vda", "path": "/dev/vda", "type": "disk", "size": 64 * 10**9, "rm": False,
                  "hotplug": False, "tran": None, "mountpoints": [None],
                  "children": [{"name": "vda1", "kname": "vda1", "path": "/dev/vda1", "type": "part",
                                "size": 64 * 10**9, "fstype": "ext4", "mountpoints": ["/", "/var/home"]}]}]
    if stick is not None:
        deel = {"name": "sdb1", "kname": "sdb1", "path": "/dev/sdb1", "type": "part", "size": 16 * 10**9,
                "fstype": "exfat", "label": "STICK", "parttype": "0x7", "mountpoints": [None]}
        deel.update(stick)
        apparaten.append({"name": "sdb", "kname": "sdb", "path": "/dev/sdb", "type": "disk", "size": 16 * 10**9,
                          "rm": True, "hotplug": True, "tran": "usb", "model": "Cruzer", "mountpoints": [None],
                          "children": [deel]})
    LSBLK.write_text(json.dumps({"blockdevices": apparaten}))


def dicht() -> None:
    """Geen stick open: alleen het systeem in mountinfo."""
    MOUNTINFO.write_text(SYSTEEM_MI)


def plan(*stappen: dict) -> None:
    PLAN.write_text(json.dumps(list(stappen)))
    LOG.write_text("")


def aanroepen() -> list[str]:
    return [r for r in LOG.read_text().splitlines() if r.startswith("mount")] if LOG.exists() else []


def maak_stick(label: str, info: dict | None = None, map_naam: str = "BugOS-Switch",
               bestand: str = "bugos-switch.json") -> Path:
    """De inhoud van een stick zoals het Windows-programma hem schrijft (met Set-Content -Encoding UTF8: met BOM)."""
    m = MEDIA / label / map_naam
    (m / "Documents").mkdir(parents=True, exist_ok=True)
    (m / "Documents" / "brief.txt").write_text("hallo")
    if info is not None:
        (m / bestand).write_bytes(codecs.BOM_UTF8 + json.dumps(info).encode("utf-8"))
    return m


import bugos_drives as bd  # noqa: E402
import bugos_overstap_toepassen as ot  # noqa: E402

ot.OPEN_WACHT = (0.2, 0.2, 0.2, 0.2)   # in de test niet seconden wachten tussen de pogingen


def opnieuw() -> None:
    """Een nieuwe start (zoals een nieuw venster): niets onthouden van de vorige proef."""
    wacht_draad()
    ot._pogingen.clear()
    ot._losse.clear()


def wacht_draad(s: float = 10.0) -> None:
    eind = time.monotonic() + s
    while ot.openen_bezig() and time.monotonic() < eind:
        time.sleep(0.02)


def kijk(s: float = 5.0) -> tuple[list[Path], float]:
    """Doe wat het venster doet: steeds opnieuw zoek_overstap(), tot de stick er is (of de tijd om is)."""
    begin = time.monotonic()
    while time.monotonic() - begin < s:
        gevonden = ot.zoek_overstap()
        if gevonden:
            return gevonden, time.monotonic() - begin
        time.sleep(0.1)
    return [], time.monotonic() - begin


GELEZEN = {"versie": 2, "gebruiker": "José", "computer": "WOONKAMER"}
NIET_KLAAR = {"code": 1, "uit": "Error looking up object for device /dev/sdb1\n"}
VUIL_NTFS = {"code": 1, "uit": "Error mounting /dev/sdb1: GDBus.Error:org.freedesktop.UDisks2.Error.Failed: Error "
                              "mounting /dev/sdb1 at /run/media/bugie/HDD: wrong fs type, bad option, bad superblock "
                              "on /dev/sdb1, missing codepage or helper program, or other error\n"}
MAG_NIET = {"code": 1, "uit": "Error mounting /dev/sdb1: GDBus.Error:org.freedesktop.UDisks2.Error."
                             "NotAuthorizedCanObtain: Not authorized to perform operation\n"}
OPEN = {"code": 0, "open": True}

# ================================================================ de stick gaat vanzelf open ===
klopt("-Encoding UTF8" in (ROOT / "windows-switch" / "BugOS-Switch.ps1").read_text(encoding="utf-8")
      and "'bugos-switch.json'" in (ROOT / "windows-switch" / "BugOS-Switch.ps1").read_text(encoding="utf-8")
      and ot.MAPPEN[0] == ("BugOS-Switch", "bugos-switch.json"),
      "contract: Windows schrijft BugOS-Switch/bugos-switch.json met Set-Content -Encoding UTF8 (in PowerShell 5.1: "
      "met BOM), en BugOS zoekt precies die namen")

dicht()
zet_schijven(None)
plan()
klopt(ot.zoek_overstap() == [] and aanroepen() == [], "geen stick: niets gevonden, niets opengezet")

opnieuw()
maak_stick("STICK", GELEZEN)
zet_schijven({})
plan(NIET_KLAAR, OPEN)
gevonden, duur = kijk()
klopt(len(gevonden) == 1 and gevonden[0] == MEDIA / "STICK" / "BugOS-Switch" and duur < 3,
      f"net ingestoken, de eerste keer openen mislukt (udisks kent hem nog niet): BugOS probeert het opnieuw en vindt "
      f"de stick toch, binnen {duur:.1f} s")
klopt(len(aanroepen()) == 2 and all("--no-user-interaction" in a and "-b /dev/sdb1" in a for a in aanroepen())
      and not any("-o ro" in a for a in aanroepen()),
      f"openen zonder wachtwoordvraag (--no-user-interaction), en niet alleen-lezen als udisks alleen nog niet klaar "
      f"was ({aanroepen()})")
klopt(ot.info(gevonden[0]).get("gebruiker") == "José" and ot.stick_melding(gevonden) == ("", ""),
      "de stick is gevonden: bugos-switch.json (UTF-8 met BOM) gelezen, en geen melding meer")

# Jij zet hem dicht (Bestanden of het KDE-meldingsvak): dan niet zelf weer open (U164).
wacht_draad()
zet_schijven({})
dicht()
plan()
for _ in range(4):
    ot.zoek_overstap()
    wacht_draad()
_m = ot.stick_melding([])
klopt(aanroepen() == [] and "staat dicht" in _m[0],
      f"zelf dichtgezet: BugOS zet hem niet weer open, en zegt dat hij dicht staat ({_m[0][:50]})")
# lsblk geeft even niets: niets vergeten (U200).
LSBLK.write_text("")
ot.zoek_overstap()
wacht_draad()
zet_schijven({})
ot.zoek_overstap()
wacht_draad()
klopt(aanroepen() == [], "lsblk gaf even niets: de dichtgezette stick blijft dicht (niets vergeten)")
# Eruit en weer erin: weer open (U183).
zet_schijven(None)
ot.zoek_overstap()
wacht_draad()
zet_schijven({})
plan(OPEN)
gevonden, duur = kijk()
klopt(len(gevonden) == 1 and len(aanroepen()) == 1, "eruit en weer erin: hij gaat weer vanzelf open")

# NTFS die Windows niet netjes afsloot: schrijven mag niet, lezen wel.
opnieuw()
dicht()
maak_stick("HDD", GELEZEN)
zet_schijven({"fstype": "ntfs", "label": "HDD"})
plan(VUIL_NTFS, OPEN)
gevonden, duur = kijk()
klopt(len(gevonden) == 1 and len(aanroepen()) == 2 and "-o ro" in aanroepen()[1] and "-o ro" not in aanroepen()[0]
      and ot._pogingen["/dev/sdb1"].alleen_lezen,
      f"NTFS die niet netjes afgesloten is: eerst gewoon, dan alleen-lezen open, en gevonden ({aanroepen()})")

# udisks zegt 'mag niet': één keer vragen, niet steeds opnieuw (en nooit met een wachtwoordvraag).
opnieuw()
dicht()
zet_schijven({})
plan(MAG_NIET, MAG_NIET, MAG_NIET)
gevonden, duur = kijk(1.5)
wacht_draad()
_m = ot.stick_melding(gevonden)
klopt(gevonden == [] and len(aanroepen()) == 1 and "krijgt hem niet open" in _m[0] and _m[1] == "let_op",
      f"'mag niet' van udisks: één keer gevraagd, en het venster zegt wat je kunt doen ({len(aanroepen())}x)")

# Een kapotte stick: na vijf keer (gewoon en alleen-lezen) niet meer.
opnieuw()
dicht()
zet_schijven({})
plan(*[VUIL_NTFS] * 20)
gevonden, duur = kijk(3)
wacht_draad()
ot.zoek_overstap()
wacht_draad()
_m = ot.stick_melding(gevonden)
klopt(gevonden == [] and len(aanroepen()) == 2 * (len(ot.OPEN_WACHT) + 1) and "krijgt hem niet open" in _m[0],
      f"kapotte stick: {len(ot.OPEN_WACHT) + 1} pogingen, daarna niet meer ({len(aanroepen())} aanroepen)")

# Op slot (BitLocker): niet zelf openzetten (dat vraagt een sleutel), wel zeggen.
opnieuw()
dicht()
zet_schijven({"fstype": "BitLocker", "label": None})
plan()
ot.zoek_overstap()
wacht_draad()
_m = ot.stick_melding([])
klopt(aanroepen() == [] and "op slot" in _m[0] and "Bestanden" in _m[0],
      f"stick op slot (BitLocker): niet zelf open, wel zeggen dat je hem in Bestanden opent ({_m[0][:40]})")

# Open, maar zonder map BugOS-Switch: zeggen, niet stil 'steek hem in'.
opnieuw()
dicht()
(MEDIA / "LEEG").mkdir()
zet_schijven({"label": "LEEG"})
plan(OPEN)
gevonden, duur = kijk(1.5)
wacht_draad()
_m = ot.stick_melding(gevonden)
klopt(gevonden == [] and len(aanroepen()) == 1 and "geen map BugOS-Switch" in _m[0] and "LEEG" in _m[0],
      f"stick zonder map BugOS-Switch: het venster zegt het ({_m[0][:50]})")

# Een stick die ergens anders open staat dan /run/media/<naam> (hier: in mountinfo): ook gevonden.
opnieuw()
zet_schijven(None)
plan()
_elders = TMP / "mnt" / "usb"
(_elders / "BugOS-Switch").mkdir(parents=True)
(_elders / "BugOS-Switch" / "bugos-switch.json").write_text("{}")
MOUNTINFO.write_text(SYSTEEM_MI + f"91 1 8:33 / {_elders} rw - vfat /dev/sdc1 rw\n")
klopt(ot.zoek_overstap(openen=False) == [_elders / "BugOS-Switch"],
      "een stick die ergens anders open staat (/mnt/usb, uit mountinfo): ook gevonden")
klopt(not any(p == Path("/var/home") or p == Path("/") for p in ot._open_plekken()),
      "mountinfo: de plekken van het systeem zelf (/, /var/home) doorzoeken we niet")
dicht()

# ===================================================== bugos-switch.json zoals Windows hem schrijft ===
_j = json.dumps({"versie": 2, "gebruiker": "José", "computer": "WOONKAMER", "extra": [{"naam": "Foto's"}]},
                ensure_ascii=False, indent=4).replace("\n", "\r\n")
for naam, data in (("UTF-8 zonder BOM (PowerShell 7)", _j.encode("utf-8")),
                   ("UTF-8 met BOM (Set-Content -Encoding UTF8)", codecs.BOM_UTF8 + _j.encode("utf-8")),
                   ("UTF-16 LE met BOM (Out-File, >)", _j.encode("utf-16")),
                   ("UTF-16 BE met BOM", codecs.BOM_UTF16_BE + _j.encode("utf-16-be")),
                   ("UTF-16 LE zonder BOM", _j.encode("utf-16-le")),
                   ("UTF-32 met BOM", _j.encode("utf-32")),
                   ("cp1252 (Set-Content zonder -Encoding)", _j.encode("cp1252"))):
    _m = TMP / "codering" / naam.split(" (")[0].replace(" ", "-") / "BugOS-Switch"
    _m.mkdir(parents=True)
    (_m / "bugos-switch.json").write_bytes(data)
    _i = ot.info(_m)
    klopt(_i.get("gebruiker") == "José" and _i.get("extra") == [{"naam": "Foto's"}],
          f"bugos-switch.json in {naam}: goed gelezen ({_i.get('gebruiker')!r})")
_m = TMP / "codering" / "kapot" / "BugOS-Switch"
_m.mkdir(parents=True)
(_m / "bugos-switch.json").write_bytes(b"")
klopt(ot.info(_m) == {} and ot._op_schijf(_m.parent) == [_m], "een leeg bugos-switch.json: {} (geen crash), wel gevonden")

# Andere hoofdletters (op NTFS let Linux daarop, Windows niet).
_s = TMP / "hoofdletters"
(_s / "bugos-switch").mkdir(parents=True)
(_s / "bugos-switch" / "BUGOS-SWITCH.JSON").write_text('{"gebruiker": "Oma"}')
klopt(ot._op_schijf(_s) == [_s / "bugos-switch"] and ot.info(_s / "bugos-switch").get("gebruiker") == "Oma",
      "map en bestand met andere hoofdletters (bugos-switch/BUGOS-SWITCH.JSON): gevonden en gelezen")
# Geen infobestand: Windows schrijft het als laatste. Met de mappen erop: toch gevonden, als versie 1.
_s = TMP / "zonder-info"
(_s / "BugOS-Switch" / "Pictures").mkdir(parents=True)
klopt(ot._op_schijf(_s) == [_s / "BugOS-Switch"] and ot.info(_s / "BugOS-Switch") == {}
      and [o.sleutel for o in ot.onderdelen(_s / "BugOS-Switch")] == ["bestanden"],
      "geen bugos-switch.json (stick te vroeg uitgetrokken), wel de mappen: gevonden, alleen de bestanden")
_s = TMP / "lege-map"
(_s / "BugOS-Switch").mkdir(parents=True)
klopt(ot._op_schijf(_s) == [], "een lege map BugOS-Switch (zonder infobestand en zonder mappen): niet gevonden")
# Beide versies: de nieuwe telt.
_s = TMP / "beide"
for _n, _b in ot.MAPPEN:
    (_s / _n).mkdir(parents=True)
    (_s / _n / _b).write_text("{}")
klopt(ot._op_schijf(_s) == [_s / "BugOS-Switch"], "BugOS-Switch en het oude BugOS-Overstap: alleen de nieuwe")

# ========================================================================== het venster ===
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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
        time.sleep(0.01)
    return voorwaarde()


opnieuw()
ot.OPEN_WACHT = (1.0, 2.0, 4.0, 8.0)   # in het venster zoals echt
dicht()
zet_schijven(None)
plan()
bo = laad("bugos_overstap_stick", "bugos-switch")
bo.venster()
w = _gevangen[-1]
w.show()
app.processEvents()
klopt(not w.kiezer.kaarten and w.kiezer.leeg.isVisibleTo(w) and not w.melding.isVisibleTo(w),
      "venster zonder stick: 'Steek de USB-schijf in…', geen melding")
# Nu de stick erin (dicht, zoals KDE hem laat), en de eerste keer openen mislukt.
zet_schijven({})
plan(NIET_KLAAR, OPEN)
_klok = time.monotonic()
klopt(wacht(lambda: bool(w.kiezer.kaarten), 12000),
      f"venster open, stick erin: binnen {time.monotonic() - _klok:.1f} s staat hij erin, zonder iets te doen")
klopt(wacht(lambda: bool(w.schakelaars) and w.knop.isEnabled(), 3000) and "bestanden" in w.schakelaars
      and not w.kiezer.leeg.isVisibleTo(w) and not w.melding.isVisibleTo(w)
      and len(aanroepen()) == 2 and all("--no-user-interaction" in a for a in aanroepen()),
      f"venster: het overzicht van de stick staat er (schuifjes, Overzetten aan), geen melding ({sorted(w.schakelaars)})")
klopt(any("José" in k._teksten[1].text() and "WOONKAMER" in k._teksten[1].text() for k in w.kiezer.kaarten.values()),
      "venster: de kaart noemt van wie en van welke computer (uit bugos-switch.json met BOM)")
# Eruit (lsblk en mountinfo zonder stick): de kaart gaat weg.
zet_schijven(None)
dicht()
klopt(wacht(lambda: not w.kiezer.kaarten, 8000), "venster: stick eruit, de kaart gaat weg")
# Een andere stick zonder map BugOS-Switch: het venster zegt het.
zet_schijven({"label": "LEEG", "path": "/dev/sdb1"})
plan(OPEN)
klopt(wacht(lambda: "geen map BugOS-Switch" in w.melding.tekst.text() and w.melding.isVisibleTo(w), 12000),
      f"venster: een stick zonder map BugOS-Switch: dat staat in de meldingsbalk ({w.melding.tekst.text()[:50]})")
zet_schijven(None)
dicht()
klopt(wacht(lambda: not w.melding.isVisibleTo(w), 8000), "venster: stick eruit, de melding gaat ook weg")
w.close()
app.processEvents()

print(f"\n{fouten} fout(en)")
sys.exit(1 if fouten else 0)
