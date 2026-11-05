"""Mappen, plekken, apparaten en bestandssoorten voor het BugOS-pictogramthema.

Doel: Dolphin, de bestandskiezer, het bureaublad en de pop-up "Schijven en apparaten"
laten dezelfde mappen en bestanden zien als BugOS Bestanden (usr/bin/bugos-files):

  - mappen vanaf 32 px: de zachte BugOS-map uit teken_map(), met het tekentje erop;
  - mappen en plekken op 16 en 22 px (en elke naam-symbolic): BugOS-lijniconen, net als in
    de zijbalk van Bestanden (huis, scherm, document, ...); een bijzondere map is klein
    alleen zijn tekentje (een tekentje ín een mapomtrek is op 16 px een vlekje);
  - apparaten: lijniconen in de tekstkleur (schijf, USB-stick, telefoon, ...), met de namen
    die Solid en het systeemvak vragen (ook multimedia-player voor een Android-telefoon);
  - bestandssoorten: het papiertje met het gekleurde labeltje uit teken_papier(), met
    dezelfde kleuren en tekentjes (SOORTEN uit bugos-files). Op 16 en 22 px een
    lijnpapiertje met de kleur van het labeltje erin;
  - de actie "Nieuwe map" (folder-new): de map met plusje, zoals de knop in Bestanden.

16 en 22 px staan ook in <map>@2x en @3x: anders kiest KDE op een HiDPI-scherm (125 % en
meer) de grote versie, ook in de zijbalk en de lijstweergave.

Meekleuren met licht en donker: KDE vervangt de klassen ColorScheme-Background en -Text
door de venster- en tekstkleur van het kleurenschema (gemeten in de testbank). Highlight
gebruiken we niet: in de BugOS-schema's is dat het zachte rood van een gekozen regel, niet
het rood zelf, en dat kan nog veranderen. Een map is daarom een stapel lagen: de
vensterkleur, daarover een vast grijs en daarover het BugOS-rood (ROOD uit bugos_ui.py),
elk met een eigen dekking. pas_aan() rekent die dekkingen uit, zodat licht en donker zo
dicht mogelijk uitkomen bij map_voor, map_achter en map_teken uit bugos_ui.py. Verandert
daar een kleur (of in de kleurenschema's), dan volgen de pictogrammen vanzelf bij de
volgende keer maken. Gekozen (Dolphin, lijstweergave): KDE maakt de tekstkleur dan rood,
dus lijniconen en het tekentje op de map worden rood, net als in de zijbalk van Bestanden.

Labeltjes: tekst in een pictogram mag geen lettertype gebruiken, dus de letters (PDF, ZIP,
MP3, ...) zijn kleine lijntekeningen (LETTERS hieronder), even dik en ruim als Inter Bold in
Bestanden. Net als in Bestanden staat de extensie op elk papiertje waarvan we die kennen (LABELS,
anders EXTENSIES uit shared-mime-info); zonder extensie komt er geen labeltje.
"""

from __future__ import annotations

import ast
import configparser
import itertools
import math
import re
from xml.etree import ElementTree as ET

import basis
from basis import STIJLBLAD, klein, symbolisch
from tokens import KLEUREN, LIJN, ROOD, SYSTEM, TINTEN

# ------------------------------------------------------------------ mappen in index.theme ---
# Klein (16 en 22) zijn het lijniconen, zoals Breeze ook doet; vanaf 32 px de zachte map.
basis.map_erbij("places/22", Size=22, Context="Places", Type="Fixed")
basis.map_erbij("mimetypes/16", Size=16, Context="MimeTypes", Type="Fixed")
basis.map_erbij("mimetypes/22", Size=22, Context="MimeTypes", Type="Fixed")

# HiDPI: bij een schaal van 125 tot 200 % zoekt KDE eerst in <maat>@2x, vanaf 225 % in @3x
# (gemeten met KIconLoader 6.31 in de testbank). Zonder die mappen kiest KDE op zo'n scherm de
# grote versie (de zachte map, het papiertje met label) waar de lijnversie hoort. Breeze heeft
# ze ook. Inhoud: een kopie van 16 en 22 (git en OSTree bewaren gelijke bestanden maar één keer).
SCHALEN = (2, 3)
GESCHAALD = ("places/16", "places/22", "mimetypes/16", "mimetypes/22")
for _map in GESCHAALD:
    _soort, _maat = _map.split("/")
    for _s in SCHALEN:
        basis.map_erbij(f"{_map}@{_s}x", Size=int(_maat), Scale=_s,
                        Context="Places" if _soort == "places" else "MimeTypes", Type="Fixed")


def _mappen_instellen() -> None:
    basis.MAPPEN["places/scalable"]["MinSize"] = 32
    basis.MAPPEN["mimetypes/scalable"]["MinSize"] = 32


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


# --------------------------------------------------------------------- SVG-hulpjes ---

def _g(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    return (f"M{_g(x + r)} {_g(y)}H{_g(x + w - r)}A{_g(r)} {_g(r)} 0 0 1 {_g(x + w)} {_g(y + r)}"
            f"V{_g(y + h - r)}A{_g(r)} {_g(r)} 0 0 1 {_g(x + w - r)} {_g(y + h)}"
            f"H{_g(x + r)}A{_g(r)} {_g(r)} 0 0 1 {_g(x)} {_g(y + h - r)}"
            f"V{_g(y + r)}A{_g(r)} {_g(r)} 0 0 1 {_g(x + r)} {_g(y)}Z")


def _veelhoek(punten: list[tuple[float, float]], r: float) -> str:
    """Gesloten veelhoek met afgeronde hoeken (kwadratische bochtjes)."""
    d = []
    n = len(punten)
    for i, (px, py) in enumerate(punten):
        ax, ay = punten[i - 1]
        bx, by = punten[(i + 1) % n]
        la, lb = math.hypot(ax - px, ay - py), math.hypot(bx - px, by - py)
        ra, rb = min(r, la / 2), min(r, lb / 2)
        p1 = (px + (ax - px) * ra / la, py + (ay - py) * ra / la)
        p2 = (px + (bx - px) * rb / lb, py + (by - py) * rb / lb)
        d.append(("M" if i == 0 else "L") + f"{_g(p1[0])} {_g(p1[1])}Q{_g(px)} {_g(py)} {_g(p2[0])} {_g(p2[1])}")
    return "".join(d) + "Z"


_GETAL = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _pad_van(el: ET.Element) -> str:
    """Eén SVG-element (path, rect, circle) als paddata."""
    tag = el.tag.split("}")[-1]
    a = el.attrib
    if tag == "path":
        d = a["d"].strip()
        if d[:1] == "m":
            # Een los pad dat met een kleine m begint: het eerste punt is absoluut, de punten
            # erna zijn relatieve lijnen. Zo blijft dat zo als we paden aan elkaar plakken.
            getallen = list(_GETAL.finditer(d))
            x, y = getallen[0].group(), getallen[1].group()
            rest = d[getallen[1].end():].lstrip(" ,")
            d = f"M{x} {y}" + ("l" + rest if rest[:1] and (rest[0].isdigit() or rest[0] in "-+.") else rest)
        return d
    if tag == "rect":
        x, y = float(a.get("x", 0)), float(a.get("y", 0))
        w, h = float(a["width"]), float(a["height"])
        r = float(a.get("rx", a.get("ry", 0)))
        return _rrect(x, y, w, h, r) if r else f"M{_g(x)} {_g(y)}h{_g(w)}v{_g(h)}h{_g(-w)}Z"
    if tag == "circle":
        cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
        return (f"M{_g(cx - r)} {_g(cy)}A{_g(r)} {_g(r)} 0 1 0 {_g(cx + r)} {_g(cy)}"
                f"A{_g(r)} {_g(r)} 0 1 0 {_g(cx - r)} {_g(cy)}Z")
    raise ValueError(f"onbekend element in lijnicoon: {tag}")


def pad(glyph: str) -> str:
    """Een lijnicoon (naam uit LIJN/EIGEN of SVG-elementen) als één pad.

    Eén pad, zodat een halfdoorzichtige lijn op kruisingen niet dubbel donker wordt."""
    binnen = EIGEN.get(glyph) or LIJN.get(glyph) or glyph
    boom = ET.fromstring(f'<g xmlns="http://www.w3.org/2000/svg">{binnen}</g>')
    return "".join(_pad_van(el) for el in boom)


def _svg(binnen: str, maat: int = 48) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{maat}" height="{maat}" viewBox="0 0 {maat} {maat}">'
            f"{STIJLBLAD}{binnen}</svg>")


