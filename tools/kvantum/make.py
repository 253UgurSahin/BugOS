#!/usr/bin/env python3
"""BugOS-programmastijl voor KDE- en Qt-programma's (Kvantum), licht en donker.

Schrijft:
  system_files/usr/share/Kvantum/BugOS/BugOS.kvconfig + BugOS.svg              (licht)
  system_files/usr/share/Kvantum/BugOSDark/BugOSDark.kvconfig + .svg       (donker)
en zet in de KDE-kleurenschema's (BugOSLight.colors, BugOSDark.colors) de
kleuren die bij deze stijl horen: venster, kaart, knop en de zachte selectie.

Eén bron: alle kleuren en maten komen uit tools/design/tokens.py (dus uit
bugos_ui.py, net als de eigen BugOS-apps). Licht en donker komen uit dezelfde
code, zodat ze nooit uit elkaar lopen.

Hoe Kvantum werkt (kort): elk onderdeel (knop, invoerveld, lijst...) is een
"negenvlak" in de SVG: 4 hoeken, 4 randen en een binnenkant, per toestand
(normal = rust, focused = muis erop, pressed = ingedrukt, toggled = aan/gekozen,
disabled = uit). Ronde hoeken van 12 px krijgen we met "frame.expansion": dan
tekent Kvantum de hoeken op expansion/2 px, als het element expand-<naam>-<toestand>
bestaat; zo blijft de binnenruimte klein (frame.top=3) en worden de hoeken toch rond.

Gebruik:  python3 tools/kvantum/make.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "ontwerp"))

from tokens import KLEUREN, LIJN, MATEN, REPO, ROOD_VERLOOP, ROOD_VERLOOP_DONKER  # noqa: E402

KVANTUM = REPO / "system_files" / "usr" / "share" / "Kvantum"
SCHEMAS = REPO / "system_files" / "usr" / "share" / "color-schemes"

#: thema -> (Kvantum-naam, kleurenschema)
THEMAS = {"licht": ("BugOS", "BugOSLight"), "donker": ("BugOSDark", "BugOSDark")}

STATEN = ("normal", "focused", "pressed", "toggled", "disabled")
KNOP = MATEN["knop"]      # 12: knoppen, velden, menu's, tooltips
KAART = MATEN["kaart"]    # 16: kaarten, groepen


# ---------------------------------------------------------------- kleuren

def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexk(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def meng(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b."""
    ra, rb = rgb(a), rgb(b)
    return hexk(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lum(h: str) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def leesbaar(kleur: str, achter: list[str], naar: str, minimum: float = 4.6) -> str:
    """Schuif kleur stapje voor stapje richting `naar` tot hij op alle achtergronden AA haalt."""
    for i in range(0, 101):
        k = meng(kleur, naar, i / 100)
        if all(contrast(k, a) >= minimum for a in achter):
            return k
    return naar


def palet(thema: str) -> dict:
    """De tokens plus de paar afgeleide kleuren die Kvantum nodig heeft."""
    k = dict(KLEUREN[thema])
    donker = thema == "donker"
    k["verloop"] = ROOD_VERLOOP_DONKER if donker else ROOD_VERLOOP
    k["knop_druk"] = meng(k["knop_hover"], k["tekst"], 0.10 if donker else 0.07)
    # Zachte selectie (zoals in BugOS Instellingen): rode tint, rode tekst die AA haalt.
    k["selectie"] = k["accent_zacht"]
    k["selectie_alt"] = meng(k["accent_zacht"], k["accent_lijn"], 0.35)
    k["selectie_tekst"] = leesbaar(k["accent"], [k["selectie"], k["selectie_alt"], k["vlak"], k["achter"]],
                                   "#FFFFFF" if donker else "#000000")
    k["link"] = leesbaar(k["accent"], [k["vlak"], k["achter"]], "#FFFFFF" if donker else "#000000")
    # Tooltip zoals het kleurenschema: licht thema inkt met lichte tekst, donker thema omgekeerd.
    k["tip"] = "#16171C" if not donker else "#EDEEF1"
    k["tip_tekst"] = "#F6F5F5" if not donker else "#16171C"
    k["tip_rand"] = k["tip"]
    # Schuifbalkje: warm grijs, iets donkerder als je erop wijst (zoals QScrollBar in bugos_ui).
    k["balk"] = k["rand_sterk"]
    k["balk_hover"] = k["tekst3"]
    # Focus op labels en rijen (vinkjes, tabbladen, huidige rij): een rustig grijs streepje eronder.
    k["focus_streep"] = k["tekst3"]
    k["spoor"] = k["rand"] if not donker else k["rand_sterk"]
    k["uit_tekst"] = k["tekst3"]
    k["schaduw_kleur"] = "#000000"
    k["schaduw_alpha"] = 0.35 if donker else 0.10
    # Het bolletje van een schuif is altijd wit, met een haarlijntje (ook in donker, zoals in de apps).
    k["bol"] = "#FFFFFF"
    k["bol_rand"] = k["rand_sterk"] if not donker else "#00000000"
    k["vink_vlak"] = k["accent"]
    # Standaardknop: het accent als dunne laag over de knop (licht #EFD7D9, donker #4D2D35 in rust).
    k["standaard_tint"] = k["accent"] + ("33" if donker else "1F")
    return k


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


# ---------------------------------------------------------------- het thema

def maak_svg(k: dict) -> str:
    svg = Svg()
    donker = k is PALETTEN["donker"]
    rood = svg.verloop(k["verloop"])                    # links -> rechts
    rood_v = svg.verloop(k["verloop"], 0, 1)            # boven -> onder

    # Knoppen: plat warmgrijs, 12 px rond, geen rand.
    knop = {"normal": (k["knop"], None, 0), "focused": (k["knop_hover"], None, 0),
            "pressed": (k["knop_druk"], None, 0), "toggled": (k["selectie"], k["accent_lijn"], 1),
            "disabled": (k["knop"] + "80", None, 0)}
    kader_set(svg, "btn", "button", knop, 3, KNOP, KNOP)
    svg.element("button-default-indicator", 8, 8, lambda x, y: "")
    # Toetsenbordfocus: een rode ring van 2 px langs de rand, zoals QPushButton:focus in bugos_ui.
    # Kvantum tekent btn-focus over de knop heen; in QML (KDE Instellingen) krijgt een
    # "highlighted" knop zo ook de ring.
    negenvlak(svg, "btn", "focus", 3, 3, None, k["accent"], 2, binnen=False)
    negenvlak(svg, "button", "focus", KNOP, KNOP, None, k["accent"], 2, binnen=False)
    # De standaardknop (Open, Opslaan): in de apps rood met witte tekst, maar Kvantum kent geen eigen
    # tekstkleur voor die knop. Dus een zachte rode tint over de knop (geen ring: die betekent focus).
    # Half doorzichtig, zodat wijzen en indrukken eronder zichtbaar blijven.
    negenvlak(svg, "btn", "default", 3, 3, k["standaard_tint"])
    negenvlak(svg, "button", "default", KNOP, KNOP, k["standaard_tint"])
    for staat in ("focus", "default"):
        svg.element(f"expand-button-{staat}", 4, 4,
                    lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="4" height="4" fill="#000000"/>')

    # Knoppen op een werkbalk: zonder vlak tot je erop wijst.
    tknop = {"normal": (None, None, 0), "focused": (k["knop_hover"], None, 0),
             "pressed": (k["knop_druk"], None, 0), "toggled": (k["selectie"], None, 0),
             "disabled": (None, None, 0)}
    kader_set(svg, "tbtn", "tbutton", tknop, 3, KNOP, KNOP)

    # Invoervelden: kaartkleur, haarlijn, 12 px; met focus een rode ring van 2 px.
    veld = {"normal": (k["vlak"], k["rand_sterk"] if donker else k["rand_sterk"], 1),
            "focused": (k["vlak"], k["accent"], 2), "pressed": (k["vlak"], k["accent"], 2),
            "toggled": (k["vlak"], k["accent"], 2),
            "disabled": (meng(k["vlak"], k["achter"], 0.6), k["rand"], 1)}
    kader_set(svg, "le", "lineedit", veld, 3, KNOP, KNOP)

    # Keuzelijst (combobox): als een veld, wijzen = iets donkerdere rand.
    combo = {"normal": (k["vlak"], k["rand_sterk"], 1), "focused": (k["vlak_hover"], k["tekst3"], 1),
             "pressed": (k["vlak"], k["accent"], 2), "toggled": (k["vlak"], k["accent"], 2),
             "disabled": (meng(k["vlak"], k["achter"], 0.6), k["rand"], 1)}
    kader_set(svg, "cb", "combo", combo, 3, KNOP, KNOP)

    # Lijsten: wijzen = rustige tint, gekozen = zachte rode tint (12 px).
    rij = {"normal": (None, None, 0), "focused": (k["knop"], None, 0),
           "pressed": (k["selectie"], None, 0), "toggled": (k["selectie"], None, 0),
           "disabled": (None, None, 0)}
    kader_set(svg, "itemview", "ritemview", rij, 2, KNOP, KNOP)

    # Menu: kaart met haarlijn en 12 px hoeken; regels met 8 px wijs-tint.
    menu = {"normal": (k["vlak"], k["rand"] if not donker else k["rand_sterk"], 1)}
    kader_set(svg, "menu", "rmenu", menu, 6, KNOP, KNOP)
    mregel = {"normal": (None, None, 0), "focused": (k["knop"] if not donker else k["knop"], None, 0),
              "pressed": (k["knop"], None, 0), "toggled": (k["knop"], None, 0), "disabled": (None, None, 0)}
    kader_set(svg, "menuitem", "rmenuitem", mregel, 3, 8, 8)
    kader_set(svg, "menubaritem", "rmenubaritem", mregel, 3, 8, 8)
    negenvlak(svg, "menubar", "normal", 2, 0, k["achter"])
    schaduw(svg, "menu", 8, k["schaduw_alpha"])
    # Scheidingslijn in een menu (Kvantum rekt menuitem-separator uit over de hele regel van 9 px):
    # een haarlijn in de randkleur, met aan beide kanten wat ruimte (zoals QMenu::separator in bugos_ui).
    svg.element("menuitem-separator", 120, 9,
                lambda x, y: f'<rect x="{f(x + 6)}" y="{f(y + 4)}" width="108" height="1" {vul(k["rand"])}/>')
    # Afscheurrand van een menu (zelden): een stippellijn, Kvantum herhaalt dit stukje om de 20 px.
    for st, kl in (("normal", k["rand_sterk"]), ("focused", k["tekst3"])):
        svg.element(f"menuitem-tearoff-{st}", 20, 8,
                    lambda x, y, kl=kl: f'<rect x="{f(x + 4)}" y="{f(y + 3.5)}" width="12" height="1" {vul(kl)}/>')

    # Tooltip: inkt met lichte tekst (donker: omgekeerd), 12 px.
    tip = {"normal": (k["tip"], None, 0)}
    kader_set(svg, "tooltip", "rtooltip", tip, 4, KNOP, KNOP)
    schaduw(svg, "tooltip", 6, k["schaduw_alpha"])

    # Kaders (lijsten, scrollvlakken) en groepen: kaart met haarlijn.
    kader = {"normal": (k["vlak"], k["rand"] if not donker else k["rand"], 1),
             "focused": (k["vlak"], k["rand"] if not donker else k["rand"], 1)}
    kader_set(svg, "common", "rcommon", kader, 4, KNOP, KNOP, binnen=False)
    groep = {"normal": (k["vlak"], k["rand"], 1)}
    kader_set(svg, "group", "rgroup", groep, 4, KAART, KAART)
    tabvlak = {"normal": (k["vlak"], k["rand"], 1)}
    kader_set(svg, "tabframe", "rtabframe", tabvlak, 4, KNOP, KNOP, binnen=False)

    # Tabbladen: rustig; gekozen = zachte rode tint.
    tab = {"normal": (None, None, 0), "focused": (k["knop_hover"], None, 0), "pressed": (k["selectie"], None, 0),
           "toggled": (k["selectie"], None, 0), "disabled": (None, None, 0)}
    kader_set(svg, "tab", "rtab", tab, 3, KNOP, KNOP)
    # Kvantum tekent "tab-tear" als er tabbladen buiten beeld zijn; leeg, anders komt het standaardthema.
    svg.element("tab-tear", 8, 8, lambda x, y: "")

    # Kopjes van tabellen: kaartkleur met een lijntje eronder.
    for st, kl in {"normal": k["vlak"], "focused": k["vlak_hover"], "pressed": k["knop"], "toggled": k["vlak"],
                   "disabled": k["vlak"]}.items():
        negenvlak(svg, "header", st, 2, 0, kl, k["rand"], 1, alleen_onder=True)

    # Werkbalk, venster, dock: plat in de vensterkleur.
    negenvlak(svg, "toolbar", "normal", 2, 0, k["achter"])
    # Scheiding tussen knoppengroepen op een werkbalk: een staande haarlijn.
    svg.element("toolbar-separator", 8, 24,
                lambda x, y: f'<rect x="{f(x + 3.5)}" y="{f(y + 4)}" width="1" height="16" {vul(k["rand_sterk"])}/>')
    svg.element("window-normal", 8, 8, lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="8" height="8" {vul(k["achter"])}/>')
    negenvlak(svg, "dock", "normal", 2, 0, k["achter"])
    negenvlak(svg, "dock", "focused", 2, 0, k["achter"])
    negenvlak(svg, "titlebar", "normal", 2, 0, k["zijbalk"])
    negenvlak(svg, "titlebar", "focused", 2, 0, k["zijbalk"])

    # Schuif: spoor van 8 px, gevuld deel koraal -> rood; bolletje van 22 px.
    for st, kl in {"normal": k["spoor"], "disabled": k["spoor"] + "80"}.items():
        negenvlak(svg, "slider", st, 4, 4, kl)
    spoor(svg, "slider", "toggled", 4, k["verloop"][0], k["verloop"][1], rood_v, "y")
    negenvlak(svg, "slider", "focused", 4, 4, k["spoor"])
    negenvlak(svg, "slider", "pressed", 4, 4, k["spoor"])
    # Toetsenbordfocus op een schuif: een dun rood randje om het spoor (focusFrame=true in [Slider]);
    # een streepje eronder zou Kvantum hier gedraaid tekenen.
    negenvlak(svg, "slider", "focus", 4, 4, None, k["accent"], 1, binnen=False)
    for naam in ("slidercursor", "slidercursor-tickless"):
        for st in ("normal", "focused", "pressed", "disabled"):
            rand = k["bol_rand"] if st != "focused" else k["tekst3"]
            vulk = k["bol"] if st != "disabled" else meng(k["bol"], k["achter"], 0.5)
            ring = rand if not rand.endswith("00") else None

            def bol(x, y, vulk=vulk, ring=ring, st=st):
                m = 11
                uit = (f'<circle cx="{f(x + m)}" cy="{f(y + m + 0.8)}" r="10.2" fill="#000000" '
                       f'fill-opacity="{0.10 if not donker else 0.40}"/>')
                if ring:
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="10" {vul(ring)}/>'
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="9" {vul(vulk)}/>'
                else:
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="10" {vul(vulk)}/>'
                if st == "pressed":
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="4" {vul(k["accent"])}/>'
                return uit
            svg.element(f"{naam}-{st}", 22, 22, bol)
    svg.element("slider-tick-normal", 2, 8,
                lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="2" height="8" {vul(k["rand_sterk"])}/>')

    # Voortgang: spoor zoals de schuif, gevuld met het rode verloop.
    negenvlak(svg, "progress", "normal", 4, 4, k["spoor"])
    negenvlak(svg, "progress", "disabled", 4, 4, k["spoor"] + "80")
    spoor(svg, "progress-pattern", "normal", 4, k["verloop"][0], k["verloop"][1], rood, "x")
    spoor(svg, "progress-pattern", "focused", 4, k["verloop"][0], k["verloop"][1], rood, "x")
    negenvlak(svg, "progress-pattern", "disabled", 4, 4, k["tekst3"] + "80")

    # Schuifbalk: dun rond staafje, geen pijltjes.
    for st, (kl, w) in {"normal": (k["balk"], 6), "focused": (k["balk_hover"], 8), "pressed": (k["balk_hover"], 8),
                        "disabled": (k["balk"] + "60", 6)}.items():
        s = 6
        rr = w / 2
        off = (12 - w) / 2

        def stuk(deel, kl=kl, w=w, rr=rr, off=off):
            def teken(x, y):
                # alles in een staande balk van 12 breed: twee helften (left/right) van elk 6
                if deel in ("left", "right"):
                    if deel == "left":
                        return f'<rect x="{f(x + off)}" y="{f(y)}" width="{f(6 - off)}" height="8" {vul(kl)}/>'
                    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(6 - off)}" height="8" {vul(kl)}/>'
                # hoeken: kwart van een cirkel met straal rr, tegen de binnenkant
                links = deel.endswith("left")
                boven = deel.startswith("top")
                cx = x + 6 if links else x
                cy = y + 6 if boven else y
                # halve dop (breedte 6-off, hoogte rr) aan de binnenkant
                bx = x + off if links else x
                d = (f"M{f(cx)} {f(cy)} L{f(bx if links else cx + (6 - off))} {f(cy)} "
                     f"A{f(rr)} {f(rr)} 0 0 {1 if links == boven else 0} {f(cx)} {f(cy - rr if boven else cy + rr)} Z")
                return f'<path d="{d}" {vul(kl)}/>'
            return teken
        for deel in ("topleft", "topright", "bottomleft", "bottomright"):
            svg.element(f"scrollbarslider-{st}-{deel}", s, s, stuk(deel))
        for deel in ("left", "right"):
            svg.element(f"scrollbarslider-{st}-{deel}", s, 8, stuk(deel))
        for deel in ("top", "bottom"):
            svg.element(f"scrollbarslider-{st}-{deel}", 8, s, lambda x, y: "")
        svg.element(f"scrollbarslider-{st}", 8, 8, lambda x, y: "")

    # Vinkjes en rondjes: 18 px, rond 6; aan = rood met wit.
    def vakje(st: str, aan: str):
        def teken(x, y):
            m = 18
            if aan == "nee":
                rand = {"normal": k["rand_sterk"], "focused": k["tekst3"], "pressed": k["accent"],
                        "disabled": k["rand"]}[st]
                binnenk = k["vlak"] if st != "disabled" else meng(k["vlak"], k["achter"], 0.6)
                return (f'<rect x="{f(x + 0.75)}" y="{f(y + 0.75)}" width="{f(m - 1.5)}" height="{f(m - 1.5)}" rx="5.25" '
                        f'{vul(binnenk)} stroke="{rand}" stroke-width="1.5"/>')
            vlak = {"normal": k["accent"], "focused": k["accent_hover"], "pressed": k["accent_hover"],
                    "disabled": k["tekst3"] + "80"}[st]
            uit = f'<rect x="{f(x)}" y="{f(y)}" width="{m}" height="{m}" rx="6" {vul(vlak)}/>'
            if aan == "ja":
                d = "M5 9.4 7.9 12.3 13.2 6.4"
            else:
                d = "M5.5 9h7"
            uit += (f'<path transform="translate({f(x)} {f(y)})" d="{d}" fill="none" stroke="#FFFFFF" stroke-width="2" '
                    'stroke-linecap="round" stroke-linejoin="round"/>')
            return uit
        return teken

    def rondje(st: str, aan: bool):
        def teken(x, y):
            c = 9
            if not aan:
                rand = {"normal": k["rand_sterk"], "focused": k["tekst3"], "pressed": k["accent"],
                        "disabled": k["rand"]}[st]
                binnenk = k["vlak"] if st != "disabled" else meng(k["vlak"], k["achter"], 0.6)
                return f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="8.25" {vul(binnenk)} stroke="{rand}" stroke-width="1.5"/>'
            vlak = {"normal": k["accent"], "focused": k["accent_hover"], "pressed": k["accent_hover"],
                    "disabled": k["tekst3"] + "80"}[st]
            return (f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="9" {vul(vlak)}/>'
                    f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="3.5" fill="#FFFFFF"/>')
        return teken

    for st in ("normal", "focused", "pressed", "disabled"):
        svg.element(f"checkbox-{st}", 18, 18, vakje(st, "nee"))
        svg.element(f"checkbox-checked-{st}", 18, 18, vakje(st, "ja"))
        svg.element(f"checkbox-tristate-{st}", 18, 18, vakje(st, "half"))
        svg.element(f"radio-{st}", 18, 18, rondje(st, False))
        svg.element(f"radio-checked-{st}", 18, 18, rondje(st, True))
    # In menu's: alleen een vinkje (of stip) als het aan staat, zoals in de BugOS-apps.
    for st in ("normal", "focused"):
        svg.element(f"menu-checkbox-{st}", 18, 18, lambda x, y: "")
        icoon(svg, f"menu-checkbox-checked-{st}", lijn_pad("vink"), k["tekst"], 18, 2)
        icoon(svg, f"menu-checkbox-tristate-{st}", "M7 12h10", k["tekst"], 18, 2)
        svg.element(f"menu-radio-{st}", 18, 18, lambda x, y: "")
        svg.element(f"menu-radio-checked-{st}", 18, 18,
                    lambda x, y: f'<circle cx="{f(x + 9)}" cy="{f(y + 9)}" r="3.5" {vul(k["tekst"])}/>')

    # Pijltjes: BugOS-lijn (chevron), in de tweede tekstkleur.
    chevron = lijn_pad("rechts")
    pijlkleur = {"normal": k["tekst2"], "focused": k["tekst"], "pressed": k["tekst"], "toggled": k["selectie_tekst"],
                 "disabled": k["tekst3"] + "90"}
    for richting, draai in {"right": 0, "down": 90, "left": 180, "up": 270}.items():
        for st, kl in pijlkleur.items():
            icoon(svg, f"arrow-{richting}-{st}", chevron, kl, 16, 2, draai)
            if st != "toggled":
                icoon(svg, f"iarrow-{richting}-{st}", chevron, kl, 16, 2, draai)
    for st, kl in pijlkleur.items():
        if st == "toggled":
            continue
        icoon(svg, f"arrow-plus-{st}", "M12 6v12M6 12h12", kl, 16, 2)
        icoon(svg, f"arrow-minus-{st}", "M6 12h12", kl, 16, 2)
        icoon(svg, f"iarrow-plus-{st}", "M12 6v12M6 12h12", kl, 16, 2)
        icoon(svg, f"iarrow-minus-{st}", "M6 12h12", kl, 16, 2)
    # Boom: pijltje naar rechts (dicht) of naar onder (open).
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["tekst"]),
                   ("disabled", k["tekst3"] + "90")):
        icoon(svg, f"tree-plus-{st}", chevron, kl, 16, 2)
        icoon(svg, f"tree-minus-{st}", chevron, kl, 16, 2, 90)
    # Sluitkruisje op tabbladen.
    kruis = lijn_pad("kruis")
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["accent"]),
                   ("disabled", k["tekst3"] + "90"), ("toggled", k["selectie_tekst"])):
        icoon(svg, f"tab-close-{st}", kruis, kl, 16, 2)
    # Vensterknopjes in programma's met deelvensters (MDI); zelden gezien.
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["accent"]),
                   ("disabled", k["tekst3"] + "90")):
        icoon(svg, f"mdi-close-{st}", kruis, kl, 16, 2)
        icoon(svg, f"mdi-minimize-{st}", "M6 12h12", kl, 16, 2)
        icoon(svg, f"mdi-maximize-{st}", "M6.5 6.5h11v11h-11z", kl, 16, 2)
        icoon(svg, f"mdi-restore-{st}", "M8.5 8.5h9v9h-9zM6.5 15.5v-9h9", kl, 16, 2)
        icoon(svg, f"mdi-shade-{st}", "m7 14 5-5 5 5", kl, 16, 2)
    icoon(svg, "mdi-menu-normal", "M6 8h12M6 12h12M6 16h12", k["tekst2"], 16, 2)

    # Grepen: rustige stipjes.
    def stipjes(kl):
        def teken(x, y):
            return "".join(f'<circle cx="{f(x + 4)}" cy="{f(y + cy)}" r="1" {vul(kl)}/>' for cy in (8, 12, 16))
        return teken
    for st, kl in (("normal", k["rand_sterk"]), ("focused", k["tekst3"]), ("pressed", k["accent"])):
        svg.element(f"splitter-grip-{st}", 8, 24, stipjes(kl))
    svg.element("toolbar-handle", 8, 24, stipjes(k["rand_sterk"]))
    svg.element("resize-grip-normal", 12, 12,
                lambda x, y: "".join(f'<circle cx="{f(x + a)}" cy="{f(y + b)}" r="1" {vul(k["tekst3"])}/>'
                                     for a, b in ((10, 10), (6, 10), (10, 6))))
    # Draaiknop (QDial), zelden gebruikt.
    svg.element("dial", 40, 40, lambda x, y: f'<circle cx="{f(x + 20)}" cy="{f(y + 20)}" r="19" {vul(k["knop"])} '
                f'stroke="{k["rand_sterk"]}" stroke-width="1"/>')
    svg.element("dial-handle", 8, 8, lambda x, y: f'<circle cx="{f(x + 4)}" cy="{f(y + 4)}" r="4" {vul(k["accent"])}/>')
    svg.element("dial-notches", 40, 40, lambda x, y: "")

    # Focus op een label of rij (PE_FrameFocusRect: vinkjes, rondjes, tabbladen, schuif, de huidige rij
    # in lijsten en in Dolphin): Kvantum zoekt "focus-top" enz. zonder toestand, op hoogstens 2 px.
    # Ontbreken ze, dan tekent Kvantum de stippelrand van zijn eigen standaardthema. BugOS: een rustig
    # grijs streepje van 2 px onderaan (een rij met focus blijft grijs, zoals in de BugOS-apps).
    for deel, (w, h) in {"top": (8, 2), "bottom": (8, 2), "left": (2, 8), "right": (2, 8), "topleft": (2, 2),
                         "topright": (2, 2), "bottomleft": (2, 2), "bottomright": (2, 2)}.items():
        onder = deel.startswith("bottom")
        svg.element(f"focus-{deel}", w, h,
                    lambda x, y, w=w, h=h, onder=onder:
                    f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" {vul(k["focus_streep"])}/>'
                    if onder else "")
    return svg.tekst()


