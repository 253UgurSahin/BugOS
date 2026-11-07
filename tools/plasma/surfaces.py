#!/usr/bin/env python3
"""Maakt de vlakken van de Plasma-stijl "bugos": taakbalk, pop-ups, tooltips, kaarten en lijstregels.

Schrijft naar system_files/usr/share/plasma/desktoptheme/bugos/:

    dialogs/background, widgets/panel-background, widgets/tooltip, widgets/background,
    widgets/translucentbackground, widgets/plasmoidheading, widgets/tasks, widgets/viewitem,
    widgets/listitem, widgets/frame, widgets/margins-highlight
    en dezelfde set als Breeze in opaque/, solid/ en translucent/.

Vormtaal (docs/BRAND.md): rustige, dichte vlakken in de vensterkleur met een haarlijn
(tekstkleur, 10 %) en een zachte brede schaduw, zoals de kaarten in de BugOS-apps.
Pop-ups 22 px hoeken, taakbalk 16, kaarten 16, tooltips en menu's 12. Aanwijzen is een
zachte tint, gekozen is zacht rood (zoals het gekozen onderdeel in de zijbalk) en de
actieve taak krijgt een kort rood streepje onderaan. Kleuren lopen via de ColorScheme-
klassen van KSvg, zodat licht en donker vanzelf volgen; alleen de schaduw is zwart.

De element-id's zijn de API van KSvg en Plasma. Ze volgen de Breeze-bestanden: binnen een
bestand vult Plasma niets aan uit Breeze. Een paar id's zijn extra (taakknoppen bij
aanwijzen, marges per richting); Plasma 6 zoekt die eerst en valt anders terug.

Gebruik:
    python3 tools/plasma/surfaces.py [uitmap]          # schrijf alle bestanden
    python3 tools/plasma/surfaces.py --controleer MAP  # vergelijk de id's met Breeze (uitgepakte .svg's)
"""

from __future__ import annotations

import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "design"))
from tokens import KLEUREN, MATEN, SYSTEM  # noqa: E402

UIT = SYSTEM / "usr" / "share" / "plasma" / "desktoptheme" / "bugos"
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


# ------------------------------------------------- negen stukjes van een kader ---
#
# Een kader (KSvg FrameSvg) bestaat uit vier hoeken, vier randen en een midden.
# KSvg tekent de hoeken op ware grootte, de randen worden gerekt of herhaald.
# De dikte van de randen komt uit de elementen top/bottom/left/right; de hoeken
# moeten daar precies op passen. De vormen worden per tegel uitgerekend (geen clipPath).

def kader(blad: Blad, voor: str, ox: float, oy: float, L: float, T: float, R: float, B: float,
          lagen, *, cw: float = 32, ch: float = 32, extra: dict | None = None) -> tuple[float, float]:
    """Schrijf voor-topleft ... voor-bottomright. lagen(W, H) geeft de vormen in kaderruimte.

    Geeft de maat (W, H) van het kader terug.
    """
    W, H = L + cw + R, T + ch + B
    vormen = [Laag(l.vorm.schuif(ox, oy), l.klasse, l.alfa, l.ring) for l in lagen(W, H)]
    kol = [(0, L), (L, L + cw), (L + cw, W)]
    rij = [(0, T), (T, T + ch), (T + ch, H)]
    for j, (y0, y1) in enumerate(rij):
        for i, (x0, x1) in enumerate(kol):
            naam = NEGEN[j][i]
            tegel = (ox + x0, oy + y0, ox + x1, oy + y1)
            inhoud = list(extra[naam](tegel)) if extra and naam in extra else []  # schaduw eerst (eronder)
            inhoud += [laag_in_tegel(l, tegel) for l in vormen]
            blad.groep(voor + naam, inhoud, tegel)
    return W, H


def marges(blad: Blad, voor: str, ox: float, oy: float, W: float, H: float,
           boven: float, rechts: float, onder: float, links: float, soort: str = "margin",
           kleur: str = "#ff00ff") -> None:
    """hint-<zijde>-margin (of -inset): de maat zegt hoeveel ruimte er aan die kant is."""
    mx, my = ox + W / 2 - 1, oy + H / 2 - 1
    blad.hint(f"{voor}hint-top-{soort}", mx, oy, 2, boven, kleur)
    blad.hint(f"{voor}hint-bottom-{soort}", mx, oy + H - onder, 2, onder, kleur)
    blad.hint(f"{voor}hint-left-{soort}", ox, my, links, 2, kleur)
    blad.hint(f"{voor}hint-right-{soort}", ox + W - rechts, my, rechts, 2, kleur)


def vlak(r: float, alfa: float = 1.0, rand: bool = True, klasse: str = "Background", gat: float = 0.0):
    """Lagen voor een dicht vlak met haarlijn, ingesprongen met 'gat'."""
    def lagen(W, H):
        vorm = RR(gat, gat, W - gat, H - gat, r)
        uit = [Laag(vorm, klasse, alfa)]
        if rand:
            uit.append(Laag(vorm, "Text", A_RAND, ring=1))
        return uit
    return lagen