# ------------------------------------------------ eigen lijntekeningen (24-raster) ---
# In dezelfde taal als LIJN in bugos_ui.py: lijn 2, ronde uiteinden, eenvoudige vormen.
EIGEN = {
    "telefoon": '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
    "tekentablet": '<rect x="2.5" y="5.5" width="13" height="14" rx="2"/><path d="M6 10h6M6 13.5h4"/>'
                   '<path d="M18.5 6.5 20 3l1.5 3.5v10l-1.5 3-1.5-3z"/>',
    "touchpad": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M3 14.5h18M12 14.5v5"/>',
    "koptelefoon": '<path d="M4 16v-3.5a8 8 0 0 1 16 0V16"/><path d="M4 14.5h2a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 '
                   '1.5H5.5A1.5 1.5 0 0 1 4 19z"/><path d="M20 14.5h-2a1.5 1.5 0 0 0-1.5 1.5v3a1.5 1.5 0 0 0 1.5 '
                   '1.5h.5A1.5 1.5 0 0 0 20 19z"/>',
    "headset": '<path d="M4 15v-2.5a8 8 0 0 1 16 0V15"/><path d="M4 13h2a1.5 1.5 0 0 1 1.5 1.5v2.5A1.5 1.5 0 0 1 6 '
               '18.5h-.5A1.5 1.5 0 0 1 4 17z"/><path d="M20 13h-2a1.5 1.5 0 0 0-1.5 1.5v2.5a1.5 1.5 0 0 0 1.5 '
               '1.5h.5A1.5 1.5 0 0 0 20 17z"/><path d="M19.5 18.5v.5a2.5 2.5 0 0 1-2.5 2.5h-3"/>',
    "luidspreker": '<rect x="5.5" y="2.5" width="13" height="19" rx="2.5"/><circle cx="12" cy="14.5" r="3.5"/>'
                   '<path d="M12 7h.01"/>',
    "geluidskaart": '<rect x="2.5" y="5" width="19" height="11" rx="2"/><path d="M6 16v3M9.5 16v3M14.5 16v3M18 16v3"/>'
                    '<path d="M6 10.5h1.5l1.5-2.5 2 5 1.5-2.5H14"/><path d="M17.5 10.5h.01"/>',
    "netwerkkaart": '<rect x="2.5" y="5" width="19" height="11" rx="2"/><path d="M6 16v3M9.5 16v3M14.5 16v3M18 16v3"/>'
                    '<path d="M12.5 8h5v5h-5z"/><path d="M6.5 10.5h.01M9 10.5h.01"/>',
    "chip": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M10 10h4v4h-4z"/>'
            '<path d="M9.5 2.5V6M14.5 2.5V6M9.5 18v3.5M14.5 18v3.5M2.5 9.5H6M2.5 14.5H6M18 9.5h3.5M18 14.5h3.5"/>',
    "geheugen": '<rect x="2.5" y="6" width="19" height="10" rx="1.5"/><path d="M6 9h3v4H6zM10.5 9h3v4h-3zM15 9h3v4h-3z"/>'
                '<path d="M5.5 16v2.5M8.5 16v2.5M11 16v2.5M15.5 16v2.5M18.5 16v2.5"/>',
    "camera": '<path d="M3 9a2 2 0 0 1 2-2h2.5l1.5-2.5h6L16.5 7H19a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
              '<circle cx="12" cy="13" r="3.5"/>',
    "webcam": '<circle cx="12" cy="10" r="7"/><circle cx="12" cy="10" r="2.5"/><path d="M8 21h8M12 17v4"/>',
    "schijven": '<rect x="3.5" y="3.5" width="17" height="7.5" rx="2"/><rect x="3.5" y="13" width="17" height="7.5" rx="2"/>'
                '<path d="M7.5 7.25h.01M10.5 7.25h.01M7.5 16.75h.01M10.5 16.75h.01"/>',
    "server": '<rect x="3.5" y="3.5" width="17" height="7.5" rx="2"/><rect x="3.5" y="13" width="17" height="7.5" rx="2"/>'
              '<path d="M7.5 7.25h.01M7.5 16.75h.01M12.5 7.25h4M12.5 16.75h4"/>',
    "uitwerpschijf": '<path d="M12 3.5 16.5 8.5h-9z"/><rect x="3.5" y="12" width="17" height="8.5" rx="2.5"/>'
                     '<path d="M7.5 16.25h.01M10.5 16.25h.01"/>',
    "wolk": '<path d="M17.5 19H8.5a5.5 5.5 0 1 1 5.3-7h1.2l1.3-.5a4 4 0 0 1 1.2 7.5z"/>',
    "slot-open": '<rect x="5.5" y="10.5" width="13" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 6.9-.8"/>',
    "envelop": '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "kalender": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "belangrijk": '<path d="M12 5v9M12 18.5h.01"/>',
    "zandloper": '<path d="M7 3.5h10M7 20.5h10M8 3.5c0 4.5 8 4 8 8.5s-8 4-8 8.5M16 3.5c0 4.5-8 4-8 8.5s8 4 8 8.5"/>',
    "prullenbak-vol": '<path d="M4 7h16M6.5 7l1 12a1.5 1.5 0 0 0 1.5 1.5h6a1.5 1.5 0 0 0 1.5-1.5l1-12M10 11v6M14 11v6"/>'
                      '<path d="M8.5 7 9.3 3.5l4 .9-.6 2.6M15 7l1.3-3 2.4 1.1L17.8 7"/>',
    "map-open": '<path d="M3.5 17V7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1.5"/>'
                '<path d="M3.5 17.5 6 11.8a2 2 0 0 1 1.8-1.3h12.6a1 1 0 0 1 .9 1.4l-2.6 6.3a2 2 0 0 1-1.8 1.3H5.5'
                'a2 2 0 0 1-2-2z"/>',
    "tablet": '<rect x="4.5" y="3" width="15" height="18" rx="2.5"/><path d="M10.5 17.5h3"/>',
    "diskette": '<path d="M3.5 5.5a2 2 0 0 1 2-2h10.5l4.5 4.5v10.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'
                '<path d="M7.5 3.5V8h7V3.5M7.5 20.5v-6h9v6"/>',
    "videocamera": '<rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/>',
    "boek": '<path d="M12 6.5C10.2 5.2 7.7 4.5 4.5 4.5v13c3.2 0 5.7.7 7.5 2 1.8-1.3 4.3-2 7.5-2v-13'
            'c-3.2 0-5.7.7-7.5 2zM12 6.5v13"/>',
}

MAP_LIJN = LIJN["map"]


# --------------------------------------------------------------------- de zachte map ---
# Verhoudingen uit teken_map() in bugos-files (daar 84 x 66 beeldpunten).
ML, MT, MW, MH = 3.0, 8.0, 42.0, 33.0     # links, boven, breedte, hoogte op het 48-raster
MR = MW * 0.085                           # hoekstraal
VOOR_Y = MT + MH * 0.24                   # bovenkant van de voorkant


def _stapel(d: str, laag: tuple, tint: str | None = None) -> str:
    """Een vlak dat meekleurt: vensterkleur, dan vast grijs, dan het BugOS-rood (of een andere tint)."""
    g, og, oh = _afgerond(laag)
    grijs = _hex((g, g, g))
    return (f'<path class="ColorScheme-Background" fill="currentColor" d="{d}"/>'
            f'<path fill="{grijs}" fill-opacity="{_g(og)}" d="{d}"/>'
            f'<path fill="{tint or ROOD}" fill-opacity="{_g(oh)}" d="{d}"/>')


def _streep(d: str, laag: tuple, tint: str | None, breedte: float, transform: str = "") -> str:
    """Een lijntekening in de kleur van het tekentje (wit, dan rood, dan tekstkleur)."""
    ow, oh, ot = _afgerond(laag)
    t = f' transform="{transform}"' if transform else ""
    gemeen = f'fill="none" stroke-width="{_g(breedte)}" stroke-linecap="round" stroke-linejoin="round" d="{d}"'
    return (f"<g{t}>"
            f'<path stroke="#FFFFFF" stroke-opacity="{_g(ow)}" {gemeen}/>'
            f'<path stroke="{tint or ROOD}" stroke-opacity="{_g(oh)}" {gemeen}/>'
            f'<path class="ColorScheme-Text" stroke="currentColor" stroke-opacity="{_g(ot)}" {gemeen}/>'
            "</g>")


def _papier_vlak(d: str, rand: float = 0.16, licht: float = 0.05) -> str:
    """Papier in de kleur van een kaart: vensterkleur, iets opgelicht, met een haarlijn.

    licht: hoeveel wit erover. 0.05 geeft in donker de kaartkleur van Bestanden; in een open map
    is meer nodig, anders leest het velletje in donker als een zwarte gleuf."""
    return (f'<path class="ColorScheme-Background" fill="currentColor" d="{d}"/>'
            f'<path fill="#FFFFFF" fill-opacity="{_g(licht)}" d="{d}"/>'
            f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="{_g(rand)}" '
            f'stroke-width="0.75" stroke-linejoin="round" d="{d}"/>')


def _glyph_op_map(teken: str, tint: str | None, cy: float | None = None) -> str:
    m = MH * 0.38
    cx = ML + MW / 2
    if cy is None:
        cy = (VOOR_Y + MT + MH) / 2 + MH * 0.02
    s = m / 24
    return _streep(pad(teken), LAGEN["teken"], tint, 2.2,
                   f"translate({_g(cx - m / 2)} {_g(cy - m / 2)}) scale({_g(s)})")


def map_svg(teken: str | None = None, tint: str | None = None, open_: bool = False) -> str:
    """De zachte BugOS-map op het 48-raster (zie teken_map in bugos-files)."""
    tab = _rrect(ML, MT, MW * 0.44, MH * 0.32, MR)
    achter = _rrect(ML, MT + MH * 0.1, MW, MH * 0.9, MR)
    delen = [_stapel(tab, LAGEN["achter"], tint), _stapel(achter, LAGEN["achter"], tint)]
    onder = MT + MH
    if open_:
        delen.append(_papier_vlak(_rrect(ML + 4, MT + MH * 0.2, MW - 8, MH * 0.6, 1.5), 0.2, licht=0.3))
        boven = MT + MH * 0.36
        voor = _veelhoek([(ML + 4.5, boven), (ML + MW + 1.5, boven), (ML + MW, onder), (ML, onder)], MR)
        delen.append(_stapel(voor, LAGEN["voor"], tint))
        lijn_y = boven + 0.5
        delen.append(f'<path d="M{_g(ML + 4.5 + MR)} {_g(lijn_y)}H{_g(ML + MW + 1.5 - MR)}" stroke="#FFFFFF" '
                     f'stroke-opacity="0.35" stroke-width="0.75" stroke-linecap="round"/>')
        if teken:
            delen.append(_glyph_op_map(teken, tint, (boven + onder) / 2 + MH * 0.02))
    else:
        voor = _rrect(ML, VOOR_Y, MW, onder - VOOR_Y, MR)
        delen.append(_stapel(voor, LAGEN["voor"], tint))
        delen.append(f'<path d="M{_g(ML + MR)} {_g(VOOR_Y + 0.5)}H{_g(ML + MW - MR)}" stroke="#FFFFFF" '
                     f'stroke-opacity="0.35" stroke-width="0.75" stroke-linecap="round"/>')
        if teken:
            delen.append(_glyph_op_map(teken, tint))
    return _svg("".join(delen))


def prullenbak_svg(vol: bool = False) -> str:
    """De prullenbak in dezelfde zachte tint als de mappen."""
    delen = []
    if vol:
        for x, y, hoek in ((13.5, 3.5, -8), (23, 2.5, 10)):
            vel = _rrect(x, y, 11, 13, 1.5)
            regels = f"M{_g(x + 2.5)} {_g(y + 4)}h6M{_g(x + 2.5)} {_g(y + 7)}h4.5"
            delen.append(f'<g transform="rotate({hoek} {_g(x + 5.5)} {_g(y + 6.5)})">{_papier_vlak(vel, 0.3)}'
                         f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="0.3" '
                         f'stroke-width="1" stroke-linecap="round" d="{regels}"/></g>')
    lid = _stapel(_rrect(19, 6.5, 10, 6, 2), LAGEN["achter"]) + _stapel(_rrect(9, 10, 30, 5, 2.2), LAGEN["achter"])
    if vol:
        lid = f'<g transform="rotate(-14 38 14) translate(0 -2.5)">{lid}</g>'
    lijf = _veelhoek([(11.5, 15), (36.5, 15), (34.5, 42), (13.5, 42)], 3.2)
    delen.append(_stapel(lijf, LAGEN["voor"]))
    delen.append(f'<path d="M{_g(13.5)} {_g(15.5)}H{_g(34.5)}" stroke="#FFFFFF" stroke-opacity="0.35" '
                 f'stroke-width="0.75" stroke-linecap="round"/>')
    delen.append(lid)
    delen.append(_streep("M19 21v14M24 21v14M29 21v14", LAGEN["teken"], None, 1.6))
    return _svg("".join(delen))