def maak_kvconfig(thema: str, k: dict) -> str:
    donker = thema == "donker"
    naam = THEMAS[thema][0]
    st = k["selectie_tekst"]
    e_knop = KNOP * 2     # frame.expansion: hoeken van 12 px
    e_kaart = KAART * 2   # hoeken van 16 px
    e_regel = 16          # hoeken van 8 px (menu-regels)
    tekst = k["tekst"]
    t2 = k["tekst2"]

    def sectie(titel: str, **sleutels) -> str:
        # Knoppen met een vlak zijn halfvet (zoals QPushButton in bugos_ui: font-weight 600). Alles wat
        # verder van PanelButtonCommand erft (vinkjes, lijsten, tabbladen, werkbalkknoppen) blijft gewoon.
        if "inherits" in sleutels and "text__bold" not in sleutels and titel != "PanelButtonTool":
            sleutels["text__bold"] = False
        regels = [f"[{titel}]"]
        for s, v in sleutels.items():
            s = s.replace("__", ".")
            if isinstance(v, bool):
                v = "true" if v else "false"
            regels.append(f"{s}={v}")
        return "\n".join(regels) + "\n"

    def kader(element, groot, rand, expansie, **extra):
        d = dict(frame=True, frame__element=element, frame__expandedElement=groot,
                 frame__top=rand, frame__bottom=rand, frame__left=rand, frame__right=rand,
                 frame__expansion=expansie)
        d.update(extra)
        return d

    delen = [f"""# BugOS-programmastijl voor Kvantum ({"donker" if donker else "licht"}).
# Gemaakt door tools/kvantum/make.py uit tools/design/tokens.py; niet met de hand bewerken.
"""]
    delen.append(sectie(
        "%General",
        author="BugOS", comment=f"The BugOS style for KDE and Qt apps ({'dark' if donker else 'light'})",
        x11drag="menubar_and_primary_toolbar", alt_mnemonic=True, respect_DE=True, click_behavior=0,
        composite=True, translucent_windows=False, blurring=False, popup_blurring=False,
        reduce_window_opacity=0, reduce_menu_opacity=0, no_window_pattern=False, no_inactiveness=True,
        menu_shadow_depth=8, tooltip_shadow_depth=6, menu_blur_radius=0, tooltip_blur_radius=0,
        shadowless_popup=False, animate_states=True,
        layout_spacing=6, layout_margin=12, small_icon_size=16, large_icon_size=32, button_icon_size=16,
        toolbar_icon_size=22, toolbutton_style=0,
        # transient_groove=false: geen half doorzichtige baan met een streep ernaast, alleen het staafje
        # (zoals in de BugOS-apps).
        scroll_width=12, scroll_min_extent=36, scroll_arrows=False, transient_scrollbar=True,
        transient_groove=False, scrollbar_in_view=True,
        slider_width=MATEN["schuif_spoor"], slider_handle_width=MATEN["schuif_knop"],
        slider_handle_length=MATEN["schuif_knop"], tickless_slider_handle_size=MATEN["schuif_knop"],
        check_size=18, progressbar_thickness=MATEN["schuif_spoor"], textless_progressbar=False, spread_progressbar=True,
        combo_as_lineedit=False, square_combo_button=False, combo_menu=True, hide_combo_checkboxes=True,
        combo_focus_rect=False, inline_spin_indicators=True, vertical_spin_indicators=False,
        inline_spin_separator=False, spin_button_width=24,
        groupbox_top_label=True, spread_menuitems=True, spread_header=True, menu_separator_height=9,
        scrollable_menu=True, submenu_overlap=0, submenu_delay=250, tooltip_delay=-1,
        merge_menubar_with_toolbar=True, menubar_mouse_tracking=True,
        left_tabs=False, attach_active_tab=False, embedded_tabs=False, mirror_doc_tabs=True,
        joined_inactive_tabs=False, bold_active_tab=False, no_active_tab_separator=True,
        group_toolbar_buttons=False, toolbar_item_spacing=2, toolbar_interior_spacing=4,
        center_toolbar_handle=True, slim_toolbars=False, fill_rubberband=False, tree_branch_line=False,
        splitter_width=7, drag_from_buttons=False, contrast="1.00", intensity="1.00", saturation="1.00",
    ))
    delen.append(sectie(
        "GeneralColors",
        window__color=k["achter"], inactive__window__color=k["achter"],
        base__color=k["vlak"], inactive__base__color=k["vlak"],
        alt__base__color=meng(k["vlak"], k["achter"], 0.55 if not donker else 0.0) if not donker else k["vlak_hover"],
        inactive__alt__base__color=meng(k["vlak"], k["achter"], 0.55) if not donker else k["vlak_hover"],
        button__color=k["knop"],
        light__color=k["vlak"] if not donker else k["rand_sterk"],
        mid__light__color=k["achter"] if not donker else k["knop_hover"],
        mid__color=k["rand"], dark__color=k["rand_sterk"] if not donker else "#0B0C0F",
        highlight__color=k["selectie"], inactive__highlight__color=k["selectie"],
        text__color=tekst, inactive__text__color=tekst, window__text__color=tekst,
        inactive__window__text__color=tekst, button__text__color=tekst, inactive__button__text__color=tekst,
        disabled__text__color=k["tekst3"],
        tooltip__base__color=k["tip"], tooltip__text__color=k["tip_tekst"],
        highlight__text__color=st, inactive__highlight__text__color=st,
        link__color=k["link"], link__visited__color="#8B3FA8" if not donker else "#C08CE0",
        progress__indicator__text__color=tekst, progress__inactive__indicator__text__color=tekst,
    ))
    delen.append(sectie(
        "Hacks",
        transparent_ktitle_label=True, transparent_dolphin_view=False, transparent_pcmanfm_sidepane=True,
        transparent_pcmanfm_view=False, blur_translucent=False, transparent_menutitle=True,
        respect_darkness=False, force_size_grip=False, iconless_pushbutton=False, iconless_menu=False,
        disabled_icon_opacity=50, normal_default_pushbutton=True, single_top_toolbar=True,
        tint_on_mouseover=0, no_selection_tint=True, transparent_arrow_button=True,
        middle_click_scroll=False, kinetic_scrolling=False, centered_forms=False, lxqtmainmenu_iconsize=0,
        style_vertical_toolbars=False,
    ))
    knoptekst = dict(text__normal__color=tekst, text__focus__color=tekst, text__press__color=tekst,
                     text__toggle__color=st, text__shadow=False, text__bold=True, text__boldness=2)
    delen.append(sectie(
        "PanelButtonCommand",
        **kader("btn", "button", 3, e_knop), interior=True, interior__element="button", focusFrame=True,
        indicator__element="arrow", indicator__size=12, text__margin=1, text__iconspacing=6,
        text__margin__top=5, text__margin__bottom=5, text__margin__left=9, text__margin__right=9,
        min_width="+0.3font", **knoptekst))
    # Losse gereedschapsknoppen: dezelfde ronde knop (de sleutels hier nog eens, anders blijven de hoeken klein).
    delen.append(sectie("PanelButtonTool", inherits="PanelButtonCommand", **kader("btn", "button", 3, e_knop),
                        interior=True, interior__element="button"))
    delen.append(sectie(
        "ToolbarButton", inherits="PanelButtonCommand", **kader("tbtn", "tbutton", 3, e_knop),
        interior__element="tbutton", text__margin__top=4, text__margin__bottom=4, text__margin__left=5,
        text__margin__right=5, min_width=0, focusFrame=False))
    delen.append(sectie("Dock", inherits="PanelButtonCommand", frame=False, interior=False,
                        text__normal__color=tekst))
    delen.append(sectie("DockTitle", inherits="PanelButtonCommand", frame=False, interior=False,
                        text__normal__color=t2, text__focus__color=tekst, text__bold=False,
                        text__margin__top=4, text__margin__bottom=4))
    delen.append(sectie("IndicatorSpinBox", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="iarrow", indicator__size=12, text__normal__color=tekst))
    delen.append(sectie("RadioButton", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="radio", text__margin__top=2, text__margin__bottom=2,
                        text__margin__left=2, text__margin__right=2, text__focus__color=tekst,
                        text__toggle__color=tekst, focusFrame=False))
    delen.append(sectie("CheckBox", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="checkbox", text__margin__top=2, text__margin__bottom=2,
                        text__margin__left=2, text__margin__right=2, text__focus__color=tekst,
                        text__toggle__color=tekst, focusFrame=False))
    # Kvantum tekent dit kader altijd zonder ronde hoeken en hoogstens 2 px dik (zie focus-* in de SVG).
    delen.append(sectie("Focus", inherits="PanelButtonCommand", interior=False, frame=True, frame__element="focus",
                        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0))
    delen.append(sectie("GenericFrame", inherits="PanelButtonCommand", interior=False,
                        **kader("common", "rcommon", 4, e_knop), interior__element="common", focusFrame=False))
    delen.append(sectie(
        "LineEdit", inherits="PanelButtonCommand", **kader("le", "lineedit", 3, e_knop),
        interior=True, interior__element="lineedit", text__margin__top=4, text__margin__bottom=4,
        text__margin__left=7, text__margin__right=7, focusFrame=False))
    delen.append(sectie("ToolbarLineEdit", inherits="LineEdit"))
    delen.append(sectie("DropDownButton", inherits="PanelButtonCommand", indicator__element="arrow-down",
                        indicator__size=12))
    delen.append(sectie("IndicatorArrow", indicator__element="arrow", indicator__size=12))
    delen.append(sectie("ToolboxTab", inherits="PanelButtonCommand", text__normal__color=tekst,
                        text__press__color=tekst, text__focus__color=tekst))
    delen.append(sectie(
        "Tab", inherits="PanelButtonCommand", **kader("tab", "rtab", 3, e_knop), interior=True,
        interior__element="tab", indicator__element="tab", indicator__size=16, focusFrame=False,
        text__margin__top=4, text__margin__bottom=4, text__margin__left=10, text__margin__right=10,
        text__normal__color=t2, text__focus__color=tekst, text__press__color=st, text__toggle__color=st,
        min_width="4font"))
    delen.append(sectie("TabFrame", inherits="PanelButtonCommand", interior=False,
                        **kader("tabframe", "rtabframe", 4, e_knop), focusFrame=False))
    delen.append(sectie("TabBarFrame", inherits="GenericFrame", frame=False, interior=False))
    delen.append(sectie("TreeExpander", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="tree", indicator__size=14))
    delen.append(sectie(
        "HeaderSection", inherits="PanelButtonCommand", frame=True, frame__element="header",
        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0,
        frame__expandedElement="header", interior=True, interior__element="header",
        text__margin__top=4, text__margin__bottom=4, text__margin__left=6, text__margin__right=6,
        text__normal__color=t2, text__focus__color=tekst, text__press__color=tekst, text__toggle__color=tekst,
        text__bold=False, focusFrame=False))
    delen.append(sectie("SizeGrip", indicator__element="resize-grip"))
    delen.append(sectie("Toolbar", inherits="PanelButtonCommand", frame=True, frame__element="toolbar",
                        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0,
                        interior=True, interior__element="toolbar", indicator__element="toolbar",
                        indicator__size=8, text__margin=0, text__normal__color=tekst, focusFrame=False))
    delen.append(sectie("Slider", inherits="PanelButtonCommand", frame=True, frame__element="slider",
                        frame__expandedElement="slider", frame__top=4, frame__bottom=4, frame__left=4,
                        frame__right=4, frame__expansion=0, interior=True, interior__element="slider",
                        focusFrame=True))
    delen.append(sectie("SliderCursor", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="slidercursor", focusFrame=False))
    delen.append(sectie("Progressbar", inherits="PanelButtonCommand", frame=True, frame__element="progress",
                        frame__expandedElement="progress", frame__top=4, frame__bottom=4, frame__left=4,
                        frame__right=4, frame__expansion=0, interior=True, interior__element="progress",
                        text__margin=0, text__normal__color=tekst, text__focus__color=tekst,
                        text__press__color=tekst, text__toggle__color=tekst, text__bold=False, focusFrame=False))
    delen.append(sectie("ProgressbarContents", inherits="PanelButtonCommand", frame=True,
                        frame__element="progress-pattern", frame__expandedElement="progress-pattern",
                        frame__top=4, frame__bottom=4, frame__left=4, frame__right=4, frame__expansion=0,
                        interior=True, interior__element="progress-pattern", focusFrame=False))
    delen.append(sectie(
        "ItemView", inherits="PanelButtonCommand", **kader("itemview", "ritemview", 2, e_knop),
        interior=True, interior__element="itemview", text__margin=0, text__margin__top=3,
        text__margin__bottom=3, text__margin__left=6, text__margin__right=6, text__normal__color=tekst,
        text__focus__color=tekst, text__press__color=st, text__toggle__color=st, min_width=0, min_height=0,
        focusFrame=False))
    delen.append(sectie("Splitter", indicator__size=24))
    delen.append(sectie("Scrollbar", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="arrow", indicator__size=10))
    delen.append(sectie("ScrollbarSlider", inherits="PanelButtonCommand", frame=True,
                        frame__element="scrollbarslider", frame__expandedElement="scrollbarslider",
                        frame__top=6, frame__bottom=6, frame__left=6, frame__right=6, frame__expansion=0,
                        interior=False, indicator__element="grip", indicator__size=0, focusFrame=False))
    delen.append(sectie("ScrollbarGroove", inherits="PanelButtonCommand", frame=False, interior=False))
    delen.append(sectie(
        "MenuItem", inherits="PanelButtonCommand", **kader("menuitem", "rmenuitem", 3, e_regel),
        interior=True, interior__element="menuitem", indicator__element="menuitem", indicator__size=12,
        # Zelfde ruimte als QMenu::item in bugos_ui (Instellingen, Bestanden): 9 px boven en onder,
        # 12 px links. Het kader neemt er al 3 van; de tekstmarge doet de rest.
        text__margin__top=6, text__margin__bottom=6, text__margin__left=9, text__margin__right=12,
        text__normal__color=tekst, text__focus__color=tekst, text__press__color=tekst,
        text__toggle__color=tekst, min_width=0, min_height=0, focusFrame=False))
    delen.append(sectie("MenuBar", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="menubar", frame__element="menubar"))
    delen.append(sectie(
        "MenuBarItem", inherits="PanelButtonCommand", **kader("menubaritem", "rmenubaritem", 3, e_regel),
        interior=True, interior__element="menubaritem", text__margin__top=3, text__margin__bottom=3,
        text__margin__left=6, text__margin__right=6, text__normal__color=tekst, text__focus__color=tekst,
        text__press__color=tekst, text__toggle__color=tekst, min_width=0, min_height=0, focusFrame=False))
    delen.append(sectie("TitleBar", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="titlebar", indicator__element="mdi", indicator__size=16,
                        text__normal__color=t2, text__focus__color=tekst, text__bold=True, text__italic=False))
    delen.append(sectie("ComboBox", inherits="PanelButtonCommand", **kader("cb", "combo", 3, e_knop),
                        interior=True, interior__element="combo", text__margin__left=7, text__margin__right=7,
                        indicator__element="arrow", indicator__size=12, text__toggle__color=tekst))
    delen.append(sectie("ToolbarComboBox", inherits="ComboBox"))
    delen.append(sectie("Menu", inherits="PanelButtonCommand", **kader("menu", "rmenu", 6, e_knop),
                        interior=True, interior__element="menu", text__normal__color=tekst, focusFrame=False))
    delen.append(sectie("GroupBox", inherits="GenericFrame", **kader("group", "rgroup", 4, e_kaart),
                        interior=True, interior__element="group", text__margin=0, text__margin__top=0,
                        text__margin__bottom=4, text__margin__left=2, text__margin__right=2,
                        # Kopje boven een kaart zoals in de BugOS-apps ("sectie"): tweede tekstkleur, halfvet.
                        text__normal__color=t2, text__press__color=tekst, text__focus__color=tekst,
                        text__bold=True, text__boldness=2, focusFrame=False))
    delen.append(sectie("ToolTip", inherits="GenericFrame", **kader("tooltip", "rtooltip", 4, e_knop),
                        interior=True, interior__element="tooltip", text__margin__top=4, text__margin__bottom=4,
                        text__margin__left=6, text__margin__right=6, text__normal__color=k["tip_tekst"],
                        text__focus__color=k["tip_tekst"], text__shadow=False))
    delen.append(sectie("StatusBar", inherits="GenericFrame", frame=False, interior=False))
    delen.append(sectie("Window", interior=True, interior__element="window", frame=False))
    delen.append(sectie("Dialog", inherits="Window"))
    return "\n".join(delen)


