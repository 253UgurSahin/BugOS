"""Het papiertje van een bestandssoort, met de letters voor het labeltje (voor places.py)."""

from __future__ import annotations

import re

from places_folders import BINNEN_LIJN
from places_mimetypes import FAMILIES
from places_svg import _GETAL, _g, _rrect, _svg, pad


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