def server_svg() -> str:
    """Een server (twee kastjes) in de zachte maptint."""
    delen = []
    for y in (8.5, 25.5):
        delen.append(_stapel(_rrect(7, y, 34, 14, 3.5), LAGEN["voor"]))
        delen.append(f'<path d="M{_g(10.5)} {_g(y + 0.5)}H{_g(37.5)}" stroke="#FFFFFF" stroke-opacity="0.35" '
                     f'stroke-width="0.75" stroke-linecap="round"/>')
        delen.append(_streep(f"M13 {_g(y + 7)}h.01M22 {_g(y + 7)}h13", LAGEN["teken"], None, 2.2))
    return _svg("".join(delen))


# ------------------------------------------------------------------- de lijnversies ---

def _klein_set(binnen: str) -> dict[str, str]:
    """Dezelfde lijntekening voor 16 px, 22 px en schaalbaar (24-raster)."""
    return {"16": klein(binnen), "22": symbolisch(binnen, maat=22), "scalable": symbolisch(binnen)}


BINNEN_LIJN = 1.35   # lijndikte van een klein tekentje in een map of papiertje (24-raster)


def _map_met_klein(glyph: str, schaal: float = 0.4) -> str:
    """Mapomtrek met een klein tekentje erin (zoals map-plus in LIJN)."""
    return (f"{MAP_LIJN}<g transform=\"translate(12 13.4) scale({_g(schaal)}) translate(-12 -12)\" "
            f"stroke-width=\"{_g(BINNEN_LIJN / schaal)}\"><path d=\"{pad(glyph)}\"/></g>")


def _lijnset(soort: str, glyph: str | None) -> dict[str, str]:
    """soort: 'teken' (alleen het tekentje, zoals de zijbalk van Bestanden), 'map', 'met' of 'open'."""
    if soort == "teken":
        return _klein_set(EIGEN.get(glyph) or LIJN[glyph])
    if soort == "map":
        return _klein_set(MAP_LIJN)
    if soort == "open":
        return _klein_set(EIGEN["map-open"])
    if soort == "met":
        binnen = _map_met_klein(glyph)
        return {"16": klein(binnen), "22": symbolisch(binnen, maat=22), "scalable": symbolisch(binnen)}
    raise ValueError(soort)


# --------------------------------------------------------------------- mappen-tabel ---
# (namen, tekentje op de grote map, kleine versie)
# Klein: 'teken' = alleen het lijnicoon (zoals de zijbalk van Bestanden en zoals Breeze op
# 16 en 22 px), 'met' = mapomtrek met een eenvoudig tekentje erin, 'map' = alleen de
# mapomtrek. Een klein tekentje ín een mapomtrek wordt op 16 px een vlekje; daarom krijgen
# de bijzondere mappen klein alleen hun tekentje. Alleen het uitroepteken (één streepje)
# blijft leesbaar in de map. Openbaar en Sjablonen hebben in Bestanden geen tekentje; hier
# dus ook niet.
MAPPEN = [
    (["folder", "inode-directory", "folder-red", "folder-templates", "folder-publicshare", "folder-public",
      "folder-root"], None, ("map", None)),
    (["folder-open"], None, ("open", None)),
    (["folder-documents", "folder-txt", "folder-text", "folder-log"], "document", ("teken", "document")),
    (["folder-download", "folder-downloads"], "download", ("teken", "download")),
    (["folder-pictures", "folder-images", "folder-image", "folder-picture"], "foto", ("teken", "foto")),
    (["folder-music", "folder-sound", "folder-podcast"], "muziek", ("teken", "muziek")),
    (["folder-videos", "folder-video"], "film", ("teken", "film")),
    (["folder-desktop", "user-desktop"], "computer", ("teken", "computer")),
    (["folder-home", "user-home"], "huis", ("teken", "huis")),
    (["folder-network", "network-workgroup"], "wereld", ("teken", "wereld")),
    (["folder-remote"], "wereld", ("teken", "wereld")),
    # wolkdiensten (kio-gdrive vraagt folder-gdrive in het Netwerk-overzicht van Dolphin)
    (["folder-cloud", "folder-gdrive", "folder-dropbox", "folder-onedrive", "folder-owncloud"], "wolk",
     ("teken", "wolk")),
    (["folder-recent", "folder-open-recent"], "klok", ("teken", "klok")),
    (["folder-favorites", "folder-bookmark"], "ster", ("teken", "ster")),
    (["folder-saved-search"], "zoek", ("teken", "zoek")),
    (["folder-important"], "belangrijk", ("met", "belangrijk")),
    (["folder-temp"], "zandloper", ("teken", "zandloper")),
    (["folder-development", "folder-script", "folder-build", "folder-git", "folder-java", "folder-html"],
     "code", ("teken", "code")),
    (["folder-games", "folder-godot"], "spel", ("teken", "spel")),
    (["folder-locked", "folder-encrypted"], "slot", ("teken", "slot")),
    (["folder-unlocked", "folder-decrypted"], "slot-open", ("teken", "slot-open")),
    (["folder-mail"], "envelop", ("teken", "envelop")),
    (["folder-print"], "printer", ("teken", "printer")),
    (["folder-tar", "folder-appimage", "folder-deb", "folder-rpm", "folder-snap", "folder-flatpak",
      "folder-docker"], "doos", ("teken", "doos")),
    (["folder-trash"], "prullenbak", ("teken", "prullenbak")),
    # KDE Connect vraagt folder-book (de map Boeken op de telefoon)
    (["folder-book", "folder-library"], "boek", ("teken", "boek")),
    (["folder-android"], "telefoon", ("teken", "telefoon")),
    (["folder-windows", "folder-mac"], "computer", ("teken", "computer")),
    (["folder-design", "folder-drawing", "folder-paint", "folder-blender"], "palet", ("teken", "palet")),
    (["folder-notes", "folder-sign"], "potlood", ("teken", "potlood")),
    (["folder-chart", "folder-presentation", "folder-calculate"], "grafiek", ("teken", "grafiek")),
    (["folder-table", "folder-activities", "folder-extension"], "apps", ("teken", "apps")),
    (["folder-comic"], "praten", ("teken", "praten")),
    (["folder-crash"], "uitroep", ("teken", "uitroep")),
    (["folder-database"], "opslag", ("teken", "opslag")),
    (["folder-image-people"], "persoon", ("teken", "persoon")),
    (["folder-language"], "letter", ("teken", "letter")),
]
EIGEN["doos"] = ('<rect x="3.5" y="4.5" width="17" height="4.5" rx="1.5"/>'
                 '<path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 12.5h4"/>')

# Gekleurde mappen (Dolphin: "Mappictogram wijzigen"): dezelfde map in een rustige tint.
KLEURMAPPEN = {
    "folder-blue": TINTEN["blauw"], "folder-green": TINTEN["groen"], "folder-yellow": TINTEN["geel"],
    "folder-orange": TINTEN["oranje"], "folder-brown": TINTEN["oranje"], "folder-violet": TINTEN["paars"],
    "folder-magenta": TINTEN["roze"], "folder-cyan": TINTEN["turkoois"], "folder-grey": TINTEN["grijs"],
    "folder-black": TINTEN["grijs"],
}


# ------------------------------------------------------------------ apparaten-tabel ---
# lijnicoon -> namen (devices/16 en devices/scalable, met -symbolic erbij)
APPARATEN = {
    "computer": ["computer", "video-display"],
    "laptop": ["computer-laptop"],
    "opslag": ["drive-harddisk", "drive-harddisk-solidstate", "drive-harddisk-root", "drive-harddisk-system",
               "drive-harddisk-usb", "drive-harddisk-ieee1394", "drive-harddisk-encrypted", "drive", "drive-partition",
               "drive-multipartition"],
    "schijven": ["drive-multidisk"],
    "usb": ["drive-removable-media", "drive-removable-media-usb", "drive-removable-media-usb-pendrive",
            "media-removable"],
    "cd": ["drive-optical", "media-optical", "media-optical-audio", "media-optical-cd", "media-optical-cd-audio",
           "media-optical-cd-r", "media-optical-dvd", "media-optical-dvd-video", "media-optical-blu-ray",
           "media-optical-bd", "media-optical-data", "media-optical-recordable", "media-optical-mixed-cd",
           "media-optical-video"],
    "kaart": ["media-flash", "media-flash-sd-mmc", "media-flash-memory-stick", "media-flash-smart-media"],
    "diskette": ["media-floppy"],
    # Solid en kio-mtp: een Android-telefoon heet multimedia-player, een iPhone phone-apple-iphone.
    # Het systeemvak vraagt <naam>-symbolic van het laatst aangesloten apparaat.
    "telefoon": ["phone", "smartphone", "multimedia-player", "phone-apple-iphone",
                 "multimedia-player-apple-ipod-touch"],
    "tablet": ["computer-apple-ipad"],
    "printer": ["printer", "printer-network"],
    "toetsenbord": ["input-keyboard"],
    "muis": ["input-mouse"],
    "spel": ["input-gaming", "input-gamepad"],
    "tekentablet": ["input-tablet"],
    "touchpad": ["input-touchpad"],
    "geluidskaart": ["audio-card"],
    "koptelefoon": ["audio-headphones"],
    "headset": ["audio-headset"],
    "luidspreker": ["audio-speakers"],
    "camera": ["camera-photo"],
    "videocamera": ["camera-video"],
    "webcam": ["camera-web"],
    "netwerkkaart": ["network-card"],
    "chip": ["cpu", "preferences-devices-cpu"],
    "geheugen": ["memory"],
    "uitwerpschijf": ["device-notifier"],
}