# -------------------------------------------------------------- schaduwen ---

def schaduw_inhoud(blad: Blad, venster: RR, tegels: dict, sch: Schaduw, gid_voor: str,
                   namen: dict | None = None, pad_ids: dict | None = None) -> dict:
    """Per tegelnaam de schaduwvormen (buiten het venster), met verlopen in absolute maten.

    venster: de vorm die de schaduw werpt; tegels: naam -> (x0, y0, x1, y1).
    namen: andere id's voor sommige verlopen (Breeze: shadow-side, shadow-corner).
    pad_ids: id's voor de zichtbare paden in de zijtegels (Breeze: st, sb, sl, sr).
    """
    namen = namen or {}
    pad_ids = pad_ids or {}
    uit = {}
    vorm = venster.schuif(0, sch.dy)
    r = venster.r
    middens = {"topleft": (vorm.x0 + r, vorm.y0 + r), "topright": (vorm.x1 - r, vorm.y0 + r),
               "bottomleft": (vorm.x0 + r, vorm.y1 - r), "bottomright": (vorm.x1 - r, vorm.y1 - r)}
    n = 18
    for naam, tegel in tegels.items():
        if naam == "center":
            uit[naam] = []
            continue
        gat = knip(venster, tegel)
        d = pad(*tegel)
        if gat is not None:
            d += pad(*gat[:4], gat[4], omgekeerd=True)
        gid = namen.get(naam, f"{gid_voor}{naam}-verloop")
        x0, y0, x1, y1 = tegel
        if naam in middens:
            cx, cy = middens[naam]
            rho = max(math.hypot(px - cx, py - cy) for px in (x0, x1) for py in (y0, y1)) + 1
            stops = [(i / n, sch(i / n * rho - r)) for i in range(n + 1)]
            blad.radiaal(gid, cx, cy, rho, stops)
        else:
            if naam == "top":
                lengte = venster.y0 - y0
                stops = [(i / n, sch(sch.dy + i / n * lengte)) for i in range(n + 1)]
                blad.lineair(gid, x0, venster.y0, x0, y0, stops)
            elif naam == "bottom":
                lengte = y1 - venster.y1
                stops = [(i / n, sch(-sch.dy + i / n * lengte)) for i in range(n + 1)]
                blad.lineair(gid, x0, venster.y1, x0, y1, stops)
            elif naam == "left":
                lengte = venster.x0 - x0
                stops = [(i / n, sch(i / n * lengte)) for i in range(n + 1)]
                blad.lineair(gid, venster.x0, y0, x0, y0, stops)
            else:  # right
                lengte = x1 - venster.x1
                stops = [(i / n, sch(i / n * lengte)) for i in range(n + 1)]
                blad.lineair(gid, venster.x1, y0, x1, y0, stops)
        pid = f' id="{blad._id(pad_ids[naam])}"' if naam in pad_ids else ""
        uit[naam] = [f'<path{pid} d="{d}" fill="url(#{gid})" fill-rule="evenodd"/>']
    return uit


def schaduw_kader(blad: Blad, ox: float, oy: float, r: float, sch: Schaduw, *, cw: float = 32, ch: float = 32,
                  breeze_namen: bool = True, inset_hints: bool = True) -> tuple[float, float]:
    """KWin-schaduw: shadow-topleft ... shadow-center en shadow-hint-*.

    Net als Breeze: de hoektegels lopen 'r' onder het venster door (daar is de schaduw
    weggelaten), zodat de ronde hoek van het venster ook schaduw krijgt. Dezelfde tegels
    werken als FrameSvg met voorvoegsel "shadow" (menu's van Plasma).
    """
    pt, pr, pb, pl = sch.marges
    vx, vy = ox + pl, oy + pt                      # linksboven van het venster
    venster = RR(vx, vy, vx + 2 * r + cw, vy + 2 * r + ch, r)
    kol = [(vx - pl, vx + r), (vx + r, vx + r + cw), (vx + r + cw, venster.x1 + pr)]
    rij = [(vy - pt, vy + r), (vy + r, vy + r + ch), (vy + r + ch, venster.y1 + pb)]
    tegels = {NEGEN[j][i]: (kol[i][0], rij[j][0], kol[i][1], rij[j][1]) for j in range(3) for i in range(3)}
    namen = {"top": "shadow-side", "topleft": "shadow-corner"} if breeze_namen else {}
    pad_ids = {"top": "st", "bottom": "sb", "left": "sl", "right": "sr"} if breeze_namen else {}
    inhoud = schaduw_inhoud(blad, venster, tegels, sch, "shadow-", namen, pad_ids)
    for naam, tegel in tegels.items():
        blad.groep("shadow-" + naam, inhoud[naam], tegel)
    W, H = venster.x1 + pr - ox, venster.y1 + pb - oy
    # shadow-hint-*-margin: hoeveel schaduw er buiten het venster valt (de 'padding' voor KWin)
    blad.hint("shadow-hint-top-margin", vx + r + 2, oy, 2, pt)
    blad.hint("shadow-hint-bottom-margin", vx + r + 2, venster.y1, 2, pb)
    blad.hint("shadow-hint-left-margin", ox, vy + r + 2, pl, 2)
    blad.hint("shadow-hint-right-margin", venster.x1, vy + r + 2, pr, 2)
    if inset_hints:
        # Breeze geeft hier dezelfde maten als de marges
        blad.hint("shadow-hint-top-inset", vx + r + 6, oy, 2, pt, "#00ff00")
        blad.hint("shadow-hint-bottom-inset", vx + r + 6, venster.y1, 2, pb, "#00ff00")
        blad.hint("shadow-hint-left-inset", ox, vy + r + 6, pl, 2, "#00ff00")
        blad.hint("shadow-hint-right-inset", venster.x1, vy + r + 6, pr, 2, "#00ff00")
    return W, H


