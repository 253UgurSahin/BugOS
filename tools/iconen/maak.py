#!/usr/bin/env python3
"""Maak het BugOS-pictogramthema opnieuw: system_files/usr/share/icons/BugOS.

    python3 tools/iconen/maak.py                 alles opnieuw (zo hoort het in de repo)
    python3 tools/iconen/maak.py --alleen status alleen dat onderdeel (de rest blijft staan)

Elk onderdeel staat in een eigen bestand met een functie maak(b):
  apps.py         app-pictogrammen: een lijnicoon op een rustig grijs tegeltje
  status.py       systeemvak, meldingen, knoppen (eenkleurig, kleurt mee)
  plaatsen.py     mappen, apparaten en bestandssoorten (in de zachte BugOS-maptint)
  instellingen.py de pictogrammen in KDE Instellingen (eenkleurig, zoals in BugOS Instellingen)
Een onderdeel dat er (nog) niet is, wordt overgeslagen.

Per onderdeel staat in tools/iconen/lijsten/<onderdeel>.txt welke bestanden het maakte.
Zo ruimt --alleen alleen zijn eigen oude bestanden op, en kan proef_iconen.py een
contactvel per onderdeel maken.
"""

from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))

import basis  # noqa: E402

ONDERDELEN = ["apps", "status", "plaatsen", "instellingen"]
LIJSTEN = HIER / "lijsten"


def _lijst(naam: str) -> Path:
    return LIJSTEN / f"{naam}.txt"


def _bewaar_lijst(naam: str, b: basis.Bouwer) -> None:
    LIJSTEN.mkdir(exist_ok=True)
    regels = sorted(f"{m}/{n}.svg" for (m, n), wie in b.namen.items() if wie == naam)
    _lijst(naam).write_text("\n".join(regels) + "\n", encoding="utf-8", newline="\n")


def _draai(naam: str, b: basis.Bouwer) -> int:
    mod = importlib.import_module(naam)
    voor = len(b.namen)
    b.huidig = naam
    mod.maak(b)
    # Wie niets meegaf als 'door', telt voor dit onderdeel.
    for sleutel, wie in list(b.namen.items()):
        if wie == "":
            b.namen[sleutel] = naam
    _bewaar_lijst(naam, b)
    return len(b.namen) - voor


def _mappen_uit_lijsten() -> set[str]:
    mappen = set()
    for pad in LIJSTEN.glob("*.txt"):
        for regel in pad.read_text(encoding="utf-8").split():
            mappen.add(regel.rsplit("/", 1)[0])
    return mappen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alleen", choices=ONDERDELEN, help="alleen dit onderdeel opnieuw maken")
    args = ap.parse_args()

    b = basis.Bouwer()
    if args.alleen:
        oud = _lijst(args.alleen)
        if oud.exists():
            for regel in oud.read_text(encoding="utf-8").split():
                (basis.UIT / regel).unlink(missing_ok=True)
        print(f"{args.alleen}: {_draai(args.alleen, b)} pictogrammen")
        b.gebruikte_mappen |= {m for m in _mappen_uit_lijsten() if m in basis.MAPPEN}
    else:
        if basis.UIT.exists():
            shutil.rmtree(basis.UIT)
        for naam in ONDERDELEN:
            if not (HIER / f"{naam}.py").exists():
                print(f"(overgeslagen: {naam}.py bestaat nog niet)")
                _lijst(naam).unlink(missing_ok=True)
                continue
            print(f"{naam}: {_draai(naam, b)} pictogrammen")

    pad = b.schrijf_index()
    fouten = basis.controleer(volledig=not args.alleen)
    for f in fouten:
        print("FOUT", f)
    print(f"klaar: {len(b.namen)} pictogrammen geschreven -> {pad.parent}")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