# ------------------------------------------------------------- letters voor labeltjes ---
# Op een raster van 6 hoog; (breedte, pad). Getekend met een witte lijn, ronde uiteinden.
LETTERS = {
    "A": (4.0, "M0 6 2 0l2 6M.7 4h2.6"),
    "B": (3.9, "M0 6V0h2.1a1.5 1.5 0 0 1 0 3H0h2.4a1.5 1.5 0 0 1 0 3z"),
    "C": (4.0, "M4 1.2A2.2 3 0 1 0 4 4.8"),
    "D": (3.8, "M0 0v6h1.3a2.5 3 0 0 0 0-6z"),
    "E": (3.4, "M3.4 0H0v6h3.4M0 3h2.8"),
    "F": (3.4, "M3.4 0H0v6M0 3h2.8"),
    "G": (4.2, "M4 1.2A2.2 3 0 1 0 4.2 4.7V3.4H2.6"),
    "H": (3.6, "M0 0v6M3.6 0v6M0 3h3.6"),
    "I": (0.0, "M0 0v6"),
    "J": (3.0, "M3 0v4.5a1.5 1.5 0 0 1-3 0"),
    "K": (3.6, "M0 0v6M3.6 0 0 3.8M1.3 2.9 3.6 6"),
    "L": (3.2, "M0 0v6h3.2"),
    "M": (4.6, "M0 6V0l2.3 4L4.6 0v6"),
    "N": (3.8, "M0 6V0l3.8 6V0"),
    "O": (4.2, "M2.1 0A2.1 3 0 0 0 2.1 6A2.1 3 0 0 0 2.1 0z"),
    "P": (3.6, "M0 6V0h2a1.6 1.6 0 0 1 0 3.2H0"),
    "Q": (4.2, "M2.1 0A2.1 3 0 0 0 2.1 6A2.1 3 0 0 0 2.1 0zM2.7 4.4 4.2 6.2"),
    "R": (3.6, "M0 6V0h2a1.6 1.6 0 0 1 0 3.2H0M1.9 3.2 3.6 6"),
    "S": (3.6, "M3.5 1.2C3.1.4 2.5 0 1.8 0 .8 0 .1.6.1 1.5c0 1.9 3.4 1.1 3.4 3 0 .9-.7 1.5-1.7 1.5-.8 0-1.4-.4-1.8-1.1"),
    "T": (3.8, "M0 0h3.8M1.9 0v6"),
    "U": (3.6, "M0 0v4.2a1.8 1.8 0 0 0 3.6 0V0"),
    "V": (4.0, "M0 0l2 6 2-6"),
    "W": (5.0, "M0 0l1.2 6 1.3-4.5 1.3 4.5L5 0"),
    "X": (3.8, "M0 0l3.8 6M3.8 0 0 6"),
    "Y": (4.0, "M0 0l2 3 2-3M2 3v3"),
    "Z": (3.6, "M0 0h3.6L0 6h3.6"),
    "0": (3.4, "M1.7 0A1.7 3 0 0 0 1.7 6 1.7 3 0 0 0 1.7 0z"),
    "1": (2.0, "M0 1.2 2 0v6"),
    "2": (3.4, "M.1 1.4A1.65 1.5 0 0 1 3.3 1.7C3.3 3.2 0 4.4 0 6h3.4"),
    "3": (3.4, "M.2.8A1.6 1.5 0 0 1 3.1 1.5 1.6 1.5 0 0 1 1.5 3a1.6 1.5 0 0 1 1.7 1.5A1.6 1.5 0 0 1 .1 5.2"),
    "4": (3.6, "M2.8 6V0L0 4.2h3.6"),
    "5": (3.4, "M3.2 0H.6L.3 2.6C.7 2.3 1.1 2.2 1.6 2.2C2.7 2.2 3.4 3 3.4 4.1C3.4 5.2 2.7 6 1.6 6C.9 6 .3 5.7 0 5.1"),
    "6": (3.4, "M2.9.3C2.6.1 2.2 0 1.8 0 .7 0 0 1.4 0 3.4 0 5.1.7 6 1.7 6 2.7 6 3.4 5.2 3.4 4.2 3.4 3.1 2.7 2.4 1.7 2.4"
               " .9 2.4.3 2.9 0 3.5"),
    "7": (3.4, "M0 0h3.4L1.2 6"),
    "8": (3.4, "M1.7 2.9A1.45 1.45 0 1 1 1.7 0 1.45 1.45 0 1 1 1.7 2.9ZM1.7 2.9A1.7 1.55 0 1 0 1.7 6 1.7 1.55 0 1 0 1.7 2.9Z"),
    "9": (3.4, "M.5 5.7C.8 5.9 1.2 6 1.6 6 2.7 6 3.4 4.6 3.4 2.6 3.4 .9 2.7 0 1.7 0 .7 0 0 .8 0 1.8 0 2.9.7 3.6 1.7 3.6"
               " 2.5 3.6 3.1 3.1 3.4 2.5"),
}
# Afstand tussen twee letters (pad tot pad) en de lijndikte, in letter-eenheden. Zoals Inter Bold in
# het labeltje van Bestanden: tussen de letters blijft ongeveer één lijndikte wit over (met 1.2 bij
# lijn 1.35 raakten de letters elkaar en las ZIP als ZP).
LETTERAFSTAND = 2.6
LETTERLIJN = 1.5


def _tekst_pad(tekst: str, x: float, y: float, schaal: float) -> tuple[str, float]:
    """Letters als één pad; geeft (pad, breedte) terug."""
    delen, pos = [], 0.0
    for i, teken in enumerate(tekst):
        breedte, d = LETTERS[teken]
        delen.append(_verschuif(d, x + pos * schaal, y, schaal))
        pos += breedte + (LETTERAFSTAND if i < len(tekst) - 1 else 0)
    return "".join(delen), pos * schaal


def _verschuif(d: str, dx: float, dy: float, s: float) -> str:
    """Paddata schalen en verschuiven (alleen de opdrachten die LETTERS gebruikt)."""
    uit, i = [], 0
    tokens = re.findall(r"[MmLlHhVvCcAaZz]|" + _GETAL.pattern, d)
    cmd = None
    per = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "A": 7, "Z": 0}
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            uit.append(t)
            i += 1
            if cmd in "Zz":
                continue
        n = per[cmd.upper()]
        waarden = [float(v) for v in tokens[i:i + n]]
        i += n
        absoluut = cmd.isupper()
        u = cmd.upper()
        if u in "ML":
            x, y = waarden
            uit.append(f"{_g(x * s + (dx if absoluut else 0))} {_g(y * s + (dy if absoluut else 0))} ")
        elif u == "H":
            uit.append(f"{_g(waarden[0] * s + (dx if absoluut else 0))} ")
        elif u == "V":
            uit.append(f"{_g(waarden[0] * s + (dy if absoluut else 0))} ")
        elif u == "C":
            p = []
            for j in range(0, 6, 2):
                p.append(f"{_g(waarden[j] * s + (dx if absoluut else 0))} {_g(waarden[j + 1] * s + (dy if absoluut else 0))}")
            uit.append(" ".join(p) + " ")
        elif u == "A":
            rx, ry, rot, groot, zin, x, y = waarden
            uit.append(f"{_g(rx * s)} {_g(ry * s)} {_g(rot)} {int(groot)} {int(zin)} "
                       f"{_g(x * s + (dx if absoluut else 0))} {_g(y * s + (dy if absoluut else 0))} ")
        if cmd == "M":
            cmd = "L"
        elif cmd == "m":
            cmd = "l"
    return "".join(uit).strip()


# ---------------------------------------------------------------- bestandssoorten ---

def _soorten_uit_bestanden() -> dict[str, tuple[str, str]]:
    """SOORTEN uit bugos-files (extensie -> (kleur, tekentje)), zodat Dolphin en Bestanden gelijk blijven."""
    bron = SYSTEM / "usr" / "bin" / "bugos-files"
    try:
        boom = ast.parse(bron.read_text(encoding="utf-8"))
        for knoop in boom.body:
            if isinstance(knoop, ast.Assign) and any(isinstance(d, ast.Name) and d.id == "SOORTEN"
                                                     for d in knoop.targets):
                return ast.literal_eval(knoop.value)
    except (OSError, SyntaxError, ValueError):
        pass
    return {}


SOORTEN = _soorten_uit_bestanden()


def _soort(ext: str, kleur: str, teken: str) -> tuple[str, str]:
    return SOORTEN.get(ext, (kleur, teken))


# familie -> (kleur, tekentje). Tekentje: 'tekst' en 'tabel' zijn regeltjes, de rest een lijnicoon.
# 'doos' tekent Bestanden als de mapomtrek ('map'); dat doen we hier ook.
FAMILIES = {
    "pdf": _soort("pdf", "#D3263A", "tekst"),
    "doc": _soort("docx", TINTEN["blauw"], "tekst"),
    "sheet": _soort("xlsx", TINTEN["groen"], "tabel"),
    "slides": _soort("pptx", TINTEN["oranje"], "tekst"),
    "txt": _soort("txt", TINTEN["grijs"], "tekst"),
    "archive": _soort("zip", TINTEN["grijs"], "doos"),
    "exe": _soort("exe", TINTEN["paars"], "doos"),
    "audio": _soort("mp3", TINTEN["roze"], "muziek"),
    "video": _soort("mp4", TINTEN["turkoois"], "film"),
    "image": (TINTEN["geel"], "foto"),
    "code": (TINTEN["grijs"], "code"),
    "web": (TINTEN["blauw"], "wereld"),
    "key": (TINTEN["grijs"], "slot"),
    "font": (TINTEN["grijs"], "letter"),
    "mail": (TINTEN["blauw"], "envelop"),
    "contact": (TINTEN["blauw"], "persoon"),
    "calendar": (TINTEN["oranje"], "kalender"),
    "db": (TINTEN["grijs"], "opslag"),
    "torrent": (TINTEN["grijs"], "download"),
    "game": (TINTEN["paars"], "spel"),
    "unknown": ("#8A8F9A", "tekst"),   # zoals Bestanden een onbekend bestand tekent
}

