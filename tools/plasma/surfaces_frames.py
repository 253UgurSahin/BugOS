"""Kaders voor surfaces.py: negen stukjes, marges, schaduwen (KWin) en maskers."""

from __future__ import annotations

import math

from surfaces_shapes import A_RAND, KAPPA, NEGEN, RR, Blad, Laag, Schaduw, f, knip, laag_in_tegel, pad


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
