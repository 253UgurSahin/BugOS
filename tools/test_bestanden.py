#!/usr/bin/env python3
"""Test of BugOS Bestanden veilig met je bestanden omgaat.

Alles gebeurt in een tijdelijke map; je echte bestanden worden niet aangeraakt.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_bestanden.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))

TMP = Path(tempfile.mkdtemp(prefix="bugos-bestanden-test-"))
os.environ["HOME"] = str(TMP / "thuis")
os.environ["XDG_DATA_HOME"] = str(TMP / "thuis" / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(TMP / "thuis" / ".config")
os.environ["BUGOS_USB"] = ""
(TMP / "thuis" / ".config").mkdir(parents=True)

lader = importlib.machinery.SourceFileLoader("bestanden", str(ROOT / "system_files" / "usr" / "bin" / "bugos-bestanden"))
spec = importlib.util.spec_from_loader("bestanden", lader)
b = importlib.util.module_from_spec(spec)
lader.exec_module(b)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


thuis = TMP / "thuis"
docs = thuis / "Documenten"
docs.mkdir()
(docs / "brief.txt").write_text("hallo oma")
(docs / "map").mkdir()
(docs / "map" / "binnen.txt").write_text("binnenin")

# 1. vrije namen: nooit overschrijven
klopt(b.vrije_naam(docs / "nieuw.txt") == docs / "nieuw.txt", "vrije naam: bestaat niet, blijft gelijk")
klopt(b.vrije_naam(docs / "brief.txt") == docs / "brief (2).txt", "vrije naam: bestaat al, wordt 'brief (2).txt'")
klopt(b.vrije_naam(docs / "map") == docs / "map (2)", "vrije naam: map bestaat al, wordt 'map (2)'")

# 2. naar de prullenbak en weer terug
bestand, info = b.naar_prullenbak(docs / "brief.txt")
klopt(not (docs / "brief.txt").exists(), "prullenbak: bestand is weg uit Documenten")
klopt(bestand.exists() and info.exists(), "prullenbak: bestand en info staan in de prullenbak")
klopt(b.lees_herkomst(info) == docs / "brief.txt", "prullenbak: weet waar het vandaan kwam")
inhoud = b.prullenbak_inhoud()
klopt(len(inhoud) == 1 and inhoud[0][0] == bestand, "prullenbak: inhoud toont het bestand")
terug = b.terugzetten(bestand, info)
klopt(terug == docs / "brief.txt" and terug.read_text() == "hallo oma", "terugzetten: weer op de oude plek, inhoud heel")
klopt(not info.exists(), "terugzetten: info-bestand opgeruimd")

# 3. twee keer hetzelfde weggooien: geen botsing
(docs / "kopie.txt").write_text("een")
b1, i1 = b.naar_prullenbak(docs / "kopie.txt")
(docs / "kopie.txt").write_text("twee")
b2, i2 = b.naar_prullenbak(docs / "kopie.txt")
klopt(b1 != b2 and b1.read_text() == "een" and b2.read_text() == "twee", "prullenbak: twee keer dezelfde naam, allebei bewaard")

# 4. terugzetten als er inmiddels iets anders staat: niets overschrijven
(docs / "kopie.txt").write_text("nieuw")
t1 = b.terugzetten(b1, i1)
klopt((docs / "kopie.txt").read_text() == "nieuw" and t1.read_text() == "een", "terugzetten: bestaand bestand blijft heel")

# 5. een oud bestand in de prullenbak zonder info wordt niet overschreven
wees = thuis / ".local" / "share" / "Trash" / "files" / "wees.txt"
wees.write_text("oud")
(docs / "wees.txt").write_text("nieuw")
b3, _i3 = b.naar_prullenbak(docs / "wees.txt")
klopt(wees.read_text() == "oud" and b3.read_text() == "nieuw", "prullenbak: los bestand zonder info blijft heel")

# 6. kopiëren en verplaatsen
doel = thuis / "Bureaublad"
doel.mkdir()
k = b.kopieer_een(docs / "map", doel, verplaats=False)
klopt(k == doel / "map" and (doel / "map" / "binnen.txt").read_text() == "binnenin", "kopiëren: map met inhoud gekopieerd")
k2 = b.kopieer_een(docs / "map", doel, verplaats=False)
klopt(k2 == doel / "map (2)", "kopiëren: tweede keer wordt 'map (2)'")
v = b.kopieer_een(docs / "kopie.txt", doel, verplaats=True)
klopt(v == doel / "kopie.txt" and not (docs / "kopie.txt").exists(), "verplaatsen: bestand verplaatst")
zelfde = b.kopieer_een(doel / "kopie.txt", doel, verplaats=True)
klopt(zelfde == doel / "kopie.txt" and zelfde.exists(), "verplaatsen naar dezelfde map: er gebeurt niets")
try:
    b.kopieer_een(docs / "map", docs / "map", verplaats=False)
    klopt(False, "map in zichzelf kopiëren wordt geweigerd")
except ValueError:
    klopt(True, "map in zichzelf kopiëren wordt geweigerd")

# 7. prullenbak legen
b.prullenbak_legen()
klopt(b.prullenbak_inhoud() == [], "prullenbak legen: leeg")
klopt((docs / "kopie.txt").exists() is False and (doel / "kopie.txt").exists(), "prullenbak legen: rest blijft heel")

# 8. namen tonen
klopt(b.toon_naam("Recept.odt", False) == "Recept", "naam: bekende extensie verborgen")
klopt(b.toon_naam("SpotifySetup.exe", False) == "SpotifySetup.exe", "naam: programma houdt zijn extensie")
klopt(b.toon_naam("foto.jpg", True) == "foto.jpg", "naam: map houdt zijn naam")

# 9. het venster start en toont de mappen (zonder scherm)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or b.maak_app("bugos-bestanden", "bugos-bestanden", ["test"])
venster = b.Bestanden(docs)
for _ in range(50):
    app.processEvents()
klopt(venster.huidig == docs, "venster: opent in Documenten")
klopt(venster.grote_titel.text() in ("Documenten", "Documents", "Documenten".lower()) or venster.grote_titel.text() != "",
      "venster: toont een titel")
venster.open_prullenbak()
klopt(venster.in_prullenbak and venster.lijst.model() is venster.bak_model, "venster: prullenbak opent")
venster.terug()
klopt(not venster.in_prullenbak and venster.huidig == docs, "venster: terug uit de prullenbak")

venster.close()
import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
