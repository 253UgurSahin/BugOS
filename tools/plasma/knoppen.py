#!/usr/bin/env python3
"""Maakt de knoppen van de Plasma-stijl "bugos" (pop-ups van het systeemvak en widgets).

Schrijft de SVG's voor de bedieningselementen van PlasmaComponents 3 naar
system_files/usr/share/plasma/desktoptheme/bugos/widgets/:

    button, actionbutton, toolbar, slider, switch, tabbar, lineedit, checkmarks,
    radiobutton, scrollbar, scrollwidget, bar_meter_horizontal, bar_meter_vertical,
    busywidget, menubaritem, arrows, line

Dezelfde vormtaal als de eigen BugOS-apps en het snelmenu: vlakke warmgrijze
knoppen, rood alleen als accent (aan, gekozen, focus), schuif en schakelaar met
het koraal-naar-rood verloop en een wit bolletje. Kleuren lopen via de
ColorScheme-klassen van KSvg, zodat licht en donker vanzelf volgen.

De namen van de elementen (normal-center, groove-highlight, hint-*, ...) zijn de
API van Plasma: we houden dezelfde namen aan als Breeze.

Gebruik:  python3 tools/plasma/knoppen.py [uitmap]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "ontwerp"))
from tokens import KLEUREN, LIJN, MATEN, ROOD_VERLOOP, SYSTEM  # noqa: E402

UIT = SYSTEM / "usr" / "share" / "plasma" / "desktoptheme" / "bugos" / "widgets"
LICHT = KLEUREN["licht"]
KORAAL = ROOD_VERLOOP[0]  # begin van het verloop; het einde is de accentkleur
WIT = LICHT["accent_tekst"]  # vinkje, stip en bolletjes: wit in licht en donker

# Accentrood = ColorScheme-ButtonFocus (DecorationFocus in het kleurenschema, of de
# accentkleur van KDE). NIET ColorScheme-Highlight: dat is in BugOS de zachte
# selectiekleur (#FDE9E9 met rode tekst), net als de zijbalk van de BugOS-apps.
# Die gebruiken we alleen voor zachte tinten (ZACHT_ROOD hieronder).

# Rondingen. De gewone knop deelt zijn hoeken met het vinkvakje (16 px, CheckIndicator
# tekent widgets/button "normal"), daarom niet ronder dan 6. Gereedschapsknoppen
# (vlak, meestal alleen een pictogram) hebben eigen elementen en mogen ronder.
R_KNOP = 6
R_GEREEDSCHAP = 10
R_VELD = MATEN["knop"]  # invoervelden: 12, zoals in docs/HUISSTIJL.md
R_TAB = 10
R_MENU = 8
FOCUS = 2  # dikte van de focusring

# Doorzichtigheid van de tekstkleur over de achtergrond (zelfde gevoel als het snelmenu).
# Een knop is precies de BugOS-knop: ButtonBackground (#F1EEEE / #262930), zonder rand.
A_KNOP_ZWEEF = 0.05   # bij aanwijzen: ButtonBackground + 5% = knop_hover (#E8E4E4 / #2F333B)
A_KNOP_DRUK = 0.10    # ingedrukt (bovenop ButtonBackground)
A_VAK_RAND = 0.20     # rand van een leeg vinkvakje/keuzerondje (= rand_sterk, zoals in Kvantum)
VAK_RAND = 1.5        # dikte van die rand, zoals in Kvantum
A_SPOOR = 0.12        # ring van het bezig-rondje
A_SPOOR_KNOP = 0.08   # spoor van schuif en voortgang: ButtonBackground + 8%, warmgrijs zoals het snelmenu
A_SCHAKELAAR = 0.12   # schakelaar uit: ButtonBackground + 12% = schuif_uit (#D9D4D4 / #3A3E48)
A_VELD_RAND = 0.13
A_VELD_RAND_ZWEEF = 0.26
A_SCHUIF = 0.24       # schuifbalk (BugOS: rand_sterk, bij aanwijzen tekst3)
A_SCHUIF_ZWEEF = 0.45
A_LIJN = 0.10
NUL = 0.001           # zo zegt Breeze "geen marge"
# Zachte rode tint (gekozen tab, vlakke knop die aan staat, open menu): ColorScheme-Highlight.
# Dat is in BugOS de selectiekleur van de zijbalk (#FDE9E9 / #3A1C22), dus precies dezelfde tint.
ZACHT_ROOD = "Highlight"

STIJL = f"""    <style type="text/css" id="current-color-scheme">
        .ColorScheme-Text {{ color:{LICHT['tekst']}; }}
        .ColorScheme-Background {{ color:{LICHT['achter']}; }}
        .ColorScheme-ButtonFocus {{ color:{LICHT['accent']}; }}
        .ColorScheme-ButtonBackground {{ color:{LICHT['knop']}; }}
        .ColorScheme-ViewBackground {{ color:{LICHT['vlak']}; }}
        .ColorScheme-Highlight {{ color:{LICHT['accent_zacht']}; }}
    </style>"""


def f(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------------ verf ---

def klasse(naam: str, alfa: float = 1.0) -> str:
    """Vulling met een ColorScheme-kleur."""
    a = "" if alfa >= 1 else f";fill-opacity:{f(alfa)}"
    return f'class="ColorScheme-{naam}" style="fill:currentColor{a}"'


# Spoor van schuif en voortgangsbalk (8 px, helemaal rond): warmgrijs op de knopkleur.
SPOOR = [("vul", 0, 4, klasse("ButtonBackground")), ("vul", 0, 4, klasse("Text", A_SPOOR_KNOP))]


def kleur(hexkleur: str, alfa: float = 1.0) -> str:
    a = "" if alfa >= 1 else f";fill-opacity:{f(alfa)}"
    return f'style="fill:{hexkleur}{a}"'


def verloop(gid: str) -> str:
    return f'style="fill:url(#{gid})"'


# ------------------------------------------------------------- het blad ---

class Blad:
    """Een SVG-blad; blokken komen onder elkaar te staan."""

    def __init__(self) -> None:
        self.defs: list[str] = []
        self.delen: list[str] = []
        self.y = 2.0
        self.breed = 0.0

    def blok(self, w: float, h: float) -> tuple[float, float]:
        x, y = 2.0, self.y
        self.y += h + 6
        self.breed = max(self.breed, x + w + 2)
        return x, y

    def voeg(self, tekst: str) -> None:
        self.delen.append(tekst)

    def lineair(self, gid: str, x2: float, y2: float, stops: list[tuple[float, str, float]],
                x1: float = 0, y1: float = 0) -> None:
        s = "".join(f'<stop offset="{f(o)}" style="stop-color:{c};stop-opacity:{f(a)}"/>' for o, c, a in stops)
        self.defs.append(f'<linearGradient id="{gid}" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}">{s}</linearGradient>')

    def radiaal(self, gid: str, cx: float, cy: float, r: float, stops: list[tuple[float, str, float]]) -> None:
        s = "".join(f'<stop offset="{f(o)}" style="stop-color:{c};stop-opacity:{f(a)}"/>' for o, c, a in stops)
        self.defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{f(cx)}" cy="{f(cy)}" '
                         f'r="{f(r)}">{s}</radialGradient>')

    def schrijf(self, pad: Path, titel: str) -> None:
        w, h = self.breed, self.y
        defs = "\n".join("        " + d for d in self.defs)
        tekst = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!-- BugOS Plasma-stijl: {titel}. Gemaakt door tools/plasma/knoppen.py; niet met de hand bewerken. -->\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{f(w)}" height="{f(h)}" '
            f'viewBox="0 0 {f(w)} {f(h)}">\n'
            f'    <defs>\n{STIJL}\n{defs}\n    </defs>\n'
            + "\n".join(self.delen) + "\n</svg>\n"
        )
        pad.write_text(tekst, encoding="utf-8", newline="\n")


def rechthoek(x: float, y: float, w: float, h: float, verf: str = 'fill="none"', eid: str = "") -> str:
    i = f'id="{eid}" ' if eid else ""
    return f'<rect {i}x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" {verf}/>'


def hint(eid: str, x: float, y: float, w: float, h: float) -> str:
    return "    " + rechthoek(x, y, w, h, eid=eid)


# ------------------------------------------------- negen stukjes van een kader ---
#
# Een kader (FrameSvg) bestaat uit vier hoeken, vier randen en een midden. KSvg
# tekent de hoeken op ware grootte en rekt (of herhaalt) randen en midden.
# Een laag is een afgeronde rechthoek, ingesprongen vanaf de buitenrand:
#     ("vul",  inspring, straal, verf)
#     ("ring", inspring, straal, dikte, verf)
# De vormen worden per stukje uitgerekend, zonder clipPath (QtSvg-vriendelijk).

HOEKEN = {"topleft": (False, False), "topright": (True, False),
          "bottomleft": (False, True), "bottomright": (True, True)}


def _hoekpad(w: float, h: float, ins: float, r: float, sx: bool, sy: bool, ox: float, oy: float) -> str:
    """Pad van het deel van een afgeronde rechthoek in een hoekstukje (w x h)."""
    def p(x: float, y: float) -> str:
        return f"{f(ox + (w - x if sx else x))},{f(oy + (h - y if sy else y))}"
    if r <= 0:
        return f"M{p(ins, h)}L{p(ins, ins)}L{p(w, ins)}L{p(w, h)}Z"
    veeg = 0 if sx != sy else 1
    return (f"M{p(ins, h)}L{p(ins, ins + r)}A{f(r)},{f(r)} 0 0 {veeg} {p(ins + r, ins)}"
            f"L{p(w, ins)}L{p(w, h)}Z")


def _laag_hoek(laag: tuple, w: float, h: float, sx: bool, sy: bool, ox: float, oy: float) -> str:
    soort = laag[0]
    if soort == "vul":
        _, ins, r, verf = laag
        return f'<path d="{_hoekpad(w, h, ins, r, sx, sy, ox, oy)}" {verf}/>'
    _, ins, r, dik, verf = laag
    buiten = _hoekpad(w, h, ins, r, sx, sy, ox, oy)
    binnen = _hoekpad(w, h, ins + dik, max(r - dik, 0), sx, sy, ox, oy)
    return f'<path d="{buiten}{binnen}" {_evenodd(verf)}/>'


def _evenodd(verf: str) -> str:
    return verf.replace('style="', 'style="fill-rule:evenodd;', 1)


def _laag_rand(laag: tuple, kant: str, x: float, y: float, w: float, h: float) -> str:
    """Een rand (top/bottom/left/right) of het midden (center)."""
    soort = laag[0]
    ins = laag[1]
    if kant == "center":
        if soort == "ring":
            return ""
        return rechthoek(x, y, w, h, laag[3])
    dik = laag[3] if soort == "ring" else None
    verf = laag[4] if soort == "ring" else laag[3]
    if kant == "top":
        a, b = ins, (ins + dik if dik else h)
        return rechthoek(x, y + a, w, b - a, verf) if b > a else ""
    if kant == "bottom":
        a, b = (h - ins - dik if dik else 0), h - ins
        return rechthoek(x, y + a, w, b - a, verf) if b > a else ""
    if kant == "left":
        a, b = ins, (ins + dik if dik else w)
        return rechthoek(x + a, y, b - a, h, verf) if b > a else ""
    if kant == "right":
        a, b = (w - ins - dik if dik else 0), w - ins
        return rechthoek(x + a, y, b - a, h, verf) if b > a else ""
    raise ValueError(kant)


def kader(blad: Blad, prefix: str, hoek: float, lagen: list[tuple], marges: tuple | None = None,
          zijde: float = 4, extra_id: dict[str, str] | None = None, stukjes: dict | None = None) -> None:
    """Negen stukjes + marge-hints voor één prefix.

    hoek: breedte en hoogte van de hoekstukjes (minstens de straal van de ronding).
    marges: (boven, onder, links, rechts) of None (dan volgen ze uit de stukjes).
    extra_id: {"center": "pc"} geeft het onzichtbare kader van een stukje een extra naam.
    stukjes: {"center": teken(x, y, w, h) -> svg, ...} om een stukje zelf te tekenen (verlopen).
    """
    cw = ch = hoek
    s = zijde
    hm = max(marges) if marges else 0
    x0, y0 = blad.blok(cw * 2 + s + 6 + hm + 6, max(ch * 2 + s, 4 * 4 + 12))
    kol = {"l": x0, "m": x0 + cw, "r": x0 + cw + s}
    rij = {"t": y0, "m": y0 + ch, "b": y0 + ch + s}
    plekken = {
        "topleft": (kol["l"], rij["t"], cw, ch), "top": (kol["m"], rij["t"], s, ch),
        "topright": (kol["r"], rij["t"], cw, ch), "left": (kol["l"], rij["m"], cw, s),
        "center": (kol["m"], rij["m"], s, s), "right": (kol["r"], rij["m"], cw, s),
        "bottomleft": (kol["l"], rij["b"], cw, ch), "bottom": (kol["m"], rij["b"], s, ch),
        "bottomright": (kol["r"], rij["b"], cw, ch),
    }
    for stuk, (x, y, w, h) in plekken.items():
        binnen = []
        if stukjes and stuk in stukjes:
            binnen.append(stukjes[stuk](x, y, w, h))
        else:
            for laag in lagen:
                if stuk in HOEKEN:
                    sx, sy = HOEKEN[stuk]
                    binnen.append(_laag_hoek(laag, w, h, sx, sy, x, y))
                else:
                    binnen.append(_laag_rand(laag, stuk, x, y, w, h))
        eid = (extra_id or {}).get(stuk, "")
        omlijning = rechthoek(x, y, w, h, eid=eid)
        blad.voeg(f'    <g id="{prefix}-{stuk}">{omlijning}{"".join(b for b in binnen if b)}</g>')
    if marges:
        boven, onder, links, rechts = marges
        hx = x0 + cw * 2 + s + 6
        blad.voeg(hint(f"{prefix}-hint-top-margin", hx, y0, 2, boven))
        blad.voeg(hint(f"{prefix}-hint-bottom-margin", hx + 3, y0, 2, onder))
        blad.voeg(hint(f"{prefix}-hint-left-margin", hx, y0 + 10, links, 2))
        blad.voeg(hint(f"{prefix}-hint-right-margin", hx, y0 + 14, rechts, 2))


# ----------------------------------------------------------- verlopen ---

def verloop_stukjes(blad: Blad, gid: str, richting: str) -> dict:
    """Stukjes voor een balk met het koraal-naar-rood verloop.

    Het verloop loopt over de uitgerekte randen; de begin-hoeken zijn koraal, de
    eind-hoeken rood (ButtonFocus). Rood = basis, koraal = laag erboven die naar
    doorzichtig loopt: zo heeft het einde precies de accentkleur van het thema.
    richting "h": links koraal -> rechts rood. "v": onder koraal -> boven rood.

    Een liggende balk gebruikt alleen hoeken en boven/onder-randen. Staat dezelfde
    balk rechtop (verticale schuif), dan tekent KSvg de linker- en rechterrand:
    die lopen daarom samen van koraal naar rood over de breedte, zonder harde naad.
    """
    if richting == "h":
        blad.lineair(gid, 1, 0, [(0, KORAAL, 1), (1, KORAAL, 0)])
        blad.lineair(gid + "-l", 1, 0, [(0, KORAAL, 1), (1, KORAAL, 0.5)])
        blad.lineair(gid + "-r", 1, 0, [(0, KORAAL, 0.5), (1, KORAAL, 0)])
    else:
        blad.lineair(gid, 0, 0, [(0, KORAAL, 1), (1, KORAAL, 0)], x1=0, y1=1)
    rood = klasse("ButtonFocus")

    def hoekstuk(sx: bool, sy: bool, koraal: bool):
        def teken(x, y, w, h):
            d = _hoekpad(w, h, 0, min(w, h), sx, sy, x, y)
            uit = f'<path d="{d}" {rood}/>'
            if koraal:
                uit += f'<path d="{d}" {kleur(KORAAL)}/>'
            return uit
        return teken

    def randstuk(kant: str):
        def teken(x, y, w, h):
            uit = rechthoek(x, y, w, h, rood)
            if richting == "h" and kant in ("top", "bottom", "center"):
                uit += rechthoek(x, y, w, h, verloop(gid))
            elif richting == "h" and kant in ("left", "right"):
                uit += rechthoek(x, y, w, h, verloop(gid + ("-l" if kant == "left" else "-r")))
            elif richting == "v" and kant in ("left", "right", "center"):
                uit += rechthoek(x, y, w, h, verloop(gid))
            elif richting == "v" and kant == "bottom":
                uit += rechthoek(x, y, w, h, kleur(KORAAL))
            return uit
        return teken

    if richting == "h":
        hk = {"topleft": True, "bottomleft": True, "topright": False, "bottomright": False}
    else:
        hk = {"bottomleft": True, "bottomright": True, "topleft": False, "topright": False}
    uit = {k: hoekstuk(*HOEKEN[k], hk[k]) for k in HOEKEN}
    for kant in ("top", "bottom", "left", "right", "center"):
        uit[kant] = randstuk(kant)
    return uit


# ============================================================ de bestanden ===

def button() -> Blad:
    """Gewone knop, vlakke knop (ToolButton), vinkvakje (CheckIndicator) en keuzelijst.

    De gewone knop is de BugOS-knop: vlak warmgrijs (ButtonBackground), geen rand. Het
    vlak zit in het midden: met hint-compose-over-border legt KSvg het midden over de hele
    knop en snijdt het met mask-normal rond af. De randstukjes zijn daarom leeg.
    """
    b = Blad()
    rk, rg = R_KNOP, R_GEREEDSCHAP
    knop_marges = (8, 8, 12, 12)          # binnenruimte van een knop
    gereedschap_marges = (4, 4, 4, 4)     # zoals Breeze: pictogramknoppen blijven even groot
    # Schaduw: BugOS-knoppen zijn vlak. Het element blijft bestaan (API), maar is leeg.
    kader(b, "shadow", rk, [], (NUL, NUL, NUL, NUL),
          extra_id={"bottom": "sb", "right": "sr", "left": "sl", "top": "st"})
    vlak = {"center": lambda x, y, w, h: rechthoek(x, y, w, h, klasse("ButtonBackground"))}
    kader(b, "normal", rk, [], knop_marges, stukjes=vlak)
    b.voeg(hint("normal-hint-compose-over-border", 0, 0, 2, 2))
    _vinkvak(b)
    kader(b, "mask-normal", rk, [("vul", 0, rk, kleur("#000000"))])
    kader(b, "hover", rk, [("vul", 0, rk, klasse("Text", A_KNOP_ZWEEF))], (NUL, NUL, NUL, NUL))
    ingedrukt = [("vul", 0, rk, klasse("ButtonBackground")), ("vul", 0, rk, klasse("Text", A_KNOP_DRUK))]
    kader(b, "pressed", rk, ingedrukt, knop_marges, extra_id={"center": "pc"})
    b.voeg(hint("pressed-hint-compose-over-border", 0, 0, 2, 2))
    # Focus: een rode ring van 2 px direct om de knop heen (kader steekt 2 px uit).
    kader(b, "focus", rk + FOCUS, [("ring", 0, rk + FOCUS, FOCUS, klasse("ButtonFocus"))], (FOCUS,) * 4)
    # Vlakke knoppen: doorzichtig tot je ze aanwijst (dan knop_hover, zoals de ronde
    # knopjes in de BugOS-apps); aan (checked) = de zachte selectietint.
    zweef = [("vul", 0, rg, klasse("ButtonBackground")), ("vul", 0, rg, klasse("Text", A_KNOP_ZWEEF))]
    kader(b, "toolbutton-hover", rg, zweef, gereedschap_marges)
    kader(b, "toolbutton-pressed", rg, [("vul", 0, rg, klasse(ZACHT_ROOD))], gereedschap_marges)
    kader(b, "toolbutton-focus", rg + FOCUS, [("ring", 0, rg + FOCUS, FOCUS, klasse("ButtonFocus"))], (FOCUS,) * 4)
    return b


def _vinkvak(b: Blad) -> None:
    """Het lege vinkvakje: kaartkleur met een grijze rand van 1,5 px, net als in Kvantum.

    PlasmaComponents tekent het vakje met widgets/button "normal" op 16 x 16. Bij het
    tekenen van het midden kiest KSvg het kleinste element "<b>-<h>-normal-center" dat
    minstens zo groot is in schermpixels. Een knop is altijd groter dan 32 px en houdt
    dus het gewone grijze midden; alleen het vakje (16 px bij schaal 1 tot 32 px bij
    schaal 2) krijgt dit. Niet groter dan 32: dan zou een knop met alleen een pictogram
    (ongeveer 42 x 34) het ook krijgen.
    """
    for n in (16, 20, 24, 28, 32):
        s = n / 16
        x0, y0 = b.blok(n, n)
        d = VAK_RAND * s
        ring = (_hoekpad_rondom(x0, y0, n, n, R_KNOP * s)
                + _hoekpad_rondom(x0 + d, y0 + d, n - 2 * d, n - 2 * d, R_KNOP * s - d))
        b.voeg(f'    <g id="{n}-{n}-normal-center">{rechthoek(x0, y0, n, n)}'
               f'{rechthoek(x0, y0, n, n, klasse("ViewBackground"))}'
               f'<path d="{ring}" {_evenodd(klasse("Text", A_VAK_RAND))}/></g>')


def actionbutton() -> Blad:
    """Ronde knop (RoundButton, Dial): een cirkel in elke grootte."""
    b = Blad()
    grootten = [(32, ""), (24, "24-24-"), (22, "22-22-"), (16, "16-16-")]
    for maat, voor in grootten:
        x0, y0 = b.blok(maat * 4 + 18, maat)
        r = maat / 2
        for i, (naam, inhoud) in enumerate([
            ("normal", lambda cx, cy: f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {klasse("Text", 0.10)}/>'),
            ("pressed", lambda cx, cy: f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {klasse(ZACHT_ROOD)}/>'),
            ("hover", lambda cx, cy: f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {klasse("Text", 0.06)}/>'),
            ("focus", lambda cx, cy: (f'<path d="{_cirkel(cx, cy, r)}{_cirkel(cx, cy, r - FOCUS)}" '
                                      f'{_evenodd(klasse("ButtonFocus"))}/>')),
        ]):
            x = x0 + i * (maat + 6)
            b.voeg(f'    <g id="{voor}{naam}">{rechthoek(x, y0, maat, maat)}{inhoud(x + r, y0 + r)}</g>')
    return b


def _cirkel(cx: float, cy: float, r: float) -> str:
    return (f"M{f(cx - r)},{f(cy)}A{f(r)},{f(r)} 0 1 0 {f(cx + r)},{f(cy)}"
            f"A{f(r)},{f(r)} 0 1 0 {f(cx - r)},{f(cy)}Z")


def toolbar() -> Blad:
    """Achtergrond van een PlasmaComponents ToolBar: vlak, in de kleur van het venster."""
    b = Blad()
    x0, y0 = b.blok(40 + 30, 40)
    plekken = {
        "topleft": (0, 0, 4, 4), "top": (4, 0, 32, 4), "topright": (36, 0, 4, 4),
        "left": (0, 4, 4, 32), "center": (4, 4, 32, 32), "right": (36, 4, 4, 32),
        "bottomleft": (0, 36, 4, 4), "bottom": (4, 36, 32, 4), "bottomright": (36, 36, 4, 4),
    }
    for naam, (x, y, w, h) in plekken.items():
        b.voeg("    " + rechthoek(x0 + x, y0 + y, w, h, klasse("Background"), eid=naam))
    b.voeg(hint("hint-tile-center", x0 + 44, y0, 2, 2))
    b.voeg(hint("hint-top-margin", x0 + 48, y0, 2, 4))
    b.voeg(hint("hint-bottom-margin", x0 + 52, y0, 2, 4))
    b.voeg(hint("hint-left-margin", x0 + 44, y0 + 8, 4, 2))
    b.voeg(hint("hint-right-margin", x0 + 44, y0 + 12, 4, 2))
    return b


def _knop_bol(b: Blad, eid: str, x: float, y: float, w: float, h: float, r: float,
              vul: str = "#FFFFFF", rand_rood: bool = False) -> None:
    """Het witte bolletje van schuif en schakelaar (wit in licht en donker, net als het snelmenu).

    Een haarlijn eromheen (zwart op 12%); bij aanwijzen een zacht rode rand.
    """
    if rand_rood:
        rand = f'class="ColorScheme-ButtonFocus" style="fill:{vul};stroke:currentColor;stroke-opacity:0.45;stroke-width:1"'
    else:
        rand = f'style="fill:{vul};stroke:#000000;stroke-opacity:0.12;stroke-width:1"'
    b.voeg(f'    <g id="{eid}">{rechthoek(x, y, w, h)}'
           f'<circle cx="{f(x + w / 2)}" cy="{f(y + h / 2)}" r="{f(r - 0.5)}" {rand}/></g>')


def _schaduw(b: Blad, eid: str, gid: str, x: float, y: float, maat: float, r: float, zak: float = 1) -> None:
    cx, cy = x + maat / 2, y + maat / 2 + zak
    b.radiaal(gid, cx, cy, r, [(0, "#000000", 0.22), (0.72, "#000000", 0.12), (1, "#000000", 0)])
    b.voeg(f'    <g id="{eid}">{rechthoek(x, y, maat, maat)}'
           f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {verloop(gid)}/></g>')


def _ring(cx: float, cy: float, r_buiten: float, r_binnen: float, verf: str) -> str:
    return f'<path d="{_cirkel(cx, cy, r_buiten)}{_cirkel(cx, cy, r_binnen)}" {_evenodd(verf)}/>'


def slider() -> Blad:
    """Schuif: spoor van 8 px, gevuld deel met het verloop, wit bolletje van 22 px."""
    b = Blad()
    kader(b, "groove", 4, SPOOR)
    kader(b, "groove-highlight", 4, [], extra_id={"center": "msc"},
          stukjes=verloop_stukjes(b, "vul-h", "h"))
    for richting in ("horizontal", "vertical"):
        x0, y0 = b.blok(22 + 26 + 26 + 22 + 30, 28)
        _knop_bol(b, f"{richting}-slider-handle", x0, y0, 22, 22, 11)
        _schaduw(b, f"{richting}-slider-shadow", f"schaduw-{richting}", x0 + 26, y0, 28, 13)
        b.voeg(f'    <g id="{richting}-slider-focus">{rechthoek(x0 + 58, y0, 26, 26)}'
               f'{_ring(x0 + 71, y0 + 13, 13, 11, klasse("ButtonFocus"))}</g>')
        b.voeg(f'    <g id="{richting}-slider-hover">{rechthoek(x0 + 88, y0, 22, 22)}'
               f'{_ring(x0 + 99, y0 + 11, 11, 9.5, klasse("ButtonFocus", 0.4))}</g>')
    # Het bolletje is 22 px, maar PlasmaComponents rekent met 20: zo steekt het 1 px
    # over de uiteinden van het spoor en piept het rode deel er bij 0% en 100% niet
    # langs de rand van het bolletje uit.
    x0, y0 = b.blok(40, 22)
    b.voeg(hint("hint-handle-size", x0, y0, 20, 20))
    b.voeg(hint("hint-tile-center", x0 + 26, y0, 2, 2))
    b.voeg(hint("hint-stretch-borders", x0 + 30, y0, 2, 2))
    return b


def switch() -> Blad:
    """Schakelaar: pil van 40 x 22, uit = grijs, aan = koraal naar rood, wit bolletje."""
    b = Blad()
    h, kap, mid = 22, 11, 2
    b.lineair("aan-verloop", 1, 0, [(0, KORAAL, 1), (1, KORAAL, 0)])
    for prefix in ("inactive", "active"):
        x0, y0 = b.blok(kap * 2 + mid + 4, h)
        links = f"M{f(x0 + kap)},{f(y0)}A{kap},{kap} 0 0 0 {f(x0 + kap)},{f(y0 + h)}Z"
        rechts_x = x0 + kap + mid
        rechts = f"M{f(rechts_x)},{f(y0)}A{kap},{kap} 0 0 1 {f(rechts_x)},{f(y0 + h)}Z"
        if prefix == "inactive":
            # Warmgrijs zoals de BugOS-schakelaar (schuif_uit): knopkleur met 12% tekst erover.
            onder, grijs = klasse("ButtonBackground"), klasse("Text", A_SCHAKELAAR)
            delen = {"left": f'<path d="{links}" {onder}/><path d="{links}" {grijs}/>',
                     "center": rechthoek(x0 + kap, y0, mid, h, onder) + rechthoek(x0 + kap, y0, mid, h, grijs),
                     "right": f'<path d="{rechts}" {onder}/><path d="{rechts}" {grijs}/>'}
        else:
            rood = klasse("ButtonFocus")
            delen = {"left": f'<path d="{links}" {rood}/><path d="{links}" {kleur(KORAAL)}/>',
                     "center": rechthoek(x0 + kap, y0, mid, h, rood) + rechthoek(x0 + kap, y0, mid, h, verloop("aan-verloop")),
                     "right": f'<path d="{rechts}" {rood}/>'}
        b.voeg(f'    <g id="{prefix}-left">{rechthoek(x0, y0, kap, h)}{delen["left"]}</g>')
        b.voeg(f'    <g id="{prefix}-center">{rechthoek(x0 + kap, y0, mid, h)}{delen["center"]}</g>')
        b.voeg(f'    <g id="{prefix}-right">{rechthoek(rechts_x, y0, kap, h)}{delen["right"]}</g>')
    # Het bolletje: 18 px, met 2 px lucht in de pil. Het element is 24 breed, zodat het
    # bolletje links en rechts net zo ver van de rand staat als boven en onder.
    x0, y0 = b.blok(24 * 3 + 24 + 28 + 30, 28)
    _knop_bol(b, "handle", x0, y0, 24, 22, 9)
    _knop_bol(b, "handle-hover", x0 + 28, y0, 24, 22, 9, rand_rood=True)
    _knop_bol(b, "handle-pressed", x0 + 56, y0, 24, 22, 9, vul=LICHT["knop"])
    b.voeg(f'    <g id="handle-focus">{rechthoek(x0 + 84, y0, 24, 24)}'
           f'{_ring(x0 + 96, y0 + 12, 12, 10, klasse("ButtonFocus"))}</g>')
    _schaduw(b, "handle-shadow", "schaduw-knop", x0 + 112, y0, 28, 11.5)
    x0, y0 = b.blok(60, 22)
    b.voeg(hint("hint-bar-size", x0, y0, 42, 22))
    b.voeg(hint("hint-stretch-borders", x0 + 46, y0, 2, 2))
    return b


def tabbar() -> Blad:
    """Tabs: de gekozen tab krijgt een zacht rode pil (ook: open pop-up in de taakbalk).

    Dezelfde tint als het gekozen onderdeel in de zijbalk van de BugOS-apps.
    """
    b = Blad()
    ins = 3
    c = ins + R_TAB
    for kant in ("north", "south", "east", "west"):
        kader(b, f"{kant}-active-tab", c, [("vul", ins, R_TAB, klasse(ZACHT_ROOD))],
              (9, 9, 12, 12))
    x0, y0 = b.blok(4, 2)
    b.voeg(hint("hint-tile-center", x0, y0, 2, 2))
    return b


def lineedit() -> Blad:
    """Invoerveld: kaartkleur met een dunne rand; focus = rode rand van 2 px."""
    b = Blad()
    r = R_VELD
    x0, y0 = b.blok(12, 2)
    b.voeg(hint("hint-tile-center", x0, y0, 2, 2))
    b.voeg(hint("hint-focus-over-base", x0 + 4, y0, 2, 2))
    kader(b, "base", r, [("vul", 0, r, klasse("ViewBackground")), ("ring", 0, r, 1, klasse("Text", A_VELD_RAND))],
          (8, 8, 12, 12))
    kader(b, "hover", r, [("ring", 0, r, 1, klasse("Text", A_VELD_RAND_ZWEEF))], (NUL, NUL, NUL, NUL))
    kader(b, "focus", r, [("ring", 0, r, FOCUS, klasse("ButtonFocus"))], (NUL, NUL, NUL, NUL))
    kader(b, "focusframe", r, [("ring", 0, r, FOCUS, klasse("ButtonFocus"))], (NUL, NUL, NUL, NUL))
    return b


def checkmarks() -> Blad:
    """Vinkje (CheckBox) en bolletje (oude RadioButton): rood vlak met wit teken."""
    b = Blad()
    x0, y0 = b.blok(16, 16)
    vak = _hoekpad_rondom(x0, y0, 16, 16, R_KNOP)
    vink = f"M{f(x0 + 3.5)},{f(y0 + 8.3)}L{f(x0 + 6.5)},{f(y0 + 11.3)}L{f(x0 + 12.6)},{f(y0 + 5)}"
    b.voeg(f'    <g id="checkbox">{rechthoek(x0, y0, 16, 16)}<path d="{vak}" {klasse("ButtonFocus")}/>'
           f'<path d="{vink}" style="fill:none;stroke:{WIT};'
           f'stroke-width:2;stroke-linecap:round;stroke-linejoin:round"/></g>')
    x0, y0 = b.blok(16, 16)
    b.voeg(f'    <g id="radiobutton">{rechthoek(x0, y0, 16, 16)}'
           f'<circle cx="{f(x0 + 8)}" cy="{f(y0 + 8)}" r="8" {klasse("ButtonFocus")}/>'
           f'<circle cx="{f(x0 + 8)}" cy="{f(y0 + 8)}" r="3" {kleur(WIT)}/></g>')
    return b


def _hoekpad_rondom(x: float, y: float, w: float, h: float, r: float) -> str:
    return (f"M{f(x + r)},{f(y)}H{f(x + w - r)}A{f(r)},{f(r)} 0 0 1 {f(x + w)},{f(y + r)}V{f(y + h - r)}"
            f"A{f(r)},{f(r)} 0 0 1 {f(x + w - r)},{f(y + h)}H{f(x + r)}A{f(r)},{f(r)} 0 0 1 {f(x)},{f(y + h - r)}"
            f"V{f(y + r)}A{f(r)},{f(r)} 0 0 1 {f(x + r)},{f(y)}Z")


def radiobutton() -> Blad:
    """Keuzerondje: uit = wit rondje met een grijze rand (zoals het vinkvakje en Kvantum),
    aan = rood met een witte stip."""
    b = Blad()
    x0, y0 = b.blok(16 * 3 + 20 + 22 + 6 * 4 + 6 + 16, 22)
    c = 8
    b.voeg(f'    <g id="normal">{rechthoek(x0, y0, 16, 16)}'
           f'<circle cx="{f(x0 + c)}" cy="{f(y0 + c)}" r="8" {klasse("ViewBackground")}/>'
           f'{_ring(x0 + c, y0 + c, 8, 8 - VAK_RAND, klasse("Text", A_VAK_RAND))}</g>')
    x = x0 + 22
    b.voeg(f'    <g id="checked">{rechthoek(x, y0, 16, 16)}'
           f'<circle cx="{f(x + c)}" cy="{f(y0 + c)}" r="8" {klasse("ButtonFocus")}/></g>')
    x += 22
    b.voeg(f'    <g id="hover">{rechthoek(x, y0, 16, 16)}'
           f'<circle cx="{f(x + c)}" cy="{f(y0 + c)}" r="8" {klasse("Text", A_KNOP_ZWEEF)}/></g>')
    x += 22
    b.voeg(f'    <g id="focus">{rechthoek(x, y0, 20, 20)}{_ring(x + 10, y0 + 10, 10, 8, klasse("ButtonFocus"))}</g>')
    x += 26
    b.voeg(f'    <g id="shadow">{rechthoek(x, y0, 22, 22)}</g>')
    x += 28
    b.voeg(hint("hint-size", x, y0, 16, 16))
    x += 20
    b.voeg(f'    <circle id="symbol" cx="{f(x + 3)}" cy="{f(y0 + 3)}" r="3" {kleur(WIT)}/>')
    return b


def scrollbar() -> Blad:
    """Schuifbalk: een dun afgerond greepje, geen pijltjes en geen spoor."""
    b = Blad()
    x0, y0 = b.blok(12, 2)
    b.voeg(hint("hint-tile-center", x0, y0, 2, 2))
    b.voeg(hint("hint-scrollbar-size", x0 + 4, y0, 6, 6))
    inspring = 4

    def insets(prefix: str) -> None:
        x, y = b.blok(30, 8)
        b.voeg(hint(f"{prefix}-hint-left-inset", x, y, inspring, 3))
        b.voeg(hint(f"{prefix}-hint-right-inset", x + 6, y, inspring, 3))
        b.voeg(hint(f"{prefix}-hint-top-inset", x + 12, y, 3, inspring))
        b.voeg(hint(f"{prefix}-hint-bottom-inset", x + 18, y, 3, inspring))

    kader(b, "slider", 3, [("vul", 0, 3, klasse("Text", A_SCHUIF))])
    insets("slider")
    kader(b, "mouseover-slider", 3, [("vul", 0, 3, klasse("Text", A_SCHUIF_ZWEEF))], extra_id={"center": "msc"})
    insets("mouseover-slider")
    for richting in ("vertical", "horizontal"):
        kader(b, f"background-{richting}", 3, [])
        insets(f"background-{richting}")
    return b


def scrollwidget() -> Blad:
    """Rand om een schuifvlak (oude API): een haarlijn met ronde hoeken."""
    b = Blad()
    kader(b, "border", 8, [("ring", 0, 8, 1, klasse("Text", A_LIJN + 0.02))])
    return b


def bar_meter(richting: str) -> Blad:
    """Voortgangsbalk: spoor van 8 px zoals de schuif, gevuld deel met het verloop."""
    b = Blad()
    x0, y0 = b.blok(12, 8)
    b.voeg(hint("hint-tile-center", x0, y0, 2, 2))
    b.voeg(hint("hint-bar-size", x0 + 4, y0, 8, 8))
    b.voeg(hint("hint-stretch-borders", x0 + 14, y0, 2, 2))
    kader(b, "bar-inactive", 4, SPOOR)
    kader(b, "bar-active", 4, [], extra_id={"center": "msc"},
          stukjes=verloop_stukjes(b, "vul", "h" if richting == "horizontal" else "v"))
    return b


def busywidget() -> Blad:
    """Bezig-rondje: een grijze ring met een rood boogje dat ronddraait."""
    b = Blad()

    def rondje(eid: str, x: float, y: float, maat: float, dik: float, boog: bool) -> None:
        r = maat / 2 - dik / 2 - 0.5
        cx, cy = x + maat / 2, y + maat / 2
        ring = (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" class="ColorScheme-Text" '
                f'style="fill:none;stroke:currentColor;stroke-opacity:{f(A_SPOOR + 0.03)};stroke-width:{f(dik)}"/>')
        stuk = ""
        if boog:
            # Boog van ongeveer 110 graden, bovenaan beginnend.
            a1, a2 = math.radians(-90), math.radians(20)
            p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
            p2 = (cx + r * math.cos(a2), cy + r * math.sin(a2))
            stuk = (f'<path d="M{f(p1[0])},{f(p1[1])}A{f(r)},{f(r)} 0 0 1 {f(p2[0])},{f(p2[1])}" '
                    f'class="ColorScheme-ButtonFocus" style="fill:none;stroke:currentColor;stroke-width:{f(dik)};'
                    f'stroke-linecap:round"/>')
        b.voeg(f'    <g id="{eid}">{rechthoek(x, y, maat, maat)}{ring}{stuk}</g>')

    x0, y0 = b.blok(36 * 2 + 22 + 16 + 40, 36)
    rondje("busywidget", x0, y0, 36, 3, True)
    rondje("stopped", x0 + 40, y0, 36, 3, False)
    rondje("22-22-busywidget", x0 + 80, y0, 22, 2.5, True)
    rondje("16-16-busywidget", x0 + 106, y0, 16, 2, True)
    b.voeg(hint("hint-rotation-angle", x0 + 126, y0, 14, 14))
    return b


def menubaritem() -> Blad:
    """Menubalk (globaal menu): aanwijzen = zacht grijs, open = zacht rood."""
    b = Blad()
    m = (8, 8, 8, 8)
    kader(b, "normal", R_MENU, [], m)
    kader(b, "hover", R_MENU, [("vul", 0, R_MENU, klasse("ButtonBackground")),
                               ("vul", 0, R_MENU, klasse("Text", A_KNOP_ZWEEF))], m)
    kader(b, "pressed", R_MENU, [("vul", 0, R_MENU, klasse(ZACHT_ROOD))], m)
    return b


def arrows() -> Blad:
    """Pijltjes (keuzelijst e.d.): de BugOS-lijn, 2 op het 24-raster, ronde uiteinden."""
    b = Blad()
    k = 14 / 24  # van het 24-raster naar een vakje van 14

    # 'onder' uit LIJN: m6.5 9.5 5.5 5.5 5.5-5.5  (punten op het 24-raster)
    assert LIJN["onder"] == '<path d="m6.5 9.5 5.5 5.5 5.5-5.5"/>'
    omlaag = [(6.5, 9.5), (12, 15), (17.5, 9.5)]
    vormen = {
        "down-arrow": omlaag,
        "up-arrow": [(x, 24 - y) for x, y in omlaag],
        "left-arrow": [(24 - y, x) for x, y in omlaag],
        "right-arrow": [(y, x) for x, y in omlaag],
    }
    x0, y0 = b.blok(14 * 4 + 18, 14)
    for i, (eid, punten) in enumerate(vormen.items()):
        x = x0 + i * 18
        d = "M" + "L".join(f"{f(x + px * k)},{f(y0 + py * k)}" for px, py in punten)
        b.voeg(f'    <g id="{eid}">{rechthoek(x, y0, 14, 14)}<path d="{d}" class="ColorScheme-Text" '
               f'style="fill:none;stroke:currentColor;stroke-width:{f(2 * k)};stroke-linecap:round;'
               f'stroke-linejoin:round"/></g>')
    return b


def line() -> Blad:
    """Scheidingslijn: tekstkleur op 10%, zoals de randen in de BugOS-apps."""
    b = Blad()
    b.voeg(f'    <rect id="vertical-line" x="0" y="0" width="1" height="1" {klasse("Text", A_LIJN)}/>')
    b.voeg(f'    <rect id="horizontal-line" x="2" y="0" width="1" height="1" {klasse("Text", A_LIJN)}/>')
    b.y, b.breed = 1, 3
    return b


BESTANDEN = {
    "button": (button, "knoppen"),
    "actionbutton": (actionbutton, "ronde knoppen"),
    "toolbar": (toolbar, "werkbalk"),
    "slider": (slider, "schuif"),
    "switch": (switch, "schakelaar"),
    "tabbar": (tabbar, "tabs"),
    "lineedit": (lineedit, "invoerveld"),
    "checkmarks": (checkmarks, "vinkjes"),
    "radiobutton": (radiobutton, "keuzerondjes"),
    "scrollbar": (scrollbar, "schuifbalk"),
    "scrollwidget": (scrollwidget, "rand van een schuifvlak"),
    "bar_meter_horizontal": (lambda: bar_meter("horizontal"), "voortgangsbalk"),
    "bar_meter_vertical": (lambda: bar_meter("vertical"), "staande voortgangsbalk"),
    "busywidget": (busywidget, "bezig-rondje"),
    "menubaritem": (menubaritem, "menubalk"),
    "arrows": (arrows, "pijltjes"),
    "line": (line, "lijnen"),
}


def main(args: list[str]) -> int:
    uit = Path(args[0]) if args else UIT
    uit.mkdir(parents=True, exist_ok=True)
    for naam, (maker, titel) in BESTANDEN.items():
        maker().schrijf(uit / f"{naam}.svg", titel)
    print(len(BESTANDEN), "bestanden in", uit)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