# ---------------------------------------------------------------- KDE-kleurenschema

def _drie(h: str) -> str:
    return ",".join(str(v) for v in rgb(h))


def schema_kleuren(thema: str, k: dict) -> dict[str, dict[str, str]]:
    """De sleutels in het kleurenschema die bij deze stijl horen (de rest blijft zoals hij is)."""
    donker = thema == "donker"
    sel = {
        # Zachte selectie: rode tint met rode tekst die AA haalt (nooit een volle rode balk).
        "BackgroundNormal": _drie(k["selectie"]),
        "BackgroundAlternate": _drie(k["selectie_alt"]),
        "ForegroundNormal": _drie(k["selectie_tekst"]),
        "ForegroundActive": _drie(k["selectie_tekst"]),
        "ForegroundInactive": _drie(k["tekst2"]),
        "ForegroundLink": _drie(k["selectie_tekst"]),
        "ForegroundVisited": "139,63,168" if not donker else "192,140,224",
        "ForegroundNegative": _drie(k["fout"]),
        "ForegroundNeutral": _drie(k["let_op"]),
        "ForegroundPositive": _drie(k["goed"]),
        # Focus en accent blijven het BugOS-rood.
        "DecorationFocus": _drie(k["accent"]),
    }
    uit = {"Colors:Selection": sel}
    if donker:
        # Donker: pagina = achtergrond, lijsten en kaarten iets lichter (zoals de BugOS-apps).
        uit["Colors:Window"] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["zijbalk"])}
        uit["Colors:View"] = {"BackgroundNormal": _drie(k["vlak"]), "BackgroundAlternate": _drie(k["vlak_hover"])}
        uit["Colors:Button"] = {"BackgroundNormal": _drie(k["knop"]), "BackgroundAlternate": _drie(k["knop_hover"])}
        uit["ColorEffects:Disabled"] = {"Color": _drie(k["achter"])}
        uit["ColorEffects:Inactive"] = {"Color": _drie(k["achter"])}
    else:
        uit["Colors:Window"] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["zijbalk"])}
        uit["Colors:View"] = {"BackgroundNormal": _drie(k["vlak"])}
        uit["Colors:Button"] = {"BackgroundNormal": _drie(k["knop"]), "BackgroundAlternate": _drie(k["knop_hover"])}
    # Eén vlak per venster, zoals Windows 11 en macOS: de vensterbalk (WM), de kop- en
    # werkbalken (Header) en de zijbalk hebben precies de vensterkleur. Zo loopt de titelbalk
    # naadloos over in het venster, bij de eigen apps en bij KDE-programma's.
    for groep in ("Colors:Header", "Colors:Header][Inactive"):
        uit[groep] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["achter"])}
    uit["WM"] = {"activeBackground": _drie(k["achter"]), "inactiveBackground": _drie(k["achter"])}
    # ForegroundActive is in KDE de kleur van een gewone mededeling (Kirigami InlineMessage en Badge
    # "Information"): een rand in die kleur en een vlak met 20% ervan. Rood maakte van elke mededeling
    # in KDE Instellingen een foutmelding; BugOS houdt een mededeling rustig grijs ("alleen wat aandacht
    # nodig heeft krijgt kleur", Melding in bugos_ui = knopgrijs). tekst3 geeft een licht vlak met een
    # zachte rand (tekst2 werd een zwaar grijs blok). Rood blijft voor focus (DecorationFocus), de
    # selectie en fouten (ForegroundNegative).
    for groep in ("Colors:Window", "Colors:View", "Colors:Button", "Colors:Header", "Colors:Header][Inactive"):
        uit.setdefault(groep, {})["ForegroundActive"] = _drie(k["tekst3"])
    return uit