# Namen met een eigen labeltje: naam -> (familie, label).
LABELS = {
    "application-pdf": ("pdf", "PDF"), "application-postscript": ("pdf", "PS"), "viewpdf": ("pdf", "PDF"),
    "viewps": ("pdf", "PS"), "application-x-gzpostscript": ("pdf", "PS"), "viewdvi": ("pdf", "DVI"),
    "application-x-bzdvi": ("pdf", "DVI"), "application-x-gzdvi": ("pdf", "DVI"), "image-vnd.djvu": ("pdf", "DJVU"),
    "application-x-chm": ("pdf", "CHM"),
    "application-msword": ("doc", "DOC"), "application-vnd.ms-word": ("doc", "DOC"),
    "application-vnd.openxmlformats-officedocument.wordprocessingml.document": ("doc", "DOCX"),
    "application-vnd.oasis.opendocument.text": ("doc", "ODT"), "application-rtf": ("doc", "RTF"),
    "text-rtf": ("doc", "RTF"), "application-epub+zip": ("doc", "EPUB"), "x-office-document": ("doc", None),
    "application-vnd.ms-excel": ("sheet", "XLS"),
    "application-vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("sheet", "XLSX"),
    "application-vnd.oasis.opendocument.spreadsheet": ("sheet", "ODS"), "text-csv": ("sheet", "CSV"),
    "x-office-spreadsheet": ("sheet", None),
    "application-vnd.ms-powerpoint": ("slides", "PPT"),
    "application-vnd.openxmlformats-officedocument.presentationml.presentation": ("slides", "PPTX"),
    "application-vnd.oasis.opendocument.presentation": ("slides", "ODP"), "x-office-presentation": ("slides", None),
    "text-plain": ("txt", "TXT"), "text-x-generic": ("txt", None), "text-markdown": ("txt", "MD"),
    "text-x-markdown": ("txt", "MD"), "text-x-log": ("txt", "LOG"),
    "application-zip": ("archive", "ZIP"), "application-x-7z-compressed": ("archive", "7Z"),
    "application-x-rar": ("archive", "RAR"), "application-vnd.rar": ("archive", "RAR"),
    "application-x-tar": ("archive", "TAR"), "application-x-compressed-tar": ("archive", "GZ"),
    "application-gzip": ("archive", "GZ"), "application-x-gzip": ("archive", "GZ"),
    "application-x-bzip-compressed-tar": ("archive", "BZ"), "application-x-bzip": ("archive", "BZ"),
    "application-x-xz-compressed-tar": ("archive", "XZ"), "application-x-xz": ("archive", "XZ"),
    "application-zstd": ("archive", "ZST"), "application-x-zstd-compressed-tar": ("archive", "ZST"),
    "application-x-cd-image": ("archive", "ISO"), "application-x-iso": ("archive", "ISO"),
    "application-vnd.efi.iso": ("archive", "ISO"), "application-x-compressed-iso": ("archive", "ISO"),
    "package-x-generic": ("archive", None),
    "application-x-ms-dos-executable": ("exe", "EXE"), "application-x-msdownload": ("exe", "EXE"),
    "application-x-msi": ("exe", "MSI"), "application-x-executable": ("exe", None),
    "application-x-rpm": ("exe", "RPM"), "application-x-source-rpm": ("exe", "RPM"),
    "application-x-deb": ("exe", "DEB"), "application-vnd.debian.binary-package": ("exe", "DEB"),
    "application-vnd.appimage": ("exe", "APP"), "application-x-iso9660-appimage": ("exe", "APP"),
    "application-vnd.flatpak.ref": ("exe", "APP"), "application-vnd.flatpak": ("exe", "APP"),
    "application-vnd.flatpak.repo": ("exe", None), "application-vnd.android.package-archive": ("exe", "APK"),
    "android-package-archive": ("exe", "APK"),
    "audio-mpeg": ("audio", "MP3"), "audio-mp3": ("audio", "MP3"), "audio-x-mpeg": ("audio", "MP3"),
    "audio-flac": ("audio", "FLAC"), "audio-x-flac": ("audio", "FLAC"), "audio-ogg": ("audio", "OGG"),
    "audio-x-vorbis+ogg": ("audio", "OGG"), "audio-x-wav": ("audio", "WAV"), "audio-vnd.wave": ("audio", "WAV"),
    "audio-mp4": ("audio", "M4A"), "audio-x-m4a": ("audio", "M4A"), "audio-x-opus+ogg": ("audio", "OPUS"),
    "audio-x-generic": ("audio", None),
    "video-mp4": ("video", "MP4"), "video-x-matroska": ("video", "MKV"), "video-webm": ("video", "WEBM"),
    "video-x-msvideo": ("video", "AVI"), "video-quicktime": ("video", "MOV"), "video-x-generic": ("video", None),
    "image-png": ("image", "PNG"), "image-jpeg": ("image", "JPG"), "image-gif": ("image", "GIF"),
    "image-svg+xml": ("image", "SVG"), "image-svg+xml-compressed": ("image", "SVG"), "image-webp": ("image", "WEBP"),
    "image-bmp": ("image", "BMP"), "image-tiff": ("image", "TIF"), "image-heif": ("image", "HEIC"),
    "image-avif": ("image", "AVIF"), "image-x-xcf": ("image", "XCF"), "image-vnd.microsoft.icon": ("image", "ICO"),
    "image-x-icon": ("image", "ICO"), "image-x-generic": ("image", None),
    "text-html": ("web", "HTML"), "application-xhtml+xml": ("web", "HTML"),
    "text-css": ("code", "CSS"), "text-javascript": ("code", "JS"), "application-javascript": ("code", "JS"),
    "application-x-javascript": ("code", "JS"), "text-x-javascript": ("code", "JS"), "application-json": ("code", "JSON"),
    "application-xml": ("code", "XML"), "text-xml": ("code", "XML"), "text-x-python": ("code", "PY"),
    "text-x-python3": ("code", "PY"), "application-x-shellscript": ("code", "SH"), "text-x-shellscript": ("code", "SH"),
    "text-x-script": ("code", None), "text-x-csrc": ("code", "C"), "text-x-chdr": ("code", "H"),
    "text-x-c++src": ("code", "CPP"), "text-x-java": ("code", "JAVA"), "text-x-go": ("code", "GO"),
    "text-rust": ("code", "RS"), "text-x-rust": ("code", "RS"), "application-sql": ("code", "SQL"),
    "text-x-sql": ("code", "SQL"), "application-toml": ("code", "TOML"),
    "font-ttf": ("font", "TTF"), "application-x-font-ttf": ("font", "TTF"), "font-otf": ("font", "OTF"),
    "application-x-font-otf": ("font", "OTF"),
    "text-calendar": ("calendar", "ICS"), "text-vcalendar": ("calendar", "ICS"), "text-x-vcard": ("contact", "VCF"),
    "text-directory": ("contact", "VCF"),
    "unknown": ("unknown", None), "application-octet-stream": ("unknown", None),
    # Office-bestanden die mensen van Windows meenemen
    "application-msonenote": ("doc", "ONE"), "application-vnd.ms-publisher": ("doc", "PUB"),
    "vnd.ms-publisher": ("doc", "PUB"), "application-vnd.ms-infopath": ("doc", None),
    "application-msoutlook": ("mail", None), "application-vnd.google-earth.kml+xml": ("web", "KML"),
}

