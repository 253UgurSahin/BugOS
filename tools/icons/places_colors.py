"""Kleuren van de zachte BugOS-map: de lagen die meekleuren met licht en donker (voor places.py).

pas_aan() rekent de dekkingen uit (LAGEN), zodat een map in licht en donker zo dicht
mogelijk uitkomt bij map_voor, map_achter en map_teken uit bugos_ui.py.
"""

from __future__ import annotations

import configparser
import itertools
import math

from tokens import KLEUREN, ROOD, SYSTEM


# ------------------------------------------------------------------------- kleuren ---

def _rgb(tekst: str) -> tuple[float, float, float]:
    tekst = tekst.strip()
    if tekst.startswith("#"):
        h = tekst[1:]
        return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return tuple(float(x) for x in tekst.split(",")[:3])


def _hex(kleur) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in kleur)


def _schema(naam: str, reserve: dict[str, str]) -> dict[str, tuple]:
    """De kleuren die KDE in het stijlblad zet: B (venster) en T (tekst)."""
    pad = SYSTEM / "usr" / "share" / "color-schemes" / f"{naam}.colors"
    c = configparser.RawConfigParser(strict=False, interpolation=None)
    try:
        c.read_string(pad.read_text(encoding="utf-8"))
        return {"B": _rgb(c.get("Colors:Window", "BackgroundNormal")),
                "T": _rgb(c.get("Colors:Window", "ForegroundNormal"))}
    except (OSError, configparser.Error):
        return {"B": _rgb(reserve["achter"]), "T": _rgb(reserve["tekst"])}


THEMAS = {"licht": _schema("BugOSLight", KLEUREN["licht"]), "donker": _schema("BugOSDark", KLEUREN["donker"])}
WIT = (255.0, 255.0, 255.0)
ROOD_RGB = _rgb(ROOD)


def _over(boven, dekking: float, onder):
    return tuple(dekking * b + (1 - dekking) * o for b, o in zip(boven, onder))


def _zoek(fout, bereiken: list[tuple[float, float]], rondes: int = 4, n: int = 12) -> tuple:
    """Grof naar fijn zoeken naar de waarden met de kleinste fout (zonder numpy)."""
    midden = [(lo + hi) / 2 for lo, hi in bereiken]
    breedte = [hi - lo for lo, hi in bereiken]
    beste = None
    for _ in range(rondes):
        roosters = []
        for (lo, hi), m, w in zip(bereiken, midden, breedte):
            a, b = max(lo, m - w / 2), min(hi, m + w / 2)
            roosters.append([a + (b - a) * i / n for i in range(n + 1)])
        for waarden in itertools.product(*roosters):
            e = fout(*waarden)
            if beste is None or e < beste[0]:
                beste = (e, waarden)
        midden = list(beste[1])
        breedte = [w / 3 for w in breedte]
    return beste[1]


def _vlak(th: dict, laag: tuple, tint=ROOD_RGB):
    grijs, og, oh = laag
    return _over(tint, oh, _over((grijs,) * 3, og, th["B"]))


def _teken(th: dict, ondergrond, laag: tuple, tint=ROOD_RGB):
    ow, oh, ot = laag
    return _over(th["T"], ot, _over(tint, oh, _over(WIT, ow, ondergrond)))


def pas_aan() -> dict[str, tuple]:
    """Dekkingen voor de lagen van de map, passend bij map_voor/map_achter/map_teken."""
    L, D = THEMAS["licht"], THEMAS["donker"]
    uit = {}
    for deel, sleutel in (("voor", "map_voor"), ("achter", "map_achter")):
        doel_l, doel_d = _rgb(KLEUREN["licht"][sleutel]), _rgb(KLEUREN["donker"][sleutel])
        uit[deel] = _zoek(lambda g, og, oh: math.dist(_vlak(L, (g, og, oh)), doel_l)
                          + math.dist(_vlak(D, (g, og, oh)), doel_d),
                          [(0, 255), (0, 0.8), (0, 0.8)])
    voor_l, voor_d = _vlak(L, uit["voor"]), _vlak(D, uit["voor"])
    doel_l, doel_d = _rgb(KLEUREN["licht"]["map_teken"]), _rgb(KLEUREN["donker"]["map_teken"])

    # Het tekentje: licht donkerrood, donker bijna wit. Met dezelfde lagen kan dat niet
    # allebei precies; licht krijgt voorrang (moet dicht bij Bestanden), donker mag iets
    # roziger uitvallen.
    def fout_teken(ow, oh, ot):
        el = math.dist(_teken(L, voor_l, (ow, oh, ot)), doel_l)
        ed = math.dist(_teken(D, voor_d, (ow, oh, ot)), doel_d)
        return ed + 6 * max(0.0, el - 18)

    uit["teken"] = _zoek(fout_teken, [(0, 1), (0, 1), (0, 1)])
    return uit


LAGEN = pas_aan()


def _afgerond(laag: tuple) -> tuple:
    return tuple(round(x, 3) for x in laag)


def kleurverslag() -> str:
    """Wat de lagen in licht en donker opleveren (voor in de uitvoer van make.py)."""
    regels = []
    for thema, th in THEMAS.items():
        voor = _vlak(th, LAGEN["voor"])
        achter = _vlak(th, LAGEN["achter"])
        teken = _teken(th, voor, LAGEN["teken"])
        k = KLEUREN[thema]
        regels.append(f"  map {thema}: voor {_hex(voor)} (Bestanden {k['map_voor']}), achter {_hex(achter)} "
                      f"({k['map_achter']}), tekentje {_hex(teken)} ({k['map_teken']})")
    return "\n".join(regels)