def schema_bijwerken(pad: Path, wijzig: dict[str, dict[str, str]]) -> str:
    """Zet alleen de gegeven sleutels; volgorde, andere groepen en [WM] blijven precies zoals ze zijn."""
    regels = pad.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    groep = None
    gezien: dict[str, set[str]] = {}
    uit = []
    for r in regels:
        m = re.match(r"^\[(.+)\]$", r)
        if m:
            groep = m.group(1)
            gezien.setdefault(groep, set())
        elif groep in wijzig and "=" in r:
            sleutel = r.split("=", 1)[0]
            if sleutel in wijzig[groep]:
                r = f"{sleutel}={wijzig[groep][sleutel]}"
                gezien[groep].add(sleutel)
        uit.append(r)
    ontbreekt = [(g, s) for g, d in wijzig.items() for s in d if s not in gezien.get(g, set())]
    if ontbreekt:
        raise SystemExit(f"{pad.name}: sleutels niet gevonden: {ontbreekt}")
    tekst = "\n".join(uit)
    return tekst if tekst.endswith("\n") else tekst + "\n"


PALETTEN = {t: palet(t) for t in THEMAS}


def main() -> int:
    for thema, (kvnaam, schema) in THEMAS.items():
        k = PALETTEN[thema]
        doel = KVANTUM / kvnaam
        doel.mkdir(parents=True, exist_ok=True)
        (doel / f"{kvnaam}.kvconfig").write_text(maak_kvconfig(thema, k), encoding="utf-8", newline="\n")
        (doel / f"{kvnaam}.svg").write_text(maak_svg(k), encoding="utf-8", newline="\n")
        pad = SCHEMAS / f"{schema}.colors"
        pad.write_text(schema_bijwerken(pad, schema_kleuren(thema, k)), encoding="utf-8", newline="\n")
        print(f"{thema}: {doel.relative_to(REPO)}  selectie {k['selectie']} / tekst {k['selectie_tekst']} "
              f"(contrast {contrast(k['selectie_tekst'], k['selectie']):.2f}:1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
