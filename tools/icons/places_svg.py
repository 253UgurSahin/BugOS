"""SVG-hulpjes en de eigen lijntekeningen (EIGEN) voor places.py."""

from __future__ import annotations

import math
import re
from xml.etree import ElementTree as ET

from base import STIJLBLAD
from tokens import LIJN


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