# Alle andere bestandssoorten die Breeze kent: die krijgen ook het BugOS-papiertje (anders
# kiest KDE de Breeze-versie). Ingedeeld met de regels in _familie().
BREEZE_SOORTEN = """
    android-package-archive application-atom+xml application-certificate application-dicom application-epub+zip
    application-gzip application-illustrator application-javascript application-json application-mathml+xml
    application-msword application-msword-template application-octet-stream application-ogg application-pdf
    application-pgp application-pgp-encrypted application-pgp-keys application-pgp-signature application-pkcs12
    application-pkcs7-mime application-pkcs7-signature application-pkix-cerl application-pkix-cert application-postscript
    application-relaxng application-rss+xml application-rtf application-sql application-sxw
    application-toml application-vnd.android.app-bundle application-vnd.android.package-archive application-vnd.appimage
    application-vnd.debian.binary-package application-vnd.efi.iso application-vnd.flatpak.ref application-vnd.iccprofile
    application-vnd.kde.kleopatra.keygroup application-vnd.ms-access application-vnd.ms-excel
    application-vnd.ms-excel.addin.macroenabled.12 application-vnd.ms-excel.sheet.binary.macroenabled.12
    application-vnd.ms-excel.sheet.macroenabled.12 application-vnd.ms-excel.template.macroenabled.12
    application-vnd.ms-powerpoint application-vnd.ms-powerpoint.addin.macroenabled.12
    application-vnd.ms-powerpoint.presentation.macroenabled.12 application-vnd.ms-powerpoint.slide.macroenabled.12
    application-vnd.ms-powerpoint.slideshow.macroenabled.12 application-vnd.ms-powerpoint.template.macroenabled.12
    application-vnd.ms-word application-vnd.ms-word.document.macroenabled.12 application-vnd.ms-word.template.macroenabled.12
    application-vnd.oasis.opendocument.chart application-vnd.oasis.opendocument.database
    application-vnd.oasis.opendocument.draw.template application-vnd.oasis.opendocument.drawing
    application-vnd.oasis.opendocument.drawing.template application-vnd.oasis.opendocument.formula
    application-vnd.oasis.opendocument.formula-template application-vnd.oasis.opendocument.graphics
    application-vnd.oasis.opendocument.image application-vnd.oasis.opendocument.presentation
    application-vnd.oasis.opendocument.presentation-template application-vnd.oasis.opendocument.spreadsheet
    application-vnd.oasis.opendocument.spreadsheet-template application-vnd.oasis.opendocument.text
    application-vnd.oasis.opendocument.text-master application-vnd.oasis.opendocument.text-template
    application-vnd.oasis.opendocument.web-template application-vnd.openofficeorg.extension
    application-vnd.openxmlformats-officedocument.spreadsheetml.sheet
    application-vnd.openxmlformats-officedocument.wordprocessingml.document application-vnd.rar
    application-vnd.rn-realmedia application-vnd.scribus application-vnd.snap application-vnd.sqlite3
    application-vnd.squashfs application-vnd.stardivision.calc application-vnd.stardivision.draw
    application-vnd.stardivision.mail application-vnd.stardivision.math application-vnd.sun.xml.calc
    application-vnd.sun.xml.calc.template application-vnd.sun.xml.draw application-vnd.sun.xml.draw.template
    application-vnd.sun.xml.impress application-vnd.sun.xml.impress.template application-vnd.sun.xml.math
    application-vnd.sun.xml.writer application-vnd.sun.xml.writer.global application-vnd.sun.xml.writer.template
    application-vnd.visio application-vnd.wordperfect application-wps-office.doc application-wps-office.docx
    application-wps-office.dot application-wps-office.dotx application-wps-office.pot application-wps-office.potx
    application-wps-office.ppt application-wps-office.pptx application-wps-office.xls application-wps-office.xlsx
    application-wps-office.xlt application-wps-office.xltx application-x-7z-compressed application-x-abiword
    application-x-ace application-x-apple-diskimage application-x-applix-spreadsheet application-x-applix-word
    application-x-ar application-x-arc application-x-archive application-x-arj application-x-audacity-project
    application-x-awk application-x-bittorrent application-x-blender application-x-bzdvi
    application-x-bzip application-x-bzip-compressed-tar application-x-cd-image application-x-cda application-x-chm
    application-x-compress application-x-compressed-iso application-x-compressed-tar application-x-core application-x-cpio
    application-x-cue application-x-deb application-x-designer application-x-desktop application-x-executable
    application-x-executable-script application-x-fictionbook+xml application-x-flash-video application-x-font-afm
    application-x-font-bdf application-x-font-otf application-x-font-pcf application-x-font-snf application-x-font-ttf
    application-x-font-ttx application-x-font-type1 application-x-gdscript application-x-gettext-translation
    application-x-gnumeric application-x-gzdvi application-x-gzip application-x-gzpostscript application-x-iso
    application-x-iso9660-appimage application-x-jar application-x-java application-x-java-applet
    application-x-java-archive application-x-javascript application-x-kdenlive application-x-kdenlivetitle
    application-x-kmymoney application-x-krita application-x-kword application-x-lha application-x-lzma-compressed-tar
    application-x-lzop application-x-m4 application-x-mimearchive application-x-mplayer2 application-x-ms-dos-executable
    application-x-ms-shortcut application-x-ms-wim application-x-msdownload application-x-mswinurl application-x-mswrite
    application-x-object application-x-openvpn-profile application-x-cisco-vpn-settings application-x-pak
    application-x-partial-download application-x-pem-key application-x-perl application-x-php application-x-pkcs12
    application-x-pkcs7-certificates application-x-plasma application-x-python-bytecode application-x-qemu-disk
    application-x-quattropro application-x-rar application-x-raw-disk-image application-x-rpm application-x-ruby
    application-x-sami application-x-sharedlib application-x-shellscript application-x-shockwave-flash application-x-siag
    application-x-source-rpm application-x-sqlite2 application-x-sqlite3 application-x-srt application-x-subrip
    application-x-tar application-x-tarz application-x-theme application-x-trash application-x-troff-man
    application-x-tzo application-x-vdi-disk application-x-wmf application-x-x509-ca-cert application-x-x509-user-cert
    application-x-xliff application-x-xpinstall application-x-xz-compressed-tar application-x-xz-pkg application-x-zerosize
    application-x-zip-compressed-fb2 application-x-zoo application-xhtml+xml application-xml application-xsd
    application-xslt+xml application-zip audio-ac3 audio-flac audio-midi audio-mp2 audio-mp3 audio-mp4 audio-mpeg
    audio-ogg audio-prs.sid audio-vn.rn-realmedia audio-vnd.rn-realvideo audio-vnd.wave audio-x-adpcm audio-x-aiff
    audio-x-flac audio-x-flac+ogg audio-x-generic audio-x-monkey audio-x-mp2 audio-x-mpeg audio-x-speex+ogg
    audio-x-vorbis+ogg audio-x-wav audiobook encrypted font-otf font-ttf fonts-package image-bmp image-gif image-ico
    image-jpeg image-jpeg2000 image-png image-svg+xml image-svg+xml-compressed image-tiff image-vnd.dgn image-vnd.djvu
    image-vnd.dwg image-vnd.microsoft.icon image-x-adobe-dng image-x-compressed-xcf image-x-emf image-x-eps
    image-x-generic image-x-ico image-x-icon image-x-krita image-x-portable-bitmap image-x-psd image-x-svg+xml
    image-x-tga image-x-vnd.trolltech.qpicture image-x-win-bitmap image-x-win-bmp image-x-wmf image-x-xcf image-x-xfig
    libreoffice-database libreoffice-drawing libreoffice-drawing-template libreoffice-extension libreoffice-formula
    libreoffice-master-document libreoffice-oasis-database libreoffice-oasis-drawing libreoffice-oasis-drawing-template
    libreoffice-oasis-formula libreoffice-oasis-master-document libreoffice-oasis-presentation
    libreoffice-oasis-presentation-template libreoffice-oasis-spreadsheet libreoffice-oasis-spreadsheet-template
    libreoffice-oasis-text libreoffice-oasis-text-template libreoffice-oasis-web-template libreoffice-presentation
    libreoffice-presentation-template libreoffice-spreadsheet libreoffice-spreadsheet-template libreoffice-text
    libreoffice-text-template message message-news message-partial message-rfc822 message-x-gnu-rmail odf
    package-x-generic podcast text-calendar text-csharp text-css text-csv text-directory text-dockerfile text-enriched
    text-html text-javascript text-markdown text-plain text-rdf text-rdf+xml text-rtf text-rust text-sgml text-troff
    text-vcalendar text-vnd.abc text-vnd.trolltech.linguist text-vnd.typst text-vnd.wap.wml text-vtt text-wiki
    text-x-adasrc text-x-authors text-x-bibtex text-x-c++hdr text-x-c++src text-x-changelog text-x-chdr text-x-cmake
    text-x-copying text-x-credits text-x-csharp text-x-csrc text-x-dtd text-x-generic text-x-gettext-translation
    text-x-go text-x-haskell text-x-hex text-x-install text-x-java text-x-java-source text-x-javascript
    text-x-katefilelist text-x-kotlin text-x-ldif text-x-lilypond text-x-log text-x-lua text-x-makefile text-x-markdown
    text-x-microdvd text-x-mpsub text-x-nfo text-x-nim text-x-objchdr text-x-objcsrc text-x-opml text-x-opml+xml
    text-x-pascal text-x-patch text-x-plain text-x-po text-x-python text-x-python2 text-x-python3 text-x-qml text-x-r
    text-x-readme text-x-rpm-spec text-x-rust text-x-sass text-x-scala text-x-script text-x-scss text-x-shellscript
    text-x-sql text-x-ssa text-x-subviewer text-x-tcl text-x-tex text-x-texinfo text-x-vcard text-x-xslfo text-xml
    unknown video-mlt-playlist video-mp2t video-mp4 video-vnd.rn-realvideo video-webm video-x-anim video-x-flic
    video-x-flv video-x-generic video-x-matroska video-x-mng video-x-ms-wmp video-x-ms-wmv video-x-msvideo
    video-x-ogm+ogg video-x-theora+ogg video-x-wmv viewbib viewdvi viewhtml viewpdf viewps virtualbox-hdd virtualbox-ova
    virtualbox-ovf virtualbox-vbox virtualbox-vbox-extpack virtualbox-vdi virtualbox-vhd virtualbox-vmdk
    x-mail-distribution-list x-media-podcast x-office-address-book x-office-calendar x-office-contact x-office-document
    x-office-drawing x-office-presentation x-office-spreadsheet
""".split() + """
    apple-vnd.apple.pkpasses application-mac-binhex40 application-msonenote application-msoutlook
    application-vnd.apple.pkpass application-vnd.apple.pkpasses application-vnd.google-earth.kml+xml
    application-vnd.ms-infopath application-vnd.ms-publisher application-vnd.nintendo.snes.rom
    application-vnd.nokia.xml.qt.resource application-x-egon application-x-gameboy-rom application-x-gamecube-rom
    application-x-gba-rom application-x-godot-project application-x-godot-resource application-x-godot-scene
    application-x-godot-shader application-x-it87 application-x-k3b application-x-kcsrc application-x-kexi-connectiondata
    application-x-kexiproject-shortcut application-x-kexiproject-sqlite application-x-kexiproject-sqlite2
    application-x-kexiproject-sqlite3 application-x-kformula application-x-kgetlist application-x-kontour
    application-x-kplato application-x-kvtml application-x-labplot2 application-x-lyx application-x-macbinary
    application-x-marble application-x-n64-rom application-x-nes-rom application-x-nintendo-ds-rom application-x-nzb
    application-x-qet-element application-x-qet-project application-x-rdata application-x-root application-x-sif
    application-x-skg application-x-skgc application-x-srtrip application-x-tgif application-xmind text-fortran
    text-vnd.kde.kcrash-report text-x-apport text-x-fortran text-xmcd uri-mms uri-mmst uri-pnm uri-rtspt uri-rtspu
    video-vivo video-wavelet video-x-google-vlc-plugin video-x-javafx vnd.ms-publisher x-kde-nsplugin-generated
""".split()   # de rest van Breeze (zonder de kapotte namen in Breeze zelf, zoals "none")

# (familie, regel) op volgorde: de eerste die past wint.
_REGELS = [
    ("pdf", r"^(viewpdf|viewps|viewdvi|application-x-(gz|bz)(dvi|postscript)|image-vnd\.djvu|application-x-chm)$"),
    ("game", r"(-rom$|\.rom$)"),
    ("db", r"kexi"),
    ("mail", r"msoutlook"),
    ("web", r"(google-earth|x-marble)"),
    ("torrent", r"(x-nzb$|kgetlist)"),
    ("archive", r"(binhex|macbinary)"),
    ("txt", r"(kcrash-report|x-apport$|^text-xmcd$)"),
    ("video", r"^uri-(mms|mmst|pnm|rtspt|rtspu)$"),
    ("code", r"(godot|qt\.resource|x-kcsrc$|fortran)"),
    ("doc", r"(msonenote|ms-publisher|ms-infopath|x-lyx$|kformula)"),
    ("txt", r"^(text-x-(plain|readme|authors|changelog|copying|credits|install|nfo|hex|bibtex|tex|texinfo|ssa|microdvd|"
            r"mpsub|subviewer|po|gettext-translation)|text-(enriched|troff|wiki|vtt)|viewbib|application-x-"
            r"(troff-man|subrip|srt|sami|gettext-translation|xliff))$"),
    ("doc", r"(msword|ms-word|wordprocessingml|opendocument\.(text|formula|web)|libreoffice(-oasis)?-(text|formula|"
            r"master-document|web)|sun\.xml\.(writer|math)|stardivision\.(mail|math)|wps-office\.do|x-abiword|x-kword|"
            r"wordperfect|x-mswrite|application-sxw|applix-word|fictionbook|fb2|^odf$)"),
    ("sheet", r"(ms-excel|spreadsheetml|opendocument\.(spreadsheet|chart)|libreoffice(-oasis)?-spreadsheet|"
              r"sun\.xml\.calc|stardivision\.calc|wps-office\.xl|x-gnumeric|applix-spreadsheet|quattropro|x-siag|"
              r"x-kmymoney)"),
    ("slides", r"(ms-powerpoint|presentationml|opendocument\.presentation|libreoffice(-oasis)?-presentation|"
               r"sun\.xml\.impress|wps-office\.p)"),
    ("db", r"(sqlite|opendocument\.database|libreoffice(-oasis)?-database|ms-access)"),
    ("image", r"^(image-|application-(vnd\.oasis\.opendocument\.(graphics|drawing|draw|image)|vnd\.sun\.xml\.draw|"
              r"vnd\.stardivision\.draw|illustrator|x-krita|vnd\.visio|dicom|vnd\.scribus|x-wmf|vnd\.iccprofile|"
              r"x-blender)|libreoffice(-oasis)?-drawing|x-office-drawing)"),
    ("audio", r"^(audio-|audiobook$|podcast$|x-media-podcast$|application-(ogg|x-audacity-project|x-cda))"),
    ("video", r"^(video-|application-(x-flash-video|x-shockwave-flash|vnd\.rn-realmedia|x-mplayer2|x-kdenlive))"),
    ("key", r"(pgp|pkcs|pkix|pem-key|x509|certificate|^encrypted$|openvpn|cisco-vpn|kleopatra)"),
    ("font", r"(^font-|x-font-|^fonts-package$)"),
    ("mail", r"(^message|mail-distribution)"),
    ("contact", r"(vcard|^text-directory$|x-office-contact|x-office-address-book|ldif)"),
    ("calendar", r"(calendar)"),
    ("torrent", r"(bittorrent|partial-download)"),
    ("exe", r"(rpm|debian|x-deb$|flatpak|vnd\.snap|appimage|android|xpinstall|x-plasma$|openofficeorg\.extension|"
            r"libreoffice-extension|executable|ms-dos|msdownload|x-msi$|sharedlib|x-object$|x-core$|ms-shortcut|"
            r"x-desktop$|java-applet|x-java$)"),
    ("archive", r"(zip|tar|rar|7z|gzip|bzip|x-xz|lzma|lzop|compress|x-ace$|x-ar$|x-arc$|archive|x-arj$|cpio|x-lha$|"
                r"x-zoo$|x-tzo$|squashfs|ms-wim|x-pak$|x-jar$|cd-image|x-iso$|\.iso$|diskimage|raw-disk|qemu-disk|vdi-disk|"
                r"virtualbox|x-cue$|x-theme$)"),
    ("web", r"^(viewhtml|application-x-mswinurl)$"),
    ("code", r"^(text-|application-(x-)?(javascript|json|xml|xsd|xslt|relaxng|toml|sql|atom|rss|mathml|php|ruby|perl|"
             r"awk|m4|gdscript|shellscript|executable-script|python-bytecode|designer|kdenlivetitle))"),
]


