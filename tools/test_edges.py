#!/usr/bin/env python3
"""Randgevallen en de fixes van de laatste verbeterronde (forge-work/test-plan.md).

- Bestanden, Back-up en Overstap met rare namen: accenten, emoji en een heel lange naam.
- Elk app-pictogram uit de .desktop-bestanden bestaat echt in het BugOS-thema (A036).
- bugos-exe vindt de Wine-kleuren (A036).
- Elk BugOS-programma en elk gedeeld onderdeel laadt (A034: na het opsplitsen mist er niets).
- De ISO-bouw weigert een rare bouwnaam (A035), en build.yml bouwt elke week en draait elke test (A031).

Alles gebeurt in tijdelijke mappen; je echte bestanden worden niet aangeraakt.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_edges.py   (rsync moet er zijn)
"""

from __future__ import annotations

import configparser
import importlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = ROOT / "system_files"
PYTHON = SYSTEM / "usr" / "lib" / "bugos" / "python"
sys.path.insert(0, str(PYTHON))

TMP = Path(tempfile.mkdtemp(prefix="bugos-edges-test-"))
THUIS = TMP / "thuis"
os.environ.update(HOME=str(THUIS), XDG_DATA_HOME=str(THUIS / ".local" / "share"),
                  XDG_CONFIG_HOME=str(THUIS / ".config"), BUGOS_LSBLK="", LC_ALL="nl_NL.UTF-8",
                  PATH="/usr/bin:/bin")  # geen xdg-user-dir: dan de standaardnamen
(THUIS / ".config").mkdir(parents=True)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(naam: str, pad: Path):
    lader = importlib.machinery.SourceFileLoader(naam, str(pad))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(naam, lader))
    sys.modules[naam] = mod  # nodig voor @dataclass
    lader.exec_module(mod)
    return mod


def schrijf(pad: Path, inhoud: bytes) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_bytes(inhoud)


RAAR = ["Zoë's verjaardag 🎂.odt", "Ça va — één.txt",
        "Een heel erg lange naam voor een brief aan de gemeente over het afval.txt"]  # 75 tekens

# F05-E1..E3: Bestanden, prullenbak en terug, kopiëren en verplaatsen met rare namen
b = laad("bestanden", SYSTEM / "usr" / "bin" / "bugos-files")
docs = THUIS / "Documenten"
docs.mkdir()
doel = THUIS / "Doel"
doel.mkdir()
for naam in RAAR:
    (docs / naam).write_text("inhoud " + naam, encoding="utf-8")
    bestand, info = b.naar_prullenbak(docs / naam)
    terug = b.terugzetten(bestand, info)
    klopt(terug == docs / naam and terug.read_text(encoding="utf-8") == "inhoud " + naam,
          f"bestanden: prullenbak en terug met de naam '{naam}'")
    kopie = b.kopieer_een(docs / naam, doel, False)
    klopt(kopie == doel / naam and (docs / naam).exists(), f"bestanden: kopiëren met de naam '{naam}'")
    tweede = b.kopieer_een(docs / naam, doel, False)
    klopt(tweede is not None and tweede != kopie and kopie.read_text(encoding="utf-8") == "inhoud " + naam,
          f"bestanden: tweede kopie overschrijft niets ('{tweede.name if tweede else '-'}')")
klopt(b.vrije_naam(docs / RAAR[0]).name == "Zoë's verjaardag 🎂 (2).odt",
      "bestanden: vrije naam houdt accent en emoji: 'Zoë's verjaardag 🎂 (2).odt'")
klopt(b.toon_naam(RAAR[0], False) == "Zoë's verjaardag 🎂", "bestanden: naam zonder extensie houdt accent en emoji")

# F04-E1: Back-up en terugzetten met rare namen (rsync)
bb = laad("bugos_backup", SYSTEM / "usr" / "bin" / "bugos-backup")
bb.gebruikersmap = lambda xdg, standaard: THUIS / standaard
SCHIJF = TMP / "stick"
SCHIJF.mkdir()
for naam in RAAR:
    schrijf(THUIS / "Documents" / naam, naam.encode())