# ----------------------------------------------------------------- maskers ---

def masker_kader(blad: Blad, voor: str, ox: float, oy: float, r: float, cw: float = 32, ch: float = 32) -> None:
    """mask-*: de vorm voor de vervaging achter het venster (en de vensterrand zonder compositing).

    Net als Breeze 1 px kleiner in de hoeken: het masker is niet afgevlakt, de rand wel.
    """
    W, H = 2 * r + cw, 2 * r + ch
    k = KAPPA
    q = r - 1  # straal van de boog in het masker
    kol = [(0, r), (r, r + cw), (r + cw, W)]
    rij = [(0, r), (r, r + ch), (r + ch, H)]
    for j, (y0, y1) in enumerate(rij):
        for i, (x0, x1) in enumerate(kol):
            naam = NEGEN[j][i]
            tegel = (ox + x0, oy + y0, ox + x1, oy + y1)
            if naam in ("topleft", "topright", "bottomleft", "bottomright"):
                sx = -1 if "right" in naam else 1
                sy = -1 if "bottom" in naam else 1
                hx = ox + (x0 if sx > 0 else x1)   # buitenhoek van de tegel
                hy = oy + (y0 if sy > 0 else y1)

                def p(dx, dy):
                    return f"{f(hx + sx * dx)},{f(hy + sy * dy)}"
                # van de rand-naad, langs een boog met straal r-1 (middelpunt (r, r)), terug
                d = (f"M{p(0, r)}L{p(1, r)}C{p(1, r - k * q)} {p(r - k * q, 1)} {p(r, 1)}"
                     f"L{p(r, 0)}L{p(r, r)}Z")
                inhoud = [f'<path d="{d}"/>']
            else:
                inhoud = [f'<path d="{pad(*tegel)}"/>']
            blad.groep(f"mask-{voor}{naam}", inhoud, tegel)


# --------------------------------------------------------- vensterachtergronden ---

@dataclass(frozen=True)
class Venster:
    """Een vensterachtergrond: pop-up, taakbalk of tooltip."""
    r: float
    marge: tuple[float, float, float, float]   # boven, rechts, onder, links
    schaduw: Schaduw
    inzet: float = NUL                         # hint-*-inset (zie I_POPUP)


POPUP = Venster(R_POPUP, (M_POPUP,) * 4, S_POPUP, inzet=I_POPUP)
BALK = Venster(R_BALK, (M_BALK,) * 4, S_BALK)
TIP = Venster(R_TIP, (M_TIP,) * 4, S_TIP)
KAART_VENSTER = Venster(R_KAART, (M_KAART,) * 4, S_POPUP)


def vensterachtergrond(titel: str, v: Venster, *, alfa: float, schaduw: bool = True, dik: bool = False,
                       inset: bool = True, basis: bool = False, prive_schaduw: bool = False) -> Blad:
    """dialogs/background, widgets/panel-background en widgets/tooltip (en hun varianten)."""
    blad = Blad(titel)
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    if prive_schaduw:
        blad.hint("private-hint-use-shadow", 6, 0, 5, 5, "#ff6600")
    oy = 10
    if basis:
        blad.voeg('  <g id="base">')
        blad.ids.add("base")
    W, H = kader(blad, "", 2, oy, v.r, v.r, v.r, v.r, vlak(v.r, alfa))
    if basis:
        blad.voeg("  </g>")
    b, rr, o, l = v.marge
    marges(blad, "", 2, oy, W, H, b, rr, o, l)
    if inset:
        # de schaduw valt buiten het venster (KWin tekent hem); de inspringing zegt alleen
        # hoe ver ingeklapte inhoud van de rand blijft (pop-ups: I_POPUP, de rest 0)
        i = v.inzet
        marges(blad, "", 2, oy, W, H, i, i, i, i, soort="inset", kleur="#00ff00")
    if dik:
        # "thick": de marges rechts van de margescheiding (systeemvak, klok)
        blad.groep("thick-center", [], (2 + v.r, oy + H + 10, 2 + v.r + 32, oy + H + 42))
        tx, ty = 2, oy + H + 6
        blad.hint("thick-hint-top-margin", tx + W / 2 + 4, ty, 2, M_BALK_DIK, "#800080")
        blad.hint("thick-hint-bottom-margin", tx + W / 2 + 4, ty + 40, 2, M_BALK_DIK, "#800080")
        blad.hint("thick-hint-left-margin", tx, ty + 20, M_BALK_DIK, 2, "#800080")
        blad.hint("thick-hint-right-margin", tx + W - M_BALK_DIK, ty + 20, M_BALK_DIK, 2, "#800080")
    mx = 2 + W + 12
    masker_kader(blad, "", mx, oy, v.r)
    if schaduw:
        schaduw_kader(blad, mx + W + 12, 0, v.r, v.schaduw)
    return blad