# Het labeltje van de andere soorten: de extensie uit shared-mime-info (de eerste *.ext van dat type,
# hoogstens 4 tekens), zoals Bestanden op elk bestand met een extensie het labeltje zet. Eenmalig
# uitgelezen in de testbank en hier vastgelegd, zodat maken op elk systeem hetzelfde oplevert.
# Algemene namen krijgen de bekendste extensie van hun familie: KDE vraagt bijv. voor een .docm
# "application-vnd.ms-word.document.macroEnabled.12" (met hoofdletters, die kan een pictogramnaam niet
# hebben) en valt dan terug op x-office-document.
EXTENSIES = dict(regel.split("=") for regel in """
    application-atom+xml=ATOM application-dicom=DCM application-illustrator=AI application-mac-binhex40=HQX
    application-mathml+xml=MML application-msword-template=DOT application-ogg=OGX application-pgp=PGP
    application-pgp-encrypted=PGP application-pgp-keys=KEY application-pgp-signature=ASC application-pkcs12=P12
    application-pkcs7-mime=P7C application-pkcs7-signature=P7S application-pkix-cert=CER application-relaxng=RNG
    application-rss+xml=RSS application-sxw=SXW application-vnd.iccprofile=ICC application-vnd.ms-access=MDB
    application-vnd.ms-excel.addin.macroenabled.12=XLAM application-vnd.ms-excel.sheet.binary.macroenabled.12=XLSB
    application-vnd.ms-excel.sheet.macroenabled.12=XLSM application-vnd.ms-excel.template.macroenabled.12=XLTM
    application-vnd.ms-powerpoint.addin.macroenabled.12=PPAM
    application-vnd.ms-powerpoint.presentation.macroenabled.12=PPTM
    application-vnd.ms-powerpoint.slide.macroenabled.12=SLDM
    application-vnd.ms-powerpoint.slideshow.macroenabled.12=PPSM
    application-vnd.ms-powerpoint.template.macroenabled.12=POTM
    application-vnd.ms-word.document.macroenabled.12=DOCM application-vnd.ms-word.template.macroenabled.12=DOTM
    application-vnd.nintendo.snes.rom=SFC application-vnd.oasis.opendocument.chart=ODC
    application-vnd.oasis.opendocument.database=ODB application-vnd.oasis.opendocument.formula=ODF
    application-vnd.oasis.opendocument.formula-template=OTF application-vnd.oasis.opendocument.graphics=ODG
    application-vnd.oasis.opendocument.image=ODI application-vnd.oasis.opendocument.presentation-template=OTP
    application-vnd.oasis.opendocument.spreadsheet-template=OTS application-vnd.oasis.opendocument.text-master=ODM
    application-vnd.oasis.opendocument.text-template=OTT application-vnd.oasis.opendocument.web-template=OTH
    application-vnd.openofficeorg.extension=OXT application-vnd.rn-realmedia=RM application-vnd.snap=SNAP
    application-vnd.squashfs=SQSH application-vnd.stardivision.calc=SDC application-vnd.stardivision.draw=SDA
    application-vnd.stardivision.mail=SMD application-vnd.stardivision.math=SMF application-vnd.sun.xml.calc=SXC
    application-vnd.sun.xml.calc.template=STC application-vnd.sun.xml.draw=SXD
    application-vnd.sun.xml.draw.template=STD application-vnd.sun.xml.impress=SXI
    application-vnd.sun.xml.impress.template=STI application-vnd.sun.xml.math=SXM application-vnd.sun.xml.writer=SXW
    application-vnd.sun.xml.writer.global=SXG application-vnd.sun.xml.writer.template=STW application-vnd.visio=VSD
    application-vnd.wordperfect=WP application-wps-office.doc=DOC application-wps-office.docx=DOCX
    application-wps-office.dot=DOT application-wps-office.dotx=DOTX application-wps-office.pot=POT
    application-wps-office.potx=POTX application-wps-office.ppt=PPT application-wps-office.pptx=PPTX
    application-wps-office.xls=XLS application-wps-office.xlsx=XLSX application-wps-office.xlt=XLT
    application-wps-office.xltx=XLTX application-x-abiword=ABW application-x-ace=ACE
    application-x-apple-diskimage=DMG application-x-applix-spreadsheet=AS application-x-applix-word=AW
    application-x-archive=A application-x-arj=ARJ application-x-awk=AWK application-x-cda=CDA
    application-x-cisco-vpn-settings=PCF application-x-compress=Z application-x-cpio=CPIO application-x-cue=CUE
    application-x-designer=UI application-x-egon=EGON application-x-fictionbook+xml=FB2
    application-x-flash-video=FLV application-x-font-afm=AFM application-x-font-bdf=BDF application-x-font-pcf=PCF
    application-x-font-snf=SNF application-x-font-ttx=TTX application-x-font-type1=PFA application-x-gameboy-rom=GB
    application-x-gamecube-rom=ISO application-x-gba-rom=GBA application-x-gdscript=GD
    application-x-gettext-translation=GMO application-x-gnumeric=GNM application-x-godot-resource=RES
    application-x-godot-scene=SCN application-x-it87=IT87 application-x-jar=JAR application-x-java-archive=JAR
    application-x-kexiproject-sqlite=KEXI application-x-kexiproject-sqlite2=KEXI
    application-x-kexiproject-sqlite3=KEXI application-x-kformula=KFO application-x-kgetlist=KGT
    application-x-kmymoney=KMY application-x-kontour=KON application-x-krita=KRA application-x-kword=KWD
    application-x-lha=LHA application-x-lyx=LYX application-x-lzma-compressed-tar=TLZ application-x-lzop=LZO
    application-x-m4=M4 application-x-mimearchive=MHT application-x-mplayer2=WMP application-x-ms-shortcut=LNK
    application-x-ms-wim=WIM application-x-mswinurl=URL application-x-mswrite=WRI application-x-n64-rom=N64
    application-x-nes-rom=NES application-x-nintendo-ds-rom=NDS application-x-nzb=NZB application-x-object=O
    application-x-openvpn-profile=OVPN application-x-pak=PAK application-x-partial-download=PART
    application-x-perl=PL application-x-php=PHP application-x-pkcs12=P12 application-x-pkcs7-certificates=P7B
    application-x-python-bytecode=PYC application-x-qemu-disk=QCOW application-x-quattropro=WB1
    application-x-raw-disk-image=IMG application-x-ruby=RB application-x-sami=SMI application-x-sharedlib=SO
    application-x-shockwave-flash=SWF application-x-siag=SIAG application-x-srt=SRT application-x-subrip=SRT
    application-x-tarz=TAZ application-x-tgif=OBJ application-x-trash=BAK application-x-troff-man=MAN
    application-x-tzo=TZO application-x-vdi-disk=VDI application-x-wmf=WMF application-x-x509-ca-cert=DER
    application-x-xliff=XLF application-x-xpinstall=XPI application-x-zip-compressed-fb2=FB2 application-x-zoo=ZOO
    application-xsd=XSD application-xslt+xml=XSL audio-ac3=AC3 audio-midi=MID audio-mp2=MP2 audio-prs.sid=SID
    audio-x-aiff=AIFF audio-x-flac+ogg=OGA audio-x-mp2=MP2 audio-x-speex+ogg=OGA image-ico=ICO image-jpeg2000=JP2
    image-vnd.dwg=DWG image-x-adobe-dng=DNG image-x-emf=EMF image-x-eps=EPS image-x-ico=ICO
    image-x-portable-bitmap=PBM image-x-psd=PSD image-x-tga=TGA image-x-win-bitmap=CUR image-x-wmf=WMF
    image-x-xfig=FIG libreoffice-database=ODB libreoffice-drawing=ODG libreoffice-drawing-template=OTG
    libreoffice-formula=ODF libreoffice-master-document=ODM libreoffice-oasis-database=ODB
    libreoffice-oasis-drawing=ODG libreoffice-oasis-drawing-template=OTG libreoffice-oasis-formula=ODF
    libreoffice-oasis-master-document=ODM libreoffice-oasis-presentation=ODP
    libreoffice-oasis-presentation-template=OTP libreoffice-oasis-spreadsheet=ODS
    libreoffice-oasis-spreadsheet-template=OTS libreoffice-oasis-text=ODT libreoffice-oasis-text-template=OTT
    libreoffice-oasis-web-template=OTH libreoffice-presentation=ODP libreoffice-presentation-template=OTP
    libreoffice-spreadsheet=ODS libreoffice-spreadsheet-template=OTS libreoffice-text=ODT
    libreoffice-text-template=OTT message-rfc822=EML odf=ODF text-rdf=RDF text-sgml=SGML text-troff=TR
    text-vnd.abc=ABC text-vnd.trolltech.linguist=TS text-vnd.wap.wml=WML text-vtt=VTT text-x-adasrc=ADB
    text-x-bibtex=BIB text-x-c++hdr=HH text-x-csharp=CS text-x-dtd=DTD text-x-fortran=F
    text-x-gettext-translation=PO text-x-haskell=HS text-x-hex=HEX text-x-kotlin=KT text-x-ldif=LDIF
    text-x-lilypond=LY text-x-lua=LUA text-x-makefile=MK text-x-microdvd=SUB text-x-mpsub=SUB text-x-nfo=NFO
    text-x-nim=NIM text-x-objcsrc=M text-x-opml=OPML text-x-opml+xml=OPML text-x-pascal=P text-x-patch=DIFF
    text-x-po=PO text-x-qml=QML text-x-rpm-spec=SPEC text-x-sass=SASS text-x-scala=SC text-x-scss=SCSS
    text-x-ssa=SSA text-x-subviewer=SUB text-x-tcl=TCL text-x-tex=TEX text-x-texinfo=TEXI text-x-xslfo=FO
    video-mp2t=M2T video-vivo=VIV video-vnd.rn-realvideo=RV video-x-flic=FLI video-x-flv=FLV video-x-javafx=FXM
    video-x-mng=MNG video-x-ms-wmp=WMP video-x-ms-wmv=WMV video-x-ogm+ogg=OGM video-x-theora+ogg=OGG
    x-office-document=DOC x-office-spreadsheet=XLS x-office-presentation=PPT application-vnd.ms-infopath=XSN
""".split())