klopt(bb.zonder_venster(SCHIJF) == 0, "back-up: lukt met accenten, emoji en een lange naam")
bdoel = bb.backup_doel(SCHIJF)
klopt(all((bdoel / "Documents" / n).read_bytes() == n.encode() for n in RAAR),
      "back-up: elk bestand staat met zijn eigen naam op de schijf")
NIEUW = TMP / "nieuwe-computer"  # de thuismap op de andere computer (bestaat altijd)
NIEUW.mkdir()
bb.gebruikersmap = lambda xdg, standaard: NIEUW / standaard  # terugzetten op een andere computer
for cmd in bb.terug_opdrachten(bdoel, NIEUW):
    subprocess.run(cmd, check=False, capture_output=True)
klopt(all((NIEUW / "Documents" / n).read_bytes() == n.encode() for n in RAAR),
      "terugzetten: elk bestand komt terug met zijn eigen naam")

# F03-E1/E2: Overstap van Windows met rare namen; bladwijzers met HTML in hun naam
bo = laad("bugos_overstap", SYSTEM / "usr" / "bin" / "bugos-switch")
bo.gebruikersmap = lambda xdg, standaard: THUIS / "van-windows" / standaard
(THUIS / "van-windows").mkdir()  # staat voor de thuismap, die er altijd is
WIN = TMP / "windows-stick" / "BugOS-Switch"
schrijf(WIN / "bugos-switch.json", json.dumps({"computer": "PC-VAN-ZOË"}).encode())
for naam in RAAR:
    schrijf(WIN / "Pictures" / naam, b"p")
klopt(bo.zonder_venster(WIN) == 0 and all((THUIS / "van-windows" / "Pictures" / n).exists() for n in RAAR),
      "overstap: bestanden met accenten, emoji en een lange naam komen over")
klopt(bo.info(WIN).get("computer") == "PC-VAN-ZOË", "overstap: de info met een accent wordt gelezen")
schrijf(WIN / "Bladwijzers" / "Edge.json", json.dumps({"roots": {"bar": {"name": "Balk & co", "children": [
    {"type": "url", "name": "<script>alert(1)</script>", "url": "https://example.org/?a=1&b=\"2\""}]}}}).encode())
html = bo.chrome_naar_html({"Edge": WIN / "Bladwijzers" / "Edge.json"})
klopt("<script>" not in html and "&lt;script&gt;" in html and 'a=1&amp;b=&quot;2&quot;' in html,
      "overstap: een bladwijzer met HTML in naam of adres wordt veilig in het bestand gezet")

# F03-E4 (B006): een stick met de nieuwe én de oude map (beide versies gebruikt) staat er één keer
BEIDE = TMP / "stick-beide"
schrijf(BEIDE / "BugOS-Switch" / "bugos-switch.json", json.dumps({"computer": "NIEUW"}).encode())
schrijf(BEIDE / "BugOS-Overstap" / "bugos-overstap.json", json.dumps({"computer": "OUD"}).encode())
os.environ["BUGOS_SCHIJVEN"] = str(BEIDE)
gevonden = bo.zoek_overstap()
klopt([m.name for m in gevonden] == ["BugOS-Switch"],
      f"overstap: een stick met beide mappen staat er één keer, met de nieuwe map ({[m.name for m in gevonden]})")
del os.environ["BUGOS_SCHIJVEN"]

# F12-H1 (A036): elk Icon= uit een BugOS-.desktop-bestand bestaat in het BugOS-pictogramthema
THEMA = SYSTEM / "usr" / "share" / "icons" / "BugOS"
# Wat de bouw zelf als pictogram neerlegt (zoals bugos-logo in hicolor), telt ook.
BOUW = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "build_files").glob("*.sh")))
desktops = sorted((SYSTEM / "usr" / "share" / "applications").glob("*.desktop")) + \
    sorted((ROOT / "iso_live" / "src").glob("*.desktop"))
ontbreekt = []
for d in desktops:
    ini = configparser.ConfigParser(interpolation=None, strict=False)
    ini.read(d, encoding="utf-8")
    icoon = ini.get("Desktop Entry", "Icon", fallback="")
    if icoon.startswith("bugos") and not list(THEMA.glob(f"*/*/{icoon}.svg")) \
            and f"/usr/share/icons/hicolor/scalable/apps/{icoon}.svg" not in BOUW:
        ontbreekt.append(f"{d.name}: {icoon}")