# ----------------------------------------------------- widgets op het bureaublad ---

def kaart_lagen(ins: float, r: float, alfa: float, rand: bool = True):
    """Een kaart, ingesprongen voor de schaduw binnen het kader (zie kaart_schaduw)."""
    def lagen(W, H):
        vorm = RR(ins, ins, W - ins, H - ins, r)
        uit = [Laag(vorm, "Background", alfa)]
        if rand:
            uit.append(Laag(vorm, "Text", A_RAND, ring=1))
        return uit
    return lagen


def kaart_schaduw(blad: Blad, voor: str, ox: float, oy: float, ins: float, r: float, sch: Schaduw,
                  cw: float = 32, ch: float = 32) -> dict:
    """extra-functies voor kader(): de schaduw in de randtegels, onder de kaart."""
    L = ins + r
    W, H = 2 * L + cw, 2 * L + ch
    venster = RR(ox + ins, oy + ins, ox + W - ins, oy + H - ins, r)
    kol = [(0, L), (L, L + cw), (L + cw, W)]
    rij = [(0, L), (L, L + ch), (L + ch, H)]
    tegels = {NEGEN[j][i]: (ox + kol[i][0], oy + rij[j][0], ox + kol[i][1], oy + rij[j][1])
              for j in range(3) for i in range(3)}
    inhoud = schaduw_inhoud(blad, venster, tegels, sch, voor)
    return {naam: (lambda _t, s=inhoud[naam]: s) for naam in inhoud}