def _familie(naam: str) -> tuple[str, str | None]:
    if naam in LABELS:
        fam, label = LABELS[naam]
        return fam, label or EXTENSIES.get(naam)
    for fam, regel in _REGELS:
        if re.search(regel, naam):
            return fam, EXTENSIES.get(naam)
    return "unknown", EXTENSIES.get(naam)


# ---------------------------------------------------------------- het papiertje ---
# Verhoudingen uit teken_papier() in bugos-files (daar 62 x 80 beeldpunten).
PL, PT, PW, PH = 8.5, 4.0, 31.0, 40.0
HOEK = PW * 0.26


def papier_svg(familie: str, label: str | None) -> str:
    kleur, soort = FAMILIES[familie]
    r, b = PL + PW, PT + PH
    straal = 3.0
    omtrek = (f"M{_g(PL + straal)} {_g(PT)}H{_g(r - HOEK)}L{_g(r)} {_g(PT + HOEK)}V{_g(b - straal)}"
              f"Q{_g(r)} {_g(b)} {_g(r - straal)} {_g(b)}H{_g(PL + straal)}Q{_g(PL)} {_g(b)} {_g(PL)} {_g(b - straal)}"
              f"V{_g(PT + straal)}Q{_g(PL)} {_g(PT)} {_g(PL + straal)} {_g(PT)}Z")
    vouw = (f"M{_g(r - HOEK)} {_g(PT)}V{_g(PT + HOEK - 2)}Q{_g(r - HOEK)} {_g(PT + HOEK)} "
            f"{_g(r - HOEK + 2)} {_g(PT + HOEK)}H{_g(r)}")
    delen = [
        f'<path class="ColorScheme-Background" fill="currentColor" d="{omtrek}"/>',
        f'<path fill="#FFFFFF" fill-opacity="0.05" d="{omtrek}"/>',
        f'<path class="ColorScheme-Text" fill="currentColor" fill-opacity="0.035" d="{vouw}Z"/>',
        f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="0.16" stroke-width="0.75" '
        f'stroke-linejoin="round" d="{omtrek}{vouw}"/>',
    ]
    if soort in ("tekst", "tabel"):
        regels = []
        for i in range(4 if soort == "tekst" else 3):
            y = PT + PH * (0.26 + i * 0.11)
            breed = 0.62 if i % 2 == 0 else 0.48
            eind = 0.82 if soort == "tabel" else 0.18 + breed
            regels.append(f"M{_g(PL + PW * 0.18)} {_g(y)}H{_g(PL + PW * eind)}")
        delen.append(f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="0.16" '
                     f'stroke-width="1.1" stroke-linecap="round" d="{"".join(regels)}"/>')
    else:
        glyph = "map" if soort == "doos" else soort
        m = PW * 0.46
        s = m / 24
        delen.append(f'<g transform="translate({_g(PL + PW / 2 - m / 2)} {_g(PT + PH * 0.22)}) scale({_g(s)})">'
                     f'<path fill="none" stroke="{kleur}" stroke-width="2" stroke-linecap="round" '
                     f'stroke-linejoin="round" d="{pad(glyph)}"/></g>')
    # Zonder extensie geen labeltje, net als in Bestanden (vroeger: een leeg gekleurd labeltje, dat
    # las als een label waar de tekst uit was gevallen).
    if label:
        schaal = 0.62
        tekst_d, breedte = _tekst_pad(label, 0, 0, schaal)
        hoogte = PH * 0.19
        rand = 2.1
        lx, ly = PL + PW * 0.12, b - PH * 0.3
        bw = breedte + 2 * rand + LETTERLIJN * schaal
        if lx + bw > r - 1.5:
            raise ValueError(f"labeltje {label!r} past niet op het papiertje")
        tekst_d, _ = _tekst_pad(label, lx + rand + LETTERLIJN * schaal / 2, ly + (hoogte - 6 * schaal) / 2, schaal)
        delen.append(f'<path fill="{kleur}" d="{_rrect(lx, ly, bw, hoogte, 2)}"/>')
        delen.append(f'<path fill="none" stroke="#FFFFFF" stroke-width="{_g(LETTERLIJN * schaal)}" '
                     f'stroke-linecap="round" stroke-linejoin="round" d="{tekst_d}"/>')
    return _svg("".join(delen))


DOC_LIJN = ('<path d="M7 3.5h6.5l4.5 4.5v11.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z"/>'
            '<path d="M13.5 3.5V8H18"/>')


def papier_klein(familie: str) -> str:
    """Lijnpapiertje: de omtrek in de tekstkleur, de inhoud in de kleur van het labeltje."""
    kleur, soort = FAMILIES[familie]
    if soort == "tekst":
        inhoud = f'<path stroke="{kleur}" d="M9 12.5h6M9 16h4"/>'
    elif soort == "tabel":
        inhoud = f'<path stroke="{kleur}" d="M9 11.5h6M9 14.5h6M9 17.5h6"/>'
    else:
        glyph = "map" if soort == "doos" else soort
        s = 0.42
        inhoud = (f'<g transform="translate(12 14.6) scale({_g(s)}) translate(-12 -12)" stroke="{kleur}" '
                  f'stroke-width="{_g(BINNEN_LIJN / s)}"><path d="{pad(glyph)}"/></g>')
    return DOC_LIJN + inhoud


# ------------------------------------------------------------------------- maken ---

def maak(b: basis.Bouwer) -> None:
    _mappen_instellen()
    gedaan: set[tuple[str, str]] = set()

    def schrijf(map_: str, naam: str, svg: str) -> None:
        if (map_, naam) in gedaan:
            raise ValueError(f"plaatsen: {map_}/{naam} twee keer")
        gedaan.add((map_, naam))
        b.schrijf(map_, naam, svg)
        if map_ in GESCHAALD:
            for s in SCHALEN:
                b.schrijf(f"{map_}@{s}x", naam, svg)

    def plek(namen: list[str], groot: str, klein_set: dict[str, str]) -> None:
        for naam in namen:
            schrijf("places/scalable", naam, groot)
            schrijf("places/scalable", naam + "-symbolic", klein_set["scalable"])
            for maat in ("16", "22"):
                schrijf(f"places/{maat}", naam, klein_set[maat])
                schrijf(f"places/{maat}", naam + "-symbolic", klein_set[maat])

    # Mappen en plekken.
    for namen, teken, (soort, glyph) in MAPPEN:
        plek(namen, map_svg(teken, open_=(soort == "open")), _lijnset(soort, glyph))
    for naam, tint in KLEURMAPPEN.items():
        plek([naam], map_svg(None, tint=tint), _lijnset("map", None))
    plek(["user-trash"], prullenbak_svg(), _lijnset("teken", "prullenbak"))
    plek(["user-trash-full"], prullenbak_svg(vol=True), _lijnset("teken", "prullenbak-vol"))
    plek(["network-server"], server_svg(), _lijnset("teken", "server"))

    # De actie "Nieuwe map" (Dolphin, elke KDE-bestandskiezer): de map met plusje, net als de
    # knop "Nieuwe map" in Bestanden. Een actie, dus een lijnicoon op elke maat.
    for naam in ("folder-new", "folder-add"):
        for map_, svg in (("actions/16", klein(LIJN["map-plus"])), ("actions/scalable", symbolisch(LIJN["map-plus"]))):
            schrijf(map_, naam, svg)
            schrijf(map_, naam + "-symbolic", svg)

    # Apparaten: lijniconen in de tekstkleur.
    for glyph, namen in APPARATEN.items():
        binnen = EIGEN.get(glyph) or LIJN[glyph]
        for naam in namen:
            for map_, svg in (("devices/16", klein(binnen)), ("devices/scalable", symbolisch(binnen))):
                schrijf(map_, naam, svg)
                schrijf(map_, naam + "-symbolic", svg)

    # Bestandssoorten.
    namen = list(dict.fromkeys(list(LABELS) + BREEZE_SOORTEN))
    for naam in namen:
        fam, label = _familie(naam)
        schrijf("mimetypes/scalable", naam, papier_svg(fam, label))
        schrijf("mimetypes/22", naam, symbolisch(papier_klein(fam), maat=22))
        schrijf("mimetypes/16", naam, klein(papier_klein(fam)))
    # Netwerkplekken die als bestandssoort binnenkomen (smb://).
    for naam, groot, glyph in (("application-x-smb-workgroup", map_svg("wereld"), "wereld"),
                               ("application-x-smb-server", server_svg(), "server")):
        set_ = _lijnset("teken", glyph)
        schrijf("mimetypes/scalable", naam, groot)
        schrijf("mimetypes/22", naam, set_["22"])
        schrijf("mimetypes/16", naam, set_["16"])

    print(kleurverslag())
