"""Knoppen, vinkjes, keuzerondjes, schuif en schakelaar voor buttons.py."""

from __future__ import annotations

from buttons_draw import (A_KNOP_DRUK, A_KNOP_ZWEEF, A_SCHAKELAAR, A_VAK_RAND, FOCUS, KORAAL, LICHT, NUL,
                          R_GEREEDSCHAP, R_KNOP, SPOOR, VAK_RAND, WIT, ZACHT_ROOD, Blad, _evenodd, f, hint, kader,
                          klasse, kleur, rechthoek, verloop, verloop_stukjes)


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
            # Warmgrijs zoals de BugOS-schakelaar (schuif_uit): knopkleur met 45% tekst erover (3:1, U283).
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