def widgets_background(titel: str, *, vervaagd: bool) -> Blad:
    """widgets/background: kaart op het bureaublad (en Popup/Dialog/Drawer van PlasmaComponents)."""
    blad = Blad(titel)
    ins, r = 8, R_KAART
    L = ins + r
    m = ins + M_KAART
    blad.hint("hint-stretch-borders", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    oy = 8
    extra = kaart_schaduw(blad, "", 2, oy, ins, r, S_KAART)
    W, H = kader(blad, "", 2, oy, L, L, L, L, kaart_lagen(ins, r, 1.0), extra=extra)
    blad.voeg("  </g>")
    # oud element van Breeze: alleen het midden
    blad.groep("toolbutton-pressed-center", [f'<path d="{pad(2 + L, oy + H + 8, 2 + L + 32, oy + H + 40)}" '
                                             f'{verf("Background")}/>'], (2 + L, oy + H + 8, 2 + L + 32, oy + H + 40))
    marges(blad, "", 2, oy, W, H, m, m, m, m)
    marges(blad, "", 2, oy, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
    # shadow-*: alleen de schaduw, als kader
    sx = 2 + W + 12
    extra = kaart_schaduw(blad, "shadow-", sx, oy, ins, r, S_KAART)
    kader(blad, "shadow-", sx, oy, L, L, L, L, lambda W_, H_: [], extra=extra)
    marges(blad, "shadow-", sx, oy, W, H, m, m, m, m)
    marges(blad, "shadow-", sx, oy, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
    if vervaagd:
        # blurred-*: Plasma vervaagt de achtergrond zelf (blurred-mask) en legt dit erover
        by = oy + H + 50
        extra = kaart_schaduw(blad, "blurred-", 2, by, ins, r, S_KAART)
        kader(blad, "blurred-", 2, by, L, L, L, L, kaart_lagen(ins, r, A_DOORZICHTIG - 0.03),
              extra=extra)
        marges(blad, "blurred-", 2, by, W, H, m, m, m, m)
        marges(blad, "blurred-", 2, by, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
        kader(blad, "blurred-mask-", sx, by, L, L, L, L,
              lambda W_, H_: [Laag(RR(ins, ins, W_ - ins, H_ - ins, r), None)])
    return blad


def translucentbackground() -> Blad:
    """widgets/translucentbackground: een doorschijnende kaart (applets die daarom vragen)."""
    blad = Blad("doorschijnende kaart")
    r = R_KAART
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    oy = 10
    W, H = kader(blad, "", 2, oy, r, r, r, r, vlak(r, 0.80))
    blad.voeg("  </g>")
    marges(blad, "", 2, oy, W, H, M_KAART, M_KAART, M_KAART, M_KAART)
    marges(blad, "", 2, oy, W, H, NUL, NUL, NUL, NUL, soort="inset", kleur="#00ff00")
    schaduw_kader(blad, 2 + W + 12, 0, r, S_DOORZICHTIG, breeze_namen=False)
    return blad


# ------------------------------------------------------------ kop van een pop-up ---

def plasmoidheading() -> Blad:
    """widgets/plasmoidheading: geen aparte balk, alleen een haarlijn tussen kop en inhoud."""
    blad = Blad("kop en voet van een pop-up")
    blad.hint("hint-stretch-borders", 0, 0, 5, 5, "#ff6600")
    zij, dik = 12, 12

    def kop(W, H):  # lijn onderaan, alleen tussen de hoeken: springt 12 px in, net als de inhoud
        return [Laag(RR(zij, H - 1, W - zij, H, 0), "Text", A_RAND)]

    def voet(W, H):
        return [Laag(RR(zij, 0, W - zij, 1, 0), "Text", A_RAND)]

    W, H = kader(blad, "header-", 2, 8, zij, dik, zij, 1, kop)
    kader(blad, "footer-", 2 + W + 12, 8, zij, 1, zij, dik, voet)
    # Breeze heeft ook kale hint-*-margin (voor het voorvoegsel ""): zelfde maat als de kop
    marges(blad, "", 2, 8, W, H, 8, 8, 8, 8)
    return blad


# ------------------------------------------------------------- lijstregels ---

def regel(klasse: str | None, alfa: float, r: float = R_REGEL):
    """Een regel: niets, een zachte tint (tekstkleur) of zacht rood (kaartkleur + rood)."""
    if klasse is None:
        return lambda W, H: []
    if klasse == ROOD:
        return lambda W, H: [Laag(RR(0, 0, W, H, r), KAART), Laag(RR(0, 0, W, H, r), ROOD, alfa)]
    return lambda W, H: [Laag(RR(0, 0, W, H, r), klasse, alfa)]


def viewitem() -> Blad:
    """widgets/viewitem: markering in lijsten (PlasmaExtras.Highlight) en menu-items."""
    blad = Blad("markering in lijsten en menu's")
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    r = R_REGEL
    standen = [("normal", None, 0), ("hover", ZWEEF, A_ZWEEF), ("selected", ROOD, A_ROOD),
               ("selected+hover", ROOD, A_ROOD_ZWEEF)]
    plekken = []
    x = 2
    for naam, klasse, alfa in standen:
        W, H = kader(blad, naam + "-", x, 8, r, r, r, r, regel(klasse, alfa), cw=24, ch=24)
        plekken.append((naam, x, W, H))
        x += W + 10
    blad.voeg("  </g>")
    # extra (Breeze heeft ze niet): de binnenruimte van een menu-item (PC3 MenuItem gebruikt die)
    for naam, x, W, H in plekken:
        marges(blad, naam + "-", x, 8, W, H, 8, 8, 8, 8)
    return blad


def listitem() -> Blad:
    """widgets/listitem: achtergrond van lijstregels (ItemDelegate, PlasmaExtras.ListItem)."""
    blad = Blad("lijstregels")
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    r = R_REGEL
    standen = [("normal", None, 0, True), ("pressed", ROOD, A_ROOD, True),
               ("hover", ZWEEF, A_ZWEEF, False), ("section", None, 0, True)]
    plekken = []
    x = 2
    for naam, klasse, alfa, met_marges in standen:
        W, H = kader(blad, naam + "-", x, 8, r, r, r, r, regel(klasse, alfa), cw=24, ch=24)
        plekken.append((naam, x, W, H, met_marges))
        x += W + 10
    blad.voeg("  </g>")
    for naam, x, W, H, met_marges in plekken:
        if met_marges:
            marges(blad, naam + "-", x, 8, W, H, 8, 8, 8, 8)
    # scheidingslijn tussen regels: haarlijn
    blad.groep("separator", [f'<path d="{pad(2, 70, 42, 71)}" {verf("Text", A_RAND)}/>'], (2, 70, 42, 71))
    return blad


def frame() -> Blad:
    """widgets/frame: kaders (PlasmaComponents Frame en GroupBox gebruiken 'plain')."""
    blad = Blad("kaders")
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    r = R_KAART

    def plain(W, H):
        return [Laag(RR(0, 0, W, H, r), "Text", A_RAND, ring=1)]

    def raised(W, H):  # een BugOS-kaart: kaartkleur met haarlijn
        vorm = RR(0, 0, W, H, r)
        return [Laag(vorm, KAART, 1.0), Laag(vorm, "Text", A_RAND + 0.02, ring=1)]

    def sunken(W, H):
        vorm = RR(0, 0, W, H, r)
        return [Laag(vorm, "Text", 0.05), Laag(vorm, "Text", A_RAND, ring=1)]

    plekken = []
    x = 2
    for naam, lagen in (("plain", plain), ("raised", raised), ("sunken", sunken)):
        W, H = kader(blad, naam + "-", x, 8, r, r, r, r, lagen)
        plekken.append((naam, x, W, H))
        x += W + 10
    blad.voeg("  </g>")
    for naam, x, W, H in plekken:
        marges(blad, naam + "-", x, 8, W, H, 8, 8, 8, 8)
    # oud, onbenut element van Breeze; blijft bestaan zodat niets ontbreekt
    blad.groep("border-bottomleft", [], (2, 90, 10, 98))
    return blad


def margins_highlight() -> Blad:
    """widgets/margins-highlight: de marges van de taakbalk in de bewerkstand (zacht rood)."""
    blad = Blad("marges van de taakbalk in de bewerkstand")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    a = 0.25
    blad.groep("fill", [f'<path d="M2,2h4v4h-4z" {verf(ROOD, a)}/>'], (2, 2, 6, 6))
    driehoeken = {  # rechte hoek op de genoemde plek
        "topleft": "M10,2h4l-4,4z", "topright": "M18,2h4v4z",
        "bottomleft": "M26,2v4h4z", "bottomright": "M38,2v4h-4z",
    }
    kaders = {"topleft": (10, 2, 14, 6), "topright": (18, 2, 22, 6), "bottomleft": (26, 2, 30, 6),
              "bottomright": (34, 2, 38, 6)}
    for naam, d in driehoeken.items():
        blad.groep(naam, [f'<path d="{d}" {verf(ROOD, a)}/>'], kaders[naam])
    blad.voeg("  </g>")
    return blad


# ------------------------------------------------------------- taakknoppen ---
#
# De taakbeheerder (Plasma 6) zoekt per stand een lijst voorvoegsels, bijvoorbeeld
# voor een actieve taak onder de muis op een taakbalk onderaan:
#   south-focus-hover, focus-hover, south-hover, hover, south-focus, focus
# en voor een vastgezette app onder de muis: south-launcher-hover, launcher-hover, ...
# Zonder voorvoegsel = taakbalk onderaan. north-/west-/east- = boven, links, rechts.
#
# Vorm: een zachte tegel (12 px hoeken, 2 px van de rand) en een kort streepje aan de
# kant van de schermrand: rood bij de actieve taak, grijs bij een open taak.

GAT = 2      # ruimte tussen tegel en rand van de taakknop
STREEP = 2   # dikte van het streepje
HOEK_LANG = GAT + R_REGEL   # randdikte bij een lang streepje (actief, aandacht)
HOEK_KORT = 20              # randdikte bij een kort streepje (open, geminimaliseerd)

TAAKSTANDEN = {
    # naam: (tint, tint-alfa, streep-kleur, streep-alfa, streep-lengte)
    "normal": (None, 0, "Text", A_STREEP, "kort"),
    "hover": (ZWEEF, A_ZWEEF, None, 0, None),
    "focus": (ROOD, A_ROOD, ROOD, 1.0, "lang"),
    "attention": ("NeutralText", A_ROOD, "NeutralText", 1.0, "lang"),
    "minimized": (None, 0, "Text", A_STREEP_MIN, "kort"),
    "progress": ("voortgang", 0.16, None, 0, None),
    # extra standen (niet in Breeze): aanwijzen houdt het streepje
    "normal-hover": (ZWEEF, A_ZWEEF, "Text", A_STREEP, "kort"),
    "focus-hover": (ROOD, A_ROOD_ZWEEF, ROOD, 1.0, "lang"),
    "attention-hover": ("NeutralText", A_ROOD_ZWEEF, "NeutralText", 1.0, "lang"),
    "minimized-hover": (ZWEEF, A_ZWEEF, "Text", A_STREEP_MIN, "kort"),
    "launcher-hover": (ZWEEF, A_ZWEEF, None, 0, None),
}


def taak_lagen(stand: tuple, richting: str):
    tint, tint_a, streep, streep_a, lengte = stand

    def lagen(W, H):
        uit = []
        tegel = RR(GAT, GAT, W - GAT, H - GAT, R_REGEL)
        if tint == "voortgang":
            # voortgang ligt over de knop heen (alleen tot waar het werk is): alleen wat rood
            uit.append(Laag(tegel, ROOD, tint_a))
        elif tint in (ROOD, "NeutralText"):
            # gekozen/aandacht: een lichte tegel (kaartkleur) met een zweem kleur
            uit += [Laag(tegel, KAART), Laag(tegel, tint, tint_a)]
        elif tint:
            uit.append(Laag(tegel, tint, tint_a))
        if streep:
            rand = HOEK_LANG if lengte == "lang" else HOEK_KORT
            kap = STREEP / 2
            if richting in ("", "north-"):
                x0, x1 = rand - kap, W - rand + kap
                y0 = H - GAT - STREEP if richting == "" else GAT
                uit.append(Laag(RR(x0, y0, x1, y0 + STREEP, kap), streep, streep_a))
            else:
                y0, y1 = rand - kap, H - rand + kap
                x0 = GAT if richting == "west-" else W - GAT - STREEP
                uit.append(Laag(RR(x0, y0, x0 + STREEP, y1, kap), streep, streep_a))
        return uit
    return lagen


def tasks() -> Blad:
    blad = Blad("taakknoppen")
    y = 2
    for richting in ("", "north-", "west-", "east-"):
        x = 2
        liggend = richting in ("", "north-")
        for naam, stand in TAAKSTANDEN.items():
            lengte = stand[4]
            rand = HOEK_KORT if lengte == "kort" else HOEK_LANG
            if liggend:
                L = R = rand
                T = B = HOEK_LANG
                cw, ch = 16, 12
            else:
                L = R = HOEK_LANG
                T = B = rand
                cw, ch = 12, 16
            W, H = kader(blad, f"{richting}{naam}-", x, y, L, T, R, B, taak_lagen(stand, richting), cw=cw, ch=ch)
            if naam == "normal":
                # de binnenruimte van een taakknop: waar het pictogram staat (zoals Breeze: 4 px)
                marges(blad, f"{richting}normal-", x, y, W, H, 4, 4, 4, 4)
            x += W + 6
        y += 70
    # Groepje vensters: een klein rond plusje. Plasma zet het tegen de schermrand van de
    # knop; 4 px lucht aan die kant houdt het streepje vrij.
    x = 2
    lucht = GAT + STREEP
    for naam, (dx, dy, w, h) in {"group-expander-bottom": (0, 0, 11, 11 + lucht),
                                 "group-expander-top": (0, lucht, 11, 11 + lucht),
                                 "group-expander-left": (lucht, 0, 11 + lucht, 11),
                                 "group-expander-right": (0, 0, 11 + lucht, 11)}.items():
        cx, cy, r = x + dx + 5.5, y + dy + 5.5, 5.5
        k = KAPPA * r
        cirkel = (f"M{f(cx)},{f(cy - r)}C{f(cx + k)},{f(cy - r)} {f(cx + r)},{f(cy - k)} {f(cx + r)},{f(cy)}"
                  f"C{f(cx + r)},{f(cy + k)} {f(cx + k)},{f(cy + r)} {f(cx)},{f(cy + r)}"
                  f"C{f(cx - k)},{f(cy + r)} {f(cx - r)},{f(cy + k)} {f(cx - r)},{f(cy)}"
                  f"C{f(cx - r)},{f(cy - k)} {f(cx - k)},{f(cy - r)} {f(cx)},{f(cy - r)}Z")
        ring = RR(cx - r, cy - r, cx + r, cy + r, r)
        plus = (f'<path d="M{f(cx - 2.5)},{f(cy)}H{f(cx + 2.5)}M{f(cx)},{f(cy - 2.5)}V{f(cy + 2.5)}" '
                'class="ColorScheme-Text" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
                'fill="none"/>')
        inhoud = [f'<path d="{cirkel}" {verf("Background")}/>',
                  laag_in_tegel(Laag(ring, "Text", 0.25, ring=1), (cx - r, cy - r, cx + r, cy + r)),
                  plus]
        blad.groep(naam, inhoud, (x, y, x + w, y + h))
        x += 20
    return blad


# ------------------------------------------------------------------ alles ---

def bestanden() -> dict[str, Blad]:
    """Alle bestanden: pad (zonder .svg) -> blad."""
    uit: dict[str, Blad] = {}
    # pop-ups en dialogen
    uit["dialogs/background"] = vensterachtergrond("pop-up", POPUP, alfa=1.0)
    uit["translucent/dialogs/background"] = vensterachtergrond("pop-up (met vervaging)", POPUP, alfa=A_DOORZICHTIG)
    uit["solid/dialogs/background"] = vensterachtergrond("pop-up (dicht)", POPUP, alfa=1.0)
    uit["opaque/dialogs/background"] = vensterachtergrond("pop-up (zonder compositing)", POPUP, alfa=1.0,
                                                          schaduw=False, inset=False, basis=True)
    # taakbalk
    uit["widgets/panel-background"] = vensterachtergrond("taakbalk", BALK, alfa=1.0, dik=True)
    uit["translucent/widgets/panel-background"] = vensterachtergrond("taakbalk (met vervaging)", BALK,
                                                                     alfa=A_DOORZICHTIG, dik=True)
    uit["solid/widgets/panel-background"] = vensterachtergrond("taakbalk (dicht)", BALK, alfa=1.0, dik=True)
    uit["opaque/widgets/panel-background"] = vensterachtergrond("taakbalk (zonder compositing)", BALK, alfa=1.0,
                                                                dik=True, schaduw=False, inset=False, basis=True)
    # tooltips (solid/ is ook het menu van Plasma)
    uit["widgets/tooltip"] = vensterachtergrond("tooltip", TIP, alfa=1.0)
    uit["translucent/widgets/tooltip"] = vensterachtergrond("tooltip (met vervaging)", TIP, alfa=A_DOORZICHTIG)
    uit["solid/widgets/tooltip"] = vensterachtergrond("tooltip en menu (dicht)", TIP, alfa=1.0)
    uit["opaque/widgets/tooltip"] = vensterachtergrond("tooltip (zonder compositing)", TIP, alfa=1.0,
                                                       schaduw=False, inset=False, basis=True)
    # kaarten
    uit["widgets/background"] = widgets_background("kaart op het bureaublad", vervaagd=False)
    uit["translucent/widgets/background"] = widgets_background("kaart op het bureaublad (met vervaging)",
                                                               vervaagd=True)
    uit["solid/widgets/background"] = vensterachtergrond("kaart (dicht)", KAART_VENSTER, alfa=1.0,
                                                         prive_schaduw=True)
    uit["widgets/translucentbackground"] = translucentbackground()
    # binnen de pop-ups en op de taakbalk
    uit["widgets/plasmoidheading"] = plasmoidheading()
    uit["widgets/viewitem"] = viewitem()
    uit["widgets/listitem"] = listitem()
    uit["widgets/frame"] = frame()
    uit["widgets/margins-highlight"] = margins_highlight()
    uit["widgets/tasks"] = tasks()
    return uit


def schrijf(doel: Path = UIT) -> list[Path]:
    geschreven = []
    for rel, blad in bestanden().items():
        p = doel / f"{rel}.svg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(blad.tekst(), encoding="utf-8", newline="\n")
        geschreven.append(p)
    return geschreven


# ------------------------------------------------------------- controle ---

INKSCAPE = re.compile(r"^(rect|path|g|stop|linearGradient|radialGradient|svg|defs|namedview|grid|text|tspan|use|"
                      r"circle|ellipse|filter|feGaussianBlur|metadata|layer|clipPath|mask|image|perspective|title|"
                      r"guide|pattern)[-_]?\d+([-_.]\d+)*$")


def ids_van(pad_: Path) -> set[str]:
    return {el.get("id") for el in ET.parse(pad_).iter() if el.get("id")}


def api_ids(alle: set[str]) -> set[str]:
    """De id's die ertoe doen: zonder Inkscape-namen en zonder Inkscape-dubbelingen (naam-9)."""
    uit = set()
    for i in alle:
        if INKSCAPE.match(i):
            continue
        m = re.match(r"^(.+)-\d+$", i)
        if m and m.group(1) in alle:
            continue
        uit.add(i)
    return uit


def kaders_kloppen(pad_: Path) -> list[str]:
    """Elk kader heeft 9 stukken en de hoeken passen op de randen (zo leest KSvg de maten)."""
    maten = {}
    for el in ET.parse(pad_).iter():
        eid = el.get("id")
        kind = list(el)
        if eid and el.tag.endswith("}g") and kind and kind[0].tag.endswith("}rect") and kind[0].get("fill") == "none":
            r = kind[0]
            maten[eid] = (float(r.get("width")), float(r.get("height")))
    namen = [n for rij in NEGEN for n in rij]
    fouten = []
    for eid in maten:
        if not eid.endswith("center") or eid in ("thick-center", "toolbutton-pressed-center", "shadow-center"):
            continue
        v = eid[:-len("center")]
        if any(v + n not in maten for n in namen):
            fouten.append(f"{v}*: niet alle negen stukken")
            continue
        m = {n: maten[v + n] for n in namen}
        L, R, T, B = m["left"][0], m["right"][0], m["top"][1], m["bottom"][1]
        goed = (m["topleft"] == (L, T) and m["topright"] == (R, T) and m["bottomleft"] == (L, B)
                and m["bottomright"] == (R, B) and m["top"][0] == m["center"][0] == m["bottom"][0]
                and m["left"][1] == m["center"][1] == m["right"][1])
        if not goed:
            fouten.append(f"{v}*: hoeken passen niet op de randen")
    return fouten


def controleer(breeze: Path, doel: Path = UIT) -> int:
    fouten = 0
    for rel in bestanden():
        mijn = doel / f"{rel}.svg"
        if mijn.exists():
            for fout in kaders_kloppen(mijn):
                fouten += 1
                print(f"FOUT  {rel}: {fout}")
        ref = breeze / f"{rel}.svg"
        if not ref.exists():
            print(f"??    {rel}: geen Breeze-bestand om mee te vergelijken")
            continue
        if not mijn.exists():
            print(f"FOUT  {rel}: ontbreekt")
            fouten += 1
            continue
        nodig = api_ids(ids_van(ref))
        heb = ids_van(mijn)
        mist = sorted(nodig - heb)
        extra = sorted(api_ids(heb) - nodig)
        if mist:
            fouten += 1
            print(f"FOUT  {rel}: mist {len(mist)}: {' '.join(mist)}")
        else:
            print(f"ok    {rel}: alle {len(nodig)} id's van Breeze" + (f", plus {len(extra)} eigen" if extra else ""))
    return fouten


def main(args: list[str]) -> int:
    if args and args[0] == "--controleer":
        breeze = Path(args[1]) if len(args) > 1 else None
        if not breeze or not breeze.is_dir():
            print("gebruik: surfaces.py --controleer <map met de uitgepakte Breeze-stijl (.svg)> [uitmap]")
            return 2
        return 1 if controleer(breeze, Path(args[2]) if len(args) > 2 else UIT) else 0
    doel = Path(args[0]) if args else UIT
    for p in schrijf(doel):
        print("geschreven:", p.relative_to(doel).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