klopt(not ontbreekt, f"pictogrammen: elk BugOS-app-pictogram bestaat ({len(desktops)} .desktop-bestanden)"
      + (f"; mist: {ontbreekt}" if ontbreekt else ""))

# F13-H1 (A036): bugos-exe leest wine/<licht|donker>.reg; die moeten er allebei zijn
exe = (SYSTEM / "usr" / "bin" / "bugos-exe").read_text(encoding="utf-8")
klopt('KLEUREN="/usr/share/bugos/wine/$THEMA.reg"' in exe
      and all((SYSTEM / "usr" / "share" / "bugos" / "wine" / f"{t}.reg").is_file() for t in ("licht", "donker")),
      "wine-kleuren: licht.reg en donker.reg, de namen die bugos-exe zoekt, staan klaar")

# F14-H1 (A034): elk Python-programma en elk gedeeld onderdeel laadt, zonder dat er iets mist
import bugos_ui  # noqa: E402,F401  (eerst de ouders: de onderdelen laden via hen)
import bugos_config  # noqa: E402,F401
import bugos_tasks  # noqa: E402,F401
for pad in sorted(PYTHON.glob("*.py")):
    try:
        importlib.import_module(pad.stem)
        gelukt = True
    except Exception as e:  # noqa: BLE001  (elke fout telt)
        gelukt = False
        print("      ", type(e).__name__, e)
    klopt(gelukt, f"onderdelen: {pad.name} laadt")
programmas = [p for p in sorted((SYSTEM / "usr" / "bin").glob("bugos-*"))
              if p.read_text(encoding="utf-8", errors="replace").startswith("#!/usr/bin/python3")]
for pad in programmas:
    try:
        laad("prog_" + pad.name.replace("-", "_"), pad)
        gelukt = True
    except SystemExit:
        gelukt = True  # een programma dat bij het laden al stopt (geen venster nodig): laadt wel
    except Exception as e:  # noqa: BLE001
        gelukt = False
        print("      ", type(e).__name__, e)
    klopt(gelukt, f"programma's: {pad.name} laadt")

# F15-N1 (A035): de ISO-bouw weigert een bouwnaam die een opdracht zou kunnen zijn
iso = (ROOT / ".github" / "workflows" / "iso.yml").read_text(encoding="utf-8")
patronen = re.findall(r'\[\[ "\$TAG" =~ (\S+) \]\]', iso)
klopt(len(patronen) == 2 and "${{ inputs.tag }}" not in "".join(
    regel for regel in iso.splitlines() if not regel.strip().startswith(("TAG:", "name:"))),
      "iso.yml: beide stappen lezen de bouwnaam via env en controleren hem")
if patronen:
    p = re.compile(patronen[0])
    klopt(all(p.fullmatch(t) for t in ("latest", "claude-fix-x", "2026.11.07"))
          and not any(p.fullmatch(t) for t in ("x;id", "$(id)", "a b", "`id`", "", "-x")),
          "iso.yml: 'latest' en branchnamen mogen, ';', '$( )', spaties en backticks niet")

# F10-H1 (A031): build.yml bouwt vanzelf (elke week) en draait elke test uit tools/
bouw = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
aan = bouw.split("\njobs:")[0]
klopt(re.search(r"^  schedule:\n    - cron: \"[^\"]+\"", aan, re.M) is not None and "workflow_dispatch:" in aan,
      "build.yml: bouwt vanzelf volgens een schema, en met de hand")
klopt("needs: controle" in bouw, "build.yml: bouwen gebeurt pas na de controle")
tests = sorted(p.name for p in (ROOT / "tools").glob("test_*") if p.suffix in (".py", ".sh"))
mist = [t for t in tests if f"tools/{t}" not in bouw]
klopt(not mist, f"build.yml: draait elke test uit tools/ ({len(tests)})" + (f"; mist: {mist}" if mist else ""))

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
