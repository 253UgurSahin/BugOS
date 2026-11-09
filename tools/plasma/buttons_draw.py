"""Maten, kleuren, het SVG-blad en de negen stukjes van een kader voor buttons.py."""

from __future__ import annotations

from pathlib import Path

from tokens import KLEUREN, MATEN, ROOD_VERLOOP


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
R_VELD = MATEN["knop"]  # invoervelden: 12, zoals in docs/BRAND.md
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
A_SCHAKELAAR = 0.45   # schakelaar uit: ButtonBackground + 45% haalt 3:1 tegen het vlak, zoals schuif_uit (U283)
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
            f'<!-- BugOS Plasma-stijl: {titel}. Gemaakt door tools/plasma/buttons.py; niet met de hand bewerken. -->\n'
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
