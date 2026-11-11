"""BugOS: laat zien hoe ver het kopiëren van BugOS is, tijdens het installeren.

Draait IN het installatieprogramma (Anaconda, als root), vanuit DeployOSTreeTask.run: build.sh zet dit bestand naast
pyanaconda/modules/payloads/payload/rpm_ostree/installation.py en zet de aanroep erin (patch_installatie hieronder).

Waarom: `ostree container image deploy` zegt zelf niets als er geen terminal is (20 tot 40 minuten lang alleen
"Deployment starting: /var/lib/bugos-stick/bugos"). Wel komt er voor elke ingelezen laag een verwijzing bij in
<physroot>/ostree/repo/refs/heads/ostree/container/blob/ (naam: sha256_3A_<hex>), en de OCI-map op de stick zegt hoe
groot elke laag is. Samen: echte voortgang, zonder iets aan het kopiëren zelf te veranderen. Leest alleen; schrijft
en start niets. Gaat er iets mis, dan zie je alleen de minuten; het installeren zelf merkt er nooit iets van.

Ook als los programma (build.sh):  python3 bugos_voortgang.py patch <pad naar installation.py>
Python 3.12+; alleen de standaardbibliotheek.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager

BLOB_MAP = os.path.join("ostree", "repo", "refs", "heads", "ostree", "container", "blob")


def lagen(oci_map: str) -> dict[str, int]:
    """{hex: grootte in bytes} van alle lagen in de OCI-map. OSError/ValueError/KeyError als het geen OCI-map is.
    Dezelfde laag twee keer in het manifest telt één keer (ostree leest hem ook één keer in)."""
    if not os.path.isdir(oci_map) and ":" in oci_map:   # 'map:tag' (oci-transport met een naam)
        oci_map = oci_map.rsplit(":", 1)[0]
    with open(os.path.join(oci_map, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    alg, hexd = index["manifests"][0]["digest"].split(":", 1)
    with open(os.path.join(oci_map, "blobs", alg, hexd), encoding="utf-8") as f:
        manifest = json.load(f)
    uit = {}
    for laag in manifest["layers"]:
        uit[laag["digest"].split(":", 1)[1]] = int(laag["size"])
    if not uit:
        raise ValueError("geen lagen")
    return uit


def binnen(physroot: str) -> set[str]:
    """De lagen (hex) die al zijn ingelezen; een lege verzameling zolang de map er nog niet is."""
    try:
        namen = os.listdir(os.path.join(physroot, BLOB_MAP))
    except OSError:
        return set()
    return {n.split("_3A_", 1)[1] for n in namen if n.startswith("sha256_3A_")}


def procent(alle: dict[str, int], klaar: set[str]) -> int:
    """0..100, naar beneden afgerond (100 pas als alles binnen is)."""
    totaal = sum(alle.values())
    gedaan = sum(g for h, g in alle.items() if h in klaar)
    return min(100, gedaan * 100 // totaal) if totaal else 0


def bericht(pct: int | None, minuten: int, nl: bool) -> str:
    """De regel onder 'BugOS kopiëren' in het installatieprogramma. pct None: we weten het percentage niet."""
    if minuten == 1:
        tijd = " (1 minuut bezig)" if nl else " (1 minute so far)"
    elif minuten > 1:
        tijd = f" ({minuten} minuten bezig)" if nl else f" ({minuten} minutes so far)"
    else:
        tijd = ""
    if pct is None:
        return ("BugOS wordt gekopieerd" if nl else "Copying BugOS") + tijd
    if pct >= 100:
        # Alles is binnen; ostree zet de bestanden nog op hun plek. Geen belofte hoe lang dat duurt.
        return ("Bijna klaar: BugOS wordt op zijn plek gezet" if nl else "Almost done: putting BugOS in place") + tijd
    return (f"BugOS wordt gekopieerd: {pct}% klaar" if nl else f"Copying BugOS: {pct}% done") + tijd


@contextmanager
def met_voortgang(meld, physroot: str, oci_map: str, interval: float = 5.0, klok=time.monotonic, taal: str | None = None):
    """Meldt elke `interval` seconden hoe ver het is, zolang het with-blok loopt. Gaat zelf nooit mis.
    taal None: de taal van het installatieprogramma (LANG van de module; Nederlands als die met 'nl' begint)."""
    try:
        alle = lagen(oci_map)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        alle = None
    nl = (taal if taal is not None else os.environ.get("LANG", "")).startswith("nl")
    begin = klok()
    stop = threading.Event()

    def lus() -> None:
        while not stop.wait(interval):
            try:
                pct = procent(alle, binnen(physroot)) if alle else None
                meld(bericht(pct, int((klok() - begin) // 60), nl))
            except Exception:  # noqa: BLE001 - voortgang mag het installeren nooit laten mislukken
                pass

    draad = threading.Thread(target=lus, name="bugos-voortgang", daemon=True)
    draad.start()
    try:
        yield
    finally:
        stop.set()
        draad.join(timeout=interval + 1)


# ====================================================================== de aanroep in Anaconda zetten (build.sh) ===
# In DeployOSTreeTask.run (anaconda 44.30): 12 spaties voor safe_exec_program(, 16 voor de argumenten.
OUD = '''            safe_exec_program(
                "ostree",
                args,
                env_add={"LC_ALL": "C.UTF-8"},
            )
'''
NIEUW = '''            # BugOS: ostree zegt niets tijdens het kopiëren; laat zien hoe ver het is (iso_live/src/bugos_voortgang.py).
            from pyanaconda.modules.payloads.payload.rpm_ostree.bugos_voortgang import met_voortgang
            with met_voortgang(self.report_progress, self._physroot, ref):
                safe_exec_program(
                    "ostree",
                    args,
                    env_add={"LC_ALL": "C.UTF-8"},
                )
'''


def patch_installatie(tekst: str) -> str:
    """Zet met_voortgang om het kopiëren. Een andere vorm (Anaconda bijgewerkt) stopt het bouwen (AssertionError)."""
    assert "bugos_voortgang" not in tekst, "installation.py is al aangepast"
    assert tekst.count(OUD) == 1, f"installation.py heeft een onbekende vorm ({tekst.count(OUD)} keer; anaconda bijgewerkt?)"
    return tekst.replace(OUD, NIEUW)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "patch":
        print("gebruik: bugos_voortgang.py patch <installation.py>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        tekst = f.read()
    nieuw = patch_installatie(tekst)
    compile(nieuw, argv[1], "exec")
    with open(argv[1], "w", encoding="utf-8") as f:
        f.write(nieuw)
    print(f"bugos_voortgang: voortgang tijdens het kopiëren staat in {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
