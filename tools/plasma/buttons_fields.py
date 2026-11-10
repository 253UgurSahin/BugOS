"""Tabs, invoerveld, schuifbalk, voortgang, bezig-rondje, menubalk, pijltjes en lijnen voor buttons.py."""

from __future__ import annotations

import math

from buttons_draw import (A_KNOP_ZWEEF, A_LIJN, A_SCHUIF, A_SCHUIF_ZWEEF, A_SPOOR, A_VELD_RAND, A_VELD_RAND_ZWEEF,
                          FOCUS, NUL, R_MENU, R_TAB, R_VELD, SPOOR, ZACHT_ROOD, Blad, f, hint, kader, klasse,
                          rechthoek, verloop_stukjes)
from tokens import LIJN


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
