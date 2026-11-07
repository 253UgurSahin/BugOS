"""SVG-bouwstenen voor make.py: Svg, negenvlakken, sporen, lijntekeningen en schaduwen."""

from __future__ import annotations

import re

from palette import STATEN
from tokens import LIJN


# ---------------------------------------------------------------- SVG

def vul(kleur: str | None) -> str:
    """SVG-vulling uit #RRGGBB, #RRGGBBAA of url(#...)."""
    if kleur is None:
        return 'fill="#000000" fill-opacity="0"'
    if kleur.startswith("url("):
        return f'fill="{kleur}"'
    h = kleur.lstrip("#")
    if len(h) == 8:
        a = int(h[6:8], 16) / 255
        return f'fill="#{h[:6]}" fill-opacity="{a:.3f}"'
    return f'fill="#{h}"'


def f(v: float) -> str:
    return ("%.3f" % v).rstrip("0").rstrip(".")


class Svg:
    """Een SVG met elementen op een raster; elk element heeft een onzichtbaar kader voor zijn maat."""

    BREED = 1600

    def __init__(self) -> None:
        self.delen: list[str] = []
        self.defs: list[str] = []
        self.ids: set[str] = set()
        self.x = self.y = 0.0
        self.rij = 0.0
        self.n = 0

    def plek(self, w: float, h: float) -> tuple[float, float]:
        if self.x + w > self.BREED:
            self.x = 0
            self.y += self.rij + 4
            self.rij = 0
        x, y = self.x, self.y
        self.x += w + 4
        self.rij = max(self.rij, h)
        return x, y

    def element(self, id_: str, w: float, h: float, inhoud) -> None:
        """inhoud(x, y) -> SVG-tekst binnen het vak (x, y, w, h)."""
        if id_ in self.ids:
            raise ValueError("dubbel element: " + id_)
        self.ids.add(id_)
        x, y = self.plek(w, h)
        self.delen.append(f'<g id="{id_}"><rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" '
                          f'fill="#000000" fill-opacity="0"/>{inhoud(x, y)}</g>')

    def verloop(self, kleuren: tuple[str, str], x2: float = 1, y2: float = 0) -> str:
        self.n += 1
        gid = f"v{self.n}"
        self.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="{f(x2)}" y2="{f(y2)}">'
                         f'<stop offset="0" stop-color="{kleuren[0]}"/><stop offset="1" stop-color="{kleuren[1]}"/>'
                         '</linearGradient>')
        return f"url(#{gid})"

    def verloop_vervaag(self, kleur: str, alpha: float, x2: float, y2: float, omgekeerd: bool) -> str:
        """Verloop van één kleur van alpha naar helemaal doorzichtig (of andersom).

        Waarom niet verloop() met '#00000000': Qt's SVG-tekenaar (die Kvantum gebruikt)
        kent geen kleuren met een alfakanaal (#RRGGBBAA). Dan vloeit het verloop niet uit
        en krijg je een harde grijze band om elk menu. stop-opacity kent Qt wel."""
        self.n += 1
        gid = f"v{self.n}"
        van, tot = (0.0, alpha) if omgekeerd else (alpha, 0.0)
        self.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="{f(x2)}" y2="{f(y2)}">'
                         f'<stop offset="0" stop-color="{kleur}" stop-opacity="{f(van)}"/>'
                         f'<stop offset="1" stop-color="{kleur}" stop-opacity="{f(tot)}"/>'
                         '</linearGradient>')
        return f"url(#{gid})"

    def radiaal(self, kleur: str, alpha: float, cx: float, cy: float) -> str:
        """Zachte schaduw voor hoeken: vol bij (cx, cy) van het vak, weg aan de overkant."""
        self.n += 1
        gid = f"r{self.n}"
        self.defs.append(f'<radialGradient id="{gid}" cx="{f(cx)}" cy="{f(cy)}" r="1" fx="{f(cx)}" fy="{f(cy)}">'
                         f'<stop offset="0" stop-color="{kleur}" stop-opacity="{f(alpha)}"/>'
                         f'<stop offset="1" stop-color="{kleur}" stop-opacity="0"/></radialGradient>')
        return f"url(#{gid})"

    def tekst(self) -> str:
        h = self.y + self.rij + 4
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<!-- Gemaakt door tools/kvantum/make.py uit tools/design/tokens.py; niet met de hand bewerken. -->\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.BREED}" height="{f(h)}" viewBox="0 0 {self.BREED} {f(h)}">\n'
                f'<defs>{"".join(self.defs)}</defs>\n' + "\n".join(self.delen) + "\n</svg>\n")


