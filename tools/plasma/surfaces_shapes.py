"""Maten, kleuren, schaduwen en vormen voor surfaces.py: RR, Laag, pad() en het SVG-blad (Blad)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from tokens import KLEUREN, MATEN


LICHT = KLEUREN["licht"]

# Rondingen (docs/BRAND.md, "Shapes"): knoppen 12, kaarten 16, grote vlakken 22.
R_POPUP = MATEN["groot"]   # pop-ups van het systeemvak, dialogen
R_BALK = MATEN["kaart"]    # de zwevende taakbalk
R_KAART = MATEN["kaart"]   # widgets op het bureaublad, kaders
R_TIP = MATEN["knop"]      # tooltips, menu's van Plasma
R_REGEL = MATEN["knop"]    # lijstregels en taakknoppen

# Marges binnen de vlakken (stappen van 4).
M_POPUP = 12
M_BALK = 4         # gewone applets op de taakbalk (zoals Breeze, houdt pictogrammen 32 px)
M_BALK_DIK = 8     # rechts van de margescheiding: systeemvak en klok
M_TIP = 8
M_KAART = 12

# Inspringing (hint-*-inset) van een pop-up. Pop-ups die hun marges laten vallen
# (collapseMarginsHint: Netwerken, Geluid, Meldingen, Mediaspeler) zetten hun inhoud op
# -marge + inspringing. Bij 0 (zoals Breeze) loopt die inhoud tot de vensterrand en steken
# rechte hoeken (albumhoes, schuifbalk) buiten de ronding van 22 px. Met r * (1 - 1/wortel 2)
# blijft een rechte hoek binnen de ronding (afgerond 6; lijsten staan dan op 6 + 8 = 14 px).
# Alleen QML leest dit (Representation, Kickoff); de vensters zelf gebruiken de marges.
I_POPUP = math.floor(R_POPUP * (1 - math.sqrt(0.5)))

# Doorzichtigheid (zelfde getallen als tools/plasma/buttons.py en het snelmenu).
A_RAND = 0.10       # haarlijn rond een vlak: tekstkleur 10 %
# Aanwijzen = de knopkleur, net als in de BugOS-apps (zijbalk, rijen, balkknoppen: 'knop').
# Een tekst-tint werkt niet in beide thema's: 8 % is licht te zwaar (#E4E3E3, zwaarder
# dan zacht rood), en de knopkleur is licht #F1EEEE en donker #262930.
ZWEEF = "ButtonBackground"
A_ZWEEF = 1.0
A_ROOD = 0.13       # zacht rood: gekozen regel, actieve taak (op ViewBackground: #FDE9E9-achtig)
A_ROOD_ZWEEF = 0.16  # in een ListView is een gekozen regel altijd ook 'hover': niet veel feller
A_DOORZICHTIG = 0.95  # translucent/: KWin vervaagt erachter, net een tikje doorschijnend
A_STREEP = 0.45     # streepje onder een open (niet actieve) taak
A_STREEP_MIN = 0.22  # ... en onder een geminimaliseerde taak
NUL = 9.9999999e-09  # zo zegt Breeze "inspringing 0"

# Het accentrood. Niet ColorScheme-Highlight: in de BugOS-kleuren is 'Selection' het zachte
# rood (#FDE9E9, net als de zijbalk van de apps), en KDE's accentkleur kan hem weer fel
# maken. DecorationFocus (ButtonFocus) is in beide gevallen het lieveheersbeestjesrood.
ROOD = "ButtonFocus"
# Zacht rood = de kaartkleur met een beetje rood erover: licht ~#FBE9EB, donker ~#37212A.
KAART = "ViewBackground"

KAPPA = 0.5522847498  # kwartcirkel als Bezier-kromme


@dataclass(frozen=True)
class Schaduw:
    """Zachte schaduw: gaussisch vervaagde, iets omlaag geschoven kopie van de vorm."""
    sigma: float   # vervaging
    reik: float    # hoe ver de schaduw buiten de vorm reikt (zijkanten)
    dy: float      # verschuiving omlaag (boven korter, onder langer)
    alfa: float    # sterkte binnen de vorm

    def __call__(self, d: float) -> float:
        """Doorzichtigheid op afstand d buiten de (verschoven) vorm."""
        return self.alfa * 0.5 * math.erfc(d / (self.sigma * math.sqrt(2)))

    @property
    def marges(self) -> tuple[float, float, float, float]:
        """(boven, rechts, onder, links): hoe ver de schaduw buiten het venster valt."""
        return self.reik - self.dy, self.reik, self.reik + self.dy, self.reik


S_POPUP = Schaduw(sigma=8, reik=24, dy=4, alfa=0.18)
S_BALK = Schaduw(sigma=6, reik=16, dy=2, alfa=0.14)
S_TIP = Schaduw(sigma=5, reik=14, dy=3, alfa=0.16)
S_KAART = Schaduw(sigma=4, reik=8, dy=2, alfa=0.12)        # binnen het kader (bureaublad-widgets)
S_DOORZICHTIG = Schaduw(sigma=5, reik=12, dy=2, alfa=0.12)

STIJL = f"""    <style type="text/css" id="current-color-scheme">
        .ColorScheme-Text {{ color:{LICHT['tekst']}; }}
        .ColorScheme-Background {{ color:{LICHT['achter']}; }}
        .ColorScheme-ViewBackground {{ color:{LICHT['vlak']}; }}
        .ColorScheme-ButtonBackground {{ color:{LICHT['knop']}; }}
        .ColorScheme-Highlight {{ color:{LICHT['accent_zacht']}; }}
        .ColorScheme-ButtonFocus {{ color:{LICHT['accent']}; }}
        .ColorScheme-NeutralText {{ color:{LICHT['let_op']}; }}
    </style>"""

NEGEN = (("topleft", "top", "topright"), ("left", "center", "right"), ("bottomleft", "bottom", "bottomright"))


def f(v: float) -> str:
    if abs(abs(v) - NUL) < 1e-12:
        return "9.9999999e-09" if v > 0 else "-9.9999999e-09"
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------------ vormen ---

@dataclass(frozen=True)
class RR:
    """Afgeronde rechthoek (x0, y0) - (x1, y1) met straal r."""
    x0: float
    y0: float
    x1: float
    y1: float
    r: float

    def in_(self, d: float) -> "RR":
        return RR(self.x0 + d, self.y0 + d, self.x1 - d, self.y1 - d, max(self.r - d, 0))

    def schuif(self, dx: float, dy: float) -> "RR":
        return RR(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy, self.r)


@dataclass(frozen=True)
class Laag:
    vorm: RR
    klasse: str | None = "Background"   # ColorScheme-<klasse>; None = zwart (masker)
    alfa: float = 1.0
    ring: float = 0.0                   # > 0: alleen een rand van deze dikte, binnen de vorm


def knip(rr: RR, tegel: tuple[float, float, float, float]):
    """Het deel van rr binnen een tegel, als (x0, y0, x1, y1, (r_lb, r_rb, r_ro, r_lo)) of None.

    Voorwaarde: een hoekboog valt helemaal binnen of helemaal buiten een tegel (zo zijn de
    kaders opgebouwd); anders is het ontwerp fout en stoppen we.
    """
    tx0, ty0, tx1, ty1 = tegel
    x0, y0, x1, y1 = max(tx0, rr.x0), max(ty0, rr.y0), min(tx1, rr.x1), min(ty1, rr.y1)
    if x1 - x0 < 1e-6 or y1 - y0 < 1e-6:
        return None
    r = rr.r

    def hoek(bx0, by0, bx1, by1):
        ix0, iy0, ix1, iy1 = max(bx0, tx0), max(by0, ty0), min(bx1, tx1), min(by1, ty1)
        if ix1 - ix0 <= 1e-6 or iy1 - iy0 <= 1e-6:
            return 0.0
        if max(abs(ix0 - bx0), abs(iy0 - by0), abs(ix1 - bx1), abs(iy1 - by1)) < 1e-6:
            return r
        raise ValueError(f"tegel {tegel} snijdt door een hoekboog van {rr}")

    if r <= 0:
        stralen = (0.0, 0.0, 0.0, 0.0)
    else:
        stralen = (hoek(rr.x0, rr.y0, rr.x0 + r, rr.y0 + r), hoek(rr.x1 - r, rr.y0, rr.x1, rr.y0 + r),
                   hoek(rr.x1 - r, rr.y1 - r, rr.x1, rr.y1), hoek(rr.x0, rr.y1 - r, rr.x0 + r, rr.y1))
    return x0, y0, x1, y1, stralen


def pad(x0: float, y0: float, x1: float, y1: float, stralen=(0, 0, 0, 0), omgekeerd: bool = False) -> str:
    """Pad van een rechthoek met per hoek een eigen straal (linksboven, rechtsboven, rechtsonder, linksonder)."""
    a, b, c, d = stralen
    k = KAPPA
    stukken = [
        ("M", (x0 + a, y0)), ("L", (x1 - b, y0)),
        ("C", (x1 - b + k * b, y0, x1, y0 + b - k * b, x1, y0 + b)) if b else None,
        ("L", (x1, y1 - c)),
        ("C", (x1, y1 - c + k * c, x1 - c + k * c, y1, x1 - c, y1)) if c else None,
        ("L", (x0 + d, y1)),
        ("C", (x0 + d - k * d, y1, x0, y1 - d + k * d, x0, y1 - d)) if d else None,
        ("L", (x0, y0 + a)),
        ("C", (x0, y0 + a - k * a, x0 + a - k * a, y0, x0 + a, y0)) if a else None,
    ]
    stukken = [s for s in stukken if s]
    if omgekeerd:
        # zelfde vorm, andere draairichting (voor gaten, naast evenodd)
        uit = [f"M{f(x0 + a)},{f(y0)}"]
        # tegen de klok in: linksboven -> linksonder -> rechtsonder -> rechtsboven
        if a:
            uit.append(f"C{f(x0 + a - k * a)},{f(y0)} {f(x0)},{f(y0 + a - k * a)} {f(x0)},{f(y0 + a)}")
        uit.append(f"L{f(x0)},{f(y1 - d)}")
        if d:
            uit.append(f"C{f(x0)},{f(y1 - d + k * d)} {f(x0 + d - k * d)},{f(y1)} {f(x0 + d)},{f(y1)}")
        uit.append(f"L{f(x1 - c)},{f(y1)}")
        if c:
            uit.append(f"C{f(x1 - c + k * c)},{f(y1)} {f(x1)},{f(y1 - c + k * c)} {f(x1)},{f(y1 - c)}")
        uit.append(f"L{f(x1)},{f(y0 + b)}")
        if b:
            uit.append(f"C{f(x1)},{f(y0 + b - k * b)} {f(x1 - b + k * b)},{f(y0)} {f(x1 - b)},{f(y0)}")
        uit.append("Z")
        return "".join(uit)
    uit = []
    for soort, w in stukken:
        if soort in "ML":
            uit.append(f"{soort}{f(w[0])},{f(w[1])}")
        else:
            uit.append(f"C{f(w[0])},{f(w[1])} {f(w[2])},{f(w[3])} {f(w[4])},{f(w[5])}")
    uit.append("Z")
    return "".join(uit)


def verf(klasse: str | None, alfa: float = 1.0, evenodd: bool = False) -> str:
    regel = ' fill-rule="evenodd"' if evenodd else ""
    a = "" if alfa >= 1 else f' opacity="{f(alfa)}"'
    if klasse is None:
        return f'fill="#000000"{a}{regel}'
    return f'class="ColorScheme-{klasse}" fill="currentColor"{a}{regel}'


def laag_in_tegel(laag: Laag, tegel) -> str:
    buiten = knip(laag.vorm, tegel)
    if buiten is None:
        return ""
    if laag.ring <= 0:
        return f'<path d="{pad(*buiten[:4], buiten[4])}" {verf(laag.klasse, laag.alfa)}/>'
    binnen = knip(laag.vorm.in_(laag.ring), tegel)
    if binnen is not None and max(abs(p - q) for p, q in zip(buiten[:4], binnen[:4])) < 1e-6 \
            and buiten[4] == binnen[4]:
        return ""  # geen rand in deze tegel
    d = pad(*buiten[:4], buiten[4])
    if binnen is not None:
        d += pad(*binnen[:4], binnen[4], omgekeerd=True)
    return f'<path d="{d}" {verf(laag.klasse, laag.alfa, evenodd=True)}/>'


# -------------------------------------------------------------- het blad ---

class Blad:
    """Een SVG-bestand. Alle maten in pixels bij schaal 1; geen transformaties."""

    def __init__(self, titel: str) -> None:
        self.titel = titel
        self.defs: list[str] = []
        self.delen: list[str] = []
        self.ids: set[str] = set()
        self.w = 0.0
        self.h = 0.0

    def _id(self, eid: str) -> str:
        if eid in self.ids:
            raise ValueError(f"{self.titel}: id {eid} dubbel")
        self.ids.add(eid)
        return eid

    def bereik(self, x: float, y: float) -> None:
        self.w = max(self.w, x)
        self.h = max(self.h, y)

    def voeg(self, tekst: str) -> None:
        self.delen.append(tekst)

    def groep(self, eid: str, inhoud: list[str], kader: tuple[float, float, float, float]) -> None:
        """Een element: onzichtbare rechthoek (bepaalt de maat) plus de vormen."""
        x0, y0, x1, y1 = kader
        self.bereik(x1, y1)
        binnen = "".join(i for i in inhoud if i)
        self.voeg(f'  <g id="{self._id(eid)}"><rect x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" '
                  f'height="{f(y1 - y0)}" fill="none"/>{binnen}</g>')

    def hint(self, eid: str, x: float, y: float, w: float, h: float, kleur: str = "#ff00ff") -> None:
        self.bereik(x + w, y + h)
        self.voeg(f'  <rect id="{self._id(eid)}" x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" '
                  f'fill="{kleur}"/>')

    def lineair(self, gid: str, x1, y1, x2, y2, stops) -> str:
        self._id(gid)
        s = "".join(f'<stop offset="{f(o)}" stop-color="#000000" stop-opacity="{f(a)}"/>' for o, a in stops)
        self.defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{f(x1)}" y1="{f(y1)}" '
                         f'x2="{f(x2)}" y2="{f(y2)}">{s}</linearGradient>')
        return gid

    def radiaal(self, gid: str, cx, cy, r, stops) -> str:
        self._id(gid)
        s = "".join(f'<stop offset="{f(o)}" stop-color="#000000" stop-opacity="{f(a)}"/>' for o, a in stops)
        self.defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{f(cx)}" cy="{f(cy)}" '
                         f'fx="{f(cx)}" fy="{f(cy)}" r="{f(r)}">{s}</radialGradient>')
        return gid

    def tekst(self) -> str:
        w, h = math.ceil(self.w + 2), math.ceil(self.h + 2)
        defs = "\n".join("    " + d for d in self.defs)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!-- BugOS Plasma-stijl: {self.titel}. Gemaakt door tools/plasma/surfaces.py; '
            'niet met de hand bewerken. -->\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n'
            f'  <defs>\n{STIJL}\n{defs}\n  </defs>\n'
            + "\n".join(self.delen) + "\n</svg>\n"
        )
