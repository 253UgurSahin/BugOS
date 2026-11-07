"""Lijstregels, kaders, marges en taakknoppen voor surfaces.py."""

from __future__ import annotations

from surfaces_frames import kader, marges
from surfaces_shapes import (A_RAND, A_ROOD, A_ROOD_ZWEEF, A_STREEP, A_STREEP_MIN, A_ZWEEF, KAART, KAPPA, R_KAART,
                             R_REGEL, ROOD, RR, ZWEEF, Blad, Laag, f, laag_in_tegel, pad, verf)


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