# Hoekpaden: het pad linksboven, en spiegelingen voor de andere hoeken.
def _hoek_pad(hoek: str, x0: float, y0: float, s: float, r: float, i: float) -> str:
    """Gevuld vlak van een hoekstuk (s x s) met straal r, ingesprongen met i (voor de binnenkant)."""
    ri = max(r - i, 0)
    # punten voor linksboven in lokale coördinaten
    pts = [("M", i, s), ("L", i, r if ri > 0 else i), ("A", r, i) if ri > 0 else ("L", r, i), ("L", s, i), ("L", s, s)]
    spx = hoek.endswith("right")
    spy = hoek.startswith("bottom")

    def tx(x):
        return x0 + (s - x if spx else x)

    def ty(y):
        return y0 + (s - y if spy else y)

    sweep = 1 if spx == spy else 0
    d = []
    for cmd, x, y in pts:
        if cmd == "A":
            d.append(f"A{f(ri)} {f(ri)} 0 0 {sweep} {f(tx(x))} {f(ty(y))}")
        else:
            d.append(f"{cmd}{f(tx(x))} {f(ty(y))}")
    return " ".join(d) + " Z"


def negenvlak(svg: Svg, naam: str, staat: str, s: float, r: float, kleur: str | None, rand: str | None = None,
              rw: float = 1.0, binnen: bool = True, binnen_kleur: str | None = "zelfde", L: float = 8,
              alleen_onder: bool = False) -> None:
    """Hoeken, randen en binnenkant van één toestand: naam-staat-top, ...-topleft, naam-staat."""
    i = rw if rand else 0.0
    if alleen_onder:   # kopje van een tabel: alleen een lijn onderaan
        for deel, (w, h) in {"topleft": (s, s), "top": (L, s), "topright": (s, s), "left": (s, L), "right": (s, L)}.items():
            svg.element(f"{naam}-{staat}-{deel}", w, h,
                        lambda x, y, w=w, h=h: f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" {vul(kleur)}/>')
        for deel, w in (("bottomleft", s), ("bottom", L), ("bottomright", s)):
            svg.element(f"{naam}-{staat}-{deel}", w, s,
                        lambda x, y, w=w: f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(s - rw)}" {vul(kleur)}/>'
                        f'<rect x="{f(x)}" y="{f(y + s - rw)}" width="{f(w)}" height="{f(rw)}" {vul(rand)}/>')
    else:
        for hoek in ("topleft", "topright", "bottomleft", "bottomright"):
            def teken(x, y, hoek=hoek):
                uit = ""
                if rand:
                    ring = _hoek_pad(hoek, x, y, s, r, 0) + " " + _hoek_pad(hoek, x, y, s, r, i)
                    uit += f'<path d="{ring}" fill-rule="evenodd" {vul(rand)}/>'
                if kleur:
                    uit += f'<path d="{_hoek_pad(hoek, x, y, s, r, i)}" {vul(kleur)}/>'
                return uit
            svg.element(f"{naam}-{staat}-{hoek}", s, s, teken)

        def rand_stuk(kant):
            def teken(x, y):
                uit = ""
                if kant in ("top", "bottom"):
                    by = y if kant == "top" else y + s - i
                    vy = y + i if kant == "top" else y
                    if rand:
                        uit += f'<rect x="{f(x)}" y="{f(by)}" width="{f(L)}" height="{f(i)}" {vul(rand)}/>'
                    if kleur:
                        uit += f'<rect x="{f(x)}" y="{f(vy)}" width="{f(L)}" height="{f(s - i)}" {vul(kleur)}/>'
                else:
                    bx = x if kant == "left" else x + s - i
                    vx = x + i if kant == "left" else x
                    if rand:
                        uit += f'<rect x="{f(bx)}" y="{f(y)}" width="{f(i)}" height="{f(L)}" {vul(rand)}/>'
                    if kleur:
                        uit += f'<rect x="{f(vx)}" y="{f(y)}" width="{f(s - i)}" height="{f(L)}" {vul(kleur)}/>'
                return uit
            return teken

        svg.element(f"{naam}-{staat}-top", L, s, rand_stuk("top"))
        svg.element(f"{naam}-{staat}-bottom", L, s, rand_stuk("bottom"))
        svg.element(f"{naam}-{staat}-left", s, L, rand_stuk("left"))
        svg.element(f"{naam}-{staat}-right", s, L, rand_stuk("right"))
    if binnen:
        bk = kleur if binnen_kleur == "zelfde" else binnen_kleur
        svg.element(f"{naam}-{staat}", L, L,
                    lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="{f(L)}" height="{f(L)}" {vul(bk)}/>')


def spoor(svg: Svg, naam: str, staat: str, s: float, begin: str, eind: str, verloop_id: str, langs: str) -> None:
    """Een gevuld spoor (pil) met een verloop over de hele lengte.

    langs="y": staand ontwerp (schuif; Kvantum legt het om: boven = links);
    langs="x": liggend ontwerp (voortgangsbalk). Begin- en eindkappen krijgen de vaste kleur.
    """
    L = 8

    def rect(w, h, kl):
        return lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" {vul(kl)}/>'

    for hoek in ("topleft", "topright", "bottomleft", "bottomright"):
        if langs == "y":
            kl = begin if hoek.startswith("top") else eind
        else:
            kl = begin if hoek.endswith("left") else eind
        svg.element(f"{naam}-{staat}-{hoek}", s, s,
                    lambda x, y, hoek=hoek, kl=kl: f'<path d="{_hoek_pad(hoek, x, y, s, s, 0)}" {vul(kl)}/>')
    if langs == "y":
        svg.element(f"{naam}-{staat}-top", L, s, rect(L, s, begin))
        svg.element(f"{naam}-{staat}-bottom", L, s, rect(L, s, eind))
        svg.element(f"{naam}-{staat}-left", s, L, rect(s, L, verloop_id))
        svg.element(f"{naam}-{staat}-right", s, L, rect(s, L, verloop_id))
    else:
        svg.element(f"{naam}-{staat}-top", L, s, rect(L, s, verloop_id))
        svg.element(f"{naam}-{staat}-bottom", L, s, rect(L, s, verloop_id))
        svg.element(f"{naam}-{staat}-left", s, L, rect(s, L, begin))
        svg.element(f"{naam}-{staat}-right", s, L, rect(s, L, eind))
    svg.element(f"{naam}-{staat}", L, L, rect(L, L, verloop_id))


def uitzetbaar(svg: Svg, naam: str, staten=STATEN) -> None:
    """Het vlaggetje waarmee Kvantum de hoeken van `naam` mag uitzetten (frame.expansion)."""
    for st in staten:
        svg.element(f"expand-{naam}-{st}", 4, 4,
                    lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="4" height="4" fill="#000000"/>')


def kader_set(svg: Svg, klein: str, groot: str, staten: dict, s_klein: float, s_groot: float, r_groot: float,
              binnen: bool = True) -> None:
    """Een onderdeel met een klein kader (voor de opmaak) en een groot rond kader (wat je ziet)."""
    for st, (kleur, rand, rw) in staten.items():
        negenvlak(svg, klein, st, s_klein, min(s_klein, r_groot), kleur, rand, rw, binnen=binnen)
        negenvlak(svg, groot, st, s_groot, r_groot, kleur, rand, rw, binnen=binnen)
    uitzetbaar(svg, groot, staten.keys())


# ---------------------------------------------------------------- kleine tekeningen

def lijn_pad(naam: str) -> str:
    """De d-waarden van een BugOS-lijnicoon (24-raster)."""
    return " ".join(re.findall(r'd="([^"]+)"', LIJN[naam]))


def icoon(svg: Svg, id_: str, d: str, kleur: str, maat: float = 16, lijn: float = 2.0, draai: float = 0,
          raster: float = 24) -> None:
    """Een lijntekening (pad op een raster van 24) in een vak van maat x maat."""
    schaal = maat / raster
    alpha = ""
    h = kleur.lstrip("#")
    if len(h) == 8:
        alpha = f' stroke-opacity="{int(h[6:8], 16) / 255:.3f}"'
        kleur = "#" + h[:6]

    def teken(x, y):
        rot = f" rotate({f(draai)} {f(raster / 2)} {f(raster / 2)})" if draai else ""
        return (f'<g transform="translate({f(x)} {f(y)}) scale({f(schaal)}){rot}">'
                f'<path d="{d}" fill="none" stroke="{kleur}"{alpha} stroke-width="{f(lijn / schaal)}" '
                'stroke-linecap="round" stroke-linejoin="round"/></g>')
    svg.element(id_, maat, maat, teken)


def schaduw(svg: Svg, naam: str, diepte: float, alpha: float, kleur: str = "#000000", L: float = 40) -> None:
    """Zachte schaduw rond menu's en tooltips (alleen als er een compositor is)."""
    d = diepte
    for kant, (w, h, x2, y2, omgekeerd) in {"top": (L, d, 0, 1, True), "bottom": (L, d, 0, 1, False),
                                           "left": (d, L, 1, 0, True), "right": (d, L, 1, 0, False)}.items():
        # Van 'alpha' aan de kant van het menu naar 0 aan de buitenkant. De sterkte zit in
        # het verloop zelf (stop-opacity), zodat de hoeken (radiaal) en de zijkanten gelijk oplopen.
        gid = svg.verloop_vervaag(kleur, alpha, x2, y2, omgekeerd)
        svg.element(f"{naam}-shadow-{kant}", w, h,
                    lambda x, y, w=w, h=h, gid=gid: f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" '
                    f'fill="{gid}"/>')
    for hoek, (cx, cy) in {"topleft": (1, 1), "topright": (0, 1), "bottomleft": (1, 0), "bottomright": (0, 0)}.items():
        rid = svg.radiaal(kleur, alpha, cx, cy)
        svg.element(f"{naam}-shadow-{hoek}", d, d,
                    lambda x, y, rid=rid: f'<rect x="{f(x)}" y="{f(y)}" width="{f(d)}" height="{f(d)}" fill="{rid}"/>')
    # De "hints" zeggen hoe dik de schaduw aan elke kant is (hier: overal even dik).
    for kant, (w, h) in {"top": (2, d), "bottom": (2, d), "left": (d, 2), "right": (d, 2)}.items():
        svg.element(f"{naam}-shadow-hint-{kant}", w, h, lambda x, y: "")
