#!/usr/bin/env python3
"""Test van BugOS Back-up (zonder venster): ruimte, back-up maken en terugzetten, met nep-mappen.
Er verandert niets aan je computer: thuis en de USB-schijf zijn tijdelijke mappen.

Gebruik:  python3 tools/test_backup.py   (rsync moet er zijn)
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))
TMP = Path(tempfile.mkdtemp(prefix="bugos-backup-test-"))
THUIS, SCHIJF = TMP / "thuis", TMP / "stick"
THUIS.mkdir()
SCHIJF.mkdir()
os.environ.update(HOME=str(THUIS), XDG_CONFIG_HOME=str(THUIS / ".config"), LC_ALL="nl_NL.UTF-8",
                  PATH="/usr/bin:/bin")  # geen xdg-user-dir nodig: dan de standaardnamen

lader = importlib.machinery.SourceFileLoader("bugos_backup", str(ROOT / "system_files" / "usr" / "bin" / "bugos-backup"))
spec = importlib.util.spec_from_loader("bugos_backup", lader)
bb = importlib.util.module_from_spec(spec)
lader.exec_module(bb)
bb.gebruikersmap = lambda xdg, standaard: THUIS / standaard  # vaste plek, wat de computer ook zegt

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def schrijf(pad: Path, inhoud: bytes) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_bytes(inhoud)


# 1. ruimte: alleen wat nieuw of veranderd is, telt
schrijf(THUIS / "Documents" / "brief.txt", b"x" * 1000)
schrijf(THUIS / "Pictures" / "foto.jpg", b"y" * 5000)
mappen = bb.bron_mappen()
doel = bb.backup_doel(SCHIJF)
_, nodig, _ = bb.ruimte_genoeg(SCHIJF, mappen, doel)
klopt(nodig == 6000, "ruimte: eerste keer telt alles (6000 bytes)")
klopt(bb.zonder_venster(SCHIJF) == 0 and (doel / "Pictures" / "foto.jpg").read_bytes() == b"y" * 5000,
      "back-up: de foto staat op de schijf")
schrijf(THUIS / "Documents" / "nieuw.txt", b"z" * 300)
_, nodig, _ = bb.ruimte_genoeg(SCHIJF, mappen, doel)
klopt(nodig == 300, "ruimte: daarna alleen wat nieuw is (300 bytes), niet alles opnieuw")

# 2. een paar bestanden kunnen niet mee (rsync 23): de andere mappen gaan gewoon door
NEP = TMP / "nep-bin"
NEP.mkdir()
(NEP / "rsync").write_text('#!/usr/bin/bash\ncase "$*" in *Documents*) exit 23;; esac\nexec /usr/bin/rsync "$@"\n')
(NEP / "rsync").chmod(0o755)
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"
schrijf(THUIS / "Pictures" / "vakantie.jpg", b"v" * 10)
code = bb.zonder_venster(SCHIJF)
klopt(code == 2 and (doel / "Pictures" / "vakantie.jpg").exists(),
      "deels: Documents lukt niet helemaal, Pictures (erna) wordt toch gekopieerd, met een melding")

lader = importlib.machinery.SourceFileLoader("bugos_overstap",
                                             str(ROOT / "system_files" / "usr" / "bin" / "bugos-overstap"))
spec = importlib.util.spec_from_loader("bugos_overstap", lader)
bo = importlib.util.module_from_spec(spec)
lader.exec_module(bo)
bo.gebruikersmap = lambda xdg, standaard: THUIS / "nieuw" / standaard
(THUIS / "nieuw").mkdir()
WIN = TMP / "windows-stick" / "BugOS-Overstap"
schrijf(WIN / "Documents" / "cv.docx", b"c")
schrijf(WIN / "Pictures" / "kat.jpg", b"k")
code = bo.zonder_venster(WIN)
klopt(code == 2 and (THUIS / "nieuw" / "Pictures" / "kat.jpg").exists(),
      "overstap deels: Documents lukt niet helemaal, Pictures wordt toch teruggezet")
os.environ["PATH"] = "/usr/bin:/bin"

# 3. terugzetten na opnieuw installeren: de computer heet anders, de oude back-up moet je toch zien
oud = SCHIJF / "BugOS-Backup" / "bugie@oude-laptop"
schrijf(oud / "Documents" / "oud.txt", b"o")
lijst = bb.backups_op(SCHIJF)
klopt(lijst[0] == doel and oud in lijst, "terugzetten: eigen back-up eerst, die van een andere computer staat er ook")
leeg = TMP / "lege-stick"
schrijf(leeg / "BugOS-Backup" / "bugie@oude-laptop" / "Music" / "lied.mp3", b"m")
klopt(bb.backups_op(leeg) == [leeg / "BugOS-Backup" / "bugie@oude-laptop"],
      "terugzetten: alleen een back-up van een andere computer, die wordt gevonden")
klopt(bb.backups_op(TMP / "bestaat-niet") == [], "terugzetten: schijf zonder back-up, geen fout")

# 4. links gaan mee, en elke map komt terug in de echte map (ook als die in een andere taal heet)
(THUIS / "Documents" / "snelkoppeling").symlink_to("brief.txt")
klopt(bb.zonder_venster(SCHIJF) == 0 and (doel / "Documents" / "snelkoppeling").is_symlink(),
      "back-up: een snelkoppeling (symlink) gaat mee")
klopt(json.loads((doel / bb.LIJSTJE).read_text()).get("PICTURES") == "Pictures",
      "back-up: lijstje met welke map welke soort is")
nl = TMP / "nl-stick" / "BugOS-Backup" / "bugie@oud"
schrijf(nl / "Afbeeldingen" / "kat.jpg", b"k")
schrijf(nl / "Eigen map" / "x.txt", b"x")
(nl / bb.LIJSTJE).write_text(json.dumps({"PICTURES": "Afbeeldingen"}))
naar = {Path(c[-2].rstrip("/")).name: c[-1].rstrip("/") for c in bb.terug_opdrachten(nl, THUIS)}
klopt(naar == {"Afbeeldingen": str(THUIS / "Pictures"), "Eigen map": str(THUIS / "Eigen map")},
      "terugzetten: 'Afbeeldingen' gaat naar de afbeeldingenmap van deze computer, een eigen map naar thuis")
oud_stijl = TMP / "oude-stick"
schrijf(oud_stijl / "Music" / "lied.mp3", b"m")
klopt([c[-1].rstrip("/") for c in bb.terug_opdrachten(oud_stijl, THUIS)] == [str(THUIS / "Music")],
      "terugzetten: een back-up zonder lijstje werkt ook (Engelse namen)")

print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
